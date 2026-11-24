#!/usr/bin/env python3
"""lage_frueh.py - VORSTUFE 'LAGE FRUEH' der Gesamtkette: Ausrichtung + GPS-Tor + Lageproben auf dem DUENNEN SfM-Netz, VOR der dichten Wolke (22.11.2026).

WARUM: die Lage-Tore liefen erst in gesamtkette 'tore' nach pipeline_objekt (SfM + 40-60 min Tiefenkarten/Fusion + Ausrichtung). GPS-Tor, Lageproben und der Teil-Beleg
brauchen nur Kameras + eine Punktwolke fuer die Ausrichtung: am 22.11. brachen 1122b/1122g/1122k erst nach der dichten Wolke an der Lage ab. Diese Stufe rechnet die
ECHTE Ausrichtung (sfm_lod2_ausrichten.ausrichten, gleiche Argumente wie pipeline_objekt) auf den sparse-Punkten von <P>/sfm/sparse/0 (Spur >= 3, Fehler < p90 - dieselbe
Auswahl wie die Ausrichtung mit --sparse) und danach die ECHTEN Tore: lage_gps_pruefen.main, lage_proben.tor_rc, Regel lage_proben.lage_frueh_bestanden (= lage_bestanden
ohne Grundriss), Korrekturkreislauf wie gesamtkette (--loesung 1..max, bis eine besteht). Teil-Beleg (seiten_lage_beleg ueber lage_pruefstand.seiten_beleg) nur Bericht.
NICHT hier: Grundriss-Tor A und wand_dicke (brauchen die dichte Wolke; eine sparse-Fassung mit umgerechneten Grenzen ist an 1120/1122 noch nicht als gleichurteilend
belegt - Torgrenzen werden nicht gelockert). Die spaeten Tore der Kette bleiben unveraendert (diese Stufe ist zusaetzlich).
Schreibt NUR nach --aus (Standard <P>/lage_frueh): objekt.json-Kopie (fotos_dir absolut), sparse_punkte.ply, messprotokoll/ (Ausrichtung + Zwischenstand), audit/ (Tore),
lage_frueh.json, lage_frueh.log. Das Objekt (modelle/<ziel>) bleibt unberuehrt.
Aufruf: tools/py tools/lage_frueh.py <objekt.json> <pipe-ordner P> <fotoordner> --ziel <name> [--aus DIR] [--max-loesung 3] [--radius 30]
Exit: 0 = eine Loesung besteht (oder kein Tor urteilt), 3 = EINDEUTIG durchgefallen (jede probierte Loesung von einem geprueften Tor verworfen, rc 3),
      4 = kein Urteil (Werkzeug abgestuerzt, Eingaben fehlen) - die Kette rechnet dann weiter, die spaeten Tore entscheiden."""
import os, sys, json, time, struct, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(T); sys.path.insert(0, T)
PY_COL = "/media/oem/scan/venv-colmap/bin/python"


def sparse_lesen(pfad):
    """COLMAP points3D.bin -> (P n x 3, Farbe n x 3 uint8, Fehler n, Spurlaenge n). Reiner numpy/struct-Leser (laeuft in jeder Umgebung, kein pycolmap)."""
    raw = open(pfad, "rb").read(); n = struct.unpack_from("<Q", raw, 0)[0]; o = 8
    P = np.empty((n, 3)); F = np.empty((n, 3), np.uint8); E = np.empty(n); L = np.empty(n, np.int64)
    for i in range(n):
        x, y, z = struct.unpack_from("<3d", raw, o + 8); F[i] = struct.unpack_from("<3B", raw, o + 32); e, tl = struct.unpack_from("<dQ", raw, o + 35)
        P[i] = (x, y, z); E[i] = e; L[i] = tl; o += 51 + 8 * tl
    return P, F, E, L


def sparse_ply(sparse_dir, ply):
    """sparse-Punkte (Spur >= 3, Fehler < p90 wie sfm_lod2_ausrichten mit --sparse) als PLY im Format der dichten Wolke (x y z nx ny nz r g b) -> Zahl der Punkte.
    Nur neu, wenn points3D.bin neuer ist als das PLY."""
    q = os.path.join(sparse_dir, "points3D.bin")
    if os.path.isfile(ply) and os.path.getmtime(ply) >= os.path.getmtime(q):
        with open(ply, "rb") as f: kopf = f.read(400).decode(errors="ignore")
        return int([l for l in kopf.splitlines() if l.startswith("element vertex")][0].split()[-1])
    P, F, E, L = sparse_lesen(q); gut = (L >= 3) & (E < np.percentile(E, 90)) if len(E) else np.zeros(0, bool)
    dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
    V = np.zeros(int(gut.sum()), dt); V["x"], V["y"], V["z"] = P[gut].T; V["r"], V["g"], V["b"] = F[gut].T
    os.makedirs(os.path.dirname(ply), exist_ok=True); tmp = ply + ".neu"
    with open(tmp, "wb") as f:
        f.write(f"ply\nformat binary_little_endian 1.0\nelement vertex {len(V)}\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\n"
                "property float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n".encode()); f.write(V.tobytes())
    os.replace(tmp, ply); return len(V)


def eindeutig_durchgefallen(laeufe):
    """Abbruchregel: jede probierte Loesung wurde von mindestens einem GEPRUEFTEN Tor mit rc 3 verworfen (GPS-Tor oder Lageproben) und kein Tor ist abgestuerzt."""
    return bool(laeufe) and all(l.get("tore") and not l.get("kaputt") and not l.get("bestanden") and 3 in (l["tore"].get("gps"), l["tore"].get("lage_proben")) for l in laeufe)


def sfm_mit_vorstufe(B, lauf, notiz, pipe_cmd, neu_sfm, objekt_rel, P, FV, ziel, log, timeout, py=sys.executable):
    """Kettenstufe 'sfm' mit Vorstufe (aufgerufen von tools/gesamtkette.py, Schalter RCPARK_LAGE_FRUEH: '1' Standard = Abbruch bei eindeutigem Durchfall, 'hinweis' = nur
    Bericht, '0' = aus und der bisherige Einzelaufruf in gesamtkette). Ablauf: pipeline_objekt.py ... --bis kameras (SfM + kameras.json) -> lage_frueh.py -> bei rc 3
    Abbruch VOR der dichten Wolke; sonst pipeline_objekt.py ein zweites Mal OHNE --neu/RCPARK_PIPE_NEU (die SfM des ersten Aufrufs darf nicht beiseitegelegt werden).
    lauf/notiz = die Funktionen der Kette (Bericht, Speicher-Wiederholung, Zeitlimit). -> (rc der SfM-Stufe, Abbruchtext oder None)."""
    modus = os.environ.get("RCPARK_LAGE_FRUEH", "1")
    rc_b = lauf(B, "sfm_bis_kameras", pipe_cmd + neu_sfm + ["--bis", "kameras"], log, platz=[P], timeout=timeout)[0]
    if rc_b != 0: return rc_b, None                                                    # SfM gescheitert: die Kette meldet es wie bisher
    rc_f, _ = lauf(B, "lage_frueh", [py, "-u", "-I", "tools/lage_frueh.py", objekt_rel, P, FV, "--ziel", ziel], log, ok=(0, 3, 4))
    try: J = json.load(open(os.path.join(P, "lage_frueh", "lage_frueh.json")))
    except Exception: J = {}
    kurz = [dict(loesung=l.get("loesung"), tore=l.get("tore"), gps=(l.get("gps") or {}), bestanden=l.get("bestanden")) for l in J.get("laeufe") or []]
    notiz(B, "lage_frueh", rc_f == 0, rc=rc_f, modus=modus, grund=J.get("grund"), loesung=J.get("loesung"), laeufe=kurz, sekunden=J.get("sekunden"), teil_beleg=J.get("teil_beleg"),
          hinweis="Vorstufe vor der dichten Wolke (tools/lage_frueh.py): Ausrichtung auf dem duennen Netz + GPS-Tor + Lageproben; Grundriss/Wanddicke erst in 'tore'")
    if rc_f == 3 and modus == "1":
        B["lage"] = dict(bestanden=False, fehler="lage_frueh", tore=kurz, hinweis="vor der dichten Wolke durchgefallen (pipe/lage_frueh/lage_frueh.json)")
        return 0, (f"LAGE FRUEH: {J.get('grund')} - dichte Wolke NICHT gerechnet (Abhilfe: Fotos/Seiten pruefen; nur melden statt abbrechen: RCPARK_LAGE_FRUEH=hinweis, aus: 0)")
    # 24.11.2026 EINE Fusion je Lauf (tools/fusion_vorab.py): Ausschlusslisten der Tore (Kameras unter Gelaende, Insel-Ketten, Wolken-Gruppen) brauchen keine dichte Wolke ->
    # hier auf der Ausrichtung des duennen Netzes vorab rechnen; feuert die Neufusion-Regel sicher, kuerzt dicht_kette.py die fusion.cfg schon vor der ersten Fusion.
    try: __import__("fusion_vorab").plan(P, ziel, lauf, B, log, py_col=PY_COL, py="python3")
    except Exception as e: print(f"FUSION VORAB: Plan gescheitert ({type(e).__name__}: {e}) - alte Doppelfusion", flush=True)
    alt = os.environ.pop("RCPARK_PIPE_NEU", None)
    try: rc_s = lauf(B, "sfm", pipe_cmd, log, platz=[P], timeout=timeout)[0]
    finally:
        if alt is not None: os.environ["RCPARK_PIPE_NEU"] = alt
    return rc_s, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("objekt"); ap.add_argument("pipe"); ap.add_argument("fotos"); ap.add_argument("--ziel", required=True)
    ap.add_argument("--aus", default=None); ap.add_argument("--max-loesung", type=int, default=3, dest="max_loesung"); ap.add_argument("--radius", default="30")
    a = ap.parse_args(argv)
    import lage_pruefstand as LPS, lage_proben as LP, lage_gps_pruefen as LGP, sfm_lod2_ausrichten as SA
    t0 = time.time(); aus = os.path.abspath(a.aus or os.path.join(a.pipe, "lage_frueh")); os.makedirs(aus, exist_ok=True); log = os.path.join(aus, "lage_frueh.log")
    sp = os.path.join(a.pipe, "sfm", "sparse", "0"); kj = os.path.join(a.pipe, "kameras.json")
    R = dict(werkzeug="lage_frueh.py", zeit=time.strftime("%Y-%m-%d %H:%M"), ziel=a.ziel, sparse=sp, laeufe=[])
    fehlt = [p for p in (a.objekt, kj, os.path.join(sp, "points3D.bin")) if not os.path.isfile(p)] + ([a.fotos] if not os.path.isdir(a.fotos) else [])
    def ende(rc, grund):
        R.update(rc=rc, grund=grund, sekunden=round(time.time() - t0, 1)); json.dump(R, open(os.path.join(aus, "lage_frueh.json"), "w"), indent=1, ensure_ascii=False, default=LPS._json_sicher)
        print(f"LAGE FRUEH: rc {rc} - {grund} ({R['sekunden']:.0f} s, {os.path.join(aus, 'lage_frueh.json')})", flush=True); return rc
    if fehlt: return ende(4, "Eingaben fehlen: " + ", ".join(fehlt))
    ok_ = LPS.objekt_kopie(a.objekt, aus, a.fotos); ply = os.path.join(aus, "sparse_punkte.ply")
    R["sparse_punkte"] = sparse_ply(sp, ply); print(f"sparse-Punkte fuer die Ausrichtung: {R['sparse_punkte']} (Spur >= 3, Fehler < p90) -> {ply}", flush=True)
    if R["sparse_punkte"] < 1000: return ende(4, f"nur {R['sparse_punkte']} sparse-Punkte - kein Urteil")
    au = os.path.join(aus, "messprotokoll", f"SFM-AUSRICHTUNG-{a.ziel}.json"); lj = os.path.join(aus, "audit", "lage_gps.json")
    basis = [ok_, "--kameras", kj, "--dicht", ply, "--name", a.ziel, "--radius", str(a.radius), "--schreiben", "--fotos", a.fotos]
    for k in range(a.max_loesung + 1):
        t1 = time.time()
        try:
            with LPS.Mitschrift(log): E = SA.ausrichten(basis + ["--loesung", str(k)])
        except Exception as e:
            R["laeufe"].append(dict(loesung=k, kaputt=True, fehler=f"Ausrichtung: {type(e).__name__}: {e}")); return ende(4, f"Ausrichtung Loesung {k} abgestuerzt ({type(e).__name__}: {e}) - kein Urteil")
        if E["rc"] == 5 and E.get("loesung_nr") is None: break
        if k == 0 and os.path.isfile(au): __import__("shutil").copyfile(au, au[:-5] + ".loesung0.json")      # 24.11.2026: Loesung 0 = Ausrichtung, mit der die Kette die dichte Wolke ausrichtet -> tools/fusion_vorab.py
        with LPS.Mitschrift(log): rc_g = LPS._rc_aus(LGP.main, [ok_, au, "--fotos", a.fotos])
        L = json.load(open(lj)) if os.path.isfile(lj) else {}; gf = L.get("gps_fit") or {}
        rc_p, txt_p = LP.tor_rc(json.load(open(au)).get("transformation"))
        tore = dict(gps=rc_g, lage_proben=rc_p); kaputt = rc_g in (1, 4)
        l = dict(loesung=k, geschrieben=E.get("loesung_nr"), n_unterscheidbar=E["n_unterscheidbar"], tore=tore, kaputt=kaputt, bestanden=(not kaputt) and LP.lage_frueh_bestanden(tore),
                 gps=dict(geprueft=L.get("geprueft"), drehung_grad=gf.get("drehung_grad"), massstab=gf.get("massstab"), festgelegt=gf.get("lage_festgelegt"), warnungen=L.get("warnungen")),
                 lage_proben=txt_p, massstab_sfm_je_m=(E.get("transformation") or {}).get("s"), sekunden=round(time.time() - t1, 1))
        R["laeufe"].append(l)
        print(f"   Loesung {k}/{E['n_unterscheidbar']}: GPS rc {rc_g}" + (f" ({gf['drehung_grad']:+.1f} Grad x{gf['massstab']:.3f}{'; ' + '; '.join(L.get('warnungen') or []) if L.get('warnungen') else ''})" if gf else f" ({L.get('ergebnis')})")
              + f", Lageproben rc {rc_p} - {'BESTANDEN' if l['bestanden'] else 'nicht bestanden'} ({l['sekunden']:.0f} s)", flush=True)
        if kaputt: return ende(4, f"GPS-Tor ohne Urteil (rc {rc_g}: {L.get('ergebnis')}) - die spaeten Tore entscheiden")
        if l["bestanden"] or E["rc"] == 5 or k + 1 >= E["n_unterscheidbar"]: break
    smj = os.path.join(a.pipe, "sfm", "seiten_modelle.json")
    if os.path.isfile(smj):
        try: R["teil_beleg"] = LPS.seiten_beleg(smj)
        except Exception as e: R["teil_beleg"] = dict(fehler=f"{type(e).__name__}: {e}")
    if not R["laeufe"]: return ende(4, "keine Loesung gerechnet - kein Urteil")
    ok = [l for l in R["laeufe"] if l["bestanden"]]
    if ok: R["loesung"] = ok[0]["loesung"]; return ende(0, f"Loesung {ok[0]['loesung']} besteht GPS-Tor + Lageproben auf dem duennen Netz (Grundriss/Wanddicke folgen nach der dichten Wolke)")
    kurz = "; ".join(f"Loesung {l['loesung']}: GPS rc {l['tore']['gps']}" + (f" ({'; '.join(l['gps']['warnungen'])})" if l["gps"].get("warnungen") else "") + f", Lageproben rc {l['tore']['lage_proben']}" for l in R["laeufe"])
    if eindeutig_durchgefallen(R["laeufe"]): return ende(3, f"LAGE FRUEH DURCHGEFALLEN vor der dichten Wolke - keine Loesung besteht GPS-Tor + Lageproben: {kurz}")
    return ende(0, f"keine Loesung eindeutig bestanden, aber auch nicht eindeutig verworfen ({kurz}) - spaete Tore entscheiden")


if __name__ == "__main__":
    sys.exit(main())

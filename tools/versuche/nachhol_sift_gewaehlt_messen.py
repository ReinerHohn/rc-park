#!/usr/bin/env python3
"""nachhol_sift_gewaehlt_messen.py - Messvergleich fuer den Schalter RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT (SIFT-Matching nur auf den LightGlue-gewaehlten Paaren + Marge
statt auf allen ~438.900 Kandidatenpaaren; Kette 1122q: 19,8 min). Der Schalter bleibt AUS, bis dieser Vergleich KEINEN Verlust zeigt. 23.11.2026.

ERST NACH DER KETTE STARTEN (GPU fuer SIFT/ALIKED, ~30-60 min, 2 x DB-Kopie ~3 GB): per tools/job_start.sh (Skill langer-job), z. B.
  JOB_GPU_MB=3000 JOB_RAM_MB=12000 tools/job_start.sh sift_gewaehlt_messen tools/py tools/versuche/nachhol_sift_gewaehlt_messen.py alles \
      --skript modelle/<objekt>/audit/seiten_luecken_holen.sh --ziel /media/oem/scan/rc-park_daten/<objekt>/seiten_nachholen --aus /media/oem/rcdaten/messung_sift_gewaehlt
Voraussetzung: <ziel>/bilder + <ziel>/vorbereitet.json eines Nachhol-Laufs (bleiben nach dem Lauf liegen; lg/ und db.db raeumt das Skript weg - darum rechnet 'a' neu).

Warum das Ergebnis B EXAKT dem Schalterweg entspricht, ohne SIFT zweimal zu rechnen: COLMAP matcht und verifiziert jedes importierte Paar fuer sich
(kein gefuehrtes Matching ueber Paargrenzen), also ist "nur Paare P matchen" == "alle matchen, dann alle Paare ausserhalb P loeschen".
Stufen (Ordner <aus>/A, <aus>/B, <aus>/K):
  a         Standardweg wie das Nachhol-Skript (Befehle aus --skript, <ziel> -> <aus>/A): merkmale (alle Paare), refnamen, paare (Zwischenspeicher
            RCPARK_LG_CACHE=<ziel>/zwischenspeicher_lg, falls vorhanden), einlesen, registrieren.
  b         Schalterweg: Kopie der A-Datenbank, SIFT-Matches/Verifikationen aller Paare mit einem neuen Bild AUSSERHALB der SIFT-Paarliste geloescht
            (Liste aus A/lg/grob_rang.json mit --marge/--min, Regel zusatzfotos_lightglue.sift_auswahl), dann einlesen + registrieren.
  kontrolle Rauschboden: Kopie der A-Datenbank OHNE Loeschen, einlesen + registrieren nochmal (zeigt, wie stark einlesen/registrieren allein streuen).
  vergleich A gegen B (und A gegen K): registrierte Bilder, verlorene/gewonnene Namen, Kamerazentren (m) und Blickwinkel (Grad) gemeinsamer Bilder,
            Paarzahl SIFT (Zeitabschaetzung). -> <aus>/vergleich.json
  alles     a, b, kontrolle, vergleich.
URTEIL 'kein Verlust' (Schalter darf Standard werden): verloren = 0 UND registriert_B >= registriert_A UND Zentrum-Abweichung A/B im 95-%-Wert nicht groesser als
1,5 x der Kontrolle A/K + 0,02 m UND Winkel-Maximum A/B <= max(0,5 Grad, 1,5 x Kontrolle). Sonst Marge erhoehen (--marge 4/6) und 'b' + 'vergleich' wiederholen.
"""
import sys, os, re, json, time, shutil, sqlite3, argparse, subprocess
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.dirname(HIER); sys.path.insert(0, TOOLS)


def befehle_aus_skript(skript, Z):
    """{stufe: befehl} aus dem erzeugten Nachhol-Skript (seiten_luecken_holen.sh); Kommentare am Zeilenende entfernt."""
    muster = {"merkmale": "zusatzfotos_registrieren.py merkmale", "refnamen": "zusatzfotos_lightglue.py refnamen", "paare": "zusatzfotos_lightglue.py paare",
              "einlesen": "zusatzfotos_lightglue.py einlesen", "registrieren": "zusatzfotos_registrieren.py registrieren"}
    out = {}
    for z in open(skript):
        z = z.strip()
        for st, m in muster.items():
            if m in z and st not in out: out[st] = re.sub(r"\s+#.*$", "", z).replace("RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT=1 ", "")
    fehlt = [s for s in muster if s not in out]
    if fehlt: raise SystemExit(f"FEHLER: im Skript {skript} fehlen Befehle fuer {fehlt}")
    return out


def umlenken(cmd, Z, ziel):
    """Pfad <Z> (als ganzes Pfadstueck) im Befehl durch <ziel> ersetzen."""
    return re.sub(re.escape(Z.rstrip("/")) + r"(?=/|\s|$)", ziel, cmd)


def laufen(cmd, log, env=None):
    t0 = time.time(); e = dict(os.environ, **(env or {})); e.pop("RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT", None)
    with open(log, "a") as f:
        f.write(f"\n### {cmd}\n"); f.flush(); rc = subprocess.run(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT, env=e).returncode
    if rc: raise SystemExit(f"FEHLER rc {rc}: {cmd[:160]} (Log {log})")
    return round(time.time() - t0, 1)


def grundordner(Z, D):
    os.makedirs(os.path.join(D, "lg"), exist_ok=True)
    if not os.path.exists(os.path.join(D, "bilder")): os.symlink(os.path.join(Z, "bilder"), os.path.join(D, "bilder"))
    shutil.copy(os.path.join(Z, "vorbereitet.json"), os.path.join(D, "vorbereitet.json"))


def stufe_a(a):
    B = befehle_aus_skript(a.skript, a.ziel); D = os.path.join(a.aus, "A"); grundordner(a.ziel, D); log = os.path.join(D, "lauf.log"); zeit = {}
    if os.path.exists(os.path.join(D, "db.db")): os.remove(os.path.join(D, "db.db"))
    cache = os.path.join(a.ziel, "zwischenspeicher_lg"); env = {"RCPARK_LG_CACHE": cache} if os.path.isdir(cache) else {}
    for st in ("merkmale", "refnamen", "paare", "einlesen", "registrieren"): zeit[st] = laufen(umlenken(B[st], a.ziel, D), log, env); print(f"A {st}: {zeit[st]} s", flush=True)
    json.dump(zeit, open(os.path.join(D, "zeiten.json"), "w"), indent=1)


def sc_aus_rang(rang):
    """grob_rang.json {neu: [[partner, n], ...]} -> sc {x: {y: n}} (nur die gespeicherten Spitzenplaetze; reicht fuer auswahl mit k <= Laenge der Rangliste)."""
    return {x: {y: int(n) for y, n in l} for x, l in rang.items()}


def sift_menge(D_a, marge, mind, k):
    import zusatzfotos_lightglue as ZL
    rang = json.load(open(os.path.join(D_a, "lg", "grob_rang.json"))); sc = sc_aus_rang(rang)
    lang = min(len(v) for v in rang.values()) if rang else 0; os.environ["RCPARK_NACHHOL_SIFT_MARGE"] = str(marge); os.environ["RCPARK_NACHHOL_SIFT_MIN"] = str(mind)
    import math
    if math.ceil(k * marge) > lang: print(f"WARNUNG: Rangliste (kuerzeste {lang}) kuerzer als k*marge = {math.ceil(k * marge)} - Auswahl fuer manche Bilder abgeschnitten", flush=True)
    return ZL.sift_auswahl(sc, sorted(rang), k)


def db_beschneiden(db, behalten, neu):
    """Matches + Verifikationen aller Paare mit mindestens einem Bild aus <neu> loeschen, die nicht in <behalten> {(a, b) sortiert} stehen. -> (geloescht, behalten)."""
    import zusatzfotos_lightglue as ZL
    con = sqlite3.connect(db); ids = {n: i for i, n in con.execute("select image_id,name from images")}; nid = {ids[n] for n in neu if n in ids}
    keep = {ZL.paar_id(ids[x], ids[y]) for x, y in behalten if x in ids and y in ids}; weg = []
    for (pid,) in con.execute("select pair_id from matches union select pair_id from two_view_geometries"):
        i2 = pid % 2147483647; i1 = (pid - i2) // 2147483647
        if (i1 in nid or i2 in nid) and pid not in keep: weg.append(pid)
    for i in range(0, len(weg), 900):
        t = weg[i:i + 900]; q = ",".join("?" * len(t)); con.execute(f"delete from matches where pair_id in ({q})", t); con.execute(f"delete from two_view_geometries where pair_id in ({q})", t)
    con.commit(); con.close(); return len(weg), len(keep)


def stufe_b(a, name="B", beschneiden=True):
    Bf = befehle_aus_skript(a.skript, a.ziel); Da = os.path.join(a.aus, "A"); D = os.path.join(a.aus, name); grundordner(a.ziel, D); log = os.path.join(D, "lauf.log")
    for f in ("merkmale.json",): shutil.copy(os.path.join(Da, f), os.path.join(D, f))
    for f in ("refnamen.json", "lg.npz", "paare.json", "grob_rang.json", "sift_paare.txt"):
        if os.path.exists(os.path.join(Da, "lg", f)): shutil.copy(os.path.join(Da, "lg", f), os.path.join(D, "lg", f))
    src = sqlite3.connect(f"file:{os.path.join(Da, 'db.db')}?mode=ro", uri=True); dst = sqlite3.connect(os.path.join(D, "db.db")); src.backup(dst); dst.close(); src.close()
    info = dict(variante=name)
    if beschneiden:
        V = json.load(open(os.path.join(Da, "vorbereitet.json"))); k = json.load(open(os.path.join(Da, "lg", "paare.json")))["k"]
        S = sift_menge(Da, a.marge, a.min, k); g, b = db_beschneiden(os.path.join(D, "db.db"), S, set(V["bilder"]))
        M = json.load(open(os.path.join(Da, "merkmale.json"))); info.update(marge=a.marge, min=a.min, sift_paare=len(S), kandidatenpaare=M.get("kandidatenpaare", M.get("paare")), geloescht=g)
        print(f"{name}: SIFT-Paarliste {len(S)} von {info['kandidatenpaare']} Kandidaten, {g} Paare aus der DB-Kopie entfernt", flush=True)
    for st in ("einlesen", "registrieren"): info["zeit_" + st] = laufen(umlenken(Bf[st], a.ziel, D), log); print(f"{name} {st}: {info['zeit_' + st]} s", flush=True)
    json.dump(info, open(os.path.join(D, "variante.json"), "w"), indent=1)


def posen(D):
    import pycolmap
    V = json.load(open(os.path.join(D, "vorbereitet.json"))); r = pycolmap.Reconstruction(os.path.join(D, "lg", "sparse_handy", "0")); out = {}
    for im in r.images.values():
        if im.name in V["bilder"] and im.has_pose: out[im.name] = (np.asarray(im.projection_center()), np.asarray(im.cam_from_world().rotation.matrix()) if callable(im.cam_from_world) else np.asarray(im.cam_from_world.rotation.matrix()))
    return out


def gegenueber(PA, PB):
    gem = sorted(set(PA) & set(PB)); dz = np.array([np.linalg.norm(PA[n][0] - PB[n][0]) for n in gem]) if gem else np.zeros(0)
    dw = np.array([np.degrees(np.arccos(np.clip((np.trace(PA[n][1] @ PB[n][1].T) - 1) / 2, -1, 1))) for n in gem]) if gem else np.zeros(0)
    q = lambda x, p: round(float(np.percentile(x, p)), 4) if len(x) else None
    return dict(registriert_1=len(PA), registriert_2=len(PB), gemeinsam=len(gem), verloren=sorted(set(PA) - set(PB)), gewonnen=sorted(set(PB) - set(PA)),
                zentrum_m=dict(median=q(dz, 50), p95=q(dz, 95), max=q(dz, 100)), winkel_grad=dict(median=q(dw, 50), p95=q(dw, 95), max=q(dw, 100)),
                ueber_0_25m=[n for n, d in zip(gem, dz) if d > 0.25])


def urteil(ab, ak):
    """Kriterium aus dem Kopftext. ak = Kontrolle (Rauschboden) oder None."""
    gz = (1.5 * ak["zentrum_m"]["p95"] + 0.02) if ak and ak["zentrum_m"]["p95"] is not None else 0.02
    gw = max(0.5, 1.5 * ak["winkel_grad"]["max"]) if ak and ak["winkel_grad"]["max"] is not None else 0.5
    gruende = []
    if ab["verloren"]: gruende.append(f"{len(ab['verloren'])} Bilder verloren")
    if ab["registriert_2"] < ab["registriert_1"]: gruende.append("weniger registriert")
    if ab["zentrum_m"]["p95"] is not None and ab["zentrum_m"]["p95"] > gz: gruende.append(f"Zentrum p95 {ab['zentrum_m']['p95']} m > {gz:.3f} m")
    if ab["winkel_grad"]["max"] is not None and ab["winkel_grad"]["max"] > gw: gruende.append(f"Winkel max {ab['winkel_grad']['max']} Grad > {gw:.2f}")
    return dict(kein_verlust=not gruende, gruende=gruende, grenze_zentrum_p95_m=round(gz, 4), grenze_winkel_max_grad=round(gw, 3))


def stufe_vergleich(a):
    A, B, K = (os.path.join(a.aus, x) for x in ("A", "B", "K")); PA = posen(A); PB = posen(B); ab = gegenueber(PA, PB)
    ak = gegenueber(PA, posen(K)) if os.path.exists(os.path.join(K, "lg", "sparse_handy", "0")) else None
    vb = json.load(open(os.path.join(B, "variante.json"))); za = json.load(open(os.path.join(A, "zeiten.json"))) if os.path.exists(os.path.join(A, "zeiten.json")) else {}
    ant = vb.get("sift_paare", 0) / max(1, vb.get("kandidatenpaare") or 1)
    erg = dict(a_gegen_b=ab, a_gegen_kontrolle=ak, urteil=urteil(ab, ak), variante=vb, zeit_merkmale_a_s=za.get("merkmale"),
               ANNAHME_matchzeit_b_s=(round(za["merkmale"] * ant, 0) if za.get("merkmale") else None), anteil_sift_paare=round(ant, 4))
    json.dump(erg, open(os.path.join(a.aus, "vergleich.json"), "w"), indent=1)
    print(json.dumps(dict(urteil=erg["urteil"], registriert_a=ab["registriert_1"], registriert_b=ab["registriert_2"], verloren=len(ab["verloren"]), gewonnen=len(ab["gewonnen"]),
                          zentrum_m=ab["zentrum_m"], winkel_grad=ab["winkel_grad"], kontrolle=(ak and dict(zentrum_m=ak["zentrum_m"], winkel_grad=ak["winkel_grad"], verloren=len(ak["verloren"]))),
                          anteil_sift_paare=erg["anteil_sift_paare"]), indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stufe", choices=["a", "b", "kontrolle", "vergleich", "alles"]); ap.add_argument("--skript"); ap.add_argument("--ziel"); ap.add_argument("--aus", required=True)
    ap.add_argument("--marge", type=float, default=3.0); ap.add_argument("--min", type=int, default=4); a = ap.parse_args(argv)
    if a.stufe != "vergleich" and not (a.skript and a.ziel): ap.error("--skript und --ziel noetig")
    if a.stufe in ("a", "alles"): stufe_a(a)
    if a.stufe in ("b", "alles"): stufe_b(a)
    if a.stufe in ("kontrolle", "alles"): stufe_b(a, "K", beschneiden=False)
    if a.stufe in ("vergleich", "alles"): stufe_vergleich(a)
    return 0


if __name__ == "__main__": sys.exit(main())

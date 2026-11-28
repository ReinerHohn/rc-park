#!/usr/bin/env python3
"""kameras_zusatz.py - registrierte Zusatzfotos (Handy; <ordner>/sparse_handy/0 aus tools/zusatzfotos_registrieren.py) als Messkameras
messprotokoll/K-<foto>.json schreiben, damit Foto-Tor (foto_diff/foto_tor_bezug), Wandbild (fassade_ortho -> fassade_fein) und Foto-F1 (teil_fotoform) sie nutzen.

Anlass 28.11.2026 (schwabentor-1122): die Kantenstufe nimmt seit tools/ausrichtung_zusatz.py 903 + 399 Kameras, aber fuer die Handyfotos vom 26.11. (327)
und 28.11. (72) gab es KEINE K-Datei (die 207 Handy-K-Dateien stammen alle aus dem Hauptnetz vom 23.11.) - die Folgestufen sahen nur die 903.
Warum nicht kameras_nachtragen.py: das schaetzt eine Umeyama-Abbildung aus Kamerastandorten (Kern + Inlier, Tor 0,5 m) - hier ist die Abbildung BEKANNT
(sparse_handy liegt im SfM-Rahmen der Ausrichtung, Rahmen-Tor 0,05 m / 0,5 Grad an den gemeinsamen Referenzbildern). Warum nicht kameras_aus_buendel.py
auf der erweiterten Ausrichtung: es setzt den Rahmenstempel (RAHMEN.json) aus der Datei - die Kopie mit Zusatzkameras ergaebe einen FREMDEN Rahmen und
alle 903 Kameras galten als veraltet.
Verwandt: tools/ausrichtung_zusatz.py (gleiche Zusatzordner + Rahmen-Tor, fuer die Kantenstufe), tools/kameras_aus_buendel.py (gleiche Umrechnung, herkunft 'abgeleitet'),
tools/kamera_rahmen.py (Rahmenstempel), tools/kameras_nachtragen.py (Umeyama, hier unpassend). Vorlaeufer: keiner - Handyfotos hatten keine K-Dateien.

Ablauf (nichts Objektspezifisches, Namen nur aus den Netzen):
  1. ausrichtung_zusatz.erweitern() auf der ORIGINAL-Ausrichtung (dasselbe Rahmen-Tor, Schwellen NICHT einstellbar - nicht lockern).
  2. Rahmen-Probe: Stempel (kamera_rahmen.stempel) der Ausrichtung mit T_ des gueltigen Rahmens (messprotokoll/RAHMEN.json, schreibt kameras_aus_buendel)
     muss dessen Kennung ergeben - sonst gilt der Rahmen der K-Dateien fuer eine ANDERE Ausrichtung: nichts schreiben, rc 4.
  3. Je neue Kamera: Netzguete (kamera_sfm_guete, >= --min_beob Beobachtungen), Plausibilitaet (kamera_plausibel.plausibel), Umrechnung wie
     kameras_aus_buendel (Bildpixel des VORBEREITETEN Bildes, t' = t - R T_). K-Datei: kamera mit herkunft 'abgeleitet' (kamera_rahmen: neuer Rahmen ->
     umgerechnet bzw. gesperrt), quelle 'zusatz:<ordner> ...', bild_datei = Pfad des vorbereiteten Bildes (das Bild liegt NICHT im Sammelordner:
     dessen Namensliste ist der Fotosatz-Hash der SfM-Stufe). Leser finden es ueber pfade.foto_aus_k().
  4. Eigene K-Dateien frueherer Laeufe (quelle 'zusatz:'), die dieser Lauf nicht schreibt, werden beiseitegelegt (.zusatz_weg; mit Picks nur kamera ->
     kamera_veraltet) - der Bestand ist danach immer Original + Zusatz DIESES Laufs. Fremde K-Dateien (Buendel, Hand, nachregistriert) bleiben unberuehrt.
  --weg: nur Schritt 4 fuer ALLE eigenen (Rueckfall auf Original, z. B. RCPARK_K_ZUSATZ=0 oder Fehler). --trocken: nichts schreiben/umbenennen.
Exit: 0 = mindestens eine K-Datei geschrieben, 3 = keine neue Kamera (kein Ordner/Rahmen abgelehnt/alle unbelegt), 4 = Rahmen passt nicht (nichts geschrieben,
eigene beiseite), 2 = Eingabe fehlt. Bericht audit/kameras_zusatz.json.
  /media/oem/scan/venv-colmap/bin/python -I tools/kameras_zusatz.py modelle/<obj>/objekt.json --ausrichtung AU.json --fotos FV --zusatz O1 [O2 ...] [--trocken]
Test: tools/test_kameras_zusatz.py (Schnelltest)."""
import os, sys, json, glob, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ausrichtung_zusatz as AZ
import kamera_rahmen as KR

MARKE = "zusatz:"


def eigen(k):
    return isinstance(k, dict) and str(k.get("quelle", "")).startswith(MARKE)


def k_eintrag(k, W, H, T_, st_id, ordner, n_beob, bp, rahmen_info):
    """Kamera der erweiterten Ausrichtung (Modellrahmen, Pixel des vorbereiteten Bildes bild_b x bild_h) -> K-Datei-'kamera' im Werkzeugrahmen (T_).
    -> (kamera oder None, grund). Gleiche Formel wie kameras_aus_buendel.py."""
    bw, bh = float(k.get("bild_b", W)), float(k.get("bild_h", H)); s = W / bw
    if abs(H / bh - s) > 0.01 * s: return None, f"Seitenverhaeltnis {W}x{H} vs Netz {bw:.0f}x{bh:.0f}"
    R = np.asarray(k["R"], float); t = np.asarray(k["t"], float) - R @ np.asarray(T_, float); C = -R.T @ t
    k1 = float((k.get("k") or [0.0])[0])
    return dict(rvec=KR._rvec(R).tolist(), t=t.tolist(), f_px=float(k["f_px_original"]) * s, cx=float(k["cx"]) * s, cy=float(k["cy"]) * s, k1=k1, bild=[int(W), int(H)],
                standort_xyz=[round(float(x), 3) for x in C], hoehe_ueber_gelaende=round(float(C[2]), 2), brennweite_quelle="zusatz", herkunft="abgeleitet",
                sfm_guete=dict(n_beob=int(n_beob)), rahmen_verschiebung=[round(float(x), 4) for x in T_], rahmen=st_id, bild_datei=os.path.abspath(bp),
                quelle=f"{MARKE}{ordner} (kameras_zusatz.py: sparse_handy im SfM-Rahmen der Ausrichtung, Rahmen-Tor {rahmen_info}); Bildpixel x {s:.4f}"), ""


def beiseite(mp, behalten, trocken):
    """Eigene K-Dateien (quelle 'zusatz:'), deren Foto nicht in 'behalten' steht -> .zusatz_weg bzw. kamera -> kamera_veraltet (mit Picks). -> Anzahl."""
    n = 0
    for kp in sorted(glob.glob(os.path.join(mp, "K-*.json"))):
        nr = os.path.basename(kp)[2:-5]
        if nr in behalten: continue
        try: d = json.load(open(kp))
        except Exception: continue
        if not eigen(d.get("kamera")): continue
        n += 1
        if trocken: continue
        if any(d.get(s_) for s_ in ("punkte", "linien")):
            d["kamera_veraltet"] = dict(d.pop("kamera"), sperre="kameras_zusatz.py: in diesem Lauf nicht bestaetigt"); __import__("json_sicher").schreiben(kp, d)
        else: os.replace(kp, kp + ".zusatz_weg")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("objekt"); ap.add_argument("--ausrichtung"); ap.add_argument("--fotos", help="Sammelordner (Namenskollision wie ausrichtung_zusatz)"); ap.add_argument("--zusatz", nargs="*", default=[])
    ap.add_argument("--min_beob", type=int, default=30, help="wie kameras_aus_buendel: weniger Netzbeobachtungen = Lage unbelegt"); ap.add_argument("--trocken", action="store_true")
    ap.add_argument("--weg", action="store_true", help="nur alle eigenen K-Dateien beiseitelegen (Rueckfall auf Original)"); a = ap.parse_args(argv)
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(objp)); mp = os.path.join(od, "messprotokoll")
    au_dir = os.path.join(root, obj.get("audit", os.path.join(os.path.relpath(od, root), "audit"))); bericht = dict(werkzeug="kameras_zusatz.py", trocken=a.trocken, ordner=[], neu=[], verworfen=[], behalten_fremd=[])
    def ende(rc, **k):
        bericht.update(k, rc=rc)
        if not a.trocken: os.makedirs(au_dir, exist_ok=True); json.dump(bericht, open(os.path.join(au_dir, "kameras_zusatz.json"), "w"), indent=1, ensure_ascii=False)
        return rc
    if a.weg:
        n = beiseite(mp, set(), a.trocken); print(f"Rueckfall auf Original: {n} eigene Zusatz-K-Dateien beiseitegelegt{' (trocken)' if a.trocken else ''}", flush=True); return ende(3, beiseite=n, modus="weg")
    if not a.ausrichtung or not a.fotos or not os.path.isfile(a.ausrichtung) or not os.path.isdir(a.fotos):
        print(f"FEHLER: --ausrichtung/--fotos fehlen ({a.ausrichtung}, {a.fotos})", flush=True); return ende(2, fehler="Eingabe fehlt", beiseite=beiseite(mp, set(), a.trocken))
    A = json.load(open(a.ausrichtung)); st = KR.aktuell(mp)
    if not st:
        print("FEHLER: messprotokoll/RAHMEN.json ohne gueltigen Rahmen (kameras_aus_buendel lief nicht) - keine Zusatz-K-Datei", flush=True)
        return ende(4, fehler="kein gueltiger Rahmen", beiseite=beiseite(mp, set(), a.trocken))
    st_neu = KR.stempel(A, st["T_"])
    if st_neu["id"] != st["id"]:
        g = f"Rahmen der K-Dateien {st['id']} ({st.get('ausrichtung')}) gehoert NICHT zur Ausrichtung {a.ausrichtung} (Stempel {st_neu['id']}) - Zusatzkameras laegen im falschen Rahmen"
        print("FEHLER: " + g, flush=True); return ende(4, fehler=g, beiseite=beiseite(mp, set(), a.trocken))
    fv_namen = sorted(f for f in os.listdir(a.fotos) if not f.startswith(".")); netze = []; guete = {}
    import kamera_sfm_guete as KG
    for o_ in a.zusatz:
        sp = os.path.join(o_, "sparse_handy", "0")
        if not os.path.isfile(os.path.join(sp, "images.bin")): print(f"WARNUNG: {sp} fehlt - Ordner uebersprungen", flush=True); bericht["ordner"].append(dict(ordner=o_, fehler="sparse_handy/0 fehlt")); continue
        netze.append((o_, AZ.sparse_lesen(sp))); guete[o_] = {os.path.splitext(n)[0]: v.get("n_beob", 0) for n, v in KG.guete(sp).items()}
    A2, neu, ber = AZ.erweitern(A, fv_namen, netze)                      # Standard-Tor von ausrichtung_zusatz (0,05 m / 0,5 Grad / 20 gemeinsame), bewusst nicht einstellbar
    bericht["ordner"] += ber["ordner"]
    for e in ber["ordner"]:
        print(f"{e['ordner']}: Rahmen {'OK' if e['rahmen_ok'] else 'ABGELEHNT'} (gemeinsam {e['gemeinsam']}, Zentrum {e['zentrum_median_m']} m, Winkel {e['winkel_median_grad']} Grad), Kandidaten {e['neu']}"
              + (f" - {e['grund']}" if e.get("grund") else ""), flush=True)
    import kamera_plausibel as KP
    from PIL import Image
    T_ = st["T_"]; geschrieben = set()
    for nr, bp in sorted(neu.items()):
        k = A2["kameras"][nr]; o_ = k["quelle"][len(MARKE):]; e_ = next(e for e in ber["ordner"] if e["ordner"] == o_)
        nb = guete.get(o_, {}).get(nr, 0)
        if nb < a.min_beob: bericht["verworfen"].append(dict(foto=nr, grund=f"nur {nb} Netzbeobachtungen (< {a.min_beob})")); continue
        W, H = Image.open(bp).size
        kam, g = k_eintrag(k, W, H, T_, st["id"], o_, nb, bp, f"{e_['zentrum_median_m']} m / {e_['winkel_median_grad']} Grad an {e_['gemeinsam']} Referenzbildern")
        if kam is None: bericht["verworfen"].append(dict(foto=nr, grund=g)); continue
        ok_p, g = KP.plausibel(kam["f_px"], (W, H), kam["standort_xyz"], k1=kam["k1"], bild_diag=float(np.hypot(W, H)))
        if not ok_p: bericht["verworfen"].append(dict(foto=nr, grund="UNPLAUSIBEL: " + g)); continue
        kp = os.path.join(mp, f"K-{nr}.json"); d = json.load(open(kp)) if os.path.exists(kp) else dict(foto=nr, seite="unbekannt", punkte={}, linien={})
        if isinstance(d.get("kamera"), dict) and not eigen(d["kamera"]): bericht["behalten_fremd"].append(nr); continue     # Hand/Buendel/nachregistriert nie ueberschreiben
        d["kamera"] = kam; geschrieben.add(nr)
        if eigen(d.get("kamera_veraltet")): d.pop("kamera_veraltet")             # eigene Sperre eines frueheren Laufs aufheben
        bericht["neu"].append(dict(foto=nr, standort=[round(float(v), 1) for v in kam["standort_xyz"]], f_px=round(kam["f_px"]), n_beob=nb))
        if not a.trocken: __import__("json_sicher").schreiben(kp, d)
    n_weg = beiseite(mp, geschrieben, a.trocken)
    print(f"{len(geschrieben)} Zusatz-K-Dateien {'(trocken) ' if a.trocken else ''}geschrieben (Rahmen {st['id']}), verworfen {len(bericht['verworfen'])}, fremde behalten {len(bericht['behalten_fremd'])}, "
          f"fruehere eigene beiseite {n_weg}", flush=True)
    for v in bericht["verworfen"][:8]: print("  verworfen", v["foto"], v["grund"], flush=True)
    return ende(0 if geschrieben else 3, rahmen=st["id"], beiseite=n_weg, geschrieben=len(geschrieben))


if __name__ == "__main__":
    sys.exit(main())

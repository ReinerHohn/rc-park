#!/usr/bin/env python3
"""kameras_aus_buendel.py - PIPELINE-BRUECKE (2026-11-04): Kameras des Buendelausgleichs (sfm_lod2_buendel.py, an LoD2/DGM1 verankert, ohne Handpicks)
als K-<foto>.json 'kamera' schreiben, damit die Vergleichswerkzeuge (foto_diff.py, fehlteile_finden.py, foto_mass.py --kamera, foto_pick_pruefen.py) auf
ALLEN registrierten Fotos laufen - nicht nur auf den wenigen handkalibrierten (Kaufhaus hatte 0 K-Kameras, Martinstor 7).

Umrechnung: SfM-Bildpixel -> Originalfoto (Faktor s = Breite_Original / Breite_SfM; f, cx, cy x s; k1 bleibt, normierte Koordinaten), Modellrahmen ->
Werkzeugrahmen (STL skaliert + zentriert wie textur_projektion.modell_laden: X_w = X_modell + T_, t' = t - R T_). rms_px = Median-Rueckprojektion
dieser Kamera im Buendelnetz (pycolmap), in Originalpixeln. Ankerzone = DGM-Boden bis Modelloberkante (LoD2/DGM1 tragen das ganze Gebaeude).
Vorhandene K-Kameras (handkalibriert, amtliche Picks) werden NICHT ueberschrieben (--ueberschreiben erzwingt); Picks/Linien bleiben immer erhalten.
  /media/oem/scan/venv-colmap/bin/python -I tools/kameras_aus_buendel.py modelle/<objekt>/objekt.json --ausrichtung <SFM-AUSRICHTUNG-buendel.json> [--ueberschreiben] [--trocken]
GRENZEN: k1 wird gespeichert, aber foto_diff/fehlteile rendern ohne Verzeichnung (|k1| ~0,06 -> Ecken ~1-2 % radial); Kameras gelten fuer den Rahmen T_
(im Protokoll) - aendert sich die STL-Unterkante, neu schreiben.
"""
import sys, os, json, glob, struct, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kamera_plausibel as KP


def stl_punkte(p):
    with open(p, "rb") as f: d = f.read()
    n = struct.unpack("<I", d[80:84])[0] if len(d) >= 84 else 0
    if 84 + 50 * n == len(d):
        a = np.frombuffer(d, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("x", "<u2")]), count=n, offset=84); return a["v"].reshape(-1, 3).astype(np.float64)
    return np.array([[float(x) for x in l.split()[1:4]] for l in d.decode(errors="ignore").splitlines() if l.strip().startswith("vertex")])


def rodrigues(R):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_matrix(R).as_rotvec()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ausrichtung", required=True); ap.add_argument("--stl"); ap.add_argument("--sparse", default="", help="COLMAP-Netz (images.bin) fuer die Guete je Kamera; Standard: 'sparse' der Ausrichtung"); ap.add_argument("--min_beob", type=int, default=30, help="Kameras mit weniger Netzpunkten werden nicht geschrieben")
    ap.add_argument("--fotos", default="", help="Fotoordner statt objekt.json fotos_dir (Gesamtkette: Sammelordner mit Quellpraefix eigen__)"); ap.add_argument("--ueberschreiben", action="store_true"); ap.add_argument("--trocken", action="store_true"); a = ap.parse_args()
    from PIL import Image
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    ap_ = a.ausrichtung if os.path.isabs(a.ausrichtung) else (os.path.join(od, a.ausrichtung) if os.path.exists(os.path.join(od, a.ausrichtung)) else os.path.join(root, a.ausrichtung))
    A = json.load(open(ap_))
    V = stl_punkte(a.stl or os.path.join(root, obj["stl"])) * obj.get("stl_massstab", 87) / 1000.0
    lo, hi = V.min(0), V.max(0); c = (lo + hi) / 2 if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3); T_ = np.array([-c[0], -c[1], -lo[2]])
    zone = [-0.5, float(hi[2] - lo[2]) + 0.5]
    # Guete je Kamera im Netz (Zahl der Netzpunkte, Rueckprojektion) - ohne pycolmap (16.11.2026: der alte pycolmap-Block lief in der Kette nie, 'sparse' war dort None;
    # 21 Kameras OHNE einen einzigen Netzpunkt wurden als Messkamera geschrieben und 22 schlechte in Fassadenbildern benutzt)
    rms = {}; G = {}; sp_ = a.sparse or A.get("sparse")
    if sp_ and os.path.exists(os.path.join(sp_, "images.bin")):
        import kamera_sfm_guete as KG; G = {os.path.splitext(n_)[0]: v_ for n_, v_ in KG.guete(sp_).items()}; rms = {n_: v_["rms_px"] for n_, v_ in G.items() if v_.get("rms_px") is not None}
    else: print("WARNUNG: kein Netz (--sparse) - Kameraguete NICHT geprueft, Kameras ohne Netzpunkte koennen dabei sein")
    def beiseite(kp_):                                   # alte Buendel-Kamera derselben Aufnahme nicht liegen lassen (umbenennen, nichts loeschen)
        if os.path.exists(kp_) and not a.trocken and json.load(open(kp_)).get("kamera", {}).get("brennweite_quelle") == "buendel": os.replace(kp_, kp_ + ".unplausibel")
    neu = gesch = 0; ber = []; behandelt = set()
    for nr, k in sorted(A["kameras"].items()):
        fp = sorted(glob.glob(os.path.join(a.fotos or os.path.join(root, obj["fotos_dir"]), glob.escape(nr) + "_*")) or glob.glob(os.path.join(a.fotos or os.path.join(root, obj["fotos_dir"]), glob.escape(nr) + ".*")))
        if not fp: ber.append((nr, "Foto fehlt")); continue
        behandelt.add(nr)
        W, H = Image.open(fp[0]).size; bw, bh = float(k.get("bild_b", W)), float(k.get("bild_h", H)); s = W / bw
        if abs(H / bh - s) > 0.01 * s: ber.append((nr, f"Seitenverhaeltnis {W}x{H} vs SfM {bw:.0f}x{bh:.0f}")); continue
        R = np.array(k["R"], float); t = np.array(k["t"], float) - R @ T_; Cw = -R.T @ t
        kp = os.path.join(od, "messprotokoll", f"K-{nr}.json"); K = json.load(open(kp)) if os.path.exists(kp) else dict(foto=nr, seite=obj.get("fotos", {}).get(nr, {}).get("seite", "unbekannt"), punkte={}, linien={})
        if K.get("kamera") and K["kamera"].get("brennweite_quelle") != "buendel" and not a.ueberschreiben: gesch += 1; ber.append((nr, "handkalibriert - nicht ueberschrieben")); continue
        ok_p, grund_p = KP.plausibel(float(k["f_px_original"]) * s, (W, H), Cw, k1=float((k.get("k") or [0.0])[0]), bild_diag=float(np.hypot(W, H)))
        if not ok_p: ber.append((nr, "UNPLAUSIBEL, nicht geschrieben: " + grund_p)); beiseite(kp); continue
        if G and G.get(nr, {}).get("n_beob", 0) < a.min_beob: ber.append((nr, f"nur {G.get(nr, {}).get('n_beob', 0)} Netzpunkte (< {a.min_beob}) - Lage unbelegt, nicht geschrieben")); beiseite(kp); continue      # 16.11.2026: 9 solche Kameras lagen tagelang unbemerkt im Bestand
        K["kamera"] = dict(rvec=rodrigues(R).tolist(), t=t.tolist(), f_px=float(k["f_px_original"]) * s, cx=float(k["cx"]) * s, cy=float(k["cy"]) * s, k1=float((k.get("k") or [0.0])[0]),
                           bild=[W, H], standort_xyz=[round(float(x), 3) for x in Cw], hoehe_ueber_gelaende=round(float(Cw[2]), 2), rms_px=round(rms.get(nr, float("nan")) * s, 2) if nr in rms else None,
                           brennweite_quelle="buendel", sfm_guete=(dict(klasse=G[nr]["klasse"], n_beob=G[nr]["n_beob"]) if nr in G else None), ankerzone_z=zone, rahmen_verschiebung=T_.round(4).tolist(),
                           quelle=f"kameras_aus_buendel.py aus {os.path.relpath(ap_, root)} (sfm_lod2_buendel: LoD2/DGM1-Flaechen im Ausgleich, ohne Handpicks); SfM-Pixel x {s:.4f}")
        neu += 1; ber.append((nr, f"f {K['kamera']['f_px']:.0f} px, rms {K['kamera']['rms_px']} px"))
        if not a.trocken: os.makedirs(os.path.dirname(kp), exist_ok=True); __import__("json_sicher").schreiben(kp, K)
    # 17.11.2026 VERALTETE KAMERAS: K-Dateien, die dieses Werkzeug frueher aus DERSELBEN Ausrichtungsdatei schrieb, deren Foto jetzt aber nicht mehr in der Ausrichtung steht (neue SfM mit weniger Bildern)
    # oder dessen Foto fehlt, blieben als Messkamera liegen - im ALTEN Rahmen. fassade_ortho/foto_diff nehmen jede K-Datei. Sie werden beiseitegelegt (umbenannt, nichts geloescht).
    marke = f"kameras_aus_buendel.py aus {os.path.relpath(ap_, root)} "; alt = 0
    for kp_ in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr_ = os.path.basename(kp_)[2:-5]
        if nr_ in behandelt or os.path.getmtime(kp_) >= os.path.getmtime(ap_): continue
        try: kk_ = json.load(open(kp_)).get("kamera") or {}
        except Exception: continue
        if kk_.get("brennweite_quelle") == "buendel" and str(kk_.get("quelle", "")).startswith(marke):
            alt += 1; ber.append((nr_, "VERALTET (nicht mehr in der Ausrichtung bzw. Foto fehlt; Datei aelter als die Ausrichtung) - beiseitegelegt als .veraltet"))
            if not a.trocken: os.replace(kp_, kp_ + ".veraltet")
    for nr, b in ber: print(f"  K-{nr}: {b}")
    print(f"{neu} K-Kameras aus dem Buendel {'(trocken) ' if a.trocken else ''}geschrieben, {gesch} handkalibrierte behalten" + (f", {alt} veraltete beiseitegelegt" if alt else "") + f"; Rahmen T_ {T_.round(3).tolist()}, Ankerzone {zone}")
    fehlt = sum(1 for _, b in ber if b == "Foto fehlt")
    if fehlt > 0.5 * max(len(A["kameras"]), 1): print(f"WARNUNG: zu {fehlt} von {len(A['kameras'])} Kameras der Ausrichtung fehlt das Foto - falscher Fotoordner (--fotos / fotos_dir)?")
    if neu + gesch == 0:                                               # 17.11.2026: rc 0 ohne eine einzige Kamera (leere Ausrichtung, falscher Fotoordner) - die Kette rechnete mit den K-Dateien eines frueheren Laufs weiter
        print(f"FEHLER: KEINE Kamera geschrieben oder behalten ({len(A['kameras'])} in der Ausrichtung, {fehlt} ohne Foto) - Fotoordner und Ausrichtung pruefen"); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

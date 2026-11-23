#!/usr/bin/env python3
"""kameras_nachtragen.py <objekt.json> <sparse-neu> [--bilder ORDNER] [--ueberschreiben] - nachregistrierte Fotos als Messkameras K-<foto>.json in den MODELLRAHMEN bringen.

Teil der Stufe `seiten` (16.11.2026): tools/seiten_luecken.py laedt/registriert Fotos fuer ungesehene Waende (zusatzfotos_registrieren.py registrieren --je-bild).
Deren Posen liegen im SfM-Rahmen. Bruecke ohne eigene Ausrichtungsdatei: die Rekonstruktion <sparse-neu> enthaelt auch die alten Referenzbilder, fuer die es schon
K-Dateien im Modellrahmen gibt -> Aehnlichkeitsabbildung (Massstab, Drehung, Verschiebung; Umeyama) aus den Kamerastandorten der gemeinsamen Bilder,
angewandt auf die neuen Kameras. Pixelmassstab: SfM-Bild (verkleinert) -> Originalfoto (f, cx, cy x Breite_orig / Breite_sfm).
Neue Fotos, die nicht im fotos_dir liegen (Downloads), werden dorthin verlinkt (Name wie im SfM), damit alle Werkzeuge sie finden.
Ausgabe: messprotokoll/K-<foto>.json mit kamera {rvec, t, f_px, cx, cy, k1, quelle, inlier}, Bericht audit/kameras_nachtragen.json (Restfehler der Abbildung,
je vorhandener K-Datei eines neuen Fotos der Standortunterschied = Gegenprobe). Vorhandene Kameras bleiben (ausser --ueberschreiben).
ACHTUNG 'gegenprobe' (23.11.2026, Kette 1122q: 327 neu, gegenprobe 0): sie vergleicht NUR Fotos, die schon eine K-Datei hatten - 0 heisst "keine Doppelbestimmung
widerspricht", NICHT "die neuen Kameras sind geprueft". Die neuen Posen prueft erst tools/kameras_nachtragen_tor.py (plausibel + am Modell nachgezogen, sonst gesperrt).
  /media/oem/scan/venv-colmap/bin/python -I tools/kameras_nachtragen.py modelle/<objekt>/objekt.json <ziel>/lg/sparse_handy/0 --bilder <ziel>/roh
"""
import sys, os, json, glob, argparse, numpy as np, cv2


def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); a, b = A - ma, B - mb; U, S, Vt = np.linalg.svd(b.T @ a / len(A)); d = np.sign(np.linalg.det(U @ Vt)); D = np.diag([1, 1, d]); R = U @ D @ Vt; s = (S * np.diag(D)).sum() / (a ** 2).sum(1).mean()
    return s, R, mb - s * R @ ma


def main():
    import pycolmap
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("sparse"); ap.add_argument("--bilder", help="Ordner mit den Originalen der neuen Fotos (z. B. <ziel>/roh)"); ap.add_argument("--ueberschreiben", action="store_true"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); mp = os.path.join(od, "messprotokoll"); rec = pycolmap.Reconstruction(a.sparse)
    def kdatei(n): return os.path.join(mp, "K-" + os.path.splitext(n)[0] + ".json")
    def kam(n):
        if not os.path.exists(kdatei(n)): return None
        k = json.load(open(kdatei(n))).get("kamera"); return k if isinstance(k, dict) and "rvec" in k else None
    alt_s, alt_m, neu = [], [], []
    for im in rec.images.values():
        if not im.has_pose: continue
        cw = im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world; R = np.array(cw.rotation.matrix()); t = np.array(cw.translation); C = -R.T @ t; k = kam(im.name)
        if k is not None: Rk = cv2.Rodrigues(np.array(k["rvec"]))[0]; alt_s.append(C); alt_m.append(-Rk.T @ np.array(k["t"]))
        neu.append((im, R, C, k))
    alt_s, alt_m = np.array(alt_s), np.array(alt_m)
    if len(alt_s) < 10: print("zu wenige gemeinsame Bilder mit K-Datei"); return 2
    gut = np.ones(len(alt_s), bool)
    for _ in range(3):                                                    # Ausreisser (falsch registrierte Altkameras) verwerfen
        s, Ra, ta = umeyama(alt_s[gut], alt_m[gut]); rest = np.linalg.norm((s * (Ra @ alt_s.T).T + ta) - alt_m, axis=1); gut = rest < max(3 * np.median(rest), 0.3)
    print(f"Abbildung SfM -> Modell aus {gut.sum()} von {len(gut)} gemeinsamen Kameras: Massstab {s:.4f}, Restfehler Median {np.median(rest[gut]):.2f} m, p90 {np.percentile(rest[gut], 90):.2f} m")
    bericht = dict(gemeinsam=int(gut.sum()), massstab=float(s), rest_median_m=float(np.median(rest[gut])), neu=[], gegenprobe=[])
    for im, R, C, k in neu:
        Cm = s * Ra @ C + ta; Rm = R @ Ra.T; stem = os.path.splitext(im.name)[0]
        if k is not None and not a.ueberschreiben:                         # vorhandene Kamera bleibt IMMER (16.11.2026: der Gesamtlauf ueberschrieb die am Modell nachgezogene Kamera von ov_0005 mit der schlechteren SfM-Pose)
            Rk = cv2.Rodrigues(np.array(k["rvec"]))[0]; dC = float(np.linalg.norm(Cm - (-Rk.T @ np.array(k["t"]))))
            if dC > 1.0 and not any(np.allclose(C, q) for q in alt_s[gut]): bericht["gegenprobe"].append(dict(foto=stem, standort_unterschied_m=round(dC, 2)))
            continue
        cam = rec.cameras[im.camera_id]; orig = (glob.glob(os.path.join(fd, stem + ".*")) or (glob.glob(os.path.join(a.bilder, stem + ".*")) if a.bilder else []))
        if not orig: continue
        if not orig[0].startswith(fd): ziel = os.path.join(fd, os.path.basename(orig[0])); os.path.lexists(ziel) or os.symlink(os.path.realpath(orig[0]), ziel); orig = [ziel]
        b = cv2.imread(orig[0])
        if b is None: continue
        f = b.shape[1] / cam.width; p = list(cam.params); K = dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=(-Rm @ Cm).tolist(), f_px=p[0] * f, cx=p[1] * f, cy=p[2] * f, k1=float(p[3]) if len(p) > 3 else 0.0,
                                                                 standort=Cm.tolist(), quelle=f"nachregistriert ({os.path.basename(os.path.dirname(os.path.abspath(a.sparse)))}), Abbildung aus {int(gut.sum())} gemeinsamen Kameras, Rest {np.median(rest[gut]):.2f} m", punkte3d=int(im.num_points3D))
        d = json.load(open(kdatei(im.name))) if os.path.exists(kdatei(im.name)) else dict(foto=stem, seite="unbekannt", punkte={}, linien={})
        if isinstance(d.get("kamera"), dict) and "rvec" in d["kamera"]: d["kamera_vorher"] = d["kamera"]
        d["kamera"] = K; json.dump(d, open(kdatei(im.name), "w"), indent=1); bericht["neu"].append(dict(foto=stem, standort=[round(float(v), 1) for v in Cm], f_px=round(K["f_px"]), punkte3d=int(im.num_points3D)))
    au = os.path.join(root, obj.get("audit", os.path.join(od, "audit"))); json.dump(bericht, open(os.path.join(au, "kameras_nachtragen.json"), "w"), indent=1)
    print(f"{len(bericht['neu'])} neue Messkameras geschrieben; Gegenprobe (vorhandene Kamera weicht > 1 m ab): {bericht['gegenprobe'][:6]}")
    for e in bericht["neu"]: print("  ", e["foto"][-28:], e["standort"], "f", e["f_px"], "Punkte", e["punkte3d"])


if __name__ == "__main__":
    sys.exit(main())

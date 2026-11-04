#!/usr/bin/env python3
"""beweis_anker.py - SICHTBEWEIS je Kamera (generisch, 2026-11-04): amtliche Anker (anker3d.json: LoD2-Ecken, First, Traufe) mit der Kamera aus
K-<foto>.json ins Foto projizieren. Liegen die Kreise auf den echten Gebaeudeecken, passt die Kamera zum Gebaeude; ein kleiner Netzfehler beweist das NICHT
(Kaufhaus altes Netz: 1 px Netzfehler, Traufecke ueber dem Dach). Ergebnis ist ein Bild zum Ansehen (Regel 3) + Kontaktabzug aller Fotos.
  /media/oem/scan/venv-seg/bin/python -I tools/beweis_anker.py modelle/<objekt>/objekt.json [--fotos 018,043] [--max 24]
Ausgabe: audit/beweis_anker/<foto>.jpg, audit/beweis_anker_uebersicht.jpg, audit/beweis_anker.json (je Foto: Anker im Bild, ausserhalb, hinter der Kamera).
"""
import sys, os, json, glob, argparse, numpy as np, cv2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotos"); ap.add_argument("--max", type=int, default=24); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    an = json.load(open(os.path.join(od, "anker3d.json")))["anker"]; aus = os.path.join(od, "audit", "beweis_anker"); os.makedirs(aus, exist_ok=True)
    wahl = set(a.fotos.split(",")) if a.fotos else None; erg = {}; kacheln = []
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr = os.path.basename(kp)[2:-5]; K = json.load(open(kp)).get("kamera")
        if not K or (wahl and nr not in wahl): continue
        fp = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))
        if not fp: continue
        im = cv2.imread(fp[0]); H, W = im.shape[:2]; R, _ = cv2.Rodrigues(np.array(K["rvec"], float)); t = np.array(K["t"], float)
        T_ = np.array(K.get("rahmen_verschiebung", [0, 0, 0]), float); f = K["f_px"]; cx = K.get("cx", W / 2); cy = K.get("cy", H / 2); k1 = K.get("k1", 0.0)
        n_in = n_aus = n_hinter = 0
        for name, A in an.items():
            x = R @ (np.array(A["xyz"], float) + T_) + t
            if x[2] <= 0: n_hinter += 1; continue
            xn = x[:2] / x[2]; d = 1 + k1 * float(xn @ xn); u, v = f * d * xn + [cx, cy]
            if not (0 <= u < W and 0 <= v < H): n_aus += 1; continue
            n_in += 1; r = max(6, W // 120); cv2.circle(im, (int(u), int(v)), r, (0, 255, 255), max(2, W // 500))
            cv2.putText(im, name.replace("ecke_", ""), (int(u) + r, int(v) - r), 0, W / 1600, (0, 255, 255), max(1, W // 700))
        cv2.putText(im, f"{nr}: {n_in} Anker im Bild ({K.get('brennweite_quelle', '?')})", (20, int(H / 25)), 0, W / 1400, (255, 255, 255), max(2, W // 600))
        cv2.imwrite(os.path.join(aus, nr + ".jpg"), cv2.resize(im, (1400, int(1400 * H / W))), [cv2.IMWRITE_JPEG_QUALITY, 85])
        erg[nr] = dict(im_bild=n_in, ausserhalb=n_aus, hinter_kamera=n_hinter)
        if n_in >= 2 and len(kacheln) < a.max: kacheln.append(cv2.resize(im, (600, int(600 * H / W))))
    if kacheln:
        h = max(k.shape[0] for k in kacheln); kacheln = [np.pad(k, ((0, h - k.shape[0]), (0, 4), (0, 0))) for k in kacheln]
        while len(kacheln) % 4: kacheln.append(np.zeros_like(kacheln[0]))
        cv2.imwrite(os.path.join(od, "audit", "beweis_anker_uebersicht.jpg"), np.vstack([np.hstack(kacheln[i:i + 4]) for i in range(0, len(kacheln), 4)]), [cv2.IMWRITE_JPEG_QUALITY, 80])
    json.dump(dict(kameras=erg, hinweis="Sichtbeweis: Kreise muessen auf den echten Ecken liegen (ansehen); Zahlenbeweis = kamera_lod2_nachfuehren (Tor)"), open(os.path.join(od, "audit", "beweis_anker.json"), "w"), indent=1)
    print(f"beweis_anker: {len(erg)} Kameras, {sum(1 for e in erg.values() if e['im_bild'] >= 2)} mit >= 2 Ankern im Bild -> audit/beweis_anker_uebersicht.jpg")
    sys.exit(0 if erg else 3)


if __name__ == "__main__":
    main()

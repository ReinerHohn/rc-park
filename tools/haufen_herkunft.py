#!/usr/bin/env python3
"""haufen_herkunft.py - welche BILDER haben einen Strassenhaufen des Grundriss-Tors erzeugt? (20.11.2026, Schwabentor: Flugpunkt-Faecher auf dem Platz)

Nimmt je Haufen aus audit/wolke_grundriss.json (strasse.haufen) die Strassenpunkte des Tors (audit/wolke_grundriss_strasse.npy, im Kasten des Haufens),
rechnet sie ins SfM-System zurueck und prueft je Bild der dichten Wolke, ob seine TIEFENKARTE an der Stelle genau diese Tiefe hat (Abweichung <= --tol relativ).
Ein Punkt gilt als von dem Bild "getragen". Ausgabe: je Bildquelle (Clip / Namensteil vor '__') Zahl getragener Punkte und Anteil, die staerksten Einzelbilder,
audit/haufen_herkunft.json. Kein Urteil - Hinweis, welche Bilder man aus der Fusion nehmen und neu pruefen sollte.
  /media/oem/scan/venv-colmap/bin/python -I tools/haufen_herkunft.py modelle/<obj>/objekt.json <SFM-AUSRICHTUNG.json> --wolke punkte_modell.npy --dicht <pipe>/dicht [--max 1]
"""
import sys, os, json, argparse, collections, numpy as np, cv2, pycolmap


def tiefenkarte(p):
    with open(p, "rb") as f:
        kopf = b""
        while kopf.count(b"&") < 3: kopf += f.read(1)
        w, h, c = (int(x) for x in kopf.split(b"&")[:3]); d = np.fromfile(f, np.float32)
    return d.reshape((w, h, c), order="F").transpose(1, 0, 2)[:, :, 0]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ausrichtung"); ap.add_argument("--wolke", required=True); ap.add_argument("--dicht", required=True)
    ap.add_argument("--max", type=int, default=1); ap.add_argument("--tol", type=float, default=0.01); ap.add_argument("--proben", type=int, default=60000); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); H = json.load(open(os.path.join(od, "audit", "wolke_grundriss.json")))["strasse"]["haufen"][:a.max]
    T = json.load(open(a.ausrichtung))["transformation"]; s = float(T["s"]); R = cv2.Rodrigues(np.array(T["rvec"], float))[0]; t = np.array(T["t"], float)
    sp = os.path.join(od, "audit", "wolke_grundriss_strasse.npy")            # die Strassenpunkte des Tors (nicht der Kasten aus der ganzen Wolke: der enthaelt echte Waende)
    if not os.path.exists(sp): sys.exit(f"{sp} fehlt - erst tools/wolke_grundriss_pruefen.py laufen lassen (legt die Strassenpunkte ab)")
    P = np.load(sp); rec = pycolmap.Reconstruction(os.path.join(a.dicht, "sparse"))
    quelle = lambda n: n.split("__vf_")[0] if "__vf_" in n else (n.split("__")[0] if "__" in n else "eigen")
    aus = []
    for nr, h in enumerate(H):
        m = np.array(h["mitte"], float); r = 0.5 * np.array(h["ausdehnung_m"], float) + 1.0
        X = np.asarray(P[(np.abs(P[:, 0] - m[0]) < r[0]) & (np.abs(P[:, 1] - m[1]) < r[1])], float)
        if len(X) > a.proben: X = X[np.random.default_rng(0).choice(len(X), a.proben, replace=False)]
        Xs = s * X @ R.T + t                                                 # X_sfm = s * R @ X_modell + t (Feld 'beschreibung' der Ausrichtung)
        getragen = np.zeros(len(X), int); je_bild = {}
        for im in rec.images.values():
            dp = os.path.join(a.dicht, "stereo", "depth_maps", im.name + ".photometric.bin")
            if not os.path.exists(dp): continue
            D = tiefenkarte(dp); cam = rec.cameras[im.camera_id]; cw = im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world
            Xc = Xs @ cw.rotation.matrix().T + cw.translation; z = Xc[:, 2]; fx, fy, cx, cy = cam.params[:4]
            fu = D.shape[1] / cam.width; u = (fx * Xc[:, 0] / np.maximum(z, 1e-9) + cx) * fu; v = (fy * Xc[:, 1] / np.maximum(z, 1e-9) + cy) * fu
            ok = (z > 0) & (u >= 0) & (u < D.shape[1] - 1) & (v >= 0) & (v < D.shape[0] - 1); i = np.where(ok)[0]
            d = D[v[i].astype(int), u[i].astype(int)]; tr = i[(d > 0) & (np.abs(d - z[i]) <= a.tol * z[i])]
            if len(tr): je_bild[im.name] = int(len(tr)); getragen[tr] += 1
        jq = collections.Counter(); nq = collections.Counter()
        for n, c in je_bild.items(): jq[quelle(n)] += c; nq[quelle(n)] += 1
        ges = sum(jq.values()) or 1
        print(f"Haufen {nr} bei {h['mitte']}: {len(X)} Proben (Tor-Zaehlung {h['punkte']}), von mindestens einer Tiefenkarte getragen {int((getragen > 0).sum())} ({100 * (getragen > 0).mean():.0f} %), nur von EINER {int((getragen == 1).sum())}")
        for q, c in jq.most_common(8): print(f"   {q[:44]:44s} {c:7d} Treffer ({100 * c / ges:4.1f} %) aus {nq[q]:3d} Bildern")
        for n, c in sorted(je_bild.items(), key=lambda x: -x[1])[:8]: print(f"      {n[:60]:60s} {c:6d}")
        aus.append(dict(haufen=nr, mitte=h["mitte"], proben=len(X), getragen=int((getragen > 0).sum()), je_quelle=dict(jq.most_common()), je_bild=dict(sorted(je_bild.items(), key=lambda x: -x[1])[:60])))
    json.dump(dict(werkzeug="haufen_herkunft.py", tol=a.tol, haufen=aus), open(os.path.join(od, "audit", "haufen_herkunft.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()

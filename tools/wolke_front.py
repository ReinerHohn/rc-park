#!/usr/bin/env python3
"""wolke_front.py - FRONTANSICHT der gefaerbten Wolke (Orthokamera, z-Puffer, GPU) + Abdeckung je Pixel (Zahl der Fotos je Punkt aus .vis).
Wolke -> Rahmen der K-Dateien per Umeyama aus Kamerazentren (Rest muss < 5 cm sein; SFM-AUSRICHTUNG-*.json NICHT verwenden, 7.11. BS10).
Tiefe kommt aus der 3D-Lage der Punkte (KEINE Ebenenannahme wie im Foto-Median BS9): Bogenlaibung/Rueckwand verschmieren nicht.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_front.py modelle/<obj>/objekt.json --dicht <sfm/dicht_*> --box x0,y0,z0,x1,y1,z1 --normale nx,ny --aus ordner [--zelle 0.01]
Ausgabe: front_farbe.png, front_tiefe.png (w in m ab Ebene), front_abdeckung.png (Fotos je Punkt, 0..8+), front.json (Kennzahlen, Rahmenrest, Luecken je Hoehenband)."""
import os, sys, json, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freiraum_pruefen as FP

def rahmen_umeyama(dicht, od):
    Kd = json.load(open(os.path.join(dicht, "kameras_unverzerrt.json"))); S = []; M = []
    for i, c in Kd.items():
        p = os.path.join(od, "messprotokoll", f"K-{i}.json")
        if not os.path.exists(p): continue
        k = json.load(open(p)).get("kamera", {})
        if "standort_xyz" not in k: continue
        S.append(-np.array(c["R"]).T @ np.array(c["t"])); M.append(k["standort_xyz"])
    S = np.array(S); M = np.array(M); ms, mm = S.mean(0), M.mean(0); A = S - ms; B = M - mm
    U, D, Vt = np.linalg.svd(B.T @ A / len(S)); Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt)); Rm = U @ Sg @ Vt
    s = np.trace(np.diag(D) @ Sg) / A.var(0).sum(); t0 = mm - s * Rm @ ms; rest = np.linalg.norm(s * (Rm @ S.T).T + t0 - M, axis=1)
    assert np.median(rest) < 0.05, "Rahmen passt nicht"
    return s, Rm, t0, M, float(np.median(rest))

def ply_farbe(pfad):
    with open(pfad, "rb") as f:
        hd = []
        while True:
            l = f.readline().decode("ascii").strip(); hd.append(l)
            if l == "end_header": break
        n = int([h for h in hd if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in hd if h.startswith("property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); arr = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    return np.c_[arr["x"], arr["y"], arr["z"]].astype(np.float64), np.c_[arr["red"], arr["green"], arr["blue"]]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dicht", required=True); ap.add_argument("--box", required=True); ap.add_argument("--normale", required=True)
    ap.add_argument("--aus", required=True); ap.add_argument("--zelle", type=float, default=0.01); ap.add_argument("--tiefe", type=float, default=6.0, help="Bereich hinter/vor der Ebene (m)")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); os.makedirs(a.aus, exist_ok=True)
    import torch; dev = "cuda" if torch.cuda.is_available() else "cpu"
    s, Rm, t0, CM, rest = rahmen_umeyama(a.dicht, od); X, C = ply_farbe(os.path.join(a.dicht, "fused.ply")); X = s * (Rm @ X.T).T + t0
    x0, y0, z0, x1, y1, z1 = [float(v) for v in a.box.split(",")]; nx, ny = [float(v) for v in a.normale.split(",")]; n = np.array([nx, ny, 0.0]); n /= np.linalg.norm(n); d = np.array([-n[1], n[0], 0.0])
    mitte = np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0.0]); seite = np.sign(np.mean((CM - mitte) @ n))              # Kameraseite: dort steht der Betrachter
    if seite < 0: n = -n; d = -d
    P = X - mitte; w = P @ n; u = P @ d; v = X[:, 2]                                                           # w>0 = zum Betrachter hin
    # Region: Kasten-Ecken in (u,v) umrechnen -> Fensterbreite
    ecken = np.array([[x, y, 0] for x in (x0, x1) for y in (y0, y1)]) - mitte; ue = ecken @ d; u0, u1 = ue.min(), ue.max()
    ok = (u >= u0) & (u <= u1) & (v >= z0) & (v <= z1) & (np.abs(w) <= a.tiefe)
    Wp = int(np.ceil((u1 - u0) / a.zelle)); Hp = int(np.ceil((z1 - z0) / a.zelle)); print(f"Region {(u1-u0):.1f} x {(z1-z0):.1f} m -> {Wp} x {Hp} px, Punkte {int(ok.sum())}, Rahmenrest {rest*100:.2f} cm, Seite {seite:+.0f}")
    iu = np.clip(((u[ok] - u0) / a.zelle).astype(np.int64), 0, Wp - 1); iv = np.clip(((z1 - v[ok]) / a.zelle).astype(np.int64), 0, Hp - 1); lin = torch.tensor(iv * Wp + iu, device=dev)
    wt = torch.tensor(w[ok], dtype=torch.float32, device=dev); farbe = torch.tensor(C[ok], device=dev)
    best = torch.full((Hp * Wp,), -1e9, device=dev); best.scatter_reduce_(0, lin, wt, "amax")                          # nahester Punkt zum Betrachter
    nah = wt >= best[lin] - 0.05                                                                                    # Farbe nur aus der vordersten 5-cm-Schicht
    img = torch.zeros((Hp * Wp, 3), dtype=torch.float32, device=dev); cnt = torch.zeros(Hp * Wp, device=dev)
    img.index_add_(0, lin[nah], farbe[nah].float()); cnt.index_add_(0, lin[nah], torch.ones(int(nah.sum()), device=dev))
    cntn = cnt.clamp(min=1).unsqueeze(1); img = (img / cntn); belegt = (cnt > 0).cpu().numpy().reshape(Hp, Wp)
    rgb = img.reshape(Hp, Wp, 3).cpu().numpy().astype(np.uint8); bgr = rgb[:, :, ::-1].copy()
    # Luecken (Wolke ist duenn: 1 cm Pixel) fuellen fuer die Ansicht: Dilatation nur im Bild, belegt-Anteil getrennt melden
    fill = cv2.inpaint(bgr, (~belegt).astype(np.uint8) * 255, 3, cv2.INPAINT_TELEA); cv2.imwrite(os.path.join(a.aus, "front_farbe_roh.png"), bgr); cv2.imwrite(os.path.join(a.aus, "front_farbe.png"), fill)
    wb = best.reshape(Hp, Wp).cpu().numpy(); wb[~belegt] = np.nan; wn = np.nan_to_num((wb - np.nanmin(wb)) / max(1e-6, np.nanmax(wb) - np.nanmin(wb)), nan=0)
    cv2.imwrite(os.path.join(a.aus, "front_tiefe.png"), cv2.applyColorMap((wn * 255).astype(np.uint8), cv2.COLORMAP_TURBO))
    # Abdeckung: Fotos je Punkt (.vis)
    pi, ii = FP.vis_lesen(os.path.join(a.dicht, "fused.ply.vis")); nk = np.bincount(pi, minlength=len(X)); nkr = torch.tensor(nk[ok], device=dev).float()
    asum = torch.zeros(Hp * Wp, device=dev); asum.index_add_(0, lin[nah], nkr[nah]); ab = (asum / cnt.clamp(min=1)).reshape(Hp, Wp).cpu().numpy(); ab[~belegt] = 0
    cv2.imwrite(os.path.join(a.aus, "front_abdeckung.png"), cv2.applyColorMap((np.clip(ab, 0, 8) / 8 * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS))
    baender = []; zs = np.arange(z0, z1, 1.0)
    for z in zs:
        r0 = int((z1 - min(z + 1, z1)) / a.zelle); r1 = int((z1 - z) / a.zelle); blk = belegt[r0:r1]; abk = ab[r0:r1][blk]
        baender.append(dict(z0=round(float(z), 1), belegt=round(float(blk.mean()), 3), fotos_median=round(float(np.median(abk)), 1) if abk.size else 0, anteil_unter3=round(float((abk < 3).mean()), 3) if abk.size else 1.0))
    json.dump(dict(rahmenrest_cm=rest * 100, zelle=a.zelle, groesse_px=[Wp, Hp], baender=baender, seite=float(seite), normale=n.tolist()), open(os.path.join(a.aus, "front.json"), "w"), indent=1)
    for b in baender: print(b)

#!/usr/bin/env python3
"""seiten_audit.py - PFLICHT-SICHTBLATT nach jedem Bau (Mechanik fuer Lehre F5/F6: vollstaendiger Mehrflaechen-Audit, nie nur eine Seite).

Erzeugt modelle/<objekt>/audit/seiten.jpg: vier Ansichten (Sued, Nord, Ost, West, orthografisch, schattiert) + Draufsicht,
darunter je verfuegbarem Foto mit bekannter Seite das Paar Foto | Modell aus der angepassten Kamera (kameras.json der gemeinsamen Anpassung).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/seiten_audit.py modelle/<objekt>/objekt.json
Das Blatt wird nicht bewertet - es muss ANGESEHEN werden (CLAUDE.md Regel 3). Jede Seite, die nur als Annahme existiert, ist hier sichtbar.
"""
import sys, os, json, glob, math, numpy as np, cv2, trimesh
SIL_F0 = 5.4 / 4.29   # Brennweitenfaktor der Silhouettenkamera (foto_silhouette_gpu); je Objekt in objekt.json ueberschreibbar

def lade(obj, root):
    m = trimesh.load(os.path.join(root, obj["stl"]))
    if obj.get("stl_einheit_mm", True): m.apply_scale(obj.get("stl_massstab", 1) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]]); return m

def ortho_schnell(sz, P, N, view, hoehe=900):
    """Orthografisch ueber den gemeinsamen Renderkern: Kamera weit weg + passende Brennweite (perspektivischer Fehler < 0,5 %)."""
    import render_kern as RK
    d, r, u = [np.array(v, float) for v in view]
    mit = P.mean(0); ausd = max(P @ r.max() - P @ r.min(), P @ u.max() - P @ u.min()) if False else max(np.ptp(P @ r), np.ptp(P @ u))
    D = 4000.0; cam = mit - d * D                                    # Blickrichtung d zeigt VOM Betrachter weg
    R = np.vstack([r, -u, d]); t = -R @ cam
    s_ = (hoehe - 20) / ausd; f = D * s_
    W = int(np.ptp(P @ r) * s_) + 20; H = hoehe
    img, _ = sz.schattiert_np(R, t, f, W / 2, H / 2, W, H)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

def ortho(P, N, view, hoehe=900):
    """Orthografische Ansicht: view = (Blickrichtung, Rechts-Vektor, Oben-Vektor)."""
    d, r, u = [np.array(v, float) for v in view]
    x = P @ r; y = P @ u; depth = P @ d
    x0, x1, y0, y1 = x.min(), x.max(), y.min(), y.max(); s = (hoehe - 20) / max(y1 - y0, x1 - x0)
    W = int((x1 - x0) * s) + 20; H = int((y1 - y0) * s) + 20
    px = ((x - x0) * s + 10).astype(int); py = (H - 10 - (y - y0) * s).astype(int)
    lit = np.clip(N @ np.array([0.35, -0.45, 0.82]), 0, 1); back = (N @ d) > 0.2          # Rueckseiten unterdruecken
    shade = (70 + 170 * (0.25 + 0.75 * lit)).astype(np.uint8); shade[back] = 0
    img = np.full((H, W), 238, np.uint8); zb = np.full((H, W), -1e9)
    order = np.argsort(depth)                                                                 # nah zuletzt
    for i in order:
        if back[i]: continue
        if depth[i] > zb[py[i], px[i]]:
            zb[py[i], px[i]] = depth[i]; img[max(0, py[i] - 1):py[i] + 1, max(0, px[i] - 1):px[i] + 1] = shade[i]
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

VIEWS = {"Sued (+x)": ((-1, 0, 0), (0, 1, 0), (0, 0, 1)), "Nord (-x)": ((1, 0, 0), (0, -1, 0), (0, 0, 1)),
         "Ost (+y)": ((0, -1, 0), (-1, 0, 0), (0, 0, 1)), "West (-y)": ((0, 1, 0), (1, 0, 0), (0, 0, 1)), "Draufsicht": ((0, 0, -1), (0, 1, 0), (-1, 0, 0))}

def main():
    objp = sys.argv[1]; obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    out = os.path.join(root, obj.get("audit", os.path.join(os.path.dirname(obj["masstabelle"]), "audit"))); os.makedirs(out, exist_ok=True)
    m = lade(obj, root); P, fi = trimesh.sample.sample_surface(m, 2500000, seed=0); P = np.asarray(P); N = m.face_normals[fi]
    sys.path.insert(0, os.path.join(root, "tools")); import render_kern as RK
    sz = RK.Szene(P, N); print(f"  Renderkern: {RK.geraet()}")
    tiles = []
    for name, view in VIEWS.items():
        im = ortho_schnell(sz, P, N, view); cv2.putText(im, name, (8, 26), 0, 0.8, (0, 0, 200), 2); tiles.append(im)
    H = max(t.shape[0] for t in tiles); row1 = np.hstack([cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles])
    # Foto | Render je Foto mit bekannter Seite und Kamera
    kam = {}
    for kp in glob.glob(os.path.join(root, "modelle", "foto_silhouette", "*kameras.json")): kam.update(json.load(open(kp)))
    sys.path.insert(0, os.path.join(root, "tools")); os.environ.setdefault("OBJEKT", os.path.abspath(objp))
    pairs = []
    try:
        import foto_silhouette_gpu as F, foto_profil_gpu as PG
        for nr, cfg in sorted(obj.get("fotos", {}).items()):
            if cfg.get("seite") in (None, "unbekannt") or nr not in kam: continue
            fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))
            if not fn: continue
            im = cv2.imread(fn[0]); h, w = im.shape[:2]; s = 700 / h; W2, H2 = int(w * s), 700; im = cv2.resize(im, (W2, H2)); k = W2 / 400.
            t = np.array(kam[nr]["th"], float); t[6] *= k; t[7] *= k
            cam = np.array([0, 0, t[3]]) + t[0] * np.array([math.sin(t[1]) * math.cos(t[2]), -math.cos(t[1]) * math.cos(t[2]), math.sin(t[2])])
            fw = np.array([0, 0, t[3]]) - cam; fw /= np.linalg.norm(fw); rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt)
            cr, sr = math.cos(t[4]), math.sin(t[4]); Rm = np.vstack([cr * rt + sr * dn, -sr * rt + cr * dn, fw]); tm = -Rm @ cam
            img, _ = sz.schattiert_np(Rm, tm, SIL_F0 * 400 * k * t[5], W2 / 2 + t[6], H2 / 2 + t[7], W2, H2, hintergrund=238)
            r = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            pair = np.hstack([im, r]); cv2.putText(pair, f"Foto {nr} ({cfg['seite']})", (8, 26), 0, 0.8, (0, 0, 200), 2); pairs.append(pair)
    except Exception as e:
        print("Foto-Paare uebersprungen:", e)
    sheet = row1
    if pairs:
        Wmax = max(row1.shape[1], sum(p.shape[1] + 6 for p in pairs))
        rows, cur, acc = [], [], 0
        for p in pairs:
            if acc + p.shape[1] > max(row1.shape[1], 3200) and cur: rows.append(cur); cur, acc = [], 0
            cur.append(p); acc += p.shape[1] + 6
        rows.append(cur)
        for rw in rows:
            line = np.hstack([cv2.copyMakeBorder(p, 0, 0, 0, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for p in rw])
            Wn = max(sheet.shape[1], line.shape[1])
            sheet = cv2.copyMakeBorder(sheet, 0, 0, 0, Wn - sheet.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
            line = cv2.copyMakeBorder(line, 0, 0, 0, Wn - line.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
            sheet = np.vstack([sheet, np.full((8, Wn, 3), 255, np.uint8), line])
    fn = os.path.join(out, "seiten.jpg"); cv2.imwrite(fn, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"ANSEHEN: {fn}  ({len(VIEWS)} Ansichten, {len(pairs)} Foto-Paare)")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""foto_mass.py - REPRODUZIERBARE Fotomessung: zwei Bildpunkte + Massstabskette -> Meter, als Protokoll (JSON + markierter Ausschnitt).

Bisher standen Fotomasse als "44 px x 1,5 cm" in Kommentaren - nicht nachpruefbar. Jede Messung bekommt jetzt eine Protokollnummer, die in der
Masstabelle als Quelle steht (z. B. "M-049-003"), mit Pixelkoordinaten, Massstabsherkunft und Bild.

  foto_mass.py OBJEKT.json FOTO-NR  --mess x1 y1 x2 y2  --massstab-px x1 y1 x2 y2 --massstab-m L --massstab-von "Tafel 3,4 m (MASSPRUEFUNG Teil 5)"
  foto_mass.py OBJEKT.json FOTO-NR  --mess ... --px-pro-m 97 --massstab-von "..."          (Massstab aus frueherem Protokoll)
  [--name "Eckturm Durchmesser"] [--merkmal duennes_bauteil] [--richtung h|v|frei]
Schreibt modelle/<objekt>/messprotokoll/M-<foto>-<nr>.json + .jpg. Senkrechte Masse in Schraegaufnahmen sind gestaucht -> --richtung v mit --stauchung 0.88.
"""
import sys, os, json, glob, math, cv2, numpy as np

def strahl_ebene(kam, uv, ebene):
    """Pixel -> 3D-Punkt auf einer Ebene 'x=4.85' | 'y=-5.6' | 'z=31.5' (Modellrahmen) oder beliebig 'nx,ny,nz=d' (Ebene n.X = d, z. B. gedrehte
    Fassadenebene '0.3347,0.9423,0=6.54'), mit kalibrierter Kamera (foto_kalibrieren / Kamera-Bruecke). Radiale Verzeichnung k1 (falls im K-Protokoll)
    wird vor dem Strahl entfernt (Fixpunkt-Iteration, SIMPLE_RADIAL)."""
    import cv2
    R, _ = cv2.Rodrigues(np.array(kam["rvec"])); t = np.array(kam["t"]); cam = -R.T @ t
    x, y = (uv[0] - kam["cx"]) / kam["f_px"], (uv[1] - kam["cy"]) / kam["f_px"]; k1 = float(kam.get("k1") or 0.0); xu, yu = x, y
    for _ in range(10): r2 = xu * xu + yu * yu; xu, yu = x / (1 + k1 * r2), y / (1 + k1 * r2)
    d = R.T @ np.array([xu, yu, 1.0])
    ax, val = ebene.split("="); val = float(val)
    nv = np.array([float(v) for v in ax.split(",")]) if "," in ax else np.eye(3)["xyz".index(ax.strip())]
    s = (val - nv @ cam) / (nv @ d); return cam + s * d, float(np.linalg.norm(s * d))

def main():
    a = sys.argv[1:]; obj = json.load(open(a[0])); nr = a[1]; root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0]))))
    if "--tri2d" in a:                                                    # Modus 4 (2026-11-09 R7): Grundriss-Position einer SENKRECHTEN Kante (Pfosten/Ecke) aus Peilungen in 2+ Fotos - Hoehe der Picks egal
        # foto_mass.py OBJ FOTO --tri2d K-A xa ya K-B xb yb [K-C ...] --name "..." [--achse_n nx ny]   (Pixel irgendwo auf der Kante; nur die waagerechte Peilrichtung zaehlt)
        od = os.path.join(root, os.path.dirname(obj["masstabelle"])); i = a.index("--tri2d") + 1; obs = []
        while i + 2 < len(a) and a[i].startswith("K-"): obs.append((a[i], float(a[i + 1]), float(a[i + 2]))); i += 3
        if len(obs) < 2: sys.exit("--tri2d braucht >= 2 Kameras")
        name = a[a.index("--name") + 1] if "--name" in a else "Peilung senkrechte Kante"; A_ = np.zeros((2, 2)); b_ = np.zeros(2); L = []
        for kid, x, y in obs:
            K = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(K["rvec"])); c = -R.T @ np.array(K["t"])
            xn, yn = (x - K["cx"]) / K["f_px"], (y - K["cy"]) / K["f_px"]; k1 = float(K.get("k1") or 0.0); xu, yu = xn, yn
            for _ in range(10): r2 = xu * xu + yu * yu; xu, yu = xn / (1 + k1 * r2), yn / (1 + k1 * r2)
            d = R.T @ np.array([xu, yu, 1.0]); dh = d[:2] / np.linalg.norm(d[:2]); Pm = np.eye(2) - np.outer(dh, dh); A_ += Pm; b_ += Pm @ c[:2]; L.append((kid, c[:2], dh, K))
        X = np.linalg.solve(A_, b_); res = [round(float(np.linalg.norm((X - c) - ((X - c) @ dh) * dh)), 3) for _, c, dh, _ in L]
        winkel = [float(np.degrees(np.arccos(np.clip(L[j][2] @ L[l][2], -1, 1)))) for j in range(len(L)) for l in range(j + 1, len(L))]
        an = [float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]] if "--achse_n" in a else None
        d = os.path.join(od, "messprotokoll"); n = len(glob.glob(os.path.join(d, f"M-{nr}-*.json"))) + 1; pid = f"M-{nr}-{n:03d}"
        dist = max(float(np.linalg.norm(X - c)) for _, c, _, _ in L); fmin = min(k_["f_px"] for *_, k_ in L)
        rec = dict(id=pid, typ="triangulation_plan", foto=nr, name=name, beobachtungen=[dict(kamera=k_, px=[x_, y_]) for k_, x_, y_ in obs], P_xy=X.round(3).tolist(),
                   strahl_abstand_m=res, schnittwinkel_grad=[round(w, 1) for w in winkel],
                   unsicherheit_m=round(float(max(res) + 3.0 * dist / fmin / max(np.sin(np.radians(max(winkel))), 0.05)), 3),
                   massstab_von="Kameras " + ", ".join(o_[0] for o_ in obs) + " aus SfM-Buendel (KEINE amtlichen Anker); waagerechte Peilung einer senkrechten Kante, Pickhoehe beliebig, keine Ebenenannahme")
        if an: nn = np.array(an) / np.linalg.norm(an); rec["n"] = round(float(X @ nn), 3); rec["u"] = round(float(X @ np.array([nn[1], -nn[0]])), 3)
        json.dump(rec, open(os.path.join(d, pid + ".json"), "w"), indent=1, ensure_ascii=False)
        bilder = []
        for kid, x, y in obs:
            fn = (glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*")) or glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + ".*")))
            if fn:
                im = cv2.imread(fn[0]); cv2.circle(im, (int(x), int(y)), 14, (0, 255, 255), 3)
                c_ = im[max(0, int(y) - 300):int(y) + 300, max(0, int(x) - 300):int(x) + 300].copy(); c_ = cv2.resize(c_, (600, 600)); cv2.putText(c_, kid, (8, 26), 0, 0.8, (0, 0, 255), 2); bilder.append(c_)
        if bilder: b0 = np.hstack(bilder); cv2.putText(b0, f"{pid}: {name}", (8, 590), 0, 0.7, (0, 0, 255), 2); cv2.imwrite(os.path.join(d, pid + ".jpg"), b0)
        print(f"{pid}: {name}: P_xy {X.round(3).tolist()}" + (f" n {rec['n']} u {rec['u']}" if an else "") + f" | Strahlabstand {res} m | Schnittwinkel {rec['schnittwinkel_grad']} Grad | +-{rec['unsicherheit_m']} m"); return
    if "--tri" in a:                                                      # Modus 3 (2026-11-09): Triangulation desselben Punkts in 2+ Fotos -> Tiefe direkt, ohne angenommene Ebene
        # foto_mass.py OBJ FOTO --tri K-A xa ya K-B xb yb [K-C xc yc ...] --name "..." [--achse_n nx ny]   (Pixel je Kamera, gleicher Objektpunkt)
        od = os.path.join(root, os.path.dirname(obj["masstabelle"])); i = a.index("--tri") + 1; obs = []
        while i + 2 < len(a) and a[i].startswith("K-"): obs.append((a[i], float(a[i + 1]), float(a[i + 2]))); i += 3
        if len(obs) < 2: sys.exit("--tri braucht >= 2 Kameras")
        name = a[a.index("--name") + 1] if "--name" in a else "Triangulation"; A_ = np.zeros((3, 3)); b_ = np.zeros(3); strahlen = []
        for kid, x, y in obs:
            K = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(K["rvec"])); c = -R.T @ np.array(K["t"])
            xn, yn = (x - K["cx"]) / K["f_px"], (y - K["cy"]) / K["f_px"]; k1 = float(K.get("k1") or 0.0); xu, yu = xn, yn
            for _ in range(10): r2 = xu * xu + yu * yu; xu, yu = xn / (1 + k1 * r2), yn / (1 + k1 * r2)
            d = R.T @ np.array([xu, yu, 1.0]); d /= np.linalg.norm(d); Pm = np.eye(3) - np.outer(d, d); A_ += Pm; b_ += Pm @ c; strahlen.append((kid, c, d, K))
        X = np.linalg.solve(A_, b_); res = []; winkel = []
        for kid, c, d, K in strahlen:
            v = X - c; dist = float(np.linalg.norm(v)); res.append(round(float(np.linalg.norm(v - (v @ d) * d)), 3))
        for j in range(len(strahlen)):
            for l in range(j + 1, len(strahlen)): winkel.append(float(np.degrees(np.arccos(np.clip(strahlen[j][2] @ strahlen[l][2], -1, 1)))))
        an = [float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]] if "--achse_n" in a else None
        d = os.path.join(od, "messprotokoll"); n = len(glob.glob(os.path.join(d, f"M-{nr}-*.json"))) + 1; pid = f"M-{nr}-{n:03d}"
        rec = dict(id=pid, typ="triangulation", foto=nr, name=name, beobachtungen=[dict(kamera=k_, px=[x_, y_]) for k_, x_, y_ in obs], P=X.round(3).tolist(),
                   strahl_abstand_m=res, schnittwinkel_grad=[round(w, 1) for w in winkel], z=round(float(X[2]), 3),
                   unsicherheit_m=round(float(max(res) + 3.0 * max(np.linalg.norm(X - s[1]) for s in strahlen) / min(s[3]["f_px"] for s in strahlen) / max(np.sin(np.radians(max(winkel))), 0.05)), 3),
                   massstab_von="Kameras " + ", ".join(o_[0] for o_ in obs) + " aus SfM-Buendel (KEINE amtlichen Anker); Tiefe aus Strahlschnitt, keine Ebenenannahme")
        if an: nn = np.array(an) / np.linalg.norm(an); rec["n"] = round(float(X[:2] @ nn), 3); rec["u"] = round(float(X[:2] @ np.array([nn[1], -nn[0]])), 3)
        json.dump(rec, open(os.path.join(d, pid + ".json"), "w"), indent=1, ensure_ascii=False)
        bilder = []
        for kid, x, y in obs:
            fn = (glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*")) or glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + ".*")))
            if fn:
                im = cv2.imread(fn[0]); H, W = im.shape[:2]; cv2.circle(im, (int(x), int(y)), 14, (0, 255, 255), 3)
                c_ = im[max(0, int(y) - 300):int(y) + 300, max(0, int(x) - 300):int(x) + 300].copy(); c_ = cv2.resize(c_, (600, 600)); cv2.putText(c_, kid, (8, 26), 0, 0.8, (0, 0, 255), 2); bilder.append(c_)
        if bilder: b0 = np.hstack(bilder); cv2.putText(b0, f"{pid}: {name}", (8, 590), 0, 0.7, (0, 0, 255), 2); cv2.imwrite(os.path.join(d, pid + ".jpg"), b0)
        print(f"{pid}: {name}: P {X.round(3).tolist()}" + (f" n {rec['n']} u {rec['u']}" if an else "") + f" | Strahlabstand {res} m | Schnittwinkel {rec['schnittwinkel_grad']} Grad | +-{rec['unsicherheit_m']} m"); return
    if "--kamera" in a:                                                 # Modus 2: echte Meter ueber kalibrierte Kamera + bekannte Ebene
        od = os.path.join(root, os.path.dirname(obj["masstabelle"])); kid = a[a.index("--kamera") + 1]; K = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]
        ebene = a[a.index("--ebene") + 1]; pts = [float(x) for x in a[a.index("--mess") + 1:a.index("--mess") + 5]]; name = a[a.index("--name") + 1] if "--name" in a else "Messung"
        P1, d1 = strahl_ebene(K, pts[:2], ebene); P2, d2 = strahl_ebene(K, pts[2:], ebene)
        tiefe_sigma = float(a[a.index("--tiefe-sigma") + 1]) if "--tiefe-sigma" in a else 0.3        # Unsicherheit der Ebenenlage (m)
        rel = tiefe_sigma / max(d1, 1.0); pix_m = 3.0 * d1 / K["f_px"]                                   # 3 px Pickfehler in Meter
        d = os.path.join(od, "messprotokoll"); n = len(glob.glob(os.path.join(d, f"M-{nr}-*.json"))) + 1; pid = f"M-{nr}-{n:03d}"
        rec = dict(id=pid, foto=nr, kamera=kid, ebene=ebene, name=name, mess_px=pts, P1=P1.round(3).tolist(), P2=P2.round(3).tolist(),
                   dz=round(float(P2[2] - P1[2]), 3), dy=round(float(P2[1] - P1[1]), 3), dx=round(float(P2[0] - P1[0]), 3), abstand=round(float(np.linalg.norm(P2 - P1)), 3),
                   z1=round(float(P1[2]), 3), z2=round(float(P2[2]), 3), unsicherheit_rel=round(rel, 4), unsicherheit_m=round(float(np.linalg.norm(P2 - P1)) * rel + pix_m * 1.4, 3),
                   massstab_von=(f"Kamera {kid} aus SfM-Buendel ({kq.get('typ')}, KEINE amtlichen Anker)" if (kq := json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))).get("typ", "").startswith("kamera_bruecke")
                                 else f"Kamera {kid} aus amtlichen Ankern (LoD2/DOM1/Dokument)") + f", Ebene {ebene} (+-{tiefe_sigma} m)")
        json.dump(rec, open(os.path.join(d, pid + ".json"), "w"), indent=1, ensure_ascii=False)
        fn = (glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*")) or glob.glob(os.path.join(root, obj["fotos_dir"], nr + ".*")))                                 # markierter Ausschnitt zum Nachpruefen der Picks
        if fn:
            im = cv2.imread(fn[0]); H, W = im.shape[:2]; cv2.line(im, (int(pts[0]), int(pts[1])), (int(pts[2]), int(pts[3])), (0, 0, 255), 3)
            for q_ in (pts[:2], pts[2:]): cv2.circle(im, (int(q_[0]), int(q_[1])), 12, (0, 255, 255), 3)
            x0, x1 = int(max(0, min(pts[0], pts[2]) - 300)), int(min(W, max(pts[0], pts[2]) + 300)); y0, y1 = int(max(0, min(pts[1], pts[3]) - 300)), int(min(H, max(pts[1], pts[3]) + 300))
            c = im[y0:y1, x0:x1].copy(); cv2.putText(c, f"{pid}: {name} = {rec['abstand']:.2f} m", (8, 30), 0, 0.9, (0, 0, 255), 2); cv2.imwrite(os.path.join(d, pid + ".jpg"), c)
        print(f"{pid}: {name}: P1 z={rec['z1']:.2f} y={P1[1]:.2f} | P2 z={rec['z2']:.2f} y={P2[1]:.2f} | dz {rec['dz']:.2f} dy {rec['dy']:.2f} Abstand {rec['abstand']:.2f} m +-{rec['unsicherheit_m']} m"); return
    def opt(k, n=1, d=None):
        if k not in a: return d
        i = a.index(k); return a[i + 1] if n == 1 else a[i + 1:i + 1 + n]
    mess = [float(x) for x in opt("--mess", 4)]; name = opt("--name", d="Messung"); richtung = opt("--richtung", d="frei"); st = float(opt("--stauchung", d="1.0"))
    von = opt("--massstab-von", d="?"); merkmal = opt("--merkmal", d="-")
    fn = (glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*")) or glob.glob(os.path.join(root, obj["fotos_dir"], nr + ".*")))[0]; im = cv2.imread(fn); H, W = im.shape[:2]
    if opt("--px-pro-m"): ppm = float(opt("--px-pro-m")); mpx = None
    else:
        mpx = [float(x) for x in opt("--massstab-px", 4)]; L = float(opt("--massstab-m")); ppm = math.hypot(mpx[2] - mpx[0], mpx[3] - mpx[1]) / L
    dx, dy = mess[2] - mess[0], mess[3] - mess[1]
    px = abs(dx) if richtung == "h" else abs(dy) / st if richtung == "v" else math.hypot(dx, dy)
    meter = px / ppm
    d = os.path.join(root, os.path.dirname(obj["masstabelle"]), "messprotokoll"); os.makedirs(d, exist_ok=True)
    n = len(glob.glob(os.path.join(d, f"M-{nr}-*.json"))) + 1; pid = f"M-{nr}-{n:03d}"
    rec = dict(id=pid, foto=os.path.basename(fn), bild=[W, H], name=name, merkmal=merkmal, mess_px=mess, richtung=richtung, stauchung=st,
               massstab_px=mpx, px_pro_m=round(ppm, 2), massstab_von=von, pixel=round(px, 1), meter=round(meter, 3),
               unsicherheit_m=round(meter * 0.08 + 2 / ppm, 3), hinweis="+-8 % Ablesung/Perspektive + 2 px")
    json.dump(rec, open(os.path.join(d, pid + ".json"), "w"), indent=1, ensure_ascii=False)
    o = im.copy(); cv2.line(o, (int(mess[0]), int(mess[1])), (int(mess[2]), int(mess[3])), (0, 0, 255), 3)
    if mpx: cv2.line(o, (int(mpx[0]), int(mpx[1])), (int(mpx[2]), int(mpx[3])), (0, 200, 0), 3)
    xs = [mess[0], mess[2]] + ([mpx[0], mpx[2]] if mpx else []); ys = [mess[1], mess[3]] + ([mpx[1], mpx[3]] if mpx else [])
    x0, x1 = int(max(0, min(xs) - 150)), int(min(W, max(xs) + 150)); y0, y1 = int(max(0, min(ys) - 150)), int(min(H, max(ys) + 150))
    c = o[y0:y1, x0:x1]; cv2.putText(c, f"{pid}: {name} = {meter:.2f} m ({px:.0f} px, {ppm:.1f} px/m)", (8, 28), 0, 0.8, (0, 0, 255), 2)
    cv2.imwrite(os.path.join(d, pid + ".jpg"), c)
    print(f"{pid}: {name} = {meter:.2f} m +- {rec['unsicherheit_m']} m  ({px:.0f} px bei {ppm:.1f} px/m, Massstab: {von})  -> {d}/{pid}.json/.jpg")

if __name__ == "__main__":
    main()

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
    if "--kamera" in a:                                                   # Modus 2: echte Meter ueber kalibrierte Kamera + bekannte Ebene
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
        fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))                                 # markierter Ausschnitt zum Nachpruefen der Picks
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
    fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; im = cv2.imread(fn); H, W = im.shape[:2]
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

#!/usr/bin/env python3
"""foto_element_hoehe.py - Hoehe und Groesse markanter Fassadenelemente automatisch aus dem Foto (kalibrierte Kamera, keine Handpicks).

Bisher wurden Hoehen wie "Uhrmitte 26,9 m" geschaetzt oder aus Verhaeltnissen abgeleitet. Mit einer kalibrierten Kamera laesst sich das
direkt messen: Element im Bild finden (Uhr = Kreis per Hough; dunkle Oeffnungen = Rechtecke), Sichtstrahl mit der Wandebene schneiden -> Meter.

  foto_element_hoehe.py OBJEKT.json <foto> uhr [--wand x=4.5] [--rmin 60 --rmax 400]
  foto_element_hoehe.py OBJEKT.json <foto> oeffnungen [--wand x=4.5] [--zmin 18 --zmax 32]
Die Wandebene gibt an, in welcher Ebene das Element liegt (Modellrahmen, z. B. x=4.5 fuer die Suedwand). Die Unsicherheit folgt aus
Kameraguete und Ebenenlage. Ergebnis als Messprotokoll (messprotokoll/E-<foto>-<nr>.json) und als Vorschlag fuer eine Pruefzeile.
"""
import sys, os, json, glob, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def strahl_ebene(kam, uv, ebene):
    R, _ = cv2.Rodrigues(np.array(kam["rvec"])); t = np.array(kam["t"]); C = -R.T @ t
    d = R.T @ np.array([(uv[0] - kam["cx"]) / kam["f_px"], (uv[1] - kam["cy"]) / kam["f_px"], 1.0])
    ax, val = ebene.split("="); i = "xyz".index(ax.strip()); val = float(val)
    s = (val - C[i]) / d[i]
    return C + s * d

def abstand(kam, uv1, uv2, ebene):
    """Hoehenabstand zweier Bildpunkte auf derselben Wandebene. ROBUSTER als zwei absolute Hoehen:
    ein Fehler in Kamerahoehe oder Brennweite verschiebt beide Punkte fast gleich und kuerzt sich heraus
    (2026-11-01: absolut sagte Foto 031 die Uhr auf 24,7 m und Foto 030 auf 26,8 m - der ABSTAND zum
    Zinnenkranz war in beiden Fotos dagegen einig und zeigte den Fehler von 2 m)."""
    return float(strahl_ebene(kam, uv1, ebene)[2] - strahl_ebene(kam, uv2, ebene)[2])

def main():
    a = sys.argv[1:]; objp, nr, was = a[0], a[1], a[2]
    def opt(k, d):
        return a[a.index(k) + 1] if k in a else d
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    K = json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json")))
    if "kamera" not in K: raise SystemExit(f"K-{nr}.json ohne Kamera - erst tools/foto_kalibrieren.py")
    kam = K["kamera"]; ebene = opt("--wand", "x=4.5")
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); H, W = im.shape[:2]
    grau = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); funde = []
    if was == "farbe":
        # Element ueber seine FARBE finden (Gold, Kupfergruen, Sandstein ...) statt ueber Form. Robuster als Hough,
        # weil Bauteile sich farblich von Putz und Himmel abheben, auch wenn ihre Kontur gestoert ist.
        # --ton H_von,H_bis (OpenCV-Hue 0-179), --saettigung-min, --hell-min, --flaeche-min
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
        h0, h1 = [int(x) for x in opt("--ton", "15,35").split(",")]
        smin, vmin = int(opt("--saettigung-min", 70)), int(opt("--hell-min", 90))
        maske = ((hsv[:, :, 0] >= h0) & (hsv[:, :, 0] <= h1) & (hsv[:, :, 1] >= smin) & (hsv[:, :, 2] >= vmin)).astype(np.uint8)
        maske = cv2.morphologyEx(maske, cv2.MORPH_CLOSE, np.ones((int(opt("--schliessen", 25)),) * 2, np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(maske, 8)
        for i in range(1, n):
            x, y, w, h, flaeche = st[i]
            if flaeche < int(opt("--flaeche-min", 3000)): continue
            r = 0.5 * (w + h) / 2
            Pm = strahl_ebene(kam, cen[i], ebene); Pr = strahl_ebene(kam, (cen[i][0] + r, cen[i][1]), ebene)
            funde.append(dict(art="farbfleck", px=[int(x), int(y), int(w), int(h)], flaeche_px=int(flaeche),
                              rundheit=round(float(min(w, h) / max(w, h)), 2), z=round(float(Pm[2]), 2),
                              y_quer=round(float(Pm[1]), 2), durchmesser=round(2 * float(np.linalg.norm(Pr - Pm)), 2)))
    if was == "uhr":
        kr = cv2.HoughCircles(cv2.medianBlur(grau, 5), cv2.HOUGH_GRADIENT, dp=1, minDist=200,
                              param1=120, param2=60, minRadius=int(opt("--rmin", 60)), maxRadius=int(opt("--rmax", 400)))
        if kr is None: raise SystemExit("kein Kreis gefunden - --rmin/--rmax anpassen")
        for x, y, r in np.round(kr[0]).astype(int):
            Pm = strahl_ebene(kam, (x, y), ebene); Pr = strahl_ebene(kam, (x + r, y), ebene)
            funde.append(dict(art="kreis", px=[int(x), int(y), int(r)], z=round(float(Pm[2]), 2),
                              y_quer=round(float(Pm[1]), 2), durchmesser=round(2 * float(np.linalg.norm(Pr - Pm)), 2)))
    else:
        zmin, zmax = float(opt("--zmin", 15)), float(opt("--zmax", 35))
        th = cv2.adaptiveThreshold(grau, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 101, 25)
        n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)), 8)
        for i in range(1, n):
            x, y, w, h, flaeche = st[i]
            if flaeche < 400 or w < 15 or h < 15 or flaeche / (w * h) < 0.5: continue
            Pm = strahl_ebene(kam, cen[i], ebene); Pu = strahl_ebene(kam, (cen[i][0], cen[i][1] + h / 2), ebene)
            if not (zmin <= Pm[2] <= zmax): continue
            funde.append(dict(art="oeffnung", px=[int(x), int(y), int(w), int(h)], z=round(float(Pm[2]), 2),
                              y_quer=round(float(Pm[1]), 2), hoehe_m=round(2 * abs(float(Pm[2] - Pu[2])), 2)))
    # Filter: ein Fassadenelement liegt nahe der Turmachse und in plausibler Hoehe - Wolken und Nachbardaecher fallen damit raus.
    qmax = float(opt("--quer-max", 3.5)); zmin_, zmax_ = float(opt("--zmin", 12)), float(opt("--zmax", 34))
    vorher = len(funde)
    funde = [f for f in funde if abs(f["y_quer"]) <= qmax and zmin_ <= f["z"] <= zmax_]
    if was in ("uhr", "farbe"): funde = [f for f in funde if 1.5 <= f.get("durchmesser", 0) <= 7.0]
    if was == "farbe" and "--rund" in a: funde = [f for f in funde if f["rundheit"] >= 0.6]        # Zifferblatt eines Torturms
    print(f"  Filter (|quer| <= {qmax} m, z {zmin_}-{zmax_} m): {vorher} -> {len(funde)} Fund(e)")
    funde.sort(key=lambda f: -f["z"])
    print(f"Foto {nr}, Ebene {ebene}, Kamera-RMS {kam.get('rms_px', float('nan')):.0f} px -> {len(funde)} Fund(e):")
    for f in funde: print("  " + json.dumps(f, ensure_ascii=False))
    d = os.path.join(od, "messprotokoll"); n_ = len(glob.glob(os.path.join(d, f"E-{nr}-*.json"))) + 1; pid = f"E-{nr}-{n_:03d}"
    json.dump(dict(id=pid, foto=nr, was=was, ebene=ebene, kamera=f"K-{nr}", funde=funde), open(os.path.join(d, pid + ".json"), "w"), indent=1, ensure_ascii=False)
    o = im.copy()
    for f in funde:
        p = f["px"]
        if f["art"] == "kreis": cv2.circle(o, (p[0], p[1]), p[2], (0, 0, 255), 4); cv2.putText(o, f"z={f['z']} d={f['durchmesser']}", (p[0] - 120, p[1] - p[2] - 14), 0, 1.2, (0, 0, 255), 3)
        else: cv2.rectangle(o, (p[0], p[1]), (p[0] + p[2], p[1] + p[3]), (0, 200, 0), 3); cv2.putText(o, f"{f['z']}", (p[0], p[1] - 8), 0, 0.9, (0, 200, 0), 2)
    cv2.imwrite(os.path.join(d, pid + ".jpg"), o); print(f"  -> {d}/{pid}.json/.jpg")

if __name__ == "__main__":
    main()

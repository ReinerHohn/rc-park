#!/usr/bin/env python3
"""luftbild_messen.py - Dachgeometrie aus dem Orthofoto (DOP20) messen: die einzige Quelle, die die Ost- und Westseite zeigt.

Ein Orthofoto ist nur am BODEN entzerrt. Hohe Bauteile erscheinen nach aussen versetzt (Gebaeudeversatz): ein Punkt in Hoehe h
liegt im Bild um h * tan(z) in Richtung vom Nadir weg. Fuer einen 60-m-Turm sind das leicht 10-20 m - wer das ignoriert, misst
den Grundriss voellig falsch. Dieses Werkzeug bestimmt den Versatz aus EINEM bekannten Paar (Turmachse am Boden aus LoD2 gegen
die Spitze im Bild) und rechnet danach jeden Bildpunkt auf seine wahre Lage zurueck, wenn man seine Hoehe kennt.

  luftbild_messen.py OBJEKT.json spitze            -> Versatzrichtung und -laenge aus der Turmspitze bestimmen, in objekt.json ablegen
  luftbild_messen.py OBJEKT.json tuermchen         -> die vier Ecktuermchen (gruene Kegel) finden und ihre Lage in Modellkoordinaten geben
  luftbild_messen.py OBJEKT.json vergleich         -> Modell von oben rendern, mit Versatz ins Luftbild legen, Bild zum Ansehen
Voraussetzung in objekt.json: "luftbild": {"tif": "...", "spitze_hoehe_m": 60.0}
"""
import sys, os, json, glob, math, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from messung_pruefen import plausibel
from PIL import Image
Image.MAX_IMAGE_PIXELS = None


def lade(obj, root):
    lb = obj["luftbild"]; f = lb["tif"] if os.path.isabs(lb["tif"]) else os.path.join(root, lb["tif"])
    tfw = [float(x) for x in open(f[:-4] + ".tfw")]
    return np.array(Image.open(f)), tfw, lb


def welt_zu_px(E, N, tfw):
    px, _, _, py, x0, y0 = tfw
    return (E - x0) / px, (N - y0) / py


def px_zu_welt(c, r, tfw):
    px, _, _, py, x0, y0 = tfw
    return x0 + c * px, y0 + r * py


def gruene_kegel(aus, smin=30, vmin=40):
    """Kupfergruene Flaechen (Daecher) im Ausschnitt: Farbton um 80-100 (OpenCV-Hue), maessig gesaettigt."""
    hsv = cv2.cvtColor(aus, cv2.COLOR_RGB2HSV)
    m = ((hsv[:, :, 0] >= 70) & (hsv[:, :, 0] <= 105) & (hsv[:, :, 1] >= smin) & (hsv[:, :, 2] >= vmin)).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))


def main():
    objp, modus = sys.argv[1], sys.argv[2]
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    im, tfw, lb = lade(obj, root)
    mitte = json.load(open(os.path.join(root, os.path.dirname(obj["masstabelle"]), "anker3d.json")))["mitte_utm"]
    cx, cy = welt_zu_px(mitte[0], mitte[1], tfw); aufl = abs(tfw[0])
    w = int(30 / aufl); c0, r0 = int(cx - w), int(cy - w)
    aus = im[r0:r0 + 2 * w, c0:c0 + 2 * w]
    gr = gruene_kegel(aus)

    if modus == "spitze":
        # Die Turmspitze ist der gruene Fleck, der am weitesten vom Grundriss entfernt liegt - sie hat den groessten Versatz.
        n, lab, st, cen = cv2.connectedComponentsWithStats(gr, 8)
        kand = [(st[i, cv2.CC_STAT_AREA], cen[i]) for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 40]
        if not kand: raise SystemExit("keine gruene Dachflaeche gefunden")
        flaeche, mp = max(kand, key=lambda t: t[0])                      # groesste gruene Flaeche = Hauptdach
        # Das Dach eines 10 x 11 m Turms kann keine 2700 m2 haben - genau das meldete die erste Fassung (Baeume und Schatten).
        plausibel(flaeche * aufl ** 2, 40, 260, "groesste gruene Flaeche (Hauptdach)", "m2")
        E, N = px_zu_welt(c0 + mp[0], r0 + mp[1], tfw)
        dE, dN = E - mitte[0], N - mitte[1]; laenge = math.hypot(dE, dN)
        h = float(lb.get("spitze_hoehe_m", 60.0)) * 0.5                  # Schwerpunkt des Dachs liegt etwa auf halber Hoehe
        print(f"Groesste gruene Dachflaeche: {flaeche * aufl**2:.1f} m2, Schwerpunkt {laenge:.1f} m vom Grundriss entfernt")
        plausibel(laenge, 2.0, 40.0, "Versatz der Dachmitte gegenueber dem Grundriss", "m")
        print(f"  Versatzrichtung {math.degrees(math.atan2(dN, dE)) % 360:.0f} Grad, Versatz je Hoehenmeter {laenge / h:.3f} m/m "
              f"(entspricht Blickwinkel {math.degrees(math.atan(laenge / h)):.0f} Grad aus der Senkrechten)")
        obj.setdefault("luftbild", {}).update(versatz_pro_m=round(laenge / h, 4), versatz_richtung_grad=round(math.degrees(math.atan2(dN, dE)) % 360, 1))
        json.dump(obj, open(objp, "w"), indent=1, ensure_ascii=False); print("  -> in objekt.json abgelegt")

    elif modus == "tuermchen":
        v = float(lb["versatz_pro_m"]); ri = math.radians(lb["versatz_richtung_grad"])
        n, lab, st, cen = cv2.connectedComponentsWithStats(gr, 8)
        funde = []
        for i in range(1, n):
            a = st[i, cv2.CC_STAT_AREA]
            if not (8 <= a * aufl ** 2 <= 12): continue                  # Kegelgrundflaeche eines Ecktuermchens: ~2,4 m Durchmesser
            E, N = px_zu_welt(c0 + cen[i][0], r0 + cen[i][1], tfw)
            h = 41.2                                                      # Hoehe der Tuermchenspitzen (Laser DOM1)
            E -= v * h * math.cos(ri); N -= v * h * math.sin(ri)          # Gebaeudeversatz zuruecknehmen
            dx, dy = E - mitte[0], N - mitte[1]
            funde.append((round(a * aufl ** 2, 1), round(dx, 2), round(dy, 2)))
        print(f"{len(funde)} Kegel in Tuermchengroesse (Flaeche m2, Lage relativ zur Turmmitte in UTM-Metern):")
        for f in sorted(funde, key=lambda t: -t[0]): print(f"   {f[0]:5.1f} m2  bei dE {f[1]:+6.2f}  dN {f[2]:+6.2f}")

    else:
        o = aus.copy()
        o[gr > 0] = (0.4 * o[gr > 0] + 0.6 * np.array([255, 0, 0])).astype(np.uint8)
        cv2.circle(o, (w, w), 4, (255, 255, 0), -1)                       # Turmachse am Boden
        pfad = os.path.join(root, obj.get("audit", "audit"), "luftbild.jpg"); os.makedirs(os.path.dirname(pfad), exist_ok=True)
        cv2.imwrite(pfad, cv2.cvtColor(cv2.resize(o, (0, 0), fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4), cv2.COLOR_RGB2BGR))
        print(f"ANSEHEN: {pfad}  (rot = kupfergruene Dachflaechen, gelb = Turmachse am Boden)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""foto_pick.py - Ankerpunkte im VOLLBILD auf +-2 px: automatische Spitzen/Kugeln + Lupenblatt fuer Handpicks.

  foto_pick.py OBJEKT.json FOTO auto            -> findet Spitzen (Nadel, Tuermchen) und Goldkugeln in der Himmelsmaske (Sub-Pixel), schreibt
                                                   messprotokoll/K-<foto>.json: "auto": {...} und ein Kontrollbild lupe_<foto>/auto.jpg
  foto_pick.py OBJEKT.json FOTO lupe            -> je Pick in K-<foto>.json ein 3x vergroesserter 240-px-Ausschnitt mit 10-px-Gitter (Koordinaten
                                                   des Vollbilds am Rand) + Kontaktbogen lupe_<foto>/lupe.jpg. Daran Picks ablesen/korrigieren.
  foto_pick.py OBJEKT.json FOTO setze NAME u v  -> Pick setzen (nach Lupe), z. B. aus der Pick-Seite (pick.html) uebernommen
Spitzen: oberste Nicht-Himmel-Pixel je Spalte -> lokale Maxima der Oberkontur -> Kanten links/rechts der Spitze als Geraden gefittet -> Schnittpunkt.
Kugeln: kleine runde Nicht-Himmel-Komponenten (10-400 px2), ganz von Himmel umgeben oder nur unten verbunden -> Schwerpunkt.
"""
import sys, os, json, glob, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def plausibel(sk):
    """Eine Himmelsmaske ist brauchbar, wenn der obere Bildrand ueberwiegend Himmel ist und die untere Bildmitte (dort steht das Bauwerk) kaum.
    Faengt den Fehler 'weisse Wand als Himmel' und 'Baum am oberen Rand -> fast kein Himmel' ab."""
    H, W = sk.shape
    oben = sk[:max(3, H // 50), :].mean(); unten_mitte = sk[int(0.55 * H):int(0.95 * H), int(0.35 * W):int(0.65 * W)].mean()
    return (0.05 <= sk.mean() <= 0.9) and oben >= 0.3 and unten_mitte <= 0.25, dict(anteil=round(float(sk.mean()), 3), oben=round(float(oben), 2), unten_mitte=round(float(unten_mitte), 2))

def himmel(im, streng=False):
    """Himmelsmaske mit Pruefung. Drei Verfahren nacheinander, die erste plausible gewinnt; sonst Fehler statt stiller Unsinn.
    FALLE (2026-11-01): die Regel 'hell und ungesaettigt' machte die weisse Turmwand zu Himmel -> Breitenprofil mass 5,8 m statt 13 m."""
    import foto_silhouette_gpu as F
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); b, g, r = [im[:, :, i].astype(int) for i in range(3)]
    def randkomponente(cand):
        cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n, lab = cv2.connectedComponents(cand); rand = set(np.unique(np.r_[lab[0, :], lab[:, 0], lab[:, -1]])) - {0}
        return np.isin(lab, list(rand))
    kandidaten = [("referenz", F.sky_mask(im)),
                  ("blau", randkomponente((b > r + 20) & (b > g + 8) & (hsv[:, :, 2] > 80))),           # klarer Himmel - KEINE Helligkeitsregel
                  ("blau weich", randkomponente((b > r + 8) & (hsv[:, :, 2] > 120) & (hsv[:, :, 1] > 15)))]  # dunstig/bewoelkt
    befunde = []
    for name, sk in kandidaten:
        ok, info = plausibel(sk); befunde.append((name, ok, info))
        if ok:
            if streng: print(f"  Himmelsmaske: {name} {info}")
            return sk
    raise SystemExit("keine plausible Himmelsmaske: " + "; ".join(f"{n} {i}" for n, _, i in befunde) +
                     "  (oben >= 0,3 und untere Bildmitte <= 0,25 verlangt)")

def spitzen(nicht_himmel, min_abstand=60, hoehe_min=40):
    H, W = nicht_himmel.shape; top = np.array([np.argmax(nicht_himmel[:, c]) if nicht_himmel[:, c].any() else H for c in range(W)], float)
    cand = []
    for c in range(2, W - 2):
        if 2 < top[c] < H and top[c] <= top[max(0, c - min_abstand):c + min_abstand + 1].min() and (top[max(0, c - 150):c + 151].max() - top[c]) >= hoehe_min:
            cand.append(c)                                            # Bildrand (top <= 2) ausgeschlossen: dort beginnt kein Objekt, es ist abgeschnitten
    gruppen = []                                                      # benachbarte Spalten = eine Spitze (Spalte mit kleinstem top)
    for c in cand:
        if gruppen and c - gruppen[-1][-1] <= 3: gruppen[-1].append(c)
        else: gruppen.append([c])
    cand = [min(g, key=lambda c: (top[c], abs(c - np.mean(g)))) for g in gruppen]
    out = []
    for c in cand:                                                    # Kanten links/rechts der Spitze: Punkte der Oberkontur 8..60 px unterhalb der Spitze
        y0 = top[c]; L, R = [], []
        for d in range(1, 80):
            if c - d >= 0 and 8 <= top[c - d] - y0 <= 60: L.append((c - d, top[c - d]))
            if c + d < W and 8 <= top[c + d] - y0 <= 60: R.append((c + d, top[c + d]))
        if len(L) >= 4 and len(R) >= 4:
            (al, bl) = np.polyfit([p[1] for p in L], [p[0] for p in L], 1); (ar, br) = np.polyfit([p[1] for p in R], [p[0] for p in R], 1)   # x = a*y + b
            if abs(al - ar) > 1e-6:
                y = (br - bl) / (al - ar); x = al * y + bl
                if abs(y - y0) < 25: out.append(dict(u=round(float(x), 1), v=round(float(y), 1), spalte=c, art="spitze")); continue
        out.append(dict(u=float(c), v=float(y0), spalte=c, art="spitze_grob"))
    return out

def kugeln(nicht_himmel, im):
    """Goldkugeln: kleine runde Komponenten, goldfarben (R >= G > B), nicht Blattwerk (G dominant)."""
    n, lab, st, cen = cv2.connectedComponentsWithStats(nicht_himmel.astype(np.uint8), 8)
    out = []
    for i in range(1, n):
        a = st[i, cv2.CC_STAT_AREA]; w, h = st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        if not (10 <= a <= 400 and 0.6 <= w / max(h, 1) <= 1.6 and a / (w * h) > 0.5): continue
        b, g, r = [float(x) for x in im[lab == i].mean(0)]
        if r >= g - 5 and r > b + 25: out.append(dict(u=round(float(cen[i][0]), 1), v=round(float(cen[i][1]), 1), flaeche=int(a), art="kugel", farbe=[int(r), int(g), int(b)]))
    return out

def main():
    objp, nr, modus = sys.argv[1:4]; obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"])); kp = os.path.join(od, "messprotokoll", f"K-{nr}.json")
    K = json.load(open(kp)) if os.path.exists(kp) else {"foto": nr, "punkte": {}}
    fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; im = cv2.imread(fn); H, W = im.shape[:2]
    ld = os.path.join(od, "messprotokoll", f"lupe_{nr}"); os.makedirs(ld, exist_ok=True)
    if modus == "auto":
        nh = ~himmel(im); nh = cv2.morphologyEx(nh.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)   # Leitungen (1-2 px) weg
        sp = spitzen(nh); ku = kugeln(~himmel(im), im); K["auto"] = dict(spitzen=sp, kugeln=ku)
        o = im.copy()
        for s in sp: cv2.drawMarker(o, (int(s["u"]), int(s["v"])), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 40, 3); cv2.putText(o, f"{s['u']:.0f},{s['v']:.0f}", (int(s["u"]) + 20, int(s["v"]) + 30), 0, 1.0, (0, 0, 255), 2)
        for k in ku: cv2.circle(o, (int(k["u"]), int(k["v"])), 18, (0, 255, 0), 3); cv2.putText(o, f"{k['u']:.0f},{k['v']:.0f}", (int(k["u"]) + 20, int(k["v"]) - 10), 0, 0.9, (0, 255, 0), 2)
        cv2.imwrite(os.path.join(ld, "auto.jpg"), o); json.dump(K, open(kp, "w"), indent=1, ensure_ascii=False)
        print(f"Spitzen: {[(s['u'], s['v'], s['art']) for s in sp]}\nKugeln: {[(k['u'], k['v']) for k in ku]}\nKontrollbild: {ld}/auto.jpg")
    elif modus == "lupe":
        tiles = []
        for name, (u, v) in K["punkte"].items():
            r = 40; x0, y0 = int(max(0, u - r)), int(max(0, v - r)); c = im[y0:y0 + 2 * r, x0:x0 + 2 * r]; c = cv2.resize(c, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            for k in range(0, 2 * r + 1, 10):
                cv2.line(c, (k * 3, 0), (k * 3, c.shape[0]), (0, 255, 255), 1); cv2.line(c, (0, k * 3), (c.shape[1], k * 3), (0, 255, 255), 1)
                cv2.putText(c, str(x0 + k), (k * 3 + 1, 12), 0, 0.35, (0, 255, 255), 1); cv2.putText(c, str(y0 + k), (1, k * 3 + 12), 0, 0.35, (0, 255, 255), 1)
            cv2.drawMarker(c, (int((u - x0) * 3), int((v - y0) * 3)), (0, 0, 255), cv2.MARKER_CROSS, 30, 2)
            cv2.putText(c, f"{name} ({u:.0f},{v:.0f})", (4, c.shape[0] - 6), 0, 0.5, (255, 255, 255), 2); cv2.putText(c, f"{name} ({u:.0f},{v:.0f})", (4, c.shape[0] - 6), 0, 0.5, (0, 0, 255), 1)
            cv2.imwrite(os.path.join(ld, f"{name}.jpg"), c); tiles.append(cv2.copyMakeBorder(c, 0, 0, 0, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
        if tiles:
            n = 4; rows = [np.hstack(tiles[i:i + n] + [np.full_like(tiles[0], 255)] * (n - len(tiles[i:i + n]))) for i in range(0, len(tiles), n)]
            cv2.imwrite(os.path.join(ld, "lupe.jpg"), np.vstack(rows)); print(f"Lupenblatt: {ld}/lupe.jpg ({len(tiles)} Picks, 3x, Gitter 10 px, Koordinaten = Vollbild)")
    elif modus == "setze":
        name, u, v = sys.argv[4], float(sys.argv[5]), float(sys.argv[6]); alt = K["punkte"].get(name); K["punkte"][name] = [u, v]
        K.setdefault("pick_historie", []).append(dict(name=name, alt=alt, neu=[u, v])); json.dump(K, open(kp, "w"), indent=1, ensure_ascii=False); print(f"{name}: {alt} -> {[u, v]}")

if __name__ == "__main__":
    main()

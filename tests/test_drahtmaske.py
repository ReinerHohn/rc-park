#!/usr/bin/env python3
"""test_drahtmaske.py - Waechter fuer tools/drahtmaske.py + tools/drahtmasken.py (24.11.2026, Oberleitung vor dem Schwabentor als 'Fahnen' in der Wolke).

Synthetisches Foto 1500 x 2000: Himmel oben, Wand unten mit Quadern + Fugen (auch durchgehende waagrechte Lagerfugen, 2 px), Gesims (heller Wulst + Schattenkante),
Fenster mit dunklen Rahmen, Dachkante gegen den Himmel, Fallrohr (10 px), Zweige-Stummel im Himmel; dazu ZWEI Draehte: ein gerader, ein durchhaengender,
beide ueber Himmel UND Wand.
  1. Draehte: >= 85 % ihrer Pixel maskiert (vor Himmel), >= 60 % auch vor der Wand.
  2. ROT-PROBE: Fugen, Gesims, Fensterrahmen, Dachkante, Fallrohr - weniger als 0,5 % ihrer Pixel maskiert (abseits der Draehte).
  3. Gleiches Bild ohne Draehte -> Maske leer.
  4. drahtmasken.masken_ordner: COLMAP-Format (0 = Draht oder Himmel) in Bildgroesse, Bericht; OHNE_DRAHTMASKE=1 -> leere Maske / nichts geschrieben.
  5. HIMMEL FUER DIE FUSION (24.11.2026, blaues Geisterblatt 1122z): himmelmaske/fusionsmaske maskieren >= 90 % des Himmels abseits der Silhouette (auch um die
     Draehte), ROT-PROBE Dachkante, Turmspitze (6 px), Laterne, Gesims mit seitlichem Himmelsanschluss: Gebaeudepixel < 0,5 % maskiert, Saum HIMMEL_RAND_PX an der
     Silhouette frei; Wand ohne Himmel leer. Blauer Himmel nur himmelmaske (drahtmaske() haelt im blauen Fall die Lagerfugen der Testwand fuer Draehte - eigener Befund).
Ausgabe 'OK ...' oder 'FEHLER ...' (rc 1)."""
import os, sys, json, tempfile
import numpy as np, cv2

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(R, "tools"))
os.environ["RCPARK_MASKEN_CACHE"] = "0"; os.environ.pop("OHNE_DRAHTMASKE", None)
import drahtmaske as DM, drahtmasken as DMK

W, H = 1500, 2000; rng = np.random.default_rng(7)


def szene(mit_draht=True, turm=False):
    b = np.zeros((H, W, 3), np.uint8); b[:] = (235, 228, 222)                 # Himmel, leichter Verlauf
    b = (b.astype(float) * np.linspace(0.92, 1.0, H)[:, None, None]).astype(np.uint8)
    top = 700; rot = {}                                                       # Gebaeude ab y=700 (Dachkante gegen Himmel), links x 100..1400
    b[top:, 100:1400] = (120, 130, 150)
    for y in range(top, H, 40):                                               # Quader mit Fugen; Lagerfugen laufen ueber die ganze Wand
        x = 100 + int(rng.integers(-30, 0))
        while x < 1400:
            L = int(rng.integers(60, 110)); b[y:y + 40, max(x, 100):min(x + L, 1400)] = rng.integers(100, 160, 3); x += L
            if x < 1398: cv2.line(b, (x, y), (x, y + 39), (70, 70, 80), 2)
        cv2.line(b, (100, y), (1399, y), (70, 70, 80), 2)
    fugen = np.zeros((H, W), bool); g0 = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY); fugen[top + 2:, 102:1398] = g0[top + 2:, 102:1398] < 85
    rot["fugen"] = fugen
    gs = np.zeros((H, W), np.uint8); cv2.rectangle(b, (100, 1000), (1399, 1030), (215, 215, 210), -1); cv2.rectangle(b, (100, 1031), (1399, 1036), (40, 40, 45), -1)   # Gesims + Schatten
    cv2.rectangle(gs, (100, 1000), (1399, 1036), 1, -1); rot["gesims"] = gs > 0
    fe = np.zeros((H, W), np.uint8)
    for x0 in (250, 650, 1050):                                               # Fenster mit 3-px-Rahmen
        cv2.rectangle(b, (x0, 1200), (x0 + 180, 1500), (200, 205, 210), -1); cv2.rectangle(b, (x0, 1200), (x0 + 180, 1500), (35, 35, 40), 3)
        cv2.line(b, (x0 + 90, 1200), (x0 + 90, 1500), (35, 35, 40), 3); cv2.rectangle(fe, (x0, 1200), (x0 + 180, 1500), 1, 3)
    rot["fenster"] = fe > 0
    dk = np.zeros((H, W), np.uint8); cv2.line(b, (100, top), (1399, top), (30, 30, 35), 3); cv2.line(dk, (100, top), (1399, top), 1, 3); rot["dachkante"] = dk > 0
    fr = np.zeros((H, W), np.uint8); cv2.line(b, (1360, top), (1360, H - 1), (40, 40, 40), 10); cv2.line(fr, (1360, top), (1360, H - 1), 1, 10); rot["fallrohr"] = fr > 0
    if turm:                                                                  # Silhouette vor Himmel: Turmspitze (6 px) und Laterne mit Knauf auf dem Dach
        cv2.rectangle(b, (697, top - 160), (702, top), (60, 55, 50), -1); cv2.rectangle(b, (980, top - 70), (1030, top), (90, 85, 95), -1)
        cv2.circle(b, (1005, top - 82), 12, (70, 65, 60), -1)
        sil = np.zeros((H, W), np.uint8); cv2.rectangle(sil, (697, top - 160), (702, top), 1, -1); cv2.rectangle(sil, (980, top - 70), (1030, top), 1, -1)
        cv2.circle(sil, (1005, top - 82), 12, 1, -1); sil[top:top + 4, 100:1400] = 1; rot["silhouette"] = sil > 0
    for _ in range(25):                                                       # kurze Zweig-/Antennenstummel im Himmel
        x, y = int(rng.integers(50, 1450)), int(rng.integers(50, 600)); a = rng.uniform(0, np.pi)
        cv2.line(b, (x, y), (int(x + 60 * np.cos(a)), int(y + 60 * np.sin(a))), (60, 60, 60), 2)
    b = np.clip(b.astype(int) + rng.normal(0, 4, b.shape), 0, 255).astype(np.uint8)
    dr = []
    if mit_draht:
        d1 = np.zeros((H, W), np.uint8); cv2.line(b, (0, 150), (1499, 1650), (45, 45, 50), 3); cv2.line(d1, (0, 150), (1499, 1650), 1, 3); dr.append(d1 > 0)
        xs = np.arange(0, W)                                                  # zweiter Draht: durchhaengend (Parabel), links im Himmel, rechts vor der Wand
        ys2 = (200 + 0.55 * xs + 0.00012 * (xs - 750.0) ** 2).astype(int); pts = np.stack([xs, ys2], 1).reshape(-1, 1, 2).astype(np.int32)
        d2 = np.zeros((H, W), np.uint8); cv2.polylines(b, [pts], False, (40, 40, 45), 2); cv2.polylines(d2, [pts], False, 1, 2); dr.append(d2 > 0)
    return b, rot, dr


def main():
    fehler = []; b, rot, dr = szene(True); I = {}; m = DM.drahtmaske(b, info=I) > 0
    himmel = np.zeros((H, W), bool); himmel[:690] = True; himmel[:, :95] = True; himmel[:, 1405:] = True
    alle_dr = np.zeros((H, W), bool)
    for k, d in enumerate(dr):
        alle_dr |= d; vh = m[d & himmel].mean(); vw = m[d & ~himmel].mean() if (d & ~himmel).any() else 1.0
        print(f"Draht {k + 1}: vor Himmel {vh:.0%} maskiert, vor Wand {vw:.0%}")
        if vh < 0.85: fehler.append(f"Draht {k + 1} vor Himmel nur {vh:.0%} maskiert (>= 85 %)")
        if vw < 0.60: fehler.append(f"Draht {k + 1} vor der Wand nur {vw:.0%} maskiert (>= 60 %)")
    weg = cv2.dilate(alle_dr.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0
    for n, r in rot.items():
        a = m[r & ~weg].mean(); print(f"Rot-Probe {n}: {a:.2%} maskiert")
        if a > 0.005: fehler.append(f"Rot-Probe {n}: {a:.2%} maskiert (> 0,5 %)")
    frei = m[~weg].mean(); print(f"abseits der Draehte maskiert: {frei:.3%}, angenommen {len(I['angenommen'])}")
    if frei > 0.002: fehler.append(f"abseits der Draehte {frei:.3%} maskiert")
    b0, _, _ = szene(False); m0 = DM.drahtmaske(b0)
    if m0.any(): fehler.append(f"ohne Draehte {int((m0 > 0).sum())} Pixel maskiert")
    with tempfile.TemporaryDirectory() as td:                                 # Ordner-Weg, COLMAP-Format, Schalter
        bd = os.path.join(td, "bilder"); os.makedirs(bd); cv2.imwrite(os.path.join(bd, "a.jpg"), b); cv2.imwrite(os.path.join(bd, "b.jpg"), b0)
        B = DMK.masken_ordner(bd, os.path.join(td, "m"), colmap=True, rand_px=2, arbeiter=1)
        ma = cv2.imread(os.path.join(td, "m", "a.jpg.png"), cv2.IMREAD_GRAYSCALE); mb = cv2.imread(os.path.join(td, "m", "b.jpg.png"), cv2.IMREAD_GRAYSCALE)
        if ma is None or ma.shape != (H, W) or (ma == 0).mean() < 0.002 or mb is None: fehler.append("COLMAP-Masken falsch (Groesse/0 = Draht)")
        if not ((ma == 0) & ~cv2.resize(DM.himmelmaske(b), (W, H)).astype(bool)).any(): fehler.append("COLMAP-Maske ohne Drahtanteil")
        if (mb == 0)[:600].mean() < 0.8 or (mb == 0)[720:, 100:1400].mean() > 0.005: fehler.append(f"COLMAP-Maske b: Himmel {(mb == 0)[:600].mean():.0%} (>= 80 %), Wand {(mb == 0)[720:, 100:1400].mean():.2%}")
        if B.get("mit_draht") != 2 or not DMK.colmap_masken_aktuell(os.path.join(td, "m")): fehler.append(f"Bericht falsch: {B.get('mit_draht')}")
        os.environ["OHNE_DRAHTMASKE"] = "1"
        if DMK.maske_fuer(os.path.join(bd, "a.jpg")).any() or not DMK.masken_ordner(bd, os.path.join(td, "m2")).get("aus") or os.path.exists(os.path.join(td, "m2")):
            fehler.append("OHNE_DRAHTMASKE=1 schaltet nicht ab")
        os.environ.pop("OHNE_DRAHTMASKE")
    fehler += himmel_probe()
    if fehler: print("FEHLER " + " | ".join(fehler)); return 1
    print("OK Drahtmaske: 2 Draehte ueber Himmel und Wand maskiert, Fugen/Gesims/Fenster/Dachkante/Fallrohr frei, COLMAP-Format, Schalter; Himmel fuer die Fusion maskiert, Dachkante/Turmspitze/Laterne frei"); return 0


def himmel_probe():
    """Punkt 5: Himmelsmaske fuer die Fusion (grauer und blauer Himmel), Rot-Probe Silhouette."""
    f = []
    for name, blau in (("grau", False), ("blau", True)):
        b, rot, dr = szene(True, turm=True)
        if blau:                                                              # blauer Himmel (BGR), gleiche Gebaeude: alles oberhalb der Silhouette einfaerben
            g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY); hm = np.zeros((H, W), bool); hm[:700] = g[:700] > 150
            b[hm] = np.clip(np.array([225, 175, 120]) + rng.normal(0, 3, (int(hm.sum()), 3)), 0, 255).astype(np.uint8)
        mh = DM.himmelmaske(b) > 0; m = (np.maximum(DM.drahtmaske(b), mh * 255) if not blau else mh) > 0; sil = rot["silhouette"] | (np.arange(H)[:, None] >= 700) & (np.arange(W)[None, :] >= 100) & (np.arange(W)[None, :] < 1400)
        alle_dr = np.zeros((H, W), bool)
        for d in dr: alle_dr |= d
        nah = cv2.dilate(sil.astype(np.uint8), np.ones((41, 41), np.uint8)) > 0; r = DM.HIMMEL_RAND_PX; saum = (cv2.dilate(sil.astype(np.uint8), DM._kern(2 * r + 1)) > 0) & ~sil & (np.arange(H)[:, None] < 720)
        # (Saum nur an der oberen Silhouette: das Testgesims ist farbgleich mit dem Himmel ohne Kante - dort waechst die Maske hoechstens HIMMEL_WACHS px hinein, Wand-Probe)
        drw = cv2.dilate(alle_dr.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0
        himmel_fern = ~nah & (np.arange(H)[:, None] < 690); hv = m[himmel_fern].mean(); hd = m[himmel_fern & drw & ~(cv2.dilate(alle_dr.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0)].mean()
        geb = mh[rot["silhouette"]].mean(); sv = mh[saum].mean(); wand = m[(np.arange(H)[:, None] >= 720) & ~drw & sil].mean()   # Rot-Probe der HIMMELmaske (Drahtmaske: Punkt 2)
        print(f"Himmel {name}: fern maskiert {hv:.1%}, um Draehte (4-15 px) {hd:.1%}; Rot-Probe Silhouette {geb:.2%}, Saum {r} px {sv:.2%}, Wand {wand:.3%}")
        if hv < 0.90: f.append(f"Himmel {name} nur {hv:.0%} maskiert (>= 90 %)")
        if hd < 0.90: f.append(f"Himmel {name} um Draehte nur {hd:.0%} maskiert (>= 90 %)")
        if geb > 0.005: f.append(f"Rot-Probe Silhouette ({name}) {geb:.2%} maskiert (Dachkante/Turmspitze/Laterne verschwinden)")
        if sv > 0.005: f.append(f"Rot-Probe Saum {r} px ({name}) {sv:.2%} maskiert, z. B. bei (x, y) {[tuple(int(t) for t in q) for q in np.argwhere(saum & mh)[::50, ::-1][:6]]}")
        if wand > 0.005: f.append(f"Wand ({name}) {wand:.2%} maskiert")
        gm = mh[rot["gesims"]].mean()
        if gm > 0.1: f.append(f"Gesims ({name}) {gm:.1%} als Himmel maskiert (> 10 %: Kern nicht geoeffnet?)")
    b0 = szene(False)[0][800:, 100:1400].copy()                              # Ausschnitt nur Wand, kein Himmel -> leer
    if (DM.himmelmaske(b0) > 0).mean() > 0.001: f.append(f"Wand ohne Himmel {(DM.himmelmaske(b0) > 0).mean():.2%} als Himmel maskiert")
    return f


if __name__ == "__main__":
    sys.exit(main())

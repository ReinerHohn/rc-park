#!/usr/bin/env python3
"""test_wolke_draehte.py - Draht-/Fahnenfilter der dichten Wolke (tools/wolke_draehte.py), Anlass 24.11.2026 Nutzerbefund schwabentor-1122:
Oberleitung/Spanndraehte als diagonale Linien und als schmale schraege Blaetter ("Fahnen") vor der Nordseite.

Synthetisch (Meter, z oben): Wand x=0 mit Gesims, angebundenem schmalem Pultdach (Vordach) und Dach oben, lotrechte Wetterstange auf dem First,
freier Draht (schraeg) und freie Fahne (Draht als 0,8-m-Band verschmiert, schraege Ebene). ROT-PROBE: Wand, Gesims, Vordach, Dach, Stange bleiben
(<= 1 %); Draht und Fahne gehen (>= 85 %). Dazu: Kettenstufe 'draehte' steht vor 'html' und html zeigt die gefilterte Kopie.
"""
import os, re, sys, json, tempfile, subprocess
import numpy as np
T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"); sys.path.insert(0, T)
import wolke_draehte as WD

rng = np.random.default_rng(7); F = []


def flaeche(o, a, b, dichte=400, rausch=0.03):
    o, a, b = (np.asarray(x, float) for x in (o, a, b)); n = int(dichte * np.linalg.norm(a) * np.linalg.norm(b))
    u, v = rng.random((2, n)); nrm = np.cross(a, b); nrm /= np.linalg.norm(nrm)
    return o + u[:, None] * a + v[:, None] * b + rng.normal(0, rausch, (n, 1)) * nrm


def linie(p, q, je_m=300, rausch=0.02):
    p, q = np.asarray(p, float), np.asarray(q, float); n = int(je_m * np.linalg.norm(q - p)); t = rng.random(n)
    return p + t[:, None] * (q - p) + rng.normal(0, rausch, (n, 3))


teile = {
    "wand": flaeche([0, 0, 0], [0, 10, 0], [0, 0, 10]),
    "gesims": np.vstack([flaeche([0, 0, 6], [0, 10, 0], [0.4, 0, 0]), flaeche([0.4, 0, 5.8], [0, 10, 0], [0, 0, 0.2])]),
    "vordach": flaeche([0, 0, 4], [0, 10, 0], [1.2, 0, -0.5]),                       # angebundenes Pultdach 1,3 m tief - schmal und schraeg wie eine Fahne
    "dach": flaeche([0, 0, 10], [0, 10, 0], [-3.0, 0, 2.0]),
    "stange": linie([-1.5, 5, 11.0], [-1.5, 5, 14.0], rausch=0.015),                 # Wetterstange/Turmspitze: lotrecht, bleibt
    "draht": linie([3, 0, 7], [3, 10, 5]),
    "fahne": flaeche([5, 0, 8] - 0.4 * np.array([0.6, 0, 0.8]), [0, 6, 0], 0.8 * np.array([0.6, 0, 0.8])),
}
X = np.vstack(list(teile.values())); lab = np.concatenate([[k] * len(v) for k, v in teile.items()])
entf, info = WD.draht_maske(X, workers=2)
fehler = []
for k in teile:
    a = float(entf[lab == k].mean())
    soll_weg = k in ("draht", "fahne")
    print(f"  {k:8s} entfernt {100 * a:5.1f} %  ({'soll weg' if soll_weg else 'soll bleiben'})")
    if soll_weg and a < 0.85: fehler.append(f"FEHLER {k}: nur {100 * a:.1f} % entfernt (>= 85 % erwartet)")
    if not soll_weg and a > 0.01: fehler.append(f"FEHLER {k}: {100 * a:.1f} % entfernt - echte Gebaeudeteile duerfen nicht weg (Rot-Probe)")
# CLI: Kopie + Bericht + Bild, Original unveraendert
with tempfile.TemporaryDirectory() as d:
    w = os.path.join(d, "punkte_modell_t.npy"); np.save(w, X); np.save(w.replace("punkte_modell_", "punkte_farben_"), np.full((len(X), 3), 128, np.uint8))
    r = subprocess.run([sys.executable, "-I", os.path.join(T, "wolke_draehte.py"), w, "--farben", w.replace("punkte_modell_", "punkte_farben_"), "--aus", os.path.join(d, "a"),
                        "--bild", os.path.join(d, "k.jpg"), "--workers", "2"], capture_output=True, text=True)
    if r.returncode: fehler.append(f"FEHLER CLI rc {r.returncode}: {r.stderr[-300:]}")
    else:
        b = json.load(open(os.path.join(d, "a", "wolke_draehte.json"))); k_ = np.load(os.path.join(d, "a", "punkte_modell_t.npy")); c_ = np.load(os.path.join(d, "a", "punkte_farben_t.npy"))
        if len(k_) != len(X) - b["entfernt_punkte"] or len(c_) != len(k_): fehler.append("FEHLER CLI: Kopie/Farben passen nicht zum Bericht")
        if len(np.load(w)) != len(X): fehler.append("FEHLER CLI: Original veraendert")
        if not os.path.getsize(os.path.join(d, "k.jpg")): fehler.append("FEHLER CLI: kein Kontrollbild")
# Kette: Stufe 'draehte' vor 'html', html nimmt die gefilterte Kopie
src = open(os.path.join(T, "gesamtkette.py")).read(); ST = eval(re.search(r"^STUFEN = (\[.*\])", src, re.M).group(1))
if "draehte" not in ST or ST.index("draehte") != ST.index("html") - 1: fehler.append("FEHLER Kette: Stufe 'draehte' fehlt direkt vor 'html'")
if "wolke_draehte.py" not in src or "W_ANZ" not in src: fehler.append("FEHLER Kette: html zeigt nicht die gefilterte Kopie (W_ANZ)")
print(json.dumps(info.get("fahnen")), json.dumps(info.get("angebunden")))
print("\n".join(fehler) if fehler else f"OK wolke_draehte: {info['entfernt_punkte']} entfernt, {len(info['zuege'])} Zuege, {len(info.get('fahnen', []))} Fahnen")
sys.exit(1 if fehler else 0)

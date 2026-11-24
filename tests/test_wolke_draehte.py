#!/usr/bin/env python3
"""test_wolke_draehte.py - Draht-/Fahnenfilter der dichten Wolke (tools/wolke_draehte.py), Anlass 24.11.2026 Nutzerbefund schwabentor-1122:
Oberleitung/Spanndraehte als diagonale Linien und als schmale schraege Blaetter ("Fahnen") vor der Nordseite.

Synthetisch (Meter, z oben): Wand x=0 mit Gesims, angebundenem schmalem Pultdach (Vordach) und Dach oben, lotrechte Wetterstange auf dem First,
freier Draht (schraeg) und freie Fahne (Draht als 0,8-m-Band verschmiert, schraege Ebene). ROT-PROBE: Wand, Gesims, Vordach, Dach, Stange bleiben
(<= 1 %); Draht und Fahne gehen (>= 85 %). FREIRAUM (Sichtbarkeit, Koordinator 24.11.): lotrechte Fahne vor der Wand mit Kameras davor -> weg
(die Fahnenstufe schuetzt lotrechte Blaetter, nur die Strahlen nehmen sie); 2,5 m tiefer Erker vor der Wand -> bleibt, weil er die Wand in den
Fotos wirklich verdeckt. Dazu: Kettenstufe 'draehte' steht vor 'html' und html zeigt die gefilterte Kopie.
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
# FREIRAUM (Sichtbarkeit): Wand x=0 mit 2,5 m tiefem Erker (undurchsichtig), davor eine LOTRECHTE Fahne parallel zur Wand (die Fahnenstufe schuetzt
# lotrechte Blaetter - nur der Freiraum-Test darf sie nehmen). Kameras vor der Wand aus verschiedenen Richtungen; ein SfM-Punkt gilt als gesehen,
# wenn der Strahl Kamera -> Punkt den Erker nicht schneidet (die Fahne ist ein Phantom und verdeckt nichts).
E0, E1 = np.array([0.0, 3.0, 3.0]), np.array([2.5, 6.0, 7.0])
def im_erker(Pt): return np.all((Pt > E0 - 1e-6) & (Pt < E1 + 1e-6), axis=1)
erker = np.vstack([flaeche([2.5, 3, 3], [0, 3, 0], [0, 0, 4]), flaeche([0, 3, 3], [2.5, 0, 0], [0, 0, 4]), flaeche([0, 6, 3], [2.5, 0, 0], [0, 0, 4]),
                   flaeche([0, 3, 7], [2.5, 0, 0], [0, 3, 0])])
wand2 = flaeche([0, -2, 0], [0, 14, 0], [0, 0, 10]); wand2 = wand2[~((wand2[:, 1] > 3) & (wand2[:, 1] < 6) & (wand2[:, 2] > 3) & (wand2[:, 2] < 7))]
fahne2 = flaeche([4.0, 0, 8.2], [0, 9, 0], [0, 0, 0.8], rausch=0.02)
teile2 = {"wand": wand2, "erker": erker, "fahne_lotrecht": fahne2}
X2 = np.vstack(list(teile2.values())); lab2 = np.concatenate([[k] * len(v) for k, v in teile2.items()])
Ck = np.array([[x_, y_, z_] for x_ in (10.0, 16.0) for y_ in (-6.0, 0.0, 4.5, 9.0, 15.0) for z_ in (1.6, 10.0)])
Pq = np.vstack([wand2, erker])[rng.choice(len(wand2) + len(erker), 8000, replace=False)]
op, oc = [], []
for ci, c in enumerate(Ck):
    d_ = Pq - c; tt = np.linspace(0.02, 0.98, 200)                                      # Verdeckung durch den Erker (Abtastung des Strahls)
    vis = ~np.array([im_erker(c + np.outer(tt[tt * np.linalg.norm(dd) < np.linalg.norm(dd) - 0.08], dd)).any() for dd in d_])
    vis &= (Pq[:, 0] > 0.05) | (c[0] > 0)                                               # Wand von vorn
    op += list(np.flatnonzero(vis)); oc += [ci] * int(vis.sum())
sicht = dict(P=Pq.astype(np.float32), C=Ck.astype(np.float32), obs_p=np.array(op, np.int32), obs_c=np.array(oc, np.int32))
entf2, info2 = WD.draht_maske(X2, workers=2, sicht=sicht)
for k, soll_weg in (("wand", False), ("erker", False), ("fahne_lotrecht", True)):
    a = float(entf2[lab2 == k].mean()); print(f"  freiraum {k:15s} entfernt {100 * a:5.1f} %  ({'soll weg' if soll_weg else 'soll bleiben'})")
    if soll_weg and a < 0.85: fehler.append(f"FEHLER Freiraum {k}: nur {100 * a:.1f} % entfernt (Kameras sehen die Wand durch sie hindurch)")
    if not soll_weg and a > 0.01: fehler.append(f"FEHLER Freiraum {k}: {100 * a:.1f} % entfernt - verdeckt die Wand wirklich (Rot-Probe)")
if info2.get("fahnen"): fehler.append("FEHLER: lotrechte Fahne schon von der Fahnenstufe genommen - Freiraum-Test nicht geprueft")
with tempfile.TemporaryDirectory() as d:                                              # CLI mit --sicht; Rahmen-Gegenprobe schaltet falschen Rahmen ab
    w = os.path.join(d, "punkte_modell_s.npy"); np.save(w, X2)
    for abw, soll in ((0.004, True), (0.5, False)):
        np.savez(os.path.join(d, "sicht.npz"), kamera_abweichung_m=np.float32(abw), **sicht)
        r = subprocess.run([sys.executable, "-I", os.path.join(T, "wolke_draehte.py"), w, "--aus", os.path.join(d, "a"), "--sicht", os.path.join(d, "sicht.npz"), "--workers", "2"],
                           capture_output=True, text=True)
        b = json.load(open(os.path.join(d, "a", "wolke_draehte.json"))) if not r.returncode else {}
        if r.returncode or (b.get("freiraum_voxel", 0) > 0) != soll: fehler.append(f"FEHLER CLI --sicht (Abweichung {abw} m): rc {r.returncode}, freiraum_voxel {b.get('freiraum_voxel')}, {b.get('freiraum_aus', '')}")
# Kette: Stufe 'draehte' vor 'html', html nimmt die gefilterte Kopie
src = open(os.path.join(T, "gesamtkette.py")).read(); ST = eval(re.search(r"^STUFEN = (\[.*\])", src, re.M).group(1))
if "draehte" not in ST or ST.index("draehte") != ST.index("html") - 1: fehler.append("FEHLER Kette: Stufe 'draehte' fehlt direkt vor 'html'")
if "--sicht_export" not in src or '"--sicht", si_' not in src: fehler.append("FEHLER Kette: Freiraum-Test (Sicht-Export + --sicht) nicht in der Stufe draehte")
if "wolke_draehte.py" not in src or "W_ANZ" not in src: fehler.append("FEHLER Kette: html zeigt nicht die gefilterte Kopie (W_ANZ)")
print(json.dumps(info.get("fahnen")), json.dumps(info.get("angebunden")))
print("\n".join(fehler) if fehler else f"OK wolke_draehte: {info['entfernt_punkte']} entfernt, {len(info['zuege'])} Zuege, {len(info.get('fahnen', []))} Fahnen")
sys.exit(1 if fehler else 0)

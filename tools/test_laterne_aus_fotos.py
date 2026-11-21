#!/usr/bin/env python3
"""test_laterne_aus_fotos.py - feste synthetische Tests fuer tools/laterne_aus_fotos.py und bauteile.laterne (22.11.2026). Ohne Dateien, Sekunden.

Anlass: Schwabentor-1120 - spitze_aus_umriss.py baute die Laterne als runde Zwiebel; querschnitt() kannte nur Quadrat gegen Kreis, ein Achteck schwankt in der
Silhouette nur um 8 % und 16 von 17 Fotos lagen in 25 Grad Blickrichtung. Jetzt Eckenzahl aus den Kanten IM INNEREN der Silhouette.
A) Offene Pfosten: Quadrat (n 4) und Achteck (n 8) aus Fotos in NUR 25 Grad Blickrichtung -> richtige Eckenzahl, Umkreis auf 5 cm (Achteck darf beim Quadrat nicht gewinnen).
B) Geschlossene facettierte Haube (Helligkeitsstufen je Facette, duenne Naehte als Stoerung): Achteck aus 8 Fotos ueber 60 Grad -> n 8; gespiegelte Bilder -> n 8 + 'gespiegelt'.
C) Formfamilie: Zwiebel / gerade Pyramide / geschweift; Zonen aus einem synthetischen Breitenprofil (Pfosten, Krempe, Taille, Bauch, Hals, Knauf).
D) bauteile.laterne: 4 offene Pfosten (Schnitt in Pfostenhoehe = 4 Teile), ein zusammenhaengender Koerper bis zur Nadel; Pfosten unter dem Druckmindestmass -> geschlossener
   Koerper (Schnitt = 1 Teil); laterne_aus_block: unentschiedene Haube -> Eckenzahl der Pfosten + ANNAHME."""
import sys, os, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import laterne_aus_fotos as LA

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

rng = np.random.default_rng(7)
X = np.arange(-1.5, 1.5, 0.01)

# ---- A: offene Pfosten -----------------------------------------------------------------------------------------------------------------------
def pfosten_bild(n, phase, R, b, az, rausch=0.05):
    s = np.zeros_like(X)
    for x in LA.ecken_x(n, phase, az, R)[0]: s = np.maximum(s, (np.abs(X - x) <= b / 2).astype(float))
    return np.clip(s + rng.normal(0, rausch, len(X)), 0, 1)

for n_w, ph_w in ((4, 87.0), (8, 10.0)):
    R_w, b_w = 0.7, 0.15; beob = []
    for az in np.linspace(-23, 1, 9):
        s = pfosten_bild(n_w, ph_w, R_w, b_w, az)
        e = LA.ausdehnung(s, X); beob.append(dict(az=float(az), x=X, s=s, c=(e[0] + e[1]) / 2, h=(e[1] - e[0]) / 2))
    E, n, ab = LA.ecken_bewerten(beob, offen=True, n_kand=(3, 4, 6, 8, 12), phase_schritt=2.0)
    R = E[n]["R_anteil"] * float(np.median([B["h"] for B in beob]))
    dph = abs(((E[n]["phase"] - ph_w) + 180.0 / n) % (360.0 / n) - 180.0 / n) if n == n_w else 99
    pruef(n == n_w and (E[n]["t"] >= LA.MIN_T or n_w > 4), f"A Pfosten {n_w}-Eck aus 25 Grad Blickrichtung: gefunden {n} (t {E[n]['t']}, Abstand {ab}, Kandidaten " + " ".join(f"{k}:{v['kontrast']:.2f}" for k, v in E.items()) + ")")
    pruef(abs(R - R_w) < 0.05 and dph < 5, f"A Pfosten {n_w}-Eck: Umkreis {R:.3f} (soll {R_w}), Lage {E[n]['phase']} (soll {ph_w} mod {360 / n_w:g}, Abweichung {dph:.1f})")

# ---- B: geschlossene facettierte Haube -------------------------------------------------------------------------------------------------------
def haube_bild(n, phase, az, licht=(0.3, 0.9), naehte=True, rausch=1.0):
    """Helligkeit quer: je sichtbarer Facette konstant (Lambert gegen eine Lichtrichtung in der Ebene), Himmel 250; Naehte = duenne dunkle Linien in Facettenmitte."""
    R = 1.2; xe, ve = LA.ecken_x(n, phase, az, R); I = np.full_like(X, 250.0); L = np.array(licht) / np.linalg.norm(licht)
    a = np.radians(phase + np.arange(n) * 360.0 / n); b = math.radians(az)
    for k in range(n):
        k2 = (k + 1) % n; am = (a[k] + a[k2]) / 2 + (math.pi if k2 == 0 else 0)
        nrm = np.array([math.cos(am), math.sin(am)]); cam = np.array([math.cos(b), math.sin(b)])
        if nrm @ cam <= 0: continue
        x0, x1 = sorted((xe[k], xe[k2])); hell = 60 + 120 * (0.5 + 0.5 * float(nrm @ L))       # Himmelslicht (halbes Lambert): jede Facette eigene Helligkeit
        sel = (X >= x0) & (X <= x1); I[sel] = hell
        if naehte: I[np.abs(X - (x0 + x1) / 2) < 0.012] -= 25
    return I + rng.normal(0, rausch, len(X))

def haube_beob(n, phase, azs, spiegel=False):
    out = []
    for az in azs:
        I = haube_bild(n, phase, az)
        if spiegel: I = I[::-1].copy()
        s = LA.dunkelheit(I); e = LA.ausdehnung(s, X); st = LA.stufe(I, X, LA.STUFE_W_M); inn = (X > e[0] + LA.STUFE_W_M) & (X < e[1] - LA.STUFE_W_M)
        st = np.where(inn, (st - st[inn].mean()) / max(st[inn].std(), 1e-6), 0.0) / 10.0
        out.append(dict(az=float(az), x=X, s=st, c=(e[0] + e[1]) / 2, h=(e[1] - e[0]) / 2))
    return out

azs = np.linspace(-30, 30, 8)
E, n, ab, ds = LA.ecken_bewerten_beide(haube_beob(8, 5.0, azs), offen=False, n_kand=(4, 6, 8, 12), phase_schritt=2.0)
pruef(n == 8 and ds == "kameras", f"B Haube Achteck (Stufen + Naehte) aus 60 Grad: {n}-Eck, Drehsinn {ds}, Abstand {ab} (" + " ".join(f"{k}:{v['kontrast']:.2f}" for k, v in E.items()) + ")")
E, n, ab, ds = LA.ecken_bewerten_beide(haube_beob(8, 5.0, azs, spiegel=True), offen=False, n_kand=(4, 6, 8, 12), phase_schritt=2.0)
pruef(n == 8 and ds == "gespiegelt", f"B gespiegelte Bilder: {n}-Eck, Drehsinn {ds} (soll 8 / gespiegelt - Hinweis auf Seitenverwechslung)")
E, n, ab, ds = LA.ecken_bewerten_beide(haube_beob(4, 20.0, azs), offen=False, n_kand=(4, 6, 8, 12), phase_schritt=2.0)
pruef(n == 4, f"B Haube Quadrat: {n}-Eck (soll 4), Abstand {ab}")

# ---- C: Formfamilie + Zonen ------------------------------------------------------------------------------------------------------------------
zz = np.linspace(0, 2, 21)
zw = [(z, 1.0 + 0.3 * math.sin(math.pi * z / 1.4) if z < 1.4 else 1.0 * (2 - z) / 0.6 * 0.5 + 0.05) for z in zz]
ge = [(z, 1.2 - 0.55 * z) for z in zz]
gs = [(z, 0.1 + 1.1 * (1 - z / 2) ** 2) for z in zz]
pruef(LA.familie_aus_profil(zw) == "zwiebel" and LA.familie_aus_profil(ge) == "gerade" and LA.familie_aus_profil(gs) == "geschweift",
      f"C Familie: Zwiebel {LA.familie_aus_profil(zw)}, Pyramide {LA.familie_aus_profil(ge)}, geschweift {LA.familie_aus_profil(gs)}")
def r_syn(z):
    if z < 0.3: return 1.4 - z                     # Dachfirst unten im Profil (breiter)
    if z < 2.0: return 0.78                        # Pfosten
    if z < 2.4: return 1.30 - 0.2 * (z - 2.0)      # Krempe
    if z < 2.8: return 1.22 - 0.15 * (z - 2.4)     # Taille
    if z < 5.6: return 1.16 + 0.12 * math.sin(math.pi * (z - 2.8) / 2.4) if z < 4.0 else max(0.14, 1.16 - (z - 4.0) * 0.65)
    if z < 6.2: return 0.14 + 0.08 * math.sin(math.pi * (z - 5.6) / 0.6)   # Knauf
    return 0.03
P = [[round(z, 2), r_syn(z), 5] for z in np.arange(0, 7.0, 0.05)]
Z = LA.zonen_aus_profil(P)
pruef(Z is not None and abs(Z["z_pfosten_oben"] - 2.0) < 0.1 and abs(Z["r_pfosten_silh"] - 0.78) < 0.02 and abs(Z["z_krempe"] - 2.0) < 0.15 and 3.2 < Z["z_bauch"] < 4.0
      and 5.3 < Z["z_hals"] < 5.7 and 5.7 < Z["z_knauf"] < 6.1 and abs(Z["r_knauf"] - 0.22) < 0.02,
      "C Zonen: " + (" ".join(f"{k} {v:.2f}" for k, v in Z.items() if k != "i") if Z else "None"))

# ---- D: Bauteil -----------------------------------------------------------------------------------------------------------------------------
import bauteile as BT
haube = [(49.2, 1.15), (49.6, 1.22), (50.0, 1.26), (50.5, 1.2), (51.0, 0.95), (51.5, 0.55), (52.0, 0.16)]
kw = dict(achse=(1.0, -2.0), n=4, phase_grad=87.0, r_pfosten=0.73, b_pfosten=0.15, z_fuss=46.6, z_pfosten_oben=48.4, krempe=dict(z_kante=48.8, r_kante=1.3),
          haube=haube, knauf=(52.35, 0.2), nadel=(53.8, 0.03))
k, h = BT.laterne(**kw)
bb = k.bounding_box(); n_sch = len(k.slice(47.5).decompose()); n_k = len(k.decompose())
pruef(k.volume() > 0 and n_k == 1 and n_sch == 4 and abs(bb[5] - 53.8) < 0.03 and bb[2] < 46.6,
      f"D Laterne 4 offene Pfosten: Teile {n_k}, Schnitt z 47,5 {n_sch} Pfosten, oben {bb[5]:.2f} (soll 53,8), unten {bb[2]:.2f}; Hinweise {h}")
k2, h2 = BT.laterne(**dict(kw, b_pfosten=0.05))
pruef(len(k2.slice(47.5).decompose()) == 1 and len(k2.decompose()) == 1 and any("ANNAHME" in x for x in h2),
      f"D Pfosten 5 cm < 7 cm Druckmindestmass -> geschlossener Koerper (Schnitt {len(k2.slice(47.5).decompose())} Teil), Hinweis {h2[:1]}")
k3, _ = BT.laterne(**dict(kw, n=8, n_haube=8, phase_haube=0.0))
pruef(len(k3.slice(47.5).decompose()) == 8 and len(k3.decompose()) == 1, f"D Achteck-Laterne: {len(k3.slice(47.5).decompose())} Pfosten im Schnitt, {len(k3.decompose())} Koerper")
LF = dict(gueltig=True, achse=[1.0, -2.0], z_fuss=46.6, pfosten=dict(n=4, phase=87.0, R=0.73, breite=0.15, silh_faktor=1.0),
          haube=dict(n=5, phase=10.0, eindeutig=False, abstand=0.01), zonen=dict(z_pfosten_unten=46.6, z_pfosten_oben=48.4, z_krempe=48.8, r_krempe=1.3, z_taille=49.2,
          z_hals=52.0, z_knauf=52.35, r_knauf=0.2, r_hals=0.16), profil=[[z, r, 5] for z, r in haube], nadel_z=None)
pb = BT.laterne_aus_block(LF, dict(spitze_z=53.4))
pruef(pb is not None and pb[0]["n_haube"] == 4 and "ANNAHME" in pb[1] and pb[0]["nadel"][0] == 53.4 and pb[0]["knauf"] == (52.35, 0.2),
      f"D laterne_aus_block: Haube unentschieden -> {pb[0]['n_haube'] if pb else None}-Eck wie Pfosten ({pb[1][:40] if pb else ''}...), Nadel aus spitze_foto {pb[0]['nadel'] if pb else None}")
pruef(BT.laterne_aus_block(dict(LF, gueltig=False)) is None, "D ungueltiger Block -> None (Generator baut wie bisher)")

# Generator: Wolkendach bis zum Laternenfuss + Block laterne_foto -> bauteile.laterne statt Drehringen (ein Koerper, 4 Pfosten im Schnitt, bis zur Nadel)
import json, tempfile
from manifold3d import Manifold as M
AX = [1.0, -2.0]; prof = [[round(z, 2), -h, h, -h, h, 500, []] for z in np.arange(40.0, 46.0, 0.5) for h in [3.0 - (3.0 - 0.8) * (z - 40.0) / 6.0]]
SFb = dict(gueltig=True, achse=AX, spitze_z=53.4, hals_halb=0.8, wolke_ende_z=46.0, profil=[[round(z, 2), 0.8, 9, 0.01] for z in np.arange(46.0, 48.4, 0.1)] + [[48.5, 1.3, 9, 0.01]])
with tempfile.TemporaryDirectory() as td:
    pj = os.path.join(td, "dach_profil.json")
    json.dump(dict(o=AX, d=[1, 0], n=[0, 1], z0=40.0, schritt=0.5, wand_halb=[3, 3], scheiben=prof, spitze_foto=SFb, laterne_foto=dict(LF, nadel_z=53.8)), open(pj, "w"))
    kg, bel = BT.dach_aus_profil(M.cube((6, 6, 40)).translate((AX[0] - 3, AX[1] - 3, 0)), pj)
    zt = kg.bounding_box()[5]; ns = len(kg.slice(47.5).decompose())
    pruef(abs(zt - 53.8) < 0.05 and len(kg.decompose()) == 1 and ns == 4 and any("Laterne aus Fotokanten" in b["element"] for b in bel),
          f"Generator dach_aus_profil + laterne_foto: oben {zt:.2f} (Nadel 53,8), Koerper {len(kg.decompose())}, Schnitt z 47,5: {ns} Pfosten, Beleg {[b['element'][:40] for b in bel if 'Laterne' in b['element']]}")

print(("FEHLER " if fehler else "OK ") + f"test_laterne_aus_fotos: {len(fehler)} Fehler"); sys.exit(1 if fehler else 0)

#!/usr/bin/env python3
"""test_putz_uhr.py - fester synthetischer Test (21.11.2026, Nutzerbild schwabentor-1120 umgang_bau_ansicht: Kruemel auf dem Putz, Uhr nur flacher Kreis) fuer
  (1) putz_wandbild.glatt_karte/putz_auf_relief: Putz = mehrere Einzelfotos einig glatt; Kabel (je Foto woanders) bleibt Putz, Quaderfeld (alle Fotos Struktur) nicht;
  (2) putz_wandbild.relief_putz_glatt: Kruemel auf dem Putz weg (ein Niveau), Gesims ausserhalb des Putzes bleibt, Uhrkreis 'frei' auf Niveau, putz_niveau_m gesetzt;
  (3) fassaden_kette.uhren_frei: Uhr der passenden Fassade im Relief-Raster, fremde Fassade nicht;
  (4) uhren_wandbild.druckbar + zifferblatt_aus_fotos: Goldstriche aus der Mehrheit der Einzelfotos, duenne Striche >= 0,8 mm (H0), Hoehen Feld/Ring/Gold;
  (5) bauteile.uhren_aus_json mit Zifferblatt-Datei: Relief sitzt auf der gemessenen Wand (Wandversatz), Gold steht vor dem Ring, ein Stueck mit dem Koerper.
Werte sind Testgeometrie, kein Objektmass. < 20 s."""
import os, sys, json, tempfile
import numpy as np, cv2
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import putz_wandbild as PW, fassaden_kette as FK, uhren_wandbild as UW

fehler = []
def pruef(b, t):
    if not b: fehler.append(t)

T = temp_ordner("test_putz_uhr_"); FF = os.path.join(T, "fassade_fein"); os.makedirs(os.path.join(FF, "ortho_f00_einzeln"))
# Fassade f00: Ebene x = 0, u entlang +y, Normale +x; Raster 1 cm, u -1..5, z 10..0 (Zeile 0 oben)
c = 0.01; R = dict(u0=-1.0, z1=10.0, nu=600, nz=1000, zelle=c)
json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], raster=R)]), open(os.path.join(FF, "fassaden.json"), "w"))
uu = R["u0"] + (np.arange(R["nu"]) + 0.5) * c; zz = R["z1"] - (np.arange(R["nz"]) + 0.5) * c; UU, ZZ = np.meshgrid(uu, zz)
rng = np.random.default_rng(3)
# Uhr: Mitte u 2, z 7, Durchmesser 2 m (innen 1,3); Ring schwarz, Feld blau, 12 goldene Ziffernstriche (radial, 3 cm breit = 0,34 mm H0 -> muss verbreitert werden)
uc, zc, ra, ri = 2.0, 7.0, 1.0, 0.65; rr = np.hypot(UU - uc, ZZ - zc); phi = np.arctan2(UU - uc, ZZ - zc)
def foto(k):
    g = np.full((R["nz"], R["nu"], 3), 200, np.uint8) + rng.integers(-1, 2, (R["nz"], R["nu"], 1)).astype(np.uint8)      # glatter Putz (hell, minimales Rauschen)
    q = (UU > -0.8) & (UU < 0.5) & (ZZ > 0.5) & (ZZ < 4.0)                 # Quaderfeld: Fugenraster (alle Fotos)
    g[q] = (150 + rng.normal(0, 25, (q.sum(), 1))).clip(0, 255).astype(np.uint8); g[q & ((np.mod(ZZ, 0.35) < 0.02) | (np.mod(UU + 0.1 * (np.floor(ZZ / 0.35) % 2), 0.6) < 0.02))] = 60
    g[(ZZ > 4.4) & (ZZ < 4.6) & (UU > 1.0) & (UU < 4.0)] = 90              # Gesims: dunkles Band (alle Fotos)
    kab = np.abs(ZZ - (2.0 + 0.6 * k) - 0.3 * UU) < 0.012; g[kab & (UU > 1.0)] = 30      # Kabel: in jedem Foto woanders
    g[rr <= ra] = (40, 35, 30); g[rr <= ri] = (160, 110, 60)                # BGR: Ring dunkel, Feld blau
    for n_ in range(12):
        a_ = np.radians(30 * n_); d_ = np.abs(np.sin(phi - a_)) * rr
        g[(d_ < 0.015) & (rr > ri + 0.05) & (rr < ra - 0.05) & (np.cos(phi - a_) > 0)] = (40, 200, 230)     # Gold (BGR)
    ze = (np.abs(np.sin(phi - np.radians(40 * k))) * rr < 0.02) & (rr < 0.55) & (np.cos(phi - np.radians(40 * k)) > 0); g[ze] = (40, 200, 230)   # Zeiger: je Foto andere Zeit
    M_ = np.float32([[1, 0, 3 * k - 4], [0, 1, 2 - k]]); return cv2.warpAffine(g, M_, (R["nu"], R["nz"]), borderValue=(0, 0, 0))       # Einzelbilder gegeneinander versetzt
for k in range(4): cv2.imwrite(os.path.join(FF, "ortho_f00_einzeln", f"foto{k}.png"), foto(k))

# --- (1) Putzkarte
K = PW.glatt_karte(FF, "f00"); pruef(K is not None, "glatt_karte: keine Karte")
if K:
    P = K["putz"]; z5 = R["z1"] - (np.arange(P.shape[0]) + 0.5) * K["zelle"]; u5 = R["u0"] + (np.arange(P.shape[1]) + 0.5) * K["zelle"]
    def anteil(ua, ub, za, zb): return float(P[np.ix_((z5 > za) & (z5 < zb), (u5 > ua) & (u5 < ub))].mean())
    pruef(anteil(1.2, 4.5, 1.0, 4.2) > 0.9, f"Putz mit Kabeln nicht als Putz erkannt ({anteil(1.2, 4.5, 1.0, 4.2):.2f})")
    pruef(anteil(-0.6, 0.3, 0.8, 3.7) < 0.1, f"Quaderfeld als Putz ({anteil(-0.6, 0.3, 0.8, 3.7):.2f})")
    # ein einfarbiges Gesims sieht im Bild wie Putz aus - es bleibt ueber die Reliefregel (zusammenhaengender Koerper im Netz), Pruefung in (2)

# --- (2) Relief einer Putzwand (wie relief_roh: Niveau = 'vorstand' 0,11, Loecher = 0,11): Kruemel auf dem Putz, Gesims, Uhr
px = 0.05; Hn, Wn = 200, 100; rel = np.full((Hn, Wn), 0.11, np.float32); zr = (Hn - 1 - np.arange(Hn) + 0.5) * px; ur = (np.arange(Wn) + 0.5) * px      # Relief-u; Fassaden-u = Relief-u - 0,5 (a = (0, -0,5))
Ur, Zr = np.meshgrid(ur, zr); kr = rng.random((Hn, Wn)) < 0.08; kk = kr & (Ur > 1.5); rel[kk] += rng.choice([-0.09, 0.08, 0.12], kk.sum())
ges = (Zr > 4.4) & (Zr < 4.6) & (Ur > 1.5) & (Ur < 4.5); rel[ges] = 0.25
Zd = dict(rel=rel, a=np.array([0.0, -0.5]), t=np.array([0.0, 1.0]), n=np.array([1.0, 0.0]), u0=0.0, z0=0.0, px=px, oeffnung=np.zeros((Hn, Wn), bool), wand=np.ones((Hn, Wn), bool), loch=np.zeros((Hn, Wn), bool))
f_in = os.path.join(T, "w00_voll.npz"); np.savez_compressed(f_in, **Zd)
M = PW.putz_auf_relief(np.load(f_in), FF); pruef(M is not None and M.shape == rel.shape, "putz_auf_relief: keine Maske")
od = os.path.join(T, "obj"); os.makedirs(os.path.join(od, "audit"))
json.dump(dict(f00=dict(o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], uhren=[dict(u=uc, z=zc, d_aussen=2 * ra, d_innen=2 * ri)]), f01=dict(o=[5.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], uhren=[dict(u=1.0, z=7.0, d_aussen=1.0)])),
          open(os.path.join(od, "audit", "uhren_auto.json"), "w"))
fr = FK.uhren_frei(od, np.load(f_in)); pruef(len(fr) == 1 and abs(fr[0][0] - 2.5) < 1e-6 and abs(fr[0][1] - 7.0) < 1e-6, f"uhren_frei falsch: {fr} (erwartet u 2,5 im Relief, nur f00)")
if M is not None:
    f_out = os.path.join(T, "w00_glatt.npz"); info = PW.relief_putz_glatt(f_in, f_out, M, frei=fr); Zg = np.load(f_out); g = Zg["rel"]
    p_ = (Ur > 1.7) & (Ur < 4.8) & (Zr > 1.0) & (Zr < 4.2) & ~ges
    pruef(float(np.abs(g[p_] - 0.11).max()) < 1e-4, f"Kruemel auf dem Putz nicht weg (max {np.abs(g[p_] - 0.11).max():.3f} m)")
    pruef(float(g[ges].mean()) > 0.2, f"Gesims weggeglaettet ({g[ges].mean():.3f})")
    uh = np.hypot(Ur - 2.5, Zr - 7.0) < 0.9; pruef(float(np.abs(g[uh] - 0.11).max()) < 1e-4, "Uhrfeld nicht frei (Netz-Relief vor der Uhr)")
    pruef(abs(float(Zg["putz_niveau_m"]) - 0.11) < 1e-3, "putz_niveau_m fehlt/falsch")

# --- (4) druckbar + Zifferblatt
m = np.zeros((60, 60), bool); m[10:50, 30] = True; m[5, 5] = True; d = UW.druckbar(m, 0.02)
pruef(d[30, 27:34].sum() * 0.02 >= 0.0696 - 1e-9, f"duenner Strich nicht auf 0,8 mm verbreitert ({d[30].sum() * 0.02:.3f} m)"); pruef(not d[5, 5], "Einzelfleck nicht entfernt")
zb = os.path.join(od, "audit", "uhr_f00_0.npz")
J = json.load(open(os.path.join(od, "audit", "uhren_auto.json"))); J.pop("f01")
n = UW.zifferblaetter(od, FF, J); pruef(n == 1 and os.path.exists(zb), "zifferblaetter: kein Zifferblatt geschrieben")
if os.path.exists(zb):
    Z = np.load(zb); r_ = Z["rel"]; p2 = float(Z["px"]); N = r_.shape[0]; g_ = (np.arange(N) + 0.5) * p2 - N * p2 / 2; X, Y = np.meshgrid(g_, -g_); rr2 = np.hypot(X, Y); ph2 = np.arctan2(X, Y)
    ziff = (rr2 > ri + 0.08) & (rr2 < ra - 0.08); auf = ziff & (np.abs(np.sin(ph2)) * rr2 < 0.021) & (Y > 0); zw = ziff & (np.abs(np.sin(ph2 - np.radians(15))) * rr2 < 0.021) & (np.cos(ph2 - np.radians(15)) > 0)
    pruef(float(np.median(r_[auf])) > 0.15, f"Ziffernstrich 12 Uhr nicht erhaben (Median {np.median(r_[auf]):.3f} m)")
    pruef(float(np.median(r_[zw])) < 0.12, f"zwischen den Ziffern erhaben ({np.median(r_[zw]):.3f} m)")
    pruef(abs(float(np.median(r_[(rr2 < ri - 0.1) & (rr2 > 0.3)])) - 0.06) < 0.005, "Innenfeld nicht auf 6 cm")
    J["f00"]["o"] = [0.0, 0.0]; json.dump(J, open(os.path.join(od, "audit", "uhren_auto.json"), "w"))
    # --- (5) Bau: Wand um -0,15 m versetzt (Abweichungsschleife), Zifferblatt auf der gemessenen Wand
    json.dump(dict(korrekturen=[dict(art="wandversatz", fassade="f00", w_soll=-0.15)]), open(os.path.join(od, "audit", "schleife_korrekturen.json"), "w"))
    import bauteile as B
    from manifold3d import Manifold as Mf
    kp = Mf.cube((3.0, 6.0, 10.0)).translate((-3.15, -1.0, 0.0))            # Koerper: Wandflaeche bei x = -0,15
    k2, bel = B.uhren_aus_json(kp, os.path.join(od, "audit", "uhren_auto.json"))
    pruef(len(k2.decompose()) == 1, f"Uhr nicht verbunden ({len(k2.decompose())} Stuecke)"); pruef(any("Zifferblatt-Relief" in b_["element"] for b_ in bel), "Beleg Zifferblatt fehlt")
    bb = k2.bounding_box(); pruef(abs(bb[3] - (-0.15 + 0.10 + 0.07 + 0.005)) < 0.02, f"Vorderkante Gold {bb[3]:.3f} statt -0,15 + 0,175")
    sl = (k2 ^ Mf.cube((1.0, 0.02, 0.02)).translate((-0.5, uc - 0.01, zc + ra - 0.2))).bounding_box()           # Ziffer XII (oben im Ring)
    sl2 = (k2 ^ Mf.cube((1.0, 0.02, 0.02)).translate((-0.5, uc + 0.197, zc + 0.763))).bounding_box()            # zwischen XII und I im Ring (15 Grad, r 0,8)
    pruef(sl[3] > sl2[3] + 0.05, f"Ziffer nicht hoeher als der Ring daneben ({sl[3]:.3f} / {sl2[3]:.3f})")

print("FEHLER: " + " | ".join(fehler) if fehler else "ALLE BESTANDEN (Putz aus Wandbild, Kruemel weg, Gesims bleibt, Uhr frei, Zifferblatt aus Einzelfotos, druckbar, Bau auf gemessener Wand)")
sys.exit(1 if fehler else 0)

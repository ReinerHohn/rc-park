#!/usr/bin/env python3
"""test_rund_kranz.py - fester synthetischer Test: KRANZ eines Rundkoerpers (rund_aus_umriss.kranz_messen / kranz_einbauen), 24.11.2026.
Verwandt: tools/test_rund_aus_umriss.py (Zylinder), tools/test_kegeldach_rund.py (Kegeldach). Vorlaeufer: Befund Hoehen-Angleich 1122 (modelle/FEATURE_FORMSITZ.md:110).
Anlass: Schwabentor 1122 Rundturm - Traufe z 12,75 aus der Silhouette (Auskragungs-Falle, Rezept L31), Kranz im Modell 0,75 m dick statt ~0,45; Fotokanten und Wolke
setzen die Kranz-Oberkante 0,75-0,84 m tiefer. Szene: Schaft r 1,5 bis z 8,0, KRANZ r 2,0 von z 8,00 bis 8,45 (auskragend 0,5 m), darauf Aufsatz r 1,5 bis 9,6;
14 Kameras rundum TIEF (1,6-3,6 m, 11-15 m Abstand: tan(Blickhoehe) ~0,4-0,6), Bilder analytisch gerendert.
 ROT:  alter Weg (Silhouetten-Profil, vermessen + traufe) liest den Kranz zu hoch/zu dick (Geister-Kranz ueber der Oberkante).
 A: Fotokanten (Ober- + Unterkante als Ringe, dazu senkrechte Wandkante, Fuge in EINEM Sektor, Streupunkte) + Wolke -> Kanten gelten (+-5 cm), Dicke +-0,08.
 B: Fotokanten nur Oberkante -> Unterkante aus der Wolken-Flaechenmitte (+-8 cm).
 C: weder Kanten noch Wolke -> Silhouette mit L31-Rueckrechnung (Oberkante naeher an der Wahrheit als alt, ANNAHME im Audit).
 D: Guard: Kanten nur Stoerer, Wolke ohne Kranz, keine Blickhoehe -> gueltig False, Profil unveraendert (alter Weg protokolliert).
 E: Generator (bauteile.drehkoerper_aus_wolkenrest) baut den Kranz aus dem neuen Profil auf der gemessenen Hoehe; wolke_ausschnitt (npy, Rahmenverschiebung).
Ohne Objektdaten, < 60 s, CPU."""
import sys, os, math, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, rund_aus_umriss as RU, flaeche_ortho as FO

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

CX, CY, RS, RK, ZU, ZO, RA, ZA = 0.3, -0.2, 1.5, 2.0, 8.0, 8.45, 1.5, 9.6
W, Hh, F = 480, 640, 520.0
rng = np.random.default_rng(5)


def kamera(az, d, h, ziel_z=7.0):
    C = np.array([CX + d * math.cos(az), CY + d * math.sin(az), h]); zv = np.array([CX, CY, ziel_z]) - C; zv /= np.linalg.norm(zv)
    xv = np.cross(zv, [0, 0, 1.0]); xv /= np.linalg.norm(xv); yv = np.cross(zv, xv); Rm = np.stack([xv, yv, zv]); t = -Rm @ C
    return dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=t.tolist(), f_px=F, cx=W / 2, cy=Hh / 2, k1=0.0), C, Rm


def render(C, Rm):
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(Hh) + 0.5); d = np.stack([(u - W / 2) / F, (v - Hh / 2) / F, np.ones_like(u)], -1) @ Rm
    ox, oy, oz = C[0] - CX, C[1] - CY, C[2]; a = d[..., 0] ** 2 + d[..., 1] ** 2; b = 2 * (ox * d[..., 0] + oy * d[..., 1])
    T = np.full(u.shape, np.inf); G = np.zeros(u.shape)
    def zyl(r, z0, z1, grau):
        c = ox * ox + oy * oy - r * r; disc = b * b - 4 * a * c; t = (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a); z = oz + t * d[..., 2]
        ok = (disc > 0) & (t > 0) & (z >= z0) & (z <= z1) & (t < T); T[ok] = t[ok]; G[ok] = grau
    def ring(z, r0, r1, grau):
        t = (z - oz) / np.where(np.abs(d[..., 2]) < 1e-9, 1e-9, d[..., 2]); rr = np.hypot(ox + t * d[..., 0], oy + t * d[..., 1])
        ok = (t > 0) & (rr >= r0) & (rr <= r1) & (t < T); T[ok] = t[ok]; G[ok] = grau
    zyl(RS, 0.0, ZU, 205); zyl(RK, ZU, ZO, 220); ring(ZU, RS, RK, 160); ring(ZO, RA, RK, 190); zyl(RA, ZO, ZA, 205); ring(ZA, 0.0, RA, 215)   # weisser Putz, Untersicht im Schatten
    hinter = 60 + 40 * (np.floor(u / 21) % 2) + 25 * np.sin(v / 13)
    return np.clip(np.where(np.isinf(T), hinter, G) + rng.normal(0, 5, u.shape), 0, 255).astype(np.uint8)


def kranz_im_profil(P, r_mid):
    """Kranz so, wie der Generator ihn aus dem Profil lofted: Hoehen, an denen r die Mitte Schaft/Kranz kreuzt (linear zwischen den Profilhoehen) -> (unten, oben)."""
    zs = [p[0] for p in P]; rs = [p[1] for p in P]; ku = ko = None
    for (z0, r0), (z1, r1) in zip(zip(zs[:-1], rs[:-1]), zip(zs[1:], rs[1:])):
        if r0 < r_mid <= r1 and ku is None: ku = z0 + (z1 - z0) * (r_mid - r0) / max(r1 - r0, 1e-9)
        if r0 >= r_mid > r1: ko = z0 + (z1 - z0) * (r0 - r_mid) / max(r0 - r1, 1e-9)
    return ku, ko


# ---- Silhouette messen (wie main: vermessen -> bereinigen/glaetten -> traufe) ----
bilder = []
for i in range(14):
    c, C, Rm = kamera(2 * math.pi * i / 14 + 0.2, 11 + 2 * (i % 3), 1.6 + (i % 3) * 1.0)
    B = RU.Bild(c, render(C, Rm), (0, 0, W, Hh), FO.projektion); B.Cxy = C[:2]; B.C = C; bilder.append(B)
zs = list(np.round(np.arange(0.75, ZA + 1.0, 0.5), 2))
U = RU.vermessen(bilder, (CX + 0.2, CY - 0.1, 1.7), zs, log=lambda *a: None)
P = RU.glaetten(RU.profil_bereinigen(U["profil"], 1.7)[0]); r_s = float(np.median([p[1] for p in P[:len(P) // 2]])); z_t = RU.traufe(P, 0.5)
print("  Profil z:r " + " ".join(f"{p[0]:g}:{p[1]:.2f}" for p in P) + f"  Schaft {r_s:.3f}, Silhouetten-Traufe {z_t}")
pruef(abs(r_s - RS) < 0.05 and z_t is not None, f"Silhouette: Schaft r {r_s:.3f} (Soll {RS}), Traufe {z_t} gefunden")
r_mid = 0.5 * (RS + RK); ku0, ko0 = kranz_im_profil(P, r_mid)
alt_fehler = max(abs((ko0 or 99) - ZO), abs(((ko0 or 99) - (ku0 or 0)) - (ZO - ZU)))
pruef(ko0 is not None and alt_fehler > 0.25, f"ROT alter Weg: Kranz im Profil z {ku0 and round(ku0, 2)}..{ko0 and round(ko0, 2)} (Soll {ZU}..{ZO}), Fehler {alt_fehler:.2f} m > 0,25 (Auskragungs-Falle sichtbar)")

# ---- synthetische Fotokanten (wie kanten/sweep.npz) und Wolke ----
def bogen(r, z, a0, a1, n, sz=0.02, sr=0.02):
    a = np.radians(rng.uniform(a0, a1, n)); rr = r + rng.normal(0, sr, n)
    return np.c_[CX + rr * np.cos(a), CY + rr * np.sin(a), z + rng.normal(0, sz, n)]
stoer = [np.c_[CX + 2.25 * math.cos(math.radians(300)) + rng.normal(0, 0.02, 200), CY + 2.25 * math.sin(math.radians(300)) + rng.normal(0, 0.02, 200), rng.uniform(6, 10, 200)],   # senkrechte Wandkante
         bogen(2.2, 7.3, 300, 318, 60),                                                                    # waagrechte Fuge am Nachbarbau: EIN Sektor
         np.c_[CX + rng.uniform(-3, 3, 400), CY + rng.uniform(-3, 3, 400), rng.uniform(6, 10, 400)]]       # Streupunkte
KP_oben = bogen(RK, ZO, 0, 200, 150); KP_unten = bogen(RK, ZU, 30, 170, 80)
KP_A = np.vstack([KP_oben, KP_unten] + stoer); KP_B = np.vstack([KP_oben] + stoer); KP_D = np.vstack(stoer)

def flaeche_zyl(r, z0, z1, n, a0=0, a1=270):
    return bogen(r, 0, a0, a1, n, sz=0, sr=0.03) + np.c_[np.zeros(n), np.zeros(n), rng.uniform(z0, z1, n)]
DW = 0.08                                                                                                  # Wolke misst runde Teile dicker
unten_ = np.c_[CX + (rr_ := np.sqrt(rng.uniform((RS + DW) ** 2, (RK + DW) ** 2, 3000))) * np.cos(aa_ := np.radians(rng.uniform(0, 270, 3000))), CY + rr_ * np.sin(aa_), ZU + rng.normal(0, 0.02, 3000)]
wand = np.c_[np.full(4000, CX - 2.6) + rng.normal(0, 0.03, 4000), CY + rng.uniform(-3, 3, 4000), rng.uniform(5, 11, 4000)]
W_kranz = np.vstack([flaeche_zyl(RS + DW, 5.5, ZU, 12000), flaeche_zyl(RK + DW, ZU, ZO, 4000), unten_, flaeche_zyl(RA + DW, ZO, ZA, 5000), wand])
W_ohne = np.vstack([flaeche_zyl(RS + DW, 5.5, ZA, 20000), wand])
tb = RU.tan_blickhoehe(bilder, CX, CY, 8.2)
pruef(tb is not None and 0.3 < tb < 0.8, f"tan(Blickhoehe) der Fotos {tb:.2f}")
still = lambda *a: None

# ---- A: Kanten + Wolke ----
KA = RU.kranz_messen(P, r_s, U["x"], U["y"], 0.5, z_t, KP=KP_A, W=W_kranz, tan_blick=tb, log=still); print("  Wolke A:", KA.get("wolke"))
pruef(KA.get("gueltig") and KA.get("quelle_oberkante") == "kanten" and KA.get("quelle_unterkante") == "kanten", f"A gueltig, Quellen {KA.get('quelle_oberkante')}/{KA.get('quelle_unterkante')} ({KA.get('grund')})")
pruef(KA.get("gueltig") and abs(KA["z_oberkante"] - ZO) <= 0.05 and abs(KA["z_unterkante"] - ZU) <= 0.05 and abs(KA["dicke"] - (ZO - ZU)) <= 0.08,
      f"A Kranz z {KA.get('z_unterkante')}..{KA.get('z_oberkante')} Dicke {KA.get('dicke')} (Soll {ZU}..{ZO}, {ZO - ZU:.2f}); Wolke oben {KA.get('oberkanten', {}).get('wolke')}, einig {KA.get('einig')}")
pruef(abs(KA.get("r", 0) - RK) <= 0.1, f"A Radius aus der Silhouette {KA.get('r')} (Soll {RK})")
# ---- B: Kanten nur Oberkante -> Unterkante aus der Wolke ----
KB = RU.kranz_messen(P, r_s, U["x"], U["y"], 0.5, z_t, KP=KP_B, W=W_kranz, tan_blick=tb, log=still)
pruef(KB.get("gueltig") and KB.get("quelle_unterkante") == "wolke" and abs(KB["z_unterkante"] - ZU) <= 0.08 and abs(KB["z_oberkante"] - ZO) <= 0.05,
      f"B Unterkante aus der Wolke {KB.get('z_unterkante')} (Soll {ZU}), Oberkante {KB.get('z_oberkante')} ({KB.get('quelle_oberkante')})")
# ---- C: nur Silhouette -> L31-Rueckrechnung ----
KC = RU.kranz_messen(P, r_s, U["x"], U["y"], 0.5, z_t, KP=None, W=None, tan_blick=tb, log=still)
pruef(KC.get("gueltig") and KC.get("quelle_oberkante") == "silhouette_l31" and abs(KC["z_oberkante"] - ZO) < abs((ko0 or 99) - ZO) and bool(KC.get("annahmen")),
      f"C L31: Oberkante {KC.get('z_oberkante')} (alt im Profil {ko0 and round(ko0, 2)}, Soll {ZO}), Korrektur {KC.get('l31')}, ANNAHME im Audit ({KC.get('grund')})")
# ---- D: Guard ----
KD = RU.kranz_messen(P, r_s, U["x"], U["y"], 0.5, z_t, KP=KP_D, W=W_ohne, tan_blick=None, log=still)
pruef(not KD.get("gueltig") and KD.get("fallback") and RU.kranz_einbauen(P, KD) == P, f"D Guard: nur Stoerer -> gueltig False, alter Weg ({KD.get('grund')}), Profil unveraendert")
pruef(not RU.kranz_messen([[z, RS, 9, .4] for z in zs], RS, CX, CY, 0.5, None, KP=KP_A, W=W_kranz, log=still).get("gueltig"), "D Guard: ohne Ueberstands-Zone kein Kranz")
# ---- E: Generator + Wolkenausschnitt ----
import bauteile as BT, pfade
from manifold3d import Manifold as M
td = pfade.temp_ordner("test_rund_kranz_")
Pn = RU.kranz_einbauen(P, KA); ku1, ko1 = kranz_im_profil(Pn, r_mid)
pruef(ku1 is not None and ko1 is not None and abs(ko1 - ZO) <= 0.06 and abs(ku1 - ZU) <= 0.06, f"neues Profil: Kranz z {ku1 and round(ku1, 2)}..{ko1 and round(ko1, 2)} (alt {ku0 and round(ku0, 2)}..{ko0 and round(ko0, 2)})")
def bau(prof):
    p = os.path.join(td, "koerper_auto.json"); json.dump(dict(haufen=[dict(form="rund", kreis=dict(x=CX, y=CY, r=RS, rest=0.02), profil=[[q[0], q[1], 50] for q in prof], punkte=1000, mass_quelle="foto_umriss", umriss=dict(start_wolke=dict(r=1.7)))]), open(p, "w"))
    return BT.drehkoerper_aus_wolkenrest(M(), p)[0]
def r_bei(k, z):
    s = k.slice(z); return (s.bounds()[2] - s.bounds()[0]) / 2 if not s.is_empty() else 0.0
kn, ka = bau(Pn), bau(P)
pruef(abs(r_bei(kn, ZU + 0.2) - RK) < 0.12 and r_bei(kn, ZO + 0.15) < r_mid and r_bei(kn, ZU - 0.1) < r_mid and kn.genus() == 0,
      f"Generator neu: r bei z {ZU - 0.1:.2f}/{ZU + 0.2:.2f}/{ZO + 0.15:.2f} = {r_bei(kn, ZU - 0.1):.2f}/{r_bei(kn, ZU + 0.2):.2f}/{r_bei(kn, ZO + 0.15):.2f} (Soll Schaft/Kranz/Aufsatz), wasserdicht")
pruef(r_bei(ka, ZO + 0.15) > r_mid, f"ROT Generator alt: r bei z {ZO + 0.15:.2f} = {r_bei(ka, ZO + 0.15):.2f} (Geister-Kranz ueber der Oberkante gebaut)")
npy = os.path.join(td, "wolke.npy"); np.save(npy, (W_kranz + [0, 0, 0.126]).astype(np.float32))
Wa = RU.wolke_ausschnitt(npy, [0, 0, 0.126], CX, CY, 2.5, 7.0, 9.0, block=7000)
pruef(len(Wa) > 1000 and abs(float(Wa[:, 2].min()) - 7.0) < 0.01 and float(np.abs(Wa[:, :2] - [CX, CY]).max()) <= 2.5 + 1e-6, f"wolke_ausschnitt: {len(Wa)} Punkte, Rahmenverschiebung abgezogen, Zylinder/Fenster eingehalten")
# ---- F: Ende-zu-Ende main() auf einem synthetischen Objektordner (Kameras K-*.json, Fotos, koerper_auto.json, --kanten, --wolke mit Rahmenverschiebung) ----
od = os.path.join(td, "obj"); os.makedirs(os.path.join(od, "messprotokoll")); os.makedirs(os.path.join(od, "audit")); os.makedirs(os.path.join(od, "fotos"))
for i in range(14):
    c, C, Rm = kamera(2 * math.pi * i / 14 + 0.2, 11 + 2 * (i % 3), 1.6 + (i % 3) * 1.0); c = dict(c, rahmen_verschiebung=[0.0, 0.0, 0.126])
    # Kamera sieht den Kamerarahmen (STL + 0,126): t so verschieben, dass die gerenderte Szene im STL-Rahmen bleibt
    cv2.imwrite(os.path.join(od, "fotos", f"syn_{i:02d}.png"), render(C, Rm)); c["t"] = (np.asarray(c["t"]) - Rm @ np.array([0, 0, 0.126])).tolist()
    json.dump(dict(kamera=c), open(os.path.join(od, "messprotokoll", f"K-syn_{i:02d}.json"), "w"))
json.dump(dict(name="syn", fotos_dir=os.path.join(od, "fotos")), open(os.path.join(od, "objekt.json"), "w"))
def ka_schreiben():
    json.dump(dict(haufen=[dict(id="r0", form="rund", kreis=dict(x=CX + 0.2, y=CY - 0.1, r=1.7), kasten=[CX - 2, CY - 2, 0.5, CX + 2, CY + 2, 8.0], punkte=1000)]), open(os.path.join(od, "audit", "koerper_auto.json"), "w"))
kpn = os.path.join(td, "sweep.npz"); np.savez(kpn, P=KP_A.astype(np.float32))
ka_schreiben(); rc_neu = RU.main([os.path.join(od, "objekt.json"), "--uebernehmen", "--kanten", kpn, "--wolke", npy, "--max-fotos", "14"])
Hn = json.load(open(os.path.join(od, "audit", "koerper_auto.json")))["haufen"][0]
ka_schreiben(); RU.main([os.path.join(od, "objekt.json"), "--uebernehmen", "--ohne-kranz", "--max-fotos", "14"])
Ha = json.load(open(os.path.join(od, "audit", "koerper_auto.json")))["haufen"][0]
Kf = (Hn.get("umriss") or {}).get("kranz") or {}
pruef(rc_neu == 0 and Kf.get("gueltig") and Kf.get("quelle_oberkante") == "kanten" and abs(float(Hn.get("traufe") or 0) - ZO) <= 0.06,
      f"F main(): Traufe {Hn.get('traufe')} (Soll {ZO}, alter Weg {Ha.get('traufe')}), Kranz {Kf.get('z_unterkante')}..{Kf.get('z_oberkante')} ({Kf.get('quelle_oberkante')}/{Kf.get('quelle_unterkante')}), "
      f"Wolke oben {Kf.get('oberkanten', {}).get('wolke')} (Rahmen 0,126 abgezogen)")
kuF, koF = kranz_im_profil(Hn.get("profil") or [], r_mid)
pruef(koF is not None and abs(koF - ZO) <= 0.06 and (Ha.get("umriss") or {}).get("kranz", {}).get("fallback"), f"F Profil im Objekt: Kranz z {kuF and round(kuF, 2)}..{koF and round(koF, 2)}; --ohne-kranz = alter Weg protokolliert")
try: json.dumps(dict(A=KA, B=KB, C=KC, D=KD)); js = True
except Exception as e: js = str(e)
pruef(js is True, f"Audit-Block kranz ist JSON-faehig ({js})")
print("alle Tests bestanden" if not fehler else f"{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)

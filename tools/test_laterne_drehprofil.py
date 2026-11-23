#!/usr/bin/env python3
"""test_laterne_drehprofil.py - Haube der Laterne als DREHKOERPER aus Silhouetten (tools/laterne_aus_fotos.py: Sehstrahl-Huelle, Registrierung, Querschnitt), 23.11.2026.

Anlass: Kette 1122r, neben_detail_laterne.jpg - Foto: Zwiebelhaube mit Einschnuerung, Knauf, Nadel; Modell: Kasten. Ursache: das Median-Breitenprofil je Hoehe
war von der Taille bis zum Bauch flach, weil in Fotos von schraeg unten (bis 55 Grad) die breite Krempe als Ellipse bis ~1 m ueber ihre Hoehe in die Taillen-Zeilen
ragt; dazu Kameralagen je Foto +-0,5 m in der Hoehe versetzt und Grauwert-Silhouetten vor tiefblauem Himmel zu schmal.
Vorgespielte Silhouetten (Vorwaertsabbildung von Drehkoerpern in Kameras rund um die Achse, Hoehenwinkel 8..55 Grad (die Taille direkt ueber der Krempe sehen nur flache Blicke - K_HUELLE = 3 braucht 3 davon), Hoehen-/Seitenversatz je Foto, ein Foto mit
abgeschnittener Haube, ein Foto mit Fremdkoerper an einer Seite):
 A) ZWIEBEL rund mit Krempe: Huelle trifft Taille/Bauch/Hals (+-8 %), Familie 'zwiebel', Querschnitt 'rund' als ANNAHME (richtungsunabhaengig), Knauf gefunden;
    ROT-PROBE: Median der Halbbreiten (alter Weg) sieht die Taille nicht (Bauch/Taille < 1,15).
 B) KASTEN (Quadrat-Prisma, oben flach) aus Richtungen ueber 60 Grad: Querschnitt 'n-eck' 4 aus der Synthese, Familie nicht 'zwiebel'.
 C) KEGEL rund: Familie 'gerade', Querschnitt rund.
 D) bauteile.laterne_aus_block nimmt Huelle + Querschnitt (rund -> N_RUND-Eck, Profil = Huelle); laterne() baut einen Koerper, Bauch breiter als Taille."""
import sys, os, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import laterne_aus_fotos as LA

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

rng = np.random.default_rng(3)
A = np.array([10.0, 20.0]); ZG = np.round(np.arange(46.0, 53.5, 0.05), 3)
Z_KREMPE = 48.0


def zwiebel(z):
    """Krempe (r 1,35, z 47,95..48,05) -> Taille 0,8 (bis 48,35) -> Bauch 1,15 (z 49,0) -> Hals 0,08 (z 51,0) -> Knauf 0,2 (z 51,4) -> Nadel 0,03 bis 52,4."""
    z = np.asarray(z, float); r = np.zeros_like(z)
    r[(z >= 46.5) & (z < 47.95)] = 0.7
    r[(z >= 47.95) & (z <= 48.05)] = 1.35
    r[(z > 48.05) & (z <= 48.35)] = 0.8
    h = (z > 48.35) & (z <= 49.0); r[h] = 0.8 + 0.35 * np.sin((z[h] - 48.35) / 0.65 * math.pi / 2)
    h = (z > 49.0) & (z <= 51.0); t = (z[h] - 49.0) / 2.0; r[h] = 0.08 + 1.07 * (1 - t) ** 1.6 * (1 - 0.35 * np.sin(t * math.pi))
    h = (z > 51.0) & (z <= 51.6); r[h] = np.maximum(0.08, np.sqrt(np.clip(0.2 ** 2 - (z[h] - 51.4) ** 2, 0, None)))
    h = (z > 51.6) & (z <= 52.4); r[h] = 0.03
    return r


def kasten(z):
    z = np.asarray(z, float); r = np.zeros_like(z); r[(z >= 46.5) & (z < 47.95)] = 0.7; r[(z >= 47.95) & (z <= 48.05)] = 1.35; r[(z > 48.05) & (z <= 50.5)] = 1.0; return r


def kegel(z):
    z = np.asarray(z, float); r = np.zeros_like(z); r[(z >= 46.5) & (z < 47.95)] = 0.7; r[(z >= 47.95) & (z <= 48.05)] = 1.35
    h = (z > 48.05) & (z <= 51.0); r[h] = 1.1 * (51.0 - z[h]) / 2.95 + 0.02; return r


def fotos(profil, n=None, phase=0.0, azs=(-20, -5, 10, 25, 160, 175, 190, 205, 95), els=(8, 30, 45, 55, 12, 50, 15, 40, 50), versatz=True, stoerung=True, d=40.0):
    """Vorwaertsabbildung: je Kamera die Silhouette (l, r je Zeile) des Drehkoerpers profil (Querschnitt Kreis/n-Eck), mit Hoehenversatz +-0,4 m und Seitenversatz +-0,2 m
    (Kameralage-Fehler), Rauschen 1 cm; Foto 1 mit abgeschnittener Haube (helles Blech), Foto 3 mit Fremdkoerper rechts."""
    zf = np.arange(46.5, 52.45, 0.01); rf = profil(zf); quer = LA.querschnitt_einheit(n, phase); out = []
    for i, (az, el) in enumerate(zip(azs, els)):
        u = np.array([math.cos(math.radians(az)), math.sin(math.radians(az))]); C = np.r_[A + d * u, 48.5 - d * math.tan(math.radians(el))]
        B = dict(C=C, az=float(az), A0=A, zg=ZG, nr=f"syn{i}")
        l, r = LA.silhouette_vorhersage(B, A, zf, rf, quer, dz=0.01)
        dz = rng.uniform(-0.4, 0.4) if versatz else 0.0; dx = rng.uniform(-0.2, 0.2) if versatz else 0.0
        l = np.interp(ZG, ZG + dz, l, left=np.nan, right=np.nan) + dx + rng.normal(0, 0.01, len(ZG)); r = np.interp(ZG, ZG + dz, r, left=np.nan, right=np.nan) + dx + rng.normal(0, 0.01, len(ZG))
        if stoerung and i == 1: k = ZG > 49.6 + dz; l[k] = np.nan; r[k] = np.nan                       # obere Haube hell vor hellem Himmel -> fehlt
        if stoerung and i == 3: k = (ZG > 48.8 + dz) & (ZG < 49.6 + dz); r[k] += 0.5                     # Nachbardach rechts hinter der Haube
        halb = {float(z): (float(a), float(b)) for z, a, b in zip(ZG, l, r) if np.isfinite(a) and np.isfinite(b)}
        out.append(dict(nr=f"syn{i}", az=float(az), C=[float(v) for v in C], halb=halb, halb_f=halb))
    return out


def median_profil(fs, zs):
    P = []
    for z in zs:
        v = [(F["halb"][float(z)][1] - F["halb"][float(z)][0]) / 2 for F in fs if float(z) in F["halb"]]
        if len(v) >= 3: P.append([float(z), float(np.median(v)), len(v)])
    return P


def lauf(fs):
    zs = ZG[ZG >= 46.6]; P = median_profil(fs, zs); Z = LA.zonen_aus_profil(P)
    HB, HZ = LA.haube_huelle(fs, A, zs, P, Z)
    return P, Z, HB, HZ


# ---- A: Zwiebel ------------------------------------------------------------------------------------------------------------------------------
fs = fotos(zwiebel)
P, Z0, HB, HZ = lauf(fs)
pruef(HZ is not None, f"A Zwiebel: Zonen aus der Huelle gefunden ({None if HZ is None else {k: round(v, 2) for k, v in HZ.items() if k != 'i'}})")
if HZ:
    soll = dict(r_taille=0.8, r_bauch=1.15, z_bauch=49.0, z_hals=51.0, r_knauf=0.2, z_knauf=51.4)
    pruef(abs(HZ["r_bauch"] - 1.15) < 0.08 * 1.15 and abs(HZ["r_taille"] - 0.8) < 0.12, f"A Zwiebel: Bauch r {HZ['r_bauch']:.2f} (soll 1,15), Taille r {HZ['r_taille']:.2f} (soll 0,80)")
    pruef(abs(HZ["z_bauch"] - 49.0) < 0.3 and abs(HZ["z_hals"] - 51.0) < 0.3, f"A Zwiebel: Bauch z {HZ['z_bauch']:.2f} (soll 49,0), Hals z {HZ['z_hals']:.2f} (soll 51,0)")
    pruef(abs(HZ["z_knauf"] - 51.4) < 0.25 and 0.12 < HZ["r_knauf"] < 0.3, f"A Zwiebel: Knauf z {HZ['z_knauf']:.2f} r {HZ['r_knauf']:.2f} (soll 51,4 / 0,20)")
    sel = (HB["zh"] >= HZ["z_taille"]) & (HB["zh"] <= HZ["z_hals"])
    fam = LA.familie_aus_profil([(float(z), float(v)) for z, v in zip(HB["zh"][sel], HB["r"][sel])])
    pruef(fam == "zwiebel", f"A Zwiebel: Familie aus der Huelle {fam}")
    pruef("syn1" in HB["weg"] or HZ["r_bauch"] > 1.05, f"A Zwiebel: Foto mit abgeschnittener Haube schnuert die Huelle nicht ein (raus {list(HB['weg'])}, Bauch {HZ['r_bauch']:.2f})")
    Q = LA.querschnitt_haube(HB["beob"], A, HB["zh"], (HZ["z_taille"], HZ["z_hals"]), HZ["r_bauch"], n_kand=(3, 4, 6, 8), phase_schritt=10.0, n_fallback=4)
    pruef(Q["art"] == "rund" and Q["annahme"] and "ANNAHME" in Q["annahme"], f"A Zwiebel: Querschnitt {Q['art']} {Q.get('n')} ({Q['quelle']}; Kandidaten {Q['kandidaten']})")
# ROT-PROBE: alter Weg (Median der Halbbreiten) - Bauch kaum breiter als die Taille
zm = [p for p in P if 48.1 <= p[0] <= 51.0]; rm = np.array([p[1] for p in zm]); zz = np.array([p[0] for p in zm])
rt = float(rm[(zz >= 48.1) & (zz <= 48.4)].min()); rb = float(rm.max())
pruef(rb / rt < 1.15, f"A ROT-PROBE Median-Profil: Bauch/Taille {rb / rt:.2f} (Wahrheit 1,44) - Krempe verdeckt die Taille, alter Weg baut den Kasten")

# ---- B: Kasten (Quadrat) ---------------------------------------------------------------------------------------------------------------------
fs = fotos(kasten, n=4, phase=20.0, stoerung=False)
P, Z0, HB, HZ = lauf(fs)
pruef(HB is not None, "B Kasten: Huelle gerechnet")
if HB is not None:
    zb = (48.2, 50.4)
    Q = LA.querschnitt_haube(HB["beob"], A, HB["zh"], zb, 1.0, n_kand=(3, 4, 6, 8), phase_schritt=5.0, n_fallback=8)
    dph = abs(((Q.get("phase") or 0) - 20.0 + 45.0) % 90.0 - 45.0)
    pruef(Q["art"] == "n-eck" and Q["n"] == 4 and Q["quelle"].startswith("Silhouetten") and dph <= 10, f"B Kasten: Querschnitt {Q['art']} {Q.get('n')} Lage {Q.get('phase')} (soll 4-Eck, 20 Grad) ({Q['quelle']}; Kandidaten {Q['kandidaten']})")
    r4, _, _ = LA.drehprofil(HB["beob"], A, HB["zh"], 4, Q.get("phase") or 0.0); sel = (HB["zh"] >= 48.3) & (HB["zh"] <= 50.3)
    fam = LA.familie_aus_profil([(float(z), float(v)) for z, v in zip(HB["zh"][sel], LA.glaetten(r4)[sel])])
    pruef(fam != "zwiebel" and abs(float(np.median(r4[sel])) - 1.0) < 0.1, f"B Kasten: Familie {fam}, Umkreis Median {float(np.median(r4[sel])):.2f} (soll 1,00)")

# ---- C: Kegel --------------------------------------------------------------------------------------------------------------------------------
fs = fotos(kegel, stoerung=False)
P, Z0, HB, HZ = lauf(fs)
if HB is not None:
    sel = (HB["zh"] >= 48.2) & (HB["zh"] <= 50.8)
    fam = LA.familie_aus_profil([(float(z), float(v)) for z, v in zip(HB["zh"][sel], HB["r"][sel])])
    Q = LA.querschnitt_haube(HB["beob"], A, HB["zh"], (48.2, 50.8), 1.0, n_kand=(3, 4, 6, 8), phase_schritt=10.0, n_fallback=4)
    pruef(fam in ("gerade", "geschweift") and fam != "zwiebel" and Q["art"] == "rund", f"C Kegel: Familie {fam}, Querschnitt {Q['art']} (Kandidaten {Q['kandidaten']})")
else: pruef(False, "C Kegel: keine Huelle")

# ---- D: Bauteil ------------------------------------------------------------------------------------------------------------------------------
try:
    import bauteile as BT
    fs = fotos(zwiebel); P, Z0, HB, HZ = lauf(fs)
    LF = dict(gueltig=True, achse=[float(A[0]), float(A[1])], z_fuss=46.6, profil=P, zonen={k: v for k, v in HZ.items() if k != "i"},
              pfosten=dict(n=4, phase=0.0, R=0.6, breite=0.15, silh_faktor=1.0), haube=dict(n=4, phase=0.0, eindeutig=False),
              haube_huelle=dict(querschnitt=dict(art="rund", n=None, phase=0.0, annahme="ANNAHME: Haube rund (Test)", quelle="Test"),
                                profil=[[float(z), float(v), 3] for z, v in zip(HB["zh"], HB["r"])], bindende_fotos=["a", "b", "c"], familie="zwiebel"))
    lp, hq = BT.laterne_aus_block(LF)
    hb = lp["haube"]; rr = [p[1] for p in hb]
    pruef(lp["n_haube"] == BT.N_RUND and "ANNAHME: Haube rund" in hq, f"D laterne_aus_block: Haube {lp['n_haube']}-Eck ({hq[:80]})")
    pruef(max(rr) > 1.25 * rr[0] and rr[-1] < 0.3 * max(rr), f"D laterne_aus_block: Profil Taille {rr[0]:.2f} -> Bauch {max(rr):.2f} -> Hals {rr[-1]:.2f} (Zwiebel)")
    k, hin = BT.laterne(**lp)
    lo, hi = np.array(k.bounding_box()[:3]), np.array(k.bounding_box()[3:])
    pruef(k.volume() > 0 and abs((hi[0] - lo[0]) / 2 - 1.35) < 0.3, f"D laterne(): Koerper Volumen {k.volume():.2f} m3, halbe Breite {(hi[0] - lo[0]) / 2:.2f} (Krempe 1,35)")
except ImportError as e:
    print("    (D uebersprungen: kein manifold3d/bauteile in dieser Umgebung:", e, ")")

print(f"\n{len(fehler)} FEHLER" if fehler else "\nalle Laterne-Drehprofil-Tests bestanden")
sys.exit(1 if fehler else 0)

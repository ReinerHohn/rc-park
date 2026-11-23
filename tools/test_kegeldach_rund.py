#!/usr/bin/env python3
"""test_kegeldach_rund.py - fester synthetischer Test fuer das KEGELDACH auf Rundkoerpern (rund_aus_umriss.kegeldach + bauteile.kegeldach_teile), 23.11.2026.
Anlass: Kettenlauf 1122o (Schwabentor) baute das weisse Treppentuermchen als nackten, oben offenen Zylinder - das Kegeldach fehlte (drehkoerper_aus_wolkenrest: 'oben flach').
A) Zylinder r 1,5 m bis Traufe 8 m, Kegeldach mit Ueberstand r 1,8 m, Spitze z 10,4 m (Neigung ~53 Grad), hell vor dunkel gestreiftem Hintergrund, 12 Kameras rundum (Boden/1. Stock),
   Bilder analytisch per Strahlschnitt gerendert. Soll: Spitze auf 0,2 m, Traufradius auf 0,1 m, gueltig.
B) ROT-PROBE: derselbe Zylinder OHNE Dach (oben flach) -> kein gueltiger Kegel (Suchrand/keine Einigkeit), nichts erfunden.
C) Generator: Rundkoerper mit gueltigem Block -> Koerper bis Spitze (Kegelstumpf mit Druckradius), Traufbrett >= 0,8 mm in H0, wasserdicht; ungueltiger Block -> flach wie bisher.
Ohne Dateien ausser pfade.temp_ordner, < 60 s."""
import sys, os, math, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, rund_aus_umriss as RU, flaeche_ortho as FO

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

CX, CY, R, ZT, RE, ZS = 0.3, -0.2, 1.5, 8.0, 1.8, 10.4
W, Hh, F = 480, 640, 520.0
rng = np.random.default_rng(2)


def kamera(az, d, h, ziel_z=6.0):
    C = np.array([CX + d * math.cos(az), CY + d * math.sin(az), h]); zv = np.array([CX, CY, ziel_z]) - C; zv /= np.linalg.norm(zv)
    xv = np.cross(zv, [0, 0, 1.0]); xv /= np.linalg.norm(xv); yv = np.cross(zv, xv); Rm = np.stack([xv, yv, zv]); t = -Rm @ C
    return dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=t.tolist(), f_px=F, cx=W / 2, cy=Hh / 2, k1=0.0), C, Rm


def render(C, Rm, dach=True):
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(Hh) + 0.5); d = np.stack([(u - W / 2) / F, (v - Hh / 2) / F, np.ones_like(u)], -1) @ Rm
    ox, oy, oz = C[0] - CX, C[1] - CY, C[2]
    # Zylinder
    a = d[..., 0] ** 2 + d[..., 1] ** 2; b = 2 * (ox * d[..., 0] + oy * d[..., 1]); c = ox * ox + oy * oy - R * R; disc = b * b - 4 * a * c
    t1 = (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a); z1 = oz + t1 * d[..., 2]; hit1 = (disc > 0) & (t1 > 0) & (z1 > 0) & (z1 < ZT)
    t1 = np.where(hit1, t1, np.inf)
    # Deckel (flach, nur ohne Dach) bzw. Kegel
    if dach:
        k = RE / (ZS - ZT); w0 = ZS - oz
        a2 = a - k * k * d[..., 2] ** 2; b2 = b + 2 * k * k * w0 * d[..., 2]; c2 = ox * ox + oy * oy - k * k * w0 * w0; disc2 = b2 * b2 - 4 * a2 * c2; t2 = np.full(u.shape, np.inf)
        for sg in (-1, 1):
            tt = (-b2 + sg * np.sqrt(np.maximum(disc2, 0))) / (2 * np.where(np.abs(a2) < 1e-12, 1e-12, a2)); zz = oz + tt * d[..., 2]
            ok = (disc2 >= 0) & (tt > 0) & (zz >= ZT) & (zz <= ZS); t2 = np.where(ok & (tt < t2), tt, t2)
        # Unterseite des Ueberstands (Ring r R..RE bei ZT)
        tu = (ZT - oz) / np.where(np.abs(d[..., 2]) < 1e-9, 1e-9, d[..., 2]); rx = ox + tu * d[..., 0]; ry = oy + tu * d[..., 1]; rr = np.hypot(rx, ry)
        t3 = np.where((tu > 0) & (rr <= RE) & (rr >= R), tu, np.inf)
    else:
        tu = (ZT - oz) / np.where(np.abs(d[..., 2]) < 1e-9, 1e-9, d[..., 2]); rr = np.hypot(ox + tu * d[..., 0], oy + tu * d[..., 1])
        t2 = np.where((tu > 0) & (rr <= R), tu, np.inf); t3 = np.full(u.shape, np.inf)
    tmin = np.minimum(np.minimum(t1, t2), t3)
    hinter = 60 + 40 * (np.floor(u / 21) % 2) + 25 * np.sin(v / 13)
    img = np.where(np.isinf(tmin), hinter, np.where(tmin == t1, 205, np.where(tmin == t2, 150 if dach else 215, 120)))
    return np.clip(img + rng.normal(0, 5, u.shape), 0, 255).astype(np.uint8)


def bilder_fuer(dach):
    out = []
    for i in range(12):
        c, C, Rm = kamera(2 * math.pi * i / 12 + 0.15, 13 + 3 * (i % 3), 1.6 + (i % 2) * 4.0)
        B = RU.Bild(c, render(C, Rm, dach), (0, 0, W, Hh), FO.projektion); B.Cxy = C[:2]; B.C = C; out.append(B)
    return out


# ---- A: Kegeldach messen ----
K = RU.kegeldach(bilder_fuer(True), CX, CY, ZT, R)
pruef(bool(K.get("gueltig")), f"Kegel gueltig ({K.get('grund')}), Fotos {K.get('fotos')}, einig {K.get('einig')}")
pruef(K.get("z_spitze") is not None and abs(K["z_spitze"] - ZS) <= 0.2, f"Spitze z {K.get('z_spitze')} (Soll {ZS} +- 0,2)")
pruef(K.get("r_traufe") is not None and abs(K["r_traufe"] - RE) <= 0.1, f"Traufradius {K.get('r_traufe')} (Soll {RE} +- 0,1)")
# ---- B: Rot-Probe ohne Dach ----
K0 = RU.kegeldach(bilder_fuer(False), CX, CY, ZT, R, log=lambda *a: None)
pruef(not K0.get("gueltig"), f"Zylinder ohne Dach: kein Kegel erfunden ({K0.get('grund')}; Spitze {K0.get('z_spitze')})")
# ---- C: Generator ----
import bauteile as BT, pfade
from manifold3d import Manifold as M
td = pfade.temp_ordner("test_kegeldach_rund_")
prof = [[round(z, 2), R, 50] for z in np.arange(0.25, ZT + 1.5, 0.5)]
def bau(dach):
    p = os.path.join(td, "koerper_auto.json"); json.dump(dict(haufen=[dict(form="rund", kreis=dict(x=CX, y=CY, r=R, rest=0.02), profil=prof, punkte=1000, dach=dach, mass_quelle="foto_umriss", umriss={})]), open(p, "w"))
    return BT.drehkoerper_aus_wolkenrest(M(), p)
k, bel = bau(K if K.get("gueltig") else dict(gueltig=True, z_traufe=ZT, r_traufe=RE, z_spitze=ZS, neigung_grad=53))
bb = k.bounding_box(); dmin = 0.8 * 87 / 1000.0
z_soll = (K.get("z_spitze") or ZS) - ((K.get("z_spitze") or ZS) - ZT) * (0.5 * dmin / (K.get("r_traufe") or RE))
pruef(abs(bb[5] - z_soll) < 0.02, f"Generator: Koerper bis z {bb[5]:.2f} (Kegelstumpf bis {z_soll:.2f}, Spitzenradius {0.5 * dmin:.3f} m = Druckmass)")
s_brett = k.slice(ZT - 0.5 * dmin); s_unter = k.slice(ZT - 1.5 * dmin)
r_brett = (s_brett.bounds()[2] - s_brett.bounds()[0]) / 2 if not s_brett.is_empty() else 0; r_unter = (s_unter.bounds()[2] - s_unter.bounds()[0]) / 2 if not s_unter.is_empty() else 0
pruef(r_brett > R + 0.2 and abs(r_unter - R) < 0.03, f"Traufbrett {dmin:.3f} m dick (r {r_brett:.2f} in z {ZT - 0.5 * dmin:.2f}, darunter Schaft r {r_unter:.2f})")
pruef(k.genus() == 0 and k.volume() > 0, f"wasserdicht (ein Koerper), Geschlecht {k.genus()}")
pruef(any("Kegeldach" in b["element"] for b in bel), "Beleg Kegeldach vorhanden")
k2, bel2 = bau(dict(gueltig=False, grund="Rot-Probe"))
pruef(abs(k2.bounding_box()[5] - (prof[-1][0] + 0.25)) < 0.02 and any("NICHT gebaut" in b["element"] for b in bel2), f"ungueltiger Block: flach bei z {k2.bounding_box()[5]:.2f}, Beleg NICHT gebaut")
k3, _ = bau(dict(gueltig=True, z_traufe=ZT, r_traufe=RE, z_spitze=ZT + 0.1))
pruef(abs(k3.bounding_box()[5] - (prof[-1][0] + 0.25)) < 0.02, "Guard: Spitze nur 0,1 m ueber der Traufe -> nicht gebaut")
print("alle Tests bestanden" if not fehler else f"{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)

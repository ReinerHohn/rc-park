#!/usr/bin/env python3
"""test_dach_sichtschatten.py - Fotodach (tools/dach_aus_fotos.py) bei Fotos nur von einer/zwei Seiten (Befund Kette 1122o, 23.11.2026).

Synthetisch (CPU, < 10 s): Turm 12 x 12 m bis 37 m, Ueberstand 1 m, Zeltdach bis 46,7 m. Die Sichthuelle wird so gebaut, wie sie entsteht, wenn alle Fotos
von der Seite b- kommen (Hoehenwinkel 20 Grad): hinter dem Dach (b+) sieht kein Foto Himmel -> 'Sichtschatten' bis an den Gitterrand und bis ueber den First.
Geprueft:
  T1 profil_aus_huelle: Seite b+ OFFEN (Gitterrand), Sichtschatten erkannt, oberste Schicht nicht ueber dem First, Breite a in halber Dachhoehe aus dem
     Schnitt durch die Mitte (alt: ganze Schicht, durch den Schatten zu breit - wird mitgeprueft, damit der Test den alten Fehler wirklich sieht).
  T2 dach_aus_profil: First +-0,5 m am wahren First (alt 1122o: +4,4 m Schatten), Ueberstand b+ nicht am Gitterrand (alt 3,83 m), keine Kerbe:
     Flanken monoton nach oben schmaler.
  T3 gruppe_ursache: gleiche Meter-Abweichung nah/fern = Form; mit der Entfernung wachsend = Ausrichtung; zu aehnliche Entfernungen = offen.
  T4 gegenprobe: Kamera ueber der Traufe (Schlossberg) wird nicht beurteilt, Kamera am Boden schon.
rc 0 = alles bestanden."""
import os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, cv2
import dach_aus_fotos as D

DV = 0.15; HALB = 6.0; UEB = 1.0; Z_W = 37.0; Z_T = 37.3; Z_F = 46.7
fehler = []


def pruef(ok, text):
    print(("OK    " if ok else "FEHLER ") + text)
    if not ok: fehler.append(text)


def drin(a, b, z):
    """wahrer Koerper: Turm, Ueberstand (Traufbrett), Zeltdach."""
    w = np.where(z <= Z_W, HALB, np.where(z <= Z_T, HALB + UEB, (HALB + UEB) * np.clip((Z_F - z) / (Z_F - Z_T), 0, 1)))
    return (np.abs(a) <= w) & (np.abs(b) <= w) & (z <= Z_F)


us = np.arange(-10.0, 10.0, DV); vs = np.arange(-10.0, 10.0, DV); zs = np.arange(29.0, 56.0, DV)
A, B, Z = np.meshgrid(us, vs, zs, indexing="ij")
K = drin(A, B, Z)
tan_e = np.tan(np.radians(20.0))
for beta in np.arange(DV, 21.0, DV):                                      # Sichtschatten: vom Foto (Seite b-, Blick nach +b, 20 Grad nach oben) verdeckt
    K |= drin(A, B - beta, Z - beta * tan_e)
gitter = (us, vs, zs); c = np.array([0.0, 0.0]); ea = np.array([1.0, 0.0])   # a = u, b = v

# --- T1 ---
ext, fl, Kk, offen, info = D.profil_aus_huelle(K, gitter, c, ea, HALB, HALB)
dach = (zs > Z_T + 0.5) & (zs < Z_F - 0.5)
pruef(offen[dach, 3].mean() > 0.9 and offen[dach, 2].mean() < 0.1, f"T1 Seite b+ offen in {offen[dach, 3].mean() * 100:.0f} % der Dachschichten, b- in {offen[dach, 2].mean() * 100:.0f} %")
pruef(info["schatten_ab_z"] is not None, f"T1 Sichtschatten ohne Schnitt durch die Mitte erkannt ab z {info['schatten_ab_z']}")
oben = zs[np.isfinite(ext).all(1)].max()
pruef(oben <= Z_F + 2 * DV, f"T1 oberste Huellschicht {oben:.2f} m <= First {Z_F} m (+2 Zellen); Huelle roh bis {zs[K.any((0, 1))].max():.2f} m")
k42 = int(np.argmin(np.abs(zs - 42.0))); w_wahr = (HALB + UEB) * (Z_F - zs[k42]) / (Z_F - Z_T)
w_neu = 0.5 * (ext[k42, 1] - ext[k42, 0]); m = Kk[:, :, k42]; w_alt = 0.5 * (A[:, :, 0][m].max() - A[:, :, 0][m].min())
w_kegel = w_wahr * (Z_F - Z_T) / (HALB + UEB) / ((Z_F - Z_T) / (HALB + UEB) - tan_e)   # aus EINER Richtung ist auch der Mittelschnitt nur der Sichtkegel: Breite x s/(s - tan e)
pruef(w_wahr - 2 * DV <= w_neu <= w_kegel + 2 * DV, f"T1 halbe Breite a bei 42 m aus dem Mittelschnitt {w_neu:.2f} m (wahr {w_wahr:.2f}, Sichtkegel einer Richtung {w_kegel:.2f}, ganze Schicht/alt {w_alt:.2f})")
pruef(w_alt - w_wahr > 2 * DV, "T1 Gegenprobe: ganze Schicht (alter Weg) ist durch den Schatten wirklich zu breit - der Test sieht den Fehler")

# --- T2 ---
bel = np.zeros((len(zs), 4), int); bel[:, 0:2] = 3                     # a-Seiten von b- aus entlang gesehen
bel[(zs >= Z_W - 1) & (zs <= Z_T + 0.3), 2] = 3                         # b- nur im Traufband belegt (nahe steile Kameras)
bel[offen] = 0
teil = dict(wand_oberkante_lod2=Z_W, halb_a=HALB, halb_b=HALB)
d, grund = D.dach_aus_profil(ext, fl, bel, zs, teil, DV, offen=offen, log=lambda *x: None)
pruef(d is not None, f"T2 Dach bestimmt ({grund})")
if d is not None:
    pruef(abs(d["first_z"] - Z_F) <= 0.5, f"T2 First {d['first_z']:.2f} m gegen wahr {Z_F} m (1122o alt: +4,4 m Sichtschatten)")
    pruef(abs(d["traufe_z"] - Z_T) <= 0.5, f"T2 Traufe {d['traufe_z']:.2f} m gegen wahr {Z_T} m")
    pruef(d["ueberstand_m"]["b+"] <= UEB + 0.5, f"T2 Ueberstand b+ {d['ueberstand_m']['b+']:.2f} m (wahr {UEB}, alt Gitterrand 3,83 m)")
    q = np.array(d["profil"])[1:]
    mono = all((np.diff(np.abs(q[:, j])) <= 2 * DV + 1e-6).all() for j in range(1, 5))
    pruef(mono, "T2 Flanken nach oben nicht breiter (keine Kerbe wie 1122o Achse b 46-47 m)")

# --- T3 ---
ab = [35, 45, 50, 60, 90, 110, 130, 140]
u1 = D.gruppe_ursache([-1.6, -1.4, -1.7, -1.5, -1.6, -1.8, -1.7, -1.4], ab)
u2 = D.gruppe_ursache([0.035 * a_ for a_ in ab], ab)
u3 = D.gruppe_ursache([-1.6, -1.4, -1.7, -1.5, -1.6, -1.8], [40, 42, 44, 46, 48, 50])
pruef(u1 and u1["urteil"] == "form", f"T3 konstante Meter-Abweichung -> {u1 and u1['urteil']} ({u1 and u1['text']})")
pruef(u2 and u2["urteil"] == "ausrichtung", f"T3 mit Entfernung wachsend -> {u2 and u2['urteil']}")
pruef(u3 and u3["urteil"] == "offen", f"T3 aehnliche Entfernungen -> {u3 and u3['urteil']}")
pruef(D.gruppe_ursache([1, 1, 1], [10, 50, 100]) is None, "T3 zu wenige Fotos -> None")

# --- T4 ---
tmp = tempfile.mkdtemp(prefix="test_dach_sichtschatten_")
try:
    W, H, f = 800, 600, 700.0
    def kamera(name, C, ziel):
        C = np.array(C, float); vz = np.array(ziel, float) - C; vz /= np.linalg.norm(vz); x = np.cross(vz, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(vz, x)
        R = np.stack([x, y, vz]); t = -R @ C; foto = os.path.join(tmp, name + ".jpg"); cv2.imwrite(foto, np.zeros((H, W, 3), np.uint8))
        return dict(name=name, R=R, t=t, f=f, cx=W / 2, cy=H / 2, k1=0.0, W0=W, H0=H, C=C, foto=foto, sektor=0, abstand=float(np.hypot(*C[:2])))
    prof = [[Z_T - 0.3, -7, 7, -7, 7], [Z_T, -7, 7, -7, 7], [Z_F, -0.05, 0.05, -0.05, 0.05]]
    P = D.profil_punkte(prof, c, ea)
    k_boden = kamera("boden", [0, -45, 1.5], [0, 0, 42]); k_oben = kamera("berg", [0, -300, 70], [0, 0, 40])
    for kam in (k_boden, k_oben):                                          # Himmelsmaske: ueber der projizierten Dachkante Himmel (Boden); Berg: Horizont irgendwo
        u, v, z = D.projizieren(P, kam, 1.0); ok = (z > 0) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        top = np.full(W, H); np.minimum.at(top, u[ok].astype(int), v[ok].astype(int))
        sk = (np.arange(H)[:, None] < top[None, :]) if kam is k_boden else (np.arange(H)[:, None] < H // 10) & np.ones((1, W), bool)
        cv2.imwrite(os.path.join(tmp, f"umriss_{kam['name']}.png"), (sk * 255).astype(np.uint8))
    gp_alt = D.gegenprobe(P, [k_boden, k_oben], tmp, 0.12)
    gp_neu = D.gegenprobe(P, [k_boden, k_oben], tmp, 0.12, z_kamera_max=Z_T)
    pruef([g["foto"] for g in gp_neu] == ["boden"] and gp_neu[0]["passt"], f"T4 Gegenprobe ohne Kamera ueber der Traufe: {[(g['foto'], g['mad']) for g in gp_neu]} (ohne Grenze: {[(g['foto'], g['mad']) for g in gp_alt]})")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("FEHLER:" if fehler else "alle Pruefungen bestanden", len(fehler))
sys.exit(1 if fehler else 0)

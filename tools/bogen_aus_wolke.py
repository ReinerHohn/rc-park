#!/usr/bin/env python3
"""bogen_aus_wolke.py - Bogenoeffnungen als LOECHER in einer duennen Platte der Wolke um die Fassadenebene messen (3D-Lage, keine Foto-Ebenenannahme).
Schritte: Rahmen (Umeyama) -> Tiefenhistogramm in der Region (Peak = Fassadenebene) -> Platte +-dicke -> Belegung (cm-Raster) -> Schliessen kleiner Luecken -> Loecher >= Mindestflaeche
-> je Loch Kontur (Randpunkte, Meter ab Mitte) + Kennzahlen (Breite, Scheitelhoehe, Kaempferhoehe). Noch KEINE Benennung (Rund/Stich) - erst messen.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/bogen_aus_wolke.py modelle/<obj>/objekt.json --dicht <sfm/dicht_*> --box x0,y0,z0,x1,y1,z1 --normale nx,ny --aus ordner [--dicke 0.5] [--zelle 0.02]"""
import os, sys, json, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_front as WF
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dicht", required=True); ap.add_argument("--box", required=True); ap.add_argument("--normale", required=True)
ap.add_argument("--aus", required=True); ap.add_argument("--dicke", type=float, default=0.5); ap.add_argument("--zelle", type=float, default=0.02); ap.add_argument("--min-flaeche", type=float, default=2.0); ap.add_argument("--tiefe", type=float, default=6.0); ap.add_argument("--w", type=float, default=None, help="Fassadenebene fest (m) statt Histogrammgipfel (Gipfel springt bei grossem Kasten)")
a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); os.makedirs(a.aus, exist_ok=True)
s, Rm, t0, CM, rest = WF.rahmen_umeyama(a.dicht, od); X, C = WF.ply_farbe(os.path.join(a.dicht, "fused.ply")); X = s * (Rm @ X.T).T + t0
x0, y0, z0, x1, y1, z1 = [float(v) for v in a.box.split(",")]; nx, ny = [float(v) for v in a.normale.split(",")]; n = np.array([nx, ny, 0.0]); n /= np.linalg.norm(n); d = np.array([-n[1], n[0], 0.0])
mitte = np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0.0])
if np.sign(np.mean((CM - mitte) @ n)) < 0: n = -n; d = -d
P = X - mitte; w = P @ n; u = P @ d; v = X[:, 2]; ue = (np.array([[x, y, 0] for x in (x0, x1) for y in (y0, y1)]) - mitte) @ d; u0, u1 = ue.min(), ue.max()
reg = (u >= u0) & (u <= u1) & (v >= z0) & (v <= z1) & (np.abs(w) <= a.tiefe)
h, ed = np.histogram(w[reg], bins=np.arange(-a.tiefe, a.tiefe + 0.05, 0.05)); pk = a.w if a.w is not None else ed[np.argmax(h)] + 0.025
# Peak = Ebene mit den meisten Punkten (Archivolten-/Pfeilerfront); Platte [pk-dicke/2, pk+dicke/2]
pl = reg & (np.abs(w - pk) <= a.dicke / 2); Wp = int(np.ceil((u1 - u0) / a.zelle)); Hp = int(np.ceil((z1 - z0) / a.zelle))
iu = np.clip(((u[pl] - u0) / a.zelle).astype(int), 0, Wp - 1); iv = np.clip(((z1 - v[pl]) / a.zelle).astype(int), 0, Hp - 1)
occ = np.zeros((Hp, Wp), np.uint8); occ[iv, iu] = 255
occ = cv2.morphologyEx(occ, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))                      # Einzelpunkt-Luecken (Wolke duenn) schliessen
leer = (occ == 0).astype(np.uint8); nlab, lab, st, cen = cv2.connectedComponentsWithStats(leer, connectivity=8); loecher = []
for i in range(1, nlab):
    A = st[i, cv2.CC_STAT_AREA] * a.zelle ** 2; xw, yw, ww, hw = st[i, :4]
    if A < a.min_flaeche or xw == 0 or xw + ww >= Wp: continue                       # nur Loecher im Inneren (nicht der Rand-/Hintergrundbereich)
    m = (lab == i).astype(np.uint8); cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); c = max(cs, key=len)[:, 0, :].astype(float)
    uu = u0 + c[:, 0] * a.zelle; zz = z1 - c[:, 1] * a.zelle
    loecher.append(dict(id=int(i), flaeche_m2=round(float(A), 2), breite_m=round(float(ww * a.zelle), 2), hoehe_m=round(float(hw * a.zelle), 2), u_links=round(float(u0 + xw * a.zelle), 2), u_rechts=round(float(u0 + (xw + ww) * a.zelle), 2),
                        z_unten=round(float(z1 - (yw + hw) * a.zelle), 2), z_scheitel=round(float(z1 - yw * a.zelle), 2), kontur_u=np.round(uu, 3).tolist(), kontur_z=np.round(zz, 3).tolist()))
loecher.sort(key=lambda q: q["u_links"])
vis = cv2.cvtColor(occ, cv2.COLOR_GRAY2BGR)
for q in loecher:
    pts = np.c_[(np.array(q["kontur_u"]) - u0) / a.zelle, (z1 - np.array(q["kontur_z"])) / a.zelle].astype(np.int32); cv2.polylines(vis, [pts], True, (0, 0, 255), 2)
cv2.imwrite(os.path.join(a.aus, "platte_loecher.png"), vis)
json.dump(dict(rahmenrest_cm=rest * 100, ebene_w_peak_m=round(float(pk), 3), dicke=a.dicke, zelle=a.zelle, punkte_platte=int(pl.sum()), loecher=loecher, normale=n.tolist(), u0=float(u0), z1=float(z1)), open(os.path.join(a.aus, "bogen_aus_wolke.json"), "w"), indent=1)
print(f"Ebene w={pk:.2f} m, Platte {int(pl.sum())} Punkte, {len(loecher)} Loecher")
for q in loecher: print({k: q[k] for k in q if not k.startswith("kontur")})

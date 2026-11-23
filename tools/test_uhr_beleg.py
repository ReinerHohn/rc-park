#!/usr/bin/env python3
"""test_uhr_beleg.py - fester synthetischer Test (23.11.2026, Kettenlauf 1122p: goldener Heiligenschein im Wandgemaelde f01 als Uhr gebaut,
dieselbe Uhr zweimal (Aussenrand + Ziffernring)) fuer tools/uhren_wandbild.py:
  (1) Uhr mit 12 Ziffernstrichen, untere Haelfte im Schlagschatten -> Uhr (zifferblatt_beleg ok, k Vielfaches von 12);
  (2) heller Kreis mit 9 Steinen auf 3/4 des Rands, Gesicht + Koerper davor (Heiligenschein) -> verworfen, Grund 'kein Zifferblatt';
  (3) zwei Erkennerkaesten um dieselbe Uhr -> eine Uhr, die zweite als 'Dublette' verworfen;
  (4) dubletten_zusammenfassen: kleinerer konzentrischer Kreis (0,66 x) wird d_innen der grossen, fremde Uhr bleibt.
Werte sind Testgeometrie, kein Objektmass. < 10 s."""
import os, sys, json, subprocess
import numpy as np, cv2
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner
import uhren_wandbild as UW

fehler = []
def pruef(b, t):
    if not b: fehler.append(t)

T = temp_ordner("test_uhr_beleg_"); FF = os.path.join(T, "fassade_fein"); os.makedirs(FF); od = os.path.join(T, "obj"); os.makedirs(od)
c = 0.01; R = dict(u0=0.0, z1=8.0, nu=900, nz=800, zelle=c)                 # Raster 1 cm, u 0..9, z 8..0
json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], raster=R)]), open(os.path.join(FF, "fassaden.json"), "w"))
uu = R["u0"] + (np.arange(R["nu"]) + 0.5) * c; zz = R["z1"] - (np.arange(R["nz"]) + 0.5) * c; UU, ZZ = np.meshgrid(uu, zz)
rng = np.random.default_rng(5); g = (200 + rng.normal(0, 3, UU.shape)).clip(0, 255)
# (1) Uhr: Mitte u 2, z 5, Durchmesser 2 m, Ring dunkel, 12 helle Striche radial, Innenfeld mittel, untere Haelfte Schatten (-60)
uc, zc, ra, ri = 2.0, 5.0, 1.0, 0.65; rr = np.hypot(UU - uc, ZZ - zc); ph = np.arctan2(UU - uc, ZZ - zc)
g[rr <= ra] = 50; g[rr <= ri] = 140
for n_ in range(12):
    a_ = np.radians(30 * n_); g[(np.abs(np.sin(ph - a_)) * rr < 0.03) & (rr > ri + 0.04) & (rr < ra - 0.04) & (np.cos(ph - a_) > 0)] = 230
g[(rr <= ra + 0.02) & (ZZ < zc - 0.1)] -= 45
# (2) Heiligenschein: Mitte u 6,5, z 5, Durchmesser 1,8 m, hell (Gold), 9 dunkle Steine bei r 0,8 auf 270 Grad, Gesicht (Mitte) + Koerper unten davor
hc = 6.5; rh = np.hypot(UU - hc, ZZ - zc); phh = np.arctan2(UU - hc, ZZ - zc)
g[rh <= 0.9] = 215; g[(rh > 0.86) & (rh <= 0.9)] = 120
for a_ in np.radians(np.linspace(-135, 135, 9)):
    g[np.hypot(UU - (hc + 0.72 * np.sin(a_)), ZZ - (zc + 0.72 * np.cos(a_))) < 0.06] = 40
g[np.hypot((UU - hc) / 0.42, (ZZ - zc + 0.05) / 0.55) < 1] = 120; g[(np.abs(UU - hc) < 0.6) & (ZZ < zc - 0.45) & (rh < 0.84)] = 90
cv2.imwrite(os.path.join(FF, "ortho_f00_fein.png"), g.astype(np.uint8))
K = lambda u0, u1, z0, z1: dict(klasse="uhr", stimmen=5, gesehen=6, u0=u0, u1=u1, z0=z0, z1=z1)
E = dict(fassaden=dict(f00=dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], elemente=[K(1.0, 3.0, 4.0, 6.0), K(0.9, 3.1, 3.92, 6.1), K(5.6, 7.4, 4.1, 5.9)])))
json.dump(E, open(os.path.join(T, "elemente.json"), "w")); json.dump(dict(name="test"), open(os.path.join(od, "objekt.json"), "w"))
aus = os.path.join(od, "audit", "uhren_auto.json")
p = subprocess.run([sys.executable, "-I", os.path.join(H, "uhren_wandbild.py"), os.path.join(od, "objekt.json"), FF, "--elemente", os.path.join(T, "elemente.json"), "--aus", aus],
                   capture_output=True, text=True, env=dict(os.environ, OHNE_ZIFFERBLATT="1"))
pruef(p.returncode == 0 and os.path.exists(aus), f"uhren_wandbild rc {p.returncode}: {(p.stdout + p.stderr)[-300:]}")
if os.path.exists(aus):
    F = json.load(open(aus))["f00"]; U = F["uhren"]; V = F["verworfen"]
    pruef(len(U) == 1, f"{len(U)} Uhren statt 1: {[(x['u'], x['z'], x['d_aussen']) for x in U]}")
    if U: pruef(abs(U[0]["u"] - uc) < 0.08 and abs(U[0]["z"] - zc) < 0.08 and abs(U[0]["d_aussen"] - 2 * ra) < 0.15, f"Uhr falsch vermessen: {U[0]}")
    if U: pruef(U[0].get("beleg_12", 0) >= 1.2, f"Uhr ohne 12er-Beleg: {U[0].get('beleg_12')}")
    pruef(any("kein Zifferblatt" in v["grund"] and v["kasten"][0] > 5 for v in V), f"Heiligenschein nicht als 'kein Zifferblatt' verworfen: {V}")
    pruef(any("Dublette" in v["grund"] for v in V), f"zweiter Kasten derselben Uhr nicht als Dublette verworfen: {V}")
# (4) direkt
B, W = UW.dubletten_zusammenfassen([dict(u=0.0, z=30.0, d_aussen=5.0, d_innen=None), dict(u=1.6, z=17.0, d_aussen=1.7), dict(u=-0.03, z=30.02, d_aussen=3.3, kasten=[1, 2, 3, 4])])
pruef(len(B) == 2 and len(W) == 1 and abs((B[0].get("d_innen") or 0) - 3.3) < 1e-9 and B[1]["d_aussen"] == 1.7, f"dubletten_zusammenfassen falsch: {B} / {W}")
b = UW.zifferblatt_beleg(np.full((100, 100), 128.0), 50, 50, 10); pruef(not b["ok"] and "nicht pruefbar" in b["grund"], f"zu kleine Scheibe als belegt: {b}")
print("FEHLER: " + " | ".join(fehler) if fehler else "ALLE BESTANDEN (Uhr mit 12er-Teilung trotz Schatten, Heiligenschein verworfen, Dublette zusammengefasst, Innenring uebernommen)")
sys.exit(1 if fehler else 0)

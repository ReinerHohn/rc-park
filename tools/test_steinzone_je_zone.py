#!/usr/bin/env python3
"""Test (24.11.2026, Kette 1122u Schwabentor Sued w06/w07, Nord w02): Quader-Entscheidung JE ZONE statt je Wand.
Befund: unten Buckelquader bis zur Putzkante (~8 m), darueber Putz mit Wandgemaelde. Das Quader-Tor (ganze Wand) sagte 'kein Fugenraster' -> relief_roh
glaettete per putz_eben alles naeher als 5 cm am Wandniveau (93 % der Wand) -> Scan-Band der Steinzone flach (Std 4-8 cm -> 0,6-1,5 cm), Mono-Relief rc 4
(keine Korrelation mit dem Scan), Quaderzone im Modell glatt.
Synthetisch: Wand 4 x 20 m, Torbogen 3 m breit bis 4 m, Quader (+-3 cm Buckel) bis 8 m, darueber Putz mit Rauschen 1 cm.
Soll: (1) steinzone_band findet die Zone 0..8 m trotz Torbogen; (2) steinzone_wandbild liefert sie aus der Wandbild-Quaderkarte; (3) relief_roh mit Steinzone
behaelt das Steinrelief (Band-Std >= 1,5 cm) und glaettet den Putz, Maske 'putz' = Wand ueber der Zone. ROT-PROBE: relief_roh ohne Steinzone (alter Stand) muss
das Steinrelief plattmachen (sonst prueft der Test nichts)."""
import os, sys, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from scipy import ndimage as ndi
import fassaden_kette as FK, quader_raster as QR, putz_wandbild as PW
from pfade import temp_ordner

PX = 0.05; Wm, Hm, ZS = 4.0, 20.0, 8.0
H, W = int(Hm / PX), int(Wm / PX); zz = (H - 1 - np.arange(H) + 0.5) * PX; uu = (np.arange(W) + 0.5) * PX
ZZ, UU = np.meshgrid(zz, uu, indexing="ij"); rng = np.random.default_rng(3)
tor = (np.abs(UU - 2.0) < 1.5) & (ZZ < 4.0)                               # Torbogen (Oeffnung), Pfeiler 0,5 m
stein = ZZ < ZS
lage = (ZZ // 0.4).astype(int); buckel = np.where(((UU + 0.3 * (lage % 2)) % 0.6 > 0.05) & (ZZ % 0.4 > 0.05), 0.03, -0.02)   # Quader 0,6 x 0,4 m, Fugen 5 cm
rel = np.where(stein, 0.10 + buckel, 0.10 + 0.01 * rng.standard_normal((H, W))).astype(np.float32); rel[tor] = 0.0
fehler = []

# (1) Zonenregel
b = QR.steinzone_band(stein & ~tor, ~tor, PX, 0.0)
if not b or abs(b[0]) > 0.3 or abs(b[1] - ZS) > 0.3: fehler.append(f"steinzone_band {b} statt (0, {ZS})")
if QR.steinzone_band(np.zeros((H, W), bool), ~tor, PX, 0.0) is not None: fehler.append("steinzone_band ohne Stein muss None sein")

# (2) Wandbild-Wrapper (Quaderkarte synthetisch statt glatt_karte)
Z = dict(rel=rel, a=np.array([0.0, 0.0]), t=np.array([0.0, 1.0]), n=np.array([1.0, 0.0]), u0=0.0, z0=0.0, px=PX, oeffnung=tor, wand=np.ones((H, W), bool),
         lochanteil=0.0, trend_je_m=np.zeros(2))
FK.fein_ordner = lambda oj: "/nicht/da"
gemaelde = (ZZ > ZS + 1.0) & (ZZ < ZS + 4.0) & (np.abs(UU - 2.0) < 0.9)     # Wandgemaelde 1-4 m ueber der Putzkante: im Wandbild 'rau' (45 % der Zeile, wie w06 10-12 m)
PW.putz_auf_relief = lambda Z_, ffn, art="putz", **kw: (stein | gemaelde) if art == "quader" else (~stein & ~gemaelde)
sz = FK.steinzone_wandbild(Z, "egal.json")
if not sz or abs(sz[1] - ZS) > 0.3: fehler.append(f"steinzone_wandbild {sz} statt Oberkante {ZS} (Wandgemaelde darf die Zone nicht verlaengern)")
PW.putz_auf_relief = lambda Z_, ffn, art="putz", **kw: (stein | gemaelde) if art == "quader" else None      # ROT-PROBE: ohne Putzstopp laeuft die Zone ins Gemaelde
sz_rot = FK.steinzone_wandbild(Z, "egal.json")
if not sz_rot or sz_rot[1] < ZS + 2.0: fehler.append(f"ROT-PROBE Putzstopp wirkungslos: ohne Putzkarte Zone {sz_rot} (Test prueft den Putzstopp nicht)")
PW.putz_auf_relief = lambda Z_, ffn, art="putz", **kw: np.zeros((H, W), bool)
if FK.steinzone_wandbild(Z, "egal.json") is not None: fehler.append("steinzone_wandbild ohne Quaderkarte muss None sein")

# (3) relief_roh je Zone
td = temp_ordner("test_steinzone_je_zone_"); r0 = os.path.join(td, "w.npz"); np.savez_compressed(r0, **Z)
def band_std(f, sel):
    R = np.load(f); r = np.asarray(R["rel"], float); m = (r != 0) & ~tor
    def g(s): return ndi.gaussian_filter(np.where(m, r, 0.0), s) / np.maximum(ndi.gaussian_filter(m.astype(float), s), 1e-3)
    bp = g(0.4) - g(0.6 / PX / 2.5); k = m & sel & (ZZ > 4.5); return float(np.std(bp[k])) * 100, R
neu = os.path.join(td, "w_neu.npz"); FK.relief_roh(r0, neu, PX, steinzone=sz or (0.0, ZS)); s_neu, Rn = band_std(neu, stein)
alt = os.path.join(td, "w_alt.npz"); FK.relief_roh(r0, alt, PX); s_alt, _ = band_std(alt, stein)
p_neu, _ = band_std(neu, ~stein & (ZZ > ZS + 1))
print(f"Band-Std Steinzone: neu {s_neu:.2f} cm, alt {s_alt:.2f} cm; Putz neu {p_neu:.2f} cm; Zone {sz}")
if s_neu < 1.5: fehler.append(f"Steinzone mit Zone geglaettet: Band-Std {s_neu:.2f} cm < 1,5")
if s_alt >= 1.5: fehler.append(f"ROT-PROBE wirkungslos: alter Stand behaelt das Steinrelief ({s_alt:.2f} cm) - Test prueft nichts")
if p_neu > 0.5: fehler.append(f"Putz ueber der Zone nicht geglaettet: {p_neu:.2f} cm")
if "putz" not in Rn.files or not np.asarray(Rn["putz"])[(ZZ > ZS + 0.2)].all() or np.asarray(Rn["putz"])[(ZZ < ZS - 0.2)].any(): fehler.append("Maske 'putz' != Wand ueber der Steinzone")
if fehler: print("FEHLER:", " | ".join(fehler)); sys.exit(1)
print("OK: Quader-Tor je Zone - Steinzone 0..8 m erkannt, Steinrelief bleibt, Putz glatt, Rot-Probe (alter Stand) flach"); sys.exit(0)

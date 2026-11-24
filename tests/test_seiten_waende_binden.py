#!/usr/bin/env python3
"""test_seiten_waende_binden.py - fester synthetischer Test fuer tools/seiten_waende_binden.py (Gegenseite ueber gemeinsame Waende binden), < 1 min, nur CPU.

Befund Kettenlauf schwabentor-1122w (24.11.2026): Teil 1 (Suedseite) nur ueber das Foto-GPS gelegt; gemessen war diese Lage 10 Grad GEKIPPT und 4-5 Grad verdreht,
Klappung/Querspur/LoD2 je Teil banden nicht. Teil A sieht den Turm rundum (oberhalb der Nachbardaecher), Teil B Sued- und Ostwand.
Welt: Kastenturm 10 x 8 m, 30 m hoch, dazu ein Nachbarhaus westlich (nur A) und eine Mauer suedlich (nur B). A = Welt / 5 (5 m je Einheit), B = beliebige Aehnlichkeit.
  1 RICHTIG   GPS-Lage = wahre Lage, um 7 Grad gekippt, 4 Grad gedreht, 2 m verschoben -> gebunden; B-Turmpunkte nachher < 0,15 m neben der Wahrheit, Kippung erkannt.
  2 EINE WAND B sieht nur die Suedwand -> abgelehnt (Lage laengs der Wand nicht bestimmt), keine Matrix.
  3 WEIT WEG  wahre Lage 12 m neben dem GPS (ausserhalb der Suche) -> abgelehnt, keine Matrix.
  4 GPS-PROBE gps_urteil: keine Geotags / Median deutlich schlechter / zu wenige unter 12 m -> Ablehnung; knapp schlechter -> bestanden.
  5 VERDRAHTUNG sfm_seiten_modelle (waende_stufe, RCPARK_WAENDE, Code-Stand, Weg 'gps+waende' ohne GPS-Ausgleich), seiten_lage_beleg ('gps+waende' belegt)."""
import os, sys
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); TOOLS = os.path.join(os.path.dirname(HIER), "tools"); sys.path.insert(0, TOOLS)
import seiten_waende_binden as WB
import seiten_lage_beleg as SLB

F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def rot(achse, grad): return WB.drehung(np.asarray(achse, float), grad)


def wand(p0, p1, z0, z1, dichte, rng):
    """Punkte auf einer senkrechten Wand von p0 nach p1 (Grundriss), z0..z1, Rauschen 2 cm senkrecht zur Wand."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float); L = np.linalg.norm(p1 - p0); n = int(dichte * L * (z1 - z0)); t = rng.random(n); z = z0 + (z1 - z0) * rng.random(n)
    d = (p1 - p0) / L; nn = np.array([-d[1], d[0]]); xy = p0 + np.outer(t * L, d) + np.outer(rng.normal(0, 0.02, n), nn); return np.c_[xy, z]


rng = np.random.default_rng(3)
SW, SO, NO, NW = (-5, -4), (5, -4), (5, 4), (-5, 4)
turm_a = np.vstack([wand(SW, SO, 0, 30, 25, rng), wand(SO, NO, 0, 30, 25, rng), wand(NO, NW, 0, 30, 25, rng), wand(NW, SW, 0, 30, 25, rng)])
nachbar = np.vstack([wand((-20, -3), (-9, -3), 0, 12, 25, rng), wand((-9, -3), (-9, 6), 0, 12, 25, rng)])
boden = np.c_[rng.uniform(-30, 30, 30000), rng.uniform(-30, 30, 30000), rng.normal(0, 0.02, 30000)]
welt_a = np.vstack([turm_a, nachbar, boden])
turm_b_sued = wand(SW, SO, 0, 30, 25, rng); turm_b_ost = wand(SO, NO, 0, 30, 25, rng)
mauer = wand((-3, -14), (12, -14), 0, 3.5, 25, rng)
boden_b = np.c_[rng.uniform(-20, 20, 15000), rng.uniform(-30, -5, 15000), rng.normal(0, 0.02, 15000)]
kam_b = np.c_[rng.uniform(-15, 15, 40), rng.uniform(-40, -18, 40), np.full(40, 1.6)]

MJ = 5.0
MA = np.eye(4); MA[:3, :3] = rot([1, 2, 0.5], 25) / MJ; MA[:3, 3] = [1.0, -2.0, 0.5]                   # Welt -> A
MB = np.eye(4); MB[:3, :3] = 0.37 * rot([0.3, -1, 2], 140); MB[:3, 3] = [-4.0, 3.0, 9.0]                 # Welt -> B
M_wahr = MA @ np.linalg.inv(MB)                                                                         # B -> A
lot_a = MA[:3, :3] @ [0, 0, 1.0]; lot_a /= np.linalg.norm(lot_a)
DA = WB.anwenden(MA, welt_a)


def gps_lage(kipp=7.0, dreh=4.0, schieb=(1.5, 1.3)):
    """GPS-Lage in A: wahre Lage, dann im Welt-System um den Fusspunkt der B-Wolke gekippt (um x; dort traegt das GPS die Hoehe: Boden unter den nahen Kameras), um das Lot gedreht, waagerecht verschoben."""
    W = np.eye(4); c = np.r_[np.median(welt_b[:, :2], 0), np.percentile(welt_b[:, 2], 2)]; R = rot([0, 0, 1], dreh) @ rot([1, 0, 0], kipp); W[:3, :3] = R; W[:3, 3] = c - R @ c + [schieb[0], schieb[1], 0]
    return MA @ W @ np.linalg.inv(MA) @ M_wahr


def G_von(Mg): return dict(M=Mg, dreh_sd=1.4, mass_sd=0.03, lage_sd_m=1.0, m_je_einheit=MJ, dreh_sd_ehrlich=9.3, mass_sd_ehrlich=0.16)


def fehler_m(M, welt_b, nur=None):
    """B-Turmpunkte: Abstand (m, Welt) nach M gegen die Wahrheit; nur='waagerecht'/'senkrecht'."""
    X = WB.anwenden(MB, welt_b); Ai = np.linalg.inv(MA); d = WB.anwenden(Ai @ M, X) - WB.anwenden(Ai @ M_wahr, X)
    if nur == "waagerecht": d = d[:, :2]
    if nur == "senkrecht": d = d[:, 2:]
    return float(np.median(np.linalg.norm(d, axis=1)))


print("1 RICHTIG")
welt_b = np.vstack([turm_b_sued, turm_b_ost, mauer, boden_b]); DB = WB.anwenden(MB, welt_b); ref_b = WB.anwenden(MB, kam_b)
Mg = gps_lage(); f0 = fehler_m(Mg, np.vstack([turm_b_sued, turm_b_ost]))
e = WB.binden(DA, DB, G_von(Mg), lot_a, ref_b)
pruef(e.get("ok") is True, f"gebunden ({e.get('urteil', '')[:220]})")
if e.get("ok"):
    T_ = np.vstack([turm_b_sued, turm_b_ost]); f1 = fehler_m(np.asarray(e["B_nach_A"]), T_, "waagerecht"); f1z = fehler_m(np.asarray(e["B_nach_A"]), T_, "senkrecht")
    pruef(f1 < 0.05 and f0 > 1.0, f"B-Turmpunkte vorher {f0:.2f} m, nachher waagerecht {f1:.3f} m neben der Wahrheit (< 0,05 m)")
    pruef(f1z < 0.5, f"senkrecht {f1z:.3f} m (< 0,5 m: Waende legen die Hoehe nicht fest, sie bleibt am Fusspunkt GPS-genau; Fusspunkt der gekippten Wolke liegt ~3 m anders)")
    pruef(abs(e["pruefung"]["kippung_gps_grad"] - 7.0) < 0.5, f"Kippung der GPS-Lage aus den Waenden {e['pruefung']['kippung_gps_grad']} Grad (eingespielt 7)")
    pruef(e["pruefung"]["baender_uneinig"]["richtungen_verglichen"] == 2, "zwei Hoehenbaender, beide Wandrichtungen verglichen")

print("2 EINE WAND")
welt_b1 = np.vstack([turm_b_sued, boden_b]); e = WB.binden(DA, WB.anwenden(MB, welt_b1), G_von(Mg), lot_a, ref_b)
pruef(e.get("ok") is False and "B_nach_A" not in e and ("Wandrichtung" in e["urteil"] or "mehrdeutig" in e["urteil"]), f"abgelehnt: {e['urteil'][:200]}")

print("3 WEIT WEG")
Mw = gps_lage(kipp=7.0, dreh=3.0, schieb=(12.0, 0.0)); e = WB.binden(DA, DB, G_von(Mw), lot_a, ref_b)
pruef(e.get("ok") is False and "B_nach_A" not in e, f"abgelehnt: {e['urteil'][:200]}")

print("4 GPS-PROBE")
g = lambda m0, m1, a1: dict(n_gps_b=30, gps=dict(median_m=m0, anteil_unter_grenze=0.95), neu=dict(median_m=m1, anteil_unter_grenze=a1))
pruef(WB.gps_urteil(None) != "", "ohne Geotags: keine Gegenprobe -> Ablehnung")
pruef(WB.gps_urteil(g(5.1, 9.0, 0.8)) != "", "Median 5,1 -> 9,0 m -> Ablehnung")
pruef(WB.gps_urteil(g(5.1, 6.0, 0.5)) != "", "nur 50 % unter 12 m -> Ablehnung")
pruef(WB.gps_urteil(g(5.1, 7.8, 0.79)) == "", "1122w-Werte (5,1 -> 7,8 m, 79 %) -> bestanden")

print("5 VERDRAHTUNG")
src = open(os.path.join(TOOLS, "sfm_seiten_modelle.py")).read()
pruef("waende_stufe(" in src and 'RCPARK_WAENDE' in src and '"seiten_waende_binden.py"' in src and '"gps+waende"' in src, "sfm_seiten_modelle: Stufe, Schalter, Code-Stand, Weg")
i_q, i_w, i_l = src.index("qs = querspur_stufe("), src.index("wb_ = waende_stufe("), src.index("lo = lod2_stufe(")
pruef(i_q < i_w < i_l, "Reihenfolge: Querspur -> Waende -> LoD2 je Teil")
pruef('("gps+querspur", "gps+lod2", "gps+waende")' in src, "nach Waende-Bindung kein GPS-Ausgleich (zoege B wieder aufs GPS)")
b, grund, _ = SLB.lage_belegt(dict(weg="gps+waende", waende=dict(urteil="x")))
pruef(b is True, f"seiten_lage_beleg: 'gps+waende' belegt ({grund[:60]})")

print("ALLE TESTS BESTANDEN" if F == 0 else f"{F} FEHLER")
sys.exit(1 if F else 0)

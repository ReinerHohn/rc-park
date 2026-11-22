#!/usr/bin/env python3
"""test_dach_profil_duenn.py - Wolken-Dachprofil bei leerer/duenner Dachseite (tools/dach_profil_wolke.py, 22.11.2026).
Anlass Lauf schwabentor-1122n (20:16, Stufe bauplan_dachprofil): schale() nahm np.nonzero(h >= max(0.3*h.max(), 3))[0][-1] - auf einer Seite mit nur
verstreuten Wolkenpunkten (kein 0,1-m-Bin mit >= 3 Punkten; Wolke nur von Teil A, Dachseite b- 9 % belegt) -> IndexError, Stufe rot, audit/dach_profil.json
fehlte und damit alle Foto-Dachstufen (traufe/dachflaeche/laterne/spitze); das Modell bekam das nackte DOM1-Walmdach ohne Ueberstand.
Zweitens: Seiten ohne Wolke wurden an der Achse GESPIEGELT (Regelverstoss "Ungesehenes nie spiegeln") -> jetzt bisheriges Modell (LoD2 + DOM1) + Block 'fotoluecken'.
  T1 schale: leer -> None, verstreut (alter Ausdruck wirft IndexError) -> None, dichte Schale -> aeusserste dichte Lage (+-0,05 m), Rauschpunkt davor zaehlt nicht.
  T2 seiten_messen: -d dicht 'ok', +d verstreut 'keine dichte Schale', -n leer 'leer', +n zu wenige 'duenn'.
  T3 Ende-zu-Ende (synthetischer Turm + Walmdach-Wolke ohne +n-Seite, +d-Seite verstreut): rc 0 statt Absturz, dach_profil.json mit fotoluecken +n/+d,
     seiten_gespiegelt 0, +n-Seite = Modellausdehnung (nicht Spiegelbild der -n-Seite mit Ueberstand), -n-Seite traegt den Wolken-Ueberstand.
  T4 Rot-Probe: der alte Ausdruck wirft auf den T3-Daten (verstreute Seite) wirklich IndexError."""
import os, sys, json, subprocess, tempfile, shutil, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from dach_profil_wolke import schale, seiten_messen

F = []
def chk(b, txt):
    print(("    ok   " if b else "FEHLER   ") + txt); F.append(not b)

def alt_schale(q):                                     # Ausdruck bis 22.11.2026 (Rot-Probe)
    h, k = np.histogram(q, bins=np.arange(float(q.min()), float(q.max()) + 0.2, 0.1)); i = np.nonzero(h >= max(0.3 * h.max(), 3))[0][-1]; return float(k[i] + 0.05)

rng = np.random.default_rng(7)
# T1
chk(schale(np.array([])) is None, "T1a leere Seite -> kein Urteil (None)")
verstreut = np.linspace(0.0, 9.0, 18) + rng.uniform(0, 0.02, 18)          # 18 Punkte ueber 9 m: jedes 0,1-m-Bin <= 1 Punkt
try: alt_schale(verstreut); alt_wirft = False
except IndexError: alt_wirft = True
chk(alt_wirft, "T1b Rot-Probe: alter Ausdruck wirft auf verstreuter Seite IndexError (wie 1122n)")
chk(schale(verstreut) is None, "T1c verstreute Seite -> kein Urteil statt Absturz")
dicht = np.r_[rng.normal(6.0, 0.03, 400), rng.uniform(2.0, 6.0, 60), [7.5]]    # Schale bei 6,0, innen Streupunkte, ein Rauschpunkt 1,5 m davor
s = schale(dicht); chk(s is not None and abs(s - 6.0) < 0.1, f"T1d dichte Schale -> {s} (Soll 6,0 +-0,1; Rauschpunkt 7,5 zaehlt nicht)")

# T2: Scheibe mit vier Seiten
def seite(n, a, art):                                  # Punkte auf Seite art (-d/+d/-n/+n) bei Abstand a
    t = rng.uniform(-a * 0.8, a * 0.8, n); r = a + rng.normal(0, 0.03, n)
    return {"-d": (-r, t), "+d": (r, t), "-n": (t, -r), "+n": (t, r)}[art]
U, V = [], []
for art, n in (("-d", 300), ("+n", 8)):
    u, v = seite(n, 6.0, art); U.append(u); V.append(v)
u = np.r_[np.concatenate(U), np.linspace(1.0, 6.5, 20)]; v = np.r_[np.concatenate(V), np.zeros(20)]   # +d: 20 Punkte verstreut ueber 5,5 m
z = np.full(len(u), 40.2)
r, nk, gr = seiten_messen(u, v, z, 40.0, 0.5, [-8, 8, -8, 8], 0.7, 15)
chk(r[0] is not None and abs(r[0] + 6.0) < 0.1 and gr[0] == "ok", f"T2a -d dicht -> {r[0]} {gr[0]}")
chk(r[1] is None and gr[1].startswith("keine dichte Schale"), f"T2b +d verstreut -> {r[1]} '{gr[1]}'")
chk(r[2] is None and gr[2] == "leer", f"T2c -n leer -> {r[2]} '{gr[2]}'")
chk(r[3] is None and gr[3].startswith("duenn"), f"T2d +n 8 Punkte -> {r[3]} '{gr[3]}'")

# T5: Dachachse nur ueber dem Traufband (1122: Traufband-Rauschen schob die Achse 2,4 m neben die Wandmitte)
from dach_profil_wolke import achse_messen
PA = [[35.4, -5.6, 8.0, -7.4, 4.2, 100, []], [35.9, -5.7, 8.0, -7.4, 3.6, 100, []], [36.4, -5.7, 7.9, -7.4, 3.6, 100, []]]          # Traufband: Rauschen
PA += [[z, -(5.0 - (z - 37.4) * 0.7) + 0.1, 5.0 - (z - 37.4) * 0.7 + 0.1, -4.0, 4.0, 100, ["-n"]] for z in np.arange(37.4, 41.5, 0.5)]   # Dach: u-Mitte +0,1, -n fehlt
cu5, cv5, inf5 = achse_messen(PA, 35.4, 0.5)
chk(abs(cu5 - 0.1) < 0.02, f"T5a u-Achse aus den Dachscheiben {cu5:+.2f} (Soll +0,10; Traufband-Rauschen nicht mitgezaehlt)")
chk(cv5 == 0.0 and inf5["v"]["quelle"].startswith("ANNAHME"), f"T5b v ohne Scheiben mit beiden Seiten -> Wandmitte als ANNAHME ({inf5['v']['quelle'][:60]}); alt waere {np.median([(p[3] + p[4]) / 2 for p in PA if '-n' not in p[6]]):+.2f}")

# T3: Ende-zu-Ende auf synthetischen Dateien (ohne Rahmen -> kein DOM1-Veto)
import trimesh
T = tempfile.mkdtemp(prefix="test_dach_profil_duenn_", dir=os.environ.get("TMPDIR", "/tmp"))
try:
    os.makedirs(os.path.join(T, "audit"))
    A_, B_, ZT, UE = 6.0, 5.0, 37.0, 0.8                                       # Wand halb (u=x, v=y), Traufe, Ueberstand der echten Dachflaeche
    turm = trimesh.creation.box(extents=(2 * A_, 2 * B_, ZT)); turm.apply_translation((0, 0, ZT / 2))
    dach = trimesh.Trimesh(vertices=[[-A_, -B_, ZT], [A_, -B_, ZT], [A_, B_, ZT], [-A_, B_, ZT], [0, 0, ZT + 6.0]], faces=[[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [0, 2, 1], [0, 3, 2]])
    m = trimesh.util.concatenate([turm, dach]); m.apply_scale(1000.0 / 87); stl = os.path.join(T, "m.stl"); m.export(stl)
    pts = []
    for zz in np.arange(ZT - 3.0, ZT, 0.05):                                    # Wandpunkte unter der Traufe (alle Seiten)
        for art, a in (("-d", A_), ("+d", A_), ("-n", B_), ("+n", B_)):
            uu, vv = seite(60, a, art); pts.append(np.c_[uu, vv, np.full(60, zz)])
    for li, zz in enumerate(np.arange(ZT, ZT + 5.0, 0.05)):                     # Dachflaeche mit Ueberstand UE, Neigung wie Modell (6 m auf ~5-6 m)
        h = (zz - ZT) / 6.0; a_, b_ = (A_ + UE) * (1 - h), (B_ + UE) * (1 - h)
        uu, vv = seite(120, a_, "-d"); pts.append(np.c_[uu, vv, np.full(120, zz)])
        uu, vv = seite(120, b_, "-n"); pts.append(np.c_[uu, vv, np.full(120, zz)])
        pts.append(np.c_[0.5 * a_ + ((2 * li + np.arange(2)) * 0.17) % (0.5 * a_ + 0.6), np.zeros(2), np.full(2, zz)])   # +d: 2 Punkte je 5-cm-Lage, 0,17 m versetzt = verstreut ohne dichtes Bin; +n: gar keine
    W = np.vstack(pts).astype(np.float32); wp = os.path.join(T, "w.npy"); np.save(wp, W)
    json.dump({"fassaden": [{"d": [1.0, 0.0], "n": [0.0, 1.0], "flaeche_m2": 100.0}]}, open(os.path.join(T, "fassaden.json"), "w"))
    json.dump({"name": "test", "stl": stl, "stl_massstab": 87}, open(os.path.join(T, "objekt.json"), "w"))
    # T4 Rot-Probe auf genau diesen Daten: verstreute +d-Seite einer Dachscheibe mit dem alten Ausdruck
    k = (W[:, 2] >= ZT + 1.0) & (W[:, 2] < ZT + 1.5); q = W[k, 0][(W[k, 0] > np.abs(W[k, 1])) & (W[k, 0] < A_ + 2.7)]
    try: alt_schale(q); alt4 = False
    except IndexError: alt4 = True
    chk(alt4 and len(q) >= 15, f"T4 Rot-Probe: alter Ausdruck wirft auf der verstreuten +d-Seite ({len(q)} Punkte) IndexError")
    py = sys.executable
    pr = subprocess.run([py, "-W", "ignore", "-I", os.path.join(HIER, "dach_profil_wolke.py"), os.path.join(T, "objekt.json"), wp, os.path.join(T, "fassaden.json"), "--stl", stl],
                        capture_output=True, text=True, timeout=300)
    chk(pr.returncode == 0, f"T3a rc {pr.returncode} (kein Absturz){' | ' + pr.stderr.strip().splitlines()[-1][:200] if pr.returncode and pr.stderr.strip() else ''}")
    dp = os.path.join(T, "audit", "dach_profil.json")
    if os.path.exists(dp):
        D = json.load(open(dp)); P = D["scheiben"]; FL = D.get("fotoluecken") or {}
        an = {k_: v_["anteil"] for k_, v_ in FL.items()}
        chk(an.get("+n", 0) >= 0.6 and an.get("+d", 0) >= 0.6 and an.get("-n", 0) <= 0.3 and an.get("-d", 0) <= 0.3, f"T3b Fotoluecken gemeldet (Anteil Scheiben): {an} (Soll +d/+n >= 0,6, -d/-n <= 0,3: nur Spitze ohne Wolke)")
        chk(D.get("seiten_gespiegelt") == 0, f"T3c nichts gespiegelt (seiten_gespiegelt {D.get('seiten_gespiegelt')})")
        p0 = P[0]; mitte = [p for p in P if ZT + 0.5 <= p[0] <= ZT + 2.0]
        chk(all(p[4] <= B_ * (1 - (p[0] - ZT) / 6.0) + 0.3 for p in mitte), "T3d +n-Seite = Modellausdehnung (DOM1/LoD2), nicht das Spiegelbild der -n-Seite mit Ueberstand: "
            + ", ".join(f"z {p[0]:.1f} +n {p[4]:.2f}/-n {p[3]:.2f}" for p in mitte[:3]))
        chk(abs(p0[3] + (B_ + UE)) < 0.4, f"T3e -n traegt den Wolken-Ueberstand: Traufscheibe -n {p0[3]:.2f} (Soll {-(B_ + UE):.2f} +-0,4)")
        chk("FOTOLUECKE Dach Seite +n" in pr.stdout, "T3f Bericht nennt die Fotoluecke")
    else: chk(False, "T3b dach_profil.json fehlt: " + (pr.stdout.strip().splitlines() or [''])[-1][:200])
finally: shutil.rmtree(T, ignore_errors=True)
print("FEHLER gesamt:", sum(F)); sys.exit(1 if any(F) else 0)

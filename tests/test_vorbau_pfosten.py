#!/usr/bin/env python3
"""test_vorbau_pfosten.py - fester synthetischer Test fuer den Befund 'Bild-Vorbau Nord ohne Pfosten' aus Kettenlauf 1122w (24.11.2026), < 20 s, nur CPU.

Befund (modelle/schwabentor-1122/audit/neben_detail_vorbau_f00.jpg, Nutzer: "hatten wir doch mal fast perfekt"): im Foto stehen zwei Pfosten von der Galerie
zum Vordach, die Galerie ist darueber offen. Kette 1122w: ebenen_masse 'keine Pfosten belegt' -> Vordach + Raehm ohne Stuetze, getrennter Koerper ueber dem Bruestungskasten.
Ursache: Sammeltor 'Kantenpunkte im Band Holm..Raehm >= 100' (1122w: 94, duenn trianguliert), obwohl die zwei Pfostenhaufen klar waren (24 / 61 Punkte je 6 cm).
Teile:
  1 MESSEN    tools/ebenen_masse.py auf synthetischen Kantenpunkten wie 1122w (Kasten-Linien, 5 Konsolen, zwei duenne Pfostenhaufen, Band gesamt < 100 Punkte)
              -> zwei Pfosten bei u -3,45 / 4,24 (+- 0,05).
  2 ROT-PROBE dasselbe ohne Pfosten, aber mit waagrechtem Draht im Band -> keine Pfosten (Draht ist keine u-Spitze).
  3 BAUEN     bauteile.vorbauten_aus_json: kanten_mass ohne Pfosten + Sweep-Pfostenspalten (galerie.pfosten) -> Pfosten gebaut, Vorbau EIN Koerper;
              ohne beides -> Vordach getrennt (zeigt den Befund); Kanten-Pfosten haben Vorrang vor den Sweep-Spalten.
"""
import sys, os, json, subprocess, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); WURZEL = os.path.dirname(HIER); sys.path.insert(0, os.path.join(WURZEL, "tools"))
from pfade import temp_ordner
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def punkte(mit_pfosten, rng):
    P = []
    def add(u, w, z): P.append(np.c_[u, w, z])
    n_ = 4000; u_ = np.linspace(-3.8, 4.1, n_)
    for zl in (10.81, 12.07): add(u_, 1.24 + rng.normal(0, 0.01, n_), zl + rng.normal(0, 0.008, n_))       # Unter-/Oberkante Bruestungskasten
    for uk in (-3.5, -2.0, -0.5, 1.1, 2.7): add(rng.uniform(uk - 0.15, uk + 0.15, 300), 1.24 + rng.normal(0, 0.01, 300), 10.55 + rng.normal(0, 0.008, 300))   # Konsolen
    add(rng.uniform(-4.4, 5.1, 6000), rng.normal(0, 0.02, 6000), rng.uniform(8.3, 21.4, 6000))              # Wand
    if mit_pfosten:                                                                                         # duenn wie 1122w: 24 + 60 Punkte
        add(-3.45 + rng.normal(0, 0.012, 24), 1.25 + rng.normal(0, 0.02, 24), rng.uniform(15.6, 15.75, 24))
        add(4.24 + rng.normal(0, 0.012, 60), 1.22 + rng.normal(0, 0.02, 60), rng.uniform(12.6, 15.4, 60))
    else:
        add(rng.uniform(-3.8, 4.1, 80), 1.24 + rng.normal(0, 0.02, 80), 14.0 + rng.normal(0, 0.01, 80))     # Oberleitungsdraht quer durchs Band
    A = np.vstack(P); return np.c_[A[:, 0], A[:, 1], A[:, 2]]          # o=(0,0), d=(1,0), n=(0,1): x = u, y = w


def gruppe(km=None, pfosten_sweep=(-3.75, 4.47)):
    g = dict(u0=-4.0, u1=4.6, z0=10.0, z1=12.5, raster=0.25, w=[[1.2]], koerper=dict(u0=-4.0, u1=4.6, z0=10.0, z1=12.5, w_median=1.2),
             galerie=dict(z_dach=15.86, pfosten=list(pfosten_sweep), vordach=dict(z_traufe=16.66, z_anschluss=20.16, w_traufe=0.96)))
    if km: g["kanten_mass"] = km
    return g


def vb_json(pfad, gruppen):
    json.dump(dict(fassaden=[dict(id="f00", nr=0, o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], w_wand=0.0, gruppen=gruppen)]), open(pfad, "w"))


def messen(T, mit_pfosten):
    od = os.path.join(T, "pf" if mit_pfosten else "rot"); eb = os.path.join(od, "ebenen"); os.makedirs(os.path.join(od, "audit")); os.makedirs(eb)
    np.savez(os.path.join(eb, "sweep.npz"), P=punkte(mit_pfosten, np.random.default_rng(3)).astype(np.float32))
    json.dump(dict(ebenen=[dict(id="f00_vb0", sweep=os.path.join(eb, "sweep.npz"), o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], w_wand=0.0, zone=[-4.46, 5.18, 8.26, 21.46])]),
              open(os.path.join(eb, "ebenen.json"), "w"))
    vb_json(os.path.join(od, "audit", "vorbauten_auto.json"), [gruppe()]); open(os.path.join(od, "objekt.json"), "w").write("{}")
    r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(WURZEL, "tools", "ebenen_masse.py"), os.path.join(od, "objekt.json"), eb], capture_output=True, text=True)
    km = json.load(open(os.path.join(od, "audit", "vorbauten_auto.json")))["fassaden"][0]["gruppen"][0].get("kanten_mass") or {}
    return r, km


def main():
    T = temp_ordner("test_vorbau_pfosten_")
    print("1 MESSEN (duennes Band wie 1122w)")
    r, km = messen(T, True)
    pruef(r.returncode == 0 and "kasten" in km, f"Kasten aus Kanten gemessen (rc {r.returncode}) {r.stdout.strip()[-200:]}")
    pf = sorted(p_["u"] for p_ in km.get("pfosten") or [])
    pruef(len(pf) == 2 and abs(pf[0] + 3.45) < 0.05 and abs(pf[1] - 4.24) < 0.05, f"zwei Pfosten bei u -3,45 / 4,24 (gemessen {pf})")
    pruef((km.get("konsolen") or {}).get("anzahl") == 5, f"5 Konsolen unveraendert ({(km.get('konsolen') or {}).get('anzahl')})")
    print("2 ROT-PROBE (Draht statt Pfosten)")
    r2, km2 = messen(T, False)
    pruef("kasten" in km2 and not km2.get("pfosten"), f"keine Pfosten aus einem waagrechten Draht ({km2.get('pfosten')})")

    print("3 BAUEN")
    import bauteile
    from manifold3d import Manifold as M
    KM = dict(ausladung=1.24, kasten=dict(z_unten=10.81, z_oben=12.07, u0=-3.81, u1=4.14, breite=7.95),
              konsolen=dict(z_unten=10.55, anzahl=2, lage=[[-3.66, -3.36], [2.54, 2.84]], abstand=6.2))
    def bau(name, km_, sweep):
        p_ = os.path.join(T, f"bau_{name}.json"); vb_json(p_, [gruppe(km_, sweep)])
        k, bel = bauteile.vorbauten_aus_json(M(), p_)
        return len(k.decompose()), (bel[0].get("hinweis", "") if bel else ""), bel[0]["element"] if bel else ""
    n0, h0, e0 = bau("ohne", dict(KM), ())
    pruef(n0 > 1, f"Rot: ohne Kanten- und Sweep-Pfosten schwebt das Vordach (Koerper {n0}) - Befund 1122w")
    n1, h1, e1 = bau("sweep", dict(KM), (-3.75, 4.47))
    pruef(n1 == 1, f"Sweep-Pfostenspalten als Ersatz: Vorbau ein Koerper (Koerper {n1}); '{e1}'")
    pruef("Sweep-Pfostenspalten" in h1 and "2 Pfosten" in e1, "Ersatz im Beleg benannt (ANNAHME-Text, 2 Pfosten)")
    n2, h2, e2 = bau("kanten", dict(KM, pfosten=[dict(u=-3.45, breite=None), dict(u=4.0, breite=None)]), (-3.75, 4.47))
    pruef(n2 == 1 and "Sweep-Pfostenspalten" not in h2, f"Kanten-Pfosten haben Vorrang (Koerper {n2})")
    pruef(0.22 * 1000 / 87 >= 0.8, "Pfostenquerschnitt 0,22 m = 2,5 mm H0 >= 0,8 mm")
    print("FEHLER:", F); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())

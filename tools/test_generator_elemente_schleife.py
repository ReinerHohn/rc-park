#!/usr/bin/env python3
"""test_generator_elemente_schleife.py - BEWEIS (bekannte Wahrheit) fuer generator_elemente_schleife.py. Synthetisch, ohne Fotos (Foto-Tor = eigener Lauf auf Kaufhaus).
  A  Wahrheit = Haus + Erker (giebelbedeckt), Basis = Haus ohne Erker  -> Schleife findet ihn (Element ueberlappt die Wahrheitsbox >= 50 %), Restfeld-p90 sinkt
  A2 dasselbe mit Rangfolge UMGEKEHRT (--test-rangfolge): die richtige Familie steht an Rang >= 4 und wird trotzdem gefunden; Mehrfachtest-Aufschlag j >= 3 im Protokoll
  B  Wahrheit = Basis (nichts fehlt)                                     -> keine Cluster, nichts uebernommen
  C  erfundener Kandidat (Block an der Gegenwand, dort keine Wolke)      -> Tor lehnt ab (Grund im Protokoll)
  D  Cluster OHNE echtes Element (Punkthaufen im freien Raum, N Zufallsproben) -> Falschannahmerate gemessen und berichtet (Erwartung 0)
  E  Ruecksprung-Reihe (3 gleiche Rundbogenoeffnungen in der Wand)       -> bogenreihe/nische wird gefunden, Restfeld sinkt
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_generator_elemente_schleife.py [--zufall 8]
Ausgabe: Zahlen je Test; Exit 0 nur wenn A, A2, B, C, E bestehen und die Falschannahmerate D == 0.
"""
import sys, os, json, tempfile, argparse, io, contextlib, math
import numpy as np
TOOLS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, TOOLS)
import trimesh
from manifold3d import Manifold as M, CrossSection as C
import generator_elemente_schleife as GS, bauteil_element_wolke as BE

MASS = 87.0


def tm_aus(mf): return GS.aus_manifold(mf)


def haus():
    return M.cube((12, 8, 8)).translate((-6, -4, 0))


def erker_giebel():       # an +y-Wand (y = 4), Mitte x = 0
    k, _ = BE.koerper("giebel", dict(cx=0.0, cy=4.0, phi=math.pi / 2, w=2.4, tiefe=1.3, z0=3.0, z1=6.5, gh=1.0), M, C); return k


def wolke(tm, n_je_m2=120, sigma=0.03, seed=0):
    rng = np.random.default_rng(seed); S, _ = trimesh.sample.sample_surface(tm, int(tm.area * n_je_m2), seed=seed)
    return S + rng.normal(0, sigma, S.shape)


def lauf(ordner, P, base_tm, extra=()):
    os.makedirs(ordner, exist_ok=True); np.save(os.path.join(ordner, "wolke.npy"), P)
    s = os.path.join(ordner, "basis.stl"); GS.stl_speichern(base_tm, s, MASS)
    o = os.path.join(ordner, "objekt.json"); json.dump(dict(stl_massstab=MASS, bauteile=[dict(typ="rumpf_wolke", wolke=os.path.join(ordner, "wolke.npy"))]), open(o, "w"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        erg = GS.main([o, "--aus", os.path.join(ordner, "aus"), "--ohne-generator", "--start-stl", s, "--ohne-fotos", "--runden", "2", "--minuten-je-cluster", "2"] + list(extra))
    prot = [json.loads(l) for l in open(os.path.join(ordner, "aus", "protokoll.jsonl"))]
    return erg, prot, buf.getvalue()


def box_iou(lo1, hi1, lo2, hi2):
    lo = np.maximum(lo1, lo2); hi = np.minimum(hi1, hi2); i = np.prod(np.maximum(hi - lo, 0)); u = np.prod(hi1 - lo1) + np.prod(hi2 - lo2) - i; return i / u


def el_box(el):
    mf, _ = BE.koerper(el["familie"], el["p"], M, C, el.get("laeufe")); b = mf.bounding_box(); return np.array(b[:3]), np.array(b[3:])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--zufall", type=int, default=8); a = ap.parse_args(); erg_tests = {}
    wd = tempfile.mkdtemp(prefix="elsch_test_", dir="/media/oem/scan/rc-park_null") if os.path.isdir("/media/oem/scan/rc-park_null") else tempfile.mkdtemp()
    print("Arbeitsordner", wd)
    H = tm_aus(haus()); W = tm_aus(haus() + erker_giebel()); PW = wolke(W)
    e_lo, e_hi = np.array(erker_giebel().bounding_box()[:3]), np.array(erker_giebel().bounding_box()[3:])

    # A
    erg, prot, _ = lauf(os.path.join(wd, "A"), PW, H)
    ok = False; iou = 0.0
    for e in json.load(open(os.path.join(wd, "A", "aus", "objekt_mit_elementen.json")))["bauteile"][-1]["elemente"]:
        lo, hi = el_box(e); iou = max(iou, box_iou(lo, hi, e_lo, e_hi))
    p90a, p90b = erg["start"]["restfeld"]["p90"], erg["ende"]["p90"]; fern0, fern1 = erg["start"]["restfeld"]["fern"], erg["ende"]["fern"]
    nat = [(p["rang"], p["familie"], p["entscheidung"]) for p in prot if p.get("typ") == "kandidat" and p.get("runde") == 1 and p["cluster"] == "R1C0"]
    erg_tests["A"] = iou >= 0.5 and fern1 < 0.3 * fern0
    print(f"A  Erker gefunden: IoU {iou:.2f} (>= 0.5), ferne Punkte {fern0} -> {fern1}, p90 {p90a} -> {p90b}; Rangfolge Cluster R1C0: {nat}; uebernommen {len(erg['uebernommen'])}  -> {'OK' if erg_tests['A'] else 'FEHLER'}")
    # A2
    erg2, prot2, _ = lauf(os.path.join(wd, "A2"), PW, H, ["--test-rangfolge", "umgekehrt"]); iou2 = 0.0
    for e in json.load(open(os.path.join(wd, "A2", "aus", "objekt_mit_elementen.json")))["bauteile"][-1]["elemente"]:
        lo, hi = el_box(e); iou2 = max(iou2, box_iou(lo, hi, e_lo, e_hi))
    kk = [p for p in prot2 if p.get("typ") == "kandidat" and p.get("runde") == 1 and p["cluster"] == "R1C0"]
    ang = [(p["rang"], p["familie"], p["anzahl_vorher_geprueft"], p["aufschlag"], p["entscheidung"]) for p in kk]
    spaet = [p for p in kk if p["familie"] == "giebel" and p["entscheidung"] == "uebernommen"]
    erg_tests["A2"] = iou2 >= 0.5 and bool(spaet) and spaet[0]["rang"] >= 3 and spaet[0]["tor"]["j"] >= 3 and len(kk) >= 4
    print(f"A2 umgekehrte Rangfolge: IoU {iou2:.2f}; (rang, familie, j, aufschlag, entscheidung): {ang}  -> {'OK' if erg_tests['A2'] else 'FEHLER'}")
    # B
    ergb, _, _ = lauf(os.path.join(wd, "B"), wolke(H), H)
    erg_tests["B"] = len(ergb["uebernommen"]) == 0 and ergb["start"]["cluster"] == 0
    print(f"B  nichts fehlt: Cluster {ergb['start']['cluster']}, uebernommen {len(ergb['uebernommen'])}  -> {'OK' if erg_tests['B'] else 'FEHLER'}")
    # C erfundener Kandidat: Block an der -y-Wand, dort keine Wolke eines Elements; Cluster = der echte Erker
    mod = GS.Modell(H); r = mod.res(PW); cl = GS.cluster_finden(PW, r, 0.0, +1)
    c = cl[0]; fake = dict(familie="block", p=dict(cx=0.0, cy=-4.0, phi=-math.pi / 2, w=2.4, tiefe=1.3, z0=3.0, z1=6.5), laeufe=None)
    mf, sch = BE.koerper("block", fake["p"], M, C); fake.update(mf=mf, schnitt=sch, tm=tm_aus(mf)); S, _ = trimesh.sample.sample_surface(fake["tm"], 3000, seed=1)
    from scipy.spatial import cKDTree
    d2, _ = cKDTree(PW).query(S); fake["stuetz"] = GS.stuetzanteil(fake["tm"], S, d2, mod, sch)
    fake["dc"] = float(np.minimum(cKDTree(S).query(PW[c["idx"]])[0], 0.5).mean())
    okC, grundC, infoC = GS.tor(fake, c, mod, PW, r, M, C, 0, None, wd, "fake", None)
    erg_tests["C"] = not okC
    print(f"C  erfundener Block an der Gegenwand: {'abgelehnt' if not okC else 'ANGENOMMEN'} - {grundC}  -> {'OK' if erg_tests['C'] else 'FEHLER'}")
    # D Falschannahmerate
    angen = 0; gepr = 0; cl_n = 0
    for sd in range(a.zufall):
        rng = np.random.default_rng(100 + sd); Pn = np.vstack([wolke(H, seed=sd), rng.uniform([-1, 4.8, 3], [0.2, 6.0, 4.2], (700, 3))])     # Punkthaufen 0,8..2 m vor der +y-Wand (kein Flaechenelement)
        e_, p_, _ = lauf(os.path.join(wd, f"D{sd}"), Pn, H); k_ = [p for p in p_ if p.get("typ") == "kandidat" and p["entscheidung"] != "nicht geprueft"]
        cl_n += e_["start"]["cluster"]; gepr += len(k_); angen += len(e_["uebernommen"])
        print(f"   D{sd}: Cluster {e_['start']['cluster']}, Kandidaten geprueft {len(k_)}, uebernommen {len(e_['uebernommen'])}", flush=True)
    erg_tests["D"] = angen == 0 and cl_n > 0
    print(f"D  ohne echtes Element: {a.zufall} Proben, {cl_n} Cluster, {gepr} Kandidaten geprueft, {angen} angenommen -> Falschannahmerate {angen}/{max(cl_n, 1)} je Cluster  -> {'OK' if erg_tests['D'] else 'FEHLER'}")
    # E Bogenreihe als Ruecksprung
    reihe, _ = BE.koerper("bogenreihe", dict(cx=0.0, cy=-4.0, phi=-math.pi / 2, tiefe=0.6, z_unten=1.0, z_oben=4.0, stich=0.2), M, C, [[-3.0, 1.6], [-0.8, 1.6], [1.4, 1.6]])
    T = tm_aus(haus() - reihe); ergE, protE, _ = lauf(os.path.join(wd, "E"), wolke(T), H)
    famE = [e["familie"] for e in json.load(open(os.path.join(wd, "E", "aus", "objekt_mit_elementen.json")))["bauteile"][-1]["elemente"]]
    erg_tests["E"] = bool(famE) and ergE["ende"]["fern"] < 0.5 * ergE["start"]["restfeld"]["fern"]
    print(f"E  Ruecksprung-Reihe: Elemente {famE}, ferne Punkte {ergE['start']['restfeld']['fern']} -> {ergE['ende']['fern']}  -> {'OK' if erg_tests['E'] else 'FEHLER'}")
    print("ERGEBNIS", erg_tests)
    sys.exit(0 if all(erg_tests.values()) else 1)


if __name__ == "__main__":
    main()

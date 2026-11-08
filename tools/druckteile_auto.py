#!/usr/bin/env python3
"""druckteile_auto.py - GENERISCH: H0-Modell (STL in mm) automatisch in Teile schneiden, die in den Bauraum passen, aushoehlen, Stiftbohrungen (2026-11-05).

Anlass: Kaufhaus 1:87 = 308 x 295 x 233 mm, Bambu P1S 256 x 256 x 256 -> 'Nothing to be sliced'. teile_testdruck.py hatte Martinstor-Handschnitte.
Verfahren (keine Handwerte):
  1. Drehung um z (0..89 Grad, 1 Grad) mit der kleinsten Teilezahl (Bauraum minus Bettrand), bei Gleichstand kleinste Grundflaeche.
  2. Rekursiver Guillotine-Schnitt: ein Stueck, das nicht passt, wird senkrecht entlang der am meisten ueberstehenden Achse geteilt; Lage im zulaessigen
     Fenster (beide Seiten erreichbar mit ceil(L/b) Teilen, jede Seite >= `--min-teil` mm) dort, wo der Querschnitt DIESES Stuecks am kleinsten ist
     (wenig Detail durchschnitten). Jede Haelfte wird fuer sich weiter geteilt (kein Gitterschnitt -> keine Splitter wie 0,8-mm-Teil im 1. Versuch).
  3. Aushoehlen (`--hohl` mm Wand, 0 = massiv): Innenraum = Schnitt des Koerpers mit seinen 26 Verschiebungen um +-t (Teilmenge des Koerpers, Aussenhaut
     bleibt unveraendert), unten offen (Stuetzen von der Platte erreichbar), an jeder Schnittebene massive Platte +-`--naht` mm (Klebeflaeche + Stifte).
  4. Stiftbohrungen: je Schnittflaeche 2 Punkte im Querschnitt mit >= `--rand` mm Randabstand, moeglichst weit auseinander; Bohrung d = stift + 2*spiel,
     Tiefe `--tiefe` in BEIDE Teile; lose Stifte (Drucklehre 2026-11-03: nie Zapfen unter breiter Flaeche).
  5. Pruefung je Teil: Bauraum, wasserdicht, Koerperzahl, Volumen; mit --slice je Teil tools/bambu_slice.py (--stuetzen: Baumstuetzen).
Ausgabe: <aus>/teil_<k>.stl + stift.stl + teile.json.

  /media/oem/scan/venv-seg/bin/python -I tools/druckteile_auto.py <modell_mm.stl> --aus DIR [--hohl 3] [--slice] [--stuetzen]
"""
import os, sys, json, math, argparse, subprocess
import numpy as np, trimesh
from manifold3d import Manifold as M, Mesh as MM, OpType
from shapely.geometry import Point
from shapely.ops import unary_union

GROSS = 1e4


def zu_manifold(m):
    return M(MM(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


def zu_trimesh(k):
    me = k.to_mesh(); return trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts), process=False)


def querschnitt(m, achse, wert):
    n = np.zeros(3); n[achse] = 1.0; o = np.zeros(3); o[achse] = wert
    s = m.section(plane_origin=o, plane_normal=n)
    if s is None: return 0.0, None
    p2, T = s.to_2D(); return float(sum(p.area for p in p2.polygons_full)), (p2, T)


def box(lo, hi):
    lo = np.asarray(lo, float); hi = np.asarray(hi, float); return M.cube(tuple(hi - lo)).translate(tuple(lo))


def teilen(K, lo, hi, b, a, schnitte, blaetter, tiefe=0):
    """Stueck K ^ box(lo, hi) rekursiv teilen; schnitte += (achse, lage, lo, hi), blaetter += (lo, hi)."""
    S = K ^ box(lo, hi)
    if S.is_empty(): return
    tm = zu_trimesh(S); e0, e1 = tm.bounds; ext = e1 - e0; ueber = ext[:2] / np.array(b[:2])
    if (ueber <= 1 + 1e-9).all(): blaetter.append((np.array(lo, float), np.array(hi, float))); return
    ach = int(np.argmax(ueber)); L = ext[ach]; n = math.ceil(L / b[ach]); bb = b[ach]
    best = None
    for k in range(1, n):
        f0 = max(e0[ach] + a.min_teil, e1[ach] - (n - k) * bb); f1 = min(e0[ach] + k * bb, e1[ach] - a.min_teil)
        if f0 > f1: continue
        for x in np.arange(f0, f1 + 1e-6, 1.0):
            q = querschnitt(tm, ach, float(x))[0]
            if q <= 0 or (best is not None and q >= best[0]): continue
            hl = np.array(hi, float); hl[ach] = x; lr = np.array(lo, float); lr[ach] = x; ok_ = True
            for A in (S ^ box(lo, hl), S ^ box(lr, hi)):                                # jede Seite: Volumenanteil + Mindestbreite (keine Splitter)
                if A.is_empty() or A.volume() < a.min_anteil * S.volume(): ok_ = False; break
                bb_ = np.array(A.bounding_box()); bl, bh = bb_[:3], bb_[3:]
                if ((bh - bl)[:2] < a.min_teil).any(): ok_ = False; break
            if ok_: best = (q, float(x), (f0, f1))
    if best is None: sys.exit(f"kein zulaessiges Schnittfenster (Achse {'xy'[ach]}, Laenge {L:.1f} mm)")
    q, x, fen = best; print(f"  {'  ' * tiefe}Schnitt {'xy'[ach]} = {x:.0f} mm (Stueck {ext[0]:.0f} x {ext[1]:.0f}, Fenster {fen[0]:.0f}-{fen[1]:.0f}, Querschnitt {q:.0f} mm2)", flush=True)
    schnitte.append(dict(achse=ach, lage=x, lo=list(map(float, lo)), hi=list(map(float, hi)), querschnitt_mm2=round(q)))
    hi_l = np.array(hi, float); hi_l[ach] = x; lo_r = np.array(lo, float); lo_r[ach] = x
    teilen(K, lo, hi_l, b, a, schnitte, blaetter, tiefe + 1); teilen(K, lo_r, hi, b, a, schnitte, blaetter, tiefe + 1)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("--aus", required=True)
    ap.add_argument("--bauraum", type=float, nargs=3, default=[256, 256, 256]); ap.add_argument("--rand-bett", type=float, default=10.0, help="Rand je Seite (Brim 8 mm + 2)")
    ap.add_argument("--min-teil", type=float, default=20.0, help="kleinste Teilbreite an einem Schnitt (mm)")
    ap.add_argument("--min-anteil", type=float, default=0.15, help="kleinster Volumenanteil je Schnittseite")
    ap.add_argument("--hohl", type=float, default=3.0, help="Wandstaerke beim Aushoehlen (mm), 0 = massiv"); ap.add_argument("--naht", type=float, default=5.0)
    ap.add_argument("--stift", type=float, default=3.0); ap.add_argument("--spiel", type=float, default=0.15); ap.add_argument("--tiefe", type=float, default=6.0)
    ap.add_argument("--rand", type=float, default=4.0, help="Mindestabstand Bohrung zum Querschnittsrand (mm)")
    ap.add_argument("--slice", action="store_true"); ap.add_argument("--stuetzen", action="store_true"); ap.add_argument("--fuellung", default="12%")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    m0 = trimesh.load(a.stl); b = [a.bauraum[0] - 2 * a.rand_bett, a.bauraum[1] - 2 * a.rand_bett, a.bauraum[2] - a.rand_bett]
    if m0.extents[2] > b[2]: sys.exit(f"Hoehe {m0.extents[2]:.1f} mm > Bauraum {b[2]:.1f} mm: zusaetzlich waagerecht schneiden (noch nicht eingebaut)")
    best = None; H = m0.convex_hull.vertices
    for w in range(0, 90):
        R = trimesh.transformations.rotation_matrix(math.radians(w), [0, 0, 1]); V = trimesh.transform_points(H, R); e = V.max(0) - V.min(0)
        key = (math.ceil(e[0] / b[0]) * math.ceil(e[1] / b[1]), e[0] * e[1])
        if best is None or key < best[0]: best = (key, w)
    w = best[1]; R = trimesh.transformations.rotation_matrix(math.radians(w), [0, 0, 1]); m = m0.copy(); m.apply_transform(R); m.apply_translation(-m.bounds[0])
    e = m.extents; print(f"Drehung {w} Grad: {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm, Bauraum nutzbar {b[0]:.0f} x {b[1]:.0f} x {b[2]:.0f}", flush=True)
    K = zu_manifold(m); schnitte, blaetter = [], []
    teilen(K, [-1, -1, -1], [e[0] + 1, e[1] + 1, e[2] + 1], b, a, schnitte, blaetter)
    V0 = K.volume()
    if a.hohl > 0:
        t = a.hohl; unten = (K ^ box([-GROSS, -GROSS, 0], [GROSS, GROSS, 2 * t])).translate((0, 0, -2 * t)); Ke = K + unten
        I = Ke
        for dx in (-t, 0, t):
            for dy in (-t, 0, t):
                for dz in (-t, 0, t):
                    if dx or dy or dz: I = I ^ Ke.translate((dx, dy, dz))
        naht = []
        for s in schnitte:
            lo = np.array(s["lo"]); hi = np.array(s["hi"]); lo[s["achse"]] = s["lage"] - a.naht; hi[s["achse"]] = s["lage"] + a.naht; naht.append(box(lo, hi))
        if naht: I = I - M.batch_boolean(naht, OpType.Add)
        K = K - I; print(f"Aushoehlen: Wand {t} mm, Naht +-{a.naht} mm: Volumen {V0 / 1e3:.0f} -> {K.volume() / 1e3:.0f} cm3", flush=True)
    bohr = []; d_b = a.stift + 2 * a.spiel
    for s in schnitte:
        ach, x = s["achse"], s["lage"]; S = zu_trimesh(K ^ box(s["lo"], s["hi"])); q, pt = querschnitt(S, ach, x)
        if pt is None: s["bohrungen"] = 0; continue
        p2, T = pt; poly = unary_union(list(p2.polygons_full)).buffer(-a.rand)
        if poly.is_empty: print(f"    Schnitt {'xy'[ach]}={x:.0f}: Querschnitt zu duenn fuer Bohrungen -> nur kleben"); s["bohrungen"] = 0; continue
        gx, gy = np.meshgrid(np.linspace(poly.bounds[0], poly.bounds[2], 80), np.linspace(poly.bounds[1], poly.bounds[3], 80))
        P = np.array([(u, v) for u, v in zip(gx.ravel(), gy.ravel()) if poly.contains(Point(u, v))])
        if len(P) < 2: s["bohrungen"] = 0; continue
        i, j = np.unravel_index(np.argmax(((P[:, None] - P[None]) ** 2).sum(-1)), (len(P), len(P)))
        for qq in (P[i], P[j]):
            X = trimesh.transform_points(np.array([[qq[0], qq[1], 0.0]]), T)[0]
            zyl = M.cylinder(2 * a.tiefe, d_b / 2, d_b / 2, 24).translate((0, 0, -a.tiefe)); zyl = zyl.rotate((0, 90, 0)) if ach == 0 else zyl.rotate((-90, 0, 0))
            bohr.append(zyl.translate(tuple(X)))
        s["bohrungen"] = 2; print(f"    Schnitt {'xy'[ach]}={x:.0f}: 2 Bohrungen d {d_b:.2f} mm, Tiefe {a.tiefe} mm je Seite, Abstand {np.linalg.norm(P[i] - P[j]):.0f} mm", flush=True)
    if bohr: K = K - M.batch_boolean(bohr, OpType.Add)
    teile = []
    for k, (lo, hi) in enumerate(blaetter):
        t_ = K ^ box(lo, hi)
        if t_.is_empty(): continue
        tm = zu_trimesh(t_); tm.apply_translation(-tm.bounds[0]); p = os.path.join(a.aus, f"teil_{k}.stl"); tm.export(p)
        ok = bool((tm.extents[:2] <= np.array(b[:2]) + 1e-6).all() and tm.extents[2] <= b[2])
        teile.append(dict(datei=p, masse_mm=tm.extents.round(1).tolist(), wasserdicht=bool(tm.is_watertight), volumen_cm3=round(tm.volume / 1000, 1), passt=ok,
                          koerper=sum(1 for c in tm.split(only_watertight=False) if c.volume > 0), hohlraeume=sum(1 for c in tm.split(only_watertight=False) if c.volume <= 0)))
        print(f"  teil_{k}: {tm.extents.round(1)} mm, {tm.volume / 1000:.0f} cm3, wasserdicht {tm.is_watertight}, Koerper {teile[-1]['koerper']}, geschlossene Hohlraeume {teile[-1]['hohlraeume']}, passt {ok}", flush=True)
    stift = trimesh.creation.cylinder(radius=a.stift / 2, height=2 * a.tiefe - 1.0, sections=24); stift.apply_translation((0, 0, stift.extents[2] / 2)); stift.export(os.path.join(a.aus, "stift.stl"))
    erg = dict(eingabe=os.path.abspath(a.stl), drehung_grad=w, schnitte=schnitte, stifte_anzahl=len(bohr) // 2, stift_mm=a.stift, spiel_mm=a.spiel, hohl_mm=a.hohl,
               volumen_massiv_cm3=round(V0 / 1e3, 1), teile=teile, quelle="druckteile_auto.py (generisch: Drehung, rekursiver Schnitt nach kleinstem Querschnitt, Aushoehlen)")
    if a.slice:
        for t in teile:
            cmd = [sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bambu_slice.py"), t["datei"].replace(".stl", ".gcode.3mf"), t["datei"], "--fuellung", a.fuellung]
            r = subprocess.run(cmd + (["--stuetzen"] if a.stuetzen else []), capture_output=True, text=True)
            t["slice_ok"] = r.returncode == 0; t["slice"] = (r.stdout.strip().splitlines() or [r.stderr[-300:]])[-1][:400]
            try: t.update(json.loads(t["slice"]))
            except Exception: pass
            print(f"  slice {os.path.basename(t['datei'])}: {'ok' if t['slice_ok'] else 'FEHLER'} {t['slice'][:200]}", flush=True)
        g = [float(t.get("gramm") or 0) for t in teile]; erg["gramm_summe"] = round(sum(g), 1); print(f"Filament gesamt {sum(g):.0f} g", flush=True)
    json.dump(erg, open(os.path.join(a.aus, "teile.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

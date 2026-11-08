#!/usr/bin/env python3
"""anbau_verbinden.py - PROTOTYP (5.11.): allgemeine Druckregel fuer Anbauteile ohne Kontakt (Figuren, Zier, Erkerteile, Spitzen).
Jeder Teilkoerper ausser dem groessten: Splitter (< --min-vol m3) -> verwerfen; sonst Netz reparieren (Hohlraeume fuellen, notfalls konvexe Huelle je Teil
NICHT - Form bleibt), dann Konsole = Huelle(untere --konsole-anteil der Teilpunkte + dieselben Punkte bis --eintauchen m hinter die naechste Flaeche des
Hauptkoerpers verschoben) und alles vereinigen. Ziel: 1 Koerper, wasserdicht; Formaenderung nur hinter/unter dem Teil.
  /home/oem/.venvs/rcpark/bin/python -I tools/anbau_verbinden.py ein.stl aus.stl [--massstab 87]
"""
import argparse, numpy as np, trimesh, manifold3d as mf


def zu_mf(t): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(t.vertices, np.float32), tri_verts=np.asarray(t.faces, np.uint32)))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus"); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--min-vol", type=float, default=1e-3); ap.add_argument("--konsole-anteil", type=float, default=0.2); ap.add_argument("--eintauchen", type=float, default=0.1)
    a = ap.parse_args(argv); f = a.massstab / 1000.0                                                 # mm -> m
    m = trimesh.load(a.ein); teile = sorted(m.split(only_watertight=False), key=lambda x: -abs(x.volume)); haupt = teile[0]
    H = zu_mf(haupt) if haupt.is_watertight else None
    if H is None or H.status() != mf.Error.NoError: raise SystemExit("Hauptkoerper nicht wasserdicht - erst Druckreparatur")
    from trimesh.proximity import ProximityQuery
    pq = ProximityQuery(haupt); erg = H; n_v, n_k = 0, 0
    for t in teile[1:]:
        vol = abs(t.volume) * f ** 3
        if vol < a.min_vol: n_v += 1; continue
        if not t.is_watertight:
            t = t.copy(); trimesh.repair.fill_holes(t); trimesh.repair.fix_normals(t)
            if not t.is_watertight: t = t.convex_hull; print(f"  Teil {np.round(t.bounds.mean(0) * f, 1)}: nicht reparierbar -> konvexe Huelle")
        T = zu_mf(t); V = t.vertices; z = V[:, 2]; unten = V[z <= z.min() + a.konsole_anteil * (z.max() - z.min())]
        cp, dist, _ = pq.on_surface(unten); rich = cp - unten; L = np.linalg.norm(rich, axis=1, keepdims=True); rich = rich / np.maximum(L, 1e-9)
        ziel = cp + rich * (a.eintauchen / f)
        K = mf.Manifold.hull_points(np.vstack([unten, ziel]).tolist()); erg = erg + T + K; n_k += 1
        print(f"  Teil bei {np.round(t.bounds.mean(0) * f, 1)} m, {vol:.3f} m3, Abstand zur Wand {dist.min() * f:.2f}..{dist.max() * f:.2f} m -> Konsole")
    R = erg.to_mesh(); out = trimesh.Trimesh(np.asarray(R.vert_properties[:, :3], np.float32).astype(float), R.tri_verts, process=True)
    if not out.is_watertight:                                                                         # float32-Splitter wie baukasten_gen Druckreparatur (Volumenaenderung < 0,1 %%)
        v0 = erg.volume(); out.merge_vertices(digits_vertex=3); out.update_faces(out.nondegenerate_faces(height=1e-4)); out.remove_unreferenced_vertices(); trimesh.repair.fill_holes(out)
        print(f"  Druckreparatur: wasserdicht {out.is_watertight}, Volumen {abs(out.volume) / v0 - 1:+.2e}")
    teile_ = [x for x in out.split(only_watertight=False) if abs(x.volume) * f ** 3 >= 1e-6]                 # Nullvolumen-Reste (entartete Flaechen) weg
    if len(teile_) < len(out.split(only_watertight=False)): out = trimesh.util.concatenate(teile_); print(f"  Nullvolumen-Reste entfernt -> wasserdicht {out.is_watertight}")
    out.export(a.aus)
    print(f"{n_k} Teile angebunden, {n_v} Splitter verworfen -> Koerper {len(erg.decompose())}, wasserdicht {out.is_watertight} -> {a.aus}")


if __name__ == "__main__":
    main()

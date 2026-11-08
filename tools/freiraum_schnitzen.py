#!/usr/bin/env python3
"""freiraum_schnitzen.py - PROTOTYP (Stand 5.11.): Modell um den gesehenen Freiraum verkleinern (Space Carving gegen das Generatormodell).

Liest die verletzenden Strahlen aus freiraum_pruefen.py (--strahlen-npz) und schneidet entlang jedes Strahls das Stueck vom ersten Modelleintritt bis
--rand m vor dem gesehenen Punkt aus. Gerastert in Voxel (--voxel), geschnitten wird nur, wo >= --min-kameras VERSCHIEDENE Kameras durchsehen
(eine Kamera allein = Rauschen/Spiegelung). Allgemein: Durchgaenge, Arkadentiefe, Nischen, ohne Bauteilregel.
Noch NICHT im Generator (erst nach Laufende null5i, mit beleg + Pruefstand-Merkmal). Ausgabe: STL im selben Massstab wie die Eingabe.
  /home/oem/.venvs/rcpark/bin/python -I tools/freiraum_schnitzen.py <ein.stl> <strahlen.npz> <aus.stl> [--voxel 0.25] [--min-kameras 3] [--zmax Z]
"""
import argparse, numpy as np, trimesh, manifold3d as mf


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("npz"); ap.add_argument("aus"); ap.add_argument("--voxel", type=float, default=0.25)
    ap.add_argument("--min-kameras", type=int, default=3); ap.add_argument("--schritt", type=float, default=0.08); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--zmax", type=float, default=1e9, help="nur unterhalb dieser Hoehe schneiden (m) - z. B. Dach ausnehmen, solange Foto/LoD2 strittig")
    a = ap.parse_args(argv); Z = np.load(a.npz); C, D, t0, t1, kam = Z["C"], Z["d"], Z["t0"], Z["t1"], Z["kam"]
    vox = {}
    for c, d, s, e, k in zip(C, D, t0, t1, kam):
        if e <= s: continue
        p = c + d * np.arange(s, e, a.schritt)[:, None]; p = p[p[:, 2] < a.zmax]
        for q in {tuple(x) for x in np.floor(p / a.voxel).astype(np.int64)}: vox.setdefault(q, set()).add(int(k))
    V = np.array([q for q, ks in vox.items() if len(ks) >= a.min_kameras], np.int64)
    print(f"{len(vox)} durchsehene Voxel, davon {len(V)} mit >= {a.min_kameras} Kameras ({len(V) * a.voxel ** 3:.1f} m3)")
    m = trimesh.load(a.stl); f = 1000.0 / a.massstab
    M = mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32))); v0 = M.volume()
    w = a.voxel * f * 1.001; cubes = [mf.Manifold.cube([w, w, w]).translate(list((q * a.voxel) * f)) for q in V]
    if cubes: M = M - mf.Manifold.batch_boolean(cubes, mf.OpType.Add)
    R = M.to_mesh(); out = trimesh.Trimesh(R.vert_properties[:, :3], R.tri_verts)
    out.export(a.aus); print(f"Volumen {v0 * (a.massstab / 1000) ** 3 / a.massstab ** 0 :.0f} -> {M.volume() * (a.massstab / 1000) ** 3:.0f} m3 (Modellmass), Koerper {len(M.decompose())} -> {a.aus}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""kh_dicht_viewer.py - dichte Wolke (tools/dicht_handy.py rechnen) als selbstenthaltene 3D-HTML (three.js Punkte, Fotofarben).

  /media/oem/scan/venv-seg/bin/python -I tools/kh_dicht_viewer.py <dicht_ordner> <ausgabe.html> [--titel TEXT] [--stl modell.stl --stl-skala 0.087 [--stl-name TEXT]]
Optional --stl: Modell-Netz als zusaetzliche Ebene (Skala auf Meter, z.B. 1:87-STL in mm -> 0.087), je Knoten Abweichung zur Wolke (Median-Abstand der Wolkenpunkte
in 0,5 m Umgebung laengs der Normalen: rot = Wolke ausserhalb/vor dem Modell, blau = Wolke innerhalb = Modell steht vor der Wolke, grau = zu wenig Wolkenpunkte = LUECKE, kein Fehler).
Liest <dicht_ordner>/stapel/<tag>_modell.npy (N,3 float32, Meter im Modellrahmen, z oben) + <tag>_farben.npy (N,3 uint8) + <tag>_bericht.json.
Positionen werden je Ebene auf uint16 quantisiert (Spanne/65535, bei 40 m unter 1 mm), Farben als uint8; Seite < 16 MB.
Nichts Objektspezifisches: Titel und Ordner kommen vom Aufrufer. Die Achsen sind Modellachsen, KEINE Himmelsrichtungen.
"""
import sys, os, json, glob, base64, argparse
import numpy as np

VORLAGE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kh_dicht_viewer_vorlage.html"), encoding="utf-8").read()


def ebene(npy_modell):
    tag = os.path.basename(npy_modell)[:-len("_modell.npy")]
    p = np.load(npy_modell).astype(np.float64); c = np.load(npy_modell.replace("_modell.npy", "_farben.npy")).astype(np.uint8)
    assert p.ndim == 2 and p.shape[1] == 3 and c.shape == p.shape, (p.shape, c.shape)
    ok = np.isfinite(p).all(1); p, c = p[ok], c[ok]
    lo = p.min(0); sp = np.maximum(p.max(0) - lo, 1e-6)
    q = np.rint((p - lo) / sp * 65535).astype("<u2")
    pk = base64.b64encode(q.tobytes()).decode(); ck = base64.b64encode(c.tobytes()).decode()
    return dict(tag=tag, an=not tag.startswith("unsicher"), n=int(len(p)), lo=lo.tolist(), spanne=sp.tolist(), pos=pk, farbe=ck)


def netz_ebene(stl, skala, name, wolke, radius=0.5, min_n=8, max_edge=0.7):
    import trimesh
    from scipy.spatial import cKDTree
    m = trimesh.load(stl); m.apply_scale(skala); v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=max_edge)
    m = trimesh.Trimesh(v, f, process=False); V = np.asarray(m.vertices); N = np.asarray(m.vertex_normals)
    T = cKDTree(wolke); nb = T.query_ball_point(V, r=radius); off = np.full(len(V), np.nan); n_pt = np.zeros(len(V), int)
    for i, ids in enumerate(nb):
        n_pt[i] = len(ids)
        if len(ids) >= min_n: off[i] = float(np.median((wolke[ids] - V[i]) @ N[i]))
    col = np.full((len(V), 3), 150, np.uint8); ok = np.isfinite(off); t = np.clip(off[ok] / 0.5, -1, 1)
    r = np.where(t > 0, 255, 255 * (1 + t)); b = np.where(t < 0, 255, 255 * (1 - t)); g = 255 * (1 - np.abs(t)) * 0.9 + 30 * np.abs(t)
    col[ok] = np.stack([r, g, b], 1).astype(np.uint8)
    st = dict(vertices=int(len(V)), mit_wolke=int(ok.sum()), luecke_anteil=float(1 - ok.mean()), median_abw_m=float(np.nanmedian(np.abs(off))), p90_abw_m=float(np.nanpercentile(np.abs(off), 90)))
    return dict(name=name, pos=base64.b64encode(V.astype("<f4").tobytes()).decode(), idx=base64.b64encode(np.asarray(m.faces).astype("<u4").tobytes()).decode(),
                farbe=base64.b64encode(col.tobytes()).decode(), nv=int(len(V)), nf=int(len(m.faces)), stat=st)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("ausgabe"); ap.add_argument("--titel", default="Dichte Wolke")
    ap.add_argument("--stl", action="append", default=[], help="mehrfach moeglich; das LETZTE ist sichtbar, die anderen ausgeschaltet"); ap.add_argument("--stl-skala", type=float, default=1.0); ap.add_argument("--stl-name", action="append", default=[])
    a = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(a.ordner, "stapel", "*_modell.npy")))
    assert fs, "keine Stapel unter " + a.ordner
    E = [ebene(f) for f in fs]
    NZ = []
    if a.stl:
        W = np.concatenate([np.load(f).astype(np.float64) for f in fs if os.path.basename(f).startswith("sicher")])
        for k, stl in enumerate(a.stl):
            nm = a.stl_name[k] if k < len(a.stl_name) else os.path.basename(stl); n = netz_ebene(stl, a.stl_skala, nm, W); n["an"] = (k == len(a.stl) - 1); NZ.append(n); print("Netz:", nm, n["stat"])
    html = VORLAGE.replace("/*DATEN*/[]", json.dumps(E)).replace("/*NETZE*/[]", json.dumps(NZ)).replace("@@TITEL@@", a.titel)
    open(a.ausgabe, "w", encoding="utf-8").write(html)
    print(f"{a.ausgabe}: {len(E)} Ebenen, {sum(e['n'] for e in E)} Punkte, {os.path.getsize(a.ausgabe) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""nachbarn_modellrahmen.py - LoD2-Nachbargebaeude (ohne das Objekt selbst) als Netz im Modell-/SfM-Rahmen (Nutzer 10.11.: "wo ein anderes Haus steht,
kann ich keine Fotos machen" -> Brandwaende duerfen weder als Schwaeche zaehlen noch auf den Fotoplan).

Quelle: objekt.json "lod2" (gml, id des Objekts) + "rahmen"; Transformation SfM <-> LoD2 aus georef.json von tools/foto_luecken.py
(Grundriss-Anpassung, Beweiswerte dort: IoU, Umrissabstand ~1 m -> Brandwand-Test mit Toleranz, s. brandwand()).
  /media/oem/scan/venv-seg/bin/python -I tools/nachbarn_modellrahmen.py modelle/<objekt>/objekt.json --georef <foto_luecken>/georef.json --aus <nachbarn.ply> [--radius 70]
Standardablage (generisch je Objekt): /media/oem/scan/rc-park_daten/<objekt>/nachbarn_modellrahmen.ply

brandwand(P, N, nachbar_mesh, weite): Punkte P (Modellrahmen) mit Normalen N, deren Strahl entlang der Normalen das Nachbarnetz nach < weite m trifft
(oder die schon im Nachbarn liegen) = angebaute Wand. Ueber dem Nachbardach trifft der Strahl nichts -> bleibt frei (sichtbar).
"""
import os, sys, json, argparse
import numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def nachbarn_netz(objp, georef, radius=70.0):
    import foto_luecken as FL
    obj = json.load(open(objp)); g = FL.Georef(json.load(open(georef)))
    _, nachbar = FL.lod2_laden(obj, radius=radius)
    mL = FL.lod2_mesh_L([p for p in nachbar if p], g)
    V = g.L_nach_sfm(np.asarray(mL.vertices))
    return trimesh.Trimesh(V, np.asarray(mL.faces), process=True)


def brandwand(P, N, nachbar, weite=2.0, start=0.3, min_d=None):
    """Bool je Punkt: Normalenstrahl trifft Nachbarnetz innerhalb weite m (angebaute Wand), oder Punkt liegt im Nachbarn (Strahl nach innen trifft
    Rueckseite der Nachbarflaeche - ebenfalls Treffer innerhalb weite)."""
    if nachbar is None or len(P) == 0: return np.zeros(len(P), bool)
    P = np.asarray(P, np.float64); N = np.asarray(N, np.float64); N = N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)
    out = np.zeros(len(P), bool); seitlich = np.abs(N[:, 2]) < 0.7     # nur Wandflaechen; Dach-/Bodenflaechen sind keine Brandwaende
    idx = np.nonzero(seitlich)[0]
    if len(idx) == 0: return out
    # start > 0: Strahl beginnt start m HINTER der Flaeche (Nachbarhaus, das die Wand durchdringt, zaehlt mit - LoD2/Georef ~1 m ungenau).
    # start < 0 + min_d: Strahl beginnt VOR der Flaeche, nur Treffer > min_d davor zaehlen (Modellteile stecken ineinander: Fenster in der Rumpfwand
    # duerfen sich nicht gegenseitig 'verdecken'; 10.11. markierte start 0,3 75 % der OG-Fenster und die gut passende Rumpffront).
    o = P[idx] - N[idx] * start
    loc, ri, _ = nachbar.ray.intersects_location(o, N[idx], multiple_hits=False)
    if len(ri):
        d = np.linalg.norm(loc - o[ri], axis=1) - start; out[idx[ri[(d < weite) & ((d > min_d) if min_d is not None else True)]]] = True
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--georef", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--radius", type=float, default=70.0); a = ap.parse_args()
    m = nachbarn_netz(a.objekt, a.georef, a.radius); os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True); m.export(a.aus)
    print(f"Nachbarn: {len(m.faces)} Dreiecke, Bereich {np.round(m.bounds, 1).tolist()} -> {a.aus}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""objekt_rahmen.py - GENERISCH: fehlende Pflichtangaben 'rahmen' und 'lod2' eines Objekts ergaenzen (Lernregister 3, 2026-11-04).

Alte Objekte (Martinstor) haben den Modellrahmen nur in anker3d.json und keinen LoD2-Eintrag; die LoD2-Kette (sfm_lod2_ausrichten, sfm_lod2_buendel,
wolke_entzerren_lod2, wolke_dom1_pruefen) brach dort ab bzw. brauchte eine Handkopie der objekt.json. Jetzt:
  rahmen: objekt.json 'rahmen', sonst anker3d.json (mitte_utm, xhat_utm, yhat_utm, gelaende)
  lod2:   objekt.json 'lod2', sonst die LGL-Kachel LoD2_32_<E km>_<N km>_1_BW.gml unter der Rahmenmitte und darin das Gebaeude, dessen Grundriss
          die Rahmenmitte enthaelt (sonst das naechste). Quelle wird in obj['_ergaenzt'] vermerkt (Nachweis, kein stilles Raten).
  from objekt_rahmen import ergaenzen; obj = ergaenzen(obj, objektordner)
"""
import os, sys, json, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GEO = "/media/oem/scan/rc-park_daten/_geo"


def _innen(P, q):
    """Punkt-in-Polygon (Strahlverfahren), ohne matplotlib (venv-colmap hat es nicht)."""
    x, y = P[:, 0], P[:, 1]; x2, y2 = np.roll(x, -1), np.roll(y, -1); k = (y > q[1]) != (y2 > q[1])
    xs = x[k] + (q[1] - y[k]) * (x2[k] - x[k]) / (y2[k] - y[k]); return bool(np.sum(xs > q[0]) % 2)


def ergaenzen(obj, od):
    erg = obj.setdefault("_ergaenzt", {})
    if not obj.get("rahmen"):
        p = os.path.join(od, "anker3d.json")
        if os.path.exists(p):
            A = json.load(open(p)); obj["rahmen"] = {k: A[k] for k in ("mitte_utm", "xhat_utm", "yhat_utm", "gelaende") if k in A}; erg["rahmen"] = p
    if not obj.get("lod2") and obj.get("rahmen"):
        c0 = np.array(obj["rahmen"]["mitte_utm"], float)
        f = sorted(glob.glob(os.path.join(GEO, "**", f"LoD2_32_{int(c0[0] // 1000)}_{int(c0[1] // 1000)}_1_BW.gml"), recursive=True))
        if f:
            import lod2_gebaeude as LG
            best, bd = None, np.inf
            for meta, polys in LG.extract(f[0], center=tuple(c0), radius=40):
                for _, P in polys:
                    if _innen(P[:, :2], c0): best, bd = meta, -1.0; break
                if bd < 0: break
                d = np.linalg.norm(np.array(meta["center_utm"]) - c0)
                if d < bd: best, bd = meta, d
            if best is not None:
                obj["lod2"] = dict(gml=f[0], id=best.get("id")); erg["lod2"] = f"Kachel unter Rahmenmitte, Gebaeude {'mit Mitte im Grundriss' if bd < 0 else f'naechstes ({bd:.1f} m)'}"
    return obj


if __name__ == "__main__":
    import sys
    o = ergaenzen(json.load(open(sys.argv[1])), os.path.dirname(os.path.abspath(sys.argv[1]))); print(json.dumps(dict(rahmen=o.get("rahmen"), lod2=o.get("lod2"), ergaenzt=o["_ergaenzt"]), indent=1))

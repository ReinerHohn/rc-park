#!/usr/bin/env python3
"""rahmen_aus_lod2.py <objekt.json> [--name NAME] [--schreiben] - lod2 {gml,id}, koordinate_utm und rahmen fuer ein Objekt OHNE diese Angaben,
ueber das GML-Namensattribut (Lehre Schwabentor 2026-11-14: Ziel nur nach Hoehe gewaehlt -> Nachbarhaus; Name hat Vorrang).
Sucht in allen LGL-Kacheln unter /media/oem/scan/rc-park_daten/_geo/**/LoD2_*.gml nach name == NAME (Standard: erstes Wort von objekt.json name).
Mehrere Treffer (z. B. Turm + Anbau) -> der mit der groessten Grundflaeche. Rahmen: mitte_utm = Flaechenmitte der Grundflaechen,
xhat = lange Seite des kleinsten umschliessenden Rechtecks (Richtung so, dass xhat nach Nord/Ost zeigt), yhat = +90 Grad, gelaende = DGM1 an der Mitte.
Ohne --schreiben nur Ausgabe. Mehrdeutiger Name (2 Gebaeude > 50 m auseinander) -> rc 2, nichts schreiben.
"""
import sys, os, json, glob, re, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as LG


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--name", default=""); ap.add_argument("--schreiben", action="store_true")
    a = ap.parse_args(); obj = json.load(open(a.objekt))
    name = a.name or re.split(r"[\s(,-]", obj.get("name", "").strip())[0]
    treffer = []
    for g in sorted(glob.glob("/media/oem/scan/rc-park_daten/_geo/**/LoD2_*.gml", recursive=True)):
        if name.lower().encode() not in open(g, "rb").read().lower(): continue
        for meta, polys in LG.extract(g, name=name):
            if (meta.get("name") or "").lower() != name.lower(): continue
            gr = [p for t, p in polys if t == "GroundSurface"]
            fl = sum(0.5 * abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1))) for p in gr)
            treffer.append((fl, g, meta, gr))
    if not treffer: print(f"KEIN LoD2-Gebaeude mit name '{name}'"); return 1
    treffer.sort(key=lambda t: -t[0]); fl, g, meta, gr = treffer[0]
    ids = {t[2]["id"] for t in treffer}
    cs = [np.array(t[2]["center_utm"]) for t in treffer]
    if max(np.linalg.norm(c - cs[0]) for c in cs) > 50: print(f"MEHRDEUTIG: '{name}' an {len(cs)} Stellen > 50 m auseinander {sorted(ids)}"); return 2
    P = np.vstack([p[:, :2] for p in gr]); from scipy.spatial import ConvexHull
    h = P[ConvexHull(P).vertices]; best = None
    for i in range(len(h)):
        e = h[(i + 1) % len(h)] - h[i]; n = np.linalg.norm(e)
        if n < 1e-6: continue
        ea = e / n; eb = np.array([-ea[1], ea[0]]); pa, pb = h @ ea, h @ eb; f = np.ptp(pa) * np.ptp(pb)
        if best is None or f < best[0]: best = (f, ea, eb, pa, pb)
    _, ea, eb, pa, pb = best
    if np.ptp(pb) > np.ptp(pa): ea, eb, pa, pb = eb, -ea, pb, -pa
    if ea[1] + ea[0] < 0: ea = -ea                                                            # xhat nach Nord/Ost
    eb = np.array([-ea[1], ea[0]]); m = ea * (pa.max() + pa.min()) / 2 + eb * (pb.max() + pb.min()) / 2
    m = P.mean(0) if not np.all(np.isfinite(m)) else ea * ((P @ ea).max() + (P @ ea).min()) / 2 + eb * ((P @ eb).max() + (P @ eb).min()) / 2
    from dom1_kachel import dom1_hoehe
    gel = float(dom1_hoehe(np.array([m[0]]), np.array([m[1]]), art="dgm1")[0]) if True else float(meta["ground_z"])
    if not np.isfinite(gel): gel = float(meta["ground_z"])
    erg = dict(lod2=dict(gml=g, id=meta["id"], name=meta["name"], quelle="tools/rahmen_aus_lod2.py (GML-Namensattribut)"),
               koordinate_utm=[round(float(m[0]), 2), round(float(m[1]), 2)],
               rahmen=dict(mitte_utm=[round(float(m[0]), 2), round(float(m[1]), 2)], xhat_utm=[round(float(ea[0]), 4), round(float(ea[1]), 4)],
                           yhat_utm=[round(float(eb[0]), 4), round(float(eb[1]), 4)], gelaende=round(gel, 2),
                           quelle=f"tools/rahmen_aus_lod2.py: LoD2 {meta['id']} '{meta['name']}', xhat = lange Rechteckseite, gelaende DGM1"),
               lod2_hoehen=dict(traufe=meta.get("eave_m"), first=meta.get("ridge_m"), alle_teile=sorted(ids)))
    print(json.dumps(erg, ensure_ascii=False)[:600])
    if a.schreiben:
        for k in ("lod2", "koordinate_utm", "rahmen"):
            if k not in obj or not obj[k] or (k == "lod2" and not isinstance(obj[k], dict)): obj[k] = erg[k]
        __import__("json_sicher").schreiben(a.objekt, obj); print("geschrieben:", a.objekt)
    return 0


if __name__ == "__main__":
    sys.exit(main())

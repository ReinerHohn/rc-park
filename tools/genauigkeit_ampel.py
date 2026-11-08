#!/usr/bin/env python3
"""genauigkeit_ampel.py - 10-cm-Ampel je Flaeche (Nutzerziel 2026-11-05: <= 0,10 m gruen, <= 0,20 m gelb, sonst rot).

Messgroesse: Abstand echter Mehrbild-Punkte (SfM-Wolke im Modellsystem, sfm/dicht_*_modell.npy oder punkte_modell_*.npy; Punkte entstehen aus
Merkmalszuordnung zwischen Fotos, nicht aus dem Modell) zur Modelloberflaeche (STL), vorzeichenbehaftet (+ = Punkt vor der Modellflaeche).
Gruppen: Wandflaechen nach Normalenrichtung (8 Sektoren, Azimut der naechsten Dreiecksnormale), Dach (n_z > 0,3), Unterseiten verworfen.
Je Gruppe: n, Anteil der Punkte im 1-m-Band (Rest = Nachbarn/Personen/Rauschen/fehlende Bauteile - offen ausgewiesen), Median (Lage, Bias),
MAD*1,4826 (Streuung), Ampel aus |Median| (Lage).
EHRLICHKEIT: die Wolke ist an LoD2-Ankern ausgerichtet (sfm_lod2_ausrichten/-buendel) und der Rumpf ist LoD2 -> der Median der grossen Wandflaechen ist
teilweise durch die Ausrichtung erzwungen (Zirkelschluss-Anteil). Aussagekraeftig sind: Dach/Giebel (nicht Ausrichtungsziel), kleine Flaechen,
Streuung und die Gegenprobe --verschieben (Modell um dx verschoben muss |Median| um dx aendern).
  /media/oem/scan/venv-seg/bin/python -I tools/genauigkeit_ampel.py <objekt.json> [--stl X.stl] [--punkte sfm/dicht_alle_modell.npy] [--max 60000] [--verschieben dx dy dz]
"""
import os, sys, json, argparse
import numpy as np, trimesh


def ampel(d):
    return "gruen" if d <= 0.10 else ("gelb" if d <= 0.20 else "rot")


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--punkte"); ap.add_argument("--max", type=int, default=60000)
    ap.add_argument("--band", type=float, default=1.0); ap.add_argument("--min-n", type=int, default=200); ap.add_argument("--min-kante", type=float, default=4.0); ap.add_argument("--schnitt-z", type=float, default=8.0); ap.add_argument("--verschieben", nargs=3, type=float, default=[0, 0, 0]); ap.add_argument("--json")
    a = ap.parse_args(argv)
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)) if "modelle" in od else os.getcwd()
    stl = a.stl or os.path.join(root, obj["stl"]) if not (a.stl or "").startswith("/") else a.stl
    m = trimesh.load(stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); m.apply_translation(a.verschieben)
    pp = a.punkte or next((os.path.join(od, "sfm", f) for f in ("dicht_alle_modell.npy", "punkte_modell_buendel.npy") if os.path.exists(os.path.join(od, "sfm", f))), None)
    P = np.load(pp); rng = np.random.default_rng(0)
    if len(P) > a.max: P = P[rng.choice(len(P), a.max, replace=False)]
    q = trimesh.proximity.ProximityQuery(m); cp, dist, tri = q.on_surface(P); N = m.face_normals[tri]
    s = np.sign(((P - cp) * N).sum(1)); d = s * dist
    nz = N[:, 2]                                                                                          # Gruppe = Fassade nach Lage (naechste lange Grundrisskante bei z=1,5 m),
    sek = m.section(plane_origin=[0, 0, a.schnitt_z], plane_normal=[0, 0, 1]); K = []                                 # nicht nach Dreiecksnormale (Laibungen/Erkerseiten gehoerten sonst zur Nachbarfassade)
    for e in sek.entities:
        V = sek.vertices[e.points][:, :2]
        for p0, p1 in zip(V[:-1], V[1:]):
            if np.linalg.norm(p1 - p0) >= a.min_kante: K.append((p0, p1))
    A0 = np.array([k[0] for k in K]); A1 = np.array([k[1] for k in K]); t_ = A1 - A0; L_ = np.linalg.norm(t_, axis=1); t_ /= L_[:, None]
    rel = P[:, None, :2] - A0[None]; u_ = np.clip((rel * t_[None]).sum(2), 0, L_[None]); dk = np.linalg.norm(rel - u_[..., None] * t_[None], axis=2); ki = dk.argmin(1)
    nrm = np.stack([t_[:, 1], -t_[:, 0]], 1); mi = (A0 + A1) / 2; ctr = m.centroid[:2]; nrm *= np.sign(((mi - ctr) * nrm).sum(1))[:, None]
    azk = (np.degrees(np.arctan2(nrm[:, 1], nrm[:, 0])) + 360) % 360
    gruppe = np.where(nz > 0.3, "dach", np.where(nz < -0.3, "unten", np.array([f"wand_{int(round(azk[k])):03d}" for k in ki])))
    erg = {}
    print(f"Punkte {len(P)} aus {os.path.relpath(pp, root)}; Modell {os.path.relpath(stl, root)} verschoben {a.verschieben}")
    for g in sorted(set(gruppe) - {"unten"}):
        k = gruppe == g; db = d[k]; ib = np.abs(db) <= a.band
        if ib.sum() < a.min_n: continue
        med = float(np.median(db[ib])); mad = float(1.4826 * np.median(np.abs(db[ib] - med)))
        erg[g] = dict(n=int(k.sum()), im_band=round(float(ib.mean()), 3), median_m=round(med, 3), streuung_m=round(mad, 3), ampel=ampel(abs(med)),
                      anteil_10cm=round(float((np.abs(db[ib]) <= 0.10).mean()), 3), anteil_20cm=round(float((np.abs(db[ib]) <= 0.20).mean()), 3))
        e = erg[g]; print(f"  {g:9s} n={e['n']:6d} im Band {e['im_band']:.0%}  Lage(Median) {med:+.3f} m  Streuung {mad:.3f} m  <=10cm {e['anteil_10cm']:.0%} <=20cm {e['anteil_20cm']:.0%}  -> {e['ampel']}")
    z = {k: sum(1 for e in erg.values() if e["ampel"] == k) for k in ("gruen", "gelb", "rot")}; print("AMPEL:", z)
    if a.json: json.dump(dict(gruppen=erg, ampel=z, punkte=os.path.relpath(pp, root), stl=os.path.relpath(stl, root), verschoben=a.verschieben), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()

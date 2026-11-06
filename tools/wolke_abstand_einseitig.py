#!/usr/bin/env python3
"""wolke_abstand_einseitig.py - EINSEITIGER Abstand Modell -> Punktwolke (Schritt 2 der Methode 'grob zuerst + Wolke als Gegenprobe', Nutzer 6.11.).

Frage: Liegt das, was das MODELL hat, in der Wolke? Fehlende Modellteile (Erker, Gauben, Figuren ...) kosten NICHTS - nur Modellflaeche ohne Wolke in der Naehe faellt auf.
(Gegenrichtung Wolke -> Modell ist absichtlich NICHT Teil: sie wuerde jedes noch nicht gebaute Bauteil bestrafen.)
Unabhaengig von den Fotokanten (zweites Mass): Foto und Wolke pruefen sich gegenseitig; Widerspruch wird NICHT gemittelt, sondern gemeldet.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_abstand_einseitig.py modelle/<obj>/objekt.json --dicht <sfm/dicht_*> --stl <modell.stl>
        [--ausrichtung messprotokoll/SFM-AUSRICHTUNG-buendel.json] [--baender 0,3,12,25] [--n 200000] [--aus bericht.json]
Rahmen: STL in mm im Massstab objekt.json['stl_massstab'], zentrierung 'achse' (Ursprung bleibt) oder 'huelle' (Mitte der Huelle -> 0), wie foto_diff.
Wolke: fused.ply -> Modellrahmen wie wolke_carving.wolke_laden (Transformation aus der Ausrichtung). Alle Punkte (KEIN Mindestkamerafilter: .vis wird nicht gelesen).
Regionen: Hoehenbaender (--baender, m ueber Modellrahmen-z). Je Band: Mediane/p90/p95 des Abstands, Anteil > 0,5 m und > 1 m, Wolkendichte (Punkte je m2 Modellflaeche
im Umkreis 1 m) - Abstand ist nur dort aussagekraeftig, wo die Wolke dicht ist; Baender mit Dichte < --dichte-min werden als 'Wolke duenn' markiert (kein Urteil).
Ausgabe: JSON (Kennzahlen je Band), kurze Tabelle auf der Konsole.
"""
import os, sys, json, argparse, numpy as np, cv2, trimesh
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freiraum_pruefen as FP


def wolke_im_modellrahmen(dicht, ausr):
    tr = json.load(open(ausr))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
    X = FP.ply_lesen(os.path.join(dicht, "fused.ply"))
    return ((X - ta) @ Ra) / s


def modell_laden(stl, obj):
    m = trimesh.load(stl, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    if obj.get("zentrierung", "huelle") == "huelle": m.apply_translation(-m.bounds.mean(0))
    return m


def bewerten(m, X, baender, n=200000, dichte_min=20.0, tol=(0.5, 1.0), seed=1):
    """Kennzahlen je Hoehenband. m = trimesh (Meter, Modellrahmen), X = Wolkenpunkte (Meter, Modellrahmen)."""
    rng = np.random.default_rng(seed)
    P, fi = trimesh.sample.sample_surface(m, n, seed=seed)                 # gleichmaessig nach Flaeche
    flaeche = m.area; w_je = flaeche / n                                    # m2 je Stichprobe
    tree = cKDTree(X); d, _ = tree.query(P, k=1, workers=-1)
    nb = tree.query_ball_point(P[:: max(1, n // 20000)], r=1.0, workers=-1, return_length=True)   # Wolkenpunkte im Umkreis 1 m (Unterstichprobe)
    nb_full = np.zeros(len(P)); nb_full[:: max(1, n // 20000)] = nb; idx_nb = np.arange(0, len(P), max(1, n // 20000))
    ber = []
    for z0, z1 in zip(baender[:-1], baender[1:]):
        k = (P[:, 2] >= z0) & (P[:, 2] < z1)
        if k.sum() < 50: ber.append(dict(z0=z0, z1=z1, flaeche_m2=round(float(k.sum() * w_je), 1), urteil="zu wenig Modellflaeche")); continue
        dk = d[k]; kn = np.isin(np.nonzero(k)[0], idx_nb)
        dichte = float(nb_full[np.nonzero(k)[0][kn]].mean() / (np.pi * 1.0 ** 2)) if kn.any() else 0.0   # Punkte je m2 Kreisflaeche (grob)
        r = dict(z0=z0, z1=z1, flaeche_m2=round(float(k.sum() * w_je), 1), median_m=round(float(np.median(dk)), 3), p90_m=round(float(np.percentile(dk, 90)), 3), p95_m=round(float(np.percentile(dk, 95)), 3),
                 anteil_ueber_0_5m=round(float((dk > tol[0]).mean()), 3), anteil_ueber_1m=round(float((dk > tol[1]).mean()), 3), wolkendichte_je_m2=round(dichte, 1))
        r["urteil"] = "Wolke duenn (kein Urteil)" if dichte < dichte_min else "belastbar"; ber.append(r)
    return dict(baender=ber, n_stichproben=n, modellflaeche_m2=round(float(flaeche), 1), wolkenpunkte=int(len(X)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dicht", required=True); ap.add_argument("--stl")
    ap.add_argument("--ausrichtung"); ap.add_argument("--baender", default="0,3,12,25"); ap.add_argument("--n", type=int, default=200000); ap.add_argument("--dichte-min", type=float, default=20.0); ap.add_argument("--aus")
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
    stl = a.stl or os.path.join(root, obj["stl"]); ausr = a.ausrichtung or os.path.join(od, obj.get("ausrichtung", "messprotokoll/SFM-AUSRICHTUNG-buendel.json"))
    X = wolke_im_modellrahmen(a.dicht, ausr); m = modell_laden(stl, obj)
    bd = [float(x) for x in a.baender.split(",")]; erg = bewerten(m, X, bd, a.n, a.dichte_min); erg.update(stl=stl, dicht=a.dicht)
    print(f"Modellflaeche {erg['modellflaeche_m2']} m2, Wolke {erg['wolkenpunkte']} Punkte")
    print(" z [m]        Flaeche  median  p90   p95   >0,5m  >1m   Dichte/m2  Urteil")
    for b in erg["baender"]:
        if "median_m" in b: print(f" {b['z0']:4.0f}-{b['z1']:<4.0f}  {b['flaeche_m2']:8.1f} {b['median_m']:7.2f} {b['p90_m']:5.2f} {b['p95_m']:5.2f} {b['anteil_ueber_0_5m']:6.2f} {b['anteil_ueber_1m']:5.2f} {b['wolkendichte_je_m2']:9.1f}  {b['urteil']}")
        else: print(f" {b['z0']:4.0f}-{b['z1']:<4.0f}  {b['flaeche_m2']:8.1f}  {b['urteil']}")
    if a.aus: json.dump(erg, open(a.aus, "w"), indent=1, ensure_ascii=False)

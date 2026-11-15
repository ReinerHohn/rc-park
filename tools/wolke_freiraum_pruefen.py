#!/usr/bin/env python3
"""wolke_freiraum_pruefen.py <objekt.json> --wolke punkte_modell.npy [--tief 1.2] [--grenze 0.5] - Stoerpunkte der dichten Wolke messen, BEVOR sie gezeigt wird.

Lehre 15.11.2026 (Nutzer: "schwebende Wolke, schraeger Streifen im Turm - sehr schlecht"): Drohnen-/Fernbilder brachten in der Stufe schnell
Rauschen; kein Tor bemerkte es, die 3D-Seite wurde ungesehen veroeffentlicht. Zwei Kennzahlen im Modellrahmen (STL = Rahmen):
  IM KOERPER  Anteil der Wolkenpunkte im Umkreis des Modells, die tiefer als --tief m IM Baukoerper liegen (dort kann nichts sein;
              Durchfahrten/Innenhoefe im LoD2-Klotz geben einen kleinen Sockel -> Vergleich mit dem Vorlauf zaehlt).
  SCHWEBEND   Anteil der Punkte hoeher als 3 m, die keinen Nachbarn im 1-m-Raster direkt darunter (bis 6 m tiefer) haben = haengen frei in der Luft.
rc 3, wenn IM KOERPER > --grenze % ; Ausgabe audit/wolke_freiraum.json. Nur Lage-/Qualitaets-Veto fuer die Wolke, keine Formquelle.
"""
import sys, os, json, argparse, numpy as np, trimesh


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--tief", type=float, default=1.2); ap.add_argument("--grenze", type=float, default=0.5); ap.add_argument("--ab_hoehe", type=float, default=12.0)
    a = ap.parse_args(); objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0); lo, hi = m.bounds
    P = np.load(a.wolke, mmap_mode="r"); P = np.asarray(P[::max(1, len(P) // 1500000)], float)
    um = np.all((P[:, :2] > lo[:2] - 15) & (P[:, :2] < hi[:2] + 15), axis=1); U = P[um]
    kb = np.all((U > lo + a.tief) & (U < hi - a.tief), axis=1) & (U[:, 2] > lo[2] + a.ab_hoehe); K = U[kb]   # erst ab --ab_hoehe: Durchfahrten/Arkaden im LoD2-Klotz sind echte Punkte "im Koerper" (Schwabentor: 2-3 % Sockel)
    if len(K) > 200000: K = K[np.random.default_rng(0).choice(len(K), 200000, replace=False)]; fak = kb.sum() / 200000
    else: fak = 1.0
    drin = m.contains(K) if len(K) else np.zeros(0, bool); tief = 0
    if drin.any():
        I = K[drin]; d = np.abs(trimesh.proximity.signed_distance(m, I[:20000])) if len(I) else np.zeros(0); tief = float((d > a.tief).mean()) * drin.sum() * fak
    im_koerper = 100.0 * tief / max(len(U), 1)
    g = np.floor(U[:, :2]).astype(np.int64); key = g[:, 0] * 100003 + g[:, 1]; o = np.lexsort((U[:, 2], key)); ks, zs = key[o], U[o, 2]
    luecke = np.r_[True, (ks[1:] != ks[:-1]) | (zs[1:] - zs[:-1] > 6.0)]              # erster Punkt der Saeule oder > 6 m Luft darunter
    frei = luecke & (zs > 3.0) & ~np.r_[True, ks[1:] != ks[:-1]]                       # nur echte Luecken innerhalb einer Saeule (unten ist etwas, dazwischen Luft)
    grp = np.cumsum(luecke); n_frei = int(np.isin(grp, grp[frei]).sum()); schwebend = 100.0 * n_frei / max(len(U), 1)
    erg = dict(werkzeug="wolke_freiraum_pruefen.py", wolke=a.wolke, punkte_umkreis=int(len(U)), im_koerper_prozent=round(im_koerper, 3), schwebend_prozent=round(schwebend, 2), tief_m=a.tief, grenze_prozent=a.grenze)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(erg, open(os.path.join(od, "audit", "wolke_freiraum.json"), "w"), indent=1)
    print(f"FREIRAUM: im Koerper {im_koerper:.3f} % (Grenze {a.grenze} %), schwebend {schwebend:.2f} % von {len(U)} Punkten im 15-m-Umkreis")
    if im_koerper > a.grenze: print("WARNUNG: zu viele Punkte IM Baukoerper - Wolke verrauscht (Fern-/Videobilder ohne geometrische Pruefung?), nicht zeigen/benutzen"); return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

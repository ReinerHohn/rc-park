#!/usr/bin/env python3
"""wolke_vereinigen.py <basis.ply> <aus.ply> --ausrichtung SFM-AUSRICHTUNG.json --quelle NAME=PFAD.ply [--quelle ...] [--voxel 0.015] [--max_abw 0.05]

ALLE fotogestuetzten Wolken EINES Objekts zu einer vereinen (Nutzer 26.11.2026: "nicht Entweder-Oder, alles mergen, aus den Daten alles rausziehen").
Nicht blind: jede Quelle muss ZUERST zeigen, dass sie im selben Rahmen liegt (Memory 8.11.: gekippte/doppelte Wolken, "ein Punkt ist ein Punkt nur in EINER Rechnung"):
  Stichprobe 100 000 Punkte der Quelle -> naechster Basispunkt (KD-Baum, Modellmeter). Nur Punkte mit Basisnachbar < 0,5 m zaehlen als Ueberlapp.
  Angenommen, wenn Ueberlapp >= 1 000 Punkte UND Median-Abstand <= --max_abw (ANNAHME 5 cm). Sonst ABGELEHNT mit Zahl - kein Mitteln verschobener Quellen.
Vereinigung: Basis bleibt unveraendert; Quellpunkte kommen nur in Voxel (--voxel m, ANNAHME 1,5 cm), die die Basis noch nicht belegt, untereinander je Voxel einer.
Ergebnis <aus.ply> (SfM-Rahmen, wie fused.ply), <aus.ply>.quellen.npy (uint8 je Punkt: 0 Basis, 1.. Quelle), <aus.ply>.vereinigt.json (Messung je Quelle).
Laser (DOM1) und LoD2 sind KEINE Quellen (Kernmethode: nur Lage-Veto/Hoehe). Danach tools/quellfilter.py wie bei jeder Wolke.
Verwandt: tools/kachel_vereinen.py (Entweder-Oder je Kachel, abgeloest durch diese Vereinigung), tools/kachelfusion.py, tools/quellfilter.py, tools/wolke_ebenen_ransac.py.
Vorlaeufer: kachel_vereinen.py - nahm je Kachel nur eine Quelle; Gewinn der Kachelfusion und Dichte der alten Wolke gingen nicht zusammen.
"""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def modell(P, s, R, t):
    return (np.c_[P["x"], P["y"], P["z"]].astype(float) - t) @ R / s


def vkey(M, v):
    q = np.floor(M / v).astype(np.int64) + 1_000_000
    return (q[:, 0] * 2_097_152 + q[:, 1]) * 2_097_152 + q[:, 2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("basis"); ap.add_argument("aus"); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--quelle", action="append", default=[], metavar="NAME=PLY"); ap.add_argument("--voxel", type=float, default=0.015); ap.add_argument("--max_abw", type=float, default=0.05)
    ap.add_argument("--stichprobe", type=int, default=100000); ap.add_argument("--npy", help="zusaetzlich <name>_modell.npy + <name>_farben.npy")
    a = ap.parse_args()
    import cv2, teilfusion as TF
    from scipy.spatial import cKDTree
    T = json.load(open(a.ausrichtung))["transformation"]; s = T["s"]; R = cv2.Rodrigues(np.array(T["rvec"]))[0]; t = np.array(T["t"])
    B = TF.ply_lesen(a.basis); MB = modell(B, s, R, t); kb = np.unique(vkey(MB, a.voxel)); print(f"Basis {len(B)} Punkte, {len(kb)} Voxel", flush=True)
    baum = cKDTree(MB[:: max(1, len(MB) // 6_000_000)]); teile = [B]; tags = [np.zeros(len(B), np.uint8)]; bericht = []; rng = np.random.default_rng(0)
    for n, q in enumerate(a.quelle, 1):
        name, pfad = q.split("=", 1); Q = TF.ply_lesen(pfad); MQ = modell(Q, s, R, t); idx = rng.choice(len(Q), min(a.stichprobe, len(Q)), replace=False)
        d, _ = baum.query(MQ[idx]); ue = d < 0.5; med = float(np.median(d[ue])) if ue.sum() else float("nan")
        ok = bool(ue.sum() >= 1000 and med <= a.max_abw)
        z = {"name": name, "pfad": pfad, "punkte": int(len(Q)), "ueberlapp_stichprobe": int(ue.sum()), "median_abstand_m": round(med, 4), "angenommen": ok}
        if ok:
            k = vkey(MQ, a.voxel); pos = np.searchsorted(kb, k); frei = ~((pos < len(kb)) & (kb[np.minimum(pos, len(kb) - 1)] == k)); _, ersterIdx = np.unique(k[frei], return_index=True)
            wahl = np.flatnonzero(frei)[ersterIdx]; teile.append(Q[wahl]); tags.append(np.full(len(wahl), n, np.uint8)); z["neu_punkte"] = int(len(wahl))
            kb = np.union1d(kb, k[wahl])
        bericht.append(z); print(("OK     " if ok else "ABGELEHNT ") + json.dumps(z, ensure_ascii=False), flush=True)
    G = np.concatenate(teile); TG = np.concatenate(tags); TF.ply_schreiben(a.aus, G); np.save(a.aus + ".quellen.npy", TG)
    json.dump({"voxel_m": a.voxel, "max_abw_m": a.max_abw, "punkte_basis": int(len(B)), "punkte": int(len(G)), "quellen": bericht}, open(a.aus + ".vereinigt.json", "w"), indent=1, ensure_ascii=False)
    if a.npy:
        np.save(a.npy + "_modell.npy", modell(G, s, R, t).astype(np.float32)); np.save(a.npy + "_farben.npy", np.c_[G["r"], G["g"], G["b"]].astype(np.uint8))
    print(f"VEREINIGT {len(B)} + {len(G) - len(B)} = {len(G)} Punkte", flush=True); return 0


if __name__ == "__main__":
    sys.exit(main())

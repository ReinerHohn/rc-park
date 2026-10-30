#!/usr/bin/env python3
"""Juror 1 — GEOMETRIE-TREUE.
Frage: Bildet das Modell den ECHTEN Ort geometrisch treu ab, oder frisst
Glättung/Auflösung die markanten Kanten weg?

Misst den Glättungs-Rest (Generator-smooth vs. Roh-DEM) in MODELL-MM — gesamt und
nur auf den steilsten 20 % (Grate/Felswände, wo Treue am meisten zählt). Je kleiner
der Fehler relativ zur Materialdicke, desto treuer.

Aufruf:  python3 tools/bewerter_geometrie.py --manifest modelle/x/manifest.json
"""
import argparse, sys, os
import numpy as np
import bewerter_common as bc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_modell as vm


def judge(m, verbose=False):
    # BAUWERK mit STL → harter architektonischer Geometrie-Test (Bögen/Durchsicht/Proportion)
    spec = m.get("bauwerk")
    if m.get("typ") == "bauwerk" and spec and spec.get("stl") and os.path.exists(spec["stl"]):
        import bewerter_bauwerk_geom as bg
        return bg.judge(spec["stl"], spec)

    relief = bc.load_relief(m)
    nscale, vscale, smooth = m["nscale"], m["vscale"], m["smooth"]
    relief_m = float(relief.max())

    # Glättungs-Residuum (= Oberflächen-Untreue) in Modell-mm
    recon, support = vm.nan_smooth(relief, smooth)
    valid = support
    err_mm = (recon - relief) * nscale * vscale
    e = err_mm[valid]
    rms = float(np.sqrt(np.mean(e**2))) if e.size else 0.0
    p95 = float(np.percentile(np.abs(e), 95)) if e.size else 0.0

    # Grat-Treue: steilste 20 %
    gy, gx = np.gradient(relief)
    grad = np.hypot(gx, gy)
    thr = np.percentile(grad[valid], 80)
    mask = valid & (grad >= thr)
    er = err_mm[mask]
    ridge_rms = float(np.sqrt(np.mean(er**2))) if er.size else 0.0

    # Auflösungs-Treue: reicht die Rippen-/Mesh-Dichte für die Reliefspanne?
    # Reliefspanne in mm (vertikal) als Kontext
    relief_mm = relief_m * nscale * vscale

    # Scores: Fehler klein relativ zu ~3 mm Materialdicke = gut
    s_flat = bc.lin(8.0 - rms, 0.0, 6.0)        # rms 2mm->100, 8mm->0
    s_ridge = bc.lin(12.0 - ridge_rms, 0.0, 9.0)  # ridge 3mm->100, 12mm->0
    # Reliefspanne muss überhaupt genug Höhe haben, dass Geometrie zählt
    s_span = bc.lin(relief_mm, 20.0, 120.0)
    score = bc.clamp(0.45 * s_ridge + 0.35 * s_flat + 0.20 * s_span)

    reasons = [
        f"Reliefspanne {relief_m:.0f} m = {relief_mm:.0f} mm im Modell (nscale {nscale})",
        f"Oberflächen-Untreue (Glättung smooth={smooth}): RMS {rms:.2f} mm, P95 {p95:.2f} mm",
        f"Grat-/Kanten-Untreue (steilste 20 %): RMS {ridge_rms:.2f} mm",
    ]
    if ridge_rms > 8:
        reasons.append("⚠ Kanten verschmieren spürbar — smooth senken oder feiner auflösen")
    if relief_mm < 30:
        reasons.append("⚠ sehr flach — Geometrie trägt das Modell kaum, lebt von Textur/Kontext")

    return {
        "judge": "Geometrie-Treue",
        "score": round(score, 1),
        "verdict": bc.verdict_from_score(score),
        "reasons": reasons,
        "metrics": {"relief_m": relief_m, "relief_mm": relief_mm,
                    "rms_mm": rms, "p95_mm": p95, "ridge_rms_mm": ridge_rms},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    v = judge(bc.load_manifest(a.manifest), verbose=True)
    bc.print_verdict(v)


if __name__ == "__main__":
    main()

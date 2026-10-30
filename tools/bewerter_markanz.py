#!/usr/bin/env python3
"""Juror 3 — MARKANZ (Wiedererkennbarkeit & Wow).
Frage: Ist die Szene überhaupt markant genug, dass sich das Modell lohnt — oder
ist es ein flacher, austauschbarer Hügel, den niemand wiedererkennt?

Rein aus dem DEM (keine Meinung, nur Geometrie):
  - Steilheit: Reliefspanne relativ zur Grundfläche (dramatisches vs. sanftes Gelände)
  - Senkrechte Wände: Anteil Zellen ≥45° (Felswände, Schluchten, Staumauer-Fronten)
  - Skyline-Prägnanz: Streuung der Horizontlinie (unverwechselbares Profil)
  - Signatur-Feature: See-Wasserfläche / markanter Absturz vorhanden?
  - Modellgröße im Maßstab: handlich oder unhandlich?

Aufruf:  python3 tools/bewerter_markanz.py --manifest modelle/x/manifest.json
"""
import argparse, sys, os
import numpy as np
import bewerter_common as bc


def judge(m, verbose=False):
    # BAUWERK mit STL → Markanz der STRUKTUR (Bogen-Rhythmus / massive Präsenz), nicht nur Gelände
    spec = m.get("bauwerk")
    if m.get("typ") == "bauwerk" and spec and spec.get("stl") and os.path.exists(spec["stl"]):
        return _judge_bauwerk(m, spec)

    relief = bc.load_relief(m)
    cell = m["cell_m"]
    ny, nx = relief.shape
    relief_m = float(relief.max())
    footprint_m = float(np.sqrt(nx * ny) * cell)

    steepness = relief_m / (footprint_m + 1e-6)            # Höhe/Breite (ganzes Fenster)
    water = bc.water_fraction(relief, cell, 2.0)           # See-Proxy
    # DRAMATISCHSTE Teilregion (so wie man den Modell-Ausschnitt rahmt)
    peak_sf, peak_rel, peak_p95, box = bc.best_window_drama(relief, cell, 0.5, 45.0)

    # Modellgröße im Maßstab
    w_mm = nx * m["mm_per_cell"]; h_mm = ny * m["mm_per_cell"]
    size_mm = max(w_mm, h_mm)

    # Scores — lokale Dramatik führt (Feature, nicht die sanfte Umgebung)
    s_relief = bc.lin(relief_m, 25.0, 180.0)              # absolute Fallhöhe/Wandhöhe
    s_wall = bc.lin(peak_sf, 0.03, 0.25)                  # Steilwand im besten Ausschnitt
    s_p95 = bc.lin(peak_p95, 22.0, 58.0)                  # 95%-Hangneigung = Wand-Schärfe
    sig = m.get("signatur", "")
    # Signatur-Bonus: markante Wand ODER klarer See
    s_sig = 100.0 if (peak_sf > 0.08 or (0.08 < water < 0.75)) else 45.0
    s_size = bc.lin(300 - abs(size_mm - 300), 0, 250)     # Ideal ~ 50..550 mm

    score = bc.clamp(0.30 * s_wall + 0.26 * s_relief + 0.24 * s_p95 + 0.14 * s_sig + 0.06 * s_size)

    tight = (box[2]-box[0] < ny*0.9) or (box[3]-box[1] < nx*0.9)
    reasons = [
        f"Fallhöhe/Reliefspanne {relief_m:.0f} m (Steilheit H/B {steepness:.2f})",
        f"Steilwand im besten Ausschnitt: {peak_sf*100:.1f} % ≥45°, p95-Neigung {peak_p95:.0f}° "
        f"(Fensterkern y{box[0]}:{box[2]} x{box[1]}:{box[3]})",
        f"Wasserfläche {water*100:.0f} %  ·  Modellgröße ~{size_mm:.0f} mm",
    ]
    if sig:
        reasons.append(f"Signatur deklariert: '{sig}'")
    # klare Begründung bei schwachem Urteil (für Voting-Einwand)
    verd = bc.verdict_from_score(score)
    if verd != "PASS":
        if peak_sf < 0.04 and water > 0.1:
            reasons.append("⚠ flaches See-/Talgelände ohne Steilwand — das Markante wäre hier ein "
                           "BAUWERK (Staumauer/Brücke), nicht die Topografie")
        elif peak_sf < 0.04:
            reasons.append("⚠ nirgends echte Steilwand — Gefahr: austauschbarer Hügel, lebt nur von Textur")
        elif tight:
            reasons.append("⚠ Fenster zu weit — auf den genannten Fensterkern zuschneiden, dann markanter")
        else:
            reasons.append("⚠ Markanz grenzwertig — steileren/engeren Ausschnitt wählen")

    return {
        "judge": "Markanz",
        "score": round(score, 1),
        "verdict": bc.verdict_from_score(score),
        "reasons": reasons,
        "metrics": {"relief_m": relief_m, "steepness": round(steepness, 3),
                    "peak_steep_frac": round(peak_sf, 3), "peak_p95_slope": round(peak_p95, 1),
                    "water_frac": round(water, 3), "size_mm": round(size_mm)},
    }


def _judge_bauwerk(m, spec):
    """Markanz einer STRUKTUR: ein regelmäßiger Mehrbogen-Rhythmus oder eine große
    massive Mauer ist für sich markant — unabhängig vom (oft sanften) Gelände."""
    import bewerter_bauwerk_geom as bg
    p = bg.probe(spec["stl"])
    arch = spec.get("archetyp", "viadukt")
    n = p["n_through"] if arch in ("viadukt", "bruecke") else p["n_relief"]
    cv = max(p["gap_cv"], p["width_cv"])
    L, H = spec.get("L", p["L"]), spec.get("H", p["H"])

    s_rhythm = bc.lin(n, 1, 9)                    # 1 Bogen fad → ≥9 Bögen ikonisch
    s_reg = bc.lin(0.2 - cv, 0.0, 0.18)           # regelmäßig = markant (CV klein)
    s_scale = bc.lin(max(L, H), 20, 220)          # große Bauwerke sind markanter
    s_height = bc.lin(H, 15, 70)
    # massive Gewichtsmauer hat keinen Bogen-Rhythmus → über Höhe/Größe punkten
    if arch not in ("viadukt", "bruecke", "bogenstaumauer", "bogenmauer"):
        # monolithischer Block: beeindruckend, aber wenig UNVERWECHSELBAR → Deckel
        score = bc.clamp(0.70 * (0.55 * s_height + 0.45 * s_scale))
        rhy = f"massiver Block ohne Rhythmus, H={H} m (monolithisch = weniger unverwechselbar)"
    else:
        score = bc.clamp(0.42 * s_rhythm + 0.23 * s_reg + 0.20 * s_scale + 0.15 * s_height)
        rhy = f"{n} Bögen, Regelmäßigkeit-CV {cv:.2f}"
    reasons = [f"Struktur-Markanz ({arch}): {rhy}; Maße ~{L}×{H} m",
               "Bauwerk-Markanz ≠ Gelände-Markanz: die Struktur selbst trägt das Modell"]
    if n <= 1 and arch in ("viadukt", "bruecke", "bogenstaumauer"):
        reasons.append("⚠ nur 1 Öffnung erkannt — als Mehrbogen-Bauwerk wenig markant (Geometrie prüfen)")
    return {"judge": "Markanz", "score": round(score, 1),
            "verdict": bc.verdict_from_score(score), "reasons": reasons,
            "metrics": {"n_arch": n, "reg_cv": cv, "L": L, "H": H}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    v = judge(bc.load_manifest(a.manifest), verbose=True)
    bc.print_verdict(v)


if __name__ == "__main__":
    main()

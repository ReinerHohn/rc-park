#!/usr/bin/env python3
"""Juror 2 — FERTIGBARKEIT.
Frage: Lässt sich das Modell auf UNSEREN Maschinen sauber bauen — oder fliegt es
beim Entgittern auseinander / passt nicht aufs Bett / wird ein Materialgrab?

Zwei Modi:
  a) Mit Artefakten (SVG/STL im --artifact-Ordner): echte Teile prüfen
     (Teilzahl, größtes Teil ≤ Bett, Mini-Bruchstück-Risiko, STL watertight/Bett).
  b) Ohne Artefakte (nur Szene+Maßstab): SCHÄTZUNG — passt die Szene aufs Bett,
     wie viele Rippen/Bogen, grobe Material-/Zeitgröße.

Aufruf:  python3 tools/bewerter_fertigung.py --manifest modelle/x/manifest.json
"""
import argparse, sys, os, glob, re
import numpy as np
import bewerter_common as bc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_modell as vm


def _svg_part_bboxes(paths):
    """grobe Bounding-Box je SVG (mm) aus width/height oder viewBox."""
    out = []
    for p in paths:
        try:
            head = open(p, "r", errors="ignore").read(2000)
        except Exception:
            continue
        w = h = None
        mw = re.search(r'width="([\d.]+)', head); mh = re.search(r'height="([\d.]+)', head)
        if mw and mh:
            w, h = float(mw.group(1)), float(mh.group(1))
        else:
            vb = re.search(r'viewBox="[\d.\- ]*?([\d.]+) ([\d.]+)"', head)
            if vb:
                w, h = float(vb.group(1)), float(vb.group(2))
        if w and h:
            out.append((os.path.basename(p), w, h))
    return out


def judge(m, verbose=False):
    bx, by = m["bed"]
    reasons = []
    metrics = {}
    score = 100.0

    svgs, stls = bc.parse_artifacts(m)
    # Bauwerk-STL explizit mitnehmen (auch ohne artifact-Ordner)
    bstl = m.get("bauwerk", {}).get("stl", "")
    if bstl and os.path.exists(bstl) and bstl not in stls:
        stls = stls + [bstl]
    have_art = bool(svgs or stls)

    if have_art:
        bbs = _svg_part_bboxes(svgs)
        metrics["n_svg"] = len(svgs)
        if bbs:
            oversize = [b for b in bbs if b[1] > bx or b[2] > by]
            # Mini-Bruchstück-Risiko: Teil mit kleinster Kante < 8 mm
            tiny = [b for b in bbs if min(b[1], b[2]) < 8.0]
            biggest = max(bbs, key=lambda b: b[1] * b[2])
            metrics.update(oversize=len(oversize), tiny=len(tiny),
                           biggest_mm=[round(biggest[1]), round(biggest[2])])
            reasons.append(f"{len(svgs)} SVG-Teile; größtes {biggest[1]:.0f}×{biggest[2]:.0f} mm (Bett {bx}×{by})")
            if oversize:
                score -= 40; reasons.append(f"❌ {len(oversize)} Teil(e) größer als Bett → Kopf fährt über Rand")
            if tiny:
                score -= min(25, 3 * len(tiny)); reasons.append(f"⚠ {len(tiny)} sehr kleine Teile (<8 mm Kante) → Bruch-/Verlustrisiko")
            if not oversize and not tiny:
                reasons.append("✓ alle Teile passen aufs Bett, keine Mini-Bruchstücke")
        if stls:
            try:
                sh = bc.stl_health(max(stls, key=os.path.getsize), bx, by)
                metrics["stl"] = sh
                reasons.append(f"STL {sh['mm'][0]}×{sh['mm'][1]}×{sh['mm'][2]} mm: watertight={sh['watertight']}, Bett-ok={sh['fits_bed']}")
                if not sh["watertight"]:
                    score -= 30; reasons.append("❌ STL nicht watertight → Slicer-Risiko, reparieren")
                if not sh["fits_bed"]:
                    score -= 25; reasons.append("❌ STL passt nicht aufs Bett → kacheln")
            except Exception as e:
                reasons.append(f"⚠ STL-Check fehlgeschlagen: {e}")
    else:
        # Schätzung aus Szene + Maßstab
        relief = bc.load_relief(m)
        ny, nx = relief.shape
        mmc = m["mm_per_cell"]
        w_mm = nx * mmc; h_mm = ny * mmc
        metrics.update(scene_mm=[round(w_mm), round(h_mm)])
        reasons.append(f"Szene {w_mm:.0f}×{h_mm:.0f} mm im Maßstab (mm/Zelle {mmc})")
        # passt eine Rippe (volle Spannweite) aufs Bett?
        if w_mm > bx or h_mm > by:
            # muss gesplittet werden (Fingerzinken) — machbar, aber Aufwand
            n_split = int(np.ceil(w_mm / bx)) * int(np.ceil(h_mm / by))
            score -= min(25, 8 * (n_split - 1))
            reasons.append(f"⚠ Szene > Bett → in ~{n_split} Kacheln splitten (Fingerzinken)")
        else:
            reasons.append("✓ Szene passt in einen Bett-Ausschnitt (kein Splitten nötig)")
        # Rippenzahl-Schätzung (adaptiv ~ alle 6-10 mm eine Rippe je Richtung)
        rib_gap = 8.0
        n_rib = int(w_mm / rib_gap) + int(h_mm / rib_gap)
        sheets = max(1, int(np.ceil((w_mm * h_mm) / (bx * by * 0.6))))
        metrics.update(est_ribs=n_rib, est_sheets=sheets)
        reasons.append(f"Schätzung: ~{n_rib} Rippen, ~{sheets} Laser-Bretter (≈{sheets*8} min Schnitt)")
        if sheets > 10:
            score -= 15; reasons.append("⚠ viele Bretter — Material/Zeit beachten")

    # Bauwerk-Hinweis
    if m.get("typ") == "bauwerk" and not have_art:
        reasons.append("ℹ Bauwerk: parametrischer Generator nötig (Mauer/Viadukt/Turm) — Fertigbarkeit erst nach Generierung final")

    score = bc.clamp(score)
    return {
        "judge": "Fertigbarkeit",
        "score": round(score, 1),
        "verdict": bc.verdict_from_score(score),
        "reasons": reasons,
        "metrics": metrics,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    v = judge(bc.load_manifest(a.manifest), verbose=True)
    bc.print_verdict(v)


if __name__ == "__main__":
    main()

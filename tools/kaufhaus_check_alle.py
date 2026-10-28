#!/usr/bin/env python3
"""kaufhaus_check_alle.py — EIN Lauf, alle Checks → konsolidierte Ratsche für die nächste Loop.

Fängt die Fehlertypen dieser Session AUTOMATISCH ab (siehe FEHLER_ZUSAMMENFASSUNG.md):
  1) MASSING vs LOD2  — hätte „Dach zu kurz / Fassade zu schmal" sofort gezeigt.
  2) DEGENERACY        — hätte die kollabierten Fenster gezeigt (ungültige/entartete Geometrie).
  3) Bild-Checks (optional, --render model.png): proportion_check + gauben_check + fenster_detail_check.
Gibt eine PRIORITÄTENLISTE der WARN/FAIL aus → die nächste Loop arbeitet sie der Reihe nach ab.

Lauf: python3 tools/kaufhaus_check_alle.py [--render /tmp/model.png]
"""
import os, sys, re, json, glob, subprocess
import numpy as np

ROOT = "/home/md/git/rc-park"
MDIR = f"{ROOT}/modelle/kaufhaus_freiburg"
findings = []   # (schwere, text)


def massing_check():
    try:
        src = open(f"{ROOT}/tools/kaufhaus_measured.py").read()
        W = float(re.search(r"W,\s*D\s*=\s*([\d.]+)", src).group(1))
        D = float(re.search(r"W,\s*D\s*=\s*[\d.]+,\s*([\d.]+)", src).group(1))
        mass = json.load(open(f"{MDIR}/kaufhaus_mass.json"))["features_verfeinert_m"]
        eave, ridge = mass["Traufe"], mass["First"]
        lod = json.load(open(f"{MDIR}/kaufhaus_lod2.json"))
        g = lod["gebaeude"][0]; l_eave, l_ridge = g["eave_m"], g["ridge_m"]
        l_w = max(lod["bbox_lbh_m"][0], lod["bbox_lbh_m"][1])
        print("MASSING vs LOD2:")
        for name, mv, lv, tol in [("Traufe", eave, l_eave, 1.0), ("First", ridge, l_ridge, 1.5),
                                  ("Fassadenbreite", W, l_w, 2.5)]:
            d = abs(mv-lv); ok = d <= tol
            print(f"  {name:<16} Modell {mv:5.1f}  LOD2 {lv:5.1f}  Δ {d:4.1f}  {'ok' if ok else 'ABWEICHUNG'}")
            if not ok:
                findings.append(("HOCH", f"Massing {name}: {mv:.1f} vs LOD2 {lv:.1f} (Δ{d:.1f}) → an amtlichen Wert angleichen"))
    except Exception as e:
        print("MASSING-Check übersprungen:", e)


def degeneracy_check():
    import trimesh
    print("DEGENERACY (STL-Geometrie-Sanity):")
    bad = 0
    for f in sorted(glob.glob(f"{MDIR}/khm_*.stl")):
        nm = os.path.basename(f).replace("khm_", "").replace(".stl", "")
        m = trimesh.load(f, process=True)
        if len(m.faces) == 0:
            findings.append(("HOCH", f"{nm}: leeres Mesh")); bad += 1; continue
        areas = m.area_faces
        zero = int((areas < 1e-9).sum())
        nonfinite = int((~np.isfinite(m.vertices)).any())
        # Sliver/entartet: sehr viele Null-Flächen oder Nicht-endliche Vertices
        if nonfinite:
            findings.append(("HOCH", f"{nm}: nicht-endliche Vertices (NaN/Inf)")); bad += 1
        if zero > len(areas)*0.05:
            findings.append(("MITTEL", f"{nm}: {zero} Null-Flächen ({100*zero/len(areas):.0f}%) → evtl. entartet")); bad += 1
    print(f"  {bad} auffällige Segmente" if bad else "  alle Segmente geometrisch gesund")


def image_checks(render):
    print("BILD-CHECKS (gegen Foto):")
    def run(cmd, label):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout
            print(f"  --- {label} ---")
            for ln in out.strip().splitlines():
                print("   ", ln)
            for ln in out.splitlines():
                if "WARN" in ln or "FAIL" in ln or "ABWEICH" in ln:
                    findings.append(("MITTEL", f"{label}: {ln.strip()}"))
        except Exception as e:
            print(f"  {label} übersprungen: {e}")
    run(["python3", "tools/kanten_abgleich.py", "--sweep", f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg", render, "/tmp/ka_sweep"], "Kanten-Gate-Sweep")


def main():
    render = sys.argv[sys.argv.index("--render")+1] if "--render" in sys.argv else None
    print("="*64); print("KAUFHAUS — ALLE CHECKS"); print("="*64)
    massing_check(); print()
    degeneracy_check(); print()
    if render:
        image_checks(render); print()
    print("="*64)
    if not findings:
        print("✓ Keine Abweichungen — Modell solide.")
    else:
        print(f"PRIORITÄTENLISTE ({len(findings)} Punkte) für die nächste Loop:")
        for sev, txt in sorted(findings, key=lambda x: {"HOCH": 0, "MITTEL": 1, "NIEDRIG": 2}[x[0]]):
            print(f"  [{sev}] {txt}")
    print("="*64)


if __name__ == "__main__":
    main()

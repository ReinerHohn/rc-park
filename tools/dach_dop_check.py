#!/usr/bin/env python3
"""dach_dop_check.py — GUARD: prüft die Modell-Dachaufsicht gegen das DOP-Luftbild. Das DOP zeigt,
wie viele zusammenhängende Dächer es WIRKLICH gibt. Fehler, der mich erwischte: ich baute die
LOD2-Teile als GETRENNTE Dächer, obwohl das Luftbild EIN zusammenhängendes Dach zeigt → falsches
„zweites Gebäude". Dieser Check fängt das: Modell-Dach von oben → Zahl zusammenhängender Komponenten
muss zur DOP-Dachfläche passen (i.d.R. 1).

Lauf: /tmp/ml/bin/python tools/dach_dop_check.py --name hofgut_sternen
"""
import argparse, json, os, subprocess
import numpy as np
import cv2


def components(mask, min_area):
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    return [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > min_area]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True); a = ap.parse_args()
    md = f"modelle/{a.name}"
    # Modell-Dach von oben
    subprocess.run(["/tmp/rv/bin/python", "tools/glb_render.py", f"{md}/hofgut_massing.glb", "/tmp/ddc_top", "top,270,89"],
                   capture_output=True, env={**os.environ, "PYOPENGL_PLATFORM": "egl", "GLB_LIGHT": "0.9"})
    g = cv2.cvtColor(cv2.imread("/tmp/ddc_top_top.png"), cv2.COLOR_BGR2GRAY)
    mcomp = components(g < 248, 500)
    # DOP-Dachfläche (grosse dunkle Region) als Referenz
    dop_comp = None
    dp = f"{md}/dop_dach.png"
    if os.path.exists(dp):
        dg = cv2.cvtColor(cv2.imread(dp), cv2.COLOR_BGR2GRAY)
        dark = (dg < 110)
        dop_comp = len(components(dark, dark.size * 0.03))

    # Regel: Modell-Dach darf NICHT mehr getrennte Dächer haben als das Luftbild. Hofgut = 1 Masse.
    # (DOP-Zählung ist schattenverrauscht → Modell muss zusammenhängend sein UND <= DOP.)
    ok = len(mcomp) == 1 and (dop_comp is None or len(mcomp) <= max(1, dop_comp))
    out = {"modell_dach_komponenten": len(mcomp), "dop_dach_komponenten": dop_comp,
           "ok": bool(ok), "regel": "Modell-Dachkomponenten muss DOP-Dach entsprechen (i.d.R. 1, kein falsches 2. Gebaeude)"}
    json.dump(out, open(f"{md}/dach_dop_check.json", "w"), indent=1)
    print(f"=== DACH-DOP-GUARD {a.name} ===")
    print(f"  Modell-Dach von oben: {len(mcomp)} Komponente(n)")
    print(f"  DOP-Dach (Luftbild):  {dop_comp} Komponente(n)")
    print(f"  {'✅ zusammenhaengend wie Luftbild' if ok else '⚠️ MODELL hat getrennte Daecher, Luftbild NICHT = falsches 2. Gebaeude'}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

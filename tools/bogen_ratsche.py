#!/usr/bin/env python3
"""bogen_ratsche.py — ARC_BW so setzen, dass die Gold-Archivolte die Bogen-ÖFFNUNG genau rahmt.

BEFUND (aus dieser Analyse, dokumentiert): die Arkaden-ÖFFNUNG wird von den PFEILERN bestimmt
(Teilung = W/N_ARCH minus Pfeilerbreite), NICHT von ARC_BW. ARC_BW skaliert nur den Gold-Ring
(arch_rings: bw=pitch*ARC_BW). Die Öffnungsbreite des Modells (lichte Weite/Pitch) stimmt bereits
mit dem Foto überein (~0,74 vs 0,70). ARC_BW muss daher = lichte-Weite/Pitch sein, damit der Ring
auf der Leibung sitzt (wie die kräftige Gold-Archivolte im Foto), statt frei in der Öffnung zu schweben.

Messung: lichte Weite an der KÄMPFER-Zeile (unterster müllfreier Rand = Bogen am breitesten) im Render.
→ ARC_BW = lichte Weite / Pitch, in kaufhaus_mass.json geschrieben (Generator liest es, kein Hardcoding).

Lauf: /tmp/rv/bin/python tools/bogen_ratsche.py
"""
import os, sys, json, subprocess, importlib.util
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np
from scipy import ndimage, signal

ROOT = "/home/md/git/rc-park"
MASS = f"{ROOT}/modelle/kaufhaus_freiburg/kaufhaus_mass.json"
d = os.path.join(ROOT, "tools")
sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("od", os.path.join(d, "overlay_diff.py"))
od = importlib.util.module_from_spec(spec); spec.loader.exec_module(od)


def set_bw(val):
    j = json.load(open(MASS)); j["bogen_breite_frac"] = round(float(val), 3)
    json.dump(j, open(MASS, "w"), ensure_ascii=False)
    subprocess.run(["python3", f"{ROOT}/tools/kaufhaus_measured.py"], capture_output=True, cwd=ROOT)


def clear_span_frac(im, y_band=(0.62, 0.74)):
    """lichte Weite / Pitch: an der breitesten (untersten) müllfreien Zeile der Arkade die dunklen
    Öffnungs-Läufe messen, Mittelwert ihrer Breite / mittlere Teilung (Zentrumsabstand)."""
    a = np.asarray(im.convert("RGB")); H, W = a.shape[:2]
    y0, y1 = int(H*y_band[0]), int(H*y_band[1])
    x0, x1 = int(W*0.06), int(W*0.94)
    best = None
    # unterste Zeilen zuerst (Bogen am breitesten), erste mit sauberen >=3 Öffnungen nehmen
    for yy in range(y1-1, y0, -2):
        row = a[yy, x0:x1]
        r, g, b = row[:, 0].astype(int), row[:, 1].astype(int), row[:, 2].astype(int)
        dark = ((r < 100) & (g < 95) & (b < 110)).astype(float)
        dark = ndimage.uniform_filter1d(dark, max(3, len(dark)//60))
        on = dark > 0.5
        runs = []; i = 0
        while i < len(on):
            if on[i]:
                j = i
                while j < len(on) and on[j]:
                    j += 1
                runs.append((i, j)); i = j
            else:
                i += 1
        runs = [rn for rn in runs if rn[1]-rn[0] > len(on)*0.04]
        if len(runs) >= 3:
            centers = [(p0+p1)/2 for p0, p1 in runs]
            pitch = np.mean(np.diff(centers))
            ow = np.mean([p1-p0 for p0, p1 in runs])
            best = (float(ow/pitch), len(runs), yy/H)
            break
    return best


def main():
    print("Arkaden-Öffnung (lichte Weite/Pitch) im Render messen → ARC_BW = dieser Wert (Ring rahmt Öffnung).")
    # ARC_BW beeinflusst die Öffnung NICHT (Pfeiler tun das); ein Referenz-Build genügt für die Messung.
    set_bw(0.86)
    rim = od.render()
    cs = clear_span_frac(rim)
    if cs is None:
        print("keine saubere Arkaden-Zeile gefunden — ARC_BW unverändert."); return
    frac, nrun, yf = cs
    print(f"  gemessen: lichte Weite/Pitch = {frac:.3f}  ({nrun} Öffnungen, Zeile y={yf:.2f})")
    bw_fit = round(float(np.clip(frac, 0.6, 1.0)), 3)
    orig = json.load(open(MASS)).get("bogen_breite_frac", None)
    set_bw(bw_fit)
    print(f"\nARC_BW gesetzt = {bw_fit} (war {orig}) → Gold-Archivolte rahmt jetzt die Öffnung.")


if __name__ == "__main__":
    main()

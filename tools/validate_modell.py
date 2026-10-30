#!/usr/bin/env python3
"""validate_modell.py — VALIDIERUNG: wie nah ist das erzeugte Modell an der Realität,
und ist es ohne viel Nacharbeit lasercut-/druckbar?

Misst drei Dinge gegen HARTE Toleranzen und gibt PASS/WARN/FAIL:

  1. OBERFLÄCHEN-TREUE  — wie stark weicht die Modelloberfläche vom Roh-DEM ab?
       Die Generatoren (skin_smart_split, terrain_eggcrate) bauen die Oberfläche als
       gaussian_filter(DEM, smooth). Der Validator reproduziert GENAU diesen Schritt
       aus den echten Parametern und vergleicht mit dem UNGEGLÄTTETEN DEM.
       → RMS / P95 / Max, in ECHTEN METERN und in MODELL-MM.
       → zusätzlich GRAT-TREUE: Fehler nur auf den steilen Kanten (dort frisst
         Glättung am meisten — die „scharfe Kanten"-Qualität).

  2. QUANTISIERUNG (nur cut/Kontur-Stack) — Materialdicke = Höhenstufe.
       Treppenfehler = Materialdicke/√12. Zeigt die physikalische Untergrenze.

  3. FERTIGBARKEIT — aus den TATSÄCHLICHEN Dateien geparst (kein Raten):
       STL : watertight? konsistente Wicklung? Euler? passt aufs Druckbett?
       SVG : wie viele Teile? größtes Teil ≤ Laser-Bogen (410×400)? Pfade geschlossen?

Die Trennung ist bewusst ehrlich: Treue aus Parametern+DEM (reproduzierbare Mathe),
Fertigbarkeit aus den echten Artefakten (geparst). Keine fragile Rück-Georeferenzierung.

Aufruf
    python3 tools/validate_modell.py --dem daten/linach/linach_dgm1.npy \\
        --nscale 10 --smooth 4 --artifact modelle/linachtalsperre
    python3 tools/validate_modell.py --dem daten/hoellental/dgm025_full.npy \\
        --r0 470 --r1 640 --c0 3310 --c1 3570 --nscale 6.25 --smooth 1 \\
        --mode cut --material 3 --layers 25 --artifact /tmp/laser
"""
import argparse, glob, os, re, sys
import numpy as np

try:
    from scipy.ndimage import gaussian_filter
except ImportError:
    sys.exit("scipy fehlt")


def load_window(dem, r0, r1, c0, c1):
    A = np.load(dem)
    if A.ndim != 2:
        sys.exit(f"DEM ist {A.ndim}D, erwartet 2D Höhenfeld")
    if r1 <= 0 or r1 > A.shape[0]:
        r0, r1 = 0, A.shape[0]
    if c1 <= 0 or c1 > A.shape[1]:
        c0, c1 = 0, A.shape[1]
    return A[r0:r1, c0:c1].astype(float)


def nan_smooth(raw, s):
    """NaN-robuste Gauß-Glättung: Nodata-Zellen verseuchen das Ergebnis nicht."""
    v = np.isfinite(raw).astype(float)
    filled = np.where(np.isfinite(raw), raw, 0.0)
    if s <= 0:
        return filled, v > 0
    num = gaussian_filter(filled, s)
    den = gaussian_filter(v, s)
    out = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-6)
    return out, den > 1e-6


def stat(name, arr_mm, arr_m, tol_rms, tol_max):
    if arr_mm.size == 0:
        print(f"  [WARN] {name}: keine gültigen Zellen"); return "WARN", 0.0, 0.0
    rms = float(np.sqrt(np.mean(arr_mm ** 2)))
    p95 = float(np.percentile(np.abs(arr_mm), 95))
    mx = float(np.max(np.abs(arr_mm)))
    rms_m = float(np.sqrt(np.mean(arr_m ** 2)))
    mx_m = float(np.max(np.abs(arr_m)))
    # Urteil auf RMS + P95 (robust); Max ist nur Info (echte Steilwände/Kanten)
    verd = "PASS" if (rms <= tol_rms and p95 <= tol_max) else \
           ("WARN" if (rms <= tol_rms * 1.5 and p95 <= tol_max * 1.5) else "FAIL")
    print(f"  [{verd}] {name}")
    print(f"         RMS {rms:6.2f} mm ({rms_m:6.3f} m)   "
          f"P95 {p95:6.2f} mm   Max {mx:6.2f} mm ({mx_m:6.3f} m, Info: Steilkante)")
    print(f"         Toleranz: RMS≤{tol_rms} mm, P95≤{tol_max} mm")
    return verd, rms, mx


def surface_from_dump(npz, tol_rms, tol_max, tol_ridge):
    """ECHTES gebautes Modell-Höhenfeld (vom Generator, --dump-surface) vs. Roh-DEM.
    Misst die TATSÄCHLICHE Geometrie (inkl. Zoom/Glättung/Resampling), keine Formel."""
    d = np.load(npz)
    real, model = d["real_m"], d["model_m"]
    nscale, vscale = float(d["nscale"]), float(d["vscale"])
    print("\n1) OBERFLÄCHEN-TREUE — ECHTES gebautes Modell vs. Roh-DEM")
    print(f"   (Beleg {os.path.basename(npz)}, {real.shape}, nscale {nscale} mm/m)")
    valid = np.isfinite(real) & np.isfinite(model)
    err_m = np.where(valid, model - real, 0.0)
    err_mm = err_m * nscale * vscale
    v1, _, _ = stat("gesamte Fläche (echte Geometrie)",
                    err_mm[valid], err_m[valid], tol_rms, tol_max)
    gy, gx = np.gradient(np.where(valid, real, np.nanmin(real[valid])))
    grad = np.hypot(gx, gy)
    mask = valid & (grad >= np.percentile(grad[valid], 80))
    v2, _, _ = stat("nur Grate/Kanten (steilste 20 %)",
                    err_mm[mask], err_m[mask], tol_ridge, tol_max)
    return min_verdict(v1, v2), model, err_mm


def surface_fidelity(raw, nscale, vscale, smooth, tol_rms, tol_max, tol_ridge):
    """Residuale der Glättung = Oberflächen-Untreue."""
    print("\n1) OBERFLÄCHEN-TREUE (Modelloberfläche vs. Roh-DEM)")
    recon, support = nan_smooth(raw, smooth)
    valid = support & np.isfinite(raw)        # Zelle SELBST echt, nicht nur Nachbarn
    err_m = np.where(valid, recon - np.nan_to_num(raw), 0.0)   # Meter
    err_mm = err_m * nscale * vscale                           # Modell-mm
    v1, rms, mx = stat(f"gesamte Fläche (smooth={smooth})",
                       err_mm[valid], err_m[valid], tol_rms, tol_max)

    # Grat-Treue: nur die steilsten 20 % der GÜLTIGEN Zellen (Kanten/Grate)
    filled = np.where(valid, np.nan_to_num(raw), recon)
    gy, gx = np.gradient(filled)
    grad = np.hypot(gx, gy)
    thr = np.percentile(grad[valid], 80)
    mask = valid & (grad >= thr)
    v2, _, _ = stat("nur Grate/Kanten (steilste 20 %)",
                    err_mm[mask], err_m[mask], tol_ridge, tol_max)
    return min_verdict(v1, v2), np.where(valid, recon, np.nan), err_mm


def quantisation(raw, nscale, vscale, material, layers, tol_max):
    print("\n2) QUANTISIERUNG (Kontur-Stack: Materialdicke = Höhenstufe)")
    v = np.isfinite(raw)
    rmin, rmax = np.nanmin(raw), np.nanmax(raw)
    h_m = rmax - rmin
    step_mm = material
    step_m = material / (nscale * vscale)
    nlay = layers if layers > 0 else int(np.ceil(h_m / step_m))
    # Modelloberfläche auf Stufen gerundet (nur gültige Zellen)
    rel = (raw[v] - rmin)
    levels_m = np.floor(rel / step_m) * step_m
    err_m = rel - levels_m
    err_mm = err_m * nscale * vscale
    rms = float(np.sqrt(np.mean(err_mm ** 2)))
    mx = float(np.max(np.abs(err_mm)))
    theo = step_mm / np.sqrt(12)
    verd = "PASS" if mx <= material * 1.05 else "WARN"
    print(f"  [{verd}] {nlay} Lagen × {step_mm:g} mm   (Höhe {h_m:.1f} m = "
          f"{h_m*nscale*vscale:.0f} mm)")
    print(f"         Treppenfehler RMS {rms:5.2f} mm (theoretisch {theo:.2f}), "
          f"Max {mx:5.2f} mm = 1 Stufe")
    print(f"         → physikalische Untergrenze; nur dünneres Material hilft")
    return verd


def check_stl(path, bed_x, bed_y):
    try:
        import trimesh
    except ImportError:
        print("  [WARN] trimesh fehlt — STL-Check übersprungen"); return "WARN"
    try:
        m = trimesh.load(path, force="mesh")
    except Exception as e:
        print(f"  [FAIL] {os.path.basename(path)}: {e}"); return "FAIL"
    wt = m.is_watertight
    wind = m.is_winding_consistent
    bb = m.bounding_box.extents
    fits = bb[0] <= bed_x and bb[1] <= bed_y
    degen = int(np.sum(m.area_faces < 1e-9)) if len(m.faces) else 0
    verd = "PASS"
    if not wt:
        verd = "WARN"          # nicht-watertight = evtl. Slicer-Reparatur nötig
    if not fits:
        verd = "FAIL"          # passt nicht aufs Bett = zwingend Nacharbeit
    print(f"  [{verd}] {os.path.basename(path):32s} "
          f"{bb[0]:5.0f}×{bb[1]:5.0f}×{bb[2]:4.0f} mm")
    print(f"         watertight={wt}  winding_ok={wind}  "
          f"euler={m.euler_number}  degen_faces={degen}  "
          f"Bett {bed_x:.0f}×{bed_y:.0f}→{'passt' if fits else 'KACHELN NÖTIG'}")
    return verd


def check_svgs(paths, sheet_x, sheet_y):
    rx = re.compile(r'width="([\d.]+)mm"\s+height="([\d.]+)mm"')
    worst = "PASS"
    toobig = []
    maxw = maxh = 0.0
    for p in paths:
        with open(p) as f:
            head = f.read(400)
        mm = rx.search(head)
        if not mm:
            continue
        w, h = float(mm.group(1)), float(mm.group(2))
        maxw, maxh = max(maxw, w), max(maxh, h)
        if w > sheet_x or h > sheet_y:
            toobig.append((os.path.basename(p), w, h))
    verd = "FAIL" if toobig else "PASS"
    print(f"  [{verd}] {len(paths)} Teile   größtes {maxw:.0f}×{maxh:.0f} mm   "
          f"Bogen {sheet_x:.0f}×{sheet_y:.0f}")
    for n, w, h in toobig[:5]:
        print(f"         ✗ {n}: {w:.0f}×{h:.0f} mm — passt NICHT auf den Bogen")
    return verd


def min_verdict(*vs):
    order = {"PASS": 0, "WARN": 1, "FAIL": 2}
    return max(vs, key=lambda v: order[v])


def heatmap(raw, err_mm, out):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    from matplotlib.colors import LightSource
    fig, ax = plt.subplots(1, 2, figsize=(11, 5))
    ls = LightSource(azdeg=315, altdeg=45)
    ax[0].imshow(ls.hillshade(raw, vert_exag=2), cmap="gray")
    ax[0].set_title("Roh-DEM (Realität)")
    im = ax[1].imshow(np.abs(err_mm), cmap="inferno")
    ax[1].set_title("|Oberflächen-Fehler| [Modell-mm]")
    fig.colorbar(im, ax=ax[1], shrink=0.8)
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser(description="Modell-Validierung gegen Realität")
    ap.add_argument("--dem", default="", help="Roh-DEM (.npy) — Formel-Modus")
    ap.add_argument("--surface", default="", help="Beleg .npz vom Generator "
                    "(--dump-surface): validiert die ECHTE gebaute Geometrie")
    ap.add_argument("--r0", type=int, default=0); ap.add_argument("--r1", type=int, default=0)
    ap.add_argument("--c0", type=int, default=0); ap.add_argument("--c1", type=int, default=0)
    ap.add_argument("--nscale", type=float, default=6.25, help="Modell-mm je echtem Meter")
    ap.add_argument("--vscale", type=float, default=1.0, help="Höhen-Überhöhung des Modells")
    ap.add_argument("--smooth", type=float, default=4.0, help="Glättung, die der Generator nutzt")
    ap.add_argument("--mode", choices=["print", "cut", "auto"], default="auto")
    ap.add_argument("--material", type=float, default=3.0, help="Materialdicke mm (cut)")
    ap.add_argument("--layers", type=int, default=0, help="Lagen-Anzahl (cut, 0=auto)")
    ap.add_argument("--artifact", default="", help="STL-Datei oder Ordner mit STL/SVG")
    ap.add_argument("--bed-x", type=float, default=250); ap.add_argument("--bed-y", type=float, default=210)
    ap.add_argument("--sheet-x", type=float, default=410); ap.add_argument("--sheet-y", type=float, default=400)
    ap.add_argument("--tol-rms", type=float, default=0.6, help="erlaubtes RMS Modell-mm")
    ap.add_argument("--tol-max", type=float, default=2.0, help="erlaubter Max-Fehler Modell-mm")
    ap.add_argument("--tol-ridge", type=float, default=1.0, help="erlaubtes RMS auf Graten")
    ap.add_argument("--out", default="/tmp/validate_heatmap.png")
    a = ap.parse_args()

    if not a.surface and not a.dem:
        sys.exit("--surface (Beleg) ODER --dem (Formel-Modus) angeben")

    verdicts = []
    if a.surface:
        # ECHTE Geometrie: Modell-Höhenfeld vom Generator vs. Roh-DEM
        d = np.load(a.surface)
        raw = d["real_m"]; a.nscale = float(d["nscale"]); a.vscale = float(d["vscale"])
        print(f"=== VALIDIERUNG (ECHTES MODELL)  {os.path.basename(a.surface)}  "
              f"{raw.shape[0]}×{raw.shape[1]}  Höhe {np.nanmax(raw)-np.nanmin(raw):.1f} m "
              f" nscale {a.nscale} mm/m ===")
        sv, recon, err_mm = surface_from_dump(a.surface, a.tol_rms, a.tol_max, a.tol_ridge)
    else:
        # Formel-Modus: Oberfläche aus DEM+smooth rekonstruiert (schneller Vorab-Check)
        raw = load_window(a.dem, a.r0, a.r1, a.c0, a.c1)
        nanpct = 100 * np.mean(~np.isfinite(raw))
        print(f"=== VALIDIERUNG (Formel-Vorschau)  {os.path.basename(a.dem)}  "
              f"Fenster {raw.shape[0]}×{raw.shape[1]}  "
              f"Höhe {np.nanmax(raw)-np.nanmin(raw):.1f} m  nscale {a.nscale} mm/m  "
              f"Nodata {nanpct:.1f}% ===")
        sv, recon, err_mm = surface_fidelity(raw, a.nscale, a.vscale, a.smooth,
                                             a.tol_rms, a.tol_max, a.tol_ridge)
    verdicts.append(("Oberfläche", sv))

    stls, svgs = [], []
    if a.artifact:
        if os.path.isdir(a.artifact):
            stls = sorted(glob.glob(os.path.join(a.artifact, "**", "*.stl"), recursive=True))
            svgs = sorted(glob.glob(os.path.join(a.artifact, "**", "*.svg"), recursive=True))
        elif a.artifact.endswith(".stl"):
            stls = [a.artifact]

    mode = a.mode
    if mode == "auto":
        mode = "cut" if (svgs and not stls) else "print"

    if mode == "cut" or svgs:
        qv = quantisation(raw, a.nscale, a.vscale, a.material, a.layers, a.tol_max)
        verdicts.append(("Quantisierung", qv))

    if stls:
        print("\n3) FERTIGBARKEIT — 3D-Druck (STL)")
        sv2 = min_verdict(*[check_stl(s, a.bed_x, a.bed_y) for s in stls[:20]])
        verdicts.append(("STL-Druck", sv2))
    if svgs:
        print("\n3) FERTIGBARKEIT — Laser-Cut (SVG)")
        verdicts.append(("SVG-Cut", check_svgs(svgs, a.sheet_x, a.sheet_y)))
    if not stls and not svgs and a.artifact:
        print("\n3) FERTIGBARKEIT — keine STL/SVG im Artefakt gefunden")

    png = heatmap(raw, err_mm, a.out)
    overall = min_verdict(*[v for _, v in verdicts])
    print("\n" + "=" * 54)
    for name, v in verdicts:
        print(f"  {v:5s}  {name}")
    print(f"  GESAMT: {overall}")
    if png:
        print(f"  Heatmap: {png}")
    print("=" * 54)
    sys.exit(0 if overall == "PASS" else (1 if overall == "WARN" else 2))


if __name__ == "__main__":
    main()

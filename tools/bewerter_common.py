#!/usr/bin/env python3
"""bewerter_common.py — gemeinsame Basis für die drei Modell-Juroren + Voting.

Ein "Modell" wird über ein MANIFEST (JSON) beschrieben, damit alle drei Juroren
dasselbe bewerten. Minimal-Felder:

  {
    "name": "Hirschsprung",
    "typ": "gelaende" | "bauwerk",
    "dem": "daten/hoellental/dgm025_full.npy",   # 2D-Höhenfeld (Meter)
    "r0":150,"r1":750,"c0":2900,"c1":3700,       # Fenster (Zellindizes); flip [::-1]
    "cell_m": 0.25,                               # Zellgröße real (m)
    "nscale": 3.125,                             # mm je echtem Höhen-Meter (6.25=1:160)
    "mm_per_cell": 0.78125,                      # Modell-mm je DGM-Zelle (horizontal)
    "vscale": 1.0,                               # Überhöhung
    "smooth": 1.0,                              # Glättung des Generators (Zellen)
    "artifact": "modelle/hoellental_geruest_a3", # optional: SVG/STL-Ordner
    "bed": [410, 400],                           # Laserbett / Druckbett mm
    "signatur": "felswand|wasserfall|see|staumauer|viadukt|turm|burg|gipfel|schlucht"
  }

Jeder Juror gibt ein einheitliches Verdikt-Dict zurück:
  {judge, score (0..100), verdict (PASS|WARN|FAIL), reasons:[...], metrics:{...}}
"""
import json, os, sys, glob
import numpy as np

# validate_modell-Bausteine wiederverwenden (keine Duplikate)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def load_manifest(path):
    with open(path) as f:
        m = json.load(f)
    m.setdefault("typ", "gelaende")
    m.setdefault("cell_m", 1.0)
    m.setdefault("nscale", 6.25)
    m.setdefault("vscale", 1.0)
    m.setdefault("smooth", 1.0)
    m.setdefault("bed", [410, 400])
    m.setdefault("mm_per_cell", m["cell_m"] * m["nscale"])
    m.setdefault("artifact", "")
    m.setdefault("signatur", "")
    return m


def load_relief(m):
    """DEM-Fenster -> relief (Meter, 0=Minimum), geflippt wie die Generatoren."""
    A = np.load(m["dem"]).astype(float)
    if A.ndim != 2:
        raise SystemExit(f"DEM {m['dem']} ist {A.ndim}D, erwartet 2D")
    r0 = m.get("r0", 0); r1 = m.get("r1", A.shape[0])
    c0 = m.get("c0", 0); c1 = m.get("c1", A.shape[1])
    win = A[r0:r1, c0:c1]
    win = np.where(win < -1000, np.nan, win)
    win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]
    return win - win.min()


# ---------- Geometrie-/Relief-Metriken ----------

def slope_deg(relief, cell_m):
    gy, gx = np.gradient(relief, cell_m, cell_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def silhouette_distinctiveness(relief):
    """Wie 'gezeichnet' ist die Skyline? Std der Spalten-Maxima / Reliefspanne (0..1)."""
    sky = relief.max(axis=0)
    span = relief.max() - relief.min() + 1e-6
    return float(np.std(sky) / span)


def ruggedness(relief, cell_m):
    """Formfülle / TRI: mittlerer Höhenunterschied zu Nachbarn in Metern — misst, wie
    'skulptiert' das Gelände ist (Klamm/Fels = hoch, glatte Wiese = ~0). Robust für
    symmetrische UND asymmetrische Features (anders als Silhouetten-Streuung)."""
    d = (np.abs(np.diff(relief, axis=0)).mean() + np.abs(np.diff(relief, axis=1)).mean()) / 2
    return float(d)


def water_fraction(relief, cell_m, flat_deg=2.0):
    """Anteil nahezu waagerechter Fläche (See/Wasser-Proxy)."""
    return float((slope_deg(relief, cell_m) < flat_deg).mean())


def steep_fraction(relief, cell_m, steep_deg=45.0):
    return float((slope_deg(relief, cell_m) >= steep_deg).mean())


def best_window_drama(relief, cell_m, frac=0.5, steep_deg=45.0):
    """Findet die DRAMATISCHSTE Teilregion (so wie man den Modell-Ausschnitt rahmt).
    Schiebt ein frac×frac-Fenster (grobes Raster) und nimmt das mit max. Steilwand-Anteil.
    Gibt (best_steep_frac, best_relief_m, best_p95_slope_deg, (y0,x0,y1,x1)) zurück."""
    ny, nx = relief.shape
    wy, wx = max(8, int(ny * frac)), max(8, int(nx * frac))
    sl = slope_deg(relief, cell_m)
    best = (0.0, 0.0, 0.0, (0, 0, ny, nx))
    steps = 5
    for iy in range(steps):
        for ix in range(steps):
            y0 = min(ny - wy, int(iy * (ny - wy) / max(1, steps - 1)))
            x0 = min(nx - wx, int(ix * (nx - wx) / max(1, steps - 1)))
            sub = relief[y0:y0+wy, x0:x0+wx]
            subs = sl[y0:y0+wy, x0:x0+wx]
            sf = float((subs >= steep_deg).mean())
            if sf > best[0]:
                best = (sf, float(sub.max()-sub.min()),
                        float(np.percentile(subs, 95)), (y0, x0, y0+wy, x0+wx))
    return best


# ---------- Artefakt-Parsing (SVG/STL) via validate_modell ----------

def parse_artifacts(m):
    """Gibt (svgs, stls) als Pfadlisten zurück ([],[] wenn kein Ordner)."""
    art = m.get("artifact", "")
    if not art or not os.path.exists(art):
        return [], []
    svgs = sorted(glob.glob(os.path.join(art, "*.svg")))
    stls = sorted(glob.glob(os.path.join(art, "*.stl")))
    return svgs, stls


def stl_health(path, bed_x, bed_y):
    """watertight / Bett-Fit / Maße einer STL via trimesh."""
    import trimesh
    mesh = trimesh.load(path, force="mesh")
    bb = mesh.bounding_box.extents
    return {"watertight": bool(mesh.is_watertight),
            "fits_bed": bool(bb[0] <= bed_x and bb[1] <= bed_y),
            "mm": [round(float(bb[0])), round(float(bb[1])), round(float(bb[2]))]}


# ---------- Scoring-Helfer ----------

def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def lin(x, x0, x1):
    """0 bei x0, 100 bei x1, linear, geklemmt."""
    if x1 == x0:
        return 100.0 if x >= x1 else 0.0
    return clamp((x - x0) / (x1 - x0) * 100.0)


def verdict_from_score(score, warn=55, pas=70):
    return "PASS" if score >= pas else ("WARN" if score >= warn else "FAIL")


def print_verdict(v, verbose=True):
    icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[v["verdict"]]
    print(f"{icon} {v['judge']:<22} {v['score']:5.1f}/100  [{v['verdict']}]")
    if verbose:
        for r in v["reasons"]:
            print(f"      · {r}")

#!/usr/bin/env python3
"""eggcrate_sim.py — REINE SOFTWARE-STUDIE (keine Hardware):
Wie genau bildet das Egg-Crate-Gitter die echte Topographie ab — als Funktion der
Rippen-/Schnitt-Anzahl, für verschiedene Strategien (uniform / adaptiv / adaptiv+snap)?

Modell der "Gips-Haut": sie liegt EXAKT auf den Rippen-Oberkanten (= echtes Gelände
entlang der Gitterlinien) und spannt im Zellinneren -> COONS-transfinite Interpolation.
Fehler = rekonstruierte Haut vs. echtes DEM.

Outputs:
  <out>/pareto.png     Genauigkeit (RMS/P95) vs. Schnitt-Länge, 3 Strategien
  <out>/surfaces3d.png matplotlib-3D: echt vs. Rekonstruktionen
  <out>/sim3d.html     INTERAKTIV (plotly): echt / Rekonstruktion / Fehler, Dichte wählbar
  + Konsolen-Tabelle + Sweet-Spot (Knie der Kurve)
"""
import os, sys, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import terrain_eggcrate as te
from scipy.ndimage import zoom, gaussian_filter

# ------------------------------------------------------------------ DEM -> Relief
def build_Hf(a):
    dem = np.load(a.dem); win = dem[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]; wmin = float(win.min()); zf = max(1, a.zoom)
    rel = gaussian_filter(zoom(win - wmin, zf, order=1) if zf > 1 else (win - wmin), a.smooth)
    cell = a.mm / zf
    Hf = rel * a.nscale * a.vscale + a.base
    return Hf, cell

def bilin(Hf, xs, ys, cell):
    NY, NX = Hf.shape
    fx = np.clip(np.asarray(xs, float) / cell, 0, NX - 1.001)
    fy = np.clip(np.asarray(ys, float) / cell, 0, NY - 1.001)
    x0 = np.floor(fx).astype(int); y0 = np.floor(fy).astype(int); x1 = x0 + 1; y1 = y0 + 1
    tx = fx - x0; ty = fy - y0
    return (Hf[y0, x0] * (1 - tx) * (1 - ty) + Hf[y0, x1] * tx * (1 - ty)
            + Hf[y1, x0] * (1 - tx) * ty + Hf[y1, x1] * tx * ty)

# ------------------------------------------------------------------ Rekonstruktion
def reconstruct(Hf, cell, xpos, ypos):
    """Coons-transfinite Haut über den Rippen-Oberkanten. Exakt auf jeder Gitterlinie
    (x=xpos, y=ypos = echtes Gelände), bilinear geblendet im Zellinneren."""
    NY, NX = Hf.shape
    X = (np.arange(NX) + 0.5) * cell; Y = (np.arange(NY) + 0.5) * cell
    XX, YY = np.meshgrid(X, Y)
    xg = np.array(sorted(set(np.round(xpos, 4)))); yg = np.array(sorted(set(np.round(ypos, 4))))
    ix = np.clip(np.searchsorted(xg, XX) - 1, 0, len(xg) - 2)
    iy = np.clip(np.searchsorted(yg, YY) - 1, 0, len(yg) - 2)
    x0 = xg[ix]; x1 = xg[ix + 1]; y0 = yg[iy]; y1 = yg[iy + 1]
    u = (XX - x0) / np.maximum(x1 - x0, 1e-9); v = (YY - y0) / np.maximum(y1 - y0, 1e-9)
    L = bilin(Hf, x0, YY, cell); R = bilin(Hf, x1, YY, cell)      # linke/rechte Rippen-Oberkante
    B = bilin(Hf, XX, y0, cell); T = bilin(Hf, XX, y1, cell)      # untere/obere Rippen-Oberkante
    c00 = bilin(Hf, x0, y0, cell); c10 = bilin(Hf, x1, y0, cell)
    c01 = bilin(Hf, x0, y1, cell); c11 = bilin(Hf, x1, y1, cell)
    rec = ((1 - u) * L + u * R + (1 - v) * B + v * T
           - ((1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11))
    inside = (XX >= xg[0]) & (XX <= xg[-1]) & (YY >= yg[0]) & (YY <= yg[-1])
    return rec, inside

# ------------------------------------------------------------------ Kanten-Lineale
def detect_edges(Hf, cell):
    """Scharfe Bruchkanten (Felsgrat, Einschnitt, Portal) als Segmente (x0,y0,x1,y1) mm —
    dieselbe Erkennung wie die echten Kanten-Lineale (K*.svg)."""
    import manmade_edges as mmE
    try:
        return list(mmE.detect_edges_ridges(Hf, cell, min_len_mm=10.0))
    except Exception:
        return []

def _edge_dist(Hf, cell, edges):
    NY, NX = Hf.shape
    X = (np.arange(NX) + 0.5) * cell; Y = (np.arange(NY) + 0.5) * cell
    XX, YY = np.meshgrid(X, Y); dist = np.full(Hf.shape, 1e9)
    for (x0, y0, x1, y1) in edges:
        dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((XX - x0) * dx + (YY - y0) * dy) / L2, 0, 1)
        d = np.hypot(XX - (x0 + t * dx), YY - (y0 + t * dy))
        dist = np.minimum(dist, d)
    return dist

def reconstruct_rulers(Hf, cell, xpos, ypos, edges, band):
    """Gitter-Haut (Coons) PLUS Kanten-Lineale: entlang jeder scharfen Kante pinnt ein
    aufgeklebtes Lineal die Haut ans echte Gelände, mit Übergang über 'band' mm."""
    rec, inside = reconstruct(Hf, cell, xpos, ypos)
    if not edges: return rec, inside
    w = np.clip(1 - _edge_dist(Hf, cell, edges) / band, 0, 1)   # 1 an der Kante -> 0 ab band
    return w * Hf + (1 - w) * rec, inside

def ruler_cut(Hf, cell, edges):
    """Schnitt-Länge der Kanten-Lineale: je Kante Ober+Unterkante (~2× Länge)."""
    tot = 0.0
    for (x0, y0, x1, y1) in edges:
        tot += 2.0 * float(np.hypot(x1 - x0, y1 - y0))
    return tot

# ------------------------------------------------------------------ Metriken
def metrics(Hf, rec, inside, nscale, vscale):
    err = np.abs(rec - Hf)[inside]
    mm2m = 1.0 / (nscale * vscale)                 # Modell-mm -> echte Meter
    return dict(rms_mm=float(np.sqrt(np.mean(err**2))), p95_mm=float(np.percentile(err, 95)),
                max_mm=float(err.max()), mean_mm=float(err.mean()),
                rms_m=float(np.sqrt(np.mean(err**2))) * mm2m, p95_m=float(np.percentile(err, 95)) * mm2m,
                max_m=float(err.max()) * mm2m)

def cut_cost(Hf, cell, xpos, ypos, slotw):
    """Schnitt-Aufwand: #Rippen, Gesamt-Rippenlänge (mm), und geschätzte Laser-Schnittlänge
    (Oberkanten-Pfad + Boden + Seiten + Steck-Schlitze)."""
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell
    nribs = len(xpos) + len(ypos)
    rib_len = len(ypos) * Wx + len(xpos) * Dy       # je X-Rippe Wx lang, je Y-Rippe Dy
    cut = 0.0
    def prof_len(xs, ys):
        z = bilin(Hf, xs, ys, cell)
        s = np.asarray(xs if np.ptp(xs) > np.ptp(ys) else ys, float)
        return float(np.sum(np.hypot(np.diff(s), np.diff(z))))
    S = np.linspace(0, Wx, int(Wx) + 1)
    for yr in ypos:                                  # X-Rippen (entlang x)
        z = bilin(Hf, S, np.full_like(S, yr), cell)
        cut += prof_len(S, np.full_like(S, yr)) + Wx + 2 * z.mean()
        cut += sum(bilin(Hf, xp, yr, cell) + slotw for xp in xpos)   # Schlitze (halbe Höhe ~ Umfang)
    Sy = np.linspace(0, Dy, int(Dy) + 1)
    for xr in xpos:                                  # Y-Rippen (entlang y)
        z = bilin(Hf, np.full_like(Sy, xr), Sy, cell)
        cut += prof_len(np.full_like(Sy, xr), Sy) + Dy + 2 * z.mean()
        cut += sum(bilin(Hf, xr, yp, cell) + slotw for yp in ypos)
    return nribs, rib_len, cut

# ------------------------------------------------------------------ Sweep
def run_sweep(Hf, cell, a):
    strategies = [("uniform", dict(uniform=True, snap=False)),
                  ("adaptiv", dict(uniform=False, snap=False)),
                  ("adaptiv+snap", dict(uniform=False, snap=True))]
    ns = [int(x) for x in a.ns.split(",")]
    edges = detect_edges(Hf, cell)
    out = {}
    for name, kw in strategies:
        rows = []
        for n in ns:
            xpos, ypos = te.rib_positions(Hf, cell, n, n, a.min_gap, snap_pct=a.snap_pct, **kw)
            if len(xpos) < 2 or len(ypos) < 2: continue
            rec, inside = reconstruct(Hf, cell, xpos, ypos)
            m = metrics(Hf, rec, inside, a.nscale, a.vscale)
            nribs, rib_len, cut = cut_cost(Hf, cell, xpos, ypos, a.thickness + a.fit)
            rows.append(dict(n=n, nribs=nribs, rib_len=rib_len, cut=cut,
                             nx=len(xpos), ny=len(ypos), xpos=xpos, ypos=ypos,
                             edges=None, **m))
        out[name] = rows
    # 4. Strategie: adaptiv+snap-Gitter PLUS aufgeklebte Kanten-Lineale an scharfen Kanten
    rc = ruler_cut(Hf, cell, edges)
    rows = []
    for n in ns:
        xpos, ypos = te.rib_positions(Hf, cell, n, n, a.min_gap, snap_pct=a.snap_pct, uniform=False, snap=True)
        if len(xpos) < 2 or len(ypos) < 2: continue
        rec, inside = reconstruct_rulers(Hf, cell, xpos, ypos, edges, a.ruler_band)
        m = metrics(Hf, rec, inside, a.nscale, a.vscale)
        nribs, rib_len, cut = cut_cost(Hf, cell, xpos, ypos, a.thickness + a.fit)
        rows.append(dict(n=n, nribs=nribs + len(edges), rib_len=rib_len, cut=cut + rc,
                         nx=len(xpos), ny=len(ypos), xpos=xpos, ypos=ypos, edges=edges, **m))
    out[f"adaptiv+snap+{len(edges)} Lineale"] = rows
    out["_edges"] = edges
    return out

def knee(rows, key_cut="cut", key_err="rms_m"):
    """Kniepunkt (Kneedle): max. senkrechter Abstand zur Verbindungslinie Anfang-Ende."""
    if len(rows) < 3: return rows[-1] if rows else None
    c = np.array([r[key_cut] for r in rows]); e = np.array([r[key_err] for r in rows])
    cn = (c - c.min()) / (np.ptp(c) + 1e-9); en = (e - e.min()) / (np.ptp(e) + 1e-9)
    d = (cn - cn[0]) * (en[-1] - en[0]) - (en - en[0]) * (cn[-1] - cn[0])
    return rows[int(np.argmax(np.abs(d)))]

# ------------------------------------------------------------------ Plots
def _strat_rows(out):
    return [(n, r) for n, r in out.items()
            if not n.startswith("_") and isinstance(r, list) and r and isinstance(r[0], dict)]

def _color(name):
    if name.startswith("uniform"): return "#888888"
    if name == "adaptiv": return "#1f77b4"
    if name.startswith("adaptiv+snap+"): return "#2ca02c"   # +Lineale
    if name.startswith("adaptiv+snap"): return "#d62728"
    return "#9467bd"

def plot_pareto(out, a):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(19, 6))
    for name, rows in _strat_rows(out):
        c = [r["cut"] / 1000 for r in rows]
        for ax, k in zip(axs, ("rms_m", "p95_m", "max_m")):
            ax.plot(c, [r[k] for r in rows], "o-", color=_color(name), label=name, ms=5)
    kn = knee(out.get("adaptiv+snap", []))
    if kn: axs[0].plot(kn["cut"] / 1000, kn["rms_m"], "k*", ms=18, label=f"Sweet-Spot ({kn['nribs']} R)")
    for ax, t in zip(axs, ["RMS-Fehler (m)", "P95-Fehler (m)", "MAX-Fehler (m) — Klippen"]):
        ax.set_xlabel("geschätzte Laser-Schnittlänge (m)"); ax.set_ylabel(t)
        ax.set_title(t); ax.grid(True, alpha=.3); ax.legend(fontsize=8)
    plt.suptitle("Relief-Genauigkeit vs. Schnitt-Aufwand — weniger Schnitt links, genauer unten", y=1.02)
    plt.tight_layout(); plt.savefig(f"{a.out}/pareto.png", dpi=110, bbox_inches="tight"); plt.close()

def _ruler_key(out):
    for n in out:
        if isinstance(n, str) and n.startswith("adaptiv+snap+"): return n
    return None

def plot_surfaces3d(Hf, cell, out, a):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    g = out.get("adaptiv+snap", []); rk = _ruler_key(out); rr = out.get(rk, [])
    if len(g) < 2: return
    kg = knee(g)
    panels = [("ECHTES Gelände (DEM)", Hf, None)]
    panels.append((f"Gitter {kg['nribs']} Rippen · RMS {kg['rms_m']:.2f}m · max {kg['max_m']:.1f}m",
                   reconstruct(Hf, cell, kg["xpos"], kg["ypos"])[0], None))
    if rr:
        kr = next((r for r in rr if r["n"] == kg["n"]), rr[-1])
        panels.append((f"+Kanten-Lineale · RMS {kr['rms_m']:.2f}m · max {kr['max_m']:.1f}m",
                       reconstruct_rulers(Hf, cell, kr["xpos"], kr["ypos"], out["_edges"], a.ruler_band)[0], None))
    NY, NX = Hf.shape; X = np.arange(NX) * cell; Y = np.arange(NY) * cell
    XX, YY = np.meshgrid(X, Y); st = max(1, max(NX, NY) // 90)
    fig = plt.figure(figsize=(16, 5))
    for i, (title, Z, _) in enumerate(panels):
        ax = fig.add_subplot(1, len(panels), i + 1, projection="3d")
        ax.plot_surface(XX[::st, ::st], YY[::st, ::st], Z[::st, ::st], cmap="terrain", linewidth=0, antialiased=True)
        ax.set_title(title, fontsize=9); ax.set_box_aspect((NX * cell, NY * cell, Hf.max() * 2.2))
        ax.view_init(elev=35, azim=-60); ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
    plt.tight_layout(); plt.savefig(f"{a.out}/surfaces3d.png", dpi=110); plt.close()

def write_html(Hf, cell, out, a):
    import plotly.graph_objects as go
    g = out.get("adaptiv+snap", [])
    if not g: return
    kg = knee(g); rk = _ruler_key(out); rr = out.get(rk, [])
    # Auswahl: grob, Sweet-Spot, fein (Gitter) + Sweet-Spot MIT Kanten-Linealen
    picks = [g[0], kg, g[-1]]
    pick_rec = [reconstruct(Hf, cell, p["xpos"], p["ypos"])[0] for p in picks]
    pick_lab = [f"Gitter {p['nribs']}R" for p in picks]
    if rr:
        kr = next((r for r in rr if r["n"] == kg["n"]), rr[-1])
        picks.append(kr); pick_rec.append(reconstruct_rulers(Hf, cell, kr["xpos"], kr["ypos"], out["_edges"], a.ruler_band)[0])
        pick_lab.append(f"Gitter+{len(out['_edges'])} Kanten-Lineale ({kr['nribs']}R)")
    NY, NX = Hf.shape; st = max(1, max(NX, NY) // 120)
    X = (np.arange(0, NX, st)) * cell; Y = (np.arange(0, NY, st)) * cell
    Ht = Hf[::st, ::st]
    fig = go.Figure()
    fig.add_surface(x=X, y=Y, z=Ht, colorscale="earth", name="ECHT", showscale=False, opacity=1.0)
    buttons = [dict(label="ECHTES Gelände", method="update",
                    args=[{"visible": [True] + [False] * (2 * len(picks))}])]
    vis_idx = 1
    for p, rec, plab in zip(picks, pick_rec, pick_lab):
        err = np.abs(rec - Hf)
        fig.add_surface(x=X, y=Y, z=rec[::st, ::st], colorscale="earth", showscale=False, visible=False,
                        name=f"REKON {plab}")
        fig.add_surface(x=X, y=Y, z=rec[::st, ::st], surfacecolor=err[::st, ::st], colorscale="Hot",
                        showscale=True, visible=False, name=f"FEHLER {plab}",
                        colorbar=dict(title="|Fehler| mm"))
        lab = f"{plab} (RMS {p['rms_m']:.2f}m, P95 {p['p95_m']:.2f}m, max {p['max_m']:.1f}m)"
        v1 = [False] * (1 + 2 * len(picks)); v1[vis_idx] = True
        v2 = [False] * (1 + 2 * len(picks)); v2[vis_idx + 1] = True
        buttons.append(dict(label="Rekon: " + lab, method="update", args=[{"visible": v1}]))
        buttons.append(dict(label="Fehler: " + lab, method="update", args=[{"visible": v2}]))
        vis_idx += 2
    fig.update_layout(title="Egg-Crate Relief-Rekonstruktion — echt / Rekonstruktion / Fehler",
                      updatemenus=[dict(buttons=buttons, x=0.0, y=1.0, xanchor="left")],
                      scene=dict(aspectmode="data", zaxis=dict(title="Höhe (mm)")), height=820)
    fig.write_html(f"{a.out}/sim3d.html", include_plotlyjs="cdn")

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--mm", type=float, default=0.78125); ap.add_argument("--nscale", type=float, default=3.125)
    ap.add_argument("--zoom", type=int, default=1)
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--vscale", type=float, default=0.85); ap.add_argument("--smooth", type=float, default=0.6)
    ap.add_argument("--base", type=float, default=12.0); ap.add_argument("--min-gap", type=float, default=7.0)
    ap.add_argument("--snap-pct", type=float, default=80.0); ap.add_argument("--thickness", type=float, default=3.0)
    ap.add_argument("--fit", type=float, default=-0.5)
    ap.add_argument("--ns", default="3,4,5,6,8,10,12,15,18", help="Dichte-Sweep (nx=ny)")
    ap.add_argument("--ruler-band", type=float, default=6.0, dest="ruler_band", help="Einfluss-Breite eines Kanten-Lineals (mm): Haut folgt bis hierher dem echten Gelände")
    ap.add_argument("--out", default="/tmp/eggcrate_sim")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    Hf, cell = build_Hf(a)
    NY, NX = Hf.shape
    print(f"DEM-Fenster {NX}x{NY} Zellen, {NX*cell:.0f}x{NY*cell:.0f} mm, Höhe {Hf.min():.0f}..{Hf.max():.0f} mm")
    print(f"Relief-Spannweite real: {(Hf.max()-Hf.min())/(a.nscale*a.vscale):.0f} m\n")
    out = run_sweep(Hf, cell, a)
    print(f"{'Strategie':26s} {'n':>3} {'#Teile':>6} {'Schnitt m':>9} {'RMS m':>7} {'P95 m':>7} {'max m':>7}")
    for name, rows in _strat_rows(out):
        for r in rows:
            print(f"{name:26s} {r['n']:>3} {r['nribs']:>6} {r['cut']/1000:>9.1f} "
                  f"{r['rms_m']:>7.2f} {r['p95_m']:>7.2f} {r['max_m']:>7.2f}")
        print()
    kn = knee(out.get("adaptiv+snap", []))
    if kn:
        print(f"★ SWEET-SPOT Gitter (adaptiv+snap, Knie): {kn['nribs']} Teile "
              f"({kn['nx']}x + {kn['ny']}y), ~{kn['cut']/1000:.1f} m Schnitt, "
              f"RMS {kn['rms_m']:.2f} m / P95 {kn['p95_m']:.2f} m / max {kn['max_m']:.2f} m")
    rk = _ruler_key(out); rr = out.get(rk, [])
    if rr and kn:
        kr = next((r for r in rr if r["n"] == kn["n"]), rr[-1])
        print(f"★ Mit Kanten-Linealen (gleiche Dichte): {kr['nribs']} Teile, ~{kr['cut']/1000:.1f} m Schnitt, "
              f"RMS {kr['rms_m']:.2f} m / P95 {kr['p95_m']:.2f} m / max {kr['max_m']:.2f} m "
              f"(Max-Fehler {100*(1-kr['max_m']/max(kn['max_m'],1e-9)):.0f}% kleiner)")
    plot_pareto(out, a); plot_surfaces3d(Hf, cell, out, a); write_html(Hf, cell, out, a)
    print(f"\n-> {a.out}/pareto.png  {a.out}/surfaces3d.png  {a.out}/sim3d.html (interaktiv)")

if __name__ == "__main__":
    main()

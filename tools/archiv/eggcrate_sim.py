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

def reconstruct_rulers(Hf, cell, xpos, ypos, edges, fin_w, drape=0.0):
    """Gitter-Haut (Coons) PLUS Kanten-Lineale als EINSEITIGE vertikale Finnen:
    entlang jeder scharfen Kante folgt die Haut EXAKT dem echten Gelände (die Finne pinnt
    ihre Linie über die Finnen-Dicke fin_w — KEIN symmetrisches Verschmieren über die Klippe).
    Optional 'drape' mm: kurze EINSEITIGE Drapierung nur auf der TIEFEREN Seite (wo die
    Finnen-Oberkante über der Gitter-Haut steht und der Gips an der Finne herunterhängt)."""
    rec, inside = reconstruct(Hf, cell, xpos, ypos)
    if not edges: return rec, inside
    d = _edge_dist(Hf, cell, edges); rec = rec.copy()
    rec[d <= fin_w / 2.0] = Hf[d <= fin_w / 2.0]                 # die Finne selbst = echtes Gelände
    if drape > 0:                                                # einseitig: nur wo Finne über Haut steht
        band = (d > fin_w / 2.0) & (d <= fin_w / 2.0 + drape) & (Hf > rec)
        w = np.clip(1 - (d - fin_w / 2.0) / max(drape, 1e-9), 0, 1)
        rec = np.where(band, w * Hf + (1 - w) * rec, rec)
    return rec, inside

def ruler_cut(Hf, cell, edges):
    """Schnitt-Länge der Kanten-Lineale: je Kante Ober+Unterkante (~2× Länge)."""
    tot = 0.0
    for (x0, y0, x1, y1) in edges:
        tot += 2.0 * float(np.hypot(x1 - x0, y1 - y0))
    return tot

# ------------------------------------------------------------------ Tunnel (Trasse)
def load_track(a, Wx, Dy):
    """Trasse (mx,my,mz,is_tunnel in Modell-mm) laden + ~1mm fein interpolieren, aufs Fenster."""
    if not a.track or not os.path.exists(a.track): return []
    raw = np.load(a.track); dense = []
    for k in range(len(raw) - 1):
        p, q = raw[k], raw[k + 1]; L = max(2, int(np.hypot(q[0] - p[0], q[1] - p[1]) / 1.0))
        for tt in np.linspace(0, 1, L, endpoint=(k == len(raw) - 2)):
            dense.append((p[0] + (q[0] - p[0]) * tt, p[1] + (q[1] - p[1]) * tt,
                          p[2] + (q[2] - p[2]) * tt, p[3] > 0.5))
    return [pt for pt in dense if -2 <= pt[0] <= Wx + 2 and -2 <= pt[1] <= Dy + 2]

def track_segs(track):
    return [(track[i][0], track[i][1], track[i + 1][0], track[i + 1][1]) for i in range(len(track) - 1)]

def _dist_to(shape, cell, segs):
    NY, NX = shape; X = (np.arange(NX) + 0.5) * cell; Y = (np.arange(NY) + 0.5) * cell
    XX, YY = np.meshgrid(X, Y); d = np.full(shape, 1e9)
    for (x0, y0, x1, y1) in segs:
        dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy + 1e-9
        t = np.clip(((XX - x0) * dx + (YY - y0) * dy) / L2, 0, 1)
        d = np.minimum(d, np.hypot(XX - (x0 + t * dx), YY - (y0 + t * dy)))
    return d

def tunnel_masks(Hf, cell, track, corridor):
    """Masken: Tunnel-Korridor (nahe der Trasse) und Portal-Umkreis (Tunnel<->offen-Übergang)."""
    if not track: return np.zeros(Hf.shape, bool), np.zeros(Hf.shape, bool)
    tmask = _dist_to(Hf.shape, cell, track_segs(track)) <= corridor
    portals = [track[i] for i in range(1, len(track)) if track[i][3] != track[i - 1][3]]
    if portals:
        psegs = [(p[0] - .1, p[1] - .1, p[0] + .1, p[1] + .1) for p in portals]
        pmask = _dist_to(Hf.shape, cell, psegs) <= max(corridor, 4.0)
    else:
        pmask = np.zeros(Hf.shape, bool)
    return tmask, pmask

def tun_metrics(Hf, rec, cell, track):
    """Fehler AUF der Trassen-Linie (wo Tunnel + Portal wirklich liegen), nicht in einem
    2D-Klecks. Portal = Trassen-Punkte nahe einem Tunnel<->offen-Übergang (±6 mm entlang)."""
    if not track:
        return dict(tun_rms_mm=0.0, tun_max_mm=0.0, portal_max_mm=0.0)
    P = np.array([(p[0], p[1], p[2], float(p[3])) for p in track])
    e = np.abs(bilin(rec, P[:, 0], P[:, 1], cell) - bilin(Hf, P[:, 0], P[:, 1], cell))
    it = P[:, 3] > 0.5; trans = np.where(it[1:] != it[:-1])[0]
    d = np.r_[0.0, np.cumsum(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1])))]
    pmask = np.zeros(len(P), bool)
    for ti in trans: pmask |= np.abs(d - d[ti]) <= 6.0
    ep = e[pmask] if pmask.any() else e
    return dict(tun_rms_mm=float(np.sqrt((e ** 2).mean())), tun_max_mm=float(e.max()),
                portal_max_mm=float(ep.max()))

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
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell
    track = load_track(a, Wx, Dy)
    tmask, pmask = tunnel_masks(Hf, cell, track, a.corridor)
    tseg = track_segs(track)
    out = {}
    for name, kw in strategies:
        rows = []
        for n in ns:
            xpos, ypos = te.rib_positions(Hf, cell, n, n, a.min_gap, snap_pct=a.snap_pct, **kw)
            if len(xpos) < 2 or len(ypos) < 2: continue
            rec, inside = reconstruct(Hf, cell, xpos, ypos)
            m = metrics(Hf, rec, inside, a.nscale, a.vscale); m.update(tun_metrics(Hf, rec, cell, track))
            nribs, rib_len, cut = cut_cost(Hf, cell, xpos, ypos, a.thickness + a.fit)
            rows.append(dict(n=n, nribs=nribs, rib_len=rib_len, cut=cut,
                             nx=len(xpos), ny=len(ypos), xpos=xpos, ypos=ypos, edges=None, **m))
        out[name] = rows
    # 4. adaptiv+snap-Gitter PLUS Kanten-Lineale an scharfen Kanten
    rc = ruler_cut(Hf, cell, edges)
    # 5. zusätzlich mit TUNNEL-LINEALEN entlang der Trasse (pinnt die Tunnel-Kanten)
    rc_tun = ruler_cut(Hf, cell, tseg)
    rows4, rows5 = [], []
    for n in ns:
        xpos, ypos = te.rib_positions(Hf, cell, n, n, a.min_gap, snap_pct=a.snap_pct, uniform=False, snap=True)
        if len(xpos) < 2 or len(ypos) < 2: continue
        nribs, rib_len, cut = cut_cost(Hf, cell, xpos, ypos, a.thickness + a.fit)
        rec, inside = reconstruct_rulers(Hf, cell, xpos, ypos, edges, a.fin_width, a.fin_drape)
        m = metrics(Hf, rec, inside, a.nscale, a.vscale); m.update(tun_metrics(Hf, rec, cell, track))
        rows4.append(dict(n=n, nribs=nribs + len(edges), rib_len=rib_len, cut=cut + rc,
                          nx=len(xpos), ny=len(ypos), xpos=xpos, ypos=ypos, edges=edges, **m))
        rec2, _ = reconstruct_rulers(Hf, cell, xpos, ypos, edges + tseg, a.fin_width, a.fin_drape)
        m2 = metrics(Hf, rec2, inside, a.nscale, a.vscale); m2.update(tun_metrics(Hf, rec2, cell, track))
        rows5.append(dict(n=n, nribs=nribs + len(edges) + len(tseg), rib_len=rib_len, cut=cut + rc + rc_tun,
                          nx=len(xpos), ny=len(ypos), xpos=xpos, ypos=ypos, edges=edges + tseg, **m2))
    out[f"adaptiv+snap+{len(edges)} Lineale"] = rows4
    if track: out["adaptiv+snap+Lineale+Tunnel"] = rows5
    out["_edges"] = edges; out["_track"] = track; out["_tmask"] = tmask; out["_pmask"] = pmask; out["_tseg"] = tseg
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
    if "Tunnel" in name: return "#9467bd"                   # +Tunnel-Lineale
    if name.startswith("uniform"): return "#888888"
    if name == "adaptiv": return "#1f77b4"
    if name.startswith("adaptiv+snap+"): return "#2ca02c"   # +Lineale
    if name.startswith("adaptiv+snap"): return "#d62728"
    return "#17becf"

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
                       reconstruct_rulers(Hf, cell, kr["xpos"], kr["ypos"], out["_edges"], a.fin_width, a.fin_drape)[0], None))
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
        picks.append(kr); pick_rec.append(reconstruct_rulers(Hf, cell, kr["xpos"], kr["ypos"], out["_edges"], a.fin_width, a.fin_drape)[0])
        pick_lab.append(f"Gitter+{len(out['_edges'])} Kanten-Lineale ({kr['nribs']}T)")
    tr = out.get("adaptiv+snap+Lineale+Tunnel", [])
    if tr:
        kt = next((r for r in tr if r["n"] == kg["n"]), tr[-1])
        picks.append(kt)
        pick_rec.append(reconstruct_rulers(Hf, cell, kt["xpos"], kt["ypos"], out["_edges"] + out["_tseg"], a.fin_width, a.fin_drape)[0])
        pick_lab.append(f"+Tunnel-Finne (Portal {kt['portal_max_mm']:.2f}mm)")
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
    # Trasse als 3D-Linie (Tunnel/offen) — IMMER sichtbar, zeigt wo das Portal sitzt
    track = out.get("_track", []); ntr = 0
    if track:
        P = np.array([(p[0], p[1], p[2], float(p[3])) for p in track]); zc = bilin(Hf, P[:, 0], P[:, 1], cell) + 2
        seg = [("Tunnel", P[:, 3] > 0.5, "#1f77ff"), ("offen", P[:, 3] <= 0.5, "#ffffff")]
        for nm, mk, c in seg:
            if mk.any():
                fig.add_scatter3d(x=P[mk, 0], y=P[mk, 1], z=zc[mk], mode="markers",
                                  marker=dict(size=3, color=c), name=f"Trasse {nm}"); ntr += 1
        for b in buttons: b["args"][0]["visible"] += [True] * ntr   # Trasse in jedem Modus sichtbar
    fig.update_layout(title="Egg-Crate Relief-Rekonstruktion — echt / Rekonstruktion / Fehler (Trasse: blau=Tunnel, weiß=offen)",
                      updatemenus=[dict(buttons=buttons, x=0.0, y=1.0, xanchor="left")],
                      scene=dict(aspectmode="data", zaxis=dict(title="Höhe (mm)")), height=820)
    fig.write_html(f"{a.out}/sim3d.html", include_plotlyjs="cdn")

def plot_tunnel(Hf, cell, out, a):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    track = out.get("_track", [])
    if not track: return
    T = np.array([(p[0], p[1]) for p in track]); it = np.array([bool(p[3]) for p in track])
    NY, NX = Hf.shape; X = (np.arange(NX) + 0.5) * cell; Y = (np.arange(NY) + 0.5) * cell
    mx0, mx1 = max(0, T[:, 0].min() - 10), min(NX * cell, T[:, 0].max() + 10)
    my0, my1 = max(0, T[:, 1].min() - 10), min(NY * cell, T[:, 1].max() + 10)
    g = out.get("adaptiv+snap", []); kg = knee(g)
    recg, _ = reconstruct(Hf, cell, kg["xpos"], kg["ypos"])
    panels = [("ECHTES Gelände (Höhe)", Hf, "h"),
              (f"Gitter {kg['nribs']}T · TunMAX {kg['tun_max_mm']:.2f}mm", np.abs(recg - Hf), "e")]
    tunk = out.get("adaptiv+snap+Lineale+Tunnel", [])
    if tunk:
        kt = next((r for r in tunk if r["n"] == kg["n"]), tunk[-1])
        rect, _ = reconstruct_rulers(Hf, cell, kt["xpos"], kt["ypos"], out["_edges"] + out["_tseg"], a.fin_width, a.fin_drape)
        panels.append((f"+Tunnel-Lineale · TunMAX {kt['tun_max_mm']:.2f}mm", np.abs(rect - Hf), "e"))
    fig, axs = plt.subplots(1, len(panels), figsize=(6 * len(panels), 6))
    for ax, (title, Z, kind) in zip(axs, panels):
        if kind == "e":
            im = ax.pcolormesh(X, Y, Z, cmap="hot", vmin=0, vmax=max(1.0, a.target_mm * 4), shading="auto")
            plt.colorbar(im, ax=ax, label="|Fehler| mm", fraction=.046)
        else:
            im = ax.pcolormesh(X, Y, Z, cmap="terrain", shading="auto")
            plt.colorbar(im, ax=ax, label="Höhe mm", fraction=.046)
        ax.plot(T[:, 0], T[:, 1], "c-", lw=1.2, alpha=.7)
        if it.any(): ax.plot(T[it, 0], T[it, 1], "b.", ms=6, label="Tunnel")
        if (~it).any(): ax.plot(T[~it, 0], T[~it, 1], "w.", ms=5, label="offen")
        ax.set_xlim(mx0, mx1); ax.set_ylim(my0, my1); ax.set_aspect("equal"); ax.set_title(title, fontsize=10)
    axs[0].legend(fontsize=8, loc="upper right")
    plt.suptitle(f"Tunnel-Zoom — Ziel ≤ {a.target_mm} mm an den Tunnel-Kanten", y=1.02)
    plt.tight_layout(); plt.savefig(f"{a.out}/tunnel.png", dpi=120, bbox_inches="tight"); plt.close()

def write_ribs_edges_html(Hf, cell, out, a):
    """3D: Relief + GITTER-Rippen (X/Y) + ALLE erkannten scharfen Kanten als Kanten-Lineale
    (auf dem Relief liegend). Zeigt: jede relevante Kante ist durch eine Rippe ODER ein
    Lineal abgedeckt. + Trasse (Tunnel/offen)."""
    import plotly.graph_objects as go
    g = out.get("adaptiv+snap", []); kg = knee(g) if g else None
    if not kg: return
    xpos, ypos = kg["xpos"], kg["ypos"]; edges = out.get("_edges", [])
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell; st = max(1, max(NX, NY) // 120)
    X = np.arange(0, NX, st) * cell; Y = np.arange(0, NY, st) * cell
    fig = go.Figure()
    fig.add_surface(x=X, y=Y, z=Hf[::st, ::st], colorscale="earth", opacity=0.55, showscale=False, name="Relief")
    def drape(xs, ys):                                   # z = Relief entlang der Linie (+1mm sichtbar)
        return bilin(Hf, np.asarray(xs), np.asarray(ys), cell) + 1.0
    sy = np.linspace(0, Dy, 80); sx = np.linspace(0, Wx, 80)
    for i, xr in enumerate(xpos):                        # Y-Rippen (x=const, laufen in y) — grün
        yy = np.full_like(sy, xr)
        fig.add_scatter3d(x=yy, y=sy, z=drape(yy, sy), mode="lines", line=dict(color="#2ca02c", width=4),
                          name="Y-Rippen", legendgroup="Y", showlegend=(i == 0))
    for i, yr in enumerate(ypos):                        # X-Rippen (y=const, laufen in x) — blau
        xx = np.full_like(sx, yr)
        fig.add_scatter3d(x=sx, y=xx, z=drape(sx, xx), mode="lines", line=dict(color="#1f77b4", width=4),
                          name="X-Rippen", legendgroup="X", showlegend=(i == 0))
    for i, (x0, y0, x1, y1) in enumerate(edges):         # Kanten-Lineale auf scharfen Kanten — ROT, dick
        tx = np.linspace(x0, x1, 12); ty = np.linspace(y0, y1, 12)
        fig.add_scatter3d(x=tx, y=ty, z=drape(tx, ty), mode="lines", line=dict(color="#d62728", width=7),
                          name=f"Kanten-Lineale ({len(edges)})", legendgroup="K", showlegend=(i == 0))
    track = out.get("_track", [])
    if track:
        P = np.array([(p[0], p[1], float(p[3])) for p in track]); zc = drape(P[:, 0], P[:, 1]) + 1
        for nm, mk, c in [("Tunnel", P[:, 2] > 0.5, "#111"), ("offen", P[:, 2] <= 0.5, "#ffffff")]:
            if mk.any():
                fig.add_scatter3d(x=P[mk, 0], y=P[mk, 1], z=zc[mk], mode="markers",
                                  marker=dict(size=3, color=c), name=f"Trasse {nm}")
    fig.update_layout(title=f"Alle relevanten Kanten abgedeckt — {len(ypos)} X + {len(xpos)} Y-Rippen "
                            f"(blau/grün) + {len(edges)} Kanten-Lineale (rot)",
                      scene=dict(aspectmode="data", zaxis=dict(title="Höhe (mm)")), height=840)
    fig.write_html(f"{a.out}/ribs_edges.html", include_plotlyjs="cdn")

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
    ap.add_argument("--fin-width", type=float, default=3.0, dest="fin_width", help="Finnen-Dicke (mm): Breite des Streifens, auf dem die Haut EXAKT dem Gelände folgt (= Material-Dicke des Kanten-Lineals)")
    ap.add_argument("--fin-drape", type=float, default=0.0, dest="fin_drape", help="einseitige Drapierung (mm) auf der tieferen Seite der Finne; 0 = reine exakte Kante")
    ap.add_argument("--track", default="daten/hoellental/hoellental_track_50.npy", help="Trasse (.npy mx,my,mz,is_tunnel in Modell-mm) für die Tunnel-Genauigkeits-Analyse; leer=aus")
    ap.add_argument("--corridor", type=float, default=3.0, help="Tunnel-Korridor-Breite (mm) für die Fehler-Messung an den Tunnel-Kanten")
    ap.add_argument("--target-mm", type=float, default=0.5, dest="target_mm", help="Genauigkeits-Ziel an den Tunnel-Kanten (mm Modell)")
    ap.add_argument("--out", default="/tmp/eggcrate_sim")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    Hf, cell = build_Hf(a)
    NY, NX = Hf.shape
    print(f"DEM-Fenster {NX}x{NY} Zellen, {NX*cell:.0f}x{NY*cell:.0f} mm, Höhe {Hf.min():.0f}..{Hf.max():.0f} mm")
    print(f"Relief-Spannweite real: {(Hf.max()-Hf.min())/(a.nscale*a.vscale):.0f} m\n")
    out = run_sweep(Hf, cell, a)
    has_tun = bool(out.get("_track"))
    hdr = f"{'Strategie':28s} {'n':>3} {'#Teile':>6} {'Schnitt m':>9} {'RMS m':>7} {'max m':>7}"
    if has_tun: hdr += f" | {'TunRMS':>7} {'TunMAX':>7} {'Portal':>7} (mm)"
    print(hdr)
    for name, rows in _strat_rows(out):
        for r in rows:
            line = (f"{name:28s} {r['n']:>3} {r['nribs']:>6} {r['cut']/1000:>9.1f} "
                    f"{r['rms_m']:>7.2f} {r['max_m']:>7.2f}")
            if has_tun:
                ok = "✓" if r['tun_max_mm'] <= a.target_mm else " "
                line += f" | {r['tun_rms_mm']:>7.2f} {r['tun_max_mm']:>7.2f}{ok} {r['portal_max_mm']:>6.2f}"
            print(line)
        print()
    kn = knee(out.get("adaptiv+snap", []))
    if kn:
        print(f"★ SWEET-SPOT Gitter (adaptiv+snap, Knie): {kn['nribs']} Teile, ~{kn['cut']/1000:.1f} m, "
              f"RMS {kn['rms_m']:.2f} m / max {kn['max_m']:.2f} m")
    if has_tun:
        print(f"\n== TUNNEL-GENAUIGKEIT (Ziel ≤ {a.target_mm} mm an den Tunnel-Kanten) ==")
        for name, rows in _strat_rows(out):
            hit = [r for r in rows if r['tun_max_mm'] <= a.target_mm]
            if hit:
                h = min(hit, key=lambda r: r['cut'])
                print(f"  {name:28s}: ERREICHT ab {h['nribs']} Teilen / ~{h['cut']/1000:.1f} m "
                      f"(TunMAX {h['tun_max_mm']:.2f} mm, Portal {h['portal_max_mm']:.2f} mm)")
            else:
                best = min(rows, key=lambda r: r['tun_max_mm'])
                print(f"  {name:28s}: NIE erreicht (bestes TunMAX {best['tun_max_mm']:.2f} mm bei {best['nribs']} Teilen)")
    plot_pareto(out, a); plot_surfaces3d(Hf, cell, out, a); write_html(Hf, cell, out, a)
    write_ribs_edges_html(Hf, cell, out, a)
    if has_tun: plot_tunnel(Hf, cell, out, a)
    print(f"\n-> {a.out}/pareto.png  {a.out}/surfaces3d.png  {a.out}/sim3d.html"
          + (f"  {a.out}/tunnel.png" if has_tun else ""))

if __name__ == "__main__":
    main()

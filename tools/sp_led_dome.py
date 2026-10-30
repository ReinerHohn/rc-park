#!/usr/bin/env python3
"""sp_led_dome.py — rüstet die Petersdom-KUPPEL (sp-dome.stl) für 0402-LEDs auf:

Reale Nacht-Beleuchtung nachgebaut:
  - RING aus 16 Uplightern am Balkon-Kranz (z≈55, r≈27), Lichtkegel nach OBEN,
    leicht nach INNEN zur Kuppel gekippt → streift die Rippen (wie echte Flutlichter).
  - 1 Uplighter an der Laterne.
  - Jede LED = rechteckiger 0402-Steckschlitz (nur 1.0x0.5-LED passt) + Mikro-
    Kabelkanal, der nach INNEN in den Hohlraum bricht (Druck mit 0% Infill = hohl).
  - Kabel-Austritt (Port) an der Basis.

Verifiziert per Raycast, dass hinter jedem Schlitz echtes Material sitzt.
"""
import sys, numpy as np, trimesh
sys.path.insert(0, "tools")
import light_prep as L

SRC = "modelle/3d_druck/sp-dome.stl"
OUT = "modelle/3d_druck/sp-dome-led.stl"
PNG = "modelle/stl/sp-dome-led_preview.png"

# 0.8-mm-Düse: Modell hochskalieren (bessere Details) + Schlitze 0.8-druckbar.
# LED vom User gemessen = 0805 (2.0x1.25 mm) → Schlitz auf 0805 + Klebespiel.
SCALE   = 1.6
SOCKET  = dict(body=[2.0, 1.25], tol=0.5, seat_depth=1.4, wire_d=1.6)  # Schlitz ~2.5x1.75

def main():
    m = trimesh.load(SRC, force="mesh")
    m.apply_scale(SCALE)
    S = SCALE
    cx, cy = m.vertices[:, 0].mean(), m.vertices[:, 1].mean()

    lights = []
    # --- Trommel-Ring: 16 Uplighter am Balkon-Kranz, strahlen die Rippen an -
    lights += L.ring_uplights(16, (cx, cy), 55.0*S, 26.5*S, tilt_in_deg=18.0,
                              wire_len=10.0*S, **SOCKET)
    # --- Laternen-KRONE (der hellste warme Punkt): Ring am Laternenfuß -----
    lights += L.ring_uplights(8, (cx, cy), 103.0*S, 11.0*S, tilt_in_deg=12.0,
                              wire_len=7.0*S, **SOCKET)
    # --- SPITZE / Finial: Uplighter am Laternenkopf, strahlt Kugel+Kreuz an -
    lights.append({"type": "led0402", "pos": [cx, cy + 3.0*S, 121.0*S],
                   "dir": [0, -0.25, 1.0], "wire_len": 7.0*S,
                   "wire_dir": [0, 0, -1], **SOCKET})
    # --- Kabel-Austritt (Port) an der Basis -------------------------------
    lights.append({"type": "port", "pos": [cx, cy, 41.2*S], "d": 4.0, "up": 6})

    # Raycast-Check: sitzt hinter jedem Schlitz Material? ------------------
    good = 0
    for Lt in lights:
        if Lt["type"] != "led0402":
            continue
        p = np.array(Lt["pos"], float)
        d = np.array(Lt["dir"], float); d /= np.linalg.norm(d)
        # Strahl von knapp vor dem Mund in die Tasche (−d): muss Mesh treffen
        hit = m.ray.intersects_any([p - d * 0.05], [-d])
        good += bool(hit[0])
    print(f"Sockets: {sum(1 for x in lights if x['type']=='led0402')}  "
          f"mit Material dahinter: {good}")

    out = L.prep(m, lights)
    out.export(OUT)
    print(f"watertight={out.is_watertight} faces={len(out.faces):,} "
          f"vol={out.volume/1000:.1f}cm3 -> {OUT}")

    # --- leichte Matplotlib-Vorschau (dezimiert) + Socket-Marker --------
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        tr_all = out.triangles
        step = max(1, len(tr_all) // 9000)       # ~9000 Dreiecke als Vorschau
        tr = tr_all[::step]
        fig = plt.figure(figsize=(7, 9)); ax = fig.add_subplot(111, projection="3d")
        pc = Poly3DCollection(tr, alpha=0.9, facecolor="#e8e0c8", edgecolor="none")
        ax.add_collection3d(pc)
        for Lt in lights:
            if Lt["type"] != "led0402":
                continue
            p = np.array(Lt["pos"]); d = np.array(Lt["dir"], float); d /= np.linalg.norm(d)
            ax.scatter(*p, c="red", s=14, depthshade=False)
            ax.quiver(*p, *(d * 8), color="orange", linewidth=1.1)
        b = out.bounds
        ax.set_xlim(b[0][0], b[1][0]); ax.set_ylim(b[0][1], b[1][1]); ax.set_zlim(b[0][2], b[1][2])
        ax.set_box_aspect((b[1]-b[0]))
        ax.view_init(elev=14, azim=-60); ax.axis("off")
        ax.set_title("sp-dome-led: 0402-Schlitze (rot) + Lichtrichtung (orange)")
        fig.tight_layout(); fig.savefig(PNG, dpi=110); print(f"preview -> {PNG}")
    except Exception as e:
        print("preview skipped:", e)

if __name__ == "__main__":
    main()

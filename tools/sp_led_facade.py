#!/usr/bin/env python3
"""sp_led_facade.py — rüstet die Petersdom-FASSADE (sp-facade.stl) für 0402-LEDs auf.

Reale Nacht-Beleuchtung (vgl. Miniatur-Wunderland): Fassade von unten kühl-weiß
geflutet, Attika-Krone (Statuen-Balustrade) mit angestrahlt.
  - SOCKEL-Reihe: Uplighter auf der Plinthe (z≈4.5), Lichtkegel nach OBEN,
    leicht nach HINTEN in die Fassade gekippt ("Richtung Petersdom rein").
  - KRONE: Uplighter-Reihe unter der Attika-Balustrade (z≈46).
  - Jeder = 0402-Steckschlitz + Mikro-Kabelkanal nach innen; Port an der Basis.
Front zeigt nach −Y. Raycast-geprüft, dass hinter jedem Schlitz Material sitzt.
"""
import sys, numpy as np, trimesh
sys.path.insert(0, "tools")
import light_prep as L

SRC = "modelle/3d_druck/sp-facade.stl"
OUT = "modelle/3d_druck/sp-facade-led.stl"
PNG = "modelle/stl/sp-facade-led_preview.png"

def row(xs, z, y, tilt_deg, wire_len):
    """Uplighter-Reihe: Licht hoch + nach hinten (+Y) in die Fassade gekippt."""
    t = np.radians(tilt_deg)
    d = [0, np.sin(t), np.cos(t)]          # hoch + in die Wand
    wdir = [0, 1.0, -0.6]                   # Kabel: in die Wand + runter → Hohlraum
    return [{"type": "led0402", "pos": [x, y, z], "dir": d, "wire_dir": wdir,
             "seat_depth": 0.7, "wire_d": 0.9, "wire_len": wire_len} for x in xs]

def snap_down(m, x, y, z_start):
    """Oberste waagrechte Fläche unter z_start bei (x,y) finden → Schlitz-Mund mit
    garantiertem Material darunter. Gibt z zurück oder None."""
    locs, _, _ = m.ray.intersects_location([[x, y, z_start]], [[0, 0, -1]])
    if len(locs) == 0:
        return None
    return float(locs[:, 2].max())

def snapped_row(m, xs, y, z_start, tilt_deg, wire_len):
    t = np.radians(tilt_deg)
    d = [0, np.sin(t), np.cos(t)]; wdir = [0, 1.0, -0.6]
    out = []
    for x in xs:
        z = snap_down(m, x, y, z_start)
        if z is None:
            continue
        out.append({"type": "led0402", "pos": [x, y, z], "dir": d, "wire_dir": wdir,
                    "seat_depth": 0.7, "wire_d": 0.9, "wire_len": wire_len})
    return out

def main():
    m = trimesh.load(SRC, force="mesh")
    x0, x1 = 78.0, 172.0
    base_xs  = list(np.linspace(x0, x1, 9))
    crown_xs = list(np.linspace(x0 + 6, x1 - 6, 7))

    # Mund auf echte Leisten snappen (Material garantiert darunter)
    lights  = snapped_row(m, base_xs,  y=95.0, z_start=10.0, tilt_deg=28.0, wire_len=12.0)
    lights += snapped_row(m, crown_xs, y=97.0, z_start=50.0, tilt_deg=22.0, wire_len=8.0)
    lights.append({"type": "port", "pos": [125.0, 110.0, 0.5], "d": 3.5, "up": 5})

    nled = sum(1 for x in lights if x["type"] == "led0402")
    print(f"Sockets gesnappt (mit Material darunter): {nled}")

    try:
        out = L.prep(m, lights)
        out.export(OUT)
        print(f"watertight={out.is_watertight} faces={len(out.faces):,} -> {OUT}")
    except Exception as e:
        out = m
        print(f"[!] Boolean übersprungen ({e}) — Fassaden-STL ist nicht watertight,"
              f" braucht erst Volumen-Reparatur. Vorschau zeigt die geplante Platzierung.")

    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        tr_all = out.triangles; step = max(1, len(tr_all) // 9000); tr = tr_all[::step]
        fig = plt.figure(figsize=(9, 6)); ax = fig.add_subplot(111, projection="3d")
        ax.add_collection3d(Poly3DCollection(tr, alpha=0.9, facecolor="#dfe6ef", edgecolor="none"))
        for Lt in lights:
            if Lt["type"] != "led0402":
                continue
            p = np.array(Lt["pos"]); d = np.array(Lt["dir"], float); d /= np.linalg.norm(d)
            ax.scatter(*p, c="red", s=16, depthshade=False)
            ax.quiver(*p, *(d * 8), color="orange", linewidth=1.1)
        b = out.bounds
        ax.set_xlim(b[0][0], b[1][0]); ax.set_ylim(b[0][1], b[1][1]); ax.set_zlim(b[0][2], b[1][2])
        ax.set_box_aspect((b[1]-b[0])); ax.view_init(elev=12, azim=-100); ax.axis("off")
        ax.set_title("sp-facade-led: 0402-Schlitze (rot) + Lichtrichtung (orange)")
        fig.tight_layout(); fig.savefig(PNG, dpi=110); print(f"preview -> {PNG}")
    except Exception as e:
        print("preview skipped:", e)

if __name__ == "__main__":
    main()

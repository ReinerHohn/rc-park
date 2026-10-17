#!/usr/bin/env python3
"""hoellental_prep.py — Spur-N-Demonstrator Höllental/Hirschsprung.

Echtes LGL-1m-Gelände (DGM1, Kachel 425/5306) → N-Maßstab (1:160) Geländeblock,
mit Gleis-Trasse entlang des Talbodens. Das NEM-102-N-Lichtraumprofil wird als
Freiraum-Kanal entlang der (sanft gegradeten) Trasse aus dem Gelände gefräst:
  - offenes Tal  → Einschnitt/Trog (Gleis liegt frei)
  - Felssporn darüber → automatisch TUNNEL (groß genug für normale N-Gleise)

NEM 102 Spur N (gerade): Breite 27 mm, Höhe 33 mm über SO. Hier großzügig
30 x 36 mm (Kurven-Überhang NEM 103 + Schotter/Druck-Toleranz).
"""
import numpy as np, trimesh

SCALE = 160.0                 # 1:160
MM = 1000.0 / SCALE           # 1 m real = 6.25 mm Modell
GRID = "daten/hoellental/grid2k.npy"
E0, N0 = 425000, 5306000
CORE_E = 425720               # Tunnel-Stelle (Felssporn, per Scan gefunden)

# Board-Zuschnitt (real, m): Länge entlang Tal (E) x quer (Süd..Nord um Talboden)
LEN_E   = 90                  # Länge entlang Tal → 562 mm
N_SOUTH = 12                  # m südlich des Talbodens
N_NORTH = 60                  # m nördlich (Hang hoch) → Board quer 72 m = 450 mm
BENCH_OFF = 34                # Gleis-Trasse so viele m den Nordhang hinauf (Hangbahn)

# NEM-N Lichtraum (Modell-mm, absolut – NICHT skaliert!)
CLEAR_W, CLEAR_H = 30.0, 36.0
RAIL_SINK = 6.0               # Trog reicht so weit unter SO (Schotterbett/Planum)

OUT = "modelle/stl/hoellental_n.stl"
PNG = "modelle/stl/hoellental_n_preview.png"

def main():
    g = np.load(GRID)                       # [N-row, E-col] m
    ec = CORE_E - E0
    floor_row = np.nanargmin(g, axis=0)
    fr_core = int(np.median(floor_row[ec-50:ec+50]))
    e0, e1 = ec - LEN_E // 2, ec + LEN_E // 2
    n0, n1 = fr_core - N_SOUTH, fr_core + N_NORTH
    win = g[n0:n1, e0:e1].astype(float)     # [ny, nx] m; Talboden ~ Zeile N_SOUTH
    ny, nx = win.shape
    zmin = np.nanmin(win)
    print(f"Fenster {nx}x{ny} m | Höhe {zmin:.0f}..{np.nanmax(win):.0f} m "
          f"Relief {np.nanmax(win)-zmin:.0f} m")

    # ---- Gelände-Heightfield → Modell-mm (x=E, y=N, z=Höhe) ----
    xs = np.arange(nx) * MM
    ys = np.arange(ny) * MM
    zz = (win - zmin) * MM                    # Basis auf 0
    terr = solidify(xs, ys, zz)
    print(f"Gelände: {len(terr.faces)} faces, Modell {nx*MM:.0f} x {ny*MM:.0f} x {zz.max():.0f} mm, "
          f"wt={terr.is_watertight} vol={terr.is_volume}")

    # ---- Trasse: HANGBAHN am Nordhang (echte Höllentalbahn fährt am Hang) ----
    floor_y = smooth(np.argmin(win, axis=0).astype(float), 9)    # Talboden-Zeile je E
    bench_y = np.clip(floor_y + BENCH_OFF, 0, ny-1)              # Trasse am Hang hinauf
    bench_terr = win[bench_y.round().astype(int), np.arange(nx)] # Hanghöhe entlang Trasse
    grade = np.linspace(bench_terr[0], bench_terr[-1], nx) - 1.5 # KONSTANTE Steigung → bohrt Sporn
    y_track = bench_y * MM
    z_track = (grade - zmin) * MM
    # Tunnel-Statistik
    clear_real = CLEAR_H / MM
    tun = int(np.sum(bench_terr > grade + clear_real))
    print(f"Hangtrasse: Offset {BENCH_OFF} m, Tunnel-Spalten {tun}/{nx} "
          f"(~{tun*MM:.0f} mm Tunnel gesamt)")

    # ---- Lichtraum-Kanal entlang der Trasse (echte Union) ----
    step = 3
    cutters = []
    for c in range(0, nx, step):
        x = xs[c]
        box = trimesh.creation.box(extents=[MM*step*1.6, CLEAR_W, CLEAR_H + RAIL_SINK])
        box.apply_translation([x, y_track[c], z_track[c] + (CLEAR_H - RAIL_SINK)/2])
        cutters.append(box)
    chan = trimesh.boolean.union(cutters)
    print(f"Lichtraum-Kanal: {CLEAR_W:.0f}x{CLEAR_H:.0f} mm, {len(cutters)} Segmente, "
          f"vol={chan.is_volume}")

    if not terr.is_volume:
        trimesh.repair.fill_holes(terr); trimesh.repair.fix_normals(terr)
        print(f"Gelände repariert, vol={terr.is_volume}")
    model = terr.difference(chan)
    model.export(OUT)
    print(f"-> {OUT}  faces={len(model.faces)} wt={model.is_watertight}")

    preview(model, xs, ys, y_track, z_track, nx)

def solidify(xs, ys, zz):
    """Heightfield → wasserdichter Block: volles Top- + Boden-Gitter + 4 Wände."""
    nx, ny = len(xs), len(ys)
    TX, TY = np.meshgrid(xs, ys)
    top = np.column_stack([TX.ravel(), TY.ravel(), zz.ravel()])
    bot = np.column_stack([TX.ravel(), TY.ravel(), np.zeros(nx*ny)])
    V = np.vstack([top, bot]); nt = nx*ny
    def t(r,c): return r*nx+c
    def b(r,c): return nt + r*nx+c
    F = []
    for r in range(ny-1):
        for c in range(nx-1):
            F += [[t(r,c),t(r+1,c),t(r+1,c+1)], [t(r,c),t(r+1,c+1),t(r,c+1)]]   # oben
            F += [[b(r,c),b(r+1,c+1),b(r+1,c)], [b(r,c),b(r,c+1),b(r+1,c+1)]]   # unten
    R = ny-1; C = nx-1
    for c in range(nx-1):
        F += [[t(0,c),t(0,c+1),b(0,c)], [t(0,c+1),b(0,c+1),b(0,c)]]             # Rand r=0
        F += [[t(R,c),b(R,c),t(R,c+1)], [t(R,c+1),b(R,c),b(R,c+1)]]             # Rand r=R
    for r in range(ny-1):
        F += [[t(r,0),b(r,0),t(r+1,0)], [t(r+1,0),b(r,0),b(r+1,0)]]            # Rand c=0
        F += [[t(r,C),t(r+1,C),b(r,C)], [t(r+1,C),b(r+1,C),b(r,C)]]            # Rand c=C
    m = trimesh.Trimesh(V, np.array(F), process=False)
    trimesh.repair.fix_normals(m)
    return m

def smooth(a, k):
    k=int(k)|1; pad=np.pad(a,k//2,mode='edge')
    return np.convolve(pad, np.ones(k)/k, mode='valid')

def preview(model, xs, ys, y_track, z_track, nx):
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        tr_all=model.triangles; step=max(1,len(tr_all)//12000); tr=tr_all[::step]
        fig=plt.figure(figsize=(10,6)); ax=fig.add_subplot(111,projection="3d")
        ax.add_collection3d(Poly3DCollection(tr,alpha=.9,facecolor="#b9a98a",edgecolor="none"))
        ax.plot(xs, y_track, z_track+2, color="red", lw=2, label="Gleis-Trasse")
        b=model.bounds
        ax.set_xlim(b[0][0],b[1][0]); ax.set_ylim(b[0][1],b[1][1]); ax.set_zlim(b[0][2],b[1][2])
        ax.set_box_aspect((b[1]-b[0])); ax.view_init(elev=22,azim=-70); ax.axis("off")
        ax.set_title("Höllental N (1:160) — rot = Gleis, Tunnel wo Fels drüber")
        fig.tight_layout(); fig.savefig(PNG,dpi=110); print(f"preview -> {PNG}")
    except Exception as e:
        print("preview skipped:", e)

if __name__=="__main__":
    main()

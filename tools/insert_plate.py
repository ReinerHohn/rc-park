#!/usr/bin/env python3
"""insert_plate.py — EBENE EINHÄNG-PLATTE für eine man-made Fläche (Einschnitt/Trog/
Portal-Deck/Stützwand), die das grobe Egg-Crate systematisch übertreppt.

Statt die Fläche über die treppige Rippen-Silhouette zu approximieren: eine ECHTE flache
Platte in der GEFITTETEN Ebene schneiden (true-shape, um die Neigung gestreckt), registriert
aufs Rippenraster (gravierte Kreuzungslinien + Dübel-Löcher an den X/Y-Kreuzungen) und mit
der pro-Rippe nötigen Oberkanten-Höhe, damit die Platten-Oberseite = die Ebene wird.

Gleiche Rippen-Quelle wie das Gerüst (terrain_eggcrate.rib_positions, inkl. --snap-edges),
damit Platte und Rippen exakt zusammenpassen.

  python3 tools/insert_plate.py --dem daten/hoellental/dgm025_full.npy \
      --r0 470 --r1 640 --c0 3310 --c1 3570 --zoom 1 --mm 1.5625 --nscale 6.25 \
      --vscale 0.85 --x0 218 --x1 329 --y0 113 --y1 212 --thickness 3 --snap-edges \
      --out /tmp/plate
"""
import argparse, os, sys, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter, zoom as ndzoom
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_eggcrate import rib_positions
from laser_relief_kit import glyph_strokes, svg_write, gcode_write


def load_hf(a):
    """Höhenfeld Hf (mm) + cell (mm/Zelle) wie terrain_eggcrate.main — EINE Quelle."""
    dem = np.load(a.dem)
    win = dem[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any():
        win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]                                           # +y = Nord (wie das Gerüst)
    zf = max(1, a.zoom)
    rel = gaussian_filter(ndzoom(win - win.min(), zf, order=1) if zf > 1 else (win - win.min()), a.smooth)
    cell = a.mm / zf
    Hf = rel * a.nscale * a.vscale + a.base
    return Hf, cell


def fit_plane(Hf, cell, x0, x1, y0, y1, iters=4, keep=0.6):
    """ROBUSTE Least-Squares-Ebene z = a*x + b*y + c über die Region (mm): fittet erst alle
    Zellen, trimmt dann iterativ die Ausreißer raus (behält die besten `keep`-Anteil nach
    Residuum) und refittet — so rastet die Ebene auf die DOMINANTE flache Fläche ein und
    ignoriert umgebenden Fels (sonst zieht der Fels die Ebene schief, RMS explodiert).
    Gibt a,b,c, RMS (nur Inlier) und Inlier-Anteil zurück."""
    NY, NX = Hf.shape
    ix0, ix1 = max(0, int(x0 / cell)), min(NX, int(round(x1 / cell)) + 1)
    iy0, iy1 = max(0, int(y0 / cell)), min(NY, int(round(y1 / cell)) + 1)
    xs = (np.arange(ix0, ix1) + 0.5) * cell
    ys = (np.arange(iy0, iy1) + 0.5) * cell
    XX, YY = np.meshgrid(xs, ys)
    z = Hf[iy0:iy1, ix0:ix1].ravel()
    A = np.column_stack([XX.ravel(), YY.ravel(), np.ones(XX.size)])
    coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    m = np.ones(z.size, bool)
    for _ in range(iters):
        res = np.abs(A @ coef - z)                           # Residuen auf ALLEN Zellen (nicht kompoundierend)
        thr = np.quantile(res, keep)
        m = res <= thr
        if m.sum() < 12: break
        coef, *_ = np.linalg.lstsq(A[m], z[m], rcond=None)
    res = np.abs(A @ coef - z)
    rms = float(np.sqrt(np.mean(res[m] ** 2))) if m.any() else float("nan")
    a, b, c = (float(v) for v in coef)
    return a, b, c, rms, float(m.mean())


def write_plate_html(fn, Hf, cell, region, plane, thickness, ds=3):
    """Drehbarer three.js-Viewer: Gelände-Fenster (halbtransparent) + die FLACHE Platte in
    der gefitteten Ebene (Holzfarbe, solide) — man sieht direkt, wie die Platte den treppigen
    Trog durch eine saubere Ebene ersetzt. Selbstständig (three.js via CDN, Daten eingebettet)."""
    x0, x1, y0, y1 = region; a, b, c = plane
    H = Hf[::ds, ::ds]; ny, nx = H.shape; cl = cell * ds
    zmin, zmax = float(Hf.min()), float(Hf.max()); zr = max(1e-6, zmax - zmin)
    verts, cols = [], []
    for j in range(ny):
        for i in range(nx):
            z = float(H[j, i]); verts += [round(i * cl, 1), round(z, 1), round(j * cl, 1)]
            t = (z - zmin) / zr; cols += [round(0.32 + 0.5 * t, 3), round(0.5 - 0.15 * t, 3), round(0.28, 3)]
    idx = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            p = j * nx + i; idx += [p, p + nx, p + 1, p + 1, p + nx, p + nx + 1]
    pz = lambda x, y: a * x + b * y + c
    plate = [[x0, pz(x0, y0), y0], [x1, pz(x1, y0), y0], [x1, pz(x1, y1), y1], [x0, pz(x0, y1), y1]]
    D = {"verts": verts, "cols": cols, "idx": idx, "plate": plate,
         "cx": round(nx * cl / 2, 1), "cz": round(ny * cl / 2, 1), "span": round(max(nx * cl, ny * cl), 1)}
    html = ('<!doctype html><html><head><meta charset=utf8><title>Einhäng-Platte 3D</title>'
            '<style>body{margin:0;background:#dde6ef;font-family:sans-serif}'
            '#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:8px 12px;border-radius:8px;font-size:13px}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<div id=i><b>Einhäng-Platte (Trog)</b><br><span style=color:#8cf>Maus drehen · Rad zoom</span><br>'
            'Gelände = halbtransparent · Holzfarbe = flache Platte in der Ebene</div>'
            '<script>'
            'const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xdde6ef);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;ct.target.set(D.cx,0,D.cz);'
            'cam.position.set(D.cx,D.span*0.9,D.cz+D.span*1.1);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.8));const dl=new THREE.DirectionalLight(0xffffff,1.1);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();'
            'tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setAttribute("color",new THREE.Float32BufferAttribute(D.cols,3));'
            'tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({vertexColors:true,transparent:true,opacity:0.5,side:THREE.DoubleSide,roughness:1})));'
            'const pv=[];D.plate.forEach(p=>pv.push(...p));const pg=new THREE.BufferGeometry();'
            'pg.setAttribute("position",new THREE.Float32BufferAttribute(pv,3));pg.setIndex([0,1,2,0,2,3]);pg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(pg,new THREE.MeshStandardMaterial({color:0xb5651d,side:THREE.DoubleSide,roughness:0.85})));'
            'const eg=new THREE.EdgesGeometry(pg);sc.add(new THREE.LineSegments(eg,new THREE.LineBasicMaterial({color:0x5a2d0c})));'
            'addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});'
            '(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();</script></body></html>')
    open(fn, "w").write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--zoom", type=int, default=1); ap.add_argument("--mm", type=float, default=1.5625)
    ap.add_argument("--nscale", type=float, default=6.25); ap.add_argument("--vscale", type=float, default=0.85)
    ap.add_argument("--base", type=float, default=12.0); ap.add_argument("--smooth", type=float, default=4.0)
    # Region der ebenen Fläche (mm). Default = Trog-Kandidat P1/P8 aus der Tunnel-Analyse.
    ap.add_argument("--x0", type=float, default=218); ap.add_argument("--x1", type=float, default=329)
    ap.add_argument("--y0", type=float, default=113); ap.add_argument("--y1", type=float, default=212)
    ap.add_argument("--thickness", type=float, default=3.0)
    ap.add_argument("--nx", type=int, default=6); ap.add_argument("--ny", type=int, default=6)
    ap.add_argument("--min-gap", type=float, default=7.0)
    ap.add_argument("--snap-edges", action="store_true", help="Rippenraster mit Bruchkanten-Snap (wie Gerüst)")
    ap.add_argument("--snap-pct", type=float, default=92.0)
    ap.add_argument("--dowel-d", type=float, default=3.2, help="Registrier-Dübel-Durchmesser mm (Löcher an X/Y-Kreuzungen)")
    ap.add_argument("--feed", type=float, default=150); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=85)
    ap.add_argument("--out", default="/tmp/plate")
    ap.add_argument("--gcode", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    Hf, cell = load_hf(a)
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell
    x0, x1 = min(a.x0, a.x1), max(a.x0, a.x1)
    y0, y1 = min(a.y0, a.y1), max(a.y0, a.y1)
    if not (0 <= x0 < x1 <= Wx and 0 <= y0 < y1 <= Dy):
        print(f"!! Region {x0:.0f}..{x1:.0f} x {y0:.0f}..{y1:.0f} mm liegt nicht im Fenster "
              f"0..{Wx:.0f} x 0..{Dy:.0f} mm — bitte --x0/x1/y0/y1 anpassen."); sys.exit(2)

    av, bv, cv, rms, infrac = fit_plane(Hf, cell, x0, x1, y0, y1)
    tilt = np.degrees(np.arctan(np.hypot(av, bv)))
    sx, sy = np.hypot(1.0, av), np.hypot(1.0, bv)             # true-shape-Streckung je Achse
    Lx, Ly = x1 - x0, y1 - y0
    Wp, Dp = Lx * sx, Ly * sy                                 # flache Platten-Maße (abgewickelt)

    # Rippenraster — DIESELBE Quelle wie das Gerüst (optional mit Snap), damit es passt.
    mg = None
    xpos, ypos = rib_positions(Hf, cell, a.nx, a.ny, a.min_gap, mg, False, a.snap_edges, a.snap_pct)
    xin = [xp for xp in xpos if x0 - 1e-6 <= xp <= x1 + 1e-6]
    yin = [yp for yp in ypos if y0 - 1e-6 <= yp <= y1 + 1e-6]
    PX = lambda xp: (xp - x0) * sx                            # Welt-mm -> Platten-mm (gestreckt)
    PY = lambda yp: (yp - y0) * sy

    # --- Laser-Geometrie ------------------------------------------------------
    plate = [(0, 0), (Wp, 0), (Wp, Dp), (0, Dp), (0, 0)]      # flache Platte (Rechteck, abgewickelt)
    cut_polys = [plate]
    engrave = []
    for xp in xin:                                            # Rippen-Kreuzungslinien gravieren (Ausrichthilfe)
        engrave.append([(PX(xp), 0), (PX(xp), Dp)])
    for yp in yin:
        engrave.append([(0, PY(yp)), (Wp, PY(yp))])
    engrave.append([(1.5, 1.5), (1.5, 6.5)])                 # kleiner Nord-Pfeil (Orientierung)
    engrave.append([(0.5, 5.5), (1.5, 6.5), (2.5, 5.5)])
    engrave += glyph_strokes("TROG", 4, Dp - 7, h=5)
    holes = [(PX(xp), PY(yp)) for xp in xin for yp in yin]    # Dübel-Löcher an X/Y-Kreuzungen

    base = os.path.join(a.out, "insert_trog")
    svg_write(base + ".svg", cut_polys, [], holes, engrave, a.dowel_d / 2)
    if a.gcode:
        gcode_write(base + ".gcode", cut_polys, [], holes, engrave, a.dowel_d / 2,
                    a.feed, a.power, a.passes, a.eng_power)

    # --- pro-Rippe nötige Oberkanten-Höhe (damit Platten-OBERSEITE = Ebene) ----
    # Rippe-Oberkante im Trog = Ebene(x,y) − Plattendicke. Als Tabelle (Integration ins
    # Gerüst = nächster Schritt; hier erstmal sichtbar ausgegeben + in die Manifest-Datei).
    def plane_z(xp, yp): return av * xp + bv * yp + cv
    man = [f"EINHÄNG-PLATTE (Trog/Einschnitt) — Region {x0:.0f}..{x1:.0f} x {y0:.0f}..{y1:.0f} mm",
           f"Ebene z = {av:+.4f}*x {bv:+.4f}*y {cv:+.2f}  |  Neigung {tilt:.1f}°  |  Fit-RMS {rms:.2f} mm "
           f"(robust, {infrac*100:.0f}% Inlier)",
           f"Platte (abgewickelt, flach): {Wp:.0f} x {Dp:.0f} mm, Dicke {a.thickness} mm",
           f"Registrierung: {len(holes)} Dübel-Löcher (Ø{a.dowel_d}) an {len(xin)} X- x {len(yin)} Y-Kreuzungen",
           "Rippen-OBERKANTE im Trog (= Ebene − Dicke), damit Platten-Oberseite = Ebene:"]
    for xp in xin:
        for yp in yin:
            man.append(f"  X={xp:6.1f}  Y={yp:6.1f}  ->  Rippe-Oberkante {plane_z(xp,yp)-a.thickness:6.1f} mm")
    open(base + "_manifest.txt", "w").write("\n".join(man) + "\n")

    # --- Vorschau -------------------------------------------------------------
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5))
    axA.imshow(Hf, origin="lower", extent=[0, Wx, 0, Dy], cmap="terrain", aspect="equal")
    axA.add_patch(plt.Rectangle((x0, y0), Lx, Ly, fill=False, ec="red", lw=2))
    for xp in xin: axA.plot([xp, xp], [y0, y1], color="k", lw=.6, alpha=.6)
    for yp in yin: axA.plot([x0, x1], [yp, yp], color="k", lw=.6, alpha=.6)
    axA.plot([xp for xp in xin for _ in yin], [yp for _ in xin for yp in yin], "wo", ms=4, mec="k")
    axA.set_title(f"Fenster — Trog-Region (rot), Neigung {tilt:.1f}°, RMS {rms:.2f} mm"); axA.set_xlabel("x [mm]")
    axB.add_patch(plt.Rectangle((0, 0), Wp, Dp, fill=False, ec="red", lw=2))
    for xp in xin: axB.plot([PX(xp), PX(xp)], [0, Dp], color="g", lw=.8)
    for yp in yin: axB.plot([0, Wp], [PY(yp), PY(yp)], color="g", lw=.8)
    for xp in xin:
        for yp in yin: axB.add_patch(plt.Circle((PX(xp), PY(yp)), a.dowel_d / 2, fill=False, ec="b"))
    axB.set_xlim(-6, Wp + 6); axB.set_ylim(-6, Dp + 6); axB.set_aspect("equal")
    axB.set_title(f"FLACHE PLATTE {Wp:.0f}x{Dp:.0f} mm (grün=Rippenlinien, blau=Dübel)"); axB.set_xlabel("mm")
    plt.tight_layout(); plt.savefig(base + "_preview.png", dpi=120)

    write_plate_html(base + "_3d.html", Hf, cell, (x0, x1, y0, y1), (av, bv, cv), a.thickness)

    print("\n".join(man))
    print(f"\n-> {base}.svg" + (f" + {base}.gcode" if a.gcode else "")
          + f"  |  Vorschau {base}_preview.png  |  3D-HTML {base}_3d.html")


if __name__ == "__main__":
    main()

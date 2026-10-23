#!/usr/bin/env python3
"""combined_view.py — KOMBINIERTE Vorschau: Rippen-Skelett + HAUT + Einhäng-Platte.

Zeigt, dass das grobe Egg-Crate NICHT das Endergebnis ist: die HAUT (durchgehende
Oberfläche über den Rippen-Oberkanten) deckt alle Lücken zwischen den Rippen UND bildet
das Tunnel-Dach (= Fels über der Röhre); die flache Einhäng-Platte kleidet die ebene
Man-made-Fläche (Trog) aus.

Erzeugt:
  * _combined.png  — 2 Panels: links Skelett (nackte Rippen), rechts fertig (Haut+Dach+Platte)
  * _combined.html — drehbarer three.js-Viewer (solide Haut + Rippen-Gitter + Platte)

  python3 tools/combined_view.py --snap-edges --x0 260 --x1 325 --y0 160 --y1 210 --out /tmp/combined
"""
import argparse, os, sys, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip
from terrain_eggcrate import rib_positions


def rib_strip(Hf, cell, const, axis):
    """Vertikale Rippen-Silhouette als geschlossenes Polygon (3D): Unterkante z=0, Oberkante
    folgt dem Gelände entlang der Rippe. axis='x' -> Rippe bei x=const läuft über y."""
    NY, NX = Hf.shape
    if axis == "x":
        js = np.arange(NY); ci = min(max(int(round(const / cell)), 0), NX - 1)
        ys = js * cell; ztop = Hf[js, ci]
        top = [(const, y, z) for y, z in zip(ys, ztop)]
        bot = [(const, y, 0.0) for y in ys[::-1]]
    else:
        ii = np.arange(NX); cj = min(max(int(round(const / cell)), 0), NY - 1)
        xs = ii * cell; ztop = Hf[cj, ii]
        top = [(x, const, z) for x, z in zip(xs, ztop)]
        bot = [(x, const, 0.0) for x in xs[::-1]]
    return top + bot


def write_combined_html(fn, Hf, cell, xpos, ypos, region, plane, ds=3):
    """three.js: solide HAUT (Gelände-Oberfläche) + Rippen-Gitter (dunkle Linien, drapiert)
    + flache Platte. Macht sichtbar, dass die Haut Lücken + Tunnel-Dach schließt."""
    x0, x1, y0, y1 = region; a, b, c = plane
    H = Hf[::ds, ::ds]; ny, nx = H.shape; cl = cell * ds
    zmin, zmax = float(Hf.min()), float(Hf.max()); zr = max(1e-6, zmax - zmin)
    verts, cols, idx = [], [], []
    for j in range(ny):
        for i in range(nx):
            z = float(H[j, i]); verts += [round(i * cl, 1), round(z, 1), round(j * cl, 1)]
            t = (z - zmin) / zr; cols += [round(0.30 + 0.55 * t, 3), round(0.52 - 0.17 * t, 3), 0.26]
    for j in range(ny - 1):
        for i in range(nx - 1):
            p = j * nx + i; idx += [p, p + nx, p + 1, p + 1, p + nx, p + nx + 1]
    NY, NX = Hf.shape
    riblines = []                                        # Rippen-Gitter auf die Haut drapiert
    for xp in xpos:
        ci = min(max(int(round(xp / cell)), 0), NX - 1)
        for j in range(0, NY - ds, ds):
            z0 = float(Hf[j, ci]); z1 = float(Hf[min(j + ds, NY - 1), ci])
            riblines += [round(xp, 1), z0 + 0.5, round(j * cell, 1),
                         round(xp, 1), z1 + 0.5, round(min(j + ds, NY - 1) * cell, 1)]
    for yp in ypos:
        cj = min(max(int(round(yp / cell)), 0), NY - 1)
        for i in range(0, NX - ds, ds):
            z0 = float(Hf[cj, i]); z1 = float(Hf[cj, min(i + ds, NX - 1)])
            riblines += [round(i * cell, 1), z0 + 0.5, round(yp, 1),
                         round(min(i + ds, NX - 1) * cell, 1), z1 + 0.5, round(yp, 1)]
    pz = lambda x, y: a * x + b * y + c
    plate = [[x0, pz(x0, y0), y0], [x1, pz(x1, y0), y0], [x1, pz(x1, y1), y1], [x0, pz(x0, y1), y1]]
    D = {"verts": verts, "cols": cols, "idx": idx, "ribs": riblines, "plate": plate,
         "cx": round(nx * cl / 2, 1), "cz": round(ny * cl / 2, 1), "span": round(max(nx * cl, ny * cl), 1)}
    html = ('<!doctype html><html><head><meta charset=utf8><title>A3 kombiniert 3D</title>'
            '<style>body{margin:0;background:#dde6ef;font-family:sans-serif}'
            '#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:8px 12px;border-radius:8px;font-size:13px}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<div id=i><b>A3 — fertig (Haut + Tunnel-Dach + Platte)</b><br>'
            '<span style=color:#8cf>Maus drehen · Rad zoom</span><br>'
            'Solide Fläche = HAUT (deckt Lücken + Tunnel-Dach) · dunkle Linien = Rippen darunter · Holz = Einhäng-Platte</div>'
            '<script>const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xdde6ef);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;ct.target.set(D.cx,0,D.cz);'
            'cam.position.set(D.cx,D.span*0.9,D.cz+D.span*1.15);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.8));const dl=new THREE.DirectionalLight(0xffffff,1.1);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();'
            'tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setAttribute("color",new THREE.Float32BufferAttribute(D.cols,3));'
            'tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({vertexColors:true,side:THREE.DoubleSide,roughness:1,flatShading:false})));'
            'const rg=new THREE.BufferGeometry();rg.setAttribute("position",new THREE.Float32BufferAttribute(D.ribs,3));'
            'sc.add(new THREE.LineSegments(rg,new THREE.LineBasicMaterial({color:0x222222,transparent:true,opacity:0.5})));'
            'const pv=[];D.plate.forEach(p=>pv.push(...p));const pg=new THREE.BufferGeometry();'
            'pg.setAttribute("position",new THREE.Float32BufferAttribute(pv,3));pg.setIndex([0,1,2,0,2,3]);pg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(pg,new THREE.MeshStandardMaterial({color:0xb5651d,side:THREE.DoubleSide,roughness:0.85})));'
            'sc.add(new THREE.LineSegments(new THREE.EdgesGeometry(pg),new THREE.LineBasicMaterial({color:0x5a2d0c})));'
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
    ap.add_argument("--nx", type=int, default=6); ap.add_argument("--ny", type=int, default=6)
    ap.add_argument("--min-gap", type=float, default=7.0)
    ap.add_argument("--snap-edges", action="store_true"); ap.add_argument("--snap-pct", type=float, default=92.0)
    ap.add_argument("--x0", type=float, default=260); ap.add_argument("--x1", type=float, default=325)
    ap.add_argument("--y0", type=float, default=160); ap.add_argument("--y1", type=float, default=210)
    ap.add_argument("--out", default="/tmp/combined")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    Hf, cell = ip.load_hf(a)
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell
    mg = a.min_gap
    xpos, ypos = rib_positions(Hf, cell, a.nx, a.ny, mg, None, False, a.snap_edges, a.snap_pct)
    x0, x1 = sorted((a.x0, a.x1)); y0, y1 = sorted((a.y0, a.y1))
    av, bv, cv, rms, infrac = ip.fit_plane(Hf, cell, x0, x1, y0, y1)
    pz = lambda x, y: av * x + bv * y + cv
    plate3d = [(x0, y0, pz(x0, y0)), (x1, y0, pz(x1, y0)), (x1, y1, pz(x1, y1)), (x0, y1, pz(x0, y1))]

    # ---- 2-Panel-Render: Skelett (nackte Rippen) vs. fertig (Haut + Dach + Platte) ----
    ds = 3; H = Hf[::ds, ::ds]; ny, nx = H.shape
    XX, YY = np.meshgrid(np.arange(nx) * cell * ds, np.arange(ny) * cell * ds)
    fig = plt.figure(figsize=(15, 6.2))
    axA = fig.add_subplot(1, 2, 1, projection="3d")
    strips = [rib_strip(Hf, cell, xp, "x") for xp in xpos] + [rib_strip(Hf, cell, yp, "y") for yp in ypos]
    axA.add_collection3d(Poly3DCollection(strips, facecolor="#c19a6b", edgecolor="#6b4f2a", linewidths=0.3, alpha=0.9))
    axA.set_xlim(0, Wx); axA.set_ylim(0, Dy); axA.set_zlim(0, Hf.max() * 1.05)
    axA.set_title("SKELETT — nur Rippen (grob, löchrig, Tunnel offen)\n= was du im Zusammenbau-Tool siehst")
    axB = fig.add_subplot(1, 2, 2, projection="3d")
    axB.plot_surface(XX, YY, H, cmap="terrain", alpha=0.97, linewidth=0, antialiased=True, rcount=70, ccount=100)
    axB.add_collection3d(Poly3DCollection([plate3d], facecolor="#b5651d", edgecolor="#5a2d0c", alpha=0.95, linewidths=2))
    axB.set_title(f"FERTIG — HAUT deckt Lücken + Tunnel-Dach\n+ Einhäng-Platte (RMS {rms:.1f} mm)")
    for ax in (axA, axB):
        ax.set_xlabel("x [mm]"); ax.set_ylabel("y [mm]"); ax.view_init(elev=34, azim=-58)
        ax.set_box_aspect((Wx, Dy, Hf.max() * 1.1))
    plt.tight_layout(); png = os.path.join(a.out, "_combined.png"); plt.savefig(png, dpi=120)

    html = os.path.join(a.out, "_combined.html")
    write_combined_html(html, Hf, cell, xpos, ypos, (x0, x1, y0, y1), (av, bv, cv))
    print(f"Fenster {Wx:.0f}x{Dy:.0f} mm | {len(xpos)} X- + {len(ypos)} Y-Rippen | Platte RMS {rms:.1f} mm")
    print(f"-> 2-Panel: {png}")
    print(f"-> 3D-HTML: {html}")


if __name__ == "__main__":
    main()

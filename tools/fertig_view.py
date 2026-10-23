#!/usr/bin/env python3
"""fertig_view.py — EIN interaktives 3D des FERTIGEN Modells: die HAUT in voller Detailtiefe
(solide = der sichtbare Berg) + die Einhäng-Platten farbig obenauf. KEINE nackten Rippen —
genau das, was am Ende dasteht. Erzeugt _fertig.html (drehbar) + _fertig.png.

  python3 tools/fertig_view.py --dem daten/hoellental/dgm025_full.npy --r0 470 --r1 640 \
      --c0 3310 --c1 3570 --zoom 1 --mm 0.78125 --nscale 3.125 --vscale 0.85 \
      --snap-edges --out modelle/hoellental_A3_set
"""
import argparse, os, sys, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip
import insert_plates_auto as ipa
from terrain_eggcrate import rib_positions


def detect_plates(Hf, cell, a):
    out = []
    for m in ipa.segment_planes(Hf, cell, 2.5, 12.0, a.min_area, 90.0)[:a.max_plates]:   # JEDE Facette (jeder Winkel)
        av, bv, cv, _rms = ipa.fit_plane_mask(Hf, cell, m)
        if _rms > 3.0:                                        # GENERELL: nur saubere planare Flächen, kein Berg-Rauschen
            continue
        w = ipa.mask_contour_mm(m, cell, 2.5)
        if w is None:
            continue
        out.append((w, (av, bv, cv)))
    return out


def write_html(fn, Hf, cell, plates, ds=2):
    NY, NX = Hf.shape
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
    pal = [[0.90, 0.30, 0.24], [0.26, 0.52, 0.80], [0.40, 0.65, 0.29], [0.85, 0.60, 0.13],
           [0.58, 0.40, 0.74], [0.34, 0.70, 0.73], [0.89, 0.47, 0.76], [0.74, 0.74, 0.13]]
    P = []
    for k, (w, (av, bv, cv)) in enumerate(plates):
        tri = []
        for i in range(1, len(w) - 1):                       # Fan-Triangulation der Kontur
            for q in (0, i, i + 1):
                x, y = float(w[q][0]), float(w[q][1]); tri += [x, av * x + bv * y + cv + 0.4, y]
        P.append({"v": [round(t, 1) for t in tri], "c": pal[k % len(pal)]})
    D = {"verts": verts, "cols": cols, "idx": idx, "plates": P,
         "cx": round(nx * cl / 2, 1), "cz": round(ny * cl / 2, 1), "span": round(max(nx * cl, ny * cl), 1)}
    html = ('<!doctype html><html><head><meta charset=utf8><title>Fertiges Modell 3D</title>'
            '<style>body{margin:0;background:#dde6ef;font-family:sans-serif}'
            '#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:8px 12px;border-radius:8px;font-size:13px}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<div id=i><b>FERTIGES Modell</b> — Haut (voller Detail) + Einhäng-Platten (farbig)<br>'
            '<span style=color:#8cf>Maus drehen · Rad zoom</span> · KEINE nackten Rippen</div>'
            '<script>const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xdde6ef);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;ct.target.set(D.cx,0,D.cz);'
            'cam.position.set(D.cx,D.span*0.85,D.cz+D.span*1.15);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.8));const dl=new THREE.DirectionalLight(0xffffff,1.1);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();'
            'tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setAttribute("color",new THREE.Float32BufferAttribute(D.cols,3));'
            'tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({vertexColors:true,side:THREE.DoubleSide,roughness:1})));'
            'D.plates.forEach(function(p){var g=new THREE.BufferGeometry();'
            'g.setAttribute("position",new THREE.Float32BufferAttribute(p.v,3));g.computeVertexNormals();'
            'sc.add(new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:new THREE.Color(p.c[0],p.c[1],p.c[2]),side:THREE.DoubleSide,roughness:0.7})));});'
            'addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});'
            '(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();</script></body></html>')
    open(fn, "w").write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--zoom", type=int, default=1); ap.add_argument("--mm", type=float, default=0.78125)
    ap.add_argument("--nscale", type=float, default=3.125); ap.add_argument("--vscale", type=float, default=0.85)
    ap.add_argument("--base", type=float, default=12.0); ap.add_argument("--smooth", type=float, default=0.4)
    ap.add_argument("--nx", type=int, default=6); ap.add_argument("--ny", type=int, default=6)
    ap.add_argument("--min-gap", type=float, default=7.0)
    ap.add_argument("--snap-edges", action="store_true"); ap.add_argument("--snap-pct", type=float, default=92.0)
    ap.add_argument("--slope-max", type=float, default=25.0); ap.add_argument("--min-area", type=float, default=300.0)
    ap.add_argument("--close-mm", type=float, default=2.5); ap.add_argument("--rib-miss", type=float, default=4.0)
    ap.add_argument("--max-plates", type=int, default=8)
    ap.add_argument("--out", default="/tmp/fertig")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    Hf, cell = ip.load_hf(a)
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell
    plates = detect_plates(Hf, cell, a)

    # PNG: solide Haut (volle Auflösung) + Platten-Konturen farbig obenauf
    X = np.arange(NX) * cell; Y = np.arange(NY) * cell; XX, YY = np.meshgrid(X, Y)
    fig = plt.figure(figsize=(13, 7)); ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(XX, YY, Hf, cmap="terrain", linewidth=0, antialiased=False, rcount=NY, ccount=NX)
    pal = plt.cm.tab10(np.linspace(0, 1, 10))
    polys = []
    for k, (w, (av, bv, cv)) in enumerate(plates):
        polys.append([(float(px), float(py), av * px + bv * py + cv + 0.6) for px, py in w])
    if polys:
        ax.add_collection3d(Poly3DCollection(polys, facecolors=pal[:len(polys)], edgecolor="k", linewidths=1.0, alpha=0.95))
    ax.view_init(elev=40, azim=-60); ax.set_box_aspect((Wx, Dy, Hf.max()))
    ax.set_title(f"FERTIGES Modell: Haut (voller Detail) + {len(plates)} Einhäng-Platten (farbig) — keine nackten Rippen")
    ax.set_xlabel("x[mm]"); ax.set_ylabel("y[mm]")
    plt.tight_layout(); png = os.path.join(a.out, "_fertig.png"); plt.savefig(png, dpi=120)

    html = os.path.join(a.out, "_fertig.html")
    write_html(html, Hf, cell, plates)
    print(f"FERTIG-Ansicht: Haut {Wx:.0f}x{Dy:.0f} mm + {len(plates)} Platten")
    print(f"-> {png}\n-> {html}")


if __name__ == "__main__":
    main()

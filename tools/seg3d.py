#!/usr/bin/env python3
"""seg3d.py — NUR der Tunnel-Einschnitt als Platten, sauber. Keine Facetten-Segmentierung.
Aus der erkannten Einschnitt-Kontur (grow-to-rim): DECKPLATTE = ebener Boden auf Gleis-Niveau,
SEITENPLATTEN = senkrechte Wände von der Gelände-Oberkante (Rim) runter zum Boden. Das sind die
Teile, die die groben Rippen NICHT können und die gecuttet + eingesetzt werden. Neutrales Gelände
als Kontext. Schreibt _seg3d.html (drehbar)."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip, insert_plates_auto as ipa


def main():
    class A: pass
    a = A(); a.dem = "daten/hoellental/dgm025_full.npy"; a.r0 = 470; a.r1 = 640; a.c0 = 3310; a.c1 = 3570
    a.zoom = 1; a.mm = 0.78125; a.nscale = 3.125; a.vscale = 0.85; a.base = 12.0; a.smooth = 0.4
    Hf, cell = ip.load_hf(a); NY, NX = Hf.shape
    tr = np.load("modelle/hoellental_A3_set/track50.npy").astype(float)
    poly = ipa.einschnitt_corridor_poly(Hf, cell, [list(p) for p in tr])

    # Boden-Ebene = best-fit durch die Trassen-Punkte (das Gleis-Niveau, FLACH)
    T = np.column_stack([tr[:, 0], tr[:, 1], np.ones(len(tr))])
    coef, *_ = np.linalg.lstsq(T, tr[:, 2], rcond=None)
    floor = lambda x, y: float(coef[0]*x + coef[1]*y + coef[2])
    zq = lambda x, y: float(Hf[min(int(y/cell), NY-1), min(int(x/cell), NX-1)])

    cx = NX*cell/2; cz = NY*cell/2; cy = (float(Hf.min())+float(Hf.max()))/2
    ctr = lambda x, y, z: [round(float(x)-cx, 1), round(float(z)-cy, 1), round(float(y)-cz, 1)]

    verts, idx = [], []
    for j in range(NY):
        for i in range(NX):
            verts += ctr(i*cell, j*cell, float(Hf[j, i]))
    for j in range(NY-1):
        for i in range(NX-1):
            p = j*NX+i; idx += [p, p+NX, p+1, p+1, p+NX, p+NX+1]

    floorV, wallV = [], []
    if poly is not None:
        P = poly[:, :2]
        # DECKPLATTE (Boden, flach auf Gleis-Niveau) — Fan-Triangulation
        for i in range(1, len(P)-1):
            for q in (0, i, i+1):
                x, y = P[q]; floorV += ctr(float(x), float(y), floor(x, y))
        # SEITENPLATTEN: senkrechte Wand von Rim (Gelände) runter zum Boden, je Kanten-Segment ein Quad
        for i in range(len(P)-1):
            x0, y0 = P[i]; x1, y1 = P[i+1]
            zt0, zt1 = zq(x0, y0), zq(x1, y1); zf0, zf1 = floor(x0, y0), floor(x1, y1)
            A0 = ctr(x0, y0, zt0); B0 = ctr(x1, y1, zt1); C0 = ctr(x1, y1, zf1); D0 = ctr(x0, y0, zf0)
            wallV += A0 + B0 + C0 + A0 + C0 + D0

    D = {"verts": verts, "idx": idx, "floor": floorV, "wall": wallV,
         "span": round(max(NX*cell, NY*cell), 1)}
    html = ('<!doctype html><html><head><meta charset=utf8><title>Einschnitt-Platten</title>'
            '<style>body{margin:0;background:#eef2f6;font-family:sans-serif}'
            '#i{position:fixed;top:8px;left:8px;background:#000b;color:#fff;padding:7px 11px;border-radius:7px;font-size:13px;line-height:1.5}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<div id=i><b>Tunnel-Einschnitt als Platten</b> (die Teile, die die Rippen nicht koennen)<br>'
            '<span style=color:#22c0ff>CYAN</span> = Deckplatte (Boden, flach) &nbsp; '
            '<span style=color:#ffb23a>ORANGE</span> = Seitenplatten (Waende) &middot; Maus dreht</div>'
            '<script>const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xeef2f6);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;ct.target.set(0,0,0);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.85));const dl=new THREE.DirectionalLight(0xffffff,0.7);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({color:0xccb089,roughness:1,side:THREE.DoubleSide,flatShading:true,transparent:true,opacity:0.55})));'
            'function solid(v,col){if(!v.length)return;const g=new THREE.BufferGeometry();'
            'g.setAttribute("position",new THREE.Float32BufferAttribute(v,3));g.computeVertexNormals();'
            'const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:col,side:THREE.DoubleSide,roughness:0.55,metalness:0.0}));m.renderOrder=5;sc.add(m);}'
            'solid(D.wall,0xffb23a);solid(D.floor,0x22c0ff);'
            'const d=D.span;cam.position.set(d*0.25,d*0.9,d*0.95);cam.lookAt(0,0,0);ct.update();'
            'addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});'
            '(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();</script></body></html>')
    out = "modelle/hoellental_A3_set/_seg3d.html"
    open(out, "w").write(html)
    print(f"Einschnitt: Deckplatte + {0 if poly is None else len(poly)-1} Wand-Segmente -> {out}")


if __name__ == "__main__":
    main()

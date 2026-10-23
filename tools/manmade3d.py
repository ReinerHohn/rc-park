#!/usr/bin/env python3
"""manmade3d.py — 3D: menschgemachte Objekte (scharfe Kanten + Flächen darin) auf neutralem Gelände.
Farbige ebene Platten = die erkannten Flächen (plan-gefittet), rote Linien = die geraden scharfen
Kanten. Kein Rippen-Rainbow, keine Facetten-Flut. Schreibt _manmade3d.html (drehbar)."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip
from manmade_edges import detect_manmade


def main():
    class A: pass
    a = A(); a.dem = "daten/hoellental/dgm025_full.npy"; a.r0 = 470; a.r1 = 640; a.c0 = 3310; a.c1 = 3570
    a.zoom = 1; a.mm = 0.78125; a.nscale = 3.125; a.vscale = 0.85; a.base = 12.0; a.smooth = 0.4
    Hf, cell = ip.load_hf(a); NY, NX = Hf.shape
    surf, edges, cell2 = detect_manmade(Hf, cell)

    cx = NX*cell/2; cz = NY*cell/2; cy = (float(Hf.min())+float(Hf.max()))/2
    ctr = lambda x, y, z: [round(float(x)-cx, 1), round(float(z)-cy, 1), round(float(y)-cz, 1)]
    zq = lambda x, y: float(Hf[min(int(y/cell), NY-1), min(int(x/cell), NX-1)])

    verts, idx = [], []
    for j in range(NY):
        for i in range(NX):
            verts += ctr(i*cell, j*cell, float(Hf[j, i]))
    for j in range(NY-1):
        for i in range(NX-1):
            p = j*NX+i; idx += [p, p+NX, p+1, p+1, p+NX, p+NX+1]

    FLAT = [0.26, 0.56, 0.86]      # blau = flache Fläche
    STEEP = [0.95, 0.45, 0.12]     # orange = steile/senkrechte Fläche (Wand)
    nflat = nsteep = 0
    P = []
    for k, (poly, (av, bv, cvv), rms, pslope) in enumerate(surf):
        col = STEEP if pslope >= 45.0 else FLAT
        nsteep += pslope >= 45.0; nflat += pslope < 45.0
        # ECHTE Geländehöhe (drapen) statt extrapolierter Ebene -> kein Überschießen an Steilwänden
        tri = []
        for i in range(1, len(poly)-1):
            for q in (0, i, i+1):
                x, y = float(poly[q][0]), float(poly[q][1]); tri += ctr(x, y, zq(x, y)+0.6)
        ed = []
        for i in range(len(poly)):
            x, y = poly[i]; ed += ctr(float(x), float(y), zq(x, y)+0.8)
            xn, yn = poly[(i+1) % len(poly)]; ed += ctr(float(xn), float(yn), zq(xn, yn)+0.8)
        P.append({"v": tri, "e": ed, "c": col})

    E = []
    for x0, y0, x1, y1 in edges:
        E += ctr(x0, y0, zq(x0, y0)+1.5) + ctr(x1, y1, zq(x1, y1)+1.5)

    D = {"verts": verts, "idx": idx, "plates": P, "edges": E,
         "span": round(max(NX*cell, NY*cell), 1), "ns": len(surf), "ne": len(edges)}
    html = ('<!doctype html><html><head><meta charset=utf8><title>Menschgemachte Objekte 3D</title>'
            '<style>body{margin:0;background:#eef2f6;font-family:sans-serif}'
            '#i{position:fixed;top:8px;left:8px;background:#000b;color:#fff;padding:7px 11px;border-radius:7px;font-size:13px}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<div id=i><b>Menschgemachte Objekte</b> &mdash; <span style=color:#4a90e0>blau</span> = flache, '
            '<span style=color:#f27420>orange</span> = steile/senkrechte Flaechen ('+str(nflat)+' flach / '+str(nsteep)+' steil), '
            '<span style=color:#ff3b3b>rot</span> = scharfe Kanten ('+str(len(edges))+') &middot; Maus dreht</div>'
            '<script>const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xeef2f6);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;ct.target.set(0,0,0);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.9));const dl=new THREE.DirectionalLight(0xffffff,0.6);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({color:0xccb089,roughness:1,side:THREE.DoubleSide,flatShading:true})));'
            'D.plates.forEach(function(p){const g=new THREE.BufferGeometry();'
            'g.setAttribute("position",new THREE.Float32BufferAttribute(p.v,3));g.computeVertexNormals();'
            'const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:new THREE.Color(p.c[0],p.c[1],p.c[2]),side:THREE.DoubleSide,roughness:0.55}));m.renderOrder=5;sc.add(m);'
            'const eg=new THREE.BufferGeometry();eg.setAttribute("position",new THREE.Float32BufferAttribute(p.e,3));'
            'sc.add(new THREE.LineSegments(eg,new THREE.LineBasicMaterial({color:0x101014})));});'
            'if(D.edges.length){const xg=new THREE.BufferGeometry();xg.setAttribute("position",new THREE.Float32BufferAttribute(D.edges,3));'
            'const xl=new THREE.LineSegments(xg,new THREE.LineBasicMaterial({color:0xff3b3b,depthTest:false}));xl.renderOrder=20;sc.add(xl);}'
            'const d=D.span;cam.position.set(d*0.2,d*1.0,d*0.95);cam.lookAt(0,0,0);ct.update();'
            'addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});'
            '(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();</script></body></html>')
    out = "modelle/hoellental_A3_set/_manmade3d.html"
    open(out, "w").write(html)
    print(f"{len(surf)} Flaechen + {len(edges)} scharfe Kanten -> {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""seg3d.py — 3D der Felzenszwalb-FLÄCHEN auf dem Gelände: jede planare Fläche eigene Farbe
(nach Orientierung), die Ränder (approximate_polygon) als dunkle Kanten-Tubes = saubere Geo-Kanten.
Schreibt _seg3d.html (three.js UMD, drehbar)."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip
from plane_segment import segment_facets, facet_polys
from skimage.measure import regionprops


def main():
    class A: pass
    a = A(); a.dem = "daten/hoellental/dgm025_full.npy"; a.r0 = 470; a.r1 = 640; a.c0 = 3310; a.c1 = 3570
    a.zoom = 1; a.mm = 0.78125; a.nscale = 3.125; a.vscale = 0.85; a.base = 12.0; a.smooth = 0.4
    Hf, cell = ip.load_hf(a); NY, NX = Hf.shape

    lab, n = segment_facets(Hf, cell, scale=140.0, sigma=0.6, min_size=90, smooth=1.5)
    polys = facet_polys(lab, cell, min_area_mm2=150.0, rdp_mm=3.0)

    # Farbe je Fläche = mittlere Normalen-Orientierung (wie im 2D-Bild)
    rgb01 = (n * 0.5 + 0.5)
    facecol = {}
    for r in regionprops(lab + 1):
        facecol[r.label - 1] = rgb01[r.slice][r.image].mean(0) if r.image.any() else np.array([.5, .5, .5])

    cx = NX*cell/2; cz = NY*cell/2; cy = (float(Hf.min())+float(Hf.max()))/2
    verts, cols, idx = [], [], []
    for j in range(NY):
        for i in range(NX):
            verts += [round(i*cell-cx, 1), round(float(Hf[j, i])-cy, 1), round(j*cell-cz, 1)]
            c = facecol.get(int(lab[j, i]), np.array([.5, .5, .5]))
            cols += [round(float(c[0]), 3), round(float(c[1]), 3), round(float(c[2]), 3)]
    for j in range(NY-1):
        for i in range(NX-1):
            p = j*NX+i; idx += [p, p+NX, p+1, p+1, p+NX, p+NX+1]

    zq = lambda x, y: float(Hf[min(int(y/cell), NY-1), min(int(x/cell), NX-1)])
    edges = []
    for p in polys:
        line = []
        for x, y in p:
            line += [round(float(x)-cx, 1), round(zq(x, y)+2.5-cy, 1), round(float(y)-cz, 1)]
        edges.append(line)

    D = {"verts": verts, "cols": cols, "idx": idx, "edges": edges,
         "span": round(max(NX*cell, NY*cell), 1), "nf": len(polys)}
    html = ('<!doctype html><html><head><meta charset=utf8><title>Flaechen-Segmentierung 3D</title>'
            '<style>body{margin:0;background:#eef2f6;font-family:sans-serif}'
            '#i{position:fixed;top:8px;left:8px;background:#000b;color:#fff;padding:7px 11px;border-radius:7px;font-size:13px}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<div id=i><b>Planare Flaechen (Felzenszwalb) + Geo-Kanten</b><br>'
            'Farbe = Flaechen-Orientierung &middot; schwarze Linien = saubere Kanten &middot; Maus dreht, Rad zoomt</div>'
            '<script>const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xeef2f6);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;ct.target.set(0,0,0);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.95));const dl=new THREE.DirectionalLight(0xffffff,0.5);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setAttribute("color",new THREE.Float32BufferAttribute(D.cols,3));tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({vertexColors:true,roughness:1,side:THREE.DoubleSide,flatShading:true})));'
            'function tube(flat,col,rad){const P=[];for(let i=0;i<flat.length;i+=3)P.push(new THREE.Vector3(flat[i],flat[i+1],flat[i+2]));'
            'if(P.length<2)return;const cv=new THREE.CatmullRomCurve3(P,true);'
            'const g=new THREE.TubeGeometry(cv,P.length*3,rad,6,true);'
            'sc.add(new THREE.Mesh(g,new THREE.MeshBasicMaterial({color:col})));}'
            'D.edges.forEach(function(e){tube(e,0x101018,0.9);});'
            'const d=D.span;cam.position.set(d*0.3,d*1.0,d*0.95);cam.lookAt(0,0,0);ct.update();'
            'addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});'
            '(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();</script></body></html>')
    out = "modelle/hoellental_A3_set/_seg3d.html"
    open(out, "w").write(html)
    print(f"{len(polys)} Flaechen -> {out}")


if __name__ == "__main__":
    main()

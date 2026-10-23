#!/usr/bin/env python3
"""goal_overlay.py — minimale 3D-Ansicht WIE goal.png: tan Gelände + AUTOMATISCH erkannte
Einschnitt-Kontur als ROTE Linie, drapiert. Beweis, dass die Erkennung die markierten Kanten trifft.
Schreibt /tmp/goal_overlay.html (three.js UMD)."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip, insert_plates_auto as ipa


def main():
    class A: pass
    a = A(); a.dem = "daten/hoellental/dgm025_full.npy"; a.r0 = 470; a.r1 = 640; a.c0 = 3310; a.c1 = 3570
    a.zoom = 1; a.mm = 0.78125; a.nscale = 3.125; a.vscale = 0.85; a.base = 12.0; a.smooth = 0.4
    Hf, cell = ip.load_hf(a); NY, NX = Hf.shape
    tr = np.load("modelle/hoellental_A3_set/track50.npy").astype(float); track = [list(p) for p in tr]
    poly = ipa.einschnitt_corridor_poly(Hf, cell, track)

    ds = 1
    H = Hf[::ds, ::ds]; ny, nx = H.shape; cl = cell * ds
    cx = nx*cl/2; cz = ny*cl/2; cy = (float(Hf.min())+float(Hf.max()))/2   # Geometrie zentrieren
    verts, idx = [], []
    for j in range(ny):
        for i in range(nx):
            verts += [round(i*cl-cx, 1), round(float(H[j, i])-cy, 1), round(j*cl-cz, 1)]
    for j in range(ny-1):
        for i in range(nx-1):
            p = j*nx+i; idx += [p, p+nx, p+1, p+1, p+nx, p+nx+1]
    zq = lambda x, y: float(Hf[min(int(y/cell), NY-1), min(int(x/cell), NX-1)])
    line = []
    for x, y in poly[:, :2]:
        line += [round(float(x)-cx, 1), round(zq(x, y)+3-cy, 1), round(float(y)-cz, 1)]
    D = {"verts": verts, "idx": idx, "line": line, "span": round(max(nx*cl, ny*cl), 1)}
    html = ('<!doctype html><html><head><meta charset=utf8><style>body{margin:0;background:#eef2f6}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<script>const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xeef2f6);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.target.set(0,0,0);'
            'cam.position.set(0,D.span*0.75,D.span*1.05);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.75));const dl=new THREE.DirectionalLight(0xffffff,1.0);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({color:0xcDae86,roughness:1,side:THREE.DoubleSide,flatShading:true})));'
            'const lg=new THREE.BufferGeometry();lg.setAttribute("position",new THREE.Float32BufferAttribute(D.line,3));'
            'const lo=new THREE.Line(lg,new THREE.LineBasicMaterial({color:0xff1111}));lo.renderOrder=999;sc.add(lo);'
            'cam.lookAt(0,0,0);ct.update();'
            '(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();</script></body></html>')
    open("/tmp/goal_overlay.html", "w").write(html)
    print(f"poly_pts {len(poly)} -> /tmp/goal_overlay.html")


if __name__ == "__main__":
    main()

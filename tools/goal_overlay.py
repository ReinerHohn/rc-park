#!/usr/bin/env python3
"""goal_overlay.py — saubere 3D-Ansicht: tan Gelände + ALLE automatisch erkannten Kanten obenauf:
ROT = Einschnitt-Rimse (grow-to-rim, kurvenfolgend), CYAN = die Deckplatte (drapiert),
BLAU = LSD-Geraden (menschgemachte gerade Kanten). Beweis, dass die Erkennung die markierten
Kanten trifft. Schreibt _goal_overlay.html (three.js UMD, drehbar)."""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip, insert_plates_auto as ipa
import lsd_edges


def main():
    class A: pass
    a = A(); a.dem = "daten/hoellental/dgm025_full.npy"; a.r0 = 470; a.r1 = 640; a.c0 = 3310; a.c1 = 3570
    a.zoom = 1; a.mm = 0.78125; a.nscale = 3.125; a.vscale = 0.85; a.base = 12.0; a.smooth = 0.4
    Hf, cell = ip.load_hf(a); NY, NX = Hf.shape
    tr = np.load("modelle/hoellental_A3_set/track50.npy").astype(float); track = [list(p) for p in tr]
    poly = ipa.einschnitt_corridor_poly(Hf, cell, track)
    segs = lsd_edges.detect_straight_edges(Hf, cell, min_len_mm=22.0)

    cx = NX*cell/2; cz = NY*cell/2; cy = (float(Hf.min())+float(Hf.max()))/2
    zq = lambda x, y: float(Hf[min(int(y/cell), NY-1), min(int(x/cell), NX-1)])
    C = lambda x, y, dz=3.0: [round(float(x)-cx, 1), round(zq(x, y)+dz-cy, 1), round(float(y)-cz, 1)]

    verts, idx = [], []
    for j in range(NY):
        for i in range(NX):
            verts += [round(i*cell-cx, 1), round(float(Hf[j, i])-cy, 1), round(j*cell-cz, 1)]
    for j in range(NY-1):
        for i in range(NX-1):
            p = j*NX+i; idx += [p, p+NX, p+1, p+1, p+NX, p+NX+1]

    rim = []
    for x, y in poly[:, :2]:
        rim += C(x, y, 3.0)
    # Platte als Grid-Clip-Drape (cyan)
    from matplotlib.path import Path as _MP
    gx, gy = np.meshgrid(np.arange(NX)*cell, np.arange(NY)*cell)
    inside = _MP(poly[:, :2]).contains_points(np.column_stack([gx.ravel(), gy.ravel()])).reshape(NY, NX)
    pv = []; pf = []; pidx = -np.ones((NY, NX), int)
    for j in range(NY):
        for i in range(NX):
            if inside[j, i]:
                pidx[j, i] = len(pv)//3; pv += [round(i*cell-cx, 1), round(float(Hf[j, i])+1.5-cy, 1), round(j*cell-cz, 1)]
    for j in range(NY-1):
        for i in range(NX-1):
            A0, B0, C0, D0 = pidx[j, i], pidx[j, i+1], pidx[j+1, i], pidx[j+1, i+1]
            if min(A0, B0, C0, D0) >= 0:
                pf += [int(A0), int(C0), int(B0), int(B0), int(C0), int(D0)]
    lsdlines = []
    for x0, y0, x1, y1 in segs:
        lsdlines += C(x0, y0, 4.0) + C(x1, y1, 4.0)

    D = {"verts": verts, "idx": idx, "rim": rim, "pv": pv, "pf": pf, "lsd": lsdlines,
         "span": round(max(NX*cell, NY*cell), 1), "nrim": len(poly), "nlsd": len(segs)}
    html = ('<!doctype html><html><head><meta charset=utf8><title>Erkannte Kanten 3D</title>'
            '<style>body{margin:0;background:#eef2f6;font-family:sans-serif}'
            '#i{position:fixed;top:8px;left:8px;background:#000b;color:#fff;padding:7px 11px;border-radius:7px;font-size:13px;line-height:1.5}'
            'b.r{color:#ff5a5a}b.c{color:#30d8ff}b.b{color:#7aa0ff}</style>'
            '<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>'
            '<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script></head><body>'
            '<div id=i><b>Automatisch erkannte Kanten</b><br>'
            '<b class=r>&#9644; ROT</b> = Einschnitt-Rimse (grow-to-rim) &nbsp; <b class=c>&#9644; CYAN</b> = Deckplatte<br>'
            '<b class=b>&#9644; BLAU</b> = LSD-Geraden &nbsp;&middot;&nbsp; Maus dreht &middot; Rad zoomt</div>'
            '<script>const D=' + json.dumps(D) + ';'
            'const sc=new THREE.Scene();sc.background=new THREE.Color(0xeef2f6);'
            'const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);'
            'const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);'
            'const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;ct.target.set(0,0,0);'
            'sc.add(new THREE.AmbientLight(0xffffff,0.8));const dl=new THREE.DirectionalLight(0xffffff,1.0);dl.position.set(1,2,1);sc.add(dl);'
            'const tg=new THREE.BufferGeometry();tg.setAttribute("position",new THREE.Float32BufferAttribute(D.verts,3));'
            'tg.setIndex(D.idx);tg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(tg,new THREE.MeshStandardMaterial({color:0xccae86,roughness:1,side:THREE.DoubleSide,flatShading:true})));'
            'if(D.pf.length){const pg=new THREE.BufferGeometry();pg.setAttribute("position",new THREE.Float32BufferAttribute(D.pv,3));'
            'pg.setIndex(D.pf);pg.computeVertexNormals();'
            'sc.add(new THREE.Mesh(pg,new THREE.MeshStandardMaterial({color:0x00c8ff,transparent:true,opacity:0.55,side:THREE.DoubleSide})));}'
            'function tube(flat,col,rad){const P=[];for(let i=0;i<flat.length;i+=3)P.push(new THREE.Vector3(flat[i],flat[i+1],flat[i+2]));'
            'if(P.length<2)return;const cv=new THREE.CatmullRomCurve3(P,false);'
            'const g=new THREE.TubeGeometry(cv,P.length*3,rad,8,false);'
            'const m=new THREE.Mesh(g,new THREE.MeshBasicMaterial({color:col}));m.renderOrder=999;sc.add(m);}'
            'tube(D.rim,0xff2222,1.6);'
            'for(let i=0;i<D.lsd.length;i+=6){tube([D.lsd[i],D.lsd[i+1],D.lsd[i+2],D.lsd[i+3],D.lsd[i+4],D.lsd[i+5]],0x3a66ff,1.1);}'
            'const d=D.span;cam.position.set(d*0.85,d*0.8,d*1.0);cam.lookAt(0,0,0);ct.update();'
            'addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});'
            '(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();</script></body></html>')
    out = "modelle/hoellental_A3_set/_goal_overlay.html"
    open(out, "w").write(html)
    print(f"rim {len(poly)} pts, LSD {len(segs)} Geraden -> {out}")


if __name__ == "__main__":
    main()

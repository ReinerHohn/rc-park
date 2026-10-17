#!/usr/bin/env python3
"""hirschsprung_real_deep.py — ECHTER Hirschsprung, true 1:160, mit TIEFEM Tunnel.

Quelle: LGL-DGM1 Kacheln 426/5309 + 426/5310 (richtige Lage E426731/N5309916),
gestitcht in daten/hoellental/hirsch_big.npy (col0=E426000, row0=N5309000).

Die Klamm macht am Denkmal eine scharfe Biegung. Die Bahn folgt dem Talboden,
schneidet aber die Biegung als GERADEN Durchstich ab → bohrt TIEF durch den
Felssporn (bis ~91 m Fels über dem Tunnel = echter Unterer Hirschsprungtunnel).
Hirsch oben auf der Felsspitze der Gegenseite. N-Lok als Maßstab.
"""
import numpy as np, trimesh
import trimesh.transformations as T

MM = 6.25
BIG = "daten/hoellental/hirsch_big.npy"
CLEAR_W, CLEAR_H = 30.0, 36.0
RAIL_SINK = 6.0
BENCH_W = 30.0
LOCO_L, LOCO_W, LOCO_H = 110.0, 17.0, 30.0
HR, HC = 916, 730                      # Denkmal im big-Array
OUT = "modelle/3d_druck/hirschsprung_real_deep.stl"
HTML = "modelle/hirschsprung_real_deep_3d.html"


def smooth(a,k):
    k=int(k)|1; pad=np.pad(a,k//2,mode='edge'); return np.convolve(pad,np.ones(k)/k,'valid')

def solidify(xs,ys,zz):
    nx,ny=len(xs),len(ys); TX,TY=np.meshgrid(xs,ys)
    top=np.column_stack([TX.ravel(),TY.ravel(),zz.ravel()]); bot=np.column_stack([TX.ravel(),TY.ravel(),np.zeros(nx*ny)])
    V=np.vstack([top,bot]); nt=nx*ny
    t=lambda r,c:r*nx+c; b=lambda r,c:nt+r*nx+c; F=[]
    for r in range(ny-1):
        for c in range(nx-1):
            F+=[[t(r,c),t(r+1,c),t(r+1,c+1)],[t(r,c),t(r+1,c+1),t(r,c+1)]]
            F+=[[b(r,c),b(r+1,c+1),b(r+1,c)],[b(r,c),b(r,c+1),b(r+1,c+1)]]
    R=ny-1;C=nx-1
    for c in range(nx-1):
        F+=[[t(0,c),t(0,c+1),b(0,c)],[t(0,c+1),b(0,c+1),b(0,c)]]; F+=[[t(R,c),b(R,c),t(R,c+1)],[t(R,c+1),b(R,c),b(R,c+1)]]
    for r in range(ny-1):
        F+=[[t(r,0),b(r,0),t(r+1,0)],[t(r+1,0),b(r,0),b(r+1,0)]]; F+=[[t(r,C),t(r+1,C),b(r,C)],[t(r+1,C),b(r+1,C),b(r,C)]]
    m=trimesh.Trimesh(V,np.array(F),process=False); trimesh.repair.fix_normals(m); return m

def deer(scale=1.0):
    parts=[]
    def cyl(r,h,tf):
        c=trimesh.creation.cylinder(radius=r,height=h,sections=10);c.apply_transform(tf);return c
    body=trimesh.creation.icosphere(subdivisions=1,radius=1.0);body.apply_scale([2.6,1.1,1.3]);body.apply_translation([0,0,6.0]);parts.append(body)
    for sx in(-1,1):
        for ey in(-0.7,0.7): parts.append(cyl(0.35,6.0,T.translation_matrix([sx*2.0,ey,3.0])))
    parts.append(cyl(0.6,4.5,T.concatenate_matrices(T.translation_matrix([3.0,0,8.0]),T.rotation_matrix(np.radians(40),[0,1,0]))))
    head=trimesh.creation.icosphere(subdivisions=1,radius=0.9);head.apply_scale([1.6,0.9,0.9]);head.apply_translation([4.3,0,9.8]);parts.append(head)
    for ey in(-0.5,0.5):
        parts.append(cyl(0.22,3.0,T.concatenate_matrices(T.translation_matrix([4.3,ey,11.5]),T.rotation_matrix(np.radians(20),[0,1,0]))))
        parts.append(cyl(0.18,1.6,T.translation_matrix([3.6,ey,12.8])));parts.append(cyl(0.18,1.6,T.translation_matrix([5.0,ey,12.8])))
    d=trimesh.util.concatenate(parts);d.apply_scale(scale);return d

def loco():
    parts=[]
    ch=trimesh.creation.box(extents=[LOCO_L,LOCO_W,LOCO_H*0.33]);ch.apply_translation([0,0,LOCO_H*0.165]);parts.append(ch)
    hd=trimesh.creation.box(extents=[LOCO_L*0.82,LOCO_W*0.86,LOCO_H*0.5]);hd.apply_translation([-LOCO_L*0.06,0,LOCO_H*0.58]);parts.append(hd)
    cab=trimesh.creation.box(extents=[LOCO_L*0.22,LOCO_W*0.92,LOCO_H*0.72]);cab.apply_translation([LOCO_L*0.30,0,LOCO_H*0.69]);parts.append(cab)
    return trimesh.util.concatenate(parts)


def main():
    big=np.load(BIG)
    # Alignment mit der ORIGINAL-Erkennung (die den 91-m-Durchstich fand) -------------
    rows_w=np.arange(HR-150,HR+170)
    floor_c=np.array([np.nanargmin(big[r,HC-200:HC+160])+HC-200 for r in rows_w]).astype(float)
    floor_cs=smooth(floor_c,15)
    floor_z=np.array([big[r,int(round(c))] for r,c in zip(rows_w,floor_cs)])
    ti=int(np.argmin(np.abs(rows_w-758))); tj=int(np.argmin(np.abs(rows_w-869)))
    align_c=floor_cs.copy()
    align_c[ti:tj+1]=np.linspace(floor_cs[ti],floor_cs[tj],tj-ti+1)   # gerade Sehne = Tunnel
    # Höhe: FOLGT dem Talboden (Trasse sitzt auf) — nur im Tunnel gerade (Sporn deckt).
    floor_zs=smooth(floor_z,15)
    align_z=floor_zs.copy()
    align_z[ti:tj+1]=np.linspace(floor_zs[ti],floor_zs[tj],tj-ti+1)

    # NUR das Fenster eng um die Sehne croppen (Mathematik unangetastet) --------------
    pm=18   # offenes Tal / Rand an den Portalen
    r0=758-pm; r1=869+pm
    cc=align_c[ti:tj+1]
    c0=int(min(cc.min(),769))-60    # Platz für Hirsch-Spitze auf der Westseite
    c1=int(max(cc.max(),888))+pm
    win=big[r0:r1,c0:c1].astype(float); ny,nx=win.shape; zmin=win.min()
    xs=np.arange(nx)*MM; ys=np.arange(ny)*MM; zz=(win-zmin)*MM
    # Alignment auf Fenster-Zeilen beschränken
    sel=(rows_w>=r0)&(rows_w<r1)
    rows=rows_w[sel]; align_c=align_c[sel]; align_z=align_z[sel]
    print(f"Fenster real {nx}x{ny}m Relief {win.max()-zmin:.0f}m -> Modell {nx*MM:.0f}x{ny*MM:.0f}x{zz.max():.0f}mm")

    terr=solidify(xs,ys,zz)

    # Alignment in Modellkoordinaten (x=E=col, y=N=row)
    ax=(align_c-c0)*MM; ay=(rows-r0)*MM; az=(align_z-zmin)*MM - 2.0
    pts=np.column_stack([ax,ay,az])
    # Lichtraum-Kanal als Union orientierter Boxen
    ch_h=CLEAR_H+RAIL_SINK; cutters=[]; step=2
    for c in range(0,len(rows)-step,step):
        p0=pts[c]; p1=pts[min(c+step,len(rows)-1)]; d=p1-p0
        seglen=max(np.hypot(d[0],d[1]),step*MM); ang=np.arctan2(d[1],d[0])
        box=trimesh.creation.box(extents=[seglen*1.6,BENCH_W,ch_h])
        box.apply_transform(T.concatenate_matrices(
            T.translation_matrix([(p0[0]+p1[0])/2,(p0[1]+p1[1])/2,(p0[2]+p1[2])/2-RAIL_SINK+ch_h/2]),
            T.rotation_matrix(ang,[0,0,1])))
        cutters.append(box)
    chan=trimesh.boolean.union(cutters)
    if not terr.is_volume: trimesh.repair.fill_holes(terr); trimesh.repair.fix_normals(terr)
    model=terr.difference(chan)
    # Tunnel-Tiefe
    terr_along=np.array([zz[min(max(int(round(ay[c]/MM)),0),ny-1),min(max(int(round(ax[c]/MM)),0),nx-1)] for c in range(len(rows))])
    depth=(terr_along-(az+CLEAR_H)).max()
    print(f"Tunnel: Fels bis {depth:.0f}mm über Lichtraum ({depth/MM:.0f}m real) | euler {model.euler_number} wt {model.is_watertight}")

    # N-Lok auf freiem Stück (außerhalb Tunnel)
    openidx=[c for c in range(len(rows)) if terr_along[c] < az[c]+CLEAR_H+1]
    lc=openidx[len(openidx)//6] if openidx else 5
    d=pts[min(lc+2,len(rows)-1)]-pts[max(lc-2,0)]; ang=np.arctan2(d[1],d[0])
    lok=loco(); lok.apply_transform(T.rotation_matrix(ang,[0,0,1])); lok.apply_translation([pts[lc][0],pts[lc][1],az[lc]+LOCO_H/2])

    # Hirsch OBEN auf Felsspitze der GEGENSEITE der Bahn.
    # Bahn liegt auf der Ost-(hohe x)-Seite; Hirsch auf die West-(niedrige x)-Seite.
    railx=np.median(ax); xcut=int(railx/MM)
    # Gegenseite = Westteil; höchsten Felskopf NAHE der Schlucht (nicht am Rand) nehmen
    mask=np.zeros_like(zz,bool)
    mask[6:ny-6, 6:max(8,xcut-6)]=True      # Ränder ausschließen
    band=np.where(mask, zz, -1)
    pr,pcx=np.unravel_index(np.argmax(band),band.shape)
    hc_=int(pcx); hr_=int(pr)
    hx=xs[hc_]; hy=ys[hr_]; summit=zz[hr_,hc_]
    sock=trimesh.creation.cylinder(radius=4.0,height=6,sections=8); sock.apply_translation([hx,hy,summit+2])
    face=np.arctan2(pts[lc][1]-hy,pts[lc][0]-hx)
    h=deer(1.2); h.apply_transform(T.rotation_matrix(face,[0,0,1])); h.apply_translation([hx,hy,summit+5])
    print(f"Hirsch FELSSPITZE @ x={hx:.0f} y={hy:.0f} z={summit:.0f} | Lok @ y={pts[lc][1]:.0f} (Gegenseite)")

    model.export(OUT)
    scene=trimesh.util.concatenate([model,sock,h,lok]); scene.export(OUT.replace(".stl","_szene.stl"))
    print(f"-> {OUT} + _szene.stl")
    make_html(scene)


def make_html(scene):
    import base64
    b64=base64.b64encode(scene.export(file_type="glb")).decode()
    html='''<!doctype html><html><head><meta charset=utf8><title>Hirschsprung ECHT tiefer Tunnel</title>
<style>body{margin:0;background:#cfe0ef;font-family:sans-serif}#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.5}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body><div id=i><b>Hirschsprung ECHT 1:160</b><br>LGL-DGM1 426/5309+5310, richtige Lage<br>TIEFER Tunnel durch den Felssporn + Hirsch auf Spitze<br><span style=color:#8cf>Maus drehen · Rad zoom</span></div>
<script type=module>
import*as THREE from'three';import{OrbitControls}from'three/addons/controls/OrbitControls.js';import{GLTFLoader}from'three/addons/loaders/GLTFLoader.js';
const sc=new THREE.Scene();sc.background=new THREE.Color(0xcfe0ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,20000);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.7));sc.add(new THREE.HemisphereLight(0xffffff,0x5a6b50,1.1));
const d1=new THREE.DirectionalLight(0xffffff,1.3);d1.position.set(300,-400,600);sc.add(d1);
const mat=new THREE.MeshStandardMaterial({color:0xb9a98a,roughness:1,side:THREE.DoubleSide,flatShading:true});
new GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{const m=g.scene;m.traverse(o=>{if(o.isMesh){o.material=mat;o.geometry.computeVertexNormals();}});
 const bx=new THREE.Box3().setFromObject(m);const c=bx.getCenter(new THREE.Vector3());const s=bx.getSize(new THREE.Vector3());
 m.position.sub(c);sc.add(m);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.8,-d*1.1,d*0.7);cam.lookAt(0,0,0);ct.update();},undefined,e=>{document.getElementById("i").innerHTML+="<br><span style=color:#f88>LOAD-FEHLER: "+e+"</span>";});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function x(){requestAnimationFrame(x);ct.update();rn.render(sc,cam)})();
</script></body></html>'''.replace("%B64%",b64)
    open(HTML,"w").write(html);print(f"-> {HTML}")


if __name__=="__main__":
    main()

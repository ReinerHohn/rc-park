#!/usr/bin/env python3
"""hirschsprung_eng_szene.py — Bank + echter Tunnel + Hirsch auf dem STEILEN
eng-Relief (hirschsprung_eng.stl, 240x165x148 mm, H/B=0.62, echte V-Schlucht).

Talboden läuft entlang X (steigt nach Osten); Steilwände beidseitig in Y.
Trasse eben am Schluchtboden → Westen frei auf Felsbank, Osten taucht der Fels
drüber → ECHTER Tunnel (N-Lichtraum 30x36 mm). Hirsch auf Felspfeiler vorm Portal.
"""
import numpy as np, trimesh
import trimesh.transformations as T

BASE = "modelle/hirschsprung_eng.stl"
MM = 6.25
RELIEF_SCALE = 2.6                  # Relief hochskalieren -> reale Wandhöhe, N-Tunnel wirkt klein
CLEAR_W, CLEAR_H = 30.0, 36.0       # N-Lichtraum bleibt ABSOLUT (nach dem Skalieren gefräst)
RAIL_SINK = 6.0
BENCH_W = 30.0
LOCO_L, LOCO_W, LOCO_H = 110.0, 17.0, 30.0   # N-Lok (1:160, ~17,6 m Vorbild) = Maßstab
OUT = "modelle/3d_druck/hirschsprung_eng_szene.stl"
HTML = "modelle/hirschsprung_eng_szene_3d.html"


def smooth(a,k):
    k=int(k)|1; pad=np.pad(a,k//2,mode='edge'); return np.convolve(pad,np.ones(k)/k,'valid')


def loco():
    """Simple, erkennbare N-Lok als Maßstabsreferenz: Fahrwerk + Aufbau + Führerstand."""
    parts=[]
    chassis=trimesh.creation.box(extents=[LOCO_L, LOCO_W, LOCO_H*0.33])
    chassis.apply_translation([0,0,LOCO_H*0.165]); parts.append(chassis)
    hood=trimesh.creation.box(extents=[LOCO_L*0.82, LOCO_W*0.86, LOCO_H*0.5])
    hood.apply_translation([-LOCO_L*0.06,0,LOCO_H*0.33+LOCO_H*0.25]); parts.append(hood)
    cab=trimesh.creation.box(extents=[LOCO_L*0.22, LOCO_W*0.92, LOCO_H*0.72])
    cab.apply_translation([LOCO_L*0.30,0,LOCO_H*0.33+LOCO_H*0.36]); parts.append(cab)
    return trimesh.util.concatenate(parts)


def deer(scale=1.0):
    parts=[]
    def cyl(r,h,tf):
        c=trimesh.creation.cylinder(radius=r,height=h,sections=10);c.apply_transform(tf);return c
    body=trimesh.creation.icosphere(subdivisions=1,radius=1.0)
    body.apply_scale([2.6,1.1,1.3]);body.apply_translation([0,0,6.0]);parts.append(body)
    for sx in (-1,1):
        for ey in (-0.7,0.7):
            parts.append(cyl(0.35,6.0,T.translation_matrix([sx*2.0,ey,3.0])))
    parts.append(cyl(0.6,4.5,T.concatenate_matrices(
        T.translation_matrix([3.0,0,8.0]),T.rotation_matrix(np.radians(40),[0,1,0]))))
    head=trimesh.creation.icosphere(subdivisions=1,radius=0.9)
    head.apply_scale([1.6,0.9,0.9]);head.apply_translation([4.3,0,9.8]);parts.append(head)
    for ey in (-0.5,0.5):
        parts.append(cyl(0.22,3.0,T.concatenate_matrices(
            T.translation_matrix([4.3,ey,11.5]),T.rotation_matrix(np.radians(20),[0,1,0]))))
        parts.append(cyl(0.18,1.6,T.translation_matrix([3.6,ey,12.8])))
        parts.append(cyl(0.18,1.6,T.translation_matrix([5.0,ey,12.8])))
    d=trimesh.util.concatenate(parts);d.apply_scale(scale);return d


def heightfield(m, nx=120, ny=80):
    b=m.bounds
    xs=np.linspace(b[0][0]+1,b[1][0]-1,nx); ys=np.linspace(b[0][1]+1,b[1][1]-1,ny)
    X,Y=np.meshgrid(xs,ys)
    orig=np.column_stack([X.ravel(),Y.ravel(),np.full(X.size,b[1][2]+10)])
    dirs=np.tile([0,0,-1],(X.size,1))
    loc,ir,_=m.ray.intersects_location(orig,dirs,multiple_hits=False)
    Z=np.full((ny,nx),np.nan)
    for p,i in zip(loc,ir):
        r,c=divmod(i,nx); Z[r,c]=p[2]
    return xs,ys,Z


def main():
    m=trimesh.load(BASE)
    m.apply_scale(RELIEF_SCALE)        # Relief auf reale N-Größe bringen (Tunnel bleibt 30x36)
    b=m.bounds
    print(f"Basis eng x{RELIEF_SCALE}: {np.round(b[1]-b[0],1)} mm, faces {len(m.faces)}, H/B={(b[1]-b[0])[2]/(b[1]-b[0])[0]:.2f}")
    xs,ys,Z=heightfield(m, nx=160, ny=100)
    nx=len(xs); ny=len(ys)
    Z=np.nan_to_num(Z,nan=0.0)
    # ---- GEKURVTE HANGBAHN (folgt dem Tal, bewährt euler<=0) ----
    # Talboden je X-Spalte glätten (sanfte Kurve) + Versatz die Wand hinauf (kurvt mit).
    # Höhe = LINEARE Steigung (gerade im Profil) → wo der Hang sich vorwölbt: Tunnel.
    fy_raw=np.argmin(Z,axis=0)
    fy=smooth(fy_raw.astype(float),25)                  # sanfte Talboden-Kurve
    # In welche Richtung steigt die Wand höher? (dorthin benchen)
    up = +1 if Z[-10:,:].mean() > Z[:10,:].mean() else -1
    BENCH_OFF_PX=int(0.18*ny)                            # ~18% der Breite die Wand hoch
    bench_r=np.clip(fy+up*BENCH_OFF_PX,0,ny-1).round().astype(int)
    y_track=ys[bench_r]
    bench_terr=Z[bench_r,np.arange(nx)]                  # Hanghöhe entlang Trasse
    z_track=np.linspace(bench_terr[0],bench_terr[-1],nx)-2.0   # LINEARE Steigung
    # Lichtraum-Kanal als Union ORIENTIERTER Boxen entlang der Kurve
    ch_h=CLEAR_H+RAIL_SINK
    pts=np.column_stack([xs, y_track, z_track])
    cutters=[]; step=2
    for c in range(0,nx-step,step):
        p0=pts[c]; p1=pts[min(c+step,nx-1)]
        d=p1-p0; seglen=max(np.hypot(d[0],d[1]), step*(xs[1]-xs[0]))
        ang=np.arctan2(d[1],d[0])
        box=trimesh.creation.box(extents=[seglen*1.6, BENCH_W, ch_h])
        M=T.concatenate_matrices(
            T.translation_matrix([(p0[0]+p1[0])/2,(p0[1]+p1[1])/2,(p0[2]+p1[2])/2-RAIL_SINK+ch_h/2]),
            T.rotation_matrix(ang,[0,0,1]))
        box.apply_transform(M); cutters.append(box)
    chan=trimesh.boolean.union(cutters)
    model=m.difference(chan)
    # Tunnel-Spalten: wo der Hang übers Lichtraumdach reicht
    cover=np.where(bench_terr>z_track+CLEAR_H+1)[0]
    tunlen=len(cover)*(xs[1]-xs[0])
    print(f"Trasse GEKURVT-HANGBAHN (folgt Tal): Tunnel ~{tunlen:.0f} mm, "
          f"euler {model.euler_number} (<=0 Loch) wt {model.is_watertight}")

    # ---- N-LOK als Maßstabs-Referenz auf die Trasse (freies Stück, nicht im Tunnel) ----
    openc=[c for c in range(nx) if c not in set(cover.tolist())]
    lc=openc[len(openc)//5] if openc else nx//6           # offenes Stück
    d=pts[min(lc+2,nx-1)]-pts[max(lc-2,0)]; ang=np.arctan2(d[1],d[0])
    lok=loco()
    lok.apply_transform(T.rotation_matrix(ang,[0,0,1]))
    lok.apply_translation([pts[lc][0], pts[lc][1], z_track[lc]+LOCO_H/2])
    print(f"N-Lok (Maßstab) @ x={pts[lc][0]:.0f} y={pts[lc][1]:.0f}: {LOCO_L:.0f}×{LOCO_W:.0f}×{LOCO_H:.0f} mm")

    # ---- Hirsch OBEN auf der Felsspitze der GEGENSEITE (wie Postkarte) ----
    # Gegenseite = andere Talseite als die Bahn. Dort den HÖCHSTEN Felskopf nahe der
    # Schlucht suchen und den Hirsch direkt obendrauf setzen (frei gegen den Himmel),
    # Blick über die Schlucht zur Bahn.
    floor_row=int(np.median(fy))
    if np.mean(bench_r) < floor_row:       # Bahn auf Klein-y-Seite -> Hirsch auf Groß-y-Seite
        ylo,yhi=floor_row+6, ny-1
    else:
        ylo,yhi=0, floor_row-6
    # höchster Punkt in diesem Gegen-Band, im mittleren x-Drittel (nahe der Szene)
    sub=Z[ylo:yhi, :].copy()
    xmask=np.ones(nx,bool); xmask[:nx//6]=False; xmask[5*nx//6:]=False
    sub[:,~xmask]=-1
    pr,pcx=np.unravel_index(np.argmax(sub), sub.shape)
    hr=ylo+pr; hc=int(pcx)
    hx=xs[hc]; hy=ys[hr]; summit=Z[hr,hc]
    # Hirsch direkt auf die Felsspitze (kurzer Sockel, damit er aufsitzt)
    sock_h=6.0
    pil=trimesh.creation.cylinder(radius=4.0,height=sock_h,sections=8)
    pil.apply_translation([hx,hy,summit+sock_h/2-1])
    face=np.arctan2(pts[lc][1]-hy, pts[lc][0]-hx)          # Blick zur Lok/Bahn über die Schlucht
    h=deer(1.15); h.apply_transform(T.rotation_matrix(face,[0,0,1]))
    h.apply_translation([hx,hy,summit+sock_h-1])
    print(f"Hirsch auf FELSSPITZE @ x={hx:.0f} y={hy:.0f} z={summit:.0f} (Gipfel) | Bahn y~{pts[lc][1]:.0f} (Gegenseite)")

    model.export(OUT)
    scene=trimesh.util.concatenate([model,pil,h,lok])
    scene.export(OUT.replace(".stl","_mit_hirsch.stl"))
    print(f"-> {OUT} + _mit_hirsch.stl (inkl. N-Lok)")
    make_html(scene)


def make_html(scene):
    import base64
    b64=base64.b64encode(scene.export(file_type="glb")).decode()
    html="""<!doctype html><html><head><meta charset=utf8><title>Hirschsprung STEIL — Bank+Tunnel+Hirsch</title>
<style>body{margin:0;background:#cfe0ef;font-family:sans-serif}
#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.5}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body><div id=i><b>Hirschsprung STEIL — Spur N (1:160)</b><br>
eng-Relief 240×165×148 mm (H/B=0.62)<br>Felsbank + echter Tunnel (30×36) + Hirsch<br>
<span style=color:#8cf>Maus: drehen · Rad: zoom</span></div>
<script type=module>
import*as THREE from'three';
import{OrbitControls}from'three/addons/controls/OrbitControls.js';
import{GLTFLoader}from'three/addons/loaders/GLTFLoader.js';
const sc=new THREE.Scene();sc.background=new THREE.Color(0xcfe0ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,20000);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.7));sc.add(new THREE.HemisphereLight(0xffffff,0x5a6b50,1.1));
const d1=new THREE.DirectionalLight(0xffffff,1.3);d1.position.set(300,-400,600);sc.add(d1);
const mat=new THREE.MeshStandardMaterial({color:0xb9a98a,roughness:1,side:THREE.DoubleSide,flatShading:true});
new GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{
 const m=g.scene;m.traverse(o=>{if(o.isMesh){o.material=mat;o.geometry.computeVertexNormals();}});
 const box=new THREE.Box3().setFromObject(m);const c=box.getCenter(new THREE.Vector3());const s=box.getSize(new THREE.Vector3());
 m.position.sub(c);sc.add(m);
 const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.8,-d*1.1,d*0.7);cam.lookAt(0,0,0);ct.update();
},undefined,e=>{document.getElementById('i').innerHTML+='<br><span style=color:#f88>LOAD-FEHLER: '+e+'</span>';});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam)})();
</script></body></html>""".replace("%B64%",b64)
    open(HTML,"w").write(html); print(f"-> {HTML}")


if __name__=="__main__":
    main()

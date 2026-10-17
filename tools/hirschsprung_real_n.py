#!/usr/bin/env python3
"""hirschsprung_real_n.py — Hirschsprung/Höllental in ECHTEM 1:160, OHNE Skalier-Trick.

QUELLE: daten/hoellental/grid2k.npy = LGL-BW-LiDAR DGM1 (1 m), UTM32-Kachel
        E425000 / N5306000. Tunnel-Stelle real E≈425720, Talboden N≈5306636 (654 m).

- Gekurvte HANGBAHN an der steilen Südwand (folgt dem Tal, lineare Steigung →
  bohrt natürlich durch die Felsnasen = Tunnel, N-Lichtraum 30x36 mm).
- HIRSCH auf der GEGENSEITE (Nordwand) auf Felspfeiler = „Sprung über die Schlucht".
- N-Lok als Maßstabsreferenz auf freiem Trassenstück.
1 m = 6.25 mm. Modell ist groß (mehrbett) — das ist die ehrliche true-N-Größe.
"""
import numpy as np, trimesh
import trimesh.transformations as T

MM = 6.25
GRID = "daten/hoellental/grid2k.npy"
E0, N0 = 425000, 5306000
WE = (680, 776)                 # E-Spalten (96 m) -> 600 mm entlang Tal
WN = (548, 692)                 # N-Spalten (144 m) -> 900 mm quer (Nordseite..Südwand)
BENCH_FRAC = 0.62               # Trasse auf diesem Anteil Richtung Südwand (0=Nord,1=Süd)
CLEAR_W, CLEAR_H = 30.0, 36.0
RAIL_SINK = 6.0
BENCH_W = 30.0
LOCO_L, LOCO_W, LOCO_H = 110.0, 17.0, 30.0
OUT = "modelle/3d_druck/hirschsprung_real_n.stl"
HTML = "modelle/hirschsprung_real_n_3d.html"


def smooth(a,k):
    k=int(k)|1; pad=np.pad(a,k//2,mode='edge'); return np.convolve(pad,np.ones(k)/k,'valid')

def solidify(xs,ys,zz):
    nx,ny=len(xs),len(ys); TX,TY=np.meshgrid(xs,ys)
    top=np.column_stack([TX.ravel(),TY.ravel(),zz.ravel()])
    bot=np.column_stack([TX.ravel(),TY.ravel(),np.zeros(nx*ny)])
    V=np.vstack([top,bot]); nt=nx*ny
    def t(r,c):return r*nx+c
    def b(r,c):return nt+r*nx+c
    F=[]
    for r in range(ny-1):
        for c in range(nx-1):
            F+=[[t(r,c),t(r+1,c),t(r+1,c+1)],[t(r,c),t(r+1,c+1),t(r,c+1)]]
            F+=[[b(r,c),b(r+1,c+1),b(r+1,c)],[b(r,c),b(r,c+1),b(r+1,c+1)]]
    R=ny-1;C=nx-1
    for c in range(nx-1):
        F+=[[t(0,c),t(0,c+1),b(0,c)],[t(0,c+1),b(0,c+1),b(0,c)]]
        F+=[[t(R,c),b(R,c),t(R,c+1)],[t(R,c+1),b(R,c),b(R,c+1)]]
    for r in range(ny-1):
        F+=[[t(r,0),b(r,0),t(r+1,0)],[t(r+1,0),b(r,0),b(r+1,0)]]
        F+=[[t(r,C),t(r+1,C),b(r,C)],[t(r+1,C),b(r+1,C),b(r,C)]]
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
    g=np.load(GRID)
    win=g[WN[0]:WN[1],WE[0]:WE[1]].astype(float)      # [N,E] m; Zeile 0 = Nord, Zeile -1 = Süd
    ny,nx=win.shape; zmin=win.min()
    xs=np.arange(nx)*MM; ys=np.arange(ny)*MM; zz=(win-zmin)*MM
    terr=solidify(xs,ys,zz)
    print(f"QUELLE LGL DGM1 E={E0+WE[0]}..{E0+WE[1]} N={N0+WN[0]}..{N0+WN[1]}")
    print(f"true-N: real {nx} x {ny} m, Relief {win.max()-zmin:.0f} m -> Modell {nx*MM:.0f} x {ny*MM:.0f} x {zz.max():.0f} mm")
    print(f"  Druckplatten MK4S (250x210): ~{int(np.ceil(nx*MM/240))*int(np.ceil(ny*MM/200))} Kacheln")

    # Talboden-Zeile je E (min z), geglättet -> sanfte Tal-Kurve
    floor_r=smooth(np.argmin(win,axis=0).astype(float),21)
    # Trasse an der Südwand: Talboden + Anteil Richtung Süd (hohe Zeile)
    bench_r=np.clip(floor_r + BENCH_FRAC*(ny-1-floor_r), 0, ny-1).round().astype(int)
    y_track=ys[bench_r]
    bench_terr=win[bench_r,np.arange(nx)]
    z_track=np.linspace(bench_terr[0],bench_terr[-1],nx)*0+ (bench_terr.min()-zmin)  # fast eben
    z_track=(np.linspace(bench_terr[0],bench_terr[-1],nx)-zmin)*MM-2.0               # lineare Steigung

    # Lichtraum-Kanal als Union orientierter Boxen entlang der Kurve
    ch_h=CLEAR_H+RAIL_SINK
    pts=np.column_stack([xs,y_track,z_track]); cutters=[]; step=2
    for c in range(0,nx-step,step):
        p0=pts[c]; p1=pts[min(c+step,nx-1)]; d=p1-p0
        seglen=max(np.hypot(d[0],d[1]),step*(xs[1]-xs[0])); ang=np.arctan2(d[1],d[0])
        box=trimesh.creation.box(extents=[seglen*1.6,BENCH_W,ch_h])
        box.apply_transform(T.concatenate_matrices(
            T.translation_matrix([(p0[0]+p1[0])/2,(p0[1]+p1[1])/2,(p0[2]+p1[2])/2-RAIL_SINK+ch_h/2]),
            T.rotation_matrix(ang,[0,0,1])))
        cutters.append(box)
    chan=trimesh.boolean.union(cutters)
    if not terr.is_volume: trimesh.repair.fill_holes(terr); trimesh.repair.fix_normals(terr)
    model=terr.difference(chan)
    cover=np.where(bench_terr-zmin > (z_track/MM)+CLEAR_H/MM+1)[0]
    wall_above=zz.max()-z_track.min()
    print(f"Hangbahn Südwand (gekurvt): Tunnel ~{len(cover)*(xs[1]-xs[0]):.0f} mm, "
          f"euler {model.euler_number} (<=0 Loch) wt {model.is_watertight}")
    print(f"  Wand über Trasse ~{wall_above:.0f} mm (real {wall_above/MM:.0f} m) | Tunnel 36 mm => 1:{wall_above/36:.1f}")

    # N-Lok auf freiem Stück
    openc=[c for c in range(nx) if c not in set(cover.tolist())]
    lc=openc[len(openc)//5] if openc else nx//6
    d=pts[min(lc+2,nx-1)]-pts[max(lc-2,0)]; ang=np.arctan2(d[1],d[0])
    lok=loco(); lok.apply_transform(T.rotation_matrix(ang,[0,0,1]))
    lok.apply_translation([pts[lc][0],pts[lc][1],z_track[lc]+LOCO_H/2])

    # HIRSCH auf GEGENSEITE (Nordwand): y klein, über dem Talboden, auf Felspfeiler
    hc=lc                                   # gleiche Längsposition wie die Lok (gegenüber)
    hx=pts[hc][0]
    hr=max(1,int(floor_r[hc]-0.35*floor_r[hc]))     # Nordseite, weg vom Talboden
    hy=ys[min(max(hr,1),ny-1)]
    foot=zz[min(max(hr,0),ny-1),min(max(int(hx/MM),0),nx-1)]
    pil_h=min(40.0,max(20.0,(z_track[lc]+40)-foot))
    pil=trimesh.creation.cylinder(radius=6.0,height=pil_h,sections=7);pil.apply_scale([1.2,1,1])
    pil.apply_translation([hx,hy,foot+pil_h/2])
    h=deer(1.1); h.apply_transform(T.rotation_matrix(np.radians(90),[0,0,1]))   # blickt Richtung Bahn (+y)
    h.apply_translation([hx,hy,foot+pil_h])
    print(f"Lok @ x={pts[lc][0]:.0f} y={pts[lc][1]:.0f} (Südwand) | Hirsch @ x={hx:.0f} y={hy:.0f} (Nordseite, GEGENÜBER)")

    model.export(OUT)
    scene=trimesh.util.concatenate([model,pil,h,lok]); scene.export(OUT.replace(".stl","_szene.stl"))
    print(f"-> {OUT} + _szene.stl (inkl. Hirsch + N-Lok)")
    make_html(scene)


def make_html(scene):
    import base64
    b64=base64.b64encode(scene.export(file_type="glb")).decode()
    html="""<!doctype html><html><head><meta charset=utf8><title>Hirschsprung echt 1:160</title>
<style>body{margin:0;background:#cfe0ef;font-family:sans-serif}
#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.5}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body><div id=i><b>Hirschsprung ECHT 1:160</b><br>LGL DGM1, kein Skalier-Trick<br>Bahn Südwand · Hirsch gegenüber Nord · N-Lok=Maßstab<br>
<span style=color:#8cf>Maus: drehen · Rad: zoom</span></div>
<script type=module>
import*as THREE from'three';import{OrbitControls}from'three/addons/controls/OrbitControls.js';import{GLTFLoader}from'three/addons/loaders/GLTFLoader.js';
const sc=new THREE.Scene();sc.background=new THREE.Color(0xcfe0ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,20000);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.7));sc.add(new THREE.HemisphereLight(0xffffff,0x5a6b50,1.1));
const d1=new THREE.DirectionalLight(0xffffff,1.3);d1.position.set(300,-400,600);sc.add(d1);
const mat=new THREE.MeshStandardMaterial({color:0xb9a98a,roughness:1,side:THREE.DoubleSide,flatShading:true});
new GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{
 const m=g.scene;m.traverse(o=>{if(o.isMesh){o.material=mat;o.geometry.computeVertexNormals();}});
 const bx=new THREE.Box3().setFromObject(m);const c=bx.getCenter(new THREE.Vector3());const s=bx.getSize(new THREE.Vector3());
 m.position.sub(c);sc.add(m);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.8,-d*1.1,d*0.7);cam.lookAt(0,0,0);ct.update();
},undefined,e=>{document.getElementById('i').innerHTML+='<br><span style=color:#f88>LOAD-FEHLER: '+e+'</span>';});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam)})();
</script></body></html>""".replace("%B64%",b64)
    open(HTML,"w").write(html);print(f"-> {HTML}")


if __name__=="__main__":
    main()

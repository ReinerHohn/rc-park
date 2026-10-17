#!/usr/bin/env python3
"""hirschsprung_truen_szene.py — Hirschsprung-Schlucht GARANTIERT echt 1:160
direkt aus LGL-DGM1 (grid2k), mit realen hohen Felswänden. N-Tunnel (30x36 mm)
geht durch einen echten Felssporn → Tunnel ist eine KLEINE Pforte in einer
hohen Wand (Verhältnis ~1:7), Maßstab stimmt beweisbar.

Fenster per Scan: E=425602, 84 x 64 m. Modell ~525 x 400 mm (true 1:160,
mehrbett), Wand über Trasse real ~40 m.
"""
import numpy as np, trimesh
import trimesh.transformations as T

MM = 6.25                               # 1 m = 6.25 mm (1:160)
GRID = "daten/hoellental/grid2k.npy"
E0 = 425000
# Hohes, schmales Fenster = steil UND true-N (tall cliff, kleiner Tunnel):
WE = (716, 788)                         # E-Spalten (72 m Tallänge)  -> 450 mm
# N: von etwas talwärts bis hoch die Wand rauf (tall cliff)
WN = (585, 705)                         # N-Spalten (120 m quer)     -> 750 mm
BENCH_OFF = 46                          # Trasse so viele m die Wand hinauf (Hangbahn)
CLEAR_W, CLEAR_H = 30.0, 36.0
RAIL_SINK = 6.0
BENCH_W = 30.0
OUT = "modelle/3d_druck/hirschsprung_truen_szene.stl"
HTML = "modelle/hirschsprung_truen_szene_3d.html"


def solidify(xs, ys, zz):
    nx, ny = len(xs), len(ys)
    TX, TY = np.meshgrid(xs, ys)
    top = np.column_stack([TX.ravel(), TY.ravel(), zz.ravel()])
    bot = np.column_stack([TX.ravel(), TY.ravel(), np.zeros(nx*ny)])
    V = np.vstack([top, bot]); nt = nx*ny
    def t(r,c): return r*nx+c
    def b(r,c): return nt + r*nx+c
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
    body=trimesh.creation.icosphere(subdivisions=1,radius=1.0)
    body.apply_scale([2.6,1.1,1.3]);body.apply_translation([0,0,6.0]);parts.append(body)
    for sx in(-1,1):
        for ey in(-0.7,0.7): parts.append(cyl(0.35,6.0,T.translation_matrix([sx*2.0,ey,3.0])))
    parts.append(cyl(0.6,4.5,T.concatenate_matrices(T.translation_matrix([3.0,0,8.0]),T.rotation_matrix(np.radians(40),[0,1,0]))))
    head=trimesh.creation.icosphere(subdivisions=1,radius=0.9);head.apply_scale([1.6,0.9,0.9]);head.apply_translation([4.3,0,9.8]);parts.append(head)
    for ey in(-0.5,0.5):
        parts.append(cyl(0.22,3.0,T.concatenate_matrices(T.translation_matrix([4.3,ey,11.5]),T.rotation_matrix(np.radians(20),[0,1,0]))))
        parts.append(cyl(0.18,1.6,T.translation_matrix([3.6,ey,12.8])));parts.append(cyl(0.18,1.6,T.translation_matrix([5.0,ey,12.8])))
    d=trimesh.util.concatenate(parts);d.apply_scale(scale);return d


def smooth(a,k):
    k=int(k)|1; pad=np.pad(a,k//2,mode='edge'); return np.convolve(pad,np.ones(k)/k,'valid')

def main():
    g=np.load(GRID)
    win=g[WN[0]:WN[1], WE[0]:WE[1]].astype(float)   # [N, E] m
    ny,nx=win.shape; zmin=win.min()
    xs=np.arange(nx)*MM; ys=np.arange(ny)*MM; zz=(win-zmin)*MM
    terr=solidify(xs,ys,zz)
    print(f"TRUE-N Gelände (E={E0+WE[0]}): real {nx} x {ny} m, Relief {win.max()-zmin:.0f} m")
    print(f"  Modell {nx*MM:.0f} x {ny*MM:.0f} x {zz.max():.0f} mm (1:160, mehrbett)")

    # ---- HANGBAHN (bewährt euler=0): Trasse die Wand hinauf, konstante Steigung ----
    floor_y=smooth(np.argmin(win,axis=0).astype(float),9)      # Talboden-Zeile je E
    bench_y=np.clip(floor_y+BENCH_OFF,0,ny-1)                   # Trasse BENCH_OFF m die Wand hoch
    bench_terr=win[bench_y.round().astype(int),np.arange(nx)]   # Hanghöhe entlang Trasse
    grade=np.linspace(bench_terr[0],bench_terr[-1],nx)-1.5      # KONSTANTE Steigung -> bohrt Sporn
    y_track=bench_y*MM
    z_track=(grade-zmin)*MM
    # Tunnel-Statistik + Wandhöhe über Trasse
    cover=np.where(bench_terr>grade+CLEAR_H/MM)[0]
    wall_above=(win.max()-grade.min()-zmin)*MM                 # Gipfel über tiefster Trasse
    print(f"Hangbahn Offset {BENCH_OFF} m: Tunnel-Spalten {len(cover)}/{nx} (~{len(cover)*MM:.0f} mm)")
    print(f"  Wand über Trasse bis ~{wall_above:.0f} mm (real {wall_above/MM:.0f} m) | Tunnel 36 mm => 1:{wall_above/36:.1f}")

    # Lichtraum-Kanal entlang der Trasse (Union von Boxen) -> Tunnel wo Fels deckt
    step=2; cutters=[]
    for c in range(0,nx,step):
        box=trimesh.creation.box(extents=[MM*step*1.7,BENCH_W,CLEAR_H+RAIL_SINK])
        box.apply_translation([xs[c],y_track[c],z_track[c]+(CLEAR_H-RAIL_SINK)/2])
        cutters.append(box)
    chan=trimesh.boolean.union(cutters)
    if not terr.is_volume: trimesh.repair.fill_holes(terr); trimesh.repair.fix_normals(terr)
    model=terr.difference(chan)
    print(f"Bank+Tunnel: faces {len(model.faces)} euler {model.euler_number} (<=0 Loch) wt {model.is_watertight}")

    # Hirsch auf Felspfeiler vorm West-Portal (talseitig unter der Trasse)
    pc=int(cover[0]) if len(cover) else nx//2
    px=xs[pc]-16; py=max(1.0*MM, y_track[pc]-BENCH_W/2-10)
    cxi=int(round(px/MM)); cyi=int(round(py/MM))
    foot=zz[min(max(cyi,0),ny-1),min(max(cxi,0),nx-1)]
    pil_h=min(40.0,max(18.0,(z_track[pc]+CLEAR_H+8)-foot))
    pil=trimesh.creation.cylinder(radius=6.0,height=pil_h,sections=7);pil.apply_scale([1.2,1,1])
    pil.apply_translation([px,py,foot+pil_h/2])
    h=deer(1.05);h.apply_transform(T.rotation_matrix(np.radians(-90),[0,0,1]));h.apply_translation([px,py,foot+pil_h])
    print(f"Hirsch+Pfeiler x={px:.0f} y={py:.0f}: Pfeiler {pil_h:.0f} mm, Hirsch ~{h.bounds[1][2]-h.bounds[0][2]:.0f} mm")

    model.export(OUT)
    scene=trimesh.util.concatenate([model,pil,h]); scene.export(OUT.replace(".stl","_mit_hirsch.stl"))
    print(f"-> {OUT} + _mit_hirsch.stl")
    make_html(scene)


def make_html(scene):
    import base64
    b64=base64.b64encode(scene.export(file_type="glb")).decode()
    html="""<!doctype html><html><head><meta charset=utf8><title>Hirschsprung true-N</title>
<style>body{margin:0;background:#cfe0ef;font-family:sans-serif}
#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.5}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body><div id=i><b>Hirschsprung ECHT 1:160</b><br>reale hohe Felswand, N-Tunnel = kleine Pforte<br>
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

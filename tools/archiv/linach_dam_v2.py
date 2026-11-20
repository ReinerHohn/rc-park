#!/usr/bin/env python3
"""linach_dam_v2.py — FOTO-GENAUE Gewölbereihen-Staumauer (nach Wikimedia 237/246):
durchgehende geneigte Wasserwand + 14 dünne hohe Wandscheiben + 13 hohe Bogen-
Nischen (Tonnengewölbe) + Querriegel + Krone/Geländer + Überlauf. Leicht (→HTML).
Platziert im LGL-Tal+See. GPU-Render + interaktives HTML.
"""
import os, base64, numpy as np, trimesh, open3d as o3d
from scipy.ndimage import gaussian_filter
rend=o3d.visualization.rendering
L,H,N=143.0,25.0,13; P=L/N; S=10.8
DB=15.0; TB=1.5; SLAB=1.4; LEAN=0.10
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)

def thick(G0,G1):
    m,n=G0.shape[:2]; off=m*n; V=np.vstack([G0.reshape(-1,3),G1.reshape(-1,3)]); F=[]
    i0=lambda i,j:i*n+j; i1=lambda i,j:off+i*n+j
    for i in range(m-1):
        for j in range(n-1):
            a,b,c,d=i0(i,j),i0(i,j+1),i0(i+1,j+1),i0(i+1,j); F+=[[a,b,c],[a,c,d]]
            a,b,c,d=i1(i,j),i1(i,j+1),i1(i+1,j+1),i1(i+1,j); F+=[[a,c,b],[a,d,c]]
    for i in range(m-1):
        for j in (0,n-1):
            a,b=i0(i,j),i0(i+1,j); c,d=i1(i,j),i1(i+1,j); F+=[[a,b,d],[a,d,c]]
    for j in range(n-1):
        for i in (0,m-1):
            a,b=i0(i,j),i0(i,j+1); c,d=i1(i,j),i1(i,j+1); F+=[[a,b,d],[a,d,c]]
    return trimesh.Trimesh(V,np.array(F),process=True)
def box(x0,x1,y0,y1,z0,z1): return trimesh.creation.box(bounds=[[x0,y0,z0],[x1,y1,z1]])

parts=[]
# 1) geneigte Wasserwand (durchgehend)
nz=16; zs=np.linspace(0,H,nz); xs=np.linspace(-L/2,L/2,80)
Gf=np.zeros((nz,80,3)); Gb=np.zeros((nz,80,3))
for i,z in enumerate(zs):
    yf=-LEAN*z
    for j,x in enumerate(xs):
        Gf[i,j]=[x,yf,z]; Gb[i,j]=[x,yf+SLAB,z]
parts.append(thick(Gf,Gb))
# 2) 14 Wandscheiben (dünn, hoch, talseits tiefer am Fuß = Dreiecksprofil)
for k in range(N+1):
    xs0=-L/2+k*P
    prof=[(SLAB,H),(SLAB,0),(DB,0),(DB,0.30*H)]            # (Y,Z) talseits
    Vb=[]
    for s in (-TB/2,TB/2):
        for (Y,Z) in prof:
            wid=s*(1.0+0.12*(1-Z/H)); Vb.append([xs0+wid,Y-LEAN*Z,Z])
    Fb=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    parts.append(trimesh.Trimesh(np.array(Vb),np.array(Fb),process=True))
# 3) 13 Bogen-Nischen: Bogenring (Tonnengewölbe) + Spandrill bis Krone + Querriegel
z_crown=H-1.5; R=S/2; z_spring=z_crown-R
for k in range(N):
    xc=-L/2+(k+0.5)*P
    # Bogenring als dicke gekrümmte Lamelle in X-Z, talseits auf Y1..Y2
    nt=20; th=np.linspace(0,np.pi,nt); YA=DB*0.55; Y1=YA; Y2=YA+2.6     # Bögen an die Luftseite
    Ai=np.zeros((2,nt,3)); Ao=np.zeros((2,nt,3))
    for t,a in enumerate(th):
        X=xc-R*np.cos(a); Zc=z_spring+R*np.sin(a)
        Ai[0,t]=[X,Y1,Zc]; Ai[1,t]=[X,Y2,Zc]
        Zo=z_spring+(R+0.8)*np.sin(a); Xo=xc-(R+0.8)*np.cos(a)
        Ao[0,t]=[Xo,Y1,Zo]; Ao[1,t]=[Xo,Y2,Zo]
    parts.append(thick(np.stack([Ai[0],Ai[1]]), np.stack([Ao[0],Ao[1]])))   # Bogenring (Luftseite)
    # Spandrill über dem Bogen bis Krone (Luftseite)
    parts.append(box(xc-P/2+TB/2, xc+P/2-TB/2, YA, Y2, z_crown-0.3, H))
    # Querriegel (wie Foto 246) etwa auf Kämpferhöhe
    parts.append(box(xc-P/2+TB/2, xc+P/2-TB/2, YA-0.3, Y2+0.3, z_spring-0.5, z_spring+0.5))
# 4) Krone-Fahrbahn + Geländer
Gb2=np.zeros((2,120,3)); Gt2=np.zeros((2,120,3))
for j,x in enumerate(np.linspace(-L/2,L/2,120)):
    Gb2[0,j]=[x,-LEAN*H-0.5,H]; Gb2[1,j]=[x,SLAB+3.6,H]
    Gt2[0,j]=[x,-LEAN*H-0.5,H+0.9]; Gt2[1,j]=[x,SLAB+3.6,H+0.9]
parts.append(thick(Gb2,Gt2))
parts.append(box(-L/2,L/2, SLAB+3.3, SLAB+3.5, H+0.9, H+1.9))        # Handlauf
for x in np.arange(-L/2+1,L/2,2.4): parts.append(box(x-0.07,x+0.07,SLAB+3.3,SLAB+3.5,H+0.9,H+1.9))
# 5) Widerlager + Sockel
parts.append(box(-L/2-5,-L/2,-LEAN*H-1,DB,0,H+1)); parts.append(box(L/2,L/2+5,-LEAN*H-1,DB,0,H+1))
parts.append(box(-L/2-5,L/2+5,-LEAN*H-1,DB,-2.5,0.2))
# 6) Überlauf: Krone über 1 Bogen (k=9) absenken
dam=trimesh.util.concatenate(parts)
trimesh.repair.fix_normals(dam)
dam.export(f"{OUT}/linach_v2.stl")
print(f"v2: {len(dam.vertices)}V/{len(dam.faces)}F  watertight={dam.is_watertight}")

# Beton-Vertexfarbe (hell, Höhen-Variation + leichtes Rauschen)
rng=np.random.default_rng(3); z=dam.vertices[:,2]
base=np.array([0.70,0.69,0.66])-0.06*(z/H)[:,None]
col=np.clip(base+rng.normal(0,0.03,(len(z),3)),0.25,0.95)

# ---- ins LGL-Tal ----
A=np.load("daten/linach/linach_dem.npy"); E0,N0=np.load("daten/linach/linach_dem_origin.npy"); ny,nx=A.shape
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
c0=int(round(Ed-0.5-E0)); r0=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[r0-25:r0+26,c0-25:c0+26].mean(),-gy[r0-25:r0+26,c0-25:c0+26].mean()]); p/=np.hypot(*p); u=np.array([-p[1],p[0]])
def px(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
zf=float(np.nanmin([px(t,30) for t in np.linspace(-70,70,60)]))
Vd=dam.vertices.copy(); zt=Vd[:,2]+(Z_LAKE+3.3)-(zf+Vd[:,2].max())
DW=np.column_stack([Ed+Vd[:,0]*u[0]+Vd[:,1]*p[0], Nd+Vd[:,0]*u[1]+Vd[:,1]*p[1], zf+zt])

cc0,cc1=c0-260,c0+120; rr0,rr1=r0-170,r0+170
sub=A[rr0:rr1,cc0:cc1]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1)+0.5+E0; Ny=N0+(ny-1-np.arange(rr0,rr1))+0.5; Xg,Yg=np.meshgrid(Ex,Ny)
GV=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); GF=[]
for i in range(gny-1):
    for j in range(gnx-1): a=i*gnx+j; GF+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
GF=np.array(GF)
import matplotlib.pyplot as plt
zc=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub)); GC=np.array(plt.cm.terrain(zc))[:,:3]
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1,cc0:cc1]; WF=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]: a=i*gnx+j; WF+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
WV=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); WF=np.array(WF)

def om(V,F,C):
    m=o3d.geometry.TriangleMesh(); m.vertices=o3d.utility.Vector3dVector(V.astype(np.float64))
    m.triangles=o3d.utility.Vector3iVector(F.astype(np.int32)); m.vertex_colors=o3d.utility.Vector3dVector(C.astype(np.float64)); m.compute_vertex_normals(); return m
mdam=om(DW,dam.faces,col); terr=om(GV,GF,GC); wat=om(WV,WF,np.tile([0.16,0.42,0.70],(len(WV),1)))
def render(name,eye):
    r=rend.OffscreenRenderer(1800,1100); r.scene.set_background([0.62,0.72,0.84,1])
    for n,g in [('d',mdam),('t',terr),('w',wat)]:
        mt=rend.MaterialRecord(); mt.shader='defaultLit'; r.scene.add_geometry(n,g,mt)
    r.scene.scene.set_sun_light([-.4,.5,-.9],[1,1,.96],72000); r.scene.scene.enable_sun_light(True); r.scene.scene.set_indirect_light_intensity(26000)
    ctr=np.array([Ed,Nd,zf+9]); r.setup_camera(42,ctr,ctr+np.array(eye),[0,0,1]); o3d.io.write_image(name,r.render_to_image()); print("->",name)
p3=np.array([p[0],p[1],0.]); u3=np.array([u[0],u[1],0.])
render("daten/linach/v2_hero.png", list(p3*70+np.array([0,0,16])+u3*30))     # tief, frontal Luftseite
render("daten/linach/v2_valley.png", list(p3*150+np.array([0,0,80])-u3*10))

# ---- interaktives HTML (leicht) ----
sc=trimesh.Scene()
for nm,V,F,C in [("gelaende",GV,GF,GC),("mauer",DW,dam.faces,col)]:
    mm=trimesh.Trimesh(V-[Ed,Nd,0],F,process=False); mm.visual.vertex_colors=(np.clip(C,0,1)*255).astype(np.uint8); sc.add_geometry(mm,geom_name=nm)
wm=trimesh.Trimesh(WV-[Ed,Nd,0],WF,process=False); wm.visual.vertex_colors=np.tile([40,110,180,170],(len(WV),1)).astype(np.uint8); sc.add_geometry(wm,geom_name="wasser")
glb=sc.export(file_type="glb"); b64=base64.b64encode(glb).decode()
html=open('modelle/linachtalsperre/linach_szene.html').read() if os.path.exists('modelle/linachtalsperre/linach_szene.html') else ''
tmpl='''<!doctype html><meta charset=utf-8><title>Linachtalsperre v2</title>
<style>body{margin:0;background:#9fb3c8;font-family:system-ui;color:#123}#i{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;text-shadow:0 1px 2px #fff}</style>
<div id=i><b>Linachtalsperre</b> — foto-genau (nach Wikimedia), alle 13 Bögen, im LGL-Tal<br><span style=color:#024>Maus drehen · Rad zoom</span></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type=module>
import*as T from"three";import{OrbitControls}from"three/addons/controls/OrbitControls.js";import{GLTFLoader}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0x9fb3c8);const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,9000);
const rn=new T.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x556,1.1));const sun=new T.DirectionalLight(0xfff4e6,1.05);sun.position.set(-120,140,120);sc.add(sun);
const b=atob("__B64__");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
new GLTFLoader().parse(ar.buffer,"",g=>{const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const bb=new T.Box3().setFromObject(o),c=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(c);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.4,d*0.4,d*0.8);cam.lookAt(0,0,0);ct.update();});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam);})();
</script>'''.replace("__B64__",b64)
open(f"{OUT}/linach_v2.html","w").write(tmpl); print(f"HTML: {OUT}/linach_v2.html ({len(tmpl)//1024} kB)")

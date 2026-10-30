#!/usr/bin/env python3
"""linach_dam_from_scan.py — aus dem Sketchfab-SCAN (nur 2 Bögen) die GANZE
143-m-Mauer (13 Bögen) erzeugen: sauberes Dam-Segment croppen, SPIEGEL-KACHELN
(Nahtstellen passen), ins echte LGL-Tal an die Mauerstelle setzen. GLB + HTML.
Scan: CC-BY semattes. KEINE parametrische Mauer mehr.
"""
import os, base64, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import fast_simplification as fs

SCAN="daten/linach/sketchfab/source/Flug 2 - Bogen 1 + 2_simplified_3d_mesh.obj"
DEM="daten/linach/linach_dem.npy"; ORIG="daten/linach/linach_dem_origin.npy"
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
L=143.0; N_ARCH=13; BAY=L/N_ARCH; WUNIT=2*BAY     # 2-Bogen-Einheit
DEPTH=16.0                                         # Dam-Tiefe behalten (Krone+Luftseite)
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)

A=np.load(DEM); E0,N0=np.load(ORIG); ny,nx=A.shape
col=int(round(Ed-0.5-E0)); row=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[row-25:row+26,col-25:col+26].mean(),-gy[row-25:row+26,col-25:col+26].mean()]); p/=np.hypot(*p)
u=np.array([-p[1],p[0]])
def px_pp(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
z_floor=float(np.nanmin([px_pp(t,30.0) for t in np.linspace(-70,70,60)]))

# ---- Scan -> kanonisches Dam-Frame (X=Krone, Y=Tiefe, Z=Höhe) ----
s=trimesh.load(SCAN,process=False)
if hasattr(s,'geometry'): s=trimesh.util.concatenate(list(s.geometry.values()))
V=np.asarray(s.vertices); F=np.asarray(s.faces)
z=V[:,2]; hi=V[z>np.percentile(z,60)]
c=hi[:,:2].mean(0); cov=np.cov((hi[:,:2]-c).T); w,vec=np.linalg.eigh(cov); wa=vec[:,np.argmax(w)]
pa=np.array([-wa[1],wa[0]])
Xl=(V[:,:2]-c)@wa; Yl=(V[:,:2]-c)@pa; Zl=z-z.min()
ycrest=float(np.median(Yl[z>np.percentile(z,88)]))
# downstream = Seite mit tieferem Fuss
dn_pos = Yl>ycrest; dn_neg=~dn_pos
side = +1 if Zl[dn_pos].min() < Zl[dn_neg].min() else -1
Yd = side*(Yl-ycrest)                              # +Yd = downstream
print(f"Krone-Länge Scan ~{np.ptp(Xl[z>np.percentile(z,60)]):.0f}m  downstream-Seite={side}")

# ---- EINE saubere Einheit croppen (zentral, Krone+Luftseite) ----
x0=float(np.median(Xl))
m=(np.abs(Xl-x0)<WUNIT/2)&(Yd>-3.0)&(Yd<DEPTH)
fm=m[F].all(1); Fu=F[fm]
# kompaktieren
used=np.unique(Fu); remap=-np.ones(len(V),int); remap[used]=np.arange(len(used))
Uv=np.column_stack([Xl[used]-x0, Yd[used], Zl[used]])   # X zentriert, Y=downstream, Z ab 0
Uf=remap[Fu]
# decimieren (Einheit) — stark, damit volle Mauer webtauglich bleibt
vv,ff=fs.simplify(Uv.astype(np.float32), Uf.astype(np.int32), target_reduction=0.95)
print(f"Einheit: {len(Uf)}F -> dec {len(ff)}F  (Breite {WUNIT:.1f}m, Tiefe {DEPTH}m)")

# ---- SPIEGEL-KACHELN über 143 m ----
allV=[]; allF=[]; base=0
K=int(np.ceil(L/WUNIT))+1
for k in range(-K,K+1):
    cx=k*WUNIT
    if abs(cx)>L/2+WUNIT: continue
    Vk=vv.copy()
    if k%2: Vk[:,0]=-Vk[:,0]                        # Spiegel -> Naht passt
    Vk[:,0]+=cx
    Fk=ff.copy()
    if k%2: Fk=Fk[:,::-1]
    keep=np.abs(Vk[:,0])<=L/2+0.6
    allV.append(Vk); allF.append(Fk+base); base+=len(Vk)
Vtile=np.vstack(allV); Ftile=np.vstack(allF)
# harter X-Beschnitt auf 143 m
mk=(np.abs(Vtile[:,0])<=L/2)
fk=mk[Ftile].all(1); Ftile=Ftile[fk]
used=np.unique(Ftile); remap=-np.ones(len(Vtile),int); remap[used]=np.arange(len(used))
Vtile=Vtile[used]; Ftile=remap[Ftile]
print(f"Volle Mauer: {len(Vtile)}V / {len(Ftile)}F  Länge {np.ptp(Vtile[:,0]):.0f}m")

# ---- ins Welt-Frame an die Mauerstelle (Krone auf Seespiegel+3,3 m verankern) ----
Zt=Vtile[:,2] + (Z_LAKE+3.3) - (z_floor+Vtile[:,2]).max()
Wx=Ed+Vtile[:,0]*u[0]+Vtile[:,1]*p[0]
Wy=Nd+Vtile[:,0]*u[1]+Vtile[:,1]*p[1]
Wz=z_floor+Zt
dam=trimesh.Trimesh(np.column_stack([Wx,Wy,Wz]),Ftile,process=False)
dam.visual=trimesh.visual.ColorVisuals(dam,face_colors=[150,146,136,255])
dam.export(f"{OUT}/linach_mauer_scan.stl")
print(f"STL: {OUT}/linach_mauer_scan.stl  Krone z={Wz.max():.1f} (See {Z_LAKE})")

# ---- Gelände + Wasser ----
cc0,cc1=col-300,col+130; rr0,rr1=row-180,row+180; st=2
sub=A[rr0:rr1:st,cc0:cc1:st]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1,st)+0.5+E0; Ny_=N0+(ny-1-np.arange(rr0,rr1,st))+0.5
Xg,Yg=np.meshgrid(Ex,Ny_)
Vt=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); Ft2=[]
for i in range(gny-1):
    for j in range(gnx-1):
        a=i*gnx+j; Ft2+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
terr=trimesh.Trimesh(Vt,np.array(Ft2),process=False)
zz=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub))
terr.visual.vertex_colors=(np.array(plt.cm.terrain(zz))*255).astype(np.uint8)
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1:st,cc0:cc1:st]
Vw=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); Fw=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]:
            a=i*gnx+j; Fw+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
water=trimesh.Trimesh(Vw,np.array(Fw),process=False); water.visual.face_colors=[40,110,180,170]

# ---- GLB + HTML ----
sc=trimesh.Scene(); ctr=terr.vertices.mean(0)
for nm,msh in [("gelaende",terr),("wasser",water),("mauer",dam)]:
    mm=msh.copy(); mm.apply_translation(-ctr); sc.add_geometry(mm,geom_name=nm)
glb=sc.export(file_type="glb"); b64=base64.b64encode(glb).decode()
html="""<!doctype html><meta charset=utf-8><title>Linachtalsperre 3D</title>
<style>body{margin:0;background:#0c1116;font-family:system-ui;color:#cdd}#i{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;text-shadow:0 1px 3px #000;line-height:1.4}</style>
<div id=i><b>Linachtalsperre</b> — echtes LGL-Tal + volle Mauer aus <b>Sketchfab-Scan</b> gekachelt (13 Bögen, CC-BY semattes)<br>
<span style=color:#8cf>Maus: drehen · Rad: zoom</span></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type=module>
import*as T from"three";import{OrbitControls}from"three/addons/controls/OrbitControls.js";import{GLTFLoader}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0x0c1116);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,8000);
const rn=new T.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x334455,0.95));const sun=new T.DirectionalLight(0xfff2e0,1.1);sun.position.set(-120,80,160);sc.add(sun);
const b=atob("__B64__");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
new GLTFLoader().parse(ar.buffer,"",g=>{const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const bb=new T.Box3().setFromObject(o),cc=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(cc);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.5,d*0.45,d*0.8);cam.lookAt(0,0,0);ct.update();},
 e=>{document.getElementById("i").innerHTML+="<br><span style=color:#f88>LOAD "+e+"</span>";});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam);})();
</script>""".replace("__B64__",b64)
open(f"{OUT}/linach_voll.html","w").write(html)
print(f"HTML: {OUT}/linach_voll.html ({len(html)//1024} kB)")

# ---- Render: schattierte Eigen-Frame-Ansicht (Bögen sichtbar) ----
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
rv,rf=fs.simplify(Vtile.astype(np.float32),Ftile.astype(np.int32),target_reduction=0.85)  # ~20k fürs Plotten
Zr=rv[:,2]+(Z_LAKE+3.3)-(z_floor+Vtile[:,2]).max()
tri=np.column_stack([rv[:,0],rv[:,1],z_floor+Zr])[rf]
def shade(tr):
    n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]); n=n/np.clip(np.linalg.norm(n,axis=1,keepdims=True),1e-9,None)
    lt=np.array([0.3,-0.6,0.75]); lt/=np.linalg.norm(lt)
    return np.array([0.66,0.64,0.58])[None,:]*(0.35+0.65*np.clip(np.abs(n@lt),0,1))[:,None]
fig=plt.figure(figsize=(15,6)); ax=fig.add_subplot(111,projection='3d')
ax.add_collection3d(Poly3DCollection(tri,facecolors=shade(tri),edgecolor='none'))
ax.set_xlim(-L/2-3,L/2+3); ax.set_ylim(-DEPTH*0.6,DEPTH+3); ax.set_zlim(z_floor-1,z_floor+30)
ax.set_box_aspect((L,(DEPTH+25)*1.6,25*1.6)); ax.view_init(elev=11,azim=-84)
ax.set_title("Volle Linachtalsperre aus Scan gekachelt — 13 Bögen, 143×25 m (Luftseite)")
ax.set_xlabel("Länge m"); ax.set_zlabel("m"); ax.set_yticks([])
plt.tight_layout(); plt.savefig("daten/linach/linach_voll_3d.png",dpi=115); print("Render: daten/linach/linach_voll_3d.png")

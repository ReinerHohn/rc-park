#!/usr/bin/env python3
"""linach_scan_place.py — Sketchfab-SCAN (Bogen 1+2, CC-BY semattes) an die echte
Mauerstelle ins LGL-Tal setzen. KEINE parametrische Mauer. Export GLB + 3D-HTML.
"""
import os, base64, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

SCAN="daten/linach/sketchfab/source/Flug 2 - Bogen 1 + 2_simplified_3d_mesh.obj"
DEM="daten/linach/linach_dem.npy"; ORIG="daten/linach/linach_dem_origin.npy"
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)

A=np.load(DEM); E0,N0=np.load(ORIG); ny,nx=A.shape
col=int(round(Ed-0.5-E0)); ri=int(round(Nd-0.5-N0)); row=ny-1-ri
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[row-25:row+26,col-25:col+26].mean(),-gy[row-25:row+26,col-25:col+26].mean()]); p/=np.hypot(*p)
u=np.array([-p[1],p[0]])
def px_pp(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
z_floor=float(np.nanmin([px_pp(t,30.0) for t in np.linspace(-70,70,60)]))

# ---- Scan laden + ausrichten ----
scan=trimesh.load(SCAN,process=False)
if hasattr(scan,'geometry'): scan=trimesh.util.concatenate(list(scan.geometry.values()))
V=scan.vertices.copy()
# Wandachse im Scan = Haupt-Streurichtung in XY (PCA)
xy=V[:,:2]-V[:,:2].mean(0)
w,vec=np.linalg.eigh(np.cov(xy.T)); wall=vec[:,np.argmax(w)]; wall/=np.hypot(*wall)
# Rotation um Z: wall -> u
ang=np.arctan2(u[1],u[0])-np.arctan2(wall[1],wall[0])
ca,sa=np.cos(ang),np.sin(ang)
Rz=np.array([[ca,-sa,0],[sa,ca,0],[0,0,1.0]])
Vc=V-V.mean(0); Vr=Vc@Rz.T
# platzieren: XY-Zentrum -> Mauer, Basis -> Talsohle
Vr[:,0]+=Ed; Vr[:,1]+=Nd; Vr[:,2]+=z_floor-Vr[:,2].min()
scan.vertices=Vr
scan.visual=trimesh.visual.ColorVisuals(scan, face_colors=[150,146,136,255])
print(f"Scan platziert: Krone z={Vr[:,2].max():.1f}m (See {Z_LAKE}, Talsohle {z_floor:.1f})")

# ---- Gelände + Wasser (Fenster) ----
cc0,cc1=col-300,col+130; rr0,rr1=row-180,row+180; st=2
sub=A[rr0:rr1:st,cc0:cc1:st]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1,st)+0.5+E0; Ny_=N0+(ny-1-np.arange(rr0,rr1,st))+0.5
Xg,Yg=np.meshgrid(Ex,Ny_)
Vt=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); Ft=[]
for i in range(gny-1):
    for j in range(gnx-1):
        a=i*gnx+j; Ft+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
terr=trimesh.Trimesh(Vt,np.array(Ft),process=False)
zz=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub))
terr.visual.vertex_colors=(np.array(plt.cm.terrain(zz))*255).astype(np.uint8)
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1:st,cc0:cc1:st]
Vw=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); Fw=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]:
            a=i*gnx+j; Fw+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
water=trimesh.Trimesh(Vw,np.array(Fw),process=False); water.visual.face_colors=[40,110,180,170]

# ---- Scan fürs Web verkleinern ----
web=scan.copy()
try:
    web=web.simplify_quadric_decimation(180000); print(f"Scan web-decimiert -> {len(web.faces)}F")
except Exception as ex:
    print("Decimation n/a (",ex,") -> volles Mesh");
web.visual=trimesh.visual.ColorVisuals(web,face_colors=[150,146,136,255])

# ---- GLB + HTML ----
sc=trimesh.Scene(); ctr=terr.vertices.mean(0)
for nm,m in [("gelaende",terr),("wasser",water),("mauer_scan",web)]:
    mm=m.copy(); mm.apply_translation(-ctr); sc.add_geometry(mm,geom_name=nm)
glb=sc.export(file_type="glb"); b64=base64.b64encode(glb).decode()
html="""<!doctype html><meta charset=utf-8><title>Linachtalsperre 3D (Scan)</title>
<style>body{margin:0;background:#0c1116;font-family:system-ui;color:#cdd}#i{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;text-shadow:0 1px 3px #000;line-height:1.4}</style>
<div id=i><b>Linachtalsperre</b> — echtes LGL-Tal + <b>Sketchfab-Scan</b> (Bogen 1+2, CC-BY semattes)<br>
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
 const bb=new T.Box3().setFromObject(o),c=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(c);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.5,d*0.45,d*0.8);cam.lookAt(0,0,0);ct.update();},
 e=>{document.getElementById("i").innerHTML+="<br><span style=color:#f88>LOAD "+e+"</span>";});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam);})();
</script>""".replace("__B64__",b64)
open(f"{OUT}/linach_scan.html","w").write(html)
print(f"HTML: {OUT}/linach_scan.html ({len(html)//1024} kB)")

# ---- Schneller Render zum Verifizieren ----
fig=plt.figure(figsize=(12,8)); ax=fig.add_subplot(111,projection='3d')
ax.plot_surface(Xg-Ed,Yg-Nd,sub,cmap='terrain',alpha=0.7,linewidth=0,antialiased=False,rcount=80,ccount=80)
Wz=np.where(lake,Z_LAKE,np.nan); ax.plot_surface(Xg-Ed,Yg-Nd,Wz,color='#2a6fb0',alpha=0.5,linewidth=0,rcount=80,ccount=80)
sv=scan.vertices[::40]
ax.scatter(sv[:,0]-Ed,sv[:,1]-Nd,sv[:,2],s=1,c='#555',alpha=0.5)
ax.set_box_aspect((1,1,0.45)); ax.view_init(elev=28,azim=-118)
ax.set_title("Sketchfab-Scan (Bogen 1+2) an der echten Mauerstelle im LGL-Tal")
ax.set_xlabel("Ost m"); ax.set_ylabel("Nord m")
plt.tight_layout(); plt.savefig("daten/linach/linach_scan_3d.png",dpi=110); print("Render: daten/linach/linach_scan_3d.png")

#!/usr/bin/env python3
"""linach_scene.py — HYBRID-Mauer (feiner + Detail) + Scan-Farben, gesetzt ins
echte LGL-Tal mit Stausee. Export Szene-GLB + HTML + heller Render.
Detail-Upgrade vs linach_dam_fine: feinere Gewölbe, Wandscheiben mit Kappe,
Krone mit Geländer-Pfosten, dezente Oberflächen-Unruhe.
"""
import os, base64, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter

L,H,N=143.0,25.0,13; P=L/N; S=10.8
R=7.0; A=np.arcsin((S/2)/R); TSH=1.1; LEAN=0.10
DB=14.0; TB=2.2
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)
rng=np.random.default_rng(1)

def thick_surface(G0,G1):
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

def box(x0,x1,y0,y1,z0,z1):
    b=trimesh.creation.box(bounds=[[x0,y0,z0],[x1,y1,z1]]); return b

parts=[]
nT,nZ=46,34                                      # feiner
for k in range(N):                               # Gewölbe + feine Rand-Rippe
    Xc=-L/2+(k+0.5)*P
    th=np.linspace(-A,A,nT); zs=np.linspace(0,H,nZ)
    Pin=np.zeros((nZ,nT,3)); Pout=np.zeros((nZ,nT,3))
    for iz,z in enumerate(zs):
        yoff=LEAN*z
        # dezente Oberflächen-Unruhe (vertikale Schalbretter + leichtes Rauschen)
        for it,a in enumerate(th):
            rough=0.04*np.sin(z*2.6)+0.03*rng.standard_normal()
            X=Xc+R*np.sin(a); Y=(R-R*np.cos(a))+yoff+rough
            Pin[iz,it]=[X,Y,z]; Pout[iz,it]=[X,Y+TSH,z]
    parts.append(thick_surface(Pin,Pout))

for k in range(N+1):                             # Wandscheiben: Wand + Kappe
    Xs=-L/2+k*P
    prof=[(LEAN*H,H),(0.0,0.0),(DB,0.0),(DB,H*0.34)]
    Vb=[]
    for s in (-TB/2,TB/2):
        for (Y,Z) in prof:
            wid=s*(1.0+0.18*(1-Z/H))             # Böschung unten breiter
            Vb.append([Xs+wid,Y,Z])
    Fb=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    parts.append(trimesh.Trimesh(np.array(Vb),np.array(Fb),process=True))
    parts.append(box(Xs-TB/2-0.2,Xs+TB/2+0.2, LEAN*H-0.3, 2.2, H-0.4, H+0.2))  # Kappe oben

# Krone-Fahrbahn
Gb=np.zeros((2,220,3)); Gt=np.zeros((2,220,3))
for j,x in enumerate(np.linspace(-L/2,L/2,220)):
    Gb[0,j]=[x,LEAN*H-0.6,H]; Gb[1,j]=[x,LEAN*H+2.8,H]
    Gt[0,j]=[x,LEAN*H-0.6,H+0.9]; Gt[1,j]=[x,LEAN*H+2.8,H+0.9]
parts.append(thick_surface(Gb,Gt))
# Geländer: Handlauf + Pfosten (Feindetail)
yR=LEAN*H+2.75
parts.append(box(-L/2,L/2, yR-0.1,yR+0.1, H+1.9,H+2.1))        # Handlauf
for x in np.arange(-L/2+1,L/2,2.2):                             # Pfosten alle 2,2 m
    parts.append(box(x-0.08,x+0.08, yR-0.08,yR+0.08, H+0.9,H+2.0))

dam=trimesh.util.concatenate(parts)
print(f"Mauer (detailliert): {len(dam.vertices)}V/{len(dam.faces)}F  watertight={dam.is_watertight}")

# ---- Scan-Farben übertragen ----
s=trimesh.load('daten/linach/sketchfab_gltf/scene.gltf',process=False)
SV=[]; SC=[]
for g in s.geometry.values():
    SV.append(np.asarray(g.vertices)); SC.append(g.visual.to_color().vertex_colors[:,:3])
SV=np.vstack(SV); SC=np.vstack(SC).astype(float)
zz=SV[:,2]; hi=SV[zz>np.percentile(zz,60)]; c=hi[:,:2].mean(0)
w,vec=np.linalg.eigh(np.cov((hi[:,:2]-c).T)); wa=vec[:,np.argmax(w)]
xs=(SV[:,:2]-c)@wa; xn=(xs-xs.min())/np.ptp(xs); zn=(zz-zz.min())/np.ptp(zz)
tree=cKDTree(np.column_stack([xn,zn]))
V=dam.vertices; xb=((V[:,0]+L/2)%P)/P; znp=np.clip(V[:,2]/(H+2.1),0,1)
_,idx=tree.query(np.column_stack([xb,znp]),k=6)
col=np.clip(SC[idx].mean(1)+SC[idx].std(1)*rng.normal(0,0.25,(len(V),3)),0,255)
dam.visual.vertex_colors=np.column_stack([col,np.full(len(col),255)]).astype(np.uint8)
dam.export(f"{OUT}/linach_hybrid_detail.stl")

# ---- ins LGL-Tal setzen ----
A2=np.load("daten/linach/linach_dem.npy"); E0,N0=np.load("daten/linach/linach_dem_origin.npy"); ny,nx=A2.shape
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
col0=int(round(Ed-0.5-E0)); row0=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A2,6); gy,gx=np.gradient(-sm)
p=np.array([gx[row0-25:row0+26,col0-25:col0+26].mean(),-gy[row0-25:row0+26,col0-25:col0+26].mean()]); p/=np.hypot(*p)
u=np.array([-p[1],p[0]])
def px_pp(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A2[rr,cc]
z_floor=float(np.nanmin([px_pp(t,30.0) for t in np.linspace(-70,70,60)]))
Vd=dam.vertices.copy()
zt=Vd[:,2]+(Z_LAKE+3.3)-(z_floor+Vd[:,2].max())
Wx=Ed+Vd[:,0]*u[0]+Vd[:,1]*p[0]; Wy=Nd+Vd[:,0]*u[1]+Vd[:,1]*p[1]; Wz=z_floor+zt
damw=trimesh.Trimesh(np.column_stack([Wx,Wy,Wz]),dam.faces,process=False)
damw.visual.vertex_colors=dam.visual.vertex_colors

# Gelände + Wasser
cc0,cc1=col0-300,col0+130; rr0,rr1=row0-180,row0+180; st=2
sub=A2[rr0:rr1:st,cc0:cc1:st]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1,st)+0.5+E0; Ny_=N0+(ny-1-np.arange(rr0,rr1,st))+0.5
Xg,Yg=np.meshgrid(Ex,Ny_)
Vt=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); Ft=[]
for i in range(gny-1):
    for j in range(gnx-1):
        a=i*gnx+j; Ft+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
terr=trimesh.Trimesh(Vt,np.array(Ft),process=False)
znn=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub))
terr.visual.vertex_colors=(np.array(plt.cm.terrain(znn))*255).astype(np.uint8)
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1:st,cc0:cc1:st]
Vw=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); Fw=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]:
            a=i*gnx+j; Fw+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
water=trimesh.Trimesh(Vw,np.array(Fw),process=False); water.visual.face_colors=[40,110,180,165]

sc=trimesh.Scene(); ctr=terr.vertices.mean(0)
for nm,msh in [("gelaende",terr),("wasser",water),("mauer",damw)]:
    mm=msh.copy(); mm.apply_translation(-ctr); sc.add_geometry(mm,geom_name=nm)
glb=sc.export(file_type="glb"); b64=base64.b64encode(glb).decode()
html="""<!doctype html><meta charset=utf-8><title>Linachtalsperre im Tal</title>
<style>body{margin:0;background:#9fb3c8;font-family:system-ui;color:#123}#i{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;line-height:1.4;text-shadow:0 1px 2px #fff}</style>
<div id=i><b>Linachtalsperre</b> — Hybrid-Mauer im echten LGL-Tal + Stausee<br><span style=color:#024>Maus drehen · Rad zoom</span></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type=module>
import*as T from"three";import{OrbitControls}from"three/addons/controls/OrbitControls.js";import{GLTFLoader}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0x9fb3c8);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,8000);
const rn=new T.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x556,1.0));const sun=new T.DirectionalLight(0xfff4e6,1.05);sun.position.set(-120,140,120);sc.add(sun);
const b=atob("__B64__");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
new GLTFLoader().parse(ar.buffer,"",g=>{g.scene.traverse(o=>{if(o.material){o.material.vertexColors=true;o.material.roughness=0.95;o.material.metalness=0;}});
 const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const bb=new T.Box3().setFromObject(o),cc=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(cc);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.45,d*0.4,d*0.8);cam.lookAt(0,0,0);ct.update();});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam);})();
</script>""".replace("__B64__",b64)
open(f"{OUT}/linach_szene.html","w").write(html)
print(f"Szene-HTML: {OUT}/linach_szene.html ({len(html)//1024} kB)")

# ---- Render: Mauer-Detail + Szene ----
def lam(tr,amb=0.66):
    n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]); n=n/np.clip(np.linalg.norm(n,axis=1,keepdims=True),1e-9,None)
    lt=np.array([0.35,-0.55,0.75]); lt/=np.linalg.norm(lt); return amb+0.4*np.clip(n@lt,0,1)
fig=plt.figure(figsize=(16,7),facecolor='white')
tri=dam.vertices[dam.faces]; fc=dam.visual.vertex_colors[dam.faces,:3].mean(1)/255.0
ax=fig.add_subplot(121,projection='3d',facecolor='white')
ax.add_collection3d(Poly3DCollection(tri,facecolors=np.clip(fc*lam(tri)[:,None],0,1),edgecolor='none'))
ax.set_xlim(-L/2-3,L/2+3); ax.set_ylim(-4,17); ax.set_zlim(0,H+4); ax.set_box_aspect((L,(14+H)*1.3,H*1.3))
ax.view_init(elev=20,azim=-60); ax.set_title("Hybrid-Mauer (detaillierter) — Luftseite",fontsize=11); ax.set_yticks([]); ax.set_xlabel("Länge m"); ax.set_zlabel("m")
for pa in (ax.xaxis,ax.yaxis,ax.zaxis): pa.pane.set_facecolor((1,1,1,0))
axB=fig.add_subplot(122,projection='3d',facecolor='white')
axB.plot_surface(Xg-Ed,Yg-Nd,sub,cmap='terrain',alpha=0.8,linewidth=0,antialiased=False,rcount=80,ccount=80)
axB.plot_surface(Xg-Ed,Yg-Nd,np.where(lake,Z_LAKE,np.nan),color='#2a6fb0',alpha=0.5,linewidth=0,rcount=80,ccount=80)
dt=damw.vertices[damw.faces].copy(); dt[:,:,0]-=Ed; dt[:,:,1]-=Nd
axB.add_collection3d(Poly3DCollection(dt,facecolors=np.clip(fc*lam(dt,0.7)[:,None],0,1),edgecolor='none'))
axB.set_box_aspect((1,1,0.5)); axB.view_init(elev=30,azim=-118); axB.set_title("im echten Tal + Stausee",fontsize=11); axB.set_xlabel("Ost m"); axB.set_ylabel("Nord m")
plt.tight_layout(); plt.savefig("daten/linach/linach_szene.png",dpi=120,facecolor='white'); print("Render: daten/linach/linach_szene.png")

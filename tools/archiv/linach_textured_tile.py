#!/usr/bin/env python3
"""linach_textured_tile.py — ECHTE Scan-Geometrie (texturiert, Bogen 6) auf die
volle 143-m-Mauer SPIEGEL-KACHELN, mit UV/Textur-Erhalt, ins LGL-Tal setzen.
Maximales Detail (Fotogrammetrie) + echte Foto-Textur. GLB + HTML.
"""
import os, base64, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from PIL import Image
from scipy.ndimage import gaussian_filter

L,N=143.0,13; BAY=L/N
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)

# ---- texturiertes glTF laden, zu EINEM Mesh mit gemeinsamer Textur ----
s=trimesh.load('daten/linach/sketchfab_gltf/scene.gltf',process=False)
geoms=list(s.geometry.values())
img=geoms[0].visual.material.baseColorTexture.convert("RGB").resize((2048,2048))
Vs=[];Fs=[];UV=[];off=0
for g in geoms:
    Vs.append(np.asarray(g.vertices)); Fs.append(np.asarray(g.faces)+off)
    UV.append(np.asarray(g.visual.uv)); off+=len(g.vertices)
V=np.vstack(Vs); F=np.vstack(Fs); uv=np.vstack(UV)
print(f"Scan: {len(V)}V / {len(F)}F  (texturiert)")

# ---- Krone-Frame ----
z=V[:,2]; hi=V[z>np.percentile(z,60)]; c=hi[:,:2].mean(0)
w,vec=np.linalg.eigh(np.cov((hi[:,:2]-c).T)); wa=vec[:,np.argmax(w)]; pa=np.array([-wa[1],wa[0]])
Xl=(V[:,:2]-c)@wa; Yl=(V[:,:2]-c)@pa; Zl=z-z.min()
ycrest=np.median(Yl[z>np.percentile(z,88)])
side=+1 if Zl[Yl>ycrest].min()<Zl[Yl<ycrest].min() else -1
Yd=side*(Yl-ycrest)
Xc0=np.median(Xl)
Vl=np.column_stack([Xl-Xc0,Yd,Zl])                 # lokales Dam-Frame

# ---- Dam-Band croppen (Gelände/Reservoir weg), Textur behalten ----
sel=(Yd>-6)&(Yd<16)&(np.abs(Xl-Xc0)<BAY*0.95)      # EIN sauberer Bogen (~11m)
fm=sel[F].all(1); Fu=F[fm]
usedv=np.unique(Fu); remap=-np.ones(len(V),int); remap[usedv]=np.arange(len(usedv))
uV=Vl[usedv]; uUV=uv[usedv]; uF=remap[Fu]
WUNIT=np.ptp(uV[:,0]); uV[:,0]-=uV[:,0].mean()
print(f"Bogen-Einheit: {len(uF)}F  Breite {WUNIT:.1f}m")

# ---- SPIEGEL-KACHELN auf 143 m (UV mit) ----
allV=[];allF=[];allUV=[];base=0
K=int(np.ceil(L/WUNIT/2))+1
for k in range(-K,K+1):
    cx=k*WUNIT
    if abs(cx)>L/2+WUNIT*0.6: continue
    Vk=uV.copy(); Vk[:,0]=(-Vk[:,0] if k%2 else Vk[:,0])+cx
    Fk=uF[:,::-1] if k%2 else uF
    allV.append(Vk); allUV.append(uUV); allF.append(Fk+base); base+=len(Vk)
TV=np.vstack(allV); TF=np.vstack(allF); TUV=np.vstack(allUV)
print(f"Volle Mauer: {len(TV)}V / {len(TF)}F  Länge {np.ptp(TV[:,0]):.0f}m")

# ---- ins LGL-Tal ----
A=np.load("daten/linach/linach_dem.npy"); E0,N0=np.load("daten/linach/linach_dem_origin.npy"); ny,nx=A.shape
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
col0=int(round(Ed-0.5-E0)); row0=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[row0-25:row0+26,col0-25:col0+26].mean(),-gy[row0-25:row0+26,col0-25:col0+26].mean()]); p/=np.hypot(*p)
u=np.array([-p[1],p[0]])
def px_pp(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
z_floor=float(np.nanmin([px_pp(t,30.0) for t in np.linspace(-70,70,60)]))
zt=TV[:,2]+(Z_LAKE+3.3)-(z_floor+TV[:,2].max())
Wx=Ed+TV[:,0]*u[0]+TV[:,1]*p[0]; Wy=Nd+TV[:,0]*u[1]+TV[:,1]*p[1]; Wz=z_floor+zt
dam=trimesh.Trimesh(np.column_stack([Wx,Wy,Wz]),TF,process=False)
dam.visual=trimesh.visual.TextureVisuals(uv=TUV,image=img)
dam.export(f"{OUT}/linach_textur.glb")

# ---- Gelände + Wasser ----
cc0,cc1=col0-300,col0+130; rr0,rr1=row0-180,row0+180; st=2
sub=A[rr0:rr1:st,cc0:cc1:st]; gny,gnx=sub.shape
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
for nm,msh in [("gelaende",terr),("wasser",water),("mauer",dam)]:
    mm=msh.copy(); mm.apply_translation(-ctr); sc.add_geometry(mm,geom_name=nm)
glb=sc.export(file_type="glb"); b64=base64.b64encode(glb).decode()
html="""<!doctype html><meta charset=utf-8><title>Linachtalsperre texturiert</title>
<style>body{margin:0;background:#9fb3c8;font-family:system-ui;color:#123}#i{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;line-height:1.4;text-shadow:0 1px 2px #fff}</style>
<div id=i><b>Linachtalsperre</b> — echte Scan-Geometrie+Textur, auf 13 Bögen gekachelt, im LGL-Tal<br><span style=color:#024>Maus drehen · Rad zoom</span></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type=module>
import*as T from"three";import{OrbitControls}from"three/addons/controls/OrbitControls.js";import{GLTFLoader}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0x9fb3c8);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,8000);
const rn=new T.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x556,1.15));const sun=new T.DirectionalLight(0xfff4e6,1.0);sun.position.set(-120,140,120);sc.add(sun);
const b=atob("__B64__");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
new GLTFLoader().parse(ar.buffer,"",g=>{const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const bb=new T.Box3().setFromObject(o),cc=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(cc);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.4,d*0.4,d*0.8);cam.lookAt(0,0,0);ct.update();});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam);})();
</script>""".replace("__B64__",b64)
open(f"{OUT}/linach_textur.html","w").write(html)
print(f"HTML: {OUT}/linach_textur.html ({len(html)//1024} kB)")

# ---- matplotlib-Vorschau mit Vertex-Farben aus Textur ----
tc=trimesh.visual.uv_to_color(TUV,img)[:, :3]/255.0
tri=dam.vertices[dam.faces]; fc=tc[dam.faces].mean(1)
Vl2=np.column_stack([TV[:,0],TV[:,1],z_floor+zt])
trL=Vl2[dam.faces]
def lam(tr):
    n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]); n=n/np.clip(np.linalg.norm(n,axis=1,keepdims=True),1e-9,None)
    lt=np.array([0.35,-0.55,0.75]); lt/=np.linalg.norm(lt); return 0.7+0.4*np.clip(n@lt,0,1)
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
fig=plt.figure(figsize=(15,6),facecolor='white'); ax=fig.add_subplot(111,projection='3d',facecolor='white')
ax.add_collection3d(Poly3DCollection(trL,facecolors=np.clip(fc*lam(trL)[:,None],0,1),edgecolor='none'))
ax.set_xlim(-L/2-3,L/2+3); ax.set_ylim(-6,16); ax.set_zlim(z_floor,z_floor+28); ax.set_box_aspect((L,22*1.3,25*1.3))
ax.view_init(elev=14,azim=-82); ax.set_title("Echte Scan-Geometrie+Textur, 13 Bögen gekachelt (Luftseite)",fontsize=11); ax.set_yticks([])
for pq in (ax.xaxis,ax.yaxis,ax.zaxis): pq.pane.set_facecolor((1,1,1,0))
plt.tight_layout(); plt.savefig("daten/linach/linach_textur.png",dpi=120,facecolor='white'); print("Render: daten/linach/linach_textur.png")

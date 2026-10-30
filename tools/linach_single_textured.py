#!/usr/bin/env python3
"""linach_single_textured.py — EIN Bogen in vollem Scan-Detail + Foto-Textur,
sauber ins LGL-Tal gesetzt (Textur 2048). Zeigt die echte Detail-Obergrenze.
"""
import os, base64, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
OUT="modelle/linachtalsperre"

s=trimesh.load('daten/linach/sketchfab_gltf/scene.gltf',process=False)
geoms=list(s.geometry.values())
img=geoms[0].visual.material.baseColorTexture.convert("RGB").resize((2048,2048))
Vs=[];Fs=[];UV=[];off=0
for g in geoms:
    Vs.append(np.asarray(g.vertices)); Fs.append(np.asarray(g.faces)+off); UV.append(np.asarray(g.visual.uv)); off+=len(g.vertices)
V=np.vstack(Vs); F=np.vstack(Fs); uv=np.vstack(UV)

# Krone-Frame -> u/p/z
z=V[:,2]; hi=V[z>np.percentile(z,60)]; c=hi[:,:2].mean(0)
w,vec=np.linalg.eigh(np.cov((hi[:,:2]-c).T)); wa=vec[:,np.argmax(w)]; pa=np.array([-wa[1],wa[0]])
Xl=(V[:,:2]-c)@wa; Yl=(V[:,:2]-c)@pa; Zl=z-z.min()
ycrest=np.median(Yl[z>np.percentile(z,88)]); side=+1 if Zl[Yl>ycrest].min()<Zl[Yl<ycrest].min() else -1
Yd=side*(Yl-ycrest); Xl=Xl-np.median(Xl)

A=np.load("daten/linach/linach_dem.npy"); E0,N0=np.load("daten/linach/linach_dem_origin.npy"); ny,nx=A.shape
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
col0=int(round(Ed-0.5-E0)); row0=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[row0-25:row0+26,col0-25:col0+26].mean(),-gy[row0-25:row0+26,col0-25:col0+26].mean()]); p/=np.hypot(*p); u=np.array([-p[1],p[0]])
def px_pp(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
z_floor=float(np.nanmin([px_pp(t,30.0) for t in np.linspace(-30,30,40)]))
zt=Zl+(Z_LAKE+3.3)-(z_floor+Zl.max())
Wx=Ed+Xl*u[0]+Yd*p[0]; Wy=Nd+Xl*u[1]+Yd*p[1]; Wz=z_floor+zt
dam=trimesh.Trimesh(np.column_stack([Wx,Wy,Wz]),F,process=False)
dam.visual=trimesh.visual.TextureVisuals(uv=uv,image=img)
print(f"Ein Bogen: {len(F)}F, texturiert")

# Gelände + Wasser (enger ums Bauwerk)
cc0,cc1=col0-120,col0+90; rr0,rr1=row0-90,row0+90; st=1
sub=A[rr0:rr1:st,cc0:cc1:st]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1,st)+0.5+E0; Ny_=N0+(ny-1-np.arange(rr0,rr1,st))+0.5
Xg,Yg=np.meshgrid(Ex,Ny_)
Vt=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); Ft=[]
for i in range(gny-1):
    for j in range(gnx-1):
        a=i*gnx+j; Ft+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
terr=trimesh.Trimesh(Vt,np.array(Ft),process=False)
znn=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub)); terr.visual.vertex_colors=(np.array(plt.cm.terrain(znn))*255).astype(np.uint8)
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1:st,cc0:cc1:st]
Vw=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); Fw=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]:
            a=i*gnx+j; Fw+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
water=trimesh.Trimesh(Vw,np.array(Fw),process=False); water.visual.face_colors=[40,110,180,165]

sc=trimesh.Scene(); ctr=terr.vertices.mean(0)
for nm,m in [("gelaende",terr),("wasser",water),("mauer",dam)]:
    mm=m.copy(); mm.apply_translation(-ctr); sc.add_geometry(mm,geom_name=nm)
glb=sc.export(file_type="glb"); b64=base64.b64encode(glb).decode()
html="""<!doctype html><meta charset=utf-8><title>Linach Bogen (voll texturiert)</title>
<style>body{margin:0;background:#9fb3c8;font-family:system-ui;color:#123}#i{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;line-height:1.4;text-shadow:0 1px 2px #fff}</style>
<div id=i><b>Linachtalsperre</b> — EIN Bogen, volles Scan-Detail + Foto-Textur, im LGL-Tal<br><span style=color:#024>Maus drehen · Rad zoom</span></div>
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
open(f"{OUT}/linach_bogen.html","w").write(html)
print(f"HTML: {OUT}/linach_bogen.html ({len(html)//1024} kB)")

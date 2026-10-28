#!/usr/bin/env python3
"""linach_render.py — VOLLES Detail als Bild: echte Scan-Geometrie+Textur auf 13
Bögen gekachelt, im LGL-Tal+See, GPU-offscreen fotorealistisch gerendert (open3d).
Dateigröße egal, weil Ausgabe = PNG.
"""
import numpy as np, trimesh, open3d as o3d
from scipy.ndimage import gaussian_filter
rend=o3d.visualization.rendering

L,N=143.0,13; BAY=L/N

# ---- texturierten Scan -> Dam-Band -> Spiegel-Kacheln (lokal) ----
s=trimesh.load('daten/linach/sketchfab_gltf/scene.gltf',process=False)
geoms=list(s.geometry.values())
img=np.ascontiguousarray(np.asarray(geoms[0].visual.material.baseColorTexture.convert('RGB')))
Vs=[];Fs=[];UV=[];off=0
for g in geoms:
    Vs.append(np.asarray(g.vertices)); Fs.append(np.asarray(g.faces)+off); UV.append(np.asarray(g.visual.uv)); off+=len(g.vertices)
V=np.vstack(Vs); F=np.vstack(Fs); uv=np.vstack(UV)
z=V[:,2]; hi=V[z>np.percentile(z,60)]; c=hi[:,:2].mean(0)
w,vec=np.linalg.eigh(np.cov((hi[:,:2]-c).T)); wa=vec[:,np.argmax(w)]; pa=np.array([-wa[1],wa[0]])
Xl=(V[:,:2]-c)@wa; Yl=(V[:,:2]-c)@pa; Zl=z-z.min()
ycrest=np.median(Yl[z>np.percentile(z,88)]); side=+1 if Zl[Yl>ycrest].min()<Zl[Yl<ycrest].min() else -1
Yd=side*(Yl-ycrest); Xl=Xl-np.median(Xl)
sel=(Yd>-4)&(Yd<18)&(np.abs(Xl)<BAY/2)          # GENAU EIN Bogen (Pfeiler zu Pfeiler)
fm=sel[F].all(1); Fu=F[fm]; usedv=np.unique(Fu); remap=-np.ones(len(V),int); remap[usedv]=np.arange(len(usedv))
uV=np.column_stack([Xl,Yd,Zl])[usedv]; uUV=uv[usedv]; uF=remap[Fu]
WUNIT=BAY; uV[:,0]-=np.median(uV[:,0])          # am echten Bogenabstand 11 m kacheln
allV=[];allF=[];allUV=[];base=0; K=int(np.ceil(L/WUNIT/2))+1
for k in range(-K,K+1):
    cx=k*WUNIT
    if abs(cx)>L/2+WUNIT*0.6: continue
    Vk=uV.copy(); Vk[:,0]=(-Vk[:,0] if k%2 else Vk[:,0])+cx
    allV.append(Vk); allUV.append(uUV); allF.append((uF[:,::-1] if k%2 else uF)+base); base+=len(Vk)
TV=np.vstack(allV); TF=np.vstack(allF); TUV=np.vstack(allUV)
print(f"Mauer: {len(TF)}F  Länge {np.ptp(TV[:,0]):.0f}m")

# ---- Welt-Frame ----
A=np.load("daten/linach/linach_dem.npy"); E0,N0=np.load("daten/linach/linach_dem_origin.npy"); ny,nx=A.shape
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
col0=int(round(Ed-0.5-E0)); row0=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[row0-25:row0+26,col0-25:col0+26].mean(),-gy[row0-25:row0+26,col0-25:col0+26].mean()]); p/=np.hypot(*p); u=np.array([-p[1],p[0]])
def px_pp(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
z_floor=float(np.nanmin([px_pp(t,30.0) for t in np.linspace(-70,70,60)]))
zt=TV[:,2]+(Z_LAKE+3.3)-(z_floor+TV[:,2].max())
DW=np.column_stack([Ed+TV[:,0]*u[0]+TV[:,1]*p[0], Nd+TV[:,0]*u[1]+TV[:,1]*p[1], z_floor+zt])

# ---- Gelände + Wasser ----
cc0,cc1=col0-260,col0+120; rr0,rr1=row0-170,row0+170; st=1
sub=A[rr0:rr1:st,cc0:cc1:st]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1,st)+0.5+E0; Ny_=N0+(ny-1-np.arange(rr0,rr1,st))+0.5
Xg,Yg=np.meshgrid(Ex,Ny_)
TVt=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); TFt=[]
for i in range(gny-1):
    for j in range(gnx-1):
        a=i*gnx+j; TFt+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
TFt=np.array(TFt)
import matplotlib.pyplot as plt
znn=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub)); terrcol=np.array(plt.cm.terrain(znn))[:,:3]
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1:st,cc0:cc1:st]
Fw=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]:
            a=i*gnx+j; Fw+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
VW=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); Fw=np.array(Fw)

# ---- open3d Szene ----
def o3dmesh(Vx,Fx,uvx=None,vcol=None):
    m=o3d.geometry.TriangleMesh(); m.vertices=o3d.utility.Vector3dVector(Vx); m.triangles=o3d.utility.Vector3iVector(Fx)
    if uvx is not None:
        m.triangle_uvs=o3d.utility.Vector2dVector(uvx[Fx].reshape(-1,2)); m.textures=[o3d.geometry.Image(img)]
        m.triangle_material_ids=o3d.utility.IntVector(np.zeros(len(Fx),np.int32))
    if vcol is not None: m.vertex_colors=o3d.utility.Vector3dVector(vcol)
    m.compute_vertex_normals(); return m
dam=o3dmesh(DW,TF,uvx=TUV); terr=o3dmesh(TVt,TFt,vcol=terrcol); wat=o3dmesh(VW,Fw,vcol=np.tile([0.16,0.42,0.70],(len(VW),1)))

def render(name,eye,up=[0,0,1],W=1800,Hh=1150):
    r=rend.OffscreenRenderer(W,Hh); r.scene.set_background([0.60,0.70,0.82,1])
    mt=rend.MaterialRecord(); mt.shader='defaultLit'; mt.albedo_img=o3d.geometry.Image(img); r.scene.add_geometry('dam',dam,mt)
    mg=rend.MaterialRecord(); mg.shader='defaultLit'; r.scene.add_geometry('terr',terr,mg)
    mw=rend.MaterialRecord(); mw.shader='defaultLit'; mw.base_color=[0.16,0.42,0.70,1]; r.scene.add_geometry('wat',wat,mw)
    r.scene.scene.set_sun_light([-.4,.5,-.9],[1,1,.96],95000); r.scene.scene.enable_sun_light(True)
    r.scene.scene.set_indirect_light_intensity(45000)
    ctr=np.array([Ed,Nd,z_floor+10.0])
    r.setup_camera(45,ctr,ctr+np.array(eye),up)
    o3d.io.write_image(name,r.render_to_image()); print("->",name)

p3=np.array([p[0],p[1],0.0]); u3=np.array([u[0],u[1],0.0])
# Luftseite 3/4 (downstream = +p), erhöht
render("daten/linach/linach_hero.png", list(p3*150+np.array([0,0,95])+u3*40))
# Weiter Talblick
render("daten/linach/linach_valley.png", list(p3*240+np.array([0,0,170])-u3*20))

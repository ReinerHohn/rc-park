#!/usr/bin/env python3
"""Komplette Sperre aus echtem Scan: Bogen1+2 (2-Bogen-Einheit) auf Dam-Körper
beschränkt, am Bogenabstand gespiegelt auf 13 Bögen, ins LGL-Tal, GPU-Render.
"""
import numpy as np, open3d as o3d
from scipy.ndimage import gaussian_filter
from linach_scan_common import load_baked, to_dam_frame
rend=o3d.visualization.rendering
L=143.0; BAY=L/13

V,F,col=load_baked("modelle/linachtalsperre/linach_bogen12.glb")
Lc=to_dam_frame(V)
# Dam-Körper: Vault-Region finden, X darauf zentrieren
vault=(Lc[:,1]>1)&(Lc[:,1]<13)&(Lc[:,2]>8)&(Lc[:,2]<21)
xcen=np.median(Lc[vault,0])
sel=(np.abs(Lc[:,0]-xcen)<BAY)&(Lc[:,1]>-8)&(Lc[:,1]<22)        # 2 Bögen + Körper
fm=sel[F].all(1); Fu=F[fm]; uq=np.unique(Fu); rm=-np.ones(len(V),int); rm[uq]=np.arange(len(uq))
uV=Lc[uq].copy(); uC=col[uq]; uF=rm[Fu]; uV[:,0]-=xcen
WU=2*BAY; print(f"Einheit {len(uF)}F  Breite~{np.ptp(uV[:,0]):.0f}m")

# Spiegel-Kacheln auf 143 m
aV=[];aF=[];aC=[];b=0
for k in range(-4,5):
    cx=k*WU
    if abs(cx)>L/2+WU*0.6: continue
    Vk=uV.copy(); Vk[:,0]=(-Vk[:,0] if k%2 else Vk[:,0])+cx
    aV.append(Vk); aC.append(uC); aF.append((uF[:,::-1] if k%2 else uF)+b); b+=len(Vk)
TV=np.vstack(aV); TF=np.vstack(aF); TC=np.vstack(aC)
print(f"Mauer {len(TF)}F  Länge {np.ptp(TV[:,0]):.0f}m")

# Welt-Frame
A=np.load("daten/linach/linach_dem.npy"); E0,N0=np.load("daten/linach/linach_dem_origin.npy"); ny,nx=A.shape
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
c0=int(round(Ed-0.5-E0)); r0=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[r0-25:r0+26,c0-25:c0+26].mean(),-gy[r0-25:r0+26,c0-25:c0+26].mean()]); p/=np.hypot(*p); u=np.array([-p[1],p[0]])
def px(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
zf=float(np.nanmin([px(t,30) for t in np.linspace(-70,70,60)]))
zt=TV[:,2]+(Z_LAKE+3.3)-(zf+TV[:,2].max())
DW=np.column_stack([Ed+TV[:,0]*u[0]+TV[:,1]*p[0], Nd+TV[:,0]*u[1]+TV[:,1]*p[1], zf+zt])

# Gelände + Wasser
cc0,cc1=c0-260,c0+120; rr0,rr1=r0-170,r0+170
sub=A[rr0:rr1,cc0:cc1]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1)+0.5+E0; Ny=N0+(ny-1-np.arange(rr0,rr1))+0.5
Xg,Yg=np.meshgrid(Ex,Ny)
GV=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); GF=[]
for i in range(gny-1):
    for j in range(gnx-1):
        a=i*gnx+j; GF+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
GF=np.array(GF)
import matplotlib.pyplot as plt
zc=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub)); GC=np.array(plt.cm.terrain(zc))[:,:3]
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1,cc0:cc1]
WF=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]:
            a=i*gnx+j; WF+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
WV=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); WF=np.array(WF)

def om(Vx,Fx,Cx):
    m=o3d.geometry.TriangleMesh(); m.vertices=o3d.utility.Vector3dVector(Vx.astype(np.float64))
    m.triangles=o3d.utility.Vector3iVector(Fx.astype(np.int32)); m.vertex_colors=o3d.utility.Vector3dVector(Cx.astype(np.float64)); m.compute_vertex_normals(); return m
dam=om(DW,TF,TC); terr=om(GV,GF,GC); wat=om(WV,WF,np.tile([0.16,0.42,0.70],(len(WV),1)))

def render(name,eye,W=1800,Hh=1100):
    r=rend.OffscreenRenderer(W,Hh); r.scene.set_background([0.60,0.70,0.82,1])
    for n,g in [('d',dam),('t',terr),('w',wat)]:
        mt=rend.MaterialRecord(); mt.shader='defaultLit'; r.scene.add_geometry(n,g,mt)
    r.scene.scene.set_sun_light([-.4,.5,-.9],[1,1,.96],95000); r.scene.scene.enable_sun_light(True)
    r.scene.scene.set_indirect_light_intensity(42000)
    ctr=np.array([Ed,Nd,zf+10.0]); r.setup_camera(45,ctr,ctr+np.array(eye),[0,0,1])
    o3d.io.write_image(name,r.render_to_image()); print("->",name)
p3=np.array([p[0],p[1],0.]); u3=np.array([u[0],u[1],0.])
render("daten/linach/full_hero.png", list(p3*130+np.array([0,0,80])+u3*35))
render("daten/linach/full_valley.png", list(p3*230+np.array([0,0,160])-u3*20))

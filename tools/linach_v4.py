#!/usr/bin/env python3
"""linach_v4.py — DATENGETRIEBEN: Geometrie-Parameter aus Bogen6-Scan gemessen
(Neigung 0.22, DB 8.6, Querriegel-Höhen), nahtlos arrayfähig (parametrisch),
DICHT unterteilt + echte Scan-Farben in hoher Dichte (3D-Match pro Bogen).
GPU-Render (beide Seiten) + interaktives HTML im Tal.
"""
import os,sys,base64,numpy as np,trimesh,open3d as o3d
sys.path.insert(0,'tools')
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter
from linach_scan_common import load_baked, to_dam_frame
rend=o3d.visualization.rendering
L,H,N=143.0,25.0,13; P=L/N; S=10.8
LEAN=0.218; DB=8.6; TB=1.4; TSH=0.9; SAG=3.4     # gemessen
BEAMZ=[5,9,14,19]                                 # Querriegel-Höhen (gemessen ~)
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)

def thick(G0,G1):
    m,n=G0.shape[:2]; off=m*n; V=np.vstack([G0.reshape(-1,3),G1.reshape(-1,3)]); Fa=[]
    i0=lambda i,j:i*n+j; i1=lambda i,j:off+i*n+j
    for i in range(m-1):
        for j in range(n-1):
            a,b,c,d=i0(i,j),i0(i,j+1),i0(i+1,j+1),i0(i+1,j); Fa+=[[a,b,c],[a,c,d]]
            a,b,c,d=i1(i,j),i1(i,j+1),i1(i+1,j+1),i1(i+1,j); Fa+=[[a,c,b],[a,d,c]]
    for i in range(m-1):
        for j in (0,n-1):
            a,b=i0(i,j),i0(i+1,j); c,d=i1(i,j),i1(i+1,j); Fa+=[[a,b,d],[a,d,c]]
    for j in range(n-1):
        for i in (0,m-1):
            a,b=i0(i,j),i0(i,j+1); c,d=i1(i,j),i1(i,j+1); Fa+=[[a,b,d],[a,d,c]]
    return trimesh.Trimesh(V,np.array(Fa),process=True)
def box(x0,x1,y0,y1,z0,z1): return trimesh.creation.box(bounds=[[x0,y0,z0],[x1,y1,z1]])
def yarc(s,z): return SAG*(1-s*s)+LEAN*z

parts=[]; ns,nh=22,20
for k in range(N):                                # konkave geneigte Schalen
    Xc=-L/2+(k+0.5)*P
    Pin=np.zeros((nh,ns,3)); Pout=np.zeros((nh,ns,3))
    for ih in range(nh):
        z=ih/(nh-1)*H
        for js in range(ns):
            s=-1+2*js/(ns-1); X=Xc+s*(S/2); y=yarc(s,z)
            Pin[ih,js]=[X,y,z]; Pout[ih,js]=[X,y+TSH,z]
    parts.append(thick(Pin,Pout))
for k in range(N+1):                              # Wandscheiben (DB gemessen)
    xb=-L/2+k*P; prof=[(LEAN*H,H),(0,0),(DB,0),(DB,0.32*H)]
    Vb=[]
    for sg in (-TB/2,TB/2):
        for (Y,Z) in prof:
            wid=sg*(1.0+0.12*(1-Z/H)); Vb.append([xb+wid,Y,Z])
    Fb=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    parts.append(trimesh.Trimesh(np.array(Vb),np.array(Fb),process=True))
for k in range(N):                                # Querriegel (gemessene Höhen)
    Xc=-L/2+(k+0.5)*P
    for z in BEAMZ:
        ym=yarc(0,z); parts.append(box(Xc-S/2+TB/2,Xc+S/2-TB/2,ym+TSH+0.2,ym+TSH+1.3,z-0.4,z+0.4))
# gewellte Krone + Geländer
nx=N*14; xs=np.linspace(-L/2,L/2,nx); yin=np.zeros(nx)
Gb=np.zeros((2,nx,3)); Gt=np.zeros((2,nx,3))
for j,x in enumerate(xs):
    kk=min(int((x+L/2)//P),N-1); Xc=-L/2+(kk+0.5)*P; s=max(-1,min(1,(x-Xc)/(S/2))); yi=yarc(s,H); yin[j]=yi
    Gb[0,j]=[x,yi-0.4,H]; Gb[1,j]=[x,yi+2.0,H]; Gt[0,j]=[x,yi-0.4,H+0.8]; Gt[1,j]=[x,yi+2.0,H+0.8]
parts.append(thick(Gb,Gt))
Rb=np.zeros((2,nx,3)); Rt=np.zeros((2,nx,3))
for j,x in enumerate(xs):
    Rb[0,j]=[x,yin[j]+1.8,H+0.8]; Rb[1,j]=[x,yin[j]+2.0,H+0.8]; Rt[0,j]=[x,yin[j]+1.8,H+1.6]; Rt[1,j]=[x,yin[j]+2.0,H+1.6]
parts.append(thick(Rb,Rt))
parts.append(box(-L/2-5,-L/2,-1,DB,0,H+1)); parts.append(box(L/2,L/2+5,-1,DB,0,H+1)); parts.append(box(-L/2-5,L/2+5,-1,DB,-2.5,0.2))
dam=trimesh.util.concatenate(parts); trimesh.repair.fix_normals(dam)
for _ in range(2): dam=dam.subdivide()            # DICHT -> trägt Farb-Detail
print('v4: %dV/%dF watertight=%s'%(len(dam.vertices),len(dam.faces),dam.is_watertight))
dam.export(f'{OUT}/linach_v4.stl')

# ---- echte Scan-Farben in HOHER Dichte übertragen (3D-Match pro Bogen) ----
V,Fs,col=load_baked('daten/linach/sketchfab_gltf/scene.gltf'); Lc=to_dam_frame(V)
m=(Lc[:,1]>-8)&(Lc[:,1]<12); Sp=Lc[m]; Sc=col[m]
Sp=Sp.copy(); Sp[:,0]-=np.median(Sp[(Sp[:,2]>8)&(Sp[:,2]<20),0])   # Bogen-Zentrum -> 0
tree=cKDTree(np.column_stack([Sp[:,0],Sp[:,1],Sp[:,2]]))
Vd=dam.vertices; xb=((Vd[:,0]+L/2)%P)-P/2                          # Position im Bogen [-P/2,P/2]
q=np.column_stack([xb, Vd[:,1]-TSH, Vd[:,2]*(22.7/H)]); _,ii=tree.query(q); vc=np.clip(Sc[ii],0,1)

def mo(V,F,C):
    o=o3d.geometry.TriangleMesh(); o.vertices=o3d.utility.Vector3dVector(V.astype(np.float64)); o.triangles=o3d.utility.Vector3iVector(F.astype(np.int32))
    o.vertex_colors=o3d.utility.Vector3dVector(np.clip(C,0,1).astype(np.float64)); o.compute_vertex_normals(); return o
md=mo(dam.vertices,dam.faces,vc)
def shot(name,eye):
    r=rend.OffscreenRenderer(1900,760); r.scene.set_background([0.57,0.67,0.80,1]); mt=rend.MaterialRecord(); mt.shader='defaultLit'; r.scene.add_geometry('d',md,mt)
    r.scene.scene.set_sun_light([-.3,-.5,-.75],[1,1,.97],82000); r.scene.scene.enable_sun_light(True); r.scene.scene.set_indirect_light_intensity(33000)
    c=dam.vertices.mean(0); r.setup_camera(38,[c[0],c[1],9],np.array([c[0],c[1],9])+np.array(eye),[0,0,1]); o3d.io.write_image(name,r.render_to_image())
shot('daten/linach/v4_luft.png',[14,92,15]); shot('daten/linach/v4_wasser.png',[10,-96,22]); print('renders ok')

# ---- interaktives HTML im Tal ----
A=np.load('daten/linach/linach_dem.npy'); E0,N0=np.load('daten/linach/linach_dem_origin.npy'); ny,nx2=A.shape
Ed,Nd=447097.5,5318581.4; Z_LAKE=847.5
c0=int(round(Ed-0.5-E0)); r0=ny-1-int(round(Nd-0.5-N0))
sm=gaussian_filter(A,6); gy,gx=np.gradient(-sm)
p=np.array([gx[r0-25:r0+26,c0-25:c0+26].mean(),-gy[r0-25:r0+26,c0-25:c0+26].mean()]); p/=np.hypot(*p); u=np.array([-p[1],p[0]])
def px(xu,pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx2-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1); return A[rr,cc]
zf=float(np.nanmin([px(t,30) for t in np.linspace(-70,70,60)]))
Vv=dam.vertices.copy(); zt=Vv[:,2]+(Z_LAKE+3.3)-(zf+Vv[:,2].max())
DW=np.column_stack([Ed+Vv[:,0]*u[0]+Vv[:,1]*p[0],Nd+Vv[:,0]*u[1]+Vv[:,1]*p[1],zf+zt])
cc0,cc1=c0-200,c0+110; rr0,rr1=r0-140,r0+140
sub=A[rr0:rr1,cc0:cc1]; gny,gnx=sub.shape
Ex=np.arange(cc0,cc1)+0.5+E0; Ny=N0+(ny-1-np.arange(rr0,rr1))+0.5; Xg,Yg=np.meshgrid(Ex,Ny)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
GV=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()]); GF=[]
for i in range(gny-1):
    for j in range(gnx-1): a=i*gnx+j; GF+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
GF=np.array(GF); zc=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub)); GC=(np.array(plt.cm.terrain(zc))[:,:3]*255).astype(np.uint8)
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1,cc0:cc1]; WF=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]: a=i*gnx+j; WF+=[[a,a+1,a+gnx+1],[a,a+gnx+1,a+gnx]]
WV=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); WF=np.array(WF)
ctr=np.array([Ed,Nd,zf+8]); sc=trimesh.Scene()
dm=trimesh.Trimesh(DW-ctr,dam.faces,process=False); dm.visual.vertex_colors=(vc*255).astype(np.uint8); sc.add_geometry(dm,'mauer')
gm=trimesh.Trimesh(GV-ctr,GF,process=False); gm.visual.vertex_colors=GC; sc.add_geometry(gm,'gelaende')
wm=trimesh.Trimesh(WV-ctr,WF,process=False); wm.visual.vertex_colors=np.tile([40,110,180,170],(len(WV),1)).astype(np.uint8); sc.add_geometry(wm,'wasser')
glb=sc.export(file_type='glb'); b64=base64.b64encode(glb).decode()
T='<!doctype html><meta charset=utf-8><title>Linachtalsperre v4</title><style>body{margin:0;background:#9fb3c8;font-family:system-ui}#i{position:fixed;left:12px;top:10px;color:#123;font-size:13px;text-shadow:0 1px 2px #fff}</style><div id=i><b>Linachtalsperre v4</b> datengetrieben, alle 13 Bögen + Scan-Farben<br>Maus drehen . Rad zoom</div>'
T+='<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>'
T+='<script type=module>import*as T from"three";import{OrbitControls}from"three/addons/controls/OrbitControls.js";import{GLTFLoader}from"three/addons/loaders/GLTFLoader.js";'
T+='const s=new T.Scene();s.background=new T.Color(0x9fb3c8);const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,9000);const rn=new T.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;s.add(new T.HemisphereLight(0xffffff,0x556,1.15));const L=new T.DirectionalLight(0xfff4e6,1.05);L.position.set(-120,140,120);s.add(L);'
T+='const b=atob("%s");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);new GLTFLoader().parse(ar.buffer,"",g=>{const o=g.scene;o.rotation.x=-Math.PI/2;s.add(o);const bb=new T.Box3().setFromObject(o),c=bb.getCenter(new T.Vector3()),z=bb.getSize(new T.Vector3());o.position.sub(c);const d=Math.max(z.x,z.y,z.z);cam.position.set(d*0.35,d*0.3,d*0.7);cam.lookAt(0,0,0);ct.update();});'%b64
T+='addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);});(function a(){requestAnimationFrame(a);ct.update();rn.render(s,cam);})();</script>'
open(f'{OUT}/linach_v4.html','w').write(T); print('HTML %dkB -> linach_v4.html'%(len(T)//1024))

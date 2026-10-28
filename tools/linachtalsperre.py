#!/usr/bin/env python3
"""linachtalsperre.py — ECHTES LGL-Tal (DGM1) + PARAMETRISCHE Gewölbereihen-Staumauer.

Deutschlands einzige Gewölbereihenstaumauer: 13 Tonnengewölbe (je 10,8 m Spannweite,
wasserseits konkav) auf 12 Wandscheiben, 143 m lang, 25 m hoch. 1922-25, Denkmalschutz.

Baut aus gestitchtem LGL-DGM1 (446+447/5318):
  modelle/linachtalsperre/linach_mauer.stl       — Mauer, METER (Referenz)
  modelle/linachtalsperre/linach_mauer_print.stl — Mauer druckfertig (Länge = PRINT_MM)
  modelle/linachtalsperre/linach_basis_print.stl — Gelände-Diorama-Basis (solid), gleicher Maßstab
  modelle/linachtalsperre/linach.html            — interaktiver 3D-Viewer (three.js, GLB eingebettet)
  daten/linach/linach_3d.png                     — statischer Render
Mauer-Achse AUS DEM GELÄNDE (quer zur Talenge), unabhängig von OSM.
"""
import os, base64, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.ndimage import gaussian_filter

DEM   = "daten/linach/linach_dem.npy"
ORIG  = "daten/linach/linach_dem_origin.npy"
Ed,Nd = 447097.5, 5318581.4
L, H  = 143.0, 25.0
N_ARCH= 13; SPAN = L/N_ARCH
R_ARC = 8.0; T_SH = 1.0
T_BUT = 1.6; D_BUT = 15.0
LEAN  = 0.12
Z_LAKE= 847.5
PRINT_MM = 160.0                                   # gewünschte Mauer-Länge im Druck
OUT   = "modelle/linachtalsperre"; os.makedirs(OUT, exist_ok=True)

A   = np.load(DEM); E0,N0 = np.load(ORIG); ny,nx = A.shape
col = int(round(Ed-0.5-E0)); ri = int(round(Nd-0.5-N0)); row = ny-1-ri

# ---- Talrichtung aus Gelände ------------------------------------------------
sm = gaussian_filter(A, 6); gy, gx = np.gradient(-sm)
r0,r1 = row-25,row+26; c0,c1 = col-25,col+26
p = np.array([gx[r0:r1,c0:c1].mean(), -gy[r0:r1,c0:c1].mean()]); p/=np.hypot(*p)
u = np.array([-p[1], p[0]])
print(f"Mauer px row,col={row},{col}  downstream p={p.round(2)} Achse u={u.round(2)}")

def px_pp(xu, pp):
    e=Ed+xu*u[0]+pp*p[0]; n=Nd+xu*u[1]+pp*p[1]
    cc=min(max(int(round(e-0.5-E0)),0),nx-1); rr=min(max(ny-1-int(round(n-0.5-N0)),0),ny-1)
    return A[rr,cc]
z_floor=float(np.nanmin([px_pp(t,30.0) for t in np.linspace(-L/2,L/2,60)]))
print(f"Mauerfuss z={z_floor:.1f} Krone z={z_floor+H:.1f} See {Z_LAKE}")

def to_xyz(xu,pp,zz):
    return (Ed+xu*u[0]+pp*p[0], Nd+xu*u[1]+pp*p[1], z_floor+zz)

# ====== Mesh-Helfer ==========================================================
def thick_surface(G0,G1):
    """zwei (m,n,3)-Gitter -> geschlossenes Volumen dazwischen."""
    m,n=G0.shape[:2]; off=m*n
    V=np.vstack([G0.reshape(-1,3),G1.reshape(-1,3)]); F=[]
    i0=lambda i,j:i*n+j; i1=lambda i,j:off+i*n+j
    for i in range(m-1):
        for j in range(n-1):
            a,b,c,d=i0(i,j),i0(i,j+1),i0(i+1,j+1),i0(i+1,j)
            F+=[[a,b,c],[a,c,d]]
            a,b,c,d=i1(i,j),i1(i,j+1),i1(i+1,j+1),i1(i+1,j)
            F+=[[a,c,b],[a,d,c]]
    for i in range(m-1):                       # Ränder j=0 / j=n-1
        for (j,) in [(0,),(n-1,)]:
            a,b=i0(i,j),i0(i+1,j); c,d=i1(i,j),i1(i+1,j)
            F+=[[a,b,d],[a,d,c]]
    for j in range(n-1):                       # Ränder i=0 / i=m-1
        for (i,) in [(0,),(m-1,)]:
            a,b=i0(i,j),i0(i,j+1); c,d=i1(i,j),i1(i,j+1)
            F+=[[a,b,d],[a,d,c]]
    return trimesh.Trimesh(V,np.array(F),process=True)

parts=[]
nT,nH=14,10
for k in range(N_ARCH):                        # 13 Gewölbe als dicke Schalen
    umid=-L/2+(k+0.5)*SPAN; ang=np.arcsin((SPAN/2)/R_ARC)
    th=np.linspace(-ang,ang,nT); hh=np.linspace(0,H,nH)
    Pin=np.zeros((nH,nT,3)); Pout=np.zeros((nH,nT,3))
    for ih,z in enumerate(hh):
        for it,a in enumerate(th):
            uu=umid+R_ARC*np.sin(a); pp=(R_ARC*np.cos(a)-R_ARC*np.cos(ang))+LEAN*z
            Pin[ih,it]=to_xyz(uu,pp,z); Pout[ih,it]=to_xyz(uu,pp+T_SH,z)
    parts.append(thick_surface(Pin,Pout))

for k in range(N_ARCH+1):                      # 14 Wandscheiben (Dreiecksprismen)
    us=-L/2+k*SPAN
    tri=[(LEAN*H,H),(0.0,0.0),(D_BUT,0.0)]     # (pp,z)
    Vb=[]
    for s in (-T_BUT/2,T_BUT/2):
        for (pp,zz) in tri:
            x=Ed+us*u[0]+pp*p[0]+s*u[0]; y=Nd+us*u[1]+pp*p[1]+s*u[1]; Vb.append([x,y,z_floor+zz])
    Fb=[[0,1,2],[3,5,4],[0,3,4],[0,4,1],[1,4,5],[1,5,2],[2,5,3],[2,3,0]]
    parts.append(trimesh.Trimesh(np.array(Vb),np.array(Fb),process=True))

# Krone (Fahrweg) als dicke Platte z=H..H+1.2
nU=60; Gb=np.zeros((2,nU,3)); Gt=np.zeros((2,nU,3))
for j,t in enumerate(np.linspace(-L/2,L/2,nU)):
    Gb[0,j]=to_xyz(t,LEAN*H-0.4,H); Gb[1,j]=to_xyz(t,LEAN*H+2.4,H)
    Gt[0,j]=to_xyz(t,LEAN*H-0.4,H+1.2); Gt[1,j]=to_xyz(t,LEAN*H+2.4,H+1.2)
parts.append(thick_surface(Gb,Gt))

dam=trimesh.util.concatenate(parts)
dam.visual.face_colors=[170,168,158,255]
dam.export(f"{OUT}/linach_mauer.stl")
print(f"Mauer: {len(dam.vertices)}V/{len(dam.faces)}F  watertight={dam.is_watertight}")

# ====== GELÄNDE + WASSER (Szene-Fenster) =====================================
cc0,cc1=col-300,col+130; rr0,rr1=row-180,row+180; st=2
sub=A[rr0:rr1:st,cc0:cc1:st]
gny,gnx=sub.shape
Ex=(np.arange(cc0,cc1,st)+0.5+E0); Ny_=(N0+(ny-1-np.arange(rr0,rr1,st))+0.5)
Xg,Yg=np.meshgrid(Ex,Ny_)
# Gelände-Surface-Mesh mit Höhen-Vertexfarben
Vt=np.column_stack([Xg.ravel(),Yg.ravel(),sub.ravel()])
Ft=[]
for i in range(gny-1):
    for j in range(gnx-1):
        a=i*gnx+j; b=a+1; c=a+gnx; d=c+1; Ft+=[[a,b,d],[a,d,c]]
terr=trimesh.Trimesh(Vt,np.array(Ft),process=False)
zz=(sub.ravel()-np.nanmin(sub))/(np.nanmax(sub)-np.nanmin(sub))
terr.visual.vertex_colors=(np.array(plt.cm.terrain(zz))*255).astype(np.uint8)
# Wasser-Mesh: Zellen, deren 4 Ecken alle unter Seespiegel liegen
lake=np.load('daten/linach/lake_mask.npy')[rr0:rr1:st,cc0:cc1:st]
Vw=np.column_stack([Xg.ravel(),Yg.ravel(),np.full(Xg.size,Z_LAKE)]); Fw=[]
for i in range(gny-1):
    for j in range(gnx-1):
        if lake[i,j] and lake[i+1,j] and lake[i,j+1] and lake[i+1,j+1]:
            a=i*gnx+j; b=a+1; c=a+gnx; d=c+1; Fw+=[[a,b,d],[a,d,c]]
water=trimesh.Trimesh(Vw,np.array(Fw),process=False) if Fw else None
if water is not None:
    water.visual.face_colors=[40,110,180,170]

# ====== GLB + HTML ===========================================================
scene=trimesh.Scene()
ctr=terr.vertices.mean(0)
for nm,msh in [("gelaende",terr),("wasser",water),("mauer",dam)]:
    if msh is None: continue
    m=msh.copy(); m.apply_translation(-ctr); m.apply_scale(1.0)  # meters, zentriert
    scene.add_geometry(m,geom_name=nm)
glb=scene.export(file_type="glb")
b64=base64.b64encode(glb).decode()
html=f"""<!doctype html><meta charset=utf-8><title>Linachtalsperre 3D</title>
<style>body{{margin:0;background:#0c1116;font-family:system-ui;color:#cdd}}#i{{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;text-shadow:0 1px 3px #000;line-height:1.4}}</style>
<div id=i><b>Linachtalsperre</b> — echtes LGL-Tal + Gewölbereihe (13 Bögen à 10,8 m, 143×25 m)<br>
<span style=color:#8cf>Maus: drehen · Rad: zoom · rechts: verschieben</span></div>
<script type="importmap">{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}}}</script>
<script type=module>
import*as T from"three";import{{OrbitControls}}from"three/addons/controls/OrbitControls.js";
import{{GLTFLoader}}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0x0c1116);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,5000);
const rn=new T.WebGLRenderer({{antialias:true}});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x334455,0.9));
const sun=new T.DirectionalLight(0xfff2e0,1.1);sun.position.set(-120,80,160);sc.add(sun);
const b=atob("{b64}");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
new GLTFLoader().parse(ar.buffer,"",g=>{{
 const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const bb=new T.Box3().setFromObject(o),c=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(c);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.6,d*0.5,d*0.9);cam.lookAt(0,0,0);ct.update();
}},e=>{{document.getElementById("i").innerHTML+="<br><span style=color:#f88>LOAD-FEHLER "+e+"</span>";}});
addEventListener("resize",()=>{{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);}});
(function a(){{requestAnimationFrame(a);ct.update();rn.render(sc,cam);}})();
</script>"""
open(f"{OUT}/linach.html","w").write(html)
print(f"HTML: {OUT}/linach.html ({len(html)//1024} kB)")

# ====== DRUCKFERTIG (Maßstab: Mauer-Länge = PRINT_MM) ========================
f=PRINT_MM/L                                   # mm pro Meter
S=1000.0/f                                      # Nenner 1:S
dam_p=dam.copy(); dam_p.apply_translation(-dam.bounds[0]); dam_p.apply_scale(f)
dam_p.export(f"{OUT}/linach_mauer_print.stl")
e=dam_p.extents
print(f"DRUCK Maßstab 1:{S:.0f}  Mauer {e[0]:.0f}×{e[1]:.0f}×{e[2]:.0f} mm")

# Gelände-Basis solid (watertight: Haut + Schürze + Boden), gleicher Maßstab
base_z=np.nanmin(sub)-3.0
top=terr.copy()
# Rand-Schürze + Boden erzeugen
V2=top.vertices.copy(); F2=list(top.faces)
idx=lambda i,j:i*gnx+j
border=[]
for j in range(gnx): border.append(idx(0,j))
for i in range(gny): border.append(idx(i,gnx-1))
for j in range(gnx-1,-1,-1): border.append(idx(gny-1,j))
for i in range(gny-1,-1,-1): border.append(idx(i,0))
bo=len(V2); Vb2=V2[border].copy(); Vb2[:,2]=base_z; V2=np.vstack([V2,Vb2])
for k in range(len(border)-1):
    a,b=border[k],border[k+1]; c,d=bo+k,bo+k+1; F2+=[[a,b,d],[a,d,c]]
cb=len(V2); V2=np.vstack([V2,[[Xg.mean(),Yg.mean(),base_z]]])
for k in range(len(border)-1): F2+=[[bo+k,bo+k+1,cb]]
basis=trimesh.Trimesh(V2,np.array(F2),process=True)
basis.apply_translation(-basis.bounds[0]); basis.apply_scale(f)
basis.export(f"{OUT}/linach_basis_print.stl")
be=basis.extents
print(f"DRUCK Basis {be[0]:.0f}×{be[1]:.0f}×{be[2]:.0f} mm  (Bett 250×210 -> {'passt' if be[0]<250 and be[1]<210 else 'KACHELN nötig'})")

# ====== STATISCHER RENDER (2 Panels) =========================================
def shade(tr):
    n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0])
    n=n/np.clip(np.linalg.norm(n,axis=1,keepdims=True),1e-9,None)
    lt=np.array([0.4,-0.5,0.8]); lt/=np.linalg.norm(lt)
    return (np.array([0.62,0.60,0.55])[None,:]*(0.35+0.65*np.clip(n@lt,0,1))[:,None])
dctr=dam.vertices.mean(0); Vc=dam.vertices-dctr
Vloc=np.stack([Vc@np.array([u[0],u[1],0]),Vc@np.array([p[0],p[1],0]),Vc[:,2]],1)
triL=Vloc[dam.faces]
fig=plt.figure(figsize=(16,7))
axA=fig.add_subplot(121,projection='3d')
axA.add_collection3d(Poly3DCollection(triL,facecolors=shade(triL),edgecolor='k',linewidths=0.2))
axA.set_xlim(-L/2-3,L/2+3); axA.set_ylim(-D_BUT*0.7,D_BUT+3); axA.set_zlim(0,H+3)
axA.set_box_aspect((L,(D_BUT+H)*1.8,H*1.8)); axA.view_init(elev=9,azim=-86)
axA.set_title("13 Gewölbe à 10,8 m — 143×25 m (Luftseite)"); axA.set_xlabel("Länge m"); axA.set_zlabel("m"); axA.set_yticks([])
axB=fig.add_subplot(122,projection='3d')
axB.plot_surface(Xg-Ed,Yg-Nd,sub,cmap='terrain',alpha=0.75,linewidth=0,antialiased=False,rcount=80,ccount=80)
Wz=np.where(lake,Z_LAKE,np.nan); axB.plot_surface(Xg-Ed,Yg-Nd,Wz,color='#2a6fb0',alpha=0.5,linewidth=0,rcount=80,ccount=80)
triT=dam.vertices[dam.faces].copy(); triT[:,:,0]-=Ed; triT[:,:,1]-=Nd
axB.add_collection3d(Poly3DCollection(triT,facecolors=shade(triT),edgecolor='none'))
axB.set_box_aspect((1,1,0.45)); axB.view_init(elev=32,azim=-118)
axB.set_title("im echten LGL-Tal — See staut gegen die Mauer"); axB.set_xlabel("Ost m"); axB.set_ylabel("Nord m")
plt.tight_layout(); plt.savefig("daten/linach/linach_3d.png",dpi=115)
print("Render: daten/linach/linach_3d.png")

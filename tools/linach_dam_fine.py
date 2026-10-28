#!/usr/bin/env python3
"""linach_dam_fine.py — FEINE, wasserdichte Gewölbereihen-Staumauer (Beton-Hälfte
des Hybrids). Echte Maße (143m/13 Bögen/10,8m/25m). Runde Tonnengewölbe, hoch
aufgelöst, Wandscheiben mit Böschung, Krone+Brüstung. HELLER Render.
Textur (Scan-glTF) kommt separat drüber.
"""
import os, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

L,H=143.0,25.0; N=13; P=L/N; S=10.8
R=7.0; A=np.arcsin((S/2)/R); TSH=1.1; LEAN=0.10
DB=14.0; TB=1.9                      # Wandscheibe Tiefe/Dicke
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)

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

parts=[]
nT,nZ=30,22
for k in range(N):                                   # 13 runde Tonnengewölbe
    Xc=-L/2+(k+0.5)*P
    th=np.linspace(-A,A,nT); zs=np.linspace(0,H,nZ)
    Pin=np.zeros((nZ,nT,3)); Pout=np.zeros((nZ,nT,3))
    for iz,z in enumerate(zs):
        yoff=LEAN*z
        for it,a in enumerate(th):
            X=Xc+R*np.sin(a); Y=(R-R*np.cos(a))+yoff
            Pin[iz,it]=[X,Y,z]; Pout[iz,it]=[X,Y+TSH,z]
    parts.append(thick_surface(Pin,Pout))

for k in range(N+1):                                 # 14 Wandscheiben (Böschung+Trapez)
    Xs=-L/2+k*P
    prof=[(LEAN*H,H),(0.0,0.0),(DB,0.0),(DB,H*0.32)]  # (Y,Z) Trapez
    Vb=[]
    for s in (-TB/2,TB/2):
        sb=s*(1.0 if True else 1)                     # leichte Basis-Verbreiterung
        for (Y,Z) in prof:
            wid=s*(1.0+0.15*(1-Z/H))                   # Böschung: unten breiter
            Vb.append([Xs+wid,Y,Z])
    Fb=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],
        [0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    parts.append(trimesh.Trimesh(np.array(Vb),np.array(Fb),process=True))

# Krone (Fahrbahn) + 2 Brüstungen
nU=160
Gb=np.zeros((2,nU,3)); Gt=np.zeros((2,nU,3))
for j,x in enumerate(np.linspace(-L/2,L/2,nU)):
    Gb[0,j]=[x,LEAN*H-0.6,H]; Gb[1,j]=[x,LEAN*H+2.8,H]
    Gt[0,j]=[x,LEAN*H-0.6,H+1.0]; Gt[1,j]=[x,LEAN*H+2.8,H+1.0]
parts.append(thick_surface(Gb,Gt))
for yb in (LEAN*H-0.5,LEAN*H+2.6):                    # Brüstungsstreifen
    Gb=np.zeros((2,nU,3)); Gt=np.zeros((2,nU,3))
    for j,x in enumerate(np.linspace(-L/2,L/2,nU)):
        Gb[0,j]=[x,yb-0.12,H+1.0]; Gb[1,j]=[x,yb+0.12,H+1.0]
        Gt[0,j]=[x,yb-0.12,H+1.7]; Gt[1,j]=[x,yb+0.12,H+1.7]
    parts.append(thick_surface(Gb,Gt))

# End-Widerlager (binden in den Hang) + durchgehender Sockel
parts.append(trimesh.creation.box(bounds=[[-L/2-5,-1.0,0],[-L/2,DB,H+1.0]]))
parts.append(trimesh.creation.box(bounds=[[ L/2, -1.0,0],[ L/2+5,DB,H+1.0]]))
parts.append(trimesh.creation.box(bounds=[[-L/2-5,-1.0,-2.5],[L/2+5,DB,0.3]]))   # Sockel/Standfläche
dam=trimesh.util.concatenate(parts)
trimesh.repair.fix_normals(dam); trimesh.repair.fill_holes(dam)
dam.export(f"{OUT}/linach_fein.stl")
print(f"Feine Mauer: {len(dam.vertices)}V/{len(dam.faces)}F  watertight={dam.is_watertight}")

# ---- DRUCKFERTIG: skalieren + prüfen ----
for name,target_mm in [("linach_druck_230",230.0),("linach_druck_N160",143000/160.0)]:
    f=target_mm/L; d=dam.copy(); d.apply_translation(-dam.bounds[0]); d.apply_scale(f)
    e=d.extents; S=1000.0/f
    bed=(e[0]<250 and e[1]<210)
    print(f"{name}: 1:{S:.0f}  {e[0]:.0f}×{e[1]:.0f}×{e[2]:.0f}mm  watertight={d.is_watertight}  "
          f"Bett250×210={'1 Teil' if bed else 'in %d Teile splitten'%int(np.ceil(e[0]/230))}  Vol={d.volume/1000:.0f}cm³")
    d.export(f"{OUT}/{name}.stl")

# ---- HELLER Render, 2 gute Winkel ----
def shade(tr,base=(0.86,0.84,0.79)):
    n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]); n=n/np.clip(np.linalg.norm(n,axis=1,keepdims=True),1e-9,None)
    lt=np.array([0.35,-0.55,0.75]); lt/=np.linalg.norm(lt)
    return np.clip(np.array(base)[None,:]*(0.62+0.4*np.clip(n@lt,0,1))[:,None],0,1)
tri=dam.vertices[dam.faces]
fig=plt.figure(figsize=(16,7),facecolor='white')
for i,(el,az,ti) in enumerate([(22,-58,"Luftseite 3/4 (Wandscheiben + Gewölbe)"),
                                (24,118,"Wasserseite (konkave Gewölbe)")]):
    ax=fig.add_subplot(1,2,i+1,projection='3d',facecolor='white')
    ax.add_collection3d(Poly3DCollection(tri,facecolors=shade(tri),edgecolor=(0,0,0,0.08),linewidths=0.1))
    ax.set_xlim(-L/2-3,L/2+3); ax.set_ylim(-4,DB+3); ax.set_zlim(0,H+4)
    ax.set_box_aspect((L,(DB+H)*1.3,H*1.3)); ax.view_init(elev=el,azim=az)
    ax.set_title(f"Linachtalsperre — feine Form, 13 Bögen à 10,8 m — {ti}",fontsize=11)
    ax.set_xlabel("Länge m"); ax.set_zlabel("m"); ax.set_yticks([])
    for pane in (ax.xaxis,ax.yaxis,ax.zaxis): pane.pane.set_facecolor((1,1,1,0)); pane.pane.set_edgecolor((0.8,0.8,0.8,1))
plt.tight_layout(); plt.savefig("daten/linach/linach_fein.png",dpi=120,facecolor='white')
print("Render: daten/linach/linach_fein.png")

#!/usr/bin/env python3
"""linach_dam_v3.py — STRUKTUR-GENAU nach Wikimedia 220/237/245/246:
 - 13 konkave, geneigte Tonnengewölbe-SCHALEN (Wasserseite gegen Wasser gewölbt)
 - 14 Wandscheiben (talseits dreieckig)
 - 4 horizontale Querriegel pro Nische (die eckigen Streben, Foto 245)
 - gewellte Krone (folgt den Schalen) + Geländer + Widerlager/Sockel
Leicht -> interaktives HTML + GPU-Render.
"""
import os, base64, numpy as np, trimesh, open3d as o3d
from scipy.ndimage import gaussian_filter
rend=o3d.visualization.rendering
L,H,N=143.0,25.0,13; P=L/N; S=10.8
SAG=3.6          # Gewölbe-Ausbauchung talseits (Mitte) — konkav zum Wasser
BATTER=0.16      # Rückneigung (Krone talseits der Sohle)
TSH=0.9          # Schalendicke
DB=12.0; TB=1.5  # Wandscheibe Tiefe/Dicke
NBEAM=4          # Querriegel pro Nische
OUT="modelle/linachtalsperre"; os.makedirs(OUT,exist_ok=True)

def thick(G0,G1):
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
def box(x0,x1,y0,y1,z0,z1): return trimesh.creation.box(bounds=[[x0,y0,z0],[x1,y1,z1]])
def yarc(s,z): return SAG*(1-s*s)+BATTER*z            # Talseits-Y der Schale

parts=[]
ns,nh=18,16
for k in range(N):                                     # 13 geneigte konkave Schalen
    Xc=-L/2+(k+0.5)*P
    Pin=np.zeros((nh,ns,3)); Pout=np.zeros((nh,ns,3))
    for ih in range(nh):
        z=ih/(nh-1)*H
        for js in range(ns):
            s=-1+2*js/(ns-1); X=Xc+s*(S/2); y=yarc(s,z)
            Pin[ih,js]=[X,y,z]; Pout[ih,js]=[X,y+TSH,z]
    parts.append(thick(Pin,Pout))
for k in range(N+1):                                   # 14 Wandscheiben
    xb=-L/2+k*P
    prof=[(BATTER*H,H),(0,0),(DB,0),(DB,0.30*H)]       # (Y,Z): Front folgt Rückneigung
    Vb=[]
    for sg in (-TB/2,TB/2):
        for (Y,Z) in prof:
            wid=sg*(1.0+0.12*(1-Z/H)); Vb.append([xb+wid,Y,Z])
    Fb=[[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    parts.append(trimesh.Trimesh(np.array(Vb),np.array(Fb),process=True))
for k in range(N):                                     # Querriegel: 4 pro Nische
    Xc=-L/2+(k+0.5)*P
    for b in range(NBEAM):
        z=(b+1)/(NBEAM+1)*H; ymid=yarc(0,z)
        parts.append(box(Xc-S/2+TB/2, Xc+S/2-TB/2, ymid+TSH+0.3, ymid+TSH+1.6, z-0.45, z+0.45))
# gewellte Krone (folgt Schalen) + Geländer
nx=N*12; xs=np.linspace(-L/2,L/2,nx)
Gb=np.zeros((2,nx,3)); Gt=np.zeros((2,nx,3)); yin=np.zeros(nx)
for j,x in enumerate(xs):
    kk=min(int((x+L/2)//P),N-1); Xc=-L/2+(kk+0.5)*P; s=(x-Xc)/(S/2); s=max(-1,min(1,s))
    yi=yarc(s,H); yin[j]=yi
    Gb[0,j]=[x,yi-0.4,H]; Gb[1,j]=[x,yi+2.2,H]; Gt[0,j]=[x,yi-0.4,H+0.8]; Gt[1,j]=[x,yi+2.2,H+0.8]
parts.append(thick(Gb,Gt))
Rb=np.zeros((2,nx,3)); Rt=np.zeros((2,nx,3))
for j,x in enumerate(xs):
    Rb[0,j]=[x,yin[j]+2.0,H+0.8]; Rb[1,j]=[x,yin[j]+2.2,H+0.8]; Rt[0,j]=[x,yin[j]+2.0,H+1.7]; Rt[1,j]=[x,yin[j]+2.2,H+1.7]
parts.append(thick(Rb,Rt))                             # Handlauf-Band
parts.append(box(-L/2-5,-L/2,-1,DB,0,H+1)); parts.append(box(L/2,L/2+5,-1,DB,0,H+1))   # Widerlager
parts.append(box(-L/2-5,L/2+5,-1,DB,-2.5,0.2))                                          # Sockel

dam=trimesh.util.concatenate(parts); trimesh.repair.fix_normals(dam)
dam.export(f"{OUT}/linach_v3.stl")
print(f"v3: {len(dam.vertices)}V/{len(dam.faces)}F  watertight={dam.is_watertight}")

# Beton-Farbe
rng=np.random.default_rng(5); z=dam.vertices[:,2]
col=np.clip(np.array([0.72,0.71,0.68])-0.05*(z/H)[:,None]+rng.normal(0,0.022,(len(z),3)),0.3,0.95)

# ---- GPU-Render Mauer allein (Luft- + Wasserseite) ----
def mesh_o3d(V,F,C):
    m=o3d.geometry.TriangleMesh(); m.vertices=o3d.utility.Vector3dVector(V.astype(np.float64))
    m.triangles=o3d.utility.Vector3iVector(F.astype(np.int32)); m.vertex_colors=o3d.utility.Vector3dVector(np.clip(C,0,1).astype(np.float64)); m.compute_vertex_normals(); return m
md=mesh_o3d(dam.vertices,dam.faces,col); c=dam.vertices.mean(0)
def face(name,eye,look=None):
    r=rend.OffscreenRenderer(1900,800); r.scene.set_background([0.58,0.68,0.80,1])
    mt=rend.MaterialRecord(); mt.shader='defaultLit'; r.scene.add_geometry('d',md,mt)
    r.scene.scene.set_sun_light([-.3,-.45,-.8],[1,1,.97],82000); r.scene.scene.enable_sun_light(True); r.scene.scene.set_indirect_light_intensity(32000)
    tgt=look if look else [c[0],c[1],9]; r.setup_camera(38,tgt,np.array(tgt)+np.array(eye),[0,0,1]); o3d.io.write_image(name,r.render_to_image()); print("ok",name)
face("daten/linach/v3_luft.png",[18,90,16])       # Luftseite (talseits +Y)
face("daten/linach/v3_wasser.png",[14,-95,22])    # Wasserseite (-Y)

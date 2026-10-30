#!/usr/bin/env python3
"""
ECHTER Todtnauer Wasserfall — LGL-1m-LiDAR (Kachel 421/5298) + Wasserkreislauf.

Gelaende = reale Topografie der Fall-Schlucht (Fallkopf 903 m -> Fallfuss 825 m,
78 m Gefaelle). Lauf folgt der echten Tallinie (incised Bachbett). Dazu:
Becken unten (Fallfuss) + 45-Grad-Aufsteck-Stutzen (Auslass oben/Becken unten),
Diffusor-Pool, duenne Randlippe ums Eck. Nur Druckteil, keine Bruecke.

Daten: daten/todtnau/waterfall_grid.npy (col c->E=421000.5+c, row r->N=5299999.5-r).
"""
import numpy as np, trimesh
from scipy.ndimage import gaussian_filter
from trimesh.transformations import rotation_matrix as ROT
import trimesh.geometry as _tg

GRID="daten/todtnau/waterfall_grid.npy"
FOOT=210.0; EXAG=1.4; BASE=5.0; STEP=2
CH_DEPTH=5.0; CH_HW=3.5               # schmaler, natuerlicher Bach (~7mm)
BASIN_ROWS=40; BORE_D=10.0
POOL_START=24; DIFF_LEN=15

from scipy.ndimage import rotate as ndrotate
Gb=np.load("daten/todtnau/todtnau_grid.npy")            # E419000-421000
Gw=np.load("daten/todtnau/waterfall_grid.npy")          # E421000-423000
G=np.concatenate([Gb,Gw],axis=1)                        # durchgehend, col c->E=419000.5+c
kopf=np.array([1366,2068]); fuss=np.array([1501,2201])  # Fall head/foot im Stitch
cen=(kopf+fuss)//2; R=190
big=G[cen[0]-R:cen[0]+R, cen[1]-R:cen[1]+R].astype(float)
mk=np.zeros_like(big); kk=kopf-(cen-R); ff=fuss-(cen-R)
mk[kk[0]-3:kk[0]+4,kk[1]-3:kk[1]+4]=1; mk[ff[0]-3:ff[0]+4,ff[1]-3:ff[1]+4]=2
bigr=ndrotate(big,-44.6,reshape=True,order=1,mode='nearest')   # Fall -> vertikal
mkr =ndrotate(mk, -44.6,reshape=True,order=0,mode='constant')
kp=np.argwhere((mkr>0.5)&(mkr<1.5)).mean(0); fp=np.argwhere(mkr>=1.5).mean(0)
cc=int(round((kp[1]+fp[1])/2)); r0=int(min(kp[0],fp[0]))-40; r1=int(max(kp[0],fp[0]))+40
HALF=118
sub=bigr[max(0,r0):r1, cc-HALF:cc+HALF].astype(float)
sub=gaussian_filter(sub,0.6)[::STEP,::STEP]
if kp[0] < fp[0]: sub=np.flipud(sub)                     # vorne(y=0)=Fallfuss(tief)
NY,NX=sub.shape
dx=FOOT/max(NX,NY); mmpm=FOOT/(max(NX,NY)*STEP)
Z=(sub-sub.min())*mmpm*EXAG
xs=np.arange(NX)*dx; ys=np.arange(NY)*dx
X,Y=np.meshgrid(xs,ys); rows=np.arange(NY)[:,None]
print(f"Gelaende {sub.shape} Relief {Z.max():.0f}mm (echter Fall 78m Gefaelle)")

# ---- Tallinie NUR im mittleren Streifen suchen (= der Fall) -> Bach bleibt ZENTRIERT ----
sm=gaussian_filter(Z,1.5)
b0,b1=NX//2-16, NX//2+16                                  # zentraler Suchstreifen
tcol=np.array([b0+int(np.argmin(sm[i,b0:b1])) for i in range(NY)])
tcol=np.round(gaussian_filter(tcol.astype(float),5)).astype(int)
chx=gaussian_filter(xs[tcol],1.2); dist=np.abs(X-chx[:,None])   # purer echter Thalweg (kein Fake-Maeander)

# ---- Lauf einfraesen (variable Tiefe = Gumpen/Riffel), ab Diffusor nach vorne ----
zt=Z[np.arange(NY),tcol]; zt=np.minimum.accumulate(zt[::-1])[::-1]   # hinten hoch -> vorne tief
depth=CH_DEPTH*(0.65+0.35*np.sin(2*np.pi*np.arange(NY)/26.0))
sole=zt-depth
ramp=np.clip((dist-CH_HW)/9.0,0,1)
chan=sole[:,None]+ramp*(Z-sole[:,None])
carve=(rows<NY-0)&(dist<CH_HW+9)
Z=np.where(carve, np.minimum(Z,chan), Z)

# ---- Becken unten (Fallfuss, vorne) ----
basin=(rows<BASIN_ROWS)&(dist<CH_HW+24)
basin_floor=float(Z[basin].min())-2
Z=np.where(basin, basin_floor, Z)
RIM_H=36.0
# ---- Diffusor-Pool oben (Fallkopf, hinten) ----
pool=(rows>=NY-POOL_START-DIFF_LEN)&(rows<NY-POOL_START)&(dist<CH_HW+16)
dz_pool=float(Z[pool].min())-4 if pool.any() else float(Z.max())
Z=np.where(pool, dz_pool, Z)
# ---- duenne Randlippe ums Eck (nur aeussere Zellen, keine dicken Waende) ----
cols=np.arange(NX)[None,:]
border=(rows<3)|(cols<3)|(cols>=NX-3)
Z=np.where(border, np.maximum(Z, basin_floor+RIM_H), Z)
Z=gaussian_filter(Z,0.5); Z-=Z.min()
print(f"  Modellhoehe {Z.max():.0f}mm, Bach {CH_HW*2:.0f}mm schmal + maeandernd")

# ---- Solidify ----
NT=NX*NY
top=np.column_stack([X.ravel(),Y.ravel(),Z.ravel()]); bot=np.column_stack([X.ravel(),Y.ravel(),np.full(NT,-BASE)])
V=np.vstack([top,bot]); F=[]
I2,J2=np.mgrid[0:NY-1,0:NX-1]; I2=I2.ravel(); J2=J2.ravel()
a=I2*NX+J2; b=a+1; c=(I2+1)*NX+J2; d=c+1
F+=[np.column_stack([a,c,b]),np.column_stack([b,c,d])]; F+=[np.column_stack([a+NT,b+NT,c+NT]),np.column_stack([b+NT,d+NT,c+NT])]
def wall(it):
    it=np.array(it); ib=it+NT; f=[]
    for k in range(len(it)-1): f+=[[it[k],ib[k],it[k+1]],[it[k+1],ib[k],ib[k+1]]]
    return np.array(f)
tr=np.arange(NX); br=np.arange((NY-1)*NX,NY*NX); lc=np.arange(NY)*NX; rc=lc+(NX-1)
for e,fl in [(tr,False),(br,True),(lc,True),(rc,False)]: F.append(wall(e[::-1] if fl else e))
mesh=trimesh.Trimesh(vertices=V,faces=np.vstack(F),process=True); trimesh.repair.fix_normals(mesh)
mesh.vertices[:,2]-=mesh.vertices[:,2].min()

# ---- 45-Grad-Aufsteck-Stutzen + Durchgang ----
def zAt(x,y):
    j=int(np.clip(x/dx,0,NX-1)); i=int(np.clip(y/dx,0,NY-1)); return float(Z[i,j])
def cyl_between(p,q,r):
    p=np.array(p,float); q=np.array(q,float); v=q-p; L=float(np.linalg.norm(v))
    cc=trimesh.creation.cylinder(radius=r,height=L); cc.apply_transform(_tg.align_vectors([0,0,1.],v/L)); cc.apply_translation((p+q)/2); return cc
def barb45(B,outw,T):
    dd=np.array([0.,outw,1.]); dd/=np.linalg.norm(dd); B=np.array(B,float); tip=B+dd*16
    body=cyl_between(B-dd*9,tip,4.6); rings=[cyl_between(tip-dd*4.5,tip-dd*3.0,5.8),cyl_between(tip-dd*1.8,tip-dd*0.3,5.8)]
    barb=trimesh.boolean.union([body]+rings)
    bore=trimesh.boolean.union([cyl_between(tip+dd*3,B-dd*2,2.6),cyl_between(B,np.array(T,float),2.6)])
    return trimesh.boolean.difference([barb,bore]), bore
# Auslass hinten (Fallkopf), Becken vorne (Fallfuss)
xo=float(chx[NY-POOL_START-6]); poolY=ys[NY-POOL_START-6]; poolF=zAt(xo,poolY)
b_out,bore_out=barb45([xo,ys[-1],poolF+20],+1,[xo,poolY,poolF+3])
xb=float(chx[6]); basF=zAt(xb,ys[6])
b_bas,bore_bas=barb45([xb,0.0,basF+16],-1,[xb,ys[6],basF+6])
mesh=trimesh.boolean.union([mesh,b_out,b_bas]); mesh=trimesh.boolean.difference([mesh,bore_out,bore_bas])
# ---- Brueckenkoepfe (GEDRUCKT) + prominente Haengebruecke ueber den Fall (Viz wie todtnau_3d) ----
ym=ys[NY//2]; xl=18.0; xr=float(xs[-1]-18.0)
def marker(x,y):
    zt=zAt(x,y); peg=trimesh.creation.cylinder(radius=3.4,height=28); peg.apply_translation([x,y,zt+1])
    head=trimesh.creation.cylinder(radius=5.5,height=3); head.apply_translation([x,y,zt+13])
    return trimesh.boolean.union([peg,head])
mesh=trimesh.boolean.union([mesh, marker(xl,ym), marker(xr,ym)])
np.save('/tmp/wf_heads.npy', np.array([[xl,ym,zAt(xl,ym)],[xr,ym,zAt(xr,ym)]]))
anchor=max(zAt(xl,ym),zAt(xr,ym))+12; S=xr-xl
valley=min(zAt(float(x),ym) for x in np.linspace(xl,xr,30)); sag=min(0.13*S, anchor-valley-12); TH=20; wd=12
def bx(s,x,y,z): bb=trimesh.creation.box(s); bb.apply_translation([x,y,z]); return bb
dz=lambda x:(lambda u:anchor-sag*(1-u*u))((x-(xl+xr)/2)/(S/2))
cz=lambda x:(lambda u:anchor+TH-(TH+sag-7)*(1-u*u))((x-(xl+xr)/2)/(S/2))
xb_=np.linspace(xl,xr,36); P=[]
for i in range(len(xb_)-1):
    xm=(xb_[i]+xb_[i+1])/2; L=(xb_[i+1]-xb_[i])*1.3
    P.append(bx([L,wd,3],xm,ym,dz(xm)))
    for yo in(-wd/2,wd/2): P.append(bx([L,1.6,1.6],xm,ym+yo,cz(xm)))
for x in xb_[1:-1:2]:
    for yo in(-wd/2,wd/2): P.append(bx([1.4,1.4,max(2.0,cz(x)-dz(x))],float(x),ym+yo,(cz(x)+dz(x))/2))
for xp in(xl,xr): P.append(bx([4,wd+3,TH+8],xp,ym,anchor+TH/2))
trimesh.boolean.union(P).export("modelle/todtnau_wasserfall_bruecke.stl")
# Sliver-Artefakte aus den Booleans entfernen -> nur substanzielle Koerper behalten
parts=[p for p in mesh.split(only_watertight=False) if len(p.faces)>30]
mesh=max(parts,key=lambda b:len(b.faces)) if len(parts)==1 else trimesh.util.concatenate(parts)
np.save('/tmp/wf_chx.npy', np.column_stack([chx, ys]))   # fuer Bach-Faerbung im Render
np.save('/tmp/wf_stutzen.npy', np.array([[xo,ys[-1],poolF+20],[xb,0.0,basF+16]]))  # Auslass, Becken
mesh.export("modelle/todtnau_wasserfall.stl")
print(f"-> modelle/todtnau_wasserfall.stl {mesh.extents.round(0)} Koerper={len(mesh.split(only_watertight=False))}")

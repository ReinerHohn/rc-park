#!/usr/bin/env python3
"""
Todtnau/Hasenhorn — echtes LGL-1m-LiDAR.
  DRUCKTEIL  : modelle/todtnau_gelaende.stl = Gelaende + Wasserlauf durchs echte Tal
               + geschlossenes Becken unten (Schlauchanschluss) + Auslass oben (Pumpe rein).
  NUR VIZ    : modelle/todtnau_bruecke.stl  = BlackForest-Line-Haengebruecke an den echten
               OSM-Punkten (NICHT drucken, nur zur Veranschaulichung).

Tal faellt Nord(oben,~939m) -> Sued(unten,~765m): Auslass Nord, Becken Sued.
Georef: col c -> E=419000.5+c ; row r -> N=5299999.5-r. Bruecke OSM 'BlackForest Line'.
Hoehenfeld = Schauseite ueberhangfrei. Becken+Lauf innen mit Epoxy abdichten.
"""
import numpy as np, trimesh
from scipy.ndimage import gaussian_filter

GRID="daten/todtnau/todtnau_grid.npy"
C0,C1,R0,R1=np.load("daten/todtnau/crop.npy")
HEADS=np.load("daten/todtnau/bridge_heads.npy")
FOOT=240.0; EXAG=1.25; BASE=5.0; STEP=2
CH_DEPTH=5.0; CH_HW=4.5
BASIN_ROWS=46          # suedliches Becken (Zeilen am Unterende)
BORE_D=10.0

g=np.load(GRID); sub=g[R0:R1,C0:C1].astype(float)[::STEP,::STEP]
sub=gaussian_filter(sub,0.6)
NY,NX=sub.shape
dx=FOOT/max(NX,NY); mmper_m=FOOT/(max(NX,NY)*STEP)
Z=(sub-sub.min())*mmper_m*EXAG
xs=np.arange(NX)*dx; ys=np.arange(NY)*dx
X,Y=np.meshgrid(xs,ys)
def head_mm(cr): c,r=cr; return c/STEP*dx, r/STEP*dx
K1=np.array(head_mm(HEADS[0])); K2=np.array(head_mm(HEADS[1]))
print(f"Gelaende {sub.shape} Relief {Z.max():.0f}mm")

# ---- echtes Bachbett: Talboden (Thalweg) + sanfter Maeander ----
sm=gaussian_filter(Z,1.5)
tcol=np.array([int(np.argmin(sm[i])) for i in range(NY)])
tcol=np.round(gaussian_filter(tcol.astype(float),5)).astype(int)
mx=xs[tcol]+5.0*np.sin(2*np.pi*np.arange(NY)/52.0)+2.5*np.sin(2*np.pi*np.arange(NY)/23.0)
chx=gaussian_filter(mx,1.5); dist=np.abs(X-chx[:,None])

# ---- Nordbank bleibt MASSIV (traegt den versenkten Einlass); Lauf beginnt am Diffusor ----
POOL_START=26; DIFF_LEN=16
rows=np.arange(NY)[:,None]
zt=Z[np.arange(NY),tcol]; zt=np.minimum.accumulate(zt)
depth=CH_DEPTH*(0.65+0.35*np.sin(2*np.pi*np.arange(NY)/27.0))   # Gumpen/Riffel = echtes Bett
sole=zt-depth
ramp=np.clip((dist-CH_HW)/8.0,0,1)                              # sanftere Ufer
chan=sole[:,None]+ramp*(Z-sole[:,None])
carve=(rows>=POOL_START)&(dist<CH_HW+8)           # NUR ab Diffusor nach Sued fraesen
Z=np.where(carve, np.minimum(Z,chan), Z)

# ---- Becken unten (Sued): flacher dichter Pool + Suedkanten-Damm ----
basin=(rows>=NY-BASIN_ROWS)&(dist<CH_HW+26)
basin_floor=float(Z[basin].min())-2
Z=np.where(basin, basin_floor, Z)
RIM_H=38.0
# NUR eine duenne Rand-Lippe an der Modell-Aussenkante, laeuft ums Eck (keine dicken Innenwaende).
# Hebt nur die aeussersten Zellen dort an, wo der Rand tiefer als die Lippe liegt (= Suedende + Ecken).
cols=np.arange(NX)[None,:]
border=(rows>=NY-3)|(cols<3)|(cols>=NX-3)
Z=np.where(border, np.maximum(Z, basin_floor+RIM_H), Z)

# ---- DIFFUSOR-Pool direkt hinter der Nordbank: bricht den Strahl, Weir laeuft breit+sanft ----
pool=(rows>=POOL_START)&(rows<POOL_START+DIFF_LEN)&(dist<CH_HW+18)
dz_pool=float(Z[pool].min())-4
Z=np.where(pool, dz_pool, Z)
weir=(rows>=POOL_START+DIFF_LEN-1)&(rows<=POOL_START+DIFF_LEN)&(dist<CH_HW+18)
Z=np.where(weir, dz_pool+5, Z)                     # breite, sanfte Ueberlaufkante
Z=gaussian_filter(Z,0.5); Z-=Z.min()
print(f"  Modellhoehe {Z.max():.0f}mm, Tal Nord->Sued, Becken {BASIN_ROWS} Zeilen Sued")

# ---- Solidify ----
NT=NX*NY
top=np.column_stack([X.ravel(),Y.ravel(),Z.ravel()])
bot=np.column_stack([X.ravel(),Y.ravel(),np.full(NT,-BASE)])
V=np.vstack([top,bot]); F=[]
I2,J2=np.mgrid[0:NY-1,0:NX-1]; I2=I2.ravel(); J2=J2.ravel()
a=I2*NX+J2; b=a+1; c=(I2+1)*NX+J2; d=c+1
F+=[np.column_stack([a,c,b]),np.column_stack([b,c,d])]
F+=[np.column_stack([a+NT,b+NT,c+NT]),np.column_stack([b+NT,d+NT,c+NT])]
def wall(it):
    it=np.array(it); ib=it+NT; f=[]
    for k in range(len(it)-1): f+=[[it[k],ib[k],it[k+1]],[it[k+1],ib[k],ib[k+1]]]
    return np.array(f)
tr=np.arange(NX); br=np.arange((NY-1)*NX,NY*NX); lc=np.arange(NY)*NX; rc=lc+(NX-1)
for e,fl in [(tr,False),(br,True),(lc,True),(rc,False)]: F.append(wall(e[::-1] if fl else e))
mesh=trimesh.Trimesh(vertices=V,faces=np.vstack(F),process=True)
trimesh.repair.fix_normals(mesh); mesh.vertices[:,2]-=mesh.vertices[:,2].min()

# ---- VERSENKTE waagerechte Steck-Anschluesse (keine Tuelle -> kein Ueberhang/Stuetze) ----
from trimesh.transformations import rotation_matrix as ROT
def zAt(x,y):
    j=int(np.clip(x/dx,0,NX-1)); i=int(np.clip(y/dx,0,NY-1)); return float(Z[i,j])
def cylY(r,L,x,y,z):                 # Zylinder entlang Y, Mitte (x,y,z)
    c=trimesh.creation.cylinder(radius=r,height=L); c.apply_transform(ROT(np.pi/2,[1,0,0]))
    c.apply_translation([x,y,z]); return c
BW=(BORE_D-2)/2
def aufsteck(x,ywall,z,outw,into=30):
    """waagerechter Aufsteck-Stutzen + Widerhaken + 45°-Stuetzkeil unten; Durchgang BW."""
    L=12.0; rb=4.6
    body=cylY(rb,L,x,ywall+outw*L/2,z)
    r1=cylY(5.7,2.0,x,ywall+outw*L*0.5,z); r2=cylY(5.7,2.0,x,ywall+outw*L*0.85,z)
    g=trimesh.creation.box([2*rb+3,L*1.25,L*1.25]); g.apply_transform(ROT(np.pi/4,[1,0,0]))
    g.apply_translation([x,ywall+outw*L*0.45,z-rb-3])            # 45°-Keil = stuetzenfrei
    barb=trimesh.boolean.union([body,r1,r2,g])
    bore=cylY(BW,L+into,x,ywall+outw*(L-into)/2,z)              # waagerecht durch Wand in Kammer
    return trimesh.boolean.difference([barb,bore]), bore
# --- 45-Grad-Aufsteck-Stutzen (nach aussen-oben gewinkelt -> stuetzenfrei, KEIN Block) ---
import trimesh.geometry as _tg
def cyl_between(p,q,r):
    p=np.array(p,float); q=np.array(q,float); v=q-p; L=float(np.linalg.norm(v))
    c=trimesh.creation.cylinder(radius=r,height=L)
    c.apply_transform(_tg.align_vectors([0,0,1.],v/L)); c.apply_translation((p+q)/2); return c
def barb45(B,outw,T):
    d=np.array([0.,outw,1.]); d/=np.linalg.norm(d); B=np.array(B,float); tip=B+d*16
    body=cyl_between(B-d*3,tip,4.6)
    rings=[cyl_between(tip-d*4.5,tip-d*3.0,5.8), cyl_between(tip-d*1.8,tip-d*0.3,5.8)]
    barb=trimesh.boolean.union([body]+rings)
    bore1=cyl_between(tip+d*3, B-d*2, 2.6)              # gerade DURCH den Stutzen
    bore2=cyl_between(B, np.array(T,float), 2.6)        # dann Knick in die Kammer
    bore=trimesh.boolean.union([bore1,bore2])
    return trimesh.boolean.difference([barb,bore]), bore
# AUSLASS: 45-Grad-Stutzen hoch an der Nordbank -> Bohrung runter in den Diffusor-Pool
xo=float(chx[POOL_START+4]); poolY=ys[POOL_START+4]; poolF=zAt(xo,poolY)
b_out,bore_out=barb45([xo,0.0,poolF+20], -1, [xo,poolY,poolF+3])
# BECKEN/Pumpe: 45-Grad-Stutzen mittig an der Suedwand -> Bohrung in die Beckenmitte (nie zum Boden)
xb=float(chx[-6]); basF=zAt(xb,ys[-6])
b_bas,bore_bas=barb45([xb,ys[-1],basF+16], +1, [xb,ys[-1]-16,basF+6])
mesh=trimesh.boolean.union([mesh,b_out,b_bas])
mesh=trimesh.boolean.difference([mesh,bore_out,bore_bas])
baffle=trimesh.creation.box([CH_HW*1.7,2.4,9]); baffle.apply_translation([xo,ys[POOL_START+6],poolF+5])
mesh=trimesh.boolean.union([mesh,baffle])
print(f"  45-Grad-Aufsteck-Stutzen (stuetzenfrei, kein Block): Auslass Nord / Becken Sued")

# ---- Brueckenpunkt-MARKER an den OSM-Punkten (im Druck sichtbar: Start/Ende) ----
def marker(x,y,zt):
    # EIN massiver Stift, 12mm tief im Gelaende verankert (merged sicher) -> schwebt nie
    peg =trimesh.creation.cylinder(radius=3.2,height=26); peg.apply_translation([x,y,zt+1])  # zt-12..zt+14
    head=trimesh.creation.cylinder(radius=5.0,height=3);  head.apply_translation([x,y,zt+12]) # Kopf, ueberlappt Stift
    return trimesh.boolean.union([peg,head])
mk=[marker(K1[0],K1[1],zAt(*K1)), marker(K2[0],K2[1],zAt(*K2))]
mesh=trimesh.boolean.union([mesh]+mk)
print(f"  Brueckenmarker @ Kopf1 {K1.round(0)} / Kopf2 {K2.round(0)}")
mesh.export("modelle/todtnau_gelaende.stl")
print(f"-> modelle/todtnau_gelaende.stl  {mesh.extents.round(0)}  (Auslass oben + Becken-Stutzen unten)")

# ========== NUR-VIZ: Haengebruecke an den OSM-Punkten (nicht drucken) ==========
def zat(p):
    j=int(np.clip(p[0]/dx,0,NX-1)); i=int(np.clip(p[1]/dx,0,NY-1)); return float(Z[max(0,i-2):i+3,max(0,j-2):j+3].max())
anchor=max(zat(K1),zat(K2))+5
tline=np.linspace(0,1,40)[:,None]*(K2-K1)+K1; valley=min(zat(p) for p in tline)
span=float(np.linalg.norm(K2-K1)); ang=np.arctan2(K2[1]-K1[1],K2[0]-K1[0])
sag=min(0.13*span, anchor-valley-25)
N=34; wd=9.0; TH=16.0
def dz(x): u=(x-span/2)/(span/2); return anchor - sag*(1-u*u)
def cz(x): u=(x-span/2)/(span/2); return anchor+TH-(TH+sag-6)*(1-u*u)
def bx(s,x,y,z): b=trimesh.creation.box(s); b.apply_translation([x,y,z]); return b
xb=np.linspace(0,span,N); P=[]
for i in range(N-1):
    xm=(xb[i]+xb[i+1])/2; L=(xb[i+1]-xb[i])*1.3
    P.append(bx([L,wd,2.2],xm,0,dz(xm)))
    for yo in (-wd/2,wd/2): P.append(bx([L,1.3,1.3],xm,yo,cz(xm)))
for x in xb[2:-2:2]:
    for yo in (-wd/2,wd/2):
        hh=max(2,cz(x)-dz(x)); P.append(bx([1.1,1.1,hh],x,yo,(cz(x)+dz(x))/2))
for xp in (0,span):
    P.append(bx([3,wd+2,TH+6],xp,0,anchor+TH/2))
    P.append(bx([6,wd+4,anchor+6],xp,0,(anchor+6)/2-BASE))   # Auflagerfuss (nur Viz)
br=trimesh.boolean.union(P)
br.apply_transform(trimesh.transformations.rotation_matrix(ang,[0,0,1]))
br.apply_translation([K1[0],K1[1],0])
br.export("modelle/todtnau_bruecke.stl")
print(f"-> modelle/todtnau_bruecke.stl  (NUR Viz, Spannweite {span:.0f}mm Durchhang {sag:.0f}mm)")

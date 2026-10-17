#!/usr/bin/env python3
"""
Triberg-Wasserfall — ECHTER LASERSCAN (LGL-1m-LiDAR) als Basis, nur fuers Wasser
leicht eingefraest. KEINE gestaltete Geometrie.

Vorgehen:
  - echte DGM1-Topografie um den Triberger Fall (daten/triberg/*.npy) = das Gelaende
  - nur LEICHT einfraesen: flache Rinne entlang der echten Tallinie, damit Wasser fliesst
  - Becken vorne wasserdicht schliessen (Damm quer) -> geschlossenes Reservoir + Pumpe
  - Schlauch versteckt: Bohrung hoch + Diamant-Tunnel im Sockel
  - ZWEI Brueckenkoepfe (Auflager li+re, gleiche Hoehe, Schlitz) -> eigene Bruecke reinhaengen

Hoehenfeld = Schauseite ueberhangfrei. Abdichten: Rinne+Becken 1x mit Epoxy/2K-Lack.
"""
import os, numpy as np, trimesh
from scipy.ndimage import gaussian_filter

_R="daten/triberg/triberg_grid.npy"; GRID=_R if os.path.exists(_R) else "/tmp/triberg_grid.npy"
FALL=GRID.replace("grid","fall")

ROWS, COLS = 240, 181      # Original-Ausschnitt
FOOT = 240.0; EXAG = 1.35  # echter Scan, dezente Ueberhoehung
BASE = 6.0
CH_DEPTH = 6.0; CH_HW = 8.0        # nur LEICHT einfraesen
NPOOL = 7; LIP = 2.5               # 7 Becken (Wasserfall-Treppe) + Weir-Lippe
BASIN_Y = 40.0                     # Beckentiefe vorne
DAM_T = 7.0; DAM_H = 46.0          # vorderer Damm schliesst das Becken
TOPPOOL_Y = 20.0
BORE_D = 12.0
AB_FRAC = 0.50                     # Bruecke bei 50% Tiefe
BRIDGE_CLR = 6.0                   # Luft unter der Bruecke ueber dem Wasser

g=np.load(GRID); fr,fc=np.load(FALL)
sub=g[fr-60:fr-60+ROWS, fc-140:fc-140+COLS].astype(float)
sub=np.flipud(sub)                 # vorne=tief (Becken), hinten=hoch
sub=gaussian_filter(sub,0.6)
dx=FOOT/max(ROWS,COLS)
Z=(sub-sub.min())*dx*EXAG
NY,NX=Z.shape
xs=np.arange(NX)*dx; ys=np.arange(NY)*dx
X,Y=np.meshgrid(xs,ys)
W=xs[-1]; CXc=W/2
print(f"echter Scan {sub.shape}  Relief {Z.max():.0f}mm (EXAG {EXAG})")

# --- echte Tallinie ---
band=slice(NX//5,NX-NX//5); sm=gaussian_filter(Z,2.0)
thal=np.array([band.start+np.argmin(sm[i,band]) for i in range(NY)])
thal=np.round(gaussian_filter(thal.astype(float),6)).astype(int)
chx=xs[thal]; dist=np.abs(X-chx[:,None])

# --- 7 BECKEN als Wasserfall-Treppe entlang der echten Tallinie (wie Original) ---
zt=Z[np.arange(NY),thal]
zt=np.minimum.accumulate(zt[::-1])[::-1]             # Gelaende entlang Lauf, vorne tief
seg=np.clip(np.arange(NY)*NPOOL//NY,0,NPOOL-1)       # 0=vorne .. NPOOL-1=hinten
pool_z=np.array([zt[seg==k].mean() for k in range(NPOOL)])  # steigt vorne->hinten
sole=pool_z[seg]-CH_DEPTH                            # flacher Pool-Boden je Stufe
# Weir-Lippe an der Pool-Vorderkante -> haelt stehendes Wasser in jedem Becken
for k in range(NPOOL-1):
    e=np.argmax(seg==k+1); sole[e-1]+=LIP
ramp=np.clip((dist-CH_HW)/5.0,0,1)
chan=sole[:,None]+ramp*(Z-sole[:,None])
Z=np.where(dist<CH_HW+5, np.minimum(Z,chan), Z)
print(f"  {NPOOL} Becken, Pool-Hoehen {[round(float(p)) for p in pool_z]} mm")

# --- Becken vorne + Damm (geschlossenes Reservoir) ---
distC=np.abs(X-CXc)                        # Leitung laeuft mittig
basin=(Y<BASIN_Y)&(distC<CH_HW+24)
basin_floor=Z[Y<BASIN_Y].min()-2
Z=np.where(basin, basin_floor, Z)
Z=np.where(Y<DAM_T, basin_floor+DAM_H, Z)          # Damm quer vorn -> dicht
# --- Top-Pool hinten (mittig, nimmt Auslass-Stutzen auf) ---
tp=(Y>ys[-1]-TOPPOOL_Y)&(distC<CH_HW+6)
Z=np.where(tp, Z[tp].min(), Z)
Z=gaussian_filter(Z,0.5); Z-=Z.min()
print(f"  Modellhoehe {Z.max():.0f}mm, Rinne {CH_HW*2:.0f}mm/{CH_DEPTH:.0f}mm tief")

# --- Solidify ---
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
print(f"  solid watertight={mesh.is_watertight} faces={len(mesh.faces):,}")

# --- zwei Brueckenkoepfe WEIT auseinander auf den Talflanken (Haengebruecke) ---
ri=int(AB_FRAC*NY); yb=ys[ri]
xl=0.15*W; xr=0.85*W                 # auf beiden Flanken, ~70% Breite auseinander
def zAt(xp):
    j=int(np.clip(xp/dx,0,NX-1)); return float(Z[max(0,ri-3):ri+4, max(0,j-3):j+4].max())
zbr=max(zAt(xl),zAt(xr))+6           # Auflager-/Deckankerhoehe
abut=[]
for xp in (xl,xr):
    a=trimesh.creation.box([20,26,zbr+10]); a.apply_translation([xp,yb,(zbr+10)/2-2]); abut.append(a)
mesh=trimesh.boolean.union([mesh]+abut)
slots=[trimesh.creation.box([12,16,15]) for _ in (0,1)]
for sl,xp in zip(slots,(xl,xr)): sl.apply_translation([xp,yb,zbr+8])
# Talsohle an dieser Linie -> wie tief darf das Deck haengen
valley_z=float(Z[ri, int(0.3*NX):int(0.7*NX)].min())
print(f"  Haengebruecke-Koepfe @ y={yb:.0f}mm, Spannweite {xr-xl:.0f}mm, Anker {zbr:.0f}mm, Talsohle {valley_z:.0f}mm")

# --- versteckte Leitung (mittig): Tunnel Becken->hinten + Bohrung hoch ---
bz=mesh.bounds[1][2]
y_top=ys[-1]-TOPPOOL_Y/2; y_bot=BASIN_Y*0.5
bore=trimesh.creation.cylinder(radius=BORE_D/2,height=bz+BASE+2)
bore.apply_translation([CXc, y_top,(bz+BASE+2)/2-BASE])
tun=trimesh.creation.box([14,ys[-1]+4,14]); tun.apply_transform(
    trimesh.transformations.rotation_matrix(np.pi/4,[0,1,0])); tun.apply_translation([CXc,ys[-1]/2,2])

# --- ZWEI SCHLAUCHSTUTZEN (Tuellen) mit Durchgangsbohrung, mittig ueber der Leitung ---
def stutzen(x,y,zbase,L=15):
    """barbed Tuelle: Fuss + 2 Widerhaken-Ringe, Durchgang BORE_D-2."""
    parts=[trimesh.creation.cylinder(radius=5.0,height=L)]
    parts[0].apply_translation([0,0,L/2])
    for zr in (L*0.45,L*0.8):                       # Widerhaken
        r=trimesh.creation.cylinder(radius=6.0,height=2.0); r.apply_translation([0,0,zr]); parts.append(r)
    s=trimesh.boolean.union(parts)
    hole=trimesh.creation.cylinder(radius=(BORE_D-2)/2,height=L+6); hole.apply_translation([0,0,L/2])
    s=trimesh.boolean.difference([s,hole]); s.apply_translation([x,y,zbase]); return s
# Auslass-Stutzen oben im Top-Pool, Pumpen-Stutzen unten im Becken
tp_floor = float(Z[(Y>ys[-1]-TOPPOOL_Y)&(np.abs(X-CXc)<CH_HW)].min())
bs_floor = float(Z[(Y<BASIN_Y)&(np.abs(X-CXc)<CH_HW+24)].min())
st_top = stutzen(CXc, y_top, tp_floor-2)
st_bot = stutzen(CXc, y_bot, bs_floor-2)
mesh=trimesh.boolean.union([mesh,st_top,st_bot])
print("  2 Schlauchstutzen gesetzt (oben Auslass, unten Pumpe)")

mesh=trimesh.boolean.difference([mesh,bore,tun]+slots)
n=mesh.face_normals; ar=mesh.area_faces; dn=n[:,2]<-0.5
print(f"  final watertight={mesh.is_watertight} Ueberhang {100*ar[dn].sum()/ar.sum():.1f}% (nur intern)")
mesh.export("modelle/triberg_wasserfall.stl"); print("-> modelle/triberg_wasserfall.stl")

# --- HAENGEBRUECKE (separat): durchhaengendes Deck + Seile, haengt tief ueber dem Hang ---
S=xr-xl; mid=(xl+xr)/2; N=30; wd=11.0; TH=20.0
# Durchhang so, dass das Deck ~10mm ueber der Talsohle schwebt (tief, aber nicht drin)
sag=min(40.0, zbr-(valley_z+10))
def deckz(x): return zbr - sag*(1-((x-mid)/(S/2))**2)      # Deck-Parabel
sag_c=TH+sag-7
def cabz(x):  return zbr+TH - sag_c*(1-((x-mid)/(S/2))**2) # Seil-Parabel (hoeher)
def box_at(size,x,y,z):
    b=trimesh.creation.box(size); b.apply_translation([x,y,z]); return b
xb=np.linspace(xl,xr,N); parts=[]            # alles in ABSOLUTEN x, y um 0
for i in range(N-1):
    xm=(xb[i]+xb[i+1])/2; Lseg=(xb[i+1]-xb[i])*1.3
    parts.append(box_at([Lseg,wd,2.6], xm,0,deckz(xm)))            # Deck
    for yo in (-wd/2,wd/2):
        parts.append(box_at([Lseg,1.5,1.5], xm,yo,cabz(xm)))       # 2 Trageseile
for x in xb[2:-2:2]:                                               # Haenger
    for yo in (-wd/2,wd/2):
        hh=max(2.0,cabz(x)-deckz(x))
        parts.append(box_at([1.2,1.2,hh], x,yo,(cabz(x)+deckz(x))/2))
for xp in (xl,xr):                                                 # Pylone + Einhaenge-Zapfen
    parts.append(box_at([3.5,wd+3,TH+8], xp,0,zbr+TH/2))
    parts.append(box_at([12,15,14],      xp,0,zbr-6))
br=trimesh.boolean.union(parts)
br.apply_translation([0,yb,0])                                     # nur in y auf die Bruecken-Linie
br.export("modelle/triberg_bruecke.stl")
print(f"-> modelle/triberg_bruecke.stl (Haengebruecke, Durchhang {sag:.0f}mm, Deckmitte {deckz(mid):.0f}mm)")

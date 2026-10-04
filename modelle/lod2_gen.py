#!/usr/bin/env python3
"""
lod2_gen.py — amtliches LoD2-CityGML (Freiburg) -> Altstadt ums Muenster mit ECHTEN
Dachformen. Laesst den Muenster-Slot frei (Detail-Highlight) und schneidet in Druck-Kacheln
fuer die Farm. Streaming-Parse (memory-safe) + UTM32 ohne pyproj. stdlib + numpy.
Cache: /tmp/lod2_muenster_buildings.pkl (kein 1,6-GB-Neuparse beim Iterieren).

Datenbasis: Stadt Freiburg (www.freiburg.de) / LGL BW, Datenlizenz Deutschland Namensnennung 2.0.
"""
import xml.etree.ElementTree as ET
import math, struct, zlib, os, pickle
import numpy as np

GML="/tmp/freiburg_lod2.gml"
TILES=int(os.environ.get("TILES","2"))  # NxN Kacheln (per Env TILES=3 usw.)
RADIUS=float(os.environ.get("RADIUS","250"))  # Altstadt-Radius ums Muenster in m (RADIUS=700 = ganze Altstadt)
CACHE="/tmp/lod2_muenster_%dm.pkl"%int(RADIUS)  # Cache pro Radius (sonst alter 250er geladen)
MAXMM=float(os.environ.get("MAXMM","180"))  # groesste Kante in mm

def utm32(lat,lon):
    a=6378137.0; f=1/298.257222101; e2=f*(2-f); ep2=e2/(1-e2); k0=0.9996; lon0=math.radians(9.0)
    lat=math.radians(lat); lon=math.radians(lon)
    N=a/math.sqrt(1-e2*math.sin(lat)**2); T=math.tan(lat)**2; C=ep2*math.cos(lat)**2
    A=math.cos(lat)*(lon-lon0)
    M=a*((1-e2/4-3*e2**2/64-5*e2**3/256)*lat-(3*e2/8+3*e2**2/32+45*e2**3/1024)*math.sin(2*lat)
         +(15*e2**2/256+45*e2**3/1024)*math.sin(4*lat)-(35*e2**3/3072)*math.sin(6*lat))
    E=500000+k0*N*(A+(1-T+C)*A**3/6+(5-18*T+T*T+72*C-58*ep2)*A**5/120)
    Nn=k0*(M+N*math.tan(lat)*(A*A/2+(5-T+9*C+4*C*C)*A**4/24+(61-58*T+T*T+600*C-330*ep2)*A**6/720))
    return E,Nn
ME,MN=utm32(47.9956970,7.8535034); R=RADIUS
X0,X1,Y0,Y1=ME-R,ME+R,MN-R,MN+R
lname=lambda t:t.split('}')[-1]

if os.path.exists(CACHE):
    print("Gebaeude aus Cache..."); buildings=pickle.load(open(CACHE,"rb"))
else:
    print("Parse LoD2 (1,6 GB)..."); buildings=[]; seen=0
    ctx=ET.iterparse(GML,events=('start','end')); ev,root=next(ctx)
    for ev,elem in ctx:
        if ev!='end': continue
        if lname(elem.tag) in ("Building","BuildingPart"):
            seen+=1; polys=[]
            for pl in elem.iter():
                if lname(pl.tag)=="posList" and pl.text:
                    n=pl.text.split()
                    if len(n)>=9: polys.append([(float(n[i]),float(n[i+1]),float(n[i+2])) for i in range(0,len(n)-2,3)])
            elem.clear()
            if not polys: continue
            fx,fy=polys[0][0][0],polys[0][0][1]
            if not(X0<=fx<=X1 and Y0<=fy<=Y1): continue
            bt=[]; zs=[]
            for ring in polys:
                if len(ring)>=4 and ring[0]==ring[-1]: ring=ring[:-1]
                if len(ring)<3: continue
                for p in ring: zs.append(p[2])
                a0=ring[0]
                for i in range(1,len(ring)-1): bt.append((a0,ring[i],ring[i+1]))
            if bt:
                cx=sum(t[0][0] for t in bt)/len(bt); cy=sum(t[0][1] for t in bt)/len(bt)
                buildings.append({'t':bt,'cx':cx,'cy':cy,'zmin':min(zs),'zmax':max(zs)})
            if seen%20000==0: root.clear(); print("  ...%d gescannt, %d im Bereich"%(seen,len(buildings)))
    pickle.dump(buildings,open(CACHE,"wb"))
print("%d Gebaeude im Muenster-Bereich"%len(buildings))

# --- Muenster behalten (Standard). MROUT>0 wuerde den Komplex ums hoechste Gebaeude freilassen ---
MROUT=float(os.environ.get("MROUT","0"))
mset=set()
if MROUT>0:
    ti=max(range(len(buildings)),key=lambda i:buildings[i]['zmax']-buildings[i]['zmin'])
    tcx,tcy=buildings[ti]['cx'],buildings[ti]['cy']
    mset=set(i for i,b in enumerate(buildings) if math.hypot(b['cx']-tcx,b['cy']-tcy)<MROUT)
    print("Muenster-Slot frei: %d Gebaeude entfernt (Radius %.0fm)"%(len(mset),MROUT))
else:
    print("Muenster bleibt drin.")

# --- globale Skalierung (max 180 mm) ---
allp=np.array([p for b in buildings for t in b['t'] for p in t],dtype=np.float64)
gmn=allp.min(0); s=MAXMM/max((allp[:,0]-gmn[0]).max(),(allp[:,1]-gmn[1]).max())
def to_mm(tri):
    a=np.array(tri,dtype=np.float64); a-=gmn; a*=s; return a

# --- Hero-Overlay: LoD2-Masse durch Detailmodelle ersetzen/ueberlagern, wo vorhanden ---
# Manifest modelle/hero/hero.json = [{"name","lat","lon","radius_m","stl","height_m"[,"rot_deg"]}]
# Detail-STLs liegen LOKAL in modelle/hero/ (NICHT committen: Muenster-Scan ist CC-BY-NC).
# Fehlt das Verzeichnis/Manifest -> no-op, LoD2-Masse bleibt stehen.
def read_stl(path):
    with open(path,"rb") as f: head=f.read(5)
    if head==b"solid":  # evtl. ASCII
        txt=open(path,"r",errors="ignore").read()
        if "facet normal" in txt:
            vs=[]; tri=[]
            for ln in txt.split("\n"):
                ln=ln.strip()
                if ln.startswith("vertex"):
                    _,x,y,z=ln.split()[:4]; vs.append((float(x),float(y),float(z)))
                    if len(vs)==3: tri.append(vs); vs=[]
            return np.array(tri,dtype=np.float64)
    with open(path,"rb") as f:  # binaer
        f.read(80); n=struct.unpack("<I",f.read(4))[0]
        d=np.frombuffer(f.read(50*n),dtype=np.dtype([('n','<3f4'),('v','<3,3f4'),('a','<u2')]),count=n)
        return d['v'].astype(np.float64)

HERO_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"hero")
HERO_JSON=os.path.join(HERO_DIR,"hero.json")
hmset=set(); hero_tris=[]
if os.path.exists(HERO_JSON):
    import json
    heroes=json.load(open(HERO_JSON))
    gz=gmn[2]
    for h in heroes:
        he,hn=utm32(h["lat"],h["lon"]); rad=float(h.get("radius_m",40))
        # LoD2-Gebaeude im Hero-Radius entfernen
        rem=[i for i,b in enumerate(buildings) if math.hypot(b['cx']-he,b['cy']-hn)<rad]
        if not rem:
            print("  ! Hero '%s' ausserhalb des Ausschnitts, uebersprungen"%h["name"]); continue
        hmset.update(rem)
        grd=min(buildings[i]['zmin'] for i in rem)  # Bodenhoehe aus ersetzten Gebaeuden
        sp=os.path.join(HERO_DIR,h["stl"])
        if not os.path.exists(sp):
            print("  ! Hero-STL fehlt: %s (LoD2 nur entfernt, kein Ersatz)"%sp); continue
        V=read_stl(sp)  # (m,3,3)
        vmin=V.reshape(-1,3).min(0); vmax=V.reshape(-1,3).max(0); ext=vmax-vmin
        hs=(float(h["height_m"])/ext[2]) if ext[2]>0 else 1.0   # auf echte Zielhoehe (m) skalieren
        W=(V-vmin)*hs   # Nullpunkt unten, in Metern
        if h.get("rot_deg"):
            th=math.radians(float(h["rot_deg"])); ca,sa=math.cos(th),math.sin(th)
            cx=(W[:,:,0].max())/2; cy=(W[:,:,1].max())/2
            x=W[:,:,0]-cx; y=W[:,:,1]-cy
            W[:,:,0]=x*ca-y*sa+cx; W[:,:,1]=x*sa+y*ca+cy
        # in UTM-Weltkoordinaten setzen: zentriert auf Hero, Basis auf Bodenhoehe
        W[:,:,0]+= he-(W[:,:,0].max()/2); W[:,:,1]+= hn-(W[:,:,1].max()/2); W[:,:,2]+= grd
        Wm=(W-gmn)*s  # ins Modell-mm (gleiche Skalierung wie LoD2)
        hero_tris.append(((he-gmn[0])*s,(hn-gmn[1])*s,Wm.tolist()))
        print("  + Hero '%s': %d LoD2-Gebaeude ersetzt, Detailmodell %.0fmm hoch eingefuegt"%(h["name"],len(rem),Wm[:,:,2].max()-Wm[:,:,2].min()))
if hmset: print("Hero-Overlay: %d Gebaeude durch %d Detailmodelle ersetzt"%(len(hmset),len(hero_tris)))

def box(x0,x1,y0,y1,z0,z1):
    v=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    q=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(3,0,4,7)]; o=[]
    for a,b,c,d in q: o.append((v[a],v[b],v[c])); o.append((v[a],v[c],v[d]))
    return o

HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,"stl"),exist_ok=True)
def write_stl(path,tri_list):
    A=np.array(tri_list,dtype=np.float64)
    nm=np.cross(A[:,1]-A[:,0],A[:,2]-A[:,0]); ln=np.linalg.norm(nm,axis=1); ln[ln==0]=1; nn=nm/ln[:,None]
    with open(path,"wb") as o:
        o.write(b" "*80); o.write(struct.pack("<I",len(A)))
        b=np.zeros(len(A),dtype=np.dtype([('n','<3f4'),('v','<3,3f4'),('a','<u2')]))
        b['n']=nn.astype('<f4'); b['v']=A.astype('<f4'); o.write(b.tobytes())
    return A

# --- Gesamt-STL (LoD2-Masse + Hero-Detailmodelle + ggf. Muenster-Marker) ---
full=[]; mslot=[]
for i,b in enumerate(buildings):
    if i in hmset: continue                       # von Hero-Detailmodell ersetzt
    if i in mset: mslot.append(to_mm(b['t'])); continue
    full.extend(to_mm(b['t']).tolist())
for _,_,tl in hero_tris: full.extend(tl)          # Detailmodelle (Scan/Faller) einmergen
if mslot:
    M=np.concatenate(mslot)
    full.extend(box(M[:,:,0].min(),M[:,:,0].max(),M[:,:,1].min(),M[:,:,1].max(),0,1.5))  # Slot-Marker
A=write_stl(os.path.join(HERE,"stl","altstadt_lod2.stl"),full)
print("Gesamt-STL -> altstadt_lod2.stl  (%d Dreiecke, X%.0f Y%.0f Z%.0f mm)"%(len(A),A[:,:,0].max(),A[:,:,1].max(),A[:,:,2].max()))

# --- Kacheln (TILESxTILES), Gebaeude per Zentroid zuordnen + Grundplatte je Kachel ---
W=A[:,:,0].max(); H=A[:,:,1].max(); tw=W/TILES; th=H/TILES
tiles={}
for i,b in enumerate(buildings):
    if i in mset or i in hmset: continue
    cx=(b['cx']-gmn[0])*s; cy=(b['cy']-gmn[1])*s
    tx=min(TILES-1,int(cx//tw)); ty=min(TILES-1,int(cy//th))
    tiles.setdefault((tx,ty),[]).extend(to_mm(b['t']).tolist())
for hx,hy,tl in hero_tris:   # Hero-Detailmodell seiner Kachel zuordnen
    tx=min(TILES-1,int(hx//tw)); ty=min(TILES-1,int(hy//th))
    tiles.setdefault((tx,ty),[]).extend(tl)
tdir=os.path.join(HERE,"stl","tiles_%dx%d"%(TILES,TILES)); os.makedirs(tdir,exist_ok=True)
for (tx,ty),tl in tiles.items():
    tl=tl+box(tx*tw,(tx+1)*tw,ty*th,(ty+1)*th,-2,0)   # Kachel-Grundplatte
    write_stl(os.path.join(tdir,"t%02d_%02d.stl"%(tx,ty)),tl)
print("Kacheln -> stl/tiles_%dx%d/ (%d Stueck, je ~%.0fx%.0f mm)"%(TILES,TILES,len(tiles),tw,th))

# --- Render (Gesamt, Muenster-frei) ---
nm=np.cross(A[:,1]-A[:,0],A[:,2]-A[:,0]); ln=np.linalg.norm(nm,axis=1); ln[ln==0]=1; nmn=nm/ln[:,None]
az,el=math.radians(38),math.radians(32)
Rz=np.array([[math.cos(az),-math.sin(az),0],[math.sin(az),math.cos(az),0],[0,0,1]])
Rx=np.array([[1,0,0],[0,math.cos(el),-math.sin(el)],[0,math.sin(el),math.cos(el)]]); Rr=Rx@Rz
Vr=A@Rr.T; Nn=nmn@Rr.T; L=np.array([0.35,-0.75,0.55]); L/=np.linalg.norm(L)
sh=np.clip(np.abs(Nn@L),0,1)*0.75+0.25; sxv=Vr[:,:,0]; syv=Vr[:,:,2]; depv=Vr[:,:,1]
Wd,Hd,mar=960,720,25; x0r,x1r,y0r,y1r=sxv.min(),sxv.max(),syv.min(),syv.max()
sc=min((Wd-2*mar)/(x1r-x0r),(Hd-2*mar)/(y1r-y0r))
PX=(sxv-x0r)*sc+mar; PY=Hd-1-((syv-y0r)*sc+mar); Z=depv.mean(1)
img=np.full((Hd,Wd),20,np.float64); zb=np.full((Hd,Wd),1e18)
for t in np.argsort(-Z):
    xs0=PX[t]; ys0=PY[t]
    xm=max(0,int(xs0.min())); xM=min(Wd-1,int(xs0.max())+1); ym=max(0,int(ys0.min())); yM=min(Hd-1,int(ys0.max())+1)
    if xM<xm or yM<ym: continue
    x1,y1_=xs0[0],ys0[0]; x2,y2=xs0[1],ys0[1]; x3,y3=xs0[2],ys0[2]
    den=(y2-y3)*(x1-x3)+(x3-x2)*(y1_-y3)
    if abs(den)<1e-9: continue
    gx,gy=np.meshgrid(np.arange(xm,xM+1),np.arange(ym,yM+1))
    a=((y2-y3)*(gx-x3)+(x3-x2)*(gy-y3))/den; bb=((y3-y1_)*(gx-x3)+(x1-x3)*(gy-y3))/den; cc=1-a-bb
    m=(a>=0)&(bb>=0)&(cc>=0)
    if not m.any(): continue
    su=zb[ym:yM+1,xm:xM+1]; si=img[ym:yM+1,xm:xM+1]; up=m&(Z[t]<su); su[up]=Z[t]; si[up]=sh[t]*255
img=img.astype(np.uint8)
H_,Wi=img.shape; raw=b''.join(b'\x00'+img[i].tobytes() for i in range(H_))
ch=lambda ty,d:struct.pack(">I",len(d))+ty+d+struct.pack(">I",zlib.crc32(ty+d)&0xffffffff)
open(os.path.join(HERE,"altstadt_lod2_vorschau.png"),"wb").write(b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack(">IIBBBBB",Wi,H_,8,0,0,0,0))+ch(b'IDAT',zlib.compress(raw,9))+ch(b'IEND',b''))
print("Render -> modelle/altstadt_lod2_vorschau.png")

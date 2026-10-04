#!/usr/bin/env python3
"""
stadt_osm_gen.py — holt echte Gebaeude rund ums Freiburger Muenster aus OpenStreetMap
(Overpass API), extrudiert die Grundrisse auf ihre Hoehe und schreibt eine druckbare STL
+ ein Vorschau-Render. Reine stdlib + numpy. (Wie ein Mini-Cadmapper.)

Ausgabe: modelle/stl/altstadt_muenster.stl  +  modelle/altstadt_vorschau.png
"""
import urllib.request, urllib.parse, json, math, struct, zlib, os
import numpy as np

# --- Ausschnitt um den Muenster (S,W,N,E) ---
S,W,N,E = 47.9940, 7.8505, 47.9975, 7.8560
Q = f"""[out:json][timeout:60];
( way["building"]({S},{W},{N},{E}); );
(._;>;);
out body;"""

print("Hole OSM-Gebaeude (Overpass)...")
data = urllib.parse.urlencode({"data": Q}).encode()
req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=data,
                             headers={"User-Agent":"rc-park-citybuilder"})
j = json.load(urllib.request.urlopen(req, timeout=90))
els = j["elements"]
nodes = {e["id"]:(e["lon"],e["lat"]) for e in els if e["type"]=="node"}
ways  = [e for e in els if e["type"]=="way" and "nodes" in e]
print(f"  {len(ways)} Gebaeude, {len(nodes)} Knoten")

# --- Projektion lon/lat -> Meter (lokal) ---
lat0=(S+N)/2; lon0=(W+E)/2
mlon=math.cos(math.radians(lat0))*111320.0; mlat=110540.0
def proj(lon,lat): return ((lon-lon0)*mlon,(lat-lat0)*mlat)

def height_of(tags):
    if not tags: return 8.0
    if "height" in tags:
        try: return float(str(tags["height"]).split()[0].replace(",","."))
        except: pass
    if "building:levels" in tags:
        try: return float(str(tags["building:levels"]).replace(",","."))*3.2
        except: pass
    t=tags.get("building","")
    if t in ("cathedral","church"): return 30.0
    return 8.0

def earclip(poly):
    n=len(poly)
    if n<3: return []
    idx=list(range(n))
    def a2(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    s=sum(poly[i][0]*poly[(i+1)%n][1]-poly[(i+1)%n][0]*poly[i][1] for i in range(n))
    if s<0: idx.reverse()
    def inside(p,a,b,c):
        d1=a2(a,b,p); d2=a2(b,c,p); d3=a2(c,a,p)
        return not(((d1<0)or(d2<0)or(d3<0)) and ((d1>0)or(d2>0)or(d3>0)))
    tris=[]; guard=0
    while len(idx)>3 and guard<20000:
        guard+=1; m=len(idx); ear=False
        for k in range(m):
            i0,i1,i2=idx[(k-1)%m],idx[k],idx[(k+1)%m]
            a,b,c=poly[i0],poly[i1],poly[i2]
            if a2(a,b,c)<=0: continue
            if any((j not in (i0,i1,i2)) and inside(poly[j],a,b,c) for j in idx): continue
            tris.append((i0,i1,i2)); del idx[k]; ear=True; break
        if not ear: break
    if len(idx)==3: tris.append((idx[0],idx[1],idx[2]))
    return tris

tris=[]  # list of (p1,p2,p3) in meters, z up
for w in ways:
    ring=[nodes[nid] for nid in w["nodes"] if nid in nodes]
    if len(ring)<4: continue
    if ring[0]==ring[-1]: ring=ring[:-1]
    if len(ring)<3: continue
    poly=[proj(lo,la) for lo,la in ring]
    h=height_of(w.get("tags"))
    ct=earclip(poly)
    if not ct: continue
    # Boden (z=0, Normale unten) + Dach (z=h, Normale oben)
    for (i,jx,k) in ct:
        A,B,C=poly[i],poly[jx],poly[k]
        tris.append(((A[0],A[1],0),(C[0],C[1],0),(B[0],B[1],0)))
        tris.append(((A[0],A[1],h),(B[0],B[1],h),(C[0],C[1],h)))
    # Waende
    m=len(poly)
    for e in range(m):
        A=poly[e]; B=poly[(e+1)%m]
        a0=(A[0],A[1],0); b0=(B[0],B[1],0); a1=(A[0],A[1],h); b1=(B[0],B[1],h)
        tris.append((a0,b0,b1)); tris.append((a0,b1,a1))

# Grundplatte (duenn) unter allem
xs=[p[0] for t in tris for p in t]; ys=[p[1] for t in tris for p in t]
x0,x1,y0,y1=min(xs)-5,max(xs)+5,min(ys)-5,max(ys)+5; bt=-2.0
bv=[(x0,y0,bt),(x1,y0,bt),(x1,y1,bt),(x0,y1,bt),(x0,y0,0),(x1,y0,0),(x1,y1,0),(x0,y1,0)]
for a,b,c,d in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(3,0,4,7)]:
    tris.append((bv[a],bv[b],bv[c])); tris.append((bv[a],bv[c],bv[d]))

# --- auf Modellgroesse skalieren (max 180 mm horizontal) ---
A=np.array(tris,dtype=np.float64)       # (n,3,3)
mn=A.reshape(-1,3).min(0)
A=A-mn
s=180.0/max(A[:,:,0].max(),A[:,:,1].max())
A=A*s
print("Modellgroesse mm: X%.0f Y%.0f Z%.0f  (%d Dreiecke)"%(A[:,:,0].max(),A[:,:,1].max(),A[:,:,2].max(),len(A)))

# --- STL schreiben ---
nm=np.cross(A[:,1]-A[:,0],A[:,2]-A[:,0]); ln=np.linalg.norm(nm,axis=1); ln[ln==0]=1; nmn=nm/ln[:,None]
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,"stl"),exist_ok=True)
out=os.path.join(HERE,"stl","altstadt_muenster.stl")
with open(out,"wb") as o:
    o.write(b" "*80); o.write(struct.pack("<I",len(A)))
    buf=np.zeros(len(A),dtype=np.dtype([('n','<3f4'),('v','<3,3f4'),('a','<u2')]))
    buf['n']=nmn.astype('<f4'); buf['v']=A.astype('<f4'); o.write(buf.tobytes())
print("STL ->",out)

# --- Render (3/4) ---
c=A.mean(1); az,el=math.radians(40),math.radians(28)
Rz=np.array([[math.cos(az),-math.sin(az),0],[math.sin(az),math.cos(az),0],[0,0,1]])
Rx=np.array([[1,0,0],[0,math.cos(el),-math.sin(el)],[0,math.sin(el),math.cos(el)]]); R=Rx@Rz
P=c@R.T; Nn=nmn@R.T; sx,sy,dep=P[:,0],P[:,2],P[:,1]
L=np.array([0.3,-0.8,0.5]); L/=np.linalg.norm(L); sh=np.clip(Nn@L,0,1)*0.8+0.2
Wd,Hd,mar=900,680,30
x0r,x1r,y0r,y1r=sx.min(),sx.max(),sy.min(),sy.max()
sc=min((Wd-2*mar)/(x1r-x0r),(Hd-2*mar)/(y1r-y0r))
px=((sx-x0r)*sc+mar).astype(int); py=(Hd-1-((sy-y0r)*sc+mar)).astype(int)
img=np.full((Hd,Wd),26,np.uint8); o2=np.argsort(-dep); px,py,sh=px[o2],py[o2],sh[o2]; val=(sh*255).astype(np.uint8)
for dx in(0,1):
  for dy in(0,1): img[np.clip(py+dy,0,Hd-1),np.clip(px+dx,0,Wd-1)]=val
def png(fn,a):
    H,Wi=a.shape; raw=b''.join(b'\x00'+a[i].tobytes() for i in range(H))
    ch=lambda t,d:struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    open(fn,"wb").write(b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack(">IIBBBBB",Wi,H,8,0,0,0,0))+ch(b'IDAT',zlib.compress(raw,9))+ch(b'IEND',b''))
png(os.path.join(HERE,"altstadt_vorschau.png"),img)
print("Render -> modelle/altstadt_vorschau.png")

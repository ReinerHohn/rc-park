#!/usr/bin/env python3
"""
laser_grundplatte.py — Stadt-Grundriss (Strassen, Baechle, Gebaeude-Footprints, Plaetze) aus
OpenStreetMap als LASER-SVG, DECKUNGSGLEICH zu den LoD2-Druckkacheln (gleiche UTM32-Projektion
+ Ursprung + Skalierung aus modelle/stl/altstadt_meta.json). So kommt der Boden+Strassenraster
aus dem Laser, die Haeuser aus dem Drucker — und beides passt ohne Nacharbeit zusammen.

Ausgabe:
  modelle/laser/grundplatte_uebersicht.svg   (ganze Platte W x H mm, alle Layer + Kachelraster)
  modelle/laser/tiles/t##_##.svg             (je Kachel, passend zur Druckkachel tiles_NxN)
  modelle/laser_grundplatte_vorschau.png     (Farb-Preview zum Anschauen)

Layer/Farben (Laser): schnitt=rot (Plattenrand), raster=blau gestrichelt (Kachelgrenzen, Score),
  strassen=schwarz, baechle=cyan, haeuser=grau (Gravur-Outlines).
stdlib + numpy. Overpass mit Cache + Server-Fallback.
Datenbasis Grundriss: © OpenStreetMap-Mitwirkende (ODbL).
"""
import urllib.request, urllib.parse, json, math, struct, zlib, os
import numpy as np

HERE=os.path.dirname(os.path.abspath(__file__))
META=os.path.join(HERE,"stl","altstadt_meta.json")
if not os.path.exists(META):
    raise SystemExit("Fehlt: %s  -> erst lod2_gen.py laufen lassen (RADIUS=700 TILES=6 MAXMM=1200)"%META)
m=json.load(open(META))
GMNX,GMNY=m["gmn"][0],m["gmn"][1]; S=m["scale_mm_per_m"]
Wmm,Hmm,tw,th,TILES=m["W_mm"],m["H_mm"],m["tw_mm"],m["th_mm"],m["TILES"]
Slat,Wlon,Nlat,Elon=m["bbox_SWNE"]

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

def to_mm(lat,lon):
    E,Nn=utm32(lat,lon); return (E-GMNX)*S,(Nn-GMNY)*S   # x rechts, y nach Norden (mm)

# --- OSM holen (Strassen, Baechle, Gebaeude) ---
Q=f"""[out:json][timeout:120];
(
  way["highway"]({Slat},{Wlon},{Nlat},{Elon});
  way["waterway"]({Slat},{Wlon},{Nlat},{Elon});
  way["building"]({Slat},{Wlon},{Nlat},{Elon});
);
(._;>;);
out body;"""
CACHE="/tmp/osm_laser_grundplatte.json"
if os.path.exists(CACHE):
    print("OSM aus Cache..."); j=json.load(open(CACHE))
else:
    print("Hole OSM-Grundriss (Overpass)...")
    data=urllib.parse.urlencode({"data":Q}).encode()
    eps=["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter",
         "https://lz4.overpass-api.de/api/interpreter"]
    j=None
    for ep in eps:
        try:
            req=urllib.request.Request(ep,data=data,headers={"User-Agent":"rc-park-laser"})
            j=json.load(urllib.request.urlopen(req,timeout=180)); break
        except Exception as e: print("  Server fehlgeschlagen:",ep.split('/')[2],e)
    if j is None: raise SystemExit("Overpass nicht erreichbar - spaeter erneut")
    json.dump(j,open(CACHE,"w"))
els=j["elements"]
nodes={e["id"]:(e["lat"],e["lon"]) for e in els if e["type"]=="node"}
ways=[e for e in els if e["type"]=="way" and "nodes" in e]
print("  %d Wege, %d Knoten"%(len(ways),len(nodes)))

# --- kategorisieren -> Polylinien in mm ---
strassen=[]; baechle=[]; haeuser=[]
for w in ways:
    tg=w.get("tags") or {}
    pts=[to_mm(*nodes[n]) for n in w["nodes"] if n in nodes]
    if len(pts)<2: continue
    if "building" in tg: haeuser.append(pts)
    elif "waterway" in tg: baechle.append(pts)
    elif "highway" in tg:
        if tg["highway"] in ("motorway","trunk","construction"): continue
        strassen.append(pts)
print("  Strassen %d / Baechle %d / Haeuser %d"%(len(strassen),len(baechle),len(haeuser)))

# ============================ SVG schreiben ============================
os.makedirs(os.path.join(HERE,"laser","tiles"),exist_ok=True)
def ysvg(y): return Hmm-y   # SVG y nach unten -> Norden oben

def poly_svg(pts,close=False):
    d="M "+" L ".join("%.2f,%.2f"%(x,ysvg(y)) for x,y in pts)
    return d+(" Z" if close else "")

def write_svg(path,x0,y0,w,h,clip=False):
    L=['<?xml version="1.0" encoding="UTF-8"?>',
       '<svg xmlns="http://www.w3.org/2000/svg" width="%.2fmm" height="%.2fmm" viewBox="%.2f %.2f %.2f %.2f">'
       %(w,h,x0,ysvg(y0+h),w,h),
       '<!-- Laser: schnitt=rot Plattenrand, raster=blau Kachelgrenze(Score), strassen=schwarz, baechle=cyan, haeuser=grau. Datenbasis (c) OpenStreetMap ODbL. -->']
    cp=""
    if clip:
        L.append('<clipPath id="c"><rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"/></clipPath>'%(x0,ysvg(y0+h),w,h))
        cp=' clip-path="url(#c)"'
    L.append('<g%s fill="none" stroke-linecap="round" stroke-linejoin="round">'%cp)
    # Gravur: Haeuser (grau), Baechle (cyan), Strassen (schwarz)
    L.append('<g stroke="#999999" stroke-width="0.3">')
    for p in haeuser: L.append('<path d="%s"/>'%poly_svg(p,close=True))
    L.append('</g>')
    L.append('<g stroke="#00b0d0" stroke-width="0.5">')
    for p in baechle: L.append('<path d="%s"/>'%poly_svg(p))
    L.append('</g>')
    L.append('<g stroke="#000000" stroke-width="0.6">')
    for p in strassen: L.append('<path d="%s"/>'%poly_svg(p))
    L.append('</g>')
    L.append('</g>')
    # Kachelraster (Score, blau gestrichelt)
    L.append('<g fill="none" stroke="#2040ff" stroke-width="0.4" stroke-dasharray="3,2">')
    for i in range(TILES+1):
        gx=i*tw
        if x0-0.01<=gx<=x0+w+0.01: L.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f"/>'%(gx,ysvg(y0),gx,ysvg(y0+h)))
    for iy in range(TILES+1):
        gy=iy*th
        if y0-0.01<=gy<=y0+h+0.01: L.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f"/>'%(x0,ysvg(gy),x0+w,ysvg(gy)))
    L.append('</g>')
    # Schnitt: Plattenrand (rot)
    L.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" stroke="#ff0000" stroke-width="0.4"/>'
             %(x0,ysvg(y0+h),w,h))
    L.append('</svg>')
    open(path,"w").write("\n".join(L))

write_svg(os.path.join(HERE,"laser","grundplatte_uebersicht.svg"),0,0,Wmm,Hmm)
print("SVG -> modelle/laser/grundplatte_uebersicht.svg (%.0fx%.0f mm)"%(Wmm,Hmm))
nt=0
for tx in range(TILES):
    for ty in range(TILES):
        write_svg(os.path.join(HERE,"laser","tiles","t%02d_%02d.svg"%(tx,ty)),tx*tw,ty*th,tw,th,clip=True); nt+=1
print("Kachel-SVGs -> modelle/laser/tiles/ (%d, je %.0fx%.0f mm, passend zu tiles_%dx%d)"%(nt,tw,th,TILES,TILES))

# ============================ Farb-Preview PNG ============================
PW=1100; sc=PW/Wmm; PH=int(Hmm*sc)
img=np.full((PH,PW,3),255,np.uint8)
def draw(pts,color,close=False):
    q=list(pts)+([pts[0]] if close and len(pts)>2 else [])
    for i in range(len(q)-1):
        x1,y1=q[i]; x2,y2=q[i+1]
        px1=x1*sc; py1=(Hmm-y1)*sc; px2=x2*sc; py2=(Hmm-y2)*sc
        n=int(max(abs(px2-px1),abs(py2-py1)))+1
        xs=np.linspace(px1,px2,n).astype(int); ys=np.linspace(py1,py2,n).astype(int)
        ok=(xs>=0)&(xs<PW)&(ys>=0)&(ys<PH); img[ys[ok],xs[ok]]=color
for p in haeuser: draw(p,(170,170,170),close=True)
for p in baechle: draw(p,(0,150,210))
for p in strassen: draw(p,(20,20,20))
# Kachelraster blau
for i in range(TILES+1):
    gx=int(i*tw*sc)
    if 0<=gx<PW: img[:,gx]=(80,120,255)
for iy in range(TILES+1):
    gy=int((Hmm-iy*th)*sc)
    if 0<=gy<PH: img[gy,:]=(80,120,255)
raw=b''.join(b'\x00'+img[i].tobytes() for i in range(PH))
ch=lambda t,d:struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
open(os.path.join(HERE,"laser_grundplatte_vorschau.png"),"wb").write(
    b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack(">IIBBBBB",PW,PH,8,2,0,0,0))+ch(b'IDAT',zlib.compress(raw,9))+ch(b'IEND',b''))
print("Preview -> modelle/laser_grundplatte_vorschau.png")

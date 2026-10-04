#!/usr/bin/env python3
"""
lod2_gen.py — liest das amtliche LoD2-CityGML (Freiburg) und baut aus den ECHTEN
Dachflaechen (Sattel/Walm/Mansarde) einen Altstadt-Ausschnitt ums Muenster als STL.
Streaming-Parse (memory-safe) + UTM32-Umrechnung ohne pyproj. stdlib + numpy.

Ausgabe: modelle/stl/altstadt_lod2.stl + modelle/altstadt_lod2_vorschau.png
"""
import xml.etree.ElementTree as ET
import math, struct, zlib, os
import numpy as np

GML="/tmp/freiburg_lod2.gml"
# --- Muenster WGS84 -> UTM32 (EPSG:25832, GRS80) ---
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
ME,MN=utm32(47.9956970,7.8535034); R=250.0
X0,X1,Y0,Y1=ME-R,ME+R,MN-R,MN+R
print("Muenster UTM32 E=%.1f N=%.1f  bbox +-%.0fm"%(ME,MN,R))

def lname(t): return t.split('}')[-1]

tris=[]; kept=0; seen=0
ctx=ET.iterparse(GML, events=('start','end'))
ev,root=next(ctx)
for ev,elem in ctx:
    if ev!='end': continue
    t=lname(elem.tag)
    if t in ("Building","BuildingPart"):
        seen+=1
        polys=[]
        for pl in elem.iter():
            if lname(pl.tag)=="posList" and pl.text:
                n=pl.text.split()
                if len(n)>=9:
                    pts=[(float(n[i]),float(n[i+1]),float(n[i+2])) for i in range(0,len(n)-2,3)]
                    polys.append(pts)
        elem.clear()
        if not polys: continue
        # Lage ueber ersten Punkt
        fx,fy=polys[0][0][0],polys[0][0][1]
        if not (X0<=fx<=X1 and Y0<=fy<=Y1): continue
        kept+=1
        for ring in polys:
            if len(ring)>=4 and ring[0]==ring[-1]: ring=ring[:-1]
            if len(ring)<3: continue
            a0=ring[0]
            for i in range(1,len(ring)-1):
                tris.append((a0,ring[i],ring[i+1]))   # Fan (planare Flaeche)
        if seen%20000==0:
            root.clear(); print("  ...%d Gebaeude gescannt, %d im Bereich"%(seen,kept))
print("Fertig: %d Gebaeude total, %d im Muenster-Bereich, %d Dreiecke"%(seen,kept,len(tris)))

if not tris: raise SystemExit("keine Flaechen im Bereich gefunden")
A=np.array(tris,dtype=np.float64)
A[:,:,0]-=X0; A[:,:,1]-=Y0; A[:,:,2]-=A[:,:,2].min()
s=180.0/max(A[:,:,0].max(),A[:,:,1].max()); A=A*s
print("Modellgroesse mm: X%.0f Y%.0f Z%.0f"%(A[:,:,0].max(),A[:,:,1].max(),A[:,:,2].max()))

nm=np.cross(A[:,1]-A[:,0],A[:,2]-A[:,0]); ln=np.linalg.norm(nm,axis=1); ln[ln==0]=1; nmn=nm/ln[:,None]
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,"stl"),exist_ok=True)
out=os.path.join(HERE,"stl","altstadt_lod2.stl")
with open(out,"wb") as o:
    o.write(b" "*80); o.write(struct.pack("<I",len(A)))
    buf=np.zeros(len(A),dtype=np.dtype([('n','<3f4'),('v','<3,3f4'),('a','<u2')]))
    buf['n']=nmn.astype('<f4'); buf['v']=A.astype('<f4'); o.write(buf.tobytes())
print("STL ->",out)

# --- Render (gefuellte Dreiecke, Z-Buffer) ---
az,el=math.radians(38),math.radians(32)
Rz=np.array([[math.cos(az),-math.sin(az),0],[math.sin(az),math.cos(az),0],[0,0,1]])
Rx=np.array([[1,0,0],[0,math.cos(el),-math.sin(el)],[0,math.sin(el),math.cos(el)]]); Rr=Rx@Rz
Vr=A@Rr.T; Nn=nmn@Rr.T
L=np.array([0.35,-0.75,0.55]); L/=np.linalg.norm(L); sh=np.clip(np.abs(Nn@L),0,1)*0.75+0.25
sxv=Vr[:,:,0]; syv=Vr[:,:,2]; depv=Vr[:,:,1]
Wd,Hd,mar=960,720,25
x0r,x1r,y0r,y1r=sxv.min(),sxv.max(),syv.min(),syv.max()
sc=min((Wd-2*mar)/(x1r-x0r),(Hd-2*mar)/(y1r-y0r))
PX=(sxv-x0r)*sc+mar; PY=Hd-1-((syv-y0r)*sc+mar); Z=depv.mean(1)
img=np.full((Hd,Wd),20,np.float64); zb=np.full((Hd,Wd),1e18)
for t in np.argsort(-Z):
    xs0=PX[t]; ys0=PY[t]
    xmin=max(0,int(np.floor(xs0.min()))); xmax=min(Wd-1,int(np.ceil(xs0.max())))
    ymin=max(0,int(np.floor(ys0.min()))); ymax=min(Hd-1,int(np.ceil(ys0.max())))
    if xmax<xmin or ymax<ymin: continue
    x1,y1_=xs0[0],ys0[0]; x2,y2=xs0[1],ys0[1]; x3,y3=xs0[2],ys0[2]
    den=(y2-y3)*(x1-x3)+(x3-x2)*(y1_-y3)
    if abs(den)<1e-9: continue
    gx,gy=np.meshgrid(np.arange(xmin,xmax+1),np.arange(ymin,ymax+1))
    a=((y2-y3)*(gx-x3)+(x3-x2)*(gy-y3))/den; b=((y3-y1_)*(gx-x3)+(x1-x3)*(gy-y3))/den; cc=1-a-b
    m=(a>=0)&(b>=0)&(cc>=0)
    if not m.any(): continue
    sub=zb[ymin:ymax+1,xmin:xmax+1]; subi=img[ymin:ymax+1,xmin:xmax+1]
    upd=m&(Z[t]<sub); sub[upd]=Z[t]; subi[upd]=sh[t]*255
img=img.astype(np.uint8)
def png(fn,arr):
    H,Wi=arr.shape; raw=b''.join(b'\x00'+arr[i].tobytes() for i in range(H))
    ch=lambda ty,d:struct.pack(">I",len(d))+ty+d+struct.pack(">I",zlib.crc32(ty+d)&0xffffffff)
    open(fn,"wb").write(b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack(">IIBBBBB",Wi,H,8,0,0,0,0))+ch(b'IDAT',zlib.compress(raw,9))+ch(b'IEND',b''))
png(os.path.join(HERE,"altstadt_lod2_vorschau.png"),img)
print("Render -> modelle/altstadt_lod2_vorschau.png")

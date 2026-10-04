#!/usr/bin/env python3
"""
terrain_gen.py — Schwarzwald-Gelaende-Sockel um Freiburg aus echten Hoehendaten
(opentopodata SRTM 30m) -> druckbare STL + Render. Markiert die Altstadt-Lage.
stdlib + numpy. (Wie TouchTerrain, nur direkt hier.)
"""
import urllib.request, json, math, struct, zlib, os, time
import numpy as np

# Bbox um Freiburg (Tal + Schwarzwald-Haenge Richtung Schlossberg/Schauinsland)
S,W,N,E = 47.940, 7.800, 48.030, 7.950
G = 60                      # Gitter GxG
EXAG = float(os.environ.get("EXAG","1.3"))   # Hoehenueberhoehung
MAXMM = 220.0               # groesste Kante in mm
MUE = (47.9956970, 7.8535034)

lats=np.linspace(S,N,G); lons=np.linspace(W,E,G)
pts=[(la,lo) for la in lats for lo in lons]
print("Hole %d Hoehenpunkte (opentopodata SRTM30m)..."%len(pts))
Z=np.zeros(len(pts))
for b in range(0,len(pts),100):
    chunk=pts[b:b+100]
    loc="|".join("%.6f,%.6f"%(la,lo) for la,lo in chunk)
    url="https://api.opentopodata.org/v1/srtm30m?locations="+loc
    for attempt in range(4):
        try:
            r=json.load(urllib.request.urlopen(url,timeout=60))
            for k,res in enumerate(r["results"]):
                e=res.get("elevation"); Z[b+k]=e if e is not None else 0
            break
        except Exception as ex:
            if attempt==3: raise
            time.sleep(2)
    time.sleep(1.1)   # Rate-Limit opentopodata (1 Anfrage/s)
    print("  %d/%d"%(min(b+100,len(pts)),len(pts)))
Z=Z.reshape(G,G)
print("Hoehe min %.0f max %.0f m (Relief %.0f m)"%(Z.min(),Z.max(),Z.max()-Z.min()))

# lon/lat -> Meter (lokal)
lat0=(S+N)/2; mlon=math.cos(math.radians(lat0))*111320; mlat=110540
X=np.zeros((G,G)); Y=np.zeros((G,G))
for i in range(G):
    for j in range(G):
        X[i,j]=(lons[j]-W)*mlon; Y[i,j]=(lats[i]-S)*mlat
Zm=(Z-Z.min())*EXAG

tris=[]
def q(a,b,c): tris.append((a,b,c))
# Oberflaeche
for i in range(G-1):
    for j in range(G-1):
        p00=(X[i,j],Y[i,j],Zm[i,j]); p01=(X[i,j+1],Y[i,j+1],Zm[i,j+1])
        p10=(X[i+1,j],Y[i+1,j],Zm[i+1,j]); p11=(X[i+1,j+1],Y[i+1,j+1],Zm[i+1,j+1])
        q(p00,p01,p11); q(p00,p11,p10)
base=-max(30.0,(Zm.max())*0.15)
# Skirt (4 Raender) + Boden
def edge_wall(idx):
    for k in range(len(idx)-1):
        (xa,ya,za)=idx[k]; (xb,yb,zb)=idx[k+1]
        q((xa,ya,za),(xb,yb,zb),(xb,yb,base)); q((xa,ya,za),(xb,yb,base),(xa,ya,base))
top_edges=[ [(X[0,j],Y[0,j],Zm[0,j]) for j in range(G)],
            [(X[G-1,j],Y[G-1,j],Zm[G-1,j]) for j in range(G-1,-1,-1)],
            [(X[i,0],Y[i,0],Zm[i,0]) for i in range(G-1,-1,-1)],
            [(X[i,G-1],Y[i,G-1],Zm[i,G-1]) for i in range(G)] ]
for e in top_edges: edge_wall(e)
x0,x1,y0,y1=X.min(),X.max(),Y.min(),Y.max()
q((x0,y0,base),(x1,y1,base),(x1,y0,base)); q((x0,y0,base),(x0,y1,base),(x1,y1,base))

# Altstadt-Marker (kleiner Pfosten an Muenster-Lage)
mx=(MUE[1]-W)*mlon; my=(MUE[0]-S)*mlat
# naechster Gitter-Z fuer Marker-Basis
ii=int((MUE[0]-S)/(N-S)*(G-1)); jj=int((MUE[1]-W)/(E-W)*(G-1)); mz=Zm[ii,jj]
r=200
for dx,dy in [(-r,-r),(r,-r),(r,r),(-r,r)]:
    pass
mk=[(mx-r,my-r),(mx+r,my-r),(mx+r,my+r),(mx-r,my+r)]
for k in range(4):
    (ax,ay)=mk[k]; (bx,by)=mk[(k+1)%4]
    q((ax,ay,mz),(bx,by,mz),(bx,by,mz+400)); q((ax,ay,mz),(bx,by,mz+400),(ax,ay,mz+400))
q((mk[0][0],mk[0][1],mz+400),(mk[1][0],mk[1][1],mz+400),(mk[2][0],mk[2][1],mz+400))
q((mk[0][0],mk[0][1],mz+400),(mk[2][0],mk[2][1],mz+400),(mk[3][0],mk[3][1],mz+400))

A=np.array(tris,dtype=np.float64)
A[:,:,:2]-=A[:,:,:2].reshape(-1,2).min(0); A[:,:,2]-=A[:,:,2].min()
s=MAXMM/max(A[:,:,0].max(),A[:,:,1].max()); A=A*s
print("Modellgroesse mm: X%.0f Y%.0f Z%.0f"%(A[:,:,0].max(),A[:,:,1].max(),A[:,:,2].max()))

HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(HERE,"stl"),exist_ok=True)
nm=np.cross(A[:,1]-A[:,0],A[:,2]-A[:,0]); ln=np.linalg.norm(nm,axis=1); ln[ln==0]=1; nmn=nm/ln[:,None]
with open(os.path.join(HERE,"stl","schwarzwald_sockel.stl"),"wb") as o:
    o.write(b" "*80); o.write(struct.pack("<I",len(A)))
    bf=np.zeros(len(A),dtype=np.dtype([('n','<3f4'),('v','<3,3f4'),('a','<u2')]))
    bf['n']=nmn.astype('<f4'); bf['v']=A.astype('<f4'); o.write(bf.tobytes())
print("STL -> modelle/stl/schwarzwald_sockel.stl")

# Render
az,el=math.radians(35),math.radians(30)
Rz=np.array([[math.cos(az),-math.sin(az),0],[math.sin(az),math.cos(az),0],[0,0,1]])
Rx=np.array([[1,0,0],[0,math.cos(el),-math.sin(el)],[0,math.sin(el),math.cos(el)]]); Rr=Rx@Rz
Vr=A@Rr.T; Nn=nmn@Rr.T; L=np.array([0.3,-0.7,0.6]); L/=np.linalg.norm(L)
sh=np.clip(np.abs(Nn@L),0,1)*0.8+0.2; sx=Vr[:,:,0]; sy=Vr[:,:,2]; dep=Vr[:,:,1]
Wd,Hd,mar=960,720,25; x0r,x1r,y0r,y1r=sx.min(),sx.max(),sy.min(),sy.max()
sc=min((Wd-2*mar)/(x1r-x0r),(Hd-2*mar)/(y1r-y0r))
PX=(sx-x0r)*sc+mar; PY=Hd-1-((sy-y0r)*sc+mar); Zd=dep.mean(1)
img=np.full((Hd,Wd),20,np.float64); zb=np.full((Hd,Wd),1e18)
for t in np.argsort(-Zd):
    xs0=PX[t]; ys0=PY[t]; xm=max(0,int(xs0.min())); xM=min(Wd-1,int(xs0.max())+1); ym=max(0,int(ys0.min())); yM=min(Hd-1,int(ys0.max())+1)
    if xM<xm or yM<ym: continue
    x1,y1_=xs0[0],ys0[0]; x2,y2=xs0[1],ys0[1]; x3,y3=xs0[2],ys0[2]
    den=(y2-y3)*(x1-x3)+(x3-x2)*(y1_-y3)
    if abs(den)<1e-9: continue
    gx,gy=np.meshgrid(np.arange(xm,xM+1),np.arange(ym,yM+1))
    a=((y2-y3)*(gx-x3)+(x3-x2)*(gy-y3))/den; bb=((y3-y1_)*(gx-x3)+(x1-x3)*(gy-y3))/den; cc=1-a-bb
    m=(a>=0)&(bb>=0)&(cc>=0)
    if not m.any(): continue
    su=zb[ym:yM+1,xm:xM+1]; si=img[ym:yM+1,xm:xM+1]; up=m&(Zd[t]<su); su[up]=Zd[t]; si[up]=sh[t]*255
img=img.astype(np.uint8); H_,Wi=img.shape; raw=b''.join(b'\x00'+img[i].tobytes() for i in range(H_))
ch=lambda ty,d:struct.pack(">I",len(d))+ty+d+struct.pack(">I",zlib.crc32(ty+d)&0xffffffff)
open(os.path.join(HERE,"schwarzwald_sockel_vorschau.png"),"wb").write(b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack(">IIBBBBB",Wi,H_,8,0,0,0,0))+ch(b'IDAT',zlib.compress(raw,9))+ch(b'IEND',b''))
print("Render -> modelle/schwarzwald_sockel_vorschau.png")

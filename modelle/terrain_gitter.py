#!/usr/bin/env python3
"""terrain_gitter.py - Heightmap/STL -> grobes Rippen-Waffelgitter (Gelaende-Former fuer Gips/Gipsbinden).

Erzeugt senkrechte Rippen in X- und Y-Richtung, deren Oberkanten der Topografie folgen und
sich an den Kreuzungen ueberlappen (verschmelzen beim Slicen). Minimaler Filamentverbrauch,
bockstabil, Gipsbinde haelt perfekt drauf.

Beispiele:
  python3 terrain_gitter.py --stl belchen.stl --foot 220 --exagg 1.5 --ribs 14 --out belchen_gitter.stl
  python3 terrain_gitter.py --png hoehe.png  --foot 220 --height 70 --ribs 14 --out gitter.stl
  python3 terrain_gitter.py                              # Testlauf: synthetischer Berg
"""
import argparse, numpy as np, trimesh

def hf_from_stl(path, n):
    m = trimesh.load(path, force='mesh'); v = m.vertices
    x0,y0,x1,y1 = v[:,0].min(),v[:,1].min(),v[:,0].max(),v[:,1].max()
    ix = np.clip(((v[:,0]-x0)/(x1-x0+1e-9)*(n-1)).astype(int),0,n-1)
    iy = np.clip(((v[:,1]-y0)/(y1-y0+1e-9)*(n-1)).astype(int),0,n-1)
    H = np.full((n,n),-1e9); np.maximum.at(H,(iy,ix),v[:,2])
    from scipy import ndimage
    mask = H<-1e8
    if mask.any():
        idx = ndimage.distance_transform_edt(mask,return_distances=False,return_indices=True); H=H[tuple(idx)]
    H -= H.min()
    return H, (x1-x0)/(y1-y0+1e-9)        # heightfield (mm), Seitenverhaeltnis

def hf_from_png(path, n):
    from PIL import Image
    im = np.asarray(Image.open(path).convert('L').resize((n,n)),dtype=float)
    im -= im.min(); im /= (im.max()+1e-9)
    return im, 1.0                        # 0..1, quadratisch

def hf_synth(n):
    xs=np.linspace(-1,1,n); X,Y=np.meshgrid(xs,xs)
    H=np.exp(-(X**2+Y**2)*2.2)+0.45*np.exp(-(((X-0.5))**2+((Y+0.45))**2)*8)+0.35*np.exp(-(((X+0.45))**2+((Y-0.3))**2)*10)
    H+=0.04*np.random.default_rng(1).random((n,n)); H-=H.min(); H/=H.max()
    return H, 1.0                         # 0..1, quadratisch

def sample(H,u,v):
    n=H.shape[0]; fu=np.clip(u*(n-1),0,n-1); fv=np.clip(v*(n-1),0,n-1)
    i0=np.floor(fv).astype(int); j0=np.floor(fu).astype(int); i1=np.minimum(i0+1,n-1); j1=np.minimum(j0+1,n-1)
    dy=fv-i0; dx=fu-j0
    return (H[i0,j0]*(1-dx)*(1-dy)+H[i0,j1]*dx*(1-dy)+H[i1,j0]*(1-dx)*dy+H[i1,j1]*dx*dy)

def build(H, fx, fy, hscale, nribs, t, minh, msamp=140):
    V=[]; F=[]
    def quad(a,b,c,d):
        i=len(V); V.extend([a,b,c,d]); F.append([i,i+1,i+2]); F.append([i,i+2,i+3])
    def one_rib(axis,pos,u_or_v_fixed):
        cs=np.linspace(0,1,msamp)
        if axis=='y':                      # laeuft entlang Y bei x=pos
            hs=np.maximum(sample(H,u_or_v_fixed*np.ones_like(cs),cs)*hscale,minh); coords=cs*fy
        else:                              # laeuft entlang X bei y=pos
            hs=np.maximum(sample(H,cs,u_or_v_fixed*np.ones_like(cs))*hscale,minh); coords=cs*fx
        def corners(c,h):
            if axis=='y': return (pos-t/2,c,0),(pos+t/2,c,0),(pos+t/2,c,h),(pos-t/2,c,h)
            else:         return (c,pos-t/2,0),(c,pos+t/2,0),(c,pos+t/2,h),(c,pos-t/2,h)
        for k in range(msamp-1):
            BL0,BR0,TR0,TL0=corners(coords[k],hs[k]); BL1,BR1,TR1,TL1=corners(coords[k+1],hs[k+1])
            quad(BL0,TL0,TL1,BL1); quad(BR0,BR1,TR1,TR0); quad(TL0,TR0,TR1,TL1); quad(BL0,BL1,BR1,BR0)
        bl,br,tr,tl=corners(coords[0],hs[0]);  quad(bl,br,tr,tl)
        bl,br,tr,tl=corners(coords[-1],hs[-1]); quad(tl,tr,br,bl)
    for u in np.linspace(0,1,nribs): one_rib('y', u*fx, u)   # Y-Rippen (x=pos)
    for v in np.linspace(0,1,nribs): one_rib('x', v*fy, v)   # X-Rippen (y=pos)
    m=trimesh.Trimesh(np.array(V),np.array(F),process=True); trimesh.repair.fix_normals(m); return m

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--stl'); p.add_argument('--png'); p.add_argument('--out',default='/tmp/terrain_gitter.stl')
    p.add_argument('--foot',type=float,default=200); p.add_argument('--height',type=float,default=60)
    p.add_argument('--exagg',type=float,default=1.0); p.add_argument('--ribs',type=int,default=12)
    p.add_argument('--t',type=float,default=1.2); p.add_argument('--min',type=float,default=3.0)
    p.add_argument('--grid',type=int,default=200)
    a=p.parse_args()
    if a.stl: H,ar=hf_from_stl(a.stl,a.grid); hscale=a.exagg
    elif a.png: H,ar=hf_from_png(a.png,a.grid); hscale=a.height*a.exagg
    else: H,ar=hf_synth(a.grid); hscale=a.height*a.exagg; print('Testlauf: synthetischer Berg')
    fx=a.foot if ar>=1 else a.foot*ar; fy=a.foot if ar<1 else a.foot/ar
    m=build(H,fx,fy,hscale,a.ribs,a.t,a.min)
    e=m.extents
    print(f'Rippen: {a.ribs}x{a.ribs}  Rippendicke {a.t} mm')
    print(f'Masse: {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} mm   Dreiecke: {len(m.faces):,}')
    # grobe Materialschaetzung ggue. Vollkoerper
    vol_ribs=m.volume if m.is_volume else len(m.faces)*0  # Naeherung
    m.export(a.out); print(f'-> {a.out}')

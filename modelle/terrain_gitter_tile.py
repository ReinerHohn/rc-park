#!/usr/bin/env python3
"""terrain_gitter_tile.py - wie terrain_gitter.py, aber zerlegt das Gelaende in
NxN Kacheln (Quadranten), die EINZELN aufs Bett passen und deren Kanten
zusammenpassen (gleiche Heightfield-Koordinate an der Naht -> Hoehen matchen).

Jede Kachel wird auf voller Bettgroesse (per-Kachel-Footprint) gedruckt und
bildet ein 1/N x 1/N Stueck des Berges ab. Zusammengesetzt ergibt sich das
grosse Gelaende (foot x foot/ar).

  python3 terrain_gitter_tile.py --stl belchen_large_real.stl --foot 450 \
      --tiles 2 --exagg 1.7 --ribs 9 --t 1.0 --min 3 --out belchen_xl
  -> belchen_xl_r0c0.stl ... belchen_xl_r1c1.stl
"""
import argparse, numpy as np, trimesh
from terrain_gitter import hf_from_stl, hf_from_png, hf_synth, sample

def build_tile(H, fx, fy, hscale, nribs, t, minh, u0,u1,v0,v1, msamp=160):
    V=[]; F=[]
    def quad(a,b,c,d):
        i=len(V); V.extend([a,b,c,d]); F.append([i,i+1,i+2]); F.append([i,i+2,i+3])
    def one_rib(axis, pos, frac_fixed):
        cs=np.linspace(0,1,msamp)
        if axis=='y':                                   # laeuft entlang Y bei x=pos
            uu=(u0+frac_fixed*(u1-u0))*np.ones_like(cs)
            vv=v0+cs*(v1-v0)
            hs=np.maximum(sample(H,uu,vv)*hscale,minh); coords=cs*fy
        else:                                           # laeuft entlang X bei y=pos
            uu=u0+cs*(u1-u0)
            vv=(v0+frac_fixed*(v1-v0))*np.ones_like(cs)
            hs=np.maximum(sample(H,uu,vv)*hscale,minh); coords=cs*fx
        def corners(c,h):
            if axis=='y': return (pos-t/2,c,0),(pos+t/2,c,0),(pos+t/2,c,h),(pos-t/2,c,h)
            else:         return (c,pos-t/2,0),(c,pos+t/2,0),(c,pos+t/2,h),(c,pos-t/2,h)
        for k in range(msamp-1):
            BL0,BR0,TR0,TL0=corners(coords[k],hs[k]); BL1,BR1,TR1,TL1=corners(coords[k+1],hs[k+1])
            quad(BL0,TL0,TL1,BL1); quad(BR0,BR1,TR1,TR0); quad(TL0,TR0,TR1,TL1); quad(BL0,BL1,BR1,BR0)
        bl,br,tr,tl=corners(coords[0],hs[0]);  quad(bl,br,tr,tl)
        bl,br,tr,tl=corners(coords[-1],hs[-1]); quad(tl,tr,br,bl)
    for p in np.linspace(0,1,nribs): one_rib('y', p*fx, p)   # Y-Rippen
    for p in np.linspace(0,1,nribs): one_rib('x', p*fy, p)   # X-Rippen
    m=trimesh.Trimesh(np.array(V),np.array(F),process=True); trimesh.repair.fix_normals(m); return m

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--stl'); p.add_argument('--png'); p.add_argument('--out',default='/tmp/belchen_xl')
    p.add_argument('--foot',type=float,default=450); p.add_argument('--height',type=float,default=60)
    p.add_argument('--exagg',type=float,default=1.7); p.add_argument('--ribs',type=int,default=9)
    p.add_argument('--t',type=float,default=1.0); p.add_argument('--min',type=float,default=3.0)
    p.add_argument('--grid',type=int,default=240); p.add_argument('--tiles',type=int,default=2)
    a=p.parse_args()
    if a.stl: H,ar=hf_from_stl(a.stl,a.grid); hscale=a.exagg
    elif a.png: H,ar=hf_from_png(a.png,a.grid); hscale=a.height*a.exagg
    else: H,ar=hf_synth(a.grid); hscale=a.height*a.exagg; print('Testlauf: synthetischer Berg')
    full_fx=a.foot if ar>=1 else a.foot*ar
    full_fy=a.foot if ar<1 else a.foot/ar
    N=a.tiles; tfx=full_fx/N; tfy=full_fy/N
    print(f'Voll: {full_fx:.0f} x {full_fy:.0f} mm  |  {N}x{N} Kacheln je {tfx:.0f} x {tfy:.0f} mm (+Rippendicke)')
    # pro Kachel eine Rippen-Ueberlappung teilen: nribs inkl. Endpunkte -> Naht-Rippe doppelt (passt)
    for r in range(N):          # Zeile = v
        for c in range(N):      # Spalte = u
            u0,u1 = c/N,(c+1)/N
            v0,v1 = r/N,(r+1)/N
            m=build_tile(H,tfx,tfy,hscale,a.ribs,a.t,a.min,u0,u1,v0,v1)
            e=m.extents
            fn=f'{a.out}_r{r}c{c}.stl'; m.export(fn)
            print(f'  r{r}c{c}: {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} mm  {len(m.faces):,} tris -> {fn}')

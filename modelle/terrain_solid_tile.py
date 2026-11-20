#!/usr/bin/env python3
"""terrain_solid_tile.py - SOLIDE (durchgehende Oberflaeche) Gelaende-Kacheln.
Kein Rippen-Gitter: jede Kachel ist ein wasserdichter Block (Gelaende-Oberseite
+ 4 Waende + flacher Boden). Naehte matchen (gleiche Heightfield-Koordinate an
der Kante -> Hoehen passen beim Zusammensetzen). Hohl = beim Slicen via
Lightning-Infill (stuetzt nur die Oberseite, Rest leer).

  python3 terrain_solid_tile.py --stl belchen_large_real.stl --foot 480 \
      --tiles 2 --exagg 2.0 --min 3 --res 100 --out belchen_solid
"""
import argparse, numpy as np, trimesh
from terrain_gitter import hf_from_stl, hf_from_png, hf_synth, sample

def build_solid_tile(H, fx, fy, hscale, minh, u0,u1,v0,v1, nx=100, ny=100):
    us=np.linspace(u0,u1,nx); vs=np.linspace(v0,v1,ny)
    xs=np.linspace(0,fx,nx);  ys=np.linspace(0,fy,ny)
    UU,VV=np.meshgrid(us,vs)                      # (ny,nx)
    hh=np.maximum(sample(H,UU.ravel(),VV.ravel())*hscale, minh).reshape(ny,nx)
    XX,YY=np.meshgrid(xs,ys)
    ntop=nx*ny
    top=np.stack([XX.ravel(),YY.ravel(),hh.ravel()],axis=1)
    bot=np.stack([XX.ravel(),YY.ravel(),np.zeros(ntop)],axis=1)
    V=np.vstack([top,bot])
    def t(j,i): return j*nx+i
    def b(j,i): return ntop+j*nx+i
    F=[]
    for j in range(ny-1):
        for i in range(nx-1):
            F.append([t(j,i),t(j,i+1),t(j+1,i+1)]); F.append([t(j,i),t(j+1,i+1),t(j+1,i)])
            F.append([b(j,i),b(j+1,i+1),b(j,i+1)]); F.append([b(j,i),b(j+1,i),b(j+1,i+1)])
    for i in range(nx-1):   # Kante vorne (j=0) + hinten (j=ny-1)
        F.append([t(0,i),b(0,i),b(0,i+1)]); F.append([t(0,i),b(0,i+1),t(0,i+1)])
        J=ny-1; F.append([t(J,i),b(J,i+1),b(J,i)]); F.append([t(J,i),t(J,i+1),b(J,i+1)])
    for j in range(ny-1):   # Kante links (i=0) + rechts (i=nx-1)
        F.append([t(j,0),b(j+1,0),b(j,0)]); F.append([t(j,0),t(j+1,0),b(j+1,0)])
        I=nx-1; F.append([t(j,I),b(j,I),b(j+1,I)]); F.append([t(j,I),b(j+1,I),t(j+1,I)])
    m=trimesh.Trimesh(V,np.array(F),process=True); trimesh.repair.fix_normals(m); return m

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--stl'); p.add_argument('--png'); p.add_argument('--out',default='/tmp/belchen_solid')
    p.add_argument('--foot',type=float,default=480); p.add_argument('--height',type=float,default=60)
    p.add_argument('--exagg',type=float,default=2.0); p.add_argument('--min',type=float,default=3.0)
    p.add_argument('--grid',type=int,default=200); p.add_argument('--tiles',type=int,default=2)
    p.add_argument('--res',type=int,default=100)
    a=p.parse_args()
    if a.stl: H,ar=hf_from_stl(a.stl,a.grid); hscale=a.exagg
    elif a.png: H,ar=hf_from_png(a.png,a.grid); hscale=a.height*a.exagg
    else: H,ar=hf_synth(a.grid); hscale=a.height*a.exagg; print('Testlauf: synthetischer Berg')
    full_fx=a.foot if ar>=1 else a.foot*ar
    full_fy=a.foot if ar<1 else a.foot/ar
    N=a.tiles; tfx=full_fx/N; tfy=full_fy/N
    print(f'Voll: {full_fx:.0f} x {full_fy:.0f} mm | {N}x{N} Kacheln je {tfx:.0f} x {tfy:.0f} mm')
    for r in range(N):
        for c in range(N):
            m=build_solid_tile(H,tfx,tfy,hscale,a.min, c/N,(c+1)/N, r/N,(r+1)/N, a.res,a.res)
            e=m.extents; fn=f'{a.out}_r{r}c{c}.stl'; m.export(fn)
            print(f'  r{r}c{c}: {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} mm  {len(m.faces):,} tris  watertight={m.is_watertight} -> {fn}')

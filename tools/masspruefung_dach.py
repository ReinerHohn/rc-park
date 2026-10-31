#!/usr/bin/env python3
"""Punktweiser Dachvergleich: nur Zellen im 6-m-Umkreis der Spitze (Dach+Spitze), Lage frei gesucht. Nutzung: python masspruefung_dach.py a.stl b.stl ..."""
import sys, numpy as np, trimesh
DOM="/media/oem/scan/tmp/mt_dom/mt_win.npy"; N=60
ref=np.load(DOM)-277.98; pk=np.unravel_index(ref.argmax(),ref.shape)
yy,xx=np.mgrid[:N,:N]; win=np.hypot(yy-pk[0],xx-pk[1])<=4.5
for stl in sys.argv[1:]:
    m=trimesh.load(stl); m.apply_scale(87/1000.0)
    v,f=trimesh.remesh.subdivide_to_size(m.vertices,m.faces,max_edge=0.3,max_iter=14)
    P=v[f].mean(1)
    def H(a,dx,dy):
        c,s=np.cos(np.radians(a)),np.sin(np.radians(a))
        x=c*P[:,0]-s*P[:,1]+dx; y=s*P[:,0]+c*P[:,1]+dy
        ix=np.floor(x+N/2).astype(int); iy=np.floor(N/2-y).astype(int)
        ok=(ix>=0)&(ix<N)&(iy>=0)&(iy<N); h=np.zeros((N,N)); np.maximum.at(h,(iy[ok],ix[ok]),P[ok,2]); return h
    best=(1e9,)
    for a in np.arange(8,24,1.0):
        for dx in np.arange(-2,2.01,.25):
            for dy in np.arange(-2,2.01,.25):
                e=np.abs(H(a,dx,dy)-ref)[win].mean()
                if e<best[0]: best=(e,a,dx,dy)
    h=H(*best[1:]); d=(h-ref)[win]
    print("%-28s |Fehler| %.2f m  Mittel %+.2f  Winkel %.0f  max Modell %.1f"%(stl.split('/')[-1],best[0],d.mean(),best[1],h[win].max()))

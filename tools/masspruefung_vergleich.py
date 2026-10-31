#!/usr/bin/env python3
"""Vergleich Laser (DOM) gegen Modell auf gleichem 1-m-Raster: Flaeche + Mindestrechteck der Turmkomponente je Hoehenschwelle.
Nutzung: python3 tools/masspruefung_vergleich.py [stl]  (Modell-STL in mm bei 1:87)"""
import sys; stl=sys.argv[1] if len(sys.argv)>1 else "modelle/stl/martinstor_v4_1-87.stl"; sys.argv=["x",stl]
sys.path.insert(0,"tools")
import numpy as np, cv2, masspruefung as M
from scipy import ndimage as ndi
yy,xx=np.mgrid[:M.N,:M.N]
def rects(A,pk,ts):
    out={}
    for t in ts:
        lab,n=ndi.label((A>t)&(np.hypot(yy-pk[0],xx-pk[1])<=13)); k=lab[pk]
        if not k: continue
        ys,xs=np.nonzero(lab==k); r=cv2.minAreaRect(np.c_[xs,ys].astype(np.float32)+0.5); out[t]=(len(xs),max(r[1]),min(r[1]))
    return out
ts=(20,24,28,32,36,40,44,48,52)
pr=np.unravel_index(np.argmax(M.ref),M.ref.shape)
best=None
for ph in [(a,b) for a in (-1.0,-0.5,0,0.5,1.0) for b in (-1.0,-0.5,0,0.5,1.0)]:          # Rasterphase des Modells offen -> beste nehmen
    for ang in np.arange(60,92,2.0):
        H=M.hmap(ang,ph[0],ph[1]); pm=np.unravel_index(np.argmax(H),H.shape); Mo=rects(H,pm,ts); R=rects(M.ref,pr,ts)
        e=sum(abs(Mo[t][0]/R[t][0]-1) for t in ts if t in Mo and t in R)
        if best is None or e<best[0]: best=(e,ang,ph,Mo,R,H.max())
e,ang,ph,Mo,R,hm=best
print("Modell-Drehung %.0f Grad, Rasterphase %s; Spitze Laser %.2f m / Modell %.2f m"%(ang,ph,M.ref.max(),hm))
print("  t    Laser m2  Rechteck      Modell m2  Rechteck     Flaechenabweichung")
for t in ts:
    if t in R and t in Mo: print(f"{t:3d}   {R[t][0]:5d}  {R[t][1]:4.1f} x {R[t][2]:4.1f}     {Mo[t][0]:5d}  {Mo[t][1]:4.1f} x {Mo[t][2]:4.1f}     {Mo[t][0]/R[t][0]-1:+.0%}")

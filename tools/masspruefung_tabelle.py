#!/usr/bin/env python3
"""Tabelle Laser gegen Modell (Gesamtflaeche im 9-m-Umkreis um die Spitze, gleiches 1-m-Raster wie das amtliche DOM).
Nutzung: python3 tools/masspruefung_tabelle.py [stl]"""
import sys; stl=sys.argv[1] if len(sys.argv)>1 else "modelle/stl/martinstor_v4_1-87.stl"; sys.argv=["x",stl]; sys.path.insert(0,"tools")
import numpy as np, masspruefung as M, trimesh
print("wasserdicht:", trimesh.load(stl).is_watertight)
yy,xx=np.mgrid[:M.N,:M.N]; pr=np.unravel_index(np.argmax(M.ref),M.ref.shape)
TS=(20,24,28,32,35,38,40,42,44,46,48,50,52)
ar=lambda A,pk,t:int(((A>t)&(np.hypot(yy-pk[0],xx-pk[1])<=9)).sum())
best=None
for ph in [(a,b) for a in (-1,-.5,0,.5,1) for b in (-1,-.5,0,.5,1)]:
  for ang in np.arange(70,100,2.0):
    H=M.hmap(ang,*ph); pm=np.unravel_index(np.argmax(H),H.shape)
    e=sum(abs(ar(H,pm,t)/max(ar(M.ref,pr,t),1)-1) for t in TS)
    if best is None or e<best[0]: best=(e,ang,ph,H,pm)
e,ang,ph,H,pm=best; print("Spitze Laser %.2f m  Modell %.2f m  (Drehung %.0f, Phase %s)"%(M.ref.max(),H.max(),ang,ph))
print("  t   Laser m2  Modell m2  Abw.")
d=[]
for t in TS:
    a,b=ar(M.ref,pr,t),ar(H,pm,t); d.append(abs(b/max(a,1)-1)); print(f"{t:3d}   {a:5d}     {b:5d}   {b/max(a,1)-1:+.0%}")
print("mittlere Flaechenabweichung %.0f %%  (Median %.0f %%)"%(100*np.mean(d),100*np.median(d)))

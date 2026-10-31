#!/usr/bin/env python3
"""masspruefung_fit.py - Parameter des Martinstors an amtliches LiDAR-DOM anpassen (Proxy-Modell aus Quadern/Kegelstuempfen).
Gibt die besten Parameter, die Flaechenkurve und die Restabweichung aus. Raster wie beim Laser: Zelle zaehlt, wenn irgendwo darin Hoehe > t."""
import numpy as np, sys
from scipy import ndimage as ndi
from scipy.optimize import minimize
ref=np.load("/media/oem/scan/tmp/mt_dom/mt_win.npy")-277.98; N=60
pk=np.unravel_index(np.argmax(ref),ref.shape); yy,xx=np.mgrid[:N,:N]; disc=np.hypot(yy-pk[0],xx-pk[1])<=9
TS=np.array([20,24,28,32,35,38,40,42,44,46,48,50,52],float)
AZ=np.radians(14.0)          # Durchfahrtsachse (Laser: Kanten bei 14 Grad)
SUB=4                         # Unterraster je Laserzelle
G=np.arange(-N/2*SUB,N/2*SUB)/SUB+0.5/SUB
def frame(cx,cy):
    X,Y=np.meshgrid(G,G); X=X-cx; Y=N/2-0.0-(0)-Y*0  # Platzhalter
def heightmap(P,cx=0.0,cy=0.0):
    X,Y=np.meshgrid(G+cx,G[::-1]+cy)               # Zeile 0 = Nord
    c,s=np.cos(AZ),np.sin(AZ)
    u=c*Y+s*X; v=-s*Y+c*X                           # u: Durchfahrtsachse (Nord-Sued ~ 14 Grad), v: Fassadenbreite
    H=np.zeros_like(u)
    def rect(hx,hy,z0,z1):                          # Quader
        m=(abs(u)<=hx)&(abs(v)<=hy); return np.where(m,z1,0.0)
    def frust(hx0,hy0,hx1,hy1,z0,z1):               # Kegelstumpf (Rechteck): Hoehe = z, bis zu der der Punkt noch drin liegt
        t=np.maximum((abs(u)-hx0)/(hx1-hx0+1e-9),(abs(v)-hy0)/(hy1-hy0+1e-9)) if False else None
        fx=np.where(abs(hx1-hx0)<1e-9,1.0,(abs(u)-hx0)/(hx1-hx0)); fy=np.where(abs(hy1-hy0)<1e-9,1.0,(abs(v)-hy0)/(hy1-hy0))
        tt=np.clip(np.maximum(np.where(abs(u)<=min(hx0,hx1),0,fx),np.where(abs(v)<=min(hy0,hy1),0,fy)),0,None)
        ok=(abs(u)<=np.maximum(hx0,hx1))&(abs(v)<=np.maximum(hy0,hy1))&(tt<=1.0)
        return np.where(ok,z0+(1-tt)*(z1-z0) if hx1<hx0 else z0+tt*(z1-z0),0.0)
    DB,WB,D,W,ZZ,Zc,GX,GY,GZ1,RZ1,T1,Hc=P
    ZB=8.0
    H=np.maximum(H,frust(DB/2,WB/2,D/2,W/2,ZB,ZZ))                      # Schaft (verjuengt)
    H=np.maximum(H,rect(D/2,W/2,ZZ,Zc))                                 # Zinnen
    H=np.maximum(H,rect(GX/2,GY/2,Zc,GZ1))                              # Glockenstock
    H=np.maximum(H,frust(GX/2+0.4,GY/2+0.4,0.4,1.3,GZ1,RZ1))            # Dach
    for sx in (-1,1):                                                   # vier Erker
        for sy in (-1,1):
            cu,cv=sx*(D/2-1.6+0.4),sy*(W/2-1.6+0.4)
            m=(abs(u-cu)<=1.6)&(abs(v-cv)<=1.6); H=np.maximum(H,np.where(m,T1,0.0))
            r=np.hypot(u-cu,v-cv); cone=np.clip(1-r/1.6,0,1)*Hc+T1+2.5       # Kegel
            H=np.maximum(H,np.where((r<=1.6)&(cone>T1+2.5),cone,0.0))
    H=np.maximum(H,np.where(np.hypot(u,v)<0.6,54.8-np.hypot(u,v)*10,0.0))   # Dachreiter/Spitze
    return H
def to_cells(H):
    h=H.reshape(N,SUB,N,SUB).max(axis=(1,3)); return h
def areas(h,pkc):
    d=np.hypot(yy-pkc[0],xx-pkc[1])<=9; return np.array([((h>t)&d).sum() for t in TS],float)
A_ref=areas(ref,pk)
def loss(P,verbose=False):
    best=1e9
    for cx in (0,0.5):
        for cy in (0,0.5):
            h=to_cells(heightmap(P,cx,cy)); pm=np.unravel_index(np.argmax(h),h.shape); a=areas(h,pm)
            best=min(best,float(np.sum(((a-A_ref)/np.maximum(A_ref,3.0))**2)))
    return best
if __name__=="__main__":
    P0=np.array([10.2,11.6,9.2,10.8,32.0,33.6,5.2,6.0,38.5,48.4,36.0,3.9])
    lo=np.array([9,10.5,8.5,9.8,29,30.5,3.5,4.5,36,45,32,2.0]); hi=np.array([11.5,13,10.7,12.2,35,36,7.5,8,42,50.5,40,8])
    f=lambda x: loss(np.clip(x,lo,hi))+1e-4*np.sum(((np.clip(x,lo,hi)-x)/1)**2)
    print("Start-Loss %.3f"%loss(P0))
    best=(loss(P0),P0)
    rng=np.random.default_rng(1)
    for k in range(6):
        x0=best[1]*(1+0.04*rng.standard_normal(len(P0))) if k else P0
        r=minimize(f,x0,method="Nelder-Mead",options=dict(maxiter=700,xatol=0.02,fatol=1e-3))
        x=np.clip(r.x,lo,hi); l=loss(x); print(" Lauf",k,"Loss %.3f"%l)
        if l<best[0]: best=(l,x)
    l,P=best; names="DB WB D W ZZ Zc GX GY GZ1 RZ1 T1 Hc".split()
    print("\nBeste Parameter (m):"); [print(f"  {n:4s} {v:6.2f}") for n,v in zip(names,P)]
    h=to_cells(heightmap(P,0,0)); pm=np.unravel_index(np.argmax(h),h.shape); a=areas(h,pm)
    print("\n  t   Laser  Proxy  Abw."); [print(f"{int(t):3d}  {int(r):5d}  {int(m):5d}  {m/max(r,1)-1:+.0%}") for t,r,m in zip(TS,A_ref,a)]
    np.save("/media/oem/scan/tmp/mt_dom/fitP.npy",P)

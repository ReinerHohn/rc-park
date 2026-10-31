import numpy as np, trimesh, cv2
from scipy.spatial import cKDTree
from scipy.optimize import minimize
d=np.load("/tmp/claude-29999/-home-oem-git-rc-park/bf197a0c-a706-4c3e-9f93-17b19691b58c/scratchpad/vggt/vggt.npz")
P=d["pts"].reshape(-1,3); C=d["conf"].reshape(-1); col=(d["cols"].reshape(-1,3)*255).astype(np.uint8)
hsv=cv2.cvtColor(col.reshape(-1,1,3),cv2.COLOR_RGB2HSV).reshape(-1,3)
print("Rohpunkte",len(P),"conf Perzentile",np.percentile(C,[10,50,90]).round(2))
ok=(C>np.percentile(C,40))&np.isfinite(P).all(1)
# Himmel raus: helle, wenig gesaettigte oder blaue Pixel
sky=(hsv[:,1]<40)&(hsv[:,2]>150) | ((hsv[:,0]>95)&(hsv[:,0]<130)&(hsv[:,1]>50))
ok&=~sky
Q=P[ok]; Q=Q[np.linalg.norm(Q-np.median(Q,0),axis=1)<np.percentile(np.linalg.norm(Q-np.median(Q,0),axis=1),90)]; Q=Q[::6]
print("Turmpunkte",len(Q))
mu=Q.mean(0); U,S_,Vt=np.linalg.svd(Q-mu,full_matrices=False); print("Hauptachsen-Streuung",(S_/np.sqrt(len(Q))).round(3))
M=trimesh.load("/home/oem/git/rc-park/modelle/stl/martinstor_v4_1-87.stl"); M.apply_scale(87/1000.0)
c=M.bounds.mean(0); M.apply_translation([-c[0],-c[1],-M.bounds[0,2]])
pm,_=trimesh.sample.sample_surface(M,60000,seed=0); tree=cKDTree(pm)
best=None
for sg in (1,-1):
    up=sg*Vt[0]; a=np.cross(up,[1,0,0]); a/=np.linalg.norm(a); b=np.cross(up,a)
    X=np.c_[(Q-mu)@a,(Q-mu)@b,(Q-mu)@up]; zt=np.percentile(X[:,2],99.5); ext=zt-np.percentile(X[:,2],0.5)
    for h in (35,):                         # sichtbare Turmhoehe in m (unbekannt) -> Startmassstab
        s0=h/ext
        for th in np.arange(0,2*np.pi,np.pi/4):
            def cost(q):
                s,t,tx,ty,tz=q
                if not (0.2*s0<s<5*s0): return 9+abs(s)
                cc,sn=np.cos(t),np.sin(t); x=s*(cc*X[:,0]-sn*X[:,1])+tx; y=s*(sn*X[:,0]+cc*X[:,1])+ty; z=s*(X[:,2]-zt)+54.8+tz
                dd,_=tree.query(np.c_[x,y,z]); dd=np.sort(dd); return dd[:int(.6*len(dd))].mean()
            r=minimize(cost,[s0,th,0,0,0],method="Powell",options=dict(maxiter=500,xtol=1e-3,ftol=1e-5))
            if best is None or r.fun<best[0].fun: best=(r,sg,s0,a,b,up,zt,X)
r,sg,s0,a,b,up,zt,X=best; s,t,tx,ty,tz=r.x
print(f"beste Anpassung: Kosten {r.fun:.3f} m (60%-Mittel), Hoehe-Annahme-Start s0={s0:.2f}, s={s:.3f} (m je Einheit), Drehung {np.degrees(t)%360:.0f} Grad, tz={tz:.2f}")
cc,sn=np.cos(t),np.sin(t); W=np.c_[s*(cc*X[:,0]-sn*X[:,1])+tx,s*(sn*X[:,0]+cc*X[:,1])+ty,s*(X[:,2]-zt)+54.8+tz]
dd,_=tree.query(W)
print("Wolke Hoehe",W[:,2].min().round(1),"bis",W[:,2].max().round(1),"m; Abstand Median",np.median(dd).round(2),"m, P90",np.percentile(dd,90).round(2),"m")
for z0 in range(10,56,5):
    k=(W[:,2]>=z0)&(W[:,2]<z0+5)
    if k.sum()>200: print(f" z {z0:2d}-{z0+5:2d} m  Punkte {k.sum():6d}  Median {np.median(dd[k]):.2f} m  P90 {np.percentile(dd[k],90):.2f} m")
np.save("/tmp/claude-29999/-home-oem-git-rc-park/bf197a0c-a706-4c3e-9f93-17b19691b58c/scratchpad/vggt/W.npy",W)

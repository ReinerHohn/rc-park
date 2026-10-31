import numpy as np, trimesh, torch, math
dev="cuda"; V="/tmp/claude-29999/-home-oem-git-rc-park/bf197a0c-a706-4c3e-9f93-17b19691b58c/scratchpad/vggt10/"
d=np.load(V+"vggt.npz"); ext=d["ext"]; P=d["pts"].reshape(-1,3); C=d["conf"].reshape(-1); import cv2
col=(d["cols"].reshape(-1,3)*255).astype(np.uint8); hsv=cv2.cvtColor(col.reshape(-1,1,3),cv2.COLOR_RGB2HSV).reshape(-1,3)
sky=((hsv[:,1]<40)&(hsv[:,2]>150))|((hsv[:,0]>95)&(hsv[:,0]<130)&(hsv[:,1]>50))
ok=(C>np.percentile(C,40))&np.isfinite(P).all(1)&~sky; Q=P[ok]
r=np.linalg.norm(Q-np.median(Q,0),axis=1); Q=Q[r<np.percentile(r,92)]; Q=Q[np.random.default_rng(0).choice(len(Q),8000,replace=False)]
Rv=ext[7][:,:3]; tv=ext[7][:,3]; Cv=-Rv.T@tv
# Silhouettenkamera 044 (Modellkoordinaten): d, az, el, tz, roll
dd,az0,el,tz,roll=57.9,-1.05,-0.43,26.3,0.0
def Rm_Cm(az):
    tgt=np.array([0,0,tz]); cam=tgt+dd*np.array([math.sin(az)*math.cos(el),-math.cos(az)*math.cos(el),math.sin(el)])
    fwd=tgt-cam; fwd/=np.linalg.norm(fwd); x=np.cross(fwd,[0,0,1]); x/=np.linalg.norm(x); y=np.cross(fwd,x)
    cr,sr=math.cos(roll),math.sin(roll); x2=cr*x+sr*y; y2=-sr*x+cr*y
    return np.array([x2,y2,fwd]),cam
M=trimesh.load("/home/oem/git/rc-park/modelle/stl/martinstor_v4_1-87.stl"); M.apply_scale(87/1000.0)
c=M.bounds.mean(0); M.apply_translation([-c[0],-c[1],-M.bounds[0,2]])
pm,_=trimesh.sample.sample_surface(M,60000,seed=0); pm=pm[::5]; Pm=torch.tensor(pm,dtype=torch.float32,device=dev)
dv=np.linalg.norm(np.median(Q,0)-Cv); s0=dd/dv; print(f"Abstand Kamera-Wolke {dv:.3f} Einheiten, Start s0={s0:.1f} m/Einheit")
def cost_for(Xm):
    X=torch.tensor(Xm,dtype=torch.float32,device=dev); D=torch.cdist(X,Pm).min(1).values.sort().values; return D[:int(.5*len(D))].mean().item(), D.median().item()
res=[]
for k in range(4):
    az=az0+k*math.pi/2; Rm,Cm=Rm_Cm(az); R=Rm.T@Rv
    for s in np.linspace(0.5*s0,1.8*s0,53):
        Xm=s*(Q-Cv)@R.T+Cm; f,med=cost_for(Xm); res.append((f,med,k,s))
res.sort(); print("beste 6 (Kosten=50%-Mittel, Median, Azimut+90*k, s):")
for f,med,k,s in res[:6]: print(f"  {f:.2f} m  {med:.2f} m  k={k} az={math.degrees(az0+k*math.pi/2)%360:.0f} s={s:.1f}")
# Kostenkurve je k (Minimum je Azimut)
for k in range(4): 
    m=min(r for r in res if r[2]==k); print(f" Azimut-Variante {k}: min Kosten {m[0]:.2f} bei s={m[3]:.1f}")
f,med,k,s=res[0]; az=az0+k*math.pi/2; Rm,Cm=Rm_Cm(az); R=Rm.T@Rv; Xm=s*(Q-Cv)@R.T+Cm
print("Hoehe der Wolke",Xm[:,2].min().round(1),"bis",Xm[:,2].max().round(1),"m")
np.save(V+"Xm_anker.npy",Xm)
from scipy.spatial import cKDTree
dist,_=cKDTree(pm).query(Xm)
for z0 in range(10,56,5):
    kk=(Xm[:,2]>=z0)&(Xm[:,2]<z0+5)
    if kk.sum()>100: print(f" z {z0:2d}-{z0+5:2d} m  Punkte {kk.sum():5d}  Median {np.median(dist[kk]):.2f} m  P90 {np.percentile(dist[kk],90):.2f} m")
print("--- Kostenkurve (k=3) ---")
Rm,Cm=Rm_Cm(az0+3*math.pi/2); R=Rm.T@Rv
for s in np.linspace(0.6*s0,1.6*s0,21):
    f,med=cost_for(s*(Q-Cv)@R.T+Cm); print(f" s={s:5.1f}  Kosten {f:.2f} m  Median {med:.2f} m"+("  <==" if abs(s-48.3)<1.4 else ""))

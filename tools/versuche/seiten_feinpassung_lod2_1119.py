import numpy as np, sys, json
from scipy.spatial import cKDTree
sys.path.insert(0,"/home/oem/git/rc-park/tools"); from sfm_lod2_ausrichten import lod2_ziel
d=np.load("/media/oem/rcdaten/tmp/mt_seiten/verbund/verbund_meter.npz"); obj=json.load(open("/home/oem/git/rc-park/modelle/martinstor_gk3/objekt.json")); L,Tn,Tt,_,_,_,Te=lod2_ziel(obj,80.0); W=L[Tt==0][:,:2]; bw=cKDTree(W)
def fein(P, name, runden=40):
    P=P[(np.abs(P[:,0])<85)&(np.abs(P[:,1])<85)&(P[:,2]>2)&(P[:,2]<40)][:,:2]; X=P.copy(); S=1.0; A=np.eye(2); T=np.zeros(2)
    for it in range(runden):
        dd,ix=bw.query(X); thr=max(0.6, np.percentile(dd,60)); m=dd<thr; p,q=X[m],W[ix[m]]
        mp,mq=p.mean(0),q.mean(0); H=(q-mq).T@(p-mp); U,Sg,Vt=np.linalg.svd(H); D=np.diag([1,np.sign(np.linalg.det(U@Vt))]); R=U@D@Vt; s=(Sg*np.diag(D)).sum()/((p-mp)**2).sum()
        s=np.clip(s,0.99,1.01); t=mq-s*R@mp; X=s*X@R.T+t; S*=s; A=R@A; T=s*R@T+t
    dd=bw.query(X)[0]; yaw=np.degrees(np.arctan2(A[1,0],A[0,0])); v=np.linalg.norm(X-P,axis=1)
    print(f"{name:26s}: nach Feinpassung Median {np.median(dd):.2f} m, {100*(dd<1).mean():.0f} % < 1 m | Korrektur: Drehung {yaw:+.1f} Grad, Massstab {S:.3f}, Verschiebung der Punkte Median {np.median(v):.1f} m")
    return S,A,T
fein(d["pa"],"A (Vorderseite)"); r=fein(d["pb"],"B gedreht (Rueckseite)"); fein(d["pbg"],"B geklappt (Kontrolle)")
np.savez("fein_b.npz",S=r[0],A=r[1],T=r[2])

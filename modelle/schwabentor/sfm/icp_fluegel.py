import numpy as np
from scipy.spatial import cKDTree
rng=np.random.default_rng(0)
F=np.load('fluegel_punkte.npy').astype(float)
M=np.load('/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_modell_schwabentor_veto.npy').astype(float)
c=np.median(M[:,:2],axis=0); P=M-np.array([c[0],c[1],0])
wing=(P[:,0]>3.5)&(P[:,1]<-1.5)
A=P[~wing]
Z=lambda t:np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
def icp(S,T,tree,spiegel,it=25):
    best=None
    for yaw in np.deg2rad(np.arange(0,360,20)):
        X=S.copy()
        if spiegel: X[:,0]=-X[:,0]
        X[:,:2]=X[:,:2]@Z(yaw).T
        X[:,:2]+=T[:,:2].mean(0)-X[:,:2].mean(0)   # Schwerpunkt xy auf Ziel
        X[:,2]+=np.median(T[:,2])-np.median(X[:,2])
        for k in range(it):
            d,i=tree.query(X); m=d<np.percentile(d,60)
            X=X+ (T[i[m]]-X[m]).mean(0)*0.7
        d,_=tree.query(X); s=float(np.mean(d<0.3))
        if best is None or s>best[0]: best=(s,np.rad2deg(yaw))
    return best
def lauf(name,S,T):
    S=S[rng.choice(len(S),4000,replace=False)]
    tree=cKDTree(T)
    for sp in (0,1):
        print(name,'Spiegel' if sp else 'Drehung','Anteil<0.3m %.3f, yaw %.0f'%icp(S,T,tree,sp),flush=True)
for zname,T in (('links x<-6',A[(A[:,0]<-6)&(A[:,2]>0)]),('Turm+Mitte',A[(A[:,0]>=-6)&(A[:,0]<3.5)&(A[:,2]>0)])):
    T=T[rng.choice(len(T),min(150000,len(T)),replace=False)]
    print(zname,len(T))
    lauf('Fluegel->'+zname,F,T)
    # Kontrolle: Fremdstueck gleicher Groesse (aus Ziel der anderen Haelfte)
    K=A[(A[:,0]>-3)&(A[:,0]<3)&(A[:,2]>0)]
    lauf('Kontrolle Turmstueck->'+zname,K[rng.choice(len(K),len(F)//4,replace=False)],T)

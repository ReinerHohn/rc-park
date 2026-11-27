import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
HH,T=lade()
hn={i.name:i for i in HH.images.values() if i.has_pose}; tn={i.name:i for i in T.images.values() if i.has_pose}
gem=sorted(set(hn)&set(tn)); X=[];Y=[];W=[]
nkp_ok=0
for n in gem:
    a=tn[n]; b=hn[n]
    pa=a.points2D; pb=b.points2D
    if len(pa)!=len(pb): continue
    nkp_ok+=1
    for k in range(len(pa)):
        if pa[k].has_point3D() and pb[k].has_point3D():
            if np.linalg.norm(np.array(pa[k].xy)-np.array(pb[k].xy))>0.01: continue
            X.append(T.points3D[pa[k].point3D_id].xyz); Y.append(HH.points3D[pb[k].point3D_id].xyz); W.append((n,pa[k].point3D_id,pb[k].point3D_id))
print('Bilder mit gleicher Keypointliste',nkp_ok,'/',len(gem),'Paare',len(X))
X=np.array(X);Y=np.array(Y)
# eindeutige Punktpaare
key={};
for i,(n,a,b) in enumerate(W): key.setdefault((a,b),[]).append(i)
idx=[v[0] for v in key.values()]; print('eindeutige 3D-Paare',len(idx), 'Teilpunkte',len(set(a for a,b in key)),'Hauptpunkte',len(set(b for a,b in key)))
np.savez('paare3d.npz',X=X[idx],Y=Y[idx],nimg=np.array([len(v) for v in key.values()]),ids=np.array(list(key.keys())))

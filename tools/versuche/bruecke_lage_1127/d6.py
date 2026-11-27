import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
from sim3_robust import sim3_meter, anwenden, umeyama
HH,T=lade()
z=np.load('paare3d.npz'); ids=z['ids']; X=z['X']; Y=z['Y']
# Hauptnetz-Stuetze: Spurbilder ohne IMG_
nh=[]; nt=[]; eh=[]
for a,b in ids:
    p=HH.points3D[int(b)]; el=p.track.elements; names=[HH.images[e.image_id].name for e in el]
    nh.append(sum(1 for x in names if not x.startswith('IMG_'))); eh.append(p.error); nt.append(T.points3D[int(a)].track.length())
nh=np.array(nh); eh=np.array(eh); nt=np.array(nt)
Ym=sfm2m(Y); r=np.linalg.norm(Ym[:,:2],axis=1)
print('Paare',len(X),'Hauptstuetze>=2',(nh>=2).sum(),'>=3',(nh>=3).sum(),'r<80m',(r<80).sum())
np.savez('paare3d_info.npz',nh=nh,eh=eh,nt=nt)
for name,sel in [('alle',r<80),('haupt>=2',(nh>=2)&(r<80)),('haupt>=3',(nh>=3)&(r<80)&(nt>=3))]:
    for thr in [0.15,0.3]:
        res=sim3_meter(X[sel],Ym[sel],schwelle_m=thr,runden=3000,min_anteil=0.05)
        if res is None: print(name,thr,'keine'); continue
        M=res['M']; s=np.cbrt(np.linalg.det(M[:3,:3])); print('%-9s thr %.2f n %d inl %d (%.0f%%) s %.5f rest_med %.3f m'%(name,thr,res['n'],res['n_inlier'],100*res['n_inlier']/res['n'],s,res['rest_median_m']))
        np.save('M_%s_%.2f.npy'%(name.replace('>=','ge'),thr),M)

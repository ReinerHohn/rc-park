import json, numpy as np, trimesh
from scipy.spatial import cKDTree
d=json.load(open('modelle/schwabentor-1120/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1120.json'))['kameras']
names=list(d); C=np.array([d[n]['standort'] for n in names])
P=np.load('modelle/schwabentor-1120/sfm/punkte_modell_schwabentor-1120.npy')[:,:3].astype(float)
m=trimesh.load('modelle/stl/schwabentor-1120_1-87.stl'); S=m.sample(400000)*87/1000.0
print('STL m', S.min(0).round(1), S.max(0).round(1))
k=[-2.32,5.13,1.46,9.09,20.56,23.64]
box=(P[:,0]>k[0])&(P[:,0]<k[3])&(P[:,1]>k[1])&(P[:,1]<k[4])&(P[:,2]>k[2])&(P[:,2]<k[5])
dist,_=cKDTree(S).query(P[box]); F=P[box][dist>0.5]; print('Faecherpunkte', len(F))
rng=np.random.default_rng(0); F=F[rng.choice(len(F),min(60000,len(F)),replace=False)]
res=[]
for i,c in enumerate(C):
    v=F-c; r=np.linalg.norm(v,axis=1)
    if np.median(r)>80: continue
    v/=r[:,None]; az=np.degrees(np.arctan2(v[:,1],v[:,0])); el=np.degrees(np.arcsin(v[:,2]))
    key=(np.floor(az/0.15).astype(np.int64)*100000+np.floor(el/0.15).astype(np.int64))
    o=np.argsort(key); ks=key[o]; rs=r[o]; b=np.r_[0,np.flatnonzero(np.diff(ks))+1,len(ks)]
    cnt=np.diff(b); rmin=np.minimum.reduceat(rs,b[:-1]); rmax=np.maximum.reduceat(rs,b[:-1])
    strahl=((cnt>=4)&(rmax-rmin>1.0)); anteil=cnt[strahl].sum()/len(F)
    res.append((anteil,names[i],c.round(1),np.median(r).round(1)))
res.sort(key=lambda x:-x[0])
for x in res[:10]: print('%.3f'%x[0], x[1], x[2], x[3])
print('Median', np.median([x[0] for x in res]).round(3), 'Kameras', len(res))

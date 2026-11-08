import numpy as np, trimesh, glob, os, sys, json
from scipy.spatial import cKDTree
S=sys.argv[1]; P=np.load("/media/oem/scan/rc-park_null/wolke_netzrahmen.npy")[:,:3]
rng=np.random.default_rng(1); names=[]; pts=[]; lab=[]
for i,f in enumerate(sorted(glob.glob(S+"/teile/teil_*.stl"))):
    m=trimesh.load(f,process=False); m.apply_scale(0.087); nm=os.path.basename(f)[5:-4].replace("stl_teil_","")
    try: X,_=trimesh.sample.sample_surface(m,60000,seed=1)
    except Exception: X=m.vertices
    names.append(nm); pts.append(np.asarray(X)); lab.append(np.full(len(X),i))
A=np.vstack(pts); L=np.concatenate(lab); kd=cKDTree(A)
lo,hi=A.min(0)-1,A.max(0)+1; Pc=P[np.all((P>lo)&(P<hi),axis=1)]; d,j=kd.query(Pc); near=d<1.0; Pc,d,j=Pc[near],d[near],j[near]; lb=L[j]
print(f"Wolkenpunkte im Gebaeudeumfeld (<1 m zu irgendeinem Teil): {len(Pc)}")
rows=[]
for i,nm in enumerate(names):
    k=lb==i; dd=d[k]
    cov=np.mean(cKDTree(Pc).query(pts[i][::10])[0]<0.3) if len(Pc) else 0   # Anteil Teilflaeche, nahe an Wolke (<0.3 m): Wolke "stuetzt" das Teil
    rows.append((nm,int(k.sum()),float(np.median(dd)) if k.any() else np.nan,float(np.percentile(dd,90)) if k.any() else np.nan,float(np.mean(dd>0.3)) if k.any() else np.nan,float(cov),float(dd.sum())))
rows.sort(key=lambda r:-(r[6] if r[6]==r[6] else 0))
print(f"{'Teil':22s} {'Wolkenpkt':>9s} {'Median m':>8s} {'P90 m':>6s} {'>0,3 m':>7s} {'Flaeche gestuetzt':>17s} {'Summe Abst.':>11s}")
for r in rows: print(f"{r[0]:22s} {r[1]:9d} {r[2]:8.3f} {r[3]:6.2f} {r[4]*100:6.0f}% {r[5]*100:16.0f}% {r[6]:11.0f}")
json.dump([dict(teil=r[0],n=r[1],median=r[2],p90=r[3],anteil_ueber_0_3=r[4],gestuetzt=r[5]) for r in rows],open(S+"/teilabstand.json","w"),indent=1)

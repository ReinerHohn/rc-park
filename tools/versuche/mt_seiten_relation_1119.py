import pycolmap, sqlite3, numpy as np, sys, collections
from scipy.spatial import cKDTree
D="/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/"
db=sqlite3.connect(f"file:{D}konsens_arbeit/lauf1/db_kalib.db?mode=ro",uri=True); nm=dict(db.execute("select image_id,name from images")); inv={n:i for i,n in nm.items()}
def p3(rec): return {im.name: np.array([p.point3D_id if p.has_point3D() else -1 for p in im.points2D],dtype=np.int64) for im in rec.images.values() if im.has_pose}
def um(P,Q):
    mp,mq=P.mean(0),Q.mean(0); H=(Q-mq).T@(P-mp)/len(P); U,S,Vt=np.linalg.svd(H); Dg=np.diag([1,1,np.sign(np.linalg.det(U@Vt))]); R=U@Dg@Vt; s=(S*np.diag(Dg)).sum()/((P-mp)**2).sum(1).mean(); return s,R,mq-s*R@mp
def freiraum(Xp, rec, max_bilder=40, seed=0):
    """Xp = fremde Punkte im System von rec. Je Bild: fremder Punkt projiziert neben einen eigenen Punkt -> Tiefe gleich (passt) oder deutlich davor (Konflikt: das Bild haette ihn sehen muessen)."""
    ims=[im for im in rec.images.values() if im.has_pose]; rng=np.random.default_rng(seed); ims=[ims[i] for i in rng.permutation(len(ims))[:max_bilder]]; passt=konf=0
    for im in ims:
        cam=rec.cameras[im.camera_id]; M=im.cam_from_world().matrix(); f=cam.focal_length_x; cx,cy=cam.principal_point_x,cam.principal_point_y
        own=[(p.xy,rec.points3D[p.point3D_id].xyz) for p in im.points2D if p.has_point3D()]
        if len(own)<30: continue
        uv=np.array([o[0] for o in own]); dy=(np.array([o[1] for o in own])@M[:,:3].T+M[:,3])[:,2]
        pc=Xp@M[:,:3].T+M[:,3]; v=pc[:,2]>1e-6; pu=np.c_[f*pc[v,0]/pc[v,2]+cx, f*pc[v,1]/pc[v,2]+cy]; dx=pc[v,2]
        drin=(pu[:,0]>0)&(pu[:,0]<cam.width)&(pu[:,1]>0)&(pu[:,1]<cam.height); pu,dx=pu[drin],dx[drin]
        if not len(pu): continue
        d,ix=cKDTree(uv).query(pu,distance_upper_bound=0.02*cam.width); ok=np.isfinite(d); q=dx[ok]/dy[ix[ok]]
        passt+=int(((q>0.85)&(q<1.18)).sum()); konf+=int((q<0.7).sum())
    return passt,konf
def relation(pa,pb):
    A=pycolmap.Reconstruction(pa); B=pycolmap.Reconstruction(pb); PA,PB=p3(A),p3(B); XA={i:p.xyz for i,p in A.points3D.items()}; XB={i:p.xyz for i,p in B.points3D.items()}
    idA={inv[n] for n in PA}; idB={inv[n] for n in PB}; kor={}; npaar=0
    for pid,rows,data in db.execute("select pair_id,rows,data from two_view_geometries where rows>=15"):
        a,b=divmod(pid,2147483647)
        if a in idB and b in idA and a not in idA and b not in idB: i,j,sw=a,b,False
        elif b in idB and a in idA and b not in idA and a not in idB: i,j,sw=b,a,True
        else: continue
        m=np.frombuffer(data,np.uint32).reshape(-1,2); m=m[:,::-1] if sw else m; npaar+=1
        qb=PB[nm[i]][m[:,0]]; qa=PA[nm[j]][m[:,1]]; ok=(qb>=0)&(qa>=0)
        for x,y in zip(qb[ok],qa[ok]): kor.setdefault(int(x),collections.Counter())[int(y)]+=1
    if len(kor)<30: return dict(paare=npaar,gemeinsam=len(kor),urteil="keine Verbindung")
    P=np.array([XB[k] for k in kor]); Q=np.array([XA[c.most_common(1)[0][0]] for c in kor.values()]); rng=np.random.default_rng(0); best=(0,None)
    thr=0.03*np.percentile(np.linalg.norm(Q-np.median(Q,0),axis=1),50)
    for _ in range(2000):
        ix=rng.choice(len(P),3,replace=False); s,R,t=um(P[ix],Q[ix]); e=np.linalg.norm(s*P@R.T+t-Q,axis=1); k=(e<thr).sum()
        if k>best[0]: best=(k,e<thr)
    inl=best[1]; s,R,t=um(P[inl],Q[inl])
    Bp=np.array(list(XB.values())); Ap=np.array(list(XA.values())); BinA=s*Bp@R.T+t; AinB=((Ap-t)@R)/s
    p1,k1=freiraum(BinA,A); p2,k2=freiraum(AinB,B)
    return dict(paare=npaar,gemeinsam=len(kor),sim3_inlier=round(float(inl.mean()),2),passt=p1+p2,konflikt=k1+k2,konflikt_anteil=round((k1+k2)/max(1,p1+p2+k1+k2),3))
T="/media/oem/rcdaten/tmp/mt_"
for a,b in [x.split(":") for x in sys.argv[1:]]: print(a,"<->",b,relation(T+a+"/sparse/0",T+b+"/sparse/0"),flush=True)

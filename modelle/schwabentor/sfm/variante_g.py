"""Variante G: Original (ohne 498 Fernpunkte) + neu triangulierte Aussenpunkte aus 25 Commons-Aussenfotos (ca_*).
Fluegel bleibt an der ORIGINALLAGE (Beleg: 74 % der Fluegelpunkte haben <0,6 m einen unabhaengig aus >=3 Aussenfotos triangulierten Punkt)."""
import sys,struct,numpy as np
S="/home/oem/git/rc-park/modelle/schwabentor/sfm/"; Zd="/media/oem/scan/rc-park_daten/schwabentor/zusatz_aussen/"
sys.path.insert(0,'/home/oem/git/rc-park/tools'); from sichtrichtung_kohaerenz import fused_xyz
M=np.load(S+"punkte_modell_schwabentor.npy"); Col=np.load(S+"punkte_farben_schwabentor.npy"); V=np.load(S+"punkte_modell_schwabentor_veto.npy")
X=fused_xyz("/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht/fused.ply"); Mf=M.astype(float)
c=np.median(V[:,:2],axis=0); P=Mf-np.array([c[0],c[1],0]); far=np.hypot(P[:,0]-0.1,P[:,1]+0.9)>25
fwd=np.linalg.lstsq(np.c_[X,np.ones(len(X))][::50],P[::50],rcond=None)[0]
def lies(p):
    with open(p,"rb") as f:
        n=struct.unpack("<Q",f.read(8))[0]; d={}
        for _ in range(n):
            pid=struct.unpack("<Q",f.read(8))[0]; xyz=struct.unpack("<3d",f.read(24)); rgb=f.read(3); err=struct.unpack("<d",f.read(8))[0]; tl=struct.unpack("<Q",f.read(8))[0]; tr=np.frombuffer(f.read(8*tl),dtype="<i4").reshape(-1,2)[:,0] if tl else np.zeros(0,int); d[pid]=(xyz,np.frombuffer(rgb,np.uint8),err,tr)
    return d
def namen(p):
    out={}
    with open(p,"rb") as f:
        n=struct.unpack("<Q",f.read(8))[0]
        for _ in range(n):
            iid=struct.unpack("<i",f.read(4))[0]; f.read(32+24+4); nm=b""
            while True:
                ch=f.read(1)
                if ch==b"\x00": break
                nm+=ch
            k=struct.unpack("<Q",f.read(8))[0]; f.read(24*k); out[iid]=nm.decode()
    return out
nm=namen(Zd+"tri/images.bin"); CA=np.array([i for i,v in nm.items() if v.startswith("ca_")])
old=lies(Zd+"reg/points3D.bin"); new=lies(Zd+"tri/points3D.bin")
xs=[];cs=[]
for pid,(xyz,rgb,err,tr) in new.items():
    if pid in old or err>=1.5 or np.isin(tr,CA).sum()<3: continue
    xs.append(xyz); cs.append(rgb)
xs=np.array(xs); cs=np.array(cs); Q=np.c_[xs,np.ones(len(xs))]@fwd
ok=(Q[:,2]>-1.5)&(Q[:,2]<22)&(np.hypot(Q[:,0]-0.1,Q[:,1]+0.9)<25); Q=Q[ok]; cs=cs[ok]
Qm=Q+np.array([c[0],c[1],0])
out=np.vstack([M[~far],Qm.astype(M.dtype)]); col=np.vstack([Col[~far],cs.astype(Col.dtype)])
np.save(S+"punkte_modell_schwabentor_variante_g.npy",out); np.save(S+"punkte_farben_schwabentor_variante_g.npy",col)
print("Basis",int((~far).sum()),"neue Aussenpunkte",len(Qm),"gesamt",len(out))

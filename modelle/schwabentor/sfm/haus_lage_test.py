import sys,os,numpy as np
sys.path.insert(0,'/home/oem/git/rc-park/modelle/schwabentor/sfm')
import rueckprojektion_flaeche as rp
from PIL import Image
rng=np.random.default_rng(0)
cams=rp.read_cameras(os.path.join(rp.SPARSE,'cameras.bin')); imgs=rp.read_images(os.path.join(rp.SPARSE,'images.bin'))
Dp=np.load('/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht_xyz_tmp.npy').astype(float)
Mo=np.load(rp.MODEL_NP).astype(float)
c=np.median(np.load('/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_modell_schwabentor_veto.npy')[:,:2],axis=0)
Pm=Mo-np.array([c[0],c[1],0]); wing=(Pm[:,0]>3.5)&(Pm[:,1]<-1.5)
Col=np.load('/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_farben_schwabentor.npy').astype(float)
if Col.max()<=1.5: Col*=255
i136=[i for i in imgs if '113930' in i['name']][0]; R0=rp.qmat(i136['q']); C=-R0.T@np.array(i136['t'])
import sys
sys.path.insert(0,'/home/oem/git/rc-park/tools')
from sichtrichtung_kohaerenz import vis_flach
from scipy.ndimage import minimum_filter
pidx,cidx=vis_flach('/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht/fused.ply.vis')
wi=np.where(wing)[0]; isw=np.zeros(len(Dp),bool); isw[wi]=True
cn=np.bincount(cidx[isw[pidx]],minlength=len(imgs)); gruppe=set(np.where(cn>=0.02*len(wi))[0].tolist())
print('Erzeuger-Kameras des Fluegels (vis-Index):',sorted(gruppe),flush=True)
ids=sorted(i['id'] for i in imgs); byid={i['id']:i for i in imgs}
W=400; G=[]; GS=[]
for k in range(len(ids)):
    if k in gruppe: continue
    im=byid[ids[k]]; cam=cams[im['cam']]; I=Image.open(os.path.join(rp.IMGS,im['name'])).convert('RGB').resize((W,int(W*cam[2]/cam[1])))
    A=np.asarray(I,float); G.append((cam,A,rp.qmat(im['q']),np.array(im['t']))); GS.append(minimum_filter(A.min(2),size=3)>=250)
print('Kontroll-Kameras',len(G),flush=True)
def score(X,Cl):
    D=[]; sk=np.zeros(len(X)); ob=np.zeros(len(X))
    for (cam,A,Rm,tv),S in zip(G,GS):
        u,v,z,w,h=rp.project(X,cam,Rm,tv); m=(z>0)&(u>=0)&(u<w-1)&(v>=0)&(v<h-1)
        if m.sum()<100: continue
        ui=(u[m]*W/w).astype(int); vi=(v[m]*A.shape[0]/h).astype(int)
        dd=np.full(len(X),np.nan); dd[m]=np.abs(A[vi,ui]-Cl[m]).mean(1); D.append(dd)
        ob[m]+=1; sk[np.where(m)[0][S[vi,ui]]]+=1
    with np.errstate(all='ignore'): q=np.nanpercentile(np.array(D),25,axis=0)
    ok=ob>=3
    return round(float(np.nanmedian(q)),1), round(float(np.mean(sk[ok]/ob[ok]>=0.2)),3), int(ok.sum())
iw=rng.choice(wi,2500,replace=False); X=Dp[iw]; Cl=Col[iw]
# Modellrahmen -> SfM ueber Umeyama
i=rng.choice(len(Dp),100000,replace=False); Xa=Pm[i]; Ya=Dp[i]; mx,my=Xa.mean(0),Ya.mean(0)
U,S_,Vt=np.linalg.svd((Ya-my).T@(Xa-mx)/len(Xa)); d=np.sign(np.linalg.det(U@Vt)); Rr=U@np.diag([1,1,d])@Vt
sc=(S_*np.array([1,1,d])).sum()/(Xa-mx).var(0).sum(); tt=my-sc*Rr@mx
Pw=Pm[iw]
T=Pm[(Pm[:,0]>-2.5)&(Pm[:,0]<3)&(Pm[:,1]>-3.5)&(Pm[:,1]<1.5)&(Pm[:,2]>2)&(Pm[:,2]<20)]
cx,cy=np.median(T[:,0]),np.median(T[:,1]); print('Turmachse (Modellrahmen)',round(cx,2),round(cy,2),flush=True)
def sfm(P): return sc*(Rr@P.T).T+tt
print('Ist-Lage',score(X,Cl),flush=True)
res=[]
for sp in (0,1):
  for ang in range(0,360,30):
    a=np.deg2rad(ang); Q=Pw-np.array([cx,cy,0]); 
    if sp: Q[:,0]=-Q[:,0]
    Q=np.stack([np.cos(a)*Q[:,0]-np.sin(a)*Q[:,1],np.sin(a)*Q[:,0]+np.cos(a)*Q[:,1],Q[:,2]],1)+np.array([cx,cy,0])
    r=score(sfm(Q),Cl); res.append((r[0],r[1],sp,ang)); print('Spiegel' if sp else 'Drehung',ang,r,flush=True)
res.sort(); print('BESTE:',res[:4])

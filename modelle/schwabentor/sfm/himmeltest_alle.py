import sys,os,numpy as np
sys.path.insert(0,'/home/oem/git/rc-park/modelle/schwabentor/sfm')
import rueckprojektion_flaeche as rp
from scipy.ndimage import minimum_filter
from PIL import Image
cams=rp.read_cameras(os.path.join(rp.SPARSE,'cameras.bin')); imgs=rp.read_images(os.path.join(rp.SPARSE,'images.bin'))
Dp=np.load('/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht_xyz_tmp.npy').astype(np.float32)
sky=np.zeros(len(Dp),np.int32); obs=np.zeros(len(Dp),np.int32)
for n,im in enumerate(imgs):
    cam=cams[im['cam']]
    G=np.asarray(Image.open(os.path.join(rp.IMGS,im['name'])).convert('RGB')).min(2)
    S=minimum_filter(G,size=7)>=250
    R=rp.qmat(im['q']); t=np.array(im['t'])
    for a in range(0,len(Dp),1000000):
        u,v,z,w,h=rp.project(Dp[a:a+1000000].astype(float),cam,R,t)
        ui=np.round(u*G.shape[1]/w); vi=np.round(v*G.shape[0]/h)
        m=(z>0)&(ui>=0)&(ui<G.shape[1])&(vi>=0)&(vi<G.shape[0])
        idx=np.where(m)[0]; ui=ui[m].astype(int); vi=vi[m].astype(int)
        obs[a+idx]+=1; sky[a+idx[S[vi,ui]]]+=1
    if n%30==0: print(n,flush=True)
np.savez('himmel_alle.npz',sky=sky,obs=obs); print('fertig')

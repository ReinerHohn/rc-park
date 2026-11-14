import sys,os,numpy as np
sys.path.insert(0,'/home/oem/git/rc-park/modelle/schwabentor/sfm')
import rueckprojektion_flaeche as rp
from PIL import Image, ImageDraw
cams=rp.read_cameras(os.path.join(rp.SPARSE,'cameras.bin')); imgs=rp.read_images(os.path.join(rp.SPARSE,'images.bin'))
names=[i['name'] for i in imgs]; print('113930' , [n for n in names if '113930' in n], [n for n in names if '1139' in n])
sel=[i for i in imgs if '113930' in i['name']]
if not sel: sys.exit()
im=sel[0]; ids=sorted(i['id'] for i in imgs); print('vis-Index',ids.index(im['id']))
Dp=np.load('/media/oem/scan/rc-park_daten/schwabentor/pipe/dicht_xyz_tmp.npy').astype(float)
Mo=np.load(rp.MODEL_NP).astype(float)
c=np.median(np.load('/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_modell_schwabentor_veto.npy')[:,:2],axis=0)
Pm=Mo-np.array([c[0],c[1],0]); wing=(Pm[:,0]>3.5)&(Pm[:,1]<-1.5)
rng=np.random.default_rng(0)
G=Image.open(os.path.join(rp.IMGS,im['name'])).convert('RGB'); dr=ImageDraw.Draw(G)
cam=cams[im['cam']]; R=rp.qmat(im['q']); t=np.array(im['t'])
for msk,col in ((~wing,(0,200,255)),(wing,(255,40,40))):
    idx=np.where(msk)[0]; idx=rng.choice(idx,6000,replace=False)
    u,v,z,w,h=rp.project(Dp[idx],cam,R,t); k=(z>0)&(u>=0)&(u<w)&(v>=0)&(v<h)
    sx=G.size[0]/w; sy=G.size[1]/h
    print('Farbe',col,'im Bild',int(k.sum()))
    for x_,y_ in zip(u[k]*sx,v[k]*sy): dr.ellipse([x_-2,y_-2,x_+2,y_+2],fill=col)
G.thumbnail((900,1200)); G.save('overlay_haus_113930.jpg',quality=85)

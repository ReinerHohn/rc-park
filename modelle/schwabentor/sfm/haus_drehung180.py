import numpy as np
from scipy.spatial import cKDTree
from PIL import Image
F=np.load('fluegel_punkte.npy').astype(float); Fc=np.load('fluegel_farben.npy')
M=np.load('/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_modell_schwabentor_sauber.npy').astype(float)
Col=np.load('/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_farben_schwabentor_sauber.npy')
c=np.median(np.load('/home/oem/git/rc-park/modelle/schwabentor/sfm/punkte_modell_schwabentor_veto.npy')[:,:2],axis=0)
P=M-np.array([c[0],c[1],0])
cx,cy=0.0,-0.86
def rot(F,a=180,cx=cx,cy=cy):
    t=np.deg2rad(a); Q=F-np.array([cx,cy,0]); return np.stack([np.cos(t)*Q[:,0]-np.sin(t)*Q[:,1],np.sin(t)*Q[:,0]+np.cos(t)*Q[:,1],Q[:,2]],1)+np.array([cx,cy,0])
R=rot(F); print('rot Fluegel x',R[:,0].min().round(1),R[:,0].max().round(1),'y',R[:,1].min().round(1),R[:,1].max().round(1))
tree=cKDTree(P[::3]); d,_=tree.query(R[::20]); print('Anteil gedrehter Fluegelpunkte <0.3 m an vorhandener Wolke: %.3f, <1 m: %.3f'%(np.mean(d<.3),np.mean(d<1)))
d0,_=tree.query(F[::20]); print('vorher (Ist-Lage): <0.3 m %.3f <1 m %.3f'%(np.mean(d0<.3),np.mean(d0<1)))
np.save('fluegel_gedreht180.npy',R)
# Render Draufsicht + Front
Cf=Col.astype(float); Cf=Cf*255 if Cf.max()<=1.5 else Cf
rng=np.random.default_rng(0); k=rng.choice(len(P),500000,replace=False); PP=P[k]; CC=Cf[k].astype(np.uint8)
FF=Fc.astype(float); FF=FF*255 if FF.max()<=1.5 else FF
ALL=np.vstack([PP,R[::2]]); COL=np.vstack([CC,np.tile(np.array([255,0,255],np.uint8),(len(R[::2]),1))])
def render(yaw,pit=0.18,S=34,W=620):
    cy_,sy_=np.cos(yaw),np.sin(yaw); x=cy_*ALL[:,0]+sy_*ALL[:,1]; dd=-sy_*ALL[:,0]+cy_*ALL[:,1]
    u=W/2+x*S; v=W*0.85-(ALL[:,2]*np.cos(pit)+dd*np.sin(pit))*S
    o=np.argsort(-dd); I=np.full((W,W,3),245,np.uint8); ui=u[o].astype(int); vi=v[o].astype(int); m=(ui>=0)&(ui<W-1)&(vi>=0)&(vi<W-1)
    for a in (0,1):
        for b in (0,1): I[vi[m]+b,ui[m]+a]=COL[o][m]
    return I
Wd=Image.new('RGB',(1860,620),'white')
for i,a in enumerate((-26,120,-110)): Wd.paste(Image.fromarray(render(np.deg2rad(a))),(i*620,0))
Wd.save('ansicht_variante_c.jpg',quality=85)

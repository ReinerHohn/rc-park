import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pickle, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
w=np.load(sys.argv[1]); P=w['P']; out=sys.argv[2]; G=pickle.load(open('geo.pkl','rb'))
nd=G['dom']-G['dgm']; g=G['g']
fig,ax=plt.subplots(1,3,figsize=(27,9))
a=ax[0]; a.imshow(np.clip(nd,0,25),extent=[g[0]-.5,g[-1]+.5,g[0]-.5,g[-1]+.5],origin='lower',cmap='Greys',alpha=.6)
i=np.random.default_rng(1).choice(len(P),min(len(P),400000),replace=False)
a.scatter(P[i,0],P[i,1],s=.2,c=P[i,2],cmap='jet',vmin=-2,vmax=20)
for gid,nm,typ,Q in G['polys']:
    if typ=='GroundSurface': a.plot(np.r_[Q[:,0],Q[0,0]],np.r_[Q[:,1],Q[0,1]],'m-',lw=.8)
if 'cams' in w: c=w['cams']; a.plot(c[:,0],c[:,1],'k.',ms=2)
a.set_xlim(-60,60); a.set_ylim(-100,50); a.set_aspect('equal'); a.grid(); a.set_title('Draufsicht x/y m, Farbe z; grau nDOM (DOM1-DGM1 0..25 m), magenta LoD2')
for k,(u,v,nm) in enumerate([(1,2,'Seite y/z'),(0,2,'Seite x/z')]):
    a=ax[k+1]; a.scatter(P[i,u],P[i,v],s=.2,c=P[i,1-u if u==0 else 0],cmap='viridis')
    a.set_aspect('equal'); a.grid(); a.set_title(nm+' (m)')
    # nDOM Profil Maximum entlang
    if u==1: prof=np.nanmax(np.where((g[None,:]>-15)&(g[None,:]<5),G['dom'],np.nan),axis=1); a.plot(g,prof,'r-',lw=1,label='DOM1 max x-15..5')
    a.set_xlim(-100,50) if u==1 else a.set_xlim(-60,60); a.set_ylim(-15,50)
plt.tight_layout(); plt.savefig(out,dpi=60)

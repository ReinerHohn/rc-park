import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pickle, json, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
w=np.load(sys.argv[1]); P=w['P']; Cc=w['C'] if 'C' in w else None; st=json.load(open(sys.argv[2])); out=sys.argv[3]; titel=sys.argv[4]
G=pickle.load(open('geo.pkl','rb')); g=G['g']; dom,dgm=G['dom'],G['dgm']; nd=dom-dgm
O=json.load(open('/home/oem/git/rc-park/modelle/schwabentor-1122/objekt.json')); gid=O['lod2']['id']
m=np.array(st['mitte_xy']); u=np.array(st['richtung_xy']); n=np.array([-u[1],u[0]]); L=st['laenge_m']
def at(A,x,y):
    j=np.clip(np.round(x-g[0]).astype(int),0,len(g)-1); i=np.clip(np.round(y-g[0]).astype(int),0,len(g)-1); return A[i,j]
fig=plt.figure(figsize=(24,15)); 
a=fig.add_subplot(2,2,1)
a.imshow(np.clip(nd,0,20),extent=[g[0]-.5,g[-1]+.5,g[0]-.5,g[-1]+.5],origin='lower',cmap='Greys',alpha=.7)
k=(P[:,2]>0.5)&(P[:,2]<25); i=np.random.default_rng(0).choice(np.where(k)[0],min(k.sum(),300000),replace=False)
sc=a.scatter(P[i,0],P[i,1],s=.3,c=P[i,2],cmap='jet',vmin=0,vmax=20); plt.colorbar(sc,ax=a,label='z Modellmeter')
for gi,nm,typ,Q in G['polys']:
    if typ=='GroundSurface': a.plot(np.r_[Q[:,0],Q[0,0]],np.r_[Q[:,1],Q[0,1]],'-',color='magenta' if gi==gid else 'purple',lw=1.6 if gi==gid else .6)
B=np.array([m-L/2*u-2*n,m+L/2*u-2*n,m+L/2*u+2*n,m-L/2*u+2*n,m-L/2*u-2*n]); a.plot(B[:,0],B[:,1],'k-',lw=2,label='Steg-Box (Messung)')
a.set_xlim(-35,35); a.set_ylim(-55,35); a.set_aspect('equal'); a.grid(alpha=.3); a.legend(loc='upper right'); a.set_xlabel('x m'); a.set_ylabel('y m')
a.set_title('Draufsicht (Modellmeter): Wolke nach Farbe z, grau = nDOM (DOM1-DGM1, 0..20 m), magenta = LoD2 Schwabentor, lila = LoD2 Nachbarn')
# Laengsschnitt
a=fig.add_subplot(2,2,3); d=P[:,:2]-m; S=d@u; Q=d@n; k=np.abs(Q)<2.5
a.scatter(S[k],P[k,2],s=.3,c='steelblue',alpha=.4,label='Wolke |quer|<2,5 m')
ss=np.arange(-30,30.1,0.25); xy=m+np.outer(ss,u)
from scipy.ndimage import map_coordinates
def D(x,y,art):
    A=dom if art=='dom1' else dgm; return map_coordinates(A,[np.asarray(y)-g[0],np.asarray(x)-g[0]],order=1)
a.plot(ss,D(xy[:,0],xy[:,1],'dom1'),'r-',lw=2,label='DOM1 (Laser, Oberflaeche) auf Achse'); a.plot(ss,D(xy[:,0],xy[:,1],'dgm1'),'g-',lw=2,label='DGM1 (Gelaende) auf Achse')
a.axvline(-L/2,color='k',ls='--'); a.axvline(L/2,color='k',ls='--'); a.set_xlim(-30,30); a.set_ylim(-3,22); a.set_aspect('equal'); a.grid(alpha=.3); a.legend(loc='upper left')
a.set_xlabel('laengs Stegachse m (Richtung %s)'%np.round(u,2)); a.set_ylabel('z m'); a.set_title('Laengsschnitt Steg: Dach %.2f m, Neigung %.1f Grad, Laenge %.1f m'%(st['dach_z_p50'],st['neigung_dach_grad'],L))
# Querschnitt
a=fig.add_subplot(2,2,4); k=np.abs(S)<L/2-1
a.scatter(Q[k],P[k,2],s=.3,c='steelblue',alpha=.3)
qs=np.arange(-12,12.1,0.25)
for sv,col in [(-L/4,'r'),(0,'m'),(L/4,'orange')]:
    xy=m+sv*u+np.outer(qs,n); a.plot(qs,D(xy[:,0],xy[:,1],'dom1'),'-',color=col,lw=1.5,label='DOM1 quer bei s=%.0f'%sv)
xy=m+np.outer(qs,n); a.plot(qs,D(xy[:,0],xy[:,1],'dgm1'),'g-',lw=2,label='DGM1')
a.set_xlim(-12,12); a.set_ylim(-3,16); a.set_aspect('equal'); a.grid(alpha=.3); a.legend(); a.set_xlabel('quer m'); a.set_title('Querschnitt (alle Stegpunkte projiziert)')
# Seitenansicht Gesamt y/z mit Turm
a=fig.add_subplot(2,2,2); k=np.abs(P[:,0]-0)<15
i=np.random.default_rng(1).choice(np.where(k)[0],min(k.sum(),300000),replace=False); a.scatter(P[i,1],P[i,2],s=.3,c=P[i,0],cmap='viridis')
for gi,nm,typ,Qp in G['polys']:
    if gi==gid: a.plot(np.r_[Qp[:,1],Qp[0,1]],np.r_[Qp[:,2],Qp[0,2]],'m-',lw=.8)
prof=np.nanmax(np.where((g[None,:]>-15)&(g[None,:]<15),dom,np.nan),axis=1); a.plot(g,prof,'r-',lw=1.5,label='DOM1 max (x -15..15)')
prof=np.nanmin(np.where((g[None,:]>-15)&(g[None,:]<15),dgm,np.nan),axis=1); a.plot(g,prof,'g-',lw=1.5,label='DGM1 min')
a.set_xlim(-55,35); a.set_ylim(-3,50); a.set_aspect('equal'); a.grid(alpha=.3); a.legend(); a.set_xlabel('y m'); a.set_ylabel('z m'); a.set_title('Seitenansicht y/z (|x|<15), magenta = LoD2 Schwabentor')
fig.suptitle(titel,fontsize=16); plt.tight_layout(); plt.savefig(out,dpi=55)

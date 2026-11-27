import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
from sim3_robust import anwenden
from seiten_gps_vereinen import lot_info
HH,T=lade(); tr=rots(T); tc=zentren(T)
v=np.load('alt_sim3.npy'); s,R,t=v[0],v[1:10].reshape(3,3),v[10:]
def alt(X): return sfm2m(s*np.asarray(X)@R.T+t)
Mn=np.load('M_hauptge3_0.15.npy')
z=np.load('paare3d.npz'); X=z['X']; Ym=sfm2m(z['Y']); inf=np.load('paare3d_info.npz'); sel=inf['nh']>=3
for nm,f in [('alt',alt),('neu',lambda P:anwenden(Mn,P))]:
    e=np.linalg.norm(f(X[sel])-Ym[sel],axis=1); print(nm,'3D-Paare Rest median %.3f p75 %.3f <0.15m %.0f%%'%(np.median(e),np.percentile(e,75),100*(e<.15).mean()))
    # Lot
    Rs=np.array([tr[n] for n in tc]); L=lot_info(Rs); 
    Rl=(f(np.array([L['oben']]))-f(np.zeros((1,3))))[0]; Rl/=np.linalg.norm(Rl); print('   Neigung Teil-Lot(Bild-x) gegen Modell-z %.2f Grad, Richtung xy %s'%(np.degrees(np.arccos(Rl[2])),Rl[:2].round(3)))
    # Brueckenkameras
    nm_=sorted(tc); C=f(np.array([tc[n] for n in nm_])); np.save('cams_%s_m.npy'%nm,C)
    b=np.array(['160715'<=n[13:19]<='161151' for n in nm_]); print('   Brueckenkameras mittel',C[b].mean(0).round(2),'z %.2f..%.2f'%(C[b,2].min(),C[b,2].max()))
# Unterschied alt/neu an Brueckenpunkten
nm_=sorted(tc); b=np.array(['160715'<=n[13:19]<='161151' for n in nm_]); P=np.array([tc[n] for n in nm_])[b]
d=alt(P)-anwenden(Mn,P); print('Versatz alt-neu an Brueckenkameras (m) mittel',d.mean(0).round(2),'max',np.abs(d).max().round(2))

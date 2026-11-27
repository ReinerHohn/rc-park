import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
from sim3_robust import anwenden, sim3_meter
HH,T=lade()
v=np.load('alt_sim3.npy'); s,R,t=v[0],v[1:10].reshape(3,3),v[10:]
def alt(X): return sfm2m(s*np.asarray(X)@R.T+t)
Mn=np.load('M_hauptge3_0.15.npy')
Ma=np.eye(4); 
# Rotationsunterschied
P=np.random.default_rng(0).normal(size=(50,3)); A=alt(P)-alt(np.zeros((1,3))); B=anwenden(Mn,P)-anwenden(Mn,np.zeros((1,3)))
from sim3_robust import umeyama; s2,R2,_=umeyama(B,A); print('alt gegen neu: Drehung %.2f Grad, Massstab %.4f'%(np.degrees(np.arccos((np.trace(R2)-1)/2)),s2))
z=np.load('paare3d.npz'); X=z['X']; Ym=sfm2m(z['Y']); inf=np.load('paare3d_info.npz'); nh=inf['nh']
m=np.array([0.9,-24.6]); u=np.array([-0.411,-0.912]); q_=np.array([-u[1],u[0]])
d=Ym[:,:2]-m; S=d@u; Q=d@q_
for nm,sel in [('Brueckenzone s-12..18 |q|<6',(S>-12)&(S<18)&(np.abs(Q)<6)),('Turmnah r<15 um Turm',np.linalg.norm(Ym[:,:2]-np.array([-2,16]),axis=1)<15),('Zone s<-12 (Anbau)',(S<-12)&(S>-30)&(np.abs(Q)<10))]:
    for hn in [0,2]:
        k=sel&(nh>=hn)
        if k.sum()<5: print(nm,hn,'n',k.sum()); continue
        ea=np.linalg.norm(alt(X[k])-Ym[k],axis=1); en=np.linalg.norm(anwenden(Mn,X[k])-Ym[k],axis=1)
        dz_a=np.median((alt(X[k])-Ym[k])[:,2]); dz_n=np.median((anwenden(Mn,X[k])-Ym[k])[:,2])
        print('%-30s nh>=%d n %6d  alt med %.2f dz %.2f | neu med %.2f dz %.2f'%(nm,hn,k.sum(),np.median(ea),dz_a,np.median(en),dz_n))

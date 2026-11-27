import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
from sim3_robust import sim3_meter, anwenden
z=np.load('paare3d.npz'); X=z['X']; Ym=sfm2m(z['Y']); nh=np.load('paare3d_info.npz')['nh']
Mn=np.load('M_hauptge3_0.15.npy'); Ma=np.load('M_alt.npy')
m=np.array([0.9,-24.6]); u=np.array([-0.411,-0.912]); n=np.array([-u[1],u[0]])
br=np.array([m+(-9)*u, m+15*u])   # Brueckenenden
probe=np.array([[*(m+s*u),8.0] for s in (-9,3,15)])
# Teilkoordinaten der Probe (ueber neue Transf. rueckwaerts)
Mi=np.linalg.inv(Mn); pt=anwenden(Mi,probe)
d=np.min(np.linalg.norm(Ym[:,None,:2]-br[None],axis=2),1)
for lab,sel in [('nah <20 m',(d<20)&(nh>=2)),('nah <30 m',(d<30)&(nh>=2)),('Turm >30 m',(d>=30)&(nh>=3))]:
    r=sim3_meter(X[sel],Ym[sel],schwelle_m=0.3,runden=3000,min_anteil=0.05)
    if r is None: print(lab,'keine',sel.sum()); continue
    M=r['M']; s=np.cbrt(np.linalg.det(M[:3,:3])); q=anwenden(M,pt)-probe
    print('%-12s n %6d inl %6d s %.4f rest %.3f | Brueckenprobe s-9/3/15 Versatz zu neu dz %s  dxy %s'%(lab,r['n'],r['n_inlier'],s,r['rest_median_m'],q[:,2].round(2),np.linalg.norm(q[:,:2],axis=1).round(2)))
    np.save('M_%s.npy'%lab.split()[0]+lab.split()[1],M)
print('alt gegen neu Probe dz',(anwenden(Ma,pt)-probe)[:,2].round(2))

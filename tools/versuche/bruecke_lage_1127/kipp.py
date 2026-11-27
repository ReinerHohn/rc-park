import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, json; from bewerte import dom
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation as Ro
from sim3_robust import anwenden
def rotM(ax,ay,piv):
    R=Ro.from_rotvec([ax,ay,0]).as_matrix(); M=np.eye(4); M[:3,:3]=R; M[:3,3]=piv-R@piv; return M
def kipp_fit(C, piv, h0_start=1.5):
    g0=dom(C[:,0],C[:,1],'dgm1'); o=dom(C[:,0],C[:,1],'dom1'); frei=(o-g0<0.5)&(np.abs(C[:,2]-g0-np.median(C[:,2]-g0))<1.5)
    Cf=C[frei]
    def res(p):
        Cn=anwenden(rotM(p[0],p[1],piv),Cf); return Cn[:,2]-dom(Cn[:,0],Cn[:,1],'dgm1')-p[2]
    r=least_squares(res,[0,0,h0_start],loss='soft_l1',f_scale=0.2)
    # Unsicherheit per Bootstrap
    rng=np.random.default_rng(0); B=[]
    for _ in range(100):
        i=rng.choice(len(Cf),len(Cf)); 
        def rb(p): Cn=anwenden(rotM(p[0],p[1],piv),Cf[i]); return Cn[:,2]-dom(Cn[:,0],Cn[:,1],'dgm1')-p[2]
        B.append(least_squares(rb,r.x,loss='soft_l1',f_scale=0.2).x)
    B=np.array(B); return r.x, B.std(0), frei.sum(), np.median(np.abs(r.fun))
if __name__=='__main__':
    C=np.load(sys.argv[1]); piv=np.array([-2.0,16.0,10.0])
    x,sd,n,mad=kipp_fit(C,piv)
    print('Kippung um Turm: ax %.2f +- %.2f Grad, ay %.2f +- %.2f Grad, h0 %.2f +- %.2f m, n %d, Rest-Median %.2f m'%(np.degrees(x[0]),np.degrees(sd[0]),np.degrees(x[1]),np.degrees(sd[1]),x[2],sd[2],n,mad))
    np.save(sys.argv[2],rotM(x[0],x[1],piv))

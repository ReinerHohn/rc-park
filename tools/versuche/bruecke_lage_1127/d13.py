import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np; from bewerte import dom
P=np.load(sys.argv[1])['P'].astype(float)
m=np.array([0.9,-24.6]); u=np.array([-0.411,-0.912]); n=np.array([-u[1],u[0]])
d=P[:,:2]-m; S=d@u; Q=d@n
for side,(q0,q1) in [('links',(-9,-4)),('rechts',(4,9))]:
    print(side)
    for a in range(-16,26,2):
        k=(S>=a)&(S<a+2)&(Q>=q0)&(Q<q1)
        if k.sum()<100: print('  s %3d n %d'%(a,k.sum())); continue
        zc=np.percentile(P[k,2],3); p=m+(a+1)*u+(q0+q1)/2*n; g=dom(p[0],p[1],'dgm1')[0]; o=dom(p[0],p[1],'dom1')[0]
        print('  s %3d n %6d Wolke-Boden p3 %5.2f  DGM %5.2f  DOM %5.2f  diff %5.2f'%(a,k.sum(),zc,g,o,zc-g))

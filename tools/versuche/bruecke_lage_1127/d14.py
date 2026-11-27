import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np; from bewerte import dom
from geo import m2utm, utm2m, Z0
from dom1_kachel import _kachel
m=np.array([0.9,-24.6]); u=np.array([-0.411,-0.912]); n=np.array([-u[1],u[0]])
# rohe DOM1-Zellen im Streifen s -8..12, |q|<4: Zellmitten in Modellrahmen
A,xc,yc,_=_kachel(414,5316,'dom1'); 
E0,N0=m2utm(np.array([m[0]]),np.array([m[1]])); j0=int(round(E0[0]-xc)); i0=int(round(yc-N0[0]))
cells=[]
for i in range(i0-30,i0+31):
    for j in range(j0-30,j0+31):
        E=xc+j; N=yc-i; x,y=utm2m(E,N); d=np.array([x,y])-m; s=d@u; q=d@n
        if -8<s<12 and abs(q)<4: cells.append((s,q,A[i,j]-Z0))
c=np.array(cells); top=c[c[:,2]>7]
print('DOM1-Rohzellen Dach (>7 m) n %d: z median %.2f p90 %.2f max %.2f; q-Mitte gewichtet %.2f, q-Breite p5..p95 %.2f..%.2f'%(len(top),np.median(top[:,2]),np.percentile(top[:,2],90),top[:,2].max(),np.median(top[:,1]),*np.percentile(top[:,1],[5,95])))
for f in sys.argv[1:]:
    P=np.load(f)['P'].astype(float); d=P[:,:2]-m; S=d@u; Q=d@n
    k=(S>-8)&(S<12)&(np.abs(Q)<4)&(P[:,2]>7)&(P[:,2]<14)
    # Dachflaeche je 1-m-Zelle: Maximum (p95) der Punkte in der Zelle (wie DOM: erste Rueckkehr)
    ci=np.floor(S[k]).astype(int)*100+np.floor(Q[k]).astype(int); zz=P[k,2]
    o=np.argsort(ci); u_,st=np.unique(ci[o],return_index=True); en=np.r_[st[1:],len(o)]
    zc=np.array([np.percentile(zz[o[a:b]],95) for a,b in zip(st,en) if b-a>20])
    print(f,'Wolke Dach je 1-m-Zelle (p95 in Zelle): median %.2f p90 %.2f max %.2f n %d ; q-Mitte %.2f'%(np.median(zc),np.percentile(zc,90),zc.max(),len(zc),np.median(Q[k])))

import sys; sys.path.insert(0,".")
import numpy as np, cv2, json
from bogen_dp import *
bogen={
 "a":[(423,1837),(447,1863),(477,1890),(497,1920),(513,1953),(523,1980),(530,2007)],
 "b":[(423,1823),(457,1847),(490,1877),(520,1907),(540,1930),(557,1960),(570,1987),(577,2010)],
 "c":[(673,1830),(640,1850),(613,1867),(593,1887),(577,1910),(563,1933),(553,1960),(543,1987),(540,2010)],
 "d":[(517,1810),(507,1847),(502,1880),(505,1920),(513,1947),(520,1967)],
 "e":[(527,1817),(547,1837),(567,1857),(583,1877),(597,1897),(607,1920),(613,1940)],
 "f":[(527,1820),(537,1847),(547,1880),(553,1907),(557,1927)],
}
out={}; ov=None
for nm,p in bogen.items():
    q,P,sc,iA,iB,KA,KB=lauf(nm,p)
    if ov is None: ov=iB.copy()
    for X in P:
        b=proj(KB,X); 
        if b: cv2.circle(ov,(int(b[0]),int(b[1])),3,(255,0,255),-1)
    out[nm]=dict(uvz=[uvz(X).round(3).tolist() for X in P],gold_median=float(np.median(sc)),gold_min=float(sc.min()),n=len(P))
    print(nm,"n",len(P),"gold med",round(float(np.median(sc)),2),"min",round(float(sc.min()),2),"u",round(uvz(P[0])[0],2),round(uvz(P[-1])[0],2),"z",round(uvz(P[0])[2],2),round(uvz(P[-1])[2],2),"n",round(uvz(P[0])[1],2),round(uvz(P[-1])[1],2))
json.dump(out,open("bogen_dp.json","w"))
cv2.imwrite("bogen_dp_B.jpg",ov[2380:2600,690:1060].repeat(3,0).repeat(3,1))

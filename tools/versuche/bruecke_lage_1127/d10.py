import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,'/media/oem/scan/rc-park_tmp/lage_bruecke/tools')
import numpy as np, json
from gps import lese; from geo import utm2m, Z0
from bilder_holen import wgs84_zu_utm
nm=json.load(open('cam_namen.json')); G=lese(nm)
pass
ok=[i for i,n in enumerate(nm) if n in G and G[n]['meth']=='GPS']
print('mit GPS',len(G),'davon Methode GPS',len(ok))
U=np.array([wgs84_zu_utm(G[nm[i]]['lat'],G[nm[i]]['lon']) for i in ok]); x,y=utm2m(U[:,0],U[:,1]); Gm=np.c_[x,y]
for f in sys.argv[1:]:
    C=np.load(f)[ok]; d=Gm-C[:,:2]; e=np.linalg.norm(d,axis=1)
    print(f,'GPS-Kamera: Versatz median dx %.1f dy %.1f m, |d| median %.1f p75 %.1f'%(np.median(d[:,0]),np.median(d[:,1]),np.median(e),np.percentile(e,75)))
    # Brueckenkameras getrennt
    b=np.array(['160715'<=nm[i][13:19]<='161151' for i in ok]); print('   Bruecke n %d Versatz median dx %.1f dy %.1f |d| %.1f'%(b.sum(),np.median(d[b,0]),np.median(d[b,1]),np.median(e[b])))
    # 2D-Aehnlichkeit robust: Drehung
    import gps_unsicherheit as GU
    r=GU.robust_fit2d(C[:,:2],Gm,schwelle=10.0)
    print('   robust_fit2d', {k:(np.round(v,3).tolist() if hasattr(v,'shape') else v) for k,v in (r.items() if isinstance(r,dict) else enumerate(r)) if not (hasattr(v,'shape') and v.size>6)})

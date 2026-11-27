import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
HH,T=lade(); hc=zentren(HH); hr=rots(HH); nm=json.load(open('cam_namen.json'))
for f in ['cams_alt_m.npy','cams_neu_m.npy']:
    C=np.load(f); 
    for lab,(a,b) in [('Bruecke 160715-161151',('160715','161151')),('Treppe/Anbau 155910-160713',('155910','160713')),('Turm 163243-164229',('163243','164229'))]:
        idx=[i for i,n in enumerate(nm) if a<=n[13:19]<=b and n in hc]
        if not idx: continue
        H=sfm2m(np.array([hc[nm[i]] for i in idx])); d=C[idx]-H; e=np.linalg.norm(d,axis=1)
        print('%s %-28s n %3d |d| median %.2f p75 %.2f  dz median %.2f  d median %s'%(f[:8],lab,len(idx),np.median(e),np.percentile(e,75),np.median(d[:,2]),np.median(d,0).round(2)))

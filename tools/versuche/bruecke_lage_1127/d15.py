import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
H=pycolmap.Reconstruction('/media/oem/scan/rc-park_daten/schwabentor-1122/pipe/sfm/sparse/0')
P=np.array([p.xyz for p in H.points3D.values()]); L=np.array([p.track.length() for p in H.points3D.values()]); E=np.array([p.error for p in H.points3D.values()])
Pm=sfm2m(P); m=np.array([0.9,-24.6]); u=np.array([-0.411,-0.912]); n=np.array([-u[1],u[0]])
d=Pm[:,:2]-m; S=d@u; Q=d@n
k=(S>-8)&(S<12)&(np.abs(Q)<4)
print('Hauptnetz-Punkte im Bruecken-Streifen',k.sum(),'Spurlaenge median',np.median(L[k]) if k.any() else 0)
for zr in [(7,14),(3,7),(-2,3)]:
    kk=k&(Pm[:,2]>zr[0])&(Pm[:,2]<zr[1]); print('  z',zr,'n',kk.sum(), 'z p50/p90 %.2f %.2f'%tuple(np.percentile(Pm[kk,2],[50,90])) if kk.sum()>3 else '')
# welche Kameras sehen sie
ims={}
for pid,p in H.points3D.items():
    pass

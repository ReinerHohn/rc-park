import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
from seiten_gps_vereinen import lot_info
HH,T=lade(); hc=zentren(HH); tc=zentren(T); hr=rots(HH); tr=rots(T)
gem=sorted(set(hc)&set(tc)); A_=np.array([tc[n] for n in gem]); B=np.array([hc[n] for n in gem])
alt=json.load(open(D+'/teilmodell/ausrichtung.json'))['0']
# alte Transformation aus 0_ausgerichtet rekonstruieren
TA=pycolmap.Reconstruction(D+'/teilmodell/0_ausgerichtet'); tac=zentren(TA)
X=np.array([tc[n] for n in tc]); Y=np.array([tac[n] for n in tc])
from sim3_robust import umeyama
s,R,t=umeyama(X,Y); print('alte Sim3 s',s,'Rest',np.abs(s*X@R.T+t-Y).max())
Bm=sfm2m(B); Am=sfm2m(s*A_@R.T+t); e=np.linalg.norm(Am-Bm,axis=1)
print('Rest je gemeinsames Bild (m): median %.2f p75 %.2f p90 %.2f max %.2f; <0.3m %d <0.5 %d <1 %d <2 %d von %d'%(np.median(e),*np.percentile(e,[75,90]),e.max(),(e<.3).sum(),(e<.5).sum(),(e<1).sum(),(e<2).sum(),len(e)))
# Lot: Bild-x im Teilnetz
Rt=np.array([tr[n] for n in tc]); L=lot_info(Rt); up_t=L['oben']; print('Teil-Lot stuetzend',L['stuetzend'],L['quelle'])
up_alt=R@up_t; up_alt/=np.linalg.norm(up_alt)
print('Neigung alte Einpassung: Teil-Lot gegen Modell-z = %.2f Grad'%np.degrees(np.arccos(up_alt@ZUP_SFM)))
# Lot aus PnP-Handyfotos im Hauptnetz
Rh=np.array([hr[n] for n in gem]); Lh=lot_info(Rh); print('Lot der PnP-Handyfotos gegen Modell-z %.2f Grad (stuetzend %.2f)'%(np.degrees(np.arccos(Lh['oben']@ZUP_SFM)),Lh['stuetzend']))
# Rotationsgegenprobe je Bild: R_h vs R_t R^T
ang=[]
for n in gem:
    Rp=tr[n]@R.T; d=Rp@hr[n].T; ang.append(np.degrees(np.arccos(np.clip((np.trace(d)-1)/2,-1,1))))
ang=np.array(ang); print('Rotationsabweichung je Bild Grad: median %.2f p90 %.2f >5Grad %d'%(np.median(ang),np.percentile(ang,90),(ang>5).sum()))
# Drift: Rest gegen Zeit (Name) 
import re
tt=np.array([int(n[13:19]) for n in gem]); o=np.argsort(tt)
for k in range(0,len(o),40):
    sl=o[k:k+40]; print('  zeit %s..%s Rest median %.2f m, Rot %.1f'%(gem[sl[0]][13:19],gem[sl[-1]][13:19],np.median(e[sl]),np.median(ang[sl])))
np.save('alt_sim3.npy',np.r_[s,R.ravel(),t])
json.dump(dict(gem=gem,rest=e.tolist(),rot=ang.tolist()),open('d2.json','w'))

import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
from teilmodell_sim3 import sim3_robust as lmeds
from sim3_robust import anwenden
HH,T=lade(); hc=zentren(HH); tc=zentren(T); gem=sorted(set(hc)&set(tc))
A_=np.array([tc[n] for n in gem]); B=sfm2m(np.array([hc[n] for n in gem]))
r=lmeds(A_,B,versuche=5000); M=np.eye(4); M[:3,:3]=r['s']*r['R']; M[:3,3]=r['t']; np.save('M_lmeds.npy',M)
print('LMedS Kamerazentren: s %.4f inlier %d/%d Rest median %.2f m'%(r['s'],r['inlier'].sum(),r['n'],np.median(r['res'][r['inlier']])))
Mn=json.load(open('/media/oem/rcdaten/tmp/handy_teil_spuren/einpassung.json'))['spuren']['M_teil_modell']; Mn=np.array(Mn)
probe=np.array([[*(np.array([1.94,-22.13])+s*np.array([-0.433,-0.901])),9.0] for s in (-12,0,18)]); pt=anwenden(np.linalg.inv(Mn),probe)
print('Brueckenprobe s-12/0/18: LMedS minus Spuren dz',(anwenden(M,pt)-probe)[:,2].round(2),'dxy',np.linalg.norm((anwenden(M,pt)-probe)[:,:2],axis=1).round(2))

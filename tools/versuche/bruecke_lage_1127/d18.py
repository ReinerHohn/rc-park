import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *; from bewerte import dom
HH,T=lade(); hc=zentren(HH)
for lab,f in [('Hauptnetz (ohne Handy)',lambda n: not n.startswith('IMG_')),('Handy PnP',lambda n: n.startswith('IMG_'))]:
    nm=[n for n in hc if f(n)]; C=sfm2m(np.array([hc[n] for n in nm])); g=dom(C[:,0],C[:,1],'dgm1'); o=dom(C[:,0],C[:,1],'dom1'); h=C[:,2]-g
    k=(o-g<0.5)&(np.abs(C[:,0])<80)&(np.abs(C[:,1])<80)
    print(lab,'frei n',k.sum())
    for y0,y1 in [(30,80),(15,30),(0,15),(-15,0),(-30,-15),(-80,-30)]:
        kk=k&(C[:,1]>=y0)&(C[:,1]<y1)
        if kk.sum(): print('   y %4d..%4d n %3d  Hoehe ueber DGM median %.2f p25 %.2f p75 %.2f'%(y0,y1,kk.sum(),np.median(h[kk]),*np.percentile(h[kk],[25,75])))

import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, json; from bewerte import dom
nm=json.load(open('cam_namen.json'))
m=np.array([0.9,-24.6]); u=np.array([-0.411,-0.912]); n=np.array([-u[1],u[0]])
for f in sys.argv[1:]:
    C=np.load(f); g=dom(C[:,0],C[:,1],'dgm1'); o=dom(C[:,0],C[:,1],'dom1'); h=C[:,2]-g
    d=C[:,:2]-m; S=d@u; Q=d@n
    frei=(o-g<0.5)   # kein Dach/Baum/Bruecke ueber der Kamera im DOM
    print(f)
    for lab,sel in [('frei, Turmseite y>0',frei&(C[:,1]>0)),('frei, y -15..0',frei&(C[:,1]<=0)&(C[:,1]>-15)),('frei, y<-15 (Strasse/Hang)',frei&(C[:,1]<=-15)),
                    ('Hang-Ende s>14 |q|<8',(S>14)&(np.abs(Q)<8)),('auf Bruecke s-8..13 |q|<2',(S>-8)&(S<13)&(np.abs(Q)<2))]:
        if sel.sum()==0: print('  %-28s n 0'%lab); continue
        print('  %-28s n %3d  Kamera ueber DGM median %.2f  p25 %.2f p75 %.2f   (DGM median %.2f)'%(lab,sel.sum(),np.median(h[sel]),*np.percentile(h[sel],[25,75]),np.median(g[sel])))

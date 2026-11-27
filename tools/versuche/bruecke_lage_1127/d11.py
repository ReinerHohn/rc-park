import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *; from ply import lies; from bewerte import teil_aus_wolke, dom
from sim3_robust import anwenden
P,C=lies('/media/oem/rcdaten/tmp/handy_teil_dicht/vereint.ply'); X=teil_aus_wolke(P); del P
Mn=np.load(sys.argv[1]); Pm=anwenden(Mn,X); del X
i=np.random.default_rng(0).choice(len(Pm),3000000,replace=False); np.savez_compressed(sys.argv[2],P=Pm[i].astype(np.float32),C=C[i])
# Boden gegen DGM1: 2-m-Zellen, p3 der z je Zelle, nur Zellen mit >=200 Punkten
cell=np.floor(Pm[:,:2]/2).astype(np.int64); key=cell[:,0]*100000+cell[:,1]
o=np.argsort(key); ks,st=np.unique(key[o],return_index=True); en=np.r_[st[1:],len(o)]
B=[]
for k,a,b in zip(ks,st,en):
    if b-a<200: continue
    z=Pm[o[a:b],2]; B.append((Pm[o[a],0]//2*2+1,Pm[o[a],1]//2*2+1,np.percentile(z,3)))
B=np.array(B); g=dom(B[:,0],B[:,1],'dgm1'); d=B[:,2]-g; nd=dom(B[:,0],B[:,1],'dom1')-g
bod=(np.abs(d)<2)&(nd<0.5)   # Zelle ohne Bebauung/Baum im DOM und Wolke nahe Gelaende
print('Bodenzellen',bod.sum(),'Wolke-DGM median %.3f MAD %.3f'%(np.median(d[bod]),np.median(np.abs(d[bod]-np.median(d[bod])))))
for nm,sel in [('Turm-Umfeld x>-20,y>-5',(B[:,1]>-5)),('Bruecken-Umfeld y<-5',(B[:,1]<=-5))]:
    k=bod&sel; print('  %s n %d median %.3f'%(nm,k.sum(),np.median(d[k])))
# Neigung des Restes: Ebene d = a x + b y + c
k=bod; A=np.c_[B[k,0],B[k,1],np.ones(k.sum())]; c=np.linalg.lstsq(A,d[k],rcond=None)[0]; print('  Restkippung Boden: %.3f Grad (x) %.3f Grad (y)'%(np.degrees(np.arctan(c[0])),np.degrees(np.arctan(c[1]))))
# Verschiebungssuche gegen DGM (Hanganstieg Landeseite gibt Lage laengs)
best=[]
for dx in np.arange(-3,3.01,0.5):
    for dy in np.arange(-3,3.01,0.5):
        gg=dom(B[:,0]-dx,B[:,1]-dy,'dgm1'); dd=B[:,2]-gg; ndd=dom(B[:,0]-dx,B[:,1]-dy,'dom1')-gg; kk=(np.abs(dd)<2)&(ndd<0.5)&(B[:,1]<-5)
        best.append((np.median(np.abs(dd[kk]-np.median(dd[kk]))),dx,dy,kk.sum()))
best.sort(); print('  beste Verschiebung gegen DGM (Brueckenumfeld) MAD/dx/dy/n',best[:4])
np.save(sys.argv[2]+'.boden.npy',np.c_[B,g,nd])

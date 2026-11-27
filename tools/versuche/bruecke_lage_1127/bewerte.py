import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
from ply import lies
from sim3_robust import anwenden
from geo import m2utm, Z0
from dom1_kachel import dom1_bilinear
v=np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)),'alt_sim3.npy')); s0,R0,t0=v[0],v[1:10].reshape(3,3),v[10:]
def teil_aus_wolke(P): return ((np.asarray(P)-t0)@R0)/s0
def wolke_teil(cache='wolke_teil_br.npy'):
    if os.path.exists(cache): return np.load(cache)
    P,C=lies('/media/oem/rcdaten/tmp/handy_teil_dicht/vereint.ply'); X=teil_aus_wolke(P)
    alt=sfm2m(P); m=np.array([0.9,-24.6]); sel=np.linalg.norm(alt[:,:2]-m,axis=1)<45
    np.save(cache,X[sel]); return X[sel]
def dom(x,y,art='dom1'):
    E,N=m2utm(np.atleast_1d(x),np.atleast_1d(y)); return dom1_bilinear(E,N,art)-Z0
def bewerte(Pm, m=np.array([0.9,-24.6]), u=np.array([-0.411,-0.912]), aus=True):
    """Pm: Brueckenwolke in Modellmetern. Liefert Kennzahlen gegen DOM1/DGM1."""
    n=np.array([-u[1],u[0]]); d=Pm[:,:2]-m; S=d@u; Q=d@n; Z=Pm[:,2]
    # Achse aus Wolke neu: Dachpunkte z>7.5, |q|<5, s -9..12
    k=(Z>7.5)&(Z<13)&(np.abs(Q)<5)&(S>-9)&(S<12)
    r=[]
    for a in np.arange(-8,12,2.0):
        kk=k&(S>=a)&(S<a+2)
        if kk.sum()<50: continue
        qc=np.median(Q[kk]); zt=np.percentile(Z[kk],98)
        qs=np.arange(-6,6.01,0.25); p=m+(a+1)*u; dd=dom(p[0]+qs*n[0],p[1]+qs*n[1]); qd=(qs*(dd>dd.max()-0.5)).sum()/(dd>dd.max()-0.5).sum()
        # Fahrbahn-/Deckunterkante: p3 der Punkte |q|<2 zwischen 3 und 8
        kd=(np.abs(Q-qc)<2)&(S>=a)&(S<a+2)&(Z>3)&(Z<8); zd=np.percentile(Z[kd],5) if kd.sum()>30 else np.nan
        r.append((a+1,qc,qd,zt,dd.max(),zd))
    r=np.array(r)
    if aus:
        for x in r: print('  s %5.1f  Dachmitte q Wolke %5.2f DOM %5.2f | Dach z Wolke(p98) %5.2f DOM-max %5.2f | Deck-Unterkante %5.2f'%tuple(x))
    dq=r[:,1]-r[:,2]; dz=r[:,3]-r[:,4]
    # Neigung Deck
    ok=np.isfinite(r[:,5]); k_=np.polyfit(r[ok,0],r[ok,5],1)[0] if ok.sum()>3 else np.nan
    kd=np.polyfit(r[:,0],r[:,3],1)[0]
    return dict(seite_m=float(np.median(dq)),seite_streu=float(np.std(dq)),dach_dz_m=float(np.median(dz)),dach_streu=float(np.std(dz)),deck_neigung_grad=float(np.degrees(np.arctan(k_))),dach_neigung_grad=float(np.degrees(np.arctan(kd))),deck_z=float(np.nanmedian(r[:,5])),n_bins=len(r))
if __name__=='__main__':
    X=wolke_teil(); print('Brueckenumgebung',len(X))
    v=np.load('alt_sim3.npy'); 
    for nm in sys.argv[1:]:
        if nm=='alt': Pm=sfm2m(s0*X@R0.T+t0)
        else: Pm=anwenden(np.load(nm),X)
        print(nm, json.dumps({k:round(v,3) for k,v in bewerte(Pm).items()}))

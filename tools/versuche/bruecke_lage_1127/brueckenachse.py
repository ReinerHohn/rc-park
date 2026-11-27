import numpy as np, json, sys
def achse(C, nm, von='160715', bis='161151'):
    sel=np.array([von<=n[13:19]<=bis for n in nm]); c=C[sel]
    m=c[:,:2].mean(0); u=np.linalg.svd(c[:,:2]-m)[2][0]; s=(c[:,:2]-m)@u
    # Hoehenverlauf der Kameras ueber Achse
    A=np.c_[s,np.ones(len(s))]; k=np.linalg.lstsq(A,c[:,2],rcond=None)[0]
    return m,u,s,c,k
def profil(P,m,u,breite=3.0):
    d=P[:,:2]-m; s=d@u; q=d@np.array([-u[1],u[0]]); sel=(np.abs(q)<breite)
    return s[sel],q[sel],P[sel,2]
if __name__=='__main__':
    w=np.load(sys.argv[1]); P=w['P'].astype(float); C=np.load(sys.argv[2]); nm=json.load(open('cam_namen.json'))
    m,u,s,c,k=achse(C,nm); print('Achse Mitte',m.round(1),'Richtung',u.round(3),'Kamerastrecke %.1f m, Kamerahoehe-Steigung %.2f Grad, z %.1f..%.1f'%(s.max()-s.min(),np.degrees(np.arctan(k[0])),c[:,2].min(),c[:,2].max()))
    S,Q,Z=profil(P,m,u)
    for a in range(-30,31,3):
        z=Z[(S>=a)&(S<a+3)]
        if len(z)>20: print('  s %3d..%3d n %6d z p5 %.1f p50 %.1f p95 %.1f'%(a,a+3,len(z),*np.percentile(z,[5,50,95])))

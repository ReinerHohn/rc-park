import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pickle, json, cv2
G=pickle.load(open('geo.pkl','rb')); O=json.load(open('/home/oem/git/rc-park/modelle/schwabentor-1122/objekt.json')); gid=O['lod2']['id']
W=[p[3] for p in G['polys'] if p[0]==gid and p[2]=='WallSurface']
def lod2_schnitt(z):
    S=[]
    for Q in W:
        if Q[:,2].min()<z<Q[:,2].max():
            # Kanten schneiden
            for a,b in zip(Q,np.roll(Q,-1,0)):
                if (a[2]-z)*(b[2]-z)<0: t=(z-a[2])/(b[2]-a[2]); S.append(a[:2]+t*(b[:2]-a[:2]))
    return np.array(S)
def rechteck(xy):
    r=cv2.minAreaRect(xy.astype(np.float32)); return r
def wolke_schnitt(P,z0,z1,box):
    k=(P[:,2]>z0)&(P[:,2]<z1)&(P[:,0]>box[0])&(P[:,0]<box[1])&(P[:,1]>box[2])&(P[:,1]<box[3]); return P[k,:2]
def seiten(xy, ang):
    # Ausdehnung in Richtung ang (Grad) robust: p1/p99
    a=np.radians(ang); u=np.array([np.cos(a),np.sin(a)]); v=np.array([-u[1],u[0]])
    s=xy@u; t=xy@v; return np.percentile(s,99)-np.percentile(s,1), np.percentile(t,99)-np.percentile(t,1), (np.percentile(s,1),np.percentile(s,99),np.percentile(t,1),np.percentile(t,99))
if __name__=='__main__':
    for f in sys.argv[1:]:
        P=np.load(f)['P'].astype(float)
        for z in [22,27,32]:
            L=lod2_schnitt(z)
            if len(L)<3: print('LoD2 z',z,'kein Schnitt'); continue
            r=rechteck(L); ang=r[2]; wl,hl,_=seiten(L,ang)
            box=(L[:,0].min()-3,L[:,0].max()+3,L[:,1].min()-3,L[:,1].max()+3)
            xy=wolke_schnitt(P,z-1,z+1,box)
            if len(xy)<200: print(f,'z',z,'zu wenig Wolke',len(xy)); continue
            wc,hc,ex=seiten(xy,ang)
            print('%s z %d: LoD2 %.2f x %.2f m | Wolke(p1-p99) %.2f x %.2f m | Verh %.3f %.3f n %d'%(f,z,wl,hl,wc,hc,wc/wl,hc/hl,len(xy)))

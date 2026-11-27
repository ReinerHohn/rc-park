import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,'/media/oem/scan/rc-park_tmp/lage_bruecke/tools')
import numpy as np, json, pickle
O=json.load(open('/home/oem/git/rc-park/modelle/schwabentor-1122/objekt.json'))
r=O['rahmen']; M0=np.array(r['mitte_utm']); XH=np.array(r['xhat_utm']); YH=np.array(r['yhat_utm']); Z0=r['gelaende']
def utm2m(E,N,H=None):
    d=np.stack([np.asarray(E)-M0[0],np.asarray(N)-M0[1]],-1); x=d@XH; y=d@YH
    return (x,y) if H is None else (x,y,np.asarray(H)-Z0)
def m2utm(x,y):
    p=M0+np.outer(x,XH)+np.outer(y,YH); return p[:,0],p[:,1]
if __name__=='__main__':
    import lod2_gebaeude as L
    gml=O['lod2']['gml']
    ch=L.building_chunks(open(gml,encoding='utf-8',errors='ignore').read())
    polys=[]
    for c in ch:
        meta=L.chunk_meta(c)
        for typ,P in L.polygons_from_chunk(c):
            if np.hypot(P[:,0].mean()-M0[0],P[:,1].mean()-M0[1])<140:
                x,y,z=utm2m(P[:,0],P[:,1],P[:,2]); polys.append((meta['id'],meta['name'],typ,np.c_[x,y,z]))
    print('LoD2 Flaechen',len(polys),'Gebaeude',len(set(p[0] for p in polys)))
    from dom1_kachel import dom1_hoehe
    g=np.arange(-120,120.5,1.0); X,Y=np.meshgrid(g,g); E,N=m2utm(X.ravel(),Y.ravel())
    dom=dom1_hoehe(E,N,'dom1').reshape(X.shape)-Z0; dgm=dom1_hoehe(E,N,'dgm1').reshape(X.shape)-Z0
    print('dom nan',np.isnan(dom).mean(),'dgm nan',np.isnan(dgm).mean(), 'dgm am Turm',dgm[120,120])
    pickle.dump(dict(polys=polys,g=g,dom=dom,dgm=dgm),open('geo.pkl','wb'))
    sch=[p for p in polys if p[0]==O['lod2']['id']]; A=np.vstack([p[3] for p in sch]); print('Schwabentor LoD2 bbox',A.min(0),A.max(0))

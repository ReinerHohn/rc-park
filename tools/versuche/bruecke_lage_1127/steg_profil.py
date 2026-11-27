import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, json; from bewerte import dom
sys.path.insert(0,'/media/oem/scan/rc-park_tmp/lage_bruecke/tools'); from teilmodell_spuren_einpassen import lies_ply
W=lies_ply(sys.argv[1]); P=np.stack([W['x'],W['y'],W['z']],1).astype(float)
e=json.load(open('/media/oem/rcdaten/tmp/handy_teil_spuren/einpassung.json'))['kandidaten'][sys.argv[2]]['steg']
m=np.array(e['mitte_xy']); u=np.array(e['richtung_xy']); n=np.array([-u[1],u[0]])
d=P[:,:2]-m; S=d@u; Q=d@n; k=(np.abs(Q)<5)&(np.abs(S)<30); P=P[k]; S=S[k]; Q=Q[k]
# Achse neu: Dachpunkte z 8.5..11.5 ueber Strasse (DGM<2)
g=dom(P[:,0],P[:,1],'dgm1')
rows=[]
for a in np.arange(-25,25,1.0):
    b=(S>=a)&(S<a+1)&(np.abs(Q)<3.5)
    gg=float(np.median(dom(*(m+(a+.5)*u),'dgm1'))) 
    z=P[b,2]; roof=(z>8.3)&(z<11.8); under=(z>gg+1.5)&(z<4.3)
    qroof=np.percentile(Q[b][roof],[2,98]) if roof.sum()>30 else (np.nan,np.nan)
    rows.append((a+.5,b.sum(),roof.sum(),under.sum(),gg,*qroof, np.percentile(z[roof],98) if roof.sum()>30 else np.nan, float(dom(*(m+(a+.5)*u),'dom1')[0])))
for r in rows: print('s %5.1f n %6d dach %6d unter %5d DGM %5.2f quer %5.2f..%5.2f Dach-p98 %5.2f DOM %5.2f'%r)

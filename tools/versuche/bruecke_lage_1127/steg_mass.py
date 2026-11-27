import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import numpy as np, json; from bewerte import dom
sys.path.insert(0,'/media/oem/scan/rc-park_tmp/lage_bruecke/tools'); from teilmodell_spuren_einpassen import lies_ply
from geo import m2utm, Z0
from dom1_kachel import dom1_hoehe
W=lies_ply(sys.argv[1]); P=np.stack([W['x'],W['y'],W['z']],1).astype(float); C=np.load(sys.argv[2]); nm=json.load(open('cam_namen.json'))
e=json.load(open('/media/oem/rcdaten/tmp/handy_teil_spuren/einpassung.json'))['kandidaten']['spuren']['steg']
m=np.array(e['mitte_xy']); u=np.array(e['richtung_xy']); n=np.array([-u[1],u[0]])
def roh(x,y): E,N=m2utm(np.atleast_1d(x),np.atleast_1d(y)); return dom1_hoehe(E,N,'dom1')-Z0
# DOM-Streifen: auf Achse und quer, Zellen >= 9 m
ss=np.arange(-25,25.01,0.5); qq=np.arange(-6,6.01,0.5)
D=np.array([[roh(*(m+s*u+q*n))[0] for q in qq] for s in ss])
ax=D[:,np.abs(qq)<=1].max(1); on=ax>=9.0
# laengster zusammenhaengender Lauf
best=(0,0,0); i=0
while i<len(on):
    if on[i]:
        j=i
        while j+1<len(on) and on[j+1]: j+=1
        if j-i>best[0]: best=(j-i,i,j)
        i=j+1
    else: i+=1
s0,s1=ss[best[1]],ss[best[2]]
print('DOM1-Dachstreifen (Rohzellen >= 9 m, |quer|<=1) laengs %.1f..%.1f m -> Laenge %.1f m (+-1 m Raster)'%(s0,s1,s1-s0))
wid=[(qq[D[k]>=9.0].max()-qq[D[k]>=9.0].min()+1.0) for k in range(best[1],best[2]+1) if (D[k]>=9).sum()>0]
print('DOM1-Streifenbreite (Zellen >= 9 m, +1 m Zelle) median %.1f m'%np.median(wid))
sl=np.polyfit(ss[best[1]:best[2]+1],ax[best[1]:best[2]+1],1)[0]; print('DOM1-Dach: z median %.2f, Neigung laengs %.2f Grad'%(np.median(ax[on]),np.degrees(np.arctan(sl))))
# Achse aus DOM-Streifen: quer-Schwerpunkt je s
qc=[(qq*(D[k]>=9)).sum()/max((D[k]>=9).sum(),1) for k in range(best[1],best[2]+1)]
print('DOM1-Streifen quer-Mitte gegen Wolkenachse: median %.2f, Drehung %.2f Grad'%(np.median(qc),np.degrees(np.arctan(np.polyfit(ss[best[1]:best[2]+1],qc,1)[0]))))
# Wolke
d=P[:,:2]-m; S=d@u; Q=d@n; k=(np.abs(Q)<4)&(S>s0)&(S<s1)
Pk=P[k]; Sk=S[k]; Qk=Q[k]
roof=(Pk[:,2]>8.3)&(Pk[:,2]<12)
ci=(np.floor(Sk[roof])*100+np.floor(Qk[roof])).astype(int); zz=Pk[roof,2]; o=np.argsort(ci); us,st=np.unique(ci[o],return_index=True); en=np.r_[st[1:],len(o)]
cells=[(us[t]//100,us[t]%100,np.percentile(zz[o[a:b]],95)) for t,(a,b) in enumerate(zip(st,en)) if b-a>15]
cz=np.array([c[2] for c in cells]); print('Wolke-Dach je 1-m-Zelle p95: median %.2f p90 %.2f (DOM-Zellen median %.2f p90 %.2f)'%(np.median(cz),np.percentile(cz,90),np.median(D[best[1]:best[2]+1][D[best[1]:best[2]+1]>=9]),np.percentile(D[best[1]:best[2]+1][D[best[1]:best[2]+1]>=9],90)))
hb=[]
for a in np.arange(s0,s1-1,2.0):
    b=roof&(Sk>=a)&(Sk<a+2)
    if b.sum()>50: hb.append((a+1,np.percentile(Pk[b,2],95)))
hb=np.array(hb); print('Wolke-Dach Neigung laengs (p95 je 2 m) %.2f Grad'%np.degrees(np.arctan(np.polyfit(hb[:,0],hb[:,1],1)[0])))
wq=[]
for a in np.arange(s0+2,s1-2,1.0):
    b=roof&(Sk>=a)&(Sk<a+1)
    if b.sum()>100: wq.append(np.percentile(Qk[b],98)-np.percentile(Qk[b],2))
print('Wolke-Dachbreite quer p2-p98 median %.2f m'%np.median(wq))
# Steg-Kameras (Laufflaeche)
d=C[:,:2]-m; Sc=d@u; Qc=d@n; kc=(np.abs(Qc)<2)&(Sc>s0)&(Sc<s1)&(C[:,2]>5)
print('Kameras auf dem Steg n %d z median %.2f p10..p90 %.2f..%.2f, Neigung Kamerapfad %.2f Grad'%(kc.sum(),np.median(C[kc,2]),*np.percentile(C[kc,2],[10,90]),np.degrees(np.arctan(np.polyfit(Sc[kc],C[kc,2],1)[0]))))
g=[dom(*(m+s*u),'dgm1')[0] for s in np.arange(s0,s1+0.1,1)]; print('DGM1 unter Achse: min %.2f max %.2f (Strasse bis Hangkante)'%(min(g),max(g)))
mitte=m+(s0+s1)/2*u; E,N=m2utm(np.array([mitte[0]]),np.array([mitte[1]]))
json.dump(dict(mitte_xy=mitte.tolist(),richtung_xy=u.tolist(),laenge_m=float(s1-s0),dach_z_p50=float(np.median(cz)),neigung_dach_grad=float(np.degrees(np.arctan(np.polyfit(hb[:,0],hb[:,1],1)[0]))),utm=[float(E[0]),float(N[0])]),open('steg_box.json','w'))
print('Mitte Modell',mitte.round(2),'UTM32',round(E[0],1),round(N[0],1),'Richtung Azimut (UTM, Grad von Nord)',end=' ')
from geo import XH,YH; dirutm=u[0]*XH+u[1]*YH; print('%.1f'%(np.degrees(np.arctan2(dirutm[0],dirutm[1]))%360))
# Seitenversatz je s: Wolkendach-Mitte (Median q der Dachpunkte) gegen DOM-Streifenmitte
r=[]
for kidx in range(best[1],best[2]+1):
    sv=ss[kidx]; b=roof&(np.abs(Sk-sv)<0.5)
    if b.sum()>50 and (D[kidx]>=9).sum()>0: r.append((sv,np.median(Qk[b]),(qq*(D[kidx]>=9)).sum()/(D[kidx]>=9).sum()))
r=np.array(r); dq=r[:,1]-r[:,2]; print('Seitenversatz Wolkendach-DOM-Streifen: median %.2f m, p25..p75 %.2f..%.2f, Trend %.2f Grad'%(np.median(dq),*np.percentile(dq,[25,75]),np.degrees(np.arctan(np.polyfit(r[:,0],dq,1)[0]))))

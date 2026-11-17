# Reihenabstand Dach gk: Logik wie tools/foto_dachreihen.py, Hangebene aus bauteile_foto.gauben (dach_z0, dach_s) an der Traufwand
import sys, json, glob, numpy as np, cv2
sys.path.insert(0,'tools'); from bauteile import Wand
o=json.load(open('modelle/kaufhaus_gk/objekt.json')); BF=o['bauteile_foto']; T=BF['traufwand']; W=Wand(T['a'],T['b'],aussen=T['aussen'])
z0=BF['gauben']['dach_z0']; sl=BF['gauben']['dach_s']; L=np.hypot(1,sl); res=0.01
for ur in ([6.5,7.4],[15.4,17.0],[1.5,4.6]):
  for nr in sys.argv[1].split(','):
    K=json.load(open(glob.glob('modelle/kaufhaus_gk/messprotokoll/K-'+nr+'*.json')[0]))['kamera']; Rm,_=cv2.Rodrigues(np.array(K['rvec']))
    im=cv2.imread(glob.glob('daten/kaufhaus_gk/fotos/'+nr+'*')[0],0)
    s=np.arange(0.5,6.0,res); u=np.arange(ur[0],ur[1],res); S,U=np.meshgrid(s,u,indexing='ij')
    wv=-S/L; zv=z0+sl*S/L
    X=np.stack([W.a[0]+U*W.t[0]+wv*W.n[0], W.a[1]+U*W.t[1]+wv*W.n[1], zv],-1)
    c=X@Rm.T+np.array(K['t']); x,y=c[...,0]/c[...,2],c[...,1]/c[...,2]; d=1+K.get('k1',0.0)*(x*x+y*y)
    mx=(K['cx']+K['f_px']*x*d).astype(np.float32); my=(K['cy']+K['f_px']*y*d).astype(np.float32)
    ppm_img=np.hypot(np.diff(mx,axis=0),np.diff(my,axis=0)).mean()/res
    oo=cv2.remap(im,mx,my,cv2.INTER_LINEAR); g=oo.astype(np.float32); g-=cv2.GaussianBlur(g,(0,0),30); prof=g.mean(1); prof-=prof.mean()
    ac=np.correlate(prof,prof,'full')[len(prof)-1:]; ac/=ac[0]
    pk=[(round(i*res,3),round(float(ac[i]),2)) for i in range(6,len(ac)-1) if ac[i]>ac[i-1] and ac[i]>=ac[i+1]][:4]
    print(ur, nr[:16], 'px/m Foto %.0f'%ppm_img, pk)

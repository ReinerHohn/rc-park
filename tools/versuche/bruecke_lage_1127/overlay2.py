import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *; import cv2, pickle
from sim3_robust import anwenden
from overlay import zone
G=pickle.load(open('geo.pkl','rb')); O=json.load(open('/home/oem/git/rc-park/modelle/schwabentor-1122/objekt.json'))
kanten=[]
for gid,nm,typ,Q in G['polys']:
    if typ!='WallSurface' and typ!='RoofSurface': continue
    if gid!=O['lod2']['id']: continue
    for a,b in zip(Q,np.roll(Q,-1,0)):
        L=np.linalg.norm(b-a)
        if L>0.5: kanten.append(np.linspace(a,b,max(2,int(L*20))))
K=np.vstack(kanten)
def proj_teil(im,cam,Xt):
    T_=im.cam_from_world(); Xc=Xt@T_.rotation.matrix().T+T_.translation; ok=Xc[:,2]>0.3
    uv=np.full((len(Xt),2),np.nan); uv[ok]=np.array(cam.img_from_cam(Xc[ok])); return uv
def male(img,uv,col,r=0):
    ok=np.isfinite(uv[:,0])&(uv[:,0]>=0)&(uv[:,0]<img.shape[1])&(uv[:,1]>=0)&(uv[:,1]<img.shape[0])
    for x,y in uv[ok].astype(int):
        if r: cv2.circle(img,(x,y),r,col,-1)
        else: img[y,x]=col
if __name__=='__main__':
    T=pycolmap.Reconstruction(D+'/teilmodell/0')
    Ms=[('alt',np.load('M_alt.npy'),(0,0,255)),('neu',np.load('M_hauptge3_0.15.npy'),(0,255,0))]
    Pn=np.load('wolke_neu_m.npz')['P'].astype(float); Pn=Pn[zone(Pn)][::3]
    for name in sys.argv[1:]:
        im=[i for i in T.images.values() if i.name==name][0]; cam=T.cameras[im.camera_id]
        img=cv2.imread(D+'/bilder/'+name); 
        if img.shape[1]!=cam.width: img=cv2.resize(img,(cam.width,int(img.shape[0]*cam.width/img.shape[1])))
        pans=[img.copy()]
        for lab,M,col in Ms:
            p=img.copy(); Mi=np.linalg.inv(M)
            if lab=='neu': male(p,proj_teil(im,cam,anwenden(Mi,Pn)),(255,255,0),1)
            male(p,proj_teil(im,cam,anwenden(Mi,K)),col,2)
            cv2.putText(p,'LoD2 (amtlich) mit %s-Einpassung'%lab+(' + Wolke tuerkis' if lab=='neu' else ''),(10,40),0,1.2,(255,255,255),5); cv2.putText(p,'LoD2 (amtlich) mit %s-Einpassung'%lab+(' + Wolke tuerkis' if lab=='neu' else ''),(10,40),0,1.2,col,2)
            pans.append(p)
        out=np.hstack(pans); sc=2400/out.shape[1]; cv2.imwrite('fo_'+name[13:19]+'.jpg',cv2.resize(out,None,fx=sc,fy=sc),[cv2.IMWRITE_JPEG_QUALITY,85])

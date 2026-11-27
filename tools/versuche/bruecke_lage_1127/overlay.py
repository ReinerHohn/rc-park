import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *; import cv2
m=np.array([0.9,-24.6]); u=np.array([-0.411,-0.912]); n=np.array([-u[1],u[0]])
def zone(P):
    d=P[:,:2]-m; S=d@u; Q=d@n; return (S>-11)&(S<17)&(np.abs(Q)<4)&(P[:,2]>4)&(P[:,2]<13)
def m2sfm(X): return sA*np.asarray(X)@RA.T+tA
def proj(M,im,X):
    cam=M.cameras[im.camera_id]; T_=im.cam_from_world(); Xc=X@T_.rotation.matrix().T+T_.translation; ok=Xc[:,2]>0.1
    uv=np.full((len(X),2),np.nan); uv[ok]=np.array(cam.img_from_cam(Xc[ok])); return uv
def zeichne(M, name, bildpfad, wolken, aus, titel):
    im=[i for i in M.images.values() if i.name==name][0]; img=cv2.imread(bildpfad); cam=M.cameras[im.camera_id]
    if img.shape[1]!=cam.width: img=cv2.resize(img,(cam.width,int(img.shape[0]*cam.width/img.shape[1])))
    ov=img.copy()
    for X,col in wolken:
        uv=proj(M,im,m2sfm(X)); ok=np.isfinite(uv[:,0])&(uv[:,0]>=0)&(uv[:,0]<img.shape[1])&(uv[:,1]>=0)&(uv[:,1]<img.shape[0])
        for x,y in uv[ok].astype(int): ov[y,x]=col; 
        for x,y in uv[ok][::3].astype(int): cv2.circle(ov,(x,y),1,col,-1)
    sc=1000/img.shape[1]; a=cv2.resize(img,None,fx=sc,fy=sc); b=cv2.resize(ov,None,fx=sc,fy=sc)
    for t,y in zip(titel,(25,50)): cv2.putText(b,t,(10,y),0,.7,(255,255,255),3); cv2.putText(b,t,(10,y),0,.7,(0,0,0),1)
    cv2.imwrite(aus,np.hstack([a,b]),[cv2.IMWRITE_JPEG_QUALITY,85])
if __name__=='__main__':
    neu=np.load('wolke_neu_m.npz')['P'].astype(float); alt=np.load('wolke_alt_m.npz')['P'].astype(float)
    neu=neu[zone(neu)][::4]; alt=alt[zone(alt)][::4]
    W=[(alt,(0,0,255)),(neu,(0,255,0))]
    H=pycolmap.Reconstruction('/media/oem/scan/rc-park_daten/schwabentor-1122/pipe/sfm/sparse/0')
    for vf in ['video_frames_Bbzk0Qpb5l0__vf_244.jpg','video_frames_Bbzk0Qpb5l0__vf_240.jpg']:
        zeichne(H,vf,'/media/oem/scan/rc-park_daten/schwab_v3/fotos/'+vf,W,'ov_'+vf[-10:],['Hauptnetz-Kamera '+vf[-10:-4]+' (unabh. vom Teilnetz)','rot=alte Einpassung, gruen=neu (3D-Spuren)'])
    HH,T=lade()
    for nmx in sys.argv[1:]:
        zeichne(HH,nmx,D+'/bilder/'+nmx,W,'ov_'+nmx[9:21]+'.jpg',['PnP-Kamera im Hauptnetz '+nmx[9:21],'rot=alt, gruen=neu'])

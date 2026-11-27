import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from overlay import *
def crop_panels(M,name,bildpfad,X_list,box,aus,titel):
    im=[i for i in M.images.values() if i.name==name][0]; img=cv2.imread(bildpfad); cam=M.cameras[im.camera_id]
    if img.shape[1]!=cam.width: img=cv2.resize(img,(cam.width,int(img.shape[0]*cam.width/img.shape[1])))
    x0,x1,y0,y1=box; pans=[img[y0:y1,x0:x1].copy()]
    for (X,col,lab) in X_list:
        ov=img.copy(); uv=proj(M,im,m2sfm(X)); ok=np.isfinite(uv[:,0])
        for x,y in uv[ok].astype(int):
            if 0<=x<img.shape[1] and 0<=y<img.shape[0]: ov[y,x]=col
        p=cv2.addWeighted(img,0.35,ov,0.65,0)[y0:y1,x0:x1]; cv2.putText(p,lab,(5,20),0,.6,col,2); pans.append(p)
    f=max(1,int(900/(x1-x0))); pans=[cv2.resize(p,None,fx=f,fy=f,interpolation=cv2.INTER_NEAREST) for p in pans]
    out=np.vstack(pans) if (x1-x0)>(y1-y0)*1.3 else np.hstack(pans); cv2.putText(out,titel,(5,out.shape[0]-10),0,.7,(255,255,255),2); cv2.imwrite(aus,out,[cv2.IMWRITE_JPEG_QUALITY,88])
if __name__=='__main__':
    neu=np.load('wolke_neu_m.npz')['P'].astype(float); alt=np.load('wolke_alt_m.npz')['P'].astype(float)
    neu=neu[zone(neu)]; alt=alt[zone(alt)]
    L=[(alt,(0,0,255),'alt (Kamerazentren-Umeyama)'),(neu,(0,255,0),'neu (direkte 3D-Spuren)')]
    for extra in sys.argv[1:]:
        L.append((np.load(extra)['P'].astype(float),(255,0,255),extra))
    H=pycolmap.Reconstruction('/media/oem/scan/rc-park_daten/schwabentor-1122/pipe/sfm/sparse/0')
    for vf,box in [('video_frames_Bbzk0Qpb5l0__vf_244.jpg',(1250,1920,560,860)),('video_frames_Bbzk0Qpb5l0__vf_240.jpg',(1100,1920,450,900))]:
        crop_panels(H,vf,'/media/oem/scan/rc-park_daten/schwab_v3/fotos/'+vf,L,box,'zoom_'+vf[-10:],'Hauptnetz-Kamera '+vf[-10:-4])

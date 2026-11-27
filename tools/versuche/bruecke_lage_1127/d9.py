import sys,os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import *
import copy
HH,T=lade()
# Kandidat: reprojektionsbasiert (pycolmap/COLMAP, BSD-3)
for mo,me in [(0.3,8.0),(0.3,4.0)]:
    S=pycolmap.align_reconstructions_via_reprojections(T,HH,min_inlier_observations=mo,max_reproj_error=me)
    if S is None: print('reproj',mo,me,'None'); continue
    M=np.eye(4); M[:3,:4]=S.matrix(); print('reproj',mo,me,'s',S.scale)
    # nach Modellmeter: X_m = (M X - tA) RA / sA
    Mm=np.eye(4); Mm[:3,:3]=RA.T/sA; Mm[:3,3]=-RA.T@tA/sA; np.save('M_reproj_%g.npy'%me,Mm@M)
def sim3_sfm_aus_modell(Mmod):
    Ms=np.eye(4); Ms[:3,:3]=sA*RA; Ms[:3,3]=tA; return Ms@Mmod
def reproj(Mmod, nhmin=2):
    Ms=sim3_sfm_aus_modell(Mmod); sc=np.cbrt(np.linalg.det(Ms[:3,:3])); Rs=Ms[:3,:3]/sc; ts=Ms[:3,3]
    hn={i.name:i for i in HH.images.values() if i.has_pose}; E=[]
    for im in T.images.values():
        if not im.has_pose or im.name not in hn: continue
        b=hn[im.name]; cam=T.cameras[im.camera_id]
        Rc=im.cam_from_world().rotation.matrix(); tc_=im.cam_from_world().translation
        # Welt_sfm = sc Rs Xt + ts  -> Xt = Rs^T (W-ts)/sc ; Kamera: Rc Xt + tc
        P=[];uv=[]
        for k,p2 in enumerate(b.points2D):
            if p2.has_point3D():
                pt=HH.points3D[p2.point3D_id]
                if sum(1 for e in pt.track.elements if not HH.images[e.image_id].name.startswith('IMG_'))>=nhmin: P.append(pt.xyz); uv.append(p2.xy)
        if len(P)<5: continue
        P=np.array(P); Xt=((P-ts)@Rs)/sc; Xc=Xt@Rc.T+tc_; ok=Xc[:,2]>0
        pr=np.array(cam.img_from_cam(Xc[ok])); E.append(np.linalg.norm(pr-np.array(uv)[ok],axis=1))
    E=np.concatenate(E); return np.median(E), np.percentile(E,75), (E<4).mean(), len(E)
v=np.load('alt_sim3.npy'); s,R,t=v[0],v[1:10].reshape(3,3),v[10:]
Malt_s=np.eye(4); Malt_s[:3,:3]=s*R; Malt_s[:3,3]=t; Mm=np.eye(4); Mm[:3,:3]=RA.T/sA; Mm[:3,3]=-RA.T@tA/sA; np.save('M_alt.npy',Mm@Malt_s)
for f in ['M_alt.npy','M_hauptge3_0.15.npy','M_alle_0.30.npy','M_reproj_8.npy','M_reproj_4.npy']:
    if os.path.exists(f): print(f,'Reproj Hauptpunkte in Teilkameras: median %.1f px p75 %.1f  <4px %.0f%%  n %d'%(lambda r:(r[0],r[1],100*r[2],r[3]))(reproj(np.load(f))))

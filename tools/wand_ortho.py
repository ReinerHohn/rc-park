#!/usr/bin/env python3
"""wand_ortho.py - Foto auf eine senkrechte Wandebene entzerren (u/z-Raster) und Wandpunkte zurueck in Originalpixel rechnen (Hilfe fuer foto_mass.py-Picks).

  wand_ortho.py bild <objekt.json> FOTO u0 u1 z0 z1 px d AUS.jpg --a x y --b x y     entzerrtes Bild; Ebene durch die Wandecken a, b, um d nach aussen versetzt
  wand_ortho.py px   <objekt.json> FOTO d u z [u z ...] --a x y --b x y              Originalpixel der Wandpunkte (fuer foto_mass.py --mess / --tri)
u laeuft ab Ecke a Richtung b, z ist die Hoehe im Modellrahmen; 'aussen' = Seite, auf der die Kamera steht. FOTO = Name ohne 'K-' (K-<FOTO>.json muss existieren).
Entstanden 15.11.2026 (Schwabentor Tordurchfahrt): am entzerrten Frontalfoto lassen sich Oeffnungen in Metern ablesen; gemessen wird trotzdem ueber foto_mass.py.
"""
import sys,os,json,glob,cv2,numpy as np
arg=sys.argv; A=np.array([float(v) for v in arg[arg.index("--a")+1:arg.index("--a")+3]]); B=np.array([float(v) for v in arg[arg.index("--b")+1:arg.index("--b")+3]]); arg=arg[:min(arg.index("--a"),arg.index("--b"))]
OBJ=arg[2]; OD=os.path.dirname(os.path.abspath(OBJ)); ROOT=os.path.dirname(os.path.dirname(OD)); FD=json.load(open(OBJ))["fotos_dir"]; del arg[2]; sys.argv=arg
t=(B-A)/np.linalg.norm(B-A); n=np.array([t[1],-t[0]])
def kam(nm):
    K=json.load(open(os.path.join(OD,"messprotokoll","K-"+nm+".json")))["kamera"]; S_=np.array(K["standort_xyz"][:2]); global n; n=n if (S_-A)@n>0 else -n; return nm,K,cv2.Rodrigues(np.array(K["rvec"]))[0],np.array(K["t"])
def proj(K,R,tt,X):
    p=X@R.T+tt; x=p[:,0]/p[:,2]; y=p[:,1]/p[:,2]; f=1+float(K.get("k1") or 0)*(x*x+y*y); return np.c_[K["f_px"]*x*f+K["cx"],K["f_px"]*y*f+K["cy"]]
def welt(u,z,d): u=np.asarray(u,float); z=np.asarray(z,float); return np.c_[A[0]+u*t[0]+d*n[0],A[1]+u*t[1]+d*n[1],z]
if sys.argv[1]=="bild":
    nm,K,R,tt=kam(sys.argv[2]); u0,u1,z0,z1,px=[float(v) for v in sys.argv[3:8]]; d=float(sys.argv[8]) if len(sys.argv)>8 else 0.0
    W=int((u1-u0)/px); H=int((z1-z0)/px); yy,xx=np.mgrid[0:H,0:W]; SP=(t[0]*n[1]-t[1]*n[0])>0   # von der Kamera aus laeuft u nach LINKS -> Bild so zeichnen, wie man die Wand sieht (15.11.2026: Suedbild war gespiegelt)
    ucol=(u1-(xx.ravel()+.5)*px) if SP else (u0+(xx.ravel()+.5)*px); uv=proj(K,R,tt,welt(ucol,z0+(H-1-yy.ravel()+.5)*px,d))
    im=cv2.imread((glob.glob(os.path.join(ROOT,FD,nm+".*")) or glob.glob(os.path.join(ROOT,FD,nm+"_*")))[0]); o=cv2.remap(im,uv[:,0].reshape(H,W).astype(np.float32),uv[:,1].reshape(H,W).astype(np.float32),cv2.INTER_LINEAR)
    s=max(1,int(round(1000/max(H,W)))); o=cv2.resize(o,None,fx=s,fy=s,interpolation=cv2.INTER_CUBIC); st=0.5 if (u1-u0)<=6 else 1.0
    for g in np.arange(np.ceil(u0/st)*st,u1,st): X=int(((u1-g) if SP else (g-u0))/px*s); cv2.line(o,(X,0),(X,o.shape[0]),(0,255,255),1); cv2.putText(o,"u%.1f"%g,(X+2,12),0,0.4,(0,255,255),1)
    for g in np.arange(np.ceil(z0/st)*st,z1,st): Y=int((H-(g-z0)/px)*s); cv2.line(o,(0,Y),(o.shape[1],Y),(0,255,255),1); cv2.putText(o,"z%.1f"%g,(2,Y-2),0,0.4,(0,255,255),1)
    cv2.imwrite(sys.argv[9] if len(sys.argv)>9 else "o.jpg",o); print(o.shape)
else:
    nm,K,R,tt=kam(sys.argv[2]); d=float(sys.argv[3]); v=[float(x) for x in sys.argv[4:]]; uv=proj(K,R,tt,welt(v[0::2],v[1::2],d)); print(" ".join("%.0f %.0f"%(a,b) for a,b in uv))

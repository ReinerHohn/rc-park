"""Variante D: Haus (Fluegel ohne Turmwand-Streifen) nach Nutzerlage verschoben; Streifen bleibt als Turmwand.
Pose (Nutzer 14:22, Viewer v14-Regler): Drehung -180 Grad um (0/-0,86) im zentrierten Rahmen, dx 6,5, dy 7,1, dz 0. ANNAHME: grobe Schaetzung des Nutzers.
Originale bleiben unveraendert."""
import numpy as np, json
S="/home/oem/git/rc-park/modelle/schwabentor/sfm/"
M=np.load(S+"punkte_modell_schwabentor.npy").astype(np.float64); Col=np.load(S+"punkte_farben_schwabentor.npy")
V=np.load(S+"punkte_modell_schwabentor_veto.npy"); c=np.median(V[:,:2],axis=0)
P=M-np.array([c[0],c[1],0])
wing=(P[:,0]>3.5)&(P[:,1]<-1.5); far=np.hypot(P[:,0]-0.1,P[:,1]+0.9)>25
b=-0.74*P[:,0]+0.67*P[:,1]; strip=wing&(b>=-5.3)&(b<-3.9)&(P[:,2]>8); house=wing&~strip
TH,DX,DY,DZ=-180.0,6.5,7.1,0.0; cen=np.array([0.0,-0.86]); t=np.radians(TH)
Q=P.copy(); x=P[house,0]-cen[0]; y=P[house,1]-cen[1]
Q[house,0]=cen[0]+np.cos(t)*x-np.sin(t)*y+DX; Q[house,1]=cen[1]+np.sin(t)*x+np.cos(t)*y+DY; Q[house,2]=P[house,2]+DZ
keep=~far; out=Q[keep]+np.array([c[0],c[1],0])
np.save(S+"punkte_modell_schwabentor_variante_d.npy",out.astype(M.dtype if False else np.float32)); np.save(S+"punkte_farben_schwabentor_variante_d.npy",Col[keep])
info=dict(basis="punkte_modell_schwabentor.npy ohne 498 Fernpunkte",haus_punkte=int(house.sum()),turmwand_streifen=int(strip.sum()),drehung_grad=TH,dx=DX,dy=DY,dz=DZ,zentrum=[0.0,-0.86],quelle="Nutzerschaetzung Viewer 14:22",n=int(keep.sum()))
json.dump(info,open(S+"punkte_variante_d_schwabentor.json","w"),indent=1,ensure_ascii=False); print(info)
Hc=Q[house]; print("Hausmitte neu",Hc.mean(0).round(1),"Punkte",len(out))

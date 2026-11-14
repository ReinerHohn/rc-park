"""Variante I: ganze Wolke Massstab x1,80, Drehung 134 Grad (um Turmmitte der Wolke), Turm auf LoD2-PLcp (Schwabentor, Rundanbau = Treppentuermchen).
Fit: nur Wandfit (Punkte z 1-6 m ohne Fluegel gegen LoD2-Wandlinien, FFT GPU) ueber Massstab 1,0-2,0 x Drehung 100-160 Grad, Turmanker +-6 m
(Scratchpad lage_skala.py, Log lageskala.log): globales Maximum 0,49 bei 1,80/134 (alter Massstab 0,39).
Unabhaengige Belege (nicht im Fit): Muenster-Entfernung der 10 Muensterturm-Fotos 312 m (LoD2 310 m); EXIF-GPS-Fit Massstab 1,84, Drehung 134-136 Grad;
Turmbreite 6,8 m x 1,8 = 12,2 m (PLcp 12,1 m); Kameras in Gebaeuden 1 %; Kamera-Median 4 m vom GPS-Median.
Alte Lage: Turm auf Tvdv (Nachbarhaus 28,7 m), Massstab 1/1,8 zu klein, 134 Grad verdreht -> Fluegel auf der Strasse.
ANNAHME: Boden der Wolke bei z=0 (Median p5 je 1-m-Zelle 0,3 m), z mit gleichem Massstab um 0 skaliert; Gelaende eben."""
import json,numpy as np
S="/home/oem/git/rc-park/modelle/schwabentor/sfm/"
SK,DREH=1.80,134.0
TC,BASIS,D=np.array([7.8,0.5]),np.array([-23.7,-5.8]),np.array([-0.25,3.0])
obj=json.load(open("/home/oem/git/rc-park/modelle/schwabentor/objekt.json")); r=obj["rahmen"]; xh=np.array(r["xhat_utm"]); yh=np.array(r["yhat_utm"])
def lage_i(X):
    X=np.asarray(X,float).copy(); U=X[:,0:1]*xh+X[:,1:2]*yh; t=np.radians(DREH); R=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
    U2=SK*(U-TC)@R.T+TC+BASIS+D; X[:,0]=U2@xh; X[:,1]=U2@yh; X[:,2]=SK*X[:,2]; return X
if __name__=="__main__":
    M=np.load(S+"punkte_modell_schwabentor.npy"); C=np.load(S+"punkte_farben_schwabentor.npy")
    np.save(S+"punkte_modell_schwabentor_variante_i.npy",lage_i(M).astype(M.dtype)); np.save(S+"punkte_farben_schwabentor_variante_i.npy",C)
    print("geschrieben",len(M))

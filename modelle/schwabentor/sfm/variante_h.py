"""Variante H: ganze Wolke um 126 Grad (um die Turmmitte der Wolke) gedreht und Turm auf LoD2-PLcp (Schwabentor mit Treppentuermchen) gesetzt.
Belege (2026-11-14, unabhaengig voneinander): Wandfit mit Turmanker Max. bei 125 Grad; 10 Muenster-Fotos (Foto zeigt Tor vom Muensterturm) zeigen
nach Drehung auf LoD2-Muenster (Fehler 0,5 Grad bei 126); EXIF-GPS aller Fotos: Drehung 134-136 Grad (Bootstrap 134-142). Bisherige Lage (0 Grad) hatte
den Turm auf Tvdv (28,7 m) statt PLcp (37 m Wand, Rundanbau = Treppentuermchen 'Zinnfiguren-Klause', Foto IMG_20261106_113545_1).
ANNAHME: Massstab und Hoehen unveraendert (GPS-Massstab 1,84 unglaubwuerdig: Fernkameras tiefenschwach, Torfotos streuen 20-29 m); Gelaende eben."""
import json,numpy as np
S="/home/oem/git/rc-park/modelle/schwabentor/sfm/"
DREH,TC,BASIS,D=126.0,np.array([7.8,0.5]),np.array([-23.7,-5.8]),np.array([2.75,5.25])   # aus lage_kurve.py (Scratchpad, Log lagekurve3.log)
obj=json.load(open("/home/oem/git/rc-park/modelle/schwabentor/objekt.json")); r=obj["rahmen"]; xh=np.array(r["xhat_utm"]); yh=np.array(r["yhat_utm"])
def lage_h(X):
    X=np.asarray(X,float).copy(); U=X[:,0:1]*xh+X[:,1:2]*yh; t=np.radians(DREH); R=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
    U2=(U-TC)@R.T+TC+BASIS+D; X[:,0]=U2@xh; X[:,1]=U2@yh; return X
if __name__=="__main__":
    M=np.load(S+"punkte_modell_schwabentor.npy"); C=np.load(S+"punkte_farben_schwabentor.npy")
    np.save(S+"punkte_modell_schwabentor_variante_h.npy",lage_h(M).astype(M.dtype)); np.save(S+"punkte_farben_schwabentor_variante_h.npy",C)
    print("geschrieben", len(M))

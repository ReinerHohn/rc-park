"""Variante J = Variante I (ganze Wolke x1,80, 134 Grad, Turm auf PLcp) + Fluegel (eigenes Teilnetz, Ringseite des Fachwerkhauses Tvdv) neu gesetzt.
Fluegel: Drehung 189 Grad um seine Mitte, auf Suedwand Tvdv/PLcp (Aussenseite). Suche: Drehung 0-359 x +-20 m (fluegel_suche.py), Feinlage (fluegel_fein.py).
Belege (nicht im Fit): Turmkanten-Streifen des Fluegels (z bis 35,6 m) liegt im einzigen >=33 m hohen Teil (PLcp); 14 von 16 Aussenkameras (ca_) stehen VOR der
Fassade, Gebaeude dahinter (Kandidaten 70/268 Grad: Kameras im Haus bzw. Wand im Haus); Lage passt zur Nutzerbeschreibung (von aussen: Turm links, Haus rechts).
ANNAHME: Fluegel starr (eigenes Teilnetz), nur Lage in der Ebene geaendert, Hoehe aus Variante I; Wandabstand Median 0,46 m, 79 % < 1 m."""
import sys,json,numpy as np
S="/home/oem/git/rc-park/modelle/schwabentor/sfm/"; sys.path.insert(0,S); import variante_i as VI
FL_DREH,FL_D=189.0,np.array([-4.25,-9.25])
WC=np.array([-24.9855, -4.4746]); TV=np.array([1.182, 2.1364])
obj=json.load(open("/home/oem/git/rc-park/modelle/schwabentor/objekt.json")); r=obj["rahmen"]; xh=np.array(r["xhat_utm"]); yh=np.array(r["yhat_utm"])
def fluegel_maske(X0):
    V=np.load(S+"punkte_modell_schwabentor_veto.npy"); c=np.median(V[:,:2],axis=0); return (X0[:,0]-c[0]>3.5)&(X0[:,1]-c[1]<-1.5)
def lage_j(X0,F=None):
    X0=np.asarray(X0,float); F=fluegel_maske(X0) if F is None else F; X=VI.lage_i(X0)
    U=X[F][:,0:1]*xh+X[F][:,1:2]*yh; t=np.radians(FL_DREH); R=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
    U2=(U-WC)@R.T+TV+FL_D; X[F,0]=U2@xh; X[F,1]=U2@yh; return X
if __name__=="__main__":
    M=np.load(S+"punkte_modell_schwabentor.npy"); C=np.load(S+"punkte_farben_schwabentor.npy")
    np.save(S+"punkte_modell_schwabentor_variante_j.npy",lage_j(M).astype(M.dtype)); np.save(S+"punkte_farben_schwabentor_variante_j.npy",C); print("geschrieben",len(M))

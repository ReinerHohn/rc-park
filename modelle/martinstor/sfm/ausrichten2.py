import pycolmap, numpy as np, json, os, cv2
S=os.path.dirname(os.path.abspath(__file__))
rec=pycolmap.Reconstruction(S+"/sparse/0")
P=np.array([q.xyz for q in rec.points3D.values()])
zen={os.path.splitext(i.name)[0]: np.array(i.cam_from_world().inverse().translation) for i in rec.images.values()}
# 1) Senkrechte: die Kamerazentren liegen alle etwa auf Augenhoehe -> ihre Ebene ist waagrecht.
Z=np.array(list(zen.values())); c=Z.mean(0)
u,s,vt=np.linalg.svd(Z-c); n=vt[2]                                  # Normale der Kameraebene = Senkrechte
if n @ (P.mean(0)-c) < 0: n=-n                                      # soll zum Bauwerk zeigen (nach oben)
# 2) Turmpunkte: alles im Zylinder um den Schwerpunkt der hohen Punkte
h=(P-c)@n; kern=P[h>np.percentile(h,60)]
achse=kern.mean(0); d=np.linalg.norm((P-achse)-np.outer((P-achse)@n,n),axis=1)
turm=P[d<np.percentile(d,55)]
ht=(turm-c)@n
# 3) Massstab: Hoehe der Turmpunkte (5.-99. Perzentil) gegen die bekannte Hoehe ueber Gelaende
unten,oben=np.percentile(ht,2), np.percentile(ht,99.5)
H_MODELL=60.0-6.2                                                   # Spitze minus Sockeloberkante: der Bereich, den die Fotos zeigen
s_=H_MODELL/(oben-unten); print(f"Senkrechte aus {len(Z)} Kameras, Turmpunkte {len(turm)}, Massstab {s_:.3f} Einheiten/m")
# 4) Drehung um die Senkrechte: Hauptachse des Grundrisses der Turmpunkte auf die Modellachsen legen
e1=np.array([1.0,0,0]); e1=e1-(e1@n)*n; e1/=np.linalg.norm(e1); e2=np.cross(n,e1)
xy=np.c_[(turm-achse)@e1,(turm-achse)@e2]*s_
w=np.linalg.svd(xy-xy.mean(0))[2][0]; phi=np.arctan2(w[1],w[0])
cr,sr=np.cos(-phi),np.sin(-phi); xy2=xy@np.array([[cr,-sr],[sr,cr]]).T
zm=((turm-c)@n-unten)*s_+6.2
print(f"Turm im Modellsystem: z {zm.min():.1f}..{zm.max():.1f} m, Grundriss {xy2[:,0].ptp():.1f} x {xy2[:,1].ptp():.1f} m (Modell: 9,8 x 11,3 am Sockel)")
for z0 in range(6,62,8):
    k=(zm>=z0)&(zm<z0+8)
    if k.sum()>20: print(f"  z {z0:2d}-{z0+8:2d} m: {k.sum():4d} Punkte, Breite {xy2[k][:,0].ptp():5.1f} x {xy2[k][:,1].ptp():5.1f} m")
np.save(S+"/turm_modell.npy", np.c_[xy2, zm])

#!/usr/bin/env python3
"""masspruefung.py - Massstabs-Beweis fuer Martinstor: Hoehenkarte des Modells gegen amtliches LiDAR-DOM (LGL BW, 1 m, Genauigkeit 0,15 m).
Nutzung: python3 tools/masspruefung.py modelle/stl/martinstor_v4_1-87.stl   (STL in mm bei 1:87)
Ablauf: Modell in Meter -> fein unterteilen -> von oben rastern (1 m) -> Drehung/Verschiebung suchen -> Abweichungen je Zelle."""
import sys, numpy as np, trimesh
from scipy import ndimage as ndi
DOM="/media/oem/scan/tmp/mt_dom/mt_win.npy"; GELAENDE=277.98; N=60
stl=sys.argv[1] if len(sys.argv)>1 else "modelle/stl/martinstor_v4_1-87.stl"
ref=np.load(DOM)-GELAENDE
m=trimesh.load(stl); m.apply_scale(87/1000.0)
v,f=trimesh.remesh.subdivide_to_size(m.vertices,m.faces,max_edge=0.45,max_iter=14)
print("fein unterteilt:",len(f),"Flaechen")
def hmap(ang,dx=0.0,dy=0.0,res=1.0):
    c,s=np.cos(np.radians(ang)),np.sin(np.radians(ang))
    P=v[f].mean(1); Pz=P[:,2]
    x=c*P[:,0]-s*P[:,1]+dx; y=s*P[:,0]+c*P[:,1]+dy
    ix=np.floor(x/res+N/2).astype(int); iy=np.floor(N/2-y/res).astype(int)
    ok=(ix>=0)&(ix<N)&(iy>=0)&(iy<N); H=np.zeros((N,N)); np.maximum.at(H,(iy[ok],ix[ok]),Pz[ok]); return H
def score(H):
    core=ndi.binary_dilation(H>8,iterations=1)
    return float(np.mean(np.minimum(np.abs(H-ref)[core],20.0)))
if __name__=="__main__":
    best=(1e9,0,0,0)
    for ang in np.arange(0,180,2.0):
        for dx in np.arange(-6,6.1,1.0):
            for dy in np.arange(-6,6.1,1.0):
                sc=score(hmap(ang,dx,dy))
                if sc<best[0]: best=(sc,ang,dx,dy)
    print("grob  %.2f  Winkel %.0f dx %.1f dy %.1f"%best)
    sc0,a0,dx0,dy0=best
    for ang in np.arange(a0-3,a0+3.01,0.5):
        for dx in np.arange(dx0-1,dx0+1.01,0.25):
            for dy in np.arange(dy0-1,dy0+1.01,0.25):
                sc=score(hmap(ang,dx,dy))
                if sc<best[0]: best=(sc,ang,dx,dy)
    sc,ang,dx,dy=best; H=hmap(ang,dx,dy); print("fein  %.2f  Winkel %.1f dx %.2f dy %.2f"%best)
    core=ndi.binary_dilation(H>8,iterations=1); e=(H-ref)[core]
    print("Zellen %d  Mittel %+.2f  Median %+.2f  p10 %+.1f  p90 %+.1f m  (Modell minus Laser)"%(core.sum(),e.mean(),np.median(e),*np.percentile(e,[10,90])))
    print("Turmspitze: Laser %.2f m, Modell %.2f m"%(ref[core].max(),H.max()))
    # Hoehenverteilung der Spitzen (hoechste Zellen) vergleichen
    print("Top-10 Zellen Laser :",np.sort(ref[core])[-10:].round(1))
    print("Top-10 Zellen Modell:",np.sort(H[core])[-10:].round(1))
    np.save("/media/oem/scan/tmp/mt_dom/H_model.npy",H)

def hypsometrie(ref_arr, model_H, radius=13.0):
    """Flaeche ueber Hoehe t: unabhaengig von Drehung/Lage. Laser nur im Umkreis um die Turmspitze, zusammenhaengend."""
    pk=np.unravel_index(np.argmax(ref_arr),ref_arr.shape)
    yy,xx=np.mgrid[:N,:N]; disc=np.hypot(yy-pk[0],xx-pk[1])<=radius
    rows=[]
    for t in (10,15,20,25,30,35,40,45,50):
        lab,n=ndi.label((ref_arr>t)&disc); a_ref=(lab==lab[pk]).sum() if lab[pk] else 0
        a_mod=(model_H>t).sum(); rows.append((t,a_ref,a_mod))
    return rows

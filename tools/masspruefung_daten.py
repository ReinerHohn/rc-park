#!/usr/bin/env python3
"""masspruefung_daten.py - holt die amtlichen LiDAR-Daten (LGL BW, DOM1 + DGM1, 1 m, Genauigkeit 0,15 m) fuer das Martinstor
und legt das 60x60-m-Fenster als /media/oem/scan/tmp/mt_dom/mt_win.npy ab. Ausgabe: Geländehoehe + Turmhoehe.
Lizenz: Datenlizenz Deutschland Namensnennung 2.0 (LGL BW / opengeodata.lgl-bw.de)."""
import os, math, subprocess, zipfile, numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
D="/media/oem/scan/tmp/mt_dom"; os.makedirs(D,exist_ok=True)
LAT,LON=47.9937139,7.8489466      # Nominatim: Martinstor, Kaiser-Joseph-Strasse
def utm32(lat,lon):
    a=6378137.0; f=1/298.257222101; e2=f*(2-f); ep2=e2/(1-e2); k0=0.9996; lon0=math.radians(9.0)
    la=math.radians(lat); lo=math.radians(lon); N=a/math.sqrt(1-e2*math.sin(la)**2); T=math.tan(la)**2; C=ep2*math.cos(la)**2; A=math.cos(la)*(lo-lon0)
    M=a*((1-e2/4-3*e2**2/64-5*e2**3/256)*la-(3*e2/8+3*e2**2/32+45*e2**3/1024)*math.sin(2*la)+(15*e2**2/256+45*e2**3/1024)*math.sin(4*la)-(35*e2**3/3072)*math.sin(6*la))
    return 500000+k0*N*(A+(1-T+C)*A**3/6+(5-18*T+T*T+72*C-58*ep2)*A**5/120), k0*(M+N*math.tan(la)*(A*A/2+(5-T+9*C+4*C*C)*A**4/24+(61-58*T+T*T+600*C-330*ep2)*A**6/720))
E,N=utm32(LAT,LON); ek,nk=int(E//1000),int(N//1000); t2=f"{ek if ek%2 else ek-1}_{nk if nk%2==0 else nk-1}"; t1=f"{ek}_{nk}"
for kind in ("dom1","dgm1"):
    z=f"{D}/{kind}.zip"
    if not os.path.exists(z): subprocess.run(["curl","-s","-m","300","-o",z,f"https://opengeodata.lgl-bw.de/data/{"dom1" if kind=="dom1" else "dgm"}/{kind}_32_{t2}_2_bw.zip"],check=True)
    zipfile.ZipFile(z).extractall(D)
dom=f"{D}/dom1_32_{t2}_2_bw/dom1_32_{t1}_1_bw_2017"; a=np.array(Image.open(dom+".tif")).astype(float); a[a<-100]=np.nan
x0,y0=[float(x) for x in open(dom+".tfw")][4:6]
g=np.loadtxt(f"{D}/dgm1_32_{t2}_2_bw/dgm1_32_{t1}_1_bw_2017.xyz"); m=(abs(g[:,0]-E)<4)&(abs(g[:,1]-N)<4); gel=float(np.median(g[m,2]))
c=int(E-x0); r=int(y0-N); w=a[r-30:r+30,c-30:c+30]; np.save(f"{D}/mt_win.npy",w)
print("Martinstor UTM32 E %.0f N %.0f  Kachel %s"%(E,N,t1)); print("Gelaendehoehe %.2f m ue.NN, DOM-Maximum %.2f m -> Turmhoehe %.2f m"%(gel,np.nanmax(w),np.nanmax(w)-gel))

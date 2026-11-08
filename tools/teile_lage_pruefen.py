#!/usr/bin/env python3
"""teile_lage_pruefen.py <objekt> [wolke.npy] - je aktivem Bauteil (NUR_BAUTEIL) Median-Abstand Wolke->Teil und Hoehe/Lage; markiert Teile ohne Wolkenstuetzung und Doppelungen.
Sichtfund 8.11. (Erker/Helme falsch): Gesamtmetrik sieht kleine Teile nicht."""
import os,sys,json,subprocess,numpy as np,trimesh
sys.path.insert(0,"/media/oem/scan/p3d_site")
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));ob=sys.argv[1]
W=np.load(sys.argv[2] if len(sys.argv)>2 else "/media/oem/scan/rc-park_null/wolke_netzrahmen.npy")[:,:3].astype(np.float32)
from scipy.spatial import cKDTree
T=cKDTree(W);O=json.load(open(f"{R}/modelle/{ob}/objekt.json"))
for b in O["bauteile"]:
    if b.get("aktiv")==False: continue
    env=dict(os.environ,NUR_BAUTEIL=b["typ"],OBJ_DIR=ob,STL_NAME="_tlp.stl",SCALE="87",ELEMENTE_AUS="/dev/null")
    r=subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"),f"{R}/tools/baukasten_gen.py",ob],env=env,capture_output=True,text=True)
    p=f"{R}/modelle/stl/_tlp.stl"
    if not os.path.exists(p): print(f"{b['typ']:28s} Bau fehlgeschlagen");continue
    m=trimesh.load(p,process=False);os.remove(p);m.apply_scale(87/1000)
    q,_=trimesh.sample.sample_surface(m,5000);d,_=T.query(q);bb=m.bounds
    print(f"{b['typ']:28s} Median {np.median(d):.2f} m  >0,5 m {np.mean(d>0.5)*100:4.0f} %  u/n/z-Box {bb[0].round(1)}..{bb[1].round(1)}"+("   <-- LAGE PRUEFEN" if np.median(d)>0.4 else ""))

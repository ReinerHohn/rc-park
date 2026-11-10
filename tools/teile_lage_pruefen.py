#!/usr/bin/env python3
"""teile_lage_pruefen.py <objekt> [wolke.npy] - je aktivem Bauteil (NUR_BAUTEIL) Median-Abstand Wolke->Teil und Hoehe/Lage; markiert Teile ohne Wolkenstuetzung und Doppelungen.
Sichtfund 8.11. (Erker/Helme falsch): Gesamtmetrik sieht kleine Teile nicht."""
import os,sys,json,subprocess,numpy as np,trimesh
sys.path.insert(0,"/media/oem/scan/p3d_site")
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));ob=sys.argv[1]
O=json.load(open(f"{R}/modelle/{ob}/objekt.json"))
# Wolke: Argument, sonst dieselbe wie der Konvergenz-Kreis (objekt.json kreis.wolke). 10.11.: alte Voreinstellung wolke_netzrahmen.npy lag in einem
# anderen Rahmen -> Helm O 2,54 m statt 0,14 m, Erker 1,64 statt 0,09 m; Agenten bekamen falsche 'LAGE PRUEFEN'.
WP=sys.argv[2] if len(sys.argv)>2 else O.get("kreis",{}).get("wolke","/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy")
print("Wolke:",WP)
W=np.load(WP)[:,:3].astype(np.float32)
from scipy.spatial import cKDTree
T=cKDTree(W)
for b in O["bauteile"]:
    if b.get("aktiv")==False: continue
    env=dict(os.environ,NUR_BAUTEIL=b["typ"],OBJ_DIR=ob,STL_NAME="_tlp.stl",SCALE="87",ELEMENTE_AUS="/dev/null")
    r=subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"),f"{R}/tools/baukasten_gen.py",ob],env=env,capture_output=True,text=True)
    p=f"{R}/modelle/stl/_tlp.stl"
    if not os.path.exists(p):
        gr=[l for l in (r.stdout+r.stderr).splitlines() if l.strip()][-1:] or ["?"]
        print(f"{b['typ']:28s} Bau allein nicht moeglich: {gr[0][:110]}");continue
    m=trimesh.load(p,process=False,force="mesh");os.remove(p)
    if not isinstance(m,trimesh.Trimesh) or len(m.faces)==0:   # 10.11.: leeres Teil (z. B. Fensterreihe als reiner Ausschnitt) -> leere Szene -> KeyError 'world', Pruefung brach fuer alle Folgeteile ab
        print(f"{b['typ']:28s} LEER (Teil erzeugt allein kein Netz - reiner Ausschnitt/Abzug?) - nicht pruefbar");continue
    m.apply_scale(87/1000)
    q,_=trimesh.sample.sample_surface(m,5000);d,_=T.query(q);bb=m.bounds
    print(f"{b['typ']:28s} Median {np.median(d):.2f} m  >0,5 m {np.mean(d>0.5)*100:4.0f} %  u/n/z-Box {bb[0].round(1)}..{bb[1].round(1)}"+("   <-- LAGE PRUEFEN" if np.median(d)>0.4 else ""))

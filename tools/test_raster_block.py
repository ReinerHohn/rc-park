# Beweis 10.11.: dreiecke_rastern mit VRAM-abhaengigem Block ist bitgleich zu 1<<20 (Tiefe, Teilnummer, Weltpunkt). Aufruf: venv-seg python -I tools/test_raster_block.py 6119 c12
import sys, json, time, numpy as np, trimesh, glob, os
sys.path.insert(0, "tools"); import render_kern as RK, fehlteile_finden as FF, cv2
R0=os.getcwd(); objp="modelle/kaufhaus_grob3/objekt.json"; obj=json.load(open(objp))
mv=trimesh.load(obj["stl"], force="mesh"); mv.apply_scale(0.087)
for nr in sys.argv[1:]:
    K=json.load(open(FF.k_datei(objp,obj,R0,nr))); kk=K["kamera"]; im=cv2.imread(glob.glob(os.path.join(obj["fotos_dir"], nr+"_*"))[0]); H,W=im.shape[:2]
    R,t,f,_,_=FF.kamera_laden(K,obj,nr,R0,W,H); cx,cy=float(kk.get("cx",W/2)),float(kk.get("cy",H/2))
    import teil_fotoform as TF; tr=TF.rahmen(obj["stl"],obj,kk); m=mv.copy(); m.apply_translation(tr)
    r={}
    for b in (1<<20, None):
        t0=time.time(); r[b]=RK.dreiecke_rastern(m,R,t,f,cx,cy,W,H,block=b); print(nr, b, f"{time.time()-t0:.1f} s")
    a,c=r[1<<20],r[None]; print(nr, "gleich:", np.array_equal(a[0],c[0]), np.array_equal(a[1],c[1]), np.array_equal(a[2],c[2]), f"{W}x{H}")

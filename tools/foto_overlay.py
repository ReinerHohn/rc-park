#!/usr/bin/env python3
"""foto_overlay.py - scharfe STL-Kanten (Winkel > 25 Grad) mit der kalibrierten Kamera K-<nr>.json (rvec,t,f_px,cx,cy; R*X+t wie foto_kalibrieren.py) ueber das echte Foto legen (Register BW: Sichtpruefung Modell gegen Foto, unabhaengig von Wolkenfehlern).
  /media/oem/scan/venv-seg/bin/python -I tools/foto_overlay.py <fotonr> <aus.jpg> [--objekt modelle/<objekt>] [--stl datei.stl]   (Fotos daten/martinstor/fotos/; Methode: PIPELINE_H0.md Abschnitt 8)"""
import sys, json, glob, cv2, numpy as np, trimesh
a=sys.argv[1:]; objd="modelle/martinstor"; stl="modelle/stl/martinstor_v4_1-87.stl"
for fl in ("--objekt","--stl"):
    if fl in a: i=a.index(fl); (objd:=a[i+1]) if fl=="--objekt" else (stl:=a[i+1]); a=a[:i]+a[i+2:]
nr,out=a[0],a[1]
Kd=json.load(open(f"{objd}/messprotokoll/K-{nr}.json")); cam=Kd["kamera"] if "kamera" in Kd else Kd
import os; _op=os.path.join(objd,"objekt.json"); _obj=json.load(open(_op)) if os.path.exists(_op) else {}            # GENERISCH (2026-11-04): Fotoordner + Massstab aus objekt.json (vorher fest Martinstor)
_fp=glob.glob(f"{_obj.get('fotos_dir','daten/martinstor/fotos')}/{nr}_*")
if not _fp: sys.exit(f"Foto {nr} nicht gefunden")
im=cv2.imread(_fp[0]); H,W=im.shape[:2]
f=cam["f_px"]; cx=cam.get("cx",W/2); cy=cam.get("cy",H/2); rvec=np.array(cam["rvec"],float); t=np.array(cam["t"],float)
m=trimesh.load(stl); m.apply_scale(_obj.get("stl_massstab",87)/1000.0); m.apply_translation(np.array(cam.get("rahmen_verschiebung",[0,0,0]),float))   # Werkzeugrahmen der Kamera (Buendelkameras: T_)
R,_=cv2.Rodrigues(rvec)
def proj(X):
    Xc=X@R.T+t; z=Xc[:,2]; return np.c_[f*Xc[:,0]/z+cx, f*Xc[:,1]/z+cy], z
V=np.asarray(m.vertices); uv,z=proj(V)
ed=m.edges_unique; fa=m.face_adjacency; ang=m.face_adjacency_angles
# scharfe Kanten (Winkel > 25 Grad) + Silhouette-aehnliche Kanten
sharp=m.face_adjacency_edges[ang>np.radians(25)]
ov=im.copy()
for a,b in sharp:
    if z[a]>1 and z[b]>1:
        p=tuple(np.round(uv[a]).astype(int)); q=tuple(np.round(uv[b]).astype(int))
        cv2.line(ov,p,q,(0,0,255),1,cv2.LINE_AA)
res=cv2.addWeighted(ov,0.9,im,0.1,0)
cv2.imwrite(out,cv2.resize(res,None,fx=1400/H,fy=1400/H,interpolation=cv2.INTER_AREA))
print(nr,W,H,"f",round(f),"Kante/Vertex",len(sharp),len(V))

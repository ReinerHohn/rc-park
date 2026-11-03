#!/usr/bin/env python3
"""breite_quellenvergleich.py - Helmbreite quer (E-W) je Hoehe aus DERSELBEN Silhouetten-Schaetzung (hybrid_abgleich.silhouette_quer) fuer Strassenwolke, Generator-STL,
Drohnenwolke gesamt und je Clip, dazu Bootstrap ueber Clips (Register BU). Gleicher Schaetzer fuer alle Quellen: Vergleiche mit anderen Breitenmassen (Frontschicht) sind Mass-Unterschiede, keine Widersprueche.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/breite_quellenvergleich.py modelle/<objekt>/objekt.json <video_sfm/d1> --stl modelle/stl/<objekt>_v4_1-87.stl [--z 45.2 47.9 50.6 53.2]
Hinweis: p2-p98 der y-Werte ist bei verrauschten Wolken nach aussen verzerrt (mehr Rauschen = breiter); Clip-Streuung zeigt die Unsicherheit der Drohne."""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import hybrid_abgleich as h
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("drohne"); ap.add_argument("--stl", required=True); ap.add_argument("--z", nargs="+", type=float, default=[45.2, 47.9, 50.6, 53.2]); ap.add_argument("--boot", type=int, default=200); a = ap.parse_args()
R = os.path.dirname(os.path.abspath(a.objekt)) + "/"; d = a.drohne.rstrip("/") + "/"
G=json.load(open(R+'profile_generator.json'))
V=np.load(d+'dicht_korrigiert.npy').astype(float); bad=np.load(d+'dicht_verworfen.npy'); A=np.load(d+'punkt_clips.npy').astype(float); cn=json.load(open(d+'punkt_clips.json'))
V+=np.array(json.load(open(R+'audit/video_versatz.json')).get('verschiebung_m') or [0,0,0])
fr=A/np.maximum(A.sum(1,keepdims=True),1); dom=fr.argmax(1); rein=fr.max(1)>=0.7
ok=~bad & ~h.tuerm_maske(V,G)
S_=np.load(R+'sfm/dicht_nord_entzerrt_ohnevideo.npy').astype(float); S_=S_[~h.tuerm_maske(S_,G)]
mesh=h.mesh_punkte(a.stl,87/1000.0); mesh=mesh[~h.tuerm_maske(mesh,G)]
zs=a.z
def w(P,z): r=h.silhouette_quer(P,z,minpts=60); return None if r is None else round(r[0],2)
print('z        ', zs)
print('Strasse  ', [w(S_,z) for z in zs]); print('Generator', [w(mesh,z) for z in zs]); print('Drohne ges',[w(V[ok],z) for z in zs])
for i,c in enumerate(cn): m=ok&(dom==i)&rein; print('Clip',c[:6],m.sum(),[w(V[m],z) for z in zs])
rng=np.random.default_rng(1); res=[]
for b in range(a.boot):
    pick=rng.integers(0,len(cn),len(cn)); m=np.zeros(len(V),bool)
    for i in pick: m|=(dom==i)&rein
    m&=ok; res.append([w(V[m],z) or np.nan for z in zs])
res=np.array(res,float); print('Bootstrap Clips (Median, p5-p95):',[(round(float(np.nanmedian(res[:,i])),2),round(float(np.nanpercentile(res[:,i],5)),2),round(float(np.nanpercentile(res[:,i],95)),2)) for i in range(len(zs))])

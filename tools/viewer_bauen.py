#!/usr/bin/env python3
"""viewer_bauen.py — H0-Modelle (STL) in EINE selbstenthaltene 3D-HTML packen (three.js, Drehen/Zoomen/Gitter/H0-Figur).

Nutzung:  python tools/viewer_bauen.py [ausgabe.html]      (Standard: modelle/h0/viewer.html)
Modelle stehen unten als M.append(entry(...)). Binaer-STL wird base64 in die Seite eingebettet (Seite < 16 MB halten:
Modelle mit > ~100k Flaechen vorher mit --solid/Vereinfachung verkleinern). three.js kommt per jsDelivr (r128).
Die Seite wird danach mit dem Artifact-Tool veroeffentlicht oder lokal im Browser geoeffnet.
"""
import json, base64, io, sys, os, trimesh
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))+"/"; S=os.path.dirname(os.path.abspath(__file__))
def stl_bytes(m): return trimesh.exchange.stl.export_stl(m)
def entry(name, tag, path, note, parts, scale=1.0, status=("ok",""), maxfaces=None):
    m=trimesh.load(R+path); 
    if scale!=1.0: m.apply_scale(scale)
    m.apply_translation([0,0,-m.bounds[0,2]])
    return dict(name=name, tag=tag, faces=int(len(m.faces)), watertight=bool(m.is_watertight), parts=parts,
                status=status[0], status_text=status[1], note=note, stl=base64.b64encode(stl_bytes(m)).decode())
M=[]
M.append(entry("Martinstor v3","Torturm · 45,3 m · Favorit","modelle/h0/martinstor_v3_h0.stl",
  "Nach Fotos gebaut (Lernjournal): nach oben verjuengter Rumpf mit Bruchstein-Sockel und Keilsteinbogen, gezahnte Eckquader, Uhr mit Giebel, Zinnenkranz, Kragdach, abgesetzter Glockenstock mit Schallarkaden, Kupferdach mit Stehfalzen, vier achteckige Erkertuermchen mit X-Bruestung und Arkade, Dachreiter. Hoehe 45,3 m nach LOD2 und Scan-Verhaeltnis; Textquellen nennen 60 bis 66 m.",3))
M.append(entry("Martinstor v2","Vorgaenger · 54 m","modelle/h0/martinstor_detail_h0.stl",
  "Fruehere Fassung nach OSM-Massen: richtige Silhouette, aber falsche Proportionen (zu hohes Dach, Gauben, die es nicht gibt, kein Glockenstock, Rumpf nicht verjuengt).",3,status=("warn","ueberholt")))
M.append(entry("Martinstor Scan-Hülle","Foto-Scan · nur Proportionen","modelle/scan_koerper/martinstor_scan.stl",
  "Körper aus dem Video-Scan (653 Frames), Höhe per Annahme auf 45,9 m gesetzt. Zeigt Sockel und Helm als Hülle, aber keinen Torbogen. Der untere Teil unter etwa 18 m ist im Scan lückenhaft und wurde durchgezogen. Nicht als Druckmodell gedacht.",1,scale=45.9/44.5*1000/87,status=("warn","Hülle, kein Detail")))
M.append(entry("Martinstor einfach","Generator v2 · 45,9 m","modelle/h0/martinstor_h0.stl",
  "Erster parametrischer Entwurf aus LOD2-Daten: quadratischer Schaft mit Torbogen und Spitzhelm. Wasserdicht, aber ohne Detail und mit dem Foto verglichen deutlich schlechter als das Detailmodell.",3,status=("warn","grob")))
M.append(entry("Ravenna-Viadukt","Brücke · Generator","modelle/h0/ravenna_h0.stl",
  "Eisenbahnviadukt über die Ravennaschlucht aus dem Brückengenerator. Wasserdicht, in 40 Teile für den Druck geteilt, 6 % der Wand sind dünner als 0,8 mm und müssen vor dem Druck geprüft werden.",40,status=("warn","dünne Stellen")))
tpl=open(S+"/viewer_vorlage.html").read()
out=sys.argv[1] if len(sys.argv)>1 else R+"modelle/h0/viewer.html"
open(out,"w").write(tpl.replace("/*MODELS*/[]",json.dumps(M)))
print(len(M),"Modelle", os.path.getsize(out)//1024,"KB ->",out)

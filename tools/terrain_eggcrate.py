#!/usr/bin/env python3
"""terrain_eggcrate.py — DEM -> STECKBARES Laser-Gerüst (Egg-Crate / Spanten).

Zwei Sätze senkrechter Rippen, deren Oberkante dem Gelände folgt. Sie greifen über
Halb-Schlitze ineinander (X-Rippen Schlitz von OBEN bis Mitte, Y-Rippen von UNTEN bis
Mitte) -> selbsttragendes Kreuzgitter, kein Kleber. Haut (Gips/3D-Druck) kommt oben
drauf. Export: pro Rippe ein SVG (Kontur mit Schlitzen) + optional GRBL-G-Code.

  python3 tools/terrain_eggcrate.py --nx 6 --ny 6 --thickness 3 --vscale 0.3 --out /tmp/crate
"""
import argparse, os, sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from laser_relief_kit import glyph_strokes, svg_write, gcode_write, contour_polys, decimate, pip

BIG = "daten/hoellental/hirsch_big.npy"; MM = 6.25


def write_html(fn, scene, engrave_lines=None):
    """Drehbarer three.js-Viewer der zusammengesteckten Rippen (GLB eingebettet).
    engrave_lines = Liste von Nx3-Polylinien (Gravur X/Y+Nr. auf der Holzfläche)."""
    import base64, json
    b64 = base64.b64encode(scene.export(file_type="glb")).decode()
    seg = []                                       # Gravur -> Segment-Paare (flach x,y,z,...)
    for pl in (engrave_lines or []):
        pl = np.asarray(pl, float)
        for i in range(len(pl)-1):
            seg += [*pl[i].tolist(), *pl[i+1].tolist()]
    eng_json = json.dumps([round(v, 2) for v in seg])
    html = '''<!doctype html><html><head><meta charset=utf8><title>Egg-Crate 3D</title>
<style>body{margin:0;background:#dde6ef;font-family:sans-serif}#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:8px 12px;border-radius:8px;font-size:13px}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body><div id=i><b>Egg-Crate — zusammengesteckt</b><br><span style=color:#8cf>Maus drehen · Rad zoom</span></div>
<div id=i2 style="position:fixed;bottom:10px;left:10px;background:#000a;color:#fff;padding:6px 10px;border-radius:8px;font-size:12px">Jede Farbe = ein Puzzle-Stück · dunkle Linien = Laser-Gravur (X/Y + Nr.) auf dem Holz</div>
<script type=module>
import*as THREE from'three';import{OrbitControls}from'three/addons/controls/OrbitControls.js';import{GLTFLoader}from'three/addons/loaders/GLTFLoader.js';
const sc=new THREE.Scene();sc.background=new THREE.Color(0xdde6ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.75));sc.add(new THREE.HemisphereLight(0xffffff,0x556,1.0));
const d1=new THREE.DirectionalLight(0xffffff,1.2);d1.position.set(200,-300,500);sc.add(d1);
const mat=new THREE.MeshStandardMaterial({vertexColors:true,roughness:1,side:THREE.DoubleSide,flatShading:true});
const ENG=%ENG%;
new GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{const m=g.scene;m.traverse(o=>{if(o.isMesh)o.material=mat;});
 const bx=new THREE.Box3().setFromObject(m),c=bx.getCenter(new THREE.Vector3()),s=bx.getSize(new THREE.Vector3());
 m.position.sub(c);sc.add(m);
 if(ENG.length){const gg=new THREE.BufferGeometry();gg.setAttribute('position',new THREE.Float32BufferAttribute(ENG,3));
  const ls=new THREE.LineSegments(gg,new THREE.LineBasicMaterial({color:0x1a0f06}));m.add(ls);}
 const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.9,-d*1.2,d*0.8);cam.lookAt(0,0,0);ct.update();});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function x(){requestAnimationFrame(x);ct.update();rn.render(sc,cam)})();
</script></body></html>'''.replace("%B64%", b64).replace("%ENG%", eng_json)
    open(fn, "w").write(html)


def write_assembly_html(fn, named_pieces, engrave_lines=None, relief_mesh=None, extra_meshes=None, overlay_edges=None):
    """ZUSAMMENBAUANLEITUNG: Suchleiste -> Teil leuchtet rot im 3D (wo es hinkommt), Rest blass.
    + Gravur-Nummern auf dem Holz + ein-/ausblendbares RELIEF als Kontext.
    named_pieces=[(label,mesh,is_x)], engrave_lines=Nx3-Polylinien, relief_mesh=Trimesh (optional)."""
    import base64, json, trimesh as _tm
    sc = _tm.Scene()
    for (label, mesh, is_x) in named_pieces:
        sc.add_geometry(mesh, geom_name=label, node_name=label)
    if relief_mesh is not None:
        relief_mesh.visual.vertex_colors = [200, 180, 140, 255]
        sc.add_geometry(relief_mesh, geom_name="RELIEF", node_name="RELIEF")
    for (lbl, mesh, rgba) in (extra_meshes or []):                 # Einhäng-Platten als eigene Ebene
        try:
            mesh.visual.vertex_colors = rgba
            sc.add_geometry(mesh, geom_name=lbl, node_name=lbl)
        except Exception:
            pass
    b64 = base64.b64encode(sc.export(file_type="glb")).decode()
    seg = []
    for pl in (engrave_lines or []):
        pl = np.asarray(pl, float)
        for i in range(len(pl)-1): seg += [*pl[i].tolist(), *pl[i+1].tolist()]
    eng_json = json.dumps([round(v, 2) for v in seg])
    eseg = []                                                      # Geo-Kanten-Overlay (crisp LineSegments, keine Spline-Rundung)
    for pl in (overlay_edges or []):
        pl = np.asarray(pl, float)
        for i in range(len(pl)-1): eseg += [*pl[i].tolist(), *pl[i+1].tolist()]
    edg_json = json.dumps([round(v, 2) for v in eseg])
    HTML = '''<!doctype html><html><head><meta charset=utf8><title>Zusammenbauanleitung</title>
<style>body{margin:0;background:#dde6ef;font-family:sans-serif}
#bar{position:fixed;top:0;left:0;right:0;background:#111e;color:#fff;padding:10px 12px;z-index:10;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
#bar input[type=text]{font-size:16px;padding:6px 8px;width:140px;border-radius:4px}
#bar button{font-size:13px;padding:7px 11px;margin:0;border-radius:4px;border:1px solid #444;cursor:pointer;background:#222;color:#fff;transition:0.2s}
#bar button:hover{background:#333}button[title]{position:relative}
.sep{width:1px;height:20px;background:#444;margin:0 4px}
#info{margin-left:auto;font-size:14px;font-weight:bold;color:#8f8}
#tip{position:fixed;bottom:8px;left:8px;right:8px;background:#000b;color:#fff;padding:8px 12px;border-radius:6px;font-size:12px;line-height:1.4;max-width:400px}</style>
<script src="https://unpkg.com/three@0.137.5/build/three.min.js"></script>
<script src="https://unpkg.com/three@0.137.5/examples/js/controls/OrbitControls.js"></script>
<script src="https://unpkg.com/three@0.137.5/examples/js/loaders/GLTFLoader.js"></script>
</head><body>
<div id=bar>
<div style="display:flex;gap:8px;align-items:center">
  <label style="margin:0;font-weight:bold">🔎 Teil:</label>
  <input id=q placeholder="z.B. X0a, Y5, K3" autofocus>
  <button onclick=find() title="Teil-Nr suchen">Finden</button>
  <button onclick=clr() title="Alle Teile anzeigen">Alle</button>
</div>
<div class=sep></div>
<div style="display:flex;gap:8px">
  <button onclick=tRelief() title="Gelände anzeigen/verstecken">🏔️ Relief</button>
  <label style="margin:0;display:flex;align-items:center;gap:6px">Deckkraft: <input id=ropac type=range min=0 max=100 value=50 style="width:80px" oninput=setRopac(this.value) title="Relief durchsichtig machen"></label>
</div>
<div class=sep></div>
<div style="display:flex;gap:8px">
  <button onclick=tTunnel() style="background:#d42;border-color:#a30" title="Tunnel-Lichträume zeigen">🚇 Tunnel</button>
  <button onclick=tFlaechen() style="background:#0047b2;border-color:#0033a0" title="Alle Rippen blau hervorheben">📐 Rippen</button>
  <button onclick="filterType('spanten')" id=btnSpanten title="Nur Spanten (X/Y Träger-Rippen)" style="background:#4a4">🔲 Spanten</button>
  <button onclick="filterType('kanten')" id=btnKanten title="Nur Kanten-Lineale (K/D scharfe Grate)" style="background:#f92">🔷 Kanten</button>
  <button onclick="filterType('')" id=btnAlle title="Alle Rippen + Kanten-Lineale">Alle Typen</button>
  <button onclick=tNum() title="Teil-Nummern zeigen/verstecken">Nummern</button>
</div>
<div class=sep></div>
<div style="display:flex;gap:8px">
  <button onclick=tProg() title="Baustand-Modus: Teil anklicken = ✓ geschnitten (gespeichert)" style="background:#27a">🧩 Baustand</button>
  <button onclick="filterDone('todo')" title="NUR die noch nicht geschnittenen Teile zeigen" style="background:#a53">📋 Nur offen</button>
  <button onclick="filterDone('done')" title="NUR die schon geschnittenen Teile zeigen" style="background:#2a7">✓ Nur fertig</button>
  <button onclick="filterDone('')" title="Alle Teile wieder zeigen">Alle zeigen</button>
  <button onclick=resetProg() title="Baustand-Markierungen löschen" style="background:#a33">✕ Reset</button>
</div>
<span id=pinfo style="margin-left:auto;color:#5f5"></span><span id=info></span>
</div>
<div id=tip><b>Bedienung:</b> Teil eintippen (z.B. Y10) oder anklicken → ROT = wo es hinkommt. Zwei Teile → rot+blau + grüne Kugel = Kreuzung. <b>Baustand:</b> 🧩 anklicken, dann jedes geschnittene Teil anklicken (✓, gespeichert) → mit „📋 Nur offen" siehst du, was noch fehlt. Maus: drehen, Rad: zoom</div>
<script>
const sc=new THREE.Scene();sc.background=new THREE.Color(0xdde6ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.8));sc.add(new THREE.HemisphereLight(0xffffff,0x556,1.0));
const d1=new THREE.DirectionalLight(0xffffff,1.1);d1.position.set(200,-300,500);sc.add(d1);
let meshes=[],extras=[],tunnels=[],flaechen=[],relief=null,nums=null,edges=null,prog=false;const DONE=new Set();let KEY='zbdone';const ENG=%ENG%;const EDG=%EDG%;const RAY=new THREE.Raycaster(),M=new THREE.Vector2();
new THREE.GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{
 const root=g.scene,bx=new THREE.Box3().setFromObject(root),c=bx.getCenter(new THREE.Vector3()),s=bx.getSize(new THREE.Vector3());
 root.position.sub(c);sc.add(root);
 root.traverse(o=>{if(o.isMesh){
  if((o.name||"")==="RELIEF"){o.material=new THREE.MeshStandardMaterial({color:0x6d5c3e,roughness:1,side:THREE.DoubleSide,transparent:true,opacity:0.5,flatShading:true});o.visible=true;relief=o;return;}
  if(/^TUNNEL/.test(o.name||"")){o.material=new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,depthTest:false,transparent:true,opacity:0.95});o.renderOrder=999;o.visible=true;tunnels.push(o);return;}
  if(/^FLAECHE/.test(o.name||"")){o.material=new THREE.MeshStandardMaterial({vertexColors:true,side:THREE.DoubleSide,roughness:0.85,transparent:true,opacity:0.92,flatShading:true});o.visible=true;flaechen.push(o);return;}
  if(/^KANTE/.test(o.name||"")){o.material=new THREE.MeshBasicMaterial({color:0xff1493,side:THREE.DoubleSide,depthTest:false});o.renderOrder=1300;o.visible=true;flaechen.push(o);return;}
  if(/^PLATTE/.test(o.name||"")){o.material=new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,transparent:true,opacity:0.9});o.visible=false;extras.push(o);return;}
  const hue=((meshes.length*137.508)%360)/360,col=new THREE.Color().setHSL(hue,0.58,0.55);
  o.material=new THREE.MeshStandardMaterial({color:col,roughness:1,side:THREE.DoubleSide,flatShading:true,transparent:true,opacity:1});
  o.userData.base=col.getHex();meshes.push(o);}});
 {let s=meshes.map(o=>(o.name||'').toUpperCase()).sort().join('|'),h=0;for(let i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))|0;KEY='zbdone_'+(h>>>0);try{JSON.parse(localStorage.getItem(KEY)||'[]').forEach(n=>DONE.add(n))}catch(e){}updProgInfo();apply(document.getElementById('q').value);}
 if(ENG.length){const gg=new THREE.BufferGeometry();gg.setAttribute('position',new THREE.Float32BufferAttribute(ENG,3));
  nums=new THREE.LineSegments(gg,new THREE.LineBasicMaterial({color:0x1a0f06}));root.add(nums);}
 if(EDG.length){const eg=new THREE.BufferGeometry();eg.setAttribute('position',new THREE.Float32BufferAttribute(EDG,3));
  edges=new THREE.LineSegments(eg,new THREE.LineBasicMaterial({color:0xff2a2a,depthTest:false,transparent:true}));edges.renderOrder=1000;edges.visible=true;root.add(edges);}
 const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.9,-d*1.2,d*0.8);cam.lookAt(0,0,0);ct.update();});
let marker=null;const SEL=[];
function clrMark(){if(marker){sc.remove(marker);marker=null;}}
function apply(q){q=(q||"").toUpperCase().trim();const toks=q.split(/ +/).filter(x=>x);clrMark();
 const cols=[0xff2020,0x2068ff];const grp=[[],[]];let hit=[];
 meshes.forEach(o=>{const nm=(o.name||"").toUpperCase();const rid=(nm.match(/^[XY]\d+/)||[nm])[0];
  if(toks.length===0){o.material.color.setHex(o.userData.base);o.material.emissive.setHex(0);o.material.opacity=(prog&&!DONE.has(nm))?0.12:1;return;}
  let gi=-1;for(let t=0;t<Math.min(2,toks.length);t++){const tk=toks[t];if(tk&&(rid===tk||nm===tk))gi=t;}
  if(gi>=0){o.material.color.setHex(cols[gi]);o.material.emissive.setHex(gi?0x11244d:0x661111);o.material.opacity=1;grp[gi].push(o);hit.push(o.name);}
  else{o.material.color.setHex(0x999999);o.material.emissive.setHex(0);o.material.opacity=0.06;}});
 if(toks.length>=2&&grp[0].length&&grp[1].length){
  const bA=new THREE.Box3();grp[0].forEach(o=>bA.expandByObject(o));
  const bB=new THREE.Box3();grp[1].forEach(o=>bB.expandByObject(o));
  const ix=Math.max(bA.min.x,bB.min.x),ax=Math.min(bA.max.x,bB.max.x);
  const iy=Math.max(bA.min.y,bB.min.y),ay=Math.min(bA.max.y,bB.max.y);
  const iz=Math.max(bA.min.z,bB.min.z),az=Math.min(bA.max.z,bB.max.z);
  if(ix<=ax&&iy<=ay){const r=Math.max(6,Math.min(ax-ix,ay-iy)+5);
   marker=new THREE.Mesh(new THREE.SphereGeometry(r,20,20),new THREE.MeshBasicMaterial({color:0x00ff66,transparent:true,opacity:0.55,depthTest:false}));
   marker.position.set((ix+ax)/2,(iy+ay)/2,(iz+az)/2);marker.renderOrder=999;sc.add(marker);}}
 const inf=document.getElementById("info");
 if(toks.length>=2)inf.textContent=(grp[0].length&&grp[1].length)?("🔗 "+toks[0]+" × "+toks[1]+" — Verbindung GRÜN markiert"):("eins von „"+toks.join(" / ")+"“ nicht gefunden");
 else inf.textContent=toks.length?(hit.length?("→ "+hit.slice(0,6).join(", ")+(hit.length>6?"…":"")):("„"+q+"“ nicht gefunden")):"";}
window.find=()=>apply(document.getElementById("q").value);
window.clr=()=>{SEL.length=0;document.getElementById("q").value="";apply("");};
window.tRelief=()=>{if(relief)relief.visible=!relief.visible;};
window.tPlatten=()=>{extras.forEach(o=>o.visible=!o.visible);};
window.tTunnel=()=>{tunnels.forEach(o=>o.visible=!o.visible);};
window.setRopac=v=>{if(relief){const o=v/100;relief.material.opacity=o;relief.material.transparent=o<1;relief.visible=o>0;}};
window.tNum=()=>{if(nums)nums.visible=!nums.visible;};
window.tEdges=()=>{if(edges)edges.visible=!edges.visible;};
window.tFlaechen=()=>{flaechen.forEach(o=>o.visible=!o.visible);if(edges)edges.visible=!edges.visible;};
window.filterDone=mode=>{   // Baustand-FILTER: 'todo'=nur offene, 'done'=nur fertige, ''=alle
  meshes.forEach(o=>{const nm=(o.name||'').toUpperCase();
    o.visible = mode==='todo' ? !DONE.has(nm) : mode==='done' ? DONE.has(nm) : true;});
  const el=document.getElementById('pinfo');
  if(el)el.textContent = mode==='todo' ? ('📋 '+(meshes.length-DONE.size)+' offen (noch schneiden)')
                       : mode==='done' ? ('✓ '+DONE.size+' geschnitten') : (prog?('🧩 Baustand AN · '+DONE.size+'/'+meshes.length+' fertig'):'');
};
window.filterType=type=>{
  const isSpante=o=>(o.name||'').match(/^[XY]\d/);
  const isKante=o=>(o.name||'').match(/^[KD]\d/);
  if(type==='spanten'){meshes.forEach(o=>o.visible=isSpante(o));flaechen.forEach(o=>o.visible=isKante(o));}
  else if(type==='kanten'){meshes.forEach(o=>o.visible=isKante(o));flaechen.forEach(o=>o.visible=isKante(o));}
  else{meshes.forEach(o=>o.visible=true);flaechen.forEach(o=>o.visible=true);}
  if(edges)edges.visible=type==='kanten';
};
function saveProg(){try{localStorage.setItem(KEY,JSON.stringify([...DONE]))}catch(e){}}
function updProgInfo(){const el=document.getElementById('pinfo');if(el)el.textContent=prog?('🧩 Baustand AN · '+DONE.size+'/'+meshes.length+' fertig'):'';}
window.tProg=()=>{prog=!prog;SEL.length=0;document.getElementById('q').value='';apply('');updProgInfo();};
window.resetProg=()=>{DONE.clear();saveProg();updProgInfo();apply(document.getElementById('q').value);};
document.getElementById("q").addEventListener("input",e=>apply(e.target.value));
addEventListener("click",e=>{if(e.target.tagName==="INPUT"||e.target.tagName==="BUTTON")return;
 M.x=(e.clientX/innerWidth)*2-1;M.y=-(e.clientY/innerHeight)*2+1;RAY.setFromCamera(M,cam);
 const h=RAY.intersectObjects(meshes,false);if(h.length){const nm=(h[0].object.name||"").toUpperCase();
  if(prog){if(DONE.has(nm))DONE.delete(nm);else DONE.add(nm);saveProg();updProgInfo();apply(document.getElementById("q").value);return;}
  const i=SEL.indexOf(nm);if(i>=0)SEL.splice(i,1);else{SEL.push(nm);if(SEL.length>2)SEL.shift();}
  document.getElementById("q").value=SEL.join(" ");apply(SEL.join(" "));}});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function x(){requestAnimationFrame(x);ct.update();rn.render(sc,cam)})();
</script></body></html>'''.replace("%B64%", b64).replace("%ENG%", eng_json).replace("%EDG%", edg_json)
    open(fn, "w").write(HTML)


def rib(L, hs, cross, slotw, from_top, bs=None, flare=0.4):
    """Rippen-Polygon. L=Länge, hs(s)->Oberkante, bs(s)->Unterkante (None=0=bis Boden),
    cross=[(pos,hmid)] Kreuzungs-Schlitze, Schlitz von oben (from_top) oder unten.
    flare=Einführtrichter am Schlitzmund (mm je Seite): Mund breiter als slotw, verjüngt
    sich nach ~1mm auf slotw -> Rippe gleitet rein, Griff bleibt slotw. KEINE Kantenpunkte
    mehr im Mund (verhindert den Rückwärts-Zacken/Verengung, der den Zusammenbau blockiert)."""
    if bs is None: bs = lambda s: 0.0
    S = np.arange(0, L + 0.5, 1.0)
    pts = [(0.0, bs(0.0))]
    half = slotw/2 + max(0.0, flare)                 # Mund-Halbbreite (mit Trichter)
    def _inside(x):                                  # x liegt im Schlitzmund eines Kreuzes?
        return any(pos - half < x < pos + half for (pos, _h) in cross)
    # --- Unterkante links->rechts (Schlitze nach OBEN wenn not from_top) ---
    if from_top:
        for s in S[1:]:
            pts.append((float(s), bs(float(s))))
    else:
        crs = sorted(cross); emit = set()
        for s in S[1:]:
            su = float(s)
            for (pos, hmid) in crs:
                if (pos, hmid) not in emit and su >= pos - half:   # linken Mund erreicht
                    eL = bs(pos - half); eR = bs(pos + half)
                    ch = min(1.2, max(0.0, (hmid - bs(pos)) * 0.4))
                    pts += [(pos - half, eL), (pos - slotw/2, eL + ch),
                            (pos - slotw/2, hmid), (pos + slotw/2, hmid),
                            (pos + slotw/2, eR + ch), (pos + half, eR)]
                    emit.add((pos, hmid))
            if not _inside(su): pts.append((su, bs(su)))
    if pts[-1][0] < L - 1e-6: pts.append((L, bs(L)))
    # --- rechte Kante hoch ---
    pts.append((L, hs(L)))
    # --- Oberkante rechts->links (Schlitze nach UNTEN wenn from_top) ---
    if from_top:
        crs = sorted(cross, reverse=True); emit = set()
        for s in S[::-1]:
            su = float(s)
            for (pos, hmid) in crs:
                if (pos, hmid) not in emit and su <= pos + half:   # rechten Mund erreicht
                    eR = hs(pos + half); eL = hs(pos - half)
                    ch = min(1.2, max(0.0, (hs(pos) - hmid) * 0.4))
                    pts += [(pos + half, eR), (pos + slotw/2, eR - ch),
                            (pos + slotw/2, hmid), (pos - slotw/2, hmid),
                            (pos - slotw/2, eL - ch), (pos - half, eL)]
                    emit.add((pos, hmid))
            if not _inside(su): pts.append((su, hs(su)))
    else:
        for s in S[::-1]:
            pts.append((float(s), hs(float(s))))
    pts.append((0.0, bs(0.0)))
    return pts


def adaptive_pos(detail, n, lo, hi, cell, min_gap, max_gap=None):
    """Rippen-Positionen (mm), DICHTE folgt dem Detail — KEINE feste Anzahl.
    Scharfe Features (Hirsch-Sporn, Steilkante) bekommen AUTOMATISCH mehr Rippen, bis
    hinunter zu min_gap; lange flache Strecken nur bis max_gap auseinander.
    n = Auflösungs-Regler (Detail-Budget pro Intervall), nicht die feste Rippenzahl."""
    d = np.clip(np.asarray(detail, float), 0, None)
    d = d + d.max() * 0.04 + 1e-9                 # Boden: flache Zonen nur bis max_gap, nicht unendlich
    L = len(d)
    xs = (np.arange(L) + 0.5) * cell              # Zell-Mitten in mm
    budget = float(d.sum()) / max(1, n)           # Ziel-Krümmung zwischen zwei Rippen
    if max_gap is None: max_gap = 2.2 * (hi - lo) / max(1, n - 1)
    pos = []; acc = 0.0; last = None
    for i in range(L):
        x = xs[i]
        if x < lo:  acc += d[i]; continue         # vor dem Fenster Detail schon sammeln
        if x > hi:  break
        acc += d[i]
        if last is None:                          # erste Rippe am linken Rand
            pos.append(float(x)); last = x; acc = 0.0; continue
        gap = x - last
        if gap < min_gap: continue                # zu nah -> warten (verhindert Überlappung)
        if acc >= budget or gap >= max_gap:       # genug Detail gesammelt ODER zu weit weg
            pos.append(float(x)); last = x; acc = 0.0
    if not pos: return np.array([(lo + hi) / 2])
    if pos[0] - lo > min_gap: pos.insert(0, float(lo))     # Ränder absichern
    if hi - pos[-1] > min_gap: pos.append(float(hi))
    return np.array(sorted({round(p, 2) for p in pos}))


def _edge_peaks(Hf, cell, axis, lo, hi, min_gap, pct):
    """Positionen (mm) starker BRUCHKANTEN entlang einer Achse: wo das Gelände einen
    scharfen Gradient-Grat hat (gerade Man-made-Kanten — Einschnitt-Oberkante, Portal-
    Stirn, Felssporn-Grat). Projektion per MAX über die Gegenachse, damit eine KURZE
    scharfe Kante nicht im Mittel untergeht (gleiche Philosophie wie der 1.0*Max-Term
    unten). Rückgabe: Positionen nach Stärke absteigend, mind. min_gap auseinander."""
    from scipy.ndimage import gaussian_filter
    Hs = gaussian_filter(Hf, 1.0)
    gy, gx = np.gradient(Hs)
    G = np.hypot(gx, gy)
    prof = G.max(axis=0) if axis == "x" else G.max(axis=1)   # x: vertikale Kanten -> Profil über Spalten
    thr = np.percentile(prof, pct)
    cand = []
    for i in range(1, len(prof) - 1):
        if prof[i] >= thr and prof[i] >= prof[i-1] and prof[i] >= prof[i+1]:
            x = (i + 0.5) * cell
            if lo <= x <= hi:
                cand.append((x, float(prof[i])))
    cand.sort(key=lambda t: -t[1])                           # stärkste Kante zuerst
    picked = []
    for x, _s in cand:
        if all(abs(x - p) >= min_gap for p in picked):
            picked.append(x)
    return picked


def _snap_to_edges(pos, edges, min_gap):
    """Rippen auf Bruchkanten einrasten: die nächste vorhandene Rippe innerhalb min_gap
    EXAKT auf die Kante ziehen; sonst (Platz frei) eine neue Rippe auf der Kante einfügen.
    Danach min_gap durchsetzen (Snap-Kollisionen verwerfen). Stärkste Kante zuerst, damit
    sie bei Konkurrenz gewinnt. Ergänzt die krümmungsbasierte Verteilung, ERSETZT keine
    bestehende Rippe und verwirft keine (edges liegen bereits im [lo,hi]-Fenster)."""
    pos = [float(p) for p in pos]
    for e in edges:                                          # bereits nach Stärke sortiert
        if not pos:
            pos.append(e); continue
        j = min(range(len(pos)), key=lambda k: abs(pos[k] - e))
        if abs(pos[j] - e) <= min_gap:
            pos[j] = e                                       # nächste Rippe exakt auf die Kante
        elif all(abs(e - p) >= min_gap for p in pos):
            pos.append(e)                                    # genug Platz -> neue Rippe auf der Kante
    pos = sorted({round(p, 2) for p in pos})
    out = []
    for p in pos:                                            # min_gap durchsetzen (leftmost gewinnt)
        if not out or p - out[-1] >= min_gap - 1e-6:
            out.append(p)
    return np.array(out)


def rib_positions(Hf, cell, nx, ny, min_gap, max_gap=None, uniform=False, snap=False, snap_pct=92.0):
    """DIE eine Quelle der Rippen-X/Y-Positionen — genutzt von Gerüst UND Deckplatten,
    damit die Platten exakt zwischen die Rippen passen. Dichte folgt der SCHÄRFE:
    Detail je Spalte = 0.5*Summe (breite Krümmung) + 1.0*Max (eine scharfe Kante zieht
    die Dichte hoch, geht nicht im Spaltenmittel unter).
    snap=True rastet zusätzlich auf starke BRUCHKANTEN ein (scharfe gerade Kanten am
    Tunnel/Einschnitt/Portal, die im Krümmungs-Budget untergehen) -> keine treppige
    Silhouette mehr an diesen Kanten."""
    from scipy.ndimage import gaussian_filter
    NY, NX = Hf.shape; Wx, Dy = NX*cell, NY*cell
    if uniform:
        return np.linspace(Wx*0.08, Wx*0.92, nx), np.linspace(Dy*0.08, Dy*0.92, ny)
    Hs = gaussian_filter(Hf, 1.0)
    cx = np.abs(np.gradient(np.gradient(Hs, axis=1), axis=1))
    cy = np.abs(np.gradient(np.gradient(Hs, axis=0), axis=0))
    def sharp(c, axis):
        s = c.sum(axis=axis); m = c.max(axis=axis)
        s /= (s.max() + 1e-9); m /= (m.max() + 1e-9)
        return 0.5*s + 1.0*m
    xlo, xhi = Wx*0.06, Wx*0.94; ylo, yhi = Dy*0.06, Dy*0.94
    xpos = adaptive_pos(sharp(cx, 0), nx, xlo, xhi, cell, min_gap, max_gap)
    ypos = adaptive_pos(sharp(cy, 1), ny, ylo, yhi, cell, min_gap, max_gap)
    if snap:
        xpos = _snap_to_edges(xpos, _edge_peaks(Hf, cell, "x", xlo, xhi, min_gap, snap_pct), min_gap)
        ypos = _snap_to_edges(ypos, _edge_peaks(Hf, cell, "y", ylo, yhi, min_gap, snap_pct), min_gap)
    return xpos, ypos


def choose_seams(cross_s, L, maxlen, minwid, hfn=None, min_h=0.0, phase=0.0, name=""):
    """Naht-Positionen (entlang s) wählen: möglichst gleichmäßig alle <=maxlen, aber IMMER
    in eine Lücke zwischen zwei Kreuzungen (nie auf einen Steck-Schlitz), breit genug für Zinken.
    NEU: Nähte NUR dort, wo die Rippe hoch genug ist (h>=min_h) -> die Fingerzinken bekommen
    solides Material (mehrere Zähne, kein Mini-Zahn im flachen Talauslauf, der abbricht).
    Gibt es keine hohe Lücke, wird an der HÖCHSTEN verfügbaren Lücke geteilt (Notnagel+Warnung).
    phase (Rippen-Index): VERSETZT die Naht pro Rippe (zielt auf eine andere Lücke), damit die
    Nähte benachbarter Rippen NICHT auf eine Linie fallen (sonst durchgehende Sollbruch-Linie)."""
    cs = sorted(c for c in cross_s if 1 < c < L-1)
    bnds = [0.0] + cs + [float(L)]
    cand = [(bnds[i]+bnds[i+1])/2 for i in range(len(bnds)-1)
            if (bnds[i+1]-bnds[i]) >= minwid and 0.12*L < (bnds[i]+bnds[i+1])/2 < 0.88*L]
    if not cand: return []
    h_at = (lambda s: float(hfn(s))) if hfn is not None else (lambda s: 1e9)
    tall = [c for c in cand if h_at(c) >= min_h]
    pool = tall if tall else cand
    if not tall and name:
        print(f"  ⚠ {name}: keine Naht-Lücke ≥ {min_h:.0f}mm hoch — teile an höchster ({max(h_at(c) for c in pool):.0f}mm)")
    n = max(1, int(np.ceil(L/maxlen))); step = L/n; seams = []
    off = (0.4 * step) * (1 if int(phase) % 2 else -1)  # strikt abwechselnd (ABAB): kein Nachbar teilt eine Nahtlinie
    for i in range(1, n):
        target = L*i/n + off
        sc = min(pool, key=lambda c: abs(c - target))      # nahe am Ziel, aber nur aus hohen Lücken
        if sc not in seams: seams.append(sc)
    return sorted(seams)


def finger_split(poly, seams, fdepth, fw):
    """(s,z)-Rippenpolygon an vertikalen Nähten mit INEINANDERGREIFENDEN Fingerzinken teilen.
    Linkes Stück bekommt gerade Zinken-Bänder (ragen nach rechts), rechtes die ungeraden ->
    passen formschlüssig zusammen (verleimen). Gibt Liste von Teil-Polygonen zurück."""
    from shapely.geometry import Polygon as SP, box
    from shapely.ops import unary_union
    g = SP(poly)
    if not g.is_valid: g = g.buffer(0)
    smin, zmin, smax, zmax = g.bounds
    out = []; cur = g
    for sc in sorted(seams):
        bands = []; k = 0; z = zmin
        while z < zmax:
            bands.append((k % 2, z, min(z+fw, zmax))); z += fw; k += 1
        Lf = [box(sc, z0, sc+fdepth, z1) for (par, z0, z1) in bands if par == 0]
        leftreg = box(smin-50, zmin-50, sc, zmax+50)
        if Lf: leftreg = leftreg.union(unary_union(Lf))
        # rechte Zinken (ungerade Bänder) aus dem linken Teil ausschneiden = Nut
        Rf = [box(sc-fdepth, z0, sc, z1) for (par, z0, z1) in bands if par == 1]
        if Rf: leftreg = leftreg.difference(unary_union(Rf))
        left = cur.intersection(leftreg); cur = cur.difference(leftreg)
        out.append(left)
    out.append(cur)
    res = []
    for gg in out:
        geoms = [gg] if gg.geom_type == "Polygon" else [g for g in getattr(gg, "geoms", []) if g.geom_type == "Polygon"]
        best = max(geoms, key=lambda h: h.area) if geoms else None    # Hauptstück (Slivers verwerfen)
        if best is not None and best.area >= 20:
            res.append(np.array(best.exterior.coords))
    return res


def puzzle_split(poly, seams, fdepth, fw, taper=1.6):
    """Wie finger_split, aber SCHWALBENSCHWANZ-/Puzzle-Nasen: am Hals (an der Naht) schmaler,
    an der Spitze breiter -> verhaken sich formschlüssig und HALTEN OHNE KLEBER (Press-Fit mit
    Materialflex). taper = wie stark sich die Nase pro Seite weitet (mm). Gibt Teil-Polygone zurück."""
    from shapely.geometry import Polygon as SP, box
    from shapely.ops import unary_union
    def dove(sc, z0, z1, depth, side):                 # side=+1 ragt rechts, -1 links; Hals schmal, Spitze breit
        tp = min(taper, max(0.0, (z1-z0)/2 - 0.4))     # Taper gegen duenne (Rand-)Baender begrenzen
        tip = sc + side*depth
        return SP([(sc, z0+tp), (tip, z0), (tip, z1), (sc, z1-tp)]).buffer(0)
    g = SP(poly)
    if not g.is_valid: g = g.buffer(0)
    smin, zmin, smax, zmax = g.bounds
    out = []; cur = g
    for sc in sorted(seams):
        bands = []; k = 0; z = zmin
        while z < zmax:
            bands.append((k % 2, z, min(z+fw, zmax))); z += fw; k += 1
        Lf = [dove(sc, z0, z1, fdepth, +1) for (par, z0, z1) in bands if par == 0 and z1-z0 > 1.0]
        leftreg = box(smin-50, zmin-50, sc, zmax+50)
        if Lf: leftreg = leftreg.union(unary_union(Lf).buffer(0))
        Rf = [dove(sc, z0, z1, fdepth, -1) for (par, z0, z1) in bands if par == 1 and z1-z0 > 1.0]
        if Rf: leftreg = leftreg.difference(unary_union(Rf).buffer(0))
        leftreg = leftreg.buffer(0)
        left = cur.intersection(leftreg).buffer(0); cur = cur.difference(leftreg).buffer(0)
        out.append(left)
    out.append(cur)
    res = []
    for gg in out:
        geoms = [gg] if gg.geom_type == "Polygon" else [g for g in getattr(gg, "geoms", []) if g.geom_type == "Polygon"]
        best = max(geoms, key=lambda h: h.area) if geoms else None
        if best is not None and best.area >= 20:
            res.append(np.array(best.exterior.coords))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default=BIG); ap.add_argument("--mm", type=float, default=MM, help="HORIZONTAL mm/DEM-Zelle")
    ap.add_argument("--nscale", type=float, default=MM, help="VERTIKAL mm/echtem Meter (6.25=N)")
    ap.add_argument("--zoom", type=int, default=4, help="1 für feine 0.25m-Daten, 4 für 1m")
    ap.add_argument("--r0", type=int, default=854); ap.add_argument("--r1", type=int, default=880)
    ap.add_argument("--c0", type=int, default=850); ap.add_argument("--c1", type=int, default=886)
    ap.add_argument("--nx", type=int, default=6, help="max Rippen in Y-Richtung (an X-Positionen)")
    ap.add_argument("--ny", type=int, default=6, help="max Rippen in X-Richtung (an Y-Positionen)")
    ap.add_argument("--uniform", action="store_true", help="gleichmäßiges Raster statt adaptiv (Default: adaptiv nach Krümmung)")
    ap.add_argument("--min-gap", type=float, default=7.0, help="Mindestabstand zwischen Rippen mm — so eng dürfen scharfe Kanten die Rippen packen")
    ap.add_argument("--max-gap", type=float, default=0.0, help="Max Rippenabstand mm in flachen Zonen (0=auto)")
    ap.add_argument("--snap-edges", action="store_true", dest="snap_edges", help="(DEFAULT an) Rippen auf BRUCHKANTEN snappen — fängt scharfe gerade Kanten (Einschnitt/Portal/Felssporn), die im Krümmungs-Budget untergehen.")
    ap.add_argument("--no-snap-edges", action="store_false", dest="snap_edges", help="Schaltet --snap-edges aus (nur Krümmungs-Adaptive Dichte)")
    ap.set_defaults(snap_edges=True)
    ap.add_argument("--snap-pct", type=float, default=80.0, help="Perzentil-Schwelle für Bruchkanten-Stärke (höher = nur die schärfsten Kanten; 80 = Top-20% aller Gradienten)")
    ap.add_argument("--split-len", type=float, default=0.0, help="lange Rippen in Puzzle-Stücke <= N mm mit Fingerzinken teilen (spart Verschnitt); 0=aus")
    ap.add_argument("--finger", type=float, default=12.0, help="Fingerzinken-Höhe (mm) entlang der Naht")
    ap.add_argument("--seam-min-h", type=float, default=0.0, dest="seam_min_h", help="Fingerzinken-Naht NUR in Lücken wo die Rippe >= N mm hoch ist (solide Zähne, kein Mini-Zahn im Talauslauf); 0=auto=2×--finger")
    ap.add_argument("--min-web", type=float, default=1.5, dest="min_web", help="Hals-Warnschwelle (mm): jede Rippe wird geprüft; wird sie nach Schrumpf um --min-web/2 getrennt, kommt eine Bruch-Gefahr-Warnung")
    ap.add_argument("--thickness", type=float, default=3.0)
    ap.add_argument("--rib-depth", type=float, default=0.0, help="Rippen als konstant-tiefes Band (mm unter Oberkante) statt bis Boden -> spart Material; 0=bis Boden")
    ap.add_argument("--base", type=float, default=12.0, help="Sockel mm: Gelände anheben, damit Rippen am Talboden nicht auf 0 pinchen (gegen 'schwebende' Teile)")
    ap.add_argument("--fit", type=float, default=-0.4, help="Schlitz-Spiel mm (slotw = Dicke + fit). KALIBRIERT für 3 mm Pappelsperrholz am Sculpfun S9: -0.4 (Schlitz 2.6 mm) steckt satt mit etwas Spiel (Steck-Test joint_fit_test.py, 26 perfekt); -0.5 (2.5 mm) war zu stramm. Bei anderem Material/Laser neu kalibrieren.")
    ap.add_argument("--vscale", type=float, default=1.0, help="Höhen-Überhöhung (1=true-N)")
    ap.add_argument("--trans-frac", type=float, default=0.85,
                    help="Übergangshöhe als Anteil der Max-Höhe: Gitter bis dahin, DÜNNER Kontur-Stack drüber (1.0=nur Gitter)")
    ap.add_argument("--min-seg", type=float, default=1.0)
    ap.add_argument("--dowel-d", type=float, default=3.2)
    ap.add_argument("--smooth", type=float, default=4.0)
    ap.add_argument("--bed-x", type=float, default=410); ap.add_argument("--bed-y", type=float, default=400)
    ap.add_argument("--tunnel", action="store_true", help="Bahn-Lichtraum (30x36mm) in die Rippen schneiden: Tunnel=gedeckelt, offen=Einschnitt")
    ap.add_argument("--track", default="", help="ECHTE Trasse als .npy (Zeilen mx,my,mz,is_tunnel in Modell-mm, z.B. aus OSM); leer=keine")
    ap.add_argument("--diag", type=float, default=0.0, help="4-RICHTUNGS-GITTER: zusätzlicher 45°-Diagonal-Rippensatz mit diesem senkrechten Abstand (mm); 0=aus. Fängt schräge Kanten (~30%% genauer bei gleichem Material).")
    ap.add_argument("--diag-both", action="store_true", help="auch 135°-Diagonalen (volles 4-Richtungs-Gitter; ⚠ 45°/135° kreuzen sich, Steck-Kollision noch nicht gelöst)")
    ap.add_argument("--tunnel-drop", type=float, default=0.0, help="Tunnel-Gleis um N mm tiefer legen (unters Dach statt drauf)")
    ap.add_argument("--tunnel-w-m", type=float, default=4.0, dest="tunnel_w_m", help="ECHTE Tunnel-Breite in METERN (wird mit nscale maßstäblich skaliert); eng einspurig ~4 m")
    ap.add_argument("--tunnel-h-m", type=float, default=5.5, dest="tunnel_h_m", help="ECHTE Tunnel-Höhe in METERN (wird mit nscale·vscale skaliert); ~5.5 m")
    ap.add_argument("--roof-min", type=float, default=2.0, dest="roof_min", help="Mindest-Dachdicke (mm) über dem Tunnel-Loch; sonst wird's ein offener Einschnitt")
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--feed", type=float, default=400); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=20)
    ap.add_argument("--out", default="/tmp/crate")
    a = ap.parse_args()
    if a.seam_min_h <= 0: a.seam_min_h = 2.0 * a.finger   # auto: Naht nur wo >= 2 Finger solide passen

    from scipy.ndimage import zoom, gaussian_filter
    dem_full = np.load(a.dem)
    win = dem_full[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)                       # nodata
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]                                                 # Zeile ↓=Süd flippen (+y=Nord, nicht spiegelverkehrt)
    win_min = float(win.min()); zf = max(1, a.zoom)
    rel = gaussian_filter(zoom(win - win_min, zf, order=1) if zf > 1 else (win - win_min), a.smooth)
    cell = a.mm / zf                              # HORIZONTAL mm/Zelle
    Hf = rel * a.nscale * a.vscale + a.base       # VERTIKAL: Relief_m × mm/Meter (+ Sockel, damit Rippen nie auf 0 pinchen)
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell
    os.makedirs(a.out, exist_ok=True)

    def Hat(xmm, ymm):
        xi = min(max(xmm/cell, 0), NX-1); yi = min(max(ymm/cell, 0), NY-1)
        return float(Hf[int(round(yi)), int(round(xi))])
    z_t = Hf.max() * a.trans_frac                 # Übergangshöhe Gitter->Stack
    def Hc(xmm, ymm): return min(Hat(xmm, ymm), z_t)   # geklemmt: Gitter nur bis z_t
    band = a.rib_depth > 0                         # Rippen als konstant-tiefes Band (Material sparen)
    def Htop(x, y): return Hat(x, y) if band else Hc(x, y)
    def Hbot(x, y): return max(0.0, Htop(x, y) - a.rib_depth) if band else 0.0

    # --- Trasse (Höllentalbahn): Freiraum entlang der GANZEN Strecke, falls --tunnel ---
    # Tunnel-Teil (TUN, gedeckelt) = geschlossenes 30x36-Loch; offene Strecke (EAST) =
    # offener Einschnitt (Trog) bis zur Oberkante, sonst fährt der Zug in die Rippen.
    # Tunnel-Teil (gedeckelt) = geschlossenes 30x36-Loch; offene Strecke = offener Einschnitt
    # (Trog) bis zur Oberkante. Trasse kommt als ECHTE OSM-Datei (mx,my,mz,is_tunnel).
    # Lichtraum MASSSTÄBLICH: echte Tunnelröhre (Meter) × Modell-Maßstab -> skaliert automatisch
    # mit (hier 50%). Früher absolute 30×36 mm = ein Full-N-Zug (~9.6×13.5 m real!) -> viel zu
    # groß für das halb-skalierte Gelände -> Loch brach oben durch (kein Dach).
    CLEAR_W = a.tunnel_w_m * a.nscale
    CLEAR_H = a.tunnel_h_m * a.nscale * a.vscale
    tun_pts = []; track = []
    if a.tunnel:
        if not a.track or not os.path.exists(a.track):
            print(f"!! --tunnel ohne gültige --track Datei ({a.track!r}) -> kein Tunnel");
        else:
            raw = np.load(a.track)                             # (N,4): mx,my,mz,is_tunnel
            dense = []                                         # ~2mm feiner interpolieren
            for k in range(len(raw)-1):
                p, q = raw[k], raw[k+1]
                L = max(2, int(np.hypot(q[0]-p[0], q[1]-p[1])/2))
                for tt in np.linspace(0, 1, L, endpoint=(k == len(raw)-2)):
                    mx = p[0]+(q[0]-p[0])*tt; my = p[1]+(q[1]-p[1])*tt
                    mz = p[2]+(q[2]-p[2])*tt; istun = p[3] > 0.5
                    dense.append((mx, my, mz - (a.tunnel_drop if istun else 0.0), istun))
            track = [p for p in dense if -6 <= p[0] <= Wx+6 and -6 <= p[1] <= Dy+6]
            tun_pts = [(p[0], p[1], p[2]) for p in track]
            print(f"Trasse geladen: {len(track)} Punkte ({sum(1 for p in track if p[3])} Tunnel / {sum(1 for p in track if not p[3])} offen)")

    def _rect2(cs, zlo, zhi, w):
        return [(cs-w/2,zlo),(cs+w/2,zlo),(cs+w/2,zhi),(cs-w/2,zhi),(cs-w/2,zlo)]
    def tunnel_holes(axis, pos):
        cuts = []
        for k in range(len(track)-1):
            p, q = track[k], track[k+1]
            a0,a1,s0,s1 = (p[1],q[1],p[0],q[0]) if axis=="x" else (p[0],q[0],p[1],q[1])
            if (a0-pos)*(a1-pos) <= 0 and abs(a1-a0) > 1e-6:
                t=(pos-a0)/(a1-a0); s=s0+(s1-s0)*t; z=p[2]+(q[2]-p[2])*t
                # Trasse schräg zur Rippe -> Loch in Schnittrichtung aufweiten, damit SENKRECHT
                # zum Gleis volle CLEAR_W bleiben (sonst klemmt ein N-Waggon an den Rippenkanten):
                seglen = float(np.hypot(s1-s0, a1-a0))
                w = CLEAR_W * min(2.6, seglen/abs(a1-a0))      # /sin(Winkel), gekappt
                terr = (Hc(s, pos) if axis=="x" else Hc(pos, s))
                if p[3]:                                       # Tunnel: geschlossenes Loch MIT Dach
                    top = min(z+CLEAR_H, terr - a.roof_min)    # mind. roof_min Gelände als Dach lassen
                    if top - (z-4) < 6:                        # Berg zu flach -> kein echter Tunnel
                        cuts.append(_rect2(s, z-4, terr+6, w)) # -> offener Einschnitt (ehrlich)
                    else:
                        cuts.append(_rect2(s, z-4, top, w))    # geschlossen, Dach bleibt stehen
                else:                                          # offen: Einschnitt bis Oberkante
                    cuts.append(_rect2(s, z-4, max(terr+6, z+CLEAR_H), w))
        return cuts

    mg = a.max_gap if a.max_gap > 0 else None
    xpos, ypos = rib_positions(Hf, cell, a.nx, a.ny, a.min_gap, mg, a.uniform, a.snap_edges, a.snap_pct)
    slotw = a.thickness + a.fit
    made = []; oversize = []
    manifest = [f"EGG-CRATE Gerüst  {Wx:.0f}x{Dy:.0f} mm, Höhe bis {Hf.max():.0f} mm "
                f"(vscale {a.vscale}, {a.mm} mm/Zelle)",
                f"Material {a.thickness} mm, Schlitz {slotw:.2f} mm  |  {len(ypos)} X-Rippen + {len(xpos)} Y-Rippen"
                f" ({'gleichmäßig' if a.uniform else 'ADAPTIV: dicht bei Detail, weit bei flach'})",
                "MONTAGE: X-Rippen (Schlitz oben) + Y-Rippen (Schlitz unten) ineinanderstecken.",
                "Dann Gips/Haut über die Rippen-Oberkanten.", ""]

    def emit(name, poly, label, extra_cuts=None):
        poly = np.array(poly, float)
        cuts = [poly] + list(extra_cuts or [])      # extra = Tunnel-Löcher
        # Gravur KLEIN (~5mm) in eine GARANTIERT SOLIDE Stelle legen (nicht in einen Schlitz/
        # Ausschnitt!). Y-Rippen haben Schlitze unten, X-Rippen oben -> per Polygon-Check eine
        # Position suchen, wo das ganze Label-Rechteck INNERHALB des Teils liegt.
        from matplotlib.path import Path as _MP
        def _dense(strokes):                       # Glyphen -> dichte Punktwolke (alle ~0.8mm)
            pts = []
            for s in strokes:
                s = np.array(s, float)
                for k in range(len(s)-1):
                    d = np.hypot(*(s[k+1]-s[k])); n = max(1, int(d/0.8))
                    for t in np.linspace(0, 1, n+1): pts.append(s[k] + (s[k+1]-s[k])*t)
            return np.array(pts) if pts else np.zeros((1, 2))
        mp = _MP(poly[:, :2]); x0 = float(poly[:, 0].min()); x1 = float(poly[:, 0].max())
        ph = float(np.ptp(poly[:, 1])); bx, by, lh = x0+3, 2.0, 5.0; placed = False
        for lh in (5.0, 4.0, 3.0, 2.5, 2.0):       # notfalls kleiner, bis es in eine Lücke passt
            tmpl = _dense(glyph_strokes(str(label), 0, 0, h=lh))   # echte Glyphen-Punkte am Ursprung
            cw = float(tmpl[:, 0].max()); ch = float(tmpl[:, 1].max())
            if cw > (x1-x0) - 4: continue
            for yb in np.linspace(2.0, max(2.0, ph-ch-2), 16):     # unten->oben (über Schlitztiefe)
                for cand in np.linspace(x0+2, max(x0+2, x1-cw-2), 50):
                    if mp.contains_points(tmpl + [cand, yb]).all():
                        bx, by, placed = cand, yb, True; break
                if placed: break
            if placed: break
        eng = glyph_strokes(str(label), bx, by, h=lh)
        svg_write(f"{a.out}/{name}.svg", cuts, [], [], eng, 0)
        if a.gcode:
            gcode_write(f"{a.out}/{name}.gcode", cuts, [], [], eng, 0,
                        a.feed, a.power, a.passes, a.eng_power)
        bb = (np.ptp(poly[:,0]), np.ptp(poly[:,1])); made.append(name)
        if bb[0] > a.bed_x or bb[1] > a.bed_y: oversize.append((name, bb))
        return bb

    ribdata = []; nonlocal_fragile = []              # Rippen mit dünnem Hals (Bruch-Gefahr) -> Report
    fdepth = max(8.0, 2*a.thickness)                 # Zinken-Tiefe (in s) = min. 2× Materialdicke
    def clip_holes(sp, holes):                        # Tunnel-Löcher aufs Teilstück beschneiden
        from shapely.geometry import Polygon as SP
        seg = SP(sp); seg = seg if seg.is_valid else seg.buffer(0); out = []
        for h in holes:
            hp = SP(h); hp = hp if hp.is_valid else hp.buffer(0)
            it = seg.intersection(hp)
            if it.is_empty or it.area < 1: continue
            for gg in (list(it.geoms) if it.geom_type == "MultiPolygon" else [it]):
                if gg.area >= 1: out.append(np.array(gg.exterior.coords))
        return out

    def _body_necks(poly, web, seams):
        """Zahl ECHTER Körper-Bruchstücke (Hals < web) ABSEITS der Fingerzinken-Naht.
        Nach Schrumpf um web/2 zerfällt die Rippe; GROSSE Teilstücke (>=30mm²), deren
        Schwerpunkt NICHT nahe einer Naht liegt, sind echte Soll-Bruchstellen im Körper
        (Rippe fällt auseinander). Zinken an der Naht (werden verklebt) werden ignoriert."""
        from shapely.geometry import Polygon as _P
        g = _P(poly); g = g if g.is_valid else g.buffer(0)
        if g.geom_type == "MultiPolygon": g = max(g.geoms, key=lambda h: h.area)
        er = g.buffer(-web/2.0)
        comps = list(er.geoms) if er.geom_type == "MultiPolygon" else ([er] if not er.is_empty else [])
        margin = fdepth + 3.0
        big = [c for c in comps if c.area >= 30.0 and not any(abs(c.centroid.x - sc) <= margin for sc in seams)]
        return len(big)

    def _emit_rib(name, poly, label, extra, seams):
        bb = emit(name, poly, label, extra)
        if _body_necks(poly, a.min_web, seams) > 1:      # >1 echtes Körperstück = Rippe bricht auseinander
            nonlocal_fragile.append(name)
            print(f"  ⚠ {name}: echter Körper-Hals < {a.min_web}mm — Rippe bricht auseinander (nicht an der Naht!)")
        return bb

    def add_rib(prefix, coordlab, poly, axis, pos, th, L, cross_s, hfn, ph=0):
        """emittiert eine Rippe; teilt sie bei --split-len in verzinkte Puzzle-Stücke.
        hfn(s)=Rippenhöhe an s -> Naht nur wo hoch genug (solide Zinken, kein Mini-Zahn).
        ph=Rippen-Index -> Naht pro Rippe versetzt (keine durchgehende Nahtlinie)."""
        seams = (choose_seams(cross_s, L, a.split_len, 2*fdepth+slotw+4, hfn, a.seam_min_h, phase=ph, name=prefix)
                 if a.split_len > 0 and np.ptp(poly[:, 0]) > a.split_len else [])
        if not seams:
            bb = _emit_rib(f"rib{prefix}", poly, f"{prefix} {coordlab}", th, [])
            ribdata.append((prefix, poly, axis, pos, th))
            manifest.append(f"  {prefix}: {bb[0]:.0f}x{bb[1]:.0f} mm" + (f"  (+{len(th)} Tunnel)" if th else ""))
            return
        segs = finger_split(poly, seams, fdepth, a.finger)
        for si, sp in enumerate(segs):
            lt = chr(97+si); hh = clip_holes(sp, th)
            bb = _emit_rib(f"rib{prefix}{lt}", sp, f"{prefix}{lt} {coordlab}", hh, seams)
            ribdata.append((f"{prefix}{lt}", sp, axis, pos, hh))
            manifest.append(f"  {prefix}{lt}: {bb[0]:.0f}x{bb[1]:.0f} mm (Zinken)" + (f" (+{len(hh)} Tunnel)" if hh else ""))

    # Gemeinsame Schlitz-Mittellinie (hmid) pro Kreuzung — INTERLOCK-SICHER (beide Rippen nutzen
    # dieselbe Formel): kappe hmid so, dass die Y-Rippe (Schlitz von UNTEN, Steg OBEN zur Oberkante)
    # über die ganze Schlitzbreite >= min_web Steg behält, auch in STEILEM Gelände (dort fällt die
    # Oberkante neben dem Schlitz stark ab -> sonst dünner Steg = Bruch, wie ribY2). Die X-Rippe
    # (Schlitz OBEN, Steg UNTEN zur flachen Basis) ist unkritisch, braucht nur hmid >= Basis+min_web.
    _hslot = slotw/2 + 0.4
    def hmid_at(x, y):
        raw = (Hbot(x, y) + Htop(x, y)) / 2.0
        hi = min(Htop(x, y + t) for t in np.linspace(-_hslot, _hslot, 5)) - a.min_web   # Steg oben (Y-Rippe)
        lo = Hbot(x, y) + a.min_web                                                      # Steg unten (X-Rippe)
        return float(np.clip(raw, lo, hi)) if lo <= hi else raw   # zu kurz/steil: bestmöglich (Mitte)

    # --- AUTO-NUDGE: Y-Rippen mit echtem KÖRPER-Hals (ein Steck-Schlitz liegt an einer near-
    # vertikalen Gelände-Klippe -> dünner Streifen zwischen Schlitzwand und Kante) um wenige mm
    # versetzen, bis bruchfrei. Nur Y-Rippen (Schlitz UNTEN) können das haben; die X-Schlitze
    # folgen automatisch, weil sie dasselbe (jetzt versetzte) xpos nutzen -> Verzahnung bleibt. ---
    def _ybody_neck(xr):
        cr = [(yp, hmid_at(xr, yp)) for yp in ypos]
        bf = (lambda s, xr=xr: Hbot(xr, s)) if band else None
        pl = np.array(rib(Dy, lambda s, xr=xr: Htop(xr, s), cr, slotw, False, bf), float)
        return _body_necks(pl, a.min_web, [])
    xpos = list(np.asarray(xpos, float))
    for ii in range(len(xpos)):
        if _ybody_neck(xpos[ii]) <= 1: continue
        lo_lim = (xpos[ii-1] + a.min_gap) if ii > 0 else 0.0
        hi_lim = (xpos[ii+1] - a.min_gap) if ii < len(xpos)-1 else Wx
        best = None
        for d in (1,-1,2,-2,3,-3,4,-4,5,-5,6,-6):
            c = xpos[ii] + d
            if c < lo_lim or c > hi_lim: continue
            if _ybody_neck(c) <= 1: best = c; break
        if best is not None:
            print(f"  ⟳ Auto-Nudge Y{ii}: x {xpos[ii]:.1f} -> {best:.1f} mm (Körper-Hals an Gelände-Klippe vermieden)")
            xpos[ii] = best
        else:
            print(f"  ⚠ Y{ii}: kein bruchfreier Versatz in ±6mm — bleibt (Validierung warnt)")
    xpos = np.array(sorted(xpos))

    for j, yr in enumerate(ypos):     # X-Rippen: Schlitz OBEN, Kreuzung an xpos (Höhe geklemmt auf z_t)
        cross = [(xp, hmid_at(xp, yr)) for xp in xpos]
        bsf = (lambda s, yr=yr: Hbot(s, yr)) if band else None
        hfn = (lambda s, yr=yr: Htop(s, yr) - (Hbot(s, yr) if band else 0.0))
        poly = np.array(rib(Wx, lambda s, yr=yr: Htop(s, yr), cross, slotw, True, bsf), float)
        add_rib(f"X{j}", f"Y{yr:.0f}", poly, "x", yr, tunnel_holes("x", yr), Wx, list(xpos), hfn, ph=j)
    for i, xr in enumerate(xpos):     # Y-Rippen: Schlitz UNTEN, Kreuzung an ypos
        cross = [(yp, hmid_at(xr, yp)) for yp in ypos]
        bsf = (lambda s, xr=xr: Hbot(xr, s)) if band else None
        hfn = (lambda s, xr=xr: Htop(xr, s) - (Hbot(xr, s) if band else 0.0))
        poly = np.array(rib(Dy, lambda s, xr=xr: Htop(xr, s), cross, slotw, False, bsf), float)
        add_rib(f"Y{i}", f"X{xr:.0f}", poly, "y", xr, tunnel_holes("y", xr), Dy, list(ypos), hfn, ph=i)

    # ============ B4 Schritt 2: KANTEN-LINEALE (diagonale Kanten-Rippen) ============
    # Scharfe Kanten (beliebige Richtung) als vertikale Finnen, die sich per HALB-ÜBERBLATTUNG
    # in die X/Y-Rippen stecken: Lineal-Oberkante = FEINES Relief (die scharfe Kante, die die
    # glatten Rippen verfehlen) und bleibt DURCHGEHEND (Schlitz von UNTEN); jede gekreuzte Rippe
    # bekommt oben einen passenden Schlitz. Gips legt sich an die Lineal-Oberkanten -> Kante scharf.
    edge_rulers = []                                   # (name, poly2d(s,z), (x0,y0,x1,y1))
    edge_segs = []                                     # erkannte Kanten-Segmente (Welt-mm) für den Overlay
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import manmade_edges as _mmE
        from shapely.geometry import Polygon as _ShP, box as _shbox
        _we = dem_full[a.r0:a.r1, a.c0:a.c1].astype(float)
        _we = np.where(_we < -1000, np.nan, _we)
        if np.isnan(_we).any(): _we = np.where(np.isnan(_we), np.nanmin(_we), _we)
        _Hfe = gaussian_filter(_we[::-1] - float(np.nanmin(_we)), 0.4) * a.nscale * a.vscale + a.base
        # FUSSELIGE Kanten (Bahndamm-Grat, Einschnitt-Graben, Tunnelausgang) via Ridge-Filter +
        # Canny-Hysterese statt LSD-auf-Schärfe -> fängt die verrauschten Kanten, die vorher fehlten.
        _edgE = _mmE.detect_edges_ridges(_Hfe, cell, min_len_mm=10.0)
        edge_segs = _edgE                                  # für den Overlay im Viewer wiederverwenden
        _ehY, _ehX = _Hfe.shape
        def _Hfine(x, y): return float(_Hfe[min(int(y/cell), _ehY-1), min(int(x/cell), _ehX-1)])
        FINH, LAP, MINLEN = 9.0, 4.0, 10.0
        edge_notches = {}                              # ribdata-Index -> [(s_auf_rippe, htop, zmid)]
        def _build_ruler(x0, y0, x1, y1, topfn, botfn, zmidfn, name):
            """Beliebig gerichtete Rippe (Kante oder Diagonale): Kreuzungen mit X/Y-Rippen ->
            HALB-ÜBERBLATTUNG. zmidfn(cx,cy) bestimmt die Lap-Höhe (Fin: nahe Oberkante; Voll-Rippe:
            Mitte, balanciert wie X/Y). Registriert die Rippen-Oberkerben in edge_notches."""
            L = float(np.hypot(x1 - x0, y1 - y0))
            if L < MINLEN: return None
            crossings = []
            for _ri, (_rnm, _rpoly, _rax, _rpos, _rth) in enumerate(ribdata):
                if _rax == "x":                        # X-Rippe bei y=_rpos
                    if abs(y1 - y0) < 1e-6: continue
                    t = (_rpos - y0) / (y1 - y0)
                    if not (0.02 < t < 0.98): continue
                    sc = t * L; cx, cy = x0 + (x1 - x0) * t, _rpos
                    if not (0 <= cx <= Wx): continue
                else:                                  # Y-Rippe bei x=_rpos
                    if abs(x1 - x0) < 1e-6: continue
                    t = (_rpos - x0) / (x1 - x0)
                    if not (0.02 < t < 0.98): continue
                    sc = t * L; cx, cy = _rpos, y0 + (y1 - y0) * t
                    if not (0 <= cy <= Dy): continue
                zmid = zmidfn(cx, cy)
                if zmid <= a.base + 1 or zmid >= Htop(cx, cy) - 0.5: continue
                _rs = cx if _rax == "x" else cy        # Position auf der gekreuzten Rippe (deren s-Achse)
                crossings.append((sc, zmid)); edge_notches.setdefault(_ri, []).append((_rs, Htop(cx, cy), zmid))
            crossings.sort(); merged = []
            for (sc, zm) in crossings:
                if merged and sc - merged[-1][0] < slotw + 1: continue
                merged.append((sc, zm))
            if not merged: return None
            return (name, np.array(rib(L, topfn, merged, slotw, False, botfn), float), (x0, y0, x1, y1))
        # (1) KANTEN-LINEALE: kurze Finnen, Oberkante = feines Relief, Lap nahe Oberkante
        for (x0, y0, x1, y1) in _edgE:
            L = float(np.hypot(x1 - x0, y1 - y0))
            if L < MINLEN: continue
            dx, dy = (x1 - x0) / L, (y1 - y0) / L
            _tf = (lambda s, x0=x0, y0=y0, dx=dx, dy=dy: _Hfine(x0 + dx*s, y0 + dy*s))
            _bf = (lambda s, tf=_tf: max(a.base, tf(s) - FINH))
            _zf = (lambda cx, cy: min(Htop(cx, cy), _Hfine(cx, cy)) - LAP)
            r = _build_ruler(x0, y0, x1, y1, _tf, _bf, _zf, f"K{len(edge_rulers)}")
            if r: edge_rulers.append(r)
        # (2) 4-RICHTUNGS-GITTER: diagonale VOLL-HÖHEN-Rippen (45°) steckend in die X/Y-Rippen ->
        # fängt schräg laufende Kanten, die das Rechteckgitter verfehlt (gemessen ~30% weniger
        # Rekonstruktions-Fehler bei gleichem Material). Oberkante=Htop (tragend), Boden=0, Lap=Mitte.
        if getattr(a, "diag", 0.0) > 0:
            _SPd = a.diag * (2.0 ** 0.5)               # Offset-Schritt -> SENKRECHTER Abstand = a.diag
            _dsegs = []
            _k = -Dy + _SPd                            # 45°: x - y = k
            while _k < Wx:
                _xa, _xb = max(0.0, _k), min(Wx, _k + Dy)
                if (_xb - _xa) * (2.0**0.5) > MINLEN: _dsegs.append((_xa, _xa - _k, _xb, _xb - _k))
                _k += _SPd
            if getattr(a, "diag_both", False):         # 135°: x + y = k (⚠ kreuzt die 45° — nur wenn gewünscht)
                _k = _SPd
                while _k < Wx + Dy:
                    _xa, _xb = max(0.0, _k - Dy), min(Wx, _k)
                    if (_xb - _xa) * (2.0**0.5) > MINLEN: _dsegs.append((_xa, _k - _xa, _xb, _k - _xb))
                    _k += _SPd
            _zfm = (lambda cx, cy: (Hbot(cx, cy) + Htop(cx, cy)) / 2.0)   # balancierte Mitte
            for (x0, y0, x1, y1) in _dsegs:
                _Ld = float(np.hypot(x1 - x0, y1 - y0)); _dxd, _dyd = (x1 - x0) / _Ld, (y1 - y0) / _Ld
                _tf = (lambda s, x0=x0, y0=y0, dx=_dxd, dy=_dyd: Htop(x0 + dx*s, y0 + dy*s))
                _bf = ((lambda s, x0=x0, y0=y0, dx=_dxd, dy=_dyd: Hbot(x0 + dx*s, y0 + dy*s)) if band else (lambda s: 0.0))
                r = _build_ruler(x0, y0, x1, y1, _tf, _bf, _zfm, f"D{len(edge_rulers)}")
                if r: edge_rulers.append(r)
        # KEINE Top-Kerben mehr in die Rippen (frühere Halb-Überblattung ABGESCHAFFT):
        # Die Kanten-Lineale werden OBEN AUFGEKLEBT, nicht eingesteckt. Grund:
        #  (1) die Kerben konnten Rippen zerteilen (Tunnelnähe -> loses Bruchstück, s. Y4),
        #  (2) sie hätten verlangt, bereits geschnittene Rippen neu zu schneiden, und
        #  (3) sie waren ohnehin nie im SVG/G-Code gelandet (nur im Tool/Vorschau =
        #      Phantom-Kerben). Rippen behalten also ihre SAUBERE Oberkante ->
        #      Schnitt == Tool == Vorschau. ribdata bleibt UNVERÄNDERT; edge_notches
        #      wird nicht mehr angewendet.
        # SVG/G-Code der Lineale (nur die K-Teile selbst; sie tragen ihre Kreuzungs-
        # schlitze, damit sie beim Aufsetzen über die Rippen rutschen und verklebt werden).
        for (knm, kpoly, seg) in edge_rulers:
            emit(knm, kpoly, knm)  # knm ist schon "K0", "K1" etc.
        print(f"B4: {len(edge_rulers)} Kanten-Lineale (werden OBEN AUFGEKLEBT — keine Rippen-Kerben)")
    except Exception as _be:
        edge_rulers = []
        import traceback
        print("B4 Kanten-Lineale übersprungen:", repr(_be))
        traceback.print_exc()

    # --- KONTUR-STACK oben drauf (z_t .. Hmax), nur wenn trans_frac < 1 ---
    stackdata = []; hr = a.dowel_d/2
    if a.trans_frac < 0.999 and not band:
        levels = np.arange(z_t + a.thickness*0.5, Hf.max(), a.thickness)
        holes_xy = []
        for lv in levels[::-1]:                    # Dübel in breiter hoher Lage
            ps = [decimate(p*cell, a.min_seg) for p in contour_polys(Hf, lv)]
            if not ps: continue
            bp = max(ps, key=lambda p: np.ptp(p[:,0])*np.ptp(p[:,1]))
            bw, bh = np.ptp(bp[:,0]), np.ptp(bp[:,1])
            if bw >= 30 and bh >= 20:
                cx=(bp[:,0].min()+bp[:,0].max())/2; cy=(bp[:,1].min()+bp[:,1].max())/2
                holes_xy = [(bp[:,0].min()+10,cy),(bp[:,0].max()-10,cy)] if bw>=bh else [(cx,bp[:,1].min()+10),(cx,bp[:,1].max()-10)]
                break
        for li, lv in enumerate(levels):
            ps = [decimate(p*cell, a.min_seg) for p in contour_polys(Hf, lv)]
            ps = [p for p in ps if len(p) >= 4]
            if not ps: continue
            hh = [(hx,hy) for (hx,hy) in holes_xy if any(pip(hx,hy,p) for p in ps)]
            allp = np.vstack(ps)
            eng = glyph_strokes(f"{li:02d}", allp[:,0].min()+3, allp[:,1].min()+3, h=6)
            svg_write(f"{a.out}/layer_{li:02d}.svg", list(ps), [], hh, eng, hr)
            if a.gcode: gcode_write(f"{a.out}/layer_{li:02d}.gcode", list(ps), [], hh, eng, hr,
                                    a.feed, a.power, a.passes, a.eng_power)
            stackdata.append((li, lv, ps, hh))
        manifest.append(f"  + KONTUR-STACK Lage 00..{len(stackdata)-1} (z_t={z_t:.0f}..{Hf.max():.0f} mm, {len(stackdata)} Lagen)")

    if oversize:
        manifest.append(f"!! {len(oversize)} Rippen > Bett ({a.bed_x:.0f}x{a.bed_y:.0f}) -> vertikal stückeln:")
        for (nm, bb) in oversize: manifest.append(f"   {nm}: {bb[0]:.0f}x{bb[1]:.0f}")
    open(f"{a.out}/MANIFEST.txt", "w").write("\n".join(manifest)+"\n")
    print("\n".join(manifest))
    print(f"\n{len(made)} Rippen -> {a.out}/  (SVG"+(" + GRBL" if a.gcode else "")+")")
    if nonlocal_fragile:
        print(f"⚠ HALS-WARNUNG: {len(nonlocal_fragile)} Teile mit Hals < {a.min_web}mm (Bruch-Gefahr beim Hantieren): {', '.join(nonlocal_fragile)}")
        print(f"  -> Gegenmittel: höherer --base (Rippen überall höher), gröberes --min-gap, oder diese Teile vorsichtig entgittern/mit Sekundenkleber stabilisieren.")
    else:
        print(f"✓ Alle Rippen robust (kein Hals < {a.min_web}mm).")

    # --- Vorschau 1: 3D ZUSAMMENGESTECKT (Rippen als echte Platten) ---
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(9, 7)); ax = fig.add_subplot(111, projection="3d")
    for (nm, poly, axis, pos, th) in ribdata:
        if axis == "x":
            verts = [[(px, pos, pz) for (px, pz) in poly]]; col = "#caa06a"
            tnum = (poly[:,0].min(), pos, poly[:,1].max())
        else:
            verts = [[(pos, py, pz) for (py, pz) in poly]]; col = "#6a9a7a"
            tnum = (pos, poly[:,0].min(), poly[:,1].max())
        ax.add_collection3d(Poly3DCollection(verts, alpha=0.5, facecolor=col,
                                             edgecolor="#333", linewidths=0.3))
        ax.text(*tnum, nm, color="k", fontsize=7, weight="bold")          # Nummer
        for hole in th:                                                    # Tunnel-Loch rot
            h = np.array(hole)
            if axis == "x": ax.plot(h[:,0], [pos]*len(h), h[:,1], color="red", lw=1.2)
            else:           ax.plot([pos]*len(h), h[:,0], h[:,1], color="red", lw=1.2)
    for (li, lv, ps, hh) in stackdata:          # Kontur-Stack oben drauf (falls vorhanden)
        for pm in ps:
            ax.plot(pm[:,0], pm[:,1], [lv]*len(pm), color="#b0406a", lw=0.8)
    if tun_pts:
        T = np.array(tun_pts); ax.plot(T[:,0], T[:,1], T[:,2], color="red", lw=2.5, alpha=0.7)
    ax.set_xlim(0, Wx); ax.set_ylim(0, Dy); ax.set_zlim(0, Hf.max())
    ax.set_box_aspect((Wx, Dy, max(Hf.max(), 1))); ax.view_init(elev=25, azim=-55)
    ax.set_title(f"ZUSAMMENGESTECKT — {len(ypos)}+{len(xpos)} Rippen {'(adaptiv)' if not a.uniform else ''}, {Hf.max():.0f} mm (Gips kommt drüber)")
    plt.tight_layout(); plt.savefig(f"{a.out}/_3d_assembled.png", dpi=95)

    # --- Vorschau 2: 2D CUT-LAYOUT (wie geschnitten, auf Bettbreite genestet) ---
    parts2d = [(nm, [poly] + list(th)) for (nm, poly, axis, pos, th) in ribdata]
    parts2d += [(f"L{li:02d}", list(ps)) for (li, lv, ps, hh) in stackdata]
    parts2d += [(knm, [kpoly]) for (knm, kpoly, seg) in edge_rulers]       # B4: Kanten-Lineale mit ins Cut-Layout
    fig, ax = plt.subplots(figsize=(13, 9))
    xoff = yoff = rowh = 0.0; pad = 10.0; bedw = a.bed_x
    for (nm, polys) in parts2d:
        allp = np.vstack(polys); mn = allp.min(0)
        w = np.ptp(allp[:, 0]); h = np.ptp(allp[:, 1])
        if xoff + w > bedw and xoff > 0: xoff = 0; yoff += rowh + pad; rowh = 0
        for poly in polys:
            p = poly - mn + [xoff, yoff]
            ax.plot(p[:, 0], p[:, 1], "r" if not nm.startswith("L") else "#b0406a", lw=0.6)
        ax.text(xoff+4, yoff+10, nm, color="g", fontsize=9, weight="bold")
        xoff += w + pad; rowh = max(rowh, h)
    ax.axvline(bedw, color="b", ls="--", lw=0.8); ax.text(bedw+2, 5, f"Bett {bedw:.0f} mm", color="b", fontsize=8)
    ax.set_aspect("equal"); ax.invert_yaxis()
    ax.set_title("CUT-LAYOUT (wie geschnitten) — rot=Schnitt, grün=Nr., gestapelt auf Bettbreite")
    plt.tight_layout(); plt.savefig(f"{a.out}/_cut_layout.png", dpi=90)

    # --- Interaktiver 3D-Viewer (HTML, drehbar) ---
    try:
        import trimesh as _tm
        from shapely.geometry import Polygon
        def _extrude(g, h):                      # MultiPolygon-sicher extrudieren
            geoms = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
            ms = [_tm.creation.extrude_polygon(gg, h) for gg in geoms if gg.area >= 1]
            return _tm.util.concatenate(ms) if ms else None
        import colorsys
        def pcolor(k, warm):                       # je Puzzle-Stück eigene Farbe -> Nähte sichtbar
            h = ((0.07 if warm else 0.33) + (k*0.11)) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h, 0.5, 0.92)
            return [int(r*255), int(g*255), int(b*255), 255]
        eh = 5.0                                    # Gravur-Texthöhe klein (wie Laser-Gravur)
        plates = []; engrave_lines = []; named_pieces = []; kc = 0
        for (nm, poly, axis, pos, th) in ribdata:
            pg = Polygon(poly)
            if not pg.is_valid: pg = pg.buffer(0)
            for hole in th:                        # Tunnel-Loch aus der Platte rausschneiden
                hp = Polygon(hole)
                if hp.is_valid and not hp.is_empty: pg = pg.difference(hp)
            if pg.is_empty or pg.area < 1: continue
            pm = _extrude(pg, a.thickness)
            if pm is None: continue
            V = pm.vertices.copy()
            # Gravur (X/Y + Nummer) auf die Holz-Vorderfläche legen, wie der Laser sie einbrennt
            smin = float(np.array(poly)[:,0].min())
            label = f"{nm} Y{pos:.0f}" if axis == "x" else f"{nm} X{pos:.0f}"
            face = pos + a.thickness/2 + 0.25
            for st in glyph_strokes(label, smin+4, 3, h=eh):
                st = np.array(st, float)
                if axis == "x": engrave_lines.append(np.column_stack([st[:,0], np.full(len(st), face), st[:,1]]))
                else:           engrave_lines.append(np.column_stack([np.full(len(st), face), st[:,0], st[:,1]]))
            if axis == "x":
                pm.vertices = np.column_stack([V[:,0], V[:,2]+pos-a.thickness/2, V[:,1]])
            else:
                pm.vertices = np.column_stack([V[:,2]+pos-a.thickness/2, V[:,0], V[:,1]])
            pm.visual.vertex_colors = pcolor(kc, axis == "x"); kc += 1
            pm.fix_normals(); plates.append(pm)
            named_pieces.append((label, pm.copy(), axis == "x"))   # für Zusammenbau-Finder
        for (li, lv, ps, hh) in stackdata:          # Stack-Lagen als flache Platten bei z=lv
            for pm2 in ps:
                if len(pm2) < 4: continue
                pg = Polygon(pm2)
                if not pg.is_valid: pg = pg.buffer(0)
                if pg.is_empty or pg.area < 1: continue
                sm = _extrude(pg, a.thickness)
                if sm is None: continue
                sm.apply_translation([0, 0, lv]); sm.visual.vertex_colors = [190,95,120,255]
                plates.append(sm)
        write_html(f"{a.out}/_assembled.html", _tm.util.concatenate(plates), engrave_lines)
        # Relief-Oberfläche als Kontext fürs Zusammenbau-Tool (das „geile Relief" daneben)
        try:
            raw = zoom(win - win_min, zf, order=1) if zf > 1 else (win - win_min)
            Hf_rel = gaussian_filter(raw, 0.5) * a.nscale * a.vscale + a.base   # FEINE Topografie (volle Detailtiefe, NICHT die grobe Rippen-Glättung)
            st = 1; Zs = Hf_rel[::st, ::st]; rny, rnx = Zs.shape
            rxs = np.arange(rnx)*cell*st; rys = np.arange(rny)*cell*st
            RX, RY = np.meshgrid(rxs, rys)
            RV = np.column_stack([RX.ravel(), RY.ravel(), Zs.ravel()]); RF = []
            for j in range(rny-1):
                for i in range(rnx-1):
                    aa = j*rnx+i; RF += [[aa, aa+rnx, aa+rnx+1], [aa, aa+rnx+1, aa+1]]
            relief_mesh = _tm.Trimesh(RV, np.array(RF), process=False)
        except Exception:
            relief_mesh = None
        # Einhäng-Platten (flache Bänke an Steilkanten) als eigene Ebene in den Viewer legen
        extra_meshes = []
        try:
            import insert_plates_auto as _ipa
            # ALTE segment_planes-„PLATTEN" (Facetten-Gewirr) ENTFERNT — ersetzt durch die guten
            # 📐 Flächen (manmade_edges: flach eben + steile Wände per Grid-Clip).
            # Tunnel-Teile als 3D-Ebene: Gleisbett-Band entlang der Trasse + einfache Portal-Galerie-Box
            if track:
                _cl = np.array([[p[0], p[1]] for p in track]); _zt = np.array([p[2] for p in track])
                _dd = np.gradient(_cl, axis=0); _tt = _dd / np.maximum(np.hypot(_dd[:, 0], _dd[:, 1])[:, None], 1e-9)
                _nn = np.column_stack([-_tt[:, 1], _tt[:, 0]]); _bw = CLEAR_W * 0.5
                _L = _cl + _nn * _bw / 2; _R = _cl - _nn * _bw / 2
                _TV = []; _TF = []
                for i in range(len(track)):
                    _TV.append([_L[i, 0], _L[i, 1], _zt[i] + 0.3]); _TV.append([_R[i, 0], _R[i, 1], _zt[i] + 0.3])
                for i in range(len(track) - 1):
                    _aa = 2 * i; _TF += [[_aa, _aa + 1, _aa + 2], [_aa + 1, _aa + 3, _aa + 2]]
                extra_meshes.append(("TUNNEL_gleisbett", _tm.Trimesh(np.array(_TV), np.array(_TF, int), process=False), [70, 70, 70, 255]))
                # EINSCHNITT-PLATTE = flach<->steil-Grenze am Trassen-Korridor (gerade Kanten, zuverlässig)
                try:
                    _tcp = _ipa.einschnitt_corridor_poly(Hf, cell, track)
                except Exception:
                    _tcp = None
                if _tcp is None:
                    _tcp = _ipa.tunnel_cut_from_track(Hf, cell, track)   # Fallback
                if _tcp is not None and len(_tcp) >= 4:
                    # DECKPLATTE = EBENE Platte (laser-cutbar): Ebene an die RIM-Höhen des Einschnitt-
                    # Polygons gefittet (die Oberkanten der Einschnitt-Wände = scharfe Kanten), dann das
                    # GANZE Polygon via earcut trianguliert -> reicht bis an die scharfen Kanten (kein
                    # Grid-Clip-Erosionsrand mehr, nicht mehr 'an den Ecken weggeschmolzen'), und flach
                    # statt ans Gelände drapiert (bridgt die Rinne als Deckel statt reinzuhängen).
                    try:
                        import trimesh.creation as _tmc
                        from shapely.geometry import Polygon as _Poly
                        _rim = _tcp[:-1] if np.allclose(_tcp[0], _tcp[-1]) else _tcp
                        _ny, _nx = Hf.shape
                        _rz = np.array([float(Hf[min(int(_y/cell), _ny-1), min(int(_x/cell), _nx-1)])
                                        for _x, _y in _rim[:, :2]])
                        _A = np.column_stack([_rim[:, 0], _rim[:, 1], np.ones(len(_rim))])
                        _pc, *_ = np.linalg.lstsq(_A, _rz, rcond=None)          # Deck-Ebene aus den Rim-Höhen
                        _v2, _ff = _tmc.triangulate_polygon(_Poly(_rim[:, :2]), engine="earcut")
                        if _v2 is not None and len(_ff):
                            _zz = _pc[0]*_v2[:, 0] + _pc[1]*_v2[:, 1] + _pc[2] + 1.5
                            _Vd = np.column_stack([_v2[:, 0], _v2[:, 1], _zz])
                            extra_meshes.append(("TUNNEL_deckplatte",
                                _tm.Trimesh(_Vd, np.array(_ff, int), process=False), [0, 210, 255, 255]))
                    except Exception:
                        pass
                # Felssturzschutz-GALERIE: zwei SENKRECHTE Seitenwände + DACH entlang der Trasse (nicht nur Boden)
                _h = CLEAR_H * 0.5
                _WV = []; _WF = []
                for i in range(len(track)):
                    _z0 = _zt[i] + 0.3; _z1 = _z0 + _h
                    _WV += [[_L[i, 0], _L[i, 1], _z0], [_L[i, 0], _L[i, 1], _z1],
                            [_R[i, 0], _R[i, 1], _z0], [_R[i, 0], _R[i, 1], _z1]]
                for i in range(len(track) - 1):
                    if not (track[i][3] > 0.5 and track[i + 1][3] > 0.5):           # Galerie NUR über Tunnel-Abschnitt, nicht die offene Strecke
                        continue
                    _b = 4 * i
                    _WF += [[_b, _b + 1, _b + 5], [_b, _b + 5, _b + 4]]              # linke Wand
                    _WF += [[_b + 2, _b + 6, _b + 7], [_b + 2, _b + 7, _b + 3]]      # rechte Wand
                    _WF += [[_b + 1, _b + 3, _b + 7], [_b + 1, _b + 7, _b + 5]]      # Dach
                extra_meshes.append(("TUNNEL_galerie", _tm.Trimesh(np.array(_WV), np.array(_WF, int), process=False), [255, 90, 40, 255]))
        except Exception:
            extra_meshes = []
        # MENSCHGEMACHT-LAYER: flache + steile ebene Flächen (scharf berandet) + scharfe Kanten,
        # auf echte Geländehöhe drapiert (kein Überschießen). Schaltbar über 📐 Flächen.
        overlay_edges = []
        try:
            import manmade_edges as _mm
            # Detektor braucht LEICHT geglättetes Hf (scharfe Kanten); die Rippen nutzen smooth=4.
            # Deckungsgleich aufbauen (gleicher Flip/Maßstab), nur smooth=0.4:
            _wd = dem_full[a.r0:a.r1, a.c0:a.c1].astype(float)
            _wd = np.where(_wd < -1000, np.nan, _wd)
            if np.isnan(_wd).any(): _wd = np.where(np.isnan(_wd), np.nanmin(_wd), _wd)
            _wd = _wd[::-1]
            _reld = gaussian_filter((_wd - float(_wd.min())), 0.4)
            _Hfd = _reld * a.nscale * a.vscale + a.base
            _NY2, _NX2 = Hf.shape
            _zc = lambda x, y: float(Hf[min(int(y/cell), _NY2-1), min(int(x/cell), _NX2-1)])
            # EBENE PLATTEN (flach/schräg) = DIESELBE Mechanik wie die geschnittenen Einhäng-Platten
            # (insert_plates_auto): segment_planes -> planare Facetten an den Bruchkanten getrennt,
            # fit_plane_mask -> ECHTE EBENE, mask_contour_mm -> echte (konkav-fähige) Kontur die der
            # Kante folgt. Jede Platte wird auf ihre gefittete EBENE trianguliert => WIRKLICH FLACH
            # (laser-cutbar, in die Rippen integrierbar). Eine gekrümmte Fläche zerfällt dabei in
            # mehrere ebene Facetten — anders ist flaches Sperrholz nicht abbildbar.
            import insert_plates_auto as _ipa
            import trimesh.creation as _tmc
            from shapely.geometry import Polygon as _Poly
            _facets = _ipa.segment_planes(_Hfd, cell, 2.5, 12.0, 150.0, 45.0)
            _nf = 0
            for _k, _fm in enumerate(_facets):
                _aa, _bb, _cc, _frms = _ipa.fit_plane_mask(_Hfd, cell, _fm)
                _cont = _ipa.mask_contour_mm(_fm, cell, 2.5)
                if _cont is None or len(_cont) < 4:
                    continue
                try:
                    _v2, _ff = _tmc.triangulate_polygon(_Poly(_cont), engine="earcut")
                except Exception:
                    continue
                if _v2 is None or not len(_ff):
                    continue
                _z = _aa*_v2[:, 0] + _bb*_v2[:, 1] + _cc + 0.5          # auf die gefittete EBENE -> wirklich flach
                _V3 = np.column_stack([_v2[:, 0], _v2[:, 1], _z])
                extra_meshes.append((f"FLAECHE{_k}", _tm.Trimesh(_V3, np.array(_ff, int), process=False), [60, 150, 230, 255]))
                _nf += 1
            # STEILE WÄNDE weiter über detect_manmade (plan-gefittetes Polygon = saubere Wandplatte):
            _surf, _edg, _c2 = _mm.detect_manmade(_Hfd, cell)
            def _proj(x, y, _c):
                # Geländepunkt ORTHOGONAL auf die gefittete Ebene -> liegt EXAKT drauf (eben, kein Spike)
                _z0 = _c[0]*x + _c[1]*y + _c[2]; _n2 = _c[0]*_c[0] + _c[1]*_c[1] + 1.0
                _t = (_zc(x, y) - _z0) / _n2
                _px = x + _c[0]*_t; _py = y + _c[1]*_t
                return _px, _py, _c[0]*_px + _c[1]*_py + _c[2]
            _nw = 0
            for _k, (_p, _coef, _rms, _ps) in enumerate(_surf):
                if _ps < 45:                               # flach kommt jetzt aus den Grid-Clip-Bänken
                    continue
                _V = np.array([[*_proj(float(x), float(y), _coef)[:2], _proj(float(x), float(y), _coef)[2] + 0.6] for x, y in _p])
                _F = np.array([[0, i, i + 1] for i in range(1, len(_p) - 1)])
                extra_meshes.append((f"FLAECHE_WAND{_k}", _tm.Trimesh(_V, _F, process=False), [240, 140, 30, 255]))
                _nw += 1
            for (x0, y0, x1, y1) in (edge_segs or _edg):     # Ridge/Hysterese-Kanten (Fallback: LSD)
                overlay_edges.append([[float(x0), float(y0), _zc(x0, y0) + 1.0],
                                      [float(x1), float(y1), _zc(x1, y1) + 1.0]])
            # B4: die KANTEN-LINEALE (mit Halb-Überblattungs-Schlitzen, oben in main gebaut) in 3D,
            # entlang ihrer Kante platziert (beliebige Richtung). Die Bodenschlitze stecken über die
            # X/Y-Rippen; die Oberkante = feines Relief = die scharfe Kante.
            _nk = 0
            for (_knm, _kpoly, (_x0, _y0, _x1, _y1)) in edge_rulers:
                _Lk = float(np.hypot(_x1 - _x0, _y1 - _y0))
                if _Lk < 1e-6: continue
                _dxk, _dyk = (_x1 - _x0)/_Lk, (_y1 - _y0)/_Lk
                _nxk, _nyk = -_dyk, _dxk                               # Dicke senkrecht zur Kante
                try:
                    _pgk = _Poly(_kpoly)
                    if not _pgk.is_valid: _pgk = _pgk.buffer(0)
                    _mk = _tmc.extrude_polygon(_pgk, a.thickness)
                    _Vk = _mk.vertices
                    _sk = _Vk[:, 0]; _zk = _Vk[:, 1]; _wk = _Vk[:, 2] - a.thickness/2
                    _mk.vertices = np.column_stack([_x0 + _dxk*_sk + _nxk*_wk,
                                                    _y0 + _dyk*_sk + _nyk*_wk, _zk])
                    extra_meshes.append((f"KANTE{_nk}", _mk, [255, 20, 147, 255]))
                    _nk += 1
                except Exception:
                    continue
            print(f"Flächen-Layer: {_nf} EBENE Platten + {_nw} steile Wände + {_nk} Kanten-Lineale (3D)")
        except Exception as _e:
            print("Menschgemacht-Layer übersprungen:", _e)
        write_assembly_html(f"{a.out}/_zusammenbau.html", named_pieces, engrave_lines, relief_mesh, extra_meshes, overlay_edges)
        html_ok = True
    except Exception as e:
        html_ok = False; print("HTML-Viewer übersprungen:", e)

    ap_out = os.path.abspath(a.out)
    print(f"Vorschau -> {a.out}/_3d_assembled.png (zusammengesteckt) + _cut_layout.png (geschnitten)")
    if html_ok: print(f"3D-HTML (drehbar) -> {ap_out}/_assembled.html")
    print(f"\n== ALLE DATEIEN: {ap_out}/ ==")


if __name__ == "__main__":
    main()

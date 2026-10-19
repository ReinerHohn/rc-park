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


def write_assembly_html(fn, named_pieces):
    """Interaktiver ZUSAMMENBAU-Finder: Teil-Nr eintippen -> Teil leuchtet rot, Rest blass.
    named_pieces = [(label, mesh, is_x)] mit label = Gravur ('X0a Y123')."""
    import base64, trimesh as _tm
    sc = _tm.Scene()
    for (label, mesh, is_x) in named_pieces:
        sc.add_geometry(mesh, geom_name=label, node_name=label)
    b64 = base64.b64encode(sc.export(file_type="glb")).decode()
    HTML = '''<!doctype html><html><head><meta charset=utf8><title>Zusammenbau-Finder</title>
<style>body{margin:0;background:#dde6ef;font-family:sans-serif}
#bar{position:fixed;top:0;left:0;right:0;background:#111e;color:#fff;padding:8px 12px;z-index:10}
#bar input{font-size:18px;padding:5px 9px;width:170px}#bar button{font-size:15px;padding:5px 11px;margin-left:4px}
#info{margin-left:12px;font-size:15px}
#tip{position:fixed;bottom:8px;left:8px;background:#000a;color:#fff;padding:6px 10px;border-radius:6px;font-size:12px}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body>
<div id=bar>🔎 Teil-Nr: <input id=q placeholder="z.B. X0a oder 123" autofocus>
<button onclick=find()>finden</button><button onclick=clr()>alle</button><span id=info></span></div>
<div id=tip>Maus drehen · Rad zoom · Teil anklicken markiert es · Gesuchtes leuchtet ROT, Rest blass</div>
<script type=module>
import*as THREE from'three';import{OrbitControls}from'three/addons/controls/OrbitControls.js';import{GLTFLoader}from'three/addons/loaders/GLTFLoader.js';
const sc=new THREE.Scene();sc.background=new THREE.Color(0xdde6ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,99999);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.8));sc.add(new THREE.HemisphereLight(0xffffff,0x556,1.0));
const d1=new THREE.DirectionalLight(0xffffff,1.1);d1.position.set(200,-300,500);sc.add(d1);
let meshes=[];const RAY=new THREE.Raycaster(),M=new THREE.Vector2();
new GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{
 const root=g.scene,bx=new THREE.Box3().setFromObject(root),c=bx.getCenter(new THREE.Vector3()),s=bx.getSize(new THREE.Vector3());
 root.position.sub(c);sc.add(root);
 root.traverse(o=>{if(o.isMesh){const warm=(o.name||"").toUpperCase().startsWith("X");
  o.material=new THREE.MeshStandardMaterial({color:warm?0xc8a56a:0x6ea07e,roughness:1,side:THREE.DoubleSide,flatShading:true,transparent:true,opacity:1});
  o.userData.base=o.material.color.getHex();meshes.push(o);}});
 const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.9,-d*1.2,d*0.8);cam.lookAt(0,0,0);ct.update();});
function apply(q){q=(q||"").toUpperCase().trim();let n=0,hit=[];
 meshes.forEach(o=>{if(!q){o.material.color.setHex(o.userData.base);o.material.opacity=1;o.material.emissive.setHex(0);return;}
  if((o.name||"").toUpperCase().includes(q)){o.material.color.setHex(0xff2020);o.material.emissive.setHex(0x661111);o.material.opacity=1;n++;hit.push(o.name);}
  else{o.material.color.setHex(0x999999);o.material.emissive.setHex(0);o.material.opacity=0.1;}});
 document.getElementById("info").textContent=q?(n?("→ "+n+" Teil(e): "+hit.slice(0,6).join(", ")+(hit.length>6?"…":"")):("„"+q+"“ nicht gefunden")):"";}
window.find=()=>apply(document.getElementById("q").value);
window.clr=()=>{document.getElementById("q").value="";apply("");};
document.getElementById("q").addEventListener("input",e=>apply(e.target.value));
addEventListener("click",e=>{if(e.target.tagName==="INPUT"||e.target.tagName==="BUTTON")return;
 M.x=(e.clientX/innerWidth)*2-1;M.y=-(e.clientY/innerHeight)*2+1;RAY.setFromCamera(M,cam);
 const h=RAY.intersectObjects(meshes,false);if(h.length){document.getElementById("q").value=h[0].object.name;apply(h[0].object.name);}});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function x(){requestAnimationFrame(x);ct.update();rn.render(sc,cam)})();
</script></body></html>'''.replace("%B64%", b64)
    open(fn, "w").write(HTML)


def rib(L, hs, cross, slotw, from_top, bs=None):
    """Rippen-Polygon. L=Länge, hs(s)->Oberkante, bs(s)->Unterkante (None=0=bis Boden),
    cross=[(pos,hmid)] Kreuzungs-Schlitze, Schlitz von oben (from_top) oder unten."""
    if bs is None: bs = lambda s: 0.0
    S = np.arange(0, L + 0.5, 1.0)
    pts = [(0.0, bs(0.0))]
    # --- Unterkante links->rechts (folgt bs; Schlitze nach OBEN falls not from_top) ---
    if from_top:
        for s in S[1:]:
            pts.append((float(s), bs(float(s))))
    else:
        crs = sorted(cross)
        for s in S[1:]:
            su = float(s)
            for (pos, hmid) in crs:
                if su - 1.0 <= pos < su:
                    pts += [(pos - slotw/2, bs(pos)), (pos - slotw/2, hmid),
                            (pos + slotw/2, hmid), (pos + slotw/2, bs(pos))]
            pts.append((su, bs(su)))
    if pts[-1][0] < L - 1e-6: pts.append((L, bs(L)))
    # --- rechte Kante hoch ---
    pts.append((L, hs(L)))
    # --- Oberkante rechts->links (folgt hs; Schlitze nach UNTEN falls from_top) ---
    if from_top:
        for s in S[::-1]:
            for (pos, hmid) in sorted(cross, reverse=True):
                if s <= pos < s + 1.0:
                    pts += [(pos + slotw/2, hs(pos)), (pos + slotw/2, hmid),
                            (pos - slotw/2, hmid), (pos - slotw/2, hs(pos))]
            pts.append((float(s), hs(float(s))))
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


def rib_positions(Hf, cell, nx, ny, min_gap, max_gap=None, uniform=False):
    """DIE eine Quelle der Rippen-X/Y-Positionen — genutzt von Gerüst UND Deckplatten,
    damit die Platten exakt zwischen die Rippen passen. Dichte folgt der SCHÄRFE:
    Detail je Spalte = 0.5*Summe (breite Krümmung) + 1.0*Max (eine scharfe Kante zieht
    die Dichte hoch, geht nicht im Spaltenmittel unter)."""
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
    xpos = adaptive_pos(sharp(cx, 0), nx, Wx*0.06, Wx*0.94, cell, min_gap, max_gap)
    ypos = adaptive_pos(sharp(cy, 1), ny, Dy*0.06, Dy*0.94, cell, min_gap, max_gap)
    return xpos, ypos


def choose_seams(cross_s, L, maxlen, minwid):
    """Naht-Positionen (entlang s) wählen: möglichst gleichmäßig alle <=maxlen, aber IMMER
    in eine Lücke zwischen zwei Kreuzungen (nie auf einen Steck-Schlitz), breit genug für Zinken."""
    cs = sorted(c for c in cross_s if 1 < c < L-1)
    bnds = [0.0] + cs + [float(L)]
    cand = [(bnds[i]+bnds[i+1])/2 for i in range(len(bnds)-1)
            if (bnds[i+1]-bnds[i]) >= minwid and 0.12*L < (bnds[i]+bnds[i+1])/2 < 0.88*L]
    if not cand: return []
    n = max(1, int(np.ceil(L/maxlen))); seams = []
    for i in range(1, n):
        sc = min(cand, key=lambda c: abs(c - L*i/n))
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
        geoms = list(gg.geoms) if gg.geom_type == "MultiPolygon" else [gg]
        best = max(geoms, key=lambda h: h.area) if geoms else None    # Hauptstück (Slivers verwerfen)
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
    ap.add_argument("--split-len", type=float, default=0.0, help="lange Rippen in Puzzle-Stücke <= N mm mit Fingerzinken teilen (spart Verschnitt); 0=aus")
    ap.add_argument("--finger", type=float, default=12.0, help="Fingerzinken-Höhe (mm) entlang der Naht")
    ap.add_argument("--thickness", type=float, default=3.0)
    ap.add_argument("--rib-depth", type=float, default=0.0, help="Rippen als konstant-tiefes Band (mm unter Oberkante) statt bis Boden -> spart Material; 0=bis Boden")
    ap.add_argument("--base", type=float, default=12.0, help="Sockel mm: Gelände anheben, damit Rippen am Talboden nicht auf 0 pinchen (gegen 'schwebende' Teile)")
    ap.add_argument("--fit", type=float, default=0.15, help="Schlitz-Spiel mm")
    ap.add_argument("--vscale", type=float, default=1.0, help="Höhen-Überhöhung (1=true-N)")
    ap.add_argument("--trans-frac", type=float, default=0.85,
                    help="Übergangshöhe als Anteil der Max-Höhe: Gitter bis dahin, DÜNNER Kontur-Stack drüber (1.0=nur Gitter)")
    ap.add_argument("--min-seg", type=float, default=1.0)
    ap.add_argument("--dowel-d", type=float, default=3.2)
    ap.add_argument("--smooth", type=float, default=4.0)
    ap.add_argument("--bed-x", type=float, default=410); ap.add_argument("--bed-y", type=float, default=400)
    ap.add_argument("--tunnel", action="store_true", help="Bahn-Lichtraum (30x36mm) in die Rippen schneiden: Tunnel=gedeckelt, offen=Einschnitt")
    ap.add_argument("--track", default="", help="ECHTE Trasse als .npy (Zeilen mx,my,mz,is_tunnel in Modell-mm, z.B. aus OSM); leer=keine")
    ap.add_argument("--tunnel-drop", type=float, default=0.0, help="Tunnel-Gleis um N mm tiefer legen (unters Dach statt drauf)")
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--feed", type=float, default=400); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=20)
    ap.add_argument("--out", default="/tmp/crate")
    a = ap.parse_args()

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
    CLEAR_W, CLEAR_H = 30.0, 36.0; tun_pts = []; track = []
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
                if p[3]:                                       # Tunnel: geschlossenes Loch
                    cuts.append(_rect2(s, z-4, z+CLEAR_H, w))
                else:                                          # offen: Einschnitt bis Oberkante
                    top = (Hc(s, pos) if axis=="x" else Hc(pos, s)) + 6
                    cuts.append(_rect2(s, z-4, max(top, z+CLEAR_H), w))
        return cuts

    mg = a.max_gap if a.max_gap > 0 else None
    xpos, ypos = rib_positions(Hf, cell, a.nx, a.ny, a.min_gap, mg, a.uniform)
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
        eng = glyph_strokes(label, poly[:,0].min()+4, 3, h=min(12, max(6, Hf.max()*0.12)))
        svg_write(f"{a.out}/{name}.svg", cuts, [], [], eng, 0)
        if a.gcode:
            gcode_write(f"{a.out}/{name}.gcode", cuts, [], [], eng, 0,
                        a.feed, a.power, a.passes, a.eng_power)
        bb = (np.ptp(poly[:,0]), np.ptp(poly[:,1])); made.append(name)
        if bb[0] > a.bed_x or bb[1] > a.bed_y: oversize.append((name, bb))
        return bb

    ribdata = []
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

    def add_rib(prefix, coordlab, poly, axis, pos, th, L, cross_s):
        """emittiert eine Rippe; teilt sie bei --split-len in verzinkte Puzzle-Stücke."""
        seams = (choose_seams(cross_s, L, a.split_len, 2*fdepth+slotw+4)
                 if a.split_len > 0 and np.ptp(poly[:, 0]) > a.split_len else [])
        if not seams:
            bb = emit(f"rib{prefix}", poly, f"{prefix} {coordlab}", th)
            ribdata.append((prefix, poly, axis, pos, th))
            manifest.append(f"  {prefix}: {bb[0]:.0f}x{bb[1]:.0f} mm" + (f"  (+{len(th)} Tunnel)" if th else ""))
            return
        segs = finger_split(poly, seams, fdepth, a.finger)
        for si, sp in enumerate(segs):
            lt = chr(97+si); hh = clip_holes(sp, th)
            bb = emit(f"rib{prefix}{lt}", sp, f"{prefix}{lt} {coordlab}", hh)
            ribdata.append((f"{prefix}{lt}", sp, axis, pos, hh))
            manifest.append(f"  {prefix}{lt}: {bb[0]:.0f}x{bb[1]:.0f} mm (Zinken)" + (f" (+{len(hh)} Tunnel)" if hh else ""))

    for j, yr in enumerate(ypos):     # X-Rippen: Schlitz OBEN, Kreuzung an xpos (Höhe geklemmt auf z_t)
        cross = [(xp, (Hbot(xp, yr)+Htop(xp, yr))/2) for xp in xpos]
        bsf = (lambda s, yr=yr: Hbot(s, yr)) if band else None
        poly = np.array(rib(Wx, lambda s, yr=yr: Htop(s, yr), cross, slotw, True, bsf), float)
        add_rib(f"X{j}", f"Y{yr:.0f}", poly, "x", yr, tunnel_holes("x", yr), Wx, list(xpos))
    for i, xr in enumerate(xpos):     # Y-Rippen: Schlitz UNTEN, Kreuzung an ypos
        cross = [(yp, (Hbot(xr, yp)+Htop(xr, yp))/2) for yp in ypos]
        bsf = (lambda s, xr=xr: Hbot(xr, s)) if band else None
        poly = np.array(rib(Dy, lambda s, xr=xr: Htop(xr, s), cross, slotw, False, bsf), float)
        add_rib(f"Y{i}", f"X{xr:.0f}", poly, "y", xr, tunnel_holes("y", xr), Dy, list(ypos))

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
        eh = min(12, max(6, Hf.max()*0.12))        # Gravur-Texthöhe wie beim Laser
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
        write_assembly_html(f"{a.out}/_zusammenbau.html", named_pieces)
        html_ok = True
    except Exception as e:
        html_ok = False; print("HTML-Viewer übersprungen:", e)

    ap_out = os.path.abspath(a.out)
    print(f"Vorschau -> {a.out}/_3d_assembled.png (zusammengesteckt) + _cut_layout.png (geschnitten)")
    if html_ok: print(f"3D-HTML (drehbar) -> {ap_out}/_assembled.html")
    print(f"\n== ALLE DATEIEN: {ap_out}/ ==")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""ravenna_viadukt.py — Ravennaviadukt (Höllentalbahn) OHNE Scan, rein datengetrieben.

Daten (Wikipedia/outdooractive): 224 m lang, 36 m hoch, 9 halbrunde Bögen à 20 m
Spannweite, Betonbögen mit Forbach-Granit verkleidet, 1926/27. Einzige beheizbare
Eisenbahnbrücke Deutschlands. Kreuzt die Ravennaschlucht (Hinterzarten–Breitnau).

Methode = exakt wie linach_bogenmauer.py: Ansicht als POLYGON MIT BOGEN-LÖCHERN
(shapely) extrudieren → echte offene Bögen. Hier: hohe schlanke Pfeiler, große
Rundbögen bis fast zur Talsohle, Bahn-Deck + Brüstung oben.

  modelle/ravenna/ravenna_viadukt.stl
  modelle/ravenna/ravenna.html          (interaktiv, three.js)
  daten/ravenna/rv_face.png             (face-on, für validate_bauwerk.py)
"""
import os, base64, numpy as np, trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union
from trimesh.creation import extrude_polygon
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

# ===== Maße (m) — echte Daten (per CLI überschreibbar für generische Pipeline) =
import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--L", type=float, default=224.0); _ap.add_argument("--H", type=float, default=36.0)
_ap.add_argument("--n", type=int, default=9); _ap.add_argument("--span", type=float, default=20.0)
_ap.add_argument("--deck-w", type=float, default=6.0)
_ap.add_argument("--stl", default="modelle/ravenna/ravenna_viadukt.stl")
_ap.add_argument("--face", default="daten/ravenna/rv_face.png")
_ap.add_argument("--profile", default="", help="gemessenes Intrados-Profil (JSON) statt Halbkreis")
_a = _ap.parse_args()
PROF_FN = None
if _a.profile:
    import arch_profile as _apr
    _th, _dl = _apr.load_profile(_a.profile)
    PROF_FN = _apr.profile_fn(_th, _dl)
    print(f"Bogenform: gemessenes Profil {_a.profile} (echte Kurve, kein Halbkreis)")
L, H = _a.L, _a.H
N = _a.n;  SPAN = _a.span
P = L / N                           # Feldteilung
PIER = P - SPAN                     # Pfeilerbreite
R = SPAN / 2                        # Rundbogen-Radius
DEPTH = _a.deck_w                   # Viadukt-Breite
Z_SPRING = H * 0.61                 # Kämpferhöhe (Pfeilerkopf) ~0,61·H
DECK_T = 3.0                        # Deck-Dicke
BATTER = 0.04                       # Pfeiler leicht geböscht (unten breiter)
STL, FACE = _a.stl, _a.face
OUT = os.path.dirname(STL) or "."; os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.dirname(FACE) or ".", exist_ok=True)


def round_arch(xc, half_w, z_lo, z_spring):
    """Rundbogen: senkrechte Leibung z_lo..z_spring, Halbkreis r=half_w oben.
    Leicht geböscht (unten etwas schmaler Öffnung = breitere Pfeilerfüße)."""
    bw = half_w - BATTER * (z_spring - z_lo)        # Öffnung am Fuß schmaler
    pts = [(xc-bw, z_lo), (xc-half_w, z_spring)]
    for a in np.linspace(np.pi, 0, 64):
        r = half_w * (1.0 + PROF_FN(a)) if PROF_FN else half_w   # echte Kurve statt Halbkreis
        pts.append((xc + r*np.cos(a), z_spring + r*np.sin(a)))
    pts.append((xc+bw, z_lo))
    return Polygon(pts)


# ---- Ansicht (x,z) mit 9 Bogen-Löchern, dann zu 3D extrudieren -------------
crown = Z_SPRING + R                                # 32 m
body_top = crown + 1.0                              # Spandrill bis knapp unters Deck
outer = Polygon([(-L/2, 0), (L/2, 0), (L/2, body_top), (-L/2, body_top)])
holes = [round_arch(-L/2 + (k+0.5)*P, R, 0.0, Z_SPRING) for k in range(N)]
panel2d = outer.difference(unary_union(holes))
body = extrude_polygon(panel2d, DEPTH)
body.vertices = body.vertices[:, [0, 2, 1]]         # (x,z,dicke) -> (x, y=dicke, z)

parts = [body]

def box(x0, x1, y0, y1, z0, z1):
    return trimesh.creation.box(bounds=[[x0, y0, z0], [x1, y1, z1]])

# ---- Deck (Fahrbahn) + Brüstung + leichte Kragplatte -----------------------
parts.append(box(-L/2, L/2, -0.6, DEPTH+0.6, body_top, body_top+DECK_T))       # Deck + Kragplatte
parts.append(box(-L/2, L/2, -0.6, -0.3, body_top+DECK_T, body_top+DECK_T+1.3)) # Brüstung A
parts.append(box(-L/2, L/2, DEPTH+0.3, DEPTH+0.6, body_top+DECK_T, body_top+DECK_T+1.3))  # Brüstung B

# ---- Gesims-Band auf Kämpferhöhe (typisch Steinviadukt) --------------------
parts.append(box(-L/2, L/2, -0.4, DEPTH+0.4, Z_SPRING-0.4, Z_SPRING+0.1))

dam = trimesh.util.concatenate(parts)
trimesh.repair.fix_normals(dam)
dam.export(STL)
print(f"Viadukt: {len(dam.vertices)}V/{len(dam.faces)}F  "
      f"bbox {dam.extents.round(1)} m  watertight={dam.is_watertight}")

# ===== interaktives 3D-HTML (three.js, GLB eingebettet) =====================
dam.visual.vertex_colors = [150, 146, 138, 255]     # Granit-grau
b64 = base64.b64encode(trimesh.Scene(dam).export(file_type="glb")).decode()
HTML = f"""<!doctype html><meta charset=utf-8><title>Ravennaviadukt 3D</title>
<style>body{{margin:0;background:#0c1116;font-family:system-ui;color:#cdd}}
#i{{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;text-shadow:0 1px 3px #000;line-height:1.4}}</style>
<div id=i><b>Ravennaviadukt</b> — 224×36 m, 9 Bögen à 20 m (Höllentalbahn)<br>
<span style=color:#8cf>Maus: drehen · Rad: zoom · rechts: verschieben</span></div>
<script type="importmap">{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}}}</script>
<script type=module>
import*as T from"three";import{{OrbitControls}}from"three/addons/controls/OrbitControls.js";
import{{GLTFLoader}}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0x0c1116);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,5000);
const rn=new T.WebGLRenderer({{antialias:true}});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x334455,0.95));
const sun=new T.DirectionalLight(0xfff2e0,1.15);sun.position.set(-120,120,160);sc.add(sun);
const b=atob("{b64}");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
new GLTFLoader().parse(ar.buffer,"",g=>{{
 const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const bb=new T.Box3().setFromObject(o),c=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(c);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.5,d*0.35,d*0.9);cam.lookAt(0,0,0);ct.update();
}},e=>{{document.getElementById("i").innerHTML+="<br><span style=color:#f88>LOAD-FEHLER "+e+"</span>";}});
addEventListener("resize",()=>{{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);}});
(function a(){{requestAnimationFrame(a);ct.update();rn.render(sc,cam);}})();
</script>"""
open(f"{OUT}/ravenna.html", "w").write(HTML)
print(f"HTML -> {OUT}/ravenna.html ({len(HTML)//1024} kB)")

# ===== ortho face-Render (für Validator + Foto-Vergleich) ===================
BG = (0.95, 0.96, 0.98)
def render_face(fn):
    tris = dam.triangles; ymean = tris[:, :, 1].mean(axis=1)
    order = np.argsort(-ymean); n = dam.face_normals
    shade = 0.45 + 0.55*np.clip(-n[order][:, 1], 0, 1)
    polys = [t[:, [0, 2]] for t in tris[order]]
    cols = [(0.60*s, 0.58*s, 0.55*s) for s in shade]
    fig, ax = plt.subplots(figsize=(12, 2.6)); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="none"))
    ax.set_xlim(-L/2-8, L/2+8); ax.set_ylim(-2, H+3); ax.set_aspect("equal"); ax.axis("off")
    fig.savefig(fn, dpi=130, facecolor=BG, bbox_inches="tight", pad_inches=0.05); plt.close(fig)
    print("render ->", fn)
render_face(FACE)

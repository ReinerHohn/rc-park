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
import os, sys, json, base64, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arch_profile as apr
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
_ap.add_argument("--profile", default="", help="gemessenes Intrados-Profil (JSON) ueberschreibt Form")
# KOMPLETTE FORM (datengetrieben, Bautechnik 1928): Korbbogen-Stich + Pfeiler-Anzug
_ap.add_argument("--rise", type=float, default=0.0, help="Korbbogen-Stich m (0/=span/2 -> Halbkreis; Ravenna ist laut Foto Halbkreis)")
_ap.add_argument("--haunch", type=float, default=0.5, help="Korbbogen Kaempfer-Radius-Anteil")
_ap.add_argument("--semicircle", action="store_true", help="idealer Halbkreis statt Korbbogen")
_ap.add_argument("--batter", type=float, default=0.05, help="Pfeiler-Anzug laengs (1:20=0.05; 0=senkrecht)")
# Archivolte / Stirnbogen-Ring (Bautechnik 1928): Bogendicke Scheitel 1,0 -> Kaempfer 1,80 m,
# als leicht vorspringendes Band = die "Verdickung unterhalb der Boegen".
_ap.add_argument("--ring-scheitel", type=float, default=1.0, help="Bogendicke am Scheitel (m)")
_ap.add_argument("--ring-kaempfer", type=float, default=1.8, help="Bogendicke am Kaempfer (m)")
_ap.add_argument("--ring-proj", type=float, default=0.45, help="Vorsprung des Stirnbogen-Rings aus der Flaeche (m)")
_ap.add_argument("--ring-skirt", type=float, default=1.6, help="wie weit das Band unter den Kaempfer laeuft (m)")
_ap.add_argument("--no-ring", action="store_true", help="Archivolt-Ring weglassen (alte glatte Version)")
_ap.add_argument("--merge", default="", help="Form halb-automatisch aus Merge-Spec (JSON, Block 'form_maschinell')")
_a = _ap.parse_args()

# --- KOMPLETTE Form halb-automatisch aus der Merge-Spec (CLI-Flags gewinnen) ---
if _a.merge:
    _fm = json.load(open(_a.merge)).get("form_maschinell", {})
    def _given(flag): return any(x == f"--{flag}" or x.startswith(f"--{flag}=") for x in sys.argv[1:])
    for _k in ("L", "H", "n", "span", "deck_w", "rise", "haunch", "batter", "ring_scheitel", "ring_kaempfer"):
        if _k in _fm and not _given(_k.replace("_", "-")):
            setattr(_a, _k, _fm[_k])
    print(f"Form halb-automatisch aus {_a.merge} (form_maschinell)")
L, H = _a.L, _a.H
N = _a.n;  SPAN = _a.span
P = L / N                           # Feldteilung
PIER = P - SPAN                     # Pfeilerbreite
R = SPAN / 2                        # Halbspann (Bezugsradius)
DEPTH = _a.deck_w                   # Viadukt-Breite
Z_SPRING = H * 0.61                 # Kämpferhöhe (Pfeilerkopf) ~0,61·H
DECK_T = 3.0                        # Deck-Dicke
BATTER = _a.batter                  # Pfeiler-Anzug längs (unten breiter)

# ---- Bogenform (die KOMPLETTE Form, generisch): gemessenes Profil > Korbbogen > Halbkreis
PROF_FN = None
if _a.profile:                                                     # 1) echtes Foto-Profil
    _PROF = apr.load_profile(_a.profile)
    print(f"Bogenform: gemessenes Profil {_a.profile} (echte Kurve)")
elif not _a.semicircle and _a.rise > 0 and _a.rise < R - 1e-6:     # 2) Korbbogen (Default)
    _PROF = apr.basket_arch_profile(SPAN, _a.rise, _a.haunch)
    print(f"Bogenform: Korbbogen Stich {_a.rise:.3f} m (Stich/Span {_a.rise/SPAN:.3f}), generisch")
else:                                                              # 3) Halbkreis
    _PROF = None
    print("Bogenform: Halbkreis")
if _PROF is not None:
    PROF_FN = apr.profile_fn(*_PROF)
ARCH_RISE = R * (1.0 + PROF_FN(np.pi/2)) if PROF_FN else R          # echte Scheitelhöhe über Kämpfer
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


# ---- Fassade MIT Deck als EIN extrudiertes Solid → watertight per Konstruktion
# (früher: viele überlappende Boxen konkateniert → 10–14 Körper, NICHT watertight;
#  bewiesen in 2 Runden, dass das Ein-Solid garantiert watertight + saubere Bögen liefert.)
crown = Z_SPRING + ARCH_RISE
deck_top = H                                        # Deck-Oberkante = Bauwerkshöhe (fix, formunabhängig)
body_top = max(deck_top - DECK_T, crown + 0.8)      # Spandrill-Oberkante (Füllung über dem Bogen)
# Außenkontur mit Pfeiler-Anzug: Widerlager unten um BATTER·Z_SPRING breiter (wie die Pfeiler)
ew = BATTER * Z_SPRING
outer = Polygon([(-L/2-ew, 0), (L/2+ew, 0), (L/2, Z_SPRING), (L/2, deck_top),
                 (-L/2, deck_top), (-L/2, Z_SPRING)])
holes = [round_arch(-L/2 + (k+0.5)*P, R, 0.0, Z_SPRING) for k in range(N)]
panel2d = outer.difference(unary_union(holes))
body = extrude_polygon(panel2d, DEPTH)
body.vertices = body.vertices[:, [0, 2, 1]]         # (x,z,dicke) -> (x, y=dicke, z)
body.merge_vertices(); body.fix_normals()

def box(x0, x1, y0, y1, z0, z1):
    return trimesh.creation.box(bounds=[[x0, y0, z0], [x1, y1, z1]])

# ---- Archivolte / Stirnbogen-Ring (die "Verdickung unterhalb der Boegen"): das
#      generische Band kommt aus arch_profile.archivolt_band(); hier nur extrudieren
#      + vorspringend auf Vorder-/Rueckseite legen. Daten: Bautechnik 1928 (1,0->1,80 m).
PROJ = _a.ring_proj

def ring_solid(band2d, y0):
    """2D-Band (x,z) -> vorspringendes Solid an Flaechentiefe y0 (ueberlappt die Stirn)."""
    m = extrude_polygon(band2d, PROJ + 0.05)
    v = m.vertices
    m.vertices = np.column_stack([v[:, 0], v[:, 2] + y0, v[:, 1]])   # (x, tiefe+y0, z)
    m.merge_vertices(); m.fix_normals()
    return m

# ---- Deko (Brüstung + Pfeiler-Gesims) per boolescher UNION; überlappend, damit es
#      verschmilzt. Bleibt die Union nicht watertight → Fallback aufs reine Solid.
extras = [box(-L/2, L/2, -0.3, 0.4, deck_top-0.2, deck_top+1.3),          # Brüstung A (über Deckkante)
          box(-L/2, L/2, DEPTH-0.4, DEPTH+0.3, deck_top-0.2, deck_top+1.3)]  # Brüstung B
for k in range(N + 1):
    xc = -L/2 + k * P                                # Kämpfergesims NUR auf Pfeilern
    extras.append(box(xc - PIER/2 - 0.3, xc + PIER/2 + 0.3, -0.4, DEPTH+0.4,
                      Z_SPRING - 0.4, Z_SPRING + 0.1))
# Archivolt-Ring pro Oeffnung, vorne + hinten (die "Verdickung unterhalb der Boegen")
if not _a.no_ring:
    for k in range(N):
        xc = -L/2 + (k + 0.5) * P
        band = apr.archivolt_band(xc, R, Z_SPRING, d_crown=_a.ring_scheitel,
                                  d_spring=_a.ring_kaempfer, skirt=_a.ring_skirt, prof=_PROF)
        extras.append(ring_solid(band, -PROJ))            # Vorderseite
        extras.append(ring_solid(band, DEPTH - 0.05))     # Rueckseite
try:
    cand = trimesh.boolean.union([body] + extras)
    dam = cand if (cand.is_watertight and cand.body_count == 1) else body
except Exception:
    dam = body                                       # garantiert watertight
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

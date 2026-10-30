#!/usr/bin/env python3
"""viadukt_gelaende.py — Viadukt, der der ECHTEN Trasse + dem GELÄNDE folgt.

Fix für „trifft beide Enden nicht": ein gerader, flacher Viadukt kann zwei
unterschiedlich hohe Schluchtseiten nicht verbinden. Hier:
  * Grundlinie (Pfeilerfüße) = echtes DGM1-Höhenprofil ENTLANG der OSM-Trasse
  * Deck = lineares Trassen-Gefälle zwischen den beiden Trassen-Enden
  * Pfeiler so hoch wie nötig (0 m an den Widerlagern, ~Schluchttiefe in der Mitte)
  * Bögen als Rundbogen-Öffnungen (shapely) im (Weg s, Höhe z)-Schnitt, dann entlang
    der Trasse in UTM extrudiert (folgt auch leichten Kurven)

  python3 tools/viadukt_gelaende.py --dem daten/ravenna/ravenna_dgm1.npy \\
    --dem-origin daten/ravenna/ravenna_dgm1_origin.npy \\
    --track daten/ravenna/viadukt_track.npy --n 9 --out modelle/ravenna/ravenna_viadukt_gel.stl
"""
import argparse, os, sys, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arch_profile as apr
from shapely.geometry import Polygon
from shapely.ops import unary_union
from trimesh.creation import extrude_polygon

ap = argparse.ArgumentParser()
ap.add_argument("--dem", required=True); ap.add_argument("--dem-origin", required=True)
ap.add_argument("--track", required=True, help="UTM-Polyline .npy (E,N)")
ap.add_argument("--dom", default="", help="DOM1-GeoTIFF (+.tfw): echtes Deck aus LiDAR statt DGM-Enden-Gefälle")
ap.add_argument("--n", type=int, default=9, help="Bogen-Anzahl")
ap.add_argument("--rise", type=float, default=0.0, help="Bogen-Stich m (Korbbogen; 0=Halbkreis). Ravenna 5.985")
ap.add_argument("--deck-w", type=float, default=6.0); ap.add_argument("--deck-t", type=float, default=3.0)
ap.add_argument("--pier", type=float, default=5.0, help="Pfeilerbreite m")
ap.add_argument("--batter", type=float, default=0.0, help="Pfeiler-Anzug laengs (1:20=0.05; 0=senkrecht)")
# Archivolt / Stirnbogen-Ring = die "Verdickung unterhalb der Boegen" (generisch, arch_profile)
ap.add_argument("--arch-ring", action="store_true", help="Stirnbogen-Ring (Bogen-Verdickung) anbauen")
ap.add_argument("--ring-scheitel", type=float, default=1.0, help="Bogendicke am Scheitel (m)")
ap.add_argument("--ring-kaempfer", type=float, default=1.8, help="Bogendicke am Kaempfer (m)")
ap.add_argument("--ring-proj", type=float, default=0.45, help="Vorsprung aus der Stirnflaeche (m)")
ap.add_argument("--ring-skirt", type=float, default=1.6, help="Band-Laenge unter den Kaempfer (m)")
ap.add_argument("--out", required=True)
a = ap.parse_args()

A = np.load(a.dem).astype(float); A = np.where(A < -1000, np.nan, A)
E0, N0 = np.load(a.dem_origin); ny, nx = A.shape
def terr(e, n):
    c = int(min(max(e-0.5-E0, 0), nx-1)); r = int(min(max(ny-1-(n-0.5-N0), 0), ny-1)); return A[r, c]

T = np.load(a.track)
seg = np.r_[0, np.cumsum(np.hypot(*np.diff(T, axis=0).T))]; L = seg[-1]
uhat = (T[-1]-T[0]) / np.hypot(*(T[-1]-T[0])); nrm = np.array([-uhat[1], uhat[0]])
def cl(s): return np.array([np.interp(s, seg, T[:, 0]), np.interp(s, seg, T[:, 1])])

ss = np.arange(0, L+0.5, 1.0)
tp = np.array([terr(*cl(s)) for s in ss])                 # Geländeprofil entlang Trasse
z0, z1 = tp[0], tp[-1]
DECK_T = 3.0
if a.dom:                                                 # ECHTES Deck aus LiDAR-DOM
    from PIL import Image; Image.MAX_IMAGE_PIXELS = None
    from scipy.ndimage import uniform_filter1d
    tfw = [float(x) for x in open(a.dom.replace(".tif", ".tfw")).read().split()]
    pA, _, _, pE, pC, pF = tfw
    dom = np.array(Image.open(a.dom)).astype(float)
    def domz(e, n):
        ci = int(round((e-pC)/pA)); ri = int(round((n-pF)/pE))
        return dom[ri, ci] if (0 <= ri < dom.shape[0] and 0 <= ci < dom.shape[1]) else np.nan
    deck_top = np.array([domz(*cl(s)) for s in ss])
    deck_top = uniform_filter1d(np.nan_to_num(deck_top, nan=np.nanmedian(deck_top)), 7)
    base = deck_top                                        # Panel-Oberkante = echtes DOM-Deck
    print(f"DECK aus DOM: {deck_top.min():.1f}..{deck_top.max():.1f} m (Gefälle {deck_top[-1]-deck_top[0]:.1f} m)")
else:
    base = z0 + (z1-z0)*(ss/L)                            # Deck-Unterkante (DGM-Enden-Gefälle)
MINH = 0.4                                                # Mindest-Bauhöhe (Widerlager-Sliver)
topz = np.maximum(base, tp + MINH)                        # Deck immer über Gelände
def under(s): return float(np.interp(s, ss, topz))
pitch = L / a.n
clear = pitch - a.pier
print(f"L={L:.0f} m  Enden {z0:.0f}/{z1:.0f} m  Sohle {tp.min():.0f} m  "
      f"Pfeiler max {topz[tp.argmin()]-tp.min():.0f} m  pitch {pitch:.1f}  Öffnung {clear:.1f}")

# --- Ansicht im (s,z)-Schnitt: oben Deck-Unterkante, unten Geländeprofil ----
top = [(float(s), float(topz[i])) for i, s in enumerate(ss)]
bot = [(float(s), float(tp[i])) for i, s in reversed(list(enumerate(ss)))]
outer = Polygon(top + bot).buffer(0)

def round_arch(sc, half, z_lo, z_sp, prof=None, batter=0.0):
    """Bogen-Öffnung: Leibung z_lo..z_sp (mit Pfeiler-Anzug), dann echte Bogenform aus
    `prof` (Korbbogen/gemessenes Profil; None=Halbkreis) — identisch zu ravenna_viadukt."""
    f = (lambda t: 0.0) if prof is None else apr.profile_fn(*prof)
    bw = half - batter*(z_sp - z_lo)                  # Öffnung am Fuß schmaler = Pfeiler breiter
    pts = [(sc-bw, z_lo), (sc-half, z_sp)]
    for ang in np.linspace(np.pi, 0, 48):
        r = half*(1.0 + f(ang))
        pts.append((sc + r*np.cos(ang), z_sp + r*np.sin(ang)))
    pts.append((sc+bw, z_lo))
    return Polygon(pts)

zlo = float(tp.min()-10)
rise = a.rise if a.rise > 0 else clear/2          # Korbbogen-Stich (m); 0/=Halbspann -> Halbkreis
PROF = apr.basket_arch_profile(clear, rise) if rise < clear/2 - 1e-6 else None  # KOMPLETTE Form
holes = []
for k in range(a.n):
    sc = (k+0.5)*pitch
    crown = under(sc) - 1.0
    zsp = crown - rise
    holes.append(round_arch(sc, clear/2, zlo, zsp, prof=PROF, batter=a.batter))
panel = outer.difference(unary_union(holes).buffer(0)).buffer(0)
polys = list(panel.geoms) if panel.geom_type == "MultiPolygon" else [panel]
print(f"Panel: {len(polys)} Teil(e)")

# --- extrudieren (Breite) + nach UTM entlang der Trasse ---------------------
def to_utm(mesh):
    V = mesh.vertices
    s = V[:, 0]; z = V[:, 1]; w = V[:, 2] - a.deck_w/2
    P = np.array([cl(si) for si in s])
    return np.column_stack([P[:, 0] + w*nrm[0], P[:, 1] + w*nrm[1], z])

body = trimesh.util.concatenate([extrude_polygon(pp, a.deck_w) for pp in polys])
body.vertices = to_utm(body)

# Deck-Platte (Unterkante..Oberkante) + kleine Kragplatte
deck2d = Polygon([(0, 0), (L, 0), (L, a.deck_t), (0, a.deck_t)])
deck = extrude_polygon(deck2d, a.deck_w+1.2)
Vd = deck.vertices; s = Vd[:, 0]; z = Vd[:, 1]; w = Vd[:, 2] - (a.deck_w+1.2)/2
P = np.array([cl(si) for si in s])
deck.vertices = np.column_stack([P[:, 0]+w*nrm[0], P[:, 1]+w*nrm[1], np.array([under(si) for si in s])+z])

via = trimesh.util.concatenate([body, deck])

# --- Stirnbogen-Ring (Verdickung unterhalb der Bögen), vorne + hinten ---------
if a.arch_ring:
    rings = []
    for k in range(a.n):
        sc = (k+0.5)*pitch; zsp = (under(sc)-1.0) - rise
        band = apr.archivolt_band(sc, clear/2, zsp, prof=PROF, d_crown=a.ring_scheitel,
                                  d_spring=a.ring_kaempfer, skirt=a.ring_skirt)
        for woff in (-a.ring_proj, a.deck_w-0.05):          # Vorder- + Rückseite
            m = extrude_polygon(band, a.ring_proj+0.05)
            m.vertices[:, 2] += woff                         # (s, z, w) -> w verschoben
            m.vertices = to_utm(m)
            rings.append(m)
    via = trimesh.util.concatenate([via] + rings)
    print(f"Stirnbogen-Ring: {2*a.n} Bänder (Scheitel {a.ring_scheitel}→Kämpfer {a.ring_kaempfer} m)")

trimesh.repair.fix_normals(via)
via.export(a.out)
print(f"Viadukt (UTM, gelände-folgend): {len(via.vertices)}V/{len(via.faces)}F  "
      f"bbox {via.extents.round(1)} m -> {a.out}")

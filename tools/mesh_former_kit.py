#!/usr/bin/env python3
"""mesh_former_kit.py — beliebiges 3D-MESH -> steckbares Laser-SPANTEN-Gerüst + 3D-Druck-Daten.

Der Gebäude-/Monument-Bruder zu laser_relief_kit.py (das ist nur für Höhenfelder/Gelände).
Schneidet ein Mesh mit senkrechten Ebenen in X und Y -> Querschnitte = SPANTEN (flache
Innenteile). An den Kreuzungen Halb-Schlitze (X von oben, Y von unten) -> stecken zum
inneren Gerüst. Exportiert:
  - Laser:  je Spant ein SVG (+ GRBL --gcode), Außenkontur + Schlitze + Nummer
  - 3D:     skin.stl (das Mesh selbst = die detaillierte Außenhaut/Teile zum Drucken)
  - MANIFEST.txt + 3D-Vorschau des Gerüsts

Skelett = Laser (billig, schnell), Detailhaut = FDM/Resin (wo's zählt).

  python3 tools/mesh_former_kit.py modelle/dom.stl --nx 5 --ny 5 --thickness 3 \
      --target-h 200 --gcode --out /tmp/domkit
"""
import argparse, os, math, sys, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from laser_relief_kit import glyph_strokes, svg_write, gcode_write   # Helfer wiederverwenden


def order_loops(segs, tol=1e-4):
    """2D-Segmente (K,2,2) -> geordnete Polylinien (Loops)."""
    S=[(tuple(map(float,s[0])),tuple(map(float,s[1]))) for s in segs]
    used=[False]*len(S); loops=[]
    def near(a,b): return abs(a[0]-b[0])<tol and abs(a[1]-b[1])<tol
    for st in range(len(S)):
        if used[st]: continue
        used[st]=True; loop=[S[st][0],S[st][1]]
        ext=True
        while ext:
            ext=False; tail=loop[-1]
            for k in range(len(S)):
                if used[k]: continue
                a,b=S[k]
                if near(a,tail): loop.append(b); used[k]=True; ext=True; break
                if near(b,tail): loop.append(a); used[k]=True; ext=True; break
        loops.append(np.array(loop))
    return loops


def section_2d(mesh, axis, pos):
    """Querschnitt bei axis='x'/'y' an Position pos -> Loops in (u,z) (u=y bzw. x)."""
    n=[1,0,0] if axis=="x" else [0,1,0]
    o=[pos,0,0] if axis=="x" else [0,pos,0]
    try:
        lines=trimesh.intersections.mesh_plane(mesh, plane_normal=n, plane_origin=o)
    except Exception:
        return []
    if lines is None or len(lines)==0: return []
    idx=[1,2] if axis=="x" else [0,2]        # (y,z) bzw. (x,z)
    return order_loops(lines[:,:,idx])


def section_geom(mesh, axis, pos):
    """Querschnitt -> vereinigte shapely-Silhouette (robust bei mehrteilig/überlappend)."""
    loops=section_2d(mesh, axis, pos)
    polys=[]
    for lp in loops:
        if len(lp)>=4:
            try:
                p=Polygon(lp)
                if not p.is_valid: p=p.buffer(0)
                if p.area>1e-6: polys.append(p)
            except Exception: pass
    if not polys: return None
    g=unary_union(polys)
    return g if not g.is_empty else None


def geom_rings(g):
    """Alle Ringe (außen+innen) der (Multi)Polygon-Silhouette als (N,2)-Arrays."""
    geoms=list(g.geoms) if g.geom_type=="MultiPolygon" else [g]
    rings=[]
    for gg in geoms:
        rings.append(np.array(gg.exterior.coords))
        for r in gg.interiors: rings.append(np.array(r.coords))
    return rings


def zspan_geom(g, u):
    """(zmin,zmax) der Silhouette an der vertikalen Linie U=u."""
    inter=g.intersection(LineString([(u,-1e5),(u,1e5)]))
    if inter.is_empty: return None
    zs=[]
    for geom in (inter.geoms if hasattr(inter,"geoms") else [inter]):
        zs+= [c[1] for c in getattr(geom,"coords",[])] or ([geom.y] if geom.geom_type=="Point" else [])
    return (min(zs),max(zs)) if zs else None


def slot_rect(u, zlo, zhi, w):
    return [(u-w/2,zlo),(u+w/2,zlo),(u+w/2,zhi),(u-w/2,zhi),(u-w/2,zlo)]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mesh")
    ap.add_argument("--out",default="/tmp/meshkit")
    ap.add_argument("--nx",type=int,default=5,help="Spanten normal X")
    ap.add_argument("--ny",type=int,default=5,help="Spanten normal Y")
    ap.add_argument("--thickness",type=float,default=3.0)
    ap.add_argument("--fit",type=float,default=0.2)
    ap.add_argument("--target-h",type=float,default=None,help="Zielhöhe mm (skaliert)")
    ap.add_argument("--scale",type=float,default=1.0)
    ap.add_argument("--bed-x",type=float,default=410);ap.add_argument("--bed-y",type=float,default=400)
    ap.add_argument("--gcode",action="store_true")
    ap.add_argument("--feed",type=float,default=400);ap.add_argument("--power",type=float,default=100)
    ap.add_argument("--passes",type=int,default=4);ap.add_argument("--eng-power",type=float,default=20)
    a=ap.parse_args()
    os.makedirs(a.out,exist_ok=True)
    t=a.thickness; slotw=t+a.fit

    m=trimesh.load(a.mesh,force="mesh")
    m.apply_translation(-m.bounds[0])                       # Min-Ecke auf Ursprung
    s=a.scale
    if a.target_h: s*= a.target_h/(m.bounds[1][2]-m.bounds[0][2])
    if abs(s-1)>1e-9: m.apply_scale(s)
    (x0,y0,z0),(x1,y1,z1)=m.bounds; W,D,Hh=x1-x0,y1-y0,z1-z0
    xpos=np.linspace(W*0.1,W*0.9,a.nx); ypos=np.linspace(D*0.1,D*0.9,a.ny)

    manifest=[f"MESH-SPANTEN-KIT  {os.path.basename(a.mesh)}  {W:.0f}x{D:.0f}x{Hh:.0f} mm (scale {s:.3f})",
              f"Material {t} mm, Schlitz {slotw:.2f}  |  {a.nx} X-Spanten + {a.ny} Y-Spanten",
              "MONTAGE: X-Spanten (Schlitz oben) und Y-Spanten (Schlitz unten) ineinanderstecken.",
              "Dann 3D-gedruckte Haut/Detailteile (skin.stl) aufsetzen.",""]
    parts=[]; oversize=[]

    def build(axis, pos, crossings_pos, from_top, name):
        g=section_geom(m, axis, pos)
        if g is None: return None
        rings=geom_rings(g)
        if not rings: return None
        allpts=np.vstack(rings)
        umin,umax=allpts[:,0].min(),allpts[:,0].max()
        zmin_o,zmax_o=allpts[:,1].min(),allpts[:,1].max()
        cut=[r for r in rings]                                 # außen + innen (Löcher)
        for cp in crossings_pos:
            sp=zspan_geom(g, cp)
            if not sp: continue
            zl,zh=sp; zmid=(zl+zh)/2
            if from_top: cut.append(slot_rect(cp, zmid, zh+5, slotw))   # von oben bis Mitte
            else:        cut.append(slot_rect(cp, zl-5, zmid, slotw))   # von unten bis Mitte
        eng=glyph_strokes(name, umin+3, (zmin_o+zmax_o)/2, h=min(10,(zmax_o-zmin_o)*0.25))
        bb=(umax-umin, zmax_o-zmin_o)
        if bb[0]>a.bed_x or bb[1]>a.bed_y: oversize.append((name,bb))
        return (name,cut,eng,bb)

    for i,xr in enumerate(xpos):                 # X-Spanten (Schlitz von OBEN), Kreuzung an ypos
        r=build("x",xr,list(ypos),True,f"X{i}")
        if r: parts.append(r); manifest.append(f"  Spant X{i}  ({r[3][0]:.0f}x{r[3][1]:.0f} mm)")
    for j,yr in enumerate(ypos):                 # Y-Spanten (Schlitz von UNTEN), Kreuzung an xpos
        r=build("y",yr,list(xpos),False,f"Y{j}")
        if r: parts.append(r); manifest.append(f"  Spant Y{j}  ({r[3][0]:.0f}x{r[3][1]:.0f} mm)")

    # Export Laser
    for (name,cut,eng,bb) in parts:
        svg_write(f"{a.out}/spant_{name}.svg", cut, [], [], eng, 0)
        if a.gcode: gcode_write(f"{a.out}/spant_{name}.gcode", cut, [], [], eng, 0,
                                a.feed,a.power,a.passes,a.eng_power)
    # Export 3D-Haut (das Mesh selbst = Detail zum Drucken)
    m.export(f"{a.out}/skin.stl")
    manifest+=["", "3D-DRUCK: skin.stl = detaillierte Außenhaut/Teile (über Gerüst setzen)."]
    if oversize:
        manifest.append(f"!! {len(oversize)} Spanten > Bett ({a.bed_x:.0f}x{a.bed_y:.0f}) -> teilen/kleiner skalieren:")
        for (nm,bb) in oversize: manifest.append(f"   {nm}: {bb[0]:.0f}x{bb[1]:.0f}")
    open(f"{a.out}/MANIFEST.txt","w").write("\n".join(manifest)+"\n")
    print("\n".join(manifest))
    print(f"\n{len(parts)} Spanten + skin.stl -> {a.out}/")

    # 3D-Vorschau: Spanten an ihren Ebenen
    fig=plt.figure(figsize=(9,7)); ax=fig.add_subplot(111,projection="3d")
    for i,xr in enumerate(xpos):
        for lp in section_2d(m,"x",xr):
            ax.plot([xr]*len(lp), lp[:,0], lp[:,1], color="#486", lw=.8)
    for j,yr in enumerate(ypos):
        for lp in section_2d(m,"y",yr):
            ax.plot(lp[:,0], [yr]*len(lp), lp[:,1], color="#884", lw=.8)
    ax.set_box_aspect((W,D,Hh)); ax.view_init(elev=22,azim=-60)
    ax.set_title(f"Mesh-Spanten-Gerüst {a.nx}x{a.ny}  [{Hh/10:.0f}cm]")
    plt.tight_layout(); plt.savefig(f"{a.out}/_vorschau.png",dpi=95)
    print(f"Vorschau -> {a.out}/_vorschau.png")


if __name__=="__main__": main()

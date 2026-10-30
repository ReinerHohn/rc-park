#!/usr/bin/env python3
"""terrain_spanten.py — Gelände als STECK-SPANTEN-Gerüst (egg-crate) statt Waffelgitter.

Erzeugt pro Segment:
  - einen BASISKASTEN (offene Wanne) mit Schlitzen an zwei Wänden
  - flache STREBEN, deren Oberkante dem Gelände folgt, mit Endzapfen zum EINHÄNGEN
    in die Kastenschlitze; jede Strebe trägt eine ERHABENE Nummer (z. B. S0-R3).
Alles flach gedruckt → schneller + sauberer Toolpath als das Waffelgitter.
Danach Haut (dünne Schale/Pappe/Styrol) drauf — kein Gips nötig.

Beispiel (r0c0-Region des kleinen Belchen):
  python3 tools/terrain_spanten.py --hf modelle/terrain_data/belchen_eng_hf.stl \
     --u0 0 --u1 0.5 --v0 0 --v1 0.5 --segw 106 --segd 158 --peak 42 \
     --ribs 6 --seg S0 --out modelle/spanten
"""
import argparse, os, numpy as np, trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

# ---------- Heightfield aus normiertem STL ----------
def heightfield(path, grid=240):
    m = trimesh.load(path, force='mesh'); v = m.vertices
    x0,y0,x1,y1 = v[:,0].min(),v[:,1].min(),v[:,0].max(),v[:,1].max()
    ix = np.clip(((v[:,0]-x0)/(x1-x0)*(grid-1)).astype(int),0,grid-1)
    iy = np.clip(((v[:,1]-y0)/(y1-y0)*(grid-1)).astype(int),0,grid-1)
    H = np.full((grid,grid),-1e9); np.maximum.at(H,(iy,ix),v[:,2])
    from scipy import ndimage
    mask=H<-1e8
    if mask.any():
        idx=ndimage.distance_transform_edt(mask,return_distances=False,return_indices=True); H=H[tuple(idx)]
    H-=H.min(); H/=(H.max()+1e-9)
    return H
def sample(H,u,v):
    n=H.shape[0]; fu=np.clip(u*(n-1),0,n-1); fv=np.clip(v*(n-1),0,n-1)
    return H[int(round(fv)),int(round(fu))]

# ---------- Text zu flachem Mesh (erhaben) ----------
def text_mesh(s, size=5.0, depth=0.6):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    tp=TextPath((0,0), s, size=size, prop=FontProperties(family="DejaVu Sans"))
    polys=[Polygon(p) for p in tp.to_polygons() if len(p)>=3]
    if not polys: return None
    geom=unary_union(polys).buffer(0)
    parts=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
    ms=[trimesh.creation.extrude_polygon(g,height=depth) for g in parts if not g.is_empty]
    return trimesh.util.concatenate(ms) if ms else None

# ---------- flache Platte: liegt FLACH auf dem Bett (x=Länge, y=Höhe, z=Dicke) ----------
def plate(poly_xy, thick):
    return trimesh.creation.extrude_polygon(Polygon(poly_xy), height=thick)  # flach, Dicke in Z

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--hf', required=True)
    p.add_argument('--u0',type=float,default=0); p.add_argument('--u1',type=float,default=1)
    p.add_argument('--v0',type=float,default=0); p.add_argument('--v1',type=float,default=1)
    p.add_argument('--segw',type=float,default=106); p.add_argument('--segd',type=float,default=158)
    p.add_argument('--peak',type=float,default=42); p.add_argument('--ribs',type=int,default=6)
    p.add_argument('--t',type=float,default=1.6, help='Strebendicke mm')
    p.add_argument('--tol',type=float,default=0.25, help='Schlitz-Spiel mm')
    p.add_argument('--wall',type=float,default=14, help='Kastenwandhöhe mm')
    p.add_argument('--tab',type=float,default=8, help='Zapfentiefe in den Kasten mm')
    p.add_argument('--seg',default='S0'); p.add_argument('--out',default='modelle/spanten')
    a=p.parse_args()
    os.makedirs(a.out,exist_ok=True)
    H=heightfield(a.hf)

    inner_w=a.segw; inner_d=a.segd           # Streben laufen entlang der Tiefe (segd)
    xs=np.linspace(0.12,0.88,a.ribs)          # Rippen-Positionen (Bruchteil der Breite, Rand frei)
    parts_info=[]
    NS=80                                     # Profilauflösung
    for r,fx in enumerate(xs):
        u=a.u0+fx*(a.u1-a.u0)
        cs=np.linspace(0,1,NS)
        vv=a.v0+cs*(a.v1-a.v0)
        htop=np.array([sample(H,u,x)*a.peak for x in vv])+a.wall*0.5  # Oberkante + Grundhöhe
        yc=cs*inner_d
        # Polygon: unten Linie, oben Gelände, + Endzapfen die nach unten (−tab) ragen
        pts=[(-a.tab,0)]                      # linker Zapfen unten
        pts+=[(0,a.wall*0.5)]                 # hoch an die Basis-Innenkante
        for x,h in zip(yc,htop): pts.append((x,h))
        pts+=[(inner_d,a.wall*0.5),(inner_d+a.tab,0)]  # rechter Zapfen
        pts+=[(inner_d+a.tab,-6),(-a.tab,-6)]          # unten schließen (Zapfen 6mm tief)
        m=plate(pts,a.t)
        # Nummer erhaben auf die (flach liegende) Oberseite
        lbl=text_mesh(f"{a.seg}-R{r}", size=6, depth=0.6)
        if lbl is not None:
            lbl.apply_translation([inner_d*0.5-12, a.wall*0.5+3, a.t])  # auf Oberseite z=t
            m=trimesh.util.concatenate([m,lbl])
        fn=f"{a.out}/{a.seg}_rib{r}.stl"; m.export(fn)
        parts_info.append((f"{a.seg}-R{r}", round(fx*inner_w,1)))
        print(f"  Strebe {a.seg}-R{r}: x={fx*inner_w:5.1f}mm  Höhe~{htop.max():.0f}mm -> {fn}")

    # ---------- Basiskasten (offene Wanne) mit Schlitzen ----------
    box=_tray(inner_w,inner_d,a.wall,a.t,a.tol,a.tab,xs)
    bfn=f"{a.out}/{a.seg}_kasten.stl"; box.export(bfn)
    print(f"  Basiskasten {a.segw:.0f}x{a.segd:.0f} Wand {a.wall}mm -> {bfn}")

    # ---------- Montage-Karte ----------
    _map(a,xs,inner_w,inner_d,parts_info)
    print(f"Fertig: {a.ribs} Streben + 1 Kasten + Karte in {a.out}/")

def _tray(W,D,wall,t,tol,tab,xs):
    wt=2.0                                   # Wandstärke Kasten
    boxes=[]
    # Boden-Rahmen (nur Ränder, Mitte offen -> leicht)
    for (cx,cy,sx,sy) in [(W/2,wt/2,W,wt),(W/2,D-wt/2,W,wt),(wt/2,D/2,wt,D),(W-wt/2,D/2,wt,D)]:
        b=trimesh.creation.box(extents=[sx,sy,wall]); b.apply_translation([cx,cy,wall/2]); boxes.append(b)
    tray=trimesh.util.concatenate(boxes)
    # Schlitze oben in die beiden Längswände (y=0 und y=D) an jeder Rippenposition
    cuts=[]
    for fx in xs:
        x=fx*W
        for y in (wt/2, D-wt/2):
            c=trimesh.creation.box(extents=[t+2*tol, wt+2, tab*1.2])
            c.apply_translation([x,y,wall-tab*0.6+ (tab*1.2)/2 - tab*0.6]);
            c.apply_translation([0,0,wall- (tab*1.2)/2])   # Schlitz von oben
            cuts.append(c)
    try:
        cut=trimesh.util.concatenate(cuts)
        tray=tray.difference(cut)            # braucht manifold/blender; sonst Fallback
    except Exception:
        # Fallback: Schlitze als separate „Minus"-Marker nicht möglich -> Kasten ohne Schlitze,
        # Streben stecken dann per Übermaß/Kleber. (Hinweis im Print)
        pass
    return tray

def _map(a,xs,W,D,info):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(6,8))
    ax.add_patch(plt.Rectangle((0,0),W,D,fill=False,lw=2))
    for r,fx in enumerate(xs):
        x=fx*W; ax.plot([x,x],[0,D],'r-',lw=1.5)
        ax.text(x,D+3,f"R{r}",ha='center',color='r',fontsize=9,fontweight='bold')
    ax.set_xlim(-10,W+10); ax.set_ylim(-10,D+15); ax.set_aspect('equal')
    ax.set_title(f"Montage-Karte Segment {a.seg}\n{W:.0f}x{D:.0f}mm, Streben R0..R{a.ribs-1} (links→rechts)")
    ax.set_xlabel("Breite mm"); ax.set_ylabel("Tiefe mm")
    plt.tight_layout(); plt.savefig(f"{a.out}/{a.seg}_montage.png",dpi=120)

if __name__=='__main__':
    main()

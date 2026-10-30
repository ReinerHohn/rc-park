#!/usr/bin/env python3
"""laser_relief_kit.py — EIN Relief rein -> KOMPLETTES steckbares Laser-Kit raus.

Erzeugt aus einem DEM-Fenster alle flachen Laser-Teile für den Hybrid-Aufbau:
  1. GITTER (Egg-Crate, 0..transition_z): ineinandersteckende Rippen (X-Schlitz oben,
     Y-Schlitz unten), flacher Deckel auf transition_z, je Rippe ein Steck-TAB oben.
  2. ÜBERGANGSPLATTE (P) auf transition_z: Rechteck mit Schlitzen für die Rippen-Tabs
     + 2 Dübellöchern -> steckt aufs Gitter, trägt den Stack.
  3. KONTUR-STACK (transition_z..zmax): geglättete Höhenlagen, 2 Dübellöcher (fluchten
     mit der Platte) -> dieselben 2 Dübel vom Gitterdeckel bis zur Spitze.
ALLE Teile mit eingravierter NUMMER (Strichfont). Plus Manifest + 3D-Vorschau + GRBL.

  python3 tools/laser_relief_kit.py --out /tmp/kit --thickness 3 --trans-frac 0.5 \
      --nx 5 --ny 5 --layers-max 20 --vscale 1.0
"""
import argparse, os, math, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BIG = "daten/hoellental/hirsch_big.npy"; MM = 6.25

# ---- Strich-Font (0-9, X,Y,P) in 6x10-Box ------------------------------------
_A=[(0,10),(6,10)];_B=[(6,10),(6,5)];_C=[(6,5),(6,0)];_D=[(0,0),(6,0)]
_E=[(0,5),(0,0)];_F=[(0,10),(0,5)];_G=[(0,5),(6,5)]
FONT={'0':[_A,_B,_C,_D,_E,_F],'1':[_B,_C],'2':[_A,_B,_G,_E,_D],'3':[_A,_B,_G,_C,_D],
 '4':[_F,_G,_B,_C],'5':[_A,_F,_G,_C,_D],'6':[_A,_F,_G,_C,_D,_E],'7':[_A,_B,_C],
 '8':[_A,_B,_C,_D,_E,_F,_G],'9':[_A,_B,_C,_D,_F,_G],
 'X':[[(0,10),(6,0)],[(0,0),(6,10)]],'Y':[[(0,10),(3,5)],[(6,10),(3,5)],[(3,5),(3,0)]],
 'P':[[(0,0),(0,10)],_A,_B,[(6,5),(0,5)]]}

def glyph_strokes(text, ox, oy, h=7.0):
    """Polylinien (mm) für 'text' ab (ox,oy), Zeichenhöhe h."""
    s=h/10.0; adv=6*s+2.0; out=[]
    for ch in str(text):
        if ch in FONT:
            for st in FONT[ch]:
                out.append([(ox+x*s, oy+y*s) for (x,y) in st])
        ox+=adv
    return out

# ---- SVG-Helfer --------------------------------------------------------------
def svg_write(fn, cut_polys, cut_opens, holes, engrave, hole_r):
    pts=[p for poly in cut_polys for p in poly]+[p for poly in cut_opens for p in poly]
    pts+=[(cx,cy) for (cx,cy) in holes]+[p for st in engrave for p in st]
    a=np.array(pts,float); mn=a.min(0);
    def T(p): return (p[0]-mn[0]+6, p[1]-mn[1]+6)
    W=np.ptp(a[:,0])+12; H=np.ptp(a[:,1])+12
    L=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{H:.1f}mm" viewBox="0 0 {W:.1f} {H:.1f}">']
    for poly in cut_polys:
        d="M "+" L ".join(f"{T(p)[0]:.2f},{T(p)[1]:.2f}" for p in poly)+" Z"
        L.append(f'<path d="{d}" fill="none" stroke="#f00" stroke-width="0.1"/>')
    for poly in cut_opens:
        d="M "+" L ".join(f"{T(p)[0]:.2f},{T(p)[1]:.2f}" for p in poly)
        L.append(f'<path d="{d}" fill="none" stroke="#f00" stroke-width="0.1"/>')
    for (cx,cy) in holes:
        t=T((cx,cy)); L.append(f'<circle cx="{t[0]:.2f}" cy="{t[1]:.2f}" r="{hole_r:.2f}" fill="none" stroke="#00f" stroke-width="0.1"/>')
    for st in engrave:
        d="M "+" L ".join(f"{T(p)[0]:.2f},{T(p)[1]:.2f}" for p in st)
        L.append(f'<path d="{d}" fill="none" stroke="#0a0" stroke-width="0.1"/>')
    L.append("</svg>"); open(fn,"w").write("\n".join(L)+"\n")

# ---- GRBL-Helfer -------------------------------------------------------------
def gcode_write(fn, cut_polys, cut_opens, holes, engrave, hole_r, feed, power, passes, eng_power):
    S=int(power*10); ES=int(eng_power*10)
    pts=[p for poly in cut_polys for p in poly]
    a=np.array(pts,float) if pts else np.zeros((1,2)); mn=a.min(0)
    def T(p): return (p[0]-mn[0]+6, p[1]-mn[1]+6)
    L=["G21","G90","G17","M5 S0","G92 X0 Y0"]
    def trace(poly,close,s,f):
        p0=T(poly[0]); L.append("M5"); L.append(f"G0 X{p0[0]:.2f} Y{p0[1]:.2f}"); L.append(f"M4 S{s}")
        for p in poly[1:]: t=T(p); L.append(f"G1 X{t[0]:.2f} Y{t[1]:.2f} F{f:.0f}")
        if close: L.append(f"G1 X{p0[0]:.2f} Y{p0[1]:.2f} F{f:.0f}")
        L.append("M5")
    for st in engrave: trace(st,False,ES,3000)              # Gravur zuerst (flach)
    for _ in range(passes):
        for poly in cut_polys: trace(poly,True,S,feed)
        for poly in cut_opens: trace(poly,False,S,feed)
        for (cx,cy) in holes:
            circ=[(cx+hole_r*math.cos(t),cy+hole_r*math.sin(t)) for t in [k*2*math.pi/24 for k in range(25)]]
            trace(circ,False,S,feed)
    L+=["M5 S0","G0 X0 Y0"]; open(fn,"w").write("\n".join(L)+"\n")

# ---- Geometrie ---------------------------------------------------------------
def rib_poly(L, zt, cross, slotw, from_top, tab_pos, tab_w, tab_h):
    """Rippen-Polygon (flacher Deckel zt). cross=Kreuzungspositionen, Schlitz zt/2 tief.
    from_top: Schlitze von oben (sonst von unten). tab_pos: ein Steck-Tab oben."""
    d=zt/2.0; pts=[(0.0,0.0)]
    # Bodenkante
    if from_top:
        pts.append((L,0.0))
    else:
        for c in sorted(cross):
            pts+=[(c-slotw/2,0.0),(c-slotw/2,d),(c+slotw/2,d),(c+slotw/2,0.0)]
        pts.append((L,0.0))
    pts.append((L,zt))
    # Oberkante rechts->links: Down-Notches (falls from_top) + Up-Tab
    feats=[]
    if from_top:
        for c in cross: feats.append((c,"notch"))
    feats.append((tab_pos,"tab"))
    for (pos,kind) in sorted(feats,key=lambda t:-t[0]):
        if kind=="notch":
            pts+=[(pos+slotw/2,zt),(pos+slotw/2,zt-d),(pos-slotw/2,zt-d),(pos-slotw/2,zt)]
        else:
            pts+=[(pos+tab_w/2,zt),(pos+tab_w/2,zt+tab_h),(pos-tab_w/2,zt+tab_h),(pos-tab_w/2,zt)]
    pts.append((0.0,zt)); pts.append((0.0,0.0))
    return pts

def contour_polys(Z, level):
    pad=np.pad(Z,1,mode="constant",constant_values=float(Z.min())-1e6)
    cs=plt.contour(pad,levels=[level]); segs=cs.allsegs[0] if cs.allsegs else []
    plt.close("all"); return [s-1.0 for s in segs if len(s)>=4]

def decimate(poly,m):
    if m<=0 or len(poly)<4: return poly
    out=[poly[0]]
    for p in poly[1:]:
        if math.hypot(p[0]-out[-1][0],p[1]-out[-1][1])>=m: out.append(p)
    if math.hypot(out[0][0]-out[-1][0],out[0][1]-out[-1][1])>1e-6: out.append(out[0])
    return np.array(out)

def pip(x,y,poly):
    n=len(poly);c=False;j=n-1
    for i in range(n):
        xi,yi=poly[i];xj,yj=poly[j]
        if ((yi>y)!=(yj>y)) and (x<(xj-xi)*(y-yi)/(yj-yi+1e-9)+xi): c=not c
        j=i
    return c

# ---- Main --------------------------------------------------------------------
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dem",default=BIG,help="Höhenfeld .npy (beliebiger Ort)")
    ap.add_argument("--mm",type=float,default=MM,help="mm pro DEM-Zelle (N=6.25)")
    ap.add_argument("--r0",type=int,default=854);ap.add_argument("--r1",type=int,default=880)
    ap.add_argument("--c0",type=int,default=850);ap.add_argument("--c1",type=int,default=886)
    ap.add_argument("--out",default="/tmp/kit")
    ap.add_argument("--thickness",type=float,default=3.0)
    ap.add_argument("--fit",type=float,default=0.15)
    ap.add_argument("--vscale",type=float,default=1.0,help="1.0=true-N Höhe")
    ap.add_argument("--trans-frac",type=float,default=0.5,help="Gitterhöhe als Anteil von zmax")
    ap.add_argument("--nx",type=int,default=5,help="Y-Rippen (an X-Pos)")
    ap.add_argument("--ny",type=int,default=5,help="X-Rippen (an Y-Pos)")
    ap.add_argument("--layers-max",type=int,default=20,help="max Kontur-Lagen (begrenzt Höhe/Band)")
    ap.add_argument("--smooth",type=float,default=4.0);ap.add_argument("--min-seg",type=float,default=1.0)
    ap.add_argument("--dowel-d",type=float,default=3.2)
    ap.add_argument("--tab-w",type=float,default=10.0);ap.add_argument("--tab-h",type=float,default=None)
    ap.add_argument("--gcode",action="store_true")
    ap.add_argument("--feed",type=float,default=400);ap.add_argument("--power",type=float,default=100)
    ap.add_argument("--passes",type=int,default=4);ap.add_argument("--eng-power",type=float,default=20)
    a=ap.parse_args()
    from scipy.ndimage import zoom,gaussian_filter
    os.makedirs(a.out,exist_ok=True)
    tab_h=a.tab_h if a.tab_h else a.thickness
    t=a.thickness; slotw=t+a.fit; hr=a.dowel_d/2

    win=np.load(a.dem)[a.r0:a.r1,a.c0:a.c1].astype(float)
    rel=gaussian_filter(zoom(win-win.min(),4,order=1),a.smooth)
    cell=MM/4
    H=rel*a.mm*a.vscale                       # Höhenfeld mm
    NY,NX=H.shape; W,D=NX*cell,NY*cell; zmax=float(H.max())
    zt=zmax*a.trans_frac
    def Hat(x,y):
        xi=min(max(x/cell,0),NX-1);yi=min(max(y/cell,0),NY-1)
        return float(H[int(round(yi)),int(round(xi))])

    manifest=[f"RELIEF-KIT  Fenster {NX}x{NY} -> {W:.0f}x{D:.0f} mm, zmax {zmax:.0f} mm (vscale {a.vscale})",
              f"Material {t} mm, Schlitz {slotw:.2f}, Übergang zt={zt:.0f} mm ({a.trans_frac:.0%})",
              "MONTAGE von unten nach oben:"]
    parts=[]  # (name, cut_polys, cut_opens, holes, engrave)

    # --- 1) GITTER-RIPPEN (flacher Deckel zt) ---
    xpos=np.linspace(W*0.12,W*0.88,a.nx); ypos=np.linspace(D*0.12,D*0.88,a.ny)
    for j,yr in enumerate(ypos):  # X-Rippen (entlang X, Schlitz von OBEN)
        poly=rib_poly(W,zt,list(xpos),slotw,True, W*0.5, a.tab_w,tab_h)
        eng=glyph_strokes(f"X{j}", 4, zt*0.35, h=min(10,zt*0.3))
        nm=f"grid_X{j}"; parts.append((nm,[poly],[],[],eng)); manifest.append(f"  Gitter X{j}")
    for i,xr in enumerate(xpos):  # Y-Rippen (entlang Y, Schlitz von UNTEN)
        poly=rib_poly(D,zt,list(ypos),slotw,False, D*0.5, a.tab_w,tab_h)
        eng=glyph_strokes(f"Y{i}", 4, zt*0.6, h=min(10,zt*0.3))
        nm=f"grid_Y{i}"; parts.append((nm,[poly],[],[],eng)); manifest.append(f"  Gitter Y{i}")

    # --- Kontur-Levels auf Materialdicke (physisch stapelbar) ---
    levels=np.arange(zt+t*0.5, zmax, t)
    if len(levels)==0: levels=np.array([zt+ (zmax-zt)*0.5])
    if len(levels)>a.layers_max:
        print(f"!! {len(levels)} Kontur-Lagen > layers-max {a.layers_max}: --trans-frac erhöhen "
              f"(Gitter höher) für weniger Lagen. Fahre trotzdem fort.")
    # --- Dübelpositionen (im obersten Stack-Level, in Platte+allen Lagen) ---
    holes_xy=[]
    for lv in levels[::-1]:
        ps=[decimate(p*cell,a.min_seg) for p in contour_polys(H,lv)]
        if not ps: continue
        bp=max(ps,key=lambda p:(np.ptp(p[:,0]))*(np.ptp(p[:,1])))
        bw,bh=np.ptp(bp[:,0]),np.ptp(bp[:,1])
        if bw>=40 and bh>=25:
            cyv=(bp[:,1].min()+bp[:,1].max())/2; cxv=(bp[:,0].min()+bp[:,0].max())/2
            holes_xy=[(bp[:,0].min()+12,cyv),(bp[:,0].max()-12,cyv)] if bw>=bh else [(cxv,bp[:,1].min()+12),(cxv,bp[:,1].max()-12)]
            break
    if not holes_xy: holes_xy=[(W*0.35,D*0.5),(W*0.65,D*0.5)]

    # --- 2) ÜBERGANGSPLATTE P (Rechteck + Tab-Schlitze + Dübellöcher) ---
    plate_out=[(0,0),(W,0),(W,D),(0,D),(0,0)]
    tab_slots=[]
    for xr in xpos:  # Y-Rippen-Tab bei (xr, D*0.5): footprint t(x) x tab_w(y)
        cx,cy=xr,D*0.5; tab_slots.append([(cx-t/2-a.fit/2,cy-a.tab_w/2),(cx+t/2+a.fit/2,cy-a.tab_w/2),
            (cx+t/2+a.fit/2,cy+a.tab_w/2),(cx-t/2-a.fit/2,cy+a.tab_w/2),(cx-t/2-a.fit/2,cy-a.tab_w/2)])
    for yr in ypos:  # X-Rippen-Tab bei (W*0.5, yr): footprint tab_w(x) x t(y)
        cx,cy=W*0.5,yr; tab_slots.append([(cx-a.tab_w/2,cy-t/2-a.fit/2),(cx+a.tab_w/2,cy-t/2-a.fit/2),
            (cx+a.tab_w/2,cy+t/2+a.fit/2),(cx-a.tab_w/2,cy+t/2+a.fit/2),(cx-a.tab_w/2,cy-t/2-a.fit/2)])
    eng=glyph_strokes("P", W*0.5-4, D*0.5-4, h=12)
    parts.append(("plate_P",[plate_out]+tab_slots,[],list(holes_xy),eng)); manifest.append("  ÜBERGANGSPLATTE P (auf Gitter stecken, Dübel rein)")

    # --- 3) KONTUR-STACK (zt..zmax) ---
    nlay=0
    for i,lv in enumerate(levels):
        ps=[decimate(p*cell,a.min_seg) for p in contour_polys(H,lv)]
        if not ps: continue
        hh=[(hx,hy) for (hx,hy) in holes_xy if any(pip(hx,hy,p) for p in ps)]
        eng=glyph_strokes(f"{i:02d}", float(np.vstack(ps)[:,0].min())+4, float(np.vstack(ps)[:,1].min())+4, h=7)
        parts.append((f"layer_{i:02d}",[p for p in ps],[],hh,eng)); nlay+=1
    manifest.append(f"  Kontur-Lagen 00..{len(levels)-1} (unten->oben, Dübel durch, {nlay} Stück)")

    # --- Export ---
    for (nm,cp,co,hh,eng) in parts:
        svg_write(f"{a.out}/{nm}.svg",cp,co,hh,eng,hr)
        if a.gcode: gcode_write(f"{a.out}/{nm}.gcode",cp,co,hh,eng,hr,a.feed,a.power,a.passes,a.eng_power)
    open(f"{a.out}/MANIFEST.txt","w").write("\n".join(manifest)+"\n")

    print("\n".join(manifest))
    print(f"\n{len(parts)} Teile -> {a.out}/  (SVG"+(" + GRBL" if a.gcode else "")+", MANIFEST.txt)")
    print(f"Modell true-N-Höhe {zmax:.0f} mm = {zmax/10:.1f} cm | Gitter bis {zt:.0f} mm | Stack {nlay} Lagen")

    # --- 3D-Vorschau (Konturen VOR der 3D-Achse berechnen) ---
    prev=[(i,lv,[p*cell for p in contour_polys(H,lv)]) for i,lv in enumerate(levels)]
    fig=plt.figure(figsize=(9,7));ax=fig.add_subplot(111,projection="3d")
    for xr in xpos:
        ax.plot([xr,xr],[0,D],[zt,zt],color="#486",lw=1)
        for yy in (0,D): ax.plot([xr,xr],[yy,yy],[0,zt],color="#8ac",lw=.5)
    for yr in ypos:
        ax.plot([0,W],[yr,yr],[zt,zt],color="#884",lw=1)
    ax.plot([0,W,W,0,0],[0,0,D,D,0],[zt]*5,color="#333",lw=1.2)   # Platte
    for (i,lv,ps) in prev:
        for pm in ps:
            ax.plot(pm[:,0],pm[:,1],[lv]*len(pm),color=plt.cm.terrain(i/max(1,len(levels))),lw=.8)
    for (hx,hy) in holes_xy: ax.plot([hx,hx],[hy,hy],[zt,zmax],"b--",lw=.8)
    ax.set_box_aspect((W,D,max(zmax,1)));ax.view_init(elev=28,azim=-60)
    ax.set_title(f"Relief-Kit: Gitter(zt={zt:.0f}) + Platte P + Stack  [{zmax/10:.0f}cm true-N]")
    plt.tight_layout();plt.savefig(f"{a.out}/_vorschau.png",dpi=95);print(f"Vorschau -> {a.out}/_vorschau.png")

if __name__=="__main__": main()

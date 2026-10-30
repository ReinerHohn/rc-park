#!/usr/bin/env python3
"""stadttor_generator.py — TYP-GENERATOR 'Stadttor' (Torturm mit Durchfahrt).
Parametrisch, config-getrieben → ein Generator für Martinstor UND Schwabentor
(und jedes weitere Torturm-Wahrzeichen). Massing aus LOD2, Details aus Config/Foto.

Bauteile (jeweils per Config an/aus + Maße):
  turm         quaderförmiger Turmschaft (W×D×H aus LOD2)
  durchfahrt   Spitzbogen-Tordurchfahrt, boolesch durch den Schaft geschnitten
  helm         Spitzhelm/Pyramidendach (pitch-parametrisch) + Firstknauf
  gesimse      umlaufende Sandstein-Bänder (z-Liste)
  uhr          Zifferblatt-Scheiben auf den Schauseiten
  zinnen       Zinnenkranz (optional, z.B. Schwabentor-Charakter)
  ecktuermchen Eck-Fialen/Türmchen (optional)

  python3 tools/stadttor_generator.py --config bauwerke/martinstor.json
"""
import argparse, json, os, sys
import numpy as np, trimesh


def pointed_arch_prism(w, h, rise, depth, segs=24):
    """Spitzbogen-Öffnung als Prisma (durch die Tiefe), zum boolschen Abzug.
    w=lichte Breite, h=Kämpferhöhe (senkrechte Flanke), rise=Bogenstich über Kämpfer."""
    # 2D-Profil in X(Breite)-Z(Höhe), danach entlang Y extrudieren
    hw = w / 2
    pts = [(-hw, 0), (hw, 0), (hw, h)]
    # Spitzbogen: zwei Kreisbögen von den Kämpfern zum Scheitel (gotisch)
    R = (hw**2 + rise**2) / (2 * rise) if rise > 0 else hw
    apex = (0, h + rise)
    # rechter Bogen: Mittelpunkt links unten gespiegelt → nähere parametrisch via Lerp auf Kreis
    for i in range(segs + 1):
        t = i / segs
        # von rechtem Kämpfer (hw,h) zum Scheitel (0,h+rise): Kreis um (-hw+R, h)
        cx = -hw + R
        a0 = np.arctan2(h - h, hw - cx)          # Winkel am Kämpfer
        a1 = np.arctan2(apex[1] - h, apex[0] - cx)
        a = a0 + (a1 - a0) * t
        pts.append((cx + R * np.cos(a), h + R * np.sin(a)))
    for i in range(segs + 1):                    # linker Bogen Scheitel→linker Kämpfer
        t = i / segs
        cx = hw - R
        a0 = np.arctan2(apex[1] - h, apex[0] - cx)
        a1 = np.arctan2(0.0, -hw - cx)
        a = a0 + (a1 - a0) * t
        pts.append((cx + R * np.cos(a), h + R * np.sin(a)))
    poly = trimesh.path.polygons.Polygon(pts).buffer(0)
    pr = trimesh.creation.extrude_polygon(poly, height=depth + 2.0)
    # extrude macht Höhe=Z; wir wollen Profil in X-Z, Extrusion in Y → rotieren
    pr.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [1, 0, 0]))
    pr.apply_translation([0, depth/2 + 1.0, 0])
    return pr


def box(w, d, h, z0, cx=0, cy=0):
    b = trimesh.creation.box((w, d, h))
    b.apply_translation([cx, cy, z0 + h/2])
    return b


def pyramid(w, d, h, z0, hip=0.0):
    """Pyramiden-/Spitzhelmdach. hip>0 = kleines Firstplateau (sonst Spitze)."""
    hw, hd = w/2, d/2
    base = [(-hw,-hd),(hw,-hd),(hw,hd),(-hw,hd)]
    V = [(x,y,z0) for x,y in base]
    if hip > 0:
        tw = hip/2
        V += [(-tw,-tw,z0+h),(tw,-tw,z0+h),(tw,tw,z0+h),(-tw,tw,z0+h)]
        F = [[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7],
             [4,5,6],[4,6,7],[0,3,2],[0,2,1]]
    else:
        V += [(0,0,z0+h)]
        F = [[0,1,4],[1,2,4],[2,3,4],[3,0,4],[0,3,2],[0,2,1]]
    return trimesh.Trimesh(np.array(V,float), np.array(F))


def disc(r, z, face_y, depth=0.15):
    """Zifferblatt-Scheibe an einer Schauseite (±Y)."""
    c = trimesh.creation.cylinder(radius=r, height=depth, sections=28)
    c.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2, [1,0,0]))
    c.apply_translation([0, face_y, z])
    return c


def ring_battlement(w, d, z0, merlon=0.6, h=0.9, gap=0.6, t=0.4):
    """einfacher Zinnenkranz als Quaderreihe entlang des Rands."""
    parts=[]; hw,hd=w/2,d/2
    per=2*(w+d); n=max(4,int(per/(merlon+gap)))
    # entlang 4 Kanten verteilen
    def place(x,y): parts.append(box(merlon,t,h,z0,x,y))
    xs=np.arange(-hw+merlon/2,hw,merlon+gap)
    for x in xs: place(x,-hd); place(x,hd)
    ys=np.arange(-hd+merlon/2,hd,merlon+gap)
    for y in ys: place(-hw,y); place(hw,y)
    return trimesh.util.concatenate(parts) if parts else None


def build(cfg):
    m = cfg["massing"]; W=m["W"]; D=m["D"]; H=m["H_tower"]
    parts = {}
    # Turmschaft (ggf. mit Tordurchfahrt abgezogen)
    shaft = box(W, D, H, 0)
    g = cfg.get("durchfahrt")
    if g and g.get("enabled", True):
        arch = pointed_arch_prism(g["width"], g["jamb_h"], g["rise"], D)
        try:
            shaft = shaft.difference(arch)
        except Exception as ex:
            print(f"  WARN Durchfahrt-Bool fehlgeschlagen: {ex}")
    parts["turm"] = shaft
    # Helm
    h = cfg.get("helm", {})
    if h.get("enabled", True):
        parts["helm"] = pyramid(W*h.get("overhang",1.04), D*h.get("overhang",1.04),
                                h.get("height", H*0.45), H, hip=h.get("hip", 0.0))
        if h.get("finial", True):
            parts["knauf"] = box(0.4,0.4,1.6, H+h.get("height",H*0.45)-0.2)
    # Gesimse
    for i,z in enumerate(cfg.get("gesimse", [])):
        parts[f"gesims{i}"] = box(W+0.5, D+0.5, 0.35, z)
    # Uhr
    u = cfg.get("uhr")
    if u:
        r=u.get("r",1.4); z=u["z"]
        for fy in ([-D/2-0.05, D/2+0.05] if u.get("both_faces",True) else [D/2+0.05]):
            parts[f"uhr_{'n' if fy<0 else 's'}"] = disc(r, z, fy)
    # Zinnen
    zc = cfg.get("zinnen")
    if zc and zc.get("enabled"):
        rb = ring_battlement(W, D, zc.get("z", H-1.0), zc.get("merlon",0.6),
                             zc.get("h",0.9), zc.get("gap",0.6))
        if rb is not None: parts["zinnen"]=rb
    # Rustika: Bruchstein-Sockel (unteres Schaftband) + Eckquader-Lisenen
    ru = cfg.get("rustika")
    if ru and ru.get("enabled", True):
        sh = ru.get("sockel_h", g["jamb_h"] + g["rise"] + 1.0 if g else 6.0)
        parts["sockel"] = box(W + 0.3, D + 0.3, sh, 0)      # proud stone base
        if g and g.get("enabled", True):                     # Tor wieder frei schneiden
            try: parts["sockel"] = parts["sockel"].difference(
                pointed_arch_prism(g["width"], g["jamb_h"], g["rise"], D + 0.5))
            except Exception: pass
        q = ru.get("quoin_w", 1.0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                parts[f"quoin_{sx}{sy}"] = box(q, q, H, 0, sx*(W/2-q*0.2), sy*(D/2-q*0.2))
    # Wappen-/Zierplatte auf der Schauseite
    wp = cfg.get("wappen")
    if wp:
        parts["wappen"] = box(wp.get("w",1.4), 0.25, wp.get("h",1.6), wp["z"], 0, D/2)
    # Ecktürmchen (Fialen mit Spitzdach an den 4 Parapet-Ecken)
    et = cfg.get("ecktuermchen")
    if et and et.get("enabled"):
        r = et.get("w", 1.2); eh = et.get("h", 5.0); z = et.get("z", H - 1.0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = sx*(W/2 - r*0.3), sy*(D/2 - r*0.3)
                parts[f"et_{sx}{sy}"] = box(r, r, eh, z, cx, cy)
                tip = pyramid(r*1.25, r*1.25, r*1.8, z+eh)
                tip.apply_translation([cx, cy, 0])
                parts[f"etH_{sx}{sy}"] = tip
    return parts


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",required=True)
    ap.add_argument("--no-render",action="store_true")
    a=ap.parse_args()
    cfg=json.load(open(a.config))
    out=cfg["out_dir"]; pre=cfg["prefix"]; os.makedirs(out,exist_ok=True)
    parts=build(cfg)
    col=cfg.get("colors",{})
    scene=trimesh.Scene()
    for name,mesh in parts.items():
        if mesh is None or len(mesh.faces)==0: continue
        mesh.export(f"{out}/{pre}_{name}.stl")
        base=name.split("_")[0].rstrip("0123456789")
        c=col.get(base) or col.get(name) or [180,150,120]
        mesh.visual.face_colors=np.array([*c,255],np.uint8)
        scene.add_geometry(mesh,geom_name=name)
    glb=f"{out}/{cfg.get('glb',pre+'_measured.glb')}"
    scene.export(glb)
    allm=trimesh.util.concatenate([m for m in parts.values() if m is not None and len(m.faces)])
    print(f"{len([p for p in parts.values() if p is not None])} Bauteile → {out}/")
    print(f"GLB → {glb}   gesamt {len(allm.faces):,} faces  bbox {allm.extents.round(1)}")

    if not a.no_render:
        try:
            import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            fig=plt.figure(figsize=(9,8))
            for i,(el,az,t) in enumerate([(10,-55,'3/4'),(4,0,'Front (Durchfahrt)')]):
                ax=fig.add_subplot(1,2,i+1,projection='3d')
                for name,mesh in parts.items():
                    if mesh is None or not len(mesh.faces): continue
                    base=name.split("_")[0].rstrip("0123456789")
                    c=np.array(col.get(base) or col.get(name) or [180,150,120])/255
                    V=np.array(mesh.vertices);F=np.array(mesh.faces)
                    ax.add_collection3d(Poly3DCollection(V[F],alpha=1,facecolor=c,edgecolor='k',linewidth=0.1))
                ext=allm.extents;ctr=allm.centroid;R=ext.max()/2
                for s,cc in zip('xyz',ctr): getattr(ax,f'set_{s}lim')(cc-R,cc+R)
                ax.set_box_aspect((1,1,1));ax.view_init(elev=el,azim=az);ax.set_axis_off();ax.set_title(t)
            plt.tight_layout();plt.savefig(f"{out}/{pre}_render.png",dpi=105)
            print(f"Render → {out}/{pre}_render.png")
        except Exception as ex:
            print(f"Render-Fehler: {ex}")


if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""bauwerk_szene.py — ein BAUWERK-Mesh ins echte LGL-Gelände setzen.

Nimmt ein (lokal zentriertes, in Metern gebautes) Bauwerk-STL und platziert es an
echten UTM-Koordinaten auf dem DGM1-Gelände: dreht es auf die Tal-/Schlucht-Achse,
setzt es auf die Geländehöhe, legt optional eine Wasserfläche an. Ausgabe:
interaktives Szenen-HTML (three.js, importmap+parse — lädt zuverlässig) + Render.

  python3 tools/bauwerk_szene.py --stl modelle/linachtalsperre/linach_bogenmauer.stl \\
    --dem daten/linach/linach_dem.npy --dem-origin daten/linach/linach_dem_origin.npy \\
    --E 447097.5 --N 5318581.4 --auto-axis --win 260 \\
    --lake daten/linach/lake_mask.npy --lake-z 847.5 \\
    --title "Linachtalsperre — echtes Tal + Gewölbereihe" --out modelle/linachtalsperre/linach_szene_bogen
"""
import argparse, base64, os, numpy as np, trimesh
from scipy.ndimage import gaussian_filter
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def granite_image(sz=512, courses=4):
    """Prozedurale Granit-Textur: graue Sprenkelung + versetzte Quader (Ashlar)."""
    from PIL import Image
    rng = np.random.default_rng(7)
    val = 138 + 9*gaussian_filter(rng.normal(0, 1, (sz, sz)), 1.8)      # weiche Wolken
    val += 20*(rng.random((sz, sz)) > 0.986) - 16*(rng.random((sz, sz)) > 0.986)  # Flecken
    img = np.dstack([val, val, val*0.985 + 3])                          # leicht kühl
    ch = sz // courses; bw = ch * 2; mortar = 96                        # Lager-/Stoßfugen
    for ci, y in enumerate(range(0, sz, ch)):
        img[y:y+3, :, :] = mortar
        off = bw//2 if ci % 2 else 0
        for x in range(off, sz+bw, bw):
            img[y:y+ch, (x % sz):(x % sz)+3, :] = mortar
    return Image.fromarray(np.clip(img, 40, 230).astype(np.uint8))


def box_uv(mesh, tile_m=4.0):
    """Box-Projektion: UV je Fläche nach dominanter Normalenachse (lokale Koords!)."""
    mesh.unmerge_vertices()                                            # je Fläche eigene Ecken
    V, F, Nf = mesh.vertices, mesh.faces, mesh.face_normals
    uv = np.zeros((len(V), 2))
    for fi, f in enumerate(F):
        ax = int(np.argmax(np.abs(Nf[fi])))
        pick = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[ax]
        for vi in f:
            uv[vi] = [V[vi, pick[0]]/tile_m, V[vi, pick[1]]/tile_m]
    return uv


def parse_lod2(src, E, N, win):
    """Amtliches LoD2-CityGML -> ECHTE Gebäude als trimesh in UTM-Weltkoordinaten.
    `src` = GML-Datei ODER Verzeichnis mit *.gml (2-km-Kachel). Nur Gebäude, deren erster
    Stützpunkt im Fenster [E±win, N±win] liegt. Streaming-Parse (memory-safe), posList ->
    Fan-Triangulierung (wie modelle/lod2_gen.py). Dach (Normale z>0.4) terracotta, Wand beige."""
    import glob, xml.etree.ElementTree as ET
    files = sorted(glob.glob(os.path.join(src, "*.gml"))) if os.path.isdir(src) else [src]
    ln = lambda t: t.split('}')[-1]
    X0, X1, Y0, Y1 = E-win, E+win, N-win, N+win
    V, F = [], []
    for gml in files:
        for ev, elem in ET.iterparse(gml, events=('end',)):
            if ln(elem.tag) not in ("Building", "BuildingPart"):
                continue
            rings = []
            for pl in elem.iter():
                if ln(pl.tag) == "posList" and pl.text:
                    n = pl.text.split()
                    if len(n) >= 9:
                        rings.append([(float(n[i]), float(n[i+1]), float(n[i+2]))
                                      for i in range(0, len(n)-2, 3)])
            elem.clear()
            if not rings:
                continue
            fx, fy = rings[0][0][0], rings[0][0][1]
            if not (X0 <= fx <= X1 and Y0 <= fy <= Y1):
                continue
            for ring in rings:
                if len(ring) >= 4 and ring[0] == ring[-1]:
                    ring = ring[:-1]
                if len(ring) < 3:
                    continue
                base = len(V); V.extend(ring)
                for i in range(1, len(ring)-1):
                    F.append([base, base+i, base+i+1])            # Fan-Triangulierung
    if not F:
        return None
    m = trimesh.Trimesh(np.array(V), np.array(F), process=False)
    nz = m.face_normals[:, 2]
    roof = np.abs(nz) > 0.4                                        # Dach/Boden vs. Wand
    fc = np.where(roof[:, None], np.array([190, 104, 78, 255]),    # Dach terracotta
                  np.array([206, 198, 184, 255]))                  # Wand beige
    m.visual.face_colors = fc.astype(np.uint8)
    print(f"LoD2: {len(files)} GML, {len(m.faces)} Dreiecke im Fenster {win} m, "
          f"z {m.bounds[0][2]:.0f}..{m.bounds[1][2]:.0f} m")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stl", required=True)
    ap.add_argument("--dem", required=True)
    ap.add_argument("--dem-origin", required=True, help=".npy [E0,N0] SW-Ecke, 1m-Zellen")
    ap.add_argument("--E", type=float, required=True); ap.add_argument("--N", type=float, required=True)
    ap.add_argument("--angle", type=float, default=None, help="Achs-Azimut Grad (sonst --auto-axis)")
    ap.add_argument("--auto-axis", action="store_true", help="Achse quer zum Gefälle aus DEM")
    ap.add_argument("--flip", action="store_true", help="Luftseite umdrehen")
    ap.add_argument("--base-dz", type=float, default=0.0, help="Bauwerk-Fuß relativ zur Geländehöhe")
    ap.add_argument("--y-off", type=float, default=0.0, help="Bauwerk quer verschieben (m)")
    ap.add_argument("--win", type=float, default=260.0, help="Gelände-Halbfenster m")
    ap.add_argument("--lake", default=""); ap.add_argument("--lake-z", type=float, default=0.0)
    ap.add_argument("--world", action="store_true", help="STL ist schon in UTM (kein Transform)")
    ap.add_argument("--lod2", default="", help="LoD2-CityGML (Datei ODER Kachel-Verzeichnis): echte Gebäude einblenden")
    ap.add_argument("--lod2-win", type=float, default=0.0, help="Gebäude-Fenster m (0=wie --win)")
    ap.add_argument("--textur", default="", choices=["", "granit"], help="Bauwerk-Textur")
    ap.add_argument("--title", default="Bauwerk im Gelände")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    A = np.load(a.dem).astype(float)
    A = np.where(A < -1000, np.nan, A)
    E0, N0 = np.load(a.dem_origin); ny, nx = A.shape
    cx = (a.E - 0.5 - E0); cy = ny - 1 - (a.N - 0.5 - N0)          # Zentrum in Zellen (col,row)
    c0, c1 = int(cx - a.win), int(cx + a.win)
    r0, r1 = int(cy - a.win), int(cy + a.win)
    c0, c1 = max(0, c0), min(nx, c1); r0, r1 = max(0, r0), min(ny, r1)

    # --- Achse: quer zum Gefälle ---
    if a.auto_axis:
        sm = gaussian_filter(np.nan_to_num(A, nan=np.nanmin(A)), 6)
        gy, gx = np.gradient(-sm)
        ri, ci = int(cy), int(cx)
        p = np.array([gx[ri-25:ri+26, ci-25:ci+26].mean(),
                      -gy[ri-25:ri+26, ci-25:ci+26].mean()])
        p /= np.hypot(*p)
    else:
        th = np.radians(a.angle or 0.0); p = np.array([np.sin(th), np.cos(th)])
    if a.flip: p = -p
    u = np.array([-p[1], p[0]])                                   # Achse = quer zu p
    print(f"Zentrum Zelle col={cx:.0f} row={cy:.0f}  downstream p={p.round(2)} Achse u={u.round(2)}")

    # --- z_floor (Geländehöhe an der Bauwerkslinie, luftseitig 30 m) ---
    z_floor = 0.0
    if not a.world:
        def hh(xu, pp):
            e = a.E + xu*u[0] + pp*p[0]; n = a.N + xu*u[1] + pp*p[1]
            c = int(min(max(e-0.5-E0, 0), nx-1)); r = int(min(max(ny-1-(n-0.5-N0), 0), ny-1))
            return A[r, c]
        bb = trimesh.load(a.stl, force="mesh").bounds
        Lhalf = (bb[1][0]-bb[0][0]) / 2
        z_floor = float(np.nanmin([hh(t, 25.0) for t in np.linspace(-Lhalf, Lhalf, 60)])) + a.base_dz
        print(f"z_floor = {z_floor:.1f} m")

    # --- Gelände-Mesh (UTM, Vertexfarben) ---
    st = max(1, int((c1-c0) / 300))
    sub = A[r0:r1:st, c0:c1:st]
    gny, gnx = sub.shape
    Ex = np.arange(c0, c1, st) + 0.5 + E0
    Ny = N0 + (ny-1 - np.arange(r0, r1, st)) + 0.5
    Xg, Yg = np.meshgrid(Ex, Ny)
    subf = np.nan_to_num(sub, nan=np.nanmin(sub))
    Vt = np.column_stack([Xg.ravel(), Yg.ravel(), subf.ravel()])
    Ft = []
    for i in range(gny-1):
        for j in range(gnx-1):
            k = i*gnx + j; Ft += [[k, k+1, k+gnx+1], [k, k+gnx+1, k+gnx]]
    terr = trimesh.Trimesh(Vt, np.array(Ft), process=False)
    # GRAUES Relief (Hillshade), nicht bunt/dunkel — wie Hirschsprung-Zusammenbau
    vn = terr.vertex_normals
    lt = np.array([-0.35, -0.35, 0.87]); lt /= np.linalg.norm(lt)
    sh = np.clip(vn @ lt, 0.25, 1.0)
    g = (165 + 70*sh).astype(np.uint8)                        # helles Grau 165..235
    terr.visual.vertex_colors = np.column_stack([g, g, g, np.full_like(g, 255)])

    # --- Bauwerk platzieren ---
    dam = trimesh.load(a.stl, force="mesh")
    if a.textur == "granit":
        from trimesh.visual import TextureVisuals
        from trimesh.visual.material import SimpleMaterial
        uv = box_uv(dam, tile_m=4.0)                       # unmerge + Box-UV (vor Transform)
        dam.visual = TextureVisuals(uv=uv, material=SimpleMaterial(image=granite_image()))
    if not a.world:
        V = dam.vertices.copy()
        lx, ly, lz = V[:, 0], V[:, 1] + a.y_off, V[:, 2]
        dam.vertices = np.column_stack([a.E + lx*u[0] + ly*p[0],
                                        a.N + lx*u[1] + ly*p[1], z_floor + lz])
    if a.textur != "granit":
        dam.visual.vertex_colors = [150, 146, 138, 255]
    # Achse aus dem Bauwerk selbst (für Render-Kamera) bei --world
    if a.world:
        PE = dam.vertices[:, :2] - dam.vertices[:, :2].mean(0)
        u = np.linalg.svd(PE, full_matrices=False)[2][0]; p = np.array([-u[1], u[0]])

    meshes = [("gelaende", terr), ("bauwerk", dam)]

    # --- LoD2-Gebäude (echte amtliche Dächer, UTM-Weltkoordinaten = deckungsgleich) ---
    if a.lod2:
        geb = parse_lod2(a.lod2, a.E, a.N, a.lod2_win or a.win)
        if geb is not None:
            meshes.append(("gebaeude", geb))

    # --- Wasser ---
    if a.lake:
        lk = np.load(a.lake)[r0:r1:st, c0:c1:st]
        Vw2 = np.column_stack([Xg.ravel(), Yg.ravel(), np.full(Xg.size, a.lake_z)]); Fw = []
        for i in range(gny-1):
            for j in range(gnx-1):
                if lk[i, j] and lk[i+1, j] and lk[i, j+1] and lk[i+1, j+1]:
                    k = i*gnx+j; Fw += [[k, k+1, k+gnx+1], [k, k+gnx+1, k+gnx]]
        if Fw:
            w = trimesh.Trimesh(Vw2, np.array(Fw), process=False)
            w.visual.vertex_colors = [40, 110, 180, 180]
            meshes.append(("wasser", w))

    # --- Szene -> GLB -> HTML ---
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    scene = trimesh.Scene()
    ctr = terr.vertices.mean(0)
    for nm, m in meshes:
        mm = m.copy(); mm.apply_translation(-ctr); scene.add_geometry(mm, geom_name=nm)
    b64 = base64.b64encode(scene.export(file_type="glb")).decode()
    html = f"""<!doctype html><meta charset=utf-8><title>{a.title}</title>
<style>body{{margin:0;background:#dde6ef;font-family:sans-serif}}
#i{{position:fixed;left:10px;top:10px;z-index:9;background:#000a;color:#fff;padding:8px 12px;border-radius:8px;font-size:13px;line-height:1.4}}
#c{{position:fixed;right:10px;top:10px;z-index:9;background:#000a;color:#fff;padding:10px 12px;border-radius:8px;font-size:13px;line-height:2}}
#c input{{vertical-align:middle;width:120px}}</style>
<div id=i><b>{a.title}</b><br><span style=color:#bcd>Maus: drehen · Rad: zoom · rechts: verschieben</span></div>
<div id=c><label>Gelände-Durchsicht <input id=sT type=range min=0 max=100 value=55 oninput=setTerr(this.value)></label><br>
<label>Bauwerk-Durchsicht <input id=sB type=range min=0 max=100 value=100 oninput=setBau(this.value)></label><br>
<label>Gebäude-Durchsicht <input id=sG type=range min=0 max=100 value=100 oninput=setGeb(this.value)></label></div>
<script type="importmap">{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}}}</script>
<script type=module>
import*as T from"three";import{{OrbitControls}}from"three/addons/controls/OrbitControls.js";
import{{GLTFLoader}}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0xdde6ef);sc.fog=new T.Fog(0xdde6ef,900,2600);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,8000);
const rn=new T.WebGLRenderer({{antialias:true}});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.AmbientLight(0xffffff,0.75));sc.add(new T.HemisphereLight(0xffffff,0x556677,1.0));
const sun=new T.DirectionalLight(0xfff2e0,1.2);sun.position.set(-140,120,180);sc.add(sun);
const b=atob("{b64}");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
let terr=[],bau=[],geb=[];
new GLTFLoader().parse(ar.buffer,"",g=>{{const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const all=[];o.traverse(m=>{{if(m.isMesh)all.push(m);}});
 all.forEach(m=>{{m.material.side=T.DoubleSide;
  const n=((m.name||"")+"|"+((m.parent&&m.parent.name)||"")).toLowerCase();
  if(n.includes("gelaende")||n.includes("wasser")){{m.material.transparent=true;m.material.opacity=0.55;terr.push(m);}}
  else if(n.includes("gebaeude")){{geb.push(m);}}
  else bau.push(m);}});
 if(!terr.length&&all.length){{ // Fallback: größtes Mesh = Gelände
  let big=all[0],bv=0;all.forEach(m=>{{const p=m.geometry.attributes.position;if(p&&p.count>bv){{bv=p.count;big=m;}}}});
  big.material.transparent=true;big.material.opacity=0.55;terr=[big];bau=all.filter(m=>m!==big);}}
 const bb=new T.Box3().setFromObject(o),c=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(c);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.5,d*0.45,d*0.9);cam.lookAt(0,0,0);ct.update();
}},e=>{{document.getElementById("i").innerHTML+="<br><span style=color:#f88>LOAD "+e+"</span>";}});
window.setTerr=v=>{{const o=v/100;terr.forEach(m=>{{m.material.opacity=o;m.material.transparent=o<1;m.visible=o>0;}});}};
window.setBau=v=>{{const o=v/100;bau.forEach(m=>{{m.material.opacity=o;m.material.transparent=o<1;m.visible=o>0;}});}};
window.setGeb=v=>{{const o=v/100;geb.forEach(m=>{{m.material.opacity=o;m.material.transparent=o<1;m.visible=o>0;}});}};
addEventListener("resize",()=>{{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);}});
(function an(){{requestAnimationFrame(an);ct.update();rn.render(sc,cam);}})();
</script>"""
    open(a.out + ".html", "w").write(html)
    print(f"HTML -> {a.out}.html ({len(html)//1024} kB)")

    # --- statische Render zum Prüfen der Platzierung (2 Blickwinkel) ---
    # Höhen-Schattierung fürs Gelände
    tn = terr.face_normals; tsh = 0.5 + 0.5*np.clip(tn[:, 2], 0, 1)
    gg = 0.62 + 0.28*tsh                                       # graues Relief
    tcol = np.column_stack([gg, gg, gg, np.ones_like(gg)])
    face_azim = float(np.degrees(np.arctan2(p[1], p[0])))      # Blick senkrecht auf die Front
    for tag, (elev, azim) in {"a": (8, face_azim), "b": (78, face_azim)}.items():
        fig = plt.figure(figsize=(9, 6)); ax = fig.add_subplot(111, projection="3d")
        pc = Poly3DCollection(terr.triangles, edgecolor="none"); pc.set_facecolor(tcol)
        ax.add_collection3d(pc)
        if "wasser" in dict(meshes):
            ax.add_collection3d(Poly3DCollection(dict(meshes)["wasser"].triangles,
                                facecolor=(0.18, 0.45, 0.72, 0.8), edgecolor="none"))
        ax.add_collection3d(Poly3DCollection(dam.triangles, facecolor=(0.93, 0.55, 0.30),
                            edgecolor="none"))                      # Mauer kräftig orange = sofort sichtbar
        if "gebaeude" in dict(meshes):
            ax.add_collection3d(Poly3DCollection(dict(meshes)["gebaeude"].triangles,
                                facecolor=(0.72, 0.45, 0.33), edgecolor=(0.3, 0.2, 0.15, 0.4),
                                linewidths=0.2))                    # echte LoD2-Gebäude
        allv = np.vstack([terr.vertices, dam.vertices])
        for s, v in zip("xyz", range(3)):
            getattr(ax, f"set_{s}lim")(allv[:, v].min(), allv[:, v].max())
        ax.set_box_aspect((np.ptp(allv[:,0]), np.ptp(allv[:,1]), np.ptp(allv[:,2])*1.6))
        ax.view_init(elev=elev, azim=azim); ax.set_axis_off()
        fig.tight_layout(); fig.savefig(f"{a.out}_render_{tag}.png", dpi=115, facecolor="#aeb7c0")
        plt.close(fig)
    print(f"Render -> {a.out}_render_a.png (schräg) + _render_b.png (oben)")


if __name__ == "__main__":
    main()

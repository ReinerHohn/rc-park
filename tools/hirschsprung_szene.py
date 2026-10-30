#!/usr/bin/env python3
"""hirschsprung_szene.py — Steil-Basis (echtes LGL-DGM1, 1:160, KEINE Überhöhung)
+ Felsbank (ebene Trasse ≥24 mm) + ECHTER Tunnel (N-Lichtraum 30x36 mm, durchgebohrt)
+ Hirsch auf Felspfeiler.

Geometrie des Steil-Fensters (E=425544, 70x44 m):
  - Talboden am Süd-Rand (niedriges N), Hang steigt nach Norden
  - Talboden steigt nach OSTEN ~13 m an
  → Trasse läuft eben (konstante Höhe) am Tal entlang (E-Achse). Im Westen
    liegt sie frei auf der Felsbank; nach Osten wächst der Fels über sie →
    automatisch TUNNEL. Portal dort, wo Fels erstmals voll deckt.
"""
import numpy as np, trimesh
import trimesh.transformations as T

SCALE = 160.0
MM = 1000.0 / SCALE                 # 6.25 mm/m
GRID = "daten/hoellental/grid2k.npy"
E0 = 425000
WE, WN = 70, 44                     # Steil-Fenster (m)
WIN_E = (515, 585)                 # GENEHMIGTES Fenster (pixelgleich steilste-Viewer)
WIN_N = (755, 799)                 # E=425515, Relief 25.8 m; NICHT ändern (abgenommen)

# NEM-N Lichtraum (Modell-mm, ABSOLUT – nicht skaliert)
CLEAR_W, CLEAR_H = 30.0, 36.0
RAIL_SINK = 6.0                     # Trog unter SO (Planum/Schotter)
BENCH_W = 30.0                      # Felsbank-Breite (≥24 für N-Gleis + Rand)
TRACK_ROW = 6                      # N-Zeile der Trasse (m vom Süd-Talboden)
PORTAL_PAD = 2.0                   # Puffer

OUT = "modelle/3d_druck/hirschsprung_szene.stl"
HTML = "modelle/hirschsprung_szene_final_3d.html"


def solidify(xs, ys, zz):
    nx, ny = len(xs), len(ys)
    TX, TY = np.meshgrid(xs, ys)
    top = np.column_stack([TX.ravel(), TY.ravel(), zz.ravel()])
    bot = np.column_stack([TX.ravel(), TY.ravel(), np.zeros(nx*ny)])
    V = np.vstack([top, bot]); nt = nx*ny
    def t(r,c): return r*nx+c
    def b(r,c): return nt + r*nx+c
    F = []
    for r in range(ny-1):
        for c in range(nx-1):
            F += [[t(r,c),t(r+1,c),t(r+1,c+1)], [t(r,c),t(r+1,c+1),t(r,c+1)]]
            F += [[b(r,c),b(r+1,c+1),b(r+1,c)], [b(r,c),b(r,c+1),b(r+1,c+1)]]
    R=ny-1; C=nx-1
    for c in range(nx-1):
        F += [[t(0,c),t(0,c+1),b(0,c)], [t(0,c+1),b(0,c+1),b(0,c)]]
        F += [[t(R,c),b(R,c),t(R,c+1)], [t(R,c+1),b(R,c),b(R,c+1)]]
    for r in range(ny-1):
        F += [[t(r,0),b(r,0),t(r+1,0)], [t(r+1,0),b(r,0),b(r+1,0)]]
        F += [[t(r,C),t(r+1,C),b(r,C)], [t(r+1,C),b(r+1,C),b(r,C)]]
    m = trimesh.Trimesh(V, np.array(F), process=False)
    trimesh.repair.fix_normals(m)
    return m


def deer(scale=1.0):
    """Stilisierter Hirsch (N ~12 mm hoch): Körper, 4 Beine, Hals, Kopf, Geweih."""
    parts = []
    def cyl(r,h,tf):
        c = trimesh.creation.cylinder(radius=r, height=h, sections=10); c.apply_transform(tf); return c
    body = trimesh.creation.icosphere(subdivisions=1, radius=1.0)
    body.apply_scale([2.6, 1.1, 1.3]); body.apply_translation([0,0,6.0]); parts.append(body)
    for sx in (-1,1):
        for ey in (-0.7,0.7):
            parts.append(cyl(0.35, 6.0, T.translation_matrix([sx*2.0, ey, 3.0])))
    # Hals + Kopf (vorne = +X)
    neck = cyl(0.6, 4.5, T.concatenate_matrices(
        T.translation_matrix([3.0, 0, 8.0]), T.rotation_matrix(np.radians(40),[0,1,0])))
    parts.append(neck)
    head = trimesh.creation.icosphere(subdivisions=1, radius=0.9)
    head.apply_scale([1.6,0.9,0.9]); head.apply_translation([4.3,0,9.8]); parts.append(head)
    # Geweih (zwei geweihte Stangen)
    for ey in (-0.5,0.5):
        parts.append(cyl(0.22, 3.0, T.concatenate_matrices(
            T.translation_matrix([4.3, ey, 11.5]), T.rotation_matrix(np.radians(20),[0,1,0]))))
        parts.append(cyl(0.18, 1.6, T.translation_matrix([3.6, ey, 12.8])))
        parts.append(cyl(0.18, 1.6, T.translation_matrix([5.0, ey, 12.8])))
    d = trimesh.util.concatenate(parts)
    d.apply_scale(scale)
    return d


def main():
    g = np.load(GRID)
    win = g[WIN_N[0]:WIN_N[1], WIN_E[0]:WIN_E[1]].astype(float)
    ny, nx = win.shape
    zmin = win.min()
    relief = win.max() - zmin
    print(f"Steil-Fenster {nx}x{ny} m | Relief {relief:.1f} m")

    xs = np.arange(nx) * MM          # E
    ys = np.arange(ny) * MM          # N
    zz = (win - zmin) * MM
    terr = solidify(xs, ys, zz)
    print(f"Basis: {len(terr.faces)} faces, {nx*MM:.0f}x{ny*MM:.0f}x{zz.max():.0f} mm, vol={terr.is_volume}")

    # ---- Trasse: eben am Talboden (konst. Höhe), E-Achse ----
    y_tr = TRACK_ROW * MM
    # Trassenhöhe = Talbodenhöhe am WEST-Portal (damit West frei, Ost gedeckt)
    floor_w = (win[TRACK_ROW, 0:8].min() - zmin) * MM
    z_rail = floor_w + 3.0           # SO leicht über West-Talboden
    print(f"Trasse N-Zeile {TRACK_ROW} (y={y_tr:.0f} mm), SO z={z_rail:.0f} mm")

    # Fels-Höhe entlang Trasse → Tunnel wo Fels > SO+Lichtraum
    rock = (win[TRACK_ROW, :] - zmin) * MM
    roof = z_rail + CLEAR_H
    tun_cols = np.where(rock > roof + 1)[0]
    if len(tun_cols):
        print(f"TUNNEL: Fels deckt ab E-Spalte {tun_cols[0]} (x={tun_cols[0]*MM:.0f} mm) "
              f"bis Ost-Rand → ~{(nx-tun_cols[0])*MM:.0f} mm Tunnel")

    # ---- Felsbank + Lichtraum-Kanal in EINEM: flacher Boden (z_rail-RAIL_SINK),
    #      begrenzte Höhe (CLEAR_H+RAIL_SINK) → über Fels = Tunnel, über Tal = Trog.
    #      Breite BENCH_W (≥24) gibt die ebene Bank; NICHT nach oben durchfräsen
    #      (sonst kein Tunneldach). ----
    ch_h = CLEAR_H + RAIL_SINK
    cutter = trimesh.creation.box(extents=[nx*MM + 20, BENCH_W, ch_h])
    cutter.apply_translation([nx*MM/2, y_tr, (z_rail - RAIL_SINK) + ch_h/2])
    model = terr.difference(cutter)
    print(f"Felsbank+Tunnel gefräst: faces={len(model.faces)} euler={model.euler_number} "
          f"(≤0 = echtes Loch) wt={model.is_watertight}")

    # ---- Hirsch auf schlankem Felspfeiler, VOR dem Portal aus dem Talboden ----
    portal_x = tun_cols[0]*MM if len(tun_cols) else nx*MM*0.7
    px = portal_x - 14                         # etwas westlich = vor dem Portal, frei
    py = max(1.0*MM, y_tr - BENCH_W/2 - 8)     # talseitig neben der Trasse
    pr = int(round(py/MM)); pc = int(round(px/MM))
    pr = min(max(pr,0),ny-1); pc=min(max(pc,0),nx-1)
    foot = (win[pr,pc]-zmin)*MM
    top = z_rail + CLEAR_H + 18                 # Pfeiler ragt deutlich übers Portal
    pil_h = top - foot
    pillar = trimesh.creation.cylinder(radius=3.5, height=pil_h, sections=7)
    pillar.apply_scale([1.25, 1.0, 1.0])       # leicht felsig/unregelmäßig
    pillar.apply_translation([px, py, foot + pil_h/2])
    h = deer(scale=1.05)                        # ~13.5 mm hoch (N-Hirsch mit Geweih)
    h.apply_transform(T.rotation_matrix(np.radians(-90), [0,0,1]))  # Blick ins Tal (Sprung)
    h.apply_translation([px, py, top])
    print(f"Hirsch+Pfeiler @ x={px:.0f} y={py:.0f}: Fuß z={foot:.0f}, Pfeiler {pil_h:.0f} mm, "
          f"Hirsch ~{h.bounds[1][2]-h.bounds[0][2]:.0f} mm")

    scene_full = trimesh.util.concatenate([model, pillar, h])
    model.export(OUT)
    scene_full.export(OUT.replace(".stl","_mit_hirsch.stl"))
    print(f"-> {OUT} (Gelände+Bank+Tunnel)  +  _mit_hirsch.stl (komplette Szene)")

    make_html(scene_full, model)


def make_html(scene_full, model):
    import base64
    glb = scene_full.export(file_type="glb")
    b64 = base64.b64encode(glb).decode()
    # Bewährtes Muster (= steilste-Viewer): importmap + data-URI load, Material im Callback
    html = """<!doctype html><html><head><meta charset=utf8><title>Hirschsprung N — Bank+Tunnel+Hirsch</title>
<style>body{margin:0;background:#cfe0ef;font-family:sans-serif}
#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.5}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body><div id=i><b>Hirschsprung — Spur N (1:160)</b><br>
echte LGL-Topo, KEINE Überhöhung<br>Felsbank + echter Tunnel (30×36 mm) + Hirsch auf Felspfeiler<br>
<span style=color:#8cf>Maus: drehen · Rad: zoom</span></div>
<script type=module>
import*as THREE from'three';
import{OrbitControls}from'three/addons/controls/OrbitControls.js';
import{GLTFLoader}from'three/addons/loaders/GLTFLoader.js';
const sc=new THREE.Scene();sc.background=new THREE.Color(0xcfe0ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,20000);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.7));sc.add(new THREE.HemisphereLight(0xffffff,0x5a6b50,1.1));
const d1=new THREE.DirectionalLight(0xffffff,1.3);d1.position.set(300,-400,600);sc.add(d1);
const mat=new THREE.MeshStandardMaterial({color:0xb9a98a,roughness:1,side:THREE.DoubleSide,flatShading:true});
new GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{
 const m=g.scene;m.traverse(o=>{if(o.isMesh){o.material=mat;o.geometry.computeVertexNormals();}});
 const box=new THREE.Box3().setFromObject(m);const c=box.getCenter(new THREE.Vector3());const s=box.getSize(new THREE.Vector3());
 m.position.sub(c);sc.add(m);
 const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.8,-d*1.1,d*0.7);cam.lookAt(0,0,0);ct.update();
},undefined,e=>{document.getElementById('i').innerHTML+='<br><span style=color:#f88>LOAD-FEHLER: '+e+'</span>';});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam)})();
</script></body></html>""".replace("%B64%", b64)
    with open(HTML,"w") as f: f.write(html)
    print(f"-> {HTML}")


if __name__ == "__main__":
    main()

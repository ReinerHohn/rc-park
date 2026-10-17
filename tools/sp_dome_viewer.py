#!/usr/bin/env python3
"""sp_dome_viewer.py — baut einen self-contained HTML-3D-Viewer der Petersdom-KUPPEL
(sp-dome-led.stl) mit MARKIERTEN LED-Löchern:
  - rote Kugel an jedem 0805-Steckschlitz
  - oranger Pfeil = Lichtaustrittsrichtung
  - Kuppel als halbtransparentes Mesh, damit man die Schlitze auch im Profil sieht.
GLB wird base64 in die HTML eingebettet (keine externen Dateien nötig).
"""
import sys, base64, json, numpy as np, trimesh
sys.path.insert(0, "tools")
import light_prep as L

STL = "modelle/3d_druck/sp-dome-led-bored.stl"
OUT = "modelle/sp_dome_loecher_3d.html"

# Marker = exakt die echten Bohrpositionen aus sp_led_dome_bores.py
import importlib.util
_spec = importlib.util.spec_from_file_location("sp_bores", "tools/sp_led_dome_bores.py")
_bores_mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_bores_mod)

def main():
    m = trimesh.load(STL, force="mesh")
    cx, cy = m.vertices[:, 0].mean(), m.vertices[:, 1].mean()
    # echte Bohrungen (inkl. Laternen-Kranz) am UNGEBOHRTEN Modell bestimmen
    base = trimesh.load(_bores_mod.SRC, force="mesh"); base.apply_scale(_bores_mod.SCALE)
    bores = _bores_mod.build_bores(base, cx, cy)

    # Marker-Daten (rote Kugel + orange Richtung)
    marks = []
    for b in bores:
        if b["type"] != "bore":
            continue
        p = np.array(b["pos"], float)
        d = np.array(b["dir"], float); d /= (np.linalg.norm(d) + 1e-9)
        marks.append({"p": [round(float(x), 2) for x in p],
                      "d": [round(float(x), 3) for x in d]})

    # Kuppel → GLB → base64
    glb = m.export(file_type="glb")
    b64 = base64.b64encode(glb).decode()

    bounds = m.bounds
    size = (bounds[1] - bounds[0])
    diag = float(np.linalg.norm(size))
    msz = round(diag * 0.012, 2)   # Markerradius ~1.2% der Diagonale

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Petersdom-Kuppel — LED-Löcher</title>
<style>body{{margin:0;background:#0d1016;font-family:sans-serif;color:#ccc;overflow:hidden}}
#info{{position:fixed;top:10px;left:12px;z-index:10;font-size:13px;line-height:1.6}}
b{{color:#ffd27f}} .r{{color:#ff5a5a}} .o{{color:#ffa23a}}
#btn{{position:fixed;top:12px;right:12px;z-index:10}}
button{{background:#223;color:#cde;border:1px solid #456;border-radius:6px;padding:6px 10px;cursor:pointer}}</style>
</head><body>
<div id="info"><b>Petersdom-Kuppel</b> &mdash; {len(marks)} LED-Durchbohrungen (&Oslash;3&ndash;3,5 mm)<br>
<span class="r">&#9679; rote Kugel</span> = Loch &middot; <span class="o">&#8599; oranger Pfeil</span> = Lichtrichtung<br>
16 Balkon &middot; 8 Laternenfu&szlig; &middot; 6 Laternen-KRANZ &middot; 1 Spitze<br>
Maus: <b>links</b> drehen &middot; <b>Rad</b> zoomen &middot; <b>rechts</b> schieben</div>
<div id="btn"><button id="t">Kuppel transparent: AN</button></div>
<script type="importmap">{{"imports":{{
"three":"https://unpkg.com/three@0.160.0/build/three.module.js",
"three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}}}</script>
<script type="module">
import * as THREE from 'three';
import {{OrbitControls}} from 'three/addons/controls/OrbitControls.js';
import {{GLTFLoader}} from 'three/addons/loaders/GLTFLoader.js';

const MARKS = {json.dumps(marks)};
const MSZ = {msz};

const sc=new THREE.Scene(); sc.background=new THREE.Color(0x0d1016);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,20000);
const rn=new THREE.WebGLRenderer({{antialias:true}}); rn.setSize(innerWidth,innerHeight);
rn.setPixelRatio(devicePixelRatio); document.body.appendChild(rn.domElement);
const ctl=new OrbitControls(cam,rn.domElement); ctl.enableDamping=true;
sc.add(new THREE.HemisphereLight(0xffffff,0x334455,1.2));
const dl=new THREE.DirectionalLight(0xffffff,1.3); dl.position.set(400,-500,900); sc.add(dl);

let dome=null;
const loader=new GLTFLoader();
loader.load("data:model/gltf-binary;base64,{b64}", g=>{{
  dome=g.scene;
  dome.traverse(o=>{{ if(o.isMesh){{
    o.material=new THREE.MeshStandardMaterial({{color:0xe8e0c8,transparent:true,opacity:0.45,
      roughness:0.9,metalness:0.0,side:THREE.DoubleSide}});
  }}}});
  sc.add(dome);

  // Bounding → Kamera + Marker-Gruppe zentrieren
  const box=new THREE.Box3().setFromObject(dome);
  const c=box.getCenter(new THREE.Vector3());
  const s=box.getSize(new THREE.Vector3());
  const r=Math.max(s.x,s.y,s.z);
  cam.position.set(c.x+r*1.1, c.y-r*1.4, c.z+r*0.9);
  ctl.target.copy(c); ctl.update();

  // Marker
  const sphGeo=new THREE.SphereGeometry(MSZ,16,16);
  const sphMat=new THREE.MeshStandardMaterial({{color:0xff3030,emissive:0x660000}});
  for(const mk of MARKS){{
    const p=new THREE.Vector3(mk.p[0],mk.p[1],mk.p[2]);
    const sph=new THREE.Mesh(sphGeo,sphMat); sph.position.copy(p); sc.add(sph);
    const dir=new THREE.Vector3(mk.d[0],mk.d[1],mk.d[2]).normalize();
    const arr=new THREE.ArrowHelper(dir,p,MSZ*4,0xffa23a,MSZ*2,MSZ*1.3); sc.add(arr);
  }}
}});

document.getElementById("t").onclick=e=>{{
  if(!dome)return; let on=false;
  dome.traverse(o=>{{ if(o.isMesh){{ o.material.opacity=o.material.opacity>0.7?0.45:0.95; on=o.material.opacity<0.7; }}}});
  e.target.textContent="Kuppel transparent: "+(on?"AN":"AUS");
}};

addEventListener("resize",()=>{{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);}});
(function loop(){{requestAnimationFrame(loop);ctl.update();rn.render(sc,cam);}})();
</script></body></html>"""

    open(OUT, "w").write(html)
    print(f"{len(marks)} Marker, GLB {len(glb)/1e6:.1f} MB -> {OUT} "
          f"({len(html)/1e6:.1f} MB HTML)")

if __name__ == "__main__":
    main()

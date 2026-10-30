#!/usr/bin/env python3
"""stl_html_viewer.py — GENERISCH: ein/mehrere STL als selbst-enthaltene three.js-HTML.

Jedes Teil base64-eingebettet (kein Server/kein CORS), eigene Farbe, Z-up→Y-up,
auto-zentriert + auto-Kamera. Für den „nach jedem Schritt ein 3D-HTML"-Workflow.

  python3 tools/stl_html_viewer.py --out modelle/x/szene.html --title "Hofgut Sternen" \
      --part hofgut_lod2.stl:#b8a890:LOD2-Gerüst  --part sockel.stl:#8a8278:Sockel
"""
import argparse, base64, os


HTML = """<!doctype html><meta charset=utf-8><title>{title}</title>
<style>body{{margin:0;background:#0d1117;font-family:system-ui;color:#cdd}}
#i{{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;text-shadow:0 1px 3px #000;line-height:1.5}}
#lg{{position:fixed;right:12px;top:10px;z-index:9;font-size:12px;text-align:right;line-height:1.6}}
.sw{{display:inline-block;width:11px;height:11px;margin-left:6px;border:1px solid #0008;vertical-align:middle}}</style>
<div id=i><b>{title}</b><br><span style=color:#8cf>Maus: drehen · Rad: zoom · rechts: verschieben</span><br>{sub}</div>
<div id=lg>{legend}</div>
<script type="importmap">{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}}}</script>
<script type=module>
import*as T from"three";import{{OrbitControls}}from"three/addons/controls/OrbitControls.js";
import{{STLLoader}}from"three/addons/loaders/STLLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0x0d1117);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,20000);
const rn=new T.WebGLRenderer({{antialias:true}});rn.setSize(innerWidth,innerHeight);
rn.shadowMap.enabled=true;document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x33404d,0.85));
const sun=new T.DirectionalLight(0xfff2e0,1.25);sun.position.set(-80,140,90);sun.castShadow=true;sc.add(sun);
sc.add(new T.AmbientLight(0x404854,0.5));
const loader=new STLLoader();const parts={parts};
const grp=new T.Group();
function b64(s){{const b=atob(s),a=new Uint8Array(b.length);for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return a.buffer;}}
for(const p of parts){{
  const g=loader.parse(b64(p.d));g.computeVertexNormals();
  const m=new T.Mesh(g,new T.MeshStandardMaterial({{color:p.c,roughness:0.88,metalness:0.02,flatShading:p.flat||false}}));
  m.castShadow=true;m.receiveShadow=true;grp.add(m);
}}
grp.rotation.x=-Math.PI/2;                      // Z-up (CityGML) -> Y-up (three)
sc.add(grp);
const box=new T.Box3().setFromObject(grp);const ctr=box.getCenter(new T.Vector3());const sz=box.getSize(new T.Vector3());
grp.position.sub(ctr);
const R=Math.max(sz.x,sz.y,sz.z);
// Boden
const gp=new T.Mesh(new T.PlaneGeometry(R*4,R*4),new T.MeshStandardMaterial({{color:0x2a2f26,roughness:1}}));
gp.rotation.x=-Math.PI/2;gp.position.y=-sz.z/2;gp.receiveShadow=true;sc.add(gp);
cam.position.set(R*0.9,R*0.75,R*1.1);ct.target.set(0,0,0);ct.update();
addEventListener("resize",()=>{{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);}});
(function loop(){{requestAnimationFrame(loop);ct.update();rn.render(sc,cam);}})();
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="Modell")
    ap.add_argument("--sub", default="")
    ap.add_argument("--part", action="append", default=[],
                    help="pfad.stl:#farbe:Label[:flat]  (relativ zum --out-Ordner ok)")
    a = ap.parse_args()

    base = os.path.dirname(os.path.abspath(a.out))
    parts_js, legend = [], []
    for spec in a.part:
        toks = spec.split(":")
        path, col = toks[0], toks[1]
        label = toks[2] if len(toks) > 2 else os.path.basename(path)
        flat = (len(toks) > 3 and toks[3] == "flat")
        p = path if os.path.isabs(path) else (path if os.path.exists(path) else os.path.join(base, path))
        d = base64.b64encode(open(p, "rb").read()).decode()
        parts_js.append('{"d":"%s","c":0x%s,"flat":%s}' % (d, col.lstrip("#"), "true" if flat else "false"))
        legend.append(f'{label}<span class=sw style="background:{col}"></span>')

    html = HTML.format(title=a.title, sub=a.sub,
                       legend="<br>".join(legend),
                       parts="[" + ",".join(parts_js) + "]")
    os.makedirs(base, exist_ok=True)
    open(a.out, "w").write(html)
    kb = os.path.getsize(a.out) / 1024
    print(f"-> {a.out}  ({kb:.0f} kB, {len(a.part)} Teile)")


if __name__ == "__main__":
    main()

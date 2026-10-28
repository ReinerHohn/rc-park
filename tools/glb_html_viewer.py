#!/usr/bin/env python3
"""glb_html_viewer.py — GENERISCH: ein texturiertes glb → selbst-enthaltenes three.js-HTML.
glb wird base64 eingebettet (kein Server/kein CORS), GLTFLoader + OrbitControls.
Mit --ref <foto> wird links das echte Referenzfoto eingebettet (Vergleich Modell↔Realität).

  python3 tools/glb_html_viewer.py --glb modelle/x/y.glb --out y.html --title "..." [--ref foto.jpg]
"""
import argparse, base64, os, mimetypes

HTML = """<!doctype html><meta charset=utf-8><title>{title}</title>
<style>
html,body{{margin:0;height:100%;background:#1c2229;font-family:system-ui;color:#e7edf3;overflow:hidden}}
#bar{{position:fixed;left:0;top:0;right:0;height:38px;background:#11151b;display:flex;align-items:center;
  padding:0 14px;z-index:20;font-size:14px;gap:10px;border-bottom:1px solid #2a323c}}
#bar b{{font-size:15px}} #bar span{{color:#8fb0cf;font-size:12px}}
#wrap{{position:fixed;top:38px;left:0;right:0;bottom:0;display:flex}}
#ref{{width:{refw};height:100%;background:#0d1014;display:{refdisp};flex-direction:column;border-right:2px solid #2a323c}}
#ref .lbl{{padding:5px 10px;font-size:12px;color:#9fb6cc;background:#11151b}}
#ref .imgbox{{flex:1;display:flex;align-items:center;justify-content:center;overflow:hidden}}
#ref img{{max-width:100%;max-height:100%;object-fit:contain}}
#view{{flex:1;position:relative}} #view .lbl{{position:absolute;left:10px;top:8px;z-index:9;font-size:12px;color:#9fb6cc;text-shadow:0 1px 3px #000}}
canvas{{display:block}}
</style>
<div id=bar><b>{title}</b><span>{sub}</span><span style="margin-left:auto">Maus: drehen · Rad: zoom · rechts: verschieben</span></div>
<div id=wrap>
  <div id=ref><div class=lbl>Echtes Foto</div><div class=imgbox><img src="{ref}"></div></div>
  <div id=view><div class=lbl>3D-Modell (aus Fotos vermessen)</div></div>
</div>
<script type="importmap">{{"imports":{{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}}}</script>
<script type=module>
import*as T from"three";import{{OrbitControls}}from"three/addons/controls/OrbitControls.js";
import{{GLTFLoader}}from"three/addons/loaders/GLTFLoader.js";
const view=document.getElementById("view");
const W=()=>view.clientWidth,H=()=>view.clientHeight;
const sc=new T.Scene();sc.background=new T.Color(0x1c2229);
const cam=new T.PerspectiveCamera(42,W()/H(),0.05,5000);
const rn=new T.WebGLRenderer({{antialias:true}});rn.setSize(W(),H());
rn.outputColorSpace=T.SRGBColorSpace;view.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x888877,2.0));
const s=new T.DirectionalLight(0xfff4e0,2.3);s.position.set(0.4,0.8,1.0);sc.add(s);
sc.add(new T.AmbientLight(0xffffff,0.5));
const B64="{b64}";
function toBuf(b){{const s=atob(b),a=new Uint8Array(s.length);for(let i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a.buffer;}}
new GLTFLoader().parse(toBuf(B64),"",g=>{{
  g.scene.rotation.x=-Math.PI/2;
  const box=new T.Box3().setFromObject(g.scene);const c=box.getCenter(new T.Vector3());const sz=box.getSize(new T.Vector3());
  g.scene.position.sub(c);sc.add(g.scene);
  const R=Math.max(sz.x,sz.y,sz.z);
  cam.position.set(0,R*0.12,R*1.5);ct.target.set(0,0,0);ct.update();
  const gp=new T.Mesh(new T.PlaneGeometry(R*4,R*4),new T.MeshStandardMaterial({{color:0x2a333d}}));
  gp.rotation.x=-Math.PI/2;gp.position.y=-sz.z/2;sc.add(gp);
}});
addEventListener("resize",()=>{{cam.aspect=W()/H();cam.updateProjectionMatrix();rn.setSize(W(),H());}});
(function loop(){{requestAnimationFrame(loop);ct.update();rn.render(sc,cam);}})();
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="3D-Modell")
    ap.add_argument("--sub", default="")
    ap.add_argument("--ref", default="", help="optionales Referenzfoto (wird links eingebettet)")
    a = ap.parse_args()
    b64 = base64.b64encode(open(a.glb, "rb").read()).decode()
    ref_uri, refdisp, refw = "", "none", "0"
    if a.ref:
        mt = mimetypes.guess_type(a.ref)[0] or "image/jpeg"
        ref_uri = f"data:{mt};base64," + base64.b64encode(open(a.ref, "rb").read()).decode()
        refdisp, refw = "flex", "42%"
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w").write(HTML.format(title=a.title, sub=a.sub, b64=b64,
                                       ref=ref_uri, refdisp=refdisp, refw=refw))
    print(f"-> {a.out}  ({os.path.getsize(a.out)/1024:.0f} kB, glb+Foto eingebettet)")


if __name__ == "__main__":
    main()

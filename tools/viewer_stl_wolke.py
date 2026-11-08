#!/usr/bin/env python3
"""viewer_stl_wolke.py - 3D-HTML (three.js r128, Skript statt Modul): STL-Ebenen (mm, Massstab) + Punktwolke mit Fotofarben im SELBEN Rahmen, Ebenen schaltbar.
  venv-seg/bin/python -I tools/viewer_stl_wolke.py --aus x.html --titel T --massstab 87 --wolke modell.npy --farben farben.npy [--n 250000] [--rand 2] \
      --teil name:#farbe:pfad.stl[:aus] ...
Wolke: Meter im Modellrahmen (zentrierung 'achse': Ursprung bleibt), wird mit 1000/massstab in den STL-Rahmen gebracht und auf die STL-Huelle + --rand m beschnitten."""
import argparse, base64, json, numpy as np, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("--aus", required=True); ap.add_argument("--titel", default="Modell"); ap.add_argument("--massstab", type=float, default=87)
ap.add_argument("--wolke"); ap.add_argument("--farben"); ap.add_argument("--n", type=int, default=250000); ap.add_argument("--rand", type=float, default=2.0)
ap.add_argument("--wolke2", help="zweite, getrennt schaltbare Wolke"); ap.add_argument("--farben2"); ap.add_argument("--name2", default="Wolke 2"); ap.add_argument("--n2", type=int, default=120000)
ap.add_argument("--teil", action="append", default=[]); a = ap.parse_args()
parts = []; lo = np.full(3, 1e9); hi = np.full(3, -1e9)
for s in a.teil:
    t = s.split(":"); n, c, p = t[0], t[1], t[2]; m = trimesh.load(p); lo = np.minimum(lo, m.bounds[0]); hi = np.maximum(hi, m.bounds[1])
    parts.append(dict(n=n, c=c, an=not (len(t) > 3 and t[3] == "aus"), d=base64.b64encode(open(p, "rb").read()).decode()))
cloud = None
if a.wolke:
    X = np.load(a.wolke).astype(np.float32); C = np.load(a.farben) if a.farben else np.full((len(X), 3), 200, np.uint8); k = a.massstab / 1000.0
    l, h = lo * k - a.rand, hi * k + a.rand; ok = np.all((X >= l) & (X <= h), 1); X, C = X[ok], C[ok]
    if len(X) > a.n: i = np.random.default_rng(1).choice(len(X), a.n, replace=False); X, C = X[i], C[i]
    X = X * (1000.0 / a.massstab); cloud = dict(p=base64.b64encode(X.astype(np.float32).tobytes()).decode(), c=base64.b64encode(C.astype(np.uint8).tobytes()).decode(), n=int(len(X)))
cloud2 = None
if a.wolke2:
    X = np.load(a.wolke2).astype(np.float32); C = np.load(a.farben2) if a.farben2 else np.full((len(X), 3), 150, np.uint8); k = a.massstab / 1000.0
    l, h = lo * k - a.rand, hi * k + a.rand; ok = np.all((X >= l) & (X <= h), 1); X, C = X[ok], C[ok]
    if len(X) > a.n2: i = np.random.default_rng(2).choice(len(X), a.n2, replace=False); X, C = X[i], C[i]
    X = X * (1000.0 / a.massstab); cloud2 = dict(p=base64.b64encode(X.astype(np.float32).tobytes()).decode(), c=base64.b64encode(C.astype(np.uint8).tobytes()).decode(), n=int(len(X)), name=a.name2)
HTML = open(__file__).read().split("#" + "#VORLAGE\n")[1].split("\n#" + "#ENDE")[0]
open(a.aus, "w").write(HTML.replace("@@TITEL@@", a.titel).replace("@@PARTS@@", json.dumps(parts)).replace("@@CLOUD@@", json.dumps(cloud)).replace("@@CLOUD2@@", json.dumps(cloud2)))
print(a.aus, len(open(a.aus).read()) // 1024, "kB", "Wolke", cloud and cloud["n"])
##VORLAGE
"""<title>@@TITEL@@</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
:root{--bg:#0d1117;--fg:#d6dde6;--mut:#8b98a9}
html,body{height:100%}body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,sans-serif;overflow:hidden}
#c{position:fixed;inset:0}
#p{position:fixed;z-index:5;left:max(16px,env(safe-area-inset-left,0px));top:12px;font-size:13px;line-height:1.7;background:#0d1117cc;padding:8px 12px;border-radius:6px;max-width:calc(100% - 32px)}
#p b{font-size:14px}#p label{display:flex;gap:8px;align-items:center;cursor:pointer}.sw{width:12px;height:12px;border-radius:2px;flex:none}
#h,#m{color:var(--mut);font-size:12px}
</style>
<div id="c"></div><div id="p"><b>@@TITEL@@</b><div id="h">Maus: drehen, Rad: zoomen, rechts: verschieben</div><div id="l"></div><div id="m"></div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
<script>
const PARTS=@@PARTS@@,CLOUD=@@CLOUD@@,CLOUD2=@@CLOUD2@@;
const W=()=>innerWidth,H=()=>innerHeight;
const sc=new THREE.Scene();sc.background=new THREE.Color(0x0d1117);
const cam=new THREE.PerspectiveCamera(45,W()/H(),0.5,20000);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(W(),H());rn.setPixelRatio(Math.min(devicePixelRatio,2));document.getElementById("c").appendChild(rn.domElement);
const ct=new THREE.OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.HemisphereLight(0xffffff,0x445566,0.9));
const sun=new THREE.DirectionalLight(0xfff2e0,0.9);sun.position.set(-200,300,200);sc.add(sun);
const b64=s=>{const b=atob(s),a=new Uint8Array(b.length);for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return a.buffer};
const ld=new THREE.STLLoader(),grp=new THREE.Group();
function schalter(txt,col,an,obj){const lb=document.createElement("label");lb.innerHTML='<input type="checkbox"'+(an?' checked':'')+'><span class="sw" style="background:'+col+'"></span>'+txt;
 lb.firstChild.onchange=e=>{obj.visible=e.target.checked};obj.visible=an;document.getElementById("l").appendChild(lb)}
PARTS.forEach(p=>{const g=ld.parse(b64(p.d));g.computeVertexNormals();
 const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:p.c,roughness:0.85,metalness:0.02,side:THREE.DoubleSide}));grp.add(m);schalter(p.n,p.c,p.an,m)});
grp.rotation.x=-Math.PI/2;sc.add(grp);
const box=new THREE.Box3().setFromObject(grp),ctr=box.getCenter(new THREE.Vector3()),sz=box.getSize(new THREE.Vector3());
if(CLOUD){const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(new Float32Array(b64(CLOUD.p)),3));
 g.setAttribute("color",new THREE.BufferAttribute(new Uint8Array(b64(CLOUD.c)),3,true));
 const pt=new THREE.Points(g,new THREE.PointsMaterial({size:1.5,vertexColors:true,sizeAttenuation:true}));grp.add(pt);schalter("Punktwolke ("+CLOUD.n+" Punkte, Fotofarben)","#c8a878",true,pt)}
if(CLOUD2){const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(new Float32Array(b64(CLOUD2.p)),3));
 g.setAttribute("color",new THREE.BufferAttribute(new Uint8Array(b64(CLOUD2.c)),3,true));
 const pt=new THREE.Points(g,new THREE.PointsMaterial({size:0.9,vertexColors:true,sizeAttenuation:true}));grp.add(pt);schalter(CLOUD2.name+" ("+CLOUD2.n+" Punkte)","#999999",false,pt)}
grp.position.sub(ctr);const R=Math.max(sz.x,sz.y,sz.z);
document.getElementById("m").textContent="Groesse "+sz.x.toFixed(0)+" x "+sz.y.toFixed(0)+" x "+sz.z.toFixed(0)+" mm (H0 1:87)";
const gp=new THREE.Mesh(new THREE.PlaneGeometry(R*4,R*4),new THREE.MeshStandardMaterial({color:0x2a2f26}));gp.rotation.x=-Math.PI/2;gp.position.y=-sz.z/2-0.1;sc.add(gp);
cam.position.set(R*0.9,R*0.7,R*1.2);ct.update();
addEventListener("resize",()=>{cam.aspect=W()/H();cam.updateProjectionMatrix();rn.setSize(W(),H())});
(function loop(){requestAnimationFrame(loop);ct.update();rn.render(sc,cam)})();
</script>"""
##ENDE

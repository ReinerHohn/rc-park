#!/usr/bin/env python3
"""linach_hybrid.py — HYBRID: feine, wasserdichte Form (linach_fein.stl) + ECHTE
Scan-Farben (Verwitterung/Algen aus glTF-Textur) per Nächster-Nachbar übertragen.
Match nach (Position-im-Bogen, Höhe) -> authentischer Beton auf sauberer Geometrie.
Export: farbige STL + GLB + HTML + heller Render.
"""
import os, base64, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from scipy.spatial import cKDTree

L,H,N=143.0,25.0,13; P=L/N
OUT="modelle/linachtalsperre"

# ---- Scan-Farben + normiertes (Bogen-Position, Höhe)-Frame ----
s=trimesh.load('daten/linach/sketchfab_gltf/scene.gltf',process=False)
SV=[]; SC=[]
for g in s.geometry.values():
    SV.append(np.asarray(g.vertices)); SC.append(g.visual.to_color().vertex_colors[:,:3])
SV=np.vstack(SV); SC=np.vstack(SC).astype(float)
z=SV[:,2]; hi=SV[z>np.percentile(z,60)]; c=hi[:,:2].mean(0)
w,vec=np.linalg.eigh(np.cov((hi[:,:2]-c).T)); wa=vec[:,np.argmax(w)]
xs=(SV[:,:2]-c)@wa; zs=z
xn=(xs-xs.min())/np.ptp(xs); zn=(zs-zs.min())/np.ptp(zs)
tree=cKDTree(np.column_stack([xn,zn]))
print(f"Scan-Farbquelle: {len(SV)} Punkte")

# ---- feine Form laden, Farben zuordnen ----
dam=trimesh.load(f"{OUT}/linach_fein.stl",process=False)
V=dam.vertices
xb=(((V[:,0]+L/2)%P)/P)                      # Position innerhalb des Bogens [0,1]
znp=np.clip(V[:,2]/ (H+2.7),0,1)             # Höhe normiert (inkl. Krone/Brüstung)
_,idx=tree.query(np.column_stack([xb,znp]),k=5)
col=SC[idx].mean(1)                           # mittel über 5 Nachbarn = ruhiger
# leichte Zufalls-Textur-Variation aus der Nachbar-Streuung
col=np.clip(col+ (SC[idx].std(1))*np.random.default_rng(0).normal(0,0.3,col.shape),0,255)
dam.visual.vertex_colors=np.column_stack([col,np.full(len(col),255)]).astype(np.uint8)
dam.export(f"{OUT}/linach_hybrid.stl")
print(f"Hybrid: {len(dam.faces)}F  watertight={dam.is_watertight}")

# ---- GLB + HTML ----
sc=trimesh.Scene(); d=dam.copy(); d.apply_translation(-dam.centroid); sc.add_geometry(d)
glb=sc.export(file_type="glb"); b64=base64.b64encode(glb).decode()
html="""<!doctype html><meta charset=utf-8><title>Linachtalsperre Hybrid</title>
<style>body{margin:0;background:#aab;font-family:system-ui;color:#223}#i{position:fixed;left:12px;top:10px;z-index:9;font-size:13px;line-height:1.4}</style>
<div id=i><b>Linachtalsperre</b> — feine Form + Scan-Textur (Hybrid)<br><span style=color:#036>Maus drehen · Rad zoom</span></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type=module>
import*as T from"three";import{OrbitControls}from"three/addons/controls/OrbitControls.js";import{GLTFLoader}from"three/addons/loaders/GLTFLoader.js";
const sc=new T.Scene();sc.background=new T.Color(0xaabbcc);
const cam=new T.PerspectiveCamera(45,innerWidth/innerHeight,0.1,5000);
const rn=new T.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new T.HemisphereLight(0xffffff,0x667,1.05));const sun=new T.DirectionalLight(0xfff4e6,1.0);sun.position.set(-100,120,140);sc.add(sun);
const b=atob("__B64__");const ar=new Uint8Array(b.length);for(let i=0;i<b.length;i++)ar[i]=b.charCodeAt(i);
new GLTFLoader().parse(ar.buffer,"",g=>{g.scene.traverse(o=>{if(o.material){o.material.vertexColors=true;o.material.roughness=0.95;o.material.metalness=0;}});
 const o=g.scene;o.rotation.x=-Math.PI/2;sc.add(o);
 const bb=new T.Box3().setFromObject(o),cc=bb.getCenter(new T.Vector3()),s=bb.getSize(new T.Vector3());
 o.position.sub(cc);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.3,d*0.35,d*0.9);cam.lookAt(0,0,0);ct.update();});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight);});
(function a(){requestAnimationFrame(a);ct.update();rn.render(sc,cam);})();
</script>""".replace("__B64__",b64)
open(f"{OUT}/linach_hybrid.html","w").write(html)
print(f"HTML: {OUT}/linach_hybrid.html ({len(html)//1024} kB)")

# ---- heller Render, Scan-Farbe x Lambert ----
tri=dam.vertices[dam.faces]; fc=(dam.visual.vertex_colors[dam.faces,:3].mean(1)/255.0)
def lam(tr):
    n=np.cross(tr[:,1]-tr[:,0],tr[:,2]-tr[:,0]); n=n/np.clip(np.linalg.norm(n,axis=1,keepdims=True),1e-9,None)
    lt=np.array([0.35,-0.55,0.75]); lt/=np.linalg.norm(lt); return (0.68+0.4*np.clip(n@lt,0,1))
sh=lam(tri); face=np.clip(fc*sh[:,None],0,1)
fig=plt.figure(figsize=(16,7),facecolor='white')
for i,(el,az,ti) in enumerate([(22,-58,"Luftseite 3/4"),(24,118,"Wasserseite (Gewölbe)")]):
    ax=fig.add_subplot(1,2,i+1,projection='3d',facecolor='white')
    ax.add_collection3d(Poly3DCollection(tri,facecolors=face,edgecolor='none'))
    ax.set_xlim(-L/2-3,L/2+3); ax.set_ylim(-4,17); ax.set_zlim(0,H+4)
    ax.set_box_aspect((L,(14+H)*1.3,H*1.3)); ax.view_init(elev=el,azim=az)
    ax.set_title(f"Hybrid: feine Form + echte Scan-Textur — {ti}",fontsize=11)
    ax.set_xlabel("Länge m"); ax.set_zlabel("m"); ax.set_yticks([])
    for pa in (ax.xaxis,ax.yaxis,ax.zaxis): pa.pane.set_facecolor((1,1,1,0)); pa.pane.set_edgecolor((0.85,0.85,0.85,1))
plt.tight_layout(); plt.savefig("daten/linach/linach_hybrid.png",dpi=120,facecolor='white'); print("Render: daten/linach/linach_hybrid.png")

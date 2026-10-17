#!/usr/bin/env python3
"""hirschsprung_osm.py — Hirschsprung true 1:160 mit der ECHTEN Bahntrasse + Tunnel
an den ECHTEN Portalen (aus OpenStreetMap, gegen LGL-DGM1 verifiziert).

Trasse = OSM-Weg 'Höllentalbahn': freie Vorbeifahrt am Hirschsprung-Fels (offen) →
Unterer Hirschsprungtunnel (Portale col772/row947 → col870/row869, 125 m, bis 57 m
Fels drüber). Hirsch am Denkmal (col731/row916) auf dem Fels neben der Vorbeifahrt.
Koordinaten im big-Array (col=E-426000, row=N-5309000), MM=6.25.
"""
import numpy as np, trimesh
import trimesh.transformations as T

MM=6.25
BIG="daten/hoellental/hirsch_big.npy"
CLEAR_W,CLEAR_H=30.0,36.0; RAIL_SINK=6.0; BENCH_W=30.0
LOCO_L,LOCO_W,LOCO_H=110.0,17.0,30.0
# Echte OSM-Trasse (row,col) — freie Vorbeifahrt (offen) + Tunnel-Portale
OPEN=[(1015,712),(999,728),(985,740),(967,756),(947,772)]              # Vorbeifahrt (voll)
TUN =[(947,772),(936,783),(924,796),(910,815),(896,836),(880,857),(869,870)]  # Tunnel
EAST=[(869,870),(861,879),(853,888)]                                   # Trasse Richtung Schwarzwald (Ost)
DRAW_DEER=True                                                         # Klamm-Kern A: Hirsch IST drin (Felsvorsprung West)
# Hirsch GEGENÜBER vom Tunnel: Tunnel ist ÖSTLICH des Klammbodens (col~733) -> Hirsch
# auf die WESTwand. Referenz auf Höhe des Hirschsprung-Felsens (row852), col westlich.
DEER_RC=(852,712)
OUT="modelle/3d_druck/hirschsprung_osm.stl"; HTML="modelle/hirschsprung_osm_3d.html"


def smooth(a,k):
    k=int(k)|1;pad=np.pad(a,k//2,mode='edge');return np.convolve(pad,np.ones(k)/k,'valid')

def solidify(xs,ys,zz):
    nx,ny=len(xs),len(ys);TX,TY=np.meshgrid(xs,ys)
    top=np.column_stack([TX.ravel(),TY.ravel(),zz.ravel()]);bot=np.column_stack([TX.ravel(),TY.ravel(),np.zeros(nx*ny)])
    V=np.vstack([top,bot]);nt=nx*ny;t=lambda r,c:r*nx+c;b=lambda r,c:nt+r*nx+c;F=[]
    for r in range(ny-1):
        for c in range(nx-1):
            F+=[[t(r,c),t(r+1,c),t(r+1,c+1)],[t(r,c),t(r+1,c+1),t(r,c+1)]]
            F+=[[b(r,c),b(r+1,c+1),b(r+1,c)],[b(r,c),b(r,c+1),b(r+1,c+1)]]
    R=ny-1;C=nx-1
    for c in range(nx-1):
        F+=[[t(0,c),t(0,c+1),b(0,c)],[t(0,c+1),b(0,c+1),b(0,c)]];F+=[[t(R,c),b(R,c),t(R,c+1)],[t(R,c+1),b(R,c),b(R,c+1)]]
    for r in range(ny-1):
        F+=[[t(r,0),b(r,0),t(r+1,0)],[t(r+1,0),b(r,0),b(r+1,0)]];F+=[[t(r,C),t(r+1,C),b(r,C)],[t(r+1,C),b(r+1,C),b(r,C)]]
    m=trimesh.Trimesh(V,np.array(F),process=False);trimesh.repair.fix_normals(m);return m

def deer(s=1.0):
    p=[]
    def cyl(r,h,tf):
        c=trimesh.creation.cylinder(radius=r,height=h,sections=10);c.apply_transform(tf);return c
    b=trimesh.creation.icosphere(subdivisions=1,radius=1.0);b.apply_scale([2.6,1.1,1.3]);b.apply_translation([0,0,6]);p.append(b)
    for sx in(-1,1):
        for ey in(-0.7,0.7):p.append(cyl(0.35,6,T.translation_matrix([sx*2,ey,3])))
    p.append(cyl(0.6,4.5,T.concatenate_matrices(T.translation_matrix([3,0,8]),T.rotation_matrix(np.radians(40),[0,1,0]))))
    h=trimesh.creation.icosphere(subdivisions=1,radius=0.9);h.apply_scale([1.6,0.9,0.9]);h.apply_translation([4.3,0,9.8]);p.append(h)
    for ey in(-0.5,0.5):
        p.append(cyl(0.22,3,T.concatenate_matrices(T.translation_matrix([4.3,ey,11.5]),T.rotation_matrix(np.radians(20),[0,1,0]))))
        p.append(cyl(0.18,1.6,T.translation_matrix([3.6,ey,12.8])));p.append(cyl(0.18,1.6,T.translation_matrix([5,ey,12.8])))
    d=trimesh.util.concatenate(p);d.apply_scale(s);return d

def loco():
    p=[]
    ch=trimesh.creation.box(extents=[LOCO_L,LOCO_W,LOCO_H*.33]);ch.apply_translation([0,0,LOCO_H*.165]);p.append(ch)
    hd=trimesh.creation.box(extents=[LOCO_L*.82,LOCO_W*.86,LOCO_H*.5]);hd.apply_translation([-LOCO_L*.06,0,LOCO_H*.58]);p.append(hd)
    cab=trimesh.creation.box(extents=[LOCO_L*.22,LOCO_W*.92,LOCO_H*.72]);cab.apply_translation([LOCO_L*.30,0,LOCO_H*.69]);p.append(cab)
    return trimesh.util.concatenate(p)

def densify(poly):
    out=[]
    for i in range(len(poly)-1):
        a=np.array(poly[i],float);b=np.array(poly[i+1],float);L=max(2,int(np.hypot(*(b-a))))
        for s in np.linspace(0,1,L,endpoint=False): out.append(a+(b-a)*s)
    out.append(np.array(poly[-1],float));return np.array(out)


def main():
    big=np.load(BIG)
    open_rc=densify(OPEN); tun_rc=densify(TUN); east_rc=densify(EAST)
    allrc=np.vstack([open_rc,tun_rc,east_rc])
    istun=np.concatenate([np.zeros(len(open_rc)),np.ones(len(tun_rc)),np.zeros(len(east_rc))])
    ieast=np.arange(len(open_rc)+len(tun_rc), len(allrc))   # Indizes der Ost-Trasse
    rr=allrc[:,0]; cc=allrc[:,1]

    # ENGER CROP (User „klüger drucken", aber Tunnel-EIN+AUSGANG beide dran):
    # Hirsch(West) + Portal A→B + steile Wände. Unnötiges (lange Vorbeifahrt NW,
    # dicker Bergrücken dahinter, Tiefe) weg. Echte LiDAR.
    r0,r1,c0,c1=838,905,698,885   # ENGER: Südkante hoch -> West-Ausgang(Portal A) + flacher SE-Massiv-Rest weg; Hirsch(NW)+Ost-Portal B bleiben
    win=big[r0:r1,c0:c1].astype(float); ny,nx=win.shape; zmin=win.min()
    xs=np.arange(nx)*MM; ys=np.arange(ny)*MM; zz=(win-zmin)*MM
    # WEICHER KNICK statt harter Kappung: unten 1:1, oben tanh-gestaucht gegen Asymptote.
    # Vorher np.minimum(zz,500) -> 25% des Modells wurde zur flachen Platte. Jetzt rollt
    # der Grat weiter (Gefälle bleibt erhalten), nur das Riesen-Massiv wird gestaucht.
    KNEE=300.0; CEIL=440.0   # Hirsch(332mm) bleibt voll; SE-Massiv-Rest niedrig gedeckelt (kein Turm), asympt. ~440mm
    over=zz-KNEE; zz=np.where(zz<=KNEE, zz, KNEE+(CEIL-KNEE)*np.tanh(over/(CEIL-KNEE)))
    print(f"Fenster real {nx}x{ny}m -> Modell {nx*MM:.0f}x{ny*MM:.0f}x{zz.max():.0f}mm (weicher Knick @{KNEE:.0f}->{CEIL:.0f})")

    # Rail-Höhe: offen = Gelände entlang Trasse (geglättet); Tunnel = gerade zw. Portalen
    terr_al=np.array([big[int(round(r)),int(round(c))] for r,c in allrc])
    railz=smooth(terr_al,9).copy()
    ti=np.where(istun>0)[0]
    railz[ti[0]:ti[-1]+1]=np.linspace(railz[ti[0]],railz[ti[-1]],len(ti))
    # Modellkoordinaten
    ax=(cc-c0)*MM; ay=(rr-r0)*MM; az=(railz-zmin)*MM-2.0
    pts=np.column_stack([ax,ay,az])
    ch_h=CLEAR_H+RAIL_SINK; cutters=[]; step=2
    for k in range(0,len(pts)-step,step):
        p0=pts[k];p1=pts[min(k+step,len(pts)-1)];d=p1-p0
        seglen=max(np.hypot(d[0],d[1]),step*MM);ang=np.arctan2(d[1],d[0])
        box=trimesh.creation.box(extents=[seglen*1.7,BENCH_W,ch_h])
        box.apply_transform(T.concatenate_matrices(
            T.translation_matrix([(p0[0]+p1[0])/2,(p0[1]+p1[1])/2,(p0[2]+p1[2])/2-RAIL_SINK+ch_h/2]),
            T.rotation_matrix(ang,[0,0,1])));cutters.append(box)
    terr=solidify(xs,ys,zz)
    if not terr.is_volume: trimesh.repair.fill_holes(terr);trimesh.repair.fix_normals(terr)
    model=terr.difference(trimesh.boolean.union(cutters))
    over=(terr_al-railz).max()
    print(f"Tunnel an ECHTEN Portalen: Fels bis {over*MM:.0f}mm ({over:.0f}m) | euler {model.euler_number} wt {model.is_watertight}")

    # N-Lok emergiert am IM-FENSTER sichtbaren Portal (offene Trasse im Crop)
    inwin_pt=lambda p:(-2<=p[0]<=nx*MM+2 and -2<=p[1]<=ny*MM+2)
    oi=[k for k in np.where(istun==0)[0] if inwin_pt(pts[k])]
    lk=oi[len(oi)//2] if oi else int(np.where(istun==0)[0][0])
    d=pts[min(lk+1,len(pts)-1)]-pts[max(lk-1,0)];ang=np.arctan2(d[1],d[0])
    lok=loco();lok.apply_transform(T.rotation_matrix(ang,[0,0,1]));lok.apply_translation([pts[lk][0],pts[lk][1],az[lk]+LOCO_H/2])

    # ---- TRASSE als durchgängiges GRAUES Band — NUR im Fenster (Vorbeifahrt liegt außerhalb) ----
    Wx,Wy=nx*MM,ny*MM
    inwin=lambda p:(-5<=p[0]<=Wx+5) and (-5<=p[1]<=Wy+5)
    tr_parts=[]
    for k in range(0,len(pts)-1):
        p0=pts[k];p1=pts[k+1]
        if not(inwin(p0) and inwin(p1)): continue
        dd=p1-p0; seglen=max(np.hypot(dd[0],dd[1]),1.0);ang=np.arctan2(dd[1],dd[0])
        box=trimesh.creation.box(extents=[seglen*1.3,22,4])
        box.apply_transform(T.concatenate_matrices(
            T.translation_matrix([(p0[0]+p1[0])/2,(p0[1]+p1[1])/2,(p0[2]+p1[2])/2+2]),
            T.rotation_matrix(ang,[0,0,1])))
        tr_parts.append(box)
    rail=trimesh.util.concatenate(tr_parts)
    print(f"Trasse grau: durchgängiges Band 22 mm (sichtbar an Portal B + Ost-Trasse)")

    # ---- Hirsch nur falls gewünscht (hier im Schwarzwald-Viertel: AUS) ----
    deer_objs=[]
    if DRAW_DEER:
        # Hirsch an die ECHTE Denkmal-Position auf der Westwand (DEER_RC), falls im Fenster;
        # sonst Fallback auf höchste Felsspitze.
        dr,dc=DEER_RC
        if r0<=dr<r1 and c0<=dc<c1:
            hr=int(dr-r0); hc=int(dc-c0)
        else:
            bd=zz.copy(); bd[:6,:]=-1;bd[-6:,:]=-1;bd[:,:6]=-1;bd[:,-6:]=-1
            pr,pcx=np.unravel_index(np.argmax(bd),bd.shape); hr=int(pr); hc=int(pcx)
        hx=xs[hc];hy=ys[hr];summit=zz[hr,hc]; pil_h=max(8.0,12.0)
        sock=trimesh.creation.cylinder(radius=6,height=pil_h,sections=7);sock.apply_scale([1.2,1,1]);sock.apply_translation([hx,hy,summit+pil_h/2])
        face=np.arctan2(pts[0][1]-hy,pts[0][0]-hx)
        h=deer(1.3);h.apply_transform(T.rotation_matrix(face,[0,0,1]));h.apply_translation([hx,hy,summit+pil_h])
        sock.visual.vertex_colors=[150,140,120,255]; h.visual.vertex_colors=[120,80,45,255]
        deer_objs=[sock,h]

    model.export(OUT)
    model.visual.vertex_colors=[185,169,138,255]
    lok.visual.vertex_colors=[205,30,30,255]
    rail.visual.vertex_colors=[90,90,96,255]
    scene=trimesh.util.concatenate([model,lok,rail]+deer_objs);scene.export(OUT.replace(".stl","_szene.stl"))
    print(f"-> {OUT} + _szene.stl");make_html(scene)


def make_html(scene):
    import base64
    b64=base64.b64encode(scene.export(file_type="glb")).decode()
    html='''<!doctype html><html><head><meta charset=utf8><title>Hirschsprung OSM-Trasse</title>
<style>body{margin:0;background:#cfe0ef;font-family:sans-serif}#i{position:fixed;top:10px;left:10px;background:#000a;color:#fff;padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.5}</style>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
</head><body><div id=i><b>Hirschsprung 1:160 — ECHTE Trasse</b><br>OSM-Höllentalbahn, Tunnel an echten Portalen<br>Unterer Hirschsprungtunnel 125m, Hirsch am Denkmal<br><span style=color:#8cf>Maus drehen · Rad zoom</span></div>
<script type=module>
import*as THREE from'three';import{OrbitControls}from'three/addons/controls/OrbitControls.js';import{GLTFLoader}from'three/addons/loaders/GLTFLoader.js';
const sc=new THREE.Scene();sc.background=new THREE.Color(0xcfe0ef);
const cam=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,0.1,20000);
const rn=new THREE.WebGLRenderer({antialias:true});rn.setSize(innerWidth,innerHeight);document.body.appendChild(rn.domElement);
const ct=new OrbitControls(cam,rn.domElement);ct.enableDamping=true;
sc.add(new THREE.AmbientLight(0xffffff,0.7));sc.add(new THREE.HemisphereLight(0xffffff,0x5a6b50,1.1));
const d1=new THREE.DirectionalLight(0xffffff,1.3);d1.position.set(300,-400,600);sc.add(d1);
const mat=new THREE.MeshStandardMaterial({vertexColors:true,roughness:1,side:THREE.DoubleSide,flatShading:true});
new GLTFLoader().load("data:model/gltf-binary;base64,%B64%",g=>{const m=g.scene;m.traverse(o=>{if(o.isMesh){o.material=mat;o.geometry.computeVertexNormals();}});
 const bx=new THREE.Box3().setFromObject(m);const c=bx.getCenter(new THREE.Vector3());const s=bx.getSize(new THREE.Vector3());
 m.position.sub(c);sc.add(m);const d=Math.max(s.x,s.y,s.z);cam.position.set(d*0.8,-d*1.1,d*0.7);cam.lookAt(0,0,0);ct.update();},undefined,e=>{document.getElementById("i").innerHTML+="<br><span style=color:#f88>LOAD-FEHLER: "+e+"</span>";});
addEventListener("resize",()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();rn.setSize(innerWidth,innerHeight)});
(function x(){requestAnimationFrame(x);ct.update();rn.render(sc,cam)})();
</script></body></html>'''.replace("%B64%",b64)
    open(HTML,"w").write(html);print(f"-> {HTML}")

if __name__=="__main__": main()

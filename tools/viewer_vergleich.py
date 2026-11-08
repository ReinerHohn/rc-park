#!/usr/bin/env python3
"""viewer_vergleich.py - 3D-Vergleichsseite (three.js, eine HTML) aus DENSELBEN Dateien/Rahmen wie die Pruefwerkzeuge (CLAUDE.md Regel 3, Log-Fehler 4).

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/viewer_vergleich.py modelle/<objekt>/objekt.json \
      --modell "C Etikett=a.stl" --modell "B Etikett=b.stl" --mesh "Stadtmesh=mesh.ply" --wolke --dom1 --aus seite.html [--pruef pruef.png]

Rahmen: STL 1:massstab mm -> m (pruefstand.lade_modell, Massstab/Zentrierung aus objekt.json). z-Boden: --z-boden pruefstand (lade_modell, Boden=0)
oder roh (nur Massstab, wie beweis_ansatz.stl_laden_m und die Wolke) - Standard "auto": roh, wenn die Gegenprobe Wolke<->erstes Modell damit besser ist.
Wolke: objekt.json "freiraum" (dicht + Ausrichtung), Transformation und Punktauswahl (>= 3 Kameras) wie freiraum_pruefen/beweis_ansatz.wolke_modellrahmen.
DOM1: beweis_ansatz.dom1_laden + eigener_grundriss (Zellen > 3 m ueber Gelaende im LoD2-Dach). Keine Aenderung an tools/*.
"""
import os, sys, json, base64, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import trimesh, cv2
import pruefstand as PS
import freiraum_pruefen as FP
import beweis_ansatz as BA


def b64(a): return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def wolke_laden(obj, od, min_kameras=3):
    """Punkte (Modellrahmen, m) + Fotofarben; gleiche Datei/Transformation/Auswahl wie BA.wolke_modellrahmen."""
    fr = obj["freiraum"]; dicht = fr["dicht"]; tr = json.load(open(os.path.join(od, fr["ausrichtung"])))["transformation"]
    s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
    X = ((FP.ply_lesen(os.path.join(dicht, "fused.ply")) - ta) @ Ra) / s
    with open(os.path.join(dicht, "fused.ply"), "rb") as f:
        hd = []
        while True:
            l = f.readline().decode("ascii").strip(); hd.append(l)
            if l == "end_header": break
        n = int([h for h in hd if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in hd if h.startswith("property")]
        dt = np.dtype([(q[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[q[0]]) for q in props]); arr = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    col = np.c_[arr["red"], arr["green"], arr["blue"]].astype(np.uint8)
    pi, _ = FP.vis_lesen(os.path.join(dicht, "fused.ply.vis")); ok = np.bincount(pi, minlength=len(X)) >= min_kameras
    return X[ok], col[ok], len(X), dicht, os.path.join(od, fr["ausrichtung"])


def abstand(P, m, n=20000, seed=1):
    from trimesh.proximity import ProximityQuery
    q = ProximityQuery(m); i = np.random.default_rng(seed).choice(len(P), min(n, len(P)), replace=False); d = np.empty(len(i))
    for a in range(0, len(i), 4000): d[a:a + 4000] = q.on_surface(P[i[a:a + 4000]])[1]
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("objekt"); ap.add_argument("--modell", action="append", default=[], help="NAME=STL (mehrfach; erstes = Referenz fuer Gegenprobe, an)")
    ap.add_argument("--mesh", action="append", default=[], help="NAME=PLY (Modellrahmen in m, roh)"); ap.add_argument("--wolke", action="store_true"); ap.add_argument("--dom1", action="store_true")
    ap.add_argument("--aus", required=True); ap.add_argument("--pruef"); ap.add_argument("--max-punkte", type=int, default=150000)
    ap.add_argument("--max-dreiecke", type=int, default=0, help="Modelle mit mehr Dreiecken werden ausgeduennt (0 = nie)"); ap.add_argument("--z-boden", default="auto", choices=["auto", "pruefstand", "roh"])
    ap.add_argument("--titel", default="Kaufhaus Freiburg 3D (5.11. abends)"); ap.add_argument("--an", action="append", default=[], help="Ebenennamen (Anfang), die standardmaessig an sind (erstes Modell + Wolke immer)")
    ap.add_argument("--legende", action="append", default=[], help="NAME-Anfang=Text (eine Zeile je Ebene)"); ap.add_argument("--hinweis", default="")
    ap.add_argument("--json", help="Gegenprobe-Zahlen hierhin schreiben"); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); ms = float(obj.get("stl_massstab", 1)); mm = obj.get("stl_einheit_mm", True); zen = obj.get("zentrierung", "huelle")
    sp = lambda s: s.split("=", 1)
    # ---- Wolke
    P = Pc = None; info = {}
    if a.wolke:
        Xw, Cw, nges, dicht, ausr = wolke_laden(obj, od); info["wolke"] = dict(dicht=dicht, ausrichtung=ausr, punkte_gesamt=int(nges), punkte_ab_3_kameras=int(len(Xw)))
    # ---- Modelle in beiden Z-Konventionen laden
    def lade(stl, roh):
        if roh:
            m = trimesh.load(stl)
            if mm: m.apply_scale(ms / 1000.0)
            if zen != "huelle": return m
            c = m.bounds.mean(0); m.apply_translation([-c[0], -c[1], 0]); return m
        return PS.lade_modell(stl, ms, mm, zen)
    spec = [sp(s) for s in a.modell]; roh_modus = a.z_boden == "roh"
    if a.wolke and spec and a.z_boden == "auto":
        d_ps = np.median(abstand(Xw, lade(spec[0][1], False), 8000)); d_roh = np.median(abstand(Xw, lade(spec[0][1], True), 8000))
        info["z_boden_probe"] = dict(median_pruefstand_m=round(float(d_ps), 3), median_roh_m=round(float(d_roh), 3)); roh_modus = d_roh < d_ps
    info["z_boden"] = "roh (nur Massstab, wie Wolke/beweis_ansatz)" if roh_modus else "pruefstand.lade_modell (Boden z=0)"
    models = [(n, lade(s, roh_modus)) for n, s in spec]
    meshes = [(n, trimesh.load(s)) for n, s in (sp(x) for x in a.mesh)]
    # ---- Gegenprobe
    if a.wolke and models:
        d = abstand(Xw, models[0][1], 20000); info["gegenprobe_wolke_zu_C"] = dict(modell=models[0][0], median_m=round(float(np.median(d)), 3), p90_m=round(float(np.percentile(d, 90)), 3), n=int(len(d)))
        print("Gegenprobe Wolke -> %s: Median %.3f m, P90 %.3f m" % (models[0][0], np.median(d), np.percentile(d, 90)))
    for n, m in meshes:
        if models:
            lo, hi = models[0][1].bounds; Q, _ = trimesh.sample.sample_surface(m, 200000, seed=1); Q = np.asarray(Q)      # nur Mesh-Flaeche ueber dem Modell-Grundriss (Umgebung gehoert nicht zum Gebaeude), z > 4 m (ohne Boden)
            t = (Q[:, 0] > lo[0] + 1) & (Q[:, 0] < hi[0] - 1) & (Q[:, 1] > lo[1] + 1) & (Q[:, 1] < hi[1] - 1) & (Q[:, 2] > 4); d = abstand(Q[t], models[0][1], 20000)
            info.setdefault("stadtmesh_zu_C", {})[n] = dict(median_m=round(float(np.median(d)), 3), p90_m=round(float(np.percentile(d, 90)), 3), z_max_m=round(float(np.asarray(m.vertices)[:, 2].max()), 2), flaechenproben=int(t.sum()))
            print("Gegenprobe %s (Flaeche ueber Grundriss, z>4) -> %s: Median %.3f m, P90 %.3f m" % (n, models[0][0], np.median(d), np.percentile(d, 90)))
    # ---- DOM1
    dom = None
    if a.dom1:
        k = BA.konfig(objp, os.path.dirname(a.aus)); D = BA.dom1_laden(k)
        if D is None: sys.exit("keine DOM1-Kachel")
        eigen, art = BA.eigener_grundriss(k, D); Z = D["Z"]; sel = eigen & (Z > 3) & np.isfinite(Z); ii, jj = np.where(sel)
        dom = np.c_[D["lx"][ii, jj], D["ly"][ii, jj], Z[ii, jj]]; info["dom1"] = dict(zellen=int(sel.sum()), maske=art, datei=D["quelle"], z_max_m=round(float(Z[sel].max()), 2), winkel_deg=round(float(np.degrees(np.arctan2(D["xh"][1], D["xh"][0]))), 2))
        if models:
            zc = float(models[0][1].bounds[1][2]); info["gegenprobe_first"] = dict(modell_z_max_m=round(zc, 2), dom1_zellmax_m=info["dom1"]["z_max_m"], differenz_m=round(zc - info["dom1"]["z_max_m"], 2))
            print("Gegenprobe First: %s %.2f m, DOM1-Zellmax %.2f m (%+.2f)" % (models[0][0], zc, info["dom1"]["z_max_m"], zc - info["dom1"]["z_max_m"]))
        # Zellen im Modellrahmen liegen achsparallel zu UTM -> Quadrat um die UTM-Richtung gedreht (wie verfahren_B_dom)
        ang = np.arctan2(D["xh"][1], D["xh"][0])
    # ---- Ausduennen / Ebenen bauen
    layers = []; sums = {}
    def tri_ebene(n, m, farbe, kanten, vcol=None, an=False):
        V = np.asarray(m.vertices, np.float32); F = np.asarray(m.faces, np.uint32)
        if a.max_dreiecke and len(F) > a.max_dreiecke:
            import fast_simplification as fs
            V2, F2 = fs.simplify(V.astype(np.float64), F.astype(np.int32), target_count=a.max_dreiecke); V, F = V2.astype(np.float32), F2.astype(np.uint32); vcol = None
            info.setdefault("ausgeduennt", {})[n] = dict(von=int(len(m.faces)), auf=int(len(F)))
        L = dict(name=n, typ="mesh", v=b64(V), f=b64(F), farbe=farbe, kanten=kanten, an=an, nv=int(len(V)), nf=int(len(F)))
        if vcol is not None: L["c"] = b64(np.asarray(vcol, np.uint8)[:, :3])
        sums[n] = dict(punkte=int(len(V)), dreiecke=int(len(F))); layers.append(L)
    farben = ["#c0392b", "#2e86c1", "#d4a017", "#7d3c98"]
    for i, (n, m) in enumerate(models): tri_ebene(n, m, farben[i % 4], len(m.faces) < 20000, an=(i == 0))
    for n, m in meshes:
        vc = None
        try:
            vc = np.asarray(m.visual.vertex_colors)
            if vc.shape[0] != len(m.vertices): vc = None
        except Exception: vc = None
        tri_ebene(n, m, "#8a8a8a", False, vcol=vc)
    if a.wolke:
        i = np.random.default_rng(1).choice(len(Xw), min(a.max_punkte, len(Xw)), replace=False); Xs, Cs = Xw[i].astype(np.float32), Cw[i]
        layers.append(dict(name="Buendelwolke (Fotofarben)", typ="punkte", v=b64(Xs), c=b64(Cs), an=True, nv=int(len(Xs)))); sums["Buendelwolke"] = dict(punkte=int(len(Xs)), dreiecke=0); P, Pc = Xs, Cs
    if dom is not None:
        layers.append(dict(name="DOM1 Dachzellen", typ="quads", v=b64(dom.astype(np.float32)), ang=float(ang), an=False, nv=int(len(dom)))); sums["DOM1"] = dict(punkte=int(len(dom)), dreiecke=0)
    leg = {}
    for s in a.legende: n, t = sp(s); leg[n] = t
    for L in layers:
        L["leg"] = next((t for n, t in leg.items() if L["name"].startswith(n)), "")
        if any(L["name"].startswith(x) for x in a.an): L["an"] = True
    html = HTML.replace("@@DATA@@", json.dumps(layers)).replace("@@TITEL@@", a.titel).replace("@@HINWEIS@@", a.hinweis)
    open(a.aus, "w").write(html); info["groesse_mb"] = round(os.path.getsize(a.aus) / 1048576, 2); info["ebenen"] = sums
    print(json.dumps(info, indent=1, ensure_ascii=False))
    if a.json: json.dump(info, open(a.json, "w"), indent=1, ensure_ascii=False)
    if a.pruef: pruefbild(a.pruef, models, meshes, P, Pc, dom, a.titel)


def pruefbild(pfad, models, meshes, P, Pc, dom, titel):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; from matplotlib.collections import LineCollection
    fig, ax = plt.subplots(1, 3, figsize=(24, 10)); ansichten = [("Nord (x/z)", 0, 2), ("Draufsicht (x/y)", 0, 1), ("Ost (y/z)", 1, 2)]
    for A, (t, i, j) in zip(ax, ansichten):
        lo, hi = models[0][1].bounds if models else (np.zeros(3), np.ones(3)); rd = 6.0
        if P is not None:
            o = np.where((P[:, 0] > lo[0] - rd) & (P[:, 0] < hi[0] + rd) & (P[:, 1] > lo[1] - rd) & (P[:, 1] < hi[1] + rd) & (P[:, 2] > lo[2] - 2) & (P[:, 2] < hi[2] + 3))[0]
            A.scatter(P[o, i], P[o, j], s=1.5, c=Pc[o] / 255.0, alpha=0.8, linewidths=0, rasterized=True, label="Wolke (Fotofarben)", zorder=5)
        for n, m in meshes:
            V = np.asarray(m.vertices); E = np.asarray(m.edges_unique); A.add_collection(LineCollection(V[E][:, :, [i, j]], colors="#228b22", linewidths=0.25, alpha=0.5))
            A.plot([], [], color="#228b22", label=n)
        for k, (n, m) in enumerate(models[:2]):
            V = np.asarray(m.vertices); E = np.asarray(m.edges_unique); A.add_collection(LineCollection(V[E][:, :, [i, j]], colors=["#c0392b", "#2e86c1"][k], linewidths=0.6, alpha=0.9)); A.plot([], [], color=["#c0392b", "#2e86c1"][k], label=n)
        if dom is not None and t.startswith("Nord"): A.scatter(dom[:, 0], dom[:, 2], s=6, c="#e08000", marker="s", label="DOM1")
        if dom is not None and t.startswith("Ost"): A.scatter(dom[:, 1], dom[:, 2], s=6, c="#e08000", marker="s")
        if dom is not None and t.startswith("Draufs"): A.scatter(dom[:, 0], dom[:, 1], s=8, c=dom[:, 2], cmap="autumn_r", marker="s", alpha=0.6)
        A.set_aspect("equal"); A.set_xlim(lo[i] - rd, hi[i] + rd); A.set_ylim(lo[j] - rd, hi[j] + rd); A.set_title(t); A.grid(alpha=0.3)
    ax[0].legend(loc="upper right", fontsize=8); fig.suptitle(titel + " - Pruefbild aus den geladenen Daten"); fig.tight_layout(); fig.savefig(pfad, dpi=75); print("Pruefbild", pfad)


HTML = r"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>@@TITEL@@</title>
<style>
:root{--bg:#f4f1ea;--fg:#222;--pn:#fffdf8;--ln:#ccc4b4;--ac:#8a4b14}
@media (prefers-color-scheme:dark){:root{--bg:#15171a;--fg:#e6e2d8;--pn:#1f2226;--ln:#3a3f45;--ac:#e0a060}}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:14px/1.35 system-ui,sans-serif}
#c{position:fixed;inset:0;width:100%;height:100%;display:block;touch-action:none}
#p{position:fixed;top:8px;left:8px;right:8px;max-width:440px;max-height:62vh;overflow:auto;background:var(--pn);border:1px solid var(--ln);border-radius:8px;padding:8px 12px;opacity:.96}
h1{font-size:16px;margin:0 0 4px;color:var(--ac)} .h{font-size:12px;margin:4px 0 6px;padding:4px 6px;border-left:3px solid var(--ac)}
label{display:block;font-weight:600;margin-top:5px} .k{font-size:11.5px;opacity:.8;margin:0 0 0 22px} small{opacity:.7}
</style></head><body><canvas id="c"></canvas>
<div id="p"><h1>@@TITEL@@</h1><div class="h">@@HINWEIS@@</div><div id="l"></div><small>Ziehen = drehen, Rad/Pinch = Zoom, Shift/2 Finger = verschieben. Meter, Modellrahmen (x Ost, y Nord).</small></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const D=@@DATA@@;
const dec=(s,T)=>{const b=atob(s),u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return new T(u.buffer)};
// Modell (x Ost,y Nord,z oben) -> three (x,z,-y)
const cv=v=>{const o=new Float32Array(v.length);for(let i=0;i<v.length;i+=3){o[i]=v[i];o[i+1]=v[i+2];o[i+2]=-v[i+1]}return o};
const cv8=c=>{const o=new Float32Array(c.length);for(let i=0;i<c.length;i++)o[i]=Math.pow(c[i]/255,2.2);return o};
const cvs=document.getElementById("c"),R=new THREE.WebGLRenderer({canvas:cvs,antialias:true});R.setPixelRatio(Math.min(devicePixelRatio,2));
const dark=matchMedia("(prefers-color-scheme:dark)").matches;const sc=new THREE.Scene();sc.background=new THREE.Color(dark?0x15171a:0xf4f1ea);
const cam=new THREE.PerspectiveCamera(45,1,0.5,2000);sc.add(new THREE.AmbientLight(0xffffff,.65));const dl=new THREE.DirectionalLight(0xffffff,.7);dl.position.set(-30,60,40);sc.add(dl);
sc.add(new THREE.GridHelper(80,40,dark?0x555555:0xaaaaaa,dark?0x333333:0xd0d0d0));
const G={};const lst=document.getElementById("l");
D.forEach((L,ix)=>{let o=new THREE.Group();const v=cv(dec(L.v,Float32Array));
 if(L.typ==="mesh"){const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(v,3));g.setIndex(new THREE.BufferAttribute(dec(L.f,Uint32Array),1));
  let mat;if(L.c){g.setAttribute("color",new THREE.BufferAttribute(cv8(new Uint8Array(dec(L.c,Uint8Array).buffer)).slice(0),3));mat=new THREE.MeshLambertMaterial({vertexColors:true,side:THREE.DoubleSide})}
  else mat=new THREE.MeshLambertMaterial({color:L.farbe,side:THREE.DoubleSide,flatShading:true,transparent:true,opacity:.92,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1});
  g.computeVertexNormals();o.add(new THREE.Mesh(g,mat));if(L.kanten)o.add(new THREE.LineSegments(new THREE.EdgesGeometry(g,25),new THREE.LineBasicMaterial({color:0x222222,transparent:true,opacity:.5})))}
 else if(L.typ==="punkte"){const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(v,3));g.setAttribute("color",new THREE.BufferAttribute(cv8(dec(L.c,Uint8Array)),3));o.add(new THREE.Points(g,new THREE.PointsMaterial({size:.12,vertexColors:true,sizeAttenuation:true})))}
 else{const n=v.length/3,src=dec(L.v,Float32Array),pos=new Float32Array(n*12),idx=[],ca=Math.cos(L.ang),sa=Math.sin(L.ang),h=.5;
  for(let i=0;i<n;i++){const x=src[3*i],y=src[3*i+1],z=src[3*i+2];[[-h,-h],[h,-h],[h,h],[-h,h]].forEach((q,k)=>{const X=x+q[0]*ca-q[1]*sa,Y=y+q[0]*sa+q[1]*ca;pos.set([X,z,-Y],12*i+3*k)});idx.push(4*i,4*i+1,4*i+2,4*i,4*i+2,4*i+3)}
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(pos,3));g.setIndex(idx);o.add(new THREE.Mesh(g,new THREE.MeshBasicMaterial({color:0xe08000,side:THREE.DoubleSide})))}
 o.visible=!!L.an;sc.add(o);G[ix]=o;
 const lb=document.createElement("label");lb.innerHTML='<input type="checkbox" '+(L.an?"checked":"")+'> '+L.name;lb.firstChild.onchange=e=>o.visible=e.target.checked;lst.appendChild(lb);
 const k=document.createElement("div");k.className="k";k.textContent=L.leg+(L.typ==="mesh"?" ["+L.nv+" Ecken, "+L.nf+" Dreiecke]":" ["+L.nv+" "+(L.typ==="punkte"?"Punkte":"Zellen")+"]");lst.appendChild(k)});
// eigene Orbit-Steuerung (keine weitere Bibliothek)
let th=0.9,ph=1.15,rad=75,tg=new THREE.Vector3(0,9,-4);
const upd=()=>{cam.position.set(tg.x+rad*Math.sin(ph)*Math.sin(th),tg.y+rad*Math.cos(ph),tg.z+rad*Math.sin(ph)*Math.cos(th));cam.lookAt(tg)};
const ptr=new Map();let last=null,pd=0;
cvs.addEventListener("pointerdown",e=>{cvs.setPointerCapture(e.pointerId);ptr.set(e.pointerId,[e.clientX,e.clientY]);pd=0});
cvs.addEventListener("pointerup",e=>ptr.delete(e.pointerId));cvs.addEventListener("pointercancel",e=>ptr.delete(e.pointerId));
cvs.addEventListener("pointermove",e=>{if(!ptr.has(e.pointerId))return;const o=ptr.get(e.pointerId);const dx=e.clientX-o[0],dy=e.clientY-o[1];
 if(ptr.size===2){const pts=[...ptr.values()];const d0=Math.hypot(pts[0][0]-pts[1][0],pts[0][1]-pts[1][1]);ptr.set(e.pointerId,[e.clientX,e.clientY]);const q=[...ptr.values()];const d1=Math.hypot(q[0][0]-q[1][0],q[0][1]-q[1][1]);rad=Math.min(400,Math.max(5,rad*d0/Math.max(d1,1)));
  const s=rad*.0015;const r=new THREE.Vector3().crossVectors(cam.getWorldDirection(new THREE.Vector3()),cam.up).normalize();tg.addScaledVector(r,-dx*s/2);tg.y+=dy*s/2}
 else if(e.shiftKey||e.button===2){const s=rad*.0015;const r=new THREE.Vector3().crossVectors(cam.getWorldDirection(new THREE.Vector3()),cam.up).normalize();tg.addScaledVector(r,-dx*s);tg.y+=dy*s;ptr.set(e.pointerId,[e.clientX,e.clientY])}
 else{th-=dx*.006;ph=Math.min(3.1,Math.max(.05,ph-dy*.006));ptr.set(e.pointerId,[e.clientX,e.clientY])}upd()});
cvs.addEventListener("wheel",e=>{e.preventDefault();rad=Math.min(400,Math.max(5,rad*Math.exp(e.deltaY*.0012)));upd()},{passive:false});cvs.addEventListener("contextmenu",e=>e.preventDefault());
const rs=()=>{R.setSize(innerWidth,innerHeight,false);cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix()};addEventListener("resize",rs);rs();upd();
(function f(){requestAnimationFrame(f);R.render(sc,cam)})();
</script></body></html>"""

if __name__ == "__main__": main()

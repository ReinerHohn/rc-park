#!/usr/bin/env python3
"""sfm_html_viewer.py - GENERISCH: ausgerichtetes SfM-Netz (Modellsystem, Meter) als selbst-enthaltene three.js-Seite.

Zeigt: Punktwolke (Farbe = Hoehe), Kameras als Pyramiden mit Fotonummer, LoD2-Eckkanten (anker3d.json), triangulierte Picks mit
Sigma als beschriftete Kugeln, optional das Modell-STL (1:<massstab>, mm -> m) halbtransparent zum Vergleich. Kein Server noetig.
  python3 tools/sfm_html_viewer.py modelle/<objekt>/objekt.json [--sfm messprotokoll/SFM-AUSRICHTUNG.json] [--punkte sfm/punkte_modell.npy]
                                  [--stl] [--out modelle/<objekt>/sfm/sfm_viewer.html]
"""
import sys, os, json, base64, argparse, numpy as np

HTML = r"""<title>__TITLE__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* Layout: Vollbild-Szene, links oben Legende/Masse, rechts oben Schalter; Farben aus Tokens fuer hell/dunkel */
:root{--bg:#eef0ea;--fg:#1f2a24;--muted:#5d6b63;--panel:#ffffffd9;--line:#c9d1c6;--accent:#b4541e;--cam:#2b6cb0;--lod2:#1f8f5f;--pick:#c7281f;
  --font-ui:"IBM Plex Sans",system-ui,sans-serif;--font-data:"IBM Plex Mono",ui-monospace,monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#101513;--fg:#e6ebe7;--muted:#9aa89f;--panel:#1a211dd9;--line:#2c3630;--accent:#e58a4a;--cam:#7fb3ff;--lod2:#5fd39a;--pick:#ff7a6e;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#101513;--fg:#e6ebe7;--muted:#9aa89f;--panel:#1a211dd9;--line:#2c3630;--accent:#e58a4a;--cam:#7fb3ff;--lod2:#5fd39a;--pick:#ff7a6e;color-scheme:dark}
html,body{height:100%}body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font-ui);overflow:hidden}
canvas{display:block}
.panel{position:fixed;z-index:5;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px;font-size:13px;line-height:1.45;max-width:min(360px,calc(100vw - 32px));backdrop-filter:blur(6px)}
#info{left:max(16px,env(safe-area-inset-left,0px));top:calc(12px + env(safe-area-inset-top,0px))}
#ctl{right:max(16px,env(safe-area-inset-right,0px));top:calc(12px + env(safe-area-inset-top,0px));display:flex;flex-direction:column;gap:6px}
#ctl label{display:flex;gap:8px;align-items:center;cursor:pointer}
h1{font-size:15px;margin:0 0 4px;font-weight:600;text-wrap:balance}
.k{color:var(--muted)}.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle}
table{border-collapse:collapse;margin-top:6px;font-family:var(--font-data);font-variant-numeric:tabular-nums;font-size:12px}
td{padding:1px 8px 1px 0;white-space:nowrap}td:nth-child(2),td:nth-child(3){text-align:right}
#lbl{position:fixed;inset:0;pointer-events:none;z-index:3}
.tag{position:absolute;transform:translate(-50%,-120%);font:11px var(--font-data);color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:0 4px;white-space:nowrap}
@media (max-width:600px){#info{max-width:calc(100vw - 32px);font-size:12px}#info table{display:none}}
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono&display=swap">
<div id="info" class="panel"><h1>__TITLE__</h1>
<div class="k">__SUB__</div>
<div style="margin-top:6px"><span class="sw" style="background:var(--lod2)"></span>LoD2-Eckkanten (amtlich) &nbsp; <span class="sw" style="background:var(--cam)"></span>Kameras &nbsp; <span class="sw" style="background:var(--pick)"></span>triangulierte Picks</div>
__TABLE__
<div class="k" style="margin-top:6px">Ziehen: drehen · Rad: zoomen · rechte Taste: verschieben</div></div>
<div id="ctl" class="panel">
<label><input type="checkbox" id="cbPts" checked> Netzpunkte</label>
<label><input type="checkbox" id="cbDicht" checked> dichte Wolke (Fotofarben)</label>
<label><input type="checkbox" id="cbCam" checked> Kameras</label>
<label><input type="checkbox" id="cbStl" __STLCHK__> Modell-STL</label>
<label><input type="checkbox" id="cbStlT"> STL durchsichtig</label>
<label><input type="checkbox" id="cbFarbe" __FARBCHK__> Fotofarben (sonst Hoehe)</label>
<label>Punktgroesse <input type="range" id="rgPt" min="0.1" max="1.5" step="0.05" value="0.5" style="width:90px"></label>
<label><input type="checkbox" id="cbLbl" checked> Beschriftung</label>
</div>
<div id="lbl"></div>
<div id="status" class="panel" style="left:50%;bottom:calc(16px + env(safe-area-inset-bottom,0px));transform:translateX(-50%)">Lade three.js von unpkg.com …</div>
<script>
(function(){ const st = document.getElementById('status'); const zeig = m => { st.hidden = false; st.textContent = m; };
  window.addEventListener('error', e => zeig('Fehler: ' + (e.message || e.type) + (e.filename ? ' (' + e.filename.split('/').slice(-1)[0] + ')' : '')));
  window.addEventListener('unhandledrejection', e => zeig('Fehler beim Laden: ' + (e.reason && e.reason.message || e.reason)));
  try { const c = document.createElement('canvas'); if (!(c.getContext('webgl2') || c.getContext('webgl'))) zeig('Dieser Browser stellt kein WebGL bereit - die 3D-Ansicht kann hier nicht gezeichnet werden.'); } catch (e) { zeig('WebGL nicht verfuegbar: ' + e.message); }
  setTimeout(() => { if (!window.__sfm_ok) zeig('three.js konnte nicht geladen werden (Netz? Script-Sperre?). Lokale Datei: modelle/<objekt>/sfm/sfm_viewer.html im Browser oeffnen.'); }, 20000);
})();
</script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
<script>
(function(){ if (!window.THREE) { document.getElementById('status').textContent = 'three.js (jsdelivr) nicht geladen - Netzverbindung oder Skriptsperre.'; return; }
const T = THREE; const OrbitControls = THREE.OrbitControls; const STLLoader = THREE.STLLoader;
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const sc = new T.Scene(); sc.background = new T.Color(css('--bg'));
const cam = new T.PerspectiveCamera(45, innerWidth/innerHeight, 0.5, 5000);
const rn = new T.WebGLRenderer({antialias:true}); rn.setPixelRatio(Math.min(devicePixelRatio,2)); rn.setSize(innerWidth, innerHeight); document.body.appendChild(rn.domElement);
const ct = new OrbitControls(cam, rn.domElement); ct.enableDamping = true;
// Modellsystem: x Sued, y Ost, z oben  ->  three: X = y (Ost), Y = z (oben), Z = x (Sued)
const M = (x,y,z) => new T.Vector3(y, z, x);
sc.add(new T.HemisphereLight(0xffffff, 0x334455, 0.9)); const sun = new T.DirectionalLight(0xfff1dd, 0.8); sun.position.set(60,120,40); sc.add(sun);
// Punktwolke, Farbe nach Hoehe
const P = D.punkte; const g = new T.BufferGeometry(); const pos = new Float32Array(P.length*3), col = new Float32Array(P.length*3); const colH = new Float32Array(P.length*3); const colF = new Float32Array(P.length*3);
const zs = P.map(p=>p[2]); const z0 = Math.min(...zs), z1 = Math.max(...zs); const c = new T.Color();
P.forEach((p,i)=>{ const v = M(p[0],p[1],p[2]); pos.set([v.x,v.y,v.z], i*3); c.setHSL(0.62 - 0.62*(p[2]-z0)/(z1-z0+1e-6), 0.75, 0.5); colH.set([c.r,c.g,c.b], i*3); const f = D.farben ? D.farben[i] : [128,128,128]; colF.set([f[0]/255,f[1]/255,f[2]/255], i*3); });
col.set(D.farben ? colF : colH);
g.setAttribute('position', new T.BufferAttribute(pos,3)); g.setAttribute('color', new T.BufferAttribute(col,3));
const pts = new T.Points(g, new T.PointsMaterial({size:0.5, vertexColors:true})); sc.add(pts);
let dicht = null;
if (D.n_dicht) { const b2f = s => { const b = atob(s); const u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; };
  const xyz = new Float32Array(b2f(D.dicht_xyz).buffer); const rgb = b2f(D.dicht_rgb); const n = D.n_dicht; const dp = new Float32Array(n*3), dc = new Float32Array(n*3);
  for (let i = 0; i < n; i++) { const v = M(xyz[3*i], xyz[3*i+1], xyz[3*i+2]); dp[3*i] = v.x; dp[3*i+1] = v.y; dp[3*i+2] = v.z; dc[3*i] = rgb[3*i]/255; dc[3*i+1] = rgb[3*i+1]/255; dc[3*i+2] = rgb[3*i+2]/255; }
  const dg = new T.BufferGeometry(); dg.setAttribute('position', new T.BufferAttribute(dp,3)); dg.setAttribute('color', new T.BufferAttribute(dc,3));
  dicht = new T.Points(dg, new T.PointsMaterial({size:0.18, vertexColors:true})); sc.add(dicht); pts.visible = false; document.getElementById('cbPts').checked = false; }
else { document.getElementById('cbDicht').disabled = true; }
// LoD2-Eckkanten + Bodenrechteck
const lod2 = new T.Group(); const lm = new T.LineBasicMaterial({color: new T.Color(css('--lod2'))});
D.kanten.forEach(k => { lod2.add(new T.Line(new T.BufferGeometry().setFromPoints([M(k[0],k[1],k[2]), M(k[0],k[1],k[3])]), lm)); });
if (D.kanten.length >= 4) { const q = D.kanten.map(k=>M(k[0],k[1],k[2])); q.push(q[0]); lod2.add(new T.Line(new T.BufferGeometry().setFromPoints(q), lm)); }
sc.add(lod2);
// Kameras als Pyramiden
const camG = new T.Group(); const cm = new T.LineBasicMaterial({color: new T.Color(css('--cam'))}); const labels = [];
D.kameras.forEach(k => { const o = M(k.c[0],k.c[1],k.c[2]); const ax = k.achsen.map(a => M(a[0],a[1],a[2])); const s = 2.5;
  const corners = [[1,1],[1,-1],[-1,-1],[-1,1]].map(([u,v]) => o.clone().add(ax[2].clone().multiplyScalar(s)).add(ax[0].clone().multiplyScalar(u*s*0.6)).add(ax[1].clone().multiplyScalar(v*s*0.45)));
  const segs = []; corners.forEach((p,i)=>{ segs.push(o, p, p, corners[(i+1)%4]); });
  camG.add(new T.LineSegments(new T.BufferGeometry().setFromPoints(segs), cm)); labels.push({p:o, t:k.nr, cls:'cam'}); });
sc.add(camG);
// Picks
const pickG = new T.Group(); const pm = new T.MeshStandardMaterial({color: new T.Color(css('--pick'))});
D.picks.forEach(p => { const m = new T.Mesh(new T.SphereGeometry(0.35, 16, 12), pm); m.position.copy(M(p.x,p.y,p.z)); pickG.add(m); labels.push({p:m.position, t:`${p.name} ${p.z.toFixed(1)} m`, cls:'pick'}); });
sc.add(pickG);
// Modell-STL (mm bei 1:massstab -> m)
let stl = null;
if (D.stl_b64) { const bin = Uint8Array.from(atob(D.stl_b64), ch => ch.charCodeAt(0)); const geo = new STLLoader().parse(bin.buffer); geo.computeVertexNormals();
  // STL-Achsen wie Modellsystem (x Sued, y Ost, z oben) in mm bei 1:massstab -> gleiche Abbildung wie M(): X=y, Y=z, Z=x, dann Meter
  geo.applyMatrix4(new T.Matrix4().set(0,1,0,0, 0,0,1,0, 1,0,0,0, 0,0,0,1)); const k = D.stl_massstab/1000; geo.scale(k,k,k); geo.computeVertexNormals();
  stl = new T.Mesh(geo, new T.MeshStandardMaterial({color:0xd9cdb8, transparent:false, opacity:1.0, side:T.DoubleSide, roughness:0.85}));
  stl.visible = D.stl_an; sc.add(stl); }
if (D.stl2_b64) { const bin2 = Uint8Array.from(atob(D.stl2_b64), ch => ch.charCodeAt(0)); const g2 = new STLLoader().parse(bin2.buffer);
  g2.applyMatrix4(new T.Matrix4().set(0,1,0,0, 0,0,1,0, 1,0,0,0, 0,0,0,1)); g2.computeVertexNormals();
  const stl2 = new T.Mesh(g2, new T.MeshStandardMaterial({color:0xb9b0a0, side:T.DoubleSide, roughness:0.9})); sc.add(stl2); if (stl) stl2.visible = stl.visible;
  document.getElementById('cbStl').addEventListener('change', e => { stl2.visible = e.target.checked; }); }
// Kamera-Start
const box = new T.Box3().setFromObject(pts); const ctr = box.getCenter(new T.Vector3()); const size = box.getSize(new T.Vector3()).length();
cam.position.copy(ctr).add(new T.Vector3(-size*0.6, size*0.25, -size*0.9)); ct.target.copy(ctr);
// Boden-Gitter
const grid = new T.GridHelper(80, 16, 0x888888, 0x555555); grid.material.opacity = 0.25; grid.material.transparent = true; sc.add(grid);
// Schalter
const on = (id, f) => document.getElementById(id).addEventListener('change', e => f(e.target.checked));
on('cbPts', v => pts.visible = v); on('cbDicht', v => { if (dicht) dicht.visible = v; }); on('cbCam', v => camG.visible = v); on('cbStl', v => { if (stl) stl.visible = v; }); on('cbLbl', v => lblOn = v);
on('cbStlT', v => { if (stl) { stl.material.transparent = v; stl.material.opacity = v ? 0.35 : 1.0; stl.material.depthWrite = !v; stl.material.needsUpdate = true; } });
on('cbFarbe', v => { col.set(v && D.farben ? colF : colH); g.attributes.color.needsUpdate = true; });
document.getElementById('rgPt').addEventListener('input', e => { pts.material.size = parseFloat(e.target.value); if (dicht) dicht.material.size = 0.36 * parseFloat(e.target.value); });
let lblOn = true; const lblDiv = document.getElementById('lbl'); const tags = labels.map(l => { const d = document.createElement('div'); d.className = 'tag'; d.textContent = l.t; lblDiv.appendChild(d); return d; });
function tick(){ ct.update(); rn.render(sc, cam);
  labels.forEach((l,i) => { const v = l.p.clone().project(cam); const vis = lblOn && v.z < 1 && (l.cls !== 'cam' || camG.visible) && (l.cls !== 'pick' || pickG.visible);
    tags[i].style.display = vis ? 'block' : 'none'; if (vis) { tags[i].style.left = ((v.x+1)/2*innerWidth)+'px'; tags[i].style.top = ((1-v.y)/2*innerHeight)+'px'; } });
  requestAnimationFrame(tick); }
addEventListener('resize', () => { cam.aspect = innerWidth/innerHeight; cam.updateProjectionMatrix(); rn.setSize(innerWidth, innerHeight); });
window.__sfm_ok = true; document.getElementById('status').hidden = true;
tick();
})();
</script>
"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--sfm", default="messprotokoll/SFM-AUSRICHTUNG.json"); ap.add_argument("--punkte", default="sfm/punkte_modell.npy")
    ap.add_argument("--stl", action="store_true", help="Modell-STL einbetten (mm, 1:massstab aus objekt.json)"); ap.add_argument("--out"); ap.add_argument("--titel")
    ap.add_argument("--stl2", help="zweites STL in METERN (z. B. LoD2-Nebengebaeude im Modellsystem)"); ap.add_argument("--dicht", help="dichte Wolke: sfm/dicht_<seite>_modell.npy (Farben daneben *_farben.npy)"); ap.add_argument("--dicht-max", type=int, default=400000)
    a = ap.parse_args(); obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt)))); od = os.path.dirname(os.path.abspath(a.objekt))
    S = json.load(open(os.path.join(od, a.sfm))); P = np.load(os.path.join(od, a.punkte)); A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    fp = os.path.join(od, a.punkte.replace("punkte_modell", "punkte_farben")); F = np.load(fp).astype(int).tolist() if os.path.exists(fp) and "punkte_modell" in a.punkte else None
    kanten = [[*A[n]["xyz"][:2], A[n]["xyz"][2], 30.0] for n in sorted(A) if n.startswith("ecke_boden")]
    kams = []
    for nr, k in S["kameras"].items():
        R = np.array(k["R"]); c = np.array(k["standort"]); kams.append(dict(nr=nr, c=c.round(2).tolist(), achsen=[R[0].round(4).tolist(), (-R[1]).round(4).tolist(), R[2].round(4).tolist()]))   # Bild-x, Bild-y (nach oben), Blick
    picks = [dict(name=n, x=t["xyz"][0], y=t["xyz"][1], z=t["xyz"][2], sigma=t["sigma"][2]) for n, t in S.get("trianguliert", {}).items()]
    dicht_xyz = dicht_rgb = ""; n_dicht = 0
    if a.dicht:
        D = np.load(os.path.join(od, a.dicht)).astype(np.float32); Fc = np.load(os.path.join(od, a.dicht.replace("_entzerrt.npy", "_modell.npy").replace("_modell.npy", "_farben.npy"))).astype(np.uint8)   # Farben gehoeren zur (un)entzerrten Wolke gleichermassen
        if len(D) > a.dicht_max: idx = np.random.default_rng(0).choice(len(D), a.dicht_max, replace=False); D, Fc = D[idx], Fc[idx]
        dicht_xyz = base64.b64encode(D.tobytes()).decode(); dicht_rgb = base64.b64encode(Fc.tobytes()).decode(); n_dicht = len(D)
    stl2_b64 = base64.b64encode(open(os.path.join(od, a.stl2) if not os.path.isabs(a.stl2) else a.stl2, "rb").read()).decode() if a.stl2 else ""
    stl_b64 = ""
    if a.stl:
        stl_b64 = base64.b64encode(open(os.path.join(root, obj["stl"]), "rb").read()).decode()
    data = dict(punkte=P.round(2).tolist(), farben=F, dicht_xyz=dicht_xyz, dicht_rgb=dicht_rgb, n_dicht=n_dicht, kanten=kanten, kameras=kams, picks=picks, stl_b64=stl_b64, stl2_b64=stl2_b64, stl_massstab=obj.get("stl_massstab", 87), stl_an=bool(stl_b64))
    tr = S["transformation"]
    rows = "".join(f"<tr><td>{p['name']}</td><td>{p['z']:.2f} m</td><td class=k>±{p['sigma']:.2f}</td></tr>" for p in sorted(picks, key=lambda p: -p["z"]))
    table = f"<table><tr><td class=k>Pick</td><td class=k>Hoehe</td><td class=k>Sigma</td></tr>{rows}</table>" if rows else ""
    sub = (f"{len(kams)} Kameras, {len(P)} Netzpunkte" + (f", {n_dicht} dichte Punkte" if n_dicht else "") + f" · Massstab aus LoD2-Eckkanten ±{tr['s_sigma_prozent']:.1f} % · Lage ±{max(tr['t_sigma_m']):.1f} m"
           + (" · Hoehenlage: ANNAHME Strassenkamera" if S.get("annahmen", {}).get("kamerahoehe") else " · Hoehenlage aus Bodenpunkten"))
    titel = a.titel or f"{obj['name']} SfM-Netz"
    html = HTML.replace("__TITLE__", titel).replace("__SUB__", sub).replace("__TABLE__", table).replace("__STLCHK__", "checked" if stl_b64 else "").replace("__FARBCHK__", "checked" if F else "").replace("__DATA__", json.dumps(data))
    out = a.out or os.path.join(od, "sfm", "sfm_viewer.html"); open(out, "w").write(html); print("geschrieben:", out, f"({os.path.getsize(out)/1e6:.1f} MB)")

if __name__ == "__main__":
    main()

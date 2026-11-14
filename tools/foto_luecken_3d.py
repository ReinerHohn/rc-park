#!/usr/bin/env python3
"""foto_luecken_3d.py <objekt.json> <sparse_modell> [--schritt 2] [--min 3] - neutrales 3D-HTML: Wandfelder nach Anzahl Fotos.

Zeigt NUR die Messung: je Wandfeld die Zahl der Fotos, die es im Bild haben (vorne, im Bildrahmen, Blickwinkel <= 70 Grad
zur Wandnormalen), dazu alle Kamerapositionen. Keine Empfehlung, keine Bewertung der Erreichbarkeit: das entscheidest du.
Klick auf ein Feld: Anzahl, Hoehe, Himmelsrichtung der Wand, und welche Blickrichtung/Abstand fehlt (Bereich der Kamera-
standorte, die diesen Punkt noch nicht sehen).
Ausgabe: modelle/<objekt>/foto_luecken_3d.html und foto_luecken_3d.json.
Grenzen: Verdeckung durch Nachbarbauten und Baeume wird NICHT geprueft; Feldzahl gilt im SfM-Netz ueber die Ausrichtung.
"""
import sys, os, json, math, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_luecken_plan as F

HTML = r"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Foto-Abdeckung __OBJ__</title>
<style>
body{margin:0;font:14px/1.45 system-ui,sans-serif;background:#f4f2ee;color:#1d1c1a}
#top{padding:10px 14px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;border-bottom:1px solid #d6d1c6;background:#fff}
#cv{width:100%;height:62vh;display:block;touch-action:none}
#info{padding:10px 14px;min-height:70px;background:#fff;border-top:1px solid #d6d1c6}
.sw{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:4px;vertical-align:-1px}
label{white-space:nowrap}
</style></head><body>
<div id="top">
 <b>__OBJ__</b>
 <span><i class="sw" style="background:#c0392b"></i>0 Fotos</span>
 <span><i class="sw" style="background:#e0b400"></i>1 bis __MIN_M1__</span>
 <span><i class="sw" style="background:#2e8b57"></i>&ge; __MIN__ Fotos</span>
 <label><input type="checkbox" id="cam" checked> Kameras zeigen</label>
 <label><input type="checkbox" id="wk" checked> Punktwolke zeigen</label>
 <label>Mindestzahl <input type="range" id="sl" min="0" max="10" value="__MIN__"> <span id="slv">__MIN__</span></label>
</div>
<canvas id="cv"></canvas>
<div id="info">Auf ein Wandfeld klicken: Anzahl Fotos, Hoehe und Himmelsrichtung.</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script>
<script>
const D = __DATA__;
const cv = document.getElementById('cv'), info = document.getElementById('info');
const renderer = new THREE.WebGLRenderer({canvas: cv, antialias: true});
renderer.setClearColor(0xf4f2ee, 1);
const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(35, 1, 0.5, 2000);
const grp = new THREE.Group(); scene.add(grp);
scene.add(new THREE.HemisphereLight(0xffffff, 0x887766, 1.2));
const dl = new THREE.DirectionalLight(0xffffff, 0.8); dl.position.set(60, 90, 80); scene.add(dl);
function farbe(n){ if (n <= 0) return 0xc0392b; if (n < D.min) return 0xe0b400; return 0x2e8b57; }
// Gebaeude-Box (Wandextreme + Traufe/First)
const b = D.box;
const g = new THREE.BoxGeometry(b.u1 - b.u0, b.h, b.v1 - b.v0);
const mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({color: 0xd9cdb5, transparent: true, opacity: 0.25}));
mesh.position.set((b.u0 + b.u1) / 2, b.h / 2, (b.v0 + b.v1) / 2); grp.add(mesh);
const edges = new THREE.LineSegments(new THREE.EdgesGeometry(g), new THREE.LineBasicMaterial({color: 0x665544}));
edges.position.copy(mesh.position); grp.add(edges);
// Wandfelder: kleine Quader je Punkt
const cube = new THREE.BoxGeometry(D.schritt * 0.9, D.schritt * 0.9, 0.3);
const felder = [];
D.felder.forEach((f, i) => {
  const m = new THREE.Mesh(cube, new THREE.MeshLambertMaterial({color: farbe(f.n)}));
  m.position.set(f.p[0], f.p[2], f.p[1]); m.rotation.y = f.rot;
  m.userData = f; grp.add(m); felder.push(m);
});
// Kameras als kleine Pyramiden
const camGrp = new THREE.Group(); grp.add(camGrp);
D.kameras.forEach(c => {
  const m = new THREE.Mesh(new THREE.ConeGeometry(0.6, 1.4, 4), new THREE.MeshLambertMaterial({color: 0x2c3e50}));
  m.position.set(c[0], c[2], c[1]);
  camGrp.add(m);
});
// Punktwolke (Modellkoordinaten), Farbe aus den Fotos
if (D.wolke && D.wolke.length) {
  const pos = new Float32Array(D.wolke.length * 3), col = new Float32Array(D.wolke.length * 3);
  D.wolke.forEach((q, i) => { pos[3*i] = q[0]; pos[3*i+1] = q[2]; pos[3*i+2] = q[1]; col[3*i] = q[3]/255; col[3*i+1] = q[4]/255; col[3*i+2] = q[5]/255; });
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3)); pg.setAttribute('color', new THREE.BufferAttribute(col, 3));
  window.wolkeObj = new THREE.Points(pg, new THREE.PointsMaterial({size: 0.12, vertexColors: true, sizeAttenuation: true}));
  grp.add(window.wolkeObj);
}
const bb = new THREE.Box3().setFromObject(grp), ctr = bb.getCenter(new THREE.Vector3()), size = bb.getSize(new THREE.Vector3());
let yaw = 0.8, pitch = 0.35, dist = size.length() * 0.9;
function place(){ cam.position.set(ctr.x + dist*Math.cos(pitch)*Math.sin(yaw), ctr.y + dist*Math.sin(pitch), ctr.z + dist*Math.cos(pitch)*Math.cos(yaw)); cam.lookAt(ctr); }
function size_(){ const w = cv.clientWidth, h = cv.clientHeight; renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
function render(){ place(); renderer.render(scene, cam); }
let drag = null, moved = 0;
cv.addEventListener('pointerdown', e => { drag = {x: e.clientX, y: e.clientY}; moved = 0; cv.setPointerCapture(e.pointerId); });
cv.addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; moved += Math.abs(dx) + Math.abs(dy); yaw -= dx * 0.01; pitch = Math.max(-1.2, Math.min(1.2, pitch + dy * 0.01)); drag = {x: e.clientX, y: e.clientY}; render(); });
cv.addEventListener('pointerup', e => { drag = null; if (moved > 6) return; // Klick
  const r = cv.getBoundingClientRect(); const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  const rc = new THREE.Raycaster(); rc.setFromCamera(ndc, cam);
  const hit = rc.intersectObjects(felder, false)[0];
  if (hit) { const f = hit.object.userData;
    info.innerHTML = `<b>Wandfeld</b> ${f.seite}-Wand, Hoehe ${f.p[2].toFixed(1)} m<br>Fotos im Bild: <b>${f.n}</b> &nbsp;|&nbsp; Blickrichtung der Fotos noetig: ${f.blick}<br>Abstand zur Wand, aus dem noch fotografiert werden kann: ${f.abstand}`;
  } });
window.addEventListener('resize', () => { size_(); render(); });
document.getElementById('wk').addEventListener('change', e => { if (window.wolkeObj) window.wolkeObj.visible = e.target.checked; render(); });
document.getElementById('cam').addEventListener('change', e => { camGrp.visible = e.target.checked; render(); });
const sl = document.getElementById('sl');
sl.addEventListener('input', () => { document.getElementById('slv').textContent = sl.value; const m = +sl.value;
  felder.forEach(f => f.material.color.setHex(f.userData.n <= 0 ? 0xc0392b : (f.userData.n < m ? 0xe0b400 : 0x2e8b57))); render(); });
size_(); render();
</script></body></html>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objekt"); ap.add_argument("sparse"); ap.add_argument("--schritt", type=float, default=2.0); ap.add_argument("--min", type=int, default=3); ap.add_argument("--ausrichtung", default=None); ap.add_argument("--ply", default=None)
    a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    rw = dict(obj["rahmen_wand"], xhat_utm=obj["rahmen"]["xhat_utm"], yhat_utm=obj["rahmen"]["yhat_utm"])
    hoehe = float(obj.get("hoehe_m", 25.8))
    import glob
    aus = a.ausrichtung or (glob.glob(os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-*.json")) or [None])[0]
    if not aus: print("FEHLT: SFM-AUSRICHTUNG-*.json"); return 2
    T = json.load(open(aus))["transformation"]
    from scipy.spatial.transform import Rotation as Rot
    R = Rot.from_rotvec(T["rvec"]).as_matrix(); s = float(T["s"]); t = np.array(T["t"])
    cams = F.kameras(a.sparse)
    # Kamerapositionen in Modellkoordinaten: X_mod = R^T (X_sfm - t) / s
    kam = []
    for name, P, C, W, H in cams:
        cm = R.T @ (C - t) / s
        kam.append([round(float(cm[0]), 2), round(float(cm[1]), 2), round(float(cm[2]), 2)])
    ziele = F.wand_ziele(rw, hoehe, a.schritt)
    felder = []
    # je Punkt: Anzahl Fotos, Richtung der Normalen, Abstand-Hinweis
    Pf = np.array([s * R @ np.array(p, float) + t for _, _, p in ziele])
    Nf = np.array([R @ np.array(n, float) for _, n, _ in ziele])
    counts = F.sichtbare_ansichten(Pf, Nf, cams)          # GPU (torch) oder numpy, gleiche Funktion wie foto_luecken_plan
    for (seite, n, p), anz in zip(ziele, counts):
        pm = np.array(p, float); pf = s * R @ pm + t
        normal_deg = (math.degrees(math.atan2(n[0], n[1])) + 360) % 360
        felder.append({"p": [round(float(pm[0]), 2), round(float(pm[1]), 2), round(float(pm[2]), 2)], "n": int(anz), "seite": seite,
                       "rot": math.pi / 2 if n[0] != 0 else 0.0,
                       "blick": f"Wand-Normale {normal_deg:.0f} Grad, Winkel bis 70 Grad",
                       "abstand": "5 bis 30 m (Richtwert: Feld muss im Bild ganz liegen)"})
    wolke = []
    sfx = os.path.basename(aus).replace("SFM-AUSRICHTUNG-", "").replace(".json", "")
    wp = os.path.join(od, "sfm", f"punkte_modell_{sfx}.npy"); wf = os.path.join(od, "sfm", f"punkte_farben_{sfx}.npy")
    if os.path.exists(wp) and os.path.exists(wf):
        P = np.load(wp); Cf = np.load(wf)
        idx = np.random.default_rng(1).choice(len(P), size=min(len(P), 25000), replace=False)
        Cf = Cf[idx] if Cf.max() > 1.0 else (Cf[idx] * 255)
        wolke = [[round(float(x), 2), round(float(y), 2), round(float(z), 2), int(r), int(g), int(b)] for (x, y, z), (r, g, b) in zip(P[idx], Cf.astype(int))]
    box = {"u0": rw["u0"], "u1": rw["u1"], "v0": rw["v0"], "v1": rw["v1"], "h": hoehe}
    data = {"min": a.min, "schritt": a.schritt, "box": box, "felder": felder, "kameras": kam, "wolke": wolke}
    html = HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__OBJ__", obj.get("name", a.objekt)).replace("__MIN__", str(a.min)).replace("__MIN_M1__", str(a.min - 1))
    out = os.path.join(od, "foto_luecken_3d.html")
    open(out, "w").write(html)
    json.dump(data, open(os.path.join(od, "foto_luecken_3d.json"), "w"), ensure_ascii=False)
    null = sum(1 for f in felder if f["n"] == 0); klein = sum(1 for f in felder if 0 < f["n"] < a.min)
    print(f"{len(felder)} Wandpunkte, {null} ohne Foto, {klein} unter {a.min}; {len(kam)} Kameras -> {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

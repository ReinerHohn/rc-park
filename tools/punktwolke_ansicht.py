#!/usr/bin/env python3
"""punktwolke_ansicht.py <dichte_ply> <ausrichtung.json> <ausgabe.html> [--n 250000] - dichte Wolke als 3D-HTML (Farben aus den Fotos).

Die Wolke wird mit der gewaehlten Ausrichtung ins Modellsystem uebertragen (X_mod = (X_sfm - t) R / s).
Zeigt nur die Messung: keine Bewertung. Drehen mit Ziehen, Zoomen mit Rad oder Pinch."""
import sys, json, argparse
import numpy as np
from scipy.spatial.transform import Rotation as Rot

HTML = r"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Schwabentor Punktwolke</title><style>
body{margin:0;font:14px/1.45 system-ui,sans-serif;background:#eeeae3;color:#222}
#h{padding:12px 14px;background:#fff;border-bottom:1px solid #ddd}
#cv{width:100%;height:70vh;display:block;touch-action:none}
#f{padding:10px 14px;color:#555;font-size:13px}
</style></head><body>
<div id="h"><b>Schwabentor – dichte Punktwolke</b><br>__INFO__</div>
<canvas id="cv"></canvas>
<div id="f">Ziehen: drehen · Scroll: zoomen · Rechtsklick: verschieben · Farben aus den Fotos</div>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const P = __DATA__;
const cv = document.getElementById('cv');
const renderer = new THREE.WebGLRenderer({canvas: cv, antialias: true});
renderer.setClearColor(0xeeeae3, 1);
const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(35, 1, 0.1, 2000);
const pos = new Float32Array(P.length * 3), col = new Float32Array(P.length * 3);
P.forEach((q, i) => { pos[3*i] = q[0]; pos[3*i+1] = q[2]; pos[3*i+2] = -q[1]; col[3*i] = q[3]/255; col[3*i+1] = q[4]/255; col[3*i+2] = q[5]/255; });
const g = new THREE.BufferGeometry();
g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.BufferAttribute(col, 3));
const pts = new THREE.Points(g, new THREE.PointsMaterial({size: 0.08, vertexColors: true}));
scene.add(pts);
scene.add(new THREE.AxesHelper(5));
g.computeBoundingBox();
const bb = g.boundingBox, ctr = bb.getCenter(new THREE.Vector3()), size = bb.getSize(new THREE.Vector3());
const controls = new THREE.OrbitControls(cam, renderer.domElement);
controls.target.copy(ctr); controls.enableDamping = true; controls.screenSpacePanning = true;
cam.position.set(ctr.x + size.length()*0.6, ctr.y + size.length()*0.35, ctr.z + size.length()*0.6);
function size_(){ const w = cv.clientWidth, h = cv.clientHeight; renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
function loop(){ requestAnimationFrame(loop); controls.update(); renderer.render(scene, cam); }
window.addEventListener('resize', size_);
size_(); loop();
</script></body></html>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ply"); ap.add_argument("ausrichtung"); ap.add_argument("out")
    ap.add_argument("--n", type=int, default=250000)
    a = ap.parse_args()
    dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
    raw = open(a.ply, "rb").read(); ke = raw.index(b"end_header\n") + len(b"end_header\n")
    n = int([l for l in raw[:ke].decode().splitlines() if l.startswith("element vertex")][0].split()[-1])
    V = np.frombuffer(raw, dtype=dt, count=n, offset=ke)
    rng = np.random.default_rng(3); idx = rng.choice(n, min(n, a.n), replace=False)
    X = np.c_[V["x"], V["y"], V["z"]][idx].astype(float); F = np.c_[V["r"], V["g"], V["b"]][idx].astype(int)
    tr = json.load(open(a.ausrichtung))["transformation"]
    R = Rot.from_rotvec(tr["rvec"]).as_matrix(); s = float(tr["s"]); t = np.array(tr["t"])
    M = (X - t) @ R / s                      # ins Modellsystem
    data = [[round(float(x), 3), round(float(y), 3), round(float(z), 3), int(r), int(g), int(b)] for (x, y, z), (r, g, b) in zip(M, F)]
    info = f"{len(data)} Punkte (Zufallsauswahl aus {n}) · Ausrichtung: {a.ausrichtung.split('/')[-1]} · Modellsystem, Meter"
    html = HTML.replace("__DATA__", json.dumps(data, separators=(",", ":"))).replace("__INFO__", info)
    open(a.out, "w").write(html)
    print(len(data), "Punkte ->", a.out, f"{len(html)//1024} KB")
    return 0

if __name__ == "__main__":
    sys.exit(main())

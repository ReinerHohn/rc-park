"""Draht-Editor (lokal, Port 8767): Kantenkandidaten anklicken, loeschen, vereinigen, als Spline bearbeiten/glaetten, neue Kanten ueber Wolkenpunkte ziehen,
Abdeckung gegen die abgestimmten Kantenpunkte (rot = noch nicht erklaert), Fotoansicht (Kanten ins Foto projiziert).
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/editor_draht.py KAM.json BILDER KANTEN.npz START.json DATEI.json [--port 8767]
START.json = Segmente (kanten_schleife) oder DATEI.json (bereits bearbeiteter Stand, hat Vorrang). Gespeichert wird in DATEI.json (+ Zeitstempel-Sicherung). Nutzerkorrekturen: fix=true (nie von der Schleife ueberschrieben)."""
import sys, os, json, time, shutil, numpy as np, cv2
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from scipy.spatial import cKDTree
KAM = json.load(open(sys.argv[1])); BD = sys.argv[2]; kz = np.load(sys.argv[3]); START = sys.argv[4]; DATEI = sys.argv[5]; PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8767
v = kz["vis"]; r = kz["kan"] / np.maximum(v, 1); PK = kz["P"][(v >= 6) & (r >= 0.5)].astype(np.float32); print("Kantenpunkte", len(PK), flush=True)
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor_draht.html"); FOTOS = sorted(KAM)
def laden():
    if os.path.exists(DATEI): return json.load(open(DATEI))
    S = json.load(open(START))["segmente"]; return {"kanten": [dict(id=i, pts=[s[0], s[1]], quelle="auto", fix=False, kurve=False) for i, s in enumerate(S)]}
D = laden()
def dicht(k, h=0.02):
    P = np.array(k["pts"], float)
    if len(P) < 2: return P
    if k.get("kurve") and len(P) >= 3:                                             # Catmull-Rom
        Q = np.vstack([P[0], P, P[-1]]); out = []
        for i in range(1, len(Q) - 2):
            for t in np.linspace(0, 1, 12, endpoint=False): out.append(0.5 * (2 * Q[i] + (-Q[i - 1] + Q[i + 1]) * t + (2 * Q[i - 1] - 5 * Q[i] + 4 * Q[i + 1] - Q[i + 2]) * t * t + (-Q[i - 1] + 3 * Q[i] - 3 * Q[i + 1] + Q[i + 2]) * t ** 3))
        out.append(P[-1]); P = np.array(out)
    S = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        n = max(int(np.linalg.norm(b - a) / h), 1)
        for t in np.linspace(0, 1, n + 1)[1:]: S.append(a + (b - a) * t)
    return np.array(S)
def abdeckung():
    if not D["kanten"]: return dict(recall=0.0, offen=len(PK)), np.zeros((0, 3), np.float32)
    S = np.vstack([dicht(k) for k in D["kanten"]]); d, _ = cKDTree(S).query(PK); off = d > 0.03; return dict(recall=float(1 - off.mean()), offen=int(off.sum()), n=len(D["kanten"])), PK[off]
def foto_overlay(name, sel, bildbreite=1400):
    K = KAM[name]; im = cv2.imread(os.path.join(BD, name), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); s = bildbreite / K["W"]; im = cv2.resize(im, (bildbreite, int(K["H"] * s))); R = np.array(K["Rn"]); t = np.array(K["tn"]); k1 = K["params"][3]
    def pr(P):
        X = P @ R.T + t; z = X[:, 2]; x = X[:, 0] / np.maximum(z, 1e-3); y = X[:, 1] / np.maximum(z, 1e-3); f = 1 + k1 * (x * x + y * y); return np.c_[(K["f"] * x * f + K["cx"]) * s, (K["f"] * y * f + K["cy"]) * s], z
    for k in D["kanten"]:
        P = dicht(k, 0.05)
        if len(P) < 2: continue
        uv, z = pr(P); ok = z > 1; col = (0, 0, 255) if k["id"] in sel else ((255, 160, 0) if k.get("fix") else (0, 200, 0)); th = 4 if k["id"] in sel else 2
        for i in range(len(P) - 1):
            if ok[i] and ok[i + 1]: cv2.line(im, tuple(np.round(uv[i]).astype(int)), tuple(np.round(uv[i + 1]).astype(int)), col, th, cv2.LINE_AA)
    return cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()
def bestes_foto(pts):
    P = np.array(pts, float); m = P.mean(0); best = (-1, None)
    for f, K in KAM.items():
        X = P @ np.array(K["Rn"]).T + np.array(K["tn"]); z = X[:, 2]; u = K["f"] * X[:, 0] / np.maximum(z, 1e-3) + K["cx"]; w = K["f"] * X[:, 1] / np.maximum(z, 1e-3) + K["cy"]
        n = int(((z > 1) & (u > 50) & (u < K["W"] - 50) & (w > 50) & (w < K["H"] - 50)).sum()) - 0.02 * float(np.linalg.norm(np.array(K["C"]) - m))
        if n > best[0]: best = (n, f)
    return best[1]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _s(self, c, ty, b): self.send_response(c); self.send_header("Content-Type", ty); self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/": self._s(200, "text/html; charset=utf-8", (open(HTML, encoding="utf-8").read() + ('<img src="/api/warte" width=1 height=1>' if "test" in q else "")).encode())      # ?test: Ladeereignis verzoegern, damit ein Headless-Schnappschuss nach dem Datenladen kommt
        elif u.path == "/api/warte": time.sleep(12); self._s(200, "image/gif", b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        elif u.path == "/api/draht": self._s(200, "application/json", json.dumps(D).encode())
        elif u.path == "/api/punkte": self._s(200, "application/octet-stream", PK.tobytes())
        elif u.path == "/api/abdeckung": a, off = abdeckung(); self._s(200, "application/json", json.dumps(dict(a, off=off.round(3).ravel().tolist())).encode())
        elif u.path == "/api/fotos": self._s(200, "application/json", json.dumps(FOTOS).encode())
        elif u.path == "/api/foto": sel = set(int(x) for x in q.get("sel", [""])[0].split(",") if x); self._s(200, "image/jpeg", foto_overlay(q["name"][0], sel))
        elif u.path == "/api/bestes_foto": k = [k for k in D["kanten"] if k["id"] == int(q["id"][0])]; self._s(200, "application/json", json.dumps(bestes_foto(k[0]["pts"]) if k else None).encode())
        else: self._s(404, "text/plain", b"nein")
    def do_POST(self):
        global D
        if self.path == "/api/draht":
            n = int(self.headers.get("Content-Length", 0)); D = json.loads(self.rfile.read(n)); os.makedirs(os.path.dirname(os.path.abspath(DATEI)), exist_ok=True)
            if os.path.exists(DATEI): shutil.copy(DATEI, DATEI + "." + time.strftime("%Y%m%d_%H%M%S") + ".bak")
            json.dump(D, open(DATEI, "w")); a, _ = abdeckung(); self._s(200, "application/json", json.dumps(a).encode())
        else: self._s(404, "text/plain", b"nein")
print("Editor http://localhost:%d  Datei %s  Kanten %d" % (PORT, DATEI, len(D["kanten"])), flush=True); ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

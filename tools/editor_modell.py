#!/usr/bin/env python3
"""editor_modell.py <objekt> --kameras k.json --bilder dir [--foto ip_IMG_6161.jpg] [--port 8766]
Browser-Editor (Nutzerwunsch 8.11.): Modellkanten je Bauteil ueber das Foto, Teil anklicken, mit der Maus VERSCHIEBEN (u = entlang Fassade, z = Hoehe),
'Kanten-Snap' sucht automatisch die beste Lage an den Fotokanten (Canny + Distanztransformation, +-0,8 m), 'Speichern' schreibt die Verschiebung in die Parameter
von objekt.json (Sicherung objekt.json.edit_bak, werte_quellen Regel 3b). Eigener Server (127.0.0.1), unabhaengig vom Messserver.
Grenzen (MVP): nur Verschiebung (kein Skalieren); Teile werden einzeln vom Generator gebaut (Bau schlaegt bei manchen fehl -> in der Liste markiert);
nach dem Speichern ist das Gesamt-STL NICHT neu gebaut (tools/baukasten_gen.py), nur die Kanten des gespeicherten Teils werden neu geladen."""
import sys, os, json, argparse, subprocess, shutil, datetime, threading, urllib.parse
import numpy as np, cv2, trimesh
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--kameras", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--foto", default="ip_IMG_6161.jpg"); ap.add_argument("--port", type=int, default=8766); a = ap.parse_args()
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OJ = os.path.join(R0, "modelle", a.objekt, "objekt.json"); KAM = json.load(open(a.kameras)); SW = 1613
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor_modell.html"); LOCK = threading.Lock(); CACHE = {}; DT = {}; PIV = {}
def obj(): return json.load(open(OJ))
def uax():
    n = np.array(obj()["fassade_n"]["wert"], float); n /= np.linalg.norm(n); return np.array([n[1], -n[0]])

def kanten(b, mt):
    """3D-Kanten (m) eines Bauteils: Generator mit NUR_BAUTEIL, scharfe Kanten (> 0,6 rad), max. 4000 Segmente. Cache je Typ + objekt.json-Zeit."""
    k = (b["typ"], mt)
    if k in CACHE: return CACHE[k]
    nm = "_ed_%d.stl" % abs(hash(b["typ"])); env = dict(os.environ, NUR_BAUTEIL=b["typ"], OBJ_DIR=a.objekt, STL_NAME=nm, SCALE="87", ELEMENTE_AUS="/dev/null")
    subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"), os.path.join(R0, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True)
    p = os.path.join(R0, "modelle", "stl", nm)
    if not os.path.exists(p): CACHE[k] = None; return None
    m = trimesh.load(p, process=False); os.remove(p); m.apply_scale(87 / 1000); m.merge_vertices(); V = np.asarray(m.vertices); e = m.face_adjacency_edges[m.face_adjacency_angles > 0.6]
    if len(e) > 4000: e = e[np.random.default_rng(0).choice(len(e), 4000, replace=False)]
    lo, hi = m.bounds; PIV[b["typ"]] = [float((lo[0] + hi[0]) / 2), float((lo[1] + hi[1]) / 2), float(lo[2])]   # Drehpunkt/Skalenanker = Huellmitte (x,y), Unterkante (z) des AKTUELLEN Teils
    CACHE[k] = np.hstack([V[e[:, 0]], V[e[:, 1]]]).round(3).tolist(); return CACHE[k]

def dt_foto(foto):
    if foto not in DT:
        g = cv2.imread(os.path.join(a.bilder, foto), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
        ed = cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 60, 140); DT[foto] = cv2.distanceTransform(255 - ed, cv2.DIST_L2, 3)
    return DT[foto]

def proj(K, X):
    Xc = X @ np.array(K["Rn"]).T + np.array(K["tn"]); z = Xc[:, 2]; s = SW / K["W"]
    return (K["f"] * Xc[:, :2] / np.where(z > 0.5, z, 0.5)[:, None] + [K["cx"], K["cy"]]) * s, z

def snap(foto, E, du, dz, rad=0.8, st=0.04):
    """beste Zusatzverschiebung (u,z) in +-rad: mittlerer Abstand der projizierten Kantenpunkte (5 je Kante) zur naechsten Fotokante minimal. Rueckgabe (du,dz,vorher,nachher)"""
    K = KAM[foto]; D = dt_foto(foto); E = np.asarray(E, float); t = np.linspace(0, 1, 5)[None, :, None]; Q = (E[:, None, :3] * (1 - t) + E[:, None, 3:] * t).reshape(-1, 3); u_ = uax()
    def sc(a_, b_):
        X = Q.copy(); X[:, :2] += np.outer(np.full(len(X), a_), u_); X[:, 2] += b_; uv, z = proj(K, X); x = np.clip(uv[:, 0].round().astype(int), 0, D.shape[1] - 1); y = np.clip(uv[:, 1].round().astype(int), 0, D.shape[0] - 1)
        ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < D.shape[1]) & (uv[:, 1] >= 0) & (uv[:, 1] < D.shape[0]); return float(np.minimum(D[y[ok], x[ok]], 12).mean()) if ok.sum() > 20 else 99.0
    s0 = sc(du, dz); best = (s0, du, dz)
    for a_ in np.arange(du - rad, du + rad + 1e-9, st):
        for b_ in np.arange(dz - rad, dz + rad + 1e-9, st):
            s = sc(a_, b_)
            if s < best[0] - 1e-9: best = (s, a_, b_)
    return best[1], best[2], s0, best[0]

ZP = {"fensterreihe": ["unterseite_z", "kaempfer_z", "scheitel_z", "riegel_z"], "bogenreihe": ["kaempfer_z", "scheitel_z", "oberkante_z"], "erker": ["spitze_z", "unterkante_z", "oberkante_z"],
      "satteldach": ["z_first", "z_traufe_v", "z_traufe_h", "z_unten"], "balkonband": ["oberseite_z"], "gaubenreihe": [], "quader": ["z0", "z1"]}
UP = {"fensterreihe": ["u_mitte"], "bogenreihe": ["u0"], "erker": ["mitte_u"], "satteldach": ["u0", "u1"], "balkonband": ["u_von", "u_bis"], "gaubenreihe": ["u_mitte"], "quader": ["u0", "u1"]}
def speichern(ed):
    O = obj(); shutil.copy(OJ, OJ + ".edit_bak"); out = []
    for b in O["bauteile"]:
        e = ed.get(b["typ"])
        if not e: continue
        du, dz = float(e["du"]), float(e["dz"]); fam = b["typ"].split(":")[0]; q = b.setdefault("werte_quellen", {}); txt = "editor_modell.py: vom Nutzer im Foto %s verschoben (du %.3f m, dz %.3f m), Kanten-Snap %s" % (a.foto, du, dz, "ja" if e.get("snap") else "nein")
        fu, fz, rl, gi = (float(e.get(k, v)) for k, v in (("fu", 1.0), ("fz", 1.0), ("roll", 0.0), ("gier", 0.0)))
        if fam == "stl_teil":
            if (abs(fu - 1) > 1e-4 or abs(fz - 1) > 1e-4 or abs(rl) > 1e-3 or abs(gi) > 1e-3):
                import trimesh as _t
                n_ = np.array(O["fassade_n"]["wert"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]]); piv = np.array(e["pivot"], float)
                if b.get("anker_m"): A = np.array(b["anker_m"], float)
                else:
                    Pm = np.vstack([np.asarray(_t.load(f if os.path.isabs(f) else os.path.join(os.path.dirname(OJ), f), process=False).vertices) for f in b["dateien"]]) / (1000 / 87); lo, hi = Pm.min(0), Pm.max(0); A = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
                pn, pu, pz = (piv[:2] - A[:2]) @ n_, (piv[:2] - A[:2]) @ u_, piv[2] - A[2]     # Pivot im Ankerrahmen (n,u,z)
                su0, sz0, du0, dz0 = (float(b.get(k, v)) for k, v in (("su", 1.0), ("sz", 1.0), ("du", 0.0), ("dz", 0.0)))
                b["su"], b["sz"] = round(su0 * fu, 4), round(sz0 * fz, 4); b["du"], b["dz"] = round(du0 * fu + pu * (1 - fu) + du, 3), round(dz0 * fz + pz * (1 - fz) + dz, 3)
                if abs(rl) > 1e-3 or abs(gi) > 1e-3:
                    if abs(float(b.get("roll_grad", 0))) > 1e-3 or abs(float(b.get("gier_grad", 0))) > 1e-3: out.append("%s: Teil war schon gedreht - Drehung NICHT uebernommen (erst zuruecksetzen)" % b["typ"])
                    else: b["roll_grad"], b["gier_grad"], b["rot_pivot"] = round(rl, 3), round(gi, 3), [round(pn, 3), round(pu + du, 3), round(pz + dz, 3)]; q["roll_grad"] = q["gier_grad"] = txt
                for k in ("su", "sz", "du", "dz"): q[k] = txt + " (Skalierung fu %.3f fz %.3f)" % (fu, fz)
            else:
                for k, d in (("du", du), ("dz", dz)): b[k] = round(float(b.get(k, 0.0)) + d, 3); q[k] = txt
        else:
            for k in UP.get(fam, []):
                if b.get(k) is not None: b[k] = round(float(b[k]) + du, 3); q[k] = txt
            for k in ZP.get(fam, []):
                if b.get(k) is not None: b[k] = round(float(b[k]) + dz, 3); q[k] = txt
            if fam == "gaubenreihe" and abs(dz) > 1e-6: out.append("%s: dz nicht uebernommen (Gauben haengen am Dach)" % b["typ"])
        out.append("%s: du %.3f dz %.3f" % (b["typ"], du, dz))
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False); return out

class H(BaseHTTPRequestHandler):
    def log_message(self, *x): pass
    def _send(self, code, ctype, body): self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            h = open(HTML, encoding="utf-8").read()
            if "test" in q: h += '<img src="/api/warte" width=1 height=1>'   # Testhilfe: Ladeereignis verzoegern, damit ein Headless-Screenshot das fertige Bild zeigt
            self._send(200, "text/html; charset=utf-8", h.encode())
        elif u.path == "/api/warte": import time; time.sleep(25); self._send(200, "image/gif", b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        elif u.path == "/api/start": self._send(200, "application/json", json.dumps(dict(fotos=sorted(KAM), foto=a.foto, teile=[b["typ"] for b in obj()["bauteile"] if b.get("aktiv", True) is not False], u=uax().tolist())).encode())
        elif u.path == "/api/bild":
            f = q.get("foto", [a.foto])[0]; g = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
            self._send(200, "image/jpeg", cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes())
        elif u.path == "/api/kamera": K = KAM[q.get("foto", [a.foto])[0]]; self._send(200, "application/json", json.dumps(dict(K={k: K[k] for k in ("Rn", "tn", "f", "cx", "cy", "W")}, s=SW / K["W"])).encode())
        elif u.path == "/api/kanten":
            typ = q["typ"][0]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            self._send(200, "application/json", json.dumps(dict(typ=typ, kanten=E, pivot=PIV.get(typ), n=(np.array(obj()["fassade_n"]["wert"], float) / np.linalg.norm(obj()["fassade_n"]["wert"])).tolist(), stl=typ.startswith("stl_teil"))).encode())
        else: self._send(404, "text/plain", b"nein")
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/snap":
            typ = d["typ"]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            if not E: return self._send(200, "application/json", json.dumps(dict(fehler="Teil nicht baubar")).encode())
            du, dz, s0, s1 = snap(d.get("foto", a.foto), E, float(d["du"]), float(d["dz"])); self._send(200, "application/json", json.dumps(dict(du=round(du, 3), dz=round(dz, 3), vorher=round(s0, 2), nachher=round(s1, 2))).encode())
        elif self.path == "/api/speichern":
            with LOCK: r = speichern(d["teile"])
            self._send(200, "application/json", json.dumps(dict(ok=True, log=r, hinweis="objekt.json geschrieben (Sicherung .edit_bak). Gesamt-STL neu bauen: tools/baukasten_gen.py")).encode())
        else: self._send(404, "text/plain", b"nein")
print("Editor: http://127.0.0.1:%d/  Objekt %s" % (a.port, a.objekt), flush=True); ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()

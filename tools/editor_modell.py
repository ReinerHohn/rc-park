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
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "editor_modell.html"); LOCK = threading.Lock(); CACHE = {}; DT = {}; PIV = {}; MESH = {}
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
    MESH[b["typ"]] = np.asarray(m.triangles, np.float32).tobytes()
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
SKAL = {"satteldach", "fensterreihe", "bogenreihe", "balkonband"}     # parametrische Familien, bei denen Breite/Hoehe ziehen auf Parameter abbildbar ist
SKALBR = {"fensterreihe": ["pitch", "breite"], "bogenreihe": ["pitch", "oeffnung_breite", "pfeiler_breite"]}
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
            if fam not in SKAL: fu = fz = 1.0
            piv = np.array(e.get("pivot") or [0, 0, 0], float); u_ = uax(); pu, pz = float(piv[:2] @ u_), float(piv[2])    # Skalierung um die Huellmitte (u) bzw. Unterkante (z) des Teils
            for k in UP.get(fam, []):
                if b.get(k) is not None: b[k] = round(pu + (float(b[k]) - pu) * fu + du, 3); q[k] = txt + (" (Breite x%.3f)" % fu if fu != 1 else "")
            for k in ZP.get(fam, []):
                if b.get(k) is not None: b[k] = round(pz + (float(b[k]) - pz) * fz + dz, 3); q[k] = txt + (" (Hoehe x%.3f)" % fz if fz != 1 else "")
            if fu != 1:
                for k in SKALBR.get(fam, []):
                    if b.get(k) is not None: b[k] = round(float(b[k]) * fu, 4); q[k] = txt + " (Breite x%.3f)" % fu
            if fam == "gaubenreihe" and abs(dz) > 1e-6: out.append("%s: dz nicht uebernommen (Gauben haengen am Dach)" % b["typ"])
        out.append("%s: du %.3f dz %.3f" % (b["typ"], du, dz))
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False); return out

def rdp(P, e):
    P = np.asarray(P, float)
    if len(P) < 3: return P
    a, b = P[0], P[-1]; v = b - a; d = np.abs(v[0] * (P[:, 1] - a[1]) - v[1] * (P[:, 0] - a[0])) / (np.linalg.norm(v) + 1e-9); i = int(np.argmax(d))
    if d[i] > e: return np.vstack([rdp(P[:i + 1], e)[:-1], rdp(P[i:], e)])
    return np.vstack([a, b])

def kontur_info(typ):
    """Fensterkontur eines fensterreihe-Bauteils: gespeicherte 'kontur' oder die Standardform (Rechteck + Kielbogen wie baukasten_gen.fensterreihe), Fenstermitten u, Bezug z0, Wandebene s"""
    b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
    if typ.split(":")[0] == "freiform": return dict(kontur=b["kontur"], mitten=[0.0], z0=float(b["ebene_z"]), s=float(b["ebene_s"]), neig=float(b["neigung_grad"]), eigen=True)
    if typ.split(":")[0] != "fensterreihe": return None
    nf, u0, pitch, bw = int(b["n_fenster"]), float(b["u_mitte"]), float(b["pitch"]), float(b["breite"]); z0, zk, zs = float(b["unterseite_z"]), float(b["kaempfer_z"]), float(b["scheitel_z"]); kiel = float(b.get("kiel", 0.4))
    if b.get("kontur"): K = [[float(x), float(z)] for x, z in b["kontur"]]; eigen = True
    else:
        t = np.linspace(0, 1, 16); zz = zk + (zs - zk) * (t - kiel * np.sin(2 * np.pi * t) / (2 * np.pi)); right = [(bw / 2 * (1 - tt), z_ - z0) for tt, z_ in zip(t, zz)]; left = [(-bw / 2 * (1 - tt), z_ - z0) for tt, z_ in zip(t[::-1], zz[::-1])]
        K = [[-bw / 2, 0.0], [bw / 2, 0.0]] + [list(map(float, p_)) for p_ in right] + [list(map(float, p_)) for p_ in left[1:]]; eigen = False; K = rdp(K, 0.025).tolist()    # Standardform auf wenige Punkte vereinfachen (leichter zu ziehen)
    return dict(kontur=[[round(x, 3), round(z, 3)] for x, z in K], mitten=[round(u0 + i * pitch, 3) for i in range(nf)], z0=z0, s=float(b["wand_n"]) + float(b.get("tiefe", 0.3)), eigen=eigen, neig=0.0)

def griffe_von(b):
    """Ziehbare Parameter-Griffe je Familie: (id, Beschriftung, u, s (n-Ebene), z). Ziehen -> griff_anwenden schreibt die betroffenen Parameter."""
    fam = b["typ"].split(":")[0]; G = []
    if fam == "bogenreihe":
        nb, u0, pt, ow, sn = int(b["n_boegen"]), float(b["u0"]), float(b["pitch"]), float(b["oeffnung_breite"]), float(b["pfeiler_n"])
        for i in range(nb):
            uc = u0 + (i + 0.5) * pt
            G += [("scheitel_%d" % i, "Scheitel", uc, sn, float(b["scheitel_z"])), ("kaempfer_%d" % i, "Kaempfer rechts", uc + ow / 2, sn, float(b["kaempfer_z"])), ("fuss_%d" % i, "Fuss rechts", uc + ow / 2, sn, float(b["boden_z"])), ("ober_%d" % i, "Oberkante", uc, sn, float(b["oberkante_z"]))]
    elif fam == "satteldach":
        u0, u1 = float(b["u0"]), float(b["u1"])
        G = [("first_l", "First links", u1, float(b["n_first"]), float(b["z_first"])), ("first_r", "First rechts", u0, float(b["n_first"]), float(b["z_first"])),
             ("traufe_l", "Traufe links", u1, float(b["n_traufe_v"]), float(b["z_traufe_v"])), ("traufe_r", "Traufe rechts", u0, float(b["n_traufe_v"]), float(b["z_traufe_v"]))]
    elif fam == "fensterreihe":
        u0, pt, bw, sn = float(b["u_mitte"]), float(b["pitch"]), float(b["breite"]), float(b["wand_n"]) + float(b.get("tiefe", 0.3))
        G = [("scheitel", "Scheitel", u0, sn, float(b["scheitel_z"])), ("kaempfer", "Kaempfer", u0 + bw / 2, sn, float(b["kaempfer_z"])), ("unten", "Unterkante rechts", u0 + bw / 2, sn, float(b["unterseite_z"])),
             ("pitch", "Abstand (naechstes Fenster)", u0 + pt, sn, float(b["kaempfer_z"])), ("lage", "Reihe verschieben", u0, sn, float(b["unterseite_z"]))]
    return [dict(id=i, label=l, u=round(u, 3), s=round(sv, 3), z=round(z, 3)) for i, l, u, sv, z in G]

def griff_anwenden(typ, gid, u, z):
    O = obj(); b = [x for x in O["bauteile"] if x["typ"] == typ][0]; fam = typ.split(":")[0]; q = b.setdefault("werte_quellen", {}); txt = "editor_modell.py: Griff '%s' im Foto %s gezogen" % (gid, a.foto); n = dict(b)   # n = neue Werte
    if fam == "bogenreihe":
        k, i = gid.rsplit("_", 1); i = int(i); uc = float(b["u0"]) + (i + 0.5) * float(b["pitch"])
        if k == "scheitel": n["scheitel_z"] = z; n["oberkante_z"] = float(b["oberkante_z"]) + (z - float(b["scheitel_z"])); n["u0"] = float(b["u0"]) + (u - uc)     # Oberkante (Abstand zum Scheitel) folgt
        elif k == "kaempfer": n["kaempfer_z"] = z; n["oeffnung_breite"] = 2 * (u - uc)
        elif k == "fuss": n["boden_z"] = z; n["oeffnung_breite"] = 2 * (u - uc)
        elif k == "ober": n["oberkante_z"] = z
        if not (n["boden_z"] < n["kaempfer_z"] < n["scheitel_z"] < n["oberkante_z"]) or n["oeffnung_breite"] < 0.5: return "Unplausibel: Reihenfolge boden < kaempfer < scheitel < oberkante bzw. Oeffnung >= 0,5 m verletzt"
    elif fam == "satteldach":
        if gid.endswith("_l"): n["u1"] = u
        else: n["u0"] = u
        if gid.startswith("first"): n["z_first"] = z
        else: n["z_traufe_v"] = z
        if not (n["z_traufe_v"] < n["z_first"]) or n["u1"] - n["u0"] < 1: return "Unplausibel: Traufe muss unter dem First liegen, Dach >= 1 m breit"
    elif fam == "fensterreihe":
        u0 = float(b["u_mitte"])
        if gid == "scheitel": n["scheitel_z"] = z
        elif gid == "kaempfer": n["kaempfer_z"] = z; n["breite"] = 2 * (u - u0)
        elif gid == "unten": n["unterseite_z"] = z; n["breite"] = 2 * (u - u0)
        elif gid == "pitch": n["pitch"] = u - u0
        elif gid == "lage": n["u_mitte"] = u; dz = z - float(b["unterseite_z"]); [n.__setitem__(k_, float(b[k_]) + dz) for k_ in ("unterseite_z", "kaempfer_z", "scheitel_z", "riegel_z")]
        if not (n["unterseite_z"] < n["kaempfer_z"] < n["scheitel_z"]) or n["breite"] >= n["pitch"] or n["breite"] < 0.3: return "Unplausibel: unten < kaempfer < scheitel, Breite 0,3 m bis kleiner als Abstand"
    else: return "Dieses Teil hat keine Griffe"
    shutil.copy(OJ, OJ + ".edit_bak")
    for k, v in n.items():
        if k != "werte_quellen" and v != b.get(k) and isinstance(v, (int, float)): b[k] = round(float(v), 3); q[k] = txt
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False); return None

def freiform_anlegen(d):
    """neues Bauteil freiform:<name> (oder ersetzen) mit der im Foto gezeichneten Kontur; Quelle = Nutzerzeichnung (Regel 3b)"""
    O = obj(); shutil.copy(OJ, OJ + ".edit_bak"); ref = [b for b in O["bauteile"] if b.get("achse_n")][0]; typ = "freiform:" + d["name"]
    b = dict(typ=typ, gruppe="Freiform vom Nutzer gezeichnet: " + d["name"], kontur=[[round(float(x), 3), round(float(z), 3)] for x, z in d["kontur"]], ebene_s=round(float(d["s0"]), 3), ebene_z=round(float(d["z0"]), 3), neigung_grad=round(float(d["neig"]), 2),
             tiefe=round(float(d["tiefe"]), 3), modus=d.get("modus", "anbau"), achse_n=ref["achse_n"], achse_quelle=ref.get("achse_quelle", ""),
             quelle="editor_modell.py: Kontur vom Nutzer im Foto %s gezeichnet (%s), auf Ebene s=%.2f z=%.2f Neigung %.1f Grad projiziert; Tiefe %.2f m ist ANNAHME (Foto sieht keine Tiefe)" % (d.get("foto", a.foto), datetime.date.today().isoformat(), float(d["s0"]), float(d["z0"]), float(d["neig"]), float(d["tiefe"])))
    O["bauteile"] = [x for x in O["bauteile"] if x["typ"] != typ] + [b]; json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False)

def kontur_speichern(typ, K):
    O = obj(); shutil.copy(OJ, OJ + ".edit_bak")
    for b in O["bauteile"]:
        if b["typ"] == typ: b["kontur"] = [[round(float(x), 3), round(float(z), 3)] for x, z in K]; b.setdefault("werte_quellen", {})["kontur"] = "editor_modell.py: Fensterkontur vom Nutzer im Foto %s gezeichnet/verschoben (%d Punkte, relativ zur Fenstermitte und unterseite_z)" % (a.foto, len(K))
    json.dump(O, open(OJ, "w"), indent=1, ensure_ascii=False)

class H(BaseHTTPRequestHandler):
    def log_message(self, *x): pass
    def _send(self, code, ctype, body): self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            h = open(HTML, encoding="utf-8").read()
            if "test" in q: h += '<img src="/api/warte" width=1 height=1><script>setTimeout(async()=>{try{sel=%r;zeichne();if(%s){await formUm();const q0=FM.kontur[5],pp=fmPt(0,q0),w=unproj(pp[0],pp[1]);msg("ROUNDTRIP "+q0+" -> "+[(w.u-FM.mitten[0]).toFixed(3),(w.z-FM.z0).toFixed(3)]+" Punkte "+FM.kontur.length);return}const b=c.getBoundingClientRect(),k=b.width/c.width,h=griffe(BB).find(x=>x.hx==%s&&x.hy==%s),E=(t,x,y)=>c.dispatchEvent(new MouseEvent(t,{clientX:b.left+x*k,clientY:b.top+y*k,bubbles:true}));E("mousedown",h.x,h.y);E("mousemove",h.x+(%s),h.y+(%s));window.onmouseup();msg("SIM "+JSON.stringify(off[sel])+" dx="+(h.x)+" BB="+JSON.stringify(BB))}catch(e){msg("SIMFEHLER "+e+e.stack)}},20000)</script>' % (q.get("typ", ["stl_teil:fassade"])[0], "true" if "form" in q else "false", q.get("hx", ["1"])[0], q.get("hy", ["0"])[0], q.get("dx", ["120"])[0], q.get("dy", ["0"])[0])   # Testhilfe: Ladeereignis verzoegern, damit ein Headless-Screenshot das fertige Bild zeigt
            self._send(200, "text/html; charset=utf-8", h.encode())
        elif u.path == "/api/warte": import time; time.sleep(25); self._send(200, "image/gif", b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        elif u.path == "/api/start": self._send(200, "application/json", json.dumps(dict(fotos=sorted(KAM), foto=a.foto, teile=[b["typ"] for b in obj()["bauteile"] if b.get("aktiv", True) is not False], u=uax().tolist())).encode())
        elif u.path == "/api/bild":
            f = q.get("foto", [a.foto])[0]; g = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); g = cv2.resize(g, (SW, int(g.shape[0] * SW / g.shape[1])), interpolation=cv2.INTER_AREA)
            self._send(200, "image/jpeg", cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes())
        elif u.path == "/api/kamera": K = KAM[q.get("foto", [a.foto])[0]]; self._send(200, "application/json", json.dumps(dict(K={k: K[k] for k in ("Rn", "tn", "f", "cx", "cy", "W", "H") if k in K}, s=SW / K["W"])).encode())
        elif u.path == "/api/kontur": self._send(200, "application/json", json.dumps(kontur_info(q["typ"][0]) or {}).encode())
        elif u.path == "/3d": self._send(200, "text/html; charset=utf-8", (open(os.path.join(os.path.dirname(HTML), "editor_3d.html"), encoding="utf-8").read() + ('<img src="/api/warte" width=1 height=1>' if "test" in q else "")).encode())
        elif u.path.startswith("/vendor/"): self._send(200, "application/javascript", open(os.path.join(os.path.dirname(HTML), "vendor", os.path.basename(u.path)), "rb").read())
        elif u.path == "/api/mesh":
            typ = q["typ"][0]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            self._send(200, "application/octet-stream", MESH.get(typ, b"") if E else b"")
        elif u.path == "/api/griffe": typ = q["typ"][0]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]; self._send(200, "application/json", json.dumps(dict(g=griffe_von(b))).encode())
        elif u.path == "/api/kanten":
            typ = q["typ"][0]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            self._send(200, "application/json", json.dumps(dict(typ=typ, kanten=E, pivot=PIV.get(typ), n=(np.array(obj()["fassade_n"]["wert"], float) / np.linalg.norm(obj()["fassade_n"]["wert"])).tolist(), stl=typ.startswith("stl_teil"), skal=typ.startswith("stl_teil") or typ.split(":")[0] in SKAL)).encode())
        else: self._send(404, "text/plain", b"nein")
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/snap":
            typ = d["typ"]; b = [x for x in obj()["bauteile"] if x["typ"] == typ][0]
            with LOCK: E = kanten(b, os.path.getmtime(OJ))
            if not E: return self._send(200, "application/json", json.dumps(dict(fehler="Teil nicht baubar")).encode())
            du, dz, s0, s1 = snap(d.get("foto", a.foto), E, float(d["du"]), float(d["dz"])); self._send(200, "application/json", json.dumps(dict(du=round(du, 3), dz=round(dz, 3), vorher=round(s0, 2), nachher=round(s1, 2))).encode())
        elif self.path == "/api/bauen":
            with LOCK:
                env = dict(os.environ, SCALE="87", OBJ_DIR=os.path.join(R0, "modelle", a.objekt)); t0 = datetime.datetime.now()
                r = subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"), os.path.join(R0, "tools", "baukasten_gen.py"), a.objekt], env=env, capture_output=True, text=True, cwd=os.path.join(R0, "modelle", a.objekt))
            self._send(200, "application/json", json.dumps(dict(ok=r.returncode == 0, sek=round((datetime.datetime.now() - t0).total_seconds(), 1), log=(r.stdout + r.stderr)[-400:])).encode())
        elif self.path == "/api/griff":
            with LOCK: err = griff_anwenden(d["typ"], d["id"], float(d["u"]), float(d["z"]))
            self._send(200, "application/json", json.dumps(dict(ok=err is None, fehler=err)).encode())
        elif self.path == "/api/freiform":
            with LOCK: freiform_anlegen(d)
            self._send(200, "application/json", json.dumps(dict(ok=True)).encode())
        elif self.path == "/api/kontur":
            with LOCK: kontur_speichern(d["typ"], d["kontur"])
            self._send(200, "application/json", json.dumps(dict(ok=True)).encode())
        elif self.path == "/api/speichern":
            with LOCK: r = speichern(d["teile"])
            self._send(200, "application/json", json.dumps(dict(ok=True, log=r, hinweis="objekt.json geschrieben (Sicherung .edit_bak). Gesamt-STL neu bauen: tools/baukasten_gen.py")).encode())
        else: self._send(404, "text/plain", b"nein")
print("Editor: http://127.0.0.1:%d/  Objekt %s" % (a.port, a.objekt), flush=True); ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()

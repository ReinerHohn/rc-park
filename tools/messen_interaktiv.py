#!/usr/bin/env python3
"""messen_interaktiv.py <objekt> --wolke w.npy --kameras k.json --bilder dir [--foto ip_IMG_6161.jpg] [--port 8765]
Interaktives Messen AUS DER WOLKE (Nutzerwunsch 8.11.): lokaler Webserver (nur 127.0.0.1) + Browserseite. Nutzer zieht im Foto eine Box um das gefragte Feature,
das Werkzeug misst die Lage (u,n,z) aus der Wolke (Logik wie wolke_messen.py) UND zeigt die Gegenprobe als Kreuz in 3 anderen Fotos (Blickrichtungs-Vielfalt);
Nutzer bestaetigt/verwirft, danach kommt automatisch das naechste Feature der Liste modelle/<objekt>/messliste.json (fehlt sie: Standardliste unten).
Ergebnis (nur bestaetigte): modelle/<objekt>/messungen_wolke.json, Quelle je Eintrag: Foto, Box, Median, Streuung, Gegenproben. Kein Fit. Keine Daten verlassen den Rechner."""
import sys, os, json, argparse, base64, threading, urllib.parse, datetime
import numpy as np, cv2
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--kameras", required=True); ap.add_argument("--bilder", required=True)
ap.add_argument("--foto", default="ip_IMG_6161.jpg"); ap.add_argument("--port", type=int, default=8765); ap.add_argument("--tiefe", type=float, default=0.4); a = ap.parse_args()
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OD = os.path.join(R0, "modelle", a.objekt); AUS = os.path.join(OD, "messungen_wolke.json")
P = np.load(a.wolke)[:, :3].astype(np.float32); KAM = json.load(open(a.kameras)); OBJ = json.load(open(os.path.join(OD, "objekt.json")))
nax = np.array(OBJ["fassade_n"]["wert"], float); nax /= np.linalg.norm(nax); UAX = np.array([nax[1], -nax[0]])
STD = [("spitze_links", "Spitze des LINKEN Turmhelms (oberster Punkt)"), ("spitze_rechts", "Spitze des RECHTEN Turmhelms"), ("turm_links_unten", "Unterseite des Erkerkastens LINKS (wo der Kasten unten aufhoert, ueber der Arkade)"),
       ("turm_rechts_unten", "Unterseite des Erkerkastens RECHTS"), ("bogen1_scheitel", "Scheitel (hoechster Punkt) des Bogens 1 von LINKS in der Arkade"), ("bogen2_scheitel", "Scheitel Bogen 2 von links"),
       ("bogen3_scheitel", "Scheitel Bogen 3 von links"), ("bogen4_scheitel", "Scheitel Bogen 4 von links"), ("first_links", "linkes Ende des Dachfirsts"), ("first_rechts", "rechtes Ende des Dachfirsts"),
       ("traufe_links", "linkes Ende der Dachtraufe (Dachunterkante)"), ("traufe_rechts", "rechtes Ende der Dachtraufe"), ("boden_mitte", "Boden vor der Fassade (Pflaster, Mitte)")]
LISTE = json.load(open(os.path.join(OD, "messliste.json"))) if os.path.exists(os.path.join(OD, "messliste.json")) else [{"id": i, "frage": q} for i, q in STD]
ERG = json.load(open(AUS)) if os.path.exists(AUS) else []; LOCK = threading.Lock(); SW = 1613

def bild(name, w=None):
    g = cv2.imread(os.path.join(a.bilder, name), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)   # roh, wie kalibriert
    return g if w is None else cv2.resize(g, (w, int(g.shape[0] * w / g.shape[1])), interpolation=cv2.INTER_AREA)

def projiziere(K, X):
    Xc = X @ np.array(K["Rn"]).T + np.array(K["tn"]); z = Xc[:, 2]; ok = z > 1
    return K["f"] * Xc[:, :2] / np.where(ok, z, 1)[:, None] + [K["cx"], K["cy"]], z, ok

def kreis(U, Z):
    """algebraische Kreisanpassung (u,z): Mitte, Radius, RMS-Rest (m)"""
    A = np.c_[2 * U, 2 * Z, np.ones(len(U))]; b = U ** 2 + Z ** 2; s_ = np.linalg.lstsq(A, b, rcond=None)[0]; r = float(np.sqrt(max(s_[2] + s_[0] ** 2 + s_[1] ** 2, 0)))
    return dict(mitte_u=round(float(s_[0]), 3), mitte_z=round(float(s_[1]), 3), radius=round(r, 3), rms=round(float(np.sqrt(np.mean((np.hypot(U - s_[0], Z - s_[1]) - r) ** 2))), 3))

def messen(foto, box, pfad=None):
    erw = 1.0; K = KAM[foto]; S = K["W"] / SW; uv, z, ok = projiziere(K, P)
    if pfad:   # Linie/Freihand: nur Wolkenpunkte direkt unter dem Strich (Strichbreite 14 Anzeige-Pixel)
        M = np.zeros((int(K["H"]), int(K["W"])), np.uint8); cv2.polylines(M, [np.array([[x * S, y * S] for x, y in pfad], np.int32)], False, 255, int(14 * S))
        iu = np.clip(uv[:, 0].astype(int), 0, M.shape[1] - 1); iv = np.clip(uv[:, 1].astype(int), 0, M.shape[0] - 1); m = ok & (M[iv, iu] > 0) & (uv[:, 0] >= 0) & (uv[:, 0] < M.shape[1]) & (uv[:, 1] >= 0) & (uv[:, 1] < M.shape[0])
    else:
        for fak in (1.0, 1.6, 2.5):   # zu wenig Wolke unter der Box (z. B. Unterseiten) -> Box um den Mittelpunkt vergroessern
            cx_, cy_ = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2; hw, hh = max(box[2] - box[0], 12) / 2 * fak, max(box[3] - box[1], 12) / 2 * fak
            x0, y0, x1, y1 = [v * S for v in (cx_ - hw, cy_ - hh, cx_ + hw, cy_ + hh)]; m = ok & (uv[:, 0] > x0) & (uv[:, 0] < x1) & (uv[:, 1] > y0) & (uv[:, 1] < y1)
            if m.sum() >= 30: break
        erw = fak
    if m.sum() < 30: return None
    Q = P[m]; d = z[m]; Q = Q[d <= np.percentile(d, 100 * a.tiefe)]; U = Q[:, :2] @ UAX; N = Q[:, :2] @ nax
    r = dict(box_erweitert=(erw if not pfad and erw > 1 else None), punkte=int(len(Q)), xyz=[round(float(v), 3) for v in np.median(Q, 0)], u=round(float(np.median(U)), 3), u_p10_p90=[round(float(v), 2) for v in np.percentile(U, [10, 90])],
             n=round(float(np.median(N)), 3), z=round(float(np.median(Q[:, 2])), 3), z_p10_p90=[round(float(v), 2) for v in np.percentile(Q[:, 2], [10, 90])])
    if pfad and len(Q) >= 40: r["u_min_max"] = [round(float(U.min()), 2), round(float(U.max()), 2)]; r["z_min_max"] = [round(float(Q[:, 2].min()), 2), round(float(Q[:, 2].max()), 2)]; r["kreis_u_z"] = kreis(U, Q[:, 2])
    return r

def gegenproben(foto, xyz, k=3):
    X = np.array([xyz], np.float32); cand = []; Ps = P[::8]; sicht = 0
    for nm, K in KAM.items():
        if nm == foto: continue
        uv, z, ok = projiziere(K, X)
        if ok[0] and 0.1 * K["W"] < uv[0, 0] < 0.9 * K["W"] and 0.1 * K["H"] < uv[0, 1] < 0.9 * K["H"] and 4 < z[0] < 80 and os.path.exists(os.path.join(a.bilder, nm)):
            C = np.array(K["C"], np.float32); ray = X[0] - C; L = float(np.linalg.norm(ray)); r = ray / L; t = (Ps - C) @ r; perp = np.linalg.norm((Ps - C) - t[:, None] * r, axis=1)
            cand.append((int(((t > 1) & (t < L - 1.5) & (perp < 0.6)).sum()), nm, np.array(K["C"]), uv[0]))   # Sichtlinientest: Punkte VOR dem Ziel = verdeckt
    frei = [c for c in cand if c[0] <= 4]; hinweis = ""
    if not cand: return dict(gegen=[], hinweis="Keine Gegenprobe: kein Foto sieht diesen Punkt im Bild (Abstand 4-80 m, Bildrand-Abstand).")
    if not frei: frei = sorted(cand)[:k * 3]; hinweis = "ACHTUNG: alle %d Fotos mit Blick auf den Punkt sind verdeckt - gezeigte Fotos evtl. verdeckt, Punkt pruefen." % len(cand)
    cand = [(c[1], c[2], c[3]) for c in frei]
    pick = [int(np.argmin([-np.linalg.norm(c[1] - np.array(KAM[foto]["C"])) for c in cand]))]
    while len(pick) < min(k, len(cand)): pick.append(int(np.argmax([min(np.linalg.norm(cand[i][1] - cand[j][1]) for j in pick) for i in range(len(cand))])))
    out = []
    for i in pick:
        nm, _, uv = cand[i]; g = bild(nm); h = 420; x, y = int(uv[0]), int(uv[1]); c = g[max(0, y - h):y + h, max(0, x - h):x + h].copy(); cx, cy = x - max(0, x - h), y - max(0, y - h)
        cv2.drawMarker(c, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 80, 4); c = cv2.resize(c, (360, int(c.shape[0] * 360 / c.shape[1]))); ok_, jb = cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 80])
        out.append(dict(foto=nm, jpg=base64.b64encode(jb.tobytes()).decode()))
    return dict(gegen=out, hinweis=hinweis)

import trimesh
_HB = {}
def modell_ansicht():
    if "m" in _HB: return _HB["m"]
    stl = os.path.join(R0, "modelle", "stl", a.objekt + "_1-87.stl"); m = trimesh.load(stl, process=False); m.apply_scale(87 / 1000); m.merge_vertices(); V = np.asarray(m.vertices)
    ed = m.face_adjacency_edges[m.face_adjacency_angles > 0.6]; U = V[:, 0] * UAX[0] + V[:, 1] * UAX[1]; Z = V[:, 2]; _HB["m"] = (U[ed[:, 0]], Z[ed[:, 0]], U[ed[:, 1]], Z[ed[:, 1]], U.min(), U.max(), Z.min(), Z.max()); return _HB["m"]
def modell_punkt(fid):
    """ungefaehre Lage des Features im MODELL (u,z) aus objekt.json - nur als Klick-Hinweis, kann falsch liegen"""
    B = {b["typ"]: b for b in OBJ["bauteile"]}; e0, e1, br, da = B.get("erker:0"), B.get("erker:1"), B.get("bogenreihe:laube"), B.get("satteldach:haupt")
    try:
        if fid == "spitze_links": return e1["mitte_u"], e1["spitze_z"]
        if fid == "spitze_rechts": return e0["mitte_u"], e0["spitze_z"]
        if fid in ("turm_links_unten", "turm_rechts_unten"):   # unteres Ende der SICHTBAREN Kastengeometrie (nicht Parameter unterkante_z: zwei Erker-Darstellungen im Modell stimmen nicht ueberein)
            e = e1 if fid == "turm_links_unten" else e0; u0, z0, u1, z1 = modell_ansicht()[:4]; um = np.r_[u0, u1]; zm = np.r_[z0, z1]; k = (np.abs(um - e["mitte_u"]) < 1.3) & (zm > 5.0) & (zm < 12.5)
            return e["mitte_u"], float(np.percentile(zm[k], 3)) if k.sum() > 20 else e["unterkante_z"]
        if fid.startswith("bogen") and fid.endswith("_scheitel"):
            k = int(fid[5]); n = br["n_boegen"]; return br["u0"] + (n - k) * br["pitch"] + br["oeffnung_breite"] / 2, br["scheitel_z"]   # Bogen 1 = links im Foto = groesstes u
        if fid == "first_links": return da["u1"], da["z_first"]
        if fid == "first_rechts": return da["u0"], da["z_first"]
        if fid == "traufe_links": return da["u1"], da["z_traufe_v"]
        if fid == "traufe_rechts": return da["u0"], da["z_traufe_v"]
        if fid == "boden_mitte": return 0.0, br["boden_z"]
    except Exception: return None
def hilfsbild(fid):
    u0, z0, u1, z1, umin, umax, zmin, zmax = modell_ansicht(); W, H, pad = 640, 440, 20; sc = min((W - 2 * pad) / (umax - umin), (H - 2 * pad) / (zmax - zmin))
    X = lambda u: int(W - pad - (u - umin) * sc)       # Bildlinks = +u wie im Foto (Blick auf die Fassade)
    Y = lambda z: int(H - pad - (z - zmin) * sc); img = np.full((H, W, 3), 255, np.uint8)
    for i in range(0, len(u0), max(1, len(u0) // 40000)): cv2.line(img, (X(u0[i]), Y(z0[i])), (X(u1[i]), Y(z1[i])), (150, 150, 150), 1)
    pt = modell_punkt(fid)
    if pt: cv2.circle(img, (X(pt[0]), Y(pt[1])), 16, (0, 0, 255), 3); cv2.circle(img, (X(pt[0]), Y(pt[1])), 3, (0, 0, 255), -1)
    cv2.putText(img, "Modell von vorn (ungefaehr, kann falsch liegen)", (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (90, 90, 90), 1, cv2.LINE_AA); ok_, jb = cv2.imencode(".png", img); return jb.tobytes()

HTML_PFAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "messen_interaktiv.html")   # Seite liegt in eigener Datei, wird bei jedem Aufruf neu gelesen (Layout aendern ohne Neustart)

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *x): print(datetime.datetime.now().strftime('%H:%M:%S'), fmt % x, flush=True)
    def _j(self, o): b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/": b = open(HTML_PFAD, encoding="utf-8").read().encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        elif u.path == "/start":
            fo = [n for n in KAM if os.path.exists(os.path.join(a.bilder, n))]; self._j(dict(liste=LISTE, erg={e["id"]: e["mess"] for e in ERG}, fotos=fo, foto=a.foto))
        elif u.path == "/foto":
            n = urllib.parse.parse_qs(u.query)["n"][0]; ok, jb = cv2.imencode(".jpg", bild(n, SW), [cv2.IMWRITE_JPEG_QUALITY, 88]); b = jb.tobytes()
            self.send_response(200); self.send_header("Content-Type", "image/jpeg"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        elif u.path == "/hilfe":
            fid = urllib.parse.parse_qs(u.query)["id"][0]; b = hilfsbild(fid); self.send_response(200); self.send_header("Content-Type", "image/png"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])));
        if self.path == "/messen":
            m = messen(d["foto"], d["box"], d.get("pfad")); self._j(dict(ok=False) if m is None else dict(ok=True, mess=m, gegen=[]))
        elif self.path == "/gegen":
            self._j(gegenproben(d["foto"], d["xyz"]))
        elif self.path == "/uebernehmen":
            with LOCK:
                ERG[:] = [e for e in ERG if e["id"] != d["id"]]; ERG.append(dict(id=d["id"], foto=d["foto"], box_px=d["box"], pfad_px=d.get("pfad"), bildbreite=SW, mess=d["mess"], gegenproben=d["gegen"], wolke=os.path.basename(a.wolke),
                    methode="messen_interaktiv.py: Nutzerbox im Foto -> vorderste Wolkenschicht (%.0f %%), Median; Gegenprobe Kreuz in 3 Fotos vom Nutzer bestaetigt" % (100 * a.tiefe), zeit=datetime.datetime.now().isoformat(timespec="seconds")))
                json.dump(ERG, open(AUS, "w"), indent=1, ensure_ascii=False)
            self._j(dict(ok=True))
print("Wolke %d Punkte, %d Kameras. Seite: http://127.0.0.1:%d/" % (len(P), len(KAM), a.port), flush=True)
ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()

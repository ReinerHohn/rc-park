#!/usr/bin/env python3
"""luecken_seite_bauen.py - Handy-Seite fuer den Vor-Ort-Termin aus tools/foto_luecken.py (Nutzer 10.11.: "vor Ort sehen, wo ich noch fotografieren muss").

Liest <dir>/foto_luecken.json, luecken_3d.json, georef.json, standpunkt_<n>.jpg und schreibt eine eigenstaendige HTML-Seite:
  - Lageplan nordorientiert (UTM-Meter um die Gebaeudemitte): Waende als Linien in Ampelfarbe (gruen gut / orange mittel / rot fehlt),
    Standpunkte nummeriert mit Blickkeil; eigener GPS-Punkt, falls der Browser ihn hergibt (sonst Hinweis).
  - je Standpunkt eine Karte: Vorschaubild (rot = muss ins Bild), Blick (Kompass), Neigung, Zoom, Hoch/Quer, Fotos, Bauteile, Link "in Karten-App oeffnen",
    Haken "erledigt" (nur in diesem Browser gespeichert).
Generisch: alles aus den Dateien des Laufs, nichts Objektspezifisches.
  python3 tools/luecken_seite_bauen.py <foto_luecken_dir> <aus.html> [--titel "Name"] [--bild_px 520]
"""
import sys, os, json, base64, argparse, html
import numpy as np, cv2

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("aus"); ap.add_argument("--titel", default=""); ap.add_argument("--bild_px", type=int, default=520)
    a = ap.parse_args(); d = a.dir
    L = json.load(open(os.path.join(d, "foto_luecken.json"))); M = json.load(open(os.path.join(d, "luecken_3d.json"))); G = json.load(open(os.path.join(d, "georef.json")))
    th = np.radians(G["theta_grad"]); R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]]); t = np.array(G["t"])
    xh, yh = np.array(G["xhat_utm"]), np.array(G["yhat_utm"])
    def nord(xy):   # SfM-xy -> LoD2-Rahmen -> UTM-Versatz zur Gebaeudemitte (Ost, Nord) in m
        q = np.atleast_2d(np.asarray(xy, float)) @ R.T + t; return q[..., :1] * xh + q[..., 1:2] * yh
    # luecken_3d.json speichert v/f als flache Listen (x,y,z je Ecke; 3 Ecken je Dreieck), klasse je Dreieck (Index in M["klassen"])
    V = np.asarray(M["v"], float).reshape(-1, 3); F = np.asarray(M["f"], int).reshape(-1, 3); K = np.asarray(M["klasse"], int)
    kn = list(M.get("klassen", ["gut", "mittel", "fehlt"])); assert len(K) == len(F), (len(K), len(F))
    T = V[F]; n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); fl = 0.5 * np.linalg.norm(n, axis=1); n /= 2 * fl[:, None] + 1e-12
    wand = np.abs(n[:, 2]) < 0.3
    # Waende im Plan: Wandflaeche je 1-m-Zelle des Grundrisses und je Blickrichtung (8 Sektoren) gesammelt, ueber alle Hoehen;
    # Strich quer zur Normalen, 0,4 m nach aussen versetzt (Vorder-/Rueckseite getrennt), Farbe = Flaechenanteil je Klasse.
    nm = n[wand, :2] @ R.T; nm = nm[:, :1] * xh + nm[:, 1:2] * yh; nm /= np.linalg.norm(nm, axis=1, keepdims=True) + 1e-12
    mp = nord(T[wand].mean(1)[:, :2]); sek = np.round(np.degrees(np.arctan2(nm[:, 0], nm[:, 1])) / 45).astype(int) % 8
    zell = {}
    for p, s, nn, a_, k, zz in zip(mp, sek, nm, fl[wand], K[wand], T[wand].mean(1)[:, 2]):
        key = (int(np.floor(p[0])), int(np.floor(p[1])), int(s)); e = zell.setdefault(key, [np.zeros(2), np.zeros(2), 0.0, np.zeros(3), 9e9, -9e9])
        e[0] += p * a_; e[1] += nn * a_; e[2] += a_; e[3][min(int(k), 2)] += a_; e[4] = min(e[4], zz); e[5] = max(e[5], zz)
    seg = []
    for (cx, cy, s), (ps, ns, a_, ka, z0, z1) in zell.items():
        if a_ < 0.2: continue
        p = ps / a_; nn = ns / (np.linalg.norm(ns) + 1e-12); q = np.array([-nn[1], nn[0]]) * 0.5; p = p + 0.4 * nn
        seg.append([round(float(p[0] - q[0]), 2), round(float(p[1] - q[1]), 2), round(float(p[0] + q[0]), 2), round(float(p[1] + q[1]), 2),
                    [round(float(x / a_), 2) for x in ka], round(float(a_), 1), round(float(z0 - G.get("z_boden", 0)), 1), round(float(z1 - G.get("z_boden", 0)), 1)])
    # Dach/Grundriss: Umriss aus allen Dreiecken (Flaechen nach oben), grau gefuellt
    dach = nord(T[~wand][:, :, :2].reshape(-1, 2)).reshape(-1, 3, 2) if (~wand).any() else np.zeros((0, 3, 2))
    dachp = [[round(float(x), 1) for x in tri.ravel()] for tri in dach]
    sp = []
    for s in L["standpunkte"]:
        p = nord(np.array(s["position_sfm"][:2]))[0]
        bild = os.path.join(d, f"standpunkt_{s['nr']}.jpg"); b64 = ""
        if os.path.exists(bild):
            im = cv2.imread(bild); h, w = im.shape[:2]; f = a.bild_px / max(h, w)
            if f < 1: im = cv2.resize(im, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
            b64 = base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 74])[1].tobytes()).decode()
        teile = sorted((s.get("erfasst_bauteile_m2") or {}).items(), key=lambda kv: -kv[1])
        sp.append({"nr": s["nr"], "x": round(float(p[0]), 2), "y": round(float(p[1]), 2), "kompass": s.get("blick_kompass_grad"), "neig": s.get("neigung_grad"),
                   "zoom": s.get("zoom"), "format": s.get("format"), "fotos": s.get("fotos"), "versatz": s.get("versatz_seitlich_m"), "abstand": s.get("abstand_mittel_m"),
                   "m2": s.get("erfasst_m2"), "art": s.get("art"), "lat": s.get("lat"), "lon": s.get("lon"),
                   "teile": [[k.replace("__", " "), round(v, 1)] for k, v in teile[:4]], "bild": b64})
    zs = L.get("zusammenfassung", {}); sm = zs.get("summe_m2", {})
    mitte = G["mitte_utm"]
    data = {"seg": seg, "dach": dachp, "sp": sp, "mitte_utm": mitte, "zs": {"gut": sm.get("gut"), "mittel": sm.get("mittel"), "fehlt": sm.get("fehlt"),
            "erreichbar": zs.get("erreichbar_vom_boden_m2"), "erhoeht": zs.get("nur_erhoeht_m2")}, "lage": (G.get("lage") or {}), "erzeugt": L.get("erzeugt", "")}
    titel = a.titel or f"Fotoplan {L.get('objekt', '')}"
    vorlage = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "luecken_seite_vorlage.html")).read()
    out = vorlage.replace("__TITEL__", html.escape(titel)).replace("/*DATA*/", "const DATA=" + json.dumps(data, ensure_ascii=False) + ";")
    open(a.aus, "w").write(out); print("geschrieben", a.aus, len(out) // 1024, "KB,", len(sp), "Standpunkte,", len(seg), "Wandstuecke")

if __name__ == "__main__":
    main()

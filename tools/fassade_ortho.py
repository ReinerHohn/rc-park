#!/usr/bin/env python3
"""fassade_ortho.py - Fassaden-Orthobilder (Meterraster) aus ALLEN kalibrierten Fotos, vollautomatisch (Qualitaetsstufe 3, 2026-11-04).

Je Fassade (koplanare LoD2-WallSurface-Stuecke, gleiche Normale/Ebene) ein (u, z)-Raster mit `--zelle` m: jede Zelle = Punkt auf der Wandebene,
in jedes Foto mit K-Datei (buendel_tor ok) projiziert (Lochkamera + k1 wie COLMAP SIMPLE_RADIAL), sichtbar nur wenn der erste Strahltreffer
gegen das aktuelle Modell (STL der Stufe) innerhalb `--tol` vor/hinter der Zelle liegt (Strahlen: Embree auf der CPU; Zellrechnung ab --gpu-ab Zellen auf der GPU,
hoechstens --gpu-mb MiB, bei Speicherfehler mit Meldung auf der CPU weiter - 17.11.2026).
Guete je Foto und Zelle = cos(Blickwinkel) / (Meter je Pixel); Zellen mit Bodenaufloesung > `--max-mpp` oder Blickwinkel > 70 Grad fallen weg.
Fusion: gewichteter Median je Kanal ueber die Fotos (Verdecker wie Baeume/Menschen sind nicht im Modell -> der Median ueberstimmt sie, wenn
genug Fotos die Zelle sehen); dazu Anzahl Fotos je Zelle (Abdeckung) als eigenes Bild.

Ausgabe in --aus: ortho_<id>.png (fusioniert), abdeckung_<id>.png, ortho_<id>_einzeln/<foto>.png (nur mit --einzeln), fassaden.json
(je Fassade: Wandlinie a,b (Modell-xy), Normale nach aussen, u/z-Bereich, Zelle, Fotos mit Zellenzahl/Guete).

  /media/oem/scan/venv-seg/bin/python -I tools/fassade_ortho.py modelle/kaufhaus_null4/objekt.json --stl <modell.stl> --aus DIR [--zelle 0.05]
Weitere Argumente: --tol 0.10, --max-winkel 70, --fotos <a,b,..>, --max-fotos 40, --waende-stl, --ohne-gpu, --gpu-mb 2600, --einzeln.
Umgebung: cv2/trimesh/torch -> venv-seg (s.o.) oder `tools/py tools/fassade_ortho.py ...`. Exit 0 = fertig; Abbruch mit Text (z. B. zentrierung huelle).

--messflaeche eben (22.11.2026, KREISFALL: Einzelfoto-Orthos auf dem STL des VORIGEN Kettenlaufs - dessen Oeffnungen/Relief waren Naehte, an denen Kanten in jedem
Foto klebten; das Tor-Mass wechselte je Lauf zwischen 4,3 und 5,2 m): Projektionsflaeche UND Verdecker = modellfreier Messkoerper (messkoerper(): LoD2-Fassaden flach in
der Wandebene aus Fotokanten, wandversatz(), sonst LoD2; Dach/Boden aus LoD2), kein --stl noetig (Lauf von null). Fuer alle MESSUNGEN Pflicht (Kette: fenster_ortho,
fenster_ortho_fein); --messflaeche modell (Standard) = alter Weg fuer Anzeige-/Sichtbilder (z. B. Innenwaende durch gebaute Oeffnungen, Stufe bauplan_innen_ortho).
--nur-messkoerper DATEI.stl schreibt nur den Messkoerper (STL in mm wie das Objekt-STL) fuer andere Stufen (Kette: mono).
"""
import os, sys, json, glob, math, argparse, time
import numpy as np, cv2, trimesh
from concurrent.futures import ThreadPoolExecutor
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import fehlteile_finden as FF


def lod2_eigen(obj):
    """Alle LoD2-Flaechen des eigenen Gebaeudes im Modellrahmen: [(typ, P (k, 3))], Ring ohne Schlusspunkt (Wall/Roof/GroundSurface ...)."""
    import lod2_gebaeude as LG
    R = obj["rahmen"]; C0 = np.array(R["mitte_utm"]); XH = np.array(R["xhat_utm"]); YH = np.array(R["yhat_utm"]); Z0 = float(R["gelaende"])
    lok = lambda P: np.c_[(P[:, :2] - C0) @ XH, (P[:, :2] - C0) @ YH, P[:, 2] - Z0]
    picked = LG.extract(obj["lod2"]["gml"], center=tuple(C0), radius=60.0)
    eig = [(m, p) for m, p in picked if m.get("id") == obj["lod2"]["id"]]
    _, polys = eig[0]; out = []
    for t, P in polys:
        P = np.asarray(P, float); P = P[:-1] if np.allclose(P[0], P[-1]) else P
        out.append((t, lok(P)))
    return out


def lod2_waende(obj):
    """LoD2-WallSurface-Polygone des eigenen Gebaeudes im Modellrahmen (wie baukasten_gen.lod2_flaechen/lokal, ohne manifold3d)."""
    import lod2_gebaeude as LG
    R = obj["rahmen"]; C0 = np.array(R["mitte_utm"]); XH = np.array(R["xhat_utm"]); YH = np.array(R["yhat_utm"]); Z0 = float(R["gelaende"])
    lok = lambda P: np.c_[(P[:, :2] - C0) @ XH, (P[:, :2] - C0) @ YH, P[:, 2] - Z0]
    picked = LG.extract(obj["lod2"]["gml"], center=tuple(C0), radius=60.0)
    eig = [(m, p) for m, p in picked if m.get("id") == obj["lod2"]["id"]]
    _, polys = eig[0]; out = []
    for t, P in polys:
        P = np.asarray(P, float); P = P[:-1] if np.allclose(P[0], P[-1]) else P
        if t == "WallSurface": out.append(lok(P))
    gr = np.vstack([lok(np.asarray(P, float)) for t, P in polys if t == "GroundSurface"])[:, :2].mean(0)
    return out, gr


def wandversatz(objekt, F, winkel=5.0, abstand=0.3):
    """Gemessene Lage der Wandebene einer Fassade gegen die LoD2-Ebene (m, + = nach aussen) - MODELLFREI (22.11.2026, Kreisfall Einzelorthos).
    Quelle: audit/schleife_korrekturen.json (tools/ebenen_schleife.py, Wandebene aus triangulierten FOTOKANTEN), Eintraege art 'wandversatz' mit angenommen != false,
    zugeordnet ueber Normale (< winkel Grad) und Ebenenabstand der Bezugspunkte (< abstand m) - nie ueber die Fassadennummer allein.
    Ohne Eintrag: 0 (LoD2-Ebene). Liest NICHT das gebaute Modell. Rueckgabe (versatz, quelle)."""
    p = os.path.join(os.path.dirname(os.path.abspath(objekt)), "audit", "schleife_korrekturen.json")
    if not os.path.exists(p): return 0.0, "LoD2-Ebene (keine audit/schleife_korrekturen.json)"
    try: KK = json.load(open(p)).get("korrekturen", [])
    except Exception as e_: return 0.0, f"LoD2-Ebene (schleife_korrekturen.json unlesbar: {e_})"
    n = np.asarray(F["n"], float)[:2]; o = np.asarray(F["o"], float)[:2]; ws = []
    for K in KK:
        if K.get("art") != "wandversatz" or K.get("angenommen") is False or "w_soll" not in K: continue
        try: nk = np.asarray(K["n"], float)[:2]; ok_ = np.asarray(K["o"], float)[:2]
        except Exception: continue
        if nk @ n > math.cos(math.radians(winkel)) and abs((ok_ - o) @ n) < abstand: ws.append((float(K["w_soll"]) + float((ok_ - o) @ n), K.get("id", "?")))
    if not ws: return 0.0, "LoD2-Ebene (kein Wandversatz fuer diese Fassade)"
    w_ = float(np.median([w for w, _ in ws])); return round(w_, 3), "Wandversatz aus Fotokanten (schleife_korrekturen " + ",".join(str(i) for _, i in ws) + ")"


def _netz(polys):
    """Ebene Polygone (Liste (k, 3)) -> trimesh (Ohrenschnitt in der eigenen Ebene)."""
    import mapbox_earcut as EC
    V, Fc = [], []; nv = 0
    for P in polys:
        P = np.asarray(P, float)
        if len(P) < 3: continue
        c = P.mean(0); _, _, Vt = np.linalg.svd(P - c); q = (P - c) @ Vt[:2].T
        tri = np.asarray(EC.triangulate_float64(q, np.array([len(q)], np.uint32))).reshape(-1, 3)
        if not len(tri): continue
        V.append(P); Fc.append(tri + nv); nv += len(P)
    return trimesh.Trimesh(np.vstack(V), np.vstack(Fc), process=False) if V else None


def messkoerper(eigen, fas, winkel=5.0, abstand=0.3):
    """MODELLFREIER Messkoerper (22.11.2026, Kreisfall Einzelorthos): Projektionsflaeche und Verdecker fuer Messorthos, OHNE Oeffnungen und Relief des gebauten Modells.
    Je Fassade F (LoD2-Gruppe aus fassaden_gruppieren) ihre Wandstuecke polys_uz flach in der Fassadenebene + F['messflaeche']['versatz'] (Fotokanten, sonst 0);
    dazu die uebrigen LoD2-Flaechen des eigenen Gebaeudes (Dach, Boden, kleine Wandstuecke ohne Fassade) unveraendert. Eingabe nur LoD2 + Kantenmessung -> das
    Ergebnis jeder Messung auf diesem Koerper ist vom vorigen Kettenlauf unabhaengig (Wächter tools/test_messflaeche_kreis.py)."""
    polys = []
    for F in fas:
        n = np.array(list(F["n"]) + [0.0]); d = np.array(list(F["d"]) + [0.0]); o = np.array(list(F["o"]) + [0.0]); s0 = float((F.get("messflaeche") or {}).get("versatz", 0.0))
        for poly in F["polys_uz"]:
            q = np.asarray(poly, float); polys.append(o[None] + q[:, :1] * d[None] + s0 * n[None] + q[:, 1:2] * np.array([[0, 0, 1.0]]))
    for t, P in eigen:
        if t == "WallSurface":
            c = P.mean(0); _, _, Vt = np.linalg.svd(P - c); nw = Vt[2].copy(); nw[2] = 0
            if np.linalg.norm(nw) > 0.9:
                nw /= np.linalg.norm(nw)
                if any(abs(float(nw[:2] @ np.asarray(F["n"], float))) > math.cos(math.radians(winkel)) and abs(float((c[:2] - np.asarray(F["o"], float)) @ np.asarray(F["n"], float))) < abstand for F in fas): continue   # Stueck einer Fassade: schon flach drin
        polys.append(P)
    return _netz(polys)


def nachbarn_netz(obj, radius=120.0):
    """Nachbargebaeude (alle anderen LoD2-Gebaeude im Umkreis) als Dreiecksnetz im Modellrahmen: Verdecker, die das Stufenmodell nicht kennt
    (2026-11-04: ohne sie malte fassade_ortho die Nachbarhaeuser auf die Brandwaende f00/f01)."""
    import lod2_gebaeude as LG, mapbox_earcut as EC
    R = obj["rahmen"]; C0 = np.array(R["mitte_utm"]); XH = np.array(R["xhat_utm"]); YH = np.array(R["yhat_utm"]); Z0 = float(R["gelaende"])
    lok = lambda P: np.c_[(P[:, :2] - C0) @ XH, (P[:, :2] - C0) @ YH, P[:, 2] - Z0]
    V, Fc = [], []; nv = 0; ng = 0
    for meta, polys in LG.extract(obj["lod2"]["gml"], center=tuple(C0), radius=radius):
        if meta.get("id") == obj["lod2"]["id"]: continue
        ng += 1
        for t, P in polys:
            P = np.asarray(P, float); P = P[:-1] if np.allclose(P[0], P[-1]) else P
            if len(P) < 3: continue
            P = lok(P); c = P.mean(0); _, _, Vt = np.linalg.svd(P - c); q = (P - c) @ Vt[:2].T
            tri = np.asarray(EC.triangulate_float64(q, np.array([len(q)], np.uint32))).reshape(-1, 3)
            if not len(tri): continue
            V.append(P); Fc.append(tri + nv); nv += len(P)
    if not V: return None, 0
    return trimesh.Trimesh(np.vstack(V), np.vstack(Fc), process=False), ng


def fassaden_gruppieren(waende, mitte, min_flaeche=4.0, winkel=5.0, abstand=0.3):
    """Koplanare Wandstuecke zu Fassaden: Normale (horizontal, nach aussen) innerhalb `winkel`, Ebenenabstand < `abstand` m."""
    st = []
    for P in waende:
        c = P.mean(0); _, s, V = np.linalg.svd(P - c); n = V[2].copy(); n[2] = 0
        if np.linalg.norm(n) < 0.9: continue                                                      # nicht senkrecht
        n /= np.linalg.norm(n)
        if (c[:2] - mitte) @ n[:2] < 0: n = -n
        d = np.array([-n[1], n[0], 0.0]); u = (P - c) @ d; z = P[:, 2]
        fl = 0.5 * abs(np.sum(u * np.roll(z, -1) - np.roll(u, -1) * z))
        st.append(dict(P=P, n=n, off=float(c @ n), fl=fl))
    gruppen = []
    for s_ in sorted(st, key=lambda s_: -s_["fl"]):
        for g in gruppen:
            if g["n"] @ s_["n"] > math.cos(math.radians(winkel)) and abs(s_["off"] - g["off"]) < abstand: g["teile"].append(s_); g["fl"] += s_["fl"]; break
        else: gruppen.append(dict(n=s_["n"], off=s_["off"], teile=[s_], fl=s_["fl"]))
    out = []
    for g in gruppen:
        if g["fl"] < min_flaeche: continue
        n = g["n"]; d = np.array([-n[1], n[0], 0.0]); A = np.vstack([t["P"] for t in g["teile"]])
        o = A[:, :2].mean(0) - n[:2] * ((A[:, :2].mean(0) @ n[:2]) - g["off"])                   # Punkt auf der Ebene
        u = (A[:, :2] - o) @ d[:2]
        out.append(dict(n=n[:2].tolist(), d=d[:2].tolist(), o=o.tolist(), u=[float(u.min()), float(u.max())], z=[float(A[:, 2].min()), float(A[:, 2].max())],
                        flaeche_m2=round(g["fl"], 1), teile=len(g["teile"]),
                        polys_uz=[np.c_[(t["P"][:, :2] - o) @ d[:2], t["P"][:, 2]].round(3).tolist() for t in g["teile"]]))
    return sorted(out, key=lambda f: -f["flaeche_m2"])


def innenwaende(obj):
    """ZURUECKGESETZTE / INNERE WAENDE als eigene Fassaden (18.11.2026, Agent Rueckwand/Laube). Ursache der kahlen Laubenrueckwand am Kaufhaus: die Wandliste kam
    nur aus den LoD2-Aussenwaenden; die Rueckwand der Laube (4,25 m hinter der Bogenwand) war im Bild der Bogenwand nur durch die Boegen zu sehen - parallaxverschoben auf die
    falsche Ebene gezogen, verdeckt von Pfeilern und Bogenzwickeln, und erkannte Oeffnungen wurden in der Ebene der Bogenwand (Luft) geschnitten.
    objekt.json "innenwaende": [{"name": "i00", "a": [x, y], "b": [x, y], "aussen": [x, y], "versatz": -4.25, "u": [u0, u1], "z": [z0, z1], "relief_vorn": 0.5, "quelle": ...}]
    a/b/aussen wie bauteile.Wand (Bezugswand, u ab a), versatz < 0 = hinter der Bezugswand; u/z = Wandfeld im u-Mass der Bezugswand. Sichtbarkeit wie jede Fassade gegen das
    Stufenmodell (die Fotos sehen die Innenwand nur durch die Oeffnungen davor); relief_vorn = wie weit vor der Ebene die vorderste Modellflaeche gesucht wird (kleiner als der
    Abstand zur Wand davor). Ergebnis: Fassade mit id = name, 'innen': true - fassade_fein/fassade_parsing/fenster_aus_parsing laufen darauf wie auf jeder Fassade."""
    out = []
    for i_, w_ in enumerate(obj.get("innenwaende", [])):
        A = np.asarray(w_["a"], float); B = np.asarray(w_["b"], float); t = (B - A) / np.linalg.norm(B - A); n = np.array([t[1], -t[0]])
        if (np.asarray(w_["aussen"], float) - A) @ n < 0: n = -n
        d = np.array([-n[1], n[0]]); o = A + float(w_["versatz"]) * n                                      # gleiche Richtungskonvention wie fassaden_gruppieren (d = n um 90 Grad)
        us = sorted(float((A + u_ * t - A) @ d) for u_ in w_["u"]); z0, z1 = map(float, w_["z"])
        out.append(dict(n=n.tolist(), d=d.tolist(), o=o.tolist(), u=us, z=[z0, z1], flaeche_m2=round((us[1] - us[0]) * (z1 - z0), 1), teile=1,
                        polys_uz=[[[us[0], z0], [us[1], z0], [us[1], z1], [us[0], z1]]], innen=True, versatz=float(w_["versatz"]), relief_vorn=float(w_.get("relief_vorn", 0.5)),
                        quelle_innen=w_.get("quelle", ""), _id=w_.get("name", f"i{i_:02d}")))
    return out


def projizieren(X, R, t, f, cx, cy, k1):
    Xc = X @ R.T + t; z = Xc[:, 2]; xn = Xc[:, 0] / z; yn = Xc[:, 1] / z; r2 = xn * xn + yn * yn; s = 1 + k1 * r2
    return np.c_[f * xn * s + cx, f * yn * s + cy], z


def bilinear(im, x, y):
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]; I = im      # 17.11.2026: nur die 4 abgegriffenen Werte wandeln, nicht das ganze Foto (Profil: 20 von 126 s gingen in astype des Vollbilds, je Fassade und Foto neu)
    g = lambda yy, xx: I[yy, xx].astype(np.float32)
    c = g(y0, x0) * (1 - fx) * (1 - fy) + g(y0, x0 + 1) * fx * (1 - fy) + g(y0 + 1, x0) * (1 - fx) * fy + g(y0 + 1, x0 + 1) * fx * fy
    return np.clip(c + 0.5, 0, 255).astype(np.uint8)


_STRAHL_POOL = None


def erster_treffer(ray, ursprung, richtung, roh=False):
    """Erster Treffer je Strahl: (Dreiecksnummern, Strahlnummern) wie trimesh `intersects_id(multiple_hits=False)`, aber direkt am Embree-Kern.
    17.11.2026 (Profil ober_tvdr 1 cm, 1 Arbeiter): von 52 s in intersects_id rechnete Embree selbst nur ~5 s - der Rest war trimesh-Verpackung
    (Kopien nach float64, erneutes Normieren schon normierter Richtungen, Ursprung je Strahl wiederholt). Der Kern gibt die Python-Sperre frei (gemessen: 4 Faeden = 3,3 x).
    `ursprung` (3,) = ein Punkt fuer alle Strahlen oder (n, 3); `richtung` (3,) oder (n, 3), Einheitsvektoren. Ohne Embree (anderer Strahlkern): der alte Weg ueber trimesh.
    roh=True: statt des Paars ein Feld (n,) mit der Dreiecksnummer je Strahl, -1 = kein Treffer."""
    n = len(richtung) if np.ndim(richtung) == 2 else len(ursprung)
    w = getattr(ray, "_scene", None)
    if w is None or not hasattr(w, "scene"):
        ti, ri = ray.intersects_id(np.broadcast_to(ursprung, (n, 3)), np.broadcast_to(richtung, (n, 3)), multiple_hits=False, return_locations=False)
        if not roh: return ti, ri
        q = np.full(n, -1, np.int32); q[ri] = ti; return q
    o32 = np.ascontiguousarray(np.broadcast_to(((np.asarray(ursprung, np.float64) - w.origin) * w.scale).astype(np.float32), (n, 3)))      # dieselbe Skalierung wie trimesh._EmbreeWrap.run
    d32 = np.ascontiguousarray(np.broadcast_to(richtung if getattr(richtung, "dtype", None) == np.float32 else np.asarray(richtung, np.float64).astype(np.float32), (n, 3)))
    if n >= 400000:                                                                                 # grosse Strahlmengen in Stuecken auf mehreren Kernen (Kern gibt die Python-Sperre frei; Reihenfolge bleibt -> gleiches Ergebnis)
        global _STRAHL_POOL
        if _STRAHL_POOL is None: _STRAHL_POOL = ThreadPoolExecutor(max(2, min(12, (os.cpu_count() or 4) // 2)))
        k = min(8, n // 200000); gr = [(j * n // k, (j + 1) * n // k) for j in range(k)]
        q = np.concatenate(list(_STRAHL_POOL.map(lambda g_: w.scene.run(o32[g_[0]:g_[1]], d32[g_[0]:g_[1]]), gr)))
    else: q = w.scene.run(o32, d32)
    if roh: return q
    ri = np.where(q != -1)[0]
    return q[ri], ri


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", help="Stufenmodell (Pflicht ausser --messflaeche eben / --nur-messkoerper)"); ap.add_argument("--aus")
    ap.add_argument("--messflaeche", choices=("modell", "eben"), default="modell", help="eben = modellfreier Messkoerper (LoD2 flach + Wandversatz aus Fotokanten) als Projektionsflaeche und Verdecker - Pflicht fuer Messungen (Kreisfall 22.11.2026)"); ap.add_argument("--nur-messkoerper", help="nur den Messkoerper als STL (mm, Objekt-Massstab) schreiben und enden")
    ap.add_argument("--zelle", type=float, default=0.05); ap.add_argument("--tol", type=float, default=0.10); ap.add_argument("--relief-vorn", type=float, default=3.0); ap.add_argument("--relief-hinten", type=float, default=6.0); ap.add_argument("--max-mpp", type=float, default=0.06)
    ap.add_argument("--max-winkel", type=float, default=70.0); ap.add_argument("--fotos", help="Komma-Liste (Standard: alle mit K-Datei und buendel_tor ok)")
    ap.add_argument("--waende-stl", action="store_true", help="Fassaden aus senkrechten Modelldreiecken, die keine LoD2-Ebene sind (Erker/Vorbauten)"); ap.add_argument("--min-flaeche", type=float, default=1.0); ap.add_argument("--ohne-innenwaende", action="store_true", help="objekt.json innenwaende (Laube/Arkade-Rueckwand) nicht als Fassaden i00.. mitrechnen"); ap.add_argument("--einzeln", action="store_true"); ap.add_argument("--ohne-nachbarn", action="store_true"); ap.add_argument("--beste", type=int, default=5, help="je Zelle nur die k Fotos mit der besten Guete (cos/mpp) mitteln: 61 Fotos im Median verschmierten Kanten (Kamerareste 1-4 px)"); ap.add_argument("--arbeiter", type=int, default=6, help="parallele Fotos (RAM: Vollbilder bis 0,3 GB je Foto)"); ap.add_argument("--rand", type=float, default=0.5, help="Rand um die Wand (m) fuer Vorsprung/Traufe")
    ap.add_argument("--mit-selbstbau", action="store_true", help="selbst gebaute Vorbauten (audit/vorbauten_auto.json) als Verdecker/Flaeche behalten (vor dem 21.11.2026; zirkulaer fuer Messungen)")
    ap.add_argument("--max-fotos", type=int, default=40, help="je Fassade nur die besten N Kameras (0 = alle)"); ap.add_argument("--gpu-sicht", action="store_true", help="Sichtbarkeit ueber ein GPU-Tiefenbild je Foto statt CPU-Strahlen. Messung 16.11.2026 (ober_tvdr, 700 Kameras): LANGSAMER (61 s gegen 41 s) und weniger streng - Standard bleibt CPU (embree)"); ap.add_argument("--nur", help="Komma-Liste Flaechen-IDs (f02,e05 ...): nur diese rastern (Tests/Vergleiche; IDs bleiben die des vollen Laufs)")
    ap.add_argument("--ohne-gpu", action="store_true", help="Zellrechnung (Projektion, Blickwinkel, Aufloesung, Bildrand-Maske) auf der CPU statt auf der GPU; die CPU rechnet exakt wie vor dem 17.11.2026 (Vergleichsweg)")
    ap.add_argument("--gpu-mb", type=float, default=2600.0, help="Obergrenze fuer den GPU-Speicher dieses Laufs in MiB (torch-Zuteilung; dazu kommen ~0,3 GB Grundlast des Treibers). Wird sie oder der freie Kartenspeicher ueberschritten: Meldung, Rest auf der CPU")
    ap.add_argument("--gpu-ab", type=int, default=500000, help="GPU erst ab so vielen Rasterzellen (alle Fassaden zusammen; 0 = immer). Darunter kostet der Start von torch/CUDA (~1-2 s) mehr, als die Karte spart (gemessen 17.11.2026 ober_tvdr 5 cm: nur f02 = 42 000 Zellen 1,6 s CPU gegen 2,7 s GPU; alle 13 Fassaden = 1,8 Mio. Zellen 8 s CPU gegen 6 s GPU)")
    ap.add_argument("--px-ziel", type=int, default=256, help="Flaechen unter --klein-m2: Zelle = min(--zelle, kleinere Ausdehnung / px-ziel), damit kleine Flaechen (Vorbauseiten, Erkerstreifen) genug Pixel fuer den Erkenner haben (S4: die feste 5-cm-Zelle gab einem 2-m-Streifen nur 40 px; Aufloesung statt Handschwelle ist die physikalische Grenze)")
    ap.add_argument("--klein-m2", type=float, default=20.0, help="Flaechen kleiner als dies bekommen die feinere Zelle (Begruendung: grosse Fassaden brauchen 5 cm, Speicher/Rechenzeit wachsen mit 1/Zelle^2)")
    ap.add_argument("--zelle-min", type=float, default=0.005, help="feinste Zelle (m): Untergrenze, damit eine sehr schmale Flaeche keine Riesenraster erzeugt; 5 mm ~ Bodenaufloesung der besten Fotos (ANNAHME; 1 cm schloss in T1 0,5-m-Erkerfacetten mit < 96 px aus, die Spec verlangt 256 px je 2 m = 7,8 mm)")
    a = ap.parse_args(argv); t0 = time.time(); ZT = {}; _tz = [t0]
    def zeit(name): ZT[name] = round(ZT.get(name, 0.0) + time.time() - _tz[0], 1); _tz[0] = time.time()
    import threading
    def _gpu_vor():                                                                                  # torch + CUDA brauchen ~2 s zum Start: im Hintergrund, waehrend Modell/Raster/Relief auf der CPU laufen
        try: import torch; torch.cuda.is_available() and torch.zeros(1, device="cuda")
        except Exception: pass                                                                       # der Fehler wird unten beim eigentlichen Einschalten gemeldet
    gpu_vor = threading.Thread(target=_gpu_vor, daemon=True)
    EBEN = a.messflaeche == "eben" or bool(a.nur_messkoerper)
    if EBEN and a.waende_stl: sys.exit("--messflaeche eben / --nur-messkoerper und --waende-stl schliessen sich aus (Vorbau-Fassaden kommen aus dem Modell)")
    if not EBEN and not a.stl: sys.exit("--stl fehlt (ohne Modell nur --messflaeche eben)")
    if not a.nur_messkoerper and not a.aus: sys.exit("--aus fehlt")
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt))
    if a.aus: os.makedirs(a.aus, exist_ok=True)
    waende, mitte = lod2_waende(obj)
    if a.waende_stl:                                                                                # 2026-11-05: Vorbauten (Erker) haben keine LoD2-Wand -> Fassaden aus den senkrechten Modelldreiecken;
        ms_ = trimesh.load(a.stl); ms_.apply_scale(obj.get("stl_massstab", 87) / 1000.0)            # nur Flaechen, die KEINE LoD2-Fassade sind (Ebenenabstand > 0,3 m), mit eigener Kennung e00..
        lod = fassaden_gruppieren(waende, mitte); senk = np.abs(ms_.face_normals[:, 2]) < 0.2
        fs = []                                                                                    # zusammenhaengende koplanare Flaechenstuecke (trimesh facets) statt "gleiche Ebene irgendwo im Modell"
        in_fc_ = np.zeros(len(ms_.faces), bool)                                                      # 15.11.2026: vorher `any(i in f for f in facets)` je Dreieck = 550 Mio Python-Schritte, 476 von 484 s (Profil); Ergebnis gleich
        if len(ms_.facets): in_fc_[np.concatenate([np.asarray(f__) for f__ in ms_.facets])] = True
        for fc_ in list(ms_.facets) + [[i_] for i_ in np.where(senk & ~in_fc_ & (ms_.area_faces >= a.min_flaeche))[0]]:
            fc_ = np.asarray(fc_)
            if not senk[fc_].all() or ms_.area_faces[fc_].sum() < a.min_flaeche: continue
            fs += fassaden_gruppieren([ms_.vertices[f_] for f_ in ms_.faces[fc_]], mitte, min_flaeche=a.min_flaeche)
        def lod2_ebene(F_):
            n_ = np.array(F_["n"]); return any(np.dot(n_, L_["n"]) > math.cos(math.radians(5)) and abs(np.dot(F_["o"], n_) - np.dot(L_["o"], n_)) < 0.3 for L_ in lod)
        fas = [F_ for F_ in fs if not lod2_ebene(F_)]
        for i_, F_ in enumerate(fas): F_["id_vorbau"] = f"e{i_:02d}"
        print(f"  Vorbau-Fassaden aus STL: {len(fas)} (von {len(fs)} senkrechten Ebenen >= {a.min_flaeche} m2; Rest = LoD2-Ebenen)")
    else: fas = fassaden_gruppieren(waende, mitte)
    for i_, F_ in enumerate(fas): F_["_id"] = F_.get("id_vorbau") or f"f{i_:02d}"
    if EBEN:                                                                                         # 22.11.2026 KREISFALL: Messflaeche ohne das gebaute Modell (siehe Kopf, messkoerper())
        for F_ in fas: w_, q_ = wandversatz(a.objekt, F_); F_["messflaeche"] = dict(art="eben", versatz=w_, quelle=q_)
        MK = messkoerper(lod2_eigen(obj), fas)
        print("Messflaeche eben (modellfrei): " + ", ".join(f"{F_['_id']} {F_['messflaeche']['versatz']:+.2f} m" for F_ in fas) + f"; Messkoerper {len(MK.faces) if MK is not None else 0} Dreiecke", flush=True)
        if a.nur_messkoerper:
            if MK is None: sys.exit("Messkoerper leer (keine LoD2-Flaechen)")
            mk_ = MK.copy(); mk_.apply_scale(1000.0 / float(obj.get("stl_massstab", 87))); os.makedirs(os.path.dirname(os.path.abspath(a.nur_messkoerper)), exist_ok=True); mk_.export(a.nur_messkoerper)
            print(f"Messkoerper -> {a.nur_messkoerper}"); return 0
        if not a.ohne_innenwaende and obj.get("innenwaende"): print(f"  Innenwaende ({len(obj['innenwaende'])}) entfallen: der Messkoerper ist geschlossen (Sicht durch Oeffnungen nur mit --messflaeche modell)", flush=True)
    elif not a.ohne_innenwaende: fas += innenwaende(obj)                                            # 18.11.2026 (Rueckwand/Laube): zurueckgesetzte Waende (Laube/Arkade) als eigene Fassaden i00..
    if a.nur: fas = [F_ for F_ in fas if F_["_id"] in set(a.nur.split(","))]
    def _kam(k_): c_ = json.load(open(k_)).get("kamera"); return c_ if isinstance(c_, dict) and "rvec" in c_ and "cx" in c_ else None
    alle_k = {os.path.basename(k)[2:-5]: _kam(k) for k in glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))}; alle_k = {n_: c_ for n_, c_ in alle_k.items() if c_}
    mit_tor = any("buendel_tor" in c_ for c_ in alle_k.values())          # 16.11.2026: gibt es das Pruefsiegel im Objekt gar nicht (uebernommene/neu ausgerichtete Kameras), zaehlen alle eigenen/Commons/online-Kameras;
    def _ok(n_, c_):                                                     # Fremdfotos (dl_, neu__) immer nur mit 'vertrauen' (kamera_verfeinern.py), Videobilder nur mit bestandenem Siegel
        if n_.startswith(("dl_", "neu__")): return bool(c_.get("vertrauen"))
        if c_.get("buendel_tor", {}).get("ok"): return True
        return (not mit_tor) and not n_.startswith("video")
    fotos = a.fotos.split(",") if a.fotos else sorted(n_ for n_, c_ in alle_k.items() if _ok(n_, c_))
    print(f"{len(fotos)} Messkameras" + ("" if mit_tor else " (kein buendel_tor im Objekt: alle eigenen/Commons/online + nachgezogene Fremdfotos)"), flush=True)
    if EBEN:
        if MK is None: sys.exit("Messkoerper leer (keine LoD2-Flaechen)")
        m = MK; VSB = dict(zustand="messkoerper", gruppen=0, dreiecke=0)
    else: m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    # 21.11.2026 MESSFEHLER (zirkulaer): das gebaute Vordach verdeckte genau die Fotostellen, aus denen vorbauten_bauplan seinen Wandanschluss misst (uneinig_f00: 19,39 -> ANNAHME 16,74).
    # Selbst gebaute Vorbauten (audit/vorbauten_auto.json) sind weder Verdecker noch Messflaeche; --mit-selbstbau = alter Weg. Bei --waende-stl sind sie die Fassaden selbst -> bleiben.
    from selbstbau_verdecker import selbstbau_boxen, ohne_selbstbau
    _sb = [] if EBEN else selbstbau_boxen(a.objekt)
    if not EBEN: VSB = dict(zustand="keiner", gruppen=len(_sb), dreiecke=0)
    if _sb and (a.mit_selbstbau or a.waende_stl): VSB["zustand"] = "im_modell"
    elif _sb:
        m, VSB["dreiecke"] = ohne_selbstbau(m, _sb); VSB["zustand"] = "entfernt" if VSB["dreiecke"] else "keiner"
        print(f"Verdecker ohne Selbstbau: {VSB['dreiecke']} Dreiecke aus {len(_sb)} Vorbau-Gruppen entfernt (audit/vorbauten_auto.json)", flush=True)
    if obj.get("zentrierung", "huelle") == "huelle": sys.exit("zentrierung huelle nicht unterstuetzt (Rahmen der Buendelkameras = Modellrahmen)")
    # Zellraster je Fassade (Modellrahmen)
    for F in fas:
        n, d, o = np.array(F["n"]), np.array(F["d"]), np.array(F["o"]); u0, u1 = F["u"][0] - a.rand, F["u"][1] + a.rand; z0, z1 = F["z"][0] - a.rand, F["z"][1] + a.rand
        zl = a.zelle
        if a.px_ziel > 0 and F["flaeche_m2"] < a.klein_m2: zl = min(a.zelle, max(a.zelle_min, min(F["u"][1] - F["u"][0], F["z"][1] - F["z"][0]) / a.px_ziel))   # S4: Pixelgroesse je Flaeche
        nu, nz = int(math.ceil((u1 - u0) / zl)), int(math.ceil((z1 - z0) / zl))
        uu = u0 + (np.arange(nu) + 0.5) * zl; zz = z1 - (np.arange(nz) + 0.5) * zl        # Zeile 0 = oben
        U, Z = np.meshgrid(uu, zz); F.update(raster=dict(u0=u0, z1=z1, nu=nu, nz=nz, zelle=zl))
        F["_X"] = np.c_[o[0] + U.ravel() * d[0], o[1] + U.ravel() * d[1], Z.ravel()]
    n_zellen = sum(len(F_["_X"]) for F_ in fas); gpu_klein = n_zellen < a.gpu_ab
    if not a.ohne_gpu and not a.gpu_sicht and not gpu_klein: gpu_vor.start()
    zeit("laden_raster")
    RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector
    ray = RI(m); nb, n_nb = nachbarn_netz(obj) if not a.ohne_nachbarn else (None, 0)
    _ma = trimesh.util.concatenate([m, nb]) if nb is not None else m; FN_ALLE = np.asarray(_ma.face_normals, float); P0_ALLE = np.asarray(_ma.triangles[:, 0], float)
    ray_alle = RI(_ma) if nb is not None else ray                     # Sicht: Modell + Nachbarn; Relief (Ortho-Flaeche): nur Modell
    FN_M = np.asarray(m.face_normals, float); P0_M = np.asarray(m.triangles[:, 0], float)
    def relief_eben(F):                                                                             # 22.11.2026: Messflaeche = Fassadenebene + Wandversatz, nur innerhalb der LoD2-Wandstuecke; keine Oeffnung, kein Relief
        X = F["_X"]; n3 = np.array(F["n"] + [0.0]); r_ = F["raster"]; mp_ = np.zeros((r_["nz"], r_["nu"]), np.uint8)
        for poly in F["polys_uz"]: cv2.fillPoly(mp_, [np.array([[(u_ - r_["u0"]) / r_["zelle"], (r_["z1"] - z_) / r_["zelle"]] for u_, z_ in poly], np.int32)], 1)
        rel = np.where(mp_.ravel() > 0, float(F["messflaeche"]["versatz"]), np.nan)
        F["_loch"] = np.zeros(len(rel), bool); F["_S"] = X + n3 * np.nan_to_num(rel, nan=0.0)[:, None]; F["_rel"] = rel
    def relief(F):                                                                                  # echtes Orthobild: je Zelle die VORDERSTE Modellflaeche entlang -Normale (Erker, Galerie, Arkadenrueckwand)
        if EBEN: return relief_eben(F)
        X = F["_X"]; n3 = np.array(F["n"] + [0.0]); vorn = F.get("relief_vorn", a.relief_vorn)          # Innenwand: nur kurz davor suchen, sonst traefe der Strahl die Bogenwand davor
        ur_ = X + n3 * vorn; dn_ = trimesh.util.unitize(-n3[None])[0]                               # 17.11.2026 (2): Strahlkern direkt, Trefferort mit derselben trimesh-Formel (planes_lines) -> bitgleich zu intersects_location
        ti, ri = erster_treffer(ray, ur_, dn_)
        loc, gut_ = trimesh.intersections.planes_lines(plane_origins=P0_M[ti], plane_normals=FN_M[ti], line_origins=ur_[ri], line_directions=np.broadcast_to(dn_, (len(ri), 3))); ri = ri[gut_]
        rel = np.full(len(X), np.nan); rel[ri] = vorn - np.linalg.norm(loc - ur_[ri], axis=1)   # Relief s (+ = vor der Wandebene)
        rel[rel < -a.relief_hinten] = np.nan
        # 16.11.2026: OEFFNUNGEN. Seit die Fenster echte Loecher sind (aushoehlen), trifft der Strahl dort keine Flaeche -> das Fassadenbild war an jedem Fenster schwarz und die Fenstererkennung fand
        # an der eigenen, schon gebauten Fassade nichts mehr (ober_tvdr: 6 -> 0). Zellen INNERHALB des Fassadenpolygons ohne Flaeche = Oeffnung: Farbe von der Wandebene, sichtbar, wenn nichts DAVOR steht.
        r_ = F["raster"]; mp_ = np.zeros((r_["nz"], r_["nu"]), np.uint8)
        for poly in F["polys_uz"]: cv2.fillPoly(mp_, [np.array([[(u_ - r_["u0"]) / r_["zelle"], (r_["z1"] - z_) / r_["zelle"]] for u_, z_ in poly], np.int32)], 1)
        F["_loch"] = np.isnan(rel) & (mp_.ravel() > 0) if mp_.size == len(rel) else np.zeros(len(rel), bool)
        F["_S"] = X + n3 * np.nan_to_num(rel, nan=0.0)[:, None]; F["_rel"] = rel
    with ThreadPoolExecutor(max(1, min(len(fas), a.arbeiter))) as ex: list(ex.map(relief, fas))      # 17.11.2026 (2): Fassaden nebeneinander (unabhaengig; Embree und numpy geben die Python-Sperre frei)
    zeit("relief")
    # 16.11.2026 KAMERA-VORAUSWAHL je Fassade (Turm: 700 Kameras x 4 Waende rechneten > 2 h, die Verschmelzung sortierte Hunderte Proben je Zelle): je Fassade nur die --max-fotos besten
    # nach (gesehener Anteil der Stichprobe) / (Meter je Pixel), rein aus den K-Dateien (kein Bild laden). 0 = alle wie frueher.
    if a.max_fotos > 0:
        def wahl(F):
            Xg = F["_S"][::61]; Xg = Xg[np.isfinite(Xg).all(1)]; n_ = np.array(F["n"] + [0.0]); wert = []
            for nr_ in fotos:
                c_ = alle_k.get(nr_)
                if not c_: continue
                R0 = cv2.Rodrigues(np.asarray(c_["rvec"], float))[0]; tk_ = np.asarray(c_["t"], float); C0_ = -R0.T @ tk_; v_ = C0_ - Xg; d_ = np.linalg.norm(v_, axis=1); cw_ = (v_ @ n_) / d_; pc_ = Xg @ R0.T + tk_; z_ = np.maximum(pc_[:, 2], 1e-6)
                u_ = c_["f_px"] * pc_[:, 0] / z_ + c_["cx"]; w_ = c_["f_px"] * pc_[:, 1] / z_ + c_["cy"]; mpp_ = d_ / (c_["f_px"] * np.maximum(cw_, 1e-3))
                ok_ = (cw_ > math.cos(math.radians(a.max_winkel))) & (pc_[:, 2] > 1) & (u_ > 0) & (u_ < 2 * c_["cx"]) & (w_ > 0) & (w_ < 2 * c_["cy"]) & (mpp_ < a.max_mpp)
                if not np.isfinite(d_).all() or d_.max() > 2000 or d_.min() < 0.5: continue      # unplausibler Standort (16.11.: eine 'gepruefte' Kamera stand 350 000 km entfernt und gewann wegen ihrer Schaerfe einen Platz)
                if ok_.sum() >= 3: wert.append((float(ok_.mean()) / float(np.median(mpp_[ok_])), nr_))
            F["_wahl"] = set(n for _, n in sorted(wert, reverse=True)[:a.max_fotos])
        with ThreadPoolExecutor(max(1, min(len(fas), a.arbeiter))) as ex: list(ex.map(wahl, fas))
    else:
        for F in fas: F["_wahl"] = None
    import threading, render_kern as rk; GPU_SPERRE = threading.Lock(); m_alle = trimesh.util.concatenate([m, nb]) if nb is not None else m
    # 17.11.2026 (2) ZELLRECHNUNG AUF DER GPU (Nutzer: "warum so viel CPU, so wenig GPU"). Profil 1 cm: nach dem Strahlkern war der groesste Posten die Rechnung ueber ALLE Zellen je Foto und Fassade
    # (Blickvektor, Entfernung, Projektion, Bildrand, Aufloesung: ~35 s auf einem Kern), obwohl meist nur ein Teil der Zellen im Bild liegt. Die GPU rechnet dieselben Formeln in float64 und gibt nur die
    # Zellen im Bild zurueck; Strahlen (Embree), Glaetten (cv2) und Abtasten bleiben auf der CPU und rechnen wie bisher. Gleichheit: die GPU summiert Skalarprodukte in fester Reihenfolge, numpy ueber BLAS -
    # Unterschiede nur in der letzten Stelle (1e-16), wirksam nur genau an einer Schwelle. Gemessen 17.11.2026 mit tools/test_ortho_vergleich.py (ober_tvdr, 1 cm, 13 Fassaden, 111 Bilder mit
    # Einzelbildern/Abdeckung/Relief, 378 Mio. Werte): GPU-Weg und CPU-Weg beide BITGLEICH zur Referenz; 52 s -> 11-15 s (GPU) bzw. 27-29 s (--ohne-gpu). Das ist gemessen, nicht garantiert: nach Aenderungen
    # hier den Vergleich wiederholen (Grenze: groesste Abweichung <= 1 Graustufe, < 0,1 % der Werte). --ohne-gpu = alter Rechenweg. Kleine Aufgaben (< --gpu-ab Zellen, z. B. 5-cm-Laeufe) bleiben auf der CPU.
    GPU = dict(an=False, grund="--ohne-gpu" if a.ohne_gpu else ("--gpu-sicht" if a.gpu_sicht else (f"kleine Aufgabe ({n_zellen} Zellen < --gpu-ab {a.gpu_ab})" if gpu_klein else "")), zellen=n_zellen, paare=0, cpu_paare=0, cache=0, gpu_s=0.0, strahlen=0)
    if not a.ohne_gpu and not a.gpu_sicht and not gpu_klein:
        try:
            gpu_vor.join(); import torch
            if not torch.cuda.is_available(): raise RuntimeError("keine CUDA-Karte sichtbar")
            DEV = torch.device("cuda"); torch.cuda.set_per_process_memory_fraction(min(1.0, a.gpu_mb * 2 ** 20 / torch.cuda.get_device_properties(0).total_memory))
            FNg = torch.from_numpy(FN_ALLE).to(DEV); P0g = torch.from_numpy(P0_ALLE).to(DEV); float(FNg.sum()); GPU["an"] = True
        except Exception as e_:
            GPU["grund"] = f"{type(e_).__name__}: {str(e_)[:160]}"; print(f"ACHTUNG GPU nicht nutzbar ({GPU['grund']}) - Zellrechnung laeuft auf der CPU (langsamer, Ergebnis gleich)", flush=True)

    def gpu_aus(e_):                                                                                # nie still: Speicherfehler/Kartenfehler melden, Rest auf der CPU
        with GPU_SPERRE:
            if not GPU["an"]: return
            GPU["an"] = False; GPU["grund"] = f"{type(e_).__name__}: {str(e_)[:160]}"
            for F_ in fas: F_.pop("_Sg", None)
            try: torch.cuda.empty_cache()
            except Exception: pass
        print(f"ACHTUNG GPU-Fehler nach {GPU['paare']} Foto-Fassaden-Paaren ({GPU['grund']}) - Rest der Zellrechnung auf der CPU (langsamer, Ergebnis gleich)", flush=True)

    def fass_gpu(F):
        """Zellpunkte + Masken der Fassade auf der Karte (bleiben dort, solange alle zusammen hoechstens 40 % der Grenze belegen; sonst je Aufruf neu hochgeladen). Nur unter GPU_SPERRE rufen."""
        g = F.get("_Sg")
        if g is None:
            g = (torch.from_numpy(F["_S"]).to(DEV), torch.from_numpy(F["_loch"]).to(DEV), torch.from_numpy(np.isfinite(F["_rel"]) | F["_loch"]).to(DEV)); nb_ = g[0].numel() * 8 + 2 * len(g[1])
            if GPU["cache"] + nb_ <= 0.4 * a.gpu_mb * 2 ** 20: F["_Sg"] = g; GPU["cache"] += nb_
        return g

    def zellen_gpu(F, Cw, tr, R, t, f, cx, cy, k1, W, H):
        """Stufe 1 auf der GPU: Zellen der Fassade, die im Foto liegen. Rueckgabe None (< 200 Zellen), "standort" (Kamera unplausibel), False (GPU inzwischen aus) oder
        ein Zustand (Tensoren idx, v, dist, cosw, mpp, px auf der Karte; `dirs32` = Strahlrichtungen float32 als numpy fuer Embree). Formeln wie paar_cpu, Skalarprodukte ausgeschrieben."""
        T = torch; n = F["n"] + [0.0]; cgr = math.cos(math.radians(a.max_winkel)); Rl = np.asarray(R, float).tolist(); tl = np.asarray(t, float).tolist(); Cl = np.asarray(Cw, float).tolist(); trl = np.asarray(tr, float).tolist(); teile = []
        with GPU_SPERRE:                                                                             # eine Rechnung zur Zeit: die Karte ist geteilt, der Speicher bleibt klein (ein Block von 1,5 Mio. Zellen ~ 0,35 GB)
            if not GPU["an"]: return False
            tg_ = time.time(); Sg = fass_gpu(F)[0]
            for s0 in range(0, len(Sg), 1500000):
                X = Sg[s0:s0 + 1500000]; x0, x1, x2 = X[:, 0], X[:, 1], X[:, 2]
                v0, v1, v2 = Cl[0] - x0, Cl[1] - x1, Cl[2] - x2; dist = T.sqrt(v0 * v0 + v1 * v1 + v2 * v2); cosw = (v0 * n[0] + v1 * n[1] + v2 * n[2]) / dist
                q0, q1, q2 = x0 + trl[0], x1 + trl[1], x2 + trl[2]; c_ = [q0 * Rl[k_][0] + q1 * Rl[k_][1] + q2 * Rl[k_][2] + tl[k_] for k_ in range(3)]
                z = c_[2]; xn = c_[0] / z; yn = c_[1] / z; s_ = 1 + k1 * (xn * xn + yn * yn); pu = f * xn * s_ + cx; pv = f * yn * s_ + cy
                mpp = dist / (f * T.clamp(cosw, min=1e-3))
                ok = (cosw > cgr) & (z > 1) & (pu >= 0) & (pu < W - 1) & (pv >= 0) & (pv < H - 1) & (mpp < a.max_mpp); j = T.nonzero(ok)[:, 0]
                if len(j): teile.append((j + s0, T.stack([v0[j], v1[j], v2[j]], 1), dist[j], cosw[j], mpp[j], T.stack([pu[j], pv[j]], 1)))
                del X, x0, x1, x2, v0, v1, v2, dist, cosw, q0, q1, q2, c_, z, xn, yn, s_, pu, pv, mpp, ok, j
            GPU["paare"] += 1
            if sum(len(q_[0]) for q_ in teile) < 200: return None
            st = dict(zip(("idx", "v", "dist", "cosw", "mpp", "px"), (T.cat([q_[k_] for q_ in teile]) for k_ in range(6)))); del teile
            if not (np.isfinite(Cw).all() and bool(T.isfinite(st["dist"]).all()) and float(st["dist"].min()) > 0.5 and float(st["dist"].max()) < 2000): return "standort"
            st["dirs"] = -st.pop("v") / st["dist"][:, None]; st["dirs32"] = st["dirs"].to(T.float32).cpu().numpy(); GPU["gpu_s"] += time.time() - tg_; GPU["strahlen"] += len(st["dirs32"]); return st

    def sicht_gpu(F, st, q, Cw):
        """Stufe 2 auf der GPU: aus den Dreiecksnummern des Strahlkerns (q, -1 = kein Treffer) die sichtbaren Zellen. Rueckgabe None (< 200), False (GPU aus) oder (idx, px, mpp, guete) als numpy."""
        T = torch; Cl = np.asarray(Cw, float).tolist()
        with GPU_SPERRE:
            if not GPU["an"]: return False
            tg_ = time.time(); _, lochg, relokg = fass_gpu(F); qg = T.from_numpy(q).to(DEV).long(); tr_ = qg >= 0; qg = T.clamp(qg, min=0); nn = FNg[qg]; p0 = P0g[qg]; d = st["dirs"]; dist = st["dist"]
            nen = d[:, 0] * nn[:, 0] + d[:, 1] * nn[:, 1] + d[:, 2] * nn[:, 2]; zae = (p0[:, 0] - Cl[0]) * nn[:, 0] + (p0[:, 1] - Cl[1]) * nn[:, 1] + (p0[:, 2] - Cl[2]) * nn[:, 2]
            erster = T.where(tr_, zae / T.where(T.abs(nen) < 1e-12, T.full_like(nen, 1e-12), nen), T.full_like(nen, float("inf")))
            loch = lochg[st["idx"]]; sicht = (T.abs(erster - dist) < a.tol + 0.002 * dist) | (loch & (erster > dist - a.tol)); sicht &= relokg[st["idx"]]
            j = T.nonzero(sicht)[:, 0]
            if len(j) < 200: return None
            mpp = st["mpp"][j]; GPU["gpu_s"] += time.time() - tg_; return st["idx"][j].to(T.int32).cpu().numpy(), st["px"][j].cpu().numpy(), mpp.cpu().numpy(), (st["cosw"][j] / mpp).to(T.float32).cpu().numpy()

    def paar_cpu(F, nr, tief, Cw, tr, R, t, f, cx, cy, k1, W, H):
        """Rechenweg bis 17.11.2026 (numpy ueber alle Zellen, Formeln unveraendert). Rueckgabe None oder (idx, px, mpp, guete) wie sicht_gpu."""
        X = F["_S"]; n = np.array(F["n"] + [0.0]); v = Cw - X; dist = np.linalg.norm(v, axis=1); cosw = (v @ n) / dist
        px, z = projizieren(X + tr, R, np.asarray(t, float), f, cx, cy, k1)
        ok = (cosw > math.cos(math.radians(a.max_winkel))) & (z > 1) & (px[:, 0] >= 0) & (px[:, 0] < W - 1) & (px[:, 1] >= 0) & (px[:, 1] < H - 1)
        mpp = dist / (f * np.maximum(cosw, 1e-3)); ok &= mpp < a.max_mpp
        if ok.sum() < 200: return None
        idx = np.where(ok)[0]
        if not (np.isfinite(Cw).all() and np.isfinite(dist[idx]).all() and dist[idx].min() > 0.5 and dist[idx].max() < 2000): print(f"  Kamera {nr} uebersprungen (Standort unplausibel: {Cw})", flush=True); return None
        if not a.gpu_sicht:
            dirs = -v[idx] / dist[idx, None]      # 17.11.2026: nur Dreiecksnummer vom Strahlkern holen und die Entfernung selbst rechnen (Profil: von 66 s Strahlzeit waren 44 s trimesh-Nacharbeit fuer die Trefferorte)
            ti, ri = erster_treffer(ray_alle, Cw, dirs)                                             # 17.11.2026 (2): Strahlkern direkt (siehe erster_treffer)
            erster = np.full(len(idx), np.inf); nn_ = FN_ALLE[ti]; nen = np.einsum("ij,ij->i", dirs[ri], nn_); erster[ri] = np.einsum("ij,ij->i", P0_ALLE[ti] - Cw, nn_) / np.where(np.abs(nen) < 1e-12, 1e-12, nen)
            sicht = np.abs(erster - dist[idx]) < a.tol + 0.002 * dist[idx]                           # erster Kamerastrahl-Treffer = die vorderste Flaeche der Zelle (sonst verdeckt)
        else:                                                                                         # 16.11.2026 (Aufgabenliste 1a): Sichtbarkeit ueber EIN Tiefenbild des Modells je Foto auf der GPU statt eines CPU-Strahls je Zelle
            if tief[0] is None:
                sk = min(1.0, 2400.0 / max(W, H)); Wr, Hr = int(W * sk), int(H * sk); te = np.asarray(t, float) + R @ tr
                with GPU_SPERRE: tief[0] = (np.asarray(rk.dreiecke_rastern(m_alle, R, te, f * sk, cx * sk, cy * sk, Wr, Hr)[0]), sk, Wr, Hr)
            T_, sk, Wr, Hr = tief[0]; pc = (X[idx] + tr) @ R.T + np.asarray(t, float); zc = pc[:, 2]; ui = np.clip((f * pc[:, 0] / zc + cx) * sk, 0, Wr - 1).astype(int); vi = np.clip((f * pc[:, 1] / zc + cy) * sk, 0, Hr - 1).astype(int)
            dmin = np.full(len(idx), np.inf)
            for du, dv in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):                                 # Nachbarpixel mitnehmen: an Kanten trifft der Pixelmittelpunkt sonst die Flaeche daneben
                d_ = T_[np.clip(vi + dv, 0, Hr - 1), np.clip(ui + du, 0, Wr - 1)]; d_ = np.where(d_ > 0, d_, np.inf); dmin = np.where(np.abs(d_ - zc) < np.abs(dmin - zc), d_, dmin)
            sicht = np.abs(dmin - zc) < a.tol + 0.002 * dist[idx]
        if not a.gpu_sicht: sicht |= F["_loch"][idx] & (erster > dist[idx] - a.tol)                   # Oeffnung: sichtbar, wenn der erste Treffer nicht VOR der Wandebene liegt
        sicht &= np.isfinite(F["_rel"][idx]) | F["_loch"][idx]                                        # ohne Modellflaeche ausserhalb der Fassade (Himmel/Nachbar) keine Farbe
        idx = idx[sicht]
        if len(idx) < 200: return None
        return idx.astype(np.int32), px[idx], mpp[idx], (cosw[idx] / mpp[idx]).astype(np.float32)

    def ein_foto(nr):
        K = json.load(open(FF.k_datei(a.objekt, obj, ROOT, nr))); kk = K["kamera"]; pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + ".*")) or glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))   # 15.11.2026: Fotos heissen bei neuen Objekten <nr>.jpg (ohne das fand der Lauf 0 Fotos, 8 min umsonst)
        if not pf: return nr, None
        if "cx" in kk and "rvec" in kk:                                   # 16.11.2026 (Aufgabenliste 1a, Messung: nicht die Strahlen, das LADEN aller Fotos kostet): erst grob pruefen, ob das Foto irgendeine Fassade sieht
            R0 = cv2.Rodrigues(np.asarray(kk["rvec"], float))[0]; t0 = np.asarray(kk["t"], float); C0_ = -R0.T @ t0; sieht = False
            for F in fas:
                Xg = F["_S"][::97]; n_ = np.array(F["n"] + [0.0]); v_ = C0_ - Xg; d_ = np.linalg.norm(v_, axis=1); cw_ = (v_ @ n_) / d_; pc_ = Xg @ R0.T + t0; z_ = np.maximum(pc_[:, 2], 1e-6)
                u_ = kk["f_px"] * pc_[:, 0] / z_ + kk["cx"]; w_ = kk["f_px"] * pc_[:, 1] / z_ + kk["cy"]
                if ((cw_ > math.cos(math.radians(a.max_winkel))) & (pc_[:, 2] > 1) & (u_ > -50) & (u_ < 2 * kk["cx"] + 50) & (w_ > -50) & (w_ < 2 * kk["cy"] + 50) & (d_ / (kk["f_px"] * np.maximum(cw_, 1e-3)) < a.max_mpp)).sum() >= 3: sieht = True; break
            if not sieht or not any(F["_wahl"] is None or nr in F["_wahl"] for F in fas): return nr, None
        im = cv2.imread(pf[0]); H, W = im.shape[:2]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H)
        tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)); k1 = float(kk.get("k1") or 0.0)
        Cw = -R.T @ np.asarray(t, float) - tr                                                        # Kamerazentrum im Modellrahmen
        erg = {}; weich = {}; tief = [None]
        for i, F in enumerate(fas):
            if F["_wahl"] is not None and nr not in F["_wahl"]: continue
            zl = False
            if GPU["an"]:
                try:
                    zl = zellen_gpu(F, Cw, tr, R, t, f, cx, cy, k1, W, H)
                    if isinstance(zl, str): print(f"  Kamera {nr} uebersprungen (Standort unplausibel: {Cw})", flush=True); zl = None
                    elif isinstance(zl, dict): zl = sicht_gpu(F, zl, erster_treffer(ray_alle, Cw, zl["dirs32"], roh=True), Cw)
                except Exception as e_:                                                               # torch.OutOfMemoryError / CUDA-Fehler (geteilte Karte): melden, dieses Paar und den Rest auf der CPU
                    if not (isinstance(e_, RuntimeError) or "CUDA" in str(e_) or "memory" in str(e_).lower()): raise
                    gpu_aus(e_); zl = False
            if zl is False: zl = paar_cpu(F, nr, tief, Cw, tr, R, t, f, cx, cy, k1, W, H); GPU["cpu_paare"] += 1
            if zl is None: continue
            idx, px, mpp, guete = zl                                                                 # nur die sichtbaren Zellen (Felder laufen parallel zu idx)
            # 15.11.2026: Zelle groesser als der Fotopixel -> Foto vor dem Abtasten auf die Zellgroesse glaetten (sonst Aliasing: das 5-cm-Ortho des Kaufhauses war fleckig/koernig)
            sig_ = 0.4 * (F["raster"]["zelle"] / float(np.median(mpp))); sig_ = min(round(sig_ * 2) / 2.0, 6.0)      # 16.11.2026: gedeckelt - ein Foto mit sehr feiner Aufloesung (Tele/Nahaufnahme, f > 10 000 px) gab Sigma in den Hunderten: der Weichzeichner lief minutenlang auf EINEM Kern (Suedwand Turm > 240 s statt 25 s)
            if sig_ >= 1.0:
                if sig_ not in weich: weich[sig_] = cv2.GaussianBlur(im, (0, 0), sig_)
                col = bilinear(weich[sig_], px[:, 0], px[:, 1])
            else: col = bilinear(im, px[:, 0], px[:, 1])
            erg[i] = (idx, col, guete)
        return nr, erg

    zeit("kamerawahl")
    with ThreadPoolExecutor(min(len(fotos), a.arbeiter)) as ex: alle = list(ex.map(ein_foto, fotos))
    zeit("fotos")
    def verschmelzen(iF):
        i, F = iF
        r = F["raster"]; N = r["nu"] * r["nz"]; beitr = [(nr, e[i]) for nr, e in alle if e and i in e]
        F["fotos"] = {nr: dict(zellen=int(len(x[0])), guete_median=round(float(np.median(x[2])), 1)) for nr, x in beitr}
        img = np.zeros((N, 3), np.uint8); cnt = np.zeros(N, np.int32)
        if beitr:
            I = np.concatenate([x[0] for _, x in beitr]); Cc = np.concatenate([x[1] for _, x in beitr]); G = np.concatenate([x[2] for _, x in beitr])   # 20.11.2026 Speicher: Farben bleiben im Quelltyp bis NACH der Auswahl der besten k (1 cm, Turm: > 11,7 GB)
            med_ = [float(np.median(x[1].mean(1))) for _, x in beitr]; Mz = float(np.median(med_)) if med_ else 1.0      # 16.11.2026: Belichtung je Foto angleichen (Nachtaufnahme, Sonne/Schatten, s/w), sonst ist die
            o_ = np.lexsort((-G, I)); Is = I[o_]; st = np.r_[0, np.where(np.diff(Is))[0] + 1, len(Is)]      # nur die Reihenfolge merken, keine sortierten Kopien aller Proben
            cnt[Is[st[:-1]]] = np.diff(st)
            # UNEINIGKEIT (16.11.2026, zweite Fassung): Streuung ueber die Fotos auf GROBEN Bloecken (~0,3 m), Belichtung je Foto angeglichen. Erste Fassung (je Zelle) schlug am Turm ueberall an
            # (25-31 Fotos je Zelle, cm-Versatz an Steinkanten = hohe Streuung) und war bei < 3 Fotos per Definition 0. Grob = "zeigen die Fotos dort dasselbe Ding" (Wand gegen Baum/Nachbarhaus).
            kb = max(1, int(round(0.3 / r["zelle"]))); nbz, nbu = -(-r["nz"] // kb), -(-r["nu"] // kb); Mb = np.full((len(beitr), nbz * nbu), np.nan, np.float32)
            for q_, ((_, x), m_) in enumerate(zip(beitr, med_)):
                bi = (x[0] // r["nu"] // kb) * nbu + (x[0] % r["nu"]) // kb; gg = x[1].mean(1) * float(np.clip(Mz / max(m_, 1.0), 0.4, 2.5)); c_ = np.bincount(bi, minlength=nbz * nbu)
                Mb[q_] = np.where(c_ >= 0.3 * kb * kb, np.bincount(bi, weights=gg, minlength=nbz * nbu) / np.maximum(c_, 1), np.nan)
            with np.errstate(all="ignore"): mdn = np.nanmedian(Mb, 0); mad = np.nanmedian(np.abs(Mb - mdn), 0) * 1.48      # MAD statt Streuung: eine Minderheit abweichender Fotos (Nacht, s/w, Gegenlicht) zaehlt nicht,
            ub = np.where(np.isfinite(Mb).sum(0) >= 2, np.nan_to_num(mad), 0).reshape(nbz, nbu)                               # ein Mosaik ohne Mehrheit schon (dritte Fassung; die Streuung schlug am Turm auf hellem Putz an)
            # STRUKTUR-UNEINIGKEIT (16.11.2026 spaet, vierte Fassung, eigene Karte struktur_<id>.png): die Helligkeitskarte trennt saubere Wand und Mosaik nicht (Turm Sued 30, Zeile 18).
            # Hier je Foto ein 0,1-m-Bild, LOKAL normiert (Mittel/Streuung im 0,9-m-Fenster weg: Belichtung, Schatten, Nacht, s/w fallen heraus; glatter Putz wird ~0), dann MAD ueber die Fotos.
            # Wert x 100 als uint8: ~0-25 = Fotos zeigen dieselbe Struktur (oder alle nichts), > ~45 = verschiedene Dinge (Baum, Nachbarhaus, falsche Kamera).
            ks = max(1, int(round(0.1 / r["zelle"]))); sz, su = -(-r["nz"] // ks), -(-r["nu"] // ks); Ns = np.full((len(beitr), sz, su), np.nan, np.float32)
            for q_, (_, x) in enumerate(beitr):
                bi = (x[0] // r["nu"] // ks) * su + (x[0] % r["nu"]) // ks; c_ = np.bincount(bi, minlength=sz * su); da = (c_ >= 0.3 * ks * ks).reshape(sz, su)
                L_ = (np.bincount(bi, weights=x[1].mean(1), minlength=sz * su) / np.maximum(c_, 1)).reshape(sz, su).astype(np.float32); w_ = da.astype(np.float32); kk = (9, 9)
                n_ = np.maximum(cv2.blur(w_, kk), 1e-6); mu = cv2.blur(L_ * w_, kk) / n_; sd = np.sqrt(np.maximum(cv2.blur(L_ * L_ * w_, kk) / n_ - mu * mu, 0))
                Ns[q_] = np.where(da & (cv2.blur(w_, kk) > 0.5), (L_ - mu) / (sd + 6.0), np.nan)
            with np.errstate(all="ignore"): md_ = np.nanmedian(Ns, 0); st_ = np.nanmedian(np.abs(Ns - md_), 0) * 1.48
            st_ = np.where(np.isfinite(Ns).sum(0) >= 3, np.nan_to_num(st_), 0); st_ = cv2.blur(st_.astype(np.float32), (3, 3)); del Ns
            cv2.imwrite(os.path.join(a.aus, f"struktur_{F['_id']}.png"), cv2.resize(np.clip(st_ * 100, 0, 255).astype(np.uint8), (r["nu"], r["nz"]), interpolation=cv2.INTER_NEAREST))
            cv2.imwrite(os.path.join(a.aus, f"uneinig_{F['_id']}.png"), cv2.resize(np.clip(ub, 0, 255).astype(np.uint8), (r["nu"], r["nz"]), interpolation=cv2.INTER_NEAREST))
            rang = np.arange(len(Is), dtype=np.int32) - np.repeat(st[:-1].astype(np.int32), np.diff(st)); sel = o_[rang < a.beste]; del o_, rang, Is; I, Cc, G = I[sel], Cc[sel].astype(np.float32), G[sel]; del sel   # je Zelle die besten k (gleiche Reihenfolge wie vorher)
            # gewichteter Median je Kanal und Zelle, vektorisiert: Proben je Zelle nach Wert sortieren, kumulierte Gewichte, erster Wert >= halbes Gewicht
            def kanal(k_):
                key = I.astype(np.float64) * 512 + Cc[:, k_]; o2 = np.argsort(key, kind="stable"); Ik, Vk, Gk = I[o2], Cc[o2, k_], G[o2]
                Gk = Gk.astype(np.float64); cs = np.cumsum(Gk); start = np.r_[0, np.where(np.diff(Ik))[0] + 1]; tot = np.add.reduceat(Gk, start);   # 20.11.2026: float64 - die float32-Summe ueber das ganze Raster verlor ab ~1,7e7 Gewichte (falscher Median, Zellen ohne Treffer nahmen die letzte Probe)
                base = np.r_[0, cs[start[1:] - 1]] if len(start) > 1 else np.array([0.0])
                half = base + tot / 2; grp = np.repeat(np.arange(len(start)), np.diff(np.r_[start, len(Ik)])); ueber = cs >= half[grp]
                erst = np.full(len(start), -1); pos_ = np.where(ueber)[0]; g_ = grp[pos_]; first = np.r_[True, g_[1:] != g_[:-1]]; erst[g_[first]] = pos_[first]
                img[Ik[start], k_] = np.clip(Vk[erst], 0, 255).astype(np.uint8)
            with ThreadPoolExecutor(3) as ex3: list(ex3.map(kanal, range(3)))      # 17.11.2026 (2): die drei Farbkanaele nebeneinander (Sortieren gibt die Python-Sperre frei; jeder Kanal schreibt nur seine Spalte)
        tag = F["_id"]; cv2.imwrite(os.path.join(a.aus, f"ortho_{tag}.png"), img.reshape(r["nz"], r["nu"], 3))
        cv2.imwrite(os.path.join(a.aus, f"abdeckung_{tag}.png"), np.clip(cnt * 20, 0, 255).astype(np.uint8).reshape(r["nz"], r["nu"]))
        if a.einzeln:
            ed = os.path.join(a.aus, f"ortho_{tag}_einzeln"); os.makedirs(ed, exist_ok=True)
            for nr, x in beitr:
                b_ = np.zeros((N, 3), np.uint8); b_[x[0]] = x[1]; cv2.imwrite(os.path.join(ed, f"{nr}.png"), b_.reshape(r["nz"], r["nu"], 3))
        F["id"] = tag; F["abdeckung_anteil"] = round(float((cnt > 0).mean()), 3); F["fotos_median_je_zelle"] = float(np.median(cnt[cnt > 0])) if (cnt > 0).any() else 0
        rl = F["_rel"].reshape(r["nz"], r["nu"]); cv2.imwrite(os.path.join(a.aus, f"relief_{tag}.png"), np.where(np.isfinite(rl), np.clip((rl + 10) * 1000, 1, 65535), 0).astype(np.uint16))   # mm + 10 m, 0 = kein Modell
        F["relief_png"] = f"relief_{tag}.png (uint16: (s + 10 m) in mm, 0 = keine Modellflaeche)"
        for _, e_ in alle:                                                     # 20.11.2026 Speicher: Proben dieser Fassade freigeben, sobald sie verschmolzen ist
            if e_: e_.pop(i, None)
        del F["_X"], F["_S"], F["_rel"], F["_loch"]; F.pop("_Sg", None); F.pop("_wahl", None); F.pop("_id", None); return (f"  {tag}: {F['flaeche_m2']:6.1f} m2, n=({F['n'][0]:+.2f},{F['n'][1]:+.2f}), {len(beitr):2d} Fotos, Abdeckung {F['abdeckung_anteil']:.0%}, Median {F['fotos_median_je_zelle']:.0f} Fotos/Zelle")
    _proben = [sum(len(e[i][0]) for _, e in alle if e and i in e) for i in range(len(fas))]; _neben = 3 if max(_proben, default=0) * 60 < 3e9 else 1   # ~60 Byte je Probe in der Spitze: ueber ~3 GB je Fassade nacheinander statt 3 nebeneinander
    if _neben == 1: print(f"Verschmelzen nacheinander (groesste Fassade {max(_proben) / 1e6:.0f} Mio. Proben)", flush=True)
    with ThreadPoolExecutor(max(1, min(len(fas), _neben))) as ex: bericht = list(ex.map(verschmelzen, enumerate(fas)))      # 17.11.2026 (2): bis zu 3 Fassaden nebeneinander (mehr = Arbeitsspeicher: je Fassade alle Proben aller Fotos)
    zeit("verschmelzen_schreiben"); GPU["weg"] = ("GPU" if GPU["an"] else "CPU") if not GPU["cpu_paare"] or not GPU["paare"] else "GPU, dann CPU"
    if GPU["paare"]: GPU["gpu_mb_spitze"] = round(torch.cuda.max_memory_reserved() / 2 ** 20)
    print(f"Zellrechnung: {GPU['weg']} ({GPU['paare']} Foto-Fassaden-Paare GPU, {GPU['cpu_paare']} CPU" + (f", {GPU['strahlen'] / 1e6:.0f} Mio. Sichtstrahlen, GPU-Rechenzeit {GPU['gpu_s']:.1f} s, GPU-Speicher Spitze {GPU['gpu_mb_spitze']} MiB" if GPU["paare"] else "") + (f"; Grund CPU: {GPU['grund']}" if GPU["grund"] else "") + ")", flush=True)
    print("Zeiten (s): " + ", ".join(f"{k_} {v_}" for k_, v_ in ZT.items()), flush=True)
    json.dump(dict(objekt=a.objekt, stl=None if EBEN else os.path.abspath(a.stl), zelle_m=a.zelle, tol_m=a.tol, max_mpp=a.max_mpp, fotos=fotos, fassaden=fas,
                   beste_k=a.beste, nachbarn_lod2=n_nb, verdecker_selbstbau=VSB, messflaeche=a.messflaeche if not EBEN else "eben",
                   quelle="fassade_ortho.py: LoD2-Waende + K-Dateien (buendel_tor) + " + ("modellfreier Messkoerper (LoD2 flach + Wandversatz aus Fotokanten, unabhaengig vom vorigen Lauf)" if EBEN else "Sichtbarkeit gegen Stufenmodell") + " + LoD2-Nachbarn", sekunden=round(time.time() - t0, 1), zeiten_s=ZT, zellrechnung={k_: (round(v_, 1) if isinstance(v_, float) else v_) for k_, v_ in GPU.items() if k_ not in ("an", "cache")}),
              open(os.path.join(a.aus, "fassaden.json"), "w"), indent=1)
    print(f"{len(fas)} Fassaden, {len(fotos)} Fotos, {time.time() - t0:.0f} s"); print("\n".join(bericht))


if __name__ == "__main__":
    main()

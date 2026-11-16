"""modell_3d_html.py - 3D-Seite (three.js) je Objekt: Modell aus tools/dach_bauen.py + dichte Wolke + DOM1 + LoD2-Waende, alles im Rahmen
von objekt.json (u, v, z ueber rahmen.gelaende = Modellsystem der Pruefwerkzeuge). Allgemein; Nutzerregel 'immer 3D-HTML zeigen'.

Aufruf: python -I tools/modell_3d_html.py <objekt.json> <ausgabe.html> [--wolke npy] [--farben npy] [--n 250000] [--radius 45]
Ebenen schaltbar: Modell (Flaechen/Draht), Wolke (Fotofarben), DOM1-Laser (1-m-Pixel), LoD2-Waende. Infokasten: dach.json + Belege (ANNAHMEN).
"""
import sys, os, json, base64, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dach_bauen import gebaeude_aus_lod2, seiten_aus_rahmen
from lod2_gebaeude import grundflaechen
from dom1_kachel import dom1_hoehe

TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modell_3d_html.tpl.html")


def b64(a): return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()
def cm16(X): return b64(np.round(np.asarray(X, float) * 100).clip(-32767, 32767).astype(np.int16))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("aus")
    ap.add_argument("--wolke", default=""); ap.add_argument("--farben", default=""); ap.add_argument("--n", type=int, default=250000)
    ap.add_argument("--radius", type=float, default=45.0); ap.add_argument("--netz_raster", type=float, default=0.0, help="Anzeige-Netz vergroebern: Ecken auf dieses Raster (m) zusammenziehen (Seitenlimit 16 MB)"); ap.add_argument("--extra", nargs="*", default=[], help="weitere STL im selben Rahmen (z. B. Nachbarhaus als eigenes Objekt), werden mit angezeigt")
    a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); r = obj["rahmen"]
    m0 = np.array(r["mitte_utm"], float); xh = np.array(r["xhat_utm"], float); yh = np.array(r["yhat_utm"], float); g0 = float(r["gelaende"])
    k, belege, haupt = gebaeude_aus_lod2(a.objekt)
    me = k.to_mesh(); V = np.asarray(me.vert_properties)[:, :3].astype(np.float32); F = np.asarray(me.tri_verts).astype(np.uint32)
    root = os.path.dirname(os.path.dirname(od)); stl = os.path.join(root, obj.get("stl", "")); ej = os.path.join(od, "elemente.json")
    if obj.get("stl") and os.path.exists(stl) and obj.get("zentrierung") == "achse":     # 15.11.2026: das GEBAUTE Generator-Modell zeigen (STL = Rahmen), nicht den LoD2/Laser-Rumpf neu rechnen
        import trimesh
        ms = trimesh.load(stl, process=True); ms.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0 if obj.get("stl_einheit_mm", True) else 1.0)
        V = np.asarray(ms.vertices, np.float32); F = np.asarray(ms.faces, np.uint32)
        if os.path.exists(ej): belege = json.load(open(ej))
        for ex in a.extra:                                                   # 15.11.2026: Nachbarobjekte im selben Rahmen dazuladen
            me_ = trimesh.load(ex, process=True); me_.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0); F = np.vstack([F, np.asarray(me_.faces, np.uint32) + len(V)]).astype(np.uint32); V = np.vstack([V, np.asarray(me_.vertices, np.float32)]).astype(np.float32)
    if a.netz_raster == 0 and len(F) > 800000:                              # 16.11.2026: Kettenobjekt mit 4 Mio. Dreiecken gab eine 98-MB-Seite (Grenze 16 MB) - Anzeige-Raster selbst waehlen
        for r_ in (0.02, 0.03, 0.04, 0.06, 0.08, 0.10, 0.12):
            _, i_ = np.unique(np.round(V / r_).astype(np.int64), axis=0, return_inverse=True); f_ = i_.ravel()[F]; a.netz_raster = r_
            if int(((f_[:, 0] != f_[:, 1]) & (f_[:, 1] != f_[:, 2]) & (f_[:, 0] != f_[:, 2])).sum()) <= 500000: break
        print(f"Anzeige-Netz automatisch auf {a.netz_raster * 100:.0f}-cm-Raster vergroebert ({len(F)} Dreiecke im STL; das STL bleibt unveraendert)")
    if a.netz_raster > 0:                                                   # Eckpunkt-Clustering nur fuer die Anzeige (das STL bleibt unveraendert)
        q_, inv_ = np.unique(np.round(V / a.netz_raster).astype(np.int64), axis=0, return_inverse=True); F = inv_.ravel()[F]; F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])].astype(np.uint32)
        n_ = np.bincount(inv_.ravel(), minlength=len(q_)).astype(np.float64); V = np.stack([np.bincount(inv_.ravel(), weights=V[:, k_].astype(np.float64), minlength=len(q_)) / n_ for k_ in range(3)], 1).astype(np.float32)   # 16.11.2026: Schwerpunkt der Gruppe statt Rasterpunkt - der Rasterpunkt liegt bis 2 cm NEBEN der Wandebene, lange Wanddreiecke kippten und schattierten als 'Strahlen' (Nutzerbild)
    c = haupt.mean(0)
    D = dict(name=obj.get("name", os.path.basename(od)), mitte=c.round(2).tolist(), seiten=seiten_aus_rahmen(obj),
             mv=b64(V), mf=b64(F), belege=belege)
    # Wolke (Modellsystem = Rahmen)
    if a.wolke and os.path.exists(a.wolke):
        X = np.load(a.wolke, mmap_mode="r"); ok = np.flatnonzero(np.hypot(X[:, 0] - c[0], X[:, 1] - c[1]) < a.radius)
        idx = np.sort(np.random.default_rng(0).choice(ok, min(a.n, len(ok)), replace=False)); D["w"] = cm16(X[idx]); D["wn"] = len(idx)
        if a.farben and os.path.exists(a.farben):
            C = np.load(a.farben, mmap_mode="r")[idx]; C = C if C.max() > 1 else C * 255; D["wc"] = b64(np.asarray(C, np.uint8))
        D["wquelle"] = os.path.basename(a.wolke)
    # DOM1 im Umkreis des Hauptgrundrisses (+8 m)
    u0, v0 = haupt.min(0) - 8; u1, v1 = haupt.max(0) + 8
    uu, vv = np.meshgrid(np.arange(u0, u1, 1.0), np.arange(v0, v1, 1.0)); U = np.c_[uu.ravel(), vv.ravel()]
    EN = m0 + U[:, :1] * xh + U[:, 1:] * yh; EN = np.floor(EN) + 0.5                       # LGL-Pixelmitten
    EN = np.unique(EN, axis=0); z = dom1_hoehe(EN[:, 0], EN[:, 1]) - g0; ok = np.isfinite(z)
    Ud = np.c_[(EN - m0) @ xh, (EN - m0) @ yh][ok]
    D["d"] = cm16(np.c_[Ud, z[ok]]); D["dn"] = int(ok.sum())
    # LoD2-Waende des Zielgebaeudes
    meta, gr, wa = grundflaechen(obj, obj["lod2"]["gml"]); lin = []
    for W in wa:
        Q = np.c_[(W[:, :2] - m0) @ xh, (W[:, :2] - m0) @ yh, W[:, 2] - g0]
        for i in range(len(Q)): lin.append(np.r_[Q[i], Q[(i + 1) % len(Q)]])
    D["l"] = cm16(np.array(lin).reshape(-1, 3)) if lin else ""
    dp = os.path.join(od, "dach.json")
    if os.path.exists(dp): D["dach"] = [dict(teil=t["teil"], **{x: t["beste"][x] for x in ("form", "first", "neigung_grad", "rms_m")},
                                             eindeutig=t.get("eindeutig"), spitze=(t.get("spitze") or {}).get("dom1_max")) for t in json.load(open(dp))["teile"]]
    D["hoehe"] = float(V[:, 2].max())
    html = open(TPL).read().replace("/*__DATA__*/null", json.dumps(D, ensure_ascii=False)).replace("__NAME__", D["name"])
    open(a.aus, "w").write(html)
    print(f"-> {a.aus} ({os.path.getsize(a.aus) / 1e6:.1f} MB): Modell {len(F)} Dreiecke, Wolke {D.get('wn', 0)}, DOM1 {D['dn']}, LoD2-Kanten {len(lin)}")


if __name__ == "__main__":
    main()

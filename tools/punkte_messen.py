#!/usr/bin/env python3
"""UNGUELTIG (2026-11-05, Gegenprobe): Sollpunkt um 0,5 m verschoben wird ebenfalls "gruen 0,07 m" gemessen - die "naechste Ecke zur Projektion"
zieht alle Strahlen zum Sollpunkt (Zirkelschluss), Ausschnitte zeigen Pflaster/Dachziegel statt Gebaeudeecke. NICHT verwenden, bis Ecken
bildgestuetzt (Silhouette gegen Himmel / Linienschnitt / Merkmalszuordnung zwischen Fotos) statt projektionsgestuetzt gefunden werden.

punkte_messen.py - markante Gebaeudepunkte (Ecken, Traufecken, ...) per Triangulation aus allen kalibrierten Fotos messen und gegen das Modell
als AMPEL ausweisen (Nutzerziel 2026-11-05: alles auf 10 cm, Grenze ~20 cm).

Je Sollpunkt X (anker3d.json oder --punkt x y z name): in jedes Foto projizieren (Buendelkamera, k1), Sicht per Strahl gegen Modell + LoD2-Nachbarn,
im Fenster +-fenster_m die Ecken-Kandidaten (Shi-Tomasi) suchen, Kandidat mit staerkster Eckenantwort in Naehe der Projektion -> Sehstrahl.
Alle Strahlen eines Punkts: RANSAC-Triangulation (spitze_hoehe.triangulieren, Konsens >= tri_min) -> gemessener Punkt, RMS, Fotos.
Ampel je Punkt: |gemessen - Soll| <= 0,10 m gruen, <= 0,20 m gelb, sonst rot; ohne Konsens grau (nicht messbar - Fotos fehlen).
Kein Zirkelschluss: der Sollpunkt waehlt nur das Suchfenster; Lage folgt aus dem Konsens unabhaengiger Fotos (Fehlspuren treffen sich nicht, test_spitze_hoehe T2).

  /media/oem/scan/venv-seg/bin/python -I tools/punkte_messen.py <objekt.json> [--stl modell.stl] [--punkt X Y Z NAME ...] [--nur-anker-muster ecke_] [--aus DIR]
"""
import os, sys, json, glob, argparse
import numpy as np, cv2, trimesh
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import fehlteile_finden as FF
from fassade_ortho import projizieren, nachbarn_netz
from spitze_hoehe import triangulieren, _schnitt, _abst


def strahl(px, py, kk, W, H, R, f, C):
    u, v = (px - float(kk.get("cx", W / 2))) / f, (py - float(kk.get("cy", H / 2))) / f; u0, v0 = u, v; k1 = float(kk.get("k1") or 0.0)
    for _ in range(5): r2 = u * u + v * v; u, v = u0 / (1 + k1 * r2), v0 / (1 + k1 * r2)
    d = np.array([u, v, 1.0]) @ np.asarray(R); return C, d / np.linalg.norm(d)


def triangulieren_mehrfach(O, D, F, X, radius, tol):
    """RANSAC ueber Strahlpaare VERSCHIEDENER Fotos; Konsens = Anzahl verschiedener Fotos mit einem Strahl < tol (je Foto der naechste).
    Kein Bezug zur Projektion ausser dem Suchradius um X -> (Punkt, Konsens, Indizes) oder None."""
    uf, fi = np.unique(F, return_inverse=True); best = None
    for i_ in range(len(O)):
        for j_ in range(i_ + 1, len(O)):
            if fi[i_] == fi[j_] or abs(float(D[i_] @ D[j_])) > 0.995: continue
            Y = _schnitt(O, D, [i_, j_])
            if np.linalg.norm(Y - X) > radius: continue
            d_ = _abst(O, D, Y); m_ = np.full(len(uf), np.inf); np.minimum.at(m_, fi, d_); k_ = int((m_ < tol).sum())
            if best is None or k_ > best[1]: best = (Y, k_)
    if best is None: return None
    for _ in range(3):                                                                                     # verfeinern: je Foto naechster Strahl < tol
        d_ = _abst(O, D, best[0]); ix = [int(np.where(fi == g)[0][np.argmin(d_[fi == g])]) for g in range(len(uf)) if d_[fi == g].min() < tol]
        if len(ix) < 2: return None
        best = (_schnitt(O, D, ix), len(ix))
    return best[0], best[1], ix


def ampel(d):
    return "gruen" if d <= 0.10 else ("gelb" if d <= 0.20 else "rot")


def main(argv=None):
    if '--trotzdem' not in (argv or sys.argv): raise SystemExit('punkte_messen.py ist gesperrt (Zirkelschluss, siehe Kopf); --trotzdem nur fuer Gegenproben')
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--punkt", nargs=4, action="append")
    ap.add_argument("--nur-anker-muster", default="ecke_"); ap.add_argument("--fenster-m", type=float, default=0.6); ap.add_argument("--min-ppm", type=float, default=20.0)
    ap.add_argument("--tri-tol", type=float, default=0.15); ap.add_argument("--tri-min", type=int, default=6); ap.add_argument("--alle-kameras", action="store_true"); ap.add_argument("--aus"); ap.add_argument("--trotzdem", action="store_true")
    a = ap.parse_args(argv)
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "punkte_messen"); os.makedirs(aus, exist_ok=True)
    P = []
    if a.punkt: P += [(n, np.array([float(x), float(y), float(z)])) for x, y, z, n in a.punkt]
    else:
        A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]; P += [(n, np.asarray(v["xyz"], float)) for n, v in A.items() if n.startswith(a.nur_anker_muster)]
    ray = None
    if a.stl:
        m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); nb, _ = nachbarn_netz(obj); sz = trimesh.util.concatenate([m, nb]) if nb is not None else m
        ray = (trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector)(sz)
    strahlen = {n: [] for n, _ in P}; bilder = {}
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        K = json.load(open(kp)); kk = K.get("kamera", {})
        if not kk.get("rvec") or (not (kk.get("buendel_tor") or {}).get("ok") and not a.alle_kameras): continue
        nr = os.path.basename(kp)[2:-5]; pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))
        if not pf: continue
        im = None; R = t = None
        for n, X in P:
            if im is None:
                im = cv2.imread(pf[0]); H, W = im.shape[:2]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H); R = np.asarray(R); t = np.asarray(t, float).ravel()
                tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float); C = -R.T @ t - tr; gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
            px, z = projizieren(np.array([X, X + [a.fenster_m, 0, 0]]) + tr, R, t, f, float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)), float(kk.get("k1") or 0.0))
            if (z <= 1).any(): continue
            ppm = float(np.linalg.norm(px[1] - px[0])) / a.fenster_m
            if ppm < a.min_ppm: continue
            hw = int(max(8, a.fenster_m * ppm)); x0, y0 = int(px[0, 0]) - hw, int(px[0, 1]) - hw
            if x0 < 0 or y0 < 0 or x0 + 2 * hw >= W or y0 + 2 * hw >= H: continue
            if ray is not None:                                                                       # Punkt sichtbar? (Strahl darf vorher nichts treffen; 0,3 m Spiel fuer die Kante selbst)
                v = X - C; dd = np.linalg.norm(v); loc, _, _ = ray.intersects_location(C[None], (v / dd)[None], multiple_hits=False)
                if len(loc) and np.linalg.norm(loc[0] - C) < dd - 0.3: continue
            win = gray[y0:y0 + 2 * hw, x0:x0 + 2 * hw]
            ck = cv2.goodFeaturesToTrack(cv2.GaussianBlur(win, (0, 0), max(1.0, ppm * 0.03)), 8, 0.05, max(3, int(0.15 * ppm)))
            if ck is None: continue
            ck = ck.reshape(-1, 2)                                                                     # v2: ALLE Kandidaten als Strahlen (keine Wahl nach Naehe zur Projektion)
            for c in ck:
                o, d = strahl(c[0] + x0, c[1] + y0, kk, W, H, R, f, C); strahlen[n].append(dict(foto=nr, o=o.tolist(), d=d.tolist(), ppm=round(ppm, 1), px=[float(c[0] + x0), float(c[1] + y0)]))
            b_ = cv2.resize(im[y0:y0 + 2 * hw, x0:x0 + 2 * hw].copy(), (160, 160)); s_ = 160 / (2 * hw)
            cv2.drawMarker(b_, (80, 80), (255, 128, 0), cv2.MARKER_CROSS, 14, 1); cv2.putText(b_, nr, (3, 14), 0, 0.45, (0, 255, 255), 1)
            bilder.setdefault(n, []).append((nr, b_, s_, x0, y0))
    erg = []
    for n, X in P:
        S = strahlen[n]; r = dict(name=n, soll=X.round(3).tolist(), n_fotos=len(S))
        fotos_ = sorted({s_["foto"] for s_ in S}); r["n_fotos"] = len(fotos_)
        if len(fotos_) >= a.tri_min:
            O = np.array([s_["o"] for s_ in S]); D = np.array([s_["d"] for s_ in S]); F = np.array([s_["foto"] for s_ in S])
            b = triangulieren_mehrfach(O, D, F, X, a.fenster_m * 1.5, a.tri_tol)
            if b is not None and b[1] >= a.tri_min:
                Y, k_, ix = b; dd = _abst(O[ix], D[ix], Y); dv = float(np.linalg.norm(Y - X))
                r.update(gemessen=Y.round(3).tolist(), abweichung_m=round(dv, 3), abweichung_xyz=(Y - X).round(3).tolist(), n_konsens=int(k_),
                         rms_m=round(float(np.sqrt((dd ** 2).mean())), 3), fotos=[S[i]["foto"] for i in ix], ampel=ampel(dv), px={S[i]["foto"]: S[i]["px"] for i in ix})
        r.setdefault("ampel", "grau")
        if bilder.get(n):                                                                              # Sichtpruefung: blau = Projektion des Sollpunkts, gruen = Konsens-Ecke dieses Fotos; rote Rahmen = nicht im Konsens
            B = []
            for nr_, b_, s_, x0_, y0_ in bilder[n]:
                b_ = b_.copy(); q = (r.get("px") or {}).get(nr_)
                if q: cv2.circle(b_, (int((q[0] - x0_) * s_), int((q[1] - y0_) * s_)), 6, (0, 255, 0), 2)
                B.append((0 if q else 1, cv2.rectangle(b_, (0, 0), (159, 159), (0, 200, 0) if q else (0, 0, 255), 2)))
            B = [b_ for _, b_ in sorted(B, key=lambda t_: t_[0])][:24]
            B += [np.zeros_like(B[0])] * (-len(B) % 8); cv2.imwrite(os.path.join(aus, f"{n}.jpg"), np.vstack([np.hstack(B[i:i + 8]) for i in range(0, len(B), 8)]))
        erg.append(r); print(f"  {n:22s} {r['ampel']:5s} " + (f"Abw {r['abweichung_m']:.2f} m {r['abweichung_xyz']} aus {r['n_konsens']}/{len(S)} Fotos, RMS {r['rms_m']:.2f}" if "gemessen" in r else f"nicht messbar ({len(S)} Strahlen)"), flush=True)
    z = {k: sum(1 for r in erg if r["ampel"] == k) for k in ("gruen", "gelb", "rot", "grau")}
    print(f"AMPEL: {z}"); json.dump(dict(punkte=erg, ampel=z, parameter=vars(a)), open(os.path.join(aus, "punkte_messen.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()

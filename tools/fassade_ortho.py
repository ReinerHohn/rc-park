#!/usr/bin/env python3
"""fassade_ortho.py - Fassaden-Orthobilder (Meterraster) aus ALLEN kalibrierten Fotos, vollautomatisch (Qualitaetsstufe 3, 2026-11-04).

Je Fassade (koplanare LoD2-WallSurface-Stuecke, gleiche Normale/Ebene) ein (u, z)-Raster mit `--zelle` m: jede Zelle = Punkt auf der Wandebene,
in jedes Foto mit K-Datei (buendel_tor ok) projiziert (Lochkamera + k1 wie COLMAP SIMPLE_RADIAL), sichtbar nur wenn der erste Strahltreffer
gegen das aktuelle Modell (STL der Stufe) innerhalb `--tol` vor/hinter der Zelle liegt (Embree, CPU - die GPU gehoert dem laufenden Optimierer).
Guete je Foto und Zelle = cos(Blickwinkel) / (Meter je Pixel); Zellen mit Bodenaufloesung > `--max-mpp` oder Blickwinkel > 70 Grad fallen weg.
Fusion: gewichteter Median je Kanal ueber die Fotos (Verdecker wie Baeume/Menschen sind nicht im Modell -> der Median ueberstimmt sie, wenn
genug Fotos die Zelle sehen); dazu Anzahl Fotos je Zelle (Abdeckung) als eigenes Bild.

Ausgabe in --aus: ortho_<id>.png (fusioniert), abdeckung_<id>.png, ortho_<id>_einzeln/<foto>.png (nur mit --einzeln), fassaden.json
(je Fassade: Wandlinie a,b (Modell-xy), Normale nach aussen, u/z-Bereich, Zelle, Fotos mit Zellenzahl/Guete).

  /media/oem/scan/venv-seg/bin/python -I tools/fassade_ortho.py modelle/kaufhaus_null4/objekt.json --stl <modell.stl> --aus DIR [--zelle 0.05]
"""
import os, sys, json, glob, math, argparse, time
import numpy as np, cv2, trimesh
from concurrent.futures import ThreadPoolExecutor
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import fehlteile_finden as FF


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


def projizieren(X, R, t, f, cx, cy, k1):
    Xc = X @ R.T + t; z = Xc[:, 2]; xn = Xc[:, 0] / z; yn = Xc[:, 1] / z; r2 = xn * xn + yn * yn; s = 1 + k1 * r2
    return np.c_[f * xn * s + cx, f * yn * s + cy], z


def bilinear(im, x, y):
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]; I = im.astype(np.float32)
    c = I[y0, x0] * (1 - fx) * (1 - fy) + I[y0, x0 + 1] * fx * (1 - fy) + I[y0 + 1, x0] * (1 - fx) * fy + I[y0 + 1, x0 + 1] * fx * fy
    return np.clip(c + 0.5, 0, 255).astype(np.uint8)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--zelle", type=float, default=0.05); ap.add_argument("--tol", type=float, default=0.10); ap.add_argument("--relief-vorn", type=float, default=3.0); ap.add_argument("--relief-hinten", type=float, default=6.0); ap.add_argument("--max-mpp", type=float, default=0.06)
    ap.add_argument("--max-winkel", type=float, default=70.0); ap.add_argument("--fotos", help="Komma-Liste (Standard: alle mit K-Datei und buendel_tor ok)")
    ap.add_argument("--waende-stl", action="store_true", help="Fassaden aus senkrechten Modelldreiecken, die keine LoD2-Ebene sind (Erker/Vorbauten)"); ap.add_argument("--min-flaeche", type=float, default=1.0); ap.add_argument("--einzeln", action="store_true"); ap.add_argument("--ohne-nachbarn", action="store_true"); ap.add_argument("--beste", type=int, default=5, help="je Zelle nur die k Fotos mit der besten Guete (cos/mpp) mitteln: 61 Fotos im Median verschmierten Kanten (Kamerareste 1-4 px)"); ap.add_argument("--arbeiter", type=int, default=6, help="parallele Fotos (RAM: Vollbilder bis 0,3 GB je Foto)"); ap.add_argument("--rand", type=float, default=0.5, help="Rand um die Wand (m) fuer Vorsprung/Traufe")
    ap.add_argument("--nur", help="Komma-Liste Flaechen-IDs (f02,e05 ...): nur diese rastern (Tests/Vergleiche; IDs bleiben die des vollen Laufs)")
    ap.add_argument("--px-ziel", type=int, default=256, help="Flaechen unter --klein-m2: Zelle = min(--zelle, kleinere Ausdehnung / px-ziel), damit kleine Flaechen (Vorbauseiten, Erkerstreifen) genug Pixel fuer den Erkenner haben (S4: die feste 5-cm-Zelle gab einem 2-m-Streifen nur 40 px; Aufloesung statt Handschwelle ist die physikalische Grenze)")
    ap.add_argument("--klein-m2", type=float, default=20.0, help="Flaechen kleiner als dies bekommen die feinere Zelle (Begruendung: grosse Fassaden brauchen 5 cm, Speicher/Rechenzeit wachsen mit 1/Zelle^2)")
    ap.add_argument("--zelle-min", type=float, default=0.005, help="feinste Zelle (m): Untergrenze, damit eine sehr schmale Flaeche keine Riesenraster erzeugt; 5 mm ~ Bodenaufloesung der besten Fotos (ANNAHME; 1 cm schloss in T1 0,5-m-Erkerfacetten mit < 96 px aus, die Spec verlangt 256 px je 2 m = 7,8 mm)")
    a = ap.parse_args(argv); t0 = time.time()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); os.makedirs(a.aus, exist_ok=True)
    waende, mitte = lod2_waende(obj)
    if a.waende_stl:                                                                                # 2026-11-05: Vorbauten (Erker) haben keine LoD2-Wand -> Fassaden aus den senkrechten Modelldreiecken;
        ms_ = trimesh.load(a.stl); ms_.apply_scale(obj.get("stl_massstab", 87) / 1000.0)            # nur Flaechen, die KEINE LoD2-Fassade sind (Ebenenabstand > 0,3 m), mit eigener Kennung e00..
        lod = fassaden_gruppieren(waende, mitte); senk = np.abs(ms_.face_normals[:, 2]) < 0.2
        fs = []                                                                                    # zusammenhaengende koplanare Flaechenstuecke (trimesh facets) statt "gleiche Ebene irgendwo im Modell"
        for fc_ in list(ms_.facets) + [[i_] for i_ in np.where(senk)[0] if not any(i_ in f__ for f__ in ms_.facets)]:
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
    if a.nur: fas = [F_ for F_ in fas if F_["_id"] in set(a.nur.split(","))]
    fotos = a.fotos.split(",") if a.fotos else sorted(os.path.basename(k)[2:-5] for k in glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))
                                                       if json.load(open(k)).get("kamera", {}).get("buendel_tor", {}).get("ok"))
    m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
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
    RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector
    ray = RI(m); nb, n_nb = nachbarn_netz(obj) if not a.ohne_nachbarn else (None, 0)
    ray_alle = RI(trimesh.util.concatenate([m, nb])) if nb is not None else ray                     # Sicht: Modell + Nachbarn; Relief (Ortho-Flaeche): nur Modell
    for F in fas:                                                                                   # echtes Orthobild: je Zelle die VORDERSTE Modellflaeche entlang -Normale (Erker, Galerie, Arkadenrueckwand)
        X = F["_X"]; n3 = np.array(F["n"] + [0.0]); vorn = a.relief_vorn
        loc, ri, _ = ray.intersects_location(X + n3 * vorn, np.repeat(-n3[None], len(X), 0), multiple_hits=False)
        rel = np.full(len(X), np.nan); rel[ri] = vorn - np.linalg.norm(loc - (X[ri] + n3 * vorn), axis=1)   # Relief s (+ = vor der Wandebene)
        rel[rel < -a.relief_hinten] = np.nan; F["_S"] = X + n3 * np.nan_to_num(rel, nan=0.0)[:, None]; F["_rel"] = rel

    def ein_foto(nr):
        K = json.load(open(FF.k_datei(a.objekt, obj, ROOT, nr))); kk = K["kamera"]; pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))
        if not pf: return nr, None
        im = cv2.imread(pf[0]); H, W = im.shape[:2]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H)
        tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)); k1 = float(kk.get("k1") or 0.0)
        Cw = -R.T @ np.asarray(t, float) - tr                                                        # Kamerazentrum im Modellrahmen
        erg = {}
        for i, F in enumerate(fas):
            X = F["_S"]; n = np.array(F["n"] + [0.0]); v = Cw - X; dist = np.linalg.norm(v, axis=1); cosw = (v @ n) / dist
            px, z = projizieren(X + tr, R, np.asarray(t, float), f, cx, cy, k1)
            ok = (cosw > math.cos(math.radians(a.max_winkel))) & (z > 1) & (px[:, 0] >= 0) & (px[:, 0] < W - 1) & (px[:, 1] >= 0) & (px[:, 1] < H - 1)
            mpp = dist / (f * np.maximum(cosw, 1e-3)); ok &= mpp < a.max_mpp
            if ok.sum() < 200: continue
            idx = np.where(ok)[0]; dirs = -v[idx] / dist[idx, None]
            loc, ri, _ = ray_alle.intersects_location(np.repeat(Cw[None], len(idx), 0), dirs, multiple_hits=False)
            erster = np.full(len(idx), np.inf); erster[ri] = np.linalg.norm(loc - Cw, axis=1)
            sicht = np.abs(erster - dist[idx]) < a.tol + 0.002 * dist[idx]                           # erster Kamerastrahl-Treffer = die vorderste Flaeche der Zelle (sonst verdeckt)
            sicht &= np.isfinite(F["_rel"][idx])                                                      # ohne Modellflaeche (Himmel/Nachbar) keine Farbe
            idx = idx[sicht]
            if len(idx) < 200: continue
            col = bilinear(im, px[idx, 0], px[idx, 1])
            erg[i] = (idx.astype(np.int32), col, (cosw[idx] / mpp[idx]).astype(np.float32))
        return nr, erg

    with ThreadPoolExecutor(min(len(fotos), a.arbeiter)) as ex: alle = list(ex.map(ein_foto, fotos))
    bericht = []
    for i, F in enumerate(fas):
        r = F["raster"]; N = r["nu"] * r["nz"]; beitr = [(nr, e[i]) for nr, e in alle if e and i in e]
        F["fotos"] = {nr: dict(zellen=int(len(x[0])), guete_median=round(float(np.median(x[2])), 1)) for nr, x in beitr}
        img = np.zeros((N, 3), np.uint8); cnt = np.zeros(N, np.int32)
        if beitr:
            I = np.concatenate([x[0] for _, x in beitr]); Cc = np.concatenate([x[1] for _, x in beitr]).astype(np.float32); G = np.concatenate([x[2] for _, x in beitr])
            o_ = np.lexsort((-G, I)); I, Cc, G = I[o_], Cc[o_], G[o_]; st = np.r_[0, np.where(np.diff(I))[0] + 1, len(I)]
            cnt[I[st[:-1]]] = np.diff(st)
            rang = np.arange(len(I)) - np.repeat(st[:-1], np.diff(st)); w_ = rang < a.beste; I, Cc, G = I[w_], Cc[w_], G[w_]   # je Zelle die besten k
            # gewichteter Median je Kanal und Zelle, vektorisiert: Proben je Zelle nach Wert sortieren, kumulierte Gewichte, erster Wert >= halbes Gewicht
            for k_ in range(3):
                key = I.astype(np.float64) * 512 + Cc[:, k_]; o2 = np.argsort(key, kind="stable"); Ik, Vk, Gk = I[o2], Cc[o2, k_], G[o2]
                cs = np.cumsum(Gk); start = np.r_[0, np.where(np.diff(Ik))[0] + 1]; tot = np.add.reduceat(Gk, start); base = np.r_[0, cs[start[1:] - 1]] if len(start) > 1 else np.array([0.0])
                half = base + tot / 2; grp = np.repeat(np.arange(len(start)), np.diff(np.r_[start, len(Ik)])); ueber = cs >= half[grp]
                erst = np.full(len(start), -1); pos_ = np.where(ueber)[0]; g_ = grp[pos_]; first = np.r_[True, g_[1:] != g_[:-1]]; erst[g_[first]] = pos_[first]
                img[Ik[start], k_] = np.clip(Vk[erst], 0, 255).astype(np.uint8)
        tag = F["_id"]; cv2.imwrite(os.path.join(a.aus, f"ortho_{tag}.png"), img.reshape(r["nz"], r["nu"], 3))
        cv2.imwrite(os.path.join(a.aus, f"abdeckung_{tag}.png"), np.clip(cnt * 20, 0, 255).astype(np.uint8).reshape(r["nz"], r["nu"]))
        if a.einzeln:
            ed = os.path.join(a.aus, f"ortho_{tag}_einzeln"); os.makedirs(ed, exist_ok=True)
            for nr, x in beitr:
                b_ = np.zeros((N, 3), np.uint8); b_[x[0]] = x[1]; cv2.imwrite(os.path.join(ed, f"{nr}.png"), b_.reshape(r["nz"], r["nu"], 3))
        F["id"] = tag; F["abdeckung_anteil"] = round(float((cnt > 0).mean()), 3); F["fotos_median_je_zelle"] = float(np.median(cnt[cnt > 0])) if (cnt > 0).any() else 0
        rl = F["_rel"].reshape(r["nz"], r["nu"]); cv2.imwrite(os.path.join(a.aus, f"relief_{tag}.png"), np.where(np.isfinite(rl), np.clip((rl + 10) * 1000, 1, 65535), 0).astype(np.uint16))   # mm + 10 m, 0 = kein Modell
        F["relief_png"] = f"relief_{tag}.png (uint16: (s + 10 m) in mm, 0 = keine Modellflaeche)"
        del F["_X"], F["_S"], F["_rel"]; F.pop("_id", None); bericht.append(f"  {tag}: {F['flaeche_m2']:6.1f} m2, n=({F['n'][0]:+.2f},{F['n'][1]:+.2f}), {len(beitr):2d} Fotos, Abdeckung {F['abdeckung_anteil']:.0%}, Median {F['fotos_median_je_zelle']:.0f} Fotos/Zelle")
    json.dump(dict(objekt=a.objekt, stl=os.path.abspath(a.stl), zelle_m=a.zelle, tol_m=a.tol, max_mpp=a.max_mpp, fotos=fotos, fassaden=fas,
                   beste_k=a.beste, nachbarn_lod2=n_nb, quelle="fassade_ortho.py: LoD2-Waende + K-Dateien (buendel_tor) + Sichtbarkeit gegen Stufenmodell + LoD2-Nachbarn", sekunden=round(time.time() - t0, 1)),
              open(os.path.join(a.aus, "fassaden.json"), "w"), indent=1)
    print(f"{len(fas)} Fassaden, {len(fotos)} Fotos, {time.time() - t0:.0f} s"); print("\n".join(bericht))


if __name__ == "__main__":
    main()

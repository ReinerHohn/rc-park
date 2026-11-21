#!/usr/bin/env python3
"""hintergrundhaus.py - HINTERGRUNDHAUS (Reifegrad 1) in Minuten: LoD2-Koerper + LoD2-Dach (DOM1 als Gegenprobe), Fenster aus vorhandenen Fotos, sonst Fensterraster als ANNAHME,
duenne Wand + Innenrippen, STL 1:87, Belegdatei, Sichtblatt Modell neben Foto. (Wunderland-Werkzeugkette Prioritaet 2, modelle/WERKZEUGKETTE_WUNDERLAND.md; 17.11.2026)

NIE ALS PASSEND MELDEN: ein Hintergrundhaus hat KEINE Kantenstufe / keinen Foto-F1 (KERNMETHODE) - es ist ein ehrliches Grobhaus fuer die zweite Reihe einer Anlage.
objekt.json traegt "reifegrad": 1, "kennzeichnung": "HINTERGRUND ...". Fuer Vordergrund: tools/gesamtkette.py.

Ablauf `alles` (je Haus, Zeit wird gemessen):
  1. anlegen   modelle/hg_<name>/objekt.json (Rahmen aus dem LoD2-Grundriss: Mitte, +x = laengste Grundrisskante, z ueber DGM1-Median), masstabelle.json, Belegdatei.
               Kameras OHNE neue SfM: K-Dateien eines vorhandenen Objekts (--kameras-von, z. B. kaufhaus_gk) werden in den Rahmen des Hauses UMGERECHNET (UTM-Rahmen
               beider Objekte, reine Drehung um z + Verschiebung) - nur Kameras, deren Bild das Haus trifft. Ablage /media/oem/scan/rc-park_daten/hg_<name>/messprotokoll (Symlink).
  2. bauen     (auch der 'generator' in objekt.json): Rumpf+Dach = baukasten_gen.rumpf_lod2 (amtliches LoD2, je Dachflaeche Prisma).
               Dach-Gegenprobe DOM1: je Dachpixel Modell-Oberseite gegen Laser, je freie Wand die Traufe (0,75 m innen) gegen Laser. Widerspruch > --dach-tol: Hinweis
               (mit --dach laser: Dach als DOM1-Hoehenfeld ueber tools/laserdach.py). Mittel wird nichts (Quellenwiderspruch nicht mitteln).
               Fenster: audit/fenster_auto.json (Foto) -> bauteile.fenster_aus_json; Waende OHNE Fotoabdeckung -> Raster (ANNAHME, --ohne-raster schaltet ab);
               Waende an einem Nachbarhaus (Brandwand, LoD2-Nachbar 0,5 m vor der Wand) bleiben zu. Dann bauteile.aushoehlen (Wand --wand-mm, Boden offen = Druck ohne Deckel unten).
  3. fotos     fassade_ortho.py (Stufenmodell, Nachbarn als Verdecker) -> fassade_parsing.py (OWLv2, GPU, Batch begrenzt) -> fenster_aus_parsing.py -> audit/fenster_auto.json.
  4. druck     tools/druck_rippen.py (Standard 60 mm / 0,9 mm) -> <stl>_druck.stl, Bild audit/rippen.png.
  5. pruefen   wasserdicht/Koerper, tools/hoehe_gegen_dom1.py, Sichtblatt tools/modell_neben_foto.py (bestes Foto je Hausseite) -> audit/neben_*.jpg (ANSEHEN).

  /media/oem/scan/venv-seg/bin/python -I tools/hintergrundhaus.py kandidaten --um modelle/kaufhaus_gk/objekt.json [--radius 60]
  JOB_GPU_MB=1500 tools/job_start.sh hg1 LOG /media/oem/scan/venv-seg/bin/python -I tools/hintergrundhaus.py alles <name> --lod2-id DEBW_... --kameras-von modelle/kaufhaus_gk/objekt.json
  /media/oem/scan/venv-seg/bin/python -I tools/hintergrundhaus.py bauen <name> [--ohne-raster] [--ohne-fotofenster]
Ausgaben: /media/oem/scan/rc-park_stl/hg_<name>/hg_<name>_1-87.stl (+ _druck.stl), modelle/hg_<name>/{objekt.json, elemente.json, hintergrund_beleg.json, audit/}.
"""
import os, sys, json, glob, time, math, argparse, subprocess
import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
PY = "/media/oem/scan/venv-seg/bin/python"
STL_BASIS = "/media/oem/scan/rc-park_stl"; DATEN = "/media/oem/scan/rc-park_daten"
SCALE = 87.0
KENNUNG = "HINTERGRUND, Reifegrad 1: LoD2-Koerper + Fotofenster/Raster-ANNAHME, ohne Kantenstufe/Foto-F1 - nie als passend melden"


def _od(name): return os.path.join(ROOT, "modelle", name if name.startswith("hg_") else "hg_" + name)
def _ccw(xy):
    xy = np.asarray(xy, float); a = 0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1]); return xy if a > 0 else xy[::-1]
def _fl(xy):
    xy = np.asarray(xy, float); return abs(0.5 * np.sum(xy[:, 0] * np.roll(xy[:, 1], -1) - np.roll(xy[:, 0], -1) * xy[:, 1]))
def _kompass(v):
    w = (math.degrees(math.atan2(v[0], v[1])) + 360) % 360; return ["Nord", "Nordost", "Ost", "Suedost", "Sued", "Suedwest", "West", "Nordwest"][int((w + 22.5) // 45) % 8]


def _rahmen_von(obj):
    r = obj["rahmen"]; return np.array(r["mitte_utm"], float), np.array(r["xhat_utm"], float), np.array(r["yhat_utm"], float), float(r["gelaende"])


def lod2_haus(gml, lod2_id, um_utm, radius=150.0):
    import lod2_gebaeude as LG
    for meta, polys in LG.extract(gml, center=tuple(um_utm), radius=radius):
        if meta.get("id") == lod2_id: return meta, polys
    sys.exit(f"LoD2 {lod2_id} nicht im Umkreis {radius} m von {um_utm} in {gml}")


# ------------------------------------------------------------------ kandidaten
def kandidaten(a):
    """Nachbarhaeuser um ein Objekt mit Kameras: LoD2-ID, Lage, Traufe/First, Flaeche, Zahl der Kameras, deren Bild die Hausmitte trifft (ohne Verdeckung - nur Vorauswahl)."""
    import cv2, lod2_gebaeude as LG
    obj = json.load(open(a.um)); m0, xh, yh, _ = _rahmen_von(obj); od = os.path.dirname(os.path.abspath(a.um))
    ks = [json.load(open(k)).get("kamera") for k in glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))]; ks = [k for k in ks if isinstance(k, dict) and "rvec" in k]
    for meta, polys in sorted(LG.extract(obj["lod2"]["gml"], center=tuple(m0), radius=a.radius), key=lambda mp: np.hypot(*(np.array(mp[0]["center_utm"]) - m0))):
        c = np.array(meta["center_utm"]); l = np.r_[(c - m0) @ xh, (c - m0) @ yh, meta.get("eave_m", 8) / 2]; n = 0
        for k in ks:
            R = cv2.Rodrigues(np.array(k["rvec"]))[0]; x = R @ l + np.array(k["t"])
            if x[2] <= 0 or x[2] > 80: continue
            W, H = (k.get("bild") or [2 * k["cx"], 2 * k["cy"]])[:2]; u = k["f_px"] * x[0] / x[2] + k["cx"]; v = k["f_px"] * x[1] / x[2] + k["cy"]; n += (0 < u < W and 0 < v < H)
        A = sum(_fl(P[:, :2]) for t, P in polys if t == "GroundSurface")
        print(f"{meta['id']}  x {l[0]:6.1f} y {l[1]:6.1f}  Traufe {meta.get('eave_m', 0):5.1f} First {meta.get('ridge_m', 0):5.1f}  {A:6.0f} m2  Kameras {n:3d}  {meta.get('name') or ''}")


# ------------------------------------------------------------------ anlegen
def kameras_uebertragen(quelle_obj_json, ziel_obj, ziel_mp, poly_xy, z_hoch):
    """K-Dateien des Quellobjekts in den Rahmen des Hauses umrechnen. Quelle s, Ziel t (beide Rahmen: UTM-Mitte, xhat/yhat, gelaende):
    p_s = A p_t + b  ->  x_cam = R p_s + t_s = (R A) p_t + (R b + t_s). Nur Kameras, die einen Hauspunkt (Grundrissecken auf 2 Hoehen) VOR sich und im Bild haben, < 150 m."""
    import cv2
    q = json.load(open(quelle_obj_json)); qd = os.path.dirname(os.path.abspath(quelle_obj_json))
    ms, xs, ys, gs = _rahmen_von(q); mt, xt, yt, gt = _rahmen_von(ziel_obj)
    A = np.eye(3); A[:2, :2] = [[xt @ xs, yt @ xs], [xt @ ys, yt @ ys]]; U_, _, Vt_ = np.linalg.svd(A); A = U_ @ Vt_          # Rahmenachsen sind auf 1e-4 orthonormal -> echte Drehung erzwingen
    b = np.r_[(mt - ms) @ xs, (mt - ms) @ ys, gt - gs]
    P = np.array([[x, y, z] for x, y in poly_xy for z in (1.0, max(2.0, z_hoch * 0.8))], float)
    os.makedirs(ziel_mp, exist_ok=True); n = 0
    for kp in sorted(glob.glob(os.path.join(qd, "messprotokoll", "K-*.json"))):
        K = json.load(open(kp)); k = K.get("kamera")
        if not (isinstance(k, dict) and "rvec" in k and "cx" in k): continue
        R = cv2.Rodrigues(np.array(k["rvec"], float))[0]; Rn = R @ A; tn = R @ b + np.array(k["t"], float)
        X = (Rn @ P.T).T + tn; vor = X[:, 2] > 0.5
        if not vor.any() or np.min(np.linalg.norm(X[vor], axis=1)) > 150: continue
        W, H = (k.get("bild") or [2 * k["cx"], 2 * k["cy"]])[:2]; u = k["f_px"] * X[vor, 0] / X[vor, 2] + k["cx"]; v = k["f_px"] * X[vor, 1] / X[vor, 2] + k["cy"]
        if not ((u > 0) & (u < W) & (v > 0) & (v < H)).any(): continue
        kn = dict(k); kn["rvec"] = cv2.Rodrigues(Rn)[0].ravel().tolist(); kn["t"] = tn.tolist()
        if "standort_xyz" in k: kn["standort_xyz"] = (A.T @ (np.array(k["standort_xyz"], float) - b)).round(3).tolist()
        if k.get("ankerzone_z"): kn["ankerzone_z"] = [float(z_) - b[2] for z_ in k["ankerzone_z"]]
        kn["quelle"] = f"hintergrundhaus.py: aus {os.path.relpath(kp, ROOT)} in den Hausrahmen umgerechnet (Drehung {math.degrees(math.atan2(A[1, 0], A[0, 0])):.2f} Grad, Versatz {b.round(2).tolist()} m); urspruenglich: " + str(k.get("quelle", ""))[:200]
        json.dump(dict(foto=K.get("foto", os.path.basename(kp)[2:-5]), kamera=kn), open(os.path.join(ziel_mp, os.path.basename(kp)), "w"), indent=0); n += 1
    return n


def anlegen(a):
    t0 = time.time(); od = _od(a.name); name = os.path.basename(od); os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    q = json.load(open(a.kameras_von)) if a.kameras_von else None
    gml = a.gml or (q["lod2"]["gml"] if q else sys.exit("--gml oder --kameras-von noetig"))
    um = np.array(q["rahmen"]["mitte_utm"], float) if q and a.um is None else np.array(a.um or [0, 0], float)
    meta, polys = lod2_haus(gml, a.lod2_id, um)
    boden = [P for t, P in polys if t == "GroundSurface"]; Bxy = np.vstack(boden)[:, :2]; m0 = Bxy.mean(0)
    best = (0, np.array([1.0, 0.0]))                                                                    # +x = laengste Grundrisskante (wie objekt_daten.py)
    for P in boden:
        for p_, q_ in zip(P[:, :2], np.roll(P[:, :2], -1, 0)):
            if np.linalg.norm(q_ - p_) > best[0]: best = (float(np.linalg.norm(q_ - p_)), (q_ - p_) / np.linalg.norm(q_ - p_))
    xh = best[1] if abs(best[1][0]) >= abs(best[1][1]) else best[1] * np.sign(-best[1][1])                  # eher O-W: nach Osten, eher N-S: nach Sueden
    if abs(best[1][0]) >= abs(best[1][1]) and xh[0] < 0: xh = -xh
    yh = np.array([-xh[1], xh[0]])
    from dom1_kachel import dom1_hoehe
    from matplotlib.path import Path
    gx, gy = np.meshgrid(np.arange(Bxy[:, 0].min(), Bxy[:, 0].max(), 1.0), np.arange(Bxy[:, 1].min(), Bxy[:, 1].max(), 1.0))
    inn = np.zeros(gx.shape, bool)
    for P in boden: inn |= Path(P[:, :2]).contains_points(np.c_[gx.ravel(), gy.ravel()]).reshape(gx.shape)
    zg = dom1_hoehe(gx[inn], gy[inn], art="dgm1") if inn.any() else np.array([np.nan]); g0 = float(np.nanmedian(zg)) if np.isfinite(zg).any() else float(meta["ground_z"])
    gq = f"DGM1-Median im Grundriss ({int(np.isfinite(zg).sum())} Pixel)" if np.isfinite(zg).any() else "LoD2 GroundSurface (keine DGM1-Kachel)"
    stl = os.path.join(STL_BASIS, name, f"{name}_1-87.stl")
    obj = dict(name=a.titel or f"Hintergrundhaus {meta['id']}", reifegrad=1, kennzeichnung=KENNUNG, ort=a.ort or "",
               generator=f"{PY} -I tools/hintergrundhaus.py bauen {name}", stl=stl, stl_massstab=87, stl_einheit_mm=True, zentrierung="achse",
               masstabelle=f"modelle/{name}/masstabelle.json", elemente=f"modelle/{name}/elemente.json", audit=f"modelle/{name}/audit",
               ueberwacht=["tools/hintergrundhaus.py", f"modelle/{name}/masstabelle.json", f"modelle/{name}/elemente.json"],
               fotos_dir=(q or {}).get("fotos_dir", f"daten/{name}/fotos"),
               seiten_konvention={"+x": _kompass(xh), "-x": _kompass(-xh), "+y": _kompass(yh), "-y": _kompass(-yh), "quelle": "hintergrundhaus.py: Kompass der Rahmenachsen (LoD2-Grundriss)"},
               lod2=dict(gml=gml, id=meta["id"], traufe_m=meta.get("eave_m"), first_m=meta.get("ridge_m"), dachtypen=meta.get("rooftypes")),
               rahmen=dict(mitte_utm=m0.round(3).tolist(), xhat_utm=xh.round(5).tolist(), yhat_utm=yh.round(5).tolist(), gelaende=round(g0, 2),
                           hinweis=f"hintergrundhaus.py: Ursprung Grundriss-Mitte (LoD2), +x laengste Grundrisskante, z ueber {gq}"),
               quellen=dict(lod2=f"LGL BW LoD2 {meta['id']}", dom1_dgm1="LGL BW DOM1/DGM1 (Gegenprobe Hoehe/Traufe)",
                            fotos=f"Kameras aus {os.path.relpath(a.kameras_von, ROOT)} umgerechnet (keine eigene SfM)" if a.kameras_von else "keine"),
               hintergrund=dict(kameras_von=os.path.relpath(a.kameras_von, ROOT) if a.kameras_von else None, wand_mm=a.wand_mm, raster=not a.ohne_raster))
    op = os.path.join(od, "objekt.json")
    if os.path.exists(op) and not a.neu: obj = {**obj, **{k: v for k, v in json.load(open(op)).items() if k in ("neben_fotos", "beobachtungen")}}
    json.dump(obj, open(op, "w"), indent=1, ensure_ascii=False)
    tab = {"_doku": "Masstabelle Hintergrundhaus (Reifegrad 1): nur Druckfaehigkeit + Hoehe gegen LoD2; Form NICHT abgenommen (keine Kantenstufe)", "konstanten": {},
           "messungen": {"hoehe": {"typ": "hoehe_max"}, "wasserdicht": {"typ": "wasserdicht"}, "koerper": {"typ": "koerper_anzahl"}},
           "pruefungen": [{"name": "Gesamthoehe (m)", "wert": "hoehe", "soll": [round(meta["ridge_m"] * 0.97, 2), round(meta["ridge_m"] * 1.03 + 0.1, 2)], "quelle": f"LoD2 {meta['id']} First ueber Boden", "quelltyp": "lod2", "merkmal": "hoehe"},
                          {"name": "Wasserdicht (1=ja)", "wert": "wasserdicht", "soll": [1, 1], "quelle": "Druckfaehigkeit", "quelltyp": "modell", "merkmal": "druck"},
                          {"name": "Anzahl getrennte Koerper", "wert": "koerper", "soll": [1, 1], "quelle": "Schwebende Teile", "quelltyp": "modell", "merkmal": "druck"}],
           "beobachtungen_offen": [{"datum": time.strftime("%Y-%m-%d"), "wer": "hintergrundhaus.py", "text": "Hintergrundhaus Reifegrad 1 - Fassadendetails (Gesimse, Laeden, Dachaufbauten) fehlen bewusst", "naechster_schritt": "fuer Vordergrund: tools/gesamtkette.py"}],
           "historie": [{"datum": time.strftime("%Y-%m-%d"), "text": "angelegt von tools/hintergrundhaus.py"}]}
    mp = os.path.join(od, "masstabelle.json")
    if not os.path.exists(mp) or a.neu: json.dump(tab, open(mp, "w"), indent=1, ensure_ascii=False)
    n_k = 0
    if a.kameras_von:
        ziel = os.path.join(DATEN, name, "messprotokoll"); lk = os.path.join(od, "messprotokoll")
        for f_ in glob.glob(os.path.join(ziel, "K-*.json")): os.remove(f_)                              # eigene Zwischendateien (aus frueherem Lauf)
        n_k = kameras_uebertragen(a.kameras_von, obj, ziel, [((p_[:2] - m0) @ xh, (p_[:2] - m0) @ yh) for P in boden for p_ in P], float(meta.get("ridge_m") or 10))
        if not os.path.lexists(lk): os.symlink(ziel, lk)
    print(f"angelegt {op}: LoD2 {meta['id']}, Traufe {meta.get('eave_m', 0):.2f} / First {meta.get('ridge_m', 0):.2f} m, Gelaende {g0:.2f} ({gq}), {n_k} Kameras uebertragen ({time.time() - t0:.1f} s)")
    return obj


# ------------------------------------------------------------------ bauen
def _nachbarn_dreiecke(obj, radius=60.0):
    """Alle anderen LoD2-Gebaeude im Umkreis als Dreiecksnetz im Hausrahmen (fuer Brandwand-Test)."""
    import lod2_gebaeude as LG, trimesh
    m0, xh, yh, g0 = _rahmen_von(obj); V, F = [], []
    for meta, polys in LG.extract(obj["lod2"]["gml"], center=tuple(m0), radius=radius):
        if meta.get("id") == obj["lod2"]["id"]: continue
        for t, P in polys:
            P = np.asarray(P, float); L = np.c_[(P[:, :2] - m0) @ xh, (P[:, :2] - m0) @ yh, P[:, 2] - g0]; b0 = len(V); V += L.tolist()
            F += [(b0 + i, b0 + j, b0 + k) for i, j, k in LG.planar_triangulate(L)]
    return trimesh.Trimesh(np.array(V), np.array(F), process=False) if F else None


def _waende(F_lod2):
    """LoD2-WallSurfaces -> Wandflaechen (Polygon in u,z) mit Ecke a, Richtung t, Normale (nach aussen am Grundriss bestimmt durch den Aufrufer)."""
    out = []
    for t, P in F_lod2:
        if t != "WallSurface" or len(P) < 3: continue
        xy = P[:, :2]; i, j = np.unravel_index(np.argmax(np.linalg.norm(xy[:, None] - xy[None], axis=2)), (len(xy), len(xy)))
        if np.linalg.norm(xy[j] - xy[i]) < 1.5: continue
        tv = (xy[j] - xy[i]) / np.linalg.norm(xy[j] - xy[i]); u = (xy - xy[i]) @ tv
        if np.max(np.abs((xy - xy[i]) @ np.array([-tv[1], tv[0]]))) > 0.3: continue                       # nicht eben/senkrecht genug
        out.append(dict(a=xy[i], t=tv, uz=np.c_[u, P[:, 2]], laenge=float(u.max() - u.min())))
    return out


def dach_gegenprobe(obj, koerper_m, waende):
    """DOM1 gegen Modell-Oberseite: alle 1-m-Pixel im Grundriss (0,5 m innen) + je freie Wand die Traufe 0,75 m innen. Rueckgabe dict (Zahlen fuer den Beleg)."""
    import trimesh
    from dom1_kachel import dom1_hoehe
    m0, xh, yh, g0 = _rahmen_von(obj)
    mm = koerper_m.to_mesh(); T = trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=False)
    def oben(xy):
        o = np.c_[xy, np.full(len(xy), 200.0)]; loc, ri, _ = T.ray.intersects_location(o, np.tile([0, 0, -1.0], (len(xy), 1)), multiple_hits=False)
        z = np.full(len(xy), np.nan); z[ri] = loc[:, 2]; return z
    def laser(xy): E = m0[0] + xy[:, 0] * xh[0] + xy[:, 1] * yh[0]; N = m0[1] + xy[:, 0] * xh[1] + xy[:, 1] * yh[1]; return dom1_hoehe(E, N) - g0
    b = T.bounds; gx, gy = np.meshgrid(np.arange(b[0, 0] + 0.5, b[1, 0], 1.0), np.arange(b[0, 1] + 0.5, b[1, 1], 1.0)); xy = np.c_[gx.ravel(), gy.ravel()]
    zm = oben(xy); ok = np.isfinite(zm)
    if ok.sum():                                                                                        # 0,5 m innen: alle 4 Nachbarpunkte im Abstand 0,5 m treffen das Modell
        for d in ((0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5)): ok &= np.isfinite(oben(xy + np.array(d)))
    zl = laser(xy[ok]); dz = zl - zm[ok]; g = np.isfinite(dz)
    erg = dict(n_pixel=int(g.sum()))
    if g.sum():
        erg.update(median_laser_minus_modell_m=round(float(np.median(dz[g])), 2), p10_m=round(float(np.percentile(dz[g], 10)), 2), p90_m=round(float(np.percentile(dz[g], 90)), 2),
                   first_modell_m=round(float(np.nanmax(zm)), 2), first_laser_m=round(float(np.nanpercentile(zl[g], 98)), 2))
    tr = []
    for W in waende:
        if not W.get("frei") or W["laenge"] < 3: continue
        us = np.linspace(W["uz"][:, 0].min() + 0.7, W["uz"][:, 0].max() - 0.7, max(2, int(W["laenge"] / 1.0)))
        p = W["a"] + us[:, None] * W["t"] - 0.75 * W["n"]; zmw = oben(p); zlw = laser(p); d_ = zlw - zmw; d_ = d_[np.isfinite(d_)]
        if len(d_) >= 2: tr.append(dict(wand=W["id"], seite=W["seite"], laenge_m=round(W["laenge"], 1), traufe_modell_m=round(float(np.nanmedian(zmw)), 2), traufe_laser_m=round(float(np.nanmedian(zlw)), 2), median_laser_minus_modell_m=round(float(np.median(d_)), 2)))
    erg["traufen"] = tr; return erg


def raster_fenster(W, ANN):
    """Fensterraster ANNAHME auf einer Wand ohne Foto: Achsabstand, Fenstergroesse, Geschosshoehe aus ANN; nur Fenster, die ganz in der Wandflaeche (Polygon u,z, um rand geschrumpft) liegen."""
    from manifold3d import CrossSection as C
    poly = C([_ccw(W["uz"]).tolist()]).offset(-ANN["rand_m"], __import__("manifold3d").JoinType.Miter); fen = []
    u0, u1 = W["uz"][:, 0].min(), W["uz"][:, 0].max(); n_ax = int((u1 - u0 - 2 * ANN["rand_m"] + ANN["achse_m"] - ANN["breite_m"]) // ANN["achse_m"])
    if n_ax < 1: return fen
    um = 0.5 * (u0 + u1); us = [um + (i - (n_ax - 1) / 2) * ANN["achse_m"] for i in range(n_ax)]
    zz = ANN["bruestung_eg_m"]
    while zz + ANN["hoehe_m"] < W["uz"][:, 1].max():
        for u in us:
            r = C([[[u - ANN["breite_m"] / 2, zz], [u + ANN["breite_m"] / 2, zz], [u + ANN["breite_m"] / 2, zz + ANN["hoehe_m"]], [u - ANN["breite_m"] / 2, zz + ANN["hoehe_m"]]]])
            if abs((r ^ poly).area() - r.area()) < 1e-4: fen.append((u - ANN["breite_m"] / 2, u + ANN["breite_m"] / 2, zz, zz + ANN["hoehe_m"]))
        zz += ANN["geschoss_m"]
    return fen


def bauen(a):
    t0 = time.time(); od = _od(a.name); name = os.path.basename(od); obj = json.load(open(os.path.join(od, "objekt.json"))); HG = obj.get("hintergrund", {})
    os.environ["OBJ_DIR"] = name; os.environ.setdefault("SCALE", "87")
    import baukasten_gen as BG, bauteile as BT, trimesh
    from manifold3d import Manifold as M, CrossSection as C, JoinType
    BT.DURCH.clear(); BG.ELEMENTE.clear()                                                               # 'alles' baut zweimal im selben Prozess: Listen nicht weiterschleppen
    ctx = {}; adds, _ = BG.rumpf_lod2({}, ctx); k = k_glatt = adds[0]; F = ctx["lod2_flaechen"]; g2 = ctx["grundriss2d"]; zb = ctx["boden_z"]
    beleg = list(BG.ELEMENTE); seiten = []
    def b(seite, element, quelle, **m): beleg.append(dict(seite=seite, element=element, quelle=quelle, **m))
    # Waende: Normale nach aussen (Grundriss), Brandwand-Test gegen LoD2-Nachbarn
    nb = _nachbarn_dreiecke(obj); waende = _waende(F); SK = obj.get("seiten_konvention", {})
    fl_poly = [np.asarray(p) for p in g2.to_polygons()]
    from matplotlib.path import Path
    def im_grundriss(p): return sum(Path(P).contains_point(p) for P in fl_poly) % 2 == 1
    for i, W in enumerate(waende):
        n = np.array([W["t"][1], -W["t"][0]]); um = W["a"] + W["t"] * 0.5 * (W["uz"][:, 0].min() + W["uz"][:, 0].max())
        if im_grundriss(um + 0.3 * n): n = -n
        W["n"] = n; W["id"] = f"w{i:02d}"; W["seite"] = max(((abs(n[0]), "+x" if n[0] > 0 else "-x"), (abs(n[1]), "+y" if n[1] > 0 else "-y")))[1]
        # bedeckt: Punkte 0,4 m vor der Wand liegen UNTER einem Nachbarn (Strahl nach oben trifft LoD2-Nachbarflaeche) -> Brandwand bis zu dieser Hoehe
        W["nachbar_bis_z"] = None
        if nb is not None:
            us = np.linspace(W["uz"][:, 0].min() + 0.3, W["uz"][:, 0].max() - 0.3, 5); p = W["a"] + us[:, None] * W["t"] + 0.4 * n
            o_ = np.c_[p, np.full(len(p), zb + 0.5)]; loc, ri, _ = nb.ray.intersects_location(o_, np.tile([0, 0, 1.0], (len(p), 1)), multiple_hits=True)
            if len(ri) >= 3:                                                                            # mind. 3 von 5 Stellen bedeckt: Nachbar steht davor; Hoehe = Median der hoechsten Treffer
                hz = [loc[ri == r_, 2].max() for r_ in np.unique(ri)]; W["nachbar_bis_z"] = float(np.median(hz))
        W["frei"] = W["nachbar_bis_z"] is None
    # Fenster aus Fotos. Nischentiefe 0,6 x Wandstaerke (ANNAHME): mit dem Standard 0,12 m brach die Nische schon durch die 0,10-m-Wand, Rahmen standen im Hohlraum
    # -> 60-180 Teilnetze/Kneifkanten an den Fensterecken (tv9o/tv9v/tvac 17.11.2026).
    T_NISCHE = min(0.12, 0.6 * a.wand_mm * SCALE / 1000.0)
    fa = os.path.join(od, "audit", "fenster_auto.json"); fas = os.path.join(od, "audit", "fassaden.json"); n_foto = 0; foto_fass = []
    if os.path.exists(fa) and not a.ohne_fotofenster:
        k, bel = BT.fenster_aus_json(k, fa, tiefe=T_NISCHE); beleg += bel; FJ = json.load(open(fa))
        for fid, Fx in FJ.items():
            nn = len([f for f in Fx["fenster"] if f.get("stimmen_min", 0) >= 2]); n_foto += nn
            if nn: foto_fass.append((np.array(Fx["n"], float), np.array(Fx["o"], float), fid, nn))
    gesehen = []
    if os.path.exists(fas):
        for Fx in json.load(open(fas))["fassaden"]:
            if Fx.get("abdeckung_anteil", 0) >= a.min_abdeckung: gesehen.append((np.array(Fx["n"], float), np.array(Fx["o"], float), Fx["id"], Fx["abdeckung_anteil"], len(Fx.get("fotos") or {})))
    ANN = dict(achse_m=a.achse_m, breite_m=1.0, hoehe_m=1.4, geschoss_m=a.geschoss_m, bruestung_eg_m=1.0, rand_m=0.6)
    n_raster = 0
    for W in waende:
        def gleiche_ebene(L): return [x for x in L if x[0][:2] @ W["n"] > 0.95 and abs((x[1][:2] - W["a"]) @ W["n"]) < 0.4]
        ff = gleiche_ebene(foto_fass); gs = gleiche_ebene(gesehen); se = W["seite"]; sn = SK.get(se, se)
        rec = dict(wand=W["id"], seite=se, seite_name=sn, laenge_m=round(W["laenge"], 2), hoehe_m=round(float(W["uz"][:, 1].max()), 2))
        if not W["frei"] and W["nachbar_bis_z"] >= W["uz"][:, 1].max() - 0.5:
            rec.update(quelle="BRANDWAND (LoD2-Nachbar davor bis z %.1f m) - geschlossen" % W["nachbar_bis_z"]); seiten.append(rec); continue
        if ff:
            rec.update(quelle="FOTO: Fenster aus fassade_parsing (" + ", ".join(f"{x[2]}: {x[3]}" for x in ff) + ")" + ("" if W["frei"] else f"; teils Brandwand bis {W['nachbar_bis_z']:.1f} m")); seiten.append(rec); continue
        if gs and not a.raster_auch_gesehen:
            rec.update(quelle=f"FOTO gesehen ({', '.join(f'{x[2]} Abdeckung {x[3]:.0%}, {x[4]} Fotos' for x in gs)}), aber KEIN Fenster erkannt - geschlossen gelassen (pruefen: audit/fassade/elemente_<id>.jpg)"); seiten.append(rec); continue
        if a.ohne_raster or not HG.get("raster", True):
            rec.update(quelle="kein Foto, Raster abgeschaltet - geschlossen"); seiten.append(rec); continue
        Wd = BT.Wand(W["a"], W["a"] + W["t"], aussen=W["a"] + W["n"]); fen = raster_fenster(W, ANN); nz = 0
        if W["nachbar_bis_z"] is not None: fen = [f for f in fen if f[2] > W["nachbar_bis_z"] + 0.3]
        for u0, u1, z0, z1 in fen:
            sonde = Wd.kasten(u0, u1, z0, z1, 0.03, 0.08)
            if (k ^ sonde).volume() > 0.2 * sonde.volume(): continue
            ab, zu = Wd.fenster(u0, u1, z0, z1, 0.0, tiefe=T_NISCHE); k = k - ab + zu; nz += 1
        n_raster += nz
        if not nz: rec.update(quelle="kein Foto; Wandflaeche zu klein/zu niedrig fuer das Raster (oder nur ueber dem Nachbarn) - geschlossen"); seiten.append(rec); continue
        rec.update(quelle=f"ANNAHME: Fensterraster {nz} Fenster (Achse {ANN['achse_m']} m, {ANN['breite_m']} x {ANN['hoehe_m']} m, Geschoss {ANN['geschoss_m']} m, EG-Bruestung {ANN['bruestung_eg_m']} m) - kein Foto dieser Wand" + ("" if W["frei"] else f"; Brandwand bis {W['nachbar_bis_z']:.1f} m ausgespart"))
        seiten.append(rec)
        if nz: b(se, f"ANNAHME: Fensterraster Wand {W['id']} ({nz} Fenster)", "hintergrundhaus.raster_fenster - KEIN Foto; Masse ANNAHME (typische Altstadt-Geschosse)", n=nz, **{kk: vv for kk, vv in ANN.items()})
    # DOM1-Gegenprobe Dach/Traufe (vor dem Aushoehlen, Aussenhaut identisch)
    dg = dach_gegenprobe(obj, k, waende)
    wid = abs(dg.get("median_laser_minus_modell_m", 0.0)) > a.dach_tol
    trw = [t_ for t_ in dg.get("traufen", []) if abs(t_["median_laser_minus_modell_m"]) > a.dach_tol]   # je Wand: LoD2-Traufe gegen Laser (tv9o 17.11.: Front 1,4 m zu hoch, Flaechenmedian unauffaellig)
    if trw: b("dach", "WIDERSPRUCH Traufe LoD2/DOM1: " + ", ".join(f"{t_['wand']} ({t_['seite']}) Laser-Modell {t_['median_laser_minus_modell_m']:+.2f} m" for t_ in trw),
              "DOM1 1 m, 0,75 m innen der Wand (Randpixel mischen Strasse/Wand - Hinweis, nicht gemittelt; am Foto pruefen)"); dg["traufe_widerspruch"] = [t_["wand"] for t_ in trw]
    b("dach", "Dach aus LoD2 (DOM1-Gegenprobe: Median Laser - Modell %+.2f m, P10/P90 %+.2f/%+.2f, %d Pixel)" % (dg.get("median_laser_minus_modell_m", float("nan")), dg.get("p10_m", float("nan")), dg.get("p90_m", float("nan")), dg.get("n_pixel", 0)),
      "LoD2 (amtlich) Form; DOM1 1 m nur Gegenprobe" + ("; WIDERSPRUCH > %.1f m - nicht gemittelt, Dach ansehen / --dach laser" % a.dach_tol if wid else ""))
    if a.dach == "laser":
        from laserdach import laserdach_koerper
        teile = [laserdach_koerper(os.path.join(od, "objekt.json"), P[:, :2], px=0.5) for t, P in F if t == "GroundSurface" and _fl(P[:, :2]) > 2]
        if teile: k = k_glatt = BG.UNION(teile); BT.DURCH.clear(); b("dach", "Dach als DOM1-Hoehenfeld (tools/laserdach.py, 0,5 m)", "DOM1 1 m (Laser) statt LoD2; Fenster entfallen in diesem Modus")
    # duenne Wand: aushoehlen, Boden offen (Druckteil steht auf der Platte, Innenraum unten zugaenglich)
    d = a.wand_mm * SCALE / 1000.0
    # Boden offen: Hohlraum bis 3 mm ueber zb (boden=0.003), dann die untersten 6 cm des GANZEN Koerpers (> 0,5 d: die Schraeg-Erosion in bauteile.hohlraum hebt den Hohlraumboden um 0,5 d, bei 3 cm blieb ein 0,25-mm-Boden) waagerecht weg (Platte groesser als der Grundriss).
    # Frueher: Ausschnitt = Grundriss um d+2 cm geschrumpft -> 2-cm-Lippen am Wandfuss, 90-200 Teilnetze/Kneifkanten (tv9o/tv9v/tvac 17.11.2026).
    boden = M.extrude(g2.offset(0.5, JoinType.Miter), 0.36).translate((0, 0, zb - 0.3))
    # Hohlraum aus dem GLATTEN Koerper (ohne Nischen/Rahmen), wie bauteile.aushoehlen sonst: dort wird er aus dem Koerper MIT Fensternischen erodiert -> die
    # verschobenen Nischen kerben den Hohlraum genau an der Wandinnenseite ein = Kneifkanten an jeder Fensterecke (tv9v: 118 Kanten, 66 Teilnetze im STL, 17.11.2026).
    cuts = [W_.kasten(u0, u1, z0, z1, wr - d - 0.25, wr + 0.002) for W_, u0, u1, z0, z1, wr, *_ in BT.DURCH] + [boden]; alle = BG.UNION(cuts); raum = None; v_h = 0.0
    for t_ in BT.hohlraum(k_glatt, d, None, 0.003).decompose():
        if t_.volume() >= 0.2 and (t_ ^ alle).volume() > 1e-4: raum = t_ if raum is None else raum + t_; v_h += t_.volume()
    n_off = sum(1 for c_ in cuts if raum is not None and (c_ ^ raum).volume() > 1e-5)
    k = ((k - raum) if raum is not None else k) - alle; tl_ = k.decompose()
    if len(tl_) > 1: k = BG.UNION([t_ for t_ in tl_ if t_.volume() >= 0.05])
    k = BT.kneifkanten_schliessen(k).trim_by_plane((0.0, 0.0, 1.0), zb + 0.06)                              # Kneif-Kloetze am Fuss ragten unter die Schnittebene -> Splitter unter der Druckflaeche
    # (kein Zuruecksetzen um 6 cm: Hoehen bleiben amtlich, das Druckteil faengt 6 cm = 0,7 mm ueber dem Gelaende an; der Slicer legt es auf die Platte)
    b("alle", f"Duenne Wand {a.wand_mm} mm (= {d:.3f} m), Boden offen, {n_off} Durchbrueche erreichen den Hohlraum ({v_h:.0f} m3)", "bauteile.aushoehlen; Wandstaerke = Druckvorgabe (ANNAHME 1,2 mm, CLAUDE.md WAND_MM)")
    # STL in mm
    k = k.simplify(0.005)                                                                                # wie baukasten_gen (VEREINFACHEN_M 5 mm = 0,06 mm im Druck): Splitterkanten an konkaven Fussecken
    m = k.scale((1000 / SCALE,) * 3).to_mesh(); T = trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts), process=True)
    if not T.is_watertight and os.environ.get("HG_ROH") != "1":                                                                              # Mini-Splitter (1-2 Dreiecke an konkaven Grundrissecken am Fuss, Boolesche Numerik): weg, wie baukasten_gen splitter_verwerfen
        tl_ = sorted(T.split(only_watertight=False), key=lambda q_: -len(q_.faces))                # Splitter = Klappen aus 2 deckungsgleichen Nullflaechen-Dreiecken (gemessen tv9v: Flaeche 0)
        T2 = trimesh.util.concatenate([q_ for q_ in tl_ if q_ is tl_[0] or (len(q_.faces) > 12 and q_.area > 1e-3)]); T2.merge_vertices()
        if T2.is_watertight or len(T2.faces) >= 0.99 * len(T.faces): print(f"  Splitter verworfen: {len(tl_) - len(T2.split(only_watertight=False))} Teilnetze, wasserdicht {T2.is_watertight}"); T = T2
    os.makedirs(os.path.dirname(obj["stl"]), exist_ok=True); T.export(obj["stl"])
    json.dump([dict(e, seite_name=SK.get(e.get("seite"), e.get("seite"))) for e in beleg], open(os.path.join(od, "elemente.json"), "w"), indent=1, ensure_ascii=False)
    pruef = dict(wasserdicht=bool(T.is_watertight), koerper=len(T.split(only_watertight=False)), hoehe_m=round(float(T.bounds[1, 2] - T.bounds[0, 2]) * SCALE / 1000, 2),
                 masse_mm=(T.bounds[1] - T.bounds[0]).round(1).tolist(), dreiecke=len(T.faces))
    bp = os.path.join(od, "hintergrund_beleg.json"); alt = json.load(open(bp)) if os.path.exists(bp) else {}
    alt.update(reifegrad=1, kennzeichnung=KENNUNG, lod2=obj["lod2"]["id"], stl=obj["stl"], seiten=seiten, fenster_foto=n_foto, fenster_raster_annahme=n_raster, dach_dom1=dg, dach_widerspruch=wid,
               dach_modus=a.dach, pruefung=pruef, wand_mm=a.wand_mm, raster_annahme=None if a.ohne_raster else ANN, sekunden_bauen=round(time.time() - t0, 1))
    json.dump(alt, open(bp, "w"), indent=1, ensure_ascii=False)
    print(f"-> {obj['stl']}  {pruef}  Fenster Foto {n_foto} / Raster-ANNAHME {n_raster}  Dach DOM1-LoD2 {dg.get('median_laser_minus_modell_m')} m  ({time.time() - t0:.1f} s)")
    for s_ in seiten: print(f"   {s_['wand']} {s_['seite_name']:9s} {s_['laenge_m']:5.1f} m: {s_['quelle'][:150]}")
    return pruef


# ------------------------------------------------------------------ fotos
def fotos(a):
    """Mehrfoto-Ortho + OWLv2 + Fenstergruppen fuer das Haus (ohne neue SfM). GPU begrenzt: Ortho --gpu-mb, Parsing Batch 2 + Speicheranteil."""
    t0 = time.time(); od = _od(a.name); name = os.path.basename(od); obj = json.load(open(os.path.join(od, "objekt.json")))
    if not glob.glob(os.path.join(od, "messprotokoll", "K-*.json")): print("keine Kameras - Fotostufe uebersprungen (Raster-ANNAHME)"); return 2
    fo = os.path.join(DATEN, name, "fassade"); os.makedirs(fo, exist_ok=True); log = os.path.join(od, "audit", "fotos.log")
    env = dict(os.environ, HF_HOME="/media/oem/scan/hf_cache", HF_HUB_OFFLINE="1", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    def lauf(cmd):
        with open(log, "a") as L: L.write("+ " + " ".join(cmd) + "\n"); L.flush(); r = subprocess.run(cmd, cwd=ROOT, stdout=L, stderr=subprocess.STDOUT, env=env)
        return r.returncode
    rc = lauf([PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", os.path.join(od, "objekt.json"), "--stl", obj["stl"], "--aus", fo, "--einzeln", "--min-flaeche", "6", "--gpu-mb", str(a.gpu_mb_ortho)])
    if rc != 0: print("fassade_ortho rc", rc, "- siehe", log); return rc
    fr = a.gpu_mb_parsing / 8188.0
    rc = lauf([PY, "-W", "ignore", "-I", "-c", "import sys; sys.path.insert(0, 'tools'); import torch; torch.cuda.is_available() and torch.cuda.set_per_process_memory_fraction(%.3f); "
               "import fassade_parsing as FP; FP.batch_groesse = lambda *a, **k: %d; FP.main(['--ortho', %r, '--gpu'])" % (fr, a.batch, fo)])
    if rc != 0: print("fassade_parsing rc", rc, "- siehe", log); return rc
    rc = lauf([PY, "-W", "ignore", "-I", "tools/fenster_aus_parsing.py", fo, "--aus", os.path.join(od, "audit", "fenster_auto.json")])
    import shutil
    shutil.copy(os.path.join(fo, "fassaden.json"), os.path.join(od, "audit", "fassaden.json"))
    lk = os.path.join(od, "audit", "fassade")
    if not os.path.lexists(lk): os.symlink(fo, lk)
    print(f"Fotostufe rc {rc}: {fo} ({time.time() - t0:.0f} s)"); return rc


# ------------------------------------------------------------------ druck + pruefen
def druck(a):
    od = _od(a.name); obj = json.load(open(os.path.join(od, "objekt.json"))); aus = obj["stl"].replace(".stl", "_druck.stl")
    r = subprocess.run([PY, "-W", "ignore", "-I", "tools/druck_rippen.py", obj["stl"], aus, "--bild", os.path.join(od, "audit", "rippen.png")], cwd=ROOT, capture_output=True, text=True)
    print("druck_rippen rc", r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] if (r.stdout + r.stderr).strip() else "")
    bp = os.path.join(od, "hintergrund_beleg.json"); B = json.load(open(bp)); B["druck"] = dict(stl=aus, rc=r.returncode, ausgabe=(r.stdout + r.stderr).strip().splitlines()[-4:]); json.dump(B, open(bp, "w"), indent=1, ensure_ascii=False)
    return r.returncode


def beste_fotos(od, n=2):
    """Je Hausseite das Foto mit den meisten gesehenen Zellen (fassaden.json), hoechstens n Seiten (die groessten)."""
    p = os.path.join(od, "audit", "fassaden.json")
    if not os.path.exists(p): return []
    L = []
    for F in sorted(json.load(open(p))["fassaden"], key=lambda F: -F.get("flaeche_m2", 0) * F.get("abdeckung_anteil", 0)):
        fo = F.get("fotos") or {}
        if not fo or F.get("abdeckung_anteil", 0) < 0.15: continue
        best = max(fo.items(), key=lambda kv: kv[1].get("zellen", 0) * kv[1].get("guete_median", 1))[0]
        if best not in L: L.append(best)
        if len(L) >= n: break
    return L


def sichtblatt_kontext(od, obj, foto, m_haus, K, box):
    """Foto | Render (Haus orange, LoD2-Nachbarn grau = Lagebezug der Kamera) | Ueberlagerung (Hauskanten rot, Nachbarkanten gelb auf dem Foto).
    Ohne die Nachbarn sieht man nicht, ob ein Versatz am Haus (LoD2) oder an der Kamera liegt."""
    import cv2, trimesh, render_kern as rk
    nb = _nachbarn_dreiecke(obj, radius=50.0); mm = trimesh.util.concatenate([m_haus, nb]) if nb is not None else m_haus; nh = len(m_haus.faces)
    R = cv2.Rodrigues(np.array(K["rvec"]))[0]; t = np.array(K["t"]); f, cx, cy = K["f_px"], K["cx"], K["cy"]
    im = cv2.imread((glob.glob(os.path.join(ROOT, obj["fotos_dir"], foto + ".*")) or glob.glob(os.path.join(ROOT, obj["fotos_dir"], foto + "_*")))[0]); k1 = float(K.get("k1") or 0.0)
    if k1: im = cv2.undistort(im, np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]), np.array([k1, 0, 0, 0.0]))
    x0, y0, x1, y1 = box; res = rk.dreiecke_rastern(mm, R, t, f, cx - x0, cy - y0, x1 - x0, y1 - y0); fid = np.asarray(res[1].cpu() if hasattr(res[1], "cpu") else res[1]); tr = fid >= 0
    li = R.T @ np.array([-0.45, -0.75, -1.0]); li /= np.linalg.norm(li); hell = np.zeros(fid.shape); hell[tr] = 0.35 + 0.65 * np.clip(mm.face_normals[fid[tr]] @ li, 0, 1)
    haus = tr & (fid < nh); r = np.full(fid.shape + (3,), 235, np.uint8)
    r[tr & ~haus] = (hell[tr & ~haus, None] * np.array([200, 200, 200])).astype(np.uint8); r[haus] = (hell[haus, None] * np.array([80, 170, 255])).astype(np.uint8)
    lab = np.where(tr, np.where(haus, 1, 2), 0).astype(np.uint8); fl = np.where(tr, fid, -1)
    kant = (np.abs(np.diff(fl.astype(np.int64), axis=0, prepend=fl[:1])) > 0) | (np.abs(np.diff(fl.astype(np.int64), axis=1, prepend=fl[:, :1])) > 0)
    nrm = np.zeros(fid.shape + (3,)); nrm[tr] = mm.face_normals[fid[tr]]; dn = (np.linalg.norm(np.diff(nrm, axis=0, prepend=nrm[:1]), axis=2) > 0.2) | (np.linalg.norm(np.diff(nrm, axis=1, prepend=nrm[:, :1]), axis=2) > 0.2)
    kant = cv2.dilate(((dn | (np.diff(lab, axis=0, prepend=lab[:1]) != 0) | (np.diff(lab, axis=1, prepend=lab[:, :1]) != 0)) & kant).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    foto_ = im[y0:y1, x0:x1]; ov = foto_.copy(); hk = kant & cv2.dilate(haus.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    ov[kant & ~hk] = (0, 220, 255); ov[hk] = (0, 0, 255)
    o = np.hstack([foto_, r, ov]); s = 2400 / o.shape[1]; o = cv2.resize(o, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    cv2.putText(o, f"HINTERGRUND Reifegrad 1 - {os.path.basename(od)} - {foto[:50]}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    aus = os.path.join(od, "audit", f"kontext_{foto}.jpg"); cv2.imwrite(aus, o, [cv2.IMWRITE_JPEG_QUALITY, 85]); return aus


def pruefen(a):
    import cv2, trimesh
    od = _od(a.name); name = os.path.basename(od); op = os.path.join(od, "objekt.json"); obj = json.load(open(op)); bp = os.path.join(od, "hintergrund_beleg.json"); B = json.load(open(bp))
    r = subprocess.run([PY, "-W", "ignore", "-I", "tools/hoehe_gegen_dom1.py", op, "--radius", str(a.dom_radius), "--zmin", "3"], cwd=ROOT, capture_output=True, text=True)
    B["hoehe_gegen_dom1"] = dict(rc=r.returncode, ausgabe=[z for z in r.stdout.strip().splitlines() if z.strip()][-3:])
    print("hoehe_gegen_dom1 rc", r.returncode, "|", " / ".join(B["hoehe_gegen_dom1"]["ausgabe"])[:300])
    bilder = []
    m = trimesh.load(obj["stl"]); m.apply_scale(SCALE / 1000.0); P = m.vertices[np.random.default_rng(0).choice(len(m.vertices), min(4000, len(m.vertices)), replace=False)]
    for foto in beste_fotos(od, 2):
        K = json.load(open(os.path.join(od, "messprotokoll", f"K-{foto}.json")))["kamera"]; R = cv2.Rodrigues(np.array(K["rvec"]))[0]; X = P @ R.T + np.array(K["t"]); X = X[X[:, 2] > 0.3]
        u = K["f_px"] * X[:, 0] / X[:, 2] + K["cx"]; v = K["f_px"] * X[:, 1] / X[:, 2] + K["cy"]; W_, H_ = (K.get("bild") or [2 * K["cx"], 2 * K["cy"]])[:2]
        rnd = 0.15 * max(np.ptp(u), np.ptp(v), 50); box = [int(max(0, u.min() - rnd)), int(max(0, v.min() - rnd)), int(min(W_, u.max() + rnd)), int(min(H_, v.max() + rnd))]
        aus = os.path.join(od, "audit", f"neben_{foto}.jpg")
        rr = subprocess.run([PY, "-W", "ignore", "-I", "tools/modell_neben_foto.py", op, foto, aus, "--stl", obj["stl"], "--box"] + [str(x) for x in box], cwd=ROOT, capture_output=True, text=True)
        if rr.returncode == 0: bilder.append(aus); print("ANSEHEN (Modell neben Foto, HINTERGRUND Reifegrad 1):", aus)
        else: print("neben-Bild FEHLER", foto, rr.stderr[-300:])
        try: bilder.append(sichtblatt_kontext(od, obj, foto, m, K, box)); print("ANSEHEN (Foto | Modell orange + LoD2-Nachbarn grau | Ueberlagerung):", bilder[-1])
        except Exception as e_: print("Kontextbild FEHLER", foto, repr(e_)[:200])
    nf_ = [os.path.basename(b_)[6:-4] for b_ in bilder if os.path.basename(b_).startswith("neben_")]
    if nf_: obj["neben_fotos"] = nf_; json.dump(obj, open(op, "w"), indent=1, ensure_ascii=False)
    else:                                                                                               # kein Foto sieht das Haus: wenigstens eine freie Ansicht (Raster-ANNAHME ansehen)
        c_ = m.bounds.mean(0); e_ = float(np.ptp(m.bounds[:, :2], axis=0).max()); aus = os.path.join(od, "audit", "ansicht_suedwest.jpg")
        rr = subprocess.run([PY, "-W", "ignore", "-I", "tools/modell_ansicht.py", aus, "--stl", obj["stl"], "--von", str(c_[0] - 1.6 * e_), str(c_[1] - 1.9 * e_), str(c_[2] + 0.6 * e_),
                             "--nach", str(c_[0]), str(c_[1]), str(c_[2]), "--f", "1400", "--groesse", "1000", "800"], cwd=ROOT, capture_output=True, text=True)
        if rr.returncode == 0: bilder.append(aus); print("ANSEHEN (kein Foto - freie Ansicht, Fenster = ANNAHME):", aus)
    B["sichtblatt"] = bilder; json.dump(B, open(bp, "w"), indent=1, ensure_ascii=False)
    return 0


def alles(a):
    t0 = time.time(); Z = {}
    anlegen(a); Z["anlegen"] = round(time.time() - t0, 1)
    a.ohne_fotofenster = True; bauen(a); Z["rumpf"] = round(time.time() - t0 - sum(Z.values()), 1)       # Stufenmodell fuer die Ortho-Sichtpruefung (ohne Fenster)
    a.ohne_fotofenster = False
    if a.kameras_von and not a.ohne_fotos: fotos(a); Z["fotos"] = round(time.time() - t0 - sum(Z.values()), 1)
    bauen(a); Z["bauen"] = round(time.time() - t0 - sum(Z.values()), 1)
    if not a.ohne_rippen: druck(a); Z["druck"] = round(time.time() - t0 - sum(Z.values()), 1)
    pruefen(a); Z["pruefen"] = round(time.time() - t0 - sum(Z.values()), 1)
    bp = os.path.join(_od(a.name), "hintergrund_beleg.json"); B = json.load(open(bp)); B["zeiten_s"] = Z; B["gesamt_s"] = round(time.time() - t0, 1); json.dump(B, open(bp, "w"), indent=1, ensure_ascii=False)
    print(f"FERTIG {a.name}: {B['gesamt_s']:.0f} s {Z} - {KENNUNG}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); sp = ap.add_subparsers(dest="cmd", required=True)
    k = sp.add_parser("kandidaten"); k.add_argument("--um", required=True); k.add_argument("--radius", type=float, default=60.0)
    for nm in ("anlegen", "bauen", "fotos", "druck", "pruefen", "alles"):
        p = sp.add_parser(nm); p.add_argument("name")
        p.add_argument("--lod2-id"); p.add_argument("--gml"); p.add_argument("--kameras-von"); p.add_argument("--um", type=float, nargs=2); p.add_argument("--titel"); p.add_argument("--ort")
        p.add_argument("--neu", action="store_true", help="masstabelle/objekt.json neu schreiben"); p.add_argument("--wand-mm", type=float, default=1.2)
        p.add_argument("--ohne-raster", action="store_true", help="kein Fensterraster (ANNAHME) auf Waenden ohne Foto"); p.add_argument("--raster-auch-gesehen", action="store_true", help="Raster auch auf Waenden, die Fotos sehen, wo aber kein Fenster erkannt wurde")
        p.add_argument("--ohne-fotofenster", action="store_true"); p.add_argument("--ohne-fotos", action="store_true"); p.add_argument("--ohne-rippen", action="store_true")
        p.add_argument("--min-abdeckung", type=float, default=0.25, help="Fassade gilt als 'vom Foto gesehen' ab diesem Abdeckungsanteil (fassade_ortho)")
        p.add_argument("--achse-m", type=float, default=2.4); p.add_argument("--geschoss-m", type=float, default=3.0)
        p.add_argument("--dach", choices=("lod2", "laser"), default="lod2"); p.add_argument("--dach-tol", type=float, default=1.0)
        p.add_argument("--gpu-mb-ortho", type=float, default=1000); p.add_argument("--gpu-mb-parsing", type=float, default=1300); p.add_argument("--batch", type=int, default=1)   # Budget je Agent 1500 MiB (8-GB-Karte geteilt, 17.11.2026)
        p.add_argument("--dom-radius", type=float, default=14.0)
    a = ap.parse_args()
    if a.cmd == "kandidaten": return kandidaten(a)
    if a.cmd in ("anlegen", "alles") and not a.lod2_id:
        op = os.path.join(_od(a.name), "objekt.json")
        if not os.path.exists(op): sys.exit("--lod2-id fehlt")
        o = json.load(open(op)); a.lod2_id = o["lod2"]["id"]; a.gml = a.gml or o["lod2"]["gml"]; a.kameras_von = a.kameras_von or (os.path.join(ROOT, o["hintergrund"]["kameras_von"]) if o.get("hintergrund", {}).get("kameras_von") else None)
    if a.cmd != "anlegen" and a.cmd != "alles":
        o = json.load(open(os.path.join(_od(a.name), "objekt.json"))); a.ohne_raster = a.ohne_raster or not o.get("hintergrund", {}).get("raster", True); a.kameras_von = a.kameras_von or o.get("hintergrund", {}).get("kameras_von")
    return {"anlegen": anlegen, "bauen": bauen, "fotos": fotos, "druck": druck, "pruefen": pruefen, "alles": alles}[a.cmd](a)


if __name__ == "__main__":
    r = main(); sys.exit(r if isinstance(r, int) else 0)

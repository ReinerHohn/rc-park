#!/usr/bin/env python3
"""test_foto_diff.py - BEWEIS (bekannte Wahrheit) fuer foto_diff.py, generisch fuer jedes Objekt mit K-Kamera (2026-11-04).
Das "Foto" ist ein Render des Modells mit derselben Kamera (Helligkeit je Ebene + Schattierung + Rauschen, Himmel/Boden), in Originalgroesse.
  T1 wahr:      Foto = Modell, Vergleich mit dem Modell          -> Anteil Modellkanten ohne Foto klein (<= --t1-max)
  T2 versetzt:  Foto = Modell um 0,6 m seitlich versetzt          -> Anteil deutlich groesser als T1 (>= 3 x und >= T1 + 0,1) ODER geschaetzter Versatz auf 30 % am erwarteten Bildvektor (T2v)
  T1v:          Versatzschaetzung am wahren Foto <= 0,15 m (Pflicht)
  T6 Verdecker:  Kasten zwischen Kamera und Fassade nur im Bild + synthetische Tiefenkarte -> mit Maske keine Treffer im Verdeckerbereich (<= T1 + 1,5 m) und Anteil <= T1 + 0,05; ohne Maske >= T1 + 1,5 m
  T6b:          Tiefenkarte mit 1 Grad verdrehter Kamera (andere Ausrichtung) muss vom Tor abgelehnt werden (Martinstor 014: dicht_nord gegen K aus buendel)
  Pruefbilder tragen die Verzeichnung k1 der echten Kamera; T5 (Gegenprobe, Bericht): wahres Bild mit --keine-entzerrung sollte bei |k1| >= 0,02 durchfallen
  T3 erfunden:  Modell + Kasten (2 x 2 x 1 m vor der Fassade), Foto ohne -> FALSCH-Kantenlaenge im Bildbereich des Kastens >= T1 + 1,5 m
  T4 fehlt:     Foto mit Kasten, Modell ohne                      -> FEHLT-Kantenlaenge im Bildbereich des Kastens >= T1 + 1,5 m
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_foto_diff.py modelle/<objekt>/objekt.json --foto 004 [--stl ...] [--werkzeug tools/foto_diff.py]
Ergebnis audit/test_foto_diff_<foto>.json (+ Bilder im Arbeitsordner); Exit 0 nur wenn T1-T4 bestehen.
"""
import sys, os, json, glob, argparse, subprocess, tempfile, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlteile_finden as FF, render_kern as RK

PY = sys.executable


def modell(obj, stl, kk):
    m = trimesh.load(stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    T_ = np.array(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float); m.apply_translation(T_); return m, T_


def foto_rendern(m, R, t, f, cx, cy, W0, H0, rng):
    k = min(1.0, 2000.0 / max(W0, H0)); W, H = int(round(W0 * k)), int(round(H0 * k))                  # dicht auf <= 2000 px rendern, dann hochskalieren (bei 1000 px fehlten feine Martinstor-Details im Pruefbild)
    P, fi = trimesh.sample.sample_surface(m, 20000000, seed=1); P = np.asarray(P)
    depth, idx = RK.tiefenbild(P, R, t, f * k, cx * k, cy * k, W, H)
    if hasattr(depth, "cpu"): depth = depth.cpu().numpy(); idx = idx.cpu().numpy()
    N = m.face_normals[fi]; d = np.einsum("ij,ij->i", N, m.triangles_center[fi])
    key = np.round(N * 8).astype(int) * 1000 + np.round(d / 0.5).astype(int)[:, None]               # Ebenen-Schluessel: gleiche Ebene = gleiche Albedo (keine Dreiecksnaehte)
    _, inv = np.unique(key, axis=0, return_inverse=True); alb = rng.uniform(80, 220, inv.max() + 1)[inv.ravel()]
    img = np.full((H, W), 200.0); img[int(H * 0.6):] = 120.0
    tr = idx >= 0; n = N[idx[tr]]; l1 = np.array([0.4, -0.5, 0.75]); l2 = np.array([-0.7, 0.3, 0.2]); l1 /= np.linalg.norm(l1); l2 /= np.linalg.norm(l2)
    img[tr] = (40 + 80 * np.abs(n @ l1) + 50 * np.abs(n @ l2)                                         # zwei Lichtrichtungen: jeder Knick hat Kontrast
               + 35 * np.cos(2.3 * d[idx[tr]]))                                                        # je Ebene aus ihrem Abstand d: parallele Flaechen in anderer Tiefe (Lisene vor Wand) unterscheiden sich, keine Streifen in der Flaeche
                                                                                                      # (vorher Zufallsalbedo allein -> zufaellig gleich hell, Martinstor T1 46 %; Tiefen-Sinus -> Streifen auf Schraegen)
    img = cv2.morphologyEx(img.astype(np.float32), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))           # Punktrender-Loecher schliessen
    img = cv2.resize(img, (W0, H0), interpolation=cv2.INTER_LINEAR); img += rng.normal(0, 4, img.shape); return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def kasten(m, R, t, f, cx, cy, W, H):
    """Kasten 2 x 2 x 1 m vor der ruhigsten sichtbaren Modellflaeche (geringste Kantendichte), auf der Sichtlinie zur Kamera ausgerichtet."""
    k = min(1.0, 800.0 / max(W, H)); w_, h_ = int(W * k), int(H * k)                                    # ruhige Flaeche suchen (wenig Modellkanten), sonst verschwindet der Kasten zwischen Balkon-/Pfeilerkanten
    P, fi = trimesh.sample.sample_surface(m, 3000000, seed=2); P = np.asarray(P); depth, idx = RK.tiefenbild(P, R, t, f * k, cx * k, cy * k, w_, h_)
    if hasattr(idx, "cpu"): depth = depth.cpu().numpy(); idx = idx.cpu().numpy()
    N = m.face_normals[fi]; nb = np.zeros((h_, w_, 3)); tr = idx >= 0; nb[tr] = N[idx[tr]]
    kante = (np.abs(np.diff(nb, axis=0, prepend=0)).sum(2) > 0.3) | (np.abs(np.diff(nb, axis=1, prepend=0)).sum(2) > 0.3) | ~tr
    dichte = cv2.blur(kante.astype(np.float32), (max(3, w_ // 8),) * 2); dichte[~tr] = 9; rand = int(0.15 * min(w_, h_)); dichte[:rand] = dichte[-rand:] = 9; dichte[:, :rand] = dichte[:, -rand:] = 9
    y, x = np.unravel_index(np.argmin(dichte), dichte.shape)
    if dichte[y, x] >= 9: raise SystemExit("keine ruhige Modellflaeche im Bild")
    i = idx[y, x]
    p = P[i]; C = -np.asarray(R).T @ np.asarray(t, float); n = (C - p) / np.linalg.norm(C - p)         # auf der Sichtlinie, zur Kamera gedreht: sicher sichtbar (an der Flaechennormale steckte er im Balkon)
    p = p + 0.6 * n                                                                                    # Rueckseite 0,1 m vor der Flaeche (Mitte unten + 0,5 n)
    up = np.array([0, 0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0]); u = np.cross(up, n); u /= np.linalg.norm(u); w = np.cross(n, u)
    k = trimesh.creation.box(extents=[2.0, 2.0, 1.0]); T = np.eye(4); T[:3, 0], T[:3, 1], T[:3, 2] = u, w, n; T[:3, 3] = p + 0.5 * n; k.apply_transform(T)
    return k, p + 0.5 * n


def stl_schreiben(m, T_, obj, pfad):
    mm = m.copy(); mm.apply_translation(-T_); mm.apply_scale(1000.0 / obj.get("stl_massstab", 87)); mm.export(pfad)


def foto_diff(werkzeug, objp, nr, bild, stl, aus, extra=()):
    r = subprocess.run([PY, "-W", "ignore", "-I", werkzeug, objp, nr, "--bild", bild, "--stl", stl, "--aus", aus] + list(extra), capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit("foto_diff: " + (r.stderr or r.stdout)[-600:])
    return json.load(open(os.path.join(aus, f"foto_diff_{nr}.json")))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--foto", required=True); ap.add_argument("--stl"); ap.add_argument("--werkzeug", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "foto_diff.py"))
    ap.add_argument("--t1-max", type=float, default=0.25); ap.add_argument("--arbeit"); ap.add_argument("--fd", default="", help="weitere foto_diff-Argumente, z. B. \"--kanten normalen\""); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od)); nr = a.foto
    kp = FF.k_datei(objp, obj, root, nr); K = json.load(open(kp)); kk = K["kamera"]; W, H = kk["bild"]   # dieselbe Aufloesung wie foto_diff (vorher Objektordner hier, Masstabellenordner dort -> zwei Kameras, Martinstor T1 55 %)
    R, t, f, _, _ = FF.kamera_laden(K, obj, nr, root, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
    stl0 = a.stl or os.path.join(root, obj["stl"]); m, T_ = modell(obj, stl0, kk); rng = np.random.default_rng(0)
    wd = a.arbeit or tempfile.mkdtemp(prefix="test_foto_diff_"); os.makedirs(wd, exist_ok=True)
    kb, kpos = kasten(m, R, t, f, cx, cy, W, H); mk = trimesh.util.concatenate([m, kb])
    ms = m.copy(); Rm = np.asarray(R); seit = np.cross(Rm.T @ np.array([0, 0, 1.0]), [0, 0, 1.0]); seit /= np.linalg.norm(seit); ms.apply_translation(0.6 * seit)   # waagerecht quer zur Blickrichtung (vorher Bild-x ohne z: bei Hochkantfotos fast Blickrichtung, Martinstor 014 nur 6 px = 0,13 m < tol)
    bilder = {}
    for name, mm in (("wahr", m), ("versetzt", ms), ("mit_kasten", mk)):
        p = os.path.join(wd, f"foto_{name}.jpg"); cv2.imwrite(p, FF.foto_verzerren(foto_rendern(mm, R, t, f, cx, cy, W, H, np.random.default_rng(0)), kk), [cv2.IMWRITE_JPEG_QUALITY, 95]); bilder[name] = p   # mit k1 der echten Kamera (vorher Lochkamera auf beiden Seiten: Verzeichnungsfehler unsichtbar)
    pz = lambda X: (lambda Xc: f * Xc[:2] / Xc[2])(Rm @ X + np.asarray(t, float))                    # Bildversatz T2 geometrisch (Phasenkorrelation zog wegen gleichen Rauschens beider Bilder zu 0)
    sp = m.centroid; v2_vek = pz(sp + 0.6 * seit) - pz(sp); v2_px = float(np.linalg.norm(v2_vek)); v2_m = v2_px * float((Rm @ sp + np.asarray(t, float))[2]) / f
    if v2_m < 1.5 * 0.35: raise SystemExit(f"T2-Pruefbild ungueltig: Bildversatz {v2_px:.1f} px = {v2_m:.2f} m < 1,5 x tol")
    stl_k = os.path.join(wd, "modell_mit_kasten.stl"); stl_schreiben(mk, T_, obj, stl_k)
    erg = {}
    for fall, bild, stl in (("T1_wahr", "wahr", stl0), ("T2_versetzt", "versetzt", stl0), ("T3_erfunden", "wahr", stl_k), ("T4_fehlt", "mit_kasten", stl0)):
        aus = os.path.join(wd, fall); os.makedirs(aus, exist_ok=True); erg[fall] = foto_diff(a.werkzeug, objp, nr, bilder[bild], stl, aus, a.fd.split() + ["--tiefen", "aus"])   # echte Tiefenkarten passen nicht zu synthetischen Bildern
    k1 = float(kk.get("k1") or 0.0); t5 = None
    if abs(k1) >= 0.02:                                                                             # T5 Gegenprobe: ohne Entzerrung muss das wahre Bild bei nennenswertem k1 durchfallen (Anteil > t1_max oder Versatz > 0,15 m)
        aus = os.path.join(wd, "T5_ohne_entzerrung"); os.makedirs(aus, exist_ok=True); e5 = foto_diff(a.werkzeug, objp, nr, bilder["wahr"], stl0, aus, a.fd.split() + ["--keine-entzerrung", "--tiefen", "aus"])
        t5 = dict(k1=k1, anteil=e5["anteil_modellkanten_ohne_foto"], versatz=e5.get("versatz"), faellt=bool(e5["anteil_modellkanten_ohne_foto"] > a.t1_max or (e5.get("versatz") or {}).get("versatz_m", 0) > 0.15))
    # T6 VERDECKER: Kasten 3 x 4 x 0,5 m auf 40 % des Weges Kamera -> Fassade nur im Pruefbild; Tiefenkarte (synthetisch, COLMAP-Format) zeigt ihn.
    # Mit Maske darf foto_diff im Bildbereich des Verdeckers nicht mehr FEHLT/FALSCH melden als T1; ohne Maske (Gegenprobe) muss es dort Scheintreffer geben.
    Cc = -Rm.T @ np.asarray(t, float); pv = Cc + 0.4 * (np.asarray(kpos) - Cc); nv = (Cc - pv) / np.linalg.norm(Cc - pv)
    upv = np.array([0, 0, 1.0]); uv_ = np.cross(upv, nv); uv_ /= np.linalg.norm(uv_); wv = np.cross(nv, uv_)
    vb = trimesh.creation.box(extents=[3.0, 4.0, 0.5]); Tv = np.eye(4); Tv[:3, 0], Tv[:3, 1], Tv[:3, 2] = uv_, wv, nv; Tv[:3, 3] = pv; vb.apply_transform(Tv); mv = trimesh.util.concatenate([m, vb])
    bilder["verdeckt"] = os.path.join(wd, "foto_verdeckt.jpg"); cv2.imwrite(bilder["verdeckt"], FF.foto_verzerren(foto_rendern(mv, R, t, f, cx, cy, W, H, np.random.default_rng(0)), kk), [cv2.IMWRITE_JPEG_QUALITY, 95])
    td = os.path.join(wd, "tiefen_synth"); os.makedirs(os.path.join(td, "stereo", "depth_maps"), exist_ok=True); ks = min(1.0, 1600.0 / max(W, H)); Wt, Ht = int(round(W * ks)), int(round(H * ks))
    Pv = np.vstack([np.asarray(trimesh.sample.sample_surface(m, 8000000, seed=3)[0]), np.asarray(trimesh.sample.sample_surface(vb, 2000000, seed=4)[0])])   # Verdecker eigens dicht (nach Flaeche verteilt bekam er zu wenige Punkte: Karte loechrig, Maske leer)
    Dv, _ = RK.tiefenbild(Pv, R, t, f * ks, cx * ks, cy * ks, Wt, Ht)
    Dv = Dv.cpu().numpy() if hasattr(Dv, "cpu") else Dv; Dv = np.where(np.isfinite(Dv), Dv, 0).astype(np.float32)
    Dv = cv2.morphologyEx(Dv, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))                              # Punktrender-Loecher (Tiefe 0 = keine)
    with open(os.path.join(td, "stereo", "depth_maps", f"{nr}.jpg.geometric.bin"), "wb") as fh:
        fh.write(f"{Wt}&{Ht}&1&".encode()); fh.write(Dv.T[:, :, None].ravel(order="F").astype(np.float32).tobytes())
    t_sfm = np.asarray(t, float) + np.asarray(R) @ np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)   # SfM-Rahmen wie echte Tiefenkameras (kameras_aus_buendel: t_K = t_sfm - R T_)
    json.dump({nr: dict(bild=f"{nr}.jpg", W=Wt, H=Ht, fx=f * ks, fy=f * ks, cx=cx * ks + 0.5, cy=cy * ks + 0.5, R=np.asarray(R).tolist(), t=t_sfm.tolist())}, open(os.path.join(td, "kameras_unverzerrt.json"), "w"))
    tdf = os.path.join(wd, "tiefen_fremd"); os.makedirs(os.path.join(tdf, "stereo", "depth_maps"), exist_ok=True)          # T6b: gleiche Karte, Kamera 1 Grad verdreht (andere Ausrichtung) -> Tor muss sie ablehnen
    import shutil; shutil.copy(os.path.join(td, "stereo", "depth_maps", f"{nr}.jpg.geometric.bin"), os.path.join(tdf, "stereo", "depth_maps", f"{nr}.jpg.geometric.bin"))
    Rf = cv2.Rodrigues(np.array([0, np.radians(1.0), 0]))[0] @ np.asarray(R)
    json.dump({nr: dict(bild=f"{nr}.jpg", W=Wt, H=Ht, fx=f * ks, fy=f * ks, cx=cx * ks + 0.5, cy=cy * ks + 0.5, R=Rf.tolist(), t=t_sfm.tolist())}, open(os.path.join(tdf, "kameras_unverzerrt.json"), "w"))
    for fall, extra in (("T6_verdecker", ["--tiefen", td]), ("T6_ohne_maske", ["--tiefen", "aus"]), ("T6b_fremde_kamera", ["--tiefen", tdf])):
        aus = os.path.join(wd, fall); os.makedirs(aus, exist_ok=True); erg[fall] = foto_diff(a.werkzeug, objp, nr, bilder["verdeckt"], stl0, aus, a.fd.split() + extra)
    uvv, _ = cv2.projectPoints(vb.vertices.reshape(-1, 1, 3), cv2.Rodrigues(np.asarray(R))[0], np.asarray(t, float), np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]), None); uvv = uvv.reshape(-1, 2)
    bxv = [uvv[:, 0].min(), uvv[:, 1].min(), uvv[:, 0].max(), uvv[:, 1].max()]
    im_v = lambda d: d["box"][0] <= bxv[2] and d["box"][2] >= bxv[0] and d["box"][1] <= bxv[3] and d["box"][3] >= bxv[1]
    lv = lambda fall: sum(d["laenge_m"] for d in erg[fall]["treffer"] if im_v(d)); l6, l6o, l6b = lv("T6_verdecker"), lv("T6_ohne_maske"), lv("T1_wahr")
    for fall, e in erg.items():                                                                     # T0: Werkzeug und Pruefbild muessen DIESELBE Kamera nutzen, sonst misst der Beweis einen Kameraunterschied
        if "kamera_datei" not in e: raise SystemExit(f"T0 {fall}: foto_diff meldet keine kamera_datei/f_px/cx/cy - Kameragleichheit nicht pruefbar")
        if (os.path.realpath(e["kamera_datei"]) != os.path.realpath(kp) or abs(e["f_px"] - f) > 1e-6 * f or abs(e["cx"] - cx) > 1e-6 or abs(e["cy"] - cy) > 1e-6):
            raise SystemExit(f"T0 {fall}: foto_diff nutzt {e['kamera_datei']} (f {e['f_px']:.1f}, cx {e['cx']:.1f}, cy {e['cy']:.1f}), Pruefbild {kp} (f {f:.1f}, cx {cx:.1f}, cy {cy:.1f})")
    a1 = erg["T1_wahr"]["anteil_modellkanten_ohne_foto"]; a2 =erg["T2_versetzt"]["anteil_modellkanten_ohne_foto"]

    uvk, _ = cv2.projectPoints(kb.vertices.reshape(-1, 1, 3), cv2.Rodrigues(np.asarray(R))[0], np.asarray(t, float), np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]), None); uvk = uvk.reshape(-1, 2)
    bx = [uvk[:, 0].min(), uvk[:, 1].min(), uvk[:, 0].max(), uvk[:, 1].max()]; pad = 0.02 * max(W, H)
    im_kasten = lambda d: d["box"][0] <= bx[2] + pad and d["box"][2] >= bx[0] - pad and d["box"][1] <= bx[3] + pad and d["box"][3] >= bx[1] - pad and (d["box"][2] - d["box"][0]) <= 3 * (bx[2] - bx[0] + 2 * pad)
    t4 = [d for d in erg["T4_fehlt"]["treffer"] if d["art"].startswith("FEHLT") and im_kasten(d)]
    t4_basis = [d for d in erg["T1_wahr"]["treffer"] if d["art"].startswith("FEHLT") and im_kasten(d)]
    l4, l4b = sum(d["laenge_m"] for d in t4), sum(d["laenge_m"] for d in t4_basis)
    t3 = [d for d in erg["T3_erfunden"]["treffer"] if d["art"].startswith("FALSCH") and im_kasten(d)]          # Bildlage statt 3D-Schwerpunkt (Kantenpunkte eines 2x2x1-Kastens streuen > 1,5 m um die Mitte)
    t3_basis = [d for d in erg["T1_wahr"]["treffer"] if d["art"].startswith("FALSCH") and im_kasten(d)]
    l3, l3b = sum(d["laenge_m"] for d in t3), sum(d["laenge_m"] for d in t3_basis)
    v1, v2 = erg["T1_wahr"].get("versatz") or {}, erg["T2_versetzt"].get("versatz") or {}
    t1v = v1.get("versatz_m") is not None and v1["versatz_m"] <= 0.15                                   # ohne Versatz darf die Schaetzung keinen erfinden (Grenze ANNAHME 0,15 m = 1/4 des Pruefversatzes)
    if v2.get("versatz_px") is not None:                                                            # Betrag in m (foto_diff misst m/px an den Kanten; Bildvektor am Schwerpunkt passt nur bei Tiefe = Fassade, Kaufhaus 58 vs 76 px) + Richtung
        ve = np.array(v2["versatz_px"], float); cosr = float(ve @ v2_vek / max(1e-9, np.linalg.norm(ve) * v2_px))
        t2v = abs(v2["versatz_m"] - 0.6) <= 0.3 * 0.6 and cosr >= np.cos(np.radians(20))
    else: t2v = False
    pr = dict(T1=a1 <= a.t1_max, T1v=bool(t1v), T2_anteil=a2 >= max(3 * a1, a1 + 0.1), T2v=bool(t2v), T3=l3 >= l3b + 1.5, T4=l4 >= l4b + 1.5)   # Kastenumfang ~8 m; gegen T1 (gleiches Foto ohne Kasten) verglichen
    # T2 = der Versatz wird bemerkt: per Anteil (alt) ODER per Versatzschaetzung (2026-11-04; in dichter Fassade bleibt der Anteil gleich, Martinstor 23/25 %); T1v ist neu und zusaetzlich Pflicht
    pr["T6"] = bool(l6 <= l6b + 1.5 and erg["T6_verdecker"]["anteil_modellkanten_ohne_foto"] <= a1 + 0.05)   # gegen T1 (Nutzerentscheid 2026-11-04: T6 prueft die Maske, nicht die Grundgenauigkeit; vorher <= t1_max, Martinstor 28,1 %% bei T1 24,3 %%, Verdeckerbereich 0 m)
    pr["T6_gegenprobe"] = bool(l6o >= l6b + 1.5)
    v6b = erg["T6b_fremde_kamera"].get("verdecker") or {}; pr["T6b"] = bool("passt nicht" in str(v6b.get("quelle")) and v6b.get("anteil_silhouette", 1) == 0)   # fremde Tiefenkamera abgelehnt, keine Maske
    ok = pr["T1"] and pr["T1v"] and (pr["T2_anteil"] or pr["T2v"]) and pr["T3"] and pr["T4"] and pr["T6"] and pr["T6_gegenprobe"] and pr["T6b"]
    res = dict(foto=nr, fd_argumente=a.fd, T6=dict(treffer_m=round(l6, 2), ohne_maske_m=round(l6o, 2), basis_m=round(l6b, 2), anteil=erg['T6_verdecker']['anteil_modellkanten_ohne_foto'], anteil_ohne=erg['T6_ohne_maske']['anteil_modellkanten_ohne_foto'], verdeckt=erg['T6_verdecker'].get('verdecker'), fremd=erg['T6b_fremde_kamera'].get('verdecker'), bildbox=[round(float(x)) for x in bxv]), T5_ohne_entzerrung=t5, T2_bildversatz_m=round(v2_m, 3), werkzeug=os.path.relpath(a.werkzeug, root) if a.werkzeug.startswith(root) else a.werkzeug, bestanden=ok, pruefungen=pr, T1_anteil=a1, T2_anteil=a2, T1_versatz=v1, T2_versatz=v2, T2_erwartet_px=[round(float(x), 1) for x in v2_vek],
               T1_fehlt_anteil=erg["T1_wahr"]["anteil_fotokanten_ohne_modell"], T3_treffer=t3[:3], T3_laenge_m=round(l3, 2), T3_basis_m=round(l3b, 2), T4_treffer=t4[:3], T4_laenge_m=round(l4, 2), T4_basis_m=round(l4b, 2), kasten_xyz=kpos.round(2).tolist(), kasten_bildbox=[round(float(x)) for x in bx], arbeit=wd)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(res, open(os.path.join(od, "audit", f"test_foto_diff_{nr}.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("T3_treffer", "T4_treffer")}, ensure_ascii=False))
    print("BEWEIS foto_diff:", "BESTANDEN" if ok else "NICHT BESTANDEN"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

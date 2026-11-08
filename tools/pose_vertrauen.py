#!/usr/bin/env python3
"""pose_vertrauen.py - Vertrauensmass je registriertem Zusatzfoto (Handyfotos) aus Daten abgeleitet.

Je Bild: (a) Abstand zur naechsten Referenzkamera, (b) Abweichung der Posen zweier Laeufe (z. B. SIFT vs ALIKED-LightGlue),
(c) Inlierzahl, (d) f-Kopplung kritisch (Abstand > f_kritisch_m; Schwelle aus der Kreuzvalidierung, nicht von Hand).
Klassen sicher/unsicher/unbrauchbar. Schwellen kommen aus der Referenz-Kreuzvalidierung: jedes Referenzbild wird mit
Punkten, die NUR von weiter als d entfernten anderen Referenzkameras gesehen werden (Leave-one-out), per PnP neu verortet
(Kamera bekannt bzw. f um +-f_streu verstimmt wie beim Handy-Fest-f); Fehler gegen d aufgetragen.
Zusaetzlich unabhaengige Gegenprobe der beiden Posen: Rueckprojektion der Referenz-verankerten Punkte des JEWEILS ANDEREN Laufs.

Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/pose_vertrauen.py --ref <sparse> --lauf A=<reg.json>:<sparse> --lauf B=... --aus <json>
Nur Lesen der Eingaben; schreibt eine kleine JSON. Reine Funktionen (kreuz_*, klassifiziere) sind synthetisch testbar.
"""
import sys, os, json, argparse
import numpy as np

HANDY_PRAEFIX = "h_"


# ---------- reine Hilfsfunktionen ----------
def rot_winkel_grad(R1, R2):
    c = (np.trace(R1.T @ R2) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))


def projiziere(R, t, f, cx, cy, k, X):
    """SIMPLE_RADIAL; X (n,3) Welt -> Pixel (n,2), Tiefe."""
    Xc = X @ R.T + t
    z = Xc[:, 2]
    x = Xc[:, 0] / z; y = Xc[:, 1] / z
    d = 1.0 + k * (x * x + y * y)
    return np.stack([f * x * d + cx, f * y * d + cy], 1), z


def quantil(a, q):
    a = np.asarray(a, float)
    return float(np.quantile(a, q)) if len(a) else None


def schwelle_aus_kreuz(zeilen, tol_m, q=0.9):
    """Groesstes d (Stufen aufsteigend), bis zu dem das q-Quantil des Zentrumsfehlers <= tol_m bleibt (ohne Luecke).
    zeilen: [{'d':..,'fehler_m':..}]. Gibt (d_max oder None, tabelle)."""
    ds = sorted({z["d"] for z in zeilen})
    tab = []; d_ok = None; luecke = False
    for d in ds:
        e = [z["fehler_m"] for z in zeilen if z["d"] == d]
        qq = quantil(e, q)
        tab.append({"d": d, "n": len(e), "median_m": quantil(e, .5), "q_m": qq})
        if qq is not None and qq <= tol_m and not luecke:
            d_ok = d
        else:
            luecke = True
    return d_ok, tab


def klassifiziere(b, s):
    """b: Bildmasse, s: Schwellen. Rueckgabe (klasse, gruende)."""
    g = []
    unbr = False
    if b.get("inlier") is not None and b["inlier"] < s["inlier_min"]:
        unbr = True; g.append(f"Inlier {b['inlier']} < {s['inlier_min']}")
    if s.get("abstand_unbrauchbar_m") is not None and b.get("abstand_ref_m") is not None and b["abstand_ref_m"] > s["abstand_unbrauchbar_m"]:
        unbr = True; g.append(f"Abstand {b['abstand_ref_m']:.1f} m > {s['abstand_unbrauchbar_m']:.1f} m")
    zul = b.get("abw_zulaessig_m", 0.0)  # f-Differenz der Laeufe * Tiefe ist systematisch und darf zusaetzlich abweichen
    if b.get("pose_abw_m") is not None and b["pose_abw_m"] > s["abw_unbrauchbar_m"] + zul:
        unbr = True; g.append(f"Posen-Abweichung {b['pose_abw_m']:.2f} m > {s['abw_unbrauchbar_m'] + zul:.2f} m")
    if unbr:
        return "unbrauchbar", g
    uns = False
    if b.get("abstand_ref_m") is not None and b["abstand_ref_m"] > s["abstand_sicher_m"]:
        uns = True; g.append(f"Abstand {b['abstand_ref_m']:.1f} m > {s['abstand_sicher_m']:.1f} m (ausserhalb des kreuzvalidierten Bereichs)")
    if b.get("pose_abw_m") is not None and b["pose_abw_m"] > s["abw_sicher_m"] + zul:
        uns = True; g.append(f"Posen-Abweichung {b['pose_abw_m']:.2f} m > {s['abw_sicher_m'] + zul:.2f} m")
    zg = max(s["abw_sicher_grad"], b.get("abw_grad_zulaessig", 0.0))
    if b.get("pose_abw_grad") is not None and b["pose_abw_grad"] > zg:
        uns = True; g.append(f"Rot-Abweichung {b['pose_abw_grad']:.2f} Grad > {zg:.2f}")
    if b.get("inlier") is not None and b["inlier"] < s["inlier_sicher"]:
        uns = True; g.append(f"Inlier {b['inlier']} < {s['inlier_sicher']}")
    if b.get("nur_ein_lauf"):
        uns = True; g.append("nur in einem Lauf registriert (keine Gegenprobe)")
    return ("unsicher" if uns else "sicher"), g


# ---------- Rekonstruktion lesen ----------
def lade(pfad):
    import pycolmap
    return pycolmap.Reconstruction(pfad)


def posen(rec, nur=None):
    """name -> dict(R,t,c,cam=(f,cx,cy,k),W,H,id)"""
    out = {}
    for i in rec.images.values():
        if not i.has_pose:
            continue
        if nur is not None and not nur(i.name):
            continue
        cw = i.cam_from_world(); R = cw.rotation.matrix(); t = np.array(cw.translation)
        c = rec.cameras[i.camera_id]; p = list(c.params)
        out[i.name] = {"R": R, "t": t, "c": -R.T @ t, "cam": (p[0], p[1], p[2], p[3] if len(p) > 3 else 0.0),
                       "W": c.width, "H": c.height, "id": i.image_id, "camid": i.camera_id}
    return out


def ref_namen(rec):
    return {i.name for i in rec.images.values() if i.has_pose and not i.name.startswith(HANDY_PRAEFIX)}


# ---------- Kreuzvalidierung (Leave-one-out, mit Mindestabstand d) ----------
def loo_korr(rec, name, d_min, P, refnamen):
    """2D-3D fuer Bild `name`: Punkte, deren uebrige Beobachter (nur Referenzbilder) >= 2 sind und alle >= d_min vom Zentrum entfernt."""
    im = next(i for i in rec.images.values() if i.name == name)
    c0 = P[name]["c"]
    xy = []; X = []; dnah = []
    for p2 in im.points2D:
        if not p2.has_point3D():
            continue
        pt = rec.points3D[p2.point3D_id]
        rest = [e.image_id for e in pt.track.elements if e.image_id != im.image_id]
        nm = [rec.images[r].name for r in rest]
        nm = [n for n in nm if n in refnamen]
        if len(nm) < 2:
            continue
        ds = [float(np.linalg.norm(P[n]["c"] - c0)) for n in nm]
        if min(ds) < d_min:
            continue
        xy.append(p2.xy); X.append(pt.xyz); dnah.append(min(ds))
    return np.array(xy), np.array(X), (float(np.min(dnah)) if dnah else None)


def pnp(xy, X, cam_params, W, H, f_faktor=1.0, seed=0):
    import pycolmap
    f, cx, cy, k = cam_params
    cam = pycolmap.Camera.create_from_model_id(0, pycolmap.CameraModelId.SIMPLE_RADIAL, f * f_faktor, W, H)
    cam.params = [f * f_faktor, cx, cy, k]
    eo = pycolmap.AbsolutePoseEstimationOptions(); eo.estimate_focal_length = False
    eo.ransac.max_error = 4.0; eo.ransac.random_seed = seed
    r = pycolmap.estimate_and_refine_absolute_pose(xy, X, cam, eo)
    if r is None:
        return None
    cw = r["cam_from_world"]; R = cw.rotation.matrix(); t = np.array(cw.translation)
    return {"R": R, "t": t, "c": -R.T @ t, "inlier": int(r["num_inliers"])}


def kreuz(rec, stufen, f_faktoren=(1.0, 0.9, 1.1), n_max=800, min_korr=30, seed=0):
    P = posen(rec); refn = ref_namen(rec); zeilen = []
    rng = np.random.default_rng(seed)
    for name in sorted(refn):
        for d in stufen:
            xy, X, dn = loo_korr(rec, name, d, P, refn)
            if len(X) < min_korr:
                continue
            if len(X) > n_max:  # Handy-Inlierzahlen liegen bei 30..1000: Obergrenze gleiche Groessenordnung
                idx = rng.choice(len(X), n_max, replace=False); xy, X = xy[idx], X[idx]
            Rr, tr = P[name]["R"], P[name]["t"]
            tiefe = float(np.median((X @ Rr.T + tr)[:, 2]))
            for ff in f_faktoren:
                r = pnp(xy, X, P[name]["cam"], P[name]["W"], P[name]["H"], ff, seed)
                if r is None:
                    zeilen.append({"bild": name, "d": d, "f_faktor": ff, "n_korr": int(len(X)), "fehler_m": None, "ok": False})
                    continue
                zeilen.append({"bild": name, "d": d, "d_nah": dn, "f_faktor": ff, "n_korr": int(len(X)), "inlier": r["inlier"], "tiefe_m": tiefe,
                               "fehler_m": float(np.linalg.norm(r["c"] - P[name]["c"])),
                               "fehler_grad": rot_winkel_grad(r["R"], P[name]["R"]), "ok": True})
    return zeilen


# ---------- unabhaengige Gegenprobe zweier Posen ----------
def verankerte_punkte(rec, name, refnamen):
    im = next(i for i in rec.images.values() if i.name == name)
    xy = []; X = []
    for p2 in im.points2D:
        if not p2.has_point3D():
            continue
        pt = rec.points3D[p2.point3D_id]
        nref = sum(1 for e in pt.track.elements if rec.images[e.image_id].name in refnamen)
        if nref >= 2:
            xy.append(p2.xy); X.append(pt.xyz)
    return np.array(xy), np.array(X)


def reproj_median(pose, xy, X):
    if len(X) == 0:
        return None
    f, cx, cy, k = pose["cam"]
    uv, z = projiziere(pose["R"], pose["t"], f, cx, cy, k, X)
    e = np.linalg.norm(uv - xy, axis=1)[z > 0]
    return float(np.median(e)) if len(e) else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="Referenz-Sparse (nur gelesen)")
    ap.add_argument("--lauf", action="append", required=True, help="NAME=registrierung.json:sparse_handy/0 (zwei Laeufe)")
    ap.add_argument("--aus", required=True)
    ap.add_argument("--tol_m", type=float, default=0.10, help="Toleranz Zentrumsfehler = Projektziel 10 cm (Memory ziel-10cm-genauigkeit); der Rauschboden der Kreuzvalidierung wird zusaetzlich ausgewiesen")
    ap.add_argument("--stufen", default="0,2,4,6,8,12")
    a = ap.parse_args(argv)
    stufen = [float(x) for x in a.stufen.split(",")]
    ref = lade(a.ref); Pref = posen(ref)
    laeufe = {}
    for l in a.lauf:
        n, rest = l.split("=", 1); rj, sp = rest.split(":", 1)
        laeufe[n] = {"reg": json.load(open(rj)), "rec": lade(sp), "rjson": rj}
    namen = list(laeufe)
    A, B = namen[0], namen[1]

    # --- Kreuzvalidierung an den Referenzbildern, je Lauf (Punkte des Laufs) und Referenz selbst ---
    # f-Unsicherheit des festen Handy-f: Standardfehler des Medians aus dem Kalibrierlauf (std/sqrt(n)), groesster Wert der Laeufe
    rel = []
    for n in namen:
        kl = os.path.join(os.path.dirname(laeufe[n]["rjson"]), "kalibrierlauf.json")
        if os.path.exists(kl):
            k = json.load(open(kl)); rel.append(k["f_std_px"] / max(k["n_im_fenster"], 1) ** 0.5 / k["f_median_px"])
    fs = [laeufe[n]["reg"]["f_fest_px"] for n in namen]
    rel_lauf = abs(fs[0] - fs[1]) / np.mean(fs)
    f_rel = max(rel + [rel_lauf])
    kv = {"ref": kreuz(ref, stufen, f_faktoren=(1.0, 1.0 - f_rel, 1.0 + f_rel))}
    for n in namen:
        kv[n] = kreuz(laeufe[n]["rec"], stufen, f_faktoren=(1.0,))
    # Rauschboden: d=0, f exakt, Referenznetz
    boden = [z["fehler_m"] for z in kv["ref"] if z["ok"] and z["d"] == stufen[0] and z["f_faktor"] == 1.0]
    tol = a.tol_m; rauschboden = {"median_m": quantil(boden, .5), "q90_m": quantil(boden, .9)}
    # Schwelle des Abstandes: mit f-Verstimmung (Handy-Fall: f fest und ungenau) q90 <= tol
    zf = [z for z in kv["ref"] if z["ok"] and z["f_faktor"] != 1.0]
    d_f, tab_f = schwelle_aus_kreuz([{"d": z["d"], "fehler_m": z["fehler_m"]} for z in zf], tol)
    ze = [z for z in kv["ref"] if z["ok"] and z["f_faktor"] == 1.0]
    d_e, tab_e = schwelle_aus_kreuz([{"d": z["d"], "fehler_m": z["fehler_m"]} for z in ze], tol)
    # Posen-Abweichung SIFT vs LG ist ein Mass fuer den Fehler: Schwelle = tol (sicher), 3*tol (unbrauchbar)
    # Inlier: kleinste Inlierzahl, bei der die Kreuzvalidierung q90 <= tol bleibt
    def inl_schwelle():
        z = [x for x in kv["ref"] if x["ok"] and x["f_faktor"] == 1.0]
        for g in (30, 60, 100, 200, 400):
            e = [x["fehler_m"] for x in z if x["inlier"] >= g]
            if len(e) >= 8 and quantil(e, .9) <= tol:
                return g
        return 400
    inl_s = inl_schwelle()
    # Winkel-Schwelle aus dem Rauschboden (q90 bei d=0)
    gr = [z["fehler_grad"] for z in kv["ref"] if z["ok"] and z["d"] == stufen[0] and z["f_faktor"] == 1.0]
    s = {"tol_m": tol, "abstand_sicher_m": d_e if d_e is not None else 0.0,
         "abstand_unbrauchbar_m": None, "abstand_getestet_max_m": max(stufen),
         "abw_sicher_m": tol, "abw_unbrauchbar_m": 5 * tol, "abw_sicher_grad": quantil(gr, .9) or 1.0,
         "inlier_min": 30, "inlier_sicher": inl_s}
    # Unbrauchbar ab Abstand: erste Stufe, deren q90-Fehler mit f-Verstimmung > 5*tol
    d_u = None
    for r in tab_e:
        if r["q_m"] is not None and r["q_m"] > 5 * tol:
            d_u = r["d"]; break
    if d_u is not None:
        s["abstand_unbrauchbar_m"] = d_u
    # f-Kopplung: Fehler ~ f_rel * Tiefe (an der Kreuzvalidierung geprueft)
    zt = [(x["tiefe_m"], x["fehler_m"]) for x in zf]
    verh = [e / (f_rel * t) for t, e in zt if t > 0]
    f_modell = {"n": len(verh), "median_fehler_/(f_rel*tiefe)": quantil(verh, .5), "q10": quantil(verh, .1), "q90": quantil(verh, .9),
                "korrelation_fehler_tiefe": float(np.corrcoef([t for t, _ in zt], [e for _, e in zt])[0, 1]) if len(zt) > 3 else None,
                "korrelation_fehler_abstand": float(np.corrcoef([x["d"] for x in zf], [x["fehler_m"] for x in zf])[0, 1]) if len(zf) > 3 else None,
                "median_fehler_m": quantil([e for _, e in zt], .5), "median_tiefe_m": quantil([t for t, _ in zt], .5)}
    k_f = f_modell["median_fehler_/(f_rel*tiefe)"] or 1.0

    # --- je Bild ---
    ra = laeufe[A]["rec"]; rb = laeufe[B]["rec"]; Pa = posen(ra); Pb = posen(rb)
    refa = ref_namen(ra); refb = ref_namen(rb)
    alle = sorted(set(laeufe[A]["reg"]["bilder"]) | set(laeufe[B]["reg"]["bilder"]))
    bilder = {}
    for n in alle:
        ja = laeufe[A]["reg"]["bilder"].get(n, {}); jb = laeufe[B]["reg"]["bilder"].get(n, {})
        ia = ja.get("status") == "registriert"; ib = jb.get("status") == "registriert"
        b = {"serie": n.split("_")[1] if n.startswith(HANDY_PRAEFIX) else "?", "reg": {A: ia, B: ib}}
        if not (ia or ib):
            b["klasse"] = "nicht_registriert"; bilder[n] = b; continue
        for L, j, ok in ((A, ja, ia), (B, jb, ib)):
            if ok:
                b["inlier_" + L] = j.get("inlier"); b["abstand_" + L] = j.get("naechste_referenzkamera_m"); b["zentrum_" + L] = j.get("zentrum")
        ins = [b.get("inlier_" + L) for L in (A, B) if b.get("inlier_" + L) is not None]
        ds = [b.get("abstand_" + L) for L in (A, B) if b.get("abstand_" + L) is not None]
        b["inlier"] = min(ins) if ins else None
        b["abstand_ref_m"] = max(ds) if ds else None
        if ia and ib and n in Pa and n in Pb:
            b["pose_abw_m"] = float(np.linalg.norm(Pa[n]["c"] - Pb[n]["c"]))
            b["pose_abw_grad"] = rot_winkel_grad(Pa[n]["R"], Pb[n]["R"])
            # Gegenprobe: Pose A auf den (Referenz-verankerten) Punkten von B und umgekehrt
            xyb, Xb = verankerte_punkte(rb, n, refb); xya, Xa = verankerte_punkte(ra, n, refa)
            b["quer_px"] = {f"pose{A}_auf_{B}": reproj_median(Pa[n], xyb, Xb), f"pose{B}_auf_{B}": reproj_median(Pb[n], xyb, Xb),
                            f"pose{B}_auf_{A}": reproj_median(Pb[n], xya, Xa), f"pose{A}_auf_{A}": reproj_median(Pa[n], xya, Xa),
                            "n_" + A: int(len(Xa)), "n_" + B: int(len(Xb))}
            qa = b["quer_px"][f"pose{A}_auf_{B}"]; qb = b["quer_px"][f"pose{B}_auf_{A}"]
            b["quer_fremd_px"] = {A: qb, B: qa}  # Pose A wird an B-Punkten geprueft: Fremdfehler von A = qa
            b["quer_fremd_px"] = {A: qa, B: qb}
        else:
            b["nur_ein_lauf"] = True
        xq, Xq = verankerte_punkte(ra if n in Pa else rb, n, refa if n in Pa else refb); PP = Pa if n in Pa else Pb
        if len(Xq):
            b["tiefe_m"] = float(np.median((Xq @ PP[n]["R"].T + PP[n]["t"])[:, 2]))
            b["f_fehler_erwartet_m"] = float(k_f * f_rel * b["tiefe_m"])
            b["f_kritisch"] = bool(b["f_fehler_erwartet_m"] > tol)
            b["abw_zulaessig_m"] = float(rel_lauf * b["tiefe_m"])
            b["abw_grad_zulaessig"] = float(np.degrees(np.arctan(tol / b["tiefe_m"])))  # Blickrichtungsfehler, der einen Punkt in Szenentiefe um tol verschiebt
        b["klasse"], b["gruende"] = klassifiziere(b, s)
        bilder[n] = b

    # --- Urteil SIFT vs LG ---
    sieg = {A: 0, B: 0, "gleich": 0}; qa = []; qb = []
    for n, b in bilder.items():
        q = b.get("quer_fremd_px")
        if q and q[A] is not None and q[B] is not None:
            qa.append(q[A]); qb.append(q[B])
            if abs(q[A] - q[B]) < 0.1:
                sieg["gleich"] += 1
            else:
                sieg[A if q[A] < q[B] else B] += 1
    def med_ref(z):
        e = [x["fehler_m"] for x in z if x["ok"] and x["f_faktor"] == 1.0 and x["d"] == stufen[0]]
        return {"n": len(e), "median_m": quantil(e, .5), "q90_m": quantil(e, .9)}
    urteil = {"fremdpunkte_pose_besser": sieg, "median_fremd_px": {A: quantil(qa, .5), B: quantil(qb, .5)},
              "loo_d0_punkte_des_laufs": {n: med_ref(kv[n]) for n in namen}, "loo_d0_referenznetz": med_ref(kv["ref"])}
    # Serien-Tabelle
    tab = {}
    for n, b in bilder.items():
        t = tab.setdefault(b["serie"], {"sicher": 0, "unsicher": 0, "unbrauchbar": 0, "nicht_registriert": 0})
        t[b["klasse"]] += 1
    zus = lambda zz: [{"d": r["d"], "n": r["n"], "median_m": r["median_m"], "q90_m": r["q_m"]} for r in zz]
    out = {"laeufe": namen, "schwellen": s, "f_unsicherheit_rel": f_rel, "f_rel_komponenten": {"standardfehler": rel, "differenz_laeufe": rel_lauf}, "rauschboden_ref_d0": rauschboden, "schwellen_herkunft": {
        "tol_m": "Projektziel 10 cm (Parameter --tol_m); Rauschboden der Kreuzvalidierung steht in rauschboden_ref_d0",
        "abstand_sicher_m": "groesstes getestetes d, bei dem q90 des Fehlers (f exakt, nur Punkte von Referenzkameras >= d entfernt) <= tol_m bleibt; f-Fehler ist abstandsunabhaengig (siehe f_kopplung_modell) und wird je Bild als f_fehler_erwartet_m = k*f_rel*Tiefe/f_kritisch ausgewiesen",
        "abstand_unbrauchbar_m": "kleinstes d, bei dem q90 (f exakt) > 5 x tol_m; None = im getesteten Bereich nie",
        "abw_sicher_m": "tol_m (+ rel_lauf x Tiefe je Bild: f-Differenz der Laeufe verschiebt die Pose systematisch)", "abw_unbrauchbar_m": "5 x tol_m (+ rel_lauf x Tiefe je Bild)", "abw_sicher_grad": "max(q90 Rotationsfehler Rauschboden d=0 f exakt, atan(tol/Tiefe) je Bild)",
        "inlier_sicher": "kleinste Stufe 30/60/100/200/400, ab der q90 des Fehlers <= tol_m (>= 8 Bilder)", "inlier_min": "Mindestinlier der Registrierung (min_inlier = 30)"},
        "f_kopplung_modell": f_modell, "kreuz_f_exakt": tab_e, "kreuz_f_verstimmt": tab_f, "urteil": urteil, "tabelle_je_serie": tab, "bilder": bilder,
        "kreuz_rohdaten_ref": kv["ref"]}
    os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True)
    json.dump(out, open(a.aus, "w"), indent=1, default=float)
    print("Schwellen:", json.dumps(s, default=float))
    print("Kreuz f exakt:", json.dumps(zus(tab_e)))
    print("Kreuz f +-10%:", json.dumps(zus(tab_f)))
    print("f-Modell:", json.dumps(f_modell, default=float))
    print("Urteil:", json.dumps(urteil, default=float))
    print("Serie sicher unsicher unbrauchbar nicht_reg")
    for k in sorted(tab):
        t = tab[k]; print(k, t["sicher"], t["unsicher"], t["unbrauchbar"], t["nicht_registriert"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

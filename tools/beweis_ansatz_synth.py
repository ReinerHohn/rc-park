#!/usr/bin/env python3
"""beweis_ansatz_synth.py - synthetischer Teil von tools/beweis_ansatz.py (Wahrheit bekannt, Metrik 1 dazu).

Wahrheit  : Martinstor-Generator (martinstor_v4_gen.py) mit VERSTELLTEN Parametern in einem eigenen Objektordner modelle/beweis_synth (Symlink auf die Datenplatte):
            Helmtraufe GZ1 +0,8 m, Helmueberstand HELM_UEBER +0,5 m, je Seite ein Fenster weniger (fassade.json).
Fotos     : 10 echte Martinstor-Kameras (martinstor_lod2, Reprojektionsfehler <= 1,5 px, gleichmaessig), Pruefbild wie tools/test_foto_diff.py
            (foto_rendern: Schattierung, Rauschen; Verzeichnung k1 der Kamera). 4 Fotos = Anpassungsfotos (C), 6 = zurueckgehalten (Metrik 2). Festlegung vorab: Anpassung = Index 0,3,6,9.
Wolke     : 1,2 Mio Oberflaechenpunkte der Wahrheit, nur wenn von >= 2 der 10 Kameras sichtbar (Embree-Strahl, Bildfeld, Normale zur Kamera), 5 cm Gaussrauschen je Achse.
DOM1      : 1-m-Raster, Zellmaxima der Wahrheit (80 x 80 m, modellachsparallel).
A Poisson, B DOM1-Saeulen, C = Generator mit Standardparametern (= unverstellter Zwilling modelle/beweis_synth_basis) + Koordinatensuche (Ersatz fuer Stufe 2 param_suche:
          martinstor_v4_gen kennt kein BAUTEIL_PARAM) ueber eine VORAB festgelegte Liste: GZ1, HELM_UEBER, DACHHOEHE, DB; je 4 Werte, Kosten = Mittel(rot+gelb) der 4 Anpassungsfotos.
          Fenster-Anzahl ist nicht suchbar (Stufe-3-Merkmal): bleibt Fehler von C (Restfeld nicht berechnet, keine Fassadenebenen ohne Fotoauswertung).
"""
import os, sys, json, time, glob, shutil, subprocess
os.environ.update(PRUEF_CPU="1", RENDER_CPU="1")                         # Pruefbilder/Wolke auf der CPU (GPU gehoert foto_diff)
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import beweis_ansatz as BA

MASSSTAB = 87.0
SUCHE = [("GZ1", [-0.8, -0.4, 0.4, 0.8]), ("HELM_UEBER", [-0.5, -0.25, 0.25, 0.5]), ("DACHHOEHE", [-0.8, -0.4, 0.4, 0.8]), ("DB", [-0.4, -0.2, 0.2, 0.4])]
GENERATOR = "SCALE=87 MINMM=0.8 ~/.venvs/rcpark/bin/python modelle/martinstor_v4_gen.py"
WAHRHEIT_V = {"schwach": dict(GZ1=0.8, HELM_UEBER=0.5), "stark": dict(GZ1=0.8, HELM_UEBER=0.5, W=0.8, D=-0.6, ZK=1.5, H_TOTAL=-2.0)}   # stark: nachgezogen, weil "schwach" nur 0,7 cm Chamfer zum Standard hatte (Wahrheit nicht unterscheidbar)
WAHRHEIT_AENDERUNG = dict(WAHRHEIT_V["schwach"])
VARIANTE = [os.environ.get("SYNTH_VARIANTE", "schwach")]


def synth_ordner(aus):
    """Wahrheits- und Zwillingsordner (unverstellt) aus modelle/martinstor kopieren und die Wahrheit verstellen. Idempotent (wird neu geschrieben)."""
    for nm in ("synth_obj", "synth_basis"):
        d = os.path.join(BA.BASIS, nm)
        if os.path.exists(d): shutil.rmtree(d)
        os.makedirs(os.path.join(d, "messprotokoll"))
        for f in ("masse.json", "fassade.json", "profile_generator.json", "profile_baender_zentral.json", "profile_baender_tuermchen.json", "profile_nord.json", "elemente.json"):
            shutil.copy(os.path.join(ROOT, "modelle", "martinstor", f), d)
        for p in glob.glob(os.path.join(ROOT, "modelle", "martinstor", "messprotokoll", "M-*.json")): shutil.copy(p, os.path.join(d, "messprotokoll"))
    for nm, link in (("synth_obj", "beweis_synth"), ("synth_basis", "beweis_synth_basis")):
        ln = os.path.join(ROOT, "modelle", link)
        if os.path.islink(ln): os.remove(ln)
        os.symlink(os.path.join(BA.BASIS, nm), ln)
    d = os.path.join(BA.BASIS, "synth_obj"); m = json.load(open(os.path.join(d, "masse.json")))
    for key, dv in WAHRHEIT_V[VARIANTE[0]].items():
        h = m["masse"][key]; h.setdefault("historie", []).append(dict(datum="2026-11-06", alt=h["wert"], neu=round(h["wert"] + dv, 3), grund="beweis_ansatz synthetische WAHRHEIT (verstellt)")); h["wert"] = round(h["wert"] + dv, 3)
    json.dump(m, open(os.path.join(d, "masse.json"), "w"), indent=1, ensure_ascii=False)
    f = json.load(open(os.path.join(d, "fassade.json")))
    for g in f["gruppen"]: g["oeffnungen"] = g["oeffnungen"][:-1]; g["beleg"]["anzahl"] = len(g["oeffnungen"])
    json.dump(f, open(os.path.join(d, "fassade.json"), "w"), indent=1, ensure_ascii=False)


def generator_bauen(objdir, name, aus_stl, masse_aend=None):
    """Generator mit OBJ_DIR=objdir; masse_aend {Name: neuer Wert} wird in eine Wegwerfkopie des Ordners geschrieben (Koordinatensuche)."""
    od = objdir
    if masse_aend:
        od = objdir + "_v_" + name; src = os.path.join(BA.BASIS, {"beweis_synth_basis": "synth_basis", "beweis_synth": "synth_obj"}[objdir]); dst = os.path.join(BA.BASIS, "synth_var_" + name)
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst); mm = json.load(open(os.path.join(dst, "masse.json")))
        for k, v in masse_aend.items(): mm["masse"][k]["wert"] = v
        json.dump(mm, open(os.path.join(dst, "masse.json"), "w")); od = "beweis_var_" + name; ln = os.path.join(ROOT, "modelle", od)
        if os.path.islink(ln): os.remove(ln)
        os.symlink(dst, ln)
    r = subprocess.run(["bash", "-c", f"OBJ_DIR={od} STL_NAME={od}_1-87.stl {GENERATOR}".replace("~", os.path.expanduser("~"))], cwd=ROOT, capture_output=True, text=True)
    src = os.path.join(ROOT, "modelle", "stl", f"{od}_1-87.stl")
    if r.returncode != 0 or not os.path.exists(src): raise SystemExit("Generator fehlgeschlagen: " + (r.stderr or r.stdout)[-500:])
    shutil.move(src, aus_stl)
    if masse_aend:
        os.remove(os.path.join(ROOT, "modelle", od)); shutil.rmtree(dst, ignore_errors=True)
    return aus_stl


def kameras_waehlen(n=10, rms_max=1.5):
    ld = os.path.join(ROOT, "modelle", "martinstor_lod2"); ok = []
    for p in sorted(glob.glob(os.path.join(ld, "messprotokoll", "K-*.json"))):
        kk = json.load(open(p)).get("kamera")
        if kk and kk.get("rms_px") is not None and kk["rms_px"] <= rms_max: ok.append(os.path.basename(p)[2:-5])
    return [ok[int(round(i))] for i in np.linspace(0, len(ok) - 1, n)], ok


def sichtbare_punkte(m, kams, n_punkte, min_kam, rauschen, seed=1):
    import trimesh
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    P, fi = trimesh.sample.sample_surface(m, n_punkte, seed=seed); P = np.asarray(P); N = m.face_normals[fi]; rmi = RayMeshIntersector(m); zahl = np.zeros(len(P), int)
    for (R, t, f, cx, cy, W, H) in kams:
        R = np.asarray(R); t = np.asarray(t, float); C = -R.T @ t; Xc = P @ R.T + t; z = Xc[:, 2]; u = f * Xc[:, 0] / np.maximum(z, 1e-6) + cx; v = f * Xc[:, 1] / np.maximum(z, 1e-6) + cy
        ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H) & (((C - P) * N).sum(1) > 0)
        idx = np.where(ok)[0]; sicht = np.zeros(len(P), bool)
        for i in range(0, len(idx), 200000):
            j = idx[i:i + 200000]; d = C - P[j]; dist = np.linalg.norm(d, axis=1); dirn = d / dist[:, None]
            o = P[j] + dirn * 0.02; hit = rmi.intersects_any(o, dirn); sicht[j] = ~hit
        zahl += sicht
    k = zahl >= min_kam; rng = np.random.default_rng(seed)
    return P[k] + rng.normal(0, rauschen, (int(k.sum()), 3)), N[k], zahl


def dom1_synth(m, n=80):
    """1-m-Zellmaxima der Wahrheit im Modellrahmen (Zeile 0 = groesstes y), Struktur wie BA.dom1_laden."""
    import trimesh
    P, _ = trimesh.sample.sample_surface(m, 3000000, seed=7); P = np.asarray(P); jj = np.floor(P[:, 0] + n / 2).astype(int); ii = np.floor(n / 2 - P[:, 1]).astype(int)
    ok = (ii >= 0) & (ii < n) & (jj >= 0) & (jj < n); Z = np.full(n * n, np.nan); tmp = np.full(n * n, -np.inf); np.maximum.at(tmp, ii[ok] * n + jj[ok], P[ok, 2]); Z = np.where(np.isfinite(tmp), tmp, np.nan).reshape(n, n)
    yy, xx = np.mgrid[:n, :n]; lx = -n / 2 + 0.5 + xx; ly = n / 2 - 0.5 - yy
    return dict(Z=Z, lx=lx, ly=ly, E=lx, N=ly, c0=np.zeros(2), xh=np.array([1.0, 0.0]), yh=np.array([0.0, 1.0]), obj={}, quelle="synthetisch (1-m-Zellmaxima der Wahrheit)")


def geometrie_gegen_wahrheit(wahr_stl, stl, n=100000):
    """Metrik 1: Flaeche-zu-Flaeche (beide Richtungen, 100k Stichproben je), m (Original 1:1). Fehleranteile > 3,5 cm / > 10 cm je Richtung und gemittelt."""
    import trimesh
    from scipy.spatial import cKDTree
    a = BA.stl_laden_m(wahr_stl, MASSSTAB); b = BA.stl_laden_m(stl, MASSSTAB)
    Pa, _ = trimesh.sample.sample_surface(a, n, seed=1); Pb, _ = trimesh.sample.sample_surface(b, n, seed=2)
    from trimesh.proximity import closest_point
    def dist(mesh, Q):                                                                        # Punkt-zu-FLAECHE (exakt); Punkt-zu-Punkt hat einen Abtastboden von ~8 cm bei 100k Punkten
        out = np.empty(len(Q))
        for i in range(0, len(Q), 20000): out[i:i + 20000] = np.linalg.norm(closest_point(mesh, Q[i:i + 20000])[0] - Q[i:i + 20000], axis=1)
        return out
    d_ab = dist(b, np.asarray(Pa)); d_ba = dist(a, np.asarray(Pb))                           # ab: Wahrheit-Punkte zur Verfahrensflaeche (fehlendes), ba: Verfahrenspunkte zur Wahrheit (erfundenes)
    f = lambda d: dict(mittel_m=round(float(d.mean()), 4), p95_m=round(float(np.percentile(d, 95)), 4), max_m=round(float(d.max()), 3), ueber_3_5cm=round(float((d > 0.035).mean()), 4), ueber_10cm=round(float((d > 0.10).mean()), 4))
    return dict(wahrheit_zu_verfahren=f(d_ab), verfahren_zu_wahrheit=f(d_ba), chamfer_m=round(float((d_ab.mean() + d_ba.mean()) / 2), 4), hausdorff_m=round(float(max(d_ab.max(), d_ba.max())), 3),
                ueber_3_5cm=round(float((np.mean(d_ab > 0.035) + np.mean(d_ba > 0.035)) / 2), 4), ueber_10cm=round(float((np.mean(d_ab > 0.10) + np.mean(d_ba > 0.10)) / 2), 4))


def main(a, aus, verf, schritte):
    import trimesh, cv2
    import fehlteile_finden as FF, test_foto_diff as TF
    t_ges = time.time(); ep = os.path.join(aus, "ergebnisse.json"); E = json.load(open(ep)) if os.path.exists(ep) else dict(objekt="synthetisch", verfahren={}, metriken={})
    ld = os.path.join(ROOT, "modelle", "martinstor_lod2", "objekt.json"); obj = json.load(open(ld)); root = ROOT
    k = dict(name="synthetisch", massstab=MASSSTAB, obj={}, od=aus, fd_objp=ld, pruef_objp=os.path.join(ROOT, "modelle", "martinstor", "objekt.json"))
    nrs, kand = kameras_waehlen(); fit = [nrs[i] for i in (0, 3, 6, 9)]; held = [x for x in nrs if x not in fit]
    E.update(kameras=nrs, anpassungsfotos=fit, zurueckgehaltene_fotos=held, kandidaten_kameras=kand, wahrheit_aenderung=dict(WAHRHEIT_V[VARIANTE[0]], fenster="je Gruppe das letzte Fenster entfernt", variante=VARIANTE[0]), suche=SUCHE)
    stls = E.setdefault("stl", {}); wahr = os.path.join(aus, "wahrheit_1-87.stl"); fd = os.path.join(aus, "fotos"); os.makedirs(fd, exist_ok=True)
    kam = {}
    for nr in nrs:
        kp = FF.k_datei(ld, obj, root, nr); K = json.load(open(kp)); kk = K["kamera"]; W, H = kk["bild"]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, root, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)); kam[nr] = (R, t, f, cx, cy, W, H, kk)
    if "bauen" in schritte:
        t0 = time.time(); synth_ordner(aus); generator_bauen("beweis_synth", "wahrheit", wahr); generator_bauen("beweis_synth_basis", "basis", os.path.join(aus, "basis_1-87.stl")); stls["W"] = wahr
        E["sekunden_wahrheit_bauen"] = round(time.time() - t0, 1)
        # Pruefbilder
        t0 = time.time(); m = BA.stl_laden_m(wahr, MASSSTAB); rng = np.random.default_rng(0); bilder = {}
        for nr in nrs:
            R, t, f, cx, cy, W, H, kk = kam[nr]; img = TF.foto_rendern(m, R, t, f, cx, cy, W, H, np.random.default_rng(int(nr)))
            bilder[nr] = os.path.join(fd, f"{nr}.jpg"); cv2.imwrite(bilder[nr], FF.foto_verzerren(img, kk), [cv2.IMWRITE_JPEG_QUALITY, 95]); print("  Pruefbild", nr, flush=True)
        E["bilder"] = bilder; E["sekunden_pruefbilder"] = round(time.time() - t0, 1)
        # Wolke
        t0 = time.time(); P, N, zahl = sichtbare_punkte(m, [kam[n][:7] for n in nrs], 1200000, 2, 0.05)
        E["wolke"] = dict(punkte=int(len(P)), sichtbar_ab_2_kameras_anteil=round(float((zahl >= 2).mean()), 3), rauschen_m=0.05, sekunden=round(time.time() - t0, 1)); np.savez_compressed(os.path.join(aus, "wolke_synth.npz"), P=P, N=N); print("  Wolke", E["wolke"], flush=True)
        D = dom1_synth(m); np.save(os.path.join(aus, "dom1_synth.npy"), D["Z"])
        lo, hi = m.bounds
        for v in verf:
            if v == "A": r = BA.poisson_aus_punkten(P, N, lo, hi, 3.0, aus, MASSSTAB); E["verfahren"]["A"] = r; stls["A"] = r["stl"]; print("  A:", {x: y for x, y in r.items() if x != "stl"}, flush=True)
            if v == "B": r = BA.verfahren_B_dom(k, D, aus); E["verfahren"]["B"] = r; stls["B"] = r["stl"]; print("  B:", {x: y for x, y in r.items() if x != "stl"}, flush=True)
            if v == "C":
                t0 = time.time(); st = os.path.join(aus, "basis_1-87.stl"); fest = {}; protokoll = []
                def kosten(stl, tag):
                    e = BA.foto_diff_lauf(k, fit, stl, os.path.join(aus, "suche", tag), a.cpu, bilder=E["bilder"], extra=["--tiefen", "aus"]); v_ = [x for x in e.values() if x]
                    return float(np.mean([x["rot"] + x["gelb"] for x in v_])) if v_ else 9.0
                bestk = kosten(st, "start"); protokoll.append(dict(schritt="start", kosten=round(bestk, 4)))
                for pn, deltas in SUCHE:
                    w0 = json.load(open(os.path.join(BA.BASIS, "synth_basis", "masse.json")))["masse"][pn]["wert"]; w0 = fest.get(pn, w0); beste = (bestk, w0)
                    for dv in deltas:
                        w = round(w0 + dv, 3); tag = f"{pn}_{w}"; stl = generator_bauen("beweis_synth_basis", tag, os.path.join(aus, "suche", f"{tag}.stl"), {**fest, pn: w}) if True else None
                        c = kosten(stl, tag); protokoll.append(dict(param=pn, wert=w, kosten=round(c, 4)))
                        if c < beste[0] - 0.01: beste = (c, w)                                        # Uebernahme nur bei Gewinn > 0,01 (ANNAHME, wie 'deutlich' im Laeufer)
                        os.remove(stl)
                    if beste[1] != w0: fest[pn] = beste[1]; bestk = beste[0]
                    print(f"  Suche {pn}: {w0} -> {fest.get(pn, w0)} (Kosten {bestk:.4f})", flush=True)
                stls["C"] = generator_bauen("beweis_synth_basis", "C", os.path.join(aus, "C_modell_1-87.stl"), fest or None) if fest else shutil.copy(st, os.path.join(aus, "C_modell_1-87.stl"))
                E["verfahren"]["C"] = dict(stl=stls["C"], fest=fest, protokoll=protokoll, kosten_start=protokoll[0]["kosten"], kosten_ende=round(bestk, 4), sekunden=round(time.time() - t0, 1), art="Generator Standardparameter + Koordinatensuche (4 Fotos)")
        json.dump(E, open(ep, "w"), indent=1, default=str)
    held_ = E["zurueckgehaltene_fotos"]; ergf = E["metriken"].setdefault("2_fotos", {})
    if "foto_diff" in schritte:
        for v in verf + ["W"]:
            if v in stls:
                print(f"Metrik 2: {v}", flush=True); ergf[v] = BA.foto_diff_lauf(k, held_, stls[v], os.path.join(aus, "foto_diff_" + v), a.cpu, bilder=E["bilder"], extra=["--tiefen", "aus"]); json.dump(E, open(ep, "w"), indent=1, default=str)
    if "m1" in schritte or "dach" in schritte:
        D = dom1_synth(BA.stl_laden_m(wahr, MASSSTAB))
        for v in verf + ["W"]:
            if v not in stls: continue
            E["metriken"].setdefault("1_geometrie", {})[v] = geometrie_gegen_wahrheit(wahr, stls[v])
            m = BA.stl_laden_m(stls[v], MASSSTAB); eigen, art = BA.eigener_grundriss(k, D); r, H = BA.dach_dom1(m, D, eigen); r["maske"] = art; E["metriken"].setdefault("3_dom1", {})[v] = r
            print(f"  {v}: M1 {E['metriken']['1_geometrie'][v]['chamfer_m']} m, Dach {r}", flush=True); json.dump(E, open(ep, "w"), indent=1, default=str)
    if "druck" in schritte:
        sk = min(1.0, 240.0 / max(max(trimesh.load(s).extents) for s in stls.values()))
        for v in verf + ["W"]:
            if v in stls: print(f"Metrik 5: {v}", flush=True); E["metriken"].setdefault("5_druck", {})[v] = BA.geometrie_druck(stls[v], MASSSTAB, aus=aus, skala_fuer_bett=sk); json.dump(E, open(ep, "w"), indent=1, default=str)
    if "blatt" in schritte and ergf:
        E["bildblatt"] = BA.bildblatt(k, aus, held_, ergf, verf + ["W"], os.path.join(ROOT, "modelle", "martinstor", "audit", "beweis_ansatz", "blatt_%s.jpg" % os.path.basename(aus))); print("Bildblatt:", E["bildblatt"])
    E["sekunden_gesamt_dieser_aufruf"] = round(time.time() - t_ges, 1); json.dump(E, open(ep, "w"), indent=1, default=str)

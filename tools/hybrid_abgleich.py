#!/usr/bin/env python3
"""hybrid_abgleich.py - Dachflaechen je QUELLE getrennt fitten (Strassenwolke, Drohnenwolke, Generator) und Abweichungen melden (Register BR/BS).

Hybrid-Idee des Nutzers: stimmt am Generator etwas nicht (Dachneigung), richtet er sich nach der Wolke; Quellen, die sich widersprechen, werden NICHT gemittelt (CLAUDE.md 5), sondern gemeldet.
Dies ist die messende Haelfte (Schritt 1: Dach). Je Dachseite (Nord -x, Sued +x, Ost +y, West -y) und je Quelle: Tiefenmodell d = d0 + k*z + c*v (d = Abstand entlang der Seitennormalen,
v = Querkoordinate), robust (RANSAC + Tukey-IRLS) im Mittelstreifen |v| < --streifen (Tuermchen/Nachbarn ausgeschlossen). Daraus Neigung gegen die Waagerechte theta = atan2(1, -k), Tiefenlage d(z_ref),
Unsicherheit per Bootstrap (Punkte mit Zuruecklegen). Widerspruch: |Differenz| > 3 sigma UND > --min-diff.
Drohnenpunkte: Clip-Baender, die video_merge.py als inkonsistent verwirft (audit/video_versatz.json, 'clips'), werden ausgeschlossen; Drift-Korrektur wie in video_merge.py (nur Nordseiten-Rahmen, x).
Blindheit (Regel 4): Wolken sehen steile Dachflaechen nur von ihrer Kameraseite; eine Seite ohne Punkte bleibt 'keine Daten' (kein Wert erfunden). Die Wolke sieht keine Nadel/Aufbauten.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/hybrid_abgleich.py modelle/<objekt>/objekt.json [--stl modelle/stl/martinstor_v4_1-87.stl] [--drohne <video_sfm/d1>]
Ausgabe: modelle/<objekt>/audit/hybrid_dach.json
"""
import sys, os, json, argparse, numpy as np

SEITEN = {"Nord(-x)": (-1.0, 0.0), "Sued(+x)": (1.0, 0.0), "Ost(+y)": (0.0, 1.0), "West(-y)": (0.0, -1.0)}

def koord(P, u):
    u = np.array(u); v = np.array([-u[1], u[0]]); return P[:, :2] @ u, P[:, :2] @ v, P[:, 2]

def tukey_fit(z, v, d, tol=0.25, it=30, seed=0):
    """d = d0 + k z + c v; RANSAC-Start, dann Tukey-IRLS. Gibt (d0, k, c, inlier_anteil) oder None."""
    if len(d) < 200: return None
    rng = np.random.default_rng(seed); A = np.c_[np.ones_like(z), z, v]; best = None
    for _ in range(400):
        i = rng.choice(len(d), 3, replace=False)
        try: p = np.linalg.solve(A[i], d[i])
        except np.linalg.LinAlgError: continue
        n = int((np.abs(A @ p - d) < tol).sum())
        if best is None or n > best[0]: best = (n, p)
    p = best[1]
    for _ in range(it):
        r = A @ p - d; s = max(1.4826 * np.median(np.abs(r)), 0.03); c = 4.685 * s; w = np.where(np.abs(r) < c, (1 - (r / c) ** 2) ** 2, 0.0)
        if w.sum() < 50: break
        W = np.sqrt(w)[:, None]; pn, *_ = np.linalg.lstsq(A * W, d * W[:, 0], rcond=None)
        if np.allclose(pn, p, atol=1e-6): p = pn; break
        p = pn
    return float(p[0]), float(p[1]), float(p[2]), float((np.abs(A @ p - d) < tol).mean())

def dachseite(P, u, zlo, zhi, streifen, zref, boot=30):
    d, v, z = koord(P, u); k = (z >= zlo) & (z <= zhi) & (np.abs(v) < streifen) & (d > 0.3)       # nur Punkte auf der AUSSENseite der Achse
    if k.sum() < 300: return dict(status="keine Daten", n=int(k.sum()))
    d, v, z = d[k], v[k], z[k]; f = tukey_fit(z, v, d)
    if f is None: return dict(status="keine Daten", n=int(k.sum()))
    rng = np.random.default_rng(1); th = []; dz = []
    for b in range(boot):
        i = rng.integers(0, len(d), len(d)); g = tukey_fit(z[i], v[i], d[i], seed=b)
        if g: th.append(np.degrees(np.arctan2(1, -g[1]))); dz.append(g[0] + g[1] * zref)
    d0, kk, c, anteil = f
    return dict(status="ok", n=int(k.sum()), neigung_grad=round(float(np.degrees(np.arctan2(1, -kk))), 2), neigung_sigma=round(float(np.std(th)), 2), tiefe_bei_zref_m=round(d0 + kk * zref, 3), tiefe_sigma=round(float(np.std(dz)), 3),
                quer_neigung=round(c, 3), inlier_anteil=round(anteil, 2))

def vergleich(a, b, min_diff_deg, min_diff_m):
    if a.get("status") != "ok" or b.get("status") != "ok": return None
    dth = a["neigung_grad"] - b["neigung_grad"]; sth = float(np.hypot(a["neigung_sigma"], b["neigung_sigma"])) or 0.05
    dd = a["tiefe_bei_zref_m"] - b["tiefe_bei_zref_m"]; sd = float(np.hypot(a["tiefe_sigma"], b["tiefe_sigma"])) or 0.01
    return dict(d_neigung_grad=round(dth, 2), d_tiefe_m=round(dd, 3), widerspruch_neigung=bool(abs(dth) > 3 * sth and abs(dth) > min_diff_deg), widerspruch_tiefe=bool(abs(dd) > 3 * sd and abs(dd) > min_diff_m))

def mesh_punkte(stl, einheit_zu_m, n=400000, seed=0):
    import trimesh
    m = trimesh.load(stl); m.apply_scale(einheit_zu_m); pts, _ = trimesh.sample.sample_surface(m, n, seed=seed); return np.asarray(pts, float)

def schicht_halbbreite(P, u, z, dz=0.5, streifen=1.8, vmax=6.5, minpts=150):
    """Halbbreite der Aussenflaeche in einer z-Schicht: Modus (0,1-m-Klassen, geglaettet) von d = P.u im Mittelstreifen; die Wolke ist die Oberflaeche, ihr dichtester Abstand ist die Flaeche."""
    d, v, zz = koord(P, u); k = (np.abs(zz - z) <= dz) & (np.abs(v) < streifen) & (d > 0.3) & (d < vmax)
    if k.sum() < minpts: return None
    h, e = np.histogram(d[k], bins=np.arange(0.3, vmax + 0.1, 0.1)); h = np.convolve(h, np.ones(3) / 3, mode="same"); i = int(np.argmax(h))
    return float(0.5 * (e[i] + e[i + 1])), int(k.sum()), float(h[i] / max(h.sum(), 1))

def pav_fallend(y, w):
    """Isotone Regression (Pool-Adjacent-Violators): Folge soll nach oben NICHT zunehmen (Helm wird nach oben schmaler); gewichtet nach Punktzahl."""
    bl = []
    for v, ww in zip(y, w):
        bl.append([v, ww, 1])
        while len(bl) > 1 and bl[-2][0] < bl[-1][0]:
            b2 = bl.pop(); b1 = bl.pop(); ws = b1[1] + b2[1]; bl.append([(b1[0] * b1[1] + b2[0] * b2[1]) / ws, ws, b1[2] + b2[2]])
    return [b[0] for b in bl for _ in range(b[2])]

def tuerm_maske(P, G, margin=0.35):
    """True fuer Punkte innerhalb der Ecktuermchen (Achse und Radius je Hoehe aus profile_generator.json: tuerm_achse, tuerm_profil, tuerm_kegel) - generisch, keine Handgrenzen."""
    ach = G.get("tuerm_achse"); prof = G.get("tuerm_profil"); kg = G.get("tuerm_kegel") or {}
    if not (ach and prof): return np.zeros(len(P), bool)
    zp = np.array([r[0] for r in prof]); dp = np.array([r[1] for r in prof]); st = kg.get("steigung_d_je_m", 0.44); zt = kg.get("spitze")
    d = np.interp(P[:, 2], zp, dp); hoch = P[:, 2] > zp[-1]; d[hoch] = np.maximum(dp[-1] - st * (P[hoch, 2] - zp[-1]), 0.0)
    if zt is not None: d[P[:, 2] > zt + 0.5] = 0.0
    r = 0.5 * d + margin; return (np.hypot(np.abs(P[:, 0]) - ach["tief"], np.abs(P[:, 1]) - ach["quer"]) < r) & (d > 0)

def silhouette_quer(P, z, dz=0.5, vmax=4.6, minpts=150):
    """Breite quer (E-W) der Nordflaeche in einer z-Schicht: p98 - p2 der y-Koordinaten (Punkte vor der Achse; Ecktuermchen vorher entfernt)."""
    k = (np.abs(P[:, 2] - z) <= dz) & (P[:, 0] < -0.2) & (P[:, 0] > -7) & (np.abs(P[:, 1]) < vmax)
    if k.sum() < minpts: return None
    y = P[k][:, 1]; return float(np.percentile(y, 98) - np.percentile(y, 2)), int(k.sum())

def segmentiert(z, y, w, kmax=3):
    """Stetige stueckweise lineare Regression mit automatischer Knotenzahl (0..kmax-1 Knoten, BIC) und Knotenlage (Gitter) - zweistufiger Helm ohne Handgrenzen."""
    import itertools
    best = None; n = len(z)
    for nk in range(0, kmax):
        for kn in itertools.combinations(range(2, n - 2), nk):
            if any(b - a < 3 for a, b in zip(kn, kn[1:])): continue
            X = np.c_[np.ones(n), z] if not kn else np.c_[np.ones(n), z, *[np.maximum(z - z[i], 0) for i in kn]]
            W = np.sqrt(w)[:, None]; beta, *_ = np.linalg.lstsq(X * W, y * W[:, 0], rcond=None); rss = float((w * (X @ beta - y) ** 2).sum() / w.mean())
            bic = n * np.log(max(rss / n, 1e-9)) + (2 + nk) * np.log(n)
            if best is None or bic < best[0]: best = (bic, kn, beta, rss)
    bic, kn, beta, rss = best; knoten = [float(z[i]) for i in kn]
    f = lambda zz: float(beta[0] + beta[1] * zz + sum(b * max(zz - k, 0) for b, k in zip(beta[2:], knoten)))
    return f, knoten, float(np.sqrt(rss / n))

def profil_schreiben(od, Pd, G_masse, dz_raster=0.5, minpts=150, rows=4, schreiben=True):
    """Querbreite des Helms (profile_generator.json 'dach_profil'/'dach_traufe'/'dach_oben') aus der Silhouette der Drohnenwolke (Register BU), generisch: Tuermchen ueber ihre Achsen maskiert, Knicke automatisch (BIC),
    Pruefzeilen automatisch (Toleranz aus Rest-RMS). Tiefe bleibt (offene Beobachtung: Foto-061-Silhouette 1,88 vs Wolken 1,23-1,4 bei z 48). Oberhalb der letzten belegten Schicht: Verlaengerung der letzten Geraden (ANNAHME)."""
    pf = os.path.join(od, "profile_generator.json"); G = json.load(open(pf)); alt = [list(r) for r in G["dach_profil"]]
    Pd = Pd[~tuerm_maske(Pd, G)]; z0 = float(G["dach_traufe"]["z"]) if G.get("dach_traufe") else alt[0][0]; z1 = alt[-1][0]
    zs = np.arange(z0, z1 + 0.01, dz_raster); w = [silhouette_quer(Pd, z, minpts=minpts) for z in zs]; ok = [i for i, x in enumerate(w) if x]
    if len(ok) < 8: raise SystemExit("zu wenige Silhouettenschichten")
    zz = zs[ok]; ww = np.array([w[i][0] for i in ok]); nn = np.array([w[i][1] for i in ok], float)
    d = np.diff(ww)[:len(ww) // 2]; ist = int(np.argmin(d)) + 1 if d.min() < -0.8 else 0                                # groesster Sprung nach unten = Fuss des Helms (Sockel darunter gehoert nicht zur Helmgeraden)
    dicht = nn >= 0.15 * np.median(nn)                                                                   # duenn belegte Schichten (Spitze) nicht fitten
    sel = (np.arange(len(zz)) >= ist) & dicht
    if sel.sum() < 8: raise SystemExit("zu wenige dichte Silhouettenschichten")
    zz, ww, nn = zz[sel], ww[sel], nn[sel]; f, knoten, rms = segmentiert(zz, ww, np.sqrt(nn))
    zlast = float(zz[-1]); print(f"Silhouette quer: {len(zz)} Schichten z {zz[0]:.1f}-{zlast:.1f} m, Knoten {['%.1f' % k for k in knoten]}, Rest-RMS {rms:.2f} m")
    def q(z): return max(f(min(z, zlast)) + ((f(zlast) - f(zlast - 1.0)) * (z - zlast) if z > zlast else 0.0), 0.1)
    G["dach_profil"] = [[z, t, round(q(z), 2) if z >= zz[0] else qq] for z, t, qq in alt]
    if G.get("dach_traufe"): G["dach_traufe"]["quer_alt"] = G["dach_traufe"].get("quer"); G["dach_traufe"]["quer"] = round(q(z0), 2); G["dach_traufe"]["quer_quelle"] = "Silhouette Drohnenwolke (Register BU)"
    zt = z1 + dz_raster if False else (G_masse.get("first") or z1); G["dach_oben"] = dict(quer=round(q(zt), 2), quelle="Verlaengerung der letzten Silhouettengeraden bis First %.1f m (ANNAHME, oberhalb z %.1f keine Schicht)" % (zt, zlast))
    G["quer_quelle"] = "tools/hybrid_abgleich.py --profil-schreiben: Silhouette Nordflaeche, Drohnenwolke clip-korrigiert, Tuermchen maskiert, %d Knoten (BIC), Rest-RMS %.2f m, Register BU" % (len(knoten), rms)
    if schreiben: json.dump(G, open(pf, "w"), indent=1, ensure_ascii=False)
    zr = list(np.linspace(zz[0] + 1.0, zlast - 0.5, rows)); tol = round(max(rms, 0.2), 2)
    return dict(profil_alt=alt, profil_neu=G["dach_profil"], knoten=knoten, rms=rms, tol=tol, zeilen=[(round(float(z), 1), round(f(z), 2)) for z in zr], zlast=zlast)

def pruefzeilen_schreiben(od, erg):
    """Pruefzeilen 'Helm Silhouette Nord: Breite quer bei z m (m)' (idempotent); bestehende Zeilen anderer Quellen bleiben unangetastet (Widerspruch = offene Beobachtung, Regel 5) neu setzen; frueherer Soll in historie."""
    mp = os.path.join(od, "masstabelle.json"); T = json.load(open(mp)); tol = erg["tol"]; q = "Register BU: Silhouette der Nordflaeche (p2-p98 y, Schicht +-0,5 m) der clip-korrigierten Drohnenwolke, Tuermchen maskiert, stueckweise linear (BIC); tools/hybrid_abgleich.py"
    T["pruefungen"] = [r for r in T["pruefungen"] if not r["name"].startswith("Helm Silhouette Nord:")]; T["messungen"] = {k: v for k, v in T["messungen"].items() if not k.startswith("helm_silhouette_")}
    def setze(name, wert, z, b):
        T["messungen"][wert] = {"typ": "ausdehnung_streifen", "z": z, "achse": "y", "quer_max": 4.6}; soll = [round(b - tol, 2), round(b + tol, 2)]
        for r in T["pruefungen"]:
            if r["name"] == name:
                if r["soll"] != soll: r.setdefault("historie", []).append({"datum": "auto", "alt_soll": r["soll"], "grund": "hybrid_abgleich.py: Silhouette der Drohnenwolke (Register BU)"})
                r["soll"] = soll; r["quelle"] = q; return
        T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=q, quelltyp="sfm_bodenanker", merkmal="schlankheit", massstab="LoD2-Eckkanten + Wandebene (Strassenwolke); Drohne daran gebunden"))
    for z, b in erg["zeilen"]: setze(f"Helm Silhouette Nord: Breite quer bei {z:.0f} m (m)", f"helm_silhouette_{int(round(z))}", z, b)
    json.dump(T, open(mp, "w"), indent=1, ensure_ascii=False)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--stl-faktor", type=float, default=87 / 1000.0, help="STL (mm, 1:87) -> Meter")
    ap.add_argument("--drohne", default="/media/oem/scan/rc-park_daten/martinstor/video_sfm/d1"); ap.add_argument("--zlo", type=float, default=42.0); ap.add_argument("--zhi", type=float, default=54.0)
    ap.add_argument("--zref", type=float, default=48.0); ap.add_argument("--streifen", type=float, default=2.5); ap.add_argument("--min-diff-grad", type=float, default=1.0); ap.add_argument("--min-diff-m", type=float, default=0.15); ap.add_argument("--ohne-rest", action="store_true"); ap.add_argument("--profil-schreiben", action="store_true", help="Querbreite des Helms in modelle/<objekt>/profile_generator.json aus der Drohnensilhouette ersetzen"); ap.add_argument("--ohne-korrektur", action="store_true"); ap.add_argument("--nur-pruefzeilen", action="store_true", help="mit --profil-schreiben: nur die Pruefzeilen setzen, Profil unveraendert (Regel 2: Test zuerst)"); ap.add_argument("--min-punkte", type=int, default=5000, help="Seite fuer das Profil nur ab dieser Punktzahl"); ap.add_argument("--profil", action="store_true", help="Dachprofil (z, tief, quer) aus den Drohnen-Ebenen nach audit/hybrid_dach_profil.json")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); sd = os.path.join(od, "sfm"); Q = {}
    nord = os.path.join(sd, "dicht_nord_entzerrt_ohnevideo.npy"); nord = nord if os.path.exists(nord) else os.path.join(sd, "dicht_nord_entzerrt.npy")
    if os.path.exists(nord): Q["strasse"] = np.load(nord).astype(float)
    dj = os.path.join(a.drohne, "dicht_modell.npy")
    dk = os.path.join(a.drohne, "dicht_korrigiert.npy")
    if os.path.exists(dk) and not a.ohne_korrektur:                                                  # von video_merge.py: Drift + bandweise Clip-Korrektur schon angewandt
        V = np.load(dk).astype(float); vw = os.path.join(a.drohne, "dicht_verworfen.npy"); ausg = 0
        if os.path.exists(vw): bad = np.load(vw); ausg = int(bad.sum()); V = V[~bad]
        vj0 = os.path.join(od, "audit", "video_versatz.json")
        if os.path.exists(vj0) and not a.ohne_rest: V += np.array(json.load(open(vj0)).get("verschiebung_m") or [0, 0, 0])
        Q["drohne"] = V; print(f"Drohnenpunkte {len(V)} (korrigiert von video_merge, verworfen {ausg})")
    elif os.path.exists(dj):
        V = np.load(dj).astype(float); wv = os.path.join(od, "audit", "wolke_vs_modell_nord.json"); drift = json.load(open(wv)).get("drift") if os.path.exists(wv) else None
        if drift: V[:, 0] += drift[0] * V[:, 2] + drift[1]
        vj0 = os.path.join(od, "audit", "video_versatz.json")
        if os.path.exists(vj0) and not a.ohne_rest: V += np.array(json.load(open(vj0)).get("verschiebung_m") or [0, 0, 0]); print("Rest-Verschiebung der Drohne (video_merge) angewandt")
        pc = os.path.join(a.drohne, "punkt_clips.npy"); vj = os.path.join(od, "audit", "video_versatz.json"); ausg = 0
        if os.path.exists(pc) and os.path.exists(vj):
            A_ = np.load(pc).astype(float); cn = json.load(open(os.path.join(a.drohne, "punkt_clips.json"))); fr = A_ / np.maximum(A_.sum(1, keepdims=True), 1); dom = fr.argmax(1); rein = fr.max(1) >= 0.8; bad = np.zeros(len(V), bool)
            for c in json.load(open(vj)).get("clips", []):
                if not c["ok"]: bad |= (dom == cn.index(c["clip"])) & rein & (V[:, 2] >= c["z"][0]) & (V[:, 2] < c["z"][1])
            ausg = int(bad.sum()); V = V[~bad]
        Q["drohne"] = V; print(f"Drohnenpunkte {len(V)} (inkonsistente Clip-Baender ausgeschlossen: {ausg})")
    if a.stl: Q["generator"] = mesh_punkte(a.stl, a.stl_faktor)
    out = dict(zref=a.zref, z=[a.zlo, a.zhi], streifen=a.streifen, quellen=list(Q), seiten={})
    print(f"{'Seite':9}{'Quelle':10}{'n':>7}{'Neigung':>10}{'+-':>6}{'Tiefe@%dm' % a.zref:>11}{'+-':>7}")
    for sn, u in SEITEN.items():
        R = {q: dachseite(P, u, a.zlo, a.zhi, a.streifen, a.zref) for q, P in Q.items()}; out["seiten"][sn] = dict(quellen=R, vergleiche={})
        for q, r in R.items():
            print(f"{sn:9}{q:10}{r['n']:7d}" + (f"{r['neigung_grad']:9.1f}°{r['neigung_sigma']:6.2f}{r['tiefe_bei_zref_m']:11.2f}{r['tiefe_sigma']:7.3f}" if r["status"] == "ok" else "   keine Daten"))
        for x, y in (("strasse", "drohne"), ("drohne", "generator"), ("strasse", "generator")):
            if x in R and y in R:
                c = vergleich(R[x], R[y], a.min_diff_grad, a.min_diff_m)
                if c: out["seiten"][sn]["vergleiche"][f"{x}-{y}"] = c; print(f"{'':9}{x}-{y}: dNeigung {c['d_neigung_grad']:+.1f}° dTiefe {c['d_tiefe_m']:+.2f} m" + ("  WIDERSPRUCH" if c["widerspruch_neigung"] or c["widerspruch_tiefe"] else ""))
    if a.profil and "drohne" in Q:
        Pd = Q["drohne"]; Pd = Pd[(np.abs(Pd[:, 0]) < 9) & (np.abs(Pd[:, 1]) < 9)]; lay2 = []; dicht = []
        for z in np.arange(41.0, 55.01, 1.0):
            n_ = schicht_halbbreite(Pd, SEITEN["Nord(-x)"], z); o_ = schicht_halbbreite(Pd, SEITEN["Ost(+y)"], z); w_ = schicht_halbbreite(Pd, SEITEN["West(-y)"], z)
            q = [x[0] for x in (o_, w_) if x]; lay2.append([round(float(z), 2), round(2 * n_[0], 2) if n_ else None, round(2 * float(np.mean(q)), 2) if q else None, [x[1] if x else 0 for x in (n_, o_, w_)]])
        for j, nm in ((1, "tief"), (2, "quer")):                                                 # isoton fallend, nur ueber vorhandene Schichten
            idx = [i for i, r in enumerate(lay2) if r[j] is not None]
            if len(idx) >= 3:
                glatt = pav_fallend([lay2[i][j] for i in idx], [max(lay2[i][3][0 if j == 1 else 1] + (lay2[i][3][2] if j == 2 else 0), 1) for i in idx])
                for i, g in zip(idx, glatt): lay2[i].append(round(float(g), 2)) if False else None
                for i, g in zip(idx, glatt): lay2[i][j] = round(float(g), 2)
        out["profil_schichten"] = dict(schichten=lay2, hinweis="[z, tief_voll (nur Nord, Gegenseite ANNAHME symmetrisch), quer_voll (Mittel Ost/West), Punkte N/O/W]")
        print("Schichtprofil (z, tief, quer):"); [print("  ", r[:3], r[3]) for r in lay2]
    if a.profil and "drohne" in Q:
        pass
    if a.profil and "drohne" in Q:
        def hz(sn):   # (d0 bei z=0 extrapoliert, k) der Drohnenebene; aus tiefe_bei_zref und Neigung
            r = out["seiten"][sn]["quellen"]["drohne"]
            if r.get("status") != "ok" or r["n"] < a.min_punkte: return None                    # dünne Seite (Drohne sieht den Sueden kaum): nicht verwenden
            k = -1.0 / np.tan(np.radians(r["neigung_grad"])); return r["tiefe_bei_zref_m"] - k * a.zref, k, r
        hx = [h for h in (hz("Nord(-x)"), hz("Sued(+x)")) if h]; hy = [h for h in (hz("Ost(+y)"), hz("West(-y)")) if h]
        if hx and hy:
            lay = []
            for z in np.arange(42.0, 55.01, 1.0):
                tx = float(np.mean([h[0] + h[1] * z for h in hx])); ty = float(np.mean([h[0] + h[1] * z for h in hy]))
                lay.append([round(float(z), 2), round(2 * max(tx, 0.15), 2), round(2 * max(ty, 0.15), 2)])
            streu = dict(tief=float(np.ptp([h[0] + h[1] * a.zref for h in hx])) if len(hx) > 1 else None, quer=float(np.ptp([h[0] + h[1] * a.zref for h in hy])) if len(hy) > 1 else None)
            out["profil"] = dict(dach_profil=lay, quelle="tools/hybrid_abgleich.py: Dachebenen der Drohnenwolke (Drift-Korrektur, Rest-ICP, inkonsistente Clip-Baender ausgeschlossen); Seiten ab --min-punkte, Gegenseite nur wenn belegt, sonst ANNAHME: symmetrisch zur belegten Seite", seiten_verwendet=dict(tief=len(hx), quer=len(hy)), seiten_streuung_m=streu,
                                 neigung_grad=dict(tief=[h[2]["neigung_grad"] for h in hx], quer=[h[2]["neigung_grad"] for h in hy]))
            print("Profil (z, tief, quer):", lay[::3], "Gegenseiten-Streuung (m):", streu)
    if a.profil_schreiben:
        mj = os.path.join(od, "masse.json"); gm = {"first": None}
        if os.path.exists(mj): M_ = json.load(open(mj))["masse"]; gm["first"] = M_["GZ1"]["wert"] + M_["DACHHOEHE"]["wert"] if "GZ1" in M_ and "DACHHOEHE" in M_ else None
        erg = profil_schreiben(od, Q["drohne"], gm, schreiben=not a.nur_pruefzeilen); print("Profil quer geschrieben:", [(o[0], o[2], n[2]) for o, n in zip(erg["profil_alt"][::4], erg["profil_neu"][::4])]); pruefzeilen_schreiben(od, erg); print("Pruefzeilen:", erg["zeilen"], "Toleranz +-", erg["tol"])
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(out, open(os.path.join(od, "audit", "hybrid_dach.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()

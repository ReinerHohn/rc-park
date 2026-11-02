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

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--stl-faktor", type=float, default=87 / 1000.0, help="STL (mm, 1:87) -> Meter")
    ap.add_argument("--drohne", default="/media/oem/scan/rc-park_daten/martinstor/video_sfm/d1"); ap.add_argument("--zlo", type=float, default=42.0); ap.add_argument("--zhi", type=float, default=54.0)
    ap.add_argument("--zref", type=float, default=48.0); ap.add_argument("--streifen", type=float, default=2.5); ap.add_argument("--min-diff-grad", type=float, default=1.0); ap.add_argument("--min-diff-m", type=float, default=0.15); ap.add_argument("--ohne-rest", action="store_true"); ap.add_argument("--min-punkte", type=int, default=5000, help="Seite fuer das Profil nur ab dieser Punktzahl"); ap.add_argument("--profil", action="store_true", help="Dachprofil (z, tief, quer) aus den Drohnen-Ebenen nach audit/hybrid_dach_profil.json")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); sd = os.path.join(od, "sfm"); Q = {}
    nord = os.path.join(sd, "dicht_nord_entzerrt_ohnevideo.npy"); nord = nord if os.path.exists(nord) else os.path.join(sd, "dicht_nord_entzerrt.npy")
    if os.path.exists(nord): Q["strasse"] = np.load(nord).astype(float)
    dj = os.path.join(a.drohne, "dicht_modell.npy")
    if os.path.exists(dj):
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
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); json.dump(out, open(os.path.join(od, "audit", "hybrid_dach.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()

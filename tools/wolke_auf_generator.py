#!/usr/bin/env python3
"""wolke_auf_generator.py - Hybrid: Form vom Generator-STL (LoD2/DOM1/Profile), Farbe + Belegung aus den dichten Bildpunkten (Register BW).

Warum: Poisson aus duennen Wolken zerreisst Tuermchen/Helm/Rueckseiten; der Generator ist immer vollstaendig, hat aber keine echten Farben.
Hier bleibt die GEOMETRIE des Generators; jede Flaeche bekommt die Farbe der naechsten gemessenen Punkte (Voxel-Mittel, keine Foto-Projektion),
Flaechen ohne Messpunkt im Radius bleiben neutral grau und zaehlen als NICHT BELEGT.
Gate je Seite (Wolke gegen Generator-Wandlage, d.h. gegen LoD2): Wandebene (Versatz, Neigung) wird robust angepasst und als Scherung korrigiert
(allgemeines Verfahren, keine Handwerte); Breite und Roll sind PRUEFUNGEN mit Toleranz (tol_*), die bei Ueberschreitung die Seite als 'abgelehnt' markieren
(ihre Punkte faerben dann nicht). ICP an den Generator ist bewusst NICHT Teil (Einwand-Wand = Maßstab/Roll unterbestimmt, Register BW).
  /media/oem/scan/venv-mesh/bin/python -I tools/wolke_auf_generator.py <wolke_entzerrt.npy> <ausgabe_ordner> [--stl modelle/stl/martinstor_v4_1-87.stl] [--massstab 87]
Ausgabe: farbig.ply, nur_belegt_anteile in bericht.json (je Seite/Hoehenband), npz fuer den Viewer (V,C,T,TN,belegt).
"""
import os, sys, json, argparse, numpy as np, open3d as o3d

SEITEN = {"Sued": (0, 1), "Nord": (0, -1), "Ost": (1, 1), "West": (1, -1)}   # (Achse, Vorzeichen) der Aussenflaeche

def wand_lage(Pm, ach, sg):
    """Wandebene des Generators: Median der Flaechenpunkte mit Normale zur Seite, z 18-30."""
    k = (Pm[:, 2] > 18) & (Pm[:, 2] < 30)
    return float(np.median(Pm[k, ach] * sg) ) * sg if k.sum() else None

def seiten_gate(P, ach, sg, wand, tol):
    """Messung der Wolke an der Seitenwand gegen die Generatorwand. Rueckgabe (Korrektur-Funktion, Bericht)."""
    q = 1 - ach
    k = (P[:, 2] > 18) & (P[:, 2] < 37) & (np.abs(P[:, ach] - wand) < 0.9) & (np.abs(P[:, q]) < 5.2)
    rep = dict(punkte_wand=int(k.sum()))
    if k.sum() < 2000:
        rep.update(status="zu duenn", benutzt=False); return None, rep
    Q = P[k]; d = Q[:, ach].copy()
    for it in range(4):   # robuste Wandebene d = a + b*z + c*q, Fenster verengt sich
        m = np.abs(Q[:, ach] - wand) < (0.9 - 0.15 * it)
        A = np.c_[np.ones(m.sum()), Q[m, 2], Q[m, q]]; co = np.linalg.lstsq(A, Q[m, ach], rcond=None)[0]
        Q[:, ach] -= (co[0] + co[1] * Q[:, 2] + co[2] * Q[:, q] - wand)
    korr = lambda X: _scher(X, ach, q, co, wand)
    # Pruefungen an der korrigierten Wand
    Pk = korr(P.copy()); kk = (Pk[:, 2] > 18) & (Pk[:, 2] < 37) & (np.abs(Pk[:, ach] - wand) < 0.6) & (np.abs(Pk[:, q]) < 7)
    br = []; mi = []; zs = []
    for z0 in range(18, 37, 3):
        s = kk & (Pk[:, 2] >= z0) & (Pk[:, 2] < z0 + 3)
        if s.sum() > 800:
            a, b = np.percentile(Pk[s, q], [4, 96]); br.append(b - a); mi.append((a + b) / 2); zs.append(z0 + 1.5)
    rep.update(ebene_koeff=[round(float(c), 4) for c in co], breite_m=[round(float(b), 1) for b in br])
    if len(zs) >= 3:
        sl = float(np.polyfit(zs, mi, 1)[0]); rep["lot_grad"] = round(float(np.degrees(np.arctan(sl))), 2)
    rep["breite_median_m"] = round(float(np.median(br)), 2) if br else None
    # Referenzbreite aus dem Generator (Wandbreite bei z 18-30)
    rep["pruef"] = {}
    ok = True
    # Breite per Perzentil ist abdeckungsabhaengig (Register BW) -> nur Bericht; Pruefung = Ueberstand ausserhalb Fussabdruck des Generators
    ue = []
    for z0 in range(15, 37, 3):
        s_ = (Pk[:, 2] >= z0) & (Pk[:, 2] < z0 + 3) & (np.abs(Pk[:, ach] - wand) < 0.9) & (np.abs(Pk[:, q]) < 9)
        if s_.sum() > 500: ue.append(round(float((np.abs(Pk[s_, q]) > tol["halbbreite_ref"] + 0.5).mean() * 100), 1))
    rep["ueberstand_prozent_baender"] = ue
    if ue: u_ok = max(ue[1:] or ue) <= tol["ueberstand_pct"]; rep["pruef"]["ueberstand"] = bool(u_ok); ok &= u_ok
    if "lot_grad" in rep:
        l_ok = abs(rep["lot_grad"]) <= tol["lot_grad"]; rep["pruef"]["lot"] = bool(l_ok); ok &= l_ok
    rep["benutzt"] = bool(ok); rep["status"] = "bestanden" if ok else "ABGELEHNT (Pruefung)"
    return korr, rep

def _scher(X, ach, q, co, wand):
    X[:, ach] -= (co[0] + co[1] * X[:, 2] + co[2] * X[:, q] - wand); return X

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("wolke"); ap.add_argument("aus")
    ap.add_argument("--stl", default="modelle/stl/martinstor_v4_1-87.stl"); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--radius", type=float, default=0.25, help="belegt, wenn Messpunkt innerhalb (m)"); ap.add_argument("--voxel", type=float, default=0.12)
    ap.add_argument("--fuell-voxel", type=float, default=0.6, help="Voxel fuer die Farbauffuellung nicht belegter Ecken (m)"); ap.add_argument("--kante", type=float, default=0.15, help="max Kantenlaenge nach Unterteilung (m)"); ap.add_argument("--tol-ueberstand", type=float, default=5.0); ap.add_argument("--tol-lot", type=float, default=1.5)
    ap.add_argument("--rand", type=float, default=0.5, help="Beschnitt: Fussabdruck + Rand (m)"); ap.add_argument("--streng", action="store_true", help="abgelehnte Seiten nicht verwenden"); ap.add_argument("--max-versatz", type=float, default=0.3, help="max Verschiebung der Generatorecken zur Wolke (m)"); ap.add_argument("--ohne-verfeinern", action="store_true")
    ap.add_argument("--ohne-seitengate", action="store_true", help="GENERISCH (2026-11-04): Wolke aus dem LoD2-Buendel (sfm_lod2_buendel.py) liegt schon im LoD2-System -> keine Scherung je Seite; "
                    "das Seitengate (Achsen/Hoehen des Martinstor-Turms) gilt nur fuer Netze ohne Buendel"); a = ap.parse_args()
    os.makedirs(a.aus, exist_ok=True)
    P = np.load(a.wolke).astype(np.float64); C = np.load(a.wolke.replace("_entzerrt.npy", "_farben.npy").replace("_modell.npy", "_farben.npy")).astype(np.float64)
    if C.max() > 1.5: C = C / 255.0
    m = o3d.io.read_triangle_mesh(a.stl); m.scale(a.massstab / 1000.0, center=(0, 0, 0)); m.compute_vertex_normals()
    ref = m.sample_points_uniformly(200000); Rp = np.asarray(ref.points); Rn = np.asarray(ref.normals)
    ber = dict(stl=a.stl, wolke=a.wolke, punkte=int(len(P)), seiten={}, seitengate=not a.ohne_seitengate)
    benutzt = np.ones(len(P), bool)
    for name, (ach, sg) in ({} if a.ohne_seitengate else SEITEN).items():
        s = (Rn[:, ach] * sg) > 0.8; kz = s & (Rp[:, 2] > 18) & (Rp[:, 2] < 30)
        if kz.sum() < 100: ber["seiten"][name] = dict(status="keine Wandflaeche im STL"); continue
        wand = float(np.median(Rp[kz, ach])); q = 1 - ach
        breite = float(np.percentile(Rp[kz, q], 97) - np.percentile(Rp[kz, q], 3))
        tol = dict(halbbreite_ref=float(np.percentile(np.abs(Rp[kz, q]), 99)), ueberstand_pct=a.tol_ueberstand, lot_grad=a.tol_lot)
        korr, rep = seiten_gate(P, ach, sg, wand, tol)
        rep.update(wand_generator=round(wand, 2), breite_generator_m=round(breite, 2)); ber["seiten"][name] = rep
        if korr is not None:
            # nur Punkte dieser Seite (Halbraum zur Aussenseite, ausserhalb Kern) werden verschoben
            hs = ((P[:, ach] * sg) > 2.5) & (np.abs(P[:, ach]) >= np.abs(P[:, 1 - ach]))   # Seite = dominante Achse (Ecken nicht doppelt)
            P[hs] = korr(P[hs].copy())          # Wandebene wird IMMER auf die Generatorwand geschert (robuster Fit, keine Handwerte)
            if not rep["benutzt"] and a.streng: benutzt &= ~hs
            # Beschnitt: Wandpunkte ausserhalb Generator-Fussabdruck + Rand (Strasse/Nachbarn) faerben/verfeinern nicht (Grenze je 3-m-Band AUS dem Generator)
            cut = np.zeros(len(P), bool)
            for z0 in range(0, 36, 3):      # nur Wandbereich; Dach/Helm (Fussabdruck schmaler) nie beschneiden
                g = (Rp[:, 2] >= z0) & (Rp[:, 2] < z0 + 3) & (np.sign(Rp[:, ach]) == sg) & (np.abs(Rp[:, ach]) > np.abs(Rp[:, q]))
                if g.sum() < 100: continue
                hq = float(np.percentile(np.abs(Rp[g, q]), 99)) + a.rand
                cut |= ((P[:, ach] * sg) > 2.5) & (P[:, 2] >= z0) & (P[:, 2] < z0 + 3) & (np.abs(P[:, q]) > hq) & (np.abs(P[:, ach] - wand) < 1.5)
            benutzt &= ~cut; rep["beschnitten_punkte"] = int(cut.sum())
        print(name, json.dumps({k: v for k, v in rep.items() if k != "breite_m"}))
    P, C = P[benutzt], C[benutzt]
    def farben_nachschlagen(P, C, v, V):
        """Voxel-Mittel der Farben (Kantenlaenge v); je Ecke naechstes belegtes Voxel in der 3x3x3-Nachbarschaft. Rueckgabe (Farbe, Abstand zum Voxelmittelpunkt, inf = kein Treffer)."""
        key = np.floor(P / v).astype(np.int64); uk, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel()
        cs = np.zeros((len(uk), 3)); np.add.at(cs, inv, C); cn = np.bincount(inv, minlength=len(uk)); cs /= cn[:, None]
        enc = lambda K: ((K[:, 0] + 5000) * 10007 + (K[:, 1] + 5000)) * 10007 + (K[:, 2] + 5000)
        ke = enc(uk); o = np.argsort(ke); ke = ke[o]; cs = cs[o]
        col = np.zeros((len(V), 3)); dist = np.full(len(V), np.inf); vk = np.floor(V / v).astype(np.int64)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    e = enc(vk + np.array([dx, dy, dz])); idx = np.clip(np.searchsorted(ke, e), 0, len(ke) - 1); hit = ke[idx] == e
                    d = np.linalg.norm(V - (vk + np.array([dx, dy, dz]) + 0.5) * v, axis=1); b = hit & (d < dist); col[b] = cs[idx[b]]; dist[b] = d[b]
        return col, dist
    import trimesh
    tm = trimesh.Trimesh(np.asarray(m.vertices), np.asarray(m.triangles), process=True); vv, ff = trimesh.remesh.subdivide_to_size(tm.vertices, tm.faces, max_edge=a.kante, max_iter=12)
    m = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(vv), o3d.utility.Vector3iVector(ff)); m.merge_close_vertices(1e-6); m.compute_vertex_normals(); V = np.asarray(m.vertices)
    v = a.voxel; key = np.floor(P / v).astype(np.int64)
    col, dist = farben_nachschlagen(P, C, v, V)
    bel0 = dist <= a.radius + v * 0.9
    # Auffuellen: Ecken ohne Messpunkt im Radius bekommen die Farbe aus groesserem Radius (~0,9 m), zaehlen aber NICHT als belegt
    col2, dist2 = farben_nachschlagen(P, C, a.fuell_voxel, V); fuell = (~bel0) & np.isfinite(dist2); col[fuell] = col2[fuell]
    grau = ~bel0 & ~fuell; col[grau] = np.array([0.62, 0.60, 0.57])
    bel = bel0
    ver = np.zeros(len(V))
    if not a.ohne_verfeinern:
        m.compute_vertex_normals(); N = np.asarray(m.vertex_normals)
        uk, inv = np.unique(key, axis=0, return_inverse=True); inv = inv.ravel(); cnt = np.bincount(inv, minlength=len(uk)); enc = lambda K: ((K[:, 0] + 5000) * 10007 + (K[:, 1] + 5000)) * 10007 + (K[:, 2] + 5000)
        cen_pos = np.zeros((len(uk), 3)); np.add.at(cen_pos, inv, P); cen_pos /= cnt[:, None]; ke = enc(uk); o = np.argsort(ke); ke = ke[o]; cnt = cnt[o]; cen_pos = cen_pos[o]; vk = np.floor(V / v).astype(np.int64)
        best = np.full(len(V), np.inf); cpos = np.zeros((len(V), 3)); ok = np.zeros(len(V), bool)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    e = enc(vk + np.array([dx, dy, dz])); idx = np.clip(np.searchsorted(ke, e), 0, len(ke) - 1); hit = (ke[idx] == e) & (cnt[idx] >= 5)
                    off = cen_pos[idx] - V; dn = np.abs((off * N).sum(1)); lat = np.linalg.norm(off - (off * N).sum(1)[:, None] * N, axis=1)
                    c = hit & (lat < 0.25) & (dn < best) & (dn <= 2 * a.max_versatz); best[c] = dn[c]; cpos[c] = cen_pos[idx[c]]; ok[c] = True
        d0 = np.where(ok, ((cpos - V) * N).sum(1), 0.0); d0 = np.clip(d0, -a.max_versatz, a.max_versatz)
        # Glaetten ueber Kanten (nur belegte Nachbarn gewichten)
        Tt = np.asarray(m.triangles); E = np.r_[Tt[:, [0, 1]], Tt[:, [1, 2]], Tt[:, [2, 0]]]; E = np.r_[E, E[:, ::-1]]; w = ok.astype(float); dd = d0.copy()
        for _ in range(6):
            num = np.zeros(len(V)); den = np.zeros(len(V)); np.add.at(num, E[:, 0], w[E[:, 1]] * dd[E[:, 1]]); np.add.at(den, E[:, 0], w[E[:, 1]])
            nn = np.where(den > 0, num / np.maximum(den, 1e-9), dd); dd = np.where(ok, 0.5 * dd + 0.5 * nn, dd)
        ver = dd; V = V + N * ver[:, None]; m.vertices = o3d.utility.Vector3dVector(V)
        ber["verfeinerung"] = dict(ecken_verschoben=int(ok.sum()), mittel_abs_m=round(float(np.abs(ver[ok]).mean()), 3) if ok.any() else 0, p95_abs_m=round(float(np.percentile(np.abs(ver[ok]), 95)), 3) if ok.any() else 0, max_versatz_m=a.max_versatz)
        print("Verfeinerung:", ber["verfeinerung"])
    m.vertex_colors = o3d.utility.Vector3dVector(col); o3d.io.write_triangle_mesh(os.path.join(a.aus, "farbig.ply"), m)
    m.compute_triangle_normals(); T = np.asarray(m.triangles)
    np.savez(os.path.join(a.aus, "viewer.npz"), V=V, C=col, T=T, TN=np.asarray(m.triangle_normals), belegt=bel)
    ber["ecken"] = int(len(V)); ber["belegt_anteil"] = round(float(bel.mean()), 3); ber["farbig_geschaetzt_anteil"] = round(float(fuell.mean()), 3); ber["grau_anteil"] = round(float(grau.mean()), 3); ber["baender"] = []
    for lo in range(0, 70, 10):
        kk = (V[:, 2] >= lo) & (V[:, 2] < lo + 10)
        if kk.sum() > 20: ber["baender"].append(dict(z=[lo, lo + 10], belegt=round(float(bel[kk].mean()), 3)))
    ber["tol"] = dict(ueberstand_pct=a.tol_ueberstand, lot_grad=a.tol_lot, belegt_radius_m=a.radius)
    json.dump(ber, open(os.path.join(a.aus, "bericht.json"), "w"), indent=1, ensure_ascii=False)
    print(f"Hybridnetz {len(V)} Ecken, belegt {bel.mean():.0%}")
    for b in ber["baender"]: print(f"  z {b['z'][0]:2d}-{b['z'][1]:2d} m: belegt {b['belegt']:.0%}")
    sys.exit(0 if all(s.get("benutzt", True) for s in ber["seiten"].values()) else 3)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""wolke_vs_modell.py - GENERISCH: dichte Fotowolke gegen Modell-STL, automatisch, je Fassadenseite (Register AN).

Statt Handmessungen: (1) Ausrichtungsversatz schaetzen (Wandebene des Schafts in Wolke und Modell, nur Verschiebung quer zur Fassade),
(2) Tiefenkarten der Fassade (Blick senkrecht auf die Seite): je Zelle (u, z) der vorderste Punkt der Wolke bzw. der erste Strahltreffer
im Modell, (3) Differenzkarte D = Wolke - Modell (positiv = Wirklichkeit hat dort mehr Masse / steht weiter vor), (4) Silhouette:
Zellen, in denen nur eines von beiden Masse hat, (5) zusammenhaengende Abweichungsflaechen -> automatische Beobachtungen in der
Masstabelle (auto_id, wie fehlteile_finden) + Bild audit/wolke_vs_modell_<seite>.png.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_vs_modell.py modelle/<objekt>/objekt.json <seite> [--raster 0.25]
        [--schwelle 0.4] [--min-flaeche 1.0] [--eintragen]
Seiten: Nord = Blick auf -x (u = y), Sued = +x, Ost = +y (u = x), West = -y. Masse in Metern; STL in mm 1:<stl_massstab>.
"""
import sys, os, json, argparse, numpy as np, trimesh, cv2
from scipy import ndimage

SEITE = {"nord": ("x", -1.0, "y"), "sued": ("x", 1.0, "y"), "ost": ("y", 1.0, "x"), "west": ("y", -1.0, "x")}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--raster", type=float, default=0.25)
    ap.add_argument("--schwelle", type=float, default=0.4); ap.add_argument("--min-flaeche", type=float, default=1.0); ap.add_argument("--eintragen", action="store_true")
    ap.add_argument("--schaft", nargs=2, type=float, default=[12.0, 26.0], help="Hoehenband mit senkrechter, glatter Wand fuer den Versatz")
    ap.add_argument("--dicht", help="npy der dichten Wolke (Standard sfm/dicht_<seite>_modell.npy)")
    ap.add_argument("--nebengebaeude", action="store_true", help="STLs aus objekt.json['nebengebaeude'] (Meter, Modellsystem) mit vergleichen; Raster deckt dann auch sie ab")
    ap.add_argument("--entzerren", action="store_true", help="Tiefendrift der einseitigen Wolke (linear in z, aus den Hoehenbaendern) abziehen; schreibt sfm/dicht_<seite>_entzerrt.npy - NUR fuer den Sichtvergleich, kein Mass")
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
    s = a.seite.lower(); tief, sgn, quer = SEITE[s]; it = 0 if tief == "x" else 1; iq = 1 - it
    P = np.load(os.path.join(od, a.dicht or f"sfm/dicht_{s}_modell.npy")).astype(float)
    m = trimesh.load(os.path.join(root, obj["stl"])); k = obj.get("stl_massstab", 87) / 1000.0; m.apply_scale(k)
    V = m.vertices                                           # Hauptbauwerk (fuer Versatz/Drift am Schaft)
    teile = [m]; u_lo, u_hi = -9.0, 9.0
    if a.nebengebaeude:
        for name, nb in obj.get("nebengebaeude", {}).items():
            mn = trimesh.load(os.path.join(root, nb["stl_m"])); teile.append(mn); print(f"Nebengebaeude {name}: {len(mn.faces)} Flaechen, Ausdehnung {mn.bounds.round(1).tolist()}")
        m = trimesh.util.concatenate(teile); b = m.bounds; u_lo, u_hi = float(np.floor(b[0, iq]) - 1), float(np.ceil(b[1, iq]) + 1)
    # Blickrichtung: wir sehen die Seite von aussen; "vorne" = groesstes sgn*tief
    front = lambda X: sgn * X[:, it]
    # ---- 1) Versatz quer zur Fassade am Schaft
    z0, z1 = a.schaft; kq = np.abs(P[:, iq]) < 2.5; kz = (P[:, 2] >= z0) & (P[:, 2] <= z1)
    kw = kq & kz & (front(P) > 2.0)
    wolke_wand = np.percentile(front(P[kw]), 95) if kw.sum() > 50 else np.nan
    kv = (np.abs(V[:, iq]) < 2.5) & (V[:, 2] >= z0) & (V[:, 2] <= z1)
    modell_wand = front(V[kv]).max() if kv.sum() else np.nan
    dv = wolke_wand - modell_wand
    print(f"Seite {s}: Wandlage am Schaft {z0}-{z1} m  Wolke {wolke_wand:.2f}  Modell {modell_wand:.2f}  -> Versatz {dv:+.2f} m (wird fuer den Vergleich abgezogen; Ursache Ausrichtungstiefe, siehe Register AN)")
    # Hoehenabhaengigkeit des Versatzes (einseitige Netze sind in der Tiefe weich): Wandlage je 4-m-Band an der Fassadenmitte
    baender = []
    for b0 in np.arange(6.0, 34.0, 4.0):
        kb = kq & (P[:, 2] >= b0) & (P[:, 2] < b0 + 4) & (front(P) > 2.0); kv2 = (np.abs(V[:, iq]) < 2.5) & (V[:, 2] >= b0) & (V[:, 2] < b0 + 4)
        if kb.sum() > 50 and kv2.sum(): baender.append((b0, float(np.percentile(front(P[kb]), 95) - front(V[kv2]).max())))
    spreiz = (max(v for _, v in baender) - min(v for _, v in baender)) if len(baender) > 1 else 0.0
    tiefe_unsicher = spreiz > 0.3
    drift = None
    if len(baender) >= 3:
        zb = np.array([b0 + 2.0 for b0, _ in baender]); vb = np.array([v for _, v in baender]); A_ = np.c_[zb, np.ones_like(zb)]; (m_, c_), *_ = np.linalg.lstsq(A_, vb, rcond=None)
        drift = (float(m_), float(c_)); print(f"Tiefendrift linear: {m_ * 1000:+.1f} mm je m Hoehe ({np.degrees(np.arctan(m_)):+.2f} Grad), Offset {c_:+.2f} m bei z 0; Rest-Streuung {np.std(vb - A_ @ np.r_[m_, c_]):.2f} m")
    print("Versatz je Hoehenband: " + ", ".join(f"{b0:.0f}-{b0 + 4:.0f} m: {v:+.2f}" for b0, v in baender) + f"  -> Spreizung {spreiz:.2f} m" + ("  !! TIEFE UNSICHER: Tiefendifferenzen nur als Hinweis, Silhouette/Hoehen bleiben gueltig" if tiefe_unsicher else ""))
    Pk = P.copy()
    if a.entzerren and drift:
        Pk[:, it] -= sgn * (drift[0] * Pk[:, 2] + drift[1]); dv_rest = 0.0
        np.save(os.path.join(od, "sfm", f"dicht_{s}_entzerrt.npy"), Pk.astype(np.float32)); print(f"entzerrte Wolke geschrieben: sfm/dicht_{s}_entzerrt.npy (Drift {drift[0]*1000:+.1f} mm/m, Offset {drift[1]:+.2f} m abgezogen) - Sichtvergleich, KEIN Mass")
    else: Pk[:, it] -= sgn * dv
    # ---- 2) Tiefenkarten
    r = a.raster; us = np.arange(u_lo, u_hi + 1e-9, r); zs = np.arange(0.0, 72.0 + 1e-9, r); U, Z = np.meshgrid(us, zs)
    iu = np.floor((Pk[:, iq] - u_lo) / r).astype(int); iz = np.floor(Pk[:, 2] / r).astype(int); ok = (iu >= 0) & (iu < len(us)) & (iz >= 0) & (iz < len(zs))
    W = np.full(U.shape, np.nan); N = np.zeros(U.shape, int)
    f = front(Pk)
    for a_, b_, c_ in zip(iz[ok], iu[ok], f[ok]):
        N[a_, b_] += 1
        if np.isnan(W[a_, b_]) or c_ > W[a_, b_]: W[a_, b_] = c_
    W[N < 3] = np.nan
    # Modell: Strahlen von aussen (sgn*tief = +60) nach innen
    org = np.zeros((U.size, 3)); org[:, it] = sgn * 60.0; org[:, iq] = U.ravel(); org[:, 2] = Z.ravel()
    drc = np.zeros_like(org); drc[:, it] = -sgn
    loc, idx_ray, _ = m.ray.intersects_location(org, drc, multiple_hits=False)
    Mo = np.full(U.size, np.nan); Mo[idx_ray] = sgn * loc[:, it]; Mo = Mo.reshape(U.shape)
    # ---- 3) Differenz und Silhouette
    D = W - Mo; beide = ~np.isnan(W) & ~np.isnan(Mo)
    nur_wolke = ~np.isnan(W) & np.isnan(Mo)           # Wirklichkeit hat Masse, Modell nicht (fehlt)
    nur_modell = np.isnan(W) & ~np.isnan(Mo)          # Modell hat Masse, Wolke nicht (koennte erfunden sein ODER nur nicht fotografiert)
    # nur_modell nur werten, wo die Wolke in der Umgebung Daten hat (sonst fehlt schlicht die Abdeckung)
    hat = ~np.isnan(W); umgeb = ndimage.binary_dilation(hat, iterations=int(1.0 / r)) & ~hat
    # 'nur Modell' zaehlt nur am RAND der Wolkensilhouette (Modell ragt ueber die Wirklichkeit hinaus); Loecher MITTEN in der Wolke sind
    # Abdeckungsluecken (dunkle Fassade, Verdeckung), kein Modellfehler
    hintergrund = np.isnan(W) & np.isnan(Mo); rand = ndimage.binary_dilation(hintergrund, iterations=int(1.0 / r))
    nur_modell_sicher = nur_modell & umgeb & rand
    nur_modell_loch = nur_modell & umgeb & ~rand
    print(f"'nur Modell' innerhalb der Wolke (Abdeckungsluecke, ignoriert): {nur_modell_loch.sum()} Zellen")
    print(f"Zellen: beide {beide.sum()}, nur Wolke {nur_wolke.sum()}, nur Modell (mit Wolken-Umgebung) {nur_modell_sicher.sum()}; mittlere Tiefendifferenz {np.nanmean(D[beide]):+.2f} m, Streuung {np.nanstd(D[beide]):.2f}")
    # ---- 4) Flaechen finden
    befunde = []
    def flaechen(mask, art, wert=None):
        lab, n = ndimage.label(mask)
        for i in range(1, n + 1):
            cells = lab == i; A = cells.sum() * r * r
            if A < a.min_flaeche: continue
            zz = Z[cells]; uu = U[cells]; mw = float(np.nanmean(wert[cells])) if wert is not None else None
            befunde.append(dict(art=art, flaeche_m2=round(float(A), 1), z_von=round(float(zz.min()), 1), z_bis=round(float(zz.max()), 1), u_von=round(float(uu.min()), 1), u_bis=round(float(uu.max()), 1), tiefe_diff=(round(mw, 2) if mw is not None else None)))
    flaechen(beide & (D > a.schwelle), "wirklichkeit_weiter_vorn", D)
    flaechen(beide & (D < -a.schwelle), "modell_weiter_vorn", D)
    flaechen(nur_wolke, "fehlt_im_modell"); flaechen(nur_modell_sicher, "nur_im_modell")
    befunde.sort(key=lambda b: -b["flaeche_m2"])
    print(f"\nBefunde (>= {a.min_flaeche} m2, |D| > {a.schwelle} m), Seite {s}, u = {quer}:")
    for b in befunde[:25]:
        print(f"  {b['art']:24s} {b['flaeche_m2']:6.1f} m2  z {b['z_von']:5.1f}..{b['z_bis']:5.1f}  {quer} {b['u_von']:5.1f}..{b['u_bis']:5.1f}" + (f"  D {b['tiefe_diff']:+.2f} m" if b['tiefe_diff'] is not None else ""))
    # ---- 5) Bild
    def karte(A, vmin, vmax, cmap):
        img = np.full(A.shape, np.nan); img[:] = A; n = np.isnan(img); x = np.clip((img - vmin) / (vmax - vmin + 1e-9), 0, 1); x[n] = 0
        c = cv2.applyColorMap((x * 255).astype(np.uint8), cmap); c[n] = (40, 40, 40); return cv2.flip(c, 0)
    lo = np.nanmin(np.r_[W[beide], Mo[beide]]) if beide.any() else 0; hi = np.nanmax(np.r_[W[beide], Mo[beide]]) if beide.any() else 1
    panels = [karte(W, lo, hi, cv2.COLORMAP_VIRIDIS), karte(Mo, lo, hi, cv2.COLORMAP_VIRIDIS), karte(np.where(beide, D, np.nan), -1.5, 1.5, cv2.COLORMAP_JET)]
    sil = np.zeros(U.shape + (3,), np.uint8); sil[beide] = (120, 120, 120); sil[nur_wolke] = (0, 200, 255); sil[nur_modell_sicher] = (255, 80, 255); panels.append(cv2.flip(sil, 0))
    sc = max(1, int(900 / U.shape[0])); panels = [cv2.resize(p, None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST) for p in panels]
    for p, t in zip(panels, ("Wolke: Tiefe", "Modell: Tiefe", "Differenz Wolke-Modell (+-1,5 m, rot = Wirklichkeit vorn)", "Silhouette: gelb fehlt im Modell, magenta nur im Modell")):
        cv2.putText(p, t, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    out = np.hstack(panels); os.makedirs(os.path.join(od, "audit"), exist_ok=True); bild = os.path.join(od, "audit", f"wolke_vs_modell_{s}.png"); cv2.imwrite(bild, out)
    json.dump(dict(seite=s, versatz_m=float(dv), versatz_baender=baender, tiefe_unsicher=bool(tiefe_unsicher), drift=drift, entzerrt=bool(a.entzerren and drift), raster=r, befunde=befunde, n_beide=int(beide.sum())), open(os.path.join(od, "audit", f"wolke_vs_modell_{s}.json"), "w"), indent=1, ensure_ascii=False)
    print("Bild:", bild)
    # ---- 6) Beobachtungen eintragen (auto_id, idempotent)
    if a.eintragen:
        tp = os.path.join(od, "masstabelle.json"); T = json.load(open(tp)); vorhanden = {b.get("auto_id") for b in T["beobachtungen_offen"]}; neu = 0
        for b in befunde[:12]:
            aid = f"wolke-{s}-{b['art']}-{int(b['z_von'])}-{int(b['u_von'])}"
            if aid in vorhanden: continue
            d = b["tiefe_diff"] or 0.0
            txt = {"wirklichkeit_weiter_vorn": f"Fotowolke steht {d:+.2f} m weiter vor als das Modell", "modell_weiter_vorn": f"Modell steht {-d:.2f} m weiter vor als die Fotowolke",
                   "fehlt_im_modell": "Fotowolke hat hier Masse, das Modell nicht (fehlendes Bauteil?)", "nur_im_modell": "Modell hat hier Masse, die Fotowolke (mit Daten ringsum) nicht (zu grosses/erfundenes Bauteil?)"}[b["art"]]
            if tiefe_unsicher and b["art"] in ("wirklichkeit_weiter_vorn", "modell_weiter_vorn"): txt += " [TIEFE UNSICHER: einseitiges Netz, Versatz je Hoehe %.2f m Spreizung - nur Hinweis]" % spreiz
            T["beobachtungen_offen"].append(dict(datum="auto", wer=f"wolke_vs_modell ({s}, Versatz {dv:+.2f} m abgezogen)", auto_id=aid, art="wolke_vs_modell", seite=s, z_von=b["z_von"], z_bis=b["z_bis"], quer_von=b["u_von"], quer_bis=b["u_bis"], flaeche_m2=b["flaeche_m2"],
                                                 text=f"{txt}: z {b['z_von']}-{b['z_bis']} m, {quer} {b['u_von']}..{b['u_bis']} m, {b['flaeche_m2']} m2", naechster_schritt="Im Bild audit/wolke_vs_modell_<seite>.png und im Viewer ansehen; wenn echt: Mass bestimmen, Pruefung eintragen, Generator")); neu += 1
        json.dump(T, open(tp, "w"), indent=1, ensure_ascii=False); print(f"{neu} neue Beobachtungen eingetragen")

if __name__ == "__main__":
    main()

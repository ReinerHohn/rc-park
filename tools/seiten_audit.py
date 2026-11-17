#!/usr/bin/env python3
"""seiten_audit.py - PFLICHT-SICHTBLATT nach jedem Bau (Mechanik fuer Lehre F5/F6: vollstaendiger Mehrflaechen-Audit, nie nur eine Seite).

Erzeugt modelle/<objekt>/audit/seiten.jpg: vier Ansichten (Sued, Nord, Ost, West, orthografisch, schattiert) + Draufsicht,
darunter je verfuegbarem Foto mit bekannter Seite das Paar Foto | Modell aus der angepassten Kamera (kameras.json der gemeinsamen Anpassung).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/seiten_audit.py modelle/<objekt>/objekt.json
Das Blatt wird nicht bewertet - es muss ANGESEHEN werden (CLAUDE.md Regel 3). Jede Seite, die nur als Annahme existiert, ist hier sichtbar.
"""
import sys, os, json, glob, math, numpy as np, cv2, trimesh
SIL_F0 = 5.4 / 4.29   # Brennweitenfaktor der Silhouettenkamera (foto_silhouette_gpu); je Objekt in objekt.json ueberschreibbar

def lade(obj, root):
    m = trimesh.load(os.path.join(root, obj["stl"]))
    if obj.get("stl_einheit_mm", True): m.apply_scale(obj.get("stl_massstab", 1) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]]); return m

def ortho_schnell(sz, P, N, view, hoehe=900, netz=None):
    """Orthografisch ueber den gemeinsamen Renderkern: Kamera weit weg + passende Brennweite (perspektivischer Fehler < 0,5 %)."""
    import render_kern as RK
    d, r, u = [np.array(v, float) for v in view]
    mit = P.mean(0); ausd = max(P @ r.max() - P @ r.min(), P @ u.max() - P @ u.min()) if False else max(np.ptp(P @ r), np.ptp(P @ u))
    D = 4000.0; cam = mit - d * D                                    # Blickrichtung d zeigt VOM Betrachter weg
    R = np.vstack([r, -u, d]); t = -R @ cam
    s_ = (hoehe - 20) / ausd; f = D * s_
    W = int(np.ptp(P @ r) * s_) + 20; H = hoehe
    if netz is not None:                                             # 17.11.2026: Dreiecke exakt rastern. Die Punktabtastung (2,5 Mio. Punkte) liess bei hohlen Modellen mit Relief (4 Mio. Dreiecke) die Innenwaende durchscheinen = Pixel-Pfeffer im Sichtblatt
        try:
            _, fid, _ = [np.asarray(v_) for v_ in RK.dreiecke_rastern(netz, R, t, f, W / 2, H / 2, W, H)]; img = np.full((H, W), 235, np.uint8); tr = fid >= 0
            lit = np.clip(np.asarray(netz.face_normals) @ np.array([0.35, -0.45, 0.82]), 0, 1); img[tr] = (70 + 170 * (0.25 + 0.75 * lit[fid[tr]])).astype(np.uint8); return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        except Exception as e: print("  Dreiecksraster nicht moeglich (", str(e)[:80], ") - Punktbild")
    img, _ = sz.schattiert_np(R, t, f, W / 2, H / 2, W, H)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

def ortho(P, N, view, hoehe=900):
    """Orthografische Ansicht: view = (Blickrichtung, Rechts-Vektor, Oben-Vektor)."""
    d, r, u = [np.array(v, float) for v in view]
    x = P @ r; y = P @ u; depth = P @ d
    x0, x1, y0, y1 = x.min(), x.max(), y.min(), y.max(); s = (hoehe - 20) / max(y1 - y0, x1 - x0)
    W = int((x1 - x0) * s) + 20; H = int((y1 - y0) * s) + 20
    px = ((x - x0) * s + 10).astype(int); py = (H - 10 - (y - y0) * s).astype(int)
    lit = np.clip(N @ np.array([0.35, -0.45, 0.82]), 0, 1); back = (N @ d) > 0.2          # Rueckseiten unterdruecken
    shade = (70 + 170 * (0.25 + 0.75 * lit)).astype(np.uint8); shade[back] = 0
    img = np.full((H, W), 238, np.uint8); zb = np.full((H, W), -1e9)
    order = np.argsort(depth)                                                                 # nah zuletzt
    for i in order:
        if back[i]: continue
        if depth[i] > zb[py[i], px[i]]:
            zb[py[i], px[i]] = depth[i]; img[max(0, py[i] - 1):py[i] + 1, max(0, px[i] - 1):px[i] + 1] = shade[i]
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

VIEWS = {"Sued (+x)": ((-1, 0, 0), (0, 1, 0), (0, 0, 1)), "Nord (-x)": ((1, 0, 0), (0, -1, 0), (0, 0, 1)),
         "Ost (+y)": ((0, -1, 0), (-1, 0, 0), (0, 0, 1)), "West (-y)": ((0, 1, 0), (1, 0, 0), (0, 0, 1)), "Draufsicht": ((0, 0, -1), (0, 1, 0), (-1, 0, 0))}

PARAM = ["d", "az", "el", "tz", "ro", "fs", "sx", "sy"]     # Reihenfolge von kameras.json["th"] (foto_silhouette_gpu / foto_profil_gpu)

def grenz_check(th, lo, hi, tol, nur=None):
    """M4 (Plan): Sitzt ein Optimierer-Parameter an der Suchschranke (innerhalb tol * Spanne), ist die Anpassung dort GESCHEITERT (Beispiel 3.11.: sx = -120 bei
    Foto 022/040 schob das Modell aus dem Bild). Rueckgabe: Liste (Name, Wert, 'unten'|'oben'). ANNAHME: tol = 2 % der Spanne (Argument --grenze-tol)."""
    out = []
    for i, nm in enumerate(PARAM):
        if nur is not None and i not in nur: continue
        sp = float(hi[i] - lo[i])
        if sp <= 0: continue
        if th[i] <= lo[i] + tol * sp: out.append((nm, float(th[i]), "unten"))
        elif th[i] >= hi[i] - tol * sp: out.append((nm, float(th[i]), "oben"))
    return out

def main():
    GRENZ_TOL = float(sys.argv[sys.argv.index('--grenze-tol') + 1]) if '--grenze-tol' in sys.argv else 0.02; unsicher = {}
    objp = sys.argv[1]; obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    out = os.path.join(root, obj.get("audit", os.path.join(os.path.dirname(obj["masstabelle"]), "audit"))); os.makedirs(out, exist_ok=True)
    m = lade(obj, root); P, fi = trimesh.sample.sample_surface(m, 2500000, seed=0); P = np.asarray(P); N = m.face_normals[fi]
    sys.path.insert(0, os.path.join(root, "tools")); import render_kern as RK
    sz = RK.Szene(P, N); print(f"  Renderkern: {RK.geraet()}")
    tiles = []
    sk = obj.get("seiten_konvention", {})                                                     # Himmelsrichtung je Achse aus objekt.json (nicht Martinstor-fest)
    for name, view in VIEWS.items():
        ax = name[name.find("(") + 1:name.find(")")] if "(" in name else None
        if ax in sk: name = f"{str(sk[ax]).split()[0]} ({ax})"
        im = ortho_schnell(sz, P, N, view, netz=m); cv2.putText(im, name, (8, 26), 0, 0.8, (0, 0, 200), 2); tiles.append(im)
    H = max(t.shape[0] for t in tiles); row1 = np.hstack([cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles])
    # Foto | Render je Foto mit bekannter Seite und Kamera
    kam = {}
    for kp in glob.glob(os.path.join(root, "modelle", "foto_silhouette", "*kameras.json")): kam.update(json.load(open(kp)))
    sys.path.insert(0, os.path.join(root, "tools")); os.environ.setdefault("OBJEKT", os.path.abspath(objp))
    pairs = []
    try:
        import foto_silhouette_gpu as F, foto_profil_gpu as PG
        for nr, cfg in sorted(obj.get("fotos", {}).items()):
            if cfg.get("seite") in (None, "unbekannt") or nr not in kam: continue
            fn = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))
            if not fn: continue
            im = cv2.imread(fn[0]); h, w = im.shape[:2]; s = 700 / h; W2, H2 = int(w * s), 700; im = cv2.resize(im, (W2, H2)); k = W2 / 400.
            t = np.array(kam[nr]["th"], float)
            try:
                if "grenzen" in kam[nr]: lo_, hi_ = np.array(kam[nr]["grenzen"][0]), np.array(kam[nr]["grenzen"][1]); nur = None      # gespeicherte Schranken dieser Anpassung (alle Parameter)
                else: lo_, hi_ = PG.lo.cpu().numpy(), PG.hi.cpu().numpy(); nur = [i for i, n_ in enumerate(PARAM) if n_ != "az"]       # aeltere kameras.json: Azimut-Schranke unbekannt/zyklisch -> nicht geprueft
                gc = grenz_check(t, lo_, hi_, GRENZ_TOL, nur)
            except Exception as e:
                gc = []; print("   Grenzpruefung nicht moeglich:", e)
            if gc: unsicher[nr] = dict(seite=cfg.get("seite"), an_grenze=[dict(parameter=a, wert=round(b, 3), seite=c) for a, b, c in gc], th=[float(x) for x in t])
            t[6] *= k; t[7] *= k
            cam = np.array([0, 0, t[3]]) + t[0] * np.array([math.sin(t[1]) * math.cos(t[2]), -math.cos(t[1]) * math.cos(t[2]), math.sin(t[2])])
            fw = np.array([0, 0, t[3]]) - cam; fw /= np.linalg.norm(fw); rt = np.cross(fw, [0, 0, 1.0]); rt /= np.linalg.norm(rt); dn = np.cross(fw, rt)
            cr, sr = math.cos(t[4]), math.sin(t[4]); Rm = np.vstack([cr * rt + sr * dn, -sr * rt + cr * dn, fw]); tm = -Rm @ cam
            img, _ = sz.schattiert_np(Rm, tm, SIL_F0 * 400 * k * t[5], W2 / 2 + t[6], H2 / 2 + t[7], W2, H2, hintergrund=238)
            r = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if nr in unsicher:      # Kamera unsicher: Render NICHT als Beleg zeigen (er waere irrefuehrend), sondern Hinweis
                r = np.full_like(r, 200); txt = ", ".join(f"{d['parameter']}={d['wert']} ({d['seite']})" for d in unsicher[nr]["an_grenze"])
                cv2.putText(r, "KAMERA UNSICHER", (12, 60), 0, 1.0, (0, 0, 200), 3); cv2.putText(r, "Optimierer an der Schranke:", (12, 100), 0, 0.6, (0, 0, 200), 2); cv2.putText(r, txt[:60], (12, 130), 0, 0.6, (0, 0, 200), 2)
            pair = np.hstack([im, r]); cv2.putText(pair, f"Foto {nr} ({cfg['seite']})" + (" - KAMERA UNSICHER" if nr in unsicher else ""), (8, 26), 0, 0.8, (0, 0, 200), 2); pairs.append(pair)
    except Exception as e:
        print("Foto-Paare uebersprungen:", e)
    sheet = row1
    if pairs:
        Wmax = max(row1.shape[1], sum(p.shape[1] + 6 for p in pairs))
        rows, cur, acc = [], [], 0
        for p in pairs:
            if acc + p.shape[1] > max(row1.shape[1], 3200) and cur: rows.append(cur); cur, acc = [], 0
            cur.append(p); acc += p.shape[1] + 6
        rows.append(cur)
        for rw in rows:
            line = np.hstack([cv2.copyMakeBorder(p, 0, 0, 0, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for p in rw])
            Wn = max(sheet.shape[1], line.shape[1])
            sheet = cv2.copyMakeBorder(sheet, 0, 0, 0, Wn - sheet.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
            line = cv2.copyMakeBorder(line, 0, 0, 0, Wn - line.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
            sheet = np.vstack([sheet, np.full((8, Wn, 3), 255, np.uint8), line])
    fn = os.path.join(out, "seiten.jpg"); cv2.imwrite(fn, sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"ANSEHEN: {fn}  ({len(VIEWS)} Ansichten, {len(pairs)} Foto-Paare)")
    bp = os.path.join(out, "kamera_grenzen.json"); json.dump(dict(grenze_tol=GRENZ_TOL, unsicher=unsicher, hinweis="Optimierer-Parameter an der Suchschranke = Anpassung gescheitert; Foto im Sichtblatt als KAMERA UNSICHER markiert, nicht als Beleg verwenden"), open(bp, "w"), indent=1, ensure_ascii=False)
    print(f"Kamerapruefung: {len(unsicher)} Foto(s) mit Parameter an der Schranke: {sorted(unsicher)} -> {bp}")

if __name__ == "__main__":
    main()

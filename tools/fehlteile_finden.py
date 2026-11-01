#!/usr/bin/env python3
"""fehlteile_finden.py - AUTOMATISCH finden, wo das Foto Struktur zeigt, die das Modell nicht hat (und umgekehrt).

Mit der kalibrierten Kamera eines Fotos (K-<foto>.json "kamera", aus amtlichen Ankern; ersatzweise Silhouettenkamera aus kameras.json) wird das
Modell gerendert: Tiefe + Normalen -> Modellkanten. Das Foto wird auf ~0,15 m geglaettet (Steinfugen weg) -> Fotokanten. Je Zelle (~1 x 1 m auf
dem Modell) Kantendichte Foto vs Modell. Score > 0: Foto hat Struktur, Modell nicht (FEHLT). Score < 0: Modell hat Struktur ohne Fotobeleg (ERFUNDEN?).
Jede auffaellige Zelle bekommt ihre 3D-Lage (Modelloberflaeche) und landet als Beobachtung in der Masstabelle (einmal, mit Foto/Zelle).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/fehlteile_finden.py modelle/<objekt>/objekt.json <foto> [--schwelle 0.35] [--top 12]
Ausgabe: modelle/<objekt>/audit/fehlteile_<foto>.jpg (Heatmap ueber dem Foto, nummerierte Treffer), fehlteile_<foto>.json.
Grenzen: nur Kanten (keine Farbe), Verdeckungen (Baeume, Leitungen) erzeugen Scheintreffer -> jeder Treffer wird angesehen, bevor er in den Generator geht.
"""
import sys, os, json, glob, math, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def kamera_laden(K, obj, nr, root, W, H):
    if "kamera" in K:
        k = K["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"])); return R, np.array(k["t"]), k["f_px"], "K-%s (amtliche Anker)" % nr
    for kp in glob.glob(os.path.join(root, "modelle", "foto_silhouette", "*kameras.json")):      # Silhouettenkamera (foto_dach_gemeinsam)
        kam = json.load(open(kp))
        if nr in kam:
            d, az, el, tz, ro, fs, sx, sy = kam[nr]["th"]; k = W / 400.0
            tgt = np.array([0, 0, tz]); cam = tgt + d * np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
            fw = tgt - cam; fw /= np.linalg.norm(fw); x = np.cross(fw, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(fw, x)
            cr, sr = math.cos(ro), math.sin(ro); x2 = cr * x + sr * y; y2 = -sr * x + cr * y; R = np.vstack([x2, y2, fw]); t = -R @ cam
            f = 5.4 / 4.29 * 400 * k * fs; return R, t, f, "Silhouettenkamera %s (sx/sy %.0f/%.0f px vernachlaessigt)" % (os.path.basename(kp), sx * k, sy * k)
    raise SystemExit("keine Kamera fuer Foto " + nr)

def render(m, R, t, f, W, H, cx, cy, n=2500000):
    """Tiefe, Normalen und 3D-Lage je Pixel ueber den gemeinsamen Renderkern (GPU, wenn vorhanden)."""
    import render_kern as RK
    P, fi = trimesh.sample.sample_surface(m, n, seed=0); P = np.asarray(P); N = m.face_normals[fi]
    depth, idx = RK.tiefenbild(P, R, t, f, cx, cy, W, H)
    if hasattr(depth, "cpu"): depth = depth.cpu().numpy(); idx = idx.cpu().numpy()
    nrm = np.zeros((H, W, 3)); pos = np.zeros((H, W, 3)); tr = idx >= 0
    nrm[tr] = N[idx[tr]]; pos[tr] = P[idx[tr]]
    return depth, nrm, pos

def main():
    a = sys.argv[1:]; objp, nr = a[0], a[1]; sch = float(a[a.index("--schwelle") + 1]) if "--schwelle" in a else 0.35; top = int(a[a.index("--top") + 1]) if "--top" in a else 12
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp)))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    kp = os.path.join(od, "messprotokoll", f"K-{nr}.json"); K = json.load(open(kp)) if os.path.exists(kp) else {}
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); H, W = im.shape[:2]; cx, cy = W / 2, H / 2
    R, t, f, quelle = kamera_laden(K, obj, nr, root, W, H)
    stl = a[a.index("--stl") + 1] if "--stl" in a else os.path.join(root, obj["stl"])
    m = trimesh.load(stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3); m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]])
    depth, nrm, pos = render(m, R, t, f, W, H, cx, cy); sil = np.isfinite(depth)
    sil_f = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    # Punktrender hat Loecher: Tiefe per Minimum-Filter (naechster Punkt gewinnt) fuellen, dann glaetten; Normalen aus der gefuellten Tiefe
    dfill = depth.copy(); dfill[~sil] = 1e6; dfill = cv2.erode(dfill, np.ones((5, 5), np.uint8)); dfill[sil_f == 0] = np.nan
    dsm = cv2.GaussianBlur(np.nan_to_num(dfill, nan=0.0), (0, 0), 3.0)
    gx = cv2.Sobel(dsm, cv2.CV_64F, 1, 0, ksize=3) / 8.0; gy = cv2.Sobel(dsm, cv2.CV_64F, 0, 1, ksize=3) / 8.0     # m je Pixel
    dz = np.hypot(gx, gy); ppm0 = f / float(np.nanmedian(dfill))
    # Normalenwechsel: Winkel zwischen Nachbar-Gradienten (zweite Ableitung der Tiefe, in m/px je px)
    gxx = cv2.Sobel(gx, cv2.CV_64F, 1, 0, ksize=3) / 8.0; gyy = cv2.Sobel(gy, cv2.CV_64F, 0, 1, ksize=3) / 8.0; gxy = cv2.Sobel(gx, cv2.CV_64F, 0, 1, ksize=3) / 8.0
    kruemm = (np.abs(gxx) + np.abs(gyy) + np.abs(gxy)) * ppm0                                                   # ~ Normalenaenderung je Meter
    mk = ((dz > 0.2) | (kruemm > 1.0)) & (sil_f > 0)                                                            # Tiefensprung > 0,25 m/px oder deutliche Kante
    # Fotokanten: Glaettung auf ~0,15 m (Steinfugen weg), Canny, nur innerhalb der Modellsilhouette (erodiert, damit der Rand nicht zaehlt)
    depth_f = dfill; dmed = float(np.nanmedian(depth_f)); ppm = f / dmed; sigma = max(1.0, 0.07 * ppm)                 # ~7 cm: Steinfugen weg, Bauteile bleiben
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), sigma); fk = cv2.Canny(g, 20, 60) > 0
    inner = cv2.erode(sil_f, np.ones((int(0.6 * ppm) | 1,) * 2, np.uint8)) > 0; fk &= inner; mk &= inner
    tol = np.ones((int(0.3 * ppm) | 1,) * 2, np.uint8)                                                         # Toleranz 0,3 m: Kante zaehlt, wenn im Umkreis eine liegt
    fk = cv2.dilate(fk.astype(np.uint8), tol) > 0; mk = cv2.dilate(mk.astype(np.uint8), tol) > 0                # (faengt ~0,5 m Kamerafehler ab)
    # Zellen ~1 m
    cs = max(8, int(round(1.0 * ppm))); gh, gw = H // cs, W // cs; treffer = []
    def dichte(mask):
        v = [mask[i * cs:(i + 1) * cs, j * cs:(j + 1) * cs].sum() / max(1, inner[i * cs:(i + 1) * cs, j * cs:(j + 1) * cs].sum()) for i in range(gh) for j in range(gw) if inner[i * cs:(i + 1) * cs, j * cs:(j + 1) * cs].sum() >= 0.5 * cs * cs]
        return max(1e-6, float(np.quantile(v, 0.9)))
    qf, qm = dichte(fk), dichte(mk); print(f"  Kantendichte 90%-Quantil Foto {qf:.3f}, Modell {qm:.3f}")
    heat = np.zeros((gh, gw))
    for i in range(gh):
        for j in range(gw):
            sl = (slice(i * cs, (i + 1) * cs), slice(j * cs, (j + 1) * cs)); n_in = inner[sl].sum()
            if n_in < 0.5 * cs * cs: continue
            pf = min(1.0, fk[sl].sum() / n_in / qf); pm = min(1.0, mk[sl].sum() / n_in / qm); s = (pf - pm); heat[i, j] = s   # beide auf ihr 90-%-Quantil normiert
            if abs(s) >= sch:
                pz = pos[sl][inner[sl] & np.isfinite(depth[sl])]; P3 = pz.mean(0) if len(pz) else [np.nan] * 3
                treffer.append(dict(zelle=[j * cs, i * cs, cs], score=round(float(s), 3), art="FEHLT im Modell" if s > 0 else "ERFUNDEN? (Modell ohne Fotobeleg)", xyz=[round(float(x), 2) for x in P3]))
    def nachbar_ok(tr):
        x, y, s_ = tr["zelle"]; j, i = x // cs, y // cs; nb = [heat[ii, jj] for ii in (i - 1, i, i + 1) for jj in (j - 1, j, j + 1) if 0 <= ii < gh and 0 <= jj < gw and (ii, jj) != (i, j)]
        return sum(1 for v in nb if np.sign(v) == np.sign(tr["score"]) and abs(v) >= sch / 2) >= 2
    treffer = [tr for tr in treffer if nachbar_ok(tr)]                                                           # mindestens 2 gleichsinnige Nachbarzellen
    treffer.sort(key=lambda t: -abs(t["score"])); treffer = treffer[:top]
    o = im.copy(); hm = cv2.resize(heat, (gw * cs, gh * cs), interpolation=cv2.INTER_NEAREST); hm = np.pad(hm, ((0, H - gh * cs), (0, W - gw * cs)))
    col = np.zeros_like(o); col[..., 2] = np.clip(hm / 0.6, 0, 1) * 255; col[..., 0] = np.clip(-hm / 0.6, 0, 1) * 255
    o = cv2.addWeighted(o, 0.65, col, 0.35, 0)
    for k, tr in enumerate(treffer, 1):
        x, y, s = tr["zelle"]; cv2.rectangle(o, (x, y), (x + s, y + s), (0, 255, 255), 3); cv2.putText(o, str(k), (x + 4, y + s - 6), 0, 1.0, (0, 255, 255), 3)
    out = os.path.join(root, obj.get("audit", os.path.dirname(obj["masstabelle"]) + "/audit")); os.makedirs(out, exist_ok=True)
    tag = ("_" + os.path.basename(stl)[:-4]) if "--stl" in a else ""
    cv2.imwrite(os.path.join(out, f"fehlteile_{nr}{tag}.jpg"), o); json.dump(dict(foto=nr, stl=stl, kamera=quelle, zelle_px=cs, schwelle=sch, treffer=treffer), open(os.path.join(out, f"fehlteile_{nr}{tag}.json"), "w"), indent=1, ensure_ascii=False)
    print(f"Fehlteile {nr} ({quelle}; Zelle {cs} px = 1 m; rot = fehlt im Modell, blau = Modell ohne Fotobeleg) -> {out}/fehlteile_{nr}{tag}.jpg")
    for k, tr in enumerate(treffer, 1): print(f"  {k:2d}. {tr['art']:36s} score {tr['score']:+.2f}  bei x={tr['xyz'][0]} y={tr['xyz'][1]} z={tr['xyz'][2]} m")
    # Beobachtungen automatisch eintragen (einmal je Foto/Zelle)
    tp = os.path.join(root, obj["masstabelle"]); tab = json.load(open(tp)); vorhanden = {b.get("auto_id") for b in tab.get("beobachtungen_offen", [])}; neu = 0
    for k, tr in enumerate(treffer, 1):
        if "--stl" in a: break                                                       # Testlaeufe an fremden STL erzeugen keine Beobachtungen
        if tr["art"].startswith("FEHLT") and tr["score"] >= sch:
            aid = f"fehlteile-{nr}-{tr['zelle'][0]}-{tr['zelle'][1]}"
            if aid in vorhanden: continue
            tab.setdefault("beobachtungen_offen", []).append(dict(datum="auto", wer=f"fehlteile_finden (Foto {nr}, Treffer {k})", auto_id=aid,
                art="fehlteil", foto=nr, z_von=tr["xyz"][2], z_bis=tr["xyz"][2], xyz=tr["xyz"], abweichung=tr["score"],
                text=f"Foto zeigt Struktur ohne Modellgegenstueck bei z={tr['xyz'][2]} m, y={tr['xyz'][1]} m (Zelle {tr['zelle']}, Score {tr['score']:+.2f})",
                naechster_schritt=f"audit/fehlteile_{nr}.jpg Treffer {k} ansehen, Element benennen, Zeile + beleg()")); neu += 1
    json.dump(tab, open(tp, "w"), indent=1, ensure_ascii=False); print(f"  -> {neu} neue Beobachtung(en) in der Masstabelle")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""modell_validator.py — EINHEITLICHER vollautomatischer Validator Realität gegen Modell.

Zieht ALLE Register (je Frageart der passende Richter — die Kern-Lehre: Validator zur Frage
passen) und aggregiert zu EINEM Score + priorisierter Fix-Liste. Generisch für jedes Gebäude
(traufständig wie Kaufhaus/Oberkirch, giebelständig wie Kornhaus).

Register (alle vollautomatisch):
  MASSING      Modell-BBox (GLB) vs LOD2 (front_w/ridge)            -> Proportion amtlich
  ANZAHL       fenster_zaehler auf FOTO und auf RENDER, Vergleich   -> Zahl/Anordnungstreue
  FARBE        Median-Fassadenfarbe Foto vs Render                  -> Farbtreue (Lücke gefüllt)
  FERTIGUNG    watertight/euler/Teile/BBox aus STL                  -> Druckbarkeit
  ORIENTIERUNG Silhouetten-Massenverteilung (nicht gekippt/geflippt)-> Lage-Gate
  SILHOUETTE   Breiten-Profil Foto vs Render (perspektiv-tolerant)  -> grobe Form

  python3 tools/modell_validator.py --foto F --render R --glb G --lod2 L \
      --box x0,y0,x1,y1 [--stl S] [--name N] [--out report.json] [--beleg beleg.png]
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
import fenster_zaehler as FZ
try:
    import trimesh
except Exception:
    trimesh = None


# ---------- Helfer ----------
def _count_windows(img, box=None):
    """IDENTISCHE fenster_zaehler-Auto-Pipeline für Foto UND Render (apples-to-apples, wie der
    Generator baut). box (optional) schneidet nur grob vor (Nachbar raus); die Isolierung macht
    das dominante x-Cluster selbst."""
    if box is not None:
        H0, W0 = img.shape[:2]
        img = img[int(box[1]*H0):int(box[3]*H0), int(box[0]*W0):int(box[2]*W0)]
    allw, _ = FZ.detect_windows(img); g = FZ.dominant_cluster(allw, img.shape[1], img.shape[0])
    if not g:
        return 0, 0, []
    xs = [b[0] for b in g]; ys = [b[1] for b in g]; ws = [b[2] for b in g]; hs = [b[3] for b in g]
    pad = 2.0*np.median(hs)
    x0 = max(0, int(min(xs)-max(ws))); x1 = min(img.shape[1], int(max(xs)+max(ws)))
    y0 = max(0, int(min(ys)-pad)); y1 = min(img.shape[0], int(max(ys)+2.2*pad))
    crop = img[y0:y1, x0:x1]
    wins, _ = FZ.detect_windows(crop, close_k=3, min_af=8e-4, max_af=0.015,
                                ar_lo=0.3, ar_hi=2.3, min_fill=0.28)
    ch = crop.shape[0]; wins = [b for b in wins if (b[1]+b[3]/2) < 0.90*ch]
    wins = FZ.merge_boxes(wins)
    rows = FZ.cluster_rows(wins, ch)
    return len(wins), len(rows), [len(r) for r in sorted(rows, key=lambda r: np.mean([b[1] for b in r]))]


def _facade_color(img, box):
    """Median-Farbe der hellen Putzwand in der Fassaden-ROI (Fenster/Himmel/Dunkles ausgeschlossen)."""
    H0, W0 = img.shape[:2]
    x0, y0, x1, y1 = int(box[0]*W0), int(box[1]*H0), int(box[2]*W0), int(box[3]*H0)
    c = img[y0:y1, x0:x1].reshape(-1, 3).astype(int)
    br = c.sum(1)
    sel = (br > 300) & (br < 720)                     # Wand: hell, aber nicht überstrahlt/Glas
    px = c[sel] if sel.sum() > 50 else c
    return np.median(px, 0)[::-1]                     # BGR->RGB


def _silhouette(bgr, bg_sky):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    if bg_sky:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        sky = (hsv[:, :, 2] > 150) & (hsv[:, :, 1] < 55)
        m = (~sky & (g < 250)).astype(np.uint8)
    else:
        m = (g < 248).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        i = 1+int(np.argmax(st[1:, cv2.CC_STAT_AREA])); m = (lab == i).astype(np.uint8)
    return m


def _width_profile(mask, nb=30):
    H = mask.shape[0]; prof = []
    for b in range(nb):
        band = mask[int(b/nb*H):int((b+1)/nb*H)]
        cols = np.where(band.any(0))[0]
        prof.append((cols.max()-cols.min()) if len(cols) else 0)
    p = np.array(prof, float); return p/max(p.max(), 1)


# ---------- Register ----------
def reg_massing(glb, lod2):
    if trimesh is None or not glb or not os.path.exists(glb):
        return None
    ext = trimesh.load(glb).bounds; ext = ext[1]-ext[0]
    jd = json.load(open(lod2)) if lod2 and os.path.exists(lod2) else {}
    d = jd.get("gebaeude", [{}])[0]
    ridge = d.get("ridge_m"); fw = d.get("front_w_m")
    bl = jd.get("bbox_lbh_m")
    if not ridge and bl:
        ridge = bl[2]
    if not fw and bl:
        fw = min(bl[0], bl[1])                         # Fallback: kurze Grundriss-Seite = Front
    exts = sorted(ext, reverse=True)
    h_mod = float(exts[0])                             # höchste Ausdehnung = Höhe
    w_mod = float(min(ext, key=lambda e: abs(e-fw))) if fw else float(exts[1])
    # Höhe: EINSEITIGE Toleranz — Zier (Statuen/Finial/First-Schmuck) DARF über den LOD2-First
    # ragen (bis +18%); echter Fehler ist v.a. zu KURZ. Breite: beidseitig.
    he = max(0.0, (ridge-h_mod)/ridge) + max(0.0, (h_mod-ridge*1.18)/ridge) if ridge else None
    we = abs(w_mod-fw)/fw if fw else None
    errs = [e for e in (he, we) if e is not None]
    score = max(0.0, 1-np.mean(errs)/0.15) if errs else 0.5
    fix = None
    if we and we > 0.10:
        fix = f"MASSING: Breite {w_mod:.1f}m vs LOD2 {fw:.1f}m ({we*100:.0f}% ab) -> front_w aus LOD2-Grundriss"
    elif he and he > 0.08:
        rel = "zu kurz" if h_mod < ridge else "zu hoch (über Zier hinaus)"
        fix = f"MASSING: Höhe {h_mod:.1f}m vs LOD2-First {ridge:.1f}m ({rel})"
    return dict(score=round(float(score), 2), h_mod=round(h_mod, 1), ridge=ridge,
                w_mod=round(w_mod, 1), front_w=round(fw, 1) if fw else None, fix=fix)


def reg_count(foto_img, render_img, box):
    nf, rf, rowsf = _count_windows(foto_img, box)
    nm, rm, rowsm = _count_windows(render_img, None)
    if nf == 0 or nm == 0:
        return dict(score=0.3, n_foto=nf, n_modell=nm,
                    fix=f"ANZAHL: Detektor-Fehlschlag (Foto {nf}, Modell {nm}) — unsicher")
    # GROBER Sanity-Flag, kein Feinscore: Fensterzählung schwankt mit Crop/Kontrast (Detektor
    # nicht crop-invariant). Innerhalb ±3 ODER 40 % = ok; erst grobe Abweichung zieht runter.
    diff = abs(nf-nm); derr = diff/max(nf, nm)
    score = 1.0 if (diff <= 3 or derr <= 0.40) else max(0.0, 1-(derr-0.40)/0.4)
    fix = (f"ANZAHL (grob): {nm} Fenster Modell vs {nf} Foto; "
           f"Reihen Foto {rowsf} vs Modell {rowsm}") if score < 0.9 else None
    return dict(score=round(float(score), 2), n_foto=nf, n_modell=nm,
                rows_foto=rowsf, rows_modell=rowsm, fix=fix)


def reg_color(foto_img, render_img, box):
    cf = _facade_color(foto_img, box); cm = _facade_color(render_img, (0.2, 0.15, 0.8, 0.7))
    dE = float(np.sqrt(((cf-cm)**2).sum()))
    score = max(0.0, 1-dE/120)
    fix = (f"FARBE: Fassade Foto RGB{tuple(int(x) for x in cf)} vs Modell "
           f"RGB{tuple(int(x) for x in cm)} (ΔE {dE:.0f})") if dE > 45 else None
    return dict(score=round(score, 2), rgb_foto=[int(x) for x in cf],
                rgb_modell=[int(x) for x in cm], dE=round(dE, 1), fix=fix)


def reg_fertigung(glb_or_stl):
    """prüft die DRUCK-Mesh. Ein Anzeige-Modell (measured.glb/.stl) ist absichtlich mehrteilig
    (Farbgruppen) -> NICHT watertight; das ist kein Qualitätsmangel, Druck geht über mesh_druckbar.
    Darum: existiert eine dedizierte *_3d/_druckbar-STL, diese prüfen; sonst informativ (0.7)."""
    if trimesh is None or not glb_or_stl:
        return None
    base = os.path.dirname(glb_or_stl)
    cands = []
    for pat in ("_3d.stl", "_druckbar.stl", "_print.stl"):
        import glob as _g
        cands += _g.glob(os.path.join(base, "*" + pat))
    if cands:
        m = trimesh.load(cands[0], process=False); wt = bool(m.is_watertight)
        score = 1.0 if wt else 0.5
        fix = None if wt else f"FERTIGUNG: Druck-STL {os.path.basename(cands[0])} nicht watertight -> mesh_druckbar.py"
        return dict(score=round(score, 2), druck_stl=os.path.basename(cands[0]), watertight=wt, fix=fix)
    return dict(score=0.7, druck_stl=None, hinweis="Anzeige-Mesh mehrteilig; Druck via mesh_druckbar.py", fix=None)


def reg_orientierung(render_img):
    m = _silhouette(render_img, bg_sky=True)
    if m.sum() < 500:
        return dict(score=0.0, fix="ORIENTIERUNG: keine Silhouette im Render")
    p = _width_profile(m)
    top = p[:len(p)//3].mean(); bot = p[-len(p)//3:].mean()
    # Gebäude: unten mind. so breit wie oben (Giebel schmaler oben); geflippt -> oben breiter
    flipped = top > bot*1.25
    score = 0.3 if flipped else 1.0
    fix = "ORIENTIERUNG: oben breiter als unten -> evtl. vertikal geflippt" if flipped else None
    return dict(score=score, top_w=round(float(top), 2), bot_w=round(float(bot), 2), fix=fix)


def reg_silhouette(foto_img, render_img, box):
    H0, W0 = foto_img.shape[:2]
    x0, y0, x1, y1 = int(box[0]*W0), int(box[1]*H0), int(box[2]*W0), int(box[3]*H0)
    pm = _silhouette(foto_img[y0:y1, x0:x1], bg_sky=True)
    mm = _silhouette(render_img, bg_sky=True)
    def bb(m): ys, xs = np.where(m); return m[ys.min():ys.max()+1, xs.min():xs.max()+1]
    pmc, mmc = bb(pm), bb(mm)
    mmR = cv2.resize(mmc, (pmc.shape[1], pmc.shape[0]))
    iou = float((pmc & mmR).sum())/max(int((pmc | mmR).sum()), 1)
    perr = float(np.mean(np.abs(_width_profile(pmc)-_width_profile(mmR))))
    score = 0.6*iou+0.4*(1-min(perr*3, 1))
    fix = f"SILHOUETTE: Breiten-Profil weicht ab (IoU {iou:.2f}, perspektiv-gedeckelt)" if score < 0.5 else None
    return dict(score=round(score, 2), iou=round(iou, 2), prof_err=round(perr, 2), fix=fix)


# Gewichte nach VERLÄSSLICHKEIT des Registers (kalibriert an bekannt-guten Modellen):
# Perspektiv-gedeckelte/informative Register niedrig, robuste (Massing/Anzahl/Farbe) hoch.
WEIGHTS = dict(MASSING=0.35, FARBE=0.25, ANZAHL=0.20, ORIENTIERUNG=0.10, SILHOUETTE=0.05, FERTIGUNG=0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True); ap.add_argument("--render", required=True)
    ap.add_argument("--glb", default=""); ap.add_argument("--lod2", default="")
    ap.add_argument("--stl", default=""); ap.add_argument("--box", default="0.1,0.05,0.9,0.85")
    ap.add_argument("--name", default="Gebäude"); ap.add_argument("--out", default="")
    a = ap.parse_args()
    box = [float(t) for t in a.box.split(",")]
    foto = cv2.imread(a.foto); render = cv2.imread(a.render)

    regs = {}
    regs["MASSING"] = reg_massing(a.glb, a.lod2)
    regs["ANZAHL"] = reg_count(foto, render, box)
    regs["FARBE"] = reg_color(foto, render, box)
    regs["FERTIGUNG"] = reg_fertigung(a.stl or a.glb.replace(".glb", ".stl"))
    regs["ORIENTIERUNG"] = reg_orientierung(render)
    regs["SILHOUETTE"] = reg_silhouette(foto, render, box)

    tot_w = sum(WEIGHTS[k] for k, v in regs.items() if v is not None)
    total = sum(WEIGHTS[k]*v["score"] for k, v in regs.items() if v is not None)/max(tot_w, 1e-6)
    fixes = [v["fix"] for v in regs.values() if v and v.get("fix")]

    print(f"\n=== VALIDATOR: {a.name} ===  GESAMT-SCORE {total:.2f}")
    for k in WEIGHTS:
        v = regs.get(k)
        if v is None:
            print(f"  {k:12s}  —  (kein Input)"); continue
        print(f"  {k:12s}  {v['score']:.2f}  {({kk: vv for kk, vv in v.items() if kk not in ('score','fix')})}")
    print("\nPRIORISIERTE FIXES:" if fixes else "\nKEINE FIXES — alle Register grün.")
    for i, fx in enumerate(sorted(fixes, key=lambda f: f.split(':')[0]), 1):
        print(f"  {i}. {fx}")

    report = dict(name=a.name, total_score=round(float(total), 3), register=regs, fixes=fixes)
    if a.out:
        json.dump(report, open(a.out, "w"), indent=2, ensure_ascii=False, default=float)
        print(f"-> {a.out}")
    return report


if __name__ == "__main__":
    main()

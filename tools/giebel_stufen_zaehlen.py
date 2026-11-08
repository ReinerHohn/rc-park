#!/usr/bin/env python3
"""giebel_stufen_zaehlen.py - Stufen eines Treppengiebels AUTOMATISCH am Foto zaehlen (Regel 9, Register CB), 2026-11-05.

Vorher: Zaehlprotokoll Z-050-001 von Hand ("Claude Sichtzaehlung") -> Handschritt, nicht vollautomatisch.
Verfahren: Flankenlinien (Traufe -> Spitze) aus dem Generator (elemente.json, Beleg 'Treppengiebel' masse.flanken = LoD2-Giebelwand + Dachneigung) in jedes
kalibrierte Foto projizieren (Buendelkamera, k1). Entlang der Flanke je Stelle t das Querprofil des Fotos (Grauwertgradient senkrecht zur Linie, +-Band)
-> Lage h(t) der staerksten Kante (Silhouette Stufen/Himmel bzw. Stufen/Dach). Die Stufen machen h(t) zur Saegezahnkurve: Periode per Spektrum
(n in [3, 15] Stufen auf der Flankenlaenge). Je Flanke und Foto eine Zaehlung mit Guete (Spektralanteil der Spitze); Ergebnis = gewichteter Mehrheitswert
ueber alle guten Flanken/Fotos. Sichtbarkeit: Flankenmitte per Strahl gegen Modell + LoD2-Nachbarn frei, Flanke >= 250 px lang.
Ausgabe: messprotokoll/Z-<foto>-<nr>.json + .jpg (bestes Foto, Stufenecken markiert) wie foto_zaehlung.py, 'wer' = dieses Werkzeug; giebel_stufen.json mit allen Stimmen.

  /media/oem/scan/venv-seg/bin/python -I tools/giebel_stufen_zaehlen.py <objekt.json> --elemente <elemente.json> --stl <modell.stl> [--schreiben]
"""
import os, sys, json, glob, argparse, time
import numpy as np, cv2, trimesh
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import fehlteile_finden as FF
from fassade_ortho import projizieren, nachbarn_netz


def zaehlen(gray, p0, p1, band=None, n_min=4, n_max=15):
    """Stufen entlang p0->p1 (Pixel) zaehlen: Band +-band quer zur Linie abtasten; jede Querlage ergibt ein Helligkeitssignal entlang der Flanke. Die Lage,
    die durch die Stufenkappen laeuft, zeigt ein Rechtecksignal (Stufe/Himmel bzw. Stufe/Dach) - Periode per Spektrum (Trend per gleitendem Mittel weg).
    Robuster als 'Lage der staerksten Kante' (2026-11-05: 3 statt 7, Linie liegt wegen Kameraversatz neben den Spitzen). Rueckgabe (n, guete, ecken_px)."""
    L = float(np.linalg.norm(p1 - p0)); d = (p1 - p0) / L; nrm = np.array([-d[1], d[0]])
    if nrm[1] > 0: nrm = -nrm
    band = band or max(15, int(L * 0.12)); T = int(L); ts = np.linspace(0, L, T); hs = np.arange(-band, band + 1)
    X = p0[0] + ts[:, None] * d[0] + hs[None, :] * nrm[0]; Y = p0[1] + ts[:, None] * d[1] + hs[None, :] * nrm[1]
    g = cv2.GaussianBlur(gray, (0, 0), 1.0).astype(np.float32)
    prof = cv2.remap(g, X.astype(np.float32), Y.astype(np.float32), cv2.INTER_LINEAR, borderValue=float("nan"))
    if np.isnan(prof).mean() > 0.2: return None, 0.0, []
    prof = np.nan_to_num(prof, nan=float(np.nanmean(prof))); w = max(5, T // n_min // 2) | 1
    sig = prof - cv2.blur(prof, (1, w)); sig *= np.hanning(T)[:, None]                               # je Querlage (Spalte) Trend weg
    P = np.abs(np.fft.rfft(sig, axis=0)) ** 2; fr = np.arange(P.shape[0]); ok = (fr >= n_min) & (fr <= n_max)
    if not ok.any(): return None, 0.0, []
    ges = P[2:4 * n_max].sum(0) + 1e-9; Q = P[ok] / ges[None, :]; ki, jo = np.unravel_index(np.argmax(Q), Q.shape)
    k = int(fr[ok][ki]); guete = float(Q[ki, jo]); s1 = sig[:, jo]; per = L / k; ecken = []
    phase = np.angle(np.fft.rfft(s1)[k])
    for i_ in range(k):                                                                              # Mitte jeder hellen/dunklen Periode als Markierung
        tt = ((i_ + 0.25) * per - phase / (2 * np.pi) * per) % L; ecken.append((p0 + d * tt + nrm * hs[jo]).tolist())
    return k, guete, ecken


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--elemente", required=True); ap.add_argument("--stl", required=True)
    ap.add_argument("--min-px", type=float, default=250); ap.add_argument("--min-guete", type=float, default=0.25); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--aus"); a = ap.parse_args(argv)
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "giebel_stufen"); os.makedirs(aus, exist_ok=True)
    fl = [f for e in json.load(open(a.elemente)) if e.get("flanken") for f in e["flanken"]]
    if not fl: raise SystemExit("keine Flanken im Beleg 'Treppengiebel' (Generator ohne treppengiebel?)")
    m = trimesh.load(a.stl); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); nb, _ = nachbarn_netz(obj); szene = trimesh.util.concatenate([m, nb]) if nb is not None else m
    RI = trimesh.ray.ray_pyembree.RayMeshIntersector if hasattr(trimesh.ray, "ray_pyembree") else trimesh.ray.ray_triangle.RayMeshIntersector; ray = RI(szene)
    stimmen = []
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        K = json.load(open(kp)); kk = K.get("kamera", {})
        if not (kk.get("buendel_tor") or {}).get("ok"): continue
        nr = os.path.basename(kp)[2:-5]; pf = glob.glob(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))
        if not pf: continue
        im = cv2.imread(pf[0]); H, W = im.shape[:2]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, ROOT, W, H); tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float)
        C = -R.T @ np.asarray(t, float) - tr; gray = None
        for i, F_ in enumerate(fl):
            X = np.asarray(F_["linie"], float); px, z = projizieren(X + tr, R, t, f, float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)), float(kk.get("k1") or 0.0))
            if (z <= 1).any() or not ((px >= 5).all() and (px[:, 0] < W - 5).all() and (px[:, 1] < H - 5).all()): continue
            if np.linalg.norm(px[1] - px[0]) < a.min_px: continue
            M_ = X.mean(0) + np.array([0, 0, 0.5]); v = M_ - C; dist = np.linalg.norm(v)                 # knapp ueber der Flanke (Stufenkappen)
            loc, _, _ = ray.intersects_location(C[None], (v / dist)[None], multiple_hits=False)
            if len(loc) and np.linalg.norm(loc[0] - C) < dist - 1.5: continue
            if gray is None: gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
            n, q, ecken = zaehlen(gray, px[0].astype(float), px[1].astype(float))
            if n is None: continue
            stimmen.append(dict(foto=nr, flanke=i, ende=F_["ende"], seite=F_["seite"], n=n, guete=round(q, 3), laenge_px=round(float(np.linalg.norm(px[1] - px[0]))), ecken=ecken, linie_px=px.tolist()))
            print(f"  {nr} Flanke {i} ({np.linalg.norm(px[1] - px[0]):.0f} px): {n} Stufen, Guete {q:.2f}", flush=True)
    gut = [s for s in stimmen if s["guete"] >= a.min_guete]
    erg = dict(stimmen=stimmen, min_guete=a.min_guete, n_gut=len(gut))
    if gut:
        w = {}
        for s in gut: w[s["n"]] = w.get(s["n"], 0.0) + s["guete"]
        n_best = max(w, key=w.get); erg.update(perioden=n_best, ergebnis=n_best - 1, ergebnis_regel="Stufen = Kappen-Perioden - 1: die Flanke endet an der Spitzenkante, die Spitzenkappe liegt in der letzten Periode (Sichtpruefung 082/047 2026-11-05: 9 Perioden = 8 Stufen + Spitze)", gewichte={str(k): round(v, 2) for k, v in sorted(w.items())}, einig=round(w[n_best] / sum(w.values()), 2))
        print(f"Ergebnis: {n_best} Kappen-Perioden = {n_best - 1} Stufen je Flanke (Gewichte {erg['gewichte']}, Einigkeit {erg['einig']})")
        b = max((s for s in gut if s["n"] == n_best), key=lambda s: s["guete"] * s["laenge_px"])
        im = cv2.imread(glob.glob(os.path.join(ROOT, obj["fotos_dir"], b["foto"] + "_*"))[0]); lp = np.asarray(b["linie_px"], int)
        cv2.line(im, tuple(lp[0]), tuple(lp[1]), (255, 255, 0), 2)
        for x, y in b["ecken"]: cv2.circle(im, (int(x), int(y)), 9, (0, 0, 255), 3)
        x0, y0 = np.maximum(0, lp.min(0) - 150); x1, y1 = lp.max(0) + 150; cv2.imwrite(os.path.join(aus, "beste.jpg"), im[y0:y1, x0:x1])
        if a.schreiben:
            nrs = [int(os.path.basename(p)[6:9]) for p in glob.glob(os.path.join(od, "messprotokoll", f"Z-{b['foto']}-*.json")) if os.path.basename(p)[6:9].isdigit()]
            zid = f"Z-{b['foto']}-{max(nrs + [0]) + 1:03d}"; cv2.imwrite(os.path.join(od, "messprotokoll", zid + ".jpg"), im[y0:y1, x0:x1])
            json.dump(dict(id=zid, typ="zaehlung", foto=b["foto"], datei=os.path.basename(glob.glob(os.path.join(ROOT, obj["fotos_dir"], b["foto"] + "_*"))[0]),
                           was="Treppengiebel: Stufen je Flanke (automatisch, Saegezahn entlang der projizierten Flanke)", wer="giebel_stufen_zaehlen.py (automatisch)",
                           datum=time.strftime("%Y-%m-%d"), punkte=[dict(flaeche=f"F{b['flanke']}", art="voll", x=round(x, 1), y=round(y, 1)) for x, y in b["ecken"]],
                           je_flaeche_gezaehlt={f"F{b['flanke']}": dict(art="voll", n=n_best - 1)}, ergebnis=dict(je_flaeche=n_best - 1, perioden=n_best, voll_sichtbare_flaechen=1),
                           bild=zid + ".jpg", stimmen=dict(gewichte=erg["gewichte"], einig=erg["einig"], n_gut=len(gut)),
                           regel="Quelle: Foto (automatische Zaehlung am Foto, massstabsfrei). NICHT aus Punktwolke/Generatoreingabe (Register CB)."),
                      open(os.path.join(od, "messprotokoll", zid + ".json"), "w"), indent=1, ensure_ascii=False)
            erg["protokoll"] = zid; print(f"  -> {zid}")
    json.dump(erg, open(os.path.join(aus, "giebel_stufen.json"), "w"), indent=1)


if __name__ == "__main__":
    main()

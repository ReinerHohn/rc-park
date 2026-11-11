"""foto_feinsuche.py - FEHLENDE FEINFORM automatisch finden (modelle/SPEC_FEINSUCHE.md, Nutzer 11.11. "automatische Feinsuche auf jeden Fall").

Grobe Variante: foto_fehlteile.py (gelbe Flecken >= 2000 px, 0,18-m-Glaettung). Hier dieselbe Kette fuer die FEINEN Fotokanten:
teil_fotoform liefert je Teil und Foto 'flecken_fein' = die groessten zusammenhaengenden Feinkanten des Fotos (voll aufgeloest, Canny sigma 1), zu denen es
im Teil-Raster KEINE Modell-Feinkante innerhalb 0,03 m gibt (Rippen, Sprossen, Masswerk, Figuren, Wasserspeier ...), mit Weltpunkt auf der Modellflaeche.
Ablauf: Beobachtungen sammeln -> je Foto entdoppeln (gleicher Fleck bei mehreren Teilen) -> raeumlich clustern (GPU: pytorch3d ball_query, Union-Find) ->
Cluster nur, wenn sie in >= --min_fotos Fotos AUS VERSCHIEDENEN RICHTUNGEN (Kamerawinkel >= --min_winkel Grad) stehen -> Fein-Defizit (Median der
fehlenden Feinkantenpixel je Foto) x Fotozahl -> je Teil hoechstens --je_teil Cluster -> Kollage (Fotoausschnitt | Teil-Render derselben Kamera mit Fotokanten).
Stoermaske: wirkt bereits in teil_fotoform (--stoermaske an in der Formliste; erg['stoermaske']); hier wird nur gemeldet, ob die Formliste mit Maske gemessen wurde.
art_verdacht (ANNAHME, KEIN Tor): Farbtextur ohne Relief (Glasmuster, Bemalung, Moos) hat viel Farb-, wenig Helligkeitskante: Verhaeltnis chroma/luma der
Gradientenenergie im Ausschnitt; gemeldet als Zahl + Flag > --art_schwelle, Cluster werden NICHT verworfen.

Aufruf: python -I tools/foto_feinsuche.py <objekt> --formliste DATEI [--min_fotos 3] [--min_winkel 15] [--radius 1.0] [--min_px 60] [--aus DIR] [--teile_dir D --stl S] [--synth]
Ausgabe: <aus>/bericht.json, <aus>/cluster_<id>.jpg, <aus>/top10.jpg (Standard /media/oem/scan/rc-park_tmp/feinsuche/<objekt>)."""
import sys, os, json, glob, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = "/media/oem/scan/rc-park_tmp/feinsuche"
BRENN = {}   # Foto -> Brennweite in Pixeln (von kameras() gefuellt)


def laenge_m(o, cams):
    """Kantenlaenge des Flecks in METERN aus der Kamera: Kantenpixel x Entfernung / Brennweite (Pixelgroesse am Weltpunkt). None ohne Kamera."""
    f = BRENN.get(o["foto"]); c = cams.get(o["foto"])
    return None if f is None or c is None else o["px"] * float(np.linalg.norm(o["xyz"] - c)) / f


def beobachtungen(fl, min_px=60, dedup=0.3, feld="flecken_fein"):
    """Je (Foto, Fleck) eine Beobachtung; gleiches Foto + Weltpunkt < dedup von verschiedenen Teilen = derselbe Fleck (Teil mit meisten Pixeln bleibt Hauptteil)."""
    roh = []
    for teil, je in (fl.get("teile") or {}).items():
        for foto, e in je.items():
            if foto == "_gesamt" or not isinstance(e, dict): continue
            for g in e.get(feld) or []:
                if g.get("xyz") is None or g.get("px", 0) < min_px: continue
                roh.append((foto, np.array(g["xyz"], float), int(g["px"]), teil, g.get("bbox_px")))
    obs = []
    for foto in sorted({r[0] for r in roh}):
        for f_, x, px, t, bb in sorted([r for r in roh if r[0] == foto], key=lambda r: -r[2]):
            for o in obs:
                if o["foto"] == foto and np.linalg.norm(o["xyz"] - x) < dedup:
                    o["teile"][t] = max(o["teile"].get(t, 0), px); break
            else:
                obs.append({"foto": foto, "xyz": x, "px": px, "teile": {t: px}, "bbox_px": bb})
    return obs


def komponenten_gpu(X, radius, w=None, kmax=512):
    """KOMPAKTE Cluster auf der GPU (Leader-Verfahren, Durchmesser <= 2 x radius): Nachbarschaft je Punkt per pytorch3d ball_query (gpu_knn-Weg), dann Samen = unzugeordneter
    Punkt mit groesstem Gewicht w, nimmt alle unzugeordneten Punkte im Radius. Einzelverkettung verklebte ganze Waende zu EINEM Cluster (Lauf 1, 61 Fotos, Ort bedeutungslos)."""
    import gpu_knn  # setzt den pytorch3d-Pfad
    import torch
    from pytorch3d.ops import ball_query
    n = len(X)
    if n == 0: return np.array([], int)
    T = torch.as_tensor(np.asarray(X, np.float32), device="cuda")[None]
    idx = ball_query(T, T, K=min(kmax, n), radius=float(radius)).idx[0].cpu().numpy()
    lab = -np.ones(n, int); order = np.argsort(-(np.asarray(w, float) if w is not None else np.zeros(n)), kind="stable")
    for i in order:
        if lab[i] >= 0: continue
        nb = idx[i][idx[i] >= 0]; nb = nb[lab[nb] < 0]; lab[nb] = i; lab[i] = i
    return lab


def richtungen_ok(P, w, cams, fotos, min_fotos, min_winkel):
    """Wahl von Fotos mit Blickrichtungen (Zentrum -> Kamera) mindestens min_winkel Grad auseinander (Greedy, groesstes Defizit zuerst).
    Gibt die gewaehlten Fotos zurueck; Cluster zaehlt nur, wenn >= min_fotos gewaehlt werden."""
    c = np.average(P, 0, w); gew = []; dirs = []
    for fo in sorted(fotos, key=lambda x: -fotos[x]):
        if fo not in cams: continue
        d = cams[fo] - c; d = d / (np.linalg.norm(d) + 1e-9)
        if all(np.degrees(np.arccos(np.clip(d @ e, -1, 1))) >= min_winkel for e in dirs): gew.append(fo); dirs.append(d)
    return gew


def cluster_bilden(obs, cams, radius=1.0, min_fotos=3, min_winkel=15.0, je_teil=3):
    if not obs: return []
    X = np.array([o["xyz"] for o in obs]); lab = komponenten_gpu(X, radius, [o["px"] for o in obs]); out = []
    for c in np.unique(lab):
        oo = [o for o, l in zip(obs, lab) if l == c]; je_foto = {}
        for o in oo: je_foto[o["foto"]] = je_foto.get(o["foto"], 0) + o["px"]
        if len(je_foto) < min_fotos: continue
        P = np.array([o["xyz"] for o in oo]); w = np.array([o["px"] for o in oo], float)
        gew = richtungen_ok(P, w, cams, je_foto, min_fotos, min_winkel)
        if len(gew) < min_fotos: continue
        tp = {}
        for o in oo:
            for t, px in o["teile"].items(): tp[t] = tp.get(t, 0) + px
        teil = max(tp, key=tp.get); z = np.average(P, 0, w)
        defizit = int(np.median(list(je_foto.values())))
        out.append({"teil": teil, "ort": np.round(z, 2).tolist(), "lo": np.round(P.min(0) - 0.3, 2).tolist(), "hi": np.round(P.max(0) + 0.3, 2).tolist(),
                    "n_fotos": len(je_foto), "n_richtungen": len(gew), "fotos": sorted(je_foto), "fotos_richtungen": gew, "defizit_px": defizit,
                    "rang": defizit * len(je_foto), "teile_px": {t: int(v) for t, v in sorted(tp.items(), key=lambda kv: -kv[1])},
                    "bbox_px": {o["foto"]: o["bbox_px"] for o in sorted(oo, key=lambda o: o["px"])}})
    out.sort(key=lambda c: -c["rang"]); n_t = {}; res = []
    for c in out:
        n_t[c["teil"]] = n_t.get(c["teil"], 0) + 1
        if n_t[c["teil"]] <= je_teil: res.append(c)
    for i, c in enumerate(res): c["id"] = "fs%02d_%s" % (i + 1, c["teil"])
    return res


def kameras(objekt, fotos):
    """Kamerazentren im Rahmen der Formliste (= Modellrahmen der K-Dateien), -R^T t."""
    import fehlteile_finden as FF
    from PIL import Image
    objp = os.path.join(R0, "modelle", objekt, "objekt.json"); obj = json.load(open(objp)); cams = {}; global BRENN; BRENN = {}
    for nr in fotos:
        kp = FF.k_datei(objp, obj, R0, nr)
        if not kp: continue
        K = json.load(open(kp)); bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
        if not bild: continue
        W, H = Image.open(bild[0]).size; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cams[nr] = -R.T @ np.asarray(t, float); BRENN[nr] = float(f)
    return cams


def art_verdacht(img):
    """ANNAHME (kein Tor): Gradientenenergie Farbe (Lab a,b) gegen Helligkeit (L) im Ausschnitt; > ~0,5 = eher Farbmuster ohne Relief."""
    import cv2
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32); lab = cv2.GaussianBlur(lab, (0, 0), 1.0)
    def g(c): return np.hypot(cv2.Sobel(c, cv2.CV_32F, 1, 0), cv2.Sobel(c, cv2.CV_32F, 0, 1)).mean()
    return float((g(lab[..., 1]) + g(lab[..., 2])) / (2 * g(lab[..., 0]) + 1e-6))


def kollage(c, objekt, teile_dir, stl, aus, max_fotos=3):
    """Zeilen je Foto: Fotoausschnitt | Teil-Render derselben Kamera mit Fotokanten (orange); Ausschnitt = Fleck + Rand. Rueckgabe Pfad, art_verdacht-Wert."""
    import cv2, tempfile, teil_render_foto as TR
    fo = c["fotos_richtungen"][:max_fotos]; zeilen = []; arts = []
    for nr in fo:
        x, y, w, h = c["bbox_px"][nr]; cx, cy = x + w / 2, y + h / 2; s = max(w, h, 220) * 0.9 + 80
        ausschn = "%d,%d,%d,%d" % (cx - s * 0.75, cy - s * 0.5, cx + s * 0.75, cy + s * 0.5)
        td = tempfile.mkdtemp(dir=TMP)
        try:
            pf = TR.main([objekt, c["teil"], "--fotos", nr, "--teile_dir", teile_dir, "--stl", stl, "--aus", td, "--ausschnitt=" + ausschn, "--kontur", "--name", "Teil", "--maxbreite", "1500"])
        except SystemExit: pf = []
        if not pf: continue
        im = cv2.imread(pf[0]); zeilen.append(im); half = im[:, :im.shape[1] // 2]; arts.append(art_verdacht(half))
        os.remove(pf[0]); os.rmdir(td)
    if not zeilen: return None, None
    B = max(z.shape[1] for z in zeilen)
    zeilen = [cv2.copyMakeBorder(z, 0, 0, 0, B - z.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for z in zeilen]
    out = np.vstack(zeilen); cv2.putText(out, "%s  ort %s  fotos %d  defizit %d px" % (c["id"], c["ort"], c["n_fotos"], c["defizit_px"]), (8, out.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    p = os.path.join(aus, "cluster_%s.jpg" % c["id"]); cv2.imwrite(p, out, [cv2.IMWRITE_JPEG_QUALITY, 88]); return p, float(np.median(arts))


def beobachtung(c, art_schwelle):
    """Uebergabefeld fuer die Masstabelle (beobachtungen_offen); der Kreis uebernimmt es, hier wird NICHTS geschrieben."""
    ort = "(%.1f, %.1f, %.1f)" % tuple(c["ort"])
    return {"teil": c["teil"], "merkmal": "Feinform fehlt: %s %s" % (c["teil"], ort),
            "text": "Feinsuche: in %d Fotos aus %d Richtungen Feinkanten (Rippe/Sprosse/Figur?) ohne Modell-Feinkante, Defizit Median %d px/Foto, Ort %s (Suchkasten lo %s hi %s)%s"
                    % (c["n_fotos"], c["n_richtungen"], c["defizit_px"], ort, c["lo"], c["hi"], "; art_verdacht (Farbmuster ohne Relief?) " + ("ja" if c.get("art_verdacht") else "nein") if "art_verdacht" in c else ""),
            "fotos": c["fotos_richtungen"], "wer": "Feinsuche automatisch", "pruef_stichworte": [c["teil"], "feinform"], "kollage": c.get("kollage")}


def synth_test():
    """Beweistest Kette (Beobachtungen -> Entdoppeln -> GPU-Cluster -> Richtungs-Tor): zwei echte Cluster (4 Fotos aus 4 Richtungen), ein Cluster nur aus 4 Fotos
    GLEICHER Richtung (faellt am Winkeltor), Streuflecken, Doppelte ueber zwei Teile. Erwartung: genau 2 Cluster. (Beweis mit echtem Foto: tools/test_feinsuche.py)"""
    rng = np.random.default_rng(1); te = {}
    ang = {f: np.radians(a) for f, a in zip("abcdefgh", (0, 40, 90, 150, 200, 260, 300, 330))}
    cams = {f: 30 * np.array([np.cos(a), np.sin(a), 0.3]) for f, a in ang.items()}
    def fl(p, px=400): return {"px": px, "xyz": list(p), "bbox_px": [0, 0, 50, 50]}
    for c, fotos in (((0, 0, 5), "abcd"), ((10, 0, 8), "cdef"), ((0, 12, 6), "aaaa")):
        for k, f in enumerate(fotos):
            p = np.array(c) + rng.normal(0, 0.15, 3)
            for t in ("t1", "t2"): te.setdefault(t, {}).setdefault(f + ("" if c[1] != 12 else ""), {"flecken_fein": []})["flecken_fein"].append(fl(p))
    for i, f in enumerate("ghb"): te.setdefault("t1", {}).setdefault(f, {"flecken_fein": []})["flecken_fein"].append(fl((30 + 5 * i, 5, 2)))
    # dritter Cluster: nur Fotos nahe beieinander (a,a,a,a zaehlt als 1 Foto) -> fiele schon an min_fotos; zusaetzlich Richtungstor: b,b' fast gleich
    cams2 = dict(cams); cams2["x"] = cams["a"] + np.array([0.5, 0.2, 0]); cams2["y"] = cams["a"] + np.array([-0.4, 0.3, 0]); cams2["z"] = cams["a"] + np.array([0.2, -0.5, 0.1])
    for f in "xyz": te.setdefault("t3", {}).setdefault(f, {"flecken_fein": []})["flecken_fein"].append(fl(np.array((0, 12, 6)) + rng.normal(0, 0.1, 3)))
    obs = beobachtungen({"teile": te}); cl = cluster_bilden(obs, cams2, 1.0, 3, 15.0)
    ok = len(cl) == 2 and all(c["n_fotos"] == 4 and c["n_richtungen"] >= 3 for c in cl)
    print("SYNTH", "BESTANDEN" if ok else "FALSCH", [(c["id"], c["n_fotos"], c["n_richtungen"], c["ort"]) for c in cl]); return ok


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("--formliste"); ap.add_argument("--min_fotos", type=int, default=3)
    ap.add_argument("--min_winkel", type=float, default=15.0); ap.add_argument("--radius", type=float, default=1.0); ap.add_argument("--min_px", type=int, default=60)
    ap.add_argument("--je_teil", type=int, default=3); ap.add_argument("--aus"); ap.add_argument("--teile_dir"); ap.add_argument("--stl"); ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min_laenge_m", type=float, default=0.0, help="Mindest-Kantenlaenge je Fleck in Metern (aus Kamera gerechnet); 0 = nur --min_px"); ap.add_argument("--rand", help="Formliste mit flecken_fein_rand (teil_fotoform --fein_rand_m): Randflecken zusaetzlich verwenden")
    ap.add_argument("--art_schwelle", type=float, default=0.5); ap.add_argument("--synth", action="store_true"); ap.add_argument("--ohne_kollage", action="store_true")
    a = ap.parse_args(argv)
    if a.synth: sys.exit(0 if synth_test() else 1)
    fl = json.load(open(a.formliste)); aus = a.aus or os.path.join(TMP, a.objekt); os.makedirs(aus, exist_ok=True)
    obs = beobachtungen(fl, a.min_px)
    if a.rand: obs += beobachtungen(json.load(open(a.rand)), a.min_px, feld="flecken_fein_rand")
    cams = kameras(a.objekt, sorted({o["foto"] for o in obs}))
    if a.min_laenge_m > 0: obs = [o for o in obs if (laenge_m(o, cams) or 0) >= a.min_laenge_m]
    alle = cluster_bilden(obs, cams, a.radius, a.min_fotos, a.min_winkel, 10 ** 6)   # ohne Teil-Deckel: Rang jedes Clusters in der Gesamtliste (Nachweis fuer bekannte Funde)
    for i, c in enumerate(alle): c["rang_gesamt"] = i + 1
    nt = {}; cl = []
    for c in alle:
        nt[c["teil"]] = nt.get(c["teil"], 0) + 1
        if nt[c["teil"]] <= a.je_teil: cl.append(c)
    for i, c in enumerate(cl): c["id"] = "fs%02d_%s" % (i + 1, c["teil"])
    if not a.ohne_kollage and a.teile_dir and a.stl:
        for c in cl[:a.top]:
            p, art = kollage(c, a.objekt, a.teile_dir, a.stl, aus)
            c["kollage"] = p; c["art_wert"] = None if art is None else round(art, 3); c["art_verdacht"] = None if art is None else bool(art > a.art_schwelle)
    for c in cl[:a.top]: c["beobachtung"] = beobachtung(c, a.art_schwelle)
    erg = {"formliste": a.formliste, "stl_sha": fl.get("stl_sha"), "metrik": fl.get("metrik"), "metrik_fein": fl.get("metrik_fein"), "stoermaske": fl.get("stoermaske"),
           "stoermaske_fehlt": fl.get("stoermaske_fehlt"), "beobachtungen": len(obs), "cluster_gesamt": len(alle), "parameter": vars(a), "cluster": cl, "alle_cluster": [{k: v for k, v in c.items() if k not in ("bbox_px",)} for c in alle]}
    json.dump(erg, open(os.path.join(aus, "bericht.json"), "w"), indent=1, ensure_ascii=False)
    for c in cl[:a.top]: print("%-34s fotos %2d  richt. %2d  defizit %5d  ort %s  art %s  %s" % (c["id"], c["n_fotos"], c["n_richtungen"], c["defizit_px"], c["ort"], c.get("art_wert"), c.get("kollage")))
    top = [c["kollage"] for c in cl[:10] if c.get("kollage")]
    if top:
        import cv2
        ims = [cv2.resize(cv2.imread(p), (900, int(cv2.imread(p).shape[0] * 900 / cv2.imread(p).shape[1]))) for p in top]; hmax = max(i.shape[0] for i in ims)
        ims = [cv2.copyMakeBorder(i, 0, hmax - i.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for i in ims]
        zeilen = [np.hstack(ims[i:i + 2] + ([np.full_like(ims[0], 255)] if len(ims[i:i + 2]) < 2 else [])) for i in range(0, len(ims), 2)]
        cv2.imwrite(os.path.join(aus, "top10.jpg"), np.vstack(zeilen), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return erg


if __name__ == "__main__":
    main()

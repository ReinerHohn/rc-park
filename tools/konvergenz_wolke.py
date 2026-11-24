#!/usr/bin/env python3
"""konvergenz_wolke.py <objekt.json> --aus DIR [--fotosatz F] [--wolke PFAD] [--stl P] [--n-max 3000000] [--je-seite K] [--json J]
VERLUST "dichte Wolke -> Modell" je Seite (Auftrag 24.11.2026): dasselbe grobe Foto-F1 wie tools/konvergenz.py, aber zusaetzlich fuer die DICHTE WOLKE der
Kette, auf GENAU denselben Fotos (fester Satz audit/konvergenz_fotosatz.json) und mit DERSELBEN Kantenlogik (tools/foto_diff.py, ein Prozess, main() je Foto).

Je Foto zwei foto_diff-Laeufe im PUNKTMODUS (CPU, kein torch):
  1. MODELL: End-STL abgetastet (8 M Punkte, wie foto_diff --punkte) -> F1_modell_gleich; merkt Bewertungsbereich (Modellsilhouette sil_f), dmed und
     Verdeckermaske (foto_diff._PUNKTE["merken"]).
  2. WOLKE: dieselbe Rechnung, nur die Punkte (+ PCA-Normalen) aus der Wolke statt aus dem Netz (foto_diff._PUNKTE P/N); Splat/Tiefentest = der
     9x9-Minimum-Fuellschritt + Medianfilter von foto_diff._tiefe_vorbereiten (derselbe wie beim Netz-Punktrender), Bereich/dmed/Verdecker vom Modell
     -> identische Fotokanten, Luecken der Wolke im Modellbereich zaehlen als fehlende Kanten (sonst schoent ein loechriger Bereich den Recall).
  Gepaart: verlust = Median ueber die Fotos der Seite von (F1_wolke - F1_modell_gleich) (Lehre 10.11.: Gewinne nur auf gemeinsamen Fotos).
  f1_modell (Raster, GPU) bleibt die Zahl aus konvergenz.py; verlust wird auf der Punktfassung gerechnet, weil nur sie Wolke und Modell gleich rendert.
WOLKE: --wolke, sonst objekt.json "wolke", sonst <objektordner>/sfm/punkte_modell_<ordnername>.npy (gesamtkette: W, Kamerarahmen wie die K-Dateien),
  sonst die neueste sfm/punkte_modell_*.npy. Zuschnitt auf STL-Huelle vereint mit rahmen_wand (Kamerarahmen) + RAND_M 2 m; Bodenschicht (unterste BODEN_M) weg (das Modell hat
  keinen Boden, sonst entstuende am Wandfuss eine Innenkante, die das Modell nie haben kann). Unterstichprobe auf --n-max Punkte (Saat 0, RAM).
STATUS je Seite (ANNAHMEN, Begruendung):
  MARGE 0,05 (5 pp): konvergenz.py traegt Lauf-zu-Lauf 2 pp bei GLEICHEM Renderer; hier rendern zwei verschiedene Punktquellen (Wolkenrauschen erzeugt
    eigene Knickkanten, das Netz nicht) -> 2,5 x Laufschwelle; je Foto traegt das Vorzeichen nur ~83 % (foto_tor_bezug 17.11.), deshalb Median >= 3 Fotos.
  F1_DATEN 0,45: Messreihe foto_diff 17.11.: ABSICHTLICH FALSCHES Kamera/Foto-Paar ergab F1 0,39-0,68 -> eine Wolke unter 0,45 erklaert die Fotokanten
    nicht besser als ein falsches Paar = keine brauchbaren Daten. ABD_DATEN 0,5: deckt die Wolke weniger als die Haelfte der Modellsilhouette, fehlt
    die Grundlage fuer die Form (Datendecke) unabhaengig vom F1.
  ZUFALLSNIVEAU (Gegenprobe 1122 24.11.: Wolke hatte 2 x so viele Kantenpixel wie das Modell; foto_diff 17.11.: in dichten Fassaden findet jede Kante
    irgendeine Fotokante, falsches Paar F1 0,39-0,68): je Lauf zusaetzlich F1_null = Median-F1 derselben Kantenkarte, um NULLPROBE_M 1,3 / 2,1 m in 4
    Richtungen verschoben (> 3 x tol 0,35 m, zwei Weiten gegen Fenster-Raster); guete = (F1 - F1_null) / (1 - F1_null) (wie Cohens Kappa: 0 = Zufall).
    verlust_zufall = gepaarter Median der Guete-Differenz Wolke - Modell.
  GUETE_MIN 0,1: liegen Wolke UND Modell unter 0,1 ueber Zufall (Kappa-Skala: < 0,2 "kaum Uebereinstimmung"), trennt das grobe F1 auf diesen Fotos
    nichts (Gegenprobe 1122 24.11.: F1 0,26-0,76 lagen alle 0,00-0,05 ueber ihrem verschobenen Zufallswert) -> "nicht trennbar (Zufallsniveau)" statt
    eines Urteils; dann zuerst Kamera-Sitz/tol pruefen, nicht Modell oder Daten beschuldigen.
  verlust >= MARGE UND verlust_zufall >= MARGE -> "Modellierung verliert" (Wolke deutlich besser, auch ueber Zufall: die Daten tragen mehr, als das
    Modell daraus macht);
  sonst F1_wolke < F1_DATEN, Guete_wolke <= 0 oder Abdeckung < ABD_DATEN -> "Daten fehlen" (Fotoauftrag/SfM statt Modellierung);
  sonst verlust UND verlust_zufall <= -MARGE -> "Modell besser als Wolke" (Kantenstufe ergaenzt die Wolke); sonst "gleich". < 3 gepaarte Fotos -> "zu wenig Fotos".
KANTEN-RAUSCHEN (ANNAHME, Gegenprobe 1122 24.11.): die Wolke erzeugte aus verrauschten Normalen einen Teppich kurzer Knickkanten, der in dichter Fototextur
  IMMER eine Fotokante in tol findet (F1 geschoent). Deshalb fuer Modell UND Wolke gleich: PCA-Normalen aus K_NORMALEN 32 Nachbarn und nur Kantenstuecke
  >= MIN_KANTE_M 0,5 m (deutlich ueber der Fotoglaettung 0,18 m; Fenster-/Gesimskanten sind laenger). f1_modell_gleich weicht deshalb vom foto_diff-Standard ab.
Ausgabe: JSON (--json, Standard <aus>/konvergenz_wolke.json) {seiten: {achse: dict(name, f1_wolke, f1_modell_gleich, verlust, abdeckung, n, status, fotos)}}.
Exit 0 = gerechnet, 1 = Aufruf/Daten falsch (keine Wolke, kein Fotosatz), 3 = keine Seite mit Beleg.
Umgebung: /media/oem/scan/venv-seg/bin/python -I tools/konvergenz_wolke.py ... (cv2, trimesh, scipy; KEINE GPU - CUDA_VISIBLE_DEVICES='' wie foto_diff_batch punkt)
"""
import sys, os, json, glob, time, argparse, contextlib, io
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
MARGE = 0.05; F1_DATEN = 0.45; ABD_DATEN = 0.5; N_MIN = 3; RAND_M = 2.0; BODEN_M = 0.3; N_MAX = 3_000_000; K_NORMALEN = 32; MIN_KANTE_M = 0.5; NULLPROBE_M = (1.3, 2.1)
TRENNT_NICHT = "nicht trennbar (Zufallsniveau)"; GUETE_MIN = 0.1
VERLIERT = "Modellierung verliert"; DATEN = "Daten fehlen"; GLEICH = "gleich"; BESSER = "Modell besser als Wolke"; WENIG = "zu wenig Fotos"


def wolke_pfad(obj, od, arg=None):
    if arg: return arg
    if obj.get("wolke"):
        p = obj["wolke"]; root = os.path.dirname(os.path.dirname(od))
        return p if os.path.isabs(p) else os.path.join(root, p)
    p = os.path.join(od, "sfm", f"punkte_modell_{os.path.basename(od)}.npy")
    if os.path.exists(p): return p
    c = sorted(glob.glob(os.path.join(od, "sfm", "punkte_modell_*.npy")), key=os.path.getmtime)
    return c[-1] if c else None


def wolke_laden(pfad, box, n_max=N_MAX, saat=0, boden_m=BODEN_M, block=2_000_000):
    """npy (N,>=3) im Kamerarahmen -> Punkte float32 in box (lo, hi) ohne Bodenschicht, hoechstens n_max (zufaellig, Saat). Blockweise (mmap, RAM)."""
    A = np.load(pfad, mmap_mode="r"); lo, hi = np.asarray(box[0], float), np.asarray(box[1], float); teile = []
    for i in range(0, len(A), block):
        X = np.asarray(A[i:i + block, :3], np.float32); ok = np.all((X >= lo) & (X <= hi), axis=1) & (X[:, 2] >= lo[2] + boden_m); teile.append(X[ok])
    P = np.concatenate(teile) if teile else np.zeros((0, 3), np.float32); n_box = len(P)
    if len(P) > n_max: P = P[np.sort(np.random.default_rng(saat).choice(len(P), n_max, replace=False))]
    return P, dict(pfad=os.path.abspath(pfad), n_gesamt=int(len(A)), n_box=int(n_box), n_genutzt=int(len(P)))


def normalen_pca(P, k=K_NORMALEN, block=200_000):
    """Normale je Punkt = kleinster Eigenvektor der Kovarianz der k Nachbarn (Vorzeichen egal: foto_diff dreht zur Kamera)."""
    from scipy.spatial import cKDTree
    if len(P) < k + 1: return np.tile(np.array([0, 0, 1.0], np.float32), (len(P), 1))
    T = cKDTree(P); N = np.empty_like(P)
    for i in range(0, len(P), block):
        _, nb = T.query(P[i:i + block], k=k, workers=4); Q = P[nb] - P[nb].mean(1, keepdims=True)
        C = np.einsum("nki,nkj->nij", Q, Q); w, v = np.linalg.eigh(C); N[i:i + block] = v[:, :, 0]
    return N


def f1_aus(d):
    sys.path.insert(0, HIER); import konvergenz as KV
    return KV.f1_foto(d)


def guete(f1, f1_null):
    """F1 ueber Zufall: (F1 - F1_null) / (1 - F1_null); None, wenn eines fehlt."""
    if f1 is None or f1_null is None: return None
    return (f1 - f1_null) / max(1e-6, 1.0 - f1_null)


def wolke_status(f1_w, verlust, abd, n, verlust_zufall=None, guete_w=None, guete_m=None):
    """verlust_zufall/guete_w None (alte Aufrufer, keine Nullprobe) -> nur roher Verlust."""
    if n < N_MIN or f1_w is None or verlust is None: return WENIG
    if guete_w is not None and guete_m is not None and max(guete_w, guete_m) < GUETE_MIN: return TRENNT_NICHT
    if verlust >= MARGE and (verlust_zufall is None or verlust_zufall >= MARGE): return VERLIERT
    if f1_w < F1_DATEN or (abd is not None and abd < ABD_DATEN) or (guete_w is not None and guete_w <= 0): return DATEN
    if verlust <= -MARGE and (verlust_zufall is None or verlust_zufall <= -MARGE): return BESSER
    return GLEICH


def seiten_auswerten(S, je):
    """S = Fotosatz, je = {foto: dict(w, m, abd)} -> {achse: Seitenwerte}."""
    out = {}
    for ax, s in S["seiten"].items():
        fv = {nr: je[nr] for nr in s["fotos"] if nr in je}
        par = [(e["w"], e["m"]) for e in fv.values() if e.get("w") is not None and e.get("m") is not None]
        fw = [e["w"] for e in fv.values() if e.get("w") is not None]; fm = [e["m"] for e in fv.values() if e.get("m") is not None]
        ab = [e["abd"] for e in fv.values() if e.get("abd") is not None]
        f1w = float(np.median(fw)) if fw else None; f1m = float(np.median(fm)) if fm else None
        vl = float(np.median([w - m for w, m in par])) if par else None; abd = float(np.median(ab)) if ab else None
        gp = [(guete(e["w"], e.get("w0")), guete(e["m"], e.get("m0"))) for e in fv.values() if e.get("w") is not None and e.get("m") is not None]
        gp = [(a, b) for a, b in gp if a is not None and b is not None]
        vz = float(np.median([a - b for a, b in gp])) if gp else None
        gw = float(np.median([a for a, _ in gp])) if gp else None; gm = float(np.median([b for _, b in gp])) if gp else None
        r4 = lambda x: None if x is None else round(x, 4)
        out[ax] = dict(name=s.get("name", ax), f1_wolke=r4(f1w), f1_modell_gleich=r4(f1m), verlust=r4(vl), guete_wolke=r4(gw), guete_modell=r4(gm),
                       verlust_zufall=r4(vz), abdeckung=None if abd is None else round(abd, 3), n=len(par),
                       status=wolke_status(f1w, vl, abd, len(par), vz if gp else None, gw if gp else None, gm if gp else None), fotos=fv)
    return out


def messen(objekt, fotos, aus, P, N, stl=None, log=None):
    """Je Foto Modell- und Wolkenlauf (foto_diff im selben Prozess) -> {foto: dict(w, m, abd, fehler?)}."""
    os.environ["FD_RASTER"] = "0"; os.environ.pop("FD_GPU", None); os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.setdefault("FD_LEER_OK", "1")
    import render_kern as RK; RK._T = False
    import foto_diff as FD
    je = {}
    for nr in fotos:
        t0 = time.time(); e = {}
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                FD._PUNKTE = dict(merken=True, min_kante_m=MIN_KANTE_M, nullprobe_m=NULLPROBE_M)
                em = FD.main([objekt, nr, "--punkte", "--aus", os.path.join(aus, "modell", nr)] + (["--stl", stl] if stl else []))
                bz = FD._PUNKTE.get("bezug"); m0 = FD._PUNKTE.get("f1_null")
                if bz is None: raise RuntimeError("Modelllauf ohne Bezug (Kamera/Foto fehlt?)")
                FD._PUNKTE = dict(P=P, N=N, bezug=bz, min_kante_m=MIN_KANTE_M, nullprobe_m=NULLPROBE_M)
                ew = FD.main([objekt, nr, "--punkte", "--aus", os.path.join(aus, "wolke", nr)] + (["--stl", stl] if stl else []))
                se = FD._PUNKTE.get("sil_eigen"); w0 = FD._PUNKTE.get("f1_null")
            ms = bz["sil_f"] > 0
            e = dict(m=None if f1_aus(em) is None else round(f1_aus(em), 4), w=None if f1_aus(ew) is None else round(f1_aus(ew), 4),
                     abd=round(float((se[ms] > 0).mean()), 3) if se is not None and ms.any() else None,
                     m0=None if m0 is None else round(m0, 4), w0=None if w0 is None else round(w0, 4),
                     p_w=ew.get("anteil_modellkanten_ohne_foto"), r_w=ew.get("anteil_fotokanten_ohne_modell"),
                     p_m=em.get("anteil_modellkanten_ohne_foto"), r_m=em.get("anteil_fotokanten_ohne_modell"), sek=round(time.time() - t0, 1))
            if log: log.write(buf.getvalue()[-4000:])
        except Exception as ex:
            e = dict(fehler=f"{type(ex).__name__}: {str(ex)[:160]}")
        finally:
            FD._PUNKTE = None
        je[nr] = e; print(f"  {nr}: modell {e.get('m')} (Zufall {e.get('m0')}) wolke {e.get('w')} (Zufall {e.get('w0')}) abdeckung {e.get('abd')} ({e.get('sek', e.get('fehler'))})", flush=True)
    return je


def stl_huelle_kamerarahmen(objekt, obj, root, kk, stl=None):
    """Zuschnitt (lo, hi) in Metern im Kamerarahmen: STL-Huelle (wie foto_diff._netz: Massstab, Zentrierung, rahmen_verschiebung der K-Datei) VEREINT mit
    dem Grundriss objekt.json rahmen_wand (0..hoehe_m), + RAND_M. Nur die STL-Huelle schnitte genau das weg, was dem Modell fehlt (Vorbau ueber die Huelle
    hinaus = der Fall 'Modellierung verliert')."""
    import foto_diff as FD
    m = FD._netz_raster(stl or os.path.join(root, obj["stl"]), obj, kk); lo, hi = np.array(m.bounds[0], float), np.array(m.bounds[1], float); FD._NETZ_R.clear()
    rw = obj.get("rahmen_wand") or {}
    if all(k in rw for k in ("u0", "u1", "v0", "v1")):
        lo = np.minimum(lo, [float(rw["u0"]), float(rw["v0"]), lo[2]]); hi = np.maximum(hi, [float(rw["u1"]), float(rw["v1"]), float(obj.get("hoehe_m") or hi[2])])
    return lo - RAND_M, hi + RAND_M


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True); ap.add_argument("--fotosatz"); ap.add_argument("--wolke")
    ap.add_argument("--stl"); ap.add_argument("--n-max", type=int, default=N_MAX); ap.add_argument("--je-seite", type=int, default=0, help="nur die ersten K Fotos je Seite (Probe)")
    ap.add_argument("--json"); a = ap.parse_args(argv)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); os.makedirs(a.aus, exist_ok=True)
    import konvergenz as KV
    sp = a.fotosatz or os.path.join(root, obj.get("audit") or os.path.relpath(os.path.join(od, "audit"), root), "konvergenz_fotosatz.json")
    if not os.path.exists(sp):                                                                  # Probe ohne Kettenlauf: Satz nach derselben Regel anlegen (nur in --aus)
        fotos_dir = os.path.join(root, obj.get("fotos_dir", "")); W_ = KV.waende(obj, None); kand = KV.kandidaten(od, obj, W_, fotos_dir)
        S = KV.fotosatz_anlegen(kand, W_, KV.K_STD, fotos_dir, "konvergenz_wolke_probe"); sp = os.path.join(a.aus, "konvergenz_fotosatz.json"); json.dump(S, open(sp, "w"), indent=1)
        print(f"HINWEIS: kein Fotosatz - nach konvergenz-Regel angelegt: {sp}")
    S = json.load(open(sp))
    if a.je_seite: S = dict(S, seiten={ax: dict(s, fotos=s["fotos"][:a.je_seite]) for ax, s in S["seiten"].items()})
    fotos = sorted({nr for s in S["seiten"].values() for nr in s["fotos"]})
    wp = wolke_pfad(obj, od, a.wolke)
    if not wp or not os.path.exists(wp): print(f"FEHLER: keine dichte Wolke ({wp})"); return 1
    if not fotos: print("FEHLER: Fotosatz leer"); return 1
    kp = os.path.join(od, "messprotokoll", f"K-{fotos[0]}.json"); kk = (json.load(open(kp)).get("kamera") or {}) if os.path.exists(kp) else {}
    box = stl_huelle_kamerarahmen(a.objekt, obj, root, kk, a.stl); t0 = time.time()
    P, info = wolke_laden(wp, box, a.n_max); info.update(box=[np.round(box[0], 2).tolist(), np.round(box[1], 2).tolist()], rand_m=RAND_M, boden_m=BODEN_M)
    if len(P) < 1000: print(f"FEHLER: Wolke im Modellbereich fast leer ({len(P)} Punkte, {info})"); return 1
    N = normalen_pca(P); info["sek_laden_normalen"] = round(time.time() - t0, 1)
    print(f"WOLKE {wp}: {info['n_gesamt']} Punkte, {info['n_box']} im Modellbereich, {info['n_genutzt']} genutzt ({info['sek_laden_normalen']} s inkl. Normalen)", flush=True)
    with open(os.path.join(a.aus, "foto_diff.log"), "w") as log: je = messen(a.objekt, fotos, a.aus, P, N, a.stl, log)
    seiten = seiten_auswerten(S, je)
    erg = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), fotosatz=os.path.abspath(sp), wolke=info, schwellen=dict(marge=MARGE, f1_daten=F1_DATEN, abdeckung_daten=ABD_DATEN, n_min=N_MIN, guete_min=GUETE_MIN, min_kante_m=MIN_KANTE_M, k_normalen=K_NORMALEN, nullprobe_m=list(NULLPROBE_M)),
               seiten=seiten)
    jp = a.json or os.path.join(a.aus, "konvergenz_wolke.json"); json.dump(erg, open(jp + ".tmp", "w"), indent=1, ensure_ascii=False); os.replace(jp + ".tmp", jp)
    print("VERLUST dichte Wolke -> Modell je Seite (gepaart, Punktfassung):")
    for ax, e in seiten.items(): print(f"  {e['name']}: wolke {e['f1_wolke']} modell {e['f1_modell_gleich']} verlust {e['verlust']} | ueber Zufall: wolke {e['guete_wolke']} modell {e['guete_modell']} verlust {e['verlust_zufall']} | abdeckung {e['abdeckung']} (n {e['n']}) -> {e['status']}")
    print(f"Bericht: {jp}")
    return 0 if any(e["n"] for e in seiten.values()) else 3


if __name__ == "__main__":
    sys.exit(main())

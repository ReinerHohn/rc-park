#!/usr/bin/env python3
"""param_suche.py - GENERISCH: einen Generator-Parameter gegen die Fotos einstellen (Plan 4.11.: automatische Korrektur, Punkt 6a).

Je Probewert: Generator (objekt.json['generator']) mit BAUTEIL_PARAM={bauteil: {param: wert}} in eine Probe-STL bauen (Objekt bleibt unberuehrt:
STL_NAME/ELEMENTE_AUS umgelenkt), dann foto_diff.py auf einer festen Fotoauswahl (nur Kameras mit Tor), Kosten = Mittel von kosten_param
(foto_diff kosten_param: gekappter Kantenabstand beide Richtungen / tol in einer FESTEN Maske je Foto, Umriss eingeschlossen; 0 = deckungsgleich). Grob-Raster, dann Feinraster um das Minimum; Unsicherheit aus der
Kostenkruemmung (Parabel) und der Streuung der Einzelfoto-Minima.
  /media/oem/scan/venv-seg/bin/python -I tools/param_suche.py modelle/<obj>/objekt.json --bauteil rumpf_lod2 --param first_versatz_m --werte -3:1:0.5 [--fotos 12] [--fein]
  Beweis: --bilder <ordner> (synthetische Pruefbilder <nr>.jpg, test_param_suche.py)
Ergebnis: <audit>/param_suche_<bauteil>_<param>.json (+ Tabelle); schreibt NICHTS in objekt.json - Uebernahme ist ein eigener Schritt mit Quelle.
GRENZEN: misst nur, was Kanten in den Fotos zeigen (Laser-/Foto-Blindheit beachten, Regel 4); Parameter einzeln (keine Kopplung);
Fotoauswahl gleichmaessig ueber die Tor-Kameras, Verdecker per Tiefenkarte (foto_diff --tiefen auto).
"""
import sys, os, json, glob, re, argparse, subprocess, time, tempfile, numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); PY = "/media/oem/scan/venv-seg/bin/python"


def fotos_waehlen(od, n, ohne_nacht=False):
    """ohne_nacht (2026-11-05, sonne.json aus sonne_fotos.py): Nacht-/Daemmerungsfotos (Sonne <= 0 Grad) nicht bewerten - Flutlicht-Kanten sind keine Tagesgeometrie.
    Standard aus, damit laufende Ketten ihre Fotoliste behalten (Plan-Schluessel 'ohne_nacht' in qualitaetsstufen)."""
    nacht = set()
    if ohne_nacht and os.path.exists(os.path.join(od, "sonne.json")):
        nacht = {k for k, v in json.load(open(os.path.join(od, "sonne.json")))["fotos"].items() if v["urteil"] == "Nacht"}
    ok = []
    for p in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        k = json.load(open(p)).get("kamera", {})
        if k and ((k.get("buendel_tor") or {}).get("ok") or (k.get("lod2_tor") or {}).get("ok") or k.get("brennweite_quelle") not in (None, "buendel")):
            if os.path.basename(p)[2:-5] not in nacht: ok.append(os.path.basename(p)[2:-5])
    if n is None or len(ok) <= n: return ok                                                      # n=None: ALLE kalibrierten Fotos (S3 Konvergenzschleife)
    return [ok[int(round(i))] for i in np.linspace(0, len(ok) - 1, n)]                        # gleichmaessig (Nummern ~ Aufnahmeorte gemischt), keine Auswahl nach Passung (sonst Selbstbestaetigung)


FEST = {}                                                                                         # --fest (main)


def bauen(obj, bauteil, param, wert, stl_name, elemente_aus, quelle):
    cmd = obj["generator"]; cmd = re.sub(r"STL_NAME=\S+", f"STL_NAME={stl_name}", cmd) if "STL_NAME=" in cmd else f"STL_NAME={stl_name} " + cmd
    bp = json.loads(json.dumps(FEST)); bp.setdefault(bauteil, {}).update({param: wert, "quelle": quelle})   # feste Werte frueherer Schritte + gesuchter Wert
    env = dict(os.environ, BAUTEIL_PARAM=json.dumps(bp), ELEMENTE_AUS=elemente_aus)
    r = subprocess.run(["bash", "-c", cmd.replace("~", os.path.expanduser("~"))], cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit(f"Generator fehlgeschlagen ({param}={wert}): {(r.stderr or r.stdout)[-500:]}")
    return os.path.join("modelle", "stl", stl_name)


PUNKTE_DIR = f"/dev/shm/rcpark_netz_{os.getpid()}"                                           # geteilte Oberflaechenabtastung der Arbeiter (foto_diff FD_PUNKTE_DIR)


def arbeiter_zahl(n_aufgaben, gb_je=2.2, reserve_gb=2.0):
    """So viele Prozesse wie moeglich (Nutzerregel: immer maximal parallel), begrenzt durch Kerne und FREIEN RAM (foto_diff gemessen 2,0 GB Eigenspeicher + 0,4 GB geteilte Punkte je STL in /dev/shm; Spitze im Renderkern)."""
    try: frei = int(next(l for l in open("/proc/meminfo") if l.startswith("MemAvailable")).split()[1]) / 1e6
    except Exception: frei = 8.0
    n = min(n_aufgaben, os.cpu_count() or 1, int((frei - reserve_gb) // gb_je))
    if os.environ.get("FD_GPU") == "1":                                                            # GPU-Fassung: je Arbeiter ~0,5 GB CUDA-Start + 0,2 GB Punkte + Bildfelder -> ANNAHME 0,9 GB Grafikspeicher
        try: vfrei = float(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0]) / 1024
        except Exception: vfrei = 4.0
        n = min(n, int((vfrei - 0.5) // (0.9 if os.environ.get("FD_RASTER") == "0" else 1.6)))   # Raster: gemessen 1,0 GB Spitze je Aufruf + CUDA-Start (Kaufhaus 004, 2026-11-04; 0,9 -> Speicherueberlauf)
    return max(1, n)


_BUDGET = None


def _budget_init(cond, belegt, gesamt):
    global _BUDGET; _BUDGET = (cond, belegt, gesamt)


def _vram_bedarf(args):
    """0,5 GB + 0,2 GB je Megapixel, max 7,5 (gemessen 20 MP 4,3-4,6 GB; qualitaetsstufen.vram_budget)."""
    try:
        import PIL.Image
        if "--bild" in args: p = args[args.index("--bild") + 1]
        else: obj = json.load(open(args[0])); p = sorted(glob.glob(os.path.join(ROOT, obj["fotos_dir"], args[1] + "_*")))[0]
        w, h = PIL.Image.open(p).size; return min(7.5, 0.5 + 0.2 * w * h / 1e6)
    except Exception: return 2.0


def _fd_aufgabe(t):
    """Grafikspeicher-Budget (2026-11-05: null5 7/33 Fotos Speicherueberlauf parallel): erst starten, wenn der Bedarf ins freie Budget passt; ein Foto ueber dem Budget laeuft allein."""
    if _BUDGET is None or _BUDGET[2] is None: return _fd_aufgabe_kern(t)
    cond, belegt, gesamt = _BUDGET; b = _vram_bedarf(t[0])
    with cond:
        while belegt.value > 0 and belegt.value + b > gesamt: cond.wait()
        belegt.value += b
    try: return _fd_aufgabe_kern(t)
    finally:
        with cond: belegt.value -= b; cond.notify_all()


def _fd_aufgabe_kern(t):
    """Eine foto_diff-Bewertung im Pool-Prozess (Importe + Netzabtastung je Prozess und STL einmal; Ergebnis bitgleich zum Einzelaufruf)."""
    args, jp = t
    sys.path.insert(0, TOOLS); import foto_diff as FD, contextlib, io
    try:
        with contextlib.redirect_stdout(io.StringIO()): FD.main(args)
    except SystemExit as e:
        if e.code not in (0, 1, None): return jp, f"Abbruch {e.code}"
    except Exception as e: return jp, f"{type(e).__name__}: {e}"
    return jp, None


def bewerten_viele(pool, objp, fotos, stls, aus_fn, bilder, extra, masken=None, maske_aus_fn=None):
    """Alle (Probewert x Foto) gleichzeitig in den Pool. stls: {w: stl}; Rueckgabe {w: {nr: kosten}}."""
    auf = []
    for w, stl in stls.items():
        for nr in fotos:
            a = aus_fn(w, nr); os.makedirs(a, exist_ok=True)
            args = [objp, nr, "--stl", os.path.join(ROOT, stl), "--aus", a] + extra + (["--bild", os.path.join(bilder, f"{nr}.jpg")] if bilder else [])
            if masken: args += ["--bewertung-maske", os.path.join(masken, f"{nr}.png")]
            if maske_aus_fn: args += ["--maske-aus", maske_aus_fn(w, nr)]
            auf.append(((args, os.path.join(a, f"foto_diff_{nr}.json")), w, nr))
    k = {w: {} for w in stls}; rest = {w: len(fotos) for w in stls}
    for (jp, fehler), (_, w, nr) in zip(pool.imap(_fd_aufgabe, [x[0] for x in auf]), auf):        # geordnet: Probewert fuer Probewert fertig -> geteilte Punkte sofort freigeben
        rest[w] -= 1
        if rest[w] == 0 and PUNKTE_DIR:
            for q in glob.glob(os.path.join(PUNKTE_DIR, os.path.basename(stls[w]) + "_*")): os.remove(q)
        if fehler: print(f"    {w:+.3f} {nr}: foto_diff {fehler}"); continue
        e = json.load(open(jp)); v = e.get("kosten_param") if masken else (e.get("versatz") or {}).get("kosten0")
        if v is not None: k[w][nr] = v
    return k


def bauen_viele(obj, bauteil, param, werte, name_fn, elem_fn, quelle):
    """Generator fuer alle Werte GLEICHZEITIG (eigene STL + elemente.json je Wert, keine gemeinsame Zwischendatei; baukasten_gen schreibt nur diese zwei)."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max(1, min(len(werte), os.cpu_count() or 1))) as ex:
        return dict(zip(werte, ex.map(lambda w: bauen(obj, bauteil, param, w, name_fn(w), elem_fn(w), quelle), werte)))


def parabel(xs, ys):
    """Minimum und Kruemmung einer Parabel durch das beste Raster-Tripel (Unsicherheit ~ Breite, in der die Kosten um 1 % des Minimums steigen)."""
    i = int(np.argmin(ys))
    if i == 0 or i == len(xs) - 1: return float(xs[i]), None, "am Rand des Rasters"
    a, b, c = np.polyfit(xs[i - 1:i + 2], ys[i - 1:i + 2], 2)
    if a <= 0: return float(xs[i]), None, "nicht konvex"
    xm = -b / (2 * a); ym = c - b * b / (4 * a); return float(xm), float(np.sqrt(0.01 * max(ym, 1e-9) / a)), "ok"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--bauteil", required=True); ap.add_argument("--param", required=True)
    ap.add_argument("--werte", required=True, help="von:bis:schritt oder Liste a,b,c"); ap.add_argument("--fotos", type=int, default=12); ap.add_argument("--fotoliste")
    ap.add_argument("--fein", action="store_true", help="nach dem Grobraster 5 Werte im Abstand schritt/4 um das Minimum"); ap.add_argument("--bilder"); ap.add_argument("--aus")
    ap.add_argument("--fd", default="", help="weitere foto_diff-Argumente"); ap.add_argument("--fest", default="{}", help="feste Parameter anderer Bauteile/Schritte als JSON {bauteil: {param: wert, quelle}} (qualitaetsstufen.py)"); ap.add_argument("--ergebnis-hier", action="store_true", help="Ergebnis-JSON in --aus statt ins Objekt-Audit (Suchschritte schreiben nicht ins Objekt)"); ap.add_argument("--cpu", action="store_true", help="CPU-Fassung von foto_diff (Standard GPU seit 2026-11-04: test_gpu_gleichwertig Kaufhaus+Martinstor, test_foto_diff T0-T6b, test_param_suche bestanden)"); a = ap.parse_args()
    global FEST; FEST = json.loads(a.fest)
    if not a.cpu: os.environ["FD_GPU"] = "1"; os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")   # weniger Zerstueckelung im Grafikspeicher der Arbeiter
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp)
    if ":" in a.werte: v0, v1, st = [float(x) for x in a.werte.split(":")]; werte = list(np.round(np.arange(v0, v1 + st / 2, st), 4))
    else: werte = [float(x) for x in a.werte.split(",")]; st = float(np.min(np.diff(sorted(werte)))) if len(werte) > 1 else 0.25
    fotos = a.fotoliste.split(",") if a.fotoliste else fotos_waehlen(od, a.fotos)
    if not fotos: raise SystemExit("keine Fotos mit bestandenem Kamera-Tor")
    aus = a.aus or tempfile.mkdtemp(prefix=f"param_suche_{a.param}_", dir="/media/oem/scan/rc-park_null"); os.makedirs(aus, exist_ok=True)
    quelle = f"param_suche.py Probelauf ({a.param})"; tab = {}; t0 = time.time(); extra = a.fd.split()
    print(f"param_suche {a.bauteil}.{a.param}: {len(werte)} Werte x {len(fotos)} Fotos ({','.join(fotos)}) -> {aus}", flush=True)

    import multiprocessing as mp, cv2
    n_ar = arbeiter_zahl(len(werte) * len(fotos)); os.environ["FD_PUNKTE_DIR"] = PUNKTE_DIR; ctx_ = mp.get_context("spawn")    # spawn: kein geerbter CUDA-Zustand
    gesamt = None
    if os.environ.get("FD_GPU") == "1":
        try: gesamt = float(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0]) / 1024 - 0.7
        except Exception: gesamt = None
    pool = ctx_.Pool(n_ar, initializer=_budget_init, initargs=(ctx_.Condition(), ctx_.Value("d", 0.0), gesamt))
    print(f"  {n_ar} Arbeitsprozesse ({os.cpu_count()} Kerne, RAM-begrenzt)", flush=True)

    def probe(ws):
        ws = [float(round(w, 4)) for w in ws]; ws = [w for i, w in enumerate(ws) if w not in tab and w not in ws[:i]]
        if not ws: return
        stls = bauen_viele(obj, a.bauteil, a.param, ws, lambda w: f"_probe_{os.path.basename(od)}_{a.param}_{w:+.3f}.stl", lambda w: os.path.join(aus, f"elemente_{w:+.3f}.json"), quelle)
        k = bewerten_viele(pool, objp, fotos, stls, lambda w, nr: os.path.join(aus, f"w{w:+.3f}", nr), a.bilder, extra, masken=md)
        for w in ws:
            tab[w] = k[w]; print(f"  {a.param} = {w:+.3f}: Kosten {np.mean(list(k[w].values())):.4f} ({len(k[w])} Fotos)  [{time.time() - t0:.0f} s]", flush=True)
            try: os.remove(os.path.join(ROOT, stls[w]))
            except OSError: pass

    # Feste Bewertungsmaske je Foto (2026-11-04): Vereinigung der Silhouetten der Rasterextreme + Rand. Vorher kosten0 = Fotokanten nur in der
    # Silhouette des JEWEILIGEN Probemodells -> Bereich haengt vom Parameter ab (Beweis Kaufhaus Wahrheit -0,8 -> -1,11, nach unten gezogen).
    md = os.path.join(aus, "masken"); os.makedirs(md, exist_ok=True); ext = [min(werte), max(werte)]
    for j in (0, 1): os.makedirs(os.path.join(md, f"m{j}"), exist_ok=True)
    stls = bauen_viele(obj, a.bauteil, a.param, ext, lambda w: f"_maske_{os.path.basename(od)}_{a.param}_{w:+.3f}.stl", lambda w: os.path.join(aus, f"elemente_maske{w:+.3f}.json"), quelle)
    bewerten_viele(pool, objp, fotos, stls, lambda w, nr: os.path.join(aus, f"maske{ext.index(w)}", nr), a.bilder, extra, maske_aus_fn=lambda w, nr: os.path.join(md, f"m{ext.index(w)}", f"{nr}.png"))
    for st_ in stls.values(): os.remove(os.path.join(ROOT, st_))
    for nr in fotos:
        m0, m1 = (cv2.imread(os.path.join(md, f"m{j}", f"{nr}.png"), cv2.IMREAD_GRAYSCALE) for j in (0, 1))
        if m0 is None and m1 is None: print(f"  Foto {nr}: keine Maske (Modell nicht im Bild) - nicht bewertet", flush=True); continue
        cv2.imwrite(os.path.join(md, f"{nr}.png"), m0 if m1 is None else m1 if m0 is None else np.maximum(m0, m1))
    print(f"  Bewertungsmasken fertig [{time.time() - t0:.0f} s]", flush=True)
    probe(werte)
    if a.fein:
        xs = sorted(tab); i = int(np.argmin([np.mean(list(tab[x].values())) for x in xs]))
        probe(list(np.arange(xs[i] - st / 2, xs[i] + st / 2 + 1e-9, st / 4)))
    pool.close(); pool.join(); import shutil; shutil.rmtree(PUNKTE_DIR, ignore_errors=True)
    gemeinsam = sorted(set.intersection(*[set(k) for k in tab.values()]))                     # nur Fotos, die bei JEDEM Wert bewertet wurden
    xs = np.array(sorted(tab)); ys = np.array([np.mean([tab[x][nr] for nr in gemeinsam]) for x in xs])
    xm, unsich, zustand = parabel(xs, ys)
    # Deutlichkeit (2026-11-04): gepaarter t-Wert je Rasterwert gegen den besten (je Foto Mehrkosten). Kaufhaus spitze_m: Kosten 0,961-0,969 ohne
    # Verlauf, Parabel meldete trotzdem 'ok' +-0,12. Jetzt 'ok' nur, wenn das Minimum LINKS UND RECHTS von Werten mit t >= T_DEUTLICH eingegrenzt ist.
    C_ = np.array([[tab[x][nr] for nr in gemeinsam] for x in xs]); ib = int(np.argmin(C_.mean(1))); tw = []
    for i in range(len(xs)):
        dd = C_[i] - C_[ib]; se = dd.std(ddof=1) / np.sqrt(len(dd)) if len(dd) > 1 else 0.0
        tw.append(None if i == ib or se == 0 else round(float(dd.mean() / se), 2))
    T_DEUTLICH = 2.0                                                                               # ANNAHME: ~95 % (12 Fotos); Statistik offen (Liste Punkt 5)
    links = any(t is not None and t >= T_DEUTLICH for t in tw[:ib]); rechts = any(t is not None and t >= T_DEUTLICH for t in tw[ib + 1:])
    if zustand == "ok" and not (links and rechts): zustand = "flach (Minimum nicht beidseitig deutlich, t < 2)"
    je_foto = {nr: float(xs[int(np.argmin([tab[x][nr] for x in xs]))]) for nr in gemeinsam}     # Einzelfoto-Minimum: Streuung = Uneinigkeit der Fotos
    streu = float(np.std(list(je_foto.values()))) if je_foto else None
    erg = dict(bauteil=a.bauteil, param=a.param, fotos=gemeinsam, werte=xs.tolist(), kosten=[round(float(y), 5) for y in ys], bester_wert=round(xm, 3), unsicherheit_kruemmung=None if unsich is None else round(unsich, 3),
               zustand=zustand, fest=FEST, t_gegen_bestes=tw, kosten_je_foto={f'{x:+.3f}': tab[x] for x in xs}, je_foto_minimum=je_foto, streuung_fotos=None if streu is None else round(streu, 3), sekunden=round(time.time() - t0), synthetisch=bool(a.bilder), arbeit=aus)
    ad = os.path.join(ROOT, obj.get("audit", os.path.relpath(od, ROOT) + "/audit")); os.makedirs(ad, exist_ok=True)
    pf = os.path.join(aus if (a.bilder or a.ergebnis_hier) else ad, f"param_suche_{a.bauteil}_{a.param}.json"); json.dump(erg, open(pf, "w"), indent=1)
    print(f"ERGEBNIS {a.param} = {xm:+.3f} ({zustand}; Kruemmung +-{unsich if unsich is None else round(unsich, 3)}, Streuung Einzelfotos {streu if streu is None else round(streu, 3)}) -> {pf}")


if __name__ == "__main__":
    main()

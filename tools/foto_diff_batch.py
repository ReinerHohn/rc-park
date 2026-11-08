#!/usr/bin/env python3
"""foto_diff_batch.py - foto_diff fuer MEHRERE Fotos (und optional mehrere Kameravarianten / Netze) in EINEM Prozess (Register BS8).
  venv-seg/bin/python -I tools/foto_diff_batch.py modelle/<obj>/objekt.json --aus DIR --stl NAME=pfad.stl [--stl ...] --fotos 000,004,... \
      [--maske-dir DIR (<nr>.png) | --maske-muster 'DIR/{nr}.png'] [--modus punkt|raster] [--threads 3] [--k-ordner NAME=DIR ...] [--fd-arg=--glaettung=0.18]
Aenderungen gegenueber 'foto_diff.py je Foto als eigener Prozess' (foto_diff.py selbst bleibt UNVERAENDERT, wird importiert, main() je Foto aufgerufen -> gleiche Rechnung):
  - Importe/Netz/Oberflaechen-Stichprobe EINMAL je Prozess (foto_diff._NETZ), optional zusaetzlich auf Platte (--punkte-cache = FD_PUNKTE_DIR, bitgleich, Saat 0) -> naechster Prozess spart 4-5 s.
  - Punktmodus: torch wird NICHT importiert (render_kern._T = False; entspricht CUDA_VISIBLE_DEVICES='' ohne den 8-s-Import).
  - Fotos laufen in --threads Faeden (Punktmodus: CPU-Schritte ueberlappen; Raster: GPU-Raster des einen Fotos laeuft waehrend CPU-Schritte (Kosten, Distanzen) des anderen).
  - Raster: VRAM-Deckel per torch.cuda.set_per_process_memory_fraction aus JOB_GPU_MB (Standard 1500 MiB).
  - Kameravarianten: --k-ordner NAME=DIR: DIR/messprotokoll/K-<nr>.json ersetzt die K-Datei (sonst Original); Ausgabe je Variante in eigenem Ordner.
Ausgabe: <aus>/<name>/<nr>/foto_diff_<nr>.json (+ jpg) - dieselben Felder wie foto_diff (kosten_lr, versatz, modellkanten_px ...) wie modell_wettbewerb p2/<kandidat>/<nr>.
Zusammenfassung: <aus>/batch_ergebnis.json (name|nr -> kosten_lr, modellkanten_px, sek)."""
import sys, os, json, time, threading, argparse
TOOLS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, TOOLS)


def _mit_wiederholung(fn, argv_, modus, n=3, pause=8.0):
    """Raster: CUDA-OOM (GPU wird mit anderen Jobs geteilt) -> Zwischenspeicher leeren, warten, bis zu n-mal neu. Rechnung selbst unveraendert."""
    for i in range(n):
        try: return fn(argv_)
        except BaseException as ex:
            if modus != "raster" or "OutOfMemory" not in type(ex).__name__ or i == n - 1: raise
            import torch, gc; gc.collect(); torch.cuda.empty_cache(); time.sleep(pause)


def lauf(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True)
    ap.add_argument("--stl", action="append", required=True, help="NAME=pfad.stl (mehrfach)"); ap.add_argument("--fotos", required=True)
    ap.add_argument("--maske-dir"); ap.add_argument("--maske-muster"); ap.add_argument("--modus", choices=["punkt", "raster"], default="punkt")
    ap.add_argument("--threads", type=int, default=3); ap.add_argument("--k-ordner", action="append", default=[]); ap.add_argument("--punkte-cache")
    ap.add_argument("--fd-arg", action="append", default=[]); a = ap.parse_args(argv)
    if a.modus == "punkt":
        os.environ["FD_RASTER"] = "0"; os.environ.pop("FD_GPU", None); os.environ["CUDA_VISIBLE_DEVICES"] = ""
    else:
        os.environ["FD_RASTER"] = "1"; os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    if a.punkte_cache and a.modus == "punkt": os.environ["FD_PUNKTE_DIR"] = a.punkte_cache
    import render_kern as RK
    if a.modus == "punkt": RK._T = False                                                       # kein torch-Import im Punktmodus (gleiches Verhalten wie ohne CUDA)
    else:
        import torch; mb = float(os.environ.get("JOB_GPU_MB", "1500")); tot = torch.cuda.get_device_properties(0).total_memory / 2**20
        torch.cuda.set_per_process_memory_fraction(min(1.0, mb / tot))
    import fehlteile_finden as FF, foto_diff as FD
    tl = threading.local(); orig_k = FF.k_datei; kdirs = dict(k.split("=", 1) for k in a.k_ordner)
    def k_datei(objp, obj, root, nr):                                                           # Kameravariante je Faden
        d = getattr(tl, "kdir", None)
        if d:
            p = os.path.join(d, "messprotokoll", f"K-{nr}.json")
            if os.path.exists(p): return p
        return orig_k(objp, obj, root, nr)
    FF.k_datei = k_datei
    stls = [s.split("=", 1) for s in a.stl]; fotos = a.fotos.split(","); varianten = [("", None)] if not kdirs else list(kdirs.items())
    aufg = [(n, p, nr, vn, vd) for (n, p) in stls for (vn, vd) in varianten for nr in fotos]
    erg = {}; lock = threading.Lock(); it = iter(aufg)
    def maske(nr): return a.maske_muster.format(nr=nr) if a.maske_muster else (os.path.join(a.maske_dir, nr + ".png") if a.maske_dir else None)
    def arbeiter():
        while True:
            with lock:
                t = next(it, None)
            if t is None: return
            n, p, nr, vn, vd = t; tl.kdir = vd; name = n + (("@" + vn) if vn else ""); out = os.path.join(a.aus, name, nr); t0 = time.time()
            argv_ = [a.objekt, nr, "--stl", p, "--aus", out] + (["--bewertung-maske", maske(nr)] if maske(nr) else []) + a.fd_arg
            try: e = _mit_wiederholung(FD.main, argv_, a.modus)
            except BaseException as ex:                                                          # z. B. CUDA-OOM: Aufgabe als Fehler vermerken, Rest laeuft weiter
                with lock: erg[f"{name}|{nr}"] = dict(fehler=type(ex).__name__ + ": " + str(ex)[:120]); 
                try:
                    import torch; torch.cuda.empty_cache()
                except Exception: pass
                continue
            dt = time.time() - t0
            with lock: erg[f"{name}|{nr}"] = dict(kosten_lr=e.get("kosten_lr"), modellkanten_px=e.get("modellkanten_px"), versatz_m=(e.get("versatz") or {}).get("versatz_m"), sek=round(dt, 2))
    # erste Aufgabe allein (Netz-Stichprobe/Importe einmal), danach parallel
    t0 = time.time()   # Warmlauf = erste Aufgabe allein (Importe/Stichprobe einmal, kein _NETZ.clear()-Wettlauf), Rest im Faden-Pool
    it = iter(aufg); n, p, nr, vn, vd = next(it); tl.kdir = vd; name = n + (("@" + vn) if vn else ""); t1 = time.time()
    try:
        e = _mit_wiederholung(FD.main, [a.objekt, nr, "--stl", p, "--aus", os.path.join(a.aus, name, nr)] + (["--bewertung-maske", maske(nr)] if maske(nr) else []) + a.fd_arg, a.modus)
        erg[f"{name}|{nr}"] = dict(kosten_lr=e.get("kosten_lr"), modellkanten_px=e.get("modellkanten_px"), versatz_m=(e.get("versatz") or {}).get("versatz_m"), sek=round(time.time() - t1, 2))
    except BaseException as ex: erg[f"{name}|{nr}"] = dict(fehler=type(ex).__name__ + ": " + str(ex)[:120])
    ths = [threading.Thread(target=arbeiter) for _ in range(max(1, a.threads))]
    [t.start() for t in ths]; [t.join() for t in ths]
    gesamt = round(time.time() - t0, 2); os.makedirs(a.aus, exist_ok=True)
    json.dump(dict(gesamt_sek=gesamt, n=len(aufg), modus=a.modus, threads=a.threads, ergebnisse=erg), open(os.path.join(a.aus, "batch_ergebnis.json"), "w"), indent=1)
    print(f"foto_diff_batch: {len(aufg)} Aufgaben in {gesamt} s ({gesamt / len(aufg):.2f} s je Foto)"); return erg


if __name__ == "__main__":
    lauf()

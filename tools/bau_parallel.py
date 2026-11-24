#!/usr/bin/env python3
"""bau_parallel.py - unabhaengige, rein dateibasierte Vorbereitungsschritte eines Generatorlaufs in eigenen PROZESSEN rechnen (24.11.2026).

GRUND (Profil Schwabentor-1122, Kopie, 4 Kerne): ein Bau lief praktisch auf EINEM Kern (~126-137 % CPU). Zwei Drittel der Zeit steckten nicht in manifold3d
(das rechnet mit TBB schon parallel), sondern in der Relief-Vorbereitung je Wand: quader_raster (scipy gaussian_filter), putz_wandbild.relief_kanten_beleg/
glatt_karte (binary_erosion/dilation) - einfaedig, GIL-gebunden, aber je Wand unabhaengig (jede Wand liest/schreibt nur relief/<wand>_*.npz/.jpg).
Darum: je Aufgabe ein Kindprozess (frisches `python -I`, kein fork neben den TBB-Threads des Generators), Ergebnis per pickle zurueck,
Ausgabe des Kindes gepuffert und in Aufgabenreihenfolge gedruckt (Log wie seriell, nur ohne Verschraenkung).

  prozess_map(modul, funktion, [(args, kwargs), ...], name="...")  -> [ergebnis, ...] in Reihenfolge
  RCPARK_BAU_SERIELL=1  alter Weg: alles nacheinander im eigenen Prozess (gleiche Funktion, gleiche Reihenfolge)
  RCPARK_BAU_PROZESSE=N Obergrenze gleichzeitiger Kinder (Standard: min(Aufgaben, freie Kerne der Affinitaet, 6, MemAvailable / 1,5 GB))
Fehler im Kind werden im Elternprozess mit demselben Ausnahmetyp neu ausgeloest (Meldung + Kind-Traceback)."""
import os, sys, io, pickle, subprocess, tempfile, time, traceback

HIER = os.path.dirname(os.path.abspath(__file__))
KIND_RAM_MB = 1500                                                     # ANNAHME aus Messung 24.11.2026: Kind der Relief-Vorbereitung Spitze ~0,6-1,2 GB (Wandbild + Fotos einer Fassade)


def seriell():
    return os.environ.get("RCPARK_BAU_SERIELL") == "1"


def _mem_frei_mb():
    try:
        for z in open("/proc/meminfo"):
            if z.startswith("MemAvailable:"): return int(z.split()[1]) // 1024
    except OSError: pass
    return None


def plaetze(n_aufgaben):
    """Wie viele Kinder gleichzeitig: Kerne der eigenen Affinitaet (taskset/systemd-Buchung), RAM, RCPARK_BAU_PROZESSE."""
    try: kerne = len(os.sched_getaffinity(0))
    except AttributeError: kerne = os.cpu_count() or 1
    n = min(n_aufgaben, kerne, 6)
    if os.environ.get("RCPARK_BAU_PROZESSE"): n = min(n_aufgaben, max(1, int(os.environ["RCPARK_BAU_PROZESSE"])))
    m = _mem_frei_mb()
    if m is not None: n = min(n, max(1, m // KIND_RAM_MB))
    return max(1, n)


def _kind(pfad_ein, pfad_aus):
    """Im Kindprozess: Aufgabe laden, Funktion rufen, stdout puffern, (ergebnis, ausgabe, fehler) zurueckschreiben."""
    sys.path.insert(0, HIER)
    modul, funktion, args, kwargs, pfade = pickle.load(open(pfad_ein, "rb"))
    for p in reversed(pfade):
        if p not in sys.path: sys.path.insert(0, p)
    puffer = io.StringIO(); echt = sys.stdout; sys.stdout = puffer; erg = fehler = None
    try: erg = getattr(__import__(modul), funktion)(*args, **kwargs)
    except BaseException as e: fehler = (type(e).__name__, str(e), traceback.format_exc())
    finally: sys.stdout = echt
    with open(pfad_aus + ".teil", "wb") as f: pickle.dump((erg, puffer.getvalue(), fehler), f)
    os.replace(pfad_aus + ".teil", pfad_aus)


def _neu_ausloesen(fehler, name):
    typ, text, tb = fehler
    import builtins
    E = getattr(builtins, typ, None)
    msg = f"{name}: Kindprozess {typ}: {text}\n--- Kind-Traceback ---\n{tb}"
    if isinstance(E, type) and issubclass(E, BaseException):
        try: raise E(msg)
        except TypeError: pass
    raise RuntimeError(msg)


def prozess_map(modul, funktion, aufgaben, name="bau_parallel", n=None, gewichte=None):
    """aufgaben = [(args_tuple, kwargs_dict), ...]; modul muss unter tools/ (oder sys.path des Elternprozesses) importierbar sein.
    gewichte (optional, z. B. Dateigroesse): schwerste Aufgaben zuerst starten (sonst wartet am Ende alles auf die groesste Wand); Ergebnisse bleiben in Aufgabenreihenfolge."""
    aufgaben = list(aufgaben)
    if not aufgaben: return []
    n = plaetze(len(aufgaben)) if n is None else n
    if seriell() or n <= 1 or len(aufgaben) == 1:                      # alter Weg (und eine einzige Aufgabe: kein Prozessstart noetig)
        f = getattr(__import__(modul), funktion)
        return [f(*a, **k) for a, k in aufgaben]
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.time(); dauer = [0.0] * len(aufgaben); td = tempfile.mkdtemp(prefix="bau_parallel_"); pfade = [p for p in sys.path if p and os.path.isdir(p)]

    def eins(i):
        pe, pa = os.path.join(td, f"{i}.ein"), os.path.join(td, f"{i}.aus")
        a, k = aufgaben[i]
        with open(pe, "wb") as f: pickle.dump((modul, funktion, a, k, pfade), f)
        t_ = time.time(); r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "bau_parallel.py"), "--kind", pe, pa], capture_output=True, text=True); dauer[i] = time.time() - t_
        if r.returncode != 0 or not os.path.exists(pa):
            return None, r.stdout, ("RuntimeError", f"Kindprozess rc {r.returncode}", (r.stderr or "")[-3000:])
        return pickle.load(open(pa, "rb"))
    try:
        folge = sorted(range(len(aufgaben)), key=lambda i: -gewichte[i]) if gewichte is not None else list(range(len(aufgaben)))
        with ThreadPoolExecutor(n) as ex: fu = {i: ex.submit(eins, i) for i in folge}; R = [fu[i].result() for i in range(len(aufgaben))]
    finally:
        for x in os.listdir(td): os.remove(os.path.join(td, x))
        os.rmdir(td)
    erg = []
    for e, ausgabe, fehler in R:                                         # Ausgabe in Aufgabenreihenfolge (Log wie seriell)
        if ausgabe: sys.stdout.write(ausgabe)
        if fehler: sys.stdout.flush(); _neu_ausloesen(fehler, name)
        erg.append(e)
    print(f"    {name}: {len(aufgaben)} Aufgaben in {n} Prozessen, {time.time() - t0:.1f} s (je Aufgabe " + " ".join(f"{d:.0f}" for d in dauer) + " s)", flush=True)
    return erg


def stl_lesen(pfad):
    import numpy as np
    b = open(pfad, "rb").read(); n = int(np.frombuffer(b[80:84], np.uint32)[0])
    return np.frombuffer(b[84:84 + 50 * n], dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])["v"].astype(np.float64)


def vergleichen(stl_a, stl_b):
    """Gleichheitsbeleg zweier Bauergebnisse (STL): Dreieckszahl, Volumen, Hausdorff-Schranke (Ecken + Dreiecksmitten je Seite zum naechsten Punkt der anderen;
    ueberschaetzt den Flaechenabstand, ist also streng) und ob die Dreiecksmengen bitgleich sind. Einheit wie im STL (Generator: mm im Druckmassstab)."""
    import numpy as np
    from scipy.spatial import cKDTree
    A, B = stl_lesen(stl_a), stl_lesen(stl_b)
    vol = lambda T: float(np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0)
    def punkte(T): return np.r_[T.reshape(-1, 3), T.mean(1)]
    def zeilen(T): R = T.reshape(len(T), 9); return R[np.lexsort(R.T[::-1])]   # Dreiecksmenge in fester Reihenfolge (Reihenfolge im STL egal)
    gleich = len(A) == len(B) and bool(np.array_equal(zeilen(A), zeilen(B)))
    if gleich: h = 0.0
    else:
        pa, pb = punkte(A), punkte(B)
        h = float(max(cKDTree(pb).query(pa)[0].max(), cKDTree(pa).query(pb)[0].max()))
    return dict(dreiecke=(len(A), len(B)), volumen=(round(vol(A), 4), round(vol(B), 4)), hausdorff_schranke=h, bitgleich=gleich)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--kind": _kind(sys.argv[2], sys.argv[3]); sys.exit(0)
    if len(sys.argv) == 4 and sys.argv[1] == "--vergleich":
        r = vergleichen(sys.argv[2], sys.argv[3]); print(r); sys.exit(0 if r["dreiecke"][0] == r["dreiecke"][1] and r["hausdorff_schranke"] < 0.01 else 1)
    print(__doc__); sys.exit(2)

#!/usr/bin/env python3
"""masse_bootstrap.py - Streuung der AUTOMATISCH abgeleiteten Masse (Baender -> masse_aus_profilen) innerhalb EINES Laufs messen (Register BO).

Problem: Die Bandwahl (Farbklassen, Index, ersatzwahl) kippt zwischen Laeufen; ein Einzellauf liefert z. B. ERKER_OBEN 34,25 oder 39,75 m.
Verfahren (Schwarmprinzip, nur Rechenzeit auf CPU, keine neue Quelle): aus der Wolke N Teilstichproben ziehen (Anteil --anteil ohne Zuruecklegen),
je Stichprobe in einem Sandkasten-Objekt die ECHTE Kette laufen lassen (wolke_baender tuermchen -> zentral -> masse_aus_profilen --schreiben)
und je Mass Median, MAD, Spanne und Haeufigkeit des Medianwertes ausgeben. Ein Mass mit MAD <= Rundungsquantum ist BAND-STABIL; eines mit grosser
Spanne ist bandwahl-instabil und darf nicht als Einzelwert in den Generator (Kennzeichnung 'streut').
GRENZE (ehrlich): Teilstichproben streuen nur das Wolken-Rauschen, NICHT das Netz (Merkmale/Matching/Mapper) - die Netzstreuung messen nur
Wiederholungslaeufe (nullstart_beweis.py). Ob die Bootstrap-Streuung die Laufstreuung vorhersagt, prueft --gegen (Laufmasse als Vergleich).

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/masse_bootstrap.py modelle/martinstor_null/objekt.json --n 24 [--anteil 0.7] [--seed 1]
      [--gegen /pfad/lauf_1/masse.json /pfad/lauf_2/masse.json ...] [--json aus.json]
"""
import sys, os, json, shutil, argparse, subprocess, tempfile, numpy as np
from concurrent.futures import ThreadPoolExecutor
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = sys.executable

def lauf(i, a, od, P, C, objekt, wurzel):
    d = os.path.join(wurzel, f"b{i:02d}"); os.makedirs(os.path.join(d, "sfm"), exist_ok=True)
    for f in ("objekt.json", "masse.json", "anker3d.json", "profile_generator.json"):
        if os.path.exists(os.path.join(od, f)): shutil.copy(os.path.join(od, f), d)
    rng = np.random.default_rng(a.seed * 1000 + i); k = np.sort(rng.choice(len(P), int(len(P) * a.anteil), replace=False))
    np.save(os.path.join(d, "sfm", "dicht_nord_entzerrt.npy"), P[k]); np.save(os.path.join(d, "sfm", "dicht_nord_farben.npy"), C[k])
    ob = os.path.join(d, "objekt.json"); env = dict(os.environ); log = []
    for cmd in ([PY, "-W", "ignore", "-I", os.path.join(REPO, "tools", "wolke_baender.py"), ob, "nord", "--koerper", "tuermchen"],
                [PY, "-W", "ignore", "-I", os.path.join(REPO, "tools", "wolke_baender.py"), ob, "nord", "--koerper", "zentral"],
                [PY, "-W", "ignore", "-I", os.path.join(REPO, "tools", "masse_aus_profilen.py"), ob, "--schreiben"]):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=d, env=env)
        if r.returncode != 0: return i, None, (r.stderr or r.stdout)[-300:]
    m = json.load(open(os.path.join(d, "masse.json")))["masse"]
    return i, {n: x["wert"] for n, x in m.items() if isinstance(x, dict) and isinstance(x.get("wert"), (int, float))}, ""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--n", type=int, default=24); ap.add_argument("--anteil", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--threads", type=int, default=8); ap.add_argument("--gegen", nargs="*", default=[]); ap.add_argument("--json")
    ap.add_argument("--wolke", help="Wolke statt sfm/dicht_nord_entzerrt.npy (Farben: *_farben.npy daneben)")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); pf = a.wolke or os.path.join(od, "sfm", "dicht_nord_entzerrt.npy")
    P = np.load(pf).astype(float); C = np.load(pf.replace("_entzerrt.npy", "_farben.npy"))
    wurzel = tempfile.mkdtemp(prefix="bootstrap_", dir=os.environ.get("BOOT_DIR", "/media/oem/scan/rc-park_null"))
    print(f"{len(P)} Punkte, {a.n} Stichproben zu {a.anteil:.0%}, Sandkasten {wurzel}", flush=True)
    with ThreadPoolExecutor(a.threads) as ex: res = list(ex.map(lambda i: lauf(i, a, od, P, C, a.objekt, wurzel), range(a.n)))
    fehl = [(i, e) for i, v, e in res if v is None]; V = {}
    for i, v, e in res:
        for n, w in (v or {}).items(): V.setdefault(n, []).append(w)
    print(f"{a.n - len(fehl)} von {a.n} Stichproben ohne Fehler" + (f"; Fehler z. B.: {fehl[0]}" if fehl else ""))
    ref = {n: x["wert"] for n, x in json.load(open(os.path.join(od, "masse.json")))["masse"].items() if isinstance(x, dict) and isinstance(x.get("wert"), (int, float))}
    G = []
    for f in a.gegen:
        G.append({n: x["wert"] for n, x in json.load(open(f))["masse"].items() if isinstance(x, dict) and isinstance(x.get("wert"), (int, float))})
    out = {}
    print(f"{'masse':22}{'n':>3}{'median':>8}{'MAD':>6}{'min':>8}{'max':>8}{'Modus%':>7}" + (f"{'Laeufe: median':>16}{'MAD':>6}" if G else ""))
    for n, vs in sorted(V.items()):
        vs = np.array(vs); md = float(np.median(vs)); mad = float(np.median(abs(vs - md)))
        vals, cnt = np.unique(np.round(vs, 2), return_counts=True); modus = 100 * cnt.max() / len(vs)
        row = dict(n=len(vs), median=round(md, 3), mad=round(mad, 3), min=float(vs.min()), max=float(vs.max()), modus_prozent=round(modus, 0))
        s = f"{n:22}{len(vs):3}{md:8.2f}{mad:6.2f}{vs.min():8.2f}{vs.max():8.2f}{modus:7.0f}"
        if G:
            gv = np.array([g[n] for g in G if n in g])
            if len(gv): gm = float(np.median(gv)); gs = float(np.median(abs(gv - gm))); row.update(laeufe_median=round(gm, 3), laeufe_mad=round(gs, 3), laeufe_spanne=[float(gv.min()), float(gv.max())]); s += f"{gm:16.2f}{gs:6.2f}  [{gv.min():.2f}..{gv.max():.2f}]"
        if row['min'] == row['max'] and (not G or row.get('laeufe_spanne', [0, 0])[0] == row.get('laeufe_spanne', [0, 0])[1]): continue      # konstant (Handwert/Formel): nicht aufgefuehrt
        out[n] = row; print(s)
    if a.json: json.dump(dict(n=a.n, anteil=a.anteil, seed=a.seed, masse=out, referenz=ref), open(a.json, "w"), indent=1, ensure_ascii=False)
    shutil.rmtree(wurzel, ignore_errors=True)

if __name__ == "__main__":
    main()

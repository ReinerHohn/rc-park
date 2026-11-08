#!/usr/bin/env python3
"""modell_wettbewerb.py - WETTBEWERB: viele Modelle (STL, aus verschiedenen Algorithmen) gegen dieselben Fotos mit der jeweiligen Kamera (foto_diff), gleiche Bedingungen.
Ziel (Nutzer 6.11. /goal): Weg Punktwolke -> 3D-Modell mit moeglichst kleinem Diff ueber alle Fotos.
  venv-seg/bin/python -I tools/modell_wettbewerb.py modelle/<obj>/objekt.json --aus DIR --kandidat name:pfad.stl ... [--fotos 12] [--kerne 3] [--liste 000,004,...]
Ablauf: Pass 1 je (Kandidat, Foto) Silhouettenmaske (foto_diff --maske-aus); FESTE Maske je Foto = Vereinigung ALLER Kandidatenmasken (keiner wird durch seine eigene Silhouette
bevorzugt, erfundene Geometrie ausserhalb zaehlt mit). Pass 2: foto_diff --bewertung-maske -> kosten_lr (kleiner = besser, 'a contrario'), kosten_param.
Ausgabe: DIR/ergebnis.json + Tabelle (je Kandidat Mittel/Median, Zahl Fotos besser als Basis 'C', pro Foto). CPU (FD_RASTER=0, kein CUDA): geprueftes Mass. Gleicher Foto-Satz, kein Auswaehlen nach Passung."""
import sys, os, json, glob, subprocess, argparse, numpy as np
from concurrent.futures import ThreadPoolExecutor
TOOLS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, TOOLS)
import param_suche as PS


GPU = False
RASTER = False                                                                                 # --raster: foto_diff im GPU-Raster (Standard von foto_diff), nicht in der Punktfassung (Register BS3e: Punktfassung degeneriert bei Tele-Foto)
EXTRA = []     # --fd-arg: zusaetzliche foto_diff-Optionen fuer ALLE Kandidaten (z.B. --fd-arg=--glaettung=0.05 fuer feinere Kanten)


def lauf(args, env_extra=None):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", FD_RASTER="0")
    if GPU: env = dict(os.environ, FD_GPU="1", FD_RASTER="0", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")      # Vorauswahl (nicht numerisch identisch mit CPU, Rangfolge pruefen)
    if RASTER: env = dict(os.environ, FD_RASTER="1", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"); env.pop("FD_GPU", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(TOOLS, "foto_diff.py")] + args + EXTRA, capture_output=True, text=True, env=env)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True); ap.add_argument("--kandidat", action="append", required=True)
    ap.add_argument("--batch", action="store_true", help="Pass 2 je Kandidat in EINEM Prozess (tools/foto_diff_batch.py, Punktmodus ~2x schneller, bitgleich; BS8); mit --raster nicht genutzt"); ap.add_argument("--raster", action="store_true", help="GPU-Raster statt CPU-Punktfassung (nicht numerisch identisch; BS3e)"); ap.add_argument("--fd-arg", action="append", default=[], help="zusaetzliche foto_diff-Option, z.B. --fd-arg=--glaettung=0.05 (wiederholbar)"); ap.add_argument("--fotos", type=int, default=12); ap.add_argument("--liste"); ap.add_argument("--kerne", type=int, default=3); ap.add_argument("--basis", default="C"); ap.add_argument("--gpu", action="store_true"); ap.add_argument("--maske-kandidat", help="feste Maske NUR von diesem Kandidaten (z. B. C = Gebaeude ohne Nachbarn) statt Vereinigung aller"); ap.add_argument("--maske-von", help="Ordner mit schon berechneten Masken (Dateien <Kandidat>_<Foto>.png) zum Wiederverwenden"); a = ap.parse_args(); GPU = a.gpu
    RASTER = a.raster; EXTRA.extend(a.fd_arg); od = os.path.dirname(os.path.abspath(a.objekt)); K = [(k.split(":", 1)[0], k.split(":", 1)[1]) for k in a.kandidat]
    fotos = a.liste.split(",") if a.liste else PS.fotos_waehlen(od, a.fotos); os.makedirs(a.aus, exist_ok=True); md = os.path.join(a.aus, "masken"); os.makedirs(md, exist_ok=True)
    # Konfigurations-Fingerabdruck (Review 7.11.): Ergebnisse/Masken/p2 im Ordner gelten NUR fuer dieselben STL-Dateien (Groesse+mtime), Fotoliste, Modus, Zusatzargumente.
    import hashlib
    def _fp(pf):
        st = os.stat(pf); return f"{st.st_size}:{st.st_mtime_ns}"
    konf = dict(stl={n: _fp(p) for n, p in K}, fotos=list(fotos), raster=bool(RASTER), extra=list(EXTRA), basis=a.basis)
    konf["hash"] = hashlib.sha1(json.dumps(konf, sort_keys=True).encode()).hexdigest()[:16]; kf = os.path.join(a.aus, "konfig.json"); ergf = os.path.join(a.aus, "ergebnis.json")
    if os.path.exists(ergf) and os.path.exists(kf) and json.load(open(kf)).get("hash") != konf["hash"]:
        sys.exit(f"ABBRUCH: {a.aus} enthaelt Ergebnisse einer ANDEREN Konfiguration (STL/Fotos/Modus/Zusatzargumente geaendert). Neuen --aus-Ordner waehlen oder Ordner leeren.")
    if os.path.exists(ergf) and not os.path.exists(kf): print("HINWEIS: Altordner ohne konfig.json - Konfiguration nicht pruefbar (Ergebnisse koennen aus anderer Konfiguration stammen)")
    json.dump(konf, open(kf, "w"), indent=1)
    erg = json.load(open(ergf)) if os.path.exists(ergf) else {}
    def pass1(t):
        n, p, nr = t; mo = os.path.join(md, f"{n}_{nr}.png")
        if os.path.exists(mo): return t, True
        r = lauf([a.objekt, nr, "--stl", p, "--aus", os.path.join(a.aus, "p1", n, nr), "--maske-aus", mo]); return t, os.path.exists(mo)
    if a.maske_von:
        import shutil
        for f in glob.glob(os.path.join(a.maske_von, "*_*.png")): shutil.copy(f, md) if not os.path.exists(os.path.join(md, os.path.basename(f))) else None
    todo = [(n, p, nr) for n, p in K for nr in fotos]
    with ThreadPoolExecutor(a.kerne) as ex: ok1 = dict((t[:1] + t[2:], o) for t, o in ex.map(pass1, todo))
    print("Pass 1 fertig:", sum(ok1.values()), "/", len(ok1), flush=True)
    import cv2
    for nr in fotos:                                                                          # Vereinigung aller Masken je Foto
        ms = [cv2.imread(os.path.join(md, f"{n}_{nr}.png"), cv2.IMREAD_GRAYSCALE) for n, _ in K if os.path.exists(os.path.join(md, f"{n}_{nr}.png")) and (not a.maske_kandidat or n == a.maske_kandidat)]
        if not ms and a.maske_kandidat and os.path.exists(os.path.join(md, f"{a.maske_kandidat}_{nr}.png")): ms = [cv2.imread(os.path.join(md, f"{a.maske_kandidat}_{nr}.png"), cv2.IMREAD_GRAYSCALE)]   # Maskenkandidat nicht unter den Kandidaten: kopierte Maske nehmen
        if ms: cv2.imwrite(os.path.join(md, f"{nr}.png"), (np.max(ms, 0) > 0).astype(np.uint8) * 255)
    def pass2(t):
        n, p, nr = t
        if f"{n}|{nr}" in erg: return t, erg[f"{n}|{nr}"]
        if not os.path.exists(os.path.join(md, f"{nr}.png")): return t, None
        o = os.path.join(a.aus, "p2", n, nr); j = glob.glob(os.path.join(o, "foto_diff_*.json"))
        if not j: lauf([a.objekt, nr, "--stl", p, "--aus", o, "--bewertung-maske", os.path.join(md, f"{nr}.png")]); j = glob.glob(os.path.join(o, "foto_diff_*.json"))
        if not j: return t, None
        e = json.load(open(j[0])); return t, dict(lr=e.get("kosten_lr"), param=e.get("kosten_param"))
    if a.batch and not RASTER:                                                                    # je Kandidat ein Prozess fuer alle noch fehlenden Fotos (Ergebnisse landen in p2/<kandidat>/<nr>, pass2 liest sie)
        for n, p in K:
            fehlt = [nr for nr in fotos if f"{n}|{nr}" not in erg and os.path.exists(os.path.join(md, f"{nr}.png")) and not glob.glob(os.path.join(a.aus, "p2", n, nr, "foto_diff_*.json"))]
            if fehlt:
                r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(TOOLS, "foto_diff_batch.py"), a.objekt, "--aus", os.path.join(a.aus, "p2"), "--stl", f"{n}={p}", "--fotos", ",".join(fehlt), "--maske-dir", md, "--modus", "punkt", "--threads", str(max(1, min(3, a.kerne)))] + [f"--fd-arg={x}" for x in a.fd_arg], capture_output=True, text=True, env=dict(os.environ, CUDA_VISIBLE_DEVICES="", FD_RASTER="0"))
                print(f"batch {n}: {len(fehlt)} Fotos rc={r.returncode}", flush=True)
    with ThreadPoolExecutor(a.kerne) as ex:
        for t, r in ex.map(pass2, todo):
            if r is not None: erg[f"{t[0]}|{t[2]}"] = r
    json.dump(erg, open(ergf, "w"), indent=1)
    print(f"{'Kandidat':28s} {'n':>3s} {'Mittel lr':>10s} {'Median lr':>10s} {'besser als ' + a.basis:>14s}")
    base = {nr: (erg.get(f"{a.basis}|{nr}") or {}).get("lr") for nr in fotos}
    for n, _ in K:
        v = {nr: (erg.get(f"{n}|{nr}") or {}).get("lr") for nr in fotos}; ok = [nr for nr in fotos if v[nr] is not None]
        if not ok: print(f"{n:28s} keine Werte"); continue
        b = sum(1 for nr in ok if base.get(nr) is not None and v[nr] < base[nr])
        print(f"{n:28s} {len(ok):3d} {np.mean([v[nr] for nr in ok]):10.4f} {np.median([v[nr] for nr in ok]):10.4f} {b:6d} / {len([nr for nr in ok if base.get(nr) is not None])}")

# Automatisches Versuchslog (tools/versuch_log.py): Rohspur jedes Wettbewerbs, Warnung bei Zahlengleichheit mit anderem Vorlauf (Raster-Fall BS7)
try:
    import versuch_log as VL
    _e = {}
    for n, _ in K:
        _v = [(erg.get(f"{n}|{nr}") or {}).get("lr") for nr in fotos]; _v = [x for x in _v if x is not None]
        _e[n] = dict(n=len(_v), mittel=float(np.mean(_v)) if _v else None, median=float(np.median(_v)) if _v else None)
    _fehlt = {n: [nr for nr in fotos if (erg.get(f"{n}|{nr}") or {}).get("lr") is None] for n, _ in K}; _alle_gleich = len({tuple(v) for v in _fehlt.values()}) == 1
    _nicht_beurteilbar = _fehlt[K[0][0]] if _alle_gleich else []                                                   # fehlt fuer ALLE Kandidaten identisch -> Foto sieht das Modell nicht (foto_diff NaN), nicht Fehlprobe eines Kandidaten
    _voll = all(v["n"] == len(fotos) for v in _e.values()) or (_alle_gleich and len(_nicht_beurteilbar) < len(fotos))           # vollstaendig = jeder Kandidat hat ALLE Fotos ausser denen, die fuer ALLE gleich fehlen (dann VERGLEICHBAR)
    json.dump(dict(vollstaendig=_voll, fotos=len(fotos), je_kandidat={n: v["n"] for n, v in _e.items()}, nicht_beurteilbar_fuer_alle=_nicht_beurteilbar, fehlt_je_kandidat=_fehlt, konfig_hash=konf["hash"]), open(os.path.join(a.aus, "gueltigkeit.json"), "w"), indent=1)
    if _voll and _nicht_beurteilbar: print("HINWEIS: fuer ALLE Kandidaten gleich nicht beurteilbar (Foto sieht Modell nicht / foto_diff ohne Wert):", _nicht_beurteilbar, "- Vergleich auf den uebrigen", len(fotos) - len(_nicht_beurteilbar), "Fotos gueltig")
    if not _voll: print("UNVOLLSTAENDIG: nicht jeder Kandidat hat Werte fuer ALLE", len(fotos), "Fotos ->", {n: v["n"] for n, v in _e.items()}, "- Mittel NICHT vergleichbar (Gate Review 7.11.)")
    VL.log(a.objekt, "modell_wettbewerb", sys.argv[1:], _e, status=("ok" if _voll else "unvollstaendig") if any(v["n"] for v in _e.values()) else "keine_werte", notiz=("raster" if RASTER else "punkt") + f"; aus={a.aus}; konfig={konf['hash']}")
except Exception as _x: print("versuch_log fehlgeschlagen:", _x)
if "_voll" in globals() and not _voll: sys.exit(3)

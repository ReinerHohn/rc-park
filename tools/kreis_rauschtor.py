#!/usr/bin/env python3
"""kreis_rauschtor.py - TEIL-LOKALES RAUSCHTOR fuer den Bauteil-Kreis (Analyse 12.11. 00:05: Annahmen seit 11.11. 14:30 im Rauschen, +0,006 bei
Rauschen ~0,03; feste Schwelle MIN_GEWINN_FOTO 0,02 / Grauzone / FORMFUND_TOL trennen richtige nicht von falschen Teilen).

Idee (teil_varianten_tor.py e87095b2): aus dem VORHER-Stand je Teil drei bekannt falsche Nullkontrollen bauen (Teil 0,3 m verschoben, 0,3 m angehoben,
90 Grad gedreht) und mit teil_fotoform auf denselben Fotos messen. Rauschen je Mass m:  R_m = Wert_vorher - max(Nullkontrollen)
= wie weit ein falsches Teil unter dem richtigen liegt. R_m <= 0: das Mass trennt an diesem Teil nicht (Erker: Grob-F1 bewertet das gedrehte Teil besser).
Massen: f1 (Grob-F1, 0,18 m), f1_fein (volle Aufloesung), f1_h (waagerechte Kanten).

Mass waehlen: f1_fein fuer Ornament-/Feinfunde (ORN-Worte) oder kleine Teile (kleinste Kastenkante < 0,36 m), sonst f1; ist das bevorzugte Mass nicht
trennend, das andere (falls trennend); sonst nicht messbar (kein Agent, Fotowunsch).
Annahme: Gewinn im gewaehlten Mass >= max(FAKTOR * R, MINDEST) UND kein anderes trennendes Mass k faellt um mehr als FAKTOR * R_k
(+ Grobschranke: nicht trennende Masse fallen hoechstens GROB, faengt groben Lagefehler wie der ORNAMENT-WEG).

Cache: <rdir>/<teil>_<sha16 Teil-STL>_<sha8 Fotoliste>.json (Schluessel Teil + Vorher-Teil-STL + Fotoliste); einmal je Teilstand berechnet.
Reine Funktionen ohne numpy/torch (der Kreis laeuft mit System-python3); die Messung selbst laeuft als eigener Prozess in venv-seg.

CLI (Beweis/Vorab-Cache):
  python3 tools/kreis_rauschtor.py berechnen <objekt> <teil> --teile_dir D --stl S --fotos a,b,.. [--rdir DIR]
  python3 tools/kreis_rauschtor.py zeigen <objekt> <teil> --teile_dir D --fotos a,b,..
Kein Objektname im Code.
"""
import os, sys, json, hashlib, subprocess, time, struct

MASSE = ("f1", "f1_fein", "f1_h")
NULLEN = ("null_verschoben", "null_hoch", "null_gedreht")
FAKTOR, MINDEST, GROB, KLEIN_M = 0.5, 0.01, 0.05, 0.36


def _sha_datei(p, n=16):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:n]


def schluessel(teil, teil_stl, fotos):
    return f"{teil}_{_sha_datei(teil_stl)}_{hashlib.sha256(','.join(fotos).encode()).hexdigest()[:8]}"


def laden(rdir, teil, teile_dir, fotos):
    """Cache-Eintrag oder None (fehlt / Teil-STL fehlt)."""
    ts = os.path.join(teile_dir or "", teil + ".stl")
    if not teile_dir or not os.path.exists(ts) or not fotos: return None
    p = os.path.join(rdir, schluessel(teil, ts, fotos) + ".json")
    try: return json.load(open(p))
    except Exception: return None


def aus_varianten(vt, ref="vorher"):
    """R je Mass aus einem varianten_tor.json (teil_varianten_tor.py)."""
    V = vt.get("varianten") or {}
    w = {m: (V.get(ref) or {}).get(m) for m in MASSE}
    nl = {n: {m: (V.get(n) or {}).get(m) for m in MASSE} for n in vt.get("nullen") or NULLEN}
    R = {}
    for m in MASSE:
        xs = [nl[n][m] for n in nl]
        R[m] = round(w[m] - max(xs), 4) if (w[m] is not None and xs and all(x is not None for x in xs)) else None
    return {"werte_vorher": w, "nullen": nl, "R": R, "trennend": [m for m in MASSE if (R[m] or 0) > 0]}


def berechnen(rdir, obj, teil, teile_dir, stl, fotos, cwd, lauf=None, py="/media/oem/scan/venv-seg/bin/python"):
    """Einmal je Schluessel (flock), sonst Cache. lauf(cmd, cwd, log) -> (rc, out); Standard subprocess. Rueckgabe Eintrag oder
    {'infra': True} bei OOM/Platz (nicht cachen, Ziel bleibt waehlbar)."""
    import fcntl
    os.makedirs(rdir, exist_ok=True)
    ts = os.path.join(teile_dir, teil + ".stl")
    k = schluessel(teil, ts, fotos); p = os.path.join(rdir, k + ".json")
    with open(p + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        if os.path.exists(p): return json.load(open(p))
        aus = os.path.join(rdir, k + "_lauf"); os.makedirs(aus, exist_ok=True); log = os.path.join(aus, "lauf.log")
        cmd = [py, "-W", "ignore", "-I", "tools/teil_varianten_tor.py", obj, teil, "--varianten", f"vorher:{teile_dir}:{stl}", "--fotos", ",".join(fotos),
               "--aus", aus, "--ohne_sam", "--ohne_kollage", "--wiederaufnahme"]
        t0 = time.time()
        if lauf is None:
            env = dict(os.environ); env.pop("RCPARK_FOTO_SKALA", None); env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
            with open(log, "a") as f: rc = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env).returncode
            out = open(log, errors="replace").read()
        else:
            rc, out = lauf(cmd, cwd, log)
        oom = ("INFRA_OOM" in (out or "")) or any(m in (out or "") for m in ("out of memory", "CUDA_ERROR_OUT_OF_MEMORY", "OutOfMemoryError", "PLATZ ZU KNAPP"))
        try: vt = json.load(open(os.path.join(aus, "varianten_tor.json")))
        except Exception: vt = None
        if vt is None or any(((vt.get("varianten") or {}).get(n) or {}).get("f1") is None for n in ("vorher",) + NULLEN):
            if oom: return {"infra": True, "grund": "OOM/Platz in der Rauschmessung", "log": log}
            e = {"teil": teil, "teil_sha": k.split("_")[-2], "fotos": fotos, "R": {m: None for m in MASSE}, "trennend": [], "fehler": f"rc={rc} Messung unvollstaendig", "log": log}
        else:
            e = dict(aus_varianten(vt), teil=teil, teil_sha=k.split("_")[-2], fotos=fotos, aus=aus)
        e.update(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), laufzeit_s=round(time.time() - t0), schluessel=k)
        json.dump(e, open(p + ".tmp", "w"), ensure_ascii=False, indent=1); os.replace(p + ".tmp", p)
        return e


def kleinste_kante_m(stl, massstab=87.0):
    """Kleinste Kante der Achsenbox eines binaeren Teil-STL (mm im Massstab 1:massstab) in Metern; None wenn nicht lesbar."""
    try:
        d = open(stl, "rb").read(); n = struct.unpack("<I", d[80:84])[0]
        lo, hi = [1e30] * 3, [-1e30] * 3
        for i in range(n):
            v = struct.unpack_from("<9f", d, 84 + 50 * i + 12)
            for j in range(3):
                for c in (v[j], v[3 + j], v[6 + j]):
                    if c < lo[j]: lo[j] = c
                    if c > hi[j]: hi[j] = c
        return min(hi[j] - lo[j] for j in range(3)) * massstab / 1000.0
    except Exception:
        return None


def fein_bevorzugt(text, worte, kante_m, klein=KLEIN_M):
    t = (text or "").lower()
    return bool(any(w in t for w in worte) or (kante_m is not None and kante_m < klein))


def mass_waehlen(R, fein):
    """Gewaehltes Mass oder None (kein trennendes Mass). Nur f1 / f1_fein entscheiden; f1_h ist Veto."""
    R = R or {}
    zuerst, sonst = ("f1_fein", "f1") if fein else ("f1", "f1_fein")
    for m in (zuerst, sonst):
        if (R.get(m) or 0) > 0: return m
    return None


def urteil(R, mass, vorher, nachher, faktor=FAKTOR, mindest=MINDEST, grob=GROB, veto_faktor=None):
    """(besteht, text). vorher/nachher: {f1, f1_fein, f1_h} (volle Aufloesung, gemeinsame Fotos). veto_faktor: Faktor fuer den Abfall anderer
    trennender Masse (Standard = faktor; die halbe Vorstufe lockert ihn, weil halbe Aufloesung die Betraege unterschaetzt)."""
    R = R or {}; vf = faktor if veto_faktor is None else veto_faktor
    if mass is None: return False, "kein trennendes Mass (R <= 0 fuer f1 und f1_fein)"
    v, n = (vorher or {}).get(mass), (nachher or {}).get(mass)
    if v is None or n is None: return False, f"mass={mass} nicht gemessen ({v} -> {n})"
    soll = max(faktor * R[mass], mindest); g = n - v; gruende = []
    if g < soll: gruende.append(f"Gewinn {g:+.3f} < Soll {soll:.3f}")
    for m in MASSE:
        if m == mass: continue
        a, b = (vorher or {}).get(m), (nachher or {}).get(m)
        if a is None or b is None: continue
        if (R.get(m) or 0) > 0:
            if b < a - vf * R[m]: gruende.append(f"{m} faellt {b - a:+.3f} > {vf} x R {R[m]:.3f}")
        elif grob and b < a - grob: gruende.append(f"{m} (nicht trennend) faellt {b - a:+.3f} > Grobschranke {grob}")
    txt = f"mass={mass}, R={R[mass]:.3f}, gewinn={g:+.3f} (Soll {soll:.3f}), " + ("besteht" if not gruende else "nicht: " + "; ".join(gruende))
    return (not gruende), txt


def _main():
    a = sys.argv
    if len(a) < 4 or a[1] not in ("berechnen", "zeigen"): print(__doc__); sys.exit(1)
    o = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    obj, teil = a[2], a[3]; fotos = o("--fotos", "").split(","); td = o("--teile_dir")
    rdir = o("--rdir", f"/media/oem/scan/rc-park_kreis/{obj}/rauschen")
    if a[1] == "zeigen": print(json.dumps(laden(rdir, teil, td, fotos), ensure_ascii=False, indent=1)); return
    e = berechnen(rdir, obj, teil, td, o("--stl"), fotos, o("--cwd", root))
    print(json.dumps({k: e.get(k) for k in ("teil", "R", "trennend", "werte_vorher", "nullen", "fehler", "infra", "laufzeit_s", "schluessel")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    _main()

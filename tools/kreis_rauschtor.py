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
import os, sys, json, hashlib, subprocess, time, struct, shutil

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


def urteil_detail(R, mass, vorher, nachher, faktor=FAKTOR, mindest=MINDEST, grob=GROB, veto_faktor=None):
    """Wie urteil(), aber mit getrennten Gruenden: {'ok', 'text', 'gewinn', 'soll', 'gewinn_zu_klein', 'vetos'}. (Elementmodus braucht 'Gewinn zu klein' und 'Veto' getrennt.)"""
    R = R or {}; vf = faktor if veto_faktor is None else veto_faktor
    if mass is None: return {"ok": False, "text": "kein trennendes Mass (R <= 0 fuer f1 und f1_fein)", "gewinn": None, "soll": None, "gewinn_zu_klein": False, "vetos": []}
    v, n = (vorher or {}).get(mass), (nachher or {}).get(mass)
    if v is None or n is None: return {"ok": False, "text": f"mass={mass} nicht gemessen ({v} -> {n})", "gewinn": None, "soll": None, "gewinn_zu_klein": False, "vetos": ["nicht gemessen"]}
    soll = max(faktor * R[mass], mindest); g = n - v; gruende = []; vetos = []
    if g < soll: gruende.append(f"Gewinn {g:+.3f} < Soll {soll:.3f}")
    for m in MASSE:
        if m == mass: continue
        a, b = (vorher or {}).get(m), (nachher or {}).get(m)
        if a is None or b is None: continue
        if (R.get(m) or 0) > 0:
            if b < a - vf * R[m]: vetos.append(f"{m} faellt {b - a:+.3f} > {vf} x R {R[m]:.3f}")
        elif grob and b < a - grob: vetos.append(f"{m} (nicht trennend) faellt {b - a:+.3f} > Grobschranke {grob}")
    gruende += vetos
    txt = f"mass={mass}, R={R[mass]:.3f}, gewinn={g:+.3f} (Soll {soll:.3f}), " + ("besteht" if not gruende else "nicht: " + "; ".join(gruende))
    return {"ok": not gruende, "text": txt, "gewinn": g, "soll": soll, "gewinn_zu_klein": g < soll, "vetos": vetos}


def urteil(R, mass, vorher, nachher, faktor=FAKTOR, mindest=MINDEST, grob=GROB, veto_faktor=None):
    """(besteht, text). vorher/nachher: {f1, f1_fein, f1_h} (volle Aufloesung, gemeinsame Fotos). veto_faktor: Faktor fuer den Abfall anderer
    trennender Masse (Standard = faktor; die halbe Vorstufe lockert ihn, weil halbe Aufloesung die Betraege unterschaetzt)."""
    d = urteil_detail(R, mass, vorher, nachher, faktor, mindest, grob, veto_faktor); return d["ok"], d["text"]


# ===================== ELEMENT-MESSREGION (Auftrag 12.11.; tools/kreis_elemente.py) =====================
# Schalter im Kreis: --element_region 1. Nur fuer Teile, die OHNE Elementregion kein trennendes Mass haben (mass_waehlen(...) is None) und sich in >= 2 Elemente
# teilen lassen (Reihe = zusammenhaengende Koerper, sonst Raster ueber die Dreiecksmitten). Je Element: R aus Nullkontrollen NUR auf dieses Element,
# Foto-F1 / f1_fein / f1_h nur in der Bildregion dieses Elements (teil_fotoform mit dem Element als eigenem "Teil"). Elemente mit < MIN_FOTOS_EL Fotos
# (je >= 200 sichtbare Pixel und >= 150 Modell-/Fotokantenpixel) werden gar nicht erst mit Nullkontrollen gemessen (teurer Lauf, kein Ergebnis).
ZELLE_M, MAX_EL, MIN_FOTOS_EL = 1.5, 8, 3
PY_SEG = "/media/oem/scan/venv-seg/bin/python"
OOM_MARKEN = ("INFRA_OOM", "out of memory", "CUDA_ERROR_OUT_OF_MEMORY", "OutOfMemoryError", "PLATZ ZU KNAPP")


def _lauf(cmd, cwd, log, lauf=None):
    if lauf is not None: return lauf(cmd, cwd, log)
    env = dict(os.environ); env.pop("RCPARK_FOTO_SKALA", None); env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    with open(log, "a") as f: rc = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env).returncode
    return rc, open(log, errors="replace").read()


def _massstab(cwd, obj):
    try: return float(json.load(open(os.path.join(cwd, "modelle", obj, "objekt.json"))).get("stl_massstab", 87))
    except Exception: return 87.0


def elemente_schluessel(teil, teil_stl, fotos, zelle_m=ZELLE_M, max_n=MAX_EL):
    return schluessel(teil, teil_stl, fotos) + f"_z{zelle_m:g}n{max_n}"


def elemente_laden(rdir, teil, teile_dir, fotos, zelle_m=ZELLE_M, max_n=MAX_EL):
    ts = os.path.join(teile_dir or "", teil + ".stl")
    if not teile_dir or not os.path.exists(ts) or not fotos: return None
    try: return json.load(open(os.path.join(rdir, elemente_schluessel(teil, ts, fotos, zelle_m, max_n) + ".elemente.json")))
    except Exception: return None


def elemente_masse(ent, text, worte, klein=KLEIN_M):
    """Mass je Element (None = nicht trennend / nicht messbar). Gleiche Regel wie Teil-Ebene: f1_fein bei Ornament-Worten oder kleinster Kante < klein."""
    out = {}
    for nm, e in (ent.get("elemente") or {}).items():
        out[nm] = mass_waehlen(e.get("R"), fein_bevorzugt(text, worte, e.get("kleinste_kante_m"), klein)) if e.get("R") else None
    return out


def elemente_berechnen(rdir, obj, teil, teile_dir, stl, fotos, cwd, lauf=None, py=PY_SEG, zelle_m=ZELLE_M, max_n=MAX_EL, min_fotos=MIN_FOTOS_EL):
    """Eintrag {'elemente': {name: {lo, hi, flaechen, kleinste_kante_m, sha, sicht, R, trennend, werte_vorher, nullen, fehler}}, 'trennende_elemente': [...], 'elemente_dir', ...}
    oder {'infra': True}. Einmal je Teil-STL + Fotoliste + Teilung (flock); Cache <rdir>/<schluessel>.elemente.json."""
    import fcntl
    os.makedirs(rdir, exist_ok=True)
    ts = os.path.join(teile_dir, teil + ".stl"); k = elemente_schluessel(teil, ts, fotos, zelle_m, max_n); p = os.path.join(rdir, k + ".elemente.json")
    with open(p + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        if os.path.exists(p): return json.load(open(p))
        t0 = time.time(); aus = os.path.join(rdir, k + "_elemente_lauf"); edir = os.path.join(aus, "elemente"); os.makedirs(edir, exist_ok=True)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = subprocess.run([py, "-I", os.path.join(root, "tools", "kreis_elemente.py"), "teilen", "--stl", ts, "--aus", edir, "--massstab", str(_massstab(cwd, obj)), "--zelle_m", str(zelle_m), "--max_n", str(max_n)],
                           capture_output=True, text=True)
        try: EJ = json.load(open(os.path.join(edir, "elemente.json")))
        except Exception: EJ = None
        e = {"teil": teil, "teil_sha": k.split("_")[-3], "fotos": fotos, "schluessel": k, "elemente_dir": edir, "zelle_m": zelle_m, "max_n": max_n, "elemente": {}, "trennende_elemente": []}
        if EJ is None or len(EJ["elemente"]) < 2:
            e.update(modus=(EJ or {}).get("modus", "fehler"), fehler="Teil nicht in >= 2 Elemente teilbar" + ("" if EJ else f" ({r.stderr[-200:]})"), zeit=time.strftime("%Y-%m-%d %H:%M:%S"))
            json.dump(e, open(p + ".tmp", "w"), ensure_ascii=False, indent=1); os.replace(p + ".tmp", p); return e
        e["modus"] = EJ["modus"]; namen = [x["name"] for x in EJ["elemente"]]
        # --- Sichtvorlauf: alle Elemente in EINEM teil_fotoform-Lauf (strenge Region, ohne --bereich_von) ---
        sj = os.path.join(aus, "sicht.json"); log = os.path.join(aus, "sicht.log")
        cmd = [py, "-W", "ignore", "-I", "tools/teil_fotoform.py", obj, "--teile_dir", edir, "--stl", stl, "--nur", ",".join(namen), "--fotos", ",".join(fotos), "--aus", sj, "--bilder_dir", os.path.join(aus, "bilder_sicht")]
        rc, out = _lauf(cmd, cwd, log, lauf)
        try: SJ = json.load(open(sj))["teile"]
        except Exception: SJ = None
        if SJ is None:
            if any(m in (out or "") for m in OOM_MARKEN): return {"infra": True, "grund": "OOM/Platz im Sichtvorlauf der Elemente", "log": log}
            e["fehler"] = f"Sichtvorlauf rc={rc} ohne Ergebnis"; e["zeit"] = time.strftime("%Y-%m-%d %H:%M:%S")
            json.dump(e, open(p + ".tmp", "w"), ensure_ascii=False, indent=1); os.replace(p + ".tmp", p); return e
        for x in EJ["elemente"]:
            nm = x["name"]; je = {f: v for f, v in (SJ.get(nm) or {}).items() if f != "_gesamt" and isinstance(v, dict)}
            x = dict(x, sicht={"fotos": len(je), "sicht_px": int(sum(v.get("sicht_px", 0) for v in je.values())), "mk_px": int(sum(v.get("mk_px", 0) for v in je.values())), "fk_px": int(sum(v.get("fk_px", 0) for v in je.values())),
                               "foto_liste": sorted(je)}, R=None, trennend=[], fehler=None)
            if len(je) < min_fotos: x["fehler"] = f"nur {len(je)} Fotos mit Sicht (Soll {min_fotos}; je >= 200 sichtbare Pixel, >= 150 Modell- und Fotokantenpixel)"
            e["elemente"][nm] = x
        # --- Nullkontrollen je sichtbarem Element (nur auf dieses Element) ---
        for nm, x in e["elemente"].items():
            if x["fehler"]: continue
            ae = os.path.join(aus, nm); os.makedirs(ae, exist_ok=True); log = os.path.join(ae, "lauf.log")
            cmd = [py, "-W", "ignore", "-I", "tools/teil_varianten_tor.py", obj, nm, "--varianten", f"vorher:{edir}:{stl}", "--fotos", ",".join(fotos), "--aus", ae, "--ohne_sam", "--ohne_kollage", "--wiederaufnahme"]
            rc, out = _lauf(cmd, cwd, log, lauf)
            try: vt = json.load(open(os.path.join(ae, "varianten_tor.json")))
            except Exception: vt = None
            if vt is None or any(((vt.get("varianten") or {}).get(n) or {}).get("f1") is None for n in ("vorher",) + NULLEN):
                if any(m in (out or "") for m in OOM_MARKEN): return {"infra": True, "grund": f"OOM/Platz in der Elementmessung {nm}", "log": log}
                x["fehler"] = f"Messung unvollstaendig (rc={rc}; Vorher oder Nullkontrolle ohne Wert, Region zu klein)"; continue
            x.update(aus_varianten(vt)); x["aus"] = ae
        e["trennende_elemente"] = [nm for nm, x in e["elemente"].items() if x.get("trennend")]
        e.update(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), laufzeit_s=round(time.time() - t0))
        json.dump(e, open(p + ".tmp", "w"), ensure_ascii=False, indent=1); os.replace(p + ".tmp", p)
        return e


def element_tabelle(ent, masse=None):
    """Lesbare Tabelle je Element (Bericht/Log)."""
    z = [f"{'Element':34s} {'Fotos':>5s} {'sichtpx':>8s} {'f1':>6s} {'R_f1':>7s} {'f1_fein':>7s} {'R_fein':>7s} {'f1_h':>6s} {'R_h':>7s}  Mass / Grund"]
    f = lambda v, n=3: "   -  " if v is None else f"{v:.{n}f}"
    for nm, x in (ent.get("elemente") or {}).items():
        w, R = x.get("werte_vorher") or {}, x.get("R") or {}; s = x.get("sicht") or {}
        w_ = x.get("werte_vorher") or {}; besser = sorted({n_.replace("null_", "") for n_, nv in (x.get("nullen") or {}).items() for m_ in MASSE if nv.get(m_) is not None and w_.get(m_) is not None and nv[m_] > w_[m_] + 0.02})
        hinweis = ("; Nullkontrolle schlaegt Vorher (Lage nicht am Optimum): " + ",".join(besser)) if besser else ""
        z.append(f"{nm:34s} {s.get('fotos', 0):5d} {s.get('sicht_px', 0):8d} {f(w.get('f1')):>6s} {f(R.get('f1'), 3):>7s} {f(w.get('f1_fein')):>7s} {f(R.get('f1_fein'), 3):>7s} {f(w.get('f1_h')):>6s} {f(R.get('f1_h'), 3):>7s}  "
                 + ((masse or {}).get(nm) or (x.get("fehler") or "kein trennendes Mass")) + hinweis)
    return "\n".join(z)


def elemente_nachher(ent, teil, nachher_dir, nachher_stl, vorher_stl, obj, fotos, cwd, aus, lauf=None, py=PY_SEG, *, vorher_dir):
    """Misst die GEAENDERTEN Elemente (Inhaltshash Nachher-Zuordnung gegen Vorher-Zuordnung, beide mit den Elementboxen aus ent) im Vorher- und im Nachher-Stand auf demselben
    Bildbereich (Vereinigung beider Staende, --bereich_von gegenseitig; gleiche Region = kein Schrumpf-/Wachstumsgewinn durch die Region).
    vorher_dir = Teile-Verzeichnis des beurteilten Vorher-Standes (Kreis: das des R-Eintrags; anders nur im synthetischen Test).
    -> {'betroffen': [...], 'geloescht': [...], 'vorher': {name: {f1,..}}, 'nachher': {...}} oder {'infra': True}."""
    os.makedirs(aus, exist_ok=True); root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ndir = os.path.join(aus, "nach_el"); vdir = os.path.join(aus, "vor_el")
    for d in (ndir, vdir): shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    ej = os.path.join(ent["elemente_dir"], "elemente.json"); res = {}
    for art, d, quelle in (("vorher", vdir, os.path.join(vorher_dir, teil + ".stl")), ("nachher", ndir, os.path.join(nachher_dir, teil + ".stl"))):
        if quelle is None or not os.path.exists(quelle): return {"fehler": f"Teil-STL {art} fehlt: {quelle}", "betroffen": []}
        r = subprocess.run([py, "-I", os.path.join(root, "tools", "kreis_elemente.py"), "zuordnen", "--stl", quelle, "--elemente", ej, "--aus", d, "--massstab", str(_massstab(cwd, obj)), "--teil", teil],
                           capture_output=True, text=True)
        try: res[art] = json.load(open(os.path.join(d, "zuordnung.json")))
        except Exception: return {"fehler": f"Zuordnung {art} fehlgeschlagen: " + r.stderr[-200:], "betroffen": []}
    messbar_ = [nm for nm, x in ent["elemente"].items() if x.get("R")]
    betroffen = [nm for nm in messbar_ if res["vorher"][nm]["flaechen"] > 0 and res["nachher"][nm]["flaechen"] > 0 and res["nachher"][nm]["sha"] != res["vorher"][nm]["sha"]]
    geloescht = [nm for nm in messbar_ if res["vorher"][nm]["flaechen"] > 0 and res["nachher"][nm]["flaechen"] == 0]
    out = {"betroffen": betroffen, "geloescht": geloescht, "vorher": {}, "nachher": {}, "zuordnung": res["nachher"]}
    if not betroffen: return out
    for art, td, st, bv in (("vorher", vdir, vorher_stl, ndir), ("nachher", ndir, nachher_stl, vdir)):
        aj = os.path.join(aus, f"ff_{art}.json"); log = os.path.join(aus, f"ff_{art}.log")
        cmd = [py, "-W", "ignore", "-I", "tools/teil_fotoform.py", obj, "--teile_dir", td, "--stl", st, "--nur", ",".join(betroffen), "--fotos", ",".join(fotos), "--aus", aj,
               "--bereich_von", bv, "--bilder_dir", os.path.join(aus, "bilder_" + art)]
        rc, txt = _lauf(cmd, cwd, log, lauf)
        try: T = json.load(open(aj))["teile"]
        except Exception:
            if any(m in (txt or "") for m in OOM_MARKEN): return {"infra": True, "grund": "OOM/Platz in der Element-Nachmessung", "log": log, "betroffen": betroffen}
            T = {}
        out[art] = {nm: {m: ((T.get(nm) or {}).get("_gesamt") or {}).get(m) for m in MASSE + ("fotos",)} for nm in betroffen}
    return out


def urteil_elemente(ent, masse, mess, faktor=FAKTOR, mindest=MINDEST, grob=GROB):
    """Annahme-Urteil ueber die betroffenen Elemente. Regel: mindestens ein betroffenes Element mit trennendem Mass besteht (Gewinn im Elementmass >=
    max(faktor*R, mindest), kein anderes trennendes Mass des Elements faellt um mehr als faktor*R_k, nicht trennende fallen hoechstens grob) UND kein betroffenes
    Element verschlechtert sich (Veto eines Elements, eigener Massfall > Soll, Element geloescht / nicht mehr messbar). Betroffene Elemente ohne trennendes Mass
    zaehlen nur ueber die Grobschranke. -> (ok, text, info)."""
    bet = mess.get("betroffen") or []; zeilen = []; gut = []; schlecht = []; gew = []
    for nm in mess.get("geloescht") or []: schlecht.append(nm); zeilen.append(f"{nm}: Element im Nachher-Stand geloescht")
    if not bet and not schlecht: return False, "kein Element geaendert (Nachher-Stand gleich Vorher)", {"gut": [], "schlecht": [], "gewinn": None}
    for nm in bet:
        x = ent["elemente"][nm]; R = x.get("R") or {}; m = (masse or {}).get(nm); v, n = mess["vorher"].get(nm) or {}, mess["nachher"].get(nm) or {}
        if m is not None:
            d = urteil_detail(R, m, v, n, faktor, mindest, grob)
            zeilen.append(f"{nm}: {d['text']}")
            if d["ok"]: gut.append(nm); gew.append(d["gewinn"])
            elif d["vetos"] or d["gewinn"] is None or (d["gewinn"] is not None and d["gewinn"] < -d["soll"]): schlecht.append(nm)
        else:   # nicht trennend: nur Grobschranke gegen Zusammenbruch
            f = [mm for mm in MASSE if v.get(mm) is not None and n.get(mm) is not None and grob and n[mm] < v[mm] - grob]
            zeilen.append(f"{nm}: kein trennendes Mass, " + ("Grobschranke verletzt: " + ", ".join(f) if f else "Grobschranke ok"))
            if f: schlecht.append(nm)
    ok = bool(gut) and not schlecht
    txt = f"Elementtor: {len(bet)} Element(e) geaendert, besteht: {gut}, verschlechtert: {schlecht} -> " + ("besteht" if ok else "nicht") + " | " + " | ".join(zeilen)
    return ok, txt, {"gut": gut, "schlecht": schlecht, "gewinn": (min(gew) if gew else None), "zeilen": zeilen}


def _main():
    a = sys.argv
    if len(a) < 4 or a[1] not in ("berechnen", "zeigen", "elemente", "element_urteil"): print(__doc__); sys.exit(1)
    o = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    obj, teil = a[2], a[3]; fotos = o("--fotos", "").split(","); td = o("--teile_dir")
    rdir = o("--rdir", f"/media/oem/scan/rc-park_kreis/{obj}/rauschen")
    if a[1] == "zeigen": print(json.dumps(laden(rdir, teil, td, fotos), ensure_ascii=False, indent=1)); return
    if a[1] in ("elemente", "element_urteil"):
        # elemente: Element-R berechnen/zeigen (Tabelle); element_urteil: zusaetzlich Nachher-Stand (--nachher_dir D --nachher_stl S) beurteilen
        # R-Stand: --teile_dir/--stl (Cache-Schluessel); beurteilter Vorher-Stand: --vorher_dir/--vorher_stl (Standard = R-Stand; fuer synthetische Tests anders)
        zm, mn = float(o("--zelle_m", ZELLE_M)), int(o("--max_n", MAX_EL))
        ent = elemente_berechnen(rdir, obj, teil, td, o("--stl"), fotos, o("--cwd", root), zelle_m=zm, max_n=mn)
        if ent.get("infra"): print("INFRA", ent); sys.exit(2)
        text = o("--text", teil); worte = tuple((o("--worte", "") or "").split(",")) if o("--worte") else ()
        masse = elemente_masse(ent, text, worte); print(element_tabelle(ent, masse)); print("trennende Elemente (mit Entscheidungsmass):", [k for k, v in masse.items() if v], "| nur f1_h-trennend:", [k for k in ent.get("trennende_elemente", []) if not masse.get(k)], "| Modus", ent.get("modus"), "| Schluessel", ent.get("schluessel"))
        if a[1] == "elemente": return
        aus = o("--aus", os.path.join(rdir, "element_urteil_" + time.strftime("%Y%m%d_%H%M%S"))); vdir, vstl = o("--vorher_dir", td), o("--vorher_stl", o("--stl"))
        mess = elemente_nachher(ent, teil, o("--nachher_dir"), o("--nachher_stl"), vstl, obj, fotos, o("--cwd", root), aus, vorher_dir=vdir)
        if mess.get("infra"): print("INFRA", mess); sys.exit(2)
        for nm in mess.get("betroffen", []): print(nm, "vorher", mess["vorher"].get(nm), "nachher", mess["nachher"].get(nm))
        ok, txt, info = urteil_elemente(ent, masse, mess); print("URTEIL:", "BESTEHT" if ok else "ABGELEHNT", "|", txt)
        json.dump({"ok": ok, "text": txt, "info": info, "mess": mess}, open(os.path.join(aus, "urteil.json"), "w"), ensure_ascii=False, indent=1); return
    e = berechnen(rdir, obj, teil, td, o("--stl"), fotos, o("--cwd", root))
    print(json.dumps({k: e.get(k) for k in ("teil", "R", "trennend", "werte_vorher", "nullen", "fehler", "infra", "laufzeit_s", "schluessel")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    _main()

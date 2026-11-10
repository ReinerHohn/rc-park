#!/usr/bin/env python3
"""kreis_nachmessen.py - verworfene Kreisrunden mit dem FOTO-TOR nachmessen (Nutzer 10.11. abends: "Kannst du aus den heutigen Laeufen
die Daten weiterhin nutzen? Wenn das Foto gewinnt, haetten wir die Rechenzeit nicht umsonst gehabt").

Je verworfene Runde (kein Fehlteil, Abnahme gruen, Teile-Export vorher UND nachher vorhanden):
  Foto-F1 des Zielteils vorher/nachher mit tools/teil_fotoform.py auf denselben Fotos (Top-10 der Formliste fuer das Teil).
  Ganzes Modell fuer Verdeckung/Modellkanten = Vereinigung der exportierten Teile ohne '__ausschnitt' (Schnittkoerper);
  vorher und nachher gleich behandelt -> Differenz vergleichbar. Gegenprobe: Runden mit Tor-Messung (foto_f1 im Protokoll) werden
  mitgemessen und die Abweichung zum Torwert berichtet (--gegenprobe).
  Messungen gecacht je (Teil, Hash der Teil-STLs): gleiche Basis = eine Messung.
Ergebnis: <kreisdir>/<objekt>/nachmessung_<datum>.json + Tabelle; Kandidat = Foto-F1 +>= --min_gewinn_foto und kein Veto
(Gitter-F1/Foto-F1 aus dem Protokoll; Wolkenbeleg nur bei Anteil mit Daten >= --min_daten). Kandidaten werden NICHT uebernommen -
das macht der Kreis (Patch auf aktuelles main, volles Tor inkl. Pruefer).

Aufruf: python3 tools/kreis_nachmessen.py <objekt> [--datum 20261110] [--nur_lauf L] [--max N] [--gegenprobe] [--trocken]
"""
import sys, os, json, glob, hashlib, subprocess, argparse, time
import numpy as np, trimesh

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/media/oem/scan/venv-seg/bin/python"


def dir_hash(d):
    h = hashlib.sha256()
    for p in sorted(glob.glob(os.path.join(d, "*.stl"))):
        h.update(os.path.basename(p).encode()); h.update(open(p, "rb").read())
    return h.hexdigest()[:16]


def ganz_stl(d, aus):
    ms = [trimesh.load(p, force="mesh") for p in sorted(glob.glob(os.path.join(d, "*.stl"))) if "__ausschnitt" not in os.path.basename(p)]
    ms = [m for m in ms if isinstance(m, trimesh.Trimesh) and len(m.faces)]
    trimesh.util.concatenate(ms).export(aus)


def messen(objekt, tdir, teil, fotos, cache_dir, log):
    key = f"{teil}_{dir_hash(tdir)}_{hashlib.sha256(','.join(fotos).encode()).hexdigest()[:8]}"
    cj = os.path.join(cache_dir, key + ".json")
    if not os.path.exists(cj):
        stl = os.path.join(cache_dir, key + "_ganz.stl")
        if not os.path.exists(stl): ganz_stl(tdir, stl)
        t0 = time.time()
        subprocess.run([PY, "-W", "ignore", "-I", os.path.join(R0, "tools", "teil_fotoform.py"), objekt, "--teile_dir", tdir, "--stl", stl,
                        "--nur", teil, "--fotos", ",".join(fotos), "--aus", cj], cwd=R0, stdout=open(os.path.join(cache_dir, key + ".log"), "w"), stderr=subprocess.STDOUT)
        log(f"  gemessen {key} in {time.time() - t0:.0f} s")
    try: return ((json.load(open(cj))["teile"].get(teil) or {}).get("_gesamt") or {}).get("f1")
    except Exception: return None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--datum", default=time.strftime("%Y%m%d"))
    ap.add_argument("--kreisdir", default="/media/oem/scan/rc-park_kreis"); ap.add_argument("--nur_lauf"); ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--min_gewinn_foto", type=float, default=0.02); ap.add_argument("--min_daten", type=float, default=0.3)
    ap.add_argument("--gegenprobe", action="store_true", help="nur Runden mit Tor-Foto-Messung (Methodenpruefung)"); ap.add_argument("--trocken", action="store_true")
    a = ap.parse_args(argv)
    KD = os.path.join(a.kreisdir, a.objekt); cache = os.path.join(KD, "nachmessung_cache"); os.makedirs(cache, exist_ok=True)
    fs = sorted(glob.glob(os.path.join(KD, "fotoform", "*.json")), key=os.path.getmtime); fl = json.load(open(fs[-1])) if fs else {}
    def fotos_fuer(teil, n=10):
        je = {k: v for k, v in ((fl.get("teile") or {}).get(teil) or {}).items() if k != "_gesamt"}
        return sorted(je, key=lambda k: -(je[k]["mk_px"] + je[k]["fk_px"]))[:n]
    aus = os.path.join(KD, f"nachmessung_{a.datum}.json")
    erg = json.load(open(aus)) if os.path.exists(aus) else {"runden": {}}
    def log(*x): print(time.strftime("%H:%M:%S"), *x, flush=True)
    jobs = []
    for f in sorted(glob.glob(os.path.join(KD, f"{a.datum}_*", "kreis.jsonl"))):
        L = os.path.dirname(f)
        if a.nur_lauf and os.path.basename(L) != a.nur_lauf: continue
        for l in open(f):
            try: d = json.loads(l)
            except Exception: continue
            if d.get("angenommen") is not False or not d.get("tor_abnahme"): continue
            teil = (d.get("ziel") or {}).get("teil", "")
            if not teil or teil.endswith("__neu") or d.get("ersatz_teil"): continue
            r = d["runde"]; vd = next((p for p in (os.path.join(L, f"teile_r{r}_vorher"), os.path.join(L, f"teile_r{r}_vorher_form")) if glob.glob(os.path.join(p, "*.stl"))), None)
            nd = os.path.join(L, f"teile_r{r}_nachher")
            if not vd or not glob.glob(os.path.join(nd, f"{teil}.stl")) or not os.path.exists(os.path.join(L, f"verworfen_r{r}.patch")): continue
            tor_ff = d.get("foto_f1")
            if a.gegenprobe and not tor_ff: continue
            jobs.append((os.path.basename(L), r, teil, vd, nd, d))
    if a.max: jobs = jobs[:a.max]
    log(f"{len(jobs)} Runden nachzumessen; eindeutige Basisstaende: {len({dir_hash(j[3]) + j[2] for j in jobs})}")
    if a.trocken:
        for j in jobs: print(j[0], j[1], j[2])
        return
    for lauf, r, teil, vd, nd, d in jobs:
        k = f"{lauf}:r{r}"
        if k in erg["runden"] and erg["runden"][k].get("nachher") is not None: continue
        fotos = d.get("foto_fotos") or fotos_fuer(teil)   # gleiche Fotos wie das Tor, wo bekannt
        if not fotos: log(k, teil, "keine Formfotos"); continue
        log(k, teil)
        v = messen(a.objekt, vd, teil, fotos, cache, log); n = messen(a.objekt, nd, teil, fotos, cache, log)
        z0 = (d.get("guete_vor_nach") or [None, None])
        rueck = [x for x in (d.get("rueckschritt_teil") or []) if x != "foto_f1"]
        anteil = ((d.get("ziel") or {}).get("anteil_mit_daten") or 0)
        if "beleg" in rueck and anteil < a.min_daten: rueck.remove("beleg")
        gew = None if (v is None or n is None) else round(n - v, 3)
        kand = gew is not None and gew >= a.min_gewinn_foto and not rueck
        erg["runden"][k] = {"teil": teil, "vorher": v, "nachher": n, "gewinn_foto": gew, "veto": rueck, "kandidat": kand, "tor_foto_f1": d.get("foto_f1"),
                            "patch": os.path.join(KD, lauf, f"verworfen_r{r}.patch"), "zeit": d.get("zeit")}
        log(f"  {teil}: Foto-F1 {v} -> {n} ({gew:+.3f})" if gew is not None else f"  {teil}: nicht messbar", "KANDIDAT" if kand else "", f"Veto {rueck}" if rueck else "",
            f"[Tor mass {d.get('foto_f1')}]" if d.get("foto_f1") else "")
        json.dump(erg, open(aus, "w"), indent=1, ensure_ascii=False)
    ks = [(k, v) for k, v in erg["runden"].items() if v.get("kandidat")]
    log(f"FERTIG: {len(erg['runden'])} gemessen, {len(ks)} Kandidaten -> {aus}")
    for k, v in sorted(ks, key=lambda kv: -kv[1]["gewinn_foto"]): print(f"  {k} {v['teil']} {v['vorher']} -> {v['nachher']} ({v['gewinn_foto']:+.3f})")


if __name__ == "__main__":
    main()

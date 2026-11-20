#!/usr/bin/env python3
"""qualitaetsstufen.py - Modellqualitaet in STUFEN, jede Stufe sichtbar (2026-11-04, Nutzerauftrag: "Treppenstufen: verschiedene Verfahren probieren,
mehrere Iterationen, ich schaue mir das HTML an und entscheide, wann es gut genug ist. Ziel richtig geile Modelle, das rechtfertigt mehr Zeit").

Jede Stufe = ein VERFAHREN fuer das ganze Modell, aufbauend auf der vorigen Stufe; ihr Endmodell wird gebaut und gegen ALLE Bewertungsfotos gemessen
(foto_diff, exakt gerastert, FESTE Bewertungsmaske aus Stufe 1 mit 3 m Rand -> Kosten ueber alle Stufen vergleichbar). HTML <aus>/index.html:
Spalten = Stufen (drehbares 3D-Modell, synchron, + Kennzahlen + Schritte), Zeilen = Fotos mit Kanten-Overlay. Das Objekt (objekt.json) bleibt
UNVERAENDERT: Stufen sind belegte Vorschlaege, Uebernahme entscheidet der Nutzer.

Verfahren:
  ausgang    Generator wie er ist.
  parameter  alle Generatorparameter der Liste der Reihe nach mit param_suche (Ergebnisse frueherer Schritte fest, --fest), mehrere Runden;
             uebernommen wird nur ein DEUTLICHES Ergebnis (param_suche 'ok' = beidseitig t >= 2), 'flach' behaelt den Wert.
  fassade    fassade_ortho + fassade_parsing (OWLv2) -> Bauteil fassade_auto; Versuche (Klassen zuschalten, Handbauteile abschalten) nur behalten,
             wenn gepaart ueber die Fotos deutlich besser (t <= -2).
  (geplant: gemeinsame Optimierung CMA-ES, Farbe je Bauteil - siehe modelle/QUALITAETSSTUFEN.md)

  /media/oem/scan/venv-seg/bin/python -I tools/qualitaetsstufen.py modelle/<obj>/objekt.json --plan modelle/<obj>/qualitaetsstufen.json [--fotos 12] [--aus DIR]
Fortsetzbar: <aus>/stand.json (fertige Stufen und Schritte werden uebersprungen).
Ausgaben in --aus: index.html (Stufenvergleich), stand.json. Oder `tools/py tools/qualitaetsstufen.py ...` (venv-seg; Generator per objekt.json "generator").
Exit 0 = alle Stufen fertig; Generator/Pruefstand/Teilwerkzeug fehlgeschlagen -> Abbruch mit Text (Exit 1), fortsetzbar.
"""
import sys, os, json, argparse, subprocess, time, base64, html, shutil, re, numpy as np, cv2
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import param_suche as PS
import elementbuch as EB
import fehlerkarte as FKM
import kandidaten as KAND

PY = PS.PY; ROOT = PS.ROOT; TOOLS = PS.TOOLS


def bauen_fest(obj, fest, name, elem):
    """Generator mit allen festen Parametern (BAUTEIL_PARAM) -> STL-Pfad relativ zu ROOT."""
    cmd = obj["generator"]; cmd = re.sub(r"STL_NAME=\S+", f"STL_NAME={name}", cmd) if "STL_NAME=" in cmd else f"STL_NAME={name} " + cmd
    r = subprocess.run(["bash", "-c", cmd.replace("~", os.path.expanduser("~"))], cwd=ROOT, env=dict(os.environ, BAUTEIL_PARAM=json.dumps(fest), ELEMENTE_AUS=elem), capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit(f"Generator fehlgeschlagen: {(r.stderr or r.stdout)[-500:]}")
    return os.path.join("modelle", "stl", name)


_TOR = {}
def tor_pruefung(ctx, fest):
    """Pruefstand am Kandidaten (CPU, ~1 s) -> {Pruefname: dict(status, wert, quelltyp)} ALLER Pruefungen der Masstabelle (S1b: Werte fuer das Freiraum-Tor)."""
    k = json.dumps(fest, sort_keys=True)
    if k in _TOR: return _TOR[k]
    od = os.path.basename(os.path.dirname(ctx["objp"])); nm = f"_qs_{od}_tor_{len(_TOR)}.stl"; el = os.path.join(ctx["aus"], "tor_elemente.json")
    stl = os.path.join(ROOT, bauen_fest(ctx["obj"], fest, nm, el)); pb = os.path.join(ctx["aus"], "tor_pruefbericht.json")
    r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "pruefstand.py"), ctx["objp"], "--stl", stl, "--bericht", pb], cwd=ROOT, capture_output=True, text=True); os.remove(stl)
    if r.returncode == 2 or not os.path.exists(pb): raise SystemExit("Pruefstand-Tor: Tabelle unzulaessig/kein Bericht: " + (r.stdout + r.stderr)[-400:])
    qt = {p["name"]: p.get("quelltyp", "?") for p in json.load(open(os.path.join(ROOT, ctx["obj"]["masstabelle"])))["pruefungen"]}
    _TOR[k] = {x["name"]: dict(status=x["status"], wert=x.get("wert"), quelltyp=qt.get(x["name"], "?")) for x in json.load(open(pb))["pruefungen"]}; return _TOR[k]


def tor_fehler(ctx, fest):
    """{Pruefname: quelltyp} der fehlgeschlagenen Pruefungen (wie bisher)."""
    return {k: v["quelltyp"] for k, v in tor_pruefung(ctx, fest).items() if v["status"] == "fehler"}


def tor_ok(ctx, neu, alt, was):
    """Tor (Nutzer 2026-11-05: "Laser ist nicht die Quelle der Wahrheit"): HART nur Druckfaehigkeit (quelltyp 'modell': wasserdicht, ein Koerper).
    Neu verletzte QUELLEN-Pruefungen (lod2, laser, foto ...) verwerfen NICHT, sondern werden als WIDERSPRUCH (Regel 5) in die Masstabelle eingetragen."""
    fa, fn_ = tor_fehler(ctx, alt), tor_fehler(ctx, neu); neu_f = {k: v for k, v in fn_.items() if k not in fa}
    hart = sorted(k for k, v in neu_f.items() if v == "modell"); quelle = sorted(k for k, v in neu_f.items() if v != "modell")
    if quelle:
        print(f"      WIDERSPRUCH (nicht verworfen): {was} verletzt {', '.join(f'{k} [{neu_f[k]}]' for k in quelle)} -> Masstabelle beobachtungen_offen", flush=True)
        mp = os.path.join(ROOT, ctx["obj"]["masstabelle"]); T = json.load(open(mp))
        T.setdefault("beobachtungen_offen", []).append(dict(datum=time.strftime("%Y-%m-%d %H:%M"), wer="qualitaetsstufen (automatisch)",
            text=f"WIDERSPRUCH Foto-Kantenvergleich vs {', '.join(f'{k} [{neu_f[k]}]' for k in quelle)}: {was} (Stufe {ctx.get('nr')})",
            naechster_schritt="unabhaengige dritte Messung (eigene Fotos mit Massstab / Handmass); Kamerarahmen-Hoehe pruefen; nicht mitteln, keine Quelle gilt als Wahrheit"))
        json.dump(T, open(mp, "w"), indent=1, ensure_ascii=False)
    if hart: print(f"      Pruefstand-Tor: {was} VERWORFEN (nicht druckbar): {', '.join(hart)}", flush=True)
    return not hart


def vram_budget(fotos, objp):
    """Grafikspeicher-Budget je Foto (2026-11-05: null5 Stufe 3 - 7 von 33 Fotos parallel mit Speicherueberlauf, einzeln ok -> Zeitverlust und Absturzgefahr im Nachtlauf).
    Bedarf 0,5 GB + 0,2 GB je Megapixel, hoechstens 7,5 (gemessen 2026-11-05 Rastererfehler: 20 MP-Prozess 4,3-4,6 GB, 9 MP ~1,6 GB; 86 MP rechnet verkleinert ~7 GB). Ein Foto startet erst, wenn sein Bedarf ins freie Budget passt;
    ein Foto groesser als das Budget laeuft allein. Ohne nvidia-smi: kein Limit."""
    import threading, contextlib, PIL.Image
    try: gesamt = float(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0]) / 1024 - 0.7
    except Exception: gesamt = None
    obj = json.load(open(objp)); bed = {}
    for nr in fotos:
        try: w, h = PIL.Image.open(glob_eins(os.path.join(ROOT, obj["fotos_dir"], nr + "_*"))).size; bed[nr] = min(7.5, 0.5 + 0.2 * w * h / 1e6)
        except Exception: bed[nr] = 2.0
    cv_ = threading.Condition(); belegt = [0.0]
    @contextlib.contextmanager
    def nimm(nr):
        b = bed.get(nr, 2.0)
        if gesamt is None: yield; return
        with cv_:
            while belegt[0] > 0 and belegt[0] + b > gesamt: cv_.wait()
            belegt[0] += b
        try: yield
        finally:
            with cv_: belegt[0] -= b; cv_.notify_all()
    return nimm


def glob_eins(muster):
    import glob as _g; return sorted(_g.glob(muster))[0]


def bewerten(objp, fotos, stl, aus, maske_dir=None, maske_aus=None, karte=False):
    """foto_diff (Standard: exakt gerastert, GPU) je Foto parallel; maske_aus schreibt die Bewertungsmaske, maske_dir bewertet darin (kosten_param)."""
    budget = vram_budget(fotos, objp)
    def eins(nr):
        with budget(nr): return _eins(nr)
    def _eins(nr):
        a = os.path.join(aus, nr); os.makedirs(a, exist_ok=True); x = ["--stl", stl, "--aus", a]
        if maske_aus: x += ["--maske-aus", os.path.join(maske_aus, f"{nr}.png"), "--maske-rand", "3.0"]
        if maske_dir: x += ["--bewertung-maske", os.path.join(maske_dir, f"{nr}.png")]
        if karte and maske_dir: x += ["--kostenkarte", os.path.join(a, "kostenkarte.npz")]                  # S1b: Kostenkarte fuer das Elementbuch (lokale Kennzahl je Element)
        r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "foto_diff.py"), objp, nr] + x, cwd=ROOT, env=dict(os.environ, FD_GPU="1", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"), capture_output=True, text=True)
        if r.returncode not in (0, 1, 3):
            open(os.path.join(a, "fehler.log"), "w").write(f"rc {r.returncode}\n" + r.stdout[-2000:] + "\n" + r.stderr[-4000:]); return nr, None   # Ursache sichtbar (Grafikspeicher/RAM)
        try: return nr, json.load(open(os.path.join(a, f"foto_diff_{nr}.json")))
        except Exception as ex:
            open(os.path.join(a, "fehler.log"), "w").write(f"rc {r.returncode}, kein JSON ({ex})\n" + r.stdout[-2000:] + "\n" + r.stderr[-4000:]); return nr, None
    with ThreadPoolExecutor(PS.arbeiter_zahl(len(fotos))) as ex: erg = dict(ex.map(eins, fotos))
    for nr in [n for n, v in erg.items() if v is None]:                                               # Fehlschlag (z. B. Grafikspeicher voll): einzeln wiederholen, nicht stillschweigend fehlen
        erg[nr] = _eins(nr)[1]; print(f"      Foto {nr} einzeln wiederholt: {'ok' if erg[nr] else 'FEHLT weiter'}", flush=True)
    return erg


RG_FELDER = ("anteil_modellkanten_ohne_foto", "anteil_fotokanten_ohne_modell")                 # foto_diff-Felder fuer rot/gelb; nach S2 umstellbar (test_tor_elementbuch --rg-feld rot_versatz,gelb_versatz)


def rg_von(v):
    """[rot, gelb] eines foto_diff-Ergebnisses = die Felder RG_FELDER (Standard anteil_modellkanten_ohne_foto / anteil_fotokanten_ohne_modell) oder None."""
    if not v or v.get(RG_FELDER[0]) is None or v.get(RG_FELDER[1]) is None: return None
    return [round(float(v[RG_FELDER[0]]), 4), round(float(v[RG_FELDER[1]]), 4)]


def kennzahlen(e):
    ok = [v for v in e.values() if v]
    m = lambda key: round(float(np.mean([v[key] for v in ok if v.get(key) is not None])), 4) if ok else None
    return dict(kosten=m("kosten_param"), modell_ohne_foto=m("anteil_modellkanten_ohne_foto"), foto_ohne_modell=m("anteil_fotokanten_ohne_modell"), fotos=len(ok))


def bild64(p, breite=640):
    im = cv2.imread(p)
    if im is None: return ""
    s = breite / im.shape[1]; im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return "data:image/jpeg;base64," + base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]).decode()


def modell_messen(objp, obj, fotos, aus, tag, fest, md):
    """Endmodell einer Stufe (oder eines Schritts) bauen und messen -> Eintrag mit Kennzahlen, Bildern, STL."""
    od = os.path.dirname(objp); stl = bauen_fest(obj, fest, f"_qs_{os.path.basename(od)}_{tag}.stl", os.path.join(aus, f"elemente_{tag}.json"))
    sd = os.path.join(aus, f"messung_{tag}"); e = bewerten(objp, fotos, stl, sd, maske_dir=md, karte=True); ziel = os.path.join(aus, f"modell_{tag}.stl"); shutil.move(os.path.join(ROOT, stl), ziel)
    return dict(fest=json.loads(json.dumps(fest)), kennzahlen=kennzahlen(e), stl=ziel,
                je_foto={nr: (round(v["kosten_param"], 4) if v and v.get("kosten_param") is not None else None) for nr, v in e.items()},
                je_foto_rg={nr: rg_von(v) for nr, v in e.items()},
                karten={nr: os.path.join(sd, nr, "kostenkarte.npz") for nr in fotos if os.path.exists(os.path.join(sd, nr, "kostenkarte.npz"))},
                elemente=os.path.join(aus, f"elemente_{tag}.json"),
                bilder={nr: os.path.join(sd, nr, f"foto_diff_{nr}.jpg") for nr in fotos})



# ------------------------------------------------------------------ S1b: Staende, Uebernahmetor, Elementbuch
def _schluessel(fest): return json.dumps(fest, sort_keys=True)


def registrieren(st, m_):
    """Messergebnis (modell_messen oder alter Stufeneintrag) in die Caches der Stufe: Kosten, rot/gelb, Kostenkarten, Elementdatei. Fehlende Felder (alte stand.json) werden NICHT erfunden."""
    if not m_ or "fest" not in m_: return
    k = _schluessel(m_["fest"])
    if m_.get("je_foto"): st.setdefault("kosten_cache", {}).setdefault(k, {}).update({nr: v for nr, v in m_["je_foto"].items() if v is not None})
    if m_.get("je_foto_rg"): st.setdefault("rg_cache", {}).setdefault(k, {}).update(m_["je_foto_rg"])
    if m_.get("karten"): st.setdefault("karten_cache", {}).setdefault(k, {}).update(m_["karten"])
    if m_.get("elemente") and os.path.exists(m_["elemente"]): st.setdefault("elem_cache", {})[k] = m_["elemente"]


def stand_von(ctx, st, fest, fotos, tag):
    """Stand = Kosten + rot/gelb + Kostenkarten + Elementdatei eines Generatorstands auf `fotos`, gecacht je Stand+Foto (st['kosten_cache'] usw.).
    Fehlt etwas (auch bei alter stand.json ohne je_foto_rg), wird gebaut und die fehlenden Fotos gemessen - nie abgestuerzt, nie geraten."""
    k = _schluessel(fest); kc = st.setdefault("kosten_cache", {}).setdefault(k, {}); rc = st.setdefault("rg_cache", {}).setdefault(k, {}); pc = st.setdefault("karten_cache", {}).setdefault(k, {})
    ec = st.setdefault("elem_cache", {}); od = os.path.basename(os.path.dirname(ctx["objp"]))
    fehlt = [nr for nr in fotos if nr not in kc or nr not in rc or nr not in pc or (pc[nr] and not os.path.exists(pc[nr]))]
    if fehlt or k not in ec or not os.path.exists(ec[k]):
        ef_ = os.path.join(ctx["aus"], f"elemente_{tag}.json"); stl = bauen_fest(ctx["obj"], fest, f"_qs_{od}_{tag}.stl", ef_); sd = os.path.join(ctx["aus"], f"entscheid_{tag}")
        try:
            e = bewerten(ctx["objp"], fehlt, stl, sd, maske_dir=ctx["md"], karte=True) if fehlt else {}
        finally: os.remove(os.path.join(ROOT, stl))
        for nr in fehlt:
            v_ = e.get(nr); kc[nr] = round(v_["kosten_param"], 4) if v_ and v_.get("kosten_param") is not None else None; rc[nr] = rg_von(v_)
            kp = os.path.join(sd, nr, "kostenkarte.npz"); pc[nr] = kp if os.path.exists(kp) else None
        ec[k] = ef_
    return dict(fest=fest, je_foto={nr: kc[nr] for nr in fotos}, je_foto_rg={nr: rc[nr] for nr in fotos}, karten={nr: pc[nr] for nr in fotos if pc.get(nr)}, elemente=ec[k], stl=None)


def karten_loeschen(st, fest, behalten=()):
    """Kostenkarten (gross) eines Stands loeschen; nur der uebernommene Stand behaelt sie (Spec 3). `behalten`: Staende, deren Karten stehen bleiben."""
    k = _schluessel(fest)
    if k in {_schluessel(b) for b in behalten}: return
    pc = st.setdefault("karten_cache", {}).get(k, {})
    for nr, pth in list(pc.items()):
        if pth and os.path.exists(pth): os.remove(pth)
        pc[nr] = None


def _kam(ctx):
    if "kam" not in ctx: ctx["kam"] = EB.Kameras(ctx["objp"], ctx["obj"], ROOT)
    return ctx["kam"]


def restfeld_messen(ctx, stand, fassaden_json, dach=False):
    """Restfeld (restfeld_fassade.py) eines Stands -> {fassade: dict(anteil, mittel_abs)}; STL notfalls neu gebaut, Ergebnis je Stand gecacht (<aus>/restfeld_<hash>). Laufzeit in 'sekunden'."""
    import hashlib
    fc = ctx["obj"].get("freiraum") or {}; odir = os.path.dirname(ctx["objp"]); P_ = lambda x: x if os.path.isabs(x) else os.path.join(odir, x)
    h = hashlib.md5(_schluessel(stand["fest"]).encode()).hexdigest()[:10]; rd = os.path.join(ctx["aus"], f"restfeld_{h}" + ("_dach" if dach else "")); rj = os.path.join(rd, "restfeld.json")   # S3: dach=True -> auch Dachebenen (Fehlerkarte); Tor (c) bleibt ohne Dach
    if not os.path.exists(rj):
        eigen = not (stand.get("stl") and os.path.exists(stand["stl"])); t0 = time.time()
        stl = os.path.join(ROOT, bauen_fest(ctx["obj"], stand["fest"], f"_qs_{os.path.basename(odir)}_rest{h}.stl", os.path.join(ctx["aus"], f"elemente_rest{h}.json"))) if eigen else stand["stl"]
        try:
            rr = subprocess.run(["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={fc.get('speicher', '6G')}", PY, "-W", "ignore", "-I", os.path.join(TOOLS, "restfeld_fassade.py"), "--stl", stl,
                                 "--dicht", P_(fc["dicht"]), "--ausrichtung", P_(fc["ausrichtung"]), "--fassaden", fassaden_json, "--aus", rd] + (["--dach"] if dach else []), cwd=ROOT, capture_output=True, text=True)
        finally:
            if eigen and os.path.exists(stl): os.remove(stl)
        open(rd + ".log", "w").write(rr.stdout + rr.stderr)
        if rr.returncode != 0 or not os.path.exists(rj): raise SystemExit(f"restfeld_fassade fehlgeschlagen: {(rr.stderr or rr.stdout)[-500:]}")
        R_ = json.load(open(rj)); R_["laufzeit_gesamt_s"] = round(time.time() - t0, 1); json.dump(R_, open(rj, "w"), indent=1)
    if dach: return rd
    R = json.load(open(rj)); tief = float(R["parameter"]["tief"]); out = {}
    for fid in R["fassaden"]:
        z = np.load(os.path.join(rd, f"restfeld_{fid}.npz")); daten, modell = z["daten"], z["modell"]; beob = ~np.isnan(daten)
        if not beob.any(): continue
        rest = daten - np.where(np.isnan(modell), -tief, modell); out[fid] = dict(anteil=float(beob.mean()), mittel_abs=float(np.abs(rest[beob]).mean()))
    return out, R.get("laufzeit_gesamt_s", R.get("sekunden"))


def uebernahme_tor(ctx, name, neu, alt, fotos, cfg):
    """Uebernahmetor S1b (SPEC_S1b_TOR_ELEMENTBUCH): alle Bedingungen muessen gelten, jede Verletzung = Grund mit Buchstaben.
    (a) je Foto Summe rot+gelb nicht schlechter (+ tor_toleranz; Einzelgroesse <= +0.10; geaendert nach T2 5.11.), (b) in der Summe deutlich besser (gepaart dm < 0, t <= -2; Freiraum/'nicht_schlechter': foto_freiraum-Pruefung faellt;
    Zier: IoU-Entscheid cfg['_zier_ok']), (c) Restfeld nicht schlechter (Plan tor_restfeld), (d) Pruefstand (nur Druckbarkeit hart), (e) Elementbuch (jedes geaenderte Element lokal).
    neu/alt: Stand-Dicts (stand_von / modell_messen). Standard bricht nach (a)/(b) ab (teure Stufen sparen); cfg/Plan 'tor_alle' wertet alles aus (Beweistest).
    -> (ok, gruende, detail)"""
    plan = ctx.get("plan") or {}; g = lambda k, d=None: cfg.get(k, plan.get(k, d)); tol = float(g("tor_toleranz", 0.01)); alle = bool(g("tor_alle", False))
    gruende = []; det = dict(name=name, tol=tol)
    # (a) je Foto nicht schlechter
    rn, ra = neu.get("je_foto_rg") or {}, alt.get("je_foto_rg") or {}; verl = []; n_a = 0
    for nr in fotos:                                                                               # GEAENDERT nach T2 (5.11.): rot und gelb tauschen sich bei jeder Kantenkorrektur aus -> je Foto die SUMME (rot+gelb)
        a_, n_ = ra.get(nr), rn.get(nr)                                                            # darf um nicht mehr als tol steigen; zusaetzlich keine Einzelgroesse um mehr als 0,10 (Schutz 'Modell weg = rot 0')
        if not a_ or not n_: continue
        n_a += 1
        if sum(n_) > sum(a_) + tol: verl.append(f"{nr} Summe {sum(a_):.3f}->{sum(n_):.3f}")
        for i, art in enumerate(("rot", "gelb")):
            if n_[i] > a_[i] + 0.10: verl.append(f"{nr} {art} {a_[i]:.3f}->{n_[i]:.3f} (> +0.10)")
    det["a"] = dict(fotos=n_a, verletzt=verl, regel="Summe rot+gelb <= alt + tol, Einzelgroesse <= +0.10")
    if n_a < 3: gruende.append(f"(a) nur {n_a} Fotos mit rot/gelb vergleichbar (< 3)")
    if verl: gruende.append(f"(a) je Foto schlechter (Summe > +{tol} oder Einzel > +0.10): " + "; ".join(verl[:8]) + (f" (+{len(verl) - 8})" if len(verl) > 8 else ""))
    # (b) in der Summe deutlich besser (oder eigene Messquelle)
    if g("freiraum") or g("entscheid") == "nicht_schlechter":
        pa, pn = tor_pruefung(ctx, alt["fest"]), tor_pruefung(ctx, neu["fest"]); ks = sorted(k for k, v in pn.items() if v["quelltyp"] == "foto_freiraum"); wv = {}
        for k in ks: wv[k] = (pa.get(k, {}).get("wert"), pn[k].get("wert"))
        det["b"] = dict(art="foto_freiraum", werte=wv)
        if not ks: gruende.append("(b) keine Pruefung mit quelltyp foto_freiraum in der Masstabelle")
        elif not any(a_ is not None and n_ is not None and n_ < a_ for a_, n_ in wv.values()) or any(a_ is None or n_ is None or n_ > a_ for a_, n_ in wv.values()):
            gruende.append("(b) foto_freiraum-Pruefung faellt nicht: " + "; ".join(f"{k} {a_}->{n_}" for k, (a_, n_) in wv.items()))
    elif g("entscheid") == "zier":
        det["b"] = dict(art="zier", ok=bool(cfg.get("_zier_ok")), text=cfg.get("_zier_text", ""))
        if not cfg.get("_zier_ok"): gruende.append("(b) Zierteile nicht deutlich besser: " + str(cfg.get("_zier_text", "")))
    else:
        dm, t, nn = gepaart({nr: neu["je_foto"].get(nr) for nr in fotos}, {nr: alt["je_foto"].get(nr) for nr in fotos})
        if abs(dm) < 1e-12: t = 0.0
        det["b"] = dict(art="gepaart", dm=round(dm, 5), t=round(t, 2), n=nn)
        if not (dm < 0 and t <= -2.0): gruende.append(f"(b) in der Summe nicht deutlich besser: dm {dm:+.4f}, t {t:+.1f}, {nn} Fotos")
    # (c) Restfeld
    if (gruende and not alle) or not (g("tor_restfeld") and (ctx["obj"].get("freiraum"))): det["c"] = "nicht geprueft"
    else:
        fj = ctx.get("fassaden_json") or sorted(__import__("glob").glob(os.path.join(ctx["aus"], "fassade_ortho_s*", "fassaden.json")))[-1]
        rn_, sn = restfeld_messen(ctx, neu, fj); ra_, sa = restfeld_messen(ctx, alt, fj); verl = []
        for fid, v in rn_.items():
            if v["anteil"] >= 0.3 and fid in ra_ and v["mittel_abs"] > ra_[fid]["mittel_abs"] + 0.02: verl.append(f"{fid} {ra_[fid]['mittel_abs']:.3f}->{v['mittel_abs']:.3f}")
        det["c"] = dict(verletzt=verl, sekunden=[sn, sa])
        if verl: gruende.append("(c) Restfeld schlechter (mittel |Rest| > +0.02 m): " + "; ".join(verl))
    # (f) Dachquellen (S3, SPEC 0b): Dachparameter nur, wenn Stadt-LoD2 ODER Stadtmesh die Richtung bestaetigen (die dichte Wolke liegt auf glatten Ziegelflaechen 1,4 m zu tief)
    if g("dach_f") is not None:
        det["f"] = dict(ok=bool(g("dach_f")), bestaetigt_durch=g("dach_f_quellen", []))
        if not g("dach_f"): gruende.append("(f) Dachparameter: weder Stadt-LoD2 noch Stadtmesh bestaetigen die Richtung (Wolke gesperrt, Spec 0b)")
    # (d) Pruefstand: hart nur Druckbarkeit (Quellenverletzung = Widerspruch in der Masstabelle)
    if gruende and not alle: det["d"] = "nicht geprueft"
    else:
        det["d"] = bool(tor_ok(ctx, neu["fest"], alt["fest"], name))
        if not det["d"]: gruende.append("(d) Pruefstand: nicht druckbar")
    # (e) Elementbuch
    if gruende and not alle: det["e"] = "nicht geprueft"
    elif not (neu.get("elemente") and alt.get("elemente") and neu.get("karten") and alt.get("karten")):
        det["e"] = "Daten fehlen"; gruende.append("(e) Elementdatei/Kostenkarten fehlen -> Elementbuch nicht pruefbar")
    else:
        ok_e, gr_e, de = EB.pruefen(alt, neu, fotos, _kam(ctx)); gruende += gr_e
        det["e"] = dict(zaehlung=de["zaehlung"], ungeprueft=de["ungeprueft"], uebersprungen=de["uebersprungen"], status={k: v["status"] for k, v in de["elemente"].items() if v["art"] != "gleich_geformt"}, voll=de)
        if de.get("gemischt"): print(f"      Elementbuch: {len(de['gemischt'])} Elemente 'gemischt' (blockiert nicht): {', '.join(de['gemischt'][:6])}", flush=True)
        if de["ungeprueft"]: print(f"      Elementbuch: {de['zaehlung']['nicht beurteilbar']} Elemente nicht beurteilbar -> (e) ungeprueft", flush=True)
    if det["e"] != "nicht geprueft" and isinstance(det["e"], dict) and det["e"].get("uebersprungen"): print(f"      Elementbuch: ohne Geometrie uebersprungen: {len(det['e']['uebersprungen'])} Belege", flush=True)
    ok = not gruende
    print(f"      Tor {name}: {'JA' if ok else 'NEIN'}" + ("" if ok else " - " + " | ".join(gruende[:4])), flush=True)
    return ok, gruende, det


def tor_kurz(det):
    """Detail fuer stand.json/Schritt (ohne die grossen Elementlisten)."""
    d = json.loads(json.dumps({k: v for k, v in det.items()}, default=str))
    if isinstance(d.get("e"), dict): d["e"].pop("voll", None)
    return d


def entscheide_fest(ctx, st, name, neu_fest, alt_fest, fotos, cfg, tag, behalten=()):
    """Stand_von neu/alt auf `fotos`, uebernahme_tor, bei Uebernahme Elementbuch aktualisieren; Kostenkarten des Verlierers loeschen (ausser `behalten`). -> (ok, gruende, detail)."""
    neu = stand_von(ctx, st, neu_fest, fotos, f"{tag}_n"); alt = stand_von(ctx, st, alt_fest, fotos, f"{tag}_a")
    ok, gr, det = uebernahme_tor(ctx, name, neu, alt, fotos, cfg)
    if ok: buch_aktualisieren(ctx, st, neu_fest, fotos, tag)
    karten_loeschen(st, alt_fest if ok else neu_fest, behalten)
    return ok, gr, det


def buch_aktualisieren(ctx, st, fest, fotos, tag):
    """elemente_best.json (<aus>) nach einer Uebernahme."""
    s_ = stand_von(ctx, st, fest, fotos, f"{tag}_b")
    n = EB.aktualisieren(os.path.join(ctx["aus"], "elemente_best.json"), s_, fotos, _kam(ctx), f"s{ctx['nr']} {tag}", fest.get("fassade_auto"))
    print(f"      Elementbuch: {n} Elemente (elemente_best.json)", flush=True)


# ------------------------------------------------------------------ Verfahren
def v_ausgang(ctx, st, cfg):
    """Ausgangsmodell. cfg 'giebel_zaehlen' (2026-11-05): Treppengiebel-Stufen VOR dem Messen automatisch am Foto zaehlen (giebel_stufen_zaehlen.py ->
    Z-Protokoll, Regel 9) und in objekt.json eintragen - die Flanken kommen aus einem Probebau (Flanken haengen nicht von der Stufenzahl ab)."""
    if cfg.get("giebel_zaehlen") and not st.get("giebel"):
        el = os.path.join(ctx["aus"], "elemente_giebel.json"); stl = bauen_fest(ctx["obj"], {}, f"_qs_{os.path.basename(os.path.dirname(ctx['objp']))}_giebel.stl", el)
        rr = subprocess.run([PY, "-I", os.path.join(TOOLS, "giebel_stufen_zaehlen.py"), ctx["objp"], "--elemente", el, "--stl", os.path.join(ROOT, stl), "--schreiben"], cwd=ROOT, capture_output=True, text=True)
        open(os.path.join(ctx["aus"], "giebel_stufen.log"), "w").write(rr.stdout + rr.stderr); os.remove(os.path.join(ROOT, stl))
        g = json.load(open(os.path.join(os.path.dirname(ctx["objp"]), "audit", "giebel_stufen", "giebel_stufen.json")))
        if rr.returncode != 0 or "protokoll" not in g: raise SystemExit("giebel_stufen_zaehlen ohne Ergebnis: " + (rr.stderr or rr.stdout)[-400:])
        o = json.load(open(ctx["objp"]))
        for b in o.get("bauteile", []):
            if b["typ"] == "treppengiebel": b["stufen_je_flanke"] = int(g["ergebnis"]); b["zaehlung"] = [g["protokoll"]]
        json.dump(o, open(ctx["objp"], "w"), indent=1, ensure_ascii=False); ctx["obj"].update(o)
        st["giebel"] = dict(stufen=int(g["ergebnis"]), protokoll=g["protokoll"], einig=g.get("einig")); print(f"    Treppengiebel automatisch: {g['ergebnis']} Stufen ({g['protokoll']})", flush=True)
    if cfg.get("giebel_spitze_messen") and not st.get("giebel_spitze"):                              # Giebelspitze TRIANGULIERT (spitze_hoehe.py) statt ANNAHME spitze_m 1,0 m (2026-11-05: Fotos 20,26/20,58 m, Modell 21,97 -> 1,4-1,7 m zu hoch)
        el = os.path.join(ctx["aus"], "elemente_giebelspitze.json"); stl = bauen_fest(ctx["obj"], {}, f"_qs_{os.path.basename(os.path.dirname(ctx['objp']))}_gspitze.stl", el); os.remove(os.path.join(ROOT, stl))
        fl = [f for e in json.load(open(el)) if e.get("flanken") for f in (json.loads(e["flanken"].replace("'", '"')) if isinstance(e["flanken"], str) else e["flanken"])]
        zt_ = max(f["linie"][1][2] for f in fl); zf = float(next(e["first_z"] for e in json.load(open(el)) if e.get("first_z") is not None)); achsen = {}   # First (Generator) != Flankenoberkante (First - Neigung x halbe Spitzenbreite)
        for f in fl: achsen.setdefault(f["ende"], []).append(f["linie"][1][:2])
        sd = os.path.join(ctx["aus"], "giebelspitze"); cmd = [PY, "-I", os.path.join(TOOLS, "spitze_hoehe.py"), ctx["objp"], "--hoehe-max", "8", "--aus", sd]
        for e_, pts in sorted(achsen.items()): cmd += ["--achse", *[f"{x:.3f}" for x in np.mean(pts, 0)], f"{zt_ - 3.0:.3f}"]
        rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True); open(sd + ".log", "w").write(rr.stdout + rr.stderr)
        tri = [] if rr.returncode != 0 else [r["triangulation"] for r in json.load(open(os.path.join(sd, "spitze_hoehe.json")))["spitzen"] if (r.get("triangulation") or {}).get("n", 0) >= 4]
        if tri:
            zs_ = [t_["punkt"][2] for t_ in tri]; sp_ = round(float(np.median(zs_)) - zf, 3)
            O = json.load(open(ctx["objp"]))
            for b in O.get("bauteile", []):
                if b["typ"] == "treppengiebel":
                    km_ = round(max(0.0, float(np.median(zs_)) - zt_), 3)                                    # oberste Stufenkappe darf nicht ueber die gemessene Spitze ragen (Kappe gilt fuer alle Stufen: Messung nur an der obersten)
                    if b.get("kappe_m", 0.35) > km_: b["kappe_m"] = km_; b["kappe_quelle"] = f"<= gemessene Spitze - Flankenoberkante {zt_:.2f}"
                    b["spitze_m"] = sp_; b["spitze_quelle"] = f"spitze_hoehe.py Triangulation {', '.join(f'{z:.2f} m ({t_['n']} Fotos, RMS {t_['rms_m']:.2f})' for z, t_ in zip(zs_, tri))}; First {zf:.2f} (LoD2)"
            json.dump(O, open(ctx["objp"], "w"), indent=1, ensure_ascii=False); ctx["obj"] = O
            st["giebel_spitze"] = dict(z=zs_, spitze_m=sp_, first_z=zf); print(f"    Giebelspitze trianguliert: {', '.join(f'{z:.2f}' for z in zs_)} m, First {zf:.2f} -> spitze_m {sp_:+.2f} (statt ANNAHME 1,0), Kappe <= {max(0.0, float(np.median(zs_)) - zt_):.2f}", flush=True)
        else:
            st["giebel_spitze"] = dict(ergebnis="keine Triangulation", log=sd + ".log"); print("    Giebelspitze: keine Triangulation (>= 4 Fotos) - ANNAHME bleibt", flush=True)
    st.update(modell_messen(ctx["objp"], ctx["obj"], ctx["fotos"], ctx["aus"], "s1", {}, ctx["md"]))


def v_parameter(ctx, st, cfg):
    """Alle Parameter der Liste nacheinander (param_suche, Rest fest), cfg['runden'] Runden. Schritte fortsetzbar."""
    fest = json.loads(json.dumps(ctx["fest"])); st.setdefault("schritte", []); liste = cfg["parameter"]; n = 0
    if ctx.get("vorige"): registrieren(st, ctx["vorige"])
    for s_ in st["schritte"]: fest = s_["fest"]
    for r in range(1, int(cfg.get("runden", 2)) + 1):
        for p in liste:
            n += 1
            if n <= len(st["schritte"]): continue
            sa = os.path.join(ctx["aus"], f"suche_{ctx['nr']}_{n:02d}")
            cmd = [PY, "-u", "-I", os.path.join(TOOLS, "param_suche.py"), ctx["objp"], "--bauteil", p["bauteil"], "--param", p["param"], "--werte=" + p["werte"], "--fein",
                   "--fotoliste", ",".join(ctx["fotos"]), "--aus", sa, "--fest", json.dumps(fest), "--ergebnis-hier"]
            print(f"    Schritt {n} (Runde {r}): {p['bauteil']}.{p['param']} ({p['werte']})  [{time.time() - ctx['t0']:.0f} s]", flush=True)
            rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True); open(sa + ".log", "w").write(rr.stdout + rr.stderr)
            pf = os.path.join(sa, f"param_suche_{p['bauteil']}_{p['param']}.json")
            if rr.returncode != 0 or not os.path.exists(pf): raise SystemExit(f"param_suche fehlgeschlagen (Schritt {n}): {(rr.stderr or rr.stdout)[-600:]}")
            e = json.load(open(pf)); ueb = e["zustand"] == "ok"; alt = (fest.get(p["bauteil"]) or {}).get(p["param"]); tor_ = None
            if ueb:
                kand = json.loads(json.dumps(fest)); kand.setdefault(p["bauteil"], {}).update({p["param"]: e["bester_wert"], "quelle": f"Pruefstand-Tor Kandidat Stufe {ctx['nr']} Schritt {n}"})
                tor_ok_, tor_gr_, tor_det_ = entscheide_fest(ctx, st, f"{p['param']} = {e['bester_wert']}", kand, fest, ctx["fotos"], cfg, f"s{ctx['nr']}_p{n:02d}")
                tor_ = dict(ok=tor_ok_, gruende=tor_gr_, detail=tor_kurz(tor_det_))
                if not tor_ok_: ueb = False; e["zustand"] = "Uebernahmetor"
            if ueb: fest.setdefault(p["bauteil"], {}).update({p["param"]: e["bester_wert"], "quelle": f"qualitaetsstufen Stufe {ctx['nr']} Schritt {n}: param_suche {len(e['fotos'])} Fotos, deutlich (t >= 2), Kruemmung +-{e['unsicherheit_kruemmung']}"})
            print(f"      -> {p['param']} = {e['bester_wert']} ({e['zustand']}), {'uebernommen' if ueb else 'nicht uebernommen'}", flush=True)
            st["schritte"].append(dict(runde=r, bauteil=p["bauteil"], param=p["param"], werte=p["werte"], bester_wert=e["bester_wert"], vorher=alt, zustand=e["zustand"], uebernommen=ueb,
                                       streuung=e.get("streuung_fotos"), unsicherheit=e.get("unsicherheit_kruemmung"), hinweis=p.get("hinweis", ""), sekunden=e.get("sekunden"), fest=json.loads(json.dumps(fest)), tor=tor_))
            ctx["speichern"]()
    st.update(modell_messen(ctx["objp"], ctx["obj"], ctx["fotos"], ctx["aus"], f"s{ctx['nr']}", fest, ctx["md"]))


def gepaart(neu, alt):
    """Gepaarter Vergleich je Foto (gleiche feste Maske): mittlere Differenz und t = mittel / (sd / sqrt n). Negativ = besser."""
    d = np.array([neu[k] - alt[k] for k in neu if neu.get(k) is not None and alt.get(k) is not None], float)
    if len(d) < 3: return 0.0, 0.0, len(d)
    sd = float(d.std(ddof=1)); return float(d.mean()), (float(d.mean()) / (sd / np.sqrt(len(d))) if sd > 0 else (-99.0 if d.mean() < 0 else 99.0)), len(d)


def fassaden_aufloesen(cfg, FA, min_abdeckung=0.1):
    """Gebaeudeunabhaengiger Plan (Nachtlauf, 2026-11-05): 'alle' = Fassaden mit Fotoabdeckung >= min_abdeckung (fassade_ortho), 'haupt' = groesste
    Abdeckung x Flaeche, 'seiten' = alle ohne haupt. Ersetzt in versuche[].fassaden, .bloecke.fassaden, .relief.fassaden (Liste oder Zeichenkette)."""
    L = FA.values() if isinstance(FA, dict) else FA
    alle = [F["id"] for F in L if F.get("abdeckung_anteil", 0) >= min_abdeckung]
    haupt = max(L, key=lambda F: F.get("abdeckung_anteil", 0) * F.get("flaeche_m2", 0))["id"]
    wahl = dict(alle=alle, haupt=[haupt], seiten=[f for f in alle if f != haupt])
    def los(x):
        if isinstance(x, str): x = [x]
        out = []
        for f in x or []:
            for g in wahl.get(f, [f]):
                if g not in out: out.append(g)
        return out
    for v in cfg.get("versuche", []):
        if "fassaden" in v: v["fassaden"] = los(v["fassaden"])
        for k in ("bloecke", "relief"):
            if isinstance(v.get(k), dict) and "fassaden" in v[k]: v[k]["fassaden"] = los(v[k]["fassaden"])
    cfg["_fassaden_wahl"] = wahl
    return wahl


def v_fassade(ctx, st, cfg):
    """Fassaden-Parsing (vollautomatisch): fassade_ortho (alle kalibrierten Fotos -> Einzelfoto-Orthobilder je LoD2-Fassade, Sicht gegen das Modell der
    vorigen Stufe + LoD2-Nachbarn) -> fassade_parsing (OWLv2, Abstimmung ueber die Fotos) -> Versuche der Reihe nach (cfg['versuche']: Klassen
    zuschalten / Fassaden / Handabschnitte ersetzen, jeder Versuch = Aenderung am bisher besten Stand), je Versuch Modell bauen und gegen alle Bewertungsfotos messen; behalten nur, was GEPAART ueber die Fotos
    deutlich besser ist (t <= -2). Fortsetzbar je Versuch."""
    fest = json.loads(json.dumps(ctx["fest"])); st.setdefault("schritte", []); vorher = ctx["vorige"]
    sd = cfg.get("ortho_von_stufe", ctx["nr"])                                                         # spaetere Fassadenstufen nutzen Ortho/Parsing einer frueheren Stufe (kein OWLv2-Neulauf)
    od_ = os.path.join(ctx["aus"], f"fassade_ortho_s{sd}"); pd_ = os.path.join(ctx["aus"], f"fassade_parse_s{sd}"); el = os.path.join(pd_, "elemente.json")
    if not os.path.exists(el):
        for cmd in ([PY, "-I", os.path.join(TOOLS, "fassade_ortho.py"), ctx["objp"], "--stl", vorher["stl"], "--aus", od_, "--einzeln"],
                    [PY, "-I", os.path.join(TOOLS, "fassade_parsing.py"), "--ortho", od_, "--aus", pd_, "--gpu"]):
            print(f"    {os.path.basename(cmd[2])}  [{time.time() - ctx['t0']:.0f} s]", flush=True)
            rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, HF_HOME=os.environ.get("HF_HOME", "/media/oem/scan/hf_cache")))
            open(os.path.join(ctx["aus"], f"{os.path.basename(cmd[2])[:-3]}_s{ctx['nr']}.log"), "w").write(rr.stdout + rr.stderr)
            if rr.returncode != 0: raise SystemExit(f"{cmd[2]} fehlgeschlagen: {(rr.stderr or rr.stdout)[-600:]}")
    rj = os.path.join(ctx["aus"], f"fassade_relief_s{ctx['nr']}", "relief.json")
    if not os.path.exists(rj):                                                                        # Relief aus der dichten Wolke (fassade_relief.py), Rahmen = Fassaden aus fassade_ortho
        rr = subprocess.run([PY, "-I", os.path.join(TOOLS, "fassade_relief.py"), ctx["objp"], "--fassaden", os.path.join(od_, "fassaden.json"), "--aus", os.path.dirname(rj)], cwd=ROOT, capture_output=True, text=True)
        open(os.path.join(ctx["aus"], f"fassade_relief_s{ctx['nr']}.log"), "w").write(rr.stdout + rr.stderr)
        if rr.returncode != 0: print(f"    fassade_relief fehlgeschlagen (ohne Relief weiter): {(rr.stderr or rr.stdout)[-300:]}", flush=True)
    E = json.load(open(el)); st["erkannt"] = {fid: F["anzahl"] for fid, F in E["fassaden"].items()}; st["elemente_datei"] = el
    basis = dict(je_foto=vorher["je_foto"]); ctx["fassaden_json"] = os.path.join(od_, "fassaden.json")
    FA = json.load(open(os.path.join(od_, "fassaden.json")))["fassaden"]; k_e = int(cfg.get("entscheid_fotos", 12))
    fassaden_aufloesen(cfg, FA)
    def entscheid(v):
        """Fotos, die die geaenderten Fassaden SEHEN (2026-11-05: unter den 12 Bewertungsfotos sehen viele die Nordfront nicht -> Felder 1->3 je
        Nordfoto -0,04..-0,06, im Mittel aller 12 aber 'flach'). Je Fassade die k besten nach Zellen x Guete (fassade_ortho), vereinigt."""
        if not v.get("fassaden"): return list(ctx["fotos"])
        out = []
        for F in FA:
            if F["id"] in v["fassaden"]:
                out += [nr for nr, _ in sorted(F.get("fotos", {}).items(), key=lambda kv: -kv[1]["zellen"] * kv[1]["guete_median"])[:k_e]]
        out = sorted(set(out)); fehlt = [nr for nr in out if not os.path.exists(os.path.join(ctx["md"], f"{nr}.png"))]
        if fehlt:                                                                                     # feste Maske wie Stufe 1 (Ausgangsmodell + 3 m) fuer neue Entscheidungsfotos
            stl = bauen_fest(ctx["obj"], {}, f"_qs_{os.path.basename(os.path.dirname(ctx['objp']))}_maske2.stl", os.path.join(ctx["aus"], "elemente_maske2.json"))
            bewerten(ctx["objp"], fehlt, stl, os.path.join(ctx["aus"], "maske_lauf2"), maske_aus=ctx["md"]); os.remove(os.path.join(ROOT, stl))
        return out or list(ctx["fotos"])
    registrieren(st, vorher)                                                                       # Kosten/rot-gelb/Karten/Elementdatei der vorigen Stufe, soweit vorhanden (alte stand.json: stand_von misst nach)
    for s_ in st["schritte"]:
        if s_["uebernommen"]: fest = s_["fest"]; basis = dict(je_foto=s_["je_foto"])
    for n, v in enumerate(cfg["versuche"], 1):
        if n <= len(st["schritte"]): continue
        f_ = json.loads(json.dumps(fest)); fa = f_.get("fassade_auto") or {}                          # Versuch = AENDERUNG am bisher besten (uebernommenen) Stand
        kl = sorted(set(fa.get("klassen", [])) | set(v.get("klassen", []))); fz = sorted(set(fa.get("fassaden", [])) | (set(v.get("fassaden", [])) if v.get("klassen") else set()))
        el_ = fa["datei"] if str(fa.get("datei", "")).endswith("elemente_freiraum.json") else el            # Freiraum-Elementdatei (Tiefen gemessen) bleibt fuer spaetere Versuche
        if kl: f_["fassade_auto"] = {**fa, "anhaengen": True, "datei": el_, "klassen": kl, "fassaden": fz}
        if v.get("freiraum"):                                                                         # 2026-11-05: Sichtstrahlen gegen bestes Modell -> gemessene Elementtiefen + Durchgaenge (Klasse oeffnung),
            fc = ctx["obj"].get("freiraum") or {}; odir = os.path.dirname(ctx["objp"])                # allgemein statt Bogenregel (tools/freiraum_*.py, Gegenproben Kaufhaus + Martinstor)
            P_ = lambda x: x if os.path.isabs(x) else os.path.join(odir, x)
            fr = os.path.join(ctx["aus"], f"freiraum_s{ctx['nr']}_v{n}"); ef = os.path.join(fr, "elemente_freiraum.json")
            if not fc: print("      Freiraum: objekt.json ohne 'freiraum' (dichte Wolke) - Versuch ohne Wirkung", flush=True)
            elif not os.path.exists(ef):
                tag = f"s{ctx['nr']}_v{n}_frei"; stl = bauen_fest(ctx["obj"], f_, f"_qs_{os.path.basename(odir)}_{tag}.stl", os.path.join(ctx["aus"], f"elemente_{tag}.json")); sa = os.path.join(ROOT, stl)
                for cmd in (["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={fc.get('speicher', '6G')}", PY, "-W", "ignore", "-I", os.path.join(TOOLS, "freiraum_pruefen.py"), ctx["objp"], "--stl", sa,
                             "--dicht", P_(fc["dicht"]), "--ausrichtung", P_(fc["ausrichtung"]), "--aus", fr],
                            [PY, "-W", "ignore", "-I", os.path.join(TOOLS, "freiraum_fassaden.py"), os.path.join(fr, "strahlen.npz"), os.path.join(od_, "fassaden.json"), fr, "--stl", sa],
                            [PY, "-W", "ignore", "-I", os.path.join(TOOLS, "freiraum_oeffnungen.py"), os.path.join(fr, "freiraum_fassaden.json"), el, ef, "--fassaden", os.path.join(od_, "fassaden.json")]):
                    rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True); open(fr + ".log", "a").write(rr.stdout + rr.stderr)
                    if rr.returncode != 0: os.remove(sa); raise SystemExit(f"freiraum fehlgeschlagen: {(rr.stderr or rr.stdout)[-600:]}")
                os.remove(sa); print("      Freiraum: " + " | ".join(l.strip() for l in open(fr + ".log") if "neue oeffnung" in l or "Elemente mit gemessener" in l)[:600], flush=True)
            if fc:
                fa2 = f_.get("fassade_auto") or {}; f_["fassade_auto"] = {**fa2, "anhaengen": True, "datei": ef, "klassen": sorted(set(fa2.get("klassen", [])) | {"oeffnung"}),
                                                                          "fassaden": sorted(set(fa2.get("fassaden", [])) | {fid for fid, F_ in json.load(open(ef))["fassaden"].items()
                                                                                                                     if any(e["klasse"] == "oeffnung" for e in F_["elemente"])})}   # nur Fassaden mit neuen Durchgaengen dazu
        if v.get("relief"):                                                                           # Relief aus der Wolke (Vor-/Ruecksprunge) je Fassade
            rw = f_.get("relief_wolke") or {}; f_["relief_wolke"] = {**rw, "anhaengen": True, "datei": rj, **{k: x for k, x in v["relief"].items() if k != "fassaden"},
                                                                     "fassaden": sorted(set(rw.get("fassaden", [])) | set(v["relief"].get("fassaden", [])))}
        if v.get("bloecke"):                                                                          # Vorbauten aus Wolkenbloecken (Erker/Galerie nach Seitenverhaeltnis)
            bw = f_.get("bloecke_wolke") or {}; f_["bloecke_wolke"] = {**bw, "anhaengen": True, "datei": rj, **{k: x for k, x in v["bloecke"].items() if k != "fassaden"},
                                                                       "fassaden": sorted(set(bw.get("fassaden", [])) | set(v["bloecke"].get("fassaden", [])))}
        if v.get("vorbau_fenster"):                                                                   # Erker-/Vorbaufenster (2026-11-05): Orthos der Vorbauflaechen aus dem bisher besten Modell (fassade_ortho
            vd = os.path.join(ctx["aus"], f"vorbau_ortho_s{ctx['nr']}_v{n}"); vp = vd.replace("vorbau_ortho", "vorbau_parse"); ve = os.path.join(vp, "elemente.json")   # --waende-stl), OWLv2-Parsing,
            if not os.path.exists(ve):                                                                # Schnitte auf der Vorbauflaeche (Bauteil fassade_vorbau = fassade_auto auf diesen Ebenen)
                stl = bauen_fest(ctx["obj"], fest, f"_qs_{os.path.basename(os.path.dirname(ctx['objp']))}_vorbau.stl", os.path.join(ctx["aus"], f"elemente_vorbau_v{n}.json"))
                for cmd in ([PY, "-I", os.path.join(TOOLS, "fassade_ortho.py"), ctx["objp"], "--stl", os.path.join(ROOT, stl), "--aus", vd, "--einzeln", "--waende-stl", "--min-flaeche", str(v.get("min_flaeche", 1.0))],
                            [PY, "-I", os.path.join(TOOLS, "fassade_parsing.py"), "--ortho", vd, "--aus", vp, "--gpu"]):
                    rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, HF_HOME=os.environ.get("HF_HOME", "/media/oem/scan/hf_cache")))
                    open(vd + f"_{os.path.basename(cmd[2])[:-3]}.log", "w").write(rr.stdout + rr.stderr)
                    if rr.returncode != 0: os.remove(os.path.join(ROOT, stl)); raise SystemExit(f"{cmd[2]} fehlgeschlagen: {(rr.stderr or rr.stdout)[-600:]}")
                os.remove(os.path.join(ROOT, stl))
            f_["fassade_vorbau"] = {"anhaengen": True, "datei": ve, "klassen": v.get("klassen", ["fenster"])}
        if v.get("figuren_auto"):                                                                     # Figuren vollautomatisch: zier_ausschnitt (OWLv2-Pruefung) -> zier_3d (TripoSR) -> figuren_netz
            zd = os.path.join(ctx["aus"], f"zier_s{ctx['nr']}"); zj = os.path.join(zd, "ausschnitte.json")
            if not os.path.exists(zj) or not any(e.get("netz") for e in json.load(open(zj))["ausschnitte"]):
                for cmd in ([PY, "-I", os.path.join(TOOLS, "zier_ausschnitt.py"), ctx["objp"], "--elemente", el, "--stl", vorher["stl"], "--aus", zd, "--pruefen"],
                            [PY, "-I", os.path.join(TOOLS, "zier_3d.py"), zj]):
                    rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, HF_HOME=os.environ.get("HF_HOME", "/media/oem/scan/hf_cache")))
                    open(zd + f"_{os.path.basename(cmd[2])[:-3]}.log", "w").write(rr.stdout + rr.stderr)
                    if rr.returncode != 0: raise SystemExit(f"{cmd[2]} fehlgeschlagen: {(rr.stderr or rr.stdout)[-600:]}")
            f_["figuren_netz"] = {**(f_.get("figuren_netz") or {}), "anhaengen": True, "datei": zj, **(v["figuren_auto"] if isinstance(v["figuren_auto"], dict) else {})}
        if v.get("spitzen_messen") and f_.get("bloecke_wolke"):                                       # Erker-/Helmspitzen aus der Himmelssilhouette (spitze_hoehe.py) statt helm_m-Annahme/Kantensuche (Kanten flach 9-13 m)
            tag = f"s{ctx['nr']}_v{n}_spitzen"; el_ = os.path.join(ctx["aus"], f"elemente_{tag}.json")
            stl_ = bauen_fest(ctx["obj"], f_, f"_qs_{os.path.basename(os.path.dirname(ctx['objp']))}_{tag}.stl", el_); os.remove(os.path.join(ROOT, stl_))
            sd = os.path.join(ctx["aus"], tag); rr = subprocess.run([PY, "-I", os.path.join(TOOLS, "spitze_hoehe.py"), ctx["objp"], "--elemente", el_, "--aus", sd], cwd=ROOT, capture_output=True, text=True)
            open(sd + ".log", "w").write(rr.stdout + rr.stderr)
            if rr.returncode != 0 or not os.path.exists(os.path.join(sd, "spitze_hoehe.json")):           # Nachtlauf: Messung fehlt -> Annahme bleibt, kein Abbruch (protokolliert)
                print(f"      Spitzen NICHT gemessen (spitze_hoehe rc {rr.returncode}: {(rr.stderr or rr.stdout).strip()[-200:]}) - helm_m bleibt", flush=True); sp = []
            else: sp = [r["triangulation"] for r in json.load(open(os.path.join(sd, "spitze_hoehe.json")))["spitzen"] if (r.get("triangulation") or {}).get("n", 0) >= 4]   # nur triangulierte Spitzen (RANSAC, >= 4 Fotos); Einzelhoehen je Foto nicht (Spur auf Giebel/Kamin)
            if sp: f_["bloecke_wolke"]["spitzen_z"] = [t_["punkt"] for t_ in sp]
            print(f"      Spitzen gemessen: " + (", ".join(f"({t_['punkt'][0]:.1f},{t_['punkt'][1]:.1f}) {t_['punkt'][2]:.2f} m [{t_['n']} Fotos, RMS {t_['rms_m']:.2f}]" for t_ in sp) or "keine"), flush=True)
        for bt, bc in (v.get("bauteile") or {}).items():                                              # allgemeine Zusatzbauteile je Versuch (z. B. figuren_netz)
            f_[bt] = {**(f_.get(bt) or {}), "anhaengen": True, **bc}
        if v.get("ohne_abschnitte"): f_.setdefault("fassade_raster", {})["ohne_abschnitte"] = sorted(set((f_.get("fassade_raster") or {}).get("ohne_abschnitte", [])) | set(v["ohne_abschnitte"]))
        for b in v.get("aus", []): f_.setdefault(b, {})["aktiv"] = False
        print(f"    Versuch {n}: {v['name']} (Klassen {kl}, aus {v.get('aus', [])})  [{time.time() - ctx['t0']:.0f} s]", flush=True)
        such = []; ef = entscheid(v)
        print(f"      Entscheidungsfotos ({len(ef)}): {','.join(ef)}", flush=True)
        for j, p in enumerate(v.get("suche", []), 1):                                                 # Formparameter des Versuchs ERST gegen die Fotos suchen, dann entscheiden (2026-11-05: Fenster ohne
            sa = os.path.join(ctx["aus"], f"suche_{ctx['nr']}_v{n}_{j:02d}")                           # Felder/Pfosten verloren gegen die Handablesung - unfairer Vergleich)
            pf = os.path.join(sa, f"param_suche_fassade_auto_{p['param']}.json")
            if not os.path.exists(pf):
                cmd = [PY, "-u", "-I", os.path.join(TOOLS, "param_suche.py"), ctx["objp"], "--bauteil", "fassade_auto", "--param", p["param"], "--werte=" + p["werte"],
                       "--fotoliste", ",".join(ef), "--aus", sa, "--fest", json.dumps(f_), "--ergebnis-hier"] + (["--fein"] if p.get("fein", True) else [])
                rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True); open(sa + ".log", "w").write(rr.stdout + rr.stderr)
                if rr.returncode != 0 or not os.path.exists(pf): raise SystemExit(f"param_suche fehlgeschlagen ({p['param']}): {(rr.stderr or rr.stdout)[-600:]}")
            e = json.load(open(pf)); ok_ = e["zustand"] == "ok"
            if ok_:
                k_ = json.loads(json.dumps(f_)); k_["fassade_auto"][p["param"]] = e["bester_wert"]
                ok_, gr_s, det_s = entscheide_fest(ctx, st, f"{p['param']} = {e['bester_wert']}", k_, f_, ef, v, f"s{ctx['nr']}_v{n}_x{j}", behalten=[fest])
            if ok_: f_["fassade_auto"][p["param"]] = e["bester_wert"]
            such.append(dict(param=p["param"], werte=p["werte"], bester_wert=e["bester_wert"], zustand=e["zustand"], uebernommen=ok_))
            print(f"      Suche {p['param']}: {e['bester_wert']} ({e['zustand']}){' uebernommen' if ok_ else ''}", flush=True)
        if v.get("entscheid") == "zier":                                                             # Zierteile EINZELN entscheiden (zier_pruefen.py, Silhouetten-IoU je Element): der Fassaden-Kantenvergleich sieht sie nicht
            zp = zier_entscheid(ctx, fest, f_, v, n)
            if zp is not None:
                m_ = modell_messen(ctx["objp"], ctx["obj"], ctx["fotos"], ctx["aus"], f"s{ctx['nr']}_v{n}", f_, ctx["md"]); registrieren(st, m_)
                ueb, gr_z, det_z = entscheide_fest(ctx, st, v["name"], f_, fest, ctx["fotos"], dict(v, _zier_ok=zp["ueb"], _zier_text=f"IoU {zp['iou_neu']:.3f} vs {zp['iou_alt']:.3f} (t {zp['t']:+.1f})"), f"s{ctx['nr']}_v{n}_z", behalten=[fest])
                print(f"      -> Zierteile: IoU neu {zp['iou_neu']:.3f} / alt {zp['iou_alt']:.3f} (t {zp['t']:+.1f}, {zp['n']} Elemente): {'uebernommen' if ueb else 'verworfen'}", flush=True)
                st["schritte"].append(dict(runde=1, bauteil="zier", param=v["name"], werte="", vorher=None, bester_wert=f"IoU {zp['iou_neu']:.3f} vs {zp['iou_alt']:.3f} (t {zp['t']:+.1f})", zustand="deutlich besser" if ueb else "nicht deutlich besser",
                                           uebernommen=ueb, hinweis=v.get("hinweis", ""), suche=[], fest=f_ if ueb else json.loads(json.dumps(fest)), je_foto=m_["je_foto"], je_foto_rg=m_["je_foto_rg"], kennzahlen=m_["kennzahlen"], stl=m_["stl"], bilder=m_["bilder"], zier=zp,
                                           tor=dict(ok=ueb, gruende=gr_z, detail=tor_kurz(det_z)), **({"karten": m_["karten"], "elemente": m_["elemente"]} if ueb else {})))
                if ueb: fest, basis = f_, m_
                ctx["speichern"](); continue
        m_ = modell_messen(ctx["objp"], ctx["obj"], ctx["fotos"], ctx["aus"], f"s{ctx['nr']}_v{n}", f_, ctx["md"])
        registrieren(st, m_)
        ueb, gr_t, det_t = entscheide_fest(ctx, st, v["name"], f_, fest, ef, v, f"s{ctx['nr']}_v{n}_t", behalten=[fest])       # Uebernahmetor S1b auf den Fotos, die die Fassade sehen (kein 't < 2' mehr)
        b_ = det_t.get("b") or {}; dm, t = b_.get("dm", 0.0), b_.get("t", 0.0)
        print(f"      -> Kosten {m_['kennzahlen']['kosten']}, Tor (b) {b_.get('art')}: {dm:+.4f} (t {t:+.1f}): {'uebernommen' if ueb else 'verworfen'}", flush=True)
        st["schritte"].append(dict(runde=1, bauteil="fassade_auto", param=v["name"], werte="", vorher=None, bester_wert=f"{dm:+.4f} (t {t:+.1f})", zustand="Tor bestanden" if ueb else "Tor nicht bestanden: " + "; ".join(gr_t)[:200],
                                   uebernommen=ueb, hinweis=v.get("hinweis", ""), suche=such, fest=f_ if ueb else json.loads(json.dumps(fest)), je_foto=m_["je_foto"], je_foto_rg=m_["je_foto_rg"],
                                   kennzahlen=m_["kennzahlen"], stl=m_["stl"], bilder=m_["bilder"], tor=dict(ok=ueb, gruende=gr_t, detail=tor_kurz(det_t)), **({"karten": m_["karten"], "elemente": m_["elemente"]} if ueb else {})))
        if ueb: karten_loeschen(st, fest); fest, basis = f_, m_                                       # der bisher beste Stand gibt seine Karten frei, der neue behaelt sie
        ctx["speichern"]()
    best = [s_ for s_ in st["schritte"] if s_["uebernommen"]]
    if best: st.update(fest=best[-1]["fest"], kennzahlen=best[-1]["kennzahlen"], stl=best[-1]["stl"], je_foto=best[-1]["je_foto"], bilder=best[-1]["bilder"], **{k: best[-1][k] for k in ("je_foto_rg", "karten", "elemente") if best[-1].get(k)})
    else: st.update(fest=fest, kennzahlen=vorher["kennzahlen"], stl=vorher["stl"], je_foto=vorher["je_foto"], bilder=vorher["bilder"], **{k: vorher[k] for k in ("je_foto_rg", "karten", "elemente") if vorher.get(k)})


def zier_entscheid(ctx, fest, f_, v, n):
    """Silhouetten-IoU je Zierelement (zier_pruefen.py): Modell ohne Zierteile, mit bisherigem Stand, mit Versuch. Uebernommen, wenn gepaart ueber die
    Elemente (1 - IoU) deutlich kleiner (t <= -2). Ausschnitte aus figuren_netz.datei des Versuchs. None, wenn keine Ausschnitte."""
    zj = (f_.get("figuren_netz") or {}).get("datei")
    if not zj or not os.path.exists(zj): return None
    ohne = json.loads(json.dumps(f_)); ohne.pop("figuren_netz", None); fa = ohne.get("fassade_auto")
    if fa: fa["klassen"] = [k for k in fa.get("klassen", []) if k != "figur"]
    tag = f"s{ctx['nr']}_v{n}_zier"; d = os.path.join(ctx["aus"], tag); os.makedirs(d, exist_ok=True); stl = {}
    for name, fe in (("ohne", ohne), ("alt", fest), ("neu", f_)):
        p = bauen_fest(ctx["obj"], fe, f"_qs_{os.path.basename(os.path.dirname(ctx['objp']))}_{tag}_{name}.stl", os.path.join(d, f"elemente_{name}.json"))
        stl[name] = os.path.join(d, f"{name}.stl"); shutil.move(os.path.join(ROOT, p), stl[name])   # 5.11. 14:07: os.replace scheiterte Repo-Platte -> Datenplatte (Errno 18)
    rr = subprocess.run([PY, "-I", os.path.join(TOOLS, "zier_pruefen.py"), ctx["objp"], zj, "--ohne", stl["ohne"], "--stl", "alt=" + stl["alt"], "--stl", "neu=" + stl["neu"], "--aus", d], cwd=ROOT, capture_output=True, text=True)
    open(d + ".log", "w").write(rr.stdout + rr.stderr)
    if rr.returncode != 0: raise SystemExit("zier_pruefen fehlgeschlagen: " + (rr.stderr or rr.stdout)[-500:])
    E = json.load(open(os.path.join(d, "zier_pruefung.json")))["ergebnisse"]
    a_ = np.array([e["alt"]["iou"] for e in E]); b_ = np.array([e["neu"]["iou"] for e in E]); dd = (1 - b_) - (1 - a_)
    se = dd.std(ddof=1) / np.sqrt(len(dd)) if len(dd) > 1 else 0.0; t = float(dd.mean() / se) if se > 0 else (-99.0 if dd.mean() < 0 else 0.0)
    return dict(iou_alt=float(a_.mean()), iou_neu=float(b_.mean()), t=round(t, 2), n=len(E), ueb=bool(dd.mean() < 0 and t <= -2.0), ordner=d)


def v_gemeinsam(ctx, st, cfg):
    """ALLE Parameter gemeinsam (CMA-ES, pycma BSD-3; Recherche 2026-11-05: koordinatenweise Suche findet gekoppelte Optima nicht, z. B. First <-> Giebelkappe).
    Kosten = Mittel kosten_param ueber die Bewertungsfotos (feste Maske, gerastert -> deterministisch). Je Generation: alle Kandidaten PARALLEL bauen
    (CPU), dann alle (Kandidat x Foto) in EINEM GPU-Pool messen. Parameter normiert auf [0,1] (Grenzen aus cfg), Start = bisheriger Wert.
    Uebernahme nur, wenn das Endmodell GEPAART ueber die Fotos deutlich besser ist als die vorige Stufe (t <= -2); je Parameter wird die Aenderung
    und die CMA-Streuung berichtet (Regel 6). Fortsetzbar je Generation (st['generationen'])."""
    import cma, tempfile
    fest0 = json.loads(json.dumps(ctx["fest"])); vorher = ctx["vorige"]; P_ = [p for p in cfg["parameter"] if (p.get("nur_wenn") is None or p["nur_wenn"] in fest0)]
    lo = np.array([p["min"] for p in P_], float); hi = np.array([p["max"] for p in P_], float)
    def wert(p):
        v = (fest0.get(p["bauteil"]) or {}).get(p["param"])
        if v is None: v = next((b.get(p["param"]) for b in ctx["obj"].get("bauteile", []) if b["typ"] == p["bauteil"]), None)
        return float(p.get("start", 0.5 * (p["min"] + p["max"])) if v is None else v)
    x0 = np.clip((np.array([wert(p) for p in P_]) - lo) / (hi - lo), 0, 1)
    def fest_von(xn):
        f_ = json.loads(json.dumps(fest0)); x = lo + np.clip(xn, 0, 1) * (hi - lo)
        for p, v in zip(P_, x): f_.setdefault(p["bauteil"], {})[p["param"]] = round(float(v), 3); f_[p["bauteil"]].setdefault("quelle", f"qualitaetsstufen Stufe {ctx['nr']} CMA-ES (gemeinsam)")   # Regel 3b: Generator verlangt quelle
        return f_
    tmp = os.path.join(ctx["aus"], f"gemeinsam_s{ctx['nr']}"); os.makedirs(tmp, exist_ok=True); od = os.path.basename(os.path.dirname(ctx["objp"]))
    def messen_viele(xs, gen):
        names = [f"_qs_{od}_g{gen}_{i}.stl" for i in range(len(xs))]
        with ThreadPoolExecutor(min(len(xs), os.cpu_count() or 4)) as ex:                                      # bauen: CPU, alle Kandidaten gleichzeitig
            stls = list(ex.map(lambda a: bauen_fest(ctx["obj"], fest_von(a[1]), a[0], os.path.join(tmp, a[0] + ".elem.json")), zip(names, xs)))
        auf = [(i, nr) for i in range(len(xs)) for nr in ctx["fotos"]]
        def eins(t):
            i, nr = t; a = os.path.join(tmp, f"g{gen}_{i}", nr); os.makedirs(a, exist_ok=True)
            r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "foto_diff.py"), ctx["objp"], nr, "--stl", stls[i], "--aus", a, "--bewertung-maske", os.path.join(ctx["md"], f"{nr}.png")],
                               cwd=ROOT, env=dict(os.environ, FD_GPU="1"), capture_output=True, text=True)
            try: return t, json.load(open(os.path.join(a, f"foto_diff_{nr}.json"))).get("kosten_param")
            except Exception: return t, None
        with ThreadPoolExecutor(PS.arbeiter_zahl(len(auf))) as ex: res = dict(ex.map(eins, auf))   # messen: GPU-Pool ueber alle Kandidaten
        for t in [t for t, v in res.items() if v is None]: res[t] = eins(t)[1]
        for s_ in stls: os.remove(os.path.join(ROOT, s_))
        for i in range(len(xs)): shutil.rmtree(os.path.join(tmp, f"g{gen}_{i}"), ignore_errors=True)
        je = [{nr: res[(i, nr)] for nr in ctx["fotos"]} for i in range(len(xs))]
        return [float(np.mean([v for v in j.values() if v is not None])) if any(v is not None for v in j.values()) else 9.0 for j in je], je
    gens = st.setdefault("generationen", []); sig = float(cfg.get("sigma", 0.25)); pop = int(cfg.get("popsize", 0)) or None
    es = cma.CMAEvolutionStrategy(x0.tolist(), sig, dict(bounds=[0, 1], seed=int(cfg.get("saat", 1)), verbose=-9, **({"popsize": pop} if pop else {})))
    for g in gens: es.ask(); es.tell([np.array(x) for x in g["x"]], g["f"])                          # Fortsetzen: gespeicherte Generationen nachspielen (gleiche Saat -> gleiche Folge)
    beste = min(((f, x) for g in gens for f, x in zip(g["f"], g["x"])), default=(9.0, x0.tolist()))
    while len(gens) < int(cfg.get("generationen", 12)) and not es.stop():
        xs = es.ask(); f, _ = messen_viele(xs, len(gens)); es.tell(xs, f)
        gens.append(dict(x=[list(map(float, x)) for x in xs], f=f)); i_ = int(np.argmin(f))
        if f[i_] < beste[0]: beste = (f[i_], list(map(float, xs[i_])))
        print(f"    Generation {len(gens)}: bestes {min(f):.4f}, Mittel {np.mean(f):.4f}, bisher bestes {beste[0]:.4f}  [{time.time() - ctx['t0']:.0f} s]", flush=True); ctx["speichern"]()
    xm = np.array(es.result.xfavorite); sd = es.result.stds
    kand = [("bestes", np.array(beste[1])), ("Mittelpunkt", xm)]
    erg = []
    for name, x in kand:                                                                              # beide Kandidaten voll messen und GEPAART gegen die vorige Stufe pruefen
        m_ = modell_messen(ctx["objp"], ctx["obj"], ctx["fotos"], ctx["aus"], f"s{ctx['nr']}_{'b' if name == 'bestes' else 'm'}", fest_von(x), ctx["md"])
        dm, t, nn = gepaart(m_["je_foto"], vorher["je_foto"]); erg.append((name, x, m_, dm, t))
        print(f"    {name}: Kosten {m_['kennzahlen']['kosten']}, gepaart {dm:+.4f} (t {t:+.1f})", flush=True)
    name, x, m_, dm, t = min(erg, key=lambda e: e[2]["kennzahlen"]["kosten"]); registrieren(st, vorher)
    for e_ in erg: registrieren(st, e_[2])
    ueb, gr_g, det_g = entscheide_fest(ctx, st, f"CMA {name}", fest_von(x), fest0, ctx["fotos"], cfg, f"s{ctx['nr']}_cma", behalten=[fest0])
    for e_ in erg:
        if e_[0] != name: karten_loeschen(st, e_[2]["fest"], behalten=[fest_von(x), fest0])
    xa = lo + x0 * (hi - lo); xb = lo + np.clip(x, 0, 1) * (hi - lo); s_m = np.array(sd) * (hi - lo)
    st["schritte"] = [dict(runde=1, bauteil=p["bauteil"], param=p["param"], werte=f"{p['min']}:{p['max']}", vorher=round(float(a), 3), bester_wert=round(float(b), 3),
                           zustand=f"CMA-Streuung +-{s_:.2f}", uebernommen=ueb, hinweis=p.get("hinweis", "")) for p, a, b, s_ in zip(P_, xa, xb, s_m)]
    st["ergebnis"] = dict(kandidat=name, gepaart=round(dm, 4), t=round(t, 2), auswertungen=sum(len(g["f"]) for g in gens), uebernommen=ueb, tor=dict(ok=ueb, gruende=gr_g, detail=tor_kurz(det_g)))
    print(f"    -> {name}: gepaart {dm:+.4f} je Foto (t {t:+.1f}): {'uebernommen' if ueb else 'verworfen'}", flush=True)
    if ueb: st.update(fest=fest_von(x), kennzahlen=m_["kennzahlen"], stl=m_["stl"], je_foto=m_["je_foto"], bilder=m_["bilder"], je_foto_rg=m_["je_foto_rg"], karten=m_["karten"], elemente=m_["elemente"])
    else: st.update(fest=fest0, kennzahlen=vorher["kennzahlen"], stl=vorher["stl"], je_foto=vorher["je_foto"], bilder=vorher["bilder"], **{k: vorher[k] for k in ("je_foto_rg", "karten", "elemente") if vorher.get(k)})


# ------------------------------------------------------------------ S3: Konvergenzschleife (SPEC_S3_KONVERGENZ)
def alle_fotos(ctx):
    """ALLE kalibrierten Fotos (param_suche.fotos_waehlen(od, None)), fehlende Bewertungsmasken mit dem Ausgangsmodell nachgezogen (wie main); Fotos ohne Maske (Modell nicht im Bild) fallen weg."""
    od = os.path.dirname(ctx["objp"]); fotos = PS.fotos_waehlen(od, None, ohne_nacht=bool((ctx.get("plan") or {}).get("ohne_nacht")))
    fehlt = [nr for nr in fotos if not os.path.exists(os.path.join(ctx["md"], f"{nr}.png"))]
    if fehlt:
        stl = bauen_fest(ctx["obj"], {}, f"_qs_{os.path.basename(od)}_maske_alle.stl", os.path.join(ctx["aus"], "elemente_maske_alle.json"))
        try: bewerten(ctx["objp"], fehlt, stl, os.path.join(ctx["aus"], "maske_lauf_alle"), maske_aus=ctx["md"])
        finally: os.remove(os.path.join(ROOT, stl))
    return [nr for nr in fotos if os.path.exists(os.path.join(ctx["md"], f"{nr}.png"))]


def ziel_erreicht(res, cfg):
    """Abbruch (i): je Flaeche mit >= ziel_min_kameras sehenden Fotos je Zelle (Median) im Mittel gelb < ziel_gelb UND rot < ziel_rot (Plan Abschnitt 1). -> (ok, {fid: (gelb, rot)})"""
    fl = {fid: v for fid, v in res["F_je_flaeche"].items() if v["zellen_sicht"] and v["fotos_je_zelle_median"] >= cfg["ziel_min_kameras"]}
    return bool(fl) and all(v["gelb_mittel"] < cfg["ziel_gelb"] and v["rot_mittel"] < cfg["ziel_rot"] for v in fl.values()), {fid: (v["gelb_mittel"], v["rot_mittel"]) for fid, v in fl.items()}


def abbruch_grund(hist, ziel_ok, n_angenommen, minuten_verbraucht, cfg, schw):
    """Reihenfolge (i) Grenzwert, (ii) nichts angenommen, (iii) F fiel um < abbruch_f_rel, (iv) Zeitbudget. hist = [F_0, F_1, ...] (Lauf k beginnt bei F_k, endet bei F_{k+1}). Nur (i) heisst 'konvergiert'."""
    if ziel_ok: return "(i) Grenzwert erreicht (konvergiert)", True
    if n_angenommen == 0: return "(ii) kein Kandidat angenommen", False
    if len(hist) >= 2 and hist[-2] > 0 and (hist[-2] - hist[-1]) / hist[-2] < schw["abbruch_f_rel"]: return f"(iii) F fiel um {100 * (hist[-2] - hist[-1]) / hist[-2]:.2f} % (< {100 * schw['abbruch_f_rel']:.0f} %)", False
    if minuten_verbraucht >= cfg["minuten"]: return f"(iv) Zeitbudget {cfg['minuten']} min erreicht", False
    return None, False


def _buchstaben(gr): return sorted(set(re.findall(r"\(([a-f])\)", " ".join(gr))))


def _fassaden_json(ctx):
    import glob as _g
    return ctx.get("fassaden_json") or sorted(_g.glob(os.path.join(ctx["aus"], "fassade_ortho_s*", "fassaden.json")))[-1]


def _fehlerkarte(ctx, st, fest, fotos, k, tag, schw):
    """Stand messen (alle Fotos, gecacht) -> Restfeld mit Dach -> Fehlerkarte k. Rueckgabe (stand, res)."""
    stand = stand_von(ctx, st, fest, fotos, tag); fj = _fassaden_json(ctx); rd = restfeld_messen(ctx, dict(fest=fest, stl=None), fj, dach=True); od = os.path.basename(os.path.dirname(ctx["objp"]))
    stl = os.path.join(ROOT, bauen_fest(ctx["obj"], fest, f"_qs_{od}_fk{k}.stl", os.path.join(ctx["aus"], f"elemente_fk{k}.json")))
    try: res = FKM.rechnen(ctx["objp"], ctx["obj"], stand["karten"], rd, os.path.join(ctx["aus"], f"konvergenz_s{ctx['nr']}"), k, schw, stl, stand["elemente"], ctx["md"], None, fotos)
    finally: os.remove(stl)
    return stand, res


def _param_fest(ctx, fest, p, fotos, tag):
    """param_suche eines Kandidaten-Parameters auf den sehenden Fotos (wie v_parameter) -> (fest', ergebnis) oder (None, ergebnis)."""
    sa = os.path.join(ctx["aus"], f"suche_{tag}")
    cmd = [PY, "-u", "-I", os.path.join(TOOLS, "param_suche.py"), ctx["objp"], "--bauteil", p["bauteil"], "--param", p["param"], "--werte=" + p["werte"], "--fein", "--fotoliste", ",".join(fotos), "--aus", sa, "--fest", json.dumps(fest), "--ergebnis-hier"]
    rr = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True); open(sa + ".log", "w").write(rr.stdout + rr.stderr); pf = os.path.join(sa, f"param_suche_{p['bauteil']}_{p['param']}.json")
    if rr.returncode != 0 or not os.path.exists(pf): return None, dict(zustand="param_suche fehlgeschlagen")
    e = json.load(open(pf))
    if e["zustand"] != "ok": return None, e
    f2 = json.loads(json.dumps(fest)); f2.setdefault(p["bauteil"], {}).update({p["param"]: e["bester_wert"], "quelle": f"qualitaetsstufen Stufe {ctx['nr']} Konvergenz {tag}: param_suche {len(fotos)} sehende Fotos"}); return f2, e


def _feinlage_rang(ctx, st, fest, kand, schw, kctx):
    """Elementbuch-Vorabcheck: die Varianten messen (sehende Fotos) und nach der mittleren lokalen Summe rot+gelb der geaenderten Elemente ordnen; die besten `behalten` bleiben."""
    alt = stand_von(ctx, st, fest, kand["fotos"], f"s{ctx['nr']}_fl{kand['cluster']}_a"); wert = []
    for i, v in enumerate(kand["varianten"]):
        f2, info = KAND.anwenden(dict(kand, variante=v), fest, kctx, schw)
        if f2 is None: continue
        neu = stand_von(ctx, st, f2, kand["fotos"], f"s{ctx['nr']}_fl{kand['cluster']}_v{i}"); d = EB.vergleichen(alt, neu, kand["fotos"], _kam(ctx)); w = []
        for kk, e in d["elemente"].items():
            if e["art"] in ("geaendert", "neu"): w += [f["summe"][1] for f in e["fotos"].values() if "summe" in f]
        wert.append((float(np.mean(w)) if w else 9.0, i, f2))
        karten_loeschen(st, f2, behalten=[fest])
    wert.sort(key=lambda t: (t[0], t[1])); return [(i, f2, w) for w, i, f2 in wert[:kand["behalten"]]]


def v_konvergenz(ctx, st, cfg):
    """Stufe 4 Konvergenzschleife (SPEC_S3_KONVERGENZ): je Lauf Fehlerkarte (fehlerkarte.py, alle kalibrierten Fotos, Dach ohne Wolke) -> Kandidaten (kandidaten.py) -> je Kandidat
    bauen, auf den sehenden Fotos messen, uebernahme_tor (a-f) -> greedy sequentiell neuer Stand. Abbruch (i) Grenzwert (nur das heisst konvergiert), (ii) nichts angenommen,
    (iii) F um < abbruch_f_rel, (iv) Zeitbudget. Kennzahl F = sum (gelb+rot) x zelle^2 ueber Zellen mit >= min_fotos Fotos (lokal, monoton gewollt). Fortsetzbar: st['laeufe']."""
    schw = FKM.schwellen_laden({"konvergenz": cfg.get("konvergenz")}); fest = json.loads(json.dumps(ctx["fest"])); st.setdefault("laeufe", []); st.setdefault("schritte", []); nr = ctx["nr"]
    if ctx.get("vorige"): registrieren(st, ctx["vorige"])
    fotos = alle_fotos(ctx); t_start = time.time() - 60.0 * float(st.get("minuten_vorher", 0.0)); grund = st.get("abbruch"); konv = bool(st.get("konvergiert"))
    for l in st["laeufe"]:
        if l.get("fest_ende"): fest = l["fest_ende"]
    print(f"    Konvergenz: {len(fotos)} Fotos, Schwellen {json.dumps({k_: schw[k_] for k_ in ('zelle_m', 'min_fotos', 'stimmen', 'min_flaeche_m2', 'rest_tol_m')})}", flush=True)
    k = len(st["laeufe"]) - 1 if (st["laeufe"] and not st["laeufe"][-1].get("fertig")) else len(st["laeufe"])
    while k < int(cfg["laeufe"]) and not grund:
        lauf = st["laeufe"][k] if k < len(st["laeufe"]) else None
        if lauf is None: lauf = dict(k=k, fest_start=json.loads(json.dumps(fest)), erledigt=[], kandidaten=[], fertig=False); st["laeufe"].append(lauf)
        fest = json.loads(json.dumps(lauf.get("fest_aktuell") or lauf["fest_start"])); print(f"    Lauf {k}: Fehlerkarte  [{time.time() - ctx['t0']:.0f} s]", flush=True)
        rr = subprocess.run([PY, "-I", os.path.join(TOOLS, "platz_pruefen.py")], capture_output=True, text=True); open(os.path.join(ctx["aus"], "platz_pruefen.log"), "a").write(rr.stdout + rr.stderr)        # Platzpruefung vor jedem Lauf (G1)
        if rr.returncode == 3: raise SystemExit("Platzpruefung vor dem Konvergenzlauf: " + (rr.stdout + rr.stderr)[-300:])
        stand0, res = _fehlerkarte(ctx, st, lauf["fest_start"], fotos, k, f"s{nr}_k{k}_a", schw)
        lauf["F_start"] = res["F"]; lauf["F_je_flaeche_start"] = {f: v["F"] for f, v in res["F_je_flaeche"].items()}; ok0, _ = ziel_erreicht(res, cfg)
        if ok0:                                                                                       # (i) schon vor dem Lauf erreicht
            lauf.update(fertig=True, fest_ende=lauf["fest_start"], F_ende=res["F"], angenommen=0, abbruch="(i) Grenzwert erreicht (konvergiert)"); grund, konv = lauf["abbruch"], True; ctx["speichern"](); break
        fj = _fassaden_json(ctx); fa = json.load(open(fj))["fassaden"]; import glob as _g
        ep = sorted(_g.glob(os.path.join(ctx["aus"], "fassade_parse_s*", "elemente.json")))[-1]; kdir = os.path.join(ctx["aus"], f"konvergenz_s{nr}", f"kandidaten_k{k}"); stand_el = {}
        for kk, g in EB.elemente_laden(stand0["elemente"])[0].items():                                 # Elementdatei des Baus: u in Generatorrichtung -> in die Richtung der Flaeche drehen (wie fehlerkarte.rechnen)
            F_ = next((f for f in fa if f["id"] == g["fassade"]), None); sg = -1.0 if (F_ is not None and float(np.dot(g["rahmen"]["d"][:2], F_["d"][:2])) < 0) else 1.0
            stand_el.setdefault(g["fassade"], []).append((kk, dict(g, u0=min(sg * g["u0"], sg * g["u1"]), u1=max(sg * g["u0"], sg * g["u1"]))))
        K = KAND.kandidaten_aus_clustern(res, schw, ctx.get("plan"), os.path.join(ctx["aus"], f"konvergenz_s{nr}", f"fehlerkarte_k{k}"), os.path.dirname(fj), fa, stand_el, kdir)
        json.dump(K, open(os.path.join(kdir, "kandidaten.json"), "w"), indent=1, ensure_ascii=False)
        kands = [c for c in K["kandidaten"] if c.get("anwendbar") is not False and c["art"] != "textur"][:int(cfg["max_kandidaten_je_lauf"])]
        lauf["n_cluster"] = len(res["cluster"]); lauf["n_kandidaten"] = len(K["kandidaten"]); lauf["protokoll"] = K["protokoll"]
        kctx = dict(aus=kdir, fassaden=fa, elemente_parse=ep); n_ang = sum(1 for c in lauf["kandidaten"] if c.get("angenommen"))
        print(f"      F = {res['F']} m2, {len(res['cluster'])} Cluster, {len(K['kandidaten'])} Kandidaten, davon {len(kands)} im Lauf", flush=True)
        for kand in kands:
            cid = f"{kand['cluster']}:{kand['art']}:{kand['id']}"
            if cid in lauf["erledigt"]: continue
            if (time.time() - t_start) / 60.0 >= float(cfg["minuten"]): break
            tag = f"s{nr}_k{k}_c{kand['cluster']}_{kand['art'][:3]}{kand['id']}"; rec = dict(id=cid, cluster=kand["cluster"], art=kand["art"], klasse=kand.get("klasse"), fid=kand["fid"], box=kand["box"], beleg=kand["beleg"], fotos=kand["fotos"], angenommen=False)
            cf = dict(cfg, **({"dach_f": bool(kand.get("f_ok")), "dach_f_quellen": kand.get("f_bestaetigt_durch", [])} if kand.get("dach") else {})); fsts = []   # Kandidatenstaende (fest', Bezeichnung)
            if kand["art"] == "parameter":
                for p in kand["kandidaten_parameter"]:
                    f2, e = _param_fest(ctx, fest, p, kand["fotos"], tag + "_" + p["param"])
                    if f2 is not None: fsts.append((f2, f"{p['bauteil']}.{p['param']} = {e['bester_wert']}"))
                    else: rec.setdefault("parameter_flach", []).append(f"{p['param']}: {e.get('zustand')}")
            elif kand["art"] == "feinlage":
                for i, f2, w in _feinlage_rang(ctx, st, fest, kand, schw, kctx): fsts.append((f2, f"Feinlage Variante {i} (lokal {w:.3f})"))
            else:
                f2, info = KAND.anwenden(kand, fest, kctx, schw)
                if f2 is None: rec["zustand"] = f"nicht anwendbar: {info}"
                else: fsts.append((f2, kand["art"]))
            for f2, bez in fsts:
                ok, gr, det = entscheide_fest(ctx, st, f"{bez} ({kand['beleg'][:60]})", f2, fest, kand["fotos"], cf, tag, behalten=[fest])
                rec.setdefault("versuche", []).append(dict(bezeichnung=bez, ok=ok, buchstaben=_buchstaben(gr), gruende=gr, tor=tor_kurz(det)))
                if ok: fest = f2; rec["angenommen"] = True; rec["zustand"] = f"angenommen: {bez}"; n_ang += 1; break              # greedy: der erste bestandene Kandidat des Clusters
            if not rec["angenommen"] and "zustand" not in rec:
                rec["zustand"] = ("abgelehnt: " + ",".join(sorted({b for v in rec["versuche"] for b in v["buchstaben"]}))) if rec.get("versuche") else "keine Kandidatenstaende (Suche flach/nicht anwendbar)"
            print(f"      Cluster {kand['cluster']} {kand['art']} {kand['fid']}: {rec['zustand']}", flush=True)
            lauf["kandidaten"].append(rec); lauf["erledigt"].append(cid); lauf["fest_aktuell"] = json.loads(json.dumps(fest))
            st["schritte"].append(dict(runde=k + 1, bauteil=kand["fid"], param=f"{kand['art']} Cluster {kand['cluster']}", werte="", vorher=None, bester_wert=rec["zustand"][:60], zustand=rec["zustand"][:30], uebernommen=rec["angenommen"], hinweis=kand["beleg"], fest=json.loads(json.dumps(fest))))
            st["minuten_vorher"] = round((time.time() - t_start) / 60.0, 2); ctx["speichern"]()
        lauf["fest_ende"] = json.loads(json.dumps(fest)); lauf["angenommen"] = n_ang
        stand1, res1 = _fehlerkarte(ctx, st, fest, fotos, k + 1, f"s{nr}_k{k}_e", schw)                  # F_{k+1}: Karte des neuen Stands
        lauf["F_ende"] = res1["F"]; lauf["F_je_flaeche_ende"] = {f: v["F"] for f, v in res1["F_je_flaeche"].items()}; ok1, zw1 = ziel_erreicht(res1, cfg); lauf["ziel"] = dict(ok=ok1, je_flaeche=zw1)
        try: lauf["bilder"] = cluster_bilder(ctx, res, stand0, stand1, k)
        except Exception as ex: lauf["bilder"] = f"Bilderfehler: {type(ex).__name__}: {ex}"
        hist = [l["F_start"] for l in st["laeufe"][:1]] + [l["F_ende"] for l in st["laeufe"] if l.get("F_ende") is not None]
        grund, konv = abbruch_grund(hist, ok1, n_ang, (time.time() - t_start) / 60.0, cfg, schw); lauf["fertig"] = True; lauf["abbruch"] = grund
        bericht_schreiben(ctx, st, lauf, res, res1, K); ctx["speichern"]()
        print(f"      Lauf {k} fertig: F {res['F']} -> {res1['F']} m2, {n_ang} angenommen" + (f"; Abbruch {grund}" if grund else ""), flush=True)
        k += 1
    if not grund: grund = f"(v) Laufzahl {cfg['laeufe']} erreicht (nicht konvergiert)"
    st["abbruch"] = grund; st["konvergiert"] = bool(konv); st["F_verlauf"] = [l["F_start"] for l in st["laeufe"][:1]] + [l["F_ende"] for l in st["laeufe"] if l.get("F_ende") is not None]
    print(f"    Konvergenz beendet: {grund}; F-Verlauf {st['F_verlauf']}", flush=True)
    st.update(modell_messen(ctx["objp"], ctx["obj"], ctx["fotos"], ctx["aus"], f"s{nr}", fest, ctx["md"]))


def cluster_bilder(ctx, res, stand_a, stand_b, k):
    """Bild vorher/nachher fuer die 3 groessten Cluster: foto_diff-Overlay des ersten sehenden Fotos, Ausschnitt um die projizierte Clusterbox (Stand k links, Stand k+1 rechts)."""
    out = []; R = json.load(open(os.path.join(res["restfeld"], "restfeld.json")))["fassaden"]; od = os.path.join(ctx["aus"], f"konvergenz_s{ctx['nr']}", f"bilder_k{k}"); os.makedirs(od, exist_ok=True)
    for c in res["cluster"][:3]:
        if not c["fotos"]: continue
        nr_ = c["fotos"][0]; pa, pb = stand_a["karten"].get(nr_), stand_b["karten"].get(nr_)
        if not pa or not pb: continue
        ia, ib = (cv2.imread(os.path.join(os.path.dirname(p), f"foto_diff_{nr_}.jpg")) for p in (pa, pb))
        if ia is None or ib is None: continue
        F = R[c["fid"]]; o, dd, e = (np.array(F[x], float) for x in ("o", "dd", "e")); oz = o[2] if e[2] > 0.999 else 0.0
        P = np.array([o + u * dd + (z - oz) * e for u in (c["u0"], c["u1"]) for z in (c["z0"], c["z1"])]); H, W = ia.shape[:2]; xy, _ = FKM.projizieren(P, _kam(ctx).holen(nr_, W, H)); rand = 60
        x0, y0, x1, y1 = (max(0, int(np.nanmin(xy[:, 0])) - rand), max(0, int(np.nanmin(xy[:, 1])) - rand), min(W, int(np.nanmax(xy[:, 0])) + rand), min(H, int(np.nanmax(xy[:, 1])) + rand))
        if x1 - x0 < 10 or y1 - y0 < 10: continue
        a_, b_ = ia[y0:y1, x0:x1].copy(), cv2.resize(ib[y0:y1, x0:x1], (x1 - x0, y1 - y0))
        for im_, t_x in ((a_, f"Lauf {k} vorher, Foto {nr_}"), (b_, f"Lauf {k} nachher")): cv2.putText(im_, t_x, (4, 16), 0, 0.5, (255, 255, 255), 1)
        pf = os.path.join(od, f"cluster{c['id']:03d}_{c['fid']}_{c['art']}.jpg"); cv2.imwrite(pf, cv2.hconcat([a_, b_]), [cv2.IMWRITE_JPEG_QUALITY, 85]); out.append(pf)
    return out


def bericht_schreiben(ctx, st, lauf, res, res1, K):
    """Bericht je Lauf (Markdown im Laufordner): Tabelle Cluster -> Kandidat -> Ergebnis (Buchstaben), F je Flaeche."""
    d = os.path.join(ctx["aus"], f"konvergenz_s{ctx['nr']}"); os.makedirs(d, exist_ok=True); L = [f"# Konvergenz Lauf {lauf['k']}", "", f"F gesamt {lauf['F_start']} -> {lauf['F_ende']} m2; Abbruch: {lauf.get('abbruch')}", "", "| Flaeche | F vorher | F nachher |", "|---|---|---|"]
    for f, v in res["F_je_flaeche"].items():
        if v["zellen_sicht"]: L.append(f"| {f} | {v['F']} | {res1['F_je_flaeche'].get(f, {}).get('F')} |")
    L += ["", "| Cluster | Art | Flaeche | Kandidat | Ergebnis | Buchstaben |", "|---|---|---|---|---|---|"]
    for r in lauf["kandidaten"]:
        L.append(f"| {r['cluster']} ({r['fid']}) | {r['art']} | {r['box']['u1'] - r['box']['u0']:.1f} x {r['box']['z1'] - r['box']['z0']:.1f} m | {r.get('klasse') or ''} | {r['zustand'][:60]} | {','.join(sorted({b for v in r.get('versuche', []) for b in v['buchstaben']}))} |")
    if K["protokoll"]: L += ["", "Protokoll (kein Kandidat): " + "; ".join(f"Cluster {p['cluster']} {p['art']}" for p in K["protokoll"])]
    open(os.path.join(d, f"bericht_k{lauf['k']}.md"), "w").write("\n".join(L) + "\n")


VERFAHREN = {"ausgang": v_ausgang, "parameter": v_parameter, "fassade": v_fassade, "konvergenz": v_konvergenz, "gemeinsam": v_gemeinsam}


# ------------------------------------------------------------------ HTML
def html_schreiben(aus, objname, stand, fotos):
    st = [s for s in stand["stufen"] if s.get("kennzahlen")]; k0 = st[0]["kennzahlen"]["kosten"] if st else None
    laufend = [s for s in stand["stufen"] if not s.get("kennzahlen")]
    def stl64(p):
        try: return base64.b64encode(open(p, "rb").read()).decode()
        except Exception: return ""
    def kopf(i, s):
        k = s["kennzahlen"]; d = ""
        if i and k0 and k["kosten"] is not None: d = f' <span class="d {"gut" if k["kosten"] < k0 else "schlecht"}">{100 * (k["kosten"] - k0) / k0:+.1f} % gegen Stufe 1</span>'
        sch = ""
        if s.get("schritte"):
            sch = "<details><summary>" + f"{len(s['schritte'])} Schritte, {sum(x['uebernommen'] for x in s['schritte'])} uebernommen" + "</summary><table class='sch'>"
            for x in s["schritte"]:
                sch += (f"<tr><td>R{x['runde']}</td><td>{html.escape(x['bauteil'])}.{html.escape(x['param'])}</td><td>{'' if x['vorher'] is None else x['vorher']} &rarr; <b>{x['bester_wert']}</b></td>"
                        f"<td class='{'ok' if x['uebernommen'] else 'flach'}'>{'uebernommen' if x['uebernommen'] else html.escape(str(x['zustand'])[:30])}</td></tr>"
                        + (f"<tr><td></td><td colspan=3 class='hin'>{html.escape(x['hinweis'])}</td></tr>" if x.get("hinweis") else ""))
            sch += "</table></details>"
        return (f'<th><div class="nr">Stufe {i + 1}: {html.escape(s["name"])}</div><div class="v">Verfahren: {html.escape(s["verfahren"])}</div>'
                f'<canvas class="m3d" data-stl="{stl64(s["stl"])}"></canvas>'
                f'<div class="k">Kosten <b>{k["kosten"]}</b>{d}<br>Modellkanten ohne Foto {k["modell_ohne_foto"]}<br>Fotokanten ohne Modell {k["foto_ohne_modell"]}</div>{sch}</th>')
    k_ = "".join(kopf(i, s) for i, s in enumerate(st))
    for s in laufend:
        n = len(s.get("schritte", [])); k_ += f'<th><div class="nr">Stufe {len(st) + 1}: {html.escape(s["name"])}</div><div class="v">laeuft ({n} Schritte fertig)</div></th>'
    zeilen = ""
    for nr in fotos:
        z = f'<td class="fn">Foto {nr}</td>'
        for s in st:
            c = (s.get("je_foto") or {}).get(nr); z += f'<td><img loading="lazy" src="{bild64(s["bilder"][nr])}" alt="Foto {nr}"><div class="kf">Kosten {c}</div></td>'
        zeilen += f"<tr>{z}</tr>"
    doc = f"""<title>Qualitaetsstufen {html.escape(objname.split('(')[0].strip())}</title><meta name="claude:viewport-fit-sides" content="cover">
<style>
:root{{--bg:#f6f5f1;--fg:#1c1c1a;--mut:#6b6a64;--card:#fff;--line:#dedcd4;--gut:#1f7a4d;--schlecht:#b3412e;--warn:#8a6d1a;--m3d:#ecebe6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#151513;--fg:#ecebe6;--mut:#a3a29b;--card:#1f1f1c;--line:#34332e;--gut:#5cc08c;--schlecht:#e57a66;--warn:#d6b54a;--m3d:#262622;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#151513;--fg:#ecebe6;--mut:#a3a29b;--card:#1f1f1c;--line:#34332e;--gut:#5cc08c;--schlecht:#e57a66;--warn:#d6b54a;--m3d:#262622;color-scheme:dark}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
header{{padding-block:20px 4px;max-width:1100px}} h1{{font-size:20px;margin:0 0 6px}} p{{margin:4px 0;color:var(--mut);max-width:85ch}}
.wrap{{overflow-x:auto;padding-block:8px 32px}} h1{{text-wrap:balance}} table.g{{border-collapse:separate;border-spacing:8px}}
table.g>tbody>tr>th,table.g>tbody>tr>td{{background:var(--card);border:1px solid var(--line);border-radius:8px;vertical-align:top;padding:8px;text-align:left}}
table.g th{{width:320px;min-width:320px;font-weight:400}} td img{{width:320px;display:block;border-radius:4px}}
.nr{{font-weight:600;font-size:15px}} .v{{color:var(--mut);font-size:12px;margin-bottom:6px}}
canvas.m3d{{width:320px;height:260px;display:block;border-radius:6px;background:var(--m3d);touch-action:none;cursor:grab}}
.k{{margin-top:6px;color:var(--mut);font-variant-numeric:tabular-nums}} .k b{{color:var(--fg)}} .d.gut{{color:var(--gut)}} .d.schlecht{{color:var(--schlecht)}}
details{{margin-top:6px}} summary{{cursor:pointer;color:var(--mut)}} table.sch{{font-size:12px;border-collapse:collapse;margin-top:4px}} table.sch td{{padding:2px 4px;border-top:1px solid var(--line)}}
.ok{{color:var(--gut)}} .flach{{color:var(--warn)}} .hin{{color:var(--warn)}} .fn{{font-weight:600;white-space:nowrap}} .kf{{font-size:12px;color:var(--mut);margin-top:4px;font-variant-numeric:tabular-nums}}
.leg{{display:flex;gap:16px;flex-wrap:wrap;color:var(--mut);font-size:13px;margin:8px 0}} .leg i{{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:4px;vertical-align:-1px}}
</style><header><h1>Qualitaetsstufen: {html.escape(objname)}</h1>
<p>Jede Spalte ist eine Stufe: ein Verfahren fuer das ganze Modell, aufbauend auf der vorigen. Die 3D-Modelle drehen sich gemeinsam (ziehen, Mausrad zoomt).
Kosten = mittlerer Kantenabstand Modell gegen Foto in einer festen Bewertungsmaske (kleiner ist besser, ueber alle Stufen vergleichbar). Das Objekt bleibt unveraendert, bis du eine Stufe uebernimmst.</p>
<div class="leg"><span><i style="background:#00c800"></i>Modellkante trifft Fotokante</span><span><i style="background:#e00000"></i>Modellkante ohne Fotokante</span><span><i style="background:#f0d000"></i>Fotokante ohne Modellkante</span></div>
<p>Stand {html.escape(stand.get("zeit", ""))}, {len(fotos)} Fotos.</p></header>
<div class="wrap"><table class="g"><tr><th style="width:70px;min-width:70px"></th>{k_}</tr>{zeilen}</table></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
<script>
(function(){{
 const views=[]; let az=0.9, el=0.35, zoom=1.0, drag=null;
 function sicht(){{ for(const v of views){{ const r=v.r*2.4/zoom; v.cam.position.set(v.c.x+r*Math.cos(el)*Math.cos(az), v.c.y+r*Math.cos(el)*Math.sin(az), v.c.z+r*Math.sin(el)); v.cam.lookAt(v.c); v.ren.render(v.sc,v.cam); }} }}
 const farbe=getComputedStyle(document.documentElement).getPropertyValue('--m3d').trim()||'#ecebe6';
 document.querySelectorAll('canvas.m3d').forEach(cv=>{{
  const b=cv.dataset.stl; if(!b||!window.THREE) return; const bin=Uint8Array.from(atob(b),c=>c.charCodeAt(0)).buffer;
  const g=new THREE.STLLoader().parse(bin); g.computeVertexNormals(); g.computeBoundingSphere();
  const ren=new THREE.WebGLRenderer({{canvas:cv,antialias:true}}); ren.setPixelRatio(Math.min(2,window.devicePixelRatio||1)); ren.setSize(cv.clientWidth,cv.clientHeight,false); ren.setClearColor(new THREE.Color(farbe));
  const sc=new THREE.Scene(); sc.add(new THREE.Mesh(g,new THREE.MeshStandardMaterial({{color:0xc9c2b3,roughness:0.85,flatShading:true}})));
  sc.add(new THREE.HemisphereLight(0xffffff,0x555555,0.7)); const dl=new THREE.DirectionalLight(0xffffff,0.8); dl.position.set(1,-1.5,2); sc.add(dl);
  const cam=new THREE.PerspectiveCamera(35,cv.clientWidth/cv.clientHeight,1,1e6); cam.up.set(0,0,1);
  views.push({{ren,sc,cam,c:g.boundingSphere.center,r:g.boundingSphere.radius}});
  cv.addEventListener('pointerdown',e=>{{drag=[e.clientX,e.clientY]; cv.setPointerCapture(e.pointerId);}});
  cv.addEventListener('pointermove',e=>{{ if(!drag) return; az-=(e.clientX-drag[0])*0.01; el=Math.max(-0.2,Math.min(1.5,el+(e.clientY-drag[1])*0.01)); drag=[e.clientX,e.clientY]; sicht(); }});
  cv.addEventListener('pointerup',()=>drag=null);
  cv.addEventListener('wheel',e=>{{e.preventDefault(); zoom=Math.max(0.5,Math.min(6,zoom*(e.deltaY<0?1.1:0.9))); sicht();}},{{passive:false}});
 }}); sicht();
}})();
</script>"""
    open(os.path.join(aus, "index.html"), "w").write(doc)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--plan", required=True); ap.add_argument("--fotos", type=int, default=12); ap.add_argument("--aus"); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); plan = json.load(open(a.plan)); os.environ["FD_GPU"] = "1"
    if plan.get("mass") == "lr": os.environ["FD_MASS"] = "lr"                                         # faires Kantenmass (foto_diff kosten_lr, 2026-11-05); eigener --aus-Ordner, Caches sind je Mass   # Arbeiterzahl nach VRAM (Raster)
    aus = a.aus or os.path.join("/media/oem/scan/rc-park_null", f"qualitaetsstufen_{os.path.basename(od)}"); os.makedirs(aus, exist_ok=True)
    sp = os.path.join(aus, "stand.json"); stand = json.load(open(sp)) if os.path.exists(sp) else dict(stufen=[])
    fotos = PS.fotos_waehlen(od, a.fotos, ohne_nacht=bool(plan.get("ohne_nacht"))); md = os.path.join(aus, "maske"); os.makedirs(md, exist_ok=True); t0 = time.time()
    def speichern():
        stand["zeit"] = time.strftime("%Y-%m-%d %H:%M"); json.dump(stand, open(sp + ".tmp", "w"), indent=1); os.replace(sp + ".tmp", sp);   # atomar (2026-11-05: Abbruch beim Schreiben zerstoerte stand.json)
        html_schreiben(aus, obj.get("name", od), stand, fotos)
    print(f"qualitaetsstufen {os.path.basename(od)}: {len(plan['stufen'])} Stufen, {len(fotos)} Fotos ({','.join(fotos)}) -> {aus}", flush=True)
    if not all(os.path.exists(os.path.join(md, f"{nr}.png")) for nr in fotos):                       # feste Bewertungsmaske: Ausgangsmodell, Silhouette + 3 m
        stl = bauen_fest(obj, {}, f"_qs_{os.path.basename(od)}_maske.stl", os.path.join(aus, "elemente_maske.json"))
        bewerten(objp, fotos, stl, os.path.join(aus, "maske_lauf"), maske_aus=md); os.remove(os.path.join(ROOT, stl))
    weg = [nr for nr in fotos if not os.path.exists(os.path.join(md, f"{nr}.png"))]                  # Modell im Foto nicht sichtbar (leere Silhouette, z. B. null5 Foto 089) -> nicht bewertbar
    if weg: fotos = [nr for nr in fotos if nr not in weg]; print(f"  ohne Bewertungsmaske (Modell nicht im Bild) entfernt: {','.join(weg)} -> {len(fotos)} Fotos", flush=True)
    fest = {}
    for i, cfg in enumerate(plan["stufen"]):
        offen = cfg.get("versuche") and i < len(stand["stufen"]) and len(stand["stufen"][i].get("schritte", [])) < len(cfg["versuche"])   # neue Versuche in einer fertigen Stufe -> Stufe fortsetzen
        if i < len(stand["stufen"]) and stand["stufen"][i].get("kennzahlen") and not offen: fest = stand["stufen"][i]["fest"]; continue
        if i >= len(stand["stufen"]): stand["stufen"].append(dict(name=cfg["name"], verfahren=cfg["verfahren"]))
        st = stand["stufen"][i]; print(f"  Stufe {i + 1}: {cfg['name']} ({cfg['verfahren']})  [{time.time() - t0:.0f} s]", flush=True)
        ctx = dict(objp=objp, obj=obj, plan=plan, fotos=fotos, aus=aus, md=md, fest=fest, nr=i + 1, t0=t0, speichern=speichern, vorige=stand["stufen"][i - 1] if i else None)
        VERFAHREN[cfg["verfahren"]](ctx, st, cfg); fest = st["fest"]; speichern()
        k = st["kennzahlen"]; print(f"    Stufe {i + 1} fertig: Kosten {k['kosten']} | Modellkanten ohne Foto {k['modell_ohne_foto']} | Fotokanten ohne Modell {k['foto_ohne_modell']}", flush=True)
    print(f"FERTIG [{time.time() - t0:.0f} s] -> {os.path.join(aus, 'index.html')}")


if __name__ == "__main__":
    main()

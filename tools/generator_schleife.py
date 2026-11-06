#!/usr/bin/env python3
"""generator_schleife.py - die ITERATIVE SCHLEIFE (Nutzerwunsch 6.11.): das GENERIERTE Modell immer wieder ueber ALLE kalibrierten Fotos legen
(je Foto die eigene Kamera), Abweichung messen, die freien Generator-Parameter GEMEINSAM anpassen, bis die Abweichung konvergiert.

Baut auf (nichts doppelt): param_suche (fotos_waehlen, Arbeiter, foto_diff im Pool, bauen per BAUTEIL_PARAM/STL_NAME/ELEMENTE_AUS), foto_diff (kosten_lr = faires
Kantenmass 'a contrario', kleiner = besser; rot/gelb; Kostenkarte), elementbuch (Tor-Buchstabe e), SPEC_S3 (Kennzahl, Tor, Abbruch). Misst NUR, was Kanten in
den Fotos zeigen (Regel 4: Foto-Blindheit; Dachtiefe auf glatten Flaechen etc. bleibt offen).

  /media/oem/scan/venv-seg/bin/python -I tools/generator_schleife.py modelle/<obj>/objekt.json [--aus DIR] [--fotos N] [--validierung M] [--minuten 40]
        [--starts 2] [--pop 6] [--kerne 10] [--uebernehmen] [--fd "--tiefen aus"]
  Lange Laeufe: tools/job_start.sh gschleife /media/oem/scan/rc-park_null/gschleife_<obj>.log <diese Zeile>

PARAMETERRAUM (nichts Objektspezifisches im Code). Reihenfolge der Quellen: --raum DATEI | <objektordner>/parameter_raum.json | objekt.json['parameter_raum'] |
Plan (--plan, Standard modelle/PLAN_STANDARD_qualitaetsstufen.json, Stufe 'parameter': werte 'von:bis:schritt'). Format (Datei/Objekt):
  {"<bauteil-typ>": {"<param>": {"lo": -3.0, "hi": 0.5, "schritt": 0.05, "typ": "float|int", "start": optional}}}
  Jedes Bauteil der Liste wird wie im Generator ueber BAUTEIL_PARAM angesprochen (baukasten_gen.py ueberschreibt spec[param]); ein NEUES Bauteil (z. B. rumpf_wolke)
  braucht nur Eintraege im Parameterraum, keine Aenderung hier.
HANDEINGRIFFE (objekt.json oder --overrides DATEI, zusammengefuehrt):
  "overrides": {"<bauteil>": {"<param>": <wert>, "fest": true|false, "quelle": "..."}}   fest=true: Wert gilt, die Schleife aendert ihn NIE (Kontext);
                                                                                          fest=false/fehlt: Wert ist nur der STARTWERT.
  "sperren": ["<bauteil>", "<bauteil>.<param>", ...]    nicht optimiert (Wert bleibt wie im Objekt). 'fassade:<id>' wird vermerkt, nicht ausgewertet (Parameter sind je Bauteil).
ZIELFUNKTION J = Mittel(kosten_lr je Foto) + w * Mittel(schlechtestes Viertel der Verschlechterungen gegen den Start) (verhindert, dass ein Foto auf Kosten anderer gewinnt).
VERFAHREN: CMA-ES (cma, normierter Raum, Grenzen) je Start, mehrere Starts (Basis + zufaellig, feste Seeds); Rueckfall Koordinatenabstieg mit Parabelfit.
ANNAHMETOR (S1b a/e + Mehrheit): neuer Stand nur, wenn (a) Mittel rot+gelb nicht schlechter (+tol) und kein Foto um > 0,10 schlechter, (b) kosten_lr in >= 2/3 der
  beurteilbaren Fotos besser, kein Foto um > tor_lr_schlecht schlechter, (e) Elementbuch (nur wenn die Elementdatei Geometrieelemente traegt). Sonst bleibt der alte Stand.
ABBRUCH: je Start Verbesserung der besten J < eps ueber --geduld Generationen oder CMA-Kriterium; global Budget (--minuten, --max-ausw). 'konvergiert' nur bei ersterem.
AUSGABE (nur <aus>/): protokoll.jsonl (je Generation), runde_<k>/ (Overlays foto_diff rot/gelb + blatt.jpg), ergebnis.json, cache_*.jsonl. objekt.json bleibt unberuehrt,
ausser --uebernehmen (schreibt die angenommenen Werte mit quelle + historie in objekt.json['bauteile']).
GPU wird NICHT benutzt (CUDA_VISIBLE_DEVICES leer, CPU-Fassung von foto_diff).
"""
import sys, os, json, glob, re, argparse, subprocess, time, hashlib, shutil, copy, math, datetime
import numpy as np

TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import param_suche as PS
import elementbuch as EB

J_UNGUELTIG = 1.0e3
MIN_ANTEIL_FOTOS = 0.8            # ANNAHME: Vektor gilt als ungueltig, wenn weniger als 80 % der Fotos bewertet werden konnten


# ------------------------------------------------------------------ Parameterraum, Overrides
def raum_laden(objp, obj, a):
    """-> Liste dict(bauteil, param, lo, hi, schritt, typ, start). Quellenreihenfolge siehe Modul-Docstring."""
    od = os.path.dirname(objp); raum = None; quelle = None
    for q, lade in ((a.raum, lambda: json.load(open(a.raum))) if a.raum else (None, None),
                    (os.path.join(od, "parameter_raum.json"), lambda: json.load(open(os.path.join(od, "parameter_raum.json")))) if os.path.exists(os.path.join(od, "parameter_raum.json")) else (None, None),
                    ("objekt.json['parameter_raum']", lambda: obj["parameter_raum"]) if obj.get("parameter_raum") else (None, None)):
        if q: raum, quelle = lade(), q; break
    out = []
    if raum is not None:
        for b, ps in raum.items():
            if b.startswith("_"): continue
            for p, d in ps.items():
                if p.startswith("_"): continue
                out.append(dict(bauteil=b, param=p, lo=float(d["lo"]), hi=float(d["hi"]), schritt=float(d.get("schritt", (float(d["hi"]) - float(d["lo"])) / 50)), typ=d.get("typ", "float"), start=d.get("start")))
    else:                                                                                                    # Rueckfall: Parameterliste der Plan-Stufe 'parameter'
        quelle = a.plan
        if os.path.exists(a.plan):
            pl = json.load(open(a.plan))
            for s in pl.get("stufen", []):
                if s.get("verfahren") == "parameter":
                    for p in s["parameter"]:
                        v0, v1, st = [float(x) for x in p["werte"].split(":")]
                        out.append(dict(bauteil=p["bauteil"], param=p["param"], lo=min(v0, v1), hi=max(v0, v1), schritt=st / 4.0, typ="float", start=None))
    if not out: raise SystemExit("kein Parameterraum (weder --raum, parameter_raum.json, objekt.json['parameter_raum'] noch Plan)")
    return out, quelle


def overrides_laden(objp, obj, a):
    """-> (fest {b: {p: wert}}, start {b: {p: wert}}, sperren [str], quellen {b: str})."""
    ov = copy.deepcopy(obj.get("overrides") or {}); sp = list(obj.get("sperren") or [])
    if a.overrides:
        z = json.load(open(a.overrides))
        for b, ps in (z.get("overrides") or {}).items(): ov.setdefault(b, {}).update(ps)
        sp += list(z.get("sperren") or [])
    fest, start, quellen = {}, {}, {}
    for b, ps in ov.items():
        for p, v in ps.items():
            if p in ("fest", "quelle") or (isinstance(v, bool) and p == "fest"): continue
            (fest if ps.get("fest") is True else start).setdefault(b, {})[p] = v
        if ps.get("quelle"): quellen[b] = ps["quelle"]
    return fest, start, sp, quellen


def spec_wert(obj, b, p):
    for s in obj.get("bauteile") or []:
        if s.get("typ") == b and p in s and isinstance(s[p], (int, float)) and not isinstance(s[p], bool): return float(s[p])
    return None


class Raum:
    def __init__(self, objp, obj, a):
        raum, self.quelle = raum_laden(objp, obj, a)
        self.fest, startov, self.sperren, self.quellen = overrides_laden(objp, obj, a)
        self.gesperrt, self.opt = [], []
        for r in raum:
            key = f"{r['bauteil']}.{r['param']}"
            if r["param"] in self.fest.get(r["bauteil"], {}): self.gesperrt.append((key, "fest (Override)")); continue
            if r["bauteil"] in self.sperren or key in self.sperren: self.gesperrt.append((key, "gesperrt")); continue
            if not any(s.get("typ") == r["bauteil"] for s in (obj.get("bauteile") or [{"typ": "rumpf_lod2"}])) and not a.neue_bauteile:
                self.gesperrt.append((key, "Bauteil nicht in objekt.json['bauteile'] (--neue-bauteile erlaubt es)")); continue
            self.opt.append(r)
        if not self.opt: raise SystemExit("keine freien Parameter (alles fest/gesperrt)")
        x0 = []
        for r in self.opt:
            v = startov.get(r["bauteil"], {}).get(r["param"])
            if v is None: v = spec_wert(obj, r["bauteil"], r["param"])
            if v is None: v = r["start"]
            if v is None: v = 0.5 * (r["lo"] + r["hi"])
            x0.append(float(v))
        self.x_start = self.quant(np.array(x0))

    def quant(self, v):
        out = []
        for r, x in zip(self.opt, np.asarray(v, float)):
            x = min(max(x, r["lo"]), r["hi"])
            x = round(x) if r["typ"] == "int" else r["lo"] + round((x - r["lo"]) / r["schritt"]) * r["schritt"]
            out.append(round(min(max(x, r["lo"]), r["hi"]), 6))
        return np.array(out)

    def norm(self, v): return np.array([(x - r["lo"]) / (r["hi"] - r["lo"]) for r, x in zip(self.opt, v)])
    def denorm(self, u): return np.array([r["lo"] + float(np.clip(x, 0, 1)) * (r["hi"] - r["lo"]) for r, x in zip(self.opt, u)])

    def bp(self, v, tag="Lauf"):
        """BAUTEIL_PARAM fuer den Generator: feste Overrides + Vektor; je Bauteil eine quelle (Regel 3b)."""
        bp = copy.deepcopy(self.fest)
        for r, x in zip(self.opt, v): bp.setdefault(r["bauteil"], {})[r["param"]] = int(x) if r["typ"] == "int" else float(x)
        for b in bp:
            q = self.quellen.get(b)
            bp[b]["quelle"] = (q + "; " if q else "") + f"generator_schleife.py: Parameter aus Fotovergleich (kosten_lr ueber kalibrierte Fotos), fest = Handeingriff"
        return bp

    def name(self, i): return f"{self.opt[i]['bauteil']}.{self.opt[i]['param']}"


# ------------------------------------------------------------------ Bewertung (Pool, Cache)
class Bewerter:
    def __init__(self, objp, obj, raum, fotos, a, aus):
        self.objp, self.obj, self.raum, self.fotos, self.a, self.aus = objp, obj, raum, list(fotos), a, aus
        self.root_obj = os.path.dirname(os.path.dirname(os.path.dirname(objp)))
        self.extra = a.fd.split(); self.masse = {"lr": "kosten_lr", "lr_versatz": "kosten_lr_versatz", "param": "kosten_param"}[a.mass]
        key = hashlib.sha1(json.dumps([self.masse, self.extra, a.maske_rand, os.path.abspath(a.objekt), a.region, a.region_rand if a.region != "aus" else 0], sort_keys=True).encode()).hexdigest()[:10]
        self.cachef = os.path.join(aus, f"cache_{key}.jsonl"); self.cache = {}; self.md = os.path.join(aus, "masken"); os.makedirs(self.md, exist_ok=True)
        self.ev = os.path.join(aus, "ev"); os.makedirs(self.ev, exist_ok=True); self.n_ausw = 0; self.n_treffer = 0; self.karten = False; self.pool = None
        if os.path.exists(self.cachef):
            for l in open(self.cachef):
                try: d = json.loads(l); d["karten_da"] = False; self.cache[d["h"]] = d
                except Exception: pass
        self.mask_da = {nr for nr in fotos if os.path.exists(os.path.join(self.md, f"{nr}.png"))}

    def pool_starten(self, n_aufg):
        import multiprocessing as mp
        n = min(self.a.kerne, PS.arbeiter_zahl(n_aufg, gb_je=self.a.gb_je, reserve_gb=self.a.reserve_gb))
        os.environ["FD_PUNKTE_DIR"] = PS.PUNKTE_DIR
        if self.pool is None or n != self.n_arbeiter:
            if self.pool: self.pool.close(); self.pool.join()
            self.pool = mp.get_context("spawn").Pool(n); self.n_arbeiter = n
            print(f"  {n} Arbeitsprozesse (Kerne {os.cpu_count()}, Grenze {self.a.kerne}, RAM-begrenzt)", flush=True)

    def hash(self, bp): return hashlib.sha1(json.dumps(bp, sort_keys=True).encode()).hexdigest()[:14]

    def bauen_viele(self, eintraege):
        """eintraege [(h, bp)] -> {h: (stl_abs, elemente) | None}; Generator parallel (eigene STL + Elementdatei je Vektor)."""
        from concurrent.futures import ThreadPoolExecutor
        def eins(e):
            h, bp = e; ed = os.path.join(self.ev, h); os.makedirs(ed, exist_ok=True); name = f"_gs_{os.getpid()}_{h}.stl"; el = os.path.join(ed, "elemente.json")
            cmd = self.obj["generator"]; cmd = re.sub(r"STL_NAME=\S+", f"STL_NAME={name}", cmd) if "STL_NAME=" in cmd else f"STL_NAME={name} " + cmd
            try:
                r = subprocess.run(["bash", "-c", cmd.replace("~", os.path.expanduser("~"))], cwd=ROOT, env=dict(os.environ, BAUTEIL_PARAM=json.dumps(bp), ELEMENTE_AUS=el), capture_output=True, text=True, timeout=1800)
                q = os.path.join(ROOT, "modelle", "stl", name)
                if r.returncode != 0 or not os.path.exists(q):
                    open(os.path.join(ed, "fehler.log"), "w").write((r.stdout + r.stderr)[-3000:]); return h, None
                ziel = os.path.join(ed, "modell.stl"); shutil.move(q, ziel); return h, (ziel, el)
            except Exception as ex:
                open(os.path.join(ed, "fehler.log"), "w").write(repr(ex)); return h, None
        with ThreadPoolExecutor(max(1, min(len(eintraege), 6))) as ex: return dict(ex.map(eins, eintraege))

    def messen(self, items, fotos, mit_maske=False, karten=None, schreiben=True):
        """items [(h, bp)] -> Cache gefuellt. Je Vektor werden nur noch fehlende Fotos gemessen. Rueckgabe: {h: Eintrag}."""
        karten = self.karten if karten is None else karten
        todo = []
        for h, bp in items:
            c = self.cache.get(h); fehlt = [nr for nr in fotos if not (c and nr in c["je_foto"] or (c and nr in c.get("fotofehler", {})))] if not (c and c.get("fehler")) else []   # Fehlschlaege bleiben im Cache (Generator/Foto), werden nicht endlos wiederholt
            if karten and c and not c.get("karten_da"): fehlt = list(fotos)                      # Karten wurden geloescht: neu messen
            if fehlt: todo.append((h, bp, fehlt))
        self.n_treffer += len(items) - len(todo)
        if todo:
            t0 = time.time(); bau = self.bauen_viele([(h, bp) for h, bp, _ in todo])
            auf = []; stls = {}
            for h, bp, fehlt in todo:
                if bau[h] is None: self.cache[h] = dict(h=h, bp=bp, je_foto={}, rg={}, fehler="Generator fehlgeschlagen", sek=0); continue
                stl, el = bau[h]; stls[h] = (stl, el)
                for nr in fehlt:
                    d = os.path.join(self.ev, h, nr); os.makedirs(d, exist_ok=True)
                    args = [self.objp, nr, "--stl", stl, "--aus", d] + self.extra
                    if mit_maske and nr not in self.mask_da: args += ["--maske-aus", os.path.join(self.md, f"{nr}.png"), "--maske-rand", str(self.a.maske_rand)]
                    args += ["--bewertung-maske", os.path.join(self.md, f"{nr}.png")]
                    if self.a.region != "aus": args += ["--region", self.a.region, "--region-rand", str(self.a.region_rand)]
                    if karten: args += ["--kostenkarte", os.path.join(d, "kostenkarte.npz")]
                    auf.append(((args, os.path.join(d, f"foto_diff_{nr}.json")), h, nr))
            self.pool_starten(max(1, len(auf)))
            fertig = {h: 0 for h in stls}; soll = {h: sum(1 for _, hh, _ in auf if hh == h) for h in stls}
            for (jp, fehler), (_, h, nr) in zip(self.pool.imap(PS._fd_aufgabe_kern, [x[0] for x in auf]), auf):    # geordnet: Vektor fuer Vektor
                c = self.cache.setdefault(h, dict(h=h, bp=dict(items)[h], je_foto={}, rg={}, fehler=None, sek=0))
                if fehler or not os.path.exists(jp): c.setdefault("fotofehler", {})[nr] = fehler or "keine Ausgabe"
                else:
                    try:
                        e = json.load(open(jp)); v = e.get(self.masse)
                        if v is not None:
                            c["je_foto"][nr] = float(v); c["rg"][nr] = [float(e.get("anteil_modellkanten_ohne_foto", 0.0)), float(e.get("anteil_fotokanten_ohne_modell", 0.0))]
                            c.setdefault("px", {})[nr] = [int(e.get("modellkanten_px", 0)), int(e.get("fotokanten_px", 0))]
                            c.setdefault("versatz_m", {})[nr] = (e.get("versatz") or {}).get("versatz_m")
                        else: c.setdefault("fotofehler", {})[nr] = "Kosten None (< 50 Kantenpixel)"
                    except Exception as ex: c.setdefault("fotofehler", {})[nr] = repr(ex)
                if mit_maske: self.mask_da.add(nr) if os.path.exists(os.path.join(self.md, f"{nr}.png")) else None
                fertig[h] += 1
                if fertig[h] == soll[h]:
                    self.punkte_frei(stls[h][0])
            for h, (stl, el) in stls.items():
                c = self.cache[h]; c["karten_da"] = bool(karten); c["elemente"] = el if os.path.exists(el) else None; c["sek"] = round(time.time() - t0)
                try: os.remove(stl)
                except OSError: pass
                self.n_ausw += 1
            if schreiben:
                with open(self.cachef, "a") as f:
                    for h, bp, _ in todo: f.write(json.dumps(self.cache[h], ensure_ascii=False) + "\n")
        return {h: self.cache[h] for h, _ in items}

    def punkte_frei(self, stl):
        for q in glob.glob(os.path.join(PS.PUNKTE_DIR, os.path.basename(stl) + "_*")):
            try: os.remove(q)
            except OSError: pass

    def aufraeumen(self, h, behalten_bilder=False, behalten_karten=False):
        """Bilder (jpg) und Kostenkarten eines Vektors loeschen (Speicherplatz); die JSON bleiben."""
        ed = os.path.join(self.ev, h)
        for f in glob.glob(os.path.join(ed, "*", "*")):
            if f.endswith(".json"): continue
            if f.endswith(".npz") and behalten_karten: continue
            if f.endswith(".jpg") and behalten_bilder: continue
            try: os.remove(f)
            except OSError: pass
        if not behalten_karten and h in self.cache: self.cache[h]["karten_da"] = False
        if not behalten_karten:
            try: os.remove(os.path.join(ed, "elemente.json"))
            except OSError: pass


def nr_ok(c): return bool(c) and not c.get("fehler")


# ------------------------------------------------------------------ Zielfunktion und Tor
class Ziel:
    def __init__(self, a, fotos, ref_kosten):
        self.a, self.fotos, self.ref = a, list(fotos), ref_kosten               # ref: Kosten je Foto des STARTS (fest -> J konsistent im ganzen Lauf)

    def je_foto(self, c):
        """Kosten je Foto mit Strafwert fuer fehlende Fotos; None wenn der Vektor ungueltig ist."""
        if not c or c.get("fehler"): return None
        n_ok = sum(1 for nr in self.fotos if nr in c["je_foto"])
        if n_ok < MIN_ANTEIL_FOTOS * len(self.fotos): return None
        return {nr: (c["je_foto"][nr] if nr in c["je_foto"] else self.ref[nr] + 0.05) for nr in self.fotos}

    def J(self, c):
        k = self.je_foto(c)
        if k is None: return J_UNGUELTIG, None
        v = np.array([k[nr] for nr in self.fotos]); r = np.array([self.ref[nr] for nr in self.fotos]); schl = np.sort(np.maximum(0.0, v - r))[::-1]
        nq = max(1, int(math.ceil(len(v) / 4.0)))
        return float(v.mean() + self.a.w_schlecht * schl[:nq].mean()), k


def tor(neu, alt, fotos, a, bew, ziel):
    """Annahmetor (S1b a/e + Mehrheit). neu/alt: Cache-Eintraege. -> (ok, gruende, detail)"""
    gr = []; kn, ka = ziel.je_foto(neu), ziel.je_foto(alt)
    if kn is None or ka is None: return False, ["(a) Messung unvollstaendig"], {}
    rgn, rga = neu["rg"], alt["rg"]
    beurteilbar = lambda c, nr: nr in c["rg"] and min(c.get("px", {}).get(nr, [0, 0])) >= a.min_kanten_px            # rot/gelb = 0/0 bei (fast) leerem Kantenbild ist NICHT 'perfekt' (foto_diff teilt durch max(1, n)), sondern nicht beurteilbar
    gem = [nr for nr in fotos if beurteilbar(neu, nr) and beurteilbar(alt, nr)]
    sn = {nr: sum(rgn[nr]) for nr in gem}; sa = {nr: sum(rga[nr]) for nr in gem}
    mn, ma = float(np.mean([sn[nr] for nr in gem])) if gem else 9, float(np.mean([sa[nr] for nr in gem])) if gem else 0
    verl = [f"{nr} Summe {sa[nr]:.3f}->{sn[nr]:.3f}" for nr in gem if sn[nr] > sa[nr] + a.tor_foto_rg]
    if len(gem) < 3: gr.append(f"(a) nur {len(gem)} Fotos mit rot/gelb vergleichbar (< 3)")
    if mn > ma + a.tor_tol: gr.append(f"(a) Mittel rot+gelb schlechter: {ma:.4f}->{mn:.4f} (> +{a.tor_tol})")
    if verl: gr.append(f"(a) Foto deutlich schlechter (rot+gelb > +{a.tor_foto_rg}): " + "; ".join(verl[:5]))
    d = np.array([kn[nr] - ka[nr] for nr in fotos]); besser = int((d < -a.tor_lr_besser).sum()); schlecht = [nr for nr, x in zip(fotos, d) if x > max(a.tor_lr_schlecht, 0.1 * abs(ka[nr]))]   # ANNAHME: absolut 0,01 (Kaufhaus-Skala, STAND 5.11.) oder 10 % der Fotokosten (massstabsfrei)
    if besser < (2.0 / 3.0) * len(fotos): gr.append(f"(b) kosten_lr nur in {besser}/{len(fotos)} Fotos besser (< 2/3)")
    if schlecht: gr.append(f"(b) Foto deutlich schlechter (kosten_lr > +{a.tor_lr_schlecht}): {','.join(schlecht[:6])}")
    t = (d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))) if len(d) > 2 and d.std(ddof=1) > 0 else 0.0
    det = dict(rg_mittel=[round(ma, 4), round(mn, 4)], besser=besser, n=len(fotos), schlechter_deutlich=schlecht, dm=round(float(d.mean()), 6), t=round(float(t), 2))
    if not gr and bew.karten and neu.get("elemente") and alt.get("elemente") and os.path.exists(neu["elemente"]) and os.path.exists(alt["elemente"]):   # (e) Elementbuch
        try:
            kam = EB.Kameras(bew.objp, bew.obj, bew.root_obj)
            mk = lambda c: {nr: os.path.join(bew.ev, c["h"], nr, "kostenkarte.npz") for nr in fotos}
            ok_e, gr_e, de = EB.pruefen(dict(elemente=alt["elemente"], karten=mk(alt)), dict(elemente=neu["elemente"], karten=mk(neu)), fotos, kam); gr += gr_e; det["e"] = de["zaehlung"]
        except Exception as ex: det["e"] = f"nicht pruefbar: {type(ex).__name__}: {ex}"
    return not gr, gr, det


# ------------------------------------------------------------------ Optimierer
class KoordinatenAbstieg:
    """Rueckfall ohne cma / bei n < 2: je Generation EIN Parameter, 5 Punkte (-2..+2 Schritte, Schritt = scale*Spanne), Parabelfit, Schritt halbiert bei Stillstand."""
    def __init__(self, x0, sigma, seed, n):
        self.x = np.array(x0, float); self.n = n; self.k = 0; self.s = sigma; self.fx = None; self.gen_ohne = 0; self.pts = None
    def ask(self):
        i = self.k % self.n; self.i = i; X = []
        for m in (-2, -1, 0, 1, 2):
            x = self.x.copy(); x[i] = np.clip(x[i] + m * self.s / 2.0, 0, 1); X.append(x)
        self.pts = X; return X
    def tell(self, X, J):
        j = int(np.argmin(J)); i = self.i
        xs = np.array([x[i] for x in X]); order = np.argsort(xs); xs, ys = xs[order], np.array(J)[order]
        xm, _, st = PS.parabel(xs, ys); cand = [X[j]]
        if st == "ok": xp = self.x.copy(); xp[i] = float(np.clip(xm, 0, 1)); cand.append(xp)
        if J[j] < (self.fx if self.fx is not None else 1e99) - 1e-9: self.x = X[j].copy(); self.fx = float(J[j]); self.gen_ohne = 0
        else: self.gen_ohne += 1
        self.k += 1
        if self.k % self.n == 0 and self.gen_ohne >= self.n: self.s /= 2.0; self.gen_ohne = 0
    def stop(self): return self.s < 0.01
    def best(self): return self.x


class CMA:
    def __init__(self, x0, sigma, seed, n, pop):
        import cma
        self.es = cma.CMAEvolutionStrategy(list(x0), sigma, {"bounds": [0, 1], "popsize": pop, "seed": seed, "verbose": -9, "tolfun": 1e-9, "tolx": 1e-6})
    def ask(self): return [np.asarray(x) for x in self.es.ask()]
    def tell(self, X, J): self.es.tell([list(x) for x in X], [float(j) for j in J])
    def stop(self): return bool(self.es.stop())
    def best(self): return np.asarray(self.es.result.xbest) if self.es.result.xbest is not None else np.asarray(self.es.mean)


def optimierer(art, x0, sigma, seed, n, pop):
    if art == "cma" and n >= 2:
        try: return CMA(x0, sigma, seed, n, pop)
        except ImportError: print("  cma nicht installiert -> Koordinatenabstieg", flush=True)
    return KoordinatenAbstieg(x0, sigma, seed, n)


# ------------------------------------------------------------------ Overlays
def overlays(bew, h, fotos_ov, ziel_dir, titel):
    import cv2
    os.makedirs(ziel_dir, exist_ok=True); tiles = []
    for nr in fotos_ov:
        q = os.path.join(bew.ev, h, nr, f"foto_diff_{nr}.jpg")
        if not os.path.exists(q): continue
        im = cv2.imread(q)
        if im is None: continue
        s = 1400.0 / im.shape[1]; im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); cv2.imwrite(os.path.join(ziel_dir, f"foto_diff_{nr}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 82])
        t = cv2.resize(im, (640, int(640 * im.shape[0] / im.shape[1]))); cv2.putText(t, f"{nr} {titel}", (8, 28), 0, 0.8, (255, 255, 255), 2); tiles.append(t)
    if tiles:
        hmax = max(t.shape[0] for t in tiles); tiles = [np.pad(t, ((0, hmax - t.shape[0]), (0, 0), (0, 0))) for t in tiles]
        while len(tiles) % 3: tiles.append(np.zeros_like(tiles[0]))
        cv2.imwrite(os.path.join(ziel_dir, "blatt.jpg"), np.vstack([np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]), [cv2.IMWRITE_JPEG_QUALITY, 80])


def waehle_gleichmaessig(liste, n):
    if n is None or len(liste) <= n: return list(liste)
    return [liste[int(round(i))] for i in np.linspace(0, len(liste) - 1, n)]


# ------------------------------------------------------------------ Hauptlauf
def main(argv=None):
    ap = argparse.ArgumentParser(description="Generator-Schleife: Parameter gemeinsam gegen alle kalibrierten Fotos anpassen")
    ap.add_argument("objekt"); ap.add_argument("--aus"); ap.add_argument("--raum"); ap.add_argument("--overrides"); ap.add_argument("--plan", default=os.path.join(ROOT, "modelle", "PLAN_STANDARD_qualitaetsstufen.json"))
    ap.add_argument("--fotos", type=int, default=None, help="Suchfotos: gleichmaessig N aus allen kalibrierten (Standard: ALLE)"); ap.add_argument("--fotoliste")
    ap.add_argument("--validierung", type=int, default=0, help="zusaetzlich M Fotos nur fuer vorher/nachher (nicht in der Suche, soweit moeglich)")
    ap.add_argument("--mass", default="lr", choices=["lr", "lr_versatz", "param"]); ap.add_argument("--fd", default="", help="weitere foto_diff-Argumente (z. B. '--tiefen aus')")
    ap.add_argument("--maske-rand", type=float, default=3.0, help="Bewertungsmaske = Silhouette des START-Modells + Rand (m), fest fuer den ganzen Lauf")
    ap.add_argument("--verfahren", default="cma", choices=["cma", "koordinaten"]); ap.add_argument("--pop", type=int, default=0); ap.add_argument("--sigma", type=float, default=0.2); ap.add_argument("--starts", type=int, default=2)
    ap.add_argument("--geduld", type=int, default=3); ap.add_argument("--eps", type=float, default=2e-5, help="kleinste J-Verbesserung, die zaehlt"); ap.add_argument("--w-schlecht", type=float, default=0.5)
    ap.add_argument("--minuten", type=float, default=40.0); ap.add_argument("--max-ausw", type=int, default=100000); ap.add_argument("--max-generationen", type=int, default=10000)
    ap.add_argument("--tor-tol", type=float, default=0.01); ap.add_argument("--tor-foto-rg", type=float, default=0.10); ap.add_argument("--tor-lr-besser", type=float, default=1e-5); ap.add_argument("--tor-lr-schlecht", type=float, default=0.01)
    ap.add_argument("--tor-versuche", type=int, default=3); ap.add_argument("--min-kanten-px", type=int, default=50, help="Tor (a): rot/gelb eines Fotos zaehlt nur mit mindestens so vielen Modell- UND Fotokantenpixeln (ANNAHME 50, wie foto_diff kosten)"); ap.add_argument("--overlay-fotos", type=int, default=6)
    ap.add_argument("--kerne", type=int, default=10); ap.add_argument("--gb-je", type=float, default=2.3); ap.add_argument("--reserve-gb", type=float, default=1.0); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--neue-bauteile", action="store_true", help="Parameter von Bauteilen zulassen, die nicht in objekt.json['bauteile'] stehen (Anhaengen per BAUTEIL_PARAM 'anhaengen')")
    ap.add_argument("--gpu", action="store_true", help="foto_diff auf der GPU (FD_GPU=1, FD_RASTER=0 wie param_suche); Arbeiterzahl wird zusaetzlich vom freien VRAM begrenzt. Ergebnis muss dem CPU-Lauf entsprechen (Nachweis: START-Zeile).")
    ap.add_argument("--region", default="aus", choices=["aus", "himmel"], help="Bildregion der Bewertung: himmel = nur Band um die Himmelsgrenze (Stufe 1: Dach/First/Giebel)"); ap.add_argument("--region-rand", type=float, default=2.0, help="Halbbreite des Himmelsbandes in m (ANNAHME 2 m)")
    ap.add_argument("--uebernehmen", action="store_true", help="angenommene Werte mit quelle + historie in objekt.json['bauteile'] schreiben (Standard: NICHTS ins Objekt)")
    a = ap.parse_args(argv)
    a.objekt = os.path.abspath(a.objekt); objp = a.objekt; obj = json.load(open(objp)); od = os.path.dirname(objp)
    if a.gpu: os.environ["FD_GPU"] = "1"; os.environ["FD_RASTER"] = "0"; os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")   # GPU-Fassung (Nutzerregel: GPU maximal nutzen)
    else: os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ.pop("FD_GPU", None); os.environ["FD_RASTER"] = "0"          # Standard: CPU (laeuft ein anderer GPU-Job)
    try: os.nice(10)
    except OSError: pass
    aus = os.path.abspath(a.aus or os.path.join("/media/oem/scan/rc-park_null", f"gschleife_{os.path.basename(od)}_{datetime.datetime.now():%Y%m%d_%H%M%S}")); os.makedirs(aus, exist_ok=True)
    t_start = time.time(); budget_s = a.minuten * 60.0
    raum = Raum(objp, obj, a)
    alle = a.fotoliste.split(",") if a.fotoliste else PS.fotos_waehlen(od, None, ohne_nacht=True)
    if not alle: raise SystemExit("keine kalibrierten Fotos mit gueltigem Kamera-Tor")
    fotos = waehle_gleichmaessig(alle, a.fotos); rest = [nr for nr in alle if nr not in fotos]
    val = waehle_gleichmaessig(rest, a.validierung) if a.validierung else []
    fotos_ov = waehle_gleichmaessig(fotos, a.overlay_fotos)
    pop = a.pop or (4 + int(3 * math.log(len(raum.opt))))
    log = lambda s: print(f"[{time.time() - t_start:6.0f} s] {s}", flush=True)
    log(f"generator_schleife {os.path.basename(od)}: {len(raum.opt)} freie Parameter (Raum aus {raum.quelle}), {len(raum.gesperrt)} fest/gesperrt, {len(fotos)} Suchfotos (von {len(alle)} kalibrierten), {len(val)} Validierungsfotos, Population {pop}")
    for i, r in enumerate(raum.opt): log(f"   {raum.name(i):34s} [{r['lo']:+.3f} .. {r['hi']:+.3f}] Schritt {r['schritt']:.4f} Start {raum.x_start[i]:+.4f}")
    for k, w in raum.gesperrt: log(f"   {k:34s} NICHT optimiert: {w}")
    bew = Bewerter(objp, obj, raum, fotos + val, a, aus)
    pf = open(os.path.join(aus, "protokoll.jsonl"), "a")
    P = lambda d: (pf.write(json.dumps(d, ensure_ascii=False, default=float) + "\n"), pf.flush())

    # --- Start: bauen, messen (erzeugt die feste Bewertungsmaske)
    bp0 = raum.bp(raum.x_start); h0 = bew.hash(bp0)
    E0 = bew.messen([(h0, bp0)], fotos + val, mit_maske=True, karten=False)[h0]
    if E0.get("fehler") or sum(1 for nr in fotos if nr in E0["je_foto"]) < MIN_ANTEIL_FOTOS * len(fotos):
        raise SystemExit(f"Startvektor nicht bewertbar: {E0.get('fehler') or E0.get('fotofehler')}")
    ref = {nr: E0["je_foto"].get(nr, 0.0) for nr in fotos}; ziel = Ziel(a, fotos, ref)
    # Elementbuch nur, wenn der Bau Geometrieelemente traegt
    try: el0, _ = EB.elemente_laden(E0["elemente"]) if E0.get("elemente") else ({}, [])
    except Exception: el0 = {}
    bew.karten = bool(el0)
    if bew.karten:
        E0 = bew.messen([(h0, bp0)], fotos, karten=True)[h0]
    J0, k0 = ziel.J(E0); acc = dict(h=h0, v=raum.x_start.copy(), J=J0, E=E0)
    log(f"START J = {J0:+.5f}  Mittel kosten_{a.mass} = {np.mean(list(k0.values())):+.5f} (Suchfotos), Mittel rot+gelb = {np.mean([sum(E0['rg'][nr]) for nr in fotos if nr in E0['rg']]):.4f}; Elementbuch {'an' if bew.karten else 'aus (keine Geometrieelemente)'}")
    P(dict(art="start", J=J0, vektor={raum.name(i): float(x) for i, x in enumerate(raum.x_start)}, kosten_je_foto=k0, fotos=fotos, validierung=val, sekunden=round(time.time() - t_start)))
    verlauf_J = [J0]; protokoll_runde = 0; ende_grund = {}; start_ergebnisse = []

    def budget_aus():
        if time.time() - t_start > budget_s: return f"Zeitbudget {a.minuten} min"
        if bew.n_ausw >= a.max_ausw: return f"Auswertungsbudget {a.max_ausw}"
        return None

    rng = np.random.default_rng(a.seed); n = len(raum.opt); gen_dauer = 0.0
    for s in range(a.starts):
        if budget_aus(): ende_grund[f"start{s}"] = budget_aus(); break
        x0u = raum.norm(raum.x_start) if s == 0 else rng.uniform(0.05, 0.95, n)
        opt = optimierer(a.verfahren, x0u, a.sigma if s == 0 else max(a.sigma, 0.3), a.seed + s, n, pop)
        best_s = (J0 if s == 0 else None, raum.x_start.copy() if s == 0 else None); ohne = 0; gen = 0; grund = None
        log(f"--- Start {s} ({'Basis = Objektstand' if s == 0 else 'zufaellig'}; {type(opt).__name__}) ---")
        while True:
            if (g := budget_aus()): grund = g; break
            if gen_dauer and time.time() - t_start + 0.9 * gen_dauer > budget_s: grund = f"Zeitbudget {a.minuten} min (naechste Generation passt nicht mehr)"; break
            if gen >= a.max_generationen: grund = "max Generationen"; break
            if opt.stop(): grund = "Optimierer-Kriterium (konvergiert)"; break
            tg = time.time(); X = opt.ask(); V = [raum.quant(raum.denorm(u)) for u in X]; Xq = [raum.norm(v) for v in V]
            items = []; hs = []
            for v in V:
                bp = raum.bp(v); h = bew.hash(bp); hs.append(h)
                if h not in dict(items): items.append((h, bp))
            gesehen = bew.n_treffer
            Es = bew.messen(items, fotos, karten=bew.karten)
            Js, Ks = zip(*[ziel.J(Es[h]) for h in hs])
            try: opt.tell(Xq, list(Js))
            except Exception as ex: log(f"  Optimierer tell: {ex}"); grund = f"Optimierer-Fehler {ex}"; break
            gen += 1; protokoll_runde += 1; gen_dauer = time.time() - tg
            order = np.argsort(Js); jb = Js[order[0]]; hb = hs[order[0]]
            if best_s[0] is None or jb < best_s[0] - a.eps: best_s = (jb, V[order[0]].copy()); ohne = 0
            else: ohne += 1
            entsch = "keine Verbesserung gegen akzeptierten Stand"; gruende = []; tor_det = None; probiert = []
            for oi in order[: a.tor_versuche]:
                if Js[oi] >= J_UNGUELTIG or Js[oi] >= acc["J"] - a.eps: break
                c = Es[hs[oi]]
                if bew.karten and not c.get("karten_da"): c = bew.messen([(hs[oi], c["bp"])], fotos, karten=True)[hs[oi]]
                ok, gr, det = tor(c, acc["E"], fotos, a, bew, ziel); probiert.append(dict(h=hs[oi], J=float(Js[oi]), ok=ok, gruende=gr, detail=det))
                if ok:
                    if acc["h"] != hs[oi]: bew.aufraeumen(acc["h"])
                    acc = dict(h=hs[oi], v=V[oi].copy(), J=float(Js[oi]), E=c); entsch = "ANGENOMMEN"; tor_det = det; break
                gruende += gr
            if entsch != "ANGENOMMEN" and probiert: entsch = "ABGELEHNT (Tor)"
            if entsch == "ANGENOMMEN" and acc["J"] > verlauf_J[-1] + 1e-12: log("  FEHLER: Gesamtkennzahl steigt!")
            if entsch == "ANGENOMMEN": verlauf_J.append(acc["J"])
            # Overlays des besten Kandidaten dieser Generation (und, falls angenommen, des neuen Stands)
            rd = os.path.join(aus, f"runde_{protokoll_runde:02d}")
            if os.path.exists(os.path.join(bew.ev, hb, fotos_ov[0] if fotos_ov else "", f"foto_diff_{fotos_ov[0]}.jpg")): overlays(bew, hb, fotos_ov, rd, f"J {Js[order[0]]:+.4f} {entsch[:9]}")
            for h in set(hs) | {h0, acc["h"]}: bew.aufraeumen(h, behalten_karten=(h == acc["h"] and bew.karten))     # Platz: Bilder weg, Karten nur fuer den akzeptierten Stand
            vec = {raum.name(i): float(V[order[0]][i]) for i in range(n)}
            P(dict(art="generation", runde=protokoll_runde, start=s, gen=gen, n_vektoren=len(set(hs)), cache_treffer=bew.n_treffer - gesehen, bester=dict(vektor=vec, J=float(Js[order[0]]), kosten_je_foto=Ks[order[0]]),
                   J_schlechtester=float(max(Js)), akzeptiert_J=acc["J"], akzeptiert_vektor={raum.name(i): float(acc["v"][i]) for i in range(n)}, entscheidung=entsch, tor=probiert, dauer_s=round(time.time() - tg, 1),
                   auswertungen_gesamt=bew.n_ausw, sekunden=round(time.time() - t_start)))
            log(f"  Gen {gen} (Runde {protokoll_runde}): bestes J {Js[order[0]]:+.5f} (akzeptiert {acc['J']:+.5f}), {entsch}{' - ' + gruende[0][:110] if gruende else ''}  [{time.time() - tg:.0f} s, {bew.n_ausw} Ausw.]")
            if ohne >= a.geduld: grund = f"konvergiert: bestes J {a.geduld} Generationen ohne Verbesserung > {a.eps}"; break
        ende_grund[f"start{s}"] = grund; xb = opt.best()
        vb = raum.quant(raum.denorm(xb)) if best_s[1] is None else best_s[1]
        start_ergebnisse.append(dict(start=s, J=None if best_s[0] is None else float(best_s[0]), vektor=[float(x) for x in vb], generationen=gen, grund=grund))
        log(f"--- Start {s} Ende: {grund}; bester Vektor J {best_s[0]}")

    # --- Abschluss: Validierung vorher/nachher, Parametertabelle, Mehrfachstart-Bewertung je Parameter
    bpA = raum.bp(acc["v"]); hA = bew.hash(bpA); alle_f = fotos + val
    Ee = bew.messen([(h0, bp0), (hA, bpA)], alle_f, karten=False)
    fl = lambda E, L: float(np.mean([E["je_foto"][nr] for nr in L if nr in E["je_foto"]])) if any(nr in E["je_foto"] for nr in L) else None
    rgm = lambda E, L: float(np.mean([sum(E["rg"][nr]) for nr in L if nr in E["rg"]])) if any(nr in E["rg"] for nr in L) else None
    vn = dict(suche=dict(vorher=fl(Ee[h0], fotos), nachher=fl(Ee[hA], fotos), rg_vorher=rgm(Ee[h0], fotos), rg_nachher=rgm(Ee[hA], fotos), n=len(fotos)))
    if val: vn["validierung"] = dict(vorher=fl(Ee[h0], val), nachher=fl(Ee[hA], val), rg_vorher=rgm(Ee[h0], val), rg_nachher=rgm(Ee[hA], val), n=len(val))
    je_foto_vn = {nr: [Ee[h0]["je_foto"].get(nr), Ee[hA]["je_foto"].get(nr)] for nr in alle_f}
    tab = {}
    SV = np.array([e["vektor"] for e in start_ergebnisse if e["J"] is not None]) if start_ergebnisse else np.zeros((0, n))
    for i, r in enumerate(raum.opt):
        sd = float(SV[:, i].std()) if len(SV) > 1 else None; spanne = r["hi"] - r["lo"]
        urteil = "nur ein Start" if sd is None else ("von den Fotos bestimmt (Streuung der Starts <= 5 % der Spanne)" if sd <= 0.05 * spanne else "NICHT identifizierbar (Starts streuen > 5 % der Spanne; ANNAHME Schwelle)")
        tab[raum.name(i)] = dict(start=float(raum.x_start[i]), ergebnis=float(acc["v"][i]), bewegt=bool(abs(acc["v"][i] - raum.x_start[i]) > 1e-9), lo=r["lo"], hi=r["hi"], schritt=r["schritt"],
                                 am_rand=bool(abs(acc["v"][i] - r["lo"]) < 1e-9 or abs(acc["v"][i] - r["hi"]) < 1e-9), enden_der_starts=[float(x) for x in SV[:, i]], streuung_starts=sd, urteil=urteil)
    erg = dict(objekt=objp, aus=aus, parameter=tab, fest={b: {p: v for p, v in ps.items()} for b, ps in raum.fest.items()}, gesperrt=raum.gesperrt, parameterraum_quelle=raum.quelle,
               J_start=J0, J_ende=acc["J"], J_verlauf_akzeptiert=verlauf_J, monoton=all(b <= a_ + 1e-12 for a_, b in zip(verlauf_J, verlauf_J[1:])), vorher_nachher=vn, kosten_je_foto_vorher_nachher=je_foto_vn, mass=a.mass,
               ende_gruende=ende_grund, starts=start_ergebnisse, bauteil_param_bester={b: {k: v for k, v in ps.items()} for b, ps in raum.bp(acc["v"]).items()},
               auswertungen=bew.n_ausw, cache_treffer=bew.n_treffer, fotos_suche=fotos, fotos_validierung=val, dauer_s=round(time.time() - t_start), argumente=vars(a), schwellen_annahmen=dict(mindestanteil_fotos=MIN_ANTEIL_FOTOS, identifizierbar_streuung_spanne=0.05))
    json.dump(erg, open(os.path.join(aus, "ergebnis.json"), "w"), indent=1, ensure_ascii=False, default=float)
    # Abschluss-Overlays des Ergebnisses (Suchfotos) ueber vorhandene Auswertung nur wenn Bilder noch da; sonst eine kurze Neumessung mit Bildern
    try:
        alt_ = bew.cache.pop(hA, None); bew.messen([(hA, bpA)], fotos_ov, karten=False, schreiben=False); bew.cache[hA] = alt_
        overlays(bew, hA, fotos_ov, os.path.join(aus, "runde_ergebnis"), "Ergebnis")
    except Exception as ex: log(f"Abschluss-Overlay: {ex}")
    log(f"ENDE: J {J0:+.5f} -> {acc['J']:+.5f}; {bew.n_ausw} Auswertungen ({bew.n_treffer} Cache-Treffer); {', '.join(f'{k}: {v}' for k, v in ende_grund.items())}")
    for k, d in tab.items(): log(f"   {k:34s} {d['start']:+.4f} -> {d['ergebnis']:+.4f}{' (am Rand)' if d['am_rand'] else ''}; {d['urteil']}")
    log(f"   kosten_{a.mass} Suchfotos {vn['suche']['vorher']:+.5f} -> {vn['suche']['nachher']:+.5f}" + (f"; Validierung {vn['validierung']['vorher']:+.5f} -> {vn['validierung']['nachher']:+.5f}" if val else ""))
    if bew.pool: bew.pool.close(); bew.pool.join()
    shutil.rmtree(PS.PUNKTE_DIR, ignore_errors=True)
    if a.uebernehmen:
        if hA == h0: log("--uebernehmen: nichts geaendert (Stand = Start)")
        else: uebernehmen(objp, raum, acc["v"], erg, log)
    return erg


def uebernehmen(objp, raum, v, erg, log):
    """Schreibt NUR die geaenderten Parameter mit quelle + historie in objekt.json['bauteile'] (Regel: Sollwerte nur mit Quelle)."""
    obj = json.load(open(objp)); heute = datetime.date.today().isoformat(); n_ = 0
    for i, r in enumerate(raum.opt):
        if abs(v[i] - raum.x_start[i]) < 1e-9: continue
        sp = next((s for s in obj.get("bauteile") or [] if s.get("typ") == r["bauteil"]), None)
        if sp is None: log(f"  uebernehmen: Bauteil {r['bauteil']} nicht in objekt.json - uebersprungen"); continue
        alt = sp.get(r["param"]); sp[r["param"]] = int(v[i]) if r["typ"] == "int" else float(v[i])
        sp["quelle"] = f"generator_schleife.py {heute} ({erg['aus']}): {r['param']} {alt} -> {sp[r['param']]} aus kosten_{erg['mass']} ueber {erg['vorher_nachher']['suche']['n']} Fotos (J {erg['J_start']:+.5f} -> {erg['J_ende']:+.5f}, Tor)"
        sp.setdefault("historie", []).append(dict(datum=heute, param=r["param"], vorher=alt, nachher=sp[r["param"]], quelle="generator_schleife.py", lauf=erg["aus"])); n_ += 1
    json.dump(obj, open(objp, "w"), indent=1, ensure_ascii=False); log(f"--uebernehmen: {n_} Parameter in {objp} geschrieben")


if __name__ == "__main__":
    main()

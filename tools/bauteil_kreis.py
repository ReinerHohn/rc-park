#!/usr/bin/env python3
"""bauteil_kreis.py - der Konvergenz-Kreis OHNE Koordinator (Nutzer 9.11.: "Das soll die Pipeline doch bitte selbst machen").

Je Runde:
  1. MESSEN   konvergenz_bericht.py auf dem aktuellen Stand (Wolkenbeleg je Bauteil, Kanten je Hoehenband, Pruefstand).
  2. WAEHLEN  schlechtestes Bauteil: kleinster Wolkenbeleg mit genug Daten (anteil_mit_daten >= --min_daten),
              nicht auf der Sperrliste (zu oft ohne Gewinn versucht). Der Befundtext entsteht aus den Messwerten, nicht von Hand.
  3. AUFTRAG  Auftragstext aus modelle/VORLAGE_BAUTEIL_RUNDE.md (Abschnitt "Auftragstext"), Platzhalter automatisch gefuellt.
  4. BAUEN    `claude -p` (Arbeitsmodell, Standard sonnet) im eigenen git-Worktree auf der Datenplatte, Branch kreis/<objekt>/<lauf>-r<N>.
  5. PRUEFEN  im Worktree: bauen_abnehmen.sh, Bauteile exportieren (BAUTEILE_AUS), konvergenz_bericht.py (Exit 3 = Rueckschritt),
              Zielteil-Gewinn >= --min_gewinn, dann Pruefer-Modell (`claude -p`, Standard opus) nach der Prueferliste der Vorlage
              (Bericht + Overlays ansehen, JSON-Urteil).
  6. ENTSCHEIDEN  alle drei Tore gruen -> Commit auf dem Kreis-Branch (main bleibt unberuehrt; Uebernahme nach main = Mensch/Koordinator per Merge).
              sonst -> Diff als Patch archivieren, Worktree verwerfen, Bauteil-Fehlversuch zaehlen (Sperre nach --max_fehl).
  Abbruch: --runden erreicht, kein Kandidat mehr, oder 2 Runden in Folge ohne Annahme.
Alles wird in <kreisdir>/<lauf>/kreis.jsonl protokolliert (je Runde Ziel, Auftrag, Logs, Tore, Entscheidung, Kennzahlen vorher/nachher).

Aufruf:
  python3 tools/bauteil_kreis.py <objekt> --trocken                 # nur Schritt 1-3: zeigt Ziel und Auftrag, startet nichts
  python3 tools/bauteil_kreis.py <objekt> --rechte <MODUS> [--runden 3] [--modell sonnet] [--pruefer opus] [--nach_main]
       --nach_main: angenommene Runde sofort nach main mergen (Nutzerentscheid 9.11., revertierbar); Konflikt -> bleibt auf dem Kreis-Branch
       --rechte: Rechte-Modus fuer die unbeaufsichtigten Sitzungen (z.B. acceptEdits oder bypassPermissions). Pflicht, kein Standard:
                 die Wahl trifft der Nutzer (unbeaufsichtigtes Schreiben + Bash im Worktree).
  Lange Laeufe ueber tools/job_start.sh starten (Nachtlauf).
Konfiguration aus objekt.json "kreis" (alles optional): {"stl": ..., "skala": 0.087, "gitter": ..., "wolke": ..., "tabu": [...]}
Grenzen (ehrlich): Wolkenbeleg ist noch kein bewiesenes Gate (Hinweis-Kennzahl, L22); Bauteile ohne Wolkendaten (Rueckseiten, Dach > Wolke)
waehlt der Kreis nie. Teile-Sichtpruefung fliesst ein, sobald ihre Ausgabe 'gate_bewiesen' traegt.
"""
import glob, sys, os, json, time, subprocess, shutil, re
sys.stdout.reconfigure(line_buffering=True)   # systemd-Log sofort lesbar

a = sys.argv
def opt(k, d=None, t=str):
    return t(a[a.index(k) + 1]) if k in a else d

if len(a) < 2 or a[1].startswith("-"):
    print(__doc__); sys.exit(1)
OBJ = a[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/media/oem/scan/venv-seg/bin/python"
TROCKEN = "--trocken" in a
RECHTE = opt("--rechte")
RUNDEN = opt("--runden", 3, int); MODELL = opt("--modell", "sonnet"); PRUEFER = opt("--pruefer", "opus")
MIN_DATEN = opt("--min_daten", 0.3, float); MIN_GEWINN = opt("--min_gewinn", 0.05, float); MAX_FEHL = opt("--max_fehl", 2, int)
KREISDIR = opt("--kreisdir", "/media/oem/scan/rc-park_kreis")
MAX_MIN = opt("--max_minuten", 120, int)
VORPRUEF = "--ohne_vorpruefung" not in a   # Form am Foto direkt nach dem Agenten, einmal Rueckgabe (10.11.)
if not TROCKEN and not RECHTE:
    print("--rechte <MODUS> ist Pflicht fuer echte Laeufe (Nutzerentscheid). Ohne Start: --trocken."); sys.exit(1)

ojs = json.load(open(os.path.join(ROOT, "modelle", OBJ, "objekt.json")))
K = ojs.get("kreis", {})
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"
STL = K.get("stl", f"modelle/stl/{OBJ}_1-87.stl"); SK = K.get("skala", 0.087)
GIT = K.get("gitter", D + "/segmente_gitter_v12.json")
KAM = K.get("kameras", D + "/sfm/kam_lot2.json")   # L-KR4: Wolkenbeleg nur auf kamera-zugewandter Flaeche
WOLKE = K.get("wolke", "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy")
TABU = K.get("tabu", [])
LAUF = time.strftime("%Y%m%d_%H%M%S") + opt("--spur", "")
LDIR = os.path.join(KREISDIR, OBJ, LAUF); os.makedirs(LDIR, exist_ok=True)
PROT = os.path.join(LDIR, "kreis.jsonl")

def sh(cmd, cwd, log=None, env=None, timeout=None):
    e = dict(os.environ); e.update(env or {})
    e.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")   # mehrere Spuren teilen 8 GB VRAM (OOM 10.11. 00:25)
    e.setdefault("RCPARK_SIFT_MAX", "1600")
    with open(log, "a") if log else open(os.devnull, "w") as f:
        r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), stdout=f if log else subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, env=e, timeout=timeout)
    return r.returncode, (r.stdout if not log else open(log).read()[-4000:])

OOM_MUSTER = ("out of memory", "CUDA_ERROR_OUT_OF_MEMORY", "OutOfMemoryError", "PLATZ ZU KNAPP")   # Platzwaechter-Abbruch = Infrastruktur (s2 R1 10.11., Gewinn +0,224 verworfen)

def sh_cpu(cmd, cwd, log, env=None):
    """Reiner CPU-Schritt (Generatorbau, manifold - kein torch/cuda): ohne GPU-Torsperre. 10.11.: unter der Sperre wartete jeder Export auf
    alle Messungen der anderen Spuren (Export allein 4 min, in der Schlange bis 23 min). Ergebnis deterministisch -> verlustfrei."""
    t = time.time(); rc, out = sh(cmd, cwd, log=log, env=env)
    print(f"  CPU-Schritt {os.path.basename(log)}: {time.time() - t:.0f} s", flush=True); return rc, out

def sh_tor(cmd, cwd, log, env=None, versuche=6, pause=300):
    """Torschritt (Bau/Abnahme/Messung): Spuren-uebergreifend per flock serialisiert (deterministische Messung -> verlustfrei)
    und bei CUDA-OOM wiederholt. Ein OOM ist ein Infrastrukturfehler, kein rotes Tor (Kreis1 R1 10.11.: Abnahme 'rot' war OOM in wandstaerke)."""
    import fcntl
    rc, out = 1, ""
    for v in range(versuche):
        start = os.path.getsize(log) if os.path.exists(log) else 0
        with open(os.path.join(KREISDIR, "gpu_tor.lock"), "w") as lk:
            tw = time.time(); fcntl.flock(lk, fcntl.LOCK_EX); tl = time.time()
            rc, _ = sh(cmd, cwd, log=log, env=env)
            print(f"  Torschritt {os.path.basename(log)}: Warten {tl - tw:.0f} s, Lauf {time.time() - tl:.0f} s", flush=True)
        with open(log, errors="replace") as f: f.seek(start); neu = f.read()
        out = neu   # ganzer neuer Logteil: "alle Pruefungen bestanden" steht mitten im Abnahme-Log (danach Sichtblatt, fehlteile, test_regeln_cb) - mit [-4000:] nie gefunden
        if not any(m in neu for m in OOM_MUSTER): return rc, out
        print(f"  OOM im Torschritt ({os.path.basename(log)}), Versuch {v + 1}/{versuche}, warte bis 2,5 GB VRAM frei (hoechstens {pause} s)", flush=True)
        t_ = time.time()   # 10.11.: fest 300 s je OOM (7 OOM heute = 35 min Leerlauf); jetzt sobald Speicher frei ist, Ergebnis gleich
        while time.time() - t_ < pause:
            time.sleep(15)
            try:
                fr = float(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0])
                if fr >= 2500 and time.time() - t_ >= 30: break
            except Exception: pass
    return rc, out + "\nINFRA_OOM"

def protokoll(z):
    z["zeit"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(PROT, "a") as f: f.write(json.dumps(z, ensure_ascii=False) + "\n")

def messen(wt, tag, regionen=None, vorab=False):
    """Bauteile exportieren (baut neu) und Konvergenz messen; liefert (exitcode, letzte konvergenz-zeile).
    regionen: JSON-Datei [{id, lo, hi}] -> Recall der Fotokanten je Kasten (Zielart Fehlteil)."""
    tdir = os.path.join(LDIR, f"teile_{tag}"); os.makedirs(tdir, exist_ok=True)
    gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
    if not (vorab and glob.glob(os.path.join(tdir, "*.stl"))):   # vorab: Teile kamen schon aus dem Bau der Abnahme (gleicher Stand)
        rc, _ = sh_cpu(gen, wt, log=os.path.join(LDIR, f"export_{tag}.log"), env={"BAUTEILE_AUS": tdir})
    rc2, out = sh_tor([PY, "-W", "ignore", "-I", "tools/konvergenz_bericht.py", OBJ, "--stl", STL, "--skala", str(SK), "--gitter", GIT,
                   "--wolke", WOLKE, "--teile_dir", tdir, "--kameras", KAM, "--etikett", f"kreis {LAUF} {tag}"] + (["--regionen", regionen] if regionen else []) + (["--trocken"] if TROCKEN else []),
                  wt, log=os.path.join(LDIR, f"konvergenz_{tag}.log"))
    kf = os.path.join(wt, "modelle", OBJ, "konvergenz.jsonl")
    z = json.loads([l for l in open(kf) if l.strip()][-1]) if (os.path.exists(kf) and not TROCKEN) else None
    return rc2, z, out

BELEGT = os.path.join(KREISDIR, OBJ, "belegt"); os.makedirs(BELEGT, exist_ok=True)   # Spuren parallel: je Bauteil eine Sperrdatei

def f1(t):
    p, r = t.get("kanten_praez"), t.get("kanten_recall")
    return None if p is None or r is None else (2 * p * r / (p + r) if p + r > 0 else 0.0)

def guete(t):
    """Teilguete = Mittel aus Wolkenbeleg (Lage, nur kamera-zugewandte Flaeche) und Fotokanten-F1 (Form). 10.11.: Beleg allein war
    bei ~0,6 ausgereizt und erschleichbar; Beweis Figuren +0,27 / Laube-Trick +0,01. Ohne Kantenwerte: Beleg allein (alte Messungen)."""
    b, k = t.get("beleg"), f1(t)
    return None if b is None else (b if k is None else (b + k) / 2)

def fehlversuche_global():
    """Verworfene Runden je Teil ueber ALLE Laeufe/Spuren (ohne Infrastrukturfehler). Spuren-lokale 'sperre' reichte nicht:
    jede neue Spur nahm wieder dieselben aussichtslosen Teile (10.11.: Erker/Dach/Boegen mehrfach mit Gewinn ~0)."""
    ev = []
    for d in glob.glob(os.path.join(KREISDIR, OBJ, "*", "kreis.jsonl")):
        lauf = os.path.basename(os.path.dirname(d))
        for l in open(d):
            try: z = json.loads(l)
            except Exception: continue
            if (z.get("ziel") or {}).get("teil"): ev.append((z.get("zeit", ""), lauf, z))
    ev.sort(key=lambda e: e[0])   # zeitlich ueber alle Spuren, damit eine Annahme spaetere Zaehlung zuruecksetzt
    boxen = teil_boxen(); n = {}
    for _, lauf, z in ev:
        t = z["ziel"]["teil"]
        if z["ziel"].get("art") == "beobachtung": t = beob_schluessel(z["ziel"].get("beob") or {})   # eigene Zaehlung je Beobachtung (neue Information, z. B. Nutzer-Sichtfund)
        if z.get("angenommen") is False and not z.get("infra_oom") and "guete_vor_nach" in z: n[t] = n.get(t, 0) + 1   # nur Runden mit dem heutigen Tor (Guete) zaehlen
        if z.get("angenommen") is True:
            n[t] = 0
            # Nutzerentscheid 10.11.: gesperrte Teile werden wieder frei, wenn ein Nachbarteil (Box +-1 m) danach in main geaendert wurde (neue Lage)
            if not nicht_in_main(z, lauf, z.get("runde")):
                for u in [u for u in n if n[u] and u != t and nah(boxen, u, t)]: n[u] = 0
    return n

NACHBAR = 1000 / 87 * 1.0   # 1 m in Teil-STL-Einheiten (mm im Massstab 1:87)
def stl_box(f):
    import struct, numpy as np
    d = open(f, "rb").read(); k = struct.unpack("<I", d[80:84])[0]
    a = np.frombuffer(d[84:84 + 50 * k], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    v = a["v"].reshape(-1, 3); return v.min(0), v.max(0)
def teil_boxen():
    """Achsenbox je Teil aus den neuesten Teil-Exporten der Spuren (teile_*/<teil>.stl)."""
    b = {}
    for d in sorted(glob.glob(os.path.join(KREISDIR, OBJ, "*", "teile_*")), key=os.path.getmtime, reverse=True)[:12]:
        for f in glob.glob(os.path.join(d, "*.stl")):
            t = os.path.basename(f)[:-4]
            if t not in b:
                try: b[t] = stl_box(f)
                except Exception: pass
    return b
def nah(boxen, a, c):
    if a not in boxen or c not in boxen: return False
    (alo, ahi), (clo, chi) = boxen[a], boxen[c]
    return bool((alo - NACHBAR <= chi).all() and (clo - NACHBAR <= ahi).all())

def beob_schluessel(b): return "beob:" + str(b.get("merkmal") or b.get("text", "")[:60])

def beob_ziele(z):
    """Zielart Beobachtung (Nutzerentscheid 10.11.): offene Beobachtung der Masstabelle (main) mit Feld 'teil' wird Kreisziel, auch wenn das Teil
    unter MIN_DATEN liegt (Rumpf 0,17-0,20 nach Verdeckungspruefung -> 'Ostwand 1,3 m zu lang' war nie waehlbar). Tor unveraendert."""
    try: B = json.load(open(os.path.join(ROOT, "modelle", OBJ, "masstabelle.json"))).get("beobachtungen_offen") or []
    except Exception: return []
    teile = {t["teil"]: t for t in (z or {}).get("wolkenbeleg_teile") or [] if t.get("beleg") is not None}
    out = []
    for b in B:
        if not isinstance(b, dict) or not b.get("teil") or b.get("erledigt"): continue
        tt = str(b["teil"]).replace(":", "__")
        if tt in teile: out.append(dict(teile[tt], art="beobachtung", beob=b))
    return out

MAX_GLOBAL = int(opt("--max_global", 3))
SICHT = "verdeckung_strahl"   # Messart der Sichtpruefung in konvergenz_bericht; Vorher-Zeilen anderer Messart nie wiederverwenden (L-KR17)
# Zielart Fehlteil (10.11.): Fotokanten-Cluster ohne Modellflaeche (konvergenz_bericht Abschnitt 8) = fehlendes Element
# (Ost-Staffelgiebel, Dachgitter, Pfeiler-Daechlein wurden nie Ziel, weil der Kreis nur vorhandene Teile verbessert).
FEHL_PKT = opt("--fehl_pkt", 300, int); FEHL_RECALL_MAX = opt("--fehl_recall_max", 0.5, float)
MIN_REGION = opt("--min_region", 0.25, float); MIN_PRAEZ_NEU = opt("--min_praez_neu", 0.25, float)

def ist_fehlteil(ziel): return (ziel or {}).get("art") == "fehlteil"

# Fehlteil-Befunde der Agenten (10.11.: dieselben Kaesten wurden 2-3x vergeben, obwohl der Agent 'kein Bauteil'/'Gitter zu duenn' belegt hatte)
ERLEDIGT = os.path.join(KREISDIR, OBJ, "fehlteil_erledigt.json")
def erledigt_laden():
    try: return json.load(open(ERLEDIGT))
    except Exception: return {}
def ist_erledigt(f, erl):
    """Kasten gilt als erledigt, wenn sein Zentrum in einem erledigten Kasten +-0,5 m liegt (Cluster-IDs wandern leicht zwischen Messungen)."""
    c = f["zentrum"]
    return any(all(e["lo"][i] - 0.5 <= c[i] <= e["hi"][i] + 0.5 for i in range(3)) for e in erl.values())
BEFUND_RE = re.compile(r"FEHLTEIL-BEFUND:\s*(gebaut|kein Bauteil|Gitter zu duenn|vorhandenes Teil\s+\S+)", re.I)

# Formpruefung am Foto je Teil (teil_fotoform, L-KR24/L-KR25): Gauben/Balkon/Erker-Rippen waren falsch bei Guete 0,8-0,98, weil Wolke und
# Kantengitter (Toleranz 0,35 m, an Gauben 0 Punkte) Relief und Teilung nicht sehen. Formliste vom Regler (fotoform_auffrischen.sh) je main-STL.
FORMDIR = os.path.join(KREISDIR, OBJ, "fotoform")
def formliste():
    fs = sorted(glob.glob(os.path.join(FORMDIR, "*.json")), key=os.path.getmtime)
    try: return json.load(open(fs[-1])) if fs else {}
    except Exception: return {}
def form_g(fl, teil): return (((fl.get("teile") or {}).get(teil) or {}).get("_gesamt") or {})
def form_fotos(fl, teil, n=10):
    je = {k: v for k, v in ((fl.get("teile") or {}).get(teil) or {}).items() if k != "_gesamt"}
    return sorted(je, key=lambda k: -(je[k]["mk_px"] + je[k]["fk_px"]))[:n]
def form_messen(wt, tdir, teil, fotos, tag):
    """Foto-F1 eines Teils (nur dieses Teil, Verdeckung gegen das ganze Modell) auf den Fotos der Formliste; None = nicht messbar."""
    if not fotos or not os.path.isdir(tdir): return None
    aus = os.path.join(LDIR, f"fotoform_{tag}.json")
    sh_tor([PY, "-W", "ignore", "-I", "tools/teil_fotoform.py", OBJ, "--teile_dir", tdir, "--stl", STL, "--nur", teil, "--fotos", ",".join(fotos),
            "--aus", aus, "--bilder", "--bilder_dir", os.path.join(LDIR, "fotoform_bilder"), "--etikett", tag], wt, log=os.path.join(LDIR, f"fotoform_{tag}.log"))
    try: return ((json.load(open(aus))["teile"].get(teil) or {}).get("_gesamt") or {}).get("f1")
    except Exception: return None
def form_aus_liste(fl, wt, teil, fotos, runde):
    """Vorher-F1 aus der Formliste, wenn sie zum STL des Basisstands passt (10.11.: jede Spur mass sonst 35 min dasselbe - Generator-Export
    + 10 Fotos, bei 8 Spuren parallel). Gleiche Formel wie teil_fotoform (_gesamt, pixelgewichtet) auf den gewaehlten Fotos; Vorher-Bilder verlinkt."""
    import hashlib
    try: sha = hashlib.sha256(open(os.path.join(wt, STL), "rb").read()).hexdigest()[:16]
    except OSError: return None
    je = ((fl.get("teile") or {}).get(teil) or {})
    if fl.get("stl_sha") != sha or any(f not in je for f in fotos): return None
    mk = sum(je[f]["mk_px"] for f in fotos); fk = sum(je[f]["fk_px"] for f in fotos)
    if mk <= 0 or fk <= 0: return None
    p = sum(je[f]["praez"] * je[f]["mk_px"] for f in fotos) / mk; r = sum(je[f]["recall"] * je[f]["fk_px"] for f in fotos) / fk
    bd = os.path.join(LDIR, "fotoform_bilder"); os.makedirs(bd, exist_ok=True)
    for f in fotos:
        q = os.path.join(fl.get("bilder_dir", ""), f"{teil}_{f}.jpg"); z = os.path.join(bd, f"{teil}_{f}_r{runde}_vorher.jpg")
        if os.path.exists(q) and not os.path.exists(z): os.symlink(q, z)
    return round(2 * p * r / (p + r), 3) if p + r else 0.0
def guete_form(t, ff):
    """Teilguete mit Formpruefung am Foto: Mittel aus Wolkenbeleg, Gitter-Kanten-F1 (falls Gitter) und Foto-F1 (falls messbar)."""
    c = [x for x in (t.get("beleg"), f1(t), ff) if x is not None]
    return sum(c) / len(c) if c else None

def waehlen(z, sperre):
    fg = fehlversuche_global()
    belegt_fam = {f.split("__")[0] for f in os.listdir(BELEGT)}
    # zuerst fehlende Elemente (groesster sichtbarer Fehler), groesster Cluster zuerst
    fk = [dict(f, teil=f["id"] + "__neu", art="fehlteil", beleg=None) for f in (z or {}).get("fehlkanten") or []
          if f["pkt"] >= FEHL_PKT and (f.get("recall_kasten") is not None and f["recall_kasten"] <= FEHL_RECALL_MAX)]
    erl = erledigt_laden()
    fk = [f for f in fk if sperre.get(f["teil"], 0) < MAX_FEHL and fg.get(f["teil"], 0) < MAX_GLOBAL and f["id"] not in belegt_fam and not ist_erledigt(f, erl)]
    fk.sort(key=lambda f: -f["pkt"])
    for t in fk:
        try:
            fd = os.open(os.path.join(BELEGT, t["teil"]), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, f"{LAUF} {os.getpid()}".encode()); os.close(fd)
            return t
        except FileExistsError:
            continue
    fl = formliste()
    kand = [t for t in (z or {}).get("wolkenbeleg_teile") or [] if t["beleg"] is not None and (t["anteil_mit_daten"] >= MIN_DATEN or form_g(fl, t["teil"]).get("f1") is not None)
            and sperre.get(t["teil"], 0) < MAX_FEHL and fg.get(t["teil"], 0) < MAX_GLOBAL and not os.path.exists(os.path.join(BELEGT, t["teil"]))
            and t["teil"].split("__")[0] not in belegt_fam]   # gleiche Formfamilie (gleicher Generatorcode) nie parallel
    kand.sort(key=lambda t: min(x for x in (guete(t), form_g(fl, t["teil"]).get("f1")) if x is not None))   # schwaechste Groesse zuerst: Form am Foto zaehlt mit
    # Nutzerregel 10.11. 14:4x: IMMER das schwaechste Teil zuerst ("dann konvergieren wir"). Frueher gingen offene Beobachtungen vor -
    # 7/7 Runden landeten auf Teilen mit 0,94-0,98 (kaum Spielraum, kleine Fehler = Rueckschritt). Offene Beobachtungen zu dem gewaehlten
    # Teil reisen jetzt MIT in den Auftrag (Zielart beobachtung), bestimmen aber nicht mehr die Reihenfolge.
    bz = {}
    for b in beob_ziele(z):
        bk = beob_schluessel(b["beob"])
        if sperre.get(bk, 0) < MAX_FEHL and fg.get(bk, 0) < MAX_GLOBAL: bz.setdefault(b["teil"], b)
    for t in kand:   # atomar belegen (O_EXCL), damit zwei Spuren nie dasselbe Teil nehmen
        try:
            fd = os.open(os.path.join(BELEGT, t["teil"]), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, f"{LAUF} {os.getpid()}".encode()); os.close(fd)
            return bz.get(t["teil"], t)
        except FileExistsError:
            continue
    return None

def freigeben(teil):
    try: os.remove(os.path.join(BELEGT, teil))
    except FileNotFoundError: pass

def nicht_in_main(z, lauf, r):
    """Hinweis fuer angenommene Runden, deren Stand main nicht hat (nie gemergt: baute auf Verworfenem auf; oder per Revert zurueckgenommen, 10.11. Helm O)."""
    if not (z.get("angenommen") and z.get("branch")): return ""
    if subprocess.run(["git", "-C", ROOT, "log", "--oneline", "-1", "--grep", f"kreis {lauf} r{r}", "--grep", "Revert", "--all-match"], capture_output=True, text=True).stdout.strip():
        return " [angenommen, dann per Revert aus main ZURUECKGENOMMEN - Gruende in den Folge-Eintraegen/Commit-Text]"
    if subprocess.run(["git", "-C", ROOT, "merge-base", "--is-ancestor", z["branch"] + "^{/automatisch}", "HEAD"], capture_output=True).returncode != 0:
        return " [angenommen, aber NICHT in main (baute auf verworfenem Stand auf) - brauchbare Teile gezielt uebernehmen]"
    return ""

def vorversuche(teil):
    """Alle frueheren Kreis-Runden (alle Laeufe/Spuren) zu diesem Teil: Ergebnis, Torgruende, Agentenbericht, Patch.
    Damit wiederholt kein Agent einen verworfenen Weg blind (Kreis1 R2 10.11. startete Staffelgiebel ohne Wissen aus R1)."""
    zeilen = []
    for d in sorted(glob.glob(os.path.join(KREISDIR, OBJ, "*", "kreis.jsonl"))):
        for l in open(d):
            try: z = json.loads(l)
            except Exception: continue
            if (z.get("ziel") or {}).get("teil") != teil or "runde" not in z or z.get("angenommen") is None: continue
            ld = os.path.dirname(d); r = z["runde"]
            pa = os.path.join(ld, f"verworfen_r{r}.patch"); ag = os.path.join(ld, f"agent_r{r}.log")
            zeilen.append(f"- {os.path.basename(ld)} R{r}: angenommen={z.get('angenommen')}, Gewinn {z.get('gewinn')}, Abnahme {z.get('tor_abnahme')}"
                          f"{' (CUDA-OOM, kein Pruefungsfehler)' if z.get('infra_oom') else ''}, Pruefer {json.dumps((z.get('pruefer') or {}).get('fehlerliste'), ensure_ascii=False)[:600]}"
                          f"; Agentenbericht (Ende der Datei): {ag if os.path.exists(ag) else '-'}; Patch: {pa if os.path.exists(pa) else '-'}; Zweig (git show/diff): {z.get('branch') or '-'}"
                          + nicht_in_main(z, os.path.basename(ld), r))
    for fid, e in erledigt_laden().items():   # Fehlteil-Agent verwies auf dieses vorhandene Teil
        if e.get("befund", "").lower().startswith("vorhandenes teil") and teil.replace("__", ":") in e["befund"]:
            zeilen.append(f"- Fehlteil-Befund {fid} ({e.get('lauf')}): Fotokanten-Kasten {e['lo']} .. {e['hi']} m gehoert zu DIESEM Teil "
                          f"(Agentenbericht {e.get('agent_log')}) - dort liegt der sichtbare Fehler")
    if not zeilen: return ""
    return ("\n\nVORVERSUCHE ZU DIESEM TEIL (zuerst lesen, nicht blind wiederholen; verworfenen Patch pruefen und gezielt verbessern, "
            "offene Beobachtungen dazu in masstabelle.json beachten):\n" + "\n".join(zeilen))

def auftrag(ziel, runde, wt):
    v = open(os.path.join(ROOT, "modelle", "VORLAGE_BAUTEIL_RUNDE.md")).read()
    m = re.search(r"## Auftragstext.*?\n(.*?)\n---\n", v, re.S)
    txt = m.group(1)
    typ = ziel["teil"].replace("__", ":")
    if ist_fehlteil(ziel):
        typ = f"FEHLENDES ELEMENT bei {ziel['id']} (Zentrum {ziel['zentrum']} m, Modellrahmen)"
        befund = (f"Automatisch aus konvergenz_bericht (Abschnitt 8 Fehlkanten): Im Kasten {ziel['lo']} .. {ziel['hi']} (Modellrahmen, m) liegen "
                  f"{ziel['pkt']} Punkte des Kantengitters (Fotokanten aus mehreren Fotos), die keine Modellflaeche naeher als 0,3 m haben; "
                  f"Recall der Fotokanten im Kasten nur {ziel['recall_kasten']}. Dort fehlt sehr wahrscheinlich ein Bauteil (oder ein vorhandenes ist "
                  f"an der falschen Stelle). Stufe 0: Stelle in >= 3 Fotos finden (Kasten in die kalibrierten Fotos projizieren), Element benennen und "
                  f"Formfamilie festlegen; dann als NEUES Bauteil mit beleg()/Quelle im Generator bauen (oder vorhandenes Teil dorthin korrigieren). "
                  f"Gate: Recall im Kasten muss um >= {MIN_REGION} steigen, jedes neue Teil Kanten-Praezision >= {MIN_PRAEZ_NEU} "
                  f"(keine erfundenen Kanten), kein vorhandenes Teil darf in der Guete um > 0,02 fallen, Gesamt-Recall darf nicht sinken. "
                  f"Wenn die Fotos dort NICHTS zeigen (Gitterfehler, Hintergrund), das als Befund berichten und nichts bauen. "
                  f"PFLICHT: letzte Zeile deiner Antwort GENAU eine von 'FEHLTEIL-BEFUND: gebaut' | 'FEHLTEIL-BEFUND: kein Bauteil' | "
                  f"'FEHLTEIL-BEFUND: Gitter zu duenn' | 'FEHLTEIL-BEFUND: vorhandenes Teil <typ:name>' (z. B. staffelgiebel:west, wenn ein vorhandenes Teil "
                  f"falsch liegt/zu hoch ist und du es NICHT in dieser Runde korrigierst). Danach wird der Kasten nicht erneut vergeben.")
    else:
        befund = (f"Automatisch aus konvergenz_bericht (Wolkenbeleg je Bauteil): {typ} hat nur {ziel['beleg']:.2f} seiner datennahen "
              f"Flaeche auf der Wolke (Median-Abstand {ziel['median_m']:.2f} m, Anteil mit Daten {ziel['anteil_mit_daten']:.2f}). "
              f"Fotokanten (Kantengitter aus Fotos) je Teil: Recall {ziel.get('kanten_recall')} (Anteil der Fotokanten am Teil, die das Modell erklaert), "
              f"Praezision {ziel.get('kanten_praez')} (Anteil der Teil-Formkanten, die ein Foto belegt). Gate: Mittel aus Beleg und Kanten-F1 muss um >= {MIN_GEWINN} steigen, "
              f"keine der beiden Groessen darf um > 0,02 fallen. Verdeckte Flaechen zaehlen nicht (nur kamera-zugewandt). "
              f"Form oder Lage passt nicht zu den Daten. Ursache unbekannt - in Stufe 0 an Fotos klaeren.")
        if ziel.get("art") == "beobachtung":
            b = ziel["beob"]
            befund = (f"OFFENE BEOBACHTUNG aus modelle/{OBJ}/masstabelle.json (beobachtungen_offen, Merkmal '{b.get('merkmal', '?')}', von {b.get('wer', '?')}): "
                      f"{b.get('text', '')} NAECHSTER SCHRITT laut Tabelle: {b.get('naechster_schritt', '-')} "
                      f"Diese Beobachtung ist das Ziel der Runde (Ursache steht oben, in Stufe 0 an >= 3 Fotos bestaetigen, dann messen und beheben). "
                      f"Wenn behoben: bei genau dieser Beobachtung in masstabelle.json das Feld \"erledigt\": \"kreis{runde} <Kurzbeleg>\" setzen. "
                      f"Zusatzwerte des Teils: " + befund[len("Automatisch aus konvergenz_bericht (Wolkenbeleg je Bauteil): "):])
    if not ist_fehlteil(ziel):
        _g = form_g(formliste(), ziel["teil"]); _je = {k: v for k, v in ((formliste().get("teile") or {}).get(ziel["teil"]) or {}).items() if k != "_gesamt"}
        if _g:
            _schl = sorted(_je, key=lambda k: _je[k]["praez"] + _je[k]["recall"])[:3]
            _fl = "; ".join(f"Foto {k}: Praez {_je[k]['praez']}, Recall {_je[k]['recall']}, gelbe Flecken (Fotokante OHNE Modell) bei {[f['xyz'] for f in _je[k]['gelb']]}, "
                            f"rote (Modellkante OHNE Foto) bei {[f['xyz'] for f in _je[k]['rot']]}" for k in _schl)
            befund += (f" FORM AM FOTO (tools/teil_fotoform.py, Schwelle 0,14 m, je kalibriertem Foto, verdeckte Pixel ausgenommen): F1 {_g['f1']} "
                       f"(Praezision {_g['praez']} = Modellkanten mit Fotokante, Recall {_g['recall']} = Fotokanten mit Modellkante) ueber {_g['fotos']} Fotos. "
                       f"Schwaechste: {_fl}. Bilder: {formliste().get('bilder_dir', FORMDIR)}/{ziel['teil']}_<foto>.jpg ansehen (gruen passt, rot erfunden, gelb fehlt). "
                       f"Gelb im Teil = Form fehlt (Fenster, Rippen, Pfeiler, Ueberstand); rot = Form falsch/zu viel. Der Foto-F1 geht ins Tor ein und darf nicht fallen. "
                       f"Eigene Zwischenmessung nur auf den Torfotos (das Tor misst genau diese; alle Fotos = ~20 min GPU fuer dieselbe Aussage): "
                       f"tools/teil_fotoform.py {OBJ} --nur {ziel['teil']} --fotos {','.join(form_fotos(formliste(), ziel['teil']))} --aus {LDIR}/ff_eigen.json --bilder_dir {LDIR}/ff_eigen_bilder")
    txt = (txt.replace("`<OBJEKT>`", OBJ).replace("<OBJEKT>", OBJ).replace("`<BAUTEIL>`", typ).replace("<BAUTEIL>", typ)
              .replace("`<BEFUND>`", befund).replace("<BEFUND>", befund).replace("<RUNDE>", f"kreis{runde}")
              .replace("`<TABU>`", ", ".join(TABU) or "-").replace("<TABU>", ", ".join(TABU) or "-")
              .replace("`<FOTOS>`", "-").replace("<FOTOS>", "-"))
    txt = txt.replace("/home/oem/git/rc-park", wt)
    txt += vorversuche(ziel["teil"])
    txt += (f"\n\nUNBEAUFSICHTIGTER LAUF: Arbeitsverzeichnis ist der git-Worktree {wt} (nicht /home/oem/git/rc-park). "
            "Keine Rueckfragen moeglich - bei Unklarheit ANNAHME notieren und weiter. Am Ende den Bericht (Pflichtform der Vorlage) "
            f"zusaetzlich nach {wt}/modelle/{OBJ}/audit/kreis_bericht.md schreiben und die Overlay-Pfade dort auflisten.")
    return txt

def pruefer_urteil(wt, ziel, runde):
    p = (f"Du bist der Pruefer nach modelle/VORLAGE_BAUTEIL_RUNDE.md (Abschnitt Pruefer-Checkliste) im Worktree {wt}, Objekt {OBJ}, "
         f"Bauteil {ziel['teil'].replace('__', ':')}" + (f" (FEHLENDES ELEMENT im Kasten {ziel['lo']} .. {ziel['hi']} m: neues Teil muss dort echte Fotokanten treffen, nichts erfunden)" if ist_fehlteil(ziel) else "") + f". Lies {wt}/modelle/{OBJ}/audit/kreis_bericht.md, sieh dir JEDES dort genannte Overlay "
         f"und {wt}/modelle/{OBJ}/audit/seiten.jpg selbst an. Pruefe: Formbeschreibung vollstaendig und passend zu den Fotos? Formpruefung je Foto vorher/nachher: {LDIR}/fotoform_bilder/{ziel['teil']}_*_r{runde}_vorher.jpg und _nachher.jpg "
         f"(gelb = Fotokante ohne Modell = fehlende Form, rot = erfundene Form) ansehen und gelbe Reste in die Fehlerliste. Trifft das Teil "
         "die Fotos besser als vorher? Neue Fehler an anderen Teilen? Nichts schoenreden, Agenten-'ok' nie uebernehmen. Aendere KEINE Dateien. "
         'Letzte Zeile deiner Antwort GENAU: URTEIL {"annehmen": true|false, "fehlerliste": ["..."]}')
    rc, out = sh(["claude", "-p", p, "--model", PRUEFER, "--permission-mode", "plan"], wt,
                 log=os.path.join(LDIR, f"pruefer_r{runde}.log"), timeout=MAX_MIN * 60)
    m = re.findall(r"URTEIL\s*(\{.*\})", out)
    try:
        return json.loads(m[-1])
    except Exception:
        return {"annehmen": False, "fehlerliste": ["Pruefer-Urteil nicht lesbar"], "rc": rc}

# ---------------- Kreis ----------------
sperre, ohne_annahme = {}, 0
basis = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
print(f"Kreis {OBJ} Lauf {LAUF} Basis {basis[:7]} -> {LDIR}")
# Nachpruefen (10.11.): eine verworfene Runde, deren Tor an Infrastruktur scheiterte (OOM/Platz), ohne neuen Agenten erneut durch alle 3 Tore.
# --nachpruefen <alter Laufordner>:<runde> ; Worktree der alten Runde wird weiterverwendet, Vorher-Wert = Wolkenbeleg aus deren Protokoll.
NACH = opt("--nachpruefen", "")
if NACH:
    _ld, _r = NACH.rsplit(":", 1); RUNDEN = 1
    NACH_Z = [json.loads(l) for l in open(os.path.join(_ld, "kreis.jsonl")) if l.strip() and json.loads(l).get("runde") == int(_r) and "angenommen" in json.loads(l)][-1]
import hashlib as _hl
_CODE = lambda: _hl.sha256(open(os.path.join(ROOT, "tools", "bauteil_kreis.py"), "rb").read()).hexdigest()
_CODE0 = _CODE()
for runde in range(1, RUNDEN + 1):
    if runde > 1 and not NACH and not TROCKEN and _CODE() != _CODE0:
        # 10.11.: alte Spuren liefen stundenlang mit altem Tor (ohne Formpruefung/Quellenvorrang) und scheiterten am behobenen Fehler -> neu starten lassen
        print(f"Runde {runde}: Kreis-Code auf main geaendert - Spur endet, Regler startet frisch"); protokoll({"runde": runde, "ende": "code neu"}); break
    wt = os.path.join(LDIR, f"wt_r{runde}"); br = f"kreis/{OBJ}/{LAUF}-r{runde}"
    if NACH:
        wt, br = NACH_Z["worktree"], NACH_Z["branch"]
        if not os.path.exists(wt):
            subprocess.run(["git", "-C", ROOT, "worktree", "add", "-q", wt, br], check=True)
    elif TROCKEN:
        wt = ROOT
    else:
        if "--nach_main" in a:
            # 10.11.: Spur baute auf ihrem eigenen alten Stand weiter (a064559 r2 auf 527bc46), waehrend a062358 dasselbe Teil schon nach main
            # gebracht hatte -> zwei angenommene Fassungen, Quellkonflikt objekt.json/elemente.json. Jede Runde startet auf dem aktuellen main.
            basis = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "-C", ROOT, "worktree", "add", "-q", "-b", br, wt, basis], check=True)
    if NACH:
        # volle Vorher-Messung der Originalrunde (alle Teile, sonst zaehlt jedes Teil als 'neu' - Nachpruefung s4 10.11. ergab falsch -0,320)
        _kf = os.path.join(wt, "modelle", OBJ, "konvergenz.jsonl"); z0 = None
        if os.path.exists(_kf):
            for _l in reversed([x for x in open(_kf) if x.strip()]):
                _z = json.loads(_l)
                if str(_z.get("etikett", "")).endswith(f"r{_r}_vorher") and _z.get("wolkenbeleg_teile"): z0 = _z; break
        if z0 is not None and ("kanten_recall" not in (z0["wolkenbeleg_teile"][0] if z0["wolkenbeleg_teile"] else {}) or z0.get("sicht") != SICHT):
            z0 = None   # alte Messart (ohne Sichtpruefung) - nicht vergleichbar
        if z0 is None:   # Basis der Originalrunde (Zweig~1) neu messen, gleiche Messart wie nachher
            wt0 = os.path.join(LDIR, "wt_basis")
            _msg = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%s", br], capture_output=True, text=True).stdout
            _basis = br + "~1" if ("VERWORFEN" in _msg or "gesichert" in _msg or "(automatisch" in _msg) else br   # alte Spuren: Aenderungen ungesichert im Worktree, Zweig = Basis; angenommene Runde (Commit 'automatisch') -> Basis = Zweig~1
            subprocess.run(["git", "-C", ROOT, "worktree", "add", "-q", "--detach", wt0, _basis], check=True)
            _rc0, z0, _o0 = messen(wt0, f"r{runde}_vorher_basis")
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", wt0], capture_output=True)
            if not z0: sys.exit("Nachpruefen: Basis-Messung fehlgeschlagen")
    elif TROCKEN:
        # Trockenlauf baut nichts (main bleibt unberuehrt): letzte gespeicherte Konvergenz-Zeile
        kf = opt("--z0", os.path.join(ROOT, "modelle", OBJ, "konvergenz.jsonl"))   # --z0: Zeile aus konvergenz_bericht --json_aus
        z0 = json.loads([l for l in open(kf) if l.strip()][-1])
    else:
        # Wiederverwendung (verlustfrei): letzte Konvergenz-Zeile gilt, wenn ihr STL-Hash dem STL dieses Stands gleicht und sie den Wolkenbeleg traegt
        import hashlib
        z0 = None; kf = os.path.join(wt, "modelle", OBJ, "konvergenz.jsonl"); sp = os.path.join(wt, STL)
        if os.path.exists(kf) and os.path.exists(sp):
            sha = hashlib.sha256(open(sp, "rb").read()).hexdigest()[:16]
            for l in reversed([l for l in open(kf) if l.strip()]):
                zz = json.loads(l)
                if zz.get("stl_sha") == sha and zz.get("wolkenbeleg_teile") and "kanten_recall" in zz["wolkenbeleg_teile"][0] and "fehlkanten" in zz and zz.get("sicht") == SICHT:   # gleiche Messart (Sichtpruefung + Fotokanten je Teil)
                    z0 = zz; print(f"Runde {runde}: Messung vorher wiederverwendet (STL {sha})"); break
        if z0 is None:
            # Spurenuebergreifender Vorher-Speicher (10.11.: 8 Spuren auf demselben main massen je 5-25 min dasselbe; konvergenz.jsonl liegt nur im
            # eigenen Worktree). Schluessel = STL + Werkzeuge + Objekt/Masstabelle -> gleiche Eingaben, gleiches Ergebnis (verlustfrei).
            # Die erste Spur misst unter einer Sperre je Schluessel, die anderen warten und lesen.
            import fcntl
            _h = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD:tools", f"HEAD:modelle/{OBJ}/objekt.json", f"HEAD:modelle/{OBJ}/masstabelle.json"],
                                capture_output=True, text=True).stdout.split()
            _key = hashlib.sha256((open(sp, "rb").read() if os.path.exists(sp) else b"") + " ".join(_h).encode()).hexdigest()[:20]
            _vd = os.path.join(KREISDIR, OBJ, "vorher_speicher"); os.makedirs(_vd, exist_ok=True)
            _zf, _td = os.path.join(_vd, _key + ".json"), os.path.join(LDIR, f"teile_r{runde}_vorher")
            with open(os.path.join(_vd, _key + ".lock"), "w") as _lk:
                fcntl.flock(_lk, fcntl.LOCK_EX)
                if os.path.exists(_zf) and os.path.isdir(os.path.join(_vd, _key)):
                    z0 = json.load(open(_zf)); shutil.copytree(os.path.join(_vd, _key), _td, dirs_exist_ok=True)
                    with open(kf, "a") as f: f.write(json.dumps(dict(z0, etikett=f"kreis {LAUF} r{runde}_vorher"), ensure_ascii=False) + "\n")
                    print(f"Runde {runde}: Messung vorher aus Spurenspeicher {_key} (gleicher STL, Werkzeuge, Masstabelle)")
                else:
                    rc0, z0, out0 = messen(wt, f"r{runde}_vorher")
                    if rc0 in (0, 3) and z0 and len(_h) == 3 and z0.get("stl_sha") == hashlib.sha256(open(sp, "rb").read()).hexdigest()[:16]:
                        shutil.copytree(_td, os.path.join(_vd, _key), dirs_exist_ok=True); json.dump(z0, open(_zf + ".tmp", "w"), ensure_ascii=False); os.replace(_zf + ".tmp", _zf)
    ziel = NACH_Z["ziel"] if NACH else waehlen(z0, sperre)
    if not ziel:
        if not TROCKEN and not NACH and wt != ROOT:   # 10.11.: leere Spuren liessen je 500 MB Worktree liegen (Datenplatte auf 10,0 GB); unveraendert = Commit, verlustfrei
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", wt], capture_output=True)   # ohne --force: bricht ab, falls doch etwas geaendert ist
        print("kein Kandidat mehr - Ende"); protokoll({"runde": runde, "ende": "kein Kandidat"}); break
    txt = auftrag(ziel, runde, wt)
    open(os.path.join(LDIR, f"auftrag_r{runde}.md"), "w").write(txt)
    print(f"Runde {runde}: Ziel {ziel['teil']} ({'Fehlteil ' + str(ziel['pkt']) + ' Pkt, Recall Kasten ' + str(ziel['recall_kasten']) if ist_fehlteil(ziel) else 'Wolkenbeleg ' + str(ziel['beleg'])}) -> Auftrag {LDIR}/auftrag_r{runde}.md")
    if TROCKEN:
        freigeben(ziel["teil"]); protokoll({"runde": runde, "trocken": True, "ziel": ziel}); print(txt[:1500]); break
    ff_v, ff_fotos = None, []
    if not ist_fehlteil(ziel) and not TROCKEN and not NACH:   # Form am Foto VOR dem Agenten (Basisstand), gleiche Fotos nachher
        _fl = formliste(); ff_fotos = form_fotos(_fl, ziel["teil"])
        _fv = form_aus_liste(_fl, wt, ziel["teil"], ff_fotos, runde) if ff_fotos else None
        if _fv is not None:
            ff_v = _fv; print(f"Runde {runde}: Form am Foto vorher {ziel['teil']}: F1 {ff_v} ({len(ff_fotos)} Fotos, aus Formliste {_fl.get('stl_sha')})")
        elif ff_fotos:
            _tv = os.path.join(LDIR, f"teile_r{runde}_vorher")   # Export der Vorher-Messung (gleicher Stand, Agent lief noch nicht) - zweiter Export war doppelt
            if not glob.glob(os.path.join(_tv, "*.stl")):
                _tv = os.path.join(LDIR, f"teile_r{runde}_vorher_form")
                _gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
                sh_cpu(_gen, wt, log=os.path.join(LDIR, f"export_r{runde}_vorher_form.log"), env={"BAUTEILE_AUS": _tv})
            ff_v = form_messen(wt, _tv, ziel["teil"], ff_fotos, f"r{runde}_vorher")
            print(f"Runde {runde}: Form am Foto vorher {ziel['teil']}: F1 {ff_v} ({len(ff_fotos)} Fotos)")
    t0 = time.time()
    rcA, _ = (None, "") if NACH else sh(["claude", "-p", txt, "--model", MODELL, "--permission-mode", RECHTE], wt,
                log=os.path.join(LDIR, f"agent_r{runde}.log"), timeout=MAX_MIN * 60)
    # VORPRUEFUNG (Nutzer 10.11. 14:3x, 5 von 5 Runden erst im Tor nach 1-1,5 h verworfen, meist Foto-F1 gefallen oder Pflichtschritt
    # uebersprungen): gleich nach dem Agenten Form am Foto messen (gleiche Fotos, gleiche Formel wie das Tor). Keine klare Besserung
    # (< vorher + 0,02) -> EINMAL zurueck an denselben Agenten (claude --continue im Worktree, Kontext bleibt) mit Messwerten je Foto
    # und Overlay-Pfaden. Das Tor bleibt unveraendert (gleiche Schwellen, misst danach selbst) - nur der Rueckweg ist frueher.
    _tn = os.path.join(LDIR, f"teile_r{runde}_nachher"); _vorab_gebaut = False; ff_q = None
    if ff_v is not None and not ist_fehlteil(ziel) and not NACH and VORPRUEF:
        shutil.rmtree(_tn, ignore_errors=True)
        _gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
        _rq, _ = sh_cpu(_gen, wt, log=os.path.join(LDIR, f"vorpruef_r{runde}.log"), env={"BAUTEILE_AUS": _tn})
        ff_q = form_messen(wt, _tn, ziel["teil"], ff_fotos, f"r{runde}_vorpruef") if _rq == 0 else None
        print(f"Runde {runde}: Vorpruefung Form am Foto {ziel['teil']}: F1 {ff_v} -> {ff_q}" + ("" if _rq == 0 else " (Generator rot)"), flush=True)
        if _rq != 0 or ff_q is None or ff_q < ff_v + 0.02:
            try: _je = (json.load(open(os.path.join(LDIR, f"fotoform_r{runde}_vorpruef.json")))["teile"].get(ziel["teil"]) or {})
            except Exception: _je = {}
            _zeilen = "\n".join(f"- Foto {f}: Praezision {_je[f].get('praez')} / Recall {_je[f].get('recall')}  Overlay {LDIR}/fotoform_bilder/{ziel['teil']}_{f}_r{runde}_vorpruef.jpg"
                                f"  (vorher: {ziel['teil']}_{f}_r{runde}_vorher.jpg)" for f in ff_fotos if f in _je)
            _rueck = (f"VORPRUEFUNG DES KREISES (automatisch, gleiche Messung wie das Tor): Dein Stand ist "
                      + ("im Generator ROT (siehe " + os.path.join(LDIR, f"vorpruef_r{runde}.log") + ")" if _rq != 0 else
                         f"am Foto NICHT besser: Form-F1 {ff_v} -> {ff_q} (Tor verlangt keinen Rueckschritt > 0,02 und Teilgewinn >= {MIN_GEWINN}).")
                      + f"\nJe Foto (rot = Modellkante ohne Fotokante, gelb = Fotokante fehlt im Modell):\n{_zeilen}\n"
                      "Sieh dir die Overlays an (mindestens 3), benenne je Foto, welche Kante falsch/fehlend ist, und korrigiere den Generator-Stand. "
                      "Pflicht vor der Abgabe: Zaehlmerkmale (Anzahl Elemente je Flaeche) am Foto mit tools/foto_zaehlung.py belegen, wenn das Teil welche hat; "
                      f"`bash tools/bauen_abnehmen.sh {OBJ}` gruen. Bringt eine Aenderung am Foto nichts, nimm sie zurueck (git checkout) statt sie abzugeben. "
                      "Antworte am Ende mit derselben Berichtform wie vorher.")
            open(os.path.join(LDIR, f"rueckgabe_r{runde}.md"), "w").write(_rueck)
            print(f"Runde {runde}: Vorpruefung -> zurueck an den Agenten (einmal)", flush=True)
            sh(["claude", "-p", _rueck, "--continue", "--model", MODELL, "--permission-mode", RECHTE], wt,
               log=os.path.join(LDIR, f"agent_r{runde}_nachbesserung.log"), timeout=max(30, MAX_MIN // 2) * 60)
        else:
            _vorab_gebaut = True   # Stand unveraendert seit dem Export: Tor-Bau unten nicht wiederholen (deterministisch, gleiches Ergebnis)
    fbefund = None
    if ist_fehlteil(ziel):
        _al = os.path.join(LDIR, f"agent_r{runde}.log")
        _m = BEFUND_RE.findall(open(_al, errors="replace").read()) if os.path.exists(_al) else []
        fbefund = _m[-1] if _m else None
        print(f"Runde {runde}: Fehlteil-Befund des Agenten: {fbefund}")
    # Bau (CPU) ausserhalb der GPU-Torsperre, Teile-Export im selben Lauf (vorher: bauen_abnehmen baute unter der Sperre, messen() baute danach
    # ein zweites Mal identisch); dann Pruefen unter der Sperre. Gleiche Schritte wie bauen_abnehmen.sh (Generator, dann --nur-pruefen).
    if _vorab_gebaut:
        rcG = 0
    else:
        shutil.rmtree(_tn, ignore_errors=True)
        _gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
        rcG, _ = sh_cpu(_gen, wt, log=os.path.join(LDIR, f"abnahme_r{runde}.log"), env={"BAUTEILE_AUS": _tn})
    rcB, outB = sh_tor(["bash", "tools/bauen_abnehmen.sh", OBJ, "--nur-pruefen"], wt, log=os.path.join(LDIR, f"abnahme_r{runde}.log")) if rcG == 0 else (rcG, "Generator fehlgeschlagen")
    tor_abnahme = rcB == 0 and "alle Pruefungen bestanden" in outB
    reg = None
    if ist_fehlteil(ziel):
        reg = os.path.join(LDIR, f"region_r{runde}.json"); json.dump([{"id": ziel["id"], "lo": ziel["lo"], "hi": ziel["hi"]}], open(reg, "w"))
    rcK, z1, outK = messen(wt, f"r{runde}_nachher", regionen=reg, vorab=(rcG == 0))
    vor_t = {t["teil"]: t for t in z0.get("wolkenbeleg_teile") or []}; nach_t = {t["teil"]: t for t in (z1 or {}).get("wolkenbeleg_teile") or []}
    vor = {k: guete(v) for k, v in vor_t.items()}; nach = {k: guete(v) for k, v in nach_t.items()}
    ersatz = None
    if ziel["teil"] not in nach:   # Teil durch neue Formfamilie ersetzt (z. B. stl_teil:figuren -> figurenreihe:figuren, s4 10.11.): neue Teile zaehlen, konservativ das schlechteste
        neu_t = {t: v for t, v in nach.items() if t not in vor and v is not None}
        if neu_t: ersatz = min(neu_t, key=neu_t.get); nach[ziel["teil"]] = neu_t[ersatz]
    ff_n = None
    if ff_v is not None and not ersatz:
        ff_n = ff_q if _vorab_gebaut else form_messen(wt, os.path.join(LDIR, f"teile_r{runde}_nachher"), ziel["teil"], ff_fotos, f"r{runde}_nachher")   # Vorpruefung = gleicher Stand, gleiche Messung
        if ff_n is not None:
            vor[ziel["teil"]] = guete_form(vor_t.get(ziel["teil"], {}), ff_v); nach[ziel["teil"]] = guete_form(nach_t.get(ziel["teil"], {}), ff_n)
        print(f"Runde {runde}: Form am Foto {ziel['teil']}: F1 {ff_v} -> {ff_n} ({len(ff_fotos)} Fotos)")
    gewinn = (nach.get(ziel["teil"]) or 0) - (vor.get(ziel["teil"]) or 0)
    # kein Rueckschritt in einer der beiden Groessen (Lage ODER Form) um mehr als 0,02
    tv = vor_t.get(ziel["teil"], {}); tn = nach_t.get(ersatz or ziel["teil"], {})
    rueck_teil = [n for n, fv, fn in (("beleg", tv.get("beleg"), tn.get("beleg")), ("kanten_f1", f1(tv), f1(tn)), ("foto_f1", ff_v, ff_n)) if fv is not None and fn is not None and fn < fv - 0.02]
    if "kanten_f1" in rueck_teil and ff_v is not None and ff_n is not None and ff_n >= ff_v + 0.02:
        # Quellenvorrang (10.11., Balkon 3x verworfen): das Kantengitter ist aus den Fotos ABGELEITET und hatte ~130 Segmente ueber freier Wand;
        # die direkte Formpruefung am Foto zeigt Besserung -> kein Rueckschritt, Widerspruch als Beobachtung (Regel 5: nicht mitteln).
        rueck_teil.remove("kanten_f1"); gitter_widerspruch = f"Gitter-F1 {f1(tv):.3f}->{f1(tn):.3f}, Foto-F1 {ff_v:.3f}->{ff_n:.3f}"
        print(f"Runde {runde}: Gitter widerspricht Foto ({gitter_widerspruch}) - Foto gilt, Beobachtung folgt")
    else:
        gitter_widerspruch = None
    tor_konv = rcK == 0 and gewinn >= MIN_GEWINN and not rueck_teil
    if ist_fehlteil(ziel):   # eigenes Tor: Recall im Kasten, neue Teile praezise, kein anderes Teil schlechter, Gesamt-Recall nicht kleiner
        r_n = (((z1 or {}).get("regionen") or {}).get(ziel["id"]) or {}).get("recall")
        gewinn = (r_n if r_n is not None else 0) - (ziel["recall_kasten"] or 0)
        neu_t = [t for t in nach_t if t not in vor_t]
        rueck_teil = [f"praez {t}={nach_t[t].get('kanten_praez')}" for t in neu_t if (nach_t[t].get("kanten_praez") or 0) < MIN_PRAEZ_NEU]
        rueck_teil += [f"guete {t} {vor[t]:.3f}->{nach[t]:.3f}" for t in vor if vor.get(t) is not None and nach.get(t) is not None and nach[t] < vor[t] - 0.02]
        rg0 = z0["kanten"]["gesamt"]["recall"]; rg1 = (z1 or {}).get("kanten", {}).get("gesamt", {}).get("recall")
        # Toleranz 0,002 = Stichproben-Rauschen (a030944 r1: unveraendertes Modell 0,6483 -> 0,6481)
        if rg1 is None or rg1 < rg0 - 0.002: rueck_teil.append(f"recall_gesamt {rg0}->{rg1}")
        tor_konv = rcK == 0 and r_n is not None and gewinn >= MIN_REGION and not rueck_teil
        vor[ziel["teil"]], nach[ziel["teil"]] = ziel["recall_kasten"], r_n
    if rueck_teil: print(f"Runde {runde}: Rueckschritt im Ziel-Teil: {rueck_teil}")
    urteil = pruefer_urteil(wt, ziel, runde) if (tor_abnahme and tor_konv) else {"annehmen": False, "fehlerliste": ["nicht geprueft: Vortor rot"]}
    angenommen = tor_abnahme and tor_konv and bool(urteil.get("annehmen"))
    if angenommen and gitter_widerspruch:
        try:
            _mp = os.path.join(wt, "modelle", OBJ, "masstabelle.json"); _T = json.load(open(_mp))
            _T.setdefault("beobachtungen_offen", []).append({"datum": time.strftime("%Y-%m-%d"), "wer": f"kreis {LAUF} r{runde} (automatisch)", "merkmal": f"Kantengitter widerspricht Foto ({ziel['teil']})",
                "text": f"Angenommen nach Quellenvorrang Foto: {gitter_widerspruch}. Kantengitter hat dort vermutlich Fehlsegmente.", "naechster_schritt": "Gittersegmente im Teilbereich gegen Fotos pruefen (gitter_zurueck), Fehlsegmente markieren."})
            json.dump(_T, open(_mp, "w"), ensure_ascii=False, indent=1)
        except Exception as _ex: print(f"Runde {runde}: Gitter-Widerspruch nicht eingetragen: {_ex}")
    if angenommen and urteil.get("fehlerliste") and not ist_fehlteil(ziel):
        # Pruefer-Rest wird Kreisziel (Nutzer 10.11.: Erker-Rippen standen in der Fehlerliste, Teil hatte Guete 0,98 und kam nie wieder dran).
        # Eine Beobachtung je Teil: die neue ersetzt die alte Pruefer-Rest-Beobachtung desselben Teils (erledigt = ersetzt).
        try:
            _mp = os.path.join(wt, "modelle", OBJ, "masstabelle.json"); _T = json.load(open(_mp)); _tt = ziel["teil"].replace("__", ":")
            for _b in _T.get("beobachtungen_offen") or []:
                if isinstance(_b, dict) and _b.get("teil") == _tt and str(_b.get("merkmal", "")).startswith("Pruefer-Rest") and not _b.get("erledigt"):
                    _b["erledigt"] = f"ersetzt durch Pruefer-Rest kreis {LAUF} r{runde}"
            _T.setdefault("beobachtungen_offen", []).append({"datum": time.strftime("%Y-%m-%d"), "wer": f"Pruefer {PRUEFER} kreis {LAUF} r{runde} (automatisch)", "teil": _tt,
                "merkmal": f"Pruefer-Rest {_tt} kreis {LAUF} r{runde}", "text": "Offene Fehler laut Pruefer nach angenommener Runde: " + " | ".join(urteil["fehlerliste"]),
                "naechster_schritt": "Fehler einzeln an >= 3 Fotos bestaetigen (Formbilder teil_fotoform), je Fehler Pruefung die am Modell FEHLSCHLAEGT, dann Generator; Ornamente als neue Formfamilie mit Parametern."})
            json.dump(_T, open(_mp, "w"), ensure_ascii=False, indent=1)
        except Exception as _ex:
            print(f"Runde {runde}: Pruefer-Rest nicht eingetragen: {_ex}")
    if angenommen:
        subprocess.run(["git", "-C", wt, "add", "-A", "modelle", "tools"], check=False)
        subprocess.run(["git", "-C", wt, "commit", "-q", "-m", f"kreis {LAUF} r{runde}: {ziel['teil']} Wolkenbeleg {vor.get(ziel['teil'])} -> {nach.get(ziel['teil'])} (automatisch, Pruefer {PRUEFER})"], check=False)
        basis = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        ohne_annahme = 0
        if "--nach_main" in a:   # Nutzerentscheid 9.11.: angenommene Runden direkt nach main (revertierbar)
            import fcntl; _lk = open(os.path.join(KREISDIR, OBJ, "merge.lock"), "w"); fcntl.flock(_lk, fcntl.LOCK_EX)
            mr = subprocess.run(["git", "-C", ROOT, "merge", "--no-edit", "-m", f"kreis {LAUF} r{runde}: {ziel['teil']} nach main (automatisch)", br],
                                capture_output=True, text=True)
            if mr.returncode != 0 and ("local changes to the following files would be overwritten" in (mr.stderr + mr.stdout) or "lokalen Änderungen" in (mr.stderr + mr.stdout)):
                # geaenderte Erzeugnisse in main (10.11.: Diagnoselauf schrieb audit/fehlteile_6124.json): Kopie sichern, auf HEAD zuruecksetzen, erneut mergen; Quelldateien nie anfassen
                sich = os.path.join(KREISDIR, OBJ, "merge_sicherung", LAUF + f"_r{runde}_lokal")
                fl = [l.strip() for l in (mr.stderr + mr.stdout).splitlines() if l.startswith(("\t", "    ")) and l.strip()]
                erz = lambda f: f.startswith("modelle/stl/") or f.endswith(("pruefbericht.json", "MASSNACHWEIS.md", ".jpg", ".png")) or "/audit/" in f
                if fl and all(erz(f) for f in fl):
                    for f in fl:
                        os.makedirs(os.path.dirname(os.path.join(sich, f)), exist_ok=True); shutil.copy2(os.path.join(ROOT, f), os.path.join(sich, f))
                    subprocess.run(["git", "-C", ROOT, "checkout", "--"] + fl, capture_output=True)
                    print(f"Runde {runde}: lokal geaenderte Erzeugnisse {fl} nach {sich} gesichert, Merge erneut")
                    mr = subprocess.run(["git", "-C", ROOT, "merge", "--no-edit", "-m", f"kreis {LAUF} r{runde}: {ziel['teil']} nach main (automatisch)", br], capture_output=True, text=True)
            if mr.returncode != 0 and ("untracked working tree files would be overwritten" in (mr.stderr + mr.stdout) or "unversionierten Dateien" in (mr.stderr + mr.stdout)):
                # ungetrackte Erzeugnisse in main (Audit-Bilder, Caches) blockieren den Merge (Figuren 10.11.): verlustfrei wegsichern, erneut mergen
                sich = os.path.join(KREISDIR, OBJ, "merge_sicherung", LAUF + f"_r{runde}")
                for f in [l.strip() for l in (mr.stderr + mr.stdout).splitlines() if l.startswith(("\t", "    ")) and l.strip()]:
                    src = os.path.join(ROOT, f)
                    if os.path.isfile(src): os.makedirs(os.path.dirname(os.path.join(sich, f)), exist_ok=True); shutil.move(src, os.path.join(sich, f))
                print(f"Runde {runde}: ungetrackte Dateien in main nach {sich} gesichert, Merge erneut")
                mr = subprocess.run(["git", "-C", ROOT, "merge", "--no-edit", "-m", f"kreis {LAUF} r{runde}: {ziel['teil']} nach main (automatisch)", br], capture_output=True, text=True)
            if mr.returncode != 0:
                # Konflikt nur in Bau-Erzeugnissen (STL/Pruefbericht; 10.11. Gauben vs. Laube-Runde: teil_01.stl beidseitig neu gebaut):
                # Quellen sind sauber gemergt -> Erzeugnisse auf main neu bauen statt Annahme liegen lassen. Quellkonflikte bleiben Abbruch.
                konf = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", "--diff-filter=U"], capture_output=True, text=True).stdout.split()
                erzeugt = lambda f: f.startswith("modelle/stl/") or f.endswith(("pruefbericht.json", "MASSNACHWEIS.md", ".jpg", ".png")) or "/audit/" in f
                if konf and all(erzeugt(f) for f in konf):
                    subprocess.run(["git", "-C", ROOT, "checkout", "--theirs", "--"] + konf, capture_output=True)
                    gen = json.load(open(os.path.join(ROOT, "modelle", OBJ, "objekt.json")))["generator"]
                    rcg, _ = sh_cpu(gen, ROOT, log=os.path.join(LDIR, f"merge_neubau_r{runde}.log"))
                    if rcg == 0:
                        subprocess.run(["git", "-C", ROOT, "add", "--"] + konf, capture_output=True)
                        subprocess.run(["git", "-C", ROOT, "add", "-u", "modelle/stl"], capture_output=True)
                        mr = subprocess.run(["git", "-C", ROOT, "commit", "--no-edit", "-q"], capture_output=True, text=True)
                        print(f"Runde {runde}: Erzeugnis-Konflikt {konf} durch Neubau auf main geloest (rc {mr.returncode})")
            if mr.returncode != 0:
                subprocess.run(["git", "-C", ROOT, "merge", "--abort"], capture_output=True)
                print(f"Runde {runde}: MERGE nach main fehlgeschlagen, bleibt auf {br}: {mr.stdout[-300:]}{mr.stderr[-300:]}")
            else:
                basis = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
                print(f"Runde {runde}: nach main gemergt ({basis[:7]})")
                # Abnahme auf main noch unter dem Merge-Lock (10.11.: nach Merge-Neubau war die Druckteilung veraltet -> Pruefstand rot,
                # bis jemand von Hand die Abnahme laufen liess). Gruen -> Erzeugnisse committen; rot -> Merge automatisch zuruecknehmen.
                rcM, outM = sh_tor(["bash", "tools/bauen_abnehmen.sh", OBJ], ROOT, log=os.path.join(LDIR, f"abnahme_main_r{runde}.log"))
                if rcM == 0 and "alle Pruefungen bestanden" in outM:
                    subprocess.run(["git", "-C", ROOT, "add", "-u", "modelle"], capture_output=True)
                    subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", f"Abnahme main nach kreis {LAUF} r{runde} ({ziel['teil']}): alle Pruefungen bestanden (automatisch)"], capture_output=True)
                    basis = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
                    print(f"Runde {runde}: Abnahme main GRUEN ({basis[:7]})")
                elif "INFRA_OOM" in outM:
                    subprocess.run(["git", "-C", ROOT, "checkout", "--", "modelle"], capture_output=True)
                    print(f"Runde {runde}: Abnahme main nicht moeglich (Infrastruktur) - Merge bleibt, Abnahme von Hand noetig")
                else:
                    subprocess.run(["git", "-C", ROOT, "checkout", "--", "modelle"], capture_output=True)
                    rv = subprocess.run(["git", "-C", ROOT, "revert", "--no-edit", "-m", "1", "HEAD"], capture_output=True, text=True)
                    basis = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
                    print(f"Runde {runde}: Abnahme main ROT nach Merge -> Merge automatisch zurueckgenommen (rc {rv.returncode}, {basis[:7]})")
            fcntl.flock(_lk, fcntl.LOCK_UN); _lk.close()
    else:
        patch = os.path.join(LDIR, f"verworfen_r{runde}.patch")
        with open(patch, "w") as f:
            subprocess.run(["git", "-C", wt, "add", "-A", "-N", "."], check=False)
            subprocess.run(["git", "-C", wt, "diff"], stdout=f, check=False)
        _sk = beob_schluessel(ziel["beob"]) if ziel.get("art") == "beobachtung" else ziel["teil"]; sperre[_sk] = sperre.get(_sk, 0) + 1; ohne_annahme += 1
        subprocess.run(["git", "-C", wt, "add", "-A"], check=False)   # Stand verlustfrei auf dem Zweig sichern (fuer --nachpruefen), Worktree danach weg
        subprocess.run(["git", "-C", wt, "commit", "-q", "-m", f"kreis {LAUF} r{runde}: {ziel['teil']} VERWORFEN (Stand gesichert)"], check=False)
    if ist_fehlteil(ziel) and not angenommen and fbefund and not fbefund.lower().startswith("gebaut"):
        import fcntl as _f; _lk2 = open(ERLEDIGT + ".lock", "w"); _f.flock(_lk2, _f.LOCK_EX)
        _e = erledigt_laden(); _e[ziel["id"]] = {"lo": ziel["lo"], "hi": ziel["hi"], "befund": fbefund, "lauf": f"{LAUF} r{runde}",
                                                   "agent_log": os.path.join(LDIR, f"agent_r{runde}.log"), "zeit": time.strftime("%Y-%m-%d %H:%M")}
        json.dump(_e, open(ERLEDIGT, "w"), ensure_ascii=False, indent=1); _f.flock(_lk2, _f.LOCK_UN); _lk2.close()
        print(f"Runde {runde}: Fehlteil {ziel['id']} als erledigt gesperrt ({fbefund})")
    freigeben(ziel["teil"])
    if not TROCKEN and wt != ROOT:   # Platz (10.11.: 11 Worktrees x 430 MB fuellten die Datenplatte); Inhalt liegt als Commit auf dem Zweig br
        subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", wt], capture_output=True)
    protokoll({"runde": runde, "nachgeprueft": NACH or None, "ziel": ziel, "branch": br, "worktree": wt, "minuten": round((time.time() - t0) / 60, 1),
               "agent_rc": rcA, "tor_abnahme": tor_abnahme, "infra_oom": "INFRA_OOM" in outB or "INFRA_OOM" in (outK or ""), "konvergenz_rc": rcK, "ersatz_teil": ersatz, "rueckschritt_teil": rueck_teil, "gewinn": round(gewinn, 3), "guete_vor_nach": [vor.get(ziel["teil"]), nach.get(ziel["teil"])],
               "tor_konvergenz": tor_konv, "foto_f1": [ff_v, ff_n], "foto_fotos": ff_fotos, "fehlteil_befund": fbefund, "pruefer": urteil, "angenommen": angenommen,
               "rueckschritt": (z1 or {}).get("rueckschritt"), "recall_gesamt": [z0["kanten"]["gesamt"]["recall"], (z1 or {}).get("kanten", {}).get("gesamt", {}).get("recall")]})
    print(f"Runde {runde}: {'ANGENOMMEN' if angenommen else 'VERWORFEN'} (Abnahme {tor_abnahme}, Konvergenz {tor_konv} Gewinn {gewinn:+.3f}, Pruefer {urteil.get('annehmen')})")
    if ohne_annahme >= 2:
        print("2 Runden in Folge ohne Annahme - Ende"); break
print("Protokoll:", PROT)

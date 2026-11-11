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
# FOTO ZUERST (Nutzer 10.11. abends, ersetzt Option A): "Du brauchst nur 3 Bilder, um die Kanten abzugleichen. Wir brauchen die Wolke doch gar nicht."
# Befund: staffelgiebel__west wird von ~270 Fotos gesehen, Wolkenbeleg aber nur 0,18 (Wolke an steilen/schraeg gesehenen Flaechen duenn) -
# das alte Tor (Gewinn aus Beleg + Gitter-F1) konnte dort nie gewinnen. Jetzt: Gewinn = Foto-F1 (teil_fotoform, ~10 Fotos, Verdeckung beachtet);
# Wolke nur Veto fuer die LAGE (Regel 9d) und nur, wo das Teil genug Wolkendaten hat (anteil_mit_daten >= --min_daten).
# ANNAHME: Schwelle 0,02 = Veto-Marge; Foto-F1 ist deterministisch (unveraendertes Modell 0,635 -> 0,635, 0,72 -> 0,72, Logs 10.11.).
MIN_GEWINN_FOTO = opt("--min_gewinn_foto", 0.02, float)
# KONTROLLFOTOS (10.11. abends, Westgiebel-Agent mass auf selbst gewaehlten 6 Fotos 0,73-0,81, auf allen 10 Torfotos 0,413->0,394;
# Recherche Goodhart): je Teil N Fotos aus Rang 11.. der Formliste, dem Agenten NIE genannt (eigener Bilderordner), erst am Endtor gemessen.
# Veto, wenn Kontroll-F1 um mehr als MIN_KONTROLLE faellt. ANNAHME: 5 Fotos / 0,01 (noch kein Rauschboden gemessen).
# Beweistest 10.11. 20:2x (/media/oem/scan/rc-park_tmp/kontrolltest): Tuer (angenommen, Torfotos +0,29) auf 4 Kontrollfotos 0,424->0,333, fast nur EIN Foto (q11);
# Westgiebel (Torfotos 0,449->0,434) auf Kontrollfotos 0,653->0,769 (4 von 5 besser). Widerspruch nicht mitteln (Regel 5) -> vorerst nur MESSEN und protokollieren,
# Veto erst mit --kontroll_veto (nach Auswertung weiterer Runden).
KONTROLLE = opt("--kontrolle", 5, int); MIN_KONTROLLE = opt("--min_kontrolle", 0.01, float); KONTROLL_VETO = "--kontroll_veto" in a
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
NACHBARN = K.get("nachbarn", f"/media/oem/scan/rc-park_daten/{OBJ}/nachbarn_modellrahmen.ply")   # LoD2-Nachbarn im Modellrahmen (Brandwaende, tools/nachbarn_modellrahmen.py)
TABU = K.get("tabu", [])
LAUF = time.strftime("%Y%m%d_%H%M%S") + opt("--spur", "")
LDIR = os.path.join(KREISDIR, OBJ, LAUF); os.makedirs(LDIR, exist_ok=True)
PROT = os.path.join(LDIR, "kreis.jsonl")

def sh(cmd, cwd, log=None, env=None, timeout=None):
    e = dict(os.environ); e.update(env or {})
    e.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")   # mehrere Spuren teilen 8 GB VRAM (OOM 10.11. 00:25)
    e.setdefault("RCPARK_SIFT_MAX", "1600")
    with open(log, "a") if log else open(os.devnull, "w") as f:
        try:
            r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), stdout=f if log else subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, env=e, timeout=timeout)
        except subprocess.TimeoutExpired:   # 10.11. abends: Agent > Zeitlimit warf die ganze Spur weg (Westgiebel, 2 h Arbeit) -> rc 124, Stand geht ins Tor
            if log: f.write(f"\nZEITLIMIT {timeout} s erreicht - Abbruch, Stand wird trotzdem geprueft\n"); f.flush()
            print(f"ZEITLIMIT {timeout} s: {str(cmd)[:60]} abgebrochen, weiter mit dem vorhandenen Stand", flush=True)
            return 124, (open(log).read()[-4000:] if log else "")
    return r.returncode, (r.stdout if not log else open(log).read()[-4000:])

OOM_MUSTER = ("out of memory", "CUDA_ERROR_OUT_OF_MEMORY", "OutOfMemoryError", "PLATZ ZU KNAPP")   # Platzwaechter-Abbruch = Infrastruktur (s2 R1 10.11., Gewinn +0,224 verworfen)

def sh_cpu(cmd, cwd, log, env=None):
    """Reiner CPU-Schritt (Generatorbau, manifold - kein torch/cuda): ohne GPU-Torsperre. 10.11.: unter der Sperre wartete jeder Export auf
    alle Messungen der anderen Spuren (Export allein 4 min, in der Schlange bis 23 min). Ergebnis deterministisch -> verlustfrei."""
    t = time.time(); rc, out = sh(cmd, cwd, log=log, env=env)
    print(f"  CPU-Schritt {os.path.basename(log)}: {time.time() - t:.0f} s", flush=True); return rc, out

def sh_tor(cmd, cwd, log, env=None, versuche=6, pause=300, sperre=True):
    """Torschritt (Bau/Abnahme/Messung): Spuren-uebergreifend per flock serialisiert (deterministische Messung -> verlustfrei)
    und bei CUDA-OOM wiederholt. Ein OOM ist ein Infrastrukturfehler, kein rotes Tor (Kreis1 R1 10.11.: Abnahme 'rot' war OOM in wandstaerke)."""
    import fcntl
    rc, out = 1, ""
    for v in range(versuche):
        start = os.path.getsize(log) if os.path.exists(log) else 0
        with open(os.path.join(KREISDIR, "gpu_tor.lock" if sperre else "gpu_halb.lock"), "w") as lk:   # sperre=False: geteilte Sperre (blockiert nie), nur gpu_slot regelt
            tw = time.time(); fcntl.flock(lk, fcntl.LOCK_EX if sperre else fcntl.LOCK_SH); tl = time.time()
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
                   "--wolke", WOLKE, "--teile_dir", tdir, "--kameras", KAM, "--etikett", f"kreis {LAUF} {tag}"] + (["--nachbarn", NACHBARN] if os.path.exists(NACHBARN) else []) + (["--regionen", regionen] if regionen else []) + (["--trocken"] if TROCKEN else []),
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
    boxen = teil_boxen(); n = {}; leer = {}
    for _, lauf, z in ev:
        t = z["ziel"]["teil"]
        if z["ziel"].get("art") == "beobachtung": t = beob_schluessel(z["ziel"].get("beob") or {})   # eigene Zaehlung je Beobachtung (neue Information, z. B. Nutzer-Sichtfund)
        if z.get("angenommen") is False and not z.get("infra_oom") and z.get("metrik", "v1") == METRIK_SOLL and ("tor" in z or (t.endswith("__neu") and "guete_vor_nach" in z)): n[t] = n.get(t, 0) + 1   # nur Runden mit dem Foto-Tor (Feld 'tor', ab 10.11. abends) zaehlen - Verwerfungen unter dem Wolken-Tor sperren nicht
        _ff = z.get("foto_f1_vor_nach") or [None, None]
        _lr = z.get("agent_leer") if "agent_leer" in z else bool(z.get("frueh_abgelehnt") and _ff[0] is not None and _ff[0] == _ff[1])   # Altbestand vor 11.11. 02:5x
        _tt = z["ziel"]["teil"]   # leere Runden zaehlen am TEIL, nicht am Beobachtungsschluessel (gesperrte Beobachtung -> Teil kam als Teil wieder)
        if _lr and z.get("angenommen") is False and z.get("metrik", "v1") == METRIK_SOLL: leer[_tt] = leer.get(_tt, 0) + 1
        if z.get("angenommen") is True:
            n[t] = 0; leer[z["ziel"]["teil"]] = 0
            # Nutzerentscheid 10.11.: gesperrte Teile werden wieder frei, wenn ein Nachbarteil (Box +-1 m) danach in main geaendert wurde (neue Lage)
            if not nicht_in_main(z, lauf, z.get("runde")):
                # 11.11.: volle Ruecksetzung auf 0 gab Erker 1 nach JEDER Nachbarannahme (Balkon, Baldachine, Sockel) wieder 3 Versuche -> 8 Laeufe/14
                # Ablehnungen mit gleichem Pruefergrund. Nachbaraenderung = EIN neuer Versuch (Zaehler auf MAX_GLOBAL - 1), nicht drei.
                for u in [u for u in n if n[u] and u != t and nah(boxen, u, t)]: n[u] = min(n[u], MAX_GLOBAL - 1)
    # LEERE RUNDEN (11.11., Westgiebel 4x in einer Nacht): Agent aenderte nichts (Daten fehlen, z. B. Rueckseite ohne Foto). Nachbar-Annahmen aendern daran
    # nichts -> nach 2 leeren Runden gesperrt bis zur direkten Annahme dieses Teils (neue Fotos: Eintrag in fehlteil/Fotoplan, dann Zaehler per Annahme).
    for t, k in leer.items():
        if k >= 2: n[t] = max(n.get(t, 0), MAX_GLOBAL)
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
FOTO_FEHL = opt("--foto_fehl", 1, int); FOTO_FEHL_PX = opt("--foto_fehl_px", 2000, int); FOTO_FEHL_FOTOS = opt("--foto_fehl_fotos", 5, int); FOTO_FEHL_SUMME = opt("--foto_fehl_summe", 150000, int)   # Fehlteile aus Fotokanten (foto_fehlteile.py), 0 = aus
# BELEG STATT PIXELSUMME (Nutzer 11.11. 08:38: Balkon-Seitengelaender, Baldachin-Aufsatz, nie Ziel): kleine/hohe Teile erreichen die Pixelsumme nie
# (Aufsatz ueber den Baldachinen 3 Cluster je 63-82k px in 9-13 Fotos, Balkonende 6-13 Fotos). Ein Cluster in >= FOTO_FEHL_BELEG Fotos ist auch ohne Summe Ziel.
FOTO_FEHL_BELEG = opt("--foto_fehl_beleg", 6, int)

def ist_fehlteil(ziel): return (ziel or {}).get("art") == "fehlteil"

# Fehlteil-Befunde der Agenten (10.11.: dieselben Kaesten wurden 2-3x vergeben, obwohl der Agent 'kein Bauteil'/'Gitter zu duenn' belegt hatte)
ERLEDIGT = os.path.join(KREISDIR, OBJ, "fehlteil_erledigt.json")
def erledigt_laden():
    try: return json.load(open(ERLEDIGT))
    except Exception: return {}
def ist_erledigt(f, erl):
    """Kasten gilt als erledigt, wenn sein Zentrum in einem erledigten Kasten +-0,5 m liegt (Cluster-IDs wandern leicht zwischen Messungen)."""
    c = f["zentrum"]
    # 11.11. (Nutzer: Laube-Seitenbogen fehlt): ein 13,5-m-Kasten 'kein Bauteil' (ff_+11_+4_+4) sperrte jeden Cluster darin, u. a. den Seitenbogen
    # ff_+16_+4_+8 (474k px). Mit Kasten des Clusters: nur sperren, wenn die Kaesten sich wirklich decken (IoU >= ERL_IOU) - Zentrum-im-Kasten allein
    # nur noch, wenn der erledigte Kasten nicht viel groesser ist (Volumen <= ERL_VOL_FAKTOR x Cluster). Ohne Kasten (alte Ziele) wie bisher.
    lo, hi = f.get("lo"), f.get("hi")
    def _vol(a, b): return max(0.0, b[0] - a[0]) * max(0.0, b[1] - a[1]) * max(0.0, b[2] - a[2])
    for e in erl.values():
        if not all(e["lo"][i] - 0.5 <= c[i] <= e["hi"][i] + 0.5 for i in range(3)): continue
        if lo is None or hi is None: return True
        vc, ve = _vol(lo, hi), _vol(e["lo"], e["hi"])
        vi = _vol([max(lo[i], e["lo"][i]) for i in range(3)], [min(hi[i], e["hi"][i]) for i in range(3)])
        if (vc + ve - vi) > 0 and vi / (vc + ve - vi) >= ERL_IOU: return True
        if vc > 0 and ve <= ERL_VOL_FAKTOR * vc: return True
    return False
ERL_IOU, ERL_VOL_FAKTOR = 0.25, 4.0
BEFUND_RE = re.compile(r"FEHLTEIL-BEFUND:\s*(gebaut|kein Bauteil|Gitter zu duenn|vorhandenes Teil\s+\S+)", re.I)

# Formpruefung am Foto je Teil (teil_fotoform, L-KR24/L-KR25): Gauben/Balkon/Erker-Rippen waren falsch bei Guete 0,8-0,98, weil Wolke und
# Kantengitter (Toleranz 0,35 m, an Gauben 0 Punkte) Relief und Teilung nicht sehen. Formliste vom Regler (fotoform_auffrischen.sh) je main-STL.
FORMDIR = os.path.join(KREISDIR, OBJ, "fotoform")
# AUFLOESUNGS-TREPPE (Nutzer 10.11. abends "mit kleinerer Aufloesung rechnen, spaeter hoeher verfeinern"): Vorpruefung + Agenten-Zwischenmessung
# auf halber Fotoaufloesung (RCPARK_FOTO_SKALA, ~1 min statt ~10), Endtor unveraendert voll. Beweis /media/oem/scan/rc-park_tmp/skalatest:
# Helm O 0,3 m seitlich F1 -0,063 (voll -0,093), 0,3 m hoch Hoehen-Wert -0,048 (voll -0,052), Tuer +0,081 (voll +0,29); 33-58 s je 10 Fotos.
# Vergleichswert vorher aus der halben Formliste (fotoform_auffrischen.sh, fotoform_halb/<stl_sha>.json); fehlt sie, Vorpruefung voll wie bisher.
SKALA_VOR = opt("--vorpruef_skala", 0.5, float); HALBDIR = os.path.join(KREISDIR, OBJ, "fotoform_halb")
# METRIK-VERSION der Formliste (teil_fotoform "metrik"; v1 = Verdeckung nur gegen das Modell, v2_wolkenverdeckung = zusaetzlich Fotowolke, tools/wolke_verdeckung.py).
# Formlisten verschiedener Metrik duerfen NIE verglichen werden: Dateiname <stl_sha>_<metrik>.json (v1 unveraendert <stl_sha>.json) UND Pruefung des Feldes "metrik".
import re as _re
METRIK_SOLL = _re.search(r'^METRIK = "([^"]+)"', open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "teil_fotoform.py")).read(), _re.M).group(1)   # Quelle der Wahrheit: teil_fotoform.METRIK
def metrik_suffix(): return "_" + METRIK_SOLL
def formliste_halb(wt):
    import hashlib
    try:
        sha = hashlib.sha256(open(os.path.join(wt, STL), "rb").read()).hexdigest()[:16]; fl = json.load(open(os.path.join(HALBDIR, sha + metrik_suffix() + ".json")))
        return fl if fl.get("metrik", "v1") == METRIK_SOLL and fl.get("wolke_verdeckung", "an") == "an" else None
    except Exception: return None
def _hoehe_faellt(runde, vk="vorher"):
    v, n = HOEHE.get(f"r{runde}_{vk}"), HOEHE.get(f"r{runde}_vorpruef")
    return v is not None and n is not None and n < v - 0.02
HOEHE = {}   # Hoehen-Wert je Messung (f1_h, waagerechte Kanten; teil_fotoform.waagerecht), Schluessel = tag r<N>_vorher/_vorpruef/_nachher
JE = {}      # Werte JE FOTO je Messung (praez/recall/mk_px/fk_px), gleiche Schluessel wie HOEHE (+ kontrolle_vorher)
def f1_je(je, fotos):
    """Gleiche Formel wie teil_fotoform/_gesamt und form_aus_liste: pixelgewichtete Praezision/Recall, dann F1."""
    mk = sum(je[f]["mk_px"] for f in fotos); fk = sum(je[f]["fk_px"] for f in fotos)
    if mk <= 0 or fk <= 0: return None
    p = sum(je[f]["praez"] * je[f]["mk_px"] for f in fotos) / mk; r = sum(je[f]["recall"] * je[f]["fk_px"] for f in fotos) / fk
    return round(2 * p * r / (p + r), 3) if p + r else 0.0
def f1_je_p(je):
    """Pixelgewichtete Praezision einer Je-Foto-Messung (Anteil Modellkanten mit Fotokante); None ohne Modellkanten."""
    mk = sum(v["mk_px"] for v in je.values())
    return round(sum(v["praez"] * v["mk_px"] for v in je.values()) / mk, 3) if mk > 0 else None
def angleichen(tag_v, tag_n, fv, fn, wer=""):
    """GEWINN NUR AUF GEMEINSAMEN FOTOS (11.11., EG2 a205314: nachher fielen 6130/e04 aus der Bewertung ('0 Teile beurteilt'), +0,11 nur durch
    den kleineren Fotosatz, auf den gemeinsamen Fotos schlechter). Unterscheiden sich die beurteilten Fotos von vorher und nachher, werden beide
    Werte auf der Schnittmenge neu gerechnet; ohne gemeinsames Foto ist nachher None (nicht messbar = kein Gewinn). Fehlen Je-Foto-Werte: unveraendert."""
    a, b = JE.get(tag_v), JE.get(tag_n)
    if fv is None or fn is None or not a or not b or set(a) == set(b): return fv, fn
    g = [f for f in a if f in b]
    va, na = (f1_je(a, g), f1_je(b, g)) if g else (fv, None)
    print(f"  GEMEINSAME FOTOS {wer}: vorher {len(a)}, nachher {len(b)}, gemeinsam {len(g)} (nur vorher: {sorted(set(a) - set(b))}, nur nachher: {sorted(set(b) - set(a))}) -> F1 {fv} -> {fn} wird {va} -> {na}", flush=True)
    return (va if va is not None else fv), na
def formliste():
    fs = sorted([p for p in glob.glob(os.path.join(FORMDIR, "*.json")) if METRIK_SOLL in p], key=os.path.getmtime)
    try:
        fl = json.load(open(fs[-1])) if fs else {}
        return fl if fl.get("metrik", "v1") == METRIK_SOLL and fl.get("wolke_verdeckung", "an") == "an" else {}
    except Exception: return {}
def form_g(fl, teil): return (((fl.get("teile") or {}).get(teil) or {}).get("_gesamt") or {})
def form_fotos(fl, teil, n=10):
    je = {k: v for k, v in ((fl.get("teile") or {}).get(teil) or {}).items() if k != "_gesamt"}
    return sorted(je, key=lambda k: -(je[k]["mk_px"] + je[k]["fk_px"]))[:n]
def kontroll_fotos(fl, teil, n=None, ab=10):
    je = {k: v for k, v in ((fl.get("teile") or {}).get(teil) or {}).items() if k != "_gesamt"}
    return sorted(je, key=lambda k: -(je[k]["mk_px"] + je[k]["fk_px"]))[ab:ab + (KONTROLLE if n is None else n)]
def bereich_dir(tdir, tag):
    """FESTBEREICH (10.11. nachts, Schrumpf-Falle Balkonband 0,613->0,824 durch Kuerzen): nachher/vorpruef/kontrolle im Vereinigungsbereich mit dem
    Vorher-Teil messen (teil_fotoform --bereich_von), vorher (spaete volle Messung) mit dem Nachher-Teil, falls schon gebaut. Vorher-Werte aus der
    Formliste bleiben Bereich nur-vorher (konservativ: Wachsen wird eher unter- als ueberbewertet)."""
    import re as _r
    m = _r.match(r"r(\d+)_(\w+)", tag)
    if not m: return None
    n, art = m.group(1), m.group(2)
    for d in ([f"teile_r{n}_nachher"] if art.startswith("vorher") else [f"teile_r{n}_vorher_form", f"teile_r{n}_vorher"]):
        p_ = os.path.join(LDIR, d)
        if os.path.abspath(p_) != os.path.abspath(tdir) and glob.glob(os.path.join(p_, "*.stl")): return p_
    return None
def form_messen(wt, tdir, teil, fotos, tag, bilder="fotoform_bilder", env=None, stl=None):
    """Foto-F1 eines Teils (nur dieses Teil, Verdeckung gegen das ganze Modell) auf den Fotos der Formliste; None = nicht messbar."""
    if not fotos or not os.path.isdir(tdir): return None
    aus = os.path.join(LDIR, f"fotoform_{tag}.json")
    sh_tor([PY, "-W", "ignore", "-I", "tools/teil_fotoform.py", OBJ, "--teile_dir", tdir, "--stl", stl or STL, "--nur", teil, "--fotos", ",".join(fotos),
            "--aus", aus, "--bilder", "--bilder_dir", os.path.join(LDIR, bilder), "--etikett", tag] + (["--bereich_von", _bd] if (_bd := bereich_dir(tdir, tag)) else []), wt, log=os.path.join(LDIR, f"fotoform_{tag}.log"), env=env,
            sperre=not (env or {}).get("RCPARK_FOTO_SKALA"))   # Stufe halb (10.11. abends): nicht in die Tor-Schlange (mittl. 16 min Warten fuer ~1 min Lauf),
            # teil_fotoform belegt selbst einen gpu_slot (2 Plaetze, VRAM-Zulassung) - Ergebnis deterministisch, nur Reihenfolge anders
    try:
        _t = (json.load(open(aus))["teile"].get(teil) or {}); _g = _t.get("_gesamt") or {}; HOEHE[tag] = _g.get("f1_h")
        JE[tag] = {k: v for k, v in _t.items() if k != "_gesamt" and isinstance(v, dict) and "mk_px" in v}; return _g.get("f1")
    except Exception: return None
def form_aus_liste(fl, wt, teil, fotos, runde, nebenwirkung=True, hkey=None, jtag=None):
    """Vorher-F1 aus der Formliste, wenn sie zum STL des Basisstands passt (10.11.: jede Spur mass sonst 35 min dasselbe - Generator-Export
    + 10 Fotos, bei 8 Spuren parallel). Gleiche Formel wie teil_fotoform (_gesamt, pixelgewichtet) auf den gewaehlten Fotos; Vorher-Bilder verlinkt."""
    import hashlib
    try: sha = hashlib.sha256(open(os.path.join(wt, STL), "rb").read()).hexdigest()[:16]
    except OSError: return None
    je = ((fl.get("teile") or {}).get(teil) or {})
    if fl.get("stl_sha") != sha or fl.get("metrik", "v1") != METRIK_SOLL or fl.get("wolke_verdeckung", "an") != "an" or any(f not in je for f in fotos): return None
    mk = sum(je[f]["mk_px"] for f in fotos); fk = sum(je[f]["fk_px"] for f in fotos)
    if mk <= 0 or fk <= 0: return None
    p = sum(je[f]["praez"] * je[f]["mk_px"] for f in fotos) / mk; r = sum(je[f]["recall"] * je[f]["fk_px"] for f in fotos) / fk
    JE[jtag or hkey or f"r{runde}_vorher"] = {f: je[f] for f in fotos}
    if hkey:   # Hoehen-Wert unter eigenem Schluessel (halbe Formliste der Vorpruefung)
        hh = [je[f] for f in fotos if "mkh_px" in je[f]]; mh = sum(v["mkh_px"] for v in hh); fh = sum(v["fkh_px"] for v in hh)
        if mh and fh:
            ph = sum(v["praez_h"] * v["mkh_px"] for v in hh) / mh; rh = sum(v["recall_h"] * v["fkh_px"] for v in hh) / fh
            HOEHE[hkey] = round(2 * ph * rh / (ph + rh), 3) if ph + rh else 0.0
    if not nebenwirkung: return round(2 * p * r / (p + r), 3) if p + r else 0.0   # Kontrollfotos: keine Bilder/Hoehe in den Agentenordner
    bd = os.path.join(LDIR, "fotoform_bilder"); os.makedirs(bd, exist_ok=True)
    for f in fotos:
        q = os.path.join(fl.get("bilder_dir", ""), f"{teil}_{f}.jpg"); z = os.path.join(bd, f"{teil}_{f}_r{runde}_vorher.jpg")
        if os.path.exists(q) and not os.path.exists(z): os.symlink(q, z)
    hh = [je[f] for f in fotos if "mkh_px" in je[f]]; mh = sum(v["mkh_px"] for v in hh); fh = sum(v["fkh_px"] for v in hh)
    if mh and fh:
        ph = sum(v["praez_h"] * v["mkh_px"] for v in hh) / mh; rh = sum(v["recall_h"] * v["fkh_px"] for v in hh) / fh
        HOEHE[f"r{runde}_vorher"] = round(2 * ph * rh / (ph + rh), 3) if ph + rh else 0.0
    return round(2 * p * r / (p + r), 3) if p + r else 0.0
def guete_form(t, ff):
    """Teilguete mit Formpruefung am Foto: Mittel aus Wolkenbeleg, Gitter-Kanten-F1 (falls Gitter) und Foto-F1 (falls messbar)."""
    c = [x for x in (t.get("beleg"), f1(t), ff) if x is not None]
    return sum(c) / len(c) if c else None

# --patch DATEI --ziel TEIL (10.11. abends, Westgiebel-Agent lief in die Zeitgrenze, Spur stuerzte ab, Arbeit lag ungeprueft im Worktree):
# statt eines neuen Agenten den Patch auf den aktuellen main anwenden und durch dasselbe Tor (Vorher-Messung, Vorpruefung, Abnahme, Pruefer) schicken.
PATCH = opt("--patch", ""); ZIEL = opt("--ziel", "")
def ziel_fest(z):
    t = next((t for t in (z or {}).get("wolkenbeleg_teile") or [] if t["teil"] == ZIEL), None)
    if t is None: sys.exit(f"--ziel {ZIEL} nicht in der Messung")
    fd = os.open(os.path.join(BELEGT, ZIEL), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, f"{LAUF} {os.getpid()}".encode()); os.close(fd)
    return t

def waehlen(z, sperre):
    fg = fehlversuche_global()
    belegt_fam = {f.split("__")[0] for f in os.listdir(BELEGT)}
    # zuerst fehlende Elemente (groesster sichtbarer Fehler), groesster Cluster zuerst
    fk = [dict(f, teil=f["id"] + "__neu", art="fehlteil", beleg=None) for f in (z or {}).get("fehlkanten") or []
          if f["pkt"] >= FEHL_PKT and (f.get("recall_kasten") is not None and f["recall_kasten"] <= FEHL_RECALL_MAX)]
    erl = erledigt_laden()
    fk = [f for f in fk if sperre.get(f["teil"], 0) < MAX_FEHL and fg.get(f["teil"], 0) < MAX_GLOBAL and f["id"] not in belegt_fam and not ist_erledigt(f, erl)]
    fk.sort(key=lambda f: -f["pkt"])
    # FEHLTEILE AUS FOTOKANTEN (11.11., Regel 9e): gelbe Flecken der Formliste ueber alle Fotos geclustert (tools/foto_fehlteile.py). Das Kantengitter
    # (oben) ist in der Laube fast leer - das Kreuzrippengewoelbe (gelb in ~20 Fotos) wurde nie Ziel. Direkte Fotobelege zuerst; nie, solange ein
    # betroffenes Teil von einer anderen Spur belegt ist (gleicher Bildbereich, Doppelbau/Merge-Konflikt).
    if FOTO_FEHL:
        try:
            _fs = sorted([p for p in glob.glob(os.path.join(FORMDIR, "*.json")) if METRIK_SOLL in p], key=os.path.getmtime); _bel = set(os.listdir(BELEGT)); _cl = []
            if _fs:   # eigener Prozess in der GPU-Umgebung (Spuren laufen mit System-python3 ohne torch)
                _ao = os.path.join(LDIR, "foto_fehlteile.json")
                subprocess.run([PY, "-I", os.path.join(ROOT, "tools", "foto_fehlteile.py"), OBJ, "--formliste", _fs[-1], "--min_px", str(FOTO_FEHL_PX),
                                "--min_fotos", str(FOTO_FEHL_FOTOS), "--aus", _ao], capture_output=True, text=True, timeout=300)
                _cl = json.load(open(_ao))["cluster"] if os.path.exists(_ao) else []
            # 11.11.: auch Teile, die ein schon BELEGTER Foto-Cluster beruehrt, gelten als belegt (Erker 2: ff_+19_+7_+8 und ff_+19_+7_+11 parallel)
            _bel |= {t_ for c in _cl if c["id"] + "__neu" in _bel for t_ in c["teile"]}
            ffk = [dict(c, teil=c["id"] + "__neu", art="fehlteil", beleg=None, pkt=c["px"], recall_kasten=None) for c in _cl
                   if (c["px"] >= FOTO_FEHL_SUMME or (c.get("n_fotos") or 0) >= FOTO_FEHL_BELEG) and not (set(c["teile"]) & _bel)]
            # 'gebaut'-Eintraege (angenommene Fehlteile) sperren Foto-Cluster nur, solange die Formliste AELTER als die Annahme ist (11.11.: Baldachin-Cluster
            # nach Annahme erneut Ziel, Agent 'kein Bauteil'); danach entscheidet die frische Liste, ob dort noch Gelb ist.
            _fm = os.path.getmtime(_fs[-1]) if _fs else 0
            _erl_f = {k: e for k, e in erl.items() if not (str(e.get("befund", "")).startswith("gebaut") and e.get("zeit_ts", 0) and _fm > e["zeit_ts"])}
            ffk = [f for f in ffk if sperre.get(f["teil"], 0) < MAX_FEHL and fg.get(f["teil"], 0) < MAX_GLOBAL and f["id"] not in belegt_fam and not ist_erledigt(f, _erl_f)]
            # VERWIESENE TEILE (11.11.: drei Fehlteil-Runden am OG endeten alle mit 'vorhandenes Teil fensterreihe:og'): Cluster, die zu >= 25 % auf einem Teil
            # liegen, auf das schon ein Fehlteil-Befund verweist, bekommen keinen Fehlteil-Agenten mehr - der Fehler gehoert zu diesem Teil (Verweis-Vorrang unten).
            _vw = {str(e.get("befund", "")).split()[-1].replace(":", "__") for e in erl.values() if str(e.get("befund", "")).lower().startswith("vorhandenes teil")}
            _wegv = [f["id"] for f in ffk if any(f.get("teile_anteil", {}).get(t_, 0) >= 0.25 for t_ in _vw)]
            if _wegv: print(f"Foto-Cluster an verwiesene Teile ({sorted(_vw)}), kein Fehlteil-Agent: {_wegv}", flush=True)
            ffk = [f for f in ffk if f["id"] not in _wegv]
            fk = ffk + fk
        except Exception as _ex: print("foto_fehlteile:", _ex, flush=True)
    for t in fk:
        try:
            fd = os.open(os.path.join(BELEGT, t["teil"]), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, f"{LAUF} {os.getpid()}".encode()); os.close(fd)
            return t
        except FileExistsError:
            continue
    fl = formliste()
    # GLEICHER BILDBEREICH (11.11., Lehre L37): Teile mit identischen Je-Foto-Werten (rumpf_eg/laube_rueck) werden vom selben fehlenden Element
    # gedeckelt - Fehlversuche zaehlen gemeinsam, belegt einer, ist der andere gesperrt (sonst abwechselnd Leerrunden).
    for _g in gleiche_bereiche(fl):
        _m = max(fg.get(t_, 0) for t_ in _g)
        for t_ in _g: fg[t_] = _m
        if any(os.path.exists(os.path.join(BELEGT, t_)) for t_ in _g): belegt_fam |= {t_.split("__")[0] for t_ in _g}
    # Teile im Bereich belegter Foto-Cluster nicht parallel bearbeiten (11.11.: Erker-1-Cluster belegt, Verweis zog erker_polygon__0 vor)
    try:
        _ao = os.path.join(LDIR, "foto_fehlteile.json"); _b0 = set(os.listdir(BELEGT))
        _clt = {t_ for c in (json.load(open(_ao))["cluster"] if os.path.exists(_ao) else []) if c["id"] + "__neu" in _b0 for t_ in c["teile"]}
    except Exception: _clt = set()
    # TEILE NUR MIT FOTONOTE (11.11., Nutzer 'Tor ist rund, nicht spitz'): Ausschnitt-Teile (Tor/Nischen, Boolesche Differenz) fehlen in der Wolkenliste -
    # freiform__tor_b2 war schwaechstes Teil am Foto (0,49) und nie Ziel. Regel 9e: Fotonote reicht als Beleg.
    _wl = list((z or {}).get("wolkenbeleg_teile") or []); _wn = {t["teil"] for t in _wl}
    _wl += [{"teil": t_, "beleg": None, "anteil_mit_daten": 0.0, "rang_guete": None} for t_ in ((fl or {}).get("teile") or {})
            if t_ not in _wn and form_g(fl, t_).get("f1") is not None]
    kand = [t for t in _wl if t["teil"] not in _clt and (t["beleg"] is not None or form_g(fl, t["teil"]).get("f1") is not None) and (t["anteil_mit_daten"] >= MIN_DATEN or form_g(fl, t["teil"]).get("f1") is not None)
            and sperre.get(t["teil"], 0) < MAX_FEHL and fg.get(t["teil"], 0) < MAX_GLOBAL and not os.path.exists(os.path.join(BELEGT, t["teil"]))
            and t["teil"].split("__")[0] not in belegt_fam]   # gleiche Formfamilie (gleicher Generatorcode) nie parallel
    # Rang (Nutzer 10.11.): nur was die Wolke sieht und keine Brandwand ist (rang_guete aus konvergenz_bericht --nachbarn); Teile ohne
    # sichtbare freie Flaeche (rang None) ans Ende - dort hilft nur ein neues Foto (Fotoplan), kein Agent.
    def _rang(t):   # Foto zuerst: kleinster Foto-F1; nur Teile ohne Fotomessung nach der alten Guete (dahinter)
        ff = form_g(fl, t["teil"]).get("f1")
        if ff is not None: return (0, ff)
        r = t.get("rang_guete") if "rang_guete" in t else guete(t)
        return (1 if r is not None else 2, r if r is not None else 9)
    kand.sort(key=_rang)
    # VERWEIS AUS FEHLTEIL-BEFUND (11.11., L36): 'FEHLTEIL-BEFUND: vorhandenes Teil erker_polygon:0' = groesster gelber Foto-Cluster gehoert zu einem
    # VORHANDENEN Teil (Erker-Rippennetz). Dieses Teil einmal vor die Rangfolge (dort liegt der groesste sichtbare Fehler); 'weitergereicht' markiert es.
    erl_v = {}
    for fid, e in erl.items():
        bf = str(e.get("befund", ""))
        if bf.lower().startswith("vorhandenes teil") and not e.get("weitergereicht"): erl_v.setdefault(bf.split()[-1].replace(":", "__"), fid)
    if erl_v: kand.sort(key=lambda t: 0 if t["teil"] in erl_v else 1)   # stabil: sonst Rang wie oben
    # Nutzerregel 10.11. 14:4x: IMMER das schwaechste Teil zuerst ("dann konvergieren wir"). Frueher gingen offene Beobachtungen vor -
    # 7/7 Runden landeten auf Teilen mit 0,94-0,98 (kaum Spielraum, kleine Fehler = Rueckschritt). Offene Beobachtungen zu dem gewaehlten
    # Teil reisen jetzt MIT in den Auftrag (Zielart beobachtung), bestimmen aber nicht mehr die Reihenfolge.
    _istn = lambda b: "nutzer" in str(b.get("wer", "")).lower()
    bz = {}
    # Nutzerbefund vor eigenem Befund desselben Teils, je Gruppe der NEUESTE zuerst (11.11. a105629: aeltere Kapitell-Beobachtung wurde Ziel,
    # die Funde von heute (Sockel, Stirnboegen) blieben liegen; masstabelle haengt neue Beobachtungen hinten an)
    _bzl = beob_ziele(z)
    for b in sorted(_bzl, key=lambda b: (0 if _istn(b["beob"]) else 1, 0 if b["beob"].get("formfamilie_test") else 1, -_bzl.index(b))):   # Formfund (formfamilie_test) vor Lagebefund (a112731 nahm Giebel-Versatz statt Treppe)
        bk = beob_schluessel(b["beob"])
        if sperre.get(bk, 0) < MAX_FEHL and fg.get(bk, 0) < MAX_GLOBAL: bz.setdefault(b["teil"], b)
    # NUTZERENTSCHEID 11.11. ("Nutzerfunde zuerst"): Teile mit offenem NUTZER-Sichtfund (masstabelle, wer enthaelt 'Nutzer', nicht erledigt,
    # Befund nicht gesperrt) vor die Rangfolge "schwaechstes Teil zuerst" (10.11.); deren Teile lagen oft im Mittelfeld und kamen nie dran.
    # Tor/Pruefer unveraendert. Abschalten: --nutzer_zuerst 0.
    if opt("--nutzer_zuerst", 1, int):
        try: _B = json.load(open(os.path.join(ROOT, "modelle", OBJ, "masstabelle.json"))).get("beobachtungen_offen") or []
        except Exception: _B = []
        nutz = {str(b["teil"]).replace(":", "__") for b in _B if isinstance(b, dict) and b.get("teil") and not b.get("erledigt") and _istn(b)
                and sperre.get(beob_schluessel(b), 0) < MAX_FEHL and fg.get(beob_schluessel(b), 0) < MAX_GLOBAL}
        if nutz & {t["teil"] for t in kand}:
            kand.sort(key=lambda t: 0 if t["teil"] in nutz else 1)
            print("Nutzerfunde zuerst:", [t["teil"] for t in kand if t["teil"] in nutz], flush=True)
    for t in kand:   # atomar belegen (O_EXCL), damit zwei Spuren nie dasselbe Teil nehmen
        try:
            fd = os.open(os.path.join(BELEGT, t["teil"]), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, f"{LAUF} {os.getpid()}".encode()); os.close(fd)
            if t["teil"] in erl_v:
                import fcntl as _f; _lk = open(ERLEDIGT + ".lock", "w"); _f.flock(_lk, _f.LOCK_EX)
                _e = erledigt_laden()
                for _fid, _ee in _e.items():   # alle Verweise auf dieses Teil (11.11.: zwei Befunde -> Erker 2 zweimal vorgezogen)
                    if str(_ee.get("befund", "")).lower().startswith("vorhandenes teil") and str(_ee["befund"]).split()[-1].replace(":", "__") == t["teil"] and not _ee.get("weitergereicht"):
                        _ee["weitergereicht"] = f"{LAUF} {time.strftime('%Y-%m-%d %H:%M')}"
                json.dump(_e, open(ERLEDIGT, "w"), ensure_ascii=False, indent=1); _f.flock(_lk, _f.LOCK_UN); _lk.close()
                print(f"Verweis aus Fehlteil-Befund {erl_v[t['teil']]} -> Ziel {t['teil']} vorgezogen", flush=True)
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

def gleiche_bereiche(fl, n=6, tol=0.02, min_gleich=3):
    """Gruppen von Teilen mit (fast) GLEICHEM Bildbereich (L37): auf >= min_gleich ihrer n staerksten Fotos weichen sichtbare Pixel und
    Kantenpixel um < tol (relativ) ab (rumpf_eg/laube_rueck: 6174 862304 vs 862370 px). Einzelverkettung ueber Paare."""
    E = {}
    for t, je in ((fl or {}).get("teile") or {}).items():
        if "__ausschnitt" in t: continue
        e = {k: v for k, v in je.items() if k != "_gesamt" and isinstance(v, dict) and "mk_px" in v and v.get("sicht_px")}
        E[t] = {k: e[k] for k in sorted(e, key=lambda k: -(e[k]["mk_px"] + e[k]["fk_px"]))[:n]}
    T = sorted(E); par = {t: t for t in T}
    def f(x):
        while par[x] != x: x = par[x]
        return x
    nah = lambda a, b: abs(a - b) <= tol * max(a, b, 1)
    for i, a in enumerate(T):
        for b in T[i + 1:]:
            g = [k for k in E[a] if k in E[b] and nah(E[a][k]["sicht_px"], E[b][k]["sicht_px"]) and nah(E[a][k]["mk_px"], E[b][k]["mk_px"])]
            if len(g) >= min_gleich: par[f(a)] = f(b)
    gr = {}
    for t in T: gr.setdefault(f(t), []).append(t)
    return [g for g in gr.values() if len(g) > 1]
def beob_zu_teilen(teile):
    """Offene Beobachtungen (masstabelle) der betroffenen Teile als Text fuer Fehlteil-Auftraege aus Fotokanten (11.11.: Erker-Rippennetz-
    Formbeschreibung haengt am Teil erker_polygon:0, der Fehlteil-Agent fuer den Cluster an der Erker-Unterseite sah sie sonst nicht)."""
    try: B = json.load(open(os.path.join(ROOT, "modelle", OBJ, "masstabelle.json"))).get("beobachtungen_offen") or []
    except Exception: return ""
    tt = {t.replace("__", ":") for t in teile}; z = []
    # 11.11.: neueste und Nutzer-Beobachtungen zuerst (z[:6] schnitt die frischen Nutzer-Sichtfunde ab, aelteste standen vorn)
    B = sorted([b for b in B if isinstance(b, dict)], key=lambda b: str(b.get("datum", "")), reverse=True); B = sorted(B, key=lambda b: 0 if "nutzer" in str(b.get("wer", "")).lower() else 1)
    for b in B:
        if isinstance(b, dict) and not b.get("erledigt") and str(b.get("teil", "")).split(" ")[0] in tt:
            extra = " | ".join(str(v) for k, v in b.items() if k.startswith(("stufe0", "naechster_schritt", "teil_hinweis")))
            z.append(f"[{b.get('teil')}] {b.get('merkmal')}: {str(b.get('text', ''))[:500]}" + (f" || {extra[:1500]}" if extra else ""))
    return ("OFFENE BEOBACHTUNGEN der betroffenen Teile (masstabelle.json, zuerst lesen): " + " ### ".join(z[:6]) + " ") if z else ""
def _kasten_ueberlappt(z, lo, hi):
    zl, zh = z.get("lo"), z.get("hi")
    return bool(zl and zh and lo and hi and all(zl[i] <= hi[i] and lo[i] <= zh[i] for i in range(3)))
def vorversuche(teil, kasten=None):
    """Alle frueheren Kreis-Runden (alle Laeufe/Spuren) zu diesem Teil: Ergebnis, Torgruende, Agentenbericht, Patch.
    Damit wiederholt kein Agent einen verworfenen Weg blind (Kreis1 R2 10.11. startete Staffelgiebel ohne Wissen aus R1)."""
    zeilen = []
    for d in sorted(glob.glob(os.path.join(KREISDIR, OBJ, "*", "kreis.jsonl"))):
        for l in open(d):
            try: z = json.loads(l)
            except Exception: continue
            _zz = z.get("ziel") or {}
            if "runde" not in z or z.get("angenommen") is None: continue
            # Fehlteil-Ziele: auch fruehere Fehlteil-Runden mit UEBERLAPPENDEM Kasten (Kantengitter-ID fk_* vs Fotokanten-ID ff_* - gleiche Stelle,
            # 11.11.: Baldachine 234159 verwarf das alte Gitter-Tor, am Foto +0,25 - der Patch muss beim naechsten Agenten ankommen)
            if _zz.get("teil") != teil and not (kasten and str(_zz.get("teil", "")).endswith("__neu") and _kasten_ueberlappt(_zz, *kasten)): continue
            ld = os.path.dirname(d); r = z["runde"]
            pa = os.path.join(ld, f"verworfen_r{r}.patch"); ag = os.path.join(ld, f"agent_r{r}.log")
            zeilen.append(f"- {os.path.basename(ld)} R{r}: angenommen={z.get('angenommen')}, Gewinn {z.get('gewinn')}, Abnahme {z.get('tor_abnahme')}"
                          f"{' (CUDA-OOM, kein Pruefungsfehler)' if z.get('infra_oom') else ''}, Pruefer {json.dumps((z.get('pruefer') or {}).get('fehlerliste'), ensure_ascii=False)[:600]}"
                          f"; Agentenbericht (Ende der Datei): {ag if os.path.exists(ag) else '-'}; Patch: {pa if os.path.exists(pa) else '-'}; Zweig (git show/diff): {z.get('branch') or '-'}"
                          + nicht_in_main(z, os.path.basename(ld), r)
                          + (" [ALTES Fehlteil-Tor 'region' = nur Kantengitter, Foto nie gemessen - Patch kann am Foto trotzdem gut sein, pruefen!]" if (str(_zz.get("teil", "")).endswith("__neu") and z.get("tor") != "foto_neu") else ""))
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
        _quelle = (f"Automatisch aus den FOTOKANTEN (tools/foto_fehlteile.py, Regel 9e): in {ziel.get('n_fotos')} Fotos ({', '.join((ziel.get('fotos') or [])[:12])}) "
                   f"liegen gelbe Flecken (Fotokante ohne Modellkante, zusammen {ziel['pkt']} px) auf der Modellflaeche im Kasten {ziel['lo']} .. {ziel['hi']} "
                   f"(Modellrahmen, m; Weltpunkt = Treffer auf dem VORHANDENEN Modell, das fehlende Element liegt davor, z. B. Gewoelbe vor Wand/Decke). "
                   f"Betroffene Teilbereiche: {', '.join(ziel.get('teile') or [])}. Overlays je Teil und Foto: Formliste bilder_dir. "
                   + beob_zu_teilen(ziel.get("teile") or [])
                   if ziel.get("quelle") == "fotokanten" else
                   f"Automatisch aus konvergenz_bericht (Abschnitt 8 Fehlkanten): Im Kasten {ziel['lo']} .. {ziel['hi']} (Modellrahmen, m) liegen "
                   f"{ziel['pkt']} Punkte des Kantengitters (Fotokanten aus mehreren Fotos), die keine Modellflaeche naeher als 0,3 m haben; "
                   f"Recall der Fotokanten im Kasten nur {ziel['recall_kasten']}. ")
        befund = (_quelle + f"Dort fehlt sehr wahrscheinlich ein Bauteil (oder ein vorhandenes ist "
                  f"an der falschen Stelle). Stufe 0: Stelle in >= 3 Fotos finden (Kasten in die kalibrierten Fotos projizieren), Element benennen und "
                  f"Formfamilie festlegen; dann als NEUES Bauteil mit beleg()/Quelle im Generator bauen (oder vorhandenes Teil dorthin korrigieren). "
                  f"Gate (FOTO, Regel 9e): im Bildbereich des neuen Teils muss die Foto-F1 (teil_fotoform, vorher ohne / nachher mit dem Teil, gleiche 10 Fotos) "
                  f"um >= {MIN_GEWINN_FOTO} steigen, Foto-Praezision des neuen Teils >= {MIN_PRAEZ_NEU} (keine erfundenen Kanten), kein vorhandenes Teil darf "
                  f"in der Guete um > 0,02 fallen (Lage-Veto). Kantengitter-Werte sind nur Beobachtung. Leere Wolke ist KEIN Grund, nicht zu bauen. "
                  f"Wenn die Fotos dort NICHTS zeigen (Gitterfehler, Hintergrund), das als Befund berichten und nichts bauen. "
                  f"PFLICHT: letzte Zeile deiner Antwort GENAU eine von 'FEHLTEIL-BEFUND: gebaut' | 'FEHLTEIL-BEFUND: kein Bauteil' | "
                  f"'FEHLTEIL-BEFUND: Gitter zu duenn' | 'FEHLTEIL-BEFUND: vorhandenes Teil <typ:name>' (z. B. staffelgiebel:west, wenn ein vorhandenes Teil "
                  f"falsch liegt/zu hoch ist und du es NICHT in dieser Runde korrigierst). Danach wird der Kasten nicht erneut vergeben.")
    else:
        _wtxt = (f"Automatisch aus konvergenz_bericht (Wolkenbeleg je Bauteil): {typ} hat nur {ziel['beleg']:.2f} seiner datennahen "
                 f"Flaeche auf der Wolke (Median-Abstand {ziel['median_m']:.2f} m, Anteil mit Daten {ziel['anteil_mit_daten']:.2f}). "
                 if ziel.get("beleg") is not None and ziel.get("median_m") is not None else
                 f"{typ} hat keinen Wolkenbeleg (Ausschnitt/Boolesche Differenz oder ausserhalb der Wolkenliste) - Ziel nach FOTONOTE (Regel 9e). ")
        befund = (_wtxt + beob_zu_teilen([ziel["teil"]]) +   # 11.11.: Bogenreihe-Agent sah die Nutzerbeobachtungen (Sockel, Stirnboegen) nicht - nur Fehlteil-Auftraege bekamen sie
                  
              f"Fotokanten (Kantengitter aus Fotos) je Teil: Recall {ziel.get('kanten_recall')} (Anteil der Fotokanten am Teil, die das Modell erklaert), "
              f"Praezision {ziel.get('kanten_praez')} (Anteil der Teil-Formkanten, die ein Foto belegt). GATE (Foto zuerst): die FORM AM FOTO (Foto-F1, unten) muss um >= {MIN_GEWINN_FOTO} steigen; "
              f"Wolkenbeleg und Gitter-F1 duerfen nur nicht um > 0,02 fallen (Wolkenbeleg nur, wenn Anteil mit Daten >= {MIN_DATEN}). "
              f"Arbeite an den Fotos: rote/gelbe Kanten im Teil beseitigen. Verdeckte Flaechen zaehlen nicht (nur kamera-zugewandt). "
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
            _tf = set(form_fotos(formliste(), ziel["teil"])); _je = {k: v for k, v in _je.items() if k in _tf}   # nur Torfotos nennen, Kontrollfotos bleiben unbekannt
            _schl = sorted(_je, key=lambda k: _je[k]["praez"] + _je[k]["recall"])[:3]
            _fl = "; ".join(f"Foto {k}: Praez {_je[k]['praez']}, Recall {_je[k]['recall']}, gelbe Flecken (Fotokante OHNE Modell) bei {[f['xyz'] for f in _je[k]['gelb']]}, "
                            f"rote (Modellkante OHNE Foto) bei {[f['xyz'] for f in _je[k]['rot']]}" for k in _schl)
            befund += (f" FORM AM FOTO (tools/teil_fotoform.py, Schwelle 0,14 m, je kalibriertem Foto, verdeckte Pixel ausgenommen): F1 {_g['f1']} "
                       f"(Praezision {_g['praez']} = Modellkanten mit Fotokante, Recall {_g['recall']} = Fotokanten mit Modellkante) ueber {_g['fotos']} Fotos. "
                       f"Schwaechste: {_fl}. Bilder: {formliste().get('bilder_dir', FORMDIR)}/{ziel['teil']}_<foto>.jpg NUR fuer die Torfotos {sorted(_tf)} ansehen (gruen passt, rot erfunden, gelb fehlt). "
                       f"Gelb im Teil = Form fehlt (Fenster, Rippen, Pfeiler, Ueberstand); rot = Form falsch/zu viel. Der Foto-F1 IST der Torwert (muss um >= {MIN_GEWINN_FOTO} steigen). Zusaetzlich Veto: Hoehen-Wert f1_h (nur waagerechte Kanten: Traufen, Gesimse, Stufen, Oberkanten; im Bericht _gesamt.f1_h) darf um hoechstens 0,02 fallen - Hoehenfehler sieht der Foto-F1 kaum. "
                       f"Eigene Zwischenmessung IMMER auf ALLEN 10 Torfotos, nie auf einer Teilmenge (10.11.: Westgiebel 0,73-0,81 auf 6 selbst gewaehlten Fotos, auf allen 10 ein Rueckschritt 0,413->0,394). Das Tor prueft zusaetzlich auf weiteren Kontrollfotos, die du nicht kennst - nur echte Formverbesserungen bestehen. SCHNELL (Stufe halbe Aufloesung, ~1 min statt ~10, gleiche Richtung wie das Tor, Betrag kleiner; "
                       f"so misst auch die Vorpruefung): Variante vorher und nachher je einmal mit RCPARK_FOTO_SKALA={SKALA_VOR} vor dem Befehl messen und nur diese beiden Werte vergleichen; Endtor misst voll. bauen_abnehmen.sh nur EINMAL ganz am Ende laufen lassen (10.11.: Agenten liessen es bis zu 3x laufen, je 10-20 min; das Tor prueft ohnehin selbst): "
                       f"RCPARK_FOTO_SKALA={SKALA_VOR} {PY} -W ignore -I tools/teil_fotoform.py {OBJ} --nur {ziel['teil']} --fotos {','.join(form_fotos(formliste(), ziel['teil']))} --aus {LDIR}/ff_eigen.json --bilder_dir {LDIR}/ff_eigen_bilder")
    txt = (txt.replace("`<OBJEKT>`", OBJ).replace("<OBJEKT>", OBJ).replace("`<BAUTEIL>`", typ).replace("<BAUTEIL>", typ)
              .replace("`<BEFUND>`", befund).replace("<BEFUND>", befund).replace("<RUNDE>", f"kreis{runde}")
              .replace("`<TABU>`", ", ".join(TABU) or "-").replace("<TABU>", ", ".join(TABU) or "-")
              .replace("`<FOTOS>`", "-").replace("<FOTOS>", "-"))
    txt = txt.replace("/home/oem/git/rc-park", wt)
    txt += vorversuche(ziel["teil"], (ziel.get("lo"), ziel.get("hi")) if ist_fehlteil(ziel) else None)
    txt += (f"\n\nUNBEAUFSICHTIGTER LAUF: Arbeitsverzeichnis ist der git-Worktree {wt} (nicht /home/oem/git/rc-park). "
            "Keine Rueckfragen moeglich - bei Unklarheit ANNAHME notieren und weiter. Am Ende den Bericht (Pflichtform der Vorlage) "
            f"zusaetzlich nach {wt}/modelle/{OBJ}/audit/kreis_bericht.md schreiben und die Overlay-Pfade dort auflisten.")
    return txt

def pruefer_urteil(wt, ziel, runde, vs_info=None):
    p = (f"Du bist der Pruefer nach modelle/VORLAGE_BAUTEIL_RUNDE.md (Abschnitt Pruefer-Checkliste) im Worktree {wt}, Objekt {OBJ}, "
         f"Bauteil {ziel['teil'].replace('__', ':')}" + (f" (FEHLENDES ELEMENT im Kasten {ziel['lo']} .. {ziel['hi']} m: neues Teil muss dort echte Fotokanten treffen, nichts erfunden)" if ist_fehlteil(ziel) else "") + f". Lies {wt}/modelle/{OBJ}/audit/kreis_bericht.md, sieh dir JEDES dort genannte Overlay "
         f"und {wt}/modelle/{OBJ}/audit/seiten.jpg selbst an. Pruefe: Formbeschreibung vollstaendig und passend zu den Fotos? Formpruefung je Foto vorher/nachher: {LDIR}/fotoform_bilder/{ziel['teil']}_*_r{runde}_vorher.jpg und _nachher.jpg "
         f"(gelb = Fotokante ohne Modell = fehlende Form, rot = erfundene Form) ansehen und gelbe Reste in die Fehlerliste. Trifft das Teil "
         "die Fotos besser als vorher? Neue Fehler an anderen Teilen? Nichts schoenreden, Agenten-'ok' nie uebernehmen. Aendere KEINE Dateien. "
         'Letzte Zeile deiner Antwort GENAU: URTEIL {"annehmen": true|false, "fehlerliste": ["..."]}')
    if vs_info:   # L46: Dichte-Verdacht sichtbar machen
        p += (f" VERSCHIEBUNGSKONTROLLE (dasselbe Teil 0,3 m versetzt am Foto gemessen): {json.dumps(vs_info, ensure_ascii=False)}. "
              "marge_min <= 0 = DICHTE-VERDACHT: versetzte Kopie trifft die Fotokanten genauso gut, der Foto-Gewinn belegt dann NICHT die Lage/Form - "
              "annehmen nur, wenn du die Lage in den Vorher/Nachher-Bildern selbst klar bestaetigst, und das in der Begruendung nennen. "
              "0 < marge_min < 0,03 = schwach belegt. konkat_gueltig false = Kontrolle fuer dieses (abgezogene) Teil nicht beurteilbar.")
    rc, out = sh(["claude", "-p", p, "--model", PRUEFER, "--permission-mode", "plan"], wt,
                 log=os.path.join(LDIR, f"pruefer_r{runde}.log"), timeout=MAX_MIN * 60)
    # 11.11.: Urteil per raw_decode ab der Klammer lesen - gieriges '\{.*\}' nahm Folgetext derselben Zeile mit ("Extra data"),
    # ein ANGENOMMENES Gewoelbe (+0,301, Kontrollfotos 0,689 -> 0,834) wurde so als "nicht lesbar" verworfen.
    try:
        _i = [mm.end() for mm in re.finditer(r"URTEIL\s*(?=\{)", out)][-1]
        return json.JSONDecoder().raw_decode(out[_i:])[0]
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
    # 11.11. (L34-Pfadluecke): Nachpruefen misst KEIN Foto-Tor (vorher-Formwert fehlt) und entscheidet nach Wolkenguete. Nur fuer Infra-Abbrueche
    # (OOM/Platz) gedacht; nach Tor-Codeaenderungen statt dessen --ziel <teil> --patch <verworfen_rN.patch> (voller Foto-Tor-Weg auf aktuellem main).
    print("HINWEIS nachpruefen: ohne Foto-Tor (Wolkenguete) - fuer Torfragen --ziel/--patch benutzen", flush=True)
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
            # 11.11. (Kreis wartete 15,5 h je 6 h auf die GPU): Schluessel nur aus dem, was Export + konvergenz_bericht wirklich lesen.
            # masstabelle.json liest keiner von beiden (nur ueber pruefbericht.json, das eingecheckt ist) -> pruefbericht + audit statt masstabelle;
            # Werkzeuge ohne Einfluss auf die Messung (Kreis-Steuerung, Viewer, Sichtpruefungen) aus dem tools-Hash nehmen. Jede ANDERE
            # Werkzeugaenderung macht den Speicher weiter ungueltig (sicher statt schnell).
            _ohne = {"bauteil_kreis.py", "kreis_regler.py", "formfamilie_pruefen.py", "test_formfamilie_nutzerfunde.py", "viewer_kanten_bauen.py",
                     "viewer_kanten_vorlage.html", "beobachtung_aus_viewer.py", "teil_fotoform.py", "tor_verschiebung.py", "realitaet_prozent.py"}
            _lt = subprocess.run(["git", "-C", wt, "ls-tree", "-r", "HEAD", "tools"], capture_output=True, text=True).stdout.splitlines()
            _h = [hashlib.sha256("\n".join(l for l in _lt if l.split("\t")[-1].split("/")[-1] not in _ohne).encode()).hexdigest()] + \
                 subprocess.run(["git", "-C", wt, "rev-parse", f"HEAD:modelle/{OBJ}/objekt.json", f"HEAD:modelle/{OBJ}/pruefbericht.json", f"HEAD:modelle/{OBJ}/audit"],
                                capture_output=True, text=True).stdout.split()
            _key = hashlib.sha256((open(sp, "rb").read() if os.path.exists(sp) else b"") + " ".join(_h).encode()).hexdigest()[:20]
            _vd = os.path.join(KREISDIR, OBJ, "vorher_speicher"); os.makedirs(_vd, exist_ok=True)
            _zf, _td = os.path.join(_vd, _key + ".json"), os.path.join(LDIR, f"teile_r{runde}_vorher")
            with open(os.path.join(_vd, _key + ".lock"), "w") as _lk:
                fcntl.flock(_lk, fcntl.LOCK_EX)
                if os.path.exists(_zf) and os.path.isdir(os.path.join(_vd, _key)):
                    z0 = json.load(open(_zf)); shutil.copytree(os.path.join(_vd, _key), _td, dirs_exist_ok=True)
                    with open(kf, "a") as f: f.write(json.dumps(dict(z0, etikett=f"kreis {LAUF} r{runde}_vorher"), ensure_ascii=False) + "\n")
                    print(f"Runde {runde}: Messung vorher aus Spurenspeicher {_key} (gleicher STL, Mess-Werkzeuge, Pruefbericht)")
                else:
                    rc0, z0, out0 = messen(wt, f"r{runde}_vorher")
                    if rc0 in (0, 3) and z0 and len(_h) == 3 and z0.get("stl_sha") == hashlib.sha256(open(sp, "rb").read()).hexdigest()[:16]:
                        shutil.copytree(_td, os.path.join(_vd, _key), dirs_exist_ok=True); json.dump(z0, open(_zf + ".tmp", "w"), ensure_ascii=False); os.replace(_zf + ".tmp", _zf)
    ziel = NACH_Z["ziel"] if NACH else (ziel_fest(z0) if ZIEL else waehlen(z0, sperre))
    if not ziel:
        if not TROCKEN and not NACH and wt != ROOT:   # 10.11.: leere Spuren liessen je 500 MB Worktree liegen (Datenplatte auf 10,0 GB); unveraendert = Commit, verlustfrei
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", wt], capture_output=True)   # ohne --force: bricht ab, falls doch etwas geaendert ist
        print("kein Kandidat mehr - Ende"); protokoll({"runde": runde, "ende": "kein Kandidat"}); break
    txt = auftrag(ziel, runde, wt)
    open(os.path.join(LDIR, f"auftrag_r{runde}.md"), "w").write(txt)
    print(f"Runde {runde}: Ziel {ziel['teil']} ({'Fehlteil ' + str(ziel['pkt']) + ' Pkt, Recall Kasten ' + str(ziel['recall_kasten']) if ist_fehlteil(ziel) else 'Wolkenbeleg ' + str(ziel['beleg'])}) -> Auftrag {LDIR}/auftrag_r{runde}.md")
    if TROCKEN:
        freigeben(ziel["teil"]); protokoll({"runde": runde, "trocken": True, "ziel": ziel}); print(txt[:1500]); break
    ff_v, ff_fotos, kf_fotos, kf_v = None, [], [], None; _ff_spaet = None; _vs_teil = None
    if not ist_fehlteil(ziel) and not TROCKEN and not NACH:   # Form am Foto VOR dem Agenten (Basisstand), gleiche Fotos nachher
        _fl = formliste(); ff_fotos = form_fotos(_fl, ziel["teil"])
        if KONTROLLE:
            kf_fotos = kontroll_fotos(_fl, ziel["teil"]); kf_v = form_aus_liste(_fl, wt, ziel["teil"], kf_fotos, runde, nebenwirkung=False, jtag="kontrolle_vorher") if kf_fotos else None
        _fv = form_aus_liste(_fl, wt, ziel["teil"], ff_fotos, runde) if ff_fotos else None
        if _fv is not None:
            ff_v = _fv; print(f"Runde {runde}: Form am Foto vorher {ziel['teil']}: F1 {ff_v} ({len(ff_fotos)} Fotos, aus Formliste {_fl.get('stl_sha')})")
            _tvf = os.path.join(LDIR, f"teile_r{runde}_vorher_form")   # Vorher-Teile fuer den Festbereich der Nachher-Messung (CPU, ~1 s)
            if not glob.glob(os.path.join(_tvf, "*.stl")):
                sh_cpu(json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"], wt, log=os.path.join(LDIR, f"export_r{runde}_vorher_form.log"), env={"BAUTEILE_AUS": _tvf})
        elif ff_fotos and VORPRUEF and SKALA_VOR != 1.0 and formliste_halb(wt) is not None:
            # VOLLER VORHER-WERT AUFGESCHOBEN (10.11. abends): volle Formliste passt nicht zum main-STL (nach jedem Merge ~40 min GPU), die halbe schon.
            # Vorpruefung braucht nur halb; voll gemessen wird erst, wenn die halbe Stufe Gewinn zeigt. Teile + Gesamt-STL des Basisstands jetzt sichern (CPU).
            _tv = os.path.join(LDIR, f"teile_r{runde}_vorher_form")
            _gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
            sh_cpu(_gen, wt, log=os.path.join(LDIR, f"export_r{runde}_vorher_form.log"), env={"BAUTEILE_AUS": _tv})
            _sv = os.path.join(LDIR, f"stl_r{runde}_vorher.stl"); shutil.copy2(os.path.join(wt, STL), _sv); _ff_spaet = (_tv, _sv)
            print(f"Runde {runde}: Form am Foto vorher {ziel['teil']}: voller Wert aufgeschoben (nur Kandidaten), Vorpruefung auf halber Formliste", flush=True)
        elif ff_fotos:
            _tv = os.path.join(LDIR, f"teile_r{runde}_vorher")   # Export der Vorher-Messung (gleicher Stand, Agent lief noch nicht) - zweiter Export war doppelt
            if not glob.glob(os.path.join(_tv, "*.stl")):
                _tv = os.path.join(LDIR, f"teile_r{runde}_vorher_form")
                _gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
                sh_cpu(_gen, wt, log=os.path.join(LDIR, f"export_r{runde}_vorher_form.log"), env={"BAUTEILE_AUS": _tv})
            ff_v = form_messen(wt, _tv, ziel["teil"], ff_fotos, f"r{runde}_vorher")
            print(f"Runde {runde}: Form am Foto vorher {ziel['teil']}: F1 {ff_v} ({len(ff_fotos)} Fotos)")
    _fehl_vor = None
    if ist_fehlteil(ziel) and not TROCKEN and not NACH:   # Foto-Tor fuer neue Teile (11.11., Regel 9e): Basisstand sichern (Teile + Gesamt-STL, CPU)
        _tvf = os.path.join(LDIR, f"teile_r{runde}_vorher_form"); _svf = os.path.join(LDIR, f"stl_r{runde}_vorher.stl")
        try:
            if not glob.glob(os.path.join(_tvf, "*.stl")):
                sh_cpu(json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"], wt, log=os.path.join(LDIR, f"export_r{runde}_vorher_form.log"), env={"BAUTEILE_AUS": _tvf})
            shutil.copy2(os.path.join(wt, STL), _svf); _fehl_vor = (_tvf, _svf, formliste())
        except Exception as _ex: print(f"Runde {runde}: Basisstand fuer Fehlteil-Fototor nicht gesichert: {_ex}", flush=True)
    t0 = time.time(); _agent_leer = False
    if PATCH:   # Agentenarbeit aus abgebrochener Runde uebernehmen statt neuen Agenten (gleiches Tor danach)
        # 11.11.: verworfen_rN.patch enthaelt erzeugte Dateien (STL, Teile, Audit, Pruefbericht) - nach jedem main-Merge passen die nie -> ausschliessen, werden neu gebaut
        _ex = [f"--exclude={x}" for x in ("modelle/stl/*", "modelle/stl/*/*", "modelle/stl/*/*/*", f"modelle/{OBJ}/audit/*", f"modelle/{OBJ}/audit/*/*",
                                          f"modelle/{OBJ}/pruefbericht.json", f"modelle/{OBJ}/MASSNACHWEIS.md", f"modelle/{OBJ}/konvergenz.jsonl")]
        # 11.11. a020500: der Vorher-Export schreibt elemente.json neu -> '--3way: entspricht nicht der Version im Index'. Vom Patch beruehrte Dateien,
        # die nur der Export veraendert hat, auf HEAD zuruecksetzen (der Bau danach erzeugt sie aus dem gepatchten Generator neu).
        _pp = [l.split("\t", 2)[-1] for l in subprocess.run(["git", "-C", wt, "apply", "--numstat"] + _ex + [PATCH], capture_output=True, text=True).stdout.splitlines() if "\t" in l]
        _mod = set(subprocess.run(["git", "-C", wt, "diff", "--name-only"], capture_output=True, text=True).stdout.split())
        if set(_pp) & _mod: subprocess.run(["git", "-C", wt, "checkout", "--"] + sorted(set(_pp) & _mod), capture_output=True); print(f"Runde {runde}: vor Patch zurueckgesetzt (Export-Reste): {sorted(set(_pp) & _mod)}", flush=True)
        rcA = subprocess.run(["git", "-C", wt, "apply", "--whitespace=nowarn"] + _ex + [PATCH], capture_output=True, text=True).returncode
        if rcA != 0:   # Patch aelter als main (masstabelle.json wuchs): 3-Wege-Anwendung
            for _v in range(3):   # 11.11. a014000/a015000: rc=1 zur Laufzeit, von Hand sofort sauber -> vorruebergehend (paralleles Git der Spuren?), wiederholen
                _ra = subprocess.run(["git", "-C", wt, "apply", "--3way"] + _ex + [PATCH], capture_output=True, text=True); rcA = _ra.returncode
                if rcA == 0: break
                print(f"git apply --3way Versuch {_v + 1}:", "\n".join(l for l in (_ra.stderr or "").splitlines() if "Ausweichen" not in l and "sauber angewendet" not in l
                                                                    and "Falling back" not in l and "Applied patch" not in l)[:1500], flush=True)
                subprocess.run(["git", "-C", wt, "reset", "-q", "--merge"], capture_output=True); time.sleep(20)
        print(f"Runde {runde}: Patch {PATCH} uebernommen rc={rcA}", flush=True)
        if rcA != 0: freigeben(ziel["teil"]); sys.exit("Patch passt nicht auf main")
    else:
        rcA, _ = (None, "") if NACH else sh(["claude", "-p", txt, "--model", MODELL, "--permission-mode", RECHTE], wt,
                    log=os.path.join(LDIR, f"agent_r{runde}.log"), timeout=MAX_MIN * 60)
    # VORPRUEFUNG (Nutzer 10.11. 14:3x, 5 von 5 Runden erst im Tor nach 1-1,5 h verworfen, meist Foto-F1 gefallen oder Pflichtschritt
    # uebersprungen): gleich nach dem Agenten Form am Foto messen (gleiche Fotos, gleiche Formel wie das Tor). Keine klare Besserung
    # (Foto-Veto wuerde greifen: < vorher - 0,02) -> EINMAL zurueck an denselben Agenten (claude --continue im Worktree, Kontext bleibt) mit Messwerten je Foto
    # und Overlay-Pfaden. Das Tor bleibt unveraendert (gleiche Schwellen, misst danach selbst) - nur der Rueckweg ist frueher.
    _tn = os.path.join(LDIR, f"teile_r{runde}_nachher"); _vorab_gebaut = False; ff_q = None; _halb = False
    if (ff_v is not None or _ff_spaet) and not ist_fehlteil(ziel) and not NACH and VORPRUEF:
        shutil.rmtree(_tn, ignore_errors=True)
        _gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
        _rq, _ = sh_cpu(_gen, wt, log=os.path.join(LDIR, f"vorpruef_r{runde}.log"), env={"BAUTEILE_AUS": _tn})
        _diff0 = subprocess.run(["git", "-C", wt, "status", "--porcelain", "--", "tools", "modelle/" + OBJ + "/objekt.json"], capture_output=True, text=True).stdout.strip()
        _flh = formliste_halb(wt) if SKALA_VOR != 1.0 else None
        _vh = form_aus_liste(_flh, wt, ziel["teil"], ff_fotos, runde, nebenwirkung=False, hkey=f"r{runde}_vorher_halb") if _flh else None
        _halb = _vh is not None; _vq = _vh if _halb else ff_v; _vk = "vorher_halb" if _halb else "vorher"
        if _vq is None and _ff_spaet:   # Teil/Fotos fehlen in der halben Liste: vollen Vorher-Wert doch jetzt messen (Basisstand gesichert)
            ff_v = _vq = form_messen(wt, _ff_spaet[0], ziel["teil"], ff_fotos, f"r{runde}_vorher", stl=_ff_spaet[1]); _ff_spaet = None
        ff_q = (_vq if not _diff0 else form_messen(wt, _tn, ziel["teil"], ff_fotos, f"r{runde}_vorpruef", env={"RCPARK_FOTO_SKALA": str(SKALA_VOR)} if _halb else None)) if _rq == 0 else None   # ohne Aenderung = vorher (a203713: 341 s fuer Delta 0)
        if not _diff0 and _halb: HOEHE[f"r{runde}_vorpruef"] = HOEHE.get(f"r{runde}_vorher_halb")
        print(f"Runde {runde}: Vorpruefung Form am Foto {ziel['teil']}" + (f" (Stufe halbe Aufloesung {SKALA_VOR})" if _halb else "") + f": F1 {_vq} -> {ff_q}" + ("" if _rq == 0 else " (Generator rot)"), flush=True)
        _diff = subprocess.run(["git", "-C", wt, "status", "--porcelain", "--", "tools", "modelle/" + OBJ + "/objekt.json"], capture_output=True, text=True).stdout.strip()
        if not _diff:   # Agent hat Generator/objekt.json nicht geaendert (z. B. begruendet 'nicht belegt', a144153 10.11.) -> Rueckgabe waere Leerlauf
            print(f"Runde {runde}: Vorpruefung - Agent hat am Generator nichts geaendert, keine Rueckgabe", flush=True)
            _agent_leer = True
            _vorab_gebaut = _rq == 0   # Stand unveraendert seit dem Export
        elif _rq != 0 or (_qa := angleichen(f"r{runde}_{_vk}", f"r{runde}_vorpruef", _vq, ff_q, "Vorpruefung"))[1] is None or _qa[0] is None or _qa[1] < _qa[0] + MIN_GEWINN_FOTO or _hoehe_faellt(runde, _vk):   # Foto zuerst: zurueck, wenn das Foto-Tor nicht bestehen wuerde (gemeinsame Fotos)
            try: _je = (json.load(open(os.path.join(LDIR, f"fotoform_r{runde}_vorpruef.json")))["teile"].get(ziel["teil"]) or {})
            except Exception: _je = {}
            _zeilen = "\n".join(f"- Foto {f}: Praezision {_je[f].get('praez')} / Recall {_je[f].get('recall')}  Overlay {LDIR}/fotoform_bilder/{ziel['teil']}_{f}_r{runde}_vorpruef.jpg"
                                f"  (vorher: {ziel['teil']}_{f}_r{runde}_vorher.jpg)" for f in ff_fotos if f in _je)
            _rueck = (f"VORPRUEFUNG DES KREISES (automatisch, gleiche Messung wie das Tor): Dein Stand ist "
                      + ("im Generator ROT (siehe " + os.path.join(LDIR, f"vorpruef_r{runde}.log") + ")" if _rq != 0 else
                         f"am Foto NICHT KLAR BESSER" + (f" (Vorstufe halbe Aufloesung, RCPARK_FOTO_SKALA={SKALA_VOR})" if _halb else "") + f": Form-F1 {_vq} -> {ff_q}, Hoehen-Wert (nur waagerechte Kanten) {HOEHE.get(f'r{runde}_{_vk}')} -> {HOEHE.get(f'r{runde}_vorpruef')} "
                         f"(Tor: Foto-F1 muss um >= {MIN_GEWINN_FOTO} steigen, der Hoehen-Wert darf um hoechstens 0,02 fallen; die Wolke ist nur Veto fuer die Lage).")
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
    # BILLIGSTE ENTSCHEIDENDE PRUEFUNG ZUERST (Nutzer 10.11. abends "was koennen wir noch beschleunigen"; Erker 1 a174202: Abnahme 40 min + Konvergenz,
    # dann Foto-F1 Gewinn 0 -> 95 min Tor fuer eine Ablehnung, die die Fotomessung allein in 5 min gezeigt haette). Foto-F1 (+ Hoehe) entscheidet ohnehin
    # zuerst; ohne Gewinn sofort ablehnen, Abnahme/Konvergenz/Pruefer nur fuer Kandidaten. Nach einer Rueckgabe misst zuerst die halbe Stufe (1 min).
    ff_n = None; _frueh = None
    if rcG == 0 and (ff_v is not None or _ff_spaet) and not ist_fehlteil(ziel) and os.path.exists(os.path.join(_tn, ziel["teil"] + ".stl")):
        if _halb:   # halbe Stufe: endgueltig ablehnen nur ohne JEDEN Gewinn (halb unterschaetzt den Betrag: Tuer +0,081 statt +0,29)
            if not _vorab_gebaut:   # zweiter Versuch nach Rueckgabe
                _qh = form_messen(wt, _tn, ziel["teil"], ff_fotos, f"r{runde}_vorpruef2", env={"RCPARK_FOTO_SKALA": str(SKALA_VOR)}); _hk = "vorpruef2"
            else:
                _qh = ff_q; _hk = "vorpruef"
            _h2v, _h2n = HOEHE.get(f"r{runde}_vorher_halb"), HOEHE.get(f"r{runde}_{_hk}")
            print(f"Runde {runde}: Stufe halb {ziel['teil']}: F1 {_vq} -> {_qh}, Hoehe {_h2v} -> {_h2n}", flush=True)
            _va, _qh = angleichen(f"r{runde}_vorher_halb", f"r{runde}_{_hk}", _vq, _qh, "Stufe halb")
            if _qh is None or _va is None or _qh <= _va or (_h2v is not None and _h2n is not None and _h2n < _h2v - 0.02):
                _frueh = f"Stufe halb ohne Gewinn: F1 {_vq} -> {_qh}, Hoehe {_h2v} -> {_h2n}"
        if _frueh is None and ff_v is None and _ff_spaet:   # aufgeschobener voller Vorher-Wert, nur fuer Kandidaten
            ff_v = form_messen(wt, _ff_spaet[0], ziel["teil"], ff_fotos, f"r{runde}_vorher", stl=_ff_spaet[1])
            print(f"Runde {runde}: Form am Foto vorher (voll, nachgeholt) {ziel['teil']}: F1 {ff_v}", flush=True)
            if ff_v is None: _frueh = "voller Vorher-Wert nicht messbar"
        if _frueh is None:
            ff_n = ff_q if (_vorab_gebaut and not _halb) else form_messen(wt, _tn, ziel["teil"], ff_fotos, f"r{runde}_nachher")
            _hv, _hn = HOEHE.get(f"r{runde}_vorher"), HOEHE.get(f"r{runde}_vorpruef" if (_vorab_gebaut and not _halb) else f"r{runde}_nachher")
            print(f"Runde {runde}: Form am Foto (voll, vor Abnahme) {ziel['teil']}: F1 {ff_v} -> {ff_n}, Hoehe {_hv} -> {_hn}", flush=True)
            ff_v, ff_n = angleichen(f"r{runde}_vorher", f"r{runde}_vorpruef" if (_vorab_gebaut and not _halb) else f"r{runde}_nachher", ff_v, ff_n, "Tor voll")
            if ff_n is None or ff_n < ff_v + MIN_GEWINN_FOTO or (_hv is not None and _hn is not None and _hn < _hv - 0.02):
                _frueh = f"Foto voll: F1 {ff_v} -> {ff_n}, Hoehe {_hv} -> {_hn}"
        if _frueh: print(f"Runde {runde}: FRUEH ABGELEHNT ({_frueh}) - Abnahme/Konvergenz/Pruefer uebersprungen", flush=True)
    if _frueh:
        rcB, outB = 1, "uebersprungen: " + _frueh
    else:
        rcB, outB = sh_tor(["bash", "tools/bauen_abnehmen.sh", OBJ, "--nur-pruefen"], wt, log=os.path.join(LDIR, f"abnahme_r{runde}.log"), env={"RCPARK_OHNE_FOTODIAG": "1"}) if rcG == 0 else (rcG, "Generator fehlgeschlagen")
    tor_abnahme = rcB == 0 and "alle Pruefungen bestanden" in outB
    reg = None
    if ist_fehlteil(ziel):
        reg = os.path.join(LDIR, f"region_r{runde}.json"); json.dump([{"id": ziel["id"], "lo": ziel["lo"], "hi": ziel["hi"]}], open(reg, "w"))
    rcK, z1, outK = (1, None, "uebersprungen: " + _frueh) if _frueh else messen(wt, f"r{runde}_nachher", regionen=reg, vorab=(rcG == 0))
    vor_t = {t["teil"]: t for t in z0.get("wolkenbeleg_teile") or []}; nach_t = {t["teil"]: t for t in (z1 or {}).get("wolkenbeleg_teile") or []}
    vor = {k: guete(v) for k, v in vor_t.items()}; nach = {k: guete(v) for k, v in nach_t.items()}
    ersatz = None
    if ziel["teil"] not in nach:   # Teil durch neue Formfamilie ersetzt (z. B. stl_teil:figuren -> figurenreihe:figuren, s4 10.11.): neue Teile zaehlen, konservativ das schlechteste
        neu_t = {t: v for t, v in nach.items() if t not in vor and v is not None}
        if neu_t: ersatz = min(neu_t, key=neu_t.get); nach[ziel["teil"]] = neu_t[ersatz]
    if ff_v is not None and not ersatz and ff_n is None and not _frueh:
        ff_n = ff_q if (_vorab_gebaut and not _halb) else form_messen(wt, os.path.join(LDIR, f"teile_r{runde}_nachher"), ziel["teil"], ff_fotos, f"r{runde}_nachher")   # Vorpruefung = gleicher Stand, gleiche Messung
        print(f"Runde {runde}: Form am Foto {ziel['teil']}: F1 {ff_v} -> {ff_n} ({len(ff_fotos)} Fotos)")
        ff_v, ff_n = angleichen(f"r{runde}_vorher", f"r{runde}_vorpruef" if (_vorab_gebaut and not _halb) else f"r{runde}_nachher", ff_v, ff_n, "Tor")
    kf_n = None
    _flk = formliste_halb(wt) if (kf_fotos and not _frueh) else None   # Kontrollfotos auf halber Aufloesung (nur Protokoll, ~1 statt ~5 min)
    if _flk is not None:
        kf_v = form_aus_liste(_flk, wt, ziel["teil"], kf_fotos, runde, nebenwirkung=False, jtag="kontrolle_vorher")
    if kf_v is not None and ff_n is not None and not ersatz and not _frueh:   # Kontrollfotos erst hier (Agent kennt sie nicht), eigener Bilderordner
        kf_n = form_messen(wt, os.path.join(LDIR, f"teile_r{runde}_nachher"), ziel["teil"], kf_fotos, f"r{runde}_kontrolle", bilder="kontroll_bilder",
                           env={"RCPARK_FOTO_SKALA": str(SKALA_VOR)} if _flk is not None else None)
        print(f"Runde {runde}: KONTROLLFOTOS {ziel['teil']}: F1 {kf_v} -> {kf_n} ({len(kf_fotos)} Fotos, dem Agenten unbekannt)", flush=True)
        kf_v, kf_n = angleichen("kontrolle_vorher", f"r{runde}_kontrolle", kf_v, kf_n, "Kontrolle")
    tv = vor_t.get(ziel["teil"], {}); tn = nach_t.get(ersatz or ziel["teil"], {})
    foto_tor = ff_v is not None and ff_n is not None
    if foto_tor:   # FOTO ZUERST (s. MIN_GEWINN_FOTO): Gewinn nur aus den Fotos
        gewinn = ff_n - ff_v; min_g = MIN_GEWINN_FOTO
    elif _frueh:   # frueh abgelehnt (Stufe halb ohne Gewinn): kein Wolkenwert als Ersatz (a203713 meldete sonst -0,258)
        gewinn = 0.0; min_g = MIN_GEWINN_FOTO
    else:          # Teil am Foto nicht messbar (keine Formliste/Ersatzteil): alte Guete aus Beleg + Gitter-F1
        gewinn = (nach.get(ziel["teil"]) or 0) - (vor.get(ziel["teil"]) or 0); min_g = MIN_GEWINN
    # Veto: kein Rueckschritt um mehr als 0,02 - Foto-F1, Gitter-F1, und Wolkenbeleg nur, wo die Wolke das Teil sieht
    wolke_sieht = (tv.get("anteil_mit_daten") or 0) >= MIN_DATEN
    # HOEHEN-VETO (Nutzer 10.11. abends, Positivtest Helm O 0,3 m hoch: Foto-F1 -0,010 blind, Hoehen-Wert f1_h -0,052): waagerechte Kanten duerfen nicht fallen
    h_v = HOEHE.get(f"r{runde}_vorher"); h_n = HOEHE.get(f"r{runde}_vorpruef" if (_vorab_gebaut and not _halb) else f"r{runde}_nachher")
    rueck_teil = [n for n, fv, fn in (("hoehe_f1", h_v, h_n),) + ((("beleg", tv.get("beleg"), tn.get("beleg")),) if (wolke_sieht or not foto_tor) else ()) + (("kanten_f1", f1(tv), f1(tn)), ("foto_f1", ff_v, ff_n))
                  if fv is not None and fn is not None and fn < fv - 0.02]
    if KONTROLL_VETO and kf_v is not None and kf_n is not None and kf_n < kf_v - MIN_KONTROLLE: rueck_teil.append("kontroll_f1")
    if "kanten_f1" in rueck_teil and ff_v is not None and ff_n is not None and ff_n >= ff_v + 0.02:
        # Quellenvorrang (10.11., Balkon 3x verworfen): das Kantengitter ist aus den Fotos ABGELEITET und hatte ~130 Segmente ueber freier Wand;
        # die direkte Formpruefung am Foto zeigt Besserung -> kein Rueckschritt, Widerspruch als Beobachtung (Regel 5: nicht mitteln).
        rueck_teil.remove("kanten_f1"); gitter_widerspruch = f"Gitter-F1 {f1(tv):.3f}->{f1(tn):.3f}, Foto-F1 {ff_v:.3f}->{ff_n:.3f}"
        print(f"Runde {runde}: Gitter widerspricht Foto ({gitter_widerspruch}) - Foto gilt, Beobachtung folgt")
    else:
        gitter_widerspruch = None
    # QUELLENVORRANG AUCH FUER HOEHENBAENDER (10.11. abends, Balkonband a173902: Foto-F1 0,613 -> 0,824, verworfen nur wegen
    # konvergenz_bericht 'RUECKSCHRITT: recall 5-10 m 0.795 -> 0.727' - Kantengitter dort mit ~130 Fehlsegmenten ueber freier Wand, s. kanten_f1-Vorrang oben).
    # Nur wenn der EINZIGE Rueckschritt Gitter-Recall in Hoehenbaendern ist und das Foto-Tor (Gewinn + Hoehe + Foto-Veto) besteht -> Foto gilt, Beobachtung.
    _rk = [x.strip() for l in (outK or "").splitlines() if l.startswith("RUECKSCHRITT:") for x in l[len("RUECKSCHRITT:"):].split(";") if x.strip()]
    # 11.11. a002122 Kreuzgewoelbe: auch Gitter-PRAEZISION in Baendern (5-10 m 0,351 -> 0,312) - Gitter in der Laube fast leer, neue Kappenkanten
    # finden dort kein Gittersegment; Praezision steckt im direkt gemessenen Foto-F1 (Regel 9e).
    band_vorrang = (rcK == 3 and foto_tor and gewinn >= min_g and not rueck_teil and _rk and all(x.startswith(("recall ", "praezision ")) and " m:" in x for x in _rk))
    if band_vorrang:
        gitter_widerspruch = (gitter_widerspruch + "; " if gitter_widerspruch else "") + "Gitter-Baender " + ", ".join(_rk) + f", Foto-F1 {ff_v:.3f}->{ff_n:.3f}"
        print(f"Runde {runde}: Gitter-Baender widersprechen Foto ({', '.join(_rk)}) - Foto gilt, Beobachtung folgt", flush=True)
    tor_konv = (rcK == 0 or band_vorrang) and gewinn >= min_g and not rueck_teil
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
        if ziel.get("recall_kasten") is None:   # Foto-Cluster (11.11. a004523: nichts gebaut, 'Gewinn' = absoluter Gitter-Recall 0,659 - 0 -> Tor gruen,
            gewinn = 0.0; tor_konv = False       # nur der Pruefer hielt es auf). Ohne Vorher-Wert gilt allein das Foto-Tor unten (braucht ein neues Teil).
        vor[ziel["teil"]], nach[ziel["teil"]] = ziel["recall_kasten"], r_n
        # FOTO-TOR FUER NEUE TEILE (11.11., Regel 9e "Fotokanten entscheiden"; vorher nur Kantengitter-Recall im Kasten, Schwelle +0,25,
        # Foto-F1 nie gemessen - 234159 Baldachine). Je neuem Teil: Bildbereich, den es NACHHER einnimmt, vorher (Basismodell ohne Teil,
        # teil_fotoform PHANTOM) und nachher am Foto messen, gleiche Fotos (Auswahl: 10 Fotos mit den meisten Kantenpixeln, halbe Aufloesung).
        # Gilt, sobald messbar: Gewinn >= MIN_GEWINN_FOTO, Praezision des neuen Teils >= MIN_PRAEZ_NEU; Gitter-Werte (Recall Kasten/gesamt,
        # Gitter-Praezision) nur noch Beobachtung, Lage-Veto bleibt (Guete anderer Teile).
        if _fehl_vor and neu_t and rcG == 0 and not _frueh:
            _best = None
            for p_ in neu_t:
                if not os.path.exists(os.path.join(_tn, p_ + ".stl")): continue
                _alle = sorted((_fehl_vor[2].get("fotos") or {}).keys())
                if not _alle: break
                _w = form_messen(wt, _tn, p_, _alle, f"r{runde}_fehlwahl_{p_}", env={"RCPARK_FOTO_SKALA": str(SKALA_VOR)})
                _je = JE.get(f"r{runde}_fehlwahl_{p_}") or {}
                if not _je: continue
                _px = sum(v["mk_px"] + v["fk_px"] for v in _je.values())
                if _best is None or _px > _best[1]: _best = (p_, _px, sorted(_je, key=lambda k: -(_je[k]["mk_px"] + _je[k]["fk_px"]))[:10])
            if _best:
                p_, _, _ff = _best; ff_fotos = _ff
                _vs_teil = p_
                ff_n = form_messen(wt, _tn, p_, _ff, f"r{runde}_nachher")
                ff_v = form_messen(wt, _fehl_vor[0], p_, _ff, f"r{runde}_vorher", stl=_fehl_vor[1])
                ff_v, ff_n = angleichen(f"r{runde}_vorher", f"r{runde}_nachher", ff_v, ff_n, "Fehlteil")
                _pn = f1_je_p(JE.get(f"r{runde}_nachher") or {})
                print(f"Runde {runde}: FOTO-TOR NEUES TEIL {p_}: F1 im Teilbereich {ff_v} -> {ff_n} ({len(_ff)} Fotos), Praezision nachher {_pn}; "
                      f"Gitter (nur Beobachtung): Recall Kasten {ziel['recall_kasten']} -> {r_n}, {rueck_teil}", flush=True)
                if ff_v is not None and ff_n is not None:
                    _gitter = [x for x in rueck_teil if x.startswith(("praez ", "recall_gesamt"))]
                    rueck_teil = [x for x in rueck_teil if x not in _gitter]
                    if _pn is not None and _pn < MIN_PRAEZ_NEU: rueck_teil.append(f"foto_praez {p_}={_pn}")
                    if _gitter: gitter_widerspruch = (gitter_widerspruch + "; " if gitter_widerspruch else "") + "Gitter beim neuen Teil: " + ", ".join(_gitter)
                    gewinn = ff_n - ff_v; foto_tor = True
                    _rk_ok = rcK == 0 or (rcK == 3 and _rk and all(x.startswith(("recall ", "praezision ")) and " m:" in x for x in _rk))
                    tor_konv = _rk_ok and gewinn >= MIN_GEWINN_FOTO and not rueck_teil
        # FEHLTEIL IN VORHANDENES TEIL GEBAUT (11.11. a090522: Gewoelberippen als Parameter von kreuzgewoelbe:laube, kein neues Teil -> Gewinn 0
        # erzwungen, Arbeit verworfen; L34 'jeden Pfad belegen'): dann wie ein normales Teil messen - geaendertes Clusterteil, gleiche Fotos vorher/nachher.
        if _fehl_vor and not neu_t and rcG == 0 and not _frueh and ziel.get("recall_kasten") is None:
            import filecmp
            _gt = [t_ for t_ in (ziel.get("teile") or []) if os.path.exists(os.path.join(_tn, t_ + ".stl")) and os.path.exists(os.path.join(_fehl_vor[0], t_ + ".stl"))
                   and not filecmp.cmp(os.path.join(_tn, t_ + ".stl"), os.path.join(_fehl_vor[0], t_ + ".stl"), shallow=False)]
            if _gt:
                p_ = max(_gt, key=lambda t_: (ziel.get("teile_anteil") or {}).get(t_, 0)); _ff = form_fotos(_fehl_vor[2] or {}, p_)
                if _ff:
                    ff_fotos = _ff; _vs_teil = p_
                    ff_n = form_messen(wt, _tn, p_, _ff, f"r{runde}_nachher")
                    ff_v = form_messen(wt, _fehl_vor[0], p_, _ff, f"r{runde}_vorher", stl=_fehl_vor[1])
                    ff_v, ff_n = angleichen(f"r{runde}_vorher", f"r{runde}_nachher", ff_v, ff_n, "Fehlteil im vorhandenen Teil")
                    print(f"Runde {runde}: FOTO-TOR VORHANDENES TEIL {p_} (Fehlteil eingebaut): F1 {ff_v} -> {ff_n} ({len(_ff)} Fotos)", flush=True)
                    if ff_v is not None and ff_n is not None:
                        rueck_teil = [x for x in rueck_teil if not x.startswith(("praez ", "recall_gesamt"))]
                        gewinn = ff_n - ff_v; foto_tor = True
                        _rk_ok = rcK == 0 or (rcK == 3 and _rk and all(x.startswith(("recall ", "praezision ")) and " m:" in x for x in _rk))
                        tor_konv = _rk_ok and gewinn >= MIN_GEWINN_FOTO and not rueck_teil
    if rueck_teil: print(f"Runde {runde}: Rueckschritt im Ziel-Teil: {rueck_teil}")
    # VERSCHIEBUNGSKONTROLLE (11.11., L46): Foto-F1 misst auf Ornament Kantendichte (Erker-Rippen 90 Grad gedreht > korrekt). Vor dem Pruefer das Teil um
    # 0,3 m versetzt messen (tools/tor_verschiebung.py, +t und +z, 5 Fotos, halbe Aufloesung); Ergebnis als WARNUNG an den Pruefer, kein hartes Tor
    # (Schwelle 0,03 noch unkalibriert; subtraktive Teile nicht beurteilbar). RCPARK_VERSCHIEBUNG=0 schaltet ab.
    vs_info = None
    if tor_abnahme and tor_konv and os.environ.get("RCPARK_VERSCHIEBUNG", "1") != "0" and ff_fotos:
        try:
            _vt = _vs_teil if ist_fehlteil(ziel) else ziel["teil"]; _vo = os.path.join(LDIR, f"verschiebung_r{runde}.json")
            if os.path.exists(os.path.join(_tn, _vt + ".stl")):
                sh_tor([PY, "-W", "ignore", "-I", "tools/tor_verschiebung.py", OBJ, "--teile_dir", _tn, "--teil", _vt, "--fotos", ",".join(ff_fotos[:5]),
                        "--versatz", "0.3", "--skala", "0.5", "--aus", _vo], wt, log=os.path.join(LDIR, f"verschiebung_r{runde}.log"))
                if os.path.exists(_vo):
                    _v = json.load(open(_vo)); vs_info = {k: _v.get(k) for k in ("f1_echt", "marge_min", "marge_achse", "lage_belegt", "konkat_gueltig")}
                    print(f"Runde {runde}: Verschiebungskontrolle {_vt}: {vs_info}", flush=True)
        except Exception as _ex: print(f"Runde {runde}: Verschiebungskontrolle fehlgeschlagen: {_ex}", flush=True)
    urteil = pruefer_urteil(wt, ziel, runde, vs_info) if (tor_abnahme and tor_konv) else {"annehmen": False, "fehlerliste": ["nicht geprueft: Vortor rot"]}
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
                erz = lambda f: f.startswith("modelle/stl/") or f.endswith(("pruefbericht.json", "MASSNACHWEIS.md", "elemente.json", ".jpg", ".png")) or "/audit/" in f
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
                erzeugt = lambda f: f.startswith("modelle/stl/") or f.endswith(("pruefbericht.json", "MASSNACHWEIS.md", "elemente.json", ".jpg", ".png")) or "/audit/" in f
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
            subprocess.run(["git", "-C", wt, "diff", "--binary"], stdout=f, check=False)   # 11.11.: ohne --binary fehlten Messprotokoll-Bilder, --patch scheiterte
        _sk = beob_schluessel(ziel["beob"]) if ziel.get("art") == "beobachtung" else ziel["teil"]; sperre[_sk] = sperre.get(_sk, 0) + 1; ohne_annahme += 1
        subprocess.run(["git", "-C", wt, "add", "-A"], check=False)   # Stand verlustfrei auf dem Zweig sichern (fuer --nachpruefen), Worktree danach weg
        subprocess.run(["git", "-C", wt, "commit", "-q", "-m", f"kreis {LAUF} r{runde}: {ziel['teil']} VERWORFEN (Stand gesichert)"], check=False)
    if ist_fehlteil(ziel) and angenommen and ziel.get("lo"):   # angenommenes Fehlteil: Kasten als gebaut merken (Foto-Cluster aus alter Formliste nicht erneut)
        import fcntl as _f; _lk3 = open(ERLEDIGT + ".lock", "w"); _f.flock(_lk3, _f.LOCK_EX)
        _e = erledigt_laden(); _e[ziel["id"]] = {"lo": ziel["lo"], "hi": ziel["hi"], "befund": f"gebaut (angenommen {LAUF} r{runde})", "lauf": f"{LAUF} r{runde}",
                                                   "zeit": time.strftime("%Y-%m-%d %H:%M"), "zeit_ts": time.time()}
        json.dump(_e, open(ERLEDIGT, "w"), ensure_ascii=False, indent=1); _f.flock(_lk3, _f.LOCK_UN); _lk3.close()
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
               "agent_rc": rcA, "agent_leer": _agent_leer, "tor_abnahme": tor_abnahme, "infra_oom": "INFRA_OOM" in outB or "INFRA_OOM" in (outK or ""), "konvergenz_rc": rcK, "ersatz_teil": ersatz, "rueckschritt_teil": rueck_teil, "gewinn": round(gewinn, 3), "metrik": METRIK_SOLL, "tor": ("foto" if (not ist_fehlteil(ziel) and foto_tor) else (("foto_neu" if foto_tor else "region") if ist_fehlteil(ziel) else "alt")), "foto_f1_vor_nach": [ff_v, ff_n], "kontroll_f1_vor_nach": [kf_v, kf_n], "kontroll_skala": SKALA_VOR if _flk is not None else 1.0, "frueh_abgelehnt": _frueh, "kontroll_fotos": kf_fotos, "hoehe_f1_vor_nach": [h_v, h_n], "guete_vor_nach": [vor.get(ziel["teil"]), nach.get(ziel["teil"])],
               "tor_konvergenz": tor_konv, "foto_f1": [ff_v, ff_n], "foto_fotos": ff_fotos, "fehlteil_befund": fbefund, "pruefer": urteil, "angenommen": angenommen,
               "rueckschritt": (z1 or {}).get("rueckschritt"), "recall_gesamt": [z0["kanten"]["gesamt"]["recall"], (z1 or {}).get("kanten", {}).get("gesamt", {}).get("recall")]})
    print(f"Runde {runde}: {'ANGENOMMEN' if angenommen else 'VERWORFEN'} (Abnahme {tor_abnahme}, Konvergenz {tor_konv} Gewinn {gewinn:+.3f}, Pruefer {urteil.get('annehmen')})")
    if ohne_annahme >= 2:
        print("2 Runden in Folge ohne Annahme - Ende"); break
print("Protokoll:", PROT)

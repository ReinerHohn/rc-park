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

def sh_tor(cmd, cwd, log, env=None, versuche=6, pause=300):
    """Torschritt (Bau/Abnahme/Messung): Spuren-uebergreifend per flock serialisiert (deterministische Messung -> verlustfrei)
    und bei CUDA-OOM wiederholt. Ein OOM ist ein Infrastrukturfehler, kein rotes Tor (Kreis1 R1 10.11.: Abnahme 'rot' war OOM in wandstaerke)."""
    import fcntl
    rc, out = 1, ""
    for v in range(versuche):
        start = os.path.getsize(log) if os.path.exists(log) else 0
        with open(os.path.join(KREISDIR, "gpu_tor.lock"), "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            rc, _ = sh(cmd, cwd, log=log, env=env)
        with open(log, errors="replace") as f: f.seek(start); neu = f.read()
        out = neu   # ganzer neuer Logteil: "alle Pruefungen bestanden" steht mitten im Abnahme-Log (danach Sichtblatt, fehlteile, test_regeln_cb) - mit [-4000:] nie gefunden
        if not any(m in neu for m in OOM_MUSTER): return rc, out
        print(f"  OOM im Torschritt ({os.path.basename(log)}), Versuch {v + 1}/{versuche}, warte {pause} s", flush=True)
        time.sleep(pause)
    return rc, out + "\nINFRA_OOM"

def protokoll(z):
    z["zeit"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(PROT, "a") as f: f.write(json.dumps(z, ensure_ascii=False) + "\n")

def messen(wt, tag, regionen=None):
    """Bauteile exportieren (baut neu) und Konvergenz messen; liefert (exitcode, letzte konvergenz-zeile).
    regionen: JSON-Datei [{id, lo, hi}] -> Recall der Fotokanten je Kasten (Zielart Fehlteil)."""
    tdir = os.path.join(LDIR, f"teile_{tag}"); os.makedirs(tdir, exist_ok=True)
    gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
    rc, _ = sh_tor(gen, wt, log=os.path.join(LDIR, f"export_{tag}.log"), env={"BAUTEILE_AUS": tdir})
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
    n = {}
    for d in sorted(glob.glob(os.path.join(KREISDIR, OBJ, "*", "kreis.jsonl")), key=os.path.getmtime):   # zeitlich, damit eine Annahme spaetere Zaehlung zuruecksetzt
        for l in open(d):
            try: z = json.loads(l)
            except Exception: continue
            t = (z.get("ziel") or {}).get("teil")
            if t and z.get("angenommen") is False and not z.get("infra_oom") and "guete_vor_nach" in z: n[t] = n.get(t, 0) + 1   # nur Runden mit dem heutigen Tor (Guete) zaehlen
            if t and z.get("angenommen") is True: n[t] = 0
    return n

MAX_GLOBAL = int(opt("--max_global", 3))
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
    kand = [t for t in (z or {}).get("wolkenbeleg_teile") or [] if t["beleg"] is not None and t["anteil_mit_daten"] >= MIN_DATEN
            and sperre.get(t["teil"], 0) < MAX_FEHL and fg.get(t["teil"], 0) < MAX_GLOBAL and not os.path.exists(os.path.join(BELEGT, t["teil"]))
            and t["teil"].split("__")[0] not in belegt_fam]   # gleiche Formfamilie (gleicher Generatorcode) nie parallel
    kand.sort(key=lambda t: guete(t))
    for t in kand:   # atomar belegen (O_EXCL), damit zwei Spuren nie dasselbe Teil nehmen
        try:
            fd = os.open(os.path.join(BELEGT, t["teil"]), os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, f"{LAUF} {os.getpid()}".encode()); os.close(fd)
            return t
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
         f"und {wt}/modelle/{OBJ}/audit/seiten.jpg selbst an. Pruefe: Formbeschreibung vollstaendig und passend zu den Fotos? Trifft das Teil "
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
for runde in range(1, RUNDEN + 1):
    wt = os.path.join(LDIR, f"wt_r{runde}"); br = f"kreis/{OBJ}/{LAUF}-r{runde}"
    if NACH:
        wt, br = NACH_Z["worktree"], NACH_Z["branch"]
        if not os.path.exists(wt):
            subprocess.run(["git", "-C", ROOT, "worktree", "add", "-q", wt, br], check=True)
    elif TROCKEN:
        wt = ROOT
    else:
        subprocess.run(["git", "-C", ROOT, "worktree", "add", "-q", "-b", br, wt, basis], check=True)
    if NACH:
        # volle Vorher-Messung der Originalrunde (alle Teile, sonst zaehlt jedes Teil als 'neu' - Nachpruefung s4 10.11. ergab falsch -0,320)
        _kf = os.path.join(wt, "modelle", OBJ, "konvergenz.jsonl"); z0 = None
        if os.path.exists(_kf):
            for _l in reversed([x for x in open(_kf) if x.strip()]):
                _z = json.loads(_l)
                if str(_z.get("etikett", "")).endswith(f"r{_r}_vorher") and _z.get("wolkenbeleg_teile"): z0 = _z; break
        if z0 is not None and "kanten_recall" not in (z0["wolkenbeleg_teile"][0] if z0["wolkenbeleg_teile"] else {}):
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
                if zz.get("stl_sha") == sha and zz.get("wolkenbeleg_teile") and "kanten_recall" in zz["wolkenbeleg_teile"][0] and "fehlkanten" in zz:   # gleiche Messart (Sichtpruefung + Fotokanten je Teil)
                    z0 = zz; print(f"Runde {runde}: Messung vorher wiederverwendet (STL {sha})"); break
        if z0 is None:
            rc0, z0, out0 = messen(wt, f"r{runde}_vorher")
    ziel = NACH_Z["ziel"] if NACH else waehlen(z0, sperre)
    if not ziel:
        print("kein Kandidat mehr - Ende"); protokoll({"runde": runde, "ende": "kein Kandidat"}); break
    txt = auftrag(ziel, runde, wt)
    open(os.path.join(LDIR, f"auftrag_r{runde}.md"), "w").write(txt)
    print(f"Runde {runde}: Ziel {ziel['teil']} ({'Fehlteil ' + str(ziel['pkt']) + ' Pkt, Recall Kasten ' + str(ziel['recall_kasten']) if ist_fehlteil(ziel) else 'Wolkenbeleg ' + str(ziel['beleg'])}) -> Auftrag {LDIR}/auftrag_r{runde}.md")
    if TROCKEN:
        freigeben(ziel["teil"]); protokoll({"runde": runde, "trocken": True, "ziel": ziel}); print(txt[:1500]); break
    t0 = time.time()
    rcA, _ = (None, "") if NACH else sh(["claude", "-p", txt, "--model", MODELL, "--permission-mode", RECHTE], wt,
                log=os.path.join(LDIR, f"agent_r{runde}.log"), timeout=MAX_MIN * 60)
    fbefund = None
    if ist_fehlteil(ziel):
        _al = os.path.join(LDIR, f"agent_r{runde}.log")
        _m = BEFUND_RE.findall(open(_al, errors="replace").read()) if os.path.exists(_al) else []
        fbefund = _m[-1] if _m else None
        print(f"Runde {runde}: Fehlteil-Befund des Agenten: {fbefund}")
    rcB, outB = sh_tor(["bash", "tools/bauen_abnehmen.sh", OBJ], wt, log=os.path.join(LDIR, f"abnahme_r{runde}.log"))
    tor_abnahme = rcB == 0 and "alle Pruefungen bestanden" in outB
    reg = None
    if ist_fehlteil(ziel):
        reg = os.path.join(LDIR, f"region_r{runde}.json"); json.dump([{"id": ziel["id"], "lo": ziel["lo"], "hi": ziel["hi"]}], open(reg, "w"))
    rcK, z1, outK = messen(wt, f"r{runde}_nachher", regionen=reg)
    vor_t = {t["teil"]: t for t in z0.get("wolkenbeleg_teile") or []}; nach_t = {t["teil"]: t for t in (z1 or {}).get("wolkenbeleg_teile") or []}
    vor = {k: guete(v) for k, v in vor_t.items()}; nach = {k: guete(v) for k, v in nach_t.items()}
    ersatz = None
    if ziel["teil"] not in nach:   # Teil durch neue Formfamilie ersetzt (z. B. stl_teil:figuren -> figurenreihe:figuren, s4 10.11.): neue Teile zaehlen, konservativ das schlechteste
        neu_t = {t: v for t, v in nach.items() if t not in vor and v is not None}
        if neu_t: ersatz = min(neu_t, key=neu_t.get); nach[ziel["teil"]] = neu_t[ersatz]
    gewinn = (nach.get(ziel["teil"]) or 0) - (vor.get(ziel["teil"]) or 0)
    # kein Rueckschritt in einer der beiden Groessen (Lage ODER Form) um mehr als 0,02
    tv = vor_t.get(ziel["teil"], {}); tn = nach_t.get(ersatz or ziel["teil"], {})
    rueck_teil = [n for n, fv, fn in (("beleg", tv.get("beleg"), tn.get("beleg")), ("kanten_f1", f1(tv), f1(tn))) if fv is not None and fn is not None and fn < fv - 0.02]
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
                    rcg, _ = sh_tor(gen, ROOT, log=os.path.join(LDIR, f"merge_neubau_r{runde}.log"))
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
            fcntl.flock(_lk, fcntl.LOCK_UN); _lk.close()
    else:
        patch = os.path.join(LDIR, f"verworfen_r{runde}.patch")
        with open(patch, "w") as f:
            subprocess.run(["git", "-C", wt, "add", "-A", "-N", "."], check=False)
            subprocess.run(["git", "-C", wt, "diff"], stdout=f, check=False)
        sperre[ziel["teil"]] = sperre.get(ziel["teil"], 0) + 1; ohne_annahme += 1
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
               "tor_konvergenz": tor_konv, "fehlteil_befund": fbefund, "pruefer": urteil, "angenommen": angenommen,
               "rueckschritt": (z1 or {}).get("rueckschritt"), "recall_gesamt": [z0["kanten"]["gesamt"]["recall"], (z1 or {}).get("kanten", {}).get("gesamt", {}).get("recall")]})
    print(f"Runde {runde}: {'ANGENOMMEN' if angenommen else 'VERWORFEN'} (Abnahme {tor_abnahme}, Konvergenz {tor_konv} Gewinn {gewinn:+.3f}, Pruefer {urteil.get('annehmen')})")
    if ohne_annahme >= 2:
        print("2 Runden in Folge ohne Annahme - Ende"); break
print("Protokoll:", PROT)

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

def messen(wt, tag):
    """Bauteile exportieren (baut neu) und Konvergenz messen; liefert (exitcode, letzte konvergenz-zeile)."""
    tdir = os.path.join(LDIR, f"teile_{tag}"); os.makedirs(tdir, exist_ok=True)
    gen = json.load(open(os.path.join(wt, "modelle", OBJ, "objekt.json")))["generator"]
    rc, _ = sh_tor(gen, wt, log=os.path.join(LDIR, f"export_{tag}.log"), env={"BAUTEILE_AUS": tdir})
    rc2, out = sh_tor([PY, "-W", "ignore", "-I", "tools/konvergenz_bericht.py", OBJ, "--stl", STL, "--skala", str(SK), "--gitter", GIT,
                   "--wolke", WOLKE, "--teile_dir", tdir, "--etikett", f"kreis {LAUF} {tag}"] + (["--trocken"] if TROCKEN else []),
                  wt, log=os.path.join(LDIR, f"konvergenz_{tag}.log"))
    kf = os.path.join(wt, "modelle", OBJ, "konvergenz.jsonl")
    z = json.loads([l for l in open(kf) if l.strip()][-1]) if (os.path.exists(kf) and not TROCKEN) else None
    return rc2, z, out

BELEGT = os.path.join(KREISDIR, OBJ, "belegt"); os.makedirs(BELEGT, exist_ok=True)   # Spuren parallel: je Bauteil eine Sperrdatei

def waehlen(z, sperre):
    kand = [t for t in (z or {}).get("wolkenbeleg_teile") or [] if t["beleg"] is not None and t["anteil_mit_daten"] >= MIN_DATEN
            and sperre.get(t["teil"], 0) < MAX_FEHL and not os.path.exists(os.path.join(BELEGT, t["teil"]))
            and t["teil"].split("__")[0] not in {f.split("__")[0] for f in os.listdir(BELEGT)}]   # gleiche Formfamilie (gleicher Generatorcode) nie parallel
    kand.sort(key=lambda t: t["beleg"])
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
                          f"; Agentenbericht (Ende der Datei): {ag if os.path.exists(ag) else '-'}; Patch: {pa if os.path.exists(pa) else '-'}")
    if not zeilen: return ""
    return ("\n\nVORVERSUCHE ZU DIESEM TEIL (zuerst lesen, nicht blind wiederholen; verworfenen Patch pruefen und gezielt verbessern, "
            "offene Beobachtungen dazu in masstabelle.json beachten):\n" + "\n".join(zeilen))

def auftrag(ziel, runde, wt):
    v = open(os.path.join(ROOT, "modelle", "VORLAGE_BAUTEIL_RUNDE.md")).read()
    m = re.search(r"## Auftragstext.*?\n(.*?)\n---\n", v, re.S)
    txt = m.group(1)
    typ = ziel["teil"].replace("__", ":")
    befund = (f"Automatisch aus konvergenz_bericht (Wolkenbeleg je Bauteil): {typ} hat nur {ziel['beleg']:.2f} seiner datennahen "
              f"Flaeche auf der Wolke (Median-Abstand {ziel['median_m']:.2f} m, Anteil mit Daten {ziel['anteil_mit_daten']:.2f}). "
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
         f"Bauteil {ziel['teil'].replace('__', ':')}. Lies {wt}/modelle/{OBJ}/audit/kreis_bericht.md, sieh dir JEDES dort genannte Overlay "
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
        if z0 is None: sys.exit("Nachpruefen: Vorher-Messung der Originalrunde nicht gefunden - ohne sie ist der Gewinn nicht messbar")
    elif TROCKEN:
        # Trockenlauf baut nichts (main bleibt unberuehrt): letzte gespeicherte Konvergenz-Zeile
        kf = os.path.join(ROOT, "modelle", OBJ, "konvergenz.jsonl")
        z0 = json.loads([l for l in open(kf) if l.strip()][-1])
    else:
        # Wiederverwendung (verlustfrei): letzte Konvergenz-Zeile gilt, wenn ihr STL-Hash dem STL dieses Stands gleicht und sie den Wolkenbeleg traegt
        import hashlib
        z0 = None; kf = os.path.join(wt, "modelle", OBJ, "konvergenz.jsonl"); sp = os.path.join(wt, STL)
        if os.path.exists(kf) and os.path.exists(sp):
            sha = hashlib.sha256(open(sp, "rb").read()).hexdigest()[:16]
            for l in reversed([l for l in open(kf) if l.strip()]):
                zz = json.loads(l)
                if zz.get("stl_sha") == sha and zz.get("wolkenbeleg_teile"):
                    z0 = zz; print(f"Runde {runde}: Messung vorher wiederverwendet (STL {sha})"); break
        if z0 is None:
            rc0, z0, out0 = messen(wt, f"r{runde}_vorher")
    ziel = NACH_Z["ziel"] if NACH else waehlen(z0, sperre)
    if not ziel:
        print("kein Kandidat mehr - Ende"); protokoll({"runde": runde, "ende": "kein Kandidat"}); break
    txt = auftrag(ziel, runde, wt)
    open(os.path.join(LDIR, f"auftrag_r{runde}.md"), "w").write(txt)
    print(f"Runde {runde}: Ziel {ziel['teil']} (Wolkenbeleg {ziel['beleg']}) -> Auftrag {LDIR}/auftrag_r{runde}.md")
    if TROCKEN:
        freigeben(ziel["teil"]); protokoll({"runde": runde, "trocken": True, "ziel": ziel}); print(txt[:1500]); break
    t0 = time.time()
    rcA, _ = (None, "") if NACH else sh(["claude", "-p", txt, "--model", MODELL, "--permission-mode", RECHTE], wt,
                log=os.path.join(LDIR, f"agent_r{runde}.log"), timeout=MAX_MIN * 60)
    rcB, outB = sh_tor(["bash", "tools/bauen_abnehmen.sh", OBJ], wt, log=os.path.join(LDIR, f"abnahme_r{runde}.log"))
    tor_abnahme = rcB == 0 and "alle Pruefungen bestanden" in outB
    rcK, z1, outK = messen(wt, f"r{runde}_nachher")
    vor = {t["teil"]: t["beleg"] for t in z0.get("wolkenbeleg_teile") or []}
    nach = {t["teil"]: t["beleg"] for t in (z1 or {}).get("wolkenbeleg_teile") or []}
    ersatz = None
    if ziel["teil"] not in nach:   # Teil durch neue Formfamilie ersetzt (z. B. stl_teil:figuren -> figurenreihe:figuren, s4 10.11.): neue Teile zaehlen, konservativ das schlechteste
        neu_t = {t: v for t, v in nach.items() if t not in vor and v is not None}
        if neu_t: ersatz = min(neu_t, key=neu_t.get); nach[ziel["teil"]] = neu_t[ersatz]
    gewinn = (nach.get(ziel["teil"]) or 0) - (vor.get(ziel["teil"]) or 0)
    tor_konv = rcK == 0 and gewinn >= MIN_GEWINN
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
            if mr.returncode != 0 and ("untracked working tree files would be overwritten" in (mr.stderr + mr.stdout) or "unversionierten Dateien" in (mr.stderr + mr.stdout)):
                # ungetrackte Erzeugnisse in main (Audit-Bilder, Caches) blockieren den Merge (Figuren 10.11.): verlustfrei wegsichern, erneut mergen
                sich = os.path.join(KREISDIR, OBJ, "merge_sicherung", LAUF + f"_r{runde}")
                for f in [l.strip() for l in (mr.stderr + mr.stdout).splitlines() if l.startswith(("\t", "    ")) and l.strip()]:
                    src = os.path.join(ROOT, f)
                    if os.path.isfile(src): os.makedirs(os.path.dirname(os.path.join(sich, f)), exist_ok=True); shutil.move(src, os.path.join(sich, f))
                print(f"Runde {runde}: ungetrackte Dateien in main nach {sich} gesichert, Merge erneut")
                mr = subprocess.run(["git", "-C", ROOT, "merge", "--no-edit", "-m", f"kreis {LAUF} r{runde}: {ziel['teil']} nach main (automatisch)", br], capture_output=True, text=True)
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
    freigeben(ziel["teil"])
    if not TROCKEN and wt != ROOT:   # Platz (10.11.: 11 Worktrees x 430 MB fuellten die Datenplatte); Inhalt liegt als Commit auf dem Zweig br
        subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", wt], capture_output=True)
    protokoll({"runde": runde, "nachgeprueft": NACH or None, "ziel": ziel, "branch": br, "worktree": wt, "minuten": round((time.time() - t0) / 60, 1),
               "agent_rc": rcA, "tor_abnahme": tor_abnahme, "infra_oom": "INFRA_OOM" in outB or "INFRA_OOM" in (outK or ""), "konvergenz_rc": rcK, "ersatz_teil": ersatz, "gewinn": round(gewinn, 3),
               "tor_konvergenz": tor_konv, "pruefer": urteil, "angenommen": angenommen,
               "rueckschritt": (z1 or {}).get("rueckschritt"), "recall_gesamt": [z0["kanten"]["gesamt"]["recall"], (z1 or {}).get("kanten", {}).get("gesamt", {}).get("recall")]})
    print(f"Runde {runde}: {'ANGENOMMEN' if angenommen else 'VERWORFEN'} (Abnahme {tor_abnahme}, Konvergenz {tor_konv} Gewinn {gewinn:+.3f}, Pruefer {urteil.get('annehmen')})")
    if ohne_annahme >= 2:
        print("2 Runden in Folge ohne Annahme - Ende"); break
print("Protokoll:", PROT)

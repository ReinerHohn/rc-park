# Durchsatz und Zuverlaessigkeit auf System- und Ablaufebene (ein Rechner, 8 GB VRAM)

Stand 15.11.2026. Lesehinweise:
- "Lokal geprueft" = am Rechner selbst per Befehl nachgesehen (15.11.2026), keine Webquelle.
- "Eigenes Wissen, nicht nachgeschlagen" = plausibel, aber in dieser Recherche nicht an einer Quelle geprueft. Steht nur unter Inferenzen oder Luecken.
- COLMAP-Parameter (geom_consistency, window_step, Quellbilderzahl, max_image_size) stehen schon in `reports/Foto 3D Pipeline Verbesserungen.md` Punkt 3 und werden hier nicht wiederholt.

Lokale Ausgangslage (lokal geprueft, wichtig fuer alle Abschnitte):
- Der Rechner ist ein Laptop (OMEN by HP 16-wf1xxx) mit RTX 4060 Laptop GPU, 8188 MiB, Treiber 595.91.07, Thunderbolt-4-Bruecke vorhanden. Eine gebrauchte 24-GB-Karte laesst sich also NICHT einbauen, nur als eGPU ueber Thunderbolt betreiben.
- 28 logische CPUs: 0-15 sind 8 schnelle Kerne mit je 2 Threads (5,3-5,5 GHz), 16-27 sind 12 langsame Kerne (3,9 GHz).
- 15 GB RAM gesamt, 16-GB-Auslagerungsdatei liegt auf der knappen Datenpartition (`/media/oem/scan/swapfile`, 7,4 GB belegt), zswap ist aus.
- Eine einzige interne NVMe mit 477 GB: `/media/oem/scan` ext4 98 GB (15 GB frei), `/` 48 GB (5 GB frei), Windows-NTFS 135 GB (40 GB frei), NTFS "Volume" 193 GB (20 GB frei). Extern: Toshiba-USB-Platte 932 GB NTFS (zu 100 % voll, 5 GB frei), USB-Stick 115 GB ext4 (9 GB frei). Alle NTFS-Platten laufen ueber `fuseblk` (= ntfs-3g), das Kernelmodul `ntfs3` ist vorhanden.
- systemd 255. Der Benutzerdienst `user@1000.service` hat nur `DelegateControllers=cpu memory pids`. cpuset und io fehlen.
- Installiert: `nvtop`, `zstd`, `mksquashfs`, `nvidia-cuda-mps-control`. Nicht installiert: `pueue`, `ts`/`tsp`, `snakemake`, `py-spy`, `jdupes`, `rmlint`. In `venv-seg`: torch 2.15.0+cu132, numpy 2.5.4, scipy 1.18.1; faiss, open3d, pytorch3d, cupy, blosc2, zarr wurden dort nicht gefunden.

## GPU-Teilung auf einer 8-GB-Karte und die kleinste Warteschlange mit DAG, Wiederholung, Ressourcen und Wiederaufnahme

### Takeaway
Auf 8 GB hilft kein Trick gegen Summenueberlauf ausser Buchfuehrung: Budgets muessen RESERVIERT werden (nicht aus `nvidia-smi` abgelesen), und jeder Torch-Job muss seine Obergrenze hart setzen. Das kleinste Werkzeug, das Abhaengigkeiten, Wiederholungen, Ressourcen-Zaehler und Wiederaufnahme zusammen liefert, ist Snakemake mit einer selbst benannten Ressource (z. B. `vram_mb`); pueue und der GPU-Fork von task-spooler sind kleiner, koennen aber weder Wiederholung noch VRAM-Mengen.

### Cited Findings
- PyTorch: Speicher, den der Allokator nur zwischengespeichert haelt, erscheint in `nvidia-smi` weiterhin als belegt; `torch.cuda.empty_cache()` gibt nur ungenutzten Cache frei. Folge: eine Messung per `nvidia-smi` ueberschaetzt Torch-Jobs und sieht Jobs nicht, die gerade erst starten. — [PyTorch CUDA-Notizen 2.15](https://docs.pytorch.org/docs/2.15/notes/cuda.html)
- PyTorch 2.15 kennt die Obergrenze auch als Umgebungsvariable: `PYTORCH_CUDA_ALLOC_CONF=per_process_memory_fraction:<0..1>` (bevorzugter Name der Variable inzwischen `PYTORCH_ALLOC_CONF`). Ueberschreitung ergibt einen Speicherfehler im eigenen Prozess. Mit `throw_on_cudamalloc_oom:True` wird die Anforderung abgelehnt, bevor sie den Treiber erreicht. Damit laesst sich die Grenze in `job_start.sh` setzen, ohne jedes Skript anzufassen. — [PyTorch CUDA-Notizen 2.15](https://docs.pytorch.org/docs/2.15/notes/cuda.html)
- `expandable_segments:True` ist weiterhin als experimentell markiert (Standard aus) und hilft bei wechselnden Anforderungsgroessen; `max_split_size_mb` nennt die Doku ausdruecklich "letztes Mittel"; `garbage_collection_threshold` (0-1) raeumt ungenutzten Cache aktiv ab. — [PyTorch CUDA-Notizen 2.15](https://docs.pytorch.org/docs/2.15/notes/cuda.html)
- `set_per_process_memory_fraction` muss vor der ersten CUDA-Zuweisung gesetzt sein und wirkt als harte Obergrenze je Prozess. — [Technion HPC-Anleitung](https://hpc.cs.technion.ac.il/?p=91)
- NVIDIA MPS: Dienst fuer mehrere CUDA-Prozesse auf einer GPU, Nutzen laut Hersteller "improved GPU utilization and reduced GPU context switching", dazu Speicher- und Rechenanteil-Begrenzung je Klient. — [NVIDIA MPS Uebersicht](https://docs.nvidia.com/deploy/mps/index.html)
- MPS-Speichergrenze: `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT="0=2G"` in der Umgebung des Klienten begrenzt den per CUDA zuweisbaren GPU-Speicher dieses Prozesses; der Wert kann eine Grenze des Steuerdienstes nur weiter verschaerfen. Ohne Einstellung gibt es keine Grenze. Aenderungen am Server gelten nicht fuer schon laufende Klienten. — [NVIDIA MPS Umgebungsvariablen](https://docs.nvidia.com/deploy/mps/appendix-environment-variables.html), [Handbuchseite nvidia-cuda-mps-control](https://www.mankier.com/1/nvidia-cuda-mps-control)
- Ein Nutzer berichtet im NVIDIA-Forum, dass die Grenzen je Klient nicht wie erwartet griffen; der Faden zeigt in den Suchtreffern keine Loesung. — [NVIDIA-Forum](https://forums.developer.nvidia.com/t/how-to-enforce-per-client-memory-and-sm-limits-in-cuda-mps/341976)
- COLMAP, Merkmalsabgleich: GPU-Speicher fuer SIFT etwa `4 * n^2 + 4 * n * 256` Byte bei n = `FeatureMatching.max_num_matches`; bei 10000 rund 400 MB. Bei Speichermangel diesen Wert senken, ebenso `SiftExtraction.max_num_features` und `FeatureExtraction.max_image_size`. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- COLMAP: je CUDA-GPU laeuft standardmaessig ein Arbeiter fuer Extraktion, Abgleich und PatchMatch; `geom_consistency` erhoeht den GPU-Speicherbedarf von PatchMatch. Unterbrochene PatchMatch-Laeufe setzen fort, fertige Ansichten werden uebersprungen. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- task-spooler (GPU-Fork): `-G n` fordert GPUs an; eine GPU gilt als frei, wenn ihr freier Speicher ueber einer Schwelle liegt (`--set_gpu_free_perc`, Standard 90 %). Abhaengigkeiten: `-D id,..` (nach Ende, egal wie) und `-W id,..` (nur nach Erfolg). `-S` Zahl der Plaetze, `-N` Plaetze je Job. Lizenz GPL-2.0. Keine Wiederholungen, keine VRAM-Mengen. — [task-spooler GPU-Fork](https://github.com/justanhduc/task-spooler)
- pueue: Gruppen als getrennte Warteschlangen mit eigener Parallelgrenze (`pueue parallel 1 --group gpu`), Abhaengigkeiten zwischen Aufgaben, Start zu einer Uhrzeit, `restart` fuer fehlgeschlagene Aufgaben, Rueckruf-Haken nach Aufgabenende, Zustand wird auf Platte gesichert und nach Absturz wiederhergestellt. Lizenz Apache-2.0/MIT. Die Projektseite nennt weder automatische Wiederholungen noch Ressourcenkenntnis und sagt selbst, die Planung sei einfach gehalten. — [pueue](https://github.com/Nukesor/pueue)
- Snakemake: Ressourcen duerfen beliebig heissen (ganzzahlig oder Text); mit `--resources name=N` sorgt der Planer dafuer, dass laufende Jobs die Summe nicht ueberschreiten; ohne Grenze werden Ressourcen lokal ignoriert. `retries: 3` je Regel oder `--retries` global; Ressourcen koennen von `attempt` abhaengen (z. B. kleinere Bildgroesse im zweiten Versuch). — [Snakemake Regeln](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html)
- Snakemake: `temp()` loescht Zwischenergebnisse, sobald alle Verbraucher fertig sind; `ensure(datei, non_empty=True)` laesst einen Job bei leerer Ausgabe scheitern; Logdateien bleiben bei Fehlern erhalten; Neuberechnung haengt an Zeitstempeln (kleine Dateien bis 1 MB per Pruefsumme) und an Code-Aenderungen; `shadow` fuehrt eine Regel in einem eigenen Wegwerf-Verzeichnis aus. — [Snakemake Regeln](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html)
- Snakemake zaehlt Ressourcen nur, es sperrt nichts: ein Job, der mehr nimmt als angegeben, wird nicht gebremst. — [FlowDeploy zu Snakemake-Ressourcen](https://flowdeploy-website.pages.dev/snakemake-resources)
- Lokal geprueft: `tools/job_start.sh` entscheidet die Parallelfreigabe ueber `nvidia-smi memory.used + Budget <= 7000`, Abfrage im 60-s-Takt, ohne Sperre zwischen Abfrage und Start. — lokale Datei `/home/oem/git/rc-park/tools/job_start.sh`

### Inferences
- Wahrscheinliche Ursache des naechtlichen Speicherfehlers: Wettlauf. Zwei Jobs fragen kurz nacheinander `nvidia-smi` ab, der erste hat noch nichts belegt, beide starten. Abhilfe ohne neue Software: Reservierungsbuch statt Messung. Unter `flock` die Budgets aller laufenden `rcpark-*`-Einheiten summieren (z. B. je Job eine Datei `gpu_reserviert/<name>` mit MiB, geloescht am Jobende bzw. wenn die Einheit nicht mehr aktiv ist) und zusaetzlich das Maximum aus Buch und `nvidia-smi` nehmen (faengt Fremdprozesse). Aufwand etwa 20 Zeilen Shell.
- Die Torch-Grenze gehoert in den Starter, nicht ins Werkzeug: `PYTORCH_CUDA_ALLOC_CONF=per_process_memory_fraction:$(Budget/8188),expandable_segments:True` beim `systemd-run` per `-E` mitgeben. Dann kann kein Torch-Job sein Budget ueberziehen und einen fremden Lauf entwerten; er scheitert selbst und sichtbar.
- COLMAP laesst sich nicht deckeln, nur ueber Parameter klein halten (Bildgroesse, Merkmalszahl). COLMAP-GPU-Schritte deshalb weiter exklusiv oder mit gemessenem Budget fuehren.
- MPS lohnt hier voraussichtlich nicht: Der Engpass ist Speicher, nicht Kontextwechsel, und der Bildschirm haengt an derselben Laptop-GPU. Unklar ist ausserdem, ob COLMAPs SIFT ueber CUDA oder OpenGL laeuft; OpenGL-Prozesse deckt MPS nicht ab (eigenes Wissen, nicht nachgeschlagen). Hoechstens als Versuch fuer zwei kleine Torch-Jobs.
- Empfehlung Warteschlange in zwei Stufen. Stufe 1 (heute, ohne Neuinstallation): `job_start.sh` um Reservierungsbuch, Torch-Grenze, `Restart=` und `OnFailure=` ergaenzen. Stufe 2 (wenn die Kette je Objekt feststeht): eine `Snakefile` mit `resources: vram_mb=..., kerne=...`, Aufruf `snakemake --cores 28 --resources vram_mb=7000 --retries 2 --keep-going --rerun-incomplete`. Die Regeln rufen weiter die vorhandenen Werkzeuge auf.
- pueue waere die Mitte: zwei Gruppen (`gpu` mit 1 Platz, `cpu` mit 2-3 Plaetzen) beseitigen Ueberlappung sofort, aber ohne VRAM-Mengen und ohne Wiederholung.
- Der GPU-Fork von task-spooler passt schlecht: Die Schwelle "90 % frei" macht die GPU praktisch exklusiv, und der Bau braucht vermutlich CUDA/NVML (nicht geprueft).
- Slurm (ein Knoten mit GRES), Ray, Dask, Airflow, Prefect, Luigi, Nextflow: fuer einen Rechner mehr Infrastruktur als Nutzen (Dienste, Datenbank oder Java). Eigenes Wissen, nicht nachgeschlagen.

### Gaps
- Wie viel GPU-Speicher COLMAP 4.3 fuer SIFT-Extraktion je Bildgroesse und fuer PatchMatch je Bild belegt, steht nicht in der FAQ. Die eigenen Messwerte in `tools/gpu_budget.txt` sind die beste Quelle.
- Ob COLMAP 4.3 fuer SIFT CUDA oder OpenGL nutzt, wurde nicht geprueft.
- Zeitscheiben ("time-slicing") der GPU: nichts Brauchbares fuer einen Einzelplatz gefunden; ohne MPS wechseln Prozesse ohnehin im Zeitscheibenverfahren.
- Die offizielle MPS-Seite zu Grenzen (ein Nutzer, Fehler eines Klienten reisst andere mit) wurde nicht abgerufen.
- Snakemake: `--rerun-incomplete`, `--keep-going`, `benchmark:` und Parameter als Neuberechnungs-Ausloeser lagen im nicht gelesenen Teil der Doku; Lizenz (vermutlich MIT) nicht geprueft.

## CPU-Konkurrenz: systemd-Regler, Kernbindung, Thread-Deckel

### Takeaway
Die 14-Minuten-SIFT-Extraktion laesst sich mit drei Zeilen verhindern: GPU-zufuetternde Jobs bekommen hohes `CPUWeight` und die schnellen Kerne, CPU-Dauerlaeufer bekommen `CPUWeight=idle` oder die langsamen Kerne und einen Thread-Deckel. Achtung: `AllowedCPUs=` und `IOWeight=` wirken in Benutzerdiensten auf diesem Rechner derzeit nicht, weil cpuset und io nicht delegiert sind; `taskset` geht immer.

### Cited Findings
- `CPUWeight=` 1-10000, Kernelstandard 100, Sonderwert `idle`: die Einheit bekommt CPU nur, wenn sonst niemand rechnen will. Verteilt wird unter Geschwistern derselben Scheibe im Verhaeltnis der Gewichte, also arbeitserhaltend (nichts liegt brach). — [systemd.resource-control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- `CPUQuota=` ist eine harte Obergrenze in Prozent einer CPU (z. B. `1200%` = 12 Kerne), nicht arbeitserhaltend. — [systemd.resource-control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- `AllowedCPUs=` bindet an CPU-Nummern, kann aber von Elterneinheiten eingeschraenkt sein. — [systemd.resource-control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- `MemoryHigh=` bremst und raeumt aggressiv ab, `MemoryMax=` ist die harte Grenze mit OOM-Killer in der Einheit; empfohlen ist `MemoryHigh` als Hauptregler und `MemoryMax` als letzte Verteidigung. `MemorySwapMax=` begrenzt die Auslagerung je Einheit. — [systemd.resource-control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- `IOWeight=` 1-10000 (Standard 100) teilt E/A unter Geschwistern; `IOReadBandwidthMax=`/`IOWriteBandwidthMax=` sind harte Grenzen je Geraet. — [systemd.resource-control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- Der Benutzer-systemd schaltet Regler fuer Einheiten mit Grenzen selbst ein, aber nur solche, die ihm delegiert wurden. — [systemd.resource-control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)
- Lokal geprueft: `systemctl show user@1000.service -p DelegateControllers` ergibt `cpu memory pids`; in `cgroup.controllers` des Benutzerdienstes stehen ebenfalls nur diese drei. — lokaler Befehl, 15.11.2026
- COLMAP: CPU-Extraktion kann viel RAM brauchen; Threads begrenzen mit `FeatureExtraction.num_threads`. — [COLMAP FAQ](https://colmap.github.io/faq.html)

### Inferences
- Sofort nutzbar in `job_start.sh` (cpu-Regler ist delegiert): neue Variable `JOB_KLASSE`. Fuer GPU-Jobs `-p CPUWeight=1000`, fuer CPU-Dauerlaeufer (Ausrichtung, Feinfit, globaler Mapper) `-p CPUWeight=idle` oder `-p CPUWeight=20 -p Nice=10`. Damit behaelt die SIFT-Extraktion ihre Zufuetter-Threads, auch wenn 28 Threads Ausrichtung laufen.
- Kernbindung ohne cpuset-Delegation: Befehl mit `taskset -c 16-27` (12 langsame Kerne) fuer CPU-Dauerlaeufer und `taskset -c 0-15` fuer GPU-Jobs voranstellen. Mit Delegation ginge `-p AllowedCPUs=16-27`. Dafuer einmalig als root: `/etc/systemd/system/user@.service.d/delegate.conf` mit `[Service]` und `Delegate=cpu cpuset io memory pids`, dann neu anmelden. (Eigenes Wissen, im Arch-Wiki unter "Cgroups, User delegation" beschrieben, hier nicht abgerufen.) Erst danach wirkt auch `IOWeight=`.
- Thread-Deckel je Job per `-E`: `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` auf die zugeteilte Kernzahl. Ohne Deckel startet jede numpy/scipy-Instanz 28 BLAS-Threads; drei parallele Jobs ergeben 84 Threads auf 28 CPUs. (Eigenes Wissen.)
- Faustregel fuer die Mischung: je GPU-Job 4-6 schnelle Kerne reservieren (Bilddekodierung, Zufuettern), den Rest an CPU-Jobs. `CPUWeight` regelt das weich, `taskset` hart.
- RAM ist der zweite Engpass: 15 GB gesamt, 7,4 GB lagen in der Auslagerung. `MemoryHigh=11G` je Job bei zwei parallelen Jobs ueberbucht den Rechner. Besser Summe der `MemoryHigh` <= etwa 13 G halten und je Job `MemoryMax` knapp darueber plus `MemorySwapMax` setzen, damit ein einzelner Job stirbt (und neu startet) statt den ganzen Rechner ins Auslagern zu ziehen.

### Gaps
- Keine Messung gefunden, wie viele CPU-Threads COLMAPs GPU-Extraktion wirklich braucht; lokal mit `pidstat -t` an einem Lauf messen.
- Ob `Delegate=` mit cpuset unter Ubuntu 24.04/systemd 255 Nebenwirkungen hat, wurde nicht geprueft.

## Zuverlaessigkeit: Wiederholung, idempotente Stufen, Vorab-Pruefung, Benachrichtigung, Waechter

### Takeaway
Die beobachteten Nachtausfaelle (fehlendes Verzeichnis, doppelte Dateinamen) sind deterministische Fehler: Wiederholen hilft dort nicht, ein Vorab-Lauf mit Winzdaten schon. Fuer den Rest reichen `Restart=on-failure` mit Obergrenze, eine `OnFailure=`-Vorlage mit ntfy und ein Waechter auf das Logdatei-Alter.

### Cited Findings
- Muster fuer Fehlermeldung aufs Telefon: eine Vorlageneinheit `notify-failure@.service` (Typ oneshot), die per `curl` "%i failed on %H" an ein ntfy-Thema schickt; in der ueberwachten Einheit `OnFailure=notify-failure@%n.service`. Mit einer absichtlich scheiternden Einheit testen. — [ntfy-Kochbuch](https://jwatte.com/downloads/ntfy-phone-alerts-cookbook.md), [NixOS-Forum](https://discourse.nixos.org/t/how-to-setup-a-notification-in-case-of-systemd-service-failure/51706)
- Dieselbe Vorlage laesst sich fuer `OnSuccess=` verwenden (Meldung "fertig"). — [selfhosted-apps-docker, ntfy](https://github.com/DoTheEvo/selfhosted-apps-docker/blob/master/gotify-ntfy-signal/)
- Alternative ohne `OnFailure`: per cron alle 5 Minuten nach fehlgeschlagenen Einheiten suchen und melden. — [ntfy_systemd](https://github.ksda9001.workers.dev/thiswillbeyourgithub/ntfy_systemd)
- Snakemake liefert die Bausteine fuer idempotente Stufen fertig: Wiederholungen mit Versuchszaehler, Pruefung der Ausgaben (`ensure`), Loeschen von Zwischenergebnissen (`temp`), Neuberechnung nur bei geaenderten Eingaben oder geaendertem Code. — [Snakemake Regeln](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html)
- COLMAP PatchMatch ist von sich aus wiederaufnehmbar (fertige Ansichten werden uebersprungen). — [COLMAP FAQ](https://colmap.github.io/faq.html)
- pueue sichert die Warteschlange auf Platte und stellt sie nach Absturz wieder her; fehlgeschlagene Aufgaben lassen sich mit `restart` neu einreihen. — [pueue](https://github.com/Nukesor/pueue)

### Inferences
- Ergaenzung fuer `systemd-run` in `job_start.sh` (eigenes Wissen aus systemd.service/systemd.unit, nicht abgerufen; vor Einsatz mit Dummy-Befehl testen): `-p Restart=on-failure -p RestartSec=60 -p StartLimitIntervalSec=3600 -p StartLimitBurst=3 -p RestartPreventExitStatus="2 3" -p RuntimeMaxSec=6h -p OnFailure=rcpark-melden@%n.service`. Exit-Codes 2/3 fuer "Aufruf falsch/Tor nicht bestanden" duerfen nicht neu starten, sonst dreht ein deterministischer Fehler dreimal. `--collect` und `Restart=` zusammen pruefen.
- ntfy-Vorlage (`~/.config/systemd/user/rcpark-melden@.service`): `ExecStart=/usr/bin/curl -s -H "Priority: high" -d "%i fehlgeschlagen auf %H" https://ntfy.sh/<geheimes-thema>`. ntfy.sh ist kostenlos und ohne Konto nutzbar, oeffentliche Themen kann jeder lesen, der den Namen kennt; also zufaelligen Themennamen waehlen und keine Pfade mit Personenbezug senden. (Eigenes Wissen; Pushover, Telegram-Bot und E-Mail wurden nicht recherchiert.)
- Vorab-Pruefung als Pflichtstufe jeder Kette: derselbe Befehl mit 3-5 verkleinerten Bildern in ein Wegwerf-Verzeichnis, Dauer unter 2 Minuten, deckt fehlende Ausgabeverzeichnisse, doppelte Dateinamen, falsche Optionen und fehlende Module auf. Dazu am Anfang jeder Stufe: `mkdir -p` fuer alle Ausgaben, Eindeutigkeitspruefung der Bildnamen, Platzpruefung (gibt es schon: `platz_pruefen.py`).
- Idempotenz ohne Snakemake: jede Stufe schreibt nach `<ziel>.tmp` und benennt erst bei Erfolg um; daneben `<ziel>.fertig` mit Pruefsumme ueber Eingabeliste + Parameter + Werkzeugversion. Die Stufe wird uebersprungen, wenn die Pruefsumme passt. Das ist ein inhaltsadressierter Zwischenspeicher in 15 Zeilen.
- Haenger-Waechter: ein systemd-Timer (alle 10 min), der fuer jede aktive `rcpark-*`-Einheit das Alter der Logdatei prueft und bei mehr als z. B. 45 min ohne neue Zeile sowie GPU- und CPU-Last nahe 0 meldet (nicht sofort toetet). `WatchdogSec=` braeuchte `sd_notify` in jedem Werkzeug und ist dafuer zu aufwendig.
- Strukturierte Logs billig: je Stufe eine Zeile JSON (`stufe`, `start`, `ende`, `rc`, `sekunden`, `max_rss`, `gpu_mib`) in eine gemeinsame Datei anhaengen; daraus entsteht die Zeitauswertung ohne Zusatzwerkzeug.

### Gaps
- Keine Quelle zu Pushover-/Telegram-Kosten und -Grenzen abgerufen.
- systemd.service-Handbuch (Restart, StartLimit, RuntimeMaxSec) nicht abgerufen; Verhalten in fluechtigen `systemd-run --user`-Einheiten lokal testen.

## CPU-gebundene Schritte auf die GPU verlagern oder billiger machen

### Takeaway
Belegt sind grosse Gewinne nur fuer Naechste-Nachbar-Suche auf der GPU (cKDTree mehr als zwei Groessenordnungen langsamer als ein GPU-Baum); fuer kleine Ausgleichsprobleme ist ein GPU-Loeser dagegen langsamer als Ceres auf der CPU. Der billigste Schritt ist daher: Punkte vor dem Fit ausduennen, cKDTree mehrkernig abfragen, die Residuenberechnung (nicht den Loeser) nach Torch legen.

### Cited Findings
- Vergleich k=30 Nachbarn auf gleichverteilten 3D-Punkten (float32): `scipy` cKDTree ist mehr als zwei Groessenordnungen langsamer als das GPU-Verfahren der Autoren; andere GPU-kd-Baeume liegen ab etwa 10^6 Punkten ueber eine Groessenordnung dahinter. Angabe aus Suchtreffer-Zusammenfassung, nicht aus der Originaltabelle. — [JZ-Tree, arXiv 2604.05885](https://arxiv.org/pdf/2604.05885)
- Gegenstimme: Bei rund 3,3 Mio. Lidar-Punkten profitierte cKDTree deutlich von mehr Kernen, und eine GPU-Brute-Force-Suche (cuML) war gegen mehrkerniges cKDTree nicht konkurrenzfaehig. — [lidarpc-kdtree](https://github.com/up-rs-esp/lidarpc-kdtree)
- Praxisbericht: FAISS-GPU (IVFFlat) hatte die schnellsten Abfragen, aber hohe Aufbaukosten; lohnt nur bei vielen Abfragen auf demselben Index. — [Thousand-Brains-Forum](https://thousandbrains.discourse.group/t/gpu-acceleration-of-knn-search-update/620)
- small_gicp (MIT, `pip install small_gicp`): GICP einfaedig etwa 2,4-mal schneller als PCL und 1,9-mal schneller als fast_gicp; Voxel-Ausduennung mit 6 Threads etwa 3,2-mal schneller als PCL; kd-Baum-Aufbau mehrfaedig bis 6-mal schneller. Keine GPU-Umsetzung enthalten. — [small_gicp](https://github.com/koide3/small_gicp)
- fast_gicp nennt fuer CUDA-VGICP etwa 120 Ausrichtungen je Sekunde bei rund 17 000 Punkten je Wolke (i9-9900K, RTX 2080 Ti). — [fast_gicp](https://docs.ros.org/en/iron/p/fast_gicp)
- Theseus (PyTorch, differenzierbare kleinste Quadrate, LM mit adaptiver Daempfung): bis 20-mal schneller als Ceres bei grossen, gestapelten Problemen; bei kleinen Problemen ist Ceres schneller (25-mal bei 256 Posen und Stapelgroesse 16). — [Theseus, arXiv 2207.09442](https://arxiv.org/pdf/2207.09442)
- Ceres mit CUDA beschleunigt DENSE_QR, DENSE_NORMAL_CHOLESKY, DENSE_SCHUR und CGNR; mit cuDSS zusaetzlich SPARSE_NORMAL_CHOLESKY und SPARSE_SCHUR (die fuer Buendelausgleich wichtigen Loeser). — [Ceres Installation](https://ceres-solver.readthedocs.io/latest/installation.html)
- GPU-Buendelausgleich in PyTorch (PyPose-Umfeld): im Mittel 18,5-, 22- und 23-mal schneller als GTSAM, g2o und Ceres, laut den Autoren. — [Bundle Adjustment in the Eager Mode, arXiv 2409.12190](https://arxiv.org/html/2409.12190v2)
- COLMAP-Fusion: schneller mit moeglichst grossem `StereoFusion.cache_size`; zu kleine Werte machen sie sehr langsam und belasten die Platte. Die FAQ sagt nichts zu Threads der Fusion. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Eigene fruehere Messung: Fusion aus fotometrischen Karten dauerte 146 s bei 2,63 Mio. Punkten. — lokaler Bericht `/home/oem/git/rc-park/reports/Foto 3D Pipeline Verbesserungen.md`, Punkt 3

### Inferences
- Reihenfolge nach Aufwand fuer "cKDTree auf 4,4 Mio. Punkten" und "scipy least_squares Feinfit":
  1. Wolke vor dem Fit per Voxelgitter ausduennen (z. B. 5 cm): fuer ein Lage-Veto reichen einige 100 000 Punkte; die Kosten fallen etwa linear mit der Punktzahl. In numpy per `np.unique` auf gerundeten Koordinaten, kein neues Paket.
  2. `cKDTree.query(..., workers=-1)` nutzen und den Baum einmal bauen statt je Iteration (eigenes Wissen, scipy-Doku nicht abgerufen). Der Baum der festen Wolke (LoD2/Referenz) bleibt ueber alle Iterationen gleich.
  3. Residuen statt Loeser auf die GPU: das vorhandene `tools/gpu_knn.py` fuer die Nachbarsuche, Distanzen in Torch; scipy bleibt der Loeser (wenige Parameter). Ein GPU-LM (Theseus, PyPose) bringt bei 6-9 Parametern nichts, das zeigt die Theseus-Messung fuer kleine Probleme.
  4. Jacobi-Matrix analytisch oder per `torch.func.jacrev` statt Differenzenquotient: spart bei n Parametern n zusaetzliche Residuenauswertungen je Schritt (eigenes Wissen).
- Die Fusion ist mit rund 2,5 min kein lohnendes Ziel mehr; der globale Mapper ebenfalls nur, wenn er lokal mehr als einige Minuten braucht.
- Ein Ceres-Neubau mit cuDSS waere der Weg, den Buendelausgleich in COLMAP auf die GPU zu bringen, ist aber kein Kleinaufwand (COLMAP und Ceres neu bauen) und bei 200-500 Bildern vermutlich ohne grossen Gewinn. Vermutung, keine Messung gefunden.
- Echte GPU-Leerlaufzeit laesst sich am billigsten durch Planung fuellen: waehrend CPU-Stufen von Objekt A laeuft PatchMatch oder Merkmalsabgleich von Objekt B (Fliessband ueber mehrere Objekte statt ein Objekt nach dem anderen). Das leistet jede der oben genannten Warteschlangen.

### Gaps
- Kein belastbarer Messwert fuer Open3D-Tensor-ICP auf CUDA gegen CPU gefunden; ebenso keiner fuer PyTorch3D `knn_points`, cupoch oder `torch.cdist` bei Millionen 3D-Punkten.
- Kein Messwert fuer Ceres mit cuDSS gegen CPU-SPARSE_SCHUR gefunden.
- InstantSfM, KISS-ICP, fpsample, torchmin, pyceres wurden nicht recherchiert.
- Ob `StereoFusion.num_threads` in COLMAP 4.3 die Fusion wirklich parallelisiert, ist offen.

## Platte und E/A

### Takeaway
Der Platz fehlt strukturell: eine 477-GB-NVMe, vierfach aufgeteilt, plus eine zu 100 % volle USB-Festplatte. Die groessten Hebel sind lokal sofort sichtbar (16-GB-Auslagerungsdatei auf der Datenpartition, 40 GB frei auf der Windows-Partition, Tiefenkarten nach der Fusion loeschen oder als zstd/squashfs archivieren); SSDs sind 2026 deutlich teurer geworden.

### Cited Findings
- Lokal geprueft: Auf `/media/oem/scan` belegen `rc-park_daten` 30 GB, `swapfile` 17 GB, `colmap-build` 6,3 GB, `venv-seg` 6,2 GB, `rc-park_kreis` 3,2 GB, `hf_cache` 2,2 GB. — lokaler Befehl `du -sh`, 15.11.2026
- COLMAP: zu kleine Cache-Groessen bei Stereo/Fusion fuehren zu sehr langsamer Verarbeitung und hoher Plattenlast; kleinere `max_image_size` senkt Speicher- und Plattenbedarf. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- ntfs-3g: Der damalige Tuxera-Entwickler gibt an, ntfs-3g ziele auf Stabilitaet und Vertraeglichkeit statt auf Hoechstleistung, liege bei reinen Dateiuebertragungen etwa 15-20 % hinter ext4, und schlechte Messwerte kaemen oft von der fehlenden Einhaengeoption `big_writes`. Stand 2021. — [LKML, Szakacsits](https://lore.kernel.org/lkml/alpine.DEB.2.20.2109030047330.23375@tuxera.com/)
- ntfs3 (Kerneltreiber): schneller, aber mit Fehlerberichten, auch von internen NVMe-Laufwerken; keine Messung, die das Mehrrisiko beziffert. Anekdotische Quelle. — [Frage-Antwort-Seite zu ntfs3](https://yomotherboard.com/question/is-ntfs3-reliable-enough-for-a-4tb-external-drive-on-a-raspberry-pi/)
- SSD-Preise 2026: guenstigste verfolgte 2-TB-NVMe am 19.08.2026 bei 209,99 $ (etwa 105 $ je TB); 1 TB etwa 150 $ je TB. — [Capital & Compute](https://capitalandcompute.net/blog/why-are-ssds-so-expensive/)
- Andere Angabe: 2-TB-NVMe, die ein Jahr zuvor 120-150 $ kosteten, liegen je nach Modell bei 300-480 $; die Knappheit soll bis mindestens Ende 2026, moeglicherweise 2027 anhalten. — [Tech Insider](https://tech-insider.org/ssd-prices-nand-shortage-2026/); niedrigere Werte (130-170 $ im 1. Quartal 2026) bei [RamPriceHistory](https://rampricehistory.com/blog/why-did-ssd-prices-go-up-2026). Die Quellen widersprechen sich je nach Datum und Modellklasse.

### Inferences
- Sofortmassnahmen ohne Kauf, nach Wirkung:
  1. Tiefen- und Normalenkarten nach bestandener Fusion und bestandenem Grundriss-Tor loeschen (17 GB je Objekt). Sie sind aus Bildern + Kameras reproduzierbar; aufheben nur, solange ein Tor offen ist. Als feste Aufraeumstufe der Kette (`temp()` in Snakemake waere genau das).
  2. Auslagerung von der Datenpartition nehmen: 16 GB Platz. Moeglichkeiten: zram (komprimierte Auslagerung im RAM) fuer die ersten GB und eine kleinere Auslagerungsdatei, oder die Datei auf die Windows-Partition legen (Auslagerungsdateien auf ntfs-3g sind heikel, eher nicht). zswap einschalten verringert Schreiblast. Alles eigenes Wissen, vorher testen.
  3. Windows-Partition (40 GB frei) und "Volume" (20 GB frei) verkleinern und `/media/oem/scan` vergroessern: bis zu rund 50 GB, aber Umpartitionieren mit Sicherung.
  4. Abgeschlossene Objekte als squashfs mit zstd archivieren (`mksquashfs <verz> <objekt>.sqfs -comp zstd -Xcompression-level 15`), nur lesbar einhaengbar, danach Original loeschen. `mksquashfs` und `zstd` sind installiert.
  5. `colmap-build` (6,3 GB) nach erfolgreichem Bau bis auf die Binaerdateien loeschen; `hf_cache` auf ungenutzte Modelle pruefen.
- Fuer neue npy-Zwischenstaende: `np.savez_compressed` oder zstd-gepackt schreiben, float32 statt float64, Tiefen als uint16 in Millimetern, wenn die Genauigkeit reicht (halbiert den Platz verlustarm). Eigenes Wissen; Kompressionsraten fuer COLMAP-Tiefenkarten wurden nicht gefunden. COLMAP selbst liest seine `.bin`-Karten nur unkomprimiert, Kompression geht dort nur als Archiv nach der Fusion oder ueber ein komprimierendes Dateisystem.
- Transparente Kompression (btrfs `compress=zstd`) verlangt Neuformatieren der Datenpartition; lohnt erst zusammen mit einer neuen Platte.
- Die USB-Toshiba-Platte (Modell MQ04UBF100, 2,5-Zoll-Festplatte) ist voll und ueber ntfs-3g langsam; als Arbeitslaufwerk ungeeignet, nur als Archiv. Fuer Arbeit: externe NVMe im USB-3.2/Thunderbolt-Gehaeuse mit ext4. Bei 100-240 $ je TB (Spanne der Quellen oben) kostet 1 TB grob 110-250 $ plus Gehaeuse.
- ntfs3 statt ntfs-3g fuer die internen NTFS-Partitionen nur fuer Lesezugriffe erwaegen; Schreiben grosser Pipelinedaten auf NTFS besser ganz vermeiden.

### Gaps
- Keine aktuelle (2025/2026) Messung ntfs3 gegen ntfs-3g gefunden.
- Keine Quelle zu Kompressionsraten von Tiefen-/Normalenkarten mit zstd, lz4, blosc2 oder zarr.
- JPEG-XL/WebP als Bildcache, jdupes/rmlint/borg, tmpfs: nicht recherchiert. tmpfs scheidet bei 15 GB RAM ohnehin weitgehend aus.
- Ob der Laptop einen zweiten M.2-Steckplatz hat, wurde nicht geprueft (Geraet oeffnen oder Datenblatt). Euro-Preise fuer SSDs nicht erhoben.

## Rechenleistung mieten oder 24-GB-Karte kaufen

### Takeaway
Mieten gewinnt klar: eine RTX 3090 kostet bei RunPod 0,22 $ je Stunde (Stand 12.11.2026), eine gebrauchte Karte 800-950 EUR und braeuchte am Laptop zusaetzlich ein eGPU-Gehaeuse; die Gewinnschwelle liegt bei mehreren tausend GPU-Stunden. Hetzner-GPU-Server sind Monatsmiete und fuer gelegentliche Laeufe unpassend.

### Cited Findings
- RunPod, Preisseite mit Stand 12.11.2026, Gemeinschafts-Cloud / sichere Cloud je Stunde: RTX 3090 24 GB 0,22 $ / 0,50 $; RTX 4090 24 GB 0,34 $ / 0,89 $; RTX A5000 24 GB 0,16 $ / 0,27 $; L4 24 GB 0,44 $ / 0,69 $; RTX 5090 32 GB 0,69 $ / 1,39 $. — [RunPod Preise](https://www.runpod.io/pricing)
- RunPod Speicher je GB und Monat: Container-Platte 0,10 $; Volume 0,10 $ laufend, 0,20 $ im Leerlauf; Netzwerkspeicher 0,07 $ (unter 1 TB). Die Seite nennt keine Gebuehren fuer ausgehende Daten. — [RunPod Preise](https://www.runpod.io/pricing)
- Vast.ai (Marktplatz, Preise schwanken stuendlich): Vergleichsseiten nennen fuer die RTX 3090 etwa 0,08-0,25 $ je Stunde, eine davon im Mittel 0,112 $ (Stand 04.08.2026). Nicht am Anbieter selbst geprueft. — [computeprices.com](https://computeprices.com/providers/vast/gpus/rtx3090), [getdeploying.com](https://getdeploying.com/reference/cloud-gpu/nvidia-rtx-3090)
- Hetzner: GEX44 232,30 EUR je Monat ohne MwSt. plus 114 EUR Einrichtung; GEX131-1 1197,30 EUR je Monat plus 599 EUR Einrichtung; gilt fuer Neubestellungen ab 15.06.2026. — [Hetzner Preisanpassung](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)
- Gebrauchte RTX 3090: eBay-Daten 800-950 EUR, erwartet stabil bei 750-950 EUR fuer den Rest von 2026. — [borncity](https://borncity.com/news/nvidia-rtx-3090-der-ungekroente-ki-koenig-des-gebrauchtmarkts/). Andere Quellen: Durchschnitt nahe 1000 $ ([insiderllm](https://insiderllm.com/guides/used-rtx-3090-buying-guide/)), niedrigster Monatsdurchschnitt 859 $ im Februar 2026 ([gpupoet](https://gpupoet.com/gpu/learn/price/february-2026/nvidia-geforce-rtx-3090)). Eine Quelle mit 360-540 EUR passt nicht zu den uebrigen und ist unglaubwuerdig.
- Lokal geprueft: Geraet ist ein Laptop mit Thunderbolt 4; interne Aufruestung der GPU ist nicht moeglich. — lokale Befehle `dmi product_name`, `lspci`, 15.11.2026

### Inferences
- Gewinnschwelle (eigene Rechnung): 850 EUR Karte geteilt durch rund 0,20 EUR je Stunde ergibt etwa 4000 GPU-Stunden, ohne Strom, ohne eGPU-Gehaeuse und Netzteil (Preis nicht erhoben, Thunderbolt kostet zudem Leistung). Bei 1-2 Stunden GPU je Objekt waeren das ueber 2000 Objekte. Kauf lohnt nur, wenn die Karte taeglich viele Stunden laeuft oder Daten das Haus nicht verlassen sollen.
- Kosten eines Mietlaufs: dichte Wolke 50-125 min lokal; auf einer 3090/4090 eher schneller. Ein Objekt kostet also etwa 0,20-0,70 $ GPU-Zeit plus wenige Cent Speicher. Zehn Objekte in einer Nacht parallel auf mehreren Mietkarten: wenige Dollar.
- Datenweg fuer 5 GB Fotos: bei 20 Mbit/s Hochladerate etwa 35 Minuten (5 GB x 8 / 20 Mbit/s), per `rsync -P` oder `rclone` wiederaufnehmbar. Zurueck muessen nur Kameras (`sparse/`), die fusionierte Wolke (einige 100 MB) und Logs, nicht die 17 GB Tiefenkarten. Das loest nebenbei das Plattenproblem fuer PatchMatch.
- Was 24 GB freischalten wuerden: PatchMatch in voller Bildgroesse und mit geometrischem Durchgang ohne Speicherdruck, mehrere GPU-Jobs gleichzeitig, groessere Abgleichnetze in voller Aufloesung. Netz-basierte Kameraberechnung (VGGT-Klasse) bleibt laut dem frueheren Bericht selbst mit viel mehr Speicher bei 300 Bildern kritisch, ist also kein Kaufgrund.
- Praktischer Einstieg: ein Startskript, das auf einer Mietmaschine COLMAP 4.3 mit CUDA bereitstellt (eigenes Docker-Abbild mit genau der lokalen Version, damit Ergebnisse vergleichbar bleiben), Daten holt, `tools/sfm_dicht.py` ausfuehrt, Ergebnis zurueckschiebt und die Maschine beendet. Die Tore (GPS, Grundriss, Foto-F1) laufen danach lokal.
- Datenschutz/Lizenz: Gemeinschafts-Cloud und Vast.ai laufen auf Rechnern Dritter; fuer Fotos oeffentlicher Gebaeude unkritisch, fuer fremde Bilder mit Personen abwaegen.

### Gaps
- Lambda und Paperspace: keine Preise erhoben. Vast.ai nicht an der Anbieterseite geprueft.
- Offizielle COLMAP-Docker-Abbilder mit CUDA fuer Version 4.3: nicht geprueft, ob vorhanden und aktuell.
- GPU des Hetzner GEX44 (vermutlich RTX 4000 SFF Ada mit 20 GB) von der Suche nicht bestaetigt.
- Preis und Leistungsverlust eines Thunderbolt-eGPU-Gehaeuses nicht erhoben.
- Kein Messwert, wie viel schneller COLMAP-PatchMatch auf einer 3090/4090 gegenueber der 4060 Laptop laeuft.

## Profilierung: wo die Zeit wirklich bleibt

### Takeaway
Dazu wurde keine Webquelle abgerufen; alles Folgende ist eigenes Wissen und als Vorschlag zu lesen. Der billigste belastbare Weg ist eine Zeit-, RAM- und GPU-Zeile je Stufe im gemeinsamen Log, ergaenzt um `py-spy` fuer einzelne CPU-Fresser.

### Cited Findings
- Snakemake fuehrt je Regel Buch ueber Code und Zeitstempel; eine `benchmark`-Angabe existiert (Details lagen im nicht gelesenen Teil der Doku). — [Snakemake Regeln](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html)
- Lokal geprueft: `nvtop` ist installiert, `py-spy` nicht. — lokaler Befehl, 15.11.2026

### Inferences
- Je Stufe ohne Zusatzwerkzeug: Befehl mit `/usr/bin/time -v` starten (Laufzeit, maximaler RAM), nach Ende `systemctl --user show rcpark-NAME -p CPUUsageNSec -p MemoryPeak` auslesen (Einheit dafuer nicht sofort einsammeln lassen). Verhaeltnis CPU-Sekunden zu Laufzeit zeigt sofort, ob eine Stufe einkernig laeuft.
- GPU-Verlauf mitschreiben: `nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used --format=csv -l 5 >> gpu_verlauf.csv` als Dauerdienst; zusammen mit den Stufenzeiten ergibt das die Leerlaufanteile der GPU je Stufe. `nvidia-smi dmon -s um -o T` liefert dasselbe kompakter. `gpu_wache.sh` und `gpu_messen.py` tun Teile davon bereits.
- CPU-Fresser in Python: `py-spy record -o profil.svg --pid <PID> --duration 60` an einem laufenden Job, ohne Neustart und ohne Codeaenderung; `py-spy dump --pid <PID>` zeigt bei Haengern, wo der Job steht. Installation per `pip install py-spy` (Lizenz MIT, nicht geprueft). scalene misst zusaetzlich GPU und Speicher, verlangt aber Start unter dem Profiler.
- Live-Blick: `systemd-cgtop` auf die Benutzerscheibe zeigt CPU und RAM je `rcpark-*`-Einheit; `nvtop` die GPU je Prozess.
- "Armaturenbrett" ohne Infrastruktur: ein kleines Skript, das die JSON-Zeilen je Stufe und `gpu_verlauf.csv` zu einem Balkenbild je Objekt (Stufendauer, GPU-Auslastung) rendert und neben die Stand-Datei legt.

### Gaps
- Keine Quellen zu py-spy, scalene, perf, systemd-cgtop abgerufen; Optionen vor Einsatz gegen `--help` pruefen.
- Ob `MemoryPeak` bei fluechtigen Benutzereinheiten unter systemd 255 nach Jobende noch abrufbar ist (wegen `--collect`), ist offen.

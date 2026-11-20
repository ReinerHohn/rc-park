# ⚙️ Betrieb: GPU, Jobs, Platten, Umgebungen, COLMAP-Bau, Git  ← [PROJEKT.md](../../PROJEKT.md)
Details: `modelle/GPU_PARALLEL_UNTERSUCHUNG.md` · Skill `langer-job` · `tools/INDEX.md` · CLAUDE.md Abschnitt Technik

## Gilt
- Lange Jobs nur `tools/job_start.sh` (systemd --user) mit `JOB_GPU_MB`/`JOB_RAM_MB`-Buchung, nie `run_in_background` [CLAUDE.md, Memory lange-jobs-systemd]
- GPU parallel nach VRAM-Budget (Summe ≤ 7000 MiB, Budget je Werkzeug gemessen), SIFT `RCPARK_SIFT_MAX=1600` [GPU_PARALLEL_UNTERSUCHUNG, Nutzer 6.11.]
- Jedes neue Rechenwerkzeug von Anfang an GPU; vorhandene Werkzeuge vor Start auf GPU-/CPU-only-Voreinstellung prüfen; Libs immer mit CUDA bauen [Memory feedback-gpu-bauen-immer, feedback-gpu-flag-pruefen]
- Immer maximal parallel (CPU 28 Kerne + GPU), aber nur verlustfreie Beschleunigung; genauere Methode als Standard [Memory immer-maximal-parallel, quality-over-speed]
- Große Daten nur auf der Datenplatte, Symlinks im Repo; Laufwerke per UUID benennen [REGELN Technik, Memory reference-laufwerke-uuid]
- Nach tools-Änderung: `schnelltest.sh` (30 s) + `regression.py --pruefen`; Schnappschuss nur bewusst erneuern mit Registereintrag [CLAUDE.md, Register AW]
- Kein wiederkehrender Wach-/GPU-Check-Zeitplan (stört den Nutzer) [Memory project-nachtwache-und-ssd, 15.11.]
- Sitzungsbeginn `hpwmi_pruefen.sh` (ohne Modul CPU ~38 statt 55 W) [Memory hpwmi-modul-pruefen]

## Versucht
**Rechner, GPU, Jobs, Platten**
- 03.11. · lange Jobs als Hintergrund-Shell → ✗ bei Speicherknappheit abgeschossen · systemd über `job_start.sh` [Memory lange-jobs-systemd]
- 05.11. · Umgebungsvariable vor `systemd-run` → ⚠ Falle · wird nicht vererbt; `job_start.sh NAME LOG env VAR=… cmd` [Memory lange-jobs-systemd]
- · `pgrep/pkill -f <skriptname>` → ⚠ Falle · trifft eigene Shell/Schleife; `systemctl --user is-active` [Memory lange-jobs-systemd, NICHTS_GEBRACHT 16.11.]
- 06.11. · „nur ein GPU-Job“ → ↺ VRAM-Budget · Absturz (Xid 31) erst bei ~7,8 GB Summe; Torch 4 GB + SIFT stabil, ~+70 % Durchsatz [GPU_PARALLEL_UNTERSUCHUNG]
- 06.11. · SiftGPU ohne Bildgrößen-Kappung → ⚠ Falle · nimmt bis 7,4 GB, scheitert still (0 Keypoints, rc 0); Keypoint-Tor nach Extraktion [GPU_PARALLEL_UNTERSUCHUNG]
- 15.11. · GPU-Buchung unter flock + RAM-Buchung (85 % MemTotal) in `job_start.sh` → ✓ Methode · Anlass OOM durch zwei große Jobs [STAND_2026-11-14 Z.128, 02888769a]
- 01.11. · GPU nur für Rasterung, Projektion in numpy → ✗ langsamer als CPU · GPU lohnt pro Datensatz, Daten oben halten (`render_kern.Szene` 17–21×) [Register S]
- 01.11. · float32 statt float64 für Höhenkarten → ✗ nicht bitgleich [Register D]
- 16.11. · GPU-Sichtbarkeit in `fassade_ortho` → ✗ langsamer · echter Engpass Fotos laden; erst messen, dann portieren [AUFGABENLISTE 1a, L53]
- 08.11./14.11. · Werkzeuge mit CPU-only-Voreinstellung ungeprüft gestartet → ⚠ Falle · `--gpu` vergessen, altes OpenCV-SIFT-Werkzeug [Memory feedback-gpu-flag-pruefen, feedback-gpu-bauen-immer]
- 13.11. · Ceres/pycolmap ohne CUDA („Falling back to CPU“ im Log) → ↺ Eigenbau mit CUDA + cuDSS · GPU-BA 13,6 statt 17,1 s, gleiches Ergebnis [Memory feedback-gpu-bauen-immer, project-colmap-versionen]
- 18.11. · Mapper-Eigenbau 4.3 neben pycolmap 4.2.1 → ⚠ Falle · DB-Schemabruch („No registered database factory“); Brücke `colmap_db_schema.py` [ZIEL V1i, project-colmap-versionen]
- 19.11. · CUDA-Bibliotheken für COLMAP aus venv-seg verlinkt → ⚠ Falle · torch-Update bricht COLMAP still; eigener CUDA-Ordner im Bauskript [LOGBUCH_KETTENTEST Z.322, 28a3ebe83]
- 19.11. · 4 Mapper gleichzeitig auf einer Datenbank → ✗ „database is locked“ · je Lauf eigene DB [LOGBUCH_KETTENTEST Z.224]
- 07.11. · PyTorch3D aus Quelle (c++20, CUDA aus Projektordner) → ✓ Methode · in venv-seg per `sys.path` (‑I ignoriert PYTHONPATH) [Memory pytorch3d-kompiliert]
- 20.11. · `tools/py` wählt Umgebung nach Importen, `job_start` warnt ohne Buchung → ✓ Methode [aac0f3201]
- 13.11. · Langlauf ohne Probeaufruf → ✗ scheiterte nach Stunden an falscher Signatur · neue Aufrufe vorher mit Dummy-Pfad [Memory feedback-smoketest-vor-langlauf]
- 16.11. · zwei Generatorläufe desselben Objekts gleichzeitig → ✗ unklarer Abnahmefehler · vor Bau `pgrep -f <objekt>_gen.py` [NICHTS_GEBRACHT 16.11.]
- 16.11. · „hängt auf einem Kern“ geraten → ↺ `faulthandler`-Stapel holen · Ursache Kameras 350 000 km entfernt [NICHTS_GEBRACHT 16.11. abends]
- 16.11. · zwei 4000-px-Feinläufe parallel auf 8 GB → ✗ CUDA OOM · je Lauf 4500 MiB, nichts daneben [NICHTS_GEBRACHT 16.11.]
- 18.11. · Fusion mit COLMAP-Cache (Vorgabe 32 GB > RAM) → ✗ OOM bzw. 1 Thread 4 h · Teilfusion nach Blickziel, volle Auflösung [ZIEL V1d–V1f, 6b6aec664]
- 18.11. · Platte voll während Tiefenkarten → ⚠ Falle · leere Karten brechen Fusion; kaputte Karten < 2 KB vorher löschen [ZIEL V1c]
- 08.11. · bitgleiche Kopien (Tiefenkarten je Variante) → ✗ Platte 100 % · verlinken, Schreibvolumen vorher rechnen [Memory feedback-platz-und-duplikate]
- 16.11. · Zwischendaten je Feld liegen lassen → ✗ 13,6 GB · Werkzeug räumt selbst auf [NICHTS_GEBRACHT 16.11.]
- 06.11. · Auslagern (`auslagern.sh`: rsync + Prüfsumme, dann Symlink) → ✓ Methode · nur kalte Daten [Register DJ, Memory toshiba-auslagerung]
- 17.11. · „alter Objektstand“ als kalt ausgelagert → ⚠ Falle · neue Objekte verlinkten hinein; vorher `find -L -lname` [Memory feedback-auslagern-nur-wirklich-kalt]
- 08.11. · zwei Platten mit gleichem Label am selben Mountpunkt → ⚠ Falle · Symlinks tot; per UUID führen [Memory toshiba-zwei-platten]
- 18.11. · Umzug auf 2-TB-SSD (`umzug_auslagerung.sh`, Links umbiegen) → ✓ Methode · rsync-Neulauf setzt Links zurück → Schlussdurchgang `--nur_umbiegen` [ZIEL Übergabe 17:40]
- 10.11. · Git-Packs per `alternates` auf Datenplatte → ✓ Methode · `.git` wuchs 1 GB/h durch Kreis-Commits; ohne Datenplatte kein git [Memory git-objekte-auf-datenplatte]
- 06.11. · CPU-Limit 25 W (RAPL) → ↺ eigenes hp-wmi-Modul, Profil performance · +50 % Durchsatz; 55/130 W ohne Mehrgewinn [Memory cpu-leistung-limit-25w, hpwmi-modul-pruefen]
- 15.11. · wiederkehrender Wach-Zeitplan (alle 20 min) → ✗ verworfen · störte, füllte Gespräch mit „nichts Neues“ [NICHTS_GEBRACHT 15.11.]

**SfM-Datenbanken & COLMAP-Bau**
- 01.11. · Referenznetz bei Matcher-Versuch ueberschreiben → ⚠ Falle · Backup VOR dem Lauf, `sparse_<seite>_<variante>` [VERSUCHSREGISTER AK]
- 19.11. · Kalibrator zweimal auf derselben DB → ⚠ Falle · schreibt Brennweiten/Paare hinein; immer eigene DB-Kopie [GLOBALER_MAPPER_STABIL 00:50]
- 19.11. · Kamera je Clip nur ueber images.camera_id → ⚠ Falle · Rig/Frame-Tabellen mitziehen (`sfm_db_variante.py`) [GLOBALER_MAPPER_STABIL 00:35]
- 19.11. · mehrere Mapper auf einer SQLite-DB → ⚠ Falle · "database is locked"; eigene DB-Kopie je Platz [LOGBUCH 19.11. 13:00]
- 19.11. · zwei globale Vollsatz-Laeufe parallel bei 15 GB RAM → ✗ · je ~6 GB, Auslagerung x3 [GLOBALER_MAPPER_STABIL 00:46]
- 19.11. · AnyCalib/FlexGlue mit CUDA-13-Bau → ⚠ Falle · ONNX braucht CUDA-12-Bibliotheken separat [GLOBALER_MAPPER_STABIL 00:40, LOGBUCH 22:20]
- 20.11. · COLMAP-Bau mit fremdem ONNX-Ordner → ⚠ CMake löscht dessen `lib/cmake` · Vorrat je Bau kopieren

**Git**
- 20.11. · ungepushte Arbeit auf dem GPU-PC (1159 Commits, 8,2 GB Binärdateien) → ✗ Katastrophe · Push je Arbeitsblock, Git-Sperre 1 MB/Geheimnisse

## Offen
- COLMAP-Versionen vereinheitlichen: pycolmap aus Bau-Quellstand (venv-colmap43) + A/B, umstellen nur wenn nicht schlechter (Stand 20.11., venv-colmap43 fehlt noch) [Memory project-colmap-versionen]
- GPU-Budget für 3–4 gleichzeitige Pipeline-Jobs (PatchMatch, LightGlue, Masken) nicht gemessen [GPU_PARALLEL_UNTERSUCHUNG Offen]
- CPU-Leistungsabfall nach 35–40 s (EC/geteiltes Budget?) ungeklärt [Memory cpu-leistung-limit-25w]
- Prüfstand-Commit-Sperre (`RCPARK_PRUEFSTAND_HOOK`) aus; aktiv nur Geheimnis-/Größen-Hooks – Aktivierung nur durch Nutzer (Stand 20.11.) [tools/git_hooks/installieren.sh, REGELN 8]
- Große Binärdateien schon auf GitHub (23 Pfade, 160 MB) entfernen? braucht Force-Push (Nutzer)

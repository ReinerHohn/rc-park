# Messplan Leistung (22.11.2026)

Werkzeug: `tools/leistung_messen.py` (messen / sweep / bericht, nur Standardbibliothek; Test `tools/test_leistung_messen.py` im Schnelltest).
Regel: jede Messung hier läuft ALLEIN (kein Kettenlauf, kein Agent rechnet), gestartet per `tools/job_start.sh`. Das Werkzeug meldet
`FREMDLAST` (System-CPU vor/während des Laufs deutlich über dem Prozessbaum) und aktive `rcpark-*`-Dienste; solche Messungen gelten nicht.
Ausgabe: `/media/oem/scan/rc-park_tmp/leistung/<name>_<zeit>/` (`bericht.md`, `sweep.json`/`messung.json`, `lauf_XX/befehl.log`).

## Rechner (gemessen 22.11.)
- i7-14700HX hybrid: logische CPUs 0-15 = 8 P-Kerne mit HT, 16-27 = 12 E-Kerne (`/sys/devices/cpu_core/cpus`, `cpu_atom/cpus`).
- numpy/scipy in venv-seg und venv-colmap: scipy-openblas 0.3.34 (pthreads, MAX_THREADS 64) - ohne Env nimmt OpenBLAS alle 28 Threads.
- perf: `/usr/bin/perf` ist der Ubuntu-Wrapper und scheitert (kein linux-tools für 6.17); `/usr/lib/linux-tools/6.8.0-51-generic/perf` läuft
  (perf_event_paranoid 1, eigene Prozesse, Ereignisse getrennt nach cpu_core/cpu_atom). `leistung_messen.py --perf` findet es selbst.
- turbostat: braucht `/dev/cpu/*/msr` (root) - nicht benutzt. Takt aus `scaling_cur_freq`, Energie aus RAPL `intel-rapl:0/energy_uj` (lesbar).
- Thermik: `core_throttle_count` seit Start ~28 000; in einer 2-s-Probe neben dem Kettenlauf +134 (Kerne), Paket 96 °C. ANNAHME: die
  Ausrichtungsmessung vom 22.11. (turbostat "kein Throttling") war ein günstiger Moment; der Zähler-Zuwachs wird jetzt je Lauf mitgeschrieben.

## Vorab-Beleg aus der Mini-Probe (neben dem Kettenlauf, also nur Hinweis)
300 Matrixprodukte 300x300 (venv-seg-numpy, ohne Env): 2,1 s Wand, aber 53 CPU-s = 25 Kerne, IPC 1,17. Diese Rechnung braucht
einfädig unter 1 s. ANNAHME (zu prüfen in M1): OpenBLAS verteilt kleine Produkte auf 28 Threads, die danach aktiv warten - dasselbe Muster
wie "Busy 99,6 % bei IPC 0,5" in der Ausrichtung.

## M1 - Ausrichtung, Thread-Sweep (wichtigste Messung)
Ziel: Ist `sfm_lod2_ausrichten.py` (3 x ~9 min je Nulllauf) einfädig mit Spin-Last? Welche Thread-Zahl ist "kleinste innerhalb 5 %"?
Threads im Code (gelesen, nicht gemessen): keine eigene Pool-/Env-Steuerung. CPU: numpy/OpenBLAS (Rotation `zu_modell` auf bis zu
600 000 Punkten, `--fit_punkte`), `scipy.optimize.least_squares` (einfädig, max 200 Auswertungen je Stufe, 3 Schwellen x 3 Runden),
`cKDTree(M)` in `abdeckung()` (je Kandidat neu gebaut, einfädig), `distance_transform_edt`, `np.add.at`. GPU (torch): Grob-FFT je Massstab
x Drehung, Residuen des Feinfits, `gpu_knn.naechster` (PyTorch3D). Blockgrößen: `--fit_punkte` (600 000), `--fein-punkte` (40 000),
`--zelle` (0,25 m Grobraster), `gpu_knn` blk 2 Mio. `ALIGN_CPU=1` erzwingt den CPU-Weg (Vergleich).
Befehl (aus dem Repo-Wurzelordner auf main, OHNE `--schreiben` - schreibt dann nichts ins Objekt, nur den LoD2-Cache `modelle/.cache_lod2`):
```
JOB_RAM_MB=8000 JOB_GPU_MB=2500 tools/job_start.sh leistung-ausr /media/oem/scan/rc-park_daten/job_logs/leistung-ausr.log \
  python3 -I tools/leistung_messen.py sweep --name ausr_threads --threads 1,2,4,8,16,28 --warmlauf --perf -- \
  /media/oem/scan/venv-seg/bin/python -u -I tools/sfm_lod2_ausrichten.py modelle/schwabentor-1122/objekt.json \
  --kameras /media/oem/scan/rc-park_daten/schwabentor-1122/pipe/kameras.json --dicht /media/oem/scan/rc-park_daten/schwabentor-1122/pipe/dicht/fused.ply \
  --name schwabentor-1122 --radius 30 --fotos /media/oem/scan/rc-park_daten/schwabentor-1122/fotos --loesung 0
```
Erwartet: 7 Läufe x ~9 min (mit 1 Thread ANNAHME eher kürzer) = ~65 min; RAM ANNAHME 3-5 GB (PLY 263 MB, 7,8 Mio Punkte float64),
VRAM ANNAHME < 2 GB. Danach ein zweiter Sweep nur 1 vs. 28 mit `--binden` (P-Kerne) und einer mit `--env OPENBLAS_THREAD_TIMEOUT=4`
(ANNAHME: kürzere Spinzeit, ungeprüft), je ~20 min. Schnellere Vorprobe (~1/3 der Zeit, ANNAHME): `--fit_punkte 150000` anhängen -
nur für die Skalierungskurve, nicht für die Endzahl.
Hinweis Fixture: `tools/test_gps_anker_fixture.json` enthält nur Kamerastandorte + GPS (GPS-Anker-Test, Sekunden) - für eine
Leistungsmessung zu klein; sie prüft nur, dass sich am Ergebnis nichts ändert. Ergebnisgleichheit je Thread-Zahl: Massstab/Drehung aus
`lauf_XX/befehl.log` ("Massstab SfM-Einheiten/m = ...") vergleichen - OpenBLAS-Summenreihenfolge kann die letzte Stelle ändern.

## M2 - SfM-Teilstufen einzeln (Nulllauf-SfM 73 min)
Zeiten aus `schwabentor-1122/pipe/pipeline.log` (Nulllauf 1122b, gelesen): Masken (handy_masken, GPU, OOM-Wiederholungen bei 1536 px),
Merkmale 0,7 min, Paarabgleich 6,3 min, "Abgleich (Paarliste)" 9,5 min, Seitenmapper je Teil ZWEIMAL (a/b: Teil 0 127 + 186 s, Teil 1
44 + 43 s), dichte Wolken je Teil 1495 + 369 + 137 + 79 s = 35 min. Größter Block = dichte Wolke (GPU, PatchMatch).
Messungen (jeweils `leistung_messen.py messen --perf -- <Befehl>`, allein; Eingaben vorher in einen Ordner unter `/media/oem/scan/rc-park_tmp/`
kopieren, damit die Kette nichts sieht):
- M2a Paarabgleich: `colmap` matcher auf einer KOPIE von `pipe/sfm/db.db` (796 MB) - Befehl/Optionen aus `tools/pipeline_objekt.py` übernehmen;
  erwartet ~6 min, GPU; Frage: GPU-gebunden (util > 60 %) oder CPU-Geometrieprüfung? Dann `--SiftMatching.num_threads`/GPU-Index-Sweep.
- M2b Seitenmapper Teil 0: `colmap global_mapper --database_path <kopie db_mapper.db> --image_path <fotos> --output_path <tmp>
  --GlobalMapper.image_list_path pipe/sfm/seiten_modelle/teil0.txt` (aus `tools/sfm_seiten_modelle.py:166`); erwartet 2-3 min, RAM ANNAHME 2-4 GB.
  Thread-Sweep über die Thread-Option des Mappers (Name vorher mit `colmap global_mapper -h` prüfen; ANNAHME `--GlobalMapper.num_threads`)
  per `--param T=1,4,8,16,28` und `{T}` im Befehl.
- M2c dichte Wolke Teil 1 (127 Bilder, ~6 min statt 25 min für Teil 0): `pipeline_objekt.py`-Stufe dicht bzw. `dicht_modell` auf einer Kopie;
  erwartet GPU-gebunden - prüfen, ob die GPU-Auslastung > 80 % ist oder Lücken hat (Fusion auf der CPU, Lesen der Bilder).

## M3 - seiten_luecken (Lauf 1122c 2680 s, 1122d 2643 s, jedes Mal rc 5)
Nicht als Leistungsmessung nötig - Ursache steht im Log (siehe Idee 3). Erst nach der Behebung messen:
`leistung_messen.py messen -- /media/oem/scan/venv-seg/bin/python -I tools/seiten_luecken.py <objekt.json> <fassade> --sparse ... --ref-db ... --download --holen`
auf einer Objektkopie (schreibt sonst in `audit/` und `seiten_nachholen`).

## Ideen aus dem Code (nur Vorschlag, nichts umgebaut)
1. **Dreifache Ausrichtung rechnet dreimal dasselbe.** `--loesung K` wählt nur einen anderen Index aus `_verschieden`
   (`tools/sfm_lod2_ausrichten.py:551-555`), davor laufen bei jedem Aufruf PLY-Lesen, LoD2, Grobsuche (17-33 Massstäbe x Drehungen),
   alle Feinfits und danach der Bootstrap (8 Feinfits, Zeile 568). `korrektur_loesung{k}` und `loesung0_zurueck`
   (`tools/gesamtkette.py:398` und `:407`) rufen das jeweils neu auf; Lösung 0 hatte schon die Stufe sfm gerechnet. Vorschlag: Liste
   `_verschieden` (p, B0, cm, Güte) als Zwischenstand mit `code_stand('sfm_lod2_ausrichten.py')` + Eingabe-Schlüssel (PLY-Größe/Zeit,
   kameras.json, Argumente ausser `--loesung`) speichern; Folgeaufrufe nur Bootstrap + Schreiben. Ersparnis ANNAHME ~2 x 8 min je
   Nulllauf mit Korrekturkreislauf. Risiko: Rechnung muss deterministisch sein (Seeds 0/1/3/7 fest; GPU-knn float32 - in M1 prüfen).
2. **Spin-Last der Ausrichtung** (hängt an M1). Ist "kleinste innerhalb 5 %" z. B. 1-4 Threads, dann in `tools/gesamtkette.py:398/407`
   für diese Stufe `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS` setzen: gleiche Zeit, ~28 Kerne frei für parallele Stufen, weniger Watt/Hitze
   (Throttle-Zähler). Ohne M1 nicht umsetzen.
3. **seiten_luecken wiederholt 44 min Fehlschlag in jedem Lauf.** 1122c und 1122d: f01 ungesehen, 175 Kandidaten, Nachholskript bricht nach
   ~44 min mit `Check failed: existing_frame.RigId() == frame.RigId()` (pycolmap, reconstruction.cc:327) ab -> rc 5. Die Marke
   `versucht_<hash>.txt` wird nur bei Erfolg geschrieben (`tools/seiten_luecken.py:108-109`), also läuft derselbe Versuch jedes Mal
   wieder. Vorschlag: (a) die RigId-Ursache im Nachholskript beheben (Kamera-/Rig-Zuordnung beim Einlesen der Neuzugänge, vermutlich
   `zusatzfotos_lightglue.py einlesen` bzw. `kameras_nachtragen.py` - ungeprüft); (b) bis dahin auch einen gescheiterten Versuch mit
   rc und Code-Stand markieren und nur bei geändertem Code/Kandidaten wiederholen. Ersparnis ~44 min je Lauf ab Stufe seiten.
   Zu "seiten_luecken nach vereinten Seiten überflüssig?": nein - f01 bleibt laut Bericht auch mit vereinten Seiten ungesehen; überflüssig
   ist nur die Wiederholung desselben Fehlschlags.
4. **Dichte Wolken für Teile, die nicht vereint werden** (Nulllauf 1122b: Teil 2 und 3, 137 + 79 s): `tools/sfm_seiten_modelle.py:335`
   rechnet für jeden Teil die dichte Wolke VOR dem Vereinen (Zeile 353 ff.). Die Klappung nutzt sie (`--dicht-a/--dicht-b`), der
   GPS-Rückfall nicht. Vorschlag: erst GPS-Vereinbarkeit prüfen, Wolke nur für vereinbare Teile. Ersparnis klein (~4 min), daher zuletzt.
5. **Seitenmapper a/b** (`tools/sfm_seiten_modelle.py:166`, je Teil zweimal) kostet bei Teil 0 ~3 min extra. Das ist eine Stabilitätsprobe
   mit Begründung im Docstring - nicht streichen, höchstens a und b parallel (CPU frei? M2b zeigt es).

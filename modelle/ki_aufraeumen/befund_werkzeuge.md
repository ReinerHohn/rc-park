# Werkzeug-Befund rc-park (20.11.2026) – Grundlage fuer Skills/Workflows

Ich habe nichts veraendert, nur gelesen und gezaehlt. Die Hilfsskripte liegen daneben: `cmds.py` (Auswertung der Sitzungen), `klass2.py` (Einteilung von tools/).

## 1. Einstiegspunkte

**Python-Umgebungen (gemessen)**
- `SEG=/media/oem/scan/venv-seg/bin/python -I`: die Analyse-Umgebung mit torch, trimesh usw. **Ohne pycolmap.**
- `COL=/media/oem/scan/venv-colmap/bin/python`: pycolmap 4.2.1.
- `GEN=~/.venvs/rcpark/bin/python`: Generator-Umgebung mit manifold3d und trimesh.
- System-`python3`: **ohne trimesh**. Trotzdem rufen bauen_abnehmen.sh, schnelltest.sh und kreis_regler das System-python3 auf, z. B. fuer platz_pruefen.py und py_compile.
- Den Mapper-Bau gibt es zusaetzlich als Binaerdatei: `/media/oem/scan/colmap-build/prefix/bin/colmap` (eigener Bau 4.3.dev).

**Die Einstiegspunkte im Einzelnen**
- **`./0-3d-modell.sh <Name> <Ort> [--ja|--trocken]`**, dazu `--status` und `--umgebung-sichern`. Es laeuft in dieser Reihenfolge ab:
  1. Prueft die Datenplatte und den freien Platz.
  2. Ruft hpwmi_pruefen auf.
  3. Prueft die 3 Umgebungen; fehlt eine, wird sie aus `tools/umgebung/*.txt` eingerichtet.
  4. Startet `tools/start3d.py`.
- **`tools/start3d.py`**: stellt Fragen und startet die Gesamtkette ueber job_start.sh. Es zeigt den Fortschritt und plant die Feinstufe als einmaligen systemd-Zeitgeber (`--nacht <ziel>`). Der Zustand liegt unter `/media/oem/scan/rc-park_daten/start3d-zustand/<kurz>.json`.
- **`tools/gesamtkette.py`**: Aufruf `$SEG tools/gesamtkette.py <quelle> --ziel <neu> [--ab S] [--bis S] [--trotz-lage] [--ohne-video] [--referenz-wolke npy]`. Der Bericht landet in `/media/oem/scan/rc-park_daten/<ziel>/gesamtkette_bericht.json`. Die Stufen in der Reihenfolge von STUFEN und die Werkzeuge je Stufe (aus dem Code):

| Stufe | Werkzeuge |
|---|---|
| anlegen | objekt_anlegen, rahmen_aus_lod2, fotoquellen |
| commons | commons_harvest, netz_fotos_holen |
| video | video_suchen (GPU), clips_waehlen, video_frames |
| vorpruefen | bilder_vorpruefen (GPU) |
| sammeln | fotos_sammeln |
| sfm | pipeline_objekt fein (SfM, Tiefenkarten GPU, LoD2-Abgleich), wolke_neu_fusionieren |
| tore | kamera_abdeckung, lage_gps_pruefen, wolke_grundriss_pruefen, wolke_gruppen_pruefen, kette_insel_pruefen, gps_seiten_pruefen, kamera_gelaende, modell_zerlegen; bei rc 3: sfm_lod2_ausrichten --loesung 1..max |
| dach | dach_vermessen (DOM1) |
| bauen | bauen_abnehmen.sh |
| kanten | kantenstufe |
| fototor | kameras_aus_buendel, kamera_plausibel --beiseite, foto_diff, foto_tor_bezug, dach_aus_fotos |
| fassaden | fassaden_kette, fassade_ortho, relief_aus_fotos_mono, netz_aus_dicht |
| fenster | fassade_fein, fassade_parsing, fenster_aus_parsing, oeffnungen_wandbild, oeffnungen_bogen, rueckwand_tiefe, innenwaende_finden, neben_fotos_waehlen, umriss_tor --eintragen |
| bauplan | fassade_fein/ortho/parsing, oeffnungen_wandbild, rueckwand_tiefe, innenwaende_finden, kantenstufe |
| seiten | seiten_luecken, fassade_ein_foto, fassade_tiefe, foto_auftrag |
| html | modell_3d_html |
| vergleich | Abstand zur Referenzwolke (optional) |
| druck | bausatz.sh |

  Der Standardwert von `--bis` ist vergleich. **Die Stufe druck laeuft also nur auf ausdruecklichen Wunsch.**
- **`tools/bauen_abnehmen.sh <obj> [--nur-pruefen]`**: arbeitet diese Schritte ab:
  1. Platztor (System-python3 platz_pruefen).
  2. Sperre ueber flock (`/tmp/rcpark_bau_<obj>.lock`, rc 5 = es laeuft schon ein Bau).
  3. Generator aus `objekt.json["generator"]`, immer `SCALE=87 ... ~/.venvs/rcpark/bin/python ...`.
  4. pruefstand.py und seiten_audit.py.
  5. Nebenpruefungen: fehlteile_finden, foto_breitenprofil, modell_neben_foto, umriss_tor, feinteil_tor, rundum_kanten, freiraum_audit, hoehe_gegen_dom1, druck_teilung, test_regeln_cb.

  Die Ausgabe ist lang, entscheidend ist die Zeile "alle Pruefungen bestanden".
- **`bash tools/schnelltest.sh`**: py_compile aller tools, bash -n, dazu 32 feste ok-Pruefungen an ober_tvdr. 15 test_*.py sind eingebunden.
- **`python3 tools/regression.py modelle/<obj>/objekt.json --pruefen | --schnappschuss | --ohne-kette`**: liest die Konfiguration aus `objekt.json["regression"]`. **Nur 6 von 25 Objekten haben eine.**
- **`JOB_GPU_MB=.. JOB_RAM_MB=.. tools/job_start.sh NAME LOG BEFEHL...`**: startet einen systemd-Benutzerdienst `rcpark-NAME`. Die GPU-Sperre richtet sich nach gpu_werkzeuge.txt und gpu_budget.txt. Das Ende steht im Log als `JOB_ENDE rc=<n>`; den Zustand zeigt `systemctl --user status rcpark-NAME`.
- **`tools/foto_check.sh <obj> <foto> [nr]`**: ruft `$SEG tools/foto_schnellcheck.py` auf. Es braucht `modelle/<obj>/audit/fotoauftrag.json`. Das Ergebnisbild ist `$TMPDIR/check_<name>.jpg`.
- **`python3 tools/p1s_print.py status | print <x.gcode.3mf> [name]`**: Druckerstart ueber MQTT/FTPS. paho fehlt in manchen Umgebungen (18-mal "No module named paho" in den Sitzungen). **SICHERHEIT: IP, Zugangscode und Seriennummer stehen hart im Repo.**
- **`bash tools/hpwmi_pruefen.sh`**: rc 0 = ok, rc 1 = "ACHTUNG KERNEL-MODUL".

## 2. Wiederholte Befehle (Sitzungsprotokolle)

**Datenlage:** 43 jsonl-Dateien mit 110 MB, darunter Subagenten. Insgesamt 26 571 Bash-Aufrufe, davon 11 686 seit dem 14.11.

**Haeufigste Werkzeuge in Bash-Befehlen** (Zahl = Befehle, die das Werkzeug nennen):

| Platz | alle Sitzungen | seit 14.11. |
|---|---|---|
| 1 | job_start.sh 1536 | job_start.sh 815 |
| 2 | bauen_abnehmen.sh 1041 | bauen_abnehmen.sh 701 |
| 3 | bauteil_kreis 682 | gesamtkette 425 |
| 4 | baukasten_gen 593 | bauteil_kreis 394 |
| 5 | pruefstand 511 | schnelltest.sh 298 |
| 6 | nullstart 488 | sfm_lod2_ausrichten 282 |
| 7 | foto_diff 428 | fassade_ortho 206 |
| 8 | gesamtkette 412 | bauteile 197 |
| 9 | regression 374 | pipeline_objekt 194 |
| 10 | sfm_lod2_ausrichten 317 | baukasten_gen 171 |
| 11 | editor_modell 301 | regression 136 |
| 12 | bauteile 293 | modell_3d_html 136 |
| 13 | schnelltest 275 | iphone_sfm 126 |
| 14 | sfm_netz 238 | modell_neben_foto 115 |
| 15 | fassade_ortho 235 | foto_mass 113 |
| 16 | fehlteile_finden 209 | foto_diff 113 |
| 17 | qualitaetsstufen 195 | steine_aus_foto 103 |
| 18 | pipeline_objekt 185 | teil_fotoform 101 |
| 19 | foto_kalibrieren 168 | objekt_anlegen 100 |
| 20 | foto_mass 153 | epilinie 98 |
| 21 | sfm_ausrichten 151 | kreis_regler 87 |
| 22 | teil_fotoform 148 | wand_ortho 85 |
| 23 | modell_3d_html 136 | modell_ansicht 81 |
| 24 | konvergenz_bericht 132 | lage_gps_pruefen 76 |
| 25 | modell_wettbewerb 125 | p1s_print 76 |
| 26 | viewer_kanten_bauen 124 | wolke_grundriss_pruefen 72 |
| 27 | kreis_regler 121 | seiten_luecken 70 |
| 28 | diff_parallel 120 | fenster_aus_parsing 67 |
| 29 | iphone_sfm 119 | kameras_aus_buendel 64 |
| 30 | objekt_anlegen 118 | foto_auftrag 64, druck_teilung 64 |

**Haeufige Folgen** (Werkzeug A, danach Werkzeug B):
- bauen_abnehmen -> pruefstand: 65
- bauen_abnehmen -> baukasten_gen: 39
- bauteil_kreis -> job_start: 39
- sfm_lod2_ausrichten <-> job_start: 34 und 25
- regression -> job_start: 30
- baukasten_gen -> bauen_abnehmen: 27
- kreis_regler <-> bauteil_kreis: 22 und 18
- bauteil_kreis -> teil_fotoform: 21
- nullstart -> sfm_netz: 19
- modell_neben_foto / modell_ansicht -> bauen_abnehmen: je 17

**Typische Ketten**
- (a) Generator aendern -> bauen_abnehmen -> pruefstand oder Sichtblatt -> regression.
- (b) Langer Job ueber job_start, danach `systemctl --user status` oder tail auf das Log, oft mit `sleep` gepollt (87-mal sleep seit 14.11.).
- (c) Ausrichtung: sfm_lod2_ausrichten -> Tore (lage_gps_pruefen, wolke_grundriss_pruefen).

**Weitere Befunde aus den Sitzungen**
- 55 % aller Bash-Befehle beginnen mit `cd`.
- Wie Python aufgerufen wurde: 10 399-mal venv-seg, **9 310-mal System-python3**, 1 681-mal venv-colmap, 761-mal rcpark.
- 224 Treffer "ModuleNotFoundError". Am haeufigsten fehlten trimesh (88), pycolmap (48), matplotlib (40), open3d (33), torch (32), fast_simplification (22) und paho (18). **Das ist ein klares Zeichen fuer Umgebungsverwechslung.**
- 651 Tracebacks, 234 "Killed", 103 "CUDA out of memory".
- 2 069 Tool-Ausgaben ueber 20 000 Zeichen, davon 947 seit 14.11. (8 %).

**Logbuecher:** 17 Dateien `modelle/LOGBUCH_*.md` mit 280 KB. Werkzeuge werden dort selten genannt, hoechstens 5-mal (pipeline_objekt, iphone_sfm, gitter_kurven, baukasten_gen); Thema der letzten Tage sind gitter_*, seiten_* und zusatzfotos_registrieren. Fuer eine Haeufigkeitszaehlung taugen sie nicht, es sind Erzaehltexte.

## 3. Aufraeum-Befund tools/

**Bestand:** 970 Dateien, davon 898 .py und 44 .sh. Dazu kommen `versuche/` mit 36 Skripten (flexglue_*, da3_*, datiert 1119/1120) sowie Vorlagen und Unit-Dateien.

**Einteilung** nach Token-Referenzen in Code, Doku seit 13.11. und Sitzungen seit 14.11.:
- **Kette (transitiv erreichbar aus gesamtkette, bauen_abnehmen, start3d): 330.** Direkt aufgerufen werden nur ca. 89; die 330 sind eine Obergrenze, weil Token-Treffer mitzaehlen. Beispiele: bauteile, foto_diff, pruefstand, sfm_lod2_ausrichten, fassade_fein, kantenstufe, baukasten_gen.
- **Pruef- oder Hilfswerkzeug, von einem anderen Tool oder vom schnelltest referenziert: 165.** Beispiele: muster_fit, kanten_tor, handy_kalibrieren, giebelhaus_generator, gitter_kurven, pose_vertrauen.
- **Nur in Doku oder Sitzung der letzten Woche genannt: 203,** davon 15 mit Versuchs- oder Altnamen. Beispiele: buendel_stuetz, bildwert, eggcrate_sim, `_test_baukasten_gen.py`, teilmodell_sim3, generator_ausrichten2, linach_v4.
- **Tests (test_*.py): 80.** Nur 15 davon laufen im schnelltest. 31 haben kein gleichnamiges Zielwerkzeug, z. B. test_bogenform, test_buendel_synthetisch, test_flat_plates.
- **Vermutlich tot: 164,** also nirgends referenziert und weder in Sitzung noch Doku seit 13.11.
  - 30 davon tragen Alt-Objekt- oder Standnamen, z. B. hirschsprung_osm_CHECKPOINT_362/400, hirschsprung_osm_STAND_sehrgut/quadrat_ost, 10 hirschsprung_*, 15 linach_* (dam_v2, v3, v4), 10 hofgut_*, gs_kaufhaus_train2.
  - Weitere: konsolen_sweep, oberkirch_measured, truss_kit, modellgen, **rcpark_deals**, modell_validator, tunnel_floor_portal, todtnau_bruecke, triberg_wasserfall, lod2_to_blender, combined_view, plane_segment.

**Hinweise zu Duplikaten und Varianten**
- Versionsnamen: koerper_v10/v11, linach_dam_v2/v3, handy_masken_v2, generator_ausrichten2, gs_kaufhaus_netz2/train2.
- Namensfamilien: 57 foto_*, 45 wolke_*, 25 kanten_*, 19 kamera_*, 13 sfm_*, 13 gitter_*, 11 rippen_*.
- Mehrere SfM- und Ausrichtungswege nebeneinander: sfm_ausrichten, sfm_lod2_ausrichten, sfm_lod2_buendel, sfm_netz, nullstart, pipeline_objekt, iphone_sfm.
- Die Generatoren liegen gemischt in tools/ (baukasten_gen, kaufhaus_measured, terrain_eggcrate) und in modelle/*_gen.py.

**Groessen**
- baukasten_gen 169 KB / 1469 Zeilen, bauteil_kreis 161 KB / 1599, editor_modell 113 KB, bauteile 113 KB, qualitaetsstufen 91 KB, foto_diff 76 KB.
- 217 Dateien haben Zeilen mit mehr als 300 Zeichen; in gesamtkette ist die laengste Zeile 783 Zeichen lang.
- 362 von 898 .py haben kein argparse, 195 davon lesen sys.argv direkt (kein `--help`).
- Nur 296 nennen in den ersten 15 Zeilen ihre Umgebung.
- 378 haben `sys.path.insert`.
- 179 enthalten Objektnamen hart (schwabentor/martinstor), 57 den Pfad rc-park_daten hart.

## 4. Vorschlaege

### Skills (`.claude/skills/<name>/SKILL.md`)

1. **`abnahme`**: nach jeder Generatoraenderung. Die Befehle:
   - `tools/bauen_abnehmen.sh <obj> 2>&1 | tail -40`
   - `grep -c "alle Pruefungen bestanden"`
   - Read `modelle/<obj>/audit/seiten.jpg` und `audit/neben_*.jpg` (je Seite eines)
   - `python3 tools/regression.py modelle/<obj>/objekt.json --pruefen | tail -15`, falls ein "regression"-Block existiert
   - Danach die Prozentzahl melden und eine Fehlerliste je Teil. Bei rc 5 nicht neu starten (es laeuft schon ein Bau).
2. **`werkzeug-aendern`**: der Ablauf nach einer Aenderung in tools/.
   - `bash tools/schnelltest.sh 2>&1 | grep -v '^  ok' | tail -20`
   - `python3 tools/regression.py modelle/ober_tvdr/objekt.json --pruefen`
   - Nur eigene Dateien committen, mit den Attribution-Zeilen.
   - Dazu eine Umgebungstabelle: Was importiert pycolmap -> COL, trimesh/manifold -> GEN, torch -> SEG.
3. **`langer-job`**: `JOB_GPU_MB=<n> JOB_RAM_MB=<n> tools/job_start.sh NAME /media/oem/scan/rc-park_daten/logs/NAME.log $SEG -I tools/X.py ...`. Den Zustand mit `systemctl --user is-active rcpark-NAME` und `grep JOB_ENDE LOG` abfragen; warten nur per Monitor-until, nie per sleep. Dazu die Budgets aus tools/gpu_budget.txt (SIFT 1600).
4. **`gesamtkette`**: Neustart oder Teillauf.
   - Ganzer Lauf: `./0-3d-modell.sh <Name> <Ort> --ja` oder `tools/job_start.sh kette_<ziel> LOG $SEG -I tools/gesamtkette.py <quelle> --ziel <ziel> --ab <S> --bis <S>`
   - Bericht lesen: `jq '.stufen' /media/oem/scan/rc-park_daten/<ziel>/gesamtkette_bericht.json`
   - Danach die Tore nach CLAUDE.md: kamera_abdeckung, wolke_grundriss_pruefen, lage_gps_pruefen.
5. **`foto-check`**: wenn der Nutzer ein Foto hochlaedt.
   - `tools/foto_check.sh <obj> <datei>`
   - Antwort: PASST / PASST NICHT plus eine Anweisung, dazu das Bild `$TMPDIR/check_*.jpg` zurueckschicken.
   - Fotobedarf: `$SEG -I tools/foto_auftrag.py ...`
6. **`fassade-wandbild`**: Fassadenkette nach PIPELINE_FASSADEN.md.
   - `$SEG -I tools/gesamtkette.py <q> --ziel <z> --ab fassaden --bis bauplan`
   - Einzelschritte: fassade_fein, tiefe_lokal, relief_aus_fotos_mono, fenster_aus_parsing, umriss_tor --eintragen
   - Dazu Bilder `<x>_foto.jpg` ansehen.
   - Bei linienhaften Features: kanten_tiefe_sweep_flaeche -> kanten_features --farbe stabil --sweep -> features_in_objekt.
7. **`ausrichtung-tore`**:
   - `$COL tools/sfm_lod2_ausrichten.py ... --loesung N`
   - Danach `tools/kamera_abdeckung.py <sparse>`, `tools/wolke_grundriss_pruefen.py <obj.json> --wolke <npy>` (rc 3 = falsches Teilnetz) und `tools/lage_gps_pruefen.py <obj.json> <SFM-AUSRICHTUNG.json>`.
   - Vorher im Register nach Seitenverwechslung suchen: `grep -n -i seitenverwechsl modelle/VERSUCHSREGISTER_MARTINSTOR.md | head`.
8. **`drucken`**:
   - `tools/bausatz.sh <obj>` (Stufe druck)
   - druck_teilung und `druck.splitter_verwerfen` pruefen
   - `python3 tools/p1s_print.py status`, danach `print <x.gcode.3mf>`
   - Regel: Details auf Bambu, Wand auf MK4S.

### Workflows (mehrere Agenten)

- **A Bauteil-Runde mit Pruefer:**
  - Ein Bau-Agent arbeitet je Bauteil im Worktree. Sein Auftrag ist der Abschnitt "Auftragstext" aus `modelle/VORLAGE_BAUTEIL_RUNDE.md`; der Ablauf ist Stufe 0 Formbeschreibung -> Messen (foto_mass, foto_zaehlung) -> Generator -> `tools/bauen_abnehmen.sh` -> teil_fotoform / foto_diff.
  - Ein Pruefer-Agent mit frischem Kontext prueft nur Formbeschreibung, Bericht, neben_*.jpg und das JSON-Urteil.
  - Das ersetzt bzw. umhuellt `tools/bauteil_kreis.py` (dort `claude -p` sonnet/opus) und kreis_regler.
- **B Abnahme mehrerer Objekte parallel:**
  - Je Objekt ein Agent, Liste aus `ls modelle/*/objekt.json`.
  - Jeder Agent ruft `tools/bauen_abnehmen.sh <obj> --nur-pruefen`, `regression.py --pruefen --ohne-kette` und Read seiten.jpg auf.
  - Ergebnis: eine Zeile je Objekt (bestanden, Prozent, Fehler).
  - Die flock-Sperre verhindert Doppelbau; die GPU-Jobs bleiben ueber job_start.
- **C Recherche + Messung:**
  - Ein Agent sucht Quellen: commons_harvest, seiten_luecken --download --holen, Dokumente.
  - Ein zweiter misst parallel: foto_mass, foto_zaehlung, wand_ortho.
  - Der Koordinator traegt `beobachtungen_offen` und `beleg()` in masstabelle.json ein. Quellenwidersprueche nicht mitteln.
- **D Werkzeug-Aenderung mit Gegenprobe:**
  - Ein Agent aendert das Werkzeug.
  - Ein zweiter laeuft parallel `schnelltest.sh` plus `regression.py --pruefen` auf allen 6 Objekten mit Regression und vergleicht mit main.
  - Ein dritter ist Code-Review ohne Kenntnis der Absicht.

## 5. Was am meisten bremst, und was dagegen hilft

1. **Python-Umgebung verwechselt.** System-python3 wird 9 310-mal benutzt, es gibt 224 ModuleNotFoundError.
   - Abhilfe: Starter `tools/py seg|col|gen <tool>`, oder ein Kopfkommentar `# UMGEBUNG: seg` je Tool, den eine Kopfzeile auswertet.
   - Ein PreToolUse-Hook warnt bei `python3 tools/X.py`, wenn X pycolmap oder trimesh importiert.
   - bauen_abnehmen.sh und schnelltest.sh sollten fuer platz_pruefen und regression ausdruecklich $SEG nehmen.
2. **Riesige Pflicht-Dokumente.** VERSUCHSREGISTER_MARTINSTOR hat 348 KB, NICHTS_GEBRACHT 171 KB, STAND_2026-11-14 139 KB, PIPELINE_FASSADEN 86 KB, ZIEL_PIPELINE_H0 24 KB; modelle/*.md sind zusammen 2,7 MB in 154 Dateien.
   - Abhilfe: je Datei ein kurzer Index (Stichwort -> Abschnitt/Zeile) und ein grep-Rezept im Skill.
   - STAND und ZIEL in "UEBERGABE aktuell" (max. 3 KB) und Archiv teilen.
   - VORLAGE_BAUTEIL_RUNDE verweist noch auf "CLAUDE.md Regeln 2, 3b, 3c, 8b, 9 ..."; diese Nummern stehen jetzt in REGELN_AUSFUEHRLICH.md. Die Verweise sind veraltet.
3. **Lange Ausgaben.** 947 Tool-Ausgaben ueber 20 000 Zeichen seit 14.11.; bauen_abnehmen erzeugt sehr viel Text.
   - Abhilfe: ein Schalter `--kurz` bzw. `RCPARK_KURZ=1`, der nur Ergebnis, rc und Pfade druckt.
   - Am Ende eine maschinenlesbare Summenzeile (`ABNAHME rc=0 bestanden=1 fehler=0 blatt=...`), wie schon `JOB_ENDE rc=`.
4. **Fehlende --help und lange Zeilen.** 362 .py ohne argparse; 217 Dateien mit Zeilen ueber 300 Zeichen (Read und Edit werden unzuverlaessig, old_string trifft schlecht).
   - Abhilfe: mindestens Docstring plus argparse fuer die Top 60 aus Abschnitt 2.
   - Eine erzeugte Datei `tools/INDEX.md` mit Zweck, Aufruf, Umgebung und Gruppe je Tool aus den Docstring-Kopfzeilen; ein Skill liest nur sie.
5. **Riesendateien.** baukasten_gen (169 KB) und bauteil_kreis (161 KB) laden viel Kontext. Abhilfe: in Module teilen (Messung, Auftrag, Pruefung) und die Funktionen in bauteile.py nach Familien gruppieren.
6. **Toter und doppelter Bestand.** ca. 164 vermutlich tote Tools, 30 davon Alt-Objekt-Skripte (hirschsprung, linach, hofgut, CHECKPOINT/STAND-Kopien), dazu 31 verwaiste Tests und mehrere SfM-Wege nebeneinander. Das stoert Suche und grep.
   - Abhilfe nach Freigabe durch den Nutzer: nach `tools/archiv/<thema>/` bzw. `tools/versuche/` verschieben (git mv). Den schnelltest-Syntaxcheck nur auf aktive Tools anwenden.
7. **Pfade.** 55 % der Bash-Befehle beginnen mit `cd`; 179 Tools enthalten Objektnamen hart und 57 den Datenpfad.
   - Abhilfe: eine gemeinsame `tools/pfade.py` (ROOT, DATEN, `objekt_dir(obj)`, `daten_dir(obj)`).
   - In settings eine Erlaubnis fuer `cd /home/oem/git/rc-park && ...`; `/fewer-permission-prompts` nutzen (`.claude/settings.local.json` hat 0 Bash-Freigaben).
8. **Pollen statt warten.** 87 sleep-Aufrufe seit 14.11. Abhilfe: Skill `langer-job` mit Monitor-until auf `JOB_ENDE`.
9. **Speicher und GPU.** 234 "Killed", 103 CUDA-OOM. Abhilfe: job_start sollte bei fehlendem JOB_GPU_MB und fehlendem gpu_budget-Eintrag laut warnen; ein Skill nennt die Budgets.
10. **Regression deckt wenig ab.** Nur 6 von 25 objekt.json haben einen "regression"-Block. Abhilfe: einen Block fuer die aktiven Objekte ergaenzen (schwabentor, martinstor-1120, kaufhaus_grob3).
11. **Sicherheit.** p1s_print.py enthaelt Zugangscode und Seriennummer im Klartext im Repo. Abhilfe: in `~/.config/rcpark/p1s.json` auslagern.

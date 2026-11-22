# RC-Park Freiburg – Arbeitsregeln
## 🔥💥 ZUERST LESEN: `0_DURCHBRUCH_AGENTEN_SCHLEIFE.md` – GIGANTISCHE, BOMBENGEILE HARDCORE-ERFAHRUNG (Nutzer 22.11.2026) 💥🔥
Skill `kette-schleife`. Kettenlauf -> Nebeneinander-Bild ansehen -> je Befund ein Agent (Vorlage, Worktree, opus, Kettenstufe+Test, nicht rechnen waehrend Kette) -> Merge nur bei Schnelltest 0 -> naechster Lauf. Bild schlaegt Zahl.
Gesamtprojekt: Miniatur-Wunderland zum Selbersteuern (Konzept/Businessplan) + 3D-Pipeline Fotos -> SfM (COLMAP) -> druckbares H0-Modell (1:87), wird verkauft.
Vision `KONZEPT.md`, Dokumentindex `README.md`. Deutsch, Anrede "mein grosser Meister", keine breiten Tabellen.
WISSENSBAEUME (nie ganze Ordner/grosse Dateien lesen):
- Gesamtprojekt/Geschaeft: `PROJEKT.md` -> `Doku/projekt/<ast>.md` (Gilt · Versucht · Offen; vor neuem Ansatz "Versucht" lesen, nach Versuch eine Zeile eintragen). Businessplan: `./start.sh` bzw. `python3 build.py`.
- 3D-Pipeline: `modelle/INDEX.md` -> Ast -> grosse Datei ueber `modelle/inhalt/<name>.md` (Read offset/limit); Werkzeuge `tools/INDEX.md` -> `tools/index/<thema>.md`; Archiv `modelle/archiv/INDEX.md`. Neu erzeugen: `python3 tools/baum_erzeugen.py`. Volltext Regeln: `modelle/REGELN_AUSFUEHRLICH.md`.
Stand 3D zuerst: `modelle/ZIEL_PIPELINE_H0.md` (UEBERGABE/NACHTRAG am Ende) -> dort verlinktes Logbuch. Sitzungsbeginn: Skill `sitzungsbeginn`.

## KERNMETHODE (nie vergessen)
- Form = Fotokanten + Triangulation (Kanten-Tiefen-Sweep mit SfM-Kameras). SfM liefert die KAMERAS. Dichte Wolke/LoD2/DOM1 nur Lage-Veto, Hoehe, Gegenprobe.
- WANDBILD = BAUPLAN: Wand aus vielen Fotos entzerrt (`tools/fassade_fein.py`) + Tiefe je Zelle -> Gestalt nachbilden. Erkennen = nur Zone/Loch. Keine Musterteile; Katalog nur Freistehendes.
- Jede Kette: Kantenstufe + Foto-F1 (`tools/teil_fotoform.py`) + `tools/foto_diff.py` als Tor.
- Formfamilie aus >= 3 Fotos. Zaehlen nur am Foto (`tools/foto_zaehlung.py`), Masse nur `tools/foto_mass.py`.
- Quellen nicht mitteln; Lage unabhaengig belegen (GPS, DOM1-Hoehe, Massstab). Neue Objekte: Fotos -> SfM -> LoD2 nur Abgleich.
- Ungesehene Wand nie spiegeln/erfinden -> Fotos suchen. Neue Bauteile nur generisch in `tools/bauteile.py`.
- Symmetrische Tuerme: Seitenverwechslung pruefen; globale Modelle erst `tools/modell_zerlegen.py`, dann bewerten.
- Verwerfen nur mit benannter Ursache. Vor neuen Versuchen: `modelle/NICHTS_GEBRACHT.md`, `modelle/VERSUCHSREGISTER_MARTINSTOR.md`, `modelle/LIZENZ_WERKZEUGE.md` (nur verkaufstaugliche Lizenzen; NC nur Test).

## Pflicht-Pruefungen (Ablauf je Skill)
- Generatoraenderung -> Skill `abnahme` (`tools/bauen_abnehmen.sh <objekt>`; nur bei "alle Pruefungen bestanden" weiter; Sollwerte nie lockern ohne neue Quelle + `historie`).
- tools-Aenderung -> Skill `tools-pruefen` (`bash tools/schnelltest.sh`, dann `tools/regression.py ... --pruefen`).
- Nach dichter Wolke -> Skill `wolke-tore`.
- Sichtbeobachtung = Testauftrag: erst `beobachtungen_offen` in `masstabelle.json`, dann messen, dann Generator.
- Zahlen allein gelten nicht: `audit/seiten.jpg` + `audit/neben_*.jpg` ansehen. Fehlerliste vor Lob, Realitaets-% melden. Annahmen heissen `ANNAHME: ...`.

## Technik
- Grosse Daten nie auf Root: `/media/oem/scan/...` (knapp) bzw. `/media/oem/rcdaten` (gross), Symlinks. HART (Nutzer 20.11.): intern (Root, scan, Volume) nur was laufend gebraucht wird - Abgeloestes/Altes sofort nach `/media/oem/rcdaten` auslagern (`tools/auslagern.sh`, Pruefsumme), wirklich Kaltes dort packen (tar+zstd, nicht JPG/Video). Ohne /media/oem/scan kein git. Toshiba-Platte nie anfassen.
- Python: `/media/oem/scan/venv-seg/bin/python -I` (torch/CUDA), `/media/oem/scan/venv-colmap/bin/python -I` (pycolmap), Generator `~/.venvs/rcpark` (trimesh). Einfachster Weg: `tools/py <werkzeug.py> ...` (waehlt die Umgebung nach Importen). Nackter `python3` hat weder trimesh noch pycolmap (224 Fehler bisher).
- Lange Jobs nur per Skill `langer-job` (`tools/job_start.sh` mit JOB_GPU_MB/JOB_RAM_MB); vorher Dummy-Test; GPU immer nutzen, VRAM-Summe <= 7000 MiB.
- Nie zwei Optimierer/Generatorlaeufe mit gleicher Zwischendatei parallel. Nie `pkill -f` mit Muster aus der eigenen Befehlszeile.
- Git-Hooks (Geheimnisse, Dateien > 1 MB ohne LFS) einmal je Rechner: `bash tools/git_hooks/installieren.sh`. Loeschen nur nach ausdruecklichem "Ja". Eigene Aenderungen sofort committen UND nach jedem Arbeitsblock pushen (Nutzer 20.11.: lokal 1157 Commits ungepusht = Katastrophe; zwei Rechner arbeiten am Repo) - vorher `git fetch` + zusammenfuehren. Attribution-Zeilen. Hook nur Nutzer.
- Nie idle, nachts weiterarbeiten; aber KEIN wiederkehrender Cron/Loop fuer Job-/GPU-Checks (einmalige Warter ok).
- Kontext sparen: Ausgaben kuerzen (cut/head/tail). Bilder (SendUserFile) + 3D-HTML zeigen. Kein Druck ohne Nutzerwunsch.

## Bei Aufgabe X -> Skill / Dokument
- Neues Objekt / Kette von null -> `objekt-von-null`. SfM/Mapper -> `modelle/GLOBALER_MAPPER_STABIL.md`.
- Symmetrischer Turm, Seitenverklebung, globaler Mapper je Seite, Seiten vereinen -> `modelle/METHODE_SEITEN_SFM.md`.
- Foto vom Nutzer vor Ort -> `foto-vor-ort`.
- Bauteil neu/falsch -> `bauteil-runde` (`modelle/VORLAGE_BAUTEIL_RUNDE.md`).
- Fassaden/Fenster/Relief/leere Wand -> `fassaden` (`modelle/PIPELINE_FASSADEN.md`).
- Rippen/Baender/Leisten/Staebe -> `linien-features`.
- Vorbauten/Erker, Ebenen, Abweichungsschleife, "Kette soll den Handstand erreichen" -> `modelle/METHODE_EBENEN_BAUPLAN.md`.
- Drucken -> `druck`.
- Lehren: `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md` (Lehren-Register). Platten: Memory reference-laufwerke-uuid.

## Weitere Regeln (vom anderen Rechner, 20.11.2026)
- Kein Hardcoding - alles erkennen: Masse/Stueckzahlen/Formen aus Daten/Fotos -> JSON -> generischer Generator; bei Fehler den Detektor fixen, nicht den Wert.
- Erst die Realitaet zaehlen, dann bauen; selbst hinschauen - Score != Ergebnis, Foto-Grundwahrheit schlaegt Juror-Mehrheit.
- Parametrisch-gueltig, nie degeneriert: keine freien Multiplikatoren auf gemessene Geometrie; Gueltigkeits-Guard + Fallback.
- Aenderungs-Waechter `python3 tools/aenderung_check.py` nach Modell-Aenderungen (Heatmap gegen Foto). Harte Tests: `python3 tests/test_quellen_hart.py`, `tests/test_hybrid_hart.py`.
- Businessplan-Schaetzungen = begruendete Annahmen (oeffentliche Benchmarks), keine testierte Finanzplanung.
- ENTSCHIEDEN 20.11.2026 (Nutzer: "was neuer ist, ist besser"): fuer Gebaeude gilt die KERNMETHODE oben - Fotos -> SfM -> Form aus Fotokanten, LoD2 nur Abgleich (ersetzt "Massing aus LOD2 schlaegt Foto-Schaetzung", Okt.); Feindetail = echte Loecher/Relief aus dem Wandbild, aber druckbar (Mindestmass 0,8 mm, keine Mikroteile) statt nur Textur/Bemalung.

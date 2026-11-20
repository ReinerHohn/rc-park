# Aufraeumen Regeln/Skills – Bericht (20.11.2026)
Gelesen: CLAUDE.md, modelle/REGELN_AUSFUEHRLICH.md, ZIEL_PIPELINE_H0.md (Anfang+UEBERGABEN), PIPELINE_FASSADEN.md (Gliederung), REZEPT_GEBAEUDE_AUS_FOTOS.md (Gliederung+Schritte), GLOBALER_MAPPER_STABIL.md (Rezept), VORLAGE_BAUTEIL_RUNDE.md, LIZENZ_WERKZEUGE.md (Zweck), LOGBUCH_KETTENTEST_2026-11-19.md (UEBERGABE), Memory-Dateien (MEMORY.md + feedback-/project-/reference-/user- + alte Kurznamen aus dem Index).
Alle unten genannten Pfade per ls geprueft; Fehlende sind mit FEHLT markiert.
Abk.: CL=CLAUDE.md, RA=modelle/REGELN_AUSFUEHRLICH.md, M:=memory/<datei>.md

## 1. HARTE REGELN (dedupliziert)

### Methode / Form
1. Form aus Fotokanten + Triangulation (Kanten-Tiefen-Sweep mit SfM-Kameras); SfM liefert v.a. Kameras; Wolke/LoD2/DOM1 nur Lage-Veto, Hoehe, Gegenprobe. (CL KERNMETHODE, RA 9d/9e, M:feedback-kernmethode-fotokanten, M:feedback-foto-tor-statt-wolke)
2. Jede Kette braucht Kantenstufe + Foto-F1 (`tools/teil_fotoform.py`) + `tools/foto_diff.py` als Tor. (CL)
3. Wandbild = Bauplan: Gestalt aus `fassade_fein.py` + Tiefe (`tiefe_lokal.py`, `relief_aus_fotos_mono.py`) nachbilden; Erkennen nur Zone/Loch; keine Musterteile; Katalog nur Freistehendes, auch dann Form aus Fotokanten. (CL, M:feedback-form-aus-wandbild-nicht-muster)
4. Leere Wolke ist kein Datenmangel, wenn Merkmal in >= 3 Fotos sichtbar; erst Fotos je Teil zaehlen. (RA 9e, M:feedback-foto-tor-statt-wolke)
5. Formfamilie aus >= 3 Fotos (Stufe 0) VOR jeder Messung; Form nie per Kennzahl-Sweep waehlen (F1-Diff < 0,03 = gleich). (RA 9d, VORLAGE_BAUTEIL_RUNDE)
6. Zaehlen nur am Foto (`tools/foto_zaehlung.py`), nie aus Wolke/LoD2/Generatordateien; Etikett ehrlich. (RA 9, M:zaehlen-nur-am-foto)
7. Fotomasse nur ueber `tools/foto_mass.py`; Massstab aus Modell = zirkulaer; echte Meter nur ueber amtliche Anker. (RA 3c/3d)
8. Quellen-Blindheit beachten; Widersprueche nicht mitteln, als Beobachtung stehen lassen. (RA 4/5)
9. Linienhafte Features nie nach Farbschwelle/Wolke: Sweep -> `kanten_features.py --farbe stabil --sweep` -> `features_in_objekt.py`. (CL, RA Abschnitt Linienhaft)
10. Ungesehene Wand: nie spiegeln/erfinden; Fotos suchen (`seiten_luecken.py --download --holen`, `fassade_ein_foto.py`). (CL, M:feedback-ungesehene-seite-fotos-suchen, M:feedback-lehren-fotos-ausreizen-1611)
11. Neue Bauteile nur als generische Funktion in `tools/bauteile.py` (+ Katalog in PIPELINE_FASSADEN.md); keine Objektnamen im Code; jede Lehre generalisieren (Lehren-Register REZEPT). (CL, M:feedback-generische-werkzeuge, M:feedback-jeden-schritt-generalisieren)
12. Neue Objekte: Fotos -> SfM -> LoD2 nur Abgleich, nie umgekehrt. (M:feedback-foto-wolke-zuerst-dann-lod2)
13. Lage unabhaengig belegen (Foto-GPS, Fernkameras, DOM1-Hoehe, Massstab); Fit und Beweis trennen. (M:feedback-lage-unabhaengig-belegen, M:feedback-lehren-schwabentor-1511)
14. Getrennte SfM nie verformen/verkleben; neue Quellen in EINE SfM. (M:feedback-wolken-nie-verformen-gemeinsame-sfm)
15. Symmetrische Tuerme: Seitenverwechslung pruefen (Teilmodelle, `modell_zerlegen.py`, `gps_seiten_pruefen.py`), erst Register durchsuchen – kein Rueckfall. (RA 7, M:project-seitenverwechslung-symmetrie, M:project-modell-zerfall-global)
16. Verwerfen nur mit benannter Ursache (Logwarnungen lesen), Eintrag NICHTS_GEBRACHT. (M:feedback-verworfenes-neu-pruefen)

### Abnahme / Pruefung
17. Nach JEDER Generatoraenderung `tools/bauen_abnehmen.sh <objekt>`; nur bei "alle Pruefungen bestanden" weiter; Sollwerte nie lockern ohne neue Quelle + `historie`. (CL, RA 1)
18. Sichtbeobachtung = Testauftrag: `beobachtungen_offen` (datum, wer, text, naechster_schritt) -> Pruefung, die ROT ist -> dann Generator. Masstabelle vor Commit per `--nur-pruefen` pruefen. (CL, RA 2, M:feedback-masstabelle-pruefen-vor-commit, M:feedback-sichtfunde-generalisieren)
19. Neues Element: `beleg(seite, element, quelle)`; Annahmen `ANNAHME: ...`. (RA 3b)
20. Zahlen allein gelten nicht: `audit/seiten.jpg` + `audit/neben_<foto>.jpg` (je Seite >= 1 Foto) ANSEHEN, sonst nichts als passend melden. (CL, RA 3, PIPELINE_FASSADEN Pflichtkontrolle)
21. Nach Bau `fehlteile_finden.py`, `foto_diff.py`, `teile_lage_pruefen.py`; vor Zeigen/Druck Teil neben Referenzfoto. (CL, RA 3e/3f/9b/9c)
22. Fehlerliste vor Lob; nur selbst am Bild Geprueftes heisst "trifft". Realitaets-% nach jedem Ergebnis. (M:feedback-fehlerliste-vor-lob, M:feedback-realitaet-prozent)
23. Nie ein Bauteil ersatzlos abschalten (aktiv:false statt loeschen). (RA 9c, VORLAGE)
24. Nach tools-Aenderung: `tools/schnelltest.sh` (rot = erst klaeren), dann `python3 tools/regression.py modelle/<objekt>/objekt.json --pruefen`; Schnappschuss nur bei gewollter Aenderung + Register. (CL, RA 8b)
25. Nach dichter Wolke: `kamera_abdeckung.py`, `wolke_grundriss_pruefen.py` (rc 3 = nicht modellieren), `lage_gps_pruefen.py`. (CL, M:feedback-grundriss-tor)
26. Vor Langlauf jeden neuen Aufruf mit Dummy testen; pkill-Muster nie in derselben Zeile. (M:feedback-smoketest-vor-langlauf)

### Technik / Betrieb
27. Sitzungsbeginn `bash tools/hpwmi_pruefen.sh`; bei ACHTUNG KERNEL-MODUL Nutzer sofort sagen. (CL, RA, M:hpwmi-modul-pruefen)
28. Grosse Daten nie auf Root (/: 7,9 GB frei); unter /media/oem/scan/... (15 GB frei) bzw. /media/oem/rcdaten (2 TB, 1,2 TB frei), Symlinks im Repo. (CL, RA, M:reference-laufwerke-uuid)
29. Auslagern nur wirklich Kaltes (vorher `find -L ... -lname`), Platten nur nach Aushaengen; Toshiba-Familienvideos nie anfassen. (M:feedback-auslagern-nur-wirklich-kalt, M:reference-laufwerke-uuid)
30. Ohne gemountete /media/oem/scan kein git (Packs dort). (M:git-objekte-auf-datenplatte)
31. Lange Jobs nur `JOB_GPU_MB=.. JOB_RAM_MB=.. tools/job_start.sh NAME LOG BEFEHL` (Umgebung per `env VAR=..` im Befehl); nie run_in_background. (CL, RA, M:lange-jobs-systemd)
32. GPU immer: neue Werkzeuge von Anfang an GPU (`tools/gpu_knn.py`), Libs mit CUDA bauen, "Falling back to CPU" ernst nehmen, VRAM-Summe <= 7000 MiB, SIFT 1600. Maximal parallel (CPU+GPU). (CL, RA, M:feedback-gpu-bauen-immer, M:feedback-gpu-flag-pruefen, M:gpu-parallel-vram-budget, M:immer-maximal-parallel)
33. Nie zwei Optimierer/Generatorlaeufe mit gleicher Zwischendatei; Generator nicht aendern, solange Optimierer laufen. (CL, RA)
34. Kein Commit/Push ohne Auftrag; Commit-Texte mit Attribution-Zeilen; Pre-commit-Hook nur Nutzer. AUSNAHME per Nutzer: eigene masstabelle/NICHTS_GEBRACHT-Eintraege sofort committen; Agenten committen nur eigene Dateien nach Schnelltest. (CL, M:feedback-eigene-aenderungen-sofort-committen, M:feedback-agenten-integrieren-selbst)
35. Kein Slicen/Drucken ohne Nutzerwunsch; wenn gewuenscht, Druck selbst starten (Details Bambu, Wand MK4S). (M:feedback-kein-druck-vor-details, M:reference-drucker-starten, M:feedback-druck-details-bambu-wand-prusa)
36. Nie idle: Turn nicht mit "warte auf Job" beenden; nachts weiterarbeiten; vor Rueckfragen alles Unabhaengige starten. ABER: kein wiederkehrender Cron/Loop fuer Job-/GPU-Checks. (M:nie-idle-warten, M:feedback-nachts-weiterarbeiten, M:project-nachtwache-und-ssd)
37. Alles mitloggen (Logbuch je Thema+Datum nach jedem Versuch, Sackgassen in NICHTS_GEBRACHT, Skripte ins Repo). (M:feedback-alles-mitloggen, M:feedback-immer-mitloggen – Duplikat)
38. Kommunikation: Deutsch, Anrede "mein grosser Meister", keine breiten Tabellen, immer Bilder (SendUserFile) + 3D-HTML zeigen, Schnellversion nach ~20 min. (M:user-anrede-und-kantenziel, M:feedback-keine-breiten-tabellen, M:feedback-immer-bilder-zeigen, M:immer-3d-html-zeigen, M:feedback-schnellversion-zuerst)
39. Foto vor Ort hochgeladen -> sofort `tools/foto_check.sh`, Antwort PASST/PASST NICHT + eine Anweisung + Bild. (CL, M:feedback-foto-vor-ort-sofort-pruefen)
40. Fehler berichten getrennt nach "neu entdeckt" vs. "Rueckfall"; Rueckfaelle (Platz, Lib-Version) vor Langlauf ausschliessen. COLMAP: Mapper eigener Bau 4.3.dev, Rest pycolmap 4.2.1, keine Umstellung ohne A/B. (M:feedback-fehler-lernen-vs-dumm, M:project-colmap-versionen)
41. Lizenz: Verkauf geplant, NC-Werkzeuge nur Test und in LIZENZ_WERKZEUGE.md eintragen. (RA)
42. Kontext sparen: Ausgaben kuerzen (cut/head/tail), CLAUDE.md/MEMORY.md klein. (CL, M:feedback-kontext-sparen)

### VERALTET / WIDERSPRUECHLICH (ausdruecklich)
- CL "Aktueller Stand: modelle/archiv/STAND_2026-11-14.md (UEBERGABE am Ende)" und M:stand-2026-11-15 -> VERALTET. Aktuell: modelle/ZIEL_PIPELINE_H0.md (UEBERGABE 18.11. 17:40 + NACHTRAG 20.11.) -> modelle/LOGBUCH_KETTENTEST_2026-11-19.md (UEBERGABE 20.11. ~09:00). M:project-ziel-h0-von-null ist richtig, die beiden anderen widersprechen ihm.
- CL "Offene Arbeit: modelle/archiv/AUFGABENLISTE_2026-11-16.md" + M:project-aufgabenliste-1611: groesstenteils ERLEDIGT (1a,1c,1e,2,3,5); offen nur 1b,1d,4,6 – in ZIEL_PIPELINE_H0 aufgehen lassen, nicht mehr als Sitzungsstart-Pflicht.
- RA 9d(b) "param_wolke_fit.py --fotos ... Status: noch NICHT gebaut" -> VERALTET: `tools/param_wolke_fit.py` hat `--fotos` (Zeile 17).
- RA 9c(d) Status-Satz (GPU-Sweep, FFT offen) = Stand 8.11., Arbeitsnotiz, keine Regel.
- RA "Vor neuen Versuchen lesen": LERNJOURNAL_MARTINSTOR, PIPELINE_H0 (Stand 31.10.), PROTOKOLL_VALIDATOR – alt (Oktober), nicht mehr Pflichtlektuere.
- RA Technik "nullstart.py ... --ziel martinstor_null als Wiederholbarkeitstest" -> ersetzt durch `tools/gesamtkette.py` (ZIEL_PIPELINE_H0 Abnahmekriterium 1).
- REZEPT "Neues Gebaeude in Schritten" nutzt `tools/gitter_kette.sh` (existiert) – durch `tools/gesamtkette.py` abgeloest.
- VORLAGE_BAUTEIL_RUNDE Formfamilie aus `tools/baukasten_gen.py` (existiert) – widerspricht teilweise Regel 3/11 (Gestalt aus Wandbild, Katalog jetzt `tools/bauteile.py`). Vorlage sagt ausserdem "ZUERST LESEN CLAUDE.md (Regeln 2, 3b ...)" – Regelnummern stehen nur noch in REGELN_AUSFUEHRLICH.md.
- M:kreis-merge-nutzer-fragen "keine Agenten selbst starten" vs. M:feedback-agenten-integrieren-selbst (17.11., Worktrees, Agenten integrieren selbst) und CL "Agentenauftrag aus VORLAGE": Widerspruch; neuere Regel (17.11.) gilt offenbar fuer Agenten-Runden, alte nur fuer den Kreis (`bauteil_kreis.py`). Nutzer klaeren lassen.
- M:feedback-realitaet-prozent: Zahl = Mittel Wolkenbeleg (`tools/realitaet_prozent.py`) – widerspricht Kernmethode (Wolke nur Veto); Foto-F1 als Hauptzahl vorschlagen.
- M:feedback-immer-mitloggen (`LOGBUCH_<datum>.md`) vs M:feedback-alles-mitloggen (`LOGBUCH_<thema>_<datum>.md`) – Duplikat, zusammenlegen.
- M:project-uebersehene-punkte-1511 "Warteschlange rcpark-warteschlange / warteschlange.sh" -> FEHLT (kein tools/warteschlange*); Eintrag veraltet.
- M:feedback-schnellversion-zuerst nennt `/media/oem/scan/rc-park_tmp/abend/var.sh` -> FEHLT.
- LOGBUCH_KETTENTEST UEBERGABE nennt `tools/versuche/stufe2_nach_kette.sh` -> FEHLT (nicht im Repo; tools/versuche hat nur flexglue_*.sh/py).
- PIPELINE_FASSADEN nennt `tools/wand_feinausrichten` -> heisst `tools/wand_feinausrichtung.py`.
- M:feedback-fehler-lernen-vs-dumm nennt "platz_pruefen" -> existiert nur als `tools/platz_pruefen.py` (kein .sh).
- M:disk-space-windows-volume (Stand 30.10., englisch) – ohne rcdaten-2-TB-Platte; ueberholt durch M:reference-laufwerke-uuid.
- RA "GPU-Sperre/nur ein GPU-Job" nur noch Altverhalten ohne JOB_GPU_MB – ok, aber CL soll nur VRAM-Budget nennen.
- GLOBALER_MAPPER_STABIL: Kette reicht `--mapper konsens` nicht durch (offen, pipeline_objekt.py:142) – Stand pruefen, bevor Regel "konsens = Standard" in CLAUDE.md kommt.
- Python fuer COLMAP-Werkzeuge `/media/oem/scan/venv-colmap/bin/python -I` fehlt in CL (nur venv-seg + rcpark genannt).

## 2. Vorschlag neue CLAUDE.md (<= 60 Zeilen)

```
# RC-Park – Arbeitsregeln (Kurzfassung)
Fotos -> SfM (COLMAP) -> 3D -> druckbares H0-Modell (1:87). Sprache Deutsch, Anrede "mein grosser Meister".
Stand/Uebergabe zuerst: `modelle/ZIEL_PIPELINE_H0.md` (UEBERGABE/NACHTRAG am Ende) -> dort verlinktes Logbuch (UEBERGABE am Ende).
Volltext der Regeln: `modelle/REGELN_AUSFUEHRLICH.md` (gezielt per grep lesen).

## KERNMETHODE (nie vergessen)
- Form = Fotokanten + Triangulation (Kanten-Tiefen-Sweep mit SfM-Kameras). SfM liefert die KAMERAS. Wolke/LoD2/DOM1 nur Lage-Veto, Hoehe, Gegenprobe.
- WANDBILD = BAUPLAN: Wand entzerrt (`tools/fassade_fein.py`) + Tiefe je Zelle -> Gestalt nachbilden. Erkennen = nur Zone/Loch. Keine Musterteile; Katalog nur Freistehendes.
- Jede Kette: Kantenstufe + Foto-F1 (`tools/teil_fotoform.py`) + `tools/foto_diff.py` als Tor.
- Formfamilie aus >= 3 Fotos vor jeder Messung; nie per Kennzahl-Sweep. Zaehlen nur am Foto (`foto_zaehlung.py`), Masse nur `foto_mass.py`.
- Quellen nicht mitteln; Lage unabhaengig belegen (GPS, DOM1-Hoehe, Massstab). Neue Objekte: Fotos -> SfM -> LoD2 nur Abgleich.
- Ungesehene Wand nie spiegeln/erfinden -> Fotos suchen. Neue Bauteile nur generisch in `tools/bauteile.py`.
- Verwerfen nur mit benannter Ursache (`modelle/NICHTS_GEBRACHT.md`). Symmetrische Tuerme: Seitenverwechslung pruefen.

## Abnahme (Pflicht, Details per Skill)
- Generatoraenderung -> Skill `abnahme` (`tools/bauen_abnehmen.sh <objekt>`, nur bei "alle Pruefungen bestanden" weiter; Sollwerte nie lockern).
- tools-Aenderung -> Skill `tools-pruefen` (`tools/schnelltest.sh`, dann `tools/regression.py ... --pruefen`).
- Nach dichter Wolke -> Skill `wolke-tore` (Abdeckung, Grundriss, GPS).
- Sichtbeobachtung = erst `beobachtungen_offen` (datum, wer, text, naechster_schritt), Pruefung rot, dann Generator.
- Zahlen allein gelten nicht: `audit/seiten.jpg` + `audit/neben_*.jpg` ansehen. Fehlerliste vor Lob, Realitaets-% melden.
- Nie ein Bauteil ersatzlos abschalten. Neues Element `beleg(...)`, Annahmen `ANNAHME: ...`.

## Technik
- Sitzungsbeginn: `bash tools/hpwmi_pruefen.sh` (ACHTUNG KERNEL-MODUL -> Nutzer sofort sagen).
- Grosse Daten nie auf Root: `/media/oem/scan/...` bzw. `/media/oem/rcdaten`, Symlinks. Ohne /media/oem/scan kein git.
- Python: `/media/oem/scan/venv-seg/bin/python -I` (torch/CUDA), `/media/oem/scan/venv-colmap/bin/python -I` (pycolmap 4.2.1), Generator `~/.venvs/rcpark`.
- Lange Jobs nur per Skill `langer-job` (`tools/job_start.sh`, JOB_GPU_MB/JOB_RAM_MB); nie run_in_background; vorher Dummy-Test.
- GPU immer (neue Werkzeuge `tools/gpu_knn.py`, Libs mit CUDA, "Falling back to CPU" = Fehler); maximal parallel, VRAM-Summe <= 7000 MiB.
- Nie zwei Optimierer/Generatorlaeufe mit gleicher Zwischendatei parallel.
- Kein Commit/Push ohne Auftrag (Ausnahme: eigene masstabelle/NICHTS_GEBRACHT-Eintraege sofort). Attribution-Zeilen. Hook nur Nutzer.
- Kein Slicen/Drucken ohne Nutzerwunsch; dann Skill `druck`.
- Nie idle, nachts weiterarbeiten; aber KEIN wiederkehrender Cron/Loop fuer Job-/GPU-Checks.
- Kontext sparen: Ausgaben kuerzen (cut/head/tail). Keine breiten Tabellen; Bilder (SendUserFile) + 3D-HTML zeigen.

## Bei Aufgabe X lies Y / Skill
- Foto vom Nutzer vor Ort -> Skill `foto-vor-ort`.
- Neues Objekt von null -> Skill `objekt-von-null` (`tools/gesamtkette.py`, `modelle/ZIEL_PIPELINE_H0.md`).
- Bauteil neu/falsch -> Skill `bauteil-runde` (`modelle/VORLAGE_BAUTEIL_RUNDE.md`).
- Fassaden/Fenster/Relief -> Skill `fassaden` (`modelle/PIPELINE_FASSADEN.md`).
- Linienhafte Features -> Skill `linien-features`.
- SfM/Mapper -> `modelle/GLOBALER_MAPPER_STABIL.md`, Versionen: Mapper 4.3.dev-Bau, Rest pycolmap 4.2.1.
- Vor neuen Versuchen: `modelle/NICHTS_GEBRACHT.md`, `modelle/VERSUCHSREGISTER_MARTINSTOR.md`, `modelle/LIZENZ_WERKZEUGE.md` (NC nur Test).
- Lehren eintragen: `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md` (Lehren-Register); Logbuch -> Skill `logbuch-commit`.
- Platten/Auslagern -> Memory reference-laufwerke-uuid (Toshiba nie anfassen).
```
(~55 Zeilen)

## 3. Wiederkehrende ABLAEUFE (Skill-Kandidaten) – alle Pfade per ls vorhanden, sofern nicht FEHLT

A. `abnahme` – Ausloeser: jede Generatoraenderung / objekt.json / masstabelle.
 1. `tools/bauen_abnehmen.sh <objekt>` (oder `--nur-pruefen` nach masstabelle-Edit); laeuft Generator, `tools/pruefstand.py`, `tools/seiten_audit.py`, `tools/modell_neben_foto.py` (objekt.json `neben_fotos`), `tools/test_regeln_cb.py`.
 2. Nur weiter bei "alle Pruefungen bestanden".
 3. `tools/fehlteile_finden.py <objekt> <foto>`, `tools/foto_diff.py <objekt> <foto>`, `tools/teile_lage_pruefen.py <objekt>`.
 4. Ansehen: `modelle/<objekt>/audit/seiten.jpg`, `audit/neben_*.jpg`, `audit/foto_diff_*.jpg` (Read-Tool), Fehlerliste je Teil.
 5. `tools/realitaet_prozent.py <objekt>` -> %-Zahl mit Differenz melden; Bild per SendUserFile; 3D-HTML.
 Auf main nach Kreis-Merge: `tools/job_start.sh abnahme_main LOG bash tools/main_abnahme.sh <objekt> "<Text>"`.
 Doku: RA Abschnitt Modell-Abnahme, modelle/METHODE_MASSTABELLE.md.

B. `tools-pruefen` – Ausloeser: jede Aenderung unter tools/.
 1. `bash tools/schnelltest.sh` (~30 s; rot = klaeren, Erwartung nur mit Grund aendern).
 2. `python3 tools/regression.py modelle/<objekt>/objekt.json --pruefen` (Schnappschuss `--schnappschuss` nur bei gewollter Aenderung + Register).
 3. Bei Rechenwerkzeug: GPU-Nutzung pruefen (nvidia-smi > 0, `tools/gpu_knn.py`), Eintrag `tools/gpu_budget.txt`.
 Doku: RA 8b, AUFGABENLISTE Punkt 5.

C. `foto-vor-ort` – Ausloeser: Nutzer laedt Foto hoch (~/.claude/uploads/...).
 1. `tools/foto_check.sh <objekt> <datei> [auftrag-nr]` (braucht `modelle/<objekt>/audit/fotoauftrag.json` aus `tools/foto_auftrag.py`; Wunschliste `modelle/<objekt>/fotowuensche.json`).
 2. Antwort 2-4 Zeilen: PASST fuer Auftrag N / PASST NICHT + genau eine Anweisung; Bild check_<name>.jpg per SendUserFile zurueck.
 Fotobedarf zeigen: `tools/foto_auftrag.py`. Doku: PIPELINE_FASSADEN "Fotoauftrag" + "Sofort-Urteil".

D. `langer-job` – Ausloeser: alles > ein paar Minuten (SfM, Kette, Fusion, Optimierer).
 1. Platz pruefen (`df -h`, `tools/platz_pruefen.py`), Versionen pruefen (COLMAP).
 2. Dummy-Test jedes neuen Aufrufs.
 3. `JOB_GPU_MB=<MiB> JOB_RAM_MB=<MiB> tools/job_start.sh NAME LOG env VAR=.. BEFEHL...` (grosse Jobs RAM 11000; Budget aus `tools/gpu_budget.txt`).
 4. Status `systemctl --user status rcpark-NAME`, Ende `JOB_ENDE rc=` im Log (Monitor/until-Schleife, kein Cron). Fehler sofort beheben + neu starten.
 Doku: RA Technik, modelle/GPU_PARALLEL_UNTERSUCHUNG.md.

E. `objekt-von-null` – Ausloeser: neues Gebaeude / Kettentest.
 1. `/media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py <quelle_objekt> --ziel <name> [--ab/--bis stufe] [--fremd ORDNER] [--commons-kategorie ...]` per langer-job. Stufen: anlegen, commons, video, vorpruefen, sammeln, sfm, tore, dach, bauen, kanten, fototor, fassaden, fenster, bauplan, seiten, html, vergleich, druck.
 2. Nach dichter Wolke Skill wolke-tore; Zerfall/Seiten: `tools/modell_zerlegen.py`, `tools/gps_seiten_pruefen.py`, `tools/kette_insel_pruefen.py`.
 3. Kettenende: tor_zerfall, Konsens fremde_seite.txt, audit/seiten.jpg + neben_*.jpg, Realitaets-%.
 4. Versuch V* in ZIEL_PIPELINE_H0.md eintragen.
 Manuell alt: `tools/objekt_anlegen.py`. Mapper-Rezept: `tools/global_mapper_konsens.py` bzw. `tools/iphone_sfm.py --mapper konsens` (Kette reicht das noch nicht durch). Doku: ZIEL_PIPELINE_H0.md, GLOBALER_MAPPER_STABIL.md, REZEPT Abschnitt "Neues Gebaeude".

F. `wolke-tore` – Ausloeser: nach jeder dichten Wolke.
 `tools/kamera_abdeckung.py <sparse>` (Luecke > 90 Grad), `tools/wolke_grundriss_pruefen.py <objekt.json> --wolke <npy>` (rc 3 = nicht modellieren), `tools/lage_gps_pruefen.py <objekt.json> <SFM-AUSRICHTUNG.json>`, `tools/hoehe_gegen_dom1.py`, `tools/gruppen_punkt_tor.py`, `tools/sfm_draufsicht.py`, `tools/mapper_bewerten.py`. Doku: M:feedback-lehren-schwabentor-1511 (Reihenfolge), M:feedback-grundriss-tor.

G. `bauteil-runde` – Ausloeser: Bauteil neu/falsch (Nutzerfund).
 1. Befund in masstabelle `beobachtungen_offen`.
 2. Auftrag aus `modelle/VORLAGE_BAUTEIL_RUNDE.md` (Platzhalter, TABU), Agent mit `isolation: worktree`; Stufen 0 Form (`tools/bauteil_sichtliste.py`, `tools/kamera_bruecke.py`), 1 Zaehlen (`foto_zaehlung.py`), 2 Messen (`foto_mass.py --tri`, METHODE_MESSEN_DANN_BAUEN.md), 3 rote Pruefung, 4 Generator (`tools/bauteile.py`), 5 Abnahme.
 3. Integration: Schnelltest auf main, nur eigene Dateien committen; Lehre ins REZEPT-Register.
 Kreis-Variante: `tools/bauteil_kreis.py --nach_main` (systemd). Doku: VORLAGE, REZEPT.

H. `fassaden` – Ausloeser: Fassade/Fenster/Relief/leere Wand.
 `tools/fassade_fein.py` -> `tools/tiefe_lokal.py` / `tools/relief_aus_fotos_mono.py` -> `tools/form_aus_wandbild.py`; regelmaessig `tools/bauteile.py` + `tools/wand_ortho.py` + `foto_mass.py`; Bruchstein `tools/relief_einsatz.py` -> `tools/relief_putz.py` -> `tools/steine_generieren.py`; glatt `tools/relief_quader_eben.py`; Fugen `tools/steine_aus_foto.py`; Fenster-Loecher `bauteile.aushoehlen` (WAND_MM 1,2); leere Wand `tools/seiten_luecken.py ... --download --holen` -> `tools/fassade_ein_foto.py ... auto --stl`; Feinausrichtung `tools/wand_feinausrichtung.py`; Nutzerbild nachrendern `tools/modell_ansicht.py`. Kette: `tools/fassaden_kette.py`. Doku: PIPELINE_FASSADEN.md.

I. `linien-features` – Ausloeser: Rippen, Baender, Leisten, Staebe.
 `tools/kanten_tiefe_sweep_flaeche.py --flaeche STL --band` -> `tools/kanten_features.py --farbe stabil --sweep SWEEP.npz --nur_ref [--maske]` -> `tools/features_in_objekt.py` -> Abnahme + Render neben Foto; Druck-Teilnetze `druck.splitter_verwerfen`. Doku: RA Abschnitt Linienhaft, LOGBUCH_RIPPEN_2026-11-13.md.

J. `druck` – Ausloeser: nur ausdruecklicher Nutzerwunsch.
 Bausatz `tools/bausatz.sh` / `tools/druck_teilung.py`; Bambu: `python3 tools/bambu_slice.py <aus.gcode.3mf> <teil.stl> --schicht 0.16 --brim 0`, `~/.venvs/strom/bin/python tools/p1s_print.py status|print`; Prusa MK4S: `python3 tools/prusa_slice.py <stl> --out <ordner> --printer "Original Prusa MK4 Input Shaper 0.8 nozzle" --print "0.40mm QUALITY @MK4IS 0.8"`, `python3 tools/prusa_print.py print <gcode> <name>` (Zugang ~/.config/rcpark/prusalink.json). Vorher Teil neben Foto (RA 9b). Details Bambu (Klips), Wand MK4S (Rippen, Rahmen, Brim). Doku: M:reference-drucker-starten, PIPELINE_FASSADEN "Bausatz".

K. `logbuch-commit` – Ausloeser: nach jedem Versuch / Ende einer Arbeitseinheit.
 Logbuchzeile in `modelle/LOGBUCH_<thema>_<datum>.md` sofort (Was/Ergebnis/Beleg/Folge), Sackgasse mit Ursache in NICHTS_GEBRACHT.md, Lehre ins REZEPT-Register, Versuch in ZIEL_PIPELINE_H0.md; vor Commit `tools/bauen_abnehmen.sh <obj> --nur-pruefen` bei masstabelle-Edit; Commit nur eigene Dateien, Attribution; Uebergabe-Abschnitt am Ende des Logbuchs vor /clear.

L. `sitzungsbeginn` – Ausloeser: neue Sitzung / nach /clear.
 `bash tools/hpwmi_pruefen.sh`; `systemctl --user list-units 'rcpark-*' --no-legend | cut -c1-80`; `df -h /media/oem/scan /media/oem/rcdaten /`; UEBERGABE in ZIEL_PIPELINE_H0.md + Logbuch lesen.

M. (optional) `platte-umzug` – Auslagern/Umzug: `tools/auslagern.sh`, `tools/umzug_auslagerung.sh [--nur_umbiegen]`, `tools/git_packs_auslagern.sh --packen`; vorher `find -L ... -lname`. Doku: M:reference-laufwerke-uuid, ZIEL_PIPELINE_H0 UEBERGABE 18.11.

## 4. Veraltete/redundante MD-Dateien (Kandidaten modelle/archiv/ – NICHTS verschoben; modelle/archiv existiert noch nicht)
Spalte "Ref" = Anzahl anderer Dateien (tools/, CLAUDE.md, modelle/*.md), die den Namen nennen; vor Verschieben Verweise umbiegen.
- STAND_* (2026-11-05, -06, KURZ-06, -08_LEAVEOUT, -08_LOT_SWEEP_LOOP, -08_PARAMETER, -09_ABEND, -10_MORGEN, -10_NACHMITTAG, -12_VORMITTAG, -12_VORMITTAG_lang, -14): Tagesstaende, abgeloest durch ZIEL_PIPELINE_H0 + Logbuecher. STAND_2026-11-06 hat 12 Ref, STAND_2026-11-14 3 Ref (CLAUDE.md!) – Verweise anpassen. STAND_2026-11-10_NACHMITTAG und -12_VORMITTAG_lang sind nicht einmal in git.
- UEBERGABE_2026-11-03 (+_mittag, _abend, _nacht), UEBERGABE_2026-11-04: alte Uebergaben.
- LOGBUCH_*_R*_2026-11-10 (13 Rundenlogbuecher Fenster/Gauben/Giebel/Helm/Figuren/Erker), LOG_*_2026-11-09 (9 Dateien), LOGBUCH_2026-11-08/-09, LOG_2026-11-05_FEHLER_UND_STAND: abgeschlossene Runden (fast alle 0-2 Ref).
- RECHERCHE_* vom 6.-9.11. (ca. 17 Dateien): Literatur-Recherchen, Ergebnis eingeflossen; behalten nur RECHERCHE_VERBESSERUNGEN_2026-11-19 / _RUNDE_ELEMENTE_2026-11-18 / _VERBESSERUNG_2026-11-17 (aktuell).
- SPEC_S1b..S10, SPEC_* (11.11.): Spezifikationen der Kreis-Tore; gebaut oder verworfen – pruefen, ob tools noch darauf verweisen (SPEC_LOKALES_FOTOTOR 6 Ref, SPEC_FEINSUCHE/FORMFUND/ORNAMENT 5 Ref) -> eher behalten oder Ref umbiegen.
- Plaene/Strategie Oktober/frueh: DATA_STRATEGY, FINANZMODELL_FREIBURG, MASTERPLAN_MINIATURWUNDERLAND, QUICK_START_FREIBURG, FREIBURG_STRATEGIE, NACHT_BERICHT_schwarzwald, schwarzwald_kandidaten, FLUGPLAN_LINACHTALSPERRE, FERTIGUNG_SPLIT, FINISH_STEINGEBAEUDE (0-2 Ref, 30./31.10.) – Geschaeftsideen, nicht Arbeitsregeln (Nutzer fragen, ob Archiv).
- METHODE_*/METHODIK_* (30.10.-2.11.): METHODE_3D_AUS_ALLEN_DATEN, _AUTO_PIPELINE, _BAUWERK_AUS_DATEN, _GEBAEUDE_3D, _GEBAEUDEGENERATOR, _WAHRZEICHEN_AUS_FOTOS, _WUNSCH_ZU_MODELL, _SCAN_ZU_H0, _FOTO_AUFNAHME, METHODIK_KOMPLETT, ROADMAP_PIPELINE_ALLGEMEIN, PIPELINE_H0, PIPELINE_KOMPLETT_2026-11-07, PIPELINE_HYBRID_WOLKE_KANTEN, PIPELINE_LERNREGISTER: alles vor der Kernmethode (Wolke als Basis), widerspricht teils KERNMETHODE; ersetzt durch ZIEL_PIPELINE_H0 + PIPELINE_FASSADEN + REZEPT. Behalten: METHODE_MASSTABELLE (6 Ref, Pflichtrahmen), METHODE_MESSEN_DANN_BAUEN (VORLAGE), METHODE_GPU_SWEEP (RA), METHODIK_KANTEN_STABILITAET (Kernmethode-Grundlage, pruefen).
- Plaene 3.-9.11.: PLAN_2026-11-06_H0_DETAIL, PLAN_DETAILGETREUE, PLAN_KANTENGITTER_H0_2026-11-09, PLAN_LEAVEOUT_2026-11-08, PLAN_VERBESSERUNG, AUFTRAG_2026-11-06_TEILE, AUFWAND_BEWERTUNG_2026-11-03, BEWEIS_ANSATZ_2026-11-06, BEWERTUNG/LAGEBILD_KANTENGITTER_2026-11-09, SPEZIALCODE_AUDIT_2026-11-03, NULLSTART_GENERALITAET, LEHREN_2026-11-08_SWEEP_UND_FOTOLOOP (Lehren -> REZEPT-Register), ERKLAERUNG_*.
- LEITFADEN_NEUES_MODELL (13.11., 0 Ref): Zusammenfassung aller MDs vor Wandbild-Durchbruch – redundant zu REZEPT/ZIEL_PIPELINE_H0.
- AUFGABENLISTE_2026-11-16: fast erledigt, Restpunkte nach ZIEL_PIPELINE_H0 uebertragen, dann Archiv (CLAUDE.md-Verweis entfernen).
- GPU_LUECKEN_2026-11-08 (0 Ref, aber M:feedback-leerlauf-gpu-ports verweist) – Stand pruefen.
- Behalten (aktiv): REGELN_AUSFUEHRLICH, ZIEL_PIPELINE_H0, PIPELINE_FASSADEN, REZEPT_GEBAEUDE_AUS_FOTOS, GLOBALER_MAPPER_STABIL, VORLAGE_BAUTEIL_RUNDE, LIZENZ_WERKZEUGE (52 Ref), NICHTS_GEBRACHT (34 Ref), VERSUCHSREGISTER_MARTINSTOR, LOGBUCH_KETTENTEST_2026-11-19, LIB_UPDATES_2026-11-19, QUELLEN_REGISTER, MASSSTAB (12 Ref), CPU_LEISTUNG, GPU_PARALLEL_UNTERSUCHUNG, TOSHIBA_INVENTAR, BELEUCHTUNG/ANLEITUNG_FOTOS_NUBIA/AUFNAHME* (Fotoanleitung, pruefen), WERKZEUGKETTE_WUNDERLAND (17.11.).
- Memory: viele stand-*/lektionen-*/uebergabe-* Dateien (Okt./Anfang Nov.) im memory-Ordner sind nicht im Index – nur archiv_index; M:stand-2026-11-15 + M:project-aufgabenliste-1611 + M:project-uebersehene-punkte-1511 aus MEMORY.md nehmen; M:feedback-immer-mitloggen in feedback-alles-mitloggen aufgehen lassen; M:disk-space-windows-volume durch reference-laufwerke-uuid ersetzen.

# Übergabe 23.11.2026 14:25
Weiter mit: „weiter" (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`.

## Auftrag
- Nutzer (seit 22.11.): „Keine Handangriffe, nur Automatik." · „Ich will die Südseite" (Feldseite f01, im Objekt „Sued", -x) · „parallel".
- „Die Methode muss vollautomatisiert so robust sein, dass sie auch mit dünnen Brücken umgehen kann … vollautomatisch merkt, wo es schwach wird …"
- Heute: „Vollgas", „Verbessere die Pipeline", „Beheben die Lücke" (nachgeholte Kameras im selben Lauf), „Ja, du darfst löschen".
- Ziel: Kette baut Schwabentor von null inkl. Südseite, Lage-Tore grün, Bild + Fehlerliste + Realitäts-% an Nutzer. Arbeitsweise Skill `kette-schleife`.

## Erledigt und geprüft (main c0586132f, gepusht)
- Läufe: 1122q (05:00-10:09) ~25 %, Süd flach (Teil 1 abgetrennt). 1122r (10:39-12:37): Süd im SfM VEREINT (524 Bilder), lage_frueh -0,4 Grad x0,980, aber 3 Abstürze -> Süd/Ost flach, ~25 %. 3D V4 https://claude.ai/artifact/ScV8KGvyjJrxxHCAzCM6pi (1122q).
- In main, je voller Schnelltest 0 Fehler:
  - Probe 17: Uhr-Beleg (Heiligenschein), HTML-Zielgröße <= 14 MB, Laterne 1.
  - Probe 18: Laterne 4 Pfosten; Nachhol-Tor + Wiederholung im selben Lauf (tools/seiten_wiederholung.py, kameras_nachtragen_tor.py); Südbrücke (seiten_erkennen --durchblick-getrennt Standard, Fernsicht-Gruppe < 12 Bilder behalten).
  - Probe 19: kamera_verfeinern Stapel (--liste), LG-Zwischenspeicher (tools/lg_zwischenspeicher.py), Drossel-Marke (http_holen), Schalter RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT (AUS, Messskript tools/versuche/nachhol_sift_gewaehlt_messen.py), Tordurchfahrt aus Wandbild (form_offen, Stufe bauplan_oeffnungen_durchfahrt), neben_details Ecken-im-Kasten (Uhr-Keile waren Prüfbildfehler), Zwiebelhaube als Sehstrahl-Hülle.
  - Probe 20: tools/kamera_standort.py (231/625 K-Dateien ohne standort_xyz -> fassaden_kette-Absturz), SVD full_matrices=False (wand_dicke 119 GiB), Kamera-ID-Kollision beim Vereinen (colmap_rig_abgleich fremde_kameras, sfm_seiten_modelle belegt=).
- Gelöscht (Nutzer-Ja): /dev/shm/rcpark_netz_*, nachholen_agent, bruecke2/k1122, Worktree ac64; gemergte Worktrees entfernt.

## Läuft gerade
- Kette `rcpark-kette-schwabentor-null-1122s` (Start 13:30, --ab vorpruefen, JOB_RAM_MB 11000, JOB_GPU_MB 6000). Log job_logs/kette-schwabentor-null-1122s.log. Prüfen: `grep -a "ERGEBNIS DES LAUFS\|JOB_ENDE" <log> | tail -2`. Stand 14:22 neu_fusionieren. BEFUND: Süd NICHT vereint („Brueckenkopplung NICHT uebernommen: keine stimmige Kopplung", Teil 1 125 statt 129 Bilder) -> Süd wieder flach erwartet; lage_frueh -0,8 Grad x0,976. Prüft trotzdem Absturz-Fixes, Nachholen, Tordurchfahrt, Laterne.
- Agenten (Worktrees .claude/worktrees/agent-<id>, nur Code, rechnen nicht während Kette):
  - a8ff298c: Süd-Kopplung kippelt 1122r (vereint) vs 1122s (abgelehnt) – deterministisch machen.
  - a78d2a39: K-Dateien im alten Rahmen (87 verfeinert + 231 nachgetragen stimmen auf Süd nur 0-2 % mit Bündelkameras; kameras_aus_buendel überschreibt „handkalibriert" nie) – beweisen, Rahmen-Stempel, umrechnen/sperren.
  - a150750e: Treppentürmchen (Zylinder ohne Dach) – Drehkörper-Bausteine der Laterne generisch herausziehen; merged a195.
- Fertig, ungemergt: Zweig worktree-agent-adff173fcb612ec6b cca6a232a (steine_aus_foto: max 4 Fotos je Standort unter 12 Kandidaten; w07 162 Steine, w05 Quader-Tor ehrlich rot).

## Nächste Schritte
1. Bei JOB_ENDE 1122s: auswerten (seiten.jpg, neben_*.jpg, neben_details.jpg ansehen), Fehlerliste + Realitäts-% + SendUserFile, 3D-Artifact gleiche URL (HTML liegt unter /media/oem/scan/rc-park_daten/schwabentor-1122/schwabentor-1122_3d.html), Logbuchzeile.
2. Merge-Probe 21 = main + adff173f + fertige Agentenzweige (Kopplung, Rahmen, Türmchen); voller Schnelltest; bei 0 -> main, baum_erzeugen, push; Worktrees sauber entfernen.
3. Nach der Kette: Messung SIFT-nur-gewählt (Befehl im Messskript-Kopf, JOB_GPU_MB=3000 JOB_RAM_MB=12000); bei „kein Verlust" Schalter Standard.
4. Kettenlauf 1122t starten (gleicher Befehl wie 1122s).
5. Offene Befunde: Fachwerk-Anbau nicht gebaut (Rundbogen links), Tor 0,5 m zu breit (keine Innenkante), Laterne Krempe zu klein/Glocke fehlt, Uhr-Tiefe ANNAHME, Vordach gerade statt geschweift, Fenster f03, Südwand-Genauigkeit braucht Fotos (audit/foto_auftrag.png).

## Entscheidungen des Nutzers
- ✓ Löschen der genannten Altdaten (erledigt).
- ? Root 7,7 GB frei (< 15 GB): weitere Kandidaten erst nennen, nur nach „Ja" löschen. /media/oem/rcdaten/tmp/nachhol_vereint_agent (2,4 GB), absturz_agent, fotosteine_agent, laterne_agent* liegen auf rcdaten.
- ? Regelungs-Zweig a7cb464f361175467 nur mit Zustimmung. ? YouTube-Cookies nur nach „Cookies ja".
- ? Fotos vor Ort (Übereck-Bogen Süd/West, Frontalreihe Süd, Laterne von Ost/West) – Nutzer entscheidet.

## Fehler und Lehren dieser Sitzung
- 1122p baute Süd nur zufällig (vorpruefen-Absturz -> ungeteilte DB); Erfolg ohne Ursache nie als Fortschritt melden. Logbuch 23.11.
- Mehr Daten legen ungetestete Pfade frei (vereintes Modell -> 3 Abstürze). Neue Datenlage = Einzelstufen auf Kopie vor Kettenlauf prüfen.
- Detailbild kann lügen (Uhr-Keile = Fremddreiecke im Prüfbild); vor Bauteil-Befund Prüfbild-Auswahl prüfen.
- Eigene Laufzeit-Schätzung 4 h war ohne Messung; Zeiten aus Log-Stempeln ablesen.
- tools/py wählt für manche Tests falsches venv (numpy-Importfehler) – Schnelltest-Interpreter nehmen.
- Kippeln Süd-Kopplung zwischen Läufen = offen (Agent a8ff).

## Wichtige Pfade und Befehle
- Kettenstart: `JOB_RAM_MB=11000 JOB_GPU_MB=6000 tools/job_start.sh kette-schwabentor-null-<x> /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-<x>.log /usr/bin/env RCPARK_LAGE_FRUEH=hinweis /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1122 --ab vorpruefen --dicht-stufe schnell`
- Logbuch: modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md. Fotoauftrag: modelle/schwabentor-1122/audit/foto_auftrag.png/.md.

## Vorsicht
- Nur EIN Kettenlauf; Agenten rechnen nicht während der Kette. Merge nur bei Schnelltest 0.
- Fremde uncommittete Dateien nie committen (kaufhaus_grob3, martinstor_gk, *MASSNACHWEIS.md, schwabentor-1120/audit …); `git commit -a` ist per Hook gesperrt.
- Worktrees nicht anfassen: ram-je-stufe-1120 (a1b1), a7cb (Regelung), a4468, ae54 (untracked .cache_lod2), merge_probe11/14, flaechen/wt. Nie --force. Toshiba nie.

# Übergabe 25.11.2026 02:00
Weiter mit: „weiter" (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`.

## Auftrag (Nutzerworte)
- HAUPTZIEL (24.11.): „Das ist extrem wichtig ... davon hängt mein Projekt ab." Kette baut das Schwabentor automatisch mindestens so gut wie das Handmodell schwab_v3, dann generalisiert (zweites Objekt). Plan: `modelle/PLAN_HANDMODELL_IN_KETTE.md`.
- „Alle Maße müssen aus Fotos kommen." Bausteine nur mit gemessenen Maßen; fehlt eins: erst mehr Fotos, dann ANNAHME mit Herleitung; nie feste Zahlen.
- HART „sichere das hart ab!": nie schlechter als der beste Stand. Nach jedem Kettenlauf ZUERST `audit/neben_*.jpg` neben `modelle/<obj>/bestand/` (und ZIEL_*) legen, beide schicken, erst dann Zahlen. Rückschritt nie mergen.
- „Keine Handangriffe, nur Automatik." Deutsch, „mein grosser Meister", keine breiten Tabellen.
- Nutzer fragte zuletzt, ob das Kettenergebnis „demnächst nah an den Handlauf kommt" -> ehrliche Antwort: erster Lauf grob 7-9 von 11 (Schätzung), nah dran eher 2-4 Runden à ~4 h; Abbruchregel P7 (2 Läufe ohne Anstieg = Methode wechseln).

## Stand 25.11. 02:00
- main = 5c316a1b3 auf GitHub: Probe 31 gemergt (Bestand-Tor, Hand-Vergleich mit Höhenbezug, Linien-/Rund-/Nischen-Bausteine, Konvergenz-Messfehler, SIFT-Paarspeicher, Wissenswerkzeuge) + Wissenssuche-Agent. Probelauf rc 0 (Stand 5377c66d0), merge_sperre 0, Schnelltest 0 Fehler.
- Wissenssuche am versiegelten Satz: neu 4/40 @5, alt 0/40 (nicht „gelöst"; 8 echte Fehlsuchen neu_24abend 0/8). Wissens-INDEX fehlt in main: einmal `CUDA_VISIBLE_DEVICES= /media/oem/scan/venv-seg/bin/python -I tools/wissen_bedeutung.py --bauen` (~20 min CPU, NICHT parallel zur Kette). Offen: bei 1-2-Wort-Anfragen Bedeutungssuche geringer gewichten.
- Läuft: Job `bestand-anlegen-1122b` (Bestand-Tor-Grundlage für schwabentor-1122 aus STL `/media/oem/rcdaten/tmp/bau_parallel_agent/modelle/stl/schwabentor-1122_1-87.stl`, Log /media/oem/scan/rc-park_daten/job_logs/bestand-anlegen-1122b.log, Ende `JOB_ENDE`). Dauer > 1 h (24 Zonen, viele Fotos). OHNE Bestand würde die Kette den ersten Stand selbst als Bestand anlegen -> erst abwarten.
- DANACH: echte Kette `tools/job_start.sh kette-schwabentor-null-1122zd ... tools/gesamtkette.py` (Aufruf wie 1122zc im Log kette-schwabentor-null-1122zc.log nachsehen), dann kette-schleife Schritt 2: Bestand-Vergleich Bilder (neben_*.jpg gegen Bestand + ZIEL), beide dem Nutzer schicken, Handvergleich „x von 11" (Ausgangslage 5/11 bezugsbereinigt; 1120 = 11/11), Fehlerliste, Realitäts-%.

## Offene Befunde (ohne Agent)
- Galerie-Baustein: feste Querschnitte (Pfosten 0,22, Rähm 0,25, Knagge 0,12) und MIT_KATALOG_GALERIE noch nicht entfernt (Nutzerentscheid „alle Maße aus Fotos").
- Gesims Süd endet ~0,6 m vor den Ecken; Balkenköpfe Süd fehlen; Ost kein Ergebnis.
- Nischen: Tiefe nur ANNAHME (Druckmindestmaß 0,07; Hand 0,15), Sohlbank ~9 cm zu tief, rechte Nische „korb" statt „rund"; Fensterlaibungen ~0,36 m zu tief (laibung_aus_fotos rechnet ab Fassadenebene); weitere Verwerf-Stellen: oeffnungen_wandbild.py:225-229, fenster_tiefe_tor.py:96-102, ebenen_masse.py:150, vordach_profil.py:290, erkennerkasten_pruefen.py:142.
- Schwimmende Körper (2-5 getrennte), Abnahme rot seit 1122p; Tor-Scheitel/Breite; Dachknick/rund_aus_huelle rc 4; Uhrzeiger grob, Süd 3 Fotos; Gegenprobe an zweitem Objekt; `gps_unsicherheit.band` latent.
- Konvergenz-F1 (Agent): grobes F1 trennt kaum (0,00-0,16 über Zufall) -> Bild entscheidet; West 2 Fotos OOM bei 2,6 Mio. Dreiecken; Süd/West fein braucht nahe Fotos (Fotoauftrag); gemeinsame Fassadenebene Hand vs. Kette im Süden ungeklärt.
- 4 Baumdateien lokal geändert gewesen -> Patch `/media/oem/rcdaten/tmp/beiseite_merge/baumdateien_lokal.patch`; 3 Archivdateien dort beiseite (identisch in main eingecheckt).
- Worktrees aufräumen (nur sauber, nie --force; Locks per `git worktree unlock`): .claude/worktrees/agent-a775d50f..., agent-a9c5caaf..., /media/oem/scan/rc-park_tmp/{merge_probe31, wt_konvergenz_f1}; Root-Platz >= 15 GB halten (zuletzt 13 GB).
- Lehre heute: Warter nie mit `pgrep -f` auf eigenes Muster (findet sich selbst); `tools/py` kennt kein `-u` (PYTHONUNBUFFERED=1 setzen); eigene `timeout`-Grenzen bei GPU-Jobs weglassen, Job per job_start.sh.

## Vorsicht
- Nur EINE Kette; keine Rechenläufe daneben (Wissensindex erst nach dem Kettenstart-Fenster/zwischen Läufen).
- Fremde uncommittete Dateien nie committen (modelle/kaufhaus_grob3 u. a.). Hook nur Nutzer.

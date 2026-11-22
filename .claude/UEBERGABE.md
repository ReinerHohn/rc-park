# Übergabe 22.11.2026 16:00
Weiter mit: „weiter“ (oder /uebergabe fortsetzen; vorher Skill `sitzungsbeginn`). Zuerst Lauf `1122k` auswerten (siehe „Läuft gerade“).

## Auftrag
- „nicht manuell rumfummeln, die Kette sollst du automatisch machen“, „Schwabentor zuerst“ → Modell nur aus Kettenläufen (`tools/gesamtkette.py`).
- „Löse knallhart das Ausrichtungsproblem.“
- „Der Grundrisscheck ist wichtig, den müssen wir jetzt bestehen. Wir müssen genau die Kanten treffen und untersuchen, warum es früher besser war.“
- „Na, keine Abkürzungen. Ich will jetzt das generelle Modell bauen.“ (kein schwab_v3-SfM als Eingabe)
- „Lösche erstmal nur, was unbedingt sein muss … Erstmal geht es darum, dass wir endlich mal eine stabile Methode bekommen. Danach können wir immer noch aufräumen.“
- Ziel in einem Satz: Die Kette baut das Schwabentor von null, Lage-Tore (GPS, Grundriss, Wanddicke) bestanden, Bild + Fehlerliste + Realitäts-% an den Nutzer.

## Erledigt und geprüft (main e0ac6c230, gepusht, Schnelltest 0 Fehler 15:55)
- Ursache der falschen 1122-Lage belegt: SfM ist starr und richtig (teil0 gegen 1120: 0,06 m), falsch war nur die Ausrichtung; Nah-GPS einer Sitzung ist +9,4 Grad / x0,867 verzerrt; 10 Fernfotos (314-325 m) fehlten, weil `seiten_erkennen --streng` ihre Gruppe 22 abschnitt.
- Fernsicht-Fix (`seiten_erkennen.py --fernsicht`): Lauf 1122i registriert 521 Bilder, GPS-Tor sieht 10 stimmige unabhängige Fernfotos.
- Eine GPS-Quelle für Tor und Ausrichtung (`gps_unsicherheit.gps_fit`), ehrliches GPS-Band (Sitzung x Ring), Lageproben (Wandfit mit Nachbarn, Oberkante, Kamerahöhe nur verwerfend). Probe auf Kopie (Agent): Teil 0 liegt 0,88 m neben der 1120-Lage, GPS-Tor „Lage passt“ (+1,2 Grad, x1,013). Im Kettenlauf noch NICHT bestätigt.
- Lot-Fix (`seiten_gps_vereinen.lot_aus_bild_achsen`): Südwand Teil 1 von -25,6 auf +0,6 Grad Neigung (Agentenprobe).
- Neue Stufen/Tore: `wand_dicke_tor.py` (Grenzen 1,2 m / 0,5 m am 1120 begründet), `seiten_querspur_binden.py` (lehnt Gegenseiten-Verwechslung ab), `seiten_lod2_je_teil.py`, `sfm_gps_ausgleich.py`, `seiten_lage_beleg.py` (Teil nur bei belegter Lage einsetzen, sonst Fotolücke), `colmap_rig_abgleich.py` (seiten_luecken-Absturz), `leistung_messen.py`, `sparse_modell_schreiben.py`.
- Grundriss-Tor: geklärter Haufen gilt nur bis 2x Punktzahl (`haufen_geklaert`).
- Lizenzen an Primärquellen geprüft (`modelle/LIZENZ_WERKZEUGE.md`, Nachtrag 22.11.): MoGe-2 und gsplat ja; VGGT-1B-Commercial, DA3 (BASE/SMALL/METRIC-LARGE/MONO-LARGE), LoMa `commercial_*` mit Auflage; VGGT-Omega, GS4Buildings, LiP-Map, RoMa-v2-Gewichte nein/ungeprüft.
- Geschäftsstrategie: `Doku/konzept/team-und-gruendung.md` (Stahlbühne, Zwei-Orte-Modell, 8 Wege Leute finden, Startplan).
- Widerlegt (im Logbuch): Brennweiten (Verhältnis 1,002), „Teilmodell verbogen“, Querspuren als Bindung (167 Grad), GPS-Prior-Ausgleich als Lösung für den Teilversatz, „Anker abschalten reicht“.
- UNGEPRÜFT: ganzer Lauf mit allem zusammen (läuft als 1122k); Martinstor und Kaufhaus mit neuem Ausrichtungscode als echter Lauf; seiten_luecken nach dem Rig-Fix; Bau-/Fassadenstufen mit weggelassenem Teil.

## Läuft gerade
- Job `rcpark-kette-schwabentor-null-1122k` (Start 15:55, `--ab sfm`, JOB_RAM_MB 11000) · Log `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122k.log`, Stufenlog `/media/oem/scan/rc-park_daten/schwabentor-1122/gesamtkette.log` · Prüfen: `grep -a "ERGEBNIS DES LAUFS\|ABBRUCH\|JOB_ENDE\|HANDSTAND" <log> | tail -4`.
- Erwartet (ANNAHME): Nachstufe neu → `seiten_modelle` = Teil A allein + Fotolücke Teil 1 (Südostseite laut GPS), GPS-/Lage-Tore grün, Grundriss-Tor grün (Teil 0 in 1120-Lage: 2,1 %), wand_dicke rc 2. Besteht die Lage, baut die Kette weiter bis `druck` (60-90 min).
- Folgeschritt: Tore lesen (GPS-Fit, „A Strasse“, LAGEPROBEN, seiten_fotoluecke), `modelle/schwabentor-1122/audit/wolke_grundriss.png` ANSEHEN; bei Bau: `audit/neben_*.jpg`, `audit/neben_details.jpg`, `seiten.jpg` ansehen und schicken (Fehlerliste, Realitäts-%), 3D-HTML als Artifact.
- Kein Agent läuft. Kein Warter gesetzt (nach /clear neu setzen, einmalig).

## Nächste Schritte
1. Lauf 1122k auswerten: `grep -a "ERGEBNIS DES LAUFS\|ABBRUCH\|JOB_ENDE" /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122k.log | tail -3`; Stufenmeldungen ab letztem `=== sfm` in gesamtkette.log. Log IMMER je Lösung lesen (welche Zeile gehört zu welcher `korrektur_loesungK`).
2. Scheitert er: benannte Ursache → EIN opus-Agent im Worktree (Skill `kette-schleife`), Merge nur bei Schnelltest 0.
3. Besteht er: Bilder + Fehlerliste + Realitäts-% + 3D-Viewer an den Nutzer; Logbuchzeile; dann Endbeweis = ein Lauf OHNE `--ab` (3-4 h, JOB_RAM_MB 11000).
4. Lage-Prüfstand bauen lassen (Ausrichtung + Tore auf gespeicherten Ständen 1120/1122/Martinstor/Kaufhaus in Minuten) und Lage-Tore VOR die dichte Wolke ziehen; Lösungsliste der Ausrichtung zwischenspeichern (3 x 9-11 min).
5. Teil 1 binden (offen, Codestelle `tools/seiten_lod2_je_teil.py` teil_legen/suche): Wandende-Probe, Maßstab aus Gesims-/Quaderlagenhöhen, Brückenfotos.
6. Martinstor `--ab sfm` als zweites Objekt ohne neue Agenten.
7. Später: Thread-Messlauf M1 (`modelle/MESSPLAN_LEISTUNG.md`), Messtest VGGT-Commercial/MoGe-2, `lot_aus_fotos.py` (Fluchtpunkte) als Lot-Probe in die Kette, Aufräumen/Packen der 2-TB-Platte (gemessen: ca. 200-240 GB Ersparnis).

## Entscheidungen des Nutzers
- ✓ Keine Abkürzung über schwab_v3; generelle Methode zuerst.
- ✓ Grundriss-Tor bleibt streng. ✓ Nichts löschen/packen außer Nötigem. ✓ `agent_tmp_rig_1122` hat der Nutzer selbst gelöscht.
- ? Geschäft: Zeit/Eigenkapital, Mitgründer, Start Bibliothek oder Werk/Ganter, Zielmonat Info-Abend, Name, Verein oder GmbH zuerst.
- ? Plattenplatz Root: Mindestregel 15 GB ist mit 48-GB-Partition kaum erreichbar (jetzt 6,9 GB); Aufräumen/Packen freigeben?
- ? RAM-Aufrüstung / größere interne SSD (Hardware-Vorschlag).

## Fehler und Lehren dieser Sitzung (Details: Logbuch 22.11., `modelle/METHODE_SEITEN_SFM.md` Versucht, `Doku/projekt/lage-seiten.md`)
- Mein GPS-Anker (3 x Bootstrap) kannte nur den Zufallsfehler → zwang die Lage ins verzerrte Nah-GPS. Lehre: systematischer Fehler je Fotositzung, Fernfotos mit langem Hebel zählen.
- Dreimal dasselbe Muster: zwei Stufen rechnen dieselbe Größe verschieden (Lot Mittel/Achsen, GPS Tor/Ausrichtung, GPS-Kameraauswahl). Lehre: eine Funktion, ein Prüfstand.
- Eigene Fehlmeldungen: Log von 1122j falsch gelesen (Werte der verworfenen Lösungen als gewählte Lage gemeldet); Hypothesen „verbogen“ und „Brennweite“ falsch; 8 Zeitschätzungen nicht gehalten.
- 1120 war nur an Nord/Ost geprüft, Rückseite dort 107 Grad verklebt: „bestanden“ heißt nicht „alle Seiten richtig“.
- Schnelltest ohne Ergebniszeile (Zeitlimit) ist KEIN Bestehen; Root unter 5 GB lässt 3 Tests fallen (`platz_pruefen` Notgrenze).
- Der „Nulllauf“ 1122 ist kein ununterbrochener Lauf (13 Jobstarts, Fotos/Paare von 02:28 wiederverwendet).

## Wichtige Pfade und Befehle
- Start: `JOB_GPU_MB=4000 JOB_RAM_MB=11000 bash tools/job_start.sh kette-schwabentor-null-1122<x> /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122<x>.log /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1122 --ab sfm|tore --dicht-stufe schnell`
- Daten 1122: `/media/oem/scan/rc-park_daten/schwabentor-1122` (Symlink auf die USB-SSD `/media/oem/rcdaten/...`); Agentenproben `/media/oem/rcdaten/tmp/gu_probe`, `gu_probe2`, `gps_ausgleich_1122`.
- Schalter: `AUSR_GPS_ANKER=0`, `AUSR_GPS_EINE_QUELLE=0`, `RCPARK_TEIL_NUR_BELEGT=0`, `RCPARK_SEITEN_GPS=0`, `RCPARK_LOD2_JE_TEIL=0`, `RCPARK_QUERSPUR=0`, `RCPARK_GPS_AUSGLEICH=0`, `RCPARK_WANDDICKE=0`.
- Vergleichsbilder: Scratchpad `/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/gr/` (kanten_vergleich.png, ueberlagert_1120_1122.png).
- 3D-Viewer 1120: https://claude.ai/artifact/ScV8KGvyjJrxxHCAzCM6pi (Datei `/media/oem/scan/rc-park_daten/schwabentor-1120/schwabentor-1120_3d.html`).
- Attribution in Commits: `Co-Authored-By: Claude <noreply@anthropic.com>` + `Claude-Session: https://claude.ai/code/session_01BMC5F7JqzthTsrTAV2gKLz`.

## Vorsicht
- Nur EIN Kettenjob; Agenten rechnen nicht während der Kette (systemctl-Prüfung als eigener Befehl). Nie in main mergen, während die Kette läuft.
- Fremde uncommittete Änderungen nicht committen: `modelle/kaufhaus_grob3/*`, `martinstor_gk`, `MASSNACHWEIS.md`, Audit-Bilder von 1120.
- Worktree `ram-je-stufe-1120` nicht anfassen; Worktrees nie `--force` entfernen (drei haben unversioniertes `modelle/.cache_lod2/`).
- Toshiba-Platte nie anfassen. Löschen nur nach ausdrücklichem „Ja“. Root-Platte beobachten (unter 5 GB bricht die Kette ab).

# Übergabe 21.11.2026 16:05 (fortgeschrieben)
Weiter mit: „weiter“ (oder /uebergabe fortsetzen; vorher Skill `sitzungsbeginn`)

## Auftrag
- Nordstern (Nutzer): „möglichst schnell dahin kommen, dass wir aus Daten Modelle erzeugen, möglichst vollautomatisch“ – generalisiert, beliebige Gebäude.
- „Nein, sie muss von Null ab das selber ermitteln. Der Handstand darf hier keine Rolle spielen.“ → schwab_v3 nur Vergleich von außen nach Läufen.
- „Also ich will jetzt die Low-Hanging Fruits ernten … Teilschritte noch validieren, möglichst parallelisiert. … Gib alles, gib Vollgas, Agenten, alles.“
- „Du darfst erstmal für die Beweise auf vorhandene Daten zugreifen und dann irgendwann müssen wir mal eine Kette von Null abmachen.“
- „Logge alles mit und lerne daraus und gib immer so früh wie möglich Zwischenmeldungen.“ / „Stell die Lizenz mal hinten an.“
- Letzte Frage (beantwortet 15:30): Relief-/Steinerkennung „auf den Stein genau – ist die in der Kette drin?“ → ja (fassaden_kette --fotosteine --fein), aber Schwabentor nur w01/w03 mit Fotoquadern.

## Erledigt und geprüft
- Martinstor Süd+Nord ohne GPS vereint (Masken → Seitenerkennung mit Masken → globaler Mapper → Wolken → seiten_vereinen mit spitze_global/lot_b/dreh_b); 3D https://claude.ai/artifact/22eEm3PCx5NWmbYTUoiAhQ; Belastungsprobe 8 Läufe Endlage 0,26–0,96 % / ≤0,49°.
- Seitenkette in gesamtkette.py: tor_seiten_blick (hart), brennweite_schaerfe → sfm/sperrliste_messen.txt, seiten_vorstufe, seiten_modelle (Agenten-Commits bffeb2b45, a7fc0be1b, d8a0bce5b).
- Wolkenrest + Dachprofil in der Kette (wolke_rest.py, dach_profil_wolke.py, bauteile drehkoerper_aus_wolkenrest/dach_aus_profil); Kettenlauf Schwabentor 1121m 15:15–15:26 alle 26 Stufen, Wolkenpunkte am Modell 625 356 → 653 817.
- uhren_aus_json: Uhrring reicht hinter Wandversatz (59ba2c366) – UNGEPRÜFT (kein Neubau).
- Agent „Öffnungen aus Kanten“ gemergt (84f6c437b): tools/oeffnungen_aus_kanten.py, Test bestanden (11 s). Befund: nur aus Kanten 0/3; mit --wolke Tor+2 Fenster gefunden; Tor 5,37 m breit vs Handstand 4,32 (ungeklärt), Form Rundbogen statt Spitzbogen, Fenster unbestimmt; Beifang ungeprüft. Noch NICHT im Generator.
- Skill erkenntnis in ~/git/claude-mds; Register modelle/ERKENNTNISSE.md; Rezept modelle/METHODE_SEITEN_SFM.md.

## Läuft gerade
- Kette Martinstor `kette-martinstor-1121a` (--ab sfm, vorhandene DB; alte sparse in pipe/sfm/alt_1121) · Log /media/oem/scan/rc-park_daten/job_logs/kette-martinstor-1121a.log · Prüfen: `grep -a "JOB_ENDE\|FEHLER\|Seiten" <log> | tail` · danach: Seitenteile, Vereinen, Blick-Tor, Lage gegen LoD2-Grundriss auswerten, in METHODE_SEITEN_SFM.md nachtragen. Belegt GPU ~6989 MiB.
- Agent „Bogenkanten aus Wandbild“ (Worktree-Agent, gestartet 15:55): oeffnungen_aus_kanten mit Bildkanten aus ortho_f00(_fein).png, Maße außen/licht/Fase getrennt · Ergebnis prüfen, mergen, Schnelltest.
- Fächer-Analyse r00 (Scratchpad faecher.py, Hintergrund): welche Kamera erzeugt den Streupunkt-Fächer am Schwabentor.
- Dauerdienste gpuwache/platz_waechter/editordraht nicht melden.

## Erledigt 15:40–16:05
- Schwabentor Uhrring-Neubau: Abnahme bestanden, 1 Körper (vorher 2); Neben-Fotobilder CUDA-OOM unter Martinstor-Last → nachholen.
- koerper_schleife gemergt (992f43415), Schnelltest 0 Fehler, Regression identisch, Abnahme bestanden, Worktree entfernt.
- Torbreite geklärt: 5,37 = Außenkante Fase, 4,49 = lichte Weite; Form Spitzbogen (Werkzeug wählte Rund).

## Nächste Schritte
1. Martinstor-Lauf prüfen (Befehl oben); bei Ende Auswertung + Bild + Realitäts-%.
2. Danach GPU frei → `bash tools/schnelltest.sh`; offener Fehler test_kette_stabil (foto_diff FileNotFoundError / laut Agent CUDA OOM unter Fremdlast) – bei freier GPU wiederholen, sonst Ursache fixen.
3. Schwabentor neu bauen (Uhrring-Fix) → Skill abnahme (`tools/bauen_abnehmen.sh schwabentor-1120`), Bilder ansehen.
4. fassaden_kette für Schwabentor w00/w02 nachholen (Fotoquader fehlen; tiefe_lokal.py Signal 6 untersuchen).
5. oeffnungen_aus_kanten: Bogenkanten aus feinem 1-cm-Wandbild im gefundenen Fleck; Torbreite-Abweichung klären; dann in Kette/Generator.
6. hand_vergleich um Treppenturm/Dach aus Wolke erweitern (zeigt weiter 2/11).
7. Vereinen-Schwächen: Höhenlage nach Lot-Berichtigung, geklappt() Mindestpaare; Maßstab zweite Seite (3 %).
8. Später: Martinstor Kette ganz von null über Nacht (Masken in Merkmalssuche); drittes andersartiges Gebäude.

## Entscheidungen des Nutzers
- ✓ Handstand nie in der Schleife. ✓ Globaler Mapper Standard. ✓ Lizenz SegFormer hinten angestellt. ✓ Agenten parallel in Worktrees selbst starten.
- ? Keine offenen.

## Fehler und Lehren dieser Sitzung
- Job-Befehl als ein String an job_start.sh (rc 127) → einzelne Argumente; libcudart fehlte im Mapper-Skript → Dummy-Test vorher.
- pkill -f mit eigenem Muster (Regelverstoß). Falsche Uhrzeit gemeldet → immer `date`.
- Root-Platz 2,5 GB ließ Kette still scheitern → Platz-Tor beachten (jetzt 5,4 GB frei).
- Blick-Tor-Fehlalarm, modell_lage_vergleich 1. Fassung, dach_profil 1./2. Fassung: Messfehler eigener Werkzeuge → modelle/ERKENNTNISSE.md, modelle/ANALYSE_SACKGASSEN_2026-11-21.md.
- Lehren im Logbuch modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md, GLOBALER_MAPPER_STABIL.md (ab „Untersuchung 21.11.2026“).

## Wichtige Pfade und Befehle
- Martinstor-Daten /media/oem/scan/rc-park_daten/martinstor-1120/ (zeigen/vereint_1121.html); Versuchsskripte tools/versuche/*_1121.*
- Hand-Dateien Schwabentor koerper_auto.json/dach_profil.json lagen im Scratchpad sw_hand_1121 (flüchtig).

## Vorsicht
- Worktree agent-a1b159488c8983a24 (Zweig ram-je-stufe-1120, nicht in main) nicht anfassen; agent-adc725… ist locked (Agent läuft).
- Uncommittete fremde Änderungen (kaufhaus_grob3, martinstor_gk, MASSNACHWEIS-Dateien) nicht mitcommitten.
- Toshiba-Platte nie anfassen; Buchung RAM/GPU nie von Hand senken.

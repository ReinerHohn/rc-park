# Übergabe 28.11.2026 13:55 (löst die von 26.11. ab)
Weiter mit: „weiter" (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`. Anrede „mein grosser Meister", Deutsch, keine breiten Tabellen. Nutzer will bei JEDER Neuigkeit eine Meldung.

## Auftrag
- Ziel: Schwabentor-Turm (Brücke später) als druckbares H0-Modell 1:87. Nutzer 28.11.: „Der Turm muss gut sein. Den Rest können wir nacharbeiten." „Ziehe alle Register, Pod ist auch erlaubt … nichts ist verboten." „Lizenz ist scheißegal, erstmal durchtesten."
- Nutzer ist vor Ort gewesen und hat Fotos gemacht (siehe unten); will wissen, wann Modell/Wolke besser werden. Ihn ärgert Warten ohne Zahlen: nie Zeiten ohne Messung versprechen, ANNAHME kennzeichnen.

## Erledigt und geprüft
- Kette 1128d (Ende ~12:15, rc 4, 96 Stufen, 5 rot: bauplan_oeffnungen_aussen, bauplan_wolkenkoerper, abdeckung_zusatz, freiraum_tor_ergebnis, tauschtest_ergebnis). Handvergleich 9 von 11 PASST, Bestand-Tor „kein Rückschritt", 0 Tracebacks, 0 OOM, bestand_tor 14,6 min. Bilder angesehen: Dach/Uhr/Rundbögen/Georgs-Vordach besser als Bestand 24.11.; Ost/West flach, Tür Kasten, Brücke fehlt, Konsolen unter Vordach dünner (kleiner Rückschritt). Modell nur gesichtet, nicht in main.
- Probelauf `ketten-probe-par1` (merge-1128, RCPARK_STUFEN_PARALLEL=1): rc 0, Szenario cache 165 Stufen 29,3 min, marke 60 Stufen 12,9 min, 0 Ablauffehler. Bitgleichheit gegen Lauf ohne Schalter NICHT geprüft.
- 138 Handyfotos von heute (IMG_20261128_083156..122834, 136 mit GPS) als Originale in `/media/oem/rcdaten/tmp/handy_1128_original/` (Größenvergleich mit Handy ok). Ältere Kopien `handy_alle_original/` (~270) und `handy_schwabentor_original/` (228) liegen herum, NICHT gelöscht (nur nach „Ja").
- STL 1128d (`/media/oem/scan/rc-park_tmp/kette_integ/modelle/stl/schwabentor-1122_1-87.stl`): Hauptkörper wasserdicht 163×189×612 mm; ZWEI lose Teile (14 Dreiecke Volumen 0; 12 Dreiecke 7×7×13 mm) = Bauschritt-Fehler, Ursache offen; Höhe 53,2 m gegen DOM1-Max 49,6 m/Traufe 38,3 m offen.
- SIFT-Registrierung der 138: 66/138, Reproj 1,42 px (median 1,24); GPS-Abweichung median 10,2 m, max 42,7 m (schwache Gegenprobe, Handy-GPS in der Stadt).
- Recherche LIMAP/LiP-Map (Agent, nur gelesen): LIMAP bei uns schon 3× gelaufen (25.11. Gesims f01: K_L 0,0–1,4 m gegen Sweep 7,5 m); Stand im Zweig `agent-limap` (41 Commits vor main, ungemergt); AGPL in pytlsd; K2-Bericht nennt fälschlich „verkaufstauglich" (Zeile korrigieren); LiP-Map ohne Lizenz, nur Innenräume belegt. Beschluss Nutzer: Lizenz beim Testen egal (Memory `feedback-lizenz-beim-testen-egal.md` gespeichert).
- Kühlung: i7-14700HX (OMEN 16), Turbo an, platform_profile performance, RAPL 75/75/200 W; 92 °C bei 55,6 W vorher, nach Erhöhen + Zusatzlüfter 79–83 °C bei 60–64 W (nur Hinweis, nicht kontrolliert).
- Git: main 2 Commits VOR origin (Notgrenze 2 GB `32c93d544`, Doku `3986ec0e4`), ~3455 uncommittete Dateien im Arbeitsbaum (Altlast modelle/…, nicht von mir; nie `git add -A`).

## Läuft gerade
- Hybrid-Registrierung (Agent a0f7e37a418f7bce9, Dienst `rcpark-hybrid1128`): Zielordner `/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261128_hybrid/`, `zeiten.txt`/`lauf.log`; lg_paare fertig (1260 s), seit 13:54 Stufe `einlesen`, danach registrieren_hybrid. Prüfen: `cat …/zeiten.txt; tail -n3 …/lauf.log`; Ergebnis `registrierung.json` + `gps_gegenprobe.json`. Auftrag erweitert: danach die 144 alten, nicht eingeordneten Handyfotos (26.11., v.a. Brücke/Treppe) gegen die neuen erneut versuchen, getrennt melden.
- LIMAP-Test (Agent a0d533bbe3d553620, Worktree agent-a0d533bbe3d553620, Dienst `rcpark-limapt1`): Gesims f01 mit allen Optionen, senkrechte Kanten, ggf. LiP-Map; Abbruchregeln im Auftrag. Bericht abwarten.
- Pod (Agent aeb8e9aa07b304032): Upload auf Volume ghhv7k1089 (`rc_kette/`, 6 TAR; fehlt nur zusatz.tar 2,1 GB; Dienst `rcpark-upload2-kette-pod`, Log `/media/oem/rcdaten/tmp/runpod_test/kette_pod/upload2.log`, Ende `UPLOAD2_ENDE`). CPU-Dummy-Pod `deuf2ebaki3v1b` (0,32 $/h, läuft seit 13:45, cpu3g 8 vCPU, 20 GB Platte; nach Dummy löschen + per list-pods prüfen!). Danach GPU-Pod RTX 4090 (0,89 $/h, Preis vorher nennen, Guthaben 43,55 $, ≥5 $ halten). Vorrang: 1 Kette grund+par, 2 LIMAP/LiP-Map (erst nach lokalem Bericht), 3 ALIKED/LG volle Auflösung, 4 dichte Wolke nur wenn Zeit.
- Dauerdienste (nicht melden): editordraht, platz_waechter, *-gpuwache.

## Nächste Schritte
1. Agenten-Meldungen lesen (Registrierung, LIMAP-Test, Pod) und dem Nutzer SOFORT berichten, mit Zahlen (eingeordnet x/138, davon Gruppen Treppe/Steg/Giebel; alte 144 zusätzlich; GPS-Gegenprobe gegen die schon registrierten Fotos als Vergleich).
2. Nach Registrierung: neue Kette `tools/gesamtkette.py` mit den neuen Kameras (nur EINE Kette; Probelauf/Merge-Sperre vorher): `bash tools/merge_sperre.sh` = 0, `bash tools/schnelltest.sh` = 0 (RAM ≥ 8 GB), dann merge-1128 → main (nie --force), `git fetch` + merge + push, `python3 tools/baum_erzeugen.py`; danach Bild-Vergleich `audit/neben_*.jpg` gegen `modelle/schwabentor-1122/bestand/`.
3. Turm-STL: lose Teile ursächlich im Bauschritt entfernen (generisch), Höhe 53,2 m aus Fotokanten gegenprüfen (Laser kann falsch sein), Druck-Check (Mindestmaß 0,8 mm, ein Körper); Druck nur auf Nutzerwunsch.
4. Bitgleichheit Parallelschalter prüfen (Lauf mit/ohne `RCPARK_STUFEN_PARALLEL=1`), erst dann Standard AN.
5. `agent-limap` nach main bringen (Konflikte), K2-Lizenzzeile korrigieren, Viewer mit 1128d-Modell neu bauen (`.claude/viewer_v2/schwabentor_3d_v2b.html` ist von 09:20, ALT).
6. Offen: Nordwand frontal + Durchfahrt innen noch nicht fotografiert (Nutzer evtl. vor Ort); Nordwand = Uhr-/Georg-Wand (Modell +x, Azimut 344°), nicht „ohne Uhr".

## Entscheidungen des Nutzers
- ✓ Turm zuerst, Rest später. ✓ Pod nutzen, alles erlaubt. ✓ Lizenz beim Testen egal. ✓ Hybrid (ALIKED+LightGlue) für Registrierung. ✓ nur Fotos von heute (Handy-Kopie).
- ? Soll LIMAP-Test für senkrechte Kanten + Zweig agent-limap-Merge Priorität bekommen (Agent testet gerade)? ? Löschen der Kopien `handy_alle_original/`, `handy_schwabentor_original/` (nur nach „Ja").

## Fehler und Lehren dieser Sitzung
- Ich habe mehrfach Zeiten und Richtungen ohne Messung genannt (Probelauf „~1 h", Himmelsrichtung Uhrwand Ost statt Nord, Upload „12 Kerne"/„0 Bytes" wegen falschem Pfad, „ALIKED/LightGlue nicht benutzt" obwohl lg-Lauf es nutzte): vor Aussagen nachmessen.
- `pkill -f` mit Muster aus der eigenen Befehlszeile hat meine Shell beendet (Regel bekannt): stattdessen `pgrep` + `kill <pid>`.
- Voller `schnelltest.sh` lief gleichzeitig mit der Registrierung (Last 31); Urheber nicht ermittelt; Agenten sollen ihn nicht fahren.
- `foto_check.sh` braucht `modelle/<obj>/audit/fotoauftrag.json` (für schwabentor-1122 fehlt sie; gab sinnlose „nan m"): nicht als Urteil nutzen, ggf. ersetzen.
- Runpod-S3: Kleindateien extrem langsam, 524-Timeouts, Umlaute brechen setzen der Änderungszeit → TAR-Pakete + `--size-only --no-update-modtime`. Wissensbaum-Eintrag noch offen (Doku/projekt/betrieb/rechner-jobs.md, local Commit vorhanden).

## Wichtige Pfade und Befehle
- Chain-Worktree `/media/oem/scan/rc-park_tmp/kette_integ`, Merge-Zweig `merge-1128` (`/media/oem/scan/rc-park_tmp/merge_1128`), Logs `/media/oem/scan/rc-park_daten/job_logs/`.
- Pod-Daten: `/media/oem/rcdaten/tmp/runpod_test/kette_pod/` (upload2.sh, pod_kette.sh). rclone: `. ~/.runpod/rclone_env.sh; ~/.local/bin/rclone size rp:ghhv7k1089/rc_kette`.
- Handy per MTP: `/run/user/$(id -u)/gvfs/mtp:host=Unisoc_Unisoc_Phone_324452041248/Interner gemeinsamer Speicher/DCIM/Camera` (heute abgezogen).
- Verfahrens-Grafik: Scratchpad `verfahren_kette.html` (27.11.), Stand-Bild `verfahren_stand.png`.

## Vorsicht
- Nur EIN Kettenlauf, keine zweiten Rechenjobs auf gleicher Zwischendatei; GPU-VRAM-Summe ≤ 7000 MiB (Registrierung + LIMAP teilen die lokale GPU).
- Nichts löschen ohne „Ja"; Worktrees nie `--force`; Referenznetz/DB nie verändern; Root-Platte nur ~8,6 GB frei, alles Große nach /media/oem/rcdaten.
- Pods: Preis vor Anlegen nennen, nach Lauf löschen und per `list-pods` prüfen; Zugangsdaten nur in `~/.runpod/`.
- Kühlung: Nutzer hat Laptop erhöht + Zusatzlüfter; PL1/PL2 nicht ohne Okay ändern.

# Übergabe 20.11.2026 16:30
Weiter mit: „weiter“ (oder /uebergabe fortsetzen; vorher Skill `sitzungsbeginn`)

## Auftrag
- „Zeig mir das Kameramodell, sobald es fertig ist“ (16:20) → OFFEN, Schritt 1
- „Bitte nachher den Lauf nicht stoppen, ich bin nicht zu Hause, lass durchlaufen“ → Schwabentor-Kette startet automatisch nach dem Martinstor
- „Ich will alle Optionen für mehr Qualität, mehr Geschwindigkeit und Vollgas“ / „weitere Hardware-Configs oder Kernel-Optionen … Dateisysteme, Caching, CPU-Clocks“ → läuft, Stand `modelle/HARDWARE_STAND_2026-11-20.md`
- „gib mir jeweils Uhrzeiten, wann war es fertig“ → bei jeder Meldung die echte Fertig-Uhrzeit nennen
- HARTE REGEL neu: „es darf nur auf der SSD sein, was unbedingt sein muss, der Rest muss ausgelagert werden … vielleicht sogar gezippt“ (CLAUDE.md Technik, Memory feedback-interne-ssd-nur-noetiges)
- Weiter gültig: komplett autonom arbeiten, nirgends mit einer Frage stehen bleiben. Ziel: H0-Modelle aus Fotos (Kernmethode), aktiv Martinstor-Kette von null, danach Schwabentor, FlexGlue-Messung, Kaufhaus

## Erledigt und geprüft
- Ursache Kettenabbruch 13:27 gefunden + behoben: Start 08:36 mit Standardwerten (nur 12 langsame Kerne 16-27 + 3 h Limit). `tools/job_start.sh` gibt Kette/SfM/Mapper/dichte Wolke immer alle Kerne, `gesamtkette.py` SfM mind. 6 h (Pin-Test beide Richtungen, Schnelltest 0 Fehler). Konsens-Läufe 77 → 49 min gemessen
- CPU-Dauerleistung: 110 W statt 55 W gemessen (Nutzer mit sudo, `tools/versuche/vollgas_test2.sh`: 70/90/110 W = 70/79/93 °C kalt, 80/88/96 °C durchgewärmt, 0 % Drosselung). Nötig: WMI (neues hp-wmi mit `rcpark_pl*`, geladen) + MSR + MMIO gemeinsam. Regler `cpu_leistung_regler` eingespielt (MAX=100, START=55, Temperaturmittel), pendelt 55–80 W
- Interne SSD freigeräumt (geprüftes Verschieben, `tools/versuche/intern_freiraeumen_1120*.sh`): scan 40 GB frei (vorher 15), Volume 159 GB frei (vorher 18); Altarchive in `/media/oem/rcdaten/auslagern_Volume_archiv`, alter Lauf `martinstor_gk3/pipe` als Verknüpfung nach rcdaten; rcdaten 43 % belegt
- zswap an (zstd, 25 % RAM, dauerhaft; `tools/zswap_an.sh`): 16:28 gemessen 522 MB in 147 MB (Faktor 3,6)
- RAM-Bestand gelesen: 2 × 8 GB DDR5-5600, Firmware erlaubt 64 GB → Kaufempfehlung 2 × 32 GB DDR5-5600 SO-DIMM
- OpenBLAS-A/B: kein Gewinn (158 → 148 s CPU, GPU-Löser 33 s) – nicht umgestellt (Ast betrieb)
- Externer Lüfter: Wirkung NICHT belegt (durchgewärmt 3–10 °C wärmer als kalter Lauf ohne Lüfter)
- yt-dlp 2026.10.26 in `~/.local/bin` (ohne root); Video h6nO14cZSqE löst wieder auf
- `tools/sparse_zeigen.py` + Vorlage: Kameramodell als Bild + 3D-HTML; Bild am Konsens-Modell angesehen (Boden waagrecht), HTML erzeugt aber NICHT im Browser geprüft
- Regression Schwabentor (`regr-schwab`): „identisch – nichts verloren“
- Alles committet + gepusht (main == origin/main 16:25, 18 Commits seit 268f63f6c)

## Läuft gerade
- `rcpark-kette-martinstor-1120b` (Start 14:50, ab sfm) · Log `job_logs/kette-martinstor-1120b.log` · Prüfen: `grep -E '^\[[0-9:]+\] [a-z_]+:' LOG | tail -1; grep -c Traceback LOG; grep JOB_ENDE LOG` · 16:28: globaler Mapper seit 16:01, Gesamtausgleich 16:13 fertig, seitdem „iterative retriangulation and refinement“ (`pipe/sfm/global.log`), 0 Fehler. Konsens-Zwischenstand: 815/2107 Bilder, 793 „fremde Seite“, GPS-Median 8,7 m · danach Schritt 1
- `rcpark-warter_schwab` (einmalig): startet nach Ende von 1120b `kette-schwabentor-1120` (schwab_auto → schwabentor-1120, Log `job_logs/kette-schwabentor-1120.log`)
- GESTOPPT 14:48, später neu starten: FlexGlue-Stufe 2 (`/media/oem/rcdaten/tmp/flexglue/stufe2.sh`, ~20 h) und Süd-Anhang `mt_anh_sued3` (hing seit 11:59; mit mehr Kernen)

## Nächste Schritte
1. Kameramodell zeigen, sobald `pipe/sfm/sparse/0/images.bin` neu ist: `tools/py tools/sparse_zeigen.py /media/oem/scan/rc-park_daten/martinstor-1120/pipe/sfm/sparse/0 --png <bild> --html <seite> --titel "Martinstor Kameramodell 20.11."` → Bild per SendUserFile, HTML als Artifact (icon „map“), Zahlen: registrierte Bilder von 2107, fremde Seite angebunden?, `mapper_wahl.json`
2. Nach der dichten Wolke Skill `wolke-tore` (Zerfall, Abdeckung, Grundriss, GPS, Seiten), `audit/seiten.jpg` + `neben_*.jpg` ansehen, Fehlerliste, Realitäts-%, 3D-HTML; Stufenzeiten ins Logbuch (Vergleich alt/neu)
3. Schwabentor-Kette auswerten (gleiche Tore); danach FlexGlue-Stufe 2 und Süd-Anhang neu starten (`JOB_CPU=alle`)
4. „Seiten vereinen“ angehen (wichtigster Qualitätspunkt: fremde Seite wird aussortiert, aber nicht angebunden; Rückfall = jede Seite einzeln an LoD2)
5. Regler nachbessern: Grenze nur zurücknehmen, wenn Paketleistung nahe der Grenze liegt (Wenig-Faden-Last ist heißer als Volllast); A/B große Speicherseiten (THP always) am Bündelausgleich; künftige Kettendaten wieder intern statt USB
6. Offen aus der alten Übergabe: Lehren Runde 2 zusammenführen (`/media/oem/rcdaten/tmp/baum_sicherung/runde2/`, 1161 Zeilen, je `## AST:`), „(ungeprüft)“-Punkte gegen Code prüfen, Regression für kaufhaus_gk2 und martinstor-1120 anlegen
7. Kaltes auf rcdaten packen (tar+zstd; Kandidaten `tmp` 181 GB, alte `auslagern_*`), nur wo keine Verknüpfung hineinzeigt

## Entscheidungen des Nutzers
- ✓ FlexGlue für die Kette anhalten, Kette hat Vorrang · ✓ Altes von der internen SSD auslagern („Vollgas“) · ✓ Läufe heute durchlaufen lassen, kein Windows-Neustart
- ? RAM kaufen (2 × 32 GB DDR5-5600, Rückgaberecht) · ? Volume leeren + als ext4 formatieren (nur nach „Ja“, private Ordner Bilder/3DScan vorher klären) · ? Windows-Partition noch nötig?
- ? Cloud ohne Kreditkarte (Trooper.ai PayPal/SEPA, vast.ai Krypto) – Zahlungsart nicht genannt · ? zweiter Rechner (RAM/GPU unbekannt) als Rechenknoten
- ? FlexGlue als Standard (+30/+40 % Bilder, +2,5 h) – erst nach Messung · ? Bambu-Zugangscode neu setzen (alter seit 30.10. auf GitHub)

## Fehler und Lehren dieser Sitzung
- Startbefehle standen nur im Gespräch → nach /clear Start mit Standardwerten; Pin-Fehler beim Neustart 14:50 selbst kopiert → jetzt im Werkzeug (Ast betrieb)
- Falschmeldungen von mir: „Abfall auf 38 W“ (veraltet), „Mapper wird von 55 W nicht gebremst“ (falsch, 55 W bei Teillast), „3,5 h Hitzedrosselung“ (nur ~1 %); erster Vollgas-Test übersah den eigenen Regler → Memory feedback-verbesserung-messen-nicht-doku
- Warter startete FlexGlue nach GESCHEITERTER Kette (rc nicht geprüft) · Auslager-Skript zählte rsync-Hinweise als Abweichung (korrigiert) · `pgrep -f` traf die eigene Shell
- Alle Messwerte: `modelle/HARDWARE_STAND_2026-11-20.md`, Ast `Doku/projekt/betrieb.md`

## Wichtige Pfade und Befehle
- Regler: `cat /run/cpu_leistung_regler.state`, `journalctl -u cpu_leistung_regler -n 20`; neu einspielen `sudo bash tools/cpu_leistung_installieren.sh`
- sudo geht aus der Sitzung nicht (kein Terminal) → Nutzer führt Skripte im eigenen Terminal aus; `energy_uj` nach Neustart wieder freigeben (`sudo chmod a+r /sys/class/powercap/intel-rapl:0/energy_uj`)
- hp-wmi: neues Modul in `/lib/modules/$(uname -r)/updates/`, alter Stand `/media/oem/scan/rc-park_null/hpwmi_bau/build/hp-wmi.ko.stand_0611`; nach Kernel-Update neu bauen/signieren
- Logbuch `modelle/LOGBUCH_KETTENTEST_2026-11-19.md`; Sicherungszweige lokal (nie pushen): `sicherung-vor-umschreiben-1120`, `-geheim-1120`, `-1mb-1120`, `-1mb-b-1120`

## Vorsicht
- Uncommittete fremde Änderungen (modelle/kaufhaus_grob3/…, martinstor/MASSNACHWEIS, martinstor_gk*, ober_tvdr, schwab*) nicht mitcommitten; `git add` nur mit Einzelpfaden
- Laufende Skripte nie an Ort und Stelle ändern (bash liest nach) → neu schreiben + `mv`; Regler-Änderung wirkt erst nach `sudo systemctl restart cpu_leistung_regler`
- Kein zweiter Job mit RAM-Buchung > 2300 MB neben der Kette (15 GB); Worktrees agent-a0d77/agent-a37e9/flaechen-wt nicht entfernen
- Toshiba-Platte nie anfassen; Löschen/Formatieren nur nach „Ja“; kein wiederkehrender Wach-Zeitplan

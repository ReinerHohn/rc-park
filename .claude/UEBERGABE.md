# Übergabe 26.11.2026 05:30 (löst die von 25.11. 23:20 ab)
Weiter mit: „weiter“ (/uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`.
- Lauf 1122zi2 (Start 01:37, Ende 04:26, Probe 34 4e553b602, Probelauf rc 0): Dach wieder Pyramide mit Kragen wie Handstand (Bild gesehen), Uhr 96 %, Tür f04 Gewände+Vertiefung im Bild richtig. ROT: Bestand-Tor f04 F1 0,54 (Bestand 0,81 im eingefrorenen Kasten u 0,229..0,804), Höhen-Tor Dach +1,23 m (Massstab belegt, DOM1 = Veto), Stufigkeit 5 (fenster_f03, linien_band_f03, linien_gesims_f01, oeffnung_bogen_f01, uhr_f01). 7/11 PASST. Merge main GESPERRT.
- Lücke: Massstab-Tor nur in Stufe `tore`; `--ab bauen` überspringt ihn (Trennung OFFEN).
- merge-probe-34 jetzt afe99ac54 = 4e553b602 + Dach-Fototor + Tür-Gewände/Zonen + Fensterform-Band (nischen_fenster, Test test_form_band). Worktree /media/oem/scan/rc-park_tmp/merge_probe34 hat Symlinks (modelle/{schwab_auto,schwabentor-1122,stl,_gen.py}, daten/*); git merge dort scheitert (stash) -> in temporärem Worktree mergen, dann update-ref + git checkout NEW -- <Dateien>.
- Eingefroren: /media/oem/rcdaten/rc-park_teilbau/schwabentor-1122/stand_20261126_013724. Änderungen an nischen_fenster/befundliste/neben_details machen Teilbau VERALTET (code_stand fein zählt `__main__` als Modulebene) -> nur voller Lauf.
- Läuft: Agent adbe10efb3d8c0418 (Stufigkeit 5 Bauteile, Worktree agent-adbe10efb3d8c0418, wartet auf eigenen Teilbau). Bei Bericht: Bilder ansehen, grüne Zweige wie oben in Probe 34, Schnelltest 0, dann neuer voller Lauf (Preflight: daten/schwabentor-1122 im Arbeitsbaum, Symlinks) mit `ketten_probelauf.sh` aus dem Probe-Worktree vorher.
- Fehler dieser Nacht: Befund „Fotos zeigen rund“ aus Detektorlog ohne Foto übernommen (Fotos waren rechteckig); Probelauf erst mit main-Skript (Exit 4).
- Entscheidungen offen (Nutzer): Bestandkasten f04 neu einfrieren? Höhen-Tor Dach nach Foto/Wolke bewerten (Laser nur Veto)? Freigabe der 4 Höhen wurde erteilt und umgesetzt (11bf900e0). Fotos Ost/West, Galerie quer, Rähm-Höhe fehlen.

# Übergabe 25.11.2026 23:20
Weiter mit: „weiter“ (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`.

## Auftrag (Nutzerworte)
- HAUPTZIEL (24.11.): Kette baut das Schwabentor automatisch mindestens so gut wie Handmodell schwab_v3, danach zweites Objekt. Plan `modelle/PLAN_HANDMODELL_IN_KETTE.md`.
- „Alle Maße müssen aus Fotos kommen.“ HART „sichere das hart ab“: nie schlechter als Bestand; nach jedem Lauf ZUERST `audit/neben_*.jpg` neben `modelle/schwabentor-1122/bestand/` + ZIEL_* schicken, dann Zahlen. „Keine Handangriffe, nur Automatik.“
- Zuletzt: „Konvergieren wir jetzt oder nicht?“, „Untersuche, wie man diese Pipeline weiter verbessern, stabilisieren und besser konvergieren lassen kann“, „Aber können wir jetzt nicht schon mit dem Teilbau starten?“
- Deutsch, „mein grosser Meister“, keine breiten Tabellen, Fehlerliste vor Lob, Realitäts-% nur als Schätzung.

## Erledigt und geprüft
- Lauf 1122zh (Start 20:20, Ende 23:06, rc 6, 125 Stufen) mit Probe 34 (acac467ff): Galerie 6 Konsolen (beste bisher, Bild gesehen), Höhen 7/11 nach DGM1-Bezug (zf: 5), Dach auf Laserhöhe. NICHT in Ordnung: BESTAND RUECKSCHRITT Tür `fenster_tuer_f04` F1 0,810->0,636 / `_3` ->0,613 (Lage jetzt 0,043 m neben Wolke, Bestand 0,273 m daneben), Stufigkeit (Uhr, linien_band_f01_2, gesims_f01/f03, verdachung_f01), freiraum_tor ohne Urteil (0/645 Kameras), tauschtest, fototor_urteil. Merge gesperrt.
- 3D-HTML dieses Laufs veröffentlicht: https://claude.ai/artifact/GVKjQ4MwbbrmLHsx1X9rdz (Version 3; Datei `/media/oem/scan/rc-park_daten/schwabentor-1122/schwabentor-1122_3d_1122zh_ende.html`). Bilder an den Nutzer geschickt (Galerie, seiten.jpg, Tür, ZIEL).
- Probe 34 (Zweig `merge-probe-34`, Worktree `/media/oem/scan/rc-park_tmp/merge_probe34`, Kopf b00a97747; alle Einzeltests grün, voller Schnelltest NICHT gelaufen): Maßstab-Tor (massstab_hoehe_tor), Bestand-Lage-Gegenprobe, Dach-Knotenveto, Tür-Fixes (Kappung/Gewände/Breite), Konsolen-Konsistenz, Preflight (kette_preflight.py), Bau-Wirkung (bau_wirkung.py), Probelauf trotz Sperre, seiten_luecken überspringen, Tor-Inventar + test_tor_wirkung + grenze.py, Wiederholstreuung/ehrliches Konvergenzmaß, rote Notizen stiller Tore. Alles ohne echten Kettenlauf (nur synthetisch) – erster echter Lauf mit Preflight/Bau-Wirkung/Konvergenzzeile steht aus.
- Erkenntnis 25.11. (ERKENNTNISSE + Wissensbaum): Handstand-Höhen ~2,6 % zu tief (an Wolke gemessen), Kette stimmt; Kettenmaßstab belegt (meine Meldung „3 % zu groß“ war falsch); DOM1-Veto im Dach seit cd693bf62 still aus (behoben).
- main = 50b01c788, gepusht, nur Doku. Teilbau-Stand eingefroren: `/media/oem/rcdaten/rc-park_teilbau/schwabentor-1122/stand_20261125_202029` (Code acac467ff = Lauf-Worktree `/media/oem/scan/rc-park_tmp/merge_probe33`).

## Läuft gerade
- Kein Kettenlauf (Dauerdienste egal). Zwei Agenten (Worktrees, `git reset --hard acac467ff`, dann Teilbau als Job):
  - `aa06ffe5aeffc4cec` Dach: Aufschiebling zu groß (33°/67°, flacher Kragen bis halbe Höhe; Foto: steiles Zeltdach, schmaler Knick), Ursache + Fix + Teilbau `zeltdach_ueberstand` (~15 min) mit/ohne Fix.
  - `a31c8b0b75d85a45e` Tür f04: warum wirkten die Fixes im echten Lauf nicht; ist F1 0,81 Lagezufall; Fix + Teilbau.
  Ergebnis kommt als Benachrichtigung; Bilder dem Nutzer schicken, dann Zweige in Probe 34 mergen (`git merge --no-ff`, Tests, JSON/bash -n prüfen).

## Nächste Schritte
1. Agenten-Berichte abwarten; Teilbau-Bilder ansehen, Nutzer schicken; grüne Zweige in `/media/oem/scan/rc-park_tmp/merge_probe34` mergen (vorher `git merge-base`/Konflikte prüfen, danach test_undefinierte_namen, test_schwellen_beleg, bash -n tools/schnelltest.sh).
2. Weitere Teilbau-Runden (nach `tools/bauteil_schleife.py liste/plan/lauf schwabentor-1122 <gruppe> --stand ...`): Stufigkeit (Uhr, Gesims, Band, Verdachung), Galerie-Rähm 0,80 m, Streben-u 0,13–0,16 m daneben, freiraum_tor (0/645). Hinweis: Teilbau verweigert, wenn Code des Arbeitsbaums von der Einfrierung abweicht (fassaden_kette CODE-STAND) – deshalb Agenten auf acac467ff.
3. Wenn Tür/Dach grün und kein Rückschritt: neuen vollen Lauf mit Probe 34 (Preflight läuft jetzt), danach einfrieren; `ketten_probelauf.sh --rev merge-probe-34` (läuft trotz Sperre), `merge_sperre.sh` = 0, Merge main, `bash tools/schnelltest.sh` = 0, `tools/baum_erzeugen.py` + `wissensbaum_luecken.py`, `git pull --no-rebase --no-edit && git push`. Bestand für Tür f04 neu anlegen (Bestand lag 0,27 m daneben) NUR nach Nutzerblick aufs Bild.
4. Pipeline-Maßnahmen offen (Analyse 25.11.): Referenz-Beleg vor Bestand-Tor, Tauschtest je Messstufe, Grenzabstand „UNENTSCHIEDEN“ an weiteren Stellen, Kantenstufe (Präzision 0,13–0,14, F1 0,23), Konvergenz-Zuordnung Galerie/Tor auf Zonen.

## Entscheidungen des Nutzers
- ✓ Merge-Sperre bleibt hart; Probelauf darf trotz Sperre laufen.
- ? „Höhen-Tor ohne Urteil“ → Abnahme rot? (Hauptsitzung: vorerst nicht).
- ? Freigabe zur Rückführung der 4 berichtigten Werte in `modelle/schwabentor-1122/referenz_hand.json` (Hand-Höhen laut Wolke 2,6 % zu tief) – nicht angefasst.
- ? Fotos nötig: Ost/West, Galerie quer zur Wand, Rähm-Höhe.

## Fehler und Lehren dieser Sitzung
- Fehlmeldung: „Kettenmaßstab 3 % zu groß“ aus Regression gegen die Hand ungeprüft weitergegeben; Wolke widerlegte (ERKENNTNISSE). Lehre: Handstand/Vormodell ist kein Maßstab; Höhen gegen Wolke/Laser.
- 1122ze 4,5 h am alten STL (Generator fehlte im Worktree) – Memory `feedback-kettenstart-erste-baustufe-lesen`, Preflight/Bau-Wirkung gebaut.
- Schätzung des Tür-Agenten (CPU-Näherung 0,38 > Bestand 0,26) bestätigte sich im Lauf nicht (0,636). Lehre: Näherungen nicht als Ketten-F1 melden.
- Analyse: 57 h Kettenzeit/4 Tage, 7 bewertbare Läufe, 13 % Nachbar-Rückschritte je Fix, 4 still wirkungslose Tore.
- Nutzer reagierte ungeduldig mit Beleidigungen/Drohungen (früher in der Sitzung); sachlich weitergearbeitet, EndConversation nicht benutzt.

## Wichtige Pfade und Befehle
- Log 1122zh: `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122zh.log`. Kette im Worktree starten: Symlinks `modelle/{schwabentor-1122,schwab_auto,stl,schwabentor-1122_gen.py}` und `daten/*` UND Generator, Job: `JOB_RAM_MB=9000 JOB_GPU_MB=6000 bash tools/job_start.sh kette-schwabentor-null-<id> <log> env RCPARK_BESTAND_EINZELN=1 PYTHONUNBUFFERED=1 /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1122 --ab bauen --dicht-stufe schnell`.
- Agenten-Zweige noch nicht in main (alle in merge-probe-34 gemergt, außer den beiden laufenden). Aufräumen gemergter Worktrees: nie `--force`.
- Scratchpad: `/tmp/claude-29999/-home-oem-git-rc-park/0c18907c-31bd-4f3a-bdd7-3b99654c3ae2/scratchpad/` (Analyse-Skripte, Vergleichsbilder konsolen/, lg/, f1bilder/).

## Vorsicht
- Nur EINE Kette; Teilbau-Jobs mit JOB_RAM_MB/JOB_GPU_MB buchen. Root-Platte ~10 GB frei (Ziel 15, Notgrenze 5) – gemergte Worktrees entfernen, Teilbau-Stände liegen auf /media/oem/rcdaten.
- Fremde uncommittete Dateien (`modelle/kaufhaus_grob3`, `modelle/inhalt/LIZENZ_WERKZEUGE.md` u. a.) nie committen; nur explizites `git add <Datei>`; Löschen nur nach „Ja“; Hook nur Nutzer; nichts unter modelle/<objekt>/ ändern.

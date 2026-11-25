# Übergabe 25.11.2026 13:45
Weiter mit: „weiter“. Vorher Skill `sitzungsbeginn`.

## Auftrag (Nutzerworte)
- HAUPTZIEL (24.11.): Kette baut das Schwabentor automatisch mindestens so gut wie Handmodell schwab_v3, danach zweites Objekt. Plan `modelle/PLAN_HANDMODELL_IN_KETTE.md`.
- „Alle Maße müssen aus Fotos kommen.“ Fehlt eins: mehr Fotos, dann ANNAHME mit Herleitung.
- HART „sichere das hart ab“: nie schlechter als Bestand. Nach jedem Lauf ZUERST `audit/neben_*.jpg` neben `modelle/<obj>/bestand/` und ZIEL_* schicken, dann Zahlen. Rückschritt nie mergen. „Keine Handangriffe, nur Automatik.“
- Deutsch, „mein grosser Meister“, keine breiten Tabellen, Fehlerliste vor Lob, Realitäts-% nur als Schätzung.

## Stand 25.11. 13:45
- main = bab6e65af (nur Doku/Erkenntnisse). Code der Agenten steht NICHT in main: Probe 33 = Zweig `merge-probe-33`, Worktree `/media/oem/scan/rc-park_tmp/merge_probe33` (Symlinks modelle/{schwabentor-1122,schwab_auto,stl} und daten/* auf main; Originale in `/media/oem/rcdaten/tmp/probe33_beiseite/`).
- LÄUFT: Kette `rcpark-kette-schwabentor-null-1122ze` (Start 12:06, Ende geschätzt 16:00-16:30), Log `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122ze.log`, Ende `JOB_ENDE`. Nichts anderes rechnen.
- Ausgangslage: 1122zd 5/11, früher belegt 7/11, Handstand 1120 = 11/11. Abbruchregel P7: zwei Läufe ohne Anstieg = Methode wechseln.

## Nach Laufende (Reihenfolge)
1. `audit/neben_*.jpg` gegen `modelle/schwabentor-1122/bestand/` und ZIEL_*/1120 ansehen, dem Nutzer schicken.
2. Dann x von 11, Fehlerliste, Bestand-Tor, Stufigkeits-Tor, Tauschtest, Schwellen.
3. `ketten_probelauf.sh --rev merge-probe-33` (Job, JOB_RAM_MB=7000 JOB_GPU_MB=3000) = 0, `bash tools/merge_sperre.sh` = 0, Merge, `bash tools/schnelltest.sh` = 0 Fehler, `tools/baum_erzeugen.py` + `wissensbaum_luecken.py`, `git pull --no-rebase --no-edit && git push`, saubere Worktrees entfernen (nie --force).
4. `agent-limap` mergen (nur Messwerkzeug/Doku): Ergebnis nicht einbauen für Gesims/Waagerechte; pytlsd-Kern AGPL = nur Test.

## Offen
- 15 alte + 5 neue Gestalt-Schwellen (Klasse C) ohne Herleitung.
- Fotoaufträge an den Nutzer: Galerie quer zur Wand 5-10 m und 45° von links/rechts ~6 m; Rähm-Höhe; Gesims Ost/Süd; Uhrzeiger.
- Gedrechselter Pfosten (Fuß/Schaft/Kopf), Turmkranz über 11,5 m, Zirkularitäts-Tor breiter.
- Sohlbank unter Druckmindestmaß: Modell zeigt Foto; Entscheidung beim Druck.
- Nachtrag `modelle/LIZENZ_WERKZEUGE.md`: Pi3/Pi3X NC, UniK3D NC-SA, nvdiffrast NC, Metric3D unklar, pytlsd-Kern AGPL, MP-SfM-Zeile falsch (Datei lokal schon verändert, vorher Diff prüfen).
- Aufräumen nach Merge: `/media/oem/rcdaten/tmp/{galerie_kamera,nischen2_agent,turmachse_agent,tuer_widerspruch,pfostentiefe_agent,schwellen_agent,limap_agent}`, Worktrees wt_*.
- Memory-Lehre: Urteil „nicht schlechter“ erst nach Kontaktbogen der Schalter-Varianten; Mittelmaß ersetzt bei gedrechselten Teilen nicht das Profil über die Höhe.

## Vorsicht
- Nur EINE Kette; Root-Platte 14 GB frei (Ziel 15, Notgrenze 5). Fremde uncommittete Dateien (modelle/kaufhaus_grob3 u. a.) nie committen; nur explizites `git add <Datei>`. Löschen nur nach „Ja“. Hook nur Nutzer.

# Übergabe 24.11.2026 21:00
Weiter mit: „weiter" (oder /uebergabe fortsetzen). Vorher Skill `sitzungsbeginn`.

## Auftrag
- Stehend: „Keine Handangriffe, nur Automatik." · „Ich will die Südseite" · parallel/Vollgas · Skill `kette-schleife` (Kette → Bild → je Befund Agent → Merge-Probe → Merge nur bei Schnelltest 0).
- Heute Abend: „Suche weitere Verbesserungen." · „Können wir nicht irgendwas noch verbessern?" · Bildwert-Idee („nur die gewinnbringendsten Bilder in der ersten Stufe").
- Wissen: „Das ist eine Katastrophe" (Wissensbaum unvollständig) · „archivierte … so machen, dass wir immer alles finden" · „Schicke einen Agenten los, der … lernt, wie wir Wissen besser archivieren" · Werkzeug soll nach ~/git/claude-mds („damit alle davon profitieren").
- Nutzer will verstehen, wo wir stehen: je Lauf Zahl je Seite (Formsitz in % der Obergrenze, Höhensitz). Einfach erklären, kein Fachjargon.

## Erledigt und geprüft
- 1122zb (15:31–18:09) fertig: Wandlage f00 −0,357 / f01 −0,288 m aus Fotokanten, Ost-Teil auf Gelände, Quellfilter 1,6 %, 3D V9 https://claude.ai/artifact/ScV8KGvyjJrxxHCAzCM6pi (Logbuch 18:09).
- Merge-Probe 29+30 in main (Schnelltest 0 nach Fixes): Lot-Tore Teil 1 (10° Kippung richtig, Maßstabslücke 12–14 % offen), f02-Fernkameras, Ketten-Probelauf `tools/ketten_probelauf.sh` (Grundstand kprobe_kaufhaus steht, Probelauf p30 rc 0), Formsitz `modelle/FEATURE_FORMSITZ.md`, Uhr-Zonen verworfen, Schlitz-Mindestmaß, Unschärfe-Tor nur bei schwachem Kontrast, Erkennerkasten-Prüfung (f04 3/3 Schlitze), Treppenturm-Kerbe (Suchrand), seiten_luecken-Abbildungsfehler (alle Kameras im Turm → robuste Abbildung + Tor), Wissensbaum 0 Lücken (942 nachgetragen, 24 Unteräste), `tools/wissen_suchen.py`, `tools/wissensbaum_luecken.py`.
- Formsitz Modell 1122zb gegen volle Wolke (relativ zur Obergrenze): Süd 0,61 · West 0,52 · Nord 0,43 · Ost 0,09; med|dz| 0,15/0,20/0,29/3,57 m.
- Bildwert-Stufe 1 (61/625 Bilder) für die Wolke ✗: 1,0 statt 16,8 Mio. Punkte, Formsitz 60–70 % von „alle“, Zufall kaum schlechter (Baum foto-sfm/fotoauswahl.md).
- claude-mds: doku-pflege „Ast voll → Unterast, nie kürzen" (Commit 14f0b95, gepusht).

## Läuft gerade
- Kette 1122zc seit 20:30 `--ab bauen` (Unit rcpark-kette-schwabentor-null-1122zc, Log /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122zc.log, Ende = `JOB_ENDE rc=`), 20:43 bei fassaden_kette; Ende ca. 22:00–22:15. Danach: seiten.jpg + neben_details.jpg ansehen/schicken, Fehlerliste, Formsitz je Seite (audit/konvergenz.jsonl), 3D-HTML V10 gleiche URL (`tools/py tools/modell_3d_html.py ... --wolke ... --farben ...`, nach …_1122z_ende.html kopieren), Logbuchzeile.
- Agenten (Worktrees .claude/worktrees/agent-*): Wissensverwaltung (Doppelungen, Muster, Relevanz-Rangfolge, Nachweis-Test Recall@5, Vorschlag claude-mds unter tools/claude_mds_vorschlag/) · Höhen waagerechter Bauteile angleichen (Höhensitz) · Ost-Grobform 3,6 m klären. Ergebnisse → Merge-Probe 31.
- Merge-Probe 31 (/media/oem/scan/rc-park_tmp/merge_probe31): Höhensitz `tools/hoehensitz.py` + konvergenz-Einbau. Erst nach 1122zc-Ende in main.

## Nächste Schritte
1. Nach JOB_ENDE 1122zc: auswerten wie oben, dem Nutzer Bilder + Zahlen je Seite (einfach erklärt).
2. Agentenzweige in Probe 31 mergen; `bash tools/ketten_probelauf.sh --rev merge-probe-31` als Job (JOB_RAM_MB=7000 JOB_GPU_MB=3000), dann Merge main + `CUDA_VISIBLE_DEVICES= bash tools/schnelltest.sh` = 0, push.
3. Wissens-Vorschlag prüfen (Recall@5 hoch?) → nach ~/git/claude-mds/claude/skills/doku-pflege übernehmen, committen, pushen.
4. Nächste Kette mit Höhensitz; GPU-Pausen für Auflösungs-Leiter (BN: 1000/1200/1600 px, sweetspot.py anpassen).
5. Worktree agent-a250d1c46da5208e8 (Bildwert, Commit 865b8b785) nur als Option mergen oder entfernen (Ergebnis ✗ für Wolke).

## Entscheidungen des Nutzers
- ✓ Probelauf darf rc-park_tmp/ketten_probe/{code,arbeit} jederzeit ersetzen.
- ? Nicht eingecheckte fremde Dateien modelle/archiv/SPEC_FLAECHENMASS.md, STAND_2026-11-10_NACHMITTAG.md, STAND_2026-11-12_VORMITTAG_lang.md: einchecken? (SPEC = Flächenmaß-Vorläufer des Formsitz, 11.11.)
- ? Alte Merge-Probe-Worktrees 11/14/28/29 + rc-park_tmp/flaechen/wt entfernen (Löschen nur nach „Ja").

## Fehler und Lehren dieser Sitzung (Details: modelle/ERKENNTNISSE.md, Baum)
- Vorarbeit Bildwert/Flächenmaß nicht gefunden → Wissenssuche vor jedem Auftrag (CLAUDE.md, Memory feedback-archiv-immer-auffindbar).
- Suche findet noch nicht zuverlässig („Formmaß Fläche" → irrelevant oben) – Rangfolge/Nachweis-Test beauftragt; NICHT als bewiesen melden.
- Probelauf-Auswertung 2× falsch (Endmarke) vor erstem echten Lauf; dann echter Absturz gefunden (zusatzfotos_registrieren None-Format).
- Befund „schiefer Putz" falsch gelesen (war runder Treppenturm) – erst Bauteil prüfen, dann Auftrag.
- Maschine lag 20 min leer – parallele Jobs bei jedem Start mitdenken.

## Vorsicht
- Fremde uncommittete Dateien nie committen (modelle/INDEX.md, LIZENZ_WERKZEUGE.md, PIPELINE_FASSADEN.md, kaufhaus_grob3, martinstor*, archiv/ untracked).
- Nur EINE Kette; Agenten ohne GPU/Rechenläufe während Kette. Worktrees nie --force; .claude/worktrees kein Symlink.

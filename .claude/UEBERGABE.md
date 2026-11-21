# Übergabe 21.11.2026 17:20
Weiter mit: „weiter“ (oder /uebergabe fortsetzen; vorher Skill `sitzungsbeginn`)

## Auftrag
- Nordstern: „möglichst schnell dahin kommen, dass wir aus Daten Modelle erzeugen, möglichst vollautomatisch“ – beliebige Gebäude, von null.
- „Der Handstand darf hier keine Rolle spielen.“ → schwab_v3 nur Vergleich von außen (tools/hand_vergleich.py).
- „löse dieses Bauen-Feature für diesen runden Treppenturm, löse es generell und baue es in die Kette ein“ → erledigt (unten).
- „Hey, das ist doch Müll. Wieso eiern wir so rum? … Ich hätte viel mehr erwartet.“ → nach Wirkung priorisieren (leere Fassaden, Tor, Fenster), nicht an Kleinkram hängen.
- „Kommt es jetzt automatisch aus der Pipeline …? Wir wollen noch die Pipeline automatisieren.“ → keine Handläufe, Beweis nur über Kettenläufe.
- „Was machst du gerade eigentlich? Kommen wir so zum Ziel? Konvergieren wir?“ → Antwort: ja, langsam; Maß = hand_vergleich je Kettenlauf (heute 2/11 → 4/11).
- Letzte Frage: „Martinstor ist abgebrochen, die Daten verloren?“ → nein (siehe Läuft/Nächste Schritte).

## Erledigt und geprüft
- tools/rund_aus_umriss.py: Drehkörper aus Foto-Silhouetten (Bildpyramide, Richtungsgewichte, Embree-Verdeckung); Schwabentor r 1,585 (Hand 1,555), Traufe 11,25 (Hand 11,57); Test test_rund_aus_umriss.py; Kettenstufe bauplan_rund_umriss + Neubau.
- tools/oeffnungen_aus_kanten.py --uebernehmen (64eca2c8b): Wandbild-Form/lichte Maße nur für gebaute Öffnungen in oeffnungen_auto.json; Probe Tor f00 spitz 4,50 (Hand 4,49); Test test_oeffnungen_uebernehmen.py; Kettenstufe bauplan_oeffnungen_wandbild – NOCH NICHT im Kettenlauf gelaufen.
- Merge Nischen-Fenster (05cea3552): nischen_fenster.py, Fenster+Nische mit Bogen; Probe 2/2 Fenster, Sohlbank +0,45 m daneben (Höhenbezug, wie Uhr +0,7).
- Merge leere Fassaden (8016e719a): steine_aus_foto Paar-Probe (falsche Kamera eigen__192 kein Verdecker), West 0 → 314 Steine; tiefe_lokal Bildgröße. Süd/Ost: keine Fotos → Fotoauftrag /media/oem/scan/rc-park_daten/schwabentor-1120/fotoauftrag_schwabentor-1120.json.
- Merge Seiten vereinen (0dfb5d98b): Ursache Martinstor-Ablehnung = dichte Seitenwolken mit Sperrliste (Süd-Helm-Telebilder fehlten); jetzt ohne Sperrliste, alte Wolken werden beiseitegelegt; Tauschprobe vereint 1,9 % (Bild /media/oem/rcdaten/tmp/vereinen_agent/T8/vereinen.jpg). Kettenbeweis fehlt.
- pipeline_objekt SfM-Ziel ohne fremde Bilder; hand_vergleich mit Treppenturm/Überstand/Laterne + Quelle foto/wolke.
- Schnelltest nach allen Merges: 0 Fehler (142 s); alles gepusht (0dfb5d98b).

## Läuft gerade
- Kette `kette-schwabentor-1121n` (--ab bauplan --bis bauplan, gestartet 17:05, VOR Commit 64eca2c8b → ohne Tor-Wandbild-Stufe und ohne nischen_fenster) · Log /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-1121n.log · Prüfen: `grep -a "^\[\|JOB_ENDE\|HANDSTAND" <log> | tail -5` · 17:18 bei bauen_mit_wolkenkoerpern. Danach: hand_vergleich ansehen, audit/seiten.jpg ansehen.
- Dauerdienste gpuwache/platz_waechter/editordraht nicht melden.

## Nächste Schritte
1. Nach Ende 1121n: sofort neuer Kettenlauf mit allen Merges: `JOB_GPU_MB=2500 JOB_RAM_MB=8000 bash tools/job_start.sh kette-schwabentor-1121o /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-1121o.log /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py schwab_auto --ziel schwabentor-1120 --ab fassaden --bis bauplan --dicht-stufe schnell` (fassaden wegen Paar-Probe, bauplan wegen Tor/Nischen/Treppenturm); Erwartung hand_vergleich ≥ 5/11; Bild + Realitäts-% an Nutzer.
2. Martinstor-Kette neu ab sfm (Fix Seiten vereinen): Dummy-Test, dann `gesamtkette.py martinstor_gk3 --ziel martinstor-1120 --ab sfm --dicht-stufe schnell` per job_start (GPU-Buchung; Nord-Wolke ~23 min). Alte Seitenwolken (8,6 GB) werden nach dicht_alt_* gelegt → danach auslagern (tools/auslagern.sh). Wenn durch: Nutzer Bescheid für SSD-Schauen im Laptop.
3. Sohlbank-/Uhr-Höhenversatz (+0,45/+0,7 m) als gemeinsame Ursache suchen (Höhenbezug Wandbild vs. Modell).
4. Fertig gemergte Worktrees entfernen (a0d096…, a5c567…, ab575…, ada8ed…) und .claude/worktrees nach /media/oem/scan verlegen (Root nur 48,8 GB).
5. Galerie/Umgang, Eckquader; Kamera eigen__192 reparieren; Süd/Ost-Fotos beim Nutzer anfragen (Fotoauftrag).
6. Später: Martinstor ganz von null über Nacht; drittes Gebäude.

## Entscheidungen des Nutzers
- ✓ Handstand nie in der Schleife. ✓ Globaler Mapper Standard. ✓ Agenten parallel in Worktrees. ✓ Automatisch über die Kette statt Handläufe.
- ? Neue Fotos Süd/Ost Schwabentor (Fotoauftrag) – Nutzer fragen.

## Fehler und Lehren dieser Sitzung
- Zu viel Handmessen, zu spät in die Kette (Nutzer verärgert) → jede Verbesserung sofort Kettenstufe + Test + Kettenlauf.
- rund_aus_umriss OOM: Ursache trimesh-Raytracing (2,4 M Flächen), nicht Bildgröße – erst messen, dann fixen. Kanten schmaler als Suchschritt → Pyramide.
- Logbuchzeiten zweimal falsch → immer `date`. Hook blockte jpg > 1 MB → .gitignore.
- Martinstor-Ablehnung: Kette rechnete Wolken mit Sperrliste, Handfolge nie → Abweichung Kette/Hand per Tauschprobe finden (modelle/METHODE_SEITEN_SFM.md).
- Lehren in modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md, modelle/ERKENNTNISSE.md.

## Wichtige Pfade und Befehle
- Martinstor-Seitenwolken /media/oem/scan/rc-park_daten/martinstor-1120/pipe/sfm/seiten_modelle/teil{0,1,2}/dicht (erhalten, 8,6 GB).
- Agenten-Proben: Scratchpad probe/ (Nischen), /media/oem/rcdaten/tmp/vereinen_agent/ (T0–T9).

## Vorsicht
- Worktree agent-a1b159488c8983a24 (Zweig ram-je-stufe-1120) nicht anfassen.
- Uncommittete fremde Änderungen (kaufhaus_grob3, martinstor_gk, MASSNACHWEIS) nicht mitcommitten.
- Toshiba-Platte nie anfassen; Buchung RAM/GPU nie von Hand senken; Root-Platz-Tor 5 GB.

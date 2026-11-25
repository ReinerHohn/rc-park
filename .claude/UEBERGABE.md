# Übergabe 25.11.2026 20:55
Weiter mit: „weiter“. Vorher Skill `sitzungsbeginn`.

## Auftrag (Nutzerworte)
- HAUPTZIEL (24.11.): Kette baut das Schwabentor automatisch mindestens so gut wie Handmodell schwab_v3, danach zweites Objekt. Plan `modelle/PLAN_HANDMODELL_IN_KETTE.md`.
- „Alle Maße müssen aus Fotos kommen.“ HART „sichere das hart ab“: nie schlechter als Bestand; nach jedem Lauf ZUERST `audit/neben_*.jpg` neben `modelle/schwabentor-1122/bestand/` + ZIEL_* schicken, dann Zahlen. „Keine Handangriffe, nur Automatik.“
- Deutsch, „mein grosser Meister“, keine breiten Tabellen, Fehlerliste vor Lob.

## Stand 25.11. 20:55
- LÄUFT: Kette `rcpark-kette-schwabentor-null-1122zh` (Start 20:20, `--ab bauen`, Ende ca. 23:00), Log `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122zh.log`. Code = Zweig `merge-probe-33` (fast-forward auf merge-probe-34 = acac467ff), Worktree `/media/oem/scan/rc-park_tmp/merge_probe33` (Symlinks modelle/{schwabentor-1122,schwab_auto,stl,schwabentor-1122_gen.py}, daten/*). Erste Baustufe geprüft: STL 20:23 neu.
- Probe 34 enthält: Matching-Fix, Generator-Abbruch, Teilbau (`tools/bauteil_schleife.py`), Foto-Korrektor (aus), freiraum_tor, ebene_sicht (Nachbarhaus-Fehlprojektion), Vordach-Relief, Höhen-Zirkel-Fix, Massstab-Tor (`massstab_hoehe_tor.py`), Bestand-Lage-Gegenprobe, Dach-Knotenveto (cd693bf62 hatte DOM1-Veto abgeschaltet), Tür f04 (Knick/Gewände/Breite), Konsolen-Konsistenz (6 statt 7).
- main = 9f2209add (nur Doku). Merge-Sperre aktiv (1122zf Rückschritt Tür f04) - erst 1122zh kann sie lösen. Probelauf ist durch die Sperre ebenfalls gesperrt (nicht umgehen).
- Erkenntnis 25.11.: Handstand-Höhen ~2,6 % zu tief (an Wolke gemessen); Kette stimmt. Höhen nur gegen Wolke/Laser werten. Bestand Tür f04 lag 0,27 m zu weit aussen -> Bestand nach gutem Lauf neu anlegen (Nutzer Bild zeigen).

## Nach Laufende
1. `audit/neben_*.jpg` gegen `bestand/` + ZIEL schicken; 3D: `/media/oem/scan/rc-park_daten/schwabentor-1122/schwabentor-1122_3d.html` nach `scratchpad/schwabentor_3d_1122zd.html` kopieren, Artifact gleicher Pfad (Link https://claude.ai/artifact/GVKjQ4MwbbrmLHsx1X9rdz).
2. Ergebnis, Bestand-Tor, Stufigkeit, Tauschtest, Maßstab-/Höhen-Tor, x von 11.
3. `tools/bauteil_schleife.py einfrieren schwabentor-1122 --repo /home/oem/git/rc-park` (aus Worktree merge_probe34) -> Teilbau ab dann.
4. Kein Rückschritt: `ketten_probelauf.sh --rev merge-probe-34` = 0, `merge_sperre.sh` = 0, Merge main, Schnelltest 0, Baum, push; Worktrees aufräumen (nie --force).

## Offen
- Streben-u aus feinem Wandbild 0,13-0,16 m neben Kanten-Konsolen; Kantenstufe F1 nur 0,23 (Präzision 0,14).
- Stufigkeit Uhr/Laterne/Spitze/Gesims; Rähm 0,80 m; Ost/West Fotos fehlen.
- referenz_hand.json (4 berichtigte Werte) nicht anfassen ohne Freigabe; Klasse-B-Schwellen herleiten; LIZENZ_WERKZEUGE-Nachtrag.
- Root-Platte 10 GB (Ziel 15).

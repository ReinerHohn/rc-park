# Plan: Leave-out-Test fuer hlo (Stand 2026-11-08, nicht gestartet - wartet auf Nutzer-Freigabe, BS126)

Ziel: Foto-Diff von hlo vs d03_fix auf Fotos, die die Rekonstruktion NIE gesehen hat.

## Vorhandenes (modelle/kaufhaus_null5/sfm)
- sparse_alle (63 MB, COLMAP-Posen, 94 Kameras), dicht_alle (5,3 GB, run-colmap-geometric/photometric.sh, fused.ply + .vis), bilder_alle.
- Platte /media/oem/scan: 19 GB frei (81 %) -> Kopie von dicht_alle ohne stereo/ noetig, vorher Platz schaffen (tools/auslagern.sh).

## Schritte (je Schritt Skript, alles ueber tools/job_start.sh, JOB_GPU_MB)
1. 10 Testfotos waehlen (verteilte Seiten/Brennweiten, NICHT aus den 22 der Zonenwahl): Liste in modelle/kaufhaus_null5/leaveout_fotos.json festschreiben VOR dem Lauf.
2. sparse_alle ohne diese 10 Bilder (images.bin/points3D bereinigen; Posen der uebrigen unveraendert, kein neues SfM) -> sparse_lo.
3. COLMAP patch_match_stereo + stereo_fusion (GPU) auf sparse_lo -> fused_lo.ply. Schaetzung: ~40 min (Zeitstempel dicht_alle 16:58-17:37). WARNUNG: tools/sfm_dicht.py loescht den Ausgabeordner dicht_<seite> (rmtree) -> Seite "alle_lo" mit --netz alle verwenden, NIE "alle". --fotos = positive Liste (86 Fotos in scratchpad lo_fotos.txt).
4. OpenMVS InterfaceCOLMAP -> ReconstructMesh (Delaunay+GraphCut, Einstellungen wie mvs_default / mvs_d03_pl30 aus Register BR/BS) -> mvs_default_lo, mvs_d03_lo.
5. d03_fix-Reparatur (Saeulen/Fix) auf mvs_d03_lo: Skript FEHLT als Einzelschritt -> erst dokumentieren/reproduzieren (Register BR, fix_wolke_rund.stl).
6. hlo_lo = Unsharp(mvs_default_fix_lo, i2k2 c0.3) oben (z>=6 m) + d03_fix_lo unten.
7. diff_parallel auf den 10 Testfotos (g0.18, g0.05): d03_fix_lo vs hlo_lo; Tor wie bisher. Zusaetzlich 10 weitere Leave-out-Fotos pro Wiederholung, wenn Zeit.

## Risiko
- Schritt 5 nicht als Skript vorhanden; ohne ihn Vergleich nur hlo_lo vs mvs_default_lo / mvs_d03_lo (schwaecher).
- Posen der Testfotos stammen aus SfM mit allen Fotos (leichte Restabhaengigkeit der Kamera, nicht der Geometrie).

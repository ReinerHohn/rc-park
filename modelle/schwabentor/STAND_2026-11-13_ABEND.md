# Schwabentor – Stand 13.11.2026 abends (Uebergabe)

Objekt: Schwabentor Freiburg. Kandidat Torturm = LOD2 DEBWL0010007Tvdv (First 25,8 m). Annahme, nicht bestaetigt.

## Erledigt
- Fotos: 193 eigene (Toshiba) + 10 gueltige Commons; SfM mit 203 Bildern: Hauptmodell 181 registriert, 65.717 Punkte.
- Dichte Wolke (COLMAP, GPU Tiefenkarten, Fusion CPU): `dicht/fused.ply`, 3.304.183 Punkte. Fusion-Fehler behoben (Ausgabe PLY).
- Ausrichtung LOD2 an dichte Wolke (GPU, 471 s): Massstab 0,221, Guete 22 % (zweitbeste 20 %), RMS 0,47 m. Noch keine klare Loesung.
- Hoehe: LOD2 Stadt 25,82 m, LOD2 LGL 28,67 m, Laser DOM1-DGM1 25,5 m, Wikipedia 51 m (nicht gewertet). Band 25,5..28,7 m, nicht gemittelt.
- Generator (modelle/schwabentor_gen.py): Wand 19,2 x 19,9 m, Traufe 10,3 m, First 25,8 m, Walmdach = Annahme. Pruefstand gruen (Hoehe per letzte_option LOD2).
- 3D-Seiten: Modell (https://claude.ai/artifact/9Ld6ZYNG8PfSiYSCzWnpJr), Foto-Abdeckung (https://claude.ai/artifact/2PazcpWaDuiUt6nd2EfJ2U). Abdeckungs-Seite NICHT verlaesslich: Ausrichtung schlecht.
- Werkzeuge neu: tools/pipeline_objekt.py (Ablauf), foto_luecken_plan.py, foto_luecken_3d.py (3D-HTML), kamera_export.py, sfm_lod2_ausrichten.py (--dicht, --kameras, GPU-Grob- und Feinsuche), iphone_sfm.py (GPU-Bundle-Option gesetzt, Python-Bibliothek noch ohne GPU).
- Schlossberg: 20 von 30 Commons geladen (online2/), Rest durch Wikimedia-Drosselung (429) offen.
- Zwei SfM-Lauf mit allen 223 Bildern (sfm_neu): Hauptmodell nur 149 Bilder, Rest in 3 Teilmodelle. Neue Fotos zerlegen die Rekonstruktion.

## Offen (in dieser Reihenfolge)
1. pycolmap mit CUDA bauen (laeuft: `/media/oem/scan/rc-park_daten/schwabentor/pycolmap_build.log`, Ende mit PYCOLMAP_FERTIG). Danach: GPU-Bundle in Python testen, dann iphone_sfm.py-Lauf mit GPU-Mapper.
2. Restliche 10 Schlossberg-Bilder nach der Drosselungspause laden (online_ansichten_holen.py --aus online2 ...).
3. Schlossberg-Bilder so in die Wolke bringen, dass das Hauptmodell nicht zerfaellt (Seitentrennung, Nachbarpaare statt alle-gegen-alle, sfm_netz.py).
4. Visibilitaet der Luecken-Werkzeuge auf GPU (torch) umstellen, Gewinn messen.
5. Feinfit der Ausrichtung: Guete muss deutlich steigen, sonst Lage nicht belastbar. Erst dann Abdeckungs-Seite neu veroeffentlichen.
6. Hoehe des Tores bleibt offen (Quellen widerspruechlich).

## Regeln, die gelten
- Libs mit GPU-Unterstuetzung immer mit GPU bauen und nutzen (memory: feedback-gpu-bauen-immer).
- Keine Wolke als Befund ohne Ausrichtung mit guter Guete.

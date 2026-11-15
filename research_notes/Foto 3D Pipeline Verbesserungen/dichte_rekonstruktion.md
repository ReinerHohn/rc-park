# Dichte Mehrbild-Rekonstruktion schneller und besser auf einer 8-GB-GPU (Stand 15.11.2026)

Ausgangslage (gemessen, nicht neu recherchiert): COLMAP 4.3 dev mit CUDA, ~312 Bilder, `max_image_size` 1600, `geom_consistency = True`, `gpu_index = "0"` (so in `tools/sfm_dicht.py` Zeile 79), 105-125 min PatchMatch, 10-20 min Fusion, ~4,4 Mio. Punkte, ~17 GB Tiefen-/Normalenkarten. Der fruehere Bericht `reports/Pipeline Beschleunigung per Software.md` behandelt die dichte Stufe nur in einem Absatz (Lizenzlage OpenMVS AGPL, 2DGS/PGSR nicht-kommerziell); alles Folgende ist neu.

Kennzeichnung: "UNGEPRUEFT" = aus dem Gedaechtnis oder abgeleitet, nicht in dieser Recherche an einer Quelle bestaetigt. "LOKAL" = im lokalen COLMAP-Quelltext `/media/oem/scan/colmap-build/colmap/src/colmap/mvs/` nachgelesen.

## 1. COLMAP-PatchMatch-Parameter und ihre dokumentierten Kosten/Qualitaets-Abwaegungen

### Takeaway
Die COLMAP-FAQ nennt selbst die Hebel in dieser Reihenfolge: geometrischen Durchlauf abschalten (`geom_consistency false` + `filter true`), Aufloesung senken, weniger Quellbilder, `window_step 2`, weniger `num_iterations`/`num_samples`. Fuer unseren Zweck (Lage-Veto, Hoehen) ist "nur photometrisch + Filter + strengere Fusion" der groesste einzelne Hebel (der geometrische Durchlauf ist bei uns der Hauptblock mit ~27 s/Bild); Zahlen zum Qualitaetsverlust liefert COLMAP aber nicht, das muss an einem Objekt gegen die bestehende Wolke gemessen werden.

### Cited Findings

Offizielle Beschleunigungsliste (FAQ "Speedup dense reconstruction"):
- Geometrische Konsistenz abschalten: `--PatchMatchStereo.geom_consistency false`, dann `--PatchMatchStereo.filter true` einschalten. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- `--PatchMatchStereo.max_image_size` und `--StereoFusion.max_image_size` senken. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Zahl der Quellbilder je Referenzbild senken: in `stereo/patch-match.cfg` z. B. `__auto__, 30` auf `__auto__, 10` (die FAQ nennt 30 als Ausgangswert; bei uns steht 20). `__all__` nimmt alle Bilder; je Referenzbild koennen auch Dateinamen der Quellbilder von Hand aufgelistet werden. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- `--PatchMatchStereo.window_step 2` setzen und `--PatchMatchStereo.window_radius` verkleinern. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- `--PatchMatchStereo.num_iterations` und `--PatchMatchStereo.num_samples` senken. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- `--PatchMatchStereo.cache_size` und `--StereoFusion.cache_size` (in GB) erhoehen beschleunigt (weniger Plattenzugriffe); sehr kleine Werte bremsen und erhoehen die Plattenlast. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Abgebrochene Laeufe werden fortgesetzt, fertige Ansichten uebersprungen. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- `geom_consistency` erhoeht den GPU-Speicherbedarf; bei GPU-Speichermangel `max_image_size` senken oder Quellbildzahl auf 10. — [COLMAP FAQ](https://colmap.github.io/faq.html)

Exakte Optionsnamen, Standardwerte und Kommentare (Quelltext `patch_match_options.h`):
- `max_image_size = -1`; `gpu_index = "-1"`; `depth_min = -1.0f`, `depth_max = -1.0f` ("Depth range in which to randomly sample depth hypotheses"). — [patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)
- `window_radius = 5` ("Half window size to compute NCC photo-consistency cost"). — [patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)
- `window_step = 1`: "For larger values, only every n-th row and column is used and the computation speed thereby increases roughly by a factor of window_step^2. Note that not all combinations of window sizes and steps produce nice results, especially if the step is greater than 2." — [patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)
- `num_samples = 15` ("Number of random samples to draw in Monte Carlo sampling"); `num_iterations = 5` ("Each iteration consists of four sweeps from left to right, top to bottom, and vice versa"). — [patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)
- `geom_consistency = true`, `geom_consistency_regularizer = 0.3f`, `geom_consistency_max_cost = 3.0f` (Vorwaerts-Rueckwaerts-Reprojektionsfehler in Pixel). — [patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)
- `filter = true`, `filter_min_ncc = 0.1f`, `filter_min_triangulation_angle = 3.0f`, `filter_min_num_consistent = 2` ("Minimum number of source images have to be consistent for pixel not to be filtered"), `filter_geom_consistency_max_cost = 1.0f`. — [patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)
- `min_triangulation_angle = 1.0f`, `cache_size = 32.0` (GB), `allow_missing_files = false`, `write_consistency_graph = false`. — [patch_match_options.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match_options.h)

Ablauf im Quelltext (`patch_match.cc`):
- Bei `geom_consistency = true` laeuft zuerst ein kompletter photometrischer Durchlauf ueber alle Bilder mit `geom_consistency = false` und `filter = false`, danach der geometrische Durchlauf mit den Nutzeroptionen; Ausgabedateien heissen `<bild>.photometric.bin` bzw. `<bild>.geometric.bin` in `stereo/depth_maps` und `stereo/normal_maps`. Der geometrische Durchlauf liest die photometrischen Karten als Eingabe. — [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- `__auto__, N`: Kandidaten werden nach Zahl gemeinsamer Sparse-Punkte absteigend sortiert; behalten wird nur, wer beim Triangulationswinkel (75. Perzentil) mindestens `min_triangulation_angle` erreicht; die besten N werden Quellbilder. — [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- Schon vorhandene Ausgabedateien werden uebersprungen (nur Existenzpruefung, keine Inhaltspruefung). — [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- Die Arbeiterzahl ist gleich der Laenge der `gpu_index`-Liste; eine GPU wird nur dann von mehreren Threads genutzt, wenn der Index wiederholt wird (`"0,0"`). — [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- LOKAL (`model.cc`, `ComputeDepthRanges`): ohne gesetztes `depth_min/depth_max` wird je Bild der Tiefenbereich aus den Sparse-Punkten genommen: 1. und 99. Perzentil, danach um `kStretchRatio = 0.25` gestreckt (min x 0,75, max x 1,25). — [model.cc im COLMAP-Repo](https://github.com/colmap/colmap/blob/main/src/colmap/mvs/model.cc)

Mehrere Arbeiter auf einer GPU:
- FAQ: mehrere Threads auf derselben GPU durch wiederholte Indizes, z. B. `--PatchMatchStereo.gpu_index=0,0,1,1,2,3`; Standard ist ein Thread je GPU. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Maintainer (ahojnnes) in Issue 2536: "The algorithm imposes that each row or column of an image uses one cuda thread" - deshalb geringe Auslastung auf grossen GPUs; er schlaegt vor, denselben Index mehrfach zu listen, hat es aber nicht getestet. Der Melder berichtet bei mehreren Prozessen auf derselben A100 "almost no success". — [COLMAP Issue 2536](https://github.com/colmap/colmap/issues/2536)
- Warnung aus demselben Issue: `THREADS_PER_BLOCK` von 32 auf 64/96 zu patchen brachte scheinbar 2-2,8x, das Ergebnis war aber kaputt (`stereo_fusion` fusionierte 0 Punkte). Nicht nachmachen. — [COLMAP Issue 2536](https://github.com/colmap/colmap/issues/2536)

Fusion (`StereoFusionOptions`, `fusion.h` / `fusion.cc`):
- `min_num_pixels = 5` ("Minimum number of fused pixels to produce a point"), `max_num_pixels = 10000`, `max_traversal_depth = 100`, `max_reproj_error = 2.0f`, `max_depth_error = 0.01f` (relativ), `max_normal_error = 10.0f` (Grad), `check_num_images = 50` ("Number of overlapping images to transitively check for fusing points"), `use_cache = false`, `cache_size = 32.0`, `max_image_size = -1`, `num_threads = -1`, `mask_path`, `bounding_box`. — [fusion.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.h)
- Fusion ist mehrfaedig (Zeilenstreifen `kRowStride = 10` auf einem Thread-Pool mit `num_threads`); mit `use_cache = true` bleibt `num_threads` bei 1, die Fusion laeuft dann einfaedig. — [fusion.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.cc)
- Normalenkarten sind Pflicht: ein Bild wird nur genutzt, wenn Bitmap, Tiefenkarte und Normalenkarte vorhanden sind, sonst "Ignoring image ..., because input does not exist". — [fusion.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.cc)
- FAQ: bei zu viel Rauschen in der dichten Wolke `--StereoFusion.min_num_pixels` erhoehen. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- LOKAL (`workspace.cc`): mit `max_image_size > 0` werden Bitmap, Tiefen- und Normalenkarte beim Einlesen verkleinert (`depth_map->Downsize`, `normal_map->Downsize`). — [workspace.cc im COLMAP-Repo](https://github.com/colmap/colmap/blob/main/src/colmap/mvs/workspace.cc)

Groessenordnung Aufloesung:
- Eine MVS-Arbeit (ACMH/ACMM-Umfeld) berichtet fuer COLMAP rund 8 s je Tiefenkarte bei maximaler Bildkante ~800 px und z. B. 506,64 s (volle Aufloesung) gegen 202,02 s (halbe Aufloesung) auf einem Datensatz. (Zahlen stammen aus einem Suchtreffer-Auszug, Originaltabelle nicht gelesen.) — [Xu & Tao, arXiv 1805.07920](https://arxiv.org/pdf/1805.07920)

### Inferences

Priorisierte Massnahmenliste fuer COLMAP selbst (Lizenz COLMAP: BSD, UNGEPRUEFT in dieser Runde). Erwartungen sind Abschaetzungen aus den Formeln/Kommentaren oben, keine Messungen:

1. Nur photometrischer Durchlauf (`geom_consistency = False`, `filter = True`), Fusion mit `--input_type photometric` und zum Ausgleich strenger (`StereoFusion.min_num_pixels` 5 -> 8-10, evtl. `max_reproj_error` 2 -> 1). Erwartung: der geometrische Block (bei uns ~27 s von ~35 s je Bild) entfaellt, also grob 3-4x schneller; zugleich halbiert sich der Plattenbedarf, weil nur ein Kartensatz entsteht. Risiko: mehr Ausreisser auf glatten Putzflaechen/Himmelsraendern; die Fusion prueft aber weiterhin Reprojektion, Tiefe und Normale ueber mehrere Ansichten, was fuer ein Lage-Veto genuegen duerfte. Von der FAQ ausdruecklich als Beschleunigung empfohlen. VRAM sinkt (FAQ: `geom_consistency` kostet GPU-Speicher).
2. `window_step = 2` (bei `window_radius = 5`): Kommentar nennt "roughly window_step^2", also bis ~4x auf den NCC-Anteil; real weniger, weil nicht alles NCC ist. Laut Kommentar sind Schritte bis 2 unkritisch.
3. Quellbilder `__auto__, 20` -> `__auto__, 10`: Kosten je Pixel wachsen etwa linear mit der Quellbildzahl; Erwartung knapp 2x, dazu weniger VRAM. Bei Rundum-Aufnahmen eines Einzelgebaeudes sind 10 gut ueberlappende Quellbilder ueblich ausreichend (FAQ nennt 10 als Zielwert).
4. `max_image_size` 1600 -> 1200: Pixelzahl 56 %, also ~1,8x schneller und ~44 % weniger Platte; Tiefenrauschen steigt etwa proportional zur Pixelgroesse. Fuer Lage-Veto vertretbar, fuer feine Hoehen (Zinnen) pruefen.
5. `num_iterations` 5 -> 3 und `num_samples` 15 -> 10: etwa linear (40 % bzw. ein Teil davon); Qualitaetseffekt ist nirgends beziffert.
6. `depth_min/depth_max`: COLMAP setzt den Bereich schon automatisch je Bild aus den Sparse-Punkten (1./99. Perzentil, +-25 %). Manuelles Setzen bringt daher wenig; ein Tiefenprior (Monokular-Tiefe) haette hier keinen Einstiegspunkt ohne Quelltextaenderung.
7. `gpu_index = "0,0"`: dokumentiert, aber laut Issue 2536 auf einer A100 praktisch ohne Gewinn; auf 8 GB verdoppelt sich der VRAM-Bedarf. Niedrige Prioritaet, hoechstens zusammen mit Punkt 1-4 (kleiner VRAM je Arbeiter) als 10-Bilder-Kurztest.
8. Fusion: `use_cache` auf `false` lassen (sonst einfaedig); bei 22 Kernen und genug RAM ist die Fusion schon parallel. `StereoFusion.max_image_size` kleiner als die Kartenaufloesung (z. B. 1000) reduziert Punktzahl und Zeit ohne neuen PatchMatch-Lauf; `check_num_images` 50 -> 20-30 verringert die Nachbarpruefung (Wirkung unbeziffert). `bounding_box` auf das Gebaeude begrenzt die Ausgabe.

- Kombination 1+2+3 koennte die 105-125 min auf grob 10-20 min druecken (Abschaetzung, nicht gemessen); Reihenfolge der Tests: erst 1 allein gegen die bestehende Wolke vergleichen (Wolke-zu-Wolke-Abstand, Grundriss-Tor), dann 2 und 3 dazu.
- "Geometrischen Durchlauf mit kleinerer Aufloesung" ist in COLMAP nicht als Option vorgesehen. Technisch liest der Arbeitsbereich Karten mit `max_image_size` herunterskaliert ein, sodass "photometrisch 1600, geometrisch 1200" eventuell funktioniert; das ist UNGEPRUEFT und kein dokumentierter Weg. Sauberer ist: alles bei 1200, oder nur photometrisch bei 1600.
- Unsere Messung (geometrisch 3-4x langsamer als photometrisch) ist auffaellig hoch; moegliche Ursachen sind VRAM-Druck auf 8 GB und Platten-I/O (die geometrische Stufe laedt zusaetzlich die Tiefenkarten aller Quellbilder; Platte fast voll). `cache_size` pruefen und waehrend des Laufs `nvidia-smi` und I/O-Wartezeit beobachten.

### Gaps
- Keine Quelle beziffert den Genauigkeitsverlust durch `geom_consistency false`, `window_step 2`, weniger `num_samples`/`num_iterations` oder 10 statt 20 Quellbilder (weder FAQ noch Issues noch Paper). Muss lokal gemessen werden.
- Kein gemessener Wert fuer `gpu_index = "0,0"` auf 8-GB-Karten gefunden.
- COLMAP-4.x-Aenderungen an der dichten Stufe (Release Notes) wurden nicht durchgesehen; ob 4.3 neue MVS-Optionen hat, ist offen.

## 2. Klassisches MVS als Ersatz, das COLMAP-Ausgaben liest (OpenMVS, ACMM/ACMMP, APD-MVS, HPM-MVS, Gipuma, MVE)

### Takeaway
Auf ETH3D (2-cm-F1) liegen die ACM-Nachfolger klar vor COLMAP (COLMAP 73,0; ACMM 80,8; ACMMP 85,9; APD-MVS 87,4; HPM-MVS++ 89,0; DVP-MVS 89,6), der Gewinn ist aber vor allem Vollstaendigkeit auf texturarmen Flaechen; COLMAP gilt weiter als das genaueste/konservativste. Fuer "weniger Zeit bei gleicher Korrektheit" ist das lokal schon installierte OpenMVS 2.4.0 (CUDA-PatchMatch, AGPL) der realistischste Kandidat; belastbare Laufzeitvergleiche gegen COLMAP fand ich nicht.

### Cited Findings
- ETH3D High-Res F1 (2 cm, Test): COLMAP 73,01; ACMM 80,78; ACMP 81,51. — [Xu & Tao, ACMP, arXiv 1912.11744](https://arxiv.org/pdf/1912.11744)
- ETH3D F1 (2 cm) Train/Test: ACMM 78,86/80,78; ACMMP 83,42/85,89; APD-MVS 86,84/87,44; HPM-MVS++ 87,09/89,02; DVP-MVS 88,67/89,60. — [DVP-MVS, arXiv 2412.11578](https://arxiv.org/html/2412.11578)
- Tanks and Temples F1 Intermediate/Advanced: ACMM 57,27/34,02; ACMMP 59,38/37,84; APD-MVS 63,64/39,91; HPM-MVS++ 61,59/39,65; DVP-MVS 64,76/40,23. — [DVP-MVS, arXiv 2412.11578](https://arxiv.org/html/2412.11578)
- Laufzeit/Speicher (ETH3D, Originalaufloesung, 10 Bilder, RTX 3090): ACMM, ACMP, ACMMP haben kuerzere Laufzeiten bei vergleichbarem Speicher; APD-MVS und DVP-MVS sind langsamer; HPM-MVS ist in Laufzeit und Speicher schlechter als DVP-MVS; IterMVS-LS ist am schnellsten, braucht aber uebermaessig Speicher. Konkrete Sekunden/GB stehen nur in einer Abbildung. — [DVP-MVS, arXiv 2412.11578](https://arxiv.org/html/2412.11578)
- ACMM und ACMMP verkleinern alle Bilder um Faktor 2; ACMM rechnet 7, ACMMP 10 Iterationen je Skala; MP-MVS ist 17 % schneller als ACMMP. — [MP-MVS, arXiv 2309.13294](https://arxiv.org/pdf/2309.13294)
- OpenMVS erreicht auf ETH3D die hoechste Vollstaendigkeit, weil es bei der Fusion weniger konsistente Ansichten je Pixel verlangt - dafuer rauschiger/ungenauer; COLMAP hat die hoehere Genauigkeit. — [ACMP, arXiv 1912.11744](https://arxiv.org/pdf/1912.11744)
- ACMMP: braucht CUDA >= 6.0, OpenCV >= 2.4; getestet auf Ubuntu 16.04 mit GTX 1080 Ti (11 GB); Eingabe ueber `colmap2mvsnet_acm.py` aus COLMAP-SfM. Lizenzdatei vorhanden, Typ auf der Seite nicht genannt. — [ACMMP GitHub](https://github.com/GhiXu/ACMMP)
- APD-MVS: MIT-Lizenz; CUDA >= 10.2, OpenCV >= 3.3, Boost >= 1.62; getestet auf Titan RTX (24 GB); Eingabe ueber `colmap2mvsnet.py` mit `scale`-Option fuer beliebige Aufloesung; kein Speicher- oder Laufzeitwert im README. — [APD-MVS GitHub](https://github.com/whoiszzj/APD-MVS)
- OpenMVS: Import ueber `colmap image_undistorter ... --output_type COLMAP`, dann `InterfaceCOLMAP -i dense -o scene.mvs --image-folder dense/images`; `DensifyPointCloud scene.mvs` nutzt standardmaessig PatchMatch; `--postprocess-dmaps` (Standard 4, nur bei CUDA aktiv, "about 3 ms per map"); `--fusion-prior-weight` (Standard 3 "favours completeness", 2 "when the dense point-cloud itself is the final deliverable"); `--fusion-mode 1` schaetzt nur Tiefenkarten ohne Fusion; `--sub-scene-memory` teilt nach Speicherbudget. — [OpenMVS Wiki Usage](https://github.com/cdcseacave/openMVS/wiki/Usage)
- OpenMVS-GPU-Eintrag bei Tanks and Temples nutzt `--resolution-level 0 --number-views 12 --optimize 1`. — [Tanks and Temples, OpenMVS-GPU](https://www.tanksandtemples.org/details/2960)
- OpenMVS steht unter AGPL-3.0. — [OpenMVS COPYRIGHT](https://github.com/cdcseacave/openMVS/blob/master/COPYRIGHT.md)
- LOKAL: OpenMVS x64 v2.4.0 (Build 30.10.2026) liegt unter `/media/oem/scan/openmvs-build/bin/bin/OpenMVS/`; `DensifyPointCloud` startet derzeit nicht ohne Umgebung ("libcudart.so.12: cannot open shared object file"), zwei Laeufe vom 30.10. sind als Logs unter `/media/oem/scan/DensifyPointCloud-*.log` vorhanden. — [OpenMVS Repo](https://github.com/cdcseacave/openMVS)

### Inferences
- Reihenfolge der Alternativen fuer unseren Zweck: (a) OpenMVS 2.4 CUDA (schon gebaut; schreibt eine `.dmap` je Bild statt zweier Kartensaetze; `--resolution-level 1` halbiert die Aufloesung; AGPL ist nur relevant, wenn Software weitergegeben/als Dienst angeboten wird); (b) ACMMP/ACMM (Forschungscode, Faktor-2-Verkleinerung eingebaut, auf 11 GB getestet - bei 1600 px sollte 8 GB reichen, UNGEPRUEFT); (c) APD-MVS (MIT, bester offener Wert unter den dreien, aber langsamer und auf 24 GB entwickelt; 8-GB-Tauglichkeit UNGEPRUEFT).
- Die hoeheren ETH3D-F1-Werte der ACM-Familie kommen ueberwiegend aus Vollstaendigkeit auf texturarmen Flaechen (Planar-Prior). Planar-Prior fuellt Putzflaechen mit Ebenen - fuer ein Lage-Veto nuetzlich, aber es ist eine Annahme im Verfahren; an Gesimsen/Zinnen kann es glaetten. Deshalb gegen Fotokanten pruefen, nicht blind uebernehmen.
- Gipuma und MVE sind aelter als COLMAP-MVS bzw. CPU-lastig und tauchen in keinem der aktuellen Vergleiche mehr vorn auf; hier nicht weiter verfolgt (keine Quelle gelesen, daher keine Aussage zu Zahlen).
- OpenMVS-Optionsnamen `--resolution-level`, `--number-views` sind durch den T&T-Eintrag belegt; weitere mir bekannte Namen (`--max-resolution`, `--min-resolution`, `--number-views-fuse`, `--iters`, `--geometric-iters`, `--estimate-normals`, `--cuda-device`, `--remove-dmaps`, `--filter-point-cloud`) sind UNGEPRUEFT - vor Nutzung mit `DensifyPointCloud --help` lokal bestaetigen.

### Gaps
- Kein unabhaengiger Laufzeitvergleich OpenMVS-CUDA gegen COLMAP-PatchMatch bei gleicher Aufloesung/Bildzahl gefunden; ebenso keine Sekunden-je-Bild-Tabelle fuer ACMMP/APD-MVS/HPM-MVS (nur als Abbildung).
- Lizenz von ACMM/ACMMP nicht bestaetigt (Datei vorhanden, Typ nicht gelesen).
- VRAM-Bedarf von ACMMP/APD-MVS/HPM-MVS bei 1600 px nicht dokumentiert.
- Die beiden lokalen OpenMVS-Logs vom 30.10. enthalten vermutlich eigene Laufzeiten; ich habe sie nicht ausgewertet (Auszug lieferte nur den Kopf).

## 3. Gelerntes MVS und Feed-forward-Tiefe mit bekannten Posen auf 8 GB

### Takeaway
Gelernte Verfahren sind um eine Groessenordnung schneller (ein Vergleich von 2026: 100 Bilder bei 512 px - COLMAP 1326 s, MVSFormer++ 304 s, PatchmatchNet 238 s, MVSAnywhere 100 s, VGGT 61 s), aber derselbe Vergleich stellt fuer die End-to-End-Modelle weiterhin "large reconstruction errors" fest; als alleinige Geometriequelle fuer ein Veto sind sie nicht belegt. Praktikabel mit offener Lizenz und bekannten Posen sind MapAnything (Apache-Checkpoint) und MVSFormer++ (Apache); MVSAnywhere und die grossen DA3-Modelle sind nicht-kommerziell.

### Cited Findings
- Vergleich 2026 (eine NVIDIA A40, Bilder auf 512 px Maximalkante, Mittel aus 3 Laeufen), Laufzeit fuer 100 Bilder, Datensatz "Island": COLMAP 1326,38 s; MVSFormer++ 304,28 s; PatchmatchNet 238,10 s; MVSAnywhere 100,28 s; VGGT 60,79 s; Fast3R 16,47 s. Fuer 50 Bilder: COLMAP 343,85 s; MVSAnywhere 42,07 s; VGGT 28,36 s. — [Comparison of MVS Methods for Photogrammetric 3D Reconstruction, arXiv 2604.10246](https://arxiv.org/html/2604.10246v1)
- Derselbe Vergleich: MVSAnywhere, MVSFormer++ und PatchmatchNet liefern nichts, wenn COLMAP keine Sparse-Rekonstruktion schafft (sie brauchen Posen); Fazit der Autoren: VGGT "best balance between reconstruction quality and runtime efficiency", End-to-End-Methoden "still produce large reconstruction errors"; COLMAP "reliable and geometrically consistent" aber langsam. Genauigkeit wurde nur bis 20 Bilder ausgewertet, COLMAP nur in einer Zeile (Urban, 20 Bilder: RMS 8,55 GSD, Abdeckung 52,75 % gegen VGGT 5,64 / 66,46 %) - Luftbilder bei 512 px, wenig aussagekraeftig fuer Fassaden. Die Tabellen enthalten Unstimmigkeiten (doppelte Zeilenwerte). — [arXiv 2604.10246](https://arxiv.org/html/2604.10246v1)
- MVSAnywhere (CVPR 2025, Niantic): Zero-Shot-MVS mit Posen, ohne festen Tiefenbereich; State of the Art auf dem Robust Multi-View Depth Benchmark. — [MVSAnywhere, arXiv 2503.22430](https://arxiv.org/abs/2503.22430)
- MVSAnywhere-Code: "This code is for non-commercial use"; liest COLMAP (`colmap/sparse/0/cameras.bin`, `images.bin`); Beispielaufloesung `--image_height 480 --image_width 640`; bei GPU-Speichermangel `--fast_cost_volume` weglassen; TSDF-Fusion zu Netzen (`--run_fusion`, `--depth_fuser custom_open3d`); `regsplatfacto` nutzt die Tiefen als Splatting-Regularisierung. Kein VRAM-/Laufzeitwert. — [MVSAnywhere GitHub](https://github.com/nianticlabs/mvsanywhere)
- MVSFormer++: Apache-2.0; Test auf DTU mit `--num_view 5`, `--numdepth 192`, `--max_h 1152 --max_w 1536`; eigene COLMAP-Daten ueber `colmap2mvsnet.py --dense_folder ... --max_d 256 --convert_format`; Bildgroesse muss durch 64 teilbar sein; kein VRAM-/Laufzeitwert im README. — [MVSFormer++ GitHub](https://github.com/maybeLx/MVSFormerPlusPlus)
- MapAnything (Meta): Code Apache 2.0; Checkpoint `facebook/map-anything` CC-BY-NC 4.0, `facebook/map-anything-apache` Apache 2.0; laeuft im "MVS mode" mit COLMAP-Kalibrierung und -Posen als Eingabe (`scripts/demo_inference_on_colmap_outputs.py`, abschaltbar mit `--ignore_calibration_inputs` / `--ignore_pose_inputs`); `memory_efficient_inference=True` und `minibatch_size` (1 = kleinster Speicher); Angabe "up to 2000 views on 140 GB". — [MapAnything GitHub](https://github.com/facebookresearch/map-anything)
- Depth Anything 3: Posen optional als Eingabe ("Pose Cond."); Lizenzen: DA3-GIANT/LARGE/NESTED CC BY-NC 4.0, DA3-BASE (0,12 Mrd.), DA3-SMALL (0,08 Mrd.), DA3METRIC-LARGE und DA3MONO-LARGE Apache 2.0; DA3METRIC: `metric_depth = focal * net_output / 300.`; DA3-Streaming "less than 12GB GPU memory"; Ausgaben glb/npz/ply. — [Depth-Anything-3 GitHub](https://github.com/ByteDance-Seed/Depth-Anything-3)
- DA3 uebertrifft laut Autoren VGGT bei Mehrbild-Geometrie und Posen. — [Depth Anything 3, arXiv 2511.10647](https://arxiv.org/pdf/2511.10647v1)
- Monokulare Tiefe + SfM: "Prior Depth Anything" (ICLR 2026) nimmt duenne gemessene Tiefe inkl. SfM-Punkten und liefert dichte metrische Tiefe; SwiftNDC (2026) korrigiert Mono-/Mehrbild-Tiefen mit einem an Sparse-SfM-Punkten ueberwachten Feld und nennt COLMAP-MVS "several minutes per scene" und schwach auf texturarmen Flaechen. (Beides nur aus Suchauszuegen, Originale nicht gelesen.) — [SwiftNDC, arXiv 2602.22565](https://arxiv.org/html/2602.22565)
- PatchMatch mit Sparse-Keypoints in der Hypothesen-Initialisierung verbessert Ergebnisse in Stadtszenen (KITTI). — [Revisiting PatchMatch MVS for Urban 3D Reconstruction, arXiv 2207.08439](https://arxiv.org/pdf/2207.08439)

### Inferences
- Skaliert man die A40-Zahlen grob auf unsere Lage (312 Bilder, 1600 px ~ 10x mehr Pixel als 512 px), bleibt der relative Abstand: gelernte MVS ~4-13x schneller als COLMAP-Standard. Ob sie bei 1600 px in 8 GB passen, ist fuer MVSFormer++ (Transformer, DTU-Test mit 1152x1536) zweifelhaft und fuer MVSAnywhere unbelegt (Beispiel 640x480). Realistisch sind 8 GB nur bei reduzierter Aufloesung (~512-1024 px) - das ist dann eher "grobes Veto".
- Sinnvollste Rolle fuer Feed-forward-Modelle bei uns: schnelle Gegenprobe/Vorschau (MapAnything-Apache im MVS-Modus mit unseren SfM-Posen, in Minuten) und als unabhaengige Quelle fuer Quellen-Blindheit, nicht als Ersatz der COLMAP-Wolke fuer Hoehen. Punktkarten solcher Modelle sind bei niedriger Aufloesung geglaettet; feine Zinnen/Tuermchen gehen verloren (lokale Erfahrung in `modelle/NICHTS_GEBRACHT.md` mit Teilmengen deutet in dieselbe Richtung).
- Monokulare Tiefe als Start/Bereich fuer COLMAP-PatchMatch: COLMAP hat dafuer keine Option (Bereich kommt je Bild aus Sparse-Punkten, Initialisierung zufaellig); man muesste den Quelltext aendern oder Karten als `*.photometric.bin` unterschieben und nur den geometrischen Durchlauf rechnen (Existenzpruefung ueberspringt vorhandene Dateien). Letzteres ist ein denkbarer Hack: Mono-Tiefe an SfM-Punkte angleichen, als photometrische Karte + Normalen schreiben, dann nur `geom_consistency`-Durchlauf. UNGEPRUEFT, keine Quelle, Ausgang offen; niedrige Prioritaet.

### Gaps
- Kein direkter Genauigkeitsvergleich MVSAnywhere / MapAnything / DA3 (mit Posen) gegen COLMAP-MVS auf ETH3D oder Gebaeudedaten mit Zahlen gefunden.
- VRAM-Zahlen je Bildgroesse fehlen fuer MVSAnywhere, MVSFormer++, DA3 und MapAnything (nur Profil-Abbildungen).
- Lizenzen von VGGT (meines Wissens Forschungs-Checkpoint plus separater kommerzieller Checkpoint), MASt3R/DUSt3R (meines Wissens CC BY-NC-SA), Depth Pro, Metric3D, MoGe, IterMVS, GeoMVSNet, CasMVSNet wurden in dieser Runde nicht nachgeschlagen - UNGEPRUEFT.
- Keine Quelle mit ETH3D-Zahlen fuer "PatchMatch mit Monokular-Tiefenprior als Initialisierung".

## 4. Gaussian-Splatting- und neuronale Oberflaechen als Geometriequelle

### Takeaway
Fuer unseren Zweck nicht empfehlenswert: die besten Splatting-Oberflaechen (PGSR) brauchen 0,5-0,75 h auf einer RTX 4090 und im Mittel ~10 GB VRAM, sind lizenzbeschraenkt und liefern keine nachgewiesen bessere Geometrie als MVS; lokal ist "3DGS/2DGS als Netzquelle" schon als Fehlschlag verbucht.

### Cited Findings
- Tanks and Temples (Trainingsszenen), mittleres F1 und Trainingszeit auf RTX 4090: NeuS 0,38 (>24 h); Geo-NeuS 0,35 (>24 h); Neuralangelo 0,50 (>128 h); SuGaR 0,19 (2 h); 2DGS 0,32 (0,57 h); GOF 0,46 (2 h); PGSR 0,52 (0,75 h). Courthouse (grosses Gebaeude): 2DGS 0,13; GOF 0,28; PGSR 0,20; Neuralangelo 0,28. — [PGSR, arXiv 2406.06521](https://arxiv.org/html/2406.06521v2)
- DTU Chamfer (mm) und Zeit: Neuralangelo 0,61 (>128 h); SuGaR 1,33 (1 h); 2DGS 0,80 (0,32 h); GOF 0,74 (2 h); PGSR 0,52 (0,5 h). — [PGSR, arXiv 2406.06521](https://arxiv.org/html/2406.06521v2)
- PGSR-Grenzen laut Autoren: keine Geometrie in Bereichen mit fehlenden/wenigen Ansichten, keine spiegelnden Flaechen, "some floating points in the scene". — [PGSR, arXiv 2406.06521](https://arxiv.org/html/2406.06521v2)
- PGSR-Spitzen-VRAM auf Tanks and Temples laut NerfBaselines: z. B. 8,54 GB (auditorium), 7,49 GB (family), 14,12 GB (museum), Mittel 10,44 GB bei ~19 min Training. (Aus Suchauszug; GPU-Typ nicht genannt.) — [NerfBaselines, Tanks and Temples](https://nerfbaselines.github.io/tanksandtemples)
- Konkurrenzpapier (CVPR Findings 2026) nennt DTU-Netzwerte 2DGS 47,5 / GOF 92,9 / PGSR 49,2 gegen eigenes 27,8 (CD x 1e-3; Autoren eines Wettbewerbers, mit Vorsicht). — [2D Triangle Splatting, arXiv 2506.18575](https://arxiv.org/pdf/2506.18575)
- Lizenzen: 2DGS Inria nicht-kommerziell, PGSR nur Forschung. — [2DGS LICENSE](https://raw.githubusercontent.com/hbb1/2d-gaussian-splatting/main/LICENSE.md)
- LOKAL: `modelle/NICHTS_GEBRACHT.md` Zeile 6: "Gaussian Splatting 3DGS/2DGS als Netzquelle - kosten_lr -0,06 (vs -0,104) - uneinheitliche Fotos, Ueberanpassung". — [2DGS Repo als Bezug](https://github.com/hbb1/2d-gaussian-splatting)

### Inferences
- Splatting-Verfahren optimieren Fotoaehnlichkeit; bei uneinheitlichen Fotos (Wetter, Handy/Kamera gemischt) erklaeren sie Belichtungsunterschiede mit falscher Geometrie ("Floater") - genau das Gegenteil dessen, was ein Lage-Veto braucht. Die F1-Werte auf T&T-Trainingsszenen (0,2-0,5 fuer Courthouse) sind kein Beleg fuer MVS-Niveau; ein direkter Vergleich mit COLMAP-Fusion im selben Protokoll fehlt.
- 312 Bilder bei 1600 px passen mit PGSR/GOF nicht sicher in 8 GB (Mittel 10,4 GB schon bei kleineren T&T-Aufloesungen); 2DGS waere am ehesten machbar, ist aber am ungenauesten.
- Neuralangelo scheidet wegen >128 h aus.

### Gaps
- Kein Vergleich Splatting-Netz gegen klassische MVS-Punktwolke an Gebaeuden im selben Messprotokoll gefunden.
- VRAM-Zahlen fuer 2DGS/GOF/RaDe-GS nicht belastbar (2DGS-Zeilen der NerfBaselines-Seite im Auszug nicht eindeutig zuordenbar).
- RaDe-GS, gsplat-Netzextraktion und neuere 2026er Verfahren (z. B. MILo, 2D Triangle Splatting) wurden nicht vertieft.

## 5. Ansichtsauswahl fuer MVS (welche Bilder Tiefenkarten bekommen, welche Quellbilder)

### Takeaway
Redundanzabbau ist in der Literatur der Standardhebel (CMVS; Clustering mit berichteten Beschleunigungen bis Faktor 6), und COLMAP erlaubt ihn ohne Zusatzwerkzeug ueber `patch-match.cfg`/`fusion.cfg`. Lokal ist aber belegt, dass eine Foto-Teilmenge fuer SfM/dichte Wolke Tuermchen und Zinnen verlor - deshalb nur die Zahl der Referenzbilder ausduennen, nicht den Bildbestand.

### Cited Findings
- COLMAP-FAQ empfiehlt CMVS, um grosse Szenen zu teilen und redundante Bilder zu entfernen (Standard 100 Bilder je Cluster, z. B. `cmvs pmvs/ 500`; ein sehr grosser Wert entfernt nur redundante Bilder ohne zu clustern). — [COLMAP FAQ](https://colmap.github.io/faq.html)
- CMVS zerlegt SfM-Ausgaben in handhabbare Bildcluster (gedacht fuer PMVS2). — [CMVS, Furukawa](https://www.di.ens.fr/cmvs/)
- Mauro et al. (BMVC 2013): Clustering fuehrt zu "significant speedup factors (up to 6)" der dichten Rekonstruktion bei hoher Qualitaet (Autorenangabe). — [Mauro et al., BMVC 2013](https://bmva-archive.org.uk/bmvc/2013/Papers/paper0120/abstract0120.pdf)
- Mauro et al. (3DV 2014): Ansichtsauswahl als ganzzahliges lineares Programm, liefert eine optimale Kamerateilmenge. — [Mauro et al., 3DV 2014](https://iris.unibs.it/bitstream/11379/459150/1/3dv2014_mauro_joint_selection_clustering.pdf)
- Hornung et al. (CVPR 2008): inkrementelle Bildauswahl mit garantierter Abdeckung eines Proxys, bessere Qualitaet als gleichmaessig verteilte Ansichten. — [Hornung et al., RWTH](https://vci.rwth-aachen.de/publication/0353)
- COLMAP: Quellbilder je Referenzbild koennen in `stereo/patch-match.cfg` namentlich angegeben werden; `__auto__, N` waehlt nach gemeinsamen Sparse-Punkten und Mindest-Triangulationswinkel. — [COLMAP FAQ](https://colmap.github.io/faq.html), [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- Fusion liest die Bildliste aus `stereo/fusion.cfg`. — [fusion.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.cc)
- LOKAL: `modelle/NICHTS_GEBRACHT.md` Zeile 16: "Foto-Teilmenge fuer SfM/dichte Wolke - Tuermchen/Zinnen verloren". — [COLMAP FAQ als Bezug](https://colmap.github.io/faq.html)

### Inferences
- Konkreter Weg in COLMAP: alle 312 Bilder bleiben im Arbeitsbereich (als moegliche Quellbilder), aber nur eine abdeckungsbasierte Teilmenge (z. B. jedes zweite Bild je Kamerabahn, gierig nach "neue Sparse-Punkte abgedeckt" gewaehlt) wird in `patch-match.cfg` als Referenzbild eingetragen und in `fusion.cfg` gelistet. Mit `geom_consistency = false` kostet das linear weniger (halbe Referenzbilder = halbe Zeit und halbe Platte). Mit `geom_consistency = true` braucht der geometrische Durchlauf Tiefenkarten der Quellbilder; dann muessen die Quellbilder aus der Referenzmenge stammen oder `allow_missing_files` gesetzt werden - Verhalten UNGEPRUEFT.
- Die Auswahl muss abdeckungsbasiert sein (jeder Sparse-Punkt in >= k Referenzbildern, k ~ `min_num_pixels`), sonst wiederholt sich der lokale Fehlschlag mit verlorenen Tuermchen: kleine Bauteile sind oft nur in wenigen Nahbildern gross abgebildet. Nahbilder von Details also immer als Referenz behalten.
- Die Fusion verlangt `min_num_pixels = 5` uebereinstimmende Pixel; duennt man Referenzbilder stark aus, muss dieser Wert mitgesenkt werden, was die Ausreisserpruefung schwaecht. Halbierung der Referenzbilder ist daher eine vernuenftige Grenze.

### Gaps
- Keine aktuelle (2024-2026) Arbeit mit Zahlen "x % weniger Tiefenkarten bei gleicher Vollstaendigkeit" gefunden; die gefundenen Quellen sind von 2008-2015 bzw. 2022 (stadtweit).
- Kein fertiges Werkzeug gefunden, das fuer COLMAP eine abdeckungsbasierte Referenzbildliste erzeugt; muesste als kleines eigenes Skript entstehen.

## 6. Plattenbedarf: Normalenkarten, Kompression, Loeschen, strombasierte Fusion

### Takeaway
Die 17 GB erklaeren sich vollstaendig aus zwei unkomprimierten Kartensaetzen (photometrisch + geometrisch), wobei die Normalenkarten drei Viertel ausmachen. Sofort wirksam und ohne Qualitaetsverlust: die `*.photometric.bin` nach dem geometrischen Durchlauf loeschen (halbiert auf ~8,5 GB); Normalenkarten kann man nicht weglassen, weil `stereo_fusion` sie zwingend verlangt.

### Cited Findings
- Je Bild und Durchlauf werden Tiefenkarte und Normalenkarte geschrieben (`depth_maps/<bild>.<photometric|geometric>.bin`, `normal_maps/...`); der Konsistenzgraph nur bei `write_consistency_graph = true` (Standard false). — [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- Der geometrische Durchlauf liest die photometrischen Karten als Eingabe (`workspace_options.input_type = "photometric"`). — [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- Die Fusion ueberspringt Bilder ohne Normalenkarte ("Ignoring image ..., because input does not exist"); Normalen gehen in die Pruefung `max_normal_error` ein. — [fusion.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.cc), [fusion.h](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.h)
- Ohne `use_cache` laedt die Fusion alle Karten vorab in den RAM (`Workspace::Load`); mit `use_cache = true` arbeitet sie ueber einen LRU-Cache der Groesse `cache_size`, dann aber einfaedig. — [fusion.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.cc)
- Vorhandene Ausgabedateien werden beim Neustart uebersprungen (nur Existenzpruefung). — [patch_match.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/patch_match.cc)
- OpenMVS speichert je Bild eine Tiefenkarten-Datei und kann mit `--fusion-mode 1` nur Tiefenkarten schaetzen. — [OpenMVS Wiki Usage](https://github.com/cdcseacave/openMVS/wiki/Usage)

### Inferences
- Eigene Rechnung (Annahme: Karten sind unkomprimierte float32-Felder, Tiefe 1 Kanal, Normale 3 Kanaele; Format UNGEPRUEFT in dieser Runde, passt aber zur Messung): 1600 x 1067 px = 1,71 MP -> Tiefe 6,8 MB + Normale 20,5 MB = 27,3 MB je Bild und Durchlauf; zwei Durchlaeufe x 312 Bilder = 17,0 GB. Das trifft die gemessenen ~17 GB.
- Massnahmen nach Wirkung: (1) `stereo/depth_maps/*.photometric.bin` und `stereo/normal_maps/*.photometric.bin` direkt nach dem geometrischen Durchlauf loeschen: -50 % (~8,5 GB), ohne Folgen fuer `stereo_fusion --input_type geometric`. Nachteil: ein spaeterer Neustart des geometrischen Durchlaufs braucht sie wieder. (2) Nur photometrisch rechnen (Abschnitt 1): es entsteht von vornherein nur ein Satz. (3) `max_image_size` 1200: -44 %. (4) Weniger Referenzbilder (Abschnitt 5): linear. (5) Nach der Fusion alle Karten loeschen und nur `fused.ply` (+ `.vis`, falls Delaunay-Netz gewuenscht) behalten: fuer ein Veto reicht die Wolke; Tiefenkarten sind in ~20 min (nach Tuning) neu rechenbar.
- Kompression: COLMAP hat keine eingebaute Kartenkompression (keine Option in `patch_match_options.h`/`fusion.h`). Ein transparentes komprimierendes Dateisystem (btrfs/ZFS mit zstd) auf `/media/oem/scan` wuerde ohne Codeaenderung wirken; float-Tiefenkarten mit gefilterten Nullbereichen komprimieren gut, photometrische (ungefilterte) schlecht. Zahlen dazu habe ich nicht - UNGEPRUEFT.
- "Strombasierte Fusion" (Karten nie auf Platte) gibt es in COLMAP nicht; der Ablauf ist dateibasiert. Blockweise Verarbeitung (Bildgruppen rechnen, fusionieren, Karten loeschen) ist wegen der Nachbarpruefung ueber `check_num_images` nur mit ueberlappenden Gruppen sauber - Aufwand lohnt bei 312 Bildern nicht, wenn (1)-(4) greifen.

### Gaps
- Kein Beleg (Doku/Issue) zum Binaerformat und zu Kompressionsraten der COLMAP-Karten gelesen; Rechnung oben ist plausibilisiert, nicht zitiert.
- Ob COLMAP 4.x eine Option zum automatischen Loeschen der photometrischen Karten bekommen hat, wurde nicht geprueft.

## 7. Vernetzung (nur kurz): Poisson, Delaunay, TSDF

### Takeaway
Fuer Lage-Veto und Hoehen ist kein Netz noetig; falls doch, ist laut COLMAP-FAQ Delaunay robuster gegen Ausreisser als Poisson, und lokal ist Poisson auf der MVS-Wolke bereits gescheitert.

### Cited Findings
- Poisson braucht eine nahezu ausreisserfreie Wolke und arbeitet schlecht bei Ausreissern oder grossen Loechern; Delaunay ist robuster gegen Ausreisser und skaliert besser, liefert aber weniger glatte Flaechen und arbeitet auf Sparse- oder Dense-Ergebnissen; empfohlen wird ggf. erst Delaunay zum Ausreisserfiltern, dann Poisson. — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Stellschrauben: `--PoissonMeshing.trim`, `--DelaunayMeshing.quality_regularization` (glatter), `--DelaunayMeshing.max_proj_dist` (feiner). — [COLMAP FAQ](https://colmap.github.io/faq.html)
- Die Fusion fuehrt Sichtbarkeiten je Punkt (`fused_points_visibility_`, Schreibfunktion `WritePointsVisibility`), die der Delaunay-Mesher braucht. — [fusion.cc](https://raw.githubusercontent.com/colmap/colmap/main/src/colmap/mvs/fusion.cc)
- MVSAnywhere fusioniert Tiefenkarten per TSDF (Open3D) zu Netzen. — [MVSAnywhere GitHub](https://github.com/nianticlabs/mvsanywhere)
- LOKAL: `modelle/NICHTS_GEBRACHT.md` BS20e/BS20f: Poisson (depth 9-11) auf der MVS-Wolke nicht wasserdicht, Blasen am offenen Boden. — [COLMAP FAQ als Bezug](https://colmap.github.io/faq.html)

### Inferences
- Da die Form aus Fotokanten kommt, kann die Vernetzung in der Kette entfallen; das spart die Netzzeit vollstaendig. Wenn ein Netz als Verdeckungs-/Sichtbarkeitshilfe gebraucht wird, `delaunay_mesher` auf dem Sparse-Modell (Sekunden bis Minuten, braucht keine dichte Stufe) pruefen - Laufzeit UNGEPRUEFT.

### Gaps
- Keine Laufzeitzahlen fuer `delaunay_mesher`/`poisson_mesher` bei ~4 Mio. Punkten recherchiert.

# Direkter Weg Fotos -> Oberflaechennetz -> druckbares 1:87-Modell (Stand November 2026)

Hinweis zur Lesart: "nur Suchtreffer" heisst, die Zahl stammt aus der Zusammenfassung eines Suchergebnisses und wurde nicht in der Originaltabelle nachgelesen. "Selbst gelesen" heisst, Seite oder PDF wurde geoeffnet. Rechnungen auf 1:87 sind eigene Rechnungen und stehen unter Inferences. Nicht wiederholt wird, was in den beiden frueheren Berichten steht (GPS-Tore, PatchMatch-Tuning, LIMAP, Orthofoto-Stapel, RealityScan als zweite Kameraloesung, Mietkarte fuer dichte Wolke).

## 1. Beste Oberflaechenrekonstruktion aus Fotos mit bekannten Kameras (2024-2026)

### Takeaway
Auf gut texturierter Architektur ist klassisches MVS-Meshing (Metashape, sinngemaess OpenMVS/RealityScan) 2026 immer noch gleich genau oder leicht genauer als das beste Splatting-Netz und 36- bis 120-mal schneller; Splatting-Verfahren gewinnen nur bei duennen, organischen oder glatt-runden Formen. Unter den Splatting-/Voxel-Verfahren fuehren PGSR, GGGS, GeoSVR und Nachfolger (F1 um 0,52-0,56 auf Tanks and Temples), aber grosse Gebaeude (Courthouse) bleiben bei allen schwach (F1 0,07-0,24), und fast alle Codes haengen an der nicht-kommerziellen Inria-Lizenz.

### Cited Findings

**Direkter Vergleich an Kulturerbe mit Laserscan als Referenz (wichtigste Quelle, PDF selbst gelesen)**
- Billi et al., ISPRS-Kongress 2026: MILo gegen Metashape 2.0.0-MVS, gleiche Kameras, TLS als Referenz, M3C2 in CloudCompare, Rechner RTX 4090 (24 GB) mit Ryzen 9 7950X, beide in "mittlerer" Netzaufloesung — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)
- Keramikbrunnen mit Architektur (Sarreguemines): Metashape Standardabweichung 0,20 cm und 3,17 % Ausreisser in 4,50 Minuten; MILo 0,30 cm und 8,21 % in 163,34 Minuten (36-fach langsamer). Abweichungen beider Verfahren konzentrieren sich auf geschnitztes Ornament (0,5-1,0 cm) — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)
- Gotische Fassade Strassburger Muenster (Suedportal, Massstabsbalken 15 m): beide Standardabweichung 3,00 cm; Ausreisser Metashape 66,62 %, MILo 68,40 %; Zeit Metashape 5,58 Minuten, MILo 283,71 Minuten (50-fach). Flaechen liegen bei beiden innerhalb +-2,5 cm; Fialen, Seitentuerme, Portalrelief und Rosette sind bei beiden die Problemzonen; MILo hat rote Abweichungen bis +-8 cm im oberen Giebel, Metashape mehr Loecher an den Fialen — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)
- Baum (Tilia): MILo 2,80 cm und 15,18 % Ausreisser gegen Metashape 3,50 cm und 54,87 %; MILo 84,33 Minuten gegen 0,70 Minuten. Bei runden glatten Balustersaeulen hatte Metashape mehr Luecken, MILo war vollstaendiger — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)
- Schlussfolgerung der Autoren: fuer starre, gut texturierte Architektur "traditional MVS approaches remain highly competitive and achieve comparable or slightly better accuracy with markedly superior computational efficiency"; MILo lohnt bei organischer, duenner Geometrie. Einschraenkung: nur drei Datensaetze — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)
- Schulte et al. (ISPRS 2026, UAV-Kulturerbe): MVS genauer als NeRF und 3DGS, Streuung MVS 0,11 m (nur Suchtreffer, Meterbereich, nicht mit Fassadenarbeit vergleichbar) — [ISPRS Archives 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/1371/2026/isprs-archives-XLIX-B2-2026-1371-2026.pdf)
- ISPRS 2026 zur Lagegenauigkeit von Gebaeude-Splats: Gaussians weichen vom Startpunktwolken-Ort ab, besonders vor 15.000 Iterationen, was Floater und geringere Lagegenauigkeit ergibt; 2DGS reduziert Floater auf Kosten der Bildqualitaet (nur Suchtreffer) — [ISPRS Annals 2026](https://isprs-annals.copernicus.org/articles/XI-M-1-2026/31/2026/)

**Benchmark Tanks and Temples (F1, sechs Szenen), Tabelle aus "From Blobs to Spokes" (arXiv 2604.07337, selbst gelesen, erste 100.000 Zeichen)**
- Protokoll "Uniform Sampling", Mittel und Trainingszeit: 2DGS 0,33 (12 min), RaDe-GS 0,35 (12 min), GOF 0,31 (69 min), SOF 0,32 (17 min), MILo 0,34 (150 min), GGGS 0,45 (32 min), PGSR 0,52 (45 min), eigenes Verfahren 0,48 (27 min) — [arXiv 2604.07337](https://arxiv.org/html/2604.07337)
- Protokoll "Virtual Scanning", Mittel: 2DGS 0,38, GOF 0,38, RaDe-GS 0,39, MILo 0,42, PGSR 0,53, GGGS 0,53, eigenes Verfahren 0,53 — [arXiv 2604.07337](https://arxiv.org/html/2604.07337)
- Szene Courthouse (das einzige grosse Gebaeude) ist bei allen schwach: 2DGS 0,13, PGSR 0,24, GOF 0,10, RaDe-GS 0,12, MILo 0,11, GGGS 0,10 (Uniform Sampling). Barn (kleines Gebaeude): PGSR 0,65, GGGS 0,57, 2DGS 0,48, MILo 0,40 — [arXiv 2604.07337](https://arxiv.org/html/2604.07337)
- PGSR-Netze stammen aus TSDF-Fusion und sind laut dieser Quelle nicht wasserdicht; die Autoren beanspruchen fuer ihre Marching-Tetrahedra-Variante "complete, watertight meshes". GPU und Speicher sind nicht angegeben — [arXiv 2604.07337](https://arxiv.org/html/2604.07337)
- Andere Tabelle, gleiche Reihenfolge: PGSR 0,52 (1,2 h), GOF 0,46 (2 h), 2DGS 0,32 (0,57 h), RaDe-GS 0,40 (11,5 min), TriaGS 0,49 (0,8 h) (nur Suchtreffer). Die GOF-Zahl (0,46) widerspricht der obigen (0,31/0,38): unterschiedliche Auswerteprotokolle — [TriaGS arXiv 2512.06269](https://arxiv.org/pdf/2512.06269); abweichend [arXiv 2604.07337](https://arxiv.org/html/2604.07337)
- GeoSVR (NeurIPS 2025, sparse Voxel statt Gaussians): T&T F1 0,56 gegen Neuralangelo 0,50, PGSR 0,52; DTU Chamfer 0,47 gegen PGSR 0,52, 2DGS 0,80; Training rund 68 Minuten auf T&T, RTX 3090 Ti (nur Suchtreffer, aus Sekundaerzusammenfassungen) — [GeoSVR arXiv 2509.18090](https://arxiv.org/pdf/2509.18090)
- GeoSVR-Repo (selbst gelesen): nutzt Depth-Anything-V2 als Tiefenvorgabe (`--lambda_depthanythingv2 0.1`), Netz per TSDF (`mesh_extract/tsdf_mesh.py`, `--voxel_size 0.002`), Netzextraktion braucht rund 40 GB Arbeitsspeicher, nimmt COLMAP-Daten mit `PINHOLE`/`SIMPLE_PINHOLE`; Dateien `LICENSE` und `LICENSE_inria.md` vorhanden, VRAM nicht genannt — [GeoSVR GitHub](https://github.com/Fictionarry/GeoSVR)
- Zeitvergleich aus AmbiSuR (ICML 2026): GOF 24 min, PGSR 45 min, GeoSVR 68 min, MILo+ 131 min (nur Suchtreffer) — [arXiv 2605.12494](https://arxiv.org/pdf/2605.12494)
- SurfSVR (2026) meldet T&T-Mittel F1 0,62 (nur Suchtreffer, andere Szenenauswahl moeglich) — [arXiv 2608.11938](https://arxiv.org/pdf/2608.11938)
- Neuralangelo: T&T-F1 um 0,50, Laufzeit in Vergleichstabellen ">12 h" bis ">128 h" (nur Suchtreffer) — [Neuralangelo arXiv 2306.03092](https://arxiv.org/pdf/2306.03092)
- GS2Mesh: F1 0,37 auf vier T&T-Szenen, rund 1 h; die Autoren schreiben selbst, ihr Verfahren sei auf kleinere Szenen ausgelegt (nur Suchtreffer) — [GS2Mesh arXiv 2404.01810](https://arxiv.org/pdf/2404.01810)
- Klassisch, alter Benchmark: OpenMVG+OpenMVS T&T-Mittel rund 41,7 gegen COLMAP 42,1 (Punktwolken-F-Score der Rangliste, nur Suchtreffer, Tabelle im Treffer verstuemmelt; nicht mit den Netz-F1 oben vergleichbar) — [MVSNet arXiv 1804.02505](https://arxiv.org/pdf/1804.02505)

**Speicher, Bedienung, Lizenz**
- MILo: Experimente auf RTX 4090; Basismodell (0,1-0,5 Mio. Gaussians) rund 10 GB, dichte Variante (2-4 Mio.) bis 17 GB (nur Suchtreffer aus dem Paper) — [MILo arXiv 2506.24096](https://arxiv.org/pdf/2506.24096)
- MILo-Repo (selbst gelesen): Lizenz teils "Gaussian-Splatting License"; `--data_device cpu` senkt GPU-Speicher; Konfigurationen `verylowres` (bis rund 250.000 Delaunay-Knoten, Netz unter 20 MB), `lowres` (rund 500.000, unter 50 MB), `default` (rund 2 Mio.), `highres` (bis 9 Mio.), `veryhighres` (bis 14 Mio.); `--depth_order` nutzt DepthAnythingV2 (`vitl`); Netz per `mesh_extract_sdf.py`; Himmel nicht eigens behandelt — [MILo GitHub](https://github.com/Anttwo/MILo)
- Warnung: `github.com/bransantiago/MILo` ist nicht das offizielle Projekt, Download-Links zeigen auf ein fremdes Zip — nicht laden (Hinweis aus Suchtreffer) — [MILo Projektseite](https://anttwo.github.io/milo)
- gsplat/Nerfstudio: 2DGS ist seit gsplat 1.4 eingebaut, VRAM-Mehrbedarf rund 4 GB, Lizenz Apache 2.0 und damit kommerziell nutzbar (Sekundaerbericht) — [radiancefields.com gsplat 1.4](https://radiancefields.com/nerfstudio-release-gsplat-1-4)
- PGSR: Lizenz im Index als "other" gefuehrt (Text nicht gelesen); Paper nennt ein Belichtungs-Ausgleichsmodell fuer Szenen mit starken Beleuchtungsunterschieden — [PGSR Index](https://awesome.ecosyste.ms/projects/github.com%2Fzju3dv%2Fpgsr), [PGSR arXiv 2406.06521](https://arxiv.org/abs/2406.06521v2)
- RealityScan 2.0 (frueher RealityCapture): frei unter 1 Mio. USD Jahresumsatz, alle Funktionen; darueber 1.250 USD je Platz und Jahr; Version 2.0 bringt KI-Maskierung, Ausrichtungsverbesserungen, Qualitaetsanalyse; gelistet nur fuer Windows — [RealityScan 2.0 News](https://www.realityscan.com/news/realityscan-20-new-release-brings-powerful-new-features-to-a-rebranded-realitycapture), [RealityScan Lizenz](https://www.realityscan.com/license?lang=en-us)
- Mietpreise 24 GB (Stand Maerz-Oktober 2026, schwankend): RTX 4090 bei RunPod 0,34 USD/h (Community) bis 0,69-0,74 USD/h (Secure), bei Vast.ai typisch 0,29-0,50 USD/h; RTX 3090 bei RunPod 0,22 USD/h, Vast.ai ab 0,10-0,18 USD/h; Speicher und Datenverkehr kommen dazu — [Vast.ai Preisfuehrer](https://vast.ai/blog/how-much-does-it-cost-to-rent-a-gpu-in-the-cloud), [computeprices RunPod 3090](https://computeprices.com/providers/runpod/gpus/rtx3090), [deploybase 4090](https://deploybase.ai/articles/rtx-4090-cloud-price)

**Eigene Messungen im Repo (nicht Web, aber einschlaegig)**
- Lokal war ein dichtes OpenMVS-Netz (`mvs_default`) der erste Kandidat, der das parametrische Modell im Foto-Diff schlug (BS72: -0,1060 gegen -0,0855 bei g0.18, 19 von 22 Fotos besser); dieselben Netze liessen sich aber mit trimesh/Open3D/Poisson nicht wasserdicht bekommen (BS20-BS20f); 3DGS/2DGS als Netzquelle war schlechter (kosten_lr -0,06 gegen -0,104) — Quelle: `/home/oem/git/rc-park/modelle/NICHTS_GEBRACHT.md` (Zeilen 6, 41-46, 131)

### Inferences
- Die Genauigkeit ist nicht der Engpass fuer 1:87: 0,2-0,3 cm Streuung an Ornament (Sarreguemines) sind im Modell 0,02-0,03 mm, 3 cm an der Muensterfassade 0,34 mm. Ersteres liegt weit unter jeder Druckaufloesung, letzteres an der Grenze des Sichtbaren. Engpass sind Vollstaendigkeit (Fialen, Zinnen, Dach), Kantenschaerfe, Floater und Wasserdichtheit.
- Kosten je Gebaeude auf Mietkarte (eigene Rechnung aus obigen Zeiten und Preisen): PGSR/GGGS/GeoSVR-Klasse 0,5-1,2 h, also rund 0,2-0,9 USD; MILo 2,7-4,7 h (Billi et al.), also rund 1-3,5 USD. Dazu Einrichtung und Datenupload, die real die meiste Zeit fressen duerften (Vermutung).
- 24 GB schalten frei: MILo dicht (17 GB), PGSR in voller Aufloesung, GeoSVR; auf 8 GB bleiben gsplat-2DGS (rund 4 GB Mehrbedarf laut Sekundaerquelle), MILo `verylowres`/`lowres` mit `--data_device cpu` (ungeprueft, ob das in 8 GB passt) und alles Klassische.
- Der schnellste Qualitaetsgewinn ist vermutlich kein neues neuronales Verfahren, sondern ein klassisches MVS-Netz aus den vorhandenen Kameras (OpenMVS ist lokal gebaut und schlug im Foto-Diff schon das Parametrikmodell; RealityScan frei, aber Windows) plus bessere Reparatur (Abschnitt 3). Das deckt sich mit Billi et al.
- Der fruehere lokale Fehlschlag "Teilmenge der Fotos verlor Tuermchen und Zinnen" passt zum Muster in Strassburg: Fialen und Tuerme sind bei MVS wie bei Splatting die Luecken. Mehr Fotos dieser Zonen (Tele, wie im frueheren Bericht Block C) helfen beiden Verfahren; ein Verfahrenswechsel allein nicht.
- Courthouse-F1 von 0,07-0,24 misst bei 3-5 mm Schwellen einer ganzen Gebaeudeszene; das heisst nicht, dass das Netz unbrauchbar aussieht, aber dass feine Lagegenauigkeit ueber grosse Gebaeude bei Splatting nicht belegt ist.

### Gaps
- Lizenztexte von 2DGS (Original), PGSR, GOF, RaDe-GS, SuGaR, GeoSVR, Neuralangelo wurden nicht gelesen. Aus Vorwissen (unbelegt): alle ausser Neuralangelo bauen auf dem Inria-Code auf (nicht kommerziell, Forschung/Privat erlaubt); Neuralangelo steht unter einer NVIDIA-Quellcodelizenz (nicht kommerziell). Fuer ein Hobbyprojekt ohne Verkauf waere das unkritisch, fuer Verkauf von Druckdateien nicht. Vor Nutzung jeweils `LICENSE.md` lesen.
- VRAM-Zahlen fuer PGSR (frueherer Bericht: im Mittel rund 10 GB), GOF, RaDe-GS, GeoSVR bei 200-600 Bildern voller Aufloesung: nicht gefunden.
- NeuS2, BakedSDF, Instant-NGP-Netze: keine aktuellen Gebaeudezahlen gefunden; in den 2026er Vergleichstabellen tauchen sie nicht mehr auf.
- Kein gleichartiger Vergleich OpenMVS `ReconstructMesh`/`RefineMesh` oder COLMAP-Delaunay gegen Splatting-Netze auf denselben Szenen gefunden; Billi et al. deckt nur Metashape.
- RealityScan-Netzqualitaet gegen Metashape 2026 und Linux-Lauffaehigkeit: nicht belegt.
- Robustheit gegen duenn belegte Daecher und Himmel: fuer kein Verfahren quantitativ belegt (siehe Abschnitt 2).
- Der Rest von arXiv 2604.07337 (ab Zeichen 100.000) und die Originaltabellen von GeoSVR/AmbiSuR/SurfSVR wurden nicht gelesen.

## 2. Vorgaben (Priors) fuer schwache Bereiche: Tiefe/Normalen, LoD2, Himmel, Belichtung

### Takeaway
Monokulare Tiefen- und Normalenvorgaben sind 2025/26 Standardbestandteil der besten Verfahren (GeoSVR und MILo nutzen Depth-Anything-V2), und GS4Buildings zeigt, dass LoD2 als Start und als Tiefen-/Normalenvorgabe Vollstaendigkeit und Genauigkeit deutlich hebt. Belege speziell fuer Daecher, Himmel und duenne Bauteile im Aussenraum sind aber duenn; die meisten Prior-Arbeiten messen Innenraeume.

### Cited Findings
- GS4Buildings (TUM, 3D GeoInfo 2025): startet 2D-Gaussians aus Punkten, die auf dem LoD2-Netz abgetastet und per Mehrbild-Sichtbarkeit gefiltert werden (ohne SfM-Punkte), und nimmt aus dem LoD2 gerenderte Tiefen- und Normalenkarten als Zwang in die 2DGS-Optimierung. Abstract: Vollstaendigkeit +20,5 %, geometrische Genauigkeit +32,8 %; Gebaeude-Modus spart 71,8 % der Primitive (Autorenangaben, Tabellen nicht gelesen) — [GS4Buildings arXiv 2508.07355](https://arxiv.org/abs/2508.07355), Code [GitHub](https://github.com/zqlin0521/GS4Buildings)
- GeoSVR gewichtet Depth-Anything-V2 mit 0,1; zum Himmel nur der Hinweis, `--lambda_scaling_penalty` zu senken, wenn texturlose Hintergruende wie Himmel unwichtig sind — [GeoSVR GitHub](https://github.com/Fictionarry/GeoSVR)
- MILo: Tiefenreihenfolge-Regularisierung `--depth_order` mit DepthAnythingV2-`vitl`, Stufen `default`/`strong`; rekonstruiert ausdruecklich die ganze Szene samt Hintergrund — [MILo GitHub](https://github.com/Anttwo/MILo)
- GaussianRoom: monokulare Normalen in Gaussian- und SDF-Feld, weil der Renderverlust in texturlosen Flaechen zu schwach ist (Innenraum) — [GaussianRoom arXiv 2405.19671](https://arxiv.org/html/2405.19671v2)
- DN-Splatter: Tiefen- und Normalenvorgaben richten Gaussians an Oberflaechen aus, vor allem Innenraum — [DN-Splatter arXiv 2403.17822](https://arxiv.org/html/2403.17822v3)
- GVGS: blockweise affine Kalibrierung der monokularen Tiefe gegen Massstabsmehrdeutigkeit (nur Suchtreffer) — [arXiv 2601.20331](https://arxiv.org/pdf/2601.20331v2)
- MonoGSDF: monokulare Hinweise plus SDF, T&T-F1 0,47 gegen GOF 0,46 und 2DGS 0,30 auf einer Teilmenge (nur Suchtreffer) — [MonoGSDF arXiv 2411.16898](https://arxiv.org/pdf/2411.16898)
- 2DGS reagiert empfindlich auf die Initialisierung der Primitive; eine Folgearbeit schlaegt deshalb Tiefen-/Normalenvorgaben vor (nur Suchtreffer) — [radiancefields.com 2D-SuGaR](https://radiancefields.com/papers/2d-sugar-surface-aware-gaussian-splatting-for-geometrically-accurate-mesh-reconstruction)
- Belichtung: PGSR hat ein Kamera-Belichtungsmodell fuer stark wechselnde Beleuchtung — [PGSR arXiv 2406.06521](https://arxiv.org/abs/2406.06521v2)
- RealityScan 2.0 bringt KI-gestuetzte Maskierung mit (Hintergrund), Details nicht belegt — [RealityScan 2.0 News](https://www.realityscan.com/news/realityscan-20-new-release-brings-powerful-new-features-to-a-rebranded-realitycapture)
- Duenne Fassadenelemente: Previtali et al. (ISPRS 2026) bewerten 3DGS-Fassadenorthofotos gegen Laserscan nach Vollstaendigkeit, Kantentreue und Topologie (nur Suchtreffer, Zahlen nicht gelesen) — [ISPRS Archives 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/451/2026/isprs-archives-XLIX-B2-2026-451-2026.pdf)

### Inferences
- Fuer das Projekt ist GS4Buildings der naheliegendste Prior-Versuch: LoD2 und Kameras liegen vor, und genau die lokal schwachen Zonen (duenn belegte Daecher) werden durch die LoD2-Tiefe gestuetzt. Risiko: LoD2-Daecher sind generalisiert; wo das LoD2 falsch ist (Dachform laut Projektregel aus Fotos, nicht aus LoD2), zieht die Vorgabe die Flaeche zum Falschen. Die Vorgabe duerfte daher nur schwach gewichtet oder nur als Start dienen (Vermutung).
- Der lokal notierte Grund fuer den 2DGS-Fehlschlag ("uneinheitliche Fotos, Ueberanpassung") wird von zwei jetzt verfuegbaren Bausteinen direkt adressiert: Belichtungsmodell je Kamera (PGSR) und Tiefen-/Normalenvorgabe gegen Ueberanpassung (GeoSVR, MILo, GS4Buildings). Ein neuer Versuch waere also nicht bloss eine Wiederholung, muesste aber am Foto-Tor gewinnen.
- Himmel: da kein Verfahren ihn belegt sauber behandelt, bleibt eine Himmelsmaske vor dem Training (Segmentierung) plus Zuschnitt auf die LoD2-Box mit Rand die sichere Loesung (Vermutung, gaengige Praxis, hier nicht belegt).

### Gaps
- StableNormal, Metric3D v2, DSINE in Splatting-/SDF-Pipelines im Aussenraum: keine belastbare Quelle gefunden.
- Kein quantitativer Beleg, dass Priors an duenn fotografierten Daechern oder an Zinnen/Fialen helfen oder schaden (Glaettung duenner Teile ist plausibel, aber unbelegt).
- Himmels- und Floater-Entfernung: keine Vergleichsquelle; Belichtungsausgleich fuer gemischte Quellen (Drohne, Handy, Fremdfotos) nur ueber PGSR-Paper belegt, nicht an Gebaeuden gemessen.
- GS4Buildings: Lizenz laut fruehrem Bericht nicht kommerziell; VRAM und Laufzeit nicht gelesen.

## 3. Vom Rohnetz zum druckbaren Modell

### Takeaway
Die Kette ist ueberall dieselbe: zuschneiden, Hintergrund loeschen, Loecher schliessen, ausduennen, massstaeblich skalieren, Boden plan, aushoehlen mit Ablaufloechern, teilen; der Aufwand steckt in der Reparatur, und Loecher blind zu schliessen verfaelscht die Form. Bei 1:87 liegen die Druckgrenzen (Harz rund 0,1-0,2 mm Praegung, 0,2-0,6 mm Wand; FDM rund 0,4 mm je Bahn) weit ueber der Messgenauigkeit des Netzes, sodass echtes Fassadenrelief unter etwa 1-2 cm ohne Ueberhoehung verschwindet.

### Cited Findings

**Reparatur und Aufbereitung**
- Ein druckbares Netz ist wasserdicht (keine offenen Kanten, keine nicht-mannigfaltigen Flaechen), ohne Selbstdurchdringung, mit einheitlichen Normalen; unbedachtes Loecherschliessen liefert ungenaue Ergebnisse — [ISPRS Annals II-5/W3, 2015](https://isprs-annals.copernicus.org/articles/II-5-W3/97/2015/isprsannals-II-5-W3-97-2015.pdf)
- Sculpteo-Anleitung: Photogrammetrie erzeugt Hintergrundrauschen um das Objekt, das zuerst entfernt wird; danach Oberflaechenfehler mit Meshmixer beheben — [Sculpteo](https://www.sculpteo.com/blog/2015/11/11/scanning-for-3d-printing-using-photogrammetry/)
- Museumsskulpturen: Meshmixer "close cracks", danach automatische Reparatur in Netfabb; kleine innere Loecher bleiben oft unsichtbar zurueck — [Fabbaloo](https://www.fabbaloo.com/2016/03/secrets-of-3d-scanning-museum-sculptures-part-5-fixing-the-models)
- PhotoModeler (historisches Schulhaus): saubere, unten offene bzw. plane Basis ist fuer den Druck wichtig; vor dem Skalieren beschneiden und dezimieren; Druckkosten skalieren meist mit dem Volumen — [PhotoModeler](https://photomodeler.com/?p=667)
- Einseitig erfasste Gebaeudefront: Loecher in Meshmixer schliessen, alles waehlen, extrudieren fuer Wandstaerke (Forenanekdote) — [Reddit r/3DScanning](https://lr.eu.psf.lt/r/3DScanning/comments/1kmf9vf/how_do_i_watertight_the_model_when_i_only_have)
- Blender-Grundschritte: drehen und zentrieren, Unerwuenschtes loeschen, dezimieren; realer Massstab ist Pflicht; Splats haben keine wasserdichte Flaeche fuer den Slicer, es braucht einen Netzexport — [Instructables Mini World](https://www.instructables.com/Mini-World-How-to-Create-a-Scaled-Down-Replica-of-), [KIRI Engine Workflow](https://www.kiriengine.app/blog/photogrammetry-workflow-guide)
- RealityCapture-Nutzer berichten ungewollte Fuellflaechen an Gebaeudemodellen (Thread-Titel "Avoiding Unwanted Filling in 3D Building Models"; Inhalt nicht gelesen) — [Unreal-Forum](https://forums.unrealengine.com/t/avoiding-unwanted-filling-in-3d-building-models/1567219)
- Lokal: trimesh `fill_holes` wirkungslos, Open3D `fill_holes` laesst nicht-mannigfaltige Knoten, Poisson (depth 9-11) blaeht am offenen Boden auf und bleibt nach Dichteschnitt nicht wasserdicht; fTetWild (MPL-2.0) war als naechster Kandidat notiert — Quelle: `/home/oem/git/rc-park/modelle/NICHTS_GEBRACHT.md` (Zeilen 41-46, 54)

**Aushoehlen, Wandstaerke, Mindestmasse**
- PrusaSlicer-Aushoehlen (Harz): Schalendicke mindestens 1 mm; mindestens zwei Ablaufloecher, sonst bleibt ungehaertetes Harz eingeschlossen; fuer duenne Schalen hoehere Aushoehl-Genauigkeit waehlen; bei FDM keine Loecher noetig, Aehnliches leistet Lightning-Infill — [Prusa Hollowing](https://help.prusa3d.com/en/article/hollowing_117285)
- Hohlteile Harz: Xometry empfiehlt rund 2 mm Wand; Drittquelle 1,5-3 mm — [Xometry SLA-Tipps](https://xometry.pro/en/?p=22102), [Wevolver](https://www.wevolver.com/article/sla-3d-printing-design-guidelines-8-essential-tips)
- Harz-Waende: Formlabs gestuetzt mindestens 0,2 mm (duenne Waende quellen im IPA-Bad); Xometry 0,4 mm gestuetzt und 0,6 mm frei; Fast Radius: freie Waende unter 0,6 mm verziehen sich oder brechen; Stratasys konservativ 1,5 mm wegen Stuetzenentfernung — [Formlabs/Toronto MU SLA Design Guide](https://www.torontomu.ca/content/dam/design-technology-lab/services/3d-printing/SLA-Design-Guide.pdf), [Fast Radius](https://www.fastradius.com/sla-design-tips/), [Stratasys Direct](https://info.stratasysdirect.com/rs/626-SBR-192/images/Stereolithography_Design_Guideline_Stratasys_Direct.pdf)
- Harz-Details: Formlabs erhabenes Detail mindestens 0,1 mm, Loecher mindestens 0,5 mm (kleinere laufen zu); Xometry kleinstes Merkmal 0,2 mm, Gravur mindestens 0,5 mm tief und breit; Stratasys 0,25 mm (HD) bis 0,5 mm (SD), Schrift 0,4 mm — [Formlabs/Toronto MU](https://www.torontomu.ca/content/dam/design-technology-lab/services/3d-printing/SLA-Design-Guide.pdf), [Xometry](https://xometry.pro/en/?p=22102), [Stratasys Direct](https://info.stratasysdirect.com/rs/626-SBR-192/images/Stereolithography_Design_Guideline_Stratasys_Direct.pdf)
- FDM: eine Bahn rund 0,4 mm bei Standardduese, praktisch zwei Bahnen rund 0,8 mm (Drittquelle, keine Prusa-Angabe gefunden) — [Hubs duenne Waende](https://www.hubs.com/knowledge-base/dfm-tips-for-3d-printed-parts-with-thin-walls/)
- Prusa zur Modellbahn: grosse Teile wie Gebaeude auf FDM (i3), winzige Details brauchen den Harzdrucker (SL1) — [Prusa-Blog Eisenbahnmodelle II](https://blog.prusa3d.com/de/3d-gedruckte-eisenbahnmodelle-teil-ii-zuege-und-gebaeude_30758/)

**Ueberhoehung von Relief im Modellbau**
- Ein H0-Ziegelwand-Modell ist ausdruecklich nicht massstaeblich: 1 mm breite Fugen, damit es leicht druck- und bemalbar ist und in H0 trotzdem gut aussieht — [STLFinder HO brick wall](https://stlfinder.com/model/ho-scale-brick-wall-YpRPsreU/4334506)
- Forenpraxis: Ziegelwaende mit 0,10 mm Schichthoehe drucken, die Fuge wird dann 0,10 mm; gedruckte Ziegel "kommen meist nicht gut heraus"; Probestuecke mit verschiedenen Fugentiefen sind ueblich — [trains.com Forum](https://forum.trains.com/t/3d-printed-ho-scale-buildings/319940)
- Harz gibt die beste Zeichnung; FDM mit 0,2-mm-Duese verliert Detail gegenueber Harz (Aussage eines Anbieters von 1:87-Ziegelbauten) — [CGTrader Modellbahn-Ziegelbau](https://www.cgtrader.com/3d-print-models/games-toys/other/model-railway-small-external-brick-building)

### Inferences
- Umrechnung auf 1:87 (eigene Rechnung): 0,1 mm Praegung = 8,7 mm real; 0,2 mm = 17 mm; 0,5 mm Gravur/Loch = 44 mm; 0,4 mm FDM-Bahn = 35 mm; 1 mm Harzschale = 87 mm; 2 mm = 174 mm. Echte Moertelfugen (rund 10 mm breit, wenige mm tief), Putzstruktur, flache Quaderfugen und Schindelkanten liegen damit unter der Grenze; Gesimse, Fenstergewaende, Fachwerkbalken (120-200 mm breit, aber oft buendig) und Masswerkstaebe liegen knapp darueber oder nur in der Breite darueber.
- Folge: ein 1:1 skaliertes Scan-Netz druckt an der Fassade fast glatt. Wer Relief sehen will, muss es senkrecht zur Wand ueberhoehen. Die belegte Modellbaupraxis (1 mm Fuge statt 0,11 mm massstaeblich) entspricht rund 9-facher Ueberhoehung in der Breite; fuer Harz genuegen nach den Herstellergrenzen 0,1-0,3 mm Tiefe (Vermutung, per Probedruck klaeren, wie im Forum ueblich).
- Polygonbudget (eigene Rechnung, keine Quelle): ein 40-m-Turm ist in H0 rund 460 mm hoch; bei 0,05 mm Harz-Pixel sind Dreieckskanten unter 0,1 mm nutzlos. Fuer rund 0,25 m2 Modelloberflaeche reichen 1-5 Mio. Dreiecke; MILo `default` (rund 2 Mio. Knoten) oder ein OpenMVS-Netz in dieser Groesse traegt bereits mehr Detail, als der Drucker zeigt. Die lokal erzeugten 11 Mio. Poisson-Flaechen waren ueberdimensioniert.
- Reparaturreihenfolge, die die lokalen Fehlschlaege umgeht (Vermutung aus den Befunden): nicht Loecher im Rohnetz stopfen, sondern (a) auf LoD2-Box plus Rand zuschneiden, (b) Boden durch boolesche Vereinigung mit einer Bodenplatte bzw. Schnitt mit einem Halbraum in manifold3d schliessen, nachdem (c) das Netz ueber eine Volumenmethode (fTetWild oder Voxel-/SDF-Remesh) garantiert mannigfaltig gemacht wurde. Voxel-Remesh bei 0,05-0,1 mm Modellmass verliert nichts, was der Drucker zeigen koennte.
- Aushoehlen und Teilen sind bei einem 460-mm-Turm Pflicht (Harzbauraum, Harzverbrauch, Saugkraefte). Mit dem vorhandenen manifold3d-Generator sind Schnitte und Passstifte sauberer zu setzen als im Slicer (Vermutung).

### Gaps
- PyMeshFix, fTetWild, Instant Meshes, Quad-Remesher, Blender-Voxel-Remesh an Gebaeudescans: keine Vergleichsquelle gefunden; Eignung nur aus Vorwissen. Aus Vorwissen (unbelegt): PyMeshFix schliesst zu einem einzigen wasserdichten Koerper, entfernt dabei aber kleinere getrennte Teile (Gefahr fuer lose Fialen), Lizenz GPL; manifold3d verlangt bereits mannigfaltigen Eingang.
- Keine Herstellerquelle fuer FDM-Mindestmasse mit 0,25-mm-Duese gefunden.
- Keine Quelle mit empfohlener Relieftiefe oder Fugenbreite fuer Harz in 1:87.
- Keine Quelle zu Polygonbudgets fuer Druckdateien dieser Groesse.
- Meshmixer "Make Solid" und Slicer-Schnittwerkzeuge mit Passstiften: nicht recherchiert.

## 4. Hybride Wege: parametrische Basis plus gescanntes Detail, Netz-zu-CAD

### Takeaway
Die Kombination "saubere Flaeche plus Relief als Hoehenkarte" ist in der Bauaufnahme seit Jahren beschrieben (Abstandskarte zur Wandebene als Graustufenbild, Displacement verformt die Ebene wirklich) und passt genau zum vorhandenen Generator; Netz-zu-Flaechen-Werkzeuge (PolyFit, City3D, CGAL KSR) liefern dagegen nur LoD2-artige Koerper und scheitern an Details, fuer die keine Ebene erkannt wird.

### Cited Findings
- Hoehenkarte aus Fassadenwolke: Abstand jedes Punkts zur mittleren Wandebene wird als Graustufenbild gespeichert; der Displacement-Modifier liest die Grauwerte als Versatz und verformt die ebene Flaeche tatsaechlich (anders als Bump-Mapping); der Ausgabemassstab muss fuer die richtige Pixelgroesse festgelegt werden — [ISPRS Archives XXXVIII-5/W16, 2011](https://isprs-archives.copernicus.org/articles/XXXVIII-5-W16/191/2011/isprsarchives-XXXVIII-5-W16-191-2011.pdf)
- Laserscan-Fassade als Versatzkarte: Raster 10 mm, 2878 x 1778 Pixel, 16 Bit Versatz je Pixel — [ISPRS Archives XXXIX-B5, 2012](https://isprs-archives.copernicus.org/articles/XXXIX-B5/285/2012/isprsarchives-XXXIX-B5-285-2012.pdf)
- Warnung zur Tiefenguete aus Bildern: in einem Beispiel aendert ein Pixel Disparitaet die Tiefe um rund 5 cm, die Oberflaeche wird grob (aeltere Quelle, Zuordnung zum Paper laut Suchtreffer unsicher) — [ISPRS-Kongressband](https://WWW.ISPRS.org/proceedings/XXXV/congress/comm3/papers/409.pdf)
- Idee schon 2004: grobes Modell von Hand, Relief automatisch aus Bildern, "suitable for rapid prototyping" (nur Suchtreffer) — [ISPRS-Kongress 2004, TIB](https://goobi.tib.eu/viewer/fulltext/1663685223/984)
- Photogrammetrie und LiDAR werden oft kombiniert; photometrische Verfahren holen feines Relief heraus, das Photogrammetrie allein verfehlt (nur Suchtreffer) — [ISPRS Archives XLVIII-2/W1, 2022](https://isprs-archives.copernicus.org/articles/XLVIII-2-W1-2022/145/2022/isprs-archives-XLVIII-2-W1-2022-145-2022.pdf)
- CGAL Kinetic Surface Reconstruction (CGAL 6.2, nach Bauchet und Lafarge): zerlegt den Raum anhand erkannter Ebenen in konvexe Polyeder und beschriftet sie per Min-Cut als innen/aussen; das Handbuch zeigt selbst den Fehlerfall: wird am Kaminkopf keine Ebene erkannt, bietet die Zerlegung kein passendes Volumen — [CGAL KSR Handbuch](https://doc.cgal.org/latest/Kinetic_surface_reconstruction/)
- PolyFit: Hypothese-und-Auswahl, binaere Auswahl von Flaechenkandidaten aus Ebenenschnitten — [PolyFit](https://3d.bk.tudelft.nl/liangliang/publications/2017/polyfit/polyfit.html)
- City3D: baut auf PolyFit auf, ergaenzt senkrechte Ebenen aus dem Grundriss, zielt auf LoD2 aus Flugzeug-LiDAR — [City3D GitHub](https://github.com/tudelft3d/City3D)
- Kritik aus Folgearbeit (2025): PolyFit und City3D liefern kompakte Modelle, bekommen aber Rechenengpaesse bei komplexen Gebaeuden; City3D (und KSR bei senkrechten Ebenen) haengt am Grundriss, ein fehlerhafter Grundriss schlaegt direkt durch (nur Suchtreffer) — [Points2Model, tandfonline 2025](https://www.tandfonline.com/doi/full/10.1080/17538947.2025.2458682)
- Dachmodell-Auswertung ISPRS 2025: zu starke Vereinfachung kostet die genaue Dachgeometrie (nur Suchtreffer) — [ISPRS Archives XLVIII-G-2025](https://isprs-archives.copernicus.org/articles/XLVIII-G-2025/701/2025/isprs-archives-XLVIII-G-2025-701-2025.pdf)
- Neuere Raumzerlegungs-Arbeit (2026) existiert, Inhalt nicht gelesen — [arXiv 2606.04891](https://arxiv.org/pdf/2606.04891)
- Einsaetze getrennt rekonstruieren lohnt nach Messung: an Brunnen/Skulptur erreicht MVS 0,10-0,20 cm Streuung (Sarreguemines, Detailansichten), an der ganzen Muensterfassade nur 3 cm — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)

### Inferences
- Wo das Netz gewinnt: Skulpturales und Unregelmaessiges (Portalfiguren, Wasserspeier, Baldachine, Kapitelle, Bruchsteinmauerwerk, verformte alte Daecher), dazu Vollstaendigkeit ohne Handarbeit je Bauteil und der "gewachsene" Gesamteindruck. Lokal belegt: das OpenMVS-Netz schlug das Parametrikmodell im Foto-Diff.
- Wo das Parametrikmodell gewinnt: gerade Kanten, plane Waende, rechte Winkel, Wiederholungen (Fenster, Zinnen, Fachwerkraster), garantierte Wasserdichtheit und Wandstaerken, Teilung in Druckteile, gezielte Ueberhoehung einzelner Merkmale, Masshaltigkeit gegen Dokumente, ungesehene Seiten (Kameraluecke). Bei 1:87 ist ausserdem alles Kleine ohnehin unter der Druckgrenze, sodass das Netz seinen Detailvorteil nur bei Formen ueber rund 2-5 cm real ausspielt.
- Der schnellste Weg zu "ueberzeugend und masshaltig" ist daher vermutlich dreistufig: (1) Parametrikkoerper aus Fotokanten als masshaltige, wasserdichte Basis (vorhanden); (2) je Wandflaeche eine Tiefenkarte "MVS-Tiefe minus Wandebene" aus den Orthofoto-Stapeln (im frueheren Bericht als Punkt 10 vorgeschlagen), geglaettet, in der Tiefe ueberhoeht und als Displacement auf die unterteilte Wandflaeche gelegt; (3) wenige Einsaetze (Portal, Erker, Figuren) als getrennt rekonstruierte Nahbereichsnetze aus eigenen Nahfotos, per boolescher Vereinigung in manifold3d eingesetzt. Das verbindet die Kernmethode mit dem, was das Netz besser kann.
- Die Relief-Tiefenkarte hat bei 1-3 cm Fassadenrauschen (Strassburg) nach 1:87 nur 0,1-0,3 mm Rauschen; mit Ueberhoehung wird auch das Rauschen ueberhoeht. Deshalb vor dem Ueberhoehen kantenerhaltend glaetten und Relief nur dort zulassen, wo Fotokanten (Sweep) eine Struktur bestaetigen (Vermutung, vereinbar mit der Projektregel "linienhafte Features nie aus der Wolke").
- Netz-zu-CAD bringt hier wenig: LoD2 liegt schon amtlich vor, und PolyFit/City3D/KSR erzeugen bestenfalls dasselbe Niveau. Der vorhandene Generator mit Fotokanten ist bereits die bessere "Abstraktion". Nutzen haette KSR allenfalls als automatische Gegenprobe fuer Dachflaechen.

### Gaps
- Keine Quelle gefunden, die den Schritt Hoehenkarte -> druckbares Relief mit Ueberhoehung an Gebaeudefassaden praktisch beschreibt (Massstab, Faktor, Glaettung).
- Neuronale CAD-Rekonstruktion 2025-2026 (Netz/Punktwolke -> CAD-Programm) fuer Gebaeude: nichts Belastbares gefunden; nicht gezielt genug gesucht.
- Lizenzen PolyFit, City3D, CGAL KSR nicht gelesen (lokale Notiz BS24: "CGAL KSR/PolyFit (GPL, nur Test)").
- Kein Qualitaetsvergleich KSR gegen PolyFit an fotogrammetrischen (verrauschten) Gebaeudewolken gefunden.

## 5. Was Praktiker tun

### Takeaway
Dokumentierte Praxis ist fast ausschliesslich "Drohne -> Fertigsoftware (Pix4D, RealityCapture, Metashape) -> Blender/Meshmixer -> Druck in grobem Massstab"; die Netzbereinigung ist der groesste Zeitposten. Fuer H0-Gebaeude aus Photogrammetrie wurde kein einziger belastbarer Erfahrungsbericht gefunden; die Modellbahnszene konstruiert Gebaeude von Hand und ueberhoeht Details.

### Cited Findings
- Pix4D-Fallstudie (Vomela): Drohnengebaeude in Pix4Dmapper, Bearbeitung in Blender, Druck auf Stratasys J750, rund 11 cm breit, Export als .obj + .mtl — [Pix4D](https://pix4d.com/blog/photogrammetry-3d-printing-rapid-prototyping)
- Wargaming-Bastler: Drohnenscan in Blender und Meshmixer bereinigt; das habe "wahrscheinlich die meiste Zeit im Projekt" gekostet — [mazikainen Blog 2020](https://mazikainen.blogspot.com/2020/04/using-photogrammetry-and-3d-printing-to.html)
- Instructables "Mini World": verkleinerte Replik eines realen Gebaeudes aus Drohnen-Photogrammetrie; Schritte drehen/zentrieren, loeschen, dezimieren, auf Druckbett und Massstab skalieren — [Instructables](https://www.instructables.com/Mini-World-How-to-Create-a-Scaled-Down-Replica-of-)
- Grober Schnelldruck eines Photogrammetriemodells mit 1,0-mm-Duese und 0,5 mm Schicht (nur Suchtreffer, Quelle im Treffer nicht eindeutig zugeordnet) — [Pixpro 3D Printing](https://www.pix-pro.com/blog/3d-printing)
- Modellbahn: Prusa-Blogserie baut Gebaeude konstruktiv; grosse Teile FDM, feine Teile Harz — [Prusa-Blog](https://blog.prusa3d.com/de/3d-gedruckte-eisenbahnmodelle-teil-ii-zuege-und-gebaeude_30758/)
- Modellbahn-Anbieter konstruieren oft in OO (1:76,2) und lassen H0-Bauer auf 87 % skalieren; fuer kleinere Massstaebe wird Harz empfohlen — [CGTrader Low-Relief-Bau](https://www.cgtrader.com/3d-print-models/games-toys/other/model-railway-low-relief-industrial-building-4-back)
- Forum: Innenstadtgebaeude in H0 werden von Hand konstruiert und mit 0,10 mm Schicht gedruckt; ein Nutzer druckt stattdessen eine Form und giesst Ziegel in Harz — [trains.com Forum](https://forum.trains.com/t/3d-printed-ho-scale-buildings/319940)
- Heritage-Vergleich: Verarbeitungszeit MVS-Netz 0,7-5,6 Minuten je Objekt auf RTX 4090 bei mittlerer Aufloesung (ohne Ausrichtung) — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)

### Inferences
- Dass niemand H0-Gebaeude aus Scans dokumentiert, ist selbst ein Befund: bei 1:87 verschwindet der Scan-Vorteil (Feindetail) unter der Druckgrenze, waehrend die Scan-Nachteile (wellige Waende, weiche Kanten, Loecher) sichtbar bleiben. Scans werden dort gedruckt, wo das Objekt skulptural ist (Statuen, Ruinen, Gelaende) oder der Massstab grob.
- Typische Fehlerbilder aus den Quellen und den lokalen Notizen decken sich: Hintergrundreste, Loecher an Daechern und duennen Teilen, ungewollte Fuellflaechen, nicht-mannigfaltige Stellen, zu grosse Netze.
- Zeit je Gebaeude: keine Quelle nennt Stunden; aus den Berichten folgt nur die Rangfolge Bereinigung > Aufnahme > Rechnen.

### Gaps
- Keine belastbaren Berichte aus Modellbahn-/Architekturmodellbau-Foren zu Photogrammetrie-Gebaeuden in 1:87 oder 1:100 gefunden (deutsche und englische Suche); gezielte Suche in Stummiforum, RMweb, r/modeltrains steht aus.
- Keine Zeitangaben "Stunden je Gebaeude" gefunden.
- Herstelleranleitungen von Agisoft und Formlabs zum Drucken von Scans wurden nicht direkt gelesen (Formlabs-Werte nur ueber die Toronto-MU-Kopie des Leitfadens).

## 6. Qualitaet automatisch beurteilen

### Takeaway
Fuer Netz gegen Referenzgeometrie ist M3C2 in CloudCompare mit Mittel, Standardabweichung und Ausreisseranteil der gelebte Standard (Benchmarks: F1 bei fester Schwelle); fuer Netz gegen Fotos ohne 3D-Referenz sind Silhouetten-IoU und Render-Vergleich belegt, ein Kanten-F-Mass dagegen nicht als Standard — das projekteigene Foto-F1/Foto-Diff ist also eher weiter als die Literatur.

### Cited Findings
- M3C2 gegen TLS mit Mittel, Standardabweichung, Ausreisseranteil und Abweichungskarte; Ausreisser sind Punkte ausserhalb des Distanzbereichs oder ohne Korrespondenz, ein hoher Ausreisseranteil kann daher Luecken statt Messfehler bedeuten — [Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)
- Das Auswerteprotokoll aendert die Rangfolge: dieselben Verfahren liegen bei "Uniform Sampling" und "Virtual Scanning" unterschiedlich (MILo 0,34 gegen 0,42; GOF 0,31 gegen 0,38) — [arXiv 2604.07337](https://arxiv.org/html/2604.07337)
- Silhouetten-IoU: gerenderte Maske gegen annotierte Maske misst Form und Kamera gemeinsam, weil beide stimmen muessen — [Kanazawa et al., arXiv 1803.07549](https://arxiv.org/pdf/1803.07549)
- Ohne Referenz: Normalenkonsistenz als "no reference"-Mass fuer die Netzguete — [Shadow Art Revisited, arXiv 2107.14539](https://arxiv.org/pdf/2107.14539)
- Kulturerbe-Arbeit warnt: Schnittmenge der Masken von Referenz- und Rekonstruktionsbild zeigt den besten Fall und beschoenigt; sie nimmt die Vereinigung der Masken fuer die Bildmetriken (nur Suchtreffer, Zuordnung zum Paper unsicher) — [EvalMVX, arXiv 2602.24065](https://arxiv.org/pdf/2602.24065v2.pdf)
- Es gibt keine Standardmethode fuer die wahrgenommene Qualitaet rekonstruierter Modelle (nur Suchtreffer) — [QoMEX 2025 Kurzbeitrag](https://oa.upm.es/91829/3/QoMEX25__3D_models_quality__Short_Paper_a.pdf)
- Fassaden: Bewertung nach Vollstaendigkeit, Kantentreue und Topologieerhalt gegen Laserscan (Previtali et al., nur Suchtreffer) — [ISPRS Archives 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/451/2026/isprs-archives-XLIX-B2-2026-451-2026.pdf)

### Inferences
- Ein Netzkandidat sollte durch dieselben Tore wie das Parametrikmodell: Foto-F1 (`tools/teil_fotoform.py`), `tools/foto_diff.py`, dazu Silhouetten-IoU je Foto gegen Himmelsmaske (faengt fehlende Zinnen/Fialen und Floater besonders gut, weil beide die Kontur aendern) und M3C2 bzw. Punkt-zu-Flaeche gegen LoD2/DOM1 nur als Lage-Veto. Getrennt auswerten nach Zonen (Wand, Dach, Aufbauten), weil Gesamtmittel die Problemzonen verdecken (Strassburg: Flaechen gut, Fialen schlecht).
- Fuer Bildvergleiche die Vereinigung der Masken verwenden, nicht die Schnittmenge, sonst werden Luecken belohnt.
- Kontrollfotos aus dem Training heraushalten (Holdout); lokal ist bereits notiert, dass der Holdout frueher in SfM/MVS einfloss.
- Zusaetzlich ein Druckbarkeits-Tor ohne Referenz: wasserdicht, eine Zusammenhangskomponente je Druckteil, Mindestwandstaerke, keine Splitter (deckt sich mit `druck.splitter_verwerfen`).

### Gaps
- Kein veroeffentlichtes Kanten-Praezision/Recall-Mass "Netzrender gegen Fotokanten" als Standard gefunden.
- Die Tanks-and-Temples-Rangliste selbst wurde nicht abgerufen; alle Zahlen stammen aus Papertabellen.
- Schwellenwerte, ab wann ein Netz "druckreif" ist, nennt keine Quelle.

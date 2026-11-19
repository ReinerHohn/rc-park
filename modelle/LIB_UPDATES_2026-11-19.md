# Bibliotheken: neue Versionen und Release Notes (Stand 19.11.2026)

Nur gelesen, nichts installiert und nichts geaendert. Quellen: GitHub-API (Commits, PRs, Releases), PyPI-JSON, `CHANGELOG.rst` im eigenen COLMAP-Quellbaum, OpenCV-Wiki-Changelog.
Kennzeichnung: **[belegt]** = steht so in Release Notes, PR-Text oder Commit; **[vermutet]** = eigene Einschaetzung fuer unsere Kette, nicht gemessen.

## Kurzfazit

- Der eigene COLMAP-Bau (ce2b5ab, 30.10.) ist schon neuer als jedes Release (4.2.1 vom 29.09. ist das neueste). Seitdem kamen auf main 33 Commits. Fuer uns zaehlen davon drei: **FlexGlue** (Matcher mit Kovisibilitaets-Wert gegen Doppelgaenger), **kovarianzgewichtete Rotationsmittelung** im globalen Mapper und der **ONNX-Runtime-Umzug**. Der Umzug ist eine Bau-Falle: Ein frischer Bau unseres Stands laedt ONNX Runtime nicht mehr herunter.
- Ceres: seit 07a9526 nur kleine Beschleunigungen der Jet-Rechnung (Autodiff) und Doku. Kein Grund, allein dafuer neu zu bauen.
- kornia 0.9.2 (16.11.): LoFTR in fp16 ist repariert. Damit wird der Halbgenauigkeitsmodus unserer Doppelgaenger-Pruefung erst brauchbar. ALIKED und LightGlue laufen dort ausserdem 8 bis 13 % schneller.
- torch 2.15.0, open3d 0.20.0, pycolmap 4.2.1 und LightGlue main sind schon die neuesten Staende. OpenCV 5.1.0 bringt fuer uns wenig und hat Python-Bruchstellen.

## COLMAP (eigener Bau, git main)

Installiert ist ce2b5ab vom 30.10.2026 (4.3.dev, mit CUDA, CASPAR, ONNX und sm_89). Das neueste Release ist 4.2.1 vom 29.09.2026. Dessen Inhalt und den von 4.2.0 haben wir schon, also auch den Multi-Komponenten-Globalmapper, LoMa, DEGENSAC, analytische Jacobi-Matrizen (laut Changelog inkrementell 1,2- bis 1,55-mal schneller) und den Fix "Restore legacy bundle-adjustment behavior in the global mapper". main stand am 18.11. bei "Mirror ONNX Runtime binaries ... (#5053)".

Neu auf main nach unserem Stand:

1. **FlexGlue-Matcher** ([#4908](https://github.com/colmap/colmap/pull/4908), Folge-PRs #4915, #4949, #4957, #4969; 01. bis 08.11.)
   - [belegt] "FlexGlue also predicts a **covisibility score** for each pair. `--FlexGlueMatching.min_covisibility` rejects all matches of pairs below this score, which suppresses look-alike pairs (doppelgangers) without any ground truth." Voreinstellung 0,5. Ausserdem: "The models stop early on pairs that are confidently not covisible". fp16 ist auf GPUs ab Rechenfaehigkeit 7.0 voreingestellt, die 4060 hat 8.9. Die Voreinstellung `automatic_reconstructor --feature flexglue` nutzt DaD-Keypoints (LOMA_B128-Extraktor).
   - [belegt] #4957: Je ONNX-Sitzung belegt die GPU "~2.2–2.8 GiB", dazu ein "512 MiB GPU dense-feature cache". Mehrere Worker teilen sich jetzt eine Sitzung.
   - Nutzen [vermutet]: Das ist der direkteste Hebel gegen die Seitenverwechslung symmetrischer Tuerme. Doppelgaenger-Paare fallen schon beim Matching heraus, also vor dem Mapper, und es braucht keinen eigenen LoFTR-Klassifikator mehr. Mit 3 bis 3,3 GiB passt das in 8 GB VRAM, aber nur, wenn nicht gleichzeitig SIFT/PatchMatch laeuft. Arbeitet gegen ALIKED+LightGlue nur, wenn man die Keypoints in die DB importiert. Laut PR werden Datenbanken "with keypoints only" auch gematcht, also gehen unsere ALIKED-Keypoints. Guided Matching ist nicht unterstuetzt.
   - Lizenz [belegt, FlexGlue-README]: Code und Matcher-Gewichte stehen unter MIT. Das Rueckgrat ist aber DINOv3 ConvNeXt-B unter der **DINOv3 License (Meta)**, "restricts its use". Unser `LIZENZ_WERKZEUGE.md` fuehrt DINOv3 schon als "eigene Meta-Lizenz (Pflichthinweis, Kuendigungsrecht) - umstaendlich". Nicht nicht-kommerziell, aber vor Verkaufsnutzung den Lizenztext pruefen und den Hinweis mitliefern. Die DaD-Keypoints der LoMa-Voreinstellung haben eine eigene Lizenz, die ich nicht geprueft habe.
   - Empfehlung: **erst testen, in einem eigenen Prefix** (zweiter Bau neben `prefix/`, den Produktivbau nicht anfassen). Testfall: Martinstor/Schwabentor-DB mit bekannten Doppelgaenger-Paaren, Vergleich gegen `tools/doppelgaenger_paare.py`. Ein Quellbau lohnt sich, und anders gibt es das gar nicht, denn in keinem Release und in keinem pycolmap-Rad ist FlexGlue enthalten.

2. **Kovarianzgewichtete Rotationsmittelung** ([#4950](https://github.com/colmap/colmap/pull/4950), [#4951](https://github.com/colmap/colmap/pull/4951), [#4952](https://github.com/colmap/colmap/pull/4952), [#4953](https://github.com/colmap/colmap/pull/4953), [#4823](https://github.com/colmap/colmap/pull/4823); 03. bis 06.11.)
   - [belegt] Schaetzt je Bildpaar die Kovarianz der Relativdrehung aus den Inliern. `RotationAveragingReweighting::COVARIANCE` ist im globalen Mapper verdrahtet, mit den Schaltern `--GlobalMapper.ra_ceres_covariance_sigma_floor_deg` und `--GlobalMapper.ra_ceres_covariance_loss_scale`. "The default reweighting remains `UNIFORM` (`COVARIANCE` is opt-in)". Benoetigt das Ceres-Backend. [#4912](https://github.com/colmap/colmap/pull/4912) vermeidet die doppelte Kovarianzschaetzung bei mehreren Komponenten.
   - Nutzen [vermutet]: Schwache oder falsche Paare (Putz, Doppelgaenger mit wenigen Inliern) ziehen die Rotationsmittelung weniger. Das passt zur laufenden Arbeit in `GLOBALER_MAPPER_STABIL.md` (Kameras zu hoch, GPS-Rest 70 m). Benchmark-Zahlen zur Wirkung habe ich in den PR-Texten nicht gefunden. Laufzeit [vermutet]: eher etwas laenger, weil die Kovarianzen zusaetzlich gerechnet werden, also keine Hilfe gegen die 20+ min.
   - Empfehlung: **erst testen**, im selben Test-Prefix wie FlexGlue, als eine Variante in `tools/global_mapper_lauf.py` / `versuche.jsonl`.

3. **Inkrementeller Mapper, CPU** ([#5006](https://github.com/colmap/colmap/pull/5006), 10.11.): [belegt] Die Sichtbarkeitspyramide wird nur noch bei Zustandswechseln aktualisiert, "CPU perf". Eine Gesamtzahl fuer den Mapper nennt der PR nicht. [vermutet] Kleiner Gewinn, kein GPU-Code. Fuer die Registrierung im inkrementellen Mapper gibt es weiter **keinen GPU-Pfad**, auch keinen offenen PR.

4. **ONNX Runtime 1.32 / Bau-Falle** ([#5053](https://github.com/colmap/colmap/pull/5053), 18.11.)
   - [belegt] "The upstream repository `github.com/microsoft/onnxruntime`, including all of its release archives, now returns 404. Every fresh build with the default `ONNX_ENABLED=ON` / `FETCH_ONNX=ON` fails at configure time". Die Loesung ist ein Mirror im COLMAP-Release `deps-onnxruntime-v1.32.0`, zugleich ein Update von 1.30.0 auf 1.32.0. Unser Quellbaum setzt noch `ONNX_VERSION "1.30.0"` (FindDependencies.cmake:489).
   - Folge: `tools/umgebung/colmap-bauen.sh` scheitert bei einem **frischen** Bau von ce2b5ab (neue Platte, leeres Build-Verzeichnis). Inkrementelle Neubauten in `build-cuda/` gehen weiter, solange das entpackte Archiv dort liegt. [vermutet] Abhilfe: entweder auf main >= #5053 gehen oder die URL im Bauskript auf den COLMAP-Mirror umbiegen. Das gehoert in die Aufgabenliste, denn es betrifft auch das neue Startskript `0-3d-modell.sh`.

5. Sonstiges auf main [belegt]: "Fix default prior_position_loss_scale to sqrt(chi2_95_3dof)" (#4936). Das betrifft GPS-Prioren im Mapper, und wir nutzen Foto-GPS. "Extract ConvertPosePriorsToENU and skip pose priors without position" (#4937). "Report executed RANSAC trials" (#4974). Keine Aenderung an PatchMatch oder Fusion.

Offene PRs, die man beobachten sollte (noch nicht gemergt, also nur Ausblick):
- [#4971](https://github.com/colmap/colmap/pull/4971) "Cusift: MIT-licensed CUDA SIFT extractor and exact GEMM matcher". Eine GPU-Nachbildung des VLFeat-SIFT, kompatibel mit vorhandenen DBs, als Ersatz fuer SiftGPU. [vermutet] Das waere besser als unsere Grenze "SIFT max 1600", sobald es gemergt ist.
- [#4542](https://github.com/colmap/colmap/pull/4542) "Add optional FAISS GPU SIFT matching" (Entwurf): exakt, ohne die Grenze von 32 768 Deskriptoren.
- [#5021](https://github.com/colmap/colmap/pull/5021) "Do not fix the gauge in bundle adjustment" (laut Zhang et al. schnellere Konvergenz bei gleicher Genauigkeit).
- [#4611](https://github.com/colmap/colmap/pull/4611) Caspar-GPU-BA mit OPENCV-Kameramodell. Heute kann Caspar nur PINHOLE/SIMPLE_RADIAL, und im inkrementellen Mapper ist es bei uns gesperrt (UEBERGABE_2026-11-04).
- [#4956](https://github.com/colmap/colmap/pull/4956) behebt einen Ueberlauf in der EXIF-Brennweite. Das ist **nicht** unser Canon-FocalPlaneXResolution-Fehler aus `GLOBALER_MAPPER_STABIL.md`; der bleibt offen.
- Fuer schnellere Fusion (GPU) oder fuer weisse, texturlose Putzflaechen in PatchMatch gibt es weder Commits noch offene PRs. Die MVS-PRs betreffen nur Metal/ROCm und Fehlerbehandlung (#5026, #5033).

## pycolmap

Installiert ist pycolmap-cuda12 4.2.1 (venv-colmap); in `venv-colmap-gpuba` liegt ein eigener 4.3.0.dev0. Das neueste PyPI-Paket ist 4.2.1 vom 29.09.2026, es gibt also nichts Neueres. FlexGlue und Kovarianz-RA sind in pycolmap nur ueber einen eigenen Bau von main zu haben (laut #4908 und #4823 gibt es Python-Bindings). Lizenz: BSD-3. Empfehlung: **ignorieren**, solange kein 4.3-Release kommt. Wenn FlexGlue in Python gebraucht wird, im Test-Prefix mitbauen.

## Ceres (eigener Bau)

Installiert ist 07a9526 vom 19.10.2026 ("Back-substitute on NO_CONVERGENCE in SchurComplementSolver"). Das neueste Release ist 2.2.0; auf main liegen danach bis 05.11. vor allem Doku und CI.
- [belegt] Laufzeitrelevant sind nur die Commits 22./23.10.: "Inline Jet operators and implement compound assignments in-place" (1e13ccd), "Precompute scalar derivatives in Jet elementary functions" (7527837), "Streamline ArraySelector, VariadicEvaluate, and perturbation seeding" (258951b). Ausserdem "Update cuDSS to 1.0.0" (0397a91) und "Document cuDSS discovery and add WITH_CUDSS option" (05d9259).
- [vermutet] COLMAP nutzt seit 4.2.0 analytische Reprojektions-Jacobi-Matrizen, deshalb hilft die schnellere Autodiff im Hauptpfad kaum. Sie betrifft nur Prior-Terme und Rotationsmittelung. cuDSS 1.0.0 haben wir schon (1.0.0.35).
- Empfehlung: **ignorieren** und erst beim naechsten noetigen COLMAP-Neubau mitnehmen. Fuer den Quellbau bleibt git main die richtige Quelle; als apt-Paket gibt es nur das alte 2.x.

## cuDSS / CUDA-Raeder

- cuDSS: installiert 1.0.0.35; das neueste Paket ist nvidia-cudss-cu12/-cu13 1.0.0.35 vom 22.10.2026, also aktuell.
- nvcc: installiert 13.2; das neueste ist nvidia-cuda-nvcc 13.5.37 vom 04.11.2026. Release Notes habe ich nicht gelesen (PyPI fuehrt keine). Der Treiber ist 595.91. [vermutet] 13.5 braucht vielleicht einen neueren Treiber. Ohne konkreten Grund **nicht anfassen**, denn ein Wechsel heisst Ceres und COLMAP komplett neu bauen.
- cuDNN (venv-seg): 9.26 installiert, 9.28.1 ist neu. Das kommt mit torch-Raedern; nicht einzeln aktualisieren, sonst bricht die torch-Paarung.

## LightGlue / ALIKED (cvg/LightGlue)

Installiert ist Commit 5a650c4; die GitHub-Gegenueberstellung mit main ergibt "identical", also aktuell. Lizenz: Code Apache-2.0, ALIKED BSD-3 (schon geprueft). Empfehlung: nichts tun.

## kornia

Installiert ist 0.9.0; das neueste ist **0.9.2 vom 16.11.2026** (0.9.1 vom 13.11.). Quelle: [Release v0.9.2](https://github.com/kornia/kornia/releases/tag/v0.9.2), [v0.9.1](https://github.com/kornia/kornia/releases/tag/v0.9.1).
- [belegt] "`LoFTR` in float16 no longer loses its attention outputs to overflow; it now finds about as many matches as float32. (#6786)". Ausserdem "`LightGlueMatcher` / `LightGlue`: matching is 2–13 % faster with ALIKED, DISK and XFeat features" und "`ALIKED`: 8–11 % faster on CUDA" (gemessen auf RTX 4090). Aus 0.9.1: "LightGlue cross-attention ... use `scaled_dot_product_attention` on every device" und 192 Fehlerkorrekturen. Die Anforderungen sind gleich wie bei 0.9.0.
- Nutzen [vermutet]: `tools/doppelgaenger_paare.py` hat schon den Schalter `halb` (autocast fp16, Zeile 100). Vor 0.9.2 lieferte LoFTR damit zu wenige Zuordnungen, jetzt sollte fp16 etwa die doppelte Geschwindigkeit bei weniger VRAM bringen. Die Beschleunigung von ALIKED/LightGlue betrifft uns nur, soweit wir die kornia-Klassen nutzen. Unser Matching laeuft ueber das cvg-Paket `lightglue`, nicht ueber kornia.
- Risiko [belegt]: Eine Verhaltensaenderung betrifft nur `Boxes` (ValueError bei gemischten Listen); das nutzen wir nicht.
- Empfehlung: **jetzt aktualisieren** (pip in venv-seg, nur kornia, Lizenz Apache-2.0 unveraendert). Danach Schnelltest und eine Doppelgaenger-Stichprobe mit `halb` gegen fp32 vergleichen, bevor `halb` Standard wird. Ein Quellbau lohnt nicht, es ist reines Python.

## torch / torchvision / triton

Installiert: torch 2.15.0 vom 28.10., torchvision 0.29.2, triton 3.9.0. Das sind auch die neuesten Versionen. Nichts zu tun.

## OpenCV

Installiert: opencv-python(-headless) 5.0.0.93; das neueste ist **5.1.0 vom 06.11.2026** (Rad 5.1.0.95 vom 17.11.). Quelle: [OpenCV Change Logs, version:5.1.0](https://github.com/opencv/opencv/wiki/OpenCV-Change-Logs).
- [belegt] Fuer uns allenfalls: "OpenCL SIFT for UMat input, up to 1.87x over CPU at 1080p" (#29450), vektorisiertes float32-bilineares `warpAffine`/`remap` fuer mehr als 4 Kanaele (#30650), neuer Detektor `cv::XFeat` (#29361), Schur-Kalibrierloeser deterministisch und 1,45-mal schneller (#30175). Fuer PnP, USAC, Essential Matrix oder BA gibt es keine Eintraege.
- Risiko [belegt, Migration notes]: Python-int64-Arrays werden zu CV_64S statt abgeschnitten (#29594). Ein Mat mit Laenge-0-Dimension ergibt ein leeres Array statt None (#29524). 32-Bit-Integer-Addition saettigt (#29426). Die klassische DNN-Engine ist entfernt. Das kann in den Wandbild-/Entzerrwerkzeugen still Verhalten aendern.
- Empfehlung: **ignorieren**, oder hoechstens in einer Test-venv mit `tools/regression.py` pruefen. Unsere Rechenlast laeuft nicht ueber OpenCV-SIFT, und die Python-Pip-Raeder haben ohnehin kein CUDA. Ein Quellbau mit CUDA lohnt sich [vermutet] nicht, weil Entzerren und Warps auf torch/kornia schneller gehen.

## open3d / trimesh / manifold3d

- open3d: installiert 0.20.0 (venv-o3d, venv-mesh); das ist auch die neueste Version (16.09.). Nichts zu tun.
- trimesh: installiert 5.2.0; das neueste ist 5.2.1 vom 12.11. (Patch, Notes nicht gelesen). Empfehlung: ignorieren bis zum naechsten venv-Neubau.
- manifold3d: installiert 3.5.4; das neueste ist 3.5.5 vom 13.11. (Patch, Notes nicht gelesen). Dasselbe gilt hier; der Generator (rcpark) laeuft stabil, also nicht ohne Grund anfassen.

## faiss / onnxruntime (Python)

- faiss: wird in `tools/` nirgends importiert. faiss-cpu 1.16.0 (10.11.) und faiss-gpu-cu12 1.14.1 sind fuer uns derzeit irrelevant. Interessant wird faiss erst ueber COLMAP-PR #4542 (C++, GPU-SIFT-Matching). Lizenz MIT.
- onnxruntime (Python): in keinem Werkzeug importiert. onnxruntime-gpu 1.32.0 (13.11.) ist nur ueber COLMAP relevant, siehe #5053. Hinweis [belegt, #5053]: Das Microsoft-Repository auf GitHub ist nicht mehr erreichbar; Release Notes zu 1.32 konnte ich deshalb dort nicht lesen.

## Rest (nur kurz, nichts Relevantes gefunden)

numpy 2.5.4 -> 2.5.5 (Patch). transformers 5.22.1 -> 5.23.0. scipy 1.18.1, shapely 2.2.0, pillow 13.0.0 und scikit-image 0.26.0 sind aktuell. gsplat 1.5.3 ist aktuell (letztes Release 07/2025). Die Release Notes dieser Pakete habe ich nicht gelesen, weil sie keine der Schwachstellen (Putzloecher, Doppelgaenger, Mapper-Zeit, CPU-Fusion, Registrierung ohne GPU) beruehren.

## Was gegen unsere Schwachstellen hilft (Zusammenfassung)

- Doppelgaenger/Seitenverwechslung: COLMAP-FlexGlue `min_covisibility` [belegt: Funktion; Wirkung bei uns vermutet] sowie kornia 0.9.2 fuer schnellere fp16-LoFTR-Pruefung [belegt: Fix; Tempo vermutet].
- Globaler Mapper stabil: Kovarianz-RA (opt-in) [belegt: Funktion; Wirkung offen].
- Globaler Mapper schneller, Fusion auf GPU, Registrierung auf GPU, weisser Putz in PatchMatch: **nichts Neues** in Releases, auf main oder in offenen PRs.
- Bau-Risiko: ONNX-Download-404 trifft jeden frischen Bau von ce2b5ab (#5053).

## Vorschlag Reihenfolge

1. kornia 0.9.2 in venv-seg, dann Schnelltest und der fp16-Vergleich der Doppelgaenger-Pruefung (klein, gefahrlos).
2. `colmap-bauen.sh` gegen den ONNX-404 absichern (Mirror-URL oder neuer Stand).
3. Test-Prefix `colmap-build/prefix-main` mit COLMAP main (>= #5053) und vorhandenem Ceres bauen (Job mit RAM-Buchung). Danach FlexGlue an einer Doppelgaenger-DB pruefen und Kovarianz-RA als Variante in `versuche.jsonl` fahren. Den Produktivbau erst nach Gewinn am Foto-Tor umstellen. Vorher die DINOv3-Lizenz fuer den Verkauf klaeren.

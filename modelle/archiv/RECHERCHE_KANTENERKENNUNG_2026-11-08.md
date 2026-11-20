# Recherche Kantenerkennung (Ortho-Ansicht Fotowolke), Stand 2026-11-08

Auftrag: Kanten in 2,5-cm/px-Ortho (ca. 1160x840, Farbe + Tiefe, Rauschen/Loecher) deutlich verbessern.
Methode: Web-Recherche; Lizenzen wo moeglich ueber die GitHub-API (SPDX-Feld) bzw. Repo-Seiten gelesen.
Kennzeichnung: **[belegt]** = in dieser Recherche an der Quelle gesehen, **[nicht belegt]** = nur Erinnerung/nicht verifiziert.
Wichtig: GitHub-SPDX "MIT" gilt fuer den CODE. Fuer GEWICHTE gibt es meist keine eigene Aussage; wo das Repo sie nennt, ist es vermerkt.
Trainingsdaten-Lizenz (BSDS500, BIPED, MegaDepth, SA-1B) kann Gewichte indirekt beruehren: vor Verkauf juristisch pruefen (-> `modelle/LIZENZ_WERKZEUGE.md`).
Keine Benchmarkzahl hier ist auf Fassaden/Ortho-Wolken gemessen; alle Zahlen sind Papier-/README-Zahlen auf Fremddaten.

## 1. KI-Kantendetektoren

| Werkzeug | Repo | Code-Lizenz | Gewichte | Groesse / Tempo | Bemerkung |
|---|---|---|---|---|---|
| TEED (ICCVW 2023) | https://github.com/xavysp/TEED | MIT [belegt, API] | im Repo `checkpoints/BIPED/<epoche>/<n>_model.pth` (z. B. `5/5_model.pth` = 249 KB) [belegt]; eigene Gewichtslizenz nicht genannt | ca. 58 K Parameter [belegt]; VRAM/Laufzeit auf 4060 **nicht belegt**, aber winzig | UDED ODS 0,828 (Training BIPED), DexiNed 0,815, PiDiNet 0,812 [belegt, https://arxiv.org/pdf/2308.06468 / hyper.ai]. Training <30 min. Sehr gute erste Wahl: direkt als .py + .pth nutzbar, kein pip-Paket. Torch-Version nicht in README [nicht belegt]. |
| DexiNed (WACV 2020 / TPAMI 2022) | https://github.com/xavysp/DexiNed | MIT [belegt] | PyTorch-Checkpoint per Google Drive (BIPED, aeltere BIPED-Version) [belegt] | ca. 35 M Parameter [nicht belegt]; Eingabe Breite/Hoehe Vielfaches von 16 [belegt] | BIPED ODS .895 (README). Dazu ONNX in OpenCV Zoo: https://github.com/opencv/opencv_zoo/tree/main/models/edge_detection_dexined (MIT, `edge_detection_dexined_2024sep.onnx`, feste Eingabeform, README nennt OpenCV >= 5.0) [belegt]. Mit OpenCV-DNN ohne PyTorch nutzbar, ob es mit 4.x-DNN laeuft: nicht belegt. Duenne Kanten (Mauerwerk, Fenster) gut geeignet, da auf BIPED (Aussenszenen) trainiert. |
| PiDiNet (ICCV 2021) | https://github.com/hellozhuo/pidinet | MIT-Text, aber Hinweis "nur Forschung, kommerzielle Nutzung vorher mit Autoren klaeren" [belegt]; GitHub zeigt "Other" | im Repo `trained_models/table5_pidinet.pth` u. a. [belegt] | BSDS500 ODS 0,807, bis ~96 FPS (RTX 2080 Ti); tiny-Variante 0,789 [belegt] | **Lizenz fuer Verkauf = Risiko** (kommerziell nur nach Rueckfrage). |
| HED | https://github.com/s9xie/hed (Caffe), diverse PyTorch-Portierungen | **nicht belegt** (API-Abfrage des mlpc-ucsd-Repos 404) | Caffe-Gewichte, Portierungen unterschiedlich | VGG16-basiert | Veraltet; TEED/DexiNed besser und leichter. Nicht empfohlen. |
| RCF | https://github.com/yun-liu/rcf | GitHub "Other" (NOASSERTION), Text nicht lesbar [belegt: unklar] | Caffe/PyTorch (https://github.com/yun-liu/RCF-PyTorch) | VGG16 | Lizenz unklar -> meiden. |
| BDCN | https://github.com/pkuCactus/BDCN | MIT [belegt, API] | Google-Drive-Gewichte (BSDS/NYUD) [Link nicht geprueft] | VGG-basiert | Auf BSDS (Natur-/Objektkonturen) trainiert, neigt zu semantischen Konturen, nicht zu Mauerwerk-Fugen. |
| EDTER (CVPR 2022) | https://github.com/MengyangPu/EDTER | MIT [belegt, API] | **nicht belegt** (Google Drive, nicht geprueft) | Transformer (ViT), schwer; VRAM auf 8 GB **nicht belegt** | Hoechste BSDS-Zahlen, aber gross; Nutzen fuer Fassade fraglich. |
| MuGE (CVPR 2024), UAED | https://github.com/ZhouCX117/UAED | **keine Lizenz im Repo (license=null)** [belegt] -> rechtlich "alle Rechte vorbehalten" | **nicht belegt** | - | Nicht fuer Verkauf nutzbar ohne Rueckfrage. Fuer Test ok. |
| SAM-Kanten (Segment Anything) | https://github.com/facebookresearch/segment-anything | Apache-2.0 **[nicht belegt in dieser Recherche, aus Erinnerung]** | Meta, Checkpoints vit_b/l/h | vit_b ca. 91 M | SAM liefert Masken, keine Kantenkarte; Masken-Raender als Kandidaten (Segment-Grenzen) moeglich, aber keine dedizierte, belegte Kantenpipeline gefunden. Bei Rauschwolke Nutzen **nicht belegt**. |
| DINOv3 (Meta, 2025) | https://github.com/facebookresearch/dinov3 | "DINOv3 License" (eigene Lizenz, GitHub: Other) [belegt]: Nutzung frei, Weitergabe nur mit Lizenzkopie, Publikationen muessen Nutzung nennen, Militaer/ITAR-Verbot, Patentklage = Lizenzende, Freistellung von Meta | Gewichte unter derselben Lizenz, Download nach Zustimmung | gross (ViT bis 7 B; kleine Distill-Modelle) [Zahlen nicht belegt] | Merkmale fuer Segmentierung, **keine Kantenkarte** out-of-the-box. Fuer unser Problem (duenne geometrische Kanten) kein direkter Nutzen belegt. |
| Depth Anything V2 | https://github.com/DepthAnything/Depth-Anything-V2 | siehe README: **nur Small = Apache-2.0**; Base/Large/Giant = CC-BY-NC-4.0 [belegt] | Small 24,8 M Param.; Base 97,5 M; Large 335,3 M [belegt] | Small passt locker in 8 GB | Wir haben ein echtes Tiefenbild aus der Wolke; DA-V2 bringt nichts Neues. Nur falls Fotos ohne Wolke -> nicht unser Fall. |

Hinweis Domaene: BIPED (DexiNed/TEED) = Aussenszenen mit duenn annotierten Kanten, naeher an Fassade als BSDS500 (Objektkonturen). Das ist Plausibilitaet, **keine Messung an unserem Material** [nicht belegt].
Gross-Risiko: alle KI-Detektoren sind auf natuerliche Fotos trainiert. Unsere Ortho hat Rauschen, Loecher und rotes Gestein mit Fugen. Domain-Luecke -> erst per Sichtprobe (CLAUDE.md Regel 3) pruefen.

## 2. Klassische / robuste Verfahren

- **Phase Congruency (Kovesi):** pip `phasepack` (Python-Port von Alistair Muldal, Version 1.5, MIT) [belegt: https://pypi.org/project/phasepack/]. Funktionen `phasecong`, `phasecongmono`. Beleuchtungsinvariant; auf 1160x840 CPU-Laufzeit **nicht belegt** (log-Gabor ueber Skalen x Orientierungen, mehrere Sekunden plausibel). Kovesis Original-Matlab-Code hat eigene Hinweise (kommerzielle Nutzung des Algorithmus: Patent war historisch beim Autor/NRDC, **nicht belegt**; vor Verkauf pruefen).
- **Structured Edge Detection (Dollar):** OpenCV `cv2.ximgproc.createStructuredEdgeDetection(model.yml.gz)`, opencv_contrib. Modelldatei separat zu laden; Lizenz des Modells **nicht belegt**. Trainiert auf BSDS.
- **EDLines / EDPF / FastLineDetector:** `cv2.ximgproc.createFastLineDetector`, `cv2.ximgproc.EdgeDrawing` (opencv_contrib). Lizenz opencv_contrib Apache-2.0 [nicht belegt hier, bekannt aus OpenCV]. Schnell, parameterfrei bei EDPF; zusaetzlicher Kandidat neben LSD.
- **LSD in OpenCV:** Implementierung war zwischen 3.4.6-3.4.15 und 4.1.0-4.5.3 wegen Lizenzkonflikt des Originalcodes entfernt, danach neu implementiert (MIT, laut Doku) und ab 4.5.4 wieder da [belegt: https://docs.opencv.org/4.x/db/d73/classcv_1_1LineSegmentDetector.html, GitHub-Issue-Kommentar; Aussage "4.7.0" im Forum widerspricht, nicht geklaert]. Pruefen, welche Version bei uns laeuft (>= 4.5.4 = unkritisch).
- **Canny-Pyramide / Multi-Skalen:** reines OpenCV/scikit-image, Lizenz unkritisch. Mit hysterese-konsistenter Skalenfusion (siehe 4).
- **Gradienten in Lab/Oklab:** Oklab-Konvertierung simpel selbst zu schreiben (Formel public domain/MIT von B. Ottosson [nicht verifiziert]); Farbkanten als Vektorgradient (Di Zenzo) statt 9 getrennter Kanaele ist die saubere Alternative zu "9 Kanaele x LSD".
- **Glaettung vor Kanten:** bilateral, guided filter (`cv2.ximgproc.guidedFilter`), `cv2.pyrMeanShiftFiltering`, Anisotrope Diffusion (Perona-Malik, scikit-image `denoise_*`/eigene Umsetzung), Non-Local-Means `cv2.fastNlMeansDenoisingColored`. Wirkung auf unsere Daten **nicht belegt**; Sweep noetig.
- **Tiefenkanten:** Sprung im Tiefenbild (Sobel/Laplace auf Tiefe mit Lochmaske), unabhaengig von Farbe. Eigenes Verfahren, Lizenz kein Thema.
- **Gabor/Log-Gabor:** `skimage.filters.gabor`, Log-Gabor selbst oder via phasepack.

## 3. Lernbasierte Liniendetektoren

| Werkzeug | Repo | Code | Gewichte | Eignung |
|---|---|---|---|---|
| DeepLSD (CVPR 2023) | https://github.com/cvg/DeepLSD | MIT [belegt, API] | README: "Both models are released under an MIT license" [belegt]; `deeplsd_wireframe.tar` (innen), `deeplsd_md.tar` (aussen, MegaDepth) von https://cvg-data.inf.ethz.ch/DeepLSD/ [belegt]; HF-Spiegel (inoffiziell): https://huggingface.co/xboix/deeplsd | Liefert Liniensegmente **und** Gradientenfeld (die Fortsetzung von LSD) -> naechster Ersatz fuer LSD. `quickstart_install.sh` fuer reine Inferenz, getestet mit Python 3.7/CUDA 11/GCC 9 (**veraltet, Kompatibilitaet mit unserem Torch nicht belegt**); `third_party` Submodule mit eigenen Lizenzen (nicht geprueft). Modell `md` zuerst. |
| ScaleLSD (CVPR 2025) | https://github.com/ant-research/scalelsd | MIT [belegt, API] | HF https://huggingface.co/cherubicxn/scalelsd: `scalelsd-vitbase-v1/v2-train-sa1b.pt`, Lizenz Apache-2.0 [belegt]; v2 empfohlen | Selbstueberwacht auf ~10 Mio Bildern (u. a. SA-1B), ViT-Base; Tests mit PyTorch 2.5.1/CUDA 12.1/Python 3.10 [belegt]; behauptet besser als klassisches LSD (Autorenangabe). VRAM/Laufzeit **nicht belegt**. ViT-Base sollte auf 8 GB passen (Vermutung). |
| HAWP / HAWPv3 | https://github.com/cherubicxn/hawp | MIT [belegt, API] | im Repo-README verlinkt, nicht geprueft | Wireframe (Innenraum-Training), fuer Fassade/Ortho fraglich. |
| LCNN | https://github.com/zhou13/lcnn | MIT [belegt, API] | Gewichte-Link nicht geprueft | Alt (2019), auf Wireframe-Daten; ueberholt. |
| LETR | **nicht recherchiert/nicht belegt** | | | Transformer, nicht empfohlen. |
| GlueStick | **nicht recherchiert** (nur als Abhaengigkeit der ScaleLSD-Demo genannt) | | | Linien-Matching, fuer uns nicht noetig. |

Kritik: Lernbasierte Liniendetektoren sind meist auf Foto-Perspektive trainiert. Unsere Ortho ist eine senkrechte Parallelprojektion mit Rauschen: Domain-Luecke, nur Sichtprobe entscheidet. Ergebnisse sind Liniensegmente (gut zum direkten Mischen mit LSD-Ausgabe); Kantenkarten (TEED/DexiNed) muessten erst zu Linien (z. B. via LSD/EDLines auf der Karte) umgewandelt werden.

## 4. Fusion

Belegt fand ich keine Veroeffentlichung, die TTA-/Ensemble-Fusion fuer Kantenkarten vergleichend untersucht (Suche ergab nur Trainings-Augmentierung arXiv 2407.19992 und Multi-Scale-Netze). Alles Folgende ist deshalb **Ingenieur-Empfehlung, nicht belegt**:

1. **Normieren** je Karte (z. B. Rang-/Perzentil-Normierung statt Min-Max, damit Ausreisser nicht dominieren), dann Mittel oder Median ueber Varianten; Konsens = Anteil der Varianten, die an Pixel (+-1 px nach Toleranz-Dilatation) eine Kante haben.
2. **NMS** auf der gemittelten Karte (Orientierung aus Strukturtensor), **Hysterese** (hohe Schwelle = Konsens >= ca. 50 %, niedrige Schwelle ca. 20-30 %, Werte als Startpunkt, nicht belegt) -> duenne, zusammenhaengende Kanten.
3. **Linienstimmen:** wie bisher fuer LSD/DeepLSD/ScaleLSD/EDLines; Segmente werden zusammengelegt, wenn Winkel, Abstand und Ueberlappung passen; Gewichtung nach unabhaengiger Quelle (nicht 9 stark korrelierte Farbkanaele = 9 Stimmen). Besser: Stimmen pro **Detektorfamilie**, nicht pro Kanal.
4. **Skalen-Konsens:** Canny/Detektor auf 0,5x / 1x / 2x, Ergebnisse auf Originalgitter, nur Kanten ueber >= 2 Skalen.
5. **TTA:** Spiegelung (H/V), 90-Grad-Drehung (bei Ortho zulaessig), Rueckdrehen, mitteln. Kosten linear; fuer TEED (58 K Param.) vernachlaessigbar.
6. **Kontrast/Helligkeit/Gamma-Sweep (Startwerte, Vorschlag):** Gamma {0,6; 1,0; 1,6}, CLAHE clipLimit {2; 4} Kachel 8x8 bis 16x16, lineare Helligkeitsverschiebung +-20 % der Spannweite, Perzentil-Stretch {1-99; 5-95}. Farbraeume: Grau, Lab (L, a, b), Oklab, Hue/Sat nur dort mit Sat-Maske (Farbton bei kleiner Saettigung rauscht). Bewertung nur per Sicht + Rueckprojektion auf Foto (CLAUDE.md 3f), kein Gewinn behauptet.
7. **Tiefen-Loecher maskieren**, damit Lochraender nicht als Kanten gezaehlt werden (Hauptquelle falscher Kanten bei Fotopunktwolken, aus eigener Erfahrung, nicht belegt).

## 5. Rangliste und erste Schritte

Rangliste (Nutzen erwartet / Aufwand / Lizenz) - Nutzenangaben sind Erwartungen, keine Messung:

1. **DeepLSD (md)** - direkter LSD-Ersatz, Segmente, MIT Code+Gewichte; Aufwand mittel (Installation, alte Abhaengigkeiten); Risiko: Altpaket.
2. **TEED** - 249-KB-Gewichte im Repo, MIT-Code, kaum VRAM, Kantenkarte; Aufwand niedrig (1 Skript + .pth); Risiko: Gewichtslizenz nicht eigens genannt, Torch-Version unbekannt.
3. **ScaleLSD v2** - moderner Linienfinder, MIT + Apache-2.0-Gewichte; Aufwand mittel; Risiko: Domain, Abhaengigkeiten (Torch 2.5.1).
4. **DexiNed (ONNX aus OpenCV Zoo oder .pth)** - MIT; zweite Kantenkarte fuer Fusion; Aufwand niedrig-mittel.
5. **Phase Congruency (`phasepack`)** + Di-Zenzo-Farbgradient + Tiefenkanten - klassisch, beleuchtungsinvariant, pip, MIT; Aufwand niedrig.
6. **EDLines/FLD (ximgproc)** - billig, zweite Linienquelle; Aufwand niedrig.
7. BDCN/EDTER - nur mit Sichtprobe, aufwendiger; PiDiNet nur zum Test (Lizenzvorbehalt kommerziell); MuGE/UAED, RCF: Lizenz unklar -> nur Test; HED/LCNN/HAWP: kein Vorteil; DINOv3/SAM/DepthAnything: kein belegter Kantenbeitrag.

Die 3 besten ersten Schritte:

1. **Fusionsgeruest ohne neue KI, mit Phase Congruency + Konsens**: `pip install phasepack` (in `~/.venvs/rcpark` oder venv-seg testen), Di-Zenzo-Gradient (Lab/Oklab), Tiefenkanten mit Lochmaske, Sweep gemaess Abschnitt 4. Aufwand ca. 0,5-1 Tag. Risiko: Parameterflut -> Sichtblatt je Variante (Regel 3) und Vergleich gegen Foto-Diff (`tools/foto_diff.py`).
2. **TEED (und DexiNed) als Kantenkarte**: `git clone https://github.com/xavysp/TEED`, Gewichte `checkpoints/BIPED/<n>/<n>_model.pth` (es existieren die Ordner 0-7, welche Epoche die beste ist: nicht belegt, `checkpoints/current_res` ebenfalls ungeprueft). Eingabe Vielfaches von 8/16 (Padding), `python main.py --choose_test_data=-1` laut README. Danach Karte -> NMS -> Hysterese -> `cv2.createLineSegmentDetector`/EDLines auf der Karte. Aufwand ca. 0,5 Tag. Risiko: Domain-Luecke, Rauschen; Offline-Betrieb ok (Gewichte im Repo, kein Netz noetig).
3. **DeepLSD `deeplsd_md.tar`** (und danach ScaleLSD v2 per `huggingface-cli download cherubicxn/scalelsd`): zuerst nur an einer Ortho testen und Segmente neben die LSD-Segmente legen, in Kantenzahl, Fragmentierung, Mauerwerk-Fugenanteil per Sicht vergleichen. Aufwand 1 Tag (DeepLSD-Installation mit Submodulen und alten Versionen ist der Haken). Risiko: Installationsaerger, Torch-Kompatibilitaet.

Vor Verkauf: Gewichte/Trainingsdaten-Lizenzen je Werkzeug in `modelle/LIZENZ_WERKZEUGE.md` eintragen; PiDiNet, MuGE/UAED, RCF nur als Testwerkzeug (NC-Liste).

## Quellen
- TEED: https://github.com/xavysp/TEED , https://arxiv.org/abs/2308.06468 , UDED-Tabelle https://hyper.ai/de/sota/tasks/edge-detection/benchmark/edge-detection-on-uded
- DexiNed: https://github.com/xavysp/DexiNed ; OpenCV Zoo https://github.com/opencv/opencv_zoo/tree/main/models/edge_detection_dexined
- PiDiNet: https://github.com/hellozhuo/pidinet ; BDCN https://github.com/pkuCactus/BDCN ; RCF https://github.com/yun-liu/rcf ; EDTER https://github.com/MengyangPu/EDTER ; MuGE/UAED https://github.com/ZhouCX117/UAED , https://openaccess.thecvf.com/content/CVPR2024/html/Zhou_MuGE_Multiple_Granularity_Edge_Detection_CVPR_2024_paper.html
- DeepLSD: https://github.com/cvg/DeepLSD ; ScaleLSD: https://github.com/ant-research/scalelsd , https://huggingface.co/cherubicxn/scalelsd , https://arxiv.org/abs/2506.09369 ; HAWP: https://github.com/cherubicxn/hawp ; LCNN: https://github.com/zhou13/lcnn
- DINOv3 Lizenz: https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md ; Depth Anything V2: https://github.com/DepthAnything/Depth-Anything-V2
- phasepack: https://pypi.org/project/phasepack/ ; OpenCV LSD: https://docs.opencv.org/4.x/db/d73/classcv_1_1LineSegmentDetector.html

# Open-Vocabulary-Erkennung, Segmentierung und Fassaden-Parsing (Fenster, Tueren, Boegen, Erker, Gauben, Balkone, Figuren, Traufen, Stufengiebel), 2024-2026

Ausgangslage (Auftrag): google/owlv2-base-patch16-ensemble (Apache-2.0) ueber HF transformers, zero-shot auf entzerrten Fassaden-Orthofotos (~10 je Fassade, 2x hochskaliert), mehrere Prompts je Klasse; RTX 4060 Laptop mit 8 GB. Verkauf geplant: MIT/BSD/Apache in Ordnung, AGPL/NC problematisch.
Recherchestand 2026-11-05. "[UNSICHER]" kennzeichnet unbestaetigte Punkte.

## 1. OWLv2 schneller machen (fp16, Batching, bildgefuehrte Abfragen, TensorRT/ONNX, large gegen base, NanoOWL)

### Takeaway
OWLv2-Code und Checkpoints stehen unter Apache-2.0. Der HF-Prozessor skaliert jedes Bild auf hoechstens 960x960 und fuellt es mit Rand auf. Unser 2x-Hochskalieren bringt dem Modell darum wahrscheinlich keine zusaetzlichen Pixel: Es wird wieder heruntergerechnet. Kleine Elemente bekommen mehr Aufloesung nur durch Kacheln (Tiling). Auf der Genauigkeitsachse ist L/14 ST+FT der staerkste Checkpoint (LVIS AP 48,8 gegen 43,9 bei B/16 ens), aber deutlich schwerer. NanoOWL ist Apache-2.0, unterstuetzt aber nur OWL-ViT (v1) B/32 und B/16, nicht OWLv2.

### Cited Findings
- Code und Checkpoints von OWL-ViT/OWLv2: "Both the code and the model checkpoints are licensed under the Apache 2.0 license." — [scenic owl_vit README](https://github.com/google-research/scenic/tree/main/scenic/projects/owl_vit)
- Checkpoint-Tabelle (Evaluator-Werte, "may differ slightly from the paper"), LVIS AP / APr: B/16 ST 26,5/29,5; B/16 ST+FT 41,4/36,2; **B/16 ST/FT ens (unser Modell) 43,9/40,5**; L/14 ST 32,8/34,6; **L/14 ST+FT 48,8/44,0**; L/14 ens 44,6/42,6. — [scenic owl_vit README](https://github.com/google-research/scenic/tree/main/scenic/projects/owl_vit)
- Laut README wird die Laufzeit von Bild- und Textencoder bestimmt; ueber eine kleinere Bildgroesse laesst sich Genauigkeit gegen Tempo tauschen. Die Zahlen zur Geschwindigkeit stehen nur in einem Diagramm. — [scenic owl_vit README](https://github.com/google-research/scenic/tree/main/scenic/projects/owl_vit)
- HF-Owlv2ImageProcessor: `size` steht standardmaessig auf `{'height': 960, 'width': 960}` ("maximum input dimensions"), `do_pad=True`. Beim Batching wird auf die groesste Bildgroesse im Batch oder auf ein festes Quadrat aufgefuellt. — [HF transformers OWLv2 docs](https://huggingface.co/docs/transformers/model_doc/owlv2)
- HF bietet `Owlv2ForObjectDetection.image_guided_detection` (One-Shot mit Abfragebild) und `post_process_image_guided_detection(outputs, threshold=0.0, nms_threshold=0.3, target_sizes)`. Labels sind dabei None, die Ausgabe ist klassenagnostisch je Abfragebild. — [HF transformers OWLv2 docs](https://huggingface.co/docs/transformers/model_doc/owlv2)
- NanoOWL: Apache-2.0 (LICENSE.md). Unterstuetzt laut README nur OWL-ViT ViT-B/32 und ViT-B/16 bei Bildgroesse 768. Die TensorRT-Engine wird nur fuer den Bildencoder gebaut (`python3 -m nanoowl.build_image_encoder_engine ...`), Voraussetzung torch2trt. FPS-Tabelle mehrdeutig: etwa 95 FPS fuer B/32 und 25 FPS fuer B/16 auf AGX Orin. — [NanoOWL GitHub](https://github.com/NVIDIA-AI-IOT/nanoowl)

### Inferences
- **Hochskalieren pruefen:** Ist ein Orthofoto nach 2x groesser als 960 px, verkleinert der Prozessor es wieder auf 960 an der laengsten Kante. Das Hochskalieren kostet dann nur Vorverarbeitungszeit. Fuer kleine Elemente (Stufen, Figuren, Gaubenfenster) besser in 960er-Kacheln mit Ueberlappung zerlegen und danach NMS ueber die Kacheln rechnen. Zuerst messen: `inputs.pixel_values.shape` und den Skalierungsfaktor protokollieren.
- **Textembeddings cachen:** Prompts sind ueber alle Bilder gleich. Den Textencoder einmal je Prompt-Satz laufen lassen und nur den Bildencoder wiederholen. Die HF-Klasse trennt intern Bild-Embedding und Klassenkopf. Nachzuweisen ist, dass die Ausgabe dabei gleich bleibt (Regressionstest mit identischen Boxen).
- **fp16/bf16:** `torch_dtype=torch.float16` plus `torch.inference_mode()` duerfte auf Ada (RTX 4060) etwa doppelten Durchsatz bringen und den VRAM halbieren. Gemessene Werte fuer OWLv2 auf RTX 4060 habe ich nicht gefunden (siehe Gaps). Scores koennen sich in fp16 leicht verschieben, Schwellen danach also neu pruefen.
- **Batching:** Alle ~10 Kacheln/Bilder einer Fassade als einen Batch auf gleiche Groesse (960x960) bringen. B/16 bei 960 px ergibt 3600 Patch-Tokens. Bei 8 GB sind in fp16 Batches von etwa 4-8 realistisch [UNSICHER, nicht gemessen].
- **Bildgefuehrte Abfragen** passen gut zu Wiederholungselementen (ein gutes Fenster einer Fassade als Abfrage fuer alle anderen Fenster). Das ist One-Shot statt Text und robuster bei Fachbegriffen wie "Erker" oder "Stufengiebel", die CLIP-Text schlecht kennt.
- **L/14 gegen B/16:** +4,9 LVIS AP (ST+FT gegen B/16 ens), aber L/14 hat bei 1008 px Eingabe etwa 5184 Tokens und ein viel groesseres Backbone. Grob 3-5x langsamer [UNSICHER]. Lohnt nur fuer Problemklassen und am besten nur auf Kacheln mit Kandidaten.
- **TensorRT/ONNX:** NanoOWL zeigt, dass ein TRT-Bildencoder fuer OWL-ViT funktioniert. Fuer OWLv2 gibt es keinen offiziellen Weg. Man muesste den Encoder selbst exportieren (torch.onnx/torch2trt). Aufwand mittel, Nutzen gross, wenn der Bildencoder den Grossteil der Zeit frisst.

### Gaps
- Keine Benchmarks fuer OWLv2 fp16 gegen fp32, keine fuer SDPA/Flash-Attention-Unterstuetzung in HF Owlv2, und keine ms/Bild-Zahlen fuer Consumer-GPUs gefunden.
- Kein gepflegter OWLv2-TensorRT-Port gefunden. Ob ONNX-Exporte von OWLv2 (etwa ueber optimum) stabil laufen, ist ungeprueft.

## 2. Alternativen: Grounding DINO, 1.5/DINO-X, Florence-2, YOLO-World, YOLOE, OmDet-Turbo, LLMDet, Rex-Omni, SAM 2/3, Qwen-VL, PaliGemma 2, Molmo

### Takeaway
Lizenzsauber (Apache/MIT) und lokal lauffaehig sind Grounding DINO (original), OmDet-Turbo, LLMDet, Florence-2 und Qwen3-VL. SAM 3 ist technisch der staerkste Kandidat fuer textgesteuerte Instanzmasken ("alle Fenster"), laeuft aber unter der eigenen "SAM License": kommerziell nicht ausgeschlossen, mit Einschraenkungen (Militaer/Nuklear/Spionage, kein Reverse Engineering, Freistellung von Meta, einseitig aenderbar) und vom Juristen zu pruefen. YOLO-World (GPL-3.0) und YOLOE (AGPL-3.0) sind fuer den Verkauf problematisch. Grounding DINO 1.5/DINO-X sind faktisch nur per API verfuegbar. Rex-Omni steht unter der IDEA License 1.0 und baut auf Qwen auf (Research-Lizenz-Hinweis), ist also problematisch.

### Cited Findings
**Grounding DINO (original)**
- Repo-Lizenz Apache-2.0, ohne eigene Gewichtslizenz. COCO zero-shot: Swin-T 48,4 AP (fine-tuned 57,2), Swin-B 56,7 (Art der Messung unklar). Das README ist in sich widerspruechlich (52,5 zero-shot in den Highlights, an anderer Stelle 48,5). — [IDEA-Research/GroundingDINO](https://github.com/IDEA-Research/GroundingDINO)
- Grounding DINO 1.5: Das offizielle Repo ist ein API-Client, der ein DeepDataSpace-Token braucht. Apache-2.0 gilt fuer den API-Code, nicht fuer Gewichte. — [grounding-dino-1.5-api](https://github.com/idea-research/grounding-dino-1.5-api). Eine Sekundaerquelle behauptet, Gewichte seien offen ([emergentmind](https://www.emergentmind.com/topics/groundingdino)); das widerspricht dem offiziellen Repo und ist zu verwerfen.
- DINO-X: "Our demo and API will be released at github.com/IDEA-Research/DINO-X-API". Offene Gewichte habe ich nicht gefunden. — [DINO-X arXiv 2411.14347](https://arxiv.org/html/2411.14347v2)

**Fassaden-Praxisbeleg Grounding DINO + SAM 2 (ISPRS 2026, TU Wien/UVM)**
- Fenstererkennung, Wien, Schraegluftbilder (UltraCam Osprey 4.1, GSD ~7 cm). Bestes Verfahren: zero-shot Grounding DINO + SAM 2 auf **Fassaden-Orthofotos**, Precision 0,95, F1 0,85. SAM2-UNeXT (mit 120 annotierten Bildern trainiert): Precision 0,69, F1 0,72, Recall 0,78 (leicht hoeher). — [Otepka et al., ISPRS Archives XLIX-B2-2026, 517](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/517/2026/isprs-archives-XLIX-B2-2026-517-2026.pdf)
- Laut derselben Arbeit sind SAM2-Masken an den Kanten genauer als GDINO-Boxen und erfassen nicht rechteckige oder teilverdeckte Oeffnungen besser. Bestes IoU 0,75. Zur Regularisierung sei hoeherer Recall wichtiger als Precision. — [Otepka et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/517/2026/isprs-archives-XLIX-B2-2026-517-2026.pdf)

**Florence-2**
- MIT. Groessen: large 0,77B, base 0,23B. Tasks `<OD>`, `<CAPTION_TO_PHRASE_GROUNDING>`, `<REGION_PROPOSAL>`. COCO OD AP 39,8 (large). Die Karte sagt selbst, die weitertrainierte Version "might not be trained well". — [HF microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large)

**YOLO-World / YOLOE**
- YOLO-World (AILab-CVC, Original-Repo): GPL-3.0 (laut README-Badge und Repo-Metadaten, LICENSE-Datei selbst nicht geoeffnet). — [ecosyste.ms AILab-CVC/YOLO-World](https://awesome.ecosyste.ms/projects/github.com%2FAILab-CVC%2FYOLO-World). Ultralytics-Integration: AGPL-3.0 (Ultralytics-Standard, hier nicht separat nachgeprueft).
- YOLOE (THU-MIG): **AGPL-3.0**, auf Ultralytics-Basis. Laut Repo liegt YOLOE-v8-S auf LVIS 3,5 AP ueber YOLO-Worldv2-S und ist 1,4x schneller. FPS auf T4 mit TensorRT: 305,8 mit Text-, 64,3 mit visuellem Prompt; prompt-frei 95,8 FPS (T4, PyTorch). Seg-Varianten: Zero-Shot-LVIS AP^m 23,5 (Text) / 22,0 (visuell) fuer v8-L. — [THU-MIG/yoloe](https://github.com/THU-MIG/yoloe); Lizenzerlaeuterung AGPL-Netzklausel: [Roboflow YOLOE license](https://roboflow.com/model-licenses/yoloe)

**OmDet-Turbo**
- In transformers ab 4.45 (`omlab/omdet-turbo-swin-tiny-hf`). Tiny: zero-shot COCO 42,5 / LVIS 30,3; 21,5 FPS in PyTorch, 140 FPS mit TensorRT. Base: 100,2 FPS auf A100 (TRT, Sprach-Cache). Lizenz Apache-2.0 laut Index, offizielle Bestaetigung nicht gesehen [UNSICHER]. — [arXiv 2403.06892](https://arxiv.org/abs/2403.06892v2); [HF docs omdet-turbo](https://huggingface.co/docs/transformers/model_doc/omdet-turbo); [ecosyste.ms om-ai-lab/OmDet](https://awesome.ecosyste.ms/projects/github.com%2Fom-ai-lab%2Fomdet)

**LLMDet**
- Apache-2.0 (README und HF-Karte), iSEE-Laboratory, in transformers 4.55.0 eingebunden (Grounding-DINO-Architektur, mit LLM-Supervision trainiert). — [HF iSEE-Laboratory/llmdet_large](https://huggingface.co/iSEE-Laboratory/llmdet_large/blob/main/README.md)

**Rex-Omni (IDEA, 2025, "Detect Anything via Next Point Prediction")**
- Lizenz "IDEA License 1.0". Die Karte sagt ausserdem, das Modell basiere auf Qwen, "licensed under the Qwen RESEARCH LICENSE AGREEMENT". Fuer den Verkauf problematisch, bis die Lizenztexte geprueft sind. — [HF IDEA-Research/Rex-Omni (Spiegel)](https://hf-767.pages.dev/IDEA-Research/Rex-Omni); [arXiv 2510.12798](https://arxiv.org/abs/2510.12798v1)

**SAM 3 / SAM 3.1**
- Veroeffentlicht am 19.11.2025. "Promptable Concept Segmentation": Eine kurze Nominalphrase liefert Masken fuer **alle** passenden Instanzen. Die Prompts koennen Text, Geometrie oder Bild-Exemplare sein. 848M Parameter (HF: 0,9B, F32). — [facebookresearch/sam3](https://github.com/facebookresearch/sam3); [HF facebook/sam3](https://huggingface.co/facebook/sam3) (gated, "License: other")
- SA-Co/Gold cgF1 (README-Tabelle, Spaltenzuordnung nicht ganz eindeutig): SAM 3 55,7, OWLv2 24,5 (teilweise auf LVIS trainiert), DINO-X 22,5, Gemini 2.5 14,4, Mensch 74,0. — [facebookresearch/sam3](https://github.com/facebookresearch/sam3)
- SAM 3.1 "Object Multiplex" (27.03.2026): gemeinsamer Speicher fuer Multi-Objekt-Tracking, "significantly faster". — [facebookresearch/sam3](https://github.com/facebookresearch/sam3)
- **SAM License** (Stand 19.11.2025): "non-exclusive, worldwide, non-transferable and royalty-free limited license" zu Nutzung, Vervielfaeltigung, Verbreitung und Aenderung. Kommerzielle Nutzung wird **weder ausdruecklich erlaubt noch verboten**. Verboten sind ITAR-/Exportkontroll-Verstoesse, "military or warfare purposes, nuclear industries or applications, espionage" sowie Reverse Engineering. Bei Weitergabe muss die Lizenz beiliegen. Abgeleitete Werke gehoeren dem Nutzer. Die Lizenz endet bei Patentklage gegen Meta. Freistellungspflicht gegenueber Meta; Meta darf die Bedingungen aendern; kalifornisches Recht. — [sam3 LICENSE](https://github.com/facebookresearch/sam3/blob/main/LICENSE)
- SAM 2: Code und Gewichte Apache-2.0 (nicht in dieser Sitzung nachgeprueft, aus dem Kenntnisstand [UNSICHER, im Repo facebookresearch/sam2 bestaetigen]). Die ISPRS-Studie nutzt SAM 2 als Box-zu-Maske-Verfeinerer. — [Otepka et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/517/2026/isprs-archives-XLIX-B2-2026-517-2026.pdf)

**VLMs mit Grounding**
- Qwen3-VL (2B/4B/8B/32B dicht + MoE, Instruct/Thinking, Oktober 2025): HF-Karte 4B: `license: apache-2.0`, "stronger 2D grounding". — [HF Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct); Bericht: [arXiv 2511.21631](https://arxiv.org/pdf/2511.21631v2)
- Qwen2.5-VL-3B: Die HF-Seite zeigt beim Abruf keinen Lizenz-Tag, beschreibt aber Boxen/Punkte als "stable JSON outputs". Aus meinem Kenntnisstand: 3B steht unter "Qwen Research License" (NC), 7B unter Apache-2.0, 72B unter der Qwen License [UNSICHER, je Karte pruefen]. — [HF Qwen2.5-VL-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct)
- PaliGemma 2: HF-Karten verweisen auf die Gemma Terms (gated). Laut Sekundaerquelle ist kommerzielle Nutzung erlaubt, gebunden an eine Prohibited Use Policy [UNSICHER]. — [HF paligemma2-3b-pt-896](https://huggingface.co/google/paligemma2-3b-pt-896); [vorplabs Gemma license](https://vorplabs.com/models/gemma-license)
- Molmo 7B-O/7B-D: Tag apache-2.0, die Karten sagen aber "intended for research and educational use". 72B basiert auf Qwen2-72B (Tongyi-Qianwen-Lizenz). Widerspruechlich, deshalb vor Verkauf pruefen. — [HF allenai/Molmo-7B-O-0924](https://huggingface.co/allenai/Molmo-7B-O-0924); [HF allenai/Molmo-72B-0924](https://huggingface.co/allenai/Molmo-72B-0924)

### Inferences
- **Groesster Hebel fuer unseren Anwendungsfall:** SAM 3 mit Text- oder Exemplar-Prompt ("window", Exemplar = ein bestaetigtes Fenster) liefert Instanzmasken in einem Schritt. Laut SA-Co-Tabelle liegt es mehr als doppelt so hoch wie OWLv2. 848M Parameter in fp16 belegen etwa 1,7 GB fuer die Gewichte und passen auf 8 GB [UNSICHER, Aktivierungsspeicher nicht gemessen]. Die Lizenz ist kein klassisches NC, aber eine proprietaere Meta-Lizenz mit Freistellung und einseitiger Aenderbarkeit. In `modelle/LIZENZ_WERKZEUGE.md` als "pruefpflichtig" eintragen und bis zur Pruefung nur testen.
- **Lizenzsaubere Kette mit Fassadenbeleg:** Grounding DINO (Apache) oder LLMDet (Apache, staerker trainiert, gleiche Architektur) erzeugen Boxen, SAM 2 (Apache) die Masken. Genau diese Kette erreichte auf Fassaden-Orthofotos P=0,95/F1=0,85. Das ist der direkteste Ersatz bzw. die direkteste Ergaenzung fuer OWLv2.
- **OmDet-Turbo** ist das schnellste lizenzsaubere Open-Vocabulary-Modell mit HF-Integration (Tiny: LVIS 30,3, also unter OWLv2 B/16 ens mit 43,9 [unterschiedliche Evaluationsprotokolle, nur grob vergleichbar]). Taugt als Vorfilter oder fuer einfache Klassen (Fenster, Tuer), nicht fuer seltene Klassen (Erker, Stufengiebel).
- **Florence-2** ist klein und MIT, liefert aber laut eigener Karte maessige Detektion. Eher als Captioner/Region-Proposer zu gebrauchen.
- **VLMs (Qwen3-VL-4B/8B, Apache)** eignen sich fuer Fragen, die Detektoren schlecht koennen: "Ist das ein Stufengiebel, wie viele Stufen?", "Gibt es einen Erker?". Sie sind langsam (autoregressiv), bei 8 GB laeuft 8B nur quantisiert (4 bit). 4B in bf16 belegt etwa 8-9 GB, also knapp oder zu gross [UNSICHER].
- YOLOE/YOLO-World nur als Labor-Referenz, nicht im Produkt (AGPL/GPL). Rex-Omni und Molmo nur testen (NC- bzw. Research-Formulierungen).

### Gaps
- Direkter Vergleich OWLv2 gegen GDINO, LLMDet und SAM 3 auf Fassaden-Orthofotos (mehr als Fenster) nicht gefunden. Die ISPRS-Studie testet nur GDINO+SAM2, nur Fenster.
- LVIS-Zahlen fuer LLMDet und VRAM/ms-Werte fuer SAM 3 auf 8-GB-GPUs nicht ermittelt.
- Lizenztext der IDEA License 1.0 und der Gemma Terms nicht gelesen (gated bzw. nicht gefunden).
- MM-Grounding-DINO (MMDetection): Lizenz der Gewichte nicht bestaetigt (MMDetection selbst ist Apache-2.0 [UNSICHER]).

## 3. Spezialisiertes Fassaden-Parsing: Datensaetze, Modelle, LoD3-Oeffnungen, Lizenzen

### Takeaway
Die klassischen Datensaetze sind klein (CMP 606 Bilder; ECP 104 Pariser Haussmann-Fassaden). CMP steht unter CC BY-SA. Trainierte Gewichte daraus sind fuer den Verkauf rechtlich unklar (Share-Alike auf Gewichte ungeklaert). Neuere Arbeiten (2024-2026) sind meist kleine Fine-Tunes (YOLOv8, SegFormer, ViT) ohne veroeffentlichte und lizenzierte Gewichte. Ein einsatzfertiges, permissiv lizenziertes "Fassaden-Parser"-Modell habe ich nicht gefunden. Fine-Tuning auf eigenen Daten oder Zero-Shot bleibt der realistische Weg.

### Cited Findings
- **CMP Facade Database:** CC BY-SA. 606 entzerrte Fassaden (378 Basis + 228 erweitert). 12 Klassen: facade, molding, cornice, pillar, window, door, sill, blind, balcony, shop, deco, background. — [CMP Facade (Tylecek)](https://cmp.felk.cvut.cz/~tylecr1/facade/). Ein HF-Spiegel mit Angabe "MIT" ist Drittmetadatum und falsch gegenueber dem Original. — [atyun Spiegel](https://atyun.com/datasets/info/Xpitfire/cmp_facade.html?lang=en)
- **ECP:** 104 entzerrte Haussmann-Fassaden aus Paris, Lizenz nicht gefunden. — [arXiv 1606.06437](https://arxiv.org/pdf/1606.06437)
- **eTRIMS:** Uni Bonn, Zitierpflicht, keine explizite Lizenz gefunden. — [eTRIMS Image Database](https://www.ipb.uni-bonn.de/projects/etrims_db)
- **Hznu Facade (2025):** 624 Gebaeude in Hangzhou, 43.277 Fenster (im Mittel 69 je Bild), 6 Klassen (Gebaeude, Autos, Baeume, Fenster, Himmel, Tueren), mit Homographie-entzerrter Teilmenge, Mendeley Data 10.17632/k387xkyc5f.1. Artikel CC BY, Datensatzlizenz auf der Mendeley-Seite nicht geprueft. SegFormer und Grounded-SAM dienten nur als Annotationshilfe (laut Text war SegFormer fuer Fenster besser). — [PMC12361793](https://pmc.ncbi.nlm.nih.gov/articles/PMC12361793/)
- **RTFP (2023/24):** ViT-Pipeline plus Linien-Verfeinerung fuer Fassaden-Parsing, evaluiert auf ECP 2011, RueMonge 2014 und neuem Datensatz CFP. — [arXiv 2309.15523](https://arxiv.org/abs/2309.15523)
- **WWR mit SegFormer (2024):** erweitert CMP/ECP um Fenster- und Fassadenlabels zur Bestimmung des Fenster-Wand-Verhaeltnisses. — [arXiv 2406.02706](https://arxiv.org/pdf/2406.02706)
- **"Beyond Segmentation" (2026):** YOLOv8-S mit paarweisem Ausrichtungsverlust (gleiche Klasse, x1/x2 bzw. y1/y2 innerhalb T Pixeln) auf CMP (689 Fassaden-Crops, 80/10/10). Regelmaessigkeit wird per SVD-Score gemessen. Hoeheres Gewicht W ergibt regelmaessigere, aber schlechtere mAP@0.5 und gelegentlich verpasste Fenster. YOLOv11-S liegt nur ~0,1 % neben v8. Modelle unter beyond-segmentation.github.io, keine Lizenz genannt. Ultralytics-Basis bedeutet faktisch AGPL. — [arXiv 2604.09260](https://arxiv.org/html/2604.09260v1)
- **Thermal Image-to-3D Facade Parser (2025):** RetinaNet-R50 auf LSAA fuer Fenster. Der Artikel beklagt fehlende oeffentliche Benchmarks. — [arXiv 2508.04406](https://arxiv.org/html/2508.04406v1)
- **Scan2LoD3 / TUM-FAÇADE:** Raycasting und Bayes-Netz auf MLS-Punktwolken plus LoD2, um Oeffnungen (Fenster/Tueren) fuer LoD3 zu finden. TUM-FAÇADE (aus TUM-MLS-2016) hat 17 Fassadenklassen. Die Autoren veroeffentlichen Modelle, Wolken und Code, Lizenz nicht gefunden. — [arXiv 2305.06314](https://arxiv.org/pdf/2305.06314). Weiterer Datensatz TUM2TWIN (2025): [arXiv 2505.07396](https://arxiv.org/pdf/2505.07396)
- Facade R-CNN / Oxford RobotCar Facade (500 Strassenbilder, 5 Klassen). — [arXiv 2205.05912](https://arxiv.org/html/2205.05912)
- Die ISPRS-Studie nennt ECP, eTRIMS, Graz50, ArtDeco und CMP als oeffentliche Fassadendatensaetze und verweist auf Liu et al. 2020 (symmetrischer Verlust, bestraft nicht-rechteckige Fenster). Nach ihrem Fazit fehlen geeignete Trainingsdaten. — [Otepka et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/517/2026/isprs-archives-XLIX-B2-2026-517-2026.pdf)

### Inferences
- Fuer gotische und historische Fassaden wie das Martinstor (Boegen, Figuren, Stufengiebel, Erker) passen die Datensatzklassen kaum: CMP hat weder "arch" noch "oriel" noch "statue" ("deco" ist eine Sammelklasse), ECP ist rein Haussmann. Ein spezialisierter Parser deckt also hoechstens Fenster, Tuer, Balkon und Gesims ab.
- **Lizenzrisiko Share-Alike:** Ein auf CMP (CC BY-SA) trainiertes Gewicht koennte als "Bearbeitung" gelten, die Rechtslage ist offen. Sicherer: eigene, aus Pipeline-Fotos selbst annotierte Daten, Zero-Shot-Labels als Vorschlag mit Pruefung, Fine-Tune auf einem Apache-Detektor (GDINO/LLMDet/OmDet) oder SAM2-UNeXT.
- Die Regelmaessigkeitsidee (Ausrichtungsverlust/Gitter) aus "Beyond Segmentation" und Liu 2020 laesst sich ohne Training als Nachbearbeitung umsetzen: Detektionen auf Zeilen/Spalten clustern, Luecken im Raster als "fehlendes Fenster?" melden. Das passt zu unserer Fehlteile-/Zaehlpruefung.

### Gaps
- Graz50, ArtDeco, ECP: Lizenzen nicht gefunden.
- Keine 2024-2026-Arbeit mit offen lizenzierten Gewichten fuer Fassaden-Parsing gefunden. Keine fuer Klassen wie Erker, Gaube oder Stufengiebel.
- Lizenz von TUM-FAÇADE/Scan2LoD3 nicht bestaetigt (Projektseite sites.google.com/view/olafwysocki/papers/scan2lod3 nicht geoeffnet).

## 4. Zaehlgenauigkeit (Fenster je Fassade, Stufen eines Stufengiebels)

### Takeaway
Belegt ist: "Erst zeigen, dann zaehlen" (Point-then-count, Molmo) schlaegt direktes Zaehlen deutlich. Molmo zeigt auf PixMo-Count deutlich bessere Werte als GPT-4o/Claude 3.5. SAM 3 ist ausdruecklich fuer "alle Instanzen eines Begriffs" gebaut, Zaehl-Benchmarks dazu habe ich im README nicht gefunden. Zur Stufenzahl von Giebeln gibt es keine Quelle. Fuer unsere Regel 9 (Zaehlungen nur am Foto) ist das Modell ein Vorschlag mit markiertem Bild, kein Sollwert.

### Cited Findings
- Molmo-Ablation: Point-then-count 89,4 (CountBenchQA) / 86,3 (PixMo-Count), direktes Zaehlen 87,9 / 80,2, Count-then-point 81,5 / 77,6. — [Molmo & PixMo, arXiv 2409.17146](https://arxiv.org/pdf/2409.17146)
- PixMo-Count laut Sekundaerquelle: Molmo 79,6 % (kleinstes) bis 85,2 % (groesstes), GPT-4o 59,6 %, Claude 3.5 Sonnet 58,3 % (gegen das Paper verifizieren). — [Sean Trott, Deep Dive Molmo](https://seantrott.substack.com/p/deep-dive-molmo)
- Molmo2 (Video-Zaehlen): Molmo2-8B 49,7 % gegen Qwen3-VL-8B 47,0 %, nicht auf Einzelbilder uebertragbar. — [Molmo2 Review](https://liner.com/review/molmo2-open-weights-and-data-for-visionlanguage-models-with-video); [arXiv 2601.10611](https://arxiv.org/html/2601.10611v4)
- SITUATE (2026): synthetischer Zaehldatensatz, Qwen2.5-VL-7B nachtrainiert und gegen Molmo-7B-D auf PixMo-Count/CountBench/TallyQA evaluiert (Zahlen nicht abgerufen). — [arXiv 2602.00108](https://arxiv.org/pdf/2602.00108)
- SAM 3 liefert fuer einen Begriff jede passende Instanz (Gegensatz zu SAM 1/2). — [Roboflow: What is SAM 3](https://blog.roboflow.com/what-is-sam3/); [facebookresearch/sam3](https://github.com/facebookresearch/sam3)
- Hznu Facade: im Mittel 69 Fenster je Bild. Dichte Fensterraster sind der typische Fassadenfall. — [PMC12361793](https://pmc.ncbi.nlm.nih.gov/articles/PMC12361793/)

### Inferences
- **Zaehlen ueber Instanzen statt ueber VLM-Antworten:** Detektor/SAM 3 liefern Instanzen, die auf das Fassadenraster geclustert werden (Zeilen x Spalten). Daraus kommt die Zahl, mit markiertem Bild zur Sichtpruefung. Das entspricht dem Point-then-count-Prinzip und ist pruefbar (Z-Protokoll).
- **Stufengiebel:** Die Stufen sind keine Objekte, die Detektoren kennen. Robuster ist es, die Giebelkontur zu extrahieren (SAM-Maske "gable"/"roof" oder Kantenbild) und die Stufen geometrisch zu zaehlen (Treppen-Polylinie, Anzahl horizontaler Absaetze). Ein VLM (Qwen3-VL, Apache) koennte als zweite, unabhaengige Meinung dienen, gilt aber nur als Hinweis. Auch Molmo (Pointing auf "each step") ist eine Option, Lizenz siehe oben.
- Fuer OWLv2 gilt: Zahlen haengen stark an Score-Schwelle und NMS. Ohne Kalibrierung auf gezaehlten Referenzfassaden ist eine Zaehlung aus OWLv2 nicht belastbar.

### Gaps
- Keine veroeffentlichten Zaehlergebnisse (Fenster/Stufen) fuer OWLv2, GDINO oder SAM 3 auf Fassaden gefunden.
- Kein sauberer Vergleich Qwen2.5-/Qwen3-VL gegen Molmo auf CountBench/PixMo-Count aus Primaerquelle (Aggregator mit "74" fuer Qwen2.5-VL auf Pixmo val ohne Protokoll, verworfen).
- SAM-3-Zaehlmetriken (z. B. CountBench) nicht im README, das Paper nicht geprueft.

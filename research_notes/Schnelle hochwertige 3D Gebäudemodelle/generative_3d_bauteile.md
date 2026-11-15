# Generative Bild-zu-3D- und Mehrbild-zu-3D-Modelle fuer Bauteile historischer Architektur (H0, 1:87) - Stand 15.11.2026

Hinweise zur Lesart:
- "UNBELEGT" = Angabe stammt nur aus Zweitquellen (Blogs, Anbieter-Vergleichsseiten, Suchtreffer-Auszuege) und wurde nicht an der Primaerquelle geprueft.
- Die beiden frueheren Berichte (`reports/Foto 3D Pipeline Verbesserungen.md`, `reports/Foto 3D Pipeline weitere Optionen.md`) behandeln SfM/MVS-Tempo, GPS-Tore, LIMAP, Orthofoto-Stapel, RealityScan, MapAnything. Nichts davon wird hier wiederholt; generative 3D-Modelle kamen dort nicht vor.
- Recherche-Umfang: rund 30 Such-/Abrufschritte. Nicht jede im Auftrag genannte Software konnte an der Primaerquelle geprueft werden (siehe jeweils "Gaps").

## 1. Fuehrende offene und kommerzielle Systeme: Eingaben, Ausgaben, VRAM, Tempo, Preis, Lizenz

### Takeaway
Offene Spitzenmodelle (TRELLIS.2, Hunyuan3D 2.1, Direct3D-S2, Hi3D v1.0, SAM 3D Objects) verlangen offiziell 10-32 GB VRAM; auf 8 GB laufen nur Stable Fast 3D / SPAR3D (Low-VRAM-Modus) offiziell sowie TRELLIS.2 und Hunyuan3D ueber inoffizielle Quantisierungen (GGUF/INT8, nur 512er Aufloesung, unbelegt). Gehostete Dienste (Tripo, Meshy, Rodin) kosten grob 0,20-0,80 USD je Modell und liefern in 20-90 s; fuer das Projekt ist deshalb Miet-GPU oder API realistischer als der Laptop. Lizenzfalle: Die Tencent-Community-Lizenz von Hunyuan3D 2.1 gilt ausdruecklich NICHT in der EU.

### Cited Findings

**TRELLIS.2 (Microsoft, offen)**
- Erstveroeffentlichung des Repos 16.12.2025; Bild -> PBR-Mesh; offene Gewichte — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)
- Offizielle README: NVIDIA-GPU mit mindestens 24 GB noetig, geprueft auf A100/H100, nur Linux getestet; Aufloesungen 512^3 bis 1536^3; Export `.glb` mit PBR (base color, roughness, metallic, opacity), Texturgroesse im Beispiel 4096 — [github.com/microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- Tempo auf H100: 512^3 rund 3 s, 1024^3 rund 17 s, 1536^3 rund 60 s — [github.com/microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- Eingabe laut README: ein Einzelbild; Mehrbild-Eingabe wird nicht erwaehnt. Zusaetzlich ein Workflow "PBR-Textur fuer gegebenes Mesh" (`example_texturing.py`) — [github.com/microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- Die Darstellung "O-Voxel" kann offene Flaechen, nicht-mannigfaltige Geometrie und innere Hohlraeume abbilden; die README sagt NICHT, dass Ausgaben wasserdicht sind — [github.com/microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- Lizenz: Modell und Code MIT; Abhaengigkeiten nvdiffrast und nvdiffrec haben eigene Lizenzen — [github.com/microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2). Laut InstaSD stehen beide unter der NVIDIA Source Code License (nur nicht-kommerzielle Forschung/Evaluierung); die native ComfyUI-Integration habe beide Abhaengigkeiten entfernt (UNBELEGT an Primaerquelle) — [InstaSD](https://www.instasd.com/post/trellis-2-pixal3d-native-comfyui-guide)
- 8 GB: Community-GGUF-Builds sollen auf 8 GB laufen (Q4/Q5, 512er Aufloesung, Low-VRAM-Option, geschaetzt 3-6 min je Mesh auf RTX 3060 8 GB); ein anderer Beitrag nennt 6,0-6,5 GB Spitze mit einem ComfyUI-Fork. Alles SEO-Blogs/Social-Media, keine Bestaetigung von Microsoft (UNBELEGT) — [trellis2.app](https://trellis2.app/blog/trellis-2-low-vram), [X-Beitrag PixelArtistry](https://x.com/philippsieben/status/2047304575850356978)
- Widerspruechliche VRAM-Angaben in Zweitquellen (12 GB Minimum; 16 GB fuer 512^3 / 40 GB fuer 1024^3 / 80 GB fuer 1536^3) — nicht belastbar — [codesota](https://www.codesota.com/news/trellis-2-3d-generation)

**Hunyuan3D (Tencent)**
- Hunyuan3D 2.1 (13.06.2025): offen mit vollen Gewichten und Trainingscode; Hunyuan3D-Shape-v2-1 (3,3 Mrd. Parameter, Bild -> Form) und Hunyuan3D-Paint-v2-1 (2 Mrd., PBR-Textur fuer vorhandenes Mesh + Referenzbild). VRAM: 10 GB Form, 21 GB Textur, 29 GB zusammen — [github.com/Tencent-Hunyuan/Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- Lizenz "TENCENT HUNYUAN 3D 2.1 COMMUNITY LICENSE AGREEMENT": Territorium = weltweit AUSSER Europaeische Union, Vereinigtes Koenigreich, Suedkorea; die Vereinbarung gilt dort nicht. Ausserdem: ab 1 Mio. monatlich aktiver Nutzer Sonderlizenz noetig; Ausgaben duerfen nicht zum Training fremder KI-Modelle dienen; "Tencent claims no rights in Outputs You generate" — [LICENSE](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE)
- Hunyuan3D 2.0: Mini-Modell rund 5 GB fuer Form, gesamte Kette rund 12 GB (Zweitquelle) — [comfyui-wiki](https://comfyui-wiki.com/en/models/hunyuan3d)
- Hunyuan3D 3.0 erschien am 16.09.2025 auf Tencents eigener Plattform (bis 20 freie Generierungen/Tag), Bild-zu-3D mit bis zu 4 (bzw. 2-4) Mehransichtsbildern — [Tencent](https://www.tencent.com/en-us/articles/2202235.html), [ComfyUI-Blog](https://blog.comfy.org/p/hunyuan-3d-30-in-comfyui-state-of)
- Hunyuan 3.x ist NICHT als offener Checkpoint belegt; aeltere Endpunkte (HunyuanTo3D 2.5) sollten zum 20.10.2026 enden, Ersatz HY-3D-3.1 auf "TokenHub" — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026). Hunyuan 3.1 (gehostet, z. B. ueber Scenario) erweitert die Ansichten ueber die 4er-Grenze hinaus — [Scenario](https://www.scenario.com/models/hunyuan-3d-31-pro-multiview)
- Hunyuan3D-Omni (arXiv 2509.21245, baut auf 2.1 auf, 3,3 Mrd. Parameter, offen): nimmt neben dem Bild Punktwolken, Voxel, Bounding-Box (acht Eckpunkte, steuert Seitenverhaeltnis) oder Skelett als Bedingung; 10 GB VRAM laut Modellkarte; Aufruf `python3 inference.py --control_type point|voxel|bbox|pose` — [arXiv 2509.21245](https://arxiv.org/abs/2509.21245v1), [HF-Spiegel der Modellkarte](https://huggingface.co/Antided/Hunyuan3D-Omni)
- 8 GB: Drittanbieter-Erweiterung "Hunyuan3D 2.1 Low VRAM" mit INT8 "fuer GPUs mit 8 GB" (UNBELEGT, kein Upstream) — [github.com/Alefk1708/modly-hunyuan3d-21-lowvram](https://github.com/Alefk1708/modly-hunyuan3d-21-lowvram)
- "Hunyuan3D-Buffalo 1.0" (Paper August 2026) wird in einer Zeitleiste genannt, Freigabe nicht verifiziert — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)

**Stable Fast 3D / SPAR3D (Stability AI, offen)**
- SF3D: Einzelbild -> texturiertes, UV-abgewickeltes Mesh in 0,5 s auf GPU mit 7 GB VRAM — [Stability AI](https://stability.ai/news-updates/introducing-stable-fast-3d)
- SPAR3D: Standard 10,5 GB VRAM, Low-VRAM-Modus rund 7 GB (langsamer) — [github.com/Stability-AI/stable-point-aware-3d](https://github.com/Stability-AI/stable-point-aware-3d)
- Lizenz: Stability AI Community License; frei fuer Forschung, nicht-kommerziell und kommerziell bis 1 Mio. USD Jahresumsatz, darueber Enterprise-Lizenz — [HF stable-fast-3d](https://huggingface.co/stabilityai/stable-fast-3d), [Stability AI SPAR3D](https://stability.ai/news-updates/stable-point-aware-3d)

**Direct3D-S2 (NeurIPS 2025, offen)**
- Code MIT; rund 10 GB VRAM fuer 512er, rund 24 GB fuer 1024er Generierung; 512er Ausgabe gilt nur als Zwischenstufe (Zweitquellen, die die README zitieren) — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026), [Replicate](https://replicate.com/hcl14/direct3d_s2), Paper: [arXiv 2505.17412](https://arxiv.org/abs/2505.17412v2)

**Pixal3D (TencentARC, SIGGRAPH 2026, offen)**
- Baut auf Direct3D-S2 auf; hebt Pixelmerkmale per Rueckprojektion in 3D (direkte Pixel-zu-3D-Zuordnung); erzeugt das Objekt im Kamerarahmen des Eingabebilds statt in kanonischer Pose. Mehransichts-Inferenz (`inference_mv.py`, eigene Gewichte, Standard 2 Ansichten) seit September 2026 — [arXiv 2605.10922](https://arxiv.org/html/2605.10922v1), [github.com/TencentARC/Pixal3D](https://github.com/TencentARC/Pixal3D)
- Lizenz laut Zeitleiste MIT (UNBELEGT an LICENSE-Datei); VRAM nicht gefunden — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)

**Hi3DGen (ByteDance / Stable-X, offen)**
- "High-fidelity 3D Geometry Generation from Images via Normal Bridging": Bild -> Normalenkarte -> Geometrie, TRELLIS-Basis. Code MIT (Copyright Bytedance 2025); im Repo Stable3DGen wurden die NVIDIA-Abhaengigkeiten (kaolin, nvdiffrast, flexicube) entfernt, damit kommerzielle Nutzung moeglich ist — [github.com/Stable-X/Stable3DGen](https://github.com/Stable-X/Stable3DGen), [github.com/bytedance/Hi3DGen](https://github.com/bytedance/Hi3DGen)
- Lizenz der Gewichte (`Stable-X/trellis-normal-v0-1`) nicht an der Modellkarte geprueft (UNBELEGT); VRAM nicht gefunden.

**Hi3D v1.0 (ehemals Sparc3D / Hitem3D, offene Gewichte seit 23.10.2026)**
- Kein vollstaendiger Bild-zu-3D-Generator, sondern Geometrie-Verfeinerer: Eingabe Grob-Mesh + Referenzbild, Ausgabe hochaufgeloestes Mesh ohne Textur, bis 1536^3; trainiert auf rund 2 Mio. Assets; nur Inferenzcode — [Pandaily](https://pandaily.com/hi3d-v1-0-open-source-sparc3d-high-resolution-3d-geometry-refinement-1536), [orcarouter-Analyse](https://www.orcarouter.ai/blog/hi3d-v1-0-open-source-what-shipped), [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)
- Lizenz "Hi3D Open License Agreement 1.0" (eigene Lizenz; kommerzielle Nutzung laut einer Zweitquelle erlaubt, im grossen Massstab Sonderlizenz - Text nicht selbst gelesen, UNBELEGT) — [selfhostpilot](https://selfhostpilot.com/open-weights-vs-open-licence-checklist/)
- VRAM: 1536^3 nur auf einer 96-GB-Karte (NVIDIA H20) validiert; Minimum nicht veroeffentlicht; "mind. 10 GB" ist eine gerechnete, nicht gemessene Drittschaetzung (UNBELEGT) — [cpu3d](https://cpu3d.com/en/ai3d/hi3dv1-0/), [orcarouter-Analyse](https://www.orcarouter.ai/blog/hi3d-v1-0-open-source-what-shipped)
- Sparc3D selbst blieb Paper + Demo, Gewichte hinter dem Produkt Hitem3D — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)

**SAM 3D Objects (Meta, 19.11.2025, offen)**
- Einzelbild + Maske -> Mesh und Gaussians; offizielle Setup-Doku: Linux 64 Bit, NVIDIA-GPU mit mindestens 32 GB VRAM — [setup.md](https://github.com/facebookresearch/sam-3d-objects/blob/main/doc/setup.md)
- Praxis: Betreuer nennt V100 (32 GB) als kleinste zuverlaessige Karte; Nutzer berichten teils Erfolg, teils OOM auf 24 GB (RTX 4090); Speicher haengt an der Voxelzahl aus Stufe 1 — [Issue #6](https://github.com/facebookresearch/sam-3d-objects/issues/6)
- Ein ComfyUI-Wrapper wirbt mit 8 GB (RTX 2060) (UNBELEGT) — [github.com/DDS-3DPrintman/ComfyUI-SAM3DObjects-Low-Ram](https://github.com/DDS-3DPrintman/ComfyUI-SAM3DObjects-Low-Ram)
- Lizenz: eigene "SAM License" (kein Apache 2.0), gebuehrenfrei, mit Auflagen (Lizenzweitergabe, Verbot militaerischer Nutzung, kein Reverse Engineering) — [HF-Modellkarte](https://huggingface.co/facebook/sam-3d-objects), [Roboflow-Zusammenfassung](https://roboflow.com/model-licenses/segment-anything-3)

**Gehostete Dienste (geschlossen)**
- Tripo: P1.0/H3.1 angekuendigt 09.03.2026, P2.0 am 21.09.2026 — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026). Mehransichts-Endpunkt `POST /generation/multiview-to-model` (P-Serie) mit festen Plaetzen vorn/links/hinten/rechts, einzelne Plaetze duerfen leer bleiben; 2-4 Bilder — [Tripo Developers](https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/p), [ComfyUI-Doku](https://docs.comfy.org/built-in-nodes/TripoMultiviewToModelNode)
- Tripo-Preis (Zweitquellen, widerspruechlich): 20 Credits Bild-zu-3D, 1 Credit = 0,01 USD, texturiert bis 40 Credits; rund 0,20-0,30 USD je texturiertem Modell — [ModelsLab](https://modelslab.com/meshy-api-alternative), [Costbench](https://www.costbench.com/software/ai-3d-generation/tripo-ai/). Tempo 20-60 s — [3D AI Studio](https://www.3daistudio.com/3d-generator-ai-comparison-alternatives-guide/best-image-to-3d-tools-2026)
- Meshy: Meshy 6 (18.01.2026), Meshy 7 (10.08.2026), Meshy 7.1 (API 18.09.2026) — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026). Preis laut Zweitquelle: Bild-zu-3D 20 Credits ohne, 30 mit Textur; Pro 20 USD/Monat fuer 1000 Credits (rund 0,02 USD/Credit, also rund 0,40-0,60 USD je Modell) — [ModelsLab](https://modelslab.com/meshy-api-alternative), [Sloyd-Preisvergleich](https://www.sloyd.ai/blog/ai-3d-model-generator-pricing). Tempo 30-90 s — [3D AI Studio](https://www.3daistudio.com/3d-generator-ai-comparison-alternatives-guide/best-image-to-3d-tools-2026)
- Rodin (Hyper3D): Gen-2 am 01.10.2025, Gen-2.5 am 26.05.2026 — [Cinevva-Zeitleiste](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026). Ueber fal.ai 0,40 USD je Generierung (HighPack 3-fach), Mehrbild-Modus "concat" = mehrere Ansichten desselben Objekts, "fuse" = Merkmale verschiedener Objekte verschmelzen — [fal.ai](https://fal.ai/models/fal-ai/hyper3d/rodin). Gen-2.5-Extreme-High 0,80 USD — [Pixazo](https://www.pixazo.ai/models/hyper3d). Abo Business 120 USD/Monat — [Costbench](https://www.costbench.com/software/ai-3d-generation/rodin-hyper3d/). Obergrenze "bis fuenf Bilder" nur aus Drittquelle (UNBELEGT) — [3dtoolwiki](https://3dtoolwiki.com/tools/rodin)

**Geometrie-Benchmark (unabhaengig von den Anbietern)**
- RDT-3D-Paper (arXiv 2611.06141), Toys4K, ICP-ausgerichtete Chamfer-Distanz / F-Score@0.05: TRELLIS.2 0,0192 / 0,6636; TRELLIS 0,0216 / 0,6400; Hunyuan3D-2.1 0,0220 / 0,6389 — Abstaende klein — [arXiv 2611.06141](https://arxiv.org/html/2611.06141)

### Inferences
- F-Score um 0,64-0,66 bei Schwelle 0,05 (auf normierte Objektgroesse, nach ICP mit freier Skalierung) heisst: auch die besten offenen Einzelbild-Modelle treffen rund ein Drittel der Flaeche NICHT innerhalb von 5 % der Objektgroesse. Fuer ein 2 m breites Bauteil waeren 5 % schon 10 cm real bzw. 1,1 mm in H0 - das ist "plausibel", nicht "massgetreu".
- Auf dem 8-GB-Laptop offiziell lauffaehig sind nur SF3D und SPAR3D (Low-VRAM) - beides schnelle, aber grobe Modelle. Alles Hochwertige braucht eine Mietkarte mit 24 GB (TRELLIS.2, Direct3D-S2 1024) bis 32+ GB (SAM 3D) oder eine API. Bei Laufzeiten von Sekunden bis einer Minute je Teil kostet die Mietkarte je Teil nur Cent-Betraege; teuer ist die Einrichtung.
- Fuer ein Hobbyprojekt in Deutschland ist Hunyuan3D 2.1/Omni lokal lizenzrechtlich nicht gedeckt (EU ausgeschlossen); MIT-lizenzierte Alternativen: TRELLIS.2 (Abhaengigkeiten beachten), Direct3D-S2, Hi3DGen/Stable3DGen, ReconViaGen (siehe Abschnitt 2).

### Gaps
- InstantMesh, CRM, CSM, Luma Genie, CLAY und Nachfolger: in dieser Recherche keine Primaerquelle abgerufen. Aus Vorwissen (nicht belegt, bitte pruefen): InstantMesh Apache-2.0, CRM MIT, beide Stand 2024 und qualitativ von TRELLIS/Hunyuan ueberholt; CLAY ist die Forschungsgrundlage von Rodin und nicht offen. Zu CSM und Luma Genie wurden keine aktuellen (2026) Angaben gefunden.
- Offizielle Preislisten von Tripo, Meshy, Hyper3D wurden nicht direkt abgerufen; alle Preise stammen von Wiederverkaeufern/Vergleichsseiten und widersprechen sich teils.
- Lizenz/Nutzungsrechte an den AUSGABEN der gehosteten Dienste (kostenlose Stufen oft nur CC BY oder nicht-kommerziell) nicht geprueft.
- VRAM fuer Pixal3D, Hi3DGen, Hi3D v1.0 (unter 1536^3) nicht offiziell belegt. Lizenz von Hunyuan3D-Omni nicht geprueft (vermutlich gleiche Tencent-Lizenz wie 2.1).
- Kein unabhaengiger Benchmark gefunden, der Tripo/Rodin/Meshy an realen Objekten mit Chamfer/F-Score misst.

## 2. Treue zum echten Objekt: Halluzination, Mehrbild-Konsistenz, geometrie-konditionierte Verfahren

### Takeaway
Einzelbild-Generatoren erfinden die ungesehenen Seiten und verfehlen Ornamentdetails nachweislich; verlaesslicher sind (a) Verfahren, die mehrere echte Fotos einbeziehen (ReconViaGen = VGGT + TRELLIS, MIT; Pixal3D-Mehransicht; Tripo/Hunyuan/Rodin-Mehrbild) und (b) Verfahren, die ein vorhandenes Grob-Mesh oder eine Punktwolke als Bedingung nehmen (Hunyuan3D-Omni, Hi3D v1.0, MeshReGen, UltraShape, DetailGen3D). Keines davon nutzt unsere bekannten metrischen COLMAP-Posen direkt; belegte Genauigkeitszahlen an Architekturteilen gibt es nicht.

### Cited Findings

**Belege fuer Halluzination und Detailverlust**
- ReconViaGen-Abstract: generative Priors koennen "unsichtbare Teile halluzinieren"; "the stochastic nature of the inference process limits the accuracy and reliability of generation results" — [arXiv 2510.23306](https://arxiv.org/abs/2510.23306)
- Uebersichtsarbeit zu generativer KI in der Denkmal-Rekonstruktion: ein aus Mehransichten erzeugtes Modell der Nofretete-Bueste zeigt "substantial discrepancies" zum Original, Ornamente an Krone und Halskragen aehneln dem Original nur lose; dazu ein "Black-Box"-Problem gegenueber den Transparenzanforderungen wissenschaftlicher Rekonstruktion — [Heritage 9(7):246](https://doi.org/10.3390/heritage9070246)
- Oitijjo-3D (Street-View -> 3D fuer Kulturerbe): "minor imperfections" bei gekruemmten Kuppeln, feinen Ornamenten und spiegelnden Materialien — [arXiv 2511.00362](https://arxiv.org/html/2511.00362)
- Arbeit zu "harmful geometry" (Mai 2026, Hunyuan-3D-2.1, TripoSG, Trellis-1/2): die Modelle stuetzen sich stark auf grobe Geometrie-Priors statt auf Oberflaechentextur — [arXiv 2605.09606](https://arxiv.org/html/2605.09606v1)
- Pixal3D begruendet sich damit, dass bestehende Verfahren (TRELLIS, Hunyuan3D-2.1) Bilddetails nicht gut erhalten; Vergleich per CD, EMD, F-Score und menschlicher Bewertung der Bild-3D-Konsistenz (eigener Testsatz) — [arXiv 2605.10922](https://arxiv.org/html/2605.10922v1)
- Praktikerbericht: KI-Generatoren scheitern an feinen Strukturen (Haarstraehnen, Antennen, duenne Finger, kleine Schrift) - sie fehlen oder entstehen als nicht druckbare Geometrie; Gesichter und Haende bleiben am unzuverlaessigsten — [3DBite](https://3dbite.com/ai-tools-3d-model-generation-printing-2026/)
- Einzelbild-Pflanzenstudie: Hunyuan3D bestes Verfahren (CD 0,00515, F-Score 0,8597), scheitert aber weiter an feinen, verschachtelten Strukturen — [Plant Methods](https://link.springer.com/article/10.1186/s13007-025-01482-6)

**Verfahren mit mehreren echten Fotos**
- ReconViaGen (ICLR 2026): Mehransichts-Objektrekonstruktion "via Generation"; nutzt VGGT (posefreie Mehransichts-Rekonstruktion) als Rekonstruktions-Prior und TRELLIS als Generator; Ziel "complete and accurate 3D models consistent with input views". Offizielles Repo MIT, Training + Inferenz v0.2; Zweig v0.5 koppelt an TRELLIS.2 (hochaufgeloeste Meshes, PBR). Gewichte: `Stable-X/trellis-vggt-v0-1` — [github.com/GAP-LAB-CUHK-SZ/ReconViaGen](https://github.com/GAP-LAB-CUHK-SZ/ReconViaGen), [arXiv 2510.23306](https://arxiv.org/html/2510.23306v1), [HF Stable-X/trellis-vggt-v0-1](https://huggingface.co/Stable-X/trellis-vggt-v0-1)
- Fremdmessung (RecGen3D, 4 Eingabeansichten): Chamfer-L2 Toys4K ReconViaGen 0,0281 gegen TRELLIS-S 0,0309 / TRELLIS-M 0,0343; GSO 0,0290 gegen 0,0318 / 0,0391 — Verbesserung rund 10-25 %, kein Groessenordnungssprung — [arXiv 2604.01479](https://arxiv.org/pdf/2604.01479)
- Warnung zum Messprotokoll: Vorhersagen werden vor der Messung per skaliertem ICP auf die Wahrheit ausgerichtet; Chamfer-Werte haengen stark vom Protokoll ab — [ReconPlusGen, arXiv 2609.11129](https://arxiv.org/pdf/2609.11129)
- Pixal3D-Mehransicht: Rueckprojektion jeder Ansicht in ein pixelgenaues Merkmalsvolumen, Mittelung; vermeidet laut Autoren Kameraschaetzung — [arXiv 2605.10922](https://arxiv.org/html/2605.10922v1), [github.com/TencentARC/Pixal3D](https://github.com/TencentARC/Pixal3D)
- Tripo-Mehransicht: feste Blickrichtungen vorn/links/hinten/rechts (0/90/180/270 Grad), keine freien Posen — [Tripo Developers](https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/p), [Scenario-Doku](https://docs.scenario.com/get-started/generation/3d-model-generation/3d-model-generation-tripo-ai/)
- Hunyuan3D 3.0: 2-4 Mehransichtsbilder; 3.1 mehr — [ComfyUI-Blog](https://blog.comfy.org/p/hunyuan-3d-30-in-comfyui-state-of), [Scenario](https://www.scenario.com/models/hunyuan-3d-31-pro-multiview)
- Rodin "concat": mehrere Ansichten desselben Objekts — [fal.ai](https://fal.ai/models/fal-ai/hyper3d/rodin)
- Aeltere Feed-forward-Rekonstruktoren mit POSIERTEN Eingaben: MeshFormer (posierte Mehransichts-RGB- und Normalenbilder -> texturiertes Mesh in einem Durchlauf) — [arXiv 2408.10198](https://arxiv.org/html/2408.10198); GS-LRM (2-4 posierte Bilder -> Gaussians in 0,23 s auf A100) — [Projektseite](https://sai-bi.github.io/project/gs-lrm/); MeshLRM (4 Ansichten, Mesh in unter 1 s) — [arXiv 2404.12385](https://arxiv.org/pdf/2404.12385)

**Verfahren mit Grob-Mesh / Punktwolke / Normalen als Bedingung**
- Hunyuan3D-Omni: Punktwolke, Voxel oder Bounding-Box als Zusatzbedingung zum Bild; Bounding-Box steuert Seitenverhaeltnis und vermeidet duenne, entartete Geometrie; Voxel liefern Hinweise auf Massstab und Detail — [arXiv 2509.21245](https://arxiv.org/html/2509.21245v1)
- Hi3D v1.0: Grob-Mesh + Referenzbild -> verfeinerte Geometrie bis 1536^3 (siehe Abschnitt 1) — [Pandaily](https://pandaily.com/hi3d-v1-0-open-source-sparc3d-high-resolution-3d-geometry-refinement-1536)
- MeshReGen (arXiv 2604.28134): erzeugt aus Ausgangsform + einem Referenzbild eine detailreichere Form, die "pose and overall structure" der Grobform behaelt; funktioniert laut Autoren auch auf groben Blockouts; DiT auf VecSet-Latents. Projektseite nennt weder Zahlen noch Code-/Gewichtsfreigabe noch Lizenz — [Projektseite](https://geonyeong-park.github.io/meshregen/)
- UltraShape 1.0 (Dez. 2025): verfeinert an festen Voxelpositionen, die aus der Grobgeometrie stammen (Positionsanker per RoPE) — [Zusammenfassung](https://liner.com/review/ultrashape-10-highfidelity-3d-shape-generation-via-scalable-geometric-refinement)
- DetailGen3D (2024): generative Geometrie-Anreicherung grob -> fein — [arXiv 2411.16820](https://arxiv.org/html/2411.16820v3)
- AssetGen (arXiv 2605.26137, 2026): zweistufig; Verfeinerer nimmt Grob-Mesh und sagt dichteres Latent (16 384 Token) voraus, Oberflaechenpunkte des Grob-Mesh verankern die Token — [arXiv 2605.26137](https://arxiv.org/pdf/2605.26137)
- Hi3DGen: Normalenkarte als Zwischenschritt ("normal bridging") fuer feineres Relief als direkte Bild-zu-Form-Abbildung — [github.com/bytedance/Hi3DGen](https://github.com/bytedance/Hi3DGen)

### Inferences
- Die fuer das Projekt passendste Familie ist "Grob-Mesh + Referenzfoto -> Detail" (Hi3D v1.0, MeshReGen, UltraShape, Hunyuan3D-Omni), weil das parametrische Modell (Box, Erker-Grundkoerper) bzw. die dichte Wolke genau diese Grobform metrisch richtig liefert und der Generator nur das Relief ergaenzen muss. Die Lage/Proportion bleibt dann durch unsere Messung bestimmt, die Halluzination ist auf das Relief begrenzt.
- Zweitbeste Familie: ReconViaGen mit 4-8 ausgewaehlten, freigestellten Fotos eines Bauteils. Es schaetzt Posen selbst (VGGT) und ignoriert unsere COLMAP-Posen; das Ergebnis ist also nicht metrisch und muss nachtraeglich registriert werden (Abschnitt 3).
- Dienste mit festen Blickrichtungen (Tripo, Hunyuan 3.0) passen schlecht zu Fassadenteilen: von einem Erker im 2. Stock gibt es keine Rueck- und kaum reine Seitenansichten. Die Rueckseite ist bei Anbauteilen aber ohnehin die Wandebene - sie kann nach der Generierung plan abgeschnitten werden; die Halluzination der Rueckseite ist hier harmlos, die der Seitenflaechen nicht.
- Alle gefundenen Genauigkeitszahlen stammen von Spielzeug-/Objektdatensaetzen (Toys4K, GSO) mit skaliertem ICP. Fuer gotisches Masswerk, Fachwerk oder Wasserspeier gibt es keine Messung; eigene Stichprobe an einem Teil mit guter Wolkenabdeckung ist noetig.
- Wiederholbare Elemente mit harter Geometrie (Zifferblatt, Masswerk, Fachwerkbalken) sind fuer Generatoren unguenstig (Zaehl- und Symmetriefehler wahrscheinlich; passt zur Projektregel "Zaehlen nur am Foto") und fuer die vorhandene Fotokanten-/Parametrik-Methode guenstig. Organische Einzelstuecke (Wasserspeier, Statuen, Baldachine, Konsolen) sind umgekehrt die Staerke der Generatoren.

### Gaps
- Kein Verfahren gefunden, das bekannte metrische Kameraposen (K, R, t) vieler Fotos als harte Bedingung in einen generativen 3D-Prior einspeist und offen verfuegbar ist. MeshFormer/GS-LRM/MeshLRM nehmen posierte Bilder, wurden aber auf synthetischen Objektansichten trainiert; offene Gewichte und Lizenzen wurden nicht verifiziert (aus Vorwissen: GS-LRM und MeshLRM ohne offizielle Gewichte - unbelegt).
- LaRa und VGGT-Lizenz (kommerzieller Checkpoint) nicht recherchiert/gefunden.
- Keine quantitativen Angaben zu Hi3D v1.0, MeshReGen, UltraShape, Hunyuan3D-Omni, wie weit die Ausgabe von der Grobform abweicht (Abweichung in % der Objektgroesse).
- Keine Studie gefunden, die KI-generierte Architekturornamente direkt gegen Photogrammetrie/Laserscan vermisst.

## 3. Eigene Daten als Zwang: Skalieren, Registrieren, Render-und-Vergleich, automatische Ablehnung

### Takeaway
Die Literatur selbst arbeitet mit "skaliertem ICP" zwischen Generat und Referenz - genau das ist mit der dichten Wolke und den COLMAP-Kameras nachbaubar; eine fertige, veroeffentlichte Kette "Generat -> metrisch registrieren -> gegen Fotos pruefen -> ablehnen" wurde nicht gefunden. Der Zwang kann an zwei Stellen ansetzen: vor der Generierung (Bounding-Box/Punktwolke/Grob-Mesh als Bedingung) und danach (Aehnlichkeitstransformation + Tor).

### Cited Findings
- Bewertungsprotokolle richten jede Vorhersage per skaliertem ICP auf die Referenzform aus, bevor Chamfer/F-Score gemessen werden — [ReconPlusGen, arXiv 2609.11129](https://arxiv.org/pdf/2609.11129); ebenso "ICP-aligned Chamfer Distance and F-Score@0.05" — [RDT-3D, arXiv 2611.06141](https://arxiv.org/html/2611.06141)
- Bedingung vor der Generierung: Hunyuan3D-Omni kodiert die Bounding-Box als acht Eckpunkte (Seitenverhaeltnis/Skala) und akzeptiert Punktwolken sowie Voxel als Geometriehinweise — [arXiv 2509.21245](https://arxiv.org/html/2509.21245v1)
- Bedingung durch Grob-Mesh: Hi3D v1.0, MeshReGen, AssetGen-Verfeinerer verankern die Generierung an der Oberflaeche der Grobform — [Pandaily](https://pandaily.com/hi3d-v1-0-open-source-sparc3d-high-resolution-3d-geometry-refinement-1536), [MeshReGen](https://geonyeong-park.github.io/meshregen/), [arXiv 2605.26137](https://arxiv.org/pdf/2605.26137)
- Pixal3D erzeugt das Objekt im Kamerarahmen des Eingabebilds (nicht in kanonischer Pose) mit direkter Pixel-zu-3D-Zuordnung — [arXiv 2605.10922](https://arxiv.org/html/2605.10922v1)
- Texturierung fuer vorhandenes Mesh (falls ein Farbmodell gewuenscht ist): TRELLIS.2 `example_texturing.py`, Hunyuan3D-Paint-v2-1 (Mesh + Referenzbild) — [TRELLIS.2](https://github.com/microsoft/TRELLIS.2), [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- F1 gegen Referenzformen wird auch in der Forschung als Tor-Metrik benutzt — [arXiv 2605.09606](https://arxiv.org/html/2605.09606v1)

### Inferences
(Entwurf einer Kette aus vorhandenen Projektbausteinen; nichts davon ist als fertiges Werkzeug belegt.)
- Eingabe vorbereiten: Bauteil in 4-8 Fotos per Maske freistellen (Projektion des Bauteil-Quaders aus dem parametrischen Modell in die COLMAP-Kameras liefert die Maske/den Ausschnitt automatisch); moeglichst frontale + zwei schraege Ansichten; Wandhintergrund entfernen.
- Registrierung in drei Stufen: (1) Grobskala aus den am Foto gemessenen Bounding-Massen (`tools/foto_mass.py`) - 7 Freiheitsgrade der Aehnlichkeitstransformation, Start aus Quader-Hauptachsen; (2) skaliertes ICP gegen den Ausschnitt der dichten Wolke im Bauteil-Quader (GPU-Naechste-Nachbarn vorhanden: `tools/gpu_knn.py`); (3) Feinjustage ueber Silhouetten-/Kantenabgleich: Generat mit den bekannten Kameras rendern, Silhouette und Tiefenkanten gegen Fotokanten vergleichen.
- Tor (automatische Ablehnung), passend zu den Projektregeln "Foto-F1 als Tor, Wolke nur Lage-Veto": (a) Foto-Kanten-F1 des gerenderten Generats (`tools/teil_fotoform.py` / `tools/foto_diff.py`) muss ueber dem des bisherigen parametrischen Teils liegen; (b) Silhouetten-IoU je Kamera ueber Schwelle in ALLEN Ansichten, nicht nur der Eingabeansicht - Halluzinationen fallen in den nicht als Eingabe benutzten Fotos auf (Eingabe- und Prueffotos trennen, sonst Musterleck); (c) Wolken-Veto: Anteil der Generat-Flaeche, die weiter als Schwelle von der Wolke liegt, nur in von Kameras gesehenen Bereichen; (d) Restskala nach ICP muss zu den Fotomassen passen (Abweichung der drei Bounding-Masse); (e) Zaehl-Tor fuer wiederholte Elemente gegen `tools/foto_zaehlung.py`.
- Da die Generierung stochastisch ist und Sekunden bis eine Minute dauert, ist "N Seeds erzeugen, alle registrieren, den besten nach Foto-F1 behalten, sonst ablehnen" billig. Das Tor ist wichtiger als die Wahl des Generators.
- Anteilige Nicht-Aehnlichkeits-Verzerrung (Generat zu tief/zu flach): Statt nur einheitlicher Skala eine achsweise Skalierung auf die drei Fotomasse erlauben; alles darueber hinaus (freie Deformation) wuerde Fehler verstecken und sollte als Ablehnung zaehlen.
- Fuer Anbauteile: nach Registrierung mit der Wandebene des parametrischen Modells schneiden (manifold3d-Boolean) - das entfernt die halluzinierte Rueckseite und liefert eine saubere Fuegeflaeche.

### Gaps
- Kein veroeffentlichtes Werkzeug/Paper gefunden, das generierte Teile automatisch gegen kalibrierte Fotos prueft und ablehnt; Schwellenwerte muessen selbst kalibriert werden (Vorschlag: am vorhandenen, abgenommenen Teil eichen).
- Unklar, wie gut skaliertes ICP bei duennen Wolkenausschnitten (Erker im Obergeschoss, Kameraluecken) konvergiert; nicht belegt.
- Ob Pixal3Ds Kamerarahmen-Ausgabe eine direkte Uebernahme unserer K/R/t erlaubt (statt Nachregistrierung), wurde nicht geprueft.

## 4. Architektur-spezifische Generatoren: Fassaden, LoD3, Datensaetze, Fachwerk/Gotik

### Takeaway
Die 2026er LoD3-Forschung (AstraLOD3, SVI2LoD3, Texture2LoD3) rekonstruiert Fassadenoeffnungen (Fenster/Tueren) als strukturierte Stadtmodelle, nicht druckbares Ornamentrelief; fuer Fachwerk oder gotisches Detail wurde kein spezialisierter Generator und kein Datensatz gefunden. Fuer das Projekt taugen diese Arbeiten hoechstens als Gegenprobe fuer Fensterlagen.

### Cited Findings
- AstraLOD3 (arXiv 2609.28061, 23.09.2026): zero-shot, agentenbasierte LoD3-Rekonstruktion mit einem multimodalen Grundmodell; "structured LOD3 reconstruction can be formulated as a constrained agentic process rather than as a fixed pipeline" — [arXiv 2609.28061](https://arxiv.org/abs/2609.28061)
- SVI2LoD3 (arXiv 2608.29992, 30.08.2026): agentengetriebene Kette fuer LoD3-Fassadenoeffnungen aus freiwillig gesammelten Strassenbildern, mit neuer Metrik "Facade Feature Distance" — [arXiv 2608.29992](https://arxiv.org/abs/2608.29992)
- Texture2LoD3 (2025): LoD3 aus Panoramabildern — [arXiv 2504.05249](https://arxiv.org/pdf/2504.05249)
- FacaDiffy (2025): Diffusions-Inpainting ungesehener Fassadenteile — [arXiv 2502.14940](https://arxiv.org/pdf/2502.14940)
- ProxyBuild (arXiv 2609.23386): textgesteuerte strukturierte Gebaeudegenerierung mit "mesh-anchored procedural proxies" (nur Titel gesichtet, Inhalt nicht gelesen) — [arXiv 2609.23386](https://arxiv.org/pdf/2609.23386)
- Bild-zu-Bild-Uebersetzung fuer 2D-Fassadendarstellungen historischer Bauten (Arequipa): 50-58 % der Architekturbauteile korrekt erzeugt; Proportionsfehler bei Zierelementen — [Architecture 6(4):199](https://doi.org/10.3390/architecture6040199)
- Shp2gml: regelbasierte (Domaenenwissen) semantische Mehr-LoD-Modelle fuer Ming-/Qing-Bauten - Beispiel, dass bei stark regelhafter historischer Architektur prozedurale Ansaetze gewaehlt werden — [Int. J. Digital Earth](https://www.tandfonline.com/doi/full/10.1080/17538947.2025.2564910)
- Datensaetze: CMP Facade (606 annotierte Bilder, Klassen u. a. facade, molding, cornice) ist der uebliche Ausgangspunkt; weitere allgemeine Fassadendatensaetze (hyperspektral mit Materialklassen inkl. Holz; hochaufgeloester Fassadenparsing-Datensatz) — [Academia-Paper zu Orthofoto-Segmentierung](https://www.academia.edu/107619761/Semantic_Segmentation_for_Building_Fa%C3%A7ade_3D_Point_Cloud_from_2D_Orthophoto_Images_Using_Transfer_Learning), [arXiv 2212.02749](https://arxiv.org/pdf/2212.02749), [Data in Brief](https://www.sciencedirect.com/science/article/pii/S2352340925006742)
- Kein Fachwerk-Datensatz und nichts zu generativem/prozeduralem gotischem Masswerk in den Suchergebnissen — Negativbefund aus zwei Suchen (siehe Gaps).

### Inferences
- Architektur-spezifische KI ist heute semantisch (Was ist wo: Fenster, Tuer, Gesims), nicht geometrisch-detailtreu. Die Luecke "druckbares Ornament" fuellen eher die allgemeinen Objektgeneratoren aus Abschnitt 1/2, angewandt auf freigestellte Einzelbauteile.
- Fachwerk und Masswerk sind stark regelhafte, linienhafte Strukturen - dafuer ist die im Projekt vorhandene Kette (Mehrfoto-Kanten-Sweep -> `kanten_features.py` -> Generator-Features, flaches Relief als Extrusion) wahrscheinlich schneller UND treuer als jeder Generator; ein Generator braechte hier Zaehl-/Lagefehler ein.
- LoD3-Oeffnungsdetektoren koennten als billige unabhaengige Gegenprobe der Fensterraster dienen, loesen aber nicht das Detailproblem.

### Gaps
- Gotisches Masswerk (prozedural/generativ) wurde nur am Rand gesucht; es gibt aus der Computergrafik aeltere prozedurale Masswerk-Arbeiten (aus Vorwissen, unbelegt) - nicht recherchiert.
- Kein Befund zu Generatoren speziell fuer Dachlaternen, Zifferblaetter, Wasserspeier.
- AstraLOD3/SVI2LoD3: Code-Verfuegbarkeit, Lizenz und Genauigkeit nicht geprueft.

## 5. Druckbarkeit in 1:87: Mindestmasse, Wasserdichtheit, Reparatur, Relief-Ueberhoehung

### Takeaway
Generierte Meshes sind nicht verlaesslich wasserdicht (Meshy: 55 % direkt nach Export, 97 % Slicer-Durchlauf erst nach Auto-Reparatur; TRELLIS.2 garantiert es nicht), und feine Strukturen unter der Druckgrenze entstehen gar nicht oder undruckbar. Bei 1:87 entspricht die Harz-Grenze von 0,3 mm rund 26 mm am Original - der groesste Teil echten Ornamentreliefs liegt darunter und muss ueberhoeht oder weggelassen werden; dafuer gibt es kein generator-eigenes Werkzeug.

### Cited Findings
- Meshy-eigener Test (75 Modelle, Figuren): 97 % Bambu-Studio-Slicer-Durchlauf, 55 % vollstaendig wasserdicht direkt nach Export — [Meshy-Blog](https://www.meshy.ai/blog/best-ai-tools-for-3d-printing); die 97 % gelten erst nach dem Reparaturlauf — [3DBite](https://3dbite.com/ai-tools-3d-model-generation-printing-2026/)
- Meshy wirbt mit wasserdichten, mannigfaltigen Ausgaben und eingebauter Druckbarkeitspruefung mit Auto-Reparatur (Anbieterangabe) — [Meshy 3D Printing](https://www.meshy.ai/3d-printing)
- Wandstaerken-Schwellen laut Meshy-Leitfaden: unter 0,8 mm scheitert FDM, unter 0,3 mm Harz — [Meshy-Blog](https://www.meshy.ai/blog/best-ai-tools-for-3d-printing)
- Praktiker im Tripo-Blog: Harz "bis 0,5 mm moeglich, 0,8 mm sicheres Minimum"; kritische Masse vor dem Slicen um 102 % skalieren (Harzschrumpf); Wandstaerken-Analyse nutzen — [Tripo-Blog](https://www.tripo3d.ai/blog/explore/repo-3d-print)
- Tripo erzeuge wasserdichte Meshes mit wenig Nacharbeit, aber geringerer Detailaufloesung als Meshy bei komplexen organischen Formen — [3DBite](https://3dbite.com/ai-tools-3d-model-generation-printing-2026/)
- Hunyuan3D: laut Meshy-Vergleich (Wettbewerber!) keine Wasserdichtheits-Garantie, keine Druckwerkzeuge — [Meshy vs Hunyuan3D](https://www.meshy.ai/compare/meshy-vs-hunyuan3d)
- TRELLIS.2: O-Voxel bildet offene Flaechen, nicht-mannigfaltige Geometrie und innere Strukturen ab; keine Aussage zur Wasserdichtheit — [github.com/microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- Feinstrukturen unter einer gewissen Groesse "either fail to generate or generate as geometry that is not structurally printable" — [3DBite](https://3dbite.com/ai-tools-3d-model-generation-printing-2026/)
- Hi3D v1.0 wird ausdruecklich fuer 3D-Druck/physische Prototypen beworben (Social-Media-Aussage, UNBELEGT) — [X-Beitrag](https://x.com/itsPaulAi/status/2113887594597527577), STL-Workflow-Beschreibung — [image3d.io](https://image3d.io/blog/hi3d-1-0-open-source-stl-workflow/)

### Inferences
- Umrechnung (eigene Rechnung, Faktor 87): 0,3 mm Harz = 26 mm real; 0,4 mm FDM-Duese = 35 mm real; 0,8 mm = 70 mm real. Ein Wasserspeier (real rund 1 m lang) ist in H0 rund 11 mm - Kopf/Maul rund 2-3 mm; ein Zifferblatt-Ziffernstrich (real 3-5 cm) liegt an oder unter der Harzgrenze; Fachwerkbalken (real 15-25 cm) = 1,7-2,9 mm breit, aber Relieftiefe gegen Gefach (real 0-3 cm) = 0-0,35 mm, also ohne Ueberhoehung unsichtbar.
- Folge: Ein 1536^3-Generat liefert weit mehr Detail, als H0 drucken kann. Wichtiger als Maximalaufloesung ist die richtige GROBFORM plus gezielte Ueberhoehung. Das relativiert den VRAM-Bedarf: 512^3-1024^3 genuegt fuer ein 10-30 mm grosses Teil (1024 Voxel auf 30 mm = 0,03 mm Voxel, zehnfach feiner als die Harzgrenze).
- Vorschlag Nachbearbeitung mit vorhandenem Werkzeug (manifold3d ist im Projekt schon Generator-Kern): Generat -> voxel-/SDF-Remesh auf Zielaufloesung (macht wasserdicht, entfernt Innenflaechen) -> Mindestwandstaerke per Offset/Dilatation sichern -> Relief-Ueberhoehung als Verschiebung entlang der Flaechennormalen relativ zur registrierten Grobform (Hoehenfeld ueber Wandebene mit Faktor 1,5-3 skalieren; Faktor ist ANNAHME, am Probedruck eichen) -> Boolean mit Wandebene -> `druck.splitter_verwerfen`-Pruefung. Die im Auftrag genannten Werkzeuge (Blender 3D-Print Toolbox, MeshLab, PyMeshFix, Meshmixer) decken Pruefen/Reparieren/Verdicken ab; zu ihnen wurde in dieser Recherche keine eigene Quelle abgerufen.
- Die Relief-Ueberhoehung setzt voraus, dass Grobform und Generat registriert sind (Abschnitt 3) - ein weiterer Grund fuer den Weg "Grob-Mesh-konditioniert".

### Gaps
- Kein unabhaengiger, harzspezifischer Vergleich gefunden, welche Generate bei kleinen Massstaeben Merkmale behalten; die Mindestmass-Angaben stammen aus Anbieter- bzw. Einzelpersonen-Blogs.
- Keine Quelle zu Relief-Ueberhoehung fuer Modellbahn-Massstaebe im Zusammenhang mit KI-Generaten; Ueberhoehungsfaktoren sind Annahme.
- Blender 3D-Print Toolbox, MeshLab, PyMeshFix, Meshmixer: Funktionsumfang/Lizenzen nicht recherchiert (aus Vorwissen: Blender GPL, MeshLab GPL, PyMeshFix GPL-Kern MeshFix, manifold Apache-2.0, Meshmixer kostenlos aber eingestellt - unbelegt; siehe auch `modelle/LIZENZ_WERKZEUGE.md`).
- Wasserdichtheits-Quote fuer TRELLIS.2, Hunyuan3D, Direct3D-S2, Hi3D v1.0 nicht gemessen gefunden.

## 6. Kosten und Zeit je Teil, hybrider Workflow, gemeldete Fehlermodi

### Takeaway
Die reine Generierung kostet 0,20-0,80 USD (API) oder Sekunden bis rund eine Minute Rechenzeit auf einer gemieteten 24-80-GB-Karte; der Engpass ist nicht die Generierung, sondern Freistellen, Registrieren, Pruefen und Drucknachbearbeitung - realistisch Minuten bis wenige zehn Minuten je Teil, sobald die Kette steht. Sinnvoll ist ein Hybrid: Parametrik fuer Baukoerper und regelhafte Linien (Fachwerk, Masswerk, Zifferblatt), Generator nur fuer organische Einzelteile, immer hinter dem Foto-Tor.

### Cited Findings
- API-Preise: Rodin 0,40 USD je Generierung (fal.ai), Gen-2.5-Extreme-High 0,80 USD; Tripo rund 0,20-0,30 USD; Meshy rund 0,60 USD je texturiertem Modell (Schaetzung eines Wettbewerbers, Oktober 2026) — [fal.ai](https://fal.ai/models/fal-ai/hyper3d/rodin), [Pixazo](https://www.pixazo.ai/models/hyper3d), [ModelsLab](https://modelslab.com/meshy-api-alternative)
- Generierzeiten: Tripo 20-60 s, Meshy 30-90 s — [3D AI Studio](https://www.3daistudio.com/3d-generator-ai-comparison-alternatives-guide/best-image-to-3d-tools-2026); TRELLIS.2 3 s / 17 s / 60 s (512/1024/1536, H100) — [TRELLIS.2](https://github.com/microsoft/TRELLIS.2); SF3D 0,5 s — [Stability AI](https://stability.ai/news-updates/introducing-stable-fast-3d); TRELLIS.2-GGUF auf 8 GB geschaetzt 3-6 min (UNBELEGT) — [trellis2.app](https://trellis2.app/blog/trellis-2-low-vram)
- Hunyuan 3.0 auf Tencents Plattform: bis 20 freie Generierungen/Tag — [Tencent](https://www.tencent.com/en-us/articles/2202235.html)
- Fehlermodi: Halluzination ungesehener Teile und Stochastik (ReconViaGen); Ornamente nur lose aehnlich (Nofretete-Beispiel); Proportionsfehler bei Zierelementen (Fassaden-Bilduebersetzung); feine Strukturen fehlen oder sind undruckbar, Gesichter/Haende inkonsistent (3DBite); nur 55 % der Meshy-Exporte direkt wasserdicht — [arXiv 2510.23306](https://arxiv.org/abs/2510.23306), [Heritage](https://doi.org/10.3390/heritage9070246), [Architecture](https://doi.org/10.3390/architecture6040199), [3DBite](https://3dbite.com/ai-tools-3d-model-generation-printing-2026/), [Meshy-Blog](https://www.meshy.ai/blog/best-ai-tools-for-3d-printing)
- Einrichtungshuerden offener Modelle: SAM 3D braucht 32 GB und freigeschalteten HF-Zugang; Hi3D v1.0 braucht flash-attn ohne Rueckfall, CUDA 12.0-12.5, nur 96-GB-Karte validiert; TRELLIS.2 nur Linux/24 GB getestet — [setup.md SAM 3D](https://github.com/facebookresearch/sam-3d-objects/blob/main/doc/setup.md), [cpu3d Hi3D](https://cpu3d.com/en/ai3d/hi3dv1-0/), [TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- Die meisten "Vergleiche 2026" stammen von Anbietern oder Wiederverkaeufern (3D AI Studio verkauft Zugang, Meshy vergleicht sich selbst) — [3D AI Studio](https://www.3daistudio.com/3d-generator-ai-comparison-alternatives-guide/best-image-to-3d-tools-2026), [Meshy vs Tripo](https://www.meshy.ai/compare/meshy-vs-tripo)

### Inferences
Vorschlag hybrider Workflow (Reihenfolge nach Nutzen je Aufwand; Zeiten sind Schaetzungen, nicht gemessen):
- Stufe 0 - Schnelltest ohne Einrichtung (1-2 Stunden, unter 5 USD): Ein organisches Teil mit guter Wolkenabdeckung (z. B. ein Wasserspeier oder eine Konsole am Schwabentor) waehlen, 3-4 freigestellte Fotos an Rodin (concat) und Tripo (multiview) per API schicken sowie ein Einzelbild an eine gehostete TRELLIS.2-Demo. Je 3 Seeds. Ergebnis per skaliertem ICP an die Wolke legen und mit `foto_diff.py` gegen NICHT verwendete Fotos pruefen. Das beantwortet die Kernfrage "treu oder nur plausibel" am eigenen Objekt billiger als jede weitere Recherche.
- Stufe 1 - offene Kette auf Mietkarte (1 Tag Einrichtung, 24-48 GB): ReconViaGen v0.5 (MIT, VGGT + TRELLIS.2) fuer Mehrfoto-Eingabe; alternativ TRELLIS.2 pur. Dazu das Tor aus Abschnitt 3 als Skript im Repo. Pro Teil danach geschaetzt 5-15 min (Maske aus Quaderprojektion automatisch, 4-8 Seeds, Registrierung, Tor, Sichtpruefung neben Referenzfoto).
- Stufe 2 - Grob-Mesh-konditioniert (wenn Stufe 1 an Proportionen scheitert): parametrischen Grundkoerper des Teils (oder Poisson-Mesh des Wolkenausschnitts) + bestes Frontalfoto an Hi3D v1.0 (eigene Lizenz, 1024^3 zuerst, grosse Mietkarte) oder - falls Code erscheint - MeshReGen. Hunyuan3D-Omni waere technisch ideal (Bounding-Box/Punktwolke), ist in der EU aber lizenzrechtlich ausgeschlossen.
- Stufe 3 - Druckaufbereitung automatisch: Remesh, Wandebene schneiden, Mindeststaerke, Relief-Ueberhoehung, Splitterpruefung; Abnahme wie bisher (`bauen_abnehmen.sh`, `fehlteile_finden.py`, `teile_lage_pruefen.py`). Generierte Teile als eigene Feature-Art mit `beleg(seite, element, quelle)` und dem Vermerk "generiert, Foto-F1 = x" fuehren; Halluzinationsanteile als `ANNAHME:` kennzeichnen.
- Aufteilung nach Bauteilart: Generator fuer Wasserspeier, Statuen, Baldachine, Konsolen, Wappen, Kreuzblumen; Parametrik/Fotokanten fuer Fachwerk, Masswerk, Zifferblatt, Fensterraster, Dachlaterne (Rotations-/Prismenkoerper); Erker als Mischform (parametrischer Koerper, generierte Konsolen/Brustungsreliefs).
- Kostenrahmen je generiertem Teil: API 0,20-0,80 USD x 4-8 Seeds = rund 1-6 USD; Mietkarte bei Minutenlaufzeit im Cent-Bereich je Teil plus Leerlauf waehrend der Einrichtung. Gegenueber "Tage je Bauteil" ist das Kostenrisiko vernachlaessigbar; das Risiko liegt in der Treue, nicht im Geld.
- Wegen der kleinen H0-Druckgrenze ist die Fehlertoleranz gnaedig: Formabweichungen unter rund 2-3 cm real (0,3 mm H0) sind im Druck unsichtbar. Sichtbar bleiben Proportions-, Zaehl- und Silhouettenfehler - genau die, die das Foto-Tor misst.

### Gaps
- Keine Praktikerberichte gefunden, die generative 3D-Modelle fuer Modellbahn-/Architekturmodellbau in kleinen Massstaeben mit Messung dokumentieren; Zeit je Teil ist daher Schaetzung.
- Aktuelle Mietpreise fuer 24-/48-/80-GB-Karten wurden hier nicht recherchiert (siehe frueheren Bericht "weitere Optionen", Punkt 11, fuer Mietkarten allgemein).
- Ob ReconViaGen v0.5 auf 24 GB laeuft, ist nicht belegt (Training lief auf 8x A800 80 GB; Inferenzbedarf nicht gefunden).
- Nutzungsbedingungen der gehosteten Dienste zum Hochladen eigener Fotos (Trainingsnutzung durch den Anbieter) nicht geprueft.

# Recherche: Kanten/Linien aus Mehrfachansichten (Fassade Kaufhaus) – Stand 2026-11-09

Methodik: Code-Lizenzen per GitHub-API geprueft (belegt). Aussagen zu Gewichten/Trainingsdaten-Lizenzen und Qualitaet teils aus Wissen/Papern, als "(unverifiziert)" markiert. Vor Verkauf: Lizenz der GEWICHTE und der TRAININGSDATEN je Modell einzeln pruefen (Code-MIT heisst nicht, dass Gewichte frei sind).

## 1. Kanten-/Linienerkenner

| Verfahren | Art | Code-Lizenz (geprueft) | Gewichte lokal | Bemerkung fuer Fassaden |
|---|---|---|---|---|
| DeepLSD ([cvg/DeepLSD](https://github.com/cvg/DeepLSD), [arXiv 2212.07766](https://arxiv.org/abs/2212.07766)) | Liniensegmente, Hybrid (Feldvorhersage + klassisches LSD), subpixelgenau | MIT | ja (Checkpoint-Download, polybox), pip-Paket `deeplsd` aus Git | Sehr gerade, praezise Segmente; gut fuer Fensterrahmen/Gesimse. Trainingsdaten (MegaDepth/Wireframe) Lizenz pruefen |
| ScaleLSD ([ant-research/scalelsd](https://github.com/ant-research/scalelsd), [arXiv 2506.09369](https://arxiv.org/abs/2506.09369), CVPR 2025) | Liniensegmente, selbstueberwacht auf Millionen Bildern | MIT | ja (laut Autoren im Repo) | Aktuell staerkster Allround-Detektor, robuster als DeepLSD/HAWPv3 laut Paper (unverifiziert, nicht selbst gemessen). Erste Wahl zum Testen |
| HAWP/HAWPv3 ([cherubicXN/hawp](https://github.com/cherubicXN/hawp)) | Wireframe (Linien + Junctions), pip `hawp` | MIT | ja | Gut fuer Struktur/Junctions; auf Innenraum-Wireframe trainiert, Aussen weniger |
| SOLD2 ([cvg/SOLD2](https://github.com/cvg/SOLD2)) | Linien + Deskriptoren (Matching!) | MIT | ja; auch in kornia (`kornia.feature.SOLD2`, unverifiziert) | Nutzbar fuer Linienmatching zwischen Fotos |
| GlueStick ([cvg/GlueStick](https://github.com/cvg/GlueStick)) | Punkt+Linien-Matching (GNN) | MIT | ja | Matching, kein Detektor; fuer Line-BA/Zuordnung |
| M-LSD ([navervision/mlsd](https://github.com/navervision/mlsd)) | schneller Linien-Detektor | Apache-2.0 | ja | Leichtgewicht, geringere Genauigkeit |
| DexiNed ([xavysp/DexiNed](https://github.com/xavysp/DexiNed)) | dichte Kantenkarte, auch in kornia | MIT (Code) | ja, auch via kornia (unverifiziert) | Duenne, saubere Kantenkarten, gut fuer Architekturfotos; Datensatz BIPED |
| TEED ([xavysp/TEED](https://github.com/xavysp/TEED)) | winziges Kantennetz (58k Param.) | MIT | ja | Schnell, aehnlich DexiNed; Kantenkarte statt Segmente |
| PiDiNet/HED/EDTER | dichte Kantenkarten | nicht geprueft (PiDiNet MIT/EDTER i. d. R. Forschung; HED-Gewichte Caffe, Lizenz unklar) | ja | Aelter; kein Vorteil gegenueber DexiNed/TEED. BSDS-Trainingsdaten = Forschung -> kommerziell pruefen |
| LETR | Transformer-Linien | nicht geprueft | ja | Schwer, kein klarer Gewinn |
| SAM-Kanten / DINOv2 / Depth-Anything-Normalen | Foundation | SAM Apache-2.0, DINOv2 Apache-2.0 (unverifiziert); Depth Anything V2: nur Small Apache, Base/Large/Giant CC-BY-NC (**NC markieren**, unverifiziert) | ja (HF) | Nicht als Kantenerkenner gedacht; Maskenrand/Normalenspruenge sind weich. Nur als Zusatzsignal (Ebenen-/Segmentgrenzen) |

Einschaetzung: Fuer gerade Linien ScaleLSD und DeepLSD (subpixel), fuer Kantenkarten (Bogenraender!) DexiNed/TEED. Segmentdetektoren liefern fuer Bogen nur Polygonstuecke, Kantenkarten + Kurvenfit sind dort besser.

## 2. Multi-View-Fusion und Posenfehler

- **LIMAP** ([cvg/limap](https://github.com/cvg/limap), [arXiv 2303.17504](https://arxiv.org/abs/2303.17504), BSD-3): Linientriangulation aus bekannten Posen (+ optional Detektor wie DeepLSD/SOLD2/GlueStick), Line-Track-Bildung, Line-BA, Nutzung von Punkt-/VP-/Parallel-/Orthogonalitaets-Constraints. Direkt passend: Posen liegen vor. pip-Install nutzt C++/COLMAP/Ceres-Bau (aufwendig, Python 3.12 evtl. Reibung).
- **Line3D++** ([manhofer/Line3Dpp](https://github.com/manhofer/Line3Dpp), MPL-2.0 = Dateilevel-Copyleft, kommerziell nutzbar): klassische Linien-Rekonstruktion mit Bildpaar-Konsistenz; CPU, C++. LIMAP-Paper nennt es als Baseline.
- **3D-Kantenfelder:** EdgeGaussians ([arXiv 2409.12886](https://arxiv.org/abs/2409.12886), Repo kunalchelani/EdgeGaussians: **keine Lizenz** angegeben -> nicht kommerziell nutzen ohne Rueckfrage); SketchSplat ([arXiv 2503.14786](https://arxiv.org/abs/2503.14786), ICCV 2025, [Projekt](https://oceanying.github.io/SketchSplat)): parametrische Linien/Kurven direkt aus Kantenkarten, differenzierbar, GPU. NEF/EdgeGS: Neural Edge Fields, langsam (unverifiziert). Aufwand und Risiko hoch (Trainings je Szene, Gaussian-Splatting-Abhaengigkeiten, Lizenz Gaussian-Rasterizer INRIA nicht-kommerziell -> pruefen!).
- **Parallaxe-/Posenfehler allgemein:** (a) Nicht pixelweise stapeln, sondern 3D-Linien triangulieren und BA/Reprojektion robust (RANSAC/Median ueber Tracks) – genau LIMAP. (b) Bei Ebenen-Ortho: Foto-zu-Referenz-Feinregistrierung je Foto (ECC `cv2.findTransformECC` mit Homographie/Affin, oder Phasenkorrelation/kornia `ImageRegistrator`) auf Kantenkarten statt Grauwerten, DANN Stapeln. Parallaxe von Elementen vor/hinter der Ebene (Erker, Fensterlaibung) bleibt; nur Elemente in der Ebene stapeln, Tiefenversatz-Elemente eigene Ebene (haben Sie bereits so). (c) Posen per Line-BA mitverfeinern (LIMAP bietet Line-/Point-Joint-BA).

## 3. Fassaden-spezifisch

- **Rektifizierung + VP/Manhattan:** Fluchtpunkte aus den langen Segmenten (J-Linkage/RANSAC; LIMAP enthaelt VP-Schaetzung; Alternativen: NeurVPS, DeepLSD-Zubehoer `vp`); danach Linien auf 2 Hauptrichtungen einrasten (horizontal/vertikal), Positionen clustern. Kostenlos, grosser Gewinn fuer "gerade Kanten".
- **Regularitaet:** Fensterraster per 1D-Periodizitaetsanalyse (Autokorrelation der Kantenprojektion auf x/y) und Snap auf gemeinsame Gitterlinien; Klassiker "Symmetry/Repetition" in Fassadenparsing.
- **Planar-Segmentierung:** RANSAC/Region Growing auf der Wolke (Open3D `segment_plane`, Lizenz MIT) liefert Fassaden-/Gesimsebenen; Kanten = Schnitt benachbarter Ebenen (stabiler als Bildkanten).
- **Fassadenparsing:** Datensaetze CMP Facade DB, ECP (Ecole Centrale Paris), ParisArtDeco; Netze (FacadeNet-Varianten, DeepFacade) – Gewichte oft nur Forschung, auf Renaissance/Handyfotos schlecht uebertragbar (unverifiziert). Regelbasiert/Shape Grammars (CGA, Split-Grammatiken, Mueller et al. 2007) eignen sich als Zielmodell, nicht als Detektor; Parameter koennen aus den Kanten gefittet werden.
- **Bogen:** Kreisbogen/Ellipse an Kantenkarten-Punkte fitten (RANSAC), nicht Segmente.

## 4. Empfehlung (Aufwand/Gewinn)

1. **VP/Manhattan-Einrasten + Gitter-Regularisierung auf dem besten Einzelfoto-Ergebnis**, ergaenzt um ScaleLSD oder DeepLSD statt/neben LSD (beide MIT). Install: `pip install git+https://github.com/cvg/DeepLSD` bzw. ScaleLSD-Repo in venv-seg (torch vorhanden), Checkpoint lokal ablegen. Aufwand klein, Gewinn gross. Risiko: Gewichte-/Trainingsdatenlizenz vor Verkauf pruefen; VP-Einrasten falsch bei schiefen Bauteilen (nur Toleranz +-2 Grad).
2. **Edge-Ausrichtung je Foto vor dem Abstimmen**: ECC/Phasenkorrelation auf DexiNed/TEED-Kantenkarten (Ortho-Ausschnitt gegen Referenzfoto-Ortho), danach erst Voting. Install: opencv bzw. kornia (vorhanden), DexiNed ueber kornia oder Repo. Aufwand klein-mittel, Gewinn mittel (behebt Posenrest wenige cm -> Kanten schmieren weniger). Risiko: Parallaxe nicht mit Homographie loesbar; Konvergenz nur bei guter Startlage.
3. **LIMAP (Linientriangulation + Line-BA) mit den vorhandenen Posen**, Detektor DeepLSD/ScaleLSD-Segmente. Liefert echte 3D-Linien statt Ortho-Stapeln und umgeht Parallaxe grundsaetzlich; Ebenen-Schnitt/Wolke als Zusatzconstraint. Install: Build aus Quelle (COLMAP/Ceres/pybind, BSD-3), Python 3.12 evtl. anpassen; Docker/conda bei Problemen. Aufwand mittel-hoch, Gewinn hoch, besonders fuer Gesimse/Erkerkanten ausserhalb der Ebene. Risiko: Build, 440 Fotos x Linien = RAM/Zeit (Teilmenge nutzen), wenig GPU-Nutzen (Triangulation CPU; Detektion GPU).

Zurueckgestellt: SketchSplat/EdgeGaussians (Szenentraining, Lizenzunklarheit, GS-Rasterizer-Lizenz), Fassadenparsing-Netze (Domaenenluecke), Foundation-Modelle (kein Kantenziel).

## Quellen
- https://arxiv.org/abs/2212.07766, https://github.com/cvg/DeepLSD
- https://arxiv.org/abs/2506.09369, https://github.com/ant-research/scalelsd
- https://arxiv.org/abs/2303.17504, https://github.com/cvg/limap
- https://github.com/manhofer/Line3Dpp
- https://arxiv.org/abs/2409.12886 (EdgeGaussians), https://arxiv.org/abs/2503.14786 (SketchSplat)
- https://github.com/xavysp/DexiNed, https://github.com/xavysp/TEED, https://github.com/cherubicXN/hawp, https://github.com/cvg/SOLD2, https://github.com/cvg/GlueStick, https://github.com/navervision/mlsd

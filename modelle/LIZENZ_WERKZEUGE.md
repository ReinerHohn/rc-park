# Lizenz-Register: Werkzeuge und Daten (für späteren Verkauf der Bausätze)

Ziel des Projekts schließt Verkauf ein. **Wo etwas nur "nichtkommerziell" erlaubt ist, steht es hier rot (⚠).**
Stand 2026-10-31. **Geprüft** = in dieser Sitzung an der Quelle gelesen. **ungeprüft** = aus meinem Wissen, vor Verkauf selbst nachsehen.
Das ist keine Rechtsberatung. Offen ist immer, ob Messwerte/Ergebnisse, die mit einem NC-Werkzeug *abgeleitet* wurden, kommerziell nutzbar sind.

## ⚠ Werkzeuge, bei denen die Lizenz (noch) nicht zu kommerzieller Nutzung passt
| Werkzeug | Lizenz | Status | Wo genutzt | Was tun vor Verkauf |
|---|---|---|---|---|
| **Doppelgangers** (Cai et al. ICCV 2023, Code + Gewichte `doppelgangers_classifier_loftr.pt`) | **MIT** (geprüft 2026-11-19, LICENSE im Repo + GitHub-API) ; Trainingsbilder Wikimedia (ungeprüft, ob das die Gewichte einschränkt) | ok | `tools/doppelgaenger_paare.py`, `tools/seiten_erkennen.py` (Seitenverwechslung); `/media/oem/scan/doppelgangers/` | Gewichte-Lizenz vor Verkauf nachsehen; Ergebnis ist nur ein Paarfilter (keine Geometrie daraus) |
| **LoFTR** (kornia `pretrained='outdoor'`) | Apache 2.0 (Code kornia/LoFTR, ungeprüft für die Gewichte: MegaDepth-Training) | ok / ungeprüft | Zuordnungen für den Doppelgangers-Prüfer | vor Verkauf Gewichte-Lizenz nachsehen |
| **Doppelgangers++** (2024, MASt3R-Merkmale) | MASt3R **CC BY-NC-SA 4.0** (Websuche 2026-11-19, ungeprüft an der Quelle) | ⚠ nicht verwendet | – | nicht einsetzen |
| **VGGT-1B** (Meta, Gewichte `facebook/VGGT-1B`) | **CC BY-NC 4.0** (geprüft, HF-API) | ⚠ nur Forschung; Nutzer hat am 2026-10-31 "nur zur Forschung testen" gewählt | geplanter Fototest `/media/oem/scan/vggt/` | Ergebnisse nur als Hinweis verwenden, nichts daraus ins Produkt übernehmen, bis Lizenz geklärt. Alternative: `VGGT-1B-Commercial` (geprüft: `gated: manual`, Lizenz "other", Antrag nötig) |
| MASt3R / DUSt3R (Naver) | CC BY-NC-SA (ungeprüft) | ⚠ noch nicht benutzt | – | nicht verwenden, bis geprüft |
| Depth Anything V2 (größere Modelle) | CC BY-NC (ungeprüft; kleinste Variante Apache-2.0, ungeprüft) | ⚠ noch nicht benutzt | – | nur kleine Variante oder anderes Modell, nach Prüfung |
| nvdiffrast (NVIDIA) | NVIDIA Source Code License, nichtkommerziell (ungeprüft) | ⚠ noch nicht benutzt | – | vor Einsatz prüfen; Alternative PyTorch3D / Mitsuba 3 (BSD, ungeprüft) |
| Metric3D v2, MoGe-2, Depth Pro | je eigene Lizenz (ungeprüft) | noch nicht benutzt | – | vor Einsatz prüfen |
| Meshroom "nubia" Kameradatenbank / sonstige Fremdmodelle | – | keine NC-Bindung bekannt | – | – |

## Datenquellen (genutzt)
| Commons `Aerial View - Freiburg im Breisgau-Innenstadt1.jpg` (Foto 060) | **CC BY 3.0** (geprüft) | ✓ kommerziell erlaubt | Urheber nennen; einzige Quelle für die Westwand |
| Commons `Blick vom Schlossberg ... mit Martinstor.jpg` (Foto 061) | **CC BY-SA 3.0** (geprüft) | ✓ als Messvorlage | **ShareAlike**: Bild nicht in den Bausatz, nur Maße daraus |
| Quelle | Lizenz | Status | Auflage |
|---|---|---|---|
| LGL BW DOM1, DGM1, DGM025, LoD2, DOP20 | Datenlizenz Deutschland – Namensnennung – 2.0 (geprüft, aus LGL/BW-Seiten) | ✓ kommerziell erlaubt | "Datenquelle: LGL, www.lgl-bw.de" im Bausatz/Anleitung nennen |
| LGL Laserscandaten ALS (Rohpunkte) | "Open Data" laut LGL, Lizenztext nicht genannt (geprüft) | nicht bezogen | bei Bestellung Lizenzbedingungen erfragen (Entwurf `LGL_BESTELLUNG_ALS3.txt` fragt danach) |
| OpenStreetMap (OSM-Maße/Footprints) | ODbL (ungeprüft) | ✓ mit Namensnennung/Share-Alike für abgeleitete *Datenbanken* | Quelle nennen |
| Wikimedia-Commons-Fotos Martinstor (`daten/martinstor/fotos/`, 60 Stück) | je Datei: CC BY-SA 4.0 (22), CC BY-SA 3.0 (17), CC BY 4.0 (7), CC BY 3.0 (5), CC BY-SA 2.0 (4), Public domain (3), "Attribution" (2) (geprüft, `manifest.json`) | ✓ als Messvorlage; **Fotos selbst nicht in den Bausatz** | Share-Alike-Fotos nur als Grundlage für Maße, nicht kopieren; Urheber im Anhang nennen |
| Bauforschung BW, Texte | – | nur Maßangabe gelesen | – |
| YouTube-Videos Martinstor/Freiburg (`/media/oem/scan/rc-park_daten/martinstor/videos/`, Frames in `video_frames/`) | Standard-YouTube-Lizenz (urheberrechtlich geschuetzt); nur 1 Zeitraffer CC BY (nicht genutzt). Drohnenclips: Kanal 'Black Forest Stock' (Stockmaterial, Wasserzeichen) | ⚠ nur private Messvorlage (2026-11-02) | Frames NICHT ins Repo, NICHT verteilen; vor Verkauf Rechte beim Anbieter klaeren oder Masse aus lizenzfreien Quellen belegen. Werkzeug: tools/video_frames.py, tools/video_sfm.py |
| MASt3R/DUSt3R, MVSAnywhere, Inria-3DGS (+2DGS, GOF, RaDe-GS, SuGaR), VGGT-1B Standard, Building3D-Datensatz, ETH3D, Tanks and Temples | NC bzw. Forschungslizenz laut Recherche 2026-11-02 (teils nur Sekundaerquellen) | ⚠ nur zum Testen | nicht in ein Verkaufsprodukt; vor Einsatz LICENSE an der Primaerquelle lesen |
| MapAnything (Apache-Gewichte `map-anything-apache`), Depth-Anything-3 (BASE/SMALL/METRIC-LARGE), SAM 2, Grounding-DINO, hloc/ALIKED/DISK/RoMa | laut Recherche Apache-2.0/MIT/BSD (Gewichte je Modell, GIANT/LARGE/NESTED und `map-anything` sind NC) | ? vor Einsatz pruefen | noch nicht eingebaut; Details Roadmap |
| VGGT-1B-Commercial | `vggt-aup-license` (kommerziell ausser Militaer, Zugang gesperrt/Meta-Login) | ? Lizenztext lesen | noch nicht eingebaut |
| CGAL/PolyFit/City3D | GPL v3, City3D braucht Gurobi (kommerzielle Lizenz) | ⚠ meiden fuer Verkauf | Alternative: eigenes RANSAC/Open3D, 2.5D Dual Contouring (MIT) |
| Mapillary-Bilder | **CC BY-NC-SA** laut Terms of Use (Stand 2024-02-15), NICHT BY-SA (Recherche 2026-11-01) | ⚠ nicht benutzen | für ein Verkaufsprodukt unbrauchbar; ausserdem erreicht Street-Level die verdeckten Turmseiten ohnehin nicht |

## Werkzeuge, die kommerziell unkritisch sind (Stand ungeprüft)
manifold3d (Apache-2.0), trimesh (MIT), numpy/scipy/scikit-image (BSD), PyTorch (BSD), OpenCV (Apache-2.0), shapely (BSD),
COLMAP (BSD), PrusaSlicer (AGPL; **erzeugte G-Code-Dateien sind frei**), OpenMVS (AGPL-3.0, Ergebnisse frei).
Eigener Code (`tools/`, `modelle/*_gen.py`) gehört dem Projekt.
Pose-Prior-Buendelausgleich (`pycolmap.create_pose_prior_bundle_adjuster`, `PosePrior`, genutzt in `tools/sfm_gps_ausgleich.py`, 22.11.2026): COLMAP-Quelltext `estimators/bundle_adjustment_ceres.cc` traegt `SPDX-License-Identifier: BSD-3-Clause` (an der Quelle gelesen, eigener Bau 4.3.dev ce2b5ab); Ceres Solver BSD-3 (nicht an der Quelle geprueft). Verkaufstauglich.

## Testmodus (Nutzerfreigabe 2026-10-31)
Alles darf zum **Testen** benutzt werden, auch die ⚠-Werkzeuge. Jedes benutzte Werkzeug wird hier mit Datum und Zweck eingetragen.
Ergebnisse daraus sind "nur Test" und nicht Teil des Verkaufsprodukts.

### Benutzt (Test)
| Datum | Werkzeug | Lizenz | Zweck | Ergebnis ins Produkt? |
|---|---|---|---|---|
| 2026-10-31 | VGGT-1B (Gewichte `/media/oem/scan/vggt/gewichte`, Code `/media/oem/scan/vggt/repo`) | CC BY-NC 4.0 | Fototest: Kameralage + Punktwolke aus Commons-Fotos, Maßabgleich mit Modell | nein (nur Test) |
| 2026-11-01 | **LightGlue** (Code + Gewichte `aliked_lightglue_v0-1_arxiv.pth`, installiert aus `github.com/cvg/LightGlue` in `/media/oem/scan/venv-seg`, Gewichte in `~/.cache/torch/hub/checkpoints/`) | **Apache-2.0** (geprüft: LICENSE-Datei im Paket + README "pre-trained weights of LightGlue and the code ... Apache-2.0") | Merkmalszuordnung Luftbild gegen Strassenfotos (`tools/lg_match.py`, `tools/sfm_netz.py --matcher lightglue/hybrid`), Register AK | ✓ erlaubt; Ergebnis aber verworfen (Netz wird verbogen) |
| 2026-11-01 | **ALIKED** (Extraktor, Gewichte `aliked-n16.pth` von `github.com/Shiaoming/ALIKED`) | **BSD-3-Clause** (geprüft: Quellkopf `lightglue/aliked.py` + README) | wie oben | ✓ erlaubt (Namensnennung/Lizenztext beilegen) |
| 2026-11-01 | DISK (Extraktor, in LightGlue enthalten, nicht benutzt) | Apache-2.0 (README, Treffer) | Alternative zu ALIKED | ✓ |
| 2026-11-01 | **SuperPoint** (in LightGlue enthalten) | **restriktiv (Magic Leap, nicht kommerziell)** laut README | **bewusst NICHT benutzt** - in `tools/lg_match.py` nicht waehlbar | ⚠ nein |
| 2026-11-17 | **Depth Anything V2 Small** (`depth-anything/Depth-Anything-V2-Small-hf`, Cache `/media/oem/scan/hf_depth`, ueber transformers) | **Apache-2.0** (geprueft: HF-API cardData.license) | `tools/relief_aus_fotos_mono.py`: Feinrelief (Steine, Fugen) aus entzerrten Fassadenfotos, Massstab/Lage vom Scan | ✓ erlaubt. Dabei geprueft und NICHT benutzt: DSINE (Imperial-Lizenz, nur Forschung, LICENSE gelesen) ⚠; Marigold-Normals v1-1 (openrail++, HF-API) ?; StableNormal v0-1 (Apache-2.0 laut HF-API, baut aber auf SD2/openrail++) ?; MoGe-2 vitl-normal (MIT laut HF-API und LICENSE; Installation aus git in dieser Sitzung nicht erlaubt worden) ✓ Kandidat |
| 2026-11-01 | kornia, kornia-rs, opencv-python, matplotlib (LightGlue-Abhaengigkeiten) | Apache-2.0 / Apache-2.0 / Apache-2.0 / PSF-basiert (ungeprüft) | Laufzeit | ✓ |

## Recherche 2026-11-01: Werkzeuge fuer "Foto -> parametrisches Modell" (vor Benutzung selbst nachlesen)
Quellenstand wie angegeben; "geprueft" heisst: Lizenzdatei/Lizenzseite gelesen, "Treffer" heisst: nur ueber Suchtreffer belegt.
Keine Rechtsberatung - vor dem Verkauf jede Zeile selbst nachlesen.

| Werkzeug | Lizenz | Verkauf | Stand |
|---|---|---|---|
| nvdiffrast | NVIDIA Source Code License, "research or evaluation purposes only" | ⚠ **nein** | geprueft (LICENSE.txt) |
| Kaolin | Apache-2.0, aber `kaolin/non_commercial/` unter NVIDIA SCL; Diff-Rendering nutzt nvdiffrast | ⚠ Vorsicht | Treffer |
| PyTorch3D | BSD-3-Clause | ✓ | geprueft |
| Mitsuba 3 | BSD-3-Clause + "Enhancements"-Zusatz | ✓ | geprueft (LICENSE) |
| SAM 1 / SAM 2 | Apache-2.0 | ✓ | Treffer |
| SAM 3 | Meta SAM License: royalty-free kommerziell, Ausschluss Militaer/Waffen/ITAR/Sanktionen, Attribution bei Publikation, Meta kann Bedingungen aendern | ✓ mit Auflage | Treffer |
| Ultralytics YOLOv8 | AGPL-3.0 oder kommerzielle Lizenz | ⚠ vor Nutzung klaeren | **ungeprueft** |
| CityEngine SDK / PyPRT | Esri Terms of Use: frei nur privat/edu/nicht-kommerziell; Redistribution untersagt | ⚠ **nein** | Treffer |
| ShapeML (Grammatik-Interpreter, Burg/Bauernhof-Grammatiken) | GPL-3.0 | Werkzeug GPL, erzeugte Modelle frei (wie PrusaSlicer) | Treffer |
| Hunyuan3D 2.x | Tencent Community License - **Territorium schliesst EU/UK/KR aus** | ⚠ **nein** | ungeprueft |
| TRELLIS.2 | Modell/Code MIT, aber NC-Abhaengigkeiten (nvdiffrast, RMBG-2.0) | ⚠ nur ohne diese | ungeprueft |
| 3DGS / 2DGS / GOF, SuperPoint+SuperGlue, MASt3R, MeshAnything, VGGT-1B | Forschungslizenzen | ⚠ **nein** | Treffer |
| GLOMAP, LightGlue, ALIKED, DISK, RoMa, gsplat (Apache, 2DGS ab 1.4), MapAnything (Apache-Gewichte) | permissiv | ✓ | Treffer |
| Metashape Standard (179 $) | Agisoft-Lizenzseite: nur Edu-Lizenzen verbieten kommerzielle Nutzung | EULA vor Verkauf lesen | Treffer |
| RealityScan 2.0 (Epic) | frei unter 1 Mio. $ Jahresumsatz | ✓ | Treffer |
| Marktplatz-Assets (Fab, Sketchfab, BlenderKit, TurboSquid) | Standardlizenzen erlauben Nutzung IM Produkt, nicht die Weitergabe des Modells/der STL | ⚠ **nein** fuer Bausatzverkauf | Einschaetzung |

## Regel
Neues Werkzeug/Modell → hier eintragen, **bevor** Ergebnisse ins Produkt (STL, Anleitung, Zahlen im Bausatz) wandern.
NC-Modelle nur zur Forschung; was im Verkaufsprodukt steckt, muss aus lizenzfreien Quellen (Laser, Fotos als Messvorlage, eigener Generator) belegbar sein.

## Nachtrag 2026-11-05 (Qualitaetsstufe 3/4, Recherche-Agent + eigene Pruefung)
| Werkzeug / Daten | Lizenz | Status | Wo genutzt | Quelle der Angabe |
|---|---|---|---|---|
| OWLv2 `google/owlv2-base-patch16-ensemble` (Zero-Shot-Erkenner) | Apache-2.0 (Modellkarte) | ✓ eingebaut | tools/fassade_parsing.py (Qualitaetsstufe 3) | Treffer, vor Verkauf Modellkarte lesen |
| pycma `cma` 4.5.0 | BSD-3-Clause | ✓ eingebaut | geplante Stufe 4 (gemeinsame Optimierung) | geprueft: Paket-Metadaten |
| CMP Facade DB | **CC BY-SA** | nur zum Bewerten, NICHT zum Trainieren (ShareAlike koennte Gewichte binden) | – | geprueft (Recherche-Agent, cmp.felk.cvut.cz/~tylecr1/facade) |
| Gewichte auf CMP trainiert (z. B. `Xpitfire/segformer-finetuned-segments-cmp-facade` in tools/fenster_ml.py) | unklar (ShareAlike der Trainingsdaten) | ⚠ nicht ins Produkt | tools/fenster_ml.py (alt) | Einschaetzung |
| PGSR, MILo, Pi3/Pi3X, Depth Anything V2 Base/Large/Giant | NC / nur Forschung | ⚠ nur zum Testen | – | PGSR geprueft, Rest Treffer |
| Marigold v1-1 | OpenRAIL++-M (kommerziell mit Nutzungsauflagen); v1-0 Apache-2.0 | ? | – | Treffer |
| MoGe-2 ViT-L | Code MIT, Gewichte laut Mirrors MIT | ? vor Einsatz pruefen | – | Treffer |
| Metric3D | widerspruechlich (BSD-2 / "non-commercial") | ⚠ meiden bis geklaert | – | Treffer |
| DINOv3 | eigene Meta-Lizenz (Pflichthinweis, Kuendigungsrecht) | ⚠ umstaendlich; DINOv2 Apache | – | geprueft (Recherche-Agent) |
| **FlexGlue** (cvg/FlexGlue v0.1, in COLMAP seit 1.11.2026) | Code + Matcher/Deskriptor-Koepfe MIT; Grundnetz DINOv3-ConvNeXt-B unter DINOv3 License (an der Quelle gelesen 2026-11-19: Nutzung inkl. kommerziell erlaubt; verboten Militaer/Waffen/ITAR, Exportverstoesse, Rueckentwicklung; Weitergabe der GEWICHTE nur mit Lizenztext) | ✓ fuer Verkaufsmodelle (wir geben nur Modelle, keine Gewichte weiter) | Test Seitenverwechslung Martinstor `/media/oem/rcdaten/tmp/flexglue` | geprueft |
| **LoMa** (COLMAP LOMA_B/R/L/G, Gewichte github.com/davnords/storage `loma_*.onnx`) | laut Recherche 2026-11-19 auch auf ScanNet++/Map-free/Mapillary-Tiefen trainiert = Lizenzfalle; Autoren bieten seit 26.09.2026 getrennt `commercial_loma_B/L/G.pt` (nur .pt, ONNX-Export noetig); DINOv2 selbst Apache-2.0 | ⚠ COLMAP-Standardgewichte NICHT fuer Verkauf, bis an der Quelle geprueft | – | Recherche-Agent, Download-URL in resources.h bestaetigt |
| PolyFit / KSR (CGAL) / City3D | GPL (bindet nur Weitergabe der Software, nicht erzeugte Modelle); City3D braucht Gurobi | ✓ als Werkzeug denkbar | – | Treffer |
| **Fototextur** | Textur aus CC-BY-SA-Fotos wird ShareAlike; Mapillary NC; YouTube geschuetzt | ⚠ Textur/Farbe nur aus CC-BY/PD/eigenen Fotos | geplante Farbstufe | Einschaetzung |

## Nachtrag 2026-11-05 (G4: Stadt Freiburg, Daten getrennt von Code)
| Daten / Code | Lizenz | Status | Wo genutzt | Quelle der Angabe |
|---|---|---|---|---|
| Stadt-Freiburg-LoD2 CityGML `20261007_Freiburg_LoD2.gml` (1.610.391.847 B, Datei-Stand 2026-10-07, creationDate 2025-12-03; Datenplatte `/media/oem/scan/rc-park_daten/freiburg_stadt/lod2/`) | **DL-DE BY 2.0**, Vermerk "Datengrundlage: Stadt Freiburg, www.freiburg.de" (Metadatensatz nennt Zusatz fuer OpenStreetMap-Verwendung, dort nachlesen) | ✓ geprueft (Metadaten gelesen 2026-11-05); Vermerk in Beipackzettel/Shop | `tools/stadt_lod2_schneiden.py` -> `modelle/<objekt>/stadt_lod2.json` (nur Vergleich/Beobachtung, kein Generator) | https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/1c576440-e5e1-4095-bff1-a14d76cec6f4 ; Download https://geoportal.freiburg.de/stadtmodell/20261007_Freiburg_LoD2.gml |
| Stadtmesh Freiburg 2025 (Cesium 3D Tiles, `https://3d.freiburg.de/datasource-data/2025_befliegung/22_Mesh3D_Cesium/`), Kacheln unter `/media/oem/scan/rc-park_daten/freiburg_stadt/mesh/<objekt>/` | **UNGEKLAERT** (Metadatensatz nennt fuer die 3D-Tilesets DL-DE BY 2.0, widerspricht sich aber selbst: "ohne Textur der Fassaden" vs. texturierte Variante verlinkt; keine Open-Data-Erklaerung fuer das 2025-Mesh gefunden; Viewer-Hinweise Nr. 1/2 nicht abrufbar) | ⚠ NUR Pruefreferenz (Overlay, Kontur-Diff, Sichtvergleich); Mesh-Geometrie NICHT in den Generator; Datei nur unter `audit/referenz_stadtmesh/`; Anfrage vermessung@freiburg.de beim Nutzer ausstehend | `tools/stadtmesh_laden.py`, `tools/stadtmesh_vergleich.py` | Metadatensatz (s. o.), tileset.json HTTP 200 2026-11-05 (ohne Anmeldung) |
| `tools/stadt_lod2_schneiden.py`, `tools/stadtmesh_laden.py`, `tools/stadtmesh_vergleich.py` (Code, eigen) | eigener Code; Abhaengigkeiten shapely (BSD-3), trimesh (MIT), numpy, opencv | ✓ unkritisch | s. o. | Paket-Lizenzen, ungeprueft im Detail |
| Open3D 0.20 (Poisson, MIT) in der vorhandenen venv-mesh, pymeshfix (GPL-3 Wrapper um MeshFix, nur als Testwerkzeug im Vergleichslauf), trimesh (MIT); `tools/beweis_ansatz*.py` (eigener Code) | Open3D MIT, trimesh MIT, pymeshfix GPL-3 | ✓ (Open3D/trimesh) / NC-aehnlich pruefen (pymeshfix nur Test) | Beweislauf CM, 2026-11-05 | pymeshfix vor Verkauf nicht in die Pipeline uebernehmen |
| `tools/kanten_3d.py`, `tools/ebenen_modell.py`, `tools/test_ebenen_modell.py`, `tools/s8_kaufhaus.py` (eigener Code); OpenCV 5.0 LSD (BSD-3), torch (BSD), manifold3d (Apache-2), trimesh (MIT), scipy (BSD) | alle permissiv | ✓ unkritisch | LIMAP/PolyFit/CGAL-KSR bewusst NICHT eingesetzt (Installierbarkeit, GPL), DeepLSD ungeprueft | S8, Register CQ |
| 2026-11-06 S10 `tools/kanten_pipelines.py`, `tools/test_kanten_pipelines.py`, `tools/kanten_blatt.py` (eigener Code); P1/P2 nur OpenCV (Apache-2.0)/numpy/scikit-image (BSD-3) | permissiv | ✓ unkritisch | Paket-Lizenzen, nicht im Detail nachgelesen |
| 2026-11-06 S10 P3 DexiNed (Code kornia `kornia.models.dexined`, Apache-2.0; Originalcode xavysp/DexiNed MIT); Gewichte `kornia/dexined/DexiNed_BIPED_10.pth` (HF), trainiert auf BIPED | Code ✓; **Gewichte: BIPED-Datensatzlizenz nicht geprueft/unklar** | ⚠ nur zum Testen (NC angenommen), vor Verkauf BIPED-Lizenz klaeren oder auf TEED/PiDiNet-Gewichte mit eigener Lizenzpruefung wechseln | Treffer (Quellcode-Kopfzeile gelesen), Gewichtslizenz **ungeprueft** |
| 2026-11-06 S10 P4 SAM ViT-B `facebook/sam-vit-base` via transformers 5.22 (SamModel) | Apache-2.0 (Code + Gewichte laut Model-Card; SA-1B-Trainingsdaten nur Forschung/Meta-Lizenz fuer den Datensatz, nicht fuer das Modell) | ✓ (Hinweis SA-1B) | Treffer, Model-Card nicht im Detail gelesen |
| 2026-11-06 S10 Teil B Kandidat EMAP (cvg/EMAP) / NEF | EMAP: README nennt MIT fuer die Mehrheit, Basis NeuS/NeuralUDF/MeshUDF nicht einzeln geprueft; NEF nicht geprueft. NICHT eingebaut; Eigenbau tools/kanten_feld3d.py (eigener Code) | (MIT, unvollstaendig) | nicht verwendet |

## Nachtrag 2026-11-06 (Recherche Gaussian-Splatting-Mesh, noch NICHT eingesetzt)
| Werkzeug | Lizenz (laut Recherche, Quellen in `modelle/archiv/RECHERCHE_2026-11-06_METHODEN.md`) | Status |
|---|---|---|
| 2DGS Original (hbb1), PGSR (zju3dv), MILo, GOF, 3DGS Inria | Forschungs-/Nicht-kommerzielle Lizenz (PGSR nur ueber Index "other" gesehen, LICENSE.md vor Einsatz lesen) | ⚠ NUR Test (Stufe A), nie in die Verkaufs-Pipeline |
| gsplat (nerfstudio) | Apache-2.0 | ✓ fuer Stufe B (Eigenbau); 2DGS-Training/Mesh-Extraktion dort nicht dokumentiert |
| Depth Anything 3 | BASE/SMALL/METRIC/MONO Apache-2.0; GIANT/LARGE/NESTED CC BY-NC | nur BASE/METRIC erlaubt; PyPI-Name ungeprueft |
| MoGe | Code MIT, Gewichtslizenz OFFEN | ungeprueft |
| SAM2 | Apache-2.0 (Code+Gewichte laut Recherche; SA-1B nur Forschung) | ✓ (Hinweis SA-1B) |
| OpenMVS | AGPL-3.0 | Code nicht ins Produkt (Register CP: Ansatz bereits verworfen) |
| Open3D TSDF | MIT | ✓ |

## Nachtrag 2026-11-06 (SegFormer-B4 ADE20K, Handy-Masken)
| Werkzeug / Gewichte | Lizenz | Status | Wo genutzt | Quelle der Angabe |
|---|---|---|---|---|
| `nvidia/segformer-b4-finetuned-ade-512-512` (Gewichte), Trainingsdaten scene_parse_150 = ADE20K | Modellkarte: `license: other` (NVIDIA SegFormer-Lizenz, im Original-Repo als nicht kommerziell bekannt; ADE20K-Daten ebenfalls Forschungsbedingungen) | ⚠ nur zum Testen / als Zwischenschritt (Masken fliessen nur in SfM-Merkmalsauswahl, nicht in STL/Textur); vor Verkauf Wortlaut pruefen oder durch Apache/MIT-Segmentierer ersetzen | tools/video_masken.py, tools/gebaeude_segment.py, tools/handy_masken.py | Modellkarte per curl 2026-11-06 (nur der Eintrag "other" belegt; NC-Einordnung = Einschaetzung, Lizenztext nicht gelesen) |

## Nachtrag 2026-11-06 (OWLv2, Handy-Masken v2, Register DI)
| Werkzeug / Gewichte | Lizenz | Status | Wo genutzt | Quelle der Angabe |
|---|---|---|---|---|
| `google/owlv2-base-patch16-ensemble` (Gewichte, HF-Cache `models--google--owlv2-base-patch16-ensemble`), Code transformers `Owlv2ForObjectDetection` | Apache-2.0 (Modellkarte/Paper OWLv2; vom Auftrag so vorgegeben, Modellkarte in dieser Sitzung NICHT erneut abgerufen) | ✓ vorbehaltlich Modellkarte; Trainingsdaten (WebLI-Pseudolabels) nicht geprueft | tools/handy_masken_v2.py (Zusatz Marktplanen, nur Masken fuer SfM-Merkmalsauswahl) | Auftrag; Verifikation der Karte offen |
| `tools/handy_masken_v2.py`, `tools/handy_masken_vergleich.py`, `tools/test_handy_masken_v2.py` | eigener Code; opencv, numpy, torch, torchvision (NMS) | ✓ unkritisch | - | - |
| SAM2 | Apache-2.0 laut Recherche, aber Gewichte NICHT im Cache und NICHT geladen (Datenplatte ~10 GB frei) | nicht eingesetzt | - | - |

## Nachtrag 7.11. (Recherche modelle/archiv/RECHERCHE_2026-11-07_MESH_KANTEN.md, Quelle Subagent aus Repo-Seiten/Suchtreffern - vor Verkauf LICENSE-Dateien selbst lesen)
- OpenMVS (unser Netz-Sieger Delaunay+GraphCut, RefineMesh): AGPL-3.0 -> fuer Verkauf kritisch, nur Testwerkzeug.
- CGAL Alpha_wrap_3 / KSR / PolyFit: GPL-3.0+ oder kommerziell (GeometryFactory); City3D GPL-3 -> nur Test.
- 2DGS / MILo / GOF: nicht-kommerzielle Gaussian-Splatting-Lizenz (2DGS unklar); nvdiffrast: NVIDIA Source Code License. PyTorch3D vermutlich BSD-3 (ungeprueft).
- Frei: LIMAP (BSD-3), manifold3d (Apache-2.0), fTetWild (MPL-2.0 laut Index; Original-TetWild GPL). Ungeprueft: Line3D++, Instant Meshes, PlanarSplatting-Codestand.
- 7.11. Nutzerfreigabe: Web-Bilder inkl. Google Maps/Earth/Street View nur fuer privaten Machbarkeitstest; vor Veroeffentlichung/Verkauf jede Bildlizenz (LIZENZ_BILDER.json) pruefen, Google-Inhalte voraussichtlich nicht freigebbar.
- 7.11. Fenster-Recherche (Agent, Quelle modelle/archiv/RECHERCHE_2026-11-07_FENSTER.md): pycma BSD-3 (geprueft), PyTorch3D BSD-3 (geprueft), scipy BSD-3; nvdiffrast NUR nicht-kommerziell (geprueft) -> nicht fuer Verkauf; Optuna/nevergrad aus Gedaechtnis, vor Einsatz pruefen.
- 7.11. abends: CGAL 6.0.1 (Release-Tarball, GitHub) in /media/oem/scan/cgal_ksr gebaut, Kinetic_surface_reconstruction_3 (KSR) als Testwerkzeug (`/media/oem/scan/cgal_ksr/work/ksr_run`, header-only, GPL-3.0+ / kommerziell GeometryFactory) -> NUR TEST, nicht in ein verkauftes Produkt. Abhaengigkeiten System (Boost, GMP, MPFR, Eigen3), kein sudo.
- 7.11. PolyGNN (chenzhaiyu/polygnn): MIT (LICENSE-Datei im Klon gelesen). Vortrainierter Checkpoint (Munich, ~42 MB, Google-Drive-Link in conf/dataset/munich.yaml) - Gewichtslizenz/Trainingsdaten (Munich-LoD2/Luftbild-Punktwolken, Zenodo) NICHT geprueft -> vor Verkauf klaeren. abspy 0.2.6 (Zellkomplex) braucht SageMath, nicht installiert; torch_scatter durch eigenen Shim ersetzt (/media/oem/scan/polygnn_test/shim). tools/polygnn_auswahl.py nutzt nur Modell + Checkpoint.

## 2026-11-08 pymeshfix (GPL) nur Test
- BS124/BS125 (Wasserdicht-Ableitung hlo_pois_wd*.stl) nutzten pymeshfix (GPL; BS20 hatte es wegen geplantem Verkauf ausgeschlossen). Ergebnisse nur Testartefakte unter /media/oem/scan/rc-park_null (hlo_pois_wd*.stl), NICHT in Produkt/Druckpipeline uebernehmen; vor Verkauf Ersatz (z.B. eigener Randschleifen-Schluss, trimesh/manifold3d) oder Lizenz klaeren.
- DexiNed (kornia, Gewichte DexiNed_BIPED_10.pth von huggingface.co/kornia/dexined): Code MIT/Apache, Gewichte-/BIPED-Lizenz unverifiziert; 9.11.2026 eingebaut (Kantenerkennung Foto-Ortho)
- SAM (facebook/sam-vit-base, HF): Code/Gewichte Apache-2.0 laut Modellkarte (unverifiziert), 9.11.2026 eingebaut (Objektflaechen)

## 2026-11-11 Relief aus Einzelbild (Beweistest, tools/relief_aus_foto.py)
- Depth Anything V2 **SMALL** (`depth-anything/Depth-Anything-V2-Small-hf`, 95 MB, HF_HOME=/media/oem/scan/hf_depth): Apache-2.0 (HF-API-Metadaten + README am Primaerort 11.11. gelesen; Base/Large/Giant sind CC-BY-NC = NICHT nutzen). Trainingsdaten (595K synthetisch + 62M unbeschriftete Fotos) nicht geprueft. Code: transformers (Apache-2.0), kein neues Paket, venv-seg unveraendert.
- Nicht eingesetzt: Apple Depth Pro (LICENSE nicht gelesen), Marigold.

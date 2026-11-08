# Recherche 2026-11-06: Flaechen-/Mesh-Rekonstruktion aus Fotos (Kaufhaus), Stand der Technik

Auftrag: erst recherchieren (Regel), nichts installiert, nichts gerechnet. Quelle der Aussagen = nur WebSearch/WebFetch-Treffer vom 2026-11-06;
was nicht belegt werden konnte, ist als OFFEN markiert (nicht raten). Lizenzen vor Einsatz im LICENSE-File pruefen. Keine Rechtsberatung.
Abgleich mit Register: Carving (CP/CW), OpenMVS-Haut verworfen (CP), EMAP nicht eingebaut (8 GB, Training je Szene), 3DGS/2DGS/GOF/PGSR/MILo/SuGaR = NC/Forschung (LIZENZ_WERKZEUGE.md).

## Kandidaten (Rangfolge nach erwartetem Nutzen bei Verkaufsplan)

| Rang | Kandidat | 8 GB VRAM | Zeit (Schaetzung, ANNAHME) | Lizenz | Reife | Erwarteter Gewinn gg. Carving |
|---|---|---|---|---|---|---|
| 1 | **gsplat (nerfstudio) 2DGS-Rasterizer + Eigen-Training + Tiefen-/Normalen-Prior (DA3 BASE/METRIC oder MoGe-2) + SAM2-Masken + Open3D-TSDF** | ja bei Bildgroesse 1/4 (1000x750); gsplat wirbt mit bis 4x weniger Speicher als Original | Training ~20-40 min, TSDF Minuten | gsplat Apache-2.0 (README); Open3D MIT; DA3 BASE/SMALL/METRIC Apache-2.0 (GIANT/LARGE any-view CC BY-NC!); MoGe Code MIT, Gewichte-Lizenz OFFEN; SAM2 Apache | gsplat ausgereift, 2DGS-API in der Referenz vorhanden; Trainingsskript + Normalen-Regularisierung + Mesh-Export muss man selbst bauen (gsplat-README nennt kein 2DGS-Beispiel/Mesh-Extraktion) | mittel-hoch: dichte, glatte Flaechen auch auf Putz (Priors), Details/Figuren nur wenn Aufloesung reicht; TSDF rundet Kanten ab -> Kanten danach per Ebenen/Snap |
| 2 | PGSR (zju3dv) | ja (3DGS-Klasse) | 30-60 min | "other"/LICENSE.md, baut auf Inria-3DGS -> Forschungslizenz zu erwarten (OFFEN, im Repo lesen); in LIZENZ_WERKZEUGE als NC/geprueft | gut; in einer Studie sauberste Geometrie auf texturlosen Flaechen (arXiv 2506.04908), TSDF-Meshes brauchen "groesster Cluster"-Nachfilter | hoch als Machbarkeitstest, aber nicht verkaufbar |
| 3 | 2DGS Original (hbb1) | ja | 30-60 min | Inria/MPII-Forschungslizenz (README verweist nur auf LICENSE.md, in unserer Liste NC) | sehr verbreitet, `render.py --mesh_res 1024` (TSDF) | mittel; Referenz fuer Rang 1 |
| 4 | MILo (Anttwo) | Paper: weniger Gaussians/10x weniger Knoten, 8 GB OFFEN | 1-2 h | Gaussian-Splatting-License, nur Evaluation/Forschung | TOG Dez. 2025, neu | mittel-hoch (Mesh direkt im Training), aber nicht verkaufbar |
| 5 | Planar-Prior-MVS (OpenMVS-Fork 3DOM-FBK; PHI-MVS; TSAR-MVS) | CPU/GPU PatchMatch, ja | Stunden | OpenMVS AGPL-3.0 (Ergebnisse frei, Code nicht in Produkt einbinden); Forks/Papers je eigene Lizenz OFFEN | Forschungscode; Studie 2410.18433: Planar-Prior laesst weiter Loecher in schwach texturierten Gebaeudeflaechen | niedrig-mittel: bei uns OpenMVS-Haut schon verworfen |
| 6 | Neuralangelo / NeuS2 / EMAP (Neural SDF) | 8 GB knapp bis nein, Training je Szene Stunden | Stunden | Neuralangelo NVIDIA, laut Presse nicht kommerziell; NeuS2/SuGaR OFFEN | alt/aufwaendig | niedrig: Hash-Gitter-Detail gut, aber Zeit/VRAM/Lizenz |
| - | Nur Hilfsbausteine | | | | | |
| a | SAM 2 / SAM 3 Masken fuer Passanten/Staende (Verdecker aus Verlust und Carving ausblenden) | ja (ViT-B/Tiny) | Sekunden je Bild | SAM2 Apache-2.0; SAM 3 Meta-SAM-License mit Auflagen (LIZENZ) | ausgereift | hoch fuer Sockel, auch fuer das Carving nutzbar (Strahlen durch Maske nicht als leer zaehlen) |
| b | Depth Anything 3 (BASE/SMALL/METRIC/MONO, Apache) bzw. MoGe-2 Normalen | ja | s je Bild | s. o. | neu, Pose+Tiefe+Intrinsics | Normalen-Prior fuer glatten Putz; Gefahr: Prior-Fehler (gegen COLMAP-Skala pruefen, Register-Lehre "Messung gewinnt") |

## Befunde mit Quelle
- MILo: Mesh waehrend des Trainings differenzierbar extrahiert, TOG 44(6) Dez. 2025, ~10x weniger Knoten als 2DGS; Code unter Gaussian-Splatting-License (Forschung/Evaluation). https://arxiv.org/abs/2506.24096 , https://github.com/Anttwo/MILo
- 2DGS/PGSR-Meshes entstehen per TSDF-Fusion von Tiefenkarten (Open3D); TSDF-Meshes haben Schwebeartefakte, Nachfilter "groesste Komponente". Studie: GOF Loecher/Artefakte in texturlosen Bereichen, PGSR sauberste Geometrie. https://arxiv.org/pdf/2506.04908 ; https://arxiv.org/pdf/2506.18575 ; 2DGS-Befehle: https://github.com/hbb1/2d-gaussian-splatting
- 2DGS-Leistung haengt von Initialisierung ab; Mono-Tiefen-/Normalen-Priors helfen (2026-Kurzpapier, im Suchtreffer von https://github.com/hbb1/2d-gaussian-splatting genannt) ; weitere 2025/26-Kandidaten nur als Titel gesehen, Abstracts NICHT gelesen: G4Splat https://arxiv.org/pdf/2510.12099 , 2603.19682 (Self-Constrained Priors) https://arxiv.org/pdf/2603.19682 , 2508.07701 (Normal+Distance Guidance) https://arxiv.org/pdf/2508.07701
- gsplat: Apache-2.0, COLMAP-Training, Batch, "bis 4x weniger GPU-Speicher"; 2DGS-Funktionen `rasterization_2dgs` stehen in der API-Referenz (AMD-ROCm-Spiegel https://rocm.docs.amd.com/projects/gsplat/en/latest/ ). Offizielle Seite https://github.com/nerfstudio-project/gsplat nennt 2DGS/Mesh nicht -> Eigenbau, Aufwand OFFEN.
- Depth Anything 3: Repo Apache-2.0; Gewichte BASE/SMALL/METRIC/MONO Apache-2.0, GIANT/LARGE/NESTED any-view CC BY-NC 4.0. https://pypi.org/project/depth-anything-3/ , https://huggingface.co/depth-anything/DA3-BASE/blob/main/README.md
- MoGe: Code MIT (DINOv2-Teil Apache), Gewichte ohne eigene Lizenzangabe auf der Seite (OFFEN), MoGe-2 liefert metrische Tiefe und optionale Normalen. https://github.com/microsoft/MoGe
- OpenMVS: AGPL-3.0. https://github.com/cdcseacave/openMVS ; Planar-Prior-Fork 3DOM-FBK https://cris.fbk.eu/handle/11582/338887 ; Luecken trotz Planar-Prior https://ar5iv.labs.arxiv.org/html/2410.18433 ; PHI-MVS https://arxiv.org/pdf/2104.06165 ; TSAR-MVS https://arxiv.org/pdf/2308.09990
- PGSR: https://github.com/zju3dv/pgsr (Lizenz "other" laut Index, https://awesome.ecosyste.ms/projects/github.com%2Fzju3dv%2Fpgsr ), Paper https://arxiv.org/abs/2406.06521
- Neuralangelo: nicht kommerziell ohne NVIDIA-Lizenz (https://github.com/NVlabs/neuralangelo, https://radiancefields.com/nvidia-releases-neuralangelo-code).
- NICHT gefunden: direkter Vergleich 2DGS/PGSR/MILo auf texturlosen Putzfassaden; kein belegter Gewinn fuer Gebaeude mit 155 Handyfotos. Alle Gewinnerwartungen sind Hypothesen.

## EINE Empfehlung fuer den naechsten Versuch
**Rang 1, aber als zweistufiger Test, damit Entscheidung nach 1 Tag faellt (Teststufe A darf NC nutzen, Stufe B ist verkaufbar):**
- Stufe A (Machbarkeit, nur Test, NC ok laut LIZENZ_WERKZEUGE "nur zum Testen", vorher eintragen): PGSR oder 2DGS Original auf kaufhaus_null4 ohne Holdout-Fotos, mit SAM2-Masken (Passanten/Staende aus Verlust). Frage: schlaegt ein GS-Mesh das Carving ueberhaupt? Wenn nein -> Linie beenden, kein Eigenbau.
- Stufe B (nur wenn A gewinnt): gleiches mit gsplat-2DGS-Eigenbau (Apache) + DA3-BASE/METRIC-Normalen-Prior + Open3D-TSDF, danach Kanten/Ebenen-Snap (S8-Werkzeug) fuer scharfe Kanten.
Begruendung: einziger Weg mit durchgehend permissiver Kette; Masken (Rang a) wirken zusaetzlich unabhaengig am bestehenden Carving (billigster Sofortgewinn, separat messen).

## Minimaler Testplan (Messung)
Messgroesse: kosten_lr auf den 6 Holdout-Fotos 001, 024, 054, 083, 211, 234; Vergleich Carving korrigiert kh4 ho -0,0095 (Register CW; die alte -0,0083 war durch den vis-Index-Fehler ungueltig), Generator C -0,0111 (laut Auftrag). Gleiches Werkzeug/gleiche Kameras wie s8_kaufhaus.py-Holdouttabelle; Sollwerte nicht lockern.
0. Platz: Tor 15 GB frei beachten (derzeit ~16 GB); Daten unter /media/oem/scan/rc-park_null/kaufhaus_gs/ ; ein GPU-Job, via tools/job_start.sh.
1. Masken: SAM2 (Apache) auf alle 155 Fotos mit Text-/Punktprompts Personen/Staende/Plane; Masken ansehen (Kontaktblatt) vor Weiterverwendung.
2. Holdout: 6 Fotos aus Training entfernen (images.bin-Reihenfolge, nicht Namensreihenfolge! Register CW).
3. Training 1/4 Aufloesung (1000x750), Masken im Verlust, Tiefen-/Normalen-Prior optional (Stufe B), COLMAP-Skala behalten.
4. Mesh: TSDF (Open3D) aus gerenderten Tiefen, voxel 2-4 cm (1:87 = 0,23-0,46 mm; Mindestwand 0,34 mm beachten), groesster Zusammenhang, Wasserdicht-Pruefung.
5. kosten_lr auf 6 Holdout-Fotos, Pruefstand-Tor, Sichtblatt/foto_diff ansehen (Sockel, Arkaden, Figuren), Ergebnis als Registereintrag (auch Fehlschlag).
Abbruchkriterium: kosten_lr nicht besser als -0,0095 UND Sichtblatt zeigt keine bessere Arkade/Sockel -> Linie beenden.

## Installations-Befehle (NICHT ausgefuehrt; Pfade nach EINRICHTUNG_RECHNER.md pruefen)
```
# eigene venv auf der Datenplatte (nicht Root)
python3 -m venv /media/oem/scan/venv-gs && . /media/oem/scan/venv-gs/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124   # an CUDA-Treiber anpassen
pip install gsplat open3d pycolmap trimesh              # gsplat Apache, Open3D MIT
pip install depth-anything-3                            # PyPI-Name laut Treffer; nur Gewichte DA3-BASE/SMALL/METRIC-LARGE/MONO (Apache)
pip install sam2                                        # oder git+https://github.com/facebookresearch/sam2 ; Apache-2.0
# Stufe A (nur Test, NC):
git clone --recursive https://github.com/zju3dv/pgsr /media/oem/scan/gs_test/pgsr   # LICENSE.md vorher lesen
git clone --recursive https://github.com/hbb1/2d-gaussian-splatting /media/oem/scan/gs_test/2dgs
```
Hinweis: CUDA-Rasterizer-Builds (diff-surfel-rasterization etc.) brauchen nvcc passend zu torch; gsplat kompiliert JIT beim ersten Lauf. Zuerst LIZENZ_WERKZEUGE.md-Zeilen ergaenzen.

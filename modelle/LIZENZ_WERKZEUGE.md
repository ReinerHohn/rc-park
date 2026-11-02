# Lizenz-Register: Werkzeuge und Daten (für späteren Verkauf der Bausätze)

Ziel des Projekts schließt Verkauf ein. **Wo etwas nur "nichtkommerziell" erlaubt ist, steht es hier rot (⚠).**
Stand 2026-10-31. **Geprüft** = in dieser Sitzung an der Quelle gelesen. **ungeprüft** = aus meinem Wissen, vor Verkauf selbst nachsehen.
Das ist keine Rechtsberatung. Offen ist immer, ob Messwerte/Ergebnisse, die mit einem NC-Werkzeug *abgeleitet* wurden, kommerziell nutzbar sind.

## ⚠ Werkzeuge, bei denen die Lizenz (noch) nicht zu kommerzieller Nutzung passt
| Werkzeug | Lizenz | Status | Wo genutzt | Was tun vor Verkauf |
|---|---|---|---|---|
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

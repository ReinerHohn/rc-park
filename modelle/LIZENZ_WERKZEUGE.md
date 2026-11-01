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

## Regel
Neues Werkzeug/Modell → hier eintragen, **bevor** Ergebnisse ins Produkt (STL, Anleitung, Zahlen im Bausatz) wandern.
NC-Modelle nur zur Forschung; was im Verkaufsprodukt steckt, muss aus lizenzfreien Quellen (Laser, Fotos als Messvorlage, eigener Generator) belegbar sein.

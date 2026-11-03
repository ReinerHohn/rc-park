# Plan Verbesserung (Stand 2026-11-03) - was aussteht, nach Nutzen sortiert

Aktueller Arbeitsstand und laufende Jobs: `modelle/UEBERGABE_2026-11-03.md`.

Grundsatz: erst was billig und aussagekraeftig ist, dann was teuer ist. Jede Stufe hat ein Abbruchkriterium; ein negatives Ergebnis kommt ins Register (BU ff.).
Regeln aus CLAUDE.md gelten: kein Sollwert gelockert, Widersprueche nicht gemittelt, jede Aenderung ueber `tools/bauen_abnehmen.sh martinstor`, Schnappschuss nur mit Register-Eintrag.

## Ausgangslage (belegt)
- Strassenwolke: 16 Kameras, je Bild ein eigenes Linsenmodell (SIMPLE_RADIAL, nur k1), alle < 6 m Hoehe, 2 von 8 Richtungssektoren. Tiefenscherung x += 0,0308 z - 0,188; gefittet gegen den Generator (zirkulaer), gestuetzt nur durch den DOM1-First.
- Drohne d1: SIMPLE_RADIAL je Clip, Clip-Tilt bis +1,9 m (46-54 m), Doppeldach; per Bandkorrektur auf <= 0,13 m an die Strasse gebunden (daher nicht unabhaengig).
- Helmbreite E-W: der 'Widerspruch' (Drohne 5,93 vs Strasse 4,6 m) war ein Mass-Unterschied. Mit gleichem Silhouetten-Schaetzer (`tools/breite_quellenvergleich.py`): Strasse 5,53 / Generator 4,97 / Drohne 5,93 @45,2 m, Clips untereinander ~1 m Streuung -> keine Evidenz fuer ein falsches Profil. Nord-Sued-Tiefe der Nordflaeche stimmt in allen Quellen (<0,1 m).
- Datenluecken: Sued (Strasse < 100 Punkte), Ost/West (Strasse ~1400 Punkte), alles ueber 50 m duenn.

## Stufe 1 - laeuft/wartet bereits (Maschine arbeitet, ich werte aus)
| Nr | Schritt | Stand | Entscheidet |
|---|---|---|---|
| 1.1 | Drohne mit Linsenmodell OPENCV (`video_sfm/d1_cv`, dicht) | ERLEDIGT 3.11.: Tiefenversatz vor Korrektur RMS 0,88 -> 0,28 m (z >= 38, ein Lauf); RBC7Co +1,12/+1,66 -> -0,13/+0,09 m; Standard in video_sfm.py jetzt OPENCV | verkleinert OPENCV Clip-Tilt/Doppeldach? Abbruch: kein Unterschied -> Register "ohne Wirkung" |
| 1.2 | `video_merge` + `hybrid_abgleich` fuer d1_cv im Sandbox-Objekt | Warteschlange (`jobplan.py`) | Zahlen Clip fuer Clip, Hoehenverlauf, Dachbreite |
| 1.3 | Boden-SfM an Nordnetz ausrichten (GPU-Matching) | Warteschlange | deckt der Boden-SfM die Suedseite ab? |

## Stufe 2 - billig, CPU, ohne neue Daten (als naechstes)
| Nr | Schritt | Warum | Abbruch/Erfolg |
|---|---|---|---|
| 2.1 | Strassennetz mit gemeinsamer Intrinsik je Kamera/EXIF-Gruppe (`f_gruppe`) und/oder Modell RADIAL/OPENCV neu rechnen (`sfm_netz.py --kamera-modell`) | 16 Bilder mit je eigenem Linsenmodell sind schwach bestimmt; mogliche Mitursache der Scherung | Scherung/Reprojektion vor-nachher; sonst Register |
| 2.2 | ERLEDIGT 3.11.: Bootstrap ueber Clips + gleicher Schaetzer fuer alle Quellen | Ergebnis: vereinbar innerhalb der Clip-Streuung (~1 m @45 m); nach d1_cv wiederholen | wenn Clips < 0,3 m streuen, Drohnenbreite als Beleg nutzbar |
| 2.3 | Lot-/Linienpruefung (FLD aus opencv_contrib oder Canny+Hough; DeepLSD MIT nur als Test) der Wolke gegen senkrechte Kanten | misst die Scherung unabhaengig vom Generator | Kantenneigung je Hoehe |
| 2.4 | Doppelschicht-Detektor als Pruefzeile (1 vs 2 Ebenen per BIC) | verhindert Rueckfall des Doppeldachs | Zeile besteht am Referenzmodell |
| 2.5 | `wolke_vs_modell --entzerren` so aendern, dass die Drohne erhalten bleibt; danach `video_merge` als erster Kettenschritt | Kette wirft heute die Drohne weg | Regression + Schnappschuss mit Register |
| 2.6 | Regressionsabweichung (9 Dateien) klaeren | Schnappschuss veraltet, Ursache unbekannt | Ursache benannt oder Schnappschuss mit Register erneuert |

## Stufe 3 - mittlerer Aufwand, eigene Ausgleichung (nur wenn Stufe 1-2 den Widerspruch nicht loesen)
| Nr | Schritt | Beschreibung |
|---|---|---|
| 3.1 | Eigenbau-Buendelausgleichung (SciPy least_squares, duenne Jacobi, Start = COLMAP-Posen) mit weichen, gewichteten Residuen: LoD2-Traufe/Wandebenen, DOM1-First, Lot senkrechter Kanten; Huber/Cauchy | zieht die Scherung aus amtlichen Ankern ab, nicht aus dem Generator. Gewichte weich (Regel 5). |
| 3.2 | Primitivenfit Dach/Helm (Ebenenpaar/Kegel) mit Tukey-IRLS, Quelle je Dachflaeche nach Dichte/Unsicherheit | nutzt "Dach = Ebenen" statt verzerrter Punkte |
| 3.3 | Silhouetten-Huelle als Obergrenze der Dachbreite (Space Carving, Eigenbau) | Plausibilitaetspruefung |
| 3.4 | Hybrid-Abgleich fuer weitere Bauteile (Tuermchen mit Oeffnungen, Torboegen, Glockenstock), Bericht alt/neu/Konfidenz | wie vom Nutzer gefordert: Generator folgt der Wolke, wo diese belegt ist |
| 3.6 | Treppe fuer NEUE Objekte (`tools/treppe.py`): grob -> mittel -> fein -> Video, Guete nach jeder Stufe, Stopp bei Gewinn <= Rauschen, Bericht mit naechstem Hebel | GEBAUT 3.11. (Auswertung an den 4 Nachtlaeufen getestet; Lauf ueber `nullstart.py` noch nicht mit echtem Objekt). Befund: nur 2 von 56 gemeinsamen Pruefungen sind unabhaengig (lod2/laser/dokument) -> Guete bei neuen Objekten blind, mehr unabhaengige Sollwerte noetig; gleiche Konfiguration streut 43..49 |
| 3.7 | **Abdeckungspruefung automatisch** (`tools/abdeckung_quellen.py`, NEU; ergaenzt den Aufnahme-Assistenten `tools/abdeckung.py` (Register BI), ersetzt ihn nicht): je Quelle (Foto/Video/Drohne) Kamerapositionen in den Modellrahmen, Seite/Abstand/Hoehe/Blickneigung zaehlen, Luecken je Seite und Hoehenband als Pruefzeile; Seite aus `objekt.json` `seiten_konvention` (nicht Vorzeichen von x/y von Hand), Pfade aus `video_stufe`/`sfm`, Ausreisser (Abstand > 1000 m) verwerfen, Symmetrie-Warnung (Seitenzuordnung nur ueber asymmetrisches Merkmal sicher) | Nutzerregel 3.11.: was von Hand gemessen wird, muss in die Pipeline. Vorlage: Scratchpad-Skript `kamera_seiten.py` (3.11., Ergebnis: Drohne N161/S0/O23/W36, Boden N346/S0/O0/W1); danach `tools/regression.py --pruefen`, Schnappschuss mit Register-Eintrag |
| 3.5 | Torbau (Fork-Ergebnis, 12/12 Pruefungen) ins Hauptmodell und in den Viewer | Nutzer hat noch nicht verifiziert |

## Stufe 4 - braucht Daten (der groesste Hebel, nicht in Software loesbar)
| Nr | Schritt | Beschreibung |
|---|---|---|
| 4.1 | Fotos von erhoehten Standorten (Fenster/Parkhaus, 20-40 m), Bogen um die Nordseite, Sued aus >= 46 m, Ost/West | bricht die Scherung der Strassengeometrie; Plan in `PLAN_DETAILGETREUE.md` Schritt 2 |
| 4.2 | Fotos von Nord oder Sued aus der Ferne fuer die E-W-Breite des Helms | dritte, unabhaengige Quelle fuer den offenen Widerspruch |
| 4.3 | Weiteres Drohnen-/Videomaterial fuer Sued/Ost/West und > 50 m (Boden-SfM auswerten) | Datenluecken |
| 4.4 | Mehr Nullstart-Laeufe mit disjunkten Fototeilmengen | echte Unabhaengigkeit fuer `masse_konsens.py` |

## Stufe 5 - spaeter / nur mit Lizenzklaerung
Render-and-Compare (PyTorch3D, BSD), monokulare Tiefe/Normalen (nur Depth-Anything-V2-Small Apache, als schwacher Prior), gsplat (Apache) nur fuer Textur. Vor Verkauf pruefen: nvdiffrast, Gewichte von MoGe/Metric3D/DSINE, 2DGS, OpenCV-LSD. Mapillary-Bilder (CC BY-NC-SA) und YouTube-Drohnenpunkte nicht in ein Produkt.

## Reihenfolge
1.1 -> 1.2 -> 1.3 (laufen) | parallel 2.1, 2.4 -> 2.2 -> 2.3 -> 2.5 -> 2.6 | dann je nach Ergebnis 3.1-3.2 | 4.x sobald Fotos/Footage da sind.
Ehrliche Grenze: Stufe 1-3 verbessern, was die Daten hergeben; Stufe 4 verschiebt die Grenze selbst.

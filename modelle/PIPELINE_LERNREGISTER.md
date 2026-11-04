# Pipeline-Lernregister (objektübergreifend)

Zweck (Nutzerauftrag 2026-11-04): Aus **allen** Läufen, Martinstor wie Kaufhaus, allgemein lernen. Jede Lehre steht hier als Regel mit Beleg.
Die Regel wird erst dann als umgesetzt geführt, wenn die Pipeline sie **erzwingt** (Code oder Test), nicht nur hier beschreibt.
Einzelversuche stehen maschinenlesbar in `modelle/<objekt>/versuche.jsonl` (`tools/versuch_log.py`), Martinstor-Details in `VERSUCHSREGISTER_MARTINSTOR.md`.

Spalten: **Lehre** | **Belege** (Objekt, Lauf) | **Erzwungen durch** | **Stand**

## 1. Kamera-Intrinsik (Brennweite, Hauptpunkt, Verzeichnung)

| Lehre | Belege | Erzwungen durch | Stand |
|---|---|---|---|
| Eine EXIF-Brennweite ist ein **Prior**, kein fester Wert. Wird sie festgesetzt, verbiegt sich das ganze Netz um den Fehler herum. | Kaufhaus: `sfm_netz.py` setzte `set_constant_cam_intrinsics`; SfM-f gleich Prior, Wolke um 12–16 % zu klein und in der Höhe gestaucht, Dach 1,66 m unter DOM1 | `sfm_lod2_buendel.py` (weicher Prior, σ 5 %) | Bündel: erledigt. `sfm_netz.py`: offen |
| Die 35-mm-Äquivalenz gilt für die **Diagonale** (f_px = f35 · Diagonale / 43,27), nicht für die Langseite / 36. Für 4:3-Fotos sind das 4 % Unterschied, für beschnittene Fotos bis 15 %. | Kaufhaus: Foto 067 2333 statt 2733 px; Median SfM/EXIF 0,96 | `tools/exif_brennweite.py` | erledigt |
| Bei beschnittenen Fotos ist f35 falsch. `FocalPlaneXResolution` (Pixelabstand) bleibt auch beim Beschnitt gültig und hat Vorrang. Fehlt beides, hilft die Sensordatenbank. | Kaufhaus: 49 von 56 EXIF-Fotos auswertbar; Foto 068: FocalPlane 4817 px, SfM 4902 px | `exif_brennweite.py` (Reihenfolge f35 → FocalPlane → Datenbank), Verwerfen bei mehr als 25 % Abstand | erledigt |
| Perspektivkorrigierte Architekturfotos (Shift, Wikimedia) haben ihren Hauptpunkt weit außerhalb der Bildmitte. Ein fester Hauptpunkt in der Mitte zwingt das Netz, über Brennweite und Lage auszuweichen. | Kaufhaus: Rückprojektion 0,74 → 0,66 px mit freiem Hauptpunkt | `sfm_lod2_buendel.py` (Freigabe je Kamera, siehe nächste Zeile) | erledigt |
| Ein **global** freier Hauptpunkt schluckt die Höhenbindung, wenn das Netz kaum Boden-/Dachpunkte hat (eine Verschiebung aller Punkte gegen die Kameras gleicht einer Hauptpunktverschiebung). Hauptpunkt eng (1 %), Freigabe nur je Kamera, wenn ihr Rückwärtsschnitt bei festen Punkten es belegt. | Martinstor Nord (0 Bodenpunkte im sparse): frei Goldkugeln −0,9/−1,1 m gegen die Pick-Kette, eng −0,05/−0,18 m | `hauptpunkt_test()` in `ausgleichen()` | erledigt |
| Ein Prüfdurchgang mit anderen Freiheiten darf seinen Zustand nicht weitergeben (nur testen). | Martinstor: übernommener EXIF-Prüfzustand (Hauptpunkt frei) kostete 0,5 m an den Goldkugeln | `ausgleichen()`: EXIF-Pass ändert nur f0/fs | erledigt |
| Gespeicherte COLMAP-Fehler (`points3D.error`) können nach einer Nachbearbeitung veraltet sein. Die Rückprojektion immer selbst nachrechnen. | Kaufhaus: gespeichert 0,85 px, echt 2,63 px (Mittel) | `sfm_lod2_buendel.py` gibt die echte Rückprojektion aus | erledigt |

## 2. Ausgleich mit amtlichen Daten

| Lehre | Belege | Erzwungen durch | Stand |
|---|---|---|---|
| Eine Ähnlichkeitstransformation hinterher (7 Parameter) kann eine **innere** Verzerrung nicht heilen. Die amtlichen Flächen gehören **in** den Bündelausgleich. | Martinstor Süd (Register AI); Kaufhaus: Fassaden passend, Dach 1,66 m zu tief | `sfm_lod2_buendel.py` + Nullstart-Schritt `buendel` | erledigt (Nachweis siehe 5) |
| Mit robuster Verlustfunktion (soft_l1) werden Priors bei großem Restfehler linear, und die Brennweiten laufen trotz Prior weg. Robustheit gehört als IRLS-Gewicht nur auf die Beobachtungen. | Kaufhaus v1: Brennweiten 30–80 % weg | IRLS in `ausgleichen()` | erledigt |
| Klassenausgleich (Wand/Dach/Boden) nur gedeckelt: 150 Dachpunkte dürfen nicht wie 2300 zählen. | Kaufhaus v1 | Faktor ≤ 4 | erledigt |
| Das Gelände (DGM) ist nur eine **Untergrenze**. „Bodenpunkte“ einer Straßenwolke sitzen auf Rädern, Autos und Menschen. Zweiseitig gezogen sinkt die ganze Szene samt Kameras. | Kaufhaus: Kameras −0,6 m unter dem DGM trotz Höhenprior | einseitige Bodenbedingung in `ausgleichen()`; Simulation hat Bodenobjekte | in Prüfung |
| Die Kamerahöhe gilt **über dem DGM** unter der Kamera, nicht absolut im Rahmen. Sie ist zugleich eine unabhängige Kontrollgröße. | Kaufhaus: absolut 1,6 m im Rahmen → Kameras unter dem Gelände | `ueber_dgm()` im Bündel | erledigt |
| Eine bessere Rückprojektion bedeutet keine bessere Geometrie. Jede Variante braucht eine fremde Kontrolle (DOM1, Kamerahöhe über DGM, Foto-Maß). | Kaufhaus hp: 0,66 px, Kameras unter dem Gelände | `tools/wolke_dom1_pruefen.py` | Werkzeug fertig; Gate im Nullstart offen |

## 3. Daten, Platten, Abläufe

| Lehre | Belege | Erzwungen durch | Stand |
|---|---|---|---|
| Regeln, die nur in CLAUDE.md stehen, werden verletzt. Die Pipeline muss sie erzwingen. | Kaufhaus: Nullstart-Ziel als echter Ordner im Repo, PatchMatch 2,3 GB, Root 100 % voll | `nullstart.py`: Ziel immer unter `/media/oem/scan/rc-park_null` mit Link; echter Ordner auf Root = Abbruch | erledigt |
| Lange Jobs nur über `job_start.sh`. Hintergrundshells werden bei Speicherknappheit beendet. | Martinstor 2026-11-03 | CLAUDE.md und `job_start.sh` | erledigt |
| Ein neues Objekt braucht `rahmen` und `lod2` in `objekt.json`. Alte Objekte (Martinstor) haben den Rahmen nur in `anker3d.json`. | Martinstor-Test 2026-11-04 | `tools/objekt_rahmen.py` (ergänzt aus anker3d.json und der LoD2-Kachel unter der Rahmenmitte, vermerkt in `_ergaenzt`), in allen LoD2-Werkzeugen | erledigt |
| LGL-DGM1 liegt teils nur als XYZ vor, nicht als GeoTIFF. | Martinstor: DGM-Abfrage lieferte NaN | `dom1_kachel.py` XYZ-Rückfall | erledigt |

## 4. Messen und Prüfen (Martinstor-Lehren, allgemein)

| Lehre | Belege | Erzwungen durch | Stand |
|---|---|---|---|
| Zählmerkmale nur am Foto, nie aus der Wolke (Selbstbezug). | Martinstor Register CB | Prüfstand Exit 2, `test_regeln_cb.py` | erledigt |
| Laser DOM1 ist blind für steile Helme (> 75°) und kleine Bauteile. | Martinstor Register AR | Prüfstand Quellen-Blindheit | erledigt |
| Zuerst Modellkanten über das kalibrierte Foto legen, erst danach Wolken-Kennzahlen. | Martinstor 2026-11-03 | Regel 3/3f, `foto_diff.py` | erledigt |
| Gleicher Fehlschlag in **allen** Ketten ist ein Prüfstandsfehler (Start, Orakel), kein Befund. Startrauschen in Pixeln je Kamera, Orakel mit Kernstart; „alle > 1 m“ wird als ungültig ausgewiesen, nicht als Sieg. | Synthetik Martinstor Seed 2 (0,01 rad = 50 px bei f 5000), Kaufhaus Seed 1 (Umeyama s = 1e-4, Kette selbst 0,10 m) | `test_buendel_synthetisch.py` | erledigt |
| Widersprüche zwischen Quellen nicht mitteln, sondern Ursache suchen. Beim Kaufhaus war die Wolke der Ausreißer, Foto, DOM1 und LoD2 stimmten überein. | Kaufhaus Traufe 2026-11-04 | Regel 5 | erledigt |

## 5. Nachweise

- **Martinstor real, neue Kette ohne Picks gegen alte Pick-Kette (2026-11-04)**. Gleicher Schätzer: `sfm_ausrichten.py` trianguliert die Handpicks in beiden Netzen.

  | Merkmal (m) | alt (Picks) | neu | Δ | σ |
  |---|---|---|---|---|
  | Goldkugel NE | 54,90 | 54,85 | −0,05 | 0,16 |
  | Goldkugel NW | 55,29 | 55,11 | −0,18 | 0,16 |
  | Türmchen NE | 44,45 | 44,57 | +0,12 | 0,13 |
  | Türmchen NW | 44,65 | 44,56 | −0,09 | 0,13 |
  | Traufe N | 40,61 | 40,57 | −0,04 | 1,5 |
  | Spitze | 67,86 | 67,94 | +0,08 | 1,2 |

  Alle innerhalb 1 σ. Netz `martinstor_lod2/sfm/sparse_hptest2`, Hauptpunkt-Test: 0 von 23 freigegeben. Regression Martinstor danach identisch.
- **Synthetisch Martinstor** (Endcode, 3 Seeds): Punktfehler-Median alt 0,47 / 0,21 / 0,22 m, neu 0,062 / 0,040 / 0,041 m; Anteil > 1 m 32/18/16 % → 1/4/3 %. Neu in allen Seeds besser.
- **Synthetisch Kaufhaus**: Seed 0 alt 0,226, neu 0,036 m; Seeds 1/2 wiederholt mit korrigiertem Orakel (siehe unten).
- **Kaufhaus real**: DOM1-Kontrolle der dichten Wolke vorher/nachher. Folgt.

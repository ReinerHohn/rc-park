# Versuchsregister Martinstor – was schon probiert wurde (nicht wiederholen)

Stand 2026-10-31. Je Zeile: Versuch, Ergebnis, Konsequenz. Details im `LERNJOURNAL_MARTINSTOR.md` (Nr. in Klammern),
Zahlen in `MASSPRUEFUNG_MARTINSTOR.md`. **Vor einem neuen Versuch hier nachsehen.**

## A. Datenquellen
| Quelle | Ergebnis | Status |
|---|---|---|
| LGL DOM1/DGM1 (1 m) | Gesamthöhe 54,80 m (Laser 54,79); Grundlage der Maßprüfung | **genutzt** |
| LGL LoD2 (CityGML) | Firstlinie 45,0 m (Journal 1, 18) | genutzt, Gegenprobe |
| LGL DOP20 (Luftbild 20 cm) | Türmchenspitzen bilden Rechteck ~9,1 × 8,0 m (Ablesefehler ±0,3 m); Dachflächen verschmiert (kein echter Ortho) | genutzt (22), Dach nicht auswertbar |
| LGL Rohpunktwolke (ALS_1/2/3, LAZ) | nicht frei abrufbar (404 auf getesteten Pfaden); nur per E-Mail, ≥ 60 € + USt. (ALS_3, ≥ 8 Pkt/m²); Abdeckung Freiburg unbestätigt. Entwurf: `LGL_BESTELLUNG_ALS3.txt`, **nicht gesendet**. Nutzen für den Druck gering (Dachkanten ±0,3 m), Fassade unsichtbar | offen, nicht bestellt |
| LGL DOM025 / DOM05 / nDOM / DSM025 | alle 404 (Adressen geprüft) | **gibt es nicht offen** |
| LGL DGM025 (0,25 m Gelände) | existiert für die Kachel (100 MB), enthält nur Boden, kein Turm; war die Hirschsprung-Quelle | für Turm nutzlos |
| Bauforschung BW (PDF) | nur "65 m", "10 × 11 m" Grundriss; keine Pläne; Höhe widerlegt | erledigt |
| Textquellen 60–66 m | durch Laser widerlegt (54,80 m) | erledigt |
| Freiburg 3D-Stadtmodell | LoD2 wie oben, kein LoD3 | nichts Neues |
| Pläne / Aufmaß | nicht frei auffindbar (Stadtarchiv Freiburg, Landesdenkmalamt: nur auf Anfrage) | offen, nicht angefragt |
| Rohdaten Drohnen-Scan (COLMAP/OpenMVS, 6,7 Mio. Punkte, `colmap-test/martinstor-gpuba/`) | liegt vor, **Maßstab unbekannt** (nur angenommen), unten (< ~18 m) Löcher, Nadel fehlt; Anpassung ans Modell **versucht und abgebrochen** (erste Anpassung kollabierte auf Maßstab 0, Grenzen nötig) | offen |
| Commons-Fotos per SfM | für Fassadenebene unbrauchbar (frühere Notiz) | erledigt |

## B. Messmethoden
| Versuch | Ergebnis | Konsequenz |
|---|---|---|
| Hypsometrie (Fläche > Höhe t, 9-m-Umkreis, Rotation + Rasterphase) | Basisfehler mittel 8,3 %, Median 3,6 %, Hold-out 14,7 %, punktweise 4,13 m | Standardmaß, Rotation 86–112°, Phase −1…1 |
| Foto-Verhältnismessung (030, 042, 050, 002) | Torbogen, Uhr, Wappen, Fenster ±8–10 % | Obergrenze der Handmessung |
| Foto-Silhouette GPU (`foto_silhouette_gpu.py`) | Überlapp 0,92–0,93 (044), 0,85–0,86 (043), 0,77–0,81 (042); Azimut um 90° mehrdeutig; Suchgrenzen anfangs zu eng (043) | bestätigt Gesamtform, keine Einzelmaße (22) |
| Dachfirst-Test 43,5–49,0 m gegen 3 Fotos | IoU 0,854 → 0,888 steigend, kein Maximum; Spanne ≈ Rauschen; Nadel ändert sich mit | **unentscheidbar**, Modell unverändert (23) |

## C. Optimierung der Generatorparameter
| Versuch | Ergebnis | Lehre |
|---|---|---|
| Optimierer v1 (10 Parameter, 11,9 % → 5,9 %) | teils Überanpassung: Hold-out besser nur wenig, punktweise Höhe schlechter (1,92 → 2,28 m); "Rauschen 0,000" (±0,02 m bewegt keine Rasterzelle) | **Annahmeregel v2**: Training > 2σ besser UND Hold-out nicht schlechter UND punktweise nicht schlechter als +0,15 m; σ-Boden 0,02 |
| Optimierer v2 (16 Parameter), Lauf 1–4 | 0 von 64 Proben robust besser; Lauf 3 = Lauf 4 Feld für Feld (**wiederholbar**) | Basis nahe am Optimum **bezüglich Laser** |
| Lauf 1 ≠ Lauf 2 | Ursache: parallele Prozesse schrieben gemeinsame `cur.stl`/`cur_gen.py` | Dateinamen `cur<PID>`; **nie zwei Optimierer parallel mit gleicher Datei** |
| Mehrfachstart (Basis + 4 Zufallsstarts) | alle besser als Basis (e 0,046–0,089, Hold-out 0,055–0,096, punktweise 3,3–3,5 m), aber Parameter streuen bis 1,6 m (T1, rh, T0, ZZ) und verkleinern D/W (Luftbild widerspricht) | flaches Tal, **nicht übernommen**; Hold-out nicht unabhängig |
| Türmchenversatz 0,4 → 0,7 m (Luftbild) | Laser schlechter (11,9 → 14,8 %, M1 9,1 → 14,3 %); mit TWs 2,0/OR 0,9: 12,7 % / 12,4 % | **verworfen** (Ablesefehler = Größe der Verschiebung) |
| Einzelschritt D = 9,0 | e 0,083 → 0,067, Hold-out 0,147 → 0,144, punktweise 4,13 → 3,38 m | unter 2σ-Schwelle |

## D. GPU
- float32 statt float64 für Höhenkarten: **nicht bit-gleich** (max Abw. 3,7e-3) → verworfen.
- Zuschnitt z > 19 m: exakt und 1,8× schneller → übernommen. GPU ≈ 6× pro Auswertung, aber nur die Zielfunktion läuft auf der GPU (Profil: Höhenkarten 79 %, Unterteilung 10 %, Generator 6 %). **Nicht "maximal"**; Generator (manifold3d), Netzunterteilung, `fertigung_split`-Strahlen, `duese_check` sind CPU.
- Grafikspeicher 8 GB: zwei PyTorch-Hintergrundjobs belegen ~7,3 GiB; dritter Job → OOM. RAM 15 GB: zwei schwere Jobs parallel → früher OOM.
- Generator darf nicht bearbeitet werden, solange Optimierer laufen (lesen die Datei bei jeder Auswertung).

## E. Fertigung
| Versuch | Ergebnis |
|---|---|
| Aufteilung Lasercut + Druck (`fertigung_split.py`) | 30 Platten auf 2 Rohlingen, ~113 Druckteile, 234 cm³, passen 220×220×250; 47/113 Netze mit Kanten-Berührung (Slicer repariert) |
| Düsenprüfung 0,4 mm | 108/113 Teile mit Stellen > 2 % zu dünn |
| Düsenprüfung 0,2 mm | 35/112; Zifferblätter (druck_055/056) ~0,05 mm, Rahmen druck_111 → Ursache wohl Aufteilung, **nicht geprüft** |
| Testdruck (Prüfplatte, Adlertafel, Zinnen, Eckquader, Türmchen) | G-Code fertig (Prusa MK4S 0,4 mm), **nicht gedruckt** |
| Prusa MK4S (PrusaLink) | 401, Zugangsdaten unbekannt; Suche in Altsitzungen vom Berechtigungssystem blockiert — **nicht umgehen**; Nutzer kann Passwort geben oder G-Code per Hand starten |
| Bambu P1S (`p1s_print.py`, 192.168.178.125) | nicht erreichbar (kein Gerät auf 8883); kein Orca/Bambu-Slicer installiert |

## F. Generator-Fallen (bereits behoben)
Reliefs in Nischen gehören in `late`; Teile müssen ≥ 0,1 m überlappen (14 schwebende Körper); Fenster mit `hh=hxy(z)`; Manifold-Aufteilung mit `decompose()`.

Lizenzen der benutzten Werkzeuge/Daten: `LIZENZ_WERKZEUGE.md`.

## G0. VGGT-Fototest 2026-10-31 (nur Test, VGGT-1B CC BY-NC 4.0, siehe LIZENZ_WERKZEUGE.md)
- `tools/foto_vggt_test.py 042 043 044`: Kameras + Punktwolke in ~10 s auf der GPU (8 GB reichen nur mit **Aggregator in bfloat16**; volles Modell läuft in OOM, ganzes Modell in bfloat16 bricht an LayerNorm).
- Ergebnis Rekonstruktion: 3 × 518² Punkte (805 000), Konfidenz-Median 1,0 (Boden der Skala), 55 000 Turmpunkte nach Himmel-/Konfidenzfilter. Streuung der Hauptachsen 0,219 / 0,136 / 0,110 → Wolke **nicht eindeutig länglich** (Senkrechte per Hauptachse geraten).
- Anpassung an das Modell (Maßstab, Drehung, Verschiebung, 60 %-Mittel): Kosten 0,143 m, **aber Maßstab stieß an die untere Grenze (0,2·s0)** und die Wolke wurde auf Höhe 45–52,6 m zusammengedrückt (nur Dachbereich). **Degeneriert, keine Messaussage.**
- Lehre: Ähnlichkeitsanpassung ohne feste Senkrechte und ohne Maßstabsanker kollabiert. Nächster Versuch: Senkrechte aus Kameras/Horizont, Maßstab aus bekannter Größe (Uhrdurchmesser, Gesamthöhe über sichtbare Nadelspitze + Turmfuß) oder Anker über die GPU-Silhouettenkamera aus Eintrag 22.
- CPU-Laufzeit der Anpassung: 96 Startpunkte × 300 000 Modellpunkte ≈ > 23 min (abgebrochen); 8 Startpunkte × 60 000 Punkte ≈ 6 min.
- **Versuch 2 (Senkrechte aus Kameras + Neigung frei + beidseitiges Fehlermaß, GPU-CEM, `modelle/foto_vggt/versuche/vggt_reg2.py`):** ebenfalls **gescheitert**. Maßstab lief an die obere Grenze (68 m je Einheit), Wolke liegt 13–17 m neben dem Modell (Median je Höhenband). Kosten 24,7 m = Unsinn.
- Befund aus der Ansicht (`modelle/foto_vggt/wolke_042_043_044.jpg`, Blick entlang der Kamera in der Mitte): **Rekonstruktion selbst ist gut** (Uhr, Fenster, Dach, Türmchen scharf), aber nur eine Seite sichtbar (2,5D), an den Kanten Verschmierung; die drei x-Achsen der Kameras sind fast parallel (Eigenwerte 0,001 / 0,033 / 2,97) → Senkrechte nur in einer Ebene bestimmt, Turm erscheint um ~12° gekippt.
- Konsequenz: freie Ähnlichkeitsanpassung (Maßstab + Neigung + Drehung gleichzeitig) ist **nicht identifizierbar**. Nicht noch einmal so probieren. Nur mit Anker: Kamerapose aus der Silhouettenanpassung (Eintrag 22) oder ≥ 2 Seiten des Turms in der Rekonstruktion.
- **Versuch 3 (Anker = Kamera aus Silhouettenanpassung Foto 044, nur Maßstab frei; `versuche/vggt_anker.py`): FUNKTIONIERT.** Kostenkurve über den Maßstab hat ein klares Minimum: s = 48,3 m je VGGT-Einheit (Kosten 0,68 m, 50 %-Mittel; Mulde 45,7–51,0 ≈ ±6 %), davor/dahinter steil (12 m bei s=32, 24 m bei s=86). Alle vier 90°-Azimutvarianten fast gleich (0,68–0,72 m) → Quadratturm, Blickrichtung egal.
- Abstand Wolke–Modell nach Höhe (Median / P90): 30–35 m 0,51/1,63 m, 35–40 m 0,88/1,87 m, 40–45 m 0,88/2,34 m; darunter (10–30 m) 1,4–5,5 m, dort Bäume/Nachbarhäuser/Verdeckung. Wolke reicht nur bis 47,4 m (Nadel fehlt).
- **Grenzen (wichtig):** (1) Der Maßstab 48 m/Einheit wurde **am Modell festgelegt** (Anker + Modell) → absolute Größen sind damit **nicht unabhängig geprüft**, nur Formverhältnisse. (2) Der Anker (Silhouettenkamera) ist selbst mit d/f gekoppelt (±10 %). (3) Median 0,5–0,9 m im oberen Teil ist **eine Größenordnung über** dem, was ich für Firsthöhe 46,2 vs 45,0 m (1,2 m) bräuchte. (4) 2,5D (nur eine Seite).
- Lesart: Die Fotowolke ist mit dem Modell im oberen Turm **bis etwa 1 m verträglich**, nicht besser. Kein Beleg für ein Maß, kein Gegenbeweis.
- **Versuch 4 (10 Fotos: 017 018 022 031 041 042 043 044 047 049, gleicher Anker, `versuche/vggt_anker10.py`): kein Gewinn.** VGGT 15 s auf GPU. Die x-Achsen aller 10 Kameras sind wieder fast parallel (Eigenwerte 0,013 / 0,072 / 9,9): alle Fotos stehen auf der Straßenseite → **keine zusätzliche Turmseite**, die Senkrechte bleibt nur in einer Ebene bestimmt. Maßstabsminimum 66–68 (Einheit anders normiert), Kosten 0,70 m, Median im oberen Turm 30–35 m 0,52, 35–40 m 1,01, 40–45 m 0,77 m (P90 1,4–1,8 m). Wolke reicht bis 44,6 m.
- Ergebnis: mehr Fotos von derselben Seite machen die Wolke dichter, aber **nicht genauer**; die Grenze (~0,5–1 m) kommt vom Anker (d/f ±10 %), der 2,5D-Sicht und dem Modell-Foto-Unterschied, nicht vom Rauschen. VGGT-Linie für **Maße** hiermit **ausgereizt**; nutzbar nur als Plausibilitätsbild (oberer Turm ≈ 1 m verträglich).
- Echte Fortschritte wären nur mit Fotos von der **Rück-/Seitenseite** (Schlossberg-/Rotteckring-Seite, Innenhof) oder mit unabhängigem Maßstab (Messung vor Ort).

## G. Noch nicht versucht (Ideen)
- Scan-Punktwolke mit begrenztem Maßstab (5–16) und mehreren Startdrehungen an das Modell legen (ICP, ggf. GPU) → Abweichungskarte je Höhe.
- VGGT/MASt3R/MoGe-2/Metric3D v2 an den Fotos (kein Fassadentest in der Literatur gefunden).
- Differenzierbare Anpassung (nvdiffrast/PyTorch3D/Mitsuba 3) für Kamera, Dachhöhe, Nadel statt Zufallssuche.
- Mapillary (CC BY-SA 4.0) und Staatsarchiv-Fotos; Anfrage Stadtarchiv/Denkmalamt.
- Zifferblattdicke in der Aufteilung prüfen.

## H. Stop-Hook-Ziel "alle Maße bewiesen"
Mit offenen Daten nicht erreichbar (Raster 1 m, Laser nur von oben, Fotos ±10 %). Nur der Nutzer kann es mit `/goal clear` beenden oder lockern. Belegt: Gesamthöhe 54,80 m, Schaftquerschnitt, Glocken-/Dachform als Silhouette, ein wasserdichter Körper.

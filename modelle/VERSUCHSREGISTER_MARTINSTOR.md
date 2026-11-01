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

## I. Warum die Türmchen/Spitze nicht selbst gefunden wurden (Nutzerfrage 2026-10-31, Ursachenanalyse)
Nutzer: "die Türmchen sind zu gedrungen, die Mittelspitze stimmt nicht". Der Hinweis war **schon einmal da** (Journal Eintrag 10, Erkerkegel 7,4 m) und ist trotzdem verloren gegangen. Gründe, belegt:
1. **Rückschritt unbemerkt:** Journal 10 verlängerte den Erkerkegel auf 7,4 m. Die Laser-Korrektur (Commit 5bfbca1, "Zinnenkrone/Glockenstock/Erker nach LiDAR") senkte den Erkerkörper um 3,5 m und kürzte dabei den Kegel auf 3,5–4,5 m. Erst nach der Änderung wurde nur noch gegen den Laser geprüft, nie wieder gegen das Foto. Backups: `martinstor_v4_vor_lidar.py` 7,4 m, `vor_erker.py` 3,5 m.
2. **Messblindheit:** Mein einziges Qualitätsmaß war die Hypsometrie (Fläche über Höhe, 1-m-Raster, 13 Stufen). Türmchenkegel (1–2 Zellen) und Nadel (<1 Zelle) tragen dazu fast nichts bei; Schlankheit/Breite ist darin unsichtbar. "Grüne Zahlen" bedeuteten nicht "sieht richtig aus" (Journal 10 hatte genau diese Lehre notiert).
3. **Suchraum zu klein:** Der Optimierer hatte 16 Parameter; **Kegelhöhe, Nadeldicke, Knauf** waren nicht dabei und konnten gar nicht gefunden werden.
4. **Gute Signale weggeworfen:** OR (Erkerradius) war in allen 5 Mehrfachstarts der am besten bestimmte Parameter (1,01–1,15 statt 1,3), und mein Rastertest hatte "TWs 2,0 / OR 0,9" schon als besser als die Basis gefunden. Ich habe aber die **ganze** Lösung verworfen (weil D/W streuten bzw. weil der Versatz 0,7 aus dem Luftbild den Laser verschlechterte), statt je Parameter zu entscheiden.
5. **Laser als Wahrheit überschätzt:** DOM1 ist 1-m-Raster aus interpolierten Rohpunkten. Die "Kegel, Fußradius 1,5 m" für den Dachreiter (Journal 12) war ein Rasterartefakt; ich habe ihn als Befund übernommen. Die Fotos zeigen einen dünnen Mast mit Knauf.
6. **Falsche Beruhigung:** Silhouetten-IoU 0,92–0,93 hat große Flächen gewichtet; dünne Spitzen zählen kaum. Ich schrieb "Oberteil bestätigt" – das war zu stark.
**Regel daraus:** (a) jede Nutzer-Sichtbeobachtung ("gedrungen", "stimmt nicht") sofort in ein **messbares Kriterium** übersetzen und Foto-gegen-Render prüfen, bevor ein Laser-Wert gilt; (b) bei Änderungen nach Laserwerten immer auch Foto-Seitenvergleich; (c) Optimierer-Parameter um die sichtbaren Merkmale erweitern (Kegelhöhe, Nadel); (d) Ergebnisse je Parameter bewerten, nicht nur als Ganzes; (e) DOM1 kann **dünne Strukturen (< ~3 m)** nicht belegen.

## H. Stop-Hook-Ziel "alle Maße bewiesen"
Mit offenen Daten nicht erreichbar (Raster 1 m, Laser nur von oben, Fotos ±10 %). Nur der Nutzer kann es mit `/goal clear` beenden oder lockern. Belegt: Gesamthöhe 54,80 m, Schaftquerschnitt, Glocken-/Dachform als Silhouette, ein wasserdichter Körper.

## J. Allgemeines Breitenprofil Foto <-> Modell (`tools/foto_profil_gpu.py`, 2026-10-31)
Misst je Hoehe die Silhouettenbreite in Foto 042/043/044 und im Modell (Kamera per GPU angepasst, Faktor auf 36-48 m normiert). Kein Bauteil vorab bekannt.
- Befund (alle 3 Fotos gleich): 43-47 m ist das Foto 15-60 % BREITER als das Modell (Dach laeuft oben zu schnell zu). Unterhalb 42 m passt es (Streuung durch Verdeckung/Tuermchen).
- Erste Gegenprobe: Firsthoehe +0,8/+1,6 m: IoU steigt in allen 3 Fotos (042: .809->.815->.837), aber Spitze 54,8 und Foto 049 (First->Spitze 8,6 m) sprechen fuer 46,2 -> WIDERSPRUCH, nicht uebernommen.
- Dachabschluss breiter (frustum oben 2,0x3,8 statt 1,3x3,0): Profil 44-46 m passt (Verh. ~1,0-1,1), IoU gleich; ABER Laser verschlechtert (Ziel 14,3->15,7 %, M1 16,1->21,2 %). 2,8x4,6: 042 ueberschiesst (0,83). -> NICHT uebernommen; Foto und Laser widersprechen sich, Ursache offen (Kamera-z/Massstab-Kopplung oder Laser-Raster).
- Offen: unabhaengige Messung der Dachbreite am Vollbild (z. B. Foto 049/000) als Pruefwert, bevor der Generator geaendert wird.

### J2. Gemeinsame Anpassung ueber 10 Fotos (`tools/foto_dach_gemeinsam.py`, 2026-10-31)
Eine Dachform fuer alle, je Foto Kamera frisch verfeinert (CEM ab Basiskamera). 12 STL-Varianten: First -0,8/0/+0,8/+1,6 m x Dachabschluss 1,3x3,0 / 2,0x3,8 / 2,8x4,6 m. Fotos: 001 006 014 020 021 031 042 043 044 049 (Sichtkontrolle `dach_gemeinsam_pose_sheet.jpg`; 018 022 030 040 041 entfielen: ROI neben dem Turm, IoU-Zahl taeuschte).
Mittel-IoU (Rohdaten `dach_gemeinsam_tabelle.json`):
| First \ Abschluss | 1,3x3,0 | 2,0x3,8 | 2,8x4,6 |
|---|---|---|---|
| -0,8 | 0,8787 | 0,8794 | 0,8762 |
| 0 (Ist) | 0,8831 | 0,8840 | 0,8794 |
| +0,8 | 0,8869 | 0,8874 | 0,8814 |
| +1,6 | 0,8898 | 0,8893 | 0,8819 |
Ergebnis: UNENTSCHEIDBAR. Hoehere Firste steigen stetig (~0,004 je 0,8 m, ohne Maximum; Fotos 042, 049, 014 steigen am meisten, 001 und 031 fallen), Unterschiede <= 0,01 im Mittel = Rauschniveau der Silhouette bei 400 px. Abschluss 2,8x4,6 ist durchweg schlechter, 1,3x3,0 und 2,0x3,8 nicht trennbar. Gegenargumente gegen hoeheren First: Foto 049 (First->Spitze 8,6 m), Laser (2,0x3,8 verschlechtert M1 16,1->21,2 %). Generator NICHT geaendert.
Lehre: Silhouetten-IoU bei 400 px kann Dachhoehe/-breite nicht entscheiden; IoU-Zahl ohne Sichtkontrolle des ROI taeuscht. Naechster Weg: Kanten statt Silhouette (Dachtraufe/First als Linie im Vollbild) oder Foto-Hoehenmessung mit bekanntem Mass (Uhr, Fensterreihe) am Vollbild.

### J3. NEUER BEFUND: Dachreiter/Spitze vermutlich LAENGER als 54,8 m (Foto 049 Vollbild 1920x2880, 2026-10-31)
Silhouettenbreite je Zeile am Vollbild (Himmelsmaske, Spitze bei x=824, y=39):
- Spitze -> Oberkante Dach (Breitensprung 20 -> 162 px): 590 px. Dach oben ca. 155 px breit, Seiten +0,305 px je px (Dachflanke).
- Dach Oberkante -> Traufe (Dachunterkante ueber Schallarkaden, Sichtkontrolle `ridge049b.jpg`): ca. 490 px. Verhaeltnis Spitze/Dach = 1,20 (Modell: 8,6/10,7 = 0,80).
- Massstab im Foto: Dachbasis 304 px = 6,8-7,5 m (Modell) und Schallarkaden-Abstand ~80 px = 2 m (Modell) -> ~41-43 px/m, zwei unabhaengige Hinweise (beide aus Modellmassen, daher nicht unabhaengig vom Modell).
- Folge: Dach ~11,5-12 m (Modell 10,7: passt), Spitze ~13,8-14,2 m (Modell 8,6) -> Spitzenhoehe ca. 60-62 m statt 54,8 m. Passt zu den Textangaben 60-66 m.
- Warum der Laser das nicht sah: DOM1 (1 m Raster, ALS-Punkte) trifft eine 0,1 m dicke Nadel kaum; 54,80 m ist die hoechste GETROFFENE Flaeche (Knauf/Mast), nicht bewiesene Spitze. Mein "Texte 60-66 m falsch" (Memory lidar-massnachweis) war fuer die Nadel unbewiesen. Pruefstand-Check "Gesamthoehe 54,7-54,9" ruht auf dieser Annahme.
- Gegenprobe noetig (vor jeder Aenderung): gleiche Messung an >= 3 weiteren Fotos mit freier Spitze (001, 020, 021, 031, 000), Massstab je Foto aus Uhrscheibe/Arkaden/Fensterreihe; dann Pruefung "Spitzenhoehe" in modell_pruefstand.py (fehlschlagend), dann Generator.
J3-Fortsetzung (`tools/foto_spitze_vollbild.py`, automatische Vollbild-Messung ueber 12 Fotos): NUR 049 (16,6 m), 014 (16,0 m), 000 (12,4 m) liefern plausible Werte (alle >> Modell 8,6 m); die uebrigen scheitern (Leitungen/Nachbarn stoeren die Dach-Oberkante, Fotos nicht frontal, Steigung quantisiert) und sind WERTLOS. Der Massstab ist aus Modellmassen (Dachbasis 7,15 m, Dachhoehe 10,7 m) abgeleitet -> grobe Richtung (Spitze deutlich laenger), keine Zahl. Generator nicht geaendert. Fuer eine belastbare Zahl fehlt ein MODELLUNABHAENGIGER Massstab (bekannte Turmhoehe aus Plan/Denkmalamt/Staatsarchiv, oder Uhrscheibendurchmesser im selben Foto).

### J4. Gesamthoehe 60 m uebernommen (2026-10-31) - Dokumente + Foto, Laser blind
Quellen (WebFetch/WebSearch, 2026-10-31): Bauforschung BW (Landesamt fuer Denkmalpflege) `bauforschung-bw.de/objekt/pdf/183702660413/martinstor.pdf`: "Erhoehung um das Dreifache (von 22 m auf 60 m)" (S. 2, 7. Bauphase 1901) und "65 m hoher Turm auf Grundflaeche 10 x 11 m" (S. 4); en.Wikipedia: 22 -> 60 m; de.Wikipedia: Schaefer plante 22 -> 66 m; Structurae ~65 m. Keine Quelle nennt Dach-/Helm-/Traufhoehe.
Aenderung: `H_TOTAL 54,8 -> 60,0` (niedrigster dokumentierter Wert; passt zu Foto 049 Spitzenlaenge ~13,8 m); Spitzenlaenge ueber First 8,6 -> 13,8 m, Knauf bei 22 % = 49,2 m. Pruefstand: Gesamthoehe 59,5-66 (vorher FEHLER 54,8), neue Pruefung Spitzenlaenge 12-16,5; alle 13 Pruefungen bestanden.
Laser (optimierung_validieren alt/neu): Ziel/M1/M2/M3 UNVERAENDERT (14,3/16,1/13,9/16,1 %), M4 punktweise 1,98 -> 2,10 m (erwartet: DOM1 sieht die Nadel nicht).
Foto-Render (049/014/000, `neu60_vergleich.jpg`): Nadelspitze passt jetzt; NEU sichtbar: Dach-Oberkante im Foto ca. 40 px (~1,5-2 m) HOEHER und oben breiter als im Modell (First 46,2) - deckt sich mit IoU-Trend J2 (First +1,6 m besser). Naechster Schritt: First 47,5-48 testen (Foto + Laser), Prueffrage: widerspricht Laser (Hypsometrie bestimmte First mit Spitze 54,8!).
Offen: Bezugshoehe 60 vs 65 m (Gelaende/Fahne?), Dachhoehe nicht dokumentiert.

### J5. First-Test bei Turm 60 m (2026-10-31): Foto will hoeher, Laser verbietet es
Gemeinsame Anpassung 10 Fotos (Kamera je Foto verfeinert), Mittel-IoU: First 46,2 -> 0,8842 | 47,0 -> 0,8889 | 47,6 -> 0,8916 | 48,2 -> 0,8934 (stetig steigend, kein Maximum; 049: .805->.837, 042: .817->.857, 014 .782->.791, 001/031 leicht fallend).
Laser (optimierung_validieren, alt = 46,2): First 47,6: Ziel 14,3 -> 16,0 %, M1 16,1 -> 18,1 %, M2 13,9 -> 15,6 %, M3 16,1 -> 17,5 %; First 48,2: Ziel 19,8 %, M1 20,8 %, M2 19,4 %, M3 20,8 %. M4 punktweise 2,10 -> 2,04/2,07 m (kaum).
Ergebnis: WIDERSPRUCH bleibt (Foto-IoU +0,009 bei 2 m ~ Rauschniveau; Laser deutlich schlechter und dort messbar). First bleibt 46,2. Hinweis: Laser-Hypsometrie bewertet Flaeche ueber Hoehenstufen im 9-m-Umkreis, sieht also Dachvolumen; ein hoeherer First bei GLEICHER Flaeche (schmaleres Dach unten, steilere Flanke) wurde NICHT getestet -> naechster sinnvoller Test: Dachform (Flanken-Steigung) statt nur First.
J5-Nachtrag: First 45,0 m (Laser): Ziel 21,1 %, M1 17,7 %, M2 20,7 %, M4 2,35 m -> deutlich schlechter. Laser hat damit ein scharfes Minimum bei 46,2 m (45,0: 21,1 | 46,2: 14,3 | 47,6: 16,0 | 48,2: 19,8 %). Nutzerhinweis 2026-11-01: Turmkoerper ~45-46 m + duenne Nadel ~14-15 m = 60 m, Laser sieht nur den Koerper -> passt zum Modell (First 46,2 + Spitze 13,8). Viewer Version 15 (60 m).

### K. Seiten und Details (Start, 2026-11-01) - Foto 031 Vollbild + Fotoblatt der Turmseiten
Werkzeug `tools/foto_render_seite.py` (Foto | schattierter Render nebeneinander aus der Kamera von kameras.json). Fuer 031 unbrauchbar, weil die Kamera nur am Oberteil angepasst ist und der Azimut mehrdeutig bleibt.
Befunde (Sichtung, noch KEINE Pruefung):
1. **Das Modell hat auf allen 4 Seiten identische Fassaden** (Uhr + 2 Fenster +-2,1 m + 1 Fenster tiefer, Schleife `for f in faces`). Die Fotos zeigen mindestens zwei Seitentypen: (a) Uhr-Seiten (031, 040, 043, 044, 049, 042) mit Zinnenkranz, (b) breite Seite mit Torbogen/grossem Wappen und glatter weisser Flaeche (022, 030, 041, 050).
2. **Foto 031 (Uhrseite, 1920x2880):** unter der Uhr stehen DREI Fenster in einer Reihe (u ca. -2,6 / 0 / +2,5 m; Massstab ~48 px/m aus Schaftbreite 450 px = 9,3 m) und weiter unten ein Schlitz bei u ~ 0; Modell: nur zwei (+-2,1 m) in der Reihe -> mittleres Fenster fehlt. Uhr: Zifferblatt ~150 px (3,1 m), Rahmen ~170 px.
3. **Methodische Einsicht:** Weil alle Modellseiten gleich sind, ist der Azimut jeder Silhouettenanpassung um 90 Grad mehrdeutig (siehe Fotos 042-044). Sobald die Seiten unterscheidbar sind (Wappenseite, Uhrseite), wird die Kameralage je Foto eindeutig -> bessere Anpassung, bessere Dach-/Hoehenmessung.
Naechste Schritte: (i) je Foto Seite zuordnen (Torbogenseite vs Uhrseite, aus Sockel/Wappen), (ii) Seitenparameter im Generator (Fensteranzahl je Seite) mit Quelle als Pruefung, (iii) mittleres Fenster auf der Uhrseite ergaenzen - erst NACH Seitenzuordnung, sonst raten wir wieder.

### K2. Nord-/Suedseite unterschieden (2026-11-01, Nutzerhinweis "Uhr zeigt nach Sueden")
- Der Generator unterschied schon Uhrseiten (+-x: Uhr, 3 Fenster) und Seitenseiten (+-y: 2+1 Fenster ohne Uhr), aber +x und -x waren gleich.
- Fotosichtung (Blatt `sued_sheet.jpg`): Suedseite = McDonald's links, Fotos 041/030/042/001: zwei Schlitzfenster unter der Uhr + eines tiefer rechts der Mitte, Wappen unten. Foto 031 (andere Seite = Nordseite): DREI Fenster in einer Reihe (u -2,6/0/+2,5) + ein Schlitz tiefer bei u~0.
- Generator: `+x` = SUED (unveraendert), `-x` = NORD (3+1). Konvention; die Zuordnung zur echten Kompassrichtung stammt aus dem Nutzerhinweis und der McDonald's-Lage, nicht aus Geodaten.
- Pruefstand: 4 neue Pruefungen (Strahlenmessung der Fensternischen je Seite und Reihe); Nordseite schlug vorher fehl (2 statt 3), danach alle bestanden.
- Neue Spuren (noch ungeprueft): Foto 001/018/000: kleiner runder Eckturm mit gruenem Kegel am Sockel (neben Gedenktafel) und ein waagrechter Balken/Blende auf halber Hoehe der Schaftwand; Modell hat beides nicht belegt. Ostseite/Westseite (+-y) kaum fotografiert.

## L. Methodik-Umbau: Masstabelle + generischer Pruefstand (2026-11-01, Nutzer: "Methodik massiv verbessern")
- Befund: 10 Methodendokumente, 242 Werkzeuge, trotzdem Wiederholung derselben Fehler (Validator-Protokoll F5/F6 = Register I/J), weil Lektionen
  nicht erzwungen, Pruefcode je Objekt hart verdrahtet, Quellen fuer Merkmale benutzt, die sie nicht sehen koennen.
- Neu: `modelle/martinstor/objekt.json` (Generator, STL, Fotos mit Seite), `masstabelle.json` (17 Pruefungen + LoD2-Grundriss + 4 offene Beobachtungen),
  `tools/pruefstand.py` (generische Messer, Quellen-Blindheits-Lint Exit 2, Bericht), `tools/bauen_abnehmen.sh <objekt>`, `tools/git_hooks/pre-commit`,
  `modelle/METHODE_MASSTABELLE.md`. Alte `martinstor_bauen.sh`/`modell_pruefstand.py` sind Weiterleitungen.
- Beweise: aktuelles Modell 18/18 gruen (Werte identisch zum alten Pruefstand; Sockel 119,7 m2 vs LoD2 115,1); altes 54,8-m-STL faellt generisch durch (3 Fehler);
  Tabelle mit laser_dom1 als Quelle fuer Nadeldicke wird abgelehnt (Exit 2); Hook mit gestageter Tabelle: Exit 0.
- Nicht erledigt: `git config core.hooksPath tools/git_hooks` (Berechtigung verweigert, Nutzer aktiviert selbst); Foto-Werkzeuge lesen `objekt.json/fotos`
  noch nicht (FOTOS-Dict in foto_silhouette_gpu.py bleibt), weitere Messer (Uhr-Durchmesser, Zinnenzahl, Dachneigung) fehlen.

### J6. Dachform-Test "steilere Flanke bei gleichem Volumen" (2026-11-01)
Anlass: Foto 049/000/014 Vollbild: Halbbreiten-Zunahme der Dachflanke 0,125-0,15 je m; Modell 0,21 (Basis GY+1,5 = 7,5 m, oben 3,0 m).
Varianten (Turm 60 m, First 46,2): ist | mittel (Basis +0,9, oben 1,6x3,4) | steil (Basis +0,9, oben 2,0x3,7 -> 0,15).
Foto (10 Fotos, Kamera je Foto verfeinert): Mittel-IoU 0,8844 | 0,8859 | 0,8862 -> +0,002 = Rauschen.
Laser steil gegen ist: Ziel 14,3->13,8 (besser), M2 13,9->13,4 (besser), M1 16,1->18,4 (schlechter), M3 16,1->18,0 (schlechter), M4 2,10->2,31 m.
Ergebnis: UNENTSCHIEDEN, Generator unveraendert. Pruefung "Dachflanke" in der Masstabelle mit status=widerspruch (sichtbar, zaehlt nicht als Fehler).
Naechster Weg: Laserquelle mit mehr Aufloesung (ALS-Rohpunkte) oder Kantenmessung Dachtraufe/-first in zwei Fotos mit bekanntem Massstab.

### K3. Seiten geklaert + runder Eckturm NW eingebaut (2026-11-01)
- de.wikipedia (gelesen): Gedenktafel 1796 und Martinsbild auf der STADTSEITE; gemalter Reichsadler (bis 1951) an der TORAUSSENSEITE; 1901er Torbau WESTLICH. Stadtseite = Nord.
- Vollbilder: 001 und 031 = dieselbe Nordfassade (3 Fenster in Reihe + Schlitz, Tafel); 041/030/042 = Suedfassade (Adler, 2 Fenster + 1 tiefer). Meine Zuordnung von K2 ("001 = Sued") war falsch, die Tabelle (Sued 2+1, Nord 3+1) trotzdem richtig. objekt.json korrigiert, Seiten mit Quelle.
- Runder Eckturm (Sandstein, Kupferkegel) an der NW-Ecke zwischen Turm und Torbau (Foto 001), Suedseite ohne (Foto 000). Masse aus Foto 001 (Tafel 2,0 m = 195 px): Durchmesser 2,3 m, Traufe ~10-11 m, Spitze ~13-14,5 m.
  Generator: Zylinder r 1,15 bei (-DB/2-0,8, -WB/2+0,2), Traufgesims, Kegel 10,6-13,9 m, Knauf, 2 Schlitze. Pruefungen (vorher fehlschlagend, jetzt gruen): Durchmesser 2,0-2,7 (ist 2,3), Spitze 12-15,5 (ist 14,0). Ueberlagerung Foto 001: Lage passt (`eck_overlay.jpg`).
- Neue Pruefungen: Zinnen-Scharten 4 je Seite (N und S, Foto 031/041), Uhr-Zifferblattnische 3,9-5,2 m (MASSPRUEFUNG Teil 3: 4,5 m; Modell 4,2), Sockel-Huellrechteck gegen LoD2 11,7 x 11,4 (Polygon enthaelt die "Rundung" = Eckturm).

### L2. Werkzeuglehren aus dem Vollgas-Durchgang (generisch, in tools/pruefstand.py eingebaut)
1. `section().to_2D()` verschiebt die Schnittebene (Translation je Schnitt) -> Schwerpunkte/Bounds muessen mit der Rueckgabe-Transformation zurueckgerechnet werden. Bisher nur durch Symmetrie des Turms unschaedlich; mit dem Eckturm 2 m daneben.
2. Huellbox-Zentrierung verschiebt die Achse, sobald ein Anbau existiert -> objekt.json `zentrierung: achse` (Generator baut um 0,0); Foto-Werkzeuge lesen dieselbe Einstellung.
3. Anbauten verschmelzen im Schnitt mit dem Rumpf -> Zaehlen von Querschnitten reicht nicht; Punktmesser `ausdehnung_im_bereich` / `max_z_im_bereich(zmax)`.
4. Textparameter vs Formeln: nur `=...` ist eine Formel (seite '+x' wurde als Rechnung gelesen).
5. Reliefs mit Unterbrechungen (Stundenmarken in der Uhrnische) -> `max_luecke`.
6. Aenderungs-Diff gegen den letzten Pruefbericht nach jedem Lauf ("GEAENDERT seit letztem Lauf") = Mechanik fuer Lehre F8 (eine Eigenschaft gemeint, zwei geaendert) und F3/F4 (Ueberkorrektur).
7. status `widerspruch` fuer Pruefungen, bei denen Quellen uneins sind: sichtbar bei jedem Lauf, kein Fake-Gruen, kein Dauer-Rot.

### L3. Lehren F5/F9 als Mechanik (2026-11-01, Nutzerauftrag)
- **F9 (erfundenes Feature nie gegen Foto geprueft):** Der Generator fuehrt ein Belegregister `beleg(seite, element, quelle, masse)`; jeder Bau schreibt
  `modelle/martinstor/elemente.json` (21 Elemente). Der Pruefstand: Element ohne Quelle = FEHLER; Quelle "ANNAHME..." wird als Annahme gelistet (6: Ost/West
  Fenster, Zinnen, Schallarkaden). **Erster Fund beim Eintragen der Belege:** Inschrifttafel sass auf +x (Sued) und Doppeladler auf -x (Nord) - genau
  verkehrt zu de.wikipedia (Tafel = Stadtseite) und den Fotos. Getauscht; Pruefungen Tafel NORD 3,0-3,8 m / keine Tafel SUED / Adler SUED.
- **F5/F6 (nie ein vollstaendiger Mehrflaechen-Audit):** `tools/seiten_audit.py` erzeugt nach jedem Bau `modelle/martinstor/audit/seiten.jpg`
  (Sued/Nord/Ost/West/Draufsicht orthografisch + Foto|Render-Paare je Foto mit bekannter Seite). Laeuft in `bauen_abnehmen.sh` auch bei rotem Pruefstand.
  Der Pruefstand meldet Seiten ohne Foto als UNGEPRUEFT (Ost, West).
- Messfalle dabei: gezahnte Eckquader wechseln je Lage die Ecke -> Relief-Messungen an der Wand auf |u| < 2,5 m begrenzen.

### L4. Weitere generelle Mechaniken (2026-11-01, "suche weiter nach Methodikverbesserung")
1. **Zirkelschluss beim Massstab sichtbar:** Pruefungen tragen `massstab` (dokument/lod2/laser/foto_intern/modell). Der Pruefstand listet alle Masse, deren
   Massstab aus dem Modell stammt (6 Stueck: Tuermchenkegel, Nadel, Knauf, Spitzenlaenge) - sie belegen Richtung, nicht Zahl. Vorher stand das nirgends.
2. **Lebender Massnachweis:** `modelle/martinstor/MASSNACHWEIS.md` wird bei jedem Lauf aus der Tabelle erzeugt (Ist/Soll/Quelltyp/Massstab/Status,
   Belegt-durch-Statistik, Elemente+Annahmen, Seiten mit/ohne Foto, Widersprueche, offene Beobachtungen). Ersetzt die handgeschriebene MASSPRUEFUNG als Antwort
   auf "beweise alle Masse" - ehrlich: je Mass Quelle und Belastbarkeit.
3. **Reproduzierbare Fotomessung:** `tools/foto_mass.py` -> `messprotokoll/M-<foto>-<nr>.json/.jpg` (Pixelpunkte, Massstabskette, Unsicherheit, markierter
   Ausschnitt). Erstes Protokoll M-001-001: Eckturm 2,29 +- 0,21 m. Tabelle verweist per `protokoll`.
4. **Azimut je Fotoseite:** `foto_dach_gemeinsam.py` schraenkt die Kamerasuche auf +-50 Grad um die bekannte Seite ein (Sued +90, Nord -90, West 0, Ost 180 Grad
   in F.render) - hebt die 90-Grad-Mehrdeutigkeit des Quadratturms auf. Lauf gestartet (gem2), Ergebnis unten.
5. **Neues Objekt in Minuten:** `tools/objekt_anlegen.py <objekt> --name --hoehe --hoehe-quelle` legt objekt.json, masstabelle.json, Generator-Rumpf mit beleg()
   an; `bauen_abnehmen.sh <objekt>` laeuft sofort (getestet mit Wegwerf-Objekt: 3 Pruefungen gruen, Sichtblatt erzeugt, wieder geloescht).

## M. Echte Meter aus Fotos: Kamerakalibrierung gegen amtliche 3D-Punkte (2026-11-01, Nutzer: "tue alles, damit die Fotos echte Meter liefern")
Prinzip: Fotos liefern nur Verhaeltnisse; absolute Meter brauchen bekannte 3D-Punkte im Bild. Die gibt es amtlich: LoD2 (Grundriss-Ecken, Wandoberkanten in UTM32),
DOM1 (Tuermchen-/Spitzenhoehen), DGM1 (Gelaende). Je Foto: Pixel dieser Punkte -> Kamera (Lage, Richtung, Brennweite) loesen -> jedes Pixelpaar auf der
LoD2-Wandebene in Meter umrechnen, ohne Modell.
M1. **Fund/Fehler:** `mt_org.npy` (E 414096,8 / N 5316272,6) ist der Nominatim/OSM-Punkt, NICHT die Mitte von `mt_win.npy`; das Laserfenster war spaeter auf den
    Gipfel re-zentriert worden. Echter DOM1-Gipfel: E 414127,5 / N 5316242,5 (37 m vom OSM-Knoten); deckt sich mit der LoD2-Grundflaeche (E 414120-133,5, N 5316236-250).
    Alle frueheren Hypsometrien benutzten mt_win (richtig zentriert) - nicht betroffen. Lehre: Georeferenz nie aus einer Nebendatei annehmen, immer DOM gegen LoD2 pruefen.
M2. **Amtlicher Modellrahmen** `modelle/martinstor/anker3d.json`: Ursprung = Mitte der Endpunkte der beiden LoD2-Langwaende (E 414126,82 / N 5316242,42),
    +x = Sued entlang der Durchfahrt (254,5 Grad von Ost, d. h. SSW - die Strasse laeuft NNE), +y = Ost (344,5 Grad), z ueber DGM1 (277,93). Die "Uhr zeigt nach Sueden"-Konvention
    stimmt damit bis auf 15 Grad.
M3. Anker (Modellrahmen, Sigma): 4 Bodenecken LoD2 (+-0,3), 4 Wandoberkanten-Ecken LoD2 37,1-37,3 m (+-0,6; Modell-Glockenstock 35,5 -> pruefen),
    DOM-Gipfel (-0,3/0,6/54,8, +-1), Tuermchen DOM (4,2/-4,4/41,4) und (-3,3/-3,3/41,0) (+-0,8; nur 2 von 4 als lokale Maxima erkennbar), Spitze Dokument (0/0/60, +-3).
M4. Seitenwissen in der Silhouettenanpassung (gem2): 042 0,809->0,834, 031 0,885->0,888, 049 0,798->0,800, uebrige gleich; Azimute jetzt eindeutig je Seite.
Naechste Schritte: 2D-Picks je Foto als Protokoll (K-<foto>.json), `tools/foto_kalibrieren.py` (PnP + Brennweite, Residuen, Kamerahoehe als Plausibilitaet),
`foto_mass.py --kamera` fuer Meter auf der Wandebene; danach zirkulaere Zeilen (Nadel, Knauf, Spitzenlaenge, Dachflanke) mit echtem Massstab neu messen.
M5. **Erste echte Meter (Foto 030, Einzelkamera K-030, `foto_kalibrieren.py` + `foto_mass.py --kamera`):** Brennweite 2373 px, Standort 40 m suedlich, Augenhoehe 1,7;
    Bodenecken-Residuen 6-11 px, Dachanker 30-80 px (= die Unsicherheit der Ankerhoehen DOM/Dokument selbst). Protokolle M-030-001..005:
    Nadelspitze 57,0 m, Knauf 51,1 m, Dach-Oberkante (Goldkugeln) 47,4-47,9 m, Dachtraufe 37,9-38,2 m (!= Modell 35,5; = LoD2-Wandoberkante 37,2),
    Zinnenkranz 30,2-31,2 m (Modell 30,5 ok), Kranzbreite 10,0 m (Modell 10,3), Zifferblatt 4,04 m (Modell 4,2). Unsicherheit je Mass +-0,1..0,25 m aus Pick/Ebene,
    PLUS systematisch ~+-1 m oben aus den Ankerhoehen. Lehre: LoD2-Wandoberkante war richtig, ich hatte sie als "generalisiert" verworfen (Teil 4).
M6. **Buendel (`foto_bundle.py`, 030+041+000, freie Hoehen Spitze/Tuermchen/Kranz/First/Traufe):** gescheitert - alle Hoehen sinken um 6-19 m, RMS 70-150 px.
    Ursache: Picks von Foto 000 falsch zugeordnet (Einzelkamera landet oestlich statt suedlich), 041 ohne Bodenanker (Hoehe/Brennweite mehrdeutig,
    PnP-Scan gibt Kamerahoehe 12-18 m). Lehre: Handpicks aus verkleinerten Gitterbildern (+-20 px, Verwechslungen) sind der Engpass ->
    `tools/foto_pick_pruefen.py` (Picks + projizierte Anker + LoD2-Kanten im Foto) ist ab jetzt PFLICHT vor jedem Buendel; Fotos ohne Bodenanker nur mit EXIF-Brennweite.
M7. **Modellfreie Hoehen als Pruefzeilen (Quelltyp `foto_kalibriert`, Kamera K-030):** Dachansatz 36,9-39,2 (Modell 35,6 -> FEHLER), First 46,6-48,7 (Modell 46,7 ok, knapp),
    Zinnenkranz-Oberkante 29,5-32,5 (Modell 31,5 ok), Gesamthoehe 60 (Dokument) jetzt `widerspruch` gegen Foto 57,0 / Buendel 55,0. Neue Messer: `ausdehnung_streifen`,
    `z_bei_breite` (Dachansatz = erste Hoehe mit Dachbreite >= 6,8 m im Achsstreifen; First = hoechste Hoehe mit >= 2 m), Erker/Konsolen aus Regionen ausgeblendet.
    Varianten gestartet (grid4): v1 Traufe 38 (Glockenstock +2,5), v2 + First 47,6 (Dach 9,6 m), v3 + Spitze 57 -> Laser (optimierung_validieren) + Foto-IoU (gem2, Seitenwissen).
M8. **Pick-Werkzeug Vollaufloesung (`tools/foto_pick.py`, Nutzerauftrag):** `auto` findet Spitzen (Oberkontur, Kantenschnitt) und Goldkugeln (kleine runde goldfarbene
    Komponenten) in der Himmelsmaske auf +-1-2 px; `lupe` erzeugt 3x-Ausschnitte mit 10-px-Gitter je Pick; `setze` protokolliert Korrekturen (pick_historie).
    Dazu interaktive Pick-Seite (pick_030.html, Artefakt) mit Zoom/8x-Lupe/Pfeiltasten fuer den Nutzer. Himmelsmaske: Referenzmethode versagte bei 030 (Baum/Leitung
    am oberen Rand -> 0,1 % Himmel) -> robuster Farb-Fallback (blau-dominant, mit Bildrand verbunden). Auto bestaetigte Handpicks auf 5-13 px (Kugeln) und zeigte,
    dass "Spitzen"-Picks besser als Kugelmitte definiert werden (stabil, +-1 px).
M9. **Varianten aus den Fotomassen (grid4), Laser gegen Foto:** V1 Traufe 38 (Glockenstock +2,5, Dach gleich): Laser Ziel 14,3->27,3 %, M1 16,1->34,4 %, Foto-IoU 0,8816->0,8843
    (Nordfotos 001/031 schlechter, 049/000 besser). V2 Traufe 38 + First 47,6: Laser 19,6 % / M1 25,2 %, Foto 0,8824. V3 + Spitze 57: Laser wie V2, Foto 0,8814.
    Ergebnis: Laser widerspricht der hoeheren Traufe deutlich; die Foto-Kalibrierung hat oben ~+-1 m systematischen Fehler (Anker-Residuen 50-80 px). Modell unveraendert,
    Zeile "Dachansatz" = widerspruch. Naechster Schritt: praezises Buendel (Pick-Werkzeug, 3 Fotos mit Boden) ODER ALS-Rohpunkte, bevor Traufe/First/Spitze angefasst werden.

## N. Fehlteil-Finder + Uhrgiebel + Kragdach (2026-11-01, Nutzer: "geschwungenes Daechlein ueber der Uhr, gruenes Daechlein zwischen den Tuermen - loese es generell automatisch")
- **Mechanik `tools/fehlteile_finden.py`:** Modell mit kalibrierter Kamera (K-<foto>, ersatzweise Silhouettenkamera) rendern -> Tiefe gefuellt (Min-Filter), Modellkanten aus
  Tiefensprung/Kruemmung; Foto auf 7 cm geglaettet (Steinfugen weg), Canny; beide um 0,3 m dilatiert (Kamerafehler), je 1-m-Zelle Kantendichte Foto vs Modell (auf 90-%-Quantil
  normiert), Treffer nur mit >= 2 gleichsinnigen Nachbarzellen; 3D-Lage aus dem Render; Treffer werden als Beobachtungen in die Masstabelle geschrieben (einmal je Zelle).
  Am ALTEN Modell markierte er die Zone Uhr-Oberkante/Kragdach (z 29-31 m) als FEHLT - genau die vom Nutzer genannten Teile. Weitere Treffer: SE-Kante (Eckquader in jeder
  Lage im Foto, im Modell gezahnt = jede zweite), Torbogen-Inneres (ERFUNDEN?, Schatten). Grenzen: Kamerafehler ~0,5-1 m erzeugt Randtreffer; Verdeckungen (Baum).
- **Generator:** Kielbogen-Daechlein ueber dem Uhrrahmen (S-Kurve, Spannweite 2*(UR+1), Hoehe 1,25, Scheitel 30,6 unter dem Kranz), Kragdach als Kupferschraege vom
  Zinnenkern (ZZ+0,2, D-0,3) bis zur Glockenstockwand (ZZ+2,4) - vorher ein kleiner Kegel innen, der in den Fotos nicht sichtbar war. Beide mit beleg().
- **Fallen dabei:** (1) erster Kragdach-Ansatz begann bei ZZ+1,1 -> Durchblick-Schlitz zwischen Zinnenkern und Kragdach (im Druck ein Loch); gefunden, weil der Scharten-
  Zaehler plötzlich 3 statt 4 fand - Strahlen gingen durch. (2) `nischen_anzahl` wertete "kein Treffer" (nan) als keine Nische -> jetzt als tiefe Nische. (3) erster
  Kielbogen reichte mit dem Scheitel bis 31,05 in die Scharten.
- Pruefstand: 29 Pruefungen gruen, 2 Widersprueche (Dachansatz, Dachflanke), 3 Beobachtungen. Viewer v18.

## O. Dachansatz-Widerspruch aufgeloest + neuer Befund Turmkopf (2026-11-01)
**Werkzeug `tools/hypso_profil.py` (neu): Flaeche je Hoehenstufe statt Gesamtnote**, mit (a) GEMEINSAMER Lage fuer alle Modelle (vorher suchte jedes
Modell seine eigene beste Drehung - unfairer Vergleich) und (b) der Messunsicherheit des Lasers selbst (Umkreismitte +-1 m, Radius 8,5-9,5 m).
Nur Abweichungen ausserhalb dieser Spanne sind echt.
- **Dachansatz: Laser gewinnt, Widerspruch zu.** Bei 38/40/42/44 m hat DOM1 NULL Streuung (62/43/28/20 m2 - grosse, flach liegende Dachflaechen).
  Traufe 38 weicht dort +16/+17/+12/+9 m2 ab (bis +40 %), die aktuelle Traufe 35,5 nur +4/-1/0/-2. Die Foto-Kalibrierung (37,4-38,2 m) hat oben
  1-2 m systematischen Fehler (Ankerhoehen +-1 m, Residuen 50-80 px) und was ich als "Traufe" pickte, ist vermutlich nicht die Dachansatzkante.
  Pruefzeile umgestellt auf Laser (34,5-36,5), Historie dokumentiert. **Lehre: eine Gesamtnote verdeckt, WO eine Quelle stark ist.**
- **Neuer Befund: Turmkopf 28-32 m rund 20 % zu breit** (Modell 144/144/120 gerastert gegen Laser 121/118/97, Laserstreuung nur +-3).
  Einzeltests: Erker TWs 2,6->2,2 wirkt nur bei 32 m (120->114), Kranzueberstand 0,35->0,15 wirkt gar nicht (dann ragen die Erker vor),
  Schaft 9,3x10,3 -> 8,9x9,8 bringt 144->134. **Keine Einzelaenderung reicht** - Ursache noch nicht isoliert.
  Zweiter, unabhaengiger Beleg: Foto-Messung M-030-009 (kalibrierte Kamera) gibt den Abstand der Zinnenkranz-Ecken SW-SE mit 9,97 m, Modell 11,0 m.
  Zwei Pruefzeilen stehen ROT (Laserflaeche ueber 30 und 32 m) - Modell NICHT freigegeben, Befund dokumentiert.
- **Neuer Messer `hypso_ueber`** im Pruefstand rastert jetzt genau wie der Laser. Erster Versuch verglich die ECHTE Querschnittsflaeche (77 m2)
  mit gerasterten Laserzellen (97) - zwei verschiedene Groessen. Lehre: vor jedem Quellenvergleich pruefen, ob beide Seiten dasselbe messen.
- **`tools/variante_bauen.sh` (neu):** baut eine Generator-Variante und BRICHT AB, wenn das sed-Muster nicht greift. Ausloeser: drei "Varianten"
  (TWs 2,2/2,0) waren bitgleich mit dem Ist-Modell, weil das Muster "TWs = 2.6" nicht auf "TWs, T0, T1 = 2.6," passte - der Vergleich zeigte
  faelschlich "kein Einfluss". Zusaetzlich Warnung, wenn das fertige STL bitgleich mit dem Ist-Modell ist.

## P. Turmkopfbreite automatisch am Vollbild (2026-11-01, Nutzer: "generalisiert, nie mehr manuell eingreifen")
**`tools/foto_breitenprofil.py`:** legt fuer jede Hoehe ein METER-Lineal in die Vertikalebene durch die Turmachse (senkrecht zur Blickrichtung),
projiziert es mit der kalibrierten Kamera ins Bild und tastet es ab - der aeusserste Punkt, der noch zum Bauwerk gehoert, gibt die Halbbreite.
Dasselbe am Modell. Keine Handpicks, kein Massstab aus dem Modell. Laeuft jetzt bei JEDEM Bau automatisch (`bauen_abnehmen.sh` ueber alle Fotos
mit Kamera), traegt Abweichungen als ZONEN in die Masstabelle ein und steigt bei schlechter Kamera selbst aus.
**Ergebnis Turmkopf: die Quellen sind uneins.** Foto 030 (Guete 0,73): 13,40 m bei 30 m = Modell 13,58, Median-Differenz ueber 19 Hoehen -0,02 m.
Foto 000 (Guete 0,88): bei 25-32 m nur 11,5-12,4 m (-2 bis -3 m). -> Pruefzeile mit status `widerspruch`; die Kameras sind fuer +-0,5 m noch zu ungenau.
**Der Laser-Befund aus O (Turmkopf 20 % zu breit) ist damit WIDERLEGT als Modellfehler:** DOM1 ist 1-m-interpoliert und verliert Vorspruenge < ~1 m
(Zinnenkranz 0,35 m, Erkerauskragung) - die Flaeche ueber Hoehe faellt dann 15-20 % zu klein aus. Quellen-Matrix korrigiert: `laser_dom1` ist auch fuer
`grundriss` BLIND. Die zwei roten Laserzeilen wurden ersetzt. Beleg: kein Einzelparameter (Erker, Kranz, Schaft) konnte die Laserflaeche erreichen,
waehrend die Silhouette im Foto exakt passte.
**Vier Fallen, alle mechanisch geschlossen:**
1. Himmelsmaske machte die WEISSE TURMWAND zu Himmel ("hell und ungesaettigt") -> Breiten von 5,8 m statt 13 m. Jetzt drei Verfahren nacheinander
   mit Plausibilitaetstest (oberer Rand >= 30 % Himmel, untere Bildmitte <= 25 %); keine plausible Maske = Abbruch statt stiller Unsinn.
2. Schlechte Kamera (Foto 041: RMS 530 px) lieferte Modellbreiten von 1,5 m. Jetzt prueft das Werkzeug die Silhouetten-Ueberdeckung und bricht unter 0,60 ab.
3. Punktwolken-Loecher liessen den Abtaststrahl zu frueh abbrechen (8,58 statt 13,58 m). Jetzt werden Luecken bis 0,12 m uebersprungen.
4. Beobachtungen je Hoehe = 60 Eintraege Rauschen. Jetzt zusammenhaengende Zonen.
**Generelle Lehre:** Jedes Messwerkzeug prueft seine Eingangsdaten selbst (Maske plausibel? Kamera gut genug?) und verweigert die Messung, statt
eine Zahl zu liefern, die niemand nachprueft. Eine Quelle darf ein Merkmal nur belegen, wenn sie es aufloest - das steht in der Quellen-Matrix.

## Q. Kameras 031 und 041 brauchbar gemacht - Silhouettenterm (2026-11-01)
**Problem:** Beide Fotos haben keinen Bodenanker, die Kamera haengt an 3-9 Handpicks -> Hoehe und Brennweite mehrdeutig (041: RMS 530 px,
Modellbreiten 1,5 m statt 13 m). **Loesung (generell, `tools/foto_kalibrieren.py --silhouette`):** zweiter Term aus der GANZEN Silhouettenkante
gegen den Himmel. Distanztransformation der Fotokante; feste 3D-Randpunkte des Modells werden darauf gezogen, bilinear interpoliert, ICP-artig
in 3 Runden nachgefuehrt. Ergebnis: 031 Kantenabstand 17,7 -> 7,1 px (Guete 0,59 -> 0,61), 041 29,8 -> 9,4 px (RMS 530 -> 56 px, Guete 0,58 -> 0,62).
**Drei Fehler dabei, alle mechanisch geschlossen:**
1. **Namenskonflikt:** `for name, uv in K["punkte"].items(): a = A[name]` ueberschrieb `a = sys.argv` - danach war JEDE Option wirkungslos
   (`--silhouette` wurde stillschweigend ignoriert, das Ergebnis blieb bitgleich). Variable umbenannt; zusaetzlich meldet das Werkzeug jetzt die
   erkannten Optionen und bricht bei unbekannten ab.
2. **Stueckweise konstanter Term:** die gerasterte Modellkante aendert sich bei kleinen Parameteraenderungen nicht -> numerischer Gradient null,
   der Loeser bewegt nichts. Jetzt feste 3D-Punkte mit stetig interpoliertem Abstand.
3. **Verdeckte Kanten:** Foto 000 mass rechts 4,1 statt 7,4 m (Baum, mit Himmel dahinter - die Himmelspruefung allein reicht nicht). Zwei Regeln:
   (a) weichen beide Seiten GEGENSINNIG um > 1 m ab, ist eine Kante verdeckt -> verworfen; (b) eine EINSEITIGE Messung darf bestaetigen, aber keine
   grosse Abweichung belegen (> 1,5 m -> verworfen). Damit faellt Foto 000 korrekt raus.
**Ergebnis Turmkopf: Widerspruch aufgeloest, das Modell ist bestaetigt.** Drei unabhaengig kalibrierte Kameras ueber 26-40 m:
030 Median -0,06 m, 031 +0,12 m, 041 -0,20 m (Spannen +-0,9 m). Die Pruefzeile "Silhouettenbreite bei 30 m" steht auf gruen, der frueher
vermutete Modellfehler (Laser: "20 % zu breit") bleibt widerlegt.

## R. Dachflanken-Widerspruch aufgeloest: die zirkulaere Messung war schuld (2026-11-01)
Die alte Zeile "Halbbreiten-Zunahme 0,11-0,19 je m" stammte aus Foto 049 mit einem Massstab AUS MODELLMASSEN (zirkulaer, Register J3) und
stand seit 2026-10-31 als Widerspruch gegen den Laser. **Mit den drei kalibrierten Kameras ist sie ueberfluessig:** `foto_breitenprofil --steigung 37,46`
misst Foto und Modell mit demselben Verfahren und gibt Foto 030: 0,486, Foto 031: 0,475, Foto 041: 0,481 gegen Modell 0,437-0,505 - Differenz
hoechstens 0,05. **Die Modellflanke ist bestaetigt, der Widerspruch war ein Artefakt der zirkulaeren Messung.** Masstabelle: Zeile ersetzt
(Soll 0,40-0,56 aus drei Kameras), Historie dokumentiert. Damit stehen 0 Widersprueche offen.
**Generelle Mechanik daraus:** Der Pruefstand meldet jetzt nicht nur, welche Zeilen einen Massstab aus dem Modell haben (zirkulaer), sondern auch,
welche davon ERSETZBAR sind - naemlich wenn fuer dasselbe Merkmal inzwischen eine modellfreie Quelle (Dokument, LoD2, Laser, kalibriertes Foto)
existiert. Zirkulaere Zeilen taeuschen Widersprueche vor und muessen weichen, sobald es etwas Besseres gibt.

## S. GPU-Nutzung gemessen und ausgebaut (2026-11-01, Nutzerfrage "wie stark nutzen wir die GPU?")
**Befund:** 15 aeltere Werkzeuge nutzen CUDA (foto_silhouette_gpu, hypso_gpu, generator_optimierer, VGGT ...), aber ALLE in dieser Sitzung
gebauten Messwerkzeuge liefen auf der CPU. Laufzeiten vorher: seiten_audit 26,3 s | hypso_profil 13,5 s je STL | fehlteile_finden 7,8 s |
pruefstand 4,7 s | foto_breitenprofil 3,1 s - ein Bau-Durchlauf also rund 110 s.
**Erste Messung war ernuechternd:** GPU-Rasterung allein brachte NICHTS (0,33 s gegen 0,20 s auf CPU) - die Projektion lief in numpy, und der
Transfer CPU->GPU->CPU frass den Gewinn. **Erst als die Punktwolke auf der GPU BLEIBT** (`render_kern.Szene`), lohnt es: 10 Masken 0,14 s statt
2,43 s (17x), 10 schattierte Bilder 0,14 s statt 2,90 s (21x).
**`tools/render_kern.py` (neu): EIN Renderkern fuer alle Werkzeuge** - projizieren, Z-Puffer (scatter_reduce amin), Maske, schattiertes Bild,
Hypsometrie. Grund ist nicht nur Tempo: dieselbe Rechnung steckte vierfach im Code (pruefstand, foto_breitenprofil, fehlteile_finden,
seiten_audit) und die Fassungen wichen bereits voneinander ab (8,58 m gegen 13,58 m, weil eine weniger Punkte nahm). Vier Implementierungen
sind vier Fehlerquellen. `RENDER_CPU=1` schaltet auf CPU, Ergebnis identisch.
**Umgestellt:** seiten_audit 26,3 s -> 3,5 s (7,4x), bei 2,5 statt 1,5 Mio Punkten. Offen: fehlteile_finden, foto_breitenprofil,
pruefstand.silhouettenbreite, hypso_profil (Lagesuche: 350 Rasterungen, dort ist der groesste verbleibende Gewinn) und
foto_kalibrieren --silhouette (hunderte Projektionen je Optimierungslauf).
**Generelle Lehre:** GPU lohnt nicht pro Aufruf, sondern pro DATENSATZ - die Daten muessen oben bleiben. Und: bevor man optimiert, misst man;
die erste, naheliegende GPU-Variante war langsamer als die CPU.
S2. **Alle Werkzeuge auf den Renderkern umgestellt (2026-11-01).** Laufzeiten vorher -> nachher, jeweils mit Regressionsvergleich:

| Werkzeug | vorher | nachher | Ergebnis |
|---|---|---|---|
| seiten_audit | 26,3 s | 3,5 s | Bild gleich (bei 2,5 statt 1,5 Mio Punkten) |
| hypso_profil | 13,5 s | 4,9 s | Zahlen BITIDENTISCH zur CPU-Fassung |
| fehlteile_finden | 7,8 s | 3,5 s | Treffer gleich, 3D-Lagen um ~0,1 m verschoben (rint statt Abschneiden - korrekter) |
| pruefstand | 4,7 s | 2,4 s | alle Werte identisch (Toleranz 0,01) |
| foto_breitenprofil | 3,1 s | 3,2 s | identisch (nur EIN Render - GPU bringt hier nichts) |
| **Bau-Durchlauf gesamt** | **~110 s** | **33 s** | |

**Zwei Lehren, die generell gelten:**
1. **GPU lohnt pro Datensatz, nicht pro Aufruf.** Die erste Fassung (nur die Rasterung auf der GPU, Projektion in numpy) war LANGSAMER als die CPU,
   weil der Transfer den Gewinn frass. Erst `Szene`, die die Punktwolke oben behaelt, bringt 17-21x. Wo nur einmal gerendert wird
   (foto_breitenprofil), bleibt es bei null Gewinn - und das ist in Ordnung, der Renderkern ist dort trotzdem richtig (eine Fassung statt vier).
2. **Batch-Groesse nach freiem Speicher.** 350 Lagen x 800k Punkte sprengten die 8 GB (OOM). `hypso_lagen` teilt jetzt selbst in Bloecke
   (`mem_get_info`, ~40 Byte je Lage und Punkt) - ohne Zutun des Aufrufers.
**Regression ist Pflicht:** vor der Umstellung wurden Referenzausgaben gesichert und danach verglichen. Ohne das haette ich die 0,1-m-Verschiebung
in fehlteile_finden nicht bemerkt und nicht erklaeren koennen.

## T. Die 23 Beobachtungen abgearbeitet - und zwar maschinell (2026-11-01)
**`tools/beobachtungen_sichten.py` (neu)** gruppiert die automatischen Meldungen nach Hoehenzone und entscheidet nach fester Regel:
BESTAETIGT (>= 2 Fotos, gleiches Vorzeichen, >= 0,5 m) | UNEINS (Fotos gegensaetzlich -> Kamerafehler/Verdeckung, geschlossen) |
TEXTUR (Fehlteil-Treffer an der Fassadenkante ueber viele Hoehen = Steinfugen/Eckquader, kein Bauteil) | EINZELN (ein Foto, braucht ein zweites).
**Von 21 Meldungen blieb EINE uebrig:** z 29-33,5 m, Modell 0,72 m zu breit, von Foto 031 UND 041 bestaetigt - dieselbe Zone, die der Laser
gemeldet hatte. 12 wurden automatisch geschlossen (5x Steinfugen an der SE-Kante, 3 Gruppen gegensaetzlich), 9 blieben einzeln.
**Ursache isoliert - und es war keine der Vermutungen:** Erker schmaler (TWs 2,2) machte es SCHLECHTER, Kranzueberstand wirkte gar nicht.
Die Silhouette dort kommt vom SCHAFT. Dessen Verjuengung (9,8x11,3 unten auf 9,3x10,3 oben) war reine Annahme, durch nichts belegt.
**Ueberkorrektur-Falle (F3/F4) sofort eingetreten:** Schaft durchgehend auf 9,0x10,0 loeste die obere Zone und machte 23,5-28 m um 0,73 m zu
schmal - die naechste Sichtung meldete das prompt als neu BESTAETIGT. Loesung: **zweistufige Verjuengung mit Knick bei 26 m** (bis dahin
9,3x10,3 wie bisher, darueber auf 9,0x10,0). Ergebnis ueber drei Kameras: 030 +0,27/+0,25, 031 +0,75/-0,14, 041 +0,09/-0,21.
Drei neue Pruefzeilen (Zone 23,5-28 / 29-33,5 aus 031, 29-31,5 aus 041) sichern beide Zonen.
**Drei Mess-Fallen, alle vom Typ "zwei verschiedene Groessen verglichen":** (1) Sollwert aus einem ZONENMITTEL gegen eine Messung bei EINER
Hoehe (12,60 gegen Soll 11,1-11,9) -> Messer mittelt jetzt ueber dieselbe Zone; (2) Foto verdoppelt die freie Halbbreite, Pruefstand nahm beide
Seiten (12,50 gegen 11,74) -> Messer kennt jetzt die Seite; (3) Gruppierung der Beobachtungen nach Zonenanfang statt Ueberlappung verdeckte den
einzigen bestaetigten Befund, danach kettete die Ueberlappung ueber den halben Turm -> echte Ueberlappung UND Gruppe hoechstens 5 m hoch.
**Stand: 31 Pruefungen gruen, 0 Widersprueche, 6 einzelne Beobachtungen (brauchen ein zweites Foto).**

## U. Tuermchen-Gliederung und Kragdach (2026-11-01, Nutzer: "Uhr tiefer, haengende Daecher, gruenes Daechlein zwischen den 4 Tuermen")
**Warum ich es nicht selbst fand:** Der Fehlteil-Finder HATTE die Stellen gemeldet (z 28,7 und 30,8 m in Foto 030), aber die Triage stufte sie
als EINZELN ein (nur ein Foto) und legte sie beiseite. **EINZELN heisst nicht "ignorieren", sondern "an einem zweiten Foto pruefen"** - diese
Nachpruefung fehlte als Schritt.
**Zwei echte Modellfehler gefunden:**
1. **Das "Kragdach" kragte nicht.** Es lief von 8,7 m Breite innerhalb des 9,7 m breiten Zinnenkranzes - von aussen unsichtbar. Ursache: Beim
   Schliessen eines Durchblick-Schlitzes (Register N) hatte ich es nach INNEN verlegt statt den Schlitz anders zu schliessen. Jetzt beginnt es
   auf Kranzhoehe mit Kranzbreite und steigt zum Glockenstock - so schaut es zwischen den Zinnen hervor wie im Foto.
2. **Die Ecktuermchen hatten eine offene Arkade aus 8 duennen Saeulen** statt eines geschlossenen Erkerkoerpers. Messung: bei 34 m nur 0,30 m
   Durchmesser, im Foto 2,2-2,6 m. Jetzt geschlossener Achteckkoerper mit Fenstern (OR 1,18), eigenes kleines Pyramidendach darueber, dann erst
   der Helm (5,3 -> 4,6 m, schlanker). Zwei neue Pruefzeilen: Erkerkoerper bei 34 m (2,0-2,9) und Helm bei 37 m (0,8-1,9).
**Offen (als Beobachtung notiert):** Die Uhr sitzt laut Nutzer tiefer als im Modell. Die automatische Kreissuche (`tools/foto_element_hoehe.py`,
neu: findet Kreise und Oeffnungen und misst ihre Hoehe ueber die kalibrierte Kamera) findet das Zifferblatt NICHT - Hough liefert nur
Wolkenstrukturen, der Geometriefilter verwirft alles. Naechster Weg: Goldring farblich maskieren statt Hough.
**GPU-Nachtrag (Nutzer "nutze mehr GPU"):** Die Linealabtastung im Breitenprofil auf die GPU gebracht - KEIN Gewinn (3,21 gegen 3,19 s) und
abweichende Werte. Profiling zeigt warum: von 3,2 s gehen 1,27 s in die Himmelsmaske, 0,58 s in STL+Sampeln, 0,26 s in die Modellmaske und
nur **0,01 s** in die Abtastung. Der GPU-Pfad wurde wieder abgeschaltet (bleibt als dokumentierter Fehlversuch), stattdessen wird die
Himmelsmaske jetzt je Foto zwischengespeichert. **Lehre: erst profilieren, dann optimieren - zweimal hintereinander die falsche Stelle beschleunigt.**

## V. Befund 36-41 m: Artefakt der Mittelwertbildung - Triage-Regel verschaerft (2026-11-01)
**Nachgemessen statt geglaubt:** Das Detailprofil 34-42 m zeigt, dass die beiden Fotos NICHT einig sind - Foto 030 meldet bei 41 m +1,60 m,
Foto 031 dort +0,00 m. Meine Triage hatte den Befund als BESTAETIGT eingestuft, weil sie nur das Mittel ueber alle Meldungen prueft (+1,02 m).
**Regel verschaerft:** BESTAETIGT nur noch, wenn JEDES beteiligte Foto fuer sich >= 0,4 m abweicht (je Foto gemittelt) und alle dasselbe
Vorzeichen haben; sonst SCHWACH und geschlossen. Das ist dieselbe Falle wie "Zonenmittel gegen Einzelhoehe" (Register T): **ein Mittelwert ueber
uneinige Quellen sieht aus wie ein Befund.** Danach: 0 BESTAETIGT von 17 Meldungen.
**Neue Mechanik `--nachpruefen` (die fehlende Haelfte):** Fuer jeden EINZELN-Befund werden die UEBRIGEN Kameras an genau dieser Hoehe befragt -
auch wenn sie dort keine eigene Zone gemeldet haben (eine Abweichung unter der Meldeschwelle ist trotzdem eine Aussage). Genau dieser Schritt
fehlte, weshalb die Tuermchen-Gliederung (Register U) liegen blieb, bis der Nutzer sie fand.
Ergebnis fuer alle vier Einzelbefunde: **widerlegt** - z 39,5-41 (030+1,13 gegen 031+0,35, 041+0,28), z 23,5-28 (031+0,81 gegen 030+0,26, 041+0,08),
z 36-37,5 (031+0,79 gegen 030-0,10, 041-0,01), z 31,5-33,5 (031-0,59 gegen 000+0,84, 030+0,31, 041-0,06). Das Modell ist dort in Ordnung;
die Einzelmeldungen waren Kamerafehler und Rauschen. Sie werden mit dieser Begruendung geschlossen, nicht stillschweigend geloescht.

## W. Beweis der Generalitaet: zweites Objekt ohne Codeaenderung (2026-11-01, Nutzer: "beweise, dass du generell gelernt hast")
**Test:** `python3 tools/objekt_anlegen.py schwabentor --name "Schwabentor" --hoehe 51 --hoehe-quelle "Wikipedia"` und dann
`tools/bauen_abnehmen.sh schwabentor`. **Keine Zeile Werkzeugcode angefasst.** Ergebnis: Generator-Rumpf gebaut, STL erzeugt,
Pruefstand mit der Dokumenthoehe gelaufen (51,00 in 49,5-52,5), Belegregister gefuehrt (1 Element, als ANNAHME markiert),
Sichtblatt auf der GPU gerendert, Beobachtung "Quellen sichten" angelegt.
**Die drei Schutzmechaniken greifen auch dort** (am NEUEN Objekt geprueft, danach zurueckgebaut):
1. Quellen-Blindheit: Zeile "Turmspitze duenn" mit `laser_dom1` -> TABELLE UNZULAESSIG mit Begruendung.
2. Belegpflicht: Element `beleg("+x", "Erfundener Erker", "")` -> "FEHLER Element OHNE BELEG: Sued: Erfundener Erker (Lehre F9)".
3. Variantenpruefung: sed-Muster ohne Treffer -> "FEHLER: sed-Muster hat nicht gegriffen, Variante waere identisch".
**Objektwissen im Code:** `grep -i martinstor` findet in den 13 neuen Werkzeugen nur Kommentare, Registerverweise und Beispielaufrufe -
keine funktionale Zeile. Keine hartkodierten Martinstor-Masse oder -Pfade (mt_dom, 54.8, 46.2, 9.3x10.3) ausserhalb der objektspezifischen
Dateien `modelle/martinstor/*.json` und `modelle/martinstor_v4_gen.py`.
**Grenze, ehrlich:** Das Schwabentor hat hier nur einen Quader als Generator und keine Fotos - bewiesen ist, dass Rahmen, Pruefstand,
Belegregister, Sichtblatt und die Sperren objektunabhaengig laufen, NICHT dass die Fotomessung ohne eigene Anker funktioniert.
Dafuer braeuchte es LoD2/DOM fuer das zweite Objekt und Fotos mit freier Silhouette.

## X. Uhrhoehe farblich gemessen (2026-11-01)
Die Hough-Kreissuche fand das Zifferblatt nicht (nur Wolken). **Farbsuche** (`foto_element_hoehe.py farbe --ton 12,32 --saettigung-min 80 --rund`)
findet es sofort: Foto 030 -> 26,84 m (Durchmesser 3,80), Foto 041 -> 26,64 und 27,94 m, Foto 031 -> 24,66 m (4,45 m).
**Die zwei besten Kameras (030/041, RMS 57/56 px) bestaetigen die Modellhoehe 26,9 m; nur die schwaechste (031, RMS 146 px) sieht die Uhr tiefer.**
Der Nutzerhinweis "Uhr sitzt tiefer" ist damit an der Uhrhoehe NICHT bestaetigt - moeglicherweise war ein anderer Abstand gemeint
(zum Zinnenkranz oder zum Gesims). Als Rueckfrage notiert. Neue Pruefzeile "Uhr Zifferblatt-Hoehe 26,0-28,2 m" (quelltyp foto_kalibriert).
**Lehre: Form-Detektoren (Hough) scheitern an gestoerten Konturen; Farbe ist bei Bauteilen oft das robustere Merkmal.**

## Y. Wie generisch ist es wirklich? Gemessen (2026-11-01, Nutzer: "wie viel % generell?")
**Zeilen, gezaehlt:**
| Teil | Zeilen | generisch? |
|---|---|---|
| 12 Messwerkzeuge (`tools/`) | 1489 | ja - laufen fuer jedes Objekt (Beweis Register W) |
| Generator `martinstor_v4_gen.py`, Funktionen | 173 (39 %) | ja, aber nur hier - 17 Element-Generatoren (box, fbox, fcyl, frustum, prism, quoins, window, bruchstein, clock3, falze, hxy ...) |
| Generator, Komposition und Masse | 275 (61 %) | nein - und das ist richtig: das IST das Bauwerk |
| Daten `modelle/martinstor/*.json` | 3027 | nein - und das ist richtig: Masstabelle, Anker, Protokolle |
**Code, der fuer ein zweites Bauwerk wiederverwendbar ist: 1489 + 173 = 1662 von 1937 Zeilen = 86 %.** Die restlichen 275 Zeilen
sind die Form dieses Turms - ein zweites Bauwerk braucht dort eigene Zeilen, so wie es einen eigenen Bauplan braucht.
**Drei echte Hardcodings in den WERKZEUGEN gefunden und behoben** (das waren die letzten):
1. `hypso_profil.py` hatte Laserfenster und Gelaendehoehe fest im Code (`mt_win.npy`, 277.98) -> jetzt `objekt.json/laser`.
2. `foto_kalibrieren.py` hatte die Augenhoehe 1,7 m zweimal fest -> jetzt `objekt.json/augenhoehe_m`.
3. `seiten_audit.py` und `fehlteile_finden.py` hatten den Brennweitenfaktor der Silhouettenkamera (5,4/4,29, aus einer Pentax) im Ausdruck -> benannte Konstante `SIL_F0`.
**Der Weg zu ~100 %** ist nicht, die 275 Zeilen wegzuoptimieren, sondern die 17 Element-Generatoren in eine BIBLIOTHEK zu ziehen
(`tools/bauwerk_generator.py` hat diesen Ansatz schon: Elemente per Config komponieren). Dann waere ein Generator nur noch eine
Liste "welches Element mit welchen Massen" - also Daten, nicht Code. Geschaetzter Aufwand: die 17 Funktionen sind bereits
objektunabhaengig geschrieben und muessten nur umziehen; die Komposition bliebe als Config.

## Z. Umzug der Bauteile in eine Bibliothek - mit Bit-Beweis (2026-11-01)
**`tools/bauteile.py` (neu, 186 Zeilen):** 11 Bauteil-Generatoren, die bis dahin im Martinstor-Generator lagen, obwohl sie nichts
Bauwerksspezifisches enthalten: freie Funktionen `box, fbox, fcyl, frustum, prism` und die Klasse `Bau` (haelt adds/cuts/late,
Massstab, Standard-Halbmasse) mit `window, quoins, clock, clock3, bruchstein, falze`. Der Generator ist von 448 auf 323 Zeilen
geschrumpft und enthaelt jetzt im Wesentlichen Masse und Komposition.
**Beweis, dass nichts schlechter wurde:**
- STL **bitidentisch** (md5 a8dcc8cf... vorher wie nachher), 25.632 Dreiecke, Volumen 5534,5 cm3, Huelle 141,9 x 148,1 x 689,7 mm.
- Alle Pruefwerte bitidentisch (Toleranz 1e-9), Belegregister (24 Elemente) identisch, 0 Widersprueche.
- Das zweite Objekt (Schwabentor) nutzt dieselbe Bibliothek (`frustum`) und laeuft gruen durch.
**Drei Fallen beim Refactor, alle aufgetreten und behoben:**
1. **Neu geschrieben statt verschoben:** meine erste `quoins`-Fassung in der Bibliothek hatte eine andere Schleifenreihenfolge und
   `rel(0.1)` statt `rel(0.12)` - das haette die Geometrie still veraendert. Danach wurden die Funktionen per ZEILENBEREICH kopiert.
2. **Regex ueber den ganzen Text** loeschte beim Entfernen der Funktionen das `import random` mit. Seitdem: Bloecke ueber Zeilenbereiche
   bestimmen, nicht ueber Regex.
3. **Geteilter Zufallsgenerator:** `bruchstein` (Bibliothek) und `quoins3` (Generator) ziehen aus DEMSELBEN `random.Random(1900)`.
   Zwei getrennte Generatoren haetten Mauerwerk und Eckquader veraendert, ohne dass eine Pruefung angeschlagen haette -
   der Bit-Vergleich hat es sofort gezeigt. `Bau(..., rng=RNG)`.
**Bilanz: 1700 von 2023 Zeilen generisch = 84 %.** Die verbleibenden 323 Zeilen sind Masse und Zusammenbau dieses Turms.
Der naechste Schritt zu ~100 % waere, auch die Komposition als Konfiguration zu schreiben (`tools/bauwerk_generator.py`-Ansatz) -
dann waere ein Bauwerk eine JSON-Datei. Das ist moeglich, aendert aber nichts an der Menge des Objektwissens, nur an seiner Form.

## AA. Masse als Daten statt als Zahlen im Code (2026-11-01, Nutzer: "mach die Komposition auch als json")
**`modelle/martinstor/masse.json` (neu): 30 Masse, jedes mit Quelle und Quelltyp** - Gesamthoehe, Sockel, Schaft mit Knick, Zinnenhoehe,
Torbogen, Uhr, Adler, Eckturm NW, Glockenstock, Dachhoehe, Knauflage, Ecktuermchen. Werte sind Zahlen oder Formeln ueber frueher definierte
Namen ("EX": "-DB / 2 - 0.8"). Lader `bauteile.lade_masse()` (generisch). Der Generator holt sie von dort, statt sie im Code zu tragen.
**Der Pruefstand prueft sie jetzt mit:** jedes Mass braucht Quelle und Quelltyp, und der Quelltyp muss in der Quellen-Matrix stehen.
Beim ersten Lauf fiel sofort mein eigener Fehler auf ("foto_intern" ist ein Massstab, kein Quelltyp); die Gegenprobe mit einem Mass ohne
Quelle wird ebenfalls gemeldet.
**Beweis: STL weiterhin BITIDENTISCH** (md5 a8dcc8cf...), alle Pruefungen gruen, 0 Widersprueche.
**Warum die KOMPOSITION Code bleibt (ehrlich):** Die restlichen 323 Zeilen sind keine Zahlen, sondern Ablauf - Schleifen ueber Seiten und
Hoehen, Bedingungen (Nord 3 Fenster, Sued 2), berechnete Lagen (`hxy(z)` fuer den verjuengten Schaft), Ausnahmen (Arkaden erst schneiden,
dann wieder freistellen). Das in JSON zu fassen hiesse, eine Programmiersprache in JSON nachzubauen - mehr Zeilen, schlechter lesbar,
und das Objektwissen waere nicht kleiner, nur anders geschrieben. **Der Gewinn lag bei den Massen, und der ist eingefahren:**
sie stehen jetzt als belegte Daten neben der Masstabelle, nicht als nackte Zahlen zwischen Geometriebefehlen.
**Stand: 1721 Zeilen generischer Code (84 %), 323 Zeilen Komposition, 30 belegte Masse, 3027 Zeilen Objektdaten.**

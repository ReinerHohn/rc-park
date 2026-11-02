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

## AB. Fassadenelemente als JSON (2026-11-01)
**`modelle/martinstor/fassade.json`:** drei Gruppen (Sued 2+1, Nord 3+1, Ost/West 3 als Annahme) mit zehn Oeffnungen - je Lage,
Hoehe, Groesse, Zweck und Beleg. Der generische Abarbeiter `Bau.fassade(gruppen, seite, hxy)` baut sie und gibt den Beleg zurueck.
Die Geometrie eines Fensters (Gewaende, Sohlbank, Sturz, Nische, Mittelpfosten) bleibt in `tools/bauteile.py` - **die Grenze
laeuft entlang "Daten gegen Ablauf", nicht quer durch ein Bauteil.**
**Beweis:** STL bitidentisch (md5 a8dcc8cf...), 25.632 Dreiecke, alle Pruefungen gruen.
**Nutzen belegt, nicht behauptet:** Ein zusaetzliches Fenster wurde allein durch Bearbeiten der JSON eingefuegt - ohne Textersetzung
im Quelltext. Der Pruefstand schlug sofort an ("Fenster obere Reihe Suedseite 3,00, Soll 2..2"), danach wurde zurueckgesetzt und das
STL war wieder bitidentisch. Genau diese Varianten liefen bisher ueber `sed` auf Python-Quelltext und sind mir dreimal fehlgeschlagen
(Muster griff nicht -> drei identische "Varianten"; eine Regex loeschte `import random`).
**Was bewusst Code bleibt:** Schleifen ueber Seiten, Bedingungen, berechnete Lagen (`hxy(z)`), CSG-Reihenfolge und Ausnahmen
(Arkaden erst schneiden, dann freistellen). Das in JSON zu fassen hiesse, eine Programmiersprache in JSON nachzubauen -
mehr Zeilen, schlechter lesbar, gleiches Objektwissen.
AB2. **Fehlteil-Finder schlaegt Fassadeneintraege vor (2026-11-01):** Treffer AUF einer Fassade (|u| <= 4,5 m, z 7-32 m) werden in einen
fertigen `fassade.json`-Eintrag uebersetzt (Seite aus dem Vorzeichen, u und z aus der 3D-Lage) und nach `audit/fassade_vorschlaege_<foto>.json`
geschrieben - **nicht automatisch eingebaut**, jeder Vorschlag wird erst am Vollbild geprueft. Erst seit die Elemente Daten sind, ist der Weg
von "hier fehlt etwas" zu "dieses Element einfuegen" ein Textbaustein statt einer Codeaenderung. Erster Lauf (Foto 030): drei Vorschlaege
auf der Ostseite (z 28,2 / 16,6 / 8,2 m) - die Ostseite ist unfotografiert, deshalb sind das Kandidaten, keine Befunde.

## AC. Die Lehre wird zum Werkzeug: `tools/messung_pruefen.py` (2026-11-01, Nutzer: "lernst du daraus? beweise es!")
**Befund:** Derselbe Fehler ist in dieser Sitzung FUENFMAL passiert - zwei Dinge verglichen, die nicht dasselbe messen:
(1) echte Querschnittsflaeche 77 m2 gegen gerasterte Laserzellen 97; (2) Sollwert aus einem Zonenmittel gegen eine Messung bei EINER
Hoehe; (3) Foto verdoppelt die freie Halbbreite, Pruefstand nahm beide Seiten; (4) Mittelwert ueber uneinige Fotos sah aus wie ein
Befund; (5) "staerkste Kante ueber der Uhr" traf in drei Fotos drei verschiedene Kanten (1,22 / 4,54 / 0,04 m).
**Die Lehre stand nach Fall 1 im Register - und kam trotzdem viermal wieder. Eine aufgeschriebene Lehre reicht nicht.**
**Jetzt eine Regel im Code:** Eine Messung desselben Merkmals in mehreren Fotos ist nur gueltig, wenn ihre Streuung zur angegebenen
Unsicherheit passt (Spanne <= 4 sigma UND Standardabweichung <= 1,5 sigma). Ist sie groesser, ist die MESSUNG kaputt, nicht das Modell -
es darf daraus kein Befund und kein Sollwert werden.
**Rueckprobe auf alle Mehrfoto-Messungen dieser Sitzung - die Regel trennt genau richtig:**
| Messung | Werte | Urteil | was ich damals tat |
|---|---|---|---|
| Silhouettenbreite 29-33,5 m | -0,12 / -0,04 / -0,36 | GUELTIG | Schaft korrigiert - war richtig |
| Flankensteigung 37-46 m | 0,486 / 0,475 / 0,481 | GUELTIG | Widerspruch geschlossen - war richtig |
| Befund 36-41 m | 1,13 / 0,35 / 0,28 | UNGUELTIG | hatte ich faelschlich BESTAETIGT |
| Uhrhoehe absolut | 24,77 / 26,79 / 27,81 | UNGUELTIG | hatte ich als Pruefzeile angelegt |
| Kante ueber der Uhr | 1,22 / 4,54 / 0,04 | UNGUELTIG | gerade eben gebaut |
Die Regel ist in `beobachtungen_sichten.py` eingebaut (Status MESSUNG UNGUELTIG) und die ungueltige Uhr-Pruefzeile wurde entfernt.
**Zur Uhr (Nutzerhinweis "zu weit oben"):** bleibt OFFEN, weil es keine gueltige Messung gibt. Naechster Schritt steht in der Tabelle:
Zinnen-Unterkante je Foto als Anker PICKEN statt "staerkste Kante" zu raten, dann den Abstand zum Zifferblatt messen.
**Der Giebel dagegen ist belegt und gebaut:** Foto 031 Vollbild zeigt einen flachen Dreiecksgiebel mit ZWEI KONKAV eingezogenen
Schenkeln (nicht die S-Kurve, die ich gebaut hatte). Gemessen: Scheitel 28,96 m, Schenkelende 27,67 m, Uhrrahmen-Oberkante 27,62 m.
**Ost/West-Fotos:** Der Laser zeigt, warum es sie kaum gibt - oestlich und westlich stehen Haeuser mit 14-23 m Hoehe direkt am Turm
(ab 3-7 m Abstand). Die unteren ~20 m dieser Seiten sind von keiner Strasse aus sichtbar; nur der obere Teil ragt heraus.
Die Commons-Kategorie (107 Dateien, 60 davon bereits im Repo) enthaelt kein Luftbild und keine reine Ost/West-Ansicht.

## AD. Sechster Fall desselben Fehlers - und die zweite Sperre (2026-11-01, Nutzer: "dokumentiere das und lerne aus deinen Fehlern")
**Was passiert ist:** Direkt nachdem ich `messung_pruefen.py` gegen Fall 1-5 gebaut hatte, habe ich `luftbild_messen.py` geschrieben,
es meldete "groesste gruene Dachflaeche: 2711,9 m2" - in einem Ausschnitt von 3600 m2, fuer ein Dach von rund 100 m2. Die Farbmaske
hatte Baeume und Schatten erfasst. **Und das Werkzeug hat den daraus berechneten Versatz ungeprueft in objekt.json geschrieben.**
**Warum die erste Sperre nicht griff:** `messung_pruefen.pruefe()` vergleicht mehrere Messungen desselben Merkmals miteinander.
Hier gab es nur EINE Messung - und die war in sich widerspruchsfrei, nur eben unmoeglich. Eine Streuungspruefung faengt das nicht.
**Zweite Sperre:** `messung_pruefen.plausibel(wert, von, bis, name)` haelt ein Ergebnis gegen einen Erwartungsbereich und BRICHT AB.
Im Luftbildwerkzeug eingebaut (Dachflaeche 40-260 m2, Versatz 2-40 m). Gegenprobe: derselbe Aufruf endet jetzt mit
"UNPLAUSIBEL: groesste gruene Flaeche (Hauptdach) = 2711,88 m2, erwartet 40..260 m2 - kein Ergebnis weitergeben". Der falsche
Wert wurde aus objekt.json zurueckgezogen.
**Die generelle Regel, die daraus folgt und ab jetzt gilt:**
> Ein Messwerkzeug gibt kein Ergebnis weiter und schreibt in keine Datei, bevor es zwei Fragen beantwortet hat:
> (1) Ist das Ergebnis ueberhaupt moeglich? (`plausibel`, Erwartungsbereich aus der Bauwerksgroesse)
> (2) Messen mehrere Quellen dasselbe? (`pruefe`, Streuung gegen Unsicherheit)
> Beides gehoert in das Werkzeug, nicht in den Kommentar - und beides wird beim Schreiben eingebaut, nicht nachtraeglich.
**Was das Luftbild trotzdem wert ist:** Das DOP20 von 2025 (20 cm/px) zeigt als EINZIGE Quelle die Dachflaechen von oben, mit den
vier Tuermchenkegeln und dem Dachreiter - also genau den Teil der Ost- und Westseite, den kein Strassenfoto erreicht. Die
Farbmaske muss nur eng genug werden (Kupfergruen gegen Laubgruen trennen, Schatten ausschliessen). Das bleibt als naechster
Schritt in der Masstabelle, mit der Pflicht, das Ergebnis vorher plausibel zu pruefen.

## AE. Mehrbild-Rekonstruktion (SfM) ueber ALLE Fotos - der groesste ungenutzte Hebel (2026-11-01)
**Nie probiert, obwohl COLMAP seit Monaten installiert ist:** 37 Turmfotos (von 46, ohne Detailaufnahmen von Tafeln und Adler),
auf 2000 px verkleinert, `pycolmap 4.3` mit CUDA. **Ergebnis: 36 von 37 Fotos registriert, 4590 Punkte, Aufbau in 10 Sekunden.**
Die Fotos stammen aus 16 Jahren, von verschiedenen Kameras, ueberwiegend von der Strassenseite - COLMAP bringt sie trotzdem zusammen.
Das ist die Basis fuer alles Weitere: **36 untereinander konsistente Kameras statt vier einzeln kalibrierter.**
**Das Problem ist die AUSRICHTUNG, nicht die Rekonstruktion.** Zwei Versuche, beide unbrauchbar:
1. Ueber meine vier bereits kalibrierten Kameras (030/031/041/000): Massstab 4.205.990, Restfehler bis 1,7 Mio m. Ursache: diese
   Kamerazentren sind selbst ungenau (RMS 56-530 px, Foto 041 sprang zwischen 60,5 m und 28,4 m Abstand) - vier schlechte
   Korrespondenzen ergeben keine gute Transformation.
2. Ueber die Geometrie der Wolke (Senkrechte aus der Kameraebene, Massstab aus der Turmhoehe): plausiblere Hoehen (-3 bis 63 m),
   aber Grundrissbreiten von 15-29 m statt 9,8 x 11,3 - die Wolke enthaelt die Nachbargebaeude. **Und der Massstab kaeme aus
   meiner eigenen Turmhoehe, waere also zirkulaer.**
**Naechster Schritt (der richtige Weg):** COLMAP georeferenzieren statt nachtraeglich transformieren - entweder mit
`model_aligner` und Bodenkontrollpunkten (LoD2-Ecken, in mehreren Fotos gepickt) oder indem man die Kamerapositionen vorgibt.
Dann haette man 36 Kameras mit amtlichem Massstab, und jede Fotomessung (Breitenprofil, Elementhoehen, Fehlteil-Finder) liefe
auf 36 statt auf 3 Fotos. Das waere der groesste Genauigkeitsgewinn, der hier noch moeglich ist.
**Unverzichtbar bleibt:** die Wolke muss vom Nachbarbestand getrennt werden (Zylinder um die Turmachse reicht nicht, die
Nachbarhaeuser stehen 3-7 m entfernt).

## AF. Zwei Recherchen - und die Loesung fuer Ost/West lag auf Commons (2026-11-01)
**Datenquellen-Recherche, wichtigster Fund:** Zwei Schraegaufnahmen, die NICHT in der Commons-Kategorie "Martinstor" liegen und
deshalb bei der ersten Sammlung durchrutschten:
- **Foto 060** `Aerial View - Freiburg im Breisgau-Innenstadt1.jpg` (4658x2844, 2012, **CC BY 3.0**): Schraegluftbild aus NW.
  Zeigt die **WESTWAND ueber die volle Hoehe**, alle vier Tuermchen von oben, das Kragdach und die Dachflaechen. Rund 15 px/m -
  fuer Schlankheit und Dachneigung besser als jedes Strassenfoto. **Erste Quelle ueberhaupt fuer die verdeckte Seite.**
- **Foto 061** `Blick vom Schlossberg auf die Freiburger Altstadt mit Martinstor.jpg` (3601x2757, 2016, **CC BY-SA 3.0**):
  Ostflanke des Oberbaus ueber den Nachbardaechern, ~18 px/m. ShareAlike - nur Masse daraus, Bild nicht in den Bausatz.
**Erster Befund daraus (noch nicht gemessen, als Beobachtung notiert):** Die Westwand zeigt nur ein bis zwei kleine Oeffnungen,
nicht die drei Fenster, die `fassade.json` dort als ANNAHME setzt.
**Lizenzkorrektur:** Mapillary ist laut Terms **CC BY-NC-SA**, nicht BY-SA wie bisher im Register vermerkt - fuer ein
Verkaufsprodukt unbrauchbar. Eintrag berichtigt. (Zudem: Street-Level erreicht die verdeckten Seiten ohnehin nicht; KartaView
hat am Martinstor nur eine Sequenz mit defektem GPS und nach oben geneigter Lenkerkamera, Panoramax null Abdeckung.)
**Negativergebnisse, die Arbeit sparen:** Stadtarchiv-Serie C1 Nr. 9-13 enthaelt KEINE 1901er-Umbauplaene (endet 1891/1901);
Bauforschung BW hat zum Objekt nur Dendro- und Restauratorenbefund, ausdruecklich "Fotos: keine"; Carl Schaefers Nachlass im
Generallandesarchiv Karlsruhe sind drei Personalakten ohne Plaene; Sketchfab hat nur einen Scan des Doppeladler-Reliefs ohne
Lizenz; Zenodo und OpenHeritage3D nichts. **Hoechster offener Erwartungswert:** Volltextsuche in *Deutsche Bauzeitung*,
*Zentralblatt der Bauverwaltung*, *Die Denkmalpflege* (Jahrgaenge 1901-1903, alle frei digitalisiert) nach einem publizierten
Aufriss des Umbaus - ein masstaeblicher Aufriss schlaegt jedes Foto.
**SfM-Recherche, Kernpunkte:** `model_aligner` (RANSAC auf bekannte Kamerazentren, min. 3 Bilder) bzw. `pose_prior_mapper`
(`--prior_position_std` auf die ehrliche Unsicherheit) sind der vorgesehene Weg, eine COLMAP-Wolke metrisch zu machen - genau
mein offener Punkt aus AE. Lizenzfalle: **3DGS, 2DGS und GOF stehen alle unter der Inria/MPII-Forschungslizenz (nicht
kommerziell)**, ebenso SuperPoint/SuperGlue, MASt3R und MeshAnything; verkaufstauglich sind COLMAP, GLOMAP, LightGlue, ALIKED,
DISK, RoMa, **gsplat (Apache, 2DGS ab 1.4 enthalten)**, SAM 2 und **MapAnything mit den Apache-Gewichten**. Letzteres nimmt
bekannte Intrinsics und Posen als Eingabe und liefert metrische Geometrie - die lizenzsaubere Alternative zu VGGT-1B.

## AG. Westwand gemessen, und die Kamera-Sperre, die dabei entstand (2026-11-01)

**Ergebnis am Modell:** Die Westwand hat **eine** Oeffnung, nicht drei. Im Vollbild 060 (7-fach-Zoom auf 4100-4270 / 1620-1860)
ist die Wand zwischen den Eckquaderketten leer bis auf ein kleines hochrechteckiges Schlitzfenster bei Pixel (4180, 1732);
zwei weitere dunkle Punkte sind Mauerankerloecher (< 0,2 m). Hoehe aus dem senkrechten Massstab 15,4 px/m unter der Oberkante
der weissen Wand (v = 1611 = Zinnenunterkante 30,5 m): **z = 22,6 m +- 1,5**. `fassade.json` hat jetzt getrennte Gruppen
`-y` (West, Beleg Foto 060) und `+y` (Ost, ANNAHME, von West uebernommen) mit je einer Oeffnung; Annahmen 6 -> 5.
Zwei Pruefzeilen angelegt; die obere (`fenster_W_oben`, Soll 0) schlug am alten Modell mit 2 fehl, danach gruen - 38/38.

**Falle dabei:** Die erste Fassung der Pruefzeile mass bei z = 26,0 m und war versehentlich **gruen**. `window()` schneidet
von `z` bis `z + h`, der Strahl lag genau auf der Sohlbank. Messhoehe auf 26,5 m korrigiert - erst dann schlug sie fehl.
Lehre: eine neue Pruefzeile, die sofort gruen ist, ist verdaechtig, nicht erfreulich.

**Die eigentliche Ausbeute: Ankerzone statt Anker-RMS.** Fuer Foto 060 habe ich erstmals eine Kamera geloest
(EXIF Nikon D7000, 92 mm -> f = 19210 px; Standort 1,17 km entfernt, 376 m ueber Grund - plausibel fuer ein Schraegluftbild;
Anker: Nadelspitze + drei Tuermchenspitzen als Goldknaeufe, dazu Linienanker auf den drei sichtbaren Eckquaderketten).
Gegenprobe: die Oberkante der Westwand muss 30,5 m sein - die Kamera rechnet **23,8 m**, 6,7 m daneben. Innerhalb von
41-60 m gibt dieselbe Kamera die Tuermchenspitzen auf 0,7 m genau wieder. Der Fehler ist also nicht Rauschen, sondern
**Extrapolation unter den tiefsten Anker**. Ein RMS-Kriterium haette das nicht gefangen und haette ausserdem jede Kamera
des Projekts gesperrt (K-030: 56,7 px = 1,97 % der Bildhoehe - und sie misst trotzdem gut).
Deshalb: `ankerzone_z` im Protokoll, `messung_pruefen.kamera_zone/kamera_tauglich`, `foto_breitenprofil` beschneidet,
`fehlteile_finden` verwirft. Sofort sichtbar geworden: **K-031 und K-041 haben ihren tiefsten Anker bei 31,5 m** -
die Pruefzeile "Silhouettenbreite Zone 23,5-28 m (Kamera 031)" steht damit auf einer Extrapolation (Beobachtung offen,
naechster Schritt: Bodenecken in 031/041 picken und neu kalibrieren).

**Offener Widerspruch oben am Dach (NICHT gemittelt, nichts geaendert).** Beide weit entfernten Fotos sind nahezu
orthografisch - erkennbar daran, dass die vier gleich hohen Tuermchenspitzen in 061 nur 4 px von 236 px streuen.
Dort liegt der Knauf der Nadel bei 49-51 % der Strecke Tuermchenspitze -> Nadelspitze (060: 0,492; 061: 0,508),
im Modell bei 0,43; der Dachansatz in 061 bei -0,148, im Modell bei -0,303. Die kalibrierten Strassenkameras 031/041
sagen das Gegenteil (Silhouette bei 47 m: Foto 0,5-1,4 m, Modell 3,0-3,1 m - das Dach endet dort FRUEHER).
Die Laserstufen 48/50 m (8 und 6 m2 gegen 4 im Modell) beweisen nichts: DOM1 ist fuer Nadeln blind, das ist die
Interpolationsfahne - fast haette ich daraus einen Beleg gemacht.
Diese Verhaeltnisse sind bisher nur **abgelesen**, nicht gemessen. Naechster Schritt ist ein generisches Werkzeug fuer
massstabsfreie Hoehenverhaeltnisse aus FERNEN Fotos (Gleichhoch-Punkte liefern die eigene Unsicherheit), abgesichert
ueber `messung_pruefen.pruefe` - erst dann darf daraus ein Sollwert werden.

## AH. SfM-Netz an den Bodenankern ausgerichtet - erst nach Trennung der Fassadenseiten (2026-11-01)
**Nutzerfrage:** Kanten perspektivisch normalisieren, Kameras mitschaetzen, viele Bilder, ein absoluter Referenzwert -> Kantenbauplan?
Antwort: ja, das ist Buendelausgleich; das Netz aus AE war die Basis, die Ausrichtung der offene Punkt. Werkzeug: `tools/sfm_ausrichten.py`
(7 Parameter Modell->SfM aus LoD2-Eckkanten-Picks durch die FESTEN COLMAP-Kameras; Linien liefern Lot/Drehung/Massstab, Punkte oder
Kamerahoehen-Annahme die Hoehenlage; danach Triangulation aller Picks mit Sigma; `--schreiben` legt `messprotokoll/SFM-AUSRICHTUNG.json`
und `sfm/sparse_modell` an).
**Befund 1 - das AE-Netz war unbrauchbar, nicht die Ausrichtung:** alle 36 Kameras lagen im SfM auf EINER Seite. Nordfotos (031/001/040)
teilen untereinander 400-900 Punkte, mit Suedfotos 5-70: COLMAP hatte beide Uhrseiten zu einer Fassade verklebt (Regel 7: symmetrisches
Objekt). Ausrichtung mit allen Picks: Kameras bei -15 m, 031-Residuen 1000 px; nur mit Suedpicks: Grundriss passt, Hoehen 1,35-fach gestreckt,
Tuermchen diagonal. Jede Zahl aus diesem Netz ist wertlos.
**Befund 2 - Seitenzuordnung per Sichtkriterium** (Kontaktbogen aller 38 Fotos): McDonald's (Torbau WESTLICH) links im Bild = Sued, rechts = Nord;
Gedenktafel ueber dem Bogen = Nord, Adlerrelief = Sued. **044 war als Sued eingetragen, ist Nord**; 022/050/012/025/056 Sued; 002/005/006/014/015/
017/018/019/027/040/045/049/051 Nord. 10 Fotos zeigen nur den symmetrischen Oberbau und sind nicht zuordenbar (003 010 011 013 016 043 052 059,
dazu 026 Muensterblick, 061 Schlossberg). Die Punktstatistik taeuschte bei Fernaufnahmen (020/021 'nord-aehnlich', sind Sued) - Fernfotos sehen
fast nur den symmetrischen Oberbau. Alles in `objekt.json` (`seite`, `seite_quelle`, `sfm`).
**Befund 3 - seitengetrennter Neuaufbau** (`modelle/martinstor/sfm/lauf2.py`: Verkleinern MIT EXIF, Brennweiten-Prior aus EXIF; FALLE: Sensorbreite
gehoert zur LANGEN Bildseite, mit der kurzen waren 000/042 um Faktor 1,4-1,6 falsch und das Suednetz explodierte):
- NORD: 16 von 17 Fotos, 2562 Punkte, Reproj 0,71 px, Brennweiten EXIF-konsistent (+-8 %). Luftbild 060 nicht registriert.
- SUED: 9 von 11, 549 Punkte, Kamera 020 mit 13 Punkten, Brennweiten driften (050: 33 Mio px); auch ohne 050/056 unbrauchbar. **Suednetz offen.**
**Befund 4 - Ausrichtung Nord:** Eckkanten in 005/006/014/040 mit `tools/foto_kante_fit.py` (Gradient + RANSAC, Kontrollbilder `lupe_<foto>/kante_*.jpg`
ANGESEHEN); 031-Linie ecke_boden_3 lag 70 px daneben auf der weissen Wand (alter Handpick), neu angepasst. Zwei Fallen beim Loesen:
(a) senkrechte Linien ohne Richtung sind unter der 180-Grad-Drehung um die Querachse unentscheidbar (Turm haengt nach unten, Kameras auf der
Gegenseite) -> Richtungsresiduum Boden->oben eingebaut; (b) Linien allein lassen die Hoehenlage frei -> ANNAHME Strassenkamera 1,7 +- 0,6 m
(15 Kameras, soft_l1; 049 als Fernaufnahme ausgenommen). Ergebnis: Massstab +-2,2 %, Drehung +-2-5 Grad, Lage +-0,5-0,65 m; Kamerahoehen
Median 1,6 m (15 von 16 auf Strassenniveau), Kameras auf der Nordseite in 20-90 m, Grundriss der Wolke y +-5,0 (LoD2 +-5,6), Nordfassade bei
x -5,3..-7,4 (LoD2 -4,9: ~1 m Tiefenversatz, offen). Residuen der Eckkanten 1-8 px, Ausreisser 031/040 links 40-51 px.
**Befund 5 - triangulierte Hoehen (Picks der Goldkugeln in 006/014/031/040, Residuen 1-8 px):** Tuermchenknaeufe NE/NW **43,50 / 43,98 +-0,13**,
Dachfirst-Kugeln **53,68 / 54,20 +-0,23**, Nadelknauf **66,9 +-1,3** (Residuen 8-31 px, Nadel duenn), Hauptdach-Traufe Nordmitte 39,8 +-1,5 (grob).
Zinnenkranz-Picks verworfen (Residuen bis 170 px, in den Fotos nicht dasselbe Merkmal getroffen). Dazu +-0,7 m Hoehenlage.
**Deutung (offen gelassen, nicht gemittelt):** DOM1-Gipfel 54,84 = Dachabschluss/Goldkugel-Ebene, nicht Nadel - SfM und Laser stimmen dort
ueberein; das Modell hat First 46,2 (aus der Laser-Hypsometrie unter der Annahme 'Nadel = 54,8'). Spitze 66,9 passt zur 65-m-Objektbeschreibung
(Bauforschung BW). Tuermchen 43,7 gegen DOM1 41,2 (getroffene Kegelflaeche): 2,5 m Differenz, plausibel, aber unbelegt. Alles als
`beobachtungen_offen`; neue Pruefung 'First / Dach-Oberkante - SfM Nordnetz' 53-55 (Quelltyp `sfm_bodenanker`, neu im Pruefstand) **schlaegt
am Modell fehl** - das ist der geforderte rote Test VOR einer Generatoraenderung. Generator NICHT geaendert.
**Naechste Schritte:** Suednetz retten (mehr Suedfotos mit Sockel, feste EXIF-Brennweiten statt Prior) und dieselben Hoehen unabhaengig
bestimmen; Bodenpunkte Nord picken (Hoehenlage ohne Kamera-Annahme); Traufe/Kranz je Foto in der Lupe als dasselbe Merkmal picken; dann First,
Traufe, Tuermchen, Spitze im Generator gemeinsam mit den Pruefzeilen umstellen. SfM-Dateien: `sfm/sparse_nord/0` (Rohnetz), `sfm/sparse_modell`
(in Metern), Datenbanken/Bilder auf `/media/oem/scan/martinstor_sfm_2026-11-01/` (Symlinks).
**AH-Fortsetzung (2026-11-01): Hoehenlage ohne Kamera-Annahme.** Der Bodenpunkt der NE-Ecke ist in ALLEN Nordfotos verdeckt (Menschen,
Fahrraeder, Lkw); die Wolke enthaelt kein Pflaster (tiefste Punkte 1,5-3 m, Sockelsteine). Deshalb: Pflasterhoehe an der Ecke aus den
Sohlen/Radaufstandspunkten der direkt an der Wand stehenden Personen, Raeder (005: y 1560) und des Lkw (014: y 2695) abgelesen, Eckkante
dorthin verlaengert, je Pick eigenes Sigma 8-20 px (`K-<foto>.json` `punkte_sigma_px`, `punkte_notiz` = ANNAHME-Text). Tiefenversatz der
Personen zur Wand ist bei 35-80 m Abstand < 3 px, also unerheblich. `sfm_ausrichten.py` ohne `--kamerahoehe`: Massstab +-2,2 %, Lage
+-0,4-0,6 m, Bodenpunkt-Residuen 19-61 px (innerhalb 2-3 Sigma). **Freie Kamerahoehen: Median 1,9 m, 15 von 16 auf Strassenniveau** -
die vorherige Annahme ist damit unabhaengig bestaetigt. Hoehen: Tuermchenknaeufe 44,34 / 44,80 (+-0,13), Dachfirst-Kugeln **54,53 / 55,05**
(+-0,24), Nadelknauf **67,7 +-1,3**, Traufe Nordmitte 40,6 +-1,5 (grob). Gegen die Annahme-Variante +0,4-0,8 m = realistische
Hoehenlage-Unsicherheit. Pruefung 'First - SfM Nordnetz' auf 53,5-56 gesetzt (Historie), bleibt am Modell (46,7) ROT. Generator unveraendert.

## AI. Suednetz retten - gescheitert, aber mit messbarem Grund; sechs Lehren (2026-11-01)
**Auftrag:** Suednetz mit mehr Sockelfotos retten, generalisiert, und daraus lernen.
**Getan:** (1) Commons neu geerntet (`tools/commons_harvest.py`, jetzt mit Volltext, Kategorie, `--skip-manifest`, 429-Wartezeit, EXIF aus der
API): 130 neue Dateien, davon 6 brauchbare Suedfotos mit Sockel (062-067, Lizenzen CC0/BY-SA; 4 mit Brennweite). Rest: Demos, Postkarten,
Nordseite, Luftbilder ohne Sockel. (2) `tools/sfm_netz.py` (generisch): Netz je Seite aus `objekt.json["sfm"][seite]`, EXIF-Prior aus
Datei ODER Manifest ODER objekt.json, Brennweitenschranken 0,4-3,5 x Diagonale, EXIF-Brennweiten als konstante Intrinsics im Buendel,
Qualitaetsschranken je Kamera (f/Prior, f/Diagonale, Punktzahl), Reparaturschleife (degenerierte Kamera austragen + nachgleichen statt
Neuaufbau - der Neuaufbau wurde beim Suednetz jede Runde schlechter). Ergebnis: 13 Kameras, 1379-1566 Punkte, Reproj 0,72 px, 9 Kameras
mit fester EXIF-Brennweite. (3) Eckkanten in 062/065/066/067 mit `foto_kante_fit.py`, Bodenpunkte hinter Fahrraedern (sigma 15-20 px).
(4) `tools/sfm_bundle_anker.py`: Anker IN den Buendelausgleich (Kameras, Punkte, Brennweiten gemeinsam gegen LoD2-Kanten/Bodenpunkte;
6335 Spurpunkte + 21 Ankerbeobachtungen, duenne Jacobi-Matrix, 35 s). (5) `tools/sfm_verzerrung_test.py`: Umeyama-Fit auf Dach-, Boden-
und alle Referenzpunkte getrennt.
**Befund (jede Stufe gleich):** Nachtraegliche Ausrichtung: Residuen 100-800 px, Massstab +-20-30 %, Fassade liegt quer zum LoD2-Grundriss.
Anker im Buendel: Ankerkosten bleiben 215 (Start 208) - die 12670 Spurresiduen halten das Netz starr in seiner falschen Form.
Reiner Verhaeltnistest ohne Ausrichtung: Dachpicks untereinander konsistent (0-4 px), aber Tuermchenabstand/Eckabstand 1,19 statt 0,82
und Tuermchenhoehe/Eckabstand 5,6 statt 3,9 -> **Dach und Sockel haben verschiedene Massstaebe (Faktor 1,4)**. Umeyama auf die vier
(aus Nord gespiegelten) Dachpunkte: Dach passt auf 0,6-1,4 m, Bodenecken landen bei z +10,5 statt -0,3, Kameras bei 7-10 m Hoehe.
**Das Suednetz ist projektiv verbogen (unten ~20 % gestaucht); keine Transformation und kein Ankerzwang repariert das.**
**Lehren (generalisiert):**
1. **Einseitig + fast eben + unbekannte Brennweiten = verbogenes Netz.** Alle Suedkameras stehen auf der Strassenachse vor EINER Fassadenebene;
   Brennweite und Tiefe sind dann fast austauschbar, COLMAP waehlt irgendeine Kombination (030: 1839 px statt ~2300). Das Nordnetz hatte
   16 Kameras von 22-177 m mit Fernaufnahmen (049) - deshalb metrisch. **Vor jeder Ausrichtung `sfm_verzerrung_test.py` laufen lassen**;
   ein gutes Reprojektionsmass (0,7 px) sagt NICHTS ueber Metrik.
2. **Feste Brennweiten allein reichen nicht:** mit 9 von 13 EXIF-festen Kameras bleibt die Stauchung. Verbleibende Hebel: Verzeichnung
   (SIMPLE_RADIAL, ein k, Bodenpunkte am aeussersten Bildrand stark gekippter Weitwinkel), Kameras ausserhalb der Achse (Ost/West,
   Schraegluftbild), oder Ring um das Bauwerk (Nord-Sued-Verbindung ueber 060/061 - beide bisher nicht registriert).
3. **Gleiche Serie heisst NICHT gleiche Brennweite.** Uebertragung 031 -> 030 (3825 px) war falsch: Ueberschlag am Bild (Spitze y 84, Boden
   y 2660, 38 m) ergibt ~2300 px; Zoomobjektiv. Der alte `f_gruppe serie2025` in K-031/foto_bundle war dieselbe Falle (4527 px fuer beide).
   Prior nur mit Plausibilitaetsrechnung am Bild; 041 <- 040 (2793 vs 2726 Einzelkalibrierung) und 022 <- 018/019 (2431 vs 2281) bestanden.
4. **Bodenpunkte aus kollinearen Kameras sind tiefen-blind:** Residuen 20-140 px bei paarweiser Triangulation, waehrend Dachpunkte 0-4 px
   haben. Linien geben Lage/Richtung, der Bodenpunkt nur die Hoehe laengs der Linie - so wird er im Ausrichter auch genutzt.
5. **Commons-Ernte:** Geosearch braucht `gsprimary=all` (sonst 0 Treffer), verkleinerte Downloads verlieren EXIF (-> `iiprop=metadata`),
   429-Ratenlimit nach ~100 Dateien (Wartezeit, leere Dateien loeschen). Auf 130 Treffer kamen 6 brauchbare Sockelfotos der Suedseite.
6. **Werkzeugkette ist jetzt generisch:** `sfm_netz.py` (bauen + pruefen + reparieren) -> `sfm_verzerrung_test.py` (metrisch?) ->
   `sfm_ausrichten.py` (7 Parameter) oder `sfm_bundle_anker.py` (Anker im Buendel) -> `sfm_html_viewer.py` (3D-Seite).
**Stand:** Nord metrisch (Register AH), Sued offen. Masstabelle: Beobachtung 'Suednetz verbogen' mit naechstem Schritt. Generator unveraendert.
**Naechster Schritt (konkret):** (a) 060 (Schraegluftbild NW) und 061 (Schlossberg, Ostflanke) mit groesserer Aufloesung/anderem Matcher in
Nord UND Sued registrieren -> ein Ring; (b) Suednetz mit Kameramodell RADIAL (k1,k2) oder OPENCV neu bauen und Verzerrungstest wiederholen;
(c) falls beides scheitert: Suedhoehen nicht aus SfM, sondern aus `foto_verhaeltnis.py` an 049/014/000 gegen die Nordhoehen pruefen.

## AJ. 060 und 061 registrieren (2026-11-01)
**Auftrag:** Schraegluftbild 060 (NW) und Schlossbergblick 061 (O) in beide Netze registrieren.
**Merkmalsweg gescheitert, messbar:** Mit Turm-Ausschnitten in voller Aufloesung (`objekt.json fotos[nr].sfm_ausschnitt`, Hauptpunkt
mitverschoben, in `sfm_netz.py`/`sfm_ausrichten.py` eingebaut) hat SIFT 9300 (060) bzw. 20900 (061) Merkmale, aber **0 geometrisch
verifizierte Matches** zu irgendeinem Strassenfoto in beiden Datenbanken (Rohmatches < 30). Blickwinkel > 45 Grad plus Massstabssprung.
Der generische Ausweg (LightGlue + ALIKED, Apache-Lizenz, Register AF) konnte nicht installiert werden - Berechtigung fuer externen Code
verweigert; braucht den Nutzer.
**Pick-Weg (`tools/sfm_registrieren.py`, neu):** Kamera aus Handpicks gegen 3D-Kontrolle des metrischen Netzes (triangulierte
Dachpunkte aus SFM-AUSRICHTUNG-nord.json + LoD2-Eckkanten), Brennweite fest aus EXIF, Hauptpunkt Bildmitte; P3P/EPnP-Start, Verfeinerung
mit Punkt- und Linienresiduen; danach Triangulation aller Picks, die in >= 2 Kameras liegen.
- **060** (f 19210 px = 92 mm auf 23,6 mm x 4928 px Vollformatbreite; f35=138 auf die BESCHNITTENE Breite gerechnet waere 7 % zu klein):
  Standort (-860, -720, +512 m), 1120 m entfernt; Residuen: drei Eckkanten-Linien 1 px, Tuermchen NW/NE 6/2 px, Nadelknauf 34 px;
  **RMS 14 px = 0,49 % der Bildhoehe** (Grenze 0,5 %). Vorher (Einzelkalibrierung K-060 gegen Modellanker) 38,6 px.
- **061** (f 4669 px): nur drei Kontrollpunkte (Knauf, Tuermchen NE/NW) -> P3P exakt, Hoehe unbestimmt (Loesungen 0 bis -24 m).
  Zusatzbedingung aus dem Bild selbst: alle vier Tuermchenspitzen liegen in DERSELBEN Bildzeile (426/426/426/425) -> Kamera auf
  Tuermchenhoehe (Zeilenversatz 0,1 px je m Hoehendifferenz bei 10 m Tiefenunterschied und 700 m) -> `--hoehe 44 8`.
  Ergebnis Standort (-243, +817, +43,5 m) = Nordost, 850 m = Schlossberg; die vertauschte Tuermchenzuordnung legt die Kamera nach
  Suedost (+180, +795) und ist damit geografisch ausgeschlossen. RMS 1 px, aber 6 Unbekannte gegen 7 Gleichungen - die Pose ist so gut
  wie Picks und Brennweite, nicht besser.
**Suednetz:** Registrierung dort sinnlos, solange es verbogen ist (Register AI) - nicht gemacht.
**Ertrag:** Nordknauf/Tuermchen NE/NW nun aus 6 Kameras (Residuen 0-4 px, Knauf 68,6 +-0,7). **Erster Punkt der Suedseite im metrischen
Nordsystem:** tuermchen_SW aus 060+061 = (7,5, -2,7, 42,6) +-2,6 m, Residuen 27/9 px - schwach (beide Kameras 850-1120 m entfernt, in 061
sind SE/SW tiefenbedingt kaum trennbar; Zuordnung T2=SW ist ANNAHME). Als Beobachtung notiert, kein Sollwert.
**Lehren:** (1) Ausschnitte heilen den Massstabssprung, nicht den Blickwinkel - fuer Luft-gegen-Strasse braucht es einen gelernten Matcher
oder Picks. (2) Zeilengleichheit gleich hoher Punkte ist eine Hoehenmessung der Kamera. (3) f35 immer auf die unbeschnittene Sensorbreite
beziehen. (4) Pick-Registrierung ist nur so gut wie die 3D-Kontrolle; sie verlaengert ein metrisches Netz, kann aber keines ersetzen.
**Naechster Schritt:** LightGlue/ALIKED (mit Nutzerfreigabe) fuer 060/061 gegen Nord UND Sued -> echter Ring; bis dahin fuer die Suedseite
Picks der Suedtuermchen/First-Kugeln in 060 (sichtbar: Tuermchen SW, Dach) und weiteren Suedfotos mit EXIF (065-067) ueber LoD2-Kanten
in das Nordsystem registrieren (`sfm_registrieren.py --netz nord --foto 065 ...`).

## AK. LightGlue/ALIKED installiert und getestet: verbindet die Luftbilder, verbiegt aber das Netz (2026-11-01)
**Freigabe des Nutzers:** "alles ist erlaubt, du musst nur dokumentieren" -> Lizenzen in `modelle/LIZENZ_WERKZEUGE.md` (LightGlue Apache-2.0
geprueft, ALIKED BSD-3 geprueft, DISK Apache, **SuperPoint restriktiv und bewusst nicht waehlbar**; Gewichte in `~/.cache/torch/hub/checkpoints/`).
Installation: `pip install git+https://github.com/cvg/LightGlue.git` in venv-seg (nicht auf PyPI). Werkzeuge: `tools/lg_match.py` (ALIKED +
LightGlue, npz), `tools/sfm_netz.py --matcher lightglue|hybrid [--lg-fotos ...]` (schreibt Merkmale/Matches roh in die COLMAP-DB, COLMAP
verifiziert; hybrid haengt ALIKED-Merkmale an die SIFT-Merkmale an und vereinigt die Matches je Paar).
**Ergebnis Nord (18 Fotos inkl. 060/061-Ausschnitte):**
| Variante | registriert | Punkte | Reproj | Tuermchen NE/NW (Residuen) | Verzerrungstest |
|---|---|---|---|---|---|
| SIFT | 16/18 (060, 061 nicht) | 2606 | 0,72 px | 44,39 / 44,72 (1-3 px) | **metrisch** (ausgelassene Bodenecke 0,55 m) |
| nur LightGlue | 18/18 | 6316 | 1,05 px | 45,96 / 46,01 (4-52 px), Gold 67,6 | - |
| hybrid SIFT+LightGlue | 18/18 | 9384 | 0,96 px | 45,97 / 46,70 (4-14 px), Gold 61 | **VERBOGEN** (Bodenecke 14,9 m daneben) |
061 landet per Merkmalen bei (-443, -142) = Nordwest - geografisch falsch (Schlossberg ist Nordost; Pick-Registrierung: (-243, +817)).
**Sued hybrid:** 17/17 registriert, 4915 Punkte, aber weiterhin VERBOGEN (Bodenecken 8-12 m daneben), 060 bei 25 km. Kein Ring.
**Deutung:** LightGlue liefert fuer ALLE 153 Paare >= 15 Matches, 142-144 davon bestehen COLMAPs Verifikation - auch die falschen
(symmetrische Fassaden, Fenster-/Quaderraster, Oberleitungen; bei fast ebenen Szenen ist eine Homographie-konsistente Fehlzuordnung
nicht von einer richtigen zu unterscheiden). Diese Matches ziehen die Buendelausgleichung krumm. **SIFT ist hier nicht schlechter, sondern
vorsichtiger.** Fuer 060/061 bleibt die Pick-Registrierung (Register AJ) das belastbare Verfahren.
**Panne, dokumentiert:** Die Sicherung des SIFT-Nordnetzes (`sparse_nord_sift_backup`) wurde erst NACH dem ersten LightGlue-Lauf angelegt
und enthielt deshalb das LightGlue-Netz; `--schreiben` hatte zudem SFM-AUSRICHTUNG-nord.json ueberschrieben. Wiederhergestellt durch
Neuaufbau (SIFT ist reproduzierbar: 2606 Punkte, Tuermchen 44,39/44,72 vs vorher 44,34/44,80). **Regel ab jetzt: vor jedem Lauf mit
neuem Matcher `--name <variante>` und eigenes `sparse_<seite>_<variante>` - nie das Referenznetz ueberschreiben.** Hybrid-Netze liegen
als `sparse_nord_hybrid`, `sparse_sued_hybrid`, `netz_*_hybrid.json`, `SFM-AUSRICHTUNG-nord_lightglue.json`.
**Stand Nord (SIFT, neu, Register-Zahlen):** Tuermchen 44,39 / 44,72 +-0,14, Dachfirst-Kugeln 55,14 / 55,61 +-0,18, Nadelknauf 69,7 +-1,4
(Residuen 4-30 px, Nadel duenn), Massstab +-2,2 %, Kamerahoehen Median 3,0 m; 060 per Picks RMS 8 px (0,26 %).
**Lehren:** (1) Gelernter Matcher != besseres Netz; jede Matcher-Aenderung durch `sfm_verzerrung_test.py` abnehmen. (2) Luftbild-Registrierung
ueber Picks + bekannte 3D-Punkte ist bei symmetrischen Bauwerken sicherer als Merkmale. (3) Fuer den Ring Nord-Sued braucht es Fotos der
Ost-/Westseite vom Boden oder ein Verfahren, das falsche symmetrische Matches ausschliesst (z. B. Matches nur innerhalb per Seite
maskierter Bildbereiche). (4) Backups VOR dem Lauf, mit Variantennamen.

## AL. Dichte Fotowolke Nord fuer den Sichtvergleich (2026-11-01)
`tools/sfm_dicht.py nord`: COLMAP undistort -> PatchMatch (CUDA, 1600 px, geometrisch konsistent) -> Fusion -> Transformation ins Modellsystem
(aus SFM-AUSRICHTUNG-nord.json) -> Zylinder r 25 m: **101 098 farbige Punkte, z 0,9..66,8 m** (`sfm/dicht_nord_modell.npy` + `_farben.npy`,
Fallen: `undistort_images` nimmt `UndistortCameraOptions`, `stereo_fusion(output, workspace, output_type="ply")`).
Viewer `tools/sfm_html_viewer.py --dicht ...` bettet sie binaer (base64 float32/uint8, max 400 000 Punkte) ein; Netzpunkte und
dichte Wolke getrennt schaltbar, STL deckend, Punktgroesse regelbar. Sichtblatt `sfm/dicht_nord_sicht.jpg` (Nordansicht + Draufsicht mit
LoD2-Rechteck und den gemessenen Hoehen 44,4 / 55,4 / 69,7). Zweck: Sichtvergleich Foto gegen Modell; KEIN Massnachweis
(Pruefungen bleiben die der Masstabelle). Lizenz: COLMAP BSD; Fotos Messvorlage.

## AM. Dach, Traufe, Tuermchen, Spitze aus Rohraster + SfM umgestellt - und die Lehre ueber Fast-Fehler (2026-11-01)
**Ausloeser:** Nutzer sah im Viewer (dichte Fotowolke gegen deckendes STL) den grossen Unterschied und forderte die Korrektur.
**Beinahe-Fehler, dokumentiert:** Ich wollte zuerst aus dem SfM-Nordnetz allein umstellen. Dann fiel der Widerspruch zur Laserflaeche
(DOM1: 43 Zellen > 40 m; mit Glockenstock bis 43,5 m waeren es > 100) auf, und mein `sfm_verzerrung_test.py` fuer Nord war ZIRKULAER
(eigene Dachpunkte als Referenz). Entscheidend war dann das **rohe DOM1-Raster** (19x19 Zellen um den Peak gedruckt, `masspruefung_daten`-
Fenster): drei Zellen 53-55 m (eine Dachflaeche, keine Nadel), Schnitt vom Peak nach aussen 55 / 50 / 44-46 / 39-42 / 32-35 m bei
0/1/2/3/4 m. Dazu LoD2 Traufe 37,27 und SfM-Goldkugeln 55,1-55,6 (Residuen 2-4 px). Danach ein zweiter Beinahe-Fehler: Traufe 40 m und
Glockenstock 6 x 6,6 m aus den 3-m-Zellen abgeleitet - das waren aber Zellmaxima der Dachflanke; Laserflaeche sprang auf 74 Zellen.
Korrektur: Traufe 37,0 (LoD2), Glockenstock wie zuvor (DOM1 sieht ihn unter dem Dach nicht).
**Neue Masse (masse.json mit Historie):** H_TOTAL 60 -> 70 (SfM Nadelende 69,7 +-1,4; Dokument 60/65 bleibt als offene Beobachtung),
Traufe GZ1 35,5 -> 37,0, DACHHOEHE 10,7 -> 18,4 (First 46,2 -> 55,4), Helm dreistufig (Fuss GX+0,6 x GY+0,6 = 5,6 x 6,3; 41 m: 4,0 x 4,6;
45 m: 3,0 x 3,6; oben 1,6 x 2,0), Goldkugeln auf Kreuzarmen bei +-1,5 / +-1,9 (SfM), Tuermchenspitze 41,35 -> 44,5 (Helmkegel 8,1 m,
Radius 1,1), KNAUF_ANTEIL 0,22 -> 0,25 (Knauf 59 m). Schallarkaden unveraendert.
**Pruefstand gruen (40 Pruefungen), geaenderte Sollwerte mit Historie:** Tuermchen-Spitze 40,7-41,8 -> 43,8-45,2 (sfm), Dachansatz
34,5-36,5 -> 36-38,5 (lod2 + Rohraster; Zwischenwert 39-42,5 verworfen), First 46,6-48,7 -> 54,3-56,5 (sfm + Rohraster), Gesamthoehe
59,5-66 -> 68-72 (sfm; Dokument widerspricht), Dachflanke 0,4-0,56 -> 0,15-0,35 (Rohraster/Wolke; K-030 war unbrauchbar),
Laserflaeche > 40 m Obergrenze 48 -> 52 (Modellraster zaehlt die Tuermchenhelme, DOM1 nicht). Messfenster: Nadel 50/52 -> 62/66 m,
first 44-60, dachansatz 34-48 (Schwelle 6,2 ab), knauf 56-66, helm 37 -> 37,5. Sichtblatt `audit/seiten.jpg` angesehen.
**Noch offen / nicht gemittelt:** Gesamthoehe (SfM 69,7 vs Dokument 60/65), 061-Verhaeltnis 'dachansatz' 42,1 (vermutlich Oberkante
Schallarkaden), Dachabschluss-Form oben (DOM1 1-m-Zellen 46-53 schliessen eine breite Plattform aus; Kugeln auf Armen ist ANNAHME),
Suedseite weiterhin ohne eigenes Mass.
**Lehren:**
1. **Ein Netz ist erst metrisch, wenn eine FREMDE Quelle oben und unten passt.** Selbstreferenz (eigene Triangulation als Referenz) ist kein
   Test. `sfm_verzerrung_test.py` braucht Referenzen aus Laser/LoD2 (Kranz 31,5, Traufe 37,3, DOM1-Max 54,8), nie aus demselben Netz.
2. **Rohdaten vor Kennzahlen.** Die Hypsometrie-Summe (14 %) hatte ein 9 m zu tiefes Dach als "scharfes Minimum" verkauft; 19 Zellen auf
   dem Bildschirm haben es in einer Minute entschieden. Fuer jede Hoehenfrage zuerst `DOM1-Schnitt durch den Peak` ansehen.
3. **Zellmaxima sind keine Kanten.** Eine 1-m-Zelle 3 m vom Peak mit 40-42 m sagt: irgendwo in der Zelle ist die Flaeche so hoch - nicht,
   dass dort eine Wand steht. Daraus Traufe 40 zu machen war falsch; die Flaechenkurve (Zellen > Schwelle) hat es sofort widerlegt.
4. **Ein roter Test allein reicht nicht fuer eine Generatoraenderung**, wenn er aus EINER Quelle stammt, die fuer das Merkmal selbst
   fragwuerdig ist. Zwei unabhaengige Quellen (hier Rohraster + SfM + LoD2) oder gar nicht.
5. **Nutzersicht war richtig:** "man sieht durch die Farbwolke den grossen Unterschied" - die Wolke war vertikal nicht gestreckt (Kranz
   32,3 gegen Laser 31-32), der Fehler lag im Modell. Der Sichtvergleich Fotowolke/deckendes STL gehoert nach jedem Bau in den Viewer.

## AN. Generisch statt Handmessung: Fotowolke gegen Modell, Eckturm NW, Torbau aus LoD2 (2026-11-01)
**Nutzer:** "lerne generalisiert daraus, ich will nicht von Hand herumfummeln"; Sichtbefunde: Eckturm ('Tuermchen') kleiner als im
Modell; Nebengebaeude mit McDonald's-Schriftzug fehlt.
**Werkzeug `tools/wolke_vs_modell.py <objekt> <seite> [--eintragen]`:** Tiefenkarten der Fassade aus dichter Wolke (vorderster Punkt je
Zelle) und Modell (Strahlen von aussen, trimesh), Differenzkarte, Silhouette (nur Wolke / nur Modell mit Wolkenumgebung), zusammenhaengende
Flaechen >= 1 m2 als Befunde, Bild `audit/wolke_vs_modell_<seite>.png`, JSON, automatische Beobachtungen (auto_id, idempotent).
Versatz quer zur Fassade wird am Schaft (12-26 m) bestimmt und abgezogen, zusaetzlich je 4-m-Band gemessen: **Nord 0,85-1,4 m je nach
Hoehe (Spreizung > 0,3) -> 'TIEFE UNSICHER'**: einseitige Netze sind in der Tiefe weich (Register AI/AM); Tiefenbefunde sind nur Hinweise,
Silhouetten- und Hoehenbefunde gueltig. Erster Lauf Nord: 24 Befunde, darunter (gueltig, Silhouette/Lage) **fehlt_im_modell 32,6 m2 bei
y -9..-5,5, z 6-21 = Torbau**, **modell_weiter_vorn -1,44 m bei y -6,8..-4,8, z 3,5-14 = Eckturm zu gross/zu weit vorn**; (unsicher, Tiefe)
Dach/Glockenstock +1,1 m, unterer Schaft -0,6/+1,1.
**Eckturm NW:** Kreisfit an die Wolkenfront (z 6-12, 6077 Punkte): Mitte x -6,00 / y -3,70, r 1,26; Tiefenversatz des Bands ~1,3 m ->
Vorsprung vor der LoD2-Nordwand ~1,05 m. Modell hatte Mitte (-5,7, -5,45), r 1,15 = Vorsprung 1,95, an der Ecke. Zwei neue Pruefungen
(neue Messtypen `min_im_bereich`, `mitte_im_bereich` im Pruefstand): 'Vorsprung vor der Nordwand' 0,7-1,4 und 'Mitte y' -4,1..-3,3 -
beide am alten Modell ROT (nan / -4,85), dann masse.json EX -DB/2+0,2, EY -3,7, ER 1,2; Messfenster der alten Eckturm-Pruefungen auf die
neue Lage verschoben (Sollwerte unveraendert). Hoehe: Wolke-Vorsprung endet bei 13-14 m = Modell 14,0 (keine Aenderung); der Nutzer-Eindruck
'hoeher' kam von der NW-Eckquaderkette der Wolke; Korrektur des Nutzers ('kleiner') durch Messung bestaetigt.
**Torbau (1901, McDonald's):** LoD2 `DEBW_0010007Tv3w` (Kachel 414_5316, 3 Teile, First 24,4 m, Grundriss 23 x 17 m) mit
`tools/lod2_gebaeude.py --center 414110,5316244` extrahiert, ueber anker3d (mitte_utm, xhat/yhat, Gelaende 277,93) ins Modellsystem
gebracht: `modelle/martinstor/torbau/torbau_lod2_modell.stl` (m) und `torbau_lod2_1-87.stl` (mm), `torbau_modell.json` (Quelle, Lizenz
DL-DE-BY-2.0). Lage x -6,0..11,5, y -25,6..-5,5, z bis 24,1 - schliesst westlich an den Turm an (Foto 060: Westwand teils verdeckt).
Massenmodell; Fassade/Arkaden/Schriftzug fehlen (Fotos 002/003/089 der Ernte zeigen die Front). Im Viewer als zweites STL (`--stl2`).
**Lehren:** (1) Der Sichtvergleich ist jetzt ein Werkzeug mit Zahlen und Bild - jede Nutzerbeobachtung wird als Flaeche mit Masse gefunden,
bevor jemand misst. (2) Tiefe einer einseitigen Wolke ist nur bis +-0,5 m und hoehenabhaengig verlaesslich; Lage in der Fassadenebene und
Hoehen sind es. Das Werkzeug sagt das selbst (Spreizung). (3) Messfenster von Pruefungen muessen mit dem Bauteil wandern - sonst messen
sie Nachbarn (Eckturm: Wandquader, 10,6 m 'Spitze'). (4) Nebengebaeude kommen zuerst als LoD2-Massenmodell (amtlich, 10 Minuten), Details
spaeter aus Fotos.

## AO. Wandebenen-Anker, Tiefendrift, Tuermchen an die Wand, Glockenstock 6 m (2026-11-01)
**Nutzer:** "Wo soll die Verbesserung sein? Die echte Punktwolke weicht immer noch ab" + "lerne generell".
**Diagnose:** Der sichtbare Unterschied war zu ~1 m ein Versatz der ganzen Wolke quer zur Fassade (Ausrichtungstiefe), nicht das Modell.
Die Eckkanten-Linien legen Lot, Drehung, Massstab und Seitenlage fest, aber nicht die Tiefe.
**Werkzeug:** `sfm_ausrichten.py --wand nord`: zweiter Loesungsdurchlauf mit der LoD2-Wandebene (x der Bodenecken) als Anker fuer die
Netzpunkte des Schafts (|y| < 2,5, z 12-26, vordere Schicht). Ergebnis Nord: Schaftpunkte von -0,63 m auf -0,03 m (Streuung 0,27),
Massstab +-1,9 %, Drehung +-0,9 Grad, Lage +-0,2-0,35 m. 060/061 neu per Picks (RMS 10 / 1 px), dichte Wolke neu transformiert.
**Restdrift (einseitiges Netz):** `wolke_vs_modell.py` misst die Wandlage je 4-m-Band: +0,23 (6-10) ... +0,75 (30-34) -> linear +17,7 mm
je m Hoehe (1,0 Grad), Rest 0,16 m; `--entzerren` zieht die Gerade ab und schreibt `sfm/dicht_<seite>_entzerrt.npy` (NUR Sichtvergleich).
Oberhalb der Anker wird die Drift steiler (Glockenstock/Dach weiterhin +1,0 m): **DOM1 ist dort der Schiedsrichter** - Peakzelle mittig im
Grundriss, N-S- und E-W-Schnitt symmetrisch (3 m von der Achse 39-42 m auf beiden Achsen) -> Dach steht zentriert, Glockenstock/Helmfuss
~6-7 m tief UND breit. Deshalb GX/GY 5,0 x 5,7 -> 6,0 x 6,2 (D-3,0 / W-3,8; Fotoschaetzung 'deutlich abgesetzt' war zu stark);
Laserflaeche > 40 m im Modell 52 (DOM1 43 + Tuermchen), Dachansatz-Messung 38,0.
**Ecktuermchen:** Wolke (entzerrt) Helmachse ~0,4 m innerhalb der Nordwand, Erkerkoerper kragt 0,5 m aus; Modell hatte 1,2 m Ruecksprung.
Neue Pruefung 'Achse Abstand zur Nordwand 39-42 m' 0-0,8 (vorher nan/1,22 rot) -> c = (hx-0,1, hy-0,55) = (4,4, 4,45): jetzt 0,49 gruen.
Gesamtbreite y bei 29,5-33,5 m aus der Wolke 11,06/11,19/11,76 (Mittel 11,34) ersetzt die Kamera-Silhouettenpruefungen K-031/K-041
(unbrauchbare Einzelkameras, Register AI); Modell 11,20 gruen. Erker/Helm-Abseitsschwelle 2,5 -> 3,1/3,2 (breiterer Glockenstock).
**Pruefstand neu:** Messtypen `schnitt_mitte`, `schnitt_ausdehnung`, `min_im_bereich`, `mitte_im_bereich`, `kreis_durchmesser_im_bereich`
(Kreisfit an grobe Zylinder-Eckpunkte war instabil -> Schnittkontur); Dachflanke jetzt aus der Modellbreite auf der Achse (|x|<2) statt
Kamera-Silhouette (die enthielt die Tuermchenhelme: 0,52).
**wolke_vs_modell.py:** 'nur Modell' zaehlt nur am RAND der Wolkensilhouette; Loecher mitten in der Wolke (1282 Zellen: dunkle Fassade,
Tafel) sind Abdeckungsluecken. Stand Nord nach allem: mittlere Tiefendifferenz +0,13 m, Streuung 0,72; verbleibend: Torbau fehlt (36 m2,
jetzt als LoD2-Massenmodell daneben), Glockenstock/Dach +1,0 m (Drift, DOM1 widerspricht - offen gelassen), Torbogen/Relief-Zone (Strahlen
durch die Durchfahrt, Messartefakt).
**Generelle Lehren (Memory):**
1. Vor jedem Sichtvergleich die Wolke an eine amtliche FLAECHE (LoD2-Wand) haengen, nicht nur an Linien - Linien lassen die Tiefe frei.
2. Einseitige Netze driften in der Tiefe mit der Hoehe (hier 1 Grad): je Band messen, linear entzerren fuer die Sicht, Masse nur aus
   Hoehen/Fassadenlage; fuer Tiefen/Grundrisse oben entscheidet DOM1 (Schnitt durch den Peak, Symmetrie).
3. Pruefungen, die auf unbrauchbaren Kameras stehen (K-030/031/041), ersetzen statt lockern - durch Wolkenbreiten (y) oder DOM1.
4. Messtypen am Netz: Eckpunkte reichen nicht (Kegel/Zylinder grob), Schnittkonturen sind die robuste Basis.
5. Fenster von Messungen und Abseits-Schwellen haengen an Bauteilmassen (Glockenstockbreite!) - bei jeder Massaenderung mitpruefen.

## AP. wolke_vs_modell mit Nebengebaeuden; Torbau-Massenmodell gegen die Wolke (2026-11-01)
`tools/wolke_vs_modell.py --nebengebaeude`: STLs aus `objekt.json["nebengebaeude"]` werden mit dem Turm vereinigt, das Raster deckt sie
mit ab. Lauf Nord: der fruehere Befund 'fehlt im Modell 36 m2 bei y -9..-5,5' ist weg (Torbau vorhanden). Pruefung des LoD2-Torbaus gegen
die Wolke: Nordfront LoD2 x -6,0, Wolke -5,9..-6,6 (y -12..-8); Dachlinie LoD2 13,9/15,6/17,3/19,0/18,0 m bei y -12..-8, Wolke
12,5/17,2/19,7/20,5/19,8 -> Massenmodell stimmt auf 1-2 m (Giebel zum Turm hin steigend). Der Befund '+3,95 m bei y -10..-11' stammt von
einem anderen Gebaeude weiter noerdlich (Punkte bei x -13..-17), nicht vom Torbau. Offen am Torbau: Giebelform, Arkaden/Durchgang,
Fachwerk, Schriftzug - aus Fotos 002/003/089 (Ernte) und der Wolke (Torbau-Nordfront z 8-20 m vorhanden).
Commit cdaa625 enthaelt Werkzeuge, Netze, Masse, Register AH-AO; grosse/reproduzierbare Zwischenstaende per .gitignore draussen
(commons_neu 285 MB, dicht_nord-Werkstatt, Hybrid-/Versuchsnetze, LightGlue-npz, DB-Symlinks).

## AQ. Torbau-Nordfront parametrisch (erste Fassung) und Viewer: Wolke vor dem Modell (2026-11-01)
**Nutzer:** "mehr Farben sehen" - die Fotowolke lag auf der Oberflaeche des deckenden STL und wurde verdeckt. Viewer: Wolke wird jetzt
standardmaessig ohne Tiefentest vor dem Modell gezeichnet, STL halbdurchsichtig (beides schaltbar), mehrere Nebengebaeude-STLs (`--stl2`
mehrfach). Farbdatei-Suche auch fuer die entzerrte Wolke.
**Torbau-Front aus der Wolke gemessen** (Frontkarte y -14..-5, z 0-24; Zeichenkarte Mauer/Oeffnung/leer je 0,25 m): Obergeschosse
y -10,6..-7,2 vorn bei x -6,3 (z 10-19), Erdgeschoss-Arkade zurueckgesetzt auf -5,3 (Oeffnungsmuster z 5-9,5 durchgehend, Durchgang bis
-4,6), Tiefensprung bei 9,8 m; Giebelspitze 20,7 m bei y -8,3, Oberkante faellt beidseits auf ~18,9; oestlich von y -7,0 liegt die Front
bei -4,7..-5,0 (Turmwand/Verbindungsbau). Fenster in der Wolke nur schwach (Reihen ~11,6 und ~14,6). Fotos 003 (CC BY-SA 3.0, Nordfront
von NW: Staffelgiebel, Arkaden, Fachwerk), 089 (CC BY-SA 3.0, McDonald's-Bogen), 002 (CC BY-SA 4.0, Schriftzug) als Formquelle.
**Generator `modelle/martinstor_torbau_gen.py`** (Masse in `torbau/torbau_masse.json`, je Mass Quelle/ANNAHME): Arkadengeschoss mit
Rundbogen-Durchgang, vorkragende Obergeschosse, 2 Fensterreihen x 2, Staffelgiebel (3 Stufen ANNAHME) bis 20,7, Satteldach giebelstaendig,
Giebelfenster; wasserdicht (Genus 0), 334 Dreiecke; `torbau/torbau_front_modell.stl` (m) und `stl/martinstor_torbau_front_1-87.stl`;
`torbau_elemente.json` = Belege. In objekt.json als `nebengebaeude.torbau_front` neben dem LoD2-Massenmodell (Rest des Baukoerpers).
`wolke_vs_modell --nebengebaeude` danach im Torbau-Bereich: nur noch Reste (Giebelkopf 18,5-20,5 m: Modell 0,76 m zu weit vorn; zwei
Flecken mit D +7-8 m = Haus weiter noerdlich, das durch Fensterausschnitte 'durchscheint').
**Offen (ehrlich):** Fensterzahl, Staffelstufen, Bogenbreite und Blocktiefe sind Annahmen; kein Pruefstand fuer den Torbau (nur Turm);
der Frontblock (3,4 m breit) wirkt schmal gegen Foto 003 - die Abgrenzung zum Verbindungsbau (y -7,2..-5,7, Front -4,9) ist unsicher.
Naechster Schritt: Foto 003 kalibrieren (LoD2-Ecken des Torbaus als Anker) und Fensterachsen/Bogenbreite messen; Torbau-Masstabelle anlegen.

## AR. Dach und Tuermchen als Loft aus Profilen; DOM1 ist auf dem steilen Helm blind; Glockenstock 34,1-40,5 m (2026-11-01)
**Nutzer:** "Die Daechlein der vier Tuermchen passen noch nicht, die sind zu klein. Und das Modell des grossen Dachs, wenn du seitlich
schaust, passt auch noch nicht." - "aber generisch!"
**Werkzeuge (neu, generisch):**
- `tools/wolke_profile.py <objekt> <seite> --zentral-z 40.5 56 --generator --pruefungen`: Profile je 0,5 m aus der entzerrten Wolke.
  Zentralkoerper: Tiefe = 2 x Wolkenfront (Median der Tiefe im Achsstreifen |quer| < 1,5), Breite quer = p2-p98 im Frontfenster
  (+-0,8 m um die Front, Tuermchenzone Achse +- d/2 + 0,3 ausgeblendet) minus 0,2. Abseits (Ecktuermchen): robuster Kreisfit je
  Quadrant (Dachflaechen-Punkte ausgeblendet, 20 % groesste Residuen verworfen), nur Schichten mit beiden Quadranten; daraus ein
  Tuermchen-MODELL: Koerper = Median d der grossen Schichten (2,87 m, 31-38,75), Kegel = Gerade durch die Spitze (d = 0,419 x (44,5 - z)
  aus 9 Schichten), Knick 37,64 m. Schreibt `profile_nord.json`, `profile_generator.json` (dach_profil [z, tief, quer] monoton,
  tuerm_profil, tuerm_kegel, tuerm_achse 3,98/4,44) und idempotent die Pruefzeilen 'Profil Dach: Breite y bei 45,2/49,2/53,2' und
  'Profil Ecktuermchen: Durchmesser bei 34,25/37,75/40,25/42,5' (Soll aus dem Modell +-0,4; Messung `schnitt_ausdehnung` im Fenster
  seitlich der Dachbreite, weil Glockenstock/Kragdach im Schnitt mit dem Erker verschmelzen). Eigene veraltete Zeilen entfernt es selbst.
- `tools/foto_silhouette_profil.py <objekt> 061 --achse x --pick-oben 2387 303 --pruefungen 47 50 53`: Silhouettenbreite je Zeile aus
  dem fernen Seitenfoto 061 (Schlossberg, Ost, Orthografie-Abweichung 0,4 %). Massstab 11,26 px/m aus zwei Bezugszeilen (Tuermchenknaeufe
  44,5 / Helmscheitel 55,4). Himmel = HSV nahe dem Himmel-Median (+-14), Closing gegen Glanzlichter, Monotonie nach oben. Kontrollbild
  `audit/silhouette_061.png`, Protokoll `messprotokoll/M-061-S1.json`, Pruefzeilen 'Profil Dach (Foto 061): Tiefe x bei 47/50/53'.
**Befund Dach (drei Quellen):** N-S-Tiefe des Helms 46,75 m: Wolke 4,58, Foto 061 4,35, DOM1-Schnitt 1,76; 50,25 m: 3,06 / 3,02 / 0,52.
Wolke und Foto stimmen auf 0,3 m, der DOM1 liegt um den Faktor 2 daneben - **Quellen-Blindheit: 1-m-Zellmaxima erfassen 78-86 Grad
steile Helmflaechen nur teilweise** (wenige Rueckkehrer), Zellzahl und Schnitt sind dort KEINE Obergrenze. Damit war die Pruefung
'Laserflaeche ueber 40 m 38..52' (43 Zellen) falsch begruendet (zurueckgezogen, `pruefungen_zurueckgezogen`), ebenso 'Dachflanke y 38-45'
(ersetzt durch 'Helmflanke N-S 42-50: 0,17..0,30 je Seite', Wolke 0,21, Foto 0,26). Die Regel aus AO "oberhalb der Anker entscheidet
DOM1" gilt nur fuer Peakhoehe und flache Flaechen - Memory korrigiert.
**Befund Aufbau (Wolke Front-Tiefenprofil 0,25 m, Foto 061 Achsspalte):** Kranz 30-31,9 (-4,8..-5,15, Tropfkante des Kragdachs 31,9),
Kragdach-Schraege 32,1-34,1 (-5,0 -> -3,5), Glockenstock-Front -3,5 (34-38) / -3,3 (38-39,6), Helm-Tropfkante 40,4-40,7 (-4,0), Helm
ab 41 linear bis -0,85 bei 54. Foto 061: Gesims 37,5-37,7, Schalloeffnungen 38,4-40,9, Traufkante 42,0 (Foto-Massstab ~1-1,5 m hoeher als
die Wolke: offen `foto061_z_offset`). => GZ0 = ZZ+3,6 (34,1), GZ1 = ZZ+10 (40,5), GX 6,8, GY 6,5 (Frontfenster y -3,4..+3,0),
HELM_UEBER 1,1, DACHHOEHE 14,9, KRAG_TRAUFE ZZ+1,4 / KRAG_UEBER 1,3, ARKADE_UNTER_TRAUFE 3,0, ERKER_OBEN 38,3; Dachansatz-Pruefung
36..38,5 (LoD2 37,27 = Galeriegesims, LoD2 blind fuer Aufbauten) -> 40..41,5 mit Historie. Die 'zweimal korrigierte Traufe 40 -> 37' (AM)
beruhte auf der DOM1-Zellzahl und war ein Fehlschluss.
**Generator:** PROFIL_DATEI=1 -> Helm = Loft aus `dach_profil` (Fuss RZ0 40,5 mit BX/BY, Kopf 55,4 mit DACH_OBEN 1,4 x 3,6),
Ecktuermchen = Loft aus Achtecken (Schluesselweite = Fit-Durchmesser, gleiche Schichten zusammengefasst) von Erkerfuss bis Spitze-0,5;
Oeffnungen (Bruestungsschlitze, Erkerfenster, Schaftfenster) nur auf Flaechen, die vom Turm wegzeigen (sonst Hohlraeume: 14 -> 1 Koerper);
Kragdach als zwei Frusta (ueber den Zinnen bis Tropfkante, dann Schraege bis GZ0), Kern hinter den Zinnen 0,45 zurueck (Scharten >= 0,4).
Pruefstand: alle Pruefungen bestanden (inkl. Kegel 2 m unter Spitze 0,77 in 0,4..1,2, 4 m 1,68, Foto-061-Tiefen 4,47/3,17/1,95).
**Offen:** `foto061_z_offset` (Bezugszeile pruefen), `foto061_kuppelturm` (runder Kuppelturm links in 061, Suedseite?), Schaft-Verjuengung
(Nutzer: Wand in der Wolke senkrecht), Breite quer des Helms 41-44 m nur als Untergrenze aus dem Frontfenster (Tuermchenzone), Suedseite
ohne eigene Messung, DACH_OBEN_Y 3,6 aus den Kugeln (Plattform koennte schmaler sein).

## AS. Foto-061-Massstab, Kuppelturm, Uhrhoehe, Konsolen - alles als Werkzeug (2026-11-01)
**Nutzer:** "klaer den Foto-061-Hoehenversatz und den Kuppelturm, generisch" / "Die Uhr ist im Modell eine halbe Hoehe hoeher als in der
Punktwolke ... seitliche Tuerme: kleine Erker und Boeckchen fehlen" / "aber alles generalisieren!!!" / "kannst du nicht mehr GPU nehmen?"
**061-Versatz (aufgeloest):** kein Versatz, sondern meine von Hand gewaehlte Bezugszeile: Pick 303 = Goldknauf der Nadel (59,05 m), nicht
Plattform. `foto_silhouette_profil.py` nimmt jetzt ALLE K-Picks mit Anker (anker3d.json, neue SfM-Oberbauanker: Tuermchen 44,5 +-0,4,
Goldkugeln/Plattform 55,4, Knauf 59,05, Nadel 70) und rechnet Massstab + Nullzeile per Ausgleich: 8,90 px/m, Residuen -0,46..+0,26 m,
Orthografie 0,2 %. Unterhalb der Tuermchenknaeufe (+1 m) keine Silhouette (Knaeufe in der Strecke). `foto_kalibrieren.py`: `brennweite_frei`
fuer beschnittene Bilder (061 ist 3601x2757, kein A650-Format), unbekannte Picks werden uebersprungen statt abzubrechen; alle anker3d-Eintraege
tragen jetzt `quelltyp`.
**Folge fuer das Dach:** Silhouette N-S 5,84 / 4,27 / 2,81 m bei 46,75 / 49,75 / 52,75 - die Wolkenfront (4,58 / 3,30 / 2,06) liegt
konstant ~1 m darunter: einseitige Wolke, Tiefe oberhalb der LoD2-Anker (37,27) extrapoliert. `wolke_profile.py --tief-quelle silhouette:061`:
Tiefe aus der Silhouette, darunter Wolkenfront + Driftrampe (0,057 m je m ueber 37,27, aus dem Vergleich gefittet), Traufmass (Tropfkante,
korrigiert 8,15 x 6,03) ins Generatorprofil (`dach_traufe`), Monotonie von oben. Pruefungen 'Profil Dach (Foto 061)' 47/50/53 gruen.
**Kuppelturm (aufgeloest, negativ):** `tools/foto_lod2_zuordnen.py` projiziert LoD2 (4 Kacheln, 10 450 Gebaeude, 5 km) in die 061-Kamera:
an der Bildstelle kein Gebaeude, Martinstor-Block endet 20 px rechts, kein Gebaeude >= 30 m First in +-400 px. Suedfotos 041/043: kein
Kuppelturm am Martinstor. => Hintergrundbauwerk, kein Modellelement. Kacheln LoD2_32_411_5314/5316 und 413_5314 nachgeladen (LGL, DL-DE-BY-2.0).
**Uhr (aufgeloest):** `tools/wolke_farbmerkmal.py`: goldene Stundenmarken/Zeiger in der Wolke (515 Punkte) -> Mitte 25,69 m (Modell 26,9);
neue Modellmessung `relief_mitte` im Pruefstand (Strahlraster, Wand aus den Randspalten der Zeile, Reliefzellen vor/zurueck, Schwerpunkt +
Kreisfit). Test zuerst rot (26,5/27,9), UZ 26,9 -> 25,7, Suednischen-Fenster wandert mit; gruen (25,70). Lehre: Zeilenmedian als Wand kippt,
sobald ein Giebel die Zeile dominiert - Randspalten nehmen.
**Konsolen ('Boeckchen'):** Wolke y-Gesamtbreite je 0,25 m: 10,3 m bis 27,6, Anstieg auf 11,0 bei 28,9. Pruefung 'Gesamtbreite y bei 28,5 m'
(rot 10,13) -> KONSOLE_Z0/Z1 27,6/28,9 als Masse, Generator-Konsole daran -> gruen. Erker-Details (Fachwerk, Oeffnungen, Daechlein, Foto 043)
bleiben offen.
**Tempo:** `bauen_abnehmen.sh` fuehrt die Fotodiagnosen (15 Kameras) parallel aus (xargs -P 4), Masstabelle ueber `tools/masstabelle_io.py`
(flock, atomar); `embreex` in venv-seg (trimesh-Strahlen). Gesamtlauf 28 s statt ~2 min. GPU bringt hier nichts: manifold3d (CSG) und die
Strahlmessungen sind CPU-Bibliotheken; GPU bleibt fuer COLMAP/Dichte Wolke/Render.
**Hygiene offen:** auto-Beobachtungen (fehlteile/breitenprofil) sammeln sich ueber alte Modellstaende an und werden nicht entwertet.

## AT. Der Helm war 1 m zu tief, weil die Nadel 5 m zu hoch war - Massstab mit waagerechter Bekanntgroesse (2026-11-01)
**Nutzer:** "das grosse Dach des Hauptturms passt noch nicht und die kleinen Tuermchen sind nicht ganz richtig auf das Punktmodell gesetzt"
(Seitenansicht im Viewer); "logst du deine Aktivitaeten und lernst aus den Fehlern?"
**Messbar gemacht:** orthografische Seitenansicht Modell+Wolke (`audit/seitenansicht_west_wolke.png`) und Tabelle Nordfront Wolke vs Modell je m:
Modell stand 41-53 m um 0,45-0,56 m vor der Wolke (Folge von AS: Helmtiefe aus der Silhouette mit 8,9 px/m).
**Ursache:** Der Fotomassstab hing an zwei Hoehen (Tuermchen 44,5, SfM-Nadelende 70). Mit der WAAGERECHTEN Bekanntgroesse (N-S-Abstand der
Tuermchenknaeufe 7,95 m: Wolken-Kreisfit +-3,98, DOM1-Maxima 3,3-4,2) ist der Massstab ueberbestimmt: 10,8 px/m, und das Nadelende faellt
mit -4,7 m heraus -> 65,3 m (Foto 049 First->Spitze 8,6 m = 64,0; Dokumente 65; SfM 69,7 = duennes Bauteil, schlechte Schnittgeometrie).
`foto_silhouette_profil.py` loest jetzt eine schwache Perspektive (px/m, Azimut, u0, v0) ueber alle verankerten Picks (du/dv-Residuen,
3-sigma-Ausschluss, `--bezug` + PROBE-Zeilen fuer ausgelassene Picks). Mit korrigierten Ankern: 10,71 px/m, Residuen <= 0,9 m,
Silhouette 4,34 / 2,89 / 1,49 m bei 47,25 / 50,25 / 53,25 = Wolkenfront (4,35 / 3,06 / 1,84). Driftrampe jetzt -0,02 m je m (~0).
**Folgen:** H_TOTAL 70 -> 65,3 (quelltyp foto_kalibriert; Pruefung 'Gesamthoehe' 64,3..66,3), anker3d nadel_spitze 65,3 / knauf_nadel 57,9
(Historie), 'Spitzenlaenge ueber First' 12..16,5 (zirkulaer, alter First 46) -> 8,5..10,5, Nadeldicken-Messhoehen wandern mit der Spitze.
Helm wieder auf der Wolkenfront (+-0,2 m, 40-53 m). Tuermchen: Durchmesser jetzt aus der Aussenkante der Wolke in der Tuermchenzone
(p97 Tiefe) statt Teilbogen-Kreisfits: Koerper 2,85-3,1 bis ~37, Kegel 0,44 d/m zur Spitze - bestaetigt den Kegel aus AR; Restabweichung
der Kegelkante 0,3-0,5 m (Band der einseitigen Wolke), Achse 3,995/4,44.
**Lehre (Memory):** Nie nur senkrechte Bezugshoehen fuer einen Fotomassstab - eine waagerechte Bekanntgroesse aus unabhaengiger Quelle
macht den Massstab pruefbar; ein SfM-Punkt an einem duennen, hohen Bauteil (Nadel) ist kein Anker. Sichtfunde des Nutzers zuerst als
orthografische Projektion Modell+Wolke rendern (eine Minute), nicht am Viewer-Foto raten.

## AU. Erker-Details der Ecktuermchen als Baender aus der farbigen Wolke (2026-11-01)
**Nutzer:** "mach die Erker-Details an den Tuermchen, generisch".
**Werkzeug `tools/wolke_tuerm_baender.py`:** je 0,25 m in der Tuermchenzone Aussenradius (p97 der Tiefe = Silhouette) und Farbklassen
(stein/weiss/dunkel/kupfer, HSV). Klassenregeln: kupfer > 15 % -> Kegel (oberhalb der Dachtraufe alles Kegel); Radius springt gegen das
Band DARUNTER um > 0,12 -> Kragplatte (erste = gesims, letzte vor dem Kupfer = traufe); dunkel > 45 % ohne Stein -> offen (Arkaden);
dunkel < 20 %, wenig Stein -> fachwerk; sonst stein. Baender = gleiche Klasse in Folge (Mindesthoehe 0,5 m). Ergebnis Nord:
konsolring 27,5-28,25 r 1,17 | Schaft 28,25-31,75 r 1,23 | Kragplatte 31,75-32,5 r 1,50 | Fachwerk 32,5-33,5 r 1,55 | offen 33,5-35,0
r 1,55 | Traufe 35,0-35,5 r 1,85 | Kupferkegel ab 35,5 (r 1,85) gerade zur Spitze 44,5, Steigung 0,21 r/m (32 Schichten).
Das deckt sich mit Foto 043 (Bruestung mit X-Fachwerk, gepaarte Bogenoeffnungen, kleines Dach, schlanker Kegel).
**Generator `bau_tuerm_baender`:** baut jedes Tuermchen aus den Baendern: Konsole bis zum Schaftfuss, Schaft (Quader TWs, Eckquader, Fenster
aussen), Kragplatten als Achtecke (Schluesselweite = gemessener Radius), Fachwerkband mit Leisten und X-Schlitzen, Arkadenband mit 2 Rundbogen-
oeffnungen je Aussenflaeche (ANNAHME Foto 043), Traufplatte mit 8 Konsolen ('Boeckchen', ANNAHME Foto 043), Kupferkegel Traufe -> Spitze, Knauf.
Oeffnungen nur auf Flaechen, die vom Turm wegzeigen. Alte Hand-Elemente (Erkerkoerper bis ERKER_OBEN, Fensterzonen, Helmansatz) nur noch Fallback.
**Pruefstand:** neue Messung `tuerm_radius` (Strahlen von aussen auf die Tuermchenachse, p90 der Treffer ueber +-0,6 m quer = Aussenkante
trotz Oeffnungen); je Band eine automatische Zeile 'Ecktuermchen Band <klasse>: Aussenradius' (Soll r +-0,15), zuerst rot (Kragplatte 1,34
statt 1,50; Traufe 1,55 statt 1,85), nach dem Umbau gruen. Konsolring/Kegel/Fachwerk/offen gruen. Zwei Gesamtbreiten-Zeilen und 'Kegel 4 m unter
Spitze' mit Historie neu belegt (y-p99 einzelner Schichten streut +-0,5: seitliche Raender im streifenden Winkel unterbesetzt - Nordkante p97
ist der bessere Beleg; Kegel beginnt an der Traufplatte).
**Lehren:** (1) Schwerpunkt-/Fensterschnitte scheitern, sobald Kragdach/Glockenstock im Schnitt mit dem Erker verschmelzen - Strahl auf die
Achse misst wie die Wolke. (2) Werkzeuge, die Pruefzeilen ersetzen, duerfen Messungen nur loeschen, wenn keine Zeile sie mehr nutzt
(gleicher `wert`-Schluessel bei umbenannter Zeile loeschte die neue Messung). (3) Farbklassen aus der Wolke tragen Semantik (Oeffnung, Holz,
Kupfer), die der reinen Geometrie fehlt - generisch nutzbar fuer jedes Bauteil mit eigener Farbe.
**Offen:** Zahl der Bogenoeffnungen je Flaeche und Form der Boeckchen sind Annahmen aus Foto 043 (Sued; kein kalibriertes Nahfoto Nord);
Suedtuermchen per Symmetrie; auto-Beobachtungs-Hygiene.

## AV. Kein Spezialwerkzeug fuer Tuermchen: `wolke_baender.py` fuer jeden Koerper (2026-11-01)
**Nutzer:** "dass wir jetzt ein Spezialtool fuer Tuermchen brauchen? ... nur machen, wenn es anders genauso gut ohne Qualitaetsverlust geht."
**Befund:** Das Werkzeug aus AU war nur im Namen speziell. Umgebaut zu `tools/wolke_baender.py --koerper <name>`: ein Koerper = Achse (tief, quer)
+ Zonenbreite + Hoehenbereich + Spitzenmass, als DATEN in `objekt.json["koerper"]` (tuermchen: Kreisfit-Achse aus profile_generator.json;
zentral: Bauwerksachse 0/0). Einzige Regelaenderung: statt 'oberhalb der ersten Kupferschicht ist alles Kegel' (Tuermchen-Abkuerzung) jetzt
generisch 'Kupferdach-Kontinuitaet': Schichten ueber einem Kupferband gehoeren zum Dach, wenn ihr Radius der Dachgeraden folgt (+-0,35 m)
und kein Stein sichtbar ist. Kupferschwelle 10 % und >= Steinanteil. Klasse 'fachwerk' heisst jetzt 'hell' (Putz/Holz), der Generator deutet
sie am Tuermchen als Fachwerkbruestung (ANNAHME Foto 043).
**Regression:** Tuermchen-Baender und Kegel (r0 1,85 / z0 35,5 / 0,2093 r/m) identisch mit AU - kein Qualitaetsverlust. Pruefstand gruen.
**Probe am Hauptturm (ohne jede Eingabe):** Kragdach-Traufe 31,5-32,0 (r 5,17), Kupferschraege 32-34,5, helle Glockenstock-Wand ab 34,5,
Galeriegesims 36,25-37,75 (r 3,70; LoD2 Wandoberkante 37,27), Schalloeffnungen 38,25-39,25 (dunkel 88 %), Helmtraufe 40,25-40,5 (r 4,07),
Kupferhelm ab 40,5 - stimmt mit GZ0 34,1 / GZ1 40,5 / HELM_UEBER aus AR/AS ueberein. Abweichung notiert: Schalloeffnungen im Modell
37,9-39,5 vs Band 38,25-39,25 (offene Beobachtung, Masse ARKADE_UNTER_TRAUFE spaeter aus dem Band).
**Lehre:** Vor jedem neuen Werkzeug fragen, welche Eingaben wirklich objektspezifisch sind - meist nur Achse, Zone, Hoehenbereich. Die gehoeren
als Daten in objekt.json, nicht in den Werkzeugnamen.

## AW. Generalisierung mit Beweis: tools/regression.py (2026-11-01)
**Nutzer:** "aber jetzt haben wir viele Spezialwerkzeuge? generalisiere alles, was ohne Qualitaetsverlust moeglich ist und beweise, dass wir
nichts verlieren."
**Beweisrahmen:** `tools/regression.py <objekt> --schnappschuss | --pruefen`. Kette und Vergleichsdateien stehen als DATEN in
`objekt.json["regression"]` (8 deterministische Schritte ab der vorhandenen Wolke: Silhouette 061, Dach-/Tuermchenprofil, Uhr-Farbmerkmal,
Baender tuermchen + zentral, Generator, Pruefstand, Wolke-gegen-Modell; 9 s). Verglichen werden 10 Ergebnisdateien: Profile, Baender,
Silhouettenprotokoll, Masstabelle (Pruefungen name/wert/soll + Messungen), Pruefbericht (85 Werte, 59 ok-Flags), Elemente-Belege, STL
(Dreieckszahl exakt, Volumen/BBox relativ 1e-6), Wolke-gegen-Modell (Versatz/Drift). Ein Traceback in der Kette = Fehlschlag (haette sonst
einen Absturz als 'OK' durchgehen lassen - genau das passierte beim ersten Lauf von Gruppe 1 und wurde so gefangen).
Schnappschuss: `modelle/martinstor/regression/basis/` (vor der Generalisierung, nach AV). Vorab gezeigt: Kette zweimal = identisch.
**Generalisiert (jede Gruppe mit gruener Regression 10/10):**
1. Seitenzuordnung (nord/sued/ost/west -> Tiefen-/Querachse) stand 4x kopiert in den Wolken-Werkzeugen -> einmal `bauteile.seite_achsen`/`SEITEN`.
2. Alle Werkzeuge, die die Masstabelle schreiben, gehen ueber `masstabelle_io` (Dateisperre, atomar) - vorher nur zwei.
3. `foto_silhouette_profil.py` kennt keine Namen mehr: 'gleich hohe Picks' = groesste Gruppe gleicher Ankerhoehe, 'seitliche Picks' =
   Anker > 1,5 m abseits der Achse (statt startswith('tuermchen')). `wolke_baender.py` nimmt Koerper NUR aus objekt.json (keine Defaults
   im Code). `wolke_profile.py`: Spitzenmass aus objekt.json['koerper'], Achsstreifen/Frontfenster als Parameter statt Literale.
4. Der Baender-Bauer (Kragplatten, Bruestung mit X, Arkaden, Traufe mit Konsolen, Achteckkegel, Knauf) liegt als `bauteile.baender_rundkoerper`
   objektunabhaengig vor; der Martinstor-Generator baut nur noch den Schaft selbst. STL dreiecksgleich.
5. `pruefstand.rand_radius` = generischer Name fuer `tuerm_radius` (Alias, Tabellen unveraendert).
**Bewusst NICHT geaendert (Begruendung):** `wolke_profile.py` behaelt Kreisfit-Achse und Tuermchen-Profil (Achse wird von wolke_baender
gebraucht, vier 'Profil Ecktuermchen'-Pruefungen haengen daran; Entfernen waere Verlust an Pruefabdeckung). Der Generator bleibt
bauwerksspezifisch (das ist sein Zweck); Pfade zu profile_*.json haengen am Objektordner.
**Bestand:** 275 Dateien in tools/, davon nutzt der aktive Arbeitsablauf (Kette, Regression, bauen_abnehmen, CLAUDE.md, Importe) 24
(`regression/aktive_werkzeuge.json`); dazu SfM-/Dicht-Werkzeuge der Netzphase (sfm_dicht, lg_match, sfm_bundle_anker, foto_pick_pruefen,
foto_bundle, foto_verhaeltnis, lod2_gebaeude). Die uebrigen ~240 sind Versuchsstaende frueherer Register-Abschnitte (masspruefung_*, hypso_*,
foto_* -Experimente); fuer sie gibt es keinen Beweisrahmen, sie werden nicht angefasst. Archivieren (tools/archiv/) waere eine eigene
Entscheidung des Nutzers.
**Regel ab jetzt (CLAUDE.md):** nach jeder Werkzeug- oder Bibliotheksaenderung `tools/regression.py <objekt> --pruefen`; Schnappschuss nur
bewusst erneuern (`--schnappschuss`), wenn eine Aenderung das Ergebnis AENDERN soll - und dann mit Register-Eintrag, warum.

## AX. Hoecker, Boegen, Backsteine - vom Werkzeug gefunden, nicht von Hand (2026-11-01)
**Nutzer:** "Die rot angedeuteten Backsteine sind zu grob, die Boegen in den 4 Tuermchen zu klein und zu viele, das grosse Hauptdach hat 'nen
Hoecker und ist nicht durchgaengig" - "aber stop, du musst es generell finden" - "kannst du GPU noch mehr nutzen?"
**Generische Messungen (neu):**
- Wolke (`wolke_baender.py`): je Band 'offen' die Dunkellaeufe entlang der sichtbaren Flaeche (8-cm-Zellen) -> Oeffnungen je Flaeche, Breiten,
  Hoehe; je Steinzone die Farbperiode des Steinanteils senkrecht (Schichthoehe) und quer (Blocklaenge), 5-cm-Zellen, Autokorrelation,
  Periode = kleinster Peak >= 50 % des staerksten (Grundperiode). Koerper-Flags in objekt.json steuern, was Pruefzeile wird und was
  Beobachtung bleibt (zentral: offen -> Beobachtungen, Radius aus; Perioden mit Kanten je Hoehenbereich).
- Modell (`pruefstand.py`): `flaeche_oeffnungen` (Laeufe tiefer Treffer entlang einer Flaeche), `relief_periode` (Anteil hervortretender
  Zellen je 5 cm im Kantenband, gleiche Peak-Regel wie die Wolke), `front_linearitaet` (max. Abweichung der Front von der Geraden),
  `z_nischen_ende` (Zinnen-Oberkante = Ende der Scharten); `max_z_im_bereich` tastet jetzt die OBERFLAECHE ab (Kegel haben nur Ringe als
  Ecken - 'Eckturm-Kegelspitze' hatte bisher einen Eckquader bei 15,16 gemessen, der Kegel liegt bei 13,07).
- `wolke_profile.py --eben`: Helmflaechen als Ebenen (Gerade durch tief/quer zwischen Traufe+1 und Kopf-1), nur wenn die Daten selbst gerade
  sind (RMS 0,095/0,128 < 0,15) -> kein Hoecker an der Nahtstelle Wolkenfront/Silhouette mehr; Pruefzeilen 'Helm geradlinig'.
- `foto_silhouette_profil.py`: meldet seine Aufloesungsgrenze (Schliessungskern 7 px = 0,65 m) und markiert Breiten < 1,5 x als
  Obergrenze; Pruefzeilen dafuer werden ausgelassen. Folge: der 'Laternenschaft 0,93 m' aus 061 war ein Artefakt -> LATERNE_D 0,26 (Foto 049),
  DACH_OBEN_X zurueck auf 1,4 (Historie).
**Befunde -> Daten -> Modell (Test zuerst rot):** Tuermchen-Boegen: 2 je Flaeche, 0,48/0,72 m breit, 33,6-34,9 m hoch (Modell hatte 0,32 m);
Bauteil `baender_rundkoerper` nimmt Zahl/Breite/Hoehe aus dem Band. Eckquader: Schichthoehe 0,25 m (18-24 m, Staerke 0,67) / 0,5 m
(22-34 m) / Glockenstock 0,35 / Tuermchenschaft 0,5; Blocklaenge 0,4 m (quer 0,30-0,45); keine Lang/Kurz-Alternanz messbar ->
QUADER_KURZ_FAKTOR 1,0. Modell hatte 0,95 m Schichten und 0,95-1,75 m x 1,7 lange Bloecke mit bis 0,48 m Relief. `quoins3` nimmt jetzt
Masse statt Zufallsbereiche. Dachreiter: DOM1-Trommel (3,1 m) entfernt. Regression: 9 Dateien beabsichtigt geaendert, Schnappschuss erneuert.
**Nebenbefunde des Werkzeugs (Beobachtungen):** Hauptturm Band offen 22,75-24,0 m: 3 Oeffnungen (1,6/0,4/1,44) = obere Fensterreihe,
aber 0,7 m hoeher als die Modellfenster (22,1); Band 20,75-21,5 eine Oeffnung 0,88; Schalloeffnungen 38,25-39,25 (2 je Flaeche, 1,2/1,5 m).
**GPU:** Pruefkette 9-28 s, CSG + Strahlen = CPU-Bibliotheken; GPU bleibt fuer COLMAP/Dichtwolke/Render.

## AY. Nullstart: das Martinstor mit der Pipeline von den Eingaben neu gerechnet - Befund in drei Stufen (2026-11-01)
**Nutzer:** "koenntest du das Martinstor mit der aktuellen Pipeline von 0 aus erstellen? Beweise es!" / "verteil die Starts auf alle Kerne" /
"das Bilderholen generalisieren in der Pipeline, nur Bilder mit Mehrwert, aehnliche wenn sie etwas bringen".
**Werkzeug `tools/nullstart.py`:** frischer Objektordner `modelle/martinstor_null` (Symlink auf die Datenplatte: Root hatte 0,8 GB frei) mit
NUR Eingaben (objekt.json angepasst, masse.json, anker3d.json, masstabelle.json = Sollwerte, fassade.json, K-/V-Picks ohne abgeleitete
Kameras, torbau/ als Nebengebaeude-Eingabe); Fotos/DOM1/LoD2 geteilt gelesen. Kette: Netz Nord 7 s, Netz Sued 8 s, Ausrichtung Nord 8 s /
Sued 51 s, Verzerrungstest, Registrierung 060 (ok) / 061 (nur 2 belastbare Kontrollpunkte - Anker heute auf sfm_bodenanker umgestellt,
Filter 'nicht selbst abgeleitet' greift), Generator ohne Profile, Dichtwolke 353 s (GPU), Entzerrung, 15 Kamerakalibrierungen, Auswertungs-
kette (regression.py --schnappschuss), Vergleich. Gesamt 8 Minuten.
**Ergebnis (Stufe B, Fotos -> Modell):** STL-Volumen 6,27 vs 6,28 dm3 (0,2 %), Silhouette 061 identisch, Dachprofil/Traufe bis 0,7 m
abweichend (quer an der Traufe 5,99 -> 5,25: andere Wolkenrealisierung), Tuermchenbaender gleiche Klassenfolge, Grenzen um eine Schicht
(0,25 m) verschoben; Pruefstand im frischen Objekt 61/70 gruen (Referenz 67/67). Rot: Tuermchen-Spitze 45,25 (Kegel aus anderem Band-z0),
Kegeldurchmesser, zwei Silhouettenbreiten aus neu kalibrierten Kameras, Tuermchen-Fensterprofile (Messfenster an der Referenzachse).
**Befund daraus (generisch behoben):** Bandsegmentierung war empfindlich gegen Schichtjitter (8 -> 12 Baender, Mini-Plattenbaender):
Baender gleicher Klasse werden nach dem Umbenennen zusammengefasst; Schlitzhoehe im Bauteil nie <= 0. Referenz: Hauptturm 30 -> 25 Baender
(Schnappschuss erneuert), Tuermchen unveraendert. Nullstart danach: 1 Koerper, Volumen 0,2 %.
**Stufe C (nicht automatisch):** 24 Masse in masse.json stammen aus Werkzeugausgaben, die von Hand uebertragen wurden (Historie 'grund'):
DACHHOEHE, GZ0/GZ1, GX/GY, H_TOTAL, KONSOLE_Z0/Z1, KRAG_*, OR, QUADER_*, UZ, ERKER_OBEN, EX/EY, DACH_MITTE*. Sie bleiben im Nullstart Eingabe.
Naechster Schritt fuer einen echten Nullstart: `masse_aus_profilen.py` - die Werkzeuge schreiben diese Werte selbst (mit Quelle/Historie).
**Antwort:** Ja fuer Fotos -> Wolke -> Profile -> Baender -> Modell -> Pruefung (8 min, 0,2 % Volumen, gleiche Form), NEIN fuer die 24
Masse der Stufe C und fuer die Picks (Mensch). Der Lauf ist wiederholbar: `tools/nullstart.py modelle/martinstor/objekt.json --ziel martinstor_null`.
**Tempo:** `sfm_ausrichten.py` Mehrfachstart auf allen Kernen (fork-Pool, 72 Starts / 28 Kerne), bewiesen identisch am Referenz-Nordnetz
(Kosten 46,39, Massstab 0,18713, gleiche Sigmas); 22 -> 15 s unter Last.
**Bilder (`tools/bilder_holen.py`, Konfiguration objekt.json['bildquellen']):** Commons-Kategorien + Suchen + Geosearch mit Stichwort,
nur Vorschaubilder fuer die Auswahl: Guete (Breite, Schaerfe), pHash-Duplikate (nur das beste), ORB/Homographie-Aehnlichkeit (aehnlich mit
Parallaxe behalten, gedeckelt je Blickgruppe), neue Blickwinkel immer; Lizenz/Autor je Bild; Mapillary nur mit Token (fehlt), Videos nur
mit Flag (Urheberrecht). Ergebnis des ersten Laufs: siehe daten/martinstor/fotos_eingang/bericht.json.

## AZ. Stufe C: masse_aus_profilen.py - die Werkzeuge schreiben die Masse selbst (2026-11-01)
**Nutzer:** "mach Stufe C: Werkzeug, das die Masse selbst schreibt."
**Werkzeug `tools/masse_aus_profilen.py --schreiben`:** Regeln als Daten in objekt.json['masse_regeln'] (27 Regeln, 12 Regeltypen: band_z,
band_r/band_r2, baender_r2_median, band_periode, perioden_gruppen, periode_fenster, periode_quer, anker_z, differenz, merkmal, zylinder_an_wand,
konstante, bleibt). Quellen: profile_baender_<koerper>.json (jetzt mit Breite quer je Band, Fremdkoerper ausgeblendet), merkmal_<farbe>_<seite>.json
(neu von wolke_farbmerkmal geschrieben), anker3d.json, Formeln ueber andere Masse. Jedes Mass bekommt Quelle mit Zahlenherkunft, Historie nur bei
Aenderung; Bericht masse_regeln_bericht.json. Schritt steht in beiden Ketten vor dem Generator.
**Ergebnis am Referenzobjekt:** 20 Masse abgeleitet, davon unveraendert reproduziert: DACHHOEHE 14,9, H_TOTAL 65,3, UZ 25,7, GZ1 40,5, QUADER_TUERMCHEN
0,5, QUADER_SCHAFT_UNTEN 0,25, QUADER_ZONE_Z 23, QUADER_GLOCKENSTOCK 0,35, KONSOLE_Z0 27,5(27,6). Datengetrieben veraendert: GZ0 34,1 -> 34,5
(Ende des Kupferbands), GX 6,8 -> 7,1 (2 x Median r von 5 Glockenstock-Baendern), HELM_UEBER 1,1 -> 1,04, KRAG_TRAUFE 31,9 -> 31,8,
KRAG_UEBER 1,3 -> 1,34, QUADER_SCHAFT_OBEN 0,5 -> 0,4, QUADER_LAENGE 0,4 -> 0,35, OR 1,45 -> 1,55, ERKER_OBEN/KONSOLE_Z1 (nur Fallback).
Pruefstand gruen; Regression: beabsichtigte Aenderungen, Schnappschuss erneuert.
**Bleiben Hand (7, mit Grund in der Regel):** GY (Tuermchen verdecken die Glockenstock-Kanten, Breite quer nicht trennbar), EX/EY/ER
(Widerspruch: Wolke Durchmesser 2,84 / Vorsprung 1,31 vs Foto 001 2,29 +-0,21 - Regel 5, nicht gemittelt, Beobachtung angelegt; Kreisfit am
einseitigen Bogen war instabil 1,03..1,47, 'Front + Sehne in halber Tiefe' ist die robuste Form), DACH_MITTE_Z/DACH_MITTE2_Z (Fallback),
PROFIL_DATEI (Schalter).
**Nebenbefunde:** Sued-Zifferblattnische: auf Uhrmitte unterbrechen die Zeiger die Nische -> Messhoehe = gemessene Uhrmitte - 0,8 (Formel).
relief_periode tastet 2,5 cm (feiner als die Fuge 5 cm), sonst Aliasing der Schichtperiode (0,5 statt 0,25).

## BA. Nullstart 2-4: was eine andere Wolkenrealisierung kippt - und die Reparaturen (2026-11-01)
**Laeufe:** Nullstart 2 fusionierte alte Tiefenkarten mit neuen Posen (476 statt 99 000 Punkte) -> nullstart loescht Abgeleitetes. Nullstart 3:
COLMAP SIFT-GPU 'illegal memory access', weil die Bilderernte (LightGlue, 6 GB) gleichzeitig lief -> sfm_netz CPU-Rueckfall (>= 80 % Bilder mit
Merkmalen, sonst CPU), nullstart wartet auf freie GPU. Nullstart 4 (7,1 min; Netze 7/8 s, Dichtwolke 320 s): Wolke und Ausrichtung reproduzierbar
(Wandversatz 0,26 m in beiden Laeufen, Drift gleich), aber der Generator lieferte ein LEERES Modell:
1. Kupferanteil des Kragdachs 4-17 % statt 12-54 % (andere Fusion, andere Farbabtastung) -> Klasse kippte, 'erstes Kupferband' = Helm,
   GZ0 54,75, KRAG_TRAUFE 40,5, GX leer. Reparatur: Dachband auch GEOMETRISCH (Radius faellt >= 0,25 m je m ueber +-2 Schichten, kein Stein),
   Farbe nur Stuetze; Plausibilitaetsfenster je Massregel (objekt.json 'bereich'), ausserhalb bleibt der alte Wert ('unplausibel').
2. Tuermchenachse aus Kreisfits lag bei 3,45/4,79 statt 3,99/4,44: 'd >= 0,8 dmax' griff Kegelschichten (Ausreisser). Reparatur: Achse aus dem
   laengsten Lauf konsistenter Schichten (+-15 %) -> Referenz 4,00/4,42 (2 cm Aenderung).
3. Kurze Koerperbaender zerfallen an der Dunkelschwelle (offen 0,75 + stein 0,75): nur Paare kurzer Baender zusammenlegen, Klasse aus den
   gemeinsamen Farbanteilen (ein langer Nachbar darf ein kurzes Band nicht schlucken - erster Versuch liess die Arkaden verschwinden).
Referenz danach: Pruefstand 67/67, Baender wie vorher (8 Tuermchen, Arkaden 33,5-35,0 mit 2 Oeffnungen), Schnappschuss erneuert.
**Lehre:** Farbklassen aus Fotowolken sind zwischen Laeufen nicht stabil; Geometrie (Radiusverlauf) ist es. Jede Massableitung braucht ein
Plausibilitaetsfenster, sonst kann eine kippende Klasse das Modell ausloeschen. Der Nullstart ist der Test, der das findet.

## BB. Nullstart 5/6 (34+48 Fotos nach der Ernte) und die Untersuchung "Automatik zuverlaessig erhoehen" (2026-11-01)
**Nullstart 5** (erster Lauf mit den geernteten Fotos, Nord 34 / Sued 48): Netze und Ausrichtung ok (Tuermchen-Residuen 1-3 px), aber
PatchMatch brach ab ("depth_min > 0 ... no sparse model"): fuenf Ultraweitwinkel-Fotos (076, 110, 118, 128, 130; Pentax 15-27 mm,
EXIF-Prior) standen als **Spiegelloesung** im Netz - 100 % ihrer 3D-Punkte HINTER der Kamera (alle anderen Bilder <= 0,1 %). Kein
bisheriges Kriterium (f/EXIF, f/Diagonale, Punktzahl) sah das. Reparatur, generisch:
- `sfm_netz.bewerten`: Cheiralitaet - > 20 % Punkte hinter der Kamera = degeneriert, `--reparieren` nimmt sie heraus (Nullstart 6: Nord 5, Sued 2
  (119, 121) entfernt, Reproj 0,77 px, degeneriert danach: keine). Referenznetz: 0 Treffer, Kriterium trennt sauber (100 % gegen 0,1 %).
- `sfm_dicht.netz_fuer_dicht`: Bilder ohne positiven Tiefenbereich kommen nie in den dichten Arbeitsordner (Schutz in der Tiefe).
**Nullstart 6** (`--ab netz_nord`): PatchMatch brach erneut ab, diesmal "image 1600 vs depth_map 1598 px": der dichte Arbeitsordner aus Lauf 5
lag noch da, entzerrte Bilder alter Kameras passten nicht zu den neuen (um 1-2 px andere Entzerrung). Reparatur: `sfm_dicht` leert den
Arbeitsordner vor dem Entzerren (nur `--nur-fusion` behaelt ihn). Beide Abbrueche legten je einen 1,3-GB-Core-Dump auf die ROOT-Platte
(/var/lib/systemd/coredump, Root wieder 98 %): `nullstart.lauf` und `sfm_dicht` setzen RLIMIT_CORE = 0. Regression nach den Werkzeugaenderungen: identisch.
**Lehre (Serie):** Nullstart 1-6 fanden sechs verschiedene Fragilitaeten (alte Tiefenkarten, GPU-Kollision, kippende Farbklasse, Achsen-Ausreisser,
Spiegelkameras, alter Arbeitsordner). Jede Reparatur war generisch und ohne Verlust (Regression). Der Nullstart bleibt der Dauertest; Ziel:
drei saubere Laeufe in Folge, erst dann gilt die Kette als zuverlaessig.

### Inventar: was am Martinstor heute noch Handarbeit ist (gezaehlt, nicht geschaetzt)
- Picks: 15 K-Protokolle, 130 Punkt-/Linienpicks; davon tragen nur 5 Nordfotos (005, 006, 014, 031, 040) die Ankertriangulation
  (7 Punkte: gold_*, tuermchen_*, spitze_dokument, traufe_N_mitte) - die uebrigen Netzfotos brauchen KEINE Picks, SfM registriert sie selbst.
- Generator-Belege: 38 Elemente - 17 Foto/Mass, 15 Werkzeug/Wolke, 1 LoD2/DOM1, 7 ANNAHME (Schlitzfenster, 2 x Zinnenkranz "5 Zinnen",
  2 x Schallarkaden, Arkadenband-Runden, Traufkonsolen).
- Masse: 59 - 20 schreibt `masse_aus_profilen` selbst; 10 `foto_verhaeltnis` (Handmessungen), 12 `sfm_bodenanker` ausserhalb der Regeln, 7 Laser, 2 LoD2.
- Fotos: 118 in objekt.json - Seite bei 61 automatisch (aehnlichstes Basisfoto), 33 Sichtpruefung, 31 unbekannt.
- Beobachtungen offen: 207, davon 186 automatisch (fehlteil 81, breite 61, wolke_vs_modell 41) - nie geraeumt, 1 Nutzer-Beobachtung.
- Pruefzeilen: 67, 30 von Werkzeugen erzeugt.

### Gemessen: taugt "Picks aus dem Netz projizieren" als Ersatz fuer Handpicks? NEIN, nur als Vorschlag
Leave-one-out am Referenz-Nordnetz (Punkt aus den uebrigen Fotos triangulieren, ins ausgelassene projizieren, Abstand zum Handpick):
n = 26, Median 5,8 px, p90 80 px, max 188 px (Vollbild). Mit 3 Strahlen und sigma <= 0,2 m (gold_NE): 15-16 px; spitze_dokument 15-66 px
(Spitze je Foto anders getroffen, sigma_z bis 11 m); 2-Strahl-Punkte (traufe_N_mitte, ecke_boden_0) 60-190 px. Folgerung: Projektion liefert
einen PRUEFBAREN Vorschlag (Pick-Pruefbild), kein Mass. Zuverlaessig automatisierbar ist nicht das Picken, sondern das, was keine Picks braucht.

### Hebel, geordnet nach Zuverlaessigkeit (Beweis je Hebel = Regression identisch + Nullstart gruen)
1. Dauertest Nullstart (schon da): jede Werkzeugaenderung -> Regression; jede Ketten-/Datenaenderung -> Nullstart; drei saubere Laeufe = Freigabe.
2. Seite aus dem Netz statt aus Aehnlichkeit: unbekannte Fotos (31) in beide Seitennetze registrieren, Seite = Netz mit Inliern; in beiden
   (symmetrische Sicht) -> ausgeschlossen. Geometrisch, deterministisch; Werkzeug `sfm_registrieren` vorhanden, fehlt nur die Schleife.
3. Beobachtungs-Hygiene: jedes Werkzeug ersetzt seine eigenen Auto-Beobachtungen je Lauf (Schluessel Werkzeug+Merkmal) statt anzuhaengen;
   Deckel je Werkzeug; Nutzer-Beobachtungen bleiben. Sonst ertrinken die 21 echten in 186 automatischen.
4. Pick-Vorschlaege: Netzprojektion nur mit >= 3 Strahlen und sigma <= 0,2 m, immer mit Pruefbild (`foto_pick_pruefen`), nie ohne Blick - spart
   Zeit, kein Massverlust (Gate aus der LOO-Messung oben).
5. Die 7 ANNAHMEn des Generators aus Bandern ableiten (Zinnenzahl, Schallarkaden, Konsolen = Oeffnungs-/Periodenzaehlung je Koerper wie bei den
   Tuermchen) - nur wo die Suedwolke die Merkmale wirklich zeigt (Quellen-Blindheit), sonst bleibt ANNAHME stehen.
6. `foto_verhaeltnis`-Masse (10) durch Silhouetten-/Bandregeln ersetzen, wo eine Wolke oder kalibrierte Kamera existiert; sonst bleiben sie.
Nicht automatisierbar ohne Qualitaetsverlust: Sollwerte aus Dokumenten, Sichtabnahme des Sichtblatts, Generatorcode fuer einen NEUEN Bautyp.

**Nullstart 6 Ergebnis (nach den Reparaturen, komplette Kette durchgelaufen, Dichtwolke 567 s):** Volumen 0,14 % neben der Referenz, aber Pruefstand
63/70 statt 67/67. Offen: Modell nicht wasserdicht/mehrere Koerper (Generator mit abgeleiteten Massen), Silhouettenbreite 30 m und 23,5-28 m,
Quaderperiode, Tuermchen-Kupferradius und -oeffnungen. Massabweichungen > 0,3 m: QUADER_ZONE_Z 17,0 statt 23,0, KONSOLE_Z0 27,0 statt 27,5.
Naechster Schritt: QUADER_ZONE_Z-Regel (Plausibilitaetsfenster/Bandzuordnung) und Wasserdichtheit am Nullstart-Modell untersuchen, erst dann
Nullstart 7 (Ziel: drei saubere Laeufe in Folge).

**Nullstart 6, Nachlauf (gleicher Tag): 63/70 -> 66/70.** Zwei generische Reparaturen, Referenz unveraendert (Regression identisch):
1. `perioden_gruppen` (QUADER_ZONE_Z): Gruppen muessen sich um Faktor >= 1,3 unterscheiden (`min_verhaeltnis`), sonst "kein Wert" und der alte Wert
   bleibt. Ursache: in der Nullstart-Wolke fehlte das starke 0,25-m-Fenster der Quaderschichten (Staerke 0,67 in der Referenz), die uebrig
   gebliebenen Fenster 0,30/0,35 m ergaben eine Scheingrenze bei 17 m statt 23 m. Farbperioden sind zwischen Laeufen instabil (wie die Farbklassen).
   Hinweis: `masse.json` des Nullziels behielt den falschen Wert aus dem Vorlauf - bei Regelaenderungen das Ziel vor dem Wiederholen auf den
   Eingabestand zuruecksetzen (`cp masse.json`), sonst testet man den Altwert.
2. Generator-Hygiene: Schlitzschnitte der Bruestungsleisten (hell-Band 1,25 m, Schlitzhoehe 0,95) hinterliessen 2 Paare deckungsgleicher,
   gegenlaeufiger Dreiecke (Blech ohne Volumen, nichtmanifold angehaengt) -> "3 Koerper, nicht wasserdicht". Solche sich aufhebenden Paare
   werden entfernt und gemeldet (Referenz: 0). Ursache nicht an einem einzelnen Mass (7 Einzeltausch-Builds: alle 3 Koerper), sondern an der
   Bandhoehe 1,25 statt 1,0 m - die Schlitzgeometrie streift die Leiste. Offene Frage: Schlitze so setzen, dass sie nie streifen.
Rest (4 Pruefungen, alle am Aufloesungsboden der einseitigen Nordwolke, nicht an einem Fehler): Silhouette 30 m +0,16 m (GX 7,26 statt 7,10),
Zone 23,5-28 m -0,06 m, Tuermchen-Kupferradius -0,03 m (Band beginnt 0,5 m tiefer, Traufe 35,0-35,5 fehlt in der Wolke), Oeffnungsbreite 0,44
statt 0,45 (Pfeilergrenze). Bandkanten springen zwischen Laeufen um 0,25-0,5 m. Sollwerte bleiben (Regel: nie lockern); die Suedwolke liefert
die zweite Tiefenrichtung und ist der naechste Hebel fuer GX/Kupferband.

## BC. Suedwolke mit 31 neuen Fotos - Versuch 1: weiter verbogen (2026-11-01)
Suednetz neu (48 Fotos, Ernte 2): 40 Kameras, 5201 Punkte, Reproj 0,77 px, Cheiralitaetsfilter entfernt 119/121. Ausrichtung nur ueber Boden-/Wandanker:
Massstab 1,30 +-35 %, Residuen 50-490 px, Turmspitze bei z 5 m statt 55 m (hoechster Netzpunkt im Zylinder 7,4 m). `sfm_verzerrung_test`: VERBOGEN
(Fit alle 4,1 m, nur Dach 3,2 m, ausgelassene Punkte 12 m). Die neuen Fotos haben die Stauchung also NICHT behoben (Register AI Lehre 1:
einseitig + fast eben + unbekannte Brennweiten). `--kamera-modell RADIAL`: schlechter - nur 31 von 45 Fotos registriert (000 faellt heraus),
Massstab 0,13, Turm z 25 m, Urteil VERBOGEN; verworfen, SIMPLE_RADIAL-Netz wiederhergestellt. `SFM-AUSRICHTUNG-sued.json` wurde NICHT behalten
(ungueltig; sonst nutzt `sfm_dicht sued` eine falsche Transformation).
**Naechste Hebel (nicht gemacht):** (a) die Ausrichtung ueber das Dach statt den Boden: Dachpicks (gold/tuermchen/spitze) liegen in den drei Suedfotos
000/030/041 konsistent (Register AI: 0-4 px) - Netz in zwei Hoehenstufen getrennt anpassen, (b) Suedfotos ueber 060/061 an das metrische Nordnetz
binden (Ring), (c) Suedhoehen per `foto_verhaeltnis` an 049/014/000 gegen die Nordhoehen pruefen. Bis dahin liefert nur die Nordwolke Tiefe;
GX/Kupferband bleiben am Aufloesungsboden (Register BB).

## BD. Beobachtungs-Hygiene: Auto-Beobachtungen werden ersetzt, nicht angehaeuft (2026-11-01)
Befund (BB): 207 offene Beobachtungen, 186 automatisch - die `auto_id` enthaelt die Position, jeder Lauf mit leicht anderer Geometrie haengte neue an.
Reparatur: `masstabelle_io.auto_ersetzen(tab, praefix)` entfernt vor dem Eintragen alle `datum == "auto"`-Eintraege mit diesem Praefix
(fehlteile-<foto>-, breite-<foto>-, wolke-<seite>-, band_<koerper>_offen_); eingebunden in `fehlteile_finden` (nicht bei `--stl`), `foto_breitenprofil`
(auch ohne Zonen = raeumt), `wolke_vs_modell`, `wolke_baender`. Hand-/Nutzerbeobachtungen bleiben. Ergebnis: 207 -> 118, zweiter Lauf 118 (idempotent);
Pruefstand weiter 'alle bestanden', Regression identisch. Rest: 41 wolke_vs_modell, 35 breite, 18 fehlteil - echte Befunde des jeweils letzten Laufs.

## BE. Seitenzuordnung der 31 Fotos ohne Seite ueber die Seitennetze - Messung (2026-11-01)
Versuch (Kopie `martinstor_null`, Referenz unberuehrt): alle 31 Fotos mit Seite 'unbekannt' in BEIDE Seitennetze eingespeist, dazu je 10 Fotos mit
bekannter Gegenseite als Kontrolle (Nord-Fotos in das Sued-Netz und umgekehrt). Mass: 3D-Punkte des Fotos im Netz, Verhaeltnis richtig/falsch.
- **Der symmetrische Turm registriert in beiden Netzen:** Kontrollfotos hatten im falschen Netz 60-75 % der Punkte des richtigen (Ausnahmen 214 vs 1079).
  Die blosse Registrierung ('registriert ja/nein') trennt die Seiten NICHT - genau die bekannte Verklebung (sfm-seitentrennung-symmetrie).
- **Das Verhaeltnis trennt gerichtet, aber knapp:** bei allen 17 messbaren Kontrollen war das richtige Netz vorn (Verhaeltnis 1,30 bis 5,0, Median 1,8);
  die Ausreisser unten liegen bei 1,3. Bei den Unbekannten: Verhaeltnis >= 1,5 und >= 150 Punkte nur bei 003, 011, 016, 114 (alle Nord); 7 weitere
  zwischen 1,2 und 1,45 (010, 013, 059, 069, 070, 099 ...), 10 in keinem oder nur einem Netz sinnvoll registriert, 087 mit nur 119 Punkten.
- **Urteil:** die Methode ist NICHT zuverlaessig genug, um die 31 automatisch zu verteilen (Kontrollmenge 17, kleinste Marge 1,30; Netzgroessen
  verzerren die Zahl). Als Gate taugt hoechstens 'Verhaeltnis >= 1,5 und >= 150 Punkte' = 4 von 31 Fotos (alle Nord) - Gewinn gering, Risiko:
  jede Aenderung der Netzlisten veraendert die Nordwolke (Regression). Nicht uebernommen; Seite bleibt 'unbekannt'.
- Hebel, der stattdessen traegt: Seite aus einem **asymmetrischen Merkmal** (Uhr nur Nord? Zifferblatt/Sonnenuhr, Inschrift, Seitengebaeude Nord/Sued
  im Bild, Strassenverlauf) - braucht Bilderkennung je Merkmal, nicht Netzgeometrie. Offen.

## BF. Nullstart 7-9: Netz-Streuung, parallele Versuche, GLOMAP, Serienauswertung, Beziehungsprüfung (2026-11-02)
**Streuung gemessen (gleiche Eingaben):** Nordnetz inkrementell: Massstab-Sigma 2,8 bis 24,6 %, Wandstreuung 0,39 bis 0,75, Spitzenhoehe 53,3 bis 55,4 m;
Entfernen von Spiegelkameras (5 von 28) verschlechtert das Netz. Nullstart 6-9: 66, 56, 60, 58 Pruefungen - gleiche Kette, andere Wolke.
**Werkzeug:** `sfm_netz.py` getrennt in Merkmale/Matches (einmal, GPU) und Mapper-Versuche (CPU, `--db-von --seed --tag`); `nullstart.py` fuehrt K=6 Versuche
PARALLEL aus (87 s statt > 4 min fuer 4), waehlt nach kleinstem Massstab-Sigma (Kameras nur bei Gleichstand; erste Gewichtung "0 entfernte Kameras
bevorzugen" waehlte in Lauf 9 Sigma 5,8 % statt 2,9 % -> Turm 3 m zu tief, Glockenstock-Radius 4,2 statt 3,55 m).
**GLOMAP** (in pycolmap 4.2.1 vorhanden, bisher nur in scan-setup genutzt): `--mapper global`. Drei Seeds auf derselben Datenbank: Mapper 20 s,
Sigma 2,5 % in allen drei, Wandstreuung 0,30, Spitze 54,7 m (DOM1 54,80) - praktisch dasselbe Netz; Tuermchenresiduen 3-15 px (inkrementell bester 1-4 px).
Komplettlauf mit GLOMAP steht aus (Nullstart 10).
**Serienauswertung:** `nullstart.py` haengt jeden Lauf an `nullstart_serie.json` (mit Laeufen 6-9 nachgetragen); `tools/nullstart_serie.py` zaehlt, welche
Pruefung in wie vielen Laeufen scheitert. Nach 4 Laeufen SYSTEMATISCH (4/4): Tuermchen-Kupferradius und Silhouettenbreite 23,5-28 m; breit bei 30 m 3/4.
**Ehrliche Schritte:** `foto_kalibrieren` beendet ohne Punkte mit Exit 3 statt ValueError (044, 062); Nullstart fuehrt Exit 3 als 'uebersprungen'.
**Strenger Modus** `nullstart.py --streng`: Startwerte aller regelabgeleiteten Masse auf die Mitte ihres Plausibilitaetsfensters - scheitert eine
Ableitung, faellt es im Pruefstand auf, statt dass der Referenzwert still stehen bleibt (bisher: nur 10 von 59 Massen frisch abgeleitet, Rest Referenz).
**Beziehungsprüfung** (`objekt.json["masse_beziehungen"]`, 5 Beziehungen, von der Referenz erfuellt): Nullstart 9 lieferte KONSOLE_Z0 29,25 ueber
KONSOLE_Z1 27,0 und GX 8,68 breiter als der Schaft D 9,0 - jetzt verworfen (alter Wert bleibt, im Bericht 'beziehung_verletzt'). Plausibilitaetsfenster
verwarfen ausserdem KRAG_TRAUFE/GZ0/GZ1/ERKER_OBEN: die Zentralkoerper-Baender waren in Lauf 9 falsch eingeteilt (Klassenfarben instabil).
**Latenter Fehler behoben:** QUADER_GLOCKENSTOCK ('max() iterable argument is empty') lief seit Stufe C in der Referenz still auf Fehler - Fenster
muessen jetzt zu >= 50 % im Bereich liegen statt vollstaendig (2-m-Raster). Wert unveraendert 0,35; Referenz-Regression identisch.
**Offen aus der Serie:** Zentralkoerper-Klassen aus Farbe (gesims/stein/kupfer) kippen zwischen Laeufen; geometrische Klassifikation wie beim Dachband
der Tuermchen waere der naechste Hebel; Wolke Lauf 9 zusaetzlich vertikal gestaucht (obere Kante 50 m statt 54,5 m).

## BG - Nullstart 10 (GLOMAP), Ressourcenlage, offene Teststrecke (2026-11-02)
**Ergebnis Nullstart 10** (`--mapper global --netzversuche 2`): 64/70. Netzphase 23 s (GLOMAP), dicht 677 s. GLOMAP auf gleicher DB mit 3 Seeds praktisch
identisch (Sigma 2,5 %, Wandstreuung 0,30, Spitze 54,7 m); COLMAP-incremental streute Sigma 2,8-24,6 %. pycolmap 4.2.1, torch 2.15, kornia 0.9 sind aktuell.
Nullstart-Punkte bisher: 66, 56, 60, 58, 64 von ~70 (nicht reproduzierbar, Ursache: Mapper-Zufall + instabile Farbklassen der Wolke).
**Restfehler Lauf 10:** 'Anzahl getrennte Koerper 5'; Silhouettenbreite 23,5-28 m (10,78 statt 11,3-12,7); Ecktuermchen-Erkerkoerper Durchmesser 3,7 statt [2,5;3,2];
Profil Ecktuermchen 34,25 m 3,7; Gesamtbreite y bei 28,5 m 10,39; Quaderperiode Band tuermchen 33-37 m None.
**Befund '5 Koerper':** STL = Hauptkoerper + 4 frei schwebende Teile (je 68 Dreiecke, Vol 53, ca. 6x6x3,4 mm bei 1:87, z ~27 m, Ecken +-37/+-55 mm):
die Ecktuermchen-Erkerkoerper beruehren die Wand nicht. Wahrscheinlich gleiche Ursache wie der zu grosse Durchmesser 3,7 m (falsches abgeleitetes Mass/Lage).
Naechster Schritt: Lage/Durchmesser der Erker in Lauf 10 gegen Referenz vergleichen, Beziehung 'Erker beruehrt Wand' als Pruefung + masse_beziehungen.
**Ressourcen (gemessen):** GPU RTX 4060 95 % nur im PatchMatch-Schritt (~670 s von ~13 min), sonst ~14 %; CPU waehrend PatchMatch ~92 % Leerlauf;
RAM 16 GB (5 belegt, 9 frei, 18 Swap) kein Engpass; Intel-iGPU (Raptor Lake-S) fuer COLMAP/Torch unbrauchbar (kein CUDA/OpenCL/XPU). Leistungsgrenze/Luefter
sind nicht der Engpass (~54 W, voller Takt). Nicht 'perfekt': Hebel = Suednetz auf CPU parallel zu PatchMatch (`--cpu`, `nullstart.py` Thread, `--sued-seriell`
zum Abschalten), Bildbeschnitt `sfm_dicht.py --beschnitt` (Pixelfaktor 1,36 mechanisch belegt) - BEIDE NOCH UNGETESTET und nicht committet.
**Cloud:** Profis: Workstation/gemietete GPU/Cluster/Herstellerclouds. Gratis: Colab (T4), Kaggle (~30 GPU h/Woche), Lightning, HF Spaces; kein Tempogewinn
gegenueber RTX 4060, nur fuer Serienlaeufe; Datenschutz/Lizenz (LIZENZ_WERKZEUGE, geplanter Verkauf) -> Nutzerentscheidung, nichts hochgeladen.
**Generik (ehrlich):** nicht generisch sind Generator martinstor_v4_gen.py, ANNAHME-Eintraege, Koerperkonfiguration, Handpicks, masse_regeln/-beziehungen
je Objekt; Nullstart leitet nur 10 von 59 Massen frisch ab (`--streng` erzwingt Regelwerte nur fuer regelabgedeckte Masse).
**Serie nach 5 Laeufen:** SYSTEMATISCH Silhouettenbreite 23,5-28 m (5/5), Band tuermchen kupfer Aussenradius (4/5), Profil Ecktuermchen Durchmesser (4/5);
flackernd Silhouettenbreite bei 30 m (3/5).
**Fehler/Fixes dieser Etappe:** Spiegelkameras (100 % Punkte hinter Kamera) -> Cheiralitaetskriterium; 1600 vs 1598 px -> Arbeitsordner vor undistort loeschen;
Core-Dumps -> RLIMIT_CORE=0 (alter Dump: Nutzer `sudo rm /var/lib/systemd/coredump/core.python.*`, Root 96 %); Netzwahl Sigma-0,1*Kameras statt Sigma+2*entfernt;
Nullstart nutzt Referenzwissen via masse.json (nur 10/59 frisch) -> offengelegt, `--streng`.
**Offene Teststrecke:** (1) Regression `tools/regression.py modelle/martinstor/objekt.json --pruefen` auf ungebundene Aenderungen; (2) `--beschnitt`
Wolkengleichheit gegen Vollbild im Turmzylinder (GPU); (3) Nullstart 11 mit Sued-auf-CPU parallel; (4) `--streng`-Lauf; (5) Erker-Anliegen/5 Koerper;
(6) geometrische Klassifikation der Zentralkoerper-Baender; (7) Erntetempo-Patch `bilder_holen.py`; (8) Suedwolke (Ring via 060/061, Dach/Sockel getrennt).

## BH - Iteration 1: Ecktuermchen-Messfenster (Nullstart 11, 2026-11-02)
**Beobachtung:** Nullstart 11 64/68; 'Profil Ecktuermchen Durchmesser bei 37,75 m' 3,98 gegen Soll 2,33-3,13. Der Querschnitt durch das Nullstart-Modell selbst ist 2,65 m
(Referenz 2,74): die Pruefung (Typ `schnitt_ausdehnung`, schon ein Querschnitt) misst in einem Fenster, das `wolke_profile.py` als Achse +- 0,7*d_koerper setzt.
**Ursache:** Der Kreisfit an die Nullstart-Wolke gab d_koerper 3,76 (Referenz 3,11; vermischt sich mit dem Zentralkoerper) -> Fenster x -6,65..-1,38 statt -6,22..-1,86 ->
Schnittkontur des mittleren Helms im Fenster -> Messwert 3,86-3,98. Nicht das Modell war zu dick, das Fenster war zu breit.
**Fehlversuch (zurueckgenommen):** Kegel-r0 aus der Steigung statt aus dem Traufradius (Nullstart: 2,02 gegen 1,83): Messwert 3,98 -> 3,86, Nullstart 62/68; verworfen.
**Aenderung:** `wolke_profile.py`: Fensterbreite = min(d_koerper, obere Quellgrenze der Zeile 'erker_34' = 3,2). Sollwerte unveraendert. Referenz-Regression identisch;
Nullstart ab 'entzerren': 64/68, Profil Ecktuermchen 37,75 m besteht.
**Offen:** Erker 34 m 3,33 gegen 2,5-3,2 (Fenster x -6..-2 enthaelt Anschlusspunkt Turm/Wand, null -2,20 gegen Referenz -2,43); Silhouettenbreite 30 m (14,9) und Zone 23,5-28 m (11,28 gegen >= 11,3);
Zentralkoerper-Quaderperiode 20-24 m (0,4). `tools/viewer_bauen.sh <objekt> <datei>` baut den 3D-Viewer in einem Schritt (Einheiten: --stl mm, --stl2 Meter).

## BI - Nullstart 12 (streng), Vorwissen-Messung, Mapillary, Pruefstand-Tempo (2026-11-02)
**Nullstart 12 (`--streng`, GLOMAP, 2 Netzversuche):** 65/69 bestanden, 13 min; 16 Masse frisch abgeleitet, 7 bleiben Referenz (GY, EX, EY, ER Quellwiderspruch Regel 5; DACH_MITTE_Z/Z2 unbenutzte Fallbacks;
PROFIL_DATEI Schalter), 3 'unplausibel' (KRAG_TRAUFE 8,88 statt ~31,75; GZ0 15,0 statt ~34,75; KONSOLE_Z0 31,0 statt 27,5), 1 Fehler (OR: IndexError). Ursache: **Zentralkoerper-/Tuermchen-Baender
werden nach FARBE klassifiziert und die Klassen (kupfer/gesims/stein/hell) kippen zwischen Laeufen** (Lauf 12: 'kupfer' bei 14,25-15 m und 22-23,5 m statt 32,0-34,75 m); die Regeln waehlen nach Klassennummer
(`kupfer_1`, `klasse:gesims:0`). Naechster Hebel: geometrische Auswahl (Profilsteigung/Kragdach) statt Farbklasse.
**Vorwissen-Messung** (`tools/vorwissen_empfindlichkeit.py`, 32 Masse ohne Regel je +-15 %, Kopie des Nullstart-Ordners, STL-Hash): 22 kontrolliert (mind. eine Pruefung faellt), 1 unkontrolliert
(ARKADE_UNTER_TRAUFE), 9 wirkungslos (STL bitgleich: T0, T1, SEG, DACH_MITTE_X/Y/2, TUERM_ACHSE_DX/DY - vom Generator nicht gelesen). Stark kontrolliert: SPR (36 Pruefungen), AW (34), TUERM_SPITZE (11), ZZ (8);
schwach (1-2 Pruefungen): ZK, WK, FA, KNAUF_ANTEIL, TWs, DACH_OBEN_X/Y, KUGEL_X/Y, LATERNE_D. Einschraenkung: die Sollwerte stammen aus derselben Referenz-Masstabelle - 'kontrolliert' heisst
'die Pruefung merkt die Abweichung', nicht 'unabhaengig belegt'. **Fehler der ersten Fassung (verworfen):** die Kopie zeigte mit `obj["masstabelle"]` auf den echten Nullstart-Ordner; 64 Pruefstand-Laeufe
ueberschrieben dessen pruefbericht.json/MASSNACHWEIS.md (wiederhergestellt durch Neulauf: 65/69), Ergebnis '0 kontrolliert' war wertlos. Behoben: alle Pfade der Kopie umbiegen, alten Bericht loeschen,
Bericht muss zum Variantenmodell gehoeren, Warnung wenn der echte Bericht sich aendert.
**Foto-Abdeckung (Referenz-Netze):** Nord 16 Kameras, alle aus EINEM Sektor, 27-150 m (Median 44), Hoehe -10..6 m; Sued 40 Kameras, alle Suedost, 8-17 m (Median 14), Hoehe -3..0 m (sehr steile Blickwinkel,
kaum Basis -> verbogene Suedwolke). Wolkenpunkte je 5-m-Schicht (Nord): 15.000 bis 30 m, 4.500 bei 40-45 m, 1.300 bei 50-55 m, ~100 darueber (Spitze nie belastbar). Gebraucht: mehr ABSTAND (40-80 m),
Boegen um beide Seiten, erhoehte Standorte (Fenster/Parkhaus/Hang), Tele fuer die obere Haelfte, Originalbilder ohne Zuschnitt.
**Mapillary** (Token gueltig, `~/.config/mapillary_token`; `bilder_holen.py` setzt die Quelle NICHT um, Mapillary laeuft ueber `mapillary_rip.py` ohne `-I`): 55 Bilder im Umkreis 80 m, 39 geladen
(16 persp, 23 360-Ausschnitte), Abstand 31-98 m (Median 72), **alle Nordseite (Peilung 0-45 Grad), Strassenhoehe**, von einer Gehsequenz, Regentropfen auf der Linse; nur ~15 zeigen den Turm. Mehr Nordabdeckung
in besserem Abstand, aber keine neue Seite und keine Hoehe - hilft Sued/Spitze nicht. Offene Frage: ob die ~15 Turmbilder das Nordnetz verbessern (Test mit Extranetz, nicht in den Nullstart).
**Weitere Quellen geprueft:** LGL BW offen: Hauskoordinaten, Hausumringe, DGM, DOM, DOP20, LoD1 (kein Mesh/Schraegbild belegt); Freiburg 3D-Stadtmodell als Open Data beschrieben (Rohdaten/Lizenz ungeprueft,
Katalogseiten laden per Skript); keine Orbit-Drohnenvideos zum Martinstor gefunden; Hoehenangaben Wikipedia 60 m / Structurae ~65 m (Widerspruch, Regel 5); keine Plaene von 1901 online (Stadtarchiv, Denkmalpflege).
**Pruefstand-Tempo:** `_flaechenpunkte` und `hypso_ueber` teilen die 0,3-m-Unterteilung (`_unterteilt`): 9,7 -> 5,9 s, Regression identisch (Commit e8d8b3d). `bauen_abnehmen.sh martinstor` 34 s, Regression 14 s.
**Foto-Vorpruefung** (`tools/foto_vorpruefung.py`, ohne `-I`): EXIF/Manifest-Metadaten + Schaerfe vor dem Netz; Seite/Entfernung/Blickwinkel aus GPS (+ Peilung gegen Heading), Warnzeichen (unscharf, klein, ISO > 1600,
Belichtung > 1/60 s, Digitalzoom, kein Brennweiten-EXIF, steiler Blick > 55 Grad, schaut weg, > 5 Jahre alt). Test Mapillary (39): 16 ohne Warnung, alle GPS-Seite 'nord'; Commons-Eingang (100): 74 ohne Warnung,
Kamera-Modell 26 -> 80/100 und f35 16 -> 31/100 mit Manifest-Rueckfall (verkleinerte Dateien ohne EXIF), nur 18/100 mit GPS-Seite (nord 9, sued 6, ost 3). GPS Altstadt ca. 5-10 m, Kompass 10-20 Grad: Seite = Vorschlag.
Alter ist nur ein Hinweis (Turm aendert sich nicht, Umgebung schon). Metadaten sagen nicht, ob der Turm im Bild ist (Mapillary 'persp': ~15 von 39).

## BJ - Bandauswahl nach Plausibilitaetsfenster; Pruefung der Vorpruefung (2026-11-02)
**Bandauswahl:** `masse_aus_profilen.py`: Regeln `band_z/band_r/band_r2/band_periode` waehlen weiter per Index (`kupfer_1`, `vor_kupfer_1`, `klasse:gesims:0`). NEU: liegt der Wert der Index-Wahl ausserhalb des
`bereich` der Regel (oder das Band fehlt), werden ALLE Kandidaten des Musters geprueft; genau ein Wert im Fenster -> der gilt (`ersatzwahl: true` im Bericht), mehrere verschiedene -> der dickste, wenn >= 2 x so dick
wie der naechste, sonst 'mehrdeutig' (kein Wert). Referenz-Regression identisch, in der Referenz wird die Ersatzwahl nie benutzt. Nullstart 12 (Daten): KRAG_TRAUFE 8,88 -> 31,0 (Ref 31,75), GZ0 15,0 -> 34,5 (Ref 34,75).
**Ehrliches Ergebnis:** Nullstart ab 'entzerren' mit den neuen Regeln 62/69 statt 65/69. Neu faellt 'Zinnen-Scharten Nord/Sued (z 31,1 m)' (0 statt 4): mit KRAG_TRAUFE 31,0 liegt 31,1 schon im Dach; die Referenz hat 31,75.
Die 65/69 vorher kamen mit der Fenstermitte 31,5 (Zufallstreffer, kein abgeleiteter Wert). Das Gesimsband liegt im Nullstart um 0,75 m tiefer als in der Referenz (Bandkanten 0,25-0,5 m gerastert + Wolkenstreuung) - der
Ableitungsfehler ist echt, die Pruefung zeigt ihn zu Recht. KONSOLE_Z0 und OR bleiben ohne Wert (im Lauf gibt es das Band nicht: kein 'gesims' bei 27,5, kein 'hell'). Offen: Kantenlage der Baender genauer (feineres Raster
oder Kantenfit statt Schichtraster), dann haengt der Zinnen-Test nicht am Zufall.
**Vorpruefung (foto_vorpruefung.py) gegen die echten Netzergebnisse geprueft:** Nord 16 von 18 Fotos registriert, Sued 31 von 45 (ohne die 3 'Fernaufnahme (EXIF-Prior)'). Ergebnis: **kein Beleg, dass sie besser filtert.**
Alle registrierten Fotos tragen eine Warnung (meist 'kein Brennweiten-EXIF': die verkleinerten Netz-Eingangsbilder haben kein EXIF mehr, die Brennweite kommt aus dem Manifest - Fehlalarm). Schaerfe (Laplace-Varianz):
Sued registriert Median 5620 gegen 4350, AUC 0,66, p = 0,042 (n 31/14) - schwach; Nord nicht testbar (2 nicht registrierte). Die Schwelle 40 passt nicht zu diesen Werten (Wertebereich Tausende). Einzige belegte Metadaten-Filterung:
EXIF-Prior der Brennweite (netz json: 3 Fernaufnahmen ausgeschlossen). **Naechster Beweis:** Fotos nach Vorpruefung aus dem Netz nehmen und Sigma/Kamerazahl/Wandstreuung gegen Zufallsauswahl gleicher Groesse vergleichen.
**Ursache des Zinnen-Fehlers (korrigiert, BJ):** NICHT die Bandkanten-Rasterung. Alle abgeleiteten Hoehen > 15 m liegen im Nullstart 12 tiefer als in der Referenz (7 von 7, Median-Verhaeltnis 0,982; ERKER_OBEN -0,75, KRAG_TRAUFE -0,75,
KONSOLE_Z1 -0,50, UZ -0,49, GZ1 -0,50, GZ0 -0,25 m; QUADER_ZONE_Z 21 statt 23). Dieselbe Verschiebung in der Ausrichtung (triangulierte Hoehen Nullstart gegen Referenz): gold_NE 54,11 / 55,34, gold_NW 54,69 / 55,80,
tuermchen_NE 43,90 / 44,52, tuermchen_NW 44,21 / 44,69, traufe_N_mitte 40,26 / 40,61 (-1 bis -2,8 %). Nullstart-Netz Sigma 3,0 %. **Ursache im Code:** `sfm_ausrichten.py` nutzt als feste Hoehenanker NUR die LoD2-Bodenecken
(z -0,30, 12 m Basis); `ecke_wandoben` (LoD2, z 37,1-37,3) und der DOM1-Gipfel (54,84) sind nur Pruefungen, keine Zwangsbedingungen - der Maßstab nach oben haengt am Boden und streut mit dem Netz-Sigma (3 % = +-1,9 m bei 65 m).
Beide Netze (Ref und Nullstart) tragen diesen Fehler; welches naeher an der Wahrheit liegt, ist offen (DOM1-Gipfel 54,84 gegen gold 54,1-55,8). **Naechster Hebel:** amtliche Hoehenanker (LoD2-Wandoberkante, DOM1-Gipfel, ggf. Zinnenkranz-DOM1)
mit Gewicht als vertikale Massstabsbedingung in die Ausrichtung (Regel 3d: amtliche Anker erlaubt), danach beide Netze neu und die Verschiebung gegen die Referenz erneut messen.
**Hoehenanker - Pruefung der Umsetzbarkeit (2026-11-02), NICHT umgesetzt:** (1) `kranz_*` (z 31,5, Sigma 1,5, z_frei 'kranz', Laser-Stufe 31-32 m) hat im Nordnetz nur ein Foto mit Bildpunkten (031: kranz_NE/NW) und waere mit Sigma 1,5 m
nicht staerker als das heutige Netz-Sigma (3 % = 0,9 m bei 31 m). (2) `ecke_wandoben_*` (LoD2, z 37,1-37,3, Sigma 0,6) hat KEINE Bildpunkte in irgendeinem K-*.json; die `ecke_boden`-LINIEN laufen bis Z_KANTE_OBEN und
legen nur die Richtung fest, nicht die Hoehe. (3) DOM1-Gipfel 54,84 (`spitze_dom`) ohne Bildpunkte; die Wolke zeigt das Firstplateau nicht robust: im Zylinder r < 5 m ueber 48 m liegen Nadel und Knaeufe (max 67 m), Perzentile
unbrauchbar (Ref p90 54,55, Nullstart 55,89, p99 > 63 m). Fruehere Messung (Memory lidar-massnachweis): SfM-Dach 54,0 gegen DOM1 54,80 - dieselbe Richtung (SfM zu niedrig). **Bedingung fuer einen echten Hoehenanker:**
mindestens 6-8 Bildpunkte der LoD2-Wandoberkanten-Ecken (ecke_wandoben_0..3) in 2-3 Nordfotos (kalibrierte Kameras 000/005/006/014/031) mit Pick-Pruefung (`foto_pick_pruefen.py`), danach Gewicht Sigma 0,6 m in `sfm_ausrichten.beobachtungen`
(feste Hoehe, kein z_frei). Das braucht neue Picks (von Hand oder per Modellprojektion mit Sichtkontrolle); Regel: Sollwerte nicht lockern, keine Toleranz nach Netz-Sigma. Bis dahin: Nullstart-Hoehen tragen ~+-2 % (Sigma 3 %).

## BK - Kompletter Nullstart 3x ab 'anlegen' (2026-11-02), Beweis und Fotobewertung
**Aufbau:** `tools/nullstart_beweis.py` laeuft `tools/nullstart.py` N-mal komplett (streng, GLOMAP, 2 Netzversuche), sichert je Lauf Pruefbericht/Masse/STL und wertet automatisch aus (`modelle/martinstor/NULLSTART_BEWEIS.md`).
**Ergebnis (3 Laeufe):** 62/67, 56/68, 64/71 (Mittel 88,3 %, Standardabweichung 5,3 Prozentpunkte; Referenz 67/67); Wanduhr 764 / 761 / 785 s. STL-Volumen 0,6-1,1 % neben der Referenz.
Von 56 Pruefungen, die in allen Laeufen vorkommen: 42 immer bestanden, 14 flackernd, 0 nie. Die Pruefungsmenge ist nicht konstant (67/68/71), weil Bandpruefungen die gemessenen Fenster im Namen tragen.
Masse-Streuung zwischen den Laeufen: ERKER_OBEN 34,25 / 39,75 / 34,25 (Ausreisser Lauf 2), KRAG_TRAUFE 29,88-31,38 (Ref 31,75), GZ1 39,0-40,75, GZ0 34,0-35,5. H_TOTAL 65,3 stammt ohne Regel aus der Referenz.
**Grenzen (Beweis ist schwach):** nur 2 von 67 Pruefungen unabhaengig von Referenz und Fotos (1 LoD2, 1 Dokument; beide bestanden); Sollwerte stammen aus der Referenz-Tabelle; 24 dynamische Pruefungen ohne Quelltyp in der Tabelle;
32 von 59 Massen ohne Regel aus der Referenz (Register BI).
**Zeitprofil Lauf 1:** PatchMatch 652 s (85 %), netz_sued 110 s + ausrichten_sued 31 s (CPU, parallel dazu), registrieren_060/061 37 s, kalibrieren_* (15 Schritte) 20 s, auswertung 11 s. Passiver Sampler (alle 2 s):
waehrend PatchMatch GPU > 90 % bei CPU < 15 % in 21 von 23 Proben (CPU-Mittel 7 %). CPU-Parallelisierung der Restschritte spart hoechstens ca. 1 min von 760 s; der Hebel ist PatchMatch (Fotozahl, Pixel, `--beschnitt` ungetestet).
**Fotobewertung (`tools/foto_auswahl.py`):** Registrierung wird von Match-Graph-Kennzahlen vorhergesagt (Sued: Inlier-Summe AUC 0,91 p 0,001; Grad 0,79 p 0,034), NICHT von Schaerfe (AUC 0,74 p 0,08; fruehere Angabe p 0,042 gilt nicht), Aufloesung,
Merkmalszahl oder Brennweite; Nord untestbar (2 nicht registrierte). Das sagt nur, welche Fotos das Netz ohnehin nicht nutzt, nicht welche es verbessern. `--beitrag`: analytischer Verlust je Foto (Spuren mit 2 Beobachtungen): kein Foto
verliert mehr als 1,8 % der Sparse-Punkte (Nord 014 am wertvollsten, 002/051/045/027/001 zusammen ca. 5 %, oben fast nichts) - die Netze sind redundant. Alle Kameras liegen in einem Sektor (Nord 3, Sued 1).
**Nicht belegt / offen:** Nullstart mit den besten N Fotos und kleinerer Aufloesung gegen den Volllauf (Zeit vs Pruefungen, Stufenmodell grob -> fein); Kalibrierung parallel zu PatchMatch (Patch als Kopie vorbereitet, nicht eingebaut);
Mapillary-Netztest (39 Bilder geladen, nicht im Netz); Hoehenanker braucht neue Picks (BJ).

## BL - Stufenmodell (grob -> fein), Netzstufe GLOMAP/inkrementell, CPU- gegen GPU-SIFT (2026-11-02)
**Werkzeuge:** `tools/stufenversuch.py` (gleiches Netz, nur die dichte Stufe variiert: `nullstart.py --ab dicht --dicht-extra ...`), `sfm_dicht.py --fotos` (Teilmenge: Rekonstruktion ohne die anderen Fotos zuschneiden, sonst Abbruch 'Check failed: IsGrey'),
`foto_auswahl.py --waehle N [--schicht]` (greedy Abdeckung triangulierbarer Punkte; --schicht = 5-m-Hoehenschichten gleich gewichtet), `nullstart.py` Kalibrierung parallel zu PatchMatch (15 K-Dateien byte-gleich seriell/parallel bewiesen, 20 s -> 7 s; `--kal-seriell` = alt).
**Fehler beim Messen (korrigiert):** erste Teilmengen-Laeufe stuerzten ab, der Treiber zeigte stattdessen den Basiswert; Treiber nahm den ERSTEN statt letzten `dicht_nord`-Eintrag (Bericht sammelt mehrere) -> Zeiten 656,6 s statt 672,6/670,9 s;
Vergleich muss den neuesten Ordner je Variante laden. Alle Zahlen unten sind nachgerechnet.
**PatchMatch ist reproduzierbar:** `basis` und `basis2` (gleiches Netz, gleiche Einstellungen): STL byte-gleich, alle 71 Pruefungen gleich, alle Masse gleich. Die Streuung zwischen vollen Nullstarts (62/67, 56/68, 64/71) kommt aus der NETZstufe (BK).
**Stufen (54 gemeinsame Pruefungen, Netz aus Beweislauf 3):** Basis 27 Fotos/1600 px 672 s 48/54; 27/1200 472 s 49/54; 27/800 304 s 44/54; 16/1200 268 s 44/54; 11/1600 219 s 45/54; **11/1200 160 s 50/54; 11/1000 134 s 48/54**;
11 Schicht/1200 46/54; 11 Schicht/1000 50/54; 6/1200 84 s 40/54. Ergebnis: 6 Fotos zu wenig; 11 Fotos bei 1000-1200 px nicht nachweisbar schlechter als die Basis und 4-5x schneller; sonst NICHT monoton (16 Fotos schlechter als 11,
Schichtgewichtung 1200 px schlechter, 1000 px besser) - einzelne Laeufe streuen um +-3-4 Pruefungen, kleinere Unterschiede sind kein Beleg. Hoehenmasse (GZ1, DACHHOEHE) in allen Varianten gleich (Netz, nicht Dichte).
**Netzstufe, 6 Seeds je Kombination (Basisfotos, CPU, 24 Netze):** GLOMAP + GPU-SIFT-Datenbank: Sigma 2,5-2,6 % (6/6), gold_z 54,09-54,29, 30 Kameras = STABIL. GLOMAP + CPU-SIFT-Datenbank: Sigma 27-54 %, gold_z ~1 m (6/6 UNBRAUCHBAR;
Parameter- und Matchzahlen beider Datenbanken aehnlich: 9609 gegen 10726 Merkmale/Bild, Inlier CPU/GPU Median 0,95; Ursache offen). Inkrementell + CPU-Datenbank: Sigma 1,9/2,0/2,0/7,4/22,8/24,4; inkrementell + GPU-Datenbank: 2,6/2,8/3,4/4,6/7,3/15,6
(25-28 Kameras, sehr streuend). **Folgerung:** GLOMAP nur mit GPU-SIFT; `sfm_netz.py` warnt jetzt bei `--cpu --mapper global`. Das Suednetz im Nullstart nutzt `--cpu` mit dem Standard-Mapper (inkrementell) - dort gilt die Streuung der inkrementellen Zeilen.
**Auslastung (Sampler 81 min):** CPU Mittel 15 %, Median 6 %; GPU Mittel 77 %, 76 % der Zeit > 90 %; RAM 4,7 von 15,7 GB; PatchMatch zieht nur ca. 38-58 W und 333 MiB VRAM - ob die GPU voll ausgelastet ist, ist nicht gemessen.
**Offen:** Mapillary-Netztest mit GPU-Merkmalen (CPU-Datenbank taugt nicht fuer GLOMAP); Pruefung, ob zwei PatchMatch gleichzeitig auf einer GPU schneller sind; Stufenmodell mit zweiter Stufe nur fuer die obere Haelfte; Wiederholung der Stufen auf einem zweiten Netz.

## BM - nullstart.py --stufe grob/voll: Vergleich auf demselben Netz (2026-11-02)
**Schalter:** `nullstart.py --stufe grob [--grob-fotos 11] [--grob-px 1000]` waehlt vor der dichten Stufe die Fotos aus dem frischen Netz (`foto_auswahl.py --waehle`) und rechnet PatchMatch nur damit; `voll` = alle Fotos, 1600 px (Standard). Stufe und Argumente stehen im Bericht und im Serienprotokoll.
**Test:** kompletter Nullstart ab 'anlegen' in Stufe grob (Netz Sigma 2,1 %, 30 Kameras; gewaehlt 006,015,018,136,014,005,031,118,049,019,001 bei 1000 px): dicht 133 s, **41/56** bestanden. Danach auf DEMSELBEN Netz `--ab dicht --stufe voll` (ca. 11 min): **57/72**.
Je 15 Pruefungen fallen durch, aber andere: nur in grob (11): Tuermchen-Kegel Durchmesser 2/4 m unter Spitze, Tuermchen Anzahl, Zinnenkranz Oberkante, Zinnen-Scharten Nord/Sued, Anzahl getrennte Koerper, Silhouettenbreite 30 m, Ecktuermchen-Achse, Profil Dach 53 m, Quaderperiode 20-24 m;
nur in voll (11): meist Bandfenster-Pruefungen (fenstername-abhaengig) und Profile; in beiden 4. grob erzeugt 16 Pruefungen weniger (56 statt 72): ohne ausreichende Wolke entstehen Baender/Pruefungen gar nicht.
**Bewertung:** grob = brauchbarer Entwurf fuer Hoehen und Gesamtform, aber der obere Teil (Tuermchen, Zinnen) geht verloren - kein Ersatz fuer voll. Frueherer Wolken-Test auf dem Netz von Beweislauf 3 (11 Fotos/1000 px: 48/54 gegen Basis 48/54) zeigte das nicht: Ergebnis haengt vom Netz und von der Fotoauswahl ab, einzelne Laeufe streuen.
**Naechster Schritt:** Fotoauswahl mit Mindestabdeckung der oberen Schichten (27-45 m) erzwingen und auf diesem Netz dichte Stufe neu vergleichen.

## BN - Sweet Spot der dichten Stufe = Aufloesung, nicht Fotozahl (2026-11-02, drei Netze)
**Foto-Teilmengen verlieren den oberen Teil** (Netz 4, Sigma 2,1 %): 11 Fotos/1000 px 55/69, 16 Fotos 60/73, Schichtauswahl 11/16: 55/69 und 54/74 gegen alle 27 Fotos/1000 px 67/80. Tuermchen-Kegel, Zinnen, Helm fallen durch. -> `--stufe grob` nimmt jetzt ALLE Fotos (`--grob-fotos 0`).
**Aufloesung (alle Fotos), gleiches Netz je Paar:** Netz 3: 800 px 50/60, 1200 px 54/60, 1600 px 54/60 (gemeinsame Pruefungen; Zeit 304/472/673 s). Netz 4: 1000 px 67/80 (369 s) gegen 1600 px 57/72 (ca. 650 s).
Netz 5 (Sigma 2,4 %): `grob` 1000 px **72/76** (389 s PatchMatch, 4 durchgefallen) gegen `voll` 1600 px **55/74** (19 durchgefallen: Bandfenster Tuermchen, Profil Ecktuermchen, Zinnen-Scharten, Tuermchen-Kegel). In allen drei Netzen ist 1000-1200 px nicht schlechter,
zweimal deutlich besser als 1600 px, und 1,8x schneller. Unter 800 px faellt die Quote (Netz 3). Mechanismus nicht belegt (Vermutung: festes PatchMatch-Fenster deckt bei kleineren Bildern mehr Wandflaeche ab, weniger Feinrauschen). Hardware-unabhaengig (nur die Zeit haengt von der GPU ab).
**Objektabhaengig:** Fotos des Netzes sind 1024-2000 px lang (Median 2000); bei 1600 px werden 27 von 31 verkleinert, bei 1000 px alle. Fuer andere Objekte neu messen.
**Werkzeuge:** `tools/sweetspot.py` (Leiter 800/1000/1200/1600 auf vorhandenem Netz, Vergleich auf gemeinsamen Pruefungen, kleinste Aufloesung innerhalb Toleranz 3 -> `modelle/<objekt>/sweetspot.json`), `nullstart.py --stufe auto` liest die Datei.
Aktuelle `sweetspot.json`: 1200 px, nur aus den gespeicherten Ergebnissen von Netz 3 (800/1200/1600 px, ohne 1000 px) - ein Messpunkt, kein Leiterlauf.
**Offen:** voller Leiterlauf inkl. 1000 px; ob `voll` (1600 px) als Standard auf 1000-1200 px gesetzt wird (Entscheidung beim Nutzer); Mechanismus; zweites Objekt.

## BO - Bandwahl-Streuung und unabhaengiger Massstab (2026-11-02)
**Frage:** robuste Bandwahl, unabhaengiger (Hoehen-)Massstab. **Werkzeug:** `tools/masse_bootstrap.py` (N Teilstichproben zu 70 % der Wolke, je Stichprobe die echte Kette wolke_baender -> masse_aus_profilen im Sandkasten; 100 Stichproben in 2 s auf CPU).
**Bandwahl, gemessen an 23 gespeicherten Ergebnissen (3 Beweislaeufe + 20 Stufenvarianten, gleiche Fotos, vier Netze):** Einzellauf-Ausreisser: ERKER_OBEN 39,75 (Median 34,5), DACHHOEHE 17,4 (14,9), QUADER_ZONE_Z 17-26 (Median 21), GZ1 38,0 (40,5), KRAG_TRAUFE 29,88 (31,0), HELM_UEBER 0,35-2,5. Der Median ueber die Laeufe liegt bei den Hoehenmassen innerhalb 0,5 m an der Handreferenz (GZ1 und DACHHOEHE 0,00, GZ0/ERKER_OBEN 0,5, KRAG_TRAUFE 0,75 - dort Bias nach unten).
**Ergebnis Bootstrap (eine Wolke):** MAD ~0 fuer fast alle Hoehenkanten (GZ0, GZ1, ERKER_OBEN, UZ), aber die Laeufe streuen MAD 0,25 und Spannen bis 5 m. Die Teilstichprobe findet nur 1 % der ERKER_OBEN-Kippungen (39,0 gegen 34,5). **Die Bandwahl-Streuung kommt aus dem Netz/der Wolkenrealisierung, nicht aus dem Punktrauschen** - ein Bootstrap innerhalb eines Laufs kann sie nicht ersetzen (ehrliche Grenze, im Werkzeug dokumentiert). Robust ist nur der Median ueber unabhaengige Realisierungen (`nullstart_beweis.py`, >= 3 Laeufe); Einzelwerte mit Spanne > 1 m sind 'streut' und gehoeren nicht als Einzelwert in den Generator.
**Unabhaengiger Massstab:** NICHT geloest. Geprueft: DOM1-Zellen gegen Wolkenhoehe je Zelle. Die Fotowolke sieht Fassaden, keine Daecher: p95 je Zelle liegt bei Turmzellen +3...+9 m ueber DOM1 (Fassadenhoehe, nicht Dachflaeche), unter 30 m ~0 +- 2 m (MAD 2 m) - unbrauchbar als Skalenmass. Einzig die Peakzelle stimmt: Wolkenmaximum 54,88 gegen DOM1 54,79 (px800-Wolke, 1 Zelle, kein Beleg). Ein echter Hoehenmassstab braucht Bildpunkte auf LoD2-Wandoberkante/Gedenktafel in den kalibrierten Fotos (Register BJ) - noch nicht gepickt; DOM1 ist wegen steiler Helme/Nadeln nur Peak/flach brauchbar.
**Offen:** Median-Konsens in `nullstart_beweis.py --auswerten` als Ausgabewert (Mass + MAD + Kennzeichen 'streut'); Hoehenanker-Picks; Wiederholung des Bootstraps auf der Wolke des Leiterlaufs.

## BP - Leiterlauf (Sweet Spot) und Massstab aus mehreren Quellen (2026-11-02)
**Leiterlauf Netz 5 (alle Fotos, gleiche 61 gemeinsame Pruefungen):** 800 px 50 (303 s), **1000 px 58 (385 s)**, 1200 px 54 (473 s), 1600 px 48 (652 s). Sweet Spot **1000 px** (kleinste Stufe innerhalb Toleranz 3 der besten) -> `modelle/martinstor/sweetspot.json`. Standard geaendert: `nullstart.py --stufe auto` (neu Standard; `fein` = 1600 px ueber Nacht), `sfm_dicht.py --max-size` ohne Angabe = Sweet Spot, sonst 1600. Fund: sweetspot.py nahm `stufen_stdout.log` statt des Ordners (Glob) - behoben. Regression identisch.
**Massstab aus mehreren Quellen:** `tools/massstab_schwarm.py` (Kombinierer: s = wahre Meter/Modellmeter, Vertraeglichkeitstest K=2, Widerspruch nicht mitteln, von Bodenankern abhaengige Quellen zaehlen nicht als unabhaengiger Beleg) und Quellen-Plug-ins:
- `massstab_quelle_gps.py` (EXIF-GPS, Entfernung Kamera-Turmachse): s = 1,009, MAD 0,041, Bootstrap-Sigma 0,04, nur 4 Kameras im Netz (Foto 133 bei 356 m ausgeschlossen). Kamerapaare (Basis 20-27 m) zu verrauscht (s 1,06-1,31). Grob, unabhaengig. 
- `massstab_quelle_lod2.py` (Traufkanten der Nachbarn): nur 6 von 426 Kanten (2 Gebaeude) angedockt, s = 0,974 +- 0,037; Andocken teils auf Schilderkanten; Posen aus Bodenankern -> abhaengig, nur Hinweis.
- `massstab_quelle_normobjekte.py` (Personen, YOLOS CPU): 84 Detektionen, s = 0,744 (Bodenebene 0) bzw. 1,075 (-1,7 m) - Ergebnis bestimmt von der Annahme -> `belastbar:false`, ausgeschlossen. Auffaellig: Kamerahoehen ueber Boden Median 0,02 m (Strassenfotos 1,7 erwartet) - eigene Pruefung offen (moegliche Hoehenverzerrung der Posen).
**Stand:** einzige belastbare unabhaengige Quelle (GPS) vertraeglich mit den Ankern (+0,2 Sigma, Sigma 4-5 %) - das schliesst Fehler < ~8 % nicht aus; ein Hoehenmassstab ist NICHT belegt. **Nicht umgesetzt:** Sonnenschatten (EXIF-Zeit + Sonnenstand + Schatten auf Boden), Schienenspur 1000 mm (Freiburger Strassenbahn) und Kfz-Kennzeichen 520 mm (Detektoren fehlen), Zollstock/Latte bei eigenen Aufnahmen (Nutzeraktion), Mapillary-GPS im Netz (39 Fotos, noch nicht gematcht), Dokument-Hoehen (nur Handwerte).

## BQ - Videos als Datenquelle (Drohne/Boden), Stand 2026-11-02 abends (Uebergabe)
**Kontroll-Nullstart mit Standard 1000 px (`--stufe auto`)**: Lauf 37, 59/69 bestanden, im Bereich der Serie (56-66 von ~70). Sweet Spot 1000 px (Leiter 800/1000/1200/1600 = 50/58/54/48 von 61 gemeinsamen).
**Suche:** `yt-dlp ytsearch` mit 7 Anfragen -> 95 Kandidaten; Metadaten (Lizenz, Aufloesung) in `/media/oem/scan/rc-park_daten/martinstor/video_suche/` (kandidaten_roh.txt, meta.txt, auswahl.txt). Register-Zeile "keine Orbit-Drohnenvideos" (Eintrag davor) stimmt so nicht mehr: es gibt Nahflug-Drohnenclips.
**Drohnenclips (Black Forest Stock, 720p, je 15-25 s, Wasserzeichen 'BLACK FOREST' fest in Bildmitte, Kreis r ~7,5 % der Breite):** `o34426Ez5_U` (weit), `ua1sX3MMh9A`, `VEN1zf__KgI`, `RBC7Co30Vkc` (Nahfluege: Uhr, Tuermchen, Helm, Nadel aus mehreren Hoehen = die Luecke 45-65 m der Abdeckung). NICHT Martinstor: `R7RIkxQNOyE` (Schwabentor/Muenster), `6RTrYMs_kYE` (Drone Biker, Bertoldsbrunnen/Stadt). Bodenvideos 4K (Frames gezogen/werden gezogen): A_PUR2GXND0, F8y3lNgia5c, GqT9VMxXsu0 (Fall: 519 MB), jEQJGdvZ26U, XlAlc_fVqbg, pFa0tRoSp1U, qJhibdDzqcI, h792HhnMgR8, LSi6HGXqmiY, gjVSpDSd8rU, hcWCTjNOnng.
**Frames:** `tools/video_frames.py --fps 3` -> `/media/oem/scan/rc-park_daten/martinstor/video_frames/<id>/vf_*.jpg` (+manifest.json). Sichtprobe (Kontaktbogen) angesehen.
**`tools/video_sfm.py` (neu):** COLMAP mit MASKE (mask_path, <bild>.png) fuer feste Einblendungen, eine Kamera je Clip, SIMPLE_RADIAL. Lauf `d1` (4 Clips, ~220 Frames) lief bei Uebergabe seit >15 min ohne Ergebnis (nvidia-smi 0 % -> vermutlich CPU-SIFT/Matching; Device.auto prueft nicht). Ausgabe `/media/oem/scan/rc-park_daten/martinstor/video_sfm/d1/ergebnis.json`.
**Offen / naechste Schritte:** (1) d1 auswerten (Registrierung je Clip, ob Clips verschmelzen, Reproj.); falls zu langsam: GPU erzwingen (`Device.cuda`) oder Frames auf ~80 begrenzen. (2) Drohnen-Netz massstabsfrei gegen das Nullstart-Modell ausrichten (Aehnlichkeitstransformation, 4 Tuermchen + Uhr) -> Form-/Verhaeltnispruefung Helm, Nadel, Dach (Residuen je Hoehe). (3) Bodenvideo-Frames filtern (Treffer am Turm), Extranetz, Dichte der Wolke > 45 m messen. (4) Weitere Massstaebe: Schienenspur 1000 mm (Strassenbahn) in Drohnen-/Bodenframes ueber `foto_mass.py`-Protokoll; Verhaeltnisse (Schlankheit, Tuermchenabstand/Turmbreite). (5) Detailkatalog + `tools/detailbudget.py` (Plan `modelle/PLAN_DETAILGETREUE.md`). Lizenz: nur private Messvorlage, Eintrag in LIZENZ_WERKZEUGE.
**Nutzerhinweis (Uebergabe):** Absoluter Massstab zweitrangig (Endgroesse spaeter skalierbar); wichtig sind alle Details >= 7 cm und Proportionen. Daten soll Claude SELBST holen (Videos, Frames), keine Foto-Touren verlangen.

## BR - Drohnenwolke einpassen: Entzerrung, Clip-Kippen, Doppeldach (2026-11-03)
**Anlass:** Nutzer sah in der 3D-Ansicht die Drohnenwolke ~0,5-1 m versetzt ("schwebt") und ein zweites paralleles Dach davor.
**Messungen (alle an `video_sfm/d1`, 1,86 Mio Punkte, Nullstart-Strassenwolke):** (1) Strassenwolke ist nach `wolke_vs_modell --entzerren` hoehenabhaengig in x verschoben (+0,04 m bei z<10 bis +1,13 m bei 40-50; Drift 30,8 mm/m, aus dem GENERATORMODELL gefittet = zirkulaer). Die Drohnenwolke liegt im unentzerrten Rohrahmen: gegen Roh passt sie bis 32 m (<0,12 m), gegen entzerrt 0,65 m konstant. (2) Unabhaengige Pruefung am Laser: DOM1-Spitzenzellen x -0,26..0,01 (+-0,5); entzerrte Strassenwolke z>=55 x=+0,07, Roh -1,57, Drohne roh -1,49 -> die Entzerrung wird vom Laser gestuetzt, die Rohausrichtung der Drohne erbt die Neigung des Rohnetzes. Drift-Korrektur auf die Drohne: Spitze x=+0,06. (3) Doppeldach: Abstandshistogramm senkrecht zur RANSAC-Dachebene bimodal (Hauptpeak scharf, zweite Schicht 1,2-2,4 m davor, auf allen vier Dachseiten). Sichtbarkeitsdatei `fused.ply.vis`: Hauptschicht 81 % Clip ua1sX3 (+VEN1zf), Vorschicht 76 % Clip RBC7Co. Clip RBC7Co kippt im Gesamt-SfM: Rest-Versatz zur Strasse +0,08 (z14-32), +0,90 (32-48), +2,07 (48-70); o34426 oben -2,1; VEN1zf 48-70 -0,67; ua1sX3 <= 0,32.
**Werkzeug:** `tools/video_merge.py` jetzt: Drift-Korrektur wie Strassenwolke, Clip-x-Hoehenband-Konsistenz (dominanter Clip >= 80 % Sichten, getrimmter Translations-ICP, Verwerfen bei |dx| > 0,5 m), Rest-ICP (Nordsetup: -0,36 m x, +0,19 m z; NN-Median 0,36 -> 0,14), Abbruch bei NN > 0,3 m; Bericht `audit/video_versatz.json`. `video_dicht.py` schreibt `punkt_clips.npy/json`. Fehlerkorrektur: `--zurueck` stellt jetzt auch die Farbdatei wieder her.
**Videostufe mit/ohne (gemeinsame Pruefungen, ein Netz, Einzellaeufe, Streuung bis 5 m!):** ohne 57/67, Video unkorrigiert 59/67, Video mit ICP-Verschiebung 61/67; schlechter blieben Ecktuermchen-NE-Achse, Helm tief, Tuermchen-Durchmesser 37,75. Nicht als Beleg gewertet.
**Offen:** Nutzer: Dach sei danach "extrem gut", seitlich passend, nur etwas nach vorn und zu tief (stimmt mit Rest-ICP -0,36/+0,19 ueberein). Entzerrung der Strassenwolke bleibt generatorabhaengig - Ersatz durch amtliche Flaechen (LoD2/DOM1/Lot) in Recherche; stueckweise statt Verwerfen; nur Nordseite; pruefstand-Zeile fuer `video_versatz.json` und `beleg()` fehlen; 3 Recherchen laufen (Registrierung, Ebenen/Fusion, amtliche Zwangsbedingungen).

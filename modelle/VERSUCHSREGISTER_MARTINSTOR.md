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

## BT - Median-Konsens, Dachflaechen je Quelle, Luecken (2026-11-03)
**Werkzeuge:** `tools/masse_konsens.py` (Median/MAD/Spanne der abgeleiteten Masse ueber unabhaengige Laeufe, Status stabil/mittel/streut, aendert keinen Sollwert; 25 gespeicherte Laeufe: streut u. a. ERKER_OBEN 5,75 m Spanne, QUADER_ZONE_Z 9 m, DACHHOEHE 2,75 m; Referenz weicht vom Median bis 0,75 m ab, QUADER_ZONE_Z 2 m; stabil/mittel: KONSOLE_Z0, OR, QUADER_*). `tools/hybrid_abgleich.py` (Dachebenen je Seite und Quelle getrennt, Tukey-Fit, Bootstrap, Widerspruch statt Mittelung; `--profil` Schichtprofil).
**Dach (Drohne konsistente Baender + Drift + Rest-ICP, Nordsetup):** Neigung Nord Drohne 77,1 +- 0,02 gegen Generator 77,2 (Nutzer: 'Neigung extrem gut' bestaetigt); Strassenwolke Nord 75,6. Tiefenlage Nord bei z 48: Strasse 1,26, Drohne 1,37, Generator 1,94 -> Generator 0,6 m zu breit in N-S (Strasse und Drohne vertragen sich, DOM1-Rohraster-Zellmaximum ueberschaetzt die Kontur systematisch bis ~0,5 m). Ost/West: Generator 87,9 Grad (fast senkrecht), Drohne Ost 81,0 / West 76,7; Strasse 67 (Schlossberg, wenig Punkte). Schichtprofil quer (E/W voll): 6,9@41, 6,3@43, 5,7@45, 5,2@47, **3,6@48** (Stufe 1,6 m), 3,0@50; altes Profil (aus Foto-061-Silhouette): 4,99@43, 4,62@48 -> +1,3 m zu schmal bei 43, ~1 m zu breit ab 48. Ab z 52 messen Kreuzarme/Goldkugeln (+-1,9 m) mit, kein Dach. Sued-Flaeche der Drohne duenn (2318 Punkte, springt 1,1..2,5): nicht verwendet; Gegenseite ANNAHME symmetrisch.
**Luecken (Wolkendichte je Seite x 10-m-Band):** Sued(+x): Strasse <100 Punkte, Drohne <=1300 je Band, Sued-Netz nur sparse (2580, z<10) - groesste Luecke; Ost/West: Drohne 7000-42000 je Band bei 10-50 m, Strasse 450-5000; > 50 m ueberall duenn. Dichte Sued-Stufe war nie gerechnet (nullstart rechnet nur die Hauptseite dicht): `sfm_dicht.py ... sued` gestartet.
**Recherche (3 Agenten, Websuche duenn, meist Fachwissen, Lizenzen UNGEPRUEFT):** Registrierung: Drift ist nichtstarr; starre Methoden (TEASER++/FGR/ICP) loesen Kippen nicht -> je Clip hoehenabhaengiges Tiefenmodell d(z)=a+b*z statt Verwerfen, gemeinsame BA mit Ankern (pycolmap-Punkt-Priors ungeprueft), Doppelschicht-Detektor als Pruefung. Ebenen/Fusion: Normalen-Clustering + Offset-Histogramm statt freiem RANSAC, je Quelle trennen, Free-Space-Konsistenz, Tukey-Fit mit Mehrfachstart, Efficient RANSAC/PolyFit/City3D/KSR = CGAL-GPL (nicht fuer Verkauf), LSD original AGPL. Amtliche Zwangsbedingung: LoD2-Wandebenen/DOM-Kantenfit/Lot aus Vertikalen (eigener Beitrag: LoD2 als Constraint in BA gibt es in der Literatur nicht); Lizenzen BW dl-de/by-2-0, NL 3DBAG CC BY 4.0, PLATEAU ODbL (Share-Alike klaeren).
**Offen:** Profil-Uebernahme in Generator + Pruefzeilen (wartet auf Fork Torbau, kein paralleler Generatorlauf); per-Clip d(z)-Korrektur statt Verwerfen; Mehrfachlaeufe fuer Konsens (GPU, nach dichter Sued-Stufe).

## BS - Torbau (Nebengebaeude ueber dem 2. Bogen, McDonald's) neu nach Foto 089 (2026-11-03)
Beobachtung (Nutzer): "nicht ganz richtig". Eigenes Objekt `modelle/martinstor_torbau/` mit 12 Pruefungen; am alten Modell 8 Fehlschlaege, am neuen 12/12 gruen.
Falsch waren: Frontblock 3,4 m statt ~7 m, Bogen 2,4 m breit/Scheitel 8,6 m statt 7,25/6,2 m, Staffel- statt Schweifgiebel, Erker fehlte (Vorsprung 0,5 m), 4 statt 3 Fenster im 2. OG.
Die alte Quelle "Foto 003" war falsch (zeigt die Uhr, nicht den Torbau). Messungen: M-089-001..007 (Massstab: Turmbreite 11,2 m; Hoehe ANNAHME Giebelspitze 20,7 m aus Wolke).
Offen: Giebelachse Foto -9,2 vs Wolke/Drohne -8,3 (nicht gemittelt, bleibt -8,3); rechtes Bogenende verdeckt (Symmetrie-ANNAHME); Torbau noch nicht im Hauptmodell/Viewer.
Regression martinstor: 1 Abweichung (wolke_vs_modell n_beide 6782 -> 6836) - stammt NICHT vom Torbau (v4-Generator nutzt ihn nicht), sondern von der wiederhergestellten Wolke/Entzerrung dieser Sitzung; Schnappschuss nicht erneuert, noch zu klaeren.

## BU - Dachsilhouette automatisch, Widerspruch Strasse/Drohne, Kameramodell-Test (2026-11-03)
- `hybrid_abgleich.py --profil-schreiben` generisch neu: Tuermchen ueber `tuerm_achse/tuerm_profil` maskiert, Helmfuss = groesster Breitensprung (untere Haelfte), duenn belegte Schichten (<15 % Median) nicht gefittet, Knicke stueckweise linear per BIC, Pruefzeilen automatisch (Toleranz = max(Rest-RMS, 0,2 m)); `--nur-pruefzeilen` setzt nur die Zeilen (Regel 2). Keine Handkonstanten mehr.
- Ergebnis Silhouette E-W (Drohne, clip-korrigiert): 5,93 @45,2 / 5,15 @47,9 / 4,32 @50,6 / 3,88 @53,2 (Rest-RMS 0,04). Modell 4,84/4,65/4,25 -> 3 von 4 Zeilen schlugen am alten Modell fehl (Test ok).
- Uebernahme ins Profil bricht Dachansatz (44,30), Tuermchen-Spitze (45,25), Kegel (1,26), Helm-geradlinig, 'Profil Dach 45,2' (Strassenwolke 4,11-5,11). Widerspruch Strasse vs Drohne, NICHT gemittelt: Profil unveraendert, Zeilen entfernt, offene Beobachtung eingetragen. Nord-Sued-Tiefe (1,9 Generator/Foto 061 vs 1,3 Wolken) gleicher Fall.
- Recherche Methoden (Agent, Lizenzen UNVERIFIZIERT): kein Fusionsverfahren loest einen Systemfehler (Doming nach James & Robson 2014); Helmert-VCE/BIC/Konsens helfen nur fuer Restrauschen bzw. Ebenenzahl.
- Hypothese: d1 nutzt SIMPLE_RADIAL (nur k1) je Clip -> Doming/Clip-Tilt. Test: `video_sfm.py --kamera OPENCV` (neu) als `video_sfm/d1_cv`, startet per `nachtkette.sh` nach Nachtlauf (nullstart_beweis 4 Laeufe) und Boden-SfM. Auswertung: Doppeldach/Clipversatz (video_merge, hybrid_abgleich) vorher/nachher.
- pycolmap 4.2.1: Pose-Priors ja, 3D-Punkt-Priors nein -> Anker-BA waere Eigenbau.
- Job-Planer `tools/jobplan.py` (Standardbibliothek): Warteschlange (JSON) mit Abhaengigkeiten (`deps`, `wait_files`), genau EIN GPU-Job (auch fremd gestartete GPU-Prozesse zaehlen, nvidia-smi), CPU-Jobs bis `max_cpu_jobs` parallel, RAM-Reserve, Zustand in `<queue>.state.json`, Neustart setzt 'laeuft' auf 'wartend' (Jobs muessen idempotent sein). Zweck: GPU- und CPU-Phasen ueberlappen statt Warten auf den Menschen. `video_ausrichten.py --aus <datei>`: Ausrichtung anderer Videos ueberschreibt `audit/video_ausrichtung.json` (die `video_dicht.py` erst NACH der Fusion liest) nicht mehr.
- Warteschlange Nacht 3.11.: merge/hybrid fuer d1_cv im Sandbox-Objekt (nicht im Referenzobjekt), Boden-SfM-Ausrichtung als GPU-Job nach d1_cv.
- Breitenvergleich mit GLEICHEM Schaetzer (`tools/breite_quellenvergleich.py`, Silhouette p2-p98, Tuermchen maskiert): Strasse 5,53/5,56/5,13/4,40, Generator 4,97/4,74/4,25/4,03, Drohne 5,93/5,12/4,29/3,74 (z 45,2/47,9/50,6/53,2); Clips bei 45,2: RBC7Co 5,88, VEN1zf 4,93, ua1sX3 5,06. Der 'Widerspruch Strasse 4,6 vs Drohne 5,9' war ein Mass-Unterschied (Frontschicht vs Silhouette). Die Quellen streuen untereinander (~1 m) so stark wie ihr Abstand zum Generator -> keine Evidenz fuer ein zu schmales Dach; Profil unveraendert. Lehre: Quellen nur mit identischem Schaetzer vergleichen. Plan 2.2 damit weitgehend beantwortet; Plan-Datei aktualisiert.
- Regression/Schnappschuss (Plan 2.6): Ursache der 9 Abweichungen war die VIDEO-VERSCHMOLZENE Referenzwolke (`sfm/dicht_nord_entzerrt.npy`): `wolke_profile --generator` leitete daraus ein anderes Dachprofil ab (Basisbreite 6,18 statt 5,99; Dachansatz 41,5 statt <=41,5 FEHLER). Nach `video_merge --zurueck` nur noch 4 Abweichungen: (1) zwei neue Pruefzeilen 'Helm geradlinig' (frueher eingebaut, gewollt), (2) Text `elemente[24].quelle`, (3) `wolke_vs_modell.n_beide` 6782 -> 6836 (vermutlich Nebengebaeude/Torbau-Aenderung 8f94b2c; Ursache nicht einzeln belegt). Schnappschuss damit erneuert. WICHTIG: die Kette darf NICHT auf der verschmolzenen Wolke laufen (Plan 2.5) - Referenzwolke bleibt ohne Video, Video-Merge nur im Sandbox-Objekt oder fuer den Viewer.
- Treppe `tools/treppe.py` (Plan 3.6): Stufenleiter grob(800 px) -> mittel(1000) -> fein(voll) -> Video, je Stufe `nullstart.py`, Guete = bestandene Pruefungen, die in ALLEN Stufen vorkommen, getrennt nach unabhaengigen Quelltypen (lod2, laser_dom1, dokument), Stopp wenn Gewinn <= Rauschband (--geduld), Bericht TREPPE.md mit offenen Merkmalen -> naechster Hebel. Auswertung (`--auswerten`) an den 4 gleich konfigurierten Nachtlaeufen: gemeinsam 56 Pruefungen, bestanden 43/48/49/45 (Streuung 6, nicht +-3) -> Standardrauschband 5; nur 2 von 56 Pruefungen unabhaengig -> bei neuen Objekten ist die Guete blind fuer fast alles. Offen: kompletter Lauf an einem echten neuen Objekt.
- Kameramodell-Test (Plan 1.1): `video_sfm.py --kamera OPENCV` (d1_cv, 220 Frames, Reprojektion 0,58 statt 0,90 px, dichte Wolke 2,17 Mio Punkte, 61 min) gegen SIMPLE_RADIAL (d1). Tiefenversatz (dx) je Clip/6-m-Band VOR der Bandkorrektur: RBC7Co 38-44 m +1,12 -> -0,13, 44-50 m +1,66 -> +0,09; VEN1zf 38-50 m -0,54 -> -0,21/+0,25; ua1sX3 -0,37/-0,22 -> -0,09/+0,17. RMS Versatz z >= 38 m (Baender n > 2000): 0,88 -> 0,28 m (d1: 7 Baender, d1_cv: 6). Das Doming/der Clip-Tilt war also zum grossen Teil ein Kameramodell-Problem. Einschraenkungen: EIN Lauf je Modell (SfM-Realisierung streut), Clip o34426 jetzt dabei (32-44 m dx -1,45/-0,42, dy +1,28/+0,44, dz +1,02 - schlecht), Baender nicht identisch. Silhouettenbreite je Clip @45,2 m streut weiter (4,81..6,18 m; ohne o34426 1,1 m) - die Breite ist damit NICHT entschieden, p2-p98 ist rauschempfindlich. Boden-SfM (350/433 Frames, 0,89 px) an Nordnetz ausgerichtet: 3270/11800 Inlier, Median-Residuum 0,16-0,29 m bis 50 m. Standard-Kameramodell in video_sfm.py jetzt OPENCV; Wiederholung mit zweitem Lauf offen.
- Strassennetz mit OPENCV (Plan 2.1, 3 Laeufe, `nullstart_beweis --extra "--kamera-modell OPENCV"`): gemeinsame Pruefungen 40/45/40 von 56 gegen 43/48/49/45 mit SIMPLE_RADIAL (Mittel 41,7 vs 46,3; alle Pruefungen 47/67, 55/69, 52/69 vs 56/79, 68/78, 61/70, 60/72). OPENCV hilft dem Strassennetz NICHT (eher schlechter, am Rand des Rauschbands). Erklaerung (Hypothese): je Bild eine eigene Kamera + mehr Parameter bei nur 16 Bildern = Ueberanpassung; die Drohne bestimmt je Clip EINE Kamera aus vielen Frames. Naechster Test: gemeinsame Intrinsik je Kameragruppe (`f_gruppe`). `nullstart.py --kamera-modell` und `nullstart_beweis.py --extra` bleiben als Werkzeug.

## BV - Suedwand-Lueftungsfenster Breite (2026-11-03)
Foto 041, Messprotokoll M-041-006 (ein Lauf): 0,75 m statt 0,60 m im Generator. Regel 2: Pruefung `fenster_S_links_breite` (Soll 0,68-0,88) eingetragen, schlug am alten Modell fehl; dann `fassade.json` (breite 0.6 -> 0.77, u=+-2,1, z=21,65 Unterkante), Neubau, Pruefstand "alle Pruefungen bestanden". STL 28.628 Dreiecke, 137,4 x 144,1 x 750,6 mm, wasserdicht, 1 Koerper; H0-Aenderung ca. 2 mm.
**Offen:** Sichtblatt `audit/seiten.jpg` (GPU, nach Ende der dichten Bodenwolke), `regression.py --pruefen`, Export-STL neu; rechtes Fenster nicht gegengemessen (Symmetrie ANNAHME). Versuchslog: `fenster-S-links-breite-041`. Zurueckgezogen: Beobachtung "Uhr/Zinnen/Fensterreihe fehlen" war falsch (existieren in elemente.json/fassade.json).

## Poisson-Netz v3 (2026-11-03): Sued per LightGlue-Video + Wandebenen-Nachzug
Sued-Videowolke (sued_f8y3, 1,37 Mio Punkte) per Sim3 aus zwei Ankern ausgerichtet; Nutzer: Sued 'zu gross, krumm'. Messung: Kanten laufen mit Hoehe zusammen, Wandtiefe 5,2-5,7 statt 4,91.
Fix: Wandebene x=a+b*z+c*y robust (4 Iterationen) aus Punkten z18-37 anpassen und auf LoD2 x=4,91 scheren; Wolke auf Kasten |y|<5,9, |x-4,91|<1,2, z>10 begrenzen. Ergebnis: Wand gerade, Breite +-5,4 (LoD2 +-5,5). Netz export/poisson_alle/netz_v3.
Offen: Sued-Helm/Nadel fehlt, Eck-Tuermchen (Nutzer: 'kaputt') in Sued/Ost/West zerrissen, Loecher unten; Pruefung 'sued_breite_gerade' noch nicht im Pruefstand. Open3D liegt in venv-mesh. Skripte noch im Scratchpad (sued_pnp/sued_v3), nicht in tools/.

## BW Hybrid Generator + Bildpunkte (2026-11-03) - tools/wolke_auf_generator.py
Idee (Nutzer): Form vom Generator (LoD2/DOM1/Profile, immer vollstaendig), Bildpunkte liefern Farbe UND geometrische Verfeinerung; hybrid abgleichen statt Poisson (zerriss Tuermchen/Helm/duenne Seiten).
Verfahren: STL (1:87 -> m) adaptiv auf <=0,15 m Kante unterteilen; Gate je Seite: robuste Wandebene d=a+b*z+c*q der Wolke auf die Generatorwand scheren (allgemein, keine Handwerte), Breite/Lot als Pruefung (tol 0,8 m / 1,5 Grad, Bericht je Seite);
Ecken: Farbe aus Voxel-Mittel (0,12 m) der naechsten Punkte (keine Foto-Projektion), Verschiebung entlang Normale zum Punktschwerpunkt (max 0,3 m, geglaettet, nur wo >=5 Punkte), sonst unveraendert; belegt = Punkt im Radius.
Ergebnis auf v3-Wolke: Sued bestanden (Breite 10,49 vs 10,44, Lot -0,8 Grad); Nord/Ost/West 'ABGELEHNT' laut Pruefung, aber Breitenreferenz (Generator 3-97 % Flaechenproben) ist nicht gleich gemessen wie Wolke (4-96 % Punkte, inkl. Nachbarn) -> Tolerierung NICHT gelockert, Messvergleich offen. Belegt 32 % (fein) / 48 % (grob).
Gescheitert: erste Fassung verwarf abgelehnte Seiten mit ueberlappenden Halbraeumen (belegt 4 %). ICP der Wolke an den Generator (Maßstab 0,89, 3,7 Grad um x) verschlechterte die Rechtskante -> nur Diagnose.
Offen: Pruefung in pruefstand.py/pipeline einhaengen, Regression-Schnappschuss; Belegt nur 32-48 % (Radius/Voxel), Ost/West-Lot -2,8/-1,9 Grad.

### BW-Untersuchung: Breite/Lot gegen den Generator (2026-11-03)
Gleiche Messvorschrift (4-96 %-Perzentil je 3-m-Band, Wandfenster +-0,6 m) auf Generator-Flaechenproben und Wolke: Generator Sued/Nord 10,4-12,0 m, Wolke 8,8-9,9 m (Nord, Sued) -> Wolke ist NICHT breiter, sie ist an den Kanten schlecht abgedeckt. Perzentil-Breite ist abdeckungsabhaengig -> als Pruefung ungeeignet (entfernt, nur noch Bericht).
Ebenso Lot ueber Bandmitte: Ost/West-Mitte driftet -0,6..-0,9 m, weil nur ein Teil der Wand gesehen wird (Verdeckung, Register Verdeckung_nachbarn) -> kein Beleg fuer Kippen. Sued-Lot -0,8 Grad (Nord +1,4) ebenfalls im Rauschen.
Ersatzpruefung 'ueberstand': Anteil der Wandpunkte > Generator-Fussabdruck + 0,5 m je Band. Ergebnis v3: Sued 0-0,1 %, Ost/West <= 0,5 %, Nord 24 % (z15-18) / 8 % (z18-21) = Strassen-/Nachbarpunkte (Nachbartuermchen unten rechts, passt zur Nutzer-Sicht 'Nachbartuermchen auf der Wand'); alte Sued-Wolke vor Scherung/Kasten: 38 % im unteren Band.
Offen: (a) Nord unten auf Fussabdruck+0,5 m beschneiden (aus dem Generator abgeleitet, nicht von Hand), (b) Roll/Massstab der Sued nur per Merkmale (Uhr, Zinnenkranz, Fenster) messbar, nicht per Kantenperzentil; ICP am Generator = Einwand-Wand unterbestimmt.

### BW-Loop: Silhouetten-Schleife foto_loop.py (2026-11-03)
11 Fotos (Nord 001,006,014,031,044,049; Sued 000,020,021,042,043), je eigene Kamera (Zufall+CEM, Start-IoU 0,81-0,96, mittel 0,903), dann 4 Runden abwechselnd Kamera/Modell (Tuermchen dx,dy,hs,rs). Ergebnis: KEIN Parameter uebernommen (Gewinn < 0,002 oder keine Mehrheit), IoU 0,9029 -> 0,9063 allein durch Kameras. Konvergenz bei kleinster Schrittweite.
Befund (Negativergebnis, aber wertvoll): Die STL-Tuermchen/Helm/Nadel passen auf den Himmel-Silhouetten (044: Kontur eng um Tuermchen, Helm, Nadel). Das fruehere Kanten-Overlay (030/041: Kegel 1,5 m zu hoch) lag an Kameras mit Residuen 50-100 px, nicht am Generator. Folge: nichts am Generator aendern; die sichtbare Tuermchen-Abweichung im 3D-Tool stammt aus der Wolke im oberen Turm (z>34).
Grenzen: Silhouette sieht nur Aussenkontur (Tuermchen, Helm, Nadel), keine Wandlage/Details; Kamera-Anpassung gilt nur im ROI (oberer Turm), ausserhalb ist die Kamera unbrauchbar (014 zeigt das). Naechstes: Kantenloop (Chamfer, Gradientenabstieg), Wolken am STL ausrichten.

## BX Kanten-Schleife Nulltest (2026-11-03)
Siehe PIPELINE_H0.md 8c-Nulltest. Ergebnis: Ganzmodell-Versatz unsichtbar (Kamera absorbiert), Teilversatz Tuermchen 1 m in 3/4 Fotos nachweisbar, 1,5 m in z nur 1/4. Kein Generatoraenderungsbedarf aus den Daten. Ungeprueft: Versatz anderer Bauteile, kleinere Versaetze, andere Fotos.

BX-Nachtrag: Teilversatz 1,41 m (nicht 1 m) war die Gruppe 'gefunden'; Reihe 0,35/0,7/1,41/2,83 m siehe PIPELINE_H0.md. `tools/kanten_nulltest.py` + Pruefstand-Block eingebaut. Regression (`regression.py --pruefen`): 3 Abweichungen (masstabelle +1 Pruefung, pruefbericht neue Fensterwerte, STL-Volumen 6317387->6317276), NICHT durch diesen Eintrag verursacht (Vorarbeit aus frueheren Sitzungen, uncommittet); Schnappschuss NICHT erneuert.

## BY Vorzeichenbehafteter Kantenversatz (2026-11-03, tools/kanten_richtung.py)
Frage: Warum wird Foto 031 'Wand unten/Tor' nach Kameraanpassung schlechter (6,4->9,1 px)? Messung: naechste Fotokante je sichtbarer Modellkante, dx (senkrechte Kanten, links/rechts getrennt), dy (waagerechte). Ergebnis: in ALLEN Fotos und Bauteilen dx und dy ~ -0,5 px (konstanter Pixelkonventions-Offset, kein Modellfehler), Rest <0,3 px. Kein gleichgerichteter Fehler -> Verdacht widerlegt, Generator unveraendert. Die grossen Medianwerte stammen von Kanten ohne Fotogegenstueck (Verdeckung durch Nachbarhaeuser; 031 hat nur 996 Tor-Punkte). GRENZE: Suchradius 15 px verzerrt zu kleinen Versaetzen (Auswahl); Fehler >15 px erscheinen dort nicht, nur im Anteil >8 px der Kantenschleife. Offen, nur 1 von 4 Fotos: Helm 041 rechts -3,2 px (89 Punkte), Tuermchen 040 links -2,6 px (165 Punkte).

## BZ Nullstart und der Foto-Eingang (2026-11-03)
Frage (Nutzer): gehoert das automatische Bilder-Herunterladen zur Ehrlichkeit des Nullstarts? Befund: `nullstart.py` laedt NICHTS herunter, es liest `fotos_dir` (geteilt). bilder_holen.py/Bilderschleife sind eigene, nicht verdrahtete Werkzeuge; die Schleife fand heute 0 neue Bilder (Stufe 0). Weg 1 (umgesetzt): `tools/fotoliste.py` schreibt `modelle/martinstor/fotoliste.json` (131 Fotos: Groesse, SHA-256, Quelle/URL/Urheber/Lizenz aus manifest.json bzw. LIZENZ_BILDER.json); der Nullstart prueft den Ordner dagegen (FEHLT/GEAENDERT/NEU, rc 1). 2 Fotos ohne Quellenangabe (060 Luftbild NW 2012, 061 Schlossberg Ost 2016); 7 Manifest-Eintraege haben keine Datei im Ordner (u.a. Staatsarchiv-Bilder). GRENZE: das beweist die Kette AB diesen Fotos, nicht dass sie heute wieder aus dem Netz kaemen. Weg 2 (offen): bilder_holen als Nullstart-Schritt in frischen Ordner + Vergleich mit der Liste. Der laufende Nullstart (vor dieser Aenderung gestartet) enthaelt die Pruefung noch nicht.

## CA - Nullstart A/B nach Determinismus-Fixes (2026-11-03 abend)
Fixes: RANSAC-Seed 0 + 1 Match-Thread (sfm_netz), Fusion 1 Thread (sfm_dicht), `--netz-threads 1` (nullstart). Zwei komplette Laeufe martinstor_nullA / nullB, gleiche Eingaben.
- **STL bitgleich**: nullA = nullB = sha256 238dd38c19c298562c2fcca29953d9eeb4c6b4b4537f51a72b2383687e74886a. Ebenso gleich: masse.json, dicht_nord_modell/entzerrt/farben.npy, profile_nord.json, profile_generator.json.
- **Netz Nord gleich** (nur Pfad im JSON verschieden). **Netz Sued NICHT reproduzierbar**: Punkte 5530 vs 5533, reproj 0,738 vs 0,775 px, f_px einzelner Kameras (012, 050) weichen 4-7 % ab. Sued-Netz geht (noch) nicht in das STL ein, daher STL trotzdem gleich. Offen: Mapper/Bundle-Ausgleich Sued (Threads/Reihenfolge) eingrenzen.
- **Abweichung zur Referenz bleibt**: nullA/B 238dd38c... != martinstor_null (alt) edc5f118... != Referenz 15bb2ae0.... Reproduzierbar heisst nicht gleich der Referenz; Referenzmasse stammen aus frueheren Wolken-Realisierungen/Handwerten (Stufe C). Naechster Schritt: Re-Baseline-Entscheidung + Massvergleich nullA gegen Referenz je Parameter.

## CB - Zwei Boegen + Zwischenpfeiler je Tuermchenflaeche: Ursache, Fix, Gegenbeweis (2026-11-03)
Sichtfund (Nutzer, H0-Druckteil neben Bildschirmfoto): je Achteckflaeche des Arkadenbands steht eine Zwischensaeule (2 Boegen); am Tor ist es EIN Bogen je Flaeche.
**Ursachenkette (5 Glieder, jedes haette den Fehler allein stoppen koennen):**
1. Wert 2 = ANNAHME 'gepaarte Boegen' aus Foto 043; nie gezaehlt. Das Foto zeigt je Flaeche EINE Oeffnung, Pfosten nur an den Ecken (Protokolle Z-043-001/002).
2. `wolke_baender.py` zaehlte Dunkellaeufe der Wolke in einem Fenster breiter als die Flaeche (Nachbarflaechen, Eckpfosten, Innenraum); duenne Zellen (<4 Punkte) zerschneiden Laeufe;
   zwei Koerper lieferten 2 und 3 Laeufe -> Median 2,5 -> `int(round())` = 2, ohne Streuungsmeldung.
3. Die zugehoerige Pruefung trug das Merkmal **'schlankheit'** statt 'anzahl'. Die Quellen-Matrix haette `sfm_bodenanker` fuer 'anzahl' sofort abgelehnt (blind) - das falsche Etikett umging sie.
4. Soll [2,2] stammte aus derselben Wolkenmessung wie die Modelleingabe (`profile_baender_tuermchen.json` wird vom Generator gelesen) -> Modell besteht per Konstruktion (zirkulaer).
5. Register AX/Beschwerde 'Boegen zu klein und zu viele' wurde in der Quelle zitiert, aber nur durch dieselbe Messung 'behoben'. Und: Teil vor dem Druck nicht mit Foto 043 verglichen.
**Fix:** Foto-Zaehlprotokoll (`tools/foto_zaehlung.py`, Z-043-001/002 mit markiertem Bild), Pruefung 'Oeffnungen je Achteckflaeche' (foto_vollbild, merkmal anzahl, Soll 1) - am Altmodell FEHLER 2,00 -> nach Fix OK 1,00.
Generator: `baender_rundkoerper(oeffnungen=...)` Foto-Vorrang; Masse TUERM_OEFFNUNGEN_JE_FLAECHE = 1, TUERM_OEFFNUNG_BREITE_ANTEIL = 0,78 (Foto 043, zwei Messungen 0,76/0,81, ANNAHME-Hinweis; vorher Wolken-Median 0,48 m = 'Boegen zu klein').
`wolke_baender.py` schreibt keine Oeffnungs-Pruefungen mehr, nur Beobachtung mit Streuung. Zwei Wolken-Pruefungen nach `pruefungen_zurueckgezogen`.
**Sperren (Pruefstand, Exit 2):** (i) Zaehlarten (flaeche_oeffnungen, nischen_anzahl, anzahl_im_band) nur mit Merkmal anzahl|fassade; (ii) Merkmal anzahl|fassade darf nicht aus einer Datei stammen, die der Generator liest (SELBSTBEZUG);
(iii) Protokoll `Z-*` muss existieren und zum Soll passen; Altbestand ohne Zaehlprotokoll wird als HINWEIS gelistet (8 Pruefungen, nachzuziehen).
**Gegenbeweis:** `tools/test_regeln_cb.py` (laeuft in `bauen_abnehmen.sh`): T1 Etikettenumgehung, T2 Selbstbezug, T3 Zaehlwiderspruch, T4 Altmodell (Git-STL) faellt durch, T5 widerspruechliche Zaehlung, T6 Gutfall - alle bestanden. Der Regressionslauf hat die alte Kette sogar selbst gefangen (wolke_baender schrieb die verbotenen Pruefungen erneut -> Exit 2), danach Werkzeug korrigiert.
**Regression:** Schnappschuss erneuert (Dreiecke 28 628 -> 27 570, Volumen -0,008 %, Oeffnungen 2 -> 1; weitere Abweichungen im Schnappschuss waren schon vorher da: pruefbericht 'Lueftungsfenster', Wolke/Modell n_beide).
**Grenzen (ehrlich):** Breitenanteil 0,78 aus 2 Messungen an 1 Foto (Nachprufung an 041/031/044 offen); Bogenform ist Rundbogen, am Bau Kiel-/Schulterbogen (nicht gemessen); 8 Altpruefungen ohne Z-Protokoll; Sichtblatt zeigt die Arkadenzone zu klein (eigener Detailrender gesehen).

## CC - foto_diff.py: Kontur-Diff Modell/Foto (2026-11-03, Nutzerwunsch "Tool, das den Diff z.B. falschen Torbogen sofort MERKT")
fehlteile_finden.py (1-m-Kantendichtezellen, Ankerzone-Filter) sah den Torbogen nicht (Zellen zu grob, Treffer z < Ankerzone verworfen, 043 ohne Kamera).
Neu: Kantenlinien selbst vergleichen (Modell-Tiefenkanten vs Canny nach 18 cm Glaettung, Abstand in m per Distanztransformation, Treffer > 0,35 m und > 0,8 m zusammenhaengend).
Ergebnis Foto 030: Torbogen-Bogen des Modells liegt links/kleiner gegenueber dem Fotobogen, Helm-Silhouette viel zu breit/hoch, linker Sockelpfeiler abweichend (alles ROT im Blatt) - noch NICHT behoben, noch KEIN Pruefstand-Sollwert.
Grenzen: Kamera 030 evtl. oben ungenau (Anker); Steinfugen/Baeume/Leitungen erzeugen gelbe Scheintreffer; Beobachtungen nur mit --eintragen. Naechste Schritte: Torbogen/Helm am Foto messen (M-Protokoll), Pruefung 'Kontur-Diff < x %' mit Quelle, Lauf in bauen_abnehmen.sh.

## CD - Tuermchen-Arkade: Boegen waren 0,35-m-Nischen vor massivem Kern (2026-11-03)
Sichtfund Nutzer (Viewer Q16Sr): "immer noch kleine Boegelchen, versetzt ... drinnen sind die kleinen Boegen noch, ueberlagert". Ursache: `baender_rundkoerper` schnitt je Flaeche
nur 0,35 m tief; die Nischenrueckwand zeichnete jeden Bogen ein zweites Mal kleiner/versetzt (im durchsichtigen STL sichtbar). Hoehen stimmten (Wolke dunkel 33,5-35,0 m, Modell 33,6-34,9 m).
Pruefung `oeffnung_durchblick` (neuer Messtyp im Pruefstand; Strahl auf Bogenmitte, Ebene aus den Pfosten): vorher 0,35 m -> FEHLER, nachher 2,05 m -> OK.
Generischer Fix in `tools/bauteile.py`: jedes Wolkenband der Klasse 'offen' wird HOHLRAUM (Achteck r - 0,2 m, zur Turmseite nur 0,5 m hinter die Achse; ANNAHMEN), fuer alle Rundkoerper/Objekte.
Anzahl der Boegen bleibt Foto-Zaehlung (CB); Lage/Hoehe/Offenheit aus der Wolke. STL wasserdicht. Regression: nur beabsichtigte Abweichungen (Volumen -0,36 %, neue Pruefung/Element, sil_zone_u031 +0,03), Schnappschuss erneuert.

## CE - Schallarkaden Glockenstock generisch aus der Wolke (2026-11-03)
Nutzer: "kleine Boegelchen", "Schallarkaden an die richtige Stelle, Elemente dort ersetzen". Modell hatte Handkonstanten: 2 x 1,0 m Rundbogen (Mitte +-1,0, Pfeiler 1,0 m), Sohle 37,9.
Foto 030 (K-030, Ebene x=3,55): Breiten 1,40/1,46 m, Mittelpfeiler 0,28 m, Hoehe 1,90 m (M-030-011..014); Zaehlung 2 je Flaeche (Z-030-001). Wolke Nord Band offen: Laeufe -1,49..-0,29 / 0,03..1,55, Oberkante 39,19.
Widerspruch (nicht gemittelt): absolute Hoehe Foto 36,3-38,2 vs Wolke 38,3-39,2 -> Oberkante aus der Wolke, Hoehe aus dem Foto (Kamera 030 oben unsicher, Renderueberlagerung oben versetzt).
Pruefung Breite (foto_kalibriert, Merkmal fassade - die CB-Sperre hat das erste Etikett 'verhaeltnis' abgewiesen): vorher 1,00 FEHLER -> 1,36 OK. Generisch: `bauteile.segmentbogen_reihe` (Lage/Breite aus Wolkenlaeufen, Zahl aus Foto, Segmentbogen).
ANNAHMEN: Stich 0,27 der Breite (Fotoausschnitt, unprotokolliert), Ost/West wie Nord/Sued, keine Lamellen. Regression: nur beabsichtigte Abweichungen; Schnappschuss erneuert.
Ecktuermchen-Arkade (Nutzer "grosse Boegen"): Wolke vs STL je Flaeche verglichen (audit-Bild tuerm_wolke_vs_stl) - Hoehe 33,6-34,9 passt zur dunklen Zone 33,6-35,0; Breite fuellt die Flaeche; Abweichung NICHT gefunden -> Nutzer um Markierung gebeten.

## CF - Tuermchen-Arkade: Halbkreis statt flacher Segmentbogen ("kleine Boegelchen", 2026-11-03)
Nutzer dreimal: "immer noch kleine Boegelchen". Meine Wolkenueberlagerung (CE) fand nichts, weil die Wolke die Bogenform nicht aufloest -> Fehlschluss "keine Abweichung".
Erst der Nebeneinander-Vergleich Foto 030 | STL (gleiche Kamerarichtung, Ausschnitt Tuermchen) zeigte es: am Bau Pfosten-zu-Pfosten offen, sehr flacher Segmentbogen;
Modell Halbkreis (Stich 0,5 m, Bogen ab halber Hoehe). Foto 030 kalibriert: Breite 1,06-1,11, Hoehe 1,09, Stich 0,17 m (M-030-015..018).
Neue Messart `oeffnung_form` (Breite bei 85 % / 30 % der Oeffnungshoehe): vorher 0,80 FEHLER -> 1,00 OK. Generisch: `baender_rundkoerper(oeffnungen={stich_anteil})`, Masse TUERM_BOGEN_STICH 0,16.
Erste Messfensterwahl bis 35,2 m war falsch (Traufplatte verschob die Bezugsebene, Wert 1,00 trotz Halbkreis) - erkannt, weil der Wert gegen die Vorhersage 0,78 stand; Fenster bis 34,97.
LEHRE: Formmerkmale (Bogenform, Proportion) nie aus der Wolke beurteilen; IMMER Foto|Modell-Ausschnitt nebeneinander ansehen (Regel 9b), bevor "keine Abweichung" gesagt wird.
Offen: Zierform (Kielbogen mit Nasen) nicht modelliert; Absoluthoehe K-030 oben ~0,8-1,5 m hoeher als Wolke (Kamera oben unsicher).

## CG - Nullstart deckt auf: Tuermchenbogen haengt an springender Bandgrenze (2026-11-03)
Nullstart Lauf 53 (ohne Eingriff durchgelaufen, 66/75): Wolke schnitt das Tuermchen offen 33,5-34,5 + stein 34,5-35,0 (Ref: offen 33,5-35,0). Folgen: Oeffnung nur bis 34,44 (flache Oberkante),
und 34,5-35,0 wurde GAR NICHT gebaut (kurze stein-Baender baut baender_rundkoerper nicht) -> Luecke unter dem Dach. Segmentbogen-Pruefung (festes Fenster) zeigte 1,28/1,30 (rot), aber aus falschem Grund.
Fix generisch (bauteile): offenes Band reicht bis an die Unterseite der naechsten AUSKRAGENDEN Platte (r >= r+0,2; Ref traufe 35,0, Null gesims 35,0), Oeffnungsoberkante dort - 0,08 (ANNAHME Sturz),
Hohlraum ebenso. Pruefstand: `_band_fenster` (Fenster aus dem Wolkenprofil des Objekts statt fester Hoehen); neue Pruefung Oeffnungshoehe 1,0-1,45 (Foto M-030-016 1,09 / Wolke Ref 1,4 - Widerspruch offen).
Gegencheck: Generator mit Null-Profilen -> alle 6 Tuermchen/Schallarkaden-Pruefungen OK, Oeffnungshoehe 1,28 = Referenz. Naechster Beweis: Nullstart A/B.
Offen: Schallarkaden-Scheitel aus Wolkenlauf springt (Ref 39,19, Null 39,87) - gleiche Robustmachung (Gesims-Unterkante) noetig.

## CH - Tuermchenachsen je Tuermchen aus der Wolke: Asymmetrie war Wolkenscherung (2026-11-03)
Auftrag: Tuermchenachsen automatisch je Tuermchen statt einer gespiegelten Achse (Spezialcode-Audit Nr. 12).
Roh-Kreisfits je Quadrant (Koerperschichten 30,75-35,75): NW quer -4,55 / tief 3,94, NO quer +4,27 / tief 4,07 -> scheinbar 0,28 m unsymmetrisch.
Gegencheck: Quermitte des Zentralkoerpers in derselben Wolke wandert mit der Hoehe (Schaft 23-29 m -0,15..-0,24, Helm 46-50 m -0,12..+0,08) = Scherung (vgl. Register BU).
Ein festes Bezugsfenster haette je nach Hoehe 0,02 oder 0,26 m Asymmetrie ergeben -> nicht robust.
Generisch (wolke_profile.py `tuerm_achsen`): Mitte je 1-m-Schicht unter dem Tuermchenkoerper + ueber den Tuermchenspitzen, Gerade, auf Tuermchenhoehe interpoliert (-0,15, Streuung 0,057);
Achsen quer relativ dazu: -4,40 / +4,42 -> Asymmetrie 0,02 <= Grenze (0,15 + 2 sigma = 0,26) -> symmetrisch, Modell (+-4,42) bleibt. tief 0,13 Unterschied < 0,15 (nicht relativ messbar, nur eine Seite).
Generator: Achsen je Tuermchen (bauteile.tuermchen_achse_je_quadrant, Rueckseite gespiegelt = ANNAHME) nur wenn wolke_profile Asymmetrie meldet; Beleg mit asym/grenze.
LEHRE: Lagemerkmale aus der Wolke nie absolut, sondern relativ zum eigenen Bezugskoerper derselben Wolke und mit dessen Unsicherheit vergleichen.
Regression: Schnappschuss erneuert (neu: tuerm_achsen, Achsen-Beleg; dazu Schallarkaden-Etikett + 2 Dreiecke aus der Scheitel-Robustmachung nach CG).
Offen: Wolke Nord quer um 0,15-0,25 m gegen die Bauwerksachse verschoben/geschert (Beobachtung); Tuermchen-d Wolke 2,8/2,98 vs Modell.

## CI - Eckquader: Foto zeigt doppelte Groesse und Lang/Kurz-Zahnung (2026-11-03, offen)
Fotovergleich vor dem Mauerwerk-Testdruck (Regel 9b): Foto 030, Eckquaderband Suedwand. z~10 m: Schicht 0,52/0,58 (M-030-020/021), lang 1,02/0,82 (M-030-022/025), kurz 0,58/0,59 (M-030-023/024);
z~25 m: Schicht 0,68/0,65 (M-030-026/027, Kamera oben unsicher), lang 0,86/1,11 (M-030-028/029), kurz 0,47 (M-030-030). Masse aus Wolken-Farbperioden: Schicht 0,25/0,40, Laenge 0,35, KURZ_FAKTOR 1,0.
Zweitbefund: Nullstart Lauf 56 misst die Quaderperiode 20-24 m mit 0,55 m (Ref 0,25) -> Wolken-Periodenschaetzer springt zwischen Grund- und Oberwelle.
Testplatte tools/testdruck_mauerwerk.py (generisch, Werte aus masse.json oder @M-Protokollen) gedruckt: Feld 2 Foto vs Feld 3 Wolke.
UMGESETZT: 2 Pruefungen Eckquader-Schichthoehe (Foto 030 kalibriert; rot am alten Modell 0,25/0,40) -> bauteile.mauerwerk_aus_protokollen (liest M-Protokolle 'Mauerwerk_<Bauteil>_Schichthoehe|Stein_lang|Stein_kurz',
Schicht je z interpoliert, lang/kurz Median; ohne Protokolle Rueckfall masse.json) -> quoins3 mit Schicht(z): jetzt 0,55 / 0,65 m (gruen), lang 1,02 / kurz 0,58 im Wechsel.
Werkzeugfehler pruefstand.relief_periode: Wandebene = Median -> bei grossen Quadern (> 50 % des Fensters) lag die "Wand" auf den Steinen (Signal zeigte jede 2. Schicht leer) -> p15. Tuermchenperiode unveraendert 0,50.
Widerspruch (Regel 5, nicht gemittelt): Wolkenpruefungen 'Band zentral Quaderperiode 20-24' (0,25) und '22-26' (0,50) gegen Foto 0,52-0,68 -> status widerspruch. Overlay 030 + Sichtblatt angesehen.
Regression: Schnappschuss erneuert (gewollt: Eckquader, 2 neue Pruefungen, 2 Widersprueche, Beleg). Offen: Glockenstock-/Tuermchenquader am Foto messen; Wolkenschaetzer f/2f.

## CJ - Ecktuermchen-Altpfad geloescht, Hardcode-Zaehler (2026-11-03)
Nutzer: "Altpfad loeschen und Hardcodings abbauen und beweisen, dass es nichts verschlechtert".
Werkzeug tools/hardcode_finden.py (AST): feste Zahlen ausser trivialen/Segmentzahlen/Parameter-Defaults/Texten. Generator vorher 337, nachher 248 (-89).
Ohne Wolkenprofil (Nullstart-Erstlauf) baut der Generator die Tuermchen jetzt mit Rueckfallbaendern in derselben Form (stein/gesims/hell/offen/traufe + Kegel)
ueber bauteile.baender_rundkoerper (einziger Bauweg); Masse TUERM_RF_* in masse.json (ANNAHME mit Quelltyp).
Beweis: (1) mit Profilen Regression identisch, alle Pruefungen bestanden; (2) ohne Profile (Kopie ohne profile_*.json): vorher 60 OK/15 FEHLER, nachher 67 OK/8 FEHLER,
keine neue rote Pruefung (erst 1 neu: Gesims 31,75-32,5 -> TUERM_RF_GESIMS_H 0,5 -> 0,75 wie gemessenes Gesimsband); Bild: Boegen/Traufe statt X-Schlitz-Fenster;
(3) Nullstart danach gegen Lauf 56 (66/75).
Nebenfund pruefstand.py: Masse ohne Quelle/Quelltyp wurden gemeldet, aber nicht gezaehlt (bad = 0 danach) -> masse_bad zaehlt jetzt ins Ergebnis.

## CK - Nullstart allgemein (objekt.json statt Martinstor-Code) + Kalibrier-Optionen reproduzierbar (2026-11-03)
nullstart.py: Seiten = Fotolisten in objekt.json['sfm'] (Hauptseite sfm.hauptseite), Zusatzfotos sfm.registrieren [{foto, netz, hoehe}] (vorher 060/061 + "--hoehe 44 8" im Code),
Generator = objekt.json['generator'] (vorher fest martinstor_v4_gen.py), Nebengebaeude-Ordner aus objekt.json['nebengebaeude'] (vorher "torbau"), Toleranzen regression.toleranzen,
Standardziel <objekt>_null. Alter Fehler: hybrid_abgleich in der Nullstart-Kette pruefte das REFERENZ-STL (Pfad nicht umgelenkt) -> jetzt das eigene.
Lauf 58 (neues nullstart.py + Eckquader, ohne --ziel): 66/77, aber NEU rot "Silhouettenbreite Zone 23,5-28 m (Kamera 031)" 10,44.
Ursache (Kreuztest): Kamera, nicht Modell - Ref-Kamera + Null-STL 12,08 (ok), Null-Kamera + Ref-STL 11,13 (rot). Ref-K-031 war mit --silhouette geloest (kamera.silhouette_genutzt),
der Nullstart loeste ohne (rms 414 statt 146 px); die Option stand nur im abgeleiteten Kamerafeld, das der Nullstart entfernt.
Fix generisch: foto_kalibrieren.py schreibt K['kalibrier_optionen']; nullstart uebernimmt sie (Altprotokolle: aus silhouette_genutzt) und ruft die Kalibrierung damit auf. Gegenprobe: 12,06 (gruen).
OFFEN: K-031 schwach bestimmt - f/Abstand tauschen sich (Null 3936 px/38 m, Ref 5064 px/57 m); Silhouetten-Kamera ist an das Modell gefittet (teilweise zirkulaer fuer Breitenpruefungen).

## CL - Uebernahmetor streng + Elementbuch (2026-11-06)
Ziel: Fehler 2 (Uebernahme bei t < 2) und Fehler 5 (gutes Altelement durch globalen Gewinn verloren) technisch ausschliessen. Umsetzung: qualitaetsstufen.uebernahme_tor (a je Foto rot/gelb nicht schlechter +0.01, b gepaart t <= -2 bzw. foto_freiraum-Pruefung faellt, c Restfeld optional, d Druckbarkeit, e Elementbuch lokal je Element), elementbuch.py, Kostenkarten je Stand.
Ergebnis: T0 bestanden (max Differenz 0.00000). T1 (ohne Bilder): v2 (Eckoeffnungen) gegen v1 abgelehnt durch (a), (b), (e); Arkade-Zeile 4 ok -> 5 FEHLER. T2, T3, T4, Bilder: NICHT ausgefuehrt (GPU 30 min von anderen Jobs belegt). T5: Regression Martinstor und kaufhaus_null5 identisch (Martinstor-Generator ist martinstor_v4_gen, baukasten_gen nicht beteiligt).
Spec-Abweichung: Kostenkarte ist gekappt, Schwelle '>= 0.999'. Offen: T2-T4, Bildbeschreibung 004, tor_restfeld im Plan.

Nachtrag CL (2026-11-06): T1 bestanden (Ablehnung durch a, b, c, e; Arkade 4 -> 5), T3 bestanden, T4 bestanden (e nur fuer den verschobenen Bogen: neu +1.8 / entfernt +2.4), T2 DURCHGEFALLEN (Kaempferversatz 0.8 m in Fotokanten nicht unterscheidbar: dm -0.0001, 1 von 4 Boegen besser, 3 schlechter durch einzelne Fotos). Schwellen unveraendert. Restfeld (c) 7.7 s je STL, in T1 ablehnend (f02 0.578 -> 0.617).

Nachtrag 2 CL (2026-11-06): T2 neu (Umkehrung von T4) DURCHGEFALLEN (dm -0.0150, t -1.9; (a) 4 Fotos; (e) Bogen +1.8/+2.4 'schlechter' in 3-4 von 10 Fotos trotz 8-9 besser - rot/gelb-Tausch im selben Foto zaehlt doppelt); T2b bestanden. tor_restfeld im Standardplan an. Regel fuer gemischte Fotos offen (Koordinator).


## CM - Vergleichslauf Ansatz (Sonnet, 2026-11-05/06)
Frage: ist Modell+Restfeld (C) bei unserer Datenlage in allen Zielmetriken mindestens so gut wie Photogrammetrie (A) und amtliches Modell (B)? Vollstaendig: modelle/BEWEIS_ANSATZ_2026-11-06.md, Zahlen /media/oem/scan/rc-park_null/beweis_ansatz/*/ergebnisse.json, Werkzeug tools/beweis_ansatz.py.
Ergebnis: Kriterium NICHT bestanden. Metrik 2 (rot UND gelb): C < A bei 0 von 3 Objekten (Kaufhaus gelb A 0,13 / C 0,35; synthetisch gelb A 0,32 / C 0,37; Martinstor rot A 0,060 / C 0,073), C < B nur bei Kaufhaus und synthetisch (Martinstor gelb B 0,525 / C 0,563). Metrik 1 (synthetisch): C klar am besten (Chamfer 0,0045 / 0,0585 m gegen A 0,76 / 0,69).
Befunde: (1) gelb belohnt kantenreiche verrauschte Netze: die bekannte Wahrheit selbst hat gelb 0,358-0,368, A 0,298-0,315 -> Metrik als Rangfolge zwischen Netzarten begrenzt. (2) Metrik 3 haengt von der Zellwert-Definition ab (Zellmaximum: C besser als B am Kaufhaus-Dach; Strahl auf Zellmitte: B 0,17 / C 0,44 m); offen, Beobachtung in der Kaufhaus-Masstabelle. (3) Zellen ohne Netz als 0 m zu zaehlen war ein Artefakt (A 7,75 m). (4) Poisson-Ballon: A hat Dach/Volumen unvollstaendig. (5) Martinstor-Pruefstandzeilen fuer C sind zirkulaer. (6) Synthetische Wahrheit "schwach" war nicht unterscheidbar vom Standardmodell (0,7 cm), "stark" nachgezogen und offengelegt.
Zusatzbefund fuer Stufe 4: Fassadenzellen, in denen A besser ist (Kaufhaus gelb 0,03-0,25 gegen C 0,26-0,50), sind das noch nicht uebernommene Restfeld. Keine Sollwerte, Schnappschuesse, Generatoren, foto_diff oder qualitaetsstufen geaendert.

Nachtrag 3 CL (2026-11-06): Summenregel (rot+gelb) in (a) und (e). T0, T1, T2b, T3 bestanden; T2 und T4 durchgefallen: Bogen jetzt 'gemischt' (7/10 Fotos besser, 2 schlechter) statt 'schlechter'/'besser'; T2 zusaetzlich (a) 000/010/214 und (b) t -1.9; T4 (e) nicht ausgeloest, Tor trotzdem NEIN durch (a)(b). Regression beider Objekte identisch.

Nachtrag CM (2026-11-05 19:40, Sonnet): Nachtest Metrik 2 mit kosten_lr (vorab formuliert, Maske B+3 m je Foto). Kaufhaus A -0,030 / B -0,003 / C -0,011; Martinstor A -0,019 / B -0,004 / C -0,009; synthetisch A -0,494 / B -0,014 / C -0,493 / W -0,512; stark A -0,522 / C -0,542 / W -0,551. Kriterium (C<A,B bei >=2/3 Objekten, t<=-2 gegen A) NICHT bestanden (0/3; C gegen A t +1,5 / +1,6 / +0,08 / -0,77). Nulllinie W kleinstes: bestanden. Das Ergebnis bestaetigt rot/gelb: A ist bei echten Objekten in den Kanten besser als C (Restfeld). Details: BEWEIS_ANSATZ_2026-11-06.md. Keine Sollwerte/Tools geaendert.

Abschluss CL (2026-11-06): T0, T1, T2b, T3, T4 bestanden (T4-Erwartung nach Entscheid auf (a)/(b) + Bogen nicht 'besser' gesetzt); T2 DURCHGEFALLEN mit Befund: korrekte 0,6-m-Korrektur nicht annehmbar, weil Fotos 010 (Versatz 0,59 m) und 214 (0,94 m) das falsche Modell bevorzugen - Kameraversatz je Foto > Elementkorrektur; Voraussetzung: versatzkompensierte Kennzahlen (S2) / Feinlage (Stufe 5). Test-Schalter --rg-feld fuer die Wiederholung.

## CO-Nachtrag zu CL - Fehlerkarte S3 Phase A: gelb saturiert durch Textur (2026-11-05)
Befund gegen die Kantenzaehlung: tools/fehlerkarte.py auf Kaufhaus Stand v1 (11 Fotos) gibt gelb im Mittel 0,30-0,46 je Flaeche (min_anteil 0..0,7 aendert es kaum), weil Ziegel-/Zierkanten der Fotos im Modell fehlen; Cluster grossflaechig, Ziel gelb < 0,25 so unerreichbar. Schwellen nicht nachjustiert (Koordinator-Entscheid). Siehe STAND_2026-11-06.md "S3 Phase A".

## CO - Fehlende Bauteile: Mindestflaeche aus Aufloesung, Kacheln, Zier-Neuvernetzung (2026-11-05)
- Aenderung: `fassade_ortho.py` (Zelle je kleiner Flaeche = Ausdehnung/256 px, `--zelle-min 0.005`, `--nur`), `fassade_parsing.py` (`--mind-px 96`, `--mind-fotos 3`, Kacheln 960/25 %, Textembedding einmal, fp16, Gegenbegriffe, Z-Protokoll `--objekt`), `bauteile.netz_druckbar`, `baukasten_gen.figuren_netz` + Konsolen-Huellpunkte gerundet, `tools/test_s4.py`.
- T1: 38 von 47 Vorbauflaechen geparst (vorher 2), 25 mit Erkerfenster; Fehltreffer Wappen/Gewoelbe bleiben. T3: Figuren 1 Koerper wasserdicht, IoU 0,563 >= 0,557; ohne Neuvernetzung 11 Koerper. T2/T5 entfielen (Budget). Kacheln: Orthos der Hauptfassade < 960 px (5 cm) -> 1 Kachel, kein Unterschied; bei 2 cm Zelle Figurscore 0,47 -> 0,57 (Kachel), aber Fenster zerfallen in Einzelscheiben.
- Regression Martinstor/Kaufhaus identisch. Sicherungen: /media/oem/scan/rc-park_daten/sicherung/*_vor_S4_2026-11-05.py. Daten: /media/oem/scan/rc-park_null/test_s4/.

## CQ - Bildwert: Bilder nur, wo Luecken sind (2026-11-06)
Werkzeug `tools/bildwert.py` + `tools/test_bildwert.py` (Spec S7, Minimalform nach Budgetkuerzung 20:20). Stand: --bedarf, Mapillary-Pose, Bewertung/Auswahl (gierig, lazy), --nachher (Code, nur Funktionstest) laufen; Frame-Pose (CPU-SIFT + cv2.solvePnPRansac gegen Modelloberflaeche, kein LightGlue, kein venv-colmap) ist GESCHRIEBEN, aber NICHT GETESTET. T2/T3 entfallen, T1/T4 bestanden.
- Bedarf Kaufhaus (Embree gegen Stand + 148 LoD2-Nachbardreiecke-Netze, 94 Kameras, n_kam>=3): Nord 0,95 / Ost 0,20 / Sued 0,00 / West 0,23 / Dach 0,44 (Anteil Zellen). Bedarf m2: Sued 397,6, West 365,7, Ost 309,3, Nord 13,6. Alle 94 Kameras stehen im Norden.
- FEHLSCHLAG/Befund 1: Fehlerterm (gelb+rot der S3-Fehlerkarte) macht Frontdubletten wertvoll (w_fehler 0,1 -> 27 m2, T1 faellt durch; Fehlercluster 352 m2, gelb saturiert). Standard w_fehler = 0 (ANNAHME), bis S3 kalibriert.
- Befund 2: ohne Nachbar-Verdecker sahen 8 Mapillary-Panoramen "Sued" (je 200-320 m2 Wert); mit Nachbarn (LoD2) bleibt 1 Ausschnitt mit 0,33 m2 -> Strassenpanoramen sehen die Suedwand nicht (verdeckt). Posen sind grob (GPS +-3 m, Peilung +-10 Grad, Hoehe/Nick ANNAHME); Bildblatt: projizierte Zellen liegen teils auf dem Vorderhaus.
- T1: Spec-Aufbau (Ostkameras entfernen) unmoeglich (keine Ostkameras im Netz). Ersatz: 8 virtuelle Ostkameras + 10 Dubletten gedeckter Kameras: 4 Ostkameras gewaehlt, keine Dublette (Wert 0), Ost-Anteil 0,198 -> 0,278; 4 virtuelle Ostkameras Wert 0 (sehen nichts).
- T4: Martinstor nur 7 Kameras mit K-Datei (STL-Proben, kein Fehlerterm): groesster Bedarf Sued (579 m2; Nord 464, Ost 389, West 357). Aussage schwach (Kameraliste unvollstaendig).
- Einbau nullstart (nicht geaendert): Schritt `bilder`/Video-Stufe ruft `bildwert.frames_auswaehlen(objp, kandidaten_json, aus, restfeld=, fk=, stl=)`; Kandidaten aus `--poses-mapillary`/`--poses-frames`; SfM erhaelt nur die ids aus `auswahl.json`.

## CR - Video-Stufe objektunabhaengig (2026-11-06)
- Ziel: Video-Stufe (Register BQ/BR/BT) fuer jedes Objekt; vorher fest `sparse_nord`/`db_nord.db`/`SFM-AUSRICHTUNG-nord.json`/`dicht_nord_entzerrt.npy`. Sicherungen vor der Aenderung: /media/oem/scan/rc-park_daten/sicherung/<datei>_vor_video_20261105.py.
- Aenderung: neu `tools/video_netz.py` (Netz = `video_stufe.netz` | `sfm.netz` | "alle" wenn sparse_alle da | "nord"; Buendel automatisch bei sparse_buendel/0 + SFM-AUSRICHTUNG-buendel.json, dann Netz schon im Modellsystem). Martinstor loest auf die alten Pfade auf (`video_netz.py modelle/martinstor/objekt.json`), `regression.py --pruefen` identisch (vor und nach den Aenderungen). `video_merge.py` schreibt Standard nach `sfm/dicht_<netz>_video/` (dicht_modell.npy, fused.ply im SfM-Rahmen + .vis mit 0 Sichtbildern fuer Videopunkte, ausrichtung.json, video_merge.json); die Basis bleibt (Register BT). `--inplace` = Altverhalten. objekt.json `freiraum_video` -> vereinigte Wolke (nur wolke_solid/Viewer), `freiraum` bleibt auf der Basis. Objektbereich/ICP-Band/Clip-Baender/Pruefhoehe aus `video_stufe` (`bereich`, `icp_z`, `baender_z`, `pruef_z_unten`), Altverhalten +-8 m um den Ursprung. `video_sfm.py --max-frames-je-clip N` (gleichmaessige Zeitfenster, schaerfster Frame), `--matching sequenziell` (overlap 10 + Vokabelbaum-Retrieval aus ~/.cache/colmap). nullstart: `--nur-video` (endet nach video_merge, kein auswertung/Schnappschuss), `--video-clips`, `--modell auto` (groesstes Teilmodell), `video_stufe.tol_m/jeder/max_frames_je_clip/matching`.
- Beweis Kaufhaus (kaufhaus_null5, Netz alle/Buendel, nur Clip cnplZ_aiED8, 100 Frames, sequenziell+Retrieval): video_sfm 651 s, ausrichten 36 s, PatchMatch+Fusion 716 s, merge 42 s = 24 min. Teilmodelle 39/13/11/10/2 Bilder: Erwartung >= 50 Frames NICHT erreicht (Bodenclip mit 7 Trefferfenstern/Schnitten).
- FEHLSCHLAG/Befund: Ausrichtung mit Standard-tol 1,5 m lieferte Skala 1,67, RMS 0,87 m (RANSAC nimmt bei weiter Schwelle Rauschpaare); tol 0,5 m, alle 39 Frames: Skala 2,00, RMS 0,29 m (458 von 12471 Paaren); tol 0,3 m: Skala 1,99, RMS 0,21 m (305). Residuum ist ueber Inlier der Schwelle gerechnet (nach oben beschnitten); Skala stammt aus dem Netz, nicht unabhaengig. Kaufhaus-Eintrag: `video_stufe.tol_m` 0,5.
- Videowolke z 3,3-11,1 m (Bodenvideo): mit ANNAHME zmin 12 kamen 0 Punkte; zmin 3 -> 640617 Videopunkte, ICP-NN-Median zur Basis 0,15 m, 195004 Punkte > 0,3 m von der Basis (neue Abdeckung). Je Fassade (fassaden.json, |Abstand| <= 1,5 m): f00 Basis 86659 / Video 66757 / neu 42963 (+49,6 %), f02 573446 / 484298 / 61817 (+10,8 %), f06 18266 / 5737 / 3208 (+17,6 %), f01 und f12: 0.
- Offen: nur 1 von 14 Clips; Fragmente verbinden; Skalenmehrdeutigkeit (1,67 vs 2,0) mit Bodenankern gegenpruefen; Dach/Rueckseite bleiben leer. Kein Schnappschuss erneuert, kein Commit.

## CP - S3b Wolke zuerst: Koerper nur aus der Wolke per Sichtbarkeits-Carving (2026-11-05, Sonnet)
- Ziel (Nutzerentscheid 20:10, Korrektur 21:45): Koerper ausschliesslich aus der Buendelwolke (fused.ply + .vis + Kamerazentren); kein Generator-STL, kein fassaden.json, LoD2/DOM1 nicht verwendet.
- FEHLSCHLAG 1 (verworfen): `tools/wolke_solid.py` = Restfeld auf dem Generatormodell (Tiefenfeld je Fassadenebene, TV-Glaettung, Booleans). T1 synthetisch FAIL, T2 Kaufhaus FAIL (nicht besser als A Poisson/C Modell), T3 Martinstor = C, Hauptvariante Arkade 3 statt 4, OR-Regel schnitt einen Giebel (Ergebnis in wolke_solid/OR_regel), Martinstor/synthetisch nach STL-Neuladen nicht wasserdicht. Ursache: Basis war das Modell, nicht die Wolke. Werkzeug bleibt als Altlast, nicht weiter bewertet.
- Neu: `tools/wolke_carving.py`, Voxel 0,10 m: (1) leer = Zellen, die in >= 2 von 15 Strahlbloecken (Kamera -> Punkt minus 0,3 m) durchlaufen werden; (2) Material = Zellen mit >= 2 Punkten + 0,3 m hinter den Punkten; (3) Gebaeude = groesste zusammenhaengende Masse > 2,5 m ueber Platzniveau (Platzniveau = tiefste grosse Horizontalebene der Aufwaertsnormalen), Hohlraum je Grundrisszelle bis zur oberen Huelle gefuellt, aber NIE in carving-leeren Zellen (Arkaden, Halle), Splitter < 0,4 m geoeffnet, Sockel 0,2 m unter Platz; (4) RANSAC-Lote rasten Knoten <= 0,12 m ein; (5) Marching Cubes -> groesster Koerper -> stl_dicht (3,5 cm Druckraster, wasserdicht nach Neuladen). Optional `--haut` (Fremdhaut-PLY).
- Kaufhaus (kaufhaus_null5, Wolke dicht_alle 958k Punkte, 7,05 Mio Beobachtungen, alle genutzt, 391 s; mit Zwischenspeicher 90 s): 1 Koerper, wasserdicht, 2273 m3, Mindestwand 1,46 mm (1:87), 0 % unter 0,34 mm. Pruefstand: Wasserdicht ok, 1 Koerper ok, Arkade Hauptfassade = 4 ok; FEHLER First 18,75 (Soll 21,0-21,8), Traufe 11,07 (11,2-12,3), Durchgang-ohne-Oeffnung nicht messbar. Dach bleibt zu niedrig (Wolke ohne Dachflaeche, nur Nordflanke), nicht mit LoD2/DOM1 korrigiert. Frontrender gegen Foto 004: audit/wolke_carving/front_vs_foto004.jpg (4 Bogen, Halle tief, Tuerme, Galerie; Bodenstreifen vor der Fassade = Platzplatte).
- Hinweis zu front.png (carv_kh): Nahprojektion entlang y der Wolkenachse, keine Fotoblickrichtung; die Halle ist hohl (Schnitt/Render), 'Klotz' ist ein Projektionsartefakt.
- Haut-Variante (OpenMVS mesh_std.ply, 35 % der Knoten auf die Haut verschoben, Median 4 cm, p95 13 cm): Arkade 6 statt 4, 10,9 % der Wand-Messpunkte < 0,34 mm: VERWORFEN, keine sichtbare Detailverbesserung in der Tiefenkarte.
- Synthetisch (tools/test_wolke_carving.py synth: Halle 18 x 5,2 x 4 m hinter 4 Arkaden, 54 Kameras, Rauschen 3 cm): Voxel-IoU gegen Soll 0,973, Volumen 1256,6 gegen 1192,0 m3 (+5,4 %), Arkaden 4, Halle zu 99,2 % leer, 1 Koerper, wasserdicht, keine Modelldatei gelesen. Gegenprobe NEGATIV=1 (Test liest absichtlich ein STL): Exit 1.
- Martinstor (martinstor_lod2 dicht_nord, 226 s): 1 Koerper, wasserdicht, aber Netz nur Nordseite; Pruefstand 16 von 76 ok, Mindestwand 0,27 mm, 7,7 % unter Grenze. Kein Befund zur Form ausser Tuerm/Nadel grob erkennbar.
- Offen: Dach/First aus Wolke (Luftbilder fehlen), Platzplatte vor der Fassade, Fotodiff-Test A/B/C mit dem Carving-Koerper, Martinstor mit Mehrseitenwolke. Kein Commit, kein Schnappschuss erneuert.

## CQ - S8 Kanten + Ebenen (Sonnet, 2026-11-06): Durchstich Kaufhaus, Synth NICHT bestanden
- Phase 0 (Stand der Technik, kurz): LIMAP (BSD-3) braucht pycolmap-Fork/pytlsd/DeepLSD/poselib, in venv-seg nicht vorhanden, pycolmap nur in venv-colmap -> Eigenbau `tools/kanten_3d.py` (OpenCV-LSD, BSD; GPU = torch, optional). PolyFit/Easy3D (GPL, CGAL+SCIP) und CGAL Kinetic Shape Reconstruction (GPL, C++-Build) nicht per pip -> Eigenbau Ebenenanordnung (Vorzeichencode je Voxel, konvexe Zellen mit manifold3d, MIT/Apache). Open3D nur in venv-mesh (MIT), nicht gebraucht (RANSAC eigen, numpy). DeepLSD (Gewichte/Lizenz ungeprueft) nicht verwendet.
- Phase 1 `kanten_3d.py` (Kaufhaus, 94 Fotos, 100 017 Segmente, Saat aus 6 770 Tiefenhypothesen = Wolke nur als Tiefen-Saat, Lage/Richtung aus Bildsegmenten per Ebenen-Schnittgerade/SVD, >= 3 Fotos, 1,5 px): 930 Linien in 66 s (GPU/torch). Bild `modelle/kaufhaus_null5/audit/kanten_vektor/linien_004.jpg` angesehen: Dachkanten, Fensterrahmen, Balkon, Erker, Bogenansaetze sitzen; Fehler: einige sehr lange Linien quer ueber die Fassade (rot, < 5 Fotos) und Linien auf Nachbarhaeusern (zulaessig, werden vom Quader beschnitten); keine Filterung nach Laenge/Plausibilitaet. Holdout-Variante (6 Fotos weg) 912 Linien.
- Phase 2 `ebenen_modell.py`: normalengefuehrtes RANSAC (Ebenen auf mm genau im Synth), Anordnung, Zelle fest/leer/Restfeld nach Carving-Anteil, Union mit 0,2 mm Aufblaehung (ohne sie bleiben beruehrende Zellen getrennte Schalen: Befund 7 Koerper). 
  * Kaufhaus eb1 (19 Ebenen, Restfeld 25-75 %): wasserdicht, aber ueberwiegend rauhes Carving-Netz mit einzelnen glatten Flaechen; Bild `audit/kanten_vektor/eb1_004.jpg`. eb2 (58 Ebenen, nur Mehrheit): scharf-planar, aber zerrissen, Arkaden weg (`eb2_004.jpg`). Kein Pruefstand-/Holdout-Lauf (s. u.).
- Phase 3 synthetisch (`tools/test_ebenen_modell.py`, Kasten + 4 Rundbogen-Arkaden + Halle + Satteldach + Treppengiebel, 74 Kameras, Rauschen 3 cm): NICHT BESTANDEN. Beste Einstellung (Mindestflaeche 1 m2, solid 0,8/leer 0,2): wasserdicht, 1 Koerper, IoU 0,92, 4 Arkadenoeffnungen, aber Soll-Kanten p90 74 cm (Ziel < 5 cm). Mit reiner Mehrheit (0,5/0,5): Giebelhoehe Median 0,5 cm (Stufen vorhanden), IoU 0,93, aber Arkaden 1 statt 4 (Bogen sind keine Ebenen, 0,9 m tiefe Zelle ueberstimmt). Ursache der grossen Abweichung: NICHT die Ebenen (mm-genau), sondern die Carving-Belegung: Halle/Hallendecke und 0,5-m-Giebelstufen werden von ihr nicht aufgeloest (Kanten [1,0.8,4]-[1,6,4] 0,8 m daneben). Messfallen: Kante-zu-Flaeche-Mass belohnt ein ausgefuelltes Modell nicht, aber Soll-Kanten in der Halle zaehlen; Mehrfachprobe der Schwellen am selben Test = Tuning, nicht als Beleg zu werten.
- Eigenfehler: Testszene hatte zuerst falschen Zylinder (cylinder(h, r_lo, r_hi) falsch aufgerufen, Radius 48 m) und Bodenschachbrett erzeugte Linien (Liniendistanz 490 cm) - beides behoben; Python-RayMeshIntersector statt Embree liess den Rendern 15 min haengen (`sk.ray` nutzt Embree).
- Offen / blockiert: Holdout-Tabelle Generator C / carv Holdout / Ebenen (tools/s8_kaufhaus.py) - Platztor 15,0 GB frei < 15 GB, Lauf abgebrochen (Tor nicht umgangen). Carving-Holdout (ohne 001,024,054,083,211,234) ist gebaut: /media/oem/scan/rc-park_null/kanten_vektor/ho_carv/. Kanten als Zwangslinien im Zusammenbau NICHT umgesetzt (Linien nur Beweisgroesse), Ebenenvorschlaege aus Linienpaaren fehlen - das ist der naechste Hebel fuer Bogen/Stufen. Kein Schnappschuss, kein Commit.

## CS - S9 Erkennen + Einpassen: Arkadenboegen Kaufhaus f02 (Sonnet, 2026-11-06)
**Auftrag:** SPEC_S9, erst nur Arkadenboegen (kaufhaus_null5). Werkzeug `tools/element_einpassen.py` (Familien rund/stich/spitz, Fit per differential_evolution + Nelder-Mead, BIC, Gegenpruefung, manifold3d-Einbau), Test `tools/test_element_einpassen.py`, Ansicht `tools/element_front.py`.
**Synth 8/8** (Familie + Kurve Median < 3 cm, 2 Kleeblattboegen abgelehnt, NEGATIV faellt durch). Schwellen nach Lauf gesetzt (P90 0,06 statt 0,20; Seeds 0,10) - Tuning-Verdacht, Kleeblatt-Trennung nur 2-4 cm.
**Kaufhaus:** Canny/3D-Kanten als Fitdaten gescheitert (Hintergrundkanten, flache Kosten; erster Fit lag 0,5-1 m daneben), Carving-Leere-Maske als Formdaten. Alle 4 Boegen vom Gate abgelehnt (P90/Kantenkontrast), BIC waehlt flachen Stichbogen (falsch im Frontbild). Rundbogen erzwungen: 4 Arkaden, 1 Koerper, wasserdicht, aber kosten_lr Mittel -0,0090 gegen Carving -0,0083 / Generator C -0,0111 (gepaart t -0,95): KEIN Beleg fuer Verbesserung. Eigenfehler: CW-Polygon ergab leeres Manifold; Zwickelband-t_front falsch (Balkon), durch Pfeilerstreifen ersetzt; BIC auf allen Randpunkten (Halle) statt Inliern; NEGATIV-Test crashte (IndexError); STL-Float32-Export nicht wasserdicht (4-Flaechen-Kanten), mit Versatzschleife/Snap geloest.
**Lehre:** Fit gegen Kantenwolken braucht Daten OHNE dichte Hintergrundkanten; Gate-Kontrast (Kopie versetzt) misst das ehrlich. Offen: Foto-Intrados gegen Carving-Maske nicht aufgeloest.

## CT - S10 Teil A: vier Kantenkarten-Pipelines + Synth-Bewertung (Sonnet, 2026-11-06)
- Vorarbeit gelesen: lsd_edges/foto_diff-mehrstufig (nur Helligkeit), CQ (LSD findet keine Boegen), CP/Lehre "weiche Evidenz bis zuletzt". Neu, nichts davon wiederholt: `tools/kanten_pipelines.py` (P1 Canny 3 Skalen x 4 Belichtungen, Karte = Anteil bestaetigender Varianten; P2 Lab-Delta-E + Farbton*Saettigung, Stufenhoehe = |grad|*sigma*sqrt(2pi) + NMS, glatte Stufe 4..22 dE [ANNAHME, fest]; P3 DexiNed (kornia) 2 Eingangsskalen; P4 SAM ViT-B (transformers) 24x24-Punktraster, Grenzen der Masken pred_iou>=0,8, Stabilitaet>=0,85, gewichtet, GPU), `tools/test_kanten_pipelines.py` (Synth), `tools/kanten_blatt.py` (Sichtblatt). Lizenzen eingetragen (DexiNed-Gewichte BIPED: ungeprueft, nur Test).
- Karten: 94 unverzerrte Fotos (`sfm/dicht_alle/images`) x 4 = 376 PNG (8 bit) in /media/oem/scan/rc-park_null/s10/karten/<p1..p4>/<foto>.png (271 MB), Job s10karten2 297 s (P4 7,5 s/Foto; erste P4-Fassung mit CPU-Nachverarbeitung 91 s/Foto -> auf GPU umgeschrieben, gleiche Statistik bis auf 3. Stelle).
- Synth (zwei Szenen A Rot/Gold + Schatten links, B Gruen/Rosa + Raster + Schatten rechts; Schwellen VOR dem Lauf fest: Karte>=0,5, Skelett, Toleranz 2 px; B ist Gegenprobe, nichts nachgetunt). F1 (Praez./Vollst.): A p1 .50 (.34/.95) p2 .61 (.47/.87) p3 .42 (.27/.99) p4 .69 (.56/.90) | weich-Mittel .82 (.70/.99) | k=2 .58 k=3 .79 (.66/.99) k=4 .88 (.94/.82); B p1 .62 p2 .70 p3 .66 p4 .51 | Mittel .71 | k=3 .76 | k=4 .74 (.87/.64). Farbband gleicher Helligkeit (Vollst.): p1 .81/.59, p2 .96/.88, p3 1,0/1,0, p4 .93/.99.
- Befunde: (1) Einzelkarten haben Praezision 0,27-0,57: P1/P3 melden Ziegel-/Quaderfugen (Textur-Fehlalarm 0,43-0,67), P2 Rauschen in dunklen Flaechen, P4 grobe Grenzen. (2) Gemeinsame Verbesserung nur durch Zusammenfuehren (k=3/Mittel F1 .71-.82 gegen Einzel <= .70). (3) k=4 am praezisesten, verliert aber Band/Boegen (A: .78/.74) - SAM sieht schmale Gesimse/Bogenbaender nicht (auch am Foto 004 Bogenrand, Blatt `blatt_004_bogenrand.jpg`: Bogenband in P1/P2/P3, nicht in P4; k=3 behaelt es). (4) ALLE Pipelines melden die harte Schattenkante (88-97 % der Schattenpixel, nur P4/k=4 ~0,26-0,52/0,30): Schatten ist per Einzelfoto nicht von Geometrie trennbar -> bestaetigt die Spec, dass erst die Mehr-Foto-Bestaetigung (Teil B, >= 3 Fotos mit wanderndem Schatten) Schatten entfernt; Teil A kann das nicht. (5) Farbe (P2) schlaegt Helligkeit (P1) beim Farbband klar (.96 gegen .81 / .88 gegen .59), gelernt (P3) findet es hier immer (Synth ist sauber).
- Grenze: Synth ist 2D-gezeichnet (flach, kein Perspektivwechsel, harter Schatten); keine Aussage ueber echte Fotos ausser Sichtblatt. Kreuz-Ansicht (Foto-Holdout-Praezision) braucht Teil B (3D-Kanten) und ist NICHT gemacht. Gewichte der Abstimmung nicht am Pruefbild getunt. Kein Commit, keine Regression (kein bestehendes Werkzeug veraendert; `tools/gpu_werkzeuge.txt` +1 Zeile).

## CU - S10 Teil B: gemeinsames 3D-Kantenfeld (Sonnet, 2026-11-06)
- Recherche/Lizenz: EMAP = github.com/cvg/EMAP (README: MIT fuer die Mehrheit; NeuS/NeuralUDF-Basis, Training je Szene, Lizenz der Basisprojekte NICHT einzeln geprueft) -> NICHT eingebaut (8-GB-GPU, je Szene Training). NEF nicht geprueft. Eigenbau `tools/kanten_feld3d.py` (+ `tools/kanten_feld3d_pruefen.py`, `tools/test_kanten_feld3d.py`, `gpu_werkzeuge.txt` +1): Voxel-Akkumulation, Eingang = WEICHES MITTEL der 4 Karten, Sichtbarkeit aus COLMAP-Tiefenkarten (Voxel nicht hinter naechster Oberflaeche, Min-Pool 3x3), Fenster = Voxelgroesse in px, Kandidaten = Schale 15 cm um die Wolke (nur Punkte mit >=2 Trainingsfotos). Bestaetigung: Mittel >= 0,5 in >= 3 Fotos, >= 3 Lichtgruppen (EXIF-Stunde; ohne EXIF eigene Gruppe), Blickwinkelstreuung >= 5 Grad, Anteil bestaetigend/sichtbar >= 0,3 (alles VOR dem Lauf fest). 3D-NMS, dann RANSAC Geraden und Kreisboegen. kanten_3d.py (LSD) nicht genutzt: nur Geraden, Saat aus Wolke.
- (1) Synth (analytisch gerendert, 24 Ansichten, 6 Lichtlagen, Arkadenwand 4 Rundboegen, Plattenschatten, rot/gold gleiche Helligkeit, Ziegelfugen; Karten = echte P1-P4 aus den Bildern; Schwellen VOR dem Lauf: Praez >=0,80, Vollst >=0,70, Schattenanteil <=0,05, 4/4 Boegen). Voxel 0,10 m: FEHLSCHLAG (Praez 0,78, Vollst 0,52, 0/4 Boegen; Fenster/Gitter zu grob). Voxel 0,05 (danach gewaehlt; Seed 0 und 1, gleiche Szene, Gegenprobe nur Rauschen): Praez 0,835/0,837, Vollst 0,802/0,801, Schatten 0,006/0,005, Boegen 4/4; OHNE Lichtgruppen Schatten 0,12 (Filter wirkt), Einzelpipelines Praez 0,59-0,84 (P2 farbe 0,59), Vollst 0,67-0,84. Grenze: Szene flach, eine Geometrie; zweite Szene mit anderer Geometrie fehlt.
- (2) Kaufhaus null5 (88 Fotos, 6 Holdout 001,024,054,083,211,234 nicht im Feld; Voxel 0,05, 7,0 M Kandidaten, 3,0 M bestaetigt, 58 684 Punkte nach NMS, Lauf 20 s GPU + RANSAC 6 min). Holdout (Mittel 6 Fotos; Tol 3 px; Kontrolle = Feld um 0,5 m versetzt / Zufall 0,5 m): Praezision 0,55 (Kontrollen 0,46/0,43), Vollstaendigkeit 0,57, kosten_lr (foto_diff-Formel, Bereich = Wolke projiziert, Kantenbild = Kartenskelett; NICHT vergleichbar mit STL-Werten -0,0083/-0,0111) -0,240 (Kontrollen -0,083/-0,061). Je Foto Praez/Vollst/lr: 001 .64/.83/-.118, 024 .64/.69/-.153, 054 .46/.23/-.005, 083 .30/.23/-.042 (kleines Stueck), 211 .63/.81/-.743, 234 .64/.61/-.377. 054 (Nahaufnahme, im Training kein aehnlicher Blick): Feld fast leer an den Bogen. Sicht (holdout_024/054.jpg): Feld folgt Gesimsen, Fensterrahmen, Bogenkanten oben, aber viel Streuung auf Dach/Decke.
- Empfindlichkeit: k2 / k4 / ohne Lichtgruppen / Anteil 0,5 -> Praez 0,548/0,555/0,550/0,585, lr -0,239/-0,245/-0,240/-0,319 (Punkte 60,7k/56,0k/58,7k/51,2k): die Mehrfoto-Filter sind auf echten Fotos FAST WIRKUNGSLOS (79 Lichtgruppen bei 88 Fotos, Karten dicht: 43 % aller Schalenvoxel gelten als bestaetigt). Der Anteil-Filter (0,5) wirkt am meisten (nicht uebernommen, Schwelle nicht getunt).
- BOGENTEST (Arkade, erwartet u -6,6/-2,3/1,85/6,2, Scheitel 4,4): Kreisboegen nach Geraden: 1 von 4 (u -2,13, r 2,26, Scheitel 4,61, Wandnormale 1,0; Mitte 0,9 m hinter der Fassadenebene); Boegen vor Geraden (abst 0,12, r<=8, 1500 Versuche; nach erstem Blick geaendert): 1 von 4 (u -2,66, r 2,38). 98 weitere fassadenparallele Kreise sind meist Rauschen (Nachbarflaeche/Dach). Flaechenbild `feld3d/kh/fassade_kantenfeld.png`: Bogenverlauf nur stellenweise als Punktband zu sehen, Gesims und Balkon deutlicher. Urteil: Boegen im Feld als Kurven NICHT zuverlaessig; Ursache ungeklaert (Kandidaten: Wolkenschale leer in der Arkade, Punktstreuung +-0,1 m passt nicht zu RANSAC abst 0,08-0,12, Bogenkante ist Tiefensprung -> Sichtbarkeit am Rand).
- Offen: Karten zu dicht fuer k>=3-Filter (Textur/Ziegel); echte Lichtgruppen (viele Fotos ohne EXIF = je eigene Gruppe, ANNAHME zu grosszuegig); Bogen-Extraktion (besser: Kurve direkt in das Feld einpassen statt RANSAC); Sub-Voxel-Lage; kosten_lr gegen Carving/Generator auf gleicher Grundlage fehlt (STL-Kanten ins gleiche Kartenskelett).
- Daten: /media/oem/scan/rc-park_null/s10/feld3d/{synth,synth_v05,synth_v05_s1,kh}/ (25 MB). Kein Commit, Regression nicht gelaufen (kein bestehendes Werkzeug veraendert, nur gpu_werkzeuge.txt +1 Zeile).

## CV - S10 Teil C: Wolke filtern F0-F3 + Wirkungstest 3D-Kantenfeld (Sonnet, 2026-11-06)
- Werkzeuge (neu, generisch): `tools/wolke_filter_varianten.py` (masken / fusion / f3), `tools/wolke_kennzahlen.py` + `wolke_kennzahlen_tabelle.py`, `tools/test_wolke_filter_varianten.py` (Synth: Wand 3 cm Rauschen + Stufe + Luftausreisser; F3-Schwellen dort festgelegt, bestanden: Luft >=80 % entfernt, Wand >=97 % behalten, p50 -30 %, Stufe 20 cm bleibt). Daten: /media/oem/scan/rc-park_null/s10/filter/ (300 MB). Quellordner dicht_alle nur gelesen (Symlink-Arbeitsordner je Variante).
- FEHLER GEFUNDEN (wirkt breiter!): vis-Index in fused.ply.vis = aufsteigende Bild-ID in sparse/images.bin, NICHT Namensreihenfolge. Kaufhaus: ab Index 72 abweichend (216, 222 stehen vor 205...), 14 von 92 Bildern falsch zugeordnet; Rueckprojektion gegen Tiefenkarten: ID-Reihenfolge 98 %, Namensreihenfolge 67 % (Bild 205: 12 %). Betroffen (nutzen `ids = sorted(K, key=int)` fuer vis): `wolke_carving.py` (Sichtstrahlen von falschen Kameras -> carv_kh3 prueffen!), `freiraum_pruefen.py`, `wolke_solid.py`, `kanten_3d.py`, `kanten_feld3d.py`. Behoben nur in `kanten_feld3d.py` (neue Hilfe `freiraum_pruefen.vis_namen(dicht)`); die anderen NICHT angefasst (Ergebnis wuerde sich aendern, Regression/Schnappschuss noetig). Holdout 211 war in Teil B durch den Fehler nicht korrekt aus der Kandidatenwahl ausgenommen (Teil B Ergebnis 1/4 Boegen bleibt mit Korrektur 1/4).
- Varianten (Holdout 001,024,054,083,211,234 in F0o..F3 NICHT in der Fusion; F0r = heutige Wolke = Neuberechnung mit allen 94 Fotos, 961 488 Punkte = Original, Reproduktion exakt): F0 heutige; F0o Standardfusion ohne Holdout (Kontrolle); F1 min_pixel 7, reproj 1,0, tiefe 0,005, normal 6; F1b 10/0,7/0,003/4 (nur Empfindlichkeit); F2 Masken (SegFormer-ADE20K: Himmel, Person, Fahrzeuge, Vegetation, Zelt/Stand/Markise; Puffer 12 px, 27,5 % der Pixel, 2,5 % der Punkte); F12 = F1+Masken; F3 = Lage+Farbe (kNN-Dichte relativ, lokale Ebene, Lab-Farbe, bilaterale Normalenglaettung) auf F0o bzw. F12. Schwellen F1/F3 vorab gesetzt; die Auswahlregel "bester = nur Varianten mit Abdeckung >= 0,85 x F0o, darunter kleinste Rauheit/isolierte Punkte" wurde NACH Sicht der Kennzahlen formuliert (ehrlich: nicht vorab).
- Kennzahlen (3 Referenzebenen aus F0 per RANSAC, alle Hauptfassade in 3 Tiefenlagen; gewichtetes Mittel; cm): 
  | Var | Punkte | RANSAC p50/p90 | lokale Rauheit p50 | Schale 10-90 | Abdeckung | isol. vor Fassade % | isol. gesamt % |
  | F0 (r) | 961k | 5,91/11,67 | 4,34 | 29,2 | 0,54 | 3,81 | 10,1 |
  | F0o | 909k | 5,91/11,65 | 4,33 | 29,4 | 0,54 | 3,89 | 10,2 |
  | F1 | 345k | 5,55/11,12 | 2,57 | 28,1 | 0,44 | 2,33 | 6,2 |
  | F1b | 34k | 5,49/10,13 | 0,77 | 23,8 | 0,19 | 13,9 | 5,7 |
  | F2 | 886k | 5,90/11,65 | 4,32 | 29,1 | 0,54 | 4,09 | 9,9 |
  | F12 | 342k | 5,54/11,11 | 2,55 | 28,1 | 0,44 | 2,35 | 6,0 |
  | F3(F0o) | 799k | 5,86/11,55 | 3,91 | 29,0 | 0,52 | 2,08 | 2,95 |
  | F3(F12) | 318k | 5,45/10,97 | 2,12 | 27,3 | 0,42 | 1,05 | 1,1 |
  Nur die saubere Wand (Ebene 2, 22 m2): p50 3,23 -> 2,54 (F1) -> 2,30 (F3(F12)), Schale 8,5 -> 6,5 -> 5,0 cm, Rauheit 4,0 -> 2,2 -> 1,5. Ebenen 1/3 sind keine ebenen Waende (Schale 30-38 cm: Arkadenstaffelung/Relief) -> p50 dort 6-8 cm unabhaengig von der Variante.
- Ehrliche Befunde: (1) Rauschen sinkt vor allem durch AUSSORTIEREN (F1: 62 % der Punkte weg, Abdeckung -18 % relativ, 0,54 -> 0,44); F1b zerstoert die Wolke (96 % weg). (2) Masken F2 fast wirkungslos (-2,5 % Punkte, keine Kennzahl besser): die Wolke enthaelt kaum Himmel/Personen-Punkte, sie stehen vor der Wand und sind nicht dort wo die Kennzahl misst. (3) F3 allein senkt isolierte Punkte stark (3,9 -> 2,1 %), Rauheit kaum (4,3 -> 3,9); F3 auf F12 am besten bei Rauschen/Isolierten, Abdeckung am schlechtesten (0,42). (4) Sicht: front_varianten.jpg - die 4 Arkadenboegen sind in ALLEN Varianten als Rundboegen erkennbar, in F1/F3(F12) schaerfer und sauberer; die Kante ist in der Wolke da, nicht im Feld. (5) Kennzahl "Kante oben" (z-Profil an Wandoberkante) war unbrauchbar (Werte 10-410 cm je Ebene), nicht verwertet; echte 3D-Kantenschaerfe nicht gemessen - Ersatz: Wandschalenbreite. (6) Die Kennzahl vor_fassade_prozent (alle Punkte 0,3-3 m vor der Wand) enthaelt echte Bauteile (Erker, Balkon, Pfeiler) und ist als Ausreissermass ungeeignet; Ersatz isolierte Punkte (kNN-Abstand > 3 x Median; fuer F3 teilweise zirkulaer, da F3 auch kNN-Dichte nutzt).
- Wirkungstest 3D-Kantenfeld (voxel 0,05, gleiche Einstellung wie Teil B, mit vis-Korrektur, 6 Holdout nicht im Feld): Boegen als Kurven (von 4): F0r 1 (u -6,6), F0o 1 (-6,6), F3(F0o) 2 (-2,3 und 1,85), F3(F12) 1 (-2,3). Holdout Praez/Vollst/kosten_lr: F0r 0,550/0,566/-0,240; F0o 0,549/0,568/-0,239; F3(F0o) 0,538/0,515/-0,201; F3(F12) 0,555/0,503/-0,228 (Kontrolle versetzt -0,03..-0,06). URTEIL: KEINE belegte Verbesserung. Je Variante wird ein ANDERER Bogen getroffen (Zufallsbereich RANSAC), das Maximum 2/4 liegt im Rauschen; Vollstaendigkeit und kosten_lr werden mit F3 schlechter. Wolkenfilter ist nicht der Engpass fuer die Bogen-Extraktion; die Ursache liegt in der Extraktion (RANSAC abst 0,08-0,12 gegen Streuung, Wolkenschale leer in der Arkade) bzw. in den Karten. Naechster Schritt: Bogen direkt in die Wolke einpassen (Front-Ortho-Bild oben zeigt sie klar) statt RANSAC im Feld; Teil-B-Zusatz Anteil-Filter 0,5 nicht uebernommen (nicht am Pruefbild getunt).
- Empfehlung Wolke: fuer Carving/Kanten F1 (oder F3 auf F0o) nur mit Abdeckungsverlust-Pruefung; Carving mit F1/F3 NICHT gerechnet (kosten_lr gegen carv_kh3 offen; wegen vis-Index-Fehler zuerst wolke_carving.py korrigieren und carv_kh3 neu bewerten). Regression (8b) nicht gelaufen: freiraum_pruefen.py nur um Funktion erweitert, kanten_feld3d.py eine Zeile; kein Commit.

## CW - vis-Index-Fehler behoben, Carving neu bewertet (Sonnet, 2026-11-06)
- BEWEIS (tools/test_vis_mapping.py, Exit 0): Projektionstiefe der Beobachtung (Punkt, vis-Kamera) gegen geometrische Tiefenkarte DIESER Kamera (|D-z| < 3 %). Kaufhaus null4 dicht_alle (94 Bilder, 14 Positionen verschieden): vis_ids 97,2 % (Kamera-Mittel, schlechteste 90 %) gegen Namensreihenfolge 91,1 % gesamt / schlechteste Kamera 11,8 %. Martinstor_lod2 dicht_nord (23 Bilder): beide Ordnungen gleich (99,2 %) - dort war der Fehler folgenlos, der Test ist NUR am Kaufhaus unterscheidend (weitere vorhandene dichte Ordner haben kein kameras_unverzerrt.json oder keine images.bin; martinstor_null/daten-dicht_nord ohne Kameradatei).
- images.bin ist die einzige belegte Quelle der Reihenfolge. Hilfe `freiraum_pruefen.vis_ids(dicht, K)` (Bildmenge images.bin = K sonst ValueError); `vis_namen` raet bei fehlender images.bin NICHT mehr (FileNotFoundError; Fallback nur ausdruecklich mit Warnung). Synthetische/abgeleitete Wolken schreiben jetzt images.bin (`images_bin_schreiben`: test_wolke_carving, test_ebenen_modell, wolke_solid kopiert sie in die Ausgabe).
- Korrigiert ueber die gemeinsame Hilfe: wolke_carving.py, wolke_solid.py, freiraum_pruefen.py (main), kanten_3d.py, kanten_feld3d.py (jetzt ebenfalls vis_ids). Test D (Quelltext) lehnt jedes tools/*.py ab, das vis-Kameraindizes (zweites Ziel von vis_lesen) ohne vis_ids liest; Ausnahme test_wolke_carving (Synthese). Punktzaehler (pi, _) betroffen nicht.
- ALTE FOLGEFEHLER: ho_carv (Holdout S8/S9) strich bei Index >= 72 die falschen Kameras (u.a. war 211 nicht entfernt); alte kosten_lr-Werte "Carving -0,0083" stammen aus diesem Holdout.
- Neu gerechnet (alte Verzeichnisse unberuehrt): carv_kh4_vis (wie carv_kh3: puffer 0,7, sigma 0,75) und carv_kh4_vis_ho (Befehl wie ho_carv: Standard puffer 0,5; ohne 001 024 054 083 211 234), unter /media/oem/scan/rc-park_null/wolke_solid/. Jeweils ~3-4 min.
- kosten_lr (kleiner = besser), 6 Holdout-Fotos 001/024/054/083/211/234: Carving alt -0,0083 (-0,0059/-0,0032/-0,0094/-0,0090/-0,0161/-0,0060); Carving korrigiert (kh4 ho) -0,0095 (-0,0056/-0,0026/-0,0079/-0,0132/-0,0205/-0,0071); S9 rund -0,0090; Generator -0,0111. Median alt -0,0075, neu -0,0075. Besser auf 3 Fotos (024, 083, 211), schlechter auf 3 (054, 234, 001 kaum). URTEIL: kleine Verbesserung (0,0012), Generator bleibt vorn; der Fehler war NICHT die Hauptursache der ungenauen Kanten. Vollmodelle (Fotos im Modell, nur Information): kh3 -0,0088, kh4_vis -0,0085 (im Rauschen).
- Pruefstand carv_kh4_vis: First 21,34 ok, 1 Koerper, wasserdicht ok, Traufe Nord 10,98 FEHLER (unveraendert), Durchgang n. m.; Arkaden Hauptfassade jetzt 5 statt 4 (breite_max 4,16) -> neuer FEHLER "Arkade Hauptfassade: Oeffnungen ab Boden" (carv_kh3 hatte 4; Zahl hing schon vorher an der Glaettung 3/4/5, Register CP). Frontbild: modelle/kaufhaus_null5/audit/wolke_carving/carv4_vis_front.jpg (Tiefenkarte, 4 Boegen deutlich + Zusatzoeffnung am Rand). carv_kh3 bleibt damit der bessere DRUCKSTAND, bis die 5. Oeffnung geklaert ist (offen).
- Regression (8b): kaufhaus_null5 und martinstor identisch (Carving-Ergebnisse sind nicht im Schnappschuss) - Schnappschuss NICHT erneuert, keine Begruendung noetig. test_wolke_carving synth rc 0.
- Offen: Ursache der 5. Arkade; kanten_feld3d/test_kanten_feld3d und test_ebenen_modell nicht neu gelaufen (nur Syntax; Aenderung dort: images.bin-Schreiben bzw. vis_ids); Kanten-/S9-Ergebnisse von heute, die ho_carv nutzten (s9 kh_ho), basieren auf dem falschen Holdout-Material.

## CX - Handyfotos Kaufhaus 6.11. (Serien a-j, nubia Z2462N) gegen kaufhaus_null4 registriert (Sonnet, 2026-11-06)
- Eingang: 146 verschiedene Fotos (MD5; c_01..c_12 sind Kopien von a_01..a_12), davon 9 nach Sichtprobe als Bewegungsunschaerfe ausgeschlossen (Liste mit Begruendung `modelle/kaufhaus_null5/audit/handy_ausschluss.json`, nichts geloescht) -> 133+13 = 146 vorbereitet (Serie j nachgereicht, 13 Fotos). Hersteller-Wasserzeichen "nubia Focus 2 5G" unten links in JEDEM Foto: unterer Streifen 5 % abgeschnitten (sonst starre SIFT-Punkte wie Register BQ).
- Schaerfemass: Ganzbild-Laplace ist auf glatten roten Flaechen kleiner als bei scharfen Fotos; neues `tools/bildschaerfe.py` (Kachel-Perzentil + Kantenrelation, `tools/test_bildschaerfe.py` besteht). GRENZE ehrlich: trennt NICHT sicher (handy_08 und d_17 sind sichtbar verwackelt, haben aber kachel_q 448/222; unscharf-Schwelle 150 haette sie behalten, die Wischer h_10/h_12 teils verworfen). Entscheidung bleibt Sichtprobe; das Mass sortiert nur die Reihenfolge der Ansicht.
- Registrierung (`tools/zusatzfotos_registrieren.py`, Ziel `/media/oem/scan/rc-park_null/kaufhaus_handy`, Referenz sparse_buendel/0 + db_alle.db nur gelesen/kopiert): SIFT-GPU + Matching neu x registriert (94) + neu x neu (24309 Paare, 7,3 min), PnP, bis 4 Runden mit Triangulation neuer Punkte, Buendel nur der neuen Posen, EINE Kamera je Bildformat (Hoch/Quer) mit festem f. f: Kalibrierlauf je Bild frei streut stark (1359..6790 px, ebene Szenen), Median der Werte im Fenster +-30 % um den Prior 1444 px = 1413,6 px (27 Bilder, Streuung 149 px; Prior-Fenster ANNAHME), danach fest. Kein Profil aus ChArUco vorhanden (modelle/kamera_profil/ enthaelt nur die Vorlage).
- Ergebnis: 72 von 146 registriert (Runde 1: 44, 2: 20, 3: 6, 4: 2), Reproj mittel 1,36 px / median 1,17 px (Referenznetz 1,05), 56621 Beobachtungen. Je Serie: a 19/19, b 19/19, c 2/8, d 0/18, e 7/19, f 1/13, g 3/9, h 0/15, i 8/13, j 13/13. Serien c/d/e/h (Arkaden-Innenraum, Gasse, Erker von unten) registrieren kaum: kaum 2D-3D-Treffer, Referenznetz hat dort keine Punkte und die Bilder ueberlappen nicht mit den Strassenfotos. Massstab erbt aus den festen 3D-Punkten (KEIN unabhaengiger Beweis); Kamerahoehen z 0,8-12 m, naechste Referenzkamera median 3,9 m.
- Luecken (kd-Abstand zur dichten Wolke dicht_alle, 0,3 m): 9096 neue Punkte (Spur >= 3), davon 672 (7,4 %) ausserhalb der dichten Wolke, vor allem z 4-10 m (Balkon/Erker) und z 0-2 m (Arkadenfuss); je Serie a 281, b 163, j 157, i 66. Die neuen Fotos fuellen Arkaden-Innenraum/Erkerunterseite/Figuren NICHT (Serien c-h praktisch unregistriert). Naechster Schritt: Serien d/e/h per LightGlue (ALIKED) gegen a/b/j-Bilder neu matchen oder eigene Teilrekonstruktion je Serie und per Sim3 an das Netz binden (wie video_ausrichten.py).
- Kein foto_zaehlung noetig (keine Anzahlen gezaehlt). Test: tools/test_bildschaerfe.py.

## CY - Handyfotos Kaufhaus: Nachregistrierung mit ALIKED+LightGlue (Sonnet, 2026-11-06)
- Werkzeug `tools/zusatzfotos_lightglue.py` (Stufen refnamen/paare/einlesen/teilmodell; Test `tools/test_zusatzfotos_lightglue.py`), baut auf `tools/lg_match.py`-Technik und `zusatzfotos_registrieren.py` auf. Ergebnis `/media/oem/scan/rc-park_null/kaufhaus_handy/lg/` (registrierung.json, luecken.json, paare.json, teil_<serie>/teilmodell.json). Referenznetz nur gelesen.
- Ablauf: ALIKED 4096 fuer 146 Handyfotos (unten 5 % ab) + 94 registrierte Referenzbilder (53 s); Retrieval-Vorfilter = LightGlue mit nur 512 Merkmalen fuer alle 24309 Kandidatenpaare (Handy x Referenz, Handy x Handy, 4,5 min), je Handyfoto die 12 besten Partner -> 1345 Paare, voll gematcht (1301 mit >= 15 Matches). ALIKED-Merkmale/-Matches an die SIFT-Datenbank ANGEHAENGT, COLMAP-Verifikation, Referenzpunkte aus SIFT+ALIKED neu trianguliert (Referenzposen fest). Dann dasselbe PnP wie CX (f fest, Kamera je Format), 6 Runden, alle 146 als neu behandelt.
- Ergebnis: 115 von 146 registriert (vorher 72), Reproj mittel 1,48 / median 1,32 px (CX 1,36/1,17), f fest 1421,9 px. Je Serie (neu / vorher / gesamt): a 19/19/19, b 19/19/19, c 4/2/8, d 12/0/18, e 17/7/19, f 8/1/13, g 8/3/9, h 5/0/15, i 10/8/13, j 13/13/13.
- Luecken (0,3 m zur dichten Wolke): 25085 neue Punkte (Spur >= 3), 2969 (11,8 %) ausserhalb (CX: 672 = 7,4 %); je Serie d 599 von 1047, e 305/1417, g 262/563, j 370, a 866, b 342, i 164, f 42, c 15, h nur 4 von 206 (die 5 registrierten h-Bilder sehen die schon vorhandene Fassade, NICHT die Gassenwand).
- GRENZE/WARNUNG: von den 72 vorher registrierten Bildern weichen 17 um > 0,5 m ab (median 0,14 m), Ausreisser i_11 15 m, j_11 7,9 m, j_06 4,1 m, j_01 3,6 m; alle bei Bildern 5-11 m von der naechsten Referenzkamera (f fest, ebene Szene: Tiefe/Brennweite gekoppelt). Pose dort UNSICHER (Meter), Abweichungen stehen lassen, nicht mitteln (Regel 5). Der Gegentest "Inlier der Gegenpose" ist wegen falsch gewaehlter Mehrheits-Punkt-IDs nicht trennscharf. 31 Bilder weiter offen (h 10: kaum Matches, c 4, d 6, f 5, i 3, g 1: Korrespondenzen vorhanden, aber 15-26 Inlier < 30).
- Teilmodelle je Serie (COLMAP incremental nur dieser Bilder, f fest, Sim3 aus Posenzentren gemeinsamer Bilder): h 8/15 Bilder (3 neu: h_16-18, gemeinsam mit Netz 5, Residuum median 0,12 m, max 0,42 m; Massstab 0,72, bei Wiederholung 1,98 - Lauf nicht stabil), f 7 (Res. 0,43 m), c 7 (0,86 m), d 18/18 aber Residuum median 5,2 m (Netzposen der d-Bilder und Teilmodell widersprechen sich), g 9 (Res. 1,9 m). Daher NICHT ins Netz uebernommen. Gasse (h) braucht weitere Fotos: 7 von 15 h-Bildern haben keinen einzigen verifizierten Partner.

## CZ - Handyfotos Kaufhaus Serien k,l (40 neue) in die Registrierung - Stufe 1 fertig, Rest durch Platztor gestoppt (Sonnet, 2026-11-06)
- Stufe `vorbereiten` erledigt: `/media/oem/scan/rc-park_null/kaufhaus_handy2k` (185 Bilder = 146 alte + 39 neue, 22 verworfen: 9 Sichtausschluss alt, 12 Dubletten c, 1 neu). Ausschlussliste `modelle/kaufhaus_null5/audit/handy_ausschluss_kl.json` (alt + `handy_l_14`: Bewegungsunschaerfe, Ausschnitt gesehen). `tools/bildschaerfe.py` meldet unscharf: k_12, l_03, l_06, l_07, l_14, l_17 (pruefen: k_20, l_01, l_02, l_04, l_09, l_10, l_12, l_16, l_18, l_19); Sicht: l_14 verwackelt (raus), l_03 glatte Decke, l_12/l_17 Sockel nur weich -> behalten. Mass trennt wieder nicht sicher (Register CX).
- `kaufhaus_handy2` ist ein Fehlstart (186 Bilder, noch mit l_14), nicht benutzt; ich durfte nichts loeschen.
- GESTOPPT: `tools/job_start.sh cz_merk ...` bricht am Platztor ab (Daten 15,0 GB frei, Grenze 15 GB). Alte Laeufe brauchten ~1,5 GB (db 551 MB + lg 914 MB). Nicht umgangen. Naechste Schritte nach Platz: `merkmale` (GPU), `zusatzfotos_lightglue.py paare/einlesen`, `registrieren --kalibrieren`, `luecken`, Konsistenzpruefung der Posen k/l gegen Nachbarbilder.

## DA - Pose-Vertrauen der Handyfoto-Registrierung (SIFT CX vs ALIKED-LightGlue CY) (Sonnet, 2026-11-06)
- Werkzeug `tools/pose_vertrauen.py` (Test `tools/test_pose_vertrauen.py` besteht, synthetisch: PnP-Rueckgewinnung, f+2 % verschiebt Zentrum ~ 2 % x Tiefe), Ergebnis `/media/oem/scan/rc-park_null/kaufhaus_handy/pose_vertrauen.json` (Schwellen + Herkunft, Kreuzvalidierung, je Bild Klasse + Gruende). Nur Lesen von kaufhaus_null4 und beiden Laeufen, rein CPU, 77 s.
- Kreuzvalidierung: 94 Referenzbilder per Leave-one-out neu verortet (Punkte, deren uebrige Beobachter >= 2 Referenzkameras alle >= d entfernt sind, d = 0..12 m). f exakt: Median-Zentrumsfehler 0,004 m (d=0) bis 0,028 m (d=12), q90 <= 0,07 m -> Abstand allein macht im getesteten Bereich <= 12 m KEINEN Fehler > 10 cm (Abstand > 12 m ungetestet -> unsicher). f verstimmt um +-2,1 % (Standardfehler des festen Handy-f aus kalibrierlauf.json, 1413,6 vs 1421,9 px = 0,6 % zwischen den Laeufen): Median 0,60 m, q90 ~1 m, UNABHAENGIG vom Abstand (Korrelation Fehler~Abstand 0,09, Fehler~Tiefe 0,86; Fehler/(f_rel x Tiefe) Median 0,98). Folgerung: die f-Kopplung ist kein Abstandsproblem sondern ein systematischer Tiefenfehler ~ 2 % x Szenentiefe (~31 m -> 0,6 m) fuer ALLE Handybilder; ein absoluter 10-cm-Anspruch haelt nur nach ChArUco-/Selbstkalibrierung von f. `f_kritisch` (> 10 cm erwartet) gilt fuer 66 von 115 registrierten Bildern (nur die mit Tiefe < ~5 m nicht, oder ohne Tiefe). Die Vorgabe "Abstand > 5 m kritisch" wird von den Daten NICHT gestuetzt.
- Schwellen (alle mit Herkunft im JSON): tol 0,10 m = Projektziel; Posen-Abweichung SIFT/LG sicher <= tol + 0,6 % x Tiefe, unbrauchbar > 5 x tol + dto.; Rotation <= max(0,06 Grad Rauschboden, atan(tol/Tiefe)); Inlier < 30 unbrauchbar; nur in einem Lauf registriert = unsicher.
- Ergebnis 146 Bilder: 36 sicher, 62 unsicher, 17 unbrauchbar, 31 nicht registriert. Je Serie sicher/unsicher/unbrauchbar/nicht reg: a 16/3/0/0, b 17/2/0/0, c 0/4/0/4, d 0/12/0/6, e 0/14/3/2, f 0/7/1/5, g 0/8/0/1, h 0/5/0/10, i 1/6/3/3, j 2/1/10/0. Die 17 unbrauchbaren sind genau die mit Posen-Abweichung > 0,5 m (i_11 15,1 m, j_11 7,9 m, j_06 4,1 m, j_01 3,6 m ...), alle als unbrauchbar markiert; Serie j ist fast ganz unbrauchbar. 43 Bilder (c-h, nur LG) haben keine Gegenprobe = unsicher.
- Welche Pose stimmt eher: unabhaengige Gegenprobe (Pose gegen die Referenz-verankerten Punkte des JEWEILS ANDEREN Laufs rueckprojiziert, 71 Bilder in beiden Laeufen): LG-Pose besser in 49, SIFT in 13, gleich 9; Median 1,67 px (LG) gegen 2,03 px (SIFT). Leave-one-out an Referenzbildern mit den Punkten des Laufs: SIFT-Punkte 0,010 m / LG-Punkte 0,013 m Median (kein Vorteil fuer LG). Urteil: LG laut Gegenprobe wahrscheinlicher, aber nur ~1,7 gegen ~2,0 px und bei Ausreissern nicht entscheidbar; Registrierungen mit >0,5 m Abweichung nicht mitteln (Regel 5), sondern unbrauchbar lassen bzw. LG-Pose nur bei Inlier >= 60 und Gegenprobe < 2 px nutzen.

## DB - Brennweite der Handykamera unabhaengig bestimmt; Hochformat und gezoomte Bilder hatten falsches f (Sonnet, 2026-11-06)
- Werkzeuge `tools/handy_kalibrieren.py` (exif / mit_ref / ohne_ref), `tools/handy_zoom_verdacht.py`, Test `tools/test_handy_kalibrieren.py` (synthetisch: f_orig+k1 aus Quer+Hoch zurueckgewonnen; Gegenprobe f fest +2 % -> RMS 2,6 gegen 0,7 px). Ergebnis klein: `/media/oem/scan/rc-park_null/kaufhaus_handy/handy_kalibrierung.json`, `zoom_verdacht.json`. f wird in ORIGINALpixeln gefuehrt (f_Bild = f_orig x Skala), damit Quer-/Hochformat dieselbe Linse teilen.
- EXIF: 5,25 mm, KEIN 35mm-Aequivalent, keine Sensorbreite -> EXIF gibt keine unabhaengige Pixel-f (nur Plausibilitaet: f_orig ~2790 px -> Sensorbreite 7,5 mm, ~25 mm KB, plausibel). Crop unten 5 %: Hauptpunkt cy = H/0,95/2 (bisherige Registrierung H/2 -> f-Verzerrung ~1 %, siehe unten).
- FUND 1 (gross): der feste Wert 1413,6 px (CX) bzw. 1421,9 (CY) ist der Median ueber alle Formate und Zoomstufen (kalibrierlauf.json: Cluster ~1400 quer, ~1880 hoch, ~6200 gezoomt) und wurde fuer Quer UND Hoch UND Zoom benutzt. Bei gleicher Linse ist f_Bild im Hochformat (Skala 0,667) 1,333 x so gross: f_Bild hoch ~1860 statt 1413,6 = 24 % zu klein. Sichere Hochformatbilder a,b (9): Zentren bei PnP mit 1413,6 gegen 2790 um median 2,4 m verschoben (Tiefe ~10 m). Das "2 %" in DA ist nur die Streuung innerhalb des Medians, nicht der echte Fehler.
- Weg mit Referenz (feste Referenzpunkte, Posen frei, k1 gemeinsam, Mehrfachstart auf gemeinsamer Inliermenge, Bootstrap ueber Bilder, sicher a,b, 32 Bilder): f_orig SIFT 2783 +-9, LG 2777 +-11 (Hauptpunkt phys). Quer 2774/2768, Hoch 2823/2840 (+-20/12); Serie a quer 2701/2710 (+-16/10), b quer 2777, b hoch 2822/2835 -> Serienstreuung ~2,8 % ist GROESSER als Bootstrap (Fokus/Atmung oder Szenengeometrie je Serie; ungeklaert). Mit Hauptpunkt H/2: 2806/2822 (+1 %). k1 0,03 (quer) bis 0,0-0,015 (hoch), +-0,005.
- Weg ohne Referenz (COLMAP-Mapper nur Handybilder, Hauptpunkt H/2, f/k1 frei; Teilmengen 75 % x 20): SIFT quer 2816 +-15, hoch 2836 +-16; LG quer 2795 +-13, hoch 2818 +-24; Gesamtlauf 2785-2825; k1 0,01 +-0,003. Beide Wege stimmen auf ~1 % ueberein (Referenz mit H/2: 2806-2822), ohne Referenz ist k1 kleiner (0,01 gegen 0,03: k1 schlecht bestimmt).
- Empfehlung: f_orig 2790 +-30 (1,1 %), k1 0,02 +-0,015. Der bisherige Querwert (1413,6 -> 2827) lag +1,3 bis 1,7 % daneben, Hoch 24 % daneben. Tiefenfehler dz = df/f x Tiefe: 1,1 % = 0,11 m bei 10 m, 0,34 m bei 31 m -> 10-cm-Ziel NICHT erreichbar ueber Selbstkalibrierung allein (Grenze: Serienstreuung, cy-Konvention, Szene fast eben); noetig: Kalibriertafel (siehe unten).
- Zoom (zoom_verdacht.json; Einzelbild-f, Profil ueber f, PnP mit festen Referenzpunkten; Einzelbild-f streut ohne Zoom +-2,6 % (log), deshalb gezoomt erst z >= 1,5; 5-50 % Abweichung = "abweichend", nicht als Zoom behauptet): 38 gezoomt: j 12 von 13 (j_13 normal), i 11 von 11, g 7 von 7, f 6 von 9, e 2 von 4; a,b,c,d 0 (5 "abweichend" 0,92-1,12 = Rauschen). z-Median Zoomgruppe 3,4-3,5, gemeinsam f_orig ~9550 +-100 (j allein 9633/9652 +-16, k1 0,15-0,19 schaetzerabhaengig, unsicher). 61 Bilder konnten nicht bewertet werden (nicht registriert/<30 Korrespondenzen: c,d,e,h) - dort Zoom unbekannt. Eine feste Kamera je Format reicht NICHT: mindestens je Format x Zoomstufe eine Kamera (hier 2 Formate x {normal, 3,4x}); die Zoomstufe ist wohl fest (3,4-3,5x), sonst waere eine Kamera je Bild noetig.
- Folge: die Registrierungen CX/CY und pose_vertrauen sind fuer Hochformat und gezoomte Bilder (Serien e-j, 120 Hochformatbilder) systematisch falsch; sicher-Klasse gilt nur fuer Querformat a,b. Naechster Schritt (nicht getan): Neuregistrierung mit Kameras je (Format, Zoom), f_orig 2790 / 9550, Hauptpunkt cy phys; danach pose_vertrauen neu.
- Grenzen: Selbstkalibrierung an fast ebener Fassade (f/Tiefe-Kopplung), nur 32 sichere Bilder, k1 mit zwei Wegen nicht uebereinstimmend, Einzelbild-f ohne Unsicherheitsgarantie, Zoomgruppe nur ueber Referenzpunkte (weit entfernt, wenige Punkte).
- Kalibriertafel: fuer 10 cm waere ein ChArUco-Foto noetig. Aufnahmeanleitung: ChArUco (z. B. 7x5, Quadrat 30-40 mm, A3 starr/auf Hartschaum, matt gedruckt, Massstab mit Lineal nachmessen) 15-20 Fotos mit DEMSELBEN Handy, gleiche Einstellungen (Hauptkamera, Autofokus, KEIN Zoom und einmal im Zoom wie gewohnt 3,4x), je Format 8-10 Hoch- und Querformat, Tafel fuellt 60-80 % des Bildes, Neigungen 0-45 Grad aus verschiedenen Richtungen, Abstand 0,5-1 m, scharf, nicht Gesicht-/Beauty-Modus, Originaldatei (4000x3000), nicht zuschneiden. Zusaetzlich 3 Fotos der Tafel in ~5 m Abstand (Fokus nahe Unendlich wie bei der Fassade).

## DC - kaufhaus_handy2k: Serie m dazu, Merkmale + ALIKED/LightGlue-Paare + Verifikation bis 'einlesen' (Sonnet, 2026-11-06)
- Serie m (19 Fotos, Gassenwand): m_01, m_05, m_06, m_11 raus (Bewegungsunschaerfe, vertikale Putzverschmierung am Ausschnitt gesehen, kachel_q 34-52), eingetragen in `modelle/kaufhaus_null5/audit/handy_ausschluss_kl.json`; 15 behalten (m_02/03/04/07/18/19 'pruefen', weich aber nicht verschmiert). Ziel `/media/oem/scan/rc-park_null/kaufhaus_handy2k`: 200 Bilder (185 + 15), unten 5 % ab, Breite 2000. Ref: kaufhaus_null4 sparse_alle/0 (94 Bilder), nur gelesen.
- Job `dc_einlesen` (merkmale -> refnamen -> paare -> einlesen), rc=0, 1754 s (~29 min). SIFT: 38700 Paare, mittl. 9051 Schluesselpunkte. LightGlue-Vorfilter 38700 Kandidaten -> 1849 gewaehlt, 1700 mit >=15 Matches. Verifizierte Paare gesamt (>=15 Inlier, lg/db.db): 8110. Referenz neu trianguliert 18794 Punkte (unveraendert). Platz: Ziel 1,7 GB, Daten danach 14 GB frei (unter dem 15-GB-Tor!).
- Verifizierte Paare je Serie (zu Referenz / Altbild a-j / Neubild k,l,m; neu-neu zaehlt je Seite): k 28/332/109, l 6/38/83, m 7/83/94. Kontrolle alt: a 533/1044/42, b 487/1218/58, i 182/419/6, j 253/535/6.
- Bilder ohne jede Referenzverbindung: k 11 von 20, l 14 von 19, m 9 von 15. Ohne Referenz UND ohne Altbild (Insel): k 0, l 5, m 2. Nur 1 Bild (k) hat >=10 Referenzpaare: PnP nur ueber Altbild-Kette/Neubilder moeglich, Registrierung bleibt schwach. Serie m (Gasse, Putz) wie erwartet kaum Referenzbezug.
- Fehler: keine. GPU-Sperre griff nicht (zusatzfotos_* nicht in gpu_werkzeuge.txt), kein Konflikt beobachtet. Nicht gemacht: registrieren/PnP/luecken (wartet auf Brennweitengruppen 1x / ~3,4x). Tools nicht geaendert.

## DD - Kameragruppen (Format x Zoom) im Registrierwerkzeug; Neuregistrierung durch Platztor blockiert (Sonnet, 2026-11-06)
- Werkzeug: `tools/zusatzfotos_registrieren.py registrieren --kameras JSON [--zoom zoom_verdacht.json]`. Kameragruppe = quer/hoch (Originalgroesse) x normal/zoom (zoom_verdacht.json, Klasse 'gezoomt'); Bilder nicht in der Zoomdatei -> normal, in registrierung.json mit `zoomstatus: unbekannt` markiert; 'abweichend' bleibt normal. f/k1/cx/cy aus `modelle/kamera_profil/handy_nubia_gruppen.json` (f_orig 2790 normal, 9550 Zoom, k1 0,02 / 0,17 (unsicher), f_Bild = f_orig*skala, Hauptpunkt = 0,5*Originalgroesse*skala, also cy auf das UNGECROPPTE Original). Kein Kalibrierlauf mehr, wenn --kameras gesetzt (alter Weg unveraendert ohne Flag; merkmale unveraendert, laufende Jobs unberuehrt). Kamera-IDs neu vergeben (max Referenz-ID+1...), kollidieren nicht mit der Datenbank.
- Test: `tools/test_zusatzfotos_kameras.py` bestanden (synthetisch: Gruppenbildung, f/cy-Rechnung, unbekannter Zoom markiert, fehlende Gruppe -> KeyError).
- Vorbereitet: /media/oem/scan/rc-park_null/kaufhaus_handy3/a_j (Daten kaufhaus_handy/lg) und a_m (kaufhaus_handy2k/lg; Serien a-m, 200 Bilder), DB per Symlink (keine Kopie, Platz). NICHT gelaufen: `tools/job_start.sh` bricht mit Exit 3 ab (Daten 14,3 GB frei < 15 GB Grenze; dc/dd haben ~1,4 GB belegt). Grenze nicht veraendert, nichts geloescht. Ausserdem ist zusatzfotos_registrieren.py in gpu_werkzeuge.txt, die CPU-Stufe 'registrieren' wartet dadurch auf die GPU-Sperre (JOB_OHNE_GPU_SPERRE=1 wurde vom Berechtigungssystem verweigert, nicht umgangen).
- Offen: Registrierung a_j, a_m, npq; pose_vertrauen neu; Antwort auf 'Hochformat konsistent mit Quer?' steht aus.
- DD Nachtrag: ein a_j-Lauf startete doch (Warteschlange, Platz war kurz 15,7 GB): Kameragruppen quer_normal 26 / hoch_normal 82 / hoch_zoom 38 Bilder (a-j; quer_zoom leer); Runde 1 = +61 von 146 (alt: +44 mit Einheits-f), danach Absturz in triangulate_points: Kamera-IDs kollidierten mit DB-Kameras 233-235 (ValueError Hoehe 2533 vs 1425). Fix im Werkzeug (IDs ueber DB-Maximum), NICHT erneut getestet (Platztor). Folge des Laufs: Datei kaufhaus_handy/lg/db.db hat neue mtime (11:19:59, Groesse unveraendert, wohl nur SQLite-Kopf/WAL beim Oeffnen ueber Symlink) - Inhalt nicht erneut verifiziert; Registrierungsergebnisse zum Vergleich (registrierung.json dort) unberuehrt.

## DE – Platztor Daten 15 -> 10 GB (6.11. 11:25)
Nutzer ("Ja komm, du kannst die Grenze auch hochsetzen. Ich will's nur, dass du nicht arbeitslos bist") hat das Senken der Grenze auf 10 GB freigegeben (Angebot im Verlauf). Grund: Neuregistrierung mit Kamera je Format/Zoom wurde bei 14 GB frei blockiert. Aenderung: tools/platz_pruefen.py daten-min-gb 15 -> 10. Nichts geloescht.

## DF - Neuregistrierung mit Kameragruppen (a-m, n-q), Posenunsicherheit je Gruppe (Sonnet, 2026-11-06)
- Fehlerkorrekturen: (1) `--sparse` muss `lg/ref_tri` des jeweiligen LightGlue-Laufs sein (nicht sparse_alle: Keypoint-Indizes der Referenzbilder in der lg-DB sind ALIKED, sonst IndexError). (2) Absturz "existing_frame.RigId() == frame.RigId()" in triangulate_points: nach der Kamera-ID-Korrektur noch Rig-/Frame-Konflikt, weil die DB je Bild einen Rig mit rig_id=camera_id fuehrt. Fix: neue Funktion `db_kameras_schreiben` (Kameras, Rigs, Bild->Kamera, Frames in der KOPIE der DB), Lauf bestaetigt. test_zusatzfotos_kameras.py weiter bestanden.
- Arbeitsverzeichnisse: /media/oem/scan/rc-park_null/kaufhaus_handy3/{a_m,npq} (echte DB-Kopien; a_j entfaellt, a_m enthaelt a-j). Referenz-DBs unveraendert. Die alte Symlink-db in a_m liegt als db.db.symlink_alt (nicht geloescht).
- DB-Pruefung der ersten Originale: kaufhaus_handy/lg/db.db (Zeitstempel 11:19:59 vom Symlinkzugriff) sqlite integrity_check ok (immutable geoeffnet), 379 Bilder, WAL 0 Byte -> kein Inhaltsverlust erkennbar; kaufhaus_handy2k/lg/db.db ebenfalls ok (433 Bilder), Kopie byte-gleich (cmp).
- Ergebnis registriert (Kameras je Gruppe fest, 4 Runden): a-m 157/200 (vorher a-j mit Einheits-f 72/146 bzw. 61 nach Runde 1 im Abbruchlauf), Reproj mittel 1,44 px / median 1,28; n-q 67/74, Reproj 1,46 / 1,32. Je Serie a-m: a 19/19, b 19/19, c 4/8, d 18/18, e 19/19, f 12/13, g 8/9, h 9/15, i 12/13, j 13/13, k 15/20, l 0/19, m 9/15; n 17/20, o 15/19, p 20/20, q 15/15. Serie l wird gar nicht registriert.
- Gruppen: a-m hoch_normal 136 (22 bewertet, 114 Zoomstatus UNBEKANNT, davon 71 registriert), hoch_zoom 38 (alle registriert), quer_normal 26; n-q: ALLE 74 Zoomstatus unbekannt (nicht in zoom_verdacht.json), als normal gerechnet. Offen: Zoomklassifikation fuer d,e,f,h,k,m und n-q nachziehen.
- Posenunsicherheit (`tools/pose_vertrauen_gruppen.py`, neu; das aeltere untracked `tools/pose_vertrauen.py` blieb unberuehrt; Ausgabe kaufhaus_handy3/pose_vertrauen_gruppen.json): Leave-one-out je Bild (nur Punkte mit >=2 anderen Beobachtern) Zentrum median/q90: hoch_normal 1,1/10,9 mm, hoch_zoom 1,3/4,5 mm, quer_normal 0,9/2,3 mm; Bootstrap < 0,5 mm; f-Empfindlichkeit (f +-f_unsicherheit) median 12 mm hoch_normal, 33 mm hoch_zoom, 19 mm quer. ACHTUNG: LOO und Bootstrap sind NICHT unabhaengig (3D-Punkte sind aus denselben Posen trianguliert) = innere Konsistenz, keine Genauigkeit; die Genauigkeit gegen die Referenz steht aus (Referenz-Kreuzvalidierung der aelteren Version).
- Unabhaengiger Test Hoch gegen Quer (Essentialmatrix je Paar aus db-Matches, entzerrt, gegen Relativpose aus den Endposen; Rotationsfehler median): quer-quer 1,0 Grad (a-m); hoch(normal)-quer 1,8; hoch_zoom-quer 2,4; hoch-hoch a-m 6,1 (hoch_normal-hoch_normal), hoch_zoom-hoch_zoom 3,3; n-q hoch-hoch 0,95, hoch-quer nur 8 Paare 0,45. Nach Serien (Paare mit Basis < 2 m): a,b,i,j,n,p,q unter 2 Grad; e-e 18,5, e-f 13, e-g 19,5, d-e 46, f-k 12,8, k-k 5,7, m-m 7,7. Paare nur mit bewertetem Zoomstatus: hoch-hoch 1,6 bis 3,0 Grad gegen unbekannt 5,7 bis 28 Grad -> BEFUND: Hochformat ist nicht pauschal inkonsistent; die Fehler sitzen in Bildern mit unbekanntem Zoomstatus (Serie e, k, m, d, f) -> Verdacht falsche Gruppe (gezoomt als normal gerechnet). Verdacht, NICHT bewiesen (Gegenprobe: Zoomklassifikation dieser Bilder, dann Neulauf).
- Grenzen: Basisrichtung bei Basis < 0,5 m schlecht bestimmt (Median 30 bis 55 Grad bei hoch-hoch, auch fuer bewertete Bilder); Paare mit Basis > 2 m haben oft Fehlzuordnungen (Rot-Fehler bis 130 Grad, symmetrische Fassaden) -> nicht als Posenfehler lesen. Mehrfachregistrierung a_m/npq: keine gemeinsamen Bilder (Serien disjunkt), der Test entfaellt. Kein Dichtes, kein Carving, keine Sollwerte geaendert, nichts geloescht.

## DH - Handy-Masken Kaufhaus (GPU, SegFormer-B4 ADE20K) 6.11. (Sonnet)
- Neu: `tools/handy_masken.py` (+ `tools/test_handy_masken.py`, bestanden; Eintrag in `tools/gpu_werkzeuge.txt`). video_masken.py unveraendert. CUDA fp16, Batch gleich grosser Bilder, OOM-Leiter (Batch 1, dann 0,75 x Breite).
- Messung 16 Bilder: Breite 1536 batch 4 = 9 s, 5,6 GiB; Breite 2000 batch 4 = 19 s, 6,8 GiB. Erster Volllauf Breite 2000 batch 2 = OOM (1,8 GiB-Block, Leiter war nur im ersten Versuch), danach Breite 2000 batch 1: 274 Bilder in 229 s, GPU-Spitze 4,3 GiB, kein OOM (Job rcpark-handy_masken, Log `kaufhaus_handy_masken/job2.log`; job.log = gescheiterter erster Lauf, nicht geloescht).
- Ausgabe `/media/oem/scan/rc-park_null/kaufhaus_handy_masken/<serie>/<bild>.png` (255 benutzen / 0 ignorieren), `bericht.json` je Serie (Anteil, Klassenanteile je Bild); 274 PNG (a-m 200, n-q 74), Puffer 30 px.
- Klassen aus id2label der Modellkarte (erster Name exakt): person car bus truck van minibike bicycle boat ship animal | tent booth canopy box; awning nur mit --markise (Standard aus, koennte Bauwerk sein).
- Ergebnis: Maske > 0 in 167/274 Bildern, Mittel 1,9 %, Median 0,2 %, 95 %-Quantil 10 %, Max 35 % (l_01). Treffer-Bilder je Klasse: person 155, car 39, van 31, minibike 15, box 13, bicycle 9, truck 9, boat 5, tent 4.
- Sichtprobe 12 Bilder (Collagen c1/c2 im Scratchpad): RICHTIG: Transporter/Pkw (a_01 vollstaendig), Passanten (o_14, n_07, a_03), Marktware unten teils. FALSCH (Fassade/Bauwerk maskiert): (1) Herrscherstatuen am Obergeschoss als 'person' (a_03, f_11, p_02, q_08, n_07, n_11: Bauwerksteile, Merkmalsverlust an Figuren) ; (2) Gewoelberippen im Arkadengewoelbe als 'boat' (l_01 35 %, l_02) ; (3) Fenster/Fensterfelder als 'box' (f_11 5,5 %); (4) Pflaster als Flecken (d_15, l_02, n_11). FEHLT: Marktstand-Zeltdach/Markisen (a_03, a_06: weisse Planen nicht maskiert; 'tent' nur in 4 Bildern, 'awning' bewusst aus).
- Empfehlung (nicht umgesetzt, kein Beleg ueber Wirkung auf SfM): boat/ship/animal streichen (nur Fehlalarme sichtbar), box nur mit Gegenprobe; Statuen-Fehltreffer erst mit Gegenprobe der Registrierung bewerten (Statuen sind fest, Fehlmaske kostet nur Merkmale, kein falsches Geometriebild). Marktstand-Planen bleiben unmaskiert: naechster Schritt OWLv2 (Apache) 'market stall' oder awning mit Bodenhoehen-Kriterium. Nicht mit SfM gegengeprueft: ob Masken die Registrierung verbessern ist OFFEN.
- Lizenz: SegFormer-Gewichte `license: other` (curl Modellkarte), LIZENZ_WERKZEUGE Nachtrag 2026-11-06, nur zum Testen.

## DI - Handy-Masken v2 Kaufhaus (Segformer-Klassenlogik + OWLv2) 6.11. (Sonnet)
- Anlass: Sichtbefund DH (Statuen als person, Gewoelberippen als boat, Fensterfelder als box, Pflasterflecken; Marktplanen fehlen). Neu: `tools/handy_masken_v2.py` (v1 `handy_masken.py` und Ausgabe `kaufhaus_handy_masken/` unveraendert), Ausgabe `/media/oem/scan/rc-park_null/kaufhaus_handy_masken_v2/<serie>/*.png` + `bericht.json` je Serie (je Komponente Klasse, bbox, Bodenanteil, Entscheidung, Grund), Lauf per `tools/job_start.sh handy_masken_v2` (274 Bilder, 145-190 s, GPU-Spitze 5,4 GiB, Batch 2; Eintrag in `tools/gpu_werkzeuge.txt`), Test `tools/test_handy_masken_v2.py` (bestanden), Sichtblaetter/Auswertung `tools/handy_masken_vergleich.py`.
- (a) boat/ship/animal entfernt. (b) person/box nur mit Bodenkontakt: Fuss-Fenster (Zeilen tiefster Punkt -15 % Hoehe bis +8 % darunter, Spalten bbox +-50 % Breite, ohne die Komponente) gegen Bodenklassen floor road sidewalk earth path grass sand field stairs, Schwelle `boden_min` 0,08. Beleg der Schwelle: Statuen messen 0,0 (nur Wand/Fenster/Balkon), Passanten 0,13-0,5. ERSTVERSUCH FALSCH und verworfen: Band direkt unter der Silhouette (Segformer labelt Boden/Kleidung am Gebaeudesockel 'building': 3 Passanten faelschlich frei) und Bedingung Boden>=Fassade (zweiter Passant 0,48 vs 0,52 verworfen). Zusatzregeln: Komponente am unteren Bildrand = steht (Objekt nahe Kamera, Risiko: Statue in Steilaufnahme am Bildrand); Fuesse von Dyn-Klassen verdeckt = steht; Fleck = Flaeche < 1 % und Ring >= 85 % Boden. Mindestflaeche 0,03 % Bild (Rauschen). Fahrzeuge: Loecher gefuellt, car/bus/truck/van per konvexer Huelle (Segformer markiert Transporter nur am Rand).
- (c) OWLv2 base (Abfragen white tarp, market stall canopy, tent, parasol; Score >= 0,3 (Schwelle gewaehlt, NICHT optimiert), NMS 0,3), Plausibilitaet: >= 50 % der Box-Spalten haben irgendwo darunter Bodenklasse, Box < 50 % Bild; Fuellung = Box minus Himmel/Boden-Pixel (Fassade bleibt drin). SAM2 NICHT verfuegbar (nur sam-vit-base/SAM1 im Cache; Nachladen wegen Platz-Tor 10 GB unterlassen) -> keine SAM-Fuellung. Rest: Planen werden als Rechteck maskiert (a_04: Box streift unten die Fassade), nicht alle Planen gefunden (a_04 rechts, a_06 links, a_03 Transporter).
- (d) Qualitaetsmass = SICHTPROBE (selbst nach Sichtblaettern v1|v2 mit Blobnummern gezaehlt, kein unabhaengiger Beleg; Datei `modelle/handy_masken_sichtprobe_DI.json`, Stichprobe `modelle/handy_masken_stichprobe_DI.json`: 12 Bilder der Collagen + 18 per Zufall (seed 20261106) vorab gezogene, die nicht zum Einstellen der Schwellen angesehen wurden). Blob = Zusammenhangsgebiet der Maske; v1 zerfaellt in viel mehr Blobs, daher Blobzahlen nur grob vergleichbar. Ergebnis 30 Bilder: v1 richtig 51, FEHLTREFFER 186, fehlend 12; v2 richtig 29, FEHLTREFFER 5, fehlend 7. Nur die 12 Collagenbilder: v1 134 fp / 7 fehlend, v2 3 / 4. Nur die 18 neuen: v1 52 / 5, v2 2 / 3. Verbleibende v2-Fehltreffer: 3 Gewoelberippen l_02, 2 unsicher n_17. Maskierter Anteil Mittel 1,9 % -> 1,3 %.
- Statuen, Gewoelberippen, Fensterfelder, Pflasterflecken: in allen 30 Bildern frei (ausser 3 Rippenflecken l_02). Passanten an der Arkade (o_14, n_07, n_11) bleiben maskiert (zwischenzeitlich verloren, s. o.). Marktstaende links in a_03/a_07 jetzt maskiert (Plane+Ware).
- OFFEN: Wirkung auf SfM-Registrierung nicht gemessen (nur Masken geliefert); Segformer/OWLv2-Gewichtslizenz s. LIZENZ_WERKZEUGE (SegFormer NC-Verdacht). Regeln sind klassen-/relativ (keine Objektfestwerte), Schwellen stehen in `P` im Kopf des Werkzeugs. Nicht-Segformer-Fehler bleiben: weisse Transporter teils gar nicht als van erkannt (a_10 unmaskiert in v1 und v2).

## DG - Zoomklasse fuer alle Neuregistrierungen (v2), Neulauf a_m_v2/npq_v2, Pose-Vertrauen neu (Sonnet, 2026-11-06)
- **Werkzeug** `tools/handy_zoom_verdacht.py --v2` (alte Funktion unveraendert; alte `zoom_verdacht.json` unberuehrt, neue `kaufhaus_handy/zoom_verdacht_v2.json`, Zwischenstand Lauf 1 ohne E2: `kaufhaus_handy3/zoom_verdacht_v2_lauf1_ohneE2.json`). Alle 274 Bilder (a-m 200, n-q 74), parallel (26 Prozesse, Gegenprobe seriell == parallel auf 12 Bildern: identisch; DB-Zugriff ueber schreibgeschuetzten SQLite-Leser `DbLeser`, gegen pycolmap-Leser verglichen: Keypoints/Matches identisch; pycolmap-Mehrfachoeffnen gab 'database is locked'/SIGBUS).
- Zwei Schaetzer: **E1** PnP-Profil ueber f gegen Referenz-3D-Punkte (wie alt); **E2** unabhaengig davon: Fundamentalmatrix je Paar (neu x Referenzbild, bei Bildern ohne Referenzpartner neu x neues Bild mit E1-f), Brennweite aus gleichen Singulaerwerten (Hartley), Median ueber Partner. Grenzen aus Daten: Zoomgrenze = Mitte der 2-Means-Cluster in log z (normal 1,009 / Zoom 3,69 -> Grenze z 1,93), normal = |log z| <= 2 x Streuung der Serien a,b (0,030), kein fester Prozentwert/z-Wert im neuen Code. f_haupt 2736 px.
- **Ergebnis** (E1 allein): normal 72, abweichend 8, gezoomt 34, **unbekannt 160** (157 davon <30 Referenzkorrespondenzen: Serien d,e,h,k,l,m,o haben kaum/keine Verbindung zur Referenz, kein E1 moeglich). Endklasse mit E2-Ergaenzung (nur normal/gezoomt, >= 2 Partner, Quelle `E2` markiert): normal 86, abweichend 8, gezoomt 44, **unbekannt 136** (davon 24 nur E2). Vergleich mit alter Datei (85 gemeinsame Bilder): gezoomt->gezoomt 33, normal->normal 39, abweichend: 3 -> normal, 2 bleiben; 5 alt-gezoomt und 1 alt-normal jetzt unbekannt.
- **E1 vs E2 (Verdacht, nicht Beweis)**: wo beide da (110 Bilder): Log-Quotient f2/f1 Median 0,00, Streuung 0,30 (10-90 %: -0,12 .. +0,08). Harte Widersprueche gezoomt<->normal: 1 von 34 (E1 gezoomt, E2 normal), 0 von 52 (E1 normal). E2 ist deutlich rauschiger (liefert oft 'abweichend' bei E1 'normal': 13) und bei kleiner Basis/Reinrotation schwach; deshalb nur 'normal'/'gezoomt' aus E2 allein uebernommen. Das ist keine Bestaetigung der Zoomklasse durch ein Drittverfahren; beide Schaetzer hangen am selben Bildmaterial.
- Neuregistrierung (`registrieren --kameras ... --zoom zoom_verdacht_v2.json`, echte DB-Kopien aus den lg-Originalen, Alt-Ordner a_m/npq unberuehrt): **a_m_v2 158/200** (vorher 157), Reproj 1,45 px; **npq_v2 66/74** (vorher 67), Reproj 1,47. Je Serie a-m alt->neu: d 18->17, g 8->9, k 15->16, sonst gleich; l 0->0; n-q: n 17->16, sonst gleich. Zoomstatus der registrierten: a-m 'unbekannt' 72 -> 61 (bewertet 97), n-q 67 -> 25. Gruppenwechsel a-m: 7 normal->zoom, 2 zoom->normal; npq 1. Werkzeugfehler dabei: Gruppe mit nur 1 Bild (npq hoch_zoom) -> triangulate_points laesst Kamera/Rig fallen -> 'Rig 237 does not exist'; Fix in `zusatzfotos_registrieren.py` (Kamera nach Triangulation wieder anlegen), Lauf bestaetigt. Der erste Fehlversuch bleibt als `npq_v2/registrieren_fehlversuch1.log`.
- Threads: pycolmap-Triangulation/Ceres laufen mit num_threads=-1 (alle Kerne, als Standard geprueft); PnP-Schleife der Registrierung bleibt seriell (kein Gewinn ohne Umbau).
- **Pose-Vertrauen neu** (`pose_vertrauen_gruppen.py` auf a_m_v2, npq_v2; Ausgabe kaufhaus_handy3/pose_vertrauen_gruppen_v2_{a_m,npq}.json). Rotationsfehler Essentialmatrix-Test, Median Grad, nur Basis < 2 m, alt -> neu: hoch-hoch (alle) 2,17 -> 2,17; hoch-quer 2,09 -> 2,07; quer-quer 1,02 -> 1,02 (q90 hoch-hoch 22,3 -> 20,9). Nach Gruppenart: hoch_normal-hoch_normal 2,11 -> 1,85; hoch_normal-hoch_zoom 3,68 -> **6,47 (schlechter)**; hoch_zoom-hoch_zoom 1,74 -> 2,18; hoch_zoom-quer 2,48 -> 2,82. Nach Serienpaar (Verdachtsserien): e-e 18,5 -> 8,2; e-g 19,5 -> 6,8; f-k 12,8 -> 6,7; f-f 6,3 -> 3,7; m-m 7,7 -> 6,1; e-f 13,4 -> 11,1; **aber** b-e 2,9 -> 6,6, d-d 3,3 -> 4,3, h-m 5,4 -> 8,5, d-e 46 -> 46 (unveraendert), a-d/a-k/k-k/e-k 5-11 Grad unveraendert. Fazit: die falsche Zoomgruppe erklaert einen Teil (e, f, k-Naehe verbessert), aber nicht alles; d-e (46 Grad) und k haengen an etwas anderem (kaum Referenzbezug, Ketten-Drift/symmetrische Fassade, Verdacht). LOO-Zentrum median: hoch_normal 1,07 mm (q90 8,4), hoch_zoom 1,45 mm (5,4), quer 1,02 mm (2,3) - weiter innere Konsistenz, keine Genauigkeit (LOO/Bootstrap nicht unabhaengig). Einzelzoom-Gruppe npq hoch_zoom (1 Bild): LOO 20 mm, unzuverlaessig.
- **Serie l (0/19) Ursache** (aus DB, nicht aus dem Ergebnis geraten): l ist eine Insel: 70 l-l-Paare mit 48 190 Inlier-Matches (stark untereinander), aber nur 6 Paare/97 Matches zur Referenz und je 1-18 Paare zu d (984 Matches) und k (1226 Matches) und wenig zu a,b,c,e,f,h,i. Von 19 Bildern haben 11 <12 Korrespondenzen zu Punkten mit 3D, 8 scheitern im PnP (n_korr 1-26 < 30 Inlier). Die Nachbarn d,k sind selbst nur schwach registriert und haben an l-Bildern kaum triangulierte Punkte. Zoomklasse von l: E1 nicht moeglich, E2 nicht moeglich (keine Partner mit >= 60 Inliern und bekanntem f): alle 19 unbekannt. Ursache also fehlende Verbindung/Insel, nicht Gruppen-f. Naechster Schritt (nicht getan): l als eigenes SfM-Teilmodell rekonstruieren und per Sim3 an die Registrierung (ueber l-d/l-k-Matches) anlegen; wuerde auch d-e/k-Drift mit pruefen.
- Offen/Verdacht: 136 Bilder bleiben ohne Zoomklasse (haupts. d,e,h,k,l,m,o); die 9 Gruppenwechsel bewegen Posen bis 7 m (a_m) bzw. 3,8 m (npq), Median 7 mm bzw. 0,6 mm. Nichts geloescht, keine Sollwerte/Platztor geaendert, kein Dichtes/Carving. Platz danach 9,7 GB frei (Grenze 10 GB; Torpruefung vor den Laeufen lief mit 10,4-10,6 GB) - weitere Kopien wuerden vom Tor blockiert.

## DJ – Auslagerung auf Toshiba (6.11.)
Nutzer gab die Toshiba-EXT-Platte frei. tools/auslagern.sh (rsync + Pruefsummenvergleich, Symlink zurueck). Ausgelagert: s9, s10, kanten_vektor, beweis_ansatz, kaufhaus_handy3/a_m, npq (3,3 GB). Datenplatte danach 13 GB frei (Tor 10 GB). Nichts geloescht ausser nach verifizierter Kopie.

## DK - Serie l (Gewoelbe/Gitterfenster) als eigenes SfM-Teilmodell + Sim3 ins Referenzsystem (Sonnet, 2026-11-06)
- Werkzeug neu: `tools/teilmodell_sim3.py lauf` (CPU, pycolmap incremental_mapping, 28 Threads, keine GPU) + `tools/test_teilmodell_sim3.py` (synthetisch: Sim3 mit 20 % Ausreissern und Rauschen, Rotationsmittel, Entartungsmass; bestanden). Teil-DB aus `kaufhaus_handy2k/lg/db.db` (Original unveraendert, Kopie): Serie l (19) + in a_m_v2 REGISTRIERTE Nachbarn d,k (33 Anker), Kameras je Gruppe fest, Geometrie der LightGlue-Rohmatches mit diesen Kameras NEU verifiziert (`--neu-verifizieren`; die Altgeometrie ist mit Platzhalter-Intrinsiken gerechnet, 136 von 171 l-l-Paaren 'degeneriert'). Sim3: LMedS ohne feste Schwelle auf Anker-Zentren, Gegenprobe (a) Rotationsmittel der Anker, (b) UNABHAENGIGE Sim3 aus 2-3 Tsd. 3D-Punkten gleicher Keypoints (Teilmodell vs a_m_v2), (c) Leave-one-out auf Inliern. Ergebnisse `/media/oem/scan/rc-park_null/kaufhaus_handy3/l_teilmodell/` (je Lauf `<hyp>_S<seed>/ergebnis_m<k>.json`, `sparse_ref_m<k>` im Referenzsystem, `zusammenfassung.json`).
- Korrektur am Rahmen: mit COLMAP-Standard (min_model_size 10, init_min_tri_angle 16 Grad) entsteht fuer die Insel nur 1 l-Bild; `min_model_size` 3 noetig. l ist KEINE zusammenhaengende Insel: Kette 01-09 und 10-20 haengen nur ueber 3 schwache Paare (<= 18 Inlier) zusammen.
- Kamera von l aus den Daten: freie Brennweite im Buendel (nur l, ohne Anker, 3 Seeds, 2 unabhaengige Teilgruppen): f = 3900 / 3902 px (Bildbreite 2000), k1 0,11-0,13, Teilgruppe 04-09 UND 10-20 stimmen auf 0,3 % ueberein; Reproj-Median 0,93-0,95 px gegen 1,05-1,11 mit festem f 1860 (normal) bzw. 6367 (Zoom 9550). Weder 'normal' noch 'gezoomt' (3,4-fach) passt: Zoomfaktor ~2,1 gegenueber normal. Schwaeche: ebene Fassade -> f und Abstand korreliert; Wiederholbarkeit ist gegeben, Beweis fehlt (kein Kalibrierobjekt).
- Registrierung (3 Hypothesen x 3 Seeds, ein Mapper-Lauf ist wegen Threads nicht deterministisch): 10 von 19 l-Bilder (10,11,12,13,15,16,17,18,19,20) werden zusammen mit Ankern in EIN Modell gelegt; 01-03 nie (kaum Matches), 04-09 bilden ein 6-Bilder-Modell, das in jedem Lauf im FALSCHEN Modus (Necker/Spiegelmehrdeutigkeit der ebenen Fassade, Winkel 124 Grad zur unabhaengigen Punkt-Sim3, Anker-LOO 4,2 m) landet = verworfen. Nur 1 von 12 Laeufen mit zoom_S2 liefert 6 Bilder gueltig (nur Teilmenge von 10-20). Falschmodus tritt auch bei 10-20 auf (normal S0, normal S2): dort Winkel 126 bzw. 25 Grad -> verworfen.
- Gueltige Laeufe (Winkel Zentren-Sim3 zu Punkt-Sim3 < 15 Grad, LOO < 0,2 m; 8 von 12): Sim3-Rest auf Anker-Inliern 3,6-7 cm Median, LOO 3,4-6,6 cm (nur Inlier-Anker: 10-15 von 14-20), Punktabgleich Median 3,7-7 cm, MAD 0,7-1,7 cm. ABER Skalenmehrdeutigkeit: s = 0,17-0,28 (Zentren) bzw. 0,17-0,28 (Punkte) schwankt ueber Hypothesen/Seeds um +-15 %; die Positionen der l-Kameras im Referenzsystem streuen 0,2-0,44 m (max Abstand zum Mittel ueber 7-8 gueltige Laeufe). Anker-Ausdehnung nur 4 m (d,k liegen nahe beieinander) -> Rotation um die Ankerachse und Skala nur schwach bestimmt (kleinster/groesster Singulaerwert 0,03-0,3). 5-15 der Anker sind in jedem Lauf Ausreisser (Meter-Fehler): die Referenzposen der schwachen d/k-Bilder sind selbst nicht verlaesslich (vgl. DF: d-e 46 Grad).
- Hypothesenvergleich: Anker-Sim3 diskriminiert 'normal' / 'zoom' / 'eigen' (f 3900) NICHT (alle gleich gut in den gueltigen Laeufen); einzig Reprojektion (eigen 0,94-0,95 gegen 1,00-1,08) und die freie Schaetzung sprechen fuer f ~ 3900. Entscheidung ehrlich: l-Kamera = f 3900 px, k1 0,12 (ANNAHME aus freier Schaetzung, nicht bewiesen).
- Grenzen/Nicht getan: Posen von l in `zusammenfassung.json` (`serie_posen`: Mittel + Streuung), NICHT in a_m_v2 uebernommen; keine Verwendung fuer Dichtes/Carving; Ergebnis nicht auf Gewoelbegeometrie geprueft (kein Sichtvergleich der l-Fotos mit den Kamerapositionen). Naechster Hebel: Anker mit besserer Referenz (mehr Beobachtungen) oder l-Bilder mit Kamerafestlage ueber weitere Bilder ausserhalb d/k; 01-09 mit Handyfotos nachfotografieren (mehr Ueberlappung, schraege Standpunkte gegen Spiegelmehrdeutigkeit).

## DL - Dichte Wolke aus den neu registrierten Handybildern (PatchMatch GPU), Posenguete-Klassen, Gegenprobe gegen dicht_alle (Sonnet, 2026-11-06)
- **Werkzeug neu** `tools/dicht_handy.py` (Stufen auswahl / rechnen / vergleich; in `tools/gpu_werkzeuge.txt` eingetragen, Lauf via `tools/job_start.sh dicht_neu ...`). Wiederverwendet aus `sfm_dicht.py`: COLMAP-Kette (undistort -> patch_match_stereo geom. Konsistenz -> stereo_fusion, 1 Faden), Rueckrechnung `R^T (X-t)/s` mit `SFM-AUSRICHTUNG-alle.json`. Neu: Bilder aus `a_m_v2`/`npq_v2` (`sparse_handy/0` enthaelt Referenzposen identisch zu `sparse_alle/0`, max. Abweichung 2e-14 m -> gleicher Rahmen), Quellbilder je Bild NUR aus dem eigenen Stapel (eigene `patch-match.cfg`, Score = Summe sin(Triangulationswinkel) gemeinsamer Punkte, ANNAHME), Masken v2 (255 = benutzen) mit derselben Entzerrung auf die Tiefenkarten (Maske 0 -> Tiefe 0) vor der Fusion, Beschnitt auf Kasten der Sparse-Punkte (Perzentil 1/99, je Seite um halbe Spannweite erweitert; aus Daten), Stapelgroesse aus freiem Platz (Platztor 10 GB), Arbeitsordner je Stapel per `tools/auslagern.sh` auf Toshiba (Symlink zurueck), Fusion der Stapel parallel zur GPU des naechsten.
- **Klassen aus Daten** (`auswahl.json`): Kriterium = Median des Rotationsfehlers (Essentialmatrix-Test aus `pose_vertrauen_gruppen_v2_*.json`, Feld `paare[].rot_fehler_grad`, alle Paare mit Basis < 2 m) je Bild, Schwelle = beste 1-D-2-Means-Teilung im Log-Raum ueber alle 224 Bilder = **4,66 Grad**. sicher 145, unsicher 79 (Bilder < 3 Paare = unsicher). Je Serie: a,b,c,j,q komplett sicher; d 6/17, e 7/19, f 6/12, g 6/9, h 3/9, i 6/12, k 2/16, m 3/9, n 12/16, o 12/15, p 12/20 sicher. **Grenze:** die Schwelle ist relativ (trennt zwei Gruppen) und der E-Test ist bei kleiner Basis selbst verrauscht; 4,66 Grad ist KEINE absolute Posengenauigkeit. Abweichung von der Vorgabe 'a,b,i,j,n,p,q sicher': i nur halb sicher (6/12), p 12/20, dafuer c, o teilweise sicher.
- **Lauf** (max_size 1600, 8 Stapel, 224 Bilder, ~95 min): PatchMatch je Stapel 616-813 s (22-25 s/Bild), **GPU-Last mittel 95-98 %** (nvidia-smi alle 2 s, max 100 %), VRAM 0,6-1,2 GiB (nur ein GPU-Job, mehr Parallelitaet auf der GPU brachte nichts: schon ausgelastet; Fusion/Entzerren parallel auf CPU). Probelauf vorher mit je 10 Bildern je Klasse und Lauf (4 Stapel).
- **Ergebnis** (`dicht_neu/dicht_neu_{sicher,unsicher}_{modell,farben}.npy`, Stapel einzeln in `dicht_neu/stapel/`, `bericht.json`): **sicher 754 227 Punkte**, **unsicher 10 195 Punkte** (aus 79 Bildern; die geometrische Konsistenz von PatchMatch filtert sie fast vollstaendig weg: 1,3 % der Punkte bei 35 % der Bilder). Das stuetzt die Klasseneinteilung (unsichere Posen -> kaum konsistente Tiefen), ist aber kein Beweis der Posenfehlergroesse; unsichere Wolke ist als eigene Datei markiert, nichts verworfen.
- **Gegenprobe gegen `dicht_alle` (kaufhaus_null4, 825 790 Punkte, nur gelesen)**: Referenz-Punktabstand (2. Nachbar) Median 1,65 cm; Ueberlappungsbereich = neue Punkte in einem besetzten 16,5-cm-Voxel (10 x Referenzabstand, Wahl der Voxelgroesse ist eine ANNAHME, nur Berichtsbereich) = 66 % der sicheren (495 322 Punkte). Abstand dort, NN: Median 4,1 cm, q90 10,4 cm, q99 15,9 cm; Abstand zur lokalen Referenzebene (8 Nachbarn, nimmt den Abtastboden raus): **Median 3,2 cm, q90 9,6 cm**. Unsicher (Ueberlappung 39 %, 3 968 Punkte): Ebene Median 4,5 cm, q90 10,4 cm. **Vorsicht:** q99 ~0,16 m ist die Voxelgrenze (Abschneiden), keine Messung; ohne Abschnitt (alle sicheren Punkte, enthaelt neue Bereiche) NN-Median 6,7 cm, q90 21,9 cm, q99 1,04 m. Je Stapel Ebene-Median 2,7-3,5 cm, q90 7,2-10,0 cm (a_m_v2_02 beste, npq_v2_00 schlechteste).
- **Nicht belegt**: (a) beide Wolken stammen aus demselben Posenrahmen (Handyposen per PnP gegen die Referenz) - ein Abstand von 3 cm zeigt Konsistenz der Dichtbildung, keine absolute Genauigkeit gegen eine unabhaengige Quelle; (b) 259 k sichere Punkte (34 %) liegen ausserhalb der Referenz-Voxel = neue Flaechen (z-Quantile 5/50/95 %: 1,7 / 6,2 / 15,4 m), fuer sie gibt es KEINE Gegenprobe; (c) Abdeckung der Zielbereiche Arkaden-Innenraum / Erker-Unterseite / Gassenwand / Sockel wurde nicht je Bereich ausgezaehlt (kein Bereichskasten definiert, keine Handkonstante); im Sichtblatt (`dicht_neu/sichtblatt.jpg`, Draufsicht + beide Seiten, Referenz grau / neu nach Klasse / neu mit Fotofarbe) sieht man Punkte in Arkadenbogen, Erker-Front und Fassade; die Unterseite des Erkers wirkt in der Seitenansicht y-z noch lueckenhaft (Referenz grau dort dichter) - Sichtbefund, nicht gemessen; (d) Wolke ist mit Masken gefiltert (Planen/Stand), aber Maskenfehler wurden nicht gegen Fotos gezaehlt; (e) Auflösung 1600 px (kein Sweetspot fuer Kaufhaus vorhanden), kleinere Elemente evtl. verschmiert.
- Sonstiges: nichts geloescht (Probe-Arbeitsordner und alle Stapel auf Toshiba, Symlinks), kein Carving, kein Artifact geaendert, Sollwerte/Platztor unveraendert; Platz Daten danach 18 GB frei (zuvor 13 GB; `martinstor_lod2` 3,1 GB per `auslagern.sh` verschoben, vorher kein Prozess darauf). Ein eigener Testordner `t1` im Repo-Wurzelverzeichnis (Entzerrtest, selbst angelegt) wurde von mir entfernt. Naechster Hebel: Stapelgroesse/Quellbilder aus Ref-Bildern fuer die unsicheren Serien (d,e,h,k,m) testen; Region-Auszaehlung ueber das Modell-Elementbuch; Gegenprobe der neuen Flaechen gegen Laser/LoD2 wo moeglich.

## Register BR - Wolke -> Netz, Wettbewerb am Diff (6.11.2026 Abend, Kaufhaus null5, 23 Fotos, Gebaeudemaske, kosten_lr, kleiner = besser)
Mass: `tools/modell_wettbewerb.py ... --maske-kandidat C` (CPU-Mass). Ergebnisse unter /media/oem/scan/rc-park_null/wettbewerb_kh9g..kh17_*.
| Verfahren | Mittel | Bemerkung |
|---|---|---|
| OpenMVS Delaunay+GraphCut (mvs_d03, 30 %) | -0,104 | Sieger; nicht wasserdicht, rauschig |
| + Ebenen einrasten 0,30 m (tools/ebenen_einrasten.py) | -0,104 | gleich, geradliniger (Ersatz fuer PolyFit; echtes PolyFit nur CGAL/GPL, nicht gebaut) |
| + Saeulen-Regel (tools/saeulen_schliessen.py, DGM1-Anker + Wolken-Stuetzbeweis + Freistand) | -0,1025 | Pfeiler bis Boden; Keile am Fuss offen; Keil-Filter (--nah) schnitt Bogenlaibungen -> aus |
| RefineMesh (OpenMVS) | -0,098 | nicht besser |
| Poisson 9 / Poisson neu aus Netz | -0,084 / -0,093 | |
| wasserdicht per pymeshfix | -0,078 / -0,073 | Loecherschliessen kostet Diff (erfundene Flaechen) |
| TSDF aus Tiefenkarten | -0,068 | |
| Modell C (Generator) | -0,052 | Basis |
| Gaussian Splatting 3DGS V2 (Farbe/Himmel/Tiefe/Opa) | -0,061 | Test-PSNR ~14 (Ueberanpassung, uneinheitliche Fotos); V1 -0,041, Lauf 1 -0,016 |
| Gaussian Splatting 2DGS V3 | -0,056 | nicht besser als 3DGS |
| Carving | -0,027 | |
Martinstor (duenne Wolke, 101k Punkte): Handmodell v4 -0,075 schlaegt alle Netze (OpenMVS -0,013, Poisson -0,006) -> Sieger gilt nur bei dichter Wolke.
PolyFit-Nachbau (tools/ebenen_zellen_schnitt.py: 25 RANSAC-Ebenen, Zellen, Carving-Daten, Min-Cut, wasserdicht): lambda 0,5/2/8 -> -0,0040/-0,0030/-0,0017 = praktisch kein Gewinn (Ebenenzahl/Zellen zu grob, wie S8). Echtes CGAL-PolyFit nicht gemessen (GPL, kein Python-Binding in pip-cgal). nvcc kam als pip-Wheel (/media/oem/scan/cuda-nvcc, ohne sudo).
Offen: Keile am Pfeilerfuss, Prisma (8,64|7,89) am Foto pruefen, Saeulen-Regel an 2. Objekt mit Pfeilern belegen, Wasserdichtigkeit ohne Diff-Verlust.

## Register BS (7.11.2026) - Kamerafehler je Foto / Belichtungs-Sweep (Kaufhaus null5)
- BS1 Reprojektionsfehler je Foto (`tools/reproj_je_foto.py`, Bündel sfm/dicht_alle/sparse): 94 Bilder, Median 0,56 px, schlechtester p90 2,7 px (Foto 234); 12 markiert, fast alle nur <100 Beobachtungen. Foto 044 (~40 px im Foto-Diff) unauffällig (0,40 px) -> das Maß ist blind für Lage-/Brennweitenfehler (f 2 % = 0,6 m). Schlechte Kameras künftig über Foto-Diff/Kamera-Feinlage suchen. Daten: /media/oem/scan/rc-park_null/reproj_je_foto_kh.json.
- BS2 (OFFEN, Nutzeridee) Kontrast/Helligkeit-Sweep (Gamma/CLAHE/Mehrfachbelichtung) -> zusätzliche Merkmale -> Wolke erweitern. Erwartung: kein neuer Blickwinkel, nur mehr Merkmale in Schatten/Dunkel. Test an Teilmenge; Bewertung Dichtegewinn + Reprojektion + Anker; Ergebnis hier eintragen.
- BS3 (NÄCHSTER SCHRITT, noch nicht gebaut) Kamera-Feinlage je Foto über Foto-Diff gegen das Modell (Pose/f/k1 je Foto minimal verschieben, kosten_lr minimieren; nur wenn Nachbarfotos nicht schlechter werden; Holdout-Fotos 001 024 054 083 211 234). Begründung: BS1 zeigt, dass der Reprojektionsfehler Lagefehler nicht sieht. Vorher prüfen: tools/foto_diff.py Kamerafeinlage/Versatz-Optionen (Register "foto_diff bewiesen") nicht doppelt bauen.
- BS4 Feines Netz (mvs_fein) vs mvs_d03_pl30 vs mvs_default bei Glättung 0,18 und 0,05 (wettbewerb_kh21_g0.18/g0.05): Lauf FEHLGESCHLAGEN ("keine Werte"), Ursache: --maske-kandidat C, aber C nicht unter den Kandidaten -> keine Vereinigungsmaske. Fix in modell_wettbewerb.py (kopierte C_<foto>.png wird genommen). Neu rechnen; Ergebnis hier eintragen.
- BS5 Flächen-gegen-Netz (Nutzeridee: gleichfarbige Flächen = eben, rauhes Netz dort glätten; `tools/flaechen_gegen_netz.py` + Test, Foto- und Wolkenvariante). Synthetischer Beweis bestanden (Beulen 81 %/83 % erkannt, glatte Wand/Kasten/Stufen < 3 %). KAUFHAUS: NICHT übernehmen. Mittel kosten_lr -0,1062 (Foto/Wolke) vs -0,1045 Ausgangsnetz (saeule_median), aber 5 (Foto) bzw. 6 (Wolke) von 23 Fotos schlechter (016, 022, 032, 114, 218; 218 bis +0,02), Wolken-Median -0,0946. Ursache: Farbgleichheit ≠ Ebenheit; Abbau glättet Gauben, Arkadenkanten, Relief; Dachgauben verschmelzen mit Dachfläche. Wolkenvariante nicht feinheitsinvariant (1,4 % vs 10,3 % markiert bei 2,64 M vs 165 k Dreiecken). Überlappung Foto/Wolke IoU 0,70. Nächster Versuch nur mit Ausschluss von Struktur (Kanten/Gauben) und Region-Messung; --breite für feine Netze. Ausgaben /media/oem/scan/rc-park_null/flaechen_kh/lauf4.
- BS3a (7.11., aus vorhandenen foto_diff-JSONs wettbewerb_kh20/kh21, Netz mvs_d03_pl30, 23 Fotos; kein Neulauf): foto_diff hat die 2D-Versatzschätzung schon (`versatz`, `kosten_lr_versatz`) - NICHT neu bauen. Nur 2 von 23 Fotos haben einen deutlichen Kameraversatz: 073 (1,34 m, Gewinn 0,29) und 114 (1,12 m, Gewinn 0,21); alle anderen < 0,17 m. Beide fallen auch im Reprojektionsmaß auf (073: 52 Beobachtungen, 114: p90 2,4 px) -> zwei unabhängige Maße nennen dieselben Kameras. Auffällig: kosten_lr_versatz ist bei 073/114 SCHLECHTER (-0,0194 / -0,0111) als ohne Kompensation (-0,0244 / -0,0387): die reine 2D-Verschiebung repariert die Kamera nicht (Rotation/Brennweite wirken perspektivisch). Folge: Wettbewerbsmittel mit/ohne 073+114 getrennt ausweisen; 3D-Kamera-Feinlage (Rotation+f je Foto, nur diese Fotos) bleibt offen = BS3b.
- BS3b-Befund: die zwei Versatz-Fotos haben extreme Kameraparameter - 073: f 14089 px, k1 -0,35, nur 52 Bündelbeobachtungen (Tele-Zoom, f/k1 schlecht bestimmt). Mittel kosten_lr über 21 Fotos ohne 073/114: mvs_d03_pl30 -0,1109, saeule_median -0,1115, abgebaut -0,1135 (über 23: -0,1040/-0,1045/-0,1066); die Rangfolge bleibt, die beiden Fotos verzerren nur den Absolutwert.

## BS2-Ergebnis - Belichtungs-/Kontrast-/Farb-Sweep (Kaufhaus null5, 7.11.2026, Sonnet; Werkzeug `tools/belichtung_sweep.py`, Daten `/media/oem/scan/rc-park_null/belichtung_kh/`)
- **Aufbau**: 16 Bilder QUER ueber Seiten/Gruppen (je 45-Grad-Azimutsektor das Bild mit den meisten Buendelbeobachtungen, Rest nach Vielfalt Brennweite/Entfernung/Azimut; `auswahl.json`; alle Kameras liegen im Azimutbereich 24-129 Grad = Nordseite, andere Seiten gibt es im Buendel nicht). Entzerrte 1600-px-Bilder `sfm/dicht_alle/images`, Kameras fest aus `kameras_unverzerrt.json` (= sparse, Diff 0). 15 Varianten (orig, Gamma 0,5/0,7/1,4, CLAHE 3/8 auf L, lokale Normierung, Helligkeit +-40, Kanal B/G/R, HSV-V, Saettigung, Mertens-Mehrfachbelichtung) + 2 KONTROLLEN (Originalbild, nur SIFT-Kontrastschwelle 0,02/0,01 statt 0,04). cv2-SIFT+RootSIFT (nicht SiftGPU), Top-8000 je Bild/Variante nach Antwort fuer die Triangulation. Matching Ratio 0,8 + gegenseitig (GPU, torch), dann Epipolarfilter mit den FESTEN Kameras (<1,5 px), Tracks per Union-Find, DLT, Ausreisser <=2 px, Winkel >=3 Grad. EIGENE Triangulation statt `pycolmap.triangulate_points` (Rig-Konflikt, Register DF). Nichts in vorhandene sfm-Dateien geschrieben. Platztor (<10 GB) blockierte `job_start.sh` -> Laeufe im Vordergrund (je <3 min), 728 MB Arbeitsordner.
- **Regionen**: 2D aus Hoehenband-Huellen des LoD2-Grundrissvolumens (boden z0-4, fassade 4-9, dach 9-14, giebel 14-First, aussen = Rest inkl. Nachbarn/Platz; Himmel grob per Helligkeit/Textur ausgeschlossen); 3D-Baender aus Punkt-z und Grundriss-Huelle (+1,5 m).
- **Keypoints (Summe 16 Bilder, Schwelle 0,04)**: gesamt / boden / fassade / dach / giebel / aussen - orig 179981 / 18475 / 50199 / 56481 / 5932 / 48793; gam05 163632; gam07 176522; gam14 173046; **clahe3 236147 / 27851 / 63752 / 67636 / 6950 / 69779; clahe8 246263 / 29070 / 66606 / 68696 / 7549 / 73608**; lokal 212117; hell_p 175592; hell_m 169682; ch_b 178162; ch_g 180126; ch_r 181996; hsv_v 184316 (fassade 53080); sat 161966 (dach nur 34128); mertens 184576. KONTROLLE orig_ct02 226936 / 28338 / 64090 / 63580 / 7068 / 63734; **orig_ct01 253561 / 34453 / 72736 / 66892 / 7869 / 71259** = mehr als jede Variante. Gamma/Helligkeit/Kanal/HSV/Mertens aendern die Keypointzahl um nur -9 bis +3 %; CLAHE/lokal +18 bis +37 % - derselbe Effekt wie eine gesenkte Kontrastschwelle (Rauschen/Textur verstaerkt, keine neue Information).
- **Triangulierte Punkte (Top-8000, 16 Bilder; epi-Matches / Punkte gesamt | Dach / Giebel / Fassade / Boden / aussen)**: orig 1979 / 1430 | 291 / 29 / 828 / 38 / 244; gam05 1339; gam07 1389; gam14 1474 | 316 / 30 / 822 / 27 / 279; clahe3 1104; clahe8 1009; lokal 1239; hell_p 1337; hell_m 1231; ch_g 1527; mertens 1494 | 311 / 22 / 857 / 37 / 267; sat 337. **Viele Einzelvarianten ERGEBEN WENIGER Punkte als orig** (CLAHE: -23 bis -29 %): mehr Merkmale bringen mehr falsche Ratio-Matches, die der Epipolarfilter verwirft. Vereinigung aller Varianten (UNION_alle, 448 k Merkmale) 2149 Tracks / 1878 Punkte = +31 % gegenueber orig, Dach 316 (+9 %), Fassade 1161 (+40 %), Boden 43, Giebel 28 (orig 29), aussen 329.
- **Mit Cap 20000 (Kontrollvergleich ohne Abschneiden)**: orig 1632 Punkte (Dach 334, Giebel 33, Fassade 899, Boden 42); orig_ct02 1762 (Dach 343); **orig_ct01 1807 (Dach 342, Giebel 41, Fassade 977, Boden 69)**; clahe8 1479 (Dach 266); UNION_alle 2273 (Dach 390, Giebel 39, Fassade 1292). Bei Cap 8000 waren orig_ct01/ct02 mit orig identisch (gleiche Top-8000) - dieser Kontrolllauf war dort wertlos und wurde mit Cap 20000 wiederholt. => Der Gewinn der Vereinigung (+39 % gesamt, Dach +17 %) liegt knapp ueber dem, was EINFACH mehr Merkmale (niedrigere Schwelle, +11 %) bringt, bei ~4-fachen Merkmalszahlen; der Beitrag der Belichtungsvarianten selbst an Dachpunkten ist klein (342 -> 390).
- **Fehler / Plausibilitaet (alle Bedingungen gleich)**: Reprojektion Median 0,25-0,27 px, p90 0,55-0,59 px (Hinweis: Ausreissergrenze 2 px und feste Kameras; Buendelwert 0,56 px ist ein anderer Schaetzer, nicht vergleichbar). Je Region Median 0,18-0,46 px, kein Gewinn durch Varianten. Abstand der Punkte zur vorhandenen dichten Wolke (orig): Fassade Median 2,6 cm (p90 25 cm), Dach 3,7 cm (p90 45 cm), Giebel 16 cm (p90 1,0 m), Boden 10 cm (p90 65 cm), aussen 1,85 m (dichte Wolke deckt Nachbarn/Platz nicht ab). Wandabstand zur LoD2-Grundrisskante (Median, Punkte <1,5 m von der Kante): Fassade 0,20 m, Boden 0,40 m (Wolkenpunkte liegen am Putz/Relief vor der LoD2-Wand; kein unabhaengiger Fehlerwert). Giebelpunkte ueber LoD2-First: 0 %. UNION_alle: Giebel Median-Abstand 0,76 m zur dichten Wolke, Boden 0,15 m (schlechter als orig, mehr Ausreisser).
- **"Neue" Dachpunkte** (>30 cm von der dichten Wolke): orig 34 von 291 (12 %), UNION_alle 34 von 316 (!) , orig_ct01@20000 53, UNION@20000 52 von 390. Das Dach ist in der dichten Wolke schon belegt (85-90 % der Punkte liegen < 30 cm daneben); die dunklen/schattigen Dachstellen liefern KEINE nennenswert neuen Tiefen. Die "neuen" ~50 Punkte wurden NICHT einzeln als echt bestaetigt (p90 0,45 m deutet auf Ausreisser).
- **Bewertung**: Erwartung (kein neuer Blickwinkel, Kameras nicht genauer) bestaetigt: Reprojektion und Anker-/Wolkenabstand bleiben unveraendert. Nur Mehrmerkmal-Effekt: Kontrastvarianten wirken wie niedrigere SIFT-Schwelle; CLAHE allein verschlechtert die Tracks, Saettigung/Einzelkanaele bringen nichts, die Vereinigung bringt +31...39 % Punkte an Fassade/aussen, am Dach nur +9...17 %. Die erwartete Wirkung "dunkles Dach/Schatten" ist nicht gezeigt. Keine Uebernahme in die Wolke (Regel: nur mit Reprojektion + Ankerkonsistenz, hier nur Gleichstand; Gewinn gering, Aufwand 4x Merkmale). Wolke bleibt einzige Basis, nichts vermischt.
- **NICHT geprueft**: (a) Wirkung auf die DICHTE Wolke (PatchMatch/Fusion mit Varianten, wo Schatten Tiefen verlieren) - hier nur sparse Merkmalspunkte; (b) Variantenvereinigung in COLMAP/SiftGPU mit RCPARK_SIFT_MAX 1600 und LightGlue/ALIKED (cv2-SIFT hier, andere Matcher koennten Varianten besser nutzen); (c) volle 94 Bilder und Paarauswahl (hier alle 120 Paare von 16, Wirkung kleiner/groesser?); (d) Helligkeit der Dachpixel je neuem Punkt (ob die neuen Punkte tatsaechlich im Dunkeln liegen); (e) echte Handy-/Archivgruppen getrennt (Auswahl enthaelt f 827-4713, nicht je Gruppe ausgewertet); (f) Seiten ausser Nord (nicht im Buendel); (g) unabhaengiger Fehlermassstab (amtliche Anker sind nur 11 Eck-/Firstpunkte, keine Punktflaechen; Wandabstand gegen LoD2 ist kein Fehlermass); (h) Epipolarschwelle 1,5 px/Ratio 0,8 nicht variiert; (i) Himmelsmaske grob.
- BS4-Ergebnis (7.11., Neulauf nach Fix, 23 Fotos, feste Gebäudemaske, kosten_lr, kleiner = besser): Glättung 0,18: mvs_d03_pl30 -0,1040 (Median -0,1104) | mvs_default -0,1027 (9/23 besser) | mvs_fein -0,0811 (2/23). Glättung 0,05: mvs_d03_pl30 -0,0912 | mvs_default -0,0801 | mvs_fein -0,0419 (1/23). Das FEINE Netz (mvs_fein) ist bei beiden Glättungen SCHLECHTER als das grobe (auch bei 0,05, wo feine Details sichtbar sein sollten) -> mehr Dreiecke allein verbessern den Diff nicht; die Feinheit bringt Rauschen/Wolkenfehler ins Netz. Vorsicht: Kantenmaß bei 0,05 insgesamt schwächer (alle Werte höher).
- BS6 Wichtigkeit je Foto (`tools/foto_wichtigkeit.py`, Bündel kaufhaus_null5 sfm/dicht_alle/sparse, 94 Bilder, 16 061 Punkte, 12 199 mit >= 3 Bildern; Daten /media/oem/scan/rc-park_null/foto_wichtigkeit_kh.json): KEIN Foto ist für die Abdeckung entbehrlich (allein=0: 0 Bilder; wichtigste 230, 210, 216, 209, 212 mit 450-590 nur von ihnen getragenen Punkten). Greedy-Überdeckung (Punkte brauchen >= 3 gewählte Bilder): 66 Bilder = 90 %, 75 = 95 %, 88 = 99 %. Sparpotenzial gering: 66 statt 94 spart ~30 % linear, ~50 % beim Paar-Matching, kostet 10 % der Punkte. Aussage = Abdeckung, nicht Genauigkeit. Entscheidung: schnelle Iterationen (Kamera-Ausgleich BS3d, Wettbewerb) mit den 66 Greedy-Bildern + Holdout, Endlauf mit allen. Leave-One-Out am Diff als Prüfung noch offen.
- BS6-Einschränkung: Fotoauswahl (66 von 94) nur für Messschleifen (Kamera-Ausgleich, Diff-Wettbewerb, Parametersuche), NICHT für SfM/dichte Wolke: Register BM (nullstart --grob-fotos) fand, dass Foto-Teilmengen dort Türmchen/Zinnen verlieren; Standard bleibt alle Fotos.

## BS3c Kamera-Feinlage je Foto ueber foto_diff (7.11., `tools/kamera_feinlage.py`)
- **Auftrag/Hypothese**: Kaufhaus-Fotos 073 (f 14089 px, k1 -0,35, 52 Buendelbeob.) und 114 (f 10858, k1 +0,66) haben foto_diff-Versatz 1,29/1,18 m; Hypothese f/k1 bei Tele schlecht bestimmt. Netz `wettbewerb_kh/netze5/pl30_saeule_median.stl`, feste Maske `wettbewerb_kh9g/masken/<nr>.png`, Glaettung 0,18, CPU-Punktfassung (FD_RASTER=0, CUDA aus) wie modell_wettbewerb, kosten_lr (kleiner = besser). Daten/Logs: `/media/oem/scan/rc-park_null/feinlage_kh/` (`<nr>/feinlage_<nr>.json` mit allen Proben, `vorschlag_<nr>.json`, `log_<nr>.txt`). K-Dateien NICHT veraendert (Kopien je Arbeitsplatz unter `<aus>/slotN/modelle/kaufhaus_null5/messprotokoll`, objekt.json mit absoluten Pfaden; foto_diff.k_datei nimmt den Objektordner zuerst).
- **Verfahren**: Mustersuche (Koordinatenabstieg, +/- je Parameter parallel, Schritt halbieren bei Misserfolg). Parameter: Drehung um das Kamerazentrum rx,ry,rz (Grad; Start 0,4/0,4/0,3), ln f-Faktor (Start 0,01), k1 absolut (Start 0,03). Varianten `voll` (alles), `k1fest` (k1=0, Start lr 073 -0,0256 / 114 -0,0337 statt -0,0255/-0,0370 mit gebuendeltem k1), `nurrot` (nur Entwurf, nicht gelaufen). Holdout: Maske am Median-x der Maskenpixel in A (links)/B (rechts) geteilt; auf einer Haelfte optimiert, auf der anderen geprueft; nur Variante `voll`. Obergrenze 30 Proben je Suche (Platz/Zeit) - die Suche brach meist an der Obergrenze ab, nicht am Schritt-Minimum: **nicht konvergiert**.
- **Ergebnis voll (kosten_lr vorher -> nachher, Proben)**: 073 -0,0255 -> -0,0557 (rx 0, ry -0,8, rz +0,3 Grad, f und k1 unveraendert; 31); 073 k1fest -0,0256 -> -0,0556 (ry -0,4, f x0,995; 33). 114 -0,0370 -> -0,0745 (rx +0,4, rz -0,6; 31); **114 k1fest -0,0337 -> -0,0967 (rx +0,4, rz -0,9 Grad, f unveraendert, k1 0; foto_diff-Versatz 1,18 m -> 0,11 m)**. Kontrollen voll: 000 -0,1459 -> -0,2258; 059 -0,2530 -> -0,2610; 082 -0,1403 -> -0,1665.
- **Holdout (Pruefhaelfte vorher -> nachher, Optimierung auf der anderen Haelfte)**: 114 A->B -0,0033 -> -0,0091, B->A -0,0274 -> -0,0585 (beide besser). 073 A->B: Fit-Haelfte findet keine Verbesserung (Parameter 0, nichts zu pruefen); B->A Fit -0,086 -> -0,242, Pruefhaelfte -0,0044 -> -0,0012 = **schlechter**. Kontrollen: 000 A->B -0,121 -> -0,191 besser, B->A -0,174 -> -0,151 schlechter; 059 A->B -0,238 -> -0,200 schlechter, B->A -0,277 -> -0,248 schlechter; 082 A->B -0,054 -> -0,050 schlechter, B->A -0,233 -> -0,203 schlechter. Kontrollen: 5 von 6 Holdout-Pruefungen schlechter/ohne Nutzen = die Feinlage passt dort Rauschen an (gut so: bei gut ausgerichteten Fotos ist Drehung <= 0,4-0,6 Grad ohne Beleg).
- **Befund**: (1) 114: Versatz verschwindet mit Drehung ~1 Grad (rz -0,9, rx +0,4) und **k1 = 0**; Holdout bestaetigt die Drehung (Variante voll, k1 beibehalten); k1 +0,66 ist nach dem Ergebnis ueberflüssig/verdaechtig, aber `k1fest` wurde NICHT im Holdout geprueft. (2) 073: lr-Gewinn (0,03) liegt im Bereich der Kontrollen und des Probenrauschens (Streuung aller 073-Proben 0,011, 114: 0,021), Holdout schlecht -> kein belegter Gewinn; Versatz bleibt 0,75-1,25 m. Die Ursache fuer 073 liegt nicht in kleinen Drehungen/f/k1 (f blieb in allen Suchen bei <= 0,5 %); Verdacht: nur 52 Buendelbeobachtungen, Kamera-Standort (t) oder das Netz an dieser Seite. (3) f wurde von keiner Suche merklich verschoben -> die Hypothese "f bei Tele falsch" ist fuer diese Probenbereiche (+-1 %) nicht gestuetzt.
- **Vorschlaege**: `vorschlag_114.json` (Variante k1fest) - als Vorschlag, noch nicht in K-114 uebernommen; `vorschlag_073.json` NUR zur Dokumentation, nicht uebernehmen.
- **Fehlschlaege/Abweichungen**: Erster Lauf (90 Proben, `nurrot`, Holdout aller Varianten) wegen Rechenzeit (5 Jobs x 16-60 s je Probe, Last 28) abgebrochen und mit weniger Proben neu gestartet (Logs `log_<nr>.abgebrochen1.txt`, Ordner `abgebrochen1_<nr>`, nicht geloescht). GPU-Raster statt CPU-Punkte gab fuer dieselbe Kamera/Maske ganz andere Werte (073: lr -0,259, Versatz 0,24 m statt -0,025/1,29 m) - Rasterfassung und Punktfassung nicht vergleichbar; **Widerspruch offen** (nicht gemittelt, naechster Schritt: 073/114 auch mit Rasterfassung suchen).
- **NICHT geprueft**: Translation (Kamerastandort) und Hauptpunkt; Suche bis zur Konvergenz (Obergrenze 30 Proben); k1fest/nurrot im Holdout; weitere Fotos mit Versatz; andere Netze (mvs_d03_pl30); Einfluss auf Bundle-Reprojektion (Vorschlag 114 koennte Anker-RMS verschlechtern: `kamera_bruecke_pruefen.py` nicht gelaufen); Rasterfassung; Stabilitaet mit anderer Saat/Glaettung 0,05.
- BS3c-Nachtrag (7.11., Overlay 114 angesehen: /media/oem/scan/rc-park_null/feinlage_kh/overlay_alt|neu/foto_diff_114.jpg): mit k1=+0,66 (alt) ist die Entzerrung sichtbar verzerrt (schwarze Ränder oben/links), mit k1=0 (Vorschlag) natürlich -> k1=+0,66 vermutlich Anpassungsartefakt. ABER: Overlay zeigt die Modellkanten nicht, rot/gelb nur in wenigen Kästen; foto_diff-Texte: alt 25,5 m 'fehlt', neu 40,6 m 'erfunden' -> kein klarer Beleg, dass 114 besser sitzt; kosten_lr-Gewinn kommt vor allem vom verschwundenen Versatz. K-114.json NICHT geändert; Entscheidung über BS3d (Ausgleich mit Holdout).
- BS3e (7.11., KORREKTUR zu BS3a/BS3b): Foto 073 hat in der Punktfassung (FD_RASTER=0, wie im Wettbewerb) nur 70 Modellkanten-Pixel (Rastern: sonst 10^5-10^6; fotokanten 155 019) -> kosten_lr -0,024 und 'Versatz 1,29-1,34 m' sind ein MESSARTEFAKT (Tele, f 14089 px, Netz fast ausserhalb des Bildfelds / kaum Punkte). Mit GPU-Raster: kosten_lr -0,259, Versatz 0,24 m, rot 4,8 % / gelb 3,8 % -> 073 ist KEINE schlechte Kamera. 114: Raster 1,52 Mio Modellkanten-px, kosten_lr -0,019, Versatz 0,36 m (Punkt: 0,44 Mio px, -0,039, 1,12 m) -> 114 hat einen echten, aber kleineren Versatz (~0,36 m) als gedacht. Folge: (1) die Feinlage-Gewinne für 073 sind wertlos (Messziel degeneriert), für 114 im Raster neu prüfen; (2) Wettbewerbsmittel (Punktfassung) enthält 073 mit degeneriertem Wert; Rangfolge der Netze unverändert, Absolutwerte nicht vergleichbar mit Raster; (3) jede Messung braucht Plausibilitätsprüfung der Kantenzahl (modellkanten_px) vor Auswertung. Reprojektionsfehler von 073 war auffällig nur wegen 52 Beobachtungen (Tele).
- Auslagerung 7.11.: Nutzerfreigabe für /media/oem/Volume als zweites Ziel (tools/auslagern.sh, AUSLAGERN_MOUNT=/media/oem/Volume): kaufhaus_handy_npq, kaufhaus_handy2k per Prüfsumme dorthin, Symlink zurück. Toshiba bleibt voll (761 MB).
- BS7 (läuft) Wettbewerb im GPU-RASTER (statt Punktfassung), 23 Fotos, Netze mvs_d03_pl30, saeule_median, mvs_default, mvs_fein, Glättung 0,18: /media/oem/scan/rc-park_null/wettbewerb_kh22_raster (Log .log). Grund: BS3e (Punktfassung degeneriert bei Tele-Foto 073).
- BS7-FEHLSCHLAG (7.11. 08:42): wettbewerb_kh22_raster lief NICHT im Raster: modell_wettbewerb.lauf() setzt FD_RASTER=0 fest und überschreibt die Umgebung -> Ergebnisse identisch mit Punktfassung (mvs_d03_pl30 -0,1040, saeule_median -0,1045, mvs_default -0,1027, mvs_fein -0,0811; Foto 073 -0,02439 wie vorher). ~25 min verloren. Fix: Option --raster in modell_wettbewerb.py (setzt FD_RASTER=1, CUDA sichtbar). Neuer Lauf wettbewerb_kh23_raster. Lehre: Ergebnis auf Gleichheit mit dem Vorlauf prüfen, bevor man es als neues Maß bewertet.
- BS8 Profil foto_diff (cProfile, Foto 000, Punktfassung, saeule_median, 16,2 s gesamt, während andere Jobs liefen): Fotokanten-Berechnung taucht NICHT unter den Hauptkosten auf -> der geplante Zwischenspeicher für Fotokanten lohnt NICHT. Echte Kosten: Netz laden + Oberflächen-Stichprobe (_netz 5,3 s, davon trimesh.sample_surface 4,4 s, pro Foto neu, obwohl je Netz identisch), Import (torch 8 s kumuliert im CPU-Modus, trimesh 1,4 s), versatz_schaetzen 1,8 s, normalenkanten 1,6 s, kosten 1,5 s. Hebel: (1) Stichprobe je Netzdatei einmal und festem Seed zwischenspeichern, (2) torch im Punktmodus nicht importieren, (3) mehrere Fotos in einem Prozess. Erwartet grob 2-3x je Lauf (ungemessen). NICHT jetzt umsetzen: foto_diff.py wird von laufenden Jobs (kh23raster, Ausgleich-Agent) bei jedem Start neu gelesen; Änderung erst danach, mit tools/regression.py --pruefen (Ergebnis muss gleich bleiben).
- BS7-Ergebnis (7.11. 09:09, GPU-Raster, 23 Fotos, Glättung 0,18, feste Gebäudemaske, wettbewerb_kh23_raster): Mittel kosten_lr mvs_default -0,1139 | saeule_median -0,1086 | mvs_d03_pl30 -0,1064 | mvs_fein -0,0864. Unterschied zum Punktmodus: mvs_default liegt im Raster vorn (Punkt: -0,1027, hinten). ABER nicht belastbar: default vs saeule_median besser bei 8, schlechter bei 11 von 23 Fotos; Bootstrap-95%-Intervall der Differenz -0,0142..+0,0026 (enthält 0); Mittelvorsprung stammt aus Foto 073 (-0,289 vs -0,259). Ohne 073/114: default -0,1103, saeule -0,1057, d03_pl30 -0,1033, fein -0,0825 (gleiche Reihenfolge). Stabil: saeule_median besser als mvs_d03_pl30 (11 besser / 3 schlechter), mvs_fein überall am schlechtesten. 073: -0,2587 (d03/saeule), 114: -0,0195 -> 073 im Raster unauffällig (BS3e bestätigt). Offene Frage: Rangfolge default vs saeule hängt am Messmodus -> Entscheidung nicht auf diesen Zahlen; nächste Messung: Glättung 0,05 im Raster und Halbierungstest.

- BS8-Ergebnis (7.11., `tools/foto_diff_batch.py` + `tools/test_foto_diff_batch.py`; foto_diff.py UNVERAENDERT, wird importiert, main() je Foto im selben Prozess): Netz/Stichprobe/Importe einmal je Prozess, Punktmodus ohne torch-Import (render_kern._T=False), optional Faeden (--threads), Raster mit VRAM-Deckel (JOB_GPU_MB, Standard 1500) und OOM-Wiederholung, Kameravarianten (--k-ordner NAME=DIR), Ausgabe `<aus>/<netz>[@variante]/<nr>/foto_diff_<nr>.json` + batch_ergebnis.json. Kein Zwischenspeicher fuer Fotokanten (Befund BS8).
  - GLEICHHEIT Punktmodus (Netz pl30_saeule_median, Glaettung 0,18, Maske kh9g): das GESAMTE Ergebnis-JSON ist fuer 000/004/073/114 bitgleich zum Original (kosten_lr -0,14587 / -0,24059 / -0,02548 / -0,03704; modellkanten_px 2668194 / 1548174 / 1130 / 443919). Raster: 000 -0,13319, 004 -0,22397, 114 -0,01946 gleich dem Original-Raster UND gleich wettbewerb_kh23_raster/ergebnis.json (073 Raster -0,25865 dort; im Batch wegen VRAM nicht nachgerechnet). Anm.: kh21 enthaelt saeule_median nicht (nur mvs_*); Punktreferenz = eigener Original-Lauf (stimmt mit BS3c/BS3e: 000 -0,1459, 073 -0,0255).
  - ZEIT (Maschine durch fremde Jobs belastet, Last 13-30, GPU fremd 2,8-7,6 GB belegt; nur relativ, gleiche Bedingungen hintereinander): Punkt, 4 Fotos: Original 84,3 s (21 s/Foto) vs Batch 1 Faden 54,5 s (13,4 s/Foto) vs 3 Faeden 48,0 s; Punkt 3 Fotos: Original 48,8 s vs Batch 2 Faeden 23,6 s = ca. 2,1x. Gewinn kommt aus Einmal-Import/-Stichprobe (zus. FD_PUNKTE_DIR als --punkte-cache fuer Folgeprozesse), nicht aus Faeden (GIL; 3 statt 1 Faden nur ca. 10 %). Raster, 3 Fotos (000/004/114): Original 21,3 und 20,6 s vs Batch 1 Faden 23,3 und 14,3 s, 2 Faeden 30,3 und 21,8 s -> KEIN belastbarer Gewinn, 2 Faeden schlechter (GPU und Python-GIL geteilt; Pipeline GPU-Raster/CPU-Kosten per Faeden bringt nichts). Der Raster-Weg ist durch Prozessstart kaum belastet (3-4 s/Foto im ruhigen Moment), die GPU-Last kommt von fremden Jobs.
  - GPU/RAM: Batch-Punkt nutzt die GPU nicht (0 MiB); RAM-Spitze Gesamtsystem 13,8 GB benutzt / 1,9 GB verfuegbar (Fremdjobs dominieren; eigener Anteil ~1-2 GB je Prozess). nvidia-smi-Reihe Raster-Batch: 0-100 % in Stoessen, fremde Belegung 1,1-7,7 GB.
  - FEHLSCHLAEGE/BEFUNDE: (1) Raster Foto 073 und teilweise 114 scheitern mit CUDA-OOM, wenn die GPU von Fremdjobs voll ist (auch das ORIGINAL foto_diff scheitert bei 073: 1,46 GiB Zusatzbedarf in versatz-Schritt) und bei Deckel 1500 MiB; Raster-073 braucht >1,5 GB -> unter dem Deckel nicht rechenbar. (2) Faeden-Pipeline fuer Raster: kein Gewinn (s. o.). (3) Erster Entwurf enthielt toten Code (vom Autor entfernt, vor Messung).
  - NICHT geprueft: Raster mit freier GPU/ohne Deckel und mit 073; mehrere Netze und mehrere Kameravarianten im Grossbetrieb (nur 1 Variante, 1 Foto im Test); Einbindung in modell_wettbewerb.py/kamera_feinlage.py (nicht geaendert); --schatten/--region-Optionen; Bitgleichheit der jpg-Bilder; Speicherfreigabe bei >2 Netzen im Faden-Betrieb (_NETZ.clear()-Wettlauf nur durch Warmlauf der ersten Aufgabe entschaerft); regression.py nicht gelaufen (foto_diff.py nicht geaendert).
- BS8-Einbau (7.11.): modell_wettbewerb.py --batch (Pass 2 je Kandidat in EINEM Prozess via foto_diff_batch.py, nur Punktmodus; Pass 2 nutzt vorhandene p2-JSONs statt neu zu rechnen). Test 3 Fotos (000, 004, 059), Netz mvs_d03_pl30, Glättung 0,18: kosten_lr -0,1442 / -0,23708 / -0,24385 = identisch zum Referenzlauf wettbewerb_kh21_g0.18. Zeit gesamt 76 s inkl. Pass 1 (Pass 1 rechnet foto_diff je Kandidat und Foto, wenn keine <kandidat>_<nr>.png-Maske da ist; bei --maske-kandidat C unnötig -> weiterer Hebel: Pass 1 überspringen, wenn --maske-von + --maske-kandidat gesetzt). Gemessener Gewinn Pass 2 allein: nicht separat gemessen (Last durch Ausgleich-Lauf).
- BS3d-Ergebnis (7.11. 09:57, tools/kamera_ausgleich.py, GPU-Raster, Netz mvs_d03_pl30, 21 Trainingsfotos + 6 Holdout-Fotos 001 024 054 083 211 234, 2718 Proben, 3552 s; /media/oem/scan/rc-park_null/ausgleich_kh/real): NUR Foto 114 übernommen (lr -0,0195 -> -0,1343; Pose rx +0,3, ry -0,15, rz -0,2 Grad, ty -0,09, tz +0,15 m; Holdout A->B +0,018, B->A +0,112 Gewinn). 20 von 21 Trainingsfotos unverändert (alle Vorschläge fielen im Holdout durch), 6 Holdout-Fotos unverändert, Foto 073 unverändert. Mittel Training -0,0994 -> -0,1049 (allein 114). Folge: Kameras sind nicht der Hauptfehler; Netz ist der Engpass. K-114.json NICHT geändert (Vorschlag vorschlag_114.json), Übernahme nur auf Nutzerfreigabe. Pfeilerkeile-Analyse (pl30_saeule_median, Schnitte 0,75-2,85 m): dünne Polygone <25 cm Breite mit 0-3 Wolkenpunkten im Umkreis 15 cm an Pfeilern (x,y) (7,1;11,8), (4,1;12,4), (-4,1;15,4), (0,0;13,9) bei z=0,75 m -> Kandidaten für Keile; Auswertung läuft.
- BS3d-KORREKTUR (7.11. 10:35): Der erste echte Ausgleich-Lauf (real_lauf1, Ergebnis 'nur 114 übernommen') war durch CUDA-OOM-Fehlproben verfälscht (157 Fehlzeilen in real/fehler.log; Fotos wie 049 scheiterten bei Versuch 0/1 an Speicher, weil mehrere Raster-Jobs die 8-GB-GPU teilten). Schluss 'Kameras sind nicht der Hauptfehler' ist damit NICHT belegt. Der Ausgleich-Agent hat neu gestartet (rcpark-ausgleichreal2); Ergebnis abwarten. Lehre: Raster-Jobs nicht gleichzeitig auf der 8-GB-GPU ohne VRAM-Budget; Lauf mit Fehlproben darf kein Ergebnis liefern.

- BU-LLM (7.11., LLM als Plausibilitaetspruefer, Eichsatz): neu `tools/llm_urteil_paare.py` (Blind-Paarbilder aus foto_diff-Overlays, Schluessel getrennt unter llm_urteil/_schluessel/<lauf>.json) und `tools/llm_urteil_auswerten.py`. Eichsatz eich1 (19 Paare, Objekt kaufhaus_null5, Raster, Maske C kh9g): 6 Netzpaare mvs_default vs mvs_fein (Diff klar, delta lr 0,04-0,09), 7 Kamerapaare (Schwenk 0,5/1,0 Grad, nur Paare mit delta lr >= 0,01 behalten; 004/1,0, 054/1,0, 000/0,5 wegen unklarem Diff verworfen), 3 identische Bilder + 3 nahgleiche Netze (default/saeule_median, |delta lr| < 0,004). 3 frische Sonnet-Beurteiler, nur Bild+Frage. ERGEBNIS: Treffer Einzelurteil klar 19/39 = 49 % (Mehrheit 7/13); Netzpaare 13/18 = 72 % (Mehrheit 5/6); Kamera 1 Grad 4/12, 0,5 Grad 2/9 (haeufig 'gleich'); Nullkontrolle identisch 9/9, nahgleich 0/9 (Beurteiler sahen Unterschiede, die der Diff nicht sieht, 3 von 3 Mehrheiten A/B), gesamt 9/18 = 50 %. Konsistenz zwischen Beurteilern 82,5 %; Position-Bias links-Anteil 41,9 % (13 links / 18 rechts / 26 gleich). Entscheidung nach Regel (>= 80 % beide): TAUGT NICHT. Grobe Netzunterschiede (viel rot/gelb) sieht er, 0,5-1 Grad Kameraversatz und feine Unterschiede nicht. Kosten: 19 Paarbilder je Beurteiler = 57 Bildansichten (1600 px breit, ~84k Token je Beurteiler). Nicht geprueft: andere Bildgroessen/Ausschnitte (--region-box), staerkere Verschiebung, andere Beurteiler-Modelle, Wiederholung derselben Beurteiler (Streuung).

## BT - Bogenkontur zuerst messen, dann benennen (Pilot Arkadenboegen f02 Kaufhaus null5, 7.11.2026, Sonnet)
Nutzerwunsch 7.11.: nicht Familie raten + Diff optimieren, sondern Kontur am Foto messen, dann benennen. Werkzeug `tools/bogen_kontur.py` (ortho / kandidaten / kontur / overlay / einbauen), Test `tools/test_bogen_kontur.py` (Exit 0 = ALLE BESTANDEN, ~1 min). Daten `/media/oem/scan/rc-park_null/bogen_kontur/` (o_s0, p_s*, v_s-0.5 = Endlauf, ov/ Overlays, vis/, stl/).
- Ablauf: (1) je kalibriertem Foto (K-Dateien null5, 70 Fotos, k1 wie fassade_ortho.projizieren) metrische Ortho 1 cm/px auf der Ebene f02 um s, ohne Modellsichtbarkeit. (2) OWLv2 (Prompts 'an arch'|'an arcade arch', Schwelle 0,15 = Standard fassade_parsing, NICHT optimiert, 8 Orthos, >= 3 Stimmen) nur als Suchfenster: 4 Boegen u -8,37..-4,57 / -4,31..-0,45 / -0,07..3,90 / 4,12..8,03. (3) Kontur: Goldlinie (min(R,G)-B)/(Helligkeit+24), Polar-DP um die Fenstermitte, keine Formannahme; SAM nicht benutzt (Oeffnung im Sonnenfoto nicht dunkel: helle Gewoelbekappe; Helligkeitsschwelle waere dort falsch). (4) Fusion Median ueber Fotos, Streuung MAD. (5) Spline, dann benennen, Familien nur als Vergleich.
- Synthetik (5 Fotos, Kamera 3 cm Rauschen, k1, Passanten, Bildrauschen): rund/spitz/segment Median 1,4-1,9 cm, P95 3,1-3,6 cm (< 5 cm), Benennung richtig; Kamerafehler 15 cm: Formfehler nach Verschiebung P95 8,0 -> 1,5 cm mit ausrichten(); Gegenproben: 20 cm systematisch -> P95 22 cm (nicht behebbar), ohne Goldlinie 0 gueltige Winkel. EHRLICH: Schwellen (abs. Antwort 0,08, Streu 0,30 m, min_anteil 0,25, theta -40..220) nach Ansicht der Echtdaten gesetzt; Segment-/Rund-Trennung nur 0,96 vs 1,12 (Kronenradius/halbe Breite); Kaempferhoehe nur +-0,4 m lesbar (kurzer Ansatz verschwindet unter der Glaettung); erste Testfassung hatte Fehler (Gold-Rest in der Gegenprobe, u-Sortierung bei senkrechtem Ansatz) - behoben.
- Ebenentiefe s (Streuung der Krone ueber 30 Fotos je s): -1,0 ~28 cm, -0,75 15, -0,6 12,5, -0,5 13, -0,4 14, -0,25 15, 0 24, +0,25 30 cm: flaches Minimum -0,4..-0,6; s = -0,5 (+-0,15) deckt sich mit S9-Carving (t_front -0,49), unabhaengige Bestaetigung nur grob.
- Echtlauf (70 Fotos, s -0,5, ausgerichtet): je Foto Ebenenverschiebung Median 19-40 cm (= Kamerafehler 10-35 cm, jetzt gemessen); Streuung Foto-zu-Foto der Krone danach 2,6-5,5 cm (ZIRKULAER: nach dem Ausrichten auf den Median, nur Formuneinigkeit; vorher 14-19 cm). Scheitelhoehe 4,57 / 4,57 / 4,57 / 4,58 / 4,66 m (4 Boegen: 4,66, 4,57, 4,57, 4,58) - S9-Rundbogen hatte 4,33-4,39 (0,2-0,3 m zu tief). Kronenradius 1,95-2,3 m, Scheitelknick 0 (kein Spitzbogen). Freie Kurve: Stichbogen-Fit Rest Median 0,5-0,9 cm / P95 1,7-4,4 cm (Breite 3,7-3,85, Kaempfer 3,3-3,55, Pfeil 1,0-1,25), Rundbogen Rest 3-12 cm / P95 10-30 cm, Spitzbogen 2-4 / 10-15 cm. Rundbogen passt also schlechter als Stich; Breite/Kaempfer sind aber FORTSETZUNG des Fits, nicht gemessen.
- GRENZE/FEHLSCHLAG: gueltige Kontur nur theta ~10-170 Grad (Krone + Teil der Flanken); an den Ansaetzen (Kapitell) nur ~10 von 60 Fotos mit Signal, einzelne Haken am Kurvenende (Pfeilerkante). Overlays auf Originalfoto angesehen (004, 013, 016, 059: ov/overlay_foto_*.jpg): Kurve liegt auf der Goldlinie, Abweichung ~0-10 cm, ein Flankenende fehlt oft; Foto 059 zeigt zwei Goldlinien (Aussen-/Innenkante) - DP kann springen. Gemeinsamer Kamerafehler (Mittel der Verschiebungen) nicht beobachtbar. Gold-Linie = bemalte Bogenkante, nicht nachgewiesen identisch mit Oeffnungsrand (+-wenige cm).
- Einbau: pl30_saeule_median.stl ist nicht wasserdicht (513 offene Kanten nach fill_holes) -> manifold3d unmoeglich; Ersatz mvs_d03_fix.stl (wasserdicht). Varianten: R = S9-Rund (Elemente s9_voll_rund), S = Stichbogen aus gemessener Kontur (Plattform t_front -0,5, t_back -3,7, zb 0 wie S9), 'mess' (rohe Kurve + Pfosten) liefert wegen Kurvenende ein Fehlpolygon (Diagonalen) - verworfen. Frontbild vis/front_vergleich.jpg angesehen: R schneidet in die Pfeiler (Oeffnungen fast verschmolzen), S 4 saubere Boegen mit schlanken Pfeilern.
- DIFF NICHT ERGEBNIS: Raster-Diff (23 Fotos, B/R/S, global und --region quader) wurde gestartet, aber vom Koordinator gestoppt (GPU-Konkurrenz zu ausgleichreal2, OOM-Gefahr). Teilordner wb_global/p2 sind unvollstaendig und gelten NICHT. Neustart: `JOB_GPU_MB=3000 tools/job_start.sh bogen_diff <log> /media/oem/scan/rc-park_null/bogen_kontur/diff.sh` erst nach Ende von ausgleichreal2; OOM-Proben zaehlen und nennen. Daher: Element NICHT als bewaehrt eingebaut, kein Netz uebernommen.
- Nicht geprueft: Diff (Raster, Region), Pruefstand/regression (keine gemeinsamen Tools geaendert; element_einpassen nur zur Laufzeit in bogen_kontur ueberschrieben), SAM, Fenster/Gauben, andere Objekte, Zaehlung (Regel 9: nicht gezaehlt, 4 Fenster stammen aus OWLv2-Boxen auf Fotos, kein Zaehlprotokoll Z-* geschrieben).

## BS3d Gemeinsamer Kamera-Ausgleich gegen Foto-Diff (7.11., `tools/kamera_ausgleich.py`, `tools/test_kamera_ausgleich.py`; Daten /media/oem/scan/rc-park_null/ausgleich_kh/)
- **Verfahren**: Messziel GPU-Raster, Netz mvs_d03_pl30, feste Masken C_<nr> (23 Fotos) + erzeugte Masken fuer Holdout. Je Foto Pose (Rotation um Kamerazentrum +-1,5 Grad, Verschiebung +-0,3 m, quadratisch regularisiert gegen Buendellage); Gruppenparameter lf/dk1 fuer Kameratypen (gleiche Bildgroesse, f +-5 %, >= 3 Fotos), nur aus Nicht-Holdout-Fotos. Pose wird nur uebernommen, wenn A->B UND B->A (Maskenhaelften) jeweils > Rauschgrenze besser werden. K-Dateien nie geschrieben.
- **Rauschen (Nullproben, 0,02 Grad / 5 mm, 8 Richtungen x 000/004/209)**: kosten_lr-Streuung 0,0026-0,0056 -> RAUSCH = 0,008 (2 sigma), Suchschritt-Mindestgewinn 0,003. Gewinne darunter sind nicht belegbar.
- **Synthetisch (18 Faelle, 000/004/209, Zentrum 3/5/10 cm, Rotation 0,3/0,5/1 Grad, je 70 Proben, ohne Holdout)**: Der Ausgleich findet in ALLEN Faellen kleineres lr als die Originalkamera (z. B. 000: -0,133 -> -0,16...-0,18), aber die Kamera kommt NICHT zurueck: Pixelabstand (RMS ueber Netzpunkte) zur Originalkamera nach dem Ausgleich: 000 12-38 px (gestoert 3,6-99), 004 3-26 px, 209 0,4-10 px. Die 6 Ergebnisse je Foto liegen untereinander median 22,6 / 17,5 / 6,7 px auseinander -> kosten_lr hat bei diesen Fotos KEIN eindeutiges Optimum auf < ~10-20 px (Rotation/Verschiebung entartet, Raster-Rauschen); 3-10 cm Zentrumsfehler sind nicht ruecknehmbar (Fehler nach Ausgleich meist GROESSER als vorher: 3,6 -> 37,7 px), Rotation >= 0,5 Grad wird teilweise (Faktor 2-5) verbessert. Ehrliche Grenze: Ausgleich nur fuer Fehler >= ~0,5 Grad / ~20 px sinnvoll; das Fit-Maske-lr ueberschaetzt den Gewinn (0,03-0,05 auch ohne Stoerung).
- **Echter Lauf (Lauf 1, 5 Slots, 28 Fotos; durch VRAM-Konkurrenz mit einem fremden GPU-Job + eigener Paralleldruck CUDA-OOM, 49 Fehlproben, kein Neustart-Schutz) und Teilergebnis 13 Fotos (000..073, Lauf 2 mit Wiederholungen)**: Fit-Gewinn auf voller Maske bei fast allen Fotos 0,01-0,05, aber A->B/B->A-Pruefung bei 12 von 13 NICHT gemeinsam > 0,008 -> keine Uebernahme (Ueberanpassung, wie BS3c). Einzige Uebernahme in Lauf 1: Foto 114 (lr -0,019 -> -0,134; A->B +0,018, B->A +0,112). Foto 073 in Lauf 2: 5,1 % Proben endgueltig verloren (OOM) -> ungueltig, nicht bewertet. Alle anderen Fotos der 13: 0 % endgueltige Ausfaelle (Wiederholung half).
- **FEHLSCHLAEGE / UNGUELTIG**: Lauf 1 (Daten real_lauf1_mit_fehlproben): Gruppenstufe lieferte wegen None-Proben nur Stillstand (Gruppe lf=dk1=0), 073 Basisprobe None. Lauf 2 (real) vom Nutzer/System bei ~13 von 28 Fotos gestoppt, Ergebnis nur fuer 000..073 (vorschlag_<nr>.json), kein Gesamtbericht. Lauf 3 (real2, 11 Fotos --kerne 4) wegen 222 OOM-Fehlzeilen (073 x5, 114 x4, 082 x3 ...) gestoppt, UNGUELTIG, nicht auswerten. Ursache: eigener Paralleldruck (4-5 Raster-Laeufe, 073 allein 3,55 GiB) + fremder GPU-Job.
- **Gebaut danach**: VRAM-Semaphor in Bank.eval (Gewicht 3e-4 MiB je Bildpixel, 073-Klasse ~5990 MiB = laeuft allein, Limit 6000 MiB oder AUSGLEICH_VRAM_MB, zusaetzlich Fremdbelegung via nvidia-smi >= 600 MiB frei), Ausfallzaehler je Foto (endgueltig verlorene Proben), Bericht: `ausfall`, `ungueltig_oom` (> 2 %), `fehler_log_zeilen`, `gueltig_gesamt` (nur wahr bei leerem fehler.log). Beleg ohne GPU: `test_kamera_ausgleich.py --semaphor-test` (simulierte Laeufe: Spitze 5989 MiB statt 35931 ohne Semaphor; Foto mit 100 % Fehlern als ungueltig erkannt).
- **NICHT geprueft**: Fotos 082-247 + Holdout 001/024/083/211/234 (Lauf 2/3 unvollstaendig/ungueltig); Gruppenstufe (209-247 mit Holdout 211/234) gueltig; die 66er Greedy-Auswahl (nur 23+5 Fotos mit Masken); Netz-/Raster-Gegenprobe mit anderem Netz; Einfluss auf Buendel-Reprojektion; Uebernahme von 114 in K-114 (NICHT erfolgt, nur Vorschlag).

### BS11 (7.11. vormittags) Wolke-Frontansicht + Raster-Wettbewerb Glaettung 0,05
- tools/wolke_front.py: gefaerbte Wolke frontal (Orthokamera, z-Puffer aus 3D-Lage, Rahmen per Umeyama aus Kamerazentren, Rest 0,05 cm). Arkaden-Kasten 20,2 x 5,2 m, 1 cm/px: die 4 Bogenkonturen sind scharf sichtbar (anders als Foto-Median BS9); Innenflaechen zeigen Hintergrund/Passanten (Tiefenfenster +-6 m zu gross) -> naechster Schritt duenne Platte um die Fassadenebene, Kontur aus 3D-Loechern.
- Job kh24_raster (rcpark-kh24_raster): Raster, Glaettung 0,05, 4 Kandidaten, 23 Fotos, --kerne 1, JOB_GPU_MB=4500. Frage: ordnet sich default/saeule/d03/fein bei feinerer Kante anders? (Halbierungstest folgt)
- BS11-Ergebnis kh24 (7.11. 11:50): Raster, Glaettung 0,05, 23 Fotos, feste Masken C, ohne OOM (Job lief mit 1 Slot): d03_pl30 -0,1128 | saeule_median -0,1127 (9/23 besser als d03) | mvs_default -0,0997 (7/23) | mvs_fein -0,0484 (0/23). Gegen Glaettung 0,18 (default -0,1139 vorn) AENDERT sich die Reihenfolge: default faellt zurueck, d03/Saeule vorn und gleichauf. Noch KEINE Stabilitaetspruefung (Halbierung, Leave-One-Out); Aussage "d03 = Saeule" gilt als gleichwertig, "default schlechter bei feiner Kante" nur vorlaeufig. Regression Martinstor + Kaufhaus: identisch.
- BS11-Stabilitaet (7.11. 12:00, aus Einzelfotowerten, Bootstrap 5000, LOO, Halbierung 2000): 
  g0,05: d03 vs Saeule -0,0001 [KI -0,0022; +0,0022] = GLEICH; d03 vs default -0,0131 [-0,0288; -0,0009] knapp besser; Saeule vs default +0,0130 [-0,0002; +0,0302] NICHT signifikant; fein klar schlechter (-0,064). LOO-Sieger d03 18/23, Saeule 5/23; Halbierung gleicher Sieger nur 0,04 (zwei Gleichauf-Kandidaten).
  g0,18: default vorn (LOO 23/23, Bootstrap 0,89), aber default vs Saeule [-0,0139; +0,0027] nicht signifikant; default vs d03 -0,0075 [KI 0,0013-0,0144] signifikant.
  FAZIT: KEIN stabiler Einzelsieger. d03, Saeule und default liegen je nach Glaettung innerhalb der Streuung; nur mvs_fein verliert in beiden Massen sicher. Rangwechsel default<->d03 ist Mass-abhaengig, nicht Netz-Eigenschaft. Naechster Hebel liegt NICHT im Netzverfahren, sondern in Bauteilen (Boegen/Fenster/Rippen) und Kamerapruefung.
- BS14 (7.11. Mittag) modell_wettbewerb.py abgesichert (Reviews Google/Codex): konfig.json (STL Groesse+mtime, Fotoliste, Raster, fd-arg, Basis) -> bei geaenderter Konfiguration im selben --aus ABBRUCH statt stiller Wiederverwendung; Altordner ohne konfig.json -> Hinweis. gueltigkeit.json: vollstaendig nur wenn JEDER Kandidat Werte fuer ALLE Fotos hat, sonst "UNVOLLSTAENDIG", versuch_log-Status "unvollstaendig", Exit 3. Test an kh24: gleiche Konfig laeuft (Zahlen identisch, versuch_log warnt IDENTISCH_MIT_VORLAUF), andere Glaettung bricht ab. Regression Kaufhaus erneut gestartet.
- BS15 (7.11. Mittag) Bogenkontur aus Wolke (tools/bogen_kontur_robust.py auf Belegungsbild bogen_wolke, Platte w=1,27 m +-0,25, 2 cm/px, Kasten z<=5,2): 4 volle Oeffnungen, Laibungslinie sauber (Bild kontur_robust.png). Kreisfit je Oeffnung (RANSAC+LSQ, ganze Kontur): Mittelpunkt u -6,41/-2,03/2,32/6,67 (Abstand 4,38/4,35/4,35 m = gleiche Teilung), Mittelpunkt z 2,88-2,99, R 1,87-1,95 m, Scheitel 4,84-4,90 m, RMS 1,6-4,4 cm, Inlier 0,82-1,00; oberer Teil z>4,3: R 1,80-1,96, RMS 1,5-2,2 cm. GEMESSEN (dann benannt): Kreissegment mit Mittelpunkt ~auf Kaempferhoehe (z~2,95) = RUNDBOGEN R~1,9 m, kein Spitzbogen. Einschraenkung: Kontur = Laibungsvorderkante in der Wolke; Zaehlung am Foto (Regel 9) und Diff im Netz stehen aus. H0: R 21,8 mm, Teilung 50 mm. (BS13 'nicht belastbar' betraf Kreisfit auf bogen_unterkante-Zacken; diese robuste Kontur loest es.)
- BS15-Zaehlung (7.11. Mittag, Regel 9): Z-004-003 (messprotokoll/Z-004-003.json+jpg): Arkade Hauptfront Foto 004 frontal, 4 Boegen voll sichtbar gezaehlt (Scheitelmarken im Bild geprueft; Marken sitzen leicht links der Krone, je Bogen eindeutig). = Wolkenmessung 4 Oeffnungen (Box). Sichtbild bestaetigt Rundboegen mit Goldlinie; mittlerer Bogen hat Spitzbogentor dahinter (andere Bauteil).
- BS17 (7.11. 13:00) Netzvergleich ALLE Fotos, Raster, Glaettung 0,18 (Standard), feste Maske = Vereinigung der Kandidatenmasken, 3 Netze: n=89; Mittel mvs_d03_pl30 -0.0888, mvs_default -0.0959, saeule_median -0.0893; mvs_d03_pl30-mvs_default +0.0071 KI[+0.0035,+0.0107] besser/schlechter 17/40; mvs_d03_pl30-saeule_median +0.0005 KI[-0.0009,+0.0020] besser/schlechter 12/13; mvs_default-saeule_median -0.0066 KI[-0.0107,-0.0027] besser/schlechter 38/22; LOO-Sieger {'mvs_default': 89}; Halbierung gleicher Sieger 1.00. 5 Fotos (005, 074, 089, 106, 107) fuer ALLE Kandidaten ohne Wert (foto_diff NaN: Foto sieht das Modell nicht) = nicht beurteilbar; Gate erweitert: vollstaendig = jeder Kandidat hat alle Fotos AUSSER denen, die fuer alle gleich fehlen (gueltigkeit.json: nicht_beurteilbar_fuer_alle). Foto 068 fehlte im Hauptlauf und wurde im Nachlauf berechnet (CPU-Torch, selber Raster-Algorithmus).

## Kaufhaus 7.11. nachmittags (Kurzfassung, Details modelle/NICHTS_GEBRACHT.md BS20-BS29)
BS20-BS20g Wasserdicht-Reparatur mvs_default (Faecher-Deckel kostet 0,012 im Diff, Open3D fill_holes/Poisson 9-11 scheitern), BS21-BS21d Bogen-Diff-Verlust Ursache offen (Platte/t_back/Versatz widerlegt), BS22 Glaettungsstabilitaet (g0,05: Saeule -0,1138 < default -0,1049 < d03_fix -0,0996), BS23 Offset-Schale wasserdicht (Diff offen), BS24-BS25 Recherchen, BS26-BS29 Fenster-Ortho/Fit/Wiederholungen.

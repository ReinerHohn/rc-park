# Lagebild Kanten-Drahtgitter Kaufhaus Freiburg (Fotos + Punktwolke) - Stand 9.11.2026, ~17:10

Zweck: nüchterne Destillation aller Dokumente zum Thema 3D-Kantengitter. Nur Gelesenes, keine neuen Messungen.
Gelesen: NICHTS_GEBRACHT.md, LOGBUCH_2026-11-09.md (ganz), METHODIK_KANTEN_STABILITAET.md, ERKLAERUNG_DRAHTGITTER.md,
RECHERCHE_DRAHTGITTER / _FUSION / _KANTEN_2 / _KANTEN_MULTIVIEW / _DRAHTGITTER_VERFAHREN (alle 9.11.), RECHERCHE_KANTENERKENNUNG_2026-11-08.md (Kopf),
STAND_2026-11-06.md (S8/S9/S10), STAND_KURZ_2026-11-06.md, LOGBUCH_2026-11-08.md (Ortho-Editor), PLAN_2026-11-06_H0_DETAIL.md (Abschnitt 7),
VERSUCHSREGISTER (BS61, BS65, Überschriften CQ-CV), Docstrings tools/kanten_*.py, gitter_*.py, viewer_kanten_*, editor_draht.*,
dazu die Ergebnisdateien unter `/media/oem/scan/rc-park_daten/kaufhaus_alle/segmente_*.json` (Segmentzahlen selbst gezählt) und die Lauf-Logs `/tmp/aufbau6.log`, `/tmp/sweepoben.log`, `/tmp/editordraht.log`, `/tmp/schleife_stabil.log`.

Begriffe: "Treffer" = Anteil der Segment-Stützpunkte (alle 5 cm) mit Referenzpunkt < 10 cm; "Abdeckung" = Anteil der Referenzpunkte mit Segment < 10 cm (beide `tools/gitter_naehe.py`, je Höhenband z<12 / 12-15 / >15 m). "Foto-Stützung"/"praez" = Anteil der sichtbaren Fotos, die am projizierten Segment eine Kante zeigen (`kanten_schleife.py`). Werte sind Anteile 0..1.

---

## 1. Alle bisher versuchten Verfahren und Stufen (je eine Zeile)

### 1a. Kantenerkennung 2D (im Foto oder in der Ortho-Ansicht)

| # | Verfahren / Stufe | Ergebnis (Zahl, wenn vorhanden) | Status | Grund |
|---|---|---|---|---|
| 1 | Canny grau, Einzelfoto, Abstimmung über Fotos | 3D-Variante: 224 Segmente / 132 m, Stützung 0,71, Erker-Overlay fast leer | als Alleinquelle verworfen; als 1 von 3 Quellen in Nutzung | zu viel Textur, bleibt an Wolkendichte hängen |
| 2 | LSD auf Wolken-Ortho, 9 Kanäle x 3 Kontraststufen, Stimmenfusion (Editor `/api/ortho`, 8.11.) | 4488-5365 Fusionslinien Ebene 0; gegen Modellkanten nur 0,02-0,08 F über Zufall | überholt | Wolken-Ortho verrauscht/inpainted; Metrik trennt nicht |
| 3 | Phasenkongruenz (phasepack) auf Ortho | Präzision 0,06-0,15 | verworfen | kein Vorteil gegenüber LSD |
| 4 | Lab-b (Blau-Gelb-Chroma) als Kanal | Präzisionsgewinn 0,25 (Familie), Varianten bis 0,59 | eingeflossen in Farb-Sweep | bester Einzelkanal in der Foto-Stützung |
| 5 | Gleichgewichtete Fusion nach Stimmen/Familien | Gewinn nur 0,08-0,14, schlechter als Lab-b allein | verworfen | korrelierte Varianten verwässern |
| 6 | Foto-Ortho per Homographie + LSD je Foto, Mehrheit, Median (`fotokanten`) | Sichtbefund besser als Wolken-Ortho, nicht quantifiziert | überholt | Foto-Stützung als Messung wäre zirkulär |
| 7 | `fotokanten_voll` Auto-Sweep nach "Foto-Einigkeit" | wählte Tiefe=True gegen Sichtbefund | verworfen | Score bevorzugt wenige Fotos |
| 8 | `fotokanten_ref` (schärfstes Foto liefert Geometrie, Rest stimmt ab) | 837 -> 1022 Linien Ebene 0; Held-out Ebene 1: Präz 0,558 / Recall 0,173 / Gewinn 0,091 vs Wolken >=8: 0,506 / 0,315 / 0,099 | nicht bewiesen besser, überholt | höhere Präzision, weniger Recall, Gesamtgewinn gleich |
| 9 | Synthetischer Rundlauf (`/api/synth`, 14 gerenderte Fotos, Posenstörung 0-8 cm) | F 0,32-0,36 für alle Varianten | als Messverfahren verworfen | Wahrheit enthält unsichtbare Kanten, Metrik trennt nicht |
| 10 | Subpixel-Canny (`kanten_subpixel.py`) | Rest-RMS 0,84 -> 0,77 px (-9 %) | nicht weiterverfolgt | Gewinn klein, Kanten in Entzerrung ~0,8 px breit |
| 11 | DexiNed (kornia, BIPED-Gewichte) als Zusatzquelle in `fotokanten_ref` | 1551 Linien Ebene 0, Geländersäulen/Konsolen/Sprossen erfasst; Fehllinien an Zelten, falscher Bogen über Statue | widersprüchlich dokumentiert (s. Abschnitt 4) | Lizenz der Gewichte offen; im Drahtgitter-Weg nicht genutzt |
| 12 | DeepLSD / ScaleLSD / HAWP / TEED (gelernte Segmentdetektoren) | nicht gelaufen; Installation zweimal vom Berechtigungsprüfer abgelehnt; DeepLSD+GlueStick jetzt in venv-limap installiert | offen | Freigabe/Lizenz; "noch nicht genutzt" |
| 13 | S10 Teil A: vier weiche Kantenkarten P1 hell / P2 Farbe / P3 DexiNed / P4 Segmentgrenzen + Mittel/k-Stimmen (6.11., 94 Fotos) | Synth F1 bis 0,88 (k=4), Textur-Fehlalarm 0,03-0,06 | nicht in den Drahtgitter-Weg übernommen | Vorläufer der Stabilitätskarte; Teil B schwach (s. 1b) |
| 14 | SAM (vit-large, Kacheln, Rechteck-Regularisierung) auf Referenz-Ortho | 393-749 Flächen Ebene 0; Nutzer: "ganz genau, was ich will" | in Nutzung (Quelle 1: SAM-Grenzen) | Objektgrenzen scharf; verschmilzt feine Teile (Sprossen) |
| 15 | Farb-Sweep: Canny auf 5 Kanälen, Mehrheit je Wolkenpunkt (`kanten_3d_vote.py --sweep`) | Statuen, Sprossen, Wappen sichtbar; Ziegeltextur der Türmchen stört | in Nutzung (Quelle 3) | findet Kanten ohne Helligkeitskontrast |
| 16 | Kanten-Stabilitätskarte (`kanten_stabil.py`: 261 Läufe/Foto = 9 Kanäle x Ton x Sigma x Schwelle, 2 s GPU) | Sichtbefund IMG_6261: Dachlinie, beide Staffelgiebel, Helme, Gauben, Bögen sauber; 440 Fotos gerechnet | in Nutzung (Grundlage des Tiefen-Sweeps) | Zählen über Parameter statt eine Schwelle; einzige Quelle, die Dach/Giebel/Helme im 2D zeigt |
| 17 | Bewertung gegen Modellkanten (`/api/vsmodell`) | alle Verfahren 0,02-0,08 F über Zufall | Metrik verworfen | Modell zu grob, Fassade hat mehr Kanten als Modell |
| 18 | Bewertung per Foto-Stützung (`/api/vsfoto`, Canny an 3D-Position) | trennt Verfahren (Lab-b vorn) | nur Zwischenmetrik | nur Präzision, kein Recall |
| 19 | Nutzerkanten als Wahrheit (`kanten_wahrheit.jsonl`, Editor 8.11.) | Datei existiert nicht (geprüft) | nie entstanden | "abwarten" seit 9.11. früh |

### 1b. Kanten in 3D (Linien, Segmente, Gitter) und Körper daraus

| # | Verfahren / Stufe | Ergebnis | Status | Grund |
|---|---|---|---|---|
| 20 | `kanten_3d.py` (S8, 6.11.): LSD je Foto + Wolkensaat -> 3D-Linien aus Bildsegmenten | 930 Linien in 66 s, Overlay 004 "stimmt weitgehend" | abgelöst | Synth-Beweis des S8-Gesamtwegs (Ebenenmodell) nicht bestanden |
| 21 | `ebenen_modell.py` (S8): Ebenen + Zellen + Graph-Cut, Kanten als Schnitt | Kanten p90 74-274 cm, Ergebnis springt mit alpha | gescheitert | Zellbelegung (Carving) löst Halle/Giebelstufen nicht auf |
| 22 | S10 Teil B `kanten_feld3d.py` (EMAP-Eigenbau: weiche Karten -> Voxel-Kantenfeld) | Synth 0,835/0,80 (Voxel 0,05 nachträglich gewählt); Kaufhaus Holdout Präz 0,55 / Vollst 0,57 (Kontrolle 0,46/0,43); Bögen 1 von 4 | schwach, nicht weitergeführt | Feld zu dünn/rauschig, Bogen-Test gescheitert |
| 23 | S10 Teil C Wolkenfilter F0-F3 vor dem Kantenfeld | Bögen 1/4 .. 2/4 | kein Gewinn | Rauschen; Nebenfund vis-Index-Bug (Bild-ID- statt Namensreihenfolge) |
| 24 | S9 Bogen-Einpassen mit Canny-/3D-Kanten als Fitdaten | ~10^4 Hintergrundkanten, Fits sprangen an Boxränder; alle 4 Bögen abgelehnt | Kanten als Fitdaten verworfen | Kostenlandschaft flach |
| 25 | LIMAP BS61 (7.11.): COLMAP-Tiefenkarten, pytlsd-LSD, 94 Fotos | 1773 Linien (Spur>=5: 964), Deckung >=70 % bei 63 % (Kontrolle 36 %) = Linien echt; 92 % <=15 cm vom Netz (zirkulär); Kantenzwang BS65: +0,0015/-0,0003 = Rauschboden | Ergebnis liegt, ungenutzt | kein Modellgewinn messbar; Linien nie zu Bauteilen gemacht |
| 26 | LIMAP-Prototyp 9.11. (16 Fotos, Ausschnitt r=3 m, LSD, Wolkentiefe) | 91 Linien, 18 mit Spur>=5, Overlay IMG_6228 meist nicht auf Kanten | verworfen (mit Wolkentiefe) | Tiefe aus Wolke dominiert, LSD ohne Lernen |
| 27 | LIMAP-Triangulation ohne Wolke (hloc/DeepLSD/GlueStick in venv-limap) | Installation fertig | offen, nie gelaufen | - |
| 28 | SAM-Mehrfoto-3D (`sam_mehrfoto_3d.py`, 80 Fotos): Masken über Fotos per Punkt-IoU vereinigen | 280 Objekte, 1,58 von 1,83 Mio Punkten zugeordnet; Wand = ein Objekt | in Nutzung als Maskenquelle | Union-Find verklebt Wand (Fusion-Recherche: Consensus-Merge nötig) |
| 29 | Körper aus SAM-Objekten: Voxelhüllen, Voxel-Schnitzen, Hoppe-SDF-Schalen, Dreiecks-Zuschnitt, Relief-Solid-Kachel, pymeshfix-Schließen | Hüllen/Schnitzen "Müll"; Zuschnitt = "erster brauchbarer 3D-Stand" (nur Schalen); Relief-Kachel wasserdicht, aber verrauscht; pymeshfix 238/240 dicht, aber Keile | alles außer Zuschnitt verworfen | Schalen sind keine Körper; Wolke zu dünn (Dach), Dicke = Annahme |
| 30 | `kanten_3d_vote.py`: SAM-Grenzen aus 80 Fotos je Wolkenpunkt abgestimmt (>=6 Sichten, Anteil >=0,5) | 79k Kantenpunkte; Fenster/Statuen/Konsolen/Bogen als Linien | in Nutzung (Weg A) | 3D-Lage aus der Wolke -> nichts über ~15 m |
| 31 | `kanten_segmente.py` (GPU-RANSAC auf Kantenpunkten) | 578 Segmente aus 79k, 43k Restpunkte (gekrümmt) | in Nutzung | Bögen nur als kurze Geradenstücke |
| 32 | `kanten_schleife.py`, Beleg nur SAM (6 Durchgänge) | Präz 0,630 -> 0,694, Recall (<3 cm) 0,507 -> 0,428, 578 -> 787 Segmente, Abdeckung 42 % | überholt | Verschieben zur Fotokante entfernt Segmente von Wolkenkanten; löschte 160 von 298 Sprossen-/Farbsegmenten (Abdeckung 0,47 -> 0,15) |
| 33 | Beleg = SAM ODER Canny ODER Sweep (lax) bzw. >=2 von 3 (streng) | Stützung 0,964 (392 Seg., Abdeckung 0,49); streng mit Durchziehen 364 Seg. / 303 m, 0,957; lax 212 -> 480 m | streng in Nutzung, lax verworfen | lax erzeugt Fehlkanten |
| 34 | Getrennte Quellen + Median über Ränge (`kanten_vote_quellen.py`, `kanten_fusion.py --rang --top 0.04`) | 39 600 Kantenpunkte (= `ref_wolke_kanten.npy`, 39 605) | in Nutzung; zugleich "Wolken-Referenz" | Nutzerwunsch Median statt Mittel |
| 35 | Canny-Abstimmung + Schleife (--sicht 8 --anteil 0.85) | 224 Segmente / 132 m, Stützung 0,71 | verworfen | Erker-Overlay leer |
| 36 | Bogenfit RANSAC (`ransac_boegen`) auf Restpunkten | 2 Bögen aus 19 685 Punkten; in aufbau2_loop 14 gefunden, 4 fotogestützt | praktisch nicht erfasst | Rundungen fehlen (Arkaden, Statuen) |
| 37 | `kanten_triangulation.py` (Linienpaare ohne Wolke, 12-24 Referenzen) | 880 Segmente (3 Bögen unten, >20 m nichts); 2. Lauf 1200 Linien/Foto: 7728 Seg., 7 mit Score>=0,8 (schlechter); tri6 2353 Seg. (2319 nach Duplikaten), 199 über 15 m, 0 über 25 m | als Beitrag zur Karte genutzt, oberhalb 15 m offen | z>15: 115 517 Kandidaten -> 285 streng / 14 109 lax, Ursache offen |
| 38 | Triangulation mit gelockerten Schwellen (--zmin 14 --r1 0.35 ...) | 171 130 Segmente / 422 km | verworfen | reines Rauschen (zufällige Mehrfachtreffer auf Textur) |
| 39 | Karte = Wolken-Vote (364) + tri6 (2319) -> `kanten_buendel.py` | 2683 -> 1415 Segmente, 1399 -> 849 m; Dachfirst/Staffelgiebel fast leer | überholt durch Tiefen-Sweep | Bündelung im Dach schadet (Abdeckung 0,42 -> 0,21) -> nur unter 14 m |
| 40 | Kanten-Tiefen-Sweep (`kanten_tiefe_sweep.py`: Kantenpixel der Stabilitätskarte entlang Strahl, 12 Nachbarfotos, Peak) | 80 Refs -> 631 022 Punkte; Konsens zeigt First z~27 m, Traufe ~14,5 m; `segmente_hoch_ts.json` 45 Seg. (tol 0,12, z>14); `segmente_tsweep.json` 513 Seg. (tol 0,05) | in Nutzung (Kern) | erste 3D-Quelle für Dach ohne Wolke; Dachpunkte dünn |
| 41 | Aufbau 2 (`gitter_aufbauen.py`: Sweep 220 Refs = 2,06 Mio Punkte + Wolkenkanten, tol 3 cm unten / 15 cm oben, SVD-Ausgleich) | `segmente_aufbau2.json` 1318 Seg. (127 >15 m, 70 >25 m) | in Nutzung | - |
| 42 | Schleife gegen Stabilitätskarten (`--stabil`, lax V>=0,25 / streng V>=0,40) | `segmente_aufbau2_loop.json` 1754 Seg., praez 0,64 -> 0,72, recall 0,55 -> 0,57 (historie); 100 >15 m, 52 >25 m | **aktueller Stand im Editor** | Stützung 0,72 nicht mit 0,96 von früher vergleichbar (strengere Karten) |
| 43 | Overlay ohne Sichtbarkeitstest (`gitter_overlay.py`) auf IMG_6261, IP_6120, nu_9e19, IP_6254, IP_6233 | Dachfirst, Staffelgiebel-Seiten, Traufe sitzen auf den Fotokanten; Konsolen-Nahaufnahme zeigt Bündel paralleler Streuer | Sichtbefund positiv | Z-Puffer-Overlay der Schleife zeigt Dach nicht (Wolke leer) |
| 44 | Streuerfilter `gitter_streuer.py` (score<0,6 über 13 m) -> aufbau3 | 1754 -> 1665; Dach-Abdeckung vs B 0,32 -> 0,20 | verworfen | wirft echte Dachkanten weg |
| 45 | Sweep B (`--exclude`, 220 andere Referenzfotos) | 2,21 Mio Punkte, Konsens 30 777 (`tsweepB_konsens.npy`) | in Nutzung als Prüfmenge | unabhängig nur in der Fotoauswahl, nicht im Verfahren |
| 46 | Kontrastfilter `gitter_statistik.py` (Schlauch gegen Ring, Schwelle 2,2) -> aufbau5 | 1406 Seg.; vs B Treffer 0,97/0,96/0,53, Abdeckung 0,54/0,55/0,31; vs Wolke Abdeckung 0,87 -> 0,71 und 0,75 -> 0,66 | verworfen | auf B getunt, entfernt echte Kanten, die die Wolke sieht |
| 47 | Union A+B ohne Filter (`segmente_ab.json`) | 1803 Seg.; vs Wolke 0,43/0,84 und 0,57/0,61 (schlechter als aufbau2_loop) | verworfen | mehr Sweep-Punkte allein bringen nichts |
| 48 | aufbau6 (16:55, `gitter_aufbauen.py` mit `--qe`-Fix: Endquantil 0,02 kürzte jedes Segment um ~4 %) | 1318 Seg., 127 >15 m, 71 >25 m | **nicht dokumentiert**, unkommittiert | nur Log `/tmp/aufbau6.log` |
| 49 | Sweep oben o1/o2 (17:00-17:06, `--tol_o 0.15/0.10 --minpts_o 4/5 --minlen_o 0.6`) | o2: 1598 Seg., 366 >15 m, 198 >25 m; vs B: z<12 0,95/0,57, 12-15 0,91/0,62, **>15 0,54/0,72** | **nicht dokumentiert**, keine Wolken-Gegenprobe, nicht durch Schleife | nur Log `/tmp/sweepoben.log`; Editor weiter auf aufbau2_loop |
| 50 | Draht-Editor (`editor_draht.py`/`.html`, Port 8767, `?flach=1`) | geladen 1754 Kanten, 78 942 Kantenpunkte; Zieldatei `modelle/kaufhaus_grob3/draht_kanten.json` existiert nicht | gebaut, ohne gespeicherte Korrektur | WebGL beim Nutzer schwarz (Ursache offen), 2D-Ersatz |
| 51 | Kantenviewer (`viewer_kanten_bauen.py`, Canvas) | Wolke + Kantenpunkte + Gitter, Ebenen schaltbar | in Nutzung | - |

Nicht als 3D-Drahtgitter gelaufen, nur recherchiert: Line3D++, ELSR, EMAP, NEAT/NEF, CurveGaussian, SketchSplat, 3D Curvix, PC2WF, Point2CAD, Manhattan-Richtungszwang, IRLS-Ausgleich, Hough auf Plücker-Raum, RJMCMC, PolyFit/KSR (KSR lief 7.11. als Netz, BS62, schlechter), Consensus-Merge (MaskClustering/SAI3D).

---

## 2. Bester Stand

**Datei:** `/media/oem/scan/rc-park_daten/kaufhaus_alle/segmente_aufbau2_loop.json` (im Logbuch nur als `segmente_aufbau2_loop.json`), 1754 Segmente, 1325 m Gesamtlänge, 100 Segmente mit Oberkante über 15 m, 52 über 25 m, 4 Bögen, 0 fixierte Nutzerkanten. Entstehung: Stabilitätskarten (440 Fotos) -> Tiefen-Sweep A (220 Referenzfotos, 2,06 Mio Punkte) + Wolken-Kantenpunkte (39 605) -> `gitter_aufbauen.py` (1318 Seg.) -> `kanten_schleife.py --stabil` (1754 Seg.). Dies ist die Datei, die der Editor lädt (Logbuch Korrektur Runde 3, Editor-Log 16:35).

**Kennzahlen aufbau2_loop (gitter_naehe, Toleranz 10 cm):**

| Höhenband | vs Wolken-Kanten (39 605 P.) Treffer / Abdeckung | vs Sweep B unabhängige Fotos (30 777 P.) Treffer / Abdeckung |
|---|---|---|
| z < 12 m | 0,49 / 0,87 | 0,94 / 0,57 |
| 12-15 m | 0,67 / 0,75 | 0,93 / 0,59 |
| > 15 m | nicht angegeben (Wolke dort fast leer) | 0,49 / 0,32 |

Foto-Stützung (Schleife, Stabilitätskarten als Beleg): praez 0,72, recall 0,57 (Toleranz 3 cm, andere Definition als "Abdeckung").
Ausgangspunkt zum Vergleich (`segmente_karte4.json`, 1638 Seg., vor Tiefen-Sweep): vs Wolke z<12 0,47/0,92, 12-15 0,61/0,81, >15 0,08/0,08; vs Sweep A 0,53/0,84, 0,68/0,88, 0,15/0,38.

Der neueste, undokumentierte Lauf o2 (17:06) liegt beim Dach deutlich darüber (vs B >15 m 0,54 / 0,72, 366 Segmente über 15 m), ist aber weder gegen die Wolkenreferenz gerechnet noch durch die Schleife gelaufen noch im Editor.

**Wie gemessen wird und wo der Zirkel liegt:**
- `gitter_naehe.py` zählt Nähe zwischen Segment-Stützpunkten und einer Referenzpunktmenge (GPU-kNN). Die Datei sagt selbst: "KEINE Wahrheit: beide Quellen können dieselben Fehler haben."
- Referenz 1 "Wolken-Kanten" (`ref_wolke_kanten.npy`) = Median-Fusion von SAM/Canny/Farb-Sweep auf Wolkenpunkten. Sie ist zugleich Eingabe von `gitter_aufbauen.py` (unteres Band). Abdeckung 0,87 unten misst also, wie viel der eigenen Eingabe das Gitter noch erklärt, nicht Richtigkeit. Über 15 m hat sie fast keine Punkte und kann das Dach nicht prüfen.
- Referenz 2 "Sweep A" (`tsweep80_konsens.npy`, 199 557 P.) ist ebenfalls Eingabe des Aufbaus (zirkulär); Referenz 3 "Sweep B" (`tsweepB_konsens.npy`) nutzt andere Referenzfotos, aber dieselben Stabilitätskarten, dieselben Kameraposen und dasselbe Verfahren. Systematische Fehler (Posen in der Höhe, Texturkanten, die in vielen Fotos gleich stehen) sind in A und B identisch. Lehre Runde 3 bestätigt das: ein auf B getunter Filter verschlechterte die Wolken-Gegenprobe.
- Foto-Stützung der Schleife wird gegen dieselben Stabilitätskarten gemessen, aus denen der Sweep die Punkte holt; Sichtbarkeit per Z-Puffer aus der Wolke, daher sind Dachsegmente dort unsichtbar und gehen in praez/recall nicht ein.
- Unten passt die Aussage "Treffer vs Wolke 0,49, vs B 0,94" nicht zusammen: die Hälfte der Segmentpunkte unter 12 m hat keinen Wolken-Kantenpunkt in 10 cm, aber einen Sweep-Punkt. Ob das Mehrinformation des Sweeps (Sprossen, Rahmen) oder gemeinsame Fehler von Sweep und Gitter sind, ist in keinem Dokument geklärt.
- Unabhängige Prüfungen (Nutzer-Handkanten, Synthetik für die 3D-Kette, Held-out mit anderem Verfahren wie LIMAP/Line3D++) existieren nicht. Die einzige verfahrensfremde Bestätigung ist der Sichtbefund der Overlays auf 5 Fotos (Dachfirst, Giebelseiten, Traufe sitzen).

---

## 3. Die fünf größten offenen Lücken

1. **Dach, Turmhelme, Staffelgiebel-Zacken.** Die Wolke endet bei ~15 m, der Tiefen-Sweep liefert dort nur dünne Punkte. aufbau2_loop: 100 Segmente über 15 m, Treffer vs B 0,49 / Abdeckung 0,32; Staffelgiebel-Zacken "noch nicht als Segmente" (METHODIK); Helme über 25 m: 52 Segmente, nie getrennt gemessen oder im Detail-Overlay geprüft. Triangulation über 15 m: 115 517 Kandidaten, 285 bestehen die strenge Prüfung, Ursache (Schnittwinkel, wenige Ansichten, Posen in der Höhe) offen; der vorgeschlagene Test "Dachrand von Hand als 3D-Linie in alle Fotos, Pixelabweichung messen" ist nicht gemacht. Die Kamerapose-Genauigkeit in der Höhe ist nirgends gemessen.
2. **Streuer-Bündel bei Nahaufnahmen** (Konsolen, IP_6233): lange, fast parallele Segmente mit Tiefenfehler. Beide Filter (Streuer-Score, Kontrast) sind verworfen, weil sie echte Kanten mitnehmen; Bündel sind in B belegt, also echte Kanten mit zu langer Fassung. Die empfohlene Abhilfe (IRLS-Ausgleich mit Kovarianz nach Strahlenwinkel, Richtungszwang, Hough-Mode; RECHERCHE_VERFAHREN Prio 1/7/6) ist nicht gebaut.
3. **Keine unabhängige Wahrheit.** Alle drei Referenzen stammen aus derselben Kette (Stabilitätskarten + gleiche Posen); die Wolkenreferenz ist Eingabe. `kanten_wahrheit.jsonl` (Nutzerkanten) existiert nicht, die seit 8./9.11. mehrfach empfohlene kleine Handwahrheit (6-10 Ausschnitte, 2-3 h) ist nicht entstanden, der synthetische Prüfstand für die 3D-Kette fehlt (nur 2D-Ortho-Synthetik, und die trennte nicht). Damit ist jedes "besser" seit dem 9.11. ein Sichtbefund oder eine zirkuläre Zahl.
4. **Kurven fehlen.** Arkadenbögen, Bogenringe, Statuen, Fenstergiebel-Rundungen kommen nur als kurze Geradenstücke oder gar nicht: 4 Bögen in aufbau2_loop (14 gefunden, 4 fotogestützt), 2 Bögen aus 19 685 Restpunkten bei der Fusion. Der parametrische Bogenfit auf Kantenkarten (Kreis/Ellipse, Parameter als Median über Fotos) steht in drei Recherchen als Prio 2 und ist nicht gebaut; der 8.11. Ortho-Bogenfit (2-Punkt+Tangente) wurde nicht in den 3D-Weg übernommen.
5. **Keine Körper aus dem Gitter.** Ziel laut ERKLAERUNG ist "geschlossene, druckbare Teile". Der Weg Drahtgitter -> Flächenzyklen/Ebenengraph -> wasserdichter Körper (RECHERCHE_DRAHTGITTER Prio 3, 8-16 h) ist nicht begonnen. Alle Körperversuche über SAM-Objekte (Hüllen, Schnitzen, Schalen, Relief, pymeshfix) sind verworfen oder nur Schalen; das einzige wasserdichte Ergebnis (Relief-Testkachel) ist verrauscht, Rückplatte und Tiefen sind Annahmen. Zwischen Gitter und Generator-Bauteil (Beleg, Prüfstand) gibt es keine Verbindung.

Zusätzlich, kleiner: der Editor hat noch keine gespeicherte Nutzerkorrektur (Datei fehlt, WebGL schwarz); die Verwendung der 1773 LIMAP-Linien (BS61) und der 930 `kanten_3d`-Linien ist nie geprüft worden; der vis-Index-Bug aus S10 Teil C (Bild-ID- statt Namensreihenfolge, betraf `kanten_3d`) ist für `kanten_3d_vote`/`kanten_tiefe_sweep` nicht als geprüft dokumentiert.

---

## 4. Widersprüche und Lücken zwischen den Dokumenten

**Zahlen, die nicht zusammenpassen**
- Foto-Stützung: LOGBUCH nennt "Foto-Stützung 0,72 (strengere Karten-Schwelle, nicht mit 0,91 von früher vergleichbar)"; die früheren Werte waren 0,964 bzw. 0,957, ein Wert 0,91 kommt sonst nirgends vor. ERKLAERUNG-Tabelle gibt für "SAM allein" 0,70 / 0,43, LOGBUCH für denselben Lauf 0,694 / 0,428 (gerundet, konsistent) aber in anderer Reihenfolge 0,630 -> 0,694 bei fallendem Recall; ERKLAERUNG nennt den Recall-Abfall nicht.
- "Abdeckung" ist zweierlei: in `kanten_schleife` Recall der Kantenpunkte mit 3 cm Toleranz, in `gitter_naehe` Anteil Referenzpunkte mit 10 cm. Beides heißt im Logbuch Abdeckung; 0,42 (Schleife) und 0,87 (Wolke, 10 cm) stehen nebeneinander.
- METHODIK sagt, `segmente_tsweep.json` (513 Seg., tol 0,05) zeige "Bögen, Fenster UND das Dach"; tatsächlich enthält diese Datei nur 3 Segmente über 15 m. Das Dach steckt in `segmente_hoch_ts.json` (45 Seg., tol 0,12, davon 28 über 15 m, 22 über 25 m). Der Befund "Dach gefunden" beruht also auf 28 Segmenten mit 12-cm-Toleranz plus Voxel-Konsens-Bild.
- Schleife auf aufbau2: 1318 -> 1754 Segmente, dabei sinken die Segmente über 15 m von 127 auf 100 und über 25 m von 70 auf 52 (selbst gezählt). Die Schleife entfernt Dachsegmente, obwohl sie Dachkanten per Z-Puffer nicht beurteilen kann; nicht dokumentiert.
- ERKLAERUNG "Stand der Zahlen" ist auf dem Stand vor Aufbau 2 (364/392/787/880 Segmente, "Nicht gefunden: Dachfirst, Staffelgiebel, Türmchenhelme") und widerspricht damit dem späteren Logbuch (Overlay: First/Giebel/Traufe sitzen). Die Tabelle wurde nicht nachgezogen.

**Bewertung derselben Sache widerspricht sich**
- DexiNed: LOGBUCH (vormittags) positiv ("Geländersäulen, Konsolen, Fensterteilungen jetzt erfasst, vorher fehlten sie"), METHODIK und RECHERCHE_VERFAHREN listen es ohne Zahl als "schon versucht / verworfen, nicht wiederholen". Ein Grund für die Abwertung steht nirgends; im 3D-Weg wurde es nie als Quelle getestet.
- LIMAP: BS61 (7.11., 94 Fotos, Tiefenkarten) = "Linien echt" (Deckung 63 % vs Kontrolle 36 %, Overlay Bogen/Fenster/Giebel); ERKLAERUNG verallgemeinert zu "LIMAP mit Wolkentiefe (Linien ohne Kanten) hat nicht funktioniert", gestützt nur auf den 16-Foto-Prototyp vom 9.11. (91 Linien). RECHERCHE_DRAHTGITTER setzt den LIMAP-Neulauf auf Prio 1 (4-8 h), RECHERCHE_VERFAHREN vom selben Tag nur als "unabhängiger Gegentest" hinter eigenem Code (1 -> 7 -> 6). Zwei Recherchen desselben Tages ohne Abgleich der Reihenfolge.
- Metrik-Vertrauen: LOGBUCH Runde 3 erst "Kontrastfilter hebt Treffer ohne Dachverlust" (vs B), dann Korrektur "VERWORFEN" (vs Wolke). Die Lehre ("Filter nie nur an der Menge prüfen, nach der er eingestellt wurde") ist richtig, wird aber vom neuesten o1/o2-Lauf (Parameter für das obere Band an B eingestellt, keine Wolken-Gegenprobe) schon wieder nicht angewendet.

**Als "nächster Schritt" notiert, nie gemacht (Stand der Dokumente)**
- Nutzerkanten `kanten_wahrheit.jsonl` als Wahrheit (8.11. gebaut, 9.11. "abwarten"): Datei existiert nicht.
- Kleine Handwahrheit 6-10 Ausschnitte + synthetischer Kantenprüfstand für die 3D-Kette (RECHERCHE_KANTEN_2 Prio 1): nicht begonnen.
- Dachrand von Hand als 3D-Linie, Pixelabweichung in allen Fotos (Karte 9.11.): nicht gemacht; Posenfehler in der Höhe weiter unbekannt.
- Parametrischer Bogenfit (BS13 7.11., RECHERCHE_KANTEN_2 Prio 2, RECHERCHE_DRAHTGITTER Prio 2): nicht gebaut.
- Manhattan-/Fluchtpunkt-Richtungszwang, IRLS-Ausgleich, Hough-Mode (RECHERCHE_VERFAHREN 1/7/6): nicht gebaut.
- METHODIK Schritte 2 und 5: Triangulation mit `--stabil` (stattdessen Tiefen-Sweep gebaut, Triangulation blieb auf Median-Kantenbildern) und Phasenkongruenz/DexiNed als Zusatzquellen im Stabilitätszähler.
- LIMAP-Triangulation ohne Wolke (venv-limap mit hloc/DeepLSD/GlueStick fertig): nie gestartet.
- Videoframes registrieren (Dachkanten), Sichtbarkeitskörper (OpenMVS) in einer Zone: offen seit "Stand abends".
- Feinregistrierung ECC/RoMa je Foto vor dem Stapeln, Fensterraster-Regularisierung (RECHERCHE_KANTEN_2 Prio 3/4): nicht gemacht; durch den Wechsel vom Ortho-Stapeln auf Sweep teils gegenstandslos, aber nicht als erledigt/überholt markiert.
- S10 Teil B (EMAP-Kantenfeld) und `kanten_3d.py` (930 Linien) sind weder weitergeführt noch in NICHTS_GEBRACHT/LOGBUCH 9.11. als Vorarbeit erwähnt; RECHERCHE_DRAHTGITTER kennt `kanten_3d.py` nicht.
- Drahtgitter -> Flächen -> Körper (RECHERCHE_DRAHTGITTER Prio 3) und Consensus-Merge statt Union-Find (RECHERCHE_FUSION, 4-6 Tage): nicht begonnen.

**Ablage- und Dokumentationslücken**
- Alle Segmentdateien und Referenzen liegen unter `/media/oem/scan/rc-park_daten/kaufhaus_alle/`; das Logbuch nennt nur Basisnamen. Im Repo liegt davon nichts (nur `viewer_kanten.html`, `sam_cache_*.json`).
- `tools/gitter_aufbauen.py` und `tools/gitter_naehe.py` sind unkommittiert geändert (`--qe` Endquantil-Fix mit Kommentar "0,02 kürzte jedes Segment um ~4 %, Eckenverlust"; `--minpts_o/--minlen_o`; gitter_naehe ein kNN-Aufruf statt drei). Der Bug und sein Einfluss auf alle Treffer-/Abdeckungszahlen vor 16:55 stehen in keinem Dokument.
- aufbau6, o1, o2 (16:55-17:06) sind nur in `/tmp`-Logs belegt; die Editor-Datei `modelle/kaufhaus_grob3/draht_kanten.json` existiert trotz Nennung in Logbuch und ERKLAERUNG nicht.
- `/tmp/schleife_karte.log` endet mit "Bögen: 0 davon im Foto gestützt" für den Lauf auf karte_b; das Ergebnis dieses Jobs (`segmente_karte_loop.json`) wird im Logbuch nicht ausgewertet.

---

## 5. Werkzeuge (Kurzindex, nur aus den Docstrings)

| Werkzeug | Zweck (1 Zeile) |
|---|---|
| `kanten_stabil.py` | Stabilitätskarte je Foto (261 Läufe, GPU), `stabil_alle.py` Stapel |
| `kanten_tiefe_sweep.py` | Kantenpixel entlang Strahl sweepen, Peak über Nachbarfotos = 3D-Kantenpunkt |
| `kanten_3d_vote.py`, `kanten_vote_quellen.py`, `kanten_fusion.py` | Abstimmung SAM/Canny/Farb-Sweep je Wolkenpunkt, Median-Fusion |
| `kanten_segmente.py`, `kanten_lib.py` | GPU-RANSAC Geradensegmente aus Kantenpunkten |
| `kanten_schleife.py` | Segmente gegen Fotos löschen/verschieben/verlängern/neu, Bögen |
| `kanten_triangulation.py` | 3D-Linien aus Linienpaaren ohne Wolke (Wolke nur Suchkasten) |
| `kanten_buendel.py` | Bündel zusammenfassen, Streuer außerhalb Box entfernen |
| `gitter_aufbauen.py` | Gitter aus Sweep-Konsens + Wolkenkanten, zwei Höhenbänder |
| `gitter_naehe.py` | Treffer/Abdeckung gegen Referenzpunkte je Höhenband (keine Wahrheit) |
| `gitter_overlay.py` | Gitter ohne Sichtbarkeitstest über kalibriertes Foto (Dach) |
| `gitter_statistik.py`, `gitter_streuer.py` | Filter (beide verworfen) |
| `editor_draht.py/.html`, `viewer_kanten_bauen.py`, `viewer_kanten_vorlage.html` | Editor Port 8767 und Canvas-Viewer |
| Ältere Generation: `kanten_3d.py`, `kanten_feld3d.py`, `kanten_feld3d_pruefen.py`, `kanten_pipelines.py`, `kanten_blatt.py` (S8/S10, 6.11.) | abgelöst, Ergebnisse unter `/media/oem/scan/rc-park_null/s10/` |
| Anderer Zweck (Modell gegen Foto): `kanten_abgleich.py`, `kanten_richtung.py`, `kanten_nulltest.py`, `kanten_render.py`, `kanten_zeigen.py`, `kanten_subpixel.py` | Kanten-Gate/Versatz für Generator-Modelle, nicht Drahtgitter |

Kein Werkzeug baut aus dem Gitter Flächen oder Körper.

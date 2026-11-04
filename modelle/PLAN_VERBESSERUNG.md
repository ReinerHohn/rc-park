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
| 2.3 | Lot-/Linienpruefung (FLD aus opencv_contrib oder Canny+Hough; DeepLSD MIT nur als Test) der Wolke gegen senkrechte Kanten | misst die Scherung unabhaengig vom Generator | WOLKENTEIL GEBAUT 3.11.: `tools/lotpruefung.py` (Selbsttest + Generator-Kontrolle). z 7-23: Wolken neigen nach aussen +20..+37 mm/m, Generator -13; Rest nach Entzerrung ~33 mm/m. Quelle der Generator-Verjuengung GEKLAERT 3.11.: Tiefe 9,8 (LoD2) -> 9,3 (z 26) -> 9,0 stammt aus Silhouetten-BREITEN (Register T), keine Tiefenmessung, keine Pruefzeile -> ANNAHME (Beobachtung in masstabelle). Abschnitte aus der Wolke GEBAUT (`--eigene-abschnitte`): Restneigung +17..+35 mm/m bleibt in allen belastbaren Abschnitten (nicht an der Generatorwahl). Offen: Bildteil (Foto-Lot, FLD/Hough) als unabhaengige Quelle, Schafttiefe aus Seitenansicht messen + Pruefzeile |
| 2.4 | Doppelschicht-Detektor als Pruefzeile (1 vs 2 Ebenen per BIC) | verhindert Rueckfall des Doppeldachs | WERKZEUG GEBAUT 3.11.: `tools/doppelschicht.py` (Selbsttest ok); Nord z 43-49 Mitte: unkorrigierte Drohnenwolke 7/7 Schichten doppelt (Abstand ~2 m), korrigierte 0/7. Offen: als Pruefzeile in Kette/Pruefstand, Ost/West, Strassenwolke zu duenn in der Mitte |
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
| 4.3 | Weiteres Drohnen-/Videomaterial fuer Sued/Ost/West und > 50 m (Boden-SfM auswerten) | Datenluecken| ERSTER FUND 3.11.: `F8y3lNgia5c` (Suedanfahrt, 62 s 4K) war nur defekt geladen, jetzt repariert, 150 Frames extrahiert; SfM nach der Bodenwolke (GPU), Masken Bahn/Personen, Seitenpruefung M8. Weitere Clips nicht Martinstor (Schwabentor/Muenster) |
| 4.4 | Mehr Nullstart-Laeufe mit disjunkten Fototeilmengen | echte Unabhaengigkeit fuer `masse_konsens.py` |

## Stufe 5 - spaeter / nur mit Lizenzklaerung
Render-and-Compare (PyTorch3D, BSD), monokulare Tiefe/Normalen (nur Depth-Anything-V2-Small Apache, als schwacher Prior), gsplat (Apache) nur fuer Textur. Vor Verkauf pruefen: nvdiffrast, Gewichte von MoGe/Metric3D/DSINE, 2DGS, OpenCV-LSD. Mapillary-Bilder (CC BY-NC-SA) und YouTube-Drohnenpunkte nicht in ein Produkt.

## Reihenfolge
1.1 -> 1.2 -> 1.3 (laufen) | parallel 2.1, 2.4 -> 2.2 -> 2.3 -> 2.5 -> 2.6 | dann je nach Ergebnis 3.1-3.2 | 4.x sobald Fotos/Footage da sind.
Ehrliche Grenze: Stufe 1-3 verbessern, was die Daten hergeben; Stufe 4 verschiebt die Grenze selbst.

## Manuell -> Pipeline (HARTE REGEL, Nutzer 3.11.: alles vollautomatisch, auch beim Vollnulllauf)
Stand der Handarbeit vom 3.11. Jede Zeile ist erst erledigt, wenn sie in `tools/nullstart.py`/Kette laeuft und per `regression.py` abgesichert ist.
| Nr | Was heute von Hand lief | Ziel in der Pipeline |
|---|---|---|
| M1 | Sandbox-Objekt von Hand gebaut (objekt.json-Kopie + audit/video_ausrichtung + messprotokoll-Link), um `video_dicht` fuer die Bodenclips zu starten | `video_dicht.py --aus <ausrichtung.json>` (wie `video_ausrichten.py --aus`), dann Warteschlange ohne Sandbox |
| M2 | `abdeckung_quellen.py` nur von Hand aufgerufen, nicht in der Kette | als Kettenschritt + Pruefzeile (Luecke je Seite), Schnappschuss + Register |
| M3 | Versatztest der Fehlteile (Kamera +-60 px) nur als Scratchpad-Skript | Option in `fehlteile_finden.py` (`--versatz-test`), Ergebnis in den Treffer-Bericht |
| M4 | Sichtblatt nutzt Silhouettenkameras; Optimierer an der Grenze (sx=-120) unbemerkt | Grenzpruefung im Optimierer: Parameter an der Schranke -> Kamera 'unsicher', im Sichtblatt markiert/ausgeschlossen |
| M5 | Kameras fuer Fotos mit Baum/Symmetrie (022, 043) nur mit Handpicks loesbar | automatische Auswahl der Fotos nach Kameragueterating (RMS %-Bildhoehe), unloesbare Fotos nicht in Messungen/Textur verwenden |
| M6 | Fotofarbe auf das Modell projizieren (Strang C, `tools/textur_projektion.py`) | in die Kette, mit Abdeckung je Seite, Quelle je Vertex (Lizenz) |
| M7 | `--kamera-gruppen` (sfm_netz): EXIF der Fotodateien leer -> keine Gruppen | Gruppen aus Manifest/Dateiname als Fallback ODER Fotos mit EXIF beim Import erzwingen; erst nach Beleg Standard |
| M8 | Seitenzuordnung der Videos haengt an der Nordausrichtung (Symmetrie) | unabhaengige Pruefung ueber asymmetrisches Merkmal je Video (Gedenktafel/Adlerrelief/McDonald's) |
| M9 | Bilder holen/bewerten laeuft nur von Hand: `bilder_holen.py` + `bilder_einsortieren.py` stehen NICHT in `nullstart.py`/`treppe.py`; Mehrwert = Bildaehnlichkeit/Schaerfe/Blickgruppe, NICHT gemessener Modellgewinn | Schleife schliessen: je Stufe `abdeckung_quellen.py` + `textur_projektion.py` (Farbabdeckung je Seite) als Luecken-Bericht -> `bilder_holen` nur fuer Seiten/Hoehenbaender mit Luecke -> Netz/Auswertung -> Gewinn gegen Rauschen messen -> weiter oder STOPP (Nutzerwunsch: Bilder nur holen, wenn sie etwas verbessern, in mehreren Iterationen) |
| M10 | Geholte Fotos haben keine EXIF-Daten (Commons-Downsizes) -> keine Kameragruppen, keine Brennweiten-Priors | beim Holen Original/EXIF mitholen, sonst Brennweite aus Manifest/f_gruppe; Foto ohne verwertbare Kamera als Texturquelle abwerten |
| M11 | Lizenzklasse je Bild: Register `tools/lizenz_register.py` (neu, 3.11.) erzeugt `LIZENZ_BILDER.json/.md` automatisch (6 Klassen, Produkt ja/bedingt/nein, Auflage) - noch nicht in der Kette | in `nullstart.py`/Regression aufnehmen; `--produkt-pruefen` als Pruefzeile; Klasse im Foto-Manifest (`lizenz_klasse`) und je Dreieck in der Textur; vor Veroeffentlichung Original pruefen (ANNAHME, keine Rechtsberatung); ShareAlike-Folgen und 2 'unklar' (nur 'Attribution') klaeren |

### Fahrplan Nullstart (Stand 3.11. abend) - Details in `modelle/UEBERGABE_2026-11-03_abend.md`
Status M1-M13: M1 Option `video_dicht.py --aus` gebaut 3.11. (ungetestet, nach Bodenwolke an kleinem Clip pruefen; Warteschlange/Sandbox-Ersatz noch offen) | M2 Werkzeug da, nicht in Kette | M3-M5 im Bau (Strang F) | M6 gebaut (textur_projektion), nicht in Kette | M7 Option da, Fallback im Bau | M8 offen | M9 Entwurf (Strang D) | M10 im Bau | M11 gebaut, nicht in Kette | M12/M13 offen.
Naechste Schritte: Straenge abnehmen -> M1 -> Einbau in `nullstart.py` -> Regression-Konfiguration + Schnappschuss (Register) -> Nullstart-Wiederholbarkeit -> zweites Objekt (Generik-Test).
| M12 | GPU zu 100 % 'ausgelastet', aber nur 48 W/140 W und 0,4 von 8 GB Speicher (PatchMatch, 3.11. 10:48; keine Drosselung): `video_dicht`/`sfm_dicht` laufen mit EINEM PatchMatch-Prozess ~7 s je Ansicht, 2 Durchgaenge | PatchMatch in N Prozessen auf einer GPU (Bilder per patch-match.cfg aufteilen, Durchgang 1 komplett vor Durchgang 2), Ergebnis per Hash gleich pruefen (verlustfrei), RAM beachten (15,7 GB gesamt); erst NACH der laufenden Bodenwolke testen; Parameter `--prozesse N` in video_dicht/sfm_dicht + Eintrag in `nullstart.py` |
| M13 | Seite eines geholten Bildes (`bilder_holen.py`, `aehnlich_basis.seite`) = Seite des aehnlichsten VORHANDENEN Fotos, nicht die echte Blickrichtung (Review 3.11.). Auf Luecken-Seiten (Ost 1,1 %, West 10 %) gibt es kaum Vergleichsfotos -> `--nur-seiten` kann Bilder der falschen Seite liefern; `schliesst_luecke` im Bericht von `bilder_schleife.py` ist damit nur ein Vorschlag | Seite erst NACH der Kalibrierung aus der Kamerarichtung (Hauptachse -> Seite wie `abdeckung_quellen.seite_von`) bestimmen und `schliesst_luecke`/Gewinn daran messen; bis dahin im Bericht als `seite_art: "Vorschlag (Nachbarfoto)"` kennzeichnen; Pruefzeile: Anteil der Bilder, deren kalibrierte Seite vom Vorschlag abweicht. ANNAHME: noch nicht gemessen, wie oft der Vorschlag falsch liegt |

## Aufwand/Nutzen und Sweetspot "schnell durch die Stadt" (Nutzerwunsch 3.11., Bodenwolke)
Ziel: viele Modelle in kurzer Zeit; deshalb jeden teuren Schritt mitschreiben und NACH dem Ergebnis bewerten, ob er sich lohnt (statt "er hat etwas geliefert").
- Werkzeug `tools/aufwand_log.py` (messen / nutzen / bericht): Log `modelle/aufwand/<name>.jsonl`; laeuft fuer die Bodenwolke seit 11:14 (`boden-dicht-2026-11-03`, PID 3593479, Probe je 60 s: GPU-Leistung/Auslastung/Speicher, Last, RAM, Fortschritt). CPU-Energie nur geschaetzt (RAPL nicht lesbar).
- HYPOTHESE vorab (11:15): Nutzen nur an der Nordseite (Boden-Kameras N340/S1/O0/W1); kein Gewinn fuer die Luecken Sued/Ost/West.
- BASISLINIE 11:25 (`tools/wolken_vergleich.py`, Nordwand): schwache Zone ist z 5-20 m (Strasse 43-165 Pkt/m2, Drohne 73-78 bei Flaechenschaerfe 0,13-0,21); ab 20 m Drohne 1000-3000 Pkt/m2. Praezisierte Hypothese: Bodenwolke hilft nur z 5-20 m. Nach Jobende: `wolken_vergleich.py ... --wolke boden=video_sfm/boden/dicht_modell.npy` mit denselben Parametern (Boden ist an Nordnetz ausgerichtet -> nicht unabhaengig von der Strasse).
- Bewertung nach Jobende (Reihenfolge, alles mit GLEICHEM Schaetzer VOR/NACH, Wolke NICHT in die Referenzwolke mergen): (1) `aufwand_log.py bericht`; (2) Punktdichte Nordwand je 10-m-Band Boden vs. Strasse vs. Drohne (`abdeckung_quellen.py`, `lotpruefung.py`, `doppelschicht.py` auf die Bodenwolke); (3) Gewinn an bestandenen UNABHAENGIGEN Pruefungen (nullstart/treppe-Messung mit und ohne Bodenwolke, Rauschband 5) und je Seite abgedeckte Flaeche; (4) Eintrag `aufwand_log.py nutzen` + Versuchslog; (5) Verdikt: Nutzen pro Wanduhrstunde gegen die billigeren Stufen (sweetspot.json 1000 px = 385 s, treppe grob/mittel/fein).
- Offen fuer den Sweetspot: Zeit je Stufe fuer ein NEUES Objekt (Stadtlauf) aus `treppe.py`/`nullstart.py` mitloggen (heute nur Sekunden je Stufe in sweetspot.json); `aufwand_log.py` in `nullstart.py`/`jobplan.py` einhaengen (Handarbeit-Regel).
- ZEITBASIS 11:30 (`tools/zeit_je_modell.py`, 33 Nullstart-Berichte): ein Strassenfoto-Modell (grob) braucht im Median 11,6 min (8,3-13,2), voll 6,3 min; die dichte Nordwolke ist 50-90 % davon, Sued-Netz 20 %. Die Bodenwolke (>1 h GPU) kostet damit etwa das 5- bis 10-fache eines ganzen Strassenfoto-Modells; Drohne/Video sind nicht in diesen Zahlen. Grenzen: Zeiten teils neben anderen Jobs gemessen, ohne Nutzen. `treppe.py` schreibt jetzt `sekunden_je_stufe`/`sekunden_gesamt` in `treppe_verlauf.json` (ungetestet, nur Zeitfelder ergaenzt).
- SUED-CLIP VORBEREITET 11:57: `tools/video_masken.py` (SegFormer-B4 ADE20K, CPU, ~1,2 s/Frame) maskiert Personen/Fahrzeuge/Strassenbahn; 150 Frames von F8y3lNgia5c in 182 s -> `/media/oem/scan/rc-park_daten/martinstor/video_masken/F8y3lNgia5c/` (Mittel 7,1 % maskiert, Max 43,7 % bei der Bahn-Nahaufnahme). Sichtprobe: Bahn und Personen sauber maskiert; GRENZE: Bahn-Seitenwand im Nahbereich (Frame 060, 0,7 %) wird NICHT erkannt (als Gebaeude gelesen). `video_sfm.py --masken-vorlage DIR` (neu, ungetestet) verknuepft die Masken mit der Wasserzeichenmaske. Lizenz SegFormer-Gewichte vor Verkauf pruefen (LIZENZ_WERKZEUGE). Frames, die nicht zum Turm zeigen (z. B. Boden/Laden), fehlen noch als Filter (Schritt 'Bodenvideo-Frames filtern').
- SCHRANKE VOR DICHTER RECHNUNG 12:03: `tools/dicht_vorpruefung.py` (abdeckung.json: Kameras je Quelle/Seite + Hoehenlage; ANNAHMEN 10/30/15 m). Martinstor: Boden lohnt nur Nord ("neue Hoehenlage"), Drohne Ost/West lohnt, Fotos Sued lohnt (= Sued-Netz-Problem). Noch NICHT in `nullstart.py`/`treppe.py` (Schritt offen); wird gegen das Ergebnis der Bodenwolke bewertet. Bewertung aller Schritte der Sitzung: `modelle/AUFWAND_BEWERTUNG_2026-11-03.md`.

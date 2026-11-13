# Logbuch Rippen unter dem Erker (13.11.2026) - zum spaeteren Analysieren "wie schneller zum Ziel"

Ziel (Nutzer, /goal): Bogenrippen unter beiden Erkern so genau im Modell, dass man sie in H0 extrem gut erkennt.
Skripte dieser Runde: `modelle/rippen_runde_2026-11-13/` (faecher_generator.py, bogen_dp.py, lauf_b.py). Abnahme-Logs liegen nur im Scratchpad (nicht im Repo).

## Chronologie (Zeitaufwand grob; Ergebnis; Lehre)
| # | Schritt | Ergebnis | Lehre |
|---|---|---|---|
| 1 | Schlussstein-Rosetten (4 Zylinder) + Wasserspeier 0,60/0,30 | Abnahme rot: Ueberhang 1,44 % > 1 % in teil_06 | Wasserspeier-Verlaengerung ist druckkritisch |
| 2 | Wasserspeier 0,48/0,26 | gruen (Commit c35e4627), Viewer v61 | mittlerer Wert durch Probieren, nicht aus Foto |
| 3 | Rundum-Kantenbild beider Erker ansehen | Rippen zerfasert; Kantenbild (Normalenknick >25 Grad) zeigt flache Grate nur unvollstaendig | Kantenbild allein ist fuer flache Rippen ein schwacher Massstab -> schattierter Render noetig |
| 4 | Foto-Paare K-6261/K-6162 gegen Kantenbild | Foto: dichter Faecher, Modell lueckenhaft | |
| 5 | Schattierter Render (render8.py) | erst leer: falscher STL-Pfad (main_m.stl statt obj["stl"]) | Pfad aus objekt.json lesen, nie raten (~10 min Verlust) |
| 6 | Pfadplot der 24 rippen_pfade | nur ~5 lange Boegen, Rest Fragmente, n streut 12,2-13,9 | Ursache der schwachen Rippen = fragmentierte Messpfade, nicht Breite/Vorsprung |
| 7 | Strahl x Modellflaeche fuer Wegpunkte | Strahlen verfehlen Kegel (n 9,7 statt 12-13) | Modellflaeche als Tiefenreferenz unbrauchbar; Zwei-Foto-Triangulation noetig |
| 8 | Zwei-Foto-Triangulation (Handpixel, alle Zuordnungen probiert) | Fuss u15,81 n12,48 z6,47 (Strahlabstand 8 cm); Knaeufe vorn u16,20/14,87 n13,8 z8,12 (3 cm) = Modell auf ~0,1 m | Geruest stimmt; Fehler ist Zahl/Kontinuitaet der Rippen. Zuordnung per Symmetrie um u_mitte entschieden (mehrere Paare hatten kleinen Strahlabstand = epipolare Mehrdeutigkeit) |
| 9 | kante_3d.py Bogen b (Via nur Foto A) | Pfad in Foto B folgte Randkante, Startpunkt 0,63 m daneben | kante_3d braucht Via-Punkte in BEIDEN Fotos |
| 10 | eigener Gold-DP (bogen_dp.py): 6 Handbogen aus K-6162, Tiefe per Gold-Signal in K-6261 | landet am Erkerrand, Gold-Median 0,28 bei allen = keine Trennschaerfe | gleiche Sackgasse wie 12.11. (0 von 21 Ketten): Gold-Signal parallel verlaufender Rippen ist mehrdeutig |
| 11 | Nutzer waehlt "Faecher aus Messpunkten", dann "arbeite autonom" | faecher_generator.py: je Flaeche 6 Rippen (0/+45/-45 Grad um Achteckmitte u_mitte, n 12,27) + rechter Randbogen; n(z) der Kegelflaeche aus bisherigen Pfaden | Rippenzahl/Bogenform bleiben ANNAHME |
| 12 | Abnahme mit Faecher an beiden Erkern | 1. Lauf: Reichweite z 8,0 = 1,50 > 1,48 (oben 2 cm zu weit) -> Kurve oben -4 cm: Reichweite ok (1,45), dann aber 2 Laubengewoelbe-Fehler (Unterseite 5,75 statt 5,835) | Sollwert nicht gelockert |
| 13 | Variantenschleife (Kurve -0,02/-0,03/-0,06; nur Erker 1; nur Erker 0; weniger Rippen; Breite 0,068/0,072) | NUR EINER der beiden Erker gebaut = gruen; BEIDE = Laube rot (jede Variante) | Muster: gruen bei Reparaturmeldung "2-5 Splitter verworfen", rot bei "1 Splitter verworfen". Druck-Reparatur reagiert chaotisch auf die Gesamtgeometrie; die Laubenfehler haengen nicht an der Laubengeometrie |

## Offene Ursachenhypothese (nicht belegt)
Der Messwert `rippe_gurt_u954_z`/Diagonalrippe wird nach der Druckreparatur gemessen. Mit Faecher an beiden Erkern wird ein Teil nicht als Splitter verworfen und liegt bei z 5,75-5,80 unter der Laube. Zu pruefen: welcher Teil das ist (Mesh-Teile unter z 5,9 bei u 3-10, n 8-9 auflisten) bevor die naechste Variante gebaut wird.

## Zeitfresser / was schneller geht
- Jede Abnahme dauert mehrere Minuten; die Variantenschleife lief ~8 Builds blind. Besser: erst Teilnetz-Diagnose (siehe Hypothese), dann gezielt aendern.
- Handpixel aus Bildern ablesen kostet viele Rasterbilder; ein Klick-Werkzeug (Pixel in beiden Fotos markieren, Epipolarlinie einblenden) waere der Hebel.
- Neue Fotos nach `modelle/AUFNAHMEPLAN_ERKER_RIPPEN.md` loesen das Tiefenproblem eher als jede weitere Auswertung.
- Fehlerquellen dieser Runde: falscher STL-Pfad, Welt- vs. Fassadenkoordinaten (u = x*ny - y*nx, n = x*nx + y*ny, achse_n 0.3338 0.9426), `head` auf grep-Ausgabe schnitt FEHLER-Zeilen ab (immer `grep "^  FEHLER"`), ein Tool-Ergebnis ging durch Timeout/Verbindung verloren.
- Stand des Modells: objekt.json = HEAD (Faecher NICHT eingebaut), Abnahme gruen, Rippen weiter fragmentiert.

## Nachtrag: Diagnose Laubenfehler (14.)
- Bau `beide` (Faecher an beiden Erkern) und `nur1` (nur Erker 1) je gebaut, STL als /tmp-Scratch gesichert, Vergleich der Teile in der Laube (u 3-10, n 8-9).

## Ergebnis Diagnose Laubenfehler (14.) - GELOEST, war ein Messartefakt
- Laubengeometrie in beiden Bauten identisch (534 Vertices in der Laubenbox, gleiche Bounds, Strahl trifft beide Male die Gewoelbeunterseite bei 5,924 m).
- Ursache: `Messer.z_am_punkt` (tools/pruefstand.py) schneidet mit trimesh bei z = z0 + k*0,01. Bei z = 5,797 faellt die Ebene auf eine waagerechte Modellflaeche; `section` liefert dann 3 entartete Polygone (~490 m2) ohne Loecher, die jeden Punkt enthalten -> Messwert 5,80 statt 5,92. Ob eine Ebene so faellt, haengt von der Gesamtgeometrie ab -> "gruen bei 2-5 verworfenen Splittern, rot bei 1" war ein Scheinmuster.
- Fix: Schnittebene um 1,3 mm versetzt (Sollwerte unveraendert). Regression `regression.py --pruefen`: identisch - nichts verloren.
- Zeitaufwand dieser Fehlersuche: ~12 blinde Builds (je 3-5 min) vor der Diagnose; die Diagnose selbst (Strahltest, Messer direkt auf zwei STL) brauchte 5 Schritte. LEHRE: Bei "Wert aendert sich, obwohl Geometrie gleich" sofort den Messer isoliert auf beiden STL laufen lassen, nicht weiter Varianten bauen.

## Ergebnis Faecher (15.) - eingebaut, Abnahme gruen, Qualitaet NICHT ausreichend
- Faecher an beiden Erkern (je 19 Rippen, ANNAHME laut quelle_faecher in objekt.json): Abnahme "alle Pruefungen bestanden", Regression identisch.
- Schattierter Vergleich (modelle/rippen_runde_2026-11-13/sh_fan_6261.jpg, sh_fan_6162.jpg): Rippen jetzt dicht (~7 je Flaeche), aber dick, kantig und ohne die Kreuzungsgeometrie des Fotos; Fuss laeuft in unruhige Spitzen aus; Kegelsilhouette weicht ab (Foto: schlanker Trichter, Modell: Glocke). Foto: duenne goldgerahmte Rippen. Fehler: (a) Rippenbreite 0,07 m zu dick, Foto etwa 0,03-0,04 m je Einzellinie (Rippe = 3 Goldlinien), (b) Fussbuendel 0,30 m breit angenommen, (c) Bogenformen angenommen, nicht gemessen, (d) Kegel-Silhouette.
- Naechste Schritte: Rippenbreite/Vorsprung gegen Foto messen (foto_mass.py), Fussbreite triangulieren, Silhouette des Kegels (profil in unterbau) gegen K-6162-Kontur pruefen; Druckregel: ueber 0,0348 m (0,4 mm H0) bleiben.

## 16. Rippenbreite am Foto (Zwischenmessung)
- Massstab am Erker: K-6162 106 px/m (Tiefe 28,5 m), K-6261 99 px/m (30,7 m). Bei diesen Entfernungen ist eine Rippe von 0,07 m nur ~7 px breit; Einzelgoldlinien sind nicht aufgeloest.
- Querprofil Goldanteil (K-6162, 4 Stellen): nur eine saubere Stelle (600,1880): 7 px = 0,066 m; die uebrigen drei Profile verrauscht (Gold-Maximum 13-19, Breite 24-35 px = Rippe + Nachbarrippe + Schatten) -> keine belastbare Aussage. 
- Folgerung (vorlaeufig, EINE Messung): Rippenbreite 0,07 m ist plausibel, "klobig" im Render kommt eher aus Vorsprung 0,05 m, flacher Beleuchtung und den unruhigen Fuss-/Kreuzungsstellen. Fuer eine sichere Breite fehlt ein Nahfoto (Aufnahmeplan Punkt 3, 1-2 m Abstand -> ~500 px/m).
- LEHRE: Aufloesung vor Messung pruefen (px/m aus Kamera) - bei 100 px/m sind Rippendetails unter 5 cm nicht messbar; spart Messversuche.

## 17. Zwei-Foto-Konsens-Fit des Faechers (faecher_fit.py)
- Idee: 3D-Modell als Messer; Rippenmittellinien in K-6162 UND K-6261 projiziert, Score = mittleres lokal normiertes Gold-Signal entlang der Linien; 5 Parameter (Fussbreite, 3 Endlagen, Aussenexponent) per differential_evolution.
- Ergebnis: Score 6162 0,371 -> 0,381, 6261 0,543 -> 0,546 (praktisch flach). Parameter laufen an die Grenzen (Fusshalbbreite 0,448 bei Grenze 0,45; a1_aussen 0,50 an Grenze). Nullkontrolle (Gold-Bild um 90 px verschoben): 0,09 / 0,37 -> Score unterscheidet die Lage in K-6162 klar, in K-6261 kaum (viel Gold ueberall).
- Folgerung: Der Annahme-Faecher liegt schon grob auf dem Gold; der Score trennt Detailformen nicht. Fit NICHT uebernommen (Grenzwerte, Gewinn 0,01 = Rauschen, kein Foto-Beleg). Zweifel am Verfahren: Gold-Signal bei 100 px/m ohne Aufloesung der Einzelrippen.
- LEHRE: Ohne hoehere Aufloesung (Nahfotos) bringt weiteres Optimieren am selben Signal nichts; Zeit: ~6 min. Naechster Hebel bleibt Aufnahmeplan Punkt 1+3.

## 18. FUND: kalibrierte Nahfotos der Rippen existieren (n11_04/05/06)
- Beim Klaeren der Giebelwand-Frage (n11_05/06) zeigte sich: Beide Fotos sind Nahaufnahmen von UNTEN auf den Rippenfaecher des WESTLICHEN Erkers (Erker 0, u_mitte -8,47) aus der Gasse, kalibriert (messprotokoll/K-n11_05/06.json). Abstand 4,9 m = 625-718 px/m (Rippe 0,07 m ~ 45 px statt 7 px). n11_04: Erker 1 (Ost) aus 8,3 m, 342 px/m.
- Bild: modelle/rippen_runde_2026-11-13/nahfotos_n11_05_06.jpg. Es zeigt keinen einfachen Faecher, sondern ein RAUTENNETZ: sich kreuzende Diagonalrippen mit Knaeufen am oberen Rand und Rosetten in den Dreiecksfeldern je Facette. Mein Annahme-Faecher (Kap. 15) hat die falsche Topologie und keine Rosetten.
- Grenze: n11_05 und n11_06 stehen praktisch am selben Ort (Basis 0,06 m, 0,5 Grad) -> keine Triangulation zwischen beiden. Zweiter Blick muss aus einer anderen Kamera kommen (z. B. K-6259/6162 mit 100-200 px/m) oder Tiefe aus der bekannten Facettenflaeche (Knauf/Fuss triangulierte Punkte, +-0,1 m).
- LEHRE (Zeitfresser): Ich habe einen ganzen Nachmittag lang "keine Nahfotos" behauptet und Aufnahmeauftraege geschrieben, ohne vorher die vorhandenen Kameras nach Aufloesung am Ziel (px/m, Abstand) zu sortieren. Regel kuenftig: VOR jeder Aufnahmebitte `kameras_am_ziel` (alle Kameras, px/m, im Bild) laufen lassen. Werkzeug fehlt noch -> bauen.
- Naechster Schritt: Rautennetz in n11_06 (und n11_05) von Hand/halbautomatisch nachzeichnen (2D, hohe Aufloesung), per Strahl x Facettenflaeche (Knauf/Fuss-Ebene) in 3D, Gegenprobe in K-6162/6259; dann Faecher durch Netz ersetzen; Abnahme; Schattenvergleich.

## 19. tools/kameras_am_ziel.py gebaut; Ergebnis
- Erker 0 (West, u -8,47 n 13,3 z 7,3): K-n11_06 625 px/m (Az 96), K-6130 597 px/m (Az 167, 5,9 m), K-i08 515, K-e04 406 (Az -124), K-6124 404. Schnittwinkel n11_06/6130 = 71 Grad -> Triangulation moeglich.
- Erker 1 (Ost, u 15,52): K-6171 684 px/m (Az -177), K-h11_112038 596 (Az -68), K-d11 589 (Az -143), n11_04 342. Schnittwinkel 6171/h11_112038 ~109 Grad.
- Die "keine Nahfotos"-Aussage (Kap. 14-17) war FALSCH; 100 px/m galt nur fuer K-6261/K-6162, die ich zufaellig gewaehlt hatte. Das Tool gehoert in den Leitfaden Schritt 2/5 (vor Fotoplan).

## 20. Auswertung der Nahfotos K-n11_06 (625 px/m, Az 96) und K-6130 (597 px/m, Az 167), Erker 0 (West)
Bilder mit Raster: modelle/rippen_runde_2026-11-13/rast_n11_06.jpg, rast_6130.jpg (Beschriftung = Vollbildkoordinate).
- RIPPENBREITE: Rippenband ~90-110 px = 0,15-0,18 m (schraeg gemessen ~0,15 m, Profil gold-schwarz-gold mit dunklen Flanken, Goldlinien selbst ~0,01 m). Das Modell hat 0,07 m (aus 7-px-Messung bei 100 px/m, Kap. 16). VORLAEUFIG: wirkliche Rippenbreite etwa doppelt so gross; Kap. 16 ist damit ueberholt. Noch nicht in objekt.json (rippen_pfade.b 0,07 gilt), Abnahme-/Druckfolgen offen.
- TOPOLOGIE: Rautennetz mit breiten Rippen; ca. 12 Rippen im Bild von K-6130, Rosetten in den Dreiecksfeldern (K-6130 (1650,300), n11_06 (225,1235) und (780,1090)). Faecher falsch.
- Triangulation Merkmalspunkte (7 x 8 Handpunkte, alle Paare; nur Strahlabstand < 0,15 m und in Huelle): mehrdeutig (X1 passt zu 3 Gegenpunkten). Plausibelste Knoten: X1x1 (-8,70 / 12,89 / 7,02, Gap 3 cm, grosse Kreuzung ueber dem Fuss, auf der Achse u -8,47), X5x6 (-9,29 / 13,36 / 7,33, Gap 0,8 cm). Nicht verifiziert.
- LEHRE: Handpunkt-Zuordnung bleibt mehrdeutig, auch bei 70 Grad Schnittwinkel. Besser: Rosetten als eindeutige Ankerpunkte nehmen, danach Zuordnung der Kreuzungen per Nachbarschaft zu den Ankern; oder Epipolarlinien einblenden und mit Auge entscheiden (Werkzeug fehlt).

## 21. Werkzeuge knoten_pruefen.py und knoten_abstimmung.py; Ergebnis Erker 0
- tools/knoten_pruefen.py: 3D-Kandidat in mehrere Kameras projizieren, Ausschnitte nebeneinander (Gegenprobe der Handzuordnung). Ergebnis (knoten_gegenprobe_1.jpg): X1x1 (-8,70/12,89/7,02) liegt in 3 von 4 Kameras auf/neben einer Rippenkreuzung (Abweichung ~3-6 cm); X5x6 und X3x5 nicht ueberzeugend -> verworfen.
- tools/knoten_abstimmung.py: Gitterpunkte auf der Kegelflaeche (3 Facetten, +-0,08 m in n), Score = Harris-Ecke im Goldbild in >= k von 5 Kameras (n11_06, 6130, e04, 6124, i08; 389-617 px/m). Lauf Erker 0: 40 Knoten (knoten_erker0.json). Bester: (-8,16/12,91/7,06) 4 Kameras Score 1,0; bestaetigt zweiten Punkt (-8,73/12,86/6,98) ~ X1x1 (Score 0,74).
- Grenzen/Befund: Knoten nahe der Achse sind zwischen Facetten mehrdeutig (u-Abweichung bis 0,5 m); bei Score < 0,6 nur 1-2 Kameras = unsicher. Das Verfahren liefert KNOTEN, keine Rippenbahnen; die Bahnen muessen aus Knoten + Bogenform (aus n11_06/6130 2D) zusammengesetzt werden.
- Aufwand bisher fuer Rippen seit Ziel-Setzung: Strahl x Flaeche (fehl), kante_3d (fehl), Gold-DP (fehl), Faecher (Annahme), Fit (flach), Nahfoto-Fund, Handtriangulation (mehrdeutig), Gegenprobe (1 Knoten ok), Eckenabstimmung (40 Knoten, 2 sicher). LEHRE: Zuerst Kameras am Ziel sortieren (Kap. 19), dann mehrdeutige Merkmale per Abstimmung ueber >= 4 Kameras statt Handpaar.

## 22. tools/rippen_abstimmung.py (Gold-Band-Abstimmung ueber 5 Nahkameras, Erker 0)
- Gold-Mass zuerst (R+G)/2-B: rote Wand zaehlt als Gold -> Score ueberall ~1, kein Kontrast (FEHLER, ~10 min). Korrektur G-B (Wand ~0).
- Flaechenhypothese dr=0: Rippendiagonalen schwach sichtbar (rippenabstimmung_erker0_flach.png). Mit freiem Tiefenband +-0,12 m (9 Stufen, Max): Facetten -45 und +45 zeigen deutliche Diagonalen/V-Formen (rippenabstimmung_erker0_band.png), aber verrauscht; Facette 0 im Lauf nicht aktualisiert (Datei vom ersten Lauf; Ursache offen).
- Befund: Die Mehrfoto-Abstimmung traegt Rippenbahnen, ist aber noch kein Messergebnis. Naechster Schritt: Ridge-Extraktion (Skelett des Score-Bilds je Facette, Pixel = du/z -> 3D ueber n(z)+dr_best), danach Bahnen glaetten und in rippen_pfade schreiben; Rippenbreite 0,15 m (Kap. 20).
- Zeit: ~25 min fuer drei Laeufe; Rechenzeit je Lauf ~2-4 min (CPU). Besser: GPU und Tiefenband gleich im ersten Lauf.

## 23. DURCHBRUCH (Teil): tools/rippen_skelett_tiefe.py + rippen_ketten3d.py, Erker 0
- Methode: Gold (G-B, lokal normiert) -> Skelett in K-6130 (558 px/m) -> je Skelettpunkt Strahl, Tiefe 1,5-45 m in 1-cm-Schritten innerhalb der Erkerbox (u -10,2..-6,7, n 11,8..14,0, z 6,3..8,3), Score = Gold-Konsens in K-n11_06, K-e04, K-6124, K-i08 (>= 3 von 4 Kameras im Bild). Perzentile Score 10/50/90/99 = 0,41/0,57/0,76/0,89; Schwelle 0,6 -> 3444 von 9898 Punkten.
- GEGENPROBE (unabhaengig): Die 3D-Punkte in K-n11_06 zurueckprojiziert (skelett_gegenprobe_n11_06.jpg) landen auf den Rippen; K-n11_06 ging NUR als Konsens-Kamera ein, nicht als Ort der Skelettbildung. Das ist das erste Rippen-Messergebnis des Tages, das einen Fremdfoto-Test besteht.
- Bug zuvor: Tiefensuche startete bei 10 m, Kamera K-6130 steht 5,9 m vom Erker -> Strahl lief am Ziel vorbei, alle Scores 0 (~15 min). LEHRE: Tiefenbereich aus Kamera-Ziel-Abstand ableiten (kameras_am_ziel), nie fest.
- Ketten (rippen_ketten3d.py, Radius 7 cm, Luecke 35 cm): 14 Ketten, 8,6 m Gesamtlaenge (laengste 1,6 / 1,2 / 0,9 m), ketten_uz_erker0.png. Zu wenig fuer das vollstaendige Rautennetz (geschaetzt >> 20 m): Verdeckung und Skelett-Luecken. Zwei Ketten unten rechts liegen auf dem Laubenbogen (falsche Tiefe) -> Filter noetig (n-Plausibilitaet gegen Kegelflaeche).
- Naechste Schritte: (1) zweite Referenzkamera (K-n11_06 als Ref, Rest als Konsens) und Ketten vereinigen, (2) Filter gegen Fremdgold (Laubenbogen), (3) gemessene Ketten + Rippenbreite 0,15 m in rippen_pfade, Faecher nur dort behalten, wo noch keine Kette liegt (als ANNAHME), (4) Abnahme + Schattenvergleich, (5) dasselbe fuer Erker 1 (K-6171 Ref, h11_112038/d11 Konsens).

## 24. Vereinigung von 5 Referenzkameras (Erker 0) - KEIN Gewinn
- Je Referenz (K-6130, n11_06, e04, 6124, i08) Lauf rippen_skelett_tiefe.py: gute Punkte 3444 / 2519 / 1896 / 2722 / 971 (Rohsumme 11552). Flaechenfilter |n - n(z)| <= 0,25 m: 4515, Voxel-Dedup 1,2 cm: 2535.
- Ketten (Radius 6 cm): 10 Ketten, 9,4 m (vorher 14 Ketten, 8,6 m mit nur einer Referenz). Die Vereinigung bringt keine zusammenhaengenderen Rippen: parallele/leicht versetzte Punktwolken verschiedener Referenzen (Tiefenfehler je Kamera ~3-6 cm) verwischen das Skelett, der Zwei-Weg-Algorithmus (laengster Weg) bricht an Knicken.
- Zwei lange Ketten unten rechts (u > -7,3, z 6,4-7,3) liegen noch; ob Laubenbogen oder echte Rippe der +45-Facette, ist nicht entschieden (in n11_06 verlaufen dort echte Rippen nach rechts oben) - Filter dort NICHT blind setzen.
- Bilanz bis hier fuer das Rippenziel: Messung zeigt, DASS Rippen aus Nahfotos in 3D messbar sind (Kap. 23, Fremdfoto-Gegenprobe), aber die Kettenbildung erreicht nur ~9 m von geschaetzt >> 20 m. Der Engpass ist jetzt die Kettenbildung/Vervollstaendigung, nicht die Messung.
- Idee fuer den naechsten Lauf (Reihenfolge nach erwartetem Gewinn): (1) Rippenmitten statt Skelettpunkte: Rippenband (G-B-Breite ~0,15 m) im Bild quer abtasten und die Mitte nehmen -> weniger Rauschen; (2) Ketten im BILD des besten Fotos bilden (dort sind die Rippen zusammenhaengend), danach erst Tiefe je Kette per Median/Spline glaetten; (3) Kreuzungen als Knoten aus rippen3d + knoten_abstimmung und Ketten dazwischen als Kreisboegen ueber 3 Punkte; (4) Erker 1 mit K-6171 als Referenz.
- Zeitbilanz heute (Rippen): ~Kapitel 14-24; die zwei Weichenstellungen mit dem groessten Gewinn waren (a) Kameras am Ziel nach px/m sortieren (Kap. 19), (b) 3D-Punkte per Mehrkamera-Gold-Konsens (Kap. 23). Alle Wege ueber Strahl x Modellflaeche, Handpunkte oder Fit am 100-px/m-Foto kosteten Stunden ohne Ergebnis.

## 25. Aeste im Bild (rippen_aeste_bild.py) und Band-Schliessen (--close_m) - kein Gewinn
- Skelett der Gold-Maske in K-6130: 9898 Punkte, aber 1639 getrennte Komponenten (groesste 131 Punkte ~ 0,7 m); jede Rippe besteht aus 2-3 parallelen Goldlinien -> mehrere Skelettlinien je Rippe, Kreuzungen zerreissen.
- Aeste im Bild gebildet (Kreuzungen per Grad >= 5 entfernt, Tiefe aus guten Punkten robust interpoliert): 9 Aeste, 6,3 m. Mit --close_m 0,06 (Goldlinien zum Band schliessen): 7209 Punkte, 7 Aeste, 5,7 m. Also WENIGER als die 3D-Ketten (8,6 m).
- Schluss: Skelett-/Kettenverfahren bleibt bei ~6-9 m (geschaetzt < 40 % des Rautennetzes). Die Messung (Tiefe) ist nicht der Engpass, sondern die Kettenbildung aus der Gold-Maske. Naechster Ansatz sollte NICHT weiter am Skelett drehen, sondern modellbasiert sein: Rautennetz-Topologie festlegen (Knoten aus knoten_abstimmung + Rosetten), jede Rippe als Kreisbogen ueber 3 Knoten, Parameter (Knotenlage, Bogenstich) durch Zwei-/Mehrfoto-Gold-Score optimieren (Methode Kap. 17, jetzt mit 400-600 px/m und richtigem Gold-Mass G-B). Das ist ein Fit mit Fremdfoto-Gegenprobe wie Kap. 23.
- Nicht ins Modell uebernommen: Messketten (9 m) sind unvollstaendig; ein Mischmodell aus Messketten + Annahme-Faecher wuerde die Faecher-Fehlstruktur (Kap. 18) nur teilweise ersetzen.

## 26. Modellbasierte Bogenwahl (tools/rippen_bogen_wahl.py) - FEHLSCHLAG
- 1011 Kandidatenboegen (Knoten oben alle 4,5 Grad, Fusspunkte alle 10 Grad, 3 Profile) auf der Achteck-Kegelflaeche (n(z)-Kurve), Score = Gold-Konsens (Top-3 von 5 Nahkameras). Bester Score nur 0,52 (Median 0,33); 8 Boegen ab 0,42.
- Ueberlagerung in n11_06 (bogenwahl_n11_06_fehl.jpg): die gewaehlten Boegen liegen NICHT auf den echten Rippen (falscher Verlauf, falsche Kruemmung). Die echten Rippen sind grosse, stark gekruemmte Spitzboegen mit Knoten in verschiedenen Hoehen, nicht Bogen von Oberkante zu Fusskreis.
- Ursache (wahrscheinlich, nicht bewiesen): (a) Kegelflaechenmodell (Achteck mit n(z) aus Erker-1-Pfaden) stimmt am Westerker nur auf ~0,1-0,2 m, die Rippen sind nur 0,15 m breit; (b) Topologie (alle Rippen oben->Fuss) falsch, mehrere Rippen laufen zwischen Zwischenknoten.
- Folgerung: Die gemessene Punktwolke (Kap. 23, 3444 Punkte, Fremdfoto-Gegenprobe bestanden) ist belastbarer als jedes Flaechenmodell. Naechster Ansatz: aus den gemessenen Punkten die echte Flaeche n(phi,z) fitten (Glaettung), Rippen im besten Foto in 2D nachzeichnen (halbautomatisch, Pixelketten aus G-B-Band mit Hand-Via bei Kreuzungen) und auf die gefittete Flaeche projizieren; Gegenprobe in Fremdfoto; Rippenbreite 0,15 m.
- LEHRE: Modellbasierte Fits brauchen ein Flaechenmodell, dessen Fehler kleiner als die Rippenbreite ist; vor jedem Fit die Flaeche selbst gegen die Messpunkte pruefen (Residuum der 3444 Punkte gegen n(z)).

## 27. Bandmaske der Rippen in n11_06 (Farbtests) - Zwischenstand
- HSV-Schwellen (Gold H14-38 S>90 V>130, Schwarz V<48): trifft die schattigen Nischen statt der Rippen; Rippengold ist blass (niedrige Saettigung). Verworfen.
- R/G-Verhaeltnis: rote Wand R/G ~1,24-1,75, Gold 1,05-1,5 -> Trennung nur grob. Maske (R/G < 1,45 & V > 110 | V < 42) erfasst die Rippenbaender samt schwarzen Flanken, aber auch den hellen Pfeilerstein (bandmaske_n11_06_r_g.jpg); Skelett (10525 Pixel) verlaeuft teils auf Rippenmitten, teils in Schleifen um Nischen. Noch kein brauchbarer Rippenspur-Satz.
- Naechster Schritt: Bereich auf den Erker (Bildprojektion der Box) und z >= 6,45 begrenzen (Pfeiler weg), dann Skelett nur an Aesten ab Laenge >= 0,3 m, Tiefe aus der gemessenen Punktwolke (Kap. 23) per Nachbarschaft im Bild; Gegenprobe in Fremdfoto.
- Gesamtbilanz Rippen 13.11.: Es gibt (1) Messpunkte mit bestandener Fremdfoto-Gegenprobe (Kap. 23), (2) Werkzeuge zur Kameraauswahl und Knotenpruefung, (3) 9 m Ketten. Es gibt NICHT: ein Modell mit gemessenen Rippen. Annahme-Faecher bleibt im Modell (Abnahme gruen, Qualitaet laut Kap. 15 unzureichend).

## Kap. 28 – Rippenbreite 0,14 m (Nahfotos), Sichtvergleich
- objekt.json: rippen_pfade b 0.07 -> 0.14, vor 0.05 -> 0.04 (b0.14/vor0.05: Abnahme Reichweite Erker Ost z 8,0 = 1,48 Fehler; b0.12 gruen; b0.14/vor0.04 gruen). Sollwerte nicht gelockert. Regression identisch.
- Sichtvergleich K-n11_06 / K-6130: Modell zeigt breite, fast gerade Faecherbalken; Foto zeigt sich kreuzende, gebogene Rippenbaender mit Rosetten. Topologie (Annahme-Faecher) bleibt der Hauptfehler, Breite allein macht es nicht erkennbar. Realitaet Rippen ca. 25 %.
- Lehre: Breite lag um Faktor 2 daneben (Artefakt aus 100 px/m); Nahfoto-Messung zuerst.

## Kap. 29 – Rippen aus Handwegpunkten + Goldgrat-Einrasten (Erker 0)
- Neu: tools/rippen_pfad_snap.py (Wegpunkte in K-n11_06 -> Minimalkostenpfad auf 1-Gold -> Tiefe per Mehrfoto-Gold-Konsens), tools/snap_in_objekt.py (-> pfade_ohne_spiegel). Dateien modelle/rippen_runde_2026-11-13/snap1..3.
- Erkenntnis 1: Einrasten funktioniert sehr gut (Pfade liegen auf den Baendern); Wegpunkte von Hand aus dem Gitterbild lesen dauert ~2 Rundungen.
- Erkenntnis 2: freie Tiefensuche in breiter Box streut +-1 m (Box-Rand-Klemmung); Band +-0,12 m um die gemessene Kegelflaeche (Achteck, auch Seitenfacette phi bis 115 Grad) liefert glatte Bahnen (Spruenge <0,2 m). Tiefe ist damit zum Teil Flaechenannahme.
- 10 Wege, 11 Pfade, 16,3 m (Foto: >20 m geschaetzt). R5/R9 (Westfacette unten/oben) fast leer. Abnahme: Reichweite z7,2 0,81 (Soll 0,82-1,04) bei vor 0,04 -> vor 0,05 gruen (nur Erker West). freiraum_audit-Fehler (SFM-AUSRICHTUNG-buendel.json fehlt) ist alt.
- Render sh_snap_n11_06: gebogene, kreuzende Rippen jetzt sichtbar, aber treppenartig gezackt (Glaettung/Facetten), Diagonalfacetten luckig. Realitaet Rippen ca. 40 %.
- Offen: restliche Wege (Westfacette, Randboegen, Knotenstrahlen), Rosetten, Erker 1 (gleiches Verfahren mit K-6171), Zackenglaettung (Hüllen-Segmente).

## Kap. 30 – Facettennormalen: Zacken weg
- Ursache der Treppenzacken auf den Diagonal-/Seitenfacetten: eine feste Normale (0;0,796;-0,605) fuer alle Pfade (gilt nur fuer die Frontfacette). snap_in_objekt.py teilt jetzt Pfade an den Facettengrenzen (phi = round(45 Grad)) und dreht die Normale um die Hochachse.
- Ergebnis: Abnahme gruen (170 Beobachtungen, 1 Widerspruch alt); Render sh_snap5_n11_06: glatte, kreuzende Boegen, X-Kreuzungen erkennbar, Zacken rechts weg. Realitaet Rippen ca. 50 %.
- Lehre: bei Zacken zuerst die Querschnitts-Orientierung (Normale) pruefen, nicht die Pfadglaettung. Der Render-Ausschnitt war entgegen erstem Eindruck richtig ausgerichtet (Vertices im Rohrahmen verifiziert).
- Offen: Westfacette (R5, R9 leer), Rosetten, Profil Gold-Schwarz-Gold, Erker 1.

## Kap. 31 – Erker 1 (Ost) nach gleichem Verfahren
- kameras_am_ziel (u 15,52): K-6176 742 px/m (nur Randausschnitt, kaum Rippen), K-6171 637 px/m (volle Frontansicht, gut), h11_112038 598, d11 567. Ref K-6171, Gegenkameras 6176, h11_112038, d11, n11_04.
- 10 Wege (A-J), Einrasten gut (snap_K-6171.jpg); I (Randrippe links oben) ohne gueltige Tiefe (ausserhalb Flaechenband). snap_in_objekt Bauteil 10 --um 15.52. Abnahme gruen (169 Beobachtungen, 1 Widerspruch alt).
- Render sh_e1_6171: kreuzende Boegen mit X sichtbar; Gold-Schwarz-Gold-Profil, Rosetten, Kegelfuss und Pfeilerform weichen weiter ab. Realitaet Rippen Erker Ost ca. 45 %.
- Zeit: Wege lesen + Einrasten + Abnahme ca. 25 min pro Erker (vorher Tage mit Skelett/Ketten). Lehre: Handwegpunkte + Einrasten + Flaechenband schlaegt automatische Kettenbildung.

## Kap. 32 – Kappenruecksprung (kappe_rueck) 0,07 -> 0,10
- Der Generator hatte `unterbau.kappe_rueck` schon (0,07); ich hatte ihn uebersehen. Test: 0,14 -> Abnahme FEHLER Druck wasserdicht (0,00); 0,10 -> alle Pruefungen bestanden. Rippen stehen jetzt ca. 0,10 + 0,05 vor dem Kappenkoerper (ca. 1,7 mm in H0).
- Render sh_kr10_6171: Rippen heben sich etwas staerker ab; Gewoelbekappen weiter eben (echt: eingemuldet). Realitaet Rippen ca. 50 %, H0-Erkennbarkeit weiter nicht belegt.
- Offen: 0,14 wasserdicht-Fehler untersuchen (welches Teil), Kappenmulde, Westfacette, Rosetten.

## Kap. 33 – Westfacette Erker West
- R5, R6 mit Tiefenband +-0,35 m neu (R5 liegt auf u -10,2..-10,0 = Westfacette), R9 verworfen (Score 0, Median). Abnahme gruen (167 Beobachtungen, 1 alter Widerspruch). Render sh_west_n11_06: rechte Facette jetzt mit Rippen belegt. Realitaet Rippen ca. 50 %; Kappenmulde, Rosetten, Profil, Kegelfuss offen; H0-Erkennbarkeit weiter nicht belegt.

## Kap. 34 – Erste unabhaengige Messung der Rippenlage (tools/rippen_gegenprobe.py)
- Modell-Rippenpfade Erker West (11 Wege) in nicht zum Einrasten benutzte Kameras projiziert, Wert = Gold G-B lokal normiert (3x3-Max). Treffer = Gold > 0,5.
- K-6225 (515 px/m): echt 54 % Treffer (Mittel 0,51), Null (u +-0,3/0,6 m) 40 %. K-h13 (230 px/m): 53 % gegen 44 %. K-6145 (204 px/m): 47 % gegen 16 %. Referenz K-n11_06 (tautologisch): 89 %.
- Lesart: die Bahnen liegen im Fremdfoto nur etwa zur Haelfte auf Gold; der Abstand zur Nullprobe ist wegen der dichten, parallelen Rippen klein (6225/h13) -> Lage nur grob bestaetigt, Tiefe/Flaechenband ist der Schwachpunkt. Fruehere 'Realitaet ca. 50 %' war Augenschein; gemessen eher ~40-50 %.
- Naechster Schritt: Tiefe nicht aus Flaechenband, sondern Gold-Konsens mit engerem Suchfenster um die Flaeche; Treffer je Weg aufschluesseln (schwache Wege neu setzen).

## Kap. 35 – Fremdfoto-Tor je Pfad (tools/rippen_pfade_tor.py)
- Je Pfad Treffer in K-6225/K-h13: lange Pfade 76-92 %, kurze Fragmente (<0,6 m) oft 0-30 %. Tor min 0,45 (Mittel ueber Kameras): 22 -> 13 Pfade, 20,6 -> 15,7 m verworfen sind die Schwachen.
- Gegenprobe in nicht fuer das Tor benutzten Kameras: K-i08 64 % (Null 19 %), K-6145 56 % (Null 17 %; vorher 47 % / 16 %), K-6130 66 % (Null 56 %, war an der Tiefe beteiligt). Abnahme gruen.
- Lesart: Lage der behaltenen Pfade besser bestaetigt (Abstand zur Nullprobe 37-45 Punkte), aber Rippenlaenge sank um ~24 %: Vollstaendigkeit schlechter. Realitaet gemessen: Lage ~60 %, Vollstaendigkeit ~60 % (15,7 von >20 m) -> gesamt ~35-40 %.
- Offen: ausgesonderte Bereiche mit besserer Tiefe neu setzen (z.B. Foto-Triangulation statt Flaechenband), Erker Ost gleiches Tor, Kappenmulde, Rosetten.

## Kap. 36 – Tor Erker Ost
- Tor (K-6176, K-d11, min 0,45): 22 -> 20 Pfade, 19,8 -> 18,8 m. Unabhaengig K-n11_04: 61 % Treffer (Null 21 %). K-h11_112126 (Rueckseite, Gold kaum sichtbar) 7 %/5 % unbrauchbar. Abnahme gruen.
- Erker Ost schneidet besser ab als West (bessere Ref-Aufnahme 6171 frontal, Flaechenband passt). Lage ~60 %, Vollstaendigkeit ~90 % -> ca. 50 %.

## Kap. 37 – Sackgasse: Band je Weg nach Fremdfoto waehlen
- Tiefenband 0,06/0,12/0,20 je Weg neu eingerastet und das beste nach Treffer in K-6225/h13 gewaehlt (+3 bis +10 Punkte dort). Danach Tor + Gegenprobe in anderen Kameras: K-i08 64 -> 56 %, K-6145 56 -> 52 %, Laenge 15,7 -> 15,1 m. Ueberanpassung an die Auswahlkameras (K-6225 liegt azimutal bei n11_06, 103 vs 110 Grad) -> VERWORFEN, objekt.json zurueck auf c6446a1e.
- Lehre: Auswahl und Kontrolle nie mit denselben/aehnlichen Kameras; Auswahlkameras mit grossem Azimutabstand zur Ref waehlen (h13, e04), Kontrolle in dritter Kamera. Zeitfresser ~25 min.

## Kap. 38 – kappe_rueck-Grenze
- 0,12 -> Abnahme FEHLER Druck wasserdicht 0,00 (wie 0,14). Grenze liegt zwischen 0,10 (gruen) und 0,12. objekt.json zurueck auf 0,10. Hinweis: nach json.dump steht der Wert als `0.1` (sed muss darauf passen, sonst laeuft der Test ohne Aenderung).
- Naechster Schritt (nicht getan): Ursache der Wasserdichtigkeit klaeren (welches Teil: Rippe-Einbindung 0,38 m vs. Kappenruecksprung; Mesh-Reparatur oder Einbindung anpassen), erst dann tiefere Kappen.

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

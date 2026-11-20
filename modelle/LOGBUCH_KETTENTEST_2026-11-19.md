# Logbuch Kettentest 19.11.2026: Konsens-Mapper als Standard, Netzfotos in der Kette, drei Objekte

Auftrag (Nutzer 19.11., ca. 08:45): Martinstor fertig rechnen, danach Schwabentor und Kaufhaus als GANZE Kette von null bis zu den Lage-Toren
unter neuen Zielnamen; alles mitloggen; laufend nach Verbesserungen bei Geschwindigkeit und Qualitaet suchen.
Vorarbeit der Nacht: `modelle/GLOBALER_MAPPER_STABIL.md` (Agent, Rezept Konsens-Mapper).

## Was heute geaendert wurde (Commits)
- `449e91a0` Schalter `--mapper konsens` (iphone_sfm, durchgereicht von gesamtkette ueber pipeline_objekt).
- `f57e3c48` Konsens-Mapper ist STANDARD (`--mapper auto`); traegt er nicht -> `ACHTUNG DATENMANGEL` mit Ursache/Abhilfe (Log, mapper_wahl.json, Kettenbericht), erst dann alter Weg (`auto_alt`).
- `9a7c21c0` Zwischenspeicher Bildvorpruefung (je Bild/Kettenpaar) + Kamera-Abdeckung sofort nach dem Mapper (`ACHTUNG ABDECKUNG`).
- `e3800163` Netzfotos in der Kette (Stufe commons: `tools/netz_fotos_holen.py`, Openverse + Commons-Umkreis + Hochblicke, Zwischenspeicher 7 Tage).
- `8d4a94d9` geaenderter Fotosatz loest SfM neu aus (`pipe/fotosatz.json`); commons_harvest behaelt die Dateiendung beim Kuerzen.

## Zeitleiste / Messungen
| Zeit | Was | Ergebnis |
|---|---|---|
| 18.11. 21:41-01:09 | Martinstor `mt_gk3`, alter Weg | global 19 min (894 Bilder, 6 Teilmodelle), schrittweise nach 3 h am Stufenlimit abgebrochen (~600/1032), kein Modell |
| 06:48-07:22 | Martinstor `mt_gk3k`, Konsens-Mapper | 33 min, 833/1032 Bilder, 159 422 Punkte, 0,77 px, Rueckgrat 630/881 |
| 07:22-08:02 | dichte Wolke, Stufe schnell | ~40 min fuer 548 gewaehlte Bilder, 2,04 Mio Punkte |
| 08:02-08:16 | Ausrichtung + Lage-Tore, 3 Lagen | ALLE ROT: Guete 20 % (zweitbeste 19 %), Grundriss 43 % Randdeckung, 7/60 Fotos unter Gelaende, 2 Insel-Clips, GPS-Rest 44,5 m (Tor hier vermutlich blind) -> Abbruch 'nicht modellieren' |
| 07:36 | Test Datenmangel (28 Fotos, kein Clip) | Meldung korrekt (nur 28 Bilder, kein Videoclip), Ausweichweg rc 0 |
| 08:10 | Test Vorpruef-Zwischenspeicher (55 Bilder) | 47 s -> 7 s, Ergebnis identisch |
| 08:19- | Kaufhaus Konsens-Mapper auf Kopie (`kh_konsens`, 1364 Bilder) | laeuft |
| 08:30- | Martinstor `mt_gk3n`: Kette ab commons mit Netzfotos | Commons-Kategorie 107 Bilder (143 s); Netz: Openverse 21, Commons-Umkreis 77 (75 davon historische LABW-Aufnahmen) |

## Befunde
- Martinstor scheitert an den DATEN, nicht am Mapper (ANNAHME, gestuetzt: alter Lauf scheiterte an denselben Toren): 586 von 833 Kameras in einem 30-Grad-Sektor,
  4 von 12 Sektoren < 5 Kameras; die Wolke ist vor allem ein Fassadenstreifen entlang der Strasse, der Turm selbst kaum gedeckt (audit/wolke_grundriss.png).
- Die Kette holte bisher am Anfang nur EINE Commons-Kategorie; alle anderen Netzquellen erst in Stufe `seiten` hinter den Lage-Toren -> bei roter Lage nie.
- Ein vorhandenes `sfm/sparse/0` galt als erledigt, auch wenn neue Fotos gesammelt wurden.
- commons_harvest schnitt langen Titeln die Endung ab -> Bilder fuer Vorpruefung/SfM unsichtbar (auch in aelteren Ernten 3-4 Dateien).
- Die dichte Wolke rechnet nur 548 der 833 Bilder (Bildwahl) - die GPU ist dabei zu 100 % ausgelastet, die CPU fast frei.
- Die RAM-Buchung der Kette (11 GB fuer den ganzen Lauf) blockiert parallele Jobs, gebraucht werden die 11 GB nur in der Fusion (Tiefenkarten-Phase gemessen ~1,6 GB).

## Sackgassen / Zeitfresser
- Abdeckungspruefung VOR dem Mapper geht nicht: Foto-GPS fehlt bei Videobildern, Wikimedia-Geotags unbrauchbar -> Meldung erst nach dem Mapper (33 statt 78 min).
- Zwei globale Laeufe parallel: braucht 2 x 6 GB RAM, auf 15 GB nicht ohne Auslagern (Agent, Nacht).
- Openverse fuer Martinstor: nur 21 neue Bilder aus 7 Suchbegriffen.
- Platz: /media/oem/scan hat 29 GB frei, ein Lauf braucht ~19 GB (sfm 6,5 + dicht 12) -> alte dichte Wolke nach /media/oem/rcdaten/beiseite/martinstor_gk3_1119_konsens1 verschoben.

## Verbesserungsliste (laufend; G = Geschwindigkeit, Q = Qualitaet)
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 1 | Konsens-Mapper statt schrittweise | G+Q | Standard seit f57e3c48 |
| 2 | Bildvorpruefung zwischenspeichern | G | gebaut 9a7c21c0 |
| 3 | Abdeckung sofort nach dem Mapper | G | gebaut 9a7c21c0 |
| 4 | Netzfotos vor der SfM | Q | gebaut e3800163 |
| 5 | RAM-Buchung je Stufe statt je Lauf (Mapper Objekt B neben Tiefenkarten Objekt A) | G | offen |
| 6 | Videobilder bei den Tiefenkarten ausduennen (jedes zweite als Referenz) | G | offen, erst messen (Punktzahl, Wolkenabstand, Strassenpunkte) |
| 7 | Stufe `seiten` frueh abbrechen, wenn keine Kandidaten registrieren | G | offen |
| 8 | Merkmale/Paare der unveraenderten Bilder bei neuem Fotosatz wiederverwenden (statt db neu) | G | offen |
| 9 | Referenz-Merkmale der Vorpruefung zwischenspeichern (Rest 7 s) | G | offen, klein |
| 10 | Lage-Tor ohne GPS fuer Objekte mit unbrauchbaren Geotags (Modellvergleich/Plausibilitaet) | Q | offen |
| 11 | Ausrichtung: bei Guete-Gleichstand (20 % / 19 %) nicht raten, sondern als 'mehrdeutig' melden + welche Daten fehlen | Q | offen |
| 12 | Fuer Fassaden nur Rueckgrat-Kameras nutzen (konsens_arbeit/unstabil.txt) | Q | offen |
| 13 | Tiefenkarten wiederverwenden, wenn Kamera eines Bildes unveraendert | G | offen, erst messen |

## Plan
1. Martinstor `mt_gk3n` bis sammeln, dann `--ab sfm --bis tore` (Konsens-Mapper, neue Netzbilder).
2. Schwabentor ganze Kette von null bis Tore, neuer Zielname (GPS dort belastbar).
3. Kaufhaus ganze Kette von null bis Tore, neuer Zielname.
Je Lauf: Zeiten je Stufe, Bildzahlen, Tore, Auffaelligkeiten hier eintragen.

## 08:47-09:05 Nutzer: 3D-Seite der Martinstor-Wolke "ist Muell" - Ursache: LOT falsch (Modell lag auf der Seite)
- Ich hatte die Seite veroeffentlicht, OHNE sie anzusehen. Lehre: vor jedem Zeigen drei Ansichten (Draufsicht + 2 Seiten) selbst rendern und ansehen.
- Ursache: `sfm_lod2_ausrichten.py` nimmt das Lot als Normale der Ebene durch die Kamerazentren. Martinstor hat Drohnenclips (Kameras 10-26 m ueber der Strasse):
  Streuung der Zentren 30/11/7,9 (Dicke/Laenge 0,26, eigene Grenze 0,25) -> Ebenennormale 86,6 Grad neben dem echten Lot. Wolke z -29..+57 m, Faecher im 3D-Bild.
- Beleg fuer das richtige Lot (unabhaengig): Bild-x-Achsen aller 833 Kameras stehen senkrecht darauf (Rest Median 0,8 Grad, p90 3,3); Wandnormalen der dichten Wolke
  stimmen auf 0,3 Grad ueberein (43 % der Normalen waagerecht +-10 Grad); Strassenclips liegen damit auf konstanter Hoehe (z. B. -0,14 +-0,02 Einheiten), Drohnenclips 2-5,5 Einheiten darueber.
- Fix: Lot aus dem Kamerablick, gilt nur bei Widerspruch > 15 Grad zur Kameraebene und >= 50 % stuetzenden Kameras (`ACHTUNG LOT`); alte Laeufe unveraendert. Schnelltest 0, Regression Martinstor identisch.
- KORREKTUR meiner Aussage von 08:16 ("Datenproblem, nicht Mapper/Kette"): die roten Lage-Tore des Laufs mt_gk3k beruhten mindestens zum Teil auf DIESEM Fehler. Das Modell selbst ist
  in sich stimmig (ebener Boden, konstante Clip-Hoehen). Ob die Abdeckung reicht, ist erst nach neuer Ausrichtung zu beurteilen.
- NOCH OFFEN: mit richtigem Lot liefert die Einpassung in den Stadtplan Guete 10 % (zweitbeste 7 %), Massstab 0,2096 Einh./m, Wolkenhoehe p99 nur 15,5 m (Turm ~60 m) und der Boden
  kippt nach der Feinanpassung um ~9 Grad -> Massstab/Feinanpassung verdaechtig (Wolke deckt ein ganzes Viertel aus Drohnen- und Strassenclips, Suchradius der Einpassung 30 m).
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 14 | Lot aus Kamerablick statt Kameraebene bei Widerspruch | Q | gebaut (dieser Eintrag) |
| 15 | Feinanpassung darf das Lot nicht mehr kippen (Rotation nur um die Hochachse) / Massstab-Startwert pruefen | Q | offen, als Naechstes |
| 16 | 3D-Seite der Kette: vor dem Zeigen automatisch 3 Ansichten rendern (audit/wolke_ansichten.png) | Q | offen |
| 17 | kh_dicht_viewer: Seitentitel aus --titel statt fest 'Kaufhaus Dichtewolke' | Q | offen, klein |

## 09:05-09:20 Nutzer: "da ist kein Martinstor zu sehen" - zweite Ursache: MASSSTAB der Einpassung um Faktor ~3,6 falsch
- Die 3D-Seite V2 nutzte den Massstab der Einpassung (0,21 Einh./m). Unabhaengige Belege fuer ~0,058 Einh./m: (a) Strassenkameras stehen 0,13 Einh. ueber den tiefsten Punkten
  (= 2,2 m bei 0,058; bei 0,21 waeren es 0,6 m); (b) Punkte der eigenen Martinstor-Fotos spannen 3,4 Einh. in der Hoehe (= 58 m, Turm ~60 m).
  Mit 0,21 war das Tor im Bild 17 m hoch und ging im Viertel unter; der Ausschnitt +-90 m zeigte in Wahrheit +-325 m.
- Mit Lot aus Kamerablick + 0,058 + Ausschnitt 50 m um den Turm: Tor steht aufrecht, Uhr, Dach und Spitze bis ~65 m erkennbar (audit/wolke_turm_ansichten_1119.png).
  1,29 von 2,04 Mio Punkten liegen im 38-m-Umkreis des Turms -> das Modell ist brauchbar, die AUSRICHTUNG war in zwei Stufen falsch (Lot, Massstab).
- Grobsuche der Einpassung probierte Massstaebe 1,25 .. 0,085; der richtige Bereich (~0,06) fehlte. Gewaehlt 0,25 bzw. 0,21 bei Guete 20 % / 10 %.
- Lehre: Massstab VOR der Einpassung unabhaengig schaetzen - Kamerahoehe der Strassenkameras ueber dem Boden (~1,6 m) gibt ihn auf ~30 %; Suche nur in diesem Fenster.
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 15 | Massstab-Startwert aus Kamerahoehe ueber Boden (Strassenclips, Lot bekannt), Grobsuche auf Faktor 0,6..1,6 darum begrenzen | Q+G | als Naechstes |
| 18 | Bildwahl der dichten Wolke haengt an der Ausrichtung (>= 60 Objektpunkte): bei falscher Ausrichtung falsche 548 Bilder? pruefen | Q | offen |

## 09:17 Kaufhaus: Konsens-Mapper gegen den alten schrittweisen Lauf (gleiche Datenbank, gleiche Kennzahlen `tools/mapper_bewerten.py`)
| Modell | Zeit | Bilder | Teilmodelle | Fehler px | GPS-Median (n) | GPS > 15 m | f unplausibel / fern | groesste Luecke |
|---|---|---|---|---|---|---|---|---|
| schrittweise (17.11.) | 5,6 h | 982 | 13 | 1,05 | 4,6 m (110) | 32 % | 0 / 0 | 78 Grad |
| global einfach (17.11.) | 27 min | 1050 | 15 | 1,09 | 9,1 m (115) | 38 % | 29 / 30 | 39 Grad |
| KONSENS (19.11.) | 56 min | 949 | 1 | 0,99 | 5,1 m (107) | 33 % | 0 / 0 | 93 Grad |
- Konsens = Qualitaet des schrittweisen Laufs (GPS 5,1 gegen 4,6 m, Anteil gleich) in einem Sechstel der Zeit; Rueckgrat 870 von 1050 (83 %), unstabil 17 %.
- Preis: 33 Bilder weniger, die Kameraluecke waechst von 78 auf 93 Grad (ueber der 90-Grad-Grenze 'Seite ungesehen') -> pruefen, welche Bilder fehlen (unstabil.txt) und ob sie die Luecke schliessen.
- Zeiten: Lauf 1 1265 s, Lauf 2 1346 s, Stufe 2 761 s. Die zwei globalen Laeufe sind 77 % der Zeit (Idee 5b: parallel, sobald RAM reicht).
- 32-33 % der GPS-Fotos > 15 m in ALLEN Modellen -> das sind falsche Geotags, kein Modellfehler (Schwelle 15 % des GPS-Tors ist fuer dieses Objekt nicht erreichbar).
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 19 | Konsens Stufe 2: verworfene Bilder, die eine Kameraluecke schliessen wuerden, gezielt nachregistrieren (lockerere Schwelle nur fuer diese) | Q | offen |
| 20 | GPS-Tor: Schwelle relativ zum besten erreichbaren Anteil / Mehrheitscluster statt fest 15 % | Q | offen |

## 09:20-09:35 Ausrichtung Martinstor: Massstab aus Kamerahoehe + Hoehenprobe gegen LoD2 (Ideen 15, neu 21)
Gleiche Wolke (Lauf mt_gk3k), Testname `martinstor_gk3_lot`:
| Stand der Ausrichtung | Massstab Einh./m | Guete | Objektwand-Abdeckung | Wolke z p1..p99 | Fernfotos (Entfernung, Richtung) |
|---|---|---|---|---|---|
| alt (Lot aus Kameraebene) | 0,250 | 20 % (zweitbeste 19 %) | - | -29 .. 57 m (liegt auf der Seite) | x4,64 / 25 Grad |
| + Lot aus Kamerablick | 0,210 | 10 % | - | -4,9 .. 15,5 m | - |
| + Massstab aus Kamerahoehe (Start 0,073, Band x2) | 0,097 | 19 % | 45 % | -0,5 .. 31,8 m (Turm 40 m) | - |
| + Hoehenprobe gegen LoD2-Hoehe 45 m | 0,0725 | 35 % (zweitbeste 35 %, gleiche Familie 165-168 Grad) | 82 % | -1,2 .. 42 m, Turmspitze ~55 m | x1,20 / 3 Grad |
- Hoehenprobe: Hoehe der Wolke ueber dem Objektgrundriss (99,5-Perzentil) gegen LoD2-Hoehe des Objekts; Abweichung > 13-15 % -> Loesung abwerten, zweiter Feinfit mit korrigiertem Massstab.
  Nur ohne GPS-Massstab (mit GPS gilt das bestehende GPS-Raster) -> Objekte mit GPS unveraendert.
- Tore danach (von Hand auf der Testausrichtung): Gelaende ROT (A_PUR2GXND0 12/74, gjVSpDSd8rU 7/16, fotos 6/74 unter Gelaende = vermutlich die unstabilen Einzelkameras der Stufe 2),
  Grundriss ROT (Wolke deckt 51 % des Objektrands, 11,5 % Punkte auf der Strasse: Fassadenzeilen oestlich liegen 5-8 m neben den Baulinien -> Drehung/Massstab noch nicht exakt),
  GPS ROT (17 Geotags, Rest 44,5 m, vermutlich Objektstandorte); Fernfotos stuetzen die Lage (Richtungsfehler 3 Grad, Entfernung x1,20).
- Bild: audit/wolke_ansichten_lot_1119.png (Turm aufrecht, Uhr, Tordurchfahrt, Spitze ~55 m, Haeuser 15-20 m), audit/wolke_grundriss_lot_1119.png.
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 15 | Massstab-Startwert aus Kamerahoehe | Q | gebaut |
| 21 | Hoehenprobe gegen LoD2-Objekthoehe + Massstabskorrektur | Q | gebaut |
| 22 | Restfehler Grundriss: Feinfit nur mit Rueckgrat-Kameras/-Punkten; unstabile Kameras (unstabil.txt) aus Gelaende-/Inseltor herausnehmen oder getrennt melden | Q | offen |
| 23 | Himmelsrauschen ueber dem Turm ('Fahne' in der Seitenansicht): Fusion strenger oder Himmelsmaske | Q | offen |

## 09:57-10:15 Nutzer: "Haeuserzeile im voellig falschen Massstab" + "viel zu grosser Bereich, nur das Martinstor"
- Ursache der schiefen, zu grossen Haeuserzeile: Tiefenkarten UNSTABILER Kameras. 4899 duenne Punkte lagen > 25 m hoch neben dem Turm; gesehen fast nur vom Fernclip
  `video_frames_gjVSpDSd8rU` (16 Kameras, 152 m entfernt, 7 davon unter Gelaende) und Einzelfotos aus fotos_eingang. Der ganze Clip steht in konsens_arbeit/unstabil.txt.
  Dieselben Gruppen meldeten Gelaende- und Inseltor - die Warnung war da, die Folgerung (aus der dichten Wolke nehmen) fehlte.
- Test: Fusion nur mit den 383 stabilen der 548 Bilder (vorhandene Tiefenkarten, 360 s): hohe Punkte neben dem Turm 11 353 -> 176; Turmausschnitt 854 000 Punkte.
  Bild audit/turm_stabil_1119.png: Turm sauber, Uhr, Daecher, Spitze ~55 m, Tordurchfahrt.
- Fix in der Kette: `dicht_bildwahl.py --ohne konsens_arbeit/unstabil.txt` (pipeline_objekt, wenn der Konsens-Mapper gewaehlt wurde): 387 statt 548 Bilder -> auch ~30 % weniger Tiefenkarten.
  Dazu derselbe Lot-Fehler in dicht_bildwahl (Objekt-Zylinder um die Normale der Kameraebene) behoben.
- 3D-Seite: nur noch der Turm (12,5 m um die Achse) statt 50 m Umkreis.
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 12 | nur Rueckgrat-Kameras in die dichte Wolke | Q+G | gebaut |
| 24 | 3D-Seite der Kette: Ausschnitt = Objektgrundriss + Rand, nicht die ganze Wolke; Ansichten vorher rendern | Q | offen (bisher von Hand) |
| 25 | Tore: unstabile Kameras getrennt ausweisen (rot nur, wenn Rueckgrat-Kameras betroffen) | Q | offen |

## 10:15-10:45 Warum fehlt eine Turmwand? + Wolken-Gruppen-Tor (Idee 26) gebaut
- Messung am Turmschaft (8-32 m, Wandnormalen je 45-Grad-Sektor): gesehene Seite ~240 000 Punkte / 568 stabile Kameras; Flanken je ~30 000 / 20-35; Gegenseite < 3000 / 4 Kameras.
  Mit ALLEN Kameras gleich wenig (735 gegen 742) -> nicht durch das Aussortieren der unstabilen Kameras verursacht.
- Kontaktboegen (audit/bogen_gesehene_seite_1119.jpg, bogen_gegenseite_flanken_1119.jpg): praktisch alle Fotos und Clips zeigen DIESELBE Turmseite (die mit dem
  Staffelgiebelhaus/McDonald's daneben). Die 4 Kameras 'auf der Gegenseite' sind Bilder eines Gangs durch die Durchfahrt und blicken vom Turm WEG die Strasse hinunter.
  Die Flanken kommen nur aus Drohnenclips (Dach und obere Turmhaelfte von schraeg oben).
- Unter den nicht registrierten Bildern sind einzelne Kandidaten der Gegenseite; ohne Brueckenbilder (gleiche Punkte auf beiden Seiten sieht kein Foto) kann der Mapper sie nicht anhaengen.
  ANNAHME, nicht einzeln belegt.
- Himmelsrichtung der fehlenden Seite: nach der Einpassung Sued-Suedwest; Einpassung noch 'mehrdeutig' -> nicht sicher.
- NEU `tools/wolke_gruppen_pruefen.py` (Kette: tor_gruppen, wolke_neu_fusionieren liest audit/wolke_gruppen.json): Punkte > 6 m ueber der LoD2-Hoehe ihrer Umgebung (Umkreis 10 m)
  oder > 4 m unter Gelaende = unmoeglich; Videoclip auffaellig ab 25 % seiner eigenen Punkte, Einzelfotos je Bild. Martinstor: Fernclip gjVSpDSd8rU 44 % + 6 Vorschaubilder = 22 Bilder.
  Schutz: sind > 6 % ALLER Punkte unmoeglich, ist die Ausrichtung falsch -> nichts ausschliessen (alte, auf der Seite liegende Ausrichtung: 11,3 %; richtige: 1,8 %). 4,5 s.
- Die Kette fusionierte bisher nur neu, wenn das GPS-Tor gruen war (am Martinstor blind) -> jetzt auch, wenn das Gruppen-Tor Bilder nennt.
- 10:13 Martinstor-Kette `mt_gk3s` gestartet: 1503 Bilder (vorher 1032; 12 neue Clips, Netzfotos). Vorpruefung 6295 Bilder in 36 min (Zwischenspeicher nur 265 Treffer: Referenzsatz neu).
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 26 | Wolken-Gruppen-Tor | Q | gebaut |
| 27 | Vorpruef-Zwischenspeicher: Schluessel haengt am ganzen Referenzsatz - aendert sich ein Referenzfoto, ist alles neu. Besser je (Bild, Referenzfoto) speichern | G | offen |
| 28 | Gegenseite gezielt suchen: nicht registrierte Bilder, die das Objekt zeigen (Vorpruefung ja, Mapper nein), als Kontaktbogen + Fotoauftrag 'Bruecke' ausgeben | Q | offen |

## 10:20-10:25 Fehlende Turmseite: die Vorpruefung selbst sortiert die Gegenseite aus (Zeitfenster gebaut)
- Befund: `bilder_vorpruefen.py` laesst ein Fremdbild nur durch, wenn es >= 60 Merkmals-Inlier zu einem OBJEKTFOTO hat. Die Objektfotos zeigen (fast) alle dieselbe Turmseite ->
  jedes Bild der Gegenseite gilt als 'zeigt das Objekt nicht'. In Videoclips rettet die Nachbar-Kette nur, solange Nachbarbilder sich treffen (reisst im dunklen Durchgang).
- Netzfotos helfen hier nicht: 51 abgelehnte Netzbilder mit 'Martinstor' im Namen durchgesehen (Kontaktbogen) = historische Festzuege VOM Turm aus, Details, Panoramen; keine Gegenseite.
  Unter den 91 vom Mapper nicht registrierten Einzelbildern des alten Laufs eine Handvoll Kandidaten der Gegenseite (eigen__067, __124, __129, __135) - zu wenige, ohne Bruecke.
- Fix: `--fenster 12` (Standard): in jedem Videoclip zaehlen 12 Bilder vor/nach jedem Treffer mit. Martinstor: +596 Bilder aus 28 Clips (Kontaktbogen: Stadtrundgaenge, darunter
  Blicke auf Torturm und Wandbild; auch Unbeteiligtes wie Muenster/Markthalle - das wirft die SfM ab).
- Zwischenspeicher wirkt: Vorpruefung von 6295 Bildern beim zweiten Lauf 6 s statt 36 min.
- Lauf mt_gk3s (1503 Bilder, noch im Abgleich) gestoppt; neu `mt_gk3t` ab vorpruefen bis tore mit den Fensterbildern.
- Falls die Gegenseite danach noch fehlt: gezielte Videosuche (Stadtrundgaenge/Strassenbahn-Fuehrerstand fahren DURCH das Tor; video_suchen --anfragen, --max-s hoeher als 1500 s),
  danach Fotoauftrag.
| Nr | Idee | Art | Stand |
|---|---|---|---|
| 29 | Zeitfenster um Videotreffer (Gegenseite/Durchgang) | Q | gebaut |
| 30 | Videosuche: Zusaetze 'walking tour', 'Rundgang', 'Fuehrerstandsmitfahrt/cab ride' + laengere Clips, nur der Abschnitt um die Treffer | Q | offen |
| 31 | Gegenseiten-Referenz: nach dem ersten Mapper Bilder der schwach gedeckten Seite als ZUSAETZLICHE Referenzfotos der Vorpruefung nehmen und nicht bestandene Bilder erneut pruefen | Q | offen |

## 11:46 Martinstor, Lauf mt_gk3t: Mapper fertig (1990 Bilder, mit Zeitfenster-Bildern)
- Konsens-Mapper 4072 s (68 min; erster Lauf mit 1032 Bildern: 33 min). Rueckgrat 677 von 1265 gemeinsamen, im Modell 1012 von 1990, 603 unstabil. Kein Datenmangel.
- Zeitfenster-Bilder: 453 von 596 registriert - die Regel bringt Bilder ins Modell.
- GEGENSEITE: Kameras hinter dem Turm 22 statt 4 (Clips jRN8bKSDj2U 12, o34426Ez5_U 6, 4 Fotos), aber Turmpunkte je 45-Grad-Sektor weiter 12482/12703 vorn gegen 35/30/725 hinten -> Gegenseite in der duennen Wolke weiter fast leer. Das Zeitfenster allein loest es NICHT; die Clips laufen offenbar kaum durch das Tor bzw. blicken dahinter nicht zurueck.
- Fruehe 3D-Seite (duenne Wolke + Kameras) 1 min nach dem Mapper: neues Modell ueber 562 gemeinsame Rueckgrat-Kameras (Sim3, Rest 0,15 m) ins Metersystem der Pruefausrichtung gebracht - keine neue Ausrichtung noetig. https://claude.ai/artifact/8CrWrbZYSBDfGgdE2nKxTH (Skripte im Scratchpad mt3d/duenn2*.py)
- Verbesserung 32 (Idee): diese fruehe Seite + Sektor-Zaehlung (Kameras und Punkte je Turmseite) als Kettenstufe direkt nach dem Mapper; kamera_abdeckung zaehlt nur Kameras, nicht ob die Seite Punkte bekommt.
- Naechster Schritt Gegenseite: gezielte Videosuche (Ideen 30/31) laeuft parallel zur dichten Wolke (nur Netz/CPU).

## 12:05 URSACHE der fehlenden Turmseite gefunden: Seitenverwechslung (Doppelgaenger), NICHT fehlende Bilder
- Befund 1 (Kontaktabzug der 978 nicht registrierten Bilder): die neuen Stadtrundgang-Clips liefern vor allem Muenster, Kaufhaus, Schwabentor, Rathaus - kein Martinstor. Komponenten ohne jede Verbindung ins Modell: 127, 87, 47, 25, 24 Bilder. Sie kosten Mapper-Zeit (68 statt 33 min) und bringen nichts. -> Verbesserung 33: Videobilder ohne Verbindung zum Objekt vor dem Mapper streichen (Paarliste: Komponente ohne Kante >= 30 Inlier zur Objektkomponente); dieselben Bilder sind Futter fuer Kaufhaus/Schwabentor (Verbesserung 34: Clips objektuebergreifend auswerten).
- Befund 2: Fotos der GEGENSEITE sind im Bestand (z.B. eigen__000, 025, 075, 121, 124, neu_957f, ov_0009: Turm mit Uhr, das Nebenhaus mit McDonald's steht LINKS vom Turm; in den registrierten Rueckgrat-Fotos steht es RECHTS) - Bild audit/gegenseite_fotos_vorhanden_1119.jpg. Sie haben 16-65 Paare mit dem Modell (bis 925 Inlier), sind aber nicht registriert oder stehen als UNSTABILE Kameras auf der Vorderseite (x +57..+100, eine bei x 368, z -90).
- Deutung: beide Turmseiten sehen fast gleich aus (Uhr, Ecktuermchen, Helm). Die Merkmalszuordnung verbindet Vorder- und Rueckseite, die Geometriepruefung (2 Bilder) laesst das durch, der Mapper klappt die Rueckseite auf die Vorderseite. Der Konsens-Schnitt hat diese Kameras als unstabil erkannt (richtig), deshalb fehlt die Wand statt doppelt zu erscheinen.
- Gegenprobe: 44 Bilder (Gegenseiten-Fotos + alle nicht-Rueckgrat-Bilder mit >= 3 Paaren >= 50 Inlier dazu) ALLEIN rekonstruiert (colmap mapper --Mapper.image_list_path, 41 s CPU): 41 Bilder, 3902 Punkte, 0,98 px - sauberes Teilmodell einer Fassade mit Kamerareihe die Strasse hinunter (audit/gegenseite_teilmodell_1119.png).
- Offen: LoD2-Ausrichtung des Teilmodells allein (Guete 31 %, zweitbeste 29 %) legt die Kameras auf dieselbe Seite wie das Hauptmodell - LoD2 ist um die Strassenachse fast spiegelgleich und entscheidet die Seite nicht. Eine der beiden Ausrichtungen ist also um 180 Grad falsch. Entscheider gesucht: Nebenhaus (rechts/links vom Turm) gegen LoD2-Grundriss, Foto-GPS, Drohnenclip.
- Sackgasse: Videosuche mit Treffer-Beweis gegen Objektfotos kann eine ungesehene Seite grundsaetzlich nicht finden; Fussgaenger-Clips drehen sich hinter dem Tor nicht um (22 Kameras dahinter, alle blicken weg). video_suchen.py hat trotzdem --ref-liste/--zusaetze/--ohne bekommen (Referenz frei waehlbar).
- Plan (Verbesserung 35, Hauptpunkt): Seiten-Teilmodelle. Nach dem Konsens: unstabile + nicht registrierte Bilder -> Komponenten -> je Komponente >= 15 Bilder eigenes Teilmodell -> jedes fuer sich an LoD2, Seite ueber unsymmetrische Nachbarbauten entscheiden, dann im Metersystem vereinen (Feinpassung ueber gemeinsam sichtbare Teile: Helm, Nebenhausdach) -> dichte Wolke aus beiden. Skripte: tools/versuche/mt_gegenseite_*_1119.py

## 12:20 Nutzerfrage: "Seitenverwechslung hatten wir beim Schwabentor schon - ich dachte, geloest." Untersuchung
- Stimmt: das Problem ist DREIMAL belegt. Martinstor alt (VERSUCHSREGISTER Zeile 649 "COLMAP hatte beide Uhrseiten zu einer Fassade verklebt", 1257), Schwabentor 15.11. (STAND Zeile 211: 12 780 LightGlue-Paare gegenueberliegender Seiten, Suedgruppe verzerrt, Knauf 6,26 m auseinander), heute.
- Was damals gebaut wurde: sfm_netz.py (Fotoliste je Seite VON HAND), lg_in_db_anhaengen.py (Paare nur bis 110 Grad Azimut, alte > 120 Grad geloescht - braucht Kamerastandorte aus K-Dateien eines vorhandenen Modells), gruppen_punkt_tor.py (Tor mit Hand-Picks; Knauf danach 0,9 m).
- Was NICHT gebaut wurde: nichts davon steht in gesamtkette.py/pipeline_objekt.py/iphone_sfm.py (grep: nur kette_insel_pruefen). Der allgemeine "Doppelgaenger-Paarfilter" steht in STAND_2026-11-14.md Zeile 144 als OFFEN; STAND Zeile 212 Punkt (4) "Tore in die Kette einbauen" blieb liegen.
- Warum es heute nicht auffiel: am Schwabentor faengt das GPS-Tor den Fehler (9 %), am Martinstor ist es blind (keine Standort-GPS). Der Konsens-Mapper wurde nur auf Wiederholbarkeit und GPS geprueft, nicht auf Seiten.
- MEIN FEHLER (Rueckfall, kein Lernen): um 12:05 als neuen Fund gemeldet, ohne das Register zu durchsuchen (CLAUDE.md: "Vor neuen Versuchen NICHTS_GEBRACHT / VERSUCHSREGISTER lesen").
- Folge fuer Verbesserung 35: vorhandene Teile wiederverwenden. Teilmodelle liefern die Seite je Bild OHNE Vorwissen -> Azimut je Bild -> Paarfilter aus lg_in_db_anhaengen (alt_weg_ab 120 Grad) auf die Kettendatenbank -> ein Mapperlauf. Seitentor ohne Hand-Picks: Teilmodell aus unstabilen/nicht registrierten Bildern >= 15 Bilder = WARNUNG "zweite Seite nicht im Modell".

## 12:45 Seitenerkennung (Nutzer: "Vollgas, jedes Gebaeude hat mehrere Seiten") - Messungen
- Lauf mt_gk3t fertig 12:21: dichte Wolke 1,3 Mio Punkte (fotometrisch, 27 min), ABBRUCH "keine Lage besteht alle Tore" (GPS, Grundriss in allen 4 Loesungen rot). Die Tore haben also recht gehabt. Bild audit/dicht_lauf_gk3t_1119.png: eine Turmseite, 30 Grad gekippt -> keine 3D-Seite veroeffentlicht.
- KORREKTUR zu 12:05: nicht nur die unstabilen Kameras sind betroffen. Das RUECKGRAT selbst ist gemischt (audit/rueckgrat_gemischt_1119.jpg): Nahaufnahmen mit Nebenhaus LINKS (Clip A_PUR2GXND0, eigen 030/041) und Fernansichten mit Nebenhaus RECHTS (Clip LSi6HGXqmiY, eigen 089) stehen beide im Rueckgrat auf derselben Seite. Beide globalen Laeufe verkleben gleich -> der Konsens-Schnitt (Wiederholbarkeit) erkennt Seitenverwechslung grundsaetzlich NICHT.
- Was funktioniert: GEMEINSCHAFTEN im Paar-Graphen (Louvain, Gewicht = Inlier, alle 1990 Bilder, 2 s). Gemeinschaft 0 (242 Bilder): 63 Bilder "Nebenhaus rechts", 0 "links". Gemeinschaft 1 (110): 7 links, 0 rechts. Gemeinschaft 3 (61): 12 links, 0 rechts. Fremde Bauten (Muenster usw.) fallen als eigene Gemeinschaften ohne Verbindung heraus. -> Seiten trennen sich im Graphen sauber.
- Jede Gemeinschaft allein rekonstruiert (schrittweiser Mapper, CPU, 4 parallel ~10 min): h_a/h_b (Haelften von Gem. 0), c1, c3 -> saubere Teilmodelle.
- Offen: welche VERBINDUNG zwischen zwei Gemeinschaften ist echt, welche Verwechslung? Drei Masse gemessen (tools/versuche/mt_seiten_relation_1119.py):
  echt (h_a:h_b): 11 509 gemeinsame Punkte, Sim3-Inlier 75 %, Freiraum-Konflikt 1,7 %
  verwechselt (h_a:c1 / h_b:c1): 532 / 475 gemeinsame Punkte, Sim3-Inlier 33 %, Konflikt 4,7 / 4,3 %
  unklar (h_a:c3): 435, 42 %, 1,3 %; c1:c3 keine einzige Verbindung (Fern- gegen Nahaufnahmen).
  -> Sim3-Inlier trennt (75 gegen 33 %), aber nur EIN echtes Beispiel; Freiraum-Probe zu schwach (Nahaufnahmen sehen nur die Wand). Schwache echte Verbindung (Eckfotos) sieht bei "gemeinsame Punkte" genauso aus wie eine Verwechslung.
- Naechster Schritt: gelernten Paar-Klassifikator pruefen (Doppelgangers, Lizenz/Gewichte), nur auf Paare ZWISCHEN Gemeinschaften anwenden (wenige tausend) und je Gemeinschaftspaar abstimmen; dazu mehr echte Vergleichspaare (Schwabentor mit GPS als Wahrheit).

## 13:00 Seitenerkennung: erster voller Lauf, Pruefer allein reicht nicht; Geometrie-Gegenprobe gebaut
- tools/seiten_erkennen.py Martinstor (1990 Bilder, 22 min GPU, 1912 Paare, 0,7 s je Paar): 148 Gemeinschaften, 43 >= 12 Bilder, 80 Verbindungen: 31 'verwechselt', 26 'unklar', 23 'echt'. Verteilung p_gleich: Median 0,46. Sicher verwechselt (0<->1) 0,333, vermutlich echt Drohne<->Strasse (0<->4) 0,383 -> Schwelle 0,45 trennt am Martinstor NICHT. 637 fremde Bilder erkannt (brauchbar).
- Schwabentor (504 Bilder, 310 Paare): 13 Verbindungen, 1 verwechselt (0,399), 1 unklar (0,503), 11 echt (0,58-1,0) - dort deutlich klarer.
- Neu tools/seiten_geometrie.py: jede Gruppe allein rekonstruieren, Sim3-Anteil der gemeinsamen 3D-Punkte je Verbindung; verwechselt nur wenn Geometrie < 0,5 UND Pruefer nicht 'echt'.
- FEHLER (echter Werkzeugfehler, behoben): 4 Mapper gleichzeitig auf EINER Datenbank -> 'SQLite error: database is locked', 12 von 23 Gruppen ohne Modell; ausserdem multiple_models 0 -> nach schlechtem Startpaar nur 3 von 42 Bildern. Jetzt: eigene DB-Kopie je Platz (2,5 GB, 2-TB-SSD), mehrere Anlaeufe, groesstes Modell zaehlt. Nebenwirkung: db_kalib.db der Kette wurde schreibend geoeffnet (mtime 12:56) - Werkzeug arbeitet jetzt nur noch auf Kopien.
- Zeitfresser: Pruefer 0,7 s je Paar (Bild laden 12 MP + LoFTR 1024 px). Verbesserung 36: Bilder einmal verkleinert zwischenspeichern, Stichprobe 24 -> 12 bei eindeutigen Gruppenpaaren (fruehes Ende).

## 13:45 Geometrie-Gegenprobe gemessen: trennt NICHT (Sackgasse in dieser Form); neue Urteilsregel fuer den Pruefer
- seiten_geometrie.py, zweiter Lauf (eigene DB-Kopien): 20 von 23 Gruppen mit Modell; Gruppe 0 (242 Bilder) nicht in 40 min fertig, Gruppe 18 und 36 ohne Modell. 25 Verbindungen gemessen: Sim3-Anteil 0,11-0,58, nur 3 >= 0,5. Auch 1<->16 (Pruefer 0,90, 1239 gemeinsame Punkte) nur 0,30; 6<->30 (Pruefer 0,94) 0,27.
  Ursache: kleine Video-Teilmodelle sind in sich verzogen; starre Passung gelingt auch bei echten Verbindungen nur teilweise. Die 75 % der Handmessung stammten von zwei Haelften einer grossen Gruppe - nicht uebertragbar. -> nicht in die Kette, Werkzeug als Messwerkzeug markiert.
- Neue Urteilsregel in seiten_erkennen.py (statt Median-Schwelle): ECHT, wenn >= 10 % der Stichprobe EINDEUTIG gleich sind (p >= 0,8) - bei echter Verbindung gibt es immer ein paar leichte Paare; VERWECHSELT, wenn fast kein Paar gleich aussieht (90. Perzentil < 0,5); sonst unklar. An den 300 Handpaaren: 0<->1 verwechselt (p90 0,42, 0 % eindeutig), 0-0 / 1-1 / 3-3 echt (25 / 47 / 65 % eindeutig), 0<->3 unklar (7 %); mit 24er Stichproben gleiches Urteil.
- Laeuft: seiten2 (Schwabentor, dann Martinstor mit bereinigter Datenbank db_seiten2.db).

## 14:05 Schwabentor als Wahrheit + GPS-Anker (Nutzer: "muss auch ohne GPS funktionieren, mit GPS noch sicherer")
- Schwabentor, neue Regel, gegen Standrichtungen aus dem GPS-geprueften Modell (konsens_komplett, 466 Bilder): 12 Verbindungen 'echt' - alle 12 richtig (Gruppen 0-60 Grad auseinander). 1 'verwechselt' (9<->10, 41 Paare, p90 0,448) = FEHLALARM (beide Gruppen bei 12/13 Grad); Folge klein (beide haengen ueber Gruppe 1 am Modell). Vom Martinstor-Fall (p90 0,42) nicht unterscheidbar.
- GPS-Anker in seiten_erkennen.py (--objekt): EXIF-GPS -> Standrichtung je Bildgruppe (>= 3 Fotos, 15-300 m, Buendelung >= 0,7); > 120 Grad = verwechselt, < 60 Grad = echt.
  LEHRE: GPS darf ein klares 'echt' des Pruefers NICHT ueberstimmen. Erster Versuch: Gruppen 2<->4 laut GPS 199 Grad auseinander -> 'verwechselt', im Modell aber 60 Grad und Pruefer 54 % eindeutig gleich. Handy-GPS in der Strassenschlucht 5-15 m daneben = zig Grad bei 20 m Abstand. Jetzt: GPS entscheidet nur 'unklare' und vom Pruefer nicht gesehene schwache Verbindungen.
  Ergebnis Schwabentor: GPS loescht zusaetzlich 0<->1 (9 Paare; im Modell 180 Grad = genau die falschen Nord-Sued-Paare vom 15.11.) und 0<->4 (5 Paare, im Modell 114 Grad).
- --pruefer-aus: Pruefer-Ergebnisse einer frueheren seiten.json wiederverwenden (Cache; prueft, dass die Gemeinschaften gleich sind).
- Schnelltest 0 Fehler.

## 15:00 Mapper auf bereinigter Datenbank (Aufloesung 1.0): NOCH VERKLEBT - Ursache gemischte Gruppe am Tordurchgang
- seiten2 Martinstor (neue Regel): 25 echt, 35 unklar, 20 verwechselt (u.a. 0<->1 521 Paare, 0<->4 Drohne 984 Paare); 161 373 Paare geloescht (inkl. 637 fremde Bilder).
- Konsens-Mapper auf db_seiten2.db: 45 min (statt 68; fremde Bilder weg), 1037 Bilder, 0,795 px, 313 unstabil.
- SEITENTEST (neu, Skript blick: mittlere Blickrichtung je Bildgruppe): altes Modell Gruppe 1 (Rueckseite) 3 Grad gegen Gruppe 0 = verklebt. Neues Modell: 6 Grad -> NICHT behoben (Gruppe 1: 93 von 93 Bildern unstabil).
- Ursache: Kette 1 (Fernansichten Sued) - 16 (Clip A_PUR2GXND0, laeuft von Sueden aufs Tor zu, Pruefer 'echt' 0,90) - 3 - 0. Gruppe 3 war GEMISCHT: Nahaufnahmen der Suedwand (A_PUR 12 Bilder) und der Nordwand (eigenes Video 15, Clip jRN8 23) in einer Gemeinschaft; Verwechslungspaare INNERHALB einer Gruppe prueft das Werkzeug nicht.
- Abhilfe: Louvain-Aufloesung 2.0 (Standard): alte Gruppe 3 zerfaellt in jRN8 (+LY0S), eigenes Video, A_PUR; 50 Gruppen >= 12, 118 Verbindungen, 2822 Pruefpaare. Lauf seiten3.
- Pruefer-Tempo: Bild einmal verkleinern bringt wenig (0,78 s, LoFTR selbst ~0,5 s); halbe Genauigkeit 0,49 s, aber 6 von 60 Urteilen kippen -> NICHT benutzt.
- Verbesserung 37: Seitentest 'Blickrichtung je Bildgruppe' als Tor in die Kette (zwei Gruppen, die der Pruefer verwechselt nennt, duerfen im Modell nicht in dieselbe Richtung blicken).

## 16:00 DURCHBRUCH: Martinstor mit BEIDEN Turmseiten (duenne Wolke) - strenge Seitenerkennung + Symmetrie-Drehung
- seiten3 (Aufloesung 2.0): 161 Gemeinschaften, 50 >= 12, 116 Verbindungen: 34 echt, 53 unklar, 29 verwechselt. Mit 'unklar' bleibt alles ein Teil (1334 Bilder) -> Umwege.
- NEU --streng (nur bestaetigte Verbindungen): Teil 0 = 555 Bilder (Nordseite: 4 Clips + 65 Fotos), Teil 1 = 122 Bilder (Suedseite: Clip A_PUR + 68 Fotos/Netzbilder), Teil 2 = 27. Preis: 1265 statt 637 Bilder fallen heraus (u.a. Drohnenclips, Clip jRN8, eigenes Video) - spaeter wieder anhaengen.
- Modelle: Nord Konsens-Mapper 530 Bilder, 88 949 Punkte, 0,88 px, 97 unstabil (~20 min). Sued schrittweise 114 Bilder, 8147 Punkte, 0,87 px (4,4 min CPU). Sued: 45 gepruefte 'Nebenhaus links'-Bilder, 0 'rechts' = rein.
- LoD2-Ausrichtung des reinen Nordmodells: Guete 39 %, zweitbeste 6 %, 'mehrdeutig: False', Massstab 0,0875 (+-0,04 %), Kamerahoehe Median 1,69 m, 491 von 530 plausibel. Vorher (verklebt): 35 %, mehrdeutig. -> Die Verklebung war auch die Ursache der mehrdeutigen Ausrichtung und der roten Lage-Tore.
- Seiten zueinander: echte gemeinsame Punkte gibt es NICHT (beste 'gegenueber'-Lage 21 von 1259 = 2 %; 'geklappt' 277 = 22 %, Rest 0,011 Einheiten = 13 cm, Massstab 0,750).
  IDEE, die traegt: die Verklebung ist selbst eine Messung. Geklappte Lage = wahre Lage um 180 Grad um die senkrechte Turmachse gedreht. Achse = Mitte des LoD2-Objektgrundrisses (0,0);
  Gegenprobe Dach: oberste 3 m der Dachflaeche in A liegen 0,28 / 0,38 m neben der LoD2-Achse. (Erster Versuch 'gedrehte Helm-Punkte von B muessen auf A fallen' war ein Denkfehler: das tun sie gerade in der geklappten Lage.)
- Pruefungen der gedrehten Lage: (1) FLANKENPROBE (unabhaengig, unsymmetrischer Nachbar): Nebenhaus in A auf Flanke +y (1978 gegen 504 Punkte), in B gedreht ebenfalls +y (1040 gegen 126), in B geklappt -y -> gedreht stimmt.
  (2) LoD2-Waende: B gedreht roh Median 1,35 m (34 % < 1 m), nach Feinpassung (Drehung +1,0 Grad, Massstab 0,958 - Massstab verdaechtig, nicht uebernommen) 0,17 m / 87 %; Kontrolle geklappt 0,30 m / 77 % -> LoD2 allein entscheidet die Seite nicht (Strasse spiegelgleich).
  (3) Turmwaende bei x = +4,12 und -4,12 m (Tiefe 8,2 m; LoD2-Sockel 11,6 m), Dachflaechen beider Seiten treffen sich an der Spitze (audit/zweiseitig_turm_1119.png).
- 3D-Seite: https://claude.ai/artifact/She8oNNLBDGohUwFKbmFGh, Bilder audit/zweiseitig_*_1119.png. Skripte tools/versuche/seiten_*_1119.py.
- OFFEN: Genauigkeit vorn/hinten nur ueber LoD2-Achse (+-0,4 m), Massstab B aus Turmwand-Paaren; dichte Wolke beider Seiten; verlorene Clips wieder anhaengen; alles in die Kette (Stufe 'seiten'), Seitentest Blickrichtung als Tor; Schwabentor/Kaufhaus gegenpruefen.

## 16:50 DURCHSICHT der ganzen Kette (Nutzer: "tief durchgehen, Schwachpunkte, Tempo, Qualitaet")
Quelle: Code-Durchsicht durch einen zweiten Durchgang (nur gelesen) + Zeiten aus den Laeufen. [n] = von mir im Code nachgeprueft, [d] = nur aus der Durchsicht.
Gemessene Zeiten Martinstor 1990 Bilder: Merkmale+Paare ~19 min (293 389 Paare), Mapper 68 min (ohne fremde Bilder 45), dichte Wolke 27 min (Fusion 4,5), Tore + 3 Korrekturschleifen 7 min, Vorpruefung aus Cache 6 s; davor seriell Videosuche 77 min (Median 4600 s), Vorpruefung 23 min (ohne Cache), Netzfotos 11 min, Commons 3 min; Seitenerkennung 22-30 min.
STILLE FEHLER
38 [n] wolke_neu_fusionieren.py:104 Neu-Fusion im Korrekturweg ohne RAM-Schutz (keine Teilfusion) - bei > ~200 Bildern OOM, danach laeuft die Kette auf der UNGEFILTERTEN Wolke weiter.
39 [n] iphone_sfm.py:44-45 SfM-Cache gilt als gut, wenn Bildzahl stimmt und irgendein Paar existiert - nach Abbruch mitten im Abgleich rechnet der Mapper auf halbem Paarnetz ("aus Cache").
40 [n] global_mapper_konsens.py:77 Absturz des Bewertungsskripts -> n_reg 0 -> Meldung DATENMANGEL, fertiges Konsens-Modell verworfen, alter langsamer Weg.
41 [d] gesamtkette.py:79 + iphone_sfm.py:115-132: 3-h-Stufengrenze toetet den Rueckfall (schrittweiser Mapper, kein Zwischenstand) - naechster Lauf beginnt denselben Weg von vorn (heute zweimal rc 124).
42 [d] netz_fotos_holen.py:74-75 abgebrochene/gedrosselte Ernte zaehlt 7 Tage als frisch; Suchbegriffe/--max nicht im Schluessel.
43 [d] pipeline_objekt.py:201-203 gescheiterte Bildwahl -> stillschweigend ALLE Bilder (auch unstabile) in die dichte Wolke, kein Eintrag im Bericht; :247 Rueckgabewert des Dichte-Skripts ignoriert.
44 [d] bilder_vorpruefen.py:68 Cache-Schluessel nur Referenz-DATEINAMEN (nicht Groesse/Zeit) - ersetztes Referenzfoto = alte Urteile; ein neues eigenes Foto verwirft dagegen alles (Schrittweite).
QUALITAET
45 [d] 50-%-Regeln (global_mapper_konsens.py:35, pipeline_objekt.py:160) zaehlen ungepruefte Zeitfenster-Videobilder im Nenner: Martinstor 1012 von 1990, Ziel 995 = 17 Bilder Abstand zum falschen DATENMANGEL. -> Nenner = objektnahe Bilder (Seitenerkennung liefert 'fremd').
46 [n] dicht_bildwahl.py:64-65 Zahl der Tiefenkarten-Bilder haengt vom FREIEN PLATTENPLATZ ab (Martinstor 354, 76 wegen Platz gestrichen) - nur im JSON sichtbar. :66-70 Auswahl nimmt die entferntesten Kameras zuerst; :21 'Objekt' = Median aller Punkte (trennt kaum). Berichtigung Punkt 18: die Bildwahl nutzt die Ausrichtung nicht.
47 [n] clips_waehlen.py:42-43 / video_frames.py: je Clip die N SCHAERFSTEN Bilder des GANZEN Clips (bis 300), nicht der Trefferabschnitte aus video_suchen; Unschaerfe-Schwelle 20 statt 60. Martinstor: 84 % der Bilder sind Videobilder, 6 von 12 Clips mit 299-300 Bildern -> Quelle der 637 fremden Bilder.
48 [d] Aufloesung vor der SfM ungemessen gedeckelt: Netzfotos 1600/1920 px, Video 1080p obwohl nach '4k' gesucht wird; SfM 2400 px / 6400 Merkmale ohne Messung.
49 [d] sfm_lod2_ausrichten.py:225-322 Grobsuche um die KAMERAMITTE (nicht das Objekt), Kandidaten < 30 % im Raster ohne Meldung verworfen, Wolkenmitte > 20 m vom Objekt maskiert - bei Durchgangs-Clips kann die richtige Lage vor dem Feinfit herausfallen.
50 [d] Paarliste iphone_sfm.py:18-27: keine Bildsuche; Schluesselbilder gegen ALLES (46 % der Paare Schluesselbild x Foto, 28 % Clip x Clip) - liefert vermutlich die Vorder-/Rueckseiten-Paare; Videonachbarn nach Rang statt Zeit; Dateien mit Endung _2 gelten nicht als Videobild.
TEMPO
51 [n] gesamtkette.py:168-201 ~2 h streng nacheinander VOR der SfM (Commons -> Netz -> Videosuche -> Frames -> Vorpruefung); Videosuche ohne Cache (jedes Mal alle Vorschauen neu, Kandidatenliste ueberschrieben), prueft jedes Bild gegen alle Referenzen ohne fruehes Ende.
52 [d] Inseltor (nur duenne Wolke) laeuft NACH der dichten Wolke und wird per Neu-Fusion repariert; jede --loesung k wiederholt die ganze Grobsuche (115 s, bis 413 s).
53 (ich) Mapper: fremde Bilder vor dem Mapper streichen = 68 -> 45 min (gemessen). Seitenerkennung: Pruefer 0,6-0,8 s je Paar; Gruppen + Urteile zwischenspeichern (--pruefer-aus vorhanden), Stichprobe frueh beenden.
REIHENFOLGE (Vorschlag): erst 38-41 + 43 (stille Fehler, je < 1 h), dann 47 + 45 (Videobilder nur aus Trefferabschnitten; behebt Fremdbilder an der Quelle), dann 51 (Vorstufen parallel + Videosuche-Cache), dann 46/48 mit Messung, 49/50 als Versuche.

## 16:55 Dichte Wolke BEIDER Seiten (tools/dicht_modell.py, Stufe schnell)
- Sued: 74 Bilder (Bildwahl aus 114), 189 518 Punkte, ~8 min. Nord: 217 Bilder (77 unstabile heraus), 1 016 020 Punkte, ~22 min, Fusion am Stueck.
- In Meter (Ausrichtung Nord; Sued ueber geklappte Lage + 180-Grad-Drehung um die LoD2-Achse): Turm 12,5..14 m Umkreis: vorn 529 474, hinten 186 224 Punkte. Turmwaende bei x = +4,15 / -4,15 m. Bild audit/zweiseitig_dicht_1119.png: beide Fassaden vollstaendig (Uhr, Bogen, Ecktuermchen, Helm), Dachflaechen treffen sich an der Spitze, Nebenhaus beidseitig auf derselben Flanke.
- 3D-Seite aktualisiert: https://claude.ai/artifact/She8oNNLBDGohUwFKbmFGh (Version 2, 716 000 Punkte).
- Offen: Flanken (Seitenwaende) leer - niemand fotografiert sie, nur Drohne (Clips fielen in --streng heraus -> Anhang-Lauf); Rueckseite duenner (nur Fotos + 1 Clip).

## 17:15 Nutzer: "nah an beiden fehlen fast alle Bildpunkte", "am Boden fehlen Punkte" - LEERE PUTZFLAECHEN, Ursache Fusion + Fenster (gemessen)
- MEIN FEHLER: Kontrollbilder auf WEISSEM Grund - leere weisse Putzflaechen sahen wie Wand aus. Ab jetzt Punktwolken immer auf dunklem Grund rendern (audit/wand_loecher_1119.png).
- Befund: Wand 10-cm-Zellen belegt vorn 62 % (Putzfeld 8-20 m: 44 %), hinten 56 %. Tiefenkarten der Einzelbilder enthalten den Putz, verworfen wird in der FUSION (min_num_pixels 8 = ungemessene Annahme vom 15.11.).
- Messung Fusion (Rueckseite, 74 Bilder, gleiche Tiefenkarten, je 30-40 s CPU): min_num_pixels 8 / 5 / 3 -> 190 / 380 / 946 Tsd. Punkte; Wand belegt 56 / 66 / 76 %; Sockel 0-3 m 9,6 -> 50,6 Tsd.; Wanddicke 4 / 4 / 5 cm; falsche Punkte im Turminneren je 1,3-1,5 % (Anteil gleich). Weitere Schranken (reproj 3, depth 0,02) bringen nichts. -> min_num_pixels 3 uebernehmen.
- Messung PatchMatch (alle mit Fusion 3): 1600 px Fenster 5 (bisher): Putzfeld 80 %, Wand 76 %, 946 Tsd., 5,2 min. 800 px Fenster 9: Putz 96 %, Wand 80 %, 387 Tsd., 5,0 min, Dicke 6 cm. 1600 px Fenster 11 + filter_min_ncc 0,05: Putz 99 %, Wand 84 %, 1,19 Mio, Dicke 5 cm, falsche 1,2 %, 12,3 min (2,4-fach). Bild audit/putz_vergleich_1119.png.
- Strasse: hinter dem Turm 0 Bodenpunkte (auch mit Fusion 3 nur 2 % der Zellen) - die Bilder blicken nach oben, Strasse kaum im Bild, bewegte Menschen/Bahnen; kommt nur ueber Rundgang-Clips (Anhang-Lauf).
- Verbesserung 54: Fusion min_num_pixels 3 (kostenlos, 5-fache Punktzahl). 55: Fenster 11 + ncc 0,05 als Qualitaetsstufe (2,4-fache PatchMatch-Zeit) - Nutzerentscheidung Tempo/Qualitaet; Zwischenweg pruefen (Fenster 9, window_step 3). 56: Kontrollrender dunkel + Belegungszahl 'Wand-Zellen belegt' als Tor fuer die dichte Wolke.

## 18:15 'Post-its': verlorene Bilder an das Nord-Geruest anhaengen - Pruefung an bekannten Faellen bestanden
- Lauf: colmap mapper --input_path Nordmodell --fix_existing_frames 1, Bildliste = Nord 530 + 676 Kandidaten + 122 SUED-Bilder als Kontrolle (muessen durchfallen). ~75 min CPU (zu lang: Kontrollgruppe und Ketten kosten; Verbesserung 57: Kontrolle nur als Stichprobe, GPU-BA). Ergebnis 998 Bilder: 358 Kandidaten und 110 Kontrollbilder registriert -> die blosse Registrierung trennt die Seiten NICHT (wie bekannt).
- Mass 1 (alle Modellpunkte je Bild): Kontrolle Median 40 % Bildflaeche, echte 82 % - ueberlappt, unbrauchbar. Ursache: angehaengte Bilder triangulieren untereinander neue Punkte.
- Mass 2 (nur Punkte, die das GERUEST schon hatte): Kontrolle 0 % der Bilder mit >= 300 Punkten oder >= 30 % Flaeche (Median 0 Punkte), Geruestbilder 82 % / 84 % -> scharf.
- Wachsen in Runden (tools/versuche/seiten_anhang_wachsen_1119.py; Punkt vertrauenswuerdig ab 2 vertrauenswuerdigen Bildern; Bild angenommen ab 300 solchen Punkten auf 30 % Flaeche): +103, +57, +51, +22, +0 = 233 von 358 Kandidaten angenommen, KONTROLLE 0 von 110 in allen Runden.
  Angenommen: Drohnenclips VEN1 51, RBC7 36, o34426 33, Clips ua1sX 47, FI_JlZ 34, eigenes Video 31. Abgelehnt u.a. Fernclip gjVSpDSd8rU (16, der mit der schiefen Haeuserzeile), Clip jRN8 33, 21 Fotos.
- Fusion min_num_pixels 3 jetzt Standard der Stufe 'schnell' (pipeline_objekt.py, dicht_modell.py, wolke_neu_fusionieren.py). Schnelltest/Regression siehe Commit.
- Laeuft: dichte Wolke Nord mit Anhang (682 Kandidaten vor der Bildwahl), Fenster 11 + ncc 0,05; Anhang Sued.
- Recherche 'Foto 3D Pipeline Stand 2026' (reports/): 12 Massnahmen; Kern: Videobilder nach Bewegung waehlen, fremde Bilder per Bildsuche (MegaLoc MIT) vor dem Abgleich, Paarliste nach Bildart, Spurenzahl im Mapper deckeln; APD-MVS (MIT) fuer Putz; Vereinen getrennter Seiten in der Literatur ungeloest (Cohen 2015).

## 18:45 Nutzer (Seitenansicht der 3D-Seite): "die zwei Seiten verpassen sich, die Turmspitze trifft sich nicht" - richtig, Achse war falsch
- Messung Dachprofil (Mittelstreifen, je Hoehenmeter): beide Dachflaechen laufen UEBER die Drehachse x=0 hinaus (vorn bis x -0,9, hinten bis +0,8) und kreuzen sich bei 48,7 m statt sich oben zu treffen. Helmstange vorn bei x -0,97 / y -0,21, hinten (zurueckgeklappt) -0,78 / -0,31 -> beide Modelle sind sich einig (0,19 / 0,11 m), aber NICHT mit der Kataster-Mitte (0,0).
- Ursache: die LoD2-Ausrichtung des Nordmodells sitzt laengs der Strasse ~0,9 m daneben (Strassenfassaden laufen parallel zur Strasse, Schieben laengs ist schwach bestimmt; LoD2-Turmwand 5,8, Modellwand 4,15). Meine Gegenprobe um 16:00 ("oberste 3 m der Dachflaeche 0,3-0,4 m neben der Achse") war falsch gemessen (Dachflaeche statt Helmstange).
- Abhilfe: Drehachse = Helmstange (Mittel aus vorn und zurueckgeklappt hinten: -0,87 / -0,26), nicht die Kataster-Mitte. Danach: Dachflaechen treffen sich oben und gehen in eine Stange ueber (audit/zweiseitig_spitze_1119.png); Turmwaende +4,15 / -5,85 m = Tiefe 10,0 m (LoD2-Sockel 11,6).
- Lehren: (1) Achse eines drehsymmetrischen Baus aus dem BAU selbst nehmen (Spitze, beide Seiten muessen uebereinstimmen = eingebaute Probe: 0,2 m), LoD2 nur als Gegenprobe. (2) Offen: Nordmodell laengs der Strasse um ~0,9 m schieben (Turmmitte auf LoD2-Mitte) - Verbesserung 58: in der Ausrichtung das Objekt selbst (Turmachse/Wandmitte) als Bedingung laengs der Strasse nutzen.
- 3D-Seite Version 4.

## 19:30-20:30 Startskript, Selbstbau COLMAP, Bibliotheks-Updates (Nutzer: "ein Bash-Skript", "selber bauen, nicht apt", "Libs auf Updates pruefen")
- NEU `0-3d-modell.sh` (Repo-Wurzel) + `tools/start3d.py`: Platte/hp-wmi/Umgebungen pruefen, Fragen, Gesamtkette als Job, farbige Live-Anzeige (Stufen, RAM, VRAM, SSD, Ablageorte), Feinstufe nachts per einmaligem Zeitgeber, am Ende Druckteile. Nur trocken + Anzeige an mt_gk3 getestet, kein echter Start.
- NEU `tools/umgebung/colmap-bauen.sh` (Schalter = build-cuda vom 13.11.) + Paketlisten `tools/umgebung/*.txt`.
- FUND: cuda-toolkit-combo verlinkt CUDA-Bibliotheken aus venv-seg (152) und venv-colmap (20) -> ein torch-Update in venv-seg kann COLMAP still brechen. Bauskript legt CUDA in eigenen Ordner. Bis zur Umstellung: nach jedem venv-seg-Update COLMAP-Probe.
- FUND (Bericht modelle/LIB_UPDATES_2026-11-19.md, nachgeprueft): onnxruntime 1.30.0 Download liefert 404 (COLMAP-Issue #5053) -> jeder frische COLMAP-Bau scheitert. Abhilfe: entpackte Kopie aus build-cuda/_deps nach /media/oem/rcdaten/vorrat/onnxruntime-linux-x64-gpu_cuda12-1.30.0 (604 MB), Bauskript speist sie per FETCHCONTENT_SOURCE_DIR_ONNXRUNTIME ein.
- kornia 0.9.0 -> 0.9.2 in venv-seg (nur kornia, keine Abhaengigkeiten geaendert); Schnelltest 0 Fehler.
- MESSUNG LoFTR fp16 nach kornia 0.9.2 (Release Notes: fp16 repariert), 60 Martinstor-Paare (40 zwischen Gruppen, 20 innerhalb): Zeit 40 -> 28 s (-30 %), LoFTR-Treffer 430 / 434, |dp| Median 0,002, max 0,097; Kippungen an Schwelle 0,8: 0 von 60, an 0,5: 4 von 60 (vorher kornia 0.9.0: 6 von 60). -> fp16 bleibt AUS: die Urteilsregel nutzt p90 < 0,5, Kippungen dort aendern Urteile; 30 % Zeit lohnen das Risiko nicht.
- Offen aus dem Bericht: Testbau COLMAP main in eigenen Prefix auf rcdaten (FlexGlue mit Kovisibilitaet gegen Doppelgaenger-Paare - DINOv3-Lizenz vor Verkauf pruefen; kovarianzgewichtete Rotationsmittelung im globalen Mapper), dann A/B gleiche DB.
- FALLE Feinstufe (Quellcode colmap/mvs/patch_match.cc:154-170): geom_consistency rechnet zuerst UNGEFILTERTE fotometrische Karten, ueberspringt aber vorhandene. Nach Stufe schnell (filter=True) lief eine Feinstufe im selben Ordner still auf gefilterten Karten. Fix: pipeline_objekt.py + dicht_modell.py brechen ab (rc 5), ausser RCPARK_FEIN_KARTEN_NEU=1 (loescht die gefilterten Karten, rechnet neu); start3d.py fragt dafuer beim Planen der Nacht-Feinstufe um Erlaubnis. Schnelltest 0, Regression Martinstor identisch.
- COLMAP-Testbau (main c1b5a967 vom 18.11., ONNX dort schon gespiegelt): Bauskript zweimal korrigiert (Ceres-Untermodul abseil; lib -> lib64 fuer CMake). Ceres gebaut, COLMAP-Bau laeuft (Ergebnis folgt).
- Dichte Vorderseite mit Anhang (mt_dicht_n2, 384 Bilder, Fenster 11, ncc 0,05): 10,1 Mio Punkte (Teilfusion 7 Teile, 318 s).
- 21:xx COLMAP-Testbau FERTIG mit tools/umgebung/colmap-bauen.sh: /media/oem/rcdaten/colmap-test/prefix/bin/colmap = COLMAP 4.3.0.dev0 c1b5a967 (18.11.) mit CUDA; Ceres 07a9526; CUDA aus pip im eigenen Ordner. ONNX 1.32.0 als Vorrat gesichert. Neu verfuegbar: FeatureMatching.type FLEXGLUE (min_covisibility 0,5), GlobalMapper.ra_reweighting {UNIFORM, INLIER_MATCH_COUNT, COVARIANCE}.
- A/B gestartet (Job colmap-ab): Schwabentor db_orig 504 Bilder, view_graph_calibrator + global_mapper: alt / neu / neu mit COVARIANCE. Vergleich schnell gegen fein (Job fein-vgl, Rueckseite 74 Bilder, Fenster 11, ncc 0,05) laeuft.

## 21:10-21:40 seiten_vereinen.py: Achse und Lot korrigiert (offener Punkt von 18:45)
- Befund: Werkzeug setzte die Drehachse 2,1 m neben die Helmstange (Meter-System: +0,98/-1,30 statt -0,87/-0,26). Zwei Ursachen:
  (1) Dachende/'alle hohen Punkte' liegen zur Kameraseite verschoben (abgewandte Dachhaelfte fehlt in jeder Seitenwolke): vorn +0,7/+1,2, hinten +1,4/+1,7 m.
  (2) Kameralot (Bild-x-Achsen) 2,3 Grad verkippt; Wandnormalen der dichten Wolke (Turm 0,8, Haeuser 0,4, alle 0,3 Grad zur LoD2-Ausrichtung) belegen das LoD2-Lot. Bei 60 m Hoehe wanderte die Achse dadurch am Boden um 2 m.
- Fix: `stange()` = oberstes Band (2,5 % H unter 99,9 %) der DICHTEN Wolke; `lot_aus_waenden()` schaerft das Lot aus Normalen senkrechter Ebenen nach (Ausgabe `lot_herkunft`). Dachende nur noch Ersatzweg, als unsicher markiert.
- Ergebnis Martinstor: Achse oben -0,86/-0,20, am Boden -0,92/-0,52 (0,06 m neben der Handmessung), Einigkeit 0,67 % (0,37 m), Turmtiefe 0,18 H = 10,1 m (vorher 7,3; LoD2-Sockel 11,6), Urteil vereint.
- Test `tools/test_seiten_vereinen.py` (synthetischer Turm, gekipptes Startlot) im Schnelltest; Schnelltest 0 Fehler. Lehre: das Kameralot ist eine Startschaetzung - wo eine dichte Wolke da ist, entscheiden die Waende.

## 21:40 Messung schnell gegen fein (Martinstor Rueckseite, 74 Bilder, sonst gleiche Einstellungen, Fusion beide min_num_pixels 3)
- Zeit: schnell 729 s, fein 4766 s (6,5-fach; geometrischer Durchgang ~20 s je Bild).
- Rueckwand (Turmbreite, 3-35 m, Meter-System nach neuer Vereinigung): Punkte 1,19 / 1,23 Mio; Wand belegt (10-cm-Raster) 85 / 83 %; Fehlpunkte hinter der Wand (im Turm) 5,4 / 3,7 %, vor der Wand 0,9 / 0,3 %; Wanddicke (2 x 75-%-Abstand) 16,9 / 13,5 cm.
  Mit COLMAP-Voreinstellung min_num_pixels 5 waere fein nur 0,58 Mio Punkte, 80 % belegt - die Fusion-Einstellung zaehlt mehr als die Stufe.
- Bild audit/fein_vs_schnell_belegung_1119.png: Belegung fast gleich; fein macht die Loecher an Uhr/Fenstern sauberer, schnell hat dort Streupunkte.
- URTEIL: fein bringt ~1/3 weniger Fehlpunkte und 3,4 cm duennere Wand, aber nicht mehr Putzflaeche, fuer 6,5-fache Zeit. Da die Wolke nach der Kernmethode nur Lage-Veto ist, bleibt fein OPTIONAL (Startskript bietet es nachts an), nicht automatisch. Sinnvoll gezielt dort, wo eine Wand aus der Wolke vermessen wird (Wanddicke, Tiefenstufen).
- Zeitgewinn-Idee (nicht gemessen): fein nur fuer die Bilder einer Seite/Wand statt aller.

## 21:30-22:10 A/B globaler Mapper alt (ce2b5ab, Stand 30.10.) gegen neu (c1b5a967, 18.11.), Schwabentor 504 Bilder, gleiche DB
- alt L1_IRLS: 344 s, 494 Bilder, 79 534 Punkte, 1,21 px
- neu L1_IRLS: 422 s (letzter BA-Durchgang 117 s statt 20 s; parallel lief meine CPU-Messung -> evtl. gestoert), 494, 78 808, 1,10 px
- neu Ceres: 385 s, 493, 91 270 Punkte (+15 %), 1,08 px
- neu Ceres + COVARIANCE: 376 s, 493, 78 944, 1,18 px. (Erster Versuch mit COVARIANCE brach ab: "not implemented for the L1_IRLS rotation averaging backend" -> braucht --GlobalMapper.ra_backend CERES.)
- Vorlaeufig: neuer Stand nicht schneller; Genauigkeitsgewichtung bringt hier nichts; Ceres-Drehungsmittelung gibt die meisten Punkte. Rueckprojektionsfehler allein ist kein Genauigkeitsbeweis (Filter verschieden).
- Gegenprobe laeuft (colmap-ab3): alter Bau mit Ceres + neuer Bau L1_IRLS wiederholt ungestoert.
- Gegenprobe (ungestoert): alt + Ceres 402 s, 494 Bilder, 82 854 Punkte, 1,18 px; neu L1_IRLS wiederholt 367 s, 493, 79 000, 1,18 px (erster neu-Lauf 1,10 px) -> Streuung von Lauf zu Lauf so gross wie die Unterschiede der Varianten (Zeit 344-422 s, Punkte 79-91 Tsd., Fehler 1,08-1,21 px).
- Kameralagen gegen alt (Aehnlichkeitstransformation, Anteil der Szenengroesse): alle Varianten Median 0,003-0,035 %, p90 <= 0,1 %; je 3-6 von ~493 Kameras springen > 1 % (in jedem Lauf, auch Wiederholung).
- URTEIL: kein messbarer Gewinn durch neuen COLMAP-Stand, Ceres-Drehungsmittelung oder Genauigkeitsgewichtung an diesem Datensatz. Kette bleibt unveraendert (alter Bau, L1_IRLS). Neuer Bau bleibt als Testbau fuer FlexGlue (nach Lizenzpruefung DINOv3). Die springenden 3-6 Kameras faengt der Konsens-Schnitt ab (zwei Laeufe) - bestaetigt, dass er noetig ist.

## 22:20-23:00 Suedanhang global (Nutzer: "machen wir das mit dem globalen Mapper") + FlexGlue
- Warum lief schrittweise: Anhang an das bestehende saubere Suedmodell (teil1, --input_path, fix_existing_frames) - Koordinatensystem bleibt, Vereinigung gilt weiter. Seit 17:02, nach 5 h 678 von 1339 Bildern.
- Global (Kopie db_sued.db, gleiche liste_sued.txt, 1989 s): 1258 Bilder, 179 330 Punkte, 0,78 px - ABER VERKLEBT: enthaelt alle 530 Nord- und alle 114 Sued-Bilder in einem Modell; Kameras gegen Sued-Modell Median 11 %, gegen Nord 4 % der Ausdehnung daneben. liste_sued.txt enthaelt die Nordbilder (schrittweise mit festem Suedgeruest war das harmlos, global nicht). VERWORFEN. Lehre: global nur mit seitenreiner Bildliste oder mit Zuordnungen, die Querpaare abweisen (-> FlexGlue).
- FlexGlue-Lizenz an der Quelle gelesen (LIZENZ_WERKZEUGE.md): verkaufstauglich.
- FlexGlue braucht ONNX Runtime CUDA 12 (COLMAP-Download gpu_cuda12), Bau hat CUDA 13 -> libcublasLt.so.12 fehlte; CUDA-12-Bibliotheken (cublas, runtime, cudnn 9, cufft) per pip --target in /media/oem/rcdaten/colmap-test/cuda12-onnx (2,2 GB), nur fuer diesen Lauf zugeschaltet.
- Probelauf 20 Paare: Querpaare (Nord gegen Sued, heute verklebt) 0 von 10 bestaetigt, Kontrolle Nord 9 von 10.
- Voller Lauf (6289 Paare) mit Voreinstellung: GPU-Speicher voll (4 Arbeiter x 2 Rechnungen). Neu mit num_workers_per_gpu 1, num_inferences_per_gpu 1, feature_cache_size 96: 5,7 GB, laeuft.
- FlexGlue Speicher: auch mit 1 Arbeiter brachen Paare mit vielen Merkmalen ab (Einzelanforderung 0,9 GB; Median 7467, max 12061 SIFT-Merkmale je Bild; kein Schalter zur Begrenzung). Loesung fuer den Test: DB-Kopie mit 6000 Merkmalen je Bild (k6000.db, COLMAP legt grosse Skalen zuerst ab) + Wiederaufnahme-Schleife. 3,3 GB, 6 Paare/s (6289 Paare 1059 s).
- ERGEBNIS FlexGlue (6000 Merkmale, min_covisibility 0,5): Querpaare (Nord-Sued, mit SIFT alle bestaetigt) 35 von 3289 = 1 %; Kontrolle Nord 1488/1500 = 99 %, Sued 1500/1500 = 100 %. Bestaetigte Punktpaare je echtem Paar Median 450 statt 87 (Nord), 387 statt 50 (Sued) = 5-8-fach SIFT.
- Nutzer: "vergleichen wir beides" -> Nachtkette `rcpark-flexglue-nacht` (Skripte tools/versuche/flexglue_*_1119.*): Stufe 1 = 50 715 SIFT-bestaetigte Paare (~2,3 h) -> Variante TUERSTEHER (SIFT-DB volle Merkmale, von FlexGlue abgewiesene Paare geloescht) und Variante FLEXGLUE (FlexGlue-Zuordnungen) -> je globaler Mapper -> bewerten.py (Nord/Sued je Teilmodell, Sued gegen wahre Lage per vereinen3; am verklebten Suedanhang-Modell geprueft: 18 % daneben -> VERKLEBT erkannt). Danach Stufe 2 = 254 623 von SIFT abgewiesene Paare (~12 h; nur dort kann FlexGlue neue Paare finden) -> FLEXGLUE VOLL -> Mapper -> bewerten.
- Tempo: FlexGlue ~0,17 s je Paar (SIFT-Zuordnung viel schneller); Gewinn nur ueber den Wegfall der Seiten-Handarbeit. Fuer Bauten ohne Doppelgaenger bleibt SIFT allein.

## 20.11. 00:30-01:10 Recherche-Liste abarbeiten (Nutzer: "die ganze Liste wieder abarbeiten ... Sift und FlexGlue vereinigen") - zuerst Punkte ohne GPU
- Punkt 5 Unsicherheit je Kamera: pycolmap.estimate_ba_covariance scheitert am Schwabentor-Modell (Schur-Komplement rangdefizient, auch mit Daempfung, festen Bezugskameras, festen Intrinsiken, nur Posen) - eine schlecht bestimmte Kamera kippt die Gesamtrechnung. Ersatz `tools/versuche/kamera_unsicherheit_lokal_1120.py`: je Kamera lokal (Punkte fest, numerische Jacobi, 6 Posenparameter). Ergebnis Schwabentor (alt, 415 auswertbare Kameras, Spruenge aus 5 weiteren Laeufen): Rangkorrelation Unsicherheit~Sprung 0,43; ALLE 5 Kameras mit Sprung > 0,4 % liegen unter den 10 % unsichersten (2 unter 5 %). Absolutwerte bedeutungslos (Punkte fest), nur Rangfolge. -> brauchbar als Ein-Lauf-Hinweis; Kandidat: unsicherste 10 % aus Wandbild/Kanten-Sweep heraushalten (noch nicht eingebaut, nur 1 Datensatz, 5 Faelle).
- Punkt 8 Rollverschluss `tools/versuche/rollverschluss_pruefen_1120.py`: Martinstor-Nord 11 Clips/365 Nachbarpaare: Drehung~Fehler 0,09 (kein Effekt), Video 1,06 px gegen Fotos 1,11. Schwabentor 7 Clips/210 Paare: 0,52; ruhig (<0,5 Grad/Schritt) 0,36 px, schnell (>2 Grad) 0,85 px, Fotos 1,31 px. URTEIL: messbar, aber Videobilder bleiben genauer als die Fotos - keine Massnahme.
- Punkt 3 LoMa an der Quelle: github.com/davnords/storage Release 'loma' - COLMAP laedt `loma_matcher_*.onnx` (volle Trainingsdaten inkl. ScanNet++/Map-Free); `commercial_loma_*.pt` nur als .pt. LoMa bleibt gesperrt (FlexGlue deckt den Bedarf).
- Punkt 4 SIFT ∪ FlexGlue (`tools/versuche/flexglue_vereinigen_1120.py`: abgewiesene Paare raus, sonst Rohzuordnungen vereinigt, bei Streit gewinnt SIFT, dann colmap geometric_verifier 13 min): an den 6289 Testpaaren Inlier-Median Nord 506 (FlexGlue 450, SIFT 87), Sued 420 (387, 50); Querpaare unveraendert 35. Gleich viele bestaetigte Paare, 9-12 % mehr Punktpaare je Paar als FlexGlue allein. Dritte Variante 'vereint' als Job eingereiht (startet nach der Nachtkette, RAM-Buchung).
- Punkt 1 Schwerkraft je Bild: NEU `tools/schwerkraft_je_bild.py` (Fluchtpunkt der Senkrechten -> 'unten' im Kamerasystem -> pose_priors.gravity; vorhandene GPS-Vorgaben bleiben) + Test im Schnelltest. Pruefung gegen Modelle: Martinstor-Nord (Bezug Wandlot) 190 von 260 Bildern mit Vorgabe, Median 0,75 Grad, p90 5,5, >5 Grad 23, >20 Grad 3; Schwabentor (Bezug Median) 79 von 200, Median 0,70, p90 6,2, >20 Grad 4. Ohne Filter Ausreisser bis 90 Grad (waagerechte Linien) -> Filter Rollen <= 10 Grad, 'unten' naeher an Bild-unten; Videobilder (Median 0,73, p90 3,2) besser als Fotos (1,11 / 9,7). Ein Clip (A_PUR2GXND0) durchgehend 16 Grad in der Neigung daneben (vermutlich Verzeichnung). COLMAP liest die Vorgaben (pycolmap gegengeprueft; Schwabentor hatte 5 grobe EXIF-Vorgaben). A/B am Schwabentor (2 Laeufe mit --GlobalMapper.ra_use_gravity 1 gegen die 6 ohne) eingereiht. RISIKO: Vorgabe ist hart (1 Freiheitsgrad je Kamera) - 12 % Ausreisser > 5 Grad koennten schaden; erst die Messung entscheidet.
- Punkt 6 Bildsuche: NEU `tools/bildsuche_paare.py` (DINOv2-base Apache-2.0, CLS + GeM-Patches, top-k je Bild; MegaLoc wegen ungeklaerter Trainingsdaten nicht). Martinstor 1990 Bilder: top-40 enthaelt nur 26 % der 50 715 SIFT-Paare (top-150: 45 %), aber nach Staerke: >= 500 Inlier 91 % (top-40), >= 200: 68/85 % (top-40/150), >= 50: 40/61 %. URTEIL: als alleinige Paarliste zu luckenhaft (globales Bildmerkmal verliert Ausschnitt-/Zoom-Paare). Nutzen als Vorfilter fuer FlexGlue-Stufe 2: top-150 behaelt 22 074 von 254 623 SIFT-abgewiesenen Paaren (11-fach weniger, ~1 h statt 12 h) - ob FlexGlues NEUE Paare darin liegen, wird an einer Stichprobe aus Stufe 2 gemessen (Nachtkette laeuft dafuer ~1,5 h in Stufe 2, dann Halt zugunsten der eingereihten Tests; Stufe 2 setzt spaeter fort, importer ueberspringt Erledigtes).
- Punkt 9 DA3-BASE (Apache-2.0; Code /media/oem/rcdaten/da3, Zusatzpakete in pkgs/, moviepy als Platzhalter; Versuch `tools/versuche/da3_fuelltiefe_1120.py`): Martinstor Rueckseite, 6 Bezugsbilder je mit 7 Nachbarn, UNSERE Posen+K vorgegeben, 756 px, < 1 s je Satz, ~2 GB GPU. FALLE: DA3 schneidet Bilder verschiedener Groesse mittig zu (K dann falsch) -> auf 1600er Quadrat auffuellen. Ergebnis: Massstab trotz vorgegebener Posen 0,81-0,92 daneben (Angleich noetig); danach rel. Median 1,2-6,4 %, p90 20-172 % (Raender/Himmel/Vordergrund). Loch-Simulation (150 echte 80x80-Bloecke je Bild abgedeckt, aus Ring gefuellt): DA3 0,35-1,36 % Fehler gegen Ebene 0,21-1,93 %, DA3 besser in 32-65 % der Bloecke. URTEIL: kein klarer Gewinn gegen schlichte Ebenenfuellung auf Putz; nur an gekruemmten/gestuften Stellen (2 von 6 Bildern) leicht besser. Nicht in die Kette; Putz bleibt eben per relief_putz.py.
- 02:00 FlexGlue-Nacht Stufe 1 fertig (50 715 SIFT-Paare in 7583 s): FlexGlue weist 6460 davon ab (Tuersteher). Mapper var_tuersteher 1840 s: Hauptmodell 1228 Bilder, bewerten sagt "VERKLEBT" (Sued 18 % neben wahrer Lage) - ABER: Nord- und Sued-Bilder teilen KEINEN 3D-Punkt. Der globale Mapper legt im Ansichtsgraphen verbundene, aber punktlos getrennte Stuecke in EIN Modell mit beliebiger Lage zueinander. FALLE (Lernen, nicht Rueckfall): "ein Modell" heisst beim globalen Mapper nicht "zusammenhaengend".
  NEU `tools/modell_zerlegen.py` (+ Test im Schnelltest): zerlegt nach Punkt-Zusammenhang (Bildpaar verbunden ab 15 gemeinsamen Punkten). Ergebnis zerlegt: Tuersteher 824 Bilder (Nord 483, Sued 0) + 134 (Nord 0, Sued 106) = SAUBER GETRENNT. Gegenprobe frueherer SIFT-Suedlauf (sued_global): zerlegt ab 15 Punkten weiter VERKLEBT (965 Bilder, Nord 497 + Sued 89, Sued 15 % daneben), erst ab 50 Punkten getrennt -> dort echte schwache Bruecke aus falschen Zuordnungen, die der Tuersteher entfernt. Fairer Basislauf var_sift auf genau der Ausgangs-DB eingereiht (flexglue-basis), danach alle Varianten zerlegt bewertet.
  FOLGE fuer die Kette: nach jedem globalen Mapper modell_zerlegen (sonst gelten unverbundene Stuecke als ein Modell, und Massstab/Lage-Tore pruefen Unsinn).
- 02:20 var_flexglue (nur FlexGlue, 6000 Merkmale, nur Stufe-1-Paare) 1543 s: Modell 0 1467 Bilder, 1,71 px; zerlegt 1065 (Nord 495, Sued 0) + 161 (Nord 0, Sued 110) = SAUBER GETRENNT und groesser als Tuersteher (824 + 134).
- 02:25 Nachtkette vor Stufe 2 angehalten (254 623 Paare = ~20 h bei 0,28 s/Paar, haette alle Tests blockiert). Stattdessen Stichprobe 4000 zufaellige Stufe-2-Paare (1112 s): FlexGlue bestaetigt 946 = 23,6 % der von SIFT abgewiesenen Paare (Inlier-Median 52) -> hochgerechnet ~60 000 neue Paare. Bildsuche sagt sie NICHT voraus (top-150: 9 %, top-300: 19 %) -> Bildsuche als Vorfilter fuer Stufe 2 VERWORFEN (Ursache benannt: neue Paare sind gerade die, die global unaehnlich aussehen - Zoom, Jahrzehnt, Licht).
  Querfehler: von 110 Paaren mit bekannter Seite 12 quer bestaetigt (meist 22-49 Inlier). Staerkstes (287 Inlier, openverse_0025 / neu_957f59b875) am Foto angesehen: beide zeigen DIESELBE Seite (Uhrseite) -> Seitenliste fehlerhaft, nicht FlexGlue. 6 % ist Obergrenze. Ab 50 Inliern: echt 66/98, quer 2/12.
  168 039 der Stufe-2-Paare haben mind. ein noch nicht registriertes Bild (Gewinn = neue Bilder). Stufe 2 voll laeuft nach dem Fruehstopp-Test (dessen Faktor entscheidet das Tempo).
- 03:08 var_vereint (SIFT ∪ FlexGlue, FlexGlue-Abgewiesene raus, geometric_verifier neu) 2127 s: Modell 0 1483 Bilder, 1,39 px (FlexGlue allein 1,71); zerlegt 949 (Nord 488) + 154 (Sued 108) + zwei Stuecke je 87 -> SAUBER GETRENNT. Hauptstuecke im Vergleich: Tuersteher 824/134, FlexGlue 1065/161, vereint 949/154. Ein Lauf je Variante - Laufstreuung des globalen Mappers ist gross (Schwabentor: 3-6 springende Kameras je Lauf), Rangfolge erst nach Wiederholung.
- Fruehstopp early_stop_decay 0,3 (Standard 0,5): 6289 Testpaare 1139 s, Quer 35 = 1 %, Kontrolle 1488/1500 + 1500/1500 = identisch zum Standard.
- Fruehstopp early_stop_decay 0,2: 1088 s, Quer 34, Kontrolle 1486/1500 + 1500/1500. URTEIL Punkt 2: weder 0,3 noch 0,2 messbar schneller (~0,17-0,18 s/Paar wie Standard), Qualitaet gleich -> Standard 0,5 bleibt. Zeit steckt nicht im Abbruch, sondern in Merkmalsladen/Netz je Paar.
- Punkt 1 Schwerkraft A/B Schwabentor (`tools/versuche/schwerkraft_vergleich_1120.py`, Kamerazentren per Umeyama auf Lauf 'alt'): ohne Vorgabe 6 Laeufe 493-494 Bilder, Median 0,000-0,022 %, Springer 0-11; MIT Vorgabe (217 von 504 Bildern) 2 Laeufe 482 / 480 Bilder, Median 0,007 / 0,003 %, Springer 10 / 12. Von den fehlenden 12 / 14 Bildern hatten 11 / 13 eine Vorgabe = die ~5 % falschen Vorgaben (> 5 Grad) werfen ihre Bilder raus. URTEIL: Schwerkraft je Bild NICHT in die Kette (richtige Vorgaben bringen nichts messbar, falsche kosten Bilder). Werkzeug bleibt fuer Lot-Pruefungen.
- 03:28 Stufe 2 voll als Job flexglue-stufe2 (~20 h, setzt fort), Basislauf var_sift und PatchMatch-Testbau laufen.
- 04:05 KORREKTUR (Fehlerliste vor Lob): fairer Basislauf var_sift (reines SIFT, GENAU die Ausgangs-DB, 2251 s): Modell 0 1290 Bilder, bewerten "VERKLEBT 18 %" - zerlegt aber 818 (Nord 481, Sued 0) + 111 (Nord 0, Sued 86) = ebenfalls SAUBER GETRENNT. Meine 02:00-Aussage "Tuersteher entfernt die Klebebruecke" ist damit FALSCH fuer diese DB: die Trennung leistet `modell_zerlegen.py`, nicht FlexGlue. (Die echte schwache Bruecke im frueheren sued_global-Lauf stammt aus einer anderen Bildliste.)
  Hauptstuecke Nord/Sued: SIFT 818/111, Tuersteher 824/134, vereint 949/154, FlexGlue 1065/161. FlexGlue-Gewinn = MEHR BILDER (+30 % Nord, +45 % Sued gegen SIFT), nicht Trennung. Reprojektion SIFT 0,81 px, vereint 1,39, FlexGlue 1,71 (FlexGlue-Punkte ungenauer, aber mehr). Je Variante ein Lauf.
- Lage der Stuecke gegen die geprueften Seitenmodelle (Umeyama, gemeinsame Kameras, % der Szenengroesse): NORD alle gleich (Median 0,19-0,24 %, p90 2,4-2,7 %); SUED SIFT Median 0,27 / p90 1,9 %, Tuersteher 0,51 / 9,1 %, vereint 0,45 / 3,1 %, FlexGlue 0,46 / 6,2 %. FlexGlue-Varianten im Sued mit mehr Abweichlern - offen, ob Bezug (teil1, schrittweise) oder FlexGlue-Ungenauigkeit (1,7 px). URTEIL bisher: FlexGlue = mehr Bilder bei gleicher Nord-Lage, Sued-Genauigkeit fraglich; Seitentrennung leistet modell_zerlegen. Vor Kettenaufnahme: Wiederholungslauf + Schwabentor (GPS-Wahrheit, laeuft).
- Gesamtkette `tore()`: zwei HINWEIS-Tore (zaehlen nicht ins Bestanden): `tor_zerfall` (modell_zerlegen, rc 3 = Stuecke ab 10 Bildern) und `tor_gps_seiten` (gps_seiten_pruefen, rc 3 = verdaechtig, rc 2 = zu wenig GPS). Martinstor-Kettenmodell (pipe/sfm/sparse/0): ZERFALL 920 + 88 Bilder (!). GPS-Seiten: Martinstor nur 12 brauchbare GPS-Bilder (Wikimedia, Fernaufnahmen bis 300 m) -> erst Fehlalarm "94 m verdaechtig", darum Mindestens 25 GPS-Bilder im 150-m-Umkreis; Schwabentor 179 Bilder, 4,9 m, GPS-STIMMIG.

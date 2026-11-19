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

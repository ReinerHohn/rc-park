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

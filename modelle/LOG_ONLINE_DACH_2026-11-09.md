# Log: hochliegende Online-Blickwinkel fuer das Kaufhaus-Dach (9.11.2026)
Ziel: Dachabdeckung >15 m (Wolkenkanten 0,20 / B-Konsens 0,54, Lauf kette_foto) steigern. Daten: /media/oem/scan/rc-park_daten/kaufhaus_alle/online_dach/ (Budget 3 GB).

## Quellen
- (1) Wikimedia Commons (API-Suche, Kategorien Historisches Kaufhaus Freiburg, Muensterplatz, Views from Freiburg Minster, Aerial photographs of Freiburg). Je Bild Herkunft/Lizenz/Urheber in `online_dach/herkunft.json` (url, page, lic, artist, date).
  Auswahl nach Titel: Achteckhalle-Serie 2019-04-16 (CC BY-SA 4.0), Dach Historisches Kaufhaus 2022 (CC BY-SA 4.0), Muensterturm-Aussichten 2008/2014 (CC BY-SA 3.0), Staatsarchiv-Freiburg-Luftfotos 1950er (CC BY 4.0, schwarzweiss, Kaufhaus damals Wiederaufbau).
- (2) YouTube (yt-dlp 2026.08.19, nur Test, Standardlizenz = Rechte vorbehalten, NICHT weitergeben): 3 Clips geprueft (DnwP7z19rUw "Beautiful Freiburger Muenster Aerial 4K" Black Forest Stock; LhKaJc3cMh0 "The City in Black Forest" Incredible World; bdXVh1OqLBA UB-Drohne Badische Zeitung). Frames 2 fps, Kontaktbogen angesehen: kein Clip zeigt das Kaufhausdach brauchbar (Muensterturm aus der Ferne / Schlossberg-Panorama / UB-Neubau). Videos und Frames sofort geloescht (eigene Downloads).
- (3) Mapillary: nicht noetig, da (1) Bilder lieferte (Bodenhoehe, bringt keine Dachsicht).

## Ablauf / Befunde (laufend)
- Wikimedia-Original-Downloads (upload.wikimedia.org) lieferten nach ~11 Bildern HTTP 429 (IP-Drosselung, auch fuer Special:FilePath); meine Retry-Schleife hat es verschlimmert. Lehre: 1 Datei je >=20 s, kein Retry-Sturm, Abbruch bei 429.

## Registrierung (SIFT, dann ALIKED+LightGlue)
- 8 Commons-Bilder (od_00..od_07) vorbereitet; EXIF-Brennweite je Bild, je Bild eigene Kameragruppe (`tools/online_dach_registrieren.py`, Sensorbreiten ANNAHME aus Modell). Weitere 3 Bilder (od_08..od_10) kamen wegen HTTP 429 nicht bzw. nicht mehr in die Registrierung (od_09/od_10 = Staatsarchiv 1950er "Durchblick durch Kreuzblume auf Kaufhaus", heruntergeladen, aus Platzgruenden (Budget 3 GB, jede Kette ~1,5 GB) NICHT registriert).
- SIFT: 1/8 registriert (od_01, Boden-Tele 2,8 m Hoehe, Reproj 1,14 px). ALIKED+LightGlue: 3/8: od_00 (Achteckhalle, z=71 m, 1,56 px), od_01 (1,57 px), od_04 (Achteckhalle, z=71 m, 1,27 px). Abgelehnt (zu wenige Korrespondenzen, kein Bodenueberlapp): od_02, od_03 (Alte Wache/Stadtbibliothek, Kaufhaus nicht im Bild), od_05 (Breuninger, Nordseite), od_06, od_07 (Turmblicke ohne Kaufhaus).
- Tor Reproj < 2 px erfuellt, ABER Reproj ist blind fuer Lage (BS1): siehe Overlays.
- Kameradatei sfm/kam_lot2_dach.json = kam_lot2 (440) + 3 (443). Stabilitaetskarten od_00/01/04 in stabil/.

## Messung (Kette `dach`, ab sweep, --vorher v12, zeigen/koerper uebersprungen; Daten kaufhaus_alle/kette_dach)
| Band >15 | kette_foto (vorher) | kette_dach (nachher) |
|---|---|---|
| Abdeckung Wolke | 0,20 (n=1337) | 0,24 (n=1337) |
| Abdeckung B-Konsens | 0,54 (n=1673) | 0,54 (n=1581) |
| Treffer Wolke / B | 0,03 / 0,18 | 0,03 / 0,15 |
Kein Kontrolllauf mit gleichem Aufbau ohne die 3 Bilder: Lauf-Rauschen laut kette_video_alle (0,21) ~ +-0,01-0,02; +0,04 nicht belegt als Wirkung der Webbilder. 0 der Dachkanten (z>=10) in den 3 Bildern sind gegenueber v12 neu (Abstand >0,15 m).

## Overlay-Fehlerliste (Gitter z>=10 m, audit/online_dach/ov_od_01|00|04.jpg, Nummern in .json)
- od_01 (Boden-Tele, Pose glaubwuerdig): Helm links (Nr. 0-11,43): trifft Kanten, ja. Fensterpfosten/Erker (20,28,29,35,36,40,48,53,54...): ja. Traufe/Rinne (12,13,18,38,41,49,50,55): trifft die Rinnenlinie ungefaehr (ja, Versatz ~20-30 px), Gruppe von Doppelkanten (Doppelte). Nr. 34 (Helmfuss rechts): knapp, ja. FEHLEND: Firstlinie, Gauben (4 Stueck), Staffelgiebel-Treppen, Dachflaechenkanten >15 m: im Gitter keine Kante (kein "nein" auf falscher Kante, sondern Luecke) = die gesuchte Dachluecke bleibt.
- od_00 (Achteckhalle, Steilblick): Helm Erker: ja (Spitzenkanten 5,6,34 treffen). Erker-Brustung/Fensterpfosten 17,23,35,38,46,55,59: ja. Nr. 7,12,13,19,24,25,27,40-45,48,51-54,57: NEIN (liegen auf dem Fensterrahmen des Turms links ausserhalb des Kaufhauses = falsche Projektion/Gitterkanten ohne Gegenstueck in diesem Blick; Hinweis auf Posefehler). Nr. 4,16,37: Dachrand hinter dem Erker, nein/unsicher.
- od_04 (Achteckhalle): komplettes Gitter erscheint um ~600 px nach links oben verschoben (auf Tuerrahmen), Kaufhaus-Erker ist rechts daneben: alle Dachkanten NEIN. Pose von od_04 ist falsch trotz 1,27 px (Telebrennweite f=9400 px, Hauptpunkt/Brennweite ANNAHME, Tiefenmehrdeutigkeit). Bild aus dem Bestand nehmen (nicht fuer weitere Laeufe verwenden); od_00 nur bedingt.

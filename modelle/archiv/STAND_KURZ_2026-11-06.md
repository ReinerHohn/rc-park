# Kurzstand Kaufhaus Freiburg - 6.11.2026, 07:35

Ausfuehrliche Berichte: `modelle/STAND_2026-11-06.md` (alle Agentenabschnitte), Versuchsregister CP/CQ, Specs S8/S9/S10.

## Ziel
Druckbares, detailliertes H0-Modell (1:87) des Historischen Kaufhauses, moeglichst automatisch, Geometrie aus Daten.

## Nutzerentscheidungen (gelten)
- Punktwolke ist Basis; LoD2 nur, wo es der Wolke nicht widerspricht (je Flaeche gepruefte Regel).
- Keine Objektnamen/Festwerte im Code; alles aus objekt.json.
- Kaufhaus zuerst, kein Martinstor als Zweitobjekt bis Kaufhaus fertig.
- Formen: erkennen (OWLv2) + Formfamilien mit FREIEN Massen einpassen + Gegenpruefung an der Messung; passt keine Form, bleibt die Messung (6.11. 07:05, ersetzt "keine Vorlagen" vom 5.11.).
- Mehrere Kanten-Ansaetze vergleichen; Entscheidung nach Recherche: Hinweise aller Fotos im 3D-Raum zusammenfuehren (EMAP-Prinzip) statt getrennt abstimmen.

## Bester druckbarer Stand
`/media/oem/scan/rc-park_null/wolke_solid/carv_kh3/wolke_carving_1-87.stl` (tools/wolke_carving.py: Sichtstrahlen-Carving, LoD2 ohne Widerspruch, Nachbarhaus per Grundriss, Glaettung sigma 0,75).
3D-Seite: https://claude.ai/artifact/HdPoLi5E7mvN35aJxhwEHC (Version 18).

| Pruefung | Wert | Soll | |
|---|---|---|---|
| First | 21,34 m | 21,0-21,8 | ok |
| Traufe Nord | 10,97 m | 11,2-12,3 | FEHLER (Wolke 0,7 m unter LoD2, offener Dachbefund) |
| Arkaden Hauptfassade | 4 | 4 | ok, aber fragil (haengt an Glaettung: 3/4/5) |
| Koerper / wasserdicht | 1 / ja | | ok |
| Oberflaeche | treppig, 10-cm-Raster | | Schwaeche |

## Vergleich auf 6 Holdout-Fotos (faires Mass kosten_lr, kleiner = besser)
| Modell | Mittel | Fotos gewonnen |
|---|---|---|
| Generator (null6 s3_v9) | -0,0111 | 4 |
| Carving | -0,0083 | 1 |
| Ebenen-Modell (S8) | -0,0064 | 1 |
Generator hat beste Kantenlage, erfindet aber Formen (Boegen unter Arkaden). Wolken-Koerper ehrlich, Kanten zu ungenau.

## Was gescheitert ist (nicht wiederholen)
- Restfeld auf Generator-Modell (wolke_solid.py): Generatorboegen blieben stehen.
- OpenMVS-Haut auf Carving aufpraegen: Arkade 6, Waende zu duenn (nur ein Versuch, Ursache nicht untersucht).
- Ebenen-Modell mit Zellbelegung (Voxel oder Strahlen-Graph-Cut): Zellen kippen, Kanten ~75 cm daneben.
- rot+gelb als Mass: belohnt verrauschte Netze.

## S9 Ergebnis (6.11.)
Einbau Arkadenboegen auf Carving: kosten_lr Mittel ho -0,0083 (= Basis), ho_rund -0,0090 (Basis -0,0083, Generator -0,0111). Nur 1 Teil echt, 3-7 verworfen. Kleine Verbesserung, Generator bleibt vorn. Daten: /media/oem/scan/rc-park_null/s9/kette2.log

## Laeuft gerade (veraltet, S9 fertig)
- S9 Erkennen + Einpassen, Start Arkadenboegen (Spec `modelle/SPEC_S9_ERKENNEN_EINPASSEN.md`, tools/element_einpassen.py). Synth: Familie immer richtig, Kurve 3-5 cm; Kaufhaus Bogen 1 eingepasst (~4,3 m breit, Scheitel ~3,9 m), von Gegenpruefung abgelehnt (Kantenkontrast zu schwach). Erwartet 30-60 min.

## Naechste Schritte
1. S9-Bericht pruefen (Pruefstand, kosten_lr, Frontbild neben Foto 004), ggf. 3D-Seite aktualisieren.
2. S10 (`modelle/SPEC_S10_KANTEN_ABSTIMMUNG.md`): 4 Kantendetektoren (Helligkeit, Farbe, gelernt, Segmentgrenzen) als weiche Karten -> 3D-Kantenfeld ueber alle Fotos (EMAP, Code/Lizenz pruefen) -> Geraden + Kurven; Wolkenfilter F0-F3 (strengere Fusion, Masken, Lage+Farbe). 2-4 h.
3. Kanten als Zwangslinien fuer S9 und Ebenen-Modell.
4. Nutzer-Video: ablegen als `/media/oem/scan/rc-park_daten/kaufhaus/video/<name>/<name>.mp4`; nullstart zieht Frames jetzt automatisch (seit 6.11. 06:30). Offen: Bildwert-Auswahl nicht angeschlossen, Video-Skala gegen Bodenanker pruefen.

## Betrieb
Datenplatte 17,7 GB frei (Tor 15 GB). Lange Laeufe nur ueber tools/job_start.sh, ein GPU-Job, 15 GB RAM. Keine Commits ohne Auftrag.

## Nutzer-Handyfotos 6.11. (neu)
20 Fotos (nubia Z2462N, 4000x3000, Frontal + Ecke/Erker + Arkaden + Figuren-Zeile, viele Marktstaende/Fahrzeuge davor, 2 unscharf) abgelegt unter `/media/oem/scan/rc-park_daten/kaufhaus/fotos_eingang/handy_2026-11-06/handy_01..20.jpg`. Noch NICHT in die Pipeline eingespeist; Zaehlung am Foto (Arkaden 4, Fenster 5 + 2 Erker, Figuren 4, Gauben 6 im Obergeschoss/Dach) bleibt Aufgabe von foto_zaehlung.py. Bildwert-Filter (S7) vor Aufnahme in die SfM: Unschaerfe (handy_02, _08 sichtbar unscharf) aussortieren.
Serie b (19 Fotos) und c (20 Fotos) 6.11. gleiche Ablage: `fotos_eingang/handy_2026-11-06_b|_c/`. Serie c = Ecksaeule/Gasse, Arkaden-Innenraum mit Gewoelbe, Konsolen, Erker-Unterseite; kaum Marktstaende. Schaerfefilter vor SfM noetig (je Serie ~5-6 unscharf).
Serie d (20 Fotos) 6.11.: fotos_eingang/handy_2026-11-06_d/handy_d_01..20.jpg. Arkaden-Innenseite, Ecksaeule, Erker von unten mit Muenster, Tuer-Portal, Saeulensockel; Schaerfefilter noetig.
Serie e (20 Fotos) 6.11.: fotos_eingang/handy_2026-11-06_e/handy_e_01..20.jpg. Erker-Unterseite/Ecksaeule von Gasse und Arkade, Balkon-Konsolen, Figuren, Drachen-Wasserspeier, Dachspitze mit bunten Ziegeln; Schaerfefilter noetig.
Serie f 6.11.: fotos_eingang/handy_2026-11-06_f/ (14 neue Fotos, 6 Dubletten zu Serie e verworfen). Balkon-Figuren, Obergeschoss-Fenster, Dachgauben, Drachen-Wasserspeier, Hofdurchgang frontal.
Serie g 6.11.: fotos_eingang/handy_2026-11-06_g/ (10 neue, 10 Dubletten verworfen). Arkaden-Gewoelbe, Hofdurchgang, Balkon-Konsolen, Figuren, Dach/Gauben, Erkerturm mit Spitze und Wasserspeier; 3 unscharf (Figuren-Fenster, Balkon, Bogenansatz).
Serie h 6.11.: fotos_eingang/handy_2026-11-06_h/ (18 neue, 0 Dubletten). NEU: Gasse links der Fassade (Seitenwand mit Zinnen/Fenstern von unten, Erker-Unterseite von Seite, Arkadengang Laengsblick, Saeulensockel+Sitzbank). Viele stark unscharf/ueberbelichtet (Himmel), Schaerfefilter noetig.
Serie i 6.11.: fotos_eingang/handy_2026-11-06_i/ (13 neue, 1 Dubletten). NEU: Treppengiebel der linken Seitenwand mit Fenstern (scharf, 3 Standpunkte), Erkerturm von beiden Seiten, Figurenzeile+Wasserspeier von links schraeg, Erker-Unterseite mit Rippen. Foto i_14 = Gasse (unscharf).
Serie j 6.11.: fotos_eingang/handy_2026-11-06_j/ (13 neue, 0 Dubletten). NEU: Dachflaeche von der Strasse schraeg (6 Gauben, Zinnen/Giebelstufen, Schornstein), scharf; Totale Gesamtansicht mit Markt (j_13, Passanten/Marktstand verdecken Sockel).
Serie k 6.11.: fotos_eingang/handy_2026-11-06_k/ (20 neue, 0 Dubletten). Balkon-Konsolen+Figuren von unten (Gewoelbe/Arkade im Vordergrund), Erker-Unterseite mit Rippen und Wappen (mehrere Standpunkte, scharf), Arkadengang-Laengsblick mit Portal+Gitterfenstern, Wandstreifen zwischen Erker und Nachbarhaus, Konsolenreihe der Seitenwand schraeg (Drachen-Wasserspeier), Blick durch Bogen aufs Muenster. Noch nicht registriert.
Serie l 6.11.: fotos_eingang/handy_2026-11-06_l/ (20 neue, 0 Dubletten). Arkaden-Gewoelbe mit Schlusssteinen (3, 2 unscharf), Gitterfenster der Arkadenwand mit Wandleuchte (7, scharf), achteckiger Saeulensockel mit Abplatzungen (10, scharf). Noch nicht registriert.
Serie m 6.11.: fotos_eingang/handy_2026-11-06_m/ (19 neue, 0 Dubletten). NEU: Gassenwand (rote Seitenwand) entlang der Gasse, schraeg von unten, Erker+Wappen+Muenster im Hintergrund; viele stark verwackelt (Wandtextur nur Schlieren), schaerfere: m_09-m_10-Gruppe mit Erker im Bild, Gassen-Totalen mit Lueftungsgitter (3), Arkadengang von innen (letztes, unscharf). Noch nicht registriert.

## Handyfotos: Brennweite/Zoom-Befund (6.11. nachmittags, Register CY/CZ/DA/DB)
- LightGlue-Lauf: 115 von 146 registriert (Gasse h bleibt leer). Posen-Vertrauen (tools/pose_vertrauen.py): 36 sicher (fast nur Serien a,b), 62 unsicher, 17 unbrauchbar, 31 nicht registriert.
- Ursache der Unsicherheit: feste Brennweite f angenommen; f-Fehler 2 % = ca. 0,6 m Tiefenfehler (nicht abstandsabhaengig). Mit richtigem f Posenfehler 0,004-0,03 m (Leave-one-out an 94 Referenzbildern).
- Nutzer hat viele Fotos auf 72-mm-Stufe (Digitalzoom 3x) aufgenommen; EXIF meldet trotzdem 5,25 mm, kein Zoom-Tag. Zwischenliste kaufhaus_handy/zoom_verdacht.json: gezoomt (z ca. 3,3-3,5) j 12/13, i 11/11, g 7/7, f 6/9, e 2/4; a,b,c ungezoomt. Abschlussbericht des Kalibrier-Agenten (aaafbb99d23a1bf2d) steht aus.
- Plan: je Brennweitengruppe eine Kamera (1x und ca. 3,4x), dann k,l,m (59 Fotos) registrieren. Blockiert: Platztor (14 GB frei, Tor 15 GB); Nutzer muss tools/platz_schaffen_2026-11-06.sh starten.
- Nutzer-Einstellungen Nubia: Himmelsverbesserung aus, Beauty aus, Ort speichern an, Wasserzeichen noch offen; Foto 4:3, 24 mm, nie 72 mm. Anleitung: modelle/ANLEITUNG_FOTOS_NUBIA.md.
Serien n, o 6.11. (je 20, 0 Dubletten): fotos_eingang/handy_2026-11-06_n|_o/. Nach den Nutzereinstellungen: GPS-Block jetzt in allen 40 EXIF vorhanden (9 Felder), Brennweite weiter 5,25 mm (Zoom nicht im EXIF; Nutzer sagt 24 mm/1x). n: Gesamtfassade/Dach/Figuren/Arkaden schraeg. o: Arkaden-Gewoelbe, Erker-Unterseite (scharf, viele Standpunkte), Gassenwand (verwackelt) mit Strassenschild "Kaufhausgaesschen", Gassenseite des Erkers mit Fenstern/Laterne, Saeulen+Konsolen. Noch nicht gematcht/registriert; nach dc_einlesen (k,l,m) mitnehmen, Schaerfefilter + Zoom-Pruefung (1x erwartet).
Serie p 6.11. (20, Dubl. siehe Ordner): fotos_eingang/handy_2026-11-06_p/. Arkaden-Gewoelbe/Konsolen/Figuren von unten, Erker mit Wappen und Rippenunterseite aus mehreren Standpunkten (Arkadengang-Blick), Gesamtfassade mit Dach; einige verwackelt. Noch nicht gematcht.
Serie q 6.11. (15): fotos_eingang/handy_2026-11-06_q/. Frontalere Fassadenansichten (Figuren, Balkon, 4-5 Arkaden, Erker mit Wappen/Figuren, Gauben, Zinnengiebel), mehrere fast komplette Totalen mit beiden Tuermchen, Platz-Totale; wenige verwackelt. Noch nicht gematcht.
Register-Vorgriff: n,o,p,q (74 Bilder, Laplace-Schaerfe min 33/med 238) vorbereitet in kaufhaus_handy_npq, Job rcpark-dd_einlesen wartet auf dc_einlesen (6.11. 11:05).

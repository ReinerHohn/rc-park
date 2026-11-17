# Werkzeugkette Miniaturwunderland Freiburg (H0 1:87) - Bestand, Luecken, neue Werkzeuge (17.11.2026)

Auftrag Nutzer: "Alles zusammen, wir muessen geile Tools bauen." Recherche- und Bestandsbericht (Subagent, nur gelesen + Web-Recherche).
Kennzeichnung: [Q n] = Aussage aus Quelle n (Liste am Ende); ANNAHME = eigene Schaetzung, ungemessen; [REPO] = im Repo nachgelesen.

## Kurzfassung

1. Die Gebaeudekette (Fotos -> SfM -> Kanten -> Fassaden/Fenster -> Abnahme -> Bausatz fuer zwei Drucker) ist das reifste Stueck; sie liefert aber EIN Gebaeude in Stunden bis Tagen, nicht ein Viertel.
2. Gelaende kann das Repo schon in drei Bauarten (Laser-Spanten/Egg-Crate, Druck-Hautplatten, Z-Etagen-Stapel), alle aus der Hirschsprung-Zeit in 1:160 - noch nie fuer ein H0-Stadtmodul mit Strassen benutzt.
3. Der Laser (Sculpfun S9, 5,5-W-Diode, Bett 410 x 400 mm, 3 mm Pappel kalibriert) wird bisher nur fuer Gelaendegerueste genutzt, nie fuer Gebaeude, Fenster, Pflaster.
4. Groesste Luecke: es gibt kein "Modul"-Werkzeug, das Grundplatte, Gelaende, Strassen, Gebaeudeplaetze und Randverbinder fuer ein Stueck Freiburg in H0 erzeugt.
5. Zweitgroesste Luecke: Hintergrund- und Massenhaeuser. Ein Viertel hat Dutzende Haeuser; die volle Fotokette ist nur fuer Leitbauten tragbar. Es fehlt eine schnelle Stufe "LoD2 + DOM1-Dach + Fassadenbild als Abziehbild/Laserfassade".
6. Drittens fehlt der Laser als Gebaeudewerkzeug: Fassaden als Schichtsatz (Wand, Fensterrahmen, Gravur) ist bei flachen Putzfassaden vermutlich schneller als Druck (ANNAHME, am S9 zu messen).
7. Farbe ist offen: es gibt "ein Teil = eine Farbe" (druck_farben/druck_farbteile), aber weder AMS-Farbzonen noch Abziehbilder aus den Fassadenbildern, obwohl das feine Fassadenbild (1 cm/px) in H0 etwa 220 dpi entspricht - genau Druckerqualitaet.
8. Licht, Baeume, Figuren, Pflaster/Baechle: im Repo nichts vorhanden; Recherche zeigt, dass Profis hier ueberwiegend Kaufteile und Handarbeit nehmen [Q1][Q2][Q19][Q22].
9. Web-Lage zu Profis duenn: Miniatur Wunderland nennt 3D-Druck (Harz + Filament) als Ergaenzung, nicht Ersatz, und "Kit Bashing" fuer die Speicherstadt [Q1][Q3]; Details zu Laser/Gelaende dort nicht oeffentlich gefunden.
10. Top-5-Vorschlag: modul_platte.py, hintergrundhaus.py, fassade_decal.py, fassade_laser.py, fenster_licht.py (Begruendung unten).

## 1. Bestand je Bereich (was haben wir, Reifegrad)

### Gebaeude aus Fotos - Reifegrad HOCH (Kette steht, an 4-5 Bauten geprueft)
- `tools/gesamtkette.py`: Stufen anlegen ... sfm -> tore -> dach -> bauen -> kanten -> fototor -> fassaden -> fenster -> html -> vergleich; Bericht je Stufe [REPO]. Laut PIPELINE_FASSADEN.md ist ein voller Kettendurchlauf von null "als EIN Befehl" noch offen (AUFGABENLISTE: "LAEUFT/OFFEN Kette ab 'bauen' als ein Befehl").
- `tools/objekt_anlegen.py`: Pflichtrahmen (objekt.json, masstabelle.json, Generator-Rumpf mit beleg()).
- Fassaden: fassade_ortho (5 cm und fein 1 cm), fassade_parsing (OWLv2), fenster_aus_parsing (Sprossen, Raster-Regel), relief_einsatz/relief_putz/steine_generieren/steine_aus_foto, bauteile.py-Katalog, Fenster als echte Loecher.
- Tore: Hoehe gegen DOM1, Umriss-Tor, Grundriss-Tor, Kamera-Plausibilitaet, Foto-F1, foto_diff.
- Geprueft an: Schwabentor (schwab_v3), Nachbarhaus (schwab_nachbar), Historisches Kaufhaus, ober_tvdr (Oberlinden), Martinstor.
- Schwaechen (aus den Dokumenten): Fensterkaesten enthalten Steinrahmen; fassade_tiefe nur 1 von 3 Seiten; Daecher aus Fotos erste Fassung; Sprossen/Nischen-Masse sind ANNAHMEN.
- Grobe Alternativen ohne Fotos: `osm_zu_h0.py` (OSM-3D -> wasserdichter Koerper H0, Dachformen flat/gabled/hipped), `laserdach.py` (Dach als DOM1-Hoehenfeld, 1 m), `lod2_textured.py` (LoD2 mit DOP-Dach und entzerrtem Fassadenfoto als glb, nur Anzeige).

### Druck - Reifegrad MITTEL-HOCH (Werkzeuge da, ein Demodruck Turmschaft)
- `druck_vorcheck.py` (wasserdicht, Ueberhang, Wandstaerke), `druck_teilung.py` (Schnitt an Decken/Gesimsen, Drucklage), `druck_hohl.py` (massiv aushoehlen), `druck_rippen.py` (Innenrippen, Standard 60 mm / 0,9 mm, +18 % Zeit gemessen), `druck_farben.py` (Teil -> Farbe), `druck_farbteile.py` (Steinflaechen als eigene Platten), `druck_zeit.py` (PrusaSlicer-Zeit).
- `bausatz.sh`: grobe Teile MK4S 0,8 mm, feine Teile Bambu 0,4 mm; Bauarten tasche/einsatz.
- Slicer/Start: `prusa_slice.py` (Standard noch 0,4-Duese-Profil!), `bambu_slice.py`, `p1s_print.py` (LAN), `prusa_print.py` (PrusaLink, Zugang laut Memory noch offen).
- Gemessen: Turmschaft 129 x 136 x 102 mm, MK4S 0,8 mm, Schicht 0,4: 1 h 33 min ohne Rippen, 1 h 49 mit Standardrippen [REPO, druck_rippen.py].
- Luecke: kein AMS-Mehrfarbdruck je Flaeche; `druck_zeit.py` rechnet nur mit 0,4-Duese-Standardprofil (Zahlen nur zum Vergleich, steht selbst im Kopf).

### Gelaende - Reifegrad MITTEL (in 1:160 gebaut und teils gelasert, nie H0-Stadt)
- Daten: `dgm_xyz_to_npy.py` (LGL-DGM1-XYZ -> npy), `dom1_kachel.py` (DOM1/DGM1-Hoehe direkt aus GeoTIFF-Kacheln), `hoehe_gegen_dom1.py` (Tor).
- Bauarten: `terrain_eggcrate.py` (1181 Zeilen; steckbares Laser-Kreuzgitter, SVG + GRBL, Tunnel, Gleisbett, Spiel -0,4 mm kalibriert), `laser_relief_kit.py` (Gitter + Uebergangsplatte + Kontur-Stapel mit Duebeln), `terrain_spanten.py` (gedruckte Spanten mit Basiskasten), `terrain_skin_panels.py` (gedruckte Hautplatten aufs Geruest), `terrain_stack_tiles.py` (hohes STL in Bett-Kacheln und Z-Etagen mit Zapfen), `viadukt_gelaende.py`.
- Szenen: hirschsprung_*.py (1:160, OSM-Trasse + DGM1, Tunnel), `modelle/terrain_gen.py` (SRTM 30 m Sockel um Freiburg).
- Stadt: `modelle/laser_grundplatte.py` (OSM-Strassen, Baechle, Footprints als Laser-SVG, deckungsgleich zu LoD2-Druckkacheln) - aber im Massstab der Altstadt-Uebersicht: altstadt_meta.json = 0,812 mm/m (etwa 1:1230, 1,2 m Platte fuer 700 m Radius), NICHT H0.
- Wirklich gebaut: Hoellental-Testset 25 % (1:640), 15 Rippen + 40 Lineale, "Rippen stecken -> Lineale oben aufkleben -> Gips drueber" [REPO modelle/hoellental_geruest_25/STAND.md].

### Laser - Reifegrad MITTEL fuer Gelaende, NULL fuer Gebaeude
- Maschine: Sculpfun S9, Diodenlaser 5,5 W (fabrik_split.py), Bett-Rohling 410 x 400 mm (laser_blank_cut.py), Steuerung MeerK40t (`laser_setup.sh`) und GRBL-G-Code direkt per USB.
- Materialien benutzt/kalibriert: 3 mm Pappelsperrholz (2 Durchgaenge 100 %, 300 mm/min; Schlitz 2,6 mm steckt satt), Konfiguration auch fuer 2 mm Pappel (`tools/s9_laser.conf`); empfohlen 2-3 mm Pappel oder Graupappe, KEIN PVC (Chlorgas) [REPO METHODE_WUNSCH_ZU_MODELL.md]. Karton, MDF, Acryl: im Repo nirgends benutzt (grep ohne Treffer ausser Graupappe-Empfehlung).
- Werkzeuge: `laser_calib.py` (Durchgangszahl, Schlitzbreite), `laser_nest.py`, `laser_pack.py`, `laser_zone_nest.py` (Zonen mit Fingerzinken fuer grosse Blaetter), `laser_blank_cut.py` (je Rohling SVG + G-Code, Schnitt rot / Gravur gruen).
- `fabrik_split.py`: klassifiziert Farbgruppen eines Modells in LASERCUT (grosse gerade Wand) vs DRUCK - ein Ansatz, der nie in die heutige Kette eingehaengt wurde.

### Farbe, Licht, Strasse, Baeume, Figuren - Reifegrad NULL
- Keine Werkzeuge. Einzig `lod2_textured.py` legt Fotos als Textur auf - nur zur Anzeige.

## 2. Was die Recherche ergab (knapp, je Thema)

### Profis
- Miniatur Wunderland: 3D-Druck (Harz und Filament) "ergaenzt den traditionellen Modellbau, ersetzt ihn nicht" [Q1]. Speicherstadt entstand per "Kit Bashing" (Umbau fertiger Bausaetze) [Q3]. Werkstatt-Seite nennt keine Maschinen [Q4]. Mehr war oeffentlich nicht zu finden (Unsicherheit: Videos nicht ausgewertet).
- MinNature Malaysia (gedrucktes Miniaturwunderland): Bauwerke vor Ort fotografieren -> am Rechner modellieren -> Teile drucken, zusammensetzen, streichen, Elektronik/Licht; Bauzeit 2 Tage bis Monate je Bau [Q2]. Das ist unser Weg, nur bei uns automatisiert.
- Andere Grossanlagen (Maerklineum): Styrodur statt Gitter+Gips, weil leicht und fein schnitz-/praegbar [Q5].

### Gelaende aus DGM
- TouchTerrain (offen, Python, auch lokal): DEM -> STL, Kacheln, Sockeldicke, Ueberhoehung; ca. 0,5 mm Sockel unter Tiefpunkten [Q6][Q7]. Ueberhoehung 1,5-5x wird fuer Landschaftsmodelle empfohlen [Q7] - fuer H0-Stadtmodule NICHT sinnvoll: in H0 sind Haeuser und Gleise massstaeblich, also muss auch das Gelaende 1:1 in z bleiben (sonst stehen Haeuser schief zur Strasse). Eigene Folgerung.
- Kontur-Schichten: QGIS GDAL-Kontur -> glaetten/vereinfachen -> je Hoehe eine Datei, Gravurlinie fuer die naechste Lage, Nummern [Q8][Q9][Q10]. Haben wir in `laser_relief_kit.py` schon.
- Fraesen: Python-Kette DEM -> Netz -> G-Code existiert bei Hobbyisten [Q11]; wir haben keine Fraese -> nicht verfolgen.
- Druck-Gelaende: Prusa hat eine H0-Anlage gedruckt (5 Teile, Sekundenkleber, Gleis geklebt/geschraubt), Baeume gedruckt (Fichte FDM, Laubbaum MSLA) [Q12]; ein Studio hat Gips-Gebirge als PLA nachgedruckt, realistischer als Gips [Q13]. Gewichtszahlen fand ich NICHT; Gips duenn wiegt wenig, Unterbau ist das Gewichtsproblem [Q13].
- Fuer Freiburg-Altstadt ist das Gelaende fast eben (ANNAHME: wenige Meter Gefaelle je 100 m), in H0 sind 1 m Hoehe = 11,5 mm. Steil wird es nur am Schlossberg - dort lohnt Egg-Crate + Haut, auf der Strasse reicht eine Platte mit Hoehenstufen.

### Laser im Gebaeudebau
- H0-Lasercut-Bausaetze sind ueblich aus durchgefaerbtem Karton (Joswood) [Q14][Q15]; Micro Welten: 1 mm Karton fuer Wand, Buchenfurnier fuer Balken, Fenster als PVC-Folie [Q16]. Auhagen legt Lasercut-Kartonteile (Fenstergitter, Tore, Gelaender) zu Kunststoffbausaetzen [Q17]; gelaserte Fensterfolie wird gelobt [Q18].
- Architekturmodellbau: geschichtete Lagen mit Zapfen/Stiften ausrichten, Acryl oder Acetat hinter der Oeffnung als Glas [Q20].
- Diodenlaser und Karton: weisse/helle Oberflaechen reflektieren, Schneiden duennen Kartons mit 5,5 W braucht langsam + Air Assist, Werte stark streuend [Q21]. Klares Acryl schneidet ein blauer Diodenlaser praktisch nicht (Fachwissen, nicht per Quelle geprueft = ANNAHME) -> Fensterglas als Folie von Hand oder Plotter.
- Was schneller ist als Druck, belegt keine Quelle. ANNAHME: eine flache Putzfassade 10 x 12 m (H0 115 x 138 mm) mit 12 Fenstern in 1 mm Graupappe ist in Minuten geschnitten, gedruckt in 0,4 mm etwa 1 h; zu messen mit `laser_calib.py` + `druck_zeit.py`.

### Fotos -> 3D (Stand der Technik, Lizenz)
- COLMAP: BSD; GLOMAP (globaler Mapper) BSD-3 laut Aggregator, laut Sekundaerquelle ab COLMAP 3.12/4.0 integriert [Q23][Q24] - deckt sich mit unserer Nutzung.
- VGGT: Code seit 29.07.2025 kommerziell nutzbar (ohne Militaer), aber NUR Checkpoint "VGGT-1B-Commercial"; der Original-Checkpoint bleibt nicht-kommerziell [Q25]. MapAnything: Apache-Checkpoint `facebook/map-anything-apache`, der andere CC-BY-NC; eingebundene Fremdbibliotheken behalten ihre Lizenz [Q26]. MASt3R/DUSt3R: keine offizielle Lizenzaussage gefunden, NAVER-Hinweis auf nicht-kommerzielle Trainingsdaten [Q27] -> nur Test.
- Gaussian Splatting -> Netz: 2DGS/MILo/Original-3DGS-Code unter Inria-"Gaussian-Splatting License" = nur nicht-kommerziell [Q28][Q29]; PGSR "other"-Lizenz, ungeprueft [Q30]. gsplat (nerfstudio) ist nach meinem Wissen Apache-2.0 - NICHT in dieser Recherche bestaetigt. Deckt sich mit LIZENZ_WERKZEUGE.md (2DGS/MILo nur Test).
- Fuer Fassadendetail lohnt laut unserem eigenen Register vor allem Fotokante + Messen (KERNMETHODE); Splatting-Netze waeren hoechstens Pruefreferenz. MapAnything (Apache) steht schon als Aufgabe 4 offen.

### Farbe
- Wasserschiebebilder: Laserdrucker-Decalpapier klar und weiss erhaeltlich; Heimdrucker koennen kein Weiss und keine deckenden Farben [Q31]; Schritte: ausschneiden, 1-2 s Wasser, aufschieben, 10-15 min trocknen, glatte Schnittkante sonst loest es sich [Q32]. Profi-UV-Decals 1440 x 1200 dpi, Film ca. 7 Mikrometer, ab 33 EUR je A4 (Stand 2021) [Q32].
- AMS: Werkzeuge, die eine Textur (GLB/OBJ) auf 2-8 Filamentzonen abbilden und 3MF fuer Bambu Studio schreiben [Q33]; Blender-Addon "AMS Splitter" (UV + Base-Color-Textur -> Materialbereiche) [Q34]. HueForge-Flachbilder: 0,08-mm-Schichten, Farbmischung durch Schichtdicke [Q35]. Lizenzen dieser Fremdwerkzeuge ungeprueft -> Prinzip nachbauen, nicht einbinden.

### Strasse, Pflaster, Baeume, Figuren, Licht, Module
- Pflaster: ueblich Fertigplatten (Noch, Faller, Juweela; ca. 10-17 EUR) oder Silikonformen fuer Giessmasse [Q19]; Laser-Gravur von Pflaster: keine Anleitung gefunden. Freiburger Rheinkiesel-Mosaike und Baechle sind Alleinstellung - da lohnt ein eigenes Werkzeug.
- Baeume: Profis drehen Draht (Blumendraht, Staerke 20-26 fuer H0, bis ~300 Faeden 0,35 mm), Ueberzug Leim/Gips, Flock, matt versiegeln [Q22]; Prusa druckt Baeume (Fichte FDM, Laubbaum Harz) [Q12]. Gedruckte Staemme: keine Quelle.
- Figuren: ueberwiegend Kauf (Preiser u. a., auch Harzdruck) [Q36]; Formlabs: Harzdruck fuer feine Figuren, FDM braucht Stuetzen [Q37]. Wir haben keinen Harzdrucker -> kaufen.
- Licht: Lichtkaesten hinter einzelnen Fenstern (gedruckte Lightbox, 5050-LED passt) [Q38]; Lichtdurchschlag durch duenne Waende mit Abdeckfarbe/Schaum/Innenfotos verhindern [Q39]; Steuerung Arduino mit Treibern [Q40]. WS2812 speziell: keine Quelle gefunden.
- Module: FREMO-Normen (H0-Europa, FREMO87) sind Vereinsstandard mit genormten Stirnbrettern [Q41][Q42]; H0m: Breite mind. 400 mm, Bohrungen im 50-mm-Raster [Q43]; Spur 0: 600 mm Standard [Q44]. Exakte H0-Europa-Masse habe ich NICHT gelesen. Fuer ein Stadt-Wunderland ohne Vereinsanschluss reicht eine eigene Norm (Vorschlag unten).

## 3. Luecken (ehrlich, nach Gewicht)

1. Kein Modulbegriff: kein Werkzeug fuer "UTM-Rechteck -> H0-Platte mit Gelaende, Strassen, Bordsteinen, Baechle, Gebaeudeplaetzen, Randverbindern". `laser_grundplatte.py` ist im falschen Massstab und nur 2D.
2. Massenhaeuser: die Fotokette braucht je Bau viele Stunden Rechen- und Pruefzeit; fuer ein Viertel fehlt eine schnelle, ehrliche Stufe (LoD2-Koerper + DOM1-Dach + Fassadenbild + automatische Fenster), klar als "Hintergrund" markiert.
3. Laser nur fuer Gelaende: keine Fassaden, Fenster, Gesimse, Dachziegel, Pflaster am Laser; `fabrik_split.py` ist verwaist.
4. Farbe: keine Abziehbilder, keine AMS-Zonen, keine Farbmessung fuer Daecher (druck_farben.py: "Dachfarbe waehlen" = ANNAHME).
5. Licht: Fenster sind echte Loecher (gut), aber kein Lichtkasten, kein Kabelweg, keine Innenschwaerzung.
6. Strassenraum: Pflaster, Baechle, Bordsteine, Strassenbahngleise (Freiburg!), Brunnen - nichts.
7. Baeume/Gruen: nichts; Position und Kronengroesse waeren aus DOM1 minus DGM1 (nDOM) ableitbar (ANNAHME, nicht geprueft).
8. Druckprofil MK4S 0,8 mm fehlt in `prusa_slice.py`/`druck_zeit.py` (beide auf 0,4 mm) -> Druckzeiten fuer grobe Teile sind nur Vergleichszahlen.
9. Kein Gewichts-/Stabilitaetsnachweis fuer Module (Durchbiegung, Gewicht pro m2).
10. Datenhaltung: Hirschsprung-Dateien mit _CHECKPOINT/_STAND-Kopien in tools/ (Altlasten, nicht generisch).

## 4. Vorschlag neue Werkzeuge (priorisiert nach Nutzen / Aufwand)

Aufwand in Arbeitstagen fuer mich (Claude) inkl. Test = ANNAHME. Maschinen: P = Prusa MK4S 0,8, B = Bambu P1S 0,4 (+AMS?), L = Sculpfun S9.
Alle neuen Bauteile als generische Funktionen (Regel: tools/bauteile.py bzw. eigenes Modul), jede Stufe mit Abnahmebild.

### Prioritaet 1 - `tools/modul_platte.py` (Stadtmodul-Grundplatte)
- Zweck: aus einem UTM-Rechteck ein H0-Modul: Gelaendeoberflaeche (DGM1, z 1:1, keine Ueberhoehung), Strassen/Plaetze/Baechle/Gehwege aus OSM (+ spaeter ALKIS/Stadt-Daten), Gebaeudeplaetze als flache Taschen mit LoD2-Grundriss und Hausnummer-Gravur, Randverbinder.
- Eingabe: Rechteck (UTM, Drehung), Modulmass (Vorschlag eigene Norm: 600 x 400 mm Grundmass, Raster 200 mm, Rand-Bezugshoehe = DGM am Modulrand, 2 Fluchtstifte + 2 Schrauben je Stirnseite), Bauart (druck | laser | egg-crate).
- Ausgabe: Druckkacheln (STL je Bett, Zapfen an den Fugen - wiederverwendet `terrain_stack_tiles.py`/`terrain_skin_panels.py`) ODER Laser-Lagen (Grundplatte, Strassenlage, Gehwegkante als Lage 1 mm Graupappe, Gravur Pflaster; wiederverwendet `laser_relief_kit.py`, `laser_blank_cut.py`), Uebersichtsbild Modul neben Orthofoto/Stadtplan, belegungsplan.json (welches Haus steht wo).
- Maschine: L fuer flache Lagen und Rahmen, P fuer Gelaendehaut (Schlossberg), B fuer Bordstein-/Baechle-Einsaetze.
- Aufwand: 3-4 Tage. Risiko: DGM1 hat 1-m-Pixel = 11,5 mm in H0 -> Bordsteine/Stufen sind darin nicht sichtbar, muessen aus OSM-Linien kommen; Gebaeudesockel liegen auf schraegem Grund (Haus braucht Sockel-Ausgleich = Schnittstelle zur Gebaeudekette, `rahmen.gelaende`).

### Prioritaet 2 - `tools/hintergrundhaus.py` (schnelles Haus fuer Massen)
- Zweck: jedes LoD2-Gebaeude im Modul in Minuten als ehrliches Grobhaus: LoD2-Koerper, Dach aus LoD2 (bei Widerspruch zu DOM1 `laserdach.py`), Fenster aus dem Fassadenbild (vorhandene Kette fassade_ortho -> fassade_parsing -> fenster_aus_parsing, aber ohne SfM-Pflicht: Fotos per `seiten_luecken.py`/`fassade_ein_foto.py`), Wand duenn + Rippen (`druck_rippen.py`), Kennzeichnung "HINTERGRUND, Reifegrad 1" in objekt.json.
- Eingabe: belegungsplan.json aus modul_platte, LoD2-GML, DOM1, vorhandene Fotos.
- Ausgabe: je Haus STL + Fassadenbild-Kacheln (fuer Prioritaet 3) + Abnahme-Kurzbild (Modell neben Foto, Pflicht nach CLAUDE.md).
- Maschine: P (Koerper), optional L (Fassadenplatten, Prio 4).
- Aufwand: 3 Tage (Bausteine da, Arbeit = Verkettung + schnelle Abnahme). Risiko: KERNMETHODE verlangt Fotokanten; ein Haus ohne Kantenstufe darf nicht als "passend" gemeldet werden -> klar als Hintergrund kennzeichnen und Foto-F1 trotzdem rechnen. Fotos fuer Seitengassen fehlen oft (foto_auftrag.py).

### Prioritaet 3 - `tools/fassade_decal.py` (Fassadenbild als Abziehbild/Klebedruck)
- Zweck: das vorhandene feine Fassadenbild (1 cm/px = 0,115 mm in H0, rund 220 dpi) entzerrt, farbkorrigiert, massgenau als Druckbogen fuer Wasserschiebebild (Laserdrucker) oder Klebefolie; Fenster ausgespart oder abgedunkelt; Passmarken; Schnittlinie als Laser-/Plotter-SVG.
- Eingabe: `<objekt>/fassaden/*_fein.*`, Fenster aus `fenster_auto.json`, Wandrahmen.
- Ausgabe: A4-PDF in 1:87 (600 dpi Raster), SVG Schnittkontur, Pruefbild Abziehbild auf Render.
- Maschine: Bueroldrucker (Laser, weisses Decalpapier weil Heimdrucker kein Weiss kann [Q31]), L oder Schere fuer die Kontur.
- Aufwand: 1-2 Tage. Risiko: Schatten/Verdeckung im Fassadenbild (Autos, Baeume) werden mitgedruckt -> Maske/Retusche noetig; Lizenz der Fotos (LIZENZ_BILDER.json, Fremdfotos nur privat); Glanz/Farbtreue des Laserdrucks ungeprueft.

### Prioritaet 4 - `tools/fassade_laser.py` (Fassade als Laser-Schichtsatz)
- Zweck: flache Fassaden als 2-4 Lagen: Lage A Wand 1 mm Graupappe mit Fensterloechern, Lage B Gewaende/Gesimse 0,5-1 mm, Lage C Fensterrahmen mit Sprossen (Karton 0,3-0,5 mm), Gravur: Quaderfugen aus `steine_aus_foto.py`, Fachwerk, Putzkanten. Optional Fensterfolie von Hand. Ersetzt `fabrik_split.py` durch Klassifizierung je Wand (eben + wenig Relief -> Laser).
- Eingabe: Generator-Fenster/Bauteile, Fassadenbild, Wandrahmen.
- Ausgabe: SVG je Lage (Schnitt rot / Gravur gruen wie `laser_blank_cut.py`), Nesting auf 410 x 400, Montagebild, Zeitvergleich gegen Druck.
- Maschine: L.
- Aufwand: 2-3 Tage + Materialtests (`laser_calib.py` um Karton/Graupappe erweitern). Risiko HOCH: H0-Sprosse 3 cm real = 0,34 mm Modell - am Rand dessen, was Schnittfuge und Abbrand einer 5,5-W-Diode in Karton stehen lassen (ANNAHME, Testschnitt Pflicht); heller Karton reflektiert/schneidet schlecht [Q21]; Brandraender verfaerben.

### Prioritaet 5 - `tools/fenster_licht.py` (Licht hinter Fenstern)
- Zweck: aus `fenster_auto.json` je Fenster(gruppe) einen Lichtkasten (innen weiss, aussen schwarz, LED-Sitz 5050 oder 2020), Innenwand-Blende gegen Durchscheinen, Kabelkanal zum Sockel, Plan je Haus (welche Fenster leuchten, Kette in Reihenfolge, Strombedarf).
- Eingabe: Fensterliste, gedrucktes Haus (Wanddicke aus bausatz.sh).
- Ausgabe: Lichtkasten-STL (B), Verdrahtungsplan (SVG/JSON), Steuerdatei fuer Mikrocontroller (ANNAHME WS2812/Arduino; keine Quelle fuer WS2812 im H0-Haus gefunden).
- Maschine: B (schwarzes Filament).
- Aufwand: 1-2 Tage. Risiko: Waerme gering bei LED; Montage durch duenne Wand (1 mm) - Rippen stoeren Kastenlage -> Kollisionspruefung mit `druck_rippen.py`.

### Prioritaet 6 - `tools/strasse_pflaster.py` (Pflaster, Baechle, Bordsteine, Gleise)
- Zweck: Strassenflaechen als Lasergravur (Kopfstein-/Plattenmuster nach OSM `surface`, Bordstein als 1-mm-Lage) oder als duenne Druckplatten mit Relief; Baechle als Rinne mit Gefaelle (DGM) und Giessharz-Wasser; Strassenbahn-Rillengleis-Freiraum.
- Eingabe: Modul-Strassenlagen, OSM, Fotos fuer Muster (Rheinkiesel-Mosaik ANNAHME nur grob).
- Ausgabe: SVG Gravur/Schnitt, optional STL.
- Maschine: L (Gravur Graupappe/Pappel), B fuer Rinnen.
- Aufwand: 2 Tage. Risiko: Gravur auf Pappe wirkt evtl. zu weich; Kaufplatten [Q19] koennten guenstiger sein -> erst Probe gegen Noch/Juweela-Platte vergleichen.

### Prioritaet 7 - `tools/modul_rahmen.py` (Kasten, Spanten, Verbinder)
- Zweck: Modulkasten aus 3-mm-Pappel (L) oder gedruckten Spanten (`terrain_spanten.py`), Stirnbretter mit Bezugshoehe, Fluchtstifte, Kabeldurchlaesse, Beine/Tisch-Aufnahme; Gewicht und Durchbiegung grob rechnen.
- Aufwand: 2 Tage (Egg-Crate-Code vorhanden). Risiko: 3 mm Pappel fuer 600-mm-Spannweite zu weich (ANNAHME) -> Rahmen ggf. aus Holzleisten vom Baumarkt, Laser nur fuer Spanten.

### Prioritaet 8 - `tools/baeume_aus_ndom.py`
- Zweck: Baumstandorte und Kronenhoehe/-durchmesser aus DOM1 - DGM1 (+ OSM `natural=tree`, ggf. Baumkataster Freiburg - Verfuegbarkeit ungeprueft); Ausgabe Stueckliste (Hoehe in H0, Kronenform) + gedruckte Stammrohlinge oder Drahtplan.
- Aufwand: 1-2 Tage. Risiko: Baeume und Haeuser im DOM1 vermischt; gedruckte Staemme ohne Vorbild in der Literatur.

### Prioritaet 9 - Druckprofile 0,8 mm + AMS-Zonen (`prusa_slice.py`, `druck_zeit.py`, `druck_farben.py` erweitern)
- Zweck: echte Zeiten fuer grobe Teile (MK4S 0,8, Schicht 0,4); Farbzonen statt Farbteile fuer kleine Teile auf B (falls AMS vorhanden - NICHT geklaert); Dachfarbe aus DOP-Orthofoto statt ANNAHME.
- Aufwand: 1 Tag. Risiko: gering; Werkzeugaenderung = Schnelltest + Regression Pflicht.

### Bewusst NICHT vorgeschlagen
- Figuren selbst drucken (kein Harzdrucker; Kauf billiger) [Q36][Q37].
- Fraesen (keine Maschine) [Q11].
- Gaussian-Splatting-Netze als Geometrie (Lizenz nicht-kommerziell [Q28], KERNMETHODE verbietet Form aus Wolke/Netz).
- Ueberhoehung im Stadtmodul (zerstoert Massstab zwischen Haus, Strasse, Gleis).

## 5. Durchgehender Ablauf: ein Stadtviertel-Modul vom Foto bis zur fertigen Platte

Beispiel ANNAHME: Modul 600 x 400 mm = 52 x 35 m in Wirklichkeit (z. B. Oberlinden am Schwabentor - Schwabentor, schwab_nachbar und ober_tvdr sind schon gebaut).

1. Auswahl: Rechteck auf dem Stadtplan festlegen; `modul_platte.py --plan` listet alle LoD2-Gebaeude im Rechteck mit Reifegrad (Leitbau mit Fotokette / Hintergrund / fehlt), DGM-Gefaelle, Strassen (OSM). Ergebnis belegungsplan.json + Bild.
2. Fotobedarf: `tools/foto_auftrag.py` fuer alle Haeuser ohne Fotos je Seite; Nutzer fotografiert, `tools/foto_check.sh` sofort pruefen. Freie Quellen vorher: `seiten_luecken.py --download --holen`.
3. Leitbauten (1-3 je Modul): volle Kette `gesamtkette.py` (SfM-Kameras, Tore, Kanten, Foto-F1, foto_diff, Fassaden, Fenster), `bauen_abnehmen.sh`, Bild Modell neben Foto. Unveraendert nach CLAUDE.md.
4. Hintergrundhaeuser: `hintergrundhaus.py` fuer den Rest; jedes Haus mit Kurzabnahme und Kennzeichnung Reifegrad 1.
5. Platte: `modul_platte.py --bauart laser` (eben) bzw. `--bauart druck` (Hang); Gebaeudesockel-Hoehen aus dem DGM an die Hausgeneratoren zurueckgeben (gleiche `rahmen.gelaende`-Quelle wie `hoehe_gegen_dom1.py`), damit Haus und Platte ohne Spalt passen.
6. Strassenraum: `strasse_pflaster.py` (Gravur, Bordsteinlage, Baechle-Rinnen).
7. Druckvorbereitung je Haus: `druck_vorcheck.py` -> `bausatz.sh` (P grob, B fein) mit `druck_rippen.py`/`druck_hohl.py`; `fenster_licht.py` legt Lichtkaesten dazu; `druck_zeit.py` Summe fuer das Modul.
8. Laser: `fassade_laser.py` fuer flache Fassaden (wo schneller), Platten-/Strassenlagen, Modulrahmen (`modul_rahmen.py`); Nesting `laser_zone_nest.py`/`laser_blank_cut.py`; vorher `laser_calib.py` je neuem Material.
9. Farbe: Grundfarben per Filament (ein Teil = eine Farbe), Fassadenbild als Abziehbild (`fassade_decal.py`) auf glatte Putzflaechen, Rest von Hand; Daecher nach DOP-Farbe.
10. Montage: Rahmen -> Platte -> Strassenlagen -> Haeuser auf Sockeltaschen -> Licht verdrahten -> Baeume (Stueckliste aus `baeume_aus_ndom.py`) -> Figuren (Kauf).
11. Abnahme Modul: Uebersichtsfoto des fertigen Moduls neben Orthofoto/Strassenfoto aus gleicher Blickrichtung (Erweiterung `modell_neben_foto.py` auf Modulebene), Fehlerliste je Haus, Realitaets-Prozent.

Groessenordnung ANNAHME: H0 macht Freiburg gross - die Altstadt (ca. 700 m Radius, wie altstadt_meta.json) waere rund 16 m Durchmesser. Ein Wunderland braucht also eine Auswahl verdichteter Szenen, nicht die ganze Stadt 1:1.

## 6. Fehlerliste und Unsicherheiten dieses Berichts

- Profi-Arbeitsweise Miniatur Wunderland: oeffentlich kaum belegt; Werkstatt-Seiten nennen keine Maschinen [Q1][Q4]; das 3D-Druck-Video wurde nicht ausgewertet.
- Kein Beleg gefunden fuer: Laser schneller als Druck bei H0-Fassaden, Sprossenbreite in gelasertem Karton, Gewicht pro m2 gedruckter Gelaendehaut, WS2812 in H0-Haeusern, gedruckte Baumstaemme, Laser-Pflastergravur. Alles dazu oben ist ANNAHME und braucht Probeteile.
- Viele Quellen sind Haendlerseiten/Foren (Ebay, Hersteller-PDFs, LightBurn-Forum) - als Hinweis, nicht als Messwert.
- Lizenzen: MASt3R ungeklaert; gsplat-Apache nur aus meinem Vorwissen; PGSR "other" ungelesen; AMS-Konverter/AMS Splitter ungeprueft. Vor Einsatz LICENSE selbst lesen (Regel LIZENZ_WERKZEUGE.md).
- FREMO-H0-Europa-Modulmasse nicht gelesen; Vorschlag 600 x 400 mm ist eigene Setzung.
- Bestand: Werkzeugkoepfe nur per head gelesen, nicht ausgefuehrt; Reifegrade sind meine Einschaetzung aus Doku und Docstrings. Ob ein AMS am P1S haengt, steht im Repo nicht (nicht gefunden).
- Aufwandsschaetzungen in Tagen sind ANNAHMEN.

## 7. Quellen

- [Q1] Miniatur Wunderland, 3D-Druck-Special: https://www.miniatur-wunderland.com/news/wunderland-special-alle-infos-zu-unserem-3d-druck
- [Q2] 3Dnatives, MinNature Malaysia: https://www.3dnatives.com/de/minnature-malaysia-3d-2802171/
- [Q3] Miniatur Wunderland, Speicherstadt (Kit Bashing): https://miniatur-wunderland.com/discover-wunderland/technologies/model-building/model-building-highlights/speicherstadt
- [Q4] Miniatur Wunderland, Modellbauwerkstatt: https://www.miniatur-wunderland.com/discover-wunderland/technologies/others/our-workshops/our-model-building-workshop
- [Q5] Maerklin Magazin Leseprobe 08/2021 (Maerklineum, Styrodur): https://www.maerklin.de/fileadmin/media/newsletter/webnews/2021/maerklin-magazin-leseprobe-aug21.pdf
- [Q6] TouchTerrain (GitHub): https://github.com/ChHarding/TouchTerrain_for_CAGEO
- [Q7] EduTech Wiki, 3D printing of DEMs: https://edutechwiki.unige.ch/en/3D_printing_of_digital_elevation_models
- [Q8] RUC Fabcloud, Topographic map (Laserschichten): https://fabcloud.ruc.dk/topographic-map/
- [Q9] Lutra Consulting, Contours in QGIS: https://www.lutraconsulting.co.uk/blogs/contours-in-qgis
- [Q10] Laserlokaal, 3D model from stacked layers: https://laserlokaal.nl/en/blogs/knowledge/3d-model-from-stacked-layers
- [Q11] Harvard Fabrication Lab, CNC milling: https://harvardwiki.atlassian.net/wiki/spaces/fabricationlab/pages/60949661/CNC+milling
- [Q12] Prusa Blog, 3D printed railway models Part I Landscape: https://blog.prusa3d.com/3dprintedrailwaymodelspartilandscape_30698/
- [Q13] Studia3D, PLA-Gebirge statt Gips: https://studia3d.com/en/done/61-mountain/ ; Gewicht Gips/Unterbau: https://tysmodelrailroad.blogspot.com/2011/12/hardshell-terrain.html
- [Q14] Joswood Neuheiten 2022: https://bahnorama.ch/data/downloads/Joswood/archiv/Joswood_Neuheiten_2022.pdf
- [Q15] Joswood Neuheiten 2019: https://bahnorama.ch/data/downloads/Joswood/archiv/Joswood_Neuheiten_2019.pdf
- [Q16] Micro Welten Katalog 01/2018: https://de.readkong.com/page/katalog-micro-welten-9614459
- [Q17] Auhagen Anleitung 80208 (Lasercut-Kartonzubehoer): https://www.latelierdutrain.com/img/cms/notices/AUHAGEN/Auhagen%20HO/80208-portail%20avec%204%20portillon.pdf
- [Q18] Trusted Shops, Bewertung Modellbahn Union (gelaserte Fensterfolie): https://www.trustedshops.de/bewertung/info_X3A6D681161F45C00C9EDB63F41312A1D.html?page=2
- [Q19] Noch, strukturierte Pflasterplatte: https://www.noch.com/structured-pavement-cobblestones/60342 ; Ebay-Uebersicht H0-Kopfsteinpflaster: https://www.ebay.de/b/Modellbau-Kopfsteinpflaster-in-Landschaftsbau-fur-Modellbahnen-der-Spur-H0/262315/bn_7004734876
- [Q20] Instructables, Laser Cut Scale Model Building: https://www.instructables.com/How-to-Design-and-Laser-Cut-a-Scale-Model-Building ; QZY Models, Laser cut architectural models: https://www.qzymodels.com/what-is-laser-cutting-for-architectural-models/
- [Q21] LightBurn-Forum, 5,5-W-Diode und Karton: https://forum.lightburnsoftware.com/t/hands-up-ive-tested-and-tested-5-5w-diode-20w-laser-master/23882 ; https://forum.lightburnsoftware.com/t/settings-for-cutting-card/18132/2
- [Q22] Trains.com, Draht-Baeume: https://trains.com/?p=23071 ; Fusion Scale Hobbies: https://fusionscalehobbies.com/blogs/news/how-to-make-model-trees
- [Q23] COLMAP (GitHub, BSD): https://github.com/colmap/colmap ; GLOMAP: https://github.com/colmap/glomap
- [Q24] Radiance Fields, COLMAP 3.12: https://radiancefields.com/colmap-3-12-released
- [Q25] VGGT (Lizenz, Commercial-Checkpoint): https://huggingface.co/spaces/CgvKodai/_vggt/blob/main/README.md ; Paper: https://arxiv.org/html/2503.11651v1
- [Q26] MapAnything Paper/Doku: https://arxiv.org/pdf/2509.13414 ; https://docsearch.algolia.com/mcp/docs/repo/facebookresearch/map-anything
- [Q27] NAVER CHECKPOINTS NOTICE (Drittkopie): https://huggingface.co/spaces/zino36/Demo/raw/main/CHECKPOINTS_NOTICE
- [Q28] Gaussian-Splatting License (scancode): https://scancode-licensedb.aboutcode.org/gaussian-splatting-2024.html
- [Q29] 2DGS (GitHub): https://www.github.com/hbb1/2d-gaussian-splatting/blob/main ; MILo-Fork mit Lizenz: https://github.com/AntixK/MILo
- [Q30] PGSR (PyPI): https://pypi.org/project/pgsr/ ; GBM Gaussian Building Mesh: https://arxiv.org/html/2501.00625v1
- [Q31] Halling, Schilder selber drucken (kein Weiss am Heimdrucker): https://halling.at/documents/Schilder-selber-Drucken-2023.pdf
- [Q32] Halling, UV-Decals / Tutorial: https://halling.at/documents/UV-Decals-selber-Drucken-2021.pdf ; https://halling.at/documents//Tutorial---UV-Decals.pdf
- [Q33] Printpal AMS Color OBJ Converter: https://printpal.io/tools/ams-converter
- [Q34] AMS Splitter (Blender): https://superhivemarket.com/products/ams-splitter/docs
- [Q35] MakerWorld HueForge-Modelle (Einstellungen): https://makerworld.com/models/470022
- [Q36] Ebay-Uebersicht H0-Resinfiguren: https://www.ebay.de/b/Figuren-fur-Modellbahnen-Spur-H0-aus-Resin/262312/bn_13063549
- [Q37] Formlabs, Miniaturen/Figuren: https://formlabs.com/ch/blog/3d-druck-massgefertigte-miniaturen-figuren/
- [Q38] MakerWorld Lichtbox fuer Modellbahnhaeuser: https://makerworld.com/en/models/503898
- [Q39] Kalmbach Just-Plug-Test (Lichtdurchschlag): https://kalmbachhobbystore.Com/-/media/files/justplugreview0915.pdf ; Trains.com-Forum: https://cs.trains.com/mrr/f/11/t/259558.aspx
- [Q40] Arduino Blog, Lichtsystem fuer Modellbahn: https://blog.arduino.cc/2024/02/17/the-ultimate-lighting-system-for-model-railroaders/
- [Q41] FREMO H0-Europa Normen: https://www.fremo-net.eu/en/modular-systems/h0-scale/h0-europe/fremo-87-start/standards
- [Q42] FREMO Normen der Modulstirnbretter: https://fremo-net.eu/europa/schweiz/modulstirnbretter
- [Q43] FREMO H0m-Norm: https://www.fremo-net.eu/fileadmin/modulsysteme/baugroesse_H0/H0m/FremoH0mNorm_050319.pdf
- [Q44] FREMO Spur-0-Norm V10: https://www.fremo-net.eu/fileadmin/modulsysteme/baugroesse_0/0_Regelspur/FREMO-Spur0-Norm_V10.pdf
- [Q45] LGL Open GeoData Liste (DGM1, DOM1, LoD2; dl-de/by-2-0): https://bwmm-support.lgl-bw.de/export/sites/lgl/Produkte/Open-Data/Galerien/Dokumente/Open_GeoData_Liste_Datensaetze.pdf

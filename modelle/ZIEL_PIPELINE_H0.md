# ZIEL: Pipeline von null -> H0-druckbares Modell fuer beliebiges Ziel (Nutzer-/goal 18.11.2026)

Auftrag: "Die Pipeline muss von 0 ab zu beliebigem Ziel aus online Bildern und selbst fotografierten ein Modell
erstellen koennen, das so gut ist, dass es in H0 druckbar ist. Stoppe, wenn du nicht mehr weiter kommst.
Dokumentiere alle Versuche."  -> Diese Datei ist das Versuchsprotokoll (jeder Versuch: Datum, was, Ergebnis, Ursache, naechster Schritt).

## Abnahmekriterien (was "fertig" heisst)
1. EIN Aufruf `tools/gesamtkette.py <ziel> --ziel <name>` ohne Handeingriff im Generator (nur objekt.json-Eintraege, die die Kette selbst schreibt).
2. Lage-Tore gruen (Grundriss, GPS, Lot, Massstab) - sonst Abbruch mit Grund.
3. Foto-Tore: foto_diff/Foto-F1 und feinteil_tor je Zone mindestens auf Hoehe des bisher besten Standes des Objekts (Kaufhaus: Handmodell grob3 im gk-Rahmen).
4. Druck: wasserdicht, ein Koerper je Druckteil, Wand >= 1,2 mm, Details >= 0,3 mm, keine Luftinseln (druck_luft), Bausatz-Teilung (tools/bausatz.sh / druck_teilung.py) rc 0 -> Druckdateien.
5. Augenurteil Bild "Foto neben Modell" je Seite (modell_neben_foto) - Fehlerliste vor Lob.

## Bekannte Luecken (Stand 18.11. nachts)
- L1 ERLEDIGT 18.11. (5cfb4345): Stufe "druck" am Kettenende ruft tools/bausatz.sh mit relief/*_putz.npz; ohne Masken Notiz statt Bausatz (noch offen: Bausatz ohne Steinplatten).
- L2 TEILWEISE ERLEDIGT 18.11. nachts (V6, nicht committet): Stufe 'bauplan' schreibt rueckwand / innenwaende / innenwand_oeffnungen selbst, Vorlage ruft rueckwaende,
  oeffnungen_aus_wandbild(nur_frei), entlueften auf. OFFEN: Laube/Halle freilegen (sonst bleibt eine erkannte Innenwand im Vollkoerper), Innenwand-Tiefen je Oeffnung
  nicht reproduzierbar (NCC < 0,2), Saeulen/Balkon/Erker/Figuren/Schindeln weiter nur Hand (L3).
- L2 (alt) Generator aus der Kette = Vorlage (generator_vorlage); alles, was Agenten im Kaufhaus von Hand in kaufhaus_gk_gen.py/objekt.json geschrieben haben (Laube, Saeulen, Balkon, Erker, Figuren, Schindeln, Innenwaende), erzeugt die Kette NICHT selbst.
  Richtung (Grundsatz WANDBILD = BAUPLAN): Stufen, die aus Wandbild + Tiefe Zonen finden und Gestalt nachbilden (form_aus_wandbild, oeffnungen_wandbild, innenwaende) und ihre Ergebnisse in objekt.json schreiben; die Vorlage ruft sie generisch auf.
- L3 Freistehendes (Saeulen, Bruestung, Erkerkoerper, Konsolrippen) nur Katalog; Ziel: Fotokanten mehrerer Ansichten.
- L4 Mapper: globaler Mapper zerfaellt bei gemischten Quellen (Kaufhaus gk2: 14 Teilmodelle) -> schrittweiser Mapper 1 Thread, Stunden.
- L5 Platten: Daten auf 5 Laufwerke verteilt, Systemplatte knapp (5-7 GB) -> 2-TB-Platte 18.11.

## Versuche
- V1 17.11. 18:20 kaufhaus_gk2 von null (gesamtkette kaufhaus --ziel kaufhaus_gk2): 6410 Bilder vorgeprueft (GPU, 49 min), 1945 zeigen das Objekt, 1364 nach Sammeln. Globaler Mapper: 14 Teilmodelle; groesstes Teilmodell GPS-Rest Median 9,0 m, p90 243 m, 36 % > 15 m (44 eigene GPS-Fotos) -> Tor nicht bestanden (Schwelle 15 %). Fallback schrittweiser Mapper (1 Thread, bewusst: Mehrthread nicht reproduzierbar, Messung 13.11.) lief in das Stufen-Zeitlimit 10800 s -> rc 124, Kette Abbruch rc 4. ERGEBNIS: GESCHEITERT an L4 (Rechenzeit), nicht an Qualitaet.
- V1b 17.11. 23:29 dieselbe Kette --ab sfm mit RCPARK_STUFE_MAX_S=36000 (Merkmale/Paare aus Cache). Global 1633 s: GPS 33 % > 15 m, Median 8,0 m. Schrittweise 20251 s (5,6 h): 982 von 1364 Bildern im groessten Teilmodell (13 Teilmodelle), GPS 18 % > 15 m, Median 4,2 m -> Tor knapp NICHT bestanden, gewaehlt schrittweise. Dichte Bildwahl 867 Bilder -> 14 GB Tiefenkarten nach 758 Bildern, Datenplatte lief auf 0,6 GB frei -> Job 05:4x angehalten (L5). Platz: video_frames (4,5 GB) auf SSD 20757D2E, schwab_v3/seiten_nachholen auf rcstick ausgelagert.
  LEHRE: dicht_bildwahl braucht eine Obergrenze nach Platz (Tiefenkarten ~18 MB/Bild bei 1600 px) - offen.
- V1c 18.11. 06:51 Fortsetzung --ab sfm: SfM uebersprungen, Tiefenkarten fortgesetzt (867), Fusion brach ab ('width_ > 0', fused.ply 0 Punkte): 272 Karten waren beim Plattenvoll-Halt leer geschrieben worden. GESCHEITERT (Folgefehler L5).
  Fix generisch: dicht-Skript loescht kaputte Karten (< 2 KB) vor dem Lauf (pipeline_objekt). Rettung von Hand (einmalig): die 272 Bilder aus sfm/sparse_dicht genommen (alt: sparse_dicht.alt_1811), fusion.cfg/patch-match.cfg bereinigt -> 595 Bilder mit gueltigen Karten.
- V1d 18.11. 07:23 Fortsetzung --ab sfm mit 595 Bildern (Fusion aus Cache): nach 90 s OOM-Kill (11 GB RAM + 6 GB Swap). Ursache: StereoFusionOptions.cache_size Vorgabe 32 GB > 15 GB RAM. GESCHEITERT.
  Fix generisch (6daa0c5f): cache_size = 40 % MemAvailable. V1e 07:55 gleiche Fortsetzung (Job kaufhaus_gk2e). Zusatz 090e8637: use_cache=True (sonst cache_size wirkungslos, 13 GB in 30 s) -> 5,5-6,8 GB, aber nur 1 Thread und Nachladen: nach 65 min 596 GB gelesen (Karten 17,6 GB, Cache 4,4 GB).
  Nutzer 09:00: volle Aufloesung behalten (kein Herabsetzen auf 1200 px) -> Lauf laeuft unveraendert weiter. pipeline_objekt.run schreibt Ausgaben jetzt zeilenweise ins Log (Fortschritt sichtbar ab dem naechsten Lauf).
  11:55 nach 4 h ohne Ende (1,56 TB gelesen) gestoppt. Messung: 100 Bilder am Stueck ohne Cache 52 s / 4,1 GB / 28 Threads. Neu tools/teilfusion.py (volle 1600 px: Kerne nach Blickziel, + Nachbarn nach gemeinsamen SfM-Punkten, Punkt nur behalten, wenn sein Bezugsbild aus fused.ply.vis zum Kern gehoert);
  Gegenprobe 100 Bilder in 3 Teilen: 81 % der Punkte, Ganz-Wolke zu 98,4 % abgedeckt (5 x Punktabstand), 99,8 % der Teilpunkte auf der Ganz-Wolke. pipeline_objekt nimmt Teilfusion, wenn Bedarf (45 MB/Bild) > 60 % freier RAM. V1f 11:58 Job kaufhaus_gk2f: TEILFUSION 7 Teile (Kerne 137/100/96/6/78/93/85, je 154 Bilder, 61-69 s) -> 2 827 074 Punkte in 458 s (statt > 4 h). GPU-Wache warnt (Fusion hat keinen GPU-Code - unbegruendet).
  Randtest 160 Bilder (Ausschnitt um ein Blickziel, am Stueck fusionierbar): Teile (kern_anteil 0,6) 98,5 % der Punkte, Flaeche 99,1 % (5 x Abstand) / 99,8 % (10 x), Teilpunkte 99,7 % auf Ganz;
  kern_anteil 0,4: 102 %, gleiche Abdeckung, 20 % langsamer -> 0,6 bleibt. Der 100-Bilder-Test (81 %) war zu klein (zu wenig Nachbarn je Teil).
  RAM-Buchung job_start (JOB_RAM_MB) + kleine Kerne zusammenlegen (7fc20a34).
- V1g 18.11. 12:16 Tore gk2f: KEINE Loesung besteht (abbruch rc 3). Alle 4 Loesungen gegen GPS gedreht 73-158 Grad / Massstab 0,25-1,9, GPS-Fit selbst Rest Median 5,8 m (110 Fotos).
  Ursache: sfm_lod2_ausrichten verwarf den GPS-Massstab (Paarverhaeltnisse q75/q25 2,43 > 2 wegen einzelner falscher Geotags) -> Massstab aus Wolkenausdehnung, Suchband x4.
  Fix (01cd65e0): robuster Aehnlichkeits-Fit RANSAC (Inlier < 10 m, >= 40 %, Rest <= 8 m, Ausdehnung >= 20 m), falsche Geotags aus dem GPS-Startkandidaten; synthetisch 23 % falsche Tags -> Massstab 0,2 % genau, Haufen abgelehnt.
  V1h 12:20 Job kaufhaus_gk2g --ab tore: Ausrichter mit robustem GPS 68/110 Geotags (Rest 2,4 m), Guete 48 %, RMS 0,5 m, Kamerahoehe 1,51 m - aber Kette pruefte die neue Loesung 0 nie (rc 5 im Kreislauf) -> Fix b9fa7e32.
  V1i 12:27 kaufhaus_gk2h: GPS-Tor rc 3 auf der GUTEN Lage (Massstab 0,80): das Tor trimmte nur 20 %, 38 % der Geotags falsch. Fix: RANSAC-Konsens im Tor (>= 40 %, < 10 m), Grenzen unveraendert.
  Probe: echte Lage Drehung -5,4 / Massstab 0,91 / Rest 2,4 m -> passt; kuenstlich 73 Grad x 0,65 -> rot (-78 Grad, 1,41); x 0,8 -> rot (Median 15,6 m). OFFEN: LoD2-Massstab 9 % kleiner als GPS (innerhalb 15 %).
  Ideen falls V1b scheitert: (a) globaler Mapper nur auf eigenen Fotos + Commons, Videobilder danach registrieren (image_registrator); (b) Bildwahl auf ~700 Bilder nach Blickrichtungsabdeckung vor dem Mapper; (c) hierarchical_mapper testen (Reproduzierbarkeit messen).
- V2 17.11. Kaufhaus Runde 2/3 (Agenten, Commits 1877c251, 920af251): Pipeline-Bugs gefunden (Fotoquellen, Brei, blindes Mass); Katalogteile wirken steif (-> Grundsatz Wandbild = Bauplan).
- V3 17.11. Feinausrichtung Wandbild (eeafa1e7): Restversatz 1,2-2,5 -> 0,2-0,5 cm, Fugen-F1 0,417 -> 0,431; am Kaufhaus ohne Wirkung (Putz, Fotos aus Jahrzehnten).
- V4 17.11. form_aus_wandbild (9ba2dca2): Topologie treuer, Kanten wellig -> Standard aus; Folgeauftrag Kanten einrasten (laeuft).
- V5 18.11. Rueckwand hinter Oeffnungen + Innenwaende/Laube (oeffnungen_wandbild.py): Laube ~35 -> ~55 %, OG-Rueckwand rendert hell (feinteil OG -0,026); Abnahme im Worktree bestanden; oeffnungen_wandbild noch keine Kettenstufe.
- V6 18.11. nachts L2 'bauplan' (Agent L2, nicht committet). Neu: Kettenstufe bauplan (gesamtkette, nach fenster), tools/innenwaende_finden.py, tools/rueckwand_tiefe.py,
  bauteile.entlueften / oeffnungen_aus_wandbild(nur_frei) / oeffnungen_aus_json(innenwaende), Generator-Vorlage mit Innenwand-Oeffnungen, rueckwaende, entlueften, Splitter-Entfernung.
  Test A schwab_l2 (Kopie schwab_auto unter tmp_l2, --ab bauplan): Innenwand richtig KEINE (Tordurchfahrt; Durchblick aber nicht positiv erkannt, nur 'keine');
  rueckwand ANNAHME 0,15 (nur 1 belastbare Fenstertiefe); Rueckwand hinter 4 Oeffnungen; erster Bau 2 Koerper (Hohlraum durch Regel A ringsum zu) -> bauteile.entlueften
  (Schacht zur Standflaeche) -> bauen_abnehmen "alle Pruefungen bestanden". Druck (bausatz.sh) rc 3: Durchdringung Platte/Koerper 13,8 mm3 > 1 - gleich mit
  OHNE_RUECKWAND=1 (1 640 634 Dreiecke, 1 Koerper, 28 Platten, Luftinseln der Platten gefuellt, 0/76 offene Hoehenschnitte) -> Altfehler der Platten-Taschen, nicht V6.
  Test B kaufhaus_l2 (Kopie ohne Handeintraege): i00 selbst gefunden, Versatz -4,36 (Hand -4,25), u -8,9..9,0 (Hand -8,4..9,0), z 0,78..5,5 (Hand 0,65..5,5), Signifikanz 15;
  Wandbild i00 zeigt Laubenrueckwand; Zonen 7/7 wie Hand (4 Fenster, Tafel, Tuer, Tor) + 1 Fehlzone (Plakat); Tiefen je Oeffnung NICHT reproduziert
  (0,02/0,06/-0,06/0,02/-0,06/-0,66 gegen Hand 0,06/0,10/0,0/0,10/0,14/0,52; NCC 0,12-0,35) -> keine Innenwand-Oeffnung gebaut (Vorlage baut ohnehin nur auf freiliegender Wand).
  rueckwand gemessen 0,20 m (3 Fenster 0,18/0,20/0,32) gegen Handmass 0,14/0,19. Vorlagenbau kaufhaus_l2 erwartungsgemaess rc 1 (Laube, Saeulen, Erker, Balkon fehlen = L3).
  Naechster Schritt: Laube/Arkade aus innenwaende freilegen (Bogenform aus Wandbild der Aussenwand, form_aus_wandbild), Innenwand-Tiefe je Zone robuster (mehr Blickwinkel, Ring ohne Pfeiler).
- V7 18.11. 08:10 L2 Laube freilegen: bauteile.laube_aus_wandbild (Boegen = Bildumrisse der Aussenwand aus audit/oeffnungen_aussen.json, Halle bis zur gemessenen Innenwandebene; ANNAHME Pfeilertiefe 0,8 / ebener Boden / flache Decke), Generator-Vorlage ruft es VOR den Innenwand-Oeffnungen (nur_frei findet die Wand dann frei), gesamtkette erneuert alte Rumpfe. Schnelltest synthetisch 125 m3 / 1 Koerper gruen; Regression kaufhaus_null4 identisch. Am echten Kettenobjekt (gk2e) noch ungeprueft.
  Nebenbefund: regression.py martinstor kaputt (bauteile.lade_masse fehlt seit 497af805) - alt, nicht V7.

## UEBERGABE 18.11. ~07:40 (vor /clear) - hier weitermachen
- LAEUFT: systemd-Job rcpark-kaufhaus_gk2d (Log /media/oem/scan/rc-park_daten/kaufhaus_gk2d.log): gesamtkette kaufhaus --ziel kaufhaus_gk2 --ab sfm (Fusion 595 Bilder, dann tore/dach/bauen/kanten/fototor/fassaden/fenster/bauplan/seiten/html/druck). Erwartung: GPS-Tor knapp rot (18 % > 15 m) -> Kette koennte an den Lage-Toren anhalten -> dann Ursache pruefen (Videobilder/alte Fotos mit falschem GPS? GPS-Tor nur auf eigenen Handyfotos?), NICHT einfach --trotz-lage.
- LAEUFT: Agent "Druckstufe: Plattentaschen-Durchdringung" (druck_farbteile, 13,8 mm3 > 1 mm3 am Schwabentor; Zwischendateien rc-park_daten/tmp_druck). Ergebnis pruefen, Schnelltest, committen; tmp_druck + Test-Symlinks im Repo wegraeumen.
- NUTZER 18.11. 08:20: "3D HTML, sobald du was hast" -> sobald rc-park_daten/kaufhaus_gk2/kaufhaus_gk2_3d.html (Kettenstufe html) da ist bzw. nach tore die Wolke im Rahmen liegt: als EIGENES Artifact veroeffentlichen: https://claude.ai/artifact/2UtaDZfwddHA4sDULQCJfj (V1 12:35 Wolke+LoD2-Block nach gruenen Toren; nach Bau/html dieselbe Datei scratchpad/kaufhaus_gk2_3d.html bzw. Kettenausgabe neu publizieren). Hand-Modell HdPoLi5E7mvN35aJxhwEHC bleibt.
- Nach gk2d: Bild Foto neben Modell + feinteil_tor je Zone gegen grob3 (Bezug rc-park_daten/kaufhaus_gk/feinteil/) + Abdeckung je Seite + GPS-Rest -> Zahlen dem Nutzer melden (versprochen) + 3D-HTML.
- Offene Luecken: L2 Rest (Laube/Arkade freilegen, Tiefe Innenwand-Oeffnungen), L3 Freistehendes (Erkerkonsole/Rippen aus Fotokanten, Kielbogen = Katalogkurve an Wandbild-Geraden einpassen), L4 Mapper (Bildzahl/Zeit), L5 Platten (2-TB-Platte kommt 19.11. laut Nutzer: Umzug laut memory reference-laufwerke-uuid).
- Platten: SSD 20757D2E haengt als /media/oem/20757D2E455CA0E8 (rw) und traegt Auslagerungen (u. a. kaufhaus_gk2/video_frames, schwabentor, schwab_auto); NICHT abziehen lassen.
- V8 18.11. vormittags Agent "Druck-Taschen" (nicht committet): Kettenstufe druck (bausatz.sh) am Schwabentor rc 3. Testobjekt schwab_l2 war geloescht -> Kopie schwab_dtest
  (schwab_auto unter rc-park_daten/tmp_druck, Generator per objekt_anlegen --generator-erneuern wie in V6, OHNE_RUECKWAND). 13,8 mm3 dort NICHT exakt nachgebaut (Modell anders):
  Durchdringung 0,000, dafuer rc 3 "offene Hoehenschnitte 7 von 76" (z 18-19 / 23,5-25 m: 3 bzw. 2 Stuecke statt 1).
  Ursache 1 (Durchdringung): druck_luft.stuetzen kennt die Tasche nicht - FUELLEN = Insel + 0,2 mm, SAEULE = Insel + Kreis 1,6 mm -> ragt am Plattenrand aus dem Prisma in den Putz.
  Beleg: Kunstplatte mit Randinsel 4,84 mm3 ausserhalb des Umrisses; Schwabentor platte_w02_02 0,33 mm3 (Spiel 0,3) bzw. 0,83 mm3 (Spiel 0,15) ausserhalb der Tasche minus halbes Spiel,
  alt 0,046 mm3 Durchdringung bei Spiel 0,15. Fix: Platte nach den Stuetzen auf Tasche minus halbes Fuegespiel beschnitten (druck_farbteile; farbteile.json luft.aus_tasche_beschnitten_mm3),
  Durchdringung > 1 mm3 nennt jetzt den Ort.
  Ursache 2 (offene Schnitte): ringschicht schliesst den Schnitt mit 0,6 m - eine Oeffnung 1,4-2,7 m (Fenster/Durchgang des Turms) liess KEINEN Hohlraum, Innenraum leer ->
  alle Innenschichten der Scheibe geloescht; Platten w01/w02 (Wand liegt dort bis 20 cm vor der Maskenebene) nahmen die Wand bis auf Splitter. Fix: mit Tasche in der Scheibe
  bis 3 x schliess weiter schliessen, nur Schnittstuecke > 0,05 m2 (Splitter in der 6,7-m-Oeffnung z 9-10 m schlossen sonst einen falschen Hohlraum: 3 neue offene Schnitte),
  Innenraum dann = Schnitt + wahrer Hohlraum. Ergebnis 7/76 -> 0/76 offen (Schnittbilder z 9,5 / 18 / 24 angesehen: Innenschicht hinter den tiefen Platten da, Splitter unveraendert).
  Ursache 3: druck_teilung schrieb Teile nach Luft-Stuetzen mit Beruehrkanten (teil_02 348, teil_06 36 Kanten mit 4 Flaechen) -> trimesh nicht wasserdicht; Fix kneifkanten_schliessen r 0,05 mm.
  Ergebnis bausatz.sh schwab_dtest (Wand 2,4, Spiel 0,3, tasche + Ring): rc 0 - 1 Koerper, 28 Platten, Durchdringung 0,000 mm3, 0/76 offene Schnitte, 6 Teile + Verbinder
  + 28 Platten wasserdicht (36/36 Dateien), Luftinseln 0, Prusa 27 h 23 min / 909 cm3, Bambu 7 h 49 min / 70 cm3 (druckzeit*.json). Testobjekt danach geloescht.
  OFFEN: Platte = Prisma ab EINER Ebene je Wand; liegt die Wand oertlich bis 20 cm vor der Maskenebene (w01/w02, z 17-33 m), nimmt die Platte die ganze Wand
  und nur die Innenschicht (~1 mm) traegt dort (rippen.png z 376 mm: duenner Wandabschnitt) -> Plattentiefe je Pixel an die oertliche Wandflaeche binden.

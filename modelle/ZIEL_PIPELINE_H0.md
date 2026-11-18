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
- V1d 18.11. ~07:30 Fortsetzung --ab sfm mit 595 Bildern (Fusion aus Cache). Ergebnis: offen.
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

## UEBERGABE 18.11. ~07:40 (vor /clear) - hier weitermachen
- LAEUFT: systemd-Job rcpark-kaufhaus_gk2d (Log /media/oem/scan/rc-park_daten/kaufhaus_gk2d.log): gesamtkette kaufhaus --ziel kaufhaus_gk2 --ab sfm (Fusion 595 Bilder, dann tore/dach/bauen/kanten/fototor/fassaden/fenster/bauplan/seiten/html/druck). Erwartung: GPS-Tor knapp rot (18 % > 15 m) -> Kette koennte an den Lage-Toren anhalten -> dann Ursache pruefen (Videobilder/alte Fotos mit falschem GPS? GPS-Tor nur auf eigenen Handyfotos?), NICHT einfach --trotz-lage.
- LAEUFT: Agent "Druckstufe: Plattentaschen-Durchdringung" (druck_farbteile, 13,8 mm3 > 1 mm3 am Schwabentor; Zwischendateien rc-park_daten/tmp_druck). Ergebnis pruefen, Schnelltest, committen; tmp_druck + Test-Symlinks im Repo wegraeumen.
- Nach gk2d: Bild Foto neben Modell + feinteil_tor je Zone gegen grob3 (Bezug rc-park_daten/kaufhaus_gk/feinteil/) + Abdeckung je Seite + GPS-Rest -> Zahlen dem Nutzer melden (versprochen) + 3D-HTML.
- Offene Luecken: L2 Rest (Laube/Arkade freilegen, Tiefe Innenwand-Oeffnungen), L3 Freistehendes (Erkerkonsole/Rippen aus Fotokanten, Kielbogen = Katalogkurve an Wandbild-Geraden einpassen), L4 Mapper (Bildzahl/Zeit), L5 Platten (2-TB-Platte kommt 18.11.: Umzug laut memory reference-laufwerke-uuid).
- Platten: SSD 20757D2E haengt als /media/oem/20757D2E455CA0E8 (rw) und traegt Auslagerungen (u. a. kaufhaus_gk2/video_frames, schwabentor, schwab_auto); NICHT abziehen lassen.

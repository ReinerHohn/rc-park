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
- L2 Generator aus der Kette = Vorlage (generator_vorlage); alles, was Agenten im Kaufhaus von Hand in kaufhaus_gk_gen.py/objekt.json geschrieben haben (Laube, Saeulen, Balkon, Erker, Figuren, Schindeln, Innenwaende), erzeugt die Kette NICHT selbst.
  Richtung (Grundsatz WANDBILD = BAUPLAN): Stufen, die aus Wandbild + Tiefe Zonen finden und Gestalt nachbilden (form_aus_wandbild, oeffnungen_wandbild, innenwaende) und ihre Ergebnisse in objekt.json schreiben; die Vorlage ruft sie generisch auf.
- L3 Freistehendes (Saeulen, Bruestung, Erkerkoerper, Konsolrippen) nur Katalog; Ziel: Fotokanten mehrerer Ansichten.
- L4 Mapper: globaler Mapper zerfaellt bei gemischten Quellen (Kaufhaus gk2: 14 Teilmodelle) -> schrittweiser Mapper 1 Thread, Stunden.
- L5 Platten: Daten auf 5 Laufwerke verteilt, Systemplatte knapp (5-7 GB) -> 2-TB-Platte 18.11.

## Versuche
- V1 17.11. 18:20 kaufhaus_gk2 von null (gesamtkette kaufhaus --ziel kaufhaus_gk2): 6410 Bilder vorgeprueft (GPU, 49 min), 1945 zeigen das Objekt, 1364 nach Sammeln. Globaler Mapper: 14 Teilmodelle; groesstes Teilmodell GPS-Rest Median 9,0 m, p90 243 m, 36 % > 15 m (44 eigene GPS-Fotos) -> Tor nicht bestanden (Schwelle 15 %). Fallback schrittweiser Mapper (1 Thread, bewusst: Mehrthread nicht reproduzierbar, Messung 13.11.) lief in das Stufen-Zeitlimit 10800 s -> rc 124, Kette Abbruch rc 4. ERGEBNIS: GESCHEITERT an L4 (Rechenzeit), nicht an Qualitaet.
- V1b 17.11. 23:29 dieselbe Kette --ab sfm mit RCPARK_STUFE_MAX_S=36000 (Merkmale/Paare aus Cache). Ergebnis: offen.
  Ideen falls V1b scheitert: (a) globaler Mapper nur auf eigenen Fotos + Commons, Videobilder danach registrieren (image_registrator); (b) Bildwahl auf ~700 Bilder nach Blickrichtungsabdeckung vor dem Mapper; (c) hierarchical_mapper testen (Reproduzierbarkeit messen).
- V2 17.11. Kaufhaus Runde 2/3 (Agenten, Commits 1877c251, 920af251): Pipeline-Bugs gefunden (Fotoquellen, Brei, blindes Mass); Katalogteile wirken steif (-> Grundsatz Wandbild = Bauplan).
- V3 17.11. Feinausrichtung Wandbild (eeafa1e7): Restversatz 1,2-2,5 -> 0,2-0,5 cm, Fugen-F1 0,417 -> 0,431; am Kaufhaus ohne Wirkung (Putz, Fotos aus Jahrzehnten).
- V4 17.11. form_aus_wandbild (9ba2dca2): Topologie treuer, Kanten wellig -> Standard aus; Folgeauftrag Kanten einrasten (laeuft).
- V5 18.11. Rueckwand hinter Oeffnungen + Innenwaende/Laube (oeffnungen_wandbild.py): Laube ~35 -> ~55 %, OG-Rueckwand rendert hell (feinteil OG -0,026); Abnahme im Worktree bestanden; oeffnungen_wandbild noch keine Kettenstufe.

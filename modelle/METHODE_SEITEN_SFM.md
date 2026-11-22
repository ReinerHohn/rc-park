# Methode: Seiten-SfM für Bauten mit ähnlichen Seiten (ab 21.11.2026)

Zweck: Ein Bau mit gleich aussehenden Seiten (Torturm: Uhr, Ecktürmchen, Helm) wird vom Mapper verklebt - die Rückseite landet auf der Vorderseite (Martinstor viermal, Schwabentor 15.11.). Die Folge hier rechnet jede Seite getrennt und legt die Seiten danach über die Geometrie zusammen.
Entstehung, alle Läufe und Zahlen: `modelle/GLOBALER_MAPPER_STABIL.md` (ab „Untersuchung 21.11.2026“), `modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md` (Nachträge ab 09:44), Register `modelle/ERKENNTNISSE.md`, Ursachen `modelle/ANALYSE_SACKGASSEN_2026-11-21.md`, Verbesserungen `modelle/RECHERCHE_SEITEN_SFM_2026-11-21.md`.

## Gilt

### Grundsätze
- Die Verklebung am Martinstor kam von einer PERSON im Vordergrund (Selbstaufnahme-Video auf beiden Torseiten, 18 Brückenbilder), nicht nur von ähnlichen Wänden: Masken gehören vor die Merkmalssuche UND in den Paar-Prüfer.
- `modell_zerlegen` merkt eine Verklebung nicht (ein Stück); zwei Mapper-Läufe verkleben gleich, der Konsens-Schnitt erkennt es nicht. Nur das Blick-Tor prüft es ohne Vorwissen.
- Aus der Klappung (ähnliche Wände aufeinandergelegt) wird nur der MASSSTAB genommen; Lot, Drehung um das Lot und Lage kommen aus Spitze und Wänden der dichten Wolken.
- Ein Urteil über das Vereinen nie nur an einer Zahl fällen: `vereinen.jpg` (Ansicht + Grundriss) ansehen - ein Turm mit zwei gegenüberliegenden Wänden = richtig.
- Ein Handablauf gilt erst als erledigt, wenn die Kette ihn aufruft und ein Kettenlauf es belegt.

### Ablauf (Werkzeug je Schritt)
1. **Masken** für Personen, Fahrzeuge, Marktstände, Bäume: `tools/handy_masken.py` (GPU, SegFormer-B4 ADE20K, Batch 2 auf der 8-GB-Karte). Jedes Bild braucht eine Maskendatei - COLMAP überspringt bei `mask_path` Bilder ohne Maske (leere Maske anlegen).
2. **Masken anwenden**: neue Läufe über `ImageReader.mask_path` in der Merkmalssuche; vorhandene Datenbank über `tools/db_masken_filter.py` (streicht Vordergrund-Zuordnungen aus den Paaren, Paar unter 15 Resten wird gelöscht).
3. **Kamera-Bereinigung**: `tools/sfm_db_variante.py --priors loeschen --kamera-je-clip` (eine Kamera je Videoclip, EXIF-Prioren weg, Panoramen raus).
4. **Seitenerkennung**: `tools/seiten_erkennen.py --streng --masken DIR --db-aus kopie.db` -> `seiten.json` (Bildteile ohne echte Verbindung = Seiten, „fremd“) + Datenbank ohne die verwechselten Paare. rc 3 = Verwechslung gefunden und bereinigt (kein Fehler).
5. **Globaler Mapper je Seite, zwei Läufe**: `view_graph_calibrator` auf DB-Kopie, dann `global_mapper` mit `--GlobalMapper.image_list_path teilN.txt`, je Seite zweimal (Vorlage `tools/versuche/mt_global_gefiltert_1121.sh`). Läufe vergleichen: `tools/modell_lage_vergleich.py` (robuster Ausgleich, Abweichung je Bildquelle).
6. **Schärfe-Test und Sperrliste**: `tools/brennweite_schaerfe.py <modell> --liste/--sperrliste` - Urteil je Kamera scharf / weich / unbestimmt / zu_wenig; unbestimmt + zu_wenig nicht zum Messen nehmen.
7. **Dichte Wolke je Seite**: `tools/dicht_modell.py <sparse> <bilder> <aus> [--ohne sperrliste]` -> `fused.ply` je Seite (danach Skill `wolke-tore`).
8. **Vereinen**: `tools/seiten_vereinen.py A B <ursprungs-db> --aus DIR --dicht-a ... --dicht-b ...` -> `vereinen.json` (Matrix `B_nach_A`, Prüfwerte) + Pflichtbild `vereinen.jpg`. Innen: Klappung (Sim3 über die Paare ähnlicher Wände) nur für den Massstab; Lot von B aus seinen eigenen Wandnormalen; Lage waagerecht Spitze auf Spitze (`spitze_global` je Wolke); Drehung um das Lot aus den Wandrichtungen (mod 90 Grad) im Umkreis der Spitze; dann halbe Drehung um die Achse (Helmstange). rc 0 vereint, rc 3 abgelehnt (nichts übernehmen), rc 2 zu wenige Verbindungen.
9. **Blick-Tor**: `tools/seiten_blick_tor.py <sparse> seiten.json` an jedem Seitenmodell und am Ergebnis - „verwechselt“-Gruppen aus verschiedenen Bildteilen dürfen nicht in dieselbe Richtung blicken. rc 3 = verklebt, Modell nicht weiterverwenden.

### Gemessene Regeln und Schwellen (bisher nur am Martinstor - an einem zweiten Bauwerk prüfen)
- Seitenerkennung: mit Masken 0 gemischte Bildteile (Nord 538, Süd 102 + 55 Bilder); ohne Masken ein Teil mit 750 Bildern beider Seiten.
- Masken: im Mittel 12,6 % maskiert; 286 von 2042 Bildern mit > 30 % Vordergrund.
- Ketten-Datenbank: 2107 Bilder = 2107 Kameras, EXIF-Brennweite nur bei 49, teils unsinnig (bis 2185 x Bildbreite) -> Schritt 3 immer vor dem Mapper.
- Globaler Mapper auf gefilterter DB: Nord 538 von 538 Bildern in 909-1001 s; zwei Läufe: 456 von 538 Kameras auf ≤ 1 % der Szene gleich (Median 0,07 %). Süd: 92 von 101 (Median 0,04 %).
- Schärfe-Test (Schwellen der ersten Fassung, nie nachgestellt: scharf < 4 %, unbestimmt ≥ 10 % oder offen, zu_wenig < 15 Punkte): Nord scharf 433 -> 4 wandern (1 %), unbestimmt 24 -> 16, zu_wenig 52 -> 49; mit Sperrliste (76 Bilder) wandern 9 von 462.
- Wandernde Bilder sind fast nur Einzelfotos (Brennweite je Lauf 2-6 % anders); zwei schrittweise Läufe streuen genauso - keine Eigenheit des globalen Mappers.
- Vereinen, Prüfgrenzen in `seiten_vereinen.py`: Achse ≤ 1,5 % der Bauhöhe einig, Turmhöhen ≤ 4 % verschieden (a priori gesetzt), Blick vorher < 60 Grad, Dachflächen erreichen die Achse nicht unter 80 % der Bauhöhe, Flanke gleich oder nicht bewertbar; Korrekturgrenzen Lot 0,2-15 Grad, Drehung 0,3-30 Grad bei Bündelung > 0,3.
- Vereinen, Messwerte: Klappung lag 35,2 % der Turmhöhe daneben, Süd 4,52 Grad gekippt und 16,7 Grad verdreht; nach den drei Berichtigungen Lot 0,05 Grad, Achse 0,60 % einig, Blick 165 Grad, Dach 1,02 / 1,01, Turmhöhen 3,0 % verschieden.
- Belastungsprobe: 8 absichtlich verfälschte Klappungen (bis 7,5 Grad Kippung, 19,6 Grad Drehung, 24 % Verschiebung) enden auf 0,26-0,96 % der Bauhöhe und 0,04-0,49 Grad gleich. Fester Test ohne echte Daten: `tools/test_seiten_vereinen_robust.py`.
- Blick-Tor (Schwelle 60 Grad): verklebtes Nachtmodell 25 von 25 Paaren verklebt (rc 3); Nord global und Süd bestanden.
- Dichte Wolke: Nord 266 von 538 Bildern in 23 min, Süd 5 min.

### Schon in der Kette / noch Handfolge (im Code geprüft 21.11.2026)
- IN DER KETTE (`tools/iphone_sfm.py` über `tools/sfm_seiten_vorstufe.py`, Standard an, `RCPARK_SEITEN=0` aus): Schritt 1 (`masken_rechnen`), Schritt 2 (`masken_colmap` -> `mask_path`; Rückfall `masken_filter`), Schritt 4 (`seiten` -> Mapper rechnet auf `db_seiten.db`), Schritt 3 für jeden Mapper-Weg (`bereinigen` -> `db_mapper.db`), dazu `teile_im_modell` (meldet, welche Seite im Modell fehlt).
- IN DER KETTE (`tools/gesamtkette.py`, Stufe tore): Schritt 9 `seiten_blick_tor.py` als hartes Tor (rc 3 -> Abbruch, kein Lösungs-Kreislauf; ohne `seiten.json` nur Meldung „nicht geprüft“); Schritt 6 `brennweite_schaerfe.py` -> `sfm/sperrliste_messen.txt` (vereinigt mit `unstabil.txt` des Konsens-Mappers). `tools/pipeline_objekt.py` gibt die Sperrliste an die Bildwahl der dichten Wolke.
- IN DER KETTE seit 21.11. 15:15 (`tools/sfm_seiten_modelle.py`, von `iphone_sfm.py` bei mehreren Bildteilen, Schalter `RCPARK_SEITEN_MODELLE`): Schritt 5 (je Teil ab 30 Bildern zwei globale Läufe, Laufwahl, a/b-Vergleich, Sperrliste), Schritt 7 (`dicht_modell.py` je Teil), Schritt 8 (`seiten_vereinen.py` gegen den größten Teil, vereintes Modell nach `sparse/0`), Blick-Tor am vereinten Modell; bei Ablehnung Teil A allein + Meldung. Schwellen (30 Bilder, 1 % Laufwahl) sind ANNAHMEN.
- NOCH HANDARBEIT: Sichtprüfung des Pflichtbilds `vereinen.jpg`; Maßstab der zweiten Seite (kommt aus der Klappung).
- Die Sperrliste wirkt in der Hauptkette nur auf die dichte Wolke, noch nicht auf Kantenstufe und Wandbild. In `sfm_seiten_modelle.py` seit 21.11. abends NICHT mehr auf die dichten Seitenwolken (`DICHT_MIT_SPERRLISTE = False`, siehe nächster Punkt).
- KETTENLAUF 21.11. (`martinstor-1120/pipe`, Teile 574/101/52): `seiten_vereinen` lehnte Teil 1 (Turmhöhen 19,8 %) und Teil 2 (9,6 %) ab; Bild `vereinen_0_1/vereinen.jpg`: Süd (rot) ohne Dach, Spitze an der Traufe gesucht.
  BENANNTE URSACHE: die Kette gab der dichten Wolke jedes Teils die Schärfe-Sperrliste mit (`dicht_modell --ohne`), die Handfolge nie. Die Sperrliste traf 39 von 101 Süd-Bildern = die Teleaufnahmen des Helms; Kettenwolke Süd 38 Bilder, Handwolke 66 (alle 35 fehlenden stehen auf der Sperrliste). In der Handwolke hängen 71 % der Punkte im obersten Band (0,9-1,05 H) an weniger als 3 ungesperrten Bildern (Mitte 0,4-0,6 H: 23 %); im selben System endet die Kettenwolke tiefer (99-%-Wert 0,83 H gegen 1,01 H).
  Tauschproben (`seiten_vereinen` auf Kettendaten, je eine Eingabe aus der Hand; Ordner `/media/oem/rcdaten/tmp/vereinen_agent/`): Hand-Nord + Ketten-Süd 15,0 % abgelehnt; Ketten-DB gegen Hand-DB gleich (Merkmale in allen DBs identisch); db_seiten/db_mapper haben 0 Querpaare - db_maske ist richtig. Kettenmodelle + Kettenklappung + Ketten-Nordwolke + NUR die Süd-Wolke ohne Sperrliste (Hand, über gemeinsame Beobachtungen ins Kettensystem umgerechnet): VEREINT, Turmhöhen 1,9 %, Achse 0,15 %, Blick 171 Grad, Dach 0,96/1,03, Flanke gleich; Bild `T8/vereinen.jpg` (Süd auf dem Turm).
  FIX: `sfm_seiten_modelle.py` rechnet die dichten Seitenwolken ohne Sperrliste (alle Teile gleich), vermerkt das in `fertig.json` (`sperrliste_angewandt`) und legt eine alte Wolke mit Sperrliste beiseite (`dicht_alt_<zeit>`; `dicht_modell` nähme sonst die alte Bildwahl `sparse_dicht` wieder). `seiten_vereinen.py` nennt bei Höhenablehnung, welche Wolke tiefer endet („fehlt ihr das Dach?“). Prüfgrenzen unverändert. `test_seiten_modelle.py` prüft beides.
  NICHT BELEGT: Süd-Wolke ohne Sperrliste aus den KETTEN-Kameras (globaler Lauf, Brennweite der Telebilder unbestimmt) - erst der nächste Kettenlauf (GPU) zeigt sie; Teil 2 nur gleiche Ursache vermutet (Sperrliste 14 von 52). Nebenbefund: Ketten-Nordwolke Wandlot 5,5 Grad neben dem Kameralot, Boden 3,6 Grad gegen das Wandlot (Hand 0,7) -> `spitze_global` misst ab dem 1-%-Boden der ganzen Wolke, Nord 5,96 statt 5,12 über dem Kameraboden; hebt sich hier auf (B im selben System), bleibt Schwäche.
- Beleg durch Kettenlauf: `kette-martinstor-1121a` (ab sfm, vorhandene Datenbank) läuft seit 21.11. 15:26 - Ergebnis hier nachtragen.

## Versucht (Ergebnis in einem Satz; Einzelheiten in den Quellen oben)
- Schrittweiser Mapper „eng“ über alle Bilder (8,4 h): Südbilder auf der Nordwand verklebt, ein Stück - kein Ausweg.
- Seitenerkennung ohne Masken: Seiten nicht getrennt (Person als Brücke); Maskenfilter nur auf die Paare reichte nicht, erst Masken auch im Paar-Prüfer trennten.
- Schrittweiser Mapper auf der gefilterten Nord-DB: nach 2 h 36 min gestoppt - hing an 31 Restbildern mit fraglichem Motiv (56 Versuche, je 8-10 min Gesamtausgleich); global baut sie in Sekunden ein, der Schärfe-Test sperrt sie. Schrittweise Läufe künftig nur mit `--Mapper.snapshot_path`.
- Urteil „globaler Lauf verformt“ (20.11., Median 2,48 %): Messfehler des nicht robusten Ausgleichs über alle Kameras; robust Median 0,65 %.
- Annahme „Einzelfoto-Streuung ist eine Schwäche des globalen Mappers“: widerlegt (zwei schrittweise Läufe: 12 von 43 Bildern > 2 %).
- Vergleichswerkzeug, erste Fassung (Ausgleich über „die besten 60 %“): das waren Videobilder auf einer Geraden, scheinbar 12-14 % Abweichung - ersetzt durch RANSAC über Vierergruppen.
- Blick-Tor, erste Fassung: fiel am richtigen Nordmodell durch (4 Paare), weil der Paar-Prüfer verschiedene Clips derselben Seite „verwechselt“ nennt - jetzt nur Paare aus verschiedenen Bildteilen.
- Klappung als Lagequelle: stellte den Südturm eine Turmbreite neben den Nordturm, Achse 24,4 % uneinig, abgelehnt (Ursache des Scheiterns vom 19./20.11.) - ersetzt durch eigene Spitze je Modell.
- Klappung als Quelle für Lot und Drehung: 4,52 Grad gekippt, 16,7 Grad verdreht (beides Nutzerfund am 3D-Bild) - ersetzt durch Wandnormalen und Wandrichtungen.
- Massstab der zweiten Seite über die Breitenmessung prüfen: oberhalb 50 % der Höhe streut sie (Süd/Nord 0,75-0,88) - so nicht brauchbar; kein Beleg für < 3 %.
- FlexGlue trennt die Seiten nicht besser (19./20.11., alle 4 Varianten gleich).
- Schwabentor 22.11. (Nulllauf 1122b): Klappung gibt bei verschiedenen Gegenseiten Unsinn (Massstab 0,012) -> Teil A allein -> Lage 20 Grad gedreht. Rückfall Foto-GPS (`tools/seiten_gps_vereinen.py`, in `sfm_seiten_modelle.py`) legt Teil 1 an echten Daten richtig an (Blick-Tor 168 Grad, GPS-Seiten 4 %); Massstab der zweiten Seite nur ±12 %. Globaler Mapper über alles ist KEIN Ausweg: 1120 war verklebt (Blick-Tor 3 von 4). Logbuch `LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md` 22.11. 05:30.

## Offen
Aus `ERKENNTNISSE.md` (Zeilen mit „offen“):
1. Kontaktbogen je Brückengruppe nach der Seitenerkennung.
2. Vorfilter „zu viel Vordergrund“ (286 von 2042 Bildern > 30 %).
3. Kettenlauf als Beleg für den Einbau der Vorstufe.
4. Schärfe-Sperrliste fürs Messen (Kantenstufe, Wandbild, Massstab); zweite Ursache wandernder Videobilder.
5. Kamera je Clip + EXIF-Plausibilität immer vor dem Mapper (Code steht, Beleg am Lauf fehlt).
6. Globaler Mapper je Seite als Standard in der Kette (Vereinen + Kettenlauf fehlen).
7. Motiv-Check vor dem Mapper (erst messen).
8. Vereinen in der Kette.
9. Schwabentor als Geschwister: 798 Bilder = 798 Kameras, Vordergrundanteil noch nicht gemessen.
10. Wolkenkörper (`wolke_rest.py`) im Schleifen-Treiber (gehört zu `METHODE_EBENEN_BAUPLAN.md`).

Weitere offene Punkte aus den Logbüchern:
- Massstab zwischen den Seiten kommt weiter aus der Klappung (Turmhöhen 3,0 % verschieden - Gefälle oder Massstab?); Süd Teil 2 (52-55 Bilder) nicht vereint.
- 162 Nord- und 3 Süd-Bezugsbilder stehen unter „fremd“; die Seitenerkennung löscht auch echte Paare innerhalb einer Seite - Anteil messen.
- Strassenbahn hat im Masken-Netz keine Klasse; Brunnenfigur fälschlich maskiert.
- Belastungsprobe nicht belegt für: Bauten ohne Spitze, ohne rechte Winkel, Verfälschung über 30 Grad / 30 %.
- Der feste Test hat zwei Schwächen von `seiten_vereinen.py` aufgedeckt (als erwartete Fehlschläge im Test, Werkzeug unverändert): Höhenlage von B wird nach der Lot-Berichtigung nicht nachgeführt (bis 0,34 % der Turmhöhe); `geklappt` setzt ähnliches Lot beider Modellsysteme voraus und hat keine Mindestzahl stimmiger Paare.

Rangliste der Recherche (Erwartungen, nichts davon gemessen):
1. Masken-Netz ersetzen: RF-DETR-Seg (Apache-2.0) statt SegFormer-B4.
2. Vereinen: Lot der zweiten Seite aus eigenen Wänden (seit 21.11. 14:55 eingebaut), Massstab aus der Turmbreite statt aus Klappung/Höhe (offen).
3. Seitenerkennung zweistufig: Rückholstufe für die 162 „fremden“ echten Bilder; FlexGlue-Kovisibilität als zweiter Stimmgeber.
4. Globaler Mapper: Streuquelle eingrenzen; Standard „ein Lauf + Schärfe-Sperrliste“ festlegen.
5. Motiv-Vorfilter aus dem Paar-Graphen; schrittweiser Mapper nur noch ohne Sperrbilder.

Lizenz (vor jedem Verkaufsmodell):
- SegFormer-Gewichte (`handy_masken.py`, `video_masken.py`, `gebaeude_segment.py` und damit Schritt 1) = NVIDIA Source Code License, nur nicht-kommerziell (an der Quelle gelesen) -> Ersatz nötig; Vorschlag RF-DETR-Seg ist ungemessen, Trainingsdaten der Seg-Gewichte im README nicht benannt.
- Weitere Befunde der Recherche (Doppelgangers++ und MASt3R CC BY-NC-SA, Pi3-Gewichte CC BY-NC, AnyCalib fehlt im Register) in `modelle/LIZENZ_WERKZEUGE.md` nachtragen.

## Belege
- Bilder: `vereinen_probe.jpg` (Südturm neben Nordturm), `zeigen/vereint_1121.png`, `martinstor_vereint.jpg`, `masken_probe.jpg`; 3D https://claude.ai/artifact/22eEm3PCx5NWmbYTUoiAhQ.
- Daten: `/media/oem/rcdaten/tmp/mt_seiten_1121/` (gefilterte DB, Seitenmodelle, globale Läufe); Bezug 19.11. `/media/oem/rcdaten/tmp/mt_seiten/`.
- Skripte der Handfolge: `tools/versuche/mt_global_gefiltert_1121.sh`, `mt_seiten_mapper_1121.sh`, `vereinen_robust_1121.py`.
- Feste Tests im Schnelltest: `tools/test_seiten_erkennen.py`, `test_seiten_vereinen.py`, `test_seiten_vereinen_robust.py`, `test_seiten_kette.py`.

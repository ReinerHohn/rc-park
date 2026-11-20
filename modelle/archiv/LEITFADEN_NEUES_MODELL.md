# Leitfaden: neues Gebaeude von Null (Stand 13.11.2026)

Quelle: Lektuere aller 140 Dateien `modelle/*.md` durch vier Agenten (Details je Teil in `modelle/analyse_md/teil_1.md` ... `teil_4.md`, jede Aussage dort mit [B] belegt / [A] Annahme / [M] Meinung) plus die Erfahrungen der Erker-Runden dieser Sitzung (`METHODE_MESSEN_DANN_BAUEN.md`). Dies ist die Verdichtung; was hier steht, ist in den Teilen belegt. Nicht selbst nachgeprueft: Werkzeugzustaende (nur aus den Dokumenten, nichts ausgefuehrt).

## 0. Reihenfolge (die wichtigsten Lehren zuerst)
1. **Rahmen zuerst**: Lot, Boden, Kamerahoehe am Foto pruefen, bevor irgendein Fit laeuft. Eine um ca. 25 Grad gekippte Wolke entwertete alle frueheren Sweeps und Overlays (LOGBUCH_2026-11-08 Nr. 22-27; STAND_2026-11-08_LOT_SWEEP_LOOP). Dach-Fehldiagnosen vom 5./6.11. sind wahrscheinlich Folgen davon [A].
2. **Fotos zuerst, aus allen Seiten UND Hoehen**: einseitige Aufnahmen verbiegen Netze (Martinstor Sued, Boden 11-13 m daneben); Dach, Rueckseite, Gewoelbe, Westseite waren der Engpass. Beim Kaufhaus liegen alle kalibrierten Fotos am Erker UNTEN: 19 von 24 Bins (Azimut x unten/eben/oben) ohne Foto -> `tools/ansichten_foto_paare.py` vor dem Bau laufen lassen, Luecken als Aufnahmeauftrag.
3. **Amtliche Hoehendaten zuerst** (LoD2, DOM1/DGM): Quellen mit derselben Luecke bestaetigen sich nicht (Martinstor: LoD2+Scan+OSM 45,3 m, DOM1 54,80 m, allen fehlte der Dachreiter).
4. **Form und Anzahl kommen aus Fotos**, nie aus Wolke/Gitter; Wolke nur Lage und Veto. Anzahlen nur am Foto-Zaehlprotokoll (Baluster: 68, das Fotosignal war 6 % zu eng).
5. **Masse nur mit `tools/foto_mass.py`**, Ebene aus Wolke oder Triangulation mit Schnittwinkel >= 20-45 Grad; Handaugenmasse lagen 20-60 % daneben.
6. **Nutzerform = Sollform**: Benennt der Nutzer eine Form ("Achteck", "geschlossen"), gilt sie, bis ein Foto das Gegenteil zeigt. Nutzer-Sichtfunde waren mehrfach richtiger als Modell und Pruefstand (Tuermchen, Helm 1 m zu tief, Erker-Achteck, Rippen nur an einem Erker). Sofort in ein messbares Kriterium uebersetzen.

## 1. Pruefen
- **Bild vor Zahl**: Modell mit Z-Puffer auf kalibriertem Foto UND Foto neben Modellkanten, aus mehreren Richtungen und Hoehenwinkeln (`rundum_kanten.py`, `ansichten_foto_paare.py`). Die Nutzeransicht (Kanten-Viewer, 'Passendes Foto') nachbauen; kleine Abweichungen (Wasserspeierlaenge, Bogenform der Fenster, Schlussstein, kleiner Balkon) fielen erst auf, als der Nutzer sie einkreiste.
- **Jede Kennzahl braucht eine Nullkontrolle.** Grob-Foto-F1, f1_h/f1_v, SAM-iou, rot+gelb bewerten sogar eine um 90 Grad gedrehte Form besser; fuer Ornament blind (F1 0,574 -> 0,570 mit/ohne Rippen). Nur `f1_fein` trennt; `kosten_lr` ist relativ, Differenzen < ca. 0,01 sind Rauschen (NICHTS_GEBRACHT, SPEC_FLAECHENMASS).
- **Neue Pruefung muss am Altstand ROT sein**, erst danach den Generator aendern; Messwerkzeuge brauchen einen `--synth`-Beweis mit bekannter Wahrheit; Pruefzeilen mit Extrapolation/Selbstbezug sind wertlos.
- **Referenzen verfahrensfremd**: Wolkenkanten und Sweep teilen Fehler; Kantengitter-Referenzen teils zirkulaer (LAGEBILD_KANTENGITTER).
- **Kameraausgleich**: Reprojektionsfehler ist fuer Lagefehler blind (f 2 % = 0,6 m); Leave-one-out (LOG_KAMERA_GUETE), Umeyama aus Kamerazentren, Gegenprobe an unabhaengigen Ankern; Cheiralitaet/Verzerrung pruefen.
- **Linien/Rippen/Tiefe nie aus einem Foto oder Farbschwelle**: Lage im besten Foto, Maske + Skelett, Projektion auf die Modellflaeche, Gegenprobe in Fremdfotos (9-Grad-Paar +-0,27 m, 3. Kamera +-0,13 m); automatische Tiefenfindung scheiterte dreimal (0 von 21 Ketten).
- **Tore**: Spezifitaet vor Einbau beweisen (teile_sichtpruefung: 20 von 22 Teilen rot; Fensterreihen blieben bei 1 m Versatz gruen); Sperren gehoeren in den Code, nicht in die Doku (dieselbe Lehre kam 4-6 mal wieder).

## 2. Bauen
- Parametrische Formfamilien + Wolkenprofil: erst messen, dann fitten. Mesh, 3DGS, Carving als Endmodell scheiterten oder waren nicht besser (kosten_lr: OpenMVS -0,104, Generator -0,052, Carving -0,027, 3DGS -0,061); bei duenner Wolke schlaegt das Handmodell alle Netze.
- Formparameter nie per Kennzahl-Sweep waehlen (Saegezacken bei daechlein_h); nur EINEN Parameter drehen, nie halbieren; nie ein Feature loeschen statt die Eigenschaft zu beheben; erfundene Details sind so falsch wie uebersehene (PROTOKOLL_VALIDATOR F3-F10).
- **Gemessenes auf baugleiche Teile uebertragen und pruefen** ("Wer hat es schon?"-Liste): Rippen nur an Erker 1, Erker 0 hatte die Formel.
- Abgeschaltete Teile listen (`tools/abgeschaltete_teile.py`): Seitengelaender war 2 Tage `stirn_verworfen`.
- Druckreparatur ist geometrieempfindlich: kleine Aenderungen (Rippenkuerzung, Leisten-Absenkung, haengende Rosetten) koennen Teilnetze/Ueberhang kippen; deshalb nach JEDER Aenderung Abnahme.

## 3. Prozess und Betrieb
- Zeitfresser waren Fehllaeufe und Indexfehler, nicht Rechenzeit (vis-Index: 14 von 92 Bildern falsch; Lauf kh22 nicht im Raster ~25 min; GPU-OOM verfaelschte Laeufe).
- GPU-Budget fest (VRAM-Summe <= 6,5 GiB), keine gemeinsame Zwischendatei bei Parallellaeufen, Manifest + Exit-Code + Fehlprobenzaehler je Lauf, Rueckfrage-Stillstand vermeiden (~4 h).
- Agentenberichte nie ungeprueft uebernehmen; der Pruefer bekommt nur Bilder.
- Rauschtor-Nachtlauf (7 h 15 min) und 54 Nachtrunden brachten nichts Sichtbares: Nachtlaeufe nur mit zurueckgesetzten Sperrzaehlern und nachgewiesener Spezifitaet des Tors.

## 4. Offen / Widersprueche (aus den Teilen)
- Registerkuerzel CQ, BR, BT, BS, CO mehrfach vergeben (Teil 1); doppelt vergebene Lehren-Nummern im REZEPT (Teil 3).
- `--aenderung_von` aus SPEC_LOKALES_FOTOTOR fehlt in `tools/teil_fotoform.py` (Teil 1); Specs vom 11.11. (Formfamilie, Flaechenmass, Stoermaske) ohne belegten Umsetzungsstand (Teil 2/3).
- METHODE_AUTO_PIPELINE (Street-View-Rip) widerspricht der Regel "kein Street-View-Scraping" (Teil 1) - nicht verwenden.
- MASSSTAB.md sagt N 1:160, alles andere H0 1:87 (Teil 4); STAND_..._lang.md ist die aeltere Fassung.
- `freiraum_audit` schlaegt in jeder main-Abnahme fehl (Teil 3) - bekannt, nicht neu.
- Kaufhaus: Fassadenbreite 20,4 gegen 26 m ungeklaert (Teil 4); Seitenwand-Fenster (West/Ost-Giebel), Randleiste 5 cm zu hoch, Rippentiefe aus anderen Winkeln, Fensterbogenform am Erker, kleiner Balkon.

## 5. Erste Schritte fuer ein neues Gebaeude
1. Fotoplan: Standpunkte aus allen Seiten, Hoehen (unten, eben, oben - Balkone, Nachbarhaeuser, Drohne wo erlaubt), Dach, Rueckseite, Innenraeume; Massstabstafel/Anker.
2. Amtliche Daten holen (LoD2, DOM1, DGM, ggf. Denkmaldaten); Quellen-Blindheit je Quelle notieren.
3. Kameras kalibrieren, Rahmen (Lot, Boden, Hoehe) am Foto pruefen, Leave-one-out.
4. Stufe 0: Formbeschreibung je Teil aus >= 3 Fotos, Zaehlprotokoll am Foto.
5. Generator-Teile bauen (parametrisch), jedes Mass mit Quelle (`beleg`), Annahmen als `ANNAHME`.
6. Nach JEDEM Bau: Abnahme, `ansichten_foto_paare.py` (alle Bins), `rundum_kanten.py`, Fehlteile; Bilder dem Nutzer zeigen.
7. Nutzer-Sichtbefunde als Testauftrag eintragen, messen, dann bauen.

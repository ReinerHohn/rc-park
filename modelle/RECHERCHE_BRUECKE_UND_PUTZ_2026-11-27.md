# Recherche + Plan: Schwabentor-Brücke als Kettenbaustein (Teil A) und Putz/Bruchstein im H0-Druck (Teil B)

Stand 26./27.11.2026, nur Recherche und Planung (kein Code, kein Rechenjob). Bezug: `modelle/SPEC_SCHWABENTOR_DEMONSTRATOR.md` Anf. 4,
`modelle/PLAN_HANDMODELL_IN_KETTE.md`, KERNMETHODE in `CLAUDE.md`. Kennzeichnung: **BELEGT** = im Repo gelesen oder Quelle mit URL;
**ANNAHME:** = Folgerung oder Rechnung, nicht gemessen.

## 0. Vorab-Suche (`python3 -I tools/wissen_suchen.py`, 26.11. abends)
- `bruecke`: Treffer betreffen fast nur die SfM-"Brücke" zwischen Seitenmodellen (`tools/bruecke_nachmatchen.py`, `tools/bruecke_hebel.py`,
  `modelle/RECHERCHE_PIPELINE_LEHREN_2026-11-23.md` §1: Brücke als eigenes Kleinmodell, Einpassen per `pycolmap.align_reconstructions_via_reprojections`, BSD-3).
  Kein früherer Versuch, das BAUWERK Brücke zu bauen. Achtung, Wortgleichheit: "Brücke" heißt im Repo meist Bildverbindung im SfM.
- `ueberdachter_gang`: nur der Zweig `worktree-agent-af57fdd5b839f216f` (Commit 2c027565e) und der Verweis in `modelle/SPEC_VOLLAUTOMATIK_FOTOS_ZU_3D.md:34` ("noch nicht in der Kette").
- `bauteile`: `modelle/VORLAGE_BAUTEIL_RUNDE.md` (Stufe 0 Formbeschreibung vor Messung), `Doku/projekt/bauteile-kreis.md` (Freistehendes bisher nur Katalog; Katalogteile wirken steif, 17.11.).
- `treppe`: Fallen am Staffelgiebel 11.11.: F1-Sweep eines Parameters ergab Sägezahn statt Treppe; SAM-Flächenmaß konnte Treppe und Sägezahn nicht trennen
  (`modelle/NICHTS_GEBRACHT.md`, `Doku/projekt/kanten-messen.md:49-50`). Lehre: Stufenform am Foto lesen, mindestens 3 Parameterwerte messen. `tools/treppe.py` ist KEINE Bautreppe (Rechenstufen-Leiter).
- `putz` / `relief_aus_fotos`: `Doku/projekt/wolke-wandbild/relief.md` (Martinstor 31.10.: Fugen 0,7 mm, feinere Teilung ging im Druck als Rauschen verloren;
  Mono-Tiefe als metrische Höhe ✗ 11.11.; Putz aus ≥ 3 Einzelfotos glatt, `tools/putz_wandbild.py`, `tools/relief_putz.py`). Malablauf: `Doku/projekt/bahn-anlage.md:37`.
- `Versuchsregister`: LIMAP zweimal gelaufen (BS61 7.11.: 1773 Linien aus Tiefenkarten, 63 % Deckung gegen 36 % Kontrolle; BS65 Kantenzwang im Rauschboden;
  9.11. Prototyp mit Wolkentiefe: Linien meist NICHT auf Fotokanten). **Echte Triangulation ohne Tiefenkarten wurde nie getestet** (NICHTS_GEBRACHT Z. 224).
- Fotolage Brücke (BELEGT, `Doku/projekt/foto-sfm/grundbegriffe.md` "Versucht 26.11."): 144 von 241 Handyfotos (Brücke, Treppe, Unterdurchgang, Treppenturm)
  NICHT registriert; Teilmodelle 1 und 4 (37 neue Fotos, vermutlich Brücke) haben 0-1 gemeinsame Fotos mit dem Hauptnetz = nicht einpassbar.

## TEIL A: Brücke (überdachter Gang mit Treppe) aus Fotokanten

### A1. Abgleich aus dem Netz (NIE Quelle der Form)
- Es handelt sich sehr wahrscheinlich um den **Schwabentorsteg**: überdachte Holz-Fußgängerbrücke, etwa 25 m lang, Metallziegeldach, über den vierspurigen
  Schlossbergring, kürzeste Verbindung Altstadt -> Schlossberg; 1970 gebaut, 2011 wegen Schäden gesperrt, Spätsommer 2012 ersetzt (ca. 220 000 EUR)
  — https://www.waymarking.com/waymarks/WMNARP_Schwabentorsteg_Freiburg_BW_Germany . Structurae nennt dagegen 1984 als Fertigstellung
  (https://structurae.net/structures/schwabentorsteg, Seite lieferte 403, nur Suchauszug) — Baujahr widersprüchlich, für uns ohne Belang.
- Wegbeschreibung: vor dem Tor links die Treppe hinauf und über die Straße zum Schlossberg (Suchauszug, Quelle unter https://visit.freiburg.de/en/schwabentor-swabian-gate bzw. Wanderseiten, nicht nachgelesen).
- Turm: Bau um 1250/70, 1901 erhöht, Erhöhung 1954 zurückgebaut (https://bawue.museum-digital.de/pdf/object/29182.pdf?lang=de). Keine Turmmaße im Netz gefunden.
- **Folgerungen für den Baustein (ANNAHME, am Foto zu prüfen):** (1) Ende a = Treppenaufgang neben dem Tor, Ende b = Schlossberghang, also KEINE zweite Fassade;
  (2) Seiten vermutlich offen mit Brüstung und Pfosten; (3) Satteldach; (4) Zwischenstützen über dem Mittelstreifen möglich (25 m Holz) — unbekannt.
  Das Abgleichmaß 25 m dient nur als Warnschwelle (Kette außerhalb 18-32 m -> Meldung "Abgleich verletzt", kein Wert).

### A2. Bewertung des vorhandenen Zweigs `worktree-agent-af57fdd5b839f216f` (nur gelesen)
- Inhalt (Commit 2c027565e, +389 Zeilen): `bauteile.ueberdachter_gang(P)`, `treppen_profil`, `ueberdachter_gang_aus_json`, `als_trimesh`; Test `tests/test_ueberdachter_gang.py`
  (46 Prüfungen, rot belegt, Zufallsprobe 150 Fälle); Zeile in `tools/schnelltest.sh`.
- Gut: alle Maße aus einem dict, keine Objektzahlen; Achse a->b im Modellrahmen; "Quellen nicht mitteln" (Spannweite gegen Achse > 5 cm = nicht gebaut);
  Mindestmaß 0,8 mm bei 1:87; ein Körper + wasserdicht als Endkontrolle; Treppe innen/außen, Rampe bei zu kleinen Stufen.
- Lücken gegenüber der echten Aufgabe:
  1. **Keine Messung**: Kopplung an Fotokanten fehlt ausdrücklich ("nicht Teil dieses Auftrags"). Das ist der eigentliche Teil A.
  2. **Ende b auf Gelände** fehlt (nur zwei Fassaden mit `einbinden` 0,10 m, im Code als ANNAHME markiert). Benötigt: Auflager auf Geländekörper (DGM1-Höhe am Ende b).
  3. **Zwischenstützen** fehlen (senkrechte Kanten unter dem Boden).
  4. **Streben/Fachwerk** in offenen Seiten fehlen; die Galerie in `tools/bauteile.py` hat Streben — wiederverwenden statt neu.
  5. **Stille Ersatzformen**: "massiver Steg", "ohne Treppe", "ohne Seitenfelder" sind Fallbacks mit Beleg, aber laut PLAN §3 ("kein stiller Kasten-Fallback")
     muss jeder davon das Bestand-Tor ROT mit Bauteilname melden. Heute nur `hinweis`-Text.
  6. Treppe nur gerader Lauf in Gangachse; ein seitlich angesetzter oder gewendelter Aufgang ist nicht abbildbar (ANNAHME: der Aufgang am Tor kann quer zur Achse liegen — Foto klären).
  7. Jeder Parameter braucht eine **Quelle je Wert** (Messprotokoll-ID, Fotos, Streuung), heute nur ein Sammelfeld `quelle`.
- Urteil: als Bau-Kern brauchbar, nicht als Kettenstufe. Empfehlung: Zweig nach main erst zusammen mit Stufe B2/B3 (unten), sonst liegt ein Baustein ohne Messung im Generator (Versuchung zum Handeintrag).

### A3. Bauplan als Kettenstufe `bruecke` (Reihenfolge = Abhängigkeit)
**B0 Kameras (Voraussetzung, heute ROT).** Ohne eingeordnete Brückenfotos gibt es keinen Sweep. Weg: (a) gemeinsamer Mapper über alle 677 scharfen Handyfotos
mit ALIKED+LightGlue (schon "Offen" in grundbegriffe.md), oder (b) Brücken-Teilmodell starr einpassen über Fotos, die Turm UND Brücke zeigen
(`align_reconstructions_via_reprojections`, nie verformen). Tor: Einpassrest < 0,10 m an gemeinsamen Punkten, Maßstab gegen Turmmaß (nicht GPS allein),
GPS-Gegenprobe falls die Handyfotos GPS tragen (ANNAHME: ungeprüft). Scheitert B0 -> Stelle "Brücke nicht belegt" + Fotoauftrag (A5), nicht bauen.

**B1 Zone (wo ist die Brücke).** Drei unabhängige Belege, keiner allein entscheidet: (1) DOM1 minus DGM1 = erhöhter Streifen ~3-6 m über der Straße quer über den Ring
(Lage-Veto + Höhe, Kernmethode erlaubt DOM1 dafür); (2) Sweep-Kantenpunkte oberhalb Straßenniveau außerhalb der Turm-LoD2-Hülle; (3) Lücke/Anschluss im Wandbild
des angrenzenden Bauwerks (Erkennen = nur Zone). Ergebnis: Hüllquader (Achse grob, Länge, Höhe) als Suchraum, nicht als Form.

**B2 Kanten-Tiefen-Sweep in der Zone.** `tools/kanten_tiefe_sweep_flaeche.py` mit Messkörper = Hüllquader aus B1, `--vorn`/`--band` großzügig (Dachüberstand),
`--huelle` (Traufe vor Himmel), Stabilitätskarten wie `kantenstufe.py`. Ebenen wie `ebenen_bauplan.py`: zwei Längsseiten, Unterseite (von der Straße), Dachflächen, Treppenzone.
Danach 3D-Geraden per RANSAC wie in `kanten_feld3d.py` Schritt 5.

**B3 Maße aus Kanten (Massliste im Hand-Protokoll-Format, `quelle: auto`, Fotos, Streuung).** Je Parameter des Bausteins:
- Achse a->b: Richtung der längsten, parallelen Kantenbündel; Enden = wo die Bodenunterkante endet (Fassade / Gelände). -> `achse`, `spannweite`.
- Unterkante Boden und Oberkante Boden (Stirnbrett, zwei waagrechte Geraden an der Seite) -> `z_boden`, `boden_dicke`.
- Traufkanten beidseits -> Außenbreite + `dach.ueberstand`; Firstlinie -> `dach.neigung_grad` aus (z_First − z_Traufe) / halber Breite; Dachform aus Zahl der Dachgeraden (1 = pult, 2 = sattel).
- Brüstungsholm (waagrechte Gerade zwischen Boden und Traufe) -> `seiten.bruestung`; Riegel unter dem Dach -> `seiten.riegel`.
- Pfosten: senkrechte Kantenpaare an der Seite -> Lage; **Zahl nur am Foto** (`tools/foto_zaehlung.py`, ≥ 3 Fotos einig), Breite per `tools/foto_mass.py`.
- Wanddicke/Pfostenbreite unter Messbarkeit: aus den Fotos abgeleitet (Schattenbreite, Nachbarmaß) als ANNAHME mit Herleitung, sonst Druck-Mindestmaß.
- Treppe: Schar paralleler waagrechter Stufenkanten in der Treppenzone; Stufenzahl am Foto zählen; Steigung s und Auftritt a aus der Regression der Kantenhöhen
  und -lagen über die Stufennummer (Gerade, nicht Autokorrelation allein — Falle Periodenschätzer 03.11. springt auf Oberwelle); Hub gegen DGM1/Straßenhöhe gegenprüfen.
  Plausibilität (nur Meldung, keine Quelle): Schrittmaß 2s + a etwa 0,59-0,65 m.
- Stützen: senkrechte Kanten unter der Bodenunterkante bis Straßenniveau -> neue Parameter `stuetzen` (Lage längs, Querschnitt).
Fehlt ein Maß: erst weitere Fotos/Kameras derselben Stelle (PLAN §2b), nie fester Wert, nie aus schwab_v3 (hat keine Brücke) oder aus dem Netz-Abgleich.

**B4 Bauen.** `bauteile.ueberdachter_gang` mit den Ergänzungen aus A2 (Ende Gelände, Stützen, Streben aus Galerie, Fallback = ROT). Generator ruft nur auf.

**B5 Tore.** Foto-F1 je Teil `bruecke` (`tools/teil_fotoform.py`) auf festem Fotosatz, Paarvergleich `tools/foto_tor_bezug.py`, `audit/neben_bruecke.jpg`
neben Foto, Tauschtest, Wolke nur Lage-Veto. Abnahme: Nutzer sieht Bild "Foto neben Modell" (SPEC Hauptkriterium).

### A4. Prüfungen (je eine rote Probe vorab)
1. **Synthetik Kanten -> Parameter** (CPU, < 30 s): bekannte Brücke mit `ueberdachter_gang` bauen, mit 12 künstlichen Kameras rendern (wie `tests/test_ebenen_modell`-Stil),
   Kantenbilder -> B2/B3 -> Parameter. Soll: Spannweite, Breite, Höhen je < 3 cm, Stufenzahl exakt, Pfostenzahl exakt. Rot vorab: Modul fehlt (ImportError), dann Variante "Kamera 1,2 m verschoben" muss scheitern.
2. **Tauschtest** (gegen zirkuläre Messung, Memory 25.11.): Hüllquader aus B1 um ±30 % in Länge/Höhe verändert -> gemessene Parameter gleich (Toleranz wie 1). Rot, wenn die Messung am Vormodell klebt.
3. **Treppe Oberwelle**: Synthetik mit 14 Stufen, Rauschen auf jeder zweiten Kante -> Ergebnis 14, nicht 7 oder 28. Rot belegt mit reinem Autokorrelationsschätzer.
4. **Sägezahn gegen Treppe**: Synthetik Rampe mit Kerben gegen echte Treppe -> beide getrennt erkannt (Falle 11.11.).
5. **Kein stiller Fallback**: Sweep ohne Kanten in der Zone -> Stufe meldet "Brücke nicht belegt" + Bestand-Tor ROT; nie massiver Steg/Kasten. Rot gegen den heutigen Zweig (der baut still einen Steg).
6. **Quellen nicht mitteln**: Spannweite aus Kanten widerspricht Achse aus DOM1-Streifen um > 0,3 m -> nicht gebaut, Meldung (Zweig hat das schon für Achse/Spannweite).
7. **Druckbarkeit**: alle Teile ≥ 0,8 mm, ein Körper, wasserdicht (im Zweig vorhanden).

### A5. Minimalfotos (Standpunkte, GPS im Handy AN)
- Anschluss: mindestens 5 Fotos, die Turm/Tor UND Brückenanfang zeigen (Pflicht für B0-Einpassung), aus 2-3 Standpunkten auf dem Platz.
- Jede Längsseite: 3-4 Fotos schräg von Gehweg/Straßenrand, Standpunkte 3-5 m versetzt (Blickwinkel 15-20° auseinander), Abstand 15-25 m, ganze Brücke im Bild.
- Unterseite: 2-3 Fotos von Gehweg/Mittelinsel unter der Brücke (Bodenunterkante, Stützen) — nur bei sicherer Lage, kein Stehen auf der Fahrbahn.
- Treppe: 3 frontal + 3 seitlich (Stufenkanten mit Streiflicht, nicht Gegenlicht), dazu 1 Foto von oben den Lauf hinab.
- Dach: 2-3 Fotos erhöht vom Schlossberg-Weg (First, Neigung, Ende b auf dem Hang).
- Innen: 2 Fotos längs durch den Gang (lichte Höhe, Brüstung innen).
- Zusammen ~25-30 Fotos; Querformat, scharf, bewölkt besser als harte Sonne (Schattenkanten = Scheinkanten).

### A6. Risiken
- **B0 scheitert** (Hauptrisiko, heute Zustand): ohne Kameras keine Form — dann nur Fotoauftrag.
- Holzlattung/Ziegel = sich wiederholende Muster -> falsche Matches im SfM und falsche Kantenzuordnung im Sweep (Doppelkanten im Abstand der Latten).
- Verkehr, Straßenbahnleitungen, Ampeln, Bäume vor der Brücke -> Scheinkanten (Fahrleitung ist eine lange waagrechte Gerade wie eine Traufkante!). Gegenmittel: Mehrfoto-Stabilität, Kante muss auf der Hüllfläche liegen.
- Dach und Oberseite vom Boden kaum sichtbar -> Neigung nur aus Fotos vom Hang.
- Ende b Gelände/Hang und mögliche seitliche Treppe passen nicht in den heutigen Baustein (A2 Punkte 2, 6).
- Druck: 25 m / 87 = **287 mm** > Bett P1S (256 mm) und MK4S (250 mm). Diagonal auf dem P1S passt rechnerisch (Diagonale 362 mm, ANNAHME Gangbreite ~3 m = 35 mm),
  sonst Teilung an einer Stütze/Pfostenachse. Geländerstäbe (~4 cm = 0,46 mm) sind unter Mindestmaß -> als Brüstungsfläche, Farbe zeigt Stäbe.

### A7. Mehrsicht-Linienverfahren (Netzrecherche, mit Lizenz)
- **LIMAP** (cvg, ETH; CVPR 2023 "3D Line Mapping Revisited"): Lizenz BSD-3-Clause laut Repo (https://github.com/cvg/limap). Startet von COLMAP-Kameras;
  Standard ist Triangulation, Tiefenkarten nur mit `--use_dense_depth`. Detektoren LSD, SOLD2, HAWP, TP-LSD, DeepLSD; Matcher u. a. GlueStick, SuperPoint-Endpunkte.
  Lizenzstand im Repo (`modelle/LIZENZ_WERKZEUGE.md` Z. 204-208): Code ja, nur mit LSD oder geprüften Detektoren, **kein SuperPoint** (nur Test).
  Neu für uns: der Triangulationsweg OHNE Tiefenkarten wurde nie gemessen (bisher nur Tiefen-/Wolkenweg, Ergebnis schwach). Eine Holzbrücke besteht fast nur aus Geraden — guter Prüffall.
- **Line3D++** (manhofer): **MPL-2.0** laut README (https://github.com/manhofer/Line3Dpp); liest COLMAP (`cameras.txt`, `images.txt`, `points3D.txt`), VisualSfM, OpenMVG.
  MPL-2.0 ist verkaufstauglich bei Nutzung als eigenes Programm; Änderungen an MPL-Dateien müssen offengelegt werden. In LIZENZ_WERKZEUGE.md bisher "ungeprüft" (Z. 144) -> nachtragen.
- Vorschlag (über Skill `versuch-messen`, erst wenn GPU/CPU frei): auf der Brückenzone A/B `kanten_tiefe_sweep_flaeche` gegen LIMAP-Triangulation (LSD) gegen Line3D++,
  Maß = Anteil 3D-Kanten mit Deckung auf einem zurückgehaltenen Foto gegen 1,2-m-verschobene Kontrolle (wie BS61). Gewinnt nur, wer auf dem Halte-Foto besser ist.

## TEIL B: Putz und Bruchstein bei H0 (1:87) realistisch

### B1. Was bei 1:87 überhaupt sichtbar ist (ANNAHME: Rechnung)
- Putzkorn 1-3 mm -> 0,01-0,03 mm: als Geometrie unsichtbar. Putz wirkt in H0 durch **matte Oberfläche und leicht wolkige Tönung**, nicht durch Rauheit.
  Grobe Rauheit (Sand, Fuzzy Skin) liest sich als Kies oder Spritzbewurf, nicht als Putz.
- Bruchstein 20-50 cm -> 2,3-5,7 mm (gut sichtbar); Fugen 2-5 cm breit -> 0,2-0,6 mm, 1-3 cm tief -> 0,1-0,35 mm: **unter dem Druck-Mindestmaß 0,8 mm**.
  Repo-Erfahrung Martinstor 31.10.: Fugen 0,7 mm funktionierten, feinere Teilung ging als Rauschen verloren (BELEGT, relief.md). Also: Steinform im Druck, Fugen etwas verbreitert/vertieft drucken ODER flach lassen und mit Lasur zeichnen.
- Schichtlinien: 0,1 mm Schicht = 8,7 mm im Original — waagrechte Riefen, die es an Putz nicht gibt; bei Streiflicht der deutlichste "Druck-Verräter".

### B2. Druckeinstellungen
- Schichthöhe höchstens 70-80 % des Düsendurchmessers (https://help.prusa3d.com/article/layers-and-perimeters_1748); kleine Schichthöhe (z. B. 0,10 mm) gibt mehr Detail bei längerer Zeit (ebd.).
- 0,25-mm-Düse: feineres Detail, aber deutlich längere Druckzeit, nur für kleine Teile empfohlen; Unterschied zu 0,4 mm "nicht so dramatisch", vor allem dünne Linien profitieren
  (https://blog.prusa3d.com/everything-about-nozzles-with-a-different-diameter_8344/). Forum: 0,07 mm ist für 0,25 mm eher zu niedrig, 0,1 mm versuchen; trockenes Filament, Live-Z neu einstellen
  (https://forum.prusa3d.com/forum/english-forum-original-prusa-i3-mk4-how-do-i-print-this-printing-help/best-settings-for-28mm-miniatures-for-mk4-and-025mm-nozzle-using-pla — Nutzerberichte).
- Prusa-Beispiele: H0-Gebäude auf FDM mit 0,15 mm Schicht (https://blog.prusa3d.com/de/3d-gedruckte-eisenbahnmodelle-teil-ii-zuege-und-gebaeude_30758/).
- Fuzzy Skin wirkt nur auf die Außenkontur; kleinerer Punktabstand = mehr Zufallspunkte (https://wiki.bambulab.com/en/software/bambu-studio/parameter/fuzzy-skin);
  Gemeinschaftswerte 0,1-0,6 mm für Dicke/Punktabstand (Forum/MakerWorld, nicht amtlich, https://forum.bambulab.com/t/fuzzy-skin-point-distance/238206).
  ANNAHME: 0,1 mm Dicke = 9 mm im Original -> höchstens Rauputz/Sockel, für glatten Putz zu grob; Bambu Studio soll senkrechte Streifenfehler zeigen, Orca nicht (Forumsbericht, ebd. Suchergebnisse).
- Ironing glättet nur Deckflächen (ANNAHME aus Funktionsweise, Quelle nicht gelesen): nützt bei liegend gedruckten glatten Putzwänden, zerstört aber Relief — nur reine Putzflächen.
- ANNAHME Ausrichtung: Wand **liegend (Ansicht oben)** = keine Schichtriefen in der Fläche, Relief in Schichthöhe aufgelöst (0,1 mm Schritte) — gut für Bruchstein;
  Wand **stehend** = Riefen waagrecht, Fugenbreite in XY sauber, braucht Füllen. Beides im Test vergleichen.

### B3. Nachbearbeitung FDM
- Grob schleifen 120-220, PLA nass schleifen (wird sonst warm und schmiert); im Wechsel mit Füllergrundierung, bis die Fläche als eine Ebene wirkt; Beispiel: 3 Lagen Füller, Nassschliff 400;
  Glanzstellen nach dem Schleifen = Senken, mit Spachtel (Tamiya) füllen (https://www.matterhackers.com/articles/how-to-smooth-and-finish-your-pla-prints,
  https://formlabs.com/global/blog/painting-3d-printed-parts/, https://hackaday.com/2017/11/15/visual-3d-print-finishing-guide). Bei großen Schichthöhen ggf. ganzes Modell schleifen (Formlabs).
- ANNAHME: Schleifen zerstört 0,7-mm-Fugen und Kanten — bei Reliefwänden nur füllen, nicht schleifen; Schleifen nur an glatten Putzfeldern.
- ANNAHME: Die vorhandene Army Painter **Air** Primer (für Airbrush, dünn) füllt Schichtlinien NICHT. Füllen soll der vorhandene "3D Printing Water-Based Sealant" (Etikett prüfen, ob als Füller gedacht);
  falls nicht ausreichend: Füllergrundierung (Spraydose) als Einkauf vorschlagen — Nutzer entscheidet.

### B4. Struktur und Bemalung (Krippen- und Modellbau)
- Fertigware als Vergleich: Faller Texturpaste für H0/N/TT/Z (https://faller.de/en/model-layout-construction/tools-utilities/1021/texture-paste-200-g),
  NOCH Strukturfolien aus Quarzsand/Gesteinsmehl, nicht unter 15 °C verarbeiten (https://www.noch.com/3d-structured-foil-quarrystone-wall/60371, https://www.noch.com/layer-masonry/60370).
- Krippenbau-Putz: Leim + Wasser + Grundkreide, dann Schleif-/Sägemehl zu teigiger Masse (https://www.selbst.de/ruinen-krippe-1603.html); schneller mit Außen-Moltofill, Putz mind. 2 Tage trocknen
  (https://www.selbst.de/bauplan-orient-krippe-22153.html). ANNAHME: für H0 nur stark verdünnt und getupft (steifer Pinsel), Schleifmehl/Sand sind maßstäblich Kies — nur Sockel/Bruchstein.
- Grundierfarbe: dunkle Grundierung, wenn vor allem trockengebürstet wird (Tiefen bleiben Schatten); helle (Knochen/Hellgrau), wenn mit Washes gearbeitet wird
  (https://www.printablescenery.com/2026/04/17/7-ways-to-improve-your-terrain-painting/). Grundierung haftet am Kunststoff und gibt der Farbe Halt (Printable Scenery, Steinscheune).
  ANNAHME: Matt Grey liegt dazwischen und passt für beides.
- Dunkle Grundierung bleibt in Fugen und Vertiefungen stehen (Model Rail UK, https://www.pressreader.com/uk/model-rail-uk/20180301/282381220017213); Wash mit Wattestäbchen
  zurückwischen, senkrechte Striche wie Regenwirkung (https://world-of-railways.co.uk/techniques/weathering-model-trains--top-tips-and-techniques).
- Repo-Malplan (BELEGT, bahn-anlage.md): Putz grau grundieren -> gebrochenes Weiß/Hellocker dünn in Schichten -> graubraune Lasur -> Mattlack; Sandstein rotbraun -> dunkle Lasur in Fugen -> heller Trockenpinsel.

### B5. Testplan Wandstück (nur auf Nutzerwunsch drucken)
Ausschnitt: ein Stück Schwabentor-Wand mit Bruchstein-/Quadersockel unten und Putz oben aus dem Kettenmodell, etwa 40 x 40 mm, viermal gedruckt.
Platte A stehend 0,10 mm mit 0,4-mm-Düse; Platte B liegend (Ansicht oben) 0,10 mm; Platte C stehend mit Fuzzy Skin nur im Sockelbereich (Dicke 0,1 mm, Punktabstand 0,3 mm,
Bambu, als Modifier); Platte D wie A, aber 0,25-mm-Düse und 0,08-0,10 mm, falls die Düse vorhanden ist (ANNAHME: nicht geprüft).
Jede Platte halbieren (Abklebeband senkrecht): linke Hälfte zwei dünne Lagen Sealant, trocknen lassen, rechte Hälfte roh. Dann beide Hälften zwei dünne Pinsellagen Matt Grey.
Auf einen 10-mm-Querstreifen im Putzfeld verdünntes Moltofill tupfen (nur wenn vorhanden; sonst weglassen). Putzfeld: gebrochenes Weiß/Hellocker (Warpaints, aufgehellt) in 2-3 dünnen Lagen.
Sockel/Fugen: OBI-Anthrazit + Rehbraun stark verdünnt als Lasur (ANNAHME Mischung etwa 1 Teil Farbe auf 8-10 Teile Wasser, Tropfen Spülmittel), einlaufen lassen, nach 1-2 min senkrecht mit Wattestäbchen zurückwischen.
Trocken: heller Trockenpinsel auf die Steinköpfe. Zum Schluss Homy Arty Mattlack auf alles.
Bewertung je Platte und Hälfte: Foto aus 30 cm (Betrachtungsabstand Anlage) und Streiflicht-Makro; daneben derselbe Ausschnitt aus einem echten Foto in gleicher Größe.
Fragen: Sind Schichtlinien bei Streiflicht zu sehen? Sind Fugen aus 30 cm als Fugen lesbar? Wirkt der Putz matt-wolkig oder plastisch-glatt? Hat das Sealant die Fugen zugesetzt?
Ergebnis eine Zeile je Platte ins Logbuch (`Doku/projekt/modellbau-druck.md` Versucht), Sieger wird Standard für den Demonstratordruck.

## Fehlerliste / Unsicherheiten (vor jedem Lob)
- Brückenidentität (Schwabentorsteg) und Endenlage (Treppe am Tor, Ende b am Hang) nur aus Netztexten erschlossen — am Foto prüfen.
- B0 (Kameras für Brückenfotos) ist heute ungelöst; der ganze Teil A hängt daran.
- Der Zweig `ueberdachter_gang` deckt Ende-auf-Gelände, Stützen, Streben und seitliche Treppe nicht ab; seine Fallbacks sind still (nur Hinweistext).
- Structurae-Seite nicht lesbar (403); Turmmaße im Netz nicht gefunden.
- LIMAP-Lizenz nur über Repo-Kopfzeile, Drittkomponenten weiter ungeprüft; Line3D++ MPL-2.0 aus README, LICENSE-Datei nicht einzeln gelesen.
- Teil B: keine Quelle prüft PLA-Wände in 1:87 direkt; Ironing-Aussage ohne gelesene Quelle; Sealant-Füllwirkung und 0,25-mm-Düse beim Nutzer ungeprüft; Lasurmischung ANNAHME.
- Nichts gerechnet, nichts gedruckt; alle Zahlen zu Sichtbarkeit sind Maßstabsrechnungen.

# Plan: aus allen Daten zu sehr gut detaillierten, druckbaren H0-Modellen (Martinstor, Historisches Kaufhaus, jedes weitere Gebaeude)

Geschrieben 5.11.2026 abends aus `LOG_2026-11-05_FEHLER_UND_STAND.md`, `STAND_2026-11-05.md`, `UEBERGABE_2026-11-04.md`,
`kaufhaus/versuche.jsonl`, `reports/*.md` und dem Versuchsregister. Nutzervorgabe: **so automatisch wie moeglich.**
Alles, was hier steht, laeuft als Stufe in `tools/nullstart.py` (Nachtlauf je Gebaeude). Handanteil des Nutzers: Bestell-Mails, eigene Handyfotos,
Drucker bedienen. Sonst nichts.

## 0. Was die Fehler vom 5.11. lehren (jede Lehre wird eine Regel im Laeufer, nicht ein Vorsatz)

| Fehler (LOG Abschnitt 2) | Regel, die ihn technisch unmoeglich macht | Wo sie lebt |
|---|---|---|
| 1 Handvarianten, Handschwellen (15 %, 0,25 m, 0,3 m) | Jede Schwelle ist ein Kandidatenparameter des Laeufers mit Suchbereich; `hardcode_finden.py` schlaegt bei neuen Festwerten im Generator an (Exit 2 im Pruefstand) | qualitaetsstufen, pruefstand |
| 2 Uebernahme bei "nicht deutlich schlechter" (t < 2) | **Uebernahmetor**: in JEDEM bewertenden Foto beide Werte (rot/gelb) nicht schlechter UND in der Summe deutlich besser, Restfeld je Ebene nicht schlechter, Pruefstand gruen, druckbar. Sonst Widerspruch, kein Mitteln | qualitaetsstufen `tor_ok` (erweitern) |
| 3 grobe Kantenmetrik 9 cm lange behalten | `--mehrstufig` wird Standard, sobald `test_foto_diff` T0-T6b + Regression bestanden; Pruefbild-Skala steht im JSON jedes Ergebnisses | foto_diff, regression |
| 4 Viewer mit alter Wolke gezeigt | Viewer wird vom Laeufer gebaut (`viewer_bauen`), liest Wolke/Modell/Kameras aus demselben Lauf-Ordner; Hand-Viewer verboten | nullstart Schritt `viewer` |
| 5 Rueckschritt Boegen (gutes Altmodell verloren) | **Elementbuch**: je Fassadenelement bester bekannter Stand mit Kennzahl; ein Lauf darf ein Element nur ersetzen, wenn das Element lokal besser wird (nicht nur die Summe) | neue Datei `elemente_best.json` je Objekt |
| 6 Boegen als Tunnel | Oeffnungen/Hallen/Nischen ALLGEMEIN aus Sichtstrahlen (freiraum_*), nie je Bauteilklasse | freiraum_oeffnungen -> fassade_auto |
| 7 reiner Fotofit (Pfeiler 0 m) | Jeder Fit braucht zwei unabhaengige Quellen (Foto + Wolke/Laser/Dokument); eine Quelle = Beobachtung, nie Sollwert | pruefstand Quelltyp-Regel |
| 8 1-5 Prozentpunkte als Fortschritt verkauft | Bericht je Lauf = Bild vorher/nachher je Foto + Anteil "Foto ohne Modell" je Fassade; Fortschritt heisst: Anteil faellt UND im Bild sichtbar | `lauf_bericht.py` (neu, Schritt `bericht`) |
| 9 eigene CPU-Tests neben Nachtlauf | Ressourcen-Sperre: `job_start.sh` setzt Lock; Tests warten auf freie GPU/CPU (`gpu_warten` + CPU-Lock) | job_start.sh |
| 11 Testbauten im Speicher kaputt | Tests nur auf Kopie des Generators; Generatorsperre waehrend Laufen (`aenderung_check.py` prueft Hash) | bauen_abnehmen |
| 13 Videos erst nach Ruege | Schritt `video` ist Pflicht im Nullstart (video_suchen -> Frames -> SfM -> ausrichten -> mergen) | nullstart Pflichtliste |
| 14 Sichtfund direkt gebaut | Sichtfund = Zeile `beobachtungen_offen` + fehlschlagende Pruefung, bevor der Generator angefasst wird; Pre-Commit-Hook prueft, dass jede Generatoraenderung eine zugehoerige Pruefung hat | git_hooks/pre-commit |

Zusaetzliche Lehren aus den Zahlen:
- Globale Kennzahlen (Freiraum-Volumen, 12-Foto-Kantenwert) sind **nicht monoton** mit der Modellguete. Konvergenz wird nur lokal je Fassadenzelle gemessen.
- Hauptproblem Kaufhaus ist nicht Falschform (rot 12-19 %), sondern **fehlende Bauteile** (gelb 48-59 %). Der Plan muss zuerst Bauteile finden, nicht Parameter polieren.
- Lokaler Kameraversatz (0,35-1,3 m je Bildzone) begrenzt jede Detailmessung. Ohne Feinlage je Foto ist "10 cm" nicht erreichbar.

## 1. Ziel und Masse

- Massstab 1:87. Druckaufloesung: 0,4-Duese -> kleinstes Merkmal 0,34 mm = **3 cm real**; 0,2-Duese -> 0,17 mm = **1,5 cm real**.
  Modellziel bleibt 10 cm je Bauteil (Memory `ziel-10cm-genauigkeit`); Sprossen/Gesimse unter 10 cm kommen nur aus Zaehlung + Klassenregel, nicht aus Messung.
- "Sehr gut detailliert" heisst messbar: je kalibriertem Foto Anteil "Fotokante ohne Modellkante" (mehrstufig, Verdecker maskiert) **< 25 %** auf allen Fassaden,
  Anteil "Modellkante ohne Fotokante" **< 10 %**, alle Zaehlmerkmale (Fenster, Boegen, Zinnen, Giebelstufen, Figuren) = Foto-Zaehlung, Pruefstand gruen, 1 Koerper wasserdicht, Teile im Bauraum.
  Heute Kaufhaus: gelb 48-59 %, rot 12-19 %. Martinstor: Pruefstand gruen, Sued offen.
- Fertig ist ein Modell erst mit dem Abschlusstor (Stufe 8), nicht wenn es im Viewer gut aussieht.

## 2. Daten: alles nutzen, jede Quelle mit eigener Blindheit

| Quelle | Stand | Automatisierung | Blind fuer |
|---|---|---|---|
| LGL LoD2, DOM1, DGM1, DOP20 | vorhanden, im Nullstart | fertig | LoD2: Aufbauten; DOM1: < 3 m, Fassade, steile Helme |
| Stadt-Freiburg-LoD2 (DL-DE BY 2.0) | NEU, noch nicht geladen | Schritt `quellen`: GML laden, Gebaeude per ALKIS/OSM-Umriss schneiden, als **zweite Dachquelle** in die Masstabelle (nicht mitteln mit LGL) | wie LoD2 |
| Stadt-Mesh 2025 (Cesium-Tiles) | Lizenz ungeklaert | nur Pruefreferenz: Lader fuer tileset.json, Overlay + foto_diff gegen Mesh; Mail an vermessung@freiburg.de (Nutzer) | Textur-Glaettung, Aufloesung unbekannt |
| bDOM 0,2 m, ALS-Rohpunkte | Bestellentwuerfe liegen | Nutzer sendet Mails; Import wie DOM1 mit eigener Blindheitszeile | bDOM: steile Flaechen, Schatten |
| Mapillary, Wikimedia, Web-Fotos | im Nullstart (`bilder_holen`) | fertig | keine Masse ohne Anker |
| Videos (Drohne, Stadtrundgang) | Kaufhaus: Kandidaten gefunden (A1I7VjZXGlU, Bbzk0Qpb5l0, -mtFRFLeLZ0, Lwix1LAxooI ...), Stufe nicht gelaufen | Schritt `video` Pflicht: Frames -> SfM-Fragmente -> ausrichten -> verdichten -> mergen; Lizenz je Clip in LIZENZ_BILDER | Rolling Shutter, Kompression |
| eigene Handyfotos | Kameraprofil `modelle/kamera_profil/` | Eingangsordner wird automatisch einsortiert (`fotos_einsortieren`) | Nutzer muss hingehen |
| Dokumente (LAD, Loebbecke-Bauforschung) | teils | nur Zahlen/Zaehlungen mit Quelle, nie Form | Form |
| OSM, ALKIS | im Inventar | fertig | Hoehe |

Regel: `quellen_inventar.py` Exit 2, solange eine verfuegbare Quelle ungenutzt ist. Stadt-LoD2 und Video-Stufe sind heute solche Luecken.

## 3. Die Pipeline (ein Nachtlauf je Gebaeude, `nullstart.py <objekt> --stufen`)

Jede Stufe: Tor mit Exit-Code, Beweis (synthetisch + Kaufhaus + Martinstor + Bild angesehen), Platzpruefung vorher, Aufwand-Log, Bericht.

### Stufe 0 Vorbereitung (vorhanden, haerten)
Platzpruefung (Root und Datenplatte), Quellen laden, Lizenzliste, Kameraprofile. Abbruch mit klarer Meldung statt Errno 28 mitten in Stufe 4.

### Stufe 1 Kameras (vorhanden, bewiesen)
Merkmale GPU, LightGlue, Mapper, Buendel an amtliche Anker, Kamera-Bruecke-Tor, dichte Wolke, Textur. Offen: globaler Mapper parallel als Kandidat (Beschleunigung, verlustfrei pruefen).

### Stufe 2 Grobform (vorhanden)
LoD2 + Stadt-LoD2 + DOM1/DGM1 -> `rumpf_lod2`, Giebel gezaehlt und trianguliert, Parameter gegen Fotos (`kosten_lr`), Pruefstand-Tor an jeder Uebernahme.
Widerspruch First (Foto 20,3 vs LoD2 20,8-21,0) bleibt offen, bis Stadt-LoD2 oder bDOM als dritte Quelle da ist.

### Stufe 3 Bauteile finden (vorhanden, Luecken schliessen) - groesster Hebel gegen "gelb"
1. Fassaden-Orthos je LoD2-Flaeche und je Vorbauflaeche; **Mindestflaeche aus Pixel/m statt 20 m2** (Erkerflaechen 1-3 m2 wurden nie geparst).
2. OWLv2 mit Kacheln (960 px, Ueberlappung, NMS), Textembeddings gecacht; zweite Kette Grounding DINO/LLMDet + SAM 2 als Gegenprobe (Lizenz je Gewicht pruefen).
3. Zaehlung NUR am Foto (Z-Protokolle), Rasterpruefung (Zeilen/Spalten, Luecke = "fehlt?").
4. Freiraum aus Sichtstrahlen -> Oeffnungen, Hallen, Nischen allgemein (Arkadenhalle ist kein Sonderfall mehr, sondern Ergebnis).
5. Bloecke/Erker/Galerie aus Wolkenbloecken + triangulierte Spitzen; Relief aus Wolke; Tiefen je Klasse gemessen (`tiefen_messen`), Beleg "gemessen" statt ANNAHME.
6. Zierteile: OWLv2-Pruefung mit Gegenbegriffen -> TripoSR/TripoSG -> **Neuvernetzung auf Druckaufloesung** (bewiesen, noch nicht im Generator) -> Konsole -> Vereinigung.
7. Neue Bauteilklassen nur, wenn die Konvergenzschleife (Stufe 4) an derselben Stelle in >= 2 Fotos ein gelbes Cluster mit Tiefe meldet: Gauben, Bruestung, Rippenfaecher, Erkerfensterchen.

### Stufe 4 Konvergenzschleife (NEU, Kern dieses Plans)
Je Lauf k:
1. Modell bauen -> `foto_diff --mehrstufig` auf ALLEN kalibrierten Fotos (Verdecker per Tiefenkarte maskiert, Himmel bleibt) + Restfeld je Ebene (Waende, Daecher, Vorbauten) + Freiraum.
2. **Fehlerkarte je Fassadenzelle** (0,1 m): rot-Dichte, gelb-Dichte, Restfeld-Tiefe, Kamerazahl. Nur Zellen mit >= 3 Kameras zaehlen.
3. Fehlercluster -> Kandidaten aus vorhandenen Bauteilregeln (Oeffnung, Vorsprung, Nische, Bogenfit mit Wolkenband, Parameterzug) UND Schwellen als Parameter.
4. Uebernahmetor (Abschnitt 0, Fehler 2) + Elementbuch (Fehler 5).
5. Abbruch, wenn kein Cluster mehr einen Kandidaten mit Gewinn hat, oder Zeitbudget.
6. Beweis: bekanntes Modell stoeren (Bogen zu, Erker weg, Gaube versetzt) -> Schleife findet zurueck; Martinstor darf nicht schlechter werden.
Kennzahl pro Lauf: Summe gelb+rot ueber gut beobachtete Zellen, muss monoton fallen; sonst Lauf verworfen, Grund im Versuchslog.

### Stufe 4b Fit als Ausgleichsrechnung (Nutzerfrage 5.11. abends: "modellbasierte Rekonstruktion massiv verbessern")
Heute: Black-Box-Suche (Gitter, CMA-ES) auf Canny-Kanten mit festen Kameras. Ziel: Schaetztheorie statt Suche. Reihenfolge nach Nutzen:
1. **Gemeinsamer Fit Modell + Kameras** (Buendelausgleich mit Modell): Unbekannte = Generatorparameter + je Foto 6 DoF + k1; Beobachtungen = Fotokanten (Distanzfeld), SfM-Punkte; Kameras mit Buendel-Kovarianz als Prior. Gauss-Newton/Levenberg-Marquardt mit robustem Verlust (Cauchy), Jacobi per paralleler finiter Differenz je Parameter (Generator ist schnell), spaeter differenzierbarer Rasterer (PyTorch3D BSD, Mitsuba 3 BSD; nvdiffrast Lizenz pruefen). Loest Fehler "lokaler Kameraversatz 0,35-1,3 m" und "4,5 min je Generation" zugleich. Beweis: synthetisch (bekannte Parameter + verstellte Kameras -> Fit findet beide zurueck), Kaufhaus, Martinstor.
2. **Geometriekanten als Residuum**: Normalen-/Tiefenkanten (MoGe-2, MIT), Liniensegmente (DeepLSD MIT / OpenCV LSD), Richtungs-Chamfer, photometrische NCC auf Orthos; Verdecker SAM 2.1 (Apache), Himmel bleibt.
3. **Struktur als Inferenz**: Gitter-/Symmetriefit auf dem Ortho (Autokorrelation) fuer Achsmass und Reihen; Split-Grammatik (CGA-Prinzip) oder MRF ueber Fassadenzellen (Graph-Cut, pymaxflow) verbindet Detektionen, Gitterprior und Wolkentiefe. Zaehlung bleibt am Foto (Regel 9), aber mit Unsicherheit.
4. **Quellen mit Kovarianz**: je Quelle Streuung + Blindheit; Widerspruch = Chi-Quadrat-Test auf dem Residuum; Ausreisser bleiben stehen (M-Schaetzer/RANSAC). Ersetzt Handschwellen durch Statistik (Regel 5 als Zahl).
5. **Restfeld als regularisiertes Hoehenfeld** (TV/bilateral, Druckaufloesung) bzw. modellgefuehrte TSDF-Fusion (Open3D MIT): Tiefenkarten + Modell als Prior, Sichtbarkeitskonsistenz enthalten -> ersetzt getrennten Freiraum-Schritt.
Jeder Punkt: Spezifikation (`modelle/SPEC_*.md`), Sonnet setzt um und beweist, Lizenzklasse je Lib in `LIZENZ_WERKZEUGE.md`.

### Stufe 4c Bildwert messen statt raten (Nutzerfrage 5.11. abends; PLAN_VERBESSERUNG M9)
Stand: `bilder_schleife.py` (Klassen neu/aehnlich/Dublette ueber SIFT-Inlier) ist NICHT in `nullstart.py`; Wert = Aehnlichkeit, nicht Modellgewinn.
Neu (Spezifikation S7, nach S3): (1) Wert vorab = Summe der Fassadenzellen, die die geschaetzte Kamera des Kandidatenbilds NEU sieht (n_fotos < 3 oder hohe
Uneinigkeit), gewichtet mit dem Zellfehler der Fehlerkarte; Aufnahmeregeln als Pruefung (Basiswinkel 10-30 Grad, Einfall < 70 Grad, Bodenaufloesung < Ziel). (2) Wert nachher
= Zellabdeckung steigt oder lokale Kennzahl faellt, sonst "ohne Gewinn" und Vorhersage nachkalibrieren. (3) Abbruch bei erwartetem Gewinn < Zellflaeche x Druckaufloesung.
Gilt fuer Web-Bilder, Videoframes (statt fester Schrittweite) und als Aufnahmeplan fuer Handyfotos (`abdeckung.py` ersetzen). Einbau als Nullstart-Schritt `bilder`.
Prioritaet hochgesetzt 5.11. 19:55 (Nutzer: "mehr Bilder = dichtere Wolke, auch an den Seiten?"): Kaufhaus-Abdeckung Front 94 %, Ost 21 %, West 12 %, Rueckseite 0 - Dichte folgt Blickwinkel, nicht Bildzahl.
Reihenfolge: (1) Mapillary mit Seitenfilter aus der Abdeckung, (2) Videoframes G3, (3) Handyfotos-Aufnahmeplan (8-15 m Abstand, alle 2-3 m, alle Seiten, streifende Blicke), (4) Bildwert als Tor. Direkt nach S3b.

### Stufe 5 Feinlage und Mehrfoto-Befund (NEU, Voraussetzung fuer 10 cm)
- Lokaler Kameraversatz je Bildzone/Bauteil (Kreuzkorrelation der Kantenbilder je Richtung) als Pruefung, dann als Feinlage der Kamera (nicht des Modells), Tor gegen Buendel-Beobachtungen.
- Befund nur, wenn dieselbe 3D-Stelle in >= 2 Fotos dasselbe sagt. Schwelle "deutlich" (0,08) statistisch belegen (Versaetze 0,2/0,4/0,6 m).
- Geometrische Fotokanten aus Normalen (MoGe-2, MIT) als Gegenprobe zu Canny: Knick gegen Knick, Schatten faellt raus. Nur uebernehmen, wenn Overlay es zeigt.

### Stufe 6 Druckaufbereitung (teils vorhanden: `druckteile_auto.py`, `h0_druckfertig.py`)
- Pruefstand-Regel: Mindestbreite XY >= 0,85 x Duese, tragend >= 2 x Duese; Duese ist Objektparameter (0,4 Standard, 0,2 fuer Fassadenplatten).
- Zerlegung regelbasiert: Fassadenplatten je Seite (Laibungen in Z, Sprossen in XY), Dach, Helm, Kleinteile; Stifte/Bohrungen; Farbe je Bauteil statt Farbwechsel.
- **Teil-gegen-Foto automatisch**: je Teil Detailrender aus Fotokamera + `fehlteile_finden` + Zaehlvergleich (Regel 9b als Werkzeug, nicht als Augenregel).
- Testgitter 0,2-Duese einmal drucken und messen (Nutzer), Ergebnis als Sollwerte.

### Stufe 7 Bericht und Viewer (automatisch)
`lauf_bericht.py`: je Foto Overlay vorher/nachher, Tabelle rot/gelb je Fassade, offene Widersprueche, Elementbuch-Diff, Aufwand. Viewer aus denselben Dateien. Artifact-Update nur daraus.

### Stufe 8 Abschlusstor "Modell fertig"
Alle Pruefungen gruen, Zielwerte aus Abschnitt 1 erreicht, Widersprueche gelistet (nicht gemittelt), MASSNACHWEIS automatisch, Lizenz je Quelle und Werkzeug (Code, Gewicht, Trainingsdaten getrennt), Gemeinfreiheitsstatus je Bauteil im Beleg, Druckteile gesliced.

## 3b. Soll-Ablauf in Nutzerworten (5.11. abends) und Zuordnung
Bilder suchen (Stufe 0/1) -> Mehrwert bewerten (4c/S7) -> erster Lauf mit den besten Bildern + Sweet Spot (foto_auswahl, sweetspot) -> Kontrast/Helligkeit/Pixelgroesse
variieren, mergen, Kanten (foto_diff --mehrstufig, S2) -> STL ueber bekannte Anker in die Bildwolke matchen, relative Kanten (Buendel an LoD2/DGM, Kamera-Bruecke, Versatz je Foto; Feinlage Stufe 5)
-> Modell ueber ALLE Bilder mit richtiger Kamera legen, Restabweichung je Fassadenzelle (Fehlerkarte + Restfeld, S3) -> iterativ bis zum festgelegten Grenzwert (Konvergenzschleife mit Tor S1b; Grenzwert = Zielwerte aus Abschnitt 1).

## 4. Reihenfolge der Arbeit (jeder Punkt: bauen, beweisen, Regression, Register, dann der naechste)

| # | Schritt | Warum zuerst | Fertig, wenn |
|---|---|---|---|
| 1 | Root-Platte frei machen (100 %, 251 MB); Platzpruefung in Stufe 0 | sonst stirbt jeder Lauf | > 5 GB frei, Tor vorhanden |
| 2 | Laufenden `kh_abnahme` auswerten; `regression.py --pruefen` fuer foto_diff/freiraum; `test_foto_diff` mit `--mehrstufig` an beiden Objekten | Regel 8b, Fehler 3 | mehrstufig = Standard oder begruendet nicht |
| 3 | Uebernahmetor verschaerfen + Elementbuch im Laeufer | Fehler 2, 5 | synthetischer Test: schlechter Kandidat wird abgelehnt, Altelement bleibt |
| 4 | Stufe 4 Konvergenzschleife (Fehlerkarte, Kandidaten, Tor, Abbruch) | Nutzerauftrag "iterativ konvergieren" | Stoertest findet zurueck, Kaufhaus gelb faellt monoton, Martinstor unveraendert |
| 5 | Stufe 3 Luecken: Mindestflaeche aus Aufloesung, Kacheln, Zier-Neuvernetzung im Generator | gelb 48-59 % = fehlende Teile | Erkerfenster/Gauben werden gefunden und bestehen das Tor |
| 6 | Video-Stufe Kaufhaus laufen lassen (Kandidaten liegen vor) | mehr Blickwinkel fuer Erker/Gauben/Rueckseite | Fragmente ausgerichtet, Kamerazahl je Seite steigt |
| 7 | Stadt-LoD2 laden, Stadtmesh-Lader als Pruefreferenz; Mails bDOM/ALS/Mesh (Nutzer) | unabhaengige Quellen fuer First/Erker/Traufe-Widersprueche | Widersprueche entschieden oder dreifach belegt offen |
| 8 | Stufe 5 Feinlage je Foto + Mehrfoto-Befund | 10-cm-Ziel | Versatz je Zone < 0,1 m in Kontrollfotos |
| 9 | Stufe 6 Druck: Mindestbreiten-Regel, Platten, Teil-gegen-Foto | Druckbarkeit messbar | Kaufhaus-Front als Platte gesliced, Vergleichsbild ok |
| 10 | Stufe 7/8 Bericht, Viewer, Abschlusstor; Nachtlauf Kaufhaus von Null ohne Eingriff | Ziel "ein Nachtlauf je Gebaeude" | Lauf ohne Absturz, Bericht morgens lesbar |
| 11 | Martinstor durch dieselbe Kette (Sued offen) | zweites Objekt, Regressionsschutz | nicht schlechter, Sued-Beobachtung mit neuer Quelle |

Parallel, ohne Nutzer: Ressourcen-Sperre in `job_start.sh`, `hardcode_finden` im Pruefstand, Pre-Commit-Pruefung "Generatoraenderung hat Pruefung".

## 4a. Hardware (Nutzerfrage 5.11. abends "Hardware besser nutzen? Cloud-GPU?")
Stand: 28 Kerne meist < 10 %, 16 GB RAM (Arbeiter 1,4-2,2 GB -> 4 parallel), RTX 4060 8 GB mit 0-1 GB belegt und 0 % Last waehrend der Beweise. Engpass = Software (ein Prozess je foto_diff-Aufruf, CUDA-Neustart, serielle GPU-Regel), nicht Hardware.
Reihenfolge: (1) **S8 persistenter GPU-Arbeiter**: ein Prozess haelt Fotokanten/Distanzfelder/Kameras im VRAM, Kandidaten-STLs ueber Warteschlange, Kennzahlen zurueck (Erwartung 5-10x je Kandidat; Beweis: bitgleiche Kennzahlen gegen foto_diff-Einzelaufruf, test_foto_diff bestanden); (2) RAM 32 GB (Nutzer); (3) `jobplan.py` fuer CPU-Jobs parallel zur GPU; (4) Messprofil eines Nachtlaufs (nvidia-smi dmon, RAM) vor jeder weiteren Beschleunigung.
Cloud erst ab Stufe 8 (stabiler Nachtlauf): eine Instanz je Gebaeude (Container mit venv-seg + COLMAP-CUDA), grosse Karten nur fuer Netze > 8 GB (TripoSG, Splatting); Kosten je Gebaeude vorher lokal mit aufwand_log messen.

## 4b. Produktionsbetrieb ohne LLM (Nutzerfrage 5.11. abends: "viele Modelle mit billigen Modellen oder ohne LLM")
Rollen:
- **Produktion = kein LLM.** Eingabe: Objektname/Adresse -> `tools/objekt_anlegen.py` (UTM, Quellen laden) -> `nullstart.py <objekt> --stufen` (Standardplan) -> Abschlusstor. Jede Entscheidung ist ein Tor mit Zahl (Uebernahmetor, Pruefstand, Elementbuch, Abschlusstor). Ausgabe: `modelle/<objekt>/BERICHT.md` mit "fertig" oder "nicht fertig" + Gruende + offene Widersprueche + Druckteile.
- **Billiges Modell = Triage.** Berichte lesen, Bildblaetter beschreiben, Versuchslog/Stand fuehren, Bestell-Mails vorbereiten, Nutzer-Sichtfunde als Beobachtung eintragen. Keine Aenderung an Generator, Laeufer, Pruefstand, foto_diff.
- **Starkes Modell = Entwicklung.** Neue Bauteilklasse, neue Messung, Spezifikation + Pruefung der Beweise. Aufwand je GEBAEUDETYP, nicht je Gebaeude.
Was heute noch LLM braucht -> Automatisierung: Sichtfund -> Fehlerkarte + Pruefstandzeile (S3); Quellenwiderspruch -> Chi-Quadrat mit Kovarianz (4b.4); Bild vor Uebernahme -> Elementbuch + Zellkennzahl; Zaehlung -> Gitterfit/Kacheln mit Z-Protokoll (S4); Handschwellen -> Plan-Schluessel + hardcode_finden; neue Bauteilklasse bleibt Entwicklung, Prioritaet aus wiederkehrenden "textur"-Clustern ueber mehrere Gebaeude.
Mengenziel und Messgroessen je Gebaeude (in `aufwand_log.py`): Rechenzeit Nachtlauf, GPU-Stunden, Anteil "fertig" ohne Eingriff, Zahl offener Widersprueche, Anteil Fotokanten ohne Modell am Ende. Ziel nach Stufe 8: ein Gebaeude je Nacht ohne Eingriff, Trefferquote "fertig" >= 2 von 3 bei Standardtypen (Giebelhaus, Turm, Halle mit Arkade).
Warteschlange: `tools/jobplan.py` (vorhanden: Queue-JSON, GPU nur einfach, CPU-Jobs parallel nach RAM, Abhaengigkeiten, fortsetzbar) fuehrt Objekte nacheinander; Platzpruefung je Objekt (platz_pruefen.py, seit 5.11.); Archivierung: `aufraeumen_datenplatte.sh` ist noch auf feste Laufnamen vom 3.11. gebunden -> verallgemeinern (regenerierbare Zwischenprodukte je Lauf nach Alter und Verweisen, Trockenlauf zuerst).

## 4c. Untersuchungen, die den Plan absichern (Nutzerfrage 5.11. abends "noch mehr verbessern/untersuchen?")
1. **Wahrheit vor Ort**: 10 Masse am Kaufhaus mit Laser-Entfernungsmesser (Bogenbreiten, Pfeiler, Erkertiefe, Traufhoehe, Fensterachse) + Loebbecke-Grundrisse als Dokumentquelle -> erste absolute Referenz fuer das 10-cm-Ziel (Nutzer).
2. **Generalisierungsluecke**: jeder Lauf haelt 20 % der kalibrierten Fotos zurueck; Bericht Fehler Anpassung vs zurueckgehalten; waechst die Luecke, passt der Laeufer Rauschen an (Test gegen Fehler 8).
3. **Fehlerrate der Tore**: Serien bekannter falscher und richtiger Kandidaten durch `uebernahme_tor` -> Falschannahme-/Falschablehnungsrate je Kandidatenklasse; Toleranzen danach belegt statt gesetzt.
4. **Drittes Gebaeude ohne Entwicklung**: Giebelhaus oder Schwabentor nur per Nachtlauf, kein Code; misst, was generisch ist; Stadt-LoD2 als zweite Dachquelle sofort da.
5. **Fehlerbudget je Quelle**: Wiederholbarkeit (Buendel-Saat, LoD2 vs Stadt-LoD2 ueber viele Gebaeude, DOM1 vs Wolke auf Flachdaechern) -> Kovarianzen fuer 4b.4.
6. Nutzen je Baustein (Freiraum/Bloecke/Parsing einzeln aus, auf zurueckgehaltenen Fotos) und Rechenzeitprofil des Nachtlaufs vor jeder Beschleunigung.
Jede Untersuchung = Spezifikation + Sonnet + Beweisliste; Ergebnisse als Register-Abschnitt.

## 5. Was der Nutzer tut (alles andere laeuft)
- Mails senden: bDOM (60 EUR), ALS (Zweck "kommerzieller Modellbau"), Stadtmesh-Lizenz (vermessung@freiburg.de).
- Handyfotos: streifende Blicke entlang der Kaufhaus-Front (Erkertiefe), Rueckseite, Martinstor Sued.
- Testgitter 0,2-Duese drucken, Ergebnis fotografieren (wird Sollwert).
- Sichtfunde melden; sie werden zuerst als fehlschlagende Pruefung eingetragen.

## 6. Nicht tun (Holzwege aus Register und Log)
- Keine Handvarianten, keine Handschwellen, keine Sonderregeln je Bauteil ("Seitenbogen = Durchgang").
- Keine Uebernahme auf grober Metrik oder mit t < 2. Kein Mitteln von Widerspruechen.
- Kein Viewer, kein Fortschrittsbericht ohne Bild aus dem Lauf.
- Keine zweiten CPU/GPU-Jobs neben einem Nachtlauf. Keine Generatoraenderung waehrend ein Lauf den Generator liest.
- Keine NC-Werkzeuge im Verkaufspfad (VGGT-1B NC, Cityscapes-Gewichte, Hunyuan3D, Google Tiles).
- Kein Punkt dieses Plans gilt als erledigt ohne Beweis (synthetisch + 2 Objekte + Bild).

## 7. Nutzerentscheid 5.11. abend: Kanten statt Vorlagen
"Fertige bekannte Objekte reinmatchen ist immer bloed, es gibt nie alle Formen. Kanten perfekt erkennen und so das 3D-Modell nachbilden."
- Keine Vorlagen-/Bibliotheks-Fits (auch keine Boegen aus bauteile.py) als Formquelle.
- Kanten-Stufe nach S3b: Fotokanten (mehrstufig, Versatz-kompensiert) aus kalibrierten Fotos zu 3D-Linien/Kurven triangulieren (Linien-SfM, Kandidat LIMAP; Lizenz vor Einsatz pruefen, LIZENZ_WERKZEUGE.md).
- Flaechen zwischen den Kanten aus der Buendelwolke; Vernetzung kantenerhaltend (3D-Kanten als Zwangslinien).
- OWLv2 nur als Hinweis "Oeffnung hier" fuer die Durchblick-Erkennung, nie als Form.
- Beweis: foto_diff auf Holdout-Fotos (kosten_lr) besser als Wolken-Solid ohne Kanten; Pruefstand gruen; Nutzer-Video 6.11. als Hauptdaten (scharfe Kanten aus vielen Winkeln).

# Recherche: Verbesserungen fuer die Seiten-SfM-Folge (Stand 21.11.2026)

Nur gelesen und im Netz recherchiert. Nichts installiert, kein Rechenjob, kein Werkzeug geaendert, nichts committet.
Bezug: die am 21.11. von Hand bewiesene Folge Masken -> Seitenerkennung -> globaler Mapper je Seite -> Brennweiten-Schaerfe -> dichte Wolke je Seite -> Vereinen (`GLOBALER_MAPPER_STABIL.md` ab Zeile 172, `ERKENNTNISSE.md`).

Kennzeichnung:
- **BELEGT** = steht mit Zahl in einer Quelle (Netz oder eigenes Logbuch, Stelle genannt).
- **PLAUSIBEL** = folgt aus belegten Tatsachen, ist aber an unseren Daten nicht gemessen.
- **VERMUTUNG** = Idee ohne Beleg.
- Lizenz **an der Quelle gelesen** = heute LICENSE/README abgerufen; sonst **ungeprueft**.
Keine Rechtsberatung. Zeitangaben sind grobe Schaetzungen aus den Laufzeiten im Logbuch.

Hinweis zur Arbeitsregel aus `ANALYSE_SACKGASSEN_2026-11-21.md` Zeile 35 ("kein Mapper-Versuch mehr, solange hinten Stufen fehlen - ausser ein Tor faellt durch"): Die Vorschlaege unten sind bewusst kleine Messungen (Minuten bis 1 h) an vorhandenen Daten; nur Massnahme 1 (Lizenz der Masken) ist unabhaengig davon noetig, weil sie den Verkauf betrifft.

---

## Rangliste: die fuenf Massnahmen mit dem groessten Hebel

1. **Masken-Netz ersetzen: RF-DETR-Seg (Apache-2.0, COCO-Klassen mit `train`) statt SegFormer-B4.** Loest das Lizenzproblem (SegFormer ist an der Quelle gelesen NICHT kommerziell) und liefert Einzelobjekte, was die Statuen-Regel erst moeglich macht. Ob Strassenbahnen als `train` erkannt werden, ist zu messen. (Schwaeche 2)
2. **Vereinen: Lot der zweiten Seite aus ihren eigenen Waenden, Massstab aus der Turmbreite statt aus Klappung/Hoehe.** Beide Seiten sehen denselben Baukoerper in voller Breite; das Lot ist je Seite aus Wandnormalen messbar. Erwartet: Kippung 4,5 Grad -> unter 1 Grad, Massstab 4 % -> unter 1,5 %. Minuten, kein GPU. (Schwaeche 4)
3. **Seitenerkennung zweistufig: streng trennen wie heute, danach Rueckholstufe fuer die 162 "fremden" echten Bilder gegen das fertige Seitenmodell; FlexGlue-Kovisibilitaet als zweiter Stimmgeber neben dem Doppelgaenger-Pruefer.** Daten dafuer liegen schon in `/media/oem/rcdaten/tmp/flexglue/`. (Schwaeche 1)
4. **Globaler Mapper: Streuquelle eingrenzen (einmal kalibrieren, DB kopieren, dann zwei Mapper-Laeufe; dazu ein Lauf einfaedig ohne GPU) und als Standard "ein Lauf + Schaerfe-Sperrliste" festlegen.** Die Schalter gibt es im eigenen Bau; 10-20 min am Sued-Satz. (Schwaeche 6, 3)
5. **Motiv-Vorfilter aus dem Paar-Graphen (Flaechenabdeckung und Massstabsverhaeltnis der bestaetigten Zuordnungen) + schrittweiser Mapper nur noch auf der Liste ohne Sperrbilder.** Kein neues Netz, Minuten; die 31 Schleifenbilder vom 21.11. sind die Pruefmenge. (Schwaeche 5)

Nicht in der Rangliste, aber kostenlos und zuerst zu tun: die Zahl "9-14 % scharfer Videobilder wandern" stammt aus dem UNGEFILTERTEN alten Lauf; auf der gefilterten DB sind es 1 % (siehe Schwaeche 3, Punkt 1).

---

## Schwaeche 1 - Seitenverwechslung: Pruefer nennt Clips derselben Seite "verwechselt", 162 echte Bilder unter "fremd"

### Was in den eigenen Unterlagen schon steht
- Dreimal aufgetreten, Ursachenkette: `LOGBUCH_KETTENTEST_2026-11-19.md` Zeile 191-203.
- Louvain-Gruppen trennen sauber (Zeile 211); Sim3-Inlier und Freiraum-Probe als Geometrie-Gegenprobe gemessen und VERWORFEN (Zeile 214-217, 228: Sim3-Anteil 0,11-0,58 auch bei echten Verbindungen, Ursache verzogene kleine Video-Teilmodelle).
- Doppelgangers-Pruefer: Schwelle 0,45 trennt am Martinstor nicht (Zeile 221); neue Urteilsregel "echt ab 10 % eindeutig gleicher Paare" (Zeile 230); ein Fehlalarm am Schwabentor, vom echten Fall nicht unterscheidbar (Zeile 234); GPS darf klares "echt" nicht ueberstimmen (Zeile 235 f.).
- FlexGlue als Tuersteher: Querpaare 0 von 10 bestaetigt, Kontrolle 9 von 10 (Zeile 365); weist 6460 von 50 715 SIFT-Paaren ab (Zeile 380); ABER reines SIFT + globaler Mapper + `modell_zerlegen` trennt die Seiten ebenfalls (Zeile 392).
- Bildsuche DINOv2 als Vorfilter verworfen (`RECHERCHE_VERBESSERUNGEN_2026-11-19.md` Zeile 118). Alle LightGlue-Paare ungefiltert: 12 780 Gegenseiten-Paare (`NICHTS_GEBRACHT.md` Zeile 344).
- Befund heute: Pruefer nennt verschiedene Clips derselben Seite "verwechselt"; Tor prueft deshalb nur Paare aus verschiedenen Bildteilen; Anteil geloeschter echter Paare ungemessen (`GLOBALER_MAPPER_STABIL.md` Zeile 194-196).
- Lizenz: Doppelgangers MIT, Gewichte-Trainingsdaten ungeprueft; Doppelgangers++ "nicht einsetzen" (`LIZENZ_WERKZEUGE.md` Zeile 10-12).

### Funde im Netz
- **Doppelgangers++ (CVPR 2025).** Klassifikationskopf auf eingefrorenen MASt3R-Merkmalen; laut Projektseite bessere Praezision/Trefferquote als der Vorgaenger "in allen Einstellungen" (Zahlen nur als Bildtabellen, nicht lesbar). Code https://github.com/doppelgangers25/doppelgangers-plusplus, Gewichte auf Hugging Face. **Lizenz an der Quelle gelesen: CC BY-NC-SA 4.0** (LICENSE-Datei); die Gewichte erben zusaetzlich die Datensatzlizenzen von MASt3R/DUSt3R (CHECKPOINTS_NOTICE: Map-free, CO3Dv2, ARKitScenes u. a. nur nicht-kommerziell). MASt3R selbst: CC BY-NC-SA 4.0, "non-commercial use only" (README https://github.com/naver/mast3r gelesen). GPU: MASt3R ViT-Large, VRAM nicht angegeben. -> NUR TEST. Trifft Schwaeche 1 direkt.
- **GLUEMAP (Pan, Schoenberger, Pollefeys; CVPR 2026, arXiv 2605.26103; Code https://github.com/colmap/gluemap).** Globales SfM mit Feedforward-Netzen: Pi3 je Sterngraph, VGGSfM-Spuren, SALAD-Bildsuche, Doppelgangers++ als Paarfilter (Schwelle 0,8, je Runde 0,1 tiefer bis der Graph zusammenhaengt). BELEGT: ETH3D AUC@1/3/5 = 53,0/76,9/83,6 gegen SIFT 45,6/62,2/66,7; Ablation "Doppelgangers++-Filter wichtig auf ETH3D". Code neues BSD (README gelesen). ABER: Standardgewichte Pi3 sind **CC BY-NC 4.0** (README https://github.com/yyfz/Pi3 gelesen), Doppelgangers++ NC (s. o.); VGGSfM und SALAD nicht geprueft. Rechner der Autoren 96 GB GPU, "passt auf 24 GB" laut Arbeit - nichts zu 8 GB. Keine Angabe zur Laufstreuung. -> NICHT einbaubar (Lizenz und Speicher); als Ideengeber wichtig: auch der Stand der Technik loest Doppelgaenger per gelerntem Paarfilter mit absteigender Schwelle, nicht geometrisch.
- **FlexGlue (cvg; schon im eigenen COLMAP-Bau).** README https://github.com/cvg/FlexGlue heute gelesen: `covisibility_score` = "Wahrscheinlichkeit, dass beide Bilder denselben Ort zeigen"; Code MIT, Koepfe MIT, Grundnetz DINOv3-Lizenz (im Register schon als verkaufstauglich fuer Modelle eingestuft). Keine Doppelgaenger-Benchmarkzahl im README. Trifft Schwaeche 1 direkt, ist lizenzsauber und vorhanden.
- **Doppelgangers (Original, MIT).** README https://github.com/RuojinCai/doppelgangers: Trainingsskripte `train.py` vorhanden, Standardschwelle im COLMAP-Weg 0,8; Format eigener Paarlisten steht nicht im README (nur im Datensatz-README, nicht gelesen).
- Eine neuere, lizenzfreie GEOMETRISCHE Loesung (ohne gelerntes Netz) habe ich nicht gefunden; die Suche lieferte fuer 2026 nur die genannten Arbeiten.

### Vorschlaege (nach erwartetem Nutzen)
1. **Rueckholstufe nach der Trennung (PLAUSIBEL, groesster Nutzen).** Die Trennung darf streng bleiben; die 162 echten "fremden" Bilder werden danach gegen das fertige Seitenmodell eingehaengt (wie Konsens-Stufe 2 mit Seitenfilter, `LOGBUCH` Zeile 398/405, dort 0 verklebte Bilder), angenommen nur, wenn `brennweite_schaerfe.py` "scharf" sagt und `seiten_blick_tor.py` besteht.
   MESSPLAN: Liste der 162 aus `seiten_maske.json`; je Bild bestaetigte Paare zu Nord (`global_teil0_a`) und Sued zaehlen; `image_registrator` bzw. `mapper --fix_existing_frames` je Seite. Zahlen: zurueckgeholte Bilder (Ziel >= 100 von 162), `seiten_blick_tor` rc 0, `modell_zerlegen` weiter ein Stueck je Seite, Lage der alten Kameras unveraendert (`modell_lage_vergleich.py` Median < 0,1 %). Dauer ca. 20-30 min.
2. **FlexGlue-Kovisibilitaet als zweiter Stimmgeber im Gruppenurteil (PLAUSIBEL).** Urteil "verwechselt" nur, wenn Doppelgaenger-Pruefer UND FlexGlue (Anteil abgewiesener Paare der Gruppenverbindung) uebereinstimmen; bei Uneinigkeit "unklar" -> Rueckholstufe entscheidet.
   MESSPLAN ohne neuen GPU-Lauf: in `/media/oem/rcdaten/tmp/flexglue/` liegen die FlexGlue-Urteile fuer 50 715 SIFT-Paare (`flexglue.db`, `stich.db`) und die Wahrheit Nord/Sued (`kontrolle_nord.txt`, `quer.txt`). Fuer alle Gruppenverbindungen, die `seiten_maske.json` "verwechselt" nennt und die laut Bezug auf DERSELBEN Seite liegen (die 6 Nord-Gruppen von Zeile 194), die FlexGlue-Annahmequote ausrechnen. Zahl: Fehlalarmrate "verwechselt innerhalb einer Seite" heute (Anteil messen, ist offen) -> Ziel < 5 % der Nord-Nord-Verbindungen, bei unveraendert 0 angenommenen Nord-Sued-Verbindungen. Dauer ca. 30 min Auswertung.
3. **Pruefer-Kopf an eigenen Paaren nachtrainieren (VERMUTUNG, nur wenn 1+2 nicht reichen).** Wahrheit: Schwabentor (GPS-geprueft), Martinstor Nord/Sued-Bezug, mit Masken. Vermutete Ursache der Fehlalarme: Clip-zu-Clip-Paare mit grossem Massstabs-/Blickwinkelunterschied (Drohne gegen Strasse p = 0,383, Zeile 221) liegen ausserhalb der Trainingsverteilung. Risiko: Ueberanpassung an zwei Bauten; Kaufhaus als unbeteiligte Gegenprobe noetig. MESSPLAN: erst nur auswerten, ob die Fehlalarme mit dem Massstabsverhaeltnis der Zuordnungen zusammenhaengen (Rangkorrelation > 0,3?), bevor irgendetwas trainiert wird. 1 h.

### Nicht empfohlen
- Doppelgangers++ / MASt3R / GLUEMAP im Produktweg: NC-Lizenz (an der Quelle gelesen), GLUEMAP zusaetzlich zu gross. Als reiner TEST denkbar, um zu sehen, wie viel ein besserer Pruefer braechte.
- Sim3-Inlier, Freiraum-Probe, GPS als Ueberstimmer, DINOv2-Bildsuche: schon gemessen und verworfen (Stellen oben).

---

## Schwaeche 2 - Masken: keine Klasse Strassenbahn, Statuen/Wandbilder als Person, Lizenz SegFormer

### Was in den eigenen Unterlagen schon steht
- `tools/handy_masken.py` Zeile 8: "NICHT ERFASST: Strassenbahn - ADE20K-150 hat keine Klasse dafuer ... zweites Netz noetig (offen, Lizenz pruefen)".
- SegFormer-B4: Modellkarte `license: other`, NC nur als Einschaetzung, Wortlaut nicht gelesen (`LIZENZ_WERKZEUGE.md` Zeile 128). OWLv2 (Apache laut Karte) ist fuer Marktplanen schon eingebaut (Zeile 133); SAM ViT-B eingebaut (Zeile 111), SAM 2 nicht geladen (Zeile 135); YOLOv8 AGPL (Zeile 69).
- Messwerte SegFormer: 1536 px Batch 4 = 5,6 GiB (`VERSUCHSREGISTER` Zeile 1816). Wirkung: 0 gemischte Bildteile statt 750 Bilder (`ERKENNTNISSE.md` Zeile 5); 65 Bilder ohne Maske wegen Dateiendung, behoben (Zeile 15).

### Funde im Netz
- **SegFormer-Lizenz, an der Quelle gelesen** (https://raw.githubusercontent.com/NVlabs/SegFormer/master/LICENSE): "NVIDIA Source Code License for SegFormer", Abschnitt 3.3: Nutzung nur nicht-kommerziell, "for research or evaluation purposes only". **Damit ist die offene Frage beantwortet: das heutige Masken-Netz ist fuer den Verkaufsweg nicht zulaessig** (ob Masken, die nur Merkmale auswaehlen, ein "Ergebnis" im Sinne der Lizenz sind, ist eine Rechtsfrage - sicher ist nur der Ersatz).
- **RF-DETR-Seg (Roboflow).** Instanzsegmentierung, README https://github.com/roboflow/rf-detr gelesen: Code Apache-2.0, ALLE Segmentierungsgroessen (Nano bis 2XLarge) Apache-2.0 (nur einige Detektions-Sondergroessen stehen unter einer Plattformlizenz). BELEGT: COCO AP 40,3 (Nano, 312 px) bis 49,9 (2XL, 768 px), 34-39 Mio. Parameter -> klein genug fuer 8 GB (PLAUSIBEL, VRAM nicht angegeben). COCO hat die Klassen person, bicycle, car, motorcycle, bus, train, truck, boat (aus meinem Wissen; die COCO-Seite liess sich nicht auslesen). Ob Strassenbahnen als `train` oder `bus` kommen, ist NICHT belegt -> messen. Trainingsdatensatz der Seg-Gewichte nennt das README nicht ausdruecklich (COCO-Zahlen berichtet). Trifft Schwaeche 2 in allen drei Teilen.
- **OWLv2 + SAM 2.1 mit Textvorgabe "tram / streetcar".** OWLv2 ist im Repo eingebaut. SAM 2: README https://github.com/facebookresearch/sam2 gelesen: Code UND Gewichte Apache-2.0; Groessen 38,9 M (tiny) bis 224 M (large). Ergibt eine Tram-Maske ohne feste Klassenliste. Trefferquote auf Tram ungemessen.
- **Mask2Former:** Code MIT (README gelesen), Gewichtslizenz nicht genannt, HF-Karten laut Suchtreffer `license: other`; die Varianten mit Tram-naher Klasse sind auf Cityscapes/Mapillary trainiert (beide Datensaetze nach meinem Wissen nur nicht-kommerziell, heute ungeprueft). **DETR-ResNet-50-panoptic:** HF-Karte `apache-2.0`, COCO-panoptic (gelesen) - alte, schwaechere Rueckfalloption. **EoMT:** Code MIT, Gewichtslizenz im README nicht genannt (ungeprueft).
- Arbeiten "SfM mit dynamischen Objekten" laufen heute fast alle ueber gelernte Feedforward-Netze (NC); fuer unseren Fall (Standbilder vieler Quellen) ist die Maske vor der Merkmalssuche weiterhin der uebliche Weg.

### Vorschlaege
1. **SegFormer durch RF-DETR-Seg ersetzen (BELEGT Lizenz, PLAUSIBEL Wirkung).**
   MESSPLAN: 200 Bilder aus `/media/oem/rcdaten/tmp/mt_seiten_1121/masken` (darunter die 18 Brueckenbilder mit der Person und von Hand 20 Bilder mit Strassenbahn, 20 mit Statue/Wandbild). Zahlen: (a) Ueberdeckung der neuen Personen-/Fahrzeugmaske mit der SegFormer-Maske (IoU je Bild, Ziel Median >= 0,7); (b) Strassenbahn-Bilder mit Maske auf der Bahn: heute 0 als eigene Klasse -> Ziel >= 16 von 20; (c) Pflichtprobe: `seiten_erkennen --masken` auf der neuen Masken-DB muss weiter 0 gemischte Bildteile liefern; (d) VRAM und s/Bild. Dauer: Installation + 200 Bilder ca. 30 min, volle 2107 Bilder + Seitenerkennung ca. 1 h.
2. **Statuen-/Wandbild-Schutz als Regel auf Einzelobjekten (PLAUSIBEL; braucht Vorschlag 1, weil SegFormer keine Einzelobjekte liefert).** Eine "Person", deren Flaeche in einem ersten Modell Punkte mit Spuren ueber mehrere QUELLEN (verschiedene Clips/Fotografen = verschiedene Zeiten) traegt, steht fest und wird entmaskt. Reiner Eigencode, zweiter Durchgang.
   MESSPLAN: an den 20 Statuen-/Wandbild-Bildern Zahl der Merkmale in der faelschlich maskierten Flaeche vor/nach (Ziel: >= 80 % der Flaechen freigegeben); Gegenprobe an den 18 Brueckenbildern: die Person darf NICHT freigegeben werden (0 von 18). 1 h.
3. **Rueckfall Tram per OWLv2-Textvorgabe + SAM (nur falls 1b unter 16 von 20 bleibt).** MESSPLAN wie 1b; zusaetzlich Fehlalarme auf 50 Bildern ohne Tram (Ziel <= 2).

### Nicht empfohlen
- SegFormer behalten (NC, heute an der Quelle gelesen). Cityscapes-/Mapillary-/ADE20K-Gewichte gleich welchen Netzes (Datensatzlizenzen). Ultralytics YOLO (AGPL, im Register).
- Alle Personen/Fahrzeuge > 30 % Bildflaeche einfach als Bild verwerfen: sinnvoll als Vorfilter (ist in `ERKENNTNISSE.md` Zeile 6 schon offen notiert), ersetzt die Maske aber nicht.

---

## Schwaeche 3 - Einzelfotos ohne EXIF wandern; 9-14 % "scharfer" Videobilder wandern trotzdem

### Was in den eigenen Unterlagen schon steht
- AnyCalib als Prior (S3: 29 %) oder fest (S4/V6) schlechter, als Startwert (S5) gleichauf; "Fotos bekannter Brennweite zuerst" zu wenige (`GLOBALER_MAPPER_STABIL.md` Zeile 154-157, 62-68). Ursache: mit Prior an JEDER Kamera tut der Kalibrator nichts mehr (Zeile 65).
- Gemeinsame Kamera je Clip + global am Schwabentor schlechter als Kamera je Bild (`NICHTS_GEBRACHT.md` Zeile 335, Ursache unbekannt); `--kamera-je-clip` traegt die ANNAHME "Clip zoomt nicht" (`tools/sfm_db_variante.py` Zeile 4).
- Schaerfe-Test: "unbestimmt" wandert zu 71-100 %; Brennweite der wandernden Fotos 13,9 % anders (`GLOBALER_MAPPER_STABIL.md` Zeile 186-189, 200).
- Rollverschluss gemessen: kein Effekt am Martinstor (Korrelation 0,09), keine Massnahme (`LOGBUCH` Zeile 374). Kamera-Unsicherheit: `estimate_ba_covariance` scheitert, Ersatz `tools/versuche/kamera_unsicherheit_lokal_1120.py`; alle Springer unter den 10 % unsichersten (`LOGBUCH` Zeile 373, `RECHERCHE_VERBESSERUNGEN_2026-11-19.md` Zeile 117).
- GeoCalib: Gewichte CC BY 4.0 (am 19.11. geprueft), FoV-AUC@10 Grad 48,2 auf MegaDepth, "kaum besser als AnyCalib" (dort Zeile 20, 102). AnyCalib selbst steht NICHT im Lizenzregister (grep ohne Treffer) - nachtragen.

### Funde im Netz
- **GLOMAP-Arbeit (arXiv 2407.20219, gelesen):** Kameras mit unbekannter Brennweite werden in der globalen Positionierung nur um den Faktor 2 heruntergewichtet; die COLMAP-FAQ (gelesen) sagt: "The global mapper depends on good focal length priors", sonst `view_graph_calibrator` vorher. BELEGT also: der globale Weg ist auf brauchbare Brennweiten angewiesen; fuer Kameras, die die Geometrie nicht festlegt, gibt es im Verfahren keinen Schutz.
- **GLUEMAP (s. o.)** nimmt Brennweiten aus dem Feedforward-Netz und bildet den MEDIAN je physischer Kamera; mit wahrer Kalibrierung steigt ETH3D AUC@1 von 53,0 auf 74,0 (BELEGT). Lehre: die Brennweite ist auch im neuesten Verfahren der groesste Einzelhebel fuer die Feinlage; lizenzbedingt nicht uebernehmbar.
- **MoGe-2 (Microsoft):** gibt FoV/Brennweite je Einzelbild aus; Code MIT (README https://github.com/microsoft/MoGe gelesen), Gewichtslizenz steht NICHT im README (im Register als "MIT laut HF-API" gefuehrt); ViT-S 35 M, ViT-B 104 M, ViT-L 326 M Parameter; keine FoV-Genauigkeitszahl im README. Kandidat als ZWEITE unabhaengige Brennweitenstimme.
- **PySceneDetect (BSD-3, README gelesen):** Schnitterkennung in Videos (Content/Adaptive), OpenCV-basiert. Fuer die Frage "ein YouTube-Clip = eine Kamera?".
- Zu elektronischer Bildstabilisierung/Zoom in Fremdvideos als Fehlerquelle habe ich KEINE belastbare Quelle gefunden (Suche ergab nur allgemeine Selbstkalibrier-Literatur) -> bleibt VERMUTUNG.

### Vorschlaege
1. **Erst nachmessen, ob es die "zweite Ursache" auf gefilterten Daten ueberhaupt noch gibt (BELEGT aus eigenen Zahlen, kostenlos).** Die 9 % (33 von 360) und 14 % (96 von 709) stammen aus PRUEFUNG 2 am ALTEN ungefilterten Lauf `var_sift` (`GLOBALER_MAPPER_STABIL.md` Zeile 188); auf der gefilterten DB wandern von 433 scharfen nur 4 = 1 % (Zeile 200). PLAUSIBEL: die zweite Ursache waren Vordergrund/Seitenreste, nicht die Kamera.
   MESSPLAN: `schaerfe_varsift.json` + `vgl_varsift_nord.json` gegen `schaerfe_nord_a.json` + `vgl_nord_a_b.json` schneiden: Wie viele der 96 wandernden scharfen Bilder sind in der gefilterten DB noch enthalten, wie viele davon wandern dort? Dazu je wanderndem Bild: Vordergrundanteil aus `db_maske.db.masken.json`, Clip, Rang in `kamera_unsicherheit_lokal`. Zahl: Restanteil wandernder scharfer Bilder auf gefilterter DB (erwartet <= 2 %); wenn ja, Punkt "zweite Ursache" schliessen. 20 min, nur Auswertung.
2. **Brennweite NUR fuer die "unbestimmten" Kameras von aussen festlegen, alle anderen frei lassen (PLAUSIBEL).** Der verworfene Versuch setzte den Prior an JEDE Kamera und schaltete damit die Paar-Kalibrierung ab; hier bekommt nur die Sperrlisten-Menge (Sued 21, Nord 24 Bilder) einen Festwert. Ein Einzelbild-Schaetzer mit ~6 % Fehler (AnyCalib laut eigenem S4) ist besser als die gemessenen 13,9 % Streuung. Zwei unabhaengige Schaetzer (AnyCalib im Bau vorhanden, GeoCalib CC BY 4.0, optional MoGe-2) -> nur festlegen, wo sie sich auf <= 8 % einig sind, sonst Bild gesperrt lassen (Quellen nicht mitteln).
   MESSPLAN: Sued-Satz (102 Bilder, 130 s je Lauf): Lauf a/b mit Festwerten fuer die 21 unbestimmten. Zahlen: wandernde unter den 21 (heute 15, Ziel <= 5); wandernde unter den uebrigen 78 unveraendert (heute 5); `modell_lage_vergleich.py` Median <= 0,05 %. Gegenprobe: 5 Fotos mit guter EXIF-Brennweite kuenstlich "blind" machen und Schaetzer gegen EXIF vergleichen (Fehler in %). Ca. 30 min.
3. **Kamera je EINSTELLUNG statt je Clip (VERMUTUNG, nur falls Punkt 1 einen Rest zeigt).** YouTube-Clips koennen Schnitte und Zoom enthalten; `--kamera-je-clip` nimmt das Gegenteil an. MESSPLAN: mit freier Brennweite je Videobild (alter Lauf) die Brennweitenspruenge je Clip ueber der Bildnummer auftragen (`mapper_bewerten.py clip_f_cv` gibt die Streuung schon aus); haengen die wandernden scharfen Bilder an Sprungstellen (Anteil > 50 %)? Erst dann PySceneDetect einbauen. 30 min Auswertung.

### Nicht empfohlen
- Einzelbild-Brennweite als Prior fuer alle Kameras, feste AnyCalib-Werte ueberall, "Fotos bekannter Brennweite zuerst": verworfen (Stellen oben). Rollverschluss-Korrektur: gemessen, kein Effekt. Depth Pro / UniK3D: Lizenz nicht gelesen bzw. nach meinem Wissen NC.
- Wandernde Fotos per zweitem Mapperlauf "herausmitteln": widerspricht der Regel "Quellen nicht mitteln"; die Sperrliste ist die saubere Antwort.

---

## Schwaeche 4 - Vereinen ohne gemeinsame Punkte: Massstab ~4 % uneinig, Seite B 4,5 Grad gekippt, Seitenwaende leer

### Was in den eigenen Unterlagen schon steht
- Methode Klappung + Achse aus der Helmstange (`tools/seiten_vereinen.py` Kopf); LoD2-Grundrissmitte als Achse lag 0,9 m daneben (dort Zeile 12); Kameralot 2,3 Grad verkippt, Waende entscheiden (Zeile 42, `LOGBUCH` Zeile 339).
- LoD2-Waende entscheiden die Seite nicht (Strasse spiegelgleich), Feinpassung gab Massstab 0,958 "verdaechtig" (`LOGBUCH` Zeile 259).
- 21.11.: eigene Spitze je Modell, Achse 1,36 %, Hoehen 3,9 % verschieden, Sued 4,52 Grad gekippt (`GLOBALER_MAPPER_STABIL.md` Zeile 214-217, `ERKENNTNISSE.md` Zeile 17-18: "Lot von B aus seinen eigenen Waenden: offen").
- ICP mit freiem Massstab schrumpft die Wolke (`NICHTS_GEBRACHT.md` Zeile 208, BS143); einfache Aehnlichkeit fuer verzerrte Sued-Gruppe unerfuellbar (Zeile 342); "passt zum LoD2-Grundriss" ist kein Massstabsbeleg, DOM1-Laser schon (Zeile 340, `tools/hoehe_gegen_dom1.py`).
- Bruecken ueber Bilder, die beide Seiten sehen (Seitenstuecke 75/101 Bilder, Durchblick Torbogen, Fuehrerstandsvideos durch das Tor): als naechster Schritt notiert, nicht gemessen (`LOGBUCH` Zeile 175, 412). Luftbild 060/061 nie registriert (`VERSUCHSREGISTER` Zeile 659, 715); Luftbild-Zuordnung per LightGlue verbog das Netz (`LIZENZ_WERKZEUGE.md` Zeile 50).

### Funde im Netz
- **Cohen, Sattler, Pollefeys: "Merging the Unmatchable: Stitching Visually Disconnected SfM Models" (ICCV 2015).** Genau unser Fall: Gebaeudeseiten, die sich nicht zuordnen lassen, werden kombinatorisch ueber Symmetrien und semantische Information (Fassadenteile) zusammengesetzt; ein Symmetrie-Prior waehlt unter mehreren Lagen. Quelle: Zusammenfassung https://openaccess.thecvf.com/content_iccv_2015/html/Cohen_Merging_the_Unmatchable_ICCV_2015_paper.html - **das PDF war nicht abrufbar (HTTP 403)**, Einzelheiten (Freiheitsgrade, Genauigkeit) daher NICHT gelesen; Code habe ich keinen gefunden. Bestaetigt den eingeschlagenen Weg (Symmetrie als Messung), liefert kein fertiges Werkzeug.
- **COLMAP `model_orientation_aligner`** (FAQ gelesen; im eigenen Bau vorhanden, heute per `colmap help` geprueft): richtet ein Modell ueber Fluchtpunkte (Manhattan-Annahme) nach Schwerkraft und Hauptrichtung aus. BSD, CPU. Trifft die Kippung direkt, ist aber gleichwertig zum eigenen Weg ueber Wandnormalen.
- **COLMAP `model_merger`** (FAQ): braucht GEMEINSAME registrierte Bilder -> ohne Brueckenbilder nicht anwendbar.
- **"Emergent Extreme-View Geometry in 3D Foundation Models" (arXiv 2511.22686, Cornell).** Relative Lage fuer Bildpaare OHNE Ueberlappung aus VGGT; laut Projektseite beim unveraenderten Netz "nearly half of the pairs" unter 30 Grad Drehfehler. Das ist um Groessenordnungen zu grob fuer unsere 1,5-%-Grenze; VGGT-Gewichte NC (Register). Code-Lage und Lizenz des Repos nicht geprueft. -> nicht empfohlen.
- **Boden-Luft-Arbeiten 2025/2026** (CVD-SfM arXiv 2508.01936, Georegistrierung ohne Metadaten arXiv 2503.04927): binden Bodenbilder an Satellit/Luftmodell; nur aus Suchtreffern, nicht gelesen, Code/Lizenz ungeprueft. Fuer uns nachrangig, weil LoD2/DOM1 als amtlicher Rahmen schon da ist.

### Vorschlaege
1. **Lot von B aus den eigenen Waenden, DANN erst Klappung und Achse (PLAUSIBEL, im Register schon als offen benannt).** Jede Seite wird fuer sich lotrecht gestellt (Wandnormalen der dichten Wolke, `tools/wolke_lot_ausrichten.py`; Gegenprobe `lot_aus_fotos.py` oder `model_orientation_aligner`). Die Klappung liefert dann nur noch Drehung um die Hochachse und Verschiebung.
   MESSPLAN: `dicht_nord`, `dicht_sued`, `vereinen/`. Zahlen: Winkel zwischen Sued-Wandlot und Nord-Wandlot nach dem Vereinen 4,52 Grad -> Ziel < 1 Grad (2294 Wandnormalen wie am 21.11. 14:49); Achs-Einigkeit darf nicht schlechter werden (1,36 % -> <= 1,5 %); Pflichtbild `vereinen.jpg` ansehen. Dauer 10-15 min, CPU.
2. **Massstab zwischen den Seiten aus der Turmbreite, Hoehe nur als Probe (PLAUSIBEL).** Nord- und Suedseite zeigen denselben Turmkoerper in voller Breite (Kante zu Kante) und dieselbe Dachsilhouette. Breite je Hoehenband in beiden lotrechten Wolken messen (Fotokanten zaehlen mehr als die Wolke: Kantenpaar Turmecke links/rechts aus `foto_mass.py`/`foto_breitenprofil.py`), Verhaeltnis = Massstab B/A. Unabhaengige Probe: Hoehe Traufe -> Spitze (nicht Boden -> Spitze: der Boden ist je Seite ein anderer) und je Seite `hoehe_gegen_dom1.py`.
   MESSPLAN: Breitenverhaeltnis in 5 Hoehenbaendern (Streuung der 5 Werte <= 1 %); danach Turmhoehen-Unterschied 3,9 % -> Ziel <= 1,5 %; Dachflaechen-Treffen an der Achse 1,06/0,98 -> naeher an 1,00. 30 min.
3. **Echte Brueckenbilder zaehlen, bevor weiter an der Symmetrie gefeilt wird (PLAUSIBEL).** Mit Masken und FlexGlue (+30/+40 % Bilder) koennten Seitenwand-, Drohnen- und Durchfahrtsbilder heute tragfaehig sein, die am 19.11. fehlten. Reichen >= 3 scharf bestimmte Bilder mit je >= 15 Punkten in A UND B, liefert `tools/teilmodell_sim3.py` eine von der Symmetrie UNABHAENGIGE Lage - der fehlende zweite Beleg (Regel "Lage unabhaengig belegen").
   MESSPLAN: in `db_maske.db` fuer jedes Bild ausserhalb beider Seitenlisten (`teil0.txt`, `teil1.txt`, auch `teil2.txt` und die 162 "fremden") die bestaetigten Paare zu Nord und zu Sued zaehlen; Kontaktbogen der 20 besten ansehen (echte Seitenwand oder Verwechslung?). Zahl: Anzahl echter Brueckenbilder (heute unbekannt). Bei >= 3: Sim3 rechnen, Abweichung zur Symmetrie-Lage in % der Turmhoehe (Ziel <= 1,5 %). 30-45 min.

Zu den leeren Seitenwaenden: das ist ein Aufnahmeproblem (Fotos fehlen), keine Rechenfrage -> Fotoauftrag (Skill `foto-vor-ort`), nicht spiegeln.

### Nicht empfohlen
- ICP mit freiem Massstab (BS143 verworfen); LoD2-Grundrissmitte als Achse und LoD2-Waende als Seitenentscheid (gemessen untauglich); VGGT/MASt3R-Lageschaetzung zwischen Gegenseiten (NC und zu grob); `model_merger` (braucht gemeinsame Bilder).

---

## Schwaeche 5 - Bilder mit fraglichem Motiv kosten den schrittweisen Mapper Stunden

### Was in den eigenen Unterlagen schon steht
- 31 Bilder, 56 Versuche, je 8-10 min Gesamtausgleich; global baut sie sofort ein, Schaerfe-Test sperrt sie ("zu_wenig"); "Motiv-Check vor dem Mapper: offen (erst messen)"; Schnappschuesse setzen (`GLOBALER_MAPPER_STABIL.md` Zeile 204-207, `ERKENNTNISSE.md` Zeile 16, `REZEPT` L-BETRIEB2 Zeile 115).
- 286 von 2042 Bildern > 30 % Vordergrund, Vorfilter offen (`ERKENNTNISSE.md` Zeile 6). Bildwarnungen (Zoom, steiler Blick, alt) gab es am 2.11. schon als Werkzeug (`VERSUCHSREGISTER` Zeile 1347).
- DINOv2-Bildsuche als Paar-Vorfilter wertlos (9 % in top-150); MegaLoc wegen Trainingsdaten nicht benutzt (`LOGBUCH` Zeile 378).

### Funde im Netz
- **Optionen im eigenen COLMAP-Bau (heute per `colmap mapper --help` gelesen):** `Mapper.max_reg_trials` (=3), `Mapper.abs_pose_min_num_inliers` (=30), `Mapper.abs_pose_min_inlier_ratio` (=0,25), `Mapper.ba_global_frames_ratio` (=1,1), `Mapper.ba_global_frames_freq` (=500), `Mapper.snapshot_path`, `Mapper.snapshot_frames_freq`. Ein fertiger "Motivfilter" existiert in COLMAP nicht. Eine Fehlermeldung, die genau unsere Schleife (einbauen -> im Gesamtausgleich verwerfen -> wieder einbauen) beschreibt, habe ich nicht gefunden.
- **MegaScenes-Pipeline (arXiv 2406.11819, nur Suchtreffer):** filtert auf Kategorie-Ebene und per Doppelgangers nach der Zuordnung; kein eigener Motivfilter je Bild belegt. GLUEMAP senkt die Paarschwelle schrittweise, bis der Graph zusammenhaengt - also ebenfalls Graph-Logik statt Bildinhalt.
- Kein lizenzsauberes fertiges Werkzeug "Bild zeigt das Bauwerk gross genug" gefunden; OWLv2 (im Repo) kann es als Erkenner mit Textvorgabe leisten.

### Vorschlaege
1. **Reihenfolge festschreiben: global zuerst, Schaerfe-Sperrliste, schrittweise nur noch OHNE Sperrbilder (BELEGT aus eigenen Daten).** Der globale Lauf + `brennweite_schaerfe.py` erkennt die Problem-Bilder in Sekunden ("zu_wenig" 52 Bilder, davon 49 wandernd).
   MESSPLAN: Schnitt der 31 Schleifenbilder (Namen aus dem Mapper-Log vom 21.11. 13:05-14:03) mit `unbestimmt_nord_a.txt` + "zu_wenig" aus `schaerfe_nord_a.json`. Zahl: Trefferquote (Ziel >= 28 von 31). Nur wenn ein schrittweiser Lauf wirklich gebraucht wird: Nord mit Bildliste ohne die 76 Sperrbilder, mit Schnappschuessen; Ziel: fertig in < 90 min statt Abbruch nach 156 min. Auswertung 10 min; der Lauf selbst ~1,5 h (nur bei Bedarf).
2. **Motiv-Kennzahl aus dem Paar-Graphen, ohne Netz (PLAUSIBEL).** Je Bild aus der DB: (a) Flaechenanteil der konvexen Huelle aller bestaetigten Zuordnungspunkte am Bild (Bauwerk winzig -> klein), (b) Median des SIFT-Massstabsverhaeltnisses zu den Partnern (extreme Nah-/Fernaufnahme -> weit weg von 1), (c) Zahl der Partner mit >= 30 Inliern. Schwellen aus Daten, nicht von Hand.
   MESSPLAN: positive Menge = 31 Schleifenbilder + 52 "zu_wenig"; negative = 433 "scharfe" Nord-Bilder. Zahl: Trennguete (AUC, Ziel >= 0,9) und bei 95 % behaltenen guten Bildern der Anteil erkannter schlechter (Ziel >= 80 %). Gegenprobe Schwabentor. 30-45 min, CPU.
3. **Bauwerks-Flaeche per OWLv2 (im Repo, Apache laut Karte) als zweite Stimme (VERMUTUNG).** Textvorgabe aus `objekt.json` (z. B. "city gate tower"), Flaechenanteil des besten Kastens < 3 % oder kein Treffer -> fraglich. MESSPLAN wie 2 (gleiche Mengen, gleiche Kennzahl); nur uebernehmen, wenn es Bilder findet, die Kennzahl 2 nicht findet. 30 min GPU (~2 GB).

### Nicht empfohlen
- `max_reg_trials` senken oder Inlier-Schwellen heben als alleinige Loesung: behandelt das Symptom und kostet echte Randbilder (VERMUTUNG, ungemessen) - hoechstens zusaetzlich. MegaLoc (Trainingsdaten ungeklaert), DINOv2-Bildsuche (schon wertlos gemessen).

---

## Schwaeche 6 - Globaler Mapper: Laufstreuung, nicht deterministisch trotz Seed

### Was in den eigenen Unterlagen schon steht
- S2d gegen S2 (gleicher Seed): 36 % der Kameras > 10 % Kernradius; "Mehrthread/GPU" nur als Vermutung, nie eingegrenzt (`GLOBALER_MAPPER_STABIL.md` Zeile 73, 156).
- Ohne Gewinn: `ra_reweighting`, `ba_num_iterations`, Schwerkraft je Bild (schaedlich, 12-14 Bilder weniger) (`RECHERCHE_VERBESSERUNGEN_2026-11-19.md` Zeile 113; `GLOBALER_MAPPER_STABIL.md` Zeile 154-156). Globaler Mapper kennt keine Positions-Prioren (Zeile 34).
- Konsens-Rezept: zwei Laeufe JE mit eigenem `view_graph_calibrator` auf eigener DB-Kopie (Zeile 141). Auf gefilterter DB: scharfe Kameras zu 99 % wiederholbar (Zeile 200-201).

### Funde im Netz
- **GLOMAP-Arbeit (arXiv 2407.20219, gelesen), BELEGT:** in der globalen Positionierung werden "all point and camera variables ... initialized by a uniform random distribution" in [-1, 1]; das Ziel "converges reliably with random initialization"; eine Streuung ueber Wiederholungen berichtet die Arbeit NICHT. Zufall ist also Teil des Verfahrens; mit festem Seed bleibt als Quelle nur Reihenfolge-/Rundungsabhaengigkeit (Mehrfaden, GPU-Loeser) oder eine vorgelagerte Stufe.
- **COLMAP:** Aenderungsprotokoll 3.13 "fully deterministic with a new random_seed parameter" und die zugehoerigen PRs (#3492, #3544, #3735) betreffen laut Suchtreffern RANSAC/Zweibildgeometrie und den SCHRITTWEISEN Mapper; fuer den globalen Mapper habe ich keine Zusage gefunden (FAQ gelesen: kein Wort zu Wiederholbarkeit). Eine Issue-Suche "global_mapper deterministic" ergab 0 Treffer - das heisst nur, dass ich nichts fand.
- **Schalter im eigenen Bau (heute per `colmap global_mapper --help` gelesen):** `GlobalMapper.num_threads` (=-1), `GlobalMapper.random_seed` (=-1), `GlobalMapper.gp_use_gpu` (=1), `GlobalMapper.ba_ceres_use_gpu` (=1), Stufen einzeln abschaltbar (`skip_rotation_averaging`, `skip_global_positioning`, `skip_bundle_adjustment`, `skip_retriangulation`), `ra_max_rotation_error_deg` (=10); eigener Befehl `rotation_averager`.
- GLUEMAP berichtet ebenfalls nur Einzellaeufe ohne Streuung.

### Vorschlaege
1. **Streuquelle in drei kurzen Laeufen eingrenzen (PLAUSIBEL; nie gemacht).** (a) EINMAL kalibrieren, die kalibrierte DB kopieren, zwei Mapper-Laeufe mit gleichem Seed -> faellt die Streuung, lag sie im Kalibrator (heute laeuft er je Lauf neu). (b) Ein Lauf mit `--GlobalMapper.num_threads 1 --GlobalMapper.gp_use_gpu 0 --GlobalMapper.ba_ceres_use_gpu 0` zweimal -> sind die Modelle dann gleich, ist es Mehrfaden/GPU; dann einzeln wieder zuschalten. (c) `rotation_averager` zweimal: streuen schon die Drehungen?
   MESSPLAN: Sued-Satz aus `db_maske_seiten.db` (102 Bilder, 130 s je Lauf; einfaedig vermutlich 5-10 min). Zahl je Variante: Bilder > 2 % in `modell_lage_vergleich.py` (heute a gegen b: 8 von 101) und Median (heute 0,04 %); Ziel bei (b): 0 Bilder > 0,01 %. Danach dieselbe Variante einmal an Nord (538 Bilder, ~15 min GPU) fuer die 74 wandernden. Gesamt 30-60 min. Ergebnis ist in jedem Fall verwertbar: entweder ein deterministischer Schalter oder der Beleg, dass die Streuung aus dem Verfahren kommt.
2. **Standard "ein globaler Lauf + Schaerfe-Sperrliste" statt Doppel-Lauf-Konsens (BELEGT aus eigenen Zahlen).** Mit Sperrliste wandern 9 von 462 (2 %), scharfe 4 von 433 (1 %). Der zweite Lauf wird dann nur noch als Stichprobe gebraucht.
   MESSPLAN: Gegenprobe am zweiten Objekt (Schwabentor, gefilterte DB): gleiche Auswertung a/b + `brennweite_schaerfe.py`; Zahl: Anteil wandernder scharfer Kameras (Ziel <= 2 %), Trefferquote "unbestimmt/zu_wenig wandert" (Ziel >= 70 %). ~40 min. Erst dann in die Kette.
3. **Streuung als Messgroesse je Kamera nutzen (PLAUSIBEL, nur falls 1 keinen Schalter liefert).** Statt Determinismus zu erzwingen: `kamera_unsicherheit_lokal` + Schaerfe-Klasse zusammen als Tor fuer Wandbild-Kameras (am 19.11. unter Punkt 5 vorgeschlagen, am Schwabentor "alle Springer unter den 10 % unsichersten"). MESSPLAN: an Nord a/b: liegen die 9 trotz Sperrliste wandernden Bilder in den oberen 10 % der lokalen Unsicherheit? (Ziel >= 7 von 9.) 20 min.

### Nicht empfohlen
- Schwerkraft-Vorgabe je Bild, `ra_reweighting`, mehr BA-Runden, andere Seeds: gemessen, kein Gewinn bzw. schaedlich (Stellen oben). Offene COLMAP-PRs zu Pose-Prior-BA: betreffen den globalen Mapper nicht (am 19.11. notiert).
- Wechsel auf GLUEMAP wegen "robuster": Lizenz (Pi3-Gewichte, Doppelgangers++ NC) und Speicher (24 GB laut Arbeit) schliessen es aus; zur Laufstreuung sagt die Arbeit nichts.

---

## Lizenzbefunde dieser Recherche (in `LIZENZ_WERKZEUGE.md` nachzutragen - nicht von mir geaendert)

- **SegFormer (NVlabs): NVIDIA Source Code License, Abschnitt 3.3 nur nicht-kommerziell ("research or evaluation purposes only") - an der Quelle gelesen.** Bisher stand dort nur "other / NC als Einschaetzung". Betrifft `handy_masken.py`, `video_masken.py`, `gebaeude_segment.py` und damit die neue SfM-Vorstufe.
- **Doppelgangers++: Code CC BY-NC-SA 4.0 (LICENSE gelesen); Gewichte zusaetzlich an NC-Datensatzlizenzen gebunden (CHECKPOINTS_NOTICE gelesen).** Bisher "ungeprueft an der Quelle". MASt3R: CC BY-NC-SA 4.0, README gelesen.
- **Pi3 / Pi3X: Code BSD-3, Gewichte CC BY-NC 4.0 (README gelesen).** GLUEMAP-Code neues BSD (README gelesen), Standardgewichte damit nicht verkaufstauglich.
- **RF-DETR: Code Apache-2.0; alle Seg-Groessen Apache-2.0 (README gelesen).** Trainingsdaten der Seg-Gewichte im README nicht benannt.
- **SAM 2 / 2.1: Code und Gewichte Apache-2.0 (README gelesen).** Bisher nur "laut Recherche".
- **Mask2Former: Code MIT (README gelesen), Gewichte ohne Lizenzangabe; DETR-ResNet-50-panoptic: HF-Karte apache-2.0 (gelesen).**
- **MoGe: Code MIT (README gelesen), Gewichtslizenz im README nicht genannt.** PySceneDetect BSD-3 (README gelesen). Doppelgangers Original MIT (README gelesen, wie im Register).
- **AnyCalib fehlt im Lizenzregister** (wird im COLMAP-Bau als `single_view_calibrator` benutzt) - vor Vorschlag 3.2 nachtragen und pruefen.

## Was ich NICHT pruefen konnte

- Cohen et al. ICCV 2015: PDF HTTP 403, nur die Zusammenfassung gelesen; ob es Code gibt, unbekannt.
- COCO-Nutzungsbedingungen und Klassenliste: Seite liess sich nicht auslesen; "COCO hat die Klasse train" und "Cityscapes/Mapillary Vistas sind nicht-kommerziell" stammen aus meinem Wissen.
- Ob RF-DETR-Seg Strassenbahnen als `train` erkennt, wie viel VRAM es braucht und worauf die Seg-Gewichte genau trainiert sind.
- Doppelgangers++-Zahlen (nur als Bildtabellen auf der Projektseite), VRAM-Bedarf; GLUEMAP auf 8 GB; Lizenzen von VGGSfM und SALAD.
- Extreme-View-Arbeit (arXiv 2511.22686): Code-Stand, Lizenz, Zahlen nach dem Nachtrainieren.
- CVD-SfM und Georegistrierung ohne Metadaten: nur Suchtreffer, nicht gelesen.
- COLMAP-Issues zur Laufstreuung des globalen Mappers: Suche ohne Treffer; ob es dazu Meldungen oder Korrekturen nach dem eigenen Baustand (4.3.dev) gibt, ist offen.
- EoMT-Gewichtslizenz, MoGe-2-Gewichtslizenz (HF-Karten nicht abgerufen), GeoCalib heute nicht erneut gelesen (Angabe vom 19.11.).
- Fuer elektronische Bildstabilisierung/Zoom in Fremdvideos als Fehlerquelle fand ich keine Quelle.
- Keiner der Messplaene wurde ausgefuehrt; alle Zielzahlen sind Erwartungen, keine Ergebnisse.

## Quellen (heute abgerufen, soweit nicht anders vermerkt)

- Doppelgangers++: https://doppelgangers25.github.io/doppelgangers_plusplus , https://github.com/doppelgangers25/doppelgangers-plusplus (LICENSE, CHECKPOINTS_NOTICE), arXiv https://arxiv.org/abs/2412.05826 (nur Suchtreffer)
- Doppelgangers: https://github.com/RuojinCai/doppelgangers
- MASt3R: https://github.com/naver/mast3r
- GLUEMAP: https://arxiv.org/abs/2605.26103 , https://arxiv.org/html/2605.26103v2 (erste 100 000 Zeichen gelesen), https://github.com/colmap/gluemap
- Pi3: https://github.com/yyfz/Pi3
- FlexGlue: https://github.com/cvg/FlexGlue
- GLOMAP: https://arxiv.org/html/2407.20219v1
- COLMAP FAQ: https://colmap.github.io/faq.html ; Aenderungsprotokoll https://colmap.github.io/changelog.html (nur Suchtreffer)
- SegFormer-Lizenz: https://raw.githubusercontent.com/NVlabs/SegFormer/master/LICENSE
- RF-DETR: https://github.com/roboflow/rf-detr
- SAM 2: https://github.com/facebookresearch/sam2
- Mask2Former: https://github.com/facebookresearch/Mask2Former ; DETR panoptic: https://huggingface.co/facebook/detr-resnet-50-panoptic ; EoMT: https://github.com/tue-mps/eomt
- MoGe: https://github.com/microsoft/MoGe ; PySceneDetect: https://github.com/Breakthrough/PySceneDetect
- Cohen et al.: https://openaccess.thecvf.com/content_iccv_2015/html/Cohen_Merging_the_Unmatchable_ICCV_2015_paper.html (nur Zusammenfassung)
- Extreme-View 3DFM: https://arxiv.org/abs/2511.22686 , https://cornell-vailab.github.io/Ext-3DFMs/
- Nur als Suchtreffer: CVD-SfM https://arxiv.org/html/2508.01936v1 ; Georegistrierung https://arxiv.org/pdf/2503.04927 ; MegaScenes https://arxiv.org/abs/2406.11819
- Eigener Bau: `colmap global_mapper --help`, `colmap mapper --help`, `colmap help` (/media/oem/scan/colmap-build/prefix/bin/colmap, nur Hilfetexte)

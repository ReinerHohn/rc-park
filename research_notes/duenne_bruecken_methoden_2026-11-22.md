# Duenne Bruecken: Schwachstellen automatisch finden und dort mehr herausholen (Recherche 22.11.2026)

Auftrag (Nutzer, 22.11.): "Die Methode muss vollautomatisiert so robust sein, dass sie auch mit duennen Bruecken umgehen kann und softwaretechnisch alles rausholt und dann eben vollautomatisch merkt, an Stellen, wo es schwach wird, dann mit Software nochmal mehr rausholt als Nachmatchen. Suche nach weiteren solchen geilen Methoden."

Nur gelesen und recherchiert, nichts gerechnet. Lizenzen: GitHub-API (`api.github.com/repos/...`, Feld license) und LICENSE/README an der Quelle am 22.11. gelesen, sonst als "ungeprueft" markiert. Kennzeichnung je Methode: CODE = lauffaehiger Code mit passender Lizenz vorhanden; PAPER = nur aus Veroeffentlichung bekannt; EIGEN = Eigenbau aus vorhandenen Bausteinen.

## Was der Ist-Stand schon sagt (Grundlage der Rangfolge)

- Gemessen (Zweig `worktree-agent-a0747560562618247`, `Doku/projekt/lage-seiten.md` Zeile 85 dort): Brueckenbreite ab k = 5 kaum wirksam, der HEBEL entscheidet; Nachmatchen ALIKED+LightGlue im Selbsttest 0,83 -> 0,21 Grad, 0,14 -> 0,024 m; am Schwabentor 1122 Nachmatchen Hebel 0,23, Rest 0,63 % > 0,5 % -> abgelehnt, SIFT gilt.
- Gemessen: Suedwand-Versatz in ALLEN Kopplungsvarianten gleich (0,70-0,80 m alter Rahmen, 0,38 m neuer Lot-Rahmen) -> der Rest kommt NICHT aus der Bruecke.
- Gemessen: Kopplung sieht innere Verformung eines Teils nicht (13-16 von 20 verformten Faellen bestehen).
- Wichtige Luecke des Selbsttests (`tools/versuche/eck_selbsttest.py`, Kopf): "die Eigenverformung getrennt gerechneter Teilmodelle ist hier NICHT enthalten" - Teil A/B sind ausgeschnittene Stuecke EINES guten Modells. Genau der Fehler, der am Schwabentor uebrig bleibt, ist im Selbsttest also nicht drin.
- `seiten_eck_koppeln.py` koppelt mit freier Sim3 (7 Freiheitsgrade); das Fluchtpunkt-Lot je Teil geht in die Kopplung nicht ein.
- `pycolmap.estimate_ba_covariance` scheiterte am Schwabentor-Modell (Schur-Komplement rangdefizient; `LOGBUCH_KETTENTEST_2026-11-19.md` 20.11. 00:30), Ersatz lokal je Kamera `tools/versuche/kamera_unsicherheit_lokal_1120.py` (Rangkorrelation Unsicherheit~Sprung 0,43).
- Schon vorhanden und nicht neu vorzuschlagen: Bildsuche DINOv2 (`tools/bildsuche_paare.py`, MegaLoc bewusst nicht), FlexGlue, Durchblick-Kriterium, Doppelgaenger-Pruefer (MIT), GPS-Fit mit Band, Lot aus Fluchtpunkten, Spannbaum + Kreisschluss, Wiederholbarkeit je Zwischenmodell, Video-Bruecke (gescheitert an Verwechslung/Zeitkette), `model_merger` (verworfen: braucht gemeinsame Bilder - mit dem Zwischenmodell gibt es die jetzt aber, siehe Methode 7).
- In pycolmap 4.2.1 (venv-colmap, heute per `dir(pycolmap)` geprueft) vorhanden und im Repo ungenutzt: `align_reconstructions_via_reprojections`, `align_reconstructions_via_proj_centers`, `estimate_sim3d_robust`, `run_rotation_averaging`, `create_pose_prior_bundle_adjuster`, `BACovariance`/`get_covariance_for_relative_rigid3d`, `IncrementalTriangulator`. OpenCV 5.0 in venv-seg hat `cv2.AffineFeature` (ASIFT-Huelle).

## Die Methoden (priorisiert)

### 1. Selbsttest Stufe 2: Teile wirklich getrennt rechnen + kuenstliche Verformung (Voraussetzung fuer alles Weitere)
- Idee: Im Selbsttest Teil A und Teil B nicht ausschneiden, sondern je Teil mit dem Ketten-Mapper NEU rechnen (wie in der Kette), dazu Varianten mit eingespielter Verformung (Massstabsverlauf 2/5 % ueber die Laenge, Biegung 1/3 Grad um das Lot und um die Querachse). Wahrheit bleibt das ungetrennte Modell.
- Warum: Ohne das misst jeder weitere Vorschlag nur den Kopplungsfehler, der bereits klein ist (0,2 Grad/2,4 cm); der Schwabentor-Rest (0,38 m) liegt in der Teilverformung bzw. im Rahmen.
- Braucht: Selbsttest-Daten (Martinstor-Nord, Schwabentor Teil 0), globaler Mapper je Teil (~15 min je Teil nach METHODE_SEITEN_SFM), keine neue Lizenz. EIGEN.
- Schon versucht: nein (Selbsttest schliesst es ausdruecklich aus).
- Aufwand klein-mittel. Nutzen: macht die Methoden 2-6 erst messbar.
- Messung: Lagefehler B (Grad/m/Massstab) bei k = 3/5 fuer (a) ausgeschnitten, (b) neu gerechnet, (c) neu gerechnet + Verformung. Widerlegt (= Teilverformung unwichtig), wenn (b) nicht schlechter als (a) ist (Unterschied < Wiederholungsstreuung) - dann liegt der Schwabentor-Rest im Lot-/LoD2-Rahmen, nicht im Modell.

### 2. Lotfeld je Kamera als Verformungs-Detektor ("wo biegt sich ein Teil?")
- Idee: Fuer jede Kamera das Fluchtpunkt-Lot im Bild (schon in `schwerkraft_je_bild`) mit dem Lot vergleichen, das die SfM-Pose dieser Kamera im Teilrahmen vorhersagt. Ein starres Teil hat ein konstantes Restfeld; Biegung zeigt sich als Gradient des Restes ueber die Kameralage (1-3 Grad sind gross gegen die gemessenen 0,44-0,63 Grad Lotgenauigkeit).
- Warum: Unabhaengig von der Bruecke und von Punktzuordnungen - genau die Fehlerart, die die Kopplung nicht sieht. Liefert automatisch die "schwache Stelle" innerhalb eines Teils.
- Braucht: vorhandene Fluchtpunkte je Bild, CPU, Sekunden. EIGEN (lauffaehig aus Repo-Bausteinen, Lizenz eigen).
- Schon versucht: Lot nur GLOBAL je Teil (lage-seiten Zeilen 39/40); je Kamera als Feld nicht gefunden.
- Aufwand klein. Nutzen hoch (Diagnose), Korrektur siehe Methode 5.
- Messung: Selbsttest Stufe 2 mit eingespielter Biegung: Erkennungsrate bei 1/3 Grad, Fehlalarm bei 0. Am Schwabentor: Gradient im Suedteil, und ob er die 0,38 m Suedwand ueber die Hebellaenge erklaert. Widerlegt, wenn 3 Grad Biegung nicht ueber dem Rauschen liegt oder das Schwabentor-Feld flach ist (< 0,3 Grad ueber das Teil) und der Versatz trotzdem bleibt.
- Zusatz im selben Werkzeug (ebenfalls EIGEN): Massstabsfeld aus wiederkehrenden Massen entlang der Wand (Quaderlagen-/Gesimshoehen per `foto_mass.py`/Kantenstufe je Wandabschnitt) - Massstabsverlauf 2-5 % wird so sichtbar. Achtung: was hier misst, darf nicht zugleich in Methode 5 als Zwang dienen, sonst ist es kein Tor mehr (Lotfeld: halbe Kameras zum Zwang, halbe zur Probe, oder Fluchtpunkt-Lot zum Zwang und Wandneigungs-Lot-Tor der dichten Wolke als unabhaengige Probe).

### 3. Lot-gebundene Kopplung (4 statt 7 Freiheitsgrade + Massstab)
- Idee: Beide Teile zuerst je fuer sich an ihr Fluchtpunkt-Lot stellen; die Kopplung schaetzt dann nur Drehung um das Lot, Verschiebung und (wenn belegt) Massstab. Robust per RANSAC mit 2-Punkt-Minimalloeser statt 3-Punkt-Sim3.
- Warum: Bei duenner Bruecke mit kurzem Hebel ist gerade die Kippung schlecht bestimmt (ein kurzes Punktfeld hebelt 1 Grad zu 0,3-0,7 m am anderen Gebaeudeende). Mit festem Lot traegt die Bruecke nur noch das, was sie gut kann. Literatur: gravity-aware/4-DoF-Registrierung ist Standard in VIO-Loop-Closure (z. B. VINS-Mono 4-DoF-Posegraph) - PAPER-Wissen, Umsetzung EIGEN.
- Braucht: Lot je Teil (vorhanden), Aenderung in `sim3_robust`/`seiten_eck_koppeln`, CPU.
- Schon versucht: Lot fest im LoD2-Feinfit (`AUSR_KIPP_FEST`, lage-seiten Zeile 40) - aber nicht in der Bruecken-Kopplung.
- Aufwand klein. Nutzen mittel-hoch bei k = 3 und Hebel < 0,3.
- Messung: Selbsttest k = 3/5, Lagefehler und Streuung ueber Wiederholungen (Wiederholbarkeit), aufgetragen ueber den Hebel. Widerlegt, wenn bei Hebel < 0,3 der Lagefehler nicht mindestens um ein Drittel sinkt oder wenn ein Lotfehler der Teile (Methode 2) den Gewinn auffrisst (Gegenprobe: Lot absichtlich um 0,5 Grad verfaelschen).

### 4. Projektionsgefuehrtes Nachmatchen nach der ersten Kopplung (Schleife Koppeln -> Fuehren -> Koppeln)
- Idee: Nach der ersten Kopplung sind alle Kameras beider Teile in einem Rahmen. Fuer Bildpaare UEBER den Schnitt (A-Bild, B-Bild - auch solche, die Bildsuche und SIFT nie gepaart haben) die 3D-Punkte von A in die B-Bilder projizieren und nur im Fenster (Radius aus dem Unsicherheitsband) Deskriptoren vergleichen; ebenso Brueckenbilder per PnP getrennt gegen A und gegen B neu einmessen. Neue Spuren reichen tief in beide Teile -> Hebel steigt, dann neu koppeln.
- Warum: Der Hebel ist der Engpass; gefuehrte Suche findet Zuordnungen, die das freie Matchen bei Blickwinkel-/Massstabsunterschied verwirft (Verhaeltnistest scheitert an sich wiederholenden Quadern, mit Lagefenster nicht). COLMAP kennt epipolar gefuehrtes Matchen (Option `guided_matching`, laut COLMAP-Doku; im eigenen 4.3-Bau nicht geprueft, Programm startete hier nicht wegen fehlender CUDA-Bibliothek im Pfad); projektionsgefuehrt = EIGEN mit pycolmap (`IncrementalTriangulator`, Merkmale aus der DB).
- Gefahr Symmetrie: die Fuehrung kann eine falsche Lage selbst bestaetigen. Pflicht-Negativfall: Start mit absichtlich falscher Kopplung (2 Grad, 0,5 m, 180-Grad-Klappung) muss abgelehnt oder zurueckgefuehrt werden; Doppelgaenger-Pruefer + Durchblick bleiben Veto, Fenster nie groesser als 3 sigma.
- Braucht: CPU (+ ALIKED-Deskriptoren schon vorhanden), Minuten je Bruecke. Lizenz eigen + pycolmap BSD-3 (GitHub-API `colmap/pycolmap`: BSD-3-Clause).
- Schon versucht: nein (bruecke_nachmatchen.py matcht frei, alle Paare der kleinen Menge).
- Aufwand mittel. Nutzen hoch (direkt am gemessenen Engpass Hebel).
- Messung: Hebel vorher/nachher, Lagefehler k = 3/5, Negativfaelle. Am Schwabentor 1122: Rest-Grenze 0,5 % (heute 0,63 % bei Nachmatchen) und Suedwand. Widerlegt, wenn der Hebel nicht ueber 0,3 steigt oder ein Negativfall bestaetigt wird.

### 5. Halbstarrer gemeinsamer Buendelausgleich mit Zusatzzwaengen (statt starrer Kopplung)
- Idee: Nach Kopplung A + Bruecke + B in EIN Modell schreiben (Spuren ueber gemeinsame Bildpunkte vereinen), A-Posen fest, B-Posen frei, und nur wenige Zusatzterme: Lot je Kamera aus Fluchtpunkten (weich, mit gemessener Streuung), Intrinsik je Geraet fest (EXIF-Modell, wo `brennweite_schaerfe` "scharf" sagt), GPS-Position als Prior nur mit dem ehrlichen Band je Sitzung. Lokal begrenzt auf die Bruecke + n Nachbarschritte, damit es nicht 11 min je Ausgleich dauert.
- Warum: Laesst B sich biegen, wenn die Daten es verlangen (Methode 2 sagt wo), statt die Biegung als Lagefehler in die Suedwand zu schieben; die Lot-Terme sind ein von Punkten unabhaengiger Zwang gegen Biegung. Gegen den globalen Mapper: keine Drehungsmittelung, die die duenne Bruecke ueberstimmt (16-Grad-Knick 22.11.).
- Braucht: pycolmap 4.2.1 (`create_pose_prior_bundle_adjuster` fuer GPS-Positionen vorhanden); Lot-Term braucht eigenen Kostenterm (pyceres, ungeprueft ob in venv-colmap installiert - ANNAHME). CPU, 16 GB reichen fuer Ausschnitt.
- Schon versucht: "mehr BA auf gleichen Zuordnungen hilft nicht" (lage-seiten Zeile 47, 15.11.) und "Entfernen + BA aendert den Widerspruch nicht" (12:45) - beides OHNE neue Spuren und OHNE Lotzwang. Anders jetzt: neue Querspuren aus Methode 4 + Lot je Kamera.
- Tor-Unabhaengigkeit: dann pruefen nur noch Wandneigungs-Lot-Tor (dichte Wolke), Kamerahoehe ueber DGM1 (`kamera_gefaelle`) und Durchfahrt-Innenflaechen - DGM1 deshalb NICHT als Zwang verwenden.
- Aufwand mittel. Nutzen hoch, falls Methode 1/2 Teilverformung belegen; sonst gering.
- Messung: Selbsttest Stufe 2 mit Verformung: Restverformung nachher; Schwabentor Suedwand 0,38 m und Durchfahrt 0,16 m/2-3 Grad. Widerlegt, wenn bei eingespielter 3-Grad-Biegung weniger als die Haelfte zurueckgeholt wird oder die Durchfahrt schlechter wird.

### 6. Schwachstellen-Radar im Bild-/Spurgraph (automatischer Ausloeser)
- Idee: Nach jedem Mapper je Modell und ueber alle Teile einen gewichteten Graphen bauen (Knoten Bilder, Gewicht = verifizierte Inlier bzw. gemeinsame 3D-Punkte) und messen: Gelenkbilder (Artikulationspunkte), minimaler Kantenschnitt zwischen Gemeinschaften, Fiedler-Wert (zweitkleinster Eigenwert der Laplace-Matrix) je Teilgraph, Zahl kantendisjunkter Spannbaeume ueber den Schnitt, Spurlaengen und Triangulationswinkel der Punkte, die den Schnitt ueberqueren. Ausgabe: Liste der Schwachstellen mit Ort (Bilder) -> loest Methode 4/7 dort aus.
- Warum: Der 16-Grad-Knick hing an "5 Spuren ueber EIN Bild" - ein Gelenkbild, das ein Radar sofort meldet. HiSfM (arXiv 2609.04718, Sept. 2026) baut sein Geruest genau aus kantendisjunkten Spannbaeumen und prueft jede Geruestkante mit einem Doppelgaenger-Pruefer - PAPER, Code-URL `github.com/3dv-casia/HiSfM` laut Abstract, Repo am 22.11. nicht gefunden (API "Not Found") -> nur Idee. Ebenso "Global-Aware Edge Prioritization" (arXiv 2602.21963, CVPR 2026, Code `weitong8591/global_edge_prior` ohne Lizenz = nicht verwendbar).
- Braucht: networkx/scipy (BSD), Sekunden. EIGEN.
- Schon versucht: Louvain-Gemeinschaften (lage-seiten Zeile 50), Fiedler/Gelenke/Schnitt: 0 Treffer im Repo.
- Aufwand klein. Nutzen mittel (macht die Automatik "merkt wo es schwach wird" erst moeglich).
- Messung: Selbsttest mit Brueckenbreite k = 1/3/5 und verschieden weit reichendem Zwischenmodell: Rangkorrelation Radarwert ~ Lagefehler (Ziel > 0,6). Muss den 1122-Knick (globaler Mapper mit Eckpaaren) als Gelenk melden. Widerlegt, wenn die Korrelation < 0,3 ist oder der Hebel allein (schon vorhanden) genauso gut vorhersagt.

### 7. Ausrichtung ueber Rueckprojektion gemeinsamer Bilder (pycolmap `align_reconstructions_via_reprojections`) als zweite, unabhaengige Kopplung
- Idee: Statt (nur) Sim3 ueber gemeinsame 3D-Punkte die Teile ueber die gemeinsamen Brueckenbilder ausrichten: Punkte des einen Modells in die Bilder des anderen projizieren und den Rueckprojektionsfehler minimieren (das ist der Kern von COLMAPs `model_merger`). Zwei Kopplungen mit verschiedener Fehlerart -> ihr Unterschied ist ein eingebauter Plausibilitaetswert.
- Warum: Punkt-Sim3 gewichtet ferne, schlecht triangulierte Punkte gleich; die Bildraum-Ausrichtung gewichtet nach Messgenauigkeit. Bei Hebel 0,06-0,23 ist das der Unterschied zwischen "zufaellig gut" und "belegt".
- Braucht: pycolmap 4.2.1 (vorhanden, BSD-3), Achtung `bruecke_nachmatchen.py`-Notiz: pycolmap 4.2.1 kann 4.3-Datenbanken nicht oeffnen - Modelle (sparse) gehen, DB nicht. CODE.
- Schon versucht: `model_merger` verworfen, weil "keine gemeinsamen Bilder" (RECHERCHE_SEITEN_SFM Zeile 128) - mit dem Zwischenmodell gibt es sie jetzt.
- Aufwand klein. Nutzen mittel.
- Messung: Selbsttest k = 3/5: Lagefehler beider Kopplungen und ob ihr Unterschied den wahren Fehler vorhersagt (Rang > 0,5). Widerlegt, wenn beide immer gleich sind (dann keine Zusatzinformation).

### 8. Entzerrung auf die Fassadenebene / Sichtsimulation vor dem Matchen (ASIFT-artig)
- Idee: Eckfotos sehen beide Waende unter steilem Winkel. Vor dem Matchen jedes Brueckenbild je sichtbarer Wand per Homographie auf die Wandebene entzerren (Ebene aus zwei Fluchtpunkten des Bildes, ohne 3D; oder aus der Teilwolke), matchen, Punkte zuruecktransformieren. Ohne Ebene: affine Sichtsimulation (OpenCV `AffineFeature` = ASIFT-Huelle um ALIKED/SIFT, in cv2 5.0 vorhanden, Apache-2.0).
- Warum: Gegen Blickwinkelunterschied > 40-50 Grad brechen SIFT und auch ALIKED ein; entzerrte Bilder machen die Ecke von beiden Seiten "frontal" vergleichbar -> mehr Spuren, groesserer Hebel. Passt zur Kernmethode (Wandbild = Bauplan, `fassade_fein.py` entzerrt schon).
- Braucht: GPU optional, Minuten fuer 20-200 Bilder. CODE (OpenCV) + EIGEN.
- Schon versucht: nein (asift/Homographie-vor-Matchen 0 Treffer).
- Aufwand klein-mittel. Nutzen mittel.
- Messung: Inlier und Zellabdeckung der Querpaare, dann Hebel und Lagefehler k = 3/5. Widerlegt, wenn Querpaar-Inlier nicht um > 30 % steigen (Wert aus dem Unterschied SIFT/ALIKED abgeleitet, ANNAHME).

### 9. Staerkerer (halb)dichter Matcher NUR an der Schwachstelle
- Idee: Nur die 50-500 Paare der Schwachstelle mit einem dichten Matcher nachrechnen und wie bei `bruecke_nachmatchen.py` hinten an die SIFT-Merkmale haengen.
- Warum: Dichte Matcher finden Zuordnungen auf texturarmen/sich wiederholenden Flaechen und bei grossem Blickwinkel; ein Paar mit 2000 gut verteilten Zuordnungen hebelt mehr als zehn mit 50.
- Kandidaten und Lizenz (Primaerquellen, 22.11. gelesen):
  - RoMa v1 (`github.com/Parskatt/RoMa`): Code MIT ("All our code except DINOv2 is MIT license", README), DINOv2 Apache-2.0; Gewichte: keine eigene Lizenzzeile, trainiert auf MegaDepth - Projektseite `cs.cornell.edu/projects/megadepth`: Datensatz CC BY 4.0, Originalbilder mit eigenen Lizenzen. Bewertung: plausibel ja, Gewichte formal ungeprueft. GPU 8 GB: ANNAHME passt bei 560 px in fp16. CODE.
  - EfficientLoFTR (`zju3dv/EfficientLoFTR`): LICENSE "Project Registration License (PRL) v1.0": Projektnutzung "permitted free of charge, provided that the Project Use is registered before such use begins" (Google-Formular), gilt ausdruecklich auch kommerziell. Bewertung: ja mit Auflage (Registrierung vor Einsatz). CODE.
  - MatchAnything (`zju3dv/MatchAnything`): gleiche PRL v1.0, Gewichte auf HuggingFace; Trainingsdaten (u. a. synthetische Modalitaeten) ungeprueft. Bewertung: ja mit Auflage, Gewichte ungeprueft. CODE.
  - XFeat (`verlab/accelerated_features`): Apache-2.0 (API), Gewichte im Repo; sehr schnell, aber eher schwaecher als ALIKED bei grossem Blickwinkel (ANNAHME). CODE.
  - GIM (`xuelunshen/gim`): MIT laut API, README zugleich "provided here for research purposes only. Any use beyond this is your sole responsibility" -> unklar, nicht fuer Verkauf ohne Klaerung.
  - LoMa `commercial_*` (Register 22.11.: ja mit Auflage), FlexGlue (vorhanden, MIT + DINOv3-Lizenz).
  - NEIN: MASt3R/DUSt3R (LICENSE CC BY-NC-SA 4.0, gelesen), RoMa v2-Gewichte (Register: ungeprueft).
- Schon versucht: ALIKED+LightGlue (Selbsttest gut, 1122 Rest 0,63 % -> abgelehnt), FlexGlue (trennt Seiten nicht besser). Dichte Matcher an der Bruecke: nein.
- Aufwand klein (Einhaengen wie ALIKED). Nutzen mittel; der 1122-Befund (mehr Zuordnungen, Rest steigt) warnt: mehr Matches ohne mehr Hebel bringen wenig -> erst NACH Methode 4/8 und nur, wo das Radar (6) es verlangt.
- Messung: wie 8; zusaetzlich Rest-Grenze 0,5 % am 1122. Widerlegt, wenn Hebel und Lagefehler sich gegenueber ALIKED nicht verbessern.

### 10. Ebenen-Zwang ueber die gemeinsame Ecke (Ebene-zu-Ebene statt Punkt-zu-Punkt)
- Idee: Beide Teile sehen an der Ecke dieselben zwei Waende + Boden. Je Teil Ebenen aus der dichten bzw. sparse Wolke im Eckbereich schaetzen; drei nicht parallele Ebenen legen Drehung und Lage vollstaendig fest (Massstab nicht). Als zusaetzliche Kante neben der Punkt-Kopplung, nicht als Ersatz.
- Warum: Ebenen sind ueber viel groessere Flaechen gemittelt als die Brueckenpunkte -> laengerer Hebel fuer Drehung; unabhaengig von Merkmalszuordnung zwischen den Teilen (keine Verwechslungsgefahr, solange die Ecke stimmt).
- Braucht: Open3D (MIT laut LICENSE, gelesen) oder numpy, CPU, Sekunden. EIGEN.
- Schon versucht: "Teil 1 ueber Gebaeudekanten binden (Wandebene + Ecke + Boden, Merging the Unmatchable)" -> offen, kein Massstab (lage-seiten Zeile 74). Anders jetzt: Massstab kommt aus der Bruecke, Ebenen tragen nur Drehung; ICP mit freiem Massstab (BS143) bleibt verworfen.
- Tor-Unabhaengigkeit: Eckwaende zum Anpassen, Durchfahrt-Innenflaechen und Suedwand-Gegenwand bleiben Probe.
- Aufwand klein-mittel. Nutzen mittel.
- Messung: Selbsttest: Drehfehler mit/ohne Ebenenkante bei k = 3. Schwabentor: Winkel Suedwand gegen LoD2 (heute +1,1 Grad). Widerlegt, wenn Ebenen-Drehung und Punkt-Drehung sich um mehr als ihr Band widersprechen und die Ebene nicht die bessere ist (Probe Durchfahrt).

### 11. Konsistenz-Maximierung ueber mehrere Bruecken (PCM / GNC statt Mittelung)
- Idee: Jede Bruecke (Eckfotos, Video-Abschnitte, Drohne, Querspuren) ist eine Kante mit Sim3 + Band. Statt der staerksten Kante (Spannbaum) wird die groesste paarweise konsistente Kantenmenge gesucht (Pairwise Consistency Maximization) bzw. mit Graduated Non-Convexity robust ausgeglichen; falsche Kanten (Verwechslung) fallen heraus, statt den Kreis zu verwerfen.
- Warum: Die Video-Bruecke scheiterte an Verwechslung ueber einzelne Paare - PCM erkennt genau solche Kanten, sobald es >= 2 unabhaengige Wege gibt. Heute verwirft der Kreisschluss bei Widerspruch alle Teile des Kreises.
- Braucht: Kimera-RPGO (`MIT-SPARK/Kimera-RPGO`, BSD-2-Clause laut API) oder GTSAM (`borglab/gtsam`, LICENSE "simplified BSD", gelesen); oder eigener Kleinst-PCM (wenige Kanten, numpy). CODE/EIGEN.
- Schon versucht: Spannbaum + Kreisschluss (vorhanden), PCM/GNC: nein.
- Aufwand mittel. Nutzen gering solange es nur EINE Bruecke gibt (Schwabentor heute) - erst sinnvoll mit Teil 2/3 und Videos.
- Messung: Selbsttest mit 2-3 Bruecken, eine davon absichtlich verwechselt (180 Grad): muss sie verwerfen und die richtige Lage behalten. Widerlegt, wenn bei einer echten und einer falschen Kante falsch entschieden wird.

### 12. Beleuchtungs-/Sonnen-Tor fuer Seiten und Drehung (unabhaengige Probe)
- Idee: Aus EXIF-Zeit + Ort den Sonnenvektor rechnen (pvlib, BSD-3 - Lizenz ungeprueft) und je Bild pruefen, ob die laut Modell sonnenzugewandten Waende heller sind als die abgewandten (Helligkeitsverhaeltnis je Wandflaeche). Eine 180-Grad-Verwechslung oder eine grob falsche Drehung kehrt das Vorzeichen um.
- Warum: Symmetrie aendert die Geometrie nicht, aber die Beleuchtung; voellig unabhaengig von Zuordnungen und GPS - ein Tor, kein Anpasser.
- Braucht: EXIF-Zeit mit Zeitzone (Nubia/iPhone ja, Netzfotos oft nicht), CPU. EIGEN.
- Schon versucht: nein (Doppelgangers++ waere Alternative, LICENSE gelesen: CC BY-NC-SA 4.0 -> nein).
- Aufwand klein. Nutzen: nur fuer grobe Fehler (Seite, > 20 Grad), nicht fuer 0,38 m.
- Messung: an verklebten Modellen (Martinstor Nachtmodell, 1122b 20 Grad) und richtigen: Trefferquote. Widerlegt, wenn bewoelkte/Schattenlagen mehr als 20 % "unklar" erzeugen und richtige Modelle rot werden.

### 13. Mono-Priors fuer Bilder mit wenig Ueberlappung (MP-SfM-Ansatz) und Massstab aus MoGe-2
- Idee: MP-SfM (`cvg/mpsfm`, Code Apache-2.0 laut API; CVPR 2025) registriert Bilder mit kaum Ueberlappung ueber monokulare Tiefe und Normalen; austauschbare Priors. Mit MoGe-2 (Register: Code+Gewichte MIT) statt MASt3R (NC) koennten Brueckenbilder mit 10-30 Inliern sicherer eingemessen werden; zusaetzlich Massstab des einwandigen Teils 1 aus metrischer Tiefe (heute +-12 %).
- Warum: Genau der Fall "Eckbild mit wenigen Zuordnungen" (Registrierungsschwelle musste 12 statt 30 sein).
- Braucht: GPU (MoGe-2 ~2-3 GB, ANNAHME), Umbau der MP-SfM-Konfiguration auf erlaubte Priors; Standardkonfigurationen nutzen MASt3R/DepthPro/Metric3D -> je Prior Lizenz pruefen (DepthPro/Metric3D/DSINE ungeprueft). PAPER + CODE (mit Austausch).
- Schon versucht: VGGT/MASt3R-Lage zwischen Gegenseiten (NC, zu grob, RECHERCHE_SEITEN_SFM Zeile 143); MP-SfM nicht.
- Aufwand gross. Nutzen mittel-unsicher.
- Messung: Selbsttest k = 3 mit Schwelle 30 statt 12: registrierte Brueckenbilder und Lagefehler. Widerlegt, wenn nicht mehr Brueckenbilder sicher registrieren als mit Schwelle 12 oder der Massstab aus MoGe-2 schlechter als +-5 % gegen Wahrheit ist.

### Bewusst NICHT oben eingereiht (mit Grund)
- GlueMap (`colmap/gluemap`, CVPR 2026, Pan/Schoenberger/Pollefeys): Code BSD (LICENSE gelesen), aber Standard-Checkpoints Pi3 (Register: NC), VGGSfM-Tracker (`facebookresearch/vggsfm` LICENSE.txt: CC BY-NC 4.0, gelesen), Doppelgangers++ (NC), SALAD (`serizba/salad` GPL-3.0). Verkaufstauglich nur mit Backbone MapAnything-Apache und ohne D++; ob Tracker/SALAD abschaltbar sind, ungeprueft. Ausserdem globaler Ansatz = Drehungsmittelung, die duenne Bruecken ueberstimmt. Nur als Messtest.
- Gewichtete Drehungsmittelung (`pycolmap.run_rotation_averaging`): der globale Mapper knickte an der Bruecke um 16-25 Grad; Gewichte helfen nur, wenn die Brueckenkanten mehr wiegen duerfen als hunderte Innenkanten - das ist Methode 5 in anderer Form, aber schwerer zu pruefen.
- Inkrementeller Mapper mit Start an der Bruecke: am 22.11. zu langsam (11 min je globalem Ausgleich, CPU); Methode 5 ist die lokale, schnelle Variante davon.
- Dichte Wolken der Teile per ICP/TEASER++ registrieren (TEASER++ MIT): bei Symmetrie gefaehrlich (globale Registrierung findet die Spiegellage), freie Skala verworfen (BS143); nur als feste-Skala-Feinkante in Methode 10.
- Bildsuche: vorhanden (DINOv2). Neu waere nur, sie gezielt von den Schnitt-Raendern aus ueber den GANZEN Bestand inkl. nicht registrierter Bilder laufen zu lassen - als Unterpunkt von Methode 6 (Ausloeser), nicht eigene Methode. Die echte Bruecke lag ohnehin schon in der DB und wurde vom strengen Filter geloescht (Logbuch 22.11. 20:00).
- MegaLoc: Code MIT, Trainingsdaten laut README nicht weitergebbar -> Gewichte unklar (Repo-Entscheidung bleibt).
- Gaussian Splatting (gsplat, Apache) als "virtuelle Brueckenbilder": ehrlich bewertet schafft das KEINE Information - die gerenderte Ansicht ist eine Funktion der vorhandenen Posen und Bilder von A. Was sie leisten kann: (a) Blickwinkelluecke fuer den Matcher verkleinern (A aus Sicht einer B-Kamera rendern, dann matchen = 2D-3D gegen A mit Erscheinungs-Synthese; Methode 8 erreicht den groessten Teil billiger), (b) Render-und-Vergleich als Tor (fotometrischer Unterschied B-Foto gegen A-Splat aus der gekoppelten Pose). Gefahr: Rueckkopplung, weil der Splat auf den Posen trainiert ist, die er pruefen soll. Aufwand gross (Splat-Training 8 GB GPU), Nutzen unsicher -> spaeter, hoechstens als Tor.

## Die naechsten 5 (Reihenfolge mit Begruendung)

1. Selbsttest Stufe 2 (Methode 1) - ohne getrennt gerechnete und kuenstlich verformte Teile misst jede weitere Methode an einem Fehler, der schon klein ist; der Schwabentor-Rest (0,38 m) liegt nicht in der Bruecke.
2. Lotfeld je Kamera + Massstabsfeld (Methode 2) - billigster Weg, die vermutete Teilverformung an echten Daten zu belegen oder zu widerlegen; entscheidet, ob Methode 5 gebaut werden muss.
3. Lot-gebundene Kopplung (Methode 3) - kleiner Eingriff in `sim3_robust`/`seiten_eck_koppeln`, wirkt genau bei kurzem Hebel, und das Lot ist gemessen die beste Quelle (0,44/0,63 Grad).
4. Projektionsgefuehrtes Nachmatchen mit Negativfaellen (Methode 4) + Entzerrung vor dem Matchen (Methode 8) - beide greifen den gemessenen Engpass HEBEL an; 8 liefert die Kandidaten, 4 die tiefen Spuren.
5. Schwachstellen-Radar (Methode 6) als Ausloeser in der Kette - macht aus den Einzelwerkzeugen die verlangte Automatik ("merkt, wo es schwach wird"), indem es Gelenkbilder/duenne Schnitte meldet und dort 4/8/9 startet.

Danach, abhaengig vom Ergebnis von 1-2: Methode 5 (halbstarrer Ausgleich), dann 7 und 10 als zweite unabhaengige Kopplungen, 11 erst bei mehreren Bruecken.

Parallel als Agent (nur Code + synthetische Tests, Worktree, nicht waehrend eines Kettenlaufs rechnen):
- Agent A: Methode 1 (Selbsttest Stufe 2: Verformungsgenerator + Neu-Rechnen je Teil als Option in `eck_selbsttest.py`).
- Agent B: Methode 2 (Lotfeld je Kamera, reines Lesen von Modell + `schwerkraft_je_bild`, mit synthetischer Biegung im Test).
- Agent C: Methode 3 (Lot-gebundene Sim3 in `sim3_robust` + Schalter in `seiten_eck_koppeln`, Test mit bekannter Wahrheit).
- Agent D: Methode 6 (Radar, networkx auf DB/Modell, Test: kuenstliches Gelenkbild muss gemeldet werden).
- Methode 4/8 erst nach 3 (braucht die bessere Startkopplung und das Band); kann als Agent E starten, sobald C gemergt ist.
- Rechenmessungen (Selbsttest-Laeufe) nacheinander ueber `tools/job_start.sh`, nicht in den Agenten.

## Quellen (am 22.11.2026 gelesen)
- HiSfM: https://arxiv.org/abs/2609.04718 (Code-Repo nicht auffindbar)
- Global-Aware Edge Prioritization: https://arxiv.org/abs/2602.21963 (Code ohne Lizenz)
- GlueMap: https://github.com/colmap/gluemap (LICENSE BSD, README Checkpoints), https://arxiv.org/abs/2605.26103
- VGGSfM LICENSE.txt (CC BY-NC 4.0): https://github.com/facebookresearch/vggsfm
- MASt3R LICENSE (CC BY-NC-SA 4.0): https://github.com/naver/mast3r ; Doppelgangers++ LICENSE (CC BY-NC-SA 4.0): https://github.com/doppelgangers25/doppelgangers-plusplus
- EfficientLoFTR / MatchAnything LICENSE (PRL v1.0): https://github.com/zju3dv/EfficientLoFTR , https://github.com/zju3dv/MatchAnything
- RoMa README Lizenz: https://github.com/Parskatt/RoMa ; MegaDepth-Lizenz: https://www.cs.cornell.edu/projects/megadepth
- GIM README Lizenz: https://github.com/xuelunshen/gim ; XFeat: https://github.com/verlab/accelerated_features ; MegaLoc README: https://github.com/gmberton/MegaLoc
- MP-SfM: https://github.com/cvg/mpsfm ; Kimera-RPGO: https://github.com/MIT-SPARK/Kimera-RPGO ; GTSAM: https://github.com/borglab/gtsam ; Open3D: https://github.com/isl-org/Open3D ; TEASER++: https://github.com/MIT-SPARK/TEASER-plusplus ; SALAD: https://github.com/serizba/salad ; SEA-RAFT (BSD-3, nicht eingereiht): https://github.com/princeton-vl/SEA-RAFT
- Weitere Literatur nur aus Suchergebnis, nicht vertieft: Perda/Morelli/Remondino, ISPRS Archives XLVIII-1-W4-2025 S. 95 (mehrdeutige Bildfolgen); Kim/Park/Kim, J. Comput. Des. Eng. 13(1) 2026 (3DGS zum Nachrichten fehlgesetzter Bilder); Heinly et al. ECCV 2014 / 3DV 2014; Wilson & Snavely (Network Principles for SfM).

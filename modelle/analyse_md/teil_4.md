# Teil 4: Analyse von 39 Markdown-Dateien (Liste _liste_4.txt)

Kennzeichen: [B] = belegt (Messung/Foto/Test, im Dokument mit Zahl oder Protokoll), [A] = Annahme (im Dokument so genannt), [M] = Meinung/Einzelaussage ohne Beleg im Dokument.
Dateinamen ohne Pfad = `modelle/<Datei>`. Sehr grosse Dateien (LOGBUCH_2026-11-09, STAND_2026-11-06, LOG_KOERPER_V9, UEBERGABE_2026-11-04, METHODE_MESSEN_DANN_BAUEN) nur ueber Ueberschriften, Anfang, Schluss und Stichproben gelesen. Reine Randdateien (QUICK_START_FREIBURG, schwarzwald_kandidaten, FINISH_STEINGEBAEUDE, FLUGPLAN_LINACHTALSPERRE, FERTIGUNG_SPLIT, MASSSTAB) betreffen nicht das Kaufhaus-Verfahren.

## 1. Was hat funktioniert

### Rahmen, Kameras, Lage (Grundlage jedes neuen Gebaeudes)
- Plausibilitaetsprobe der Kamerahoehe ueber Boden fing einen um ~25 Grad gekippten Wolkenrahmen: Kamera 6161 blickte in der Wolke 11 Grad nach unten, real 13 Grad nach oben; Kamerahoehe 15,8 m statt ~1,6 m. Korrektur ueber Lot aus Foto-Vertikalen (`lot_aus_fotos.py`, `rahmen_lot_foto.py`, Streuung 0,64 Grad Median) -> Kamerahoehe 1,5/2,0/2,3 m als unabhaengiger Beweis. [B] LOGBUCH_2026-11-08 Nr. 22-25. Alle Bauteilfits im alten Rahmen waren danach wertlos (Dach +2,7 m, Nr. 26). [B]
- Dach neu gegen lot2-Wolke: Median 0,71 -> 0,16 m, z_traufe 11,4 -> 14,8, z_first 20,6 -> 21,6. [B] LOGBUCH_2026-11-08 Nr. 27. Spaeter First aus dem Kantengitter 21,65 -> 27,51 (vorher "halbes Pultdach"). [B] LOGBUCH_2026-11-09 Runde 13.
- Brueckenpruefung Kamerakette (`kamera_bruecke_pruefen.py`): Tor Median <= 0,15 %, p90 <= 0,5 % der langen Seite, >= 30 Beobachtungen; Kaufhaus 96/96 im Tor (Median 1,17 px), Selbsttest 310/310 Verstellungen abgelehnt; Buendel 0,84 px, Kameras 1,65 m ueber Boden, Dach passt auf 0,06 m. [B] UEBERGABE_2026-11-04 Kernerkenntnis 3, 5.
- Brennweiten-Prior nur halten, wenn der Mapper +-15 % bestaetigt. [B] UEBERGABE_2026-11-04 Nr. 2.
- LoD2 nur fuer Richtung/Winkel nutzen (`lod2_winkel_abgleich.py`, --synth < 0,5 Grad), Hoehen unzuverlaessig (First 21,4/22,1; Traufe 9,65/10,53). [B] LOGBUCH_2026-11-08 Nr. 28.

### Messen, Zaehlen, Tore
- Beweis-Test mit bekannter Wahrheit (`--synth`) vor jedem Messwerkzeug: Erker/Fenster/Giebel/Boegen auf < 1 cm, auch mit 10 cm Rauschen; deckte den Rueckrichtungs-Fehler auf. [B] LOGBUCH_2026-11-08 Nr. 2; ebenso LOG_MUSTER (muster_fit Fenster Periode 3,9663, Gaube).
- Foto-Messfaire: `kosten_lr` (a contrario Likelihood-Verhaeltnis) statt `kosten_param`: +10 % Zufallskanten senken kosten_param um 0,3-0,57 (belohnt Rauschen), kosten_lr steigt +0,02..+0,05. [B] UEBERGABE_2026-11-04 "Stand 5.11. mittags"; spaeter wegen festem sigma korrigiert (ML-Mischung). [B] "Stand 5.11. 11:20".
- Holdout-Vergleich mit fairem Mass: Generator C -0,0111 < Carving -0,0083 < Ebenen -0,0064 (kleiner = besser, 6 Holdout-Fotos). [B] STAND_2026-11-06 S8-Holdout.
- Zaehlung am Foto mit Protokoll (Z-*.json): Baluster Periode 0,287-0,306 m, 68 Instanzen (Z-6120-001); Fenster 5 Gruppen x 3 Lichter, fotogezaehlt. [B] LOGBUCH_2026-11-09 Runde 11/12, LOG_MUSTER.
- Kanten-Stabilitaet (`kanten_stabil.py`, GPU, 261 Laeufe/Foto = 9 Kanaele x Ton x Sigma x Schwelle, 2 s/Foto): Dachlinie, Giebel, Helme, Gauben, Boegen sauber, Himmel leer. [B] LOGBUCH_2026-11-09 "Kanten-Stabilitaet".
- Tiefen-Sweep mit Basis je Referenz aus Tiefenaufloesung b_min = d^2/(f_px*dz) (dz 0,08, Deckel 25 m): 6120 Median 4,1 cm statt 15,3 cm, < 10 cm 76 % statt 42 %. [B] LOGBUCH_2026-11-09 Runde 5/5b. Feste Basis scheiterte (nur 25 % der Kantenpixel mit eindeutigem Peak).
- SAM (Segment Anything vit-large, Kachelung 620x470 / 35 % Ueberlapp) als Objektfinder: 393-749 Flaechen je Ebene, Nutzer "Das ist ganz genau, was ich will". [B/Nutzerurteil] LOGBUCH_2026-11-09. Mehrfoto-SAM (`sam_mehrfoto_3d.py`, 80 Fotos, 350 s): 280 Objekte, 1,58 von 1,83 Mio. Punkten zugeordnet, ansichtsuebergreifend konsistent. [B]
- Wiederholungs-Prior (Nutzerregel 9.11. 19:20): Periode bestimmen, Belege aller Instanzen auf ein Musterelement, einmal fitten, kopieren, jede Kopie in >= 3 Fotos pruefen. [B Nutzerregel] LOGBUCH_2026-11-09 Runde 5b; `muster_fit.py` Fenster/Gaube Synth bestanden. LOG_MUSTER.
- Offene Laube per generischem Durchsicht-Test statt Sonderregel (Front EG 64 % Oeffnung / 36 % Wand, 5 Pfeiler, 4 Boegen). [B] LOG_KOERPER_V9 Abschnitt v11, LOGBUCH_2026-11-09 Runde 12. Nutzer 5.11. 13:53: "das ist wieder ein Spezialfall - muss generell gefunden werden". [B] UEBERGABE_2026-11-04.
- Lagenbestimmung Gauben/Helm durch Foto-Triangulation (`foto_mass.py --tri`) + Stufe-0-Formbeschreibung: Gauben unten Wolkenbeleg 0,519 -> 0,733 (Median 0,144 -> 0,090 m), 18 neue Pruefungen am Altstand alle ROT, danach 91 bestanden. [B] LOGBUCH_GAUBEN_UNTEN_R3. Helm o: Beleg 0,486 -> 0,607 (Median 0,159 -> 0,088 m). [B] LOGBUCH_HELM_O_R1.
- Erker-Rippen (spaeter Weg 12.11. abends): Lage im EINEN besten Foto (Maske schwarz neutral + Gold, Skelett = Mittellinie) + Projektion auf Modellflaeche; `kante_auf_flaeche.py` an bekannter Rippe Median 2,1 cm, max 3,6 cm; Pfade sitzen auf Rippenmitte, Verschiebung 0,3-24 px (max 5 cm). Abnahme gruen, Commit 1dd8367e. [B] METHODE_MESSEN_DANN_BAUEN, STAND_2026-11-12_VORMITTAG. Aber Ziel "extrem gut in H0 erkennbar" nicht als erreicht erklaert.
- Drei-Kamera-Gegenprobe als Pflicht: Knoten (19,919/7,639/7,971) in 6161 und 6259 bestaetigt, 2-Kamera-Strahlabstand allein beweist nichts bei Pick auf der Epipolarlinie. [B] METHODE_MESSEN_DANN_BAUEN "Verlauf".
- Druckproblem geloest: Ursache der 93-101 Teilnetze waren ~92 Mini-Splitter (1-6 Dreiecke) + 3-cm-Koerper an Rippenkreuzungen, nicht Konsolen. `druck.splitter_verwerfen` (<= 12 Dreiecke oder < 0,1 m). [B] METHODE_MESSEN_DANN_BAUEN "DURCHBRUCH Druck".
- Rundum-Pruefung (`rundum_kanten.py`, 7 Azimute; `ansichten_foto_paare.py`) in `bauen_abnehmen.sh`; Abdeckungskarte: 19 von 24 Bins (Azimut x Hoehe) ohne kalibriertes Foto. [B] METHODE_MESSEN_DANN_BAUEN "Gelernt 13.11.".
- Wolke-Nachbar-Abgleich Koerper v9: Wolkennaehe < 20 cm 49,8 % -> 55,4 %; Band 11-13 m Median 0,23 -> 0,08 m. [B] LOG_KOERPER_V9.
- Frueherer Grundansatz Viadukt (nicht Kaufhaus): Maße (Wikipedia) + OSM-Trasse + DGM1, kein Scan noetig; Stich/Spannweite 0,46 +- 0,05 aus Fotos, R = 9,3 m. [B] METHODE_BAUWERK_AUS_DATEN.
- Abnahme mit rot/gelb-Tor je Element ("Elementbuch") und Uebernahme nur bei lokaler Verbesserung. Tests T0, T1, T2b, T3, T4 bestanden, T2 durchgefallen (Versatz je Foto 0,59/0,94 m unterscheidet nicht). [B] STAND_2026-11-06 S1b.
- Fotodiff-GPU-Fassung, exakt gerasterte Pruefbilder: 2-4x schneller bitgleich; Martinstor-T1 alter Beweis nur per Saat-Glueck (24,8-32,2 %). [B] UEBERGABE_2026-11-04 "Stand 4.11. spaet".

## 2. Was ist gescheitert und warum

- Silhouetten-/Wolkenfit im falschen Rahmen: Bauteilfits, Schleifen (`schleife_ausrichten`, `modell_ausrichten_gpu`) und "Konvergenz" ueber Tage im ~25 Grad gekippten Rahmen. Boden-Fit mit z-Fenster war verzerrt (BS150); Hypothese "7 Grad Gier" per RANSAC widerlegt (BS148). Nutzer: "Warum hast du es nicht gemerkt? Katastrophe." [B] LOGBUCH_2026-11-08 Nr. 10, 23, 24.
- Schrumpf-Falle: Optimierer ohne Gegenrichtung schrumpft das Modell (su 0,65-0,68) -> Grenzen setzen, Fotokanten ohne Modellkante als Gegenterm. [B] LOGBUCH_2026-11-08 Nr. 7, 19; RECHERCHE_2026-11-08_RUNDE2.
- Wolke "Dach zu tief": dichte Wolke liegt auf glatten Ziegeln 1,4 m zu tief; Dach-Restfeld/Freiraum nutzt Wolke nicht (Quellenblindheit). [B] SPEC_S3_KONVERGENZ 0b. (Siehe Abschnitt 6: moeglicherweise Folge des Rahmenkipps.)
- Ebenen-/Carving-Modell aus Wolke (S8): Graph-Cut alpha-abhaengig springend (Kanten p90 274 cm bei alpha 0,1; IoU 0,91/0,49/0,78), Ziel p90 < 10 cm verfehlt; Arkadenzahl haengt an Glaettung sigma (sigma 1,0 -> 3, 0,5 -> 5, 0,75 -> 4). [B] STAND_2026-11-06 S8, carv_kh3.
- BIC-Familienwahl Bogen: waehlt 3 von 4 Boegen flachen Stichbogen; alle 4 Boegen abgelehnt (P90 0,076-1,035 m > 0,06). [B] STAND_2026-11-06 S9.
- Kantenkarten-Pipelines (S10): Schatten-Fehlalarm 0,52-0,99 in fast allen; nur k=4 Stimmen niedrig (0,30) aber Vollstaendigkeit 0,64-0,82; 3D-Kantenfeld Boegen 1 von 4. [B] STAND_2026-11-06 S10 A/B.
- Kantenerkenner-Zoo: Subpixel-Canny -9 % RMS (klein), Phasenkongruenz Praezision 0,06-0,15 (kein Vorteil), DexiNed zusaetzlich Fehllinien, Held-out-Beweis "Foto-Ref besser" NICHT bewiesen (Gewinn gleich). Installation von DeepLSD/ScaleLSD/DexiNed zweimal vom Berechtigungspruefer abgelehnt. [B] LOGBUCH_2026-11-09.
- SAM3D mit Medianwert je Flaeche: "keine Form", nur 287/756 Flaechen mit Tiefe; Nutzer "nur die Objekte oben drauf". [B] LOGBUCH_2026-11-09. Lehre: zu lange im Linien-Paradigma (Canny/LSD/DexiNed) geblieben, Wechsel zu Objekten kam erst durch Nutzerliste. [Selbsteinschaetzung]
- Kantengitter-Filter: Kontrastfilter auf Sweep B getunt entfernt echte Wolkenkanten (Abdeckung -16/-9 Punkte); Streuerfilter score < 0,6 drueckt Dachabdeckung 0,32 -> 0,20. Filter nie an der Menge pruefen, nach der er eingestellt wurde. [B] LOGBUCH_2026-11-09 Runde 3.
- Gitter->Koerper-Route: Nutzer-Urteil "Schrott ... das war viel besser" (= parametrischer Generator mit Formensprache) -> Kurswechsel Hybrid, Gittermasse als Quelle `kantengitter` im Generator. [B/Nutzerurteil] LOGBUCH_2026-11-09 Runde 11.
- Boolesche Koinzidenzen: Erkerkante auf Frontflaeche u.a. -> 32 offene Kanten; `nondegenerate_faces` entfernen macht ein dichtes Netz undicht. [B] LOG_KOERPER_V9 "Pannen".
- Gauben-Triangulation 0/5 (R4) geparkt; Gauben-Kantentest zu unempfindlich (First 1/5, Giebel 3/5). [B] LOGBUCH_2026-11-09 Runde 12, LOG_MUSTER Runde 3.
- Automatische Tiefenfindung fuer Rippen dreifach gescheitert (NCC, Gold 2 Kameras, Gold 3 Kameras: Gipfel schwach, je Punkt andere Tiefe). 0 von 21 Ketten bestehen die Pruefung; `ketten_match` 9/19 bestehen Gegenprobe, aber Abstand zur Flaeche 0,36-1,69 m = physikalisch unplausibel; `pfad_tiefe_dp` nur 3 von 21 Ketten. [B] METHODE_MESSEN_DANN_BAUEN, AUFNAHMEPLAN_ERKER_RIPPEN.
- Zwischenwegpunkt auf der Sehne zieht Pfad weg (D2 0,81 m); automatische Ketten (Versatz 5-15 cm) schlechter als Handvia-Punkte (2 cm); Fragment-Verbinder auf Erker 1 wirkungslos. [B] METHODE_MESSEN_DANN_BAUEN.
- Rauschtor-Nacht 11./12.11.: 54 Runden, 12 leer, 37 verworfen, 5 angenommen (+-0,00-0,01, nicht sichtbar); Erker/Baldachine/Figuren/Gauben nie Ziel (globaler Sperrzaehler zaehlte alte Verwerfungen). Eigener Fehler: `--nur_wahl` vorher nicht angesehen. [B] STAND_2026-11-12_VORMITTAG.
- Foto-F1-Schwelle 0,02 lag unter dem Rauschen (~0,03); in 4 Tagen keine Konvergenz, pixel ~71 %. [B] STAND_2026-11-12_VORMITTAG. Kreis "brachte kaum sichtbaren Gewinn", Regler gedrosselt. [B]
- Sweep ueber Formparameter: `daechlein_h` 0,8 per F1-Sweep gewaehlt (0,407 -> 0,423) -> Saegezacken statt Treppenstufen; Unterschiede < 0,03 nicht unterscheidbar. [B] VORLAGE_BAUTEIL_RUNDE.
- Element-Messregion bei Baldachinen/Erker 0: kein Element messbar (alle R negativ); nur synthetisch bewiesen. [B] STAND_2026-11-12_VORMITTAG Nachtrag.
- Online-Dachbilder (Wikimedia): 3 von 8 registriert, Abdeckung > 15 m 0,20 -> 0,24 (innerhalb Laufrauschen +-0,01-0,02), od_04 Pose um ~600 px falsch trotz 1,27 px Reproj. [B] LOG_ONLINE_DACH. HTTP 429 nach ~11 Bildern. YouTube-Clips ohne brauchbares Dach.
- Messungen von Silhouetten-Parallaxe: Helm-Traufe z 14,22 war ~0,8 m zu hoch, weil Strahl-Ebene-Messung hinter der Spitze (1,4 m) bei Kamera 10 m darunter; Foto 6261 hatte recht. Silhouettenspitzen sind keine Punkte (Strahlabstand 0,3-0,4 m). [B] LOGBUCH_HELM_O_R1.
- Schatten-Gegenprobe gescheitert: gedrehte Sonnen senken die Kosten ebenso. [B] UEBERGABE_2026-11-04 "Stand 5.11. vormittags".
- Stufe 4 CMA-ES verworfen (0,9793 vs Stand 0,9904). [B] UEBERGABE_2026-11-04. Automatik-Bloecke aus Wolke = Hand-Gleichstand, nicht uebernommen. [B]
- CPU-Leistung: 55-W-Limit brachte nichts (Paket nie > 41 W), Abfall nach ~33 s auf 35-38 W, Kuehlung nicht Hauptbegrenzer. [B] CPU_LEISTUNG. Ursache unbewiesen (Firmware/EC) [A].
- Turmfotos n11_01-03 nicht registriert (Kamerahoehe 42-98 m = falsch). [B] STAND_2026-11-12_VORMITTAG.

## 3. Regeln/Tore: wirksam vs. Aufwand

Wirksam (verhinderte nachweislich etwas):
- Pruefstand-Tor bei jeder Uebernahme: stoppte null5e (first_versatz -0,63 -> First/wasserdicht/Koerper rot; Laeufer hatte nie geprueft). [B] UEBERGABE_2026-11-04 12:35.
- Quellen-Blindheit/Beweis ohne Selbstbezug (Exit 2): Zaehlung nur am Foto, `punkte_messen.py` wegen Zirkelschluss gesperrt. [B] REGELN_AUSFUEHRLICH 9; UEBERGABE.
- "Neue Pruefungen muessen am Altstand ROT sein" (Stufe 3 der Vorlage): Gauben 18 rot, Helm 4 rot (1,46/1,46/1,39/1,10). [B] LOGBUCH_GAUBEN_UNTEN_R3, LOGBUCH_HELM_O_R1.
- Sichtfund = erst Pruefung, dann Generator (Regel 2). Pre-Commit-Hook nur Plan, Aktivierung beim Nutzer. [M]
- Plausibilitaetsprobe Kamerahoehe/Nick/Fluchtpunkt (aus dem 25-Grad-Fehler abgeleitet; Einbau als Pipelinepruefung "Folge", Umsetzungsstand nicht belegt). LOGBUCH_2026-11-08 Nr. 24.
- Rauschtor mit Nullkontrollen (0,3 m verschoben/angehoben, 90 Grad): deckte auf, dass Grob-F1 fuer Ornament blind/invertiert ist; nur f1_fein (0,03 m) trennt. [B] STAND_2026-11-12_VORMITTAG.
- Gegenprobe-Kamerakreuz: Rippenmass ueber Fremdfotos, die nicht zum Nachfuehren dienten (6171 0,43 -> 0,71, Fremdfotos unveraendert = nur Selbstbestaetigung). [B] METHODE_MESSEN_DANN_BAUEN Punkt 6.
- Formfunde-Pruefer lehnte Westgiebel +0,033 als "erfunden" ab (diagonales rotes Band); Lehre First laeuft laengs. [B] STAND_2026-11-12_VORMITTAG.
- Platztor (`platz_pruefen.py`, Exit 3): blockierte aber auch jeden Lauf bis Platz da. Nutzer: "Abbruch wegen Platz ist Kacke". Datenplatte lief 5.11. trotzdem voll (Errno 28). [B] STAND_2026-11-06 G1, UEBERGABE, STAND_2026-11-12.

Eher Aufwand / wenig Nutzen (Belege):
- Sperrzaehler MAX_GLOBAL 3 ohne Torversion: blockierte alle gewuenschten Teile (Nachtlauf). Regeln 1-4 danach repariert. [B] STAND_2026-11-12_VORMITTAG.
- Foto-F1 Tor als alleiniges Annahmekriterium bei Ornament (Rauschen > Signal). [B]
- Element-Messregion `--element_region 1`: aufwendig (Baldachine ~25 min, Erker ~60 min GPU), ohne echten Gewinn, bleibt AUS. [B]
- Juror-Ensemble-Ratsche (METHODE_WAHRZEICHEN_AUS_FOTOS) vs. spaetere Messregeln: Juroren oszillieren, LLM-Juror irrte ("rotes Dach", Foto gruen). Nur als Zusatz brauchbar. [M/B]
- Kreis-Regler in der Nacht ohne Wahlprobe (siehe oben).
- Hunderte Recherche-Seiten (RECHERCHE_*) liefern Rangfolgen als "Ingenieur-Empfehlung, nicht belegt"; vieles nie getestet (Abschnitt 7).

## 4. Werkzeuge (tools/*.py)

Zustand nur aus diesen Dateien; "unklar" = nicht belegt.

| Werkzeug | Zweck / wann | Zustand |
|---|---|---|
| `bauen_abnehmen.sh`, `pruefstand.py` | Pflichtabnahme nach jeder Generatoraenderung | laeuft (Kern) |
| `regression.py` | nach tools-Aenderung, 10 Ergebnisdateien gegen Schnappschuss | laeuft |
| `foto_diff.py` (+ `--mehrstufig`, `--raster`, `kosten_lr`) | Modellkanten gegen Fotokanten; faires Mass kosten_lr | laeuft; `--raster` als Standard offen (UEBERGABE) |
| `foto_mass.py --tri`, `foto_zaehlung.py` | Fotomasse / Zaehlprotokolle | laeuft |
| `teil_fotoform.py` (F1, f1_fein) | Foto-F1 je Teil | laeuft; Grobmass ornamentblind |
| `teile_lage_pruefen.py`, `fehlteile_finden.py` | Lage- und Fehlteil-Check nach Bau | laeuft (laut REGELN); "Fehlteil-Pfad baut nichts, 4 Annahmen/56 Runden" STAND_2026-11-12 |
| `kamera_bruecke_pruefen.py` | Kamerakette (SfM->Rahmen) mit Selbsttest | laeuft (UEBERGABE) |
| `lot_aus_fotos.py`, `rahmen_lot_foto.py`, `wolke_lot_ausrichten.py` | Rahmen gegen Kipp | laeuft; Pflicht am Anfang eines neuen Gebaeudes [A: Folgerung] |
| `lod2_winkel_abgleich.py` | Gier aus LoD2 | laeuft (--synth) |
| `teil_sweep_gpu.py`, `sweep_alle.py` | GPU-Positions-Sweep, Plateaubreite je Achse | laeuft; `--synth` Pflicht |
| `schleife_ausrichten.py`, `schleife_teile.py`, `modell_ausrichten_gpu.py` | 8-DoF/Teil-Schleifen | ersetzt/in falschem Rahmen erzeugt; Grenzen noetig |
| `param_suche.py`, `qualitaetsstufen.py`, `nullstart.py` | Parameter-/Stufenlauf | CMA-ES Stufe verworfen; Nullstart laeuft (Pflichtliste) |
| `kanten_stabil.py`, `kanten_tiefe_sweep_flaeche.py`, `kanten_features.py`, `features_in_objekt.py` | Stabilitaetskarten, Tiefenband-Sweep, Linienfeatures | laeuft; Fragmentverbinder wirkungslos; Auto-Einbau ohne Sichtpruefung zurueckgenommen |
| `kanten_ketten.py`, `luecken_rippen.py`, `pfade_nachfuehren.py` | Gold-Skelett, Luecken, Nachfuehren auf Rippenmitte | laeuft (Erker-Rippen) |
| `epilinie.py`, `kante_3d.py`, `kante_auf_flaeche.py`, `pfad_gegenprobe.py` | Handmessung mit Epipolarlinie und 3-Foto-Gegenprobe | laeuft; NCC-Variante nutzlos |
| `pfad_tiefe_dp.py`, `ketten_match.py`, `rippen_abdeckung.py` (Skizze), `rippenbreite_pruefen.py` | automatische Rippentiefe | fehlgeschlagen/Skizze (nur Pruefhilfe) |
| `sam_mehrfoto_3d.py`, SAM-Funktionen im Editor | Objektzerlegung | laeuft; Form nur Beobachtung, kein Bauteil |
| `muster_fit.py`, `kanten_tor.py`, `gitter_wiederholung.py` | Wiederholungs-Prior | laeuft (Fenster); Baluster-Tor offen; `gitter_wiederholung` verfehlt Pfeiler/Gauben/Fensterachsen |
| `gitter_aufbauen.py`, `gitter_naehe.py`, `gitter_statistik.py`, `gitter_streuer.py` | Kantengitter und Messung | gitter_streuer verworfen (Dachabdeckung sinkt) |
| `helm_fit.py`, `helm_profil_wolke.py` | Helmform | laeuft (Helme o/gross: Spitze 22,44, r 0,86) |
| `koerper_fenster_erker.py`, `koerper_v10/v11.py`, `flaeche_oder_oeffnung.py`, `koerper_kette.sh` | Gitter->Koerper-Route | durch Hybrid/Generator ersetzt (Nutzer "Schrott") |
| `baukasten_gen.py` (`rippen_pfade`, `kappe_rueck`, `druck.splitter_verwerfen`) | parametrischer Generator | laeuft (Kern) |
| `zier_ausschnitt.py`, `zier_3d.py` (TripoSR) | Figuren/Zierteile | zier_ausschnitt wiederverwendbar; TripoSR-Figuren vom Tor verworfen (frei vor Fassade) |
| `spitze_hoehe.py`, `giebel_stufen_zaehlen.py` | Spitzen/Giebelstufen | Spitze laeuft (Test); Giebelstufen 7/8/9 unentscheidbar |
| `fassade_ortho.py`, `fassade_parsing.py` (OWLv2) | Ortho/Fassadenparsing | laeuft; Komplett-Ersatz Handablesung verliert (Erker/Traufe fehlen) |
| `freiraum_oeffnungen`, `freiraum_pruefen` | Durchsicht-Test aus Tiefenkarten | laeuft (Gegenprobe bestanden) |
| `rundum_kanten.py`, `ansichten_foto_paare.py`, `abgeschaltete_teile.py` | Rundumprueung, Fotoabdeckung, abgeschaltete Teile | laeuft (13.11.) |
| `foto_feinsuche.py` | automatische Feinform-Fehlstellen | Spec 11.11.; Ergebnis speist Kreis als Cluster, Import in Masstabelle bewusst nicht |
| `kreis_regler.py`, `bauteil_kreis.py` | autonome Runden | gestoppt 12.11. 10:45 (Quota) |
| `fertigung_split.py` | Lasercut-Platten + Druckteile | Martinstor: 30 Platten, 50 s; Grenzen: Platten 0,5 mm hinter Aussenebene |
| `bildwert.py`, `video_frames.py`, `online_dach_registrieren.py` | Bildwert, Videoframes, Webfotos | video_frames in nullstart; Webfotos wenig Nutzen |
| `leistung_testen.sh`, `leistung_diagnose.sh`, `cpu_leistung_installieren.sh`, `hpwmi_pruefen.sh` | CPU-Limit | laeuft, nur diese Hardware |
| `platz_pruefen.py`, `platz_waechter.sh`, `job_start.sh`, `gpu_knn.py` | Betrieb | laeuft |

## 5. Fallen und Nutzer-Rueckmeldungen

Nutzer wiederholt bemaengelt:
- Erfundene Details und uebersehene Details sind beide Fehler; Features nur mit Foto-Beleg; auch Bestehendes hinterfragen. [B] PROTOKOLL_VALIDATOR F5, F9, F10.
- Ueberkorrektur: "X weniger weit" nicht halbieren; nur den einen Parameter drehen (Groesse nicht Form); nie ein Feature loeschen statt eine Eigenschaft zu beheben. [B] PROTOKOLL_VALIDATOR F3, F4, F8, F10.
- Nur Front geprueft ("Whack-a-Mole"): alle Ansichten + alle Fotos + Inventar je Flaeche. [B] PROTOKOLL_VALIDATOR F6; wieder 13.11. "Rundum statt nur Front".
- Spezialfall statt Generelles ("Seitenbogen = Durchgang", "Bogen verschoben"): generische Pruefungen (Freiraum, Feinlage je Element). [B] UEBERGABE_2026-11-04 13:50.
- Handarbeit/Handvarianten/Handschwellen; "alles automatisch loesen". [B] PLAN_2026-11-06 §0.
- Kanten statt Vorlagen: "Fertige bekannte Objekte reinmatchen ist immer bloed, es gibt nie alle Formen." [B Zitat] PLAN_2026-11-06 §7.
- "Du siehst im Bild, dass es zu schmal ist - Loop, nicht Masse suchen." [B] LOGBUCH_2026-11-08 Nr. 17.
- Rippen zu fett: "du musst es selber erkennen" -> `rippenbreite_pruefen.py`. [B] METHODE_MESSEN_DANN_BAUEN.
- Nutzerform ("Achteck", "geschlossenes Gebaeude") gilt als Sollform bis Foto widerspricht; Rueckseiten wurden als "gemessen" gefuehrt, obwohl verdeckt. [B] METHODE_MESSEN_DANN_BAUEN "Gelernt 12./13.11.".
- Ornament nie an der Wolke pruefen; es geht um Strukturgenauigkeit, nicht Druckbarkeit. [B] STAND_2026-11-12_VORMITTAG.
- Prozess muss ohne Nutzer laufen, Nacht nicht verschwenden, nie wegen Platz abbrechen. [B] ebenda.

Fallen/falsche Annahmen:
- Fenster-Detektor kornhaus-ueberfittet (1 statt ~10 Fenster); Oberkirch-Eingabefoto war das Haengeschild; Fensterzaehlung crop-instabil (12 -> 6). [B] PROTOKOLL_VALIDATOR 1-4 (fruehe Phase 29.10.).
- Validator an bekannt-guten Modellen kalibrieren: v1 bewertete gute Modelle schlechter als schlechte. [B] PROTOKOLL_VALIDATOR Lehre 1.
- Laser-GT war nach unten verzerrt (LoD2-Rand schneidet Dachueberstand ab); Farb-/Textur-Scores sind erpressbar. [B/Zitat] METHODE_GEBAEUDE_3D §6/7.
- "rc 0 mit leerem Ergebnis" = stilles Falsch-OK; statischer Test reicht nicht. [B] UEBERGABE_2026-11-04.
- Festwerte in Tools (Martinstor-Pfade in foto_overlay, wolke_vs_modell); Clamp ueberschreibt Messung (`DORMER_H`); verstecktes Hardcode. [B] UEBERGABE, PROTOKOLL F3.
- Blinde Messungen: Grob-Foto-F1 (0,18 m) fuer Ornament blind; `foto_diff` war 4.11. praktisch blind (nur 97 Kantenpixel, "100 % falsch, 0 % fehlt"). [B] UEBERGABE Nr. 7.
- Wolke sieht nur Sichtbares; Wand ist Plateau in u/z. Fensterreihen aus Wolke in u/z unbestimmt. [B] RECHERCHE_2026-11-08_BAUTEIL_LAGE (Befund); Verdeckte Unterseite hat keine Wolke (Median 0,37 im Band z 13,1-14,1). [B] LOGBUCH_HELM.
- LoD2: Fassadenbreite 20,4 m (LoD2) gegen ~26 m (Foto/Wolke); LoD2-First 40-50 px ueber echtem First. [B] LOGBUCH_2026-11-08 Nr. 14, UEBERGABE Nr. 4. Schiedsrichter fuer Breite offen.
- Fotoauswahl nach Abstand waehlt Nahaufnahmen falsch (12-45 m noetig); Fotoauswahl vor Sichtbarkeit begrenzt -> Sohlbank "min 1/median 3". [B] LOGBUCH_2026-11-08 Nr. 4, LOG_MUSTER.
- Handebene +-0,3 m war 0,75 m daneben (Rueckwand 7,29 statt 6,54). [B] LOG_MUSTER Runde 2.
- Mehrdeutigkeit Kameras/Brennweite vs. Breite ist genau der 25-%-Fehler; f-Fehler 2 % = 0,6 m. [B/Memory] RECHERCHE_2026-11-08_RUNDE2.
- Kameraversatz lokal 0,35-1,3 m je Bildzone begrenzt jede Detailmessung. [B] PLAN_2026-11-06 §0.
- Hintergrundjobs/Agenten: "ich warte auf den Monitor" beendet `claude -p`-Runde, 4 Runden am 11.11. leer. [B] VORLAGE_BAUTEIL_RUNDE. Stillstand 5.11. 02:51-08:03 eigene Schuld (Turn beendet). [B] UEBERGABE.
- Wikimedia 429 bei Retry-Sturm; 1 Datei je >= 20 s. [B] LOG_ONLINE_DACH.
- Cache-Dateien aendern sich mit Parametern (hash), nach Codeaenderung loeschen; GPU-Stillstand durch 12-MP-Vollbildmasken (7,5 GB RAM). [B] LOGBUCH_2026-11-09.

## 6. Widersprueche zwischen Dokumenten (Veraltetes markiert)

1. Massstab: `MASSSTAB.md` "VERBINDLICH N 1:160, nicht mehr aendern" (7.10.) gegen alle spaeteren Dokumente (H0 1:87; STL 361x324x299 mm in LOG_KOERPER_V9; PLAN_2026-11-06_H0_DETAIL). MASSSTAB.md ist VERALTET. [B]
2. `QUICK_START_FREIBURG.md` (Prusa MK4S, "diesen Monat fertig", Kachel-Plan) ist ein alter Entwurf, passt nicht zum Stand. [M]
3. Zwei Fassungen: `STAND_2026-11-12_VORMITTAG_lang.md` (Viewer "v55", ohne Nachtraege) ist der aeltere Text; `STAND_2026-11-12_VORMITTAG.md` (v57/v58, Nachtraege bis Rippen/Seitenfenster) ist massgeblich. [B]
4. Linienhafte Features: `REGELN_AUSFUEHRLICH` (12.11.) und CLAUDE.md schreiben Mehrfoto-Sweep + `kanten_features --sweep` vor; `METHODE_MESSEN_DANN_BAUEN` (abends 12.11.) stellt auf "KEINE Tiefenmessung je Rippe, Lage im Foto + Projektion" um, weil der Sweep an parallelen Kanten scheiterte (AUFNAHMEPLAN: 0/21 Ketten). Widerspruch zur Regel; die Regel in CLAUDE.md ist hinter der Praxis zurueck. [B]
5. `METHODE_MESSEN_DANN_BAUEN` Kopf "NOCH NICHT ERPROBT ... Ergebnis nachtragen" gegenueber langem Verlauf darunter (erprobt, teilweise gescheitert). Kopf veraltet. [B]
6. `REGELN_AUSFUEHRLICH` 9d(b) "Status: noch NICHT gebaut" (Fit mit Foto-Kantenabstand) gegen 9e (Foto-F1 entscheidet, `teil_fotoform.py` existiert). Teilweise ueberholt. [B]
7. Dachtiefe: SPEC_S3 0b (Wolke 1,4 m zu tief, Rahmen stimme) und UEBERGABE (First -1,28 m aus Foto gegen LoD2/DOM1, "offener Widerspruch") gegen LOGBUCH_2026-11-08 (Rahmen war 25 Grad gekippt; nach Lot passt der Rahmen) und 9.11. (Dachform halbes Pultdach, First 27,51). Die Dach-Fehldiagnosen vom 5./6.11. sind wahrscheinlich Folge des Kipps. [A: nicht ausdruecklich in den Dokumenten belegt]
8. LoD2-Rolle: "LoD2 ungenauer als Buendelkameras" (UEBERGABE), "LoD2 nur Richtung" (LOGBUCH_08 Nr. 28), "Modellfirst z=20,6 passt zu LoD2 20,97/Wolke 20,3" (LOGBUCH_08 Nr. 16), "Punktwolke einzige Basis, LoD2 nur ohne Widerspruch" (SPEC_S8). Kein konsistenter Satz. [B]
9. Plan 6.11. §7 "Kanten statt Vorlagen/keine Bibliotheks-Fits" gegen spaeteren Generator-Hybrid mit Formfamilien (`baukasten_gen`, VORLAGE: "vorhandene Familie nehmen"). Aufloesung durch Nutzer-Urteil 9.11. ("Schrott ... viel besser"). [B]
10. METHODE_WAHRZEICHEN_AUS_FOTOS (LLM-Juror-Ensemble als Loop bis PASS) gegen REGELN (Zahlen allein gelten nicht, Sollwerte aus Quellen). Juror-Verfahren ist die fruehe Phase (Oktober). [M]
11. VORLAGE: "Leere Wolke ist kein Datenmangel" gegen RECHERCHE_BAUTEIL_LAGE/UEBERGABE "Wolke einzige Basis". Aufloesung: 9e (Fotokanten entscheiden, Wolke Lage-Veto). [B]
12. `METHODE_GEBAEUDE_3D` (Hofgut Sternen) "Laser nDOM Grundwahrheit zum Validieren" gegen REGELN Quellenblindheit (DOM1 sieht keine Bauteile < 3 m, steile Helme Faktor 2). [B]
13. Arkadenzahl: Pruefstand 4/5/6 je nach Verfahren (Carving 3-5, OpenMVS 6, vis 5 "FEHLER"); Sollwert 4 gilt am Foto. [B] STAND_2026-11-06.

## 7. Offene Fragen

- Erker Ost, Gassenseite, "aeusseres Segment fehlt": Ost- oder Westwand? Nutzer fragen. [B] STAND_2026-11-12.
- Seitenwand-Fenster (Gasse) seit 9.11. offen, in Rundumbildern nur als blanke Flaeche. [B] METHODE_MESSEN_DANN_BAUEN.
- Rippen: Netz noch einstraengig (Foto dreistraengig), ~14 Rippen der Front fehlen, Randleiste ~5 cm zu hoch, Soll-Konflikt Wolke gegen Foto; Rippentiefe braucht Nahaufnahmen von unten/seitlich (AUFNAHMEPLAN, 19 von 24 Bins ohne Foto). [B]
- Baluster-Tor (4-px-Schaefte auf 1500-px-Karten), Sohlbank 0/15, Bogen 8/15. [B] LOG_MUSTER.
- Fassadenbreite 20,4 vs ~26 m und Erkerbreite Wolke 2,0 vs Hand 3,3 m: Schiedsrichter fehlt (Massbroschuere ist Bild-PDF ohne Text, structurae 403). [B] LOGBUCH_2026-11-08 Nr. 14; UEBERGABE.
- Giebelstufen 7 (Hand) vs 9 Kappen-Perioden (Automatik); `kosten_lr` trennt 7/8/9 nicht (0,422/0,437/0,430). [B] UEBERGABE.
- Baldachinhoehe zu tief? (Nullkontrolle +0,3 m schlaegt alle 4; NICHT am Foto geprueft). [B] STAND_2026-11-12.
- Gauben: Form offen (Keil/Satteldach, Wolke trennt nicht, 0/5 triangulierbar). [B] LOG_MUSTER, LOGBUCH_2026-11-09.
- Bild-zu-3D fuer Figuren/Drachen/Speier (SPAR3D/Hi3DGen; Hunyuan3D wegen EU-Lizenz ausgeschlossen). [A] STAND/METHODE.
- Nicht getestet, nur recherchiert (alle "Ingenieur-Empfehlung, nicht belegt"): DeepLSD/ScaleLSD/TEED, LIMAP/Line3D++ (Lizenz/Installation offen), CGAL KSR (GPL), Winding-Number-Huelle, PolyGNN, Manhattan/Fluchtpunkt-Zwang, Kostenvolumen-Sweep fuer Gesamtbreite/-hoehe, Himmelsmasken-Visual-Hull fuer Dach, ManifoldPlus (NC). RECHERCHE_* alle. [M]
- Turmregistrierung (n11_01-03), Dachabdeckung > 15 m (Wolke 0,03-0,24, B-Konsens 0,54): Drohnen/Schraegluft empfohlen (RECHERCHE_2026-11-07_WOLKE_ZU_MODELL #5, [M]).
- Shape-Uebernahme bei baugleichen Teilen (Erker 0 hat nur Formelrippen): Liste "Wer hat es schon?" fuehren. [B]
- Zeitprognose "2-3 gute Naechte" fuer Erker/Baldachine/Dach: Schaetzung, keine Zusage. [A] STAND_2026-11-12.
- Lizenzen vor Verkauf: DexiNed (BIPED-Gewichte), CGAL (GPL), PiDiNet/MuGE/RCF (NC), Wikimedia-Bilder je CC; YouTube nur Test. [B] LOGBUCH_2026-11-09, LOG_ONLINE_DACH, RECHERCHE_KANTENERKENNUNG.

## 8. Zeit- und Kostenangaben (belegt, soweit genannt)

- SAM vit-large: 4 s Rechnen, 209 s einmaliges Laden, 3,5 GB VRAM; Ortho fein 103-145 s; Mehrfoto-SAM 80 Fotos 350 s; SAM auf allen ~440 Fotos geplant 20-30 min. LOGBUCH_2026-11-09.
- `kanten_stabil.py` 2 s/Foto; `kanten_3d.py` 930 Linien in 66 s; Dachband-Sweep Jobs mehrere Stunden (Runde 4 17:00-18:10). LOGBUCH_2026-11-09, STAND_2026-11-06.
- Fotodiff Kaufhaus 004 45 s, Martinstor 50 s, param_suche 245 s; Restfeld 7,7 s je STL; fassade_ortho 94 Fotos 40 s. UEBERGABE_2026-11-04.
- Rundumschleife 8.11.: Sweep alle Bauteile zuerst OOM; Schleife konvergiert in 2 Runden. LOGBUCH_2026-11-08.
- Nachtlauf Kreis 00:30-07:45 (7 h 15 min): 54 Runden, 5 angenommen, kein sichtbarer Gewinn. Agentengrenze 60 -> 35 min (`--max_minuten`). Element-Messregion: Baldachine ~25 min, Erker ~60 min GPU einmalig. STAND_2026-11-12.
- Stillstand 5.11. 02:51-08:03 (5 h) durch beendeten Turn. UEBERGABE_2026-11-04.
- Die Erker-Rippen: 12.11. Vormittag bis abends durch mehrere Methodenwechsel (Tiefenmessung -> Maske); Messwerte M-6171-002..005 erster tragender Punkt erst nachmittags. METHODE_MESSEN_DANN_BAUEN.
- Konvergenz ueber Tage: "in 4 Tagen keine Konvergenz (pixel ~71 %)", Ziel > 72 %. STAND_2026-11-12.
- CPU: Dauerleistung 25/31 W Werk, mit Regler 35-45 W (+20 bis +90 % Durchsatz), 55 W bringt nichts. CPU_LEISTUNG.
- Quota ~70 % der Woche am 12.11. verbraucht (Reset 15.11. 9:00). STAND_2026-11-12.
- Druck/Fertigung (Martinstor 1:87): fertigung_split 50 s, 30 Platten, 113 Druckdateien, 234 cm3. Kaufhaus druckteile_auto: 4 Teile, 1,37 kg. FERTIGUNG_SPLIT, UEBERGABE.
- Platz: Root 48 GB / 1,0 GB frei (98 %) am 5.11.; Datenplatte 98 GB / 11 GB frei; RAM 15 GB als Engpass (3,6 GB je Render, 1,35 GB nach Raster). STAND_2026-11-06, UEBERGABE.
- Keine Angaben gefunden zu Gesamtaufwand pro Modell von Null bis fertig; erste Registrierung/Nullstart-Dauern nicht in diesen Dateien belegt.

## Hinweis fuer ein NEUES Gebaeude aus diesen Dateien (Folgerungen, [M] soweit nicht oben belegt)
1. Rahmen/Lot und Kamerahoehe vor jeder Bauteilarbeit pruefen (25-Grad-Fehler kostete Tage).
2. Fotoabdeckung (Azimut x Hoehenwinkel) vor dem Bau messen und Aufnahmen gezielt nachholen (Erker-Unterseite, Dach, Rueckseiten).
3. Stufe 0 (Formbeschreibung aus >= 3 Fotos) und Zaehlen am Foto vor jedem Messen; Form nie per Kennzahl-Sweep waehlen.
4. Erst Pruefung die am Altstand ROT ist, dann Generator; Beweistest mit synthetischer Wahrheit je neues Werkzeug.
5. Wolke nur Lage-Veto; Ornament/Kanten aus Fotos; Details in 1 gutem Foto erkennen, auf bekannte Flaeche projizieren, in Fremdfotos gegenpruefen.
6. Autonome Runden nie ohne `--nur_wahl`-Probe und ohne Fehlalarm-Pruefung der Sperrzaehler starten.

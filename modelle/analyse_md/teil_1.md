# Teil 1: Lehren aus 25 Dokumenten (Stand Dokumente 2026-10-31 bis 2026-11-12, Analyse 2026-11-13)

Gelesen: alle kleinen Dateien vollstaendig (je Zeile gekuerzt auf ~400 Zeichen); VERSUCHSREGISTER_MARTINSTOR.md (348 KB, 1969 Zeilen)
gezielt: Kopf (A-F, G0), I, L2-L4, W, X, Y, AC, AD, AE, AI, AK, AT, AY, BB, BN, BR, BS-Block, BT, BW-BY, CL-CM, CP-CW, Schluss.
Nicht gelesen (nur Ueberschrift gesehen): ca. 70 mittlere Abschnitte (J-K, M, N-V, AF-AH, AJ, AL-AS, AU-AX, AZ-BA, BC-BM, BO-BQ, BS-CK, CX-DL).
Kennzeichnung: [B] belegt (Messung/Foto im Dokument genannt), [A] Annahme, [M] Meinung/Plan ohne Beleg, [1D] steht nur in einem Dokument ohne Gegenbeleg.
Kuerzel: VR = VERSUCHSREGISTER_MARTINSTOR.md, PL = PIPELINE_LERNREGISTER.md, UA/UN = UEBERGABE_2026-11-03_abend/nacht, S9A = STAND_2026-11-09_ABEND.md.

## 1. Was hat funktioniert

### Pipeline Fotos -> Wolke -> Modell
- Nullstart des Martinstor von den Eingaben: 8 min, Volumen 6,27 vs 6,28 dm3 (0,2 %), Pruefstand 61/70 beim ersten Lauf [B] (VR AY). Nach Reparaturen 66/70 bei Lauf 6 (VR BB). Wert: der Nullstart ist der Dauertest, jede Reparatur war generisch und regressionsfrei (VR BB, "sechs Fragilitaeten").
- Buendelausgleich mit amtlichen Daten (LoD2/DOM1/DGM) INNERHALB des Ausgleichs statt 7-Parameter-Transformation danach: synthetisch Martinstor Punktfehler-Median 0,47/0,21/0,22 -> 0,062/0,040/0,041 m [B]; real: Goldkugeln/Tuermchen alt (Picks) vs neu (ohne Picks) alle innerhalb 1 sigma, Differenzen 0,04-0,18 m [B] (PL Abschnitt 2 + 5, `tools/sfm_lod2_buendel.py`).
- EXIF-Brennweite nur als weicher Prior (sigma 5 %), Aequivalenz ueber die DIAGONALE (f_px = f35*Diag/43,27), FocalPlaneXResolution bei Beschnitt bevorzugt (PL Abschnitt 1; Kaufhaus Foto 067: 2333 statt 2733 px) [B].
- Verzerrungstest vor jeder Ausrichtung (`sfm_verzerrung_test.py`): trennt metrische Netze (Nord) von projektiv verbogenen (Sued: Bodenecken 11-13 m daneben) [B] (VR AI, UA). Reprojektionsfehler 0,7 px sagt NICHTS ueber Metrik [B] (VR AI, PL "bessere Rueckprojektion != bessere Geometrie").
- Cheiralitaetspruefung (>20 % Punkte hinter Kamera = Spiegelloesung): 100 % gegen 0,1 % bei normalen Bildern, trennt sauber [B] (VR BB).
- Aufloesungs-Sweet-Spot der dichten Stufe: 1000-1200 px nicht schlechter als 1600 px, in 2 von 3 Netzen deutlich besser, 1,8x schneller (Netz 5: 72/76 vs 55/74 Pruefungen) [B]; Mechanismus ungeklaert [A] (VR BN). Alle Fotos nehmen, nicht Teilmengen: 11-16 Fotos verlieren Tuermchen/Zinnen/Helm (67/80 vs 55/69) [B] (VR BN, BS6).
- Waagerechte Bekanntgroesse fuer den Fotomassstab (N-S-Abstand Tuermchenknaeufe 7,95 m) statt nur senkrechte Hoehen: Gesamthoehe 70 -> 65,3 m, Helm wieder auf der Wolkenfront +-0,2 m [B] (VR AT).
- Video-Frames als zusaetzliche Wolke (Kaufhaus Bodenclip): ICP-Median 0,15 m zur Basis, +49,6 % neue Punkte an Fassade f00 [B]; aber nur 1 von 14 Clips, 24 min je Clip (VR CR).
- Wolke zuerst, Sichtbarkeits-Carving (`wolke_carving.py`): 1 Koerper, wasserdicht, Mindestwand 1,46 mm (1:87), synthetisch Voxel-IoU 0,973 [B] (VR CP). Auf echten Fotos aber nur kosten_lr -0,0095 vs Generator -0,0111 (VR CW) -> brauchbar als Wolke-Veto/Lagepruefung, nicht als Endmodell [B].
- Parametrischer Generator gegen Wolke (CMA-ES, `param_wolke_fit.py`): Dach Median Wolke->Dach 0,27 -> 0,12 m; Gauben aus Wolke 3+2 = Fotozaehlung [B] (STAND_2026-11-08_PARAMETER). Regel dort: "immer erst messen, dann fitten", freier Fit ohne Messstart lief in Rauschen [B].
- Kamera-Feinlage per Foto-Diff: Foto 114 k1fest: kosten_lr -0,0337 -> -0,0967, Versatz 1,18 -> 0,11 m, Holdout bestaetigt Drehung [B] (VR BS3c); aber Uebernahme nur als Vorschlag, k1fest nicht im Holdout geprueft.
- Helm W: Wolkenprofil a(z) mit `helm_profil_wolke.py`, 5 neue Pruefzeilen, 4 von 5 am Altstand rot, danach gruen; Beleg 0,45 -> 0,557, Median 0,18 -> 0,111 m [B] (LOGBUCH_HELM_W). Giebel Ost: Lagefehler u 17,15 -> 15,85 aus 8 Fotomessungen M-6115 [B] (LOGBUCH_GIEBEL_OST).
- Bogenkontur "erst messen, dann benennen": 70 Fotos, Ortho 1 cm/px, Scheitel 4,57 / 4,57 / 4,57 / 4,58 m, Ebenentiefe s = -0,5 +-0,15 deckt sich mit Carving (-0,49) [B]; Kamerafehler 10-35 cm erst durch diese Methode sichtbar (VR BT). Kreisfit aus Wolke: Teilung 4,38/4,35/4,35 m (VR BS15).

### Mess- und Abnahmemechanik
- Masstabelle + generischer Pruefstand, Belegregister `beleg(seite, element, quelle)`, Quelltyp/Massstab je Mass (VR L, L3, L4): erster Fund beim Eintragen der Belege: Inschrifttafel und Doppeladler waren vertauscht (Nord/Sued) [B] (VR L3).
- Plausibilitaets- und Streuungssperre in Messwerkzeugen (`messung_pruefen.py`: Spanne <= 4 sigma UND Std <= 1,5 sigma; `plausibel(wert, von, bis)`): trennte rueckwirkend 2 gueltige von 3 ungueltigen Mehrfoto-Messungen exakt [B] (VR AC, AD).
- Quellen-Blindheit als Pruefstandregel (Laser DOM1 blind fuer steile Helme >75 Grad) und Zaehlen nur am Foto (Exit 2, `test_regeln_cb.py`) [B] (PL Abschnitt 4).
- Farbsuche statt Hough fuer Bauteile (Uhr 26,84 m Foto 030, bestaetigt Modell 26,9 m; nur die schwaechste Kamera 031 weicht ab) [B] (VR X).
- Sichtblatt `audit/seiten.jpg` nach jedem Bau, Seiten ohne Foto als UNGEPRUEFT gemeldet [B] (VR L3).
- Generalitaetsbeweis: zweites Objekt (Schwabentor) ohne Werkzeugcodeaenderung angelegt; 86 % des Codes (1662 von 1937 Zeilen) wiederverwendbar; 3 echte Hardcodings in Werkzeugen gefunden und behoben [B] (VR W, Y). Grenze: nur Rahmen/Pruefstand bewiesen, nicht Fotomessung ohne eigene Anker.
- Bit-Beweis/Regression (`regression.py --pruefen`) nach jeder Werkzeugaenderung: Auffaelligkeiten wie Zwei-Dateien-Kollision wurden so gefunden (VR BB, CL-Abschluss).
- Foto-Diff-Beschleunigung `foto_diff_batch.py`: Ergebnis-JSON bitgleich, 2,1x schneller (Punktmodus) [B] (VR BS8).

### Reihenfolge bewaehrt
- Datenquellen: amtlich (LoD2/DOM1/DGM, DOP20) als Anker, Commons/Mapillary/eigene Handyfotos als Bilder; Video nur mit Flag (Urheberrecht) (VR AY, UA). Commons-Ernte: 6 brauchbare von 130 (VR AI) [B].

## 2. Was ist gescheitert und warum

- Freie Aehnlichkeitsanpassung einer VGGT-Fotowolke ans Modell (Massstab+Neigung+Drehung frei): kollabierte, Massstab an Grenze; "nicht identifizierbar", nicht wiederholen [B] (VR G0, Versuch 1+2). Nur mit Anker (Silhouettenkamera) lief es (s = 48,3 m/Einheit), Grenze ~0,5-1 m; 10 Fotos von derselben Seite brachten keinen Gewinn; Linie fuer Masse "ausgereizt" [B] (G0 V3+V4). VGGT-1B ist CC BY-NC.
- Suednetz Martinstor retten: einseitig + fast eben + unbekannte Brennweiten = projektiv verbogen (unten ~20 % gestaucht); keine Transformation, kein Ankerzwang im Buendel repariert das [B] (VR AI). Auch mit 31 neuen Fotos weiter verbogen (VR BC).
- LightGlue/ALIKED: verbindet Luftbilder, verbiegt aber das Netz (Bodenecke 14,9 m daneben): erzeugt Homographie-konsistente falsche Matches an symmetrischen Fassaden [B]; "SIFT ist vorsichtiger" (VR AK).
- Photogrammetrie-Mesh/Gaussian Splatting als Endmodell: Wettbewerb Kaufhaus kosten_lr: OpenMVS-GraphCut -0,104 (Sieger, nicht wasserdicht), Modell C (Generator) -0,052, Carving -0,027, 3DGS V2 -0,061, 2DGS V3 -0,056 (3DGS Test-PSNR ~14, Ueberanpassung) [B] (VR BR). Martinstor (duenne Wolke): Handmodell -0,075 schlaegt alle Netze [B]. Spaeter: kein stabiler Einzelsieger zwischen d03/Saeule/default, nur mvs_fein verliert sicher (VR BS11, BS17) [B].
- Wolke-zuerst (S3b Restfeld auf Generator, `wolke_solid.py`): T1 synthetisch FAIL, T2 Kaufhaus FAIL [B] (VR CP "FEHLSCHLAG 1").
- Wasserdicht-Reparatur kostet Diff: pymeshfix -0,078 vs -0,104; Faecher-Deckel kostet 0,012 [B] (VR BR, BS20); Loecherschliessen erfindet Flaechen.
- Kanten+Ebenen (S8): synthetisch NICHT bestanden; Kaufhaus eb1 rauh, eb2 zerrissen ohne Arkaden [B] (VR CQ-S8). 3D-Kantenfeld (S10-B): Bogentest 1 von 4; Mehrfoto-Filter auf echten Fotos "fast wirkungslos" [B] (VR CU). Poly-/Ebenenzellen-Nachbau: kein Gewinn [B] (VR BR).
- Arkadenbogen-Einpassung auf Canny/3D-Kanten: Hintergrundkanten, Fit 0,5-1 m daneben, alle 4 Boegen abgelehnt [B]; Synth-Schwellen nach Lauf gesetzt = Tuning-Verdacht (VR CS).
- Kantenkarten (S10-A): Einzelkarten Praezision 0,27-0,57 (Ziegel-/Quaderfugen als Fehlalarm); nur Zusammenfuehren (k=3/Mittel) F1 .71-.82 [B], aber nur 2D-synthetisch (VR CT).
- Wolke filtern (S10-C): Rauschen sinkt nur durch Aussortieren (F1: 62 % Punkte weg, Abdeckung 0,54 -> 0,44); Masken (Himmel/Personen) fast wirkungslos, weil kaum solche Punkte in der Wolke [B] (VR CV).
- Belichtungs-/Kontrast-Sweep (CLAHE, Gamma, Mertens): kein neuer Blickwinkel, Reprojektion/Ankerabstand unveraendert; Union +31..39 % Punkte, aber nur sparse, 16 Bilder, cv2-SIFT [B]; Wirkung auf dichte Wolke NICHT geprueft (VR BS2-Ergebnis).
- Fremdjob-/OOM-verfaelschte Laeufe: Kamera-Ausgleich real_lauf1 (157 Fehlproben), `wettbewerb_kh22_raster` lief gar nicht im Raster (FD_RASTER=0 hartkodiert, ~25 min verloren) [B] (VR BS3d, BS7). Schluss "Kameras sind nicht der Hauptfehler" daraus NICHT belegt (VR BS3d-KORREKTUR).
- Messartefakt Foto 073: "Versatz 1,3 m" war Punktfassung mit nur 70 Modellkanten-Pixeln (Tele, f 14089), mit Raster lr -0,259 [B] (VR BS3e).
- Hohe Hoffnungen auf Tuermchen/Spitze durch Hypsometrie: Laser-Maß war blind fuer duenne Spitzen; "Oberteil bestaetigt" war zu stark [B] (VR I).
- Reprojektionsfehler je Foto (`reproj_je_foto`) blind fuer Lage-/Brennweitenfehler: Foto 044 ~40 px im Foto-Diff, Reproj 0,40 px [B] (VR BS1).
- Dach aus Internetfotos / Dach von oben: Abdeckung Dach ueber 15 m 0,20 -> 0,24 (Rauschen) gescheitert [B] (S9A); Nutzer sollte eigene Fotos vom Muensterturm liefern.
- Foto-Metrik (F1 nach 0,18-m-Glaettung) BLIND fuer Ornament: Erker-Konsole mit/ohne Netzrippen F1 0,574 -> 0,570/0,574 [B] (SPEC_ORNAMENT_FEINMASS); Gesamtnote misst Kantendichte, nicht Form (L46/L47 laut SPEC_LOKALES_FOTOTOR). Balkon-Stirn 0,767 -> 0,764 trotz klar sichtbarem Detail [B] (SPEC_LOKALES_FOTOTOR).
- vis-Index-Fehler: `fused.ply.vis` = Reihenfolge in `images.bin`, NICHT Namensreihenfolge; 14 von 92 Kaufhaus-Bildern falsch, alle alten Carving-/Holdout-Werte (-0,0083) ungueltig [B] (VR CV, CW).
- Handpick durch Netzprojektion ersetzen: Median 5,8 px aber p90 80 px, max 188 px; nur als pruefbarer Vorschlag [B] (VR BB).
- Arbeit am Dach/Rueckseite aus Symmetrie: Symmetrische Rueckseite war FALSCH (Wolke: Dach ist Pultdach/Sheddach, First n 5,9) [B] (STAND_2026-11-08_PARAMETER). Rueckwandebene Kaufhaus laut Wolke 7,29 statt 6,54 m -> alle M-6120-Werte auf falscher Ebene [B] (S9A).
- Silhouettenspitzen sind keine Punkte (L31): Traufe-Apothem aus triangulierter Silhouettenspitze durch Wolke widerlegt (Beleg 0,437 -> 0,374) [B] (LOGBUCH_HELM_W).
- Foto-Teilmengen in der Wolkenstufe, Gaussian Splatting (gs_kh2 V1-V3 "laut Register: schlecht") [1D: TOSHIBA_INVENTAR; Zahlen siehe VR BR].
- DATA_STRATEGY.md (Drohne/Meshroom/Stadt-Email) und METHODE_AUTO_PIPELINE.md (Google 3D Tiles, Street-View-Rip) sind Plaene; Hebel 8 (Umgehung der EU-Sperre) ausdruecklich NICHT gebaut [B] (METHODE_AUTO_PIPELINE). Ob Hebel 1/2 jemals Produktivdaten lieferten, steht nicht in den Dokumenten [offen].

## 3. Regeln/Tore: was wirklich etwas verhindert hat, was nur Aufwand war

Hat verhindert (mit Beleg):
- Belegpflicht `beleg()` mit ANNAHME-Markierung: fing vertauschte Tafel/Adler, "Erfundenes Element" bricht ab [B] (VR L3, W).
- Quellen-Blindheit-Sperre: lehnt Pruefzeile "Turmspitze duenn" mit `laser_dom1` als TABELLE UNZULAESSIG ab [B] (VR W).
- Streuungs- und Plausibilitaetssperre (messung_pruefen): verhinderte falsche Befunde; Luftbildwerkzeug hatte 2711 m2 "Dach" in objekt.json geschrieben, bis `plausibel` eingebaut war [B] (VR AD). Lehre dort: Lehre im Register reichte nicht, kam 4x wieder; erst Code verhindert es (VR AC; PL Kopf "erzwingt").
- Variantenpruefung ("sed-Muster hat nicht gegriffen -> Variante identisch"): fing wirkungslose Varianten [B] (VR W).
- Verzerrungstest, Cheiralitaet, Plausibilitaetsfenster fuer Bandgruppen (`min_verhaeltnis` 1,3): verhinderten Scheingrenze bei 17 statt 23 m [B] (VR BB).
- Holdout-Fotos 001/024/054/083/211/234 + kosten_lr + gepaarter t-Test: lehnten korrekte Teilverbesserungen ab (T2 durchgefallen), aber auch erfundene (T1: Arkade 4 -> 5 FEHLER) [B] (VR CL).
- Foto-Tor (F1-Gewinn pro Runde, Kontrollfotos, Verschiebungskontrolle, Pruefer): hat erfundene Detailformen verworfen (z. B. Tor rund statt spitz a091923 r2; erfundene Facetten Rinne a044705 r4) [B] (SPEC_LOKALES_FOTOTOR) - verwirft aber auch echte kleine Details (Gegenstueck).
- Platztor (15 -> 10 GB), VRAM-Budget `JOB_GPU_MB`, nur ein GPU-Job: stoppte Laeufe statt Platte zu fuellen; Root war mehrfach 96-100 % voll (VR BB, PL Abschnitt 3, UN).
- Nullstart-Ziel nur unter `/media/oem/scan/rc-park_null` (Abbruch bei echtem Ordner auf Root): Reaktion auf PatchMatch 2,3 GB auf Root [B] (PL Abschnitt 3).
- Backup vor Lauf mit Variantennamen: nach LightGlue-Panne (Referenznetz ueberschrieben) [B] (VR AK).
- Testsynthetik mit "NEGATIV"-Gegenprobe (muss fallen): fing Tuning/Testfehler (VR CP, CS, S10-Spec).

Eher Aufwand oder mit Schwaeche:
- Strenges Uebernahmetor CL (a-e): 4 von 5 Tests bestanden, T2 durchgefallen obwohl korrekte 0,6-m-Korrektur: Kameraversatz je Foto (010: 0,59 m, 214: 0,94 m) liess das falsche Modell besser aussehen [B] (VR CL). Tor bevorzugt Kantendichte.
- Gelb/rot-Kantenzaehlung (Fehlerkarte S3): gelb durch Ziegel-/Zierkanten saturiert, Ziel < 0,25 unerreichbar [B] (VR CO-Nachtrag).
- Metrik "rot+gelb" (CM): belohnt kantenreiche verrauschte Netze; Wahrheit selbst gelb 0,358-0,368 [B]; ersetzt durch kosten_lr.
- Foto-Auswahl 66 von 94 darf nur fuer Messschleifen, nicht fuer SfM (VR BS6, BM): kein Foto fuer Abdeckung entbehrlich [B].
- Mikro-Zeitoptimierung: Fotokanten-Cache lohnt nicht (cProfile, VR BS8) [B] -> Aufwand gespart, weil vorher gemessen.
- Stufenschleife "Bilder nur in Stufen holen" (`bilder_schleife.py`): Entwurf ungetestet (UA); Gewinn nicht belegt [1D].
- Handlungsregel "alles vollautomatisch, jede Handaktion als M-Zeile" (UA harte Regel 1): fuehrte zu Inventar (VR BB: 59 Masse, 20 automatisch; 186 von 207 Beobachtungen automatisch, "ertrinken die 21 echten") - Beobachtungs-Hygiene noetig [B]. Nutzen vs. Aufwand nicht quantifiziert [M].

## 4. Werkzeuge (tools/*.py): Zweck, Einsatz, Zustand
Zustand = nur "Datei existiert" (ls am 2026-11-13) bzw. Aussage im Dokument; Lauf nicht geprueft.
- `nullstart.py`: kompletter Neustart eines Objekts; Dauertest; `--stufe grob/voll/auto` [existiert]. `objekt_anlegen.py` + `treppe.py`: neues Objekt in Minuten [existiert; treppe.py nicht geprueft].
- SfM: `sfm_netz.py` (Netz je Seite, Reparaturschleife), `sfm_lod2_buendel.py` (Buendel mit LoD2-Prior, empfohlen), `sfm_verzerrung_test.py` (Pflicht vor Ausrichtung), `sfm_ausrichten.py`, `exif_brennweite.py`, `sweetspot.py` [alle existieren]. `sfm_bundle_anker.py` ersetzt durch Buendel [VR AI: Ankerkosten blieben 215 vs 208 -> kein Hebel].
- Messen/Pruefen: `pruefstand.py`, `messung_pruefen.py`, `foto_mass.py`, `foto_diff.py` (kosten_lr, Raster; Punktmodus degeneriert bei Tele), `foto_diff_batch.py`, `fehlteile_finden.py`, `seiten_audit.py`, `regression.py`, `teil_fotoform.py`, `kanten_nulltest.py` [existieren].
- Wolke: `wolke_carving.py` (Lage-Veto/Koerper), `wolke_filter_varianten.py`, `wolke_kennzahlen*.py`, `wolke_front.py` (Frontansicht Orthokamera; zeigt 4 Boegen scharf, VR BS11) [existieren/teils]. `wolke_solid.py` [existiert, Ansatz gescheitert, Altlast].
- Kanten: `kanten_3d.py`, `ebenen_modell.py`, `kanten_feld3d.py`, `kanten_pipelines.py` [existieren; Ergebnis Kaufhaus negativ/schwach, Stand 6.11.; CLAUDE.md verlangt jetzt Sweep-Variante `kanten_tiefe_sweep_flaeche.py`/`kanten_features.py` -> Nachfolger, vgl. Abschnitt 6].
- Bauteile: `baukasten_gen.py` (Formfamilien: helm_geschweift, gaubenreihe, figurenreihe, ...), `bauwerk_generator.py` (Basisklasse nach METHODE_GEBAEUDEGENERATOR; ob je produktiv, unklar), `param_wolke_fit.py` (CMA-ES), `helm_profil_wolke.py`, `bogen_kontur.py`, `element_einpassen.py`, `bauteil_kreis.py` (Kreis-Tor, enthaelt jetzt Rauschtor und ORN_WORTE), `teil_render_foto.py`, `muster_fit.py`, `kanten_tor.py`, `teile_sichtpruefung.py` [alle existieren].
- Kamera: `kamera_feinlage.py`, `kamera_ausgleich.py` (nur 114 uebernehmen wollen, OOM-Probleme), `reproj_je_foto.py` [existieren; Ergebnisse nur Vorschlag].
- Bilder/Lizenz: `bilder_holen.py`, `bildwert.py` (Bedarf Kaufhaus: alle 94 Kameras im Norden; Sued Bedarf 397,6 m2, VR CQ), `lizenz_register.py`, `textur_projektion.py`, `commons_harvest.py` [existieren bzw. bei commons_harvest nicht geprueft].
- Altlast/Plan: `streetview_rip.py`, `auto_bauwerk.py`, `foto_displacement.py`, `foto_georef_overlay.py`, `foto_skyline_orient.py` (Fotos fuer Viadukt/Staumauer-Linie) [existieren; METHODE_FOTO_AUFNAHME bezieht sich auf andere Objekte, nicht Kaufhaus/Martinstor].
- `test_lokales_fototor.py` und `teil_render_foto.py` existieren; in `teil_fotoform.py` fehlt aber die in der Spec geforderte Option `--aenderung_von` (grep 0 Treffer), `f1_fein` kommt dort 4x vor -> Spec Lokal teils umgesetzt oder ersetzt durch Rauschtor (bauteil_kreis.py Zeile 25) [offen, siehe 7].
- GPU-Regel: eine GPU, Aufgaben mit `JOB_GPU_MB` und `job_start.sh`; PatchMatch+Torch gleichzeitig stuerzen ab (UA Fallen) [B].

## 5. Fallen und Nutzer-Rueckmeldungen

Wiederholte Nutzerbemaengelungen (aus den Dokumenten, nicht alle belegt):
- "Perfektes 3D-Modell" zuerst, vor Druck (UN) [B Zitat]. Kein Probedruck/Slicen ohne ausdrueckliches Wort (S9A).
- Alles vollautomatisch, keine Handaktionen; Bilder nur in Stufen und nur mit Mehrwert; jedes Bild mit Lizenzklasse (UA/UN, harte Regeln).
- Sichtfunde des Nutzers waren mehrfach richtig, Modell/Pruefstand falsch: "Tuermchen zu gedrungen, Mittelspitze stimmt nicht" (VR I, Ursache: Laser-Messblindheit); "Helm passt nicht, Tuermchen nicht auf Punktmodell" (VR AT: Nadel 5 m zu hoch); Kaufhaus Erker, Erkerhelme, EG-Tor, Westumriss (S9A) [B].
- "Beweise es!" - Forderungen nach Beweis fuehrten zu den Beweiswerkzeugen (Nullstart, Generalitaet, Blindtest Teile-Sichtpruefung) (VR W, AC, AY, S9A).
- Modell zeigen als Bild/3D-HTML, nicht Zahlen (S9A, STAND_2026-11-08: "Nutzer will parametrisches Modell sehen", Artifact mit hlo-Netz veraltet/unerwuenscht).
- Entscheid 11.11.: "Lokal + ganzes Teil" fuer das Foto-Tor; "Feinmessungen muessen eigenes Teil werden, voll automatisiert" (SPEC_LOKALES_FOTOTOR, SPEC_ORNAMENT_FEINMASS).
- Nutzer 8.11.: KEINE Netz-/Foto-Diff-Jagd mehr (hlo "geschmolzenes Wachs"); vorgebautes parametrisches Modell gegen Wolke einpassen (STAND_2026-11-08_PARAMETER).
- Nutzer 5.11.: "Buendelwolke ist das Beste, wir muessen nur solid draus machen" (SPEC_S3b) - wurde per Test widerlegt: Wolke Dach 1,4 m zu tief, 49 % Dachloecher, Ballon-Volumen 2306 statt 7859 cm3 [B].

Annahmen, die sich als falsch erwiesen (alle [B]):
- "Uhr/Zinnen/Fenster fehlen" -> existierten schon; zurueckgezogen (UA/UN, VR Strang B).
- Symmetrische Rueckseite / Ost-West aus Symmetrie -> falsch (Pultdach, STAND_2026-11-08), bei Martinstor weiter Annahme (UN).
- OPENCV vs SIMPLE_RADIAL "0,88 -> 0,28" mit gleichem Schaetzer nicht bestaetigt (0,37 vs 0,39), nicht mehr als Beleg (UA, UN).
- "Laser DOM1 = Wahrheit": Dachreiter-Kegel Fussradius 1,5 m war Rasterartefakt (VR I).
- Gleiche Serie = gleiche Brennweite: falsch, Zoomobjektiv (030: 1839 vs 2300 px) (VR AI).
- Gespeicherte COLMAP-Fehler `points3D.error` veraltet (0,85 gespeichert, 2,63 px echt) (PL Abschnitt 1).
- Subagentenberichte sind Modellausgabe: eigene Behauptung "Uhr/Zinnen fehlen" durch Strang-B-Befund widerlegt (UA Fallen).
- Zaehlung/Form: Rueckwandebene, EG-Fenster eg0/eg2 ANNAHME, Gaubenform (S9A offen).

Technische Fallen:
- Dateiname ueberschrieben (`abdeckung.py` -> `abdeckung_quellen.py`), `fassade.json` nie per json.dump neu schreiben (formatiert um), nur Textersetzung (UA, UN).
- Zwei parallele Optimierer mit gleicher Datei -> Lauf 1 != Lauf 2 (VR C).
- `regression.py` nur mit venv-seg-Python; `audit/video_ausrichtung.json` gehoert zum letzten Video; `pkill -f` trifft eigene Shell; Foreground-sleep gesperrt (UA/UN).
- PatchMatch bricht ab bei altem dichten Arbeitsordner (1-2 px andere Entzerrung); Core-Dumps 1,3 GB landen auf Root (RLIMIT_CORE=0 gesetzt) (VR BB).
- Panorama NIE fuers Overlay stitchen; GPS-Hoehe unzuverlaessig (Geoid ~48 m +-10-30 m); Handy-Kompass 15-25 Grad daneben; 15-40 Fotos, 60-80 % Ueberlappung, Parallaxe (METHODE_FOTO_AUFNAHME) [1D, allgemeine Praxis, kein Messbeleg].
- Plattenpfade: zwei Toshiba-Platten gleicher Mountpunkt; Symlinks zu Platte A seit B tot; `auslagern.sh` erwartet relativen Zielpfad (TOSHIBA_INVENTAR) [B].
- Nutzernachrichten oft abgeschnitten: nicht raten (UA, UN).

## 6. Widersprueche und veraltete Stellen
- VR Kopf "Stand 2026-10-31" und Abschnitt A "Quelle gibt es nicht offen" etc. sind Stand Martinstor 10/31; spaetere Abschnitte (BQ-BT) aendern Quellenlage (Video, Drohne) -> Abschnitt A veraltet bei Video/Drohne.
- VR G ("Noch nicht versucht") steht nach AE-BU weitgehend erledigt; nicht aktualisiert [1D].
- VR J4: "Gesamthoehe 60 m uebernommen" -> spaeter AT: 65,3 m; UN: "Nadelspitze unsicher (60-67 m)". Aeltere Hoehen (54,80 m, 60, 70, 65,3) stehen nebeneinander; gueltig ist 65,3 m (VR AT) [B], Nadelspitze weiter unsicher.
- VR CP/CM nennen "Carving korrigiert -0,0095" und "alte -0,0083 ungueltig" (CW); RECHERCHE_2026-11-06 nennt beide Werte; nur der korrigierte gilt.
- Zwei Abschnitte mit gleichem Kuerzel: "CQ - Bildwert" und "CQ - S8 Kanten", "CO"/"CO-Nachtrag", "BS/BS2/BS3" mehrfach, "BT" doppelt (Bogenkontur und Median-Konsens), "BR" dreifach (Drohne einpassen, Wolke->Netz). Verweise "Register CQ/BR/BT" sind mehrdeutig [B Struktur].
- VR L2/Tabelle zu `fassade.json`: "Suedwand-Schlitzfenster 0,77 m" (UA) vs "0,75 m ... M-041-006" (UN) -> 0,75 gemessen, 0,77 eingebaut; "rechtes Fenster nicht gegengemessen" in beiden [B Widerspruch klein].
- UA "dicke Bodenwolke 12:00-12:30 Ende" vs UN gleiche Schaetzung; beide Uebergaben vom 3.11. sind veraltet (Stand 9.11. und 12.11. spaeter).
- S9A nennt STAND vom 9.11.; CLAUDE.md nennt als aktuell STAND_2026-11-12_VORMITTAG. S9A "Kantengitter v12 5252 Kanten" vs. CLAUDE.md Linienpipeline (Mehrfoto-Sweep): neuer Weg, Gitter-Weg nicht mehr massgeblich [B Verweis].
- SPEC_LOKALES_FOTOTOR: "wird ERST umgesetzt, nachdem Tempo-Agent teil_fotoform fertig hat" vs Code: `--aenderung_von` nicht auffindbar, dafuer Rauschtor (12.11.) [offen].
- METHODE_GEBAEUDEGENERATOR: Ziel `tools/bauwerk_generator.py` fuer "Kaufhaus + Wentzingerhaus" - Datei existiert; aktuell wird aber `baukasten_gen.py` + `modelle/kaufhaus_grob3/objekt.json` benutzt (STAND_2026-11-08, S9A). Unklar, ob bauwerk_generator.py noch gepflegt [offen].
- METHODE_AUTO_PIPELINE: Hebel 2 (Street-View-Rip), Hebel 8 (Umgehung) widersprechen dem Projektprinzip "keine Umgehung/kein Street-View-Scraping" (UA harte Regel 3) -> Hebel 2 faktisch nicht zulaessig [B Regeltext].
- DATA_STRATEGY.md: DJI Mini 2 Kauf/Meshroom/Wartezeit Stadt - spaeter existieren LoD2/DOM1 vom LGL und Handy/Commons/Mapillary; Drohnenkauf-Empfehlung nie umgesetzt (Drohnenvideo kam trotzdem vor, VR BQ) [M]. Dokument ist reine Zielstellung, ohne Messung.
- RECHERCHE_2026-11-06: empfiehlt zweistufigen GS-Test (PGSR/2DGS -> gsplat); VR BR/TOSHIBA belegt, dass GS V1-V3 bereits liefen und "schlecht" waren -> Empfehlung teilweise ueberholt [B VR BR].
- MASTERPLAN/SWEET_SPOTS: Druck "Ein Bauraum = ein Print, kein Segmentieren" vs `tools/druck_teilung.py`/8 H0-Teile (S9A) und UA "Bauhoehe ~220-250 mm -> 4 Segmente" -> verschiedene Objekte (Monument vs. Kaufhaus), kein echter Widerspruch.
- ERKLAERUNG_FOTO_ZU_PUNKTWOLKE: Stand 8.11. "130/134 Bilder in 3 Teilmodellen, PatchMatch 86/206" - Momentaufnahme; Kaufhaus alle 458 Bilder (iPhone 134, Android 301, Nutzer 23) vs VR "94 Fotos null5" - verschiedene Datensaetze.

## 7. Offene Fragen
- Echte Ost/West-Seiten und Rueckseiten: weder Martinstor (Haeuser 3-7 m daneben) noch Kaufhaus (alle Kameras im Norden, Bedarf Sued 397,6 m2) haben Fotos [B]; Dach ueber 15 m nur 0,20-0,24 Abdeckung (S9A). Hebel: Fotos von erhoehten Standorten (Muensterturm, Fenster, Parkhaus; PLAN_DETAILGETREUE Schritt 2) - Nutzer-Foto ausstehend.
- Mechanismus hinter Sweet Spot 1000-1200 px (VR BN) und Objektabhaengigkeit.
- Wirkung der Belichtungsvarianten auf die DICHTE Wolke (VR BS2) und mit LightGlue/ALIKED.
- Ob ein lokales Foto-Tor/f1_fein den Kreis wirklich verbessert (Beweis 1-3 aus SPEC_ORNAMENT_FEINMASS/SPEC_LOKALES_FOTOTOR; Rueckblick-Test an 45 verworfenen Runden); Code-Stand pruefen.
- Kamera-Ausgleich: nur 114 validiert; fuer 12 von 13 Fotos Ergebnis nicht gemeinsam > RAUSCH 0,008; Wiederholung ohne OOM offen (VR BS3d).
- Fenster-Pipeline (RECHERCHE_2026-11-07): CMA-ES + Chamfer-Kantendiff, Typfenster-Median, Holdout 1/3: Plan, Beweis-Test (synthetisches Fenster auf <1 cm) nicht in diesen Dokumenten belegt [M].
- 3D-Kanten/Linien als Features statt Gitter: CLAUDE.md nennt Sweep-Weg; ob dies die S8/S10-Schwaechen beseitigt, steht nicht in diesen Dokumenten.
- Lizenzfolgen ShareAlike/NC fuer Texturen und Produktfreigabe (`--produkt` faerbt 0 %; 281 Bilder: frei 28, Namensnennung 57, ShareAlike 144, nc 39, unfrei 11, unklar 2) [B UA]; rechtliche Wirkung UNVERIFIZIERT.
- Generik: ob ein NEUES Gebaeude ohne Handpicks und ohne Generatorcode (Typ unbekannt) durchlaeuft; Schwabentor nur Rahmen bewiesen; "offen: Generator ist Martinstor-spezifisch" (UA).
- Druckverfahren/Drucker/Mindestwand (FDM 0,4/0,25, Stab statt Nadel): Entscheid des Nutzers ausstehend (UA/UN); Duesenpruefung 0,4 mm: 108/113 Teile zu duenn [B VR E].
- Fremde Gegenprobe LIMAP/EdgeGaussians: Download blockiert, braucht Freigabe (S9A).
- Wentzingerhaus/Nachbar mit BauwerkConfig: nie als gelaufen belegt [offen].
- Detailabdeckung >= 7 cm am Original (0,8 mm H0): `detailbudget.py` geplant (PLAN_DETAILGETREUE); Existenz nicht geprueft [offen].

## 8. Zeit-/Kostenangaben (nur was genannt wird)
- Nullstart Martinstor komplett: 8 min (Netz Nord 7 s, Netz Sued 8 s, Ausrichtung Nord 8 s / Sued 51 s, Dichtwolke 353 s) [B] (VR AY); spaeter Dichtwolke 567 s (Nullstart 6) [B].
- SfM 37 Turmfotos: 10 s, 36 von 37 registriert [B] (VR AE). Sweet-Spot: PatchMatch 304/472/673 s bei 800/1200/1600 px (Netz 3); 369 vs ~650 s (Netz 4) [B] (VR BN).
- Handyfoto-Registrierung Kaufhaus: neu x neu 24309 Paare 7,3 min [B] (VR CX). Voller Match 458 Bilder = ca. 105 000 Paare (ERKLAERUNG).
- Carving Kaufhaus 391 s (90 s mit Zwischenspeicher), Martinstor 226 s; carv_kh4_vis je 3-4 min [B] (VR CP, CW).
- Video-Stufe Kaufhaus: 100 Frames/1 Clip 24 min (video_sfm 651 s, PatchMatch+Fusion 716 s) [B] (VR CR). Dichte Bodenwolke Martinstor: 350 Bilder, ca. 2 h geschaetzt, gestartet 10:32 [B UN].
- S10 Kantenkarten: 94 Fotos x 4 = 376 PNG, Job 297 s (P4 7,5 s/Foto nach GPU-Umschreibung, vorher 91 s) [B] (VR CT). Kantenfeld 20 s GPU + RANSAC 6 min [B] (VR CU). `kanten_3d.py` 930 Linien in 66 s [B] (VR CQ-S8).
- Kamera-Ausgleich real: 2718 Proben, 3552 s [B]; foto_diff 21 s/Foto (Last 13-30) vs Batch 13,4 s/Foto [B] (VR BS3d, BS8). 25 min durch Fehllauf verloren (BS7).
- VGGT-Fototest: 10-15 s je Lauf auf GPU [B] (VR G0).
- Plan-Schaetzungen: GS-Training 20-40 min (gsplat) bis 1-2 h (MILo) [A, RECHERCHE_2026-11-06]; 8+ Sitzungen fuer 7-cm-Detail "ohne Gewaehr" [A] (PLAN_DETAILGETREUE); Stadtdaten 1-2 Wochen, Drohnenroute ~4 Tage, 400 EUR [M] (DATA_STRATEGY).
- Hardware: RTX 4060 Laptop 8 GB VRAM, 28 Kerne, 15,7 GB RAM; Platte /media/oem/scan ~14-16 GB frei, Root 96-100 % (UN, VR BB) [B]. Lizenz LGL-Rohpunktwolke ALS_3 ab 60 EUR + USt (nicht bestellt) (VR A).
- Kreisrunde (Agent) je Teil: Beispiel Helm W Beleg-Mittel +0,065 in einer Runde (Gate >= 0,05) (LOGBUCH_HELM_W); Dauer der Runden steht in diesen Dokumenten nicht.

## Uebertragbare Lehren fuer ein NEUES Gebaeude (aus diesen Dateien)
1. Zuerst Fotos mit Parallaxe, mehrere Seiten UND erhoehte Standorte; ohne Gegenseite wird das Netz verbogen oder die Rueckseite erfunden (VR AI, BQ, CQ-Bildwert).
2. Buendelausgleich mit LoD2/DOM1/DGM innen, EXIF nur als Prior, vor jeder Weiterverwendung Verzerrungstest + Cheiralitaet; Reprojektionsfehler ist kein Beleg (VR AI, BB, PL).
3. Mess-Tor vor Form: jedes Mass mit Quelle/Quelltyp, Plausibilitaets- und Streuungssperre im Werkzeug, Quellen-Blindheit (Laser/Wolke) beachten (VR AC, AD, L3).
4. Zaehlungen nur am Foto; Wolke nur Lage-Veto/Tiefenfeld; Silhouettenspitzen nicht triangulieren (PL, LOGBUCH_HELM_W).
5. Parametrisches Modell (Formfamilien) + Wolkenprofil messen, DANN fitten; Mesh/GS/Carving aus Wolke ersetzt das nicht (VR BR, CP, STAND_2026-11-08).
6. Metrik muss die Form sehen: F1 nach Glaettung ist blind fuer Ornament/Kleinteile; Kantenmetrik rot+gelb saturiert; Holdout + gepaarter Test + Rauschband statt Einzelwert (VR CL, CM, SPEC_ORNAMENT_FEINMASS).
7. Jede Lehre in Code erzwingen, nicht nur ins Register (4x Wiederholung trotz Eintrag, VR AC; PL Kopf).
8. Betriebsdisziplin: eine GPU, VRAM-Budget, Root-Platte schuetzen, Referenznetz nie ueberschreiben (Variantennamen), Messwerkzeuge auf gleichen Schaetzer/gleiche Kamera (UA/UN Fallen, VR AK, BS7).

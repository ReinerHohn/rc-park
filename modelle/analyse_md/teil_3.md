# Teil 3: Lehren aus 39 Markdown-Dateien (Liste _liste_3.txt)

Legende: [B] belegt (Messung/Foto/Lauf im Dokument), [A] Annahme (im Dokument so benannt oder erkennbar), [M] Meinung/Empfehlung/ohne Beleg. Beleg = Dateiname (alle unter modelle/). Gelesen: alle kleinen Dateien ganz; REZEPT_GEBAEUDE_AUS_FOTOS (72 KB), LOG_GITTER_GENERATOR (45 KB), BEWEIS_ANSATZ (38 KB), LOG_FORMEN (30 KB), LAGEBILD_KANTENGITTER (27 KB), LIZENZ_WERKZEUGE (21 KB), PLAN_VERBESSERUNG (17 KB) und die Recherchen nur gezielt (Kopf, Ergebnis, Lehren, Stichproben).
Zeitraum der Dateien: 31.10. (Martinstor-Massprüfung) bis 11.11.2026 (Specs Formnote/Grauzone).

## 1. Was hat funktioniert

### 1.1 Rahmen und Kameras (Voraussetzung für alles)
- [B] Lot aus Fotovertikalen (Fluchtpunkt aus 36-54 Fotos, Streuung 0,6 Grad) entdeckte, dass der Wolken-/Kamerarahmen ~25 Grad gekippt war; nach `tools/rahmen_lot_foto.py` Kamerahöhe 1,5/2,0/2,3 m statt 4-6 m, Lotabweichung 0,06 Grad. Alle früheren Sweeps/Overlays im alten Rahmen waren ungültig. Entdeckt hat es der Nutzer am Overlay ("Perspektive wirkt falsch"). (STAND_2026-11-08_LOT_SWEEP_LOOP, LEHREN_2026-11-08_SWEEP_UND_FOTOLOOP)
- [B] Kamera-Rahmenversatz: fehlendes `rahmen_verschiebung` in K-Protokollen verschob das Modell um -zmin = 1,453 m; Fix brachte foto_diff 6120 von 0,118/0,318 auf 0,038/0,214 (LOG_GITTER_GENERATOR Runde 5, Lehre L11 in REZEPT).
- [B] Rahmenbeweis vor Übernahme von Gittermaßen in den Generator: Frontebene Gitter 12,66 = Generator 12,666; Winkel 0,06 Grad; zusätzlich Bildbeweis Modell rot + Gitter gelb auf demselben Foto (LOG_GITTER_GENERATOR §1).
- [B] Kamerabewertung nur modellfrei per Leave-one-out (Punkte ohne das geprüfte Foto neu triangulieren, Fehler in Metern) (REZEPT L-KG1). SfM-interne mm-Fehler beweisen nicht die absolute Lage (L-KG4).

### 1.2 Kanten und Gitter
- [B] Kanten-Stabilitätskarte (Sweep über 29 Varianten x 3 Maßstäbe x 3 Schwellen = 261 Läufe, ~2 s/Foto GPU): echte Kanten bleiben, Rauschen fällt weg; zeigte Dachfirst, Giebel, Helme, die vorher keiner fand. Problem lag in den Einzelquellen, nicht in der Kantenerkennung. (METHODIK_KANTEN_STABILITAET)
- [B] Tiefen-Sweep auf Stabilitätskarten: 5 s je Referenzfoto, 80 Referenzfotos -> 631 022 Punkte; Voxel-Konsens zeigt Dach (First z~27 m, Traufe 14,5 m), das der alte Suchkasten (Wolkenperzentil + 8 m) abschnitt. (METHODIK_KANTEN_STABILITAET)
- [B] Gitter v7 (3041 Kanten): Abdeckung unabhängiger Wolkenkanten <12 m 0,90, 12-15 m 0,82; Dach vs Sweep B 0,69 (PLAN_KANTENGITTER_H0_2026-11-09 §0). Aber: Referenzen sind teils zirkulär (siehe 5.4).
- [B] Nur die VEREINIGUNG über Läufe wächst (`gitter_zurueck.py`), jeder Filter braucht eine zweite, andersartige Referenz (PLAN_KANTENGITTER_H0 §0, bestätigt durch verworfene Filter in LAGEBILD Zeilen 44/46).

### 1.3 Messen am Foto
- [B] Bewährter Messweg je Element: Ebene aus Gitter/Wolke -> Anzahl am Foto zählen (`foto_zaehlung.py`) -> Kanten mit `foto_mass.py --kamera ... --ebene` (Pixel -> Sehstrahl -> Schnitt mit Ebene, +-0,06 m) -> Generator-Bauteil mit Beleg, Prüfung vorher ROT -> Overlay + Fehlerliste. Nutzer: "gigantischer Schritt" (REZEPT §Bewährter Messweg).
- [B] Zwei-Kamera-Triangulation `foto_mass.py --tri`: Strahlabstand <= 0,03 m beweist Zuordnung; Schnittwinkel >= 20 Grad (L32), besser >= 45 Grad (L-KR19: Paare 30 und 63 Grad widersprachen sich um 0,16 m, 63-Grad-Paar passte zur Wolke). Dritte, nahe frontale Aufnahme entscheidet bei Fotowiderspruch (L19, Bogenscheitel 7,11/7,31 -> 6119 7,13).
- [B] `--tri2d` (Peilung senkrechter Kanten, Pickhöhe egal) lieferte Erker-Grundriss: regelmäßiges Achteck, Seite 1,28 m, Apothem 1,55 m (LOG_GITTER_GENERATOR Runde 7). Nutzer sah vorher "Erker war Kasten, nicht in Zahlen" (L26).
- [B] Wolke als Profil lesen: Median je dünner Scheibe an der Scheibenmitte statt p98 am Anfang (L-KR21, Fehler 0,17 m bei Steigung 2 m/m); Rotationsbauteile als r(z)-Diagramm (L-KR15); Helm-Profil +0,04-0,06 m: Helm W Beleg-Mittel 0,459 -> 0,588 (LOGBUCH_HELM_W_R4).
- [B] Fenster OG: Beleg 0,67 -> 0,979, Recall 0,792 -> 0,840, Präzision 0,491 -> 0,683 durch gemessene Breite 2,72 statt 3,33 m, Glas in der Laibung; 7 neue Prüfungen am Altstand alle ROT, danach grün (LOGBUCH_FENSTER_OG_R1). Der alte Beleg 0,67 war aufgebläht (überbreite Rahmen lagen auf Wandpunkten).
- [B] Baluster: Periode und Phase aus dem Zählprotokoll (Pixelstrahlen auf Brüstungsebene), nicht aus Wolke oder Fotosignal: 68 Instanzen, Periode 0,3062 m, Score 28/28 (LOG_FORMEN Runde 3). Fotosignal hatte 6 % zu eng (0,2869) geliefert.
- [B] Fuß-/Kappenlage gegen Gegenstück übertragen (L-H7): Fehler am einen Helm per Wolke-Mittenprofil a(z) finden, Korrektur zuerst am anderen anwenden.

### 1.4 Regeln, die sich bewährt haben
- [B] Bildfeedback zuerst: Wolke gelb + Modellkanten rot auf kalibriertem Foto (`modell_foto_overlay.py`) zeigte in 5 Min, was Zahlen in Stunden nicht zeigten (LEHREN_2026-11-08). Mit Z-Puffer (Runde 5): "Ziegelteppich" verschwand (LOG_GITTER_GENERATOR).
- [B] Prüfung zuerst eintragen und am Altstand ROT sehen, dann Generator ändern (LOG_GITTER_GENERATOR Runde 6/7, LOGBUCH_FENSTER_OG_R1).
- [B] Beweis des Werkzeugs synthetisch UND am echten Foto (LEHREN_2026-11-08 Nr. 2): Synthetik <1 cm bewies nur die Suche, der Echtfehler lag in Pose/Form.
- [B] Druckbarkeit als Prüfzeile mit Sollwert: 1 Teilnetz, wasserdicht, Wandstärke p1 >= 0,0348 m; Fehlerursachen deckungsgleiche Flächen -> 5 cm einbinden bzw. Schnitt 2-3 mm kleiner (L6, L27, L-KR20; LOG_GITTER_GENERATOR Runde 4: 545 Teilnetze -> 1).
- [B] Druckteilung generisch (`druck_teilung.py`): 8 Teile, alle wasserdicht und auf P1S-Bett (max 242 mm), 51 Stifte, Überhang je Teil 0,95 % (LOG_GITTER_GENERATOR Runde 5). Kein Probedruck vorhanden.
- [B] Kreis (parallele Spuren je Bauteil, Agent + Tore): Nacht 9./10.11.: 98 Runden, 11 am Gütetor angenommen, 16 Merges nach main, 4 Reverts; Fotokanten-Recall 0,642 -> 0,666 (STAND_2026-11-10_MORGEN). Beleg Figuren 0,435 -> 0,852, Gauben 0,479 -> 0,651, Quader Gesims 0,434 -> 0,602.
- [B] Realitätszahl nach jeder grünen main-Abnahme (`realitaet_prozent.py`): Basis 14:01 10.11. 79,0 % (Fotokanten 69,5 %, 11/23 Teile >= 0,9) (STAND_2026-11-10_NACHMITTAG).

### 1.5 Quellen/Daten
- [B] Martinstor: Höhe 54,80 m Laser = Modell (stimmt auf 1 cm); Methode am Münster geprüft (116,6 m gemessen, amtlich 116); Flächenabweichung über 13 Höhenstufen Mittel 12 %, Median 7 % (MASSPRUEFUNG_MARTINSTOR). Textquellen (60-66 m) waren falsch.
- [B] Foto-Verhältnismessung (Maß / Fassadenbreite auf gleicher Höhe) ±10 % für das, was der Laser nicht sieht (Torbogen, Uhr, Schild); frühere Augenmaße waren 20-60 % zu groß und zirkulär (MASSPRUEFUNG_MARTINSTOR Teil 2).
- [B] Fehlerbudget LoD2 (LGL gegen Stadt) 917 Paare: First robust sigma 0,56 m, 8,4 % Ausreißer > 3 m, Traufe sigma 1,42 m; ein LoD2-First ist nicht besser als ±0,6 m (QUELLEN_REGISTER).
- [B] Freiraum-Prüfung (Sichtstrahlen Kamera -> Punkt gegen Modell) fand zugemauerte Bögen (Kaufhaus 11 -> 43 Voxel, Martinstor 0 -> 68) (STAND_2026-11-05). Prinzip entspricht Scan2LoD3.

## 2. Was ist gescheitert und warum

### 2.1 Kantengitter / 3D
- [B] Ebenenmodell S8 (Zellbelegung/Graph-Cut): Kanten p90 74-274 cm, springt mit alpha; Carving löst Halle/Giebelstufen nicht auf (LAGEBILD Z.21, STAND_KURZ_2026-11-06).
- [B] Beweis Ansatz A (Photogrammetrie) / B (amtlich) / C (Modell+Restfeld): Kriterium Metrik 2 bei 0 von 3 Objekten bestanden, auch mit fairem `kosten_lr` (A besser als C auf echten Objekten, t +1,49 / +1,60). Rot/gelb belohnt kantenreiche, verrauschte Netze: die perfekte synthetische Wahrheit hatte gelb 0,368, mehr als A 0,315 (BEWEIS_ANSATZ). Daher nie rot+gelb als Maß.
- [B] Kantenfeld S10 (EMAP-Eigenbau): Bögen 1 von 4, Holdout Präz 0,55 gegenüber Kontrolle 0,46; Wolkenfilter F0-F3 ohne Gewinn (LAGEBILD Z.22/23).
- [B] Bogeneinpassen S9 mit Canny-/3D-Kanten als Fitdaten: ~10^4 Hintergrundkanten, Fits sprangen an Boxränder, alle 4 Bögen abgelehnt (LAGEBILD Z.24; STAND_KURZ_2026-11-06).
- [B] Triangulation mit gelockerten Schwellen: 171 130 Segmente / 422 km = reines Rauschen (LAGEBILD Z.38). Streuerfilter und Kontrastfilter: werfen echte Dachkanten weg (Dach-Abdeckung 0,32 -> 0,20; Wolkenabdeckung 0,87 -> 0,71) (Z.44/46).
- [B] Phasenkongruenz Präzision 0,06-0,15; Subpixel-Canny -9 % Rest-RMS, nicht weiterverfolgt; Fusion nach Stimmen verwässert korrelierte Varianten (LAGEBILD Z.3/5/10).
- [B] OpenMVS-Haut auf Carving aufprägen: Arkade 6, Wände zu dünn (ein Versuch, Ursache nicht untersucht) (STAND_KURZ_2026-11-06).
- [B] Leave-out (STAND_2026-11-08_LEAVEOUT): Schärfen (Unsharp) hilft auf unbekannten Fotos nicht (+0,0043|+0,0026); "Gesehen"-Prämie 0,03|0,05 >> hlo-Vorsprung 0,004-0,010. Parametrische Generatoren, Lage-Sweeps, Glätten, Poisson schlugen d03_fix nicht (BS90-BS115).

### 2.2 Formfits
- [B] Gauben (LOG_FORMEN Runde 3-4): Dreiecksschablone im Ebenen-Ortho = Sackgasse (Parallaxe, Fronten liegen 0,5-1,5 m über der Ebene); 12 Triangulationsläufe, 0 von 5 Gauben; nur die Lage von 5 Gauben fotobelegt, Form nicht. Lehre: Spitzen ohne Richtungsvorgabe finden, dann zuordnen; 20 min Debug je Hypothese zu wenig, gehört in synthetischen Beweistest.
- [B] Baluster: Bandwahl nach Gitterlänge falsch (Konsolen statt Brüstung, ein Geschoss zu tief); Periode aus Wolke allein gleichauf 0,225/0,275 (Fenstersprossen periodisch); Kantentest gegen Stabilitätskarten kann nie bestehen, weil Schaftkanten dort fehlen (Quellen-Blindheit) (LOG_FORMEN §3, v11/v12).
- [B] Kleiner Helm: Kandidatensuche scheiterte an Dachschräge dahinter; Ebenen-RANSAC (`ohne_dachebene`) nötig (LOG_FORMEN §1). Waagerechte Ebenen nicht entfernen (Traufring).
- [B] Westgiebel R1 verworfen: Beleg 0,238 -> 0,217, datenbegrenzt, neue Westfotos nötig (STAND_2026-11-10_NACHMITTAG).
- [B] Datenlücken: Commons-Kandidaten (65 Bilder) erwartet gering, Wirkung nicht gemessen (STAND_2026-11-10_NACHMITTAG §7).

### 2.3 Prozess/Kosten
- [B] Handarbeit statt Pipeline am 5.11. (Varianten eo, bo, wh von Hand; Schwellen gesetzt statt gemessen), "Bögen als Tunnel", Fit schrumpfte Pfeiler auf 0 m, Viewer mit falsch ausgerichteter Wolke gezeigt, 1-5 Prozentpunkte als Fortschritt verkauft (LOG_2026-11-05_FEHLER_UND_STAND §2).
- [B] GPU-Port der kNN-Werkzeuge: Ergebnisse identisch, aber GPU meist NICHT schneller (Brute-Force knn_points, Startkosten 3-5 s; cKDTree workers=-1 stark): `wolke_kennzahlen` 0,9-1,3 s CPU gegen 4,3-6,2 s GPU; `textur_projektion` bei 1 Mio. Dreiecken CPU 0,42 s gegen GPU 7,0 s. Nur Normalenschätzung gewinnt (1,6 -> 0,32 s). `modell_ansehen`-Zeitschätzung (10 s) war falsch (CPU 1,3 s). Lehre: Referenzmenge messen, `knn_points` lohnt nur < ~50k Referenzpunkte (GPU_LUECKEN_2026-11-08).
- [B] Parallel über die VRAM-Grenze ist langsamer: 1 parallel 66-70 s, 2 parallel 79 s, 3 parallel 400 s statt 200 s (STAND_2026-11-10_NACHMITTAG §3).
- [B] GPU-Absturz (Xid 31 / NVRM NO_MEMORY) reproduziert bei Summe der Reservierungen ~7,8 GB (Torch 5,5 GB + SIFT); stabil bei 6,4-6,7 GB. SiftGPU nimmt solo bis 7,4 GB und scheitert still (rc 0, 0 Features) (GPU_PARALLEL_UNTERSUCHUNG).
- [B] Martinstor OPENCV-Kameramodell am Strassennetz: kein Gewinn (40/45/40 vs 43/48/49/45 von 56), vermutlich Überanpassung bei 16 Bildern mit eigener Kamera (UEBERGABE_2026-11-03).

## 3. Regeln/Tore: was wirklich etwas verhindert hat, was nur Aufwand war

### Wirksam [B]
- Opus-Bildprüfer als Tor 3: lehnte zweimal den Beleg-Trick ab (Laube-Rückwand +0,22 durch Verschieben der verdeckten ANNAHME-Rückseite) (REZEPT L-KR4). Prüfer erhält nur Bilder, keinen Agentenbericht (SPEC_GRAUZONE_TOR).
- Formfund-Prüfer am Dreierbild Foto|vorher|nachher: Probelauf 8 von 8 richtig (SPEC_GRAUZONE_TOR zitiert SPEC_FORMFUND_TOR, Zahl nicht in SPEC_FORMFUND_TOR selbst nachgeprüft). Anlass: Kantenmaß blind für Form (Treppe statt Sägezahn -0,002; Balkon-Stirnen +0,004).
- Nullkontrolle für jede Kennzahl (L46): Foto-F1 misst auf ornamentreichen Flächen Kantendichte: Erker-Rippen 90 Grad gedreht 0,719 > korrekt 0,657 > ohne 0,618 (REZEPT L46; LOGBUCH_ERKER_UNTERBAU: Foto-F1 Basis 0,596 gegen Achse 11,9: 0,629, Unterschiede winzig).
- Tore dürfen nur am Gegenstand scheitern: OOM = wiederholen (L-KR1); Fehler "Abnahme rot" war OOM in pruefstand.wandstaerke.
- Vergleich nur auf gemeinsamen Beurteilungen (L38: EG2 +0,11 roh, gemeinsam 0,824 -> 0,768) und Gesamtkennzahl pixelgewichtet auf fester Teilmenge (L39: 68,2 % vs 69,6 %).
- Fehlteil-Gedächtnis (`fehlteil_erledigt.json`, Pflichtzeile FEHLTEIL-BEFUND): Kästen wurden vorher 2-3x vergeben (L-KR13). Fehlteil auf 3 Fotos projizieren, bevor man es baut (L-KR8/9: Ost-Staffelgiebel war nur 1,4 m verschoben).
- Rahmen/Lot-Plausibilitätsprobe (Kamerahöhe 0,8-4 m, Lot < 2 Grad) vorgesehen, aber nicht erzwungen (STAND_2026-11-08_LOT_SWEEP_LOOP Nachtrag).
- Gate nach main-Merge mit automatischem Revert (STAND_2026-11-10_MORGEN: "Main war nach jedem Merge grün").
- Quellen-Inventar-Gate (`quellen_inventar.py`, Exit 2 solange Quelle offen) (QUELLEN_REGISTER) - Nutzen für das Kaufhaus nicht dokumentiert [M].

### Verhindert hätte, wurde aber umgangen/zu schwach [B]
- Tor "t < 2" (nicht deutlich schlechter) im Läufer übernahm falsche Öffnungen; Fix: S1b-Tor streng + Elementbuch (SPEC_S1b_TOR_ELEMENTBUCH, aus LOG_2026-11-05 Fehler 2/5). Selbstkorrektur: rot und gelb getrennt zu werten war falsch, jede Kantenkorrektur tauscht rot gegen gelb (Foto 000 rot 0,23 -> 0,40, gelb 0,23 -> 0,10).
- Foto-F1 im Gütetor: Grauzone [-0,005; +0,02) ist blind für Form; 76 verworfene Runden am 11.11. (SPEC_GRAUZONE_TOR). Deshalb zusätzliche Prüfer-Bedingungen.
- Tor "Reproj < 2 px" ist blind für Lage (od_04, STAND_2026-11-10_NACHMITTAG §7).

### Nur Aufwand / nicht belegt wirksam [M]
- Erzwungenes Quellen-Inventar mit 19 Typen, davon viele (Sentinel, SAR, COP_DEM) für ein Einzelgebäude [M, kein Beleg im Dokument].
- Stufe-4-Optimierung CMA-ES 12 Generationen ~65 min: verworfen, kein deutlicher Gewinn (t -1,2) (STAND_2026-11-05).
- Mehrere Hundert Messungen von Hand per Sprachmodell-Sichtpick sind laut REZEPT selbst "Handarbeit mit Protokoll", Prüfmaßstab bis Automatik gleiche Werte trifft.
- Zählprotokoll-Gate auf Gradienten-Quotienten für Baluster: nie bestanden, wegen Quellen-Blindheit; Koordinator ersetzte durch Z-Protokoll (LOG_FORMEN).

## 4. Werkzeuge (tools/*.py): Zweck, Einsatz, Zustand

Zustand nach Dokumentlage; ich habe die Tools nicht ausgeführt. "läuft" = im Dokument als gelaufen/bewiesen genannt.

| Werkzeug | Zweck / wann einsetzen | Zustand laut Dokument |
|---|---|---|
| `gitter_kette.sh` | Gesamtkette Kameras -> Karten -> Sweep -> Aufbau -> Schleife -> Formen -> Körper (Nachtlauf) | läuft (REZEPT) |
| `kanten_stabil.py`, `stabil_alle.py` | Stabilitätskarten je Foto, zuerst für alle Fotos | läuft (261 Läufe, 2 s) |
| `kanten_tiefe_sweep.py`, `_flaeche.py` | Tiefen-Sweep -> 3D-Kantenpunkte/Features | läuft, 80 Ref. -> 631k Pkt. |
| `kanten_features.py --farbe stabil --sweep`, `features_in_objekt.py` | Rippen/Bänder (linienhaft) aus Mehrfoto-Sweep; laut CLAUDE.md Standardweg | im Repo, Wirkung auf Erker-Rippen belegt: LOGBUCH_ERKER (Foto-F1 0,596 -> 0,629) |
| `lot_aus_fotos.py`, `rahmen_lot_foto.py` | Lot/Rahmen; erste Stufe eines neuen Objekts | läuft; NICHT in Pipeline eingehängt, boden_z 1,66 Festwert (STAND_LOT_SWEEP_LOOP Nachtrag) |
| `wolke_lot_ausrichten.py` | alter Boden/Wand-Fit | VERALTET/verzerrt (STAND_LOT_SWEEP_LOOP) |
| `teil_sweep_gpu.py`, `sweep_alle.py`, `modell_ausrichten_gpu.py`, `schleife_ausrichten.py`, `schleife_teile.py` | Lage-Sweep/8-DoF-Ausrichtung | Sweep läuft; `schleife_teile` laut Stand 8.11. "noch NICHT erfolgreich im richtigen Rahmen" |
| `modell_foto_overlay.py` | DAS Bildfeedback-Werkzeug (Z-Puffer seit 9.11.) | läuft |
| `foto_mass.py` (`--kamera`, `--ebene`, `--tri`, `--tri2d`) | Fotomaße, einzige zulässige Maßquelle | läuft |
| `foto_zaehlung.py` | Zählung nur am Foto | läuft |
| `kamera_bruecke.py` | K-Protokoll aus Bündelkamera, `--kandidaten` Fotos nach Blickwinkel | läuft |
| `foto_diff.py` (`--mehrstufig`, `kosten_lr`) | Modell in jedes Foto; `kosten_lr` fairer als rot/gelb | läuft; `--mehrstufig` Standard AUS |
| `fehlteile_finden.py`, `teile_lage_pruefen.py`, `bauteil_sichtliste.py` | Abnahme nach Bau; teile_lage mit lot2-Wolke (alte Voreinstellung = falscher Rahmen: Helm O 2,54 statt 0,14 m) | läuft (lot2) |
| `teil_fotoform.py`, `formfund_pruefen.py` (Spec), `realitaet_form.py` (Spec), `test_grauzone_tor.py` (Spec) | Form-Prüfung je Teil am Foto | teil_fotoform gebaut (10.11. UNGETESTET in echter Runde); die drei anderen sind nur Specs mit Beweisplan |
| `baukasten_gen.py` | parametrischer Generator mit Bauteilfamilien (erker_polygon, helm_geschweift, konsolenreihe, fensterreihe mit nische_tiefe ...) | läuft |
| `pruefstand.py` + `bauen_abnehmen.sh` | Massregister/Abnahme; Messarten `schnitt_reichweite`, `ebene_vorspruenge`, `wandstaerke` | läuft; freiraum_audit scheitert immer an fehlender SFM-AUSRICHTUNG-buendel.json (STAND_NACHMITTAG) |
| `druck_teilung.py`, `druck_vorcheck.py` | Druckteilung/Überhang | läuft, kein Probedruck |
| `muster_fit.py`, `kanten_tor.py`, `helm_fit.py`, `baluster_fit.py` | Formfits/Wiederholung | baluster_fit läuft (abgenommen per Z-Protokoll); `kanten_tor.py`/`muster_fit.py` "im Bau" (REZEPT) |
| `gauben_fit.py`, `gauben_ortho.py`, `gauben_tri.py` | Gaubenform | gescheitert (nur Lagen) |
| `kreis_regler`, `bauteil_kreis.py`, `gpu_slot.py`, `main_abnahme.sh` | Agenten-Runden-Automatik, GPU-Schlange (3 Plätze, >= 1500 MiB frei) | läuft; Regler startet Spuren selbst |
| `realitaet_prozent.py`, `betrachter_note.py` (Spec) | Zahl in %; Betrachter-Note als Spec | realitaet_prozent läuft; betrachter_note nur Spec (SPEC_BETRACHTER_NOTE) |
| `gpu_knn.py` | NN auf GPU | läuft; schneller nur bei kleinen Referenzmengen |
| `quellen_inventar.py`, `lod2_fehlerbudget.py`, `stadt_lod2_schneiden.py` | Datenquellen, Fehlerbudget | gelaufen (Kaufhaus, Martinstor) |
| `freiraum_pruefen/fassaden/oeffnungen/audit.py` | Sichtstrahlen-Freiraum | gelaufen (null5); im Kaufhaus grob3 nicht aktiv (Datei fehlt) |
| `restfeld_fassade.py`, `bogen_anpassen.py` | 2,5D-Rest; Bogenfit | Restfeld Dachfläche 0,77 -> 0,16 m; Wand verworfen; Bogenfit WIDERSPRUCH nicht übernommen |
| `wolke_carving.py`, `ebenen_modell.py` | Carving-Körper / S8 | Carving bester druckbarer Stand 6.11. (First 21,34, Traufe FEHLER); S8 gescheitert |
| `video_suchen.py`, `bilder_holen.py`, `online_ansichten_holen.py` | Video-/Bildbeschaffung | gelaufen; Wikimedia 1 Datei/25 s, bei 429 abbrechen |
| `foto_luecken.py`, `luecken_seite_bauen.py`, `teil_ansichten.py` | Abdeckung -> Standpunkte -> Handyseite | foto_luecken ungetestet/uncommittet; luecken_seite gelaufen; teil_ansichten nie durchgelaufen (OOM) (STAND_NACHMITTAG §4) |
| `regression.py`, `versuch_log.py`, `jobplan.py`, `treppe.py` | Regression/Versuchslog/Warteschlange/Stufenleiter | regression läuft; treppe nur Auswertung getestet (UEBERGABE_2026-11-03); jobplan durch job_start.sh ersetzt [A] |

## 5. Fallen und Nutzer-Rückmeldungen

### 5.1 Wiederholt vom Nutzer bemängelt
- Zu viel Handarbeit, "das muss alles automatisch generisch gehen", keine Spezialfälle/Objektnamen im Code (UEBERGABE_2026-11-03, LOG_2026-11-05, SPEZIALCODE_AUDIT_2026-11-03: Zinnenanzahl 5 im Code, Altpfad Ecktürmchen u. a.).
- Schönreden: "der gleiche Mist wie früher" bei 1-5 Prozentpunkten (LOG_2026-11-05 Fehler 8). Ehrlich berichten, nichts behaupten, was man im Bild nicht sieht.
- Nutzer entdeckte selbst: gekippten Rahmen (Overlay), Bögen als Tunnel, rote Bögen richtiger als Fit, Erker als Kasten, Helm zu schlank, Brüstung ~22 dicke ovale Stäbe statt dichter Docken, Staffelgiebel Ost versetzt (STAND_2026-11-10_NACHMITTAG).
- Feine Kanten: Auflösung nie senken (Nutzer fragte, ob RAM der Grund); mehrstufig, Helligkeit/Kontrast variieren (LOG_2026-11-05 §8).
- Video/Daten selbst beschaffen (nach Rüge "Clown ... Drohnenvideos") (LOG_2026-11-05 Fehler 13); Laser/LoD2 nicht Wahrheit, Widerspruch eintragen statt mitteln.
- Nie idle, Uhrzeit per `date`, Monitor nach Jobstart (STAND_2026-11-05).
- Nutzer wünscht ehrliche Prozentzahl: "eine Zahl, mit der wir gegen 100 % kommen" (SPEC_BETRACHTER_NOTE, 11.11. 19:05); Foto-Realität deckelt bei ~85 % (Farbkanten, Schatten, Moos, Glasmuster).
- Ziel Nutzer: Gittermodell ALLER wesentlichen Kanten rein aus Kantenerkennung, daraus druckbares, "beeindruckendes" H0-Kaufhaus (PLAN_KANTENGITTER_H0).

### 5.2 Annahmen, die sich als falsch erwiesen [B]
- "Rückwand 6,54 m" (rohkoerper, nie gemessen) vs Wolke 7,28: Maße entlang dem Strahl verschoben (L16).
- "Links = West" geraten: Helme und Giebelende vertauscht, 9 Messungen auf falscher Achse (L18; M-6261-004..012 ungültig).
- Erker-Paarung mit Index-Versatz lieferte schöne Geraden und war falsch (M-6161-001..008) (L25).
- Altmodell-Traufzone sollte 0,93 m Versatz erzeugen: Hauptursache war z-Versatz im K-Protokoll (Runde 5 korrigiert Runde 4).
- DOM1-Zellwert als Maximum: Bias +0,58 vs -0,19 m je nach Rechnung; Dach-Beweis nicht eindeutig (BEWEIS_ANSATZ §Metrik 3).
- Dachbreite "Widerspruch 4,6 vs 5,9 m" war ein Maßunterschied der Schätzer (UEBERGABE_2026-11-03); Quellen nur mit identischem Schätzer vergleichen.
- Stufenhöhe Giebelzähler 0,83 m gegen Wolke + M-6261 1,21 m: nur Anzahl bewiesen, Nebengröße nicht (L41).
- Voraussage "10 s je Ansicht" für CPU-Painter falsch (1,3 s) (GPU_LUECKEN).
- Handyfotos: EXIF meldet 5,25 mm obwohl 72-mm-Zoom (Digitalzoom 3x); fester f-Fehler 2 % = ~0,6 m Tiefenfehler (STAND_KURZ_2026-11-06; Nutzer-Einstellungen Nubia in ANLEITUNG_FOTOS_NUBIA.md referenziert).
- Kamerahöhe 15,8 m im Netzrahmen (Fotos eher vom Platz): ungeklärt (LEHREN_2026-11-08 Nr. 7).

### 5.3 Fallen im Werkzeug/Prozess [B]
- Overlay ohne Verdeckung täuscht (schiefes "Viereck" = Rückwandfenster, Ring-Rückhälfte, "Säulen fehlen"): L7, L-H2, L-V1.
- Fotoauswahl erst nach Sichtbarkeitsprüfung begrenzen (L11), sonst wirkt Datenlage blind. Pfeiler/Gewölbe-Innenaufnahmen werden als "sehend" für Giebel gewählt (Fremdverdeckung) (LOG_GITTER_GENERATOR Runde 6 Nachtrag).
- Wolke als Arbeitsdatei schneidet still ab (z 26 m, Giebelspitzen 29 m) (L23).
- Schrumpf-Falle: jede Zielfunktion, bei der ein kleineres Modell besser passt (BS143/145) schrumpft; feste Rückrichtung + Kappung nötig (LEHREN_2026-11-08 Nr. 4).
- Beleg erschleichbar durch Schieben verdeckter Annahmeflächen (L-KR4); Beleg nur auf kamera-sichtbare Fläche [OFFEN generisch].
- Parallele Spuren müssen auf aktuellem main starten, sonst zwei angenommene Fassungen (L-KR21).
- Spuren nach RAM-Spitze budgetieren: 8 Spuren, zwei vom OOM-Killer beendet (L-KR5); Vorrangregeln brauchen Höchstwartezeit (L40: Formliste 2 h verhungert).
- `| grep ... || true` verschluckt Werkzeugabstürze: foto_breitenprofil lief für grob3 nie, unbemerkt (L-W1).
- Maschinell geschriebene JSON im Originalformat zurückschreiben (indent=1), sonst 10k-Zeilen-Diff (L43). JS `//` in einzeilig zusammengesetztem Code verschluckt den Rest (STAND_NACHMITTAG §8).
- Daten: Platte lief auf 100 % (Fusionsvarianten 2,5 GB bitgleiche Kopien); Regel verlinken statt kopieren; `sfm_dicht ... alle` löscht dicht_alle (STAND_2026-11-08_LEAVEOUT). `pkill -f` trifft eigene Shell (UEBERGABE_2026-11-03).
- Lizenz: Mapillary CC BY-NC-SA, YouTube-Standard, Google 3D Tiles, VGGT, MASt3R, 3DGS, nvdiffrast, CGAL/PolyFit (GPL), CityEngine nicht im Produkt (LIZENZ_WERKZEUGE, ROADMAP_PIPELINE_ALLGEMEIN). Lizenzangaben aus Recherchen teils "Treffer"/ungeprüft.
- Webzugriff: Wikimedia 429 -> IP-Sperre ~15 min (L-OD2).

### 5.4 Messgrenzen [B]
- Zirkulär: Referenz 1 (Wolkenkanten) und Sweep A sind Eingabe des Aufbaus; Sweep B nur in der Fotoauswahl unabhängig; keine echte Handwahrheit (`kanten_wahrheit.jsonl` existiert nicht) (LAGEBILD §2/§3).
- Martinstor: von 69 Prüfungen nur 2 unabhängig von den Fotos (UEBERGABE_2026-11-03), Tabelle auf das Modell abgenommen = zirkulär (BEWEIS_ANSATZ).
- Foto-F1 (9-cm-Zellen, 18 cm Glättung, 25-Grad-Knick) zerlegt 45-Grad-Grate; Rippenflanken 0,08 m unter sprung_m 0,25 (L45).
- Posenfehler in der Höhe nie gemessen (PLAN_KANTENGITTER_H0 §7).
- Präzision des Kantengitters gesamt 0,078 -> 0,089, weil Gitter an vielen Modellkanten leer ist (STAND_2026-11-10_MORGEN).

## 6. Widersprüche zwischen Dokumenten / veraltete Stellen

1. LOG_GITTER_GENERATOR Runde 4: "0,93 m Versatz kam nur von traufzone_alt" -> Runde 5: Hauptursache z-Versatz im K-Protokoll. Runde-4-Aussage veraltet; REZEPT L5 trägt "KORREKTUR Runde 5".
2. REZEPT: Lehren-Nummern doppelt vergeben (L11, L12, L13, L31-L33, L-KR17 dreimal mit verschiedenem Inhalt, L-GS5 doppelt, L-KR18/19 doppelt). Verweise "L11" mehrdeutig. [B, im Text sichtbar]
3. LOG_GITTER_GENERATOR §5 (Runde 1): "foto_diff/fehlteile NICHT lauffähig, brauchen K-Protokolle" -> in Runde 2-5 K-Protokolle gebaut. Veraltet.
4. STAND_KURZ_2026-11-06 "kein Martinstor als Zweitobjekt bis Kaufhaus fertig" und "keine Vorlagen" (ersetzt 6.11. 07:05) vs ROADMAP_PIPELINE_ALLGEMEIN (zweites Objekt Burg als Allgemeingültigkeitstest) vs der jetzige Nutzerwunsch nächstes Gebäude von null. ROADMAP Stand 2.11., teilweise überholt.
5. STAND_KURZ_2026-11-06 Abschnitt "Läuft gerade (veraltet, S9 fertig)" ist selbst als veraltet markiert, enthält aber noch Anweisungen.
6. STAND_2026-11-08_LEAVEOUT (Foto-Diff-Sieger hlo) arbeitet in OpenMVS-/SFM-AUSRICHTUNG-Rahmen (null5); STAND_2026-11-08_LOT_SWEEP_LOOP am gleichen Tag erklärt alle "Sweeps/Overlays/Teile-Läufe im gemeinsamen SfM-Netzrahmen" für ungültig. Ob die Leave-out-Ergebnisse betroffen sind, steht nirgends. [offen]
7. METHODIK_KANTEN_STABILITAET: "segmente_tsweep.json zeige Bögen, Fenster UND das Dach" vs LAGEBILD: Datei enthält nur 3 Segmente > 15 m, Dach steckt in segmente_hoch_ts.json (28 Segmente > 15 m, tol 0,12). (LAGEBILD §4)
8. DexiNed: LOGBUCH positiv vs METHODIK/RECHERCHE "verworfen" ohne Grund (LAGEBILD §4). LIMAP: BS61 "Linien echt" (Deckung 63 % vs 36 %) vs ERKLAERUNG "funktioniert nicht" (16-Foto-Prototyp). Zwei Recherchen desselben Tages mit unterschiedlicher LIMAP-Priorität (RECHERCHE_DRAHTGITTER Prio 1 vs RECHERCHE_VERFAHREN hinter Eigenbau).
9. "Abdeckung" doppelt definiert (Schleife: Recall 3 cm; gitter_naehe: Referenzanteil 10 cm) (LAGEBILD §4).
10. STAND_2026-11-10_MORGEN "Main war nach jedem Merge grün" vs STAND_2026-11-10_NACHMITTAG: freiraum_audit scheitert in JEDER main-Abnahme (fehlende Datei); "alle Prüfungen bestanden" bedeutet also inklusive bekanntem Dauerfehler (auch LOGBUCH_HELM_W_R4: "vorbestehend").
11. STAND_2026-11-10_MORGEN §Nachtrag: Gütetor mit Foto-F1 "UNGETESTET in echter Runde" -> nachmittags Spuren laufen; Form-Specs (SPEC_FORMNOTE, SPEC_GRAUZONE_TOR) setzen voraus, dass Foto-F1 blind ist (L46). Konsistent, aber das Tor-Gewicht des Foto-F1 ist nicht neu begründet. [A]
12. QUELLEN_REGISTER: Titel "16 kanonische Quellentypen", Tabelle führt 19. Außerdem Korrektur im Text (3d.freiburg.de doch abrufbar).
13. ROADMAP "Faller führt Martinstor-Bausatz 130922" Marktangabe ohne Primärbeleg [M].
14. METHODE_WUNSCH_ZU_MODELL (Gelände/Egg-Crate/Laser, Spur N 1:160) gehört zu einem anderen Teilprojekt; nicht auf Gebäudemodellierung übertragbar, nennt aber Prinzipien (Qualität vor Material, Koordinaten gegenchecken, "Hirsch lag 130 m daneben").
15. PLAN_VERBESSERUNG Stand 3.11. (Martinstor): viele Punkte überholt durch Kaufhaus-Arbeiten; "manuell -> Pipeline" Tabelle M1-M13 nirgends als erledigt markiert.
16. SPEC_S4: Beweis T1-T5 enthält "Erkerfenster aus Ortho-Parsing", später durch `erker_polygon` + Foto-Messung ersetzt; Status der S4-Umsetzung im Dokument nicht festgehalten.

## 7. Offene Fragen

- Welche Foto-Auflösung/Methode ersetzt Foto-F1 für Formnote, wenn Spec-Prüfer (Opus-Bild) nur mit Fallen getestet ist? Formnote/Grauzonen-Tor: Beweisläufe als Spec definiert, Ergebnis nicht in diesen Dateien (SPEC_FORMNOTE, SPEC_GRAUZONE_TOR).
- Unabhängige Wahrheit: Nutzer-Handkanten (6-10 Ausschnitte, 2-3 h) nie erstellt; Posenfehler in der Höhe unbekannt (LAGEBILD §3).
- Westseite, Rückseite/Gasse und Dach erhöht: datenbegrenzt, braucht neue Fotos; Fotoplan-Handyseite gebaut, Standpunkte 12/14 vor Ort prüfen (STAND_NACHMITTAG).
- Ist die Rückseite (Firstspiegel, Tiefe 19,2 vs LoD2 12,54) richtig? ANNAHME (LOG_GITTER_GENERATOR §6).
- Glas-Tiefe in Fenstern: Foto 0,06-0,10 vs Wolke 0,27, gewählt 0,2 = ANNAHME (LOGBUCH_FENSTER_OG_R1). Erker-Rippen: 2 Bogenrippen je Fläche ANNAHME, kein foto_zaehlung-Protokoll (LOGBUCH_ERKER_UNTERBAU).
- Gauben-Form, Balustradenkantentest, Bogenfit als Parameterobjekt, Körper aus Gitter (Flächenzyklen) nicht gelöst (LAGEBILD §3).
- Offener Quellenwiderspruch First: Foto ~20,3 vs LoD2/DOM1 20,8-21,0 (STAND_2026-11-05); Martinstor First 46,2 (Laser) vs 45,0 (LoD2) (MASSPRUEFUNG_MARTINSTOR).
- Lizenz: Wirkung NC-abgeleiteter Messwerte auf Produkt; Rechtsfragen (Rekonstruktion = Bearbeitung?, § 44b UrhG, Panoramafreiheit/Drohne) offen, Anwalt vor Verkauf (ROADMAP §1/§7, LIZENZ_WERKZEUGE).
- Probedruck: H0-Mindestwand 0,6-0,8 mm "für H0 NICHT belegt"; Nadel als Metallstift [M] (ROADMAP §6).
- Foto 6124: Modell bedeckt nur 2,5 % des Bildes, Kamera prüfen (STAND_2026-11-10_MORGEN).
- Audit-Bilder/STLs in Git wachsen ~1 GB/h; Nutzerentscheid nötig (STAND_2026-11-10_MORGEN §Offen 5).
- GPU/Beschleunigung: CASPAR-BA-Backend in pycolmap 4.2.1 aktiv? Ceres-CUDA-Ergebnis (`ba_gpu_messung.log`) nie gelesen (RECHERCHE_2026-11-06_BESCHLEUNIGUNG §Offen). Alle Faktoren dort ANNAHME bis auf zitierte.
- `foto_breitenprofil` hat Turm-Voreinstellungen (Martinstor), für grob3 nie gelaufen (L-W1).

## 8. Zeit-/Kostenangaben

| Was | Dauer | Beleg |
|---|---|---|
| Stabilitätskarte je Foto | ~2 s (261 Läufe, RTX 4060) | METHODIK_KANTEN_STABILITAET |
| Tiefen-Sweep je Referenzfoto | 5 s; 80 Fotos -> 631k Punkte | ebd. |
| Dichte Wolke ohne Testfotos (86 Fotos) | 2088 s | STAND_2026-11-08_LEAVEOUT |
| Nullstart null5 Stufen 1-4 | Ende Stufe 3 14:11, Lauf fertig 15:23 (5.11.); Stufe 4 CMA-ES 12 Gen ~65 min, verworfen | STAND_2026-11-05 |
| eine null6-Generation | 5 min, 9 min bei eigenen CPU-Tests nebenbei | LOG_2026-11-05 Fehler 9 |
| Agentenrunden Kantengitter -> Generator | je ~90 min (Runde 1, 2) | LOG_GITTER_GENERATOR Kopf |
| Formfit-Runden Helm/Gauben/Baluster | ab 19:10 bis 20:11, Gauben 12 Läufe ohne Erfolg | LOG_FORMEN |
| Jedes Torfoto-Rundenfoto/Überprüfung | Durchsatz 1 parallel 66-70 s, 2: 79 s, 3: 400 s | STAND_2026-11-10_NACHMITTAG |
| Kreis-Nacht 9./10.11. | 98 Runden, 62 mit Gütetor, bis 6 Spuren parallel | STAND_2026-11-10_MORGEN |
| Rest bis ~89 % (Schätzung 10.11.) | 10-12 h für 6 schwache Teile (nicht belegt, Schätzung) | STAND_2026-11-10_NACHMITTAG §6 [A] |
| LOT-Rahmenkorrektur | Tagesaufwand 8.11. (Schritte 1-25) | STAND_LOT_SWEEP_LOOP |
| geplante Bausteine Kantengitter | Kurven 1 Tag; Verfeinerung 1 Tag; Formfamilien 1 Tag; Flächen+Körper Tag 3; H0-Druckteilung Tag 4-5 (PLAN, Schätzung) | PLAN_KANTENGITTER_H0 §6 [A] |
| Recherche-Rangliste | LIMAP-Neulauf 4-8 h; Bogenfit 6-10 h; Drahtgitter -> Flächen 8-16 h; Fusion 2-3 Wochen | RECHERCHE_DRAHTGITTER, RECHERCHE_FUSION [A] |
| Rundenkosten Fenster/Helm | Fenster OG R1 an einem Tag (10.11.): Beleg 0,67 -> 0,979; Helm W R4: Beleg unverändert, Kanten R 0,417 -> 0,721 | LOGBUCH_* |
| GPU-Schaden Eindämmung | Messung 15:12 6.11.; Budget SIFT <= 2,2 GiB, Torch <= 4 GiB, Summe <= 6,5 GiB | GPU_PARALLEL_UNTERSUCHUNG |
| Gewinn paralleler GPU-Betrieb | +70-80 % gegenüber seriell (Schätzung, nicht an realen Jobs gemessen) | ebd. [A] |
| Laufzeit Messwerkzeuge | modell_foto_overlay 7 s; regression, bauen_abnehmen je Objekt nicht beziffert | LOG_GITTER_GENERATOR |
| Speicherbedarf | Root 7,6 -> 13 GB nach Git-Auslagerung; Datenplatte 17,7 GB frei (6.11.), 12 GB (8.11.) | STAND-Dateien |
| Kosten Verkauf/Markt | Faller Martinstor-Bausatz ~50 EUR [M]; Plattenkauf Höllental ~40 EUR (Gelände, anderes Projekt) | ROADMAP, METHODE_WUNSCH |

Keine Dokumente nennen Kosten in Geld oder Token für Agentenläufe.

## Die 8 wichtigsten Lehren (Kurzfassung)
1. Rahmen zuerst: Lot/Boden messen und Kamerahöhe/Überlagerung am Foto prüfen, bevor irgendein Fit läuft (25 Grad gekippt hat Tage entwertet).
2. Bildfeedback (Modell auf kalibriertem Foto, mit Z-Puffer) vor jeder Zahlenjagd; Nutzer sieht Fehler, die Zahlen verbergen.
3. Jede Kennzahl braucht Nullkontrolle (verschobenes/gedrehtes/fehlendes Teil), sonst belohnt sie Kantendichte; rot+gelb und Foto-F1 sind auf Ornamenten blind.
4. Maße nur über `foto_mass` mit Ebene aus Wolke + Triangulation (>= 20-45 Grad Schnittwinkel); Handaugenmaße waren 20-60 % daneben.
5. Zählungen und Perioden aus dem Foto-Protokoll, nicht aus Wolke oder Gitter (Baluster 68 aus Z-Protokoll; Fotosignal 6 % zu eng).
6. Prüfung erst ROT am Altstand, dann Generator ändern; Prüfer sieht nur Bilder; Agentenberichte nie ungeprüft übernehmen.
7. Referenz muss verfahrensfremd sein (Wolke und Sweep teilen Fehler); Filter nie an der Menge prüfen, nach der man ihn einstellt.
8. Fehlende Daten sind der Engpass (Westseite, Rückseite, Dach, Gewölbe): Fotoplan und Standpunkte früh planen; GPU-Parallelität und Hardwarebudget (VRAM <= 6,5 GiB, parallel nicht über Grenze) als Grundbetrieb festlegen.

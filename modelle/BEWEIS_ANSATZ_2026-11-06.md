# Beweis Ansatz: Vergleichslauf A Photogrammetrie / B amtlich / C Modell+Restfeld (Sonnet, Stand 2026-11-05 19:3x; Datei nach Spec 2026-11-06)

Spezifikation: modelle/SPEC_BEWEIS_ANSATZ.md. Werkzeuge: tools/beweis_ansatz.py (+ beweis_ansatz_synth.py, beweis_ansatz_bericht.py). Zwischenergebnisse: /media/oem/scan/rc-park_null/beweis_ansatz/<objekt>/ergebnisse.json (alle Zahlen).
Metriken und Kriterium wurden nicht nachjustiert. Einzige Aenderungen NACH Sicht der Zahlen (alle offengelegt): (1) Metrik 3 auf Anweisung der Koordination (nur getroffene Zellen, Abdeckung getrennt, beide Rechnungen); (2) Metrik 1 von Punkt-zu-Punkt auf Punkt-zu-Flaeche (Punkt-zu-Punkt hatte 8 cm Abtastboden: Wahrheit gegen sich selbst 0,083 m);
(3) Bildblatt zugeschnitten; (4) Slicer-Skalierung auf alle drei Achsen; (5) synthetische Wahrheit "stark" zusaetzlich, weil "schwach" (Traufe +0,8, Helmueberstand +0,5, je Seite ein Fenster weniger) nur 0,7 cm Chamfer zum Standardmodell erzeugte (die Helmform kommt aus profile_generator.json, nicht aus masse.json).

## Ergebnis in einem Satz
Das Kriterium ist NICHT bestanden: Metrik 2 (C < A UND C < B in rot und gelb) gilt bei 0 von 3 Objekten (verlangt 2). C schlaegt B bei Kaufhaus und synthetisch deutlich, verliert aber in der Fotokantenmetrik (gelb) gegen A (Kaufhaus 0,35 vs 0,13; synthetisch 0,37 vs 0,32/0,30) und bei Martinstor gegen B (gelb 0,563 vs 0,525).
Wichtige Einschraenkung: gelb belohnt kantenreiche, verrauschte Netze. Auf der synthetischen Wahrheit selbst (W, bekannt perfekt) ist gelb 0,368/0,358 und damit HOEHER als bei A (0,315/0,298): die Metrik ist als Rangfolge zwischen so verschiedenen Netzarten nur bedingt tauglich. Das aendert das Kriterium nicht; es steht als Befund da.
Bei der Geometrie gegen die Wahrheit (Metrik 1, nur synthetisch) ist C dagegen klar am besten (Chamfer 0,0045 bzw. 0,0585 m gegen A 0,76/0,69 und B 0,91). Vorsicht: bei "schwach" ist das fast trivial (Standardmodell liegt schon bei 0,0068 m); bei "stark" (Breite/Tiefe/Knick/Hoehe verstellt) bleibt C bei 0,0585 m, 35 % der Flaeche > 3,5 cm.

## Voraussetzungen (10 Zeilen) und Konfiguration
1. open3d/pymeshlab fehlen in venv-seg; open3d 0.20 (MIT) liegt in der vorhandenen /media/oem/scan/venv-mesh (nichts installiert) - Poisson dort als Hilfsmodus von beweis_ansatz.py. pymeshfix (venv-seg) fuer Wasserdichtheit.
2. Kaufhaus A: objekt.json freiraum.dicht (kaufhaus_null4 dicht_alle fused.ply, 961488 Punkte, Normalen+vis) + messprotokoll/SFM-AUSRICHTUNG-buendel.json, Modellrahmen wie freiraum_pruefen/restfeld_fassade ((X-t)@R/s), Gegenprobe: Wolke gegen Laeufer-STL Median 0,22 m; Punkte mit >= 3 Kameras; Zuschnitt = Huellquader von C + 3 m.
3. Kaufhaus B/C: stand.json (qualitaetsstufen_kaufhaus_null6): B = modell_s1.stl (Ausgangsmodell v_ausgang), C = modell_s3_v9.stl (Stufe 3).
4. Martinstor A: martinstor_lod2 dicht_nord (200477 Punkte) + martinstor_lod2/messprotokoll/SFM-AUSRICHTUNG-buendel.json (die Wolke der Hauptobjekt-Ordner hat keine Ausrichtung im K-Rahmen; Kamerazentren Wolke-gegen-K 0,5-1,2 m bei Nahkameras: Restunsicherheit, A kann dadurch benachteiligt sein). Nur Nordseite!
5. Martinstor B: der Generator hat keinen Modus "nur amtlich" und LoD2 enthaelt nur den Torbau -> B = DOM1-Hoehenfeld (1-m-Zellen im LoD2-Grundriss, Saeulen). Abweichung von der Spec (dort Generator mit LoD2); B ist nicht wasserdicht (139 Koerper). Martinstor C = modelle/stl/martinstor_v4_1-87.stl.
6. Zurueckgehaltene Fotos Kaufhaus (nicht unter den 11 Laeuferfotos 000 010 022 032 049 059 072 117 214 222 247, kein Nachtfoto, gleichmaessig aus 83 Kandidaten): 001, 024, 054, 083, 211, 234. Die dichte Wolke (A) und fassade_auto (C) benutzen diese Fotos dennoch mit (Leck, trifft A und C).
7. Zurueckgehaltene Fotos Martinstor: 002, 017, 027, 051, 108, 136 (K aus der lod2-Kette, rms <= 1,5 px, nicht unter den 24 per Regex aus Messprotokollen/Tabellen ermittelten "benutzten" Nummern; strenges "nie angepasst" ist nicht beweisbar: die Handparametrierung ist ueber Wochen gewachsen).
8. Synthetisch: Martinstor-Generator in modelle/beweis_synth (Wahrheit) und modelle/beweis_synth_basis (Zwilling), 10 echte Kameras (martinstor_lod2), 4 Anpassungs-/6 Pruefphotos (Index 0,3,6,9 vorab), Pruefbilder wie test_foto_diff.foto_rendern (CPU) mit k1, Wolke 473k Punkte (>= 2 Kameras sichtbar, 5 cm Rauschen), DOM1 aus Zellmaxima.
9. C synthetisch: Generator + Koordinatensuche statt param_suche (martinstor_v4_gen kennt kein BAUTEIL_PARAM); Liste vorab GZ1, HELM_UEBER, DACHHOEHE, DB; Restfeld nicht gerechnet (keine Fassadenebenen ohne Fotoauswertung).
10. GPU: foto_diff real/synthetisch auf der GPU (freie GPU, kein CPU-Ausweichen noetig; GPU-Wartezeit ~12 min, Kaufhaus). Platz /media/oem/scan 9 GB frei (> 5 GB); tools/job_start.sh war durch das Platztor (15 GB) gesperrt -> Laeufe per systemd-run --user (gleiche Eigenschaften), keine Torlockerung.

## Metrik 3 (Dach gegen DOM1): zwei Rechnungen, Widerspruch geklaert
Dachbeweis (Agent a40b) rechnet Strahl von oben auf die Zellmitte; mein erster Lauf nahm das Zellmaximum der Oberflaechenpunkte und setzte Zellen ohne Netz auf 0 m (Kaufhaus A 7,75 m: Artefakt). Jetzt beide nur auf getroffenen Zellen, Abdeckung getrennt (Tabellen: "Zellmax", "Strahl"). Mein Strahl reproduziert a40b exakt (B 0,166/0,303, C 0,440/0,547).
Widerspruch erklaert: Zellmaximum gibt B (LoD2-Dach, amtlich) Bias +0,58 m, Strahl auf Zellmitte -0,19 m. Ein steiles Dach (~50 Grad) liegt im Zellmaximum bis ~0,6 m ueber der Zellmitte; B stimmt mit DOM1 also dort besser ueberein, wo man den DOM1-Zellwert als Zellmitten-/Mittelwert versteht. Auf der synthetischen Wahrheit (DOM1 = Zellmaximum per Konstruktion) ist umgekehrt nur Zellmax konsistent (W 0,003 vs Strahl 0,88 bzw. 2,7 m an der Spitze).
Welche gilt: fuer den echten Laser ist der Zellwert nicht als Maximum belegt (Gegenindiz: B-Bias); die konservative Lesung ist der Strahl auf Zellmitte, nach der C am Kaufhaus-Dach GEGEN B VERLIERT (Median 0,44 vs 0,17 m; first_versatz -0,63 aus Fotos). Nach Zellmax gewinnt C (0,36 vs 0,69). Das ist KEIN eindeutiger Beleg fuer C; offene Beobachtung in modelle/kaufhaus_null5/masstabelle.json eingetragen (DOM1-Zellwertdefinition an LoD2-Ebene testen). Die Dach-Zellzahlen bei Martinstor (9) und synthetisch (5/9 Zellen, steile Spitze ausgenommen) sind zu klein fuer Aussagen.

## Tabellen (Verfahren x Metrik), unveraendert aus tools/beweis_ansatz_bericht.py

### kaufhaus_null5

Zurueckgehaltene Fotos: 001, 024, 054, 083, 211, 234

| Metrik | A | B | C |
|---|---|---|---|
| 2 rot Mittel (Modellkante ohne Foto) | 0.035 | 0.128 | 0.048 |
| 2 gelb Mittel (Fotokante ohne Modell) | 0.131 | 0.855 | 0.354 |
| 2 Foto 001 rot/gelb | 0.007/0.181 | 0.014/0.871 | 0.001/0.499 |
| 2 Foto 024 rot/gelb | 0.008/0.137 | 0.377/0.949 | 0.050/0.385 |
| 2 Foto 054 rot/gelb | 0.053/0.033 | 0.001/0.953 | 0.052/0.261 |
| 2 Foto 083 rot/gelb | 0.051/0.250 | 0.058/0.543 | 0.094/0.282 |
| 2 Foto 211 rot/gelb | 0.041/0.082 | 0.237/0.942 | 0.062/0.318 |
| 2 Foto 234 rot/gelb | 0.048/0.103 | 0.084/0.873 | 0.027/0.383 |
| 3 Dach Zellmax: Abdeckung (Zellen mit Netz) | 0.486 | 0.981 | 0.981 |
| 3 Dach Zellmax: Median |dz| nur getroffen (m) | 0.556 | 0.687 | 0.358 |
| 3 Dach Zellmax: Mittel |dz| nur getroffen (m) | 0.707 | 0.673 | 0.427 |
| 3 Dach Zellmax: Bias nur getroffen (m) | -0.406 | 0.578 | 0.207 |
| 3 Dach Strahl: Abdeckung (Zellen mit Netz) | 0.450 | 0.948 | 0.948 |
| 3 Dach Strahl: Median |dz| nur getroffen (m) | 1.355 | 0.166 | 0.440 |
| 3 Dach Strahl: Mittel |dz| nur getroffen (m) | 1.497 | 0.303 | 0.547 |
| 3 Dach Strahl: Bias nur getroffen (m) | -1.445 | -0.188 | -0.540 |
| 3 Dach alt (ohne Netz = Hoehe 0) Mittel (m), ueberholt | 7.754 | 0.899 | 0.657 |
| 3 Pruefstand laser/lod2 bestanden | 0/2 | 2/2 | 1/2 |
| 4 Pruefstand merkmal anzahl bestanden | 1/1 | 0/1 | 0/1 |
| 5 wasserdicht / Koerper | True/1 | True/1 | True/1 |
| 5 Dreiecke | 308734 | 682 | 3342 |
| 5 Volumen (cm3, STL 1:87) | 2306 | 8616 | 7859 |
| 5 Wand min / p5 (mm) | 0.23/2.44 | 0.31/8.6 | 0.21/2.53 |
| 5 Wand-Anteil < 0,8 mm | 0.020 | 0.005 | 0.020 |
| 5 Slicer rc / Zeit | 0 / 6h 1m 29s | 0 / 6h 57m 48s | 0 / 7h 39m 50s |
| 6 Rechenzeit Bauen (s) | 68.8 | - | - |
| 6 foto_diff 6 Fotos, Summe Rechenzeit (s, ohne GPU-Wartezeit) | 43.1 | 49.7 | 49.5 |

Pruefstand A: Wasserdicht (1=ja)=1.00 [ok]; Anzahl getrennte Koerper=1.00 [ok]; Dachebene an der Nordwand, u = 4 m (m)=10.40 [fehler]; First, Mitte (m)=20.36 [fehler]; Gesehener Durchgang/Arkade ohne Modelloeffnun=- [fehler]; Arkade Hauptfassade: Oeffnungen ab Boden (Anz=4.00 [ok]
Pruefstand B: Wasserdicht (1=ja)=1.00 [ok]; Anzahl getrennte Koerper=1.00 [ok]; Dachebene an der Nordwand, u = 4 m (m)=12.15 [ok]; First, Mitte (m)=21.43 [ok]; Gesehener Durchgang/Arkade ohne Modelloeffnun=20.62 [fehler]; Arkade Hauptfassade: Oeffnungen ab Boden (Anz=0.00 [fehler]
Pruefstand C: Wasserdicht (1=ja)=1.00 [ok]; Anzahl getrennte Koerper=1.00 [ok]; Dachebene an der Nordwand, u = 4 m (m)=12.02 [ok]; First, Mitte (m)=20.80 [fehler]; Gesehener Durchgang/Arkade ohne Modelloeffnun=- [fehler]; Arkade Hauptfassade: Oeffnungen ab Boden (Anz=5.00 [fehler]

### martinstor

Zurueckgehaltene Fotos: 002, 017, 027, 051, 108, 136

| Metrik | A | B | C |
|---|---|---|---|
| 2 rot Mittel (Modellkante ohne Foto) | 0.060 | 0.162 | 0.073 |
| 2 gelb Mittel (Fotokante ohne Modell) | 0.730 | 0.525 | 0.563 |
| 2 Foto 002 rot/gelb | 0.015/0.608 | 0.011/0.662 | 0.000/0.553 |
| 2 Foto 017 rot/gelb | 0.067/0.752 | 0.128/0.535 | 0.030/0.598 |
| 2 Foto 027 rot/gelb | 0.022/0.839 | 0.232/0.628 | 0.082/0.665 |
| 2 Foto 051 rot/gelb | 0.108/0.586 | 0.319/0.359 | 0.266/0.464 |
| 2 Foto 108 rot/gelb | 0.054/0.817 | 0.102/0.442 | 0.052/0.550 |
| 2 Foto 136 rot/gelb | 0.092/0.776 | 0.179/0.527 | 0.006/0.548 |
| 3 Dach Zellmax: Abdeckung (Zellen mit Netz) | 1.000 | 1.000 | 1.000 |
| 3 Dach Zellmax: Median |dz| nur getroffen (m) | 21.317 | 0.000 | 3.668 |
| 3 Dach Zellmax: Mittel |dz| nur getroffen (m) | 16.909 | 0.352 | 3.566 |
| 3 Dach Zellmax: Bias nur getroffen (m) | 16.909 | 0.352 | 3.566 |
| 3 Dach Strahl: Abdeckung (Zellen mit Netz) | 1.000 | 1.000 | 1.000 |
| 3 Dach Strahl: Median |dz| nur getroffen (m) | 19.812 | 0.000 | 1.118 |
| 3 Dach Strahl: Mittel |dz| nur getroffen (m) | 15.632 | 0.000 | 1.308 |
| 3 Dach Strahl: Bias nur getroffen (m) | 15.632 | 0.000 | 0.915 |
| 3 Dach alt (ohne Netz = Hoehe 0) Mittel (m), ueberholt | 16.909 | 0.352 | 3.566 |
| 3 Pruefstand laser/lod2 bestanden | 0/1 | 0/1 | 1/1 |
| 4 Pruefstand merkmal anzahl bestanden | 2/7 | 2/7 | 7/7 |
| 5 wasserdicht / Koerper | True/1 | False/139 | True/1 |
| 5 Dreiecke | 118994 | 2336 | 24572 |
| 5 Volumen (cm3, STL 1:87) | 58842 | 6629 | 6311 |
| 5 Wand min / p5 (mm) | 0.96/74.55 | 11.49/22.99 | 1.38/4.88 |
| 5 Wand-Anteil < 0,8 mm | 0.000 | 0.000 | 0.000 |
| 5 Slicer rc / Zeit | 0 / 5h 28m 8s | 0 / 1h 46m 20s | 0 / 2h 8m 57s |
| 6 Rechenzeit Bauen (s) | 9.2 | 1.4 | - |
| 6 foto_diff 6 Fotos, Summe Rechenzeit (s, ohne GPU-Wartezeit) | 28.2 | 25.5 | 31.9 |

Pruefstand A: Tuermchen-Spitze Hoehe (m)=73.70 [fehler]; Tuermchen-Kegel Durchmesser 2 m unter Spitze =- [fehler]; Tuermchen-Kegel Durchmesser 4 m unter Spitze =- [fehler]; Tuermchen Anzahl (Querschnitte 2 m unter Spit=0.00 [fehler]; Dachreiter Dicke 3,5 m unter der Spitze (m)=0.00 [fehler]; Dachreiter Dicke 1 m unter der Spitze (m)=0.00 [fehler]; Dachreiter Knauf Durchmesser (m)=0.00 [fehler]; Dachreiter Knauf Lage (Anteil ueber First)=-0.25 [fehler]; Gesamthoehe (m)=75.51 [widerspruch]; Dachansatz / Glockenstock-Oberkante (m)=47.90 [fehler]; First / Dach-Oberkante (m)=59.90 [fehler]; Zinnenkranz Oberkante (m)=- [fehler]; Spitzenlaenge ueber First (m)=15.61 [fehler]; Fenster obere Reihe Suedseite (Anzahl, z 22,1=0.00 [fehler]; Fenster untere Reihe Suedseite (Anzahl, z 18,=0.00 [fehler]; Fenster obere Reihe Nordseite (Anzahl, z 22,1=0.00 [fehler]; Fenster untere Reihe Nordseite (Anzahl, z 18,=0.00 [fehler]; Zinnen-Scharten Suedseite (Anzahl, z 31,1 m)=1.00 [fehler]; Zinnen-Scharten Nordseite (Anzahl, z 31,1 m)=0.00 [fehler]; Uhr Zifferblatt-Nische Suedseite (Breite m)=3.10 [fehler]; Helmflanke N-S: Halbtiefen-Abnahme je m (Mode=0.03 [fehler]; Inschrifttafel NORD Breite (m, z 7,5)=4.50 [fehler]; Keine Tafel auf SUED bei z 7,5 (m)=5.05 [fehler]; Doppeladler SUED Breite (m, z 9,45)=4.35 [fehler]; Eckturm NW Durchmesser (m, Sehne der Schnittk=2.52 [ok]; Eckturm NW Kegelspitze (m)=18.29 [fehler]; Sockel-Grundriss Rechteck (m2, z 1 m)=868.01 [fehler]; Wasserdicht (1=ja)=1.00 [ok]; Anzahl getrennte Koerper=1.00 [ok]; Silhouettenbreite bei 30 m (m, 3 Kameras)=- [fehler]; Gesamtbreite y bei 29,5-33,5 m (Modell, mit T=43.81 [fehler]; Silhouettenbreite Zone 23,5-28 m (Kamera 031)=4.04 [fehler]; Ecktuermchen: Erkerkoerper Durchmesser bei 34=1.29 [fehler]; Oeffnungen Westwand obere Reihe (Anzahl, z 26=0.00 [ok]; Oeffnung Westwand (Anzahl, z 22,3 m)=0.00 [fehler]; Knauf-Lage zwischen Tuermchenspitze und Nadel=-9.81 [fehler]; First / Dach-Oberkante (m) - SfM Nordnetz=59.90 [fehler]; Eckturm NW Vorsprung vor der Nordwand (m)=1.56 [fehler]; Eckturm NW Mitte y (m)=-3.81 [ok]; Ecktuermchen NE: Achse Abstand zur Nordwand b=0.79 [ok]; Profil Dach: Breite y bei 45.2 m (m)=29.27 [fehler]; Profil Dach: Breite y bei 49.2 m (m)=24.82 [fehler]; Profil Ecktuermchen: Durchmesser bei 34.25 m =1.44 [fehler]; Profil Ecktuermchen: Durchmesser bei 37.75 m =1.84 [fehler]; Profil Ecktuermchen: Durchmesser bei 40.25 m =1.80 [ok]; Profil Ecktuermchen: Durchmesser bei 42.50 m =1.53 [fehler]; Profil Dach: Breite y bei 53.2 m (m)=19.16 [fehler]; Profil Dach (Foto 061): Tiefe x bei 47 m (m)=18.94 [fehler]; Profil Dach (Foto 061): Tiefe x bei 50 m (m)=18.65 [fehler]; Profil Dach (Foto 061): Tiefe x bei 53 m (m)=18.43 [fehler]; Uhr Nord: Mitte z (m)=27.29 [fehler]; Gesamtbreite y bei 28,5 m (Konsolen unter den=17.82 [fehler]; Band tuermchen gesims (27.50-28.25 m): Aussen=1.08 [ok]; Band tuermchen gesims (31.75-32.50 m): Aussen=1.43 [ok]; Band tuermchen traufe (35.00-35.50 m): Aussen=1.57 [fehler]; Band tuermchen kupfer (35.50-43.50 m): Aussen=1.64 [fehler]; Band tuermchen kegel (35.50-44.50 m): Aussenr=1.36 [fehler]; Helm geradlinig (tief, 41.8-53.8 m): max. Abw=0.59 [fehler]; Helm geradlinig (quer, 41.8-53.8 m): max. Abw=1.76 [fehler]; Band zentral Quaderperiode 20-24 m: Reliefper=- [widerspruch]; Band zentral Quaderperiode 22-26 m: Reliefper=0.43 [ok]; Band tuermchen Quaderperiode 28-32 m: Reliefp=- [fehler]; Profil Dach (Foto 061): Tiefe x bei 55 m (m)=18.31 [fehler]; Band tuermchen hell (32.50-33.50 m): Aussenra=1.43 [ok]; Band tuermchen offen (33.50-35.00 m): Aussenr=1.45 [ok]; Helm geradlinig (tief, 41.8-54.8 m): max. Abw=0.59 [fehler]; Helm geradlinig (quer, 41.8-54.8 m): max. Abw=1.76 [fehler]; Lueftungsfenster Sued Oeffnung Breite (m, Fen=2.95 [fehler]; Ecktuermchen Arkadenband: Oeffnungen je Achte=1.00 [ok]; Ecktuermchen Arkade: Oeffnung offen in den Er=0.00 [fehler]; Glockenstock Schallarkaden Sued: Breite je Oe=2.24 [fehler]; Glockenstock Schallarkaden Sued: Anzahl je Fl=1.00 [fehler]; Ecktuermchen Arkade: flacher Segmentbogen (Br=1.00 [ok]; Ecktuermchen Arkade: Oeffnungshoehe (Bruestun=0.04 [fehler]; Eckquader Schaft z 8-12,5 m: Schichthoehe (Re=- [fehler]; Eckquader Schaft z 22,5-27 m: Schichthoehe (R=- [fehler]
Pruefstand B: Tuermchen-Spitze Hoehe (m)=42.11 [fehler]; Tuermchen-Kegel Durchmesser 2 m unter Spitze =0.12 [fehler]; Tuermchen-Kegel Durchmesser 4 m unter Spitze =1.50 [ok]; Tuermchen Anzahl (Querschnitte 2 m unter Spit=1.00 [fehler]; Dachreiter Dicke 3,5 m unter der Spitze (m)=2.52 [fehler]; Dachreiter Dicke 1 m unter der Spitze (m)=1.60 [fehler]; Dachreiter Knauf Durchmesser (m)=0.00 [fehler]; Dachreiter Knauf Lage (Anteil ueber First)=5.83 [fehler]; Gesamthoehe (m)=54.84 [widerspruch]; Dachansatz / Glockenstock-Oberkante (m)=46.00 [fehler]; First / Dach-Oberkante (m)=54.60 [ok]; Zinnenkranz Oberkante (m)=- [fehler]; Spitzenlaenge ueber First (m)=0.24 [fehler]; Fenster obere Reihe Suedseite (Anzahl, z 22,1=2.00 [ok]; Fenster untere Reihe Suedseite (Anzahl, z 18,=2.00 [fehler]; Fenster obere Reihe Nordseite (Anzahl, z 22,1=2.00 [fehler]; Fenster untere Reihe Nordseite (Anzahl, z 18,=2.00 [fehler]; Zinnen-Scharten Suedseite (Anzahl, z 31,1 m)=1.00 [fehler]; Zinnen-Scharten Nordseite (Anzahl, z 31,1 m)=2.00 [fehler]; Uhr Zifferblatt-Nische Suedseite (Breite m)=0.95 [fehler]; Helmflanke N-S: Halbtiefen-Abnahme je m (Mode=0.20 [ok]; Inschrifttafel NORD Breite (m, z 7,5)=5.05 [fehler]; Keine Tafel auf SUED bei z 7,5 (m)=5.05 [fehler]; Doppeladler SUED Breite (m, z 9,45)=4.10 [fehler]; Eckturm NW Durchmesser (m, Sehne der Schnittk=3.16 [fehler]; Eckturm NW Kegelspitze (m)=20.00 [fehler]; Sockel-Grundriss Rechteck (m2, z 1 m)=153.66 [fehler]; Wasserdicht (1=ja)=0.00 [fehler]; Anzahl getrennte Koerper=139.00 [fehler]; Silhouettenbreite bei 30 m (m, 3 Kameras)=14.28 [fehler]; Gesamtbreite y bei 29,5-33,5 m (Modell, mit T=12.18 [fehler]; Silhouettenbreite Zone 23,5-28 m (Kamera 031)=12.86 [fehler]; Ecktuermchen: Erkerkoerper Durchmesser bei 34=2.89 [ok]; Oeffnungen Westwand obere Reihe (Anzahl, z 26=2.00 [fehler]; Oeffnung Westwand (Anzahl, z 22,3 m)=2.00 [fehler]; Knauf-Lage zwischen Tuermchenspitze und Nadel=1.09 [fehler]; First / Dach-Oberkante (m) - SfM Nordnetz=54.60 [ok]; Eckturm NW Vorsprung vor der Nordwand (m)=1.39 [ok]; Eckturm NW Mitte y (m)=-4.12 [fehler]; Ecktuermchen NE: Achse Abstand zur Nordwand b=- [fehler]; Profil Dach: Breite y bei 45.2 m (m)=6.32 [fehler]; Profil Dach: Breite y bei 49.2 m (m)=4.39 [ok]; Profil Ecktuermchen: Durchmesser bei 34.25 m =3.16 [ok]; Profil Ecktuermchen: Durchmesser bei 37.75 m =1.50 [fehler]; Profil Ecktuermchen: Durchmesser bei 40.25 m =0.07 [fehler]; Profil Ecktuermchen: Durchmesser bei 42.50 m =- [fehler]; Profil Dach: Breite y bei 53.2 m (m)=2.19 [fehler]; Profil Dach (Foto 061): Tiefe x bei 47 m (m)=3.42 [fehler]; Profil Dach (Foto 061): Tiefe x bei 50 m (m)=2.46 [fehler]; Profil Dach (Foto 061): Tiefe x bei 53 m (m)=2.46 [fehler]; Uhr Nord: Mitte z (m)=26.50 [fehler]; Gesamtbreite y bei 28,5 m (Konsolen unter den=12.37 [fehler]; Band tuermchen gesims (27.50-28.25 m): Aussen=1.06 [ok]; Band tuermchen gesims (31.75-32.50 m): Aussen=1.06 [fehler]; Band tuermchen traufe (35.00-35.50 m): Aussen=1.06 [fehler]; Band tuermchen kupfer (35.50-43.50 m): Aussen=-0.16 [fehler]; Band tuermchen kegel (35.50-44.50 m): Aussenr=-2.24 [fehler]; Helm geradlinig (tief, 41.8-53.8 m): max. Abw=0.78 [fehler]; Helm geradlinig (quer, 41.8-53.8 m): max. Abw=0.53 [fehler]; Band zentral Quaderperiode 20-24 m: Reliefper=- [widerspruch]; Band zentral Quaderperiode 22-26 m: Reliefper=- [widerspruch]; Band tuermchen Quaderperiode 28-32 m: Reliefp=- [fehler]; Profil Dach (Foto 061): Tiefe x bei 55 m (m)=0.00 [fehler]; Band tuermchen hell (32.50-33.50 m): Aussenra=1.06 [fehler]; Band tuermchen offen (33.50-35.00 m): Aussenr=1.06 [fehler]; Helm geradlinig (tief, 41.8-54.8 m): max. Abw=0.78 [fehler]; Helm geradlinig (quer, 41.8-54.8 m): max. Abw=0.53 [fehler]; Lueftungsfenster Sued Oeffnung Breite (m, Fen=1.45 [fehler]; Ecktuermchen Arkadenband: Oeffnungen je Achte=1.00 [ok]; Ecktuermchen Arkade: Oeffnung offen in den Er=0.00 [fehler]; Glockenstock Schallarkaden Sued: Breite je Oe=1.40 [ok]; Glockenstock Schallarkaden Sued: Anzahl je Fl=2.00 [ok]; Ecktuermchen Arkade: flacher Segmentbogen (Br=0.00 [fehler]; Ecktuermchen Arkade: Oeffnungshoehe (Bruestun=0.00 [fehler]; Eckquader Schaft z 8-12,5 m: Schichthoehe (Re=- [fehler]; Eckquader Schaft z 22,5-27 m: Schichthoehe (R=- [fehler]
Pruefstand C: Tuermchen-Spitze Hoehe (m)=44.50 [ok]; Tuermchen-Kegel Durchmesser 2 m unter Spitze =0.73 [ok]; Tuermchen-Kegel Durchmesser 4 m unter Spitze =1.58 [ok]; Tuermchen Anzahl (Querschnitte 2 m unter Spit=4.00 [ok]; Dachreiter Dicke 3,5 m unter der Spitze (m)=0.13 [ok]; Dachreiter Dicke 1 m unter der Spitze (m)=0.09 [ok]; Dachreiter Knauf Durchmesser (m)=0.67 [ok]; Dachreiter Knauf Lage (Anteil ueber First)=0.24 [ok]; Gesamthoehe (m)=65.30 [ok]; Dachansatz / Glockenstock-Oberkante (m)=40.90 [ok]; First / Dach-Oberkante (m)=55.50 [ok]; Zinnenkranz Oberkante (m)=31.50 [ok]; Spitzenlaenge ueber First (m)=9.80 [ok]; Fenster obere Reihe Suedseite (Anzahl, z 22,1=2.00 [ok]; Fenster untere Reihe Suedseite (Anzahl, z 18,=1.00 [ok]; Fenster obere Reihe Nordseite (Anzahl, z 22,1=3.00 [ok]; Fenster untere Reihe Nordseite (Anzahl, z 18,=1.00 [ok]; Zinnen-Scharten Suedseite (Anzahl, z 31,1 m)=4.00 [ok]; Zinnen-Scharten Nordseite (Anzahl, z 31,1 m)=4.00 [ok]; Uhr Zifferblatt-Nische Suedseite (Breite m)=4.15 [ok]; Helmflanke N-S: Halbtiefen-Abnahme je m (Mode=0.23 [ok]; Inschrifttafel NORD Breite (m, z 7,5)=3.40 [ok]; Keine Tafel auf SUED bei z 7,5 (m)=0.00 [ok]; Doppeladler SUED Breite (m, z 9,45)=1.70 [ok]; Eckturm NW Durchmesser (m, Sehne der Schnittk=2.22 [ok]; Eckturm NW Kegelspitze (m)=13.07 [ok]; Sockel-Grundriss Rechteck (m2, z 1 m)=128.97 [ok]; Wasserdicht (1=ja)=1.00 [ok]; Anzahl getrennte Koerper=1.00 [ok]; Silhouettenbreite bei 30 m (m, 3 Kameras)=13.74 [ok]; Gesamtbreite y bei 29,5-33,5 m (Modell, mit T=11.70 [ok]; Silhouettenbreite Zone 23,5-28 m (Kamera 031)=12.02 [ok]; Ecktuermchen: Erkerkoerper Durchmesser bei 34=3.12 [ok]; Oeffnungen Westwand obere Reihe (Anzahl, z 26=0.00 [ok]; Oeffnung Westwand (Anzahl, z 22,3 m)=1.00 [ok]; Knauf-Lage zwischen Tuermchenspitze und Nadel=0.64 [ok]; First / Dach-Oberkante (m) - SfM Nordnetz=55.50 [ok]; Eckturm NW Vorsprung vor der Nordwand (m)=1.21 [ok]; Eckturm NW Mitte y (m)=-3.70 [ok]; Ecktuermchen NE: Achse Abstand zur Nordwand b=0.89 [ok]; Profil Dach: Breite y bei 45.2 m (m)=4.84 [ok]; Profil Dach: Breite y bei 49.2 m (m)=4.55 [ok]; Profil Ecktuermchen: Durchmesser bei 34.25 m =3.10 [ok]; Profil Ecktuermchen: Durchmesser bei 37.75 m =2.74 [ok]; Profil Ecktuermchen: Durchmesser bei 40.25 m =1.68 [ok]; Profil Ecktuermchen: Durchmesser bei 42.50 m =0.73 [ok]; Profil Dach: Breite y bei 53.2 m (m)=4.25 [ok]; Profil Dach (Foto 061): Tiefe x bei 47 m (m)=4.33 [ok]; Profil Dach (Foto 061): Tiefe x bei 50 m (m)=2.97 [ok]; Profil Dach (Foto 061): Tiefe x bei 53 m (m)=1.61 [ok]; Uhr Nord: Mitte z (m)=25.69 [ok]; Gesamtbreite y bei 28,5 m (Konsolen unter den=11.68 [ok]; Band tuermchen gesims (27.50-28.25 m): Aussen=1.17 [ok]; Band tuermchen gesims (31.75-32.50 m): Aussen=1.50 [ok]; Band tuermchen traufe (35.00-35.50 m): Aussen=1.85 [ok]; Band tuermchen kupfer (35.50-43.50 m): Aussen=1.00 [ok]; Band tuermchen kegel (35.50-44.50 m): Aussenr=0.90 [ok]; Helm geradlinig (tief, 41.8-53.8 m): max. Abw=0.00 [ok]; Helm geradlinig (quer, 41.8-53.8 m): max. Abw=0.00 [ok]; Band zentral Quaderperiode 20-24 m: Reliefper=0.62 [widerspruch]; Band zentral Quaderperiode 22-26 m: Reliefper=0.65 [widerspruch]; Band tuermchen Quaderperiode 28-32 m: Reliefp=0.50 [ok]; Profil Dach (Foto 061): Tiefe x bei 55 m (m)=1.05 [ok]; Band tuermchen hell (32.50-33.50 m): Aussenra=1.55 [ok]; Band tuermchen offen (33.50-35.00 m): Aussenr=1.55 [ok]; Helm geradlinig (tief, 41.8-54.8 m): max. Abw=0.00 [ok]; Helm geradlinig (quer, 41.8-54.8 m): max. Abw=0.00 [ok]; Lueftungsfenster Sued Oeffnung Breite (m, Fen=0.75 [ok]; Ecktuermchen Arkadenband: Oeffnungen je Achte=1.00 [ok]; Ecktuermchen Arkade: Oeffnung offen in den Er=1.00 [ok]; Glockenstock Schallarkaden Sued: Breite je Oe=1.36 [ok]; Glockenstock Schallarkaden Sued: Anzahl je Fl=2.00 [ok]; Ecktuermchen Arkade: flacher Segmentbogen (Br=1.00 [ok]; Ecktuermchen Arkade: Oeffnungshoehe (Bruestun=1.28 [ok]; Eckquader Schaft z 8-12,5 m: Schichthoehe (Re=0.55 [ok]; Eckquader Schaft z 22,5-27 m: Schichthoehe (R=0.65 [ok]

### synthetisch

Zurueckgehaltene Fotos: 005, 015, 027, 044, 078, 108

| Metrik | A | B | C | W |
|---|---|---|---|---|
| 1 Chamfer (m) | 0.7599 | 0.9052 | 0.0045 | 0.0000 |
| 1 Hausdorff (m) | 5.94 | 5.00 | 0.40 | 0.00 |
| 1 Anteil > 3,5 cm | 0.607 | 0.972 | 0.025 | 0.000 |
| 1 Anteil > 10 cm | 0.534 | 0.960 | 0.017 | 0.000 |
| 2 rot Mittel (Modellkante ohne Foto) | 0.187 | 0.427 | 0.165 | 0.152 |
| 2 gelb Mittel (Fotokante ohne Modell) | 0.315 | 0.853 | 0.373 | 0.368 |
| 2 Foto 005 rot/gelb | 0.138/0.327 | 0.358/0.930 | 0.100/0.325 | 0.093/0.317 |
| 2 Foto 015 rot/gelb | 0.121/0.354 | 0.203/0.872 | 0.067/0.389 | 0.059/0.381 |
| 2 Foto 027 rot/gelb | 0.392/0.415 | 0.263/0.790 | 0.463/0.556 | 0.445/0.556 |
| 2 Foto 044 rot/gelb | 0.148/0.245 | 0.532/0.915 | 0.085/0.329 | 0.061/0.319 |
| 2 Foto 078 rot/gelb | 0.159/0.264 | 0.593/0.811 | 0.115/0.293 | 0.105/0.291 |
| 2 Foto 108 rot/gelb | 0.162/0.287 | 0.616/0.803 | 0.161/0.346 | 0.153/0.344 |
| 3 Dach Zellmax: Abdeckung (Zellen mit Netz) | 0.800 | 1.000 | 1.000 | 1.000 |
| 3 Dach Zellmax: Median |dz| nur getroffen (m) | 0.757 | 0.000 | 0.002 | 0.002 |
| 3 Dach Zellmax: Mittel |dz| nur getroffen (m) | 0.918 | 0.000 | 0.004 | 0.004 |
| 3 Dach Zellmax: Bias nur getroffen (m) | 0.918 | -0.000 | -0.003 | -0.003 |
| 3 Dach Strahl: Abdeckung (Zellen mit Netz) | 0.800 | 1.000 | 1.000 | 1.000 |
| 3 Dach Strahl: Median |dz| nur getroffen (m) | 0.313 | 0.000 | 2.762 | 2.762 |
| 3 Dach Strahl: Mittel |dz| nur getroffen (m) | 0.301 | 0.000 | 2.734 | 2.734 |
| 3 Dach Strahl: Bias nur getroffen (m) | -0.235 | -0.000 | -2.734 | -2.734 |
| 3 Dach alt (ohne Netz = Hoehe 0) Mittel (m), ueberholt | 9.184 | 0.000 | 0.004 | 0.004 |
| 3 Pruefstand laser/lod2 bestanden | 0/0 | 0/0 | 0/0 | 0/0 |
| 4 Pruefstand merkmal anzahl bestanden | 0/0 | 0/0 | 0/0 | 0/0 |
| 5 wasserdicht / Koerper | True/1 | True/1 | True/1 | True/1 |
| 5 Dreiecke | 176736 | 1672 | 24644 | 24556 |
| 5 Volumen (cm3, STL 1:87) | 5934 | 10168 | 6316 | 6327 |
| 5 Wand min / p5 (mm) | 0.01/9.13 | 11.49/22.99 | 1.38/2.86 | 1.38/4.57 |
| 5 Wand-Anteil < 0,8 mm | 0.010 | 0.000 | 0.000 | 0.000 |
| 5 Slicer rc / Zeit | 0 / 2h 20m 46s | 0 / 2h 24m 38s | 0 / 2h 34m 14s | 0 / 2h 33m 38s |
| 6 Rechenzeit Bauen (s) | 28.6 | 0.2 | 298.2 | - |
| 6 foto_diff 6 Fotos, Summe Rechenzeit (s, ohne GPU-Wartezeit) | 23.7 | 22.1 | 25.6 | 25.5 |


### synthetisch_stark

Zurueckgehaltene Fotos: 005, 015, 027, 044, 078, 108

| Metrik | A | B | C | W |
|---|---|---|---|---|
| 1 Chamfer (m) | 0.6946 | 0.9050 | 0.0585 | 0.0000 |
| 1 Hausdorff (m) | 5.67 | 5.00 | 2.00 | 0.00 |
| 1 Anteil > 3,5 cm | 0.600 | 0.972 | 0.354 | 0.000 |
| 1 Anteil > 10 cm | 0.526 | 0.959 | 0.228 | 0.000 |
| 2 rot Mittel (Modellkante ohne Foto) | 0.194 | 0.477 | 0.160 | 0.153 |
| 2 gelb Mittel (Fotokante ohne Modell) | 0.298 | 0.830 | 0.369 | 0.358 |
| 2 Foto 005 rot/gelb | 0.144/0.305 | 0.587/0.887 | 0.100/0.365 | 0.102/0.304 |
| 2 Foto 015 rot/gelb | 0.111/0.336 | 0.351/0.844 | 0.093/0.390 | 0.063/0.389 |
| 2 Foto 027 rot/gelb | 0.380/0.410 | 0.492/0.814 | 0.466/0.558 | 0.439/0.593 |
| 2 Foto 044 rot/gelb | 0.142/0.232 | 0.504/0.903 | 0.062/0.305 | 0.065/0.296 |
| 2 Foto 078 rot/gelb | 0.208/0.250 | 0.447/0.775 | 0.110/0.275 | 0.114/0.246 |
| 2 Foto 108 rot/gelb | 0.181/0.255 | 0.483/0.757 | 0.128/0.318 | 0.135/0.322 |
| 3 Dach Zellmax: Abdeckung (Zellen mit Netz) | 0.889 | 1.000 | 1.000 | 1.000 |
| 3 Dach Zellmax: Median |dz| nur getroffen (m) | 1.819 | 0.000 | 0.020 | 0.003 |
| 3 Dach Zellmax: Mittel |dz| nur getroffen (m) | 4.275 | 0.000 | 0.225 | 0.003 |
| 3 Dach Zellmax: Bias nur getroffen (m) | 0.177 | -0.000 | -0.220 | 0.001 |
| 3 Dach Strahl: Abdeckung (Zellen mit Netz) | 0.778 | 1.000 | 1.000 | 1.000 |
| 3 Dach Strahl: Median |dz| nur getroffen (m) | 0.428 | 0.000 | 2.610 | 0.701 |
| 3 Dach Strahl: Mittel |dz| nur getroffen (m) | 3.585 | 0.000 | 2.015 | 0.881 |
| 3 Dach Strahl: Bias nur getroffen (m) | -0.937 | -0.000 | -2.015 | -0.881 |
| 3 Dach alt (ohne Netz = Hoehe 0) Mittel (m), ueberholt | 8.494 | 0.000 | 0.225 | 0.003 |
| 3 Pruefstand laser/lod2 bestanden | 0/0 | 0/0 | 0/0 | 0/0 |
| 4 Pruefstand merkmal anzahl bestanden | 0/0 | 0/0 | 0/0 | 0/0 |
| 5 wasserdicht / Koerper | True/1 | True/1 | True/1 | True/1 |
| 5 Dreiecke | 191236 | 1736 | 24512 | 24474 |
| 5 Volumen (cm3, STL 1:87) | 6541 | 10268 | 6230 | 6415 |
| 5 Wand min / p5 (mm) | 0.02/8.4 | 11.49/22.99 | 1.38/5.14 | 1.5/3.65 |
| 5 Wand-Anteil < 0,8 mm | 0.005 | 0.000 | 0.000 | 0.000 |
| 5 Slicer rc / Zeit | 0 / 2h 30m 34s | 0 / 2h 25m 23s | 0 / 2h 41m 42s | 0 / 2h 40m 2s |
| 6 Rechenzeit Bauen (s) | 12.8 | 0.2 | 336.6 | - |
| 6 foto_diff 6 Fotos, Summe Rechenzeit (s, ohne GPU-Wartezeit) | 23.9 | 21.3 | 21.6 | 21.6 |


### Kriterium Metrik 2 (C < A und C < B, rot UND gelb im Mittel)

- kaufhaus_null5: C<A False, C<B True; rot A/B/C [0.0348, 0.1285, 0.0478], gelb A/B/C [0.1309, 0.8552, 0.3545]
- martinstor: C<A False, C<B False; rot A/B/C [0.0596, 0.1617, 0.0726], gelb A/B/C [0.7297, 0.5255, 0.5629]
- synthetisch: C<A False, C<B True; rot A/B/C [0.1866, 0.4275, 0.1652], gelb A/B/C [0.3153, 0.8534, 0.373]
- synthetisch_stark: C<A False, C<B True; rot A/B/C [0.1944, 0.4772, 0.1599], gelb A/B/C [0.298, 0.83, 0.3685]

=> Metrik-2-Bedingung erfuellt bei 0 von 4 Objekten (verlangt: >= 2 von 3)


## Bestanden/nicht je Kriterium
- Metrik 2 (C < A und C < B, rot UND gelb, >= 2 von 3 Objekten): NICHT bestanden (0 von 3; Kaufhaus: C<B ja, C<A nein; Martinstor: C<A nein (rot 0,073 > 0,060; gelb 0,563 < 0,730), C<B nein (gelb 0,563 > 0,525; rot 0,073 < 0,162); synthetisch: C<B ja, C<A nein).
- C >= A und C >= B in JEDER Metrik: nicht bestanden: Metrik 2 (s. o.), Metrik 3 Kaufhaus Strahl (C verliert gegen B), Metrik 4 Kaufhaus (A 1/1, C 0/1: Arkade 5 statt 4; B 0/1), Metrik 5 Kaufhaus (Anteil Wand < 0,8 mm A/C 0,02, B 0,005), Martinstor Metrik 4/5 und 3: C 7/7 und 1/1 Pruefstandzeilen, aber ZIRKULAER (Martinstor-Tabelle wurde auf dieses Modell abgenommen). Gewonnen: Metrik 1 (nur synthetisch), Metrik 4/3 Martinstor (zirkulaer), Wasserdichtheit/Slicer alle bestanden ausser Martinstor-B (139 Koerper).
- Metrik 6 (nur berichtet): A 69 s (Kaufhaus), 9 s (Martinstor), 13-29 s (synth.); B <= 2 s; C Kaufhaus Laeuferstand = Stunden (nicht je Verfahren getrennt messbar), synthetisch Koordinatensuche 298-337 s. Handarbeit 0 (Skript).

## Zusatzbefund: wo A besser ist als C (Eingabe Stufe 4)
Kaufhaus: A hat gelb 0,03-0,25 gegen C 0,26-0,50 in allen sechs Pruefphotos (Foto 054 gelb A 0,033 vs C 0,261). Sichtbar im Bildblatt: A deckt die Fassadenreliefs/Gesimse ab, die C als glatte Flaeche hat (Photo 001: C gelb 0,499, Fassadenfeld rechts unten voll gelb). Das ist genau das Restfeld-Gebiet, das noch nicht uebernommen ist (Zellliste: restfeld_fassade.py auf modell_s3_v9 ist Eingabe fuer Stufe 4; hier nicht gerechnet).
Aber: A hat Dach/Volumen falsch (Abdeckung der Dachzellen 49 %, Volumen 2306 statt 7859 cm3, ein Teil der Front fehlt) - A allein ist nicht druckbar als Gebaeude.

## Bilder (angesehen)
- modelle/kaufhaus_null5/audit/beweis_ansatz/blatt_kaufhaus_null5.jpg (A|B|C, Foto 001, zugeschnitten): A ueberzieht die Fassade dicht mit gruenen Treffern (verrauschte Netzkanten), gelb nur in Streifen; B ist fast ganz gelb (glatter LoD2-Kasten ohne Fassade); C hat den Bogenaufbau gruen, rechts die Fassadenflaeche gelb.
- modelle/martinstor/audit/beweis_ansatz/blatt_martinstor.jpg (Foto 002): A (Nordwolke) trifft den Bogen, hat aber viele rote Kanten im Pflaster/Bahngleis (Poisson-Ballon); B (Saeulen) trifft nur senkrechte Kanten; C trifft Torbogen, Uhrenrahmen, Turmkanten, gelb bleibt Mauerwerk-/Putzrelief.
- modelle/martinstor/audit/beweis_ansatz/blatt_synthetisch.jpg und blatt_synthetisch_stark.jpg (Foto 005, A|B|C|W): C und W sind kaum zu unterscheiden (schwach); A hat Turmform und Uhr, aber gezackte Kanten und rote Bodenkante; B ist der Stufenklotz mit gelben Umrissen.

## Nachtest Metrik 2 mit kosten_lr (vorab formuliert, 2026-11-05 19:40)

Test VOR dem Rechnen festgelegt (kein Umdeuten des alten Kriteriums): Metrik 2 mit dem fairen Mass `kosten_lr` (foto_diff, a contrario, lr_mischung; kleiner = besser, <= 0) statt rot/gelb, weil gelb kantenreiche Rauschnetze belohnt. Kriterium: C hat auf den zurueckgehaltenen Fotos im Mittel kleineres kosten_lr als A UND als B bei >= 2 von 3 Objekten UND gepaart je Foto t <= -2 gegen A. Nulllinie: Wahrheit W (synthetisch) muss das kleinste kosten_lr haben, sonst ist auch dieses Mass ungeeignet.
Durchfuehrung: foto_diff je Foto und Modell neu mit `--bewertung-maske` (feste Maske je Foto = B-Silhouette + 3 m, per `--maske-aus` aus dem B-Lauf erzeugt, gleiche Maske fuer A/B/C/W; fuer Kaufhaus NICHT die qualitaetsstufen-Masken, weil nur 001/024/054 vorhanden), sonst Argumente wie im Beweislauf (synthetisch `--tiefen aus`, `--bild`). Per tools/job_start.sh (rcpark-lrnachtest, GPU, 84 Laeufe, 0 Fehler). Ausgabe: /media/oem/scan/rc-park_null/beweis_ansatz/<objekt>/lr/, Tabelle lr_tabelle.json im Beweisordner. Die alten foto_diff-JSONs enthielten kein kosten_lr (neu gerechnet). Die zwei synthetischen Varianten (schwach/stark) werden einzeln gezaehlt, Urteil mit "synthetisch" (schwach) als drittem Objekt; stark ergibt dasselbe.

### kaufhaus_null5

| Foto | lr A | lr B | lr C | param A | param B | param C |
|---|---|---|---|---|---|---|
| 001 | -0.0041 | -0.0009 | -0.0092 | 0.742 | 1.061 | 0.764 |
| 024 | -0.0473 | -0.0001 | -0.0132 | 0.576 | 1.514 | 0.857 |
| 054 | -0.0156 | -0.0048 | -0.0065 | 0.521 | 1.171 | 0.642 |
| 083 | -0.0033 | -0.0028 | -0.0018 | 0.734 | 1.100 | 1.015 |
| 211 | -0.1026 | -0.0067 | -0.0292 | 0.557 | 1.491 | 0.839 |
| 234 | -0.0043 | -0.0009 | -0.0065 | 0.816 | 1.230 | 0.894 |
| Mittel | -0.0295 | -0.0027 | -0.0111 | 0.658 | 1.261 | 0.835 |

C<A False (t=1.49), C<B True (t=-2.41); bestanden(Objekt)=False; kleinstes Mittel: A

### martinstor

| Foto | lr A | lr B | lr C | param A | param B | param C |
|---|---|---|---|---|---|---|
| 002 | -0.0013 | -0.0026 | -0.0018 | 0.834 | 0.966 | 0.839 |
| 017 | -0.0100 | -0.0039 | -0.0082 | 0.953 | 1.069 | 0.996 |
| 027 | -0.0172 | -0.0016 | -0.0037 | 1.070 | 1.317 | 1.151 |
| 051 | -0.0488 | -0.0016 | -0.0101 | 0.967 | 1.229 | 1.273 |
| 108 | -0.0138 | -0.0054 | -0.0065 | 0.975 | 0.975 | 0.997 |
| 136 | -0.0200 | -0.0109 | -0.0212 | 0.985 | 1.120 | 0.941 |
| Mittel | -0.0185 | -0.0043 | -0.0086 | 0.964 | 1.112 | 1.033 |

C<A False (t=1.60), C<B True (t=-2.39); bestanden(Objekt)=False; kleinstes Mittel: A

### synthetisch

| Foto | lr A | lr B | lr C | lr W | param A | param B | param C | param W |
|---|---|---|---|---|---|---|---|---|
| 005 | -0.4385 | -0.0016 | -0.4731 | -0.4841 | 0.806 | 1.670 | 0.658 | 0.643 |
| 015 | -0.5071 | -0.0078 | -0.5297 | -0.5445 | 0.920 | 1.658 | 0.732 | 0.710 |
| 027 | -0.2575 | -0.0635 | -0.2782 | -0.2856 | 1.237 | 1.506 | 1.016 | 1.004 |
| 044 | -0.6238 | -0.0001 | -0.5773 | -0.6160 | 0.781 | 1.790 | 0.655 | 0.616 |
| 078 | -0.5843 | -0.0070 | -0.5984 | -0.6215 | 0.838 | 1.662 | 0.645 | 0.626 |
| 108 | -0.5542 | -0.0046 | -0.5012 | -0.5222 | 0.850 | 1.651 | 0.664 | 0.640 |
| Mittel | -0.4942 | -0.0141 | -0.4930 | -0.5123 | 0.905 | 1.656 | 0.728 | 0.706 |

C<A False (t=0.08), C<B True (t=-8.54); bestanden(Objekt)=False; kleinstes Mittel: W; W Nulllinie kleinstes: True

### synthetisch_stark

| Foto | lr A | lr B | lr C | lr W | param A | param B | param C | param W |
|---|---|---|---|---|---|---|---|---|
| 005 | -0.4344 | -0.0008 | -0.4602 | -0.5099 | 0.779 | 1.667 | 0.689 | 0.647 |
| 015 | -0.5627 | -0.0105 | -0.5501 | -0.5398 | 0.889 | 1.642 | 0.731 | 0.705 |
| 027 | -0.2681 | -0.0290 | -0.2610 | -0.2732 | 1.177 | 1.730 | 1.060 | 1.028 |
| 044 | -0.6921 | -0.0006 | -0.6800 | -0.6918 | 0.749 | 1.768 | 0.607 | 0.594 |
| 078 | -0.5754 | -0.0375 | -0.7267 | -0.7115 | 0.865 | 1.579 | 0.598 | 0.584 |
| 108 | -0.5978 | -0.0257 | -0.5767 | -0.5818 | 0.841 | 1.547 | 0.613 | 0.607 |
| Mittel | -0.5217 | -0.0173 | -0.5424 | -0.5513 | 0.883 | 1.656 | 0.716 | 0.694 |

C<A True (t=-0.77), C<B True (t=-7.63); bestanden(Objekt)=False; kleinstes Mittel: W; W Nulllinie kleinstes: True


### Urteil (Kriterium unveraendert)
NICHT bestanden: C < A im Mittel nur bei synthetisch_stark (-0,542 vs -0,522), und dort t = -0,77 (nicht <= -2); Kaufhaus A -0,030 vs C -0,011 (t +1,49), Martinstor A -0,019 vs C -0,009 (t +1,60): A ist dort besser als C. C < B gilt ueberall (t -2,4 bis -8,5), aber B liegt mit ~0 nur auf Zufallsniveau (glatte Kloetze). Also 0 von 3 Objekten (kein einziges mit t <= -2 gegen A).
Nulllinie bestanden: W hat in beiden synthetischen Varianten das kleinste Mittel (-0,512 / -0,551; vor C -0,493 / -0,542 und A -0,494 / -0,522). Das Mass ist also zumindest auf der Wahrheit brauchbar. Auf synthetisch trennt es C nicht von A (Differenz 0,001-0,02, Streuung gross); kosten_param (Einordnung) hatte dort C 0,73 vs A 0,91 vs W 0,71, also C besser als A, das aber ist das alte, zufallsbelohnende Mass.
Interpretation: rot/gelb-Urteil wird nicht gerettet, sondern von einem unabhaengigen Mass bestaetigt: A (Photogrammetrie) passt in den Foto-Kanten bei den echten Objekten besser als C; das ist das Restfeld (Fassadenrelief) von C. Das Ergebnis traegt keine Aussage "C besser als A in Kanten".

### Bilder (angesehen: foto_diff_<nr>.jpg A und C, Ordner .../lr/{A,C}/<nr>/)
- Kaufhaus 211: A hat viele gruene Kanten, die auf echten Fassadenmerkmalen liegen (Arkadenbogen, Fensterpfeiler, Dachgrat), daneben aber dichte Gruenstreifen im Dach und rund um das Pflaster/Mast (verrauscht, Kanten ueberziehen auch glatte Flaechen: Zufallsanteil sichtbar). C hat saubere, sparsame gruene Gebaeudekanten (Bogen, Pfeiler, Traufe), aber Dach und Fassadenrelief gelb (fehlen im Modell).
- Martinstor 051: A-Gruen liegt ueberwiegend an der Turm-/Torkante und Fenstern, mit Gruenfeldern in der Strassenschlucht und roten Streifen am Dach (Ballon); C ist exakter an Kante und Bogen, bei beiden bleibt Mauer-/Relief-gelb. Hier sind A-Gruen meist echte Kanten, nur weniger genau.
- Synthetisch 078: A-Gruen sind echte Turmkanten (Gesimse, Uhrrahmen, Nadel) plus schwache Zacken am Rand; C sauber, nahe an W; hier ist A fast so gut wie C, was die kleine lr-Differenz erklaert.
Fazit der Sicht: bei A sind die gruenen Kanten ueberwiegend Gebaeudekanten (Kaufhaus teils Rauschen auf Dach/Boden), also ist A bei echten Objekten nicht nur Zufall.
Fehlschlaege/Vorbehalt: keine Laeuferfehler. Maske aus B (nicht Ausgangsmodell des Laeufers) - fuer Kaufhaus ist B = Ausgangsmodell modell_s1, fuer Martinstor/synthetisch DOM1-Saeulen. n = 6 Fotos je Objekt, nicht unabhaengig (gleiche Kamerakette); die A-Wolke benutzt die Fotos mit (Leck, trifft A zugunsten).

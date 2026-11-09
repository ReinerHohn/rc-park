# Logbuch Formfits Kantengitter Kaufhaus (Helme, Gauben, Baluster) - 2026-11-09 abends

Auftrag: drei Formfamilien auf das Kantengitter v7 setzen, jede mit Fotopruefung (Bild angesehen). Daten `/media/oem/scan/rc-park_daten/kaufhaus_alle/`
(Sweep `kanten_tsweep_A2.npz`, Wolke `kanten3d_k80.npz`, Kameras `sfm/kam_lot2.json`, Stabilitaetskarten `stabil/`, Gitter `segmente_gitter_v7.json`).
Ausgabe `formen/gitter_v7_formen.json`, Bilder `modelle/kaufhaus_grob3/audit/formen/`. Begonnen 19:05.

## 1 Kleiner Helm (helm_fit.py verbessern)
- 19:10 Ausgangslage mit A2-Sweep (`formen/helm0.log`): Kandidatensuche findet NUR den grossen Helm (18,3/6,6); Fit Mitte 18,70/6,28, Spitze 22,12, Fuss 15,14 r 0,98,
  Inlier 2374/6112. Der kleine Helm (-4,5/13,5) wird gar nicht Kandidat: im 3-m-Fenster liegt die Dachschraege dahinter, der Kegeltest (oberer Radius < 0,7 unterer) faellt durch.
- Prototyp Ebenen-RANSAC im Umfeld 2,5 m (`scratchpad/proto_ebene.py`): kleiner Helm 39698 Punkte, Ebene 1 n=(-0,18 0,87 0,46) = Dachschraege 34 %, Ebene 2 n=(0,93 0,16 0,32) 30 %
  (zweite Schraege/Dachkehle am Eck), Rest 18164; Radiusprofil des Rests faellt von r 1,0 (z 17-18) auf 0,33 (z 22) und 0,17 (z 23) -> Spitze ~23,3-23,5, Neigung ~0,15.
  Grosser Helm: Ebene 1 = Dachschraege 48 %, Ebene 2 WAAGERECHT z 13,5 (Traufring) 47 % des Rests -> waagerechte Ebenen NICHT entfernen (koennten Fussring treffen): nz auf 0,25..0,9 begrenzt.
- Einbau: `ebene_ransac` + `ohne_dachebene` (bis 2 geneigte Ebenen >= 20 % der Restpunkte, |Abstand| < 0,25 m raus) in Kandidatensuche UND Fit; `spitze_pruefen` projiziert die Spitze
  in alle Fotos, die sie sehen, Kartenwert >= 0,3 im 3-px-Umfeld, bestanden bei >= 3 Fotos; dazu `spitze_foto_max` = hoechste Achsenhoehe mit Kante in >= 3 Fotos (Fahnenstange zaehlt mit, nur Bericht).
  VRAM-Deckel `torch.cuda.set_per_process_memory_fraction(0.18)` (~1,5 GB).
- 19:25 Lauf v1 (`helm1.log`, --zmin 13): jetzt 6 Kandidaten, darunter -3,3/13,6 und -4,3/15,6 (kleiner Helm) - aber ALLE verworfen, auch der grosse (Anteil 0,24):
  der Anteil war Inlier / alle Punkte im 5x5-m-Fenster und haengt damit von --zmin ab (bei 13 statt 15 kommt die ganze Traufe dazu). Fehler im Massstab, nicht im Helm.
  Aenderung: Anteil = Inlier im Helmzylinder (Radius r_fuss+0,3, z_fuss-0,3..z_spitze+0,5) / Punkte im Zylinder (`anteil`), Fensteranteil nur noch Bericht (`anteil_fenster`).
  Ausserdem Ebenen-Neigung auf nz 0,3..0,85 (32-72 Grad) eingeengt: v1 hatte am grossen Helm eine 27-Grad-"Ebene" mit 21656 Inliern durch die dichte Traufzone gefunden.
- 19:17 Lauf v2 (`helm2.log`): kleiner Helm -3,3/13,6 weiter verworfen, Zylinderanteil 0,25 (< 0,3), Sektoren 16 (rund!).
- 19:19 Diagnose v3 (`helm3.log`, feste Zentren): kleiner Helm Mitte -4,10/14,00 Spitze 23,35 Fuss 13,15 r 1,53 k 0,15 (Zyl.-Anteil 0,35, Spitze auf Kante in 4 Fotos = bestanden,
  spitze_foto_max 27,6 = Fahnenstange). Grosser Helm aber Spitze 24,68 Fuss 13,09 r 1,97 k 0,17 statt 22,4/0,86 (Lauf 0): mit --zmin 13 zieht die dichte Traufzone (Tausende Punkte
  bei z 13-14, Zufallstreffer auf dem verlaengerten Kegel) den Kegel breit und hoch; der Fuss (Scheibe > 20 % des Maximums) landet in der Traufzone. SACKGASSE: rohe Inlierzahl ueber ein Band,
  das die Traufe enthaelt. Aenderung v4: Inlier-Gewicht je 0,5-m-Scheibe min(1, 300/n) (--cap), Fuss von oben abwaerts bis die Mantelbelegung (Inlier / Punkte im Zylinder r+0,3) unter 0,25 faellt (--fuss_min).

- 19:27 Lauf v4 (`helm4.log`, automatisch, 5 Kandidaten): kleiner Helm Mitte -3,97/14,38 Spitze 22,06 Fuss 14,68 r 0,89 k 0,12 (Zyl.-Anteil 0,58, Spitze auf Kante in 21 Fotos);
  grosser Helm 18,63/6,28 Spitze 22,44 Fuss 14,12 r 1,08 k 0,13 (0,60; 5 Fotos) = wieder wie Lauf 0. Aber: Nachbarzelle -4,3/15,6 fand den kleinen Helm doppelt, und zwei Fehlfunde:
  3,68/10,23 (k 0,32 = Halbwinkel 18 Grad: Gaube + Dachschraege) und -5,7/9,8 Spitze 29,8 (Staffelgiebel-Kopf, 806 Inlier). Aenderungen: Doppelfund-Abgleich (< 1,5 m, besserer Anteil bleibt),
  --kmax 0,25 (ANNAHME Formklasse Turmhelm: Halbwinkel <= 14 Grad), --minlier 1000.
- 19:31 Lauf v5 (`helm5.log`): 2 echte Helme + Staffelgiebel-Kopf (782 Inlier, faellt mit --minlier; `formen/helme.json` = v5 so gefiltert, Lauf v6 mit dem fertigen Werkzeug laeuft).
  ERGEBNIS: kleiner Helm Mitte -3,97/14,38 Spitze 22,35 Fuss 14,68 r 0,84 k 0,11, Inlier 3355 (Zyl.-Anteil 0,59), Spitze auf Kante in 18 von 201 Sichtfotos;
  grosser Helm Mitte 18,73/6,33 Spitze 22,76 Fuss 14,08 r 0,95 k 0,11, Inlier 2296 (0,60), Spitze auf Kante in 50 von 143 Fotos. spitze_foto_max 25,3/25,7 = Fahnenstange (nur Bericht).
  Overlay 6261 + nu_9e19 ANGESEHEN (`audit/formen/helme_*.jpg`): beide Helme sitzen auf den Spitzen, Spitze am Fahnenfuss, Fussring an der Erkerdachkante; kein Versatz erkennbar.
  Spitzenstreuung v4->v5 am grossen Helm 22,44 -> 22,76 (RANSAC-Ebenen zufaellig; Spitze damit auf ~0,3 m sicher, nicht 10 cm).
- Lauf v6 (fertiges Werkzeug, erst OOM durch fremden 6-GB-Prozess `rcpark-kette_video_alle`, dann Wiederholung mit VRAM-Budget): INSTABIL - grosser Helm diesmal Mitte 18,18/6,83
  Spitze 26,55 Fuss 19,11 (falsch, Staffelgiebel-Stufen neben dem Helm; Zylinderanteil 0,56 trotzdem), kleiner Helm als Kandidat -4,3/13,6 mit Spitze 25,3 verworfen (Anteil 0,15).
  Ursache: Ebenen-RANSAC (4000 Hypothesen, ungeseedet) entfernt je Lauf andere Punkte, die Scheibenkappung (--cap) hebt die oberen Stufenpunkte relativ an -> zweites Optimum.
  Aenderung v7: fester Seed (--seed 0) + 12000 RANSAC-Hypothesen (--ransac_it). Geliefert bleibt `formen/helme.json` = v5 (am Foto geprueft); v7 nur, wenn es v5 bestaetigt.
  Werkzeuge in `tools/gpu_werkzeuge.txt` + `tools/gpu_budget.txt` eingetragen (helm/gauben 1600 MiB Deckel, baluster 700; Spitzen nicht gemessen), damit job_start.sh wartet.
- 19:44 Lauf v7 (`helm7.log`, Seed 0, 12000 Hypothesen, fertiges Werkzeug, vollautomatisch ohne --zentren): BESTAETIGT v5.
  ERGEBNIS (geliefert als `formen/helme.json` = helme_v7.json): kleiner Helm Mitte -3,97/14,38 Spitze 22,34 Fuss 14,67 r 0,84 k 0,11, 3512 Inlier, Zylinderanteil 0,60, Sektoren 16;
  grosser Helm Mitte 18,73/6,33 Spitze 22,78 Fuss 15,09 r 0,85 k 0,11, 2407 Inlier, Anteil 0,68. Nachbarzelle als Doppelfund erkannt, Staffelgiebel-Kopf mit 791 Inliern abgewiesen.
  Overlay 6261 ANGESEHEN: beide Spitzen am Fahnenfuss, Grate auf den Helmflaechen. Offen: Spitzenstreuung ueber Laeufe ~0,3 m; Fuss des grossen Helms 14,1-15,1 je Lauf.

## 2 Gauben (`tools/gauben_fit.py` neu)
- Fotobefund 6261 (Dachausschnitt angesehen) + nu_9e19: kleine GIEBELGAUBEN (Giebelfront mit Fenster, kleines Satteldach, zwei lange Kehlen bis zum Firstende im Hauptdach),
  obere Reihe 2, untere Reihe 3 = 5 Stueck. Primitive daher: First waagerecht vom Scheitel bis in die Dachebene, 2 Ortgaenge, Fronttraufe, 2 senkrechte Frontkanten, 2 Kehlen (8 Kanten).
- Traufe automatisch 14,33 m (Gitter: lange waagerechte Segmente bei z 14,2-14,8; First 26,9-27,5). Dachebenen (RANSAC auf Punkten > Traufe+0,3): zwei fast gleiche Ebenen
  Neigung 52,8/52,1 Grad, n (0,32 0,73 0,61) - beide die Vorderseite (Rueckseite hat kaum Sweep-Punkte); zweite Ebene = Restband derselben Flaeche (unschoen, aber unschaedlich).
- Lauf v1 (`gauben1.log`): 70k Kandidatenpunkte 0,2-1,5 m ueber der Ebene, ~40 Cluster, davon ~25 im Groessenfenster - viel Beifang (Erkerdach, Figuren, Staffelgiebelstufen).
  Fits liefen fast alle auf die Untergrenze Breite 0,4 m -> Laengenstrafe (rho = halbe Gleichverteilungsdichte) viel zu stark (Cluster 2863 Pkt / 2 m² -> 172 Pkt je Kantenmeter Strafe).
  Absturz in der Fotopruefung (np.concatenate statt stack -> Skalar). Beides behoben: rho-Faktor 0,25 (--rho), Fotopruefung als Tor (Kantenbelegung >= 0,4 in >= 3 Fotos, --fotomin),
  Cluster-Dump `OUT.cluster.npz` fuer die Sichtkontrolle.
- Kandidatenpunkte auf 6261 ANGESEHEN (`audit/formen/gauben_kandidatenpunkte_*.jpg`): die Punkte 0,2-1,5 m ueber der Dachebene liegen GENAU auf den 5 Gauben (Kehlen-Dreiecke + Front),
  dazu Staffelgiebelstufen, Fahnenstange, Kamin. Die Dreiecke sind 2,5-3 m lang am Hang -> First ist GENEIGT (flacher als das Hauptdach), ein waagerechter First (Tiefe = h_f/tan) kann
  nicht passen. Modell umgestellt: Tiefe freier Parameter, First vom Scheitel zum Firstende in der Dachebene; Nebenbedingungen Tiefe >= h_f/tan(alpha), h_traufe < h_first.
- Laeufe v2-v4 (`gauben2-4.log`): Fits laufen trotzdem auf Minimalbreite/-hoehe (0,17-0,6 m), Fotopruefung aller echten Gauben 0,1-0,3 Kantenbelegung (durchgefallen), nur Beifang
  "bestanden" (Erkerdach 13,4/9,4, Helm-Nachbarschaft). Overlay v4 auf 6261 ANGESEHEN (`audit/formen/gauben_v4_alle_*.jpg`): Primitive sitzen in der Naehe der Gauben, aber klein und schief.
  Ursache (nach Laengenstrafe-Rechnung): rho skaliert mit TOL - bei --tol 0,25 ist die Strafe wieder ~1 Inlier je Kantenzentimeter, groessere Primitive koennen nie gewinnen. Lauf v5 mit --rho 0,05.
- Lauf v5 (`gauben5.log`, --tol 0,25 --rho 0,05): Primitive jetzt gaubengross (Breite 0,8-1,6, Scheitel +0,7-1,7, Tiefe 1,3-3,2 m), Inlieranteile 0,7-0,95. Overlay 6261 ANGESEHEN
  (`audit/formen/gauben_v5_alle_ip_IMG_6261_dach.jpg`): Primitive liegen auf/neben den 5 Gauben, aber um ~0,3-0,5 m versetzt und zu tief am Hang, Scheitel teils zu weit oben.
  Fotopruefung (Kantenbelegung, 3 px) aller 5 echten Gauben 0,15-0,27 -> durchgefallen; "bestanden" nur Beifang (Erkerdach 13,4/9,4 und 15,4/9,8, Punkt 0,8/15,3 neben dem kleinen Helm).
  STAND: Gauben NICHT abgenommen. Reihen-Gleichheitsregel laeuft, bringt aber ohne richtige Einzelfits nichts.
  Naechster Schritt (nicht mehr geschafft): (a) Fit-Ziel um Foto-Kantenabstand erweitern (Regel 9d) statt nur Sweep-Punkte, denn die Sweep-Punkte an den Kehlen streuen ~0,3 m
  (Cluster-Bild), (b) Kandidatenpunkte nicht auf 0,2-1,5 m ueber der Ebene beschraenken (die Kehlen liegen IN der Ebene, das Firstende auch) - Cluster aus allen Punkten im Umkreis des
  Clusters nehmen, (c) Hauptdachebene ueber die Fotos (Traufe + First aus dem Gitter) statt RANSAC ueber Sweep-Punkte legen.
- Lauf v6/v7 (Schritt b umgesetzt: --alle_punkte 1 = Fit auf allen Sweep-Punkten im Clusterumfeld, -0,3..2,0 m ueber der Ebene; --px 6; v6 OOM -> Blockgroesse nach Punktzahl):
  Masse der echten Gauben jetzt Breite 1,1-1,4, Scheitel +0,6-1,1, Tiefe 2,0-3,4 m, Reihen-Mediane Breite 1,11/1,38, First 1,01/0,94, Tiefe 2,9/3,05. Fotopruefung weiter 0,20-0,34
  (durchgefallen), bestanden nur Erkerdaecher/Beifang. Overlay ANGESEHEN (`audit/formen/gauben_v7_alle_ip_IMG_6261_dach.jpg`): Primitive zu lang, schief, liegen zwischen den Gauben -
  SCHLECHTER als v5. SACKGASSE: Kehlen/First aus Sweep-Punkten in der Dachebene fitten (die Punkte in der Ebene sind Dachkanten aller Art, der Fit haengt sich an die falschen).
  ENDSTAND Gauben: nicht abgenommen. In `gitter_v7_formen_alle.json` liegen die v5-Kandidaten als quelle 14 (unverifiziert) zur Ansicht; Hauptdatei ohne Gauben.

## Ergebnisdateien (Stand 19:50)
- `formen/gitter_v7_formen.json` = v7 + 2 Helme (quelle 4, 32 Segmente), 3057 Segmente. Overlay `audit/formen/gitter_v7_formen_ip_IMG_6261.jpg`.
- `formen/gitter_v7_formen_alle.json` = zusaetzlich Gauben-Kandidaten v5 (quelle 14, 184 Segmente) + 97 Baluster-Instanzen (quelle 13, Score 0,5, 485 Segmente) - beides UNVERIFIZIERT.
- je Form: `formen/helme.json` (= helme_v7), `formen/gauben_v5.json`/`gauben_v7.json`, `formen/baluster.json` (= v12 alle Instanzen), Logs `formen/*.log`.
- Werkzeuge: `tools/helm_fit.py` (erweitert), `tools/gauben_fit.py`, `tools/baluster_fit.py`, `tools/formen_zusammen.py` (neu); GPU-Budgets eingetragen. Keine Commits.

## 3 Baluster (`tools/baluster_fit.py` neu)
- Gitter v7 hat KEINE langen (> 2,5 m) waagerechten Segmente an der Bruestung, nur bei Traufe/First. Kurze (> 0,6 m) waagerechte Segmente buendeln sich aber bei z 7,2-7,4
  (Gesamtlaenge 49 m) und 8,2-8,4 (49 m), Abstand 1,0 m -> Bandsuche als Paar von z-Buendeln (Laengensumme, 0,1-m-Bins, Abstand 0,8-1,2 m, gleiche Lage). Sweep-z-Histogramm an der
  Fassade bestaetigt: Spitzen 7,0-7,4 (Balkonboden/Konsolen) und 8,2-8,3 (Handlauf).
- Lauf v1 (`baluster1.log`): Periode 0,15 = Untergrenze (Randanstieg der Autokorrelation durch Kantendicke, kein echtes Maximum), Profil r 0,03-0,04 = Rauschen; 100 von 186 Instanzen
  "bestanden", weil 3 Zufallstreffer bei ~100 Sichtfotos immer vorkommen. Aenderungen: Periode = staerkstes LOKALES Maximum (2 cm breit), bestanden nur bei >= 30 % der Sichtfotos (--fanteil),
  t-Bereich = Ueberlappung Unter-/Oberkante.
- Lauf v2/v3 (`baluster3.log`): Periode 0,280 m, Profil r 0,059-0,093 m (plausibel), 81 Instanzen, 0 bestanden (Kantenanteil Median 0,00). Overlay auf 6120 ANGESEHEN
  (`scratchpad/bal3_6120_crop.jpg`): die Baluster liegen ein Geschoss zu tief - Band 7,35-8,25 ist Konsolen/Balkonboden, die echte Bruestung liegt zwischen Bodenkante ~8,35 und Handlauf ~9,65
  (Abstand 1,3 m > Grenze 1,2). Stabilitaetskarte 6120 zeigt die Baluster klar. SACKGASSE: Bandwahl nach Gitterlaenge mit festem Abstand 0,8-1,2.
  Aenderung v4/v5: Bandpaare aus lokalen Maxima der Laengensumme (Abstand 0,8-1,5 m, Lage < 6 m), Entscheidung nach PERIODIZITAET der Wolkenpunkte im Band (Autokorrelationsspitze).
- Lauf v5 (`baluster5.log`): Band 8,35..9,65 (Periodizitaet 0,49 gegen 0,0 der Konsolenbaender) = richtig; Overlay 6120 ANGESEHEN: Baluster jetzt in der Bruestung, aber zu dicht:
  Wolkenperiode 0,23 m, am Foto gezaehlt ~10-11 Baluster, wo das Modell 15-17 setzt (~0,30-0,34 m). Wolken-Autokorrelation hat 0,225 und 0,275 gleichauf (0,56) - die Fenstersprossen
  hinter der Bruestung sind ebenfalls periodisch. Lauf v6 (--quer 0,15) und v7 (Fotoguete je Kandidat) entschieden nicht (0,151 gegen 0,148). SACKGASSE: Periode aus der Wolke allein.
- Lauf v8: Periode + Phase aus den FOTOS (`foto_signal`: 3D-Bruestungslinie in 5 Hoehen in 79 Sichtfotos mit >= 60 px/m projiziert, Kartenwert summiert, Autokorrelation):
  Periode 0,287 m (einziges lokales Maximum, 0,41), Phase 0,170 (Asymmetrie 0,018), Profil r 0,065-0,085 m (8 Knoten, jetzt mit Struktur). 97 Instanzen im t-Bereich -14,6..12,8.
  Overlay 6120 ANGESEHEN (`audit/formen/baluster_v8_alle_ip_IMG_6120_crop.jpg`): Abstand stimmt fast (links deckungsgleich, nach rechts laeuft die Phase um ~1/3 Periode weg -
  Periode eher 0,29-0,30; Lag-Aufloesung 1 cm = 3 %), Hoehe/Band stimmen. Fotopruefung mit 3 px: nur 12 Instanzen bestanden (Enden am Erker), Mitte Kantenanteil-Median 0,10:
  Mantellinien eines r-0,07-Zylinders treffen die vasenfoermigen Baluster (r 5-10 cm) nicht auf 3 px (= 4 cm bei 20 m). Lauf v9 mit --px 6 als Vergleich.
- Lauf v9/v10 (--px 6, Driftkorrektur der Periode ueber Phasen links/rechts: 0,287 -> 0,2869, Phase 0,265): Overlay 6120 ANGESEHEN (`audit/formen/baluster_v10_alle_ip_IMG_6120_crop.jpg`):
  jetzt Deckung mit den echten Balustern ueber die ganze sichtbare Bruestung (Abstand, Hoehe, Phase). Trotzdem bestehen nur 30 Instanzen, alle an den ENDEN (t <= -10,4 und >= 9,2 =
  Erkerfronten mit vielen senkrechten Fensterkanten = Fehlfunde), die echten Baluster in der Mitte haben Kantenanteil-Median 0,2.
- v11/v12: Pruefung auf die SILHOUETTE umgestellt (je Foto Achse +- r(z) senkrecht zur Blickrichtung statt 8 fester Mantellinien, von denen hoechstens 2 auf Kanten liegen koennen) -
  Mitte weiter 0,05-0,15. Diagnose direkt auf der Stabilitaetskarte 6120 (`scratchpad/bal_debug_6120_zoom.jpg`, projizierte Silhouettenpunkte auf die Karte gezeichnet):
  Die Karte enthaelt an der Bruestung NUR die Fussbogen/Kappen der Baluster und die Fensterrahmen dahinter - die langen Schaftkanten der Baluster sind in den Stabilitaetskarten NICHT
  vorhanden (instabile Kanten). Kappen-Test (nur unterste/oberste 12 cm) ebenfalls 0,0-0,75 gemischt. BEFUND: Quellen-Blindheit der Stabilitaetskarten fuer Balusterschaefte;
  ein 50-%-Kantentest kann hier nie bestehen, egal wie gut die Geometrie ist. Die Positionen SIND am Foto geprueft - aber durch mich per Overlay, nicht automatisch.
  STAND: Periode 0,287 m, Phase 0,265, Band 8,35-9,65, Profil r 0,065-0,085 (schwach aufgeloest, 2-8 Knoten je Lauf), 97 Instanzen auf t -14,6..12,8 (davon die Enden Erker, keine
  Baluster) - KEINE automatisch fotogeprüfte Anzahl. Die Baluster gehen deshalb nur in `gitter_v7_formen_alle.json` (quelle 13, Score 0,5, unverifiziert), nicht in die Hauptdatei.
  Naechster Schritt: Kantentest gegen die Fotos selbst (Gradient im Original, nicht Stabilitaetskarte) oder Zaehlung per `foto_zaehlung.py` auf 6120 als Z-Protokoll; t-Bereich auf
  die Strecke mit periodischem Fotosignal begrenzen (Erker ausschliessen).

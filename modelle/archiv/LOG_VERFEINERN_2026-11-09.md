# Log Gitter-Verfeinerung gegen Stabilitaetskarten (2026-11-09)

Werkzeug: `tools/gitter_verfeinern.py` (Eigenbau nach SketchSplat/EMAP-Idee: 3D-Segmentendpunkte per Gradient gegen 2D-Distanztransformationen der Kantenkarten in allen sehenden Fotos; danach Topologie).
Eingang: `segmente_gitter_v7.json` (3041 Segmente), `sfm/kam_lot2.json` (440 Fotos, alle mit Stabilitaetskarte), Wolke `kanten3d_k80.npz` (1,83 Mio Punkte) fuer den Z-Puffer.
Ausgaben: `/media/oem/scan/rc-park_daten/kaufhaus_alle/verfeinern/` (gitter_v8.json, Logs), Bilder `modelle/kaufhaus_grob3/audit/verfeinern/`.

## Basis v7 (selbst gemessen, Job rcpark-verf_v7basis)
- gitter_naehe gegen ref_wolke_kanten.npy: Abdeckung z<12 **0,90**, 12-15 **0,82**, >15 0,18; Treffer 0,29 / 0,48 / 0,02.
- gitter_pruefblatt (--k 12, --wolke): 419/440 Fotos mit Gitter, Stuetzung **Mittel 0,469, Median 0,521**, Q10 0,109. Blatt: `audit/verfeinern/pruefblatt_v7.jpg`.

## Entwurfsentscheidungen
- DT-Karten auf der GPU als **uint8** (Distanz x10, Deckel 20 px -> 0..200), nicht float16: 440 Karten a 1500x2000 = 1,3 GB uint8, float16 waeren 2,6 GB > Budget 2 GB. Abtastung per grid_sample bilinear nach float-Wandlung je Foto.
- Sehendes Foto = >= 12 der 24 Abtastpunkte im Bild, vor dem Wolken-Z-Puffer (Logik aus gitter_pruefblatt.py, 1/4 Aufloesung, 3x3-Splat, 9x9-Lochfuellung), Mittelpunkt < 40 m. Sichtmaske wird VOR der Optimierung einmal berechnet und festgehalten (Verschiebung <= 15 cm aendert Sicht kaum).
- Verschiebungsgrenze hart per tanh-Reparametrisierung (p = p0 + 0,15 m * tanh(d)); Winkelgrenze 5 Grad als quadratische Strafe (1 Grad zu viel = 2 px), Winkel per atan2 (acos hat bei 0 Grad unendlichen Gradienten).
- Verlust in Pixeln (nicht Metern): nahe/hochaufgeloeste Fotos wiegen mehr - gewollt, sie sind genauer.
- (c) Stuetzung je Foto = Median der Distanz der sichtbaren Abtastpunkte <= 4 px (Median statt Mittel: teilverdeckte Segmente nicht faelschlich loeschen).
- Alle uebrigen Schluessel der Eingabedatei (historie, boegen, helme, saeulen, zurueck) werden durchgereicht; neuer Schluessel `verfeinerung`.

## Lauf-Protokoll
- Rauchtest 40 Fotos / 5 Schritte: 5,7 s, 56 657 Sichtpaare, Distanz 5,22 -> 5,07 px, (a) 1397 Endpunkte verschmolzen (822 Gruppen; v7 hat viele exakt gemeinsame Ecken), (b) 182 vereint, (c) 157 geloescht.
- Vollauf 1 (440 Fotos): **OOM bei 1,95 GB** im ersten Schritt. Ursache: grid_sample haelt je Foto die nach float gewandelte Karte (12 MB) im Autograd-Graphen, 440 Fotos = 5 GB. Nicht die uint8-Karten (1,18 GB).
  Fix: Gradienten-Akkumulation in Foto-Chunks (24 Fotos je backward), Winkelstrafe separat. Log `verfeinern/lauf_v8_oom.log`.
  Vorab-Zahlen Vollauf: 337 153 Sichtpaare, 3021/3041 Segmente mit >= 1 sehendem Foto, Median 127 Fotos je Segment, Startdistanz 5,56 px (laengengewichtet 6,84 px).
- Vollauf 2 (v8, maxshift 15 cm, 60 Schritte, Job rcpark-verf_v8): Optimierung 35 s, gesamt 57 s. Distanz 5,56 -> 4,82 px; Verschiebung Median 6,8 cm, Q90 11,0 cm, max 15,7 cm.
  (a) 1793 Endpunkte verschmolzen (856 Gruppen), 6 entartet; (b) 552 vereint -> 2483; (c) 115 geloescht (129 geschuetzt, 24 ohne Fotos behalten); Ergebnis 2368 Segmente, Laenge 2577 -> ~2050 m.
  Tor (b) Pruefblatt: Mittel 0,469 -> **0,516**, Median 0,521 -> **0,589**, Q10 0,109 -> 0,134 (416/440 Fotos). BESTANDEN.
  Tor (a) Naehe: Abdeckung z<12 0,90 -> **0,86**, 12-15 0,82 -> **0,75**. NICHT bestanden (-4 / -7 Punkte).
  Sichtbefund Overlay IMG_6120/6261 v7 vs v8: Fensterreihe weniger Doppellinien, Balkonlinie glatter; ABER die Pfeiler-Kaefige (Quelle 7, Achteckprismen) sind
  verzerrt (Ringe gestaucht, Vertikalen gespreizt), weil jedes Segment der Form einzeln wanderte. -> Fix: Quelle 4/7 in der Optimierung EINFRIEREN
  (nicht nur vor Loeschen schuetzen), in (a) rasten fremde Endpunkte auf Form-Endpunkte ein, in (b) Formen nie vereinen.
- Diagnose-Varianten (Job rcpark-verf_var, Formen noch nicht eingefroren), Abdeckung z<12 / 12-15 | Stuetzung Mittel / Median:
  | Variante | Verschiebung Median | Abdeckung | Stuetzung |
  |---|---|---|---|
  | v7 | - | 0,90 / 0,82 | 0,469 / 0,521 |
  | nur Topologie (0 Schritte) | 0 | 0,89 / 0,82 | 0,471 / 0,531 |
  | nur Optimierung 15 cm | 6,7 cm | 0,87 / 0,76 | 0,523 / 0,616 |
  | nur Optimierung 5 cm | 3,4 cm | 0,89 / 0,80 | 0,504 / 0,582 |
  | Optimierung 5 cm + Topologie | 3,4 cm | 0,89 / 0,80 | 0,497 / 0,568 |
  | Optimierung 8 cm + Topologie | 4,6 cm | 0,88 / 0,78 | 0,500 / 0,579 |
  Befund: der Abdeckungsverlust kommt aus der VERSCHIEBUNG, nicht aus Verschmelzen/Loeschen. Mittlerer Verschiebungsvektor (-0,7, -1,1, +0,4) cm = kein systematischer
  Rahmenversatz Kameras/Wolke. "Treffer" (Segment -> Wolkenkante) steigt, "Abdeckung" (Wolkenkante -> Segment) faellt: Doppellinien rasten auf EINE Kante, die
  zweite Wolkenkante verliert ihr Segment. Die Pixel-Verlustfunktion kennt keine "Zugehoerigkeit" zu einer bestimmten Kante - bekannte Schwaeche der DT-Methode.
  Diagnose je Segment (indexgleich v7 -> nur Optimierung, Treffer-Anteil der 5-cm-Stuetzpunkte < 10 cm zur Referenz): 15 cm: 555 Segmente besser, 101 schlechter,
  11 "vorher nah, jetzt fern"; 5 cm: 356 besser, 61 schlechter, 4 abgewandert. Verschiebung ueberwiegend SENKRECHT zur Segmentachse (Median 2,3 cm senkrecht vs 0,9 cm laengs
  bei 5 cm) = echte Lagekorrektur quer zur Kante, kein Rutschen entlang der Linie. Der Abdeckungsverlust ist also grossteils ein Toleranz-Randeffekt (Referenzpunkte 5-10 cm
  von Segment entfernt fallen nach 7 cm Verschiebung aus der 10-cm-Toleranz), nicht Abwandern ganzer Segmente.
  Entscheidung: Standard maxshift = 0,05 m (einziger Wert, der Tor (a) haelt: -1 / -2 Punkte). Topologie kostet ~1 Punkt Stuetzung (Vereinen/Verschmelzen aendert die Abtastung).

## Endlauf v8 (maxshift 5 cm, Formen Quelle 4/7 eingefroren, Job rcpark-verf_v8, 19:25)
- Laufzeit 59,7 s gesamt (DT 4 s, Sichtbarkeit 9 s, 60 Schritte 40 s, Topologie 5 s); VRAM ~1,4 GB (Karten 1,18 GB uint8 + Chunk-Graph).
- Optimierung: Distanz 5,56 -> 5,17 px; Verschiebung Median 3,4 cm, Q90 4,4 cm, max 5,1 cm; Winkelstrafe blieb ~0 (max 5,4 Grad).
- Topologie: (a) 1667 Endpunkte verschmolzen (872 Gruppen), 4 entartete entfernt; (b) 338 vereint; (c) 129 geloescht (150 geschuetzt, 22 ohne Fotos behalten).
  3041 -> **2570 Segmente**, Laenge 2577 -> 2123 m. Quellen nachher: 0:1590, 8:576, 7:168 (unveraendert), 9:133, 5:76, 4:16 (unveraendert), 6:11.
- **Tor (a)** Naehe ref_wolke_kanten: Abdeckung z<12 **0,89** (v7 0,90), 12-15 **0,80** (v7 0,82), >15 0,18 (0,18). BESTANDEN (-1 / -2 Punkte, Grenze 2).
- **Tor (b)** Pruefblatt: Stuetzung Mittel **0,497** (v7 0,469), Median **0,568** (v7 0,521), Q10 0,112 (0,109), 416/440 Fotos. BESTANDEN.
- **Tor (c)** Sichtbefund `audit/verfeinern/overlay_v7_*.jpg` vs `overlay_v8_*.jpg`:
  IMG_6120 (Front nah): Pfeiler-Kaefige jetzt unveraendert sauber (Freeze wirkt; in der 15-cm-Version ohne Freeze verzerrt, archiviert als overlay_v8_s15_*).
  Fensterreihe: weniger parallele Doppellinien an den Fensterrahmen (Vereinen 338 + Verschmelzen), Balkon-/Brüstungslinie durchgehender. Unveraendert: Linien-Knaeuel
  an den Figuren-Konsolen oben (viele kurze Horizontale, Quelle 0) und einzelne schraege Streusegmente im linken Gewoelbe - die Verfeinerung verschiebt nur <= 5 cm und
  loescht nur bei Stuetzung < 30 % der Fotos; diese Segmente liegen offenbar in genug Fotos auf irgendeiner Kante.
  IMG_6261 (Gesamtansicht): Fensterzeile ruhiger (ausgeduennte Doppellinien), Erker/Helm/Staffelgiebel unveraendert, Kaefige intakt. "Ecken geschlossener" ist in
  1200-px-Overlays nicht sicher zu beurteilen; messbar ist es ueber 1667 verschmolzene Endpunkte (vorher < 6 cm auseinander).
  Pruefblatt v8 (12 Vertreter): Punkte liegen auf den Kanten, Kaefige intakt; schwach bleiben die Gewoelbe-Innenansichten (IMG_6182 0,22, v7 0,20; IMG_6185 0,07) -
  Rippen nur teilweise getroffen, das ist ein v7-Problem (fehlende Segmente), keine Verfeinerungsfrage.
- Archiv: 15-cm-Lauf ohne Freeze `verfeinern/gitter_v8_s15_ohnefreeze.json` (Stuetzung 0,516/0,589, Abdeckung 0,86/0,75 - Tor a verfehlt, Kaefige verzerrt).

## Offen / naechste Schritte
- Pixel-DT kennt keine Kantenzugehoerigkeit: bei > 5 cm Spielraum rasten Doppellinien auf eine Kante. Besser: je Segment die Zielkante im Startbild festhalten
  (Richtungs-/Orientierungs-DT: nur Kantenpixel mit aehnlicher Richtung zaehlen) oder Verlust auf Kantenorientierung konditionieren - dann waere 15 cm vertretbar.
- Formen (4/7) als starre Gruppe mit 6 DoF mitoptimieren statt einfrieren.
- Verlust in Pixeln bevorzugt nahe Fotos; Alternative metrisch (px * z / f) testen.
- Diagnose-Skript (Verschiebung/Trefferwechsel je Segment) liegt nur im Scratchpad; bei Bedarf als tools/gitter_shift_diag.py uebernehmen.

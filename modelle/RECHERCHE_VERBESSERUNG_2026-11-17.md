# Recherche: Verbesserungspotenzial der Methode "Wandbild = Bauplan" gegen den Stand der Technik (17.11.2026)

Auftrag: nur lesen und recherchieren, kein Code. Grundlage: CLAUDE.md, PIPELINE_FASSADEN.md (bis Runde 3 Kaufhaus),
NICHTS_GEBRACHT.md, LIZENZ_WERKZEUGE.md, VERSUCHSREGISTER_MARTINSTOR.md und die frueheren RECHERCHE_*.md (Kanten/Kurven, Splatting
und Fusion sind dort schon breit behandelt; hier steht nur Neues oder eine neue Lesart).
Kennzeichnung: "geprueft" = Repo-Seite oder Modellkarte in dieser Sitzung gelesen; "Treffer" = nur ueber Suchtreffer oder
Drittseiten; "Wissen" = aus dem Gedaechtnis, nicht nachgesehen. Keine Rechtsberatung, LICENSE vor Einsatz selbst lesen.

## Kurzfazit
- Der groesste Rueckstand liegt nicht bei einem einzelnen Werkzeug, sondern bei drei Schritten zwischen den Werkzeugen:
  (1) feine Ausrichtung der Einzelfotos im Wandbild (Restversatz 1-3 cm bei 1-cm-Raster = Unschaerfe und Naehte),
  (2) Tiefe je Zelle aus gelerntem Multi-View-Stereo statt COLMAP-PatchMatch mit Fusion (59-73 % Loecher),
  (3) Massstab des Mono-Reliefs aus echten Mehrbild-Punkten statt aus dem Scan-Bandpass.
- Bei Drähten ist die Ursache vor allem die Aufnahme (alle Fotos vom selben Standort), nicht die Software. Wer ein paar Fotos
  mit Basislinie hat, kann den Draht mit dem vorhandenen Median-Verfahren wegrechnen (Rechnung unten).
- Kurven/Masswerk: Die Literatur 2023-2025 (NEF, EMAP, EdgeGaussians, SketchSplat, CurveGaussian) arbeitet im Kern wie unser
  Kanten-Tiefen-Sweep. Der Engpass bei uns sind die Fotos (Fernfotos, Rippen wenige Pixel breit), kein fehlendes Verfahren.
- Bewertung: Unser Tor-System (Holdout, Nullkontrollen, Zufallsverschiebung) ist strenger als das, was die meisten Arbeiten
  zeigen. Es fehlt ein Mass, das Relief gegen Schattierung prueft, und eine Vorschau, was davon den Druck ueberlebt.

## A. Wandbild und Verdeckung (Fusion der Fotos)

### A1. Dichte Feinausrichtung nach der Homographie (optischer Fluss / Color-Map-Optimierung)
- Was: Nach der Homographie im Ortho-Raum je Foto ein glattes Verschiebungsfeld gegen das Bezugsfoto schaetzen (z. B. OpenCV DIS-Flow
  oder RAFT) und anwenden; Gegenstueck in der Literatur ist die Farb-/Kamerakarten-Optimierung beim Texturieren (Zhou & Koltun 2014
  "Color Map Optimization", in Open3D enthalten; Waechter et al. 2014 "Let There Be Color!", MVS-Texturing). Beides: Wissen.
- Schwaeche: "Restversatz 1-3 cm" im feinen Bild (PIPELINE_FASSADEN), Geister und Naehte, Parallaxe vorspringender Teile
  (die Homographie passt nur auf eine Ebene; die Bogenkontur BS9 war "zerschmiert/verschoben").
- Lizenz: OpenCV DIS-Flow Apache-2.0 (ist installiert); Open3D MIT; RAFT BSD-3 (Wissen, ungeprueft).
- 8 GB: DIS laeuft auf CPU in Sekunden je Bild; RAFT passt auf 8 GB bei Kacheln (Wissen).
- Aufwand: klein (ein Schritt in fassade_fein.py nach dem Homographie-Zug; Glattheit gross waehlen, damit Draehte/Passanten
  nicht "angezogen" werden; Fluss nur dort, wo das Foto mit dem Median uebereinstimmt).
- Register: nicht vorhanden. BS3a (2D-Versatzkompensation fuer Kamerakosten) ist etwas anderes (Kamera, nicht Wandbild).

### A2. Verdeckung durch Basislinie statt durch Software (Draehte, Oberleitung)
- Was: Ein Draht im Abstand d vor der Wand verschiebt sich im Wandbild zwischen zwei Standorten mit Basislinie b um etwa
  b * d / (D - d) (D = Abstand Kamera-Wand). Beispiel d = 3 m, D = 20 m, b = 1 m: 0,18 m Versatz, viel mehr als die Drahtbreite
  (1-2 cm). Mit >= 3 Fotos, deren Standorte >= 0,5-1 m auseinander liegen, faellt der Draht im vorhandenen Median heraus (das Prinzip
  "was vor der Wand steht, wandert" steht schon in PIPELINE_FASSADEN). Klassischer Beleg fuer Median plus Inpainting bei
  Mehrheitsverdeckung: Korah & Rasmussen 2007 (Treffer, IEEE-Eintrag), Hammoudi et al. 2012 (Treffer).
- Schwaeche: Draehte vor der Wand (alle Fotos vom selben Standort), Rest-Grat im Mono-Relief.
- Lizenz: entfaellt (Aufnahme). Aufwand: klein; braucht einen Fotoauftrag (`tools/foto_auftrag.py` mit "Standort seitlich
  versetzt um 1 m, 3 Fotos").
- LaMa (Inpainting, Apache-2.0 laut Drittseiten und OpenCV-Port, Treffer): nur fuer das Anzeige-/Erkennungsbild, nie fuer Relief
  oder Masse (erfundene Pixel; BS27 zeigte, dass Telea-Fuellung schon einmal als Messung missverstanden wurde).
- Register: draht_linien + weiche Maske sind gebaut (17.11.); Telea-Fuellung des Hochpasses als Sackgasse vermerkt.

### A3. Gradientenbasiertes Zusammenfuegen von Relief-Feldern (Poisson-Blending)
- Was: Felder (fein/grob/mono) nicht ueber 3 Zellen Uebergang mischen, sondern im Gradientenbereich zusammensetzen und die Hoehe
  per Poisson-Gleichung loesen, verankert am Tiefpass des Scans (Perez et al. 2003, Wissen).
- Schwaeche: Naehte zwischen Relief-Feldern, "Rillen an den Feldraendern" (Nachtrag 17.11.).
- Lizenz: eigener Code (scipy). 8 GB: unkritisch. Aufwand: klein.
- Register: nicht vorhanden (relief_mischen.py mischt im Wertebereich).

## B. Tiefe je Zelle (Feinrelief)

### B1. Gelerntes Multi-View-Stereo statt PatchMatch in tiefe_lokal.py
- Was: Netze, die je Referenzbild eine Tiefenkarte aus N Nachbarbildern mit bekannten Kameras rechnen; stark bei schwacher
  Textur und kleinen Schnittwinkeln.
  - MVSFormer++ (ICLR 2024, https://github.com/maybeLx/MVSFormerPlusPlus, Paper https://arxiv.org/pdf/2401.11673):
    Apache-2.0 (geprueft, Repo-Seite), eigene Daten ueber COLMAP -> colmap2mvsnet.py (geprueft), Bildgroesse durch 64 teilbar.
    Speicher laut Paper 5964 MB bei 1152 x 1536 (gemessen auf A6000) -> auf 8 GB wahrscheinlich bei dieser Groesse, eher nicht bei
    3200-4000 px; Kacheln/Ausschnitte noetig (unsicher). Gewichtslizenz separat pruefen (Backbone DINOv2 = Apache).
  - GeoMVSNet (CVPR 2023, https://github.com/doubleZ0108/GeoMVSNet): Apache-2.0 (geprueft), eigene Daten "TODO" im README.
  - MVSAnywhere (CVPR 2025, https://github.com/nianticlabs/mvsanywhere): README "non-commercial use" (geprueft) -> nur Test.
  - MonoMVSNet (ICCV 2025, mono-gefuehrtes MVS, Treffer): Lizenz nicht geprueft.
- Schwaeche: 59-73 % Loecher, Figur ueber dem Nordtor nicht sichtbar (NICHTS_GEBRACHT 16.11.: "Tiefenkarten direkt statt Fusion -
  nicht probiert"), Fugen nur im Mono-Relief.
- Aufwand: mittel (Umwandlung der Teilbuendel aus tiefe_lokal.py, Ausschnitt auf das Feld, Tiefenbereich aus dem Netz +-0,5 m).
- Grenze ehrlich: Bei 15-25 m Abstand und ~1 cm je Pixel bleibt die Aufloesung fotobegrenzt; das Netz fuellt Loecher, es erfindet
  keine Fugen, die die Fotos nicht trennen. Fuer Figuren bleiben Nahfotos der staerkste Hebel.
- Register: nicht vorhanden.

### B2. Mono-Tiefe mit Mehrbild-Skalierung (Detail-Prior)
- Was: Monokulare Tiefe liefert die Form, Mehrbildpunkte liefern Massstab und Lage. Stand der Technik: "Prior Depth Anything"
  (arXiv 2505.10565, 2025) und "Any2Full" (arXiv 2603.05711, 2026; Code github.com/zhiyuandaily/Any2Full) konditionieren das
  Mono-Netz direkt auf duenne metrische Tiefe (beide Treffer, Lizenz nicht geprueft).
- Unser Stand: relief_aus_fotos_mono.py skaliert je Kachel ueber die Streuung des Scan-Bandpasses 2-60 cm und verschiebt die Lage
  am Scan. Das ist konzeptionell dasselbe, aber der Anker ist die dichte Wolke (Brei) und die Fugentiefe heisst ANNAHME.
- Verbesserung ohne neues Modell: Anker = Punkte aus tiefe_lokal (oder B1), Fit je Kachel als robuste affine Abbildung
  (a * mono + b, Huber) nur auf gueltigen Punkten; wo keine Punkte sind, bleibt der Scan-Anker. Damit wird die Fugentiefe gemessen
  statt angenommen, wo Feinpunkte vorhanden sind.
- Modelle (frei): Depth Anything V2 Small (im Einsatz), Depth Anything 3 Base/Small (Apache-2.0 laut HF-Modellkarte DA3-BASE,
  Treffer; DA3 hat zusaetzlich einen Mehrbild-Modus mit Kamerastrahlen - ob er bekannte Posen als Eingabe nimmt, ist UNSICHER),
  MoGe-2 (Code MIT laut README, Gewichte moge-2-vitl-normal MIT laut HF-Modellkarte, geprueft). NC: DA2 Base/Large, MVSAnywhere,
  Metric3D (widerspruechlich).
- Schwaeche: Fugentiefe = ANNAHME, Relief aus Farbe (NICHTS_GEBRACHT 11.11.: Mono als metrische Hoehe erfindet 4 cm auf glattem
  Traeger).
- 8 GB: ja (Small/Base fp16). Aufwand: klein (Fit) bis mittel (Modellwechsel).
- Register: DA2-Small als Hoehenquelle fuer Rippen verworfen (11.11.), als Hochpass mit Scan-Anker angenommen (17.11.).

### B3. Feed-forward-Rekonstruktion (VGGT, MapAnything, MASt3R, Pi3)
- Einschaetzung: fuer Feinrelief nicht der richtige Hebel. Diese Modelle rechnen mit ~500 px Eingabe und liefern Geometrie im
  Zentimeter- bis Dezimeterbereich; VGGT war "fuer Masse ausgereizt" (Register G0). MapAnything (Apache-Gewichte
  `map-anything-apache`, Treffer) kann bekannte Posen und Intrinsik aufnehmen und auch Tiefenvervollstaendigung - als
  Lueckenfueller fuer ungesehene Seiten denkbar, nicht fuer Fugen. Niedrige Prioritaet.

## C. Normalen und Schattierung (Steinrelief)

### C1. Normalen aus Einzelfotos, im Wandrahmen ueber die Fotos vereint, dann integriert
- Was: Normalenkarte je entzerrtem Foto (MoGe-2-normal, MIT; StableNormal, Code Apache-2.0 laut Repo, geprueft, aber Basis
  Stable Diffusion, Gewichtslizenz offen), mit der Kameradrehung R in den Wandrahmen drehen, Median ueber Fotos, dann zu Hoehe
  integrieren (Poisson oder bilaterale Normalenintegration BiNI, ECCV 2022, github.com/xucao-42/bilateral_normal_integration,
  Lizenz NICHT geprueft; Milano et al. ICCV 2025 Normalenintegration, Code GPL-3.0 laut Gitee-Spiegel -> nur Test).
  Integration verankert am Tiefpass des Scans/der Feinpunkte.
- Warum besser als Mono-Tiefe: Normalen sind lokal, unabhaengig vom Massstab und streuen zwischen Fotos weniger; Drähte und
  Farbflecken wirken weniger als Tiefensprung (UNSICHER, nicht gemessen).
- Schwaeche: Fugen, Bossen, Bogensteine; Relief aus Farbe (teilweise).
- 8 GB: MoGe-2 ViT-L fp16 vermutlich ja (unsicher); ViT-B/S-Varianten existieren als ONNX-Spiegel (Treffer).
- Aufwand: mittel. Register: DSINE als NC geprueft und nicht benutzt; MoGe-2 als "Kandidat" vermerkt, Installation offen.

### C2. Multi-View-Photometric-Stereo / Shape-from-Shading unter Tageslicht
- Was: Relief aus Helligkeitsverlauf bei bekannter oder geschaetzter Lichtrichtung; mit Fotos zu verschiedenen Sonnenstaenden
  echtes Photometric Stereo. Belege: Li et al. 2011 / Yu et al. 2013 (Outdoor-PS, Treffer), Laurent et al. ISPRS 2024
  (Mehrbild-Mehrlicht fuer archaeologisches Relief, Licht aus der Szene geschaetzt,
  https://isprs-archives.copernicus.org/articles/XLVIII-2-W8-2024/289/2024/), RNb-NeuS 2024 (https://arxiv.org/pdf/2312.01215v2,
  braucht Normalen aus Labor-PS, fuer uns unpassend).
- Einschaetzung: Theoretisch der richtige Weg gegen "Relief aus Farbe" (Albedo bleibt, Schatten wandern mit der Sonne), praktisch
  nur, wenn dieselbe Wand an mehreren Tageszeiten fotografiert ist. Ob der Bestand das hergibt, ist UNGEPRUEFT (EXIF-Zeit je
  Wand auszaehlen). Albedo/Schattierung per Netz trennen (Careaga & Aksoy 2024, github.com/compphoto/Intrinsic) ist laut Repo
  "academic use only" (Treffer) -> nur Test.
- Aufwand: gross. Register: nicht vorhanden. Empfehlung: erst EXIF-Zeiten zaehlen, sonst lassen.

## D. Linien und Kurven (Masswerk, Rippen)
- Bereits recherchiert (RECHERCHE_KANTENGITTER_NEU, KANTEN_MULTIVIEW, DRAHTGITTER 9.11.): NEF (CVPR 2023), EMAP (MIT-Mehrheit,
  Basis ungeprueft), EdgeGaussians, SketchSplat (2025, Lizenz nicht belegt). Neu gefunden: CurveGaussian (arXiv 2506.21401, 2025):
  parametrische Kurven einstufig direkt gegen 2D-Kantenkarten optimiert; Code/Lizenz NICHT gefunden (Projektseite lieferte 404).
- LIMAP lief schon (BS61, BS65: Rauschboden; 9.11.: Linien liegen nicht auf sichtbaren Kanten).
- Einschaetzung: Unsere zweistufige Kette (Stabilitaetskarte -> Tiefen-Sweep -> Segmente) entspricht NEF/EMAP. Der fehlende Teil
  ist die einstufige Optimierung von Kurven-Kontrollpunkten gegen die Kantenabstandsfelder ALLER Fotos (SketchSplat/CurveGaussian-
  Prinzip, nachbaubar ohne fremden Code: Bezier-Punkte projizieren, Abstandstransformation der Kantenkarte als Verlust, torch).
  Ob `tools/gitter_kurven.py` das schon tut, bitte pruefen. Gewinn haengt an Nahfotos der Erker (AUFNAHMEPLAN_ERKER_RIPPEN.md);
  aus Fernfotos (Rippen 3-5 px) wird keine Methode Masswerk machen.
- Aufwand: mittel. Lizenz: eigener Code.

## E. Freistehende Teile (Saeulen, Bruestung, Figuren)
- 2DGS ist in gsplat (Apache-2.0, ab 1.4, Treffer: radiancefields.com) enthalten; PGSR, GOF, Original-2DGS, MILo sind NC.
- Register: 3DGS/2DGS als Netzquelle fuer das ganze Gebaeude verloren (BR, kosten_lr -0,06 vs -0,104; "uneinheitliche Fotos,
  Ueberanpassung").
- Neue Lesart: nicht als Gebaeudenetz, sondern lokal fuer ein freistehendes Teil mit Masken (SAM 2, Apache) und nur den Fotos, die
  das Teil rundum sehen. Die Ursache des alten Verlusts (uneinheitliche Fotos) gilt dort genauso -> niedrige Prioritaet, nur wenn
  >= 8 Fotos rund um ein Teil existieren. Fuer Saeulen genuegt meist Rotationskoerper aus Silhouetten mehrerer Ansichten
  (eigener Code, Fotokanten-konform).

## F. Bewertungsmasse fuer Feinteile
- Vorhanden: foto_diff, Foto-F1 (teil_fotoform), f1_fein, feinteil_tor (Strukturtensor, Nullkontrollen). Grenze laut Runde 3:
  Brei bekommt Punkte, wo das Foto Feinstruktur hat.
- F1. Schattierungstor ("relit NCC"): Modell als Lambert-Bild unter einer je Foto geschaetzten Lichtrichtung (3 Parameter,
  Fit auf grossen Flaechen) rendern, je Kachel normierte Korrelation mit dem Foto-Graubild im Feinband. Brei erzeugt zufaellige
  Schattierung und korreliert nicht; flaches Modell korreliert nicht; richtiges Relief korreliert. Das trennt genau den Fall, an
  dem feinteil_tor scheitert (UNSICHER bis gemessen). Eigener Code mit vorhandenem Rasterer (render_kern.py). Aufwand klein.
- F2. LPIPS/DISTS auf Normalen- oder Schattierungsrendern: LPIPS (richzhang/PerceptualSimilarity, BSD-2, Wissen, ungeprueft).
  Gelernte Wahrnehmungsmasse reagieren auf Textur -> gleiche Brei-Gefahr wie feinteil_tor; nur zusammen mit Nullkontrollen.
- F3. Gerichteter Kanten-Chamfer (Richtung + Abstand, beidseitig) statt F1 mit Toleranz: gibt einen Wert in Zentimetern statt einer
  Trefferquote; leicht aus vorhandenen Kantenkarten (Wissen; im Register als "CMA-ES + Chamfer" schon empfohlen, BS25).
- F4. Druckvorschau-Tor: Hoehenbild mit Duesenradius morphologisch oeffnen (0,4-mm-Duese = 35 mm am Original, 0,2 mm = 17 mm;
  Schichthoehe 0,08-0,12 mm = 7-10 mm) und feinteil_tor/F1 auf dem "gedruckten" Relief rechnen. So sieht man vor dem Druck,
  welche Fugen ueberleben. Eigener Code, klein.

## G. Druckaufbereitung kleinster Details
- Fakt aus der Massstabsrechnung: 1 cm am Original = 0,115 mm bei 1:87. Fugen von 1-2 cm Breite und 1-3 cm Tiefe liegen unter einer
  FDM-Spur (0,2-0,45 mm) und unter der Schichthoehe; sie erscheinen nur als Schattenkante, wenn sie verbreitert oder vertieft werden.
- Praxis im Modellbau (Wissen, keine Quelle gesucht): Relief bewusst ueberhoehen bzw. Fugen auf Mindestbreite setzen
  ("Mindest-Feature" je Duese), Steinplatten flach drucken (habt ihr), Feinteile als Klipsteil auf der feineren Duese.
  Ueberhoehung ist eine Gestaltungsentscheidung des Nutzers und muss als ANNAHME mit Faktor im Modell stehen; Sollwerte nicht still
  aendern.
- Vorschlag: Mindestbreite/Mindesttiefe je Drucker als Parameter in bausatz.sh, gesteuert durch F4 (nur Fugen, die im Foto belegt
  sind, werden auf das Druckminimum gebracht).

## Rangliste: die 5 vielversprechendsten Schritte mit kleinem Test

1. Dichte Feinausrichtung im Wandbild (A1, klein, lizenzfrei).
   Test: Schwabentor Suedwand, feines Bild aus fassade_fein.py einmal wie bisher, einmal mit DIS-Fluss nach der Homographie
   (Fluss nur, wo das Foto mit dem Median uebereinstimmt; starke Glaettung). Tor: Median der Restverschiebung gegen das Bezugsfoto
   (heute 1-3 cm) sinkt unter 1 cm; Gradientenenergie im Feinband steigt; danach Mono-Relief neu und Fugen-F1 gegen Holdout 113836
   (heute 0,417, Zufall ~0,28) darf nicht fallen und soll steigen. Nullkontrolle: Fluss auf einem Foto mit sichtbarem Baum darf den
   Baum nicht "einziehen" (Abdeckungsbild ansehen).

2. Gelerntes MVS im Feinfeld (B1, mittel, MVSFormer++ Apache).
   Test: Schwabentor Nordwand unten (Feld u 0,1-12,05, z 0-10,5), dieselben Fotos wie tiefe_lokal Lauf 2, Bildgroesse so, dass
   VRAM < 7 GB (zuerst 1152 x 1536, dann Kacheln). Tor: Lochanteil im Feld < 59 % (Lauf 2), Abstand zu den COLMAP-Punkten dort, wo
   beide Werte haben, Median < 1 cm; Fugen-F1 gegen ein Holdout-Foto ueber Zufall. Job ueber job_start.sh mit JOB_GPU_MB.
   Vorher LICENSE der Gewichte lesen und in LIZENZ_WERKZEUGE.md eintragen.

3. Mono-Massstab aus Feinpunkten statt Scan (B2, klein, eigener Code mit DA2-Small; optional DA3-Base/MoGe-2 als Vergleich).
   Test: Schwabentor Nord, wo nord_misch Feinpunkte hat: affine Abbildung je 1,5-m-Kachel auf die tiefe_lokal-Punkte (Huber),
   Haelfte der Punkte als Fit, Haelfte als Pruefung. Tor: Pruefpunkt-Rest kleiner als beim Scan-Bandpass-Anker; Fugentiefe dann als
   gemessen markieren, sonst bleibt ANNAHME. Synthetische Gegenprobe wie 11.11. (glatter Traeger darf kein Relief bekommen).

4. Schattierungstor (F1, klein, eigener Code).
   Test: kaufhaus_gk gegen grob3 auf denselben 9 Fotos wie feinteil_tor, plus Nullkontrollen flach, Brei (dichte Wolke roh),
   0,5 m verschoben. Tor fuer das Mass selbst: richtiges Relief > Brei und > flach in mindestens 8/9 Fotos, Wiederholung bitgleich.
   Erst wenn es Brei von Relief trennt, als Hinweis in bauen_abnehmen.sh.

5. Normalen aus Fotos vereint und integriert (C1, mittel, MoGe-2 MIT).
   Test: Schwabentor Sued Brei-Zone (zone 8,6-11,4 / 0,6-4,9), 6 Fotos wie im Mono-Lauf; Normalen je Foto in den Wandrahmen, Median,
   Integration mit Scan-Tiefpass als Anker. Tor: Fugen-F1 Holdout 113836 >= Mono-Relief (0,41 in der Brei-Zone); Putzflaeche
   bleibt eben (Normalenabweichung < 3 Grad); Draht-Grat kleiner als im Mono-Relief. Installation von MoGe vorher freigeben lassen
   (war am 17.11. nicht erlaubt).

Ohne Code sofort: Fotoauftrag mit seitlich versetzten Standorten (A2) fuer die Drahtzonen Nord/Sued; das loest den Draht
wahrscheinlich besser als jede Software.

## Wo wir dem Stand der Technik voraus oder gleichauf sind (ehrlich)
- Gleichauf: Wandbild aus vielen Fotos mit Homographie-Zug, Median und Verdeckererkennung ueber Abweichung vom Median - das ist
  der klassische Weg (Korah/Rasmussen, Hammoudi), sauber umgesetzt. Rueckstand nur bei der feinen Ausrichtung (A1).
- Gleichauf: Kanten-Tiefen-Sweep mit Stabilitaetskarten entspricht den zweistufigen Kurvenverfahren (NEF/EMAP/EdgeGaussians).
- Gleichauf: Mono-Hochpass mit Massstab je Kachel aus einer metrischen Quelle entspricht der Idee von Prior Depth Anything /
  Any2Full, ohne Training. Rueckstand: der Anker ist die Wolke.
- Voraus (soweit ich sehe): die Tore. Holdout-Fotos, Nullkontrollen (gedreht, verschoben, falsches Fotopaar), Zufallsbasis bei
  Fugen-F1 und die Regel "Wolke nur Lage-Veto" sind strenger als die Auswertung der meisten Arbeiten, die auf DTU/ETH3D-Chamfer
  gegen Laser-Wahrheit messen - die wir nicht haben.
- Voraus: Lizenzdisziplin und das Ziel druckbarer, parametrischer Bauteile; kaum eine Arbeit endet bei einem wasserdichten
  1:87-Bausatz.
- Rueckstand: gelerntes MVS (B1), Normalen (C1), einstufige Kurvenoptimierung (D), Druckvorschau (F4).

## Lizenzen der neuen Kandidaten (vor Einsatz in LIZENZ_WERKZEUGE.md eintragen)
- MVSFormer++: Apache-2.0 (geprueft Repo-Seite), Gewichte offen. GeoMVSNet: Apache-2.0 (geprueft Repo-Seite).
- MVSAnywhere: nicht kommerziell (geprueft README). Intrinsic (compphoto): academic use (Treffer).
- MoGe-2 vitl-normal: MIT (geprueft HF-Modellkarte). StableNormal: Code Apache-2.0 (geprueft), Gewichte/SD-Basis offen.
- Depth Anything 3 Base: Apache-2.0 (Treffer, HF-Modellkarte). LaMa: Apache-2.0 (Treffer). BiNI: offen. Any2Full/Prior DA: offen.
- gsplat (2DGS): Apache-2.0 (Treffer). CurveGaussian: Code/Lizenz nicht gefunden.

## Quellen (in dieser Sitzung gefunden)
- MVSFormer++ Paper https://arxiv.org/pdf/2401.11673 ; Code https://github.com/maybeLx/MVSFormerPlusPlus
- GeoMVSNet https://github.com/doubleZ0108/GeoMVSNet ; Paper https://openaccess.thecvf.com/content/CVPR2023/html/Zhang_GeoMVSNet_Learning_Multi-View_Stereo_With_Geometry_Perception_CVPR_2023_paper.html
- MVSAnywhere https://github.com/nianticlabs/mvsanywhere ; https://arxiv.org/abs/2503.22430
- MonoMVSNet https://openaccess.thecvf.com/content/ICCV2025/papers/Jiang_MonoMVSNet_Monocular_Priors_Guided_Multi_View_Stereo_Network_ICCV_2025_paper.pdf
- MoGe https://github.com/microsoft/moge ; Gewichte https://huggingface.co/Ruicheng/moge-2-vitl-normal ; Paper https://arxiv.org/abs/2507.02546v1
- StableNormal https://github.com/Stable-X/StableNormal ; https://arxiv.org/abs/2406.16864
- Depth Anything 3 https://huggingface.co/depth-anything/DA3-BASE/blob/main/README.md
- MapAnything https://arxiv.org/abs/2509.13414v3 ; https://huggingface.co/facebook/map-anything-apache/blob/main/README.md
- Prior Depth Anything (arXiv 2505.10565) ; Any2Full https://arxiv.org/abs/2603.05711
- LaMa https://huggingface.co/opencv/inpainting_lama/raw/main/README.md ; Paper https://arxiv.org/pdf/2109.07161v1.pdf
- Outdoor/Mehrlicht-PS: https://isprs-archives.copernicus.org/articles/XLVIII-2-W8-2024/289/2024/ ; RNb-NeuS https://arxiv.org/pdf/2312.01215v2 ;
  Kulturerbe-Orthobilder bei wechselndem Sonnenlicht https://isprs-archives.copernicus.org/articles/XL-5-W4/139/2015/isprsarchives-XL-5-W4-139-2015.pdf
- Intrinsic (Careaga & Aksoy) https://github.com/compphoto/Intrinsic ; https://arxiv.org/abs/2409.13690
- BiNI https://github.com/xucao-42/bilateral_normal_integration ; Milano ICCV 2025 https://openaccess.thecvf.com/content/ICCV2025/papers/Milano_Discontinuity-aware_Normal_Integration_for_Generic_Central_Camera_Models_ICCV_2025_paper.pdf
- Kurven: NEF https://yunfan1202.github.io/NEF ; CurveGaussian https://arxiv.org/html/2506.21401v3 ; SketchSplat https://arxiv.org/html/2503.14786v2
- gsplat 2DGS https://radiancefields.com/nerfstudio-release-gsplat-1-4
- Fassadentextur/Verdeckung (aeltere Grundlagen): MIT Facade Micro-Structure https://people.csail.mit.edu/teller/pubs/WangEtAlFacadeMicroStructure.pdf ;
  Korah/Rasmussen (IEEE-Eintrag) https://search.isc.ac/inventory/49/2379436.htm
- Nur aus dem Gedaechtnis (nicht nachgesehen): Zhou & Koltun 2014 Color Map Optimization; Waechter et al. 2014 MVS-Texturing;
  Perez et al. 2003 Poisson Image Editing; RAFT (BSD-3); LPIPS (BSD-2).

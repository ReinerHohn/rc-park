# Videobilder zaehmen, Putz fuellen, Seiten verankern

Nach den eigenen Messungen vom 19.11.2026 liegt der groesste verbleibende Hebel nicht in einem neuen Rekonstruktionsprogramm, sondern im Bildeingang: 84 % der Martinstor-Bilder sind Videobilder, und an ihnen haengen Videosuche (77 min), Mapper (68 min) und Seitenerkennung (22-30 min). Die Literatur stuetzt dafuer drei Dinge: Schluesselbilder nach Bildverschiebung statt nach Schaerfe waehlen, die Clip-Reihenfolge als vertrauenswuerdige Verbindung behandeln und Querverbindungen gesondert pruefen, und die Zahl der Spuren im globalen Mapper deckeln. Fuer Putzflaechen gibt es genau eine belegte und lizenzsaubere Verbesserung jenseits der eigenen Parameterwahl: **APD-MVS (MIT) hebt die Vollstaendigkeit auf dem Vergleichsdatensatz ETH3D von 63 % auf 86 %** bei fast gleicher Genauigkeit. Auf Internetfotos und auf 8 GB ist das aber nirgends gemessen. Fuer das Vereinen getrennter Seitenmodelle kennt die Literatur kein automatisches Verfahren. Symmetrie liefert laut der einschlaegigen Arbeit nur eine Menge moeglicher Lagen. Der saubere Weg ist deshalb, jede Seite einzeln an GPS und LoD2 auszurichten und die 180-Grad-Drehung nur als Gegenprobe zu behalten. Die Lizenzlage ist der eigentliche Engpass: Fast alles, was 2024-2026 Bestwerte setzt (MASt3R, Doppelgangers++, MVSAnywhere, das offizielle 2DGS, PGSR, Neuralangelo), ist nicht kommerziell nutzbar. Keine der zwoelf Massnahmen unten ist an gemischten Fotos eines Stadttors veroeffentlicht gemessen. "Belegt" heisst hier immer: belegt auf fremden Vergleichsdaten.

## Zwei Drittel der Rechenzeit haengen am Videomaterial

Die eigenen Zeiten am Martinstor (eigene Messung, 1990 Bilder) summieren sich auf rund 213-221 Minuten: Videosuche 77, Mapper 68, PatchMatch mit Fusion 27, Seitenerkennung 22-30, Merkmale mit Abgleich 19. Zur Einordnung der Begriffe: Der *Mapper* berechnet die Kamerastandorte. *PatchMatch* berechnet je Bild eine Tiefenkarte, die *Fusion* fuegt die Karten zur dichten Punktwolke zusammen.

Drei Beobachtungen ordnen die Recherche:

- Der Abgleich selbst ist mit 19 min kein Engpass mehr. Weniger Bildpaare lohnen nur, wenn sie auch den Mapper entlasten. Das ist plausibel, aber nicht belegt.
- Der Mapper lief ohne die 637 objektfremden Bilder in 45 statt 68 min (eigene Messung). Wer fremde Bilder vor dem Abgleich erkennt, spart also an zwei Stellen.
- 293 000 Paare bei 1990 Bildern sind im Mittel rund 147 Paare je Bild. Die Referenzkette hloc nimmt 20 Paare je Bild fuer den Modellaufbau ([hloc Aachen-Pipeline](https://raw.githubusercontent.com/cvg/Hierarchical-Localization/master/hloc/pipelines/Aachen/pipeline.py)).

In den COLMAP-Versionshinweisen 4.0.3 bis 4.2.1 steht keine Beschleunigung von PatchMatch, nur Fehlerbehebungen. Eine veroeffentlichte Version 4.3 gibt es nicht. Der eigene Mapper-Bau 4.3.dev ist also ein Entwicklungsstand, den keine Versionshinweise beschreiben ([COLMAP Releases](https://github.com/colmap/colmap/releases)).

## Rangliste: zwoelf Massnahmen nach Nutzen je Aufwand

Jede Massnahme nennt Quelle, Lizenz, 8-GB-Tauglichkeit, den Stand (belegt oder vermutet) und einen ersten Versuch. Schon frueher empfohlene Schritte stehen nicht noch einmal in der Liste: GPS-Tor, globaler Mapper mit Kalibrierstufe, Weglassen des geometrischen PatchMatch-Durchgangs, LIMAP, Orthofoto je Wand, GPU-Speicherbuchung, MapAnything als Gegenprobe, RealityScan, Mietkarte.

### 1. Spurenzahl im globalen Mapper deckeln, GPU-Loeser pruefen

Eine *Spur* (track) ist ein 3D-Punkt mit allen Bildpunkten, die ihn sehen. Der *Buendelausgleich* (BA) verfeinert Kameras und Punkte gemeinsam, und seine Kosten wachsen mit der Punktzahl.

- **Was:** `GlobalMapper.keep_max_num_tracks` setzen (seit 4.1.0). Die GLOMAP-Anleitung nennt als Faustregel rund 1000 Spuren je Bild, dazu Obergrenzen fuer die Iterationen von Positionsschaetzung und BA ([COLMAP Releases](https://github.com/colmap/colmap/releases), [GLOMAP getting_started](https://github.com/colmap/glomap/blob/main/docs/getting_started.md)). Zusaetzlich pruefen, ob der eigene Bau den GPU-Loeser cuDSS nutzt: `ba_use_gpu` wirkt seit 4.1.0 auch im globalen Mapper, und ohne passende GPU faellt Ceres seit 4.2.0 auf die CPU zurueck ([COLMAP FAQ](https://colmap.github.io/faq.html), [COLMAP Releases](https://github.com/colmap/colmap/releases)).
- **Lizenz:** BSD (COLMAP), keine Gewichte.
- **8 GB:** ja. Der Speicherbedarf des GPU-Loesers bei 1000-2000 Bildern ist nirgends veroeffentlicht.
- **Stand:** Die Optionen sind belegt. Der Gewinn ist vermutet (1,5- bis 3-fach auf den BA-Anteil, Schaetzung aus den Notizen), eine Messung fehlt. Die Faustregel stammt aus einem Suchtreffer-Auszug. Die genauen Optionsnamen am eigenen Bau mit `colmap global_mapper -h` pruefen.
- **Erster Versuch:** Martinstor ohne die fremden Bilder, Mapper mit und ohne Deckel bei 1000 Spuren je Bild. Messgroessen: Mapper-Minuten (heute 45), registrierte Bilder, Anteil am GPS-Tor, Foto-F1. Im Log nach der Rueckfallmeldung auf die CPU suchen.

### 2. Schluesselbilder nach Bildverschiebung waehlen, Schaerfe nur oertlich

Ein *Schluesselbild* ist ein aus dem Video uebernommenes Einzelbild.

- **Was:** Ein neues Schluesselbild erst dann nehmen, wenn sich die verfolgten Merkmale seit dem letzten genug verschoben haben. Unter benachbarten Kandidaten gewinnt das schaerfste. Abschnitte mit reiner Drehung oder Zoom entfallen, weil dort eine Ebenenabbildung die Bewegung besser erklaert als eine echte Zweibildgeometrie.
- **Quelle:** Das Ziel ist genug Ueberlappung und genug Parallaxe ([CNR-Arbeit](https://iris.cnr.it/retrieve/1f18b2fb-9a78-46a1-8e1b-21666b62cedd/prod_465907-doc_191167.pdf)). VidMap steuert die Auswahl ueber eine normierte Merkmalsverschiebung, Beispielwert 0,09 ([VidMap](https://github.com/cvg/vidmap)). Die Schaerfezahl nach Laplace haengt vom Bildinhalt ab und braucht je Datensatz eine eigene Schwelle ([radiancefields.com](https://radiancefields.com/focusframefinder-auto-culls-blurry-images-for-nerf-datasets)).
- **Lizenz:** eigener Code. ALIKED fuer die Merkmale ist BSD-3 ([ALIKED](https://github.com/Shiaoming/ALIKED)).
- **8 GB:** ja.
- **Stand:** Die Kriterien sind belegt. Eine Studie "Auswahlverfahren gegen Modellqualitaet" fuer Rundgang- oder Drohnenvideo wurde nicht gefunden. Dass eine Bestenliste nach Schaerfe ueber den ganzen Clip die strukturreichen Abschnitte bevorzugt und Putzwaende meidet, ist eine Folgerung, kein Messwert.
- **Erster Versuch:** Stufe Videobilder am Martinstor neu waehlen. Messgroessen: Zahl der Videobilder (heute rund 1670), Paare, Mapper-Minuten, Anteil registrierter Bilder, belegte Wandflaeche. Achtung, eigene Erfahrung: Ausduennen des Bestands hat frueher Tuermchen gekostet. Deshalb nur Bilder ohne Standortwechsel streichen und die Hoehen an Zinnen und Tuermchen gegenpruefen.

### 3. Fremde Bilder und Videoabschnitte vor dem Abgleich aussortieren

Ein *globaler Deskriptor* ist ein Zahlenvektor je Bild. Aehnliche Vektoren bedeuten: vermutlich derselbe Ort.

- **Was:** Videos mit 1 Bild je Sekunde abtasten, jedes Bild mit MegaLoc beschreiben, nur Zeitabschnitte behalten, die einer kleinen Menge gepruefter Referenzfotos des Bauwerks aehneln. Dieselben Vektoren liefern spaeter die Paarliste (Punkt 5).
- **Quelle:** MegaLoc, Auswertung bei 322 px ([MegaLoc](https://github.com/gmberton/MegaLoc), [arXiv 2502.17237](https://arxiv.org/abs/2502.17237v1)).
- **Lizenz:** Code MIT. Fuer die Gewichte nennt das Repo keine eigene Lizenz, die Trainingsdaten wurden nicht geprueft.
- **8 GB:** vermutlich ja (kleines Netz, kleine Bilder). Eine Speicherangabe ist nicht veroeffentlicht.
- **Stand:** vermutet. Ein veroeffentlichtes Werkzeug, das genau das tut, wurde nicht gefunden. Die Modelle sind auf Strassenansichten trainiert. Schwarzweissfotos und Drohnenblicke liegen ausserhalb, dort grosszuegiger schwellen.
- **Erster Versuch:** Stufe Videosuche (heute 77 min). Messgroessen: Wie viele der 637 als fremd bekannten Bilder faengt der Filter ab, wie viele der spaeter registrierten Bilder wirft er faelschlich weg, und wie lange dauert er.

### 4. Clip-Reihenfolge als vertrauenswuerdige Verbindung, Querverbindungen pruefen

- **Was:** Spuren nur aus zeitlich benachbarten Bildern eines Clips bilden. Verbindungen zwischen Clips und zu Fotos gelten als Kandidaten und werden gesondert geprueft. Fuer die Seitenerkennung heisst das: Ein Clip ist ein Knoten im Paar-Graphen, der Doppelgangers-Klassifikator stimmt nur noch ueber Verbindungen zwischen Clips und Fotogruppen ab.
- **Quelle:** VidMap (ECCV 2026) trennt genau so und erreicht auf LaMAR 88,5 statt 62,3 Punkte gegenueber GLOMAP mit LightGlue, ohne die Unterscheidung der Kantenarten noch 79,9. Die Autoren nennen die Grenze selbst: Viele untereinander stimmige falsche Verbindungen verfaelschen die Loesung weiterhin ([VidMap arXiv 2607.27194](https://arxiv.org/html/2607.27194)).
- **Lizenz:** VidMap-Code Apache-2.0. Die mitgeladenen Modelle (RoMa v2, MegaLoc, Depth Anything 3, GeoCalib) sind ungeprueft, RoMa v2 haengt an DINOv3 mit Meta-Sonderlizenz ([RoMa v2](https://github.com/Parskatt/romav2)). Deshalb das Prinzip uebernehmen, nicht das Programm.
- **8 GB:** Prinzip ja. VidMap selbst laedt rund 9 GB Modelldateien, sein Speicherbedarf ist nicht angegeben ([VidMap](https://github.com/cvg/vidmap)).
- **Stand:** belegt fuer reine Videodaten, vermutet fuer die Mischung aus Clips und Fotos. Die genannte Grenze deckt sich mit der eigenen Messung, dass die Sim3-Probe gemeinsamer Punkte nicht trennte: Doppelgaenger-Verbindungen sind in sich stimmig.
- **Erster Versuch:** Stufe Seitenerkennung am Schwabentor (Wahrheit vorhanden). Messgroessen: Bleiben 12 von 12 echten Verbindungen richtig, verschwindet der eine Fehlalarm, und wie weit faellt die Rechenzeit unter die heutigen 22-30 min, weil viel weniger Paare zu klassifizieren sind.

### 5. Paarliste nach Bildart statt alles gegen alles

- **Was:** Videobilder nur mit ihren zeitlichen Nachbarn paaren, Schleifen nur zu entfernten Bildern suchen (`SequentialMatching.loop_detection_min_index_distance`, seit 4.2.0). Fotos bekommen die k aehnlichsten Bilder aus Punkt 3, Schwarzweiss- und Luftbilder ein groesseres k. Danach die Vereinigung beider Listen als eigene Paarliste importieren. COLMAP gleicht nur noch nicht abgeglichene Paare ab, die Liste laesst sich also schrittweise erweitern ([COLMAP Tutorial](https://colmap.github.io/tutorial.html), [COLMAP Releases](https://github.com/colmap/colmap/releases)).
- **Richtwerte:** hloc 20 Paare je Bild, COLMAP-Vokabelbaum 100, Sieger des Wettbewerbs IMC 2025 10-25 je Suchverfahren ([hloc](https://raw.githubusercontent.com/cvg/Hierarchical-Localization/master/hloc/pipelines/Aachen/pipeline.py), [arXiv 1811.10343](https://arxiv.org/html/1811.10343), [IMC-2025-Sieger](https://www.kaggle.com/competitions/image-matching-challenge-2025/writeups/ns64-1st-place-solution)). Die meisten Teams waehlten lockere Schwellen und kombinierten zwei Suchsignale, oder sie paarten alles und filterten danach ([Zusammenfassung IMC 2025](https://zenn.dev/yume_neko/articles/bee802ebf8b4d0)).
- **Lizenz:** COLMAP BSD, hloc Apache-2.0, MegaLoc MIT ([hloc](https://github.com/cvg/Hierarchical-Localization)).
- **8 GB:** ja.
- **Stand:** Die Praxis ist belegt. Ein kontrollierter Vergleich "k Nachbarn gegen alle Paare" auf Internetfotos eines Bauwerks wurde nicht gefunden. Die Rechnung 293 000 auf 40 000-100 000 Paare (3- bis 7-fach weniger) ist eine Schaetzung. Zu kleines k kann die Rekonstruktion scheitern lassen ([UAVPairs](https://arxiv.org/html/2505.22098)).
- **Erster Versuch:** Stufe Abgleich am Martinstor mit k = 30 fuer Fotos. Messgroessen: Paare, registrierte Bilder getrennt nach Foto und Video, Mapper-Minuten, GPS-Tor. Nicht an der Trefferzahl entscheiden.

### 6. Jede Seite einzeln am Aussenrahmen ausrichten, Drehung nur als Gegenprobe

*Aussenrahmen* meint hier das gemeinsame Koordinatensystem aus GPS und LoD2.

- **Was:** Vorder- und Rueckseitenmodell getrennt verorten: grob ueber die Foto-GPS der jeweiligen Kameras (`model_aligner`, mindestens 3 Bilder, RANSAC-Schwelle `--alignment_max_error`), fein ueber die LoD2-Wand, die das Teilmodell wirklich sieht, Massstab je Seite aus einem Gebaeudemass. Damit sind beide Modelle ohne gemeinsame Punkte vereint. Die heutige 180-Grad-Drehung um die Turmachse wird zur Kontrolle.
- **Quelle:** `model_merger` braucht gemeinsame registrierte Bilder ([COLMAP CLI](https://colmap.github.io/cli.html), [COLMAP FAQ](https://colmap.github.io/faq.html)). Die einschlaegige Arbeit zum Vereinen unverbundener Gebaeudeseiten haelt das Problem fuer allgemein unloesbar und gibt deshalb eine Menge plausibler Lagen aus ([Cohen et al., ICCV 2015](https://www.cv-foundation.org/openaccess/content_iccv_2015/papers/Cohen_Merging_the_Unmatchable_ICCV_2015_paper.pdf)). Code dazu wurde nicht gefunden.
- **Lizenz:** BSD plus eigener Code.
- **8 GB:** ja, reine CPU-Arbeit.
- **Stand:** Die Werkzeuge sind belegt. Dass die Einzelausrichtung genauer ist als die Drehung, ist vermutet. Keine Veroeffentlichung misst eine symmetriebasierte Lage an Tuermen gegen die Wahrheit. Die Drehung laesst vier Freiheiten offen: Lage der Achse im Grundriss, Versatz laengs der Durchfahrt, Hoehenversatz, Massstab.
- **Erster Versuch:** Martinstor-Rueckseite (114 Bilder) unabhaengig ausrichten. Messgroesse: Unterschied zur gedrehten Lage in Zentimetern, Grad und Massstab, dazu das GPS-Tor nur fuer die Rueckseite. Abweichungen ueber der Wandtoleranz zeigen, welche der vier Freiheiten die Drehung falsch setzt.

### 7. APD-MVS als zweite Tiefenkarten-Rechnung fuer Putzfelder

- **Was:** APD-MVS ist ein PatchMatch-Programm, das sein Vergleichsfenster auf strukturarmen Flaechen verformt und an verlaessliche Nachbarpunkte anlehnt. Es liest das entzerrte COLMAP-Modell ueber ein Umwandlungsskript und gibt eine fertige Punktwolke aus. Kein neuronales Netz, keine Gewichte ([APD-MVS](https://github.com/whoiszzj/APD-MVS)).
- **Belegte Zahlen (ETH3D, Schwelle 2 cm, Genauigkeit / Vollstaendigkeit):**
  - COLMAP 92,0 / 63,0
  - ACMMP 91,9 / 81,5
  - APD-MVS 89,5 / 85,9
  - DVP-MVS 91,3 / 89,4

  ([ACMP-Arbeit](https://arxiv.org/abs/1912.11744), [DVP-MVS-Arbeit](https://arxiv.org/html/2412.11578v3)). *Vollstaendigkeit* ist der Anteil der wahren Oberflaeche, der in der Wolke vorkommt.
- **Lizenz:** APD-MVS und ACMMP MIT ([ACMMP](https://github.com/GhiXu/ACMMP)). DVP-MVS ist MIT, braucht aber Depth Anything V2 in ungenannter Groesse, und nur die kleine Fassung ist Apache-2.0 ([DVP-MVS](https://github.com/ZhenlongYuan/DVP-MVS), [Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2)). HPM-MVS, HPM-MVS++, MP-MVS, SD-MVS, MSP-MVS und SED-MVS haben keine Lizenzdatei und scheiden aus.
- **8 GB:** unbekannt. Die Autoren testeten auf 24 GB, ACMMP auf 11 GB. Die verwandte, aber lizenzlose HPM-Familie lief auf einer 8-GB-Karte ([HPM-MVS](https://github.com/CLinvx/HPM-MVS)). Bei 1600 px plausibel, vorher mit wenigen Bildern testen. Im Bauskript muss die GPU-Generation eingetragen werden, sonst entstehen keine Tiefen.
- **Stand:** belegt auf ETH3D (eine Kamera, eine Sitzung, viele glatte Innenwaende). Nicht belegt auf Internetfotos mit wechselndem Licht. Auf der strukturierten ETH3D-Aussenszene "facade" ist der Gewinn klein (74,2 auf 76,6 % bei ACMP). Die Ebenenannahme kann Gesimse glaetten. Die Wolke bleibt also Lage-Kontrolle.
- **Erster Versuch:** Stufe dichte Wolke, dasselbe Martinstor-Putzfeld, 1600 px. Messgroessen: belegter Anteil des Putzfelds und der ganzen Wandflaeche, Anteil falscher Punkte gegen die LoD2-Wandebene, Sekunden je Bild. Uebernahme nur, wenn die eigene Einstellung (99 % bei 2,4-facher Zeit, 76 % der Wandflaeche) in Zeit oder Flaeche geschlagen wird.

### 8. Brueckenbilder im Bestand suchen und in beide Seitenmodelle einhaengen

- **Was:** Bilder suchen, die eine Stirnseite zusammen mit Flanke, Dach, Durchfahrt oder unsymmetrischer Umgebung zeigen, und sie mit `image_registrator` in beide Teilmodelle einhaengen. Mit gemeinsamen registrierten Bildern arbeitet `model_merger`, danach ein gemeinsamer Buendelausgleich ([COLMAP CLI](https://colmap.github.io/cli.html), [COLMAP FAQ](https://colmap.github.io/faq.html)).
- **Quelle:** Die Doppelgangers-Autoren halten fest, dass ein richtig getrenntes Modell in zwei Teile zerfaellt, wenn Ansichten aus genuegend Blickwinkeln fehlen ([Doppelgangers, Anhang](https://openaccess.thecvf.com/content/ICCV2023/supplemental/Cai_Doppelgangers_Learning_to_ICCV_2023_supplemental.pdf)).
- **Lizenz:** BSD.
- **8 GB:** ja.
- **Stand:** Der Mechanismus ist belegt. Wie viele Brueckenbilder noetig sind, beziffert keine Quelle. Dass der eigene Bestand solche Bilder enthaelt (auch unter den unregistrierten und den als fremd aussortierten), ist vermutet. Risiko: Ein Stirnseitenfoto haengt sich ueber Doppelgaenger-Treffer in die falsche Seite ein. Jeder Brueckenkandidat braucht deshalb die Abstimmung aus der Seitenerkennung.
- **Erster Versuch:** Nach der Seitentrennung am Martinstor. Messgroessen: Zahl der Bilder, die in beiden Modellen mit genug Treffern stehen, und der Unterschied zwischen vereintem Modell und Punkt 6.

### 9. Blickrichtungs-Probe und Seitenmarke als Lagevorgabe

- **Was:** Fuer jede registrierte Kamera mit GPS pruefen, ob das Bauwerk von ihrem GPS-Standort aus vor der Kamera liegt. Die Blickrichtung kippt zwischen den Seiten um 180 Grad, das Handy-GPS streut nur um einige Meter. Fotos ohne GPS, deren Seite von Hand bekannt ist, bekommen eine grobe Lagevorgabe einige Meter vor der jeweiligen Stirnseite mit weiter Streuung.
- **Quelle:** COLMAP liest Foto-GPS in die Tabelle der Lagevorgaben und nutzt sie im `pose_prior_mapper` ([COLMAP FAQ](https://colmap.github.io/faq.html)). Verrauschte Geomarken reichen, um ueber den Anteil passender Kameras zu entscheiden, ob ein Modell richtig getrennt ist ([Doppelgangers++](https://arxiv.org/html/2412.05826v2)).
- **Lizenz:** BSD plus eigener Code.
- **8 GB:** ja.
- **Stand:** vermutet, nur mittelbar gestuetzt. Kein Test der Lagevorgabe als Mittel gegen Seitenverwechslung wurde gefunden. Widerspruch in den Quellen: Ein Suchtreffer nennt Lagevorgaben auch fuer den globalen Mapper, die fruehere eigene Pruefung fand dort keine. Am eigenen Bau mit `-h` klaeren. COLMAP kennt Schwerkraft-, aber keine Kompassvorgaben.
- **Erster Versuch:** Als Tor nach dem Mapper am Schwabentor. Messgroesse: Erkennt die Probe allein die bekannten falschen Verbindungen, und wie viele Kameras bleiben unentschieden.

### 10. Fehlende-Treffer-Probe als zweite, unabhaengige Stimme

- **Was:** Fuer ein Bildpaar die 3D-Punkte des einen Bildes in das andere rechnen. Bleiben grosse Bildbereiche mit gueltiger Tiefe ohne Treffer, waehrend ein kompakter Bereich passt, zeigt das Paar zwei verschiedene, gleich aussehende Seiten. Das nutzt die verschiedene Nachbarbebauung beider Turmseiten.
- **Quelle:** Verfahren von Cui und Tan (2015) und Yan (2017), umgesetzt fuer COLMAP-Datenbanken in [cvg/sfm-disambiguation-colmap](https://github.com/cvg/sfm-disambiguation-colmap). Die Autoren dort: Kein Verfahren arbeitet ueber alle Datensaetze mit einer Parameterwahl, und Yan brauchte fuer 1618 Bilder ueber 8 Stunden.
- **Lizenz:** Das Repo hat keine Lizenzdatei. Den Code also nicht uebernehmen, sondern die veroeffentlichte Idee mit pycolmap selbst schreiben.
- **8 GB:** ja, CPU.
- **Stand:** belegt auf Wahrzeichen-Vergleichsszenen, nicht an schmalen Tortuermen. Die Doppelgangers-Autoren nennen die klassischen Verfahren bruechig und einstellungsabhaengig ([Doppelgangers](https://arxiv.org/pdf/2309.02420)). Als zweite Stimme neben dem Klassifikator ist der Nutzen vermutet.
- **Erster Versuch:** Stufe Seitenerkennung am Schwabentor. Messgroessen: 12 von 12 echten Verbindungen, Verhalten beim einen Fehlalarm, Rechenzeit je Gruppenverbindung.

### 11. Fuell-Tiefe nur in Loechern, als getrennte Fuellwolke

- **Was:** Wo PatchMatch leer bleibt, eine Tiefe aus einem Einzelbild-Netz einsetzen, oertlich an die vorhandenen PatchMatch-Tiefen und Modellpunkte angepasst. Danach muss die normale Mehrbild-Pruefung der Fusion entscheiden. Das Ergebnis getrennt von der strengen Wolke ablegen.
- **Quelle:** Prior Depth Anything verbindet "genaue, aber lueckenhafte" Messtiefe mit "vollstaendiger, aber relativer" Netztiefe ([arXiv 2505.10565](https://arxiv.org/abs/2505.10565), [Repo](https://github.com/SpatialVision/Prior-Depth-Anything)). Warnzahl: Eine nur global skalierte Einzelbildtiefe liegt im Mehrbild-Vergleich bei 5,6 % relativem Fehler gegen 2,7 % eines echten Mehrbildverfahrens ([MVSAnywhere-Arbeit](https://arxiv.org/html/2503.22430v1)). Bei 10 m Abstand sind das Dezimeter, deshalb oertlich anpassen.
- **Lizenz:** Prior Depth Anything: Code und Gewichte als Apache-2.0 gekennzeichnet. Offen ist, ob die mittlere Fassung von nicht kommerziellen Depth-Anything-V2-Gewichten abstammt. Vor Verkauf klaeren, bis dahin nur die kleine Fassung nehmen. MoGe-2: Code MIT, Gewichte als MIT gekennzeichnet, von den Betreuern aber noch nicht ausdruecklich bestaetigt ([MoGe](https://github.com/microsoft/MoGe), [MoGe Issue 98](https://github.com/microsoft/MoGe/issues/98)). Depth Anything V2 Small und Depth Anything 3 Small, Base, Metric-Large, Mono-Large: Apache-2.0 ([Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3)).
- **8 GB:** plausibel bei 518-1024 px, in keiner Quelle angegeben.
- **Stand:** vermutet. Keine Veroeffentlichung prueft diese Verbindung an Putzfassaden. Fuer eine wirklich ebene Wand bringt das Netz wenig mehr als eine Ebene durch die vorhandenen Wandpunkte. Sein Wert liegt bei Ausbauchungen, Laibungen und schraegen Pfeilern.
- **Erster Versuch:** Stufe dichte Wolke, ein Putzfeld mit Laser- oder LoD2-Vergleich. Messgroessen: belegte Flaeche und Abstand der gefuellten Punkte zur Vergleichsflaeche, getrennt nach Rand und Feldmitte.

### 12. Dichter Abgleicher und Kacheln nur fuer die schwierigen Fotos

- **Was:** Historische Fotos und Luftbilder, die mit ALIKED und LightGlue haengen bleiben, mit dem dichten Abgleicher RoMa gegen ihre besten heutigen Nachbarn abgleichen und die Treffer importieren. Bei grossem Massstabsunterschied das Uebersichtsbild gegen Kacheln des Detailbilds abgleichen.
- **Quelle:** RoMa meldet Bestwerte auf WxBS, einem Vergleich mit Licht-, Jahreszeit- und Sensorwechsel ([RoMa](https://arxiv.org/html/2305.15404v2)). Der Drittplatzierte der IMC 2025 glich je Paar vier Kacheln und eine halbierte Kopie ab ([Zusammenfassung IMC 2025](https://zenn.dev/yume_neko/articles/bee802ebf8b4d0)). Gegenstimme: In einem Vergleich aus einem anderen Bildbereich erzeugten RoMa und DKM bei starkem Merkmalswechsel mehr Fehltreffer als LightGlue ([arXiv 2502.01002](https://arxiv.org/pdf/2502.01002)).
- **Lizenz:** RoMa MIT, das enthaltene DINOv2 Apache-2.0 ([RoMa](https://github.com/Parskatt/roma)). Nicht freigegeben: RoMa v2 (DINOv3-Sonderlizenz, ungelesen), Efficient LoFTR und MatchAnything (Registrierlizenz von 2026, Widerspruch zur Apache-Angabe auf Hugging Face), SuperPoint-Gewichte (nur Forschung) ([EfficientLoFTR](https://github.com/zju3dv/EfficientLoFTR), [SuperPoint-Lizenz](https://github.com/magicleap/SuperPointPretrainedNetwork/blob/master/LICENSE)).
- **8 GB:** vermutlich nur mit verkleinerter Aufloesung und halber Rechengenauigkeit. Keine Angabe gefunden.
- **Stand:** Der Vorsprung auf WxBS ist belegt. Fuer Schwarzweissfotos gegen heutige Fotos gibt es keinen Vergleich neuer Abgleicher. Belegt ist dort nur das nicht kommerzielle SuperGlue ([Maiwald et al. 2021](https://doi.org/10.3390/ijgi10110748)). Fuer Boden-zu-Luft-Paare kommen die einzigen grossen belegten Gewinne aus nicht kommerziellen MASt3R-Ablegern ([AerialMegaDepth](https://arxiv.org/pdf/2504.13157)).
- **Erster Versuch:** Stufe Abgleich, nur die heute unregistrierten historischen Fotos des Kaufhauses. Messgroesse: zusaetzlich registrierte Bilder, die das GPS- und das Foto-Tor bestehen.

## Vier fruehere Aussagen aendern sich

**Caspar ist kein Hebel fuer den globalen Mapper.** Die frueheren Berichte fuehrten den GPU-Buendelausgleich Caspar als ersten Tempo-Schritt. Laut FAQ ist er experimentell, braucht einen eigenen Bauschalter, kennt nur die Kameramodelle SIMPLE_RADIAL und PINHOLE und laesst sich im globalen Mapper nicht waehlen ([COLMAP FAQ](https://colmap.github.io/faq.html)). Ein frueherer Bericht nannte dagegen eine lokal gepruefte Option dafuer. Am eigenen Bau nachsehen, bevor Zeit hineinfliesst. Der Weg, der den globalen Mapper sicher erreicht, ist cuDSS (Punkt 1).

**Die ACMM-Familie ist nicht mehr "kein Gewinn".** Frueher zurueckgestellt, weil die Wolke nur Lage-Veto ist. Die eigenen Putzmessungen zeigen aber, dass Belegung Arbeit kostet, und die MIT-Lizenzen von ACMMP und APD-MVS sind jetzt direkt gelesen. Daher Punkt 7.

**AnyCalib ist lizenzgeklaert.** Die Einbild-Kalibrierung in COLMAP steht unter Apache-2.0, als Modelldatei vom COLMAP-Team veroeffentlicht. Seit 4.2.0 gibt es ausserdem einen Zweibild-Loeser fuer den Fall "eine Brennweite bekannt, eine unbekannt", also Videobild gegen historisches Foto ([COLMAP Releases](https://github.com/colmap/colmap/releases), [AnyCalib](https://github.com/javrtg/AnyCalib)). Wie man AnyCalib in COLMAP aufruft, stand auf keiner gelesenen Seite. Eine Bewertung an gescannten historischen Fotos fehlt.

**Die Schwellen des Doppelgangers-Klassifikators schwanken auch in der Literatur.** Die Nachfolgearbeit berichtet, dass der Vorgaenger je Szene Schwellen zwischen 0,6 und 0,97 brauchte und dass wenige ueberlebende falsche Verbindungen fuer ein falsches Modell reichen ([Doppelgangers++](https://arxiv.org/html/2412.05826v2)). Das erklaert die eigene Messung, dass eine Median-Schwelle allein nicht trennte, und stuetzt die Abstimmung je Gruppenverbindung. Der bessere Nachfolger bleibt gesperrt: Sein Code steht unter CC BY-NC-SA und baut auf MASt3R mit derselben Lizenz ([Lizenz Doppelgangers++](https://raw.githubusercontent.com/doppelgangers25/doppelgangers-plusplus/main/LICENSE)). Der genutzte Vorgaenger ist MIT, sein Abgleicher LoFTR Apache-2.0 ([Doppelgangers](https://github.com/RuojinCai/doppelgangers), [LoFTR](https://github.com/zju3dv/LoFTR)).

Dazu eine Einordnung: Die eigene Beobachtung, dass eine gelockerte Fusion (`min_num_pixels` 8 auf 3) fuenfmal so viele Punkte gibt, hat ein veroeffentlichtes Gegenstueck. OpenMVS erreicht auf ETH3D 78,5 % Vollstaendigkeit gegen 63,0 % bei COLMAP, aber nur 82,0 % Genauigkeit gegen 92,0 %. Die ACMP-Autoren fuehren das auf die lockerere Fusion zurueck, und auf der Ebene der einzelnen Tiefenkarten war OpenMVS sogar schlechter ([ACMP-Arbeit](https://arxiv.org/abs/1912.11744)). Die Zahlen stammen aus den Programmstaenden von 2017-2019. Ein Wechsel zu OpenMVS (AGPL-3.0) braechte demnach vor allem das, was die eigene Fusionseinstellung schon liefert.

## Feed-Forward-Schaetzer: wenige Gewichte sind verkaufstauglich, keines ersetzt die Kette

Ein *Feed-Forward-Schaetzer* ist ein Netz, das Kameras und Tiefen in einem Durchlauf ausgibt, ohne Ausgleichsrechnung.

Verkaufstauglich nach den gelesenen Lizenzseiten:

- **VGGT:** nur das Gewicht `VGGT-1B-Commercial`, Zugang per Antrag, Sonderlizenz mit Ausschluss militaerischer Nutzung. Der Volltext wurde nicht gelesen ([VGGT](https://github.com/facebookresearch/vggt), [HF](https://huggingface.co/facebook/VGGT-1B-Commercial)).
- **MapAnything:** nur `facebook/map-anything-apache`. In der Aenderungshistorie der Modellkarte tauchte einmal "cc-by-nc-4.0" auf. Den genutzten Stand festhalten und die Karte archivieren ([MapAnything](https://github.com/facebookresearch/map-anything), [HF](https://huggingface.co/facebook/map-anything-apache)).
- **Depth Anything 3:** Small und Base (mit Kameraschaetzung), Metric-Large und Mono-Large (nur Einzelbild). Large, Giant und Nested sind nicht kommerziell ([Depth Anything 3](https://github.com/ByteDance-Seed/Depth-Anything-3)).
- **MoGe / MoGe-2:** MIT, Gewichte mit dem Vorbehalt aus Punkt 11.

Nicht verkaufstauglich: DUSt3R, MASt3R und MASt3R-SfM (CC BY-NC-SA), das urspruengliche VGGT-Gewicht, das Standardgewicht von MapAnything, die Gewichte von Pi3 (CC BY-NC), Fast3R, CUT3R ([MASt3R](https://github.com/naver/mast3r/blob/main/LICENSE), [Pi3](https://github.com/yyfz/Pi3), [Fast3R](https://github.com/facebookresearch/fast3r/blob/main/LICENSE)).

Keine der Hauptseiten nennt den Speicherbedarf auf 8 GB. MapAnything gibt "bis 2000 Ansichten auf 140 GB" an, VGGT nennt seit Mai 2026 zwei- bis dreimal mehr Bilder je Speicher. Realistisch sind 30-60 Bilder bei rund 518 px, das ist eine Hochrechnung. Die Ausgabe ist zu grob fuer 1-cm-Wandbilder. Es bleibt bei der Rolle als Gegenprobe. Eine Studie, die einen Buendelausgleich mit solchem Startwert an ueber 1000 ungeordneten Bildern gegen den globalen Mapper misst, wurde nicht gefunden.

Bei den schnellen Mappern ueberzeugt kein Ersatz:

- **FastMap** (MIT) liest die vorhandene COLMAP-Datenbank und waere in ein bis zwei Stunden probiert. Die Autoren nennen es aber selbst anfaellig fuer "katastrophale Fehler" bei duenner Abdeckung und schwachen Treffern, also bei Internetfotos ([FastMap](https://github.com/pals-ttic/fastmap)).
- **InstantSfM** meldet das Zwei- bis Dreifache gegenueber GLOMAP (Alamo 597 gegen 1600 s), gemessen auf einer 140-GB-Karte. Auf Tanks and Temples ist es ungenauer, die Lizenz ist ungeklaert ([InstantSfM](https://arxiv.org/html/2510.13310v1)).
- **GLOMAP** selbst ist auf Internetfotos (IMC 2023) rund achtmal schneller als der schrittweise Mapper (497 gegen 4051 s) bei besserer Lagegenauigkeit. Seine Autoren nennen symmetrische Bauten und falsche Zweibildgeometrien als Schwachstellen und empfehlen einen Doppelgangers-Filter ([GLOMAP](https://arxiv.org/html/2407.20219)).

Bei den Oberflaechenverfahren sind 2DGS (offiziell), GOF, SuGaR, PGSR, Neuralangelo und NeuS2 nicht kommerziell. Frei ist gsplat (Apache-2.0) mit eigenem 2DGS-Trainer ([2DGS-Lizenz](https://github.com/hbb1/2d-gaussian-splatting/blob/main/LICENSE.md), [PGSR-Lizenz](https://github.com/zju3dv/PGSR/blob/main/LICENSE.md), [gsplat](https://github.com/nerfstudio-project/gsplat)). Keine Quelle zeigt, dass ein solches Verfahren eine weisse Wand lagetreuer trifft als ein PatchMatch mit Ebenenannahme. Die PGSR-Autoren haben fuer strukturarme Szenen einen eigenen Schalter ([PGSR](https://github.com/zju3dv/PGSR)). Kein Versuch empfohlen.

## Was vergleichbare offene Pipelines anders machen

Der Unterschied liegt bei Auswahl und Paarbildung, kaum beim Mapper.

- **hloc** (Apache-2.0) sucht je Bild die 20 aehnlichsten ueber einen globalen Deskriptor, gleicht nur diese mit gelernten Merkmalen ab und uebergibt an COLMAP. Seine Standardmerkmale SuperPoint und SuperGlue sind nicht kommerziell, sauber ist ALIKED oder DISK mit LightGlue ([hloc](https://github.com/cvg/Hierarchical-Localization), [LightGlue](https://github.com/cvg/lightglue)).
- **Die Spitzenteams der IMC 2025** verliessen sich nie auf ein einzelnes Suchsignal. Ein Team mit gelerntem Gleiche-Szene-Filter filterte zu stark und musste mit einer zweiten Paarquelle absichern ([Zusammenfassung IMC 2025](https://zenn.dev/yume_neko/articles/bee802ebf8b4d0)). Das stuetzt die Vereinigung in Punkt 5. Der Sieger nutzte MASt3R, das ausscheidet.
- **COLMAP 4.x** bringt den gelernten Abgleicher LoMa und laut aktueller Doku FlexGlue mit einer eingebauten Bewertung gemeinsamer Sichtbarkeit je Paar. Die Bildsuche ist dagegen weiter der alte Vokabelbaum. Eine MegaLoc-Liste muss als eigene Paarliste importiert werden ([COLMAP Features](https://colmap.github.io/features.html)). LoMa meldet +29,5 Punkte gegenueber ALIKED mit LightGlue auf WxBS ([LoMa](https://arxiv.org/abs/2604.04931)), Code MIT ([LoMa-Repo](https://github.com/davnords/LoMa)). Die Lizenz der automatisch geladenen Modelldateien nennt die COLMAP-Doku nicht.
- **GLUEMAP** (2026, COLMAP-Team) setzt einen Doppelgaenger-Filter als feste Stufe vor den globalen Mapper. Es nimmt dafuer Doppelgangers++, und der BSD-Kern erbt laut README die Einschraenkungen der eingebundenen Teile ([GLUEMAP](https://github.com/colmap/gluemap)). Das bestaetigt die eigene Reihenfolge, liefert aber nichts Verkaufbares.
- **VidMap** behandelt Video nicht als Bildhaufen, sondern haelt die Herkunft jeder Verbindung fest (Punkt 4).
- **nerfstudio** zieht Videobilder laut einer Fehlermeldung schlicht zufaellig ([nerfstudio Issue 3408](https://github.com/nerfstudio-project/nerfstudio/issues/3408)). Dort ist also nichts zu holen.
- **OpenDroneMap** kombiniert OpenSfM und OpenMVS, beides unter AGPL-3.0 im Gesamtpaket ([Wikipedia](https://en.wikipedia.org/wiki/OpenDroneMap)). Nach Lesart der FSF erfasst die Lizenz eines Programms dessen Ausgabe im Regelfall nicht ([FSF](https://www.fsf.org/blogs/licensing/licensing-and-compliance-lab-the-most-frequently-asked-frequently-asked-questions)). Der Verkauf von Modellen waere also zulaessig, die Weitergabe geaenderter Programme nicht ohne Quelltext. Das ist keine Rechtsberatung.

Ein Vergleich dieser Ketten an Fassaden oder Internetfotos aus den Jahren 2023-2026 wurde ausser der GLOMAP-Arbeit nicht gefunden.

## Fazit

Die Recherche verschiebt den Blick von "welches Programm rechnet besser" zu "welche Bilder und welche Verbindungen gehen hinein". Die drei laengsten Stufen der Kette haengen am selben Rohstoff, dem Video, und fuer genau diesen Rohstoff ist 2026 die Einsicht hinzugekommen, dass die Herkunft einer Verbindung mehr wert ist als ihre Trefferzahl. Das trifft zugleich die Seitenverwechslung: Ein Clip wechselt die Turmseite nicht sprunghaft, ein Internetfoto-Paar schon. Die Punkte 1 bis 5 sind deshalb ein zusammenhaengender Umbau des Eingangs und sollten in dieser Reihenfolge gemessen werden, jeder gegen GPS-Tor und Foto-F1.

Zweitens ist die eigene Kette beim Trennen der Seiten weiter als das, was sich lizenzsauber kaufen oder laden laesst. Offen bleibt das Vereinen, und dort hilft kein Netz, sondern nur der Aussenrahmen und Brueckenbilder. Drittens bleibt bei den Putzflaechen eine ehrliche Unsicherheit: APD-MVS hat den groessten belegten Vorsprung, aber der eigene Parameterlauf hat auf dem Testfeld schon 99 % erreicht. Der Versuch entscheidet, ob das Programm Zeit spart oder nur dieselbe Flaeche anders fuellt. Fuer alle zwoelf Punkte gilt: Der veroeffentlichte Beleg endet vor dem Stadttor. Die Gegenprobe am Schwabentor mit seiner GPS-geprueften Wahrheit ist der Massstab.

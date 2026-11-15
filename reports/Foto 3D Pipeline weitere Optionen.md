# Unabhaengige Quellen schlagen neue Programme und Hardware

Der groesste Hebel ausserhalb von COLMAP ist nicht ein anderes Programm und nicht mehr Rechenleistung, sondern Material, das unsere Fehler von aussen sichtbar macht: amtliche Laserpunkte fuer Daecher und Hoehen, ein paar selbst gemessene Strecken fuer den Massstab, Schraegluftbilder der Stadt fuer die oberen Geschosse und eine Fotositzung nach festem Protokoll. Fast alles davon kostet nichts oder unter 75 EUR. Auf dem Rechner selbst sind drei kleine Aenderungen am Job-Starter dringender als jede Anschaffung: GPU-Speicher fest buchen statt messen, Ausfaelle aufs Handy melden und Platz freiraeumen (17 GB Tiefenkarten je Objekt, 16 GB Auslagerungsdatei auf der Datenplatte). Als zweite Photogrammetrie-Loesung lohnt genau ein Eintagesversuch: RealityScan, kostenlos, per Befehlszeile unter Linux, mit COLMAP-Export. Es loest die Seitenverwechslung am Turm nicht von selbst, liefert aber eine unabhaengig berechnete zweite Kameraloesung. Mieten schlaegt Kaufen deutlich: Eine 24-GB-Karte kostet 0,22 USD je Stunde, eine gebrauchte 800-950 EUR, und in den Laptop passt sie ohnehin nicht. Wichtigste Einschraenkung: Fuer keinen Programmwechsel und fuer kein Aufnahmeprotokoll gibt es eine veroeffentlichte Messung an 200-500 gemischten Fotos eines Stadttors. Die Reihenfolge unten beruht auf Kosten, Recht und Plausibilitaet, die Gewinne muessen am eigenen Material gemessen werden.

Lesehilfe: **Belegt** heisst, eine verlinkte Quelle, eine eigene Abfrage vom 15.11.2026 oder eine Pruefung am Rechner stuetzt die Aussage. **Vermutung** heisst abgeleitet, gerechnet oder Praxiswissen ohne Quelle, also erst messen. "Nur Suchtreffer" heisst: Die Quelle wurde nicht im Volltext gelesen. Nichts hiervon ist Rechtsberatung.

## Was seit heute schon laeuft und hier nicht mehr offen ist

- **CPU-Vorrang im Job-Starter (umgesetzt 15.11.2026):** `tools/job_start.sh` gibt GPU-Jobs das CPU-Gewicht 1000 und alle Kerne. Reine CPU-Jobs laufen mit Gewicht 20 auf den zwoelf langsamen Kernen 16-27. Das verhindert, dass eine CPU-Dauerrechnung der GPU die Zufuetter-Threads wegnimmt. Die Regler dahinter sind in der systemd-Doku beschrieben ([systemd.resource-control](https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html)).
- **Dichte Wolke ohne geometrischen Durchgang (umgesetzt 15.11.2026):** Standard-Stufe "schnell". Eigene Messung am Schwabentor: Median 1,8 cm Abweichung zur vollen Wolke, etwa zwei Drittel der Rechenzeit und die Haelfte des Plattenplatzes gespart. Nachteil: 4,0 statt 2,2 % Punkte auf der Strasse. Die Gegenprobe am Kaufhaus steht noch aus.
- **Aus dem ersten Bericht bleiben gueltig:** GPS-Tor nach jedem Mapperlauf, globaler Mapper mit Kalibrierung und einer Kamera je Bild, Umbau der LoD2-Ausrichtung, LIMAP als zweite Kantenquelle. Diese Punkte wiederholt dieser Bericht nicht.

## Rangliste: fuenfzehn Schritte, gereiht nach Nutzen je Aufwand

Die Bloecke A und B kosten zusammen etwa einen Tag und hoechstens 75 EUR. Die Mails aus Schritt 5 wegen der Wartezeit schon heute abschicken.

### Block A: heute am Rechner, 0 EUR

#### 1. GPU-Speicher buchen statt messen, Torch und Threads deckeln

- **Was:** Der Starter gibt Paralleljobs frei, wenn `nvidia-smi` genug freien Speicher zeigt. Zwei Jobs, die kurz nacheinander fragen, starten beide. Stattdessen ein Reservierungsbuch fuehren: unter `flock` die Budgets aller laufenden `rcpark-*`-Jobs summieren und das Maximum aus Buch und `nvidia-smi` nehmen.
- **Befehl:** Torch-Jobs die Obergrenze vom Starter mitgeben, ohne die Werkzeuge anzufassen: `-E PYTORCH_CUDA_ALLOC_CONF=per_process_memory_fraction:<Budget/8188>,expandable_segments:True`. Dazu je Job `-E OMP_NUM_THREADS=<Kerne> -E OPENBLAS_NUM_THREADS=<Kerne> -E MKL_NUM_THREADS=<Kerne>`.
- **Kosten:** rund 20 Zeilen Shell, eine Stunde mit Test.
- **Gewinn:** Kein Job kann mehr den Lauf eines anderen durch Speicherueberlauf entwerten. Er scheitert selbst und sichtbar.
- **Risiko:** COLMAP laesst sich nicht deckeln, nur ueber Bildgroesse und Merkmalszahl klein halten. COLMAP-GPU-Schritte also weiter mit gemessenem Budget fuehren.
- **Belegt:** `nvidia-smi` zeigt von Torch nur zwischengespeicherten Speicher als belegt und sieht gerade startende Jobs nicht. Die Obergrenze je Prozess gibt es als Umgebungsvariable ([PyTorch CUDA-Notizen](https://docs.pytorch.org/docs/2.15/notes/cuda.html)). Am Rechner geprueft: Abfrage im 60-s-Takt ohne Sperre zwischen Abfrage und Start. Der Standard `MemoryHigh=11G` je Job ueberbucht bei zwei Jobs die 15 GB RAM.
- **Vermutung:** Dass der Wettlauf die Ursache des naechtlichen Speicherfehlers war. Ohne Thread-Deckel startet jede numpy-Instanz 28 Rechen-Threads. NVIDIA MPS lohnt hier voraussichtlich nicht, der Engpass ist Speicher, und ein Nutzer berichtet nicht greifende Grenzen ([NVIDIA-Forum](https://forums.developer.nvidia.com/t/how-to-enforce-per-client-memory-and-sm-limits-in-cuda-mps/341976)).

#### 2. Ausfaelle sofort sehen: Winzlauf, Handy-Meldung, Neustart nur bei Zufallsfehlern

- **Was:** Die Nachtausfaelle (fehlendes Verzeichnis, doppelte Dateinamen, Tippfehler) waren Fehler, die bei jeder Wiederholung wieder auftreten. Dagegen hilft ein Pflicht-Vorablauf jeder Kette mit 3-5 verkleinerten Bildern in ein Wegwerf-Verzeichnis, Dauer unter zwei Minuten.
- **Befehl Meldung:** Vorlage `~/.config/systemd/user/rcpark-melden@.service` mit `ExecStart=/usr/bin/curl -s -H "Priority: high" -d "%i fehlgeschlagen auf %H" https://ntfy.sh/<zufaelliger-Themenname>`, im Starter `-p OnFailure=rcpark-melden@%n.service`.
- **Befehl Neustart:** `-p Restart=on-failure -p RestartSec=60 -p StartLimitIntervalSec=3600 -p StartLimitBurst=3 -p RestartPreventExitStatus="2 3"`. Die Codes 2 und 3 (falscher Aufruf, Tor nicht bestanden) duerfen nie neu starten.
- **Kosten:** 0 EUR, ein bis zwei Stunden.
- **Gewinn:** Eine leere GPU ab 06:11 wie in der Nacht faellt nach Minuten auf statt am Morgen.
- **Risiko:** Oeffentliche ntfy-Themen kann jeder lesen, der den Namen kennt. Also zufaelligen Namen waehlen und keine Pfade mit Personenbezug senden.
- **Belegt:** Das Muster mit Vorlageneinheit und `OnFailure=` ist mehrfach beschrieben ([ntfy-Kochbuch](https://jwatte.com/downloads/ntfy-phone-alerts-cookbook.md), [NixOS-Forum](https://discourse.nixos.org/t/how-to-setup-a-notification-in-case-of-systemd-service-failure/51706)). COLMAPs Tiefenkarten setzen nach Abbruch von selbst fort ([COLMAP FAQ](https://colmap.github.io/faq.html)).
- **Vermutung:** Die Neustart-Schalter stammen aus Vorwissen. Ihr Verhalten in fluechtigen `systemd-run --user`-Einheiten (zusammen mit `--collect`) vorher mit einem Dummy-Befehl testen. Ebenfalls Vermutung: ein Waechter, der bei 45 Minuten ohne neue Logzeile und leerer GPU meldet.

#### 3. Platz schaffen ohne Kauf

- **Was, in dieser Reihenfolge:**
  - Tiefen- und Normalenkarten nach bestandener Fusion und bestandenem Grundriss-Tor loeschen (rund 17 GB je Objekt, aus Bildern und Kameras wiederherstellbar).
  - Die 16-GB-Auslagerungsdatei von der Datenpartition nehmen (kleinere Datei, dazu komprimierte Auslagerung im RAM).
  - `colmap-build` (6,3 GB) bis auf die Programmdateien loeschen.
  - Abgeschlossene Objekte archivieren: `mksquashfs <verz> <objekt>.sqfs -comp zstd -Xcompression-level 15`.
- **Kosten:** 0 EUR. Loeschen nur mit Freigabe.
- **Gewinn:** aus rund 14 GB freiem Platz werden 40-50 GB.
- **Risiko:** Aenderungen an der Auslagerung vorher testen. Auslagerungsdateien auf den NTFS-Partitionen sind heikel.
- **Belegt (am Rechner geprueft, 15.11.2026):** eine einzige 477-GB-NVMe, Datenpartition 98 GB, darauf `rc-park_daten` 30 GB und `swapfile` 17 GB. Zu kleine Zwischenspeicher bei Stereo und Fusion machen COLMAP sehr langsam ([COLMAP FAQ](https://colmap.github.io/faq.html)).
- **Vermutung:** Umpartitionieren zugunsten der Datenplatte braechte bis zu 50 GB, verlangt aber eine Sicherung. Eine externe NVMe mit ext4 kostet je TB grob 110-250 USD plus Gehaeuse. Die Preisquellen widersprechen sich: guenstigste 2-TB-NVMe 209,99 USD am 19.08.2026 ([Capital & Compute](https://capitalandcompute.net/blog/why-are-ssds-so-expensive/)), andere nennen 300-480 USD ([Tech Insider](https://tech-insider.org/ssd-prices-nand-shortage-2026/)). Euro-Preise wurden nicht erhoben.

### Block B: diese Woche vom Schreibtisch, 0 bis rund 72 EUR

#### 4. Frei ladbare Plaene, Gelaende und Bilder holen

- **Kaufhaus-Plaene:** Frank Loebbecke, Alemannisches Jahrbuch 57/58, mit Erdgeschoss-Grundriss, Bauphasenplan der Fassade Schusterstrasse und Westgiebel, also genau der schlecht fotografierbaren Rueckseite. 27 Seiten, rund 49 MB, Lizenz CC BY-NC 4.0: [regionalia.blb-karlsruhe.de/files/18404/BLB_Loebbecke_Historisches_Kaufhaus.pdf](https://regionalia.blb-karlsruhe.de/files/18404/BLB_Loebbecke_Historisches_Kaufhaus.pdf).
- **Gemeinfreies Werk von 1898:** "Freiburg im Breisgau. Die Stadt und ihre Bauten", Kaufhaus ab S. 424, Martinstor um S. 202: [archive.org](https://archive.org/download/freiburgimbreisg00badi/freiburgimbreisg00badi.pdf). Ob massstaebliche Aufrisse der Tore enthalten sind, ist nicht geprueft.
- **Feineres Gelaende:** Das 25-cm-Gelaendegitter DGM025 ist laut LGL-Liste frei, feiner als das bisher genutzte DGM1 ([LGL-Datensatzliste](https://bwmm-support.lgl-bw.de/export/sites/lgl/Produkte/Open-Data/Galerien/Dokumente/Open_GeoData_Liste_Datensaetze.pdf)). Bezug ueber [opengeodata.lgl-bw.de](https://opengeodata.lgl-bw.de/), im Browser, weil die Seite nicht maschinell lesbar war.
- **Zweites LoD2:** Das Stadtmodell Freiburg (CityGML, Datenlizenz Deutschland Namensnennung 2.0) ist ein anderes Modell als das LGL-LoD2 und wurde mit Schraegluftbildern erstellt ([GDI-DE Katalog](https://gdk.gdi-de.org/geonetwork/srv/api/records/1c576440-e5e1-4095-bff1-a14d76cec6f4), Angabe aus Suchtreffer). Ein Vergleich an den drei Objekten ist eine billige Gegenprobe. Widersprueche nicht mitteln.
- **Historische Stadtplaene 1838-2020:** `https://geoportal.freiburg.de/wms/verma_stadtplan_hist/verma_stadtplan_hist?` ([Geodatenkatalog Freiburg](https://geodaten.freiburg.de/geonetwork/srv/api/records/ad1ae3cc-535a-414e-94d5-c80817500497)). Lizenz im Eintrag nicht benannt.
- **Bilder:** Wikimedia Commons hat 162 Dateien zum Schwabentor, 107 zum Martinstor und 131 zum Kaufhaus, jeweils plus Unterkategorien (eigene Abfrage 15.11.2026, [Commons API](https://commons.wikimedia.org/w/api.php)). Flickr laesst sich nach Lizenz und Umkreis filtern: `flickr.photos.search` mit `license`, `bbox` und `extras=geo,url_o,date_taken,license,owner_name` ([Flickr API](https://flickr.com/services/api/flickr.photos.search.html)).
- **Kosten:** 0 EUR, ein halber Tag. Flickr braucht einen API-Schluessel.
- **Gewinn:** Plaene sind eine von GPS, LoD2 und SfM unabhaengige Proportions- und Massstabsprobe.
- **Risiko:** Alte Plaene zeigen alte Bauzustaende (1885, 1901, 1924/25), das Schwabentor wurde oben 1954 veraendert ([Wikipedia Schwabentor](https://de.wikipedia.org/wiki/Schwabentor_(Freiburg_im_Breisgau))). Flickr-Ortsangaben sind Karten-Klicks, kein GPS.
- **Recht:** CC BY-NC erlaubt nur nicht-kommerzielle Nutzung mit Namensnennung. Beim Verkauf von Drucken waeren die Planzeichnungen ein Problem, reine Masszahlen nicht (Vermutung). Bei CC BY-SA-Bildern ist offen, ob ein daraus berechnetes Modell die Weitergabepflicht erbt. Vorsichtige Linie: solche Bilder nur fuer Kameras, Zaehlung und Gegenprobe nutzen.
- **Nicht als Sollwert nehmen:** Literaturhoehen des Martinstors schwanken zwischen 60 und 65 m, selbst innerhalb der Denkmal-Datenbank ([bauforschung-bw.de](https://www.bauforschung-bw.de/objekt/pdf/183702660413/martinstor.pdf), [Structurae](https://structurae.net/de/bauwerke/martinstor)). Die OSM-Hoehen (Schwabentor 48 m, Kaufhaus-First 19,5 m, eigene Abfrage ueber [Overpass](https://overpass-api.de/api/interpreter)) tragen keine Quelle. Brauchbare Grobproben sind nur die Grundflaechen: Martinstor 10 x 11 m, Schwabentor rund 11 m im Quadrat ([Wikipedia Martinstor](https://de.wikipedia.org/wiki/Martinstor)).

#### 5. Drei Mails: Laserpunkte, Luftbilder, Schraegbilder

- **Mail 1, Laserpunkte (wichtigste neue Quelle):** an `geodaten@lgl.bwl.de`, Kacheln ALS_3 (ersatzweise ALS_2) fuer die drei Standorte, Format LAZ, mit Koordinaten. Preis: Bereitstellungsentgelt nach Aufwand, mindestens 60 EUR zuzueglich Umsatzsteuer (bei 19 % also 71,40 EUR, eigene Rechnung; Seite gelesen am 15.11.2026). Die Daten haben mindestens 8 Punkte je Quadratmeter, sieben Klassen und Hoehen im amtlichen System ([LGL ALS_3](https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/ALS_3/index.html)). Vorher im Browser pruefen, ob das Open-Data-Portal sie inzwischen direkt anbietet.
- **Mail 2, Luftbilder:** an dieselbe Adresse, Frage nach Preis, Format und Lizenz von DOP10 (10 cm Aufloesung, Lage im Mittel plus/minus 0,25 m) und des Produkts "Orientierte Luftbilder", also Luftbilder mit amtlich bestimmter Kameraposition ([LGL DOP10](https://www.lgl-bw.de/Produkte/Luftbildprodukte/DOP10/index.html)). Dazu fragen, ob die Freiburger Kachel schon ein TrueDOP ist. Die LGL-Seiten nennen dafuer zwei verschiedene Jahre (2020 und Sommer 2025).
- **Mail 3, Stadt Freiburg:** an `vermessung@freiburg.de` (Sachgebiet Geoinformation) und `gdi-support@freiburg.de`. Fragen: Jahrgang, Aufloesung und Lizenz der Schraegluftbilder und des 3D-Netzes im Portal, Zugang zu den Strassenpanoramen ("Cycloramen"), vorhandene Aufmasse der Sanierungen ([GDI-BW](https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/f4c62c54-4a27-409b-9e82-a55cb4783801)). Parallel das Export-Werkzeug auf [3d.freiburg.de](https://3d.freiburg.de/) ausprobieren: Schraegbilder aus vier Himmelsrichtungen, Netz und Gelaende, hoechstens 150.000 m2 je Abfrage, der Download-Link kommt per E-Mail ([Hilfeseite](https://3d.freiburg.de/templates/de/info.html)).
- **Gewinn:** Firstlinien, Traufhoehen, Helmspitze und Dachneigung unabhaengig von allen Fotos. Auf einem 11 x 11 m grossen Turmdach liegen rechnerisch knapp 1000 Laserpunkte, genug fuer Dachebenen, zu wenig fuer Gauben und Ecktuermchen (Vermutung, eigene Rechnung). Die Schraegbilder zeigen genau die oberen Geschosse und die ungesehene Seite.
- **Risiko:** Wartezeit. Ob der Export ohne Anmeldung geht und unter welcher Lizenz, steht nirgends. Ein fertiges Detailmodell (LoD3) der drei Objekte wurde bei Stadt und Land nicht gefunden.
- **Wichtig fuer die Tore:** Das LGL-LoD2 wird aus den Kataster-Grundrissen plus Laserhoehen berechnet ([Runder Tisch GIS](https://katalog.rundertischgis.de/en/dataset/3d-gebaudemodelle-lod2-b-w)). Kataster-Umring und LoD2 zaehlen deshalb als EINE Quelle. Laserwolke und Luftbild sind dagegen unabhaengig.
- **Weitere Anfragewege (Vermutung, ob Material herausgegeben wird):** Landesamt fuer Denkmalpflege (bauhistorische Untersuchung Kaufhaus, [bauforschung-bw.de](https://www.bauforschung-bw.de/objekt/id/105442839812/weitere-seite/2/historisches-kaufhaus-in-79098-freiburg-altstadt/)), Stadtarchiv, Muensterbauhuette, Fernleihe von Schuchard, "Carl Schaefer" (1979), S. 311 f., fuer die Tor-Umbauten von 1901.

#### 6. Mapillary-Abdeckung pruefen, Panoramax und Google abhaken

- **Was:** Mapillary liefert als einzige offene Quelle je Bild eine berechnete Position, Blickrichtung, Kameraparameter und den Massstab der Rekonstruktion ([Mapillary API](https://www.mapillary.com/developer/api-documentation)).
- **Befehl:** mit eigenem Zugangsschluessel je Objekt `graph.mapillary.com/images?bbox=<W,S,O,N>&fields=id,captured_at,is_pano,camera_type,computed_geometry` (Kasten kleiner als 0,01 Grad).
- **Kosten:** 0 EUR, eine Stunde.
- **Gewinn (Vermutung):** ein vom eigenen Handy-GPS unabhaengiger Lage- und Massstabshinweis. Genauigkeit unbekannt, also nur als Tor.
- **Recht:** Bilder CC BY-SA, automatisches Abgrasen ausserhalb der API ist untersagt ([Mapillary Terms](https://mapillary.com/legal)).
- **Belegt, bereits erledigt:** Panoramax hat in der Altstadt 464 Bilder, aber keines im Umkreis von rund 80 m um die drei Objekte (eigene Abfrage 15.11.2026: [api.panoramax.xyz](https://api.panoramax.xyz/api/search?bbox=7.846,47.989,7.858,47.998&limit=500)).
- **Gesperrt:** Google Street View, Google 3D Tiles und Google Earth verbieten Export, Bildanalyse und das Ableiten von 3D-Modellen ausdruecklich ([Google Map Tiles Policies](https://developers.google.com/maps/documentation/tile/policies)). Apple verbietet Extraktion und abgeleitete Werke ([Apple Maps Terms](https://www.apple.com/legal/internet-services/maps/terms-en.html)).

### Block C: die naechste Fotositzung (45 Minuten vor Ort)

#### 7. Massstab mit dem Laser-Distanzmesser, Lage ueber Bodenpunkte

- **Was:** Je Gebaeude mindestens vier waagrechte Strecken von 8-12 m und zwei senkrechte von 3-6 m zwischen scharfen, im Foto wiederfindbaren Punkten messen, jede zweimal. Jeden Endpunkt fotografieren. Ablage als `masse_vor_ort.json` neben den Fotos, damit die Kette die Strecken als Tor pruefen kann.
- **Lage:** Vier bis sechs Fotos genau ueber Bodenpunkten, die im amtlichen Luftbild wiederzufinden sind (Kanaldeckel, Bordsteinecke). Deren Koordinaten in eine Textdatei `bildname X Y Z`, dann `colmap model_aligner --ref_is_gps 1 --alignment_type enu --alignment_max_error 1`. Der Befehl braucht mindestens drei Bilder ([COLMAP FAQ](https://colmap.github.io/faq.html)).
- **Kosten:** zehn Minuten je Sitzung. Der Preis eines Distanzmessers wurde nicht erhoben.
- **Gewinn (Vermutung, eigene Rechnung):** Massstab auf etwa 0,05 % statt mehrerer Prozent aus GPS, also rund 2 cm auf 40 m Turmhoehe. Lage auf 0,2-0,5 m statt 3-10 m.
- **Risiko:** Die Punkte muessen im Foto eindeutig sein. Handy-GPS trotzdem mitschreiben, aber im `pose_prior_mapper` mit 5-10 m Unsicherheit statt des Standards von 1 m.
- **Belegt:** Die CIPA-Regeln verlangen an allen Gebaeudeseiten lange gemessene Strecken, mindestens eine senkrechte und eine waagrechte ([CIPA 3x3](https://www.cipaheritagedocumentation.org/wp-content/uploads/2017/02/CIPA__3x3_rules__20131018.pdf)). Handy-Lidar ist dafuer schlechter: an Fassaden rund 4,6 cm Fehler ([EGU26-2752](https://meetingorganizer.copernicus.org/EGU26/EGU26-2752.html)), und das iPhone 11 hat keines.

#### 8. Aufnahmeprotokoll fuer den symmetrischen Turm

- **Ringe (belegt):** mindestens 60 % Ueberlappung, an jeder Ecke Bilder, die beide Nachbarseiten zeigen, Boden- und Himmelslinie im Bild ([CIPA 3x3](https://www.cipaheritagedocumentation.org/wp-content/uploads/2017/02/CIPA__3x3_rules__20131018.pdf)). Besser 80 % laengs und 60 % quer ([Agisoft](https://agisoft.freshdesk.com/support/solutions/articles/31000149337)). Kamera zwischen den Bildern bewegen, nicht am Ort drehen ([COLMAP Tutorial](https://colmap.github.io/tutorial.html)).
- **Gegen Seitenverwechslung (belegt ist nur das Problem):** Gleich aussehende Seiten erzeugen falsche Bildpaare ([Doppelgangers](https://arxiv.org/pdf/2309.02420)). Agisoft raet zu mehr Unverwechselbarem im Bild und dichteren Ecken.
- **Abgeleitetes Protokoll (Vermutung, fuer einen Turm 12 x 12 x 40 m):**
  - Naher Ring im Uhrzeigersinn, seitlicher Schritt ein Viertel des Wandabstands, je Standpunkt zwei bis drei Neigungen im Hochformat.
  - An jeder Ecke ein Faecher aus 7-9 Bildern.
  - Ferner Ring aus 25-60 m mit den Nachbarhaeusern im Bild.
  - Verbindungsbilder zwischen den Ringen, Rundgang 10-15 Bilder ueber den Start hinaus.
  - In jedem Ringbild ein Viertel bis ein Drittel Umgebung, je Seite ein anderer auffaelliger Gegenstand am Boden.
  - Zusammen 250-400 Bilder in 30-45 Minuten.
- **Einstellungen (belegt):** nicht zoomen, Fokus je Ring fest, volles Bildformat, kein Zuschnitt, je Brennweite eine eigene Kameragruppe ([CIPA 3x3](https://www.cipaheritagedocumentation.org/wp-content/uploads/2017/02/CIPA__3x3_rules__20131018.pdf), [Agisoft](https://agisoft.freshdesk.com/support/solutions/articles/31000149337)). Nur die Hauptkamera, Ultraweit hoechstens als getrennter Ordner.
- **Einstellungen (Vermutung):** HDR, Nachtmodus und KI-Schaerfung aus, Verschlusszeit 1/250 s oder kuerzer, Weissabgleich fest. Eine Studie, die Handy-HDR gegen Rekonstruktionsgenauigkeit prueft, wurde nicht gefunden. Unter Android bietet Open Camera Sperren und Rohformat ([Open Camera](https://opencamera.org.uk/help.html)).
- **Originale sichern:** nie ueber die Chat-Fotofunktion, nur per Kabel oder als Datei (WhatsApp-Verhalten aus Drittquelle, nur Suchtreffer: [fast.io](https://www.fast.io/resources/whatsapp-telegram-signal-photo-metadata-preservation/)). Kontrolle am Rechner: `exiftool -n -FocalLength -FocalLengthIn35mmFormat -GPSLatitude -ImageSize -LensModel <ordner>`. Abweichler sind Linsenwechsel oder Zuschnitte.
- **Licht (belegt):** gleichmaessiges, diffuses Licht, keine tiefen Schatten, keine Spiegelungen ([COLMAP Tutorial](https://colmap.github.io/tutorial.html), [Agisoft](https://agisoft.freshdesk.com/support/solutions/articles/31000149337)). Vermutung: hell bedeckt, frueher Sonntagmorgen, laubfreies Halbjahr, den ganzen Ring in einem Lichtzustand.
- **Video (belegt):** Zeilenweise Belichtung verzerrt bei Bewegung ([Vautherin et al.](https://isprs-annals.copernicus.org/articles/III-3/139/2016/isprs-annals-III-3-139-2016.pdf), nur Suchtreffer). Vermutung: Das erklaert die Geisterwand der Nacht. Video hoechstens als Verbindungsfaden zwischen Foto-Ringen, nie als Quelle fuer Kanten.
- **Kontrolle vor dem Gehen (Schwellen sind eigene Setzung):** je Seite mindestens 25 Ringbilder, je Ecke mindestens 7, Rundgang geschlossen, jedes zehnte Bild und alle Detailbilder bei 100 % auf Schaerfe geprueft, in der Kartenansicht liegen die Bilder als Ring. CIPA verlangt die Vollstaendigkeitspruefung vor Verlassen des Orts.
- **Kosten:** 0 EUR. **Gewinn (Vermutung):** Die meisten Fehler der Nacht, also Chat-Kopien ohne EXIF, Videobilder und der falsch angesetzte Rundgang-Abschnitt, entstehen gar nicht erst.

#### 9. Obere Turmhaelfte: Abstand und Tele statt Stab

- **Rechnung (Vermutung):** Aus 10 m Abstand erscheint die Traufe in 40 m Hoehe in der Senkrechten mit rund 58 mm je Pixel. Gesimskanten sind so nicht messbar. Aus 80 m mit Dreifach-Tele sind es rund 10 mm je Pixel bei fast frontalem Blick.
- **Was:** Fernstandpunkte entlang aller Strassenachsen (30-100 m), je Standlinie 5-10 Bilder mit 3-5 m seitlichem Versatz, Tele als eigener Ordner mit eigenem Kameramodell. Vom selben Standpunkt immer auch ein Bild der Hauptkamera. Dazu erhoehte oeffentliche Standpunkte, etwa Schlossberg fuer das Schwabentor und Muensterturm fuer das Kaufhaus (Zugaenglichkeit nicht geprueft).
- **Stab:** Ein Teleskopstab von 4-6 m verbessert Erker, Gesimse und Arkaden, aendert den Blick auf eine 40-m-Traufe aber nur um wenige Grad. Stab-Aufnahmen an Fassaden sind in der Literatur beschrieben ([ISPRS 2012, Amiens](https://isprs-archives.copernicus.org/articles/XXXIX-B5/559/2012/isprsarchives-XXXIX-B5-559-2012.pdf), nur Suchtreffer). Genauigkeitszahlen wurden nicht gefunden.
- **Belegt:** COLMAP verlangt je Brennweite ein eigenes Kameramodell und fuer ferne Aufnahmen einen kleineren Mindest-Schnittwinkel ([COLMAP FAQ](https://colmap.github.io/faq.html)).
- **Kosten:** 0 EUR. Der Preis eines Stabs wurde nicht erhoben. **Recht:** kein Luftrecht beruehrt.

### Block D: Eintagesversuche am Rechner

#### 10. RealityScan als zweite, unabhaengige Kameraloesung (ein Tag)

- **Was:** Das frueher RealityCapture genannte Programm von Epic nur bis zur Kameraberechnung laufen lassen, als COLMAP-Format mit entzerrten Bildern exportieren, dann die eigenen Tore und den eigenen Kanten-Sweep darauf rechnen.
- **Kosten und Lizenz:** kostenlos fuer Personen und Firmen unter 1 Mio. USD Jahresumsatz, alle Funktionen, darueber 1.250 USD je Platz und Jahr ([Lizenzseite](https://www.realityscan.com/en-US/license)).
- **Technik (belegt):** eigene Linux-Fassung fuer die Befehlszeile, Status "experimentell", mindestens 8 GB Grafikspeicher und 16 GB RAM, empfohlen Ubuntu 24.04 ([RealityScan for Linux](https://dev.epicgames.com/documentation/en-us/realityscan/realityscan-for-linux)). Der Rechner hat 8 GB und 15 GB, liegt also an bzw. knapp unter der Untergrenze. Ausweg ist die Windows-Partition.
- **Befehle (woertlich aus der Epic-Liste):** `headless`, `newScene`, `addFolder`, `align`, `mergeComponents`, `selectMaximalComponent`, `exportRegistration`, `importColmap`, `defineDistance`, `importGroundControlPoints`, `save`, `quit` ([All Commands](https://dev.epicgames.com/documentation/realityscan/all-commands)).
- **Messen:** Zeit bis zu den Kameras, Zahl der Teilmodelle und der registrierten Bilder, GPS-Tor am bekannten Fehlabschnitt, Verhalten der Bilder ohne EXIF, Foto-F1 des Kanten-Sweeps mit diesen Kameras.
- **Gewinn:** Widersprechen sich die RealityScan- und die COLMAP-Loesung, ist eine davon falsch. Genau so eine Gegenprobe fehlt am Kaufhaus, wo der Vergleich der beiden COLMAP-Mapper unentschieden blieb und das iPhone-GPS als Schiedsrichter ausfiel (eigene Messung 15.11.). Zweiter moeglicher Nutzen (Vermutung): die eigene Loesung mit `importColmap` laden und nur die schnelle Netzberechnung als Ersatz fuer die Tiefenkarten nutzen.
- **Risiko:** Ein Nutzer berichtet, dass selbst entzerrte Bilder das Sichtfeld von RealityScans eigener Entzerrung nie genau treffen ([Epic-Forum](https://forums.unrealengine.com/t/reality-scan-image-undistortion/2574748), nur Suchtreffer). Deshalb immer die entzerrten Bilder mit uebernehmen. Der genaue Exportbefehl fuer COLMAP ist nicht bestaetigt, die Quellen widersprechen sich beim Befehlsnamen. Anmeldung und Lizenztext der Linux-Fassung waren nicht abrufbar. Entzerrte Kopien von 500 Bildern kosten mehrere GB, also erst Schritt 3.
- **Vermutung:** dass RealityScan am symmetrischen Turm besser abschneidet. Kein Hersteller dokumentiert einen Filter gegen Seitenverwechslung, und eine unabhaengige Vergleichsmessung an Tuermen wurde nicht gefunden.

#### 11. Dichte Wolke auf einer Mietkarte rechnen (nur bei Bedarf)

- **Preise (RunPod, Stand der Preisseite 12.11.2026, je Stunde):** RTX 3090 mit 24 GB 0,22 USD, RTX A5000 mit 24 GB 0,16 USD, RTX 4090 0,34 USD. Speicher 0,07-0,10 USD je GB und Monat ([RunPod Preise](https://www.runpod.io/pricing)).
- **Kosten je Objekt (Vermutung):** 0,20-0,70 USD. 5 GB Fotos brauchen bei 20 Mbit/s rund 35 Minuten: `rsync -P <fotos> <mietrechner>:`. Zurueck kommen nur Kameras, die verschmolzene Wolke und Logs, nicht die 17 GB Tiefenkarten.
- **Gewinn:** loest zugleich das Plattenproblem und erlaubt die feine Stufe mit geometrischem Durchgang ohne Speicherdruck. Mehrere Objekte parallel in einer Nacht.
- **Risiko:** Ein eigenes Abbild mit genau der lokalen COLMAP-Version ist noetig, sonst sind Ergebnisse nicht vergleichbar. Wie viel schneller die Karte wirklich ist, ist ungemessen. Die guenstige Stufe laeuft auf Rechnern Dritter: fuer Fotos oeffentlicher Gebaeude unkritisch, bei fremden Bildern mit Personen abwaegen.
- **Einordnung:** Die Rechenzeit (rund 15 Minuten bis zu den Kameras, mit der schnellen Stufe unter einer Stunde dicht) rechtfertigt Miete nicht als Dauerloesung. Der Engpass ist Zuverlaessigkeit und Platz.

#### 12. MapAnything als metrische Gegenprobe (halber Tag)

- **Befehl:** `python scripts/demo_inference_on_colmap_outputs.py --colmap_path <colmap-ausgabe> --viz` auf 50-100 Bildern einer Fassade ([MapAnything](https://github.com/facebookresearch/map-anything)).
- **Lizenz:** Code Apache 2.0. Nur das Gewicht `facebook/map-anything-apache` ist frei nutzbar, das Standardgewicht ist nicht-kommerziell.
- **Gewinn (Vermutung):** unabhaengige Massstabs- und Lagepruefung, weil das Modell Geometrie in Metern ausgibt.
- **Risiko:** Der Sparmodus ist mit "bis 2000 Bilder auf 140 GB" angegeben. Auf 8 GB waeren das grob 100 Bilder (eigene Hochrechnung). Abbruch, wenn der Speicher nicht reicht. Eine Vergleichsstudie von 2026 bescheinigt gelernten Verfahren groessere Restfehler als COLMAP ([ISPRS Annals 2026](https://isprs-annals.copernicus.org/articles/XI-2-2026/721/2026/)). Also nie als Kameraquelle fuer die Kanten.

#### 13. Die Kette als Snakemake-Datei, sobald sie je Objekt feststeht

- **Befehl:** `snakemake --cores 28 --resources vram_mb=7000 --retries 2 --keep-going --rerun-incomplete`. Jede Regel nennt ihren Bedarf (`resources: vram_mb=...`) und ruft die vorhandenen Werkzeuge auf.
- **Gewinn:** Abhaengigkeiten, Wiederholung, Wiederaufnahme, automatisches Loeschen von Zwischenergebnissen (`temp()`) und Pruefung leerer Ausgaben (`ensure`) aus einer Hand ([Snakemake](https://snakemake.readthedocs.io/en/stable/snakefiles/rules.html)). Waehrend CPU-Stufen von Objekt A laeuft die GPU-Stufe von Objekt B.
- **Risiko:** Snakemake zaehlt Ressourcen nur und sperrt nichts ([FlowDeploy](https://flowdeploy-website.pages.dev/snakemake-resources)). Die Deckel aus Schritt 1 bleiben noetig. Die Schalter `--rerun-incomplete` und `--keep-going` sowie die Lizenz wurden nicht an der Doku geprueft.
- **Alternative:** pueue mit zwei Gruppen (`pueue parallel 1 --group gpu`) ist kleiner, kennt aber weder Speichermengen noch automatische Wiederholung ([pueue](https://github.com/Nukesor/pueue)).
- **Kosten:** ein bis zwei Tage. Erst nach Schritt 1 und 2 sinnvoll.

### Block E: nur wenn eine Luecke bleibt

#### 14. 360-Grad-Kamera am Stab als Geruest

- **Belegt:** COLMAP verarbeitet Rundumbilder seit Version 3.12 als Verbund virtueller Kameras, Beispielskript `python/examples/panorama_sfm.py`, Installation `pip install 'pycolmap[panorama]'` ([COLMAP Rigs](https://colmap.github.io/rigs.html)).
- **Vermutung:** Eine 8K-Rundumkamera loest nur etwa ein Drittel so fein auf wie die Handy-Hauptkamera, bei 10 m Abstand rund 8 mm statt 3,4 mm je Pixel. Gut gegen Seitenverwechslung, weil jedes Bild alle Nachbarhaeuser sieht. Unbrauchbar fuer Details. Ob Handyfotos sich zuverlaessig an ein solches Geruest anhaengen lassen, ist ungetestet. Kamerapreise wurden nicht erhoben.

#### 15. Drohne unter 250 g, nur fuer Dach und Helm

- **Belegt:** Mit Kamera ist auch unter 250 g die Registrierung beim Luftfahrt-Bundesamt Pflicht, dazu Haftpflicht, hoechstens 120 m, keine Menschenansammlungen ([ADAC, Stand 27.10.2026](https://www.adac.de/verkehr/recht/verkehrsvorschriften-deutschland/drohnen-fuehrerschein-registrierung/)). Ueber Wohngrundstuecken gilt die Gewichts-Ausnahme nur ohne Kamera, sonst braucht es die Zustimmung. 100 m Abstand zu Bahnanlagen, Behoerden und Krankenhaeusern ([Paragraf 21h LuftVO](https://www.gesetze-im-internet.de/luftvo_2015/__21h.html)).
- **Kosten:** geografische Allgemeinerlaubnis 200 EUR, zwei Jahre gueltig, 2-14 Tage Bearbeitung. Einzelerlaubnis rund 250 EUR, 2-6 Wochen. Zustaendig ist das Regierungspraesidium Stuttgart, Referat 46.2, `bnl@rps.bwl.de` ([RP Baden-Wuerttemberg](https://rp.baden-wuerttemberg.de/themen/verkehr/luft/seiten/drohnen)). Vorab die amtliche Karte auf dipul.de pruefen.
- **Risiko:** Ob Strassenbahngleise als Bahnanlagen zaehlen, ist ungeklaert. Falls ja, ist ein Flug an beiden Toren ohne Zustimmung des Betreibers nicht moeglich. Tore und Kaufhaus gehoeren der Stadt, also dort anfragen.
- **Einordnung:** Erst wenn Laserpunkte, Schraegbilder und Fernstandpunkte (Schritte 5 und 9) Dach und Helm nicht liefern.

## Was nicht lohnt, und warum

- **Metashape:** Die Skript-Schnittstelle gibt es nur in der Professional-Ausgabe fuer 3.499 USD, Standard kostet 179 USD ([Agisoft Store](https://www.agisoft.com/buy/online-store/)). Ob eine Testlizenz Skripte freischaltet, ist nicht belegt. Beim COLMAP-Export sind laut einem Community-Handbuch zwei Verzeichnungswerte vertauscht und der Bildmittelpunkt um einen halben Pixel verschoben, richtig erst ab Version 2.3.0 ([Metashape Expert Manual](https://photogrammetrycommunity.github.io/metashape-expert-manual/workflow/camera-calibration/distortion-model-opencv-colmap/)). Das ist genau die Groessenordnung, auf die der Kanten-Sweep empfindlich ist.
- **3DF Zephyr:** nur Windows, die freie Ausgabe endet bei 50 Fotos, Kameraexport erst ab 4.200 EUR plus Mehrwertsteuer ([3Dflow](https://www.3dflow.net/3df-zephyr-photogrammetry-software/)).
- **OpenDroneMap:** auf Drohnenraster mit GPS ausgelegt. Die Gemeinschaft berichtet Probleme bei Bodenaufnahmen mit schlechtem GPS ([ODM Community](https://community.opendronemap.org/t/what-is-your-biggest-pain-with-odm-opensfm/25791?page=2), nur Suchtreffer).
- **Meshroom:** frei und unter Linux lauffaehig ([Meshroom 2025.1](https://github.com/alicevision/Meshroom/releases/tag/v2025.1.0)), aber ohne belegten Vorteil. Ein Vergleich sah es hinter COLMAP: 0,868 gegen 0,441 mm, Metashape 0,212 mm ([Sensors 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8659967/table/sensors-21-08026-t004), nur Suchtreffer, Kleinobjekt). Diese Zahlen messen die dichte Wolke, nicht die Kameras, und die Wolke ist bei uns nur Lage-Veto.
- **Gebrauchte 24-GB-Karte:** RTX 3090 fuer 800-950 EUR ([borncity](https://borncity.com/news/nvidia-rtx-3090-der-ungekroente-ki-koenig-des-gebrauchtmarkts/)). Der Rechner ist ein Laptop, sie ginge nur als externe Karte ueber Thunderbolt (am Rechner geprueft). Die Gewinnschwelle gegen Miete liegt bei rund 4000 GPU-Stunden (eigene Rechnung).
- **Hetzner-GPU-Server:** Monatsmiete, GEX44 232,30 EUR ohne Mehrwertsteuer plus 114 EUR Einrichtung, gueltig ab 15.06.2026 ([Hetzner](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)). Unpassend fuer gelegentliche Laeufe.
- **Ausgleichsrechnung auf die GPU:** Bei kleinen Problemen ist die CPU schneller ([Theseus](https://arxiv.org/pdf/2207.09442)). Billiger (Vermutung): die Wolke vor dem Fit auf ein 5-cm-Gitter ausduennen und den Suchbaum nur einmal bauen.
- **Verbraucher-Cloud-Apps und Splatting-Programme:** geben Netze oder Bildsynthesen aus, keine Kameras (Schluss aus fehlenden Belegen). Fuer die Kernmethode wertlos.

## Fazit

Die erste Recherche hat gezeigt, dass jeder teure Fehler in sich stimmig aussah und erst an einer unabhaengigen Quelle auffiel. Die zweite zeigt, wie duenn diese unabhaengigen Quellen bisher sind: Am Kaufhaus versagte das iPhone-GPS als Schiedsrichter, LoD2 und Kataster-Umring sind in Wahrheit dieselbe Quelle, und die Literaturhoehen der Tore streuen um fuenf Meter. Die Schritte 4, 5, 7 und 10 liefern zusammen vier neue, voneinander unabhaengige Schiedsrichter: Plaene, Laserpunkte, gemessene Strecken und eine zweite Kameraloesung. Damit laesst sich erstmals entscheiden, welcher Mapper am Kaufhaus recht hat.

Drei Fragen kann nur das eigene Material beantworten. Erstens, ob das Aufnahmeprotokoll die Seitenverwechslung wirklich verhindert, denn es ist abgeleitet und nicht gemessen. Zweitens, ob RealityScan auf 8 GB Grafikspeicher und 15 GB RAM ueberhaupt durchlaeuft. Drittens, was die Stadt Freiburg an Schraegbildern und Strassenpanoramen herausgibt und unter welcher Lizenz. Die Antwort auf die dritte Frage entscheidet, ob Stab, Rundumkamera und Drohne ueberhaupt noetig werden.

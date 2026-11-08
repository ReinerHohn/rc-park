# Offene/lizenzierbare Geodaten und Bilder fuer Freiburg i. Br. (Stand Recherche 2026-11-05)

Schon in Benutzung (nicht erneut bewertet): LGL LoD2 CityGML, LGL DOM1/DGM1, Mapillary, Wikimedia Commons, YouTube-Drohnenframes.

## 1. LGL BW Open Data (seit 06.06.2024): DOP, True-DOP, DOP10, bDOM, Laserpunktwolken, Schraegluftbilder, Mesh

### Takeaway
Seit Juni 2024 ist ein Grossteil der LGL-Geobasisdaten kostenlos unter DL-DE BY 2.0 erhaeltlich, auch fuer kommerzielle Nutzung. Fuer Detailrekonstruktion zaehlen vor allem: **bDOM 0,2-m-Raster bzw. LAS/LAZ aus Bildkorrelation** (Open Data, nur per E-Mail-Bestellung, 60 EUR Servicegebuehr), **ALS-Punktwolken mit mindestens 8 Pkt/m2** (LAS/LAZ, Bestellung per E-Mail, Open-Data-Status auf der Produktseite nicht klar angegeben) und **DOP20 als True-DOP seit Sommer 2025**. DOP10 ist nicht Open Data (Datenschutz). Ein LGL-Produkt mit Schraegluftbildern oder 3D-Mesh habe ich fuer BW nicht gefunden.

### Cited Findings
- Pressemitteilung MLW vom 06.06.2024: "ein Großteil" der Geobasisdaten ist ab sofort kostenlos (Liegenschaftskataster, Gelaende-/Oberflaechen-/Landschaftsmodelle, 3D-Gebaeudemodelle, Luftbilder, digitale Karten). Nutzung und Verarbeitung "für kommerzielle und nicht-kommerzielle Zwecke" sind erlaubt. Ausgenommen sind Daten mit Datenschutzkonflikt, mit geistigem Eigentum Dritter oder mit amtlichem Nachweischarakter. Zugang ueber opengeodata.lgl-bw.de und geoportal-bw.de — [MLW PM](https://mlw.baden-wuerttemberg.de/de/service/presse-und-oeffentlichkeitsarbeit/pressemitteilung/pid/land-stellt-geobasisdaten-kostenlos-zu-verfuegung)
- Lizenz: Datenlizenz Deutschland – Namensnennung – 2.0. Pflicht-Quellenvermerk: „Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0“. Fuer Datensaetze, die keine High-Value-Datensaetze sind, kann das LGL in Einzelfaellen Grenzkosten verlangen. Individuelle Abgaben kosten ein „aufwandsabhängiges Service-Entgelt“ — [LGL Open GeoData](https://www.lgl-bw.de/Produkte/Open-Data/index.html)
- Im Open-GeoData-Portal (https://opengeodata.lgl-bw.de) liegen DOP20, DGM025/DGM1, DOM1/DOM5, nDOM, LoD1/LoD2 und DTK. Historische DOP gibt es nur als WMS, nach Dekaden von 1950-59 bis 2020-29. **bDOM nur per E-Mail an die Kundenbetreuung** — [LGL Open GeoData](https://www.lgl-bw.de/Produkte/Open-Data/index.html)
- **bDOM** (bildbasiertes DOM): regelmaessiges **0,2-m-Raster** aus Luftbildern mit 20 cm Bodenaufloesung, ein Hoehenpunkt pro Pixel. Laut LGL feiner aufgeloest als DOM1, aber "nicht qualitaetsgesichert". Formate LAZ/LAS (mit Farbe, z. B. RGBI) oder ASCII-XYZ. Bestellung per E-Mail an geodaten@lgl.bwl.de mit Gebiet in ETRS89/UTM oder als Shapefile. „bDOM als Geodaten ist Open Data“. Servicegebuehr **60 EUR**. Erstbestand 2017-2019, danach laufend aus der jeweils letzten Befliegung fortgefuehrt — [LGL bDOM](https://www.lgl-bw.de/Produkte/3D-Produkte/Digitale-Oberflaechenmodelle/bDOM/)
- **DOP10**: 10 cm, landesweit, ab 2011, aktuell im 2-Jahres-Zyklus. DOP sind **seit Sommer 2025 True-DOP**. Ab 2026 werden DOP10 und DOP20 in einer gemeinsamen Befliegung aufgenommen. Bilder mit 10 cm und feiner "dürfen nicht im Internet präsentiert werden" (Datenschutz), deshalb kein Open Data. RGBI und Graustufen gibt es auf Anfrage per E-Mail. Unentzerrte Luftbilder gibt es als Stufe "Digitales (Orientiertes) Luftbild" (Stereopaare werden nicht erwaehnt). Preistabelle nur als Bild; Download bis 5 GB, groessere Mengen auf Datentraeger gegen Aufpreis — [LGL DOP10](https://www.lgl-bw.de/Produkte/Luftbildprodukte/DOP10/)
- DOP20 ist "in der Regel Open Data" — [LGL DOP20](https://www.lgl-bw.de/Produkte/Luftbildprodukte/DOP20/index.html)
- PM vom 14.11.2022: Befliegung alle 2 statt 3 Jahre (jedes Jahr die halbe Landesflaeche), True-Orthofotos mit 10-20 cm, erstmals 3D-Oberflaechenmodelle aus Luftbildern (= bDOM) — [BW PM 2022](https://www.baden-wuerttemberg.de/de/service/presse/pressemitteilung/pid/luftbilder-und-oberflaechenmodelle-in-neuer-qualitaet-1)
- **ALS-Punktwolken**: ALS_1 (2000-2005) mit etwa 0,8 Pkt/m2 und ±20 cm. ALS_2 (2016-2021) mit **≥8 Pkt/m2** und ±15 cm, 2022 fuer etwa 80 % der Landesflaeche verfuegbar. Formate ASCII/LAS/LAZ, Bestellung ueber geodaten@lgl.bwl.de — [LGL Newsletter 2022-4](https://www.lgl-bw.de/Ueber-Uns/Newsletter/Galerien/Dokumente/2022-4_LGL_ALS_Laserscanbefliegungen.pdf). ALS_3 laut Suchtreffer ebenfalls ≥8 Pkt/m2 als LAS/LAZ — [LGL Newsletter 2024-04](https://lgl-bw.de/Ueber-Uns/Newsletter/Galerien/Dokumente/2024-04_ALS.pdf) (PDF nicht lesbar abgerufen, nur Suchsnippet). Die Produktseite sagt: ALS_3 "wird derzeit aufgebaut und ist in Teilen bereits verfügbar", ALS_1 wird nicht fortgefuehrt. Open-Data-Status und Preis stehen dort nicht — [LGL Laserscandaten](https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/)
- Community-Tabelle: BW LAZ 1.2, EPSG 25832, 8 Pkt/m2 (2016-2021) — [wiesehahn gist](https://gist.github.com/wiesehahn/b26e2ddbf0b8c3e7b2b0d450b52c8a7b)
- LoD2: CityGML ist Open Data. 3D-PDF/DXF/KML/SHP/SketchUp sind kostenpflichtig — [LGL LoD2](https://www.lgl-bw.de/Produkte/3D-Produkte/3D-Gebaeudemodelle/LoD2/index.html)
- Schraegluftbilder: kein BW-LGL-Produkt gefunden. Gefunden habe ich nur Niedersachsen (LGLN, Testgebiet Hildesheim mit Punktwolke, True-Ortho und Mesh) — [LGLN Schraegluftbilder](https://www.lgln.niedersachsen.de/download/147825/Schraegluftbilder.pdf)

### Inferences
- **bDOM (0,2 m, Farbe) ist der naechste Hebel gegenueber DOM1 (1 m):** 25-fache Zelldichte. Damit werden Gauben, Erker und Dachkanten im Bereich 1-3 m sichtbar, fuer die DOM1 blind ist. Grenzen: Bildkorrelation glaettet steile Helmflaechen und Schattenzonen, und das LGL nennt die Daten "nicht qualitaetsgesichert". Deshalb nach Projektregel 4/5 als eigene Quelle mit eigener Blindheit fuehren und nicht mit DOM1 mitteln. Kosten fuer die Altstadtkachel: 60 EUR.
- Die ALS_2-Rohpunkte (≥8 Pkt/m2, also etwa 35 cm Punktabstand) liefern mehr als das 1-m-DOM1-Raster: Mehrfachechos an Traufkanten, Trennung von Turm und Dach. Fuer Fassaden bleiben sie trotzdem blind.
- True-DOP20 (seit 2025) beseitigt die Gebaeudekippung im Ortho. Daraus lassen sich Fussabdruck und Traufkante direkt messen.

### Gaps
- Kein Open-Data-Status und kein Preis fuer die ALS-Punktwolken auf der LGL-Seite. Die Vergleichs-PDF ALS_1/2/3 habe ich nicht gelesen. Unklar ist, wann ALS_2 bzw. ALS_3 ueber Freiburg geflogen wurde. Vor der Bestellung per E-Mail nachfragen.
- Die DOP10-Preise stehen nur als Bild auf der Seite. Ob die orientierten Einzelluftbilder (Stereo und Kamerapose) einzeln bestellbar sind und was sie kosten, ist unbekannt. Sie waeren fuer MVS sehr wertvoll.
- Keine Belege fuer ein LGL-3D-Mesh, fuer LoD2 mit Texturen oder fuer LGL-Schraegluftbilder in BW.

## 2. Stadt Freiburg (FreiGIS / 3d.freiburg.de): 3D-Stadtmodell, texturiertes Mesh, Schraegluftbilder, Orthobilder

### Takeaway
**Wichtigster Fund.** Die Stadt Freiburg veroeffentlicht unter DL-DE BY 2.0 ein eigenes LoD2-CityGML (Revision 2026-07/10, 1,6 GB) und ein **texturiertes LoD2 als Cesium-3D-Tiles**. Im 3D-Viewer laeuft ausserdem ein **"Digitales Oberflächenmodell 2025 (texturiert)"**. Das ist ein photogrammetrisches 3D-Mesh aus der Befliegung 2025, als Cesium-Tileset oeffentlich abrufbar. Dazu kommen **Schraegluftbilder 2021** (virtualcityMAP, Abruf nur mit Anmeldung, 401). Die Lizenz fuer Mesh und Schraegbilder ist nicht als DL-DE dokumentiert.

### Cited Findings
- Metadatensatz "3D-Stadtmodell Freiburg i. Br. - LoD2" (uuid 1c576440-e5e1-4095-bff1-a14d76cec6f4, Revision 2026-07-28). Links: CityGML `https://geoportal.freiburg.de/stadtmodell/20261007_Freiburg_LoD2.gml` (selbst geprueft: HTTP 200, 1.610.391.847 Byte, Last-Modified 07.10.2026), Cesium3DTileset LoD2 texturiert `https://3d.freiburg.de/datasource-data/fb8c16e3-1216-446a-8418-ad0f6e2a0e83/tileset.json` (selbst geprueft: 60.178 Features) und untexturiert `.../122862e9-5f4c-4597-a9d6-c7b4880a56a3/tileset.json`. Lizenz: DL-DE BY 2.0, Quellenangabe "Datengrundlage: Stadt Freiburg, www.freiburg.de". Entstehung: "tridicon-Software CityModeller und Fortführung mit Building Reconstruction (Virtual City Systems) / SGJ3D Construction (CPA)". Der Abstract sagt "ohne Dachaufbauten und ohne Textur der Fassaden", verlinkt aber eine texturierte Tileset-Variante (Widerspruch im Metadatensatz) — [GDI-BW Katalog-API, Record 1c576440](https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/1c576440-e5e1-4095-bff1-a14d76cec6f4)
- LoD1 CityGML: `https://geoportal.freiburg.de/stadtmodell/2026_Freiburg_LoD1.gml` (262 MB, 20.05.2026), DL-DE BY 2.0 — [Record 164ceef4](https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/164ceef4-6c67-4763-8100-c5799a2ea6d8)
- LoD2-Erweiterung ueber die Stadtgrenze: LGL-LoD2, mit ALKIS verschnitten, untexturiert, Juni 2026, jaehrlich aktualisiert — Record ca2e448b-4604-4a4e-aef8-77686950184e (GDI-BW-Katalog, wie oben)
- Viewer-Konfiguration `https://3d.freiburg.de/configs/320baca2-a351-4702-8d85-56da1ff88cc0.json` (selbst abgerufen) mit diesen Ebenen:
  - "Texturierte Gebäude 2025"
  - CesiumTilesetLayer "Digitales Oberflächenmodell 2025 (texturiert)" unter `https://3d.freiburg.de/datasource-data/2025_befliegung/22_Mesh3D_Cesium` (tileset.json oeffentlich lesbar, Kacheln wie `L15/IT/0399_5286_-001_lv15_0.json`; Vorgaenger 2021: `.../2021_befliegung/20_Mesh3D_Cesium`)
  - ObliqueCollection "Schrägluftbilder 2021" unter `https://freiburg.virtualcitymap.de/datasource-data/d7180767-b254-437d-be07-1010d6a32835/image.json` (selbst geprueft: HTTP 401)
  - "Orthobild Frühjahr 2025" (stadteigene WMTS) und "Orthobild (2025, 20cm, LGL)"
  - Namensnennung im Viewer: "Stadt Freiburg im Breisgau" — [3d.freiburg.de](https://3d.freiburg.de)
- Metadatensatz "3D-Viewer Freiburg": virtualcityMAP, umfasst "je nach Konfiguration Schrägluftbilder, eine 2D-Kartenansicht und eine 3D-Kartenansicht". Nutzungsbedingungen: "Siehe Hinweise Nr. 1 und Nr. 2 auf der Startseite der Geoanwendung" (Text nicht abrufbar, hinweise.html: AccessDenied) — Record 838b8635-0733-4c08-a71f-3025a4c5db2a (GDI-BW-Katalog)
- Serie "Orthobilder der Stadt Freiburg": die Stadt laesst alle 2 Jahre eine hochaufgeloeste Befliegung machen. Das aktuelle Bild gibt es als WMTS/WMS (`https://geoportal.freiburg.de/wms/verma_ortho/verma_ortho?`) und als Open Data. "Orthobilder in höherer Auflösung können über die Servicestelle des Vermessungsamtes bezogen werden" — Record 6474923e-ad08-4418-84ff-77462d55fb9f (GDI-BW-Katalog)
- FreiGIS-Open-Data allgemein unter DL-DE BY 2.0 mit eigener OSM-Regel (Kap. 5.1) — [FreiGIS Hilfe (Suchtreffer; Seite gab beim Abruf 404)](https://geoportal.freiburg.de/docs/freigis/index.php?section=chpt_terms)
- Etwa 60.000 Gebaeude, Viewer seit 2018 — [kommunal.de 2018](https://kommunal.de/open-data-3d-modell-der-stadt-bietet-viele-vorteile)

### Inferences
- Das **Mesh 2025 der Stadt ist fuer Altstadtbauten wahrscheinlich die beste verfuegbare 3D-Quelle**: Schraeg- und Nadirbildvermaschung zeigt Fassaden, Erker und Gauben, die DOM1, bDOM und LoD2 nicht erfassen. Fuer Martinstor und Kaufhaus sollte man es als Referenzform (Overlay, Kontur-Diff) und als Texturquelle pruefen. Es ist ein mutmasslich oblique-basiertes Produkt. Die Aufloesung muss man an den Kacheln messen.
- Lizenz: Die DL-DE-BY-2.0-Freigabe ist nur fuer LoD1/LoD2 (CityGML und Tilesets) dokumentiert. Fuer Mesh und Schraegluftbilder fehlt eine Open-Data-Erklaerung. **Vor kommerzieller Nutzung (Verkaufsplan) schriftlich beim Vermessungsamt anfragen** (vermessung@freiburg.de, gdi-support@freiburg.de). Bis dahin nur als Pruefreferenz verwenden und in modelle/LIZENZ_WERKZEUGE.md als "ungeklaert" fuehren.
- Das staedtische LoD2 wurde unabhaengig erzeugt (tridicon/VCS) und weicht vom LGL-LoD2 ab. Damit hat man eine zweite Dachform-Quelle, die man getrennt fuehren und nicht mitteln sollte.

### Gaps
- Lizenztext der Hinweise 1/2 im Viewer, Bodenaufloesung der Schraegluftbilder und des Mesh, Texturquelle des LoD2 sowie Bezugsweg und Preis der hoeher aufgeloesten Orthobilder: nicht ermittelt.
- Es ist nicht geprueft, ob die Mesh-Kacheln vollstaendig ohne Authentifizierung ladbar sind (S3 gab fuer `pyramid/tileset.json` AccessDenied, das Wurzel-tileset.json war lesbar).
- Kein oeffentliches Fassadenfoto- oder Bauplanarchiv der Stadt gefunden.

## 3. Strassenbilder als Alternative: Panoramax, KartaView, Google Street View, Apple, Cyclomedia

### Takeaway
Panoramax (CC BY-SA 4.0, abgeleitete Nicht-Foto-Daten ODbL) und KartaView (CC BY-SA 4.0) sind lizenzrechtlich nutzbar. ShareAlike gilt aber fuer abgeleitete *Bilder*. Fuer Panoramax ist der Rechteweg fuer abgeleitete Geometrie ausdruecklich geregelt (ODbL). Die Abdeckung in Deutschland bzw. Freiburg ist unbelegt und vermutlich duenn. Google verbietet das Extrahieren und Ableiten aus seinen Inhalten.

### Cited Findings
- Panoramax-Bilder unter CC BY-SA 4.0, mit Zusatzerlaubnis, nicht-fotografische Daten unter ODbL abzuleiten. Foederiert: jeder kann eine Instanz betreiben — [Wikipedia Panoramax](https://en.wikipedia.org/wiki/Panoramax); [OSM-Wiki Panoramax](https://wiki.openstreetmap.org/wiki/Panoramax)
- Die OSM-France-Instanz ist auf Frankreich beschraenkt (Speicher). Ein Forumsthread von 2024 heisst "Deutscher Panoramax Server?", ein Beitrag von 2025 erwaehnt eine deutsche Instanz, die Adresse ist unbestaetigt — [OSM Forum](https://community-cdn.openstreetmap.org/t/deutscher-panoramax-server/111586/25); [Forum-Tag](https://community.openstreetmap.org/tag/panoramax)
- KartaView: Bilder CC BY-SA 4.0, Software teils proprietaer — [OSM-Wiki KartaView](https://wiki.openstreetmap.org/wiki/KartaView); [Wikipedia](https://en.wikipedia.org/wiki/KartaView)
- Google Map Tiles API (inkl. Photorealistic 3D Tiles): Caching, Datenextraktion und Offline-Nutzung sind verboten. Overlays sind nur erlaubt, wenn sie nicht "extracted, traced, or otherwise derived ... from Photorealistic 3D Tiles" sind. Fuer EWR-Kunden gelten eigene AGB — [Google Map Tiles Policies](https://developers.google.com/maps/documentation/tile/policies); Forum zitiert ToS 3.2.3(a) "no scraping/export" (Sekundaerzitat) — [Cesium Forum](https://community.cesium.com/t/saving-google-map-data/31228)

### Inferences
- Google Street View und Google 3D Tiles sind fuer ein verkauftes Modell nicht verwendbar, auch nicht als Formvorlage. Dieselbe Klausel betrifft die Ableitung von Geometrie.
- Panoramax ist lizenzrechtlich die sauberste Strassenbildquelle (ODbL fuer Abgeleitetes). Realistisch muesste man die Freiburger Altstadt selbst aufnehmen und dort hochladen.

### Gaps
- Keine belastbare Abdeckungszahl fuer Panoramax oder KartaView in Freiburg. Bei Bedarf die API-Bounding-Box selbst abfragen.
- Apple Look Around, Cyclomedia (kommerziell, Preis auf Anfrage), Bing Streetside und Cesium-ion-Inhalte: in diesem Lauf nicht mit Quellen belegt. Apple und Bing bieten nach meinem Wissen keine Lizenz fuer Ableitungen an, das ist aber unbelegt.
- Flickr-API-Lizenzfilter (license=4 CC BY, 9/10 CC0/PDM): nicht verifiziert.

## 4. Denkmalpflege, Archive, historische Bauaufnahmen (Martinstor, Kaufhaus)

### Takeaway
Die LAD-Datenbank Bauforschung/Restaurierung hat Eintraege zu Martinstor und Kaufhaus mit Bauphasen, aber ohne Bauaufnahme-Zeichnungen und ohne Lizenzvermerk. Historische Fotos im Landesarchiv BW (ueber die DDB) tragen je Objekt eigene Lizenzen (teils CC BY 3.0 DE, teils PDM).

### Cited Findings
- LAD-Eintrag Martinstor (ID 183702660413, Druck 26.04.2024): neun Bauphasen von 1204-05 bis 2000-2015, Text "65 m hoch, Grundfläche 10 x 11 m" und Aufstockung 1901 "von 22 m auf 60 m" (in sich widerspruechlich). Keine Zeichnungen, kein Lizenzvermerk. Genannt werden Dokumentationen zu Dendrodatierung und restauratorischer Untersuchung, die nicht beiliegen — [bauforschung-bw.de Martinstor](https://www.bauforschung-bw.de/objekt/pdf/183702660413/martinstor.pdf)
- LAD-Eintrag Kaufhaus Muensterplatz 24 (ID 196867510511): Umorientierung zum Muensterplatz 1520-32 — [bauforschung-bw.de Kaufhaus](https://www.bauforschung-bw.de/objekt/pdf/196867510511/kaufhaus.pdf); Bauforschung F. Loebbecke mit Grundrissen und Untersuchung der Rueckfassade — [BLB Loebbecke](https://regionalia.blb-karlsruhe.de/files/18404/BLB_Loebbecke_Historisches_Kaufhaus.pdf)
- Landesarchiv-BW-Fotos (z. B. Willy Pragher) in der DDB: Martinstor-Foto unter CC BY 3.0 DE, andere Objekte unter Public Domain Mark. Die Lizenz gilt je Datensatz — [DDB Beispiel](https://www.deutsche-digitale-bibliothek.de/item/PZYWSFESPHD4MOC5PQZ2GGUCJM2XYOTT?lang=en)
- Zusaetzlich staedtisch: "Baufluchtenpläne von Freiburg i. Br." (Record e7554420-9a09-4fb8-8033-761c00e83d52, GDI-BW-Katalog), Inhalt und Lizenz nicht geprueft.

### Inferences
- Das Martinstor-Mass "65 m" aus der LAD-Datenbank ist ein Dokumentwert. Nach Regel 4 gibt er keine Form vor und kann nur als widerspruechliche Hoehenangabe in die Masstabelle (Quelltyp Dokument, 60 vs 65 m offen lassen).
- Die Loebbecke-Grundrisse des Kaufhauses sind die vielversprechendste Dokumentquelle fuer Grundriss und Fensterachsen. Fuer eine Verwendung braucht es eine Nutzungsanfrage (BLB/Autor).

### Gaps
- LAD-Bildarchiv und Planarchiv (Bauaufnahmen, Messbilder): Bezugsweg und Lizenz nicht gefunden. Eine Anfrage beim LAD Esslingen bzw. Referat Freiburg ist noetig.
- Stadtarchiv Freiburg und Universitaetsbauamt (Plaene Martinstor 1901, Umbau Kaufhaus): nicht recherchiert.

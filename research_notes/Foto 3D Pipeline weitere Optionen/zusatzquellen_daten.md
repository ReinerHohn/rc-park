# Zusatzquellen DATEN fuer Schwabentor, Martinstor, Historisches Kaufhaus (Freiburg i. Br.), Stand 15.11.2026

Hinweise zur Lesart:
- "Eigene Abfrage" = von mir am 15.11.2026 direkt gegen die oeffentliche API gestellt; die genannte URL ist der Endpunkt.
- "UNGEPRUEFT" = nicht an der Primaerquelle bestaetigt (nur Suchtreffer-Auszug, Zweitquelle oder Seite nicht lesbar).
- Software-Massnahmen aus `reports/Foto 3D Pipeline Verbesserungen.md` (GPS-Tor, PatchMatch, LIMAP, Orthofoto-Stapel usw.) werden hier nicht wiederholt; es geht nur um Datenquellen.
- Keine Rechtsberatung; Lizenzangaben sind Zitate/Zusammenfassungen der verlinkten Seiten.

## 1. Amtliche Geodaten Baden-Wuerttemberg (LGL) und Stadt Freiburg

### Takeaway
Die groessten ungenutzten amtlichen Hebel sind (a) ALS-Laserpunktwolke ALS_3/ALS_2 mit mindestens 8 Punkten/m2 (Dach- und Turmgeometrie unabhaengig von Fotos), (b) DOP10/TrueDOP und das Produkt "Orientierte Luftbilder" des LGL, und (c) das staedtische 3D-Portal 3d.freiburg.de, das Schraegluftbilder aus vier Himmelsrichtungen und ein 3D-Mesh zeigt und ein Export-Werkzeug hat. Ein landesweites LGL-Produkt "Schraegluftbild", "3D-Mesh" oder "LoD3" habe ich nicht gefunden; die Stadt Freiburg besitzt laut eigenen Metadaten aber Schraegluftbilder und Cycloramen.

### Cited Findings

LGL Open Data (Liste, Stand 29.05.2024):
- Als hochwertige Datensaetze (HVD) frei: DGM025 (!), DGM1, DOM1, DOM5, DOP20, DOP-Zeitscheiben ("Digitaler Luftbildatlas Baden-Wuerttemberg"), 3D-Gebaeudemodell LoD1 und LoD2, ALKIS-Hausumringe, Hauskoordinaten, DTK-Reihe. Als "nicht hochwertig, aber unentgeltlich" (ggf. Grenzkosten): bildbasiertes DOM (bDOM), "Punktdaten mit Katasternachweis", Badische Gemarkungsuebersicht. Schraegluftbilder, Mesh, LoD3 und ALS-Punktwolke stehen NICHT auf dieser Liste. — [LGL, Open_GeoData_Liste_Datensaetze.pdf](https://bwmm-support.lgl-bw.de/export/sites/lgl/Produkte/Open-Data/Galerien/Dokumente/Open_GeoData_Liste_Datensaetze.pdf)
- Das Land hat die Geobasisdaten fuer kommerzielle und nicht-kommerzielle Nutzung kostenlos freigegeben; Portal opengeodata.lgl-bw.de. — [Pressemitteilung Land BW](https://www.baden-wuerttemberg.de/de/service/presse/pressemitteilung/pid/land-stellt-geobasisdaten-kostenlos-zu-verfuegung-1); Anhang-Liste: [MLW PM 020 Anhang](https://mlw.baden-wuerttemberg.de/fileadmin/redaktion/m-mlw/intern/Dateien/00_Pressemitteilungen/2024/PM_020_Freigabe_Geobasisdaten_Anhang_Liste_mit_Bildern.pdf)
- Lizenz DOP20 laut INSPIRE-Metadaten: Datenlizenz Deutschland - Namensnennung 2.0, Quellenvermerk Muster "LGL-BW (Jahr) Datenlizenz Deutschland - Namensnennung - Version 2.0, www.lgl-bw.de"; es gibt einen WCS-Dienst fuer DOP20. — [INSPIRE Geoportal, DOP20-Metadaten](https://inspire-geoportal.ec.europa.eu/srv/api/records/938b32b1-ea44-4890-b2d7-09a6bd6df811)
- Das Portal selbst (https://opengeodata.lgl-bw.de/) ist eine JavaScript-Anwendung; der Inhalt war mit dem Abrufwerkzeug nicht lesbar (nur Seitentitel "Open GeoData Portal"). Aktuelle Produktliste/Jahrgaenge dort daher UNGEPRUEFT. — [opengeodata.lgl-bw.de](https://opengeodata.lgl-bw.de/)

ALS-Laserscan (wichtigste neue Quelle fuer Daecher/Turmhelme):
- ALS_3: dritte Kampagne 2022 bis voraussichtlich 2029, Daten seit 2023 fuer beflogene Gebiete; Punktdichte mindestens 8 Punkte/m2; 7 Klassen (Boden, Gebaeude, Vegetation u. a.); Format LAZ/LAS (alle Klassen in einer Datei) oder XYZ-ASCII (je Klasse eine Datei); ETRS89/UTM; Hoehe NHN (DHHN2016, Hoehenstatus 170). Die Seite nennt "Open Data", aber Abgabe gegen Bereitstellungsentgelt nach Aufwand, Mindestentgelt 60 EUR zzgl. USt; Bestellung per E-Mail an geodaten@lgl.bwl.de mit Koordinaten oder Kachelnamen; KEIN Direktdownload-Link auf der Seite. Befliegungsstand ueber Geoportal BW (Flugueberblick/Kacheluebersicht). Freiburg wird nicht genannt. — [LGL ALS_3](https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/ALS_3/index.html)
- ALS_2 (2016-2021): mindestens 8 Punkte/m2, landesweit vorhanden, LAZ/LAS. ALS_1 (2000-2005): 0,8 Punkte/m2. (aus Suchtreffer-Auszug der LGL-Seiten, Details UNGEPRUEFT) — [LGL ALS_2](https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/ALS_2/index.html), [LGL ALS_1](https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/ALS_1/index.html)
- Metadaten nennen Kachelung 1x1 km und Verfuegbarkeitspruefung ueber WFS/WMS "ATKIS DGM Kacheln" bzw. "Durchgefuehrte Laserfluege ALS 3 ab 2022" (Suchtreffer-Auszug, UNGEPRUEFT). — [Metadaten GDI-BW, Laserscandaten](https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/7416e3bb-7696-38f0-0444-e43fe4aaa9af)

Orthophotos / Luftbilder:
- DOP10: 10 cm Bodenaufloesung, Lagegenauigkeit im Mittel +/-0,25 m, landesweit ab 2011, 2-Jahres-Zyklus; Fruehjahrsbefliegung bis 2025, ab 2026 eine gemeinsame Befliegung fuer DOP10 und DOP20; laut dieser Seite TrueDOP "seit Sommer 2025"; GeoTIFF/TIFF+TFW, 1x1-km-Kacheln; RGB, RGBI, CIR, Grau; Bestellung RGB/CIR ueber Geodatenshop (Registrierung), sonst geodaten@lgl.bwl.de; Download bis 5 GB per Link. Die Seite nennt keine Open-Data-Lizenz und verweist auf eine Preistabelle. Sie verweist ausserdem auf ein eigenes Produkt "Orientierte Luftbilder" (= Luftbild vor der Entzerrung, mit Orientierung). Hinweis der Seite: hochaufloesende Bilder (10 cm und feiner) duerfen aus Datenschutzgruenden ggf. nicht online veroeffentlicht werden. — [LGL DOP10](https://www.lgl-bw.de/Produkte/Luftbildprodukte/DOP10/index.html)
- DOP20: 20 cm, Lagegenauigkeit +/-0,5 m; Sommerbefliegung mit Belaubung bis 2025; DOP "seit 2020 als TrueDOP" (aus bDOM entzerrt, Umklappeffekte/sichttote Raeume beseitigt). WIDERSPRUCH zur DOP10-Seite ("seit Sommer 2025") - vermutlich DOP20 ab 2020, DOP10 ab 2025; nicht abschliessend geklaert. — [LGL DOP20](https://www.lgl-bw.de/Produkte/Luftbildprodukte/DOP20/index.html) (Suchtreffer-Auszug), [LGL Newsletter TrueDOP 2021](https://www.lgl-bw.de/Ueber-Uns/Newsletter/Galerien/Dokumente/2021-01_LGL-TrueDOP.pdf)
- Luftbild-Zyklus seit 2022 zwei statt drei Jahre, jeden Sommer etwa das halbe Land; aus den Luftbildern werden bildbasierte Oberflaechenmodelle (mit Gebaeuden) abgeleitet. — [Pressemitteilung Land BW, 14.11.2022](https://www.baden-wuerttemberg.de/de/service/presse/pressemitteilung/pid/luftbilder-und-oberflaechenmodelle-in-neuer-qualitaet-1)
- LoD2 des LGL: aus ALKIS-Grundrissen und Laserscan-Hoehen berechnet, Standarddachformen, ohne Dachaufbauten und ohne Fassadentexturen. — [Runder Tisch GIS, Katalogeintrag LoD2 BW](https://katalog.rundertischgis.de/en/dataset/3d-gebaudemodelle-lod2-b-w)

Stadt Freiburg:
- 3D-Portal https://3d.freiburg.de/ (VC Map, Virtual City Systems): Schraegluftbild-Ansicht in vier Himmelsrichtungen, 3D-Ansicht mit Mesh; Export-Werkzeug fuer 3D-Objekte, 3D-Mesh, Schraegluftbilder und Gelaende; Bereichsabfrage maximal 150.000 m2; Export kann Stunden dauern, Download-Link kommt per E-Mail; CityGML wird als Format genannt (Hilfe zeigt Beispiel "LoD 3 mit Texturen" - das kann generischer Hilfetext des Herstellers sein). Die Hilfeseite nennt WEDER Jahrgang/Aufloesung von Mesh und Schraegbildern NOCH Lizenz/Nutzungsbedingungen NOCH ob der Export fuer anonyme Nutzer freigeschaltet ist. — [3d.freiburg.de Hilfe](https://3d.freiburg.de/templates/de/info.html)
- 3D-Stadtmodell Freiburg LoD1 und LoD2 als CityGML 2.0 (EPSG:25832), Open Data, Datenlizenz Deutschland Namensnennung 2.0; als Datengrundlage nennen die Metadaten "Grundrisspolygone (ALK, ALKIS), Luftbilder (Orthobilder, Schraegluftbilder, Cycloramen), DGM5, DOM"; Software BuildingReconstruction (Virtual City Systems). (Lizenz/Datengrundlage aus Suchtreffer-Auszug der Metadaten; der LoD2-Eintrag selbst war nicht abrufbar - ECONNRESET.) — [GDI-DE Katalog, 3D-Stadtmodell Freiburg LoD2](https://gdk.gdi-de.org/geonetwork/srv/api/records/1c576440-e5e1-4095-bff1-a14d76cec6f4), [GDI-BW, LoD1](https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/164ceef4-6c67-4763-8100-c5799a2ea6d8), [GDI-BW, Serie 3D-Stadtmodelle](https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/f4c62c54-4a27-409b-9e82-a55cb4783801)
- Kontakt Daten: Sachgebiet Geoinformation vermessung@freiburg.de (Berliner Allee 1); Bereitsteller Stabsstelle Digitales Bauen und GeoIT gdi-support@freiburg.de. — [GDI-BW, Serie 3D-Stadtmodelle](https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/f4c62c54-4a27-409b-9e82-a55cb4783801)
- FreiGIS-Geodaten inkl. Luftbilder stehen laut OSM-Wiki unter dl-de/by-2-0; ein Orthophoto 2017 mit 20 cm ist als Open Data gelistet. — [OSM-Wiki Freiburg im Breisgau](https://wiki.openstreetmap.org/wiki/Freiburg_im_Breisgau)
- Historische Stadtplaene 1838-2020 als WMS: `https://geoportal.freiburg.de/wms/verma_stadtplan_hist/verma_stadtplan_hist?` (Layer u. a. stadtplan_1838, stadtplan_1920, stadtplan_1992); Lizenz im Serieneintrag nicht benannt ("Other restrictions", Verweis auf Datensatzebene). — [Geodatenkatalog Freiburg, Serie Historische Stadtplaene](https://geodaten.freiburg.de/geonetwork/srv/api/records/ad1ae3cc-535a-414e-94d5-c80817500497)
- Das Stadtmodell umfasst rund 60.000 Gebaeude; Erstellung durch das Vermessungsamt ueber vier Jahre (Stand 2018). — [kommunal.de](https://kommunal.de/open-data-3d-modell-der-stadt-bietet-viele-vorteile), [Bertelsmann Stiftung](https://www.bertelsmann-stiftung.de/de/unsere-projekte/smart-country/gute-beispiele/54)

### Inferences
- ALS-Punktwolke (>= 8 Pkt/m2, Klasse Gebaeude) ist die unabhaengige Dach-/Helm-Quelle, die der Pipeline fehlt: Firstlinien, Traufhoehen, Helmspitze und Dachneigung der Tore lassen sich daraus direkt messen; passt zur Regel "Wolke nur Lage-Veto, Hoehe, Gegenprobe". Bei 8 Pkt/m2 liegen auf einem 11x11-m-Turmdach rechnerisch knapp 1000 Punkte - genug fuer Ebenen, zu wenig fuer Gauben/Erkertuermchen. Kosten: mind. 60 EUR + USt je Bestellung, wenn es keinen Direktdownload gibt.
- "Orientierte Luftbilder" des LGL waeren Kameras mit bekannter Pose (K, R, t) aus amtlicher Aerotriangulation mit ca. 10 cm GSD: als zusaetzliche Bilder im SfM mit festen Posen ein unabhaengiger Massstabs- und Lage-Anker und Sicht auf Daecher. Spezifikation, Preis und Lizenz dieses Produkts habe ich nicht gelesen (siehe Gaps).
- Die staedtischen Schraegluftbilder (4 Richtungen) sind genau die Quelle fuer "obere Geschosse/Daecher/ungesehene Seite". Ob der Export frei ist und unter welcher Lizenz, muss am Portal bzw. per Mail an vermessung@freiburg.de geklaert werden. Da LoD1/LoD2 der Stadt unter dl-de/by-2-0 stehen, ist eine Anfrage nach Mesh/Schraegbildern unter derselben Lizenz plausibel, aber nicht belegt.
- Die Stadt besitzt "Cycloramen" (Strassenpanoramen mit Vermessungs-Pose, typischerweise Cyclomedia) - das waere die beste Strassenquelle mit bekannter Pose; oeffentlich habe ich dazu keinen Zugang gefunden.
- LGL-LoD2 und Stadt-LoD2 sind zwei verschiedene Modelle (LGL: ALKIS + Laser, Standarddaecher; Stadt: BuildingReconstruction mit Schraegbildern). Ein Vergleich beider an den drei Objekten ist eine billige Gegenprobe; Widersprueche nicht mitteln.
- ACHTUNG Unabhaengigkeit: LoD2 (LGL) wird aus ALKIS-Grundrissen abgeleitet. ALKIS-Hausumringe sind daher KEIN unabhaengiger Beleg gegen LoD2, die ALS-Wolke und DOP10/TrueDOP dagegen schon.
- DGM025 (25-cm-Gelaendegitter) ist frei und feiner als das bisher genutzte DGM1 - nuetzlich fuer Sockel-/Strassenhoehen an den Toren.

### Gaps
- Aktuelle Produktliste, Jahrgaenge und Kachel-Download auf opengeodata.lgl-bw.de (JS-Seite, nicht lesbar); ob ALS dort inzwischen direkt ladbar ist. Im Browser pruefen.
- Befliegungsjahr ALS_3 und DOP fuer Freiburg (Geoportal-BW Befliegungsuebersicht nicht abgefragt).
- Produktseite "Orientierte Luftbilder": Format der Orientierung, Preis, Lizenz - nicht geoeffnet.
- bDOM: Rasterweite/Format nicht gefunden. Die fruehere LGL-Praesentation "Flaechendeckend 3D" liefert HTTP 404.
- 3d.freiburg.de: Jahrgang/GSD der Schraegbilder und des Mesh, Lizenz, ob Export ohne Anmeldung geht - nicht dokumentiert; ausprobieren oder anfragen.
- Kein Beleg fuer ein LoD3 oder texturiertes Modell der drei Objekte bei Stadt oder Land.
- Geoportal-BW WMS/WCS-Endpunkte: nur die Existenz eines DOP20-WCS ist belegt, keine Endpunkt-URLs verifiziert - daher hier keine angegeben.

## 2. Strassenbilder mit Posen (Mapillary, KartaView, Panoramax, Google, Apple, Bing) und 360-Grad-Bilder in COLMAP

### Takeaway
Mapillary ist die einzige offene Quelle, die je Bild SfM-korrigierte Pose, Kameraparameter und sogar die lokale Punktwolke per API liefert (Bilder CC BY-SA); die Abdeckung an den drei Objekten ist aber noch zu pruefen. Panoramax hat in der Altstadt Bilder, aber keines im 80-m-Umkreis der drei Objekte. Google Street View, Apple Look Around sind fuer Rekonstruktion vertraglich ausgeschlossen.

### Cited Findings

Mapillary:
- API v4, Bildfelder: `computed_geometry` (Position nach Bildverarbeitung), `computed_altitude`, `computed_compass_angle`, `computed_rotation` (Achse-Winkel-Vektor), `camera_parameters` (Brennweite, k1, k2 - OpenSfM-Konvention), `camera_type` (perspective/fisheye/equirectangular), `is_pano`, `atomic_scale` (Massstab der SfM-Rekonstruktion), `sfm_cluster` (URL zur Punktwolke, JSON zlib-komprimiert), `mesh` (URL), `thumb_original_url` (Originalgroesse), `merge_cc` (ID der gemeinsam ausgerichteten Komponente). — [Mapillary API-Dokumentation](https://www.mapillary.com/developer/api-documentation)
- Grenzen: bbox-Suche kleiner als 0,01 Grad im Quadrat; Radius-Suche max. 50 m; 60.000 Entity-Abfragen/min, 10.000 Suchabfragen/min, 50.000 Kachelabfragen/Tag; Client-Token noetig. — [Mapillary API-Dokumentation](https://www.mapillary.com/developer/api-documentation)
- `sfm_cluster` verweist auf Teil-Rekonstruktionen; eine lokale Rekonstruktion kann mehrere Cluster haben. — [Mapillary-Forum](https://forum.mapillary.com/t/api-identify-images-whose-geometry-was-optimized-together/10070), Format: [Mapillary-Forum, Punktwolkenformat](https://forum.mapillary.com/t/api-mesh-and-point-cloud-format/6664)
- Lizenz/Bedingungen: Nutzerinhalte anderer stehen unter "Creative Commons Share Alike (CC BY-SA) license, unless we indicate otherwise"; fuer einzelne Datensaetze koennen andere Lizenzen gelten (z. B. CC BY-NC-SA). Verboten: "data mining, robots or similar data gathering or extraction methods not approved by Mapillary" und Umgehen der robots.txt. Namensnennung mit Mapillary-Logo/Quelle; kommerzielle Nutzung nur fuer die in Abschnitt 12 genannten Zwecke; jede Anwendung braucht eigene client_id. — [Mapillary Terms of Use](https://mapillary.com/legal)
- CC BY-SA 4.0 fuer Bilder wird auch von Wikipedia/OSM-Wiki genannt; Sondererlaubnis zum Ableiten von Daten fuer OSM/Wikimedia. (Zweitquellen) — [OSM-Wiki Mapillary](https://wiki.openstreetmap.org/wiki/Mapillary)

Panoramax (freie, foederierte Alternative):
- Bilder CC BY-SA 4.0 mit Zusatzerlaubnis, daraus nicht-fotografische Daten unter ODbL abzuleiten; Software MIT; API nach STAC 1.0.0; Meta-Katalog api.panoramax.xyz ueber alle Instanzen. Instanzen laut OSM-Wiki (Stand 04.06.2026): IGN, OSM France, OSM Hrvatska, Taiwan, Cymru/Wales - keine deutsche. — [Wikipedia Panoramax](https://en.wikipedia.org/wiki/Panoramax), [OSM-Wiki Panoramax](https://wiki.openstreetmap.org/wiki/Panoramax), [Panoramax-Doku STAC](https://docs.panoramax.fr/backend/dev/STAC_compatibility/)
- Eigene Abfrage 15.11.2026, bbox Altstadt 7.846,47.989,7.858,47.998: 464 Bilder, alle CC-BY-SA-4.0; davon 323 vom Oktober 2026 und 139 vom Oktober 2025 von einem Konto "test2" (Pixel 8 Pro, 4080x3072, Blickfeld 71 Grad, KEINE 360-Grad-Bilder), gehostet auf panoramax.multimodall.com; je 1 Bild von zwei weiteren Konten. In Kaestchen von etwa +/-80 m um Schwabentor, Martinstor und Kaufhaus: 0 Bilder. Bilder sind in voller Aufloesung ("hd") direkt abrufbar; EXIF-GPS und Blickrichtung im JSON. — [api.panoramax.xyz/api/search](https://api.panoramax.xyz/api/search?bbox=7.846,47.989,7.858,47.998&limit=500)

KartaView:
- Bilder unter CC BY-SA 4.0; Einzelbilder per Web/API ladbar; API braucht Konto/Schluessel, Ratenlimits undokumentiert; Abdeckung stark gemeindeabhaengig; laut (altem, 2020) deutschem OSM-Wiki kein Massendownload. — [OSM-Wiki KartaView](https://wiki.openstreetmap.org/wiki/KartaView), [Bellingcat Toolkit](https://bellingcat.gitbook.io/toolkit/more/all-tools/kartaview), [Wikipedia KartaView](https://en.wikipedia.org/wiki/KartaView)

Google Street View / Maps Platform:
- Map Tiles API Policies (gelten auch fuer Street-View-Kacheln): "Don't export, extract, or scrape Google Maps Content for use outside the Services"; kein Massendownload von "map tiles, Street View images"; verboten u. a. "Image analysis", "Machine interpretation", "Object detection", Offline-Nutzung; "don't trace or digitize features from satellite imagery, build 3D or terrain models"; "Street View imagery may not be used for print purposes". — [Google Map Tiles API Policies](https://developers.google.com/maps/documentation/tile/policies)

Apple Look Around:
- Apple-Maps-Nutzungsbedingungen verbieten "copy, extract, scrape or reutilize any portions of the data or content ... including bulk downloads or feeds of map data or imagery" sowie abgeleitete Werke. — [Apple Maps Terms of Use](https://www.apple.com/legal/internet-services/maps/terms-en.html)

360-Grad-Panoramen in COLMAP:
- Seit COLMAP 3.12 (Rigs/Frames): Panoramen werden als virtuelle Lochkamera-Ansichten (aehnlich Cubemap) gerendert und als Kamera-Rig behandelt; Beispielskript `python/examples/panorama_sfm.py`. — [COLMAP Rig-Doku (Debian-Quelle 4.0.2)](https://sources.debian.org/src/colmap/4.0.2-2/doc/rigs.rst), [radiancefields.com zu 3.12](https://radiancefields.com/colmap-3-12-released)
- COLMAP 4.1.0 bringt laut Zweitquelle native sphaerische Kameramodelle (Rekonstruktion ohne Umrendern; "generally faster but less accurate" als der Rig-Weg) und erweitert panorama_sfm (Rueckwandlung in equirektangular, globaler Mapper). Aus Zweitquelle/Spiegel, an colmap.github.io NICHT gegengeprueft. — [radiancefields.com zu 4.1.0](https://radiancefields.com/colmap-4.1.0-ships-caspar-gpu-bundle-adjustment-and-native-360-reconstruction)

### Inferences
- Mapillary-Einbindung: Bilder im 50-m-Radius je Objekt holen, `thumb_original_url` laden, `computed_geometry/altitude/rotation` als Positions-Prior (COLMAP pose priors) und `camera_parameters` als Start-Intrinsik. Die Mapillary-Posen stammen aus OpenSfM mit GPS-Ausgleich ueber ganze Sequenzen - das ist ein vom eigenen Handy-GPS unabhaengiger Lage-/Massstabs-Hinweis (Genauigkeit unbekannt, also als Tor/Gegenprobe, nicht als Wahrheit). Gesichter/Kennzeichen sind verwischt; Bildqualitaet oft Dashcam/Actioncam.
- Lizenzfolge CC BY-SA: Herunterladen, Verarbeiten und Ableiten ist erlaubt; ob ein daraus trianguliertes 3D-Modell ein "abgeleitetes Werk" mit Share-Alike-Pflicht ist, ist rechtlich offen. Vorsichtige Linie: Mapillary/Panoramax/KartaView-Bilder nur fuer Kameraposen, Zaehlung und Gegenprobe nutzen oder das veroeffentlichte Modell mit Namensnennung/SA versehen. Bei Panoramax ist das Ableiten nicht-fotografischer Daten ausdruecklich (unter ODbL) erlaubt - die klarste Rechtslage aller Strassenbild-Quellen.
- Panoramax lohnt sich fuer die drei Objekte derzeit nur als ABLAGE eigener Aufnahmen (z. B. eigene 360-Grad-Runde), nicht als Quelle.
- Google Street View und Apple Look Around sind als SfM-Eingang vertraglich ausgeschlossen (Extraktion, Bildanalyse, 3D-Modellbau, Druck). Ansehen im Browser zur Orientierung ("wie viele Fenster hat die Seite?") ist etwas anderes als Extraktion, aber Zaehlungen muessen laut Projektregel ohnehin an eigenen/freien Fotos belegt werden.
- Eine eigene 360-Grad-Runde (Kamera auf Stange, 3-5 m hoch) waere der billigste Weg, die "eine Seite ohne Fotos" zu schliessen; technisch per panorama_sfm-Rig einbindbar.

### Gaps
- Mapillary-Abdeckung an Schwabentor/Martinstor/Muensterplatz: nicht abgefragt (Token noetig). Pruefen mit `graph.mapillary.com/images?bbox=...&fields=id,captured_at,is_pano,camera_type,computed_geometry` (bbox < 0,01 Grad).
- Mapillary-Hilfeseite zur Lizenz (help.mapillary.com) lieferte HTTP 403; CC-Versionsnummer (4.0) daher nur ueber Zweitquellen.
- KartaView-Abdeckung in Freiburg: nicht ermittelt.
- Bing Streetside / Vogelperspektive (Vexcel): keine Quelle zu Bedingungen oder Abdeckung in Freiburg gefunden.
- COLMAP-4.1-Angaben nicht an der Primaerdoku geprueft; installierte Version im Projekt pruefen.

## 3. Luftbild-/3D-Quellen: Google 3D Tiles, Google Earth, OSM-3D, Schraegbild-Anbieter, Drohne

### Takeaway
Google Photorealistic 3D Tiles und Google Earth sind fuer Geometrie-Entnahme ausdruecklich gesperrt. Legale Dachquellen sind amtlich (ALS, DOP10/TrueDOP, staedtische Schraegbilder, siehe Abschnitt 1) oder ein eigener Drohnenflug, der in der Altstadt Zustimmungen bzw. eine geografische Erlaubnis braucht. OSM enthaelt fuer alle drei Objekte bereits Simple-3D-Buildings-Teile mit Hoehen (unbelegt, nur als Hinweis).

### Cited Findings
- Google Photorealistic 3D Tiles: eigene 3D-Objekte duerfen ueberlagert werden, "as long as the 3D objects aren't extracted, traced, or otherwise derived by hand or machine from Photorealistic 3D Tiles"; ausserdem kein Vorabruf/Speichern ausser nach Cache-Headern, keine Offline-Nutzung, Attribution Pflicht. — [Google Map Tiles API Policies](https://developers.google.com/maps/documentation/tile/policies)
- Google Earth / Earth Studio: "You may not use output, or use third party tools to capture output, from Google Earth, Google Earth Pro, or Earth Studio to reconstruct 3D models or create similar content." (aus Suchtreffer-Auszug der Google-Richtlinien) — [Google Geo Guidelines](https://about.google/brand-resource-center/products-and-services/geo-guidelines/)
- OSM Simple 3D Buildings, eigene Overpass-Abfrage 15.11.2026: Weg 129932309 "Schwabentor" `building=gatehouse`, `height=48`, wikidata Q2252613; Weg 767726339 "Historisches Kaufhaus" (wikidata Q1520195) mit benachbarten `building:part`-Wegen 767726340-767726347: Erdgeschoss-Teile `height=4.5`, Ecktuermchen `min_height=4.5, height=16, roof:shape=pyramidal, roof:height=7`, Hauptbau `min_height=4.5, height=19.5, roof:shape=gabled, roof:height=10.5`. Im Martinstor-Ausschnitt u. a. ein Teil `height=53, roof:shape=pyramidal, roof:height=8.5` (Weg 100355113; Zuordnung zum Martinstor von mir NICHT geprueft). OSM-Daten stehen unter ODbL; die Hoehen tragen keine Quellenangabe. — [Overpass API](https://overpass-api.de/api/interpreter)
- Wikidata: weder Martinstor (Q328965) noch Schwabentor (Q2252613) noch Kaufhaus (Q1520195) haben Hoehe/Breite (P2048/P2049) eingetragen (eigene Abfrage 15.11.2026). — [Wikidata Q328965](https://www.wikidata.org/wiki/Q328965)
- Drohne, offene Kategorie: bis 120 m, Sichtflug, nicht ueber Menschenansammlungen; A1 (C0/C1) eingeschraenkter Ueberflug Unbeteiligter, A2 30 m (5 m im Langsamflug), A3 150 m Abstand zu Wohn-/Gewerbe-/Erholungsgebieten; Versicherung, Betreiberregistrierung (e-ID), Kompetenznachweis. — [RP Baden-Wuerttemberg, Drohnen](https://rp.baden-wuerttemberg.de/themen/verkehr/luft/seiten/drohnen)
- Geografische Gebiete nach Paragraf 21h Abs. 3 LuftVO: u. a. Wohngrundstuecke (Zustimmung des Eigentuemers/Nutzungsberechtigten oder Bedingungen wie Flughoehe ueber 100 m, nicht 22-6 Uhr), 100 m zu Bundesfernstrassen/Bahnanlagen (Zustimmung oder 1:1-Regel), Behoerden/Polizei/Krankenhaeuser 100 m. Zustaendig landesweit: Regierungspraesidium Stuttgart, Referat 46.2 (bnl@rps.bwl.de). Geografische Allgemeinerlaubnis 200 EUR, 2 Jahre gueltig, Bearbeitung 2-14 Tage; Einzelerlaubnis ca. 250 EUR, 2-6 Wochen, EU-A2-Zeugnis noetig. Vorab-Pruefung ueber dipul.de. — [RP Baden-Wuerttemberg, Drohnen](https://rp.baden-wuerttemberg.de/themen/verkehr/luft/seiten/drohnen)
- dipul zeigt Wohngebiete, nicht einzelne Wohngrundstuecke (Forenhinweis, informell). — [drohnen-forum.de](https://www.drohnen-forum.de/index.php/Thread/64303-darf-ich-hier-fliegen-Wo-fliegen-in-konkrete-Ortsangaben/?pageNo=51)

### Inferences
- Google 3D Tiles/Earth: weder Geometrie noch Texturen entnehmen, auch nicht "von Hand abzeichnen". Als reine Sichtkontrolle im Browser unkritisch, aber kein Beleg im Sinn der Projektregeln (`beleg(...)` braucht freie Quelle).
- Drohnenflug Altstadt praktisch: Schwabentor und Martinstor stehen ueber Strassenbahn/Strasse und zwischen Wohn-/Geschaeftshaeusern, der Muensterplatz ist Markt- und Menschenmengen-Flaeche. Realistisch nur mit Sub-250-g-Drohne (A1), frueh morgens, mit Zustimmung der betroffenen Eigentuemer (Tore und Kaufhaus gehoeren der Stadt - Anfrage bei der Stadt) oder ueber die geografische Allgemeinerlaubnis (200 EUR). Freiburg-spezifische Zusatzverbote (Satzung, Muensterplatz) habe ich nicht gefunden - vor Flug bei Stadt/RP klaeren.
- Billige Alternative zur Drohne ohne Luftrecht: Teleskopstange (5-8 m) mit Kamera/360-Kamera, sowie Fotos von erhoehten oeffentlichen Standpunkten (Schlossberg/Kanonenplatz fuer Schwabentor-Dach, Muensterturm fuer Kaufhaus-Dach, Parkhaeuser) - das sind "Fernkameras" im Sinn der Lage-Regel und liefern Dach- und Helmform.
- OSM-Hoehen (Schwabentor 48 m, Kaufhaus First 19,5 m, Arkadenhoehe 4,5 m) sind unbelegte Schaetzungen einzelner Mapper; nur als Plausibilitaets-Hinweis gegen ALS/LoD2, nie als Sollwert.

### Gaps
- Cesium OSM Buildings, F4map: nicht eigens geprueft (sind Darstellungen der OSM-Daten oben).
- Kommerzielle Schraegbild-Anbieter (Vexcel, Bing Bird's Eye, Nearmap o. ae.) fuer Freiburg: nichts Belastbares gefunden.
- BKG-Bundesprodukte (z. B. bundesweite DOP/3D-Mesh): Suchtreffer zeigten nur allgemeine BKG-Nutzungsbedingungen fuer DOP, nichts Freiburg-Spezifisches; nicht vertieft.
- Freiburg-spezifische Drohnenregeln und ob die Strassenbahn als "Schienenweg" im Sinn des Paragrafen 21h zaehlt: ungeklaert.

## 4. Denkmalpflege, Archive, Literatur, vorhandene 3D-Modelle

### Takeaway
Fuer das Kaufhaus gibt es eine frei lesbare bauhistorische Arbeit mit Plaenen (Loebbecke 2009/2010, CC BY-NC 4.0) und Hinweise auf massstaebliche Plaene von 1885 und ein Architekten-Aufmass der Schusterstrassen-Fassade; fuer die Tore sind die Plaene Carl Schaefers (Umbau 1901) und das gemeinfreie Werk "Freiburg im Breisgau. Die Stadt und ihre Bauten" (1898) die naheliegenden Planquellen. Fertige 3D-Modelle der drei Objekte habe ich auf Sketchfab nicht gefunden. Veroeffentlichte Hoehenangaben der Tore widersprechen sich um mehrere Meter.

### Cited Findings

Datenbank Bauforschung/Restaurierung (Landesamt fuer Denkmalpflege BW):
- Historisches Kaufhaus, Objekt-ID 105442839812: zugeordnet "Bauhistorische Untersuchung" und "Restauratorische Untersuchung"; dendrochronologische Datierung der Kellerbalken (Haus C, 1208); "Gutachten Lohrum" zum Dach (Erneuerung 1708); Umbauplaene und Baubeschriebe fuer 1812-17, 1880-82, 1924-25 sind belegt; ein "verformungsgerechtes Aufmass der Hoffassade" wird EMPFOHLEN (existiert also offenbar nicht); drei Fotos Frank Loebbecke 2010; Einzelmasse aus dem Mauerwerksbefund (z. B. Fensterpfeiler 2,20 m breit, 1,90 m hoch). Rechte: "Alle Rechte vorbehalten", Landesamt fuer Denkmalpflege BW. — [bauforschung-bw.de, Historisches Kaufhaus](https://www.bauforschung-bw.de/objekt/id/105442839812/weitere-seite/2/historisches-kaufhaus-in-79098-freiburg-altstadt/)
- Martinstor, Objekt-ID 183702660413 (Eintrag vom 23.06.2016): Grundflaeche 10 x 11 m; Hoehe im Beschreibungstext 65 m, im Phasentext "von 22 m auf 60 m" (innerer Widerspruch); verknuepft "Dendrochronologische Datierung" und "Restauratorische Untersuchung"; keine Bauaufnahme/Plaene/Fotos gelistet; Beschreibung: rundbogiges Durchfahrtstor, Buckelquader-Ecken, verputzte Flaechen, umlaufender Fusswalm, runde Ecktuermchen mit Spitzhelmen, steiles Walmdach. — [bauforschung-bw.de, Martinstor (PDF)](https://www.bauforschung-bw.de/objekt/pdf/183702660413/martinstor.pdf)

Literatur mit Plaenen/Massen:
- Frank Loebbecke: "Das 'Historische Kaufhaus' in Freiburg im Breisgau und seine neu entdeckte Schaufassade zur Schusterstrasse", Alemannisches Jahrbuch 57/58 (2009/2010), S. 89-114, DOI 10.57962/regionalia-18404, Lizenz CC BY-NC 4.0, 27 Seiten PDF (ca. 49 MB). Enthaelt: EG-Grundriss und Untergeschoss-Grundriss (Plaene Mitte 19. Jh., Muensterbauhuette Freiburg; Abb. 3 und 7), Bauphasenplan der Strassenfassade Schusterstrasse 2010 "Grundlage: Architekturbuero Buehler und Mueller" (Abb. 4), Bauphasenplan Westgiebel (Abb. 5), Rekonstruktionen der Strassenfassade 13./16./18. Jh. und Befundplan 2010 (Abb. 16a-d), Foto Hoffassade um 1900 (Stadtarchiv Freiburg, M 7010). Chronologie-Eintrag: "1885 Erste ueberlieferte massstaebliche Ansichten, Grundrisse und Schnitte des Kaufhauses (Kanalisationsakten, Eigenbetrieb Stadtentwaesserung Freiburg)"; Sanierungen 1924-25 und 1987-91. Masse im Text: Haus A elf Meter tief/breit, Traufe 5 m, First ueber 11 m ueber heutigem Strassenniveau; Platzfassade mit vier Arkaden, Balkon, Ecktuermchen. — [RegionaliaOpen / BLB Karlsruhe (PDF)](https://regionalia.blb-karlsruhe.de/files/18404/BLB_Loebbecke_Historisches_Kaufhaus.pdf)
- Loebbecke verweist auf Peter P. Albert / Max Wingenroth: "Freiburger Buergerhaeuser aus vier Jahrhunderten", Freiburg 1923 (Nachdruck 1971), S. 91-120, Abb. 129-131 und 133 (Kaufhaus), und auf Hefele, Baugeschichte. — [RegionaliaOpen (PDF)](https://regionalia.blb-karlsruhe.de/files/18404/BLB_Loebbecke_Historisches_Kaufhaus.pdf)
- Friedrich Hefele: "Zur Baugeschichte des Freiburger Kaufhauses", Zeitschrift des Breisgau-Geschichtsvereins "Schau-ins-Land" 51.-53. Jahresheft, 1926, S. 1-24 (online verfuegbar laut Wikipedia). — [Wikipedia, Historisches Kaufhaus](https://de.wikipedia.org/wiki/Historisches_Kaufhaus_(Freiburg_im_Breisgau))
- Badischer Architecten- und Ingenieur-Verein (Hrsg.): "Freiburg im Breisgau. Die Stadt und ihre Bauten", H. M. Poppen & Sohn 1898; Volltext-Scan bei archive.org; UB-Freiburg-Digitalisat in der DDB mit Public Domain Mark 1.0; Kapitel "Kaufhaus und Kornhaus" von Friedrich Kempf ab S. 424; Kapitel "Das alte Freiburg" (Korth) mit Martinstor S. 202. Ob Grundriss-/Aufrisstafeln der Tore enthalten sind: nicht seitenweise geprueft. — [archive.org (PDF)](https://archive.org/download/freiburgimbreisg00badi/freiburgimbreisg00badi.pdf), [Wikisource-Index](https://de.wikisource.org/wiki/Index:Die_Stadt_und_ihre_Bauten_(Freiburg)), [DDB-Eintrag](https://www.deutsche-digitale-bibliothek.de/item/HICNLPKMHA7FCAEDFPQJSS2FFQZZP6CO)
- Jutta Schuchard: "Carl Schaefer 1844-1908. Leben und Werk des Architekten der Neugotik", Prestel 1979, ISBN 3-7913-0373-2, S. 311 f. (Torumbauten 1901); Peter Kalchthaler: "Freiburg und seine Bauten", 4. Aufl. 2006, ISBN 3-923288-45-X (Nr. 41 Schwabentor); Haumann/Schadeck: "Geschichte der Stadt Freiburg", Bd. 1; Badische Heimat 28 (1941), S. 343. — [Wikipedia, Martinstor](https://de.wikipedia.org/wiki/Martinstor), [Wikipedia, Schwabentor (Freiburg)](https://de.wikipedia.org/wiki/Schwabentor_(Freiburg_im_Breisgau))

Veroeffentlichte Masse und Baudaten (Vorsicht, Widersprueche):
- Martinstor: Grundflaeche 10 x 11 m; Mauerstaerke Suedseite 3,10 m im Erdgeschoss, 2,70 m im Obergeschoss; Schaefer schlug Erhoehung von 22 auf 66 m vor; gebaute Hoehe nennt der Artikel nicht; Umbau Sommer 1901 (Eugen Schmidt), Richtfest 28.08.1901; 1951 Reichsadler aussen entfernt, 1968/69 Martinsbild entfernt. — [Wikipedia, Martinstor](https://de.wikipedia.org/wiki/Martinstor)
- Martinstor-Hoehe je nach Quelle: 60 m (haeufigste Angabe), 62 m, rund 63 m, ca. 65 m. — [alemannische-seiten.de](https://www.alemannische-seiten.de/deutschland/freiburg_martinstor-freiburg.php) (62 m), [spar-mit.com](https://www.spar-mit.com/urlaubstipps/martinstor-freiburg) (63 m), [Structurae](https://structurae.net/de/bauwerke/martinstor) (ca. 65 m, 10 x 11 m), [bauforschung-bw.de](https://www.bauforschung-bw.de/objekt/pdf/183702660413/martinstor.pdf) (65 m und 60 m)
- Schwabentor: quadratischer Grundriss ca. 11 m Seitenlaenge; drei Geschosse ueber der spitzbogigen Durchfahrt; Aussenmauern am Fuss ueber 3,5 m stark, im obersten Geschoss etwa zwei Drittel davon; vor 1901 26 m hoch, Schaefers Vorschlag 65 m; um 1250 erbaut, stadtseitig offen, 1547 mit Steinwand geschlossen, 1572 Treppentuermchen; 1901 Umbau mit Treppengiebel (Geis & Bauer); 1903 St. Georg aussen (Fritz Geiges); 1913 Nebengebaeude; 1954 Teilrueckbau: einfacheres Zeltdach, Glockentuermchen mit Zwiebelhaube; Sanierung 2012-2015 (Fundament, Stahlbaender). Eine HEUTIGE Hoehe nennt der Artikel nicht. — [Wikipedia, Schwabentor (Freiburg)](https://de.wikipedia.org/wiki/Schwabentor_(Freiburg_im_Breisgau)); Aufstockung 1901 / Abtrag 1954 auch: [museum-digital BW](https://bawue.museum-digital.de/pdf/object/29182.pdf?lang=de)
- Kaufhaus: 6 Arkaden der gewoelbten Laube (4 zum Muensterplatz, 2 seitlich); 2 Eck-Erker; 4 Baldachin-Figuren zwischen den Fenstern (Maximilian I., Philipp der Schoene, Karl V., Ferdinand I.; Hans Sixt von Staufen 1530/31); "je fuenf" Wappenfelder unter den Erkerfenstern; Vorhangbogenfenster; Dach mit zwei Speichergeschossen und Schleppgauben (Anzahl nicht genannt); Baubeginn 1520, Fertigstellung 1532, Balkon 1550; historistischer Umbau 1880-84, Rueckbau 1924/25 (Karl Gruber); Sanierungen 1987-91 und 2000. — [Wikipedia, Historisches Kaufhaus](https://de.wikipedia.org/wiki/Historisches_Kaufhaus_(Freiburg_im_Breisgau))

Bildarchive:
- Landesarchiv BW, Staatsarchiv Freiburg, Sammlung Willy Pragher (W 134): z. B. "Freiburg: Martinstor von der Kaiser-Joseph-Strasse", 08.10.1977, Signatur W 134 Nr. 109742a, Lizenz CC BY 3.0 DE; der Eintrag liegt in einer Mappe "Stadttore" (Martinstor und Schwabentor). — [Deutsche Digitale Bibliothek](https://www.deutsche-digitale-bibliothek.de/item/OUOIFKSI7LMPZLXSAIXVZQR4QSM7774C); weiteres Pragher-Bild: [Europeana](https://www.europeana.eu/item/00738/plink__f_5_129252)
- Stadtarchiv Freiburg: Bildsignatur M 7010 (Hoffassade Kaufhaus um 1900) ist bei Loebbecke belegt. — [RegionaliaOpen (PDF)](https://regionalia.blb-karlsruhe.de/files/18404/BLB_Loebbecke_Historisches_Kaufhaus.pdf)
- Wikimedia Commons (eigene API-Abfrage 15.11.2026): Category "Schwabentor (Freiburg im Breisgau)" 162 Dateien + 4 Unterkategorien; "Martinstor (Freiburg im Breisgau)" 107 Dateien + 3 Unterkategorien; "Historisches Kaufhaus Freiburg" 131 Dateien + 6 Unterkategorien. — [Commons API](https://commons.wikimedia.org/w/api.php)

Vorhandene 3D-Modelle:
- Sketchfab-API-Suche 15.11.2026: "Schwabentor" 0 Treffer; "Martinstor" 1 Treffer (Detail "Aguila Imperial, Martinstor", nicht herunterladbar); "Historisches Kaufhaus Freiburg" 0 Treffer. Das LAD BW (Konto "ladbw") hat das Freiburger Muenster als Photogrammetrie-Modell, herunterladbar, CC BY-NC. — [Sketchfab API](https://api.sketchfab.com/v3/search?type=models&q=Martinstor), [Sketchfab, Freiburger Muenster (LAD BW)](https://sketchfab.com/3d-models/freiburger-munster-f0f4d479997f48659658fafebc14f90c)
- Das LAD arbeitet seit 2010 mit terrestrischem Laserscanner (Riegl VZ 400) und seit 2012 mit SfM. — [Sketchfab-Blog "3D at LAD BW"](https://sketchfab.com/blogs/community/3d-at-lad-bw)
- Ein druckbares "Stadtmodell Freiburg" (STL, Altstadt) ist ueber stlfinder gelistet (Herkunft/Lizenz/Detailgrad UNGEPRUEFT). — [stlfinder](https://stlfinder.com/model/stadtmodell-freiburg-dfMehK9Z/3489153)

### Inferences
- Hoechster Nutzen je Aufwand: (1) Loebbecke-PDF laden (Plaene Schusterstrasse/Westgiebel/Grundriss - genau die schlecht fotografierbare Rueckseite des Kaufhauses); (2) im archive.org-Scan von 1898 die Kapitel Kempf (S. 424 ff.) und Korth (um S. 202) nach massstaeblichen Tafeln durchsehen - gemeinfrei, also ohne Lizenzrisiko nutzbar; (3) Schuchard 1979 S. 311 f. per Bibliothek fuer Schaefers Aufrisse beider Tore von 1901 (fuers Martinstor gilt der 1901er Zustand im Wesentlichen noch, fuers Schwabentor nur bis zur Traufe - oben 1954 veraendert).
- Planquellen mit Massstab sind eine von GPS, LoD2 und SfM unabhaengige Massstabs- und Proportionsprobe (Regel "Lage unabhaengig belegen"). Alte Plaene zeigen aber Bauzustaende (1885, 1901, 1924/25) - gegen heutige Fotos pruefen, nicht blind uebernehmen.
- CC BY-NC (Loebbecke, LAD-Sketchfab) erlaubt private/nicht-kommerzielle Nutzung mit Namensnennung; bei Verkauf von Drucken waere das ein Problem. Masse/Fakten selbst sind nicht schutzfaehig, die Planzeichnungen schon.
- Anfragewege, die sich lohnen (alle unbelegt, ob Material herausgegeben wird): LAD BW (Bauforschungs-Berichte Kaufhaus/Martinstor; evtl. Scans der Schwabentor-Sanierung 2012-2015), Stadt Freiburg Gebaeudemanagement/Hochbauamt (Sanierungsaufmass Schwabentor 2012-15, Kaufhaus 1987-91), Architekturbuero Buehler und Mueller (Fassadenaufmass Schusterstrasse), Muensterbauhuette (Kaufhausplaene 19. Jh.), Eigenbetrieb Stadtentwaesserung (Plaene 1885), Stadtarchiv (Bestand C1 Bausachen "Tore und Tuerme" - nur als Suchtreffer-Titel gesehen, UNGEPRUEFT).
- Die Hoehenangaben der Tore (60/62/63/65 m; Schwabentor heute gar keine) taugen NICHT als Sollwert; die belastbare Hoehe muss aus ALS/DOM1 kommen. Die Grundflaechen (10 x 11 m; ca. 11 m) und Mauerstaerken sind brauchbare Grob-Gegenproben fuer den Massstab (Fehlergrenze ca. +/-0,5 m, da gerundet).
- Zaehl-Sollwerte fuers Kaufhaus aus der Literatur (4+2 Arkaden, 2 Erker, 4 Figuren, je 5 Wappenfelder) sind eine Gegenprobe zur Foto-Zaehlung, ersetzen sie aber laut Projektregel nicht.

### Gaps
- Bildindex/Foto Marburg, Leo-BW, Augustinermuseum-Sammlung online, Europeana-Gesamtbestand: keine verwertbaren Treffer in der Suche; nicht direkt in den Portalen recherchiert. Insbesondere Messbild-Aufnahmen (Preussische Messbildanstalt) der Freiburger Tore: nichts gefunden.
- Planarchiv/Nutzungsbedingungen des LAD BW und Gebuehren/Reproduktionsregeln des Stadtarchivs Freiburg: keine Quelle gefunden.
- Hefele 1926 und die 1898er Tafeln nicht selbst geoeffnet; ob massstaebliche Aufrisse der Tore enthalten sind, ist offen.
- Thingiverse/Printables/Cults: nicht systematisch durchsucht (keine offene API genutzt).
- Restaurierungsbericht Schwabentor 2012-2015: nur Wikipedia-Zusammenfassung, kein Primaerbericht gefunden.
- Aufloesung/Download der Pragher-Digitalisate beim Landesarchiv nicht geprueft.

## 5. Weitere Crowd-Bilder (Flickr, Commons, Google-Maps-Nutzerfotos, Instagram, Openverse) und Handy-Lidar

### Takeaway
Commons ist mit zusammen rund 400 Dateien (plus Unterkategorien) bereits die groesste freie Sammlung; Flickr laesst sich per API nach Lizenz und Bounding-Box filtern und ist die naechstbeste Ergaenzung. Handy-Lidar taugt an Fassaden nur im Nahbereich (ca. 5 m, Fehler einige Zentimeter) - als Massstabsreferenz fuer Durchfahrt/Arkaden brauchbar, nicht fuer obere Geschosse.

### Cited Findings
- Flickr `flickr.photos.search`: Filter `license` (mehrere IDs kommagetrennt; IDs ueber `flickr.photos.licenses.getInfo`), `bbox` (min. Laenge, min. Breite, max. Laenge, max. Breite), Geodaten ueber `extras`; mit bbox maximal 250 Treffer je Seite. — [Flickr API-Doku](https://flickr.com/services/api/flickr.photos.search.html), Parameterdetails aus R-Wrapper-Doku: [FlickrAPI getPhotoSearch](https://rdrr.io/pkg/FlickrAPI/man/getPhotoSearch.html)
- Beispiel fuer vorhandene Flickr-Bilder: "Freiburg im Breisgau - Martinstor" (Lizenz des Einzelbilds nicht geprueft). — [Flickr](https://www.flickr.com/photos/133876835@N08/52338077072/)
- Commons-Bestand siehe Abschnitt 4 (162 / 107 / 131 Dateien). — [Commons API](https://commons.wikimedia.org/w/api.php)
- Google-Inhalte (Karten, Street View, damit auch die ueber Google ausgelieferten Bilder): kein Export/Scraping "for use outside the Services", kein Massendownload, keine Bildanalyse. — [Google Map Tiles API Policies](https://developers.google.com/maps/documentation/tile/policies)
- iPhone-Lidar-Genauigkeit: EGU-2026-Beitrag mit drei Apps (Modelar, 3D Scanner, SiteScape): RMS 1,34 cm bei kleinen Objekten bis 4,6 cm bei Gebaeudefassaden; Grenzen bei grossen Architekturelementen. — [EGU26-2752](https://meetingorganizer.copernicus.org/EGU26/EGU26-2752.html)
- Scaniverse auf iPhone 12 Pro: ca. +/-1 cm bei kleinen Objekten, ca. +/-10 cm bei grossen Objekten (bis 130 x 15 x 10 m). — [Geodetski vestnik, Yanchuk et al.](https://geodetski-vestnik.com/arhiv/70/1/47_Yanchuk.pdf)
- ISPRS 2026, fuenf iPhone-Scan-Apps: Zentimeter-Genauigkeit moeglich, stark app-abhaengig; bestes Lage-RMSE 49,8 mm. — [ISPRS Archives XLIX-M-1-2026](https://isprs-archives.copernicus.org/articles/XLIX-M-1-2026/1/2026/)
- Herstellerangabe Polycam: +/- 1/2 Zoll innerhalb ca. 5 m je Flaeche (Eigenwerbung). — [Polycam-Blog](https://poly.cam/blog/polycam-vs-faro-focus-when-mobile-scanning-replaces-a-terrestrial-scanner)

### Inferences
- Flickr-Abruf fuer die Pipeline: bbox je Objekt (ca. 150 m), nur CC-Lizenzen und Public Domain, `extras=geo,url_o,date_taken,license,owner_name`; Originale (`url_o`) wegen EXIF bevorzugen (vgl. Punkt 5 des Software-Berichts). Attribution je Bild in einer Quellenliste mitfuehren. Flickr-Geotags sind Nutzerangaben (Karten-Klick), also nicht als GPS-Prior verwenden.
- Commons: Unterkategorien (4/3/6) mit abholen; Wiki-Loves-Monuments-Bilder liegen in denselben Kategorien. Die meisten sind CC BY-SA - gleiche Share-Alike-Frage wie bei Mapillary.
- Google-Maps-Nutzerfotos und Instagram: als SfM-Eingang nicht nutzen (Plattformbedingungen gegen Scraping; Urheberrecht liegt bei den einzelnen Nutzern, keine freie Lizenz). Zu Instagram und Openverse habe ich keine Quelle abgerufen - Einstufung ist meine Einschaetzung.
- Handy-Lidar als Massstabsanker: Durchfahrt des Schwabentors/Martinstors bzw. zwei Arkadenjoche des Kaufhauses scannen, daraus 3-5 Strecken von 3-10 m (Torbreite, Pfeilerabstand, Sockelhoehe) entnehmen. Bei 2-5 cm Fehler auf 5-10 m sind das 0,5-1 % Massstabsfehler - schlechter als ein Stahlmassband/Laserdistanzmesser (wenige Millimeter), aber flaechig. Ein Laserdistanzmesser auf 2-3 markante Strecken ist die genauere und billigere Massstabsreferenz.

### Gaps
- Anzahl frei lizenzierter, verorteter Flickr-Bilder je Objekt: nicht abgefragt (API-Schluessel noetig).
- Flickr-Lizenz-ID-Liste und API-Nutzungsbedingungen nicht an der Primaerquelle gelesen.
- Instagram-, Google-Maps-Nutzerfoto- und Openverse-Bedingungen: nicht recherchiert.
- Keine Studie gefunden, die Massstabsfehler von Polycam/Scaniverse an einer Fassade gegen eine kalibrierte Strecke misst.

## 6. Massstabs- und Massreferenzen unabhaengig von GPS und LoD2

### Takeaway
Wirklich unabhaengige Massstabsbelege sind: ALS-Punktwolke und DOP10/TrueDOP (amtlich georeferenziert, +/-0,25 m Lage), amtliche Luftbilder mit Orientierung, Fremd-SfM-Posen von Mapillary, eigene Streckenmessungen vor Ort (Laserdistanzmesser/Handy-Lidar) und massstaebliche historische Plaene. Veroeffentlichte Zahlen (Grundflaeche 10 x 11 m, Mauerstaerken) sind nur Grobproben; Turmhoehen aus der Literatur sind widerspruechlich.

### Cited Findings
- DOP10 Lagegenauigkeit im Mittel +/-0,25 m, DOP20 +/-0,5 m. — [LGL DOP10](https://www.lgl-bw.de/Produkte/Luftbildprodukte/DOP10/index.html)
- ALS_3/ALS_2 mindestens 8 Punkte/m2, Hoehen in DHHN2016. — [LGL ALS_3](https://www.lgl-bw.de/Produkte/3D-Produkte/Laserscandaten/ALS_3/index.html)
- "Punktdaten mit Katasternachweis" (Vermessungspunkte) werden vom LGL unentgeltlich bereitgestellt; ALKIS-Hausumringe sind Open Data. — [LGL, Open_GeoData_Liste_Datensaetze.pdf](https://bwmm-support.lgl-bw.de/export/sites/lgl/Produkte/Open-Data/Galerien/Dokumente/Open_GeoData_Liste_Datensaetze.pdf)
- LGL-LoD2 beruht auf ALKIS-Grundrissen plus Laserhoehen. — [Runder Tisch GIS, LoD2 BW](https://katalog.rundertischgis.de/en/dataset/3d-gebaudemodelle-lod2-b-w)
- Mapillary liefert je Bild `atomic_scale` und SfM-korrigierte Position/Hoehe. — [Mapillary API-Dokumentation](https://www.mapillary.com/developer/api-documentation)
- Martinstor 10 x 11 m, Mauer Sued 3,10 m (EG) / 2,70 m (OG); Schwabentor ca. 11 m im Quadrat, Mauer am Fuss ueber 3,5 m. — [Wikipedia, Martinstor](https://de.wikipedia.org/wiki/Martinstor), [Wikipedia, Schwabentor (Freiburg)](https://de.wikipedia.org/wiki/Schwabentor_(Freiburg_im_Breisgau))
- Kaufhaus, Altbau Haus A: elf Meter breit/tief, Traufe 5 m, First ueber 11 m ueber heutiger Strasse (Befund Loebbecke). — [RegionaliaOpen (PDF)](https://regionalia.blb-karlsruhe.de/files/18404/BLB_Loebbecke_Historisches_Kaufhaus.pdf)
- Handy-Lidar an Fassaden: RMS ca. 4,6 cm. — [EGU26-2752](https://meetingorganizer.copernicus.org/EGU26/EGU26-2752.html)

### Inferences
- Rangfolge fuer das Massstabs-/Lage-Tor (von stark nach schwach): (1) ALS-Gebaeudepunkte + DOP10/TrueDOP-Dachkanten (amtlich, unabhaengig von ALKIS-Grundriss), (2) eigene Strecken vor Ort mit Laserdistanzmesser, (3) orientierte amtliche Luftbilder bzw. staedtische Schraegbilder als Zusatzkameras, (4) Mapillary-Posen, (5) massstaebliche Plaene (1885/1901), (6) Literaturzahlen. LoD2 und ALKIS-Umring zaehlen als EINE Quelle.
- TrueDOP ist fuer hohe Tuerme wichtig: im klassischen DOP kippt ein 60-m-Turm je nach Bildlage um viele Meter um; nur im TrueDOP liegt die Dachkante lagerichtig. Vor Nutzung pruefen, ob die Freiburger Kachel schon TrueDOP ist (DOP20 laut LGL seit 2020, DOP10 laut LGL seit Sommer 2025).
- "Standard-Elementgroessen" (Ziegel, Stufen, Tuerhoehen) sind an mittelalterlichem Quader-/Bruchsteinmauerwerk nicht normiert und daher als Massstab ungeeignet; moderne Normteile im Bild (Strassenbahn-Fahrdrahthoehe, Gleisspurweite der VAG, Verkehrszeichen) waeren moegliche Hilfsmasse, dazu habe ich aber keine Quelle erhoben - ANNAHME, vor Nutzung belegen.

### Gaps
- Keine amtlichen Hoehenfestpunkte/Hoehenbolzen an den drei Objekten recherchiert (Festpunktinformationen des LGL nicht gesucht).
- Keine verlaessliche veroeffentlichte Gesamthoehe fuer Schwabentor (heutiger Zustand) und keine Fassadenlaenge/Traufhoehe des Kaufhaus-Neubaus am Muensterplatz gefunden.
- Spurweite/Fahrdrahthoehe der Freiburger Strassenbahn als Hilfsmass: nicht belegt.

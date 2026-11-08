# Anleitung Fotos mit dem nubia (Z2462N, "Focus 2 5G") fuer Photogrammetrie

Stand der Recherche: 2026-11-06. Kennzeichnung: [G] = gesichert (Quelle belegt), [V] = Vermutung / nicht belegt, [?] = Menue unsicher, am Geraet nachsehen.
Die Menuepunkte der nubia-Kamera-App konnten im Web NICHT belegt werden. Nubia-Handbuch/Support wurde nicht gefunden.

## A. Das Geraet

- [G] Z2462N = nubia Focus 2 5G (Zertifizierung/SIRIM Feb. 2025, Nachfolger Focus 5G). Z2463N ist ein ANDERES Modell (Focus 2 Ultra, 50 MP).
  https://lowyat.net/2025/343188/nubia-focus-2-sirim , https://www.gizchina.com/2024/12/19/nubia-focus-2-5g-spotted-on-new-certification , https://aio.lv/en/product--nubia-z2463n--11653371.md
- [G, Haendlerangabe] Hauptkamera 108 MP, Sensor 1/1.67", Blende f/1.75. Zusatz: 2 MP Tiefe + 0,08 MP Hilfskamera, Blitz; Selfie 8 MP (16 MP per Software). Quelle: https://ztemobiles.com.au/nubia-focus-2-5g/
  Andere Quellen widersprechen bei Nebenkameras/Selfie (5 MP UW, 50 MP Selfie sind als "erwartet/Geruecht" markiert): https://app.cashify.in/nubia-focus-2-5g-price-in-india . Fuer uns zaehlt nur die Hauptkamera; eine echte Ultraweitwinkel-Kamera ist wahrscheinlich NICHT vorhanden [V]. Ein indonesischer Artikel sagt, nur der 108-MP-Sensor sei funktional (https://gizmologi.id/gadget/smartphone/nubia-focus-2-5g-108mp-rp2-jutaan/ , nur Suchausschnitt gelesen).
- [G] Stabilisierung: Seite nennt nur EIS (elektronisch), kein OIS (ztemobiles-Seite oben). Fehlende Erwaehnung ist kein Beweis, aber OIS ist unwahrscheinlich [V].
- [G, Haendlerseite] Kamera-Modi laut Hersteller-Haendler: Pro-Modus, 108MP Ultra Res, Panorama, Portrait, Super Night, HDR, Zeitraffer. RAW wird dort NICHT erwaehnt. Beim Vorgaenger Focus 5G nennt Notebookcheck "RAW HDR"/RAW-Fotos (https://www.notebookcheck.com/Nubia-Focus-5G-packt-108-MP-Kamera-und-120-Hz-Display-ins-guenstige-Mittelklasse-Smartphone.807934.0.html) -> beim Focus 2 [V], am Geraet pruefen.
- [G] Die Seite nennt "Brennweiten-Modi" 24/35/50/72 mm (KB-aequivalent). Bei einem Einzel-Hauptsensor ohne Tele sind 35/50/72 mm sehr wahrscheinlich digitale Ausschnitte des 108-MP-Sensors [V]. 24 mm = Grundbrennweite [V].
- [G] Review (Notebookcheck): ausser dem 108-MP-Modus unauffaellige Bilder: https://www.notebookcheck.net/Nubia-Focus-2-5G.1136976.0.html
- Nicht gefunden: Dateiformat (JPEG/HEIF) und Ausgabeaufloesung im Standardmodus (50/12/12,5 MP oder pixelgebinnt?), Menuepfad Wasserzeichen/Standort, Name und Lage von Rauschfilter/KI/Beauty-Schaltern, AE/AF-Sperre. Alles [?].

## B. Praxis Photogrammetrie (Quellenlage)

- [G] COLMAP: hohe Ueberlappung, jedes Objekt in mind. 3 Bildern, verschiedene Standpunkte; SIMPLE_RADIAL Standardmodell, OPENCV fuer staerkere Verzeichnung; Intrinsics werden mitgeschaetzt, Hauptpunkt bleibt fest. https://colmap.github.io/tutorial.html , https://colmap.github.io/faq.html
- [G, Drittquelle] Nicht aus der Position drehen, einige Schritte zwischen Bildern gehen; mehr Bilder sind nicht automatisch besser. (Spiegel des COLMAP-Tutorials, siehe Suchtreffer) https://colmap.readthedocs.io/en/stable/tutorial.html
- [G, Drittquelle] Ueberlappung 60-80 % aufeinanderfolgend, jeder Punkt in >= 5 Bildern, diffuses Licht, Licht konstant: https://www.pix-pro.com/blog/photogrammetry-settings-checklist , https://www.pix-pro.com/blog/photogrammetry-with-the-smartphone
- [G, Drittquelle Gaussian-Splatting-Tutorial, Objektmassstab] Zoom, Autofokus und Auto-Belichtung vermeiden, feste Brennweite: https://smartdatascan-site.pages.dev/tutorials/gaussian-splatting-windows/colmap/_print
- [V] Fokus/Belichtung sperren und Videos vs. Fotos: im Web keine belastbare Primaerquelle gefunden. Praktisch: Fotos mit fester Brennweite sind fuer Kalibrierung besser als Video (Rolling Shutter, Komprimierung) [V]. Fassadenmaterial aus Video (Drohne) bleibt eine eigene Quelle im Projekt.
- [V] Fuer Fassaden: parallel zur Wand entlang laufen (Seitenverschiebung statt Drehen), zwei Hoehen/Winkel, Eckenbereiche mit Drehung in Schritten von ~15 Grad.

## C. Brennweite kalibrieren ohne Spezialgeraet

- [G] OpenCV-Kalibrierung: Brennweite und Hauptpunkt aus Bildern eines Schachbretts, viele unterschiedliche Lagen/Winkel noetig (aehnliche Bilder -> schlecht gestelltes Problem), Kantenlaenge der Felder muss bekannt sein. https://docs.opencv.org/4.x/d4/d94/tutorial_camera_calibration.html , https://automaticaddison.com/?p=9126
- [V, nicht belegt] Muster am Monitor: Feldgroesse am Bildschirm mit Lineal nachmessen, Monitor flach, Moire/Pixelraster vermeiden (Abstand gross genug, Muster gross). Besser: auf starres Brett geklebter Ausdruck. Fuer Brennweite in Pixeln ist die absolute Feldgroesse sogar unwichtig (nur fuer Meter), das Seitenverhaeltnis der Felder muss quadratisch sein [V, aus Geometrie].
- ChArUco ist robuster bei Teilsicht [V]; OpenCV-Doku zu ChArUco hier nicht abgerufen.
- Wichtig: Kalibrieren in genau dem Modus, der spaeter fotografiert wird (gleiche Aufloesung, gleicher Zoom-Stufe, gleiche Fokusdistanz ~ unendlich). Autofokus-Fokus-Atmen aendert die effektive Brennweite leicht [V]. Eine Selbstkalibrierung im Bundle ist ohnehin Pflicht (COLMAP).
- EXIF: FocalLength und FocalLengthIn35mmFilm pruefen (Projektregel 3d: EXIF-Brennweite oder f_gruppe fuer Fotos ohne Bodenanker). 35-mm-Wert ist bei digitalem Zoom oft schon umgerechnet -> dann zaehlt NICHT der Sensor-Pixelabstand [V].

## D. Kurzanleitung vor Ort (priorisiert)

1. Kamera-App oeffnen, Kameraeinstellungen (Zahnrad) durchgehen [?]: **Wasserzeichen AUS** (stoert Merkmalssuche, nur Bildecke aber trotzdem). Generisch: https://www.xda-developers.com/how-to-turn-off-manufacturer-watermarks-camera-app-remove-post/ (nicht nubia-spezifisch).
2. **Standort-Tag AN** (GPS in EXIF) [?]; Android-Standortberechtigung der Kamera-App auf "Immer/bei Nutzung" setzen. Danach 1 Foto machen und am Rechner EXIF pruefen (GPSLatitude vorhanden?).
3. **Hauptkamera, 1x, KEIN Zoom** (nicht 35/50/72 mm, nicht Pinch). Alle Fotos derselben Serie in identischer Stufe. Naeher an das Objekt gehen statt zoomen.
4. **Ein Aufloesungs-/Formatmodus fuer alles** (Standard oder 108 MP). Empfehlung [V]: Standardmodus mit voller nativer Aufloesung, kein "Ultra Res" mischen; Modus notieren (Exif ImageWidth pruefen). 108 MP nur, wenn Speicher/Laufzeit egal und scharf (Verwackelung bei Handaufnahme).
5. **HDR/KI/Szenenoptimierung/Schoenheit/Filter AUS**, kein Super Night, kein Portrait, keine Filter [?]. HDR-Fusion verschiebt Pixel bei Bewegung [V].
6. **Pro-Modus nutzen, falls vorhanden** [G: Modus existiert]: ISO niedrig (<= 200-400), Verschlusszeit <= 1/250 s (Handverwackelung, es gibt kein OIS), Weissabgleich fest (z. B. Tageslicht), Fokus fest auf ~unendlich/Gebaeudeabstand. Wenn kein Fokus-Schieber: Antippen und AE/AF-Sperre halten [?].
7. RAW/DNG nur wenn angeboten [V], sonst JPEG. Kein Nachbearbeiten (kein Zuschneiden, Drehen, Verbessern) vor der Uebergabe; Originale unveraendert kopieren.
8. Aufnahme: parallel zur Fassade seitlich gehen, ca. 70-80 % Ueberlappung, Abstand gleichmaessig; je Fassade zwei Hoehen/Neigungen; an Ecken in kleinen Schritten drehen, alle 2-3 Schritte ein Bild; nicht aus der Hand drehen (Parallaxe). Keine Personen/Autos im Vordergrund soweit moeglich. Gleichmaessiges Licht (bedeckt).
9. Mind. 10-20 Bilder eines Kalibriermusters (Schachbrett/ChArUco, Ausdruck auf starrem Brett oder grosser Monitor) in GENAU diesem Modus am Ende der Serie, aus verschiedenen Winkeln und Abstaenden.
10. Fotos nur im Originalformat per Kabel/Dateiuebertragung uebergeben (nicht Messenger, der EXIF/GPS entfernt und neu komprimiert) [V].

## E. Offene Punkte (sofort am Geraet klaeren und zurueckmelden)

- Genauer Menuepfad Wasserzeichen / Standort / HDR-Aus; vorhanden: AE/AF-Sperre? RAW im Pro-Modus?
- Ausgabeformat und -aufloesung im Standardmodus (EXIF eines Testfotos).
- Was die Zoom-Stufen 35/50/72 mm technisch sind (EXIF-Pixelgroesse vergleichen: gleich gross = digital interpoliert).
- Ob "Fokus ~unendlich" im Pro-Modus einstellbar ist.

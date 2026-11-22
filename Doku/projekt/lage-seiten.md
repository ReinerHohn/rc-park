# 🧭 Lage, Maßstab, Seiten & Bildquellen  ← [PROJEKT.md](../../PROJEKT.md)
Details: `modelle/archiv/STAND_2026-11-14.md` · `modelle/LOGBUCH_KETTENTEST_2026-11-19.md` · Skill `wolke-tore` · Ast [foto-sfm](foto-sfm.md)

## Gilt
- **Tor-Reihenfolge nach jeder Ausrichtung (Nutzer 15.11. "lerne mit"):** Insel-Kette, Lot aus Fotos, GPS, Laser-Hoehe (DOM1), Gruppen-Punkt, Schnittbilder ansehen - erst dann messen [memory feedback-lehren-schwabentor-1511]
- **Fit und Beweis trennen:** Ausrichtung gilt erst, wenn Groessen ausserhalb des Fits sie bestaetigen (Foto-GPS, Fernkameras, Gebaeudemass, Kameras nicht im Haus) [memory feedback-lage-unabhaengig-belegen]
- **Muss ohne GPS gehen, mit GPS sicherer (Nutzer 19.11.);** eigene Fotos kuenftig mit GPS + Kompass als Anker [LOGBUCH 19.11. 14:05, memory project-gps-in-exif-kuenftig]

## Versucht
**Ausrichtung: LoD2 · GPS · Lot · Maßstab**
- 31.10. · VGGT/freie Aehnlichkeit (Massstab+Neigung+Drehung zugleich) → ✗ · nicht identifizierbar, kollabiert; nur mit Pose-Anker, dann 2,5D ~1 m [VERSUCHSREGISTER G0]
- 01.11. · Ausrichtung ueber 4 einzeln kalibrierte Kameras / Massstab aus eigener Turmhoehe → ✗ · ungenaue Zentren bzw. zirkulaer [VERSUCHSREGISTER AE]
- 01.11. · `sfm_ausrichten.py` mit LoD2-Eckkanten-Linien + Bodenpunkten → ✓ Methode · Massstab +-2,2 %; Linien brauchen Richtung, Hoehe aus Bodenpunkt [VERSUCHSREGISTER AH]
- 01.11. · Pick-Registrierung von Luft-/Fernbildern (`sfm_registrieren.py`) → ✓ · Zeilengleichheit gleich hoher Punkte = Kamerahoehe; verlaengert nur metrisches Netz [VERSUCHSREGISTER AJ]
- 02.11. · Massstab aus mehreren Quellen (`massstab_schwarm.py`) → ✓ teils · nur EXIF-GPS unabhaengig; LoD2-Nachbarkanten/Personen abhaengig [VERSUCHSREGISTER BP]
- 08.11. · Umeyama auf flach liegenden Kamerazentren / ICP mit freiem Massstab → ✗ · Rotation schlecht bestimmt, ICP schrumpft die Wolke [NICHTS_GEBRACHT BS143/BS146]
- 08.11. · Boden-/Wand-Ebenenfit mit z-Fenster-Auswahl → ⚠ Falle · Selektion auf abhaengiger Variable meldet 25-Grad-Kippung als eben [NICHTS_GEBRACHT BS150]
- 14.11. · Lagepruefung per FFT-Wandlinien / Silhouetten-IoU gegen LoD2 → ✗ nur Hinweis · trennt Drehlagen nicht; Tor bleibt Test A [NICHTS_GEBRACHT 2026-11-14]
- 15.11. · "passt zum LoD2-Grundriss" als Massstabsbeleg → ✗ · LoD2 = Sockelumring, Modell 7 % zu gross; DOM1 (`hoehe_gegen_dom1.py`) [NICHTS_GEBRACHT 15.11.]
- 15.11. · entzerrtes Einzelfoto als SfM-freie Massstabsprobe → ✗ · nutzt die SfM-Kamera, nicht unabhaengig [NICHTS_GEBRACHT 15.11.]
- 15.11. · LoD2-Fit bei vielen Video-/fernen Kameras → ✗ · entartet; ↺ Ausrichtung ueber gemeinsame Kameras uebertragen (`ausrichtung_uebertragen.py`) [archiv/STAND_2026-11-14 07:30]
- 15.11. · GPS-Fit ueber alle Kameras → ⚠ Falle · km-ferne Kameras kippen ihn; Start nur aus Kamerakern [archiv/STAND_2026-11-14 08:40]
- 15.11. · GPS-Tor ohne gefundene Fotos → ⚠ Falle · bestand stumm rc 0; jetzt < 50 % gefunden = rc 4 [archiv/STAND_2026-11-14]
- 15.11./19.11. · iPhone-/Wikimedia-Geotags als Schiedsrichter → ⚠ Falle · Muensterplatz 52 % > 15 m, Wikimedia "jm" = Objektstandort; nur Mehrheit zaehlt [archiv/STAND_2026-11-14 08:14, GLOBALER_MAPPER_STABIL 01:50]
- 15.11. · Lot aus Fluchtpunkten der Senkrechten (`lot_aus_fotos.py`) → ✓ · fand 0,77 Grad Schieflage der Kameraebene [archiv/STAND_2026-11-14 14:40]
- 19.11. · Lot als Normale der Kameraebene bei Drohnenclips → ✗ · 86,6 Grad daneben; ↺ Lot aus Kamerablick (Bild-x-Achsen) bei Widerspruch > 15 Grad [LOGBUCH 19.11. 08:47]
- 19.11. · Grobsuche Massstab ohne Startwert → ✗ · Faktor 3,6 falsch; ↺ Start aus Strassenkamera-Hoehe ~1,6 m + Hoehenprobe gegen LoD2 [LOGBUCH 19.11. 09:05-09:35]
- 19.11. · Kameralot fuer Drehachse ueber 60 m → ⚠ Falle · 2,3 Grad Kippung = 2 m am Boden; Lot aus Wandnormalen der dichten Wolke [LOGBUCH 19.11. 21:10]
- 19.11. · Wolken-Gruppen-Tor (Punkte > 6 m ueber LoD2-Umgebung) → ✓ · nennt fehlverortete Clips; > 6 % unmoeglich = Ausrichtung falsch [LOGBUCH 19.11. 10:15]
- 19.11. · unstabile Konsens-Kameras in die dichte Wolke → ✗ · schiefe Haeuserzeile; `dicht_bildwahl --ohne unstabil.txt` [LOGBUCH 19.11. 09:57]
- 15.11. · Drohnenclip als Kette an ein einziges Torbild → ⚠ Falle · Massstab der Kette kollabiert (Flug 500 m -> 27 m); Insel-Tor `kette_insel_pruefen` [archiv/STAND_2026-11-14]

**Seitenverwechslung & Seiten vereinen**
- 01.11. · alle Fotos eines symmetrischen Turms in einer SfM → ✗ · beide Uhrseiten zu einer Fassade verklebt [VERSUCHSREGISTER AH]
- 01.11. · Seite je Foto aus asymmetrischem Merkmal (Nebenhaus links/rechts), Netz je Seite → ✓ Methode (Handliste) · Nord metrisch; braucht Vorwissen [VERSUCHSREGISTER AH, memory sfm-seitentrennung-symmetrie]
- 01.11. · Seite ueber Registrierung/Punktverhaeltnis in beiden Seitennetzen → ✗ · registriert in beiden, Marge 1,3 zu knapp [VERSUCHSREGISTER BE]
- 15.11. · Gruppen-Punkt-Tor (gleicher Knauf aus jeder Fotogruppe) → ✓ · Knauf 6,26 -> 0,9 m; braucht Hand-Picks [archiv/STAND_2026-11-14 23:55]
- 15.11. · einfache Aehnlichkeit fuer verzerrtes Sued-Teilmodell / mehr BA → ✗ · Gruppe verzerrt, nicht skaliert; BA auf gleichen Zuordnungen hilft nicht [NICHTS_GEBRACHT 15.11.]
- 19.11. · Zeitfenster +-12 Bilder um Videotreffer in der Vorpruefung → ✓ teils · 453/596 registriert, Gegenseite trotzdem leer [LOGBUCH 19.11. 10:20/11:46]
- 19.11. · Videosuche mit Treffer-Beweis gegen Objektfotos fuer ungesehene Seite → ✗ · findet grundsaetzlich nur gesehene Seiten [LOGBUCH 19.11. 12:05]
- 19.11. · Louvain-Gemeinschaften im Paargraphen (Aufloesung 2,0) + Pruefer je Verbindung (`seiten_erkennen.py --streng`) → ✓ Methode · Martinstor Nord/Sued rein getrennt [LOGBUCH 19.11. 12:45-16:00]
- 19.11. · Pruefer-Urteil per Median-Schwelle → ↺ ersetzt durch "echt ab 10 % eindeutig gleich, verwechselt bei p90 < 0,5" · Median trennt nicht [LOGBUCH 19.11. 13:45]
- 19.11. · Sim3-Anteil gemeinsamer Punkte (`seiten_geometrie.py`) → ✗ · kleine Video-Teilmodelle verzogen; nur Messwerkzeug [LOGBUCH 19.11. 13:45]
- 19.11. · GPS-Standrichtung ueberstimmt Pruefer → ✗ · Handy-GPS in Gassen zig Grad daneben; GPS entscheidet nur "unklar" [LOGBUCH 19.11. 14:05]
- 19.11. · Seiten vereinen ueber Klappung: Verklebung = 180-Grad-Drehung um Achse → ✓ Methode (Handlisten-Seitenmodelle) · Achse aus Helmstange, Flankenprobe am Nachbarhaus [LOGBUCH 19.11. 16:00/18:45/21:10]
- 19.11. · Drehachse = LoD2-Grundrissmitte → ✗ · 0,9 m daneben; Achse aus dem Bau selbst, LoD2 nur Gegenprobe [LOGBUCH 19.11. 18:45]
- 19.11. · Verlorene Bilder an Geruest anhaengen nach blosser Registrierung → ✗ · Kontrolle registriert auch; ↺ "nur Geruestpunkte >= 300 auf 30 %" in Runden [LOGBUCH 19.11. 18:15]
- 20.11. · `gps_seiten_pruefen.py` als Hinweis-Tor → ✓ · erst ab 25 GPS-Bildern im 150-m-Umkreis (sonst Fehlalarm) [339cf0d66]
- 20.11. · Seiten vereinen aus globalen Stücken (Klappung) → ✗ nur 50–53 tragende Punktpaare, Achse 14–20 % uneinig · Rückfall: jede Seite an LoD2

**Bildquellen (Commons, Videos, Netzfotos, eigene)**
- 01.11. · nur Commons-Kategorie des Objekts → ⚠ Falle · Schraegluftbild der verdeckten Seite lag ausserhalb der Kategorie [VERSUCHSREGISTER AF]
- 01.11. · Commons-Ernte → ✓ Methode mit Regeln · Geosearch `gsprimary=all`, EXIF per `iiprop=metadata`, 429 nach ~100: warten, kein Retry-Sturm [VERSUCHSREGISTER AI, archiv/LOG_ONLINE_DACH_2026-11-09]
- 02.11. · Mapillary/KartaView/Panoramax → ✗ · NC-Lizenz bzw. defektes GPS / keine Abdeckung; erreichen verdeckte Seiten nicht [VERSUCHSREGISTER AF/BI]
- 02.11. · YouTube-Drohnenclips (Wasserzeichen maskiert, Kamera je Clip, `video_sfm.py`) → ✓ Methode · decken Dach/Spitze; YouTube nur private Messvorlage [VERSUCHSREGISTER BQ, memory web-scan-video]
- 03.11. · Vorwaertsfahrt-Videos mit SIFT exhaustive → ✗ · nur Fragmente; ALIKED+LightGlue noetig [memory gpu-leerlauf-video-sfm-fragmente]
- 09.11./14.11. · Webfotos von oben (Schlossberg/Muensterturm) in Strassenmodell → ✗ meist · 3/8 bzw. 0/10 registriert, kein Dachgewinn [NICHTS_GEBRACHT 9.11./14.11.]
- 15.11. · Kaufhaus-"eigene" Chat-Kopien ohne EXIF in SfM → ⚠ Falle · globaler Lauf schlechter; nur Originale mit EXIF [archiv/STAND_2026-11-14 07:30-08:14]
- 16.11. · "kein registriertes Foto" = "kein Foto" (Spiegeln) → ✗ · Bestand hatte 2 Ostfotos; Kontaktbogen des ganzen Bestands [NICHTS_GEBRACHT 16.11.]
- 19.11. · Netzfotos erst in Stufe `seiten` hinter den Lage-Toren → ↺ Stufe `commons` vor der SfM (`netz_fotos_holen.py`) [e3800163]
- 19.11. · ganze Clips (N schaerfste von 300) statt Trefferabschnitten → ⚠ Falle · Quelle der 637 fremden Bilder [LOGBUCH 19.11. 16:50 Punkt 47]
- 19.11. · Openverse / Commons-Umkreis fuer Gegenseite → ✗ · 21 Bilder bzw. historische Festzuege vom Turm, keine Gegenseite [LOGBUCH 19.11.]
- 19.11. · vorhandenes `sfm/sparse/0` bei neuem Fotosatz weiterverwenden → ✗ · neue Fotos ignoriert; `pipe/fotosatz.json` loest SfM neu aus [8d4a94d9]
- 22.11. · Seitenteil allein ueber Foto-GPS einsetzen (schwabentor-1122 Teil 1) → ✗ · 3-4 m versetzt, Grundriss A 17,6 %, doppelwand; jetzt Regel 'nur bei belegter Lage' (`tools/seiten_lage_beleg.py`), sonst Fotoluecke [LOGBUCH_SCHWABENTOR_KETTE 22.11. 17:00]
- 22.11. · Teil 1 ueber Gebaeudekanten binden (Wandebene + Ecke + Boden, Merging the Unmatchable) → ⚠ offen · Wandebene und EIN scharfes Wandende (y 21,3 gegen LoD2-Ecke 20,95) messbar, zweites Wandende geht in Nachbarfassade ueber, Wolke endet bei 27 m (Traufe 37,9) → kein Massstab [LOGBUCH 22.11. 17:00]

- 22.11. · GPS-Anker mit Kasten 3 x Bootstrap (nur Zufallsfehler) → ⚠ Falle · Nah-GPS einer Sitzung ist systematisch verzerrt (1122: +9,4 Grad / x0,867); ehrliches Band je Sitzung x Ring, Fernfotos mit langem Hebel zaehlen [LOGBUCH_SCHWABENTOR_KETTE 22.11.]
- 22.11. · Tor und Ausrichtung mit verschiedenen GPS-Mengen/Lot-Formeln → ⚠ Falle · eine gemeinsame Funktion (gps_unsicherheit.gps_fit, lot_aus_bild_achsen); Lage-Pruefstand offen [LOGBUCH 22.11.]
- 22.11. · Grundriss-Tor A klaert Strassenhaufen selbst (`tools/haufen_klaeren.py`, Merkmal "Wandblatt": Band z 1,5-9 m lueckenlos >= 3 m, geeicht an eigenen Waenden) → ✓ · 1120/1122k geklaert (0,5/1,5 m), falsche Lagen rot (5,5-18,5 m); Grenze L_eich/3 ✗ (haette +8 Grad x1,089 durchgewunken); kleine Drehungen <= 5 Grad sieht A nicht [LOGBUCH_SCHWABENTOR_KETTE 22.11. 17:30]
- 22.11. · Seiten-Teil ohne belegte Lage per GPS ansetzen → ✗ 3-4 m Versatz, Doppelwand · Teil weglassen + Fotoluecke (seiten_lage_beleg.py); Bindung ueber Querspuren ✗ (Gegenseiten-Verwechslung 167 Grad) [LOGBUCH 22.11.]

## Offen
- Seiten aus globalen Stuecken vereinen: Bruecke ueber Bilder, die beide Seiten sehen (Torbogen), statt Klappung (Stand 20.11.) [LOGBUCH 08:31]
- Lage-Tor ohne GPS fuer Objekte mit unbrauchbaren Geotags; GPS-Schwelle relativ statt fest 15 % (Ideen 10/20, Stand 19.11., ungeprueft)
- Ausrichtung: Objekt selbst (Turmachse) als Bedingung laengs der Strasse; Gleichstand als "mehrdeutig" melden (Ideen 58/11, Stand 19.11., ungeprueft)
- Seitentest "Blickrichtung je Bildgruppe" als Tor; Gegenseiten-Fotos als Zusatzreferenz der Vorpruefung (Ideen 37/31/28, Stand 19.11., ungeprueft)
- Videobilder nur aus Trefferabschnitten, Fremdbilder vor dem Mapper streichen, Paarliste nach Bildart (Punkte 47/33/50, Stand 19.11., ungeprueft)
- Seiten (Nord/Süd) symmetrischer Tore automatisch vereinen (Stand 20.11.)
- Massstab eines Seitenteils, das nur eine Wand sieht: gemeinsame Gesims-/Quaderlagenhoehen mit dem Hauptteil (Kantenstufe, foto_mass) statt Wolkenoberkante/Kamerahoehe; Wandende-Probe in `seiten_lod2_je_teil.teil_legen` (Stand 22.11., ungeprueft)

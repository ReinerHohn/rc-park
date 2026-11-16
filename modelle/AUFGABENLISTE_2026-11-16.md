# Aufgabenliste nach der Bestandsaufnahme 16.11.2026 (Nutzer: "merk die Liste und bearbeite sie ab")
Reihenfolge nach Nutzen. Status hier pflegen (offen / in Arbeit / erledigt + Commit + Messwert vorher/nachher).

1. HARDWARE
   1a. fassade_ortho.py - ERLEDIGT, aber anders als gedacht: GPU-Sichtbarkeit gebaut und gemessen = LANGSAMER (61 s gegen 41 s, ober_tvdr 700 Kameras) und weniger streng -> nur als Option --gpu-sicht.
       Der echte Engpass war das Laden aller Fotos: Vorpruefung 'sieht das Foto ueberhaupt eine Fassade' vor dem Laden: 59,6 -> 40,6 s (-32 %), gleiche Ergebnisse. Meine Aussage 'groesster Hebel' war falsch.
   1e. fassade_ortho Kamera-Vorauswahl je Fassade (--max-fotos 40, Standard) - ERLEDIGT: Turm 4 Waende 111 s. Die > 2 h kamen NICHT von der Kamerazahl, sondern von Kameras mit absurdem Standort (NICHTS_GEBRACHT.md); Plausibilitaet jetzt in kamera_verfeinern, fassade_ortho, schnelltest
   1b. Generator: Zwischenspeicher je Bauteilgruppe (nicht alles neu bei kleiner Aenderung) - offen
   1c. Abnahme - ERLEDIGT (Teil): Profil zeigte pruefstand.z_am_punkt = 133 von 158 s (je z-Stufe ein Schnitt durch 3 Mio. Dreiecke). Jetzt senkrechte Strahlen: Turm 153 -> 35 s, Werte identisch
       an schwab_v3, schwab_nachbar, ober_tvdr (alter Weg: PRUEFSTAND_SCHNITT=1). Pflichtbilder neben_fotos 3 gleichzeitig (ungemessen). Rest (fotodiag/seiten_audit parallel zum Pruefstand) offen.
   1d. Bildvergleich (zusatzfotos_lightglue paare): Stapel + Vorauswahl ueber Bildaehnlichkeit - offen
2. UMRISS-TOR - ERSTE FASSUNG ERLEDIGT: tools/umriss_tor.py (Dachlinie Modell gegen Himmelskante, Abweichung in Metern, Befunde mit 3D-Ort, Bild audit/umriss_<foto>.jpg), laeuft in bauen_abnehmen.sh als Hinweis.
   Turm Nordfoto 113029: Median 8 cm (Dachknick bestaetigt). GRENZEN: nur Kante gegen Himmel - Boegen/Galerie/Fenster vor der Wand sieht es nicht; Fotos ohne Himmel hinter dem Bau fallen aus. OFFEN: >30 Auto-Beobachtungen abarbeiten; Tor fuer Formen VOR der Wand (Kantenvergleich).
3. FENSTER-REGELMAESSIGKEIT - ERSTE FASSUNG ERLEDIGT: fenster_aus_parsing.raster_regel (Achsen/Geschosse angleichen, leere Rasterplaetze ergaenzen, markiert 'ergaenzt'); ober_tvdr rote Fassade: 3 x 2 Fenster, eines ergaenzt.
   Dazu Uneinigkeits-Tor (Mosaik-Fassaden) und Loch-Rueckkopplung im Fassadenbild behoben; Stimmenschwelle 50 %. OFFEN: nur an EINER Fassade geprueft; Fensterkaesten enthalten die Steinrahmen (zu breit).
4. MapAnything (Apache-Gewichte) als Test fuer Tiefe von Vorbauten/Daechern; VRAM pruefen - offen
5. SCHNELLTEST - ERLEDIGT: tools/schnelltest.sh (29 s; Syntax, Bauteile wasserdicht, Bogenform, Raster-Regel, Fenster/Mosaik/Fassadenbild an ober_tvdr, Pruefstand, Kamerabestand). Nach JEDER Werkzeugaenderung laufen lassen.
6. PLATZ (Nutzerentscheidung): groessere Datenplatte oder alte Zwischenstaende loeschen - offen, beim Nutzer
Weitere blinde Flecken (ohne Reihenfolge): Tor "ist das Quaderwerk?"; Kamerastandort-Plausibilitaet; Einzelfoto ohne Gegenfoto; fassade_tiefe nur 1 von 3 Seiten; Daecher aus Fotos;
freie Formen; Schwellen nur an einem Bauwerk; gesamtkette.py als EIN Befehl von null; LIMAP (Lizenz pruefen) fuer 3D-Kanten; Kamera gegen Modell-Renderings (MeshLoc-Prinzip) fuer Seiten ohne Referenzfoto.
Quellen der Recherche: MeshLoc arXiv 2207.10762, MapAnything arXiv 2509.13414, LIMAP arXiv 2303.17504, Mueller 2007 / Nishida 2018 (Fassaden-Grammatik).

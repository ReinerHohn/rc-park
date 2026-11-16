# Aufgabenliste nach der Bestandsaufnahme 16.11.2026 (Nutzer: "merk die Liste und bearbeite sie ab")
Reihenfolge nach Nutzen. Status hier pflegen (offen / in Arbeit / erledigt + Commit + Messwert vorher/nachher).

1. HARDWARE
   1a. fassade_ortho.py: Sichtbarkeit auf die GPU (render_kern statt CPU-Strahlen) - offen
   1b. Generator: Zwischenspeicher je Bauteilgruppe (nicht alles neu bei kleiner Aenderung) - offen
   1c. bauen_abnehmen.sh: unabhaengige Pruefschritte parallel - offen
   1d. Bildvergleich (zusatzfotos_lightglue paare): Stapel + Vorauswahl ueber Bildaehnlichkeit - offen
2. UMRISS-TOR Modell gegen Foto als Pflicht (Formfehler wie Bogen, Dachknick, Umgang automatisch melden); >30 offene Auto-Beobachtungen abarbeiten - offen
3. FENSTER-REGELMAESSIGKEIT je Fassade (Achsen/Geschosse; verdeckte ergaenzen, Fehltreffer aussieben) - offen
4. MapAnything (Apache-Gewichte) als Test fuer Tiefe von Vorbauten/Daechern; VRAM pruefen - offen
5. SCHNELLTEST fuer Werkzeugaenderungen (fester Satz, < 2 min) - offen
6. PLATZ (Nutzerentscheidung): groessere Datenplatte oder alte Zwischenstaende loeschen - offen, beim Nutzer
Weitere blinde Flecken (ohne Reihenfolge): Tor "ist das Quaderwerk?"; Kamerastandort-Plausibilitaet; Einzelfoto ohne Gegenfoto; fassade_tiefe nur 1 von 3 Seiten; Daecher aus Fotos;
freie Formen; Schwellen nur an einem Bauwerk; gesamtkette.py als EIN Befehl von null; LIMAP (Lizenz pruefen) fuer 3D-Kanten; Kamera gegen Modell-Renderings (MeshLoc-Prinzip) fuer Seiten ohne Referenzfoto.
Quellen der Recherche: MeshLoc arXiv 2207.10762, MapAnything arXiv 2509.13414, LIMAP arXiv 2303.17504, Mueller 2007 / Nishida 2018 (Fassaden-Grammatik).

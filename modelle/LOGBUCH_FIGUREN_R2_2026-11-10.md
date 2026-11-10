# Logbuch Figuren (stl_teil:figuren -> figurenreihe:figuren), Kreis r2, 2026-11-10

Befund (konvergenz_bericht): Wolkenbeleg 0,43, Median 0,17 m. Ursache jetzt geklaert: Altteil = Quader-Huellen aus dem alten Hand-Generator
(T3d-Ausrichtung nur Lage/Massstab), Scheitel 0,3-0,7 m zu tief, 0,2-0,3 m neben der echten Figur, Konsole kein Rotationskoerper.

## Formbeschreibung (Stufe 0)
Fotos (alle ANGESEHEN, Gitter-Ausschnitte in `/media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis2/figuren_r2/c_*.jpg`):
- 6120 (frontal, Nahfoto, 11,4 m, von unten 38 Grad), 6119 (gleiche Richtung, 4 m weiter rechts), 6117 (schraeg 47 Grad), 6127 (Seitenansicht 72 Grad),
  6132 (frontal, 13,5 m), 6161 (frontal, Uebersicht 26 m, alle 4), 6145 / 6164 (Uebersicht schraeg, alle 4).
- Lage-Pruefung L18: Modellpunkte der 4 Figuren in jedes K-Foto projiziert (proj.py), Figuren 1-3 in 6120, alle 4 in 6161/6145/6164 im Bild; die roten Altkanten
  lagen neben den echten Figuren (`p6120_s.jpg`).
Zonen von unten nach oben (je Figur, an 4 Figuren gleich):
1. **Pendelkonsole** (Kragstein): rotationssymmetrische Glocke/Stufenpyramide, Knauf (d 0,10) -> 2. Stufe (d 0,31) -> Kranz (d 0,58, Goldkante) -> Oberseite (Standflaeche). Sitzt 0,2 m vor der Wand, Kranz beruehrt die Wand.
2. **Figur** (Ritter/Koenig in Rüstung, schlank, 2,1 m): Fuesse/Schuhe (Sohle 11,29) -> Unterschenkel (b 0,43, d ~0,23) -> Schurz/Oberschenkel (b 0,47) -> Brustpanzer (b ~0,5, mit Armen bis 0,9, tiefer ~0,35) -> Schulter -> Kopf (b 0,30) mit Krone (Fig. 1-3) bzw. Hut mit Krone (Fig. 4, Brim breiter).
   Unterschiedliche Posen (Schwert, Reichsapfel mit Kreuz, Szepter), Arme/Waffen nicht modelliert (H0).
3. **Baldachin** (Wimperg/Fialen, golden-rot) ueber jedem Kopf: Z-6161-001 zeigt ihn deutlich; NICHT Teil dieser Runde (siehe offene Punkte).
Grundriss/Querschnitt: Figur ellipsenfoermig (breit entlang der Wand), freistehend 0,07-0,1 m vor der Wand; Konsole rund. Wiederholung: 4 Figuren, Periode in u 3,94-3,99 m (jeweils zwischen zwei Fenstergruppen).
Anschluesse: Konsolenkranz in die Wand (Frontebene 12,666), Figur steht mit 2 cm Ueberlappung auf der Konsolenoberseite.
Am alten Modell anders: siehe Befund oben.

Formfamilie: neu **`figurenreihe`** in `tools/baukasten_gen.py` (generisch: Rotationskonsole + Ellipsen-Koerperprofil, Lage je Figur, Scheitel je Figur; keine Festwerte im Code).
Begruendung: vorhanden waren nur `konsolenreihe` (Quader-Huellen mit Wandbindung, keine Rotation), `zylinder_bt` (ein Kegelstumpf), `figuren_netz` (TripoSR, in diesem Objekt nicht verwendet).
Fragen/ANNAHMEN: (a) Rueckseite nicht sichtbar -> Figurtiefe aus Seitenansicht 6127 + Blickwinkelformel (Fehler +-0,06 m); (b) Brustbreite 0,62 = ANNAHME zwischen Rumpf und Armhuelle; (c) Figur 4 Konsole nicht triangulierbar (6127/6132 schneiden sie ab) -> ANNAHME gleiche Konsolen-z wie Figuren 1-3; (d) gemeinsames s=12,89 gemittelt (Einzelwerte 12,78-12,97 = Messrauschen der Kronen-/Pendelachse, die Figuren neigen sich nicht erkennbar).

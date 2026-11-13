# Fotoauftrag Erker-Rippen (Kurzfassung, 13.11.2026)
Warum: Alle vorhandenen Fotos entstehen aus 28-31 m (~100 px/m); eine Rippe (0,07 m) hat ~7 px, Einzellinien sind nicht aufgeloest. Mit Nahfotos (1-3 m, >= 400 px/m) werden Rippenzahl, Breite, Kreuzungen und Fuss messbar. Vollversion: AUFNAHMEPLAN_ERKER_RIPPEN.md.

Fuer JEDEN der beiden Erker (links und rechts an der Fassade):
1. [ ] 6 Fotos von unten, steil nach oben (Blick ~60 Grad), im Halbkreis um den Erker, Abstand 2-4 m (Laube/Gehweg direkt darunter). Jedes Foto muss den ganzen Fuss (Pfeilerkopf) UND die Knaeufe am Erkerrand zeigen.
2. [ ] 3 Fotos je Erkerseite (Front, links schraeg, rechts schraeg) aus 1,5-3 m Abstand, Handy moeglichst hoch gehalten, Rippenfaecher fuellt das Bild.
3. [ ] 2 Detailfotos je Erker: Pfeilerkopf mit Rippenfuss (1 m), ein Knauf am Rand mit Rippenansatz (1 m); Lineal/Zollstock (1 m) senkrecht im Bild, zwei Fotos damit.
Technik: gleiche Belichtung, kein Zoomwechsel, HDR aus, Gold nicht ueberbelichten, Fotos nicht beschneiden, Dateizeit behalten. Reihenfolge ist egal.
Danach (automatisch): Kamera-Kalibrierung -> Zwei-Foto-Triangulation der Rippenpunkte (tools/foto_mass.py --tri / kante_3d.py mit Via-Punkten in BEIDEN Fotos) -> Rippen ins Modell (features_in_objekt.py) -> Abnahme + schattierter Vergleich.

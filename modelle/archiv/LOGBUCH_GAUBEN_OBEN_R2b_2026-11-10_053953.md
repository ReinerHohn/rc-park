# Logbuch gaubenreihe:oben (Kreis 20261110_053953 r2, 10.11.2026)

Vorversuch r1 (verworfen): Rueckkante auf z 22,747 gesetzt -> Absatz ~0,4 m ueber dem Satteldach + offener Keil ("Sprungschanze"), Pruefung = Selbstbezug.

## Formbeschreibung (Stufe 0)
Fotos angesehen: Overlay `rundekreis2_gaubenreihe_oben_neu_nah.jpg` (6259 Nah, c12 frontal, 6162 schraeg, j05 unscharf), M-6259-009.
Schleppgaube: Fensterbank, Fensterkasten 1,02 m mit Rundbogenfenster, ziegelgedecktes Vordach 1,45 m breit, rote Dreieckswangen, 2 Gauben (Z-018-006). Das Vordach ist eine durchgehende Ziegelflaeche, die sich buendig in den Hang schiebt (kein Absatz). In c12 reicht die helle Ziegelflaeche ~0,4 m hoeher/weiter hinten als die Modellkante.
Formfamilie unveraendert: `gaubenreihe` form schlepp (vorhanden).
Beleg: M-6259-009 heisst "Vordach hinten rechts (Anschluss Hang)" -> der Punkt liegt AUF dem Hang; das Satteldach-Modell ist dort lokal ~0,4 m zu tief (Verdacht, nur 1 Punkt).

## Aenderung
`tools/baukasten_gen.py` gaubenreihe: optionaler Parameter `dach_hinten_z`. Vordach-Oberflaeche = Ebene durch Vorderkante und gemessene Hinterecke, fortgesetzt bis zum Schnitt mit dem Satteldach-Hang (n ~6,3, z ~23,1). Kein Absatz, kein Keil (Hohlraum durch Huelle bis in den Hang). Generisch, ohne Objektnamen. `objekt.json`: dach_hinten_z 22,747 mit Quelle/Historie.

## Pruefung
`gaube_b_dach_z7` (Ebenen-Konsistenz bei n 7,0, Soll rel. 20,97-21,35 = +-0,2 m Messunsicherheit): Altstand 20,93 ROT. Ehrlich: kein unabhaengiger Beleg (gleiche Messung); unabhaengig ist nur der Wolkenbeleg (Gate) und der Sichtvergleich.

## Offen
Gaube A ANNAHME gleich B; nur 1 Messpunkt; Satteldach lokal evtl. zu tief; Stirn c12 ~0,1 m zu breit; Fensterbank 0,1-0,2 m zu hoch; A/B 0,14 m; Rundbogenfenster/Konsolen/Fensterbankprofil nicht modelliert.

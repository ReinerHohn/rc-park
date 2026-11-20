# Logbuch Kreis-Ost r1 (staffelgiebel:ost), 2026-11-10

## Formbeschreibung (Stufe 0)
Fotos angesehen: ip_IMG_6115 (Nah, von Ost-Hof schraeg), ip_IMG_6261 (Uebersicht, Sonne), ip_IMG_6164 (Nah, von Suedost), ip_IMG_6259 (nur Overlay erzeugt, nicht einzeln beurteilt).
- Zonen: unten Rumpf/Dach (nicht Teil), darueber die Giebelwand (roter Putz) mit zwei schmalen Fenstern in Faschen (Reihe an der Wand, n ~4,4), oben beidseitig gestufte Treppe, je Stufe ein Pfeilerblock mit grauem Ziegelkaeppchen.
- Grundriss/Querschnitt: dünne Scheibe (Wand ~0,6 m), nicht rechtwinklig zur Hauptfassade (siehe Messung), Vorderflanke 8 Stufen sichtbar (Z-6261-002, Z-6164-004 aus Vorrunden; hier im Overlay 6115/6261/6164 nachgesehen: 8), Rueckflanke gestuft (Spiegel, ANNAHME).
- Wiederholungen: Stufen (Teilung 1,0 m n, Sprung 1,34 m z), Fenster (2 sichtbar je Wand).
- Anschluss: Giebelwand steht auf dem Rumpf, Dach (satteldach:haupt) laeuft von hinten an die Wand, Erkerhelm davor.
- Am Modell anders (Overlay Altstand rot->cyan): Scheibe war parallel zur Fassadenachse bei u 15,85; im Foto liegt die Wand bei kleinem n (Apex) ~0,4 m weiter aussen als bei grossem n; die Stufenkonturen sassen links/oben um ~50 px (0,3-0,5 m) daneben.
Formfamilie: bestehende `staffelgiebel` (baukasten_gen.py); nur ein optionaler generischer Parameter `u_neigung`/`n_ref` (Scherung u = u_aussen + u_neigung*(n-n_ref)) neu. Altverhalten (u_neigung 0) bitgleich, `regression.py --pruefen` identisch.

## Befund
Kein Formfehler der Stufen, sondern Lage der WANDEBENE: Kappenfirst-Linie der Stufenspitzen (M-6115-001..008) faellt um 0,0609 m je m n (Streuung 0,032 m); Wolke-Wandebene faellt ebenfalls (-0,083). Die Scheibe stand parallel (Neigung 0). Zusaetzlich wurde im Vorrundenstand 'Aussenebene = Kappenfirst' gesetzt: die Kappe sitzt aber mittig auf der Mauerkrone (ANNAHME), Aussenflaeche = Kappenfirst + dicke/2 (0,315).
Unabhaengige Gegenprobe der Aussenebene: Wolke u(n 7,5) 16,06; Fensterfaschen-Ecken M-6115-009/010 (3-Foto-Triangulation, ±0,23 m): u 16,23/16,41 bei n 4,85/4,01, Modell 16,24-16,29.

## Messung / Sweep (Kreis-Messung, Beleg, Kanten-R, Kanten-P)
| u_aussen | u_neigung | Beleg | R | P |
|---|---|---|---|---|
| 15,85 | 0 (Ausgang) | 0,224 | 0,336 | 0,025 |
| 15,85 | -0,04/-0,06/-0,08/-0,10 | 0,159/0,137/0,124/0,162 | 0,324-0,393 | 0,025-0,028 |
| 15,95 | 0 / -0,06 | 0,288 / 0,318 | 0,332 / 0,372 | 0,021 / 0,017 |
| 16,05 | 0 | 0,292 | 0,313 | 0,018 |
| **16,05** | **-0,06** | **0,381 (final 0,376)** | **0,416 (0,419)** | 0,023 |
| 16,15 | 0 / -0,06 | 0,231 / 0,349 | 0,35 / 0,393 | 0,029 / 0,036 |
Beleg-Gewinn kommt aus Verschiebung UND Neigung (k=0 bei 16,05 nur 0,292): kein reines Nach-aussen-Schieben (L-KR4). Gewaehlt wurde NICHT das Beleg-Maximum, sondern der Wert aus Kappenfirst + dicke/2, der in der Scan-Reihe im Plateau liegt (L-KR12: Plateau 15,95-16,15, Rauschen ±0,01).
Gate: Guete (Mittel Beleg, F1) 0,135 -> 0,210 = +0,075 (Schwelle 0,05); Beleg +0,152, F1 0,047 -> 0,044 (-0,003, Grenze -0,02).

## Pruefungen (masstabelle.json), am Altstand ROT gegengeprueft
- Aussenebene u (n 3,45): Soll 16,15-16,50 (neue Quelle), Altstand 15,851 rot, neu 16,312 ok.
- Aussenebene u (n 10,5): Soll 15,72-16,07, Altstand 15,85 (ok, gruen - Gegenstueck), neu 15,888 ok.
- Wandneigung u(3,45)-u(10,5): Soll 0,28-0,58, Altstand 0,001 rot, neu 0,424 ok.
- Messorte giebel_o_top_b2/b4/b8, giebel_o_rueck/vorn folgen der Scheibenmitte (gleiche n, gleiche Soll-Hoehe); am Altstand wuerden sie danebenliegen (Rueckflanke/Vorderflanke 0,627 rot, aus Messortgruenden).
- Der alte Aussenebene-Sollwert (15,55-15,95) wurde geaendert, MIT neuer Quelle und historie (Regel 1).
Ergebnis bauen_abnehmen: "alle Pruefungen bestanden | 1 Widerspruch offen" (Gesamthoehe, vorbestehend). freiraum_audit-Fehler vorbestehend. Einmal fiel test_regeln_cb T6 (Martinstor-Werkzeugtest) mit Exit 1 durch, wiederholt Exit 0 - Infrastruktur (GPU 4,9 GB von Parallelspuren belegt), nicht gegenstandsbedingt (L-KR1).

## Offen / ungeprueft
- Kappe mittig (ANNAHME) - Querschnittsfoto (Blick entlang der Wand) fehlt.
- Praezision 0,023: Kantengitter hat an den Stufenecken keine Segmente (nur die Huellkurve 0,3-0,6 m unter den Spitzen, Dach/Wand-Linie); P laesst sich ohne Gitterverbesserung nicht heben.
- Hinterflanke Spiegel, Daechlein, Fenster in der Wand nicht modelliert.
- Fensterfaschen-Triangulation M-6115-011/012 (Fenster 3): FALSCHE ZUORDNUNG (Strahlabstand 0,9-1,2 m), verworfen, nicht verwenden.
- Westgiebel hat vermutlich dieselbe Wandneigung (ungeprueft).

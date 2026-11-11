# Kreis1 – bogenreihe:laube Stirnboegen (11.11., 152551)

## 1 Formbeschreibung (Stufe 0)
Fotos: 6225 (Nah, Westende, Standort -7,9/18,4/3,6), 6117 (Ostende, Randkurve links der Endsaeule), 6130/6124 (Frontbogen, gleiche Familie).
- Zone Laubenende: Stirnwand mit goldgesaeumtem Segmentbogen (Innenkante, darum Aussenring/Goldrand), dahinter das Kreuzgewoelbe. Oben bis z~8 (Bogenband).
- Grundriss: Oeffnung zwischen Laubenrueckwand (s 7,28) und Endsaeule (s~11,87). Wiederholung: je ein Bogen West/Ost.
- Aktuelles Modell war Rechteck bis z 7,9. Formfamilie: vorhandene Bogenreihe-Geometrie (segmentbogen) als neue Option stirnboegen in tools/baukasten_gen.py.
## 2 Zaehlungen
Keine neue (je ein Bogen am Foto 6225 sichtbar; Ost nur 6117 angedeutet) – kein Z-Protokoll.
## 3 Pruefungen (Quelle Foto 6225 Strahlschnitt, Stirnebene u -8,82, Ebenenfehler ~0,1 m)
| Pruefung | vorher | nachher | Soll |
|---|---|---|---|
| Bogenunterkante s 9,575 | 7,90 | 7,16 | 7,0..7,3 |
| s 8,6 | 7,90 | 6,94 | 6,73..7,03 |
| s 10,23 | 7,90 | 7,06 | 7,02..7,32 |
bauen_abnehmen (RCPARK_OHNE_FOTODIAG=1): alle Pruefungen bestanden. Foto-F1 halb, 10 Torfotos: 0,741 -> 0,756 (+0,015, Tor +0,02 NICHT erreicht); Foto 6225: 0,656 -> 0,731.
## 4 Overlays
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_stirnbogen_6225_vorher.jpg / _nachher.jpg
- /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_152551a152551/ff_nachher_bilder/bogenreihe__laube_<foto>.jpg
## 5 Fehlerliste
- Westbogen Innenkante 6225: trifft (am Bild geprueft).
- Aussenring West: trifft rechts, oben/links ~10-15 px (halbe Aufl.) zu tief; Breite/Tiefe ANNAHME von Front.
- Ostbogen: ungeprueft (gespiegelte ANNAHME, Ebene u 15,86).
- Wanddicke 0,5: ANNAHME. Kaempfer 5,28 von Front uebernommen; 6225 gibt 5,5-5,9 (Ebenenfehler) – offen. Asymmetrie bei s 11,21 (gemessen 6,77 vs Modell 6,46) ungeklaert, nicht gemittelt.
- Nur EIN kalibriertes Foto fuer die Messung (Regel >=3 nicht erfuellt).
## 6 Geaenderte Dateien
tools/baukasten_gen.py, modelle/kaufhaus_grob3/objekt.json, masstabelle.json, NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, audit/*, STL/Pruefbericht (Bauausgabe).
## 7 Generalisierte Lehre
Lehre | Anlass | Werkzeug: Endteile erst ueber Kameraprojektion den Fotos zuordnen, die sie zeigen | Torfotos sahen Stirn nicht | foto_mass.strahl_ebene.

# Kreis-Bericht 040618 r1 – satteldach:haupt (Ziegelreihen)

## 1 Formbeschreibung (Stufe 0)
Fotos 6162 (Nahausschnitt Dach), 6132, 6145, j05 (verschiedene Richtungen/Abstaende). Hauptdach: dunkle Biberschwanz-Reihen mit Moos, Dachgitter (Pfosten + Stäbe) über der grünen Rinne, Gauben, Erkerhelme mit bunten Schuppen. Formfamilie: vorhandene satteldach-Ziegelleisten (Relief quer zum Hang); neue optionale Parameter ziegel_fase, ziegel_rand. Dachgitter = noch keine Familie (offen).
## 2 Zaehlungen/Messungen
Reihenabstand: tools/foto_dachreihen.py -> messprotokoll/ZR-dachreihen.json (Hang entzerrt, Autokorrelation): 0,18 m in 6162/6132/6145/j05 (Peaks 0,18/0,36/0,54/0,72). Keine Anzahl-Zaehlung (Reihen werden per Periode gemessen, keine Z-Datei).
## 3 Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| ziegel_reihenabstand_haupt | 0,35 (ROT) | 0,18 | 0,16-0,20 | Foto-Entzerrung 4 Fotos |
| Gesamt | – | alle bestanden (bau4.log) | – | |
Tor (voll, 10 Torfotos): f1_fein 0,663 -> 0,683 (+0,020; Soll >= +0,010), f1 0,805 -> 0,804, f1_h 0,774 -> 0,773. Halbe Aufloesung: f1_fein 0,539 -> 0,575 (ohne Rand/Huellregel).
Zusatz: ziegel_tiefe 0,07 -> 0,04 (ANNAHME, Vorderhang-z-Pruefung und Druckreparatur), ziegel_rand 0,05 (ANNAHME), ziegel_fase 0 (Fase brachte keinen Gewinn). regression.py --pruefen: identisch.
## 4 Overlays
Keine rundekreis-Overlays erzeugt. Fotoform-Bilder: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261112_040618a040618/ff_voll_bilder/ (nach), /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261112_040618a040618/ff_voll_alt_bilder/ (vorher); Sichtblatt modelle/kaufhaus_grob3/audit/seiten.jpg angesehen (Dach feine gleichmaessige Reihen).
## 5 Fehlerliste
- Dachflaeche Reihenabstand: trifft (4 Fotos). Phase der Reihen (Lage der Kanten): ungeprueft, ANNAHME Start 0,5*Abstand.
- Ziegeltiefe/-anteil: ANNAHME, ungeprueft.
- Dachgitter, Rinne: nicht modelliert. Speier-Kopf (Drachenkopf), Erker-Eckdrachen, Pruefer-Rest 6132/j05: nicht bearbeitet, offen.
- foto_diff, teile_lage_pruefen, teile_sichtpruefung: nicht gelaufen (ungeprueft); fehlteile_finden lief in bauen_abnehmen.
## 6 Geaenderte Dateien
tools/baukasten_gen.py, tools/pruefstand.py, tools/foto_dachreihen.py (neu), modelle/kaufhaus_grob3/objekt.json, masstabelle.json, messprotokoll/ZR-dachreihen.json, NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, erzeugte Audit-Dateien des Baus.
## 7 Generalisierte Lehre
Periodische Deckung messen statt annehmen | ANNAHME 0,35 war doppelt | foto_dachreihen.py. Reliefteile nie ueber Huelle/Dachenden (Druckbett, Reparatur) | Extra-Schnitt, Ueberhang 1,1 % | ziegel_rand + Huellregel.

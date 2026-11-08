# SPEC S9 - Erkennen + Einpassen mit freien Parametern + Restpruefung (Nutzer 6.11. 07:05)

Nutzer: Objekterkennung (Bogen, Erker, Fenster, Dachgaube) mit OWLv2, Formen mit freien Parametern iterativ an die Daten matchen; wenn es nicht passt, andere Form/Parameter; Medianfilter.
Begruendung: kosten_lr-Holdout 6.11. 04:00 - Generator C beste Kantenlage, Wolken-Koerper schlechter; C-Fehler = erfundene Formen. S9 = Generator-Saubkeit + harte Gegenpruefung an der Messung.
Objekt: NUR kaufhaus_null5 (Nutzerprioritaet). Generischer Code, keine Objektnamen/Festwerte.

## Ablauf je Elementklasse (Reihenfolge: Arkadenboegen f02 -> Fenster -> Gauben -> Erker)
1. Wolke vorfiltern: Median/statistischer Ausreisserfilter (Open3D), Parameter in objekt.json.
2. Erkennen: tools/fassade_parsing.py (OWLv2, Gegenbegriffe, Kacheln) auf den kalibrierten Fotos bzw. Fassaden-Ortho -> Kandidatenbox je Element, ueber Fotos abgestimmt. Ortho: aus der WOLKE erzeugen (nicht aus dem Generator-STL).
3. Daten je Kandidat sammeln: 3D-Kanten (tools/kanten_3d.py, /media/oem/scan/rc-park_null/kanten_vektor/kh_alle/kanten_3d.json) + Canny-Kantenpixel aus >= 3 Fotos rueckprojiziert + Wolkenpunkte im Kandidatenvolumen; Leere (Durchblick) aus Carving material.npz (carv_kh3).
4. Einpassen: Formfamilien mit freien Parametern, z.B. Bogen: Rund-, Stich-, Spitzbogen (Breite, Kaempferhoehe, Stich/Radius, Tiefe der Laibung, Lage); Fenster: Rechteck/Bogen-Fenster (Breite, Hoehe, Laibungstiefe); Gaube: Satteldach-/Schleppgaube (Breite, Hoehe, Neigung, Ueberstand). Robuste Kleinste Quadrate (Huber) gegen Kanten + Punkte, Mehrfachstart; jede Familie probieren, Modellwahl per Rest + Strafterm Parameterzahl (BIC).
5. Gegenpruefen: Annahme nur, wenn Rest (Median Kantenabstand) < 0,10 m UND Durchblick/Material konsistent mit Carving; sonst Element NICHT ersetzen (Messung bleibt), Grund im Elementbuch.
6. Einbauen: Carving-Koerper (carv_kh3) per manifold3d: Oeffnungen abziehen, Volumenteile (Erker/Gauben) vereinigen, Flaechen um das Element auf die gefittete Ebene setzen.
7. Iteration: foto_diff/kosten_lr auf den 6 Holdout-Fotos (001,024,054,083,211,234; tools/test_wolke_solid.py fotodiff, Maske /media/oem/scan/rc-park_null/beweis_ansatz/kaufhaus_null5/lr/maske); Element behalten nur, wenn kosten_lr nicht schlechter wird.

## Beweis (Pflicht, selbst ansehen)
- Synthetisch: Boegen verschiedener Familien/Radien + ein Element, das KEINER Familie entspricht (z.B. Kleeblattbogen) -> richtige Familie/Masse < 5 cm; Fremdform wird abgelehnt (Messung bleibt).
- Kaufhaus: Pruefstand kaufhaus_null5 (Arkade 4 robust, 1 Koerper, wasserdicht, Mindestwand, First); kosten_lr-Tabelle Generator C / Carving / S9 auf den Holdout-Fotos; Frontbild neben Foto 004.
- Kein Generator-STL als Geometrie (nur als Vergleichsgegner).

## Betrieb
Lange Laeufe tools/job_start.sh; RAM 15 GB, nur ein grosser Lauf; ein GPU-Job; Platztor; Ausgabe /media/oem/scan/rc-park_null/s9/; keine Commits; Register-Eintrag, versuche.jsonl, Abschnitt STAND_2026-11-06.md.

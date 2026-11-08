# SPEC S8 - Scharfes Modell aus gemessenen Ebenen und Kanten (Nutzerauftrag 5.11. 23:40)

Nutzer: "Martinstor war schon extrem gut" (Generator: exakte Ebenen/Kanten) + "keine fertigen Formen, Kanten perfekt erkennen und so das 3D-Modell nachbilden" + "Punktwolke einzige Basis, LoD2 nur ohne Widerspruch".
Ziel: Martinstor-Schaerfe, aber jede Flaeche und Kante gemessen. Objekt zuerst NUR kaufhaus_null5 (Nutzerprioritaet), generischer Code (keine Objektnamen/Festwerte).

## Bausteine
1. **Topologie** = Carving-Belegung (tools/wolke_carving.py, material.npz / Cache; Werkzeug NICHT aendern, nur lesen).
2. **Ebenen** aus der dichten Wolke: RANSAC/Region-Growing (Open3D oder eigenes), Mindestflaeche Parameter, Ebenen auch fuer Laibungen, Hallenwaende, Decke, Balkonfront, Dachflaechen. LoD2-Ebenen nur fuer unbeobachtete Bereiche nach Widerspruchsregel.
3. **3D-Kanten** aus den kalibrierten Fotos: Liniensegmente je Foto (LSD/OpenCV oder DeepLSD), Zuordnung ueber Epipolargeometrie mit bekannten Kameras (kameras_unverzerrt.json), Triangulation, nur Linien aus >= 3 Fotos. Stand der Technik: LIMAP (pruefen: Lizenz, Installierbarkeit in venv-seg, GPU). Eigenbau nur, wenn LIMAP nicht geht; Begruendung ins Versuchsregister.
4. **Zusammenbau** (PolyFit-/Kinetic-Prinzip, keine Vorlagen): Ebenen schneiden -> Zellzerlegung (Ebenenanordnung, begrenzt auf Objektbox); jede Zelle innen/aussen per Mehrheit der Carving-Belegung; Flaechenstuecke, die an 3D-Kanten grenzen, bevorzugt (Kanten als Zwangslinien). Ergebnis: polygonales, wasserdichtes Netz mit scharfen Kanten.
5. Kleine Teile ohne Ebenen (Statuen, Fialen): Carving-/OpenMVS-Form als Restfeld behalten, Herkunft vermerkt.

## Lizenz
Fuer verkaufte Modelle zaehlt die Ausgabe; GPL/AGPL-Werkzeuge, die nur lokal laufen, sind ok (wie OpenMVS), NC-Lizenzen (nur Forschung) nur zum Testen. Jede neue Bibliothek in modelle/LIZENZ_WERKZEUGE.md.

## Beweis (vor Bericht, selbst ansehen)
- Synthetisch: Kasten mit 4 Rundbogen-Arkaden, Halle, Satteldach, Treppengiebel (gestufte Kontur) aus gerenderten Ansichten + Wolke mit Rauschen 3 cm -> Kantenabweichung < 5 cm, Stufen des Giebels vorhanden, kein Wissen ueber "Treppengiebel" im Code.
- Kaufhaus: Pruefstand kaufhaus_null5 (Arkade 4, 1 Koerper, wasserdicht, First, Mindestwand); foto_diff/kosten_lr auf den 6 Holdout-Fotos (001,024,054,083,211,234; Wolke ohne diese Fotos) besser als Carving carv_kh3; Front aus Foto-004-Richtung neben Foto 004 und Schraegansicht als JPG unter modelle/kaufhaus_null5/audit/kanten_vektor/.
- Unabhaengigkeit: kein Generator-STL gelesen (Test wie test_wolke_carving.py NEGATIV).

## Betrieb
Lange Laeufe ueber tools/job_start.sh; RAM 15 GB, nie parallel zu einem anderen grossen Lauf (rcpark-* pruefen); ein GPU-Job; Platztor nicht umgehen; Ausgabe /media/oem/scan/rc-park_null/kanten_vektor/; keine Commits. Bericht als Abschnitt in modelle/STAND_2026-11-06.md + Register-Eintrag + versuche.jsonl.

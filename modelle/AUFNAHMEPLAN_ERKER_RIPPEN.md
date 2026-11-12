# Aufnahmeplan Erker-Unterseite (Rippen) - 12.11.2026
Ziel: Tiefe der Bogenrippen unter den Erkern eindeutig messen (Mehrfoto-Triangulation, Gegenprobe). Befund: Mit den vorhandenen Fotos (Ref 6171, 33 Nachbarn, GPU-Tiefen-DP) bestehen 0 von 21 Ketten die Pruefung; 2D-Erkennung ist gut, die Tiefe nicht.
## Was fotografiert werden soll (je Erker, links/Mitte/rechts getrennt)
1. **Von unten, steil nach oben** (Kamera ca. 1,5 m unter dem Erkerboden, Blick ~60 Grad nach oben): 6 Positionen im Halbkreis, Abstand zur Rippenmitte 3-5 m. Schraegflaechen und Fussbuendel sehen sonst nur streifend.
2. **Von rechts und links** (45 Grad zur Fassade), Abstand 4-6 m, Hoehe Augenhoehe und Arm gestreckt nach oben: je 4 Fotos mit 60-70 % Ueberlappung.
3. **Nahaufnahmen 1-2 m** (Teleobjektiv/Zoom 2x, falls moeglich, sonst Abstand 2 m): Fussbuendel, Randleiste oben, Kreuzungsknoten; je 3 Fotos mit leicht verschobenem Standpunkt (Parallaxe 0,5 m).
4. **Gleiche Belichtung**, Handy fest (kein Zoomwechsel), HDR aus, Gold nicht ueberbelichten; Fotos NICHT beschneiden; Reihenfolge nummerieren oder Dateizeit behalten.
5. **Massstab**: ein Zollstock/Latte (1 m) senkrecht an einer Stuetze im Bild, zwei Fotos damit.
## Danach (automatisch)
SfM-Einbindung -> `tools/kanten_tiefe_sweep_flaeche.py` -> `kanten_ketten.py --schliessen 25` -> `pfad_tiefe_dp.py` (GPU) -> `pfad_gegenprobe.py` -> nur bestandene Pfade ueber `features_in_objekt.py` ins Modell -> Abnahme + Render neben Foto.

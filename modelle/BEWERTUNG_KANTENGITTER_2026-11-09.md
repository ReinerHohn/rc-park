# Bewertung Kantengitter Kaufhaus - Stand 9.11.2026 abends

Grundlage: `LAGEBILD_KANTENGITTER_2026-11-09.md` (51 Versuche destilliert), `RECHERCHE_KANTENGITTER_NEU_2026-11-09.md` (Verfahren 2023-2026), `RECHERCHE_DRAHTGITTER_VERFAHREN_2026-11-09.md` (klassische Verfahren), Logbuch Runden 1-4.

## 1. Wo wir stehen
Aktuelles Gitter: `kaufhaus_alle/segmente_aufbau8.json`, 2101 Segmente, 482 ueber 15 m, 1 Helm als Formfit (8 Grate + Fussring). Editor laedt es (Port 8767).

| Band | gegen Wolkenkanten (unabhaengig vom Sweep) Treffer / Abdeckung | gegen Sweep B (andere Referenzfotos) Treffer / Abdeckung |
|---|---|---|
| z < 12 m | 0,49 / 0,87 | 0,94 / 0,57 |
| 12-15 m | 0,62 / 0,76 | 0,89 / 0,61 |
| > 15 m | 0,02 / 0,14 (Wolke hat dort nur 1337 Punkte) | 0,48 / 0,74 |

Lesart: Unten deckt das Gitter 87 % der Wolkenkanten ab; nur die Haelfte der Gitterpunkte hat eine Wolkenkante, weil die Wolke viele echte Kanten (Fensterrahmen, Figuren) nicht aufloest - gegen Sweep B sind 94 % belegt. Oben (Dach) kann nur Sweep B messen: Abdeckung 0,52 -> 0,74 heute. Die einzige verfahrensfremde Bestaetigung bleibt der Overlay-Sichtbefund (`audit/gitter_aufbau8_6261.jpg`): Arkaden, Fenster, Erker, Balkon, First, beide Staffelgiebel mit Zacken, Traufe, grosser Helm sitzen; das Gebaeude ist als Kaufhaus erkennbar.

Heute gewonnen (Runde 4):
- Dachband-Parameter o2 (tol 10 cm, Voxel 5 cm, minpts 5, minlen 0,6 m): Abdeckung > 15 m 0,52 -> 0,72, Staffelgiebel-Zacken jetzt als Segmente. o3 (tol 20 cm) schlechter, o4 (k=3) 0,61/0,67. Wolken-Gegenprobe unten unveraendert (Lehre Runde 3 eingehalten).
- `--qe`-Bugfix in `gitter_aufbauen.py`: Ausgleich schnitt jedes Segment auf das 2-98-%-Quantil = 4 % kuerzer, Ecken verloren; jetzt 0,3 %.
- `tools/helm_fit.py`: Helm als n-eckige Pyramide (GPU-Rastersuche cx, cy, Spitze, Neigung; Rundheitstest gegen Giebel; Drehung aus Stabilitaetskarten). Grosser Helm: Spitze 22,4 m, Fuss 15,3 m, r 0,86 m, Inlier 40 %, Overlay passt auf 2 Fotos. Kleiner Helm: Fit zu breit/zu hoch (Dachschraege mischt in die Punkte, Inlier 28 %) - noch nicht aufgenommen.

## 2. Was nicht ging (nicht wiederholen, Details NICHTS_GEBRACHT.md)
Streuerfilter per Score, Kontrastfilter gegen Sweep B, Union A+B, Buendelung im Dach, lockere Triangulation, Phasenkongruenz/DexiNed als Einzelquelle, gleichgewichtete Fusion, Voxelhuellen/Schnitzen. Gemeinsames Muster: jeder Filter, der nur an EINER Referenz eingestellt wurde, entfernte echte Kanten.

## 3. Die fuenf Luecken
1. **Fragmente statt Zuege**: Zacken, Gauben, Konsolen sind viele kurze Stuecke; Buendel paralleler Streuer an Konsolen (Nahaufnahmen, Tiefenfehler). Kein Werkzeug verbindet Stuecke zu Ketten.
2. **Kurven**: 4 Boegen; Spitzboegen, Masswerk, Helmgrate nur als Polygon.
3. **Kleiner Helm, Gauben, rechte Giebelkante** unvollstaendig.
4. **Keine unabhaengige Wahrheit**: alle Zahlen stammen aus denselben Karten/Posen. Handwahrheit (20 gemessene Kanten im Foto) fehlt.
5. **Gitter -> Koerper** nicht begonnen (Ziel Druckteile).

## 4. Was die Recherche sagt (Kurz)
Unsere Kette (2D-Kantenkarte -> Tiefen-Sweep -> Primitive) ist exakt der zweistufige Weg von NEF/EMAP/EdgeGaussians. Die 2025er Arbeiten (SketchSplat MIT, CurveGaussian, 3D Curvix/Edge Sketch) begruenden sich mit genau unserem Mangel - Fragmente und Luecken - und antworten mit: (a) Kettenbildung unorganisierter 3D-Kantenpunkte zu geordneten Kurvenzuegen, (b) differenzierbare Verfeinerung von Linie/Bezier direkt gegen die 2D-Kantenkarten mit Topologie-Operationen (Enden verschmelzen, Kollineare vereinen, unsichtbare loeschen). Unsere Stabilitaetskarte ist dort direkter Ersatz fuer DexiNed/PiDiNet. Wiederholungs-Prior (Fenster, Zacken) gibt es nur als Papier -> Eigenbau. S23DR-Rezept (Knoten + Kantenklassifikator) nur mit eigener Synthetik.

## 5. Plan (Reihenfolge, je Schritt Gate = Wolken-Gegenprobe unten UND Sweep B oben UND Overlay auf 3 Fotos)
1. **Kettenbildung** (Curvix-artig, Eigenbau, GPU-kNN): Sweep-Punkte + Tangente (aus 2D-Kantenrichtung der Referenzkarte) -> geordnete Ketten -> Modellwahl Linie / Kreisbogen / Bezier. Ersetzt RANSAC-Fragmente, loest Zacken und Boegen in einem Schritt. 1 Tag.
2. **Verfeinerung gegen Stabilitaetskarten**: Endpunkte/Kontrollpunkte per Distanztransformations-Verlust in allen sehenden Fotos (Sichtbarkeit aus Wolke), Topologie-Ops, Enden an Punktdichte beschneiden (LineGS-Idee). Gegen Konsolen-Buendel: IRLS-Ausgleich + Richtungsklassen. 1 Tag.
3. **Helm klein + Gauben als Formfamilien** (helm_fit erweitern: Punkte ueber der Dachebene ausschliessen, Spitze aus Karten verifizieren; Gaube = Satteldach-Primitive). 0,5 Tag.
4. **Wiederholungs-Prior**: Periode der Fensterachsen/Zacken per Autokorrelation, bestbelegtes Element kopieren, jede Kopie in >= 3 Fotos pruefen (Regel 9). 0,5 Tag.
5. **Handwahrheit**: 20 Kanten in 3 Fotos per foto_mass markieren -> Pruefstand-Sollwert fuer Treffer/Abdeckung. 0,5 Tag.
6. **Gitter -> Flaechen -> Koerper** (Ebenen aus Ketten, Sichtbarkeit, Rueckseite ANNAHME). Danach EdgeGaussians nur als Vollstaendigkeits-Orakel im GPU-Leerlauf.

# Plan: Vom Kantengitter zum H0-Kaufhaus (Stand 9.11.2026, 19:00)

Ziel (Nutzer): ein Gittermodell ALLER wesentlichen Kanten, rein aus Kantenerkennung, daraus ein druckbares 3D-Modell und ein beeindruckendes Kaufhaus in H0 (1:87). Handkorrektur nur, wo die Automatik am Rauschboden ist.

## 0. Wo wir stehen (gemessen, nicht gefuehlt)
Gitter v7 (`kaufhaus_alle/segmente_gitter_v7.json`, Viewer Version 6): 3041 Kanten. Abdeckung der unabhaengigen Wolkenkanten: < 12 m 0,90 (Mittag 0,85), 12-15 m 0,82 (0,62); Dach gegen Sweep B2 0,69. Drin: Arkadenboegen, Fensterrahmen mit Pfosten/Kaempfer, Bekroenungen, Figurenumrisse, Balkon oben/unten, Konsolen, First, Traufe, beide Staffelgiebel mit Zacken, grosser Helm (Formfit), 7 Pfeiler (Zylinder-Formfit, gemeinsamer Radius 0,437 m), Spiegel-/Wiederholungskopien (fotogeprueft). Fehlt: Balkonsaeulen, kleiner Helm, Gewoelberippen/Masswerk als Kurven, Gauben als Form, Rueckseite/Gassenwand, feine Sprossen.
Lehren des Tages (bindend): nur die VEREINIGUNG ueber Laeufe waechst (gitter_zurueck.py); jeder Filter braucht eine zweite, andersartige Referenz; Pruefen am Foto, nicht am eigenen Sweep; alles in der Kette (`tools/gitter_kette.sh`), nichts von Hand zusammenstecken.

## 1. Grundsaetze der Kette
1. **Ein Aufruf, ein Log, reproduzierbar**: `gitter_kette.sh NAME --vorher BESTES.json`; jede Stufe schreibt Zahlen in `bericht.txt`.
2. **Zwei Pruefmengen je Lauf**: Wolkenkanten (verfahrensfremd) und Sweep B (andere Referenzfotos); dazu Pruefblatt ueber ALLE Fotos mit Z-Puffer (Nutzerregel: in allen Bildern pruefen).
3. **Monoton**: neue Kanten nur mit Fotobeleg (>= 3 Fotos); alte Kanten nur raus, wenn sie am Foto durchfallen. Vor jedem Zeigen: Anteil alter Kanten, die noch da sind, je Hoehenband.
4. **Stopp-Kriterium (Rauschboden)**: ein Lauf bringt < 2 % neue fotobelegte Laenge UND das Pruefblatt zeigt keine fehlende sichtbare Kante mehr in den 12 Vertreterfotos -> Automatik fertig, Rest Editor.

## 2. Datenseite (laeuft heute Nacht automatisch)
- Fotos 440 + Videoframes 336 (registriert, Reproj 1,1 px) + 117 Hochformat-Frames (Registrierung laeuft) -> `kam_lot2_video.json`, Stabilitaetskarten fuer alle.
- Kette `video` (150 Frames als Referenz) -> `video_alle` (alle Frames) -> `foto` (Reproduktion). Erwartung: kleine Basen der Frames bringen Balkonsaeulen und Masswerk-Punkte; Frames aus der Halle die Pfeilerboegen.
- Noch ohne Daten: Rueckseite und Gasse (Nutzerfotos/Video-Plan vom 6.11.: Gassenwand, Erker-Unterseite). Ohne Bilder bleibt die Rueckseite `ANNAHME` (Spiegelung/Fortsetzung).

## 3. Methodenseite - naechste Bausteine (Reihenfolge nach Nutzen/Aufwand)
| # | Baustein | Was es bringt | Beweis/Tor | Aufwand |
|---|---|---|---|---|
| 1 | **Kettenbildung + Kurven** (Curvix-artig): Sweep-Punkte + 2D-Tangente -> geordnete Zuege -> Linie / Kreisbogen / Bezier (0,5-Regel) | Spitzboegen, Gewoelberippen, Masswerk, Helmgrate als Kurven statt Stuecke; Zacken als ein Zug | Overlay 3 Fotos + Wolken-Abdeckung nicht schlechter | 1 Tag |
| 2 | **Verfeinerung gegen Stabilitaetskarten** (SketchSplat-Idee, Eigenbau): Endpunkte/Kontrollpunkte per Distanztransformation in allen sehenden Fotos, Sichtbarkeit aus Wolke; Topologie-Ops (Enden verschmelzen, Kollineare vereinen, Unsichtbares loeschen); IRLS gegen Konsolen-Buendel | geschlossene Rahmen, saubere Ecken, weniger Doppellinien | Foto-Praezision steigt, Laenge sinkt nicht > 5 % | 1 Tag |
| 3 | **Formfamilien ausbauen**: Gaube (Satteldach-Primitive), kleiner Helm (Punkte ueber Dachebene ausschliessen, Spitze aus Karten), Baluster (Rotationskoerper aus Musterzelle), Fenster als Rahmen+Pfosten+Kaempfer-Parametrik | genau die Teile, die Kanten allein nicht fassen | je Teil >= 3 Fotos Detailrender neben Fotoausschnitt (Regel 9b/9d) | 1 Tag |
| 4 | **Wiederholung/Spiegel als Datengewinn** (Nutzerregel): Musterzelle aus allen Instanzen UND allen Fotos (Verdeckung mittelt sich raus), gemeinsame Masse (Radius, Breite), Kopien nur mit Fotobeleg | Balkonsaeulen, Fensterreihen komplett, beide Erker/Giebel gleich | Zahl der Kopien = Zaehlung am Foto (Regel 9) | 0,5 Tag (steht, verfeinern) |
| 5 | **Handwahrheit**: 20 Kanten in 3 Fotos per foto_mass markieren -> Pruefstand-Sollwerte fuer Treffer/Abdeckung | erste verfahrensfremde Zahl statt Zirkel | - | 0,5 Tag |
| 6 | **Gegenprobe fremd**: EdgeGaussians / LIMAP auf 80-120 Fotos im GPU-Leerlauf, nur Vergleich der Vollstaendigkeit, keine Mittelung (Lizenz: Test) | zeigt, was unsere Kette systematisch uebersieht | Differenzliste je Fassadenteil | 1 Tag Rechenzeit |

## 4. Vom Gitter zum Koerper (druckbar)
1. **Flaechen aus Kanten**: Ebenen-Hypothesen aus koplanaren Zuegen (Fassaden, Dachflaechen, Giebel), Zuschnitt an Kanten, Loecher (Fenster, Arkaden) als innere Zuege; Sichtbarkeit aus Fotos entscheidet, was Flaeche und was Oeffnung ist.
2. **Formfamilien werden Koerper**: Pfeiler = Zylinder, Helm = Pyramide, Gaube = Satteldach-Prisma, Fensterrahmen = Profil-Extrusion, Baluster = Rotationskoerper, Boegen = Extrusion des Bogenzugs.
3. **Zusammenbau** als manifold (manifold3d, `~/.venvs/rcpark`), Rueckseite/Gasse als `ANNAHME`-Flaechen; `bauen_abnehmen.sh` + Pruefstand mit Masstabelle (Quellen: Wolke Lage, Fotos Form, Zaehlungen am Foto).
4. **Pruefung**: `foto_diff.py` / `fehlteile_finden.py` auf 12 Vertreterfotos (rot = erfunden, gelb = fehlt), `teile_lage_pruefen.py`, Sichtblatt alle Seiten.

## 5. H0 (1:87) - was ein "beeindruckendes" Modell braucht
- Massstab: 1 m = 11,5 mm; kleinste druckbare Kante ~0,3 mm = 2,6 cm real. Sprossen (~5 cm) und Baluster (~15 cm) sind druckbar, aber als **Relief/Durchbruch-Regeln** zu vereinfachen: Masswerk als 0,4-mm-Stege, Fenster als 0,3 mm tiefe Nuten, Figuren als Blockformen mit Silhouette.
- Teileteilung fuer den P1S (Lehren Bambu): Rumpf, Dach mit Zacken (liegend drucken, Zacken nach oben), Helme/Erker einzeln (Stuetzen vermeiden), Arkadenpfeiler mit Boegen als ein Teil; keine Zapfen unter breiten Flaechen; Schnitt vor Slice pruefen.
- Vor dem Druck Regel 9b: jedes Teil neben dem Referenzfoto rendern; Zahl der Fenster/Zacken/Baluster = Zaehlung am Foto.
- Farbe: rote Fassade, graues Dach, farbige Helmschindeln, Gold an Erkern -> Mehrfarbdruck oder Lackiermaske aus dem Modell (Flaechenlisten exportieren).

## 6. Zeitplan
- **Heute Nacht (automatisch)**: Ketten video / video_alle / foto, ip169-Frames. Morgen frueh: Bericht lesen, Pruefblatt ansehen, Vergleich alt/neu je Hoehenband.
- **Tag 1**: Kettenbildung + Kurven (3.1), in Kette einhaengen, Gegenprobe.
- **Tag 2**: Verfeinerung gegen Karten + Topologie (3.2), Formfamilien Gaube/kleiner Helm/Baluster (3.3).
- **Tag 3**: Handwahrheit (3.5), Flaechen aus Kanten (4.1), erster manifold Rohkoerper, foto_diff.
- **Tag 4-5**: Koerper aus Formfamilien, Teileteilung H0, Probedruck Erker + Arkadenjoch; Regel 9b vor jedem Druck.
- Danach: Rueckseite nur mit neuen Fotos (Plan 6.11.), sonst ANNAHME.

## 7. Offene Risiken
- Rauschboden am Dach und an feinen Sprossen (Karten 1500 px): ggf. 3000-px-Karten nur fuer Nahaufnahmen (Rechenzeit x4).
- Posenfehler in der Hoehe nie gemessen (Lagebild): Handwahrheit an First/Zacken einplanen.
- Lizenzen fremder Werkzeuge nur zum Testen (LIZENZ_WERKZEUGE.md), vor Verkauf pruefen.

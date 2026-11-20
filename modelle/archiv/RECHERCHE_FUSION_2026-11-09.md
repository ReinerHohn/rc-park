# Recherche Fusion mehrerer Quellen zu einem Modell (9.11.2026)

Stand der Belege: Web-Suche am 9.11.2026. "Belegt" = in Suchtreffern bestaetigt; "Wissen" = aus dem Gedaechtnis, vor Nutzung pruefen. Lizenzen der Repos wurden NICHT einzeln verifiziert (Suche lieferte sie nicht) - vor Verkauf jede LICENSE-Datei lesen und in `modelle/LIZENZ_WERKZEUGE.md` eintragen.

## Empfehlung (kurz)
1. **Kein neues Fremdwerkzeug als Kern.** Die eigene SAM-Vereinigung beibehalten, aber das Merge-Kriterium von paarweisem Punktmengen-IoU auf **View-Consensus (MaskClustering)** umstellen und mit **SAI3D-Primitiven** (Uebersegmentierung der Wolke in Ebenen/Flicken, Vereinigung nur ueber Primitive) kombinieren. Das behebt "Wand verschmilzt mit allem" strukturell.
2. **Fusion = Hypothesenliste je Region, Auswahl per Energie** (Datenterm je Quelle + MDL-/Komplexitaetsterm), nicht Mittelung. Auswahl ueber Held-out-Foto-Reprojektion (Silhouetten-IoU/Kantenabstand) und Wolkenabstand; pro Teil gewinnt die Quelle mit dem niedrigsten Held-out-Fehler.
3. **Fassade = Raster/Wiederholung statt Manhattan-Solver.** PolyFit/KSR/City3D passen schlecht (Manhattan/Dachfokus, volle Huelle noetig, GPL). Besser: Ebene je Fassadenstueck + Fassaden-Grammatik (Rasterkonstanz, Symmetrie) = dein parametrischer Generator, Parameter gefittet mit MDL-Auswahl der Anzahl.
4. **Editor: Klick-SAM, Merge/Split, Typ, Parameter-Griffe; Korrekturen als harte Constraints** in der naechsten Fusion (Must-link/Cannot-link zwischen Primitiven), nicht als Training. Das ist leicht in three.js umsetzbar und braucht kein Netz-Training.
5. Zuerst bauen: (a) einheitliches Hypothesen-Schema + Held-out-Score, (b) Primitive + Consensus-Merge, (c) Editor mit Constraint-Rueckfluss. Etwa 2-3 Wochen, siehe Abschnitt 5.

## 1. Fusion von 2D-Masken zu 3D-Instanzen

| Verfahren | Idee / Merge-Kriterium | Code, Lizenz, GPU |
|---|---|---|
| SAM3D (Yang 2023, [arXiv 2306.03908](https://arxiv.org/pdf/2306.03908)) | SAM-Masken je Bild in 3D heben, **bidirektionales Mergen nur zwischen Nachbarbildern** (Overlap-Verhaeltnis ueber Schwelle) | Repo-Lizenz nicht verifiziert; GPU fuer SAM |
| SAI3D (Yin, CVPR 2024, [arXiv 2312.11557](https://arxiv.org/html/2312.11557v2)) | Szene in **geometrische Primitive** (Superpunkte) zerlegen; duenne **Affinitaetsmatrix** aus SAM-Masken (zwei Primitive in derselben Maske = Stimme, ueber alle gueltigen Bilder aggregiert); **hierarchisches Region-Growing mit dynamischer Schwelle** (Schwelle sinkt schrittweise, liefert Granularitaetsebenen). Belegt: AP50 31,1 vs SAM3D 14,2 auf ScanNet++; Autoren begruenden, SAM3D leide an lokalem Nachbarbild-Merge ohne globalen Konsens | Training-frei; Lizenz pruefen |
| MaskClustering (Yan, CVPR 2024, [arXiv 2401.07745](https://arxiv.org/abs/2401.07745v1)) | **View-Consensus-Rate**: fuer zwei Masken A,B zaehle ueber alle Bilder, in denen beide sichtbar sind, den Anteil, in dem sie von einer gemeinsamen Maske "unterstuetzt" werden (eine 2D-Maske enthaelt beide) vs. Widerspruch (beide sichtbar, aber in getrennten Masken). Kante = Konsens wenn Rate hoch UND genug Beobachter; **iteratives Clustering** der Maskengraphen; Training-frei. Belegt: SOTA auf ScanNet++, ScanNet200, Matterport3D | Projektseite pku-epic.github.io/MaskClustering; Lizenz pruefen; GPU optional |
| Open3DIS ([arXiv 2312.10671](https://arxiv.org/pdf/2312.10671)), OpenMask3D ([2306.13631](https://arxiv.org/pdf/2306.13631.pdf)), Mask3D | Alle brauchen **auf ScanNet trainierte 3D-Netze** (Mask3D) bzw. CLIP-Merkmale; Domaene Innenraum. Fuer eine Fassade nicht passend, CLIP-Semantik nicht noetig | Mask3D/ScanNet-Gewichte: Datenlizenz ScanNet ist nicht kommerziell (Wissen) - **NC-Risiko** |
| Gaussian Grouping ([ECCV 2024, arXiv 2312.00732](https://arxiv.org/abs/2312.00732)), SAGA ([arXiv 2312.00860](https://arxiv.org/abs/2312.00860v3)) | Identitaetsvektor je Gaussian, Training mit SAM-Masken + 3D-Konsistenz; nur sinnvoll, wenn 3DGS ohnehin existiert; GS im Wettbewerb bei uns schlecht (Register BR) | 3DGS-Code der Inria-Linie ist **nicht kommerziell** (Wissen); Gaussian Grouping Lizenz in Quellen widerspruechlich (Apache-2.0 vs. MIT-Ableger) - pruefen; GPU noetig |

**Was uns hilft (konkret):**
- **Merge-Kriterium**: Punktmengen-IoU zweier Masken ist bei einer Wand, die in vielen Bildern anders beschnitten ist, instabil und "kettet" (Single-Linkage in Union-Find: eine falsche Kante verklebt alles). Besser: Consensus-Rate = unterstuetzende Bilder / (unterstuetzende + widersprechende Bilder), nur Bilder zaehlen, in denen beide Objekte sichtbar sind (Tiefenpuffer hast du). Merge nur wenn Rate >= ca. 0,8-0,9 (MaskClustering-Papier: Schwelle im Bereich 0,9, Wissen, am Paper nachlesen) UND mindestens ~3 Beobachter. Union-Find ersetzen durch **iteratives Average-Linkage**, hoechste Konsens-Kante zuerst, Neuberechnung nach jedem Merge.
- **Verschmolzene Wand zerlegen**: Widerspruchszaehlung - zwei Primitive, die in vielen Bildern in getrennten Masken liegen, duerfen nicht in einem Cluster landen, auch wenn Ketten sie verbinden (Cannot-link). Das ist genau die Info, die Union-Find wegwirft.
- **Primitive statt Punkte**: Wolke vorab in Superpunkte/Ebenenflicken (Region Growing nach Normale/Farbe, 5-20 cm) zerlegen; Masken liefern Stimmen pro Primitiv-Paar (SAI3D). Rechenzeit sinkt um Groessenordnungen, Masken-Raender (die Hauptursache fuer Fehlmerges) wirken nur noch als Stimme.
- **Granularitaet**: SAM liefert je Bild mehrere Ebenen (grob/mittel/fein, hast du schon). Cluster je Ebene getrennt rechnen, dann Baum bauen: Kind gehoert zu Elter, wenn >= 90 % seiner Primitive im Elter liegen. Die dynamische Schwelle aus SAI3D erzeugt dasselbe von selbst (Schwelle absenken = groebere Ebene).
- Nicht uebernehmen: Mask3D/OpenMask3D/Open3DIS (Trainingsdaten Innenraum, NC-Risiko), Gaussian-Verfahren (kein 3DGS im Kern).

## 2. Fusion heterogener Geometrie

- **Energie/Graph-Cut mit Datentermen mehrerer Quellen** (Standard in Multi-View-Stereo-Netzen, z.B. Labatut/OpenMVS Delaunay+GraphCut, das ihr schon nutzt): Datenterm = Sichtbarkeit/Wolke; Glattheit = Flaechenminimierung. Erweiterbar um zusaetzliche Terme (SAM-Silhouette: Voxel ausserhalb der Maske in >= k Bildern = "leer"), siehe Voxel-Schnitzen.
- **PolyFit (Nan & Wonka 2017)**: Ebenen per RANSAC, Kandidatenflaechen aus Ebenenschnitt, **binaere Auswahl per ILP** (Datenterm Punktabdeckung, Vollstaendigkeit, Komplexitaet). Braucht geschlossenen Koerper und Ebenen, die ihn definieren; Wolke nur vorne (Rueckseite fehlt) bricht den Ansatz; Manhattan nicht noetig, aber Ebenen muessen alle vorhanden sein. Code im CGAL-Umfeld/GPL (Wissen).
- **Kinetic Shape Reconstruction / Kinetic Surface Reconstruction (CGAL ab 6.0)**: Ebenen wachsen kinetisch, bilden Zellkomplex, Auswahl per Graph-Cut. Belegt: Paket "Kinetic Surface Reconstruction" seit CGAL 6.0, Lizenz GPL ([Referenz](https://doc.cgal.org/6.0-beta1/Kinetic_surface_reconstruction/group__PkgKineticSurfaceReconstructionRef.html)); CGAL ist GPL3+ oder kommerziell ueber GeometryFactory ([cgal.org/license](https://www.cgal.org/license.html)). **Fuer Verkauf: GPL = Ausschluss oder Lizenz kaufen.** Robust bei unvollstaendigen Daten, aber Ergebnis ist Polygon-Huelle, kein Fassadenmodell mit Fensterreihen.
- **City3D (Huang 2022)**: Dachmodelle aus Luftlaser + Grundriss; nicht fassadenzentriert; Lizenz nicht verifiziert (Suche ohne Treffer) - vermutlich GPL-Umfeld (Wissen).
- **Scan-to-BIM**: Ebenen/Wandfinder + Regelbibliothek + semantische Zuordnung; Prinzip passt (Typ je Bauteil), Werkzeuge meist proprietaer.
- **Fassaden-Grammatiken / Facade Parsing** (Teboul et al. 2010/2013, Riemenschneider 2012, Martinovic/Van Gool): Fassade als Raster von Spalten/Zeilen, Fenster als Wiederholung, binaere Split-Grammatik, Optimierung per RL/MCMC. Wiederholung und Symmetrie sind genau die Information, die bei Teilsicht (Wolke nur vorne) fehlende Teile ersetzt. Fuer unseren Generator: Rasterparameter (Abstand, Anzahl, Gleichheit) gemeinsam fitten, ein Fenster nur schwach, die Reihe stark.
- **Primitive Fitting + MDL**: RANSAC (Schnabel 2007, Efficient RANSAC, in CGAL/GPL; Open3D-Ebenen-RANSAC MIT) oder Region Growing; Auswahl der Primitivmenge nach **MDL** (Kosten = Modellbits + Residuumbits), z.B. Delong et al. "Fast Approximate Energy Minimization with Label Costs" (PEARL). Label-Kosten = Komplexitaet eines Parametersatzes. Das ist das passende Gegengewicht, damit nicht jede Hypothese ueberlebt.

**Passend zu uns (historische Fassade, nicht-Manhattan, Wolke nur vorne):** Ebenen je Fassadenabschnitt (auch schraeg) per PEARL/MDL, darin parametrische Raster (Fenster/Bogen) nach Grammatik; Tiefenversatz (Erker, Gesimse) als Extrusion relativ zur Ebene; Rueckseiten und Dach aus Voxel-Schnitzen/Delaunay-Netz oder bewusst offen ("unbeobachtet" kennzeichnen). Kein globaler Ebenen-Schnitt (PolyFit/KSR) als Kern.

## 3. Konfidenz und Quellenwahl ohne Handlabels

Robuste Signale (alle automatisch, alle ohne Label):
1. **Held-out-Foto**: 10-20 % der Fotos (nach Position gestreut, nicht nach Zufall, wegen Nachbarn) nie im Fit verwenden; Hypothese in diese Kameras rendern; Fehler = 1 - Silhouetten-IoU mit SAM-Maske des Teils, oder Chamfer-Abstand Modellkanten zu Fotokanten (foto_diff). Das ist die ehrlichste Zahl, weil unabhaengig von der Wolke. Warnung aus eigenen Notizen: Diff-Rauschboden - nur Unterschiede groesser als der Boden zaehlen (Register BS56-BS71).
2. **Wolkenabstand**: Median und 90-Perzentil Punkt-zu-Modell nur in sichtbaren, gut belegten Zellen; Fehler ist blind fuer Tiefe aus Foto-Sicht und fuer unbeobachtete Bereiche.
3. **MDL/Label-Kosten**: Bevorzugt einfachere Hypothese bei gleichem Held-out-Fehler (Fenster-Raster 1 Parametersatz vs. 12 Einzelboxen).
4. **Konsistenz zwischen Quellen**: Uebereinstimmung der Lage in 2+ unabhaengigen Quellen (z.B. SAM-3D-Objekt-Box und Wolkenfit) erhoeht Konfidenz; Widerspruch = **nicht mitteln**, als Konflikt markieren (CLAUDE.md Regel 5) und im Editor zur Entscheidung vorlegen.
5. Unsicherheit der Parameter: Hessian/Plateaubreite aus dem GPU-Sweep (vorhanden) als Standardabweichung; schmales Plateau = hohe Konfidenz.

Nicht robust: IoU allein auf dem Fit-Datensatz (zirkulaer), Kennzahlen ohne Blick auf ROI.

## 4. Interaktives Korrigieren (Human-in-the-loop)

Muster aus der Literatur:
- **Klick-basierte 3D-Segmentierung**: AGILE3D ([ICLR 2024, arXiv 2306.00977](https://arxiv.org/pdf/2306.00977)) - positive/negative Klicks als Queries, leichter Decoder pro neuem Klick, mehrere Objekte gleichzeitig; Netz auf ScanNet trainiert (Domaenenabstand, Lizenz pruefen). Fuer uns einfacher: **Klick -> SAM-Prompt in den 2-3 besten Fotos -> Maske in 3D heben -> Primitivmenge**. Entspricht SAM-Click-Refinement, vorhandene Bausteine.
- **Merge/Split/Paint** (typisch in Annotationswerkzeugen wie CloudCompare-Segmentierung, Semantic Segmentation Editor, Labelcloud): Objekt waehlen, Pinsel (Kugel in 3D) fuegt Primitive zu/entfernt sie.
- **Corrections als Signal**: (a) **harte Constraints** fuer die naechste Clusterung: Merge = Must-link zwischen Primitiven, Split = Cannot-link, Typaenderung = fester Label; diese Kanten in Consensus-Graph mit Gewicht +/- unendlich einsetzen, Cluster neu rechnen, restliche Szene aendert sich nur lokal (Constraint-Propagation). (b) **Parameter-Pinning**: gezogener Wert wird fest, uebrige Parameter werden neu gefittet. (c) **Gewichtslernen**: aus den Korrekturen (50-200 Ereignisse genuegen) logistische Regression ueber wenige Merkmale (Consensus-Rate, Normalenwinkel, Farbabstand, Abstand, Held-out-Fehler) -> bessere Merge-Schwelle; kein Netz-Training. (d) **Aktive Auswahl**: dem Nutzer zuerst die Teile mit niedrigster Konfidenz bzw. groesstem Quellenkonflikt zeigen.

Leicht in three.js:
- Raycast-Pick auf Instanz-ID-Puffer (ID als Vertex-Attribut / GPU-Picking-Pass), Highlight per Shader-Uniform.
- Merge/Split/Typ als Buttons; Auswahlpinsel (Kugelradius per Mausrad) -> Liste von Primitiv-IDs.
- Parameter-Griffe (TransformControls fuer Box/Lage, Slider/Handles fuer Fensterzahl, Raster-Abstand, Bogenradius); Live-Update des Generators im Browser (Generator-Parameter als JSON, Mesh clientseitig oder per Rechen-Endpunkt).
- Schicht "Konflikt/Konfidenz" als Farbe; Foto-Overlay des Teils neben 3D.
- Korrekturen als **Ereignisprotokoll** (JSON, append-only: {typ, ids, parameter, zeit}) speichern; Server wendet es als Constraints an. Undo gratis durch Protokoll.

## 5. Konkreter Fusions-Ablauf

**Datenstruktur** (eine Datei `hypothesen.json` + Binaer-Arrays):
- `primitive[]`: ID, Punktindizes, Ebene/Normale, Farbe (Superpunkt, 5-20 cm).
- `hypothese`: ID, Quelle (sam3d | schnitzen | netz | generator | linien), Typ (Wand, Fensterreihe, Bogenreihe, Erker, Quader, Dach, unbekannt), Primitivmenge, Geometrie (Parameter oder Netz), `konfidenz` mit Teilen: wolke_abstand, heldout_fehler, mdl_kosten, konsens, plateau_sigma.
- `constraints[]`: Nutzerereignisse (must/cannot-link, feste Parameter, Typ).

**Konfidenz je Quelle (Zahlen):**
- SAM-3D-Objekt: Consensus-Rate, Anzahl Beobachter, Anteil sichtbarer Bilder.
- Voxel-Schnitzen: Zahl der Kameras mit klarer Silhouette, Konkavitaets-Warnung (Schnitzen kann Nischen nicht), Held-out-IoU.
- OpenMVS-Netz: lokale Punktdichte, Wolkenabstand; nur wo Dichte > Schwelle.
- Generator: Held-out-Fehler + Wolkenabstand + MDL + Plateaubreite.
- 3D-Linien: Reprojektionsfehler in >= 3 Bildern, Anzahl Bilder; zunaechst nur als Zusatzterm im Datenterm der Generatorfits.

**Ablauf:**
1. Primitive (Region Growing) + Sichtbarkeitsmatrix Primitiv x Foto (Tiefenpuffer vorhanden).
2. SAM-Masken -> Stimmen (SAI3D) + Consensus/Widerspruch (MaskClustering) -> iteratives Clustern je Granularitaet -> Instanzbaum.
3. Typ je Instanz: Regelklassifikator aus Form (Ebenheit, Seitenverhaeltnis, Wiederholung) + SAM-Merkmale; unsichere als `unbekannt`.
4. Hypothesen erzeugen: Generator-Fit je Typ (Wolke + Foto-Kanten, Regel 9d), Schnitzen, Netz-Patch.
5. Auswahl: pro Instanz die Hypothese mit kleinster Energie `E = Held-out-Fehler + lambda_wolke * Wolkenabstand + lambda_mdl * Komplexitaet`; lambdas aus Rauschboden kalibrieren; Konflikt-Flag wenn zwei Hypothesen innerhalb Rauschboden liegen aber geometrisch > 0,4 m auseinander.
6. Zusammensetzen (Ebene + Extrusion + Raster), Kollisionen (Fenster ausserhalb Wand) loesen, Pruefstand.
7. Editor: Konflikte zuerst; Korrekturen -> `constraints[]` -> Schritt 2/5 lokal neu.
8. Lernen: Merkmalsgewichte aus Korrekturen (logistisch) nach je ~100 Ereignissen neu anpassen.

**Reihenfolge / Aufwand (grob):**
1. Primitive + Sichtbarkeitsmatrix + Consensus-Clustering ersetzen Union-Find: 4-6 Tage (Beweis: synthetisch, dann zwei echte Objekte, Wand muss zerfallen).
2. Hypothesen-Schema + Held-out-Score + Auswahl: 3-4 Tage.
3. Editor-Grundfunktionen (Pick, Merge/Split, Typ, Parameterhandles, Ereignisprotokoll): 4-5 Tage.
4. Constraint-Rueckfluss + Lerngewichte: 3 Tage.
5. 3D-Linien in Datenterm: 3-5 Tage (Triangulation noch offen).
Gesamt ca. 2-3 Wochen.

**Die 3 groessten Risiken:**
1. **Held-out-Score am Rauschboden** (frueherer Befund: kein Modell klar besser): Auswahl wird zufaellig; Gegenmittel: Mindestabstand, sonst Konflikt an den Nutzer statt Entscheidung.
2. **Uebersegmentierung/Mischobjekte durch SAM** (Wand + Gesims + Schatten in einer Maske): Consensus-Rate kann falsche Einheiten bestaetigen; Gegenmittel: Primitive nach Normale/Farbe trennen, feinste SAM-Stufe als Cannot-link-Quelle, Editor-Korrekturen frueh.
3. **Teilsicht**: Wolke nur vorne - Rueckseite/Dach nicht beobachtbar; Fusion darf dort nichts "erfinden" ohne Kennzeichnung `ANNAHME`; Wiederholung (Grammatik) ist Annahme und gehoert im Pruefstand ausgewiesen.

## Lizenzuebersicht (vor Verkauf pruefen)
- CGAL (KSR, PolyFit-Umfeld, Efficient RANSAC): **GPL3+ / kommerziell** (belegt) - nur fuer Tests oder mit GeometryFactory-Lizenz.
- Inria-3DGS-basierte Verfahren (Gaussian Grouping, SAGA): Basiscode nicht kommerziell (Wissen) - NC.
- Mask3D/OpenMask3D/Open3DIS: Gewichte auf ScanNet trainiert, ScanNet-Nutzungsbedingungen nicht kommerziell (Wissen); Repo-Lizenzen nicht verifiziert - NC-Verdacht.
- SAM: Apache-2.0 (Wissen); SAI3D/MaskClustering/SAM3D: Algorithmus frei nachbaubar (Idee), Code-Lizenz nicht verifiziert - eigener Nachbau vermeidet das Problem.
- three.js: MIT.

Quellen: arXiv 2312.11557 (SAI3D), 2401.07745 (MaskClustering), 2306.03908 (SAM3D), 2312.10671 (Open3DIS), 2306.13631 (OpenMask3D), 2312.00732 / 2312.00860 (Gaussian Grouping / SAGA), 2306.00977 (AGILE3D), cgal.org/license.html, CGAL-Handbuch Kinetic Surface Reconstruction.

# Recherche 2026-11-07: Fenster in ebenen Fassaden (Historisches Kaufhaus)

Nur Web-Recherche, nichts installiert. Die Websuche lieferte fuer 2021-2025 wenig Treffer; "[geprueft]" = Seite/Lizenz in dieser Recherche gesehen,
"[Gedaechtnis]" = Wissen ohne Quellenabruf, vor Einsatz Lizenzdatei lesen (Verkauf geplant!).

## 1. Detektion / Parametrisierung (Wolke, Bild, Wiederholung)
- Tuttas/Stilla 2011: Fenster aus Punkten hinter der Fassadenebene, Fourier-Test auf Wiederholung, Dichtepeaks als Rueckfall.
  https://www.isprs.org/proceedings/XXXVIII/3-W22/pdf/131_XXXVIII-3-W22.pdf [geprueft] - Idee uebertragbar (Loecher/Tiefe), Methode alt.
- Aijazi 2014: Fenster aus mobilem LiDAR, Parameter ueber Fassadensymmetrie. https://isprs-annals.copernicus.org/articles/II-3/1/2014/ [geprueft]
- ISPRS 2013 (II-5-W2/241): Wiederholte Elemente aus Planarpatches. https://isprs-annals.copernicus.org/articles/II-5-W2/241/2013/isprsannals-II-5-W2-241-2013.pdf [geprueft]
- Mitra et al. EG 2013 (Factored Facades): Wiederholungsmuster + je Element Verformungsparameter - genau das "Median plus Einzelabweichung".
  https://discovery-pp.ucl.ac.uk/id/eprint/1393828/1/Mitra_interactiveFacades_eg13_small.pdf [geprueft], Code unklar.
- Hu et al. 2022 (ISPRS JPRS): CNN klassifiziert Fenstertyp + Parameter aus Bildpatches, speist Grammatik. https://arxiv.org/abs/2201.08977 [geprueft], Lizenz Code unklar (nachsehen).
- Nishida/Bousseau/Aliaga EG 2018: CNN + Optimierung waehlt Grammatik und Parameter. https://www.cs.purdue.edu/cgvlab/papers/aliaga/eg18.pdf [geprueft]
- FaçAID 2024: Transformer erzeugt Split-Grammatik aus Layout-Segmentierung. https://arxiv.org/html/2406.01829v2 [geprueft], Lizenz offen.
- Fassaden-Parsing: ECP/CMP/CFP-Datensaetze, ViT+Linienintegration https://arxiv.org/abs/2309.15523 [geprueft];
  DLR "Cross Field ... Rectangular Windows" (Vektorisierung rechteckiger Fenster) https://elib.dlr.de/189964/1/Cross_Field-Based_Segmentation_and_Learning-Based_Vectorization_for_Rectangular_Windows.pdf [geprueft].
  Datensatzlizenzen meist Forschung (NC) - nur Gewichte-Nutzung pruefen, nicht trainieren.
- LoD3/Splatting: GS4City (Code github Jinyzzz/GS4City), GS4Buildings https://arxiv.org/pdf/2508.07355, Texture2LoD3 [geprueft als Existenz]; Wolke-Quelle ist bei uns aber fest, nur Vergleich.
- Zero-Shot-Maske: SAM (Apache-2.0) / OWLv2 (Apache-2.0) [Gedaechtnis] - Fensterkandidaten im Foto; Memory: OWLv2 ist schon vorgesehen.

## 2. Parametrische Fenstermodelle
Kein veroeffentlichtes Standardmodell mit Laibung/Bank/Sturz gefunden, das man uebernehmen koennte -> eigenes Modell (Stand der Technik: Split-/Shape-Grammatik, CGA Shape [Gedaechtnis], Esri-Lizenz, nicht nutzen).
Eigenes Modell, 9-12 Parameter, alles in m auf der Fassadenebene (u,v): Mitte u0,v0; Breite b, Hoehe h; Laibungstiefe t; Gewaendebreite g (Seiten) und gs (Sturz); Bankvorsprung/-hoehe; Sprossen nx, ny + Sprossenbreite;
Sturzform (flach / Segmentbogen: Stichhoehe f als Zusatzparameter, f=0 = flach). Kontinuierlich parametrisiert, damit derivatfrei fitbar; Anzahl Sprossen diskret, vorab aus Foto zaehlen (Regel 9 CLAUDE.md).
Fit gegen Wolke: Tiefenprofil Fassadenebene -> Laibungstiefe t (Medianschnitt, Auflosung 1-2 cm reicht); Kanten der Gewaende aus Normalenspruengen. Fit gegen Bild: Kantendiff (Abschnitt 3).

## 3. Derivatfreie Optimierung + Fitness aus Kantendiff
- CMA-ES pycma: BSD-3-Clause https://github.com/CMA-ES/pycma [geprueft]. Robust bei 10-30 Parametern, Populations-Parallelisierung, Restarts (IPOP/BIPOP) = Mehrfachstart eingebaut, Bounds.
  Beleg fuer CMA-ES + silhouettenbasierte Rendering-Fitness gegen lokale Minima: https://arxiv.org/pdf/2603.11404 (2026) [geprueft].
- scipy differential_evolution / minimize(Nelder-Mead, Powell): BSD-3 [Gedaechtnis]. DE gut fuer 5-10 Parameter, Nelder-Mead nur zur Endpolitur.
- Bayes-Opt (Optuna MIT, scikit-optimize BSD, nevergrad MIT) [Gedaechtnis]: nur sinnvoll, wenn ein Render >1 s kostet; bei uns Render schnell -> CMA-ES besser.
- Renderer: nvdiffrast = NVIDIA Source Code License, nur nicht-kommerziell [geprueft: https://huggingface.co/spaces/ginipick/SORA-3D/blob/e3df509037b8d7a49ea8599caebb1c08922cea96/extensions/nvdiffrast/LICENSE.txt] -> NICHT fuer Verkauf (in LIZENZ_WERKZEUGE.md eintragen).
  PyTorch3D: BSD-3 [geprueft: https://github.com/eliemichel/pytorch3d, README]. SoftRas: Lizenz nicht geprueft.
  Fuer derivatfreie Suche braucht man KEINE Differenzierbarkeit: eigener GPU-Rasterer (vorhanden: tools/render_kern.py) oder Orthoansicht der Fassade als reine 2D-Kantenkarte (Rechtecke/Bogen direkt zeichnen) genuegt.
- Fitness: Chamfer-/Distanztransformation der Canny-Fotokanten (Fotokanten -> DT, Modellkanten abtasten, Mittel der DT-Werte, getrimmt/robust z.B. 80 %-Quantil), zusaetzlich Wolke: Abstand Laibungsflaeche zu Punkten. Fotokanten nach Verdeckung/Verzeichnung maskieren.
  Verwandt: Chamfer-Silhouettenfit https://arxiv.org/pdf/1906.07870 [geprueft].
- Ueberanpassungsschutz: Holdout-Fotos (z.B. 1/3 der Ansichten nie in der Fitness, Gate = Holdout-Fehler nicht schlechter als Fit-Fehler + Toleranz), Parametergrenzen aus Bauwissen (Quelle!), Regularisierung zum Median-Fenster, Mehrfachstart mit Streuung der Ergebnisse als Unsicherheit.

## 4. Inverse prozedurale Modellierung (IPM)
Stand: Grammatik-/Layoutlernen (Nishida 2018, Hu 2022, FaçAID 2024, Dax 2025 https://web3.arxiv.org/pdf/2501.17044 [geprueft]) braucht Trainingsdaten und ist fuer EIN Gebaeude mit ~Dutzend Fenstern uebertrieben.
Fuer uns reicht "Mini-IPM": feste Fensterfamilie (Abschnitt 2) + Gitter/Wiederholungsstruktur (Achsen u_i, Geschosse v_j aus Projektionsprofilen der Kanten/Loecher) + Parameterfit. Aufwand klein, Passung hoch.

## 5. Median-Fenster plus Einzelabweichung
- Fenster nach Typ clustern (Breite/Hoehe/Sturzform; k-Means oder einfache Schwelle), je Cluster Parameter-Median (robust, MAD) = "Typfenster".
- Rauschminderung ueberlagert: Wolkenausschnitte jedes Fensters in lokales (u,v,n)-System legen, Tiefenkarte median-fusionieren (Pixel 1 cm); Fit am Median ergibt Laibung/Bank/Sturz mit kleinerem Rauschen als Einzelfit.
- Einzelabweichung zulassen: pro Fenster Offsets (du,dv,db,dh,dt) mit L2- oder L1-Strafe zum Typwert (Prior-Staerke ~ MAD); Abweichung gilt nur, wenn Foto-Holdout-Kantenfehler UND Wolke sie beide stuetzen, sonst Typwert (Regel 5: Quellenwiderspruch stehen lassen, nicht mitteln).
- Gitterlage getrennt: Mittenabstaende frei lassen (historisch ungleichmaessig), nur Form teilen.

## Bewertung (Passung / Lizenz / Aufwand 1-5 / Testplan)
1. CMA-ES (pycma) + Chamfer-Kantendiff, eigener Rasterer: Passung hoch / BSD-3 ok / 2 / Test: synthetisches Fenster mit bekannten Parametern rendern, Start verstoeren, Parameter auf <1 cm zurueckfinden.
2. Typfenster-Median + Einzelabweichung (Mitra-Idee): hoch / eigene Umsetzung ok / 2 / Test: aus 6 gleichen Fenstern mit kuenstlichem Rauschen den Median-Fehler gegen Einzelfit vergleichen.
3. Wolken-Tiefenprofil fuer Laibung/Bank (Tuttas-Idee): hoch fuer t / eigen / 2 / Test: Laibungstiefe an 3 Fenstern mit Laser- oder Foto-Handmass (foto_mass.py) gegenpruefen.
4. Fensterkandidaten per OWLv2/SAM im Foto + Gitterausrichtung: mittel (Detektion), Einstieg / Apache-2.0 [Gedaechtnis] / 3 / Test: Trefferquote auf allen 94 Fotos gegen Handzaehlung (Regel 9).
5. DE/Nelder-Mead als Gegenprobe/Politur (scipy): mittel / BSD-3 / 1 / Test: gleiche synthetische Aufgabe, Ergebnis mit CMA-ES vergleichen (Stabilitaet).
Nicht empfohlen: nvdiffrast (NC-Lizenz), gelernte Grammatiken (FaçAID/Hu: Daten fehlen, Lizenz offen), Gaussian-Splatting-Ketten (Wolke ist gesetzt), CGA/CityEngine (kommerziell).

## Empfohlene Pipeline in 8 Schritten
1. Fassadenebene je Seite aus Wolke (RANSAC, Normalen), Wolke in (u,v,Tiefe) abwickeln; Tiefenkarte 1-2 cm.
2. Fensterkandidaten: Loecher/Tiefenspruenge in der Tiefenkarte + OWLv2-Boxen im Foto; Zaehlung nur am Foto (Regel 9).
3. Gitter: Geschosshoehen v_j und Achsen u_i aus Projektionsprofilen; Typen clustern (b,h,Sturzform).
4. Anfangsfenster je Kandidat aus Tiefenkarte (Rand, Laibungstiefe, Bank/Sturz) mit beleg() je Element.
5. Typfenster: Tiefenkarten gleicher Typen median-fusionieren, CMA-ES-Fit der 9-12 Parameter (Wolke + Kantendiff), Mehrfachstart.
6. Pro Fenster Abweichungen (du,dv,db,dh,dt) mit Prior zum Typfenster, CMA-ES erneut; Annahme nur bei Holdout-Verbesserung.
7. Holdout-Gate: 1/3 der Fotos nur zur Pruefung; foto_diff.py vor/nach, Pruefstand-Sollwert je Parameter, Streuung der Mehrfachstarts als Unsicherheit in masstabelle.json.
8. Einbau in Generator als Parameter + Tabellenzeile, Bau mit tools/bauen_abnehmen.sh, Sichtblatt/Detailrender ansehen, Druckteil neben Foto legen (Regel 9b); Lizenzstand in LIZENZ_WERKZEUGE.md.

# Pipeline Hybrid: Wolke-Körper + 3D-Kanten + Diff gegen Wolke (3D) und JEDES Foto (Perspektive)
Stand 6.11.2026 abends. Nutzerentscheid: LoD2 ist NUR Notnagel; Punktwolke = erste Wahrheit; "so schnell wie möglich an die Wolke annähern, dann den Diff drehen,
im 3D gegen die Wolke und mit Perspektive gegen JEDES Foto"; Hybrid = 3D-Modell erzeugen UND Kanten für das 3D-Modell erkennen.
Status je Stufe: [x] gebaut und gelaufen, [~] teilweise, [ ] fehlt. NICHTS davon ist am Kaufhaus bewiesen (Beweis zuerst an künstlicher Szene, SPEC_BEWEIS_ANSATZ.md).

## Stufen
1. Eingaben [x]: Fotos (Archiv, Handy-Serien a-j, Video), Anker (LoD2/DOM1/DGM1 nur Maßstab/Lage), Kameras je Foto.
2. Wolke [x]: COLMAP-Bündel + dichte Wolke (fused.ply + .vis). 89 kalibrierte Fotos (K-Protokolle).
3. KÖRPER aus der Wolke [~]: Sichtbarkeits-Carving (tools/wolke_carving.py, Voxel 0,10 m) = roher, treppiger Körper mit Erker/Balkon/Arkaden. LoD2 nur wo die Wolke schweigt.
4. 3D-KANTEN [~]: tools/kanten_3d.py (930 Linien Kaufhaus), ebenen_modell.py (Ebenen mm-genau); SPEC_S10: 4 Detektoren -> 3D-Kantenfeld über alle Fotos.
5. ZWANG [ ]: Körper-Knoten/-Flächen auf gemessene Ebenen und Kanten ziehen (nur die Kanten werden gerade gezwungen, Rest bleibt glatt); Bögen = freie Kurven aus den Kanten.
   NICHT wie S8 (Ebenen bilden den Körper per Zellbelegung - gescheitert, Kanten p90 75 cm), sondern Körper aus der Wolke + Kanten als Zwang.
6. DIFF [~]:
   a) 3D: Abstand Modell -> Wolke NUR auf von Kameras gesehenen Flächen (tools/wolke_abstand_einseitig.py; Test 6.11. NICHT verwertbar: unbeobachtete Flächen dominieren, sichtbare Filter fehlt)
      und Abdeckung Wolke -> Modell. Rahmen geprüft: Wolke->Modell Median 0,35 m an der Hauptfassade, kein Rahmenfehler.
   b) 2D: Modell mit der eigenen Kamera in JEDES Foto (tools/foto_diff.py, kosten_lr, rot/gelb); Region je Bauteil (--region himmel gebaut, Region aus Bauteil-Fußabdruck fehlt).
7. Verbessern [ ]: Fehlerkarte auf der Oberfläche; nur dort bewegen, wo Wolke UND mehrere Fotos übereinstimmen; Widerspruch Foto/Wolke NICHT mitteln, als Beobachtung stehen lassen.
8. Regularisieren / druckbar machen [~]: parametrische Bauteile (baukasten_gen.py) als Reinigung NACH dem Körper, nicht als Grundlage; generator_schleife.py passt die Maße an (heute 4 Zahlen).
9. Prüfung [x]: Pruefstand, Sichtblatt, foto_diff, Zählen am Foto (Regel 9), Holdout-Fotos 001 024 054 083 211 234.
10. Ausgabe [~]: STL 1:87, 3D-Seite (Artifacts), Druck.

## Beweis vor Einsatz
Künstliche Szene mit bekannter Wahrheit (Arkaden, Erker, Treppengiebel, Satteldach), gerendert aus bekannten Kameras, Wolke mit 3 cm Rauschen:
Kantenabweichung < 5 cm -> Weg tragfähig; sonst verworfen und im Versuchsregister eingetragen. Erst danach Kaufhaus (Holdout-Fotos, kosten_lr besser als Carving).
Vergleich der Methoden nur mit gleichem Mass/Budget; jedes Bauteil nur behalten, wenn es in SEINER Region besser wird, ohne ein anderes Foto zu verschlechtern.

## Recherche (6.11., Websuche, nur Titel/Zusammenfassungen gelesen, nichts reproduziert)
Einzelteile sind Stand der Technik; die GENAUE Kombination (Carving-Körper + 3D-Kantenzwang + Diff gegen Wolke UND jedes Foto + parametrische Reinigung) fand ich nicht.
- Von einem groben Netz ausgehen und es per Photo-Konsistenz über alle Bilder verfeinern: Vu et al. (Rückgriff in Wang 2015 genannt), Rothermel et al. 2020 (https://arxiv.org/abs/2005.04777).
- 2D-Linien aus den Bildern auf das Netz zurückprojizieren, nur diese Kantenketten gerade zwingen, Rest bleibt glatt (Gebäude): Wang et al. TVCG 2015 (https://jingluw.github.io/papers/tvcg2015_building.pdf).
- 3D-Linien aus mehreren Bildern: Line3D++ (Standard), LIMAP (CVPR 2023, nutzt SfM-Punkte; https://www.arxiv.org/pdf/2303.17504); Gebäudekanten + Manhattan-Regularisierung (Adjazenz/Kollinearität/Orthogonalität).
- Ebenen schneiden und Flächen wählen (watertight, scharfe Kanten): PolyFit (ICCV 2017, https://3d.bk.tudelft.nl/liangliang/publications/2017/polyfit/polyfit.html), Kinetic Shape Reconstruction; empfindlich gegen Rauschen und kleine Wände.
- Gebäude hierarchisch grob->fein als Programm anpassen: Procedural Abstraction (arXiv 2501.17044), Nishida et al. 2018; Grammatiken (Müller, Martinović/Van Gool); keine fertige Kombination mit Kantenvergleich + CMA-ES gefunden.
Offen/UNGEPRÜFT: Lizenzen (LIMAP, Line3D++, CGAL-PolyFit GPL) vor dem Verkauf prüfen -> modelle/LIZENZ_WERKZEUGE.md; Genauigkeitszahlen der Verfahren (keine quantitativen Vergleiche gefunden).

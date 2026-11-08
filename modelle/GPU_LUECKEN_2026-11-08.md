# GPU-Luecken (Suche 8.11., Nutzerauftrag) - nach Code-Durchsicht, Laufzeiten NOCH NICHT gemessen

Methode: `grep` nach `cKDTree|KDTree|NearestNeighbors|sample_surface|cv2.*` in tools/*.py ohne torch/cuda-Bezug; danach die heissen Zeilen gelesen.
Vor jeder Portierung Mikro-Benchmark (Regel: Messen statt Raten; torch.cdist war 24x langsamer als knn_points). Bausteine: `tools/gpu_knn.py` (`min_abstand`), PyTorch3D `knn_points(K=k)` / `ball_query`.

## A. Grosser Gewinn erwartet (NN in Schleifen oder auf Millionen Punkten, nur CPU)
| Werkzeug | Stelle | GPU-Ersatz |
|---|---|---|
| `generator_elemente_schleife.py` | KD-Baum je Bewertung (Z. 77-83, 210) | `min_abstand`, Probenpunkte einmal auf GPU halten |
| `element_einpassen.py` | 14 KD-Verwendungen, Kandidatenschleife, Chamfer beidseitig (Z. 57-121) | Chamfer per knn_points, Kandidaten gebuendelt |
| `wolke_streiffilter.py`, `wolke_mincut.py`, `wolke_kennzahlen.py` | kNN k=16/Dichte ueber ganze Wolke (Mio. Punkte) | `knn_points(K=k)` blockweise |
| `wolke_umgebung.py` | kNN-Ausreisserfilter + Probenabgleich Mesh | knn_points |
| `wolke_carving.py` | Haut-Samples vs Wolke (Z. 150, 244) | min_abstand |
| `video_merge.py`, `sfm_lod2_ausrichten.py`, `sfm_lod2_buendel.py` | ICP-/Bodenabgleich, Iterationen mit KD-Query | ICP komplett auf GPU (knn je Iteration) |
| `textur_projektion.py` | k=4 Normalenabgleich 1,5 Mio. Chunks (Z. 200-203) | knn_points(K=4) |
| `dach_wolke_fit.py`, `rumpf_wolke_messen.py`, `wolke_abstand_einseitig.py` | Abstand Wolke<->Netz | `min_abstand` (Einzeiler) |
| `param_wolke_fit.py` (Rest) | `trimesh.sample_surface` CPU je Auswertung (~0,3 s von ~1 s) | Oberflaechenproben auf GPU (Flaechen-gewichtet, torch.multinomial) |
| `modell_ansehen.py` (neu) | Python-Schleife je Dreieck (~10 s je Ansicht) | PyTorch3D Rasterizer |

## B. Mittel (cv2/scipy auf CPU, Bilder)
`foto_kalibrieren.py`, `foto_auto_pose.py`, `fehlteile_finden.py`, `fassade_messen*.py`, `element_vergleich.py`, `arch_profile.py`, `dach_aus_luftbild.py`: cv2.Canny/distanceTransform/remap/warp ohne CUDA.
Ersatz: Distanztransformation und Warps in torch (foto_diff.py macht das schon, Bausteine dort wiederverwenden); Canny: kornia oder eigene Torch-Sobel+NMS. cv2.cuda ist im venv nicht gebaut (pruefen).

## C. Nicht auf GPU portierbar / schon GPU (nur dokumentiert)
- Manifold-Boolesche Operationen im Generatorbau (CPU, Kerne parallel nutzen: `--kerne`).
- OpenMVS ReconstructMesh/Poisson/Refine-Netz: CPU (Delaunay/GraphCut). DensifyPointCloud: CUDA, laeuft.
- COLMAP: SIFT/Matching GPU; Mapper CPU (GLOMAP/`ba_use_gpu` siehe Memory `colmap-gpu-nutzen`).
- foto_diff.py, kanten_feld3d.py, gs_kaufhaus_train*.py, param_wolke_fit.py (KNN): GPU.

## Vorschlag Reihenfolge
1. `min_abstand`-Einzeiler (dach_wolke_fit, rumpf_wolke_messen, wolke_abstand_einseitig, wolke_carving) - Minuten je Werkzeug.
2. `generator_elemente_schleife` + `element_einpassen` (laufen in Schleifen, hier gewinnt man Stunden).
3. kNN-Filter (streiffilter/mincut/kennzahlen/umgebung).
4. `modell_ansehen` Rasterizer und GPU-Sampling im Fit.
5. Bildwerkzeuge B nur nach Laufzeitmessung (aufwand_log.py).

## Stand der Umsetzung (8.11., laufend ergaenzen)
ERLEDIGT + bewiesen (CPU == GPU, `tools/test_gpu_knn.py` Exit 0; Ende-zu-Ende identisch):
- `tools/gpu_knn.py` (`min_abstand`, `naechster`, `ball_anzahl` gedeckelt) - Test auf Zufall + Kaufhaus-Wolke, Index zu 100 % gleich.
- `param_wolke_fit.py`, `modell_wolke_abstand.py`, `teile_abstand.py` (neu geschrieben, direkt GPU).
- `dach_wolke_fit.py`: J und alle 8 Parameter identisch, 2,4x schneller. `rumpf_wolke_messen.py`: Ausgabe identisch.
- `wolke_abstand_einseitig.py` (nur Abstandsteil; Dichte-Ball bleibt CPU), `wolke_carving.haut_anlegen` (naechster + ball_anzahl, kmax=max(min_pkt,8)): Syntax OK, NICHT Ende-zu-Ende verglichen (braucht Objektdaten).
OFFEN: generator_elemente_schleife, element_einpassen, kNN-Filter (streiffilter/mincut/kennzahlen/umgebung), textur_projektion, ICP (video_merge, sfm_lod2_*), lod2_klassifizieren (query_ball_point-Schleife), modell_ansehen-Rasterizer, GPU-Sampling im Fit.
REGRESSION (Regel 8b): `tools/regression.py modelle/martinstor/objekt.json --pruefen` bricht an fehlender Zwischendatei ab (/media/oem/scan/tmp/mt_dom/mt_win.npy, Schritt wolke_profile.py) - unabhaengig von dieser Aenderung; nicht gruen, nicht behoben.
- `modell_ansehen.py`: GPU-Rasterizer (PyTorch3D rasterize_meshes, Tiefenpuffer) ist Standard, `gpu=False` = alter Painter (`modell_ansehen_cpu.py`). Bild verglichen: GPU sauberer (keine Painter-Streifen/Artefakte in Boegen). Zeitgewinn KEINER (CPU-Painter 1,3 s, die 10-s-Schaetzung war falsch) - Gewinn = Korrektheit.
- `param_wolke_fit.py`: Oberflaechen-Sampling auf GPU (`probe_gpu`, multinomial + Schwerpunktkoord.). Statistik gleich (Median 0,156 vs 0,158, Mittel 0,412 vs 0,414, Aufwaerts-Anteil 0,189 vs 0,192; andere Zufallsziehung, daher keine Bitgleichheit). Fit-Kurzlauf OK, GPU 65 %.
- element_einpassen.py: Durchsicht (8.11.): die KD-Baeume arbeiten auf 2D-Profil-/Kantenpunkten (Kurven mit 150 Punkten gegen ~10^4 Kantenpunkte). Bei so kleinen Mengen schlaegt der KD-Baum voraussichtlich die GPU (Startkosten). NICHT portieren, bevor mit aufwand_log.py gemessen ist, dass die Schleife ueberhaupt dominiert.
- wolke_streiffilter.py: kNN (knn_points K=20) + Normale per geschlossener 3x3-Eigenvektor-Formel auf GPU (torch.linalg.eigh batched = 101 GiB OOM). Beweis: 320k-Teilwolke kaufhaus_grob, behaltene Punkte bitgleich zur CPU (320227). 6,8 s -> 4,8 s (Startkosten dominieren; Gewinn waechst mit Punktzahl). Baustein kleinster_ev wiederverwendbar fuer wolke_kennzahlen/mincut.

### Portierung 4 kNN-Werkzeuge (8.11., Teilmenge/Original-Wolke wolke_netzrahmen.npy 961k Pkt; Rohdaten /media/oem/scan/tmp/t_*.py)
Ehrliches Fazit: Ergebnisse GPU == CPU, ABER bei diesen Groessen ist die GPU meist NICHT schneller (cKDTree mit workers=-1 ist auf 24 Kernen stark; knn_points ist Brute Force, Startkosten ~3-5 s). Einzig Normalenschaetzung (mincut) gewinnt.
- `wolke_kennzahlen.py`: `isoliert` (kNN k=8) und `rauheit` (Nachbarn im Radius per knn_points K=256 + Radiusmaske; wird K irgendwo voll -> CPU-Rueckfall) auf GPU, Parameter `gpu=` (False = alter Weg). Beweis: isoliert 97246 von 961k Punkten, Maske bitgleich (0 Abweichungen, auch 320k-Teilmenge 34923); rauheit (p50, p90) = (4,25; 6,54) cm identisch. Zeit 961k: isoliert CPU 0,9-1,3 s vs GPU 4,3-6,2 s; rauheit 2,4 s vs 3,8 s -> GPU LANGSAMER (Eigenwerte bleiben numpy). Status: portiert+bewiesen, kein Zeitgewinn; Default bleibt GPU (Nutzerregel), `gpu=False` fuer Schnelllauf.
- `wolke_mincut.py`: kNN k=16 + Normalen (erledigt jetzt `normalen()`, GPU = knn_points + geschlossene 3x3-Formel wie streiffilter; `--cpu` = Original). Beweis Normalen 120k Anfragen: |cos| Median 1,00000000, P1 1,000000, ein Ausreisser 0,9983 (Gleichstand der k-ten Nachbarn). Ende-zu-Ende: erzeugter STL bitgleich (md5 gleich, GPU vs `--cpu`). Normalen 1,6 s -> 0,32 s (warm); Gesamtlauf 13,9 s GPU vs 8,4 s CPU (Torch-Import/CUDA-Start dominiert, Rest ist Manifold/Voxel CPU). Status: portiert+bewiesen.
- `wolke_umgebung.py`: Probenabgleich Mesh (`rauschen_messen`: naechster Probenpunkt per gpu_knn.naechster) und Ausreisser-kNN k=10 (`umgebungsmaske`) auf GPU, Schalter Modulvariable `GPU` / `--cpu`. Beweis auf kaufhaus_grob_1-87.stl + 500k-Wolke bei gleichem r: Behaltmaske 0 Abweichungen von 500000, `info` identisch, Rauschen `klassen` max. 1 Punkt Unterschied (Gleichstand beim naechsten Probenpunkt, Summe 315300 = 315300). Zeit: rauschen 0,7 s CPU vs 1,2 s GPU, umgebung 0,8 s vs 1,1 s -> GPU langsamer. Der Lauf von 7 min besteht fast nur aus `Modell.res` (generator), nicht aus kNN. FALLE: `generator_elemente_schleife` setzt `CUDA_VISIBLE_DEVICES=""` (setdefault) beim Import; `main()` setzt jetzt vorher "0", wenn GPU an. ACHTUNG: dadurch rechnet auch `Modell.res` auf GPU und `profil_aussen/innen` weichen zum CPU-Lauf ab (andere Zahlen in r, kein kNN-Effekt); Vergleich nur bei gleichem r aussagekraeftig (so gemessen). Status: portiert+bewiesen, kein Zeitgewinn.
- `textur_projektion.py`: kNN-Block in `fotowahl_dreieck()` ausgelagert (CPU-Pfad logisch unveraendert, 3 Mio. Texel 2,6-3,5 s). GPU-Variante vorhanden, aber NICHT Standard (`TEXTUR_KNN_GPU=1`): Brute Force, 1,5 Mio. Anfragen gegen 20k/100k/500k/1M Dreiecke: CPU 0,11/0,14/0,23/0,42 s vs GPU 0,23/0,70/3,5/7,0 s. Gleichheit: Abstaende gleich bis 1,4e-5 (float32-Epsilon), Indizes nur bei Gleichstand verschieden (92,3 % identische Fotowahl auf synthetischen, regelmaessig unterteilten Dreiecken mit 2,7 Mio. Flaechen, sonst keine Abweichung) -> NICHT bitgleich, daher Originalverhalten (CPU) als Standard behalten. Status: portiert (opt-in), bewiesen nur als aehnlich, empfohlen: CPU lassen. Besser waere ein GPU-Gitter/BVH statt Brute Force.
Lehre: vor weiteren kNN-Portierungen Dreiecks-/Punktzahl der Referenzmenge messen; knn_points lohnt nur bei kleiner Referenzmenge (< ~50k) oder sehr grossem Anfragenverhaeltnis, nicht bei 10^5-10^6 Referenzpunkten.

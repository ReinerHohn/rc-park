# Scan → H0-Druckmodell (Struktur, keine Textur)

Stand 2026-10-31, GPU-PC (RTX 4060 Laptop). Ziel: aus einem beliebigen Objekt mit allen verfügbaren Daten ein druckbares
H0-Modell (1:87) erzeugen. Dieses Dokument beschreibt die **Scan-Methode**; die Daten-Methode (LOD2 + Laser + Foto)
steht in `METHODE_GEBAEUDE_3D.md` und liefert bisher die saubereren Modelle.

## Pipeline

```
Video/Fotos → COLMAP/OpenMVS (scan-setup/GPU-PIPELINE.md) → Zuschnitt-Mesh (zuschnitt.ply)
  → tools/scan_zu_koerper.py   (Schichtkörper, Meter)
  → tools/h0_druckfertig.py    (Maßstab 1:87, Voxel-Remesh, Prüfung, Teile)
  → modelle/scan_koerper/*.stl
```

### 1. `tools/scan_zu_koerper.py` — Mesh/Punktwolke → geschlossener Schichtkörper
Schneidet das Objekt waagerecht in Schichten (Standard 0,5 m), misst je Schicht den Grundriss
(Dichte → Kontur → vereinfachtes Polygon) und stapelt die Schichten zu einem Körper. Von oben nach unten.

Aufruf (Martinstor, so erzeugt):
```
/media/oem/scan/venv-seg/bin/python -I tools/scan_zu_koerper.py \
  /media/oem/scan/colmap-test/martinstor-gpuba/openmvs/zuschnitt.ply modelle/scan_koerper/martinstor_scan.stl \
  --hoehe-m 45.9 --box -1.5 1.6 -0.7 4.2 2.0 4.6 \
  --aufrecht /media/oem/scan/analyse/R.npy /media/oem/scan/analyse/mu.npy
```
`--aufrecht` = Rotation + Mittelpunkt aus der Wandebenen-Analyse (RANSAC, siehe Memory „goal-h0-modell-aus-daten“).
Nicht aus den Kameras ableiten (22° daneben).

**Änderungen vom 2026-10-31** (Ursache: erster Körper war ein Stapel loser Streifen, 24 Teile, nicht wasserdicht):
| Problem | Ursache | Korrektur |
|---|---|---|
| Lücken zwischen Eckpunkten | Es wurden nur Mesh-**Eckpunkte** gezählt | Mesh-Fläche dicht abtasten (`lade_punkte`) |
| Schichten fehlen komplett | Schichten mit < 50 Punkten wurden still übersprungen | Umriss der Schicht darüber übernehmen |
| Falscher Block gewählt | Block „an der Achse“; die Achse liegt im Torbogen | Der Schicht darüber folgen (größte Überlappung mit aufgeweitetem Umriss, `--wachstum-m`) – wie im Docstring versprochen |
| Untere Schichten fast leer (1–9 m² statt ~50) | Löcher im Scan unter ~18 m | `--stuetzen 0.5`: Schicht mit < 50 % der Fläche darüber → Umriss darüber durchziehen. Im Bericht als `gestuetzt` gezählt |
| Schicht fehlt im Körper | `extrude_polygon` scheiterte still bei ungültigem Umriss | größtes Teilstück bzw. konvexe Hülle; Warnung bei verworfenen Schichten |
| Union nicht verbunden | Schichten stießen nur aneinander | 2 cm Überlappung |

### 2. `tools/h0_druckfertig.py` — Körper → H0-STL
```
/media/oem/scan/venv-seg/bin/python -I tools/h0_druckfertig.py modelle/scan_koerper/martinstor_scan.stl \
  modelle/scan_koerper/martinstor_scan_h0.stl --hoehe-m 45.9 --up z --min-anteil 0.02 --solid 0.8 --teilen
```
- `--min-anteil 0.02` wirft Splitter raus (der Körper hatte 2-Flächen-Reste).
- `--solid 0.8` Voxel-Remesh (0,8 mm) macht wasserdicht und glättet. Es behält nur den **größten** Block – ein Spalt im Körper
  halbiert deshalb das Modell (so war es bei `m4`: 285 mm statt 527 mm).
- `--teilen` schneidet in Teile, die in den Bauraum (220×220×250 mm) passen.

**Bug behoben (`voxel_solid`)**: `trimesh` liefert beim Marching Cubes in dieser Version Voxel-Indizes ohne Pitch/Ursprung.
Das Modell war dadurch um den Faktor 1/Pitch zu groß (0,8 → 1,25×: 658 statt 527 mm). Jetzt wird `v.transform`
angewendet. Alte Ergebnisse, die mit `--solid` erzeugt wurden, sind falsch skaliert und müssen neu gerechnet werden.

Voraussetzung: `scikit-image` im venv (`pip install scikit-image` in `/media/oem/scan/venv-seg`, Cache `/media/oem/scan/pipcache`).

## Ergebnis Martinstor (Scan) — Stand heute

| | Daten-Modell `modelle/h0/martinstor_h0.stl` | Scan-Modell `modelle/scan_koerper/martinstor_scan_h0.stl` |
|---|---|---|
| Höhe | 527,6 mm | 526,5 mm |
| Grundfläche | 115 × 115 mm (quadratischer Schaft) | 161 × 111 mm (breiter, tiefer Sockel, Schaft schmaler) |
| wasserdicht | ja | ja |
| Teile (Bauraum) | 3 | 3 |
| Wand p5 | 1,7 mm (1,6 % dünner als 0,8 mm) | 9,5 mm (0 % dünn) |
| Details | Bogen, 4 Eck-Türmchen, Helm (glatt) | nur die Hüllform; kein Torbogen, Türmchen verwaschen |

### Was ehrlich gilt
- **Das Scan-Modell ist eine Hüllform, kein Detailmodell** (Sockelbreite siehe „Offene Widersprüche“). Der Scan liefert den Umriss (Sockel breiter als Schaft, Helm), aber
  der Körper ist massiv: kein Durchgang, keine Türmchen. Die Außenfläche ist durch Scanrauschen unruhig.
- **Der untere Teil ist angenommen.** Unter etwa 18 m hat der Scan Löcher; 40 von 89 Schichten (`gestuetzt` im Bericht) sind
  durchgezogene Umrisse, kein Messwert. Es gibt keinen Torbogen.
- **Höhe**: der Körper war 44,5 m statt 45,9 m (dünne Spitze fällt unter die Mindestpunktzahl). `h0_druckfertig --hoehe-m` streckt
  deshalb alles um ~3 % auf 45,9 m.
- Das Daten-Modell ist formal sauberer, aber ein generischer Turm; ob es dem echten Martinstor gleicht, wurde nur anhand von
  Maßen geprüft. Vergleich Scan/Daten ist nur als Silhouette gemacht worden.

### Vergleich mit dem Detailmodell (Ergebnis des Tages)
Im Repo gibt es schon `modelle/martinstor_detail_gen.py` (CSG nach OSM-Maßen + Fotos: Rundbogentor mit Keilsteinen, Sandstein-Eckquader,
Gurtgesims, Fenster, Uhr, Walmdach mit Gauben, Laterne, 4 Ecktürmchen auf Konsolen). Auf H0 gerechnet:
```
cd modelle && SCALE=87 MINMM=0.8 ~/.venvs/rcpark/bin/python martinstor_detail_gen.py      # -> modelle/stl/martinstor_detail_1-87.stl
cd .. && /media/oem/scan/venv-seg/bin/python -I tools/h0_druckfertig.py modelle/stl/martinstor_detail_1-87.stl \
      modelle/h0/martinstor_detail_h0.stl --hoehe-m 54.0 --up z --teilen
```
| | Detailmodell `modelle/h0/martinstor_detail_h0.stl` |
|---|---|
| Ausdehnung | 186 × 194 × 621 mm (≈ 54 m × 16,2 m × 16,9 m im Original) |
| wasserdicht | ja (19 084 Flächen, Genus 0) |
| Teile | 3 (je ≈ 207 mm hoch), alle wasserdicht, passen in 220×220×250 |
| Wand p5 | 4,6 mm; 1,3 % dünner als 0,8 mm |
| Sichtprüfung (Silhouette vorn/seitlich) | Walmdach, Gaube, Knauf, 4 Ecktürmchen, Rundbogentor erkennbar |

**Entscheidung:** Das Detailmodell ist das H0-Modell. Die Scan-Hülle bleibt als Datenquelle für Proportionen, nicht als Druckmodell.

**Hybrid (nicht übernommen):** `tools/helm_aus_scan.py` setzt einen Helm aus gemessenen Scan-Breiten auf den Generator-Schaft.
Das Ergebnis sah schlechter aus (Glocke auf Block, Ecktürmchen-Stümpfe). Das Werkzeug bleibt als Experiment im Repo.

### Offene Widersprüche (nicht gelöst, bitte prüfen)
- **Höhe (Recherche 31.10.):** Angaben schwanken je nach Quelle: 60 m (Wikipedia-Infobox, Reiseführer), 63 m (ADAC), 65 m (Structurae,
  bauforschung-bw.de), 66 m (Schwarzwaldportal). Das Tor wurde 1901 (Carl Schäfer) von 22 m auf diese Höhe aufgestockt.
  Dagegen: OSM-Detailmodell 54 m, LOD2 45,3 m (nur Teilgebäude), Scan 45,9 m (reine Annahme). **Wahrscheinlich ≈ 65 m.**
  Dann sind das Detailmodell ca. 17 % und die Scan-Maße ca. 30 % zu klein.
  Variante (nur gleichmäßig hochskaliert, Proportionen ungeprüft): `modelle/h0/martinstor_detail_65m_h0.stl`, 747 mm hoch,
  224 × 234 mm Grundfläche, wasserdicht, 18 Teile. Standard bleibt das 54-m-Modell, bis die Proportionen (Schaftbreite/Traufhöhe) belegt sind.
- **Grundfläche:** Structurae nennt 10 × 11 m am Fuß; OSM-Part 13,4 × 12,7 m (`martinstor_detail_gen.py`: D, W); LOD2-Footprint ~9 m
  (`bauwerke/martinstor.json`). Möglich, dass OSM den breiteren Steinsockel meint (Foto: Sockel aus Bruchstein ist breiter als der verputzte Schaft).
  Scan-Seitenverhältnis (Höhe / oberer Schaft) ≈ 4,9, unabhängig vom Maßstab gemessen. Mit Schaft 13 m ergäbe das ≈ 65 m,
  mit Schaft 10–11 m ≈ 50 m. Die Maße D, W, EAVE, ROOF_TOP, TOP, TW/T0/T1/TTOP sind im Generator fest (oben in der Datei) und
  können dort direkt angepasst werden, sobald ein belastbares Maß vorliegt (Vermessung/Bauplan; bauforschung-bw.de-PDF).
- **Foto-Abgleich:** `modelle/martinstor_gen/mt_vergleich.jpg` (Foto vs. altes parametrisches Modell v2). Das Detailmodell passt strukturell zum Foto
  (Walmdach, 4 Ecktürmchen auf Konsolen, Knauf, Rundbogentor); v2 ist deutlich schlechter. Perspektive im Foto erlaubt keine Höhenmessung.
- **Schaftbreite:** OSM 13,4 × 12,7 m; der Scan zeigt unten 13,6 m. Das widerspricht meiner früheren Aussage, die breite Basis seien
  „Nachbarn“: Sie entspricht eher dem echten Schaft. Die 9 m des Generator-Modells (`bauwerke/martinstor.json`, LOD2-Footprint)
  sind wahrscheinlich zu schmal (Datei vermerkt selbst „FLAG“).
- Entscheidung braucht eine verlässliche Höhenangabe (Vermessung, Foto mit Referenz, amtliche Angabe).

### Nächste Schritte
1. Höhe klären (s. o.); danach Scan-Skalierung und `bauwerke/martinstor.json` anpassen.
2. Detailmodell mit Slicer prüfen (Resin 0,4 mm / FDM 0,8 mm Mindestwand; 1,3 % dünne Stellen sind vermutlich Reliefs/Zinnen).
3. Methode auf weitere Objekte anwenden: erst Daten-Methode (OSM + Foto), Scan nur für Proportionen.
4. RAM auf 64 GB aufrüsten, dann RefineMesh mit allen 3,1 Mio. Flächen.

## Objekt-Abdeckung (Stand 31.10.)
Gleiche Prüfkette (`h0_druckfertig.py`: Maßstab 1:87, wasserdicht, Wandstärke, Bauraum, Teile) für drei Objekttypen:
| Objekt | Typ | Ausdehnung mm | wasserdicht | Teile | Wand dünn |
|---|---|---|---|---|---|
| Hofgut Sternen | Gebäude (LOD2+Laser+Foto) | 486 × 176 × 107 | ja | 3 | 1,0 % |
| Ravenna-Viadukt | Brücke (Generator) | 2429 × 793 × 539 | ja | 40 | 6,2 % |
| Martinstor | Torturm (OSM+Foto, CSG) | 186 × 194 × 621 | ja | 3 | 1,3 % |
| Kaufhaus Freiburg | Detailmodell (47 Teile) | – | – | – | `kaufhaus_h0.log` leer, kein Lauf: offen |
Scan als Datenquelle (Martinstor) ist nur für Hüllform/Proportionen brauchbar; die druckbaren Modelle kommen aus Daten-Methoden.

## GPU-Absturz vom 2026-10-31 (Hintergrund)
Meldung „nvidia-modeset: Error while waiting for GPU progress“: Folge eines Absturzes beim **Aufwachen aus dem Standby (s2idle)**:
Xid 120 (GSP-Firmware-Fehler) → `gpuPowerManagementResume: GSP boot failed` → Xid 154 „GPU Reset Required“ → Xorg SIGABRT.
Treiber 595.91.07 (nvidia-open), Kernel 6.17.0-1032-oem. `PreserveVideoMemoryAllocations=1` und die nvidia-suspend/resume-Dienste
sind schon aktiv und haben es nicht verhindert. Mögliche Gegenmaßnahmen: Standby nicht benutzen, `mem_sleep_default=deep`
(ungetestet) oder anderer Treiber. Vorher am 30.10. 17:27: `RefineMesh` Xid 31 (MMU Fault) – wahrscheinlich RAM/VRAM-Engpass bei 3,1 Mio. Flächen.

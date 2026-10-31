# Pipeline: beliebiges Objekt → druckfertiges H0-Modell (1:87)

Stand 2026-10-31. Ziel: aus **allen verfügbaren Daten** ein gutes, realistisches Druckmodell für die Modelleisenbahn H0 erzeugen.
Nur **Struktur**, keine Textur. Diese Datei ist der Einstieg; Details zur Scan-Methode stehen in `METHODE_SCAN_ZU_H0.md`,
zur Daten-Methode in `METHODE_GEBAEUDE_3D.md` / `METHODE_3D_AUS_ALLEN_DATEN.md`.

## 1. Der Weg in einem Bild

```
                      ┌─ A. Daten-Methode (bisher die besten Modelle) ──────────────────────────┐
 Objekt ──► Daten ────┤   OSM / LOD2 (amtlich) / Laser / Fotos → parametrischer CSG-Generator   │──► Modell (m oder mm)
                      │   z. B. modelle/martinstor_detail_gen.py, tools/hofgut_sternen.py        │
                      ├─ B. Scan-Methode (nur Hülle/Proportionen) ──────────────────────────────┤
                      │   Video/Fotos → COLMAP+OpenMVS (GPU) → Zuschnitt-Mesh                    │
                      │   → tools/scan_zu_koerper.py (Schichtkörper)                             │
                      └──────────────────────────────────────────────────────────────────────────┘
 Modell ──► tools/h0_druckfertig.py ──► Maßstab 1:87 · aufräumen · (Voxel) · Wandstärke · Bauraum · Teile ──► modelle/h0/*.stl
 STL ───► tools/viewer_bauen.py ───► eine 3D-HTML zum Anschauen (three.js)
```

Faustregel aus den Ergebnissen: **Daten-Methode für das Druckmodell, Scan nur zur Kontrolle von Proportionen.**
Ein Foto-Scan liefert Rauschen, Löcher und Nachbargebäude; ein Generator mit amtlichen Maßen liefert saubere Wände, Tore, Dächer.

## 2. Werkzeuge (Referenz)

| Werkzeug | Aufgabe | Eingabe → Ausgabe |
|---|---|---|
| `modelle/martinstor_v4_gen.py` | **aktuell** (54 m, Verhältnisse nach Foto, Eintrag 6); `martinstor_v3_gen.py` = Vorgänger 45,3 m | s. v3 | s. v3 |
| `modelle/martinstor_v3_gen.py` | Vorgänger: Martinstor nach Fotos (verjüngter Rumpf, Glockenstock, Erker, Bruchstein, Falze), Höhe 45,3 m; Herleitung der Maße in `LERNJOURNAL_MARTINSTOR.md` | Konstanten oben (`H_TOTAL, DB, WB, ZB, D, W, ZZ`), `SCALE`, `MINMM` → `modelle/stl/martinstor_v3_1-<SCALE>.stl` |
| `modelle/martinstor_detail_gen.py` (v2) | CSG-Detailmodell Martinstor (manifold3d): Rundbogentor, Keilsteine, Eckquader, Gesimse, Fenster, Uhr, Walmdach, Gauben, 4 Ecktürmchen | Maße im Kopf der Datei (`D, W, EAVE, TOP, TW…`), `SCALE`, `MINMM` → `modelle/stl/martinstor_detail_1-<SCALE>.stl` |
| `tools/bauwerk_generator.py` + `bauwerke/*.json` | parametrischer Gebäudetyp (Turm, Helm, Durchfahrt) | JSON → GLB |
| `tools/scan_zu_koerper.py` | Mesh/Punktwolke → geschlossener **Schichtkörper** (Meter) | PLY + Box + Aufrichtung → STL |
| `tools/h0_druckfertig.py` | Maßstab, Aufräumen, Voxel-Remesh, Wasserdichtigkeit, Wandstärke, Bauraum, Teilen | GLB/STL/PLY → STL (mm) + `.bericht.json` |
| `tools/helm_aus_scan.py` | Experiment: Helm aus Scan-Breiten auf Generator-Schaft | (nicht übernommen, schlechter) |
| `tools/viewer_bauen.py` + `tools/viewer_vorlage.html` | STL → eine selbstenthaltene 3D-HTML | STL-Liste im Skript → `modelle/h0/viewer.html` |

Python-Umgebung für alles Mesh-/ML-Zeug: `/media/oem/scan/venv-seg/bin/python -I` (trimesh, scikit-image, pymeshfix, shapely, manifold3d, cv2).
Der CSG-Generator läuft mit `~/.venvs/rcpark/bin/python`.

### 2.1 `h0_druckfertig.py` — die Prüfkette
```
python -I tools/h0_druckfertig.py EINGABE AUSGABE.stl --hoehe-m <echte Höhe> --up z [--solid <Voxel mm>] [--min-anteil 0.02] [--teilen]
```
Ablauf im Code (`main`):
1. `lade()` – GLB/STL/PLY, alle Teile zu einem Mesh.
2. Achsen drehen (`--up`), Optionaler Zuschnitt (`--crop`).
3. `aufraeumen()` – Eckpunkte verschmelzen, Entartete/Doppelte raus, Kleinteile weg (`--min-anteil`: Anteil der größten Fläche).
4. Maßstab: `m_mm = m * (hoehe_m / Höhe) * 1000 / 87`. **`--hoehe-m` ist die echte Objekthöhe und legt den Maßstab fest.**
5. optional `voxel_solid()` (`--solid`): Voxel → innen füllen → Schließen/Öffnen → größte Komponente → Marching Cubes → Taubin-Glättung.
   Macht Scans massiv und wasserdicht, behält aber **nur den größten Block**.
6. `wasserdicht()` – Reparatur je Komponente (pymeshfix); danach Schutzprüfung: Ausdehnung darf sich nicht um > 2 % ändern.
7. `wandstaerke()` – Strahlen von der Oberfläche nach innen (4000 Proben): p5, Median, Anteil < `--min-wand` (0,8 mm FDM).
8. `--teilen` → `in_stuecke()` schneidet in Quader, die in den Bauraum (Standard 220×220×250 mm) passen, je Teil eine STL.
9. Bericht `<ausgabe>.bericht.json`; Exit-Code 2, wenn nicht wasserdicht oder Bauraum überschritten.

### 2.2 `scan_zu_koerper.py` — Schichtkörper aus dem Scan
Details und Tabelle der Korrekturen: `METHODE_SCAN_ZU_H0.md`. Kurz: Mesh-Fläche dicht abtasten → Schichten von oben nach unten →
je Schicht Dichtekarte → Kontur → Polygon; der Schicht darüber folgen (größte Überlappung); Scan-Löcher durch den Umriss darüber
überbrücken (`--stuetzen`, im Bericht als `gestuetzt` gezählt); Schichten mit 2 cm Überlappung extrudieren und per Manifold vereinigen.

### 2.3 `viewer_bauen.py` — 3D-Seite
Liest die in `tools/viewer_bauen.py` eingetragenen STLs, schreibt sie als base64 in `tools/viewer_vorlage.html` (three.js r128 über jsDelivr,
OrbitControls, STLLoader), Funktionen: Auswahl, Drehen/Zoomen, Gitteransicht, H0-Figur (20,7 mm), Datenblatt (Maße in mm und Original, Flächen,
Wasserdichtigkeit, Teile, Status), hell/dunkel. Aufruf: `python tools/viewer_bauen.py [ausgabe.html]`. Veröffentlicht wurde sie als privates Artifact.

### 2.4 Mass-Optimierung mit GPU (`hypso_gpu.py`, `generator_optimierer.py`, `optimierung_validieren.py`)
**Die GPU ist fester Teil der Pipeline** (Schritt "Masse gegen Laser pruefen/optimieren"), mit CPU-Rueckfall (`--cpu`).
- `tools/hypso_gpu.py`: Hoehenkarten des Modells fuer 2106 Drehungen/Raster-Phasen gleichzeitig (PyTorch `scatter_reduce(amax)`, float64), je Hoehenstufe Flaeche > t gegen das amtliche DOM. **Selbsttest** `--selbsttest`: GPU == CPU bit-gleich (Hoehenkarten und Fehler), Messung: 275 Kombinationen CPU 2,4 s / GPU 0,5 s; feines Raster 1,8 s gesamt.
- `tools/generator_optimierer.py`: Koordinatensuche ueber 16 Generatormasse (+Mehrfachstart mit festen Seeds). **Annahmeregel:** Trainingsfehler (13 Stufen) > 2 sigma besser UND zurueckgehaltene Stufen (12 andere, an der Trainingslage) nicht signifikant schlechter UND punktweise Hoehe im 4,5-m-Umkreis nicht schlechter als +0,15 m. sigma = Bootstrap der Raster-Suche. Vertrauensbereich +-2 Schritte. Protokoll mit Versionen, GPU, git-Stand: `modelle/optimierung_martinstor.json`.
- `tools/optimierung_validieren.py`: unabhaengige Pruefung zweier STL (andere Stufen, Umkreis 13 m, feines Raster, punktweise).
- **Wiederholbar:** Scatter-Max ist ordnungsunabhaengig, alle Seeds fest -> gleiche Eingabe = gleiche Zahlen (Nachweis: Lauf 3 gegen 4 Feld fuer Feld identisch; frueherer Unterschied lauf1/2 kam von parallelen Prozessen mit gemeinsamer cur.stl, behoben durch cur<PID>; siehe `OPTIMIERUNG_MARTINSTOR.md`).
- Nicht auf der GPU: Modellerzeugung (manifold3d, CPU), Netzunterteilung (trimesh, CPU). Hinweis: GPU stuerzte hier einmal nach Standby ab (Treiber-Eigenheit, siehe Speicher gpu-pc).

### 2.5 Foto-Silhouetten-Pruefung mit GPU (`foto_silhouette_gpu.py`, `foto_dachtest_gpu.py`)
Schritt "Form gegen Fotos pruefen" (unabhaengig vom Laser). GPU wie in 2.4 fester Teil, Rueckfall nur ueber Anpassung von `dev` im Skript.
- `tools/foto_silhouette_gpu.py <Foto 042|043|044> [seed] [out.png]`: 200 000 Modellpunkte je Kandidat-Kamera projiziert, 8 Kameraparameter (Abstand, Azimut, Elevation, Blickhoehe, Roll, Brennweite, Bildverschiebung), Himmelsmaske als Ziel, Kamerahoehe ~1,7 m als weiche Nebenbedingung; Zufallssuche (30 000) + Kreuzentropie. Ausgabe: IoU, Pose, Bild (rote Modellkontur).
- `tools/foto_dachtest_gpu.py`: Beispiel fuer Parametertest ueber alle Fotos (Dachfirst-Variation per z-Umrechnung der Punkte, Kamera je Variante neu angepasst, bester Start je Foto).
- **Aussagekraft:** Anpassungsrauschen 0,01-0,04 IoU, Azimut um 90 Grad mehrdeutig (Quadratturm), Abstand/Brennweite gekoppelt. Nur Unterschiede deutlich ueber dem Rauschen zaehlen. Ergebnisse: `LERNJOURNAL_MARTINSTOR.md` Eintrag 22-23, Bilder `modelle/foto_silhouette/`.
- **Nicht beweisend** fuer Einzelmasse; Fenster, Tafeln, Adler bleiben Verhaeltnismessung (+-10 %).

### 2.6 Abnahme-Pruefstand (`modell_pruefstand.py`, `martinstor_bauen.sh`) – PFLICHT nach jeder Generatoraenderung
Misst am STL feste Merkmale mit Quelle (Foto-Vollbild oder Laser): Tuermchen-Spitze/Kegelschlankheit, Dachreiter-Dicke/Knauf, Gesamthoehe,
Wasserdichtigkeit, Koerperzahl. Exit 1 bei Fehlschlag. Entstanden, weil "Tuermchen zu gedrungen" und "Mittelspitze falsch" nach einer Korrektur
unbemerkt zurueckkamen (Ursachenanalyse: `VERSUCHSREGISTER_MARTINSTOR.md` Abschnitt I). Neue Nutzerbeobachtung -> erst Pruefung (muss fehlschlagen), dann Fix.
Nachweis der Wirksamkeit: der Stand vor der Korrektur faellt mit 4 Pruefungen durch, der korrigierte besteht alle.

## 3. Rezepte

**Martinstor (aktuell v4):**
```
SCALE=87 MINMM=0.8 ~/.venvs/rcpark/bin/python modelle/martinstor_v4_gen.py   # -> modelle/stl/martinstor_v4_1-87.stl
/media/oem/scan/venv-seg/bin/python -I tools/h0_druckfertig.py modelle/stl/martinstor_v4_1-87.stl modelle/h0/martinstor_v4_h0.stl --hoehe-m 54.0 --up z --teilen
```
**Martinstor (v2, Vorgänger):**
```
cd modelle && SCALE=87 MINMM=0.8 ~/.venvs/rcpark/bin/python martinstor_detail_gen.py
cd .. && /media/oem/scan/venv-seg/bin/python -I tools/h0_druckfertig.py modelle/stl/martinstor_detail_1-87.stl \
    modelle/h0/martinstor_detail_h0.stl --hoehe-m 54.0 --up z --teilen
```
**Scan → Körper → H0:** siehe `METHODE_SCAN_ZU_H0.md` (Zuschnitt `.../openmvs/zuschnitt.ply`, Aufrichtung `R.npy`/`mu.npy`).
**Viewer:** `/media/oem/scan/venv-seg/bin/python -I tools/viewer_bauen.py`

## 4. Fehler, die gefunden und behoben wurden (nicht wiederholen)

| Datum | Fehler | Wirkung | Korrektur |
|---|---|---|---|
| 31.10. | `voxel_solid`: trimesh liefert Voxel-Indizes ohne Pitch/Ursprung | Modell um 1/Pitch zu groß (658 statt 527 mm) | `r.apply_transform(v.transform)` |
| 31.10. | `wasserdicht()`: pymeshfix auf Gesamtmesh behält nur größte Komponente | Hofgut (10 739 Teile, 128 864 Flächen) wurde still zu einer 20-Flächen-Platte, Bericht sagte „wasserdicht“ | Reparatur je Komponente + Abbruch bei > 2 % Ausdehnungsverlust |
| 31.10. | `scan_zu_koerper`: nur Mesh-Eckpunkte, Schichten still übersprungen, falscher Block | Körper aus 24 losen Streifen | Fläche abtasten, Lücken überbrücken, Schicht darüber folgen |
| 31.10. | `extrude_polygon` scheiterte still bei ungültigem Umriss | Lücke im Körper → `--solid` behielt nur die Hälfte | Teilstück/konvexe Hülle, Warnung |
| 31.10. | Bericht des Scan-Tools meldete „wasserdicht: true“, Nachprüfung widerlegte es | falsche Sicherheit | immer mit `trimesh` gegenprüfen (`is_watertight`, `split`) |

Lehre: **nie dem Bericht eines Werkzeugs trauen, ohne Flächenzahl, Ausdehnung und ein Bild zu prüfen.**

## 5. Stand der Objekte

| Objekt | Typ | Datei | mm (B × T × H) | wasserdicht | Teile | Anmerkung |
|---|---|---|---|---|---|---|
| **Martinstor v4** | Torturm (Foto-Detail, CSG, `martinstor_v4_gen.py`) | `h0/martinstor_v4_h0.stl` | 155 × 165 × 621 | ja | 3 | **Favorit** (54 m; verjüngter Rumpf, Erker, Glockenstock, Bruchstein); 0,5 % dünne Wand; Herleitung in `LERNJOURNAL_MARTINSTOR.md` Eintrag 6 |
| Martinstor v3 | wie v4, aber 45,3 m | `h0/martinstor_v3_h0.stl` | 142 × 159 × 521 | ja | 3 | überholt: gedrungen (Kopf zu klein), s. Journal Eintrag 6 |
| Martinstor Detail (v2) | Torturm (OSM+Foto, CSG) | `h0/martinstor_detail_h0.stl` | 186 × 194 × 621 | ja | 3 | Vorgänger, 54 m, falsche Proportionen (Gauben, kein Glockenstock) |
| Martinstor 65 m | Variante | `h0/martinstor_detail_65m_h0.stl` | 224 × 234 × 747 | ja | 18 | nur gleichmäßig skaliert |
| Martinstor einfach | Generator v2 | `h0/martinstor_h0.stl` | 115 × 115 × 528 | ja | 3 | grob |
| Martinstor Scan-Hülle | Scan | `scan_koerper/martinstor_scan_h0.stl` | 161 × 111 × 527 | ja | 3 | Hülle, kein Bogen, unten angenommen |
| Ravenna-Viadukt | Brücke (Generator) | `h0/ravenna_h0.stl` | 2429 × 793 × 539 | ja | 40 | 6 % dünne Wand |
| Hofgut Sternen | Gebäude (LOD2+Laser+Foto) | `h0/hofgut_h0.stl` | 486 × 297 × 225 | ja | 6 | 128 864 Flächen, 26 % dünne Wand → **`h0/hofgut_solid_h0.stl`** (`--solid 0.8 --teilen`): 486 × 182 × 226 mm, 6 Teile, wasserdicht, 0,1 % dünne Wand, 1,65 Mio. Flächen (zu groß fürs Repo/Viewer) |
| Kaufhaus Freiburg | Detailmodell (47 Teile) | `h0/kaufhaus_h0.stl` | – | – | – | Lauf mit `--solid 0.5` brach ohne Ausgabe ab (Speicher/Zeit), offen |

## 6. Offen

- **Detailschleife Martinstor:** Vorgehen, Messungen und Lehren je Schritt in `LERNJOURNAL_MARTINSTOR.md` (Einträge 0–6). Foto-Ernte: `daten/martinstor/fotos` mit Lizenz-Manifest.
  Wichtigste Methodenlehre: erst Foto neben Modell rendern und von Auge vergleichen; Zahlen (wasserdicht/Bauraum) fanden die gröbsten Fehler nicht.

- **Mehr Detail** (Wunsch 31.10.): Martinstor-Maße klären (Höhe 54/65 m, Schaft 13,4 vs. 10×11 m), dann Generator-Konstanten anpassen;
  Fassadenreliefs (Fenster, Uhr, Quader) sind bei `MINMM=0.8` sichtbar, aber bei Resin (0,15–0,4 mm) feiner möglich.
  Für Hofgut: Arkadenbögen im Sockel, Krüppelwalm exakt (siehe `hofgut_sternen/STAND.md`).
- RAM auf 64 GB, dann Scan mit allen 3,1 Mio. Flächen verfeinern.
- GPU-Absturz beim Aufwachen aus dem Standby (Xid 120/154, nvidia-open 595.91.07): Standby meiden, siehe `METHODE_SCAN_ZU_H0.md`.

# Web-Scan: 3D-Modelle aus Online-Bildern + Videos (ohne selbst hinzugehen)

> **Kern-Erkenntnis (30.10.2026, Martinstor):** Die besten Online-Daten für Photogrammetrie sind
> **keine Fotos, sondern Videos** — vor allem **Drohnen-Orbits** von YouTube. Ein 15–25-s-Clip
> liefert 50–100 scharfe Einzelbilder **aus einer Kamera, mit gleichmäßigem Versatz rundherum
> und von oben** (Dach, Türmchen, Spitze). Genau das, was zusammengewürfelte Internetfotos nie haben.

Werkzeug: [`scan-setup/webfotos.py`](scan-setup/webfotos.py) — sammelt, filtert, lädt und
startet Meshroom auf der GPU. Ein Befehl.

```bash
python3 scan-setup/webfotos.py --name Martinstor --lat 47.99345 --lon 7.84912 \
  --category "Martinstor (Freiburg im Breisgau)" --search "Martinstor Freiburg" \
  --video-search "Martinstor Freiburg aerial" --video-search "Martinstor Freiburg" --run
```

## Die ganze Pipeline (Martinstor als Beispiel)

| # | Schritt | Werkzeug | Ergebnis |
|---|---|---|---|
| 1 | Commons-Fotos sammeln + SIFT-Relevanzfilter | `webfotos.py` | `<work>/commons_fotos/`, `QUELLEN.csv` |
| 2 | Drohnen-/Bodenclips laden, Einzelbilder ziehen (3–4 fps), unscharfe + Standbilder raus | `webfotos.py --video-search …` (yt-dlp + ffmpeg) | `<work>/video_frames/<VideoID>_0001.jpg` |
| 3a | 3D: Meshroom (GPU-Extraktion erzwungen) | `webfotos.py --run` | texturiertes OBJ |
| 3b | 3D: COLMAP komplett auf CUDA (schneller, Matching auf GPU) | `scan-setup/colmap_gpu.py <work>/video_frames <ziel>` — teilt flache Ordner selbst nach Video auf | `mesh.ply`, `dense/fused.ply` |
| 4 | Maß-Gerüst aus OSM | `modelle/martinstor_osm_gen.py` | `stl/martinstor_osm.stl` |
| 5 | Druckbares Detailmodell (CSG) | `modelle/martinstor_detail_gen.py` | `stl/martinstor_detail.stl` |

`<work>` ist standardmäßig `/dev/shm/webscan/<name>` (RAM, nach Neustart weg) → Ergebnisse
sichern, oder `--work /media/oem/Volume/webscan/<name>` nehmen. GPU-Einrichtung auf neuem
Rechner: [`scan-setup/gpu-setup.sh`](scan-setup/gpu-setup.sh), Doku
[`scan-setup/GPU-PIPELINE.md`](scan-setup/GPU-PIPELINE.md).

## Was funktioniert hat / was nicht

| Quelle | Ergebnis | Warum |
|---|---|---|
| **YouTube-Drohnenclips** (4–5 Stück à 15–25 s) | ⭐ beste Quelle | Orbit = perfekter Rundum-Versatz, von oben, eine Kamera |
| YouTube-Bodenclips / Walking-Tours | gut als Ergänzung | gleiche Kamera, durchgehende Bewegung, aber nur Straßenseite |
| Wikimedia-Commons-Kategorie (~100 Fotos) | ❌ allein unbrauchbar | 19/41 ausgerichtet, aber **alle von derselben Straßenseite** → flache Platte statt Turm |
| Commons-Geosuche (Umkreis 150 m, ~500+) | Masse, viel Beifang | → **SIFT-Relevanzfilter** nötig (s. u.) |
| Openverse, Panoramax, KartaView | ❌ | Timeout / keine Abdeckung / SSL-Fehler |
| Mapillary, Flickr | optional | brauchen Token/API-Key (`MAPILLARY_TOKEN`, `FLICKR_KEY`) |

## Die Hebel (alle im Modul eingebaut)

1. **Video-Frames statt Fotos:** `yt-dlp` + `ffmpeg` (3–4 fps), unscharfe Frames raus
   (Laplace-Varianz < 50 % vom 60.-Perzentil), Standbilder raus (Bilddifferenz).
2. **Jedes Video = eigene Kamera:** Frames haben kein EXIF → Meshroom würde alle Videos als
   *eine* Kamera kalibrieren. Lösung: EXIF `Make=YouTube`, `Model=<Video-ID>` schreiben.
3. **GPU wirklich nutzen:** Meshroom 2023.3 rechnet die Feature-Extraktion **standardmäßig auf
   der CPU** (`forceCpuExtraction=True`)! → `FeatureExtraction:forceCpuExtraction=False` +
   `describerTypes=sift` (PopSift, GPU). Effekt: Sekunden statt ~3 min pro Bild (AKAZE/CPU).
4. **Matching passend zur Menge:** < 300 Bilder `Exhaustive` (jedes mit jedem, gut für
   Internetfotos); bei Video-Mengen `SequentialAndVocabularyTree` (Zeitnachbarn + Wiedererkennung).
5. **Volle Auflösung auf der GPU:** `DepthMap:downscale=1`, `Texturing:downscale=1`,
   `Meshing:maxPoints=15000000`.
6. **Relevanzfilter (28 CPU-Threads):** 500-px-Vorschau laden, SIFT + RANSAC-Fundamentalmatrix
   gegen Referenzfotos (Kategorie) → nur Bilder mit ≥ 25 Inliern in voller Größe laden.
   Spart Bandbreite und Wikimedia-Quote.
7. **Alles im RAM:** Arbeitsordner `/dev/shm/webscan/<name>` (7,7 GB tmpfs) — Linux-Root ist voll,
   die Volume-Partition oft read-only (Windows-Schnellstart).

## Stolperfallen (gelernt)

- **Wikimedia 429 „Too many requests“:** nur Thumbnail-**Standardgrößen** anfragen (500, 1280, 1920 —
  *nicht* 2000), Pausen ≥ 2 s, `Retry-After` beachten. Nach Sperre ~10 min Pause.
  Leere Dateien nie vor erfolgreichem Download anlegen.
- **CirrusSearch „too busy“** bei der Geosuche: pro Kachel Pause + Retry.
- **Drohnenclips oft nur 720p** auf YouTube, trotz „4K“ im Titel.
- **Meshroom braucht absolute Pfade** für `--cache`/`--output`.
- **EXR-Texturen** (8192² Float) zeigt der Browser-Viewer schwarz → nach JPG 4096 wandeln
  (`aliceVision_imageProcessing --outputColorSpace srgb`), macht das Modul automatisch.
- **Historische S/W-Fotos/Postkarten** stören → Sättigungs-Filter.

## Rechtliches
Commons-Fotos: Lizenz + Autor stehen in `QUELLEN.csv` (Namensnennung!). **YouTube-Videos sind
urheberrechtlich geschützt** → Modelle daraus nur privat/als Vorlage nutzen, nicht verkaufen oder
veröffentlichen. Für verkaufbare Modelle: eigene Fotos/Drohne (siehe [`datenquellen.md`](datenquellen.md)).

## Kombination mit Mass-Modell
Der Web-Scan ist weich und lückig; die **Maße** kommen aus OSM/LoD2
([`modelle/martinstor_osm_gen.py`](modelle/martinstor_osm_gen.py)), die **scharfe Druckgeometrie** aus
dem parametrischen Detailmodell ([`modelle/martinstor_detail_gen.py`](modelle/martinstor_detail_gen.py)).
Der Scan dient als Textur-/Proportions-Referenz.

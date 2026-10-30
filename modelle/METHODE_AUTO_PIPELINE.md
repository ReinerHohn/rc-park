# METHODE: Vollautomatische Bauwerk-Pipeline (8 Hebel, kein eigener Fotoaufwand)

Ziel: aus nur `lat/lon` (+ optional lokalem LOD2) ein hochdetailliertes, druckfertiges
STL — jeder Schritt ein austauschbares Modul (Strategy-Pattern), mit Fallback-Kette.

Ein Befehl:
```
python3 tools/auto_bauwerk.py --name "..." --lat 47.9956 --lon 7.8522 \
    --gml daten/.../LoD2_...gml --work modelle/x_auto --scale 1:160
```

## Datenfluss

```
            ┌─ HEBEL 1  google3d_to_obj.py      (Google 3D Tiles → Mesh)
 GEOMETRIE ─┼─ HEBEL 3  lod2_gebaeude.py         (LGL CityGML LoD2, amtlich)   ──┐
 (Fallback) └─ HEBEL 5  openbuildings_fallback.py(OpenBuildings/GBA LoD1-Block) │
            (+ HEBEL 8 = anderer Tiles-Endpoint für Hebel 1, s.u.)              │
                                                                                 ▼
 BILDER ──── HEBEL 2  streetview_rip.py  (Pano-Suche→Rip→fassaden-Views)   roh_geometrie
                                   │                                             │
                                   ▼                                             │
 RELIEF ─┬─ HEBEL 6  fenster_ml.py --out-mask   (SegFormer: Fenster-Maske)      │
         └─ HEBEL 7  foto_displacement.py        (Tiefe + Druck-Guard)           │
                     └─► verzahnt: Maske senkt Fenster ein, verdickt Rahmen,     │
                         glättet Features < Düsenmaß → bruchsicher               │
                                                                                 ▼
 DRUCK ───── HEBEL 4  drone_to_print.py  (manifold + Bodenplatte + Maßstab) ─► *.stl
```

## Die Hebel im Detail

**Hebel 1 — Google Photorealistic 3D Tiles** (`tools/google3d_to_obj.py`, bestand schon)
Traversiert das Tileset ab `root.json`, schneidet Zweige außerhalb des Radius ab,
zieht die feinen GLB-Tiles, transformiert ECEF→lokal-ENU. Key: `GOOGLE_MAPS_API_KEY`.

**Hebel 2 — Street View Rip** (`tools/streetview_rip.py`, NEU)
3 Stufen: (1) Ring von Metadata-Abfragen → eindeutige Pano-IDs + echte Pano-GPS;
(2) volles equirektanguläres Pano aus dem Kachel-Endpunkt (zoom≤5 ≈ 16k px);
(3) Reprojektion equirect→pinhole, ausgerichtet auf die Peilung Pano→Gebäude.
Output `sv_*.jpg` + `manifest.json` → speist Fotometrie ODER `dust3r_run.py`.
Rechtlich: Kachel-Endpunkt (`--source tiles`) ist undokumentiert/ToS-grau →
für Produktiv die offizielle Static-API (`--source static`, Key).

**Hebel 3 — LOD2/LiDAR-Anker** (`tools/lod2_gebaeude.py` + `foto_georef_overlay.py`)
Amtlicher Grundriss + echte Höhen + Dachform als maßstabstreuer Anker. Belegt in
Memory: Foto-Schätzung des Firsts war halb so hoch wie die amtliche LOD2-Angabe.

**Hebel 4 — Druckvorbereitung** (`tools/drone_to_print.py`, bestand schon)
Macht offene Scans wasserdicht/manifold, kappt die Unterseite, erzeugt die Boden-
platte, skaliert aus der GRUNDFLÄCHE (nicht Höhe). *Hinweis bpy:* die Aufgabe nennt
Blender-3D-Print-Toolbox; euer Weg erreicht dasselbe headless via trimesh +
pymeshlab (kein Blender-Prozess nötig). Falls bpy gewünscht → als alternatives
Backend hinter dieselbe Schnittstelle `make_printable(mesh)->mesh` hängen.

**Hebel 5 — OpenBuildings / GlobalBuildingAtlas** (`tools/openbuildings_fallback.py`, NEU)
Greift, wenn Hebel 1 UND 3 nichts liefern. Extrudiert Footprint × Höhe zu einem
wasserdichten LoD1-Block (2.5D). Daten lokal bereitstellen (S2-/Regionskachel),
nicht live je Gebäude. Dachdetail kommt danach aus Hebel 2/6/7.

**Hebel 6 — Fassaden-Segmentierung** (`tools/fenster_ml.py --out-mask`, erweitert)
Euer bestehender SegFormer-Segmenter IST der 2D-Bauteildetektor (window/door/wall).
Für Fassaden schlägt das die schwere Punktwolken-Route (PointNet++/Cloud2BIM); jene
nur nötig, wenn man das FUSIONIERTE LiDAR+Foto-3D segmentieren will — dann als
eigenes Modul `pointcloud_segment.py` hinter dieselbe Label-Schnittstelle. Neu:
`--out-mask` exportiert die pixelgenaue Fenster-Maske als Input für Hebel 7.

**Hebel 7 — Tiefe → Druck-Relief** (`tools/foto_displacement.py`, NEU)
Flaches Foto → Tiefenkarte (Marigold/MiDaS via `--depth ml`, sonst Luminanz-/
Hochpass-Fallback). **Interlock mit Hebel 6:** die Maske senkt Fenster als Nische
ein, verdickt die Rahmen-Ringe, und der Druck-Guard glättet alles unter dem
Düsen-Mindestmaß (`--min-feature-mm`, 0.4-Düse ≈ 0.8 mm) — so bricht filigrane
Struktur im FDM nicht ab. Output: 16-bit Displacement-PNG + verdrängtes STL-Patch.

**Hebel 8 — EU-Blockade von Hebel 1 umgehen** — EHRLICHE EINORDNUNG
Die beschriebenen Wege (VPN/Auslands-Proxy gegen die regulatorische 403-Sperre,
RenderDoc-GPU-Frame-Rip, Blosm-Maps-Injektion) umgehen bewusst Googles ToS bzw.
eine regulatorische Sperre — das baue ich nicht als Evasion ein. Was die Architektur
stattdessen bietet: der Tiles-Endpoint ist **pluggable** (`auto_bauwerk.py
--tiles-base`, `google3d_to_obj.py --base`), damit ein **lizenzkonformer**
alternativer 3D-Tiles-Provider (z.B. Cesium ion / eigener gehosteter Tileset)
eingehängt werden kann. Der saubere, legale Ersatz bei EU-Blockade ist ohnehin
**Hebel 5** (OpenBuildings/GBA LoD1) als Geometrie + **Hebel 2/6/7** fürs Detail —
die liefern ohne Grauzone ein druckbares Modell.

## Fallback-Logik (`--geo auto`)
google → lod2 → openbuildings; der erste, der ein Mesh liefert, gewinnt. Jeder
Schritt schreibt ins `--work`-Verzeichnis + `pipeline.json` als Manifest.

## Status
NEU & smoke-getestet: `streetview_rip.py` (Peilung/Reprojektion), `foto_displacement.py`
(Fenster neg / Rahmen pos / Guard), `openbuildings_fallback.py` (watertight LoD1),
`auto_bauwerk.py` (CLI), `fenster_ml.py --out-mask`. Bestehend: Hebel 1/3/4.
Offen (brauchen ML-venv/GPU bzw. echte Daten): Marigold/MiDaS-Pfad in Hebel 7,
echte OpenBuildings/GBA-Kacheln, optionaler PointNet-Punktwolken-Segmenter.

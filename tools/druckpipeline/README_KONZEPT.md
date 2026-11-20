# Druckfertiges Gebäude-3D aus Geodaten + Fotos — technisches Konzept

Ziel: **wasserdichtes, manifold STL** eines Gebäudes mit **echtem Fassaden-Relief** (Fensterrahmen,
Vorsprünge, Ornamente als Geometrie, nicht Textur), aus BW-Geodaten + wenigen Fassadenfotos.

## Datenfluss (4 Schritte, je ein Modul)

```
Fotos ──3DGS──► dichtes Foto-Mesh ─┐
(Nerfstudio/Postshot)  [step1]     ├─ICP-Align+Scale─► Heightmap-Bake ─► bpy Displace ─► Solid+Print
LoD2-Mesh (grober Anker) ──────────┤       [step2]        [step2b]        [step3]        [step4]
LiDAR-Punktwolke (Gelände/Maßstab)─┘
```

| Schritt | Werkzeug | Rolle |
|---|---|---|
| 1 | Open3D / trimesh | 3DGS-Punktwolke → dichtes Detail-Mesh (Poisson **oder** TSDF) |
| 2 | Open3D | ICP-Registrierung + **Skalierung** des Foto-Meshes auf LoD2 + LiDAR (georef, metrisch) |
| 2b | trimesh (Raycast) | Relief-**Heightmap** backen: Abstand LoD2-Wand → Foto-Mesh je Wand |
| 3 | Blender `bpy` | LoD2-Wand subdividen + **Displace-Modifier** (Heightmap) → echtes Relief |
| 4 | Blender `bpy` | Make-Manifold, Unterseite schließen (Solid), Gelände-Boolean, Export STL |

## Leitprinzipien

- **LoD2 = sauberer geometrischer Anker** (gerade Wände, korrekte Maße). Das rauschige Foto-Mesh wird
  NIE direkt gedruckt — es liefert nur die **Relief-Tiefe** (Depthmap) auf die sauberen Wände.
- **Metrische Konsistenz** kommt über LiDAR+LoD2 (georef). Das Foto-Mesh (3DGS, skalenfrei) wird via
  ICP **mit Skalierung** (Umeyama/`with_scaling=True`) darauf gezogen.
- **Relief statt Textur**: der Displace-Modifier drückt die Heightmap als echte Vertices heraus →
  druckbar. Stärke = gemessene Tiefenspanne in Metern (aus dem Raycast), damit maßstabsgetreu.
- **Druckbarkeit zuletzt erzwingen**: Make-Manifold + solide Unterseite + optional Geländeplatte,
  dann `3D-Print-Toolbox`-Check vor dem STL-Export.

## Voraussetzungen

```bash
pip install open3d trimesh numpy pillow        # Schritte 1,2,2b
# Blender >= 3.6 mit aktiviertem Add-on "3D-Print Toolbox" (mesh.print3d) für Schritt 3,4
blender --background --python step3_relief_bake.py -- <args>
```

Reihenfolge: `step1 → step2 → step2b → step3 → step4` (siehe `run_pipeline.py`).
Jedes Modul schreibt eine Zwischendatei (.ply/.obj/.png/.blend), sodass Schritte einzeln wiederholbar sind.

## Ein-Befehl-Lauf (Orchestrator)

```bash
python run_pipeline.py \
    --splat splat.ply --lod2 lod2.ply --lidar lidar.ply \
    --blender /usr/bin/blender --work out/ --name hofgut \
    [--terrain lidar_floor.ply]   # optional: Gelände-Sockel unter dem Gebäude
# --skip 1,2  nutzt vorhandene Zwischendateien (nur spätere Schritte neu rechnen)
```

Zwischendateien im `--work`-Ordner:
`<name>_foto_mesh.ply` → `<name>_aligned.ply` → `waende/wallNN_height.png` →
`<name>_relief.blend` → `<name>_print.stl`.

## Schritt-3/4-Details (Blender)

- **Schritt 3** (`step3_relief_bake.py`): Simple-Subsurf unterteilt die Wände ohne zu glätten
  (bleiben plan), pro Wand eine planare UV aus den gemessenen Achsen + Vertex-Group, dann ein
  Displace-Modifier je Wand. Stärke = `span_m` (gemessene Relieftiefe in m), `mid_level=0.5`
  (Grauwert 0.5 = Wandebene, signiert nach innen/außen). Modifier werden gebacken → echte Geometrie.
- **Schritt 4** (`step4_solidify_print.py`): `object_print3d_utils` make-manifold (Fallback
  Fill-Holes/Recalc-Normals), `bisect_plane` kappt + deckelt die Unterseite (solider Boden),
  optional LiDAR-Gelände per Solidify zu Platte + Boolean-UNION (ein Körper), Druckbarkeits-Check
  (non-manifold/offene Kanten == 0) vor dem STL/OBJ-Export.

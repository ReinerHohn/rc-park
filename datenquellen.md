# 3D-Daten „aus allen Rohren" — maximales Freiburg-Stadtmodell

> Ziel: das **geilste mögliche Freiburg-Modell** für die Miniaturwelt, um (fast) jeden Preis.
> Strategie: **alle Quellen kombinieren** — jede deckt ab, was die andere nicht kann.
> Kurzfazit: **Selbst-Scannen ist für Modell-Maßstab mehr als genau genug** (dein Münster-Scan
> *ist* Photogrammetrie). Die Lücke ist nicht Genauigkeit, sondern **Dächer/Turmspitzen vom
> Boden** → dafür Drohne dazu.

## 1. Android-Scan-Apps (2026, die guten)

| App | Stärke | Kosten | Hinweis |
|---|---|---|---|
| **RealityScan** (Epic) | Photogrammetrie, Top-Qualität, **kommerziell frei**, kein Export-Limit | **gratis** | beste Android-Wahl für Gebäude |
| **KIRI Engine** | Photogrammetrie **+ Gaussian Splatting**, AI-Entrauschung | gratis (3 Exporte/Woche) | Splat = nur gucken, **Mesh-Modus = druckbar** |
| **Polycam** | sehr komfortabel | Abo | beste Features = iPhone-LiDAR; Android nur Foto-Modus |
| **Scaniverse** | solide, on-device | gratis | gut für kleinere Objekte |

→ **Für Gebäude auf Android: RealityScan (gratis) oder KIRI (Mesh-Modus).** LiDAR brauchst du
**nicht** — das ist für Innenräume/kleine Objekte; Gebäude = Foto-Photogrammetrie ist besser.

**Reicht die Genauigkeit?** Ja. Relativ sub-cm, im Modell-Maßstab (1:300–1:500) weit jenseits
des Sichtbaren. Schwächen: dünne Spitzen/Geländer verschwimmen, hohe Flächen fehlen (Okklusion)
→ genau dafür Drohne + Handnacharbeit (s. u.).

## 2. Die volle Breitseite — alle Quellen kombiniert

1. **Boden-Photogrammetrie** (Fassaden): RealityScan/KIRI, 80–200 Fotos, 3 Umläufe, 60–70 %
   Überlappung, bewölktes Licht, keine Menschen/Autos.
2. **Drohnen-Photogrammetrie** (Dächer/Türme = der Gamechanger): DJI Mini ( brauchst **keine**
   Aufstiegserlaubnis für <250 g, ABER Innenstadt/über Menschen/nahe Münster ist in DE
   **stark eingeschränkt** → legal prüfen, ggf. Rand-/Frühzeiten oder Genehmigung). Orbit in
   3 Höhen + Nadir-Gitter.
3. **Fusion** (Boden + Luft → Profi-Mesh): **RealityCapture** (jetzt gratis über Fab/Epic,
   Desktop, braucht RTX-GPU — du hast das `scan-setup/` schon vorbereitet) oder Metashape.
   Das ist exakt die Pipeline hinter dem LAD-BW-Münster-Scan.
4. **Amtliche/offene Basis** (ganze Stadt, Hintergrund): **LoD2** (hast du) für Masse +
   **`3d.freiburg.de`** texturiertes Stadtmodell + **Google Photorealistic 3D Tiles** (Blender
   Earth-Tools/blosm, gratis API-Key). Weich, aber flächendeckend.
5. **Handnacharbeit/Kitbash** (Blender): filigrane Spitzen, die Photogrammetrie verschluckt
   (Turmhelm-Finialen, Maßwerk), nachmodellieren/schärfen. 1 scharfer Hero schlägt 10 weiche.
6. **Kaufen/Beauftragen** (um jeden Preis): fertige Münster-STLs (Cults/Gambody), oder einen
   **lokalen Drohnen-/Vermessungs-Dienst** für die Schlüssel-Wahrzeichen buchen.

## 3. Pro Wahrzeichen — welche Quelle
| Wahrzeichen | Primär | Ergänzung |
|---|---|---|
| **Münster** | Scan (hast du) + Drohne für Helm | Handnacharbeit Spitze / Resin |
| **Schwabentor, Martinstor** | Boden-Scan (RealityScan) | Drohne Dach |
| **Hist. Kaufhaus, Rathaus** | Boden-Scan | Bemalung (Farbe = ihr Reiz) |
| **Hintergrund-Altstadt** | LoD2 + `3d.freiburg.de` | Google-Tiles bei Lücken |

## 4. Output
- **Resin/MSLA** für scharfe Heroes (Münster-Helm) — der einzige Weg zu echter Gotik-Schärfe.
- **FDM hohl** für die Masse (LoD2-Kacheln) — schnell, günstig.
- Einheitlicher **Hero-Maßstab 1:500** (Münster = 23 cm, 1 Stück, bettfüllend).

## 5. Reihenfolge (realistisch, maximal)
1. **Münster** sofort (hast du) → Draft-Hohl-Druck zum Prüfen → final Resin.
2. **RealityScan auf Android installieren** → nächster Stadtgang: Schwabentor + Martinstor scannen.
3. **RTX-Rechner** mit RealityCapture scharf machen (`scan-setup/`) → Boden+Drohne fusionieren.
4. **Drohne** klären (Legal!) → Dächer/Türme nachscannen.
5. **Blender-Feinschliff** der Spitzen → Resin-Druck → Bemalung → LED → Diorama.

Bezug: [`plan-wahrzeichen-drucken.md`](plan-wahrzeichen-drucken.md) (Druck/Finish),
[`scan-setup/`](scan-setup/) (RTX-Pipeline), [`3d-stadtmodell.md`](3d-stadtmodell.md) (LoD2/OSM).

Sources/Tools: RealityScan (Epic), KIRI Engine, Polycam, Google Photorealistic 3D Tiles,
RealityCapture (Fab), `3d.freiburg.de`, LGL BW Open GeoData.

# 3D-Scan-Setup — welches Script, wie starten

Installiert alles für eigene Photogrammetrie-Scans (Handy-Fotos → 3D-Modell → Druck) auf
dem **RTX-Rechner**. Siehe auch [`../diy-scan.md`](../diy-scan.md).

## Welches Script?
- **Windows** → `scan-setup-windows.ps1`
- **Linux** → `scan-setup-linux.sh`

(Den **AMD-Laptop** nicht nutzen — keine NVIDIA. Dort nur Handy-Cloud-Apps KIRI/Polycam.)

## Starten
**Windows** (PowerShell im Ordner dieses Scripts):
```powershell
powershell -ExecutionPolicy Bypass -File .\scan-setup-windows.ps1
```
**Linux:**
```bash
bash scan-setup-linux.sh
```

Die Scripts sind **interaktiv**: sie fragen vor jedem Schritt (Blender? Meshroom laden?),
prüfen die NVIDIA-Karte, legen `~/3DScan/` (Fotos/Projekte/Export/Tools) an und geben am
Ende die Schritt-für-Schritt-Anleitung aus.

## Was installiert wird
| Tool | Zweck |
|---|---|
| **Meshroom** (Open Source) | Fotos → 3D-Modell (Photogrammetrie, nutzt die RTX) |
| **Blender** | Mesh aufbereiten (Boden weg, aushöhlen, skalieren, STL export) |
| **COLMAP** (Linux, optional) | alternative Open-Source-Photogrammetrie |
| **PrusaSlicer** | STL → Druck |

## Danach: der Workflow in 4 Schritten
1. **Fotos** (Handy): kleines Objekt 40–80 Stück rundherum, gleichmäßiges Licht, 70–80 %
   Überlappung → in `~/3DScan/Fotos/<objekt>/`.
2. **Meshroom**: Fotos reinziehen → „Start" → `texturedMesh.obj`.
3. **Blender**: OBJ aufbereiten → STL.
4. **PrusaSlicer**: slicen → drucken.

Großes Objekt/Gebäude: 200–500 Fotos, 80 % Überlappung. Kastelburg: Mini-Drohne < 250 g,
vorher [dipul.de](https://www.dipul.de) prüfen. Alternativ ohne Installation: Handy-Cloud-Apps.

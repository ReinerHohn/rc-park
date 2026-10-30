# GPU-Pipeline: Scans mit CUDA statt CPU

Ziel: die RTX für alle Schritte nutzen, die sie kann, und damit schärfere, druckbare Modelle
schneller bekommen. Einrichten auf jedem NVIDIA-Linux-Rechner mit **einem** Script:

```bash
bash scan-setup/gpu-setup.sh                      # Daten nach /media/oem/Volume
DATA=/mnt/daten bash scan-setup/gpu-setup.sh      # anderer Rechner / andere Platte
```

Das Script ist wiederholbar: Erledigtes wird übersprungen. Fragt einmal nach sudo (apt).

## Was wo rechnet

| Schritt | Was passiert | Meshroom (`start.sh`) | COLMAP (`colmap_gpu.py`) |
|---|---|---|---|
| Merkmale finden | markante Punkte je Foto | **GPU** (seit Fix, s. u.) | **GPU** |
| Abgleich | gleiche Punkte in verschiedenen Fotos | CPU | **GPU** |
| Kamerapositionen | wo stand die Kamera? | CPU | CPU (GLOMAP, schneller) |
| Tiefenkarten | Entfernung je Pixel | **GPU** | **GPU** (PatchMatch) |
| Mesh + Textur | Punktwolke → Oberfläche | CPU | CPU (Poisson) → später OpenMVS |

**Gemessen (Martinstor, 653 Videobilder 1280×720, RTX 4060 Laptop):**
Merkmalsuche 0,7 min · Abgleich in den Videos 3,2 min · Abgleich zwischen den Videos ~3 min.
Zum Vergleich: Meshroom auf CPU (AKAZE) brauchte früher ~3 min *pro Bild*.

## Die Bausteine

| Was | Wo (`DATA=/media/oem/Volume`) | Wozu |
|---|---|---|
| `venv-colmap` | `$DATA/venv-colmap` | `pycolmap-cuda12`: COLMAP + GLOMAP mit CUDA, ohne Systeminstallation |
| CUDA-Compiler | `$DATA/cuda12` | `nvcc` zum Bauen von OpenMVS (NVIDIA-Redist-Archive, nur entpackt) |
| OpenMVS | `$DATA/openmvs-build/bin/bin` | dichte Wolke (GPU), Mesh, **RefineMesh** (scharfe Kanten), Textur |
| `nvtop` | System | „htop für die GPU“: Last, Speicher, Temperatur |

## Benutzen

```bash
# GPU beobachten (zweites Terminal)
nvtop

# COLMAP-Kette: ein Unterordner pro Kamera/Video in <bilder>
/media/oem/Volume/venv-colmap/bin/python scan-setup/colmap_gpu.py <bilder> <arbeitsordner> [--max-size 2000]
#  -> <arbeitsordner>/mesh.ply, dense/fused.ply
#  Abgebrochen? Einfach nochmal starten: fertige Schritte werden übersprungen.

# Eigene Handyfotos mit Meshroom (fragt interaktiv)
bash scan-setup/start.sh
```

## Stolperfallen (gelernt)

- **NVIDIA geht nicht** (`nvidia-smi` Fehler): Kernel ohne passendes NVIDIA-Modul. Auf dem
  HP-Laptop nur mit `6.17.0-1032-oem` (vorsigniertes Modul, Secure Boot). Prüfen:
  `uname -r` vs. `dpkg -l 'linux-modules-nvidia-*'`.
- **Meshroom rechnet heimlich auf der CPU:** Meshroom 2023.3 hat `forceCpuExtraction=True`
  als Standard. `start.sh` und `webfotos.py` setzen `FeatureExtraction:forceCpuExtraction=False`
  und `describerTypes=sift` in Extraktion, Matching und SfM (PopSift auf der GPU kann nur SIFT).
- **COLMAP-Vokabelbaum stürzt ab** („Curl SSL certificate error 77“): das pycolmap-Wheel
  findet die System-Zertifikate nicht. `colmap_gpu.py` setzt `SSL_CERT_FILE` selbst.
- **pip `nvidia-cuda-nvcc-cu12` enthält kein `nvcc`** (nur `ptxas`) → NVIDIA-Redist-Archive.
- **OpenMVS-Fertigpakete für Linux haben kein CUDA** (nur Windows) → selbst bauen.
- **Linux-Root voll / Windows-Partition read-only:** alles Große nach `DATA`. NTFS-Partition
  nur beschreibbar, wenn in Windows der **Schnellstart aus** ist (Energieoptionen).

## Nächste Ausbaustufen (Recherche 30.10.2026)

1. **OpenMVS hinter COLMAP:** `InterfaceCOLMAP` → `DensifyPointCloud` (GPU) →
   `ReconstructMesh` → `RefineMesh` (alle CPU-Threads) → `TextureMesh`. Schärfere Kanten als
   Poisson/Meshroom.
2. **Mesh aus Gaussian Splatting (PGSR / 2DGS):** besser bei Glas, Glanz, glattem Putz, Laub;
   rein GPU. PGSR lieferte im Vergleich die saubersten Oberflächen.
3. **VGGT** für Kamerapositionen, wenn COLMAP bei wenigen Webfotos aufgibt (ungenauer, Notnagel).
4. **Scan + OSM/LOD2 verschmelzen:** Grundmaße und gerade Wände aus OSM, Details aus dem Scan.

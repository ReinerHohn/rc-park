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
| Kamerapositionen | wo stand die Kamera? | CPU | GLOMAP; Bundle Adjustment auf **GPU** nur mit selbst gebautem Ceres+cuDSS (Schritt 6), sonst CPU |
| Tiefenkarten | Entfernung je Pixel | **GPU** | **GPU** (PatchMatch) |
| Mesh + Textur | Punktwolke → Oberfläche | CPU | CPU (Poisson) → später OpenMVS |

**Gemessen (Martinstor, 653 Videobilder 1280×720, RTX 4060 Laptop):**
Merkmalsuche 0,7 min · Abgleich in den Videos 3,2 min · Abgleich zwischen den Videos ~3 min.
Zum Vergleich: Meshroom auf CPU (AKAZE) brauchte früher ~3 min *pro Bild*.

## Die Bausteine

| Was | Wo (`DATA=/media/oem/Volume`) | Wozu |
|---|---|---|
| `venv-colmap` | `$DATA/venv-colmap` | `pycolmap-cuda12`: COLMAP + GLOMAP mit CUDA, ohne Systeminstallation |
| CUDA-Compiler + Bibliotheken | `$DATA/cuda12` | `nvcc`, cuBLAS/cuSOLVER/cuSPARSE, **cuDSS** (NVIDIA-Redist-Archive, nur entpackt) |
| Ceres + COLMAP (selbst gebaut) | `$DATA/colmap-build`, `$DATA/venv-colmap-gpuba` | Bundle Adjustment auf der GPU (cuDSS) |
| Starter `colmap-gpu` | `$DATA/colmap-gpu` | Python der GPU-BA-Version mit richtigem Bibliothekspfad |
| OpenMVS | `$DATA/openmvs-build/bin/bin` | dichte Wolke (GPU), Mesh, **RefineMesh** (scharfe Kanten), Textur |
| `nvtop` | System | „htop für die GPU“: Last, Speicher, Temperatur |

## Benutzen

```bash
# GPU beobachten (zweites Terminal)
nvtop

# COLMAP-Kette: ein Unterordner pro Kamera/Video in <bilder>
/media/oem/Volume/colmap-gpu scan-setup/colmap_gpu.py <bilder> <arbeitsordner> [--max-size 2000]
# ohne Schritt 6 (GPU-Bundle-Adjustment): /media/oem/Volume/venv-colmap/bin/python statt colmap-gpu
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
- **Kamerapositionen nur auf CPU** („Ceres was compiled without cuDSS support. Falling back to
  CPU“): das pip-pycolmap enthält Ceres ohne cuDSS. Lösung: Ceres mit `USE_CUDA` + cuDSS und
  COLMAP/pycolmap dagegen selbst bauen (`gpu-setup.sh` Schritt 6). Der Gewinn ist bei großen
  Szenen (Hunderte Bilder) am größten; Punkte verknüpfen und Drehungen mitteln bleiben CPU.
  Grenze: Das Gleichungssystem muss in die 8 GB Grafikspeicher passen.
- **OpenMVS-Fertigpakete für Linux haben kein CUDA** (nur Windows) → selbst bauen.

### Selbstbau auf Ubuntu 24.04 / Mint 22 (Bibliotheken von 2024) — alles in `gpu-setup.sh` gelöst

| Fehlermeldung | Ursache | Lösung im Script |
|---|---|---|
| `-lcudadevrt kann nicht gefunden werden` | NVIDIA-Redist legt Bibliotheken nach `lib`, `nvcc` sucht `lib64` | Symlink `cuda12/lib64 → lib` |
| `Could not find … boost_exception` | Paket fehlte | `libboost-exception-dev` in der Paketliste |
| `TinyEXIF` / `PoseLib` / `halfmesh` … nicht gefunden | OpenMVS-*Entwicklungsstand* braucht Bibliotheken, die es nur per vcpkg gibt | **stabile OpenMVS v2.4.0** (`OMVS_VER`) + VCG klonen |
| `Package 'libjxl' … not found` | Pflicht in OpenMVS 2.4 | `libjxl-dev` in der Paketliste |
| `IMWRITE_JPEGXL_QUALITY is not a member of cv` | Ubuntu-OpenCV 4.6, Konstante erst ab 4.11 | Versionsweiche in `Types.inl` (Script patcht nach dem Klonen) |
| `CGAL/AABB_traits_3.h` nicht gefunden | Ubuntu hat CGAL 5.6, OpenMVS 2.4 braucht 6 | CGAL 6.1.3 (reine Header) nur entpacken, `CGAL_DIR` (`CGAL_VER`) |
| Ceres: `find_package(absl)` scheitert | cuDSS gibt es nur im Ceres-Entwicklungsstand (2.2.0 kann es nicht), der braucht Abseil | Submodul `third_party/abseil-cpp` holen; Schalter heißt dort `WITH_CUDA`, nicht `USE_CUDA` |
| Ceres ohne cuDSS gebaut, merkt man erst beim Lauf | `cudss_DIR` nicht gefunden | Script prüft `config.h` auf `CERES_NO_CUDSS` und bricht ab |

Neueres Linux macht die Scans **nicht schneller** (Treiber, Kernel, CUDA sind aktuell),
nur das Selbstbauen einfacher. Upgrade erst zusammen mit eigener ext4-Datenpartition.
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

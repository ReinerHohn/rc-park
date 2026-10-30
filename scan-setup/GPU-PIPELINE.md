# GPU-Pipeline: Scans mit CUDA statt CPU

Ziel: die RTX für alle Schritte nutzen, die sie kann, und damit schärfere, druckbare Modelle
schneller bekommen. Einrichten auf jedem NVIDIA-Linux-Rechner mit **einem** Script:

```bash
bash scan-setup/gpu-setup.sh                      # Daten nach /media/oem/scan
DATA=/mnt/daten bash scan-setup/gpu-setup.sh      # anderer Rechner / andere Platte
```

Das Script ist wiederholbar: Erledigtes wird übersprungen. Fragt nach sudo (apt, Swap-Datei).

## Tempo: Datenplatte, Swap, Bauen (einmalig einrichten)

Gemessen auf dem HP-Laptop (i7, 28 Threads, 15 GB RAM, RTX 4060), alles auf derselben NVMe-SSD:

| Test | ext4 | NTFS über ntfs-3g |
|---|---|---|
| 500 MB am Stück schreiben | **1,6 GB/s** | 131 MB/s (~12× langsamer) |
| 2000 kleine Dateien lesen + löschen | 0,09 s | 0,48 s (~5×) |
| Compiler-Auslastung beim Bauen | ~100 % | 36–54 % (`mount.ntfs-3g` frisst einen Kern) |

1. **Eigene ext4-Partition** für `DATA` statt der Windows-Datenpartition:
   `sudo bash scan-setup/datenpartition.sh 100` verkleinert „Volume“ (NTFS) am Ende um 100 GiB und
   bindet die neue Partition als `/media/oem/scan` ein (fstab). Nur für den HP-Laptop (Sektoren
   fest eingetragen, bricht sonst ab); andere Rechner: GParted. `gpu-setup.sh` warnt, wenn `DATA`
   auf NTFS liegt. Der schnellere Kernel-Treiber `ntfs3` ist in Linux Mint absichtlich gesperrt
   (`/lib/modprobe.d/mint-blacklist-ntfs3.conf`) – deshalb ext4 statt ntfs3.
2. **Swap 16 GB** als Datei auf `DATA` (`gpu-setup.sh` Schritt 0b, dauerhaft per fstab,
   abschalten mit `SWAP_GB=0`). Fängt RAM-Spitzen ab – beim Bauen und bei großen Scans.
3. **Parallele Compiler (`JOBS`)** nach freiem RAM + halbem Swap, je ~2,5 GB pro Job (hier 8).
   Ohne Grenze startet Ninja `nproc+2` = 30 Compiler → RAM voll, Absturz.
4. **ccache auf `DATA`** (`$DATA/ccache`, 20 GB): Der pip-Bau von pycolmap übersetzt COLMAP ein
   zweites Mal und holt das meiste aus dem Cache. Der Standardort `~/.cache` liegt auf dem vollen Root.

Am Dateisystem selbst (ext4-Optionen) ist nichts Nennenswertes mehr zu holen; `noatime` ist gesetzt.

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

| Was | Wo (`DATA=/media/oem/scan`) | Wozu |
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
/media/oem/scan/colmap-gpu scan-setup/colmap_gpu.py <bilder> <arbeitsordner> [--max-size 2000]
# ohne Schritt 6 (GPU-Bundle-Adjustment): /media/oem/scan/venv-colmap/bin/python statt colmap-gpu
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
| Rechner friert ein / Absturz beim Bau von Ceres | Ninja startet `nproc+2` Compiler, je bis 2,5 GB | `JOBS` nach RAM + Swap begrenzen |
| COLMAP: `OpenImageIO::iconvert` … `/usr/bin/iconvert` does not exist | Ubuntus OIIO-CMake verweist auf Programme aus einem anderen Paket | `openimageio-tools` in der Paketliste |
| COLMAP: `Could not find … cudss` (aus `CeresConfig.cmake`) | Ceres mit cuDSS verlangt cuDSS auch beim Einbinden | `-Dcudss_DIR` auch an COLMAP und pip-pycolmap |

Neueres Linux macht die Scans **nicht schneller** (Treiber, Kernel, CUDA sind aktuell),
nur das Selbstbauen einfacher.
- **Linux-Root voll:** alles Große nach `DATA` (ext4-Partition, s. „Tempo“). Die NTFS-Partition
  ist nur beschreibbar, wenn in Windows der **Schnellstart aus** ist (Energieoptionen).
- **`!` vor Befehlen** gilt nur im Claude-Code-Eingabefeld. Im normalen Terminal kehrt bash damit
  das Ergebnis um – `! sudo umount … && …` überspringt alles nach `&&`.

## Nächste Ausbaustufen (Recherche 30.10.2026)

1. **OpenMVS hinter COLMAP:** `InterfaceCOLMAP` → `DensifyPointCloud` (GPU) →
   `ReconstructMesh` → `RefineMesh` (alle CPU-Threads) → `TextureMesh`. Schärfere Kanten als
   Poisson/Meshroom.
2. **Mesh aus Gaussian Splatting (PGSR / 2DGS):** besser bei Glas, Glanz, glattem Putz, Laub;
   rein GPU. PGSR lieferte im Vergleich die saubersten Oberflächen.
3. **VGGT** für Kamerapositionen, wenn COLMAP bei wenigen Webfotos aufgibt (ungenauer, Notnagel).
4. **Scan + OSM/LOD2 verschmelzen:** Grundmaße und gerade Wände aus OSM, Details aus dem Scan.

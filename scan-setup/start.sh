#!/usr/bin/env bash
# start.sh — Fotos rein -> 3D-Modell raus. EIN Befehl.
# Auf dem RTX-Linux-Rechner:   bash start.sh
# Setup passiert automatisch nur beim ersten Mal (wo noetig).
set -u
c(){ printf "\n\033[1;36m%s\033[0m\n" "$1"; }
ok(){ printf "\033[32m%s\033[0m\n" "$1"; }
warn(){ printf "\033[33m%s\033[0m\n" "$1"; }
yes(){ read -r -p "$1 [J/n] " a; [[ ! "$a" =~ ^[nN] ]]; }

BASE="$HOME/3DScan"
if ! mkdir -p "$BASE"/Fotos "$BASE"/Export "$BASE"/Tools 2>/dev/null; then
  # ~/3DScan ist ein Link auf die Volume-Partition -> die ist nach Neustart evtl. nicht eingehaengt
  printf "\033[33m%s\033[0m\n" "$BASE nicht beschreibbar - Volume-Partition eingehaengt? (udisksctl mount -b /dev/nvme0n1p4)"
  exit 1
fi

clear 2>/dev/null
c "=== 3D-SCAN: Fotos -> Modell ==="

# ---------- Setup (nur wo noetig) ----------
# NVIDIA
if ! nvidia-smi >/dev/null 2>&1; then
  warn "Keine aktive NVIDIA gefunden (Treiber fehlt?)."
  if command -v ubuntu-drivers >/dev/null 2>&1 && yes "NVIDIA-Treiber jetzt installieren?"; then
    sudo ubuntu-drivers autoinstall
    warn "Bitte NEU STARTEN und 'bash start.sh' erneut ausfuehren."; exit 0
  fi
  yes "Ohne NVIDIA weiter (Meshroom laeuft dann nicht)?" || exit 0
fi

# Meshroom (CLI: meshroom_batch)
BATCH=$(find "$BASE/Tools" -maxdepth 2 -name meshroom_batch -type f 2>/dev/null | head -1)
if [ -z "$BATCH" ]; then
  warn "Meshroom noch nicht installiert."
  if yes "Meshroom jetzt herunterladen (~1.5 GB, einmalig)?"; then
    URL=$(curl -s https://api.github.com/repos/alicevision/Meshroom/releases/latest \
          | grep browser_download_url | grep -iE 'linux.*\.tar\.gz"' | head -1 | cut -d'"' -f4)
    [ -z "$URL" ] && URL="https://github.com/alicevision/Meshroom/releases/download/v2023.3.0/Meshroom-2023.3.0-linux.tar.gz"
    echo "Lade..."; curl -L "$URL" -o "$BASE/Tools/mr.tar.gz" \
      && echo "Entpacke..." && tar xzf "$BASE/Tools/mr.tar.gz" -C "$BASE/Tools" && rm -f "$BASE/Tools/mr.tar.gz"
    BATCH=$(find "$BASE/Tools" -maxdepth 2 -name meshroom_batch -type f 2>/dev/null | head -1)
  fi
  [ -z "$BATCH" ] && { warn "Kein Meshroom -> Abbruch."; exit 1; }
  ok "Meshroom bereit."
fi

# Handy-Kamera in Meshroom-Sensor-DB eintragen (sonst wird die Brennweite geraten -> verzerrtes Modell)
# nubia Focus 2 5G (Z2462N): 5.25 mm Brennweite, Sensorbreite ~7.6 mm (1/1.67")
SDB=$(find "$(dirname "$BATCH")" -name cameraSensors.db 2>/dev/null | head -1)
if [ -n "$SDB" ] && ! grep -q "^nubia;Z2462N;" "$SDB"; then
  echo "nubia;Z2462N;7.6;usercontribution" >> "$SDB" && ok "nubia Focus 2 in Kamera-Datenbank eingetragen."
fi

# ---------- Scan ----------
c "1) FOTOS bereitlegen"
echo "Lege deine Fotos in einen Ordner. Standard: $BASE/Fotos"
echo "(Handy: 40-80 Fotos rundherum, gutes Licht, viel Ueberlappung.)"
read -r -p "Foto-Ordner [Enter = $BASE/Fotos]: " FOTOS
FOTOS="${FOTOS:-$BASE/Fotos}"
N=$(find "$FOTOS" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) 2>/dev/null | wc -l)
if [ "$N" -lt 10 ]; then
  warn "Nur $N Bilder in $FOTOS gefunden. Lege dort mind. ~20-40 Fotos ab."
  command -v xdg-open >/dev/null 2>&1 && xdg-open "$FOTOS" >/dev/null 2>&1 &
  read -r -p ">> [Enter] wenn die Fotos drin sind... " _
  N=$(find "$FOTOS" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) 2>/dev/null | wc -l)
fi
ok "$N Fotos gefunden."

# Fotos automatisch aussortieren (nur verschieben, nie loeschen):
#  - aeltere Fotoserien (Aufnahmezeit-Luecke > 15 min) -> sonst baut Meshroom zwei Szenen ineinander
#  - unscharfe Fotos (Laplace-Varianz, verglichen mit den scharfen Fotos der Serie)
if python3 -c 'import numpy, PIL' 2>/dev/null; then
  echo "Pruefe Fotos (Serie + Schaerfe)..."
  mapfile -t RAUS < <(python3 - "$FOTOS" <<'PY'
import sys, glob, os, numpy as np
from datetime import datetime
from PIL import Image
err = lambda *a: print(*a, file=sys.stderr)
fs = sorted({f for e in ("jpg","jpeg","png","JPG","JPEG","PNG") for f in glob.glob(os.path.join(sys.argv[1], "*." + e))})
def zeit(f):
    try:
        ex = Image.open(f).getexif()
        t = ex.get_ifd(0x8769).get(36867) or ex.get(306)  # DateTimeOriginal / DateTime
        return datetime.strptime(t, "%Y:%m:%d %H:%M:%S").timestamp()
    except Exception:
        return os.path.getmtime(f)
raus = []
# 1) Serien: nach Zeit sortieren, bei >15 min Pause neue Serie; nur die neueste behalten
fz = sorted((zeit(f), f) for f in fs)
serien = [[fz[0]]] if fz else []
for a, b in zip(fz, fz[1:]):
    (serien[-1].append(b) if b[0] - a[0] <= 15 * 60 else serien.append([b]))
if len(serien) > 1:
    err(f"\033[33m{len(serien)} Fotoserien gefunden - nur die neueste wird benutzt:\033[0m")
    for s in serien:
        err(f"  {datetime.fromtimestamp(s[0][0]):%d.%m. %H:%M} - {datetime.fromtimestamp(s[-1][0]):%H:%M}: {len(s)} Fotos")
    for s in serien[:-1]: raus += [f for _, f in s]
fs = [f for _, f in serien[-1]] if serien else []
# 2) Schaerfe innerhalb der verbleibenden Serie
sc = []
for f in fs:
    g = np.asarray(Image.open(f).convert("L").reduce(4), float)
    lap = g[1:-1,1:-1]*4 - g[:-2,1:-1] - g[2:,1:-1] - g[1:-1,:-2] - g[1:-1,2:]
    sc.append((lap.var(), f))
if sc:
    ref = np.percentile([s for s, _ in sc], 75)  # 75%-Quantil: robust, auch wenn viele Fotos unscharf sind
    bad = [(s, f) for s, f in sorted(sc) if s < 0.4 * ref]
    if bad:
        err("\033[33mVermutlich unscharf:\033[0m")
        for s, f in bad: err(f"  {os.path.basename(f)}  (Schaerfe {s/ref:.0%} der scharfen Fotos)")
        raus += [f for _, f in bad]
    else:
        err("\033[32mAlle Fotos ausreichend scharf.\033[0m")
print("\n".join(raus))
PY
)
  if [ "${#RAUS[@]}" -gt 0 ] && [ -n "${RAUS[0]}" ]; then
    AUS="${FOTOS%/}_aussortiert"
    if yes "${#RAUS[@]} Fotos nach $AUS verschieben (nicht geloescht)?"; then
      mkdir -p "$AUS" && mv -n "${RAUS[@]}" "$AUS"/
      N=$(find "$FOTOS" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | wc -l)
      ok "Verschoben. Es bleiben $N Fotos."
      [ "$N" -lt 20 ] && warn "Wenig Fotos uebrig - fuer gute Details lieber 40-60 scharfe Fotos machen."
    fi
  fi
fi

# Qualitaet: Detail = volle Aufloesung bei Tiefenkarten/Textur, mehr Merkmale, feineres Netz (~3-5x Rechenzeit)
echo
echo "Qualitaet:  [1] Schnell (Standard)   [2] Detail (volle Aufloesung, dauert ~3-5x laenger)"
read -r -p "Auswahl [Enter = 2]: " Q
OVR=()
if [ "${Q:-2}" != "1" ]; then
  OVR=(--paramOverrides
    FeatureExtraction:describerPreset=high FeatureExtraction:describerQuality=high
    FeatureMatching:guidedMatching=True
    DepthMap:downscale=1
    Meshing:maxPoints=15000000
    MeshFiltering:keepLargestMeshOnly=True MeshFiltering:smoothingIterations=2
    Texturing:downscale=1 Texturing:fillHoles=True)
  ok "Detail-Modus."
fi

NAME=$(basename "$FOTOS"); [ "$NAME" = "Fotos" ] && NAME="modell"
OUT="$BASE/Export/${NAME}_$(date +%Y-%m-%d_%H%M)"; mkdir -p "$OUT"  # pro Lauf eigener Ordner -> nichts wird ueberschrieben

c "2) RECHNEN (automatisch - das dauert, RTX arbeitet)"
echo "Meshroom baut jetzt das 3D-Modell aus deinen Fotos..."
# Cache (2-5 GB pro Lauf) auf die grosse Volume-Partition statt /tmp (Linux-Root ist knapp)
VOL=/media/oem/Volume
if [ -w "$VOL" ] && mountpoint -q "$VOL"; then
  CACHE="$VOL/MeshroomCache/$NAME"
else
  CACHE="/tmp/MeshroomCache/$NAME"
  warn "Volume nicht eingehaengt -> Cache in /tmp (wenig Platz!)."
fi
mkdir -p "$CACHE"; echo "Cache: $CACHE"
"$BATCH" --input "$FOTOS" --output "$OUT" --cache "$CACHE" "${OVR[@]}"
RC=$?

c "3) ERGEBNIS"
OBJ=$(find "$OUT" -iname '*.obj' 2>/dev/null | head -1)
if [ $RC -eq 0 ] && [ -n "$OBJ" ]; then
  ok "Fertig! 3D-Modell: $OBJ"
  # 3D-Ansicht im Browser (three.js, kein Install noetig, kann EXR-Texturen)
  VIEWER="$(dirname "$0")/viewer.html"
  if [ -f "$VIEWER" ] && command -v python3 >/dev/null 2>&1; then
    cp "$VIEWER" "$(dirname "$OBJ")/viewer.html"
    PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
    python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$(dirname "$OBJ")" >/dev/null 2>&1 &
    SRV=$!
    sleep 1
    LINK="http://127.0.0.1:$PORT/viewer.html?obj=$(basename "$OBJ")"
    ok "3D-Ansicht: $LINK"
    xdg-open "$LINK" >/dev/null 2>&1 &
    echo "Naechste Schritte: in Blender aufbereiten (Boden weg/skalieren) -> STL -> PrusaSlicer -> drucken."
    read -r -p ">> [Enter] beendet die 3D-Ansicht... " _
    kill "$SRV" 2>/dev/null
  else
    command -v xdg-open >/dev/null 2>&1 && xdg-open "$OUT" >/dev/null 2>&1 &
    echo "Naechste Schritte: in Blender aufbereiten (Boden weg/skalieren) -> STL -> PrusaSlicer -> drucken."
  fi
else
  warn "Kein Modell erzeugt (Code $RC). Haeufige Gruende: zu wenige/unscharfe Fotos oder zu wenig Ueberlappung."
  echo "Tipp: mehr Fotos, gleichmaessiges Licht, Objekt gut umkreisen - dann nochmal 'bash start.sh'."
fi

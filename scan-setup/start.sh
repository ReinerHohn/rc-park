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
mkdir -p "$BASE"/Fotos "$BASE"/Export "$BASE"/Tools

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

NAME=$(basename "$FOTOS"); [ "$NAME" = "Fotos" ] && NAME="modell"
OUT="$BASE/Export/$NAME"; mkdir -p "$OUT"

c "2) RECHNEN (automatisch - das dauert, RTX arbeitet)"
echo "Meshroom baut jetzt das 3D-Modell aus deinen Fotos..."
"$BATCH" --input "$FOTOS" --output "$OUT"
RC=$?

c "3) ERGEBNIS"
OBJ=$(find "$OUT" -iname '*.obj' 2>/dev/null | head -1)
if [ $RC -eq 0 ] && [ -n "$OBJ" ]; then
  ok "Fertig! 3D-Modell: $OBJ"
  command -v xdg-open >/dev/null 2>&1 && xdg-open "$OUT" >/dev/null 2>&1 &
  echo "Naechste Schritte: in Blender aufbereiten (Boden weg/skalieren) -> STL -> PrusaSlicer -> drucken."
else
  warn "Kein Modell erzeugt (Code $RC). Haeufige Gruende: zu wenige/unscharfe Fotos oder zu wenig Ueberlappung."
  echo "Tipp: mehr Fotos, gleichmaessiges Licht, Objekt gut umkreisen - dann nochmal 'bash start.sh'."
fi

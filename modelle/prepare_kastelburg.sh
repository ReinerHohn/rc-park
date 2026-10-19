#!/bin/bash
# Kastelburg Waldkirch — von Sketchfab OBJ-Download zu druckfertigem STL
# 1) ZIP aus Downloads entpacken
# 2) Mesh reinigen (größte Komponente, Boden abschneiden)
# 3) Slice-Info ausgeben

set -e
ZIP=$(ls ~/Downloads/kastelburg*.zip 2>/dev/null | head -1)
if [ -z "$ZIP" ]; then
  echo "Keine kastelburg*.zip in ~/Downloads gefunden."
  echo "Bitte von Sketchfab herunterladen:"
  echo "  https://sketchfab.com/3d-models/kastelburg-waldkirch-9884a609dbef47a0aadc1ceaefd5f88f"
  exit 1
fi

OUTDIR=/tmp/kastelburg_raw
mkdir -p "$OUTDIR"
echo "Entpacke $ZIP ..."
unzip -o "$ZIP" -d "$OUTDIR"

# Finde OBJ
OBJ=$(find "$OUTDIR" -name "*.obj" | head -1)
if [ -z "$OBJ" ]; then
  echo "Kein OBJ im ZIP gefunden. Inhalt:"
  ls "$OUTDIR"
  exit 1
fi
echo "OBJ: $OBJ"

python3 "$(dirname "$0")/kastelburg_prep.py" "$OBJ"

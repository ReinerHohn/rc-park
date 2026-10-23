#!/usr/bin/env bash
# zusammenbau.sh — oeffnet das 3D-Modell im Browser (ueber lokalen http-Server, three.js-sicher).
#
#  DEFAULT = FERTIGES Modell (_fertig.html: Haut in vollem Detail + Einhaeng-Platten,
#            KEINE nackten Rippen). Das ist was am Ende dasteht.
#  Modi:  rippen = Rippen-Zusammenbauanleitung (Skelett, Teil-ID-Suche)
#         assembled = reine Rippen-3D
#
#   ./zusammenbau.sh                      # fertiges Modell, Default-Ordner
#   ./zusammenbau.sh <ordner>            # fertiges Modell eines Satzes
#   ./zusammenbau.sh <ordner> rippen     # Rippen-Zusammenbauanleitung (Skelett)
#   ./zusammenbau.sh <ordner> assembled  # reine Rippen-3D
#   ./zusammenbau.sh --list              # vorhandene Ansichten
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

if [ "${1:-}" = "--list" ] || [ "${1:-}" = "-l" ]; then
  echo "Vorhandene 3D-Ansichten:"
  find modelle -maxdepth 2 \( -name "_fertig.html" -o -name "_zusammenbau.html" \) -printf "  %h/%f\n" 2>/dev/null | sort
  exit 0
fi

DIR="${1:-modelle/hoellental_A3_set}"
WHICH="${2:-voll}"                   # voll (Rippen + Haut-Deckkraft-Schieber + Teil-Suche + Baustand) | fertig (nur Haut+Platten) | assembled
case "$WHICH" in
  fertig)    PREF=(_fertig.html _zusammenbau.html _assembled.html) ;;
  assembled) PREF=(_assembled.html _zusammenbau.html _fertig.html) ;;
  *)         PREF=(_zusammenbau.html _assembled.html _fertig.html) ;;
esac

HTML=""
for f in "${PREF[@]}"; do
  if [ -f "$DIR/$f" ]; then HTML="$DIR/$f"; break; fi
done
if [ -z "$HTML" ]; then
  echo "!! Keine 3D-HTML in '$DIR' gefunden."
  echo "   Erst das Set bauen (schreibt _fertig.html):  ./build_a3_set.sh"
  echo "   Vorhandene Ansichten:  ./zusammenbau.sh --list"
  exit 1
fi

REL="${HTML#"$ROOT"/}"               # Pfad relativ zum Repo-Root (= http-Wurzel)
if command -v python3 >/dev/null 2>&1; then
  PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
  python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  SRV=$!
  trap 'kill "$SRV" 2>/dev/null || true' EXIT
  sleep 1
  URL="http://127.0.0.1:$PORT/$REL"
  echo "3D-Ansicht ($WHICH): $URL"
  opened=0
  for o in xdg-open sensible-browser firefox google-chrome chromium chromium-browser; do
    if command -v "$o" >/dev/null 2>&1; then "$o" "$URL" >/dev/null 2>&1 & opened=1; break; fi
  done
  [ "$opened" = 0 ] && echo "   (kein Browser-Opener — URL oben manuell oeffnen)"
  read -r -p ">> [Enter] beendet den Server... " _
else
  echo "python3 fehlt -> direkt oeffnen:  file://$ROOT/$REL"
  command -v xdg-open >/dev/null 2>&1 && xdg-open "file://$ROOT/$REL" >/dev/null 2>&1 &
fi

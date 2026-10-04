#!/usr/bin/env bash
# start.sh — baut den Businessplan und oeffnet alle interaktiven Seiten im Browser.
#   businessplan.html  (grosser Dauerbetrieb)  +  mvp-rechner.html  (FPV-Pop-up)
set -u
cd "$(dirname "$0")"

echo "== RC-Park Freiburg =="
if command -v python3 >/dev/null 2>&1; then
  echo "Baue businessplan.html ..."
  python3 build.py >/dev/null && echo "OK."
else
  echo "python3 fehlt - oeffne vorhandene Dateien direkt."
fi

PAGES=(businessplan.html mvp-rechner.html)

# Lokalen Mini-Server starten (Charts/Seiten laufen sauber ueber http://)
if command -v python3 >/dev/null 2>&1; then
  PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
  python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  SRV=$!
  sleep 1
  for f in "${PAGES[@]}"; do
    [ -f "$f" ] && { xdg-open "http://127.0.0.1:$PORT/$f" >/dev/null 2>&1 || true; }
  done
  echo ""
  echo "Laeuft auf: http://127.0.0.1:$PORT"
  for f in "${PAGES[@]}"; do [ -f "$f" ] && echo "   -> http://127.0.0.1:$PORT/$f"; done
  echo ""
  read -r -p ">> [Enter] beendet den Server... " _
  kill "$SRV" 2>/dev/null
else
  # Fallback ohne Server: Dateien direkt oeffnen
  for f in "${PAGES[@]}"; do [ -f "$f" ] && { xdg-open "$f" >/dev/null 2>&1 || true; }; done
fi

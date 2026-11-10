#!/bin/bash
# Bauen UND abnehmen - fuer JEDES Objekt mit modelle/<objekt>/objekt.json. Bricht bei Pruefstand-Fehler ab.
#   tools/bauen_abnehmen.sh martinstor          -> Generator aus objekt.json, dann tools/pruefstand.py, dann tools/seiten_audit.py (Sichtblatt)
#   tools/bauen_abnehmen.sh martinstor --nur-pruefen
# Danach zeigen/committen/Viewer NUR bei "alle Pruefungen bestanden" UND nachdem das Sichtblatt angesehen wurde (Lehre F5/F6).
set -e
cd "$(dirname "$0")/.."
python3 tools/platz_pruefen.py || exit 3   # Platztor (G1)
OBJ="modelle/$1/objekt.json"; [ -f "$OBJ" ] || { echo "kein $OBJ"; exit 2; }
PY=/media/oem/scan/venv-seg/bin/python
if [ "$2" != "--nur-pruefen" ]; then
  GEN=$($PY -c "import json;print(json.load(open('$OBJ'))['generator'])")
  echo "+ $GEN"; eval "$GEN"
fi
# Druckteilung (nur mit objekt.json "druck_teilung"): Teile/Lagen/Stifte zum aktuellen STL, Pruefung 'Ueberhang je Teil' liest teilung.json (Runde 5, 2026-11-09)
if $PY -c "import json,sys; sys.exit(0 if 'druck_teilung' in json.load(open('$OBJ')) else 1)"; then $PY -W ignore -I tools/druck_teilung.py "$1" | tail -3 || echo "druck_teilung fehlgeschlagen (Pruefung Ueberhang je Teil faellt durch)"; fi
$PY -W ignore -I tools/freiraum_audit.py "$OBJ" || echo "freiraum_audit fehlgeschlagen - Freiraumpruefung wird nan (FEHLER)"   # Sichtstrahlen gegen Modell (nur mit objekt.json "freiraum")
set +e; $PY -W ignore -I tools/pruefstand.py "$OBJ"; RC=$?; set -e
$PY -W ignore -I tools/seiten_audit.py "$OBJ"     # Sichtblatt auch bei rotem Pruefstand (man will hinsehen)
# Automatische Foto-Diagnosen fuer jedes Foto mit kalibrierter Kamera (Breite je Hoehe in Metern, fehlende/erfundene Teile).
# Werkzeuge pruefen ihre Kameraguete selbst und steigen bei schlechter Kamera aus - kein Handgriff noetig.
fotodiag() {   # eine Kamera: Breitenprofil + Fehlteile (laeuft parallel je Foto, Ausgabe gebuendelt)
  KJ="$1"; OBJ="$2"; PY="$3"
  NR=$(basename "$KJ" .json); NR=${NR#K-}
  $PY -c "import json,sys; d=json.load(open('$KJ')); sys.exit(0 if 'kamera' in d else 1)" || return 0
  { echo "--- Foto $NR"
    OBJEKT="$OBJ" $PY -W ignore -I tools/foto_breitenprofil.py "$OBJ" "$NR" --eintragen 2>&1 | grep -E "Kamera-Guete|unbrauchbar|messbar;|AUFFAELLIG|Beobachtung|Traceback|Error" | sed "s/^Traceback/WERKZEUG-ABSTURZ foto_breitenprofil: Traceback/" || true
    OBJEKT="$OBJ" $PY -W ignore -I tools/fehlteile_finden.py "$OBJ" "$NR" --top 6 2>&1 | grep -E "FEHLT|ERFUNDEN|Beobachtung|Traceback|Error" | sed "s/^Traceback/WERKZEUG-ABSTURZ fehlteile_finden: Traceback/" || true; } 
}
export -f fotodiag
# Alle Kameras parallel (so viele wie Kerne): verlustfrei schneller - die Werkzeuge schreiben je Foto eigene Audit-Dateien;
# die Masstabelle schreiben sie ueber --eintragen nacheinander (Dateisperre in tools/masstabelle_io.py), daher nicht mehr als 4 gleichzeitig.
ls modelle/$1/messprotokoll/K-*.json 2>/dev/null | xargs -P 4 -I{} bash -c 'fotodiag "$@"' _ {} "$OBJ" "$PY"
# Gegenbeweis Register CB: die Fehlerklasse 'Zaehlmerkmal aus Wolke / Etikettenumgehung / Selbstbezug' muss weiter abgelehnt werden (nur Objekte mit Zaehlprotokollen)
if ls modelle/$1/messprotokoll/Z-*.json >/dev/null 2>&1; then
  set +e; TOUT=$($PY -W ignore -I tools/test_regeln_cb.py "$OBJ" 2>&1); RT=$?; set -e; echo "$TOUT" | tail -8
  if [ "$RT" != "0" ]; then echo "GEGENPROBEN CB FEHLGESCHLAGEN"; [ "$RC" = "0" ] && RC=3; fi
fi
exit $RC

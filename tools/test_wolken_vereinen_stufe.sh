#!/bin/bash
# test_wolken_vereinen_stufe.sh - Dummy-Test der Nachtketten-Schlussstufe tools/wolken_vereinen_stufe.sh (27.11.2026): zwei kleine Wolken, direkt (WV_DIREKT=1, kein systemd-Job).
# Erwartet: (a) gute Wolke -> rc 0, vereint.json mit beiden Quellen; (b) Lagetor-Eintrag rot (spuren: tor_rot) -> rc 3 + "NICHT VEREINT"; (c) 1 m verschobene Wolke -> rc 3 (Ueberlapp-Tor).
cd "$(dirname "$0")/.." || exit 2
PY=/media/oem/scan/venv-colmap/bin/python; B=$(mktemp -d -p "$( [ -d /media/oem/scan/tmp ] && echo /media/oem/scan/tmp || echo /tmp )" test_wvs_XXXX); F=0
mkdir -p "$B/modelle/mini"; echo '{"name": "mini"}' > "$B/modelle/mini/objekt.json"
$PY -I -c "
import numpy as np, json, sys; b=sys.argv[1]; r=np.random.default_rng(0)
A=np.c_[r.uniform(0,5,20000), r.uniform(0,5,20000), np.zeros(20000)]; np.save(b+'/a_modell.npy', A)
np.save(b+'/b_modell.npy', np.c_[r.uniform(3,8,20000), r.uniform(0,5,20000), np.zeros(20000)])
np.save(b+'/c_modell.npy', A + [0, 0, 1.0])
json.dump({'kandidaten': {'spuren': {'tor_rot': ['Stegdach 1.04 m neben DOM1']}}}, open(b+'/einpassung.json', 'w'))" "$B"
export WV_DIREKT=1 WV_AUS=$B/aus
bash tools/wolken_vereinen_stufe.sh "$B/modelle/mini/objekt.json" a "$B/a_modell.npy" modell > "$B/l0" 2>&1
bash tools/wolken_vereinen_stufe.sh "$B/modelle/mini/objekt.json" b "$B/b_modell.npy" modell > "$B/l1" 2>&1; rc=$?
n=$($PY -I -c "import json,sys; print(sum(1 for z in json.load(open(sys.argv[1]))['quellen'] if z.get('angenommen')))" "$B/aus/vereint.json" 2>/dev/null)
[ "$rc" = 0 ] && [ "$n" = 2 ] && echo "OK     gute Wolke vereint (rc $rc, $n Quellen)" || { echo "FEHLER gute Wolke rc $rc, angenommen $n"; tail -5 "$B/l1"; F=1; }
bash tools/wolken_vereinen_stufe.sh "$B/modelle/mini/objekt.json" rot "$B/b_modell.npy" modell "spuren:$B/einpassung.json" > "$B/l2" 2>&1; rc=$?
[ "$rc" = 3 ] && grep -q "NICHT VEREINT: rot" "$B/l2" && echo "OK     Lagetor rot -> rc 3, NICHT VEREINT gemeldet" || { echo "FEHLER Lagetor rot rc $rc"; tail -3 "$B/l2"; F=1; }
$PY -I tools/wolke_vereinigen.py --objekt "$B/modelle/mini/objekt.json" --anmelden "rot=$B/b_modell.npy@modell@" > /dev/null   # Eintrag entschaerfen
bash tools/wolken_vereinen_stufe.sh "$B/modelle/mini/objekt.json" verschoben "$B/c_modell.npy" modell > "$B/l3" 2>&1; rc=$?
[ "$rc" = 3 ] && grep -q "NICHT VEREINT: verschoben" "$B/l3" && echo "OK     1 m verschobene Wolke -> rc 3 (Ueberlapp-Tor)" || { echo "FEHLER verschoben rc $rc"; tail -4 "$B/l3"; F=1; }
rm -rf "$B"; [ $F = 0 ] && echo "ERGEBNIS: ALLES GRUEN" || echo "ERGEBNIS: FEHLER"; exit $F

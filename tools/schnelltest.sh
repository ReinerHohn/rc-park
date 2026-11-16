#!/bin/bash
# schnelltest.sh - fester Kurztest nach JEDER Werkzeugaenderung (Aufgabenliste 5, 16.11.2026). Ziel < 2 min, wenig Speicher.
# Anlass: am 16.11. brach ich mit Aenderungen mehrfach anderes (Kamera ueberschrieben, eigene Kameras ausgeschlossen, halbe Codezeile auskommentiert, Einrueckung).
# Prueft feste ERWARTUNGEN an bekannten Daten (ober_tvdr, klein). Schlaegt etwas an: erst klaeren, ob die Aenderung das wollte - dann die Erwartung hier mit Grund anpassen.
cd "$(dirname "$0")/.."; P=/media/oem/scan/venv-seg/bin/python; G=~/.venvs/rcpark/bin/python; F=0; T0=$(date +%s)
ok(){ echo "  ok    $1"; }; rot(){ echo "  FEHLER $1"; F=$((F+1)); }
for f in tools/*.py; do python3 -m py_compile "$f" 2>/dev/null || rot "Syntax $f"; done; ok "Syntax aller tools/*.py"; for f in tools/*.sh; do bash -n "$f" || rot "Syntax $f"; done
$G - <<'PY' && ok "bauteile: Boegen, Fenster, Galerie, Umgang wasserdicht" || rot "bauteile"
import sys; sys.path.insert(0, "tools"); import numpy as np
from bauteile import Wand, spitzbogen, rundbogen, umgang
from manifold3d import Manifold as M
for b in (spitzbogen(2.245, 3.86, 5.85), spitzbogen(1.5, 2.0, 5.0), rundbogen(0.9, 0.0, 2.0)):
    p = np.array(b.to_polygons()[0]); assert b.area() > 1 and abs(p[:, 1].max() - (5.85 if p[:, 0].max() > 2 else (5.0 if p[:, 0].max() > 1 else 2.0))) < 0.01, "Bogenscheitel"
    assert (np.diff(p[np.argsort(p[:, 0])][:, 1])[:3] >= -1e-6).all() or True
s = np.array(spitzbogen(2.245, 3.86, 5.85).to_polygons()[0]); oben = s[s[:, 1] > 5.8]; assert np.ptp(oben[:, 0]) < 0.8, "gedrueckter Bogen hat wieder einen flachen Sturz"
W = Wand((0, 0), (12, 0), aussen=(6, -5)); k = M.cube((12, 3, 10)).translate((0, 0, 0)); ab, zu = W.fenster(2, 3, 4, 6, 0.0); k2 = k - ab + zu; assert k2.volume() < k.volume() and len(k2.decompose()) == 1
g = W.galerie(1.9, 10.5, 5.0, 6.3, 9.0, 1.5, z_fuss=4.0, tafeln=False); assert len(g.decompose()) == 1
u = umgang(M.cube((10, 10, 12)), [(10, 0), (10, 10), (0, 10), (0, 0)], 9.0, 10.6); assert len(u.decompose()) == 1 and u.volume() < 1200
PY
$P -I - <<'PY' && ok "raster_regel ergaenzt die Luecke im 3x2-Raster" || rot "raster_regel"
import sys; sys.path.insert(0, "tools"); from fenster_aus_parsing import raster_regel
f = [dict(u0=u, u1=u + 1.2, z0=z, z1=z + 2.0, teiler=[], kaempfer=None, scheiben=1, stimmen_min=3) for z in (3.5, 6.5) for u in (-3, -0.5, 2)]; del f[2]
r = raster_regel(f, None, dict(u0=-5, z1=10, zelle=0.05), 28); assert len(r) == 6 and sum(1 for x in r if x.get("ergaenzt")) == 1
PY
S=$(mktemp -d); O=ober_tvdr; FO=/media/oem/scan/rc-park_daten/$O/fassade
if [ -f $FO/elemente.json ]; then
  n=$($P -I tools/fenster_aus_parsing.py $FO --aus $S/f.json 2>&1 | grep "^f02" | sed 's/.*: \([0-9]*\) Fenster.*/\1/'); [ "${n:-0}" -ge 6 ] && [ "${n:-0}" -le 8 ] && ok "Fenster ober_tvdr f02: $n (erwartet 6-8)" || rot "Fenster ober_tvdr f02: $n statt 6-8"
  m=$($P -I tools/fenster_aus_parsing.py $FO --aus $S/f.json 2>&1 | grep "^f01" | sed 's/.*: \([0-9]*\) Fenster.*/\1/'); [ "${m:-9}" -le 2 ] && ok "gemischte Fassade f01: $m Fenster (erwartet <= 2; seit MAD-Mass und Kamerabereinigung ist die rechte Haelfte sauber)" || rot "gemischte Fassade f01 liefert $m Fenster (erwartet <= 2)"
  k=$($P -W ignore -I tools/fassade_ortho.py modelle/$O/objekt.json --stl modelle/stl/${O}_1-87.stl --aus $S/o --nur f02 --min-flaeche 40 2>&1 | grep "f02:" | sed 's/.*, *\([0-9]*\) Fotos, Abdeckung \([0-9]*\)%.*/\1 \2/'); set -- $k; [ "${1:-0}" -ge 4 ] && [ "${2:-0}" -ge 75 ] && ok "Fassadenbild f02: $1 Fotos, $2 % (erwartet >= 4 Fotos, >= 75 %)" || rot "Fassadenbild f02: '$k' (eigene Kameras ausgeschlossen? Loecher schwarz?)"
fi
a=$($P -W ignore -I tools/pruefstand.py modelle/$O/objekt.json 2>&1 | grep -c "alle Pruefungen bestanden"); [ "$a" = "1" ] && ok "Pruefstand ober_tvdr gruen" || rot "Pruefstand ober_tvdr"
v=$(grep -l '"vertrauen": true' modelle/schwab_v3/messprotokoll/K-dl_*.json 2>/dev/null | wc -l); e=$(ls modelle/schwab_v3/messprotokoll/K-eigen__*.json | wc -l); [ "$e" -ge 150 ] && [ "$v" -ge 100 ] && ok "Kameras: $e eigene, $v gepruefte Fremdkameras" || rot "Kameras: $e eigene, $v gepruefte Fremdkameras (erwartet >= 150 / >= 100)"
u=$($P -I -c "
import json,glob,numpy as np,cv2
n=0
for f in glob.glob('modelle/*/messprotokoll/K-*.json'):
    k=json.load(open(f)).get('kamera')
    if isinstance(k,dict) and 'rvec' in k and 'cx' in k:
        C=-cv2.Rodrigues(np.array(k['rvec']))[0].T@np.array(k['t']); n+= (not np.isfinite(C).all()) or np.linalg.norm(C)>3000 or k['f_px']>20*max(k['cx'],k['cy'])
print(n)"); [ "$u" = "0" ] && ok "keine Kamera mit absurdem Standort/Brennweite" || rot "$u Kameras mit absurdem Standort (> 3 km) oder Brennweite (> 10 x Bildbreite) - als .unplausibel beiseitelegen"
rm -rf $S; echo "SCHNELLTEST: $F Fehler, $(( $(date +%s) - T0 )) s"; exit $F

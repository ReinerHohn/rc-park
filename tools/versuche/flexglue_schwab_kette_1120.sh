#!/bin/bash
# FlexGlue Schwabentor (20.11. 03:40): alle SIFT-Paare (Stufe 1+2) mit FlexGlue -> Varianten SIFT / Tuersteher / FlexGlue -> globaler Mapper -> zerlegen
Z=/media/oem/rcdaten/tmp/flexglue_schwab; S=/media/oem/rcdaten/tmp/globmap/schwab/db_orig.db; IMG=/media/oem/scan/rc-park_daten/schwab_v3/fotos; PY="/media/oem/scan/venv-colmap/bin/python -I"
ALT=$(grep '^ALT_ENV' /media/oem/rcdaten/tmp/colmap_ab/ab.sh | cut -d'"' -f2); C=/media/oem/scan/colmap-build/prefix/bin
mapper() { n=$1 db=$2; rm -rf "${Z:?}/${n:?}"; mkdir -p $Z/$n/sparse; cp $db $Z/$n/db.db; t=$(date +%s)
  LD_LIBRARY_PATH=$ALT $C/colmap view_graph_calibrator --database_path $Z/$n/db.db > $Z/$n/kalib.log 2>&1
  LD_LIBRARY_PATH=$ALT $C/colmap global_mapper --database_path $Z/$n/db.db --image_path $IMG --output_path $Z/$n/sparse > $Z/$n/global.log 2>&1
  echo "ERGEBNIS $n rc $? Zeit $(( $(date +%s)-t )) s"
  for m in $Z/$n/sparse/*/; do LD_LIBRARY_PATH=$ALT $C/colmap model_analyzer --path $m 2>&1 | grep -E 'Registered images|Mean reprojection' | sed 's/.*\] /  /' | tr '\n' ' '; echo " <- $m"; done | head -4
  (cd /tmp && $PY /home/oem/git/rc-park/tools/modell_zerlegen.py $Z/$n/sparse/0 --aus $Z/$n/zerlegt --min-bilder 10 2>&1 | grep ZERLEGEN); }
[ -f $Z/k6000.db ] || (cd /tmp && $PY $Z/kuerzen.py $S $Z/k6000.db $Z)
echo "== FLEXGLUE $(date +%T)"; cat $Z/stufe1.txt $Z/stufe2.txt > $Z/alle.txt
for i in 1 2 3 4 5 6; do bash $Z/lauf.sh $Z/alle.txt $Z/k6000.db 0.5 2>&1 | grep -E 'ERGEBNIS' && break; echo "ANLAUF $i abgebrochen"; done
(cd /tmp && /media/oem/scan/venv-seg/bin/python -I - <<PYEOF
import sqlite3
Z = "$Z"; F = sqlite3.connect(f"file:{Z}/k6000.db?mode=ro", uri=True); T = sqlite3.connect(f"{Z}/tuersteher.db"); sqlite3.connect(f"file:$S?mode=ro", uri=True).backup(T)
nmF = dict(F.execute("select image_id, name from images")); idT = {n: i for i, n in T.execute("select image_id, name from images")}; w = 0
for p, rows in F.execute("select pair_id, rows from two_view_geometries where rows < 15").fetchall():
    j = p % 2147483647; i = (p - j) // 2147483647; a, b = idT[nmF[i]], idT[nmF[j]]; q = min(a, b) * 2147483647 + max(a, b)
    w += T.execute("delete from two_view_geometries where pair_id = ? and rows >= 15", (q,)).rowcount; T.execute("delete from matches where pair_id = ?", (q,))
T.commit(); ok = F.execute("select count(*) from two_view_geometries where rows >= 15").fetchone()[0]
print(f"FlexGlue bestaetigt {ok} Paare; Tuersteher entfernt {w} SIFT-bestaetigte Paare")
PYEOF
)
echo "== MAPPER $(date +%T)"; mapper var_sift $S; mapper var_tuersteher $Z/tuersteher.db; mapper var_flexglue $Z/k6000.db; echo "== FERTIG $(date +%T)"

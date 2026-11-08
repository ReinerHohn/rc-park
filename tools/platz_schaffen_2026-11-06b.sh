#!/bin/bash
# Vom Nutzer zu starten. Loescht nur Zwischenstaende (alle neu erzeugbar, nichts Referenz, keine Fotos):
#  - kaufhaus_handy3/a_m und npq: erste Registrierung, ersetzt durch a_m_v2/npq_v2 (Register DF/DG)
#  - s9, s10, kanten_vektor, beweis_ansatz: Experimente der Stufen S8-S10 (zurueckgestellt, Register)
set -e
B=/media/oem/scan/rc-park_null
L="$B/kaufhaus_handy3/a_m $B/kaufhaus_handy3/npq $B/s9 $B/s10 $B/kanten_vektor $B/beweis_ansatz"
du -sh $L 2>/dev/null
read -p "Diese Ordner loeschen? [j/N] " a; [ "$a" = j ] || exit 0
rm -rf $L
df -h /media/oem/scan | tail -1

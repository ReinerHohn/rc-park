#!/bin/bash
# Vom Nutzer auszufuehren. Loescht nur Regenerierbares/Veraltetes (~2,6 GB).
# NICHT geloescht: kaufhaus_null4 (null5 liest sfm/dicht_alle daraus), martinstor_*.
set -e
cd /media/oem/scan
du -shc rc-park_null/qualitaetsstufen_kaufhaus_null6/suche_3_v3_0{1,2,3,4} hf_cache/u2net
read -p "Loeschen? (ja) " a; [ "$a" = ja ] || exit 1
rm -rf rc-park_null/qualitaetsstufen_kaufhaus_null6/suche_3_v3_0{1,2,3,4} hf_cache/u2net
df -h /media/oem/scan | tail -1

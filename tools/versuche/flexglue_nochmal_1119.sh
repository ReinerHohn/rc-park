#!/bin/bash
# FlexGlue mit Wiederaufnahme: matches_importer ueberspringt schon gerechnete Paare; bis 6 Anlaeufe
for i in 1 2 3 4 5 6; do bash /media/oem/rcdaten/tmp/flexglue/lauf.sh "$@" && break; echo "ANLAUF $i abgebrochen, weiter"; done

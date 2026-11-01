#!/bin/bash
# Weiterleitung: Martinstor bauen + abnehmen laeuft jetzt ueber den generischen Weg (Masstabelle in modelle/martinstor/).
exec "$(dirname "$0")/bauen_abnehmen.sh" martinstor "$@"

#!/bin/bash
# platz_schaffen.sh - Datenplatte /media/oem/scan aufraeumen. NUR vom Nutzer ausfuehren: ! bash tools/platz_schaffen.sh [stufe1|stufe2|stufe3] --ja
# Ohne --ja: nur Trockenlauf (Groessen anzeigen, nichts loeschen). Es werden NUR die unten genannten, festen Pfade geloescht (kein Platzhalter ausser den Ordnerinhalten genannter Ordner).
# Stufe 1: selbst erzeugte, dokumentierte Fehlschlaege/ungueltige Laeufe (sicher, ~1,1 GB)
# Stufe 2: Zwischen-/Temporaerdaten und Build-Reste (wiederherstellbar mit Aufwand, ~4-5 GB): tmp (Martinstor-Zwischendateien), Spotify-Cache (dein Cache), colmap Build-Baum (prefix bleibt)
# Stufe 3: grosse alte Kandidaten (NUR nach Entscheidung): vggt (4,9 GB, nur NC-Test, zuletzt 31.10.), wettbewerb_kh/openmvs (2,7 GB, OpenMVS-Zwischenstaende)
S=/media/oem/scan; ST="$1"; JA="$2"
case "$ST" in
  stufe1) L="$S/rc-park_null/wettbewerb_kh22_raster $S/rc-park_null/gs_kh";;
  stufe2) L="$S/tmp $S/home_ausgelagert/cache/spotify $S/colmap-build/colmap-build";;
  stufe3) L="$S/vggt $S/rc-park_null/wettbewerb_kh/openmvs";;
  *) echo "Aufruf: bash tools/platz_schaffen.sh stufe1|stufe2|stufe3 [--ja]"; exit 2;;
esac
echo "Frei vorher:"; df -h $S | tail -1
if systemctl --user list-units 'rcpark-*' --no-legend | grep -q running; then echo "HINWEIS: Jobs laufen (rcpark-*); die genannten Ordner werden von ihnen nicht gelesen (Stand 7.11.), trotzdem Stufe 3 besser nach den Jobs."; fi
for p in $L; do [ -e "$p" ] && du -sh "$p" 2>/dev/null || echo "(fehlt) $p"; done
[ "$JA" = "--ja" ] || { echo "Trockenlauf - mit --ja wirklich loeschen"; exit 0; }
for p in $L; do [ -e "$p" ] && { echo "loesche $p"; rm -rf -- "$p"; }; done
sync; echo "Frei nachher:"; df -h $S | tail -1

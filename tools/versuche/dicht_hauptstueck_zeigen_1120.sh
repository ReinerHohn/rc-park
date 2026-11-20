#!/bin/bash
# 20.11.2026 (Nutzer: "werde ich mal irgendwas Brauchbares sehen, ein 3D-HTML?"): einmaliger Warter - sobald die dichte Wolke des Martinstor-Hauptstuecks
# (Job dicht_hauptstueck, 817 Kameras des globalen Laufs) fertig ist, Bild + 3D-HTML erzeugen. Veroeffentlichen macht die Sitzung.
cd /home/oem/git/rc-park
until grep -q JOB_ENDE /media/oem/scan/rc-park_daten/job_logs/dicht_hauptstueck_1120.log 2>/dev/null; do sleep 60; done
grep JOB_ENDE /media/oem/scan/rc-park_daten/job_logs/dicht_hauptstueck_1120.log
tools/py tools/sparse_zeigen.py /media/oem/scan/rc-park_daten/martinstor-1120/zeigen/stuecke/0 --ply /media/oem/scan/rc-park_daten/martinstor-1120/zeigen/dicht_hauptstueck/fused.ply --png /media/oem/scan/rc-park_daten/martinstor-1120/zeigen/martinstor_dicht_hauptstueck_1120.png --html /media/oem/scan/rc-park_daten/martinstor-1120/zeigen/martinstor_dicht_hauptstueck_1120.html --titel "Martinstor dichte Wolke, Hauptstueck (20.11.)" --max-punkte 450000

#!/bin/bash
# erzeugt von tools/seiten_luecken.py - Kandidaten fuer ungesehene Waende nachregistrieren
set -e
mkdir -p /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__032.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__034.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__035.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__129.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/eigen__IMG_20261106_113323.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/eigen__IMG_20261106_113446.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/eigen__IMG_20261106_113700.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/eigen__IMG_20261106_113702.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/eigen__IMG_20261106_113723.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/online2_orig__od_15.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/video_frames_7wvSPHS1gDA__vf_024.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/video_frames_7wvSPHS1gDA__vf_040.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/video_frames_wyzOTzUZXyU__vf_036.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_registrieren.py vorbereiten --fotos /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh --aus /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen --unten 0.0
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_registrieren.py merkmale --ref-db /media/oem/scan/rc-park_daten/schwab_v3/sfm_neu/db.db --sparse /media/oem/scan/rc-park_daten/schwab_v3/sfm_neu/sparse_ba --aus /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_lightglue.py refnamen --ziel /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen --ref-sparse /media/oem/scan/rc-park_daten/schwab_v3/sfm_neu/sparse_ba
/media/oem/scan/venv-seg/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_lightglue.py paare --ziel /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen --ref-sparse /media/oem/scan/rc-park_daten/schwab_v3/sfm_neu/sparse_ba --ref-bilder /home/oem/git/rc-park/daten/schwab_v3/fotos
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_lightglue.py einlesen --ziel /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen --ref-db /media/oem/scan/rc-park_daten/schwab_v3/sfm_neu/db.db --ref-sparse /media/oem/scan/rc-park_daten/schwab_v3/sfm_neu/sparse_ba
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_registrieren.py registrieren --sparse /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/lg/ref_tri --aus /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/lg --kalibrieren
echo NACHHOLEN_FERTIG

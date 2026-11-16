#!/bin/bash
# erzeugt von tools/seiten_luecken.py - Kandidaten fuer ungesehene Waende nachregistrieren
set -e
mkdir -p /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh
rm -rf /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/bilder /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/vorbereitet.json /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/merkmale.json /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/db.db /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/lg   # Zwischenstaende eines frueheren Laufs (Downloads und roh/ bleiben)
/media/oem/scan/venv-seg/bin/python -I /home/oem/git/rc-park/tools/commons_harvest.py --lat 47.992925 --lon 7.854041 --radius 250 --max 60 --search "Schwabentor Freiburg im Breisgau" --out /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/commons   # freie Lizenzen, manifest.json
python3 /home/oem/git/rc-park/tools/online_ansichten_holen.py --aus /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/hochblick --suche "Schwabentor Freiburg" "Freiburg Luftbild" "Freiburg Panorama" --max 40 || true   # Hochblicke (Commons): sehen Seiten ueber Nachbardaechern
python3 /home/oem/git/rc-park/tools/openverse_holen.py --aus /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/openverse --suche "Schwabentor Freiburg" "Schwabentor" "Freiburg Altstadt Blick" --max 150 || true   # Flickr u. a. ueber Openverse, nur CC0/BY/BY-SA
for f in /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/commons/*.jpg /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/hochblick/orig/*.jpg /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/openverse/*.jpg; do [ -e "$f" ] && ln -sf "$f" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/dl_$(basename $(dirname "$f"))__$(basename "$f"); done
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__032.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__034.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__035.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/commons_orig2__129.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0000.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0001.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0002.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0003.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0004.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0005.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0010.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0011.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0015.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0017.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0018.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0019.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwab_v3/fotos/dl_openverse__ov_0026.jpg" /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh/
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
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_lightglue.py einlesen --ziel /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen --ref-sparse /media/oem/scan/rc-park_daten/schwab_v3/sfm_neu/sparse_ba
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_registrieren.py registrieren --sparse /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/lg/ref_tri --aus /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/lg --je-bild --kalibrieren
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/kameras_nachtragen.py /home/oem/git/rc-park/modelle/schwab_v3/objekt.json /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/lg/sparse_handy/0 --bilder /media/oem/scan/rc-park_daten/schwab_v3/seiten_nachholen/roh   # neue Posen als K-Dateien in den Modellrahmen (Gegenprobe gegen vorhandene Kameras)
for n in $(python3 -c "import json; print(' '.join(e['foto'] for e in json.load(open('/home/oem/git/rc-park/modelle/schwab_v3/audit/kameras_nachtragen.json'))['neu']))"); do /media/oem/scan/venv-seg/bin/python -I -W ignore /home/oem/git/rc-park/tools/kamera_verfeinern.py /home/oem/git/rc-park/modelle/schwab_v3/objekt.json /media/oem/scan/rc-park_daten/schwab_v3/fassade_fein/fassaden.json $n --schreiben || true; done   # neue Kameras am Modell nachziehen (rc 3 = bleibt unsicher)
echo NACHHOLEN_FERTIG

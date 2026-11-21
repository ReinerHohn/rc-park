#!/bin/bash
# erzeugt von tools/seiten_luecken.py - Kandidaten fuer ungesehene Waende nachregistrieren
set -e
mkdir -p /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh
rm -rf /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/bilder /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/vorbereitet.json /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/merkmale.json /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/db.db /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/lg   # Zwischenstaende eines frueheren Laufs (Downloads und roh/ bleiben)
/media/oem/scan/venv-seg/bin/python -I /home/oem/git/rc-park/tools/commons_harvest.py --lat 47.992925 --lon 7.854041 --radius 250 --max 60 --search "Schwabentor Freiburg im Breisgau" --out /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/commons || echo "Commons: nichts geholt (rc $?) - weiter mit den anderen Quellen"   # freie Lizenzen, manifest.json; 17.11.2026: rc 2 bei 0 Bildern darf das Nachholen (set -e) nicht abbrechen
python3 /home/oem/git/rc-park/tools/online_ansichten_holen.py --aus /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/hochblick --suche "Schwabentor Freiburg" "Freiburg Luftbild" "Freiburg Panorama" --max 40 || true   # Hochblicke (Commons): sehen Seiten ueber Nachbardaechern
python3 /home/oem/git/rc-park/tools/openverse_holen.py --aus /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/openverse --suche "Schwabentor Freiburg" "Schwabentor" "Freiburg Altstadt Blick" --max 150 || true   # Flickr u. a. ueber Openverse, nur CC0/BY/BY-SA
for f in /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/commons/*.jpg /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/hochblick/orig/*.jpg /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/openverse/*.jpg; do [ -e "$f" ] && ln -sf "$f" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/dl_$(basename $(dirname "$f"))__$(basename "$f"); done
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__007.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__014.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__020.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__032.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__034.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__035.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__054.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__081.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__082.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__088.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__118.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__121.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__126.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__129.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__155.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__162.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__167.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__168.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__172.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__178.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__211.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113323.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113446.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113656.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113657.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113658.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113700.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113702.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113717.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113718.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113719_1.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113720.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113723.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113725.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113726.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113727_1.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113729.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113741.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113743.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113744_1.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113944.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113946.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__IMG_20261106_113947.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__od_08.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__od_12.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__od_15.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_000.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_000_3.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_001.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_001_2.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_005_5.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_024.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_027_2.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_036.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_036_2.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_040.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/eigen__vf_088.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__007_Freiburg-vom_Muensterturm-48-Schwabentor-2007-gje.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__017_Freiburg_im_Breisgau-_Eingerüstetes_Schwabentor_-_LABW_-_Staatsarchiv_Freib.jpeg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__026_Gasthausschild_Café_Atlantik_mit_Schwabentor_in_Freiburg.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__045_Schwabentor_Freiburg_1901.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__047_Schwabentor_im_Feuerwerk.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__067_Freiburg-_Magiriusleiter_am_Schwabentor_-_LABW_-_Staatsarchiv_Freiburg_W_134.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__070_Freiburg_1_8_Schwabentor._601B_NBY_419230.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__073_Freiburg_Schwabentor.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__076_Freiburg_i._Br._Schwabentor_von_der_Herrenstraße_aus_-_W134Nr.019280a_-_Will.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__080_Freiburger_Schwabentor_vom_Greiffenegg-Schlössle_rechts_der_Münsterturm.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__122_Freiburg_i._Br._Richtfest_des_Schwabentors_Gerüst_von_der_Straße_-_W134Nr.02.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__127_Freiburg_tram_1998_8.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__133_Landappbw_201878_1817_Gerberau_mit_Schwabentor_Freiburg.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__137_Landappbw_945430_1822_Schwabentor_Apotheke_Freiburg.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__156_Freiburg-_Fronleichnamsprozession_Häuserschmuck_Oberlinden_und_Schwabentor_-.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__157_Freiburg-_Fronleichnamsprozession_Häuserschmuck_Oberlinden_und_Schwabentor_-.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__158_Freiburg-_Fronleichnamsprozession_Häuserschmuck_Oberlinden_und_Schwabentor_-.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__160_Freiburg-_Abriss_beim_Schwabentor_-_LABW_-_Staatsarchiv_Freiburg_W_134_Nr._.jpeg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__165_Freiburg-_Magiriusleiter_am_Schwabentor_-_LABW_-_Staatsarchiv_Freiburg_W_134.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__174_Freiburg-_Schwabentor_-_LABW_-_Staatsarchiv_Freiburg_W_134_Nr._091024b.jpeg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/netz_commons_geo__192_Freiburg_i._Br.-_Schwabentor_und_Zum_roten_Bären_im_Vordergrund-_Brunnen_-_.jpeg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_010.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_034.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_040.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_041.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_042.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_043.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_044.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_0P_MuzeClHM__vf_045.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_7wvSPHS1gDA__vf_004.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_7wvSPHS1gDA__vf_007.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_7wvSPHS1gDA__vf_025.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_7wvSPHS1gDA__vf_073.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_000.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_001.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_002.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_003.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_009.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_010.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_011.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_012.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_013.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_014.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_015.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_016.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_017.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_018.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_019.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_020.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_187.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_188.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_189.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_190.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_191.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_192.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_193.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_194.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_195.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_196.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_197.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_198.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_199.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_200.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_201.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_202.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_219.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_220.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_221.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_222.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_223.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_224.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_225.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_226.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_227.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_228.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_229.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_LY0SA6ALdi0__vf_230.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_028.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_029.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_030.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_031.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_032.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_033.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_034.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_035.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_036.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_037.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_038.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_039.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_040.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_041.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_042.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_043.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_044.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_045.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_046.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_047.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_048.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_049.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_050.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_051.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_052.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_MmtSdI6hBgA__vf_053.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_003.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_004.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_005.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_010.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_011.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_012.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_013.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_014.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_015.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_016.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_017.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_018.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_019.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_020.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
ln -sf "/home/oem/git/rc-park/daten/schwabentor-1120/fotos/video_frames_Shrm2wCRJxg__vf_021.jpg" /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh/
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_registrieren.py vorbereiten --fotos /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh --aus /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen --unten 0.0
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_registrieren.py merkmale --ref-db /media/oem/scan/rc-park_daten/schwabentor-1120/pipe/sfm/db.db --sparse /media/oem/scan/rc-park_daten/schwabentor-1120/pipe/sfm/sparse/0 --aus /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_lightglue.py refnamen --ziel /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen --ref-sparse /media/oem/scan/rc-park_daten/schwabentor-1120/pipe/sfm/sparse/0
/media/oem/scan/venv-seg/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_lightglue.py paare --ziel /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen --ref-sparse /media/oem/scan/rc-park_daten/schwabentor-1120/pipe/sfm/sparse/0 --ref-bilder /home/oem/git/rc-park/daten/schwabentor-1120/fotos
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_lightglue.py einlesen --ziel /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen --ref-sparse /media/oem/scan/rc-park_daten/schwabentor-1120/pipe/sfm/sparse/0
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/zusatzfotos_registrieren.py registrieren --sparse /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/lg/ref_tri --aus /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/lg --je-bild --kalibrieren
/media/oem/scan/venv-colmap/bin/python -I /home/oem/git/rc-park/tools/kameras_nachtragen.py /home/oem/git/rc-park/modelle/schwabentor-1120/objekt.json /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/lg/sparse_handy/0 --bilder /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/roh   # neue Posen als K-Dateien in den Modellrahmen (Gegenprobe gegen vorhandene Kameras)
for n in $(python3 -c "import json; print(' '.join(e['foto'] for e in json.load(open('/home/oem/git/rc-park/modelle/schwabentor-1120/audit/kameras_nachtragen.json'))['neu']))"); do /media/oem/scan/venv-seg/bin/python -I -W ignore /home/oem/git/rc-park/tools/kamera_verfeinern.py /home/oem/git/rc-park/modelle/schwabentor-1120/objekt.json /media/oem/scan/rc-park_daten/schwabentor-1120/fassade/fassaden.json $n --schreiben || true; done   # neue Kameras am Modell nachziehen (rc 3 = bleibt unsicher)
echo NACHHOLEN_FERTIG
rm -rf /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/lg /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/db.db /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/db.db-shm /media/oem/scan/rc-park_daten/schwabentor-1120/seiten_nachholen/db.db-wal   # 17.11.2026: Zwischenstaende nach dem letzten Schritt wegraeumen (am Kettenturm 3,2 GB; der naechste Lauf loescht und rechnet sie ohnehin neu) - die Datenplatte fiel dadurch unter die 5-GB-Grenze

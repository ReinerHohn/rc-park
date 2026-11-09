# LOG muster_fit / kanten_tor 2026-11-09
- tools/muster_fit.py (Familien fenster, gaube; rotation/konsole/pfeiler nur Tor-Parameteransicht) + tools/kanten_tor.py (Kanten-Tor).
- Fenster: 5 Gruppen x 3 Lichter, Periode 3,9663 (Plateau 3,958..3,973), --synth fenster BESTANDEN.
- Gaube: Dachebene RANSAC, 5 Blobs, --synth gaube BESTANDEN (Fehler w 0,028 h1 0,006 m 0,001; Synth ohne Dachpunkte unter der Gaube). Echte Formfamilie offen.
- kanten_tor --synth: Fall 1 (Mittel-Kaempfer hoeher) und 2 (Wolke leer) BESTANDEN, Fall 3 (Wolke widerspricht) FEHLGESCHLAGEN.
- Offen: Vorhangbogen-Koepfe je Licht (Kopf derzeit Giebellinien), M-6120-Regression, Baluster 68/0,306 erneut, Konsole/Pfeiler Synth, Overlays kanten_tor_*_entwurf.jpg ungesehen.

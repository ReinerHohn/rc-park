---
name: wolke-tore
description: Pruef-Tore nach jedem SfM-Modell und jeder dichten Wolke (RC-Park) - Zerfall, Abdeckung, Grundriss, GPS, Seiten. Verwenden, bevor ein Modell bewertet oder weiterverarbeitet wird.
---
Reihenfolge (Lehre Schwabentor 15.11.):
1. Zerfall: `/media/oem/scan/venv-colmap/bin/python -I tools/modell_zerlegen.py <sparse/0>` (rc 3 = mehrere punktlose Stuecke; erst zerlegen, dann bewerten).
2. `tools/kamera_abdeckung.py <sparse>` - Luecke > 90 Grad = Seite ungesehen -> Skill fassaden (Fotos suchen).
3. `tools/wolke_grundriss_pruefen.py <objekt.json> --wolke <npy>` - rc 3 = Wolkenhaufen auf der Strasse = falsch verortetes Teilnetz, nicht modellieren.
4. `tools/lage_gps_pruefen.py <objekt.json> <SFM-AUSRICHTUNG.json>` (Massstab/Drehung, rc 3) und `tools/gps_seiten_pruefen.py` (ab 25 GPS-Bildern).
5. Hoehe `tools/hoehe_gegen_dom1.py`, `tools/gruppen_punkt_tor.py`, Draufsicht `tools/sfm_draufsicht.py` ansehen.
6. Symmetrische Bauten: Seitenverwechslung pruefen (Memory project-seitenverwechslung-symmetrie, Konsens `fremde_seite.txt`).
Ergebnis je Tor ins Logbuch; rot = nicht modellieren.

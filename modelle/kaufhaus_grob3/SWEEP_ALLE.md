# Sweep aller Bauteile (GPU, Pyramide grob->fein)

Verschiebung des Bauteils gegen die Wolke. du = entlang der Fassade, dn = senkrecht (negativ = Richtung Strasse), dz = Hoehe (Meter, Netzrahmen).
Abstand = Mittel aus Modell->Wolke und Wolke->Modell (80 % getrimmt). Ein Peak ist nur dann belastbar, wenn der zweitbeste weit entfernte Peak deutlich schlechter ist.

| Bauteil | du | dn | dz | Abstand vorher | nachher | zweitbester Peak (Abstand) | Urteil |
|---|---|---|---|---|---|---|---|
| stl_teil:fassade | +0.73 | -0.33 | +0.50 | 0.795 | 0.742 | 0.742 | offen: du,dn,dz |
| bogenreihe:laube | +0.53 | -2.24 | -2.47 | 1.081 | 0.453 | 0.456 | offen: du,dn,dz |
| erker:0 | +0.49 | -0.12 | +0.13 | 0.285 | 0.234 | 0.234 | offen: du,dz |
| erker:1 | +1.16 | -1.18 | +1.60 | 0.518 | 0.202 | 0.203 | offen: du,dn,dz |
| balkonband:haupt | -0.63 | -0.76 | +2.44 | 0.510 | 0.195 | 0.196 | offen: du,dz |
| quader:laube_rueck | +2.28 | -0.12 | +1.85 | 0.383 | 0.206 | 0.209 | offen: du,dn,dz |
| fensterreihe:eg0 | -1.40 | +0.25 | +1.70 | 0.317 | 0.076 | 0.076 | offen: du,dz |
| fensterreihe:eg1 | +1.47 | -0.23 | +2.00 | 0.225 | 0.066 | 0.067 | offen: du,dz |
| fensterreihe:eg2 | +0.33 | -0.67 | +2.41 | 0.153 | 0.066 | 0.075 | offen: du,dz |
| stl_teil:figuren | +0.34 | -0.26 | +0.98 | 0.368 | 0.286 | 0.291 | offen: du,dz |
| gaubenreihe:unten | +2.16 | +1.23 | -2.34 | 0.652 | 0.450 | 0.452 | offen: du,dn,dz |
| gaubenreihe:oben | -0.41 | +1.39 | -2.41 | 0.640 | 0.455 | 0.456 | offen: du,dn,dz |
| stl_teil:helme_w | | | | | | | FEHLER:                                                              |
| stl_teil:helme_o | | | | | | | FEHLER:                                                              |
| staffelgiebel:ost | | | | | | | FEHLER:                                                              |
| staffelgiebel:west | | | | | | | FEHLER:                                                              |
| fensterreihe:og | | | | | | | FEHLER:                                                              |

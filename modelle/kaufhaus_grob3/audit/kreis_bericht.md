# Kreis1 Dienste Laubenrueckwand (quader:laube_rueck) 11.11.
## 1 Formbeschreibung (Stufe 0)
Fotos: 6120, 6117, 6119 (Uebersicht/Nah u 3,59 und 9,745), 6130, 6145, 6174, h11_111518 (u -2,43), 6124, 6161 (u -8,45). Projektion der Achsen (u 9,745/3,72/-2,30/-8,32, n 7,336) in alle Fotos: Achsen treffen die Dienste.
Zonen: Sockel (r 0,215, z 2,21-2,97, gedreht/kanneliert) - Schaft r 0,185 bis z 5,6 - Rippenbuendel darueber. Querschnitt: Halbrund an der Wand n 7,28. Familie: vorhandenes zylinder (anbau, radius/radius_oben), keine neue.
Abweichung: Dienst u 3,59 hat keinen Schaft bis zum Boden: Rippenbuendel verjuengt sich zu einer goldenen Muschel (z 5,03), darunter glatte Wand/Portalrahmen (6119, 6117, 6120). Modell hatte nur 2 Dienste (9,745/-2,30).
## 2 Zaehlungen
Sichtzaehlung an Fotos (kein neues Z-Protokoll, ANNAHME/ehrlich: nicht per foto_zaehlung): 4 Dienste sichtbar (3,59 / 9,745 / -2,43 / -8,455); u 15,77 hinter Endpfeiler in allen Fotos verdeckt -> nicht gebaut.
## 3 Pruefungen (vorher -> nachher)
- dienst_laube_um845_reich_z44/z26 (M-6124-021): 0,38 ROT -> 0,62/0,65 (Soll 0,565-0,685 / 0,6-0,72)
- dienst_laube_u359_reich_z53 (M-6119-018): 0,38 ROT -> 0,59 (Soll 0,565-0,685)
- dienst_laube_u359_reich_z35 Sperre (kein Schaft): 0,34 -> 0,34 (Soll 0,3-0,45)
- dienst_laube_um243_reich_z44/z26 (M-6130-008): gruen/gruen (0,62/0,65)
- laube_decke_u363: Suchstart 5,2->5,7 (Konsole im Strahl), Soll unveraendert 4,857-5,157, 4,87 gruen
bauen_abnehmen: alle Pruefungen bestanden.
Foto-F1 (halbe Aufl., 10 Torfotos, quader__laube_rueck): 0,619 -> 0,623; f1_h 0,531 -> 0,540; f1_fein 0,064 -> 0,063 (Tor: nicht fallen).
## 4 Overlays
/media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_184947dienste/overlays/zylinder__dienst_laube_um845_schaft_{6124,6161,6130}.jpg, ..._u359_konsole_{6119,6120,6117}.jpg, ..._um230_schaft_{6130,6145,6174,6124}.jpg, ..._u975_schaft_{6120,6117}.jpg; Torbilder /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_184947dienste/ff_eigen_bilder, Vorher /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_184947dienste/ff_vorher_bilder; Projektionen /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_dienste/p_*.jpg; audit/seiten.jpg angesehen (unauffaellig).
## 5 Fehlerliste
trifft: Dienst u 9,745, -2,43 (3 Fotos), Konsole 3,59 (Muschelhoehe 3 Fotos), Schaftlage -8,455 in 6124 (Overlay).
trifft nicht/offen: Konsolen-Radius unten 0,12 (ANNAHME), Sockel u -8,455 Masse = ANNAHME gleich wie 9,745, u -8,455 nur 9,6 Grad Peilung (+-0,33), Rippenvorsprung, Fenster-Kreuzstock, Portal, Rippen-Uebergang.
ungeprueft: Dienst u 15,77; foto_diff, fehlteile_finden, regression.py (keine Werkzeugaenderung); teile_lage_pruefen: Dienste Median 0,04-0,07 m (ok), neue Teile nicht in der Ausgabe gesichtet.
## 6 Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (um230 u -2,433; +3 Bauteile), masstabelle.json (6 Messungen/Pruefungen, Suchstart laube_decke_u363, Beobachtung erledigt), messprotokoll M-6119-018, M-6130-007 (unbrauchbar, 7 Grad), M-6130-008, M-6124-021, NICHTS_GEBRACHT.md, REZEPT (L-KR34), audit/kreis_bericht.md.
## 7 Generalisierte Lehre
L-KR34 | Gleichartige Elemente einzeln pruefen, Schnittwinkel angeben | foto_mass --tri; Baseline mit --teile_dir/--stl.

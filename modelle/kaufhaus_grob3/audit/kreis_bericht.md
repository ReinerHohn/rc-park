# Kreis3 quader:laube_sockel_w (12.11.)
## 1 Formbeschreibung (Fotos 6130 Nahfoto, 6124 Nah, 6145 Uebersicht; Raster Ebene n 7,73 aus K-Kameras, Skript agent_scratch_kreis3/gitter.py)
Zonen unten->oben: Steinbank u -7..-1,5 (Rechteckquerschnitt, Sockelfront n 7,73); Fuellungsfelder mit senkrechten Fugen; Gesimsband z 2,04-2,2 (schon im Profil). Zwei gerahmte Tuerchen mit eingelassener Fuellung (u -5,05..-5,62 und -5,75..-6,30, z 1,57..1,97) sind in 6130, 6124, 6145 gleich zu sehen. Ostende u -1,5 am Raster in 6130 bestaetigt (Ueberstand-Rot dort nicht als Fehler bestaetigt, nicht weiter bearbeitet).
Formfamilie: vorhandenes quader mit neuer generischer Option `aussparungen` (Vertiefungen in der eigenen Vorderflaeche, geschachtelt = Rahmen + Fuellung; baukasten_gen.quader_bt). Tiefen 0,03/0,06 = ANNAHME.
## 2 Zaehlungen
Tuerchen: 2 (in 3 Fotos per Raster/Sicht gezaehlt; KEIN Z-Protokoll via foto_zaehlung.py - nicht gelaufen). Fuellungsfelder und Fugen: NICHT gezaehlt (Fugen u -4,55 und -6,43 nur in 2 Fotos sicher) -> offen.
## 3 Pruefungen (teil_fotoform, volle Aufloesung, 10 Torfotos)
| Mass | vorher | nachher |
|---|---|---|
| f1_fein (Tor, >= +0,010) | 0,554 | 0,618 |
| F1 | 0,815 | 0,815 |
| f1_h | 0,786 | 0,786 |
f1_fein steigt in allen 10 Fotos. Keine neue masstabelle-Pruefung angelegt (Stufe 3 nicht erfuellt). bauen_abnehmen: alle Pruefungen bestanden.
## 4 Overlays
/media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261112_055730a055730/ff_eigen_bilder/quader__laube_sockel_w_{6130,6124,6145}{,_fein}.jpg (angesehen: 6130_fein, 6124_fein, Rahmen decken sich mit Fotokanten); Raster: /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis3/g{6130,6124,6145,6176}.jpg
## 5 Fehlerliste
trifft: Tuerchen-Rahmen/-Fuellung Lage in 6130, 6124. ungeprueft: 6145 Overlay, teile_lage_pruefen, foto_diff, fehlteile_finden, Sichtblatt seiten.jpg. trifft nicht/offen: Fuellungsfelder-Rahmen, Fugen, Wulst unter dem Band, Bandunterkante gelb, Westende u -7,2 ANNAHME, Beobachtung bewusst NICHT als erledigt markiert (nur Tuerchen behoben).
## 6 Geaenderte Dateien
tools/baukasten_gen.py (aussparungen), modelle/kaufhaus_grob3/objekt.json (4 Aussparungen am Teil), diese Datei; automatische Abnahmeartefakte.
## 7 Generalisierte Lehre
Lehre: Aussparung muss auf die lokale Vorderflaeche (n_front) bezogen sein, nicht auf das Huellmaximum des Profils (Band) - sonst Schnitt ohne Wirkung und identische Kennzahl | Anlass: erster Lauf f1_fein unveraendert 0,554 | Werkzeug: baukasten_gen quader aussparungen.n_front; Kontrolle Volumen vorher/nachher.

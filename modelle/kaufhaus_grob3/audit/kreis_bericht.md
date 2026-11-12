# Bericht kreis2 Lauf 070036 r2 - quader:laube_sockel_w

## 1. Formbeschreibung
Fotos 6130 (Nah, frontal), 6145 (Uebersicht), h11_112108 (schraeg), zusaetzlich 6124. Rektifizierte Front (Ebene n 7,73): Steinsockel unter dem Gesimsband, 2 gerahmte Tuerchen im Westteil, Ostteil mit senkrechten Steinfugen. Formfamilie: vorhandenes Quader-Profil mit `aussparungen` (schmale Nuten), keine neue Familie. Rest (Wulst, Fuellungsfelder, Schild, Westende) nicht bearbeitet.
## 2. Zaehlungen
Z-6130-002, Z-6145-003, Z-h11_112108-001: je 4 Fugen in u -4,9..-1,6 (u -4,55; -2,94; -2,78 doppelte Linie; -1,88). Markierte Bilder 6130 angesehen; 6145/112108 nicht einzeln angesehen. Fuge -2,50 nicht gebaut (Fotos widersprechen sich, Regel 5).
## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| sockel_fugen_anzahl | 1 | 4 | 4 | Z-6130-002 u.a. |
| f1_fein (10 Torfotos, voll) | 0,636 | 0,655 | +0,011 | teil_fotoform |
| Foto-F1 / f1_h | 0,816 / 0,784 | 0,816 / 0,784 | - | |
bauen_abnehmen.sh: alle Pruefungen bestanden (Log /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261112_070036a070036/abnahme_r2.log; freiraum_audit-Fehler war schon vorher da).
## 4. Overlays
/media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261112_070036a070036/ff_r2_bilder/quader__laube_sockel_w_{6130,6145,h11_112108}{,_fein}.jpg (6130_fein und 112108_fein angesehen: neue Fugen decken Fotonaht)
## 5. Fehlerliste
trifft: Fugen -4,55/-2,94/-2,78/-1,88 (6130, 112108). ungeprueft: 6145-Overlay, Lage laengs t (marge nicht neu gemessen), foto_diff, fehlteile_finden. trifft nicht/offen: Wulst/Bandunterkante, Westende (ANNAHME), Schild Tuerchen 2, vertiefte Fuellungsfelder, Fugen westlich -6,43, Fuge -2,50. Fugenbreite 0,04/Tiefe 0,02 ANNAHME. teile_lage_pruefen: Median 0,12 m (<0,4).
## 6. Geaenderte Dateien
objekt.json (+30 Zeilen, Textedit), masstabelle.json (Messung sockel_fugen, Pruefung, erledigt_teil), messprotokoll/Z-*, REZEPT (L-KR43), Build-Artefakte (audit, MASSNACHWEIS).
## 7. Generalisierte Lehre
L-KR43 | Struktur-Pruefung fuer rotierte Front: Rahmen per STL-Vorher/Nachher bestimmen | ebene_oeffnungen

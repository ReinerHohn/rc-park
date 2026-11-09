# LOG Kantengitter -> Generator kaufhaus_grob3 (Agent, 2026-11-09, ~90 min)

Auftrag: gemessene Groessen aus dem 3D-Kantengitter (lot2) als Quelle `kantengitter` in die Masstabelle bringen und den parametrischen Generator damit neu bauen (Hybrid: Wolke/Gitter legt Lage fest, Form aus Fotos).

## 1. Rahmenbeweis (lot2 = Generatorrahmen)
- Generator (`tools/baukasten_gen.py`, parametrische Bauteile): u = achse_n um -90 Grad, achse_n = (0.3338, 0.9426), Ursprung 0/0, z wie Wolke. Rohkoerper/Fenster-Erker-JSON: u = (0.9423, -0.3347), n = (0.3347, 0.9423) -> gleiche Konvention, Winkelabweichung 0,06 Grad.
- Zahlenbeweis: Gitter-Frontebene off 12,66 = fensterreihe:og wand_n 12,666 (unabhaengig vorher gesetzt); Gitter-Pfeiler along -8,52/-2,51/3,51/9,50/15,56 = bogenreihe u0 -8,79 + i*6,14 (alt); Erker-Mitten -8,35/15,67 vs alt -8,63/15,72.
- Bildbeweis: `audit/gitter_generator/vorher_*.jpg` / `nachher_*.jpg` (Modellkanten rot via `modell_foto_overlay.py` + Gitter gelb via `gitter_overlay.py`, beide mit `sfm/kam_lot2.json`) - Gitter und Modell liegen im selben Foto deckungsgleich auf den Fotokanten. Masse direkt uebertragbar, keine Transformation noetig. In objekt.json als `rahmen_hinweis_lot2` dokumentiert.
- Pruefstand-Falle: `pruefstand.lade_modell` setzt z = 0 auf die MODELLUNTERKANTE (hier alte Fassaden-STL bei lot2 1,34). Alle Gitter-Hoehen in der Tabelle laufen deshalb ueber die Konstante `z_unterkante_lot2 = 1.34` (Hinweis `_rahmen_hinweis` in der Tabelle; aendert sich das tiefste Bauteil, muss die Konstante nachgezogen werden).

## 2. Befund an der objekt.json (vorher)
- `masstabelle`/`elemente`/`audit`/`ueberwacht` zeigten auf `modelle/kaufhaus_grob/` (Kopierrest): der Pruefstand las fuer grob3 die falsche Tabelle und schrieb Bericht/Nachweis in den falschen Ordner. -> auf `kaufhaus_grob3/` gesetzt.
- Pruefstand stuerzte seit 8.11. ab: Beobachtungen vom 8.11. ohne Feld `wer` (KeyError in Zeile 545) -> `wer` aus `quelle` ergaenzt (Daten, kein Werkzeugeingriff).
- Alte Gesamthoehen-Pruefung (Soll 18,8-19,8 aus mvs_d03_fix im 25 Grad gekippten Netzrahmen, BS150) -> `status: widerspruch` mit Begruendung, Soll NICHT gelockert (Regel 5).

## 3. Geaenderte Generatorparameter (alt -> neu, Quelle), alle mit `werte_quellen` + `historie` je Bauteil
| Bauteil | Parameter | alt | neu | Quelle |
|---|---|---|---|---|
| satteldach:haupt | z_first / n_first | 21,65 / 7,35 | 27,51 / 3,05 | rohkoerper_v7 first (Firstkante 35 m; Rohsegmente Median 27,29 @ 3,38) |
| | z_traufe_v / n_traufe_v | 14,80 / 12,60 | 14,68 / 12,66 | traufe.kante (50,8 m), off_front (392 m) |
| | u0 / u1 | -6,36 / 11,24 | -8,82 / 17,15 | Endebenen (Ost 'plus' UNSICHER) |
| | symmetrisch | - | true | ANNAHME Firstspiegel (Rueckhang unsichtbar) |
| staffelgiebel:west | u_aussen / z_spitze / n_hinten / n_vorn / z_traufe | -9,20 / 20,22 / 5,89 / 14,69 / 9,84 | -8,82 / 29,32 / 2,83 / 12,73 / 16,45 | Endebene, Gittermaximum Westende, 7 Steiger-Cluster |
| staffelgiebel:ost | dito | 9,29 (!) / 21,36 / 6,35 / 13,71 / 12,95 | 17,15 / 28,98 / 2,69 / 12,73 / 16,45 | Endebene Ost, Gittermaximum Ostende; Stufen = ANNAHME Spiegel |
| erker:0 / erker:1 | mitte_u | -8,63 / 15,72 | -8,35 / 15,67 | fenster_erker_v9 Pfostencluster |
| | breite / auskragung | 2,66-2,75 / 0,65-0,95 | 3,74 / 1,18 | erker_gemeinsam x_wand, tiefe |
| | unterkante / oberkante / spitze | 7,56-7,72 / 9,54-10,94 / 21,37 | 9,62 / 13,18 / 14,67-15,09 (= Helmfuss) | z_unten, z_oben (Gesims), helme z_fuss; dachprofil = ANNAHME Schaft bis Helmkreis |
| stl_teil:helme_w/o | du, dn, dz, sz | 1,60/-1,36/2,76/1,197; 6,14/-1,06/2,92/1,184 | 1,72/-2,46/3,33/1,231; 6,11/-2,30/3,45/1,258 | helme cx/cy (Achse), z_spitze 22,34/22,78, Koerperunterkante 9,62 |
| bogenreihe:laube | u0 / pitch | -8,79 / 6,14 | -8,52 / 6,022 | saeulen_fit 5 Frontpfeiler |
| | pfeiler_breite/tiefe / pfeiler_n | 1,09/0,64 / 12,95 | 0,881/0,881 / 12,19 | gemeinsamer R 0,44 (7 Pfeiler), Achs-Offset |
| | oeffnung_breite / kaempfer_z / scheitel_z / oberkante_z | 3,47 / 3,64 / 7,24 / 7,44 | 5,13 / 5,46 / 7,20 / 8,0 | arkaden_fit Rundbogen R 2,76, zc 4,44 (Kaempfer abgeleitet: Bogen trifft Pfeilerrand); Vorsprung-Unterkante 8,0 |
| quader:laube_rueck | n0 / n1 / z1 | 9,0 / 9,45 / 4,85 | 6,09 / 6,54 / 8,0 | Ebene laube_rueckwand 6,54 (belegt, 30 m) |
| fensterreihe:eg0-2 | wand_n | 9,45 | 6,54 | dito |
| balkonband:haupt | wand_n / auskragung / unterseite / oberseite / u_von / u_bis | 13,44 / 0,77 / 4,91 / 9,55 / -5,33 / 11,95 | 12,66 / 1,20 / 8,0 / 10,0 / -7,6 / 14,92 | Vorsprung-Ebene 13,86 z 8-10 (0,5-m-Band), Erkerfronten |
| fensterreihe:og | u_mitte / pitch / breite | -4,32 / 3,90 / 2,40 | -4,45 / 3,96 / 3,33 | 5 Gruppen (fotobelegt), 3x0,912 + 4x0,147 |
| | unterseite / kaempfer / scheitel / riegel_z | 10,06 / 11,84 / 13,68 / 11,06 | 10,31 / 11,72 / 13,31 / 11,72 | Pfostenfuss, Horizontalen 69,9 / 29,1 m |
| | rahmen_b / pfosten_b / n_lichter / kontur | 0,089 / 0,061 / (2) / Kielbogen | 0,147 / 0,147 / 3 / Vorhangbogen-Profil (33 Punkte) | b_rahmen, n_licht, Bekroenungsprofil |
| stl_teil:fassade, :figuren | dn | 0,0 / -0,83 | -1,0 / -1,83 | alte Wand lag bei off 13,27-13,95, Frontebene 12,66 (OG-Fenster steckten in der Wand) |

Generator: `fensterreihe` um optionales `n_lichter` erweitert (Standard 2 = Altverhalten bitgleich, Mittelpfosten bei uc). `tools/regression.py modelle/kaufhaus_grob3/objekt.json --pruefen`: "identisch - nichts verloren" (grob3 ist das einzige Objekt mit fensterreihe; Kette dort leer).

## 4. Masstabelle (`modelle/kaufhaus_grob3/masstabelle.json`)
Quelle `kantengitter` als Quelltyp `sfm_bodenanker` (SfM-Rahmen, Massstab `sfm_buendel`; `foto_kalibriert` waere falsch: keine amtlichen Anker), `protokoll` = JSON-Pfad + Kennzahl. 10 neue Pruefungen (Messer `max_z_im_bereich`/`min_im_bereich`/`kreis_durchmesser_im_bereich`, Kaesten aus along/off in Modell-xy umgerechnet):
First 27,51 | Giebel W 29,32 | Giebel O 28,98 | Helm W 22,34 | Helm O 22,77 | Vorderhang z(off 11,0) 17,21 (Traufe+Neigung) | Pfeiler-D 0,88 | Arkade-Scheitel 7,18 | Fenster-Sohlbank 10,31 | Erker-Unterkante 9,52.
- Methode Schritt 2 eingehalten: am ALTEN STL (`scratchpad/vorher_kaufhaus_grob3_1-87.stl`) waren 8 von 10 rot/nan (First 12,48, Giebel 0, Helme 20,0, Pfeiler nan ...), nur Vorderhang und Erker-Unterkante zufaellig gruen.
- Messfallen beim Anlegen (alle in `historie`): Zylinder hat Eckpunkte nur an den Ringen (Schaft = nan -> Ring ueber der Fase bei z 2,2); verschobene Fassaden-STL-Wand verfaelschte den Kreisfit (Rueckhaelfte messen); Erker-Unterkante liegt zwischen den Erkern im Balkonband (freies Westende messen); min_im_bereich braucht Eckpunkte (Rahmen-Aussenkante statt Mitte).
- Ergebnis nach Bau: **alle Pruefungen bestanden | 1 Widerspruch (Alt-Gesamthoehe) | 13 Beobachtungen offen**. `bauen_abnehmen.sh` gruen bis auf freiraum_audit (SFM-AUSRICHTUNG-buendel.json fehlt in grob3 - war vorher schon so) und test_regeln_cb OK.

## 5. Sichtbefund (ANGESEHEN)
- `audit/seiten.jpg`: 5 Ansichten - Satteldach jetzt voll (First auf Hoehe der Giebelspitzen minus 1,8 m), Staffelgiebel an beiden Enden, Laube mit 4 Rundboegen und 5 runden Pfeilern, Fensterband 5x3 mit Vorhangbogen, Erker mit Nadeln; Rueckseite = Spiegel (nackt, Annahme).
- `audit/gitter_generator/vergleich_ip_IMG_6261.jpg` und `vergleich_ip_IMG_6161.jpg` (links vorher, rechts nachher, rot Modell / gelb Gitter): vorher endete das Dach als Pultdach auf halber Hoehe, Ostgiebel sass bei u 9,3 (Dachmitte), Erker/Helme 1 m zu niedrig, Pfeiler 0,75 m vor der Fassade. Nachher liegen First, Giebelstufen, Helmnadeln, Pfeiler, Boegen und Fensterband auf den Gitterlinien/Fotokanten; Nadeln in 6161 noch ~30 px gegen das Gitter versetzt (alte STL-Form).
- `foto_diff.py` / `fehlteile_finden.py` NICHT lauffaehig: beide brauchen `messprotokoll/K-<nr>.json` (Kamera aus amtlichen Ankern), grob3 hat keine; Ersatz = Overlay mit kam_lot2. Offen: Kamera-Bruecke kam_lot2 -> K-Protokolle (kameras_aus_buendel.py pruefen).

## 6. Offene Widersprueche / was das Gitter NICHT liefert (als `beobachtungen_offen` eingetragen)
1. Laubentiefe 6,1 (Gitter-Rueckwand 6,54, belegt) vs 3,2 (Wolkenmessung 8.11. im gekippten Netz) - Generator folgt dem Gitter; alte g_waende (8 m tiefer Rumpf) bleibt widerspruechlich.
2. Rueckseite/Gebaeudetiefe: Gitter sieht keine Rueckseite, off_back -6,56 = Firstspiegel-Annahme; LoD2 (Grundrisskante 12,54, First-Traufe 11,75 vs 12,8) nicht abgeglichen; lot2-z gegen DGM1 unbekannt.
3. Ostende 'plus' unsicher; Ost-Staffelgiebelstufen = Spiegelannahme.
4. "3 Lichter je Gruppe" aus dem Gitter, kein Z-Zaehlprotokoll (Regel 9) -> foto_zaehlung auf 6120 nachziehen.
5. Helm-STL = alte Erker+Nadel-Form (Nadel 0,2-0,5 m statt Kegel r 0,85; Gesims ~13,7 statt 13,18 bei einer Skala) -> parametrischer Kegel aus dem Gitter-Fit.
6. Gauben (t 0,07/0,33 am alten halben Dach gefittet, Gitter hat keine abgenommenen Gauben), Boden (1,45 Altwert; Gitter 1,5-2,7), Baluster (Hinweis 0,287 m, unverifiziert), Sockel/Laibung der Pfeiler, Figuren, Ziegel: Hand/Wolke bleibt.
7. Nicht wasserdicht (Rohdreiecke der stl_teil-Gruppen, Druckreparatur meldet sich) - unveraendert, kein Druckziel.

## 7. Dateien
- geaendert: `modelle/kaufhaus_grob3/objekt.json` (Sicherung `objekt.json.gitter_bak`), `masstabelle.json` (`masstabelle.json.gitter_bak`), `tools/baukasten_gen.py` (fensterreihe n_lichter), neu gebaut `modelle/stl/kaufhaus_grob3_1-87.stl`, `elemente.json`, `pruefbericht.json`, `MASSNACHWEIS.md`, `audit/seiten.jpg`.
- Bilder: `modelle/kaufhaus_grob3/audit/gitter_generator/{vorher,nachher,vergleich}_ip_IMG_{6261,6161}.jpg`.
- Skripte (Scratchpad, nicht im Repo): `objekt_gitter_setzen.py`, `masstabelle_gitter.py`; altes STL `vorher_kaufhaus_grob3_1-87.stl`.
- Kein Commit.

# Runde 2 (Agent, 2026-11-09, ~90 min): Zaehlprotokolle, Helm-Kegel, Bruestung, Gaubenlagen, Kamera-Bruecke
Abgrenzung (Koordinator): Fenster-/Gaubenform macht der muster_fit-Agent; hier nur Zaehlprotokoll, Fensterraster, Gaubenlagen, Helme, Bruestung, Kamera-Bruecke. Kein Gauben-Formfit gebaut.

## 1. Zaehlprotokolle Regel 9 (tools/foto_zaehlung.py, ANGESEHEN)
- Fotos als `<nr>_*.jpg`-Symlinks im fotos-Ordner (/media/oem/scan/rc-park_daten/kaufhaus/fotos): 6120_ip_IMG_6120, 6261_ip_IMG_6261, hc12_an_handy_2026-11-06_c_handy_c_12 (foto_zaehlung/foto_diff suchen `fotos_dir/<nr>_*`).
- `Z-6120-002` (Gruppen 2+3 voll, 1+4 angeschnitten): 3 Lichter je Gruppe; `Z-6261-001` (5 Gruppen voll): 3; `Z-hc12-001` (5 Gruppen voll, frontal): 3. Erste Fassungen lagen falsch (6120: y auf der Balkonplatte; hc12: dritter Punkt je Gruppe auf der Figur; 6261: G5 auf Figur 4) -> am Protokollbild erkannt, mit --nr ueberschrieben, zweite Fassung ANGESEHEN: alle Punkte auf Lichtern.
- Eingetragen: fensterreihe:og `zaehlung` + werte_quellen n_lichter; neue Pruefung "Fenstergruppe 2: Lichter je Gruppe" (Messer `ebene_oeffnungen` auf der Rahmenfront 12,81, z 12,0, u +-1,75; foto_vollbild/anzahl, protokoll Z-6261-001) -> Ist 3.
  Drei Fehlschlaege bis dahin (alle in historie): (a) alte Fassaden-STL-Wand stand nach dn -1,0 buendig vor der Rahmenfront (12,9) -> Wand auf die Gitter-Frontebene 12,65 (dn -1,3), Rahmentiefe 0,15 (fenster_erker ANNAHME); (b) Verglasungsplatte (glas_d 0,10 bei glas_n 0,135) lag VOR der Rahmenfront und schloss die Lichter -> Glas in die Wandebene (glas_n 0, glas_d 0,03; Oeffnungstiefe 0,12 ~ Gitter-ANNAHME 0,1); (c) p10-Ebene wurde von der Figurenkonsole links (off 12,96) gestellt, der ganze Rahmen zaehlte als eine Oeffnung -> u-Bereich auf die Gruppe begrenzt.
- Baluster: `bruestung:balkon` (neuer generischer Bauteiltyp `bruestung` in baukasten_gen.py: Zylinderreihe + Handlauf): 68 Baluster (Z-6120-001: 11 je Feld, 28/28 Punkte getroffen; baluster_abgenommen anzahl_modell_zwischen_erkern), u0 -6,808, Periode 0,3062, n 13,84, r 0,072 (Profil 0,070-0,074), Platte bis 8,37 / Handlauf 9,48-9,71 (Koordinator aus Balusterband 8,35-9,65, nicht eigens gemessen). balkonband oberseite 10,0 -> 8,37 (Platte). Pruefung "Handlauf Oberkante" 9,71 OK. Keine Zaehlpruefung "11 je Feld" moeglich: das Modell hat keine Bruestungspfosten (Pruefstand-Lint wuerde 68 gegen je_flaeche 11 ablehnen) -> Pfosten als offener Punkt.
## 2. Helme
- `zylinder:helm_w/o` (Kegel radius 0,844/0,846 -> 0,02) aus formen/helme.json: Achse along -8,56/15,53, off 12,22/12,23, Fuss 14,67/15,09, Spitze 22,34/22,78 (fotogeprueft). Alte Nadel-STL-Gruppen `stl_teil:helme_w/o` inaktiv mit `ersetzt_durch` (nicht ersatzlos). Erkerkoerper = erker:0/1 (Schaft bis Helmfuss, ANNAHME).
- Widerspruch Helmfuss (Koerper-Agent: Foto ~r 1,6 vs Fit 0,85) als beobachtungen_offen, NICHT gemittelt; Messung `helm_w_fussbreite` nur zur Beobachtung. foto_mass nicht anwendbar: `--ebene` kennt nur x=/y=-Ebenen, die Erkerkante liegt in der gedrehten Fassadenebene.
## 3. Gaubenlagen
- formen/gauben_r3_lagen.json (5 Dreiecke, Basis liegt auf der Dachflaeche): unten along -3,15/2,90/9,16 (Off 10,3, z 17,9 = 3,2 m ueber Traufe), oben 0,89/6,94 (Off 8,1-8,4, z 20,4-20,9). gaubenreihe:unten u_mitte 2,97 pitch 6,153 t 0,264; oben 3,91 / 6,053 / 0,493. Form = Altwert (ANNAHME) bis muster_fit. Koordinator-Werte (t -9,08/... , 1,9-2,7 m) haben eine andere Bezugsachse -> JSON-Geometrie direkt im lot2-Rahmen genommen (Beobachtung).
## 4. Kamera-Bruecke
- `messprotokoll/K-6120.json`, `K-6261.json` aus sfm/kam_lot2.json (rvec aus Rn, t, f_px, cx, cy, bild, k1 = SIMPLE_RADIAL params[3], ankerzone_z 1,5-29,5 = Gebaeude; Quelle sfm_buendel lot2, KEINE amtlichen Anker). Kamerahoehe 3,63/3,69 m ueber lot2-Boden 1,5 (Stativ/hoch gehalten plausibel). objekt.json fotos 6120/6261/hc12 ergaenzt (seite +y).
- bauen_abnehmen laeuft damit fehlteile_finden + foto_breitenprofil automatisch; foto_diff manuell (`--gpu`).
- fehlteile 6261 (ANGESEHEN audit/fehlteile_6261.jpg): 6x ERFUNDEN score -1,0 bei along 15,6-16,5 / off 4,7-5,5 / z 18,4-21,8 = glatte RUECKFLANKE des Ost-Staffelgiebels (Modell: Giebelscheibe nur vorderer Hang, Rueckflanke = glatte Satteldach-Stirn; Foto zeigt beidseitig Stufen). Gleiches am Westgiebel (foto_diff rot). 6120: 1 ERFUNDEN (Konsolenzone oben links), blaue Zellen unter den Boegen (Bogenband/Altwand).
- foto_diff 6261 (ANGESEHEN audit/foto_diff_6261.jpg; gruen = Modellkante mit Fotokante, rot = ohne, gelb = Fotokante ohne Modell): gruen Arkaden, Pfeiler, Erker, First, Giebelstufen vorn; rot Giebel-Rueckflanken West/Ost, linker Bogen-Intrados (Arkade 1 leicht versetzt), Pfeiler-/Laubenkante links (8); gelb Fenstermasswerk, Figuren, Baluster, Nachbarhaus. 6120: gruen Boegen/Pfeiler/Kaempferriegel/Baluster-Schaefte; rot Balkonunterkante (Modellkante 8,0 statt Konsolen) und Bruestungs-PFOSTEN (fehlen), Bogen-Intrados Mitte; gelb Fenstermasswerk, Figuren, EG-Fenster-Sprossen. Zahlen siehe audit/foto_diff_*.json (Lauf auf dem finalen STL).
## 5. Rueckseite/LoD2: nur dokumentiert (beobachtungen_offen: off_back Firstspiegel-ANNAHME, LoD2 Kante 12,54 vs Tiefe 19,2, First-Traufe 11,75 vs 12,83). Zusatzbefund: die Giebel-RUECKFLANKEN sind im Foto 6261 sichtbar gestuft (fehlteile/foto_diff) -> der staffelgiebel-Typ braucht eine Spiegeloption (n_vorn < n_hinten derzeit verboten); nicht gebaut (Auftrag: nichts aendern).
## 6. Ergebnis
- Pruefstand: **alle 13 Pruefungen bestanden** (neu: Lichter je Gruppe 3, Handlauf 9,71; alle Runde-1-Zeilen unveraendert gruen) | 1 Widerspruch (Alt-Gesamthoehe) | 17 Beobachtungen offen. test_regeln_cb OK; regression.py nach baukasten_gen-Aenderung (bruestung neu, fensterreihe unveraendert) "identisch".
- Sichtblatt seiten.jpg ANGESEHEN: Balkon mit Balustern + Handlauf, Helmkegel auf den Erkern, Gauben 3+2 auf dem Vorderhang. Overlays `audit/gitter_generator/runde2_ip_IMG_6261.jpg`, `runde2_ip_IMG_6120.jpg`, Vergleich `vergleich_runde1_runde2_ip_IMG_6261.jpg`.
- Dateien: objekt.json, masstabelle.json, tools/baukasten_gen.py (bruestung), messprotokoll/K-6120, K-6261, Z-6120-002, Z-6261-001, Z-hc12-001 (+jpg), STL/elemente/pruefbericht/MASSNACHWEIS neu. Kein Commit.
- Offen: Bruestungspfosten (Felder) als Bauteil; Konsolen unter dem Balkon; Giebel-Rueckflanken gestuft; Helmfuss-Widerspruch; Gauben-/Fensterform (muster_fit-Agent); Alt-Fassadengruppe (Rumpf 8 m) durch Gitter-Rumpf ersetzen.
- foto_diff finales STL (tol 0,35 m): 6120 Modellkanten ohne Fotokante 14,7 %, Fotokanten ohne Modell 44,6 %; 6261 20,1 % / 47,0 % (Masswerk/Figuren/Baluster-Detail fehlt dem H0-Modell). Hinweis: foto_diff/fehlteile beschriften die Kamera fest als "K-<nr> (amtliche Anker)" - fuer K-6120/K-6261 ist das SfM (kam_lot2), siehe K-Datei `quelle`.

## Runde 3 (Pruefer-Befund am Sichtblatt; Agent, 2026-11-09)

Ablauf nach Regel 2: zuerst 4 Beobachtungen + 6 Pruefungen eingetragen, am Runde-2-Modell gelaufen -> alle 6 FEHLER (Dachueberstand 11,13 m; Rueckwand n 4,57; Giebel-Verhaeltnis 0,89; Tuer 0; Baluster je Feld 13; Fensterlichter 0). Dann Werkzeug + Generator geaendert, gebaut: **alle Pruefungen bestanden (24 Zeilen), 1 Widerspruch (Alt-Gesamthoehe), 28 Beobachtungen**, test_regeln_cb OK.

### Werkzeugaenderungen (generisch, Regression vor jeder Objektaenderung: "identisch - nichts verloren")
- `tools/baukasten_gen.py`: `bruestung` optional Pfosten (`pfosten_alle`, `pfosten_erster`, `pfosten_b`, `pfosten_t`; Pfosten ersetzt den Baluster auf seinem Rasterplatz, eigener beleg); `staffelgiebel` optional `spiegel` (Rueckflanke = Spiegel der Vorderflanke an der Spitzenmitte, beleg nennt `werte_quellen.spiegel`).
- `tools/foto_mass.py`: `--ebene` auch beliebige Ebene `nx,ny,nz=d` (gedrehte Fassade), k1-Entzerrung aus dem K-Protokoll, markierter Ausschnitt M-*.jpg auch im Kameramodus, `massstab_von` sagt bei Kamera-Bruecken ehrlich "SfM-Buendel, KEINE amtlichen Anker".
- `tools/pruefstand.py`: neue Messart `ebene_abstand` (Lage der vordersten Flaeche hinter einer beliebigen Ebene, zaehlt nichts). Grund: `ebene_oeffnungen` ist Zaehlart, der CB-Lint sperrt sie zu Recht fuer Merkmal `druck`/`grundriss`.

### A Rumpf aus dem Gitter (Dach ragte ueber den Koerper)
- Neu `quader:rumpf_eg` (along -8,82..17,15, n -6,564..6,54, z 1,5..8,0) und `quader:rumpf_og` (n -6,564..12,66, z 7,9..14,68). Quellen: rohkoerper_v7 along_w/along_e, off_front 12,66, laube_rueckwand 6,54, traufe 14,68, z_boden 1,5; Rueckwand n -6,564 = **ANNAHME Firstspiegel** (2 x first.offset - off_front), Traufe hinten = Traufe vorn (ANNAHME).
- `stl_teil:fassade` aktiv=false, `ersetzt_durch` gesetzt. Balken/Gesims/Konsolen/Dachkante als `stl_teil:traufzone_alt` abgespalten (fester `anker_m` der alten Gruppe -> bitgleiche Lage; Konsolen unberuehrt, gehoeren dem Koerper-Agenten).
- Pruefungen: "Rumpf traegt das Dach: hinterer Dachueberstand" (modell/druck, Soll -0,1..0,8) 11,13 -> 0,00; "Rumpf-Rueckwand Lage n" (Soll -6,9..-6,2, Quelle Gitter + ANNAHME) 4,57 -> -6,57. Strahlprobe: Rueckwand bei along -8..17, z 3..14,4 durchgehend bei n -6,6.
- Folge: tiefstes Bauteil jetzt bogenreihe 1,453 -> Konstante `z_unterkante_lot2` 1,34 -> 1,453 (STL-Unterkante nachgemessen; erster Bau ohne Nachzug: 3 Hoehenzeilen 0,11 m zu tief, rot).
- **Offen**: Tiefe 19,2 m gegen LoD2 12,54 m bleibt Widerspruch - ist LoD2 richtig, ist die hintere Haelfte erfunden.

### B Staffelgiebel gespiegelt
- `spiegel: true` an Ost (Quelle Foto 6261) und West (ANNAHME wie Ost). Pruefung "Ostgiebel Rueck-/Vorderflanke Hoehe" (foto_vollbild/verhaeltnis, 0,97..1,03): 0,89 -> 1,00.
- **Ehrlich**: fehlteile_6261 meldet weiter 5 ERFUNDEN-Zellen am selben Ort. Sie liegen auf der glatten Putzflaeche des Ostgiebels nahe der Vorderecke, NICHT an der Rueckflanke -> meine Runde-2-Deutung war falsch. Ursache offen (Kandidat: Ostende 17,15 "unsicher", Ecke im Overlay ~0,5 m zu weit links). Beobachtung eingetragen.

### C EG-Laubenrueckwand Bogen 3 (along 3,5..9,5)
- Zaehlung am Foto 6120: Z-6120-003 (1 Fenster + 1 Tuer), Z-6120-004 (Kreuzstock, 2 Lichter je Zeile), Z-6120-005 (1 Tuer). Bilder angesehen; erste Fassung von -003 lag auf dem Pfosten, neu auf das Glas gesetzt.
- Lage mit foto_mass auf der Rueckwandebene 6,54 (K-6120): M-6120-001/002 Fenster along 6,25..8,29 / 6,24..8,14, z 3,20..6,45; M-6120-003 Kaempfer 5,47; M-6120-004 Tuer along 3,55..5,01, Schwelle 1,77; M-6120-005 Kaempfer 3,92 / Scheitel 4,21.
- `fensterreihe:eg1`: Spitzbogen-ANNAHME (u 6,05, b 1,26, Scheitel 7,42) -> Rechteck-Kreuzstock u 7,225, b 1,96, z 3,20..6,45, Riegel 5,47, 2 Lichter. Neu `fensterreihe:eg1_tuer` (u 4,28, Lichte 1,46) und die Nischen `quader:eg1_nische` (Tiefe 0,21) und `quader:eg1_tuer_nische` (Tiefe 0,30). Beide Tiefen sind ANNAHMEN.
- Falle: Rahmen beruehrten die Wand nur flaechig -> eigener Koerper -> Druck-Konsolenhuelle fuellte die Tuernische (Pruefung 0). Mit 0,04 m Einbindung (wand_n 6,50, tiefe 0,16) behoben; OG/eg0/eg2 haben dieselbe Lage (Beobachtung).
- Pruefungen Tuer 0 -> 1, Fensterlichter 0 -> 2. Overlay 6120: Fenster und Tuer liegen auf dem Foto. Die Boegen 1, 2 und 4 sind nicht abgenommen: eg0 und eg2 bleiben ANNAHME, und die grosse Tuer in Bogen 2 fehlt im Modell.

### D Bruestungspfosten
- M-6120-006: Pfosten-Vorderflaeche 0,26 m, Mitte along 6,96 (Vorhersage aus u0 + 45 x pitch: 6,97). M-6120-007: Luecke ueber den Pfosten = 0,64 m = 2 Perioden.
- Im Raster 12 (11 Baluster + 1 Pfosten), erster Platz 9. Damit stehen 5 Pfosten bei along -4,05 / -0,38 / 3,30 / 6,97 / 10,65; pfosten_t 0,20 ist ANNAHME.
- Pruefung "Baluster je Feld" (Z-6120-001): 13 -> 11.

### Sichtblatt seiten.jpg - Fehlerliste (angesehen nach dem Bau)
1. Ost/West: Das Dach sitzt jetzt auf dem Rumpf (Rueckwand bis zur Traufe) und beide Giebelflanken sind gestuft. Der grobe Fehler aus Runde 2 ist behoben.
2. Ost/West/Sued: Die Rueckhaelfte ist ein glatter Block ohne Fenster oder Gliederung. Die Rueckseite ist ungemessen (ANNAHME); bei LoD2 12,54 m Tiefe waere sie zu tief.
3. Sued: Hinter der Rueckwand scheinen Arkaden und OG-Fenster durch. Das ist ein Renderer-Artefakt (Punkt-Splat, grosse Flaechen duenn besetzt), kein Loch: die Strahlprobe zeigt eine geschlossene Wand.
4. Nord: Zwischen dem alten Gesims (bis 14,1) und der Traufe 14,68 liegt ein 0,6 m glattes Wandband. Die Traufzone der Alt-STL sitzt zu tief (offen).
5. Ost: Die Laube ist an der Ostseite offen, ihre Seitenwand ungeprueft.
6. Gauben, Helme und Erker sind unveraendert. Gaubenform bleibt beim muster_fit-Agenten.
7. Das Modell ist weiter nicht druckbar: "Druckreparatur fehlgeschlagen", 3052 Rohdreiecke aus stl_teil (traufzone_alt, figuren), 545 Teilnetze.

### Foto-Diagnosen (angesehen)
- foto_diff 6261: Modellkanten ohne Foto 0,201 -> 0,164 (besser), Fotokanten ohne Modell 0,470 -> 0,526 (schlechter, glatter Rumpf statt Detail-STL). Rot: Westgiebel-Anschlusslinie Dach/Giebel (wie Runde 2), Baluster-/Konsolen-Unterkanten. Gelb: Masswerk, Figuren, Giebelfenster, Nachbarhaus.
- foto_diff 6120: 0,147 -> 0,149 / 0,446 -> 0,439. Achtung: Das Werkzeug verschiebt global um 0,93 m.
- fehlteile 6120: 1 Zelle in der Konsolenzone (wie zuvor). fehlteile 6261: 5 ERFUNDEN am Ostgiebel, 1 FEHLT am Nachbarhaus.
- Overlays: `audit/gitter_generator/runde3_ip_IMG_6120.jpg`, `runde3_ip_IMG_6261.jpg`; Vorher/Nachher `vergleich_runde2_runde3_ip_IMG_6120.jpg`, `..._6261.jpg`. Das Runde-2-Bild enthielt zusaetzlich die gelbe Gitterebene, die Bilder sind also nicht stilgleich.
- Regression: Der Schnappschuss ist NICHT erneuert (Ergebnis aendert sich beabsichtigt). Erneuern nur per Auftrag und mit Register-Eintrag.

## Runde 4 (Agent, 9.11. abend) - Druckbarkeit, Versatz 6120, linker Pfeiler, Traufzone

### 1 Druckbarkeit
- Pruefungen zuerst eingetragen (Merkmal druck, quelltyp modell): Teilnetze = 1, wasserdicht, Wandstaerke p1 >= 0,0348 m (0,4 mm H0; neue Messart `wandstaerke` in pruefstand.py, Strahl entlang Innennormale, GPU). Am Runde-3-Modell: 545 / 0 / 0,03 = fehlschlagend.
- Generator (alles per cfg, Standard aus): `stl_teil.koerper` (+`koerper_dehnung`, `koerper_min_m3`: Teil-STL als manifold-Koerper; flache Reste ohne Dicke verworfen und gezaehlt), `fensterreihe.einbindung` (Rahmen/Pfosten/Riegel 0,04 m in die Wand, Glas 1 cm in den Rahmen, Rueckseite ein/2), `satteldach.ziegel_einbindung` (1 cm), `bogenreihe.druck_verbinder` (Schaft endet am Kaempfer, Verbinder = Schaft geschnitten mit dem Band - ragt nie ueber Bandflucht/Laibung).
- objekt.json: traufzone_alt aus; neu `stl_teil:konsolen_alt` (nur g_konsolen.stl, gleicher Anker) und `quader:gesims` (Gitter: z 14,1..14,70, n 12,62..13,08; u-Enden ANNAHME); figuren koerper; Fenster og/eg0/eg2 einbindung 0,04; Nischen eg1/Tuer 1 cm groesser als das Licht; druck.anbau_konsolen = true; Helme z0 -0,07 statt -0,04 unter Traufe (historie).
- Fehlersuche per Teilmengen-Bau (NUR_BAUTEIL) + Kantenzaehlung: Ursachen waren deckungsgleiche Flaechen (Ziegel/Dach, Glas/Rahmen, Nische/Rahmen, Gesims/Traufe), Pfeilerkopf 5,5 mm neben der Bogenlaibung, flache Figurenreste ohne Volumen und die Helmbasis 1 cm unter der Erkerspitze an der Westecke. VEREINFACHEN_M (0 / 0,0005 / 0,001 / 0,005 / 0,01) aenderte daran nichts.
- Ergebnis: 1 Koerper, wasserdicht, Wandstaerke p1 0,14 m (1,6 mm H0), Anteil < 0,4 mm 0,02 % (Dachfirst-Grat z 27,5 und Figurenkanten z 12,5). Pruefstand: alle bestanden.
- Slicer-Vorcheck: neues Werkzeug `tools/druck_vorcheck.py <objekt>` (generisch, GPU) -> `audit/druck_vorcheck.json`. Ueberhaenge > 60 Grad 206,6 m2 (5,6 %): Laubendecke z 7-8 173 m2, Erkerunterseiten 11,4 m2, Gesimsunterseite 9,8 m2, Fensterstuerze klein. Laubendecke braucht Stuetzen oder Teilung (Entscheidung offen).

### 2 Versatz 0,93 m in foto_diff 6120
- K-6120 = kam_lot2-Eintrag (gleiche R, t, f, k1). Kontrollversuch mit gleichem Modell, nur traufzone_alt wieder an (und gesims/konsolen_alt aus): Versatz 0,928 m [0, -291] px, DEUTLICH. Ohne traufzone_alt (Runde 4): 0,249 m [-16, 73] px, nicht deutlich (Gewinn 0,065).
- Ursache: Modell, nicht Kamera. Die Alt-Traufzone lag rund 0,6-0,9 m unter Gesims/Traufe aus dem Gitter (Beobachtung Runde 3); ihre dichten waagerechten Kanten zogen die Chamfer-Suche 291 px nach oben. foto_diff 6120 jetzt 0,118 / 0,318 (Runde 3 0,149 / 0,439), 6261 0,169 / 0,483 (0,164 / 0,526).

### 3 Linker Pfeiler (schiefes Viereck)
- Einzelteil-Overlays (eg0, eg2, laube) auf 6120: Das Viereck ist `fensterreihe:eg0` (Rueckwandfenster u 11,75 in Bogen 4) und liegt hinter dem Pfeiler u 9,55. Das Overlay zeichnet ohne Verdeckung, Zylinder nur als Ringe. Es ist kein falsches Bauteil. Im Foto ist am linken Rand hinter dem Pfeiler ein Gitterfenster sichtbar, eg0 bleibt aber ANNAHME (Lage nicht gemessen).

### 4 Traufzone
- traufzone_alt aus. Gesims als Quader nach Gitter (14,1-14,68, + 2 cm Einbindung), Konsolen unveraendert aus derselben Alt-Datei (g_konsolen.stl, gleiche Transformation).

### Sichtblatt seiten.jpg - Fehlerliste (angesehen)
1. Nord: Gesims als Leiste an der Traufe sichtbar, kein glattes 0,6-m-Band mehr unter der Traufe. Die Arkade hat 4 Boegen mit runden Pfeilern und Sockeln, das Rueckwandfenster ist sichtbar.
2. Sued: Die Vorderseite scheint durch, das ist ein Renderer-Artefakt. 8 Strahlen von hinten treffen die Rueckwand bei n -6,56. Beobachtung eingetragen.
3. Ost/West: Die Giebel sind gestuft und das Dach sitzt auf dem Rumpf. Der dunkle Block am Ostende in Nord ist die Giebelstirn schraeg gesehen (Gebaeude 19,5 Grad gedreht), kein Fehler. Die Rueckhaelfte ist weiter glatt (ungemessen).
4. Draufsicht: Ziegelreihen nur auf einer Dachseite erkennbar (unveraendert seit Runde 3, Ursache nicht geprueft).
5. Druck: 1 Koerper, wasserdicht. Offen sind die Ueberhaenge (Laubendecke).

### Overlays/Diff (angesehen)
- `audit/gitter_generator/runde4_ip_IMG_6120.jpg`, `runde4_ip_IMG_6261.jpg`, `vergleich_runde3_runde4_ip_IMG_6120.jpg`, `..._6261.jpg`. Der "Teppich" ueber OG/Balkon in 6120 bleibt auch ohne traufzone_alt: Es sind ueberwiegend die Ziegelreihen des Daches, durch die Fassade gezeichnet (Overlay ohne Tiefenpuffer). Abhilfe waere eine Werkzeugaenderung, Beobachtung ist eingetragen.
- foto_diff 6120 rot: Bogen 3 rechts vom Scheitel und Bogen 4 links (Treffer 2/6), dazu die Bandoberkante/Laubendecke als Doppellinie (Treffer 4/7). Das Bogenprofil muss am Foto gemessen werden (Beobachtung).
- fehlteile 6261: 3 FEHLT/3 ERFUNDEN am Ostgiebel z 15-18,5. fehlteile 6120: 4 ERFUNDEN? z 20-21,5 (Dach, durch die Fassade gesehen).
- Regression `--pruefen`: "identisch - nichts verloren". Der Schnappschuss ist nicht erneuert. Kein Commit.
- Testdateien in modelle/stl/: `_tmp_r4.stl`, `_tmp_alt.stl`, `_tmp_fig.stl`, `_tmp_eg0.stl`, `_tmp_eg2.stl`, `_tmp_laube.stl` (nicht geloescht, Regel "nichts loeschen").

## Runde 5 (Agent, 9.11. nacht) - Druckteilung, Konsolen, Overlay mit Z-Puffer, Bogenprofil, Rahmenversatz foto_diff

### Korrektur zu Runde 4 (Koordinator-Hinweis, bewiesen)
- foto_diff/fehlteile verschoben das Generator-STL um -zmin = -1,453 m. Grund: K-6120/K-6261 (Kamera-Bruecke im lot2-Rahmen) hatten keine `rahmen_verschiebung`, deshalb griff die Handkamera-Regel [-c0, -c1, -zmin]. Kamerazentren K gegen kam_lot2 sind identisch (z. B. 6120 C = 12,52 / 19,12 / 3,69).
- Behoben: `rahmen_verschiebung` [0, 0, 0] in beiden K-Protokollen (Eintrag in historie). `fehlteile_finden.py` liest sie jetzt wie foto_diff.
- Beleg mit dem Runde-4-Modell, nur K geaendert:

| Foto | Runde 4 | nur K geaendert | Versatz |
|---|---|---|---|
| 6120 | 0,118 / 0,318 | 0,038 / 0,214 | 0,34 m, nicht deutlich |
| 6261 | 0,169 / 0,483 | 0,098 / 0,429 | 0,09 m |

  Die Boegen liegen jetzt gruen auf dem Foto.
- Runde-4-Aussage "0,93 m kam nur von traufzone_alt" ist damit unvollstaendig. Die Alt-Traufzone verstaerkte den Fehlgriff, die Hauptursache war der z-Versatz. Die Lehre L5 im Register ist korrigiert.

### 3 Overlay mit Verdeckung
- `tools/modell_foto_overlay.py`:
  - Z-Puffer exakt auf der GPU (render_kern.dreiecke_rastern wie foto_diff --raster).
  - Kanten in Stuecke von ca. 3 px; ein Stueck ist sichtbar, wenn seine Tiefe <= Z-Puffer + max(5 cm, 0,5 %) ist, geprueft 2 cm in beide Nachbarflaechen.
  - Neu Umrisskanten (Zylinder zeigen ihre Silhouette).
  - `--verdeckt aus|gestrichelt|alle`; Standard `aus`, `alle` = altes Verhalten.
  - Laufzeit 7 s.
- Ergebnis 6120: Der Ziegelteppich ist weg, die Pfeiler haben Umrisse, die Konsolen sind sichtbar.
- foto_diff rastert schon exakt mit Z-Puffer. fehlteile hat einen Punkt-Z-Puffer mit Lochfuellung, also nicht dieselbe Ursache; dort ist nur der Rahmenversatz behoben.

### 2 Konsolen
- Neuer generischer Bauteiltyp `konsolenreihe`:
  - Lagen je Instanz, inline oder aus `lagen_datei` mit `quell_rahmen` (along/off der Datei -> Welt -> eigener Rahmen).
  - Profil [z, Ausladung] je Instanz; Koerper = konvexe Huelle (ANNAHME).
  - `einbindung` 0,2 m, `max_ausladung` 1,17 (3 cm hinter der Balkonfront).
  - Ein Beleg je Konsole.
- `konsolenreihe:balkon` liest `konsolen_v11.json` (Koerper-Agent): 11 Konsolen, u -5,21 .. 12,19, Breite 0,22-0,60.
- `stl_teil:konsolen_alt` ist aus: Es lag bei z 12,8-13,2, war ein Rest der Alt-Traufzone und enthielt keine Balkonkonsolen.
- Zaehlung Z-6120-006: 3 Konsolen zwischen den Pfeilerachsen von Bogen 3.
- Neue Messart `ebene_vorspruenge` in pruefstand.py, als STRUKTUR-Typ gefuehrt (Lint). Pruefung "Balkonkonsolen ... Bogen 3": Runde 4 = 0 (FEHLER), jetzt 3. Overlay 6120: Die 5 sichtbaren Konsolen decken sich mit dem Foto.

### 4 Bogenprofil
- foto_mass mit K-Kamera, Ebene Bandfront 12,578; gemessen wird die innere Goldlinie.

| Bogen 3 | M-6120 | M-6261 | gewichtet | vorher |
|---|---|---|---|---|
| Kaempfer z | 5,25/5,30 (008) | 5,35 (001) | 5,33 | 5,46 |
| Scheitel z | 7,11 (009) | 7,31 (002) | 7,24 | 7,20 |
| Lichte | 5,17 (008) | 5,33 (001) | 5,29 | 5,13 |

  Steg am Kaempfer M-6261-003 0,72 (= pitch - Lichte, passt).
- Der Scheitel weicht 1,5 sigma ab (Widerspruchs-Beobachtung).
- Die Boegen 1, 2 und 4 sind nicht gemessen; "gleiche Boegen" ist ANNAHME.
- Pruefung "Bogen 3 Lichte bei z 5,40": Runde 4 = 5,14 (FEHLER), jetzt 5,24. Soll 5,17..5,41.

### 1 Druckteilung (generisch)
- `tools/druck_teilung.py <objekt>`, Parameter `objekt.json druck_teilung`, Lauf in `bauen_abnehmen.sh`, wenn der Schluessel gesetzt ist:
  1. Schnittkandidaten = Hoehen mit waagerechter Unterseite (Histogramm 2 cm).
  2. Gierig: die 5 groessten Kandidaten je Teil testen, nur Schnitte mit Ueberhang-Gewinn behalten.
  3. Lage = beste von 6 Achslagen mit tragfaehiger Auflage (>= 25 % der groessten Auflage, kein Kegel auf der Spitze). Bevorzugt werden Lagen, die aufs Bett passen.
  4. Bettschnitt auf der laengsten Rahmenachse an der kleinsten Schnittflaeche im mittleren Drittel, ohne Splitter < 2 %.
  5. Danach noch einmal Ueberhang-Schnitte.
  6. Passstifte 2 x 6 mm, Spiel 0,2 mm, Bohrung nur, wo beide Seiten Material haben. Stifte liegen als eigene STL bei (keine Zapfen).
- Ergebnis: 6 Schnitte, darunter z 7,9 an der Laubendecke (175 m2 Gewinn) und z 14,1 an der Gesimsunterseite. 8 Teile, alle wasserdicht, alle passen auf das P1S-Bett (max 242 mm), 51 Stifte. Ueberhang je Teil max 0,95 %; die EG-Arkade liegt kopfueber.
- Ausgabe:
  - `modelle/stl/kaufhaus_grob3_teile/teil_01..08.stl` (Drucklage)
  - `lage/` (Originallage)
  - `stifte.stl`
  - `teilung.json`
- Neue Messart `druck_teile_ueberhang` (gilt nur bei passendem Modellvolumen, sonst ungeteiltes Modell). Pruefung "Ueberhang je Druckteil < 1 %": ungeteilt 0,056 (FEHLER), geteilt 0,0095.
- Regel 9b: `audit/druckteile/teil_NN_6261.jpg` und `teile_neben_foto_6261.jpg` (jedes Teil mit Z-Puffer auf dem Foto) angesehen.
  - Schnittlagen sind plausibel: EG und OG an der Laubendecke getrennt, Dach in 2 Hoehen.
  - Der Rumpf ragt im Bild links ueber das Nachbarhaus; das ist die verdeckte hintere Ecke (Nachbarhaus im Foto davor), kein Fehler.
  - Offen: Bettschnitt u 6,58 durch Bogen 3 (Arkade, nur 1 Stift im Bogensteg). Ein Probedruck fehlt.

### bauen_abnehmen
- Alle Pruefungen bestanden: 1 Teilnetz, wasserdicht, Wandstaerke 0,14 m, Konsolen 3, Bogen-Lichte 5,24, Ueberhang je Teil 0,0095.
- Vorbestehend: `freiraum_audit` scheitert an der fehlenden Datei `messprotokoll/SFM-AUSRICHTUNG-buendel.json`. Das Kaufhaus hat keine Freiraum-Pruefung, nicht angefasst.

### Sichtblatt seiten.jpg - Fehlerliste (angesehen)
1. Nord: Boegen springen jetzt tiefer an (Kaempfer 5,33). Die Konsolen sind in der Gesamtansicht zu klein zum Beurteilen; im Overlay 6120 decken sie sich mit dem Foto.
2. Sued: Die Vorderseite scheint durch (Renderer-Artefakt, Runde 4 per Strahltest belegt).
3. Ost/West/Draufsicht: unveraendert zu Runde 4. Rueckhaelfte glatt (ungemessen), Ziegel nur auf einer Seite erkennbar.
4. Neu aus dem Overlay mit Z-Puffer: Bei z 8,0 liegt ueber den Boegen eine waagerechte Modellkante (Stufe 8 cm zwischen Bandfront 12,578 und OG-Wand 12,66), im Foto ist dort glatter Putz. Beobachtung eingetragen.
5. Waagerechte Linie in den Bogenoeffnungen: Oberkante der Laubenrueckwand. Das Gewoelbe ist nicht modelliert und bleibt ANNAHME/offen.

### Overlays, Diff, fehlteile (angesehen)
- `audit/gitter_generator/runde5_ip_IMG_6120.jpg`, `runde5_ip_IMG_6261.jpg`, `vergleich_runde4_runde5_ip_IMG_6120.jpg`, `..._6261.jpg`. Links altes Werkzeug ohne Verdeckung, rechts neues mit Z-Puffer; nicht stilgleich.
- foto_diff (aktuelles Modell): 6120 0,042 / 0,217, Versatz 0,22 m nicht deutlich; 6261 0,091 / 0,422, Versatz 0,09 m. Gelb bleiben Rueckwandfenster/Tuer (flache Rahmen geben keine Normalenkante), Figuren und Masswerk.
- fehlteile (jetzt im richtigen Rahmen): 6120 1 ERFUNDEN? am Dach z 22; 6261 6 ERFUNDEN? am Dach z 17,7-20,9. Die Wolke sieht das Dach nicht; das Foto zeigt dort Ziegel ohne Kanten.
- Regression `--pruefen`: "identisch - nichts verloren". Schnappschuss nicht erneuert, kein Commit.

### Testdateien in modelle/stl/ (nicht geloescht, Loeschen nur durch den Nutzer)
- `_tmp_r4.stl`, `_tmp_alt.stl`, `_tmp_fig.stl`, `_tmp_eg0.stl`, `_tmp_eg2.stl`, `_tmp_laube.stl`, `_tmp_kons.stl`

## Runde 6 (Agent, 9.11. abends) - Prioritaeten nach Koordinator-Aenderungen
Reihenfolge laut Koordinator: Slicen GESTRICHEN; Vorrang Pruefer-/Nutzerbefunde 6261, dann A Erker/Helme, B EG-Fenster Boegen 1/2/4 (+ Rueckwand-Ebene zuerst), dann alte Punkte 1-3.
Alle Pruefungen vor der Generatoraenderung angelegt und ROT gesehen, danach gruen (Regel 2).

### Ergebnisse (jede Aenderung mit Pruefung vorher rot -> nachher gruen)
1. OG-Fenster Kaempfer je Licht: neue Option `fensterreihe.licht_riegel_z` / `licht_scheitel_z` (aussen->Mitte, gespiegelt). OG: [11,753, 12,283] aus kaempfer_sweep.json;
   am Foto 6120 Differenz Mitte-Seite 0,53-0,56 bestaetigt (M-6120-011..013, absolut 0,1 tiefer: nicht gemittelt). Pruefungen offene Lichter bei z 11,753 (1) und 12,283 (2): vorher 0/3, nachher 1/2.
   Sweep-Seitenscheitel 14,334 (Wolke) liegt UEBER der Rahmenoberkante 13,30 (M-6120-017) -> verworfen; Seiten folgen der Kontur. M-6120-014 = Fehlpick (Ausschnitt-Versatz vergessen), ersetzt durch M-6120-016; M-6120-015 = Probemessung Sohlbank 10,50.
2. Laubenrueckwand-Ebene: Wolke (161 282 Punkte) Spitze n 7,275; Triangulation 6120+6117 (neuer foto_mass-Modus `--tri`): Goldquaste 7,30, Glas 7,11-7,20, Tuerblatt 6,8-7,2.
   6,54 (rohkoerper_v7, nie gemessen) verworfen. Rueckwand/Rumpf-EG/EG-Fenster/Nischen +0,74; M-6120-001..005 auf 7,28 neu gerechnet (M-6120-025..029, mess_px gleich).
   Pruefung Wandflaeche hinter 7,28: vorher +0,74, nachher 0,00.
3. Erkerhelme (Nutzerbefund): neuer Bauteiltyp `helm_geschweift` (N-Eck, Profil r(z), Kranz, Knauf), Erker-Option `ohne_dach`. Profil aus Foto nu_3b29472b (K-nu3b, 19 m):
   M-nu3b-001..008; Wolke r p50 einig +-0,07 ab z 15. Foto 6261 (34 m) 0,1-0,2 schmaler, Traufe 0,7 tiefer -> Widerspruch in beobachtungen_offen.
   Achtung: in 6261 ist der LINKE Helm der Osthelm (u 15,5), der rechte der Westhelm (Projektion geprueft); M-6261-004..012 = falsche Achsebene (ungueltig), ersetzt durch M-6261-013..021.
   Pruefungen Ost z 14,64/16,18/17,76: vorher 1,36/0,73/0,57 (rot), nachher 1,21/0,59/0,35. West (Kopplung auf Probe, Wolke): 0,56/0,51 (16,25 an der Grenze).
4. Bogen 2 grosses Tor: Triangulation 6117+6127 (84-87 Grad) M-6117-001..005, Zaehlung Z-6117-001. freiform-Ausschnitt (Spitzbogen, Kaempfer 5,23, Scheitel 6,66, Spannweite 4,0, Torblatt 0,55 zurueck).
   Pruefungen Tiefe/Oeffnung: vorher 0,00/0, nachher 0,55/1.
5. Boegen 1 und 4 EG-Fenster (vorher ANNAHME eg0/eg2): Kreuzstockfenster wie Bogen 3, Fotos 6119/6130 (neue Kamera-Bruecken) auf Ebene 7,28: M-6119-001..003, M-6130-001..003, Z-6119-001, Z-6130-001.
   eg0 along 12,47 b 1,95 z 3,20-6,28; eg2 along -5,36 b 1,84 z 3,30-6,39; Glasnischen eg0/eg2_nische. Pruefungen Lichter je Zeile: vorher 0/0, nachher 2/2.
6. 8-cm-Stufe z 8,0: Wolke Band = OG-Wand (n 12,63) -> laibung_tiefe 0,776 -> 0,94 (Bandfront 12,66). Pruefung: vorher 0,08, nachher 0.
7. Bogenprofil: drittes Foto 6119 (14 m, 10 Grad): Bogen 3 Kaempfer 5,26/5,29, Lichte 5,12, Scheitel 7,13; Bogen 4 Kaempfer 5,27, Scheitel 7,08; Bogen 1 (6130, sehr schraeg) ~6,99.
   Entscheid Scheitel-Widerspruch: 6120 (7,11) + 6119 (7,13) einig, 6261 (7,31, 34 m) Ausreisser -> kaempfer 5,28 / scheitel 7,12 / oeffnung 5,15. Bogen 2 nicht gemessen.
   Pruefung Scheitel: vorher 7,22, nachher 7,10. Soll 'Lichte' mit neuer Quelle M-6119-004 auf [5,05, 5,25] (historie).
8. Pruefer Punkt 1 (hohe Umrisslinie links in 6261): das ist das OSTende (u 17,15; in 6261 waechst u nach links). Modell-Hinterecke (n -6,56) projiziert auf x 61-143 bei 42-46 m Tiefe,
   die Wolke hat dort 5 098 Punkte bei 30-33 m = Nachbarhaus davor -> Brandwand verdeckt, kein sichtbarer Modellfehler. Offen bleibt die Tiefe n -6,56 (ANNAHME Firstspiegel, LoD2 12,54 widerspricht)
   und die fehlende Stirnwand der Laube (along 16,0-17,15, Seitenbogen im Foto, Modell offen = 'Kasten x 190-290').
9. Druckreparatur: Simplify-Toleranz-Fallback (5 -> 4 -> 6 -> 3 -> 7 mm), weil die Union-Numerik zufaellig Splitter erzeugt (Lauf mit Lichtriegeln: 37 Koerper bei 5 mm, wasserdicht bei 3 mm).
10. Sichtliste je Bauteil: Generator `BAUTEILE_AUS=<dir>` schreibt jedes Bauteil als STL + liste.json; `tools/bauteil_sichtliste.py` waehlt je Bauteil das Foto mit der groessten unverdeckten Flaeche (GPU-Z-Puffer)
    und schreibt Overlay-Ausschnitte nach audit/sichtliste/ (sichtliste.json, uebersicht.jpg).

### Neue/geaenderte Werkzeuge (generisch)
- `tools/baukasten_gen.py`: fensterreihe licht_riegel_z/licht_scheitel_z; erker ohne_dach; Bauteil helm_geschweift; Druckreparatur-Toleranzfallback; BAUTEILE_AUS + liste.json.
- `tools/foto_mass.py`: Modus `--tri K-A x y K-B x y ...` (Strahlschnitt, Tiefe ohne Ebenenannahme, Protokoll typ triangulation mit Schnittwinkel).
- `tools/kamera_bruecke.py` (neu): K-<nr> aus Buendelkameradatei + Symlink; `--kandidaten X Y Z` listet Fotos nach Blickwinkel.
- `tools/pruefstand.py`: Messart `schnitt_reichweite` (Konturreichweite ab Achse in Richtung, Streifen).
- `tools/bauteil_sichtliste.py` (neu).
Neue Kameras: K-6117, K-6119, K-6127, K-6130, K-6206, K-nu3b (alle kamera_bruecke_sfm, rahmen_verschiebung [0,0,0]).

### Testdateien (nicht geloescht, Loeschen nur durch den Nutzer)
- modelle/stl/_tmp_r6_alt.stl, _tmp_r6_neu.stl, _tmp_r6_teil.stl, _tmp_r6_voll_alt.stl
- Bauteil-STL: /media/oem/scan/rc-park_daten/kaufhaus_alle/bauteile_stl/ (alt, enthaelt abgeschaltete zylinder:helm_*), bauteile_r6/ (aktuell, liste.json)
- Agent-Scratch (Root-Platte war bei 4,7 GB < 5 GB Platztor): nach /media/oem/scan/rc-park_daten/kaufhaus_alle/agent_scratch_r6/ VERSCHOBEN (nicht geloescht)

### Runde 6 Nachtrag: Sichtliste-Auswahl mit Fremdverdeckung (bauteil_sichtliste.py --wolke, --kandidaten)
- Bewertung = sichtbare px x Sichtanteil x Bildanteil x (1 - Fremdverdeckung)^2; Fremdverdeckung = Anteil Teilpixel, vor denen ein Wolkenpunkt > 0,5 m naeher liegt.
- Besser: satteldach (j_07, ganzes Dach), helm_geschweift:o (j_01 statt leerem 6185, aber nur Spitze), balkonband, rumpf_og, gaubenreihe:unten.
- Weiter schlecht (ungeprueft): staffelgiebel:ost/west, stl_teil:figuren, quader:laube_rueck -> Gewoelbe-Innenansichten; Ursache: Gewoelbe weder im Modell noch dicht in der Wolke -> Kamera unter der Arkade 'sieht' Giebel. Abhilfe offen: Kamera-Standort ausserhalb Modellhuelle / Blickrichtung zur Teilnormalen erzwingen.

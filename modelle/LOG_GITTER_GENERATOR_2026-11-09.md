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

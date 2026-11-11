# Kreis r2 – quader:laube_sockel_o (2026-11-11)

## 1. Formbeschreibung (Stufe 0; Fotos 6120 Nahsicht schraeg, 6119 Mitte, 6117 Uebersicht, ausserdem d20/6174 im Tor)
- **Zonen von unten nach oben**: (a) Steinsockel, rote Sandsteinquader mit Fugen, Fuss auf dem Pflaster; (b) Gesimsband oben (z ~2,04-2,2), springt unter dem Band zurueck (Schattenkante, Wulst); Wand darueber.
- **Grundriss**: Rechteck u 5..16,3 entlang der Laubenrueckwand (Ebene n 7,28, Front n 7,73, Band 7,8), unterbrochen von den runden Pfeilerbasen (getrennte Teile).
- **Wiederholungen**: Steinlagen/Fugen (Relief < 0,1 m, von der Metrik nicht sichtbar, nicht modelliert).
- **Was am Modell anders war**: Projektion der Ebene n 7,73 in 6120/6119/6117 (Hilfsskript agent_scratch_kreis2/proj.py, Linien z 1,5-2,2): Pflasterkante am Sockelfuss bei z 1,73-1,84, Modell z0 = 1,5 -> Modellflaeche 0,15-0,2 m im Pflaster (gelbe Fusskante in allen Torfotos); Bandunterkante fehlte (Ost ohne profil).
- **Formfamilie**: vorhandene `quader` mit `profil` (wie laube_sockel_w), nichts Neues.
- Unsicher/ANNAHME: Bandhoehe 2,04-2,2 und Ueberstand 0,07 aus West uebernommen; Pflasterhoehe 0,27 ueber laube_rueck z0 1,5 (Boden der Laube nicht geklaert); Ostende (Schaltschrank) ungeprueft.

## 2. Zaehlungen
Keine Zaehlmerkmale (Steinlagen/Felder nicht modelliert, Relief unter Metrikaufloesung; siehe NICHTS_GEBRACHT-Eintrag West). Kein Z-Protokoll.

## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| laube_sockel_fuss_ost_165 (neu) | -0,46 FEHLER | -0,01 OK | -0,08..0,08 | M-6120-069, M-6119-017, M-6117-007 (Fuss z 1,78/1,73/1,84) |
Foto-F1 (10 Torfotos, volle Aufl., teil_fotoform gleiche Gewichtung): vorher 0,599 (P 0,744, R 0,501) -> nachher 0,779 (P 0,777, R 0,781); Hoehen-F1 0,514 -> 0,714. Einzelfotos schlechter: 6174 Praez 0,705->0,642, d20 0,662->0,561, 6117 0,861->0,764 (Recall dort stark besser).
Wolkenbeleg/Gitter-F1: nicht neu gemessen (Abnahme/Konvergenz-Tor des Kreises).

## 4. Overlays
- Nachher: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_044705a044705/r2_nachher_bilder/quader__laube_sockel_o_{6120,d20,6117,6174}.jpg
- Vorher: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_044705a044705/fotoform_bilder/quader__laube_sockel_o_*_r2_vorher.jpg
- Projektionslinien: /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis2/p6120.jpg, p6119.jpg, p6117.jpg

## 5. Fehlerliste
- Fuss z0: trifft (3 Fotos, Overlay 6120 nachher: violette Flaeche weg), Auge-Pick +-0,05 m.
- Oberkante 2,2: trifft (6120/6119/6117).
- Band-Unterkante/Ueberstand: teilweise; 6120 zeigt noch gelb an Bandmitte (u ~8-12) und 6120 rechts oben, Hoehen-/Ueberstand ANNAHME.
- 6174 / d20: roter Streifen in der Frontflaeche (Praez gesunken) - Ursache ungeklaert (Rundung/Sockelfront n?), ungeprueft.
- Fugen/Steinlagen, Ostende: fehlen/ungeprueft. Pfeilerbasen-Naehe (rot links in 6120, Ecke u 5): ungeprueft.
- Pruefstand: "alle Pruefungen bestanden" (abn_r2.log). teile_lage_pruefen, foto_diff, fehlteile_finden (laufen in bauen_abnehmen), teile_sichtpruefung: NICHT einzeln angesehen (ungeprueft).

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (laube_sockel_o: z0 1,77, n1 7,8, profil), masstabelle.json (Beobachtung, Messung+Pruefung laube_sockel_fuss_ost_165), messprotokoll/M-6120-069, M-6119-017, M-6117-007, modelle/NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, dieser Bericht, vom Bau erzeugte STL/audit/pruefbericht.

## 7. Generalisierte Lehre
Lehre: Eine Fusskante, die in ALLEN Torfotos gelb ist und eine Modellflaeche, die ins Pflaster ragt, ist ein Hoehenfehler des Fusses (z0), kein Detailmangel; z0 aus Projektion der Bauteilebene ins Foto ablesen statt von Nachbarteil uebernehmen | Anlass: laube_sockel_o Foto-F1 0,60 -> 0,78 allein durch z0 1,5 -> 1,77 | Werkzeug: Projektionsskript (Ebene + z-Linien ins Foto, agent_scratch_kreis2/proj.py), foto_mass --kamera --ebene.
Offen: laube_sockel_w hat vermutlich denselben z0-Fehler (1,5) - Fuss dort nachmessen.

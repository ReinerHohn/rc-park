# Kreis 225455 r1 - erker_polygon:1, Beobachtung "Erker-Unterbau Profilform"

## 1 Formbeschreibung (Stufe 0)
Fotos: 6164 (Nahfoto), 6161 + 6259 (Silhouette vor grauer Wand), Torfotos nu3b/6132/nuaca als Uebersicht. Details: modelle/LOGBUCH_ERKER_UNTERBAU_R1_2026-11-10_225455.md.
Unterbau = nach unten zulaufender achteckiger Trichter, laeuft zur ACHSE des Achtecks (hinter der Wand) zu, unten am Pfeilerkopf abgeschnitten; Netzgewoelbe: 4 gerade Grate + je Flaeche 2 sich kreuzende Bogenrippen. Formfamilie: vorhandene erker_polygon + generischer Parameter unterbau.kegel_achse_n (Rippen-Familie rippen_bogen als optionale Familie).
Ursache der Beobachtung: Ringe wurden um die Wandebene skaliert -> Flanken unten 0,3-0,4 m zu schmal.

## 2 Zaehlungen
Rippen je Flaeche nur per Auge am Foto 6164 (2 Bogen + Grat); KEIN Z-Protokoll -> ungeprueft (Regel 9).

## 3 Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| erker_o_flanke74 (Flankenbreite u bei z 7,4) | 0,88 (ROT) | 1,22 | 0,91..1,26 | M-6259-030, M-6164-005 (3-Kamera-Konsens, u +-0,15; schwach trennend) |
| erker_o_unterbau70/72/76 (Wolke-Median) | 0,71/0,90/1,18 | 0,61/0,82/1,18 | unveraendert | Sollwerte NICHT gelockert; 72 mit 0,8209 knapp ueber 0,82 |
| Foto-F1 (10 Torfotos, Skala 0,5, Vollmodell) | 0,596 | 0,633 (Praez 0,795, Recall 0,525) | Tor >= +0,02 | teil_fotoform |
| f1_h | 0,551 | 0,563 | Veto -0,02 | teil_fotoform |
| Lage Median gegen Wolke | 0,08 | 0,08 | <0,4 | teile_lage_pruefen |
bauen_abnehmen.sh: "alle Pruefungen bestanden" (rc 0), regression.py --pruefen: identisch. Voller Endlauf (Skala 1,0) nicht gefahren.
Wolkenbeleg/Gitter-F1 nicht separat gemessen (ungeprueft).

## 4 Overlays (vorher | nachher)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_erker_polygon_1_{6164,6161,6259,nuaca}.jpg (6161 selbst angesehen: linke Flanke folgt nachher der Silhouette; 6164/6259/nuaca nur erzeugt, nicht einzeln angesehen)
Seitenblatt audit/seiten.jpg angesehen: unauffaellig.

## 5 Fehlerliste
trifft: Flanke links/Silhouette (6161), Vorderflaeche (Wolke). trifft nicht: Gewoelberippen (gelber Rhombus fehlt weiter), Flanke bei z 6,8 ~0,2 m zu schmal, Wasserspeier/Kielbogen/Masswerk (nicht angefasst). ungeprueft: erker_polygon:0 (gleicher Fehler, nicht uebertragen), Rueckseite.

## 6 Geaenderte Dateien
tools/baukasten_gen.py (kegel_achse_n, rippen_bogen, Belege), modelle/kaufhaus_grob3/objekt.json (kegel_achse_n 11,9; Profil z6,9 0,17->0,14), masstabelle.json (Pruefung flanke74, Protokolle, Beobachtung erledigt + neue offen), messprotokoll M-6259-027..031, M-6161-045/046, M-6164-004..006, REZEPT (L-KR33..37), NICHTS_GEBRACHT, Logbuch, Abnahme-Artefakte (STL, pruefbericht, audit).

## 7 Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Trichter um Polygonachse skalieren, nicht um Wandpunkt | Flanken zu schmal | kegel_achse_n |
| Falsch angenommene Ebene -> konsistent falsche Werte; Kameras widersprechen = Befund | 6164 vs 6259 | tri3.py (Mehr-Kamera-Konsens) |
| Schnellmessung nur mit Teil-STL ist ROI-Artefakt (0,629 statt 0,575) | teil_fotoform nutzt Vollmodell | voll2.py + ff2.sh |
| Ueberlappende Rippensegmente, Vollmodell-Reparatur testen | manifold3d-Splitter | komp.py |
| Flachrelief-Rippen senken Foto-F1 | 0,617 -> 0,575 | rippen_bogen AUS |

# Kreis-Bericht a021633 r4: helm_geschweift:o (kaufhaus_grob3, 2026-11-10)
Stand: nichts committet. Branch kreis/kaufhaus_grob3/20261110_021633a021633-r4.

## 1. Formbeschreibung (Stufe 0)
Fotos (alle angesehen): nu3b (Nahfoto ~17 m), nuaca (21 m), 6132 (22 m schraeg), 6161 (29 m Uebersicht), 6145 (33 m). Helmachse (18,72/6,34) vorher in jedes Foto projiziert (Z-Ticks je 1 m, Rohbilder `agent_scratch_kreis4/achse_*.jpg`).
- Fuss/Traufe: Ziegelhaut laeuft stetig konkav bis auf das Erkergesims (z ~13,3); Traufspitzen links/rechts nahezu waagerecht, Gesims-Oberkante z ~13,2-13,3; kein senkrechter Kranz.
- Schweifung z 13,3-16: stark konkav; Schaft z 16-20 mit Graten und hellen Ziegelstreifen; Kupfernadel z 20-21,1; Kugel (leicht abgeflachte Zwiebel, 0,40 m breit) Mitte z 21,33; darueber duenne Stange mit Fahne bis 22,78.
- Grundriss regelmaessiges Achteck, eine Flaeche zur Strasse (3 Grate von vorn gezaehlt, Rueckseite ANNAHME Spiegelung). Sitzt auf dem Erkergesims, gleiche Achse (Kugel-Achse 15,51/12,24 = Helmachse +-0,02 m).
- Altmodell anders: Profil unten (R1 behoben: Kranz 1,45 senkrecht, Traufring z 14,15) und Kugel 0,67 m zu hoch (z 22,0).
- Formfamilie: bestehende `helm_geschweift` (N-Eck, Profil r(z), Kranz, Knauf) reicht -> keine neue Familie.

## 2. Zaehlungen
Z-nu3b-001 (aus R1 uebernommen): 3 Grate in Bildzeile 1000, N=8 bleibt ANNAHME (Rueckseite nie sichtbar). Keine neue Zaehlung.

## 3. Pruefungen (vorher -> nachher, Quelle)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| helm_o_r_13_45/14_12/14_38/14_88 (aus R1) | rot am Runde-7-Stand | gruen | siehe masstabelle | Wolke lot2 + Foto-Gegenprobe (W-helm_o-profil) |
| helm_o_knauf_r_21_33 | 0,11 ROT | 0,21 gruen | 0,17..0,25 | M-nu3b-009 (5 Fotos Strahlschnitt) |
| helm_o_knauf_r_22_00 | 0,16 ROT | 0,05 gruen | 0..0,07 | M-nu3b-009 |
Abnahme `tools/bauen_abnehmen.sh kaufhaus_grob3`: alle Pruefungen bestanden (1 vorbestehender Widerspruch). Wolkenbeleg Helm O 0,46 -> 0,605, Median 0,087 m; Kanten je Band unveraendert.

## 4. Overlays (links Foto, rechts rot = Altstand, gruen = neu; nur Grate + Kugelkreis, ohne Sichtbarkeitstest)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis4_helm_geschweift_o_{nu3b,nuaca,6132,6161,6145}.jpg

## 5. Fehlerliste
- Traufe/Fuss (Vorderkante, Gesims): trifft (nu3b, nuaca, 6161 selbst angesehen); 6132/6145 nur teilweise.
- Schaft/Grate z 15-20: trifft (nuaca, 6161, nu3b angesehen).
- Kugel: trifft jetzt (nuaca, 6132 angesehen, Triangulation 5 Fotos). Radius 0,2 ANNAHME aus Bildbreite.
- Fahnenstange/Fahne: nur als duenne Stange, Fahne nicht modelliert (ungeprueft/bewusst weggelassen).
- Schweifung z 13,6-14,5: in 6132 evtl. 0,2-0,4 m zu schlank - NICHT belegt, ungeprueft.
- Rueckseite/N=8: ANNAHME.
- teile_lage_pruefen.py: stuerzt bei fensterreihe:og ab (nicht behoben) -> Pflichtschritt 9c(c) nicht mit dem Werkzeug erbracht; Lage ersatzweise: Kugelachse = Helmachse +-0,02 m, Wolkenbeleg.
- foto_diff / fehlteile_finden / teile_sichtpruefung: nur in bauen_abnehmen enthaltenes gelaufen, Ergebnisbilder nicht einzeln angesehen -> ungeprueft. Helm West: nicht angefasst (gleicher Fehler, eigene Runde).

## 6. Geaenderte Dateien
objekt.json (helm_geschweift:o: R1-Profil, Knauf z 21,33 r 0,2, letzter Ring z 21,0 r 0,07), masstabelle.json (+2 Messungen, +2 Pruefungen, R1-Zeilen), messprotokoll/M-nu3b-009, W-helm_o-profil, Z-nu3b-001, tools/helm_profil_wolke.py, LOGBUCH_HELM_O_R1, REZEPT (L-H1, L-H2), NICHTS_GEBRACHT, automatisch regenerierte STL/MASSNACHWEIS/pruefbericht/elemente.

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Punkte auf bekannter Achse per Mehrkamera-Strahlschnitt, Z-Ticks im Foto | Kugel 0,67 m zu hoch | foto_mass --tri |
| Drahtgitter ohne Sichtbarkeit: Rueckhaelfte nicht fuer Fehler halten | Fehlurteil 'Ring 1 m zu tief' (nho) | Overlay mit Tiefenfarbe |

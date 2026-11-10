# Logbuch Kreis helm_geschweift:w (kaufhaus_grob3, 2026-11-10, Lauf 035748a035747 r1)

Befund: Wolkenbeleg 0,45 (Median 0,18 m); Kanten R 0,426 / P 0,275. Vorversuche 001608s3 r1, 021032a021032 r1/r2 verworfen (Gewinn 0,026 / 0,024 / -0,065).

## Formbeschreibung (Stufe 0)
Fotos (angesehen): 6162 (Nah, schraeg), 6257 (schraeg von unten), g03 (Handy, Nahfoto Schaft), i04 (nur Lage, nicht einzeln angesehen). Overlays rot = neu, cyan = alt.
- Zone Fuss z 13,3-15,4: Ziegelhaut laeuft stetig konkav bis aufs Erkergesims (wie Helm O, Logbuch LOGBUCH_HELM_O_R1); Altmodell hatte senkrechten Kranz r 1,45 (z 13,1-14,15) + Traufring 1,54: in 6162/6257 ragt die cyanfarbene Altform unten weit ueber die echte Silhouette hinaus.
- Zone Schaft z 15,4-21: schlank, Achteck, Grate mit hellen Ziegelstreifen (g03: Grate + Fusskonsolen sichtbar). Zone Nadel/Kugel z 21,35.
- Grundriss Achteck, eine Flaeche zur Strasse; Rueckseite ANNAHME Spiegelung. Zaehlung der Flaechen wie Helm O (Z-nu3b-001, Osthelm) - am Westhelm NICHT neu gezaehlt (ungeprueft).
- Anschluss: sitzt auf dem Erkergesims (13,1-13,3), Achse formen/helme.json; Wolke-Phasenfit Achsversatz <= 0,05 m.
Formfamilie: bestehende `helm_geschweift` (N-Eck + Profil r(z)); nur Profil unten + Knauf falsch. Keine neue Familie.

## Messung
`tools/helm_profil_wolke.py` -> `messprotokoll/W-helm_w-profil.json` (Achse -3,99/14,38, n 0,3338/0,9426): a(z) 1,76@13,1; 1,78@13,4; 1,57@13,6; 1,30@14,1; 1,19@14,4; 1,10@14,6; 1,01@14,9; 0,945@15,1. Achteck besser als Kreis.
Vorversuch r2 (Traufe-Apothem 2,3 aus Silhouettenspitze triangulieren) ist durch die Wolke widerlegt (Beleg 0,437 -> 0,374): Silhouettenspitzen sind keine Punkte (L31, siehe Helm O). NICHT wiederholt.
Knauf z 21,35 r 0,195: Vorversuch-Triangulation (4 Fotos) uebernommen, hier nicht neu gemessen (ANNAHME), Gegenprobe Helm O z 21,329.

## Aenderung
objekt.json helm_geschweift:w: Profil unten (z 13,3-15,41, 8 neue Ringe), kranz 13,1-13,3 r 1,78, knauf z 21,35 r 0,195; Profil ab 15,41 unveraendert. 5 neue Pruefungen in masstabelle (helm_w_r_13_45/14_12/14_38/14_88, helm_w_knauf_r_21_35): am Altstand 4 von 5 ROT (1,45/1,45/1,38/knauf 0,09; 14_88 mit 1,08 noch im Band), jetzt alle gruen.

## Ergebnis
bauen_abnehmen: alle Pruefungen bestanden (1 Widerspruch vorbestehend; freiraum_audit-Absturz vorbestehend). konvergenz_bericht (Trockenlauf, Teile neu exportiert):
Helm W Beleg 0,45 -> 0,557, Median 0,18 -> 0,111 m, Kanten R 0,426 -> 0,417, P 0,275 -> 0,312 (F1 0,334 -> 0,357). Mittel(Beleg,F1) 0,392 -> 0,457 = +0,065 (Gate >= 0,05; keine Groesse faellt > 0,02: R -0,009).
Offen: Profil ab z 15,4 ist Osthelm-Kopie (Wolke a(z) dort 0,05-0,07 m breiter, Silhouettenfit Vorversuch r1 wollte 0,74@16,2 statt 0,58); Rueckseite; Westspitze der Traufe.

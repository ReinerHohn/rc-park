# Logbuch Kreis4 helm_geschweift:w (kaufhaus_grob3, 2026-11-10, Lauf 035447a035447 r4)
Befund: Beleg 0,56, Median 0,11 m, Kanten R 0,417 / P 0,312. Vorgaenger (035748a035747 r1) hat Fuss z 13,3-15,4 + Knauf schon in main gebracht; Rest laut Pruefer: Schaft links innerhalb der Fotokante, Krabben fehlen, i04 nicht angesehen, Achteck nicht gezaehlt.
## Formbeschreibung (Stufe 0)
Fotos angesehen: 6162 (Uebersicht/schraeg, 35 m), g03 + i04 (Handy-Nahfotos von unten), 6261 (Uebersicht, Overlay erzeugt, nicht einzeln beurteilt); 6257 nur aus Vorlauf.
- Zonen: Fuss z 13,3-15,4 konkave Ziegelhaut (erledigt); Schaft z 15,4-21 schlanker Achtkant, bunte Ziegelstreifen, auf den Graten Konsolen/Krabben (Haken, aussen rechts/links in g03/i04 klar); Nadel/Kugel z 21,35.
- Grundriss: Achteck, in g03/i04 3 volle + 2 Randflaechen sichtbar (konsistent mit 8, nicht gezaehlt).
- Anschluss: Erkergesims z 13,1-13,3; links im g03 ragt ein Wasserspeier (Drache) quer vor den Helm bei z ~15 - nicht Teil dieses Bauteils.
- Am Modell anders (Overlay vorher cyan): Schaft zu schlank, rechte/linke Kante 0,05-0,1 m innerhalb der Fotohuelle.
Formfamilie: bestehende helm_geschweift, nur Profil. Keine neue Familie.
## Messung
- W-helm_w-profil.json (Wolke-Mitte a(z)): 15,375 0,873 / 16,125 0,647 / 16,875 0,509 / 17,625 0,424 / 18,625 0,332 gegen Modell 0,76/0,60/0,50?(interp.)/0,36/0,28: Modell 0,04-0,06 zu schlank (Osthelm-Kopie).
- M-sil-helm_w-1 (19 Fotos, helm_silhouette_foto.py): Foto breiter 16,5 +0,17 / 18,0 +0,08 / 19,0 +0,10, z>=20,5 Foto schmaler (-0,2, unsicher). Obergrenze wegen Krabben.
- Fund: schnitt_reichweite in +n liefert bei z 16,97/17,76 konstant 0,507 = Staffelgiebel-Quader, nicht der Helm (STL-Schnitt). Neue Pruefungen messen in -u.
## Pruefungen (Soll aus Wolke-Mitte +-0,03)
helm_w_r_16_97 [0,47-0,53]: vorher 0,44 ROT, nachher 0,50 gruen; _17_76 [0,38-0,44]: 0,34 ROT -> 0,41; _18_58 [0,30-0,36]: 0,27 ROT -> 0,34 (ohne Aenderung 0,335 im Profil, Messwert 0,34).
## Aenderung
objekt.json helm_geschweift:w Profil 15,41 0,83->0,87; 16,18 0,58->0,64; 16,97 0,44->0,50; 17,76 0,34->0,41; 18,58 0,27->0,335; 19,4 0,19->0,25.
## Ergebnis
bauen_abnehmen: alle Pruefungen bestanden (freiraum_audit/SFM-AUSRICHTUNG-buendel.json fehlt: vorbestehend). konvergenz_bericht (Trockenlauf, Teile neu exportiert) Helm W: Beleg 0,561 -> 0,562, Median 0,110 -> 0,094 m, Kanten R 0,417 -> 0,721, P 0,312 -> 0,533. Mittel(Beleg, F1): 0,459 -> 0,588 (+0,129; Gate >= 0,05; keine Groesse faellt). Hinweis L-KR15: der Kanten-Sprung ist groesser als die Profilaenderung; das Gitter v12 liegt bei z 16-21 evtl. aussen - Gewinn nicht allein dem Modell zuschreiben. Beleg praktisch unveraendert (Rest 0,44 liegt nicht am Schaft).
## Offen
siehe beobachtungen_offen (Kreis r4): linke Kante i04 ~60 px, Krabben, Achteck-Zaehlung, Giebel-Quader vor dem Helm, Nadel-Silhouette.

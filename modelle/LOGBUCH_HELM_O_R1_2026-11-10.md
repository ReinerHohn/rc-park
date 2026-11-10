# Logbuch Kreis r1: helm_geschweift:o (kaufhaus_grob3, 2026-11-10)

Befund: Wolkenbeleg 0,486 (Median 0,159 m, Anteil mit Daten 0,84). Ergebnis: 0,607 (Median 0,088 m).

## Formbeschreibung (Stufe 0)
Fotos (alle angesehen, Overlay-Ausschnitte `audit/gitter_generator/rundekreis1_helm_geschweift_o_<foto>.jpg`; links Foto, rechts Overlay rot = Modell vorher, gruen = nachher):
nu3b (Nahfoto 17 m, Blick vom Osten), nuaca (21 m, von der Seite), 6132 (22 m, schraeg), 6161 (29 m, Uebersicht), 6145 (33 m), p15 (Handy 12 m, stark verwackelt, nur Anschlussblick).
Projektion der Helmachse (18,72/6,34) in jedem Foto vorher geprueft (L18).
- Zone 1 Fuss/Trauf: Ziegelhaut laeuft stetig konkav (Aufschiebling) bis direkt auf das braune Erkergesims (Oberkante ~13,2-13,3); die Traufkante ist waagerecht. Kein senkrechter Kranz, keine Stufe.
- Zone 2 Schweifung z 13,3-16: stark konkav, Flaechenmitte 1,72 / 1,50 / 1,25 / 1,15 / 1,06 / 0,97 / 0,90 bei z 13,4 / 13,6 / 14,1 / 14,4 / 14,6 / 14,9 / 15,1.
- Zone 3 Schaft z 16-21: schlank, Grate mit hellen Ziegelstreifen; Zone 4 Kupfernadel mit Kugel (z 22) und Fahne.
- Grundriss: regelmaessiges Achteck, eine Flaeche zur Strasse. Von vorn sichtbar: 3 Grate = 2 volle Flaechen + schmale Flaechen am Rand (Z-nu3b-001). Rueckseite ANNAHME (Spiegelung).
- Anschluss: Helm sitzt auf dem Erkergesims (13,18) und ist 0,08 m eingebunden; gleiche Achse (formen/helme.json, Wolke-Phasenfit Achsversatz < 0,04 m).
- Am Altmodell anders: senkrechter Kranz r 1,45 von z 13,1 bis 14,15 und ein Traufring r 1,54 bei z 14,15, im Foto ~1 m ZU HOCH und an der falschen Stelle (Ziegelhaut laeuft weiter hinunter bis auf das Gesims); Overlay nu3b/6132/nuaca vorher rot.
Formfamilie: bestehende `helm_geschweift` (N-Eck, Profil r(z)) reicht, nur das Profil unten war falsch -> keine neue Familie.
Offene Frage: Eckenschweifung (Traufspitzen der Grate stehen im Foto evtl. weiter aussen als ein regelmaessiges Achteck mit Flaechenmitten-Apothem) - nicht entschieden, siehe Beobachtung.

## Ursache
1. M-nu3b-001 (Traufe z 14,22, r 1,54) war eine Silhouetten-Messung in der Ebene durch die Achse quer zum Blick. Die Traufspitze liegt ~1,4 m VOR dieser Ebene, die Kamera 10 m darunter: der Strahl trifft die Ebene ~0,8 m zu hoch (Parallaxe). Das erklaert auch den notierten Widerspruch "Foto 6261 sieht die Traufe 0,7 m tiefer" - 6261 hatte recht.
2. Der Kranz (z 13,1-14,15, r 1,45) war ANNAHME zum Ueberbruecken der falschen Traufhoehe.
3. Die Messzeilen helm_o_r_14_64/16_18/17_76 pruefen nur Hoehen ab 14,64 und haben das untere Drittel (60 % der Teilflaeche) nie gesehen.
4. Ein Teil des Beleg-Mangels bleibt methodisch: die verdeckte Unterseite (Fuss-Wulst, z 13,1) hat keine Wolke (Beleg zaehlt Flaechen mit Normale zur Kamera, nicht verdeckte: L-KR4) - das Band z 13,1-14,1 hat weiter Median 0,37.

## Messung
- `tools/helm_profil_wolke.py` (neu, generisch) -> `messprotokoll/W-helm_o-profil.json`: Phasenfit Achteck gegen Kreis (Achteck besser in allen Baendern, Phase -0,2..-1,6 Grad, Achsversatz <= 0,04 m) und Flaechenmitten-Profil a(z).
- Zwei-Kamera-Triangulation der Traufspitzen (nu3b + 6132): Strahlabstand 0,3-0,4 m, Silhouettenspitzen sind keine Punkte -> verworfen (NICHTS_GEBRACHT).
- Ebenen-Methode durch die Eckrichtung (nu3b Traufspitzen): z 13,27-13,28 fuer die Zuordnung der Spitzen links -67,5 Grad / rechts +22,5 Grad, aber bei anderer Zuordnung 14,1-14,2 -> nicht eindeutig, NICHT als Messwert verwendet.
- Z-nu3b-001: 3 Grate in Zeile 1000.

## Aenderung
`objekt.json` helm_geschweift:o: Profil unten ersetzt (7 neue Ringe z 13,30-15,12), `kranz` 13,1-13,30 r 1,74 (nur Fuss-Einbindung), werte_quellen/historie. Alter Stand in der historie. Sollwerte nicht gelockert; 4 neue Pruefungen helm_o_r_13_45/14_12/14_38/14_88 (am Altstand ROT 1,46/1,46/1,39/1,10, jetzt 1,64/1,27/1,17/1,00).

## Ergebnis
bauen_abnehmen: alle Pruefungen bestanden, 1 Widerspruch offen (Gesamthoehe, vorher bekannt). Druck: 1 Teilnetz, wasserdicht, Wandstaerke 0,14.
Wolkenbeleg Helm O 0,486 -> 0,607, Median 0,159 -> 0,088 m. konvergenz_bericht (Trockenlauf): Recall/Praezision je Band unveraendert bis +0,006 (15-20 m), kein Rueckschritt.
Offen: Helm West hat denselben Fehler (Beleg 0,45), eigene Runde mit eigenen Pruefzeilen; `tools/teile_lage_pruefen.py` stuerzt bei fensterreihe:og ab (trimesh.load liefert Scene), Helme wurden deshalb mit eigener Abstandsmessung (GPU knn) geprueft.

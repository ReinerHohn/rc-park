# Kreis r3 - helm_geschweift:o (Erkerhelm Ost), 2026-11-10

## 1. Formbeschreibung (Stufe 0)
Fotos (mit Modellpunkt projiziert, L18): nu3b (Nah, von der Strasse Ost), nuaca (Nah, Strasse West-Seite), 6132 (Nah, Himmel), 6161 (Uebersicht/Hof), 6145.
- Zonen von unten: Erkergesims (z ~13,2) -> Fussring/Traufkante -> stetig konkave Ziegelhaut (farbige Schuppen) bis z ~19 -> duenne Nadel -> Kugel (z 21,33) -> Fahnenstange/Fahne.
- Grundriss: regelmaessiges Achteck, Flaeche zur Strasse (Grate in Zeile 1000 nu3b), Rueckseite nie sichtbar (ANNAHME N=8). Helm sitzt auf dem Erkergesims, Achse = Erkermitte (u 15,53 / n 12,23).
- Wiederholungen: 8 Grate mit Gratleisten und kleinen Kroeten (nur benannt, nicht modelliert), Ziegelreihen.
- Anschluss: Fussring liegt auf dem Gesims; an den Erkerecken biegen die Traufschnaebel nach oben (nuaca), kein Achteck-Eckpunkt.
- Am aktuellen Modell anders (Overlays vorher): Fussring 1,74 liegt in nuaca/6161/6132 INNERHALB der Traufkante; Profil z 16-20 an der Himmelssilhouette 0,07-0,1 zu schlank.
- Formfamilie: vorhandene `helm_geschweift` (Profil r(z), N-Eck, Kranz, Knauf) - nur Parameter. Keine neue Familie.

## 2. Zaehlungen
Keine neue Zaehlung noetig (Grate/N bleiben ANNAHME wie in Z-nu3b-001: 3 Grate in Bildzeile sichtbar, Rueckseite nie). Kein Z-Protokoll neu.

## 3. Pruefungen (vorher -> nachher)
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| helm_o_r_13_25 Fussring Apothem z 13,25 | 1,75 FEHLER | 1,90 ok | 1,82-1,98 | Kantengitter-Ring 1,92 (W-helm_o-fuss) + Overlay; Wolke-Mitte 1,72-1,76 widerspricht, nicht gemittelt |
| helm_o_r_19_40 Apothem z 19,4 | 0,20 FEHLER | 0,27 ok | 0,24-0,31 | Silhouette gegen Himmel, 6 Fotos (M-sil-helm_o-1) |
| alle anderen 78 | ok | ok | - | unveraendert |
Abnahme alter Stand: nur diese zwei rot; neuer Stand: "alle Pruefungen bestanden".

Konvergenz (konvergenz_bericht, gleiches Werkzeug/Daten, Messlauf --trocken): Beleg 0,607 -> 0,638, Kanten Recall 0,357 -> 0,504, Praezision 0,201 -> 0,276, F1 0,257 -> 0,357, Guete (Mittel) 0,432 -> 0,498 = +0,066 (Tor +0,05; keine Groesse faellt). Kein Rueckschritt gemeldet.

## 4. Overlays (Vorher links, Nachher rechts, kein Sichtbarkeitstest: Rueckkanten laufen durch)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis3_helm_geschweift_o_{nu3b,nuaca,6132,6161,6145}.jpg
Angesehen: nuaca, 6132, 6161 (Fussring und Silhouette z 16-20 sitzen nachher besser), nu3b und 6145 nur erzeugt, nicht einzeln durchgesehen.

## 5. Fehlerliste
- Fussring vorn/Seiten (Traufkante): trifft (nuaca, 6161, 6132 angesehen); Ecken/Traufschnaebel: trifft NICHT (kein Achteck-Eckpunkt, ~78 px Versatz in nuaca), offen.
- Schweifung z 13,6-15,1: unveraendert (Wolke-Mitte), im Overlay plausibel, nicht neu gemessen.
- Profil z 16-18,6: Silhouette ungeprueft (Himmel fehlt beidseitig), Wolke-Mitte +0,04-0,06 gestuetzt; z 19-20: gemessen (M-sil-helm_o-1).
- Nadel/Kugel: unveraendert; Fahne, Gratleisten, Kroeten: nicht modelliert. N=8 und Rueckseite ANNAHME.
- Gitter v12 liegt bei z 16-21 0,1-0,2 m ausserhalb von Foto und Wolke: Recall-Obergrenze, nicht modelliert (Beobachtung in masstabelle).
- Abstand zu fremden Teilen: teile_lage_pruefen helm_geschweift:o Median 0,12 m, nicht markiert. fehlteile_finden lief im Abnahmelauf, Bilder nicht einzeln angesehen. teile_sichtpruefung nicht gelaufen (Gate nicht bewiesen). tools/regression.py nicht noetig (nur neues Werkzeug, bestehende unveraendert).

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (helm_geschweift:o profil, kranz, werte_quellen, historie), masstabelle.json (Beobachtung + 2 Pruefungen + 2 Messungen), messprotokoll/M-sil-helm_o-1.json, messprotokoll/W-helm_o-fuss.json, tools/helm_silhouette_foto.py (neu), NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, Abnahme-Erzeugnisse (STL, audit, pruefbericht).

## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug
Rotationsteil: Gitterpunkte als r(z)-Diagramm gegen Profil, Wolke und Foto-Silhouette lesen; Kantenpunkte mit Praezision ~0 in einem z-Band sind der Hebel (Helmfuss), Phasen-/N-Sweeps sind nur Metrik-Anpassung | Helm O Guete 0,432 -> 0,498 | tools/helm_silhouette_foto.py, agent_scratch_kreis3/ev.py (Einzelteil-Guete in ~10 s)
(Eintrag L-KR15 in REZEPT_GEBAEUDE_AUS_FOTOS.md, Sackgassen in NICHTS_GEBRACHT.md.)

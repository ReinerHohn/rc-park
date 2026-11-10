# Kreis-Bericht 035447a035447 r2: bogenreihe:laube (kaufhaus_grob3, 2026-11-10)
Stand: nichts committet. Branch kreis/kaufhaus_grob3/20261110_035447a035447-r2.

## 1. Formbeschreibung (Stufe 0)
Fotos (angesehen): 6117 (Nah, Bogen 2/3 schraeg), 6119 (Nah, Bogen 3 fast frontal), 6120 (Uebersicht-Nah, Bogen 3 frontal, Blick auf alle Konsolen darueber), handy_15 (Handy, Bogen 2/3 schraeg von unten). Bogenmitten vorher in jedes Foto projiziert.
- Zone Pfeiler z 1,45-5,28: runder Schaft R 0,44 auf achteckigem Sockel mit Fase (Sockelmasse in Vorversuchen s8/a021332 nach Foto korrigiert, hier NICHT angefasst).
- Zone Bogen z 5,28-7,5: Der Bogenrand ist GESTUFT: ein Steinring (~0,3 m breit, goldene Linie darin, schwarze Aussenlinie) liegt vorn buendig mit der Bandfront, die Laibung (innere Goldlinie) springt dahinter zurueck. Das Modell hatte nur EINE Frontkante (Laibung), ~0,3 m unterhalb der sichtbaren Aussenkante des Rings.
- Zone Band z 7,5-8,0 bis Balkonkonsolen: glatter Putz, Band und OG-Wand eine Ebene (Koordinator R6); darueber Konsolen (anderes Bauteil).
- Grundriss/Querschnitt: Rechteckband (Stirn s 12,66, Laibung 0,94 tief) mit 4 Segmentbogen-Oeffnungen auf 5 runden Pfeilern; 4 Bogen gezaehlt (Z-004-003, Z-004-001 gelten weiter, keine neue Zaehlung).
- Wiederholung: 4 gleiche Boegen, Gitter v12 zeigt in allen vier den gleichen Ring (r-R = +0,31).
- Anschluss: Bogenring setzt am Pfeilerkopf (Kaempfer 5,28) an; Aussenkreis hat dieselbe Mitte wie der Laibungskreis (R 2,72, Mitte z 4,40).
- Formfamilie: bestehende `bogenreihe` (baukasten_gen), um zwei optionale Parameter erweitert (archivolt_breite, archivolt_tiefe) - generisch, kein Objektname im Code.
- Ursache des Befunds (Zerlegung der Kanten-Praezision 0,109, `agent_scratch_kreis2/praez.py`): (a) Stirnbogenkante ohne Fotobeleg ~640 Punkte, (b) 25-m-Kante Bandoberkante z 8,0 (1038 Pkt, Gitter hat bei z 8,0 nichts), (c) Facetten-/Sockelringe z 1,5-2,2 (2400 Pkt). Die drei Vorversuche bewegten nur (c) und kamen auf Gewinn ~0,013.
- Unsicherheit: Archivolt-Tiefe 0,22 und senkrechte Stufe = ANNAHME aus dem Gitter (s 12,4-12,5 gegen 12,66); Breite 0,31 aus Gitter (280 Segmente), nicht per foto_mass trianguliert, nur Overlay in 4 Fotos.

## 2. Zaehlungen
Keine neue Zaehlung (Anzahl 4 Boegen / 5 Pfeiler bleibt Z-004-003/Z-004-001). Archivolt-Ring: 4 von 4 Boegen im Gitter, im Foto 6119/6120 Bogen 3 sichtbar (Ring pro Bogen = gleiche Familie, nur Bogen 2/3 am Foto angesehen).

## 3. Pruefungen
| Pruefung | vorher (Altstand) | nachher | Soll | Quelle |
|---|---|---|---|---|
| Arkade Bogen 3: Archivolt-Ring, tiefster Festkoerper z an der Stirn (bogen3_archivolt_z) | 7,12 ROT | 7,44 gruen | 7,33-7,53 | Kantengitter v12, r-R = +0,31, Scheitel 7,12+0,31 |

Gate-Messung (Trockenlauf `konvergenz_bericht.py` auf dem Neubau, gleiche Parameter wie der Kreis):
| Groesse bogenreihe__laube | vorher | nachher |
|---|---|---|
| Wolkenbeleg | 0,697 | 0,725 |
| Kanten-Recall | 0,777 | 0,820 |
| Kanten-Praezision | 0,109 | 0,295 |
| F1 | 0,191 | 0,434 |
| Gate-Mittel (Beleg, F1) | 0,444 | 0,580 (+0,135) |
Gesamt-Recall 0,648 -> 0,655, Gesamt-Praezision 0,076 -> 0,082, kein Band-Rueckschritt.

Abnahme `tools/bauen_abnehmen.sh kaufhaus_grob3`: "alle Pruefungen bestanden" (1 vorbestehender Widerspruch, 50 Beobachtungen ohne Pruefung), Gegenproben CB bestanden. audit/seiten.jpg angesehen: 4 Boegen Nordseite plausibel, keine neuen Artefakte. Die Gate-Messung ist ein Trockenlauf auf dem Neubau, nicht der Kreis-Lauf selbst.

## 4. Overlays (cyan = Altstand, rot = Neustand; nur Stirnkanten der Bogen, ohne Verdeckungstest)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_laube_archivolt_{6117,6119,6120,handy_15}.jpg
Selbst angesehen: 6119, 6120, handy_15 - rote Aussenkante liegt auf dem Steinring, rote Innenkante auf der Goldlinie, cyan lag deutlich tiefer. 6117 nur schmaler Ausschnitt (schraeg), grob stimmig.

## 5. Fehlerliste
- Bogenstirn Aussenring (Bogen 2, 3): trifft (6119, 6120, handy_15). Bogen 1, 4: ungeprueft am Foto (nur Gitter).
- Laibungskante Stirn: trifft (6119, 6120), Abweichung ~1-3 px.
- Stufentiefe 0,22: ANNAHME, am Foto nicht gemessen (ungeprueft).
- Ringansatz am Pfeilerkopf: trifft grob (Linien enden am Kaempfer), Kapitellform nicht modelliert.
- Bandoberkante z 8,0 / Naht: trifft NICHT (Kante ohne Fotobeleg, Gitter hat sie nicht) - nicht geaendert, naechster Hebel.
- Sockel/Facettenringe z 1,5-2,2: Praezision 0,0-0,1, ungeprueft ob Gitter-Fehler (Gitter-Ring z 2,3 vs Foto 2,53, offene Beobachtung der Vorversuche).
- Gewoelbe hinter dem Band: nicht modelliert.
- Nicht gelaufen/ungesehen: `teile_lage_pruefen`, `teile_sichtpruefung`, `regression.py` (keine Werkzeugaenderung ausser baukasten_gen bogenreihe, nur mit neuem optionalem Parameter - fuer andere Objekte ohne Wirkung).

## 6. Geaenderte Dateien
tools/baukasten_gen.py (bogenreihe: archivolt_breite/archivolt_tiefe, beleg), modelle/kaufhaus_grob3/objekt.json (bogenreihe:laube +2 Parameter, werte_quellen, historie), masstabelle.json (+Messung bogen3_archivolt_z, +Pruefung, +Beobachtung), REZEPT_GEBAEUDE_AUS_FOTOS.md (L-KR14), NICHTS_GEBRACHT.md, audit/gitter_generator/rundekreis2_laube_archivolt_*.jpg, STL/Pruefberichte (Neubau).

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Niedrige Kanten-Praezision zuerst nach Kantengruppen zerlegen (je Modellkante Abstand zum Gitter, nach z/Laenge), dann Gitter um die Stelle als Polarhistogramm (r-R, s) ansehen: gestufte Raender sind dort sofort sichtbar | Laube: 3 Vorversuche am Sockel brachten +0,013, der fehlende Bogenrand +0,135 | agent_scratch_kreis2/praez.py (noch nicht in tools/) |
| Overlay mit nur den Kanten der betroffenen Stelle (Zone, Schichtfilter) statt aller Dreieckskanten | bauteil_overlay.py unlesbar/Absturz | agent_scratch_kreis2/ov_bogen.py |

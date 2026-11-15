# Massnachweis Schwabentor (automatisch aus masstabelle.json, 2026-11-15)

Status je Mass: **OK** = Istwert im Sollbereich der Quelle; **WIDERSPRUCH** = Quellen uneins (nicht gemittelt); **FEHLER** = Modell verletzt die Quelle.
Massstab: *dokument/lod2/laser* = absolut; *foto_intern* = bekanntes Mass im selben Foto; *modell* = zirkulaer (nur Richtung belastbar).

| Merkmal | Ist | Soll | Quelltyp | Massstab | Status | Quelle |
|---|---|---|---|---|---|---|
| Wasserdicht (1=ja) | 1.00 | 1..1 | modell | - | OK | Druckfaehigkeit |
| Anzahl getrennte Koerper | 1.00 | 1..1 | modell | - | OK | Schwebende Teile |
| Traufkante Nord: Abstand von Dachmitte bei z 39,05 (m) | 7.03 | 6.85..7.25 | sfm_bodenanker | sfm_buendel | OK | Foto-Triangulation foto_mass.py --tri, 5-6 Fotos der Nordseite mit SfM-Punkten in Dachhoehe, Strahlabstand 1-12 cm; Traufecken A x 4,85 / C x 4,92 (M-113205-002/-003), Dachmitte x -2,15 = Mitte der Waende (Nordwand x 3,69 aus M-113205-006/-007, Suedwand LoD2 -8,0) -> 7,03 +-0,2 (Tiefe entlang der Blickrichtung) |
| Traufkante West (+y): Abstand von Dachmitte bei z 39,05 (m) | 7.23 | 7.08..7.38 | sfm_bodenanker | sfm_buendel | OK | Foto-Triangulation foto_mass.py --tri, 5-6 Fotos der Nordseite mit SfM-Punkten in Dachhoehe, Strahlabstand 1-12 cm; Traufecke A y 22,51 (M-113205-002), Dachmitte y 15,28 -> 7,23 +-0,15 |
| Traufkante Ost (-y): Abstand von Dachmitte bei z 39,05 (m) | 7.12 | 6.97..7.27 | sfm_bodenanker | sfm_buendel | OK | Foto-Triangulation foto_mass.py --tri, 5-6 Fotos der Nordseite mit SfM-Punkten in Dachhoehe, Strahlabstand 1-12 cm; Traufecke C y 8,16 (M-113205-003), Dachmitte y 15,28 -> 7,12 +-0,15 |
| Traufe Nord Oberkante z bei x 4,75 (m) | 39.38 | 39.1..39.5 | sfm_bodenanker | sfm_buendel | OK | Foto-Triangulation foto_mass.py --tri, 5-6 Fotos der Nordseite mit SfM-Punkten in Dachhoehe, Strahlabstand 1-12 cm; Traufecken z 39,15 / 39,20 (M-113205-002/-003); Dachflaeche steigt bis x 4,75 um ~0,15 m |
| Dachflaeche Nord bei z 45: Abstand von Dachmitte (m) | 2.97 | 2.6..3.3 | sfm_bodenanker | sfm_buendel | OK | Foto-Triangulation foto_mass.py --tri, 5-6 Fotos der Nordseite mit SfM-Punkten in Dachhoehe, Strahlabstand 1-12 cm; Gerade Traufe (4,88 / 39,18) - Laternenfuss (-0,77 / 47,28) (M-113205-004) -> x 0,82 bei z 45 = 2,97 m von der Mitte; +-0,35 (Tiefe); Neigung 55,1 Grad, Gegenprobe Laser DOM1 56,1 |
| Gesamthoehe mit Laterne (m) | 55.30 | 54.2..55.8 | sfm_bodenanker | sfm_buendel | OK | Foto-Triangulation foto_mass.py --tri, 5-6 Fotos der Nordseite mit SfM-Punkten in Dachhoehe, Strahlabstand 1-12 cm; Knauf ueber der Zwiebelhaube z 54,17 (M-113205-005); darueber Spitze (ANNAHME bis ~1,5 m, nicht gemessen). WIDERSPRUCH zu objekt.json hoehe_m 50,8 - nicht gemittelt, Nutzer gemeldet |
| Nordwand Uhrgeschoss: Abstand von Dachmitte bei z 36 (m) | 5.98 | 5.7..6 | sfm_bodenanker | sfm_buendel | OK | Foto-Peilung foto_mass.py --tri2d: Wandecken A' (3,60 / 21,36) und C' (3,78 / 9,20) (M-113205-006/-007) -> Wand x 3,69 = 5,84 von der Mitte; LoD2 3,54..3,92 |

## Belegt durch

- **modell**: 2 von 2 Pruefungen gruen (Druckbarkeit, keine Realitaetsaussage)
- **sfm_bodenanker**: 7 von 7 Pruefungen gruen (COLMAP-Netz je Fassadenseite (tools/sfm_ausrichten.py), 7 Parameter aus LoD2-Eckkanten in >= 4 Fotos, Hoehenlage aus ANNAHME Strassenkamera 1,7 +- 0,6 m; Massstab +-2-3 %, Hoehe +-0,7 m systematisch; sieht keine Fassadenzaehlung (Punkte, keine Semantik). Register AH)

## Elemente des Generators: 6 belegt, 0 Annahmen

- wand: Grundriss Teil 0 - LoD2 DEBW_001000hPLcp GroundSurface 0
- wand: Teil 1 (ohne Dachmessung) - LoD2 DEBW_001000hPLcp Wandoberkante (31 eigene Waende)
- wand: Grundriss Teil 1 - LoD2 DEBW_001000hPLcp GroundSurface 1
- dach: Zeltdach mit Ueberstand - Foto-Triangulation Nordseite (foto_mass.py --tri, M-113205-002/-003/-004)
- wand: Hauptteil Wand bis Traufe - LoD2 DEBW_001000hPLcp GroundSurface 0; Nordwand am Foto bestaetigt (M-113205-006/-007)
- dach: Laterne mit Zwiebelhaube - Knauf-Hoehe 54,17 m aus Foto-Triangulation (M-113205-005)

## Beobachtungen ohne Pruefung

- heute Anlage: Quellen sichten: Dokumente (Hoehe), LoD2 (Grundriss/Traufe), DOM1 (Dachform), Fotos je Seite -> objekt.json/quellen fuellen, Zeilen mit Quelle anlegen
- 2026-11-15 Nutzer (3D-Seite, Bildschirmfotos 12:14): Turm trifft die Wolke noch nicht ganz: Wolkenwand liegt an der Kante sichtbar neben der Modellkante -> Turmbreite am Foto messen (tools/foto_mass.py, je Seite eine waagerechte Strecke auf 2 Hoehen) gegen LoD2 12,13 x 12,50 m; pruefen, ob Sockel breiter als Schaft (LoD2 = Katasterumring am Sockel)
- 2026-11-15 Nutzer (3D-Seite): Das Dach ist ein ueberstehendes Dach - Modell hat keinen Dachueberstand; Dachpunkte der Wolke liegen ausserhalb der Modelldachflaeche -> Traufhoehe, Ueberstand und Dachneigung am Foto messen (foto_mass.py an Drohnenbildern NW-Mt7ryZ8c vf_000..003 und Schlossbergfotos 1107/1108/1112; Kanten-Sweep mit --band 1.5 um die Dachflaeche) -> dach.json nicht aus DOM1, sondern Foto (Regel 9d) -> Generator: Ueberstand + Gesims
- 2026-11-15 Nutzer (3D-Seite): Das Fachwerkhaus nebenan hat keine Modellkanten -> LoD2-IDs der beiden Nachbarhaeuser bestimmen (Kandidatenliste rc-park_daten/schwab_v3/pipe/kandidaten.log, 16 Gebaeude im Umkreis), als eigene Teile/Objekte mit gebaeude_aus_lod2 anlegen (gleicher Rahmen), dann je Haus Kantenstufe + Bauteile
- 2026-11-15 Claude: Drohnenclip NW-Mt7ryZ8c: 22 von 23 Bildern im Dichtsatz sind eine Insel-Kette (0 % Fremdstuetze, Flug ~500 m bis hinter das Muenster, im SfM auf 27 m zusammengefallen). Ihre Miniaturstadt schwebte in z 25-32 m um den Turm (16 686 Sparse-Punkte im 35-m-Umkreis). Nach Ausschluss: schwebende Punkte z 24-34 m, 10-35 m um den Turm 94 725 -> 6 282, Dachpunkte z>40 m 2 491 -> 2 433. -> erledigt fuer die Wolke (tools/kette_insel_pruefen.py + wolke_neu_fusionieren.py); offen: Pruefung in pipeline_objekt.py/gesamtkette.py als Tor nach dem Mapper einbauen und K-Dateien der Insel-Bilder fuer Fotomessungen sperren
- 2026-11-15 Claude: Dachmessung am Foto (Traufecken, foto_mass.py --tri) scheitert an den Kameras in Dachhoehe: dieselbe Traufecke B aus 6 Fotos -> Strahlabstaende 0,26-0,87 m; Fotogruppe -x-Seite ergibt z 34,5 m, Gruppe +y-Seite z 39,9 m. Rueckprojektion der SfM-Punkte je Bild ist dagegen ~1 px (K-Dateien = SfM). VORLAEUFIG: Traufecke A (+x,+y) = (4,86 / 22,50 / 39,40) m aus 2 Fotos mit 57 Grad Schnittwinkel (M-113205-001), Wolke zeigt Traufe bei ~39-40 m, Modell 36,7 m. Kein Sollwert. -> Kameras in Dachhoehe verfeinern: Handpicks der 4 Traufecken + Laternenfuss als Verknuepfungspunkte in einen Buendelausgleich (Drehung je Foto frei, Lage fest), danach Traufhoehe/Ueberstand/Neigung neu mit foto_mass.py --tri (>= 3 Fotos je Ecke, Strahlabstand < 0,1 m als Tor). Nebenbefund: foto_mass.py findet die v3-Fotos nicht fuer den Protokollausschnitt (fotos_dir zeigt auf daten/schwabentor/fotos, v3-Fotos liegen in rc-park_daten/schwab_v3/fotos)
- 2026-11-15 Claude: DACH AM FOTO GEMESSEN (Nordseite +x, 5-6 Fotos mit SfM-Punkten in Dachhoehe, Strahlabstaende 1-12 cm): Traufecke A (+x,+y) = (4,85 / 22,51 / 39,15) m [M-113205-002], Traufecke C (+x,-y) = (4,92 / 8,16 / 39,20) m [M-113205-003], Laternenfuss vorn Mitte = (-0,77 / 15,04 / 47,28) m [M-113205-004]. Daraus: Traufe aussen oben 39,18 m (Modell 36,7 m), Trauflaenge Nordseite 14,35 m gegen LoD2-Wand 12,16 m -> Ueberstand ~1,1 m je Seite, Neigung Nordflaeche 55,1 Grad (DOM1 56,1), gedachte Spitze der Pyramide ~49,5 m (DOM1 max 49,62). URSACHE der frueheren Widersprueche: Der Turmkopf (z > 36 m) hat SfM-Punkte nur aus Richtung Nord (Azimut -23..+11 Grad); Bodenfotos der anderen drei Seiten haben 0-1 Punkte in Dachhoehe, ihre Kameras sind dort nicht verankert (M-113205-001, M-114037-001/-002 sind damit ungueltig). -> Generator: Dach als Zeltdach mit Traufe 39,18 m, Ueberstand 1,1 m, Neigung 55 Grad, Pyramidenstumpf bis Laternenfuss ~47,3 m + Laterne (Hoehe der Spitze noch messen); vorher Wandoberkante/Holzgalerie unter der Traufe und Laternenspitze am Foto messen (gleiche Fotos 113231/113205/113106/113029/113128/113201). Andere drei Seiten: Fotos mit Abstand (flacher Blick) suchen oder SfM am Turmkopf verdichten; bis dahin ANNAHME Dach symmetrisch.
- 2026-11-15 Claude: Gesamthoehe: Knauf der Laterne am Foto 54,17 m (M-113205-005, 5 Fotos), objekt.json hoehe_m sagt 50,8 m. Quellenwiderspruch, nicht gemittelt. -> Herkunft von hoehe_m 50,8 pruefen (Dokument? ohne Laterne?); Laternenform (Pfosten, Krempe, Zwiebel, Spitze) am Foto messen - bisher ANNAHME

## Grenze

Offene Daten (Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe) beweisen keine Masse auf den Zentimeter.
Dieser Nachweis sagt je Mass, welche Quelle es stuetzt und wie belastbar der Massstab ist; mehr ist ehrlich nicht moeglich.

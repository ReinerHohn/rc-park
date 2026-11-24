# Weg Hand -> Kette: wie schwab_v3 entstand und wo die Kette denselben Weg verliert (24.11.2026)

Auftrag Nutzer 24.11.: "Untersuche, wie das Modell [Handstand schwab_v3] entstanden ist, und den gleichen Weg musst du automatisch durchgehen."
Nur gelesen, keine Rechenläufe. Belege: Log `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-null-1122zb.log` (zb) und
`...-1122zc.log` (zc, um 21:48 im bauplan abgebrochen; `modelle/schwabentor-1122/audit/*.json` enthält deshalb teils den Stand zc, teils zb).
Bilder: Ziel `modelle/schwabentor-1122/bestand/ZIEL_handstand_schwab_v3__neben_113029.jpg`, Kette `/media/oem/rcdaten/tmp/treppe_agent/neben_nachher.jpg`,
`audit/neben_details.jpg`. Seiten: f00 = Nord/Stadtseite, f01 = Süd, f02 = Ost, f03 = West (nach `o`/`n` in fenster_auto.json, nicht aus Fließtext).

## Der Handweg (modelle/schwab_v3_gen.py, 15.-17.11.)
Er hatte vier Schritte, und jeder Schritt hatte genau einen Verbraucher:
1. Je Bauteil wurden 2-6 Punkte auf 1-2 Fotos von Hand gepickt. `tools/foto_mass.py --tri/--tri2d` hat daraus auf der Wandebene gemessen und die Protokolle M-<foto>-<nr> geschrieben (56 Stück).
2. Je Bauteil gab es einen TYPISIERTEN Bau mit diesen Zahlen (Galerie, Pultdach, Rundbogen mit Nische, Spitzbogen, Zifferblatt, Laterne). Fehlende Maße wurden als ANNAHME gesetzt und gebaut.
3. Das Relief kam aus dem OpenMVS-Netz, aus relief_aus_fotos_mono und aus tiefe_lokal. Die Steine kamen aus fassade_fein und steine_aus_foto.
4. Der Maßstab kam aus dem DOM1-Laser (MK 0,933), der Grundriss aus LoD2 x MK.
Kern des Handwegs: Eine unsichere Tiefe oder Form hat NIE das Bauteil gestrichen. Es wurde mit ANNAHME gebaut.
Die Kette verwirft an dieser Stelle und fällt auf Höhenfeld, Kasten oder nichts zurück.

## Je Bauteil (alle beleg()-Einträge von schwab_v3)

### Holzgalerie Nord (schwab_v3_gen.py:128-138, M-113231-001..-004, bauteile.Wand.galerie)
- Kette: fassade_tiefe (Sweep) -> vorbauten_bauplan (Grobband + `galerie`-Block mit Pfosten und 6 Streben aus dem Wandbild) -> ebenen_bauplan (Kanten auf der Erkerebene) -> ebenen_masse (Kasten, Konsolen, Pfosten, Brüstung) -> bauteile.vorbauten_aus_json.
- Status: FEHLT als Gestalt. Gebaut wird das treppige Höhenfeld (Bild: Kasten mit Klötzen, keine offene Brüstung, keine Pfosten).
- Bruch 1 `tools/ebenen_bauplan.py:101`: Frontale SfM-Kameras werden nur bei `art == "wand"` ergänzt. Die Erkerebene f00_vb0 hatte in zc 3354 Punkte (in 1121k waren es 47 000-54 000). Auch die Wand f00 hatte nur 30 207 Punkte, Süd/West dagegen 109 000/137 000.
- Bruch 2 `tools/ebenen_masse.py:98-100`: Die Front ist die Spitze des Histogramms über w > 0,4. Mit wenigen Punkten liefert sie 0,46 m (ebenen_masse.json), die Hand misst 1,45 m. Dann gibt es nur 1 volle Linie (z 9,71) -> `:109` kein Kasten -> rc 3 "Grobmass bleibt" (Log zb Z. 157, zc Z. 97).
- Bruch 3 `tools/bauteile.py:1011` + `:1023-1031`: Ohne `kanten_mass.kasten` wird der gemessene `galerie`-Block (u -3,82..4,66, Boden 10,42, Holm 12,82, 6 Streben) nur mit MIT_KATALOG_GALERIE=1 gebaut. Sonst entsteht das Höhenfeld aus 0,5-m-Zellen.
- Abgleich mit referenz_hand: Breite 8,48 gegen 8,06 ✓, Boden 10,42 gegen 10,22 ✓, Holm 12,82 gegen 11,42 ✗ (+1,4), Ausladung galerie.w 0,84 gegen 1,45 ✗, Pfosten 2 gegen 3.

### Vordach Nord, geschweift (schwab_v3_gen.py:129-140, M-113128-001..-004)
- Kette: vorbauten_bauplan `galerie.vordach` (Traufe 16,62 / Anschluss 20,19) -> vordach_profil (Walm/Schweifung aus Silhouetten) -> bauteile.vordach_walm.
- Status: FEHLT (Bild: ebene Klötze).
- Bruch `tools/vordach_profil.py` (rc 3 "kein Vordach (kanten_mass.kasten + galerie.vordach fehlen)", zb Z. 159) hängt am fehlenden Kasten der Galerie. Gleiche Wurzel wie dort. Der Zweig für die ebene Platte (bauteile.py:1002) liegt auch hinter `if KM_ and KM_.get("kasten")`.

### 2 Rundbogenfenster Nord: Blendnische + Öffnung + Sohlbank (schwab_v3_gen.py:114-124, M-113029-001..-007)
- Kette: fassade_parsing (OWLv2) -> nischen_fenster (Umriss aus Kanten, Formfamilie aus >= 3 Fotos) -> sohlbank_aus_fotos -> fenster_aus_json.
- Status: TEILWEISE. In zb sind beide Öffnungen da (rund, 16/19 und 15/16 Fotos, u -2,34..-1,70 und 1,81..2,42, z 23,19). Die Nischen fehlen beide, die Sohlbänke auch.
- Bruch `tools/nischen_fenster.py:333`: Eine Nische mit belegter Form (zone_aussen 2,15 m, rund) wird verworfen, wenn die Sweep-Tiefe "nicht messbar" ist. Bei der Fensteröffnung setzt `:324-326` in derselben Lage eine ANNAHME-Tiefe und baut. Die Hand setzte die Nische mit 0,15 m als ANNAHME.
- Sohlbank: `sohlbank_aus_fotos` rc 0, aber "Auskragung aus keiner Messung plausibel" -> keine Bank. Auch hier fehlt der ANNAHME-Bau.
- Stand zc: fenster_auto.json f00 hat nur noch ein Fenster (fenster_tiefe_tor, Lauf abgebrochen) - im nächsten vollen Lauf prüfen.

### Uhr Nord + Süd, Balkenköpfe (schwab_v3_gen.py:142-149, 227-229, M-113029-008..-012, M-commons127)
- Kette: uhren_wandbild (Kreis-Hough + 12er-Teilung + Zifferblatt-Relief aus 9 Fotos) -> bauteile.uhren_aus_json.
- Status Nord: LÄUFT (zb Z. 181). d 5,08/3,35, z 32,03; Referenz 5,17 / 31,92 ✓.
- Status Süd: TEILWEISE. f01 "kein Zifferblatt (12er-Teilung 1,01 x Fremdperiode)", nur der Ring wird gebaut.
- Balkenköpfe: FEHLT als Klotz. schlitze_wandbild trägt sie als dunkle Löcher ein (f00 z 33,96). Es gibt keine Stufe für kleine Vorsprünge.

### Tordurchfahrt Nord/Süd (schwab_v3_gen.py:101-112, 220-221, M-113602-001..-006)
- Kette: oeffnungen_bogen -> oeffnungen_aus_kanten --uebernehmen (Familie spitz) -> durchfahrt_pruefen -> bogen_gewaende -> oeffnungen_aus_json.
- Status: LÄUFT (zb Z. 185-189; neben_details zeigt den Spitzbogen mit Gewände).
- Abweichungen: Nord Breite 4,85 (lichte Weite der Hand 4,32, außen 5,10), Kämpfer 3,84/3,97, Scheitel 6,91/6,42. Süd Scheitel 6,69 gegen Hand 5,85 (+0,8).

### Dach: Zeltdach mit Knick, 4 Traufecken (schwab_v3_gen.py:162-181, M-113205-016/-025, M-commons127-011/-012, M-113029-012/-013)
- Kette: traufe_aus_fotos, dachflaeche_aus_umriss, dach_aus_profil.
- Status: TEILWEISE. Die Familie wird "gerade" (zb Z. 201). Der Knick bei 0,66 des Achsabstands (Aufschiebling) ist nur als `z_fuss_knick` am Fuß verdrahtet (`tools/dachflaeche_aus_umriss.py:245`).
- Traufe -d: z_unten 37,68, Überstand 1,08. Hand: 36,62 / 0,83-0,9 -> +1 m. Siehe Agenten "Kanten über Traufe" und "Maßstab".

### Laterne (schwab_v3_gen.py:183-194, M-113205-017..-024)
- Kette: spitze_aus_umriss + laterne_aus_fotos -> bauteile.laterne.
- Status: LÄUFT (zb Z. 197: 4 Pfosten, Familie Zwiebel; neben_details zeigt die Laterne).

### Offener Umgang unter der Traufe (schwab_v3_gen.py:292-297, Fotos 110756/113029, bauteile.umgang)
- Kette: umgang_aus_fotos -> umgang_aus_json.
- Status: TEILWEISE. Gefunden wird z 35,8-36,67. Bei den Pfosten nimmt die Kette 2 je Seite (Mehrheit über die Wände), obwohl f00 allein 4 zählt (`tools/umgang_aus_fotos.py:170/185`); die Hand zählt 4. Im Bild ist kein Rücksprung zu erkennen.

### Wandlagen Nord/Süd/West/Ost (schwab_v3_gen.py:65-74, 150-157, 237, 300)
- Kette: wandlage_fotokanten -> korrekturen_aus_json.
- Status: TEILWEISE. f00 hat einen Versatz in schleife_korrekturen. Für f02/Ost ist "keine RANSAC-Wandebene (fassade_tiefe nicht belastbar)" (zb Z. 163). Die Neigung f03 liegt bei 1,55 Grad (Lot).

### Grundriss/Maßstab (schwab_v3_gen.py:21-33, MK 0,933 aus DOM1)
- Kette: Ausrichtung + hoehe_gegen_dom1 / seiten. Status: siehe Agent "Maßstab" (verlorene_gewinner Punkte 1-3). Nicht Teil dieser Prüfung.

### Relief und Quader N/S/W/O (schwab_v3_gen.py:75-99, 202-219, 238-263, 300-304)
- Kette: fassaden_kette (Netz-Relief, Quader-Tor, steine_aus_foto) + mono + ortsteine.
- Status: LÄUFT für die Ortsteine (zb Z. 183: Tor 7/7 Kanten) und für Mono auf 6 Wänden (rc 0, eine Wand rc 4).
- Eine Wand sagt "Quader-Tor rc 5 - ganze Wand Putz" (zb Z. 91). Am Turm ist die Mitte tatsächlich Putz, die Ecken sind Quader. Das deckt die Ortsteine-Stufe ab.
- Steingewände Süd/West-Fenster (schwab_v3_gen.py:222-225, 256-259): loch_gewaende läuft. Nicht am Bild bestätigt.

### Süd-/Westfassade: Fenster, Schlitze, Gesims, Verdachung (schwab_v3_gen.py:226-232, 264-269)
- Fenster Süd/West, 4 Schlitze West: LÄUFT (fenster_auto f01 0,98 m bei z 23,18, Hand 0,92 bei 22,26; schlitze_wandbild "6 kleine Öffnungen").
- Gesims Süd/West (z 26,0-26,53) und Verdachung Süd: FEHLT. gesamtkette.py hat keine Gesims-Stufe (verlorene_gewinner Punkt 7). Waagerechte Kantenhaufen gibt es, aber niemand liest sie (siehe unten).

### Ostfassade: Schlitz, Luke, Balkenkopf (schwab_v3_gen.py:298-311, M-od_15-001..-007)
- Status: TEILWEISE. Für f02 gibt es kein fenster_auto. Der Ost-Sweep ist nicht belastbar, außerdem gibt es Fotolücken (foto_auftrag).

### Treppenturm (schwab_v3_gen.py:271-291, M-054-001..-005)
- Kette: koerper_schleife + rund_aus_umriss (r 1,55 ✓ Hand 1,555) + rund_aus_huelle.
- Status: TEILWEISE. Die Haube fehlt: rund_aus_huelle rc 4 "Spitze 15,4 nicht über Traufe 15,3" (zb Z. 207), im Bild steht ein Kegel. Siehe Agent "Kegeldach".

### Turm hohl, Fenster durchgebrochen (schwab_v3_gen.py:313-323)
- Kette: aushoehlen in der Generator-Vorlage. Status: LÄUFT.

## Die gemeinsame Lücke: "Punkte picken -> Maß" hat keinen automatischen Verbraucher
- Die Kantenstufe schreibt `fehlende_kanten_haufen` (tools/kantenstufe.py:178). Weder gesamtkette.py noch ein Werkzeug liest sie (grep: 0 Leser). Das deckt sich mit verlorene_gewinner Punkt 8.
- foto_mass.py läuft nur von Hand (`--tri` braucht Pixel je Kamera). In der Kette gibt es keinen Schritt "Haufen/Bauteilzone -> Kantenpunkte -> typisiertes Maß -> Bauteil".
- Jeder Erkenner hat ein hartes Tor (Kasten, Nischentiefe, Zifferblatt, Haube). Scheitert es, wird das Bauteil gestrichen oder generisch gebaut. Die Hand hat bei gleicher Unsicherheit typisiert gebaut und die Lücke als ANNAHME belegt.
- Vorschlag: ein Grundsatz für alle Stufen. Ist die Form aus >= 3 Fotos belegt und nur ein Maß fehlt, wird das typisierte Bauteil mit ANNAHME gebaut, mit Beleg und rotem Hinweis. Verworfen wird nur bei widerlegter Form.

## Rangliste der Bruchstellen nach Sichtbarkeit (Ziel gegen neben_nachher.jpg, angesehen)
1. Galerie + Vordach als Höhenfeld-Kasten: ebenen_bauplan.py:101 -> ebenen_masse.py:98-109 -> bauteile.py:1011/1023. Das ist das größte Bauteil in Bildmitte. Überschneidung mit den Agenten "Galerie-Treppen/Bestand-Tor" und "Vordach/Galerie-Pfosten".
2. Blendnischen der Nordfenster fehlen: nischen_fenster.py:333 (+ Sohlbank ohne ANNAHME-Bau). Kein Agent deckt das ab.
3. Traufe/Umgang: Dachkante zu hoch und massig, kein Umgang-Rücksprung, 2 statt 4 Pfosten (traufe_aus_fotos, umgang_aus_fotos.py:170/185). Agent "Kanten über Traufe" deckt teilweise ab; die Pfostenmehrheit deckt niemand ab.
4. Uhr: Nord nur Ring + Kerben statt lesbarem Zifferblatt, Süd ohne Zifferblatt. Agent "Uhr".
5. Gesims Süd/West, Verdachung, Balkenköpfe fehlen: keine Gesims-Stufe in gesamtkette.py, `fehlende_kanten_haufen` ohne Leser (kantenstufe.py:178), Balkenköpfe als Löcher. Kein Agent deckt das ab.
6. Dachknick (Aufschiebling) und Treppenturm-Haube: dachflaeche_aus_umriss.py:245, rund_aus_huelle rc 4. Agent "Kegeldach" deckt nur die Haube ab.
7. Torscheitel Süd +0,8 m, Tor Nord 0,5 m zu breit: oeffnungen_aus_kanten. Klein im Bild, kein Agent.
8. Maßstab/Höhenlage (Holm +1,4, Traufe +1): Agent "Maßstab".

## Belege der Prüfung
- schwab_v3: modelle/schwab_v3_gen.py (alle beleg()-Aufrufe gelesen), Referenz modelle/schwabentor-1120/referenz_hand.json.
- Kette: tools/gesamtkette.py:711-857 (Stufe bauplan), audit vorbauten_auto/ebenen_masse/nischen_fenster/fenster_auto_vor_loch/uhren_auto/umgang_auto/dach_profil.json.

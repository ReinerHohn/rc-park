# Fassaden-Pipeline (Stand 15.11.2026)

Was nach den Kameras (SfM, Tore) automatisch aus einer Fassade wird. Entstanden am Schwabentor (Turm + Nachbarhaus),
gegengeprueft am Historischen Kaufhaus. Verlauf, Zahlen und Sackgassen: `modelle/STAND_2026-11-14.md` ab "12:40 PIPELINE-AUTOMATISIERUNG".
Grundsatz (CLAUDE.md, KERNMETHODE): Form aus Fotokanten und Fotomassen; Netz/Wolke liefern Lage und Bruchstein-Relief; alles Generierte heisst ANNAHME.

## Stufen in `tools/gesamtkette.py`

Reihenfolge: ... sfm -> tore -> dach -> bauen -> kanten -> fototor -> **fassaden** -> **fenster** -> html -> vergleich.
Die beiden neuen Stufen sind einzeln geprueft (unten), ein voller Kettendurchlauf steht noch aus.

### Tore (ergaenzt)
- `kette_insel_pruefen.py` (rc 3): Bildketten ohne Fremdstuetze (Videoclip) -> vor der dichten Wolke ausschliessen (`wolke_neu_fusionieren.py` liest `audit/kette_insel.json`).
- `hoehen_tor: true` wird bei neuen Objekten mit LoD2 gesetzt -> `hoehe_gegen_dom1.py` laeuft in jeder Abnahme.

### Stufe `fassaden`
1. `netz_aus_dicht.py <objekt.json> <dicht>`: OpenMVS (InterfaceCOLMAP + ReconstructMesh, Standardeinstellung) -> `mesh_modell_ausschnitt.npz` im Modellrahmen.
   Nur auf der Datenplatte (das Werkzeug verweigert andere Ziele; ein Test schrieb 4,7 GB auf Root).
2. `fassaden_kette.py <objekt.json> --netz <npz>` je Wand (LoD2-Aussenkanten aus `dach.json` oder `--wand`):
   - Fotos automatisch: `fotos_fuer_wand` (Abdeckung x Pixel je Meter x Frontalitaet).
   - `relief_einsatz.py`: Hoehenbild 5 cm aus dem Netz, ab z 0, Maske `oeffnung`.
   - `relief_putz.py`: Putz eben ueber die FOTOFARBE (wenig Saettigung + hell, Mehrheit ueber die Fotos); Eckquader behalten das Relief, Grenze gezahnt wie im Foto.
   - `steine_generieren.py --max_loch_m2 1.5`: nur Loecher ausserhalb von Putz und Oeffnungen; Loecher >= 1,5 m2 (Tor, grosse Verdeckung) bleiben glatt;
     Niveau aus der echten Umgebung. Von Hand: `--zone`, `--ohne` (Tor), `--fremd` (Nachbardach/Schild an der Klemme).
   - Bericht `audit/fassaden_kette.json`; Generator: `from fassaden_kette import anbauen` (in der Vorlage `objekt_anlegen.py`).
3. Neu bauen (`bauen_abnehmen.sh`).

### Stufe `fenster`
1. `fassade_ortho.py` (grob, 5 cm): Fassadenbild je Ebene aus allen Fotos, Sichtbarkeit gegen das Modell. Seit 15.11.: 12 s statt 431 s (eine Python-Schleife), Fotos `<nr>.jpg` werden gefunden, Abtastung mit Glaettung auf Zellgroesse.
2. `fassade_parsing.py`: OWLv2 (Apache) mit Abstimmung ueber die Fotos -> Kaesten je Klasse (Fenster, Tuer, Bogen, Figur, Gaube, Balkon).
3. `fassade_ortho.py --zelle 0.01 --max-mpp 0.02 --einzeln` + `fassade_fein.py`: FEINES Bild (1 cm), siehe unten.
4. `fenster_aus_parsing.py <ortho> --fein <ortho_fein> --aus audit/fenster_auto.json`:
   - kein hellweisser Putz im Kasten; Helligkeit innerhalb 0,17 um den gewichteten Median der GEBAEUDESEITE (helles Spiegelglas ODER dunkle Butzenfenster);
   - Sammel- und Doppelkaesten weg; Scheiben zu Fenstern gruppieren -> Rechteck, Pfosten, Kaempfer;
   - Sprossen: Helligkeitsprofil je Scheibe am feinen Bild, nur regelmaessige Teilung, gleich grosse Scheiben teilen das haeufigste Muster.
5. Generator: `bauteile.fenster_aus_json` (Nische 12 cm, Pfosten 7 cm, Sprossen 3 cm = ANNAHMEN); Fenster, vor denen im Modell etwas steht, werden ausgelassen.

Gemessen: Nordgiebel Schwabentor-Nachbarhaus 6 von 6 sichtbaren Fenstern, kein Fehltreffer, 1-4 cm (Unterkante bis 8 cm) gegen foto_mass-Handmasse;
mit den automatischen Fenstern bestehen alle 5 Fensterpruefungen (`AUTO_FENSTER=1 bauen_abnehmen.sh schwab_nachbar`).
Kaufhaus Hauptfassade: 5 Masswerkfenster (2,0 x 2,5 m, Achsabstand 2,75-2,86 m), 2 Erker, 1 Kleinfenster.
Grenzen: nur Rechtecke (kein Spitz-/Vorhangbogen, kein Masswerk), Erker nur als Kasten, Schwellen aus zwei Fassaden.

## Das feine Fassadenbild (`fassade_fein.py`)

Ein Fassadenbild ist die Wand wie auf einem Bauplan: jeder Bildpunkt = ein festes Stueck Wand (fein: 1 cm x 1 cm), senkrecht gesehen.
- Entstehung: Raster auf der Modellwand -> je Zelle der Ort im Foto (Kamera aus dem Buendel) -> Farbe in die Zelle.
- Problem bei 1 cm: die Wandbilder verschiedener Fotos liegen 0,1-1 m versetzt (Modellebene != echte Tiefe, Kamerareste) -> zellweise Mischung gibt Naehte/Geister.
- Loesung: Bezugsfoto (siehe Verdecker); weitere Fotos per SIFT + RANSAC-Homographie im Ortho-Raum darauf ziehen
  (>= 40 Inlier, Eckversatz <= 2 m, sonst verworfen); Median wo >= 3 Fotos (Passanten, Draehte fallen heraus), sonst das beste.
- Verdecker (Baum, Mast, Schild, Passanten) OHNE Farbregel - eine Laub-Farbregel war zu speziell (gruene/gelbe Gebaeude) und wurde verworfen. Grundsatz: was VOR der Wand
  steht, wandert von Foto zu Foto; die Wand bleibt deckungsgleich. (a) Bezugsfoto = groesste Inlier-Summe der Paar-Homographien (eine Homographie passt nur auf die Wandebene,
  Baum-Merkmale werden keine Inlier); (b) nach dem Ausrichten gilt ein Foto dort als verdeckt, wo es grossflaechig vom Median abweicht; (c) `abdeckung_<id>_fein.png`:
  weiss = >= 3 Fotos einig, grau = nur 1-2 Fotos (ungeprueft), schwarz = nichts. Schwabentor Sued: Baum vor der Wandmitte verschwindet, zwei baumlastige Fotos zu 61 / 79 % als verdeckt erkannt.
- Ergebnis Kaufhaus f02 (242 m2, 2141 x 1309 px, 87 s Ortho): nahtfrei, Sechseck-Verglasung, Fensterform, Figuren lesbar; Restversatz 1-3 cm.
  Beispiele: `modelle/schwab_v3/audit/beispiele/kaufhaus_*_fein_1cm.jpg`.
- Feinheit = Fotoaufloesung: 1 cm nur mit Fotos <= ~1-2 cm je Pixel; sonst so fein wie die Fotos. Der Erkenner bleibt am groben Bild (960-px-Kacheln).
- Das Bild gibt MUSTER und KANTEN, keine Tiefe. Lage/Massstab = Bezugsfoto auf der Modellebene; Masse weiter ueber `foto_mass.py`.

## Lokale Feinrechnung der Tiefe (`tiefe_lokal.py`) - VERSUCH, laeuft

Zweck: Steinreliefs, Figuren, Masswerk feiner als das Netz (~3 cm Kanten, Relief 5 cm).
Idee: die dichte Wolke des ganzen Objekts rechnet mit 1000-1600 px Bildkante (Register: groesser bringt global nichts). Auf EINER Stelle sind wenige nahe Fotos
in voller Aufloesung bezahlbar.
1. Die k besten Fotos fuer das Feld (`fotos_fuer_wand`).
2. Teilnetz aus dem Gesamtbuendel nur mit diesen Bildern - Kameras und Rahmen bleiben, keine neue Ausrichtung.
3. COLMAP: entzerren (`--max_size`), PatchMatch geometrisch (GPU), Fusion.
4. Punkte in den Modellrahmen, auf Feld +- Band beschneiden, je 1-cm-Zelle Median des Abstands vor der Wandebene
   -> Hoehenbild im Format von `relief_einsatz.py` (direkt als Relief-Einsatz baubar) + Schattierungsbild.
Aufruf (als Job): `JOB_GPU_MB=6500 tools/job_start.sh NAME LOG /media/oem/scan/venv-colmap/bin/python -I tools/tiefe_lokal.py <objekt.json> <sparse> <bilder> --name N --a .. --b .. --aussen .. --feld u0 u1 z0 z1 [--k 12] [--max_size 3200] [--px 0.01] [--massstab ..]`
**Ergebnis (15.11.2026, Schwabentor Nordwand unten, u 0,1-12,05 m, z 0-10,5 m, Rohrahmen, 3200 px, 1 cm):**
- Lauf 1 (12 schaerfste Fotos): 633 s, 3842 Punkte je m2, 73 % Loecher. Ursache: die Fotos standen fast am selben Fleck, Schnittwinkel < 3 Grad, in den Tiefenkarten nur 15-30 % gueltig.
- Lauf 2 (Fotowahl FUER STEREO: 4-35 Grad Blickunterschied zu einem gewaehlten Foto, keine Doppel < 1,5 Grad; Filter gelockert: Triangulationswinkel 1,5 Grad,
  Fusion min 2 Pixel / 3 px / 3 % Tiefe): 672 s, 7201 Punkte je m2, 59 % Loecher im Feld; von der Flaeche, die das grobe Relief abdeckt, trifft die Feinrechnung 60 %.
  VRAM nur ~2,2 GB - 4000 px waeren moeglich. Rechenzeit ~11 min je Feld.
- Qualitaet: wo Daten sind, zeigt das 1-cm-Bild Steinflaechen, Bossen und Fugen einzeln; das 5-cm-Relief zeigt nur Kissen (Bild `modelle/schwab_v3/audit/tiefe_lokal_vergleich_5cm_1cm.jpg`).
- Einbau: `relief_mischen.py fein.npz grob_voll.npz aus.npz --px 0.02` (Putz bleibt eben; fein wo vorhanden; sonst grob/generiert auf das Niveau des feinen gebracht;
  Entstoeren: Ausreisser > 2,5 cm gegen den 5x5-Median, Uebergang fein/grob ueber 3 Zellen - ohne das schwarze Sprenkel im Modell). Raster 2 cm = 0,23 mm bei 1:87;
  1 cm waere unter der Druckaufloesung und vervierfacht das STL. Im Generator: grobes Relief mit `tief_felder=[Feld]` zurueck, gemischter Einsatz davor.
  Nordwand: 44 % fein, 25 % aus dem groben Relief (davon 11 % generiert), 5 % Putz, 27 % leer (Tor, Galeriezone). Abnahme gruen, Modell neben Foto angesehen.
- Offen: Abdeckung (mehr/naehere Fotos, 4000 px, Tiefenkarten direkt statt Fusion), Figuren (z. B. ueber dem Nordtor) gezielt als eigenes kleines Feld mit 5 mm, Aufnahme in die Kette als Stufe.
Abnahme des Versuchs: (a) Schattierungsbild neben dem feinen Fassadenbild - sind Fugen/Figur schaerfer als im 5-cm-Relief? (b) Punkte je Zelle, Lochanteil;
(c) Modell neben Foto nach dem Einbau; (d) Laufzeit und VRAM. Scheitert er, kommt er mit Ursache nach `modelle/NICHTS_GEBRACHT.md`.

## Pflichtkontrolle
- `tools/modell_neben_foto.py` (objekt.json `neben_fotos`, automatisch in `bauen_abnehmen.sh`): Modell aus der Fotokamera neben dem Foto, je Seite mindestens eines.
- Je Wand `relief/<wand>_voll.jpg` (grau = echt, blau = generiert, gruen = Putz), `fenster_<id>.jpg`, `ortho_<id>_fein.png` ansehen.

## Offen
- Kettendurchlauf mit den neuen Stufen an einem Objekt.
- Sechseck-/Butzenraster und Fensterformen (Bogen, Masswerk) als Geometrie; Fachwerkbalken; Gesimse; Erker.
- Gruppen-Punkt-Tor (braucht Handpicks) nicht in der Kette.
- Schwellen der Fensterregeln an weiteren Fassaden pruefen (Putzfassade mit Steingewaenden, Gegenlicht).

## Nachtrag 16.11.2026: Fenster als echte Loecher, ebene Eckquader
- `bauteile.aushoehlen(koerper, d=Wandstaerke, schnitte=[...], z_min=...)` am ENDE des Generators (nach allen Fenstern): Gebaeude hohl, alle mit `Wand.fenster` gebauten Fenster (Liste `bauteile.DURCH`) und die uebergebenen Schnittkoerper werden durchgebrochen. Wandstaerke ist ANNAHME. Tuerme: `z_min` ueber dem Torgewoelbe. Laufzeit 20-40 s.
- Pruefungen, die eine Nischenrueckwand erwarten (`tiefe_bei`, `schnitt_reichweite` mit grossem r_max), sehen danach die Innenwand - Pruefdefinition anpassen (historie), Sollwerte der Oeffnungsmasse bleiben.
- `tools/relief_quader_eben.py <voll.npz> <eben.npz> --feld u0 u1 z0 z1`: nur fuer GLATT behauene Quader (am feinen Fassadenbild pruefen), nie fuer Bruchstein.
- 3D-Seite: ebene Flaechennormalen; Bilder aus der Seite vor einer Generatoraenderung am STL nachrendern (`tools/modell_ansicht.py`).

## Nachtrag 16.11.2026 (2): Quader mit Fugen aus dem Foto, duennste Wand, Anzeige
### Quader aus dem feinen Fassadenbild (`tools/steine_aus_foto.py`)
Wann: Steinflaechen, an denen das Scan-Relief nur Brei ist (hoch am Turm, flacher Blick), das 1-cm-Fassadenbild die Fugen aber scharf zeigt.
Voraussetzung: `fassade_fein.py` ist fuer die Wand gelaufen (ortho_fNN_fein.png + fassaden.json), Relief hat die Putzmaske (`relief_putz.py`).
Aufruf (Schwabentor, so gelaufen):
- Sued:  `steine_aus_foto.py relief/sued_eben.npz relief/sued_foto.npz <fein>/fassaden.json 1 <fein>/ortho_f01_fein.png --feld 0.1 11.4 9.9 26.0 --schwelle 2.4`
- West:  `... west_eben.npz west_foto.npz ... 3 ortho_f03_fein.png --feld 0.1 8.3 9.4 26.0 --schwelle 2.4`
- Nord (Relief im Rohrahmen): `... nord_eben.npz nord_foto.npz ... 0 ortho_f00_fein.png --feld 0.1 12.0 14.8 27.8 --schwelle 2.4 --massstab 0.933 -2.15 15.28 0`
  (`<fein>` = /media/oem/scan/rc-park_daten/schwab_v3/fassade_fein; die Nummer ist der Index der Fassade in fassaden.json)
Verfahren: je zusammenhaengendem Steinfeld Lagerfugen = Spitzen im Zeilenprofil der Abweichung vom oertlichen Median, Stossfugen = Spitzen im Spaltenprofil je Schicht;
Polaritaet (helle Moertelfuge / dunkle Schattenfuge) wird nicht vorgegeben - beide gerechnet, die deutlichere gewinnt. Keine Farbregel.
Im Generator: `relief_koerper(<x>_foto.npz, tiefe wie grob, trend=True, rand_auslauf=False, null_felder=<Bauteilfelder>)`, das grobe Relief bekommt das Feld als `tief_felder`.
Kontrolle: `<x>_foto.jpg` (links Foto, rechts Relief) ANSEHEN.
Was NICHT ging (gleicher Tag): (1) Schwelle auf Helligkeitsabweichung + "lange duenne Linien" - fand oben fast nichts (15 Steine);
(2) Hesse-Grat-Filter mit Hysterese - Felsstruktur der Bossen ueberstimmt die Fugen; (3) Schichtmodell mit --schwelle 0.8 - erfindet ein Ziegelraster (Steine 19 x 19 cm statt ~40 x 25).
Erst Schichtmodell mit --schwelle 2.4, Mindestabstand 16 cm (Lager) / 20 cm (Stoss) passte zum Bild. Der Wert ist an EINEM Bauwerk eingestellt.
Grenzen: Schichtmodell = durchlaufende waagerechte Lagerfugen je Steinfeld; unregelmaessiger Bruchstein geht damit nicht (dort Scan-Relief/`tiefe_lokal.py`).
Nicht jede Fuge stimmt; Fugentiefe 3 cm und ebene Steinflaeche sind ANNAHME, Bossen fehlen. Feld von Hand gewaehlt (unterhalb stoert z. B. das Vordach).
### Wandstaerke beim Aushoehlen
Nutzer 16.11.: "minimal duenn, einigermassen stabil, schnell druckbar" -> d = WAND_MM x SCALE / 1000, Standard WAND_MM = 1,2 (drei Bahnen einer 0,4-mm-Duese) = 0,10 m bei 1:87.
Umgebungsvariable `WAND_MM` aendert sie ohne Codeaenderung; `OHNE_HOHL=1` baut voll. Bei duenner Wand: `kneifkanten_schliessen` zusaetzlich NACH dem Skalieren (mm, `stellen=3`).
### Anzeige (3D-Seite)
"Strahlen" auf ebenen Waenden kamen vom Ecken-Clustering: der Rasterpunkt liegt bis 2 cm neben der Wandebene, lange Dreiecke kippen. Jetzt Schwerpunkt der Gruppe
(`modell_3d_html.py`). Ebene Flaechennormalen allein (erster Versuch) haben das NICHT behoben. Seitenlimit 16 MB: mit Hohlraeumen `--netz_raster 0.042 --n 40000`.
### Noch nicht automatisch
`steine_aus_foto.py` und `relief_quader_eben.py` sind KEINE Stufe von `tools/fassaden_kette.py`/`gesamtkette.py` - Felder und Schwelle werden von Hand gesetzt.

## Bauteil-Katalog (generisch, `tools/bauteile.py`) - Nutzer 16.11.2026: "lerne daraus und baue generische Tools"
Regel: kein Bauteil als Einzelfall in den Objekt-Generator. Erst hier pruefen/ergaenzen, dann aufrufen. Zu messen ist jeweils nur das Genannte, der Rest sind Standardwerte (= ANNAHME im beleg).
- `Wand(a, b, aussen)`: Wandkoordinaten u/z/w; `kasten`, `huelle`, `prisma`, `scheibe`, `stab`, `linienzug` (geschwungene Leisten).
- `spitzbogen(halb, kaempfer, scheitel)`: bei Stich >= halbe Breite zwei Kreisboegen, sonst Vier-Zentren-Bogen (gedrueckt). `rundbogen(breite, unten, scheitel)`.
- `Wand.fenster(u0, u1, z0, z1, w, teiler, kaempfer, sprossen)`: Nische + Rahmen; meldet sich in `DURCH` fuer `aushoehlen`. `fenster_aus_json` fuer erkannte Fenster.
- `aushoehlen(koerper, d, schnitte, z_min)`: Gebaeude hohl, Fenster als Loecher; `kneifkanten_schliessen`.
- `Wand.zifferblatt(u, z, d_aussen, d_innen, zeit)`: Turmuhr.
- `Wand.galerie(u0, u1, z_boden, z_holm, z_dach, w, pfosten, streben, z_fuss, tafeln, knaggen)`: auskragende Holzgalerie / Holzerker.
- `Wand.masswerk_fischblase(u0, u1, z0, z1, w0, w1)`: durchbrochenes Bruestungsfeld.
- Dach als Laser-Hoehenfeld: `tools/laserdach.py`. Reliefs: `relief_einsatz.py`, `relief_putz.py`, `relief_quader_eben.py`, `steine_generieren.py`, `steine_aus_foto.py`.
Noch NICHT generisch (Einzelfall im Schwabentor-Generator, bei Bedarf herausziehen): Zeltdach mit Knickprofil (D_PROF), Laterne mit Zwiebelhaube, Treppenturm mit Haube (Rotationsprofil), Holzfries, Kamin/Firststange, Erker mit Konsolen.

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
- `saeule(W, u, w, z0, z1, d, basis, kapitell)`: runde Saeule mit Plinthe (quadrat/rund) + Wulst, Kapitell als Aufweitung; `laube(..., frei=[(u0,u1,z1[,w_hinten])])` raeumt dafuer die Pfeilerzone (17.11.2026, kaufhaus_gk).
- `balkon(W, u0, u1, z_boden, w_vorne, z_handlauf, docken, pfosten, konsolen, ...)`: Bodenplatte, Konsolen, Pfosten, Docken (Balustre, vorn je u + seitlich), Handlauf.
- `vorhangbogen(breite, unten, schulter, spitze, mitte, feld, exponent)` (Querschnitt) und `vorhangbogen_fenster(W, u0, u1, z0, z1, ...)` -> (zus, ab, pf), nach `aushoehlen`: `koerper = (koerper + zus - ab) + pf`; Felder, Pfosten an den Spitzen, Kaempfer.
- Putz ohne Quaderwerk: `fassaden_kette.putz_eben` (in `relief_roh`, 17.11.2026): Zellen < 5 cm am 1-m-Wandniveau = glatter Putz, Rest (Gewaende, Gesimse, Figuren) bleibt. Grund: Netzrauschen 6,6 cm machte glatte Putzfassaden zu "Brei".
- Fotoquellen: `tools/fotoquellen.py` findet alle Fotoordner des Objekts unter rc-park_daten/<basis>* (Gesamtkette Stufe `vorpruefen`, Notiz `weitere_fotos`; aus mit `--ohne-weitere-fotos`).
- Dach als Laser-Hoehenfeld: `tools/laserdach.py`. Reliefs: `relief_einsatz.py`, `relief_putz.py`, `relief_quader_eben.py`, `steine_generieren.py`, `steine_aus_foto.py`.
Noch NICHT generisch (Einzelfall im Schwabentor-Generator, bei Bedarf herausziehen): Zeltdach mit Knickprofil (D_PROF), Laterne mit Zwiebelhaube, Treppenturm mit Haube (Rotationsprofil), Holzfries, Kamin/Firststange, Erker mit Konsolen.

## Ungesehene Seite (kein SfM-Foto) - Nutzer 16.11.2026: "Nein, nicht spiegeln. Du musst Fotos suchen von dieser ungesehenen Seite."
Erkennen: `fassade_fein`/`fassade_ortho` liefert fuer die Wand ein (fast) leeres Bild (`abdeckung_fNN.png` ~0 %). Das heisst NUR: kein REGISTRIERTES Foto sieht sie.
Ablauf (Schwabentor Ostseite, so gelaufen):
1. GANZEN Fotobestand durchsehen, auch nicht registrierte Bilder (commons/online/Videobilder): Kontaktbogen bauen und ansehen. Erhoehte Standorte (Hang, Turm, Luftbild) zeigen Seiten ueber Nachbardaechern. Erst wenn dort nichts ist: Nutzer um ein Foto bitten / im Netz suchen.
2. Kamera des Fundes aus >= 8 verteilten, schon gemessenen Modellpunkten loesen (solvePnP + Brennweite frei) -> `messprotokoll/K-<FOTO>.json` mit Punkten und Restfehler. Gegenprobe: bekannte Hoehen (Gesims, Traufe) auf der neuen Wand nachmessen.
3. Masse mit `foto_mass.py --kamera K-<FOTO> --ebene <Wandebene>`; Wandgerade aus dem Modellschnitt.
4. Bild der Wand: `fassade_ein_foto.py <fassaden.json> <nr> <objekt.json> <FOTO> ortho_fNN_fein.png`; Traeger `relief_einsatz.py - <wand>.npz ...` (leeres Relief), dann `relief_putz.py` (Schwellen --s/--v an Schattenlage anpassen) und `steine_aus_foto.py`.
VERWORFEN: Eckstreifen der Nachbarwaende an die ungesehene Wand spiegeln (Werkzeug relief_ungesehen.py geloescht) - Erfindung, solange Fotos existieren.
Grenzen: Kamera aus Modellpunkten ist nur so gut wie das Modell (hier +-0,2 m); Einzelfoto = keine Verdeckungspruefung; Schattenseite -> Fugen unsicher.
OFFEN (Automatik): die Kette sucht noch nicht selbst nach unregistrierten Fotos fuer leere Waende.

## Stufe `seiten` der Gesamtkette: Wand ohne Foto -> Fotos holen (16.11.2026)
Nutzer: "Er muss doch wissen, dass dort Bilder fehlen und die sich dann holen, notfalls downloaden ... alle Quellen ... Alles muss in die Pipeline rein und dokumentiert werden."
Warum es am Schwabentor nicht automatisch ging: (1) `kamera_abdeckung.py` meldete die Luecke (Ost) seit 14.11., aber keine Stufe handelte danach;
(2) das einzige gute Ostfoto (online2_orig od_15) war nie im SfM registriert; nicht registrierte Fotos wurden nie wieder angefasst;
(3) `fassade_ortho`/`fassade_fein` lieferten fuer die Wand ein leeres Bild, ohne Alarm.
Stufe (nach `fenster`, braucht dessen `fassade/fassaden.json`): `tools/seiten_luecken.py <objekt.json> <fassade> --sparse <Netz> --ref-db <db.db> --download --holen`
1. Abdeckung je Wand (Anteil Wandzellen mit Bilddaten); < 20 % = UNGESEHEN (rc 3). Schwabentor: N 88 %, S 82 %, W 75 %, O 0 %.
2. Kandidaten = Fotobestand minus registrierte Bilder (Schwabentor: 13 von 578); Kontaktbogen `audit/seiten_luecken_kandidaten.jpg`.
3. `--download`: alle FREIEN Quellen nach `<daten>/seiten_nachholen/`: `commons_harvest.py` (Geosuche 250 m + Name), `online_ansichten_holen.py` (Hochblicke: Luftbild/Panorama),
   `openverse_holen.py` (Flickr u. a.; nur CC0/PDM/BY/BY-SA; `herkunft.json` mit Urheber/Lizenz). NICHT: Mapillary, Google-Bilder/Street View (Lizenz, `LIZENZ_WERKZEUGE.md`).
   Etikette: Wikimedia 1 Datei je 25 s; HTTP 429 sperrt nur die Quelle fuer den Lauf (erster Lauf 16.11.: nach 3 Bildern gedrosselt, weil 1,5 s).
4. `--holen`: Skript `audit/seiten_luecken_holen.sh` = Nachregistrieren mit ALIKED+LightGlue (`zusatzfotos_registrieren.py` vorbereiten/merkmale/registrieren, `zusatzfotos_lightglue.py` refnamen/paare/einlesen).
   GPU: nicht parallel zu einer Abnahme starten (16.11.: CUDA out of memory, 7,6-GB-Karte).
5. Danach `fassade_ortho`/`fassade_fein` fuer die Wand neu. Bleibt sie leer, obwohl ein Foto sie zeigt: Kamera aus gemessenen Modellpunkten + `fassade_ein_foto.py` (Abschnitt "Ungesehene Seite").
NICHT GEGANGEN: Aufloesungsgrenze (`--max-mpp`) fuer die leere Wand lockern - 24 "passende" registrierte Kameras (Videobilder in 40 m Hoehe) ergaben ein Mischbild fremder Daecher (Posen falsch). Nicht einbauen ohne Uebereinstimmungs-Tor.
STAND: Erkennung, Kandidatenliste, Openverse-Abruf einzeln gelaufen; der Gesamtablauf (Download + Nachregistrierung + neue Orthos) ist noch NICHT einmal komplett durchgelaufen; Stufe in gesamtkette.py nur syntaxgeprueft.

## Vorbauten automatisch: Ebenen-Sweep je Fassade (`tools/fassade_tiefe.py`, 16.11.2026) - ERSTE FASSUNG, nur Vorschlaege
Nutzer: Balkon vor der Wand braucht eine eigene Messebene - "mache den naechsten Automatisierungsschritt".
Prinzip: jede Wandzelle in Schritten von 5 cm vor/hinter die Wandebene schieben, in alle Fotos projizieren; wo die Fotos uebereinstimmen, liegt die echte Tiefe.
Haeufigste Tiefe = die Wand selbst (meldet den Versatz der LoD2-Ebene), Abweichungen >= 0,25 m in drei Tiefenklassen = Kandidaten mit `ebene` fuer `foto_mass.py`.
Aufruf: `fassade_tiefe.py <objekt.json> <fassaden-ordner> <nr>` -> `tiefe_fNN.jpg` (ANSEHEN), `vorbauten_fNN.json`. Laufzeit 4 s je Fassade (GPU). In der Kette: Stufe `seiten` (vor seiten_luecken).
Ergebnis Schwabentor:
- Nord (12 Fotos, Standorte bis 36 m auseinander): belastbar. Die zwei groessten Kandidaten sind die echten Vorbauten: Galerie (u -3,98..4,30, z 9,4-13,2, w +1,15; gemessen Breite 8,06 m, Ausladung ~1,45 m)
  und Vordach (z 14,7-19,2, w +1,00; schraeg, gemessen 1,54 m an der Traufe). Tiefe ~0,3 m zu klein (Mischung mit Streben/Schraege). Wandversatz -0,25 m. Fensternischen und offenes Wandbild hinter der Galerie sind im Tiefenbild zu sehen.
  Daneben 20+ kleine Fehlkandidaten (Fahrdraehte, Nachbarhaus am Bildrand, Tordurchfahrt).
- Sued (8 Fotos, Baum davor): Wandversatz -0,75 m = der bekannte LoD2-Fehler der Suedwand, aber am Rand des Suchbereichs -> Tor lehnt ab; mit `--w -1.8 1.8` kommen Fehlkandidaten (Uhr +1,55). NICHT brauchbar.
- West (9 Fotos fast aus einem Punkt, steil): Tiefenbild Streifenmuster, Tor lehnt ab (26 % auf Wandtiefe).
Tor: >= 35 % der sicheren Zellen auf der Wandtiefe, sichere Tiefe auf >= 30 % der Wand, Wandtiefe nicht am Rand des Suchbereichs; sonst rc 4, keine Kandidaten. Schwellen an EINEM Bauwerk gesetzt.
OFFEN: Verdeckung (Baum, Nachbarhaus), Fotowahl nach Standortabstand, Kandidaten automatisch vermessen und mit `bauteile` bauen. Bis dahin: Kandidatenliste = Hinweis, wo eine zweite Ebene noetig ist.

## Nachregistrieren fremder Fotos - Stand 16.11.2026
Lauf mit 46 Fotos (13 unregistrierte + 33 Openverse): `paare` fand 472 verifizierte Paare; `einlesen` kennt kein `--ref-db` (im Skript behoben); `registrieren` brach ab:
"existing_camera.width == camera.width (2000 vs. 1280)" - `zusatzfotos_registrieren.py` setzt EINE Kamera fuer alle Zusatzfotos (gebaut fuer Handyserien), Webfotos haben gemischte Formate.
OFFEN: Kamera je Bildformat (`--kameras`) automatisch erzeugen; bis dahin registriert die Stufe `seiten` gemischte Webfotos NICHT.

Nachtrag 16.11. ~10:30: Fotoquader am Schwabentor jetzt mit `--px 0.03` (statt 0,02) gerechnet - der Turmbau brauchte mit 2 cm 11-12 von 15 GB RAM und wurde zweimal vom System gestoppt. Aufrufe wie oben plus `--px 0.03`; Felder inzwischen: Sued 9,9-33,8 (`--ohne 0 11.6 25.8 27.0`), West 9,4-34,6, Nord 10,4-37,2 roh (`--ohne 1.6 11.1 9.7 21.1`), Ost 26,95-34,6 aus ost_putz.npz (`--putz_s 0.45 --putz_v 0.28 --ohne 4.6 6.4 27.0 34.6`).
Nachregistrieren: `zusatzfotos_registrieren.py registrieren --je-bild` = jedes Webfoto eigene Kamera, Brennweite je Bild aus PnP (behebt den Abbruch bei gemischten Formaten).

## Stufe `seiten`: ERSTER DURCHLAUF bis zur Messkamera (16.11.2026 ~10:45, Schwabentor)
Download (Openverse, nur Flickr - Wikimedia war gedrosselt): 33 Bilder. Nachregistrierung von 46 Kandidaten (13 Altbestand + 33 neu) mit `--je-bild`:
20 registriert (Reprojektion Median 1,2 px), darunter 13 Openverse-Fotos, 2 historische Commons-Aufnahmen und das Ostfoto od_15.
`kameras_nachtragen.py`: Abbildung SfM -> Modell aus 529 gemeinsamen Kameras, Restfehler Median 1 cm; 17 neue K-Dateien.
TREFFER: Flickr-Foto ov_0005 (CC BY 2.0, Jorge Franganillo; herkunft.json) zeigt die OSTSEITE in der Sonne, mit Fugen - automatisch geladen und registriert.
GRENZEN (gemessen): (a) dessen Pose stimmt auf der Suedseite auf 5-10 px, auf der Ostseite liegt der Schlitz ~30 px (~0,9 m) daneben - Brennweite/Abstand sind bei wenigen
Punkten auf nur einer Wand schlecht bestimmt; vor dem Messen Kamera mit gemessenen Modellpunkten nachziehen (wie bei od_15). (b) od_15: SfM-Pose (30 Inlier) liegt 74 m neben der
Kamera aus 11 Modellpunkten - die Gegenprobe im Werkzeug meldet das, die vorhandene Kamera bleibt. (c) 26 von 46 nicht registriert (meist Bilder ohne den Turm).
OFFEN: neue Kameras automatisch gegen Modellpunkte verfeinern; danach fassade_ortho/fassade_fein fuer die Ostwand mit ov_0005 + od_15 neu; Commons-Teil nachholen.

## Kamera am Modell nachziehen (`tools/kamera_verfeinern.py`, 16.11.2026) - schliesst die Luecke der Stufe `seiten`
Ablauf: ALIKED+LightGlue zwischen dem neuen Foto und Referenzfotos mit guter Kamera -> Treffer der Referenz ueber das TIEFENBILD DES MODELLS (STL, GPU-Raster) in 3D heben ->
PnP mit RANSAC ueber Brennweiten + Feinausgleich. Tor: >= 2 Flaechenrichtungen mit je >= 15 Inliern, sonst rc 3 (nicht schreiben).
Schwabentor, Flickr-Foto ov_0005 gegen od_15 + 4 Suedfotos: 1404 Inlier von 1906 (Sued 1254, Ost 59, Dach 57, West/Nachbar 31), Rest 1,6 px = 5 cm;
Brennweite 1251 -> 3003 px, Standort um 54 m verschoben (jetzt neben dem Standort von od_15 am Schlossberghang). Probe: Schlitzfenster Ost projiziert auf 8 px (vorher 30).
FEHLVERSUCH davor: Treffer mit den LoD2-Fassadenebenen schneiden - die liegen bis 0,75 m neben der echten Wand, alle Ostpunkte fielen heraus (nur 1 Wand, Tor lehnte ab).
Danach Ostwand: `fassade_ein_foto.py ... dl_openverse__ov_0005 ortho_f02_ov5.png` (2,9 cm/px, Sonne) -> `relief_putz.py` (Standardschwellen) -> `steine_aus_foto.py --feld 0 10.75 22.5 34.6
--ohne 4.6 6.4 22.5 34.6 --ohne 0 10.75 25.9 26.95 --ohne 2.6 10.75 22.5 25.95 --px 0.03` (Nachbardach und Schlitzspalte ausgenommen): 131 Steine statt 77 aus dem Schattenfoto.
In `seiten_luecken_holen.sh` laeuft das Nachziehen jetzt fuer jede neue Kamera automatisch (Referenzen = aehnlichste Standorte). Lizenz/Urheber des Fotos: herkunft.json (CC BY 2.0, Jorge Franganillo) - bei Weitergabe nennen.
OFFEN: Einzelfoto ohne Verdeckungspruefung (Nachbardach von Hand per --ohne ausgenommen); Referenzwahl nach Standort ist ungetestet (hier Liste von Hand).

## Fotoauftrag an den Nutzer (`tools/foto_auftrag.py`, 16.11.2026)
Nutzer: "wenn du mehr Daten willst, brauchst du ein Verfahren, wie du mir zeigen willst, welche Daten du brauchst."
`foto_auftrag.py <objekt.json> <fassaden-ordner> <aus.html> [--wunsch modelle/<objekt>/fotowuensche.json] [--min_m2 30] [--extra-umriss x0 y0 x1 y1 ...]`
- Bedarf automatisch: Wandbereiche ohne Daten im Fassadenbild (gelten als ungesehen; ein erhoehtes vorhandenes Foto dient nur als Vorbild fuer den Standort).
- Bedarf als Wunsch: `fotowuensche.json` je Objekt (Wand, u-/z-Bereich in Fassadenkoordinaten, Soll-Aufloesung, Titel, Begruendung) - dort eintragen, was zu grob ist.
- Je Auftrag: bestes vorhandenes Foto mit rot markiertem Ziel, Ist-/Soll-Aufloesung, Rat (Zoomfaktor am selben Standort oder naeher heran), Standort als Koordinate mit Kartenlink; Lageplan mit allen Standorten.
- Ausgabe: eine HTML-Seite (Bilder eingebettet) + JSON; veroeffentlichen als Artifact. In der Kette: Stufe `seiten`, nach seiten_luecken.
Schwabentor 16.11.: 7 Auftraege (Ost ganz, West oben, Figur Nordtor, Galerie/Vordach, Georgsbild, West-Eckquader, Umgang) - https://claude.ai/artifact/VG6sjn3AXswJ5RaFJsX8Km
Grenzen: "Fotos mit Blick darauf" ist bei Wuenschen rein rechnerisch (ohne Verdeckung, falsch registrierte Kameras zaehlen mit); keine Strassenkenntnis; Dachflaechen sind keine Waende und fehlen.

Nachtrag 16.11. (Nutzer: "Ich brauche ein besseres Tool. Stadtplan mit Richtung oder echte Bilder, aus der Richtung fotografieren"): foto_auftrag.py bettet jetzt den ECHTEN Stadtplan ein
(OpenStreetMap-Kacheln Zoom 18, einmal je Lauf geladen, Quellenangabe auf der Seite), zeichnet je Auftrag Standort + roten Blickpfeil, dazu je Karte einen Planausschnitt, die Peilung in Worten
("Blick nach Nordwesten (297 Grad), 87 m"), Links zu Google Maps/OpenStreetMap, das ganze Foto vom Standort mit rotem Ziel und den vergroesserten Zielbereich. Seitennamen statt Wandnummern.
Kameras > 130 m Abstand werden als Vorlage uebergangen (meist falsch registrierte Nahaufnahmen). Geprueft mit einem Bildschirmfoto der Seite in Handybreite (firefox --headless --screenshot).

## Sofort-Urteil fuer Fotos vor Ort (`tools/foto_schnellcheck.py`, Aufruf `tools/foto_check.sh <objekt> <datei>`) - 16.11.2026
Nutzer: "ich mache ein Foto, lade es dir hoch und du musst sagen, ja, passt oder passt nicht - ich bin dann in der Stadt und kann nicht hin und her fahren."
ABLAUF IN DER SITZUNG: Nutzer schickt ein Bild (liegt unter ~/.claude/uploads/<sitzung>/...) -> `tools/foto_check.sh schwab_v3 <datei>` -> Text-Urteil + Bild mit Zielrahmen per SendUserFile zurueck. Antwort kurz: PASST / PASST NICHT + ein Satz, was zu aendern ist.
Technik: Kamera ohne Vorwissen aus ALIKED+LightGlue gegen ~10 Referenzfotos + Tiefenbild des Modells + PnP (45 s, GPU). Je Auftrag aus `audit/fotoauftrag.json`:
Anteil des Ziels im Bild (>= 80 %), Aufloesung gegen Soll (<= 1,3x), Blickwinkel (<= 65 Grad), wiedererkannte Punkte im Ziel (>= 8, sonst wohl verdeckt), Schaerfe, Seitenabstand zum letzten angenommenen Foto (>= 1 m).
Angenommene Fotos: `audit/fotoauftrag_eingang.json`, K-Datei `K-neu__<name>.json`, Bild in fotos_dir als `neu__<name>.jpg`.
Test mit zwei Bestandsfotos als "Hochladung": Nordfoto 113205 -> Standort auf 0,6 m wie die SfM-Kamera, 4851 Punkte, Urteil "Auftrag 4 nur 34 % im Bild; Auftrag 7 1,5-fach zoomen";
Nachtfoto od_12 vom Schlossberg -> Standort neben od_15, Zielrahmen sitzt genau auf Ostwand und Georgsbild, Urteil "zu grob: 6 cm/px".
Grenzen: Schwellen sind Richtwerte ohne Feldtest; "nicht zuordenbar", wenn < 40 Stellen wiedererkannt werden; Verdeckung nur indirekt ueber die Punktzahl im Ziel;
die Soll-Aufloesung 1 cm/px der automatischen Luecken ist vom Schlossberg mit dem Handy nicht erreichbar (dort gilt: so gut wie moeglich, Tele).

## Lehren 16.11.2026 nachmittags (fuer das naechste Gebaeude) und was davon schon generisch ist
GENERISCH EINGEBAUT:
- `fassade_ein_foto.py ... auto --stl <eigenes.stl>,<nachbarn.stl>`: waehlt je Wand(-zone) selbst das beste vertrauenswuerdige Foto (sichtbare Flaeche / Meter je Pixel, Sichtbarkeit ueber das Tiefenbild des Modells)
  und blendet Verdecktes aus (mit 0,3 m Sicherheitsrand). Ersetzt die Handwahl des Fotos und die --ohne-Felder fuer Nachbardaecher. Ost Schwabentor: waehlt von selbst das 3840-px-Original (86 % sichtbar, 1,0 cm/px) vor od_15 (2,2) und der 1024-px-Kopie (3,7).
- `steine_aus_foto.py --nah 0` (Waende ohne Wandbild: Steinbaender abseits der groben Maske bleiben), `--duenn 0.12` (duenne Scheinsteine an Kanten weg).
- Kameras: `kameras_nachtragen.py` ueberschreibt nie eine vorhandene Kamera; `kamera_verfeinern.py` nimmt als Referenz nur Buendelkameras eigener/Commons-Fotos oder Kameras mit `vertrauen` (keine Videobilder, keine ungeprueften Downloads).
LEHREN:
1. Erst die vorhandenen und frei ladbaren Bilder ausreizen, dann den Nutzer um Fotos bitten: 100 geladene Bilder enthielten die Ostseite in 0,8 cm/px und die Westseite oben in 0,6 cm/px.
2. Dasselbe Motiv liegt mehrfach vor (Flickr-Kopie 1024 px, Commons-Original 3840 px). Immer nach der schaerfsten Fassung suchen; `auto` nimmt sie von selbst.
3. Eine Kamera, die nur an EINER Wand haengt, hat zwei Loesungen (nah/weitwinklig oder fern/Tele). Pruefen: steht der Standort an einem moeglichen Ort (Strasse, Hang, bekannte Aussicht)?
   Beispiel: "27 m vor dem Turm in 25 m Hoehe" war falsch, richtig war der Schlossberghang in 95 m. Noch KEIN automatisches Tor dafuer.
4. Automatik darf Geprueftes nicht ueberschreiben und sich nicht an eigenen Kopien bestaetigen (Gesamtlauf zerstoerte die gute Kamera von ov_0005; behoben, siehe oben).
5. Aus einem unscharfen/Schattenfoto keine Bauteile lesen: das "Bogenfenster Ost" aus od_15 gab es nicht (im scharfen Foto liegt dort das Nachbardach). Bauteile erst bauen, wenn ein zweites Foto oder ein scharfes sie zeigt.
6. Wikimedia drosselt Originale auch bei 25 s Abstand, wenn viele hintereinander kommen: Vorschaugroessen laden (noch nicht umgestellt).
7. Jede neue Kettenstufe einmal ganz laufen lassen, bevor man sie "fertig" nennt: der Gesamtlauf fand drei Fehler (pyproj fehlte, falsches Argument, Ueberschreiben).
NOCH NICHT GENERISCH (Handarbeit am Schwabentor): Aufruf von `fassade_ein_foto auto` + `steine_aus_foto` je Wand steht nicht in `fassaden_kette.py`; Felder (z-Bereiche, Fensterspalten) von Hand;
Tor fuer "unmoeglicher Standort"; Zusatz-Einsaetze je Wand im Generator (west_foto_oben) sind Einzelzeilen.

## Runde Bauteile und Wandebene - 16.11.2026 mittags (Nutzer: Treppenturm "kleine Fensterchen", "wichtig fuer Schloesser"; "Warum nicht automatisch?")
WARUM ES NICHT AUTOMATISCH KAM: foto_mass.py und die Fenstererkennung kennen nur Ebenen; Rundtuerme fielen durch alle Werkzeuge, ihre Schlitze standen als ANNAHME im Modell;
die Hinweise von fehlteile_finden/foto_diff (>30 offene Auto-Beobachtungen) wurden nicht abgearbeitet.
NEU, generisch:
- `tools/zylinder_mass.py <objekt.json> --achse x y --radius r --mess FOTO u v ... [--tri FOTO u v FOTO u v]`: Sehstrahl x Zylinder -> Punkt + Azimut; zwei Fotos als Gegenprobe; Triangulation fuer Spitzen.
- `tools/fassade_zylinder.py <objekt.json> <aus.png> --achse x y --radius r --z z0 z1 [--fotos auto] --stl ...`: ABWICKLUNG der Mantelflaeche (1 cm/px), Fotos selbst gewaehlt (steilster Blick je Zelle,
  max. 3 je 45-Grad-Sektor), Verdecktes ausgeblendet. Treppenturm Schwabentor: 74 % gesehen aus 14 Fotos; die drei einzeln gemessenen Schlitze liegen in der Abwicklung auf wenige cm gleich;
  zwei weitere Schlitze (z 5,8 und 4,5) und eine Tuer mit Gewaende am Fuss wurden erst dort gefunden. GRENZEN: am streifenden Rand zeigt ein Streifen faelschlich die Turmwand dahinter
  (Verdeckungstoleranz); Fenster werden nur sichtbar, nicht erkannt; Hauben/Kegel fehlen. NAECHSTER SCHRITT: fassade_parsing/fenster_aus_parsing auf die Abwicklung, Ergebnis als Zylinder-Schnitte in den Generator.
- `steine_aus_foto.py --foto <FOTO> --objekt <objekt.json> --stl ...` (statt Ortho; Aufruf `relief aus - 0 - --foto ...`): liest das Bild DIREKT aus dem Foto auf der Wandebene des Reliefs.
  GRUND: ein Ortho auf der LoD2-Fassadenebene liegt bis 0,75 m neben der echten Wand; bei schraegem Einzelfoto verschiebt das den Inhalt seitlich um 0,2-1 m
  (West: Nordwestecke 1 m zu frueh, dahinter "Steine" aus Himmel; Ost: Schlitz/Luke/Balkenkopf 0,2-0,4 m daneben). Fuer Einzelfotos IMMER diesen Weg nehmen.
  `fassade_ein_foto.py auto` bleibt fuer die Fotowahl und zum Ansehen; fuer Masse/Quader nicht mehr als Quelle.

Nachtrag 16.11. ~14:00:
- `fassade_zylinder.py` findet jetzt OEFFNUNGEN selbst (dunkle kompakte Rechtecke gegen die oertliche Helligkeit, Dubletten an der Bildnaht zusammengefasst) -> `<aus>.json` "oeffnungen" + `<aus>_oeffnungen.jpg`;
  im Generator `bauteile.zylinder_oeffnungen(json, nur=[...])`. Treppenturm: 7 Vorschlaege, 6 echt (1 Fehltreffer = Sockelstein an der Bildnaht, von Hand ausgeschlossen); helle (verschlossene) Schlitze werden NICHT erkannt.
  Zusaetzliche Sichtpruefung "30 cm vor dem Mantel freie Luft" gegen durchscheinende Anschlusswaende; cos_min 0,5.
- Steingewaende/Steinbaender in Putzwaenden: `steine_aus_foto.py --nah 0 --bosse 0.015` ueber die Wandmitte = alles, was nicht Putz ist (West: 3 Fenstergewaende + Gesimsband aus Foto 047).
- GRENZE Einzelfoto: Verdeckung wird nur gegen das MODELL geprueft. Ein Baum (nicht im Modell) wurde auf der Suedseite zu "Steinen" - dort das Mehrfoto-Fassadenbild nehmen (fassade_fein erkennt Verdecker ueber Parallaxe).
  `fassade_ein_foto auto` kennt keine Baeume: Ergebnis immer ansehen. OFFEN: Verdecker-Test auch fuer Einzelfotos (Vergleich mit einem zweiten Foto).
- Kruemelfilter beim STL-Schreiben arbeitet jetzt ueber gemeinsame KANTEN (wie trimesh.split); ueber gemeinsame Ecken blieb ein 6-Flaechen-Kruemel als zweiter Koerper.

Nachtrag 16.11. ~15:00 - IN DER KETTE:
- `steine_aus_foto.py --foto auto`: waehlt das beste vertrauenswuerdige Foto fuer das Feld selbst; VERDECKER ausserhalb des Modells (Baum) ueber ein Gegenfoto von anderem Standort:
  oertliche Korrelation der normierten Helligkeit auf der Wandebene < 0,25 bei vorhandener Struktur = widerspruechlich = keine Daten. Test Sued (Baum in beiden Fotos): 89 % ausgeblendet (richtig);
  West mit eigenem Gegenfoto: 41 % ausgeblendet - ob das zu streng ist, ist NICHT geprueft (Schwellen an einem Bauwerk).
- `fassaden_kette.py --fotosteine [--foto_ab 10] [--nachbar_stl ...]` = Stufe 5c; `anbauen()` setzt `<wand>_foto.npz` vor das grobe Relief. `gesamtkette.py` ruft die Kette mit `--fotosteine`. NUR SYNTAXGEPRUEFT, nicht gelaufen.
- `bauteile.spitzbogen`: gedrueckter Bogen (Stich < halbe Breite) = zwei Kreisboegen mit Mittelpunkten 0,3 x halbe Breite unter der Kaempferlinie. Dritte Fassung an einem Tag:
  waagerechter Sturz (falsch) -> Vier-Zentren (Nutzer: "spitzes Fehlerding") -> diese; am Bild neben Foto 217 passt die Form. Lehre: Bogenform IMMER am Bild neben dem Foto pruefen, bevor veroeffentlicht wird.
- Bogensteine der Tore werden NICHT generiert (Nutzerregel 15.11.: nichts Kuenstliches im Tor; die echten stehen im Scan-Relief).

## HAERTETEST 16.11.2026 nachmittags: drittes Gebaeude `ober_tvdr` (LoD2 DEBW_0010007Tvdr, Haeuserzeile Oberlinden noerdlich des Tors)
NICHT von null: Rahmen, Kameras (630 K-Dateien), Wolke und Netz von schwab_v3 uebernommen; SfM/dichte Wolke nicht neu (Platte 10 GB frei, Laufzeit Stunden). Stufen von Hand in Kettenreihenfolge:
objekt_anlegen -> dach_vermessen -> bauen -> fassaden_kette --fotosteine -> fassade_ortho/parsing/fein -> fenster_aus_parsing -> bauen (mit aushoehlen) -> modell_neben_foto.
ERGEBNIS: Abnahme gruen; LoD2-Koerper sitzt im Foto 113056 an der richtigen Stelle; an der einen gut gesehenen Fassade (rotes Haus, f02, 9 m) schneidet die Automatik 6 Fenster
(5 echte + Schaufenster; eines fehlt hinter einem Fahrdraht-Artefakt), im Bild neben Foto 113148 an passender Stelle. Kein Handmass.
GEFUNDENE FEHLER (alle behoben, ausser markiert):
1. fassaden_kette brauchte dach.json (Stufe dach vorher) - Reihenfolge, kein Fehler.
2. Netz deckt das Gebaeude nicht -> alle Waende "AUS", Fotostufe lief nie. Jetzt: leeres Relief als Traeger, Putz/Steine nur aus Fotos; ohne brauchbares Foto AUS; anbauen() setzt bei solchen Waenden nur die Fotoplatte (sonst 193 Splitterkoerper).
3. steine_aus_foto --foto auto waehlte eine Nahaufnahme des Schwabentors, die 15 % der Wand streifte (Wertung sichtbar/Aufloesung). Jetzt sichtbar^2 / Aufloesung (gedeckelt 0,5 cm) und mindestens 30 % sichtbar.
4. fassade_ortho fand 0 Fotos (verlangt buendel_tor in den K-Dateien) -> Rueckfall auf alle vertrauenswuerdigen Messkameras.
5. fenster_aus_parsing: feste Schwelle 3 Stimmen warf bei nur 3 Fotos fast alle Fenster weg (2 von 11) -> anteilige Schwelle (>= 2 und 60 % der sehenden Fotos); fenster_aus_json entsprechend.
6. OFFEN: die Generator-VORLAGE (objekt_anlegen) schreibt ihr STL selbst ohne Kruemelfilter; eine Fotoplatte (w00) gab 44 Zwei-Flaechen-Kruemel und wurde von Hand ausgeschlossen.
7. OFFEN: relief_einsatz.py stuerzt bei leerem Netzausschnitt ab (IndexError) statt sauber "leer" zu melden (Kette faengt es ab).
8. OFFEN: nur 1 von 13 Fassaden hat genug Fotos (>= 3 mit >= 96 px); Daecher, Rueckseiten, Laeden unten sind nicht bearbeitet; Dach = Walm-Fit aus DOM1 (RMS 1,06 m), nicht aus Fotos.
BEWERTUNG: fuer ein gewoehnliches Haus liefert die Kette jetzt ohne Handmass Koerper + Fenster einer gut fotografierten Fassade. Der Engpass ist die Fotoabdeckung je Fassade, nicht mehr die Software der Fensterstufe.

Nachtrag Haertetest (16.11. ~16:00), offene Punkte 6/7 und Fotoauftrag:
- Vorlage `objekt_anlegen.py` und `ober_tvdr_gen.py` schreiben jetzt ueber `bauteile.stl_schreiben` (Kruemelfilter). `relief_einsatz.py` meldet ein leeres Netz sauber (rc 4).
- `steine_aus_foto.py --streng` (in der Kette gesetzt): kein Ergebnis ohne Gegenfoto oder bei > 2 cm/px. Anlass: an ober_tvdr w00 wurde ein Holzgeruest aus einem 6-cm-Foto zu "Quadern".
  GRUNDSAETZLICH OFFEN: "Stein = nicht Putzfarbe" gilt nur fuer Putzbauten mit Werkstein; an farbigen Haeusern (rot, gelb) ist alles "Stein". Die Stufe braucht ein Tor "ist das ueberhaupt Quaderwerk?" (Fugenraster vorhanden).
- `foto_auftrag.py` fuer gewoehnliche Haeuser: ungesehene Fassade -> Standort 8-20 m DAVOR auf der Strasse (nicht mehr ein Fernfoto vom Muensterturm als Vorbild; Vorbild nur aus eigenen/online-Fotos < 130 m).
  Fehler dabei: ein angehaengter Kommentar hatte den Rest einer Codezeile auskommentiert (0 statt 6 ungesehene) - am Zahlenvergleich bemerkt.
  Fotoauftrag Oberlinden (6 Fassaden): https://claude.ai/artifact/BtfcXPeVi14Yid3kGypyRJ, Daten `modelle/ober_tvdr/audit/fotoauftrag.json` -> `tools/foto_check.sh ober_tvdr <datei>` ist damit einsatzbereit.

Nachtrag 16.11. ~16:40 `foto_auftrag.py` (Nutzer: "eine Uebersicht, dann jede einzelne Ansicht: die Lage und ein Bild rot markiert, was ich fotografieren muss - zusammen, jedes fehlende Ding als Objekt"):
Seite = Uebersicht (Stadtplan + nummerierte Liste mit Sprunglinks), danach je Auftrag EIN Block: links "Hier stehen" (Planausschnitt, Blickrichtung, Kartenlinks), rechts "Das fotografieren"
(Foto vom Standort mit rotem Rahmen; gibt es keins: mit `--stl` ein gerendertes Modellbild mit rotem Rahmen), darunter Anweisung, Ziel vergroessert, Zahlen, "weiter zu N". Allgemeine Regeln ans Ende.
Aufruf jetzt mit `--stl <eigenes>,<nachbarn>`. Modellbild bei Standort < 1,6 x Zielgroesse: Kamera zurueck/schraeg/erhoeht (Orientierungsbild, nicht der Standort).

Nachtrag 16.11. ~17:00 "alle Quellen" (Nutzer: "Muss ich wirklich Fotos machen?" - "Gib Vollgas"):
- `commons_harvest.py --category "A|B" --tiefe 2 --width 1920 --pause 4`: mehrere Kategorien, Unterkategorien, Standardbreite, Pause (Wikimedia drosselt Serien). Kategorien Schwabentor (162 Dateien + 4 Unterkat.) und Oberlinden (100 + 5) laufen.
- `kamera_verfeinern.py --liste datei`: viele Fotos in EINEM Lauf (Referenzmerkmale/-tiefenbilder nur einmal); Fotos OHNE Kamera werden gegen einen Kranz guter Fotos (3 je Fassade + nachgezogene Fremdfotos) eingehaengt.
- `fassade_ortho.py` nimmt jetzt auch Kameras mit `vertrauen` (bisher nur buendel_tor) - sonst kaemen nachgeholte Fotos nie ins Fassadenbild.
- Ablaufskript dieses Laufs: <daten>/schwab_v3/seiten_nachholen/nachlauf.sh (ungepruefte SfM-Posen der Downloads werden als .unsicher beiseitegelegt, dann alles ohne Vorwissen eingehaengt, Orthos und Fotoauftraege neu). NOCH NICHT als Teil von seiten_luecken.py.

Nachtrag 16.11. ~18:30 - zwei Fehler der Fensterstufe, die erst der zweite Durchlauf an ober_tvdr zeigte:
- RUECKKOPPLUNG: seit Fenster echte Loecher sind, war das Fassadenbild an jedem schon gebauten Fenster schwarz (Strahl trifft keine Flaeche) -> die Erkennung fand an der eigenen Fassade nichts mehr (6 -> 0).
  `fassade_ortho.py`: Zellen im Fassadenpolygon ohne Modellflaeche = Oeffnung, Farbe von der Wandebene, sichtbar wenn nichts davor steht. Abdeckung f02 58 -> 86 %.
- MOSAIK: eine Fassade mit 52 Fotos und 94 % "Abdeckung" war ein Flickwerk aus Baum, Nachbarn und Strassenszene, trotzdem 4 "Fenster". `fassade_ortho.py` schreibt jetzt `uneinig_<id>.png`
  (Streuung der Grauwerte ueber die Fotos je Zelle), `fenster_aus_parsing.py --uneinig 28` verwirft Kaesten in widerspruechlichen Zonen. Messung: gute Fassade 0-18, Mosaik 40-67.
  LEHRE: "Abdeckung in Prozent" sagt nichts ueber Brauchbarkeit; kuenftig Uneinigkeit mitmelden (foto_auftrag.py und seiten_luecken.py tun das noch NICHT).

Nachtrag 16.11. abends - Tempo und Selbstkontrolle (alles Standardverhalten der Werkzeuge, damit ohne Zusatzschalter in der Kette):
- `fassade_ortho.py`: (a) Vorpruefung "sieht das Foto ueberhaupt eine Fassade" VOR dem Laden; (b) `--max-fotos 40` = je Fassade nur die 40 besten Kameras (Sichtanteil / Meter je Pixel, nur aus K-Dateien).
  Anlass: Turm mit 700 Kameras x 4 Waende lief > 2 h. Messung Haeuserzeile: 60 -> 41 s durch (a); (b) dort ohne Wirkung auf das Ergebnis (wenige Kameras je Wand); Turm-Messung siehe Aufgabenliste.
  GPU-Sichtbarkeit (`--gpu-sicht`) gebaut und VERWORFEN als Standard: langsamer (61 gegen 41 s) und weniger streng.
- `pruefstand.py` z_am_punkt ueber senkrechte Strahlen: Turm 153 -> 35 s, Werte identisch an 3 Objekten.
- `umriss_tor.py` laeuft in `bauen_abnehmen.sh` (Hinweis), `schnelltest.sh` nach jeder Werkzeugaenderung (CLAUDE.md).
- `fenster_aus_parsing.py`: Stimmen >= 50 % der sehenden Fotos, Uneinigkeits-Tor, Raster-Regel (alles Standard; `--ohne-raster` schaltet die Regel ab).

Nachtrag 16.11. nachts - generisch und in der Kette (Nutzer: "alles generisch bauen und in die Pipeline einbauen, alles"):
- KAMERA-PLAUSIBILITAET ueberall: `kamera_verfeinern.py` (Abstand <= 600 m, f zwischen 0,4 und 10 x Bildbreite), `fassade_ortho.py` (Vorauswahl und Sichtpruefung ueberspringen Standorte > 2 km / nicht endlich),
  `schnelltest.sh` prueft ALLE Objekte auf absurde Kameras. Bereinigt: 49 K-Dateien als `.unplausibel` (schwab_v3, ober_tvdr, schwab_nachbar, schwab_auto, martinstor). Anlass: siehe NICHTS_GEBRACHT.md "ein Kern 100 %".
- UNEINIGKEITSKARTE dritte Fassung: grobe Bloecke 0,3 m, Belichtung je Foto angeglichen, MAD statt Streuung. Sie dient NUR dem Fenster-Tor (`fenster_aus_parsing --uneinig 28`).
  Als Mass "Wand gesehen ja/nein" taugt sie NICHT (saubere Turm-Suedwand 30, gemischte Zeilenfassade 18): in `foto_auftrag.py` nur mit `--mit-uneinig`, in `seiten_luecken.py` nur mit LUECKEN_MIT_UNEINIG=1.
  OFFEN: ein belastbares Mass fuer "Fotos zeigen dasselbe" (Strukturvergleich statt Helligkeit, vgl. Gegenfoto-Korrelation in steine_aus_foto.py).
- Turm nach der Download-Runde (fassade_neu, 3 cm, 40 Kameras je Wand, 111 s): Nord 91 %, Sued 91 %, West 90 %, Ost 45 % (morgens 0 %). Fotoauftrag Turm: nur noch Ost unten + 5 Detailwuensche.

Nachtrag 16.11. spaet - Kameras sicher, Zwischenspeicher, Kette:
- `tools/kamera_plausibel.py` = EINE Regel (Standort endlich, <= 1500 m vom Objekt, Brennweite 0,3 bis 12 x Bildbreite) fuer alle Kamera-Schreiber: `kameras_aus_buendel.py` (schreibt Unplausibles nicht),
  `foto_kalibrieren.py` (bricht mit rc 3 ab), `kamera_verfeinern.py`, `schnelltest.sh` (alle Objekte), Gesamtkette Stufe `fototor` (`--beiseite`). Zweiter Fund: 11 Kameras mit NEGATIVER oder winziger Brennweite.
- `kamera_verfeinern.py` TIEFENSPANNE-TOR: Abstand und Zoom sind nur trennbar, wenn die Inlier in der Tiefe verteilt sind. Mass = Tiefenspanne (p5-p95 entlang der Blickachse) / Abstand, Schwelle `--min_tiefe 0.06`.
  Darunter: Brennweite aus EXIF festhalten (wenn vorhanden und der Rest dann <= 3 x so gross bleibt), sonst NICHT schreiben. Probe: beide "Mond-Kameras" (4609 bzw. 205 Inlier, Tiefenspanne 0,0 % / 0,4 %) abgelehnt, gute Kameras unveraendert.
  Die Inlier-ZAHL sagt darueber nichts (4223 von 4609 lagen auf einer Wand).
- `bauteile.zwischenstand(koerper, name)` = Zwischenspeicher im Generator (Schluessel: Generatortext bis zur Zeile, Werkzeug-Inhalt, Eingabedateien, Umgebung). Im Turm-Generator an 5 Stellen
  (1_nord, 2_sued, 3_west, 4_vor_hohl, 5_hohl). OHNE_CACHE=1 schaltet ab. Neue Generatoren: nach jeder Fassade und vor/nach `aushoehlen` einen Zwischenstand setzen.
- Gesamtkette: `kamera_plausibel` in Stufe fototor, `umriss_tor.py --eintragen` nach Stufe fenster.
- NACHPRUEFUNG aller 128 'vertrauen'-Fremdkameras des Turms mit dem Tiefenspanne-Tor (16.11. spaet, Ergebnis `seiten_nachholen/tiefentor_ergebnis.json`): 90 bestehen, 28 haben Punkte fast in einer Ebene
  (und keine EXIF-Brennweite), 5 nur mit festgehaltener EXIF-Brennweite (frei geschaetzt lag f um das 1,3- bis 5-Fache daneben), 5 ohne tragfaehige Loesung. Die 38 tragen jetzt `tiefe_unsicher` in der K-Datei:
  sie bleiben fuer das Bild IHRER Wand brauchbar (dort passen sie auf wenige Pixel), sind aber KEINE Referenz mehr fuer neue Kameras (`kamera_verfeinern.py`) und taugen nicht fuer Masse ausserhalb der Wandebene.
  OFFEN: Messwerkzeuge (foto_mass, fassade_tiefe, steine_aus_foto --foto auto) werten das Kennzeichen noch nicht aus.
- STRUKTURKARTE `struktur_<id>.png` (jeder fassade_ortho-Lauf schreibt sie): je Foto 0,1-m-Bild, lokal normiert, MAD ueber die Fotos, Wert x 100. Gemessen (Median der Wand): Putzhaus sauber 3, Turmwaende 22-33
  (Putzfelder ~5-15 blau; Eckquader, Galerie, Vordach, Tordurchblick, Baum 50-80), Mosaik-Fassade der Zeile 44. Sie zeigt also "liegt nicht in der Wandebene ODER wird verdeckt ODER Fotos zeigen Verschiedenes" -
  brauchbar als Hinweis auf Vorbauten/Verdecker und als Mosaik-Warnung (Wandmedian > 40). NOCH KEIN TOR: Fensterrahmen und Quader schlagen zu Recht an; die Fenstererkennung bleibt bei `uneinig_<id>.png`.
- ZWISCHENSPEICHER gemessen (Turm): unveraenderter Bau 28 s statt 115 s, Speicher 4,1 statt 9,7 GB; `aushoehlen` (80 s) als Funktion uebergeben (`_zw(_hohl, "5_hohl")`), sonst laeuft es trotz Treffer.
  Aenderung an einer Fassade: gespart werden nur ~10 s davor, das Aushoehlen laeuft neu. STL kalt = warm bitgleich; gegenueber dem Stand ohne Zwischenspeicher gleiche Form (Volumen +-1 mm3), andere Dreieckszahl.

Nachtrag 16.11. abends - KETTE AB 'bauen' ALS EIN BEFEHL (Probe schwab_auto): `python3 tools/gesamtkette.py schwab_auto --ziel schwab_auto --ab bauen --bis html` (ueber job_start.sh)
- Drei Laeufe noetig; gefundene und behobene Kettenfehler: (1) objekt.json `fotos_dir` zeigte auf den Fotoordner der Quelle, die Kameras heissen aber nach dem Sammelordner -> 0 Fotos auf allen Fassaden,
  IndexError in relief_putz; die Kette setzt fotos_dir jetzt selbst (daten/<ziel>/fotos -> Sammelordner). (2) rc 0 mit leerem Ergebnis galt als Erfolg -> `fenster_ortho_inhalt` (0 Fotos = Fehler), Stufe seiten
  laeuft dann NICHT (sonst 32 min Download umsonst). (3) Stufe seiten fand sparse/db nicht (liegen unter pipe/sfm/). (4) Generator aus alter Vorlage rief anbauen/fenster_aus_json nicht auf -> `generator_vorlage`-Meldung.
  (5) `fassaden_kette.anbauen` schnitt jede Wand gegen alle frueheren Reliefs: 13,6 GB, vom System beendet -> Huelle aus dem Grundkoerper + Zwischenergebnis je Wand: 7,2 GB, 96 s.
  (6) Root-Platte unter 5 GB durch Git-Objekte (118-MB-STL je Commit) -> `tools/git_packs_auslagern.sh --packen`.
- Laufzeit ab 'fassaden' bis 'html' mit Inhalt: 11 min (ohne Download). Abnahme schwab_auto bestanden.
- ERGEBNIS ANGESEHEN (audit/seiten.jpg), ehrlich: Nordseite mit Relief (Uhr, Eckquader, Galerie als Abdruck), 2+2 Fenster; Sued/West/Ost fast glatt, KEINE Tordurchfahrten, Dach nur LoD2-Zelt, kein Treppenturm-Detail.
  Vorbauten-Sweep auf allen 8 Fassaden 'nicht belastbar' (LoD2-Ebene bis 2,5 m neben der Wand). Widerspruch: seiten_luecken meldet 'alle Waende gesehen', foto_auftrag meldet Ostseite 240 m2 ohne Daten (verschiedene Schwellen) - OFFEN.

## Nachtrag 16.11.2026 nachts: Fehlersuche (statische Pruefung + Kettenbericht + Bild Modell neben Foto)
Vorgehen, das Fehler fand: (1) pyflakes ueber tools/ (nur "undefined name"), (2) JEDE Zeile des Kettenberichts lesen, auch rc 0 mit leerer Ausgabe, (3) Modell neben Foto ansehen.
Behoben:
- `kamera_plausibel.py` hatte am 16.11. ein AELTERES Werkzeug gleichen Namens ueberschrieben (Kameras unter Gelaende, Tor `tor_kamera_gelaende`, Liste fuer `wolke_neu_fusionieren.py`). Das alte heisst jetzt `tools/kamera_gelaende.py`; die Kette ruft es wieder richtig auf. Lehre: vor `Write` einer neuen Werkzeugdatei `git log -- <pfad>` pruefen.
- Kameras tief unter der Strasse (25 bis 240 m) lieferten Fassadenbilder (schwab_auto f01/f03/f05). Regel in `kamera_plausibel.plausibel`: tiefer als 5 m UND steiler als 25 % = unplausibel; Kette zusaetzlich `--tief=3` (ANNAHME ebenes Umland; in Hanglage braucht es das DGM - offen). 44 + 33 Kameras beiseitegelegt (`.unplausibel`).
- Umriss-Tor: lief ohne `neben_fotos` leer mit rc 0 (jetzt rc 2 + Meldung); brach ab, wenn die Himmelsmaske fehlte (sys.exit aus foto_pick, rc 1, kein Ergebnis - auch am handgefuehrten Turm); meldet jetzt, wenn >= 2 Fotos dieselbe grobe Abweichung zeigen (Kettenturm: +5,1 m, Dach fehlt/zu niedrig) statt jedes einzeln als "nicht auswertbar" zu verwerfen.
- NEU `tools/neben_fotos_waehlen.py`: je Seite das beste Vergleichsfoto (Kette traegt es ein, wenn keins da ist). Kettenturm: Nord, Sued, Ost gefunden, West ohne Foto.
- Kettenbericht "WARNUNGEN im Lauf" zaehlte alle frueheren Laeufe mit (`log_warnungen.sammeln(ab_zeile, seit)`).
- `bauen_abnehmen.sh`: Pflichtbilder scheiterten bei 4 Mio. Dreiecken am Grafikspeicher (3 gleichzeitig) - Fehlschlaege werden einzeln wiederholt.
- `modell_3d_html.py`: ueber 800 000 Dreiecke waehlt es das Anzeige-Raster selbst (Kettenturm 98 MB -> 12 MB).
- `foto_bundle.py`: ein Kommentar mitten in der Zeile schluckte Code (NameError bei Fotos ohne Einzelkamera); `element_einpassen.bogen_einpassen`: zwei undefinierte Namen; `regression.py`: KeyError ohne Konfiguration.
Gefunden, OFFEN:
- Verzeichnung k1 der Messkameras ungeprueft (Werte bis -160; `modell_neben_foto` entzerrt damit, Foto online_orig__od_08 kommt verzerrt heraus).
- Kamera des Nordfotos eigen__IMG_20261106_113201 am Kettenturm: Modell erscheint gekippt neben dem Foto - Kamera pruefen.
- Himmelsmaske lehnt ein Foto mit klarem blauem Himmel ab (online2_orig__od_15: "unten_mitte 0.79").
- `relief_putz.py` meldet "Stein im Mittel +nan cm", wenn kein Stein uebrig ist.
- Vertrauensliste der Fremdkameras am Turm enthielt Kameras unter Gelaende - Liste neu rechnen.
- Tuerme haben keine Regressions-Konfiguration (`objekt.json["regression"]`): die Pflicht "regression.py nach tools-Aenderung" prueft dort nichts.
- `seiten_luecken.py` ("alle Waende gesehen") gegen `foto_auftrag.py` (Ostseite 240 m2 ohne Daten): Schwellen weiter verschieden.
- `bauwerk_generator.py`: Farbschluessel 'laterne' doppelt; `terrain_eggcrate.py`: ungueltige Escape-Folge (nur Warnung).

## Nachtrag 16.11.2026 spaet nachts: zweite Fehlersuche (Kameras)
- Verzeichnung: `kamera_plausibel.plausibel(k1=, bild_diag=)` - Bildrand hoechstens 25 % verschoben und nirgends gefaltet (1 + 3 k1 r^2 > 0). 19 Kameradateien beiseite (k1 bis -160). Das "verzerrte" Vergleichsfoto war eine solche Kamera (online2_orig__od_15), NICHT die Himmelsmaske und nicht od_08 (Verwechslung in der ersten Auswertung; die Himmelsmaske lehnte ein Nachtfoto zu Recht ab).
- Kameras ohne Netzpunkte: `kameras_aus_buendel.py` schrieb JEDE Kamera der Ausrichtung, auch 21 ohne einen einzigen 3D-Punkt (der globale Mapper stellt sie irgendwohin). Der eingebaute Pruefblock lief nie (pycolmap fehlt in venv-seg, 'sparse' der Kettenausrichtung ist None). Jetzt: `--sparse` + `tools/kamera_sfm_guete.py` (ohne pycolmap); unter `--min_beob 30` Netzpunkten wird nicht geschrieben, alte Datei wird beiseitegelegt; `rms_px` und `sfm_guete` stehen in der Kameradatei. Kettenturm: 24 Kameras weg, 31 der uebrigen 427 sind Klasse 'schlecht' (Rueckprojektion > 2 px oder < 150 Punkte) - noch NICHT ausgeschlossen (erst Wirkung messen).
- Nordkamera eigen__IMG_20261106_113201: 2608 Netzpunkte, 1,2 px - die Kamera stimmt; der "gekippte" Eindruck war Weitwinkel. Kein Fehler.
- Kette: Python-Absturz in einer Stufe ist immer ein Fehler (vorher galt rc 1 bei bauen/fenster_fein als Hinweis); Bau ohne Ergebniszeile = Fehler.
- `seiten_luecken.py` meldet Waende mit >= 30 m2 ohne Bilddaten als TEILWEISE (vorher "alle Waende gesehen" neben einem Fotoauftrag ueber 240 m2).
- `steine_aus_foto.py --foto auto` und 'tiefe_unsicher': kein Handlungsbedarf, das Werkzeug liest nur Bildinhalt der eigenen Wandebene.
- 7 der 128 "vertrauenswuerdigen" Fremdkameras am Turm standen tief unter der Strasse (jetzt beiseite, 121 uebrig) - die Vertrauenspruefung (Einzelfoto gegen eigene Wand) sieht das nicht.

## Nachtrag 17.11.2026 00:30: Stabilisierung der Kette
- `gesamtkette.lauf`: Ausgabe zeilenweise ins Log (vorher erst am Stufenende), Zeitlimit je Stufe (RCPARK_STUFE_MAX_S, Standard 3 h, Prozessgruppe wird beendet, rc 124), Platztor vor JEDER Stufe, Python-Absturz = Fehler, Bau ohne Ergebniszeile = Fehler.
- Kettenende: `ERGEBNIS DES LAUFS` mit Liste der Stufen, die nicht in Ordnung sind, rc 4 statt immer 0; Marke `LAUF_START` im Bericht.
- `tools/json_sicher.py`: objekt.json, masstabelle.json, K-Dateien und der Kettenbericht werden erst vollstaendig gewandelt, dann atomar ersetzt (12 Werkzeuge, 26 Stellen). Vorher leerte ein Fehler mitten im Schreiben die Datei.
- `bauteile.stl_schreiben` und `zwischenstand`: erst fertig schreiben, dann umbenennen (Verknuepfung auf die Datenplatte bleibt erhalten).
- `bauen_abnehmen.sh`: Sperre je Objekt (zweiter Lauf bricht mit rc 5 ab); am Ende zaehlt es Abstuerze der Nebenpruefungen ("ACHTUNG: ...").
- `seiten_luecken.py --holen`: dieselben Kandidaten fuer dieselben Waende werden nicht noch einmal 30 min nachregistriert (Marke `versucht_<hash>.txt`, neu erzwingen SEITEN_NEU=1).
- Schnelltest prueft jetzt: Zeitlimit, Absturz-Erkennung, Kameraregeln (Tiefe, Verzeichnung).
OFFEN (gefunden, nicht geaendert): `baukasten_gen.py:916` - Kommentar schluckt `wd_ /= np.linalg.norm(wd_)` (Rippenbreite haengt seit 13.11. leicht vom Winkel ab); Aenderung braucht Abnahme der Erker-Objekte.
OFFEN: `objekt.json["regression"]` ist bei ALLEN Objekten leer oder fehlt - `regression.py --pruefen` prueft nirgends etwas; der Schnelltest ist der einzige feste Test.

## Nachtrag 17.11.2026: Bausatz - Farbteile, Druckteilung, Druckzeit (Nutzerziel: mehrere Teile, je Farbe ein Teil, Stein flach drucken, gute Druckzeit)
Ablauf (alles generisch, arbeitet am fertigen STL):
1. `tools/druck_farbteile.py <objekt> --masken relief/<wand>_putz.npz,...` - Steinflaechen (nicht Putz) als flache Platten, Koerper mit Taschen (Spiel 0,15 mm). Lage der Wandflaeche wird per Strahlen am Modell gemessen (Maskenebene und Modellwand lagen am Turm bis 27 cm auseinander). Der Koerper braucht mehr Wand: Turm mit WAND_MM=2.2 in eigene Datei gebaut (`rc-park_stl/schwab_v3_wand22.stl`), das abgenommene STL bleibt.
2. `tools/druck_teilung.py <objekt> --stl .../koerper.stl` - bettgerechte Teile; neu: Mindesthoehe je Teil (`min_teil_mm` 15), kein Schnitt, der Splitter (< 0,5 % Volumen) abtrennt, alte Teile werden vor dem Schreiben entfernt, Ausgabe auf der Datenplatte.
3. `tools/druck_farben.py <objekt> --eintragen` - Art (Dach/Wand) und Druckfarbe je Teil aus einer Palette des ganzen Gebaeudes (3 Farbgruppen der Fassadenbilder); Dachfarbe = ANNAHME.
4. `tools/druck_zeit.py <ordner>` - Druckzeit/Material je Teil mit PrusaSlicer (Standardprofil; nur zum Vergleich).
5. `tools/druck_vorcheck.py` - fuer Netze > 150 000 Dreiecke per Embree (vorher 14 GB Grafikspeicher -> Absturz).
Stand Turm (schwab_v3, Variante 2,2 mm Wand): 6 Steinplatten (518 m2, 2,6-6,3 mm dick, zusammen 15 h 9 min / 83 cm3), Koerper 1 Stueck, alles wasserdicht.
OFFEN: Raender Stein/Putz ausgefranst (Maske aus Fotofarbe) -> Kanten glaetten/an Fugen ausrichten; Ostseite ohne Maske; Vordachbereich Nord in der Platte; Passung nie gedruckt; Farbnamen grob ("grau" = Putz im Schatten);
Farbteile fuer Dach/Gesims/Uhr fehlen; Kettenobjekte: Masken heissen dort relief/wNN_putz.npz - Lauf steht aus.
Kettenpruefstand (`tools/ketten_pruefstand.py`), erster Lauf: kaufhaus_gk 23 Stufen, 2 nicht in Ordnung (fassaden_netz: InterfaceCOLMAP 'error writing depth-data', Ursache offen; fassaden), 13 Fenster, Abdeckung 30 %, kein Relief.
Netzstufe: braucht voruebergehend ~0,03 GB je Bild; raeumt die Tiefenkarten-Kopien jetzt selbst weg; Platzpruefung vorab.

### Druckzeit gemessen (17.11.2026, Turm, PrusaSlicer-Standardprofil, Bett 256 mm) - Grundlage fuer die naechste Bauart
- Steinplatten flach (6 Stueck, Schicht 0,16): 15 h 9 min, 83 cm3.
- Koerper mit Taschen, aufrecht in 5 Teilen (Schicht 0,2): OHNE Stuetzen 65 h 35 min / 690 cm3, MIT Stuetzen 98 h 15 min / 1013 cm3. Das unterste Teil (0-21 m, unter 8 m massiv) allein 35 h.
- Versuch: Schaftteil 21-35 m (aufrecht 19 h 9 min / 166 cm3) als 4 FLACHE Wandpaneele (3,4 mm dick): 2 gemessene Paneele 1 h 40 min und 2 h 4 min, alle 4 zusammen 45 cm3 -> etwa 7-8 h statt 19 h, Material 1/3,7.
  (2 der 4 Paneele lehnte der Slicer ab - die Taschen der Steinplatten zerlegen die Wandscheibe in bis zu 26 Stuecke; ein Paneel braucht eine durchgehende Traegerschicht.)
- FOLGERUNG: der schnelle Bausatz besteht aus FLACHEN WANDPANEELEN (Putz) + flachen Steinplatten + Dach/Aufbauten als Koerper; der aufrechte Hohlkoerper ist die langsamste Bauart.
  Naechster Schritt: `druck_paneele.py` (Waende an den Gebaeudeecken trennen, Traegerschicht, Eckverbindung, Sockel hohl statt massiv).
- `druck_zeit.py`: Druckraum wird angegeben (`--bett 256`), sonst lehnt der Slicer Teile ueber 210 mm ab.

### Bausatz Turm, Stand 17.11.2026 vormittags (Variante 2,2 mm Wand, nie gedruckt)
- Koerper: 6 Teile + 2 Verbinderringe (Schnitte 26,2 m und 35,0 m; an 11,1 / 36,5 / 46,9 m kein Hohlraum oder Kollision -> stumpf kleben), 67 h 23 min / 708 cm3 (Schicht 0,2, ohne Stuetzen). Unterstes Teil 22,5 h / 301 cm3 (massiv unter 8 m).
- Steinplatten: 6 Stueck, 13 h 54 min / 73 cm3 (Schicht 0,16). Durchdringung Platte/Koerper < 0,1 mm3.
- `druck_farbteile.py`: Taschentiefe = Wand - 0,6 mm - Spiel; Innenschicht 0,8 mm hinter jeder Tasche (ohne sie war der Koerper an den Ecken in 34 von 48 Hoehenschnitten offen; jetzt 2 von 48, bei 11 und 12 m - offen).
- `druck_teilung.py`: Verbinderringe (`verbinder_NN.stl`, Hoehe 2 x 3 mm, Wand 1,2 mm, Spiel = toleranz_mm) fuer waagerechte Schnitte ohne Stift.
- OFFEN fuer das Miniaturwunderland: Testdruck einer Steinplatte (Fugen ~0,35 mm tief = 2 Schichten - sichtbar?); flache Wandpaneele (`druck_paneele.py`, ~2,5x schneller); Sockel hohl; Ostplatte; Dach als eigenes Farbteil ist schon ein Teil (Farbe ANNAHME); duenne Grate an den Turmkanten (0,7 %).
- Kette: `netz_aus_dicht.py` nimmt einen Arbeitsordner auf der Datenplatte, wenn der Ordner neben der dichten Wolke auf einer anderen/vollen Platte liegt (kaufhaus_gk/pipe -> externe Platte, 4 GB frei).
- Kette: rote Lage sperrt Fotostufen (`lage_tor`, Martinstor); Einstieg ab 'fassaden' holt `dach.json` nach; Fototor nur fuer Fotos mit Messkamera.

### Bausatz fuer zwei Drucker (17.11.2026, Nutzer: grobe Teile Prusa MK4S 0,8-mm-Duese, feine Teile Bambu) - `tools/bausatz.sh <objekt> <masken> [WAND_MM] [SPIEL_MM]`
Turm (Wand 2,4 mm, Spiel 0,3 mm), gemessen mit PrusaSlicer-Standardprofil:
- Koerper MK4S (Duese 0,8, Schicht 0,4, 250x210x220): 6 Teile + 3 Verbinderringe, 23 h 52 min, 824 cm3 (~1 kg). Groesstes Teil 143 x 172 x 173 mm, laengstes 8 h 22 min (Sockel).
- Steinplatten Bambu (Duese 0,4, Schicht 0,16): 6 Stueck, 14 h 2 min, 75 cm3.
- Vergleich: derselbe Koerper mit 0,4-mm-Duese / 0,2 mm Schicht 67 h. Parallel gedruckt ~24 h Wanduhr statt ~81 h.
Kettenpruefstand 17.11.: kaufhaus_gk ab 'fassaden' 10 Stufen alle in Ordnung, 19 min, Relief an 9 Waenden, 9 Fenster, 4,6 Mio. Dreiecke (Sichtblatt: Ost mit Steinmuster, West/Sued fast glatt, keine Arkaden/Erker);
martinstor_gk haelt an 'lage_tor' an (Lage nie belegt); schwab_auto: Ostwand 10 % Bilddaten nach Aussortieren falscher Kameras.
`fassade_ortho.py`: 41 statt 65 s (ober_tvdr, 1-cm-Bild), Ergebnisbilder bitgleich. `--gpu-sicht` bleibt Option: 53 s, aber andere Abdeckung (f07 71 statt 82 %).

### Drucker aus der Sitzung starten + Demonstrator (17.11.2026)
- Bambu: `tools/bambu_slice.py` -> `tools/p1s_print.py print`. Prusa MK4S: `tools/prusa_slice.py` (0,8-mm-Profil "0.40mm QUALITY @MK4IS 0.8", Modellzeile jetzt "MK4S") -> `tools/prusa_print.py print` (PrusaLink; Zugang in ~/.config/rcpark/prusalink.json).
- Gestartet: Bambu `demo_tor_sued_stein` (Suedtor-Steinplatte 130 x 112 x 3,5 mm, 0,16 mm, 1 h 7 min); MK4S `demo_schaft_uhr_wand1mm` (Schaft 26-35 m, 1 mm Wand, 0,8-mm-Duese, 1 h 11 min). Dateien `modelle/stl/demo_schwabentor/`.
- Wand 1 mm statt 2,4 mm (MK4S 0,8 mm): Schaftabschnitt 1 h 33 statt 4 h 10, Mittelteil 2 h 46 statt 6 h 55.
- `druck_farbteile.py --einsatz` (duenne Wand): Platte = ganze Wand, dahinter Innenschicht im Hohlraum. STAND: Koerper 1 Stueck, Platten ohne Durchdringung, aber 27 von 48 Hoehenschnitten noch offen (Luecken zwischen Putzwand und Innenschicht) - NICHT fertig.
  Verworfen: Klebefalz nur am Rand + Eckpfosten (Koerper zerfiel in 243 Stuecke, Putzinseln im Stein ohne Halt).

### Agentenrunde 17.11.2026 (von mir nachgeprueft)
- `fassade_ortho.py`: 12,3 s statt 41 s (1-cm-Bild ober_tvdr), 49 Vergleichsbilder bitgleich; Embree-Kern direkt, Zellrechnung auf der GPU (`--ohne-gpu`, `--gpu-mb`), Rueckfall auf CPU wird gemeldet.
- Kette: ~20 Stellen gegen veraltete/leere Zwischenstaende gehaertet (`frisch()`, `abschluss()`, Platzpruefung hinter Verknuepfungen), 8 Tests `tools/test_kette_stabil.py` im Schnelltest. Ohne ganzen Kettenlauf geprueft.
- `tools/oeffnungen_bogen.py`: Bogenoeffnungen aus Parsing-Kasten + Durchblick (Ebenen-Sweep) + Formfit; schwab_auto hat die Tordurchfahrt (Nord gemessen: Mitte -0,13 m, Breite +0,35 m, Scheitel +0,13 m gegen schwab_v3; Sued ANNAHME). Offen: Arkadenreihen (Kaufhaus verworfen), Rechtecktore, lichte Oeffnung statt Fasenrand.
- Bausatz Einsatz-Bauart (`tools/bausatz.sh <objekt> <masken> 1.0 0.25 einsatz`, 3,5 min): Turm 1 mm Wand, Sockel hohl (`tools/druck_hohl.py`: 1342 -> 317 cm3), 0 von 73 Hoehenschnitten offen, Durchdringung 0,000 mm3.
  Koerper MK4S (0,8/0,4): 6 Teile + 4 Verbinderringe, 14 h 13 min / 334 cm3 (2,4-mm-Wand: 23 h 52 min / 824 cm3). Steinplatten Bambu (0,16): 8 Stueck, 10 h 21 min / 52 cm3.
  Offen: Platten liegen nicht ueberall auf (eine Plattenebene je Wand, bis ~1 mm Luft an der Nordwand); platte_nord_01/west_01 decken nur 30 %/17 % ihrer Maske; lose Stuecke in zwei Platten; Innenschicht 136 cm3.
- Die Zeile "27 von 48 offen - NICHT fertig" weiter oben ist damit ueberholt.

## Nachtrag 17.11.2026: Bauteil-Katalog erweitert (Bauteil-Runde Kaufhaus, `tools/bauteile.py`)
Neue generische Funktionen (keine Objektnamen, alle Masse als Parameter; Werte und Quellen stehen in `objekt.json` -> `bauteile_foto`, der Generator ruft nur auf):
- `korbbogen` / `bogen_querschnitt(form="korb")`: halbe Ellipse ueber dem Kaempfer, senkrechter Ansatz (Laubenboegen, flacher als ein Halbkreis, ohne Knick wie beim Stichbogen).
- `Wand.versetzt(d)`: Parallelwand mit gleichem u-Ursprung (Ebene aus dem Sweep statt LoD2-Wand).
- `laube(koerper, W, boegen, tiefe, decke, ...)`: offene Arkadenhalle hinter einer Bogenreihe, Stirnbogen in Querwaenden (`stirn`). Messweg: Pfeiler/Kaempfer/Scheitel am entzerrten Frontfoto (`wand_ortho.py px`, 2 Fotos deckungsgleich), Zahl `foto_zaehlung.py`, Hallentiefe per Ebenen-Sweep durch einen Bogen. Pruefung: `ebene_oeffnungen` (Anzahl + Breite) und `z_am_punkt` (Scheitel).
- `staffelgiebel(W, mitte_u, spitze_breite, spitze_z, flanken, ...)`: Spitzblock + Stufenbloecke je Flanke, je Block Gesimsplatte + Satteldaechlein. Messweg: Giebelebene per Sweep (am Kaufhaus lag sie 0,65-0,75 m HINTER der LoD2-Wand), je Stufe Aussenkante + Oberkante am entzerrten Bild dieser Ebene. Rumpf vorher mit `W.halbraum_innen` an der Ebene abschneiden.
- `schleppgaube(W, u, w_front, z_fuss, breite, hoehe, neigung, dach_z0, dach_s, ...)`: Front senkrecht, Gaubendach flacher als das Hauptdach bis zum Schnitt mit der Dachflaeche, Rundbogen-Fensternische. Zahl je Reihe am Foto, Lage per Triangulation der Fensteroberkanten.
- `erker_polygon(achse, front_n, apothem, zonen, konsole, fenster, felder, helm, knauf, stange, wirt=)`: n-eckiger Erker (Zonen-Prismen, Pyramidenkonsole, Lichter- und Feldnischen je Flaeche, geschweifter Helm aus Stumpfstuecken, Knauf, Stange). Achse = trianguliertes Helmknauf, Flaechenabstand durch Projektion des n-Ecks in >= 3 Fotos. `wirt`: Flaechen, die in der Wand stecken, bekommen keine Nischen (sonst Null-Volumen-Splitter).
- Reihenfolge im Generator: Rumpfschnitt (Giebelebenen) und Laube VOR `aushoehlen`; massive Anbauten (Giebel, Gauben, Erker) NACH `aushoehlen` - beim Hohlmachen der Gauben entstanden sonst 10 Null-Volumen-Teilnetze.
- Vorlage `tools/objekt_anlegen.py`: Fenster vor Relief + `fenster_fuer_bau` (wie im Kaufhaus-Generator).

## Feinrelief aus Einzelfotos per monokularer Tiefe (`tools/relief_aus_fotos_mono.py`) - VERSUCH 17.11.2026
Anlass: Druck Steinplatte Tor Sued (Brei-Zone rechts neben dem Tor, Bogen ohne Bogensteine). Modell: Depth Anything V2 SMALL (Apache-2.0); DSINE ist NC, MoGe-2 (MIT) waere der Normalen-Kandidat.
Ablauf: 1-cm-Raster auf der Ebene des Eingangsreliefs -> je Foto entzerrt (Kameras, Sichtbarkeit gegen STL) -> Tiefenmodell KACHELWEISE (1,5 m; ganzes Feld in einem Lauf sieht nur das Tor:
Korrelation 0,04) -> Hochpass je Kachel -> Massstab je Foto = Streuung des Scan-Bandpasses 2-60 cm -> LAGE vom Scan: Modell-Taeler liegen 4-6 cm UNTER den Scan-Fugen
(Schattenfuge), Versatz je Foto gemessen und zurueckgeschoben -> Fotos vereinen (Rand-Auslauf 20 cm, Kappung Median +-1,5 Streuungen, duenne erhabene Grate < 5 cm weg = Draehte)
-> Relief = Tiefpass Scan (> 60 cm) + Hochpass Fotos. Putz und Scan-Loecher bleiben Scan. `--ohne` fuer Fremdkoerper (Verkehrsschild).
Aufruf (so gelaufen): Sued `relief/sued_eben.npz objekt.json relief/sued_mono.npz --feld 0.1 11.4 0.0 9.9 --stl modelle/stl/schwab_v3_1-87.stl --n 6`;
Nord `relief/nord_eben.npz ... relief/nord_mono.npz --feld 0.1 12.0 0.0 10.4 --n 5 --abstand 0 --massstab 0.933 -2.15 15.28 0 --ohne 9.7 11.1 1.9 3.6 --polaritaet hell`.
GPU: JOB_GPU_MB=3500 (fp16; Grenze ist das Sichtbarkeitsraster des 2,5-Mio-Dreieck-STL). 2-4 min je Wand.
Ergebnis: Brei-Zone Sued zeigt die Steintafel mit Gesims und Wappen und die Steine darum; Nord zeigt die Keilsteine des Spitzbogens und die Figur. Fugenabgleich gegen ein Holdout-Foto
(F1, 2 cm Toleranz, Zufall = 13/9 cm verschoben): Sued Feld Scan 0,34 (Zufall 0,28) / neu 0,40 (0,28); Brei-Zone 0,37 (0,32) / 0,43 (0,30). Nord nicht auswertbar (Holdout liegt schief: Scan unter Zufall).
Grenzen: Standorte streuen (`--abstand`) bringt nur etwas mit >= 5 Fotos, sonst Naehte; eine Oberleitung bleibt als feiner Grat; Fugentiefe = Scan-Massstab (ANNAHME, nicht gemessen);
Tiefenmodell erfindet Relief aus Farbe (Wandbild im Putz) - deshalb Putz immer Scan.
Integration (Vorschlag, nicht gebaut): im Generator wie `sued_misch.npz`: `relief_koerper("relief/<wand>_mono.npz", tiefe=0.30, trend=True, rand_auslauf=False)`, grobes Relief mit dem Feld als `tief_felder`;
in `fassaden_kette.py` als Stufe nach `relief_putz.py` (Eingang `<wand>_eben.npz`/`_voll.npz`, Feld = Wandausschnitt bis 10 m Hoehe), Tor: Korrelation je Foto >= 0,2.

### Nachtrag 17.11.2026 abends: Mono-Relief im Schwabentor-Generator und in der Gesamtkette
- Werkzeug (generisch, ohne Objektnamen): Entzerrung auf der Reliefflaeche statt der Ebene (`--auf_relief 1`; Doppelstrich an der vorspringenden Steintafel Sued war Parallaxe);
  Drahtlinien je Foto erkannt (`draht_linien`, gerichteter Linienfilter + Hough + Duennheitsprobe, Lagerfugen +-4 Grad ausgenommen, `--draht_laenge 1.0`), Maske fuer Fotos
  vom selben Standort (< 1 m) geteilt und WEICH ausgeblendet; wo jedes Foto den Draht zeigt, steht die Feinform des Eingangsreliefs. Kachel-Normierung robust (`--kachel_norm robust`),
  Rand-Auslauf ab 8 cm hinter der Sichtgrenze (`--rand_weg`). Sackgassen: harter Ausschnitt der Drahtstreifen (Doppellinien an den Streifenkanten), Telea-Fuellung des Hochpasses
  im Streifen (breite Rinne), `cv2.inpaint` auf float32 (liefert Unsinn; 16 bit geht).
- Laeufe: Sued `relief/sued_eben.npz ... relief/sued_mono.npz --feld 0.1 11.4 0.0 9.9 --n 6 --zone 3.0 8.4 4.0 7.5 --zone 8.6 11.4 0.6 4.9`; Nord jetzt mit EINGANG `relief/nord_misch.npz`
  (Feinrechnung statt nord_eben: ausserhalb der Fotodaten und in Drahtstreifen steht so die Feinrechnung) `--feld 0.1 12.0 0.0 10.4 --n 5 --abstand 0 --massstab 0.933 -2.15 15.28 0 --ohne 9.7 11.1 1.9 3.6 --polaritaet hell`.
- Fugen-F1 Sued gegen Holdout 113836 (2 cm, Zufall ~0,28): Feld Scan 0,34 / alt 0,395 / neu 0,417; Bogen-Zone 0,35 / - / 0,42; Brei-Zone 0,35 / - / 0,41. Korrelation je Foto 0,27-0,48 (Sued), 0,58-0,67 (Nord, 113512 mit 0,11 verworfen).
  Nord-Holdout 113438 weiter nicht auswertbar (Scan unter Zufall).
- Generator `schwab_v3_gen.py`: `relief_koerper("relief/<wand>_mono.npz", trend=True, rand_auslauf=False)`, grobes Relief bekommt GENAU das Feld der Datei als `tief_felder`
  (`_mono_feld`, sonst Rillen an den Feldraendern); Nord: `nord_misch` entfaellt, wenn `nord_mono` da ist (steckt darin); `OHNE_MONO=1` schaltet ab.
- Kette `tools/gesamtkette.py` (Block nach `fassaden_kette`, Stufe `fassaden`): je Wand aus `audit/fassaden_kette.json` mit `_misch`/`_voll` -> `<wand>_mono.npz`, Feld 0,1..L-0,1 / 0..min(z1, 10 m),
  Tor `--min_korr 0.2`; Ergebnis je Wand unter `mono` in fassaden_kette.json. OFFEN: `fassaden_kette.anbauen()` setzt `<wand>_mono.npz` noch nicht ein (Datei nicht in diesem Auftrag).
- Grenzen: Nord-Drahtstreifen zeigt die (unruhigere) Feinrechnung statt Steinen; Kante rechts an der Steintafel Sued bleibt als Rille (echte Tafelkante + Schatten, nicht sicher getrennt).

## Nachtrag 17.11.2026 abends: Runde 3 Kaufhaus - Feinteil-Mass, Restbrei, Erker-Masswerk, Dachdeckung, Figuren
- **Feinteil-Mass `tools/feinteil_tor.py`** (nur Hinweis in `bauen_abnehmen.sh`, objekt.json `feinteil`): Feinband 2-12 cm von Foto (Grau) und Modell (Normalenbild),
  Strukturtensor -> Richtungshistogramm je 1-m-Kachel, SSIM-artige Kachelnote, Zonen als Kaesten (`modelle/<objekt>/feinteil_zonen.json`), fester Bewertungsbereich (`--bereich_stl`),
  Modellstaerke mit festem Bezug (erstes STL). Nachweis kaufhaus_gk, 9 Fotos: grob3 0,537 > gk 0,465-0,480 in 9/9 Fotos, in allen Zonen; grob3 0,5 m verschoben 0,471 (1 m: 0,433, 9/9 schlechter);
  Wiederholung bitgleich 9/9; falsches Fotopaar 0,29 < richtiges 9/9. foto_diff-F1 sah denselben Unterschied nicht (0,77/0,78). GRENZE: Brei (Netzrauschen) bekommt Punkte, wo das Foto
  viel Feinstruktur hat (Figuren, Goldrahmen, Bleiglas) - glatter Putz verliert dort (Ablation: Brei weg -0,020). Darum kein Tor.
- `fassaden_kette.relief_bereinigen` / `anbauen(..., bereinigen=dict(ersetzt, erhalten))`: Abweichungen >= 5 cm vom Wandniveau (wandniveau, 1-m-Median) als Stuecke; linienhafte gerade
  (Gesims/Gewaende, Fuellgrad >= 0,5) bleiben, Klumpen -> Wandniveau; Rechtecke `ersetzt` (Fotobauteile: Fenster, Balkon, Figuren, Erker als ("rund", xy, r, z0, z1)) -> Wandniveau. Bild relief/<wand>_rein.jpg.
- Katalog `tools/bauteile.py` neu: `dachflaechen`, `schindeln(koerper, abstand, tiefe)` (Saegezahn-Reihen je Dachebene, Abstand am Foto per Hang-Autokorrelation, Stufe >= 0,3 mm im Druck),
  `figur(W, u, w, konsole, koerper)`, `baldachin(W, u, w_wand, z_spitze, stufen, fialen)` (beide KLIPSTEIL-Kandidaten), `erker_polygon(..., konsole_rippen=)` + fenster.kopf/kaempfer + felder.medaillon.
- Uebertrag von Handmodell-Teilen: `modelle/kaufhaus_gk/uebertrag_grob3.py` (Similaritaet grob3 -> gk s 0,767; Gegenprobe: Figurenachsen auf den Fensterpfeilern +-0,08 m).

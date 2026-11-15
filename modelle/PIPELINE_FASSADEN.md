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
- Loesung: Bezugsfoto (groesste Summe Zellen x Guete); weitere Fotos per SIFT + RANSAC-Homographie im Ortho-Raum darauf ziehen
  (>= 40 Inlier, Eckversatz <= 2 m, sonst verworfen); Median wo >= 3 Fotos (Passanten, Draehte fallen heraus), sonst das beste.
- Laub: gruen-gelbgruene, gesaettigte Flaechen gelten je Foto als nicht gesehen; Bezugsfoto = meiste Wand ohne Laub (Schwabentor Sued: Baum vor der Wandmitte, danach 7 Fotos ausgerichtet, Wand frei). Achtung gruene Bauteile (Kupfer, gruene Ziegel).
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
Erster Lauf: Schwabentor Nordwand unten (u 0,1-12,05 m, z 0-10,5 m, Rohrahmen), 12 Fotos, 3200 px, 1 cm. **Ergebnis: siehe Nachtrag unten.**
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

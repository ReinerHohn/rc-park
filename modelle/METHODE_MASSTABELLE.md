# METHODE: Masstabelle + generischer Pruefstand (das Rueckgrat jeder Modellerzeugung aus Daten)

Stand 2026-11-01. Entstanden aus dem Martinstor: zehn Methodendokumente und 240 Werkzeuge lagen vor, trotzdem wurden dieselben
Fehler wiederholt (Validator-Protokoll F5/F6 = Versuchsregister I/J: Lektion aufgeschrieben, nicht erzwungen; Werkzeug je Objekt
hart verdrahtet; Quelle fuer ein Merkmal benutzt, das sie nicht sehen kann; Zahl geglaubt, ohne hinzusehen).
Diese Methode ersetzt keine der Quellen-/Generator-Dokumente, sie ist der **Pflichtrahmen darueber**.

## 1. Prinzip: Masse sind Daten, nicht Code
Je Objekt ein Ordner `modelle/<objekt>/` mit
- `objekt.json` - Generatorbefehl, STL, Massstab, ueberwachte Dateien, Fotos mit **Seite** (N/S/O/W) + Brauchbarkeit,
- `masstabelle.json` - **die einzige Wahrheit ueber die Masse**: benannte Messungen (generische Messer), Pruefungen mit
  Sollbereich, **Quelle, Quelltyp, Merkmalstyp**, Historie; dazu **offene Beobachtungen** (noch ohne Pruefung),
- `pruefbericht.json` - letzter Lauf (Istwerte), wird vom Pruefstand geschrieben.
Kein Messcode je Objekt mehr. Neue Merkmale = neue Zeile in der Tabelle; neue Messart = neuer generischer Messer in `tools/pruefstand.py`.

## 2. Quellen koennen nicht alles sehen - und der Pruefstand weiss das
`tools/pruefstand.py` lehnt eine Tabelle ab (Exit 2), wenn eine Pruefung ihre Quelle fuer ein Merkmal nutzt, das die Quelle nicht sehen kann:

| Quelltyp | sieht | **blind** fuer | Beleg aus diesem Projekt |
|---|---|---|---|
| laser_dom1 (1 m) | Hoehe von Flaechen, Grundriss grob, Anzahl grosser Aufbauten | duenne Bauteile, Schlankheit, Fassade, absolute Spitzenhoehe | Nadel 0,1 m unsichtbar: 54,8 statt 60 m; Kegelfuss 1,5 m war Rasterartefakt |
| laser_punkte (>= 8/m2) | zusaetzlich Schlankheit | Nadel, Fassade | nicht bezogen (60 EUR+), fuer Druck kaum Gewinn |
| lod2 | Grundriss, Traufe/First | alles darueber (Dachreiter, Tuermchen, Details) | LoD2 45,3 m = ohne Aufbauten |
| foto_verhaeltnis (400 px) | Verhaeltnisse, Schlankheit, Anzahl | absolute Masse, Grundriss | IoU-Unterschiede <= 0,01 sind Rauschen; Azimut bei symmetrischem Turm 90 Grad mehrdeutig |
| foto_vollbild | zusaetzlich duenne Bauteile (Nadel, Knauf, Fensterreihen) | absolute Masse ohne Massstab | Nadel 0,08-0,14 m, Knauf 0,67 m, 3 Fenster Nordseite |
| dokument | absolute Hoehen, Anzahlen, Daten | Form, Schlankheit | Bauforschung BW 60/65 m; Bezugshoehe unklar |
| modell | Druckbarkeit | Realitaet | wasserdicht, Koerperanzahl |

## 3. Pflichtablauf (ein Objekt, jede Aenderung)
1. **Beobachtung -> Zeile.** Jede Sichtbeobachtung (Nutzer oder eigene) kommt SOFORT als `beobachtungen_offen` in die Tabelle.
2. **Messen -> Pruefung, die FEHLSCHLAEGT.** Am Vollbild/Dokument/Laser messen (passend zum Merkmalstyp!), Pruefung mit Quelle eintragen,
   Pruefstand laufen lassen: sie muss am aktuellen Modell rot sein. Sonst ist entweder die Beobachtung falsch oder die Messung misst das Falsche.
3. **Generator aendern -> `tools/bauen_abnehmen.sh <objekt>`.** Gruen = weiter; rot = Modell korrigieren, nie den Sollwert.
4. **Hinsehen.** Foto-gegen-Render (`foto_render_seite.py`, `foto_profil_gpu.py`) ansehen, nicht nur Zahlen. Eine IoU-Zahl ohne Blick auf den
   Ausschnitt gilt nicht (5 von 15 Fotos hatten den ROI neben dem Turm, IoU 0,99).
5. **Widersprueche stehen lassen.** Sagen Foto und Laser Verschiedenes (Dachbreite 43-47 m), wird NICHT der Mittelwert gebaut, sondern die
   Beobachtung bleibt offen mit naechstem Schritt. Der Pruefstand zeigt offene Beobachtungen bei jedem Lauf.
6. **Commit-Sperre.** `git config core.hooksPath tools/git_hooks` (einmalig). Aenderung an Generator/STL/Tabelle ohne gruenen Pruefstand
   laesst sich nicht committen.
7. **Register.** Jeder Versuch (auch gescheiterte) ins `VERSUCHSREGISTER_<objekt>.md`; Sollwert-Aenderungen in `historie` der Pruefung.

## 4. Reihenfolge der Quellen fuer ein neues Objekt (was zuerst, was es liefert)
1. **Dokumente** (Denkmalamt/Bauforschung, Wikipedia, Structurae): absolute Gesamthoehe, Baujahr, Grundmasse -> erste Zeilen.
2. **LoD2 + DGM1**: Grundriss, Traufe/First, Gelaende -> Massing.
3. **Laser DOM1/nDOM**: Dachform grob, Aufbauten >= 3 m, Hoehe von Flaechen -> Hypsometrie als Validator (nicht als Geometrie).
4. **Fotos nach Seite sortiert** (`objekt.json/fotos`): erst Seiten zuordnen (Suedseite = ..., aus Lage/Nutzerhinweis), dann je Seite
   Fassade (Fensterzahl, Reihen, Uhr), dann Vollbild fuer duenne Bauteile. Symmetrische Objekte: Seiten MUESSEN unterscheidbar
   gemacht werden, sonst ist jede Kameraanpassung mehrdeutig.
5. **Erst danach** Optimierer/Varianten - und jedes Ergebnis je Parameter bewerten, nie als Ganzes.

## 5. Neues Objekt anlegen (10 Minuten)
`mkdir modelle/<objekt>`; `objekt.json` nach Vorbild `modelle/martinstor/objekt.json`; `masstabelle.json` mit den Dokument-/LoD2-Zeilen beginnen
(Gesamthoehe, Grundriss, wasserdicht, Koerper); `tools/bauen_abnehmen.sh <objekt>`. Messer, die fehlen, in `tools/pruefstand.py` ergaenzen
(generisch, mit Parametern - kein Objektname im Code). Verfuegbar: hoehe_max, lokales_max_abseits, max_z_im_bereich(zmax), ausdehnung_im_bereich,
querschnitte_abseits, anzahl_im_band, breite_achse, knauf_achse, nischen_anzahl (Fassade per Strahlen), relief_breite (vor/rueck/beide, max_luecke),
grundriss_rechteck(r), wasserdicht, koerper_anzahl.

Konventionen der Tabelle: Textparameter sind Literale (`"seite": "+x"`), Verweise auf andere Messungen beginnen mit `=` (`"z": "=tuermchen_spitze - 2.0"`);
`wert` einer Pruefung ist immer eine Formel ueber Messungen und `konstanten`. `status: "widerspruch"` + `widerspruch: "..."` = Quellen uneins (sichtbar,
zaehlt nicht als Fehler). `objekt.json` `zentrierung: "achse"` fuer Generatoren (Achse bei 0,0), `"huelle"` fuer Scans. Nach jedem Lauf zeigt der
Pruefstand "GEAENDERT seit letztem Lauf" (Pruefbericht-Diff): nur die beabsichtigte Eigenschaft darf sich bewegt haben (Lehre F8/F3 aus PROTOKOLL_VALIDATOR).

Messtechnische Fallen (gelernt am Eckturm, Register L2): `section().to_2D()` verschiebt die Ebene -> zuruecktransformieren; Huellbox-Zentrierung
verschiebt die Achse bei Anbauten; Anbauten verschmelzen im Schnitt mit dem Rumpf -> Punktmesser statt Polygonzaehlung.

## 6. Belege je Element und Sichtblatt je Seite (Mechanik fuer die Lehren F5/F6/F9 aus PROTOKOLL_VALIDATOR)
- **Belegregister im Generator:** jedes sichtbare Element meldet sich mit `beleg(seite, element, quelle, **masse)`; der Bau schreibt
  `modelle/<objekt>/elemente.json` (`objekt.json: "elemente"`). Der Pruefstand: Element ohne Quelle = FEHLER (erfundenes Feature, F9);
  Quelle `ANNAHME: ...` ist erlaubt, wird aber bei jedem Lauf als Annahme gelistet; Seiten ohne Foto in `objekt.json/fotos` = UNGEPRUEFT (F5).
  Beim Eintragen der Belege am Martinstor fiel sofort auf, dass Tafel und Adler auf den falschen Seiten sassen - das ist der Zweck.
- **Sichtblatt:** `tools/seiten_audit.py` erzeugt nach jedem Bau `modelle/<objekt>/audit/seiten.jpg` (vier orthografische Ansichten + Draufsicht
  + Foto|Render-Paare aus den angepassten Kameras). `bauen_abnehmen.sh` erzeugt es auch bei rotem Pruefstand. Es wird nicht bewertet, es wird ANGESEHEN -
  jede Seite, nicht nur die fotografierte (F6: Whack-a-Mole entsteht, wenn immer nur eine Flaeche geprueft wird).

## 7. Massstabskette, Messprotokolle, lebender Nachweis, neue Objekte
- **`massstab` je Pruefung** (`dokument` / `lod2` / `laser` / `foto_intern` = bekanntes Mass im selben Foto / `modell` = Massstab aus dem Modell). Der Pruefstand
  listet jede Pruefung mit `modell`-Massstab als zirkulaer: sie belegt die Richtung einer Abweichung, nicht die Zahl. So bleibt sichtbar, was wirklich bewiesen ist.
- **Fotomessungen nur noch als Protokoll:** `tools/foto_mass.py OBJEKT.json FOTO --mess x1 y1 x2 y2 --massstab-px ... --massstab-m L --massstab-von "..."`
  schreibt `messprotokoll/M-<foto>-<nr>.json` + markierten Ausschnitt; die Tabellenzeile verweist mit `protokoll`. "44 px x 1,5 cm" im Kommentar gilt nicht mehr.
- **`MASSNACHWEIS.md`** entsteht bei jedem Pruefstandlauf automatisch aus der Tabelle (Ist/Soll/Quelltyp/Massstab/Status, Belegt-durch, Elemente und Annahmen,
  Seiten ohne Foto, Widersprueche, offene Beobachtungen). Das ist die ehrliche Antwort auf "beweise alle Masse" - und sie veraltet nicht.
- **Kameraanpassung mit Seitenwissen:** Fotos mit bekannter Seite (`objekt.json/fotos/<nr>/seite`) suchen den Azimut nur +-50 Grad um diese Seite
  (`foto_dach_gemeinsam.grenzen`). Ohne das ist jede Silhouettenanpassung an einem symmetrischen Turm um 90 Grad mehrdeutig.
- **Neues Objekt:** `tools/objekt_anlegen.py <objekt> --name ... --hoehe H --hoehe-quelle "..."` legt Ordner, Tabelle, Generator-Rumpf mit `beleg()` an;
  `tools/bauen_abnehmen.sh <objekt>` laeuft sofort. Der ganze Rahmen ist damit nicht an das Martinstor gebunden.

## 8. Echte Meter aus Fotos: Kalibrierung gegen amtliche Anker (Register M)
Fotos liefern Verhaeltnisse; Meter brauchen bekannte 3D-Punkte im Bild. Die gibt es amtlich, ohne Modell:
- `modelle/<objekt>/anker3d.json`: Modellrahmen aus LoD2 (Ursprung = Mitte der Langwand-Endpunkte, +x entlang der Durchfahrt, z ueber DGM1),
  Anker = LoD2-Bodenecken (+-0,3 m), DOM1-Maxima (Tuermchen/Gipfel, +-0,8-1 m, Nadel unsichtbar), Dokumenthoehe (+-3 m), dazu Anker mit
  **freier Hoehe** (`z_frei`: Spitze, Tuermchen, Kranz, First = Goldkugeln, Traufe) deren Lage aus LoD2/Modellgrundriss kommt.
- Je Foto `messprotokoll/K-<foto>.json`: Picks der Anker im Vollbild + Punkte auf LoD2-Senkrechten (Linienanker), `strassenfoto` (Augenhoehe 1,7 +- 0,6),
  `brennweite_px` (EXIF) oder `f_gruppe` (gleiche Kamera in einer Serie).
- `tools/foto_kalibrieren.py` (Einzelkamera: Brennweiten-Scan + PnP + Ausgleich), **`tools/foto_pick_pruefen.py` (PFLICHT: Picks und projizierte Anker im Foto ansehen)**,
  `tools/foto_bundle.py` (mehrere Fotos, freie Hoehen mit Sigma aus der Kovarianz), `tools/foto_mass.py --kamera K-<foto> --ebene x=4.85 --mess ...`
  (Pixel -> Meter auf einer LoD2-Wandebene, Protokoll M-<foto>-<nr>).
- Grenzen (gelernt): Fotos ohne Bodenanker sind in Hoehe/Brennweite mehrdeutig (Kamera "12 m hoch"); weit entfernte Fotos koppeln Brennweite und Abstand;
  Handpicks aus verkleinerten Gittern (+-20 px) sind der Engpass; Georeferenz jeder Nebendatei pruefen (mt_org war der OSM-Knoten, 37 m daneben).
  Erreichbar mit 2-3 guten Strassenfotos: Hoehen +-1-2 m modellfrei, Breiten auf der Wandebene +-0,1-0,3 m.

## 9. Was dieser Rahmen bewusst NICHT verspricht
"Alle Masse bewiesen" gibt es mit offenen Daten nicht: Laser 1 m, Fotos +-5-10 %, Dokumente mit unklarer Bezugshoehe. Der Rahmen liefert
je Mass **Wert, Quelle, Unsicherheit, Status** und verhindert, dass Behobenes zurueckkommt oder eine Quelle fuer etwas herhalten muss,
was sie nicht sehen kann. Das ist die ehrliche Form von "massstabsgetreu".

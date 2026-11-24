# 🚂 Bahn & Anlage: Unterbau, Gleis, Steuerung, Gestaltung  ← [PROJEKT.md](../../PROJEKT.md)
Kapitel: `Doku/konzept/automatisierung-ohne-rc.md` (Bewegung, Höllentalbahn, Magnorail) · `Doku/konzept/bauplan-miniaturwunderland.md` · `Doku/konzept/wartung-risiko.md` · `modelle/WERKZEUGKETTE_WUNDERLAND.md` (Gelände-Bauarten, Lücken)

Angelegt 23.11.2026 auf Nutzerwunsch („eigener Projektbaum für Bahn und Anlage"). Stand: Sammlung + Vorschläge; Schätzungen sind ANNAHMEN, keine Messungen.

## Gilt
- Alleinstellung sind die Gebäude aus Fotos (Pipeline); Bahn, Unterbau, Steuerung, Bäume, Figuren = Kaufteile + Handwerk, nichts neu erfinden [Konzept: „Burggraben ist die Software-Pipeline"; WERKZEUGKETTE_WUNDERLAND Kurzfassung 8].
- Maßstab H0 1:87 (Gebäudekette baut H0) [CLAUDE.md].
- Bewegung wartungsarm: schienengeführt statt freier RC; Magnorail für Straßenfahrzeuge, Modellbahn (z. B. Höllentalbahn H0) für Leben [automatisierung-ohne-rc §2/§4, rc-attraktionen].
- Alte Entscheidung „fahrende N-Bahn → ✗ zu viel Wartung" (08.10., konzept-geschaeft) ist für H0 durch `automatisierung-ohne-rc.md` §2 abgelöst (Gleis sauber + gelegentlicher Lok-Service gilt dort als beherrschbar) - Wartung bleibt Hauptrisiko, siehe Offen.

## Versucht
- (Hirschsprung, 1:160) · Gelände als Laser-Spanten/Egg-Crate, Druck-Hautplatten, Z-Etagen-Stapel → ✓ gebaut (Nutzer 23.11.: „Höhenreliefs haben wir im Hirschsprung schon geschafft") · noch nie für ein H0-Stadtmodul mit Straßen benutzt [WERKZEUGKETTE_WUNDERLAND Kurzfassung 2]
- 24.11. · Malplan je Wand aus dem 1-cm-Wandbild (`tools/malplan.py`, Kettenstufe nach dem Bau, nur Ausgabe: audit/malplan.json/.md/_<wand>.jpg) → ✓ Zonen Putz/Sandstein/Scharten plausibel; Weissabgleich je Wand auf den Putz (von Kries, linear) + eine Farbe je Material: Gebaeude Putz #e0dddc, Sandstein #6c5854 (vorher roh bis #2f241e auf der Schattenseite) · ✗ Wandmalerei/Nachbarhaeuser nicht erkannt, Gruen/Ziegelorange fehlen im Farbbestand (dE ~19-22), Palette-Hex = ANNAHME. Seitennamen aus objekt.json seiten_konvention [Agent 24.11.]
- 08.10. · fahrende N-Bahn als Bewegung → ✗ zu viel Wartung · statisch + Magnet-Drehscheibe [konzept-geschaeft] → für H0 neu bewertet (s. Gilt)

## Offen (Vorschläge, Nutzer entscheidet)
**Unterbau (Profi-Standard)**
- Offene Rahmenbauweise: Holzrahmen + Spanten, Gleistrassen auf Sperrholzstreifen, Landschaft dazwischen (Gaze/Gips oder Styrodur). In Modulen ~1 m, herausnehmbar für Reparatur/Transport. Unsere Gelände-Werkzeuge (Spanten/Hautplatten) passen dazu; Lücke: Modul-Werkzeug Grundplatte + Straßen + Gebäudeplätze + Randverbinder (`modul_platte.py`, WERKZEUGKETTE Vorschlag 1).

- Nutzer 23.11.: Unterbau mit dem Lasercutter maschinisieren („Relief zusammencutten"). Vorschlag (ANNAHMEN, ungemessen): Spanten/Relief 4 mm (Hirschsprung lief mit 3 mm Pappel); Gleistrasse + Modulrahmen NICHT einlagig 4 mm (Durchbiegung → Entgleisen), sondern 2-3 Lagen verleimt (8-12 mm) oder Kastenträger aus gesteckten 4-mm-Teilen, Ecken Fingerzinken. Sculpfun S9 (5,5 W, Bett 410x400) schneidet 3 mm Pappel kalibriert, 4 mm vermutlich mehrere Durchgänge; 1-m-Module aus Teilstücken. Früherer Stand: „eigenen Laser-Park kaufen → ⏸ erst validieren, CO2-Service" (konzept-geschaeft 19.10.).
- Nächster Schritt: Probemodul ~50x50 cm (Kastenrahmen, Steckspanten, Gleistrasse doppellagig) mit dem S9; messen: Durchbiegung unter Last, Schneidzeit → dann Laserkauf entscheiden. Teile per Werkzeug aus Gelände + Gleisplan erzeugen (`modul_platte.py`-Lücke).

- Nutzer 23.11.: großer Laser für viele m² über Nacht? → Sculpfun-Verlängerung S9 auf 410x950 mm (~50-130 $, LightBurn-Größe anpassen) [sculpfun.com, manuals.plus]; Großformat-CO2 130x90/160x100 cm (Vorwissen, Preise ungeprüft). Hersteller einig: NIE unbeaufsichtigt (Holzbrand) [Epilog, Thunder, xTool, Stanford EHS] → lange beaufsichtigte Blöcke + dichtes Packen statt Nachtbetrieb. Vorschlag: erst Verlängerung + Probemodul, dann CO2-Kauf entscheiden.

- ENTSCHIEDEN Nutzer 23.11.: Stufenplan. (1) Kleines Spur-N-Probemodul (1:160) mit dem S9: Unterbau, Malen, Feuchtigkeit, Bahn testen. (2) Erst wenn alles trägt: große Spur (H0) + Laser, der 4 mm in EINEM Durchgang schneidet (CO2), möglichst Open Source/verlängerbar. Verlängerung des Diodenlasers verworfen: Mehrfachdurchgänge vervielfachen die Zeit je Fläche. Hinweis: in N entspricht 0,8 mm Mindestmaß 13 cm Realmaß (H0: 7 cm) → Feindetail-Test fürs Malen nur bedingt übertragbar; Kette kann 1:160 ausgeben (Maßstab beim Export). Recherche offene CO2-Großlaser: später.

**Gleis & Fahrzeuge**
- H0-Gleis eines großen Herstellers (Code 83/100), Weichen per Servo. Fahrzeuge robust wählen (Dauerbetrieb), Ersatzloks im Umlauf. ANNAHME: Verschleißtempo im Dauerbetrieb je Fahrzeug stark verschieden - Nutzerwert „bei MiWuLa nach ~3 Monaten ausgeleiert" unbelegt, zu prüfen.

**Steuerung**
- Digital DCC: Decoder je Lok + Zentrale; Automatikbetrieb über PC-Steuersoftware mit Rückmeldern (Belegtmelder). Kaufkomponenten, nur verdrahten/konfigurieren. Auswahl Zentrale/Software offen (Lizenz/Preis prüfen).
- Wartungsplan: Gleisreinigung, Laufzeitzähler je Lok, Service-Intervalle; Werkstatt-Ecke einplanen.

**Gestaltung / Malen (Nutzer 23.11.: „das Malen ist für mich das Kritischste")**
- Material vorhanden: Army Painter Matt Grey (Grundierung), Sealant, Homy Arty Mattlack; OBI-Farben nur als Lasur [Memory user-malmaterial-bestand].
- Putz: grau grundieren → gebrochenes Weiß/Hellocker dünn in Schichten → graubraune Lasur (Wash) → Mattlack.
- Sandstein-Quader: Rotbraun → dunkle Lasur in die Fugen → Trockenbürsten heller Ton (Relief aus der Kette trägt das).
- Holz: dunkelbraun, längs mit wenig hellerem Braun (Maserung). Fenster: Rahmen fein, Scheiben dunkel/glänzend absetzen.
- Erst an Fehldrucken/Probewänden üben (2-3 Stück). Alternative für flache Putzfassaden: Abziehbild aus dem 1-cm-Fassadenbild (`fassade_decal.py`, WERKZEUGKETTE Vorschlag) - offen.
- Vorschlag: Probedruck eines Südwand-Stücks Schwabentor (Quader) + Probe-Bemalung, sobald die Kette ein gutes Modell liefert - nur auf Nutzerwunsch drucken.

**Zahlen zum Abschätzen (ANNAHMEN)**
- Schwabentor H0: ~42 cm hoch, ~12 cm Grundfläche → 2-3 Höhenstücke (Druckhöhe ~22-25 cm), Nähte an Gesimsen.
- Je Gebäude: Druck 1-2 Tage nebenher, Malen ~1 Abend.

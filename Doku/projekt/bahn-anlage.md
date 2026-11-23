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
- 08.10. · fahrende N-Bahn als Bewegung → ✗ zu viel Wartung · statisch + Magnet-Drehscheibe [konzept-geschaeft] → für H0 neu bewertet (s. Gilt)

## Offen (Vorschläge, Nutzer entscheidet)
**Unterbau (Profi-Standard)**
- Offene Rahmenbauweise: Holzrahmen + Spanten, Gleistrassen auf Sperrholzstreifen, Landschaft dazwischen (Gaze/Gips oder Styrodur). In Modulen ~1 m, herausnehmbar für Reparatur/Transport. Unsere Gelände-Werkzeuge (Spanten/Hautplatten) passen dazu; Lücke: Modul-Werkzeug Grundplatte + Straßen + Gebäudeplätze + Randverbinder (`modul_platte.py`, WERKZEUGKETTE Vorschlag 1).

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

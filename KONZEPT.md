# RC-Park Freiburg — Konzept

> **Miniatur-Wunderland zum Selbersteuern.** Eine wetterunabhängige Indoor-Erlebniswelt,
> in der Besucher RC-Fahrzeuge, -Schiffe und -Flugobjekte **selbst steuern** —
> statt nur zuzuschauen.

## 1. Die Idee in einem Satz

In Hamburg **schaut** man der größten Modellbahn der Welt zu. In Freiburg **fährt, fliegt
und schippert** man selbst — durch einen Miniatur-Schwarzwald, über ein Flottenbecken mit
Flugzeugträger und durch eine Flughalle voller Helikopter und Drohnen.

## 2. Warum Freiburg, warum jetzt

| Faktor | Beleg |
|---|---|
| **Tourismusstadt** | 2,17 Mio Übernachtungen (2024, +19 % ggü. 2019), ~1 Mio Gäste/Jahr |
| **Grenznahe Kaufkraft** | 27–29 % ausländische Gäste; Top-Herkunft **Schweiz** & **Frankreich** |
| **Schlechtwetter-Lücke** | Freiburg hat viel Outdoor (Münster, Schauinsland, Schwarzwald) — aber wenig **Indoor-Familienziel** für Regen/Winter |
| **Bewiesenes Modell** | Miniatur Wunderland Hamburg: >1 Mio Besucher, **42,7 Mio € Umsatz**, 400 MA |
| **Nachfrage-Beleg Indoor-RC** | Anlagen wie RC-Glashaus (2.500 m²) zeigen: wetterunabhängiges RC zieht |

**Kernthese:** Freiburg ist outdoor-gesättigt, aber indoor-unterversorgt. Ein Schlechtwetter-
Magnet mit Mitmach-Charakter füllt genau die Lücke — und fängt den riesigen
Tagestourismus aus der Dreiländer-Ecke ab.

## 3. Alleinstellung (USP) gegenüber Miniatur Wunderland

1. **Interaktiv statt passiv** — der Gast ist Kapitän/Pilot/Fahrer, nicht Zuschauer.
   Das erzeugt Verweildauer, Wiederkehr und eine höhere Zahlungsbereitschaft über Jetons.
2. **Regionale Identität** — ein Miniatur-Schwarzwald mit Münster, Schauinsland und
   Höllental erzeugt den Wiedererkennungs-Effekt für Touristen.
3. **Breite über Medien** — Boden (Autos, Trucks, Crawler), **Wasser** (Flotte +
   Flugzeugträger) und **Luft** (Heli, Flächenflieger, FPV-Drohnen) in einem Haus.
4. **Event- & Community-fähig** — Rennliga, FPV-Racing, Firmen-Events, Kindergeburtstage,
   Vereinsabende. Macht aus Laufkundschaft Stammkundschaft.

## 4. Die Attraktionen

Details und Investitionssummen je Attraktion liegen maschinenlesbar in
[`attraktionen/*.json`](attraktionen/) und fließen automatisch in den Businessplan.

| # | Attraktion | Medium | Wow | Kernnutzen |
|---|---|---|---|---|
| 🚢 | **Flottenbecken & Flugzeugträger** | Wasser | ★★★★★ | Foto-/Social-Magnet, Aushängeschild |
| 🚁 | **Flughalle (Heli/Flieger/Drohnen)** | Luft | ★★★★★ | Fliegen bei jedem Wetter, FPV-Racing |
| 🌲 | **Miniatur-Schwarzwald** | Schau+Boden | ★★★★★ | Regionale Identität, verbindet Schauen & Fahren |
| 🚜 | **RC-Baustelle & Truck-Spedition** | Boden | ★★★★ | Haptisch, längste Verweildauer bei Kindern |
| 🏎️ | **RC-Rennstrecke & Zeitmessung** | Boden | ★★★★ | Wettkampf, Gruppen-/Event-Treiber |
| 🪨 | **Offroad- & Crawler-Parcours** | Boden | ★★★★ | Geschicklichkeit, fesselt auch Ältere |
| 🧒 | **Mini-Fahrschule & Kinderland** | Kinder | ★★★ | Niederschwelliger Familien-Einstieg |
| 🍔 | **Gastro, Shop & Schau-Werkstatt** | Service | ★★ | Margenstärkstes Element, Zusatzumsatz |

**Gesamt-Attraktionsfläche:** ~1.740 m² Erlebnis + Gastro/Shop/Service + Verkehrsflächen
→ Zielhalle **~2.000 m²**.

## 5. Zielgruppen & Preislogik

- **Familien** (Kern): Tagesausflug bei Regen/Winter, 2–4 h Verweildauer.
- **Touristen** (Schweiz/Frankreich/Fernreisende): Schlechtwetter-Alternative zum Münster.
- **Technik-/Hobby-Community**: Vereine, Liga-Betrieb, FPV-Szene, Abendnutzung.
- **Firmen & Gruppen**: Team-Events an der Rennstrecke / im Drohnen-Parcours.

**Erlösmodell dreistufig:** (1) Eintritt inkl. Grund-Fahrzeit, (2) **Jetons** für Extra-
Fahrzeit an Premium-Stationen (Träger, FPV, Rennen), (3) margenstarke Nebenerlöse
(Gastro, Shop, Events). Siehe [`businessplan.html`](businessplan.html).

## 6. Wirtschaftlichkeit (Kurzfassung)

Bei **110.000 Besuchern/Jahr** (≈ 11 % der Freiburger Jahresgäste):

- Umsatz **~3,6 Mio €** · Gewinn vor Steuer **~0,46 Mio €** (Marge ~13 %)
- Investition **~2,9 Mio €** (davon ~1,7 Mio € Attraktionen)
- **Break-even bei ~93.000 Besuchern** → ~15 % Sicherheitspuffer

Alle Annahmen sind in [`annahmen.json`](annahmen.json) editierbar; der Businessplan
rechnet live mit. Die Zahlen sind begründete Schätzungen, keine testierte Planung.

## 7. Risiken & Gegenmaßnahmen

| Risiko | Gegenmaßnahme |
|---|---|
| **Saisonalität** (Sommer schwächer) | Positionierung als Schlechtwetter-/Winterziel, Abend-/Event-Betrieb, Ferienprogramme |
| **Verschleiß der RC-Flotte** | Eigene Schau-Werkstatt, robuste Einsteigermodelle, Ersatzteil-Budget eingeplant |
| **Hohe Anfangsinvestition** | Modularer Aufbau (Attraktionen gestaffelt eröffnen), Mix EK/FK |
| **Personalintensiver Betreuungsbedarf** | Self-Service-Stationen + Jeton-Automaten, saisonale Aushilfen |
| **Abhängigkeit vom Tourismus** | Lokale Stammkundschaft über Liga/Community/Geburtstage aufbauen |

## 8. Nächste Schritte

1. Standortsuche konkretisieren (siehe [`standort.md`](standort.md)).
2. Attraktions-Prototyp (Rennstrecke + Becken) als Pop-up testen → reale Zahlungsbereitschaft messen.
3. Gestaffelter Finanzierungsplan (EK, Förderung, Bank) auf Basis des Businessplans.
4. Genehmigungen: Versammlungsstätte, Wasserbecken-Hygiene, Brandschutz, Fluglärm-/Netzkonzept Halle.

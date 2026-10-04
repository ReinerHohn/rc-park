# Wahrzeichen: maximales Detail + Beleuchtung (der Wow-Hebel)

> Für die **Hero-Wahrzeichen** (Freiburger Münster, Stadttore) gilt nicht mehr
> „schnell/sweet spot", sondern **Detail-first + Licht**. Beleuchtung ist der stärkste
> einzelne Wow-Hebel — ein hinterleuchteter gotischer Turm mit leuchtenden Buntglasfenstern
> schlägt jedes unbeleuchtete Modell.
>
> Für Masse/Füller (Wald, Dorfhäuser) bleibt die schnelle FDM-Farm aus
> [`3d-druck-strategie.md`](3d-druck-strategie.md). Dies ist der **zweite Track**.

## Zwei-Track-Strategie

| Track | Ziel | Technik |
|---|---|---|
| **A — Masse** | viele Füller schnell | FDM-Farm, einfarbig, Vase-Mode, grobe Düse |
| **B — Wahrzeichen** | maximales Detail + Licht | **Resin** (MSLA) + LED-Beleuchtung, als Bausatz |

## Max. Detail: Resin vs. FDM

| | Resin (MSLA) | FDM |
|---|---|---|
| Auflösung | 8K–16K, Schicht ab 0,025 mm | Düse 0,4 mm, Schicht ab ~0,1 mm |
| Feindetail (Maßwerk, Fensterrahmen) | **scharf, echte Elemente** | verrundet alles < 0,5 mm |
| XY-Feinheit | ~30× feiner als 0,4-mm-Düse | grob |
| Kosten | ~50–80 €/L + Waschen/UV-Härten | ~15–25 €/kg |
| Haltbarkeit | spröder | zäher |
| Bauvolumen | klein → **Bausatz nötig** | größer |

**Empfehlung:**
- **Resin** für den filigranen Münsterturm, Maßwerk, Figuren, Stadttor-Details.
- **FDM** bleibt für Grundkörper/Massen (günstiger, größer, zäher).
- **Hybrid** ist oft am besten: großen Grundkörper in FDM, **Detail-Aufsätze** (Turmhelm,
  Fensterbögen, Fialen) in Resin — zusammenstecken.
- FDM-Detail-Maximum (wenn kein Resin): **0,2-mm-Düse, 0,08–0,12-mm-Schichten** — besser,
  aber nicht Resin-Niveau.

## Beleuchtung — so wird's der extreme Hebel

### 1. Lichtdurchlässige Wände
- Außenhaut aus **transluzentem PETG** (klarer als PLA, kein Haze). Lichtdurchlass über die
  **Wandstärke** steuern: dünner = heller Glow, dicker = sanfter.
- Opake Außenwände + **ausgesparte Fensteröffnungen**, in die leuchtende Panels kommen.

### 2. Buntglasfenster = Lithophane / farbige transluzente Panels  ← HIER lohnt Mehrfarbe
> Erinnerung: Mehrfarbdruck (AMS) lohnt für Masse NICHT. **Ausnahme: die winzigen
> Kirchenfenster.** Kleine Fläche, riesiger Effekt — der eine Ort, wo der Aufwand sich zahlt.
- Fenster als **farbige Lithophane** (Graustufen-/Farb-Translucent-Panels) drucken, die im
  Gegenlicht als Buntglas aufleuchten.
- Fertige Elektronik dafür: **Bambu Lithophane LED Backlight Board Kit** (48 LEDs).

### 3. Der durchbrochene Münsterturm, hinterleuchtet = das Killer-Feature
Der 46-m-Turm ist komplett durchbrochenes Steinmaßwerk. Von innen mit warmweißer LED oder
Lichtleitfasern beleuchtet wirkt das Spitzenwerk gegen das Licht spektakulär — das
Alleinstellungsbild des ganzen Dioramas.

### 4. LED-Technik
| Option | Wofür | Hinweis |
|---|---|---|
| **Vorverdrahtete warmweiße Modellbahn-LEDs** (12 V, 3528 SMD, mit Vorwiderstand) | realistischer Innen-Glow | Faller/Woodland/Micro-Structures; „warmweiß" = Kerzenlicht-Look |
| **LED-Pucks / Fairy-Lights** | diffuse Grundbeleuchtung im Hohlkörper | einfach, günstig |
| **Lichtleitfasern** | punktgenaue Lichtpunkte (Turmspitze, Fensterrosette) | aufwändiger, sehr edel |
| **Adressierbare WS2812/Neopixel + Controller** | Tag-Nacht-Show, Farbwechsel | passt zum Diorama-Konzept „Tag-Nacht-Lichtwechsel"! |

### 5. Diffusion & Sauberkeit
- Innen mattweiß streichen oder transluzentes Inlay → gleichmäßiger Glow statt LED-Punkte.
- Kabel durch die Bodenplatte nach unten, Verteilung unter dem Diorama.

### 6. Sicherheit
- Nur **Kleinspannung** (5–12 V, USB-Netzteil), Vorwiderstände nicht vergessen.
- Keine Netzspannung im Modell.
- Wärme beachten: PLA erweicht ab ~60 °C → LEDs mit Abstand/geringer Leistung, oder
  **PETG** für beleuchtete Teile (hitzefester).

## Rezept: beleuchtetes Freiburger Münster (Bausatz)

1. **Grundkörper** (Langhaus + Turm) als plattengroße FDM-Teile, Außenwände opak,
   Fensteröffnungen ausgespart.
2. **Fenster** separat als farbige Lithophane/transluzente Panels (Resin oder Mehrfarb-FDM),
   von innen einsetzen.
3. **Turmhelm** (durchbrochen) in Resin für scharfes Maßwerk, hell/transluzent → von innen
   mit warmweißer LED/Fiberglas beleuchten.
4. **LEDs** im Hohlkörper (warmweiß für Grundglow + optional WS2812 für Tag-Nacht-Show),
   Kabel durch die Bodenplatte, 5–12 V USB.
5. **Diffusion** innen mattweiß, außen ggf. Wash/Drybrush für Steinoptik.

## Fertige beleuchtete/detaillierte Modelle als Vorlage

- **Diablo Cathedral – Detailed Light-Up Miniature** (MakerWorld, gratis) — zeigt LED-Board
  + farbige PLA-„Gels": https://makerworld.com/en/models/644630-diablo-cathedral-detailed-light-up-miniature
- **Stained Glass Tower Night Lamp (LED Lamp 001 Kit)** (MakerWorld, gratis):
  https://makerworld.com/en/models/1837838-stained-glass-tower-night-lamp-led-lamp-001-kit
- **Gothic Arch Light: Luminous Hourglass** (MakerWorld) — Filigran + Hohlbasis für LED-Pucks:
  https://makerworld.com/en/models/2212098-gothic-arch-light-luminous-hourglass-lamp
- **Gothic Lithophane Light** (Printables): https://www.printables.com/model/22443-gothic-lithophane-light
- **Bambu Lithophane LED Backlight Board Kit** (fertige Elektronik, 48 LEDs):
  https://us.store.bambulab.com/products/lithophane-led-backlight-board-kit
- **Instructables: 3D Printed Stained Glass Light Decoration** (Technik-Tutorial):
  https://www.instructables.com/3D-Printed-Stained-Glass-Light-Decoration/
- Für den detaillierten Münster selbst → **Gambody** (feine Gotik, resin-tauglich):
  https://www.gambody.com/stock/freiburg-minster-architecture-stl

## Einordnung im Projekt
Die Beleuchtung koppelt direkt an das Diorama-Konzept „**Tag-Nacht-Lichtshow alle 15 Minuten**"
(siehe [`KONZEPT.md`](KONZEPT.md), Attraktion Miniatur-Schwarzwald): abends gehen in Münster,
Fenstern und Dörfern die Lichter an — das ist der emotionale Höhepunkt der Schaulandschaft.

# Sweet Spot: Software + Hardware für geile, genaue Modelle

> Frage: Welche Kombi aus **Hardware + Software** bringt mich mit bestem Preis-Leistungs-
> Verhältnis zu **geilen, genauen** Freiburg-Modellen — als verkaufbares Produkt?
> Antwort: Die Grenze ist **nicht** Genauigkeit (Photogrammetrie reicht locker), sondern
> **Abdeckung** (Dächer/Türme = Drohne) und **Schärfe am Hero** (Resin). Alles andere ist gratis.

## Die Fertigungskette (Capture → Compute → Print) + was kostet was

| Stufe | Werkzeug | Status | Kosten |
|---|---|---|---|
| **Capture Boden** | Handy + **RealityScan** (Epic) | gratis App, Handy hast du | **0 €** |
| **Capture Luft** (Dächer/Türme) | **Drohne sub-250 g** | neu | **220–760 €** |
| **Fusion/Mesh** | **RealityCapture** (jetzt gratis) auf RTX-PC | RTX hast du (`scan-setup/`) | **0 €** |
| **Mesh-Feinschliff** | **Blender** (Kitbash, Spitzen schärfen) | gratis | **0 €** |
| **Druck Masse** | **Prusa MK4S** (FDM, hohl) | hast du | **0 €** |
| **Druck Hero scharf** | **Resin-MSLA** | neu | **190–450 €** |
| **Resin-Slicing** | Chitubox/Lychee (gratis) | gratis | **0 €** |

**→ Alles Software ist gratis.** Investition steckt nur in **Drohne + Resin-Drucker.**

## Hardware-Sweet-Spots (2026-Preise)

### Resin-Drucker (für scharfe Hero-Wahrzeichen)
| Modell | Auflösung / Bauraum | Preis | Urteil |
|---|---|---|---|
| Anycubic Photon Mono 4 | 10K, klein | ~190 € | günstigster Einstieg, kleine Heroes |
| **Elegoo Saturn 4 Ultra** | **12K, groß** | **~450 €** | **★ Sweet Spot** — gestochen scharf + großer Bauraum für Türme |
| Elegoo Saturn 3 Ultra | 12K, groß | ~350 € | Preis-Tipp, fast gleich |

### Drohne (für Dächer/Türme = Abdeckungs-Gamechanger)
| Modell | Sensor | Preis | Urteil |
|---|---|---|---|
| **DJI Mini 4K** | 48 MP | **~220 €** | **★ Sweet Spot** — reicht für Modell-Photogrammetrie, keine Registrierungs-Hürde |
| DJI Mini 4 Pro | 48 MP + Hindernis | ~760 € | besser/sicherer, wenn Budget da |
| DJI Mini 5 Pro | 1″ 50 MP | ~800 € | beste Meshes, Overkill fürs Modell |

> **Dedizierte Handscanner (Revopoint/Creality) bringen hier NICHTS** — die sind für kleine
> Objekte, nicht für Gebäude. Gebäude = Foto/Drohnen-Photogrammetrie.

## Die drei Stufen (wähle nach Budget)

| | **Stufe 0 — jetzt** | **★ Stufe 1 — Sweet Spot** | **Stufe 2 — Max** |
|---|---|---|---|
| Capture | Handy RealityScan | + **DJI Mini 4K** | + DJI Mini 4 Pro |
| Fusion | RealityCapture/RTX | RealityCapture/RTX | RealityCapture/RTX |
| Hero-Druck | FDM 0,12 mm + schleifen | + **Elegoo Saturn 4 Ultra** | + großer Resin |
| **Neu-Invest** | **0 €** | **~670 €** | **~1.200 €** |
| Qualität | gut (Heroes weich) | **sehr gut, scharf, Dächer drauf** | Profi |
| Für Produkt? | Prototyp | **✅ verkaufsreif** | Overkill |

**★ Empfehlung: Stufe 1 (~670 €).** Handy + Mini 4K + RTX-RealityCapture (gratis) + MK4S +
Saturn 4 Ultra. Das ist der Punkt, ab dem die Modelle **scharf, vollständig und verkaufbar**
sind — mehr Geld bringt nur noch Feinheiten.

## Warum das ein Produkt ist
- **Einmal-Invest ~670 €**, Software 0 €, Materialkosten pro Modell 1–3 €.
- **Resin-Hero** 8–20 € verkaufbar (Marge hoch), **FDM-Bausatz** flach verpackt versandfähig.
- Pipeline ist **wiederholbar** für jedes Wahrzeichen/jede Stadt → skaliert.

## Startreihenfolge
1. **RealityScan** aufs Handy, Test-Scan (heute, 0 €).
2. **Saturn 4 Ultra** bestellen → Münster-Scan als ersten **scharfen Resin-Hero** drucken.
3. **DJI Mini 4K** → Dächer/Türme nachscannen (⚠️ Drohnen-Recht Innenstadt/Münster prüfen).
4. **RealityCapture** auf dem RTX-Rechner einrichten (`scan-setup/` von Meshroom umstellen).
5. Boden+Luft fusionieren → Blender-Feinschliff → Resin → bemalen → LED → Diorama.

Bezug: [`datenquellen.md`](datenquellen.md) (Scan-Apps/Quellen),
[`plan-wahrzeichen-drucken.md`](plan-wahrzeichen-drucken.md) (Druck/Finish),
[`scan-setup/`](scan-setup/) (RTX-Pipeline).

Preise: 2026-Marktstand (Elegoo/Anycubic, DJI), Richtwerte.

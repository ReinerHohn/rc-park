# 3D-Druck-Strategie: Dioramen & Gebäude schnell als Bausatz

> Ziel: **extrem schnell viele Modellgebäude** für den Miniatur-Schwarzwald
> (z. B. Freiburger Münster) produzieren — hohl / als Bausatz, Material sparen.

## TL;DR

1. **Mehrfarb-Druckwerk (AMS/MMU, eine Düse) lohnt für dieses Ziel NICHT.** Es ist
   langsamer und verschwendet Filament. Lieber das Geld in **mehr Drucker** stecken.
2. **Schnellster Weg = Druckfarm** (2–4 günstige, schnelle CoreXY-Drucker parallel),
   jeder einfarbig.
3. **Pro Modell:** Vase-Mode / hohl, 0,6-mm-Düse, 0,3-mm-Schichten, 0–5 % Infill.
4. **Riesen (Münster) in plattengroße Teile schneiden → Bausatz**, parallel drucken, kleben.
5. **Farbe** über getrennt gedruckte Teile in verschiedenen Filamenten **oder** Lackieren
   (Grundierspray + Wash/Drybrush) — nicht über Düsen-Farbwechsel.

## ⭐ Der Sweet Spot: groß + detailliert + schnell *zugleich*

Die drei Ziele widersprechen sich auf **einem** Druck / **einer** Maschine:
Detail will fein & langsam, Speed will grob, Groß passt nicht auf die Platte.
Der Trick: **nicht in einem Druck lösen, sondern aufteilen** — dann bekommst du alle drei.

1. **Modularer Bausatz** → löst „groß" UND macht Parallelität erst möglich. Großes Modell
   in plattengroße Module schneiden (Pass-Stifte an die Schnittflächen).
2. **Detail-Zoning (LOD):** hochauflösend nur, wo man hinschaut — **sichtbare Fassaden,
   Türme, Maßwerk**. Rückwände, Basis, Innenwände grob & schnell. Detail kostet nur dort Zeit,
   wo es wirkt.
3. **Parallele Druckfarm** → macht das *Gesamtwerk* schnell, obwohl Detail-Teile langsam sind.
   Wall-clock ≈ langsamstes Modul, **nicht** Summe aller Teile. Das ist der eigentliche
   Speed-Hebel bei großen Modellen.
4. **Verfahren je Modul:** Resin oder 0,2-mm-FDM für die filigranen Hero-Teile (Turmhelm,
   Maßwerk), schnelles 0,6-mm/0,3-mm-FDM für die Masse-Module.
5. **FDM-Maschinen-Sweet-Spot:** schneller CoreXY (Bambu P1S/X1C, Prusa Core One, Creality K)
   mit **0,4-mm-Düse @ 0,12–0,16 mm Schicht** = bester Detail/Speed-Kompromiss *ohne*
   Resin-Aufwand. Separate **0,2-mm-Düse** nur für die wenigen Hero-Detail-Teile.

> **Faustregel:** „Ein großes, detailreiches Modell = viele kleine, je einzeln optimierte
> Module, parallel gedruckt." Jedes Modul maximiert **eine** Achse — das Gesamtergebnis hat
> alle drei. Details zu Detail-Verfahren & Licht: [`beleuchtung-detail.md`](beleuchtung-detail.md).

## Warum kein Single-Nozzle-Mehrfarbdruck

Bei AMS/MMU teilen sich alle Farben **eine Düse**. Jeder Farbwechsel braucht einen
Retract-Load-Purge-Zyklus:

| Effekt | Größenordnung |
|---|---|
| Zeit je Farbwechsel | ~30–45 s |
| Abfall je Farbwechsel | ~2–5 g in den Purge-Tower |
| Tower-Anteil bei vielen Wechseln | **20–40 % des Gesamtfilaments** |
| Reales Beispiel (Pinguin) | einfarbig 9,3 g / 1h14 → mehrfarbig **61,9 g / 6h+** |

→ Für „viele Modelle schnell" ist das der falsche Hebel. Ausnahme: einzelne Schaustücke
oder Schilder, bei denen Farbe im selben Teil wirklich gebraucht wird.

**Purge reduzieren** (falls doch Mehrfarbe nötig): Flush-Volumen senken, ähnliche Farben
gruppieren, „Flush to infill/support" aktivieren, höhere Schichthöhe. Spart >60 % Spülung.

## Die drei Tempo-Hebel

### 1. Parallelität (Druckfarm) — größter Hebel
Durchsatz skaliert linear mit der Anzahl Drucker. 3 Drucker = 3× Modelle/Tag. Günstige,
schnelle CoreXY (Bambu A1 / A1 mini / P1S-Klasse, Creality K-Serie). Zwei einfache Drucker
schlagen einen teuren Mehrfarb-Combo bei reinem Durchsatz.

### 2. Geometrie- & Slicer-Tricks pro Modell
- **Vase-Mode (Spiralize):** hohle Einwand-Drucke, eine durchgehende Spirale, keine
  Retracts, **bis 50 % schneller**. Ideal für Türme, Spitzen, einfache Baukörper
  (20-cm-Turm in ~3,5 h). Voraussetzung: durchgehende Außenkontur, keine Brücken/Overhangs.
- **Große Düse + hohe Schicht:** 0,6-mm-Düse, 0,28–0,32-mm-Schichten. Bei Diorama-Maßstab
  (1:87 … 1:250) kaum sichtbarer Detailverlust, aber vielfaches Tempo.
- **Hohl & wenig Infill:** 2 Wände, 0–5 % Gyroid-Infill. Gebäude tragen nichts.
- **Supportfrei orientieren/schneiden:** Dächer separat, Fassaden flach legen.

### 3a. ⭐ Flat-Wall-Bauweise (flache Wände → zusammenkleben)

**Der schnellste Weg für große Gebäude.** Statt das Haus als aufrechten Block zu drucken,
jede **Wand flach liegend** als dünne Platte drucken und zum Hohlkörper zusammenbauen.

Warum es gewinnt:
- **Höhe = Zeitkiller.** 200-mm-Turm aufrecht ≈ 1000 Schichten nacheinander. Dieselbe Wand
  flach liegend ≈ 10–15 Schichten → Bruchteil der Zeit.
- **Kein Support** (Platte liegt satt auf), **hohl = kaum Material**, innen beleuchtbar.
- **Fassaden-Detail besser**: Fenster/Maßwerk/Relief liegen in der feinen XY-Ebene statt in
  groben Z-Schichtlinien.
- **Parallel**: 4 Wände auf 4 Druckern gleichzeitig.

Eckverbindungen (von einfach → stabil):
1. **Stumpf + Kleber** (Sekundenkleber/Epoxid) — am einfachsten.
2. **45°-Gehrung** an den Wandkanten — saubere Ecke ohne sichtbare Stirnfläche.
3. **Steck-Tabs / Nut-Feder** an den Kanten — selbstausrichtend, kein Verrutschen.
4. **Innen-Eckpfosten** (kleine L-Profile) zum Ankleben — maximale Stabilität + Ausrichtung.
Boden-/Deckplatte gibt zusätzlich Steifigkeit; Fensteröffnungen direkt in die Platten
aussparen (für beleuchtete Lithophane-Fenster, siehe [`beleuchtung-detail.md`](beleuchtung-detail.md)).

Faustregel: **winzige Teile** (Mini-Türmchen) ruhig aufrecht; **alles ab Haus-Größe** als
Flat-Wall-Bausatz.

### 3c. Detail-Applikation (Detail aufkleben)

Wenn der Grundkörper glatt ist (einfaches Modell oder glatter Scan): **feine Zierteile
separat drucken und aufkleben**, statt alles hochauflösend zu drucken. Detail genau dort,
wo das Auge hinschaut.

- **Weg A — fertige Elemente:** Rosette, Maßwerkfenster, Portalbogen, Friese, Fialen als
  einzelne STLs **flach** (sehr fein) drucken, mit Sekundenkleber auf den Grundkörper setzen.
  Quellen: „gothic window / tracery / rose window" auf Printables/Cults (z. B. Gothic Rose
  Window von printbyPW — FDM flach top, Resin ultra-scharf).
- **Weg B — Foto → Relief:** Fassaden-Foto per Heightmap-Tool (3D Relief Generator,
  Image-to-Heightmap, Blender „Displace") in eine Relief-Platte wandeln und aufkleben.
  Caveat: Höhe kommt aus Bild-Helligkeit, nicht echter Form → gut für Textur, Weg A sauberer.

Grundkörper schnell/grob, Detail-Overlays fein (0,12 mm oder Resin). Kombiniert ideal mit der
Flat-Wall-Bauweise.

### 3b. Bausatz-Schnitt für große Modelle
Ein großes Münster passt auf keine Druckplatte und soll laut Vorgabe **nicht voll**, sondern
als Bausatz gedruckt werden:
- Im Slicer (Bambu Studio „Cut object", PrusaSlicer „Cut", oder Blender/Meshmixer) in
  plattengroße, flach liegende Teile zerlegen.
- Pass-Stifte / Nut-Feder an die Schnittflächen setzen → sauberes Zusammenstecken.
- Teile **parallel** auf der Farm drucken, mit Sekundenkleber/Epoxid fügen.
- Vorteil: supportfrei, materialsparend (hohl), beliebig groß skalierbar.

## Empfohlene Druck-Settings (Diorama-Architektur)

| Parameter | Wert | Grund |
|---|---|---|
| Material | PLA (ggf. PLA+) | billig, steif, einfach, ideal für Deko |
| Düse | 0,6 mm | Tempo, robuste Wände |
| Schichthöhe | 0,28–0,32 mm | Tempo, Detail bei Maßstab ok |
| Wände | 2 | hohl, spart Material |
| Infill | 0–5 % Gyroid | Gebäude tragen nichts |
| Vase-Mode | wo Geometrie es zulässt | max. Tempo + min. Material |
| Druckgeschwindigkeit | 200–300 mm/s (CoreXY) | Farm-Durchsatz |
| Supports | durch Schnitt/Orientierung vermeiden | spart Zeit + Nacharbeit |

## Farbe ohne AMS

1. **Teile in verschiedenen Filamentfarben** drucken und zusammenstecken
   (Münster: sandstein-/ziegelrot + grüne Turmhelme) → null Purge-Abfall.
2. **Grundieren + bemalen:** Rattle-Can-Primer, dann Wash (dünne dunkle Farbe in die Fugen)
   + Drybrush (helle Farbe auf Kanten). Sieht bei Architektur plastischer aus als AMS.

## Lohnt ein Mehrmaterial-Druckwerk? — Entscheidungshilfe

| Setup | Für dein Ziel |
|---|---|
| **Single-Nozzle + AMS/MMU** (Bambu AMS, Prusa MMU) | ❌ langsam + Abfall; nur für kleine Schauteile |
| **Mehrere Einzeldrucker (Farm)** | ✅ bester Durchsatz pro € |
| **IDEX / Tool-Changer** (Prusa XL, IDEX-Drucker) | 〰️ separate Düsen = wenig Purge, aber teuer; nur bei echtem Mehrfarb-Serienbedarf |

**Faustregel:** Budget zuerst in **Drucker-Anzahl + einfarbige Effizienz** stecken, Farbe
über getrennte Teile oder Lack. Mehrfarb-Hardware erst, wenn ein konkretes Schaustück es
wirklich verlangt.

## Modellquellen

### Freiburger Münster (fertig druckbar)
- **Printables – „Freiburg Minster" (depth_craft3d), 1:250, gratis, inkl. 3MF** —
  https://www.printables.com/model/1831701-freiburg-minster  *(bester Startpunkt)*
- Cults3D – Freiburger Münster (reduzierte Details, klein druckbar) —
  https://cults3d.com/en/3d-model/architecture/freiburger-munster-munster-unserer-lieben-frau-katholische-stadtpfarrkirche-von-freiburg-im-breisgau
- Gambody – Freiburg Minster (detaillierte Gotik-STL) —
  https://www.gambody.com/stock/freiburg-minster-architecture-stl
- Sketchfab – Photogrammetrie-Scan (LAD BW), als Mesh-Basis zum Selbstschneiden —
  https://sketchfab.com/3d-models/freiburger-munster-f0f4d479997f48659658fafebc14f90c

### Weitere Gebäude / Dioramen
- **Modellbahn-Gebäude** (H0 1:87, TT, N): Fachwerkhäuser, Kirchen, Bahnhöfe, Höfe —
  Printables/Cults/Thingiverse, viele als steckbare Bausätze.
- **Wargaming-Terrain** (28 mm): robuste, modulare Gebäude, oft hohl & schnell druckbar.
- **Parametrische Gebäude-Generatoren** (z. B. OpenSCAD-/Web-Tools) für beliebig viele
  Häuser-Varianten mit einheitlichem Stil.

## Durchsatz-Überschlag (grob)

Annahme: 4 Drucker, Diorama-Haus ~80–150 g, bei obigen Settings ~2–4 h/Stück.
→ pro Drucker ~4–6 Häuser/Tag → **Farm ~16–24 Häuser/Tag**, ~100+/Woche.
Ein großes Münster als Bausatz (z. B. 6–10 Teile) ist in ~2–3 Tagen über die Farm fertig.

> Zahlen sind Richtwerte und hängen stark von Modellgröße, Maßstab und Drucker ab.

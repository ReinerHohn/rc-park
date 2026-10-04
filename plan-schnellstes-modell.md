# Schnellster Weg zu einem detaillierten Freiburg-Modell

> Frage: Teile drucken **und** gerade Flächen mit Laser-Cutter schneiden — oder wie?
> **Antwort: Ja, Hybrid-Fertigung — aber nach Geometrie aufgeteilt.** Laser schneidet nur
> **flach (2,5D)**; Dächer, Türme und das Münster sind **3D** → die müssen **gedruckt/gescannt**
> werden. **Laser = Beschleuniger für die Flächen, Druck = Körper.**

## 1. Die Aufteilung (jedes Teil mit dem schnellsten Verfahren)

| Bauteil | Verfahren | Warum |
|---|---|---|
| Dächer, Türme, Giebel (LoD2-Form) | **FDM-Druck, hohl** (0 % Infill, 2 Perimeter) | Schrägen/Krümmung kann der Laser nicht |
| Münster + Hero-Wahrzeichen (scharf) | **Resin-Druck** oder **Scan** (hast du: 750K-Poly) | maximale Schärfe am Blickfang |
| Grundplatte / Kachel-Böden | **Laser: MDF/Acryl** | großflächig, maßhaltig, günstig, in Minuten |
| Straßenraster, Plätze, **Bächle** | **Laser-Gravur/-schnitt** | georeferenziert in **einem** Durchgang |
| Gerade Blockfassaden (falls Block-Stil) | **Laser: Acryl/MDF** | flach = Laser schlägt Druck klar |
| Fenster/Ornament-Applikation | **Laser oder Dünndruck** + aufkleben | Detail ohne Vollkörper |
| Schutzhaube (kindersicher) | **Laser: Acryl/Polycarbonat** | siehe `schutzbox-plexiglas.md` |

**Merksatz:** *Alles Flache lasern, alle Körper drucken, den Blickfang scannen/Resin.*

## 2. Warum nicht einfach alles drucken? / alles lasern?
- **Alles drucken** = zu langsam (Boden + Straßen als Vollkörper = stundenlang pro Kachel).
- **Alles lasern** = unmöglich (keine Dächer/Türme, nur flache Platten).
- **Hybrid** = der Boden/das Straßennetz kommt in **Minuten** aus dem Laser, die Häuser
  parallel **hohl** aus der Druckfarm. Zusammenstecken → fertig.

## 3. Der schnellste Pfad (parallel, nicht seriell)

**Phase 0 — Daten (✅ erledigt).**
LoD2-Altstadt **700 m** (8207 Gebäude, echte Dächer) + **Münster-Scan reingemergt**,
geschnitten in **36 Druck-Kacheln à ~198 × 200 mm** (`modelle/lod2_gen.py`,
`modelle/stl/tiles_6x6/`). Maßstab ~1:116 (Münster-Turm ≈ 1 m).

**Phase 1 — Ein Schaustück in Tagen (Pilot-Kachel).**
Nur die **Münster-Kachel** hohl drucken + **Laser-Grundplatte** drunter → ein vorzeigbares,
fotogenes Teil für Bibliothek/FWTM-Pitch. Beweist das Verfahren, kostet fast nichts.

**Phase 2 — Fläche hochskalieren (parallel).**
- **Druckfarm / Online-Druckservice**: die 36 Kacheln hohl parallel drucken (nicht 1 Drucker
  seriell — das ist der größte Zeithebel).
- **Laser**: eine durchgehende **MDF/Acryl-Bodenplatte** mit **gravierten Straßen + Bächle +
  Plätzen** als Trägerraster, auf das die gedruckten Kacheln gesetzt werden (deckungsgleich,
  weil aus denselben Geodaten).

**Phase 3 — Detail & Leben (MiWuLa-Niveau).**
Münster in **Resin** als Upgrade, Bemalung + **LED Tag-Nacht**, **Magnorail**-Autos,
**Höllentalbahn** (wenig Wartung) — siehe `automatisierung-ohne-rc.md`, `beleuchtung-detail.md`.

## 4. Tempo-Hebel (das macht es *schnell*)
1. **Hohl drucken**: 0 % Infill, 2 Perimeter, 0,28–0,32 mm Schicht → Material/Zeit drastisch runter
   (innen „extrem hohl", wie gewünscht). Häuser sind geschlossene Volumen → wasserdicht, slicer-hohl.
2. **Parallelisieren**: mehrere Drucker oder Druckservice für die 36 Kacheln statt 1 Gerät seriell.
3. **Laser statt Druck für ALLES Flache** (Boden, Straßen, Wasser, Haube) — Faktor 10+ schneller.
4. **Resin nur fürs Hero-Münster**, FDM für die Masse — Schärfe nur dort, wo das Auge hinschaut.
5. **Eine Pilot-Kachel zuerst** (Phase 1) → sofort zeigbar, finanziert/legitimiert den Rest.

## 5. Laser-Dateien aus denselben Daten (deckungsgleich)
Aus den LoD2/OSM-Daten lässt sich der **Grundriss (Straßen, Bächle, Plätze, Gebäude-Footprints)
direkt als SVG** für den Laser exportieren — **exakt passend zu den Druck-Kacheln**, weil gleiche
Projektion/Skalierung. Geplantes Tool: `modelle/laser_grundplatte.py` (Footprints + Straßennetz →
SVG mit Schnitt-/Gravurlinien, kachelweise).
→ So kommen **Boden + Stadtgrundriss aus dem Laser** und **Häuser aus dem Drucker**, und beide
passen ohne Nacharbeit zusammen.

## 6. Kosten/Material grob
- **FDM-Filament** (hohl): wenige € pro Kachel → ~**50–100 € fürs ganze Stadtfeld**.
- **Laser-MDF/Acryl** Bodenplatte: ~**30–80 €** (je nach Größe/Material).
- **Resin-Münster**: ~**10–20 €** Harz.
- **Zeit**: Pilot-Kachel in **Tagen**, komplettes Altstadt-Feld in **1–3 Wochen** mit Druckfarm/Service.

Bezug: `bauplan-miniaturwunderland.md` (Sektionen/Maßstab), `display-mvp.md` (Kalkulation),
`3d-stadtmodell.md` (Datenpipeline), `schutzbox-plexiglas.md` (Haube).

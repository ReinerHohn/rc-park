# Bauplan: Mini-Freiburg-Schwarzwald extrem detailliert (in Sektionen)

> Ziel: extrem detailliertes Freiburg + Schwarzwald als Miniaturwunderland.
> **Nicht ein True-Scale-Modell** (Maßstabs-Konflikt, s. u.), sondern **Sektionen bei EINEM
> Maßstab** — genau wie Miniatur Wunderland.

## Die Maßstabs-Wahrheit (zuerst verstehen!)
- **Detail** (Häuser mit sichtbaren Dächern/Fenstern ≈ 2 cm) → **~1:500** → 50-cm-Modell = ~250 m Stadt.
- **Schwarzwald-Relief** (630 m / 10 km) → bei gleichem Maßstab **riesig/unmöglich**; umgekehrt wird
  die Stadt zum 11-mm-Fleck.
→ **Lösung: Sektionen.** Die Stadt flach + hochdetailliert; der Schwarzwald **repräsentativ
  komprimiert** als eigene Sektion (nicht geografisch true-scale an die Stadt gekoppelt).

## Empfohlener Maßstab: 1:500 (einheitlich)
- Altstadt-Kern ±250 m → **50 × 50 cm** (Häuser ~2 cm, Dächer/Fenster sichtbar). Modular in
  Kacheln (hast du: LoD2-Tiles).
- Größer möglich (1:250 → noch detaillierter, doppelte Fläche).

## Die Sektionen
1. **Altstadt-Kern (flach, hochdetailliert)** — der Star:
   - Masse: **LoD2-Kacheln** (echte Dächer) — [`3d-stadtmodell.md`](3d-stadtmodell.md).
   - Hero-Wahrzeichen: **Münster** (Scan/Resin/Faller), Schwabentor/Martinstor, Hist. Kaufhaus.
   - **Bächle** (Wasserrinnen), **Magnorail**-Autos, **Höllentalbahn** fährt durch
     ([`automatisierung-ohne-rc.md`](automatisierung-ohne-rc.md)).
2. **Schwarzwald-Sektion (repräsentativ, mit Relief)** — eigener Tisch:
   - **Höllental/Hirschsprung** + **Schauinsland-Bahn**, Täler, Tannen; Relief-Sockel aus
     TouchTerrain/SRTM (`modelle/terrain_gen.py`) — **komprimiert**, nicht 1:1 an die Stadt.
3. **Übergang Tal → Berg**: Dreisam, Weinberge, Stadtrand.

## Woher die „extreme" Detailtiefe kommt
| Ebene | Quelle |
|---|---|
| Gebäude-Masse + echte Dächer | **LoD2** (amtlich, gratis) |
| Hero-Wahrzeichen (scharf) | **Scan/Resin** oder **Faller** ([`prioliste-freiburg.md`](prioliste-freiburg.md)) |
| Fassaden-Detail (Fenster/Ornament) | **Applikation** aufkleben + **Lithophane-Fenster** + Bemalung ([`farbe-drucken.md`](farbe-drucken.md), [`beleuchtung-detail.md`](beleuchtung-detail.md)) |
| Leben/Bewegung | **Magnorail** + **Höllentalbahn** (wenig Wartung) |
| Gelände | **SRTM/TouchTerrain** (Schwarzwald-Sektion) |

## Der „kombinierte Sockel" — praktisch gelöst (zwei Rollen)
Statt eines unmöglichen True-Scale-Modells **zwei komplementäre Stücke am selben Ort**:
- **Großer Schwarzwald-Sockel** = **Überblick/Kontext** (ganze Region grob, `schwarzwald_sockel.stl`).
- **Detaillierte Altstadt-Kacheln** = **Zoom-Sektion** (flach, hochdetailliert).
→ Nebeneinander/ineinander ausgestellt = „Freiburg im Schwarzwald" **ohne** den Maßstabs-Konflikt.
(Alternativ als ein Schaustück: Altstadt im Zentrum groß, Schwarzwald stilisiert als Kulisse drumherum.)

## Reihenfolge (loslegen)
1. **Maßstab festlegen** (1:500) + Altstadt-Kacheln drucken (hast du) + Hero-Münster rein.
2. **Bächle + Magnorail + Höllentalbahn** einbauen (Bewegung, wenig Wartung).
3. **Schwarzwald-Sektion** separat (Höllental/Schauinsland + Relief-Sockel).
4. **Finish:** Bemalung + Tag-Nacht-Licht → MiWuLa-Niveau.

Bezug: [`display-mvp.md`](display-mvp.md), [`wartung-risiko.md`](wartung-risiko.md),
[`standort-display-pilot.md`](standort-display-pilot.md).

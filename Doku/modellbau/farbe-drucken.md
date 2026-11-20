# Scan in Farbe drucken — die 3 Wege (und was NICHT geht)

> Wichtig: Ein Scan **trägt** die Farbe (als Textur). Aber **„Scan → AMS → fertig farbig"**
> ist ein Irrtum: **AMS (eine Düse, mehrere Filamente) reproduziert KEINE Foto-Textur** — es
> reduziert alles auf **2–8 Volltonfarben** und ist langsam + Filament-fressend.
> Echte Scan-Farben (Sandstein-Münster, rotes Kaufhaus) = andere Technik.

## Die 3 Wege im Vergleich
| Weg | Was rauskommt | Wo | Kosten | Für |
|---|---|---|---|---|
| **1. Vollfarb-Service** (ColorJet-Sandstein / PolyJet / MJF) | **photorealistisch**, 30.000+ Farben – echte Textur des Scans | **Druckservice** (Shapeways, Xometry, Craftcloud, Treatstock) | Sandstein ~1,43 $/cm³, **min. ~25 $**; kleine Teile ~10–17 $ | **Hero-Schaustücke** |
| **2. AMS zuhause** (FDM, 2–8 Farben) | **stilisiert**, wenige Volltonfarben – NICHT die echte Textur; langsam + Purge-Abfall | dein Drucker (Tools: printpal/Meshy wandeln Textur → AMS) | Filament + viel Zeit | wenige designte Farbflächen |
| **3. Einfarbig + bemalen** | so gut wie du malst (Wash/Drybrush/Airbrush) | dein Drucker + Farbe | sehr billig | **Masse + Architektur** (oft schöner als AMS) |

## Was das praktisch heißt
- **Echte Farben vom Scan willst du?** → **Vollfarb-Service** (Weg 1). Du lädst das **texturierte
  Modell** hoch (OBJ+Textur / GLB / DAE / X3D) → kommt photorealistisch farbig zurück.
  **Aber: pro Modell teuer** → nur für **Hero-Wahrzeichen** (Münster, Kaufhaus), nicht die ganze Stadt.
- **„Alles in Farbe" über AMS zuhause?** → **nein, unrealistisch**: AMS ist langsam, Filament-
  intensiv und macht aus der Foto-Textur nur ein paar Volltonflächen. Für eine **ganze Stadt**
  ineffizient (siehe [`3d-druck-strategie.md`](3d-druck-strategie.md)).
- **Der günstige Weg für die Masse:** einfarbig drucken + **bemalen** (Wash/Drybrush) — bei
  Architektur sieht das meist **besser** aus als AMS.

## Die clevere Farb-Strategie (statt „alles bunt drucken")
1. **Generische Häuser gar nicht färben** — die **gekauften Faller-Bausätze sind schon farbig**
   ([`kaufen-statt-drucken.md`](kaufen-statt-drucken.md)). Größter Spar-Hebel.
2. **Hero-Freiburg-Wahrzeichen**: Scan → **Vollfarb-Service** (photorealistisch) **oder**
   einfarbig drucken + bemalen + **hinterleuchten** ([`beleuchtung-detail.md`](beleuchtung-detail.md)).
3. **AMS nur** da, wo du bewusst **wenige klare Farbflächen** willst (z. B. Schilder, Fenster-
   Panels als Lithophane) — nicht für Textur-Reproduktion.

## Fazit
- Scan **liefert** die Farbe ✓ — aber **Vollfarbe = Service-Technik**, nicht die Heim-AMS.
- **Nicht „alles bunt drucken"**: Fertig-Häuser (schon farbig) + Hero-Stücke in Vollfarbe/bemalt
  + einfarbig für den Rest. Das ist schneller, billiger und sieht besser aus.

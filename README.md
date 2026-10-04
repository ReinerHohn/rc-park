# 🏎️ RC-Park Freiburg

**Miniatur-Wunderland zum Selbersteuern** — Konzept & Businessplan für eine
wetterunabhängige Indoor-Erlebniswelt in Freiburg, in der Besucher RC-**Fahrzeuge**,
-**Schiffe** (inkl. Flugzeugträger) und -**Flugobjekte** (Helikopter, Flieger, Drohnen)
selbst steuern.

> In Hamburg schaut man zu — in Freiburg fährt, fliegt und schippert man selbst.

## Inhalt

| Datei | Inhalt |
|---|---|
| [`KONZEPT.md`](KONZEPT.md) | Vision, USP, Attraktionen, Zielgruppen, Risiken |
| [`prototyp-konzept.md`](prototyp-konzept.md) | **Schneller Prototyp**: eBay-Gear reparieren + Druckmodule + Personal-Konzept |
| [`standort.md`](standort.md) | Anforderungsprofil & Standortlogik Freiburg |
| [`mieten-kalkulation.md`](mieten-kalkulation.md) | Freiburg-Mieten (Tiers) + Kalkulation je Größe/Lage + Lage-Sweet-Spots |
| [`preise-wettbewerb.md`](preise-wettbewerb.md) | Was andere Parks verlangen (Benchmark) + eigene Preisempfehlung |
| [`mvp-kalkulation.md`](mvp-kalkulation.md) | **MVP durchgerechnet**: Sweet Spot Lage + Features, CapEx, Break-even |
| [`sweet-spots-schnellstart.md`](sweet-spots-schnellstart.md) | Schnell + wenig Personal + viel drucken: Pop-up, Druckfarm, Lage |
| [`sweet-spots-aktion.md`](sweet-spots-aktion.md) | Gedrucktes Mini-Freiburg + Aktion (Drohnen/Bagger/Flieger) = der USP |
| [`baggerland-markt.md`](baggerland-markt.md) | Marktgröße RC-Baggerland (Diggerland etc.) + wie man es spannend macht |
| [`rc-baustellenwelt.md`](rc-baustellenwelt.md) | **MVP ohne Drohnen**: Bagger/Kräne/Radlader/Kipper + Flotte ~6.300 € |
| [`baggerland-stationen.md`](baggerland-stationen.md) | Stationen-Konzept + Baggerführerschein (6 Missionen, Punkte, Level) |
| [`bagger-auswahl.md`](bagger-auswahl.md) | Größter RC-Bagger (1:8) + Preis-Leistungs-Sweet-Spot + Flotten-Stufen |
| [`indoor-fpv.md`](indoor-fpv.md) | Indoor-FPV-Bereich konkret: Whoops, Parcours, Netz, Kosten, Schlechtwetter |
| [`machbarkeit-und-hebel.md`](machbarkeit-und-hebel.md) | Machbarkeit + Beschaffung: gebraucht kaufen, Module, RC-Baggerland |
| [`kaufen-statt-drucken.md`](kaufen-statt-drucken.md) | Einkaufsliste H0-Stadt (fertig/gebraucht) + Maßstabs-Guide + nur Unikate drucken |
| [`prioliste-freiburg.md`](prioliste-freiburg.md) | Prioliste Freiburg-Wahrzeichen + Faller-Sets + Martinstor-Qualität scannen |
| [`risikolos-ohne-personal.md`](risikolos-ohne-personal.md) | Risikolos starten & (fast) ohne Personal: Schau-Installation, Self-Service |
| [`demo-standort.md`](demo-standort.md) | Risikoärmster Start: Demo bei bemanntem Partner am Münster |
| [`host-indoor-spielplatz.md`](host-indoor-spielplatz.md) | **RC-Baustelle bei Indoor-Spielplatz (Kindergalaxie)** via Umsatzbeteiligung |
| [`schutzbox-plexiglas.md`](schutzbox-plexiglas.md) | Sicherer Schutzkasten (von außen gesteuert, kindersicher, Polycarbonat) |
| [`lean-phasen.md`](lean-phasen.md) | Lean-Start in Phasen: Demo & Pop-up & große Fläche (Gates) |
| [`startausstattung.md`](startausstattung.md) | Einkaufsliste mit Preisen (gebraucht/neu) + Kastelburg-Vorbild |
| [`3d-druck-strategie.md`](3d-druck-strategie.md) | Schnell Gebäude/Dioramen als Bausatz drucken; Mehrfarb-Druck-Urteil |
| [`modelle-schwarzwald.md`](modelle-schwarzwald.md) | Sweet-Spot-Modelle (Freiburg/Schwarzwald), sortiert nach Erfolg × Wow |
| [`beleuchtung-detail.md`](beleuchtung-detail.md) | Max. Detail (Resin) + Beleuchtung der Wahrzeichen (Wow-Hebel) |
| [`farbe-drucken.md`](farbe-drucken.md) | Scan in Farbe drucken: Vollfarb-Service vs AMS vs bemalen (Irrtum geklärt) |
| [`max-detail-scan.md`](max-detail-scan.md) | Detail-Obergrenze via echtem 3D-Scan (Photogrammetrie) + Lizenz |
| [`diy-scan.md`](diy-scan.md) | Selbst scannen (Kamera+Drohne+RealityCapture) + Drohnen-Recht |
| [`annahmen.json`](annahmen.json) | **Alle editierbaren Finanz-Annahmen** |
| [`attraktionen/*.json`](attraktionen/) | Je Attraktion: Beschreibung, Fläche, Invest, USP |
| `start.sh` | **Baut + oeffnet beide Dashboards** (businessplan.html + mvp-rechner.html) |
| `build.py` | Erzeugt `businessplan.html` aus den Daten |
| `businessplan.html` | Interaktiver Businessplan mit Live-Reglern & Charts (generiert) |
| [`mvp-rechner.html`](mvp-rechner.html) | **Interaktiver FPV-Pop-up-Rechner** (Presets FWTM/Nebenlage, Break-even) |

## Businessplan erzeugen

```bash
python3 build.py          # schreibt businessplan.html + Konsolen-Zusammenfassung
```

Nur Python-Standardbibliothek, keine Abhängigkeiten. `businessplan.html` ist
self-contained (Chart.js via CDN) und in jedem Browser ohne Server lauffähig.

## Eckdaten (Default-Annahmen)

- Fläche ~2.000 m², ~110.000 Besucher/Jahr, 8 Attraktionen
- Investition **~2,9 Mio €** · Umsatz **~3,6 Mio €** · Gewinn **~0,46 Mio €** (Marge ~13 %)
- **Break-even ~93.000 Besucher/Jahr** (~15 % Sicherheitspuffer)

Zahlen anpassen → `annahmen.json` oder die Attraktions-JSONs editieren, `build.py` neu
laufen lassen. Oder im Browser live an den Reglern ziehen.

> Begründete Schätzungen auf Basis öffentlicher Benchmarks (Miniatur Wunderland Hamburg,
> Freiburg-Tourismusstatistik). Keine testierte Finanzplanung / keine Anlageberatung.

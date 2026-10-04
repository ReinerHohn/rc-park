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
| [`standort.md`](standort.md) | Anforderungsprofil & Standortlogik Freiburg |
| [`sweet-spots-schnellstart.md`](sweet-spots-schnellstart.md) | Schnell + wenig Personal + viel drucken: Pop-up, Druckfarm, Lage |
| [`sweet-spots-aktion.md`](sweet-spots-aktion.md) | Gedrucktes Mini-Freiburg + Aktion (Drohnen/Bagger/Flieger) = der USP |
| [`machbarkeit-und-hebel.md`](machbarkeit-und-hebel.md) | Machbarkeit + Beschaffung: gebraucht kaufen, Module, RC-Baggerland |
| [`risikolos-ohne-personal.md`](risikolos-ohne-personal.md) | Risikolos starten & (fast) ohne Personal: Schau-Installation, Self-Service |
| [`demo-standort.md`](demo-standort.md) | Risikoärmster Start: Demo bei bemanntem Partner am Münster |
| [`lean-phasen.md`](lean-phasen.md) | Lean-Start in Phasen: Demo & Pop-up & große Fläche (Gates) |
| [`startausstattung.md`](startausstattung.md) | Einkaufsliste mit Preisen (gebraucht/neu) + Kastelburg-Vorbild |
| [`3d-druck-strategie.md`](3d-druck-strategie.md) | Schnell Gebäude/Dioramen als Bausatz drucken; Mehrfarb-Druck-Urteil |
| [`modelle-schwarzwald.md`](modelle-schwarzwald.md) | Sweet-Spot-Modelle (Freiburg/Schwarzwald), sortiert nach Erfolg × Wow |
| [`beleuchtung-detail.md`](beleuchtung-detail.md) | Max. Detail (Resin) + Beleuchtung der Wahrzeichen (Wow-Hebel) |
| [`max-detail-scan.md`](max-detail-scan.md) | Detail-Obergrenze via echtem 3D-Scan (Photogrammetrie) + Lizenz |
| [`diy-scan.md`](diy-scan.md) | Selbst scannen (Kamera+Drohne+RealityCapture) + Drohnen-Recht |
| [`annahmen.json`](annahmen.json) | **Alle editierbaren Finanz-Annahmen** |
| [`attraktionen/*.json`](attraktionen/) | Je Attraktion: Beschreibung, Fläche, Invest, USP |
| `build.py` | Erzeugt `businessplan.html` aus den Daten |
| `businessplan.html` | Interaktiver Businessplan mit Live-Reglern & Charts (generiert) |

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

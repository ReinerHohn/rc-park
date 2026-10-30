# QUELLEN-REGISTER — kanonische Liste ALLER Datenquellen für Bauwerks-/Geländemodelle

**HARTE REGEL (User, wiederholt, mit Nachdruck):** Für JEDES Modell ALLE öffentlich verfügbaren
Quellen mergen. NICHTS raten, solange eine Quelle existiert. Eine Quelle, die vorliegt oder
upstream verfügbar ist und nicht genutzt wird, ist ein FEHLER.

**ERZWUNGEN durch `tools/quellen_inventar.py --name <modell>`** — Pflicht VOR jedem Bau. Das Tool
druckt JEDEN der folgenden Typen mit Status (✅ genutzt / ⚠️ im Repo ungenutzt / ⬇️ upstream
Bringschuld) und endet mit Exit-Code 2, solange etwas offen ist. Der Generator ruft es am Anfang auf.

## Die 16 kanonischen Quellentypen

| # | Typ | liefert | woher (BW / global) |
|--|--|--|--|
| 1 | **LOD2** | Grundriss (Teile) + Trauf-/Firsthöhen = amtliches 3D-Massing | LGL BW opengeodata `LoD2_32_*.zip` |
| 2 | **LOD1** | einfaches Blockmodell (Fallback) | LGL BW opengeodata |
| 3 | **DOP_RGB** | Luft-Orthofoto: Dachplan v. oben (First/Gauben/Kamine) + Dach-/Bodentextur | LGL `dop20rgb_*` |
| 4 | **DOP_CIR** | **radiometrisch**: Color-Infrarot/NIR → Vegetation/Material/Versiegelung | LGL `dop20cir_*` |
| 5 | **DOM1** | Laser-OBERFLÄCHE 1 m (mit Dächern/Bäumen): echte Dach-/Objektgeometrie | LGL `dom1_*` |
| 6 | **DGM1** | Laser-BODEN 1 m: Gelände-/Sockelhöhe | LGL `dgm1_*` |
| 7 | **nDOM** | Objekthöhe über Boden (= DOM1 − DGM1, sonst selbst rechnen) | LGL / selbst |
| 8 | **LAZ_ALS** | ROHE LiDAR-Punktwolke (dichter als Raster) + **Intensität/Radiometrie/Klassen** | LGL BW 3D-Messdaten (ALS) |
| 9 | **ALKIS** | amtl. Flurstück-/Gebäudeumriss + Nutzung (Grundwahrheit Footprint) | LGL BW / Geoportal |
| 10 | **HIST_DOP** | historische Orthofotos/Zustände | LGL / LUBW Archiv |
| 11 | **S2_MSI** | Sentinel-2 MULTISPEKTRAL 10 m, 13 Bänder (Landbedeckung) | Copernicus Hub |
| 12 | **S1_SAR** | Sentinel-1 Radar (wetterunabhängig, Struktur/Feuchte) | Copernicus Hub |
| 13 | **COP_DEM** | Copernicus 30 m DEM (grobes Fallback-Gelände) | AWS copernicus-dem-30m |
| 14 | **OSM** | Vektor: Gebäudeumriss/Wege/Trasse/Tags | Overpass / OSM extract |
| 15 | **FOTO_BODEN** | Fassadendetail/Material/Farben/Stückzahlen | eigene / Wikimedia / Google |
| 16 | **STREET** | Street-Level/Panorama (Fassade schräg) | Mapillary / eigene |

Neue Quellentypen werden HIER und im `REGISTER` von `quellen_inventar.py` ergänzt — nie ad hoc vergessen.

## Ablauf pro Modell
1. `python3 tools/quellen_inventar.py --name <modell>` → `modelle/<modell>/QUELLEN.md` (Status je Typ).
2. Jede ⚠️/⬇️ Quelle verbauen ODER begründet als n/a markieren (used-marker-Datei anlegen).
3. Erst wenn das Gate grün (Exit 0) ist, gilt das Massing/Detail als „vollständig aus Daten".

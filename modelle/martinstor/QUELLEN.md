# QUELLEN-MANIFEST — martinstor

Kachel UTM32 **414_5316** · E 414126 N 5316244 · in BW (LGL-Standarddaten upstream verfügbar)

Auto-Inventur `tools/quellen_inventar.py` — KANONISCHE Vollständigkeits-Checkliste.
Status: ✅ genutzt · 🚫 n/a (begründet) · ⚠️ im Repo ungenutzt · ⬇️ upstream Bringschuld.

| # | Quelle | liefert | Dateien | Status | woher / Begründung |
|--|--|--|--|--|--|
| 1 | **LOD2** (3D-Gebäudemodell) | Grundriss(Teile)+Trauf/First = amtliches Massing | 8 | ✅ genutzt | LGL BW opengeodata (LoD2_32_*.zip) |
| 2 | **LOD1** (3D-Klötzchen) | einfaches Blockmodell (Fallback zu LOD2) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL BW opengeodata |
| 3 | **DOP_RGB** (Luft-Orthofoto) | Dachplan v. oben: First/Gauben/Kamine + Dach-/Bodentextur | 4 | ⚠️  IM REPO, NICHT GENUTZT | LGL BW opengeodata (dop20rgb_*) |
| 4 | **DOP_CIR** (Color-Infrarot) | RADIOMETRISCH: NIR-Band → Vegetation/Material/Versiegelung | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL BW opengeodata (dop20cir_*) |
| 5 | **DOM1** (Laser-Oberfläche) | 1 m Oberfläche MIT Dächern/Bäumen: echte Dach-/Objektgeometrie | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL BW opengeodata (dom1_*) |
| 6 | **DGM1** (Laser-Boden) | 1 m Gelände: Sockel-/Umgebungshöhe | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL BW opengeodata (dgm1_*) |
| 7 | **nDOM** (Objekthöhe) | DOM−DGM = Höhe über Boden (sonst SELBST rechnen aus DOM1/DGM1!) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL oder = DOM1−DGM1 selbst rechnen |
| 8 | **LAZ_ALS** (LiDAR-Punktwolke) | ROHE 3D-Laserpunkte (dichter als Raster) + INTENSITÄT/Radiometrie/Klassen | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL BW 3D-Messdaten (ALS Punktwolke) |
| 9 | **ALKIS** (Kataster) | amtl. Flurstück-/Gebäudeumriss + Nutzung (Grundwahrheit Footprint) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL BW / Geoportal |
| 10 | **HIST_DOP** (Historik-Luftbild) | frühere Orthofotos/Zustände (zeitliche Referenz) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | LGL BW / LUBW Archiv |
| 11 | **S2_MSI** (Sentinel-2) | MULTISPEKTRAL 10 m, 13 Bänder (regional, Landbedeckung) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | Copernicus Open Access Hub |
| 12 | **S1_SAR** (Sentinel-1 Radar) | SAR (wetterunabhängig, Struktur/Feuchte) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | Copernicus Open Access Hub |
| 13 | **COP_DEM** (Copernicus DEM) | 30 m globales DEM (grob, Fallback-Gelände) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | AWS copernicus-dem-30m (no-auth) |
| 14 | **OSM** (OpenStreetMap) | Vektor: Gebäudeumriss/Wege/Trasse/Tags | 0 | ⬇️  UPSTREAM, NICHT GELADEN | Overpass / OSM extract |
| 15 | **FOTO_BODEN** (Bodenfotos) | Fassadendetail/Material/Farben/Stückzahlen (eigene/Commons) | 11 | ⚠️  IM REPO, NICHT GENUTZT | eigene / Wikimedia Commons / Google |
| 16 | **STREET** (Street-Level) | Panorama/Street-Level (Fassade schräg, Mapillary) | 0 | ⬇️  UPSTREAM, NICHT GELADEN | Mapillary API / eigene |

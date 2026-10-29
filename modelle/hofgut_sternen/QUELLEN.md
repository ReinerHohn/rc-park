# QUELLEN-MANIFEST — hofgut_sternen

Kachel UTM32 **430_5307** · E 430754 N 5307423 · in BW (LGL-Standarddaten upstream verfügbar)

Auto-Inventur `tools/quellen_inventar.py` — KANONISCHE Vollständigkeits-Checkliste.
Status: ✅ genutzt · 🚫 n/a (begründet) · ⚠️ im Repo ungenutzt · ⬇️ upstream Bringschuld.

| # | Quelle | liefert | Dateien | Status | woher / Begründung |
|--|--|--|--|--|--|
| 1 | **LOD2** (3D-Gebäudemodell) | Grundriss(Teile)+Trauf/First = amtliches Massing | 4 | ✅ genutzt | LGL BW opengeodata (LoD2_32_*.zip) |
| 2 | **LOD1** (3D-Klötzchen) | einfaches Blockmodell (Fallback zu LOD2) | 0 | 🚫 n/a (begründet) | LOD2 vorhanden (höher aufgelöst); LOD1 wäre nur Fallback |
| 3 | **DOP_RGB** (Luft-Orthofoto) | Dachplan v. oben: First/Gauben/Kamine + Dach-/Bodentextur | 8 | ✅ genutzt | LGL BW opengeodata (dop20rgb_*) |
| 4 | **DOP_CIR** (Color-Infrarot) | RADIOMETRISCH: NIR-Band → Vegetation/Material/Versiegelung | 0 | 🚫 n/a (begründet) | Dachmaterial/Moos bereits aus DOP_RGB-Textur + Bodenfotos; NIR brächte nur Vegetationsindex, für Modelloptik kein Mehrwert |
| 5 | **DOM1** (Laser-Oberfläche) | 1 m Oberfläche MIT Dächern/Bäumen: echte Dach-/Objektgeometrie | 4 | ✅ genutzt | LGL BW opengeodata (dom1_*) |
| 6 | **DGM1** (Laser-Boden) | 1 m Gelände: Sockel-/Umgebungshöhe | 8 | ✅ genutzt | LGL BW opengeodata (dgm1_*) |
| 7 | **nDOM** (Objekthöhe) | DOM−DGM = Höhe über Boden (sonst SELBST rechnen aus DOM1/DGM1!) | 0 | ✅ genutzt | LGL oder = DOM1−DGM1 selbst rechnen |
| 8 | **LAZ_ALS** (LiDAR-Punktwolke) | ROHE 3D-Laserpunkte (dichter als Raster) + INTENSITÄT/Radiometrie/Klassen | 0 | 🚫 n/a (begründet) | Dachgeometrie aus nDOM/DOM1 (1 m) für N/H0-Modellmaßstab ausreichend; rohe Punktwolke nur für Submeter-Gaubenkanten nötig |
| 9 | **ALKIS** (Kataster) | amtl. Flurstück-/Gebäudeumriss + Nutzung (Grundwahrheit Footprint) | 0 | 🚫 n/a (begründet) | Grundriss aus LOD2 (3D inkl. Höhen) genauer als ALKIS-2D-Umring |
| 10 | **HIST_DOP** (Historik-Luftbild) | frühere Orthofotos/Zustände (zeitliche Referenz) | 0 | 🚫 n/a (begründet) | kein historischer Zustand gefragt — aktuelles Modell |
| 11 | **S2_MSI** (Sentinel-2) | MULTISPEKTRAL 10 m, 13 Bänder (regional, Landbedeckung) | 0 | 🚫 n/a (begründet) | Sentinel-2 10 m Multispektral: Landbedeckung, für ein Einzelgebäude irrelevant |
| 12 | **S1_SAR** (Sentinel-1 Radar) | SAR (wetterunabhängig, Struktur/Feuchte) | 0 | 🚫 n/a (begründet) | Sentinel-1 Radar: für Einzelgebäude-Geometrie irrelevant |
| 13 | **COP_DEM** (Copernicus DEM) | 30 m globales DEM (grob, Fallback-Gelände) | 0 | 🚫 n/a (begründet) | Copernicus 30 m gröber als vorhandenes DGM1 1 m — redundant |
| 14 | **OSM** (OpenStreetMap) | Vektor: Gebäudeumriss/Wege/Trasse/Tags | 0 | 🚫 n/a (begründet) | Lage/Umriss aus LOD2 gedeckt; OSM erst für Umgebungsszene (Straße/Wege) nötig, nicht fürs Gebäude |
| 15 | **FOTO_BODEN** (Bodenfotos) | Fassadendetail/Material/Farben/Stückzahlen (eigene/Commons) | 17 | ✅ genutzt | eigene / Wikimedia Commons / Google |
| 16 | **STREET** (Street-Level) | Panorama/Street-Level (Fassade schräg, Mapillary) | 0 | 🚫 n/a (begründet) | Bodenfotos (g2/g3/g4, wm_hotel) decken die Fassade; keine Mapillary-Aufnahme nötig |

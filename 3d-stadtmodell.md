# Ganze Stadt als 3D-Modell: amtliches 3D-Stadtmodell Freiburg → drucken

> Du musst Freiburg **nicht** Haus für Haus scannen/bauen: Es gibt ein **amtliches
> 3D-Stadtmodell (LoD2)** mit **allen Gebäuden + Dachformen** — als **Open Data gratis**.
> Download → zu STL wandeln → drucken. Die ganze Stadt auf einmal.

---
## ⭐⭐ F4MAP — die echten Freiburg-3D-Gebäude LIVE im Browser ⭐⭐
> ## 👉 **https://demo.f4map.com/#lat=47.9956970&lon=7.8535034&zoom=17**
> **Live-3D-Karte der echten OSM-Gebäude** (inkl. Münster-Turm!) — reinzoomen, drehen,
> gucken. Perfekt als **visuelle Vorlage** und um zu sehen, welche Gebäude/Dächer es gibt,
> bevor man sie generiert/druckt. **Das Tool zum Loslegen.**
---

## 🎁 Die Quelle (gratis)
- **3D-Stadtmodell Freiburg i. Br. — LoD2** (alle Gebäude mit echten Dachformen), Format
  **CityGML**, über **daten-bw.de** / **opendata.lgl-bw.de** / Freiburg-Geoportal.
- **Lizenz: Datenlizenz Deutschland Namensnennung 2.0** → **frei nutzbar, nur Quelle nennen**
  (auch kommerziell). Kein CC-BY-NC-Problem wie beim Münster-Scan.
- **LoD2** = Gebäudekörper mit korrekten Dächern (Sattel/Walm/…), stadtweit. Kein Fassaden-
  Feindetail (keine Fenster/Ornamente) — aber die **ganze Stadtsilhouette stimmt**.

## CityGML → druckbare STL (3 Wege)
1. **citygml2stl** (Python-Lib, PyPI/GitHub ctu-fgis) — CityGML direkt → **FDM-druckbare STL**.
2. **3DCityLoader** (Webdienst) — wandelt öffentliche 3D-Stadtdaten in **STL/OBJ**.
3. **Blender**: CityGML → CityJSON (`citygml-tools`) → Import-Addon → als **STL exportieren**.

## Noch schneller: Web-Tools (ohne Behördendaten)
- **Cadmapper** (cadmapper.com) — nutzt OpenStreetMap, **gratis bis 1 km²**, inkl. **Topografie +
  3D-Gebäude** → STL. Ideal für schnelle **Altstadt-Kacheln**.
- **TouchTerrain** (touchterrain.org) — **gratis**, macht aus Höhendaten eine **druckbare
  Gelände-STL** → perfekt für den **Schwarzwald-/Freiburg-Relief-Sockel** unter der Stadt.

## Druck-Workflow (praktisch)
1. **Ausschnitt wählen** (nur Altstadt ums Münster, nicht die ganze Stadt — sonst riesig).
2. **Zu STL wandeln** (citygml2stl / 3DCityLoader / Blender).
3. In Blender/Meshmixer **wasserdicht machen** (Böden schließen, „Make Solid") + **auf
   Modellgröße skalieren** (georeferenziert = echte Meter → runterskalieren) + **aushöhlen**.
4. In **Module/Kacheln schneiden** (Flat-Wall/Bausatz, [`3d-druck-strategie.md`](3d-druck-strategie.md))
   → auf der **Druckfarm** oder per **Druckservice** ausgeben.
5. **Hero-Wahrzeichen** (Münster, Kaufhaus) separat **detailliert** ergänzen (Scan/Gambody/Resin,
   siehe [`prioliste-freiburg.md`](prioliste-freiburg.md)) — LoD2 liefert nur den groben Baukörper.

## Was das für dich ändert (groß!)
- **Die ganze Altstadt entsteht automatisch** aus echten Freiburg-Daten — nicht generische
  Faller-Häuser, sondern die **echten Gebäude-Grundrisse/Dächer** → **unverkennbar Freiburg**.
- Spart enorm: kein Haus-für-Haus-Modellieren/Scannen; nur noch **drucken (Farm/Service)** +
  Hero-Details.
- **Relief-Sockel** (Schwarzwald/Münsterberg) per TouchTerrain dazu → komplette Landschaft.

## Grenzen / Hinweise
- **LoD2 = kein Feindetail** (glatte Fassaden) → Hero-Wahrzeichen separat detailliert.
- CityGML-Gebäude sind oft **nur Hüllen** → vor dem Druck **solid/wasserdicht** machen.
- **Menge**: die ganze Stadt ist zu viel Druck — **nur den gewünschten Ausschnitt** nehmen,
  Rest ggf. kaufen/weglassen.

## 🗺️ Noch mehr Datenquellen (alles nutzbar fürs Modell)
| Quelle | Was | Link |
|---|---|---|
| **F4Map** ⭐ | **live 3D der echten OSM-Gebäude im Browser** | demo.f4map.com |
| OSM Buildings | 3D-OSM-Gebäude-Viewer | osmbuildings.org |
| **LGL BW Open GeoData** | LoD2 **ganz Baden-Württemberg** (CityGML) | opendata.lgl-bw.de |
| **BKG** | **LoD2-DE: ganz Deutschland** | gdz.bkg.bund.de |
| **Freiburg Geoportal / FreiGIS** | Stadt-Open-Data: Gebäude, **DGM (Gelände), ALKIS, Orthophotos, Bäume** | geoportal.freiburg.de |
| **ALKIS / Kataster** | exakte **Gebäude-Grundrisse + Flurstücke** | Landesvermessung |
| **LiDAR / ALS-Punktwolken** (LAS) | ultrahochauflösende Punktwolken (teils Open Data) | LGL/Länderportale |
| Google **Photorealistic 3D Tiles** | fotorealistisches 3D ganzer Städte (API, kostenpflichtig) | Google Maps Platform |
| **Mapillary / KartaView** | Straßenbilder → eigene Photogrammetrie | mapillary.com |
| Copernicus / SRTM **DEM** | Höhendaten (Gelände) | opentopography / Copernicus |
| **Cadmapper** | OSM-Stadt → STL (bis 1 km² gratis) | cadmapper.com |
| **TouchTerrain** | Gelände → druckbare STL | touchterrain.org |
| **3DCityDB / 3DCityLoader** | CityGML verwalten/konvertieren → STL/OBJ | 3dcityloader.com |

→ Für dich am wichtigsten: **F4Map** (ansehen) + **LoD2 Freiburg** (echte Dächer, drucken) +
**TouchTerrain** (Schwarzwald-Sockel). Hero-Wahrzeichen separat (Scan/Faller).

## 🌍 Noch viel mehr Datenquellen (Vollliste)

**Globale Gebäudedaten (gratis):**
- **Overture Maps** — offener globaler Gebäude-Datensatz (Meta/MS/Amazon/TomTom), Footprints+Höhen.
- **Microsoft Building Footprints** — weltweit, ML-erzeugt, gratis (GitHub).
- **Google Open Buildings** — gratis (v. a. globaler Süden).

**Andere Bundesländer (eigene LoD2/LoD3 Open Data):** Bayern, NRW, Berlin (3D), **Hamburg 3D**,
Thüringen, Sachsen … — falls ihr über Freiburg hinauswollt.

**Komfort-Tools (Buildings + Terrain + Satellit in einem):**
- **Blosm / Blender-OSM** (Blender-Addon) — OSM-Gebäude **+ Google 3D-Tiles + Gelände** importieren.
- **BlenderGIS** — OSM, DGM, Orthofotos nach Blender. · **OSM2World** — OSM → 3D.

**Gelände / Höhe (präzise):**
- **DGM1 (1 m!)** der Landesvermessung (LGL BW, Open Data) — viel feiner als SRTM.
- **OpenTopography** (DEM + LiDAR), **Copernicus DEM GLO-30**, **ALOS AW3D30**.

**Bilder / Textur (für Farbe/Hueforge):**
- **Orthophotos DOP20** (20 cm, Open Data der Länder) — Dachtexturen von oben.
- **Mapillary / KartaView / Panoramax** — Straßenbilder → eigene Photogrammetrie.

**Fertige Modelle (kaufen/gratis):**
- **Sketchfab** (Scans, teils CC), **Printables / MakerWorld / Thingiverse / Cults / MyMiniFactory**
  (druckbar), **Gambody** (Detail), **Thangs**, **GrabCAD**, **3D Warehouse** (SketchUp-Architektur),
  **BIMobject** (Bauteile).

**Historisch / Kontext:**
- **Historische Karten** (Landesarchiv BW, David Rumsey) — fürs „historische Freiburg".
- **Wikidata / Wikimedia Commons** — Landmark-Fotos als Photogrammetrie-Vorlage.
- **OSM-POIs** (Bäume, Bänke, Straßenmöbel, Läden) — zum Ausstatten des Dioramas.

**KI (Bild/Text → 3D):**
- **Meshy · Luma · Tripo · Rodin** — aus Fotos/Prompts 3D-Modelle generieren.

## Quellen
daten-bw.de (3D-Stadtmodell Freiburg LoD2), opendata.lgl-bw.de, lgl-bw.de (LoD2-Produkt),
geoportal.freiburg.de, gdz.bkg.bund.de, citygml2stl (PyPI), 3dcityloader.com, cadmapper.com,
touchterrain.org, demo.f4map.com.

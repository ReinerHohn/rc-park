# Ganze Stadt als 3D-Modell: amtliches 3D-Stadtmodell Freiburg → drucken

> Du musst Freiburg **nicht** Haus für Haus scannen/bauen: Es gibt ein **amtliches
> 3D-Stadtmodell (LoD2)** mit **allen Gebäuden + Dachformen** — als **Open Data gratis**.
> Download → zu STL wandeln → drucken. Die ganze Stadt auf einmal.

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

## Quellen
daten-bw.de (3D-Stadtmodell Freiburg LoD2), opendata.lgl-bw.de, lgl-bw.de (LoD2-Produkt),
citygml2stl (PyPI), 3dcityloader.com, cadmapper.com, touchterrain.org.

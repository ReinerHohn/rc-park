# Hotel Oberkirch — Pipeline-Test „erster Schuss" (2026-10-28)

Ziel: die am Historischen Kaufhaus erarbeitete Pipeline auf ein NEUES, schlichtes
Nachbargebäude anwenden und ehrlich bewerten, wie weit **ein Durchlauf ohne Iteration**
trägt. Zielgebäude: **Hotel Oberkirch, Münsterplatz 22** (Ost-Nachbar des Kaufhauses,
LOD2-ID `DEBW_0010007Tv9p`, direkt neben Kaufhaus `…Tv9r`).

## Vorgehen (reine Pipeline, keine Handmaße)
1. **Lokalisieren/Masse amtlich:** `lod2_gebaeude.py --center 414420.9,5316370.2` →
   B 9,41 · T 16,4 · **Traufe 11,84 · First 21,04 m**, Satteldach (traufständig, ~48°).
2. **Fotos:** 6 CC-Fotos (Wikimedia) geladen; bestes Frontfoto `ob_platz_jm3399.jpg`.
3. **Foto sezieren → Spec:** 4 Geschosse (EG-Restaurant + 3 OG), **4 Fensterachsen**
   (gemessen 2+2 gruppiert, x-frac [0.094,0.306,0.645,0.890]), grüne Lamellenläden +
   Geranienkästen je Fenster, **4 Gauben** + ~4 Dachluken, EG: „OBERKIRCHS WEINSTUBEN"-
   Band + 2 Wappen + Tür/Schaufenster, schmiedeeiserner Ausleger mittig am 1. OG.
   Specs → `oberkirch_mass.json` + `oberkirch_params.json` (kein Hardcoding im Code).
4. **Generator:** `tools/oberkirch_measured.py` (neu, parametrisch, liest die JSONs;
   bewährtes Idiom `shapely`-Fassade-minus-Löcher → `extrude_polygon` → `_stand`,
   Elementgruppen je Farbe, Export je Gruppe STL + GLB).
5. **Render/Ausliefern:** `glb_render.py` (EGL) + `oberkirch_3d.html` + `.stl`.

## Ergebnis: sitzt auf den ersten Schuss
Sofort als Hotel Oberkirch erkennbar. **Korrekt im ersten Durchlauf:** Massing (LOD2),
4×3 Fenster mit Läden + Blumenkästen, EG-Restaurantfront mit Schriftband/Wappen,
4 Gauben + Dachluken, Ausleger, steiles Dach. Beleg: `ob_vergleich.png`.

## Abweichungen (ehrlich)
- **Dach wirkt kopflastig:** Modell = LOD2 (44 % Höhe), Frontfoto verkürzt auf ~27 %
  (bekannte Falle „Frontfoto verkürzt steiles Dach" — LOD2 bleibt maßgeblich).
- EG-Schaufenster im Foto **segmentbogig**, im Modell rechteckig (Detail offen).
- Läden als flache Paneele mit angedeuteten Lamellen (kein echtes Lamellenprofil).
- Ausleger/Laternen als Platzhalter (kein Schmiede-Maßwerk).

## Pipeline-Lehre
- **Masse + Mess-Tools + Render/Validierung generalisieren sofort** (LOD2-Extraktion,
  Foto-Sezierung, `glb_render`, HTML/STL — alles 1:1 wiederverwendet).
- **Der Generator ist NICHT generisch:** `kaufhaus_measured.py` ist auf Arkade/Erker/
  Statuen/Treppengiebel verdrahtet — das Oberkirch hat NICHTS davon. Darum neuer,
  schlanker Generator. Das bestätigt den offenen Plan `tools/bauwerk_generator.py`
  (Feature-Flags has_arcade/has_oriels/shutters/dormers + Config je Gebäude). Die hier
  gebauten Bausteine (Putzfassade-Raster, Läden, Blumenkästen, Gauben, Satteldach,
  Ausleger) sind die ersten generischen Elemente über das Kaufhaus hinaus.

## Dateien
- Generator: `tools/oberkirch_measured.py`
- Specs: `modelle/hotel_oberkirch/oberkirch_mass.json`, `oberkirch_params.json`
- Masse: `oberkirch_lod2.{stl,json}`
- Modell: `oberkirch_measured.glb` / `.stl`, `oberkirch_3d.html`, `ob_vergleich.png`
- Fotos: `daten/hotel_oberkirch/fotos/` (CC, Wikimedia)

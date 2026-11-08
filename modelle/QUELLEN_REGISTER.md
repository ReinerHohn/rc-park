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
| 16 | **STREET** | Street-Level/Panorama (Fassade schräg) | Mapillary / eigene; Panoramax/KartaView (CC BY-SA) pruefen; Google verboten |
| 17 | **BDOM** | bildbasiertes Oberflächenmodell **0,2 m**, farbig (Gauben/Kamine/Erkerdächer); LGL: „nicht qualitätsgesichert" → eigene Blindheitszeile | LGL BW, ganz BW, Bestellung per Mail ca. 60 €, DL-DE BY 2.0 (Entwurf `LGL_BESTELLUNG_BDOM.txt`) |
| 18 | **STADT_LOD2** | zweites, unabhängiges LoD2 (Gegenprobe Dachformen) | Freiburg: geoportal.freiburg.de/stadtmodell/20261007_Freiburg_LoD2.gml (1,6 GB, EPSG 25832), DL-DE BY 2.0 + Vermerk "Datengrundlage: Stadt Freiburg, www.freiburg.de". **Status 2026-11-05: geladen + zugeschnitten (`tools/stadt_lod2_schneiden.py`, `modelle/<objekt>/stadt_lod2.json`), Inventar gruen; nur Vergleich, nicht gemittelt** |
| 19 | **STADT_MESH** | texturiertes Photogrammetrie-Mesh (Befliegung 2025) | Freiburg: 3d.freiburg.de (tileset.json abrufbar); **Lizenz offen → nur Prüfreferenz**, Anfrage vermessung@freiburg.de. **Status 2026-11-05: ladbar ohne Anmeldung (HTTP 200), `tools/stadtmesh_laden.py` -> `audit/referenz_stadtmesh/mesh.ply`; Inventar "Pruefreferenz"; Aufloesung ca. 1 m Dreieckskante, Hoehen schon ue.NN** |

Korrektur 2026-11-05: 3d.freiburg.de ist NICHT nur ein Viewer - die Cesium-tilesets sind abrufbar (Recherche `reports/Daten und Qualitaet fuer H0 Modelle.md`); Lizenz ungeklaert.

Neue Quellentypen werden HIER und im `REGISTER` von `quellen_inventar.py` ergänzt — nie ad hoc vergessen.

## Ablauf pro Modell
1. `python3 tools/quellen_inventar.py --name <modell>` → `modelle/<modell>/QUELLEN.md` (Status je Typ).
2. Jede ⚠️/⬇️ Quelle verbauen ODER begründet als n/a markieren (used-marker-Datei anlegen).
3. Erst wenn das Gate grün (Exit 0) ist, gilt das Massing/Detail als „vollständig aus Daten".

## Fehlerbudget LoD2 (LGL vs Stadt), 2026-11-05
Werkzeug `tools/lod2_fehlerbudget.py` (importiert `stadt_lod2_schneiden`, `lod2_gebaeude`), Ausgabe `/media/oem/scan/rc-park_daten/freiburg_stadt/fehlerbudget/` (`fehlerbudget_lod2.json`, `histogramme_lod2.png`). Alle Gebaeude mit Schwerpunkt <= 300 m um Kaufhaus (null5-Rahmen) und Martinstor (anker3d); 949 LGL, 981 Stadt; Paarung ueber Grundriss-Ueberlapp (Boden- + Dachprojektion), Paar = 1:1 mit beiden Anteilen >= 50 %: **917 Paare**; ausgeschlossen 8x 1:n, 2x n:1, 5x n:m; ohne Partner 6 LGL / 30 Stadt. Differenz = Stadt - LGL, Hoehen absolut ue.NN. Laufzeit 34 s, 258 MB Spitze.

| Groesse (alle Paare) | Median | sigma_rob (1,4826 MAD) | Mittel | Std | p5 / p95 | Anteil >0,5 | Anteil >1,0 |
|---|---|---|---|---|---|---|---|
| First abs (m) | +0,06 | 0,56 | +0,10 | 2,18 | -2,07 / +2,85 | 42 % | 24 % |
| niedrigste Traufe abs (m) | -0,27 | 1,42 | -0,99 | 2,95 | -6,85 / +2,40 | 66 % | 49 % |
| Grundriss (m2) | 0,00 | 0,06 | +0,38 | 24,8 | -0,61 / +0,31 | 10 % | 7,5 % |
| Grundriss-Verhaeltnis | 1,000 | 0,00 | 1,002 | 0,023 | 0,997 / 1,004 | - | - |
| Boden-z abs (m) | -0,06 | 0,39 | +0,04 | 0,69 | -0,80 / +1,20 | 26 % | 10 % |

Nach Typ (LGL-Dachflaechenzahl): flach/pult n=514 First sigma_rob 0,58, Traufe 1,21; sattel/walm n=263 First 0,48, Traufe 1,45; komplex n=140 First 0,58, Traufe 2,85 (Median -1,41: Stadt-LoD2 hat viele Kleinflaechen, "niedrigste Traufe" ist dort nicht gleich definiert). Dachflaechenzahl komplex: Stadt oft mit Zehnfachem (Martinstor 4 vs 162).
- **Ausreisser** |dFirst| > 3 m: 77 von 917 (8,4 %; 44 flach/pult, 18 sattel/walm, 15 komplex; 43 mit Stadt hoeher, 34 mit LGL hoeher). Groesste: Tv3j +20,9 (Martinstor-Umfeld), hPLcn +19,3 (Martinstor), qwYVj +16,6 (Kaufhaus-Umfeld), THvQ -13,8, TvnP +13,3. Kandidaten fuer "eine Quelle sieht Aufbauten/Nadeln/Tuermchen" (Stadt hoeher, Dachflaechenzahl Stadt >> LGL) oder fuer Fehlzuordnung/Zeitstand (LGL hoeher bei n_dach 1:1, z. B. THvQ, THtU: Abriss/Neubau zwischen den Staenden moeglich, ANNAHME, nicht geprueft).
- **Bodenbezug**: Median der Bodendifferenz -0,06 m (nicht 0,5 m); die 0,47/0,49 m von Kaufhaus/Martinstor (G4) sind Einzelwerte bei P12 der Verteilung, kein systematischer Versatz. Aber Streuung 0,39 m (26 % > 0,5 m): "First ueber Boden" haengt an dieser Streuung -> nur absolut (ue.NN) vergleichen, nicht ueber Boden.
- Grundriss: Stadt und LGL teilen praktisch dieselbe Katasterbasis (Median 1,000, 80 % innerhalb +-0,3 %); Grundriss-Abweichung ist kein unabhaengiges Fehlermass, Kaufhaus (1,063) und Martinstor (1,052) liegen bei P98.
- **Kovarianz-Vorschlag (Sollwerte NICHT geaendert)**: Bereich lod2 fuer First absolut sigma = 0,6 m (robust; Ausreisserwahrscheinlichkeit 8 % mit |d| > 3 m -> schwere Flanken, Student-t/Huber statt Gauss, nicht Std 2,2 m verwenden); niedrigste Traufe sigma = 1,5 m (flach/Sattel) bzw. 3 m (komplex), also fuer Traufe als Messwert schwach gewichten; Boden sigma 0,4 m; Grundriss nur als Kataster-Anker (sigma ~ 0,1 m ohne Gewicht auf Zweitquellenvergleich). Einordnung: Zwei Quellen mit gleichem Schaetzer streuen im Median 0,6 m im First - ein einzelner LoD2-First-Wert gilt also nicht besser als +-0,6 m (1 sigma), unabhaengig von der Annahme "amtlich = wahr". Die Streuung der Differenz ist die Summe beider Quellenfehler (je Quelle ca. sigma/1,4 bei Gleichverteilung des Fehlers, ANNAHME).
- Einordnung: Kaufhaus dFirst +0,23 m (P67, |d|-Rang P28 = unauffaellig), dTraufe +0,41 (P74); Martinstor dFirst +19,28 m (P99,8), dTraufe -24,96 (Minimum der Verteilung): Martinstor ist ein echter Ausreisser, Stadt sieht Helm + Nadel (162 Dachflaechen), LGL nur Rumpf - kein Fehler der Statistik, sondern "Quelle sieht Aufbauten" (Regel 4).

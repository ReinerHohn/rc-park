# Methodik: echte Orte automatisiert zu Steck-/Druck-Modellen

**Das Prinzip (und der einzige Unterschied zu normalem Modellbau):**
Was aus Daten rechenbar ist, wird **gerechnet — nicht von Hand modelliert.** Du beschreibst
den Ort (Koordinaten + Ausschnitt + Maßstab), der Rest fällt als fertige Schnitt-/Druck-Dateien
raus. Geschwindigkeit und Städte-Skalierung kommen DAHER — nicht aus Bastel-Tricks.

Alles unten ist konkret (Mathe, Parameter, echte Fehler aus diesem Projekt). Generisches
Modellbau-Wissen (Figuren kaufen, Trockenbürsten) gehört bewusst NICHT hierher.

---

## 1. Die Daten-Engine (das Herz — fast am wichtigsten)

**Gelände — LGL `dgm025` (0,25 m, ganz BW gratis):**
- Datei `dgm025_full.npy` = 4000×4000 float32 = eine 1-km-Kachel.
- Georef aus der `.tfw`: Pixel 0,25 m, Ursprung E=426000.125 / N=5309999.875.
  - Pixel→UTM: `E = 426000.125 + col·0.25`, `N = 5309999.875 − row·0.25`.
  - Genau diese Mathe hat Portal 2 (UTM 426870/5309869) auf Modell x132/y90 verifiziert.
- Ausschnitt `[r0:r1, c0:c1]` → nodata (<−1000) füllen → Zeilen flippen `[::-1]` (+y = Nord).
- Modell: `cell_mm = 0,25 m × nscale`, `Höhe = Relief_m × nscale × vscale + base`.
  nscale **6,25** = true-N, **3,125** = 50 %, **1,5625** = 25 %. Alles skaliert damit automatisch.

**Features — OSM Overpass:**
- `way["railway"](around:600,LAT,LON); way["tunnel"]...` — GET `?data=` + User-Agent; pyproj 4326→25832 → Modell-mm.
- Tunnel-Flags NUR wo real Fels drüber liegt (sonst offenes Gleisbett). Portal-Koords aus OSM gegen das DGM gegenrechnen.

**Gebäude — LOD2 (BW gratis):** Grundriss + echte Höhe → Box-Generator (noch zu bauen, §4).

---

## 2. Die Generatoren (was automatisch rausfällt)

`tools/terrain_eggcrate.py` — DEM + OSM → komplettes Steck-Gerüst in Minuten:
- **Adaptive Rippen** (dicht an scharfen Kanten, weit im Flachen, `--min-gap 7`) + **Kanten-Lineale** auf Felsgraten/Bruchkanten (Ridge-Filter, `--edge-min-len 18` = keine Fuzzel-Mini-Teile).
- **Tunnel/Trasse:** Lichtraum = echte Röhre in Metern × nscale (`--tunnel-w-m 4 --tunnel-h-m 5.5`), **Dach-Garantie** (`--roof-min`), tiefe OSM-Schiene, offene Strecke = Einschnitt.
- **Auto-robust:** `--min-web 3` kappt Steck-Schlitze (Gegenschlitz wird tiefer, Verzahnung bleibt) → nirgends dünner als 3 mm; **Auto-Nudge** versetzt Rippen mit Körper-Hals; Fingerzinken nur wo die Rippe nicht aufs Bett passt.
- Output: pro Rippe SVG + G-Code (Nummer + X/Y graviert), 3D-Zusammenbau-Tool (Kreuzungs-Finder, Baustand-Filter), Bauplan.

`modelle/<x>/generate.sh` = generieren + packen in einem Rutsch.
`tools/laser_pack.py` → A3-Bretter. ⚠️ **G-Code-Bereich IMMER gegen 410×400 prüfen** (Pack-Report lügt: meldete 403, war 442 → Kopf fährt sonst über den Rand).

---

## 3. Die Fallen-Datenbank (die echten, teuren Fehler — NICHT wiederholen)

| Fehler | Symptom | Fix |
|---|---|---|
| Falsche LiDAR-Kachel | monatelang „alles flach/Schrott" | **lokalisieren + Google-Maps-Gegencheck VOR allem** |
| Trasse ×0,5 skaliert, Krop anders referenziert | Tunnel am falschen Ort / fällt still weg | Georef pro Krop neu, **„Trasse N>0" checken** |
| Lichtraum 30×36 mm absolut bei halb-N | = 9,6×13,5 m real → Tunnel bricht durchs Dach | **maßstäblich** (× nscale) |
| Tunnel-Flags: Gleisbett als Tunnel markiert | „im Gleisbett statt Tunnel" | Flags aus echten OSM-Portalen |
| „Schiene aus Gelände" auf Portal-Niveau | Tunnel verliert Dach, Trasse zu hoch | Tunnel = tiefe OSM-Schiene, nur Gleisbett-Oberfläche flach |
| Steck-Schlitz neben Steilkante | 1,8-mm-Wand bricht beim Entgittern | `--min-web`-Kappung (Fenster = Schlitz + Wand) |
| S9-Pack-Report falsch | 442 mm statt 410 → Kopf übers Bett | echten G-Code-X/Y-Bereich prüfen |
| Serieller Abriss bei langem Schnitt | Job stirbt bei ~10 % | USB **direkt** an Laptop, Port während Job **nicht anfassen** |

---

## 4. Stadt-Automatisierung (der Teil, der „Städte schnell" erst möglich macht)

**Noch NICHT gebaut — das ist der nächste Automatisierungs-Schritt, und der eigentliche Hebel für Städte:**
- LOD2-Grundrisse + echte Höhen → **Box-Generator** (Laser-Spanten oder Druck-Box) **im Batch**, nicht Haus-für-Haus.
- Luftbild/Street-View → **auto-entzerrte Fassaden-Textur** → Farbdruck-Bogen → aufkleben.
- Ein Durchlauf = ein ganzer Straßenzug. Das ist die Skalierung; einzeln modellieren skaliert nie.

→ Genau dieselbe Logik wie beim Gelände: **aus Daten rechnen, nicht modellieren.** Wenn du willst, bauen wir diesen Generator als Nächstes.

---

## 5. Oberfläche aus Daten — der Finish-Speedup (kein Anmalen)

Das Volumen fällt aus Daten — die **Oberfläche** (Gras/Schotter/Fels/Feld/Straße) muss das
AUCH, sonst wird das Anmalen der Flaschenhals und die Demo dauert zu lange.
- **LGL DOP20** (Orthophoto, 20 cm, BW gratis) = echtes Luftbild, **gleiche UTM-Kachel wie das DGM** → deckungsgleich zum Relief.
- Krop `[r0:r1,c0:c1]` deckungsgleich holen → auf Modell-mm skalieren → drucken → **über die Gips-Haut legen/mod-podgen.** Sanftes Gelände = perfekt, 0 Pinsel.
- **Scharfe Kanten/Felsgrate macht das Laser-Gerüst selbst** (Kanten-Lineale = scharfe Geometrie, Gips legt sich dran). Keine Handarbeit dafür.
- Bleibt NUR: die FARBE auf **near-vertikalen Felswänden**, wo das Senkrecht-Luftbild kaum Pixel hat (ein Kliff ist von oben eine dünne Linie) → ein dünner **Fels-Textur-Streifen** (gedruckt/generiert) über die Wand, kein Pinsel. → auch das aus Daten.
- Noch schneller: Ortho direkt auf die **Haut-Platten** (`skin_smart_split`) texturieren → Platten kommen vorgefärbt.
- Ergebnis: Oberfläche in **Stunden statt Tagen**, farblich EXAKT der echte Ort. (Tool: `tools/ortho_drape.py` — DOP holen, auf Krop+Maßstab zuschneiden, Druck-Bogen.)

---

## 6. Der Loop (warum es schnell ist)

```
Ort (Koords+Ausschnitt) → generate.sh → Bretter gegen Bett prüfen → schneiden/drucken
→ stecken → Gips (Natur) / Fassade aufkleben (Stadt) → Kaufteile (Figuren/Autos/Gleis)
```
Ein **neuer Ort = nur Schritt 1 neu.** Alles dahinter ist Maschine. Das ist der ganze Trick —
nicht die Bastelei, sondern dass die Bastelei aus Daten abfällt.

---
Detail-Terrain-Pipeline (12 Schritte, lang): `METHODE_WUNSCH_ZU_MODELL.md`.

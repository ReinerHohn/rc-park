# Komplette Methode: vom gewünschten Ort zum bemalten Miniatur-Modell

End-to-End-Rezept für den Freiburg/Schwarzwald-im-Kleinen-Pitch. Von „ich will Ort X"
bis zum fertig bemalten, beleuchteten, befahrbaren Modul. Jeder Schritt nennt das
konkrete Werkzeug im Repo.

Grundprinzipien (gelten überall):
- **Echte Daten statt raten** — Gelände aus LiDAR, Features (Bahn/Straße/Tunnel/Gebäude) aus OSM.
- **Hybrid-Maßstab**: große Landschaft in **Spur N (1:160, 6,25 mm/m)**, Technik-Detail/Demonstrator in H0. Nie in einer Ansicht mischen.
- **Qualität vor Material**: an der sichtbaren Oberfläche NICHT sparen/glätten. Material sparen nur unsichtbar (hohl, Band-Rippen, Nesting).
- **Aufgabenteilung**: *Laser* = Volumen/Gelände schnell+billig · *3D-Druck* = Oberfläche/Technik/Gebäude · *kaufen* = Figuren, Autos, Gleise, Loks.

---

## 1. Ort festnageln & lokalisieren
- Echte Lage bestimmen (Foto/Postkarte als Komposition, dann Koordinaten).
- **IMMER mit Google Maps gegenchecken** — gespeicherten Koords nicht blind trauen (Hirsch lag mal 130 m daneben). Siehe `google-maps-fallback`.
- Prüfen: enthält die LiDAR-Kachel den Ort wirklich? (Kernfehler-Falle: falsche Kachel → alles „zu flach".)

## 2. Daten holen
- **Gelände (ganz BW gratis):** LGL DGM1 (1 m, Boden) oder DGM025 (0,25 m, Max-Detail) — `lgl-bw-lidar`. DGM = Berg, DOM/LOD2 = Bauwerke.
  `https://opengeodata.lgl-bw.de/data/dgm/dgm1_32_{E}_{N}_2_bw.zip`
- **Außerhalb BW:** Copernicus DEM 30 m (AWS, no-auth) · GEBCO via OPeNDAP (Meer/Welt).
- **Features (Bahn, Straße, Tunnel, Brücke, Gebäude):** OpenStreetMap Overpass.
  `way["railway"](bbox); way["tunnel"](bbox); …` — GET oder POST **mit User-Agent**, pyproj EPSG:4326→25832.
- Georeferenz der Kachel aus der `.tfw` (Pixelgröße + Ursprung-UTM) — Pixel→UTM→Modell-mm.

## 3. Ausschnitt & Maßstab
- Fenster `[r0:r1, c0:c1]` so wählen, dass die **Killer-Szene** drin ist (steile Teile NICHT abschneiden — sonst „flach/Schrott").
- true-N: `cell_mm = 6,25 × Pixelgröße_m`, Höhe `H = Relief_m × 6,25 × vscale`.
- **vscale (Überhöhung) 0,85–1,0** real; Sweet-Spot sonst 1,5–2× (nicht >3× = spitz/fake), alle Kacheln GLEICHE Überhöhung.
- **Entrauschen** nur gegen LiDAR-Rauschen (z. B. smooth 0,6 am Steilfels) — kein Detail-Glätten.

## 4. Aufteilung (was womit)
| Teil | Methode | Werkzeug |
|---|---|---|
| Gelände-Volumen | **Laser-Steck-Gerüst** (Egg-Crate) | `tools/terrain_eggcrate.py` |
| Gelände-Oberfläche | Gips/Fliesenkleber über Deckplatten **oder** gedruckte Haut | `tools/eggcrate_deck.py` / `tools/skin_smart_split.py` |
| Technik/Scharf (Tunnelportal, Steinschlag­galerie, Brücke) | **3D-Druck** als separates Teil | FreeCAD/Mesh → MK4S/P1S |
| Gebäude/Wahrzeichen | 3D-Druck (+ hinterleuchtbare Maßwerk-Platten) | `skelett-masswerk-system` |
| Figuren, Autos, Gleise, Loks, Bäume | **kaufen** | — |

## 5. Laser-Gerüst erzeugen
`tools/terrain_eggcrate.py` (DEM → steckbares Kreuzgitter):
- **Adaptive Rippen-Dichte**: dicht an scharfen Kanten (Fels/Schlucht/Kante Straße→Gleis), weit im Flachen — `--min-gap 7`, Schärfe-Metrik 0,5·Summe + 1,0·Max. Keine feste Rippenzahl.
- **Rippen voll bis Boden** (`--rib-depth 0`, stabil) oder Band (`--rib-depth 60`, −1 Platte). `--base` = Sockel gegen Pinchen.
- **Trasse/Tunnel aus OSM**: `--tunnel --track <trasse.npy>` (Zeilen `mx,my,mz,is_tunnel`). Lichtraum N **30×36 mm** (NIE mitskalieren); bei schräger Trasse automatisch aufgeweitet → senkrecht volle 30 mm (N-Waggon passt). Tunnel gedeckelt, offene Strecke = Einschnitt.
- **Deckplatten** mit `tools/eggcrate_deck.py` (gleiche `rib_positions()`-Quelle → passen exakt). Sanfte Zellen = flache Platte, steile = Gipsbinde.
- Output: pro Rippe SVG+GRBL, Nummer **+ X/Y-Koordinate graviert**, 3D-HTML, Bauplan.

## 6. Schneid-Planung für die Maschine  ⚠️ Sculpfun S9 = nur ~410×400 mm!
Der Laser kann eine 1200×600-Kaufplatte **nie in einem Rutsch** schneiden.
- Teile müssen **≤ 410×400** sein (lange X-Rippen = 406 mm → passen gerade). Kein Teil über Fenstergrenze.
- Nesten auf S9-Fenster: `tools/laser_nest.py <dir> --sheet 410x400`. → Anzahl Fenster = Anzahl Schneid-Durchgänge (Höllental: **15 Fenster**).
- **Material kaufen** rechnet man getrennt mit `--sheet 1200x600` (Höllental: 4 Platten ~40 €). Eine 1200×600 liefert **3 Fenster** à 400×410 → ~5 Kaufplatten in Rohlinge zersägen.
- Workflow: Kaufplatte → in 400×410-Rohlinge sägen → Rohling mit **Anschlag-Ecke** reproduzierbar in den S9 → ein Fenster-Programm laufen lassen → nächster Rohling.
- Hebel für weniger Durchgänge: lange Rippen mittig mit Fingerzinken teilen (Joint liegt unsichtbar unter dem Gips).

## 7. Cutten + Technik-Teile drucken
- **Laser:** 2–3 mm Pappel-Sperrholz oder Graupappe, **kein PVC** (Chlorgas). Geglättete Konturen → 100 % Schnitt. 3 mm ≈ 4 Passes. Fokus/Linse fix. Siehe `laser-sculpfun-s9` (+ `grbl_send.py`).
- **3D-Druck (parallel):** Tunnelportal/Steinschlaggalerie, Brücke, Gebäude, Wahrzeichen. MK4S 0,8-HF fürs Grobe (bemalt), 0,4 fürs Detail · P1S parallel · hohl drucken. Siehe `nozzle-strategie`, `prusaslicer-cli`, `bambu-p1s-lan`, `prusa-mk4s-network`.

## 8. Zusammenstecken
- X-Rippen (Schlitz oben) + Y-Rippen (Schlitz unten) ineinander = selbsttragend, kein Kleber.
- Teile über Gravur-Nummer + X/Y finden: Bauplan-PNG / interaktive Suche `tools/haut_bauplan_html.py`.
- Deckplatten in ihre Zelle auf die Rippen-Oberkanten legen/kleben.

## 9. Haut/Oberfläche — Gips & Fliesenkleber
- Über die Deckplatten **Gipsbinde** (steile Zellen überbrücken), dann **Gips oder Fliesenkleber** als modellierbare Haut drüber.
  - *Fliesenkleber* = zäher, haftet auf Holz, gut für raue Felsstruktur; *Gips* = fein, schnell, gut für glatte/weiche Formen.
- Fels-Struktur direkt reinmodellieren/ritzen, solange feucht. Pro Fläche entscheiden (`hq-modell-strategie`):
  - Natur → Streumaterial deckt Rillen · Fels → Kork/Struktur + Washes · glatte Bauten → Füller + schleifen.

## 10. Anmalen & Finish
- **Grundierung** (grau/braun), dann Schichten:
  - **Fels-Magie**: dunkle Lasur in die Spalten (Washes laufen lassen) + helles Trockenbürsten auf die Kanten → Tiefe. „dunkel in Spalten, hell auf Kanten".
  - **Natur**: Grundton + Streugras/Flock, Büsche, Bäume (gekauft/gestreut) kleben.
  - **Wasser**: Gießharz/Gel in Bachbett (ggf. Pumpenkreislauf, s. Triberg).
- **Beleuchtung — zwei Regime** (`beleuchtung-zwei-regime`): Monumente VON AUSSEN anstrahlen (opak + Flutlicht); (Hoch)häuser VON INNEN (transluzent/Fenster + LED-Strip). Warm/kühl per LED, Stromschiene + Controller als Skalierungs-Hebel.

## 11. Technik einbauen
- **N-Flexgleis** durch den Tunnelkanal (30 mm quer reichen fürs ~15 mm Gleisbett), Radius ≥ 192 mm, Steigung moderat.
- Loks/Waggons, Figuren, Autos; **Wahrzeichen-Figur** (z. B. Hirsch) auf echte Position.
- Bewegung (fahrender Zug, Seilbahn/Gondeln) = das, was den Pitch verkauft.

## 12. Verifizieren & Pitchen
- Gegen Foto/Google/OSM prüfen (Proportion, Lage). Euler/watertight bei gedruckten Teilen.
- Transportables Pitch-Board „Freiburg im Kleinen" mit mehreren Highlights → beweist Anmalen + Licht + Bewegung (`miwula-freiburg-pitch`, `mini-freiburg-geschaeftsmodell`).

---

### Werkzeug-Index
`terrain_eggcrate.py` (Gerüst + adaptive Rippen + OSM-Tunnel) · `eggcrate_deck.py` (Deckplatten) ·
`laser_nest.py` (Platten/Fenster nesten) · `laser_relief_kit.py` / `mesh_former_kit.py` (Laser-Kits generisch) ·
`skin_smart_split.py` (gedruckte Haut, flach+hohl) · `haut_bauplan_html.py` (Teil-Finder) ·
`grbl_send.py` (S9 senden) · `p1s_print.py` (Bambu LAN) · `topo_laser_contours.py` (Kontur-Stack).

### Memory-Verweise
`real-ort-lidar-osm-workflow` · `laser-skelett-workflow` · `drohnenscan-druckpipeline` ·
`lgl-bw-lidar` · `copernicus-dem-aws` · `gebco-opendap-access` · `qualitaet-vor-material` ·
`hq-modell-strategie` · `nozzle-strategie` · `beleuchtung-zwei-regime` · `miniaturland-massstab` ·
`laser-sculpfun-s9` · `miwula-freiburg-pitch`.

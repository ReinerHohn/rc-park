# Master-Methodik: Maximal schnell geile Modellbau-Landschaften & Städte
### mit vollem Technik-Einsatz (KI · Lasercut · 3D-Druck · Farbdrucker · weitere Maschinen)

Ziel: von „ich will Ort X" zur **fertigen, bemalten, beleuchteten, befahrbaren** Szene — in
Tagen statt Monaten. Die Detail-Terrain-Pipeline steht in `METHODE_WUNSCH_ZU_MODELL.md`;
DIESES Dokument ist die **Allokation + die Low-Hanging-Fruits**: welche Maschine macht was,
und wo liegen die schnellsten Siege.

---

## 0. Das Grundgesetz
**Jede Maschine macht NUR, was sie am schnellsten/besten kann. Die falsche Maschine = 10–50× langsamer.**
Der eigentliche Wert (der Moat) ist nicht das Lasern/Drucken (Commodity) — es ist die
**Software-Pipeline**, die aus echten Daten in Minuten Schnitt-/Druck-Dateien macht.

---

## 1. Daten — das Fundament (fast am wichtigsten)
**Garbage in = Garbage out.** Die beste Pipeline rettet keine falschen Daten — die teuersten
Fehler saßen ALLE in den Daten (falsche LiDAR-Kachel → monatelang „alles flach"; Trasse falsch
geflaggt → Tunnel im Gleisbett). Datenarbeit = **holen + generieren + prüfen**.

### 1a. Holen (echte Welt → Zahlen)
| Datum | Quelle | Weg |
|---|---|---|
| Gelände (Boden) | LGL **DGM1** (1 m) / **DGM025** (0,25 m), BW gratis | opengeodata.lgl-bw.de · außerhalb BW: Copernicus 30 m (AWS) · GEBCO (Meer) |
| Oberfläche m. Mauern/Bäumen | LGL **DOM1** (GeoTIFF) | enge Täler/Burgen |
| Gebäude-Höhen/Formen | **LOD2** (BW gratis) | echte Höhen → Box+Fassade |
| Bahn/Straße/Tunnel/Brücke/Fluss/Gebäude-Umriss | **OSM Overpass** | GET/POST + User-Agent, pyproj 4326→25832 |
| Fassaden | Google Street View / eigene Fotos | perspektiv-entzerren → drucken |
| Texturen (Boden/Wasser/Feld) | Fotos / Bild-KI | kacheln → drucken |
| Georeferenz der Kachel | `.tfw` (Pixelgröße + Ursprung-UTM) | Pixel→UTM→Modell-mm |

### 1b. Generieren (wo echte Daten fehlen oder stumpf sind — DER KI-Teil)
Hier entscheidet sich die Qualität; das ist der eigentliche Hebel:
- **Prozedural aus Daten ableiten:** Egg-Crate-Gerüst, Trasse, Tunnel, Lichtraum, Kanten-Lineale — alles aus DEM+OSM **gerechnet**, nicht modelliert.
- **Schärfen, was das DEM verschluckt:** DGM rundet Senkrechtfels/Überhänge → scharfe Kanten per Ridge-Filter zurückholen (snap-edges, Kanten-Lineale: Felsgrat, Bruchkante, Portal-Stirn).
- **Fehlende Features synthetisieren:** Portal/Steinschlaggalerie ohne Scan → prozedural/Hand; Schiene aus Gelände ableiten wenn OSM-z stumpf; nodata füllen.
- **Texturen/Fassaden mit Bild-KI** erzeugen/vervollständigen (Dach, Putz, Wasser), wo kein Foto taugt.
- **Maßstab rechnen:** nscale/vscale, Lichtraum **maßstäblich** skalieren (echte Röhre × nscale).

### 1c. Prüfen (VOR dem Bauen — hier sitzen die teuren Lehren)
- **Lokalisieren + Google-Maps-Gegencheck** — enthält die Kachel den Ort WIRKLICH? (falsche Kachel 2 km daneben = alles „flach/Schrott").
- **Georeferenz verifizieren** — echtes Feature (Portal, Denkmal) muss im Modell an der richtigen Stelle landen (TFW-Mapping nachrechnen: row→N, col→E).
- **Feature-Flags echt** — Tunnel nur wo wirklich Fels drüber (sonst offenes Gleisbett); „Trasse N Punkte > 0" checken (sonst fällt der Tunnel still weg).
- **Geometrie-Checks** — watertight/euler (Tunnel = 1 Röhre), Teil-Maße vs. Bett, Mindest-Wand, Tunnel-Dach.

→ **Merksatz: erst Daten festnageln, DANN bauen.** Jede Stunde Datenprüfung spart Tage Nachschnitt.

---

## 2. Tech-Allokations-Matrix (die ganze Methode auf einen Blick)

| Element der Szene | Beste Maschine | Warum = Low-Hanging-Fruit |
|---|---|---|
| **Gelände-Volumen** (Berge, Täler, Steilwände) | **Laser** Egg-Crate + Gips/Fliesenkleber | dm³ in Stunden, 3 mm Pappel billig. 3D-Druck wäre 50× langsamer. |
| **Gelände-Oberfläche Natur** (Wiese, Fels, Wald) | **Gips/Fliesenkleber** + Streu + Trockenbürsten | Textur kommt vom Material, nicht aus der Maschine. |
| **Wasser** (Fluss, See, Wasserfall) | **Farbdrucker** (Foto-Textur) + Klarlack/Resin/Laminierfolie | Gedruckte Fläche + Glanz = sofort überzeugend. |
| **Straßen, Plätze, Felder, Gleisbett** (flach) | **Farbdrucker** (Textur-Decals aufkleben) | Aufkleben statt bemalen = Minuten, fotorealistisch. |
| **Masse-Gebäude** (eine ganze Stadt) | **Laser/Druck Box** + **Farbdruck-Fassade** | Simple Box + aufgeklebte Fassade = Haus in Minuten (s. §5). |
| **Wahrzeichen/Detail-Gebäude** (Münster) | **3D-Druck** (Skelett + Maßwerk) | Feine Geometrie, hinterleuchtbar. Das EINE Hero-Piece. |
| **Beleuchtete Fenster/Maßwerk** | **Farbdrucker auf Folie** + LED dahinter | Transparent gedruckt → Nacht-Effekt fast gratis. |
| **Schilder, Reklame, Plakate, Nummern** | **Farbdrucker** | Winzig, scharf, farbig — unschlagbar. |
| **Technik** (Tunnelportal, Brücke, Galerie, Stützmauer) | **3D-Druck** als separates Teil | Präzise, scharf. |
| **Figuren, Autos, Bäume, Gleise, Loks, Laternen** | **KAUFEN** (N/H0-Massenware) | 0 Produktionszeit = sofort Leben. NIE selbst machen. |
| **Hintergrund/Tiefe** | **Farbdrucker** (Panorama-Kulisse) | Foto hinter die Szene = Tiefe ohne Modellbau. |
| **Lokalisieren · Daten · Cut/Print-Files · QC** | **KI** | Koordinaten, OSM, DEM, Scripts, Fehler VORHER finden. |

---

## 3. Die Maschinen — jede ihr Job

**KI = das Gehirn.** Ort lokalisieren (Koords + Google-Maps-Gegencheck), echte Daten holen
(LGL-DGM1/025, OSM-Overpass, LOD2), Schnitt-/Druck-Dateien generieren (`terrain_eggcrate.py`
& Co.), die **Allokation entscheiden** (was Laser/Druck/Farbe/kaufen), Fehler VORHER finden
(Teil-Maße vs. Bett, Passung, Tunnel-Dach, dünne Wände). Zusätzlich: Fassaden-/Boden-Texturen
erzeugen/entzerren (Bild-KI), Beschriftung/Reklame texten.

**Lasercut (Sculpfun S9, ~410×400 mm).** Volumen + flache Teile **schnell**: Gelände-Gerüst
(Egg-Crate), Kanten-Lineale (scharfe Grate), Gebäude-Spanten, flache Dekor-/Masken-Teile.
3 mm Pappelsperr, 2× @100 %. ⚠️ **Jedes Teil ≤ Bett** — vor dem Schnitt den echten G-Code-X/Y-
Bereich prüfen (nicht dem Pack-Report trauen: schon mal 442 mm statt 410 gemeldet).

**3D-Druck (Prusa MK4S / Bambu P1S).** Oberfläche/Technik/Detail: Gelände-Haut (watertight,
hohl), Monumente, Portale, Brücken, alles Präzise. **Langsam → nur wo nötig.** 0,8-Düse fürs
Grobe (bemalt eh), 0,4 fürs Detail.

**Farbdrucker = der unterschätzte Realismus-Turbo.** 2D-Detail in Masse, billigst, in Minuten:
Fassaden (echte Fotos entzerrt), Boden-/Wasser-/Feld-Texturen, Schilder/Reklame, **beleuchtbare
Fenster auf Transparentfolie**. Der größte Hebel für „sieht echt aus" pro Euro/Stunde.

**Weitere Maschinen (wenn vorhanden):**
- **Schneidplotter/Vinyl** — exakte Masken, Schablonen, Straßenmarkierungen, Folien-Fenster, Gebäude-Umrisse präzise ausschneiden.
- **Heißdraht/Styroporschneider** — Grob-Volumen aus Styrodur für SEHR große flache Landschaft noch schneller als Laser (dann Gips/Farbe drüber).
- **Airbrush** — Washes/Verläufe (Himmel am Kulisse, Fels-Schatten) in Sekunden statt Pinsel.
- **Laminiergerät** — gedruckte Texturen schützen + Glanz geben (= Wasser/nasse Straße).

---

## 4. LOW-HANGING-FRUITS (schnellste Siege, nach Wirkung/Aufwand)

1. **Echtes Gelände an einem Abend** — DEM → `terrain_eggcrate.py` → stecken → Fliesenkleber drüber → Trockenbürsten. Ganze Talflanke in Stunden.
2. **Kaufen statt bauen** — Figuren/Autos/Bäume/Gleise/Loks = sofort Leben, 0 Produktionszeit. (Gebraucht-Sweet-Spots: fertige Anlagen zersägen = Teilespender.)
3. **Gedruckte Fassaden auf simple Boxen** — Stadt = viele Quader + aufgeklebte Farbdruck-Fassaden (Street-View-Foto entzerren). 20 Häuser an einem Nachmittag.
4. **Gedruckte Boden-Texturen als Decals** — Straßen/Plätze/Felder/Wasser aufkleben statt bemalen.
5. **Beleuchtete Fenster für ~nichts** — Fassade mit Fenstern auf Transparentfolie drucken, LED-Streifen dahinter.
6. **Fels-Magie** — dunkel in die Spalten, hell auf die Kanten (Trockenbürsten): grauer Gips → Fels in Minuten.
7. **Nummerierte Steck-Teile** (Laser graviert X/Y) + 3D-Zusammenbau-Tool (Kreuzungen grün) → kein Rätselraten.
8. **Panorama-Kulisse** — Hintergrundfoto gedruckt = Tiefe ohne ein einziges Modellteil.

---

## 5. Der schnellste Komplett-Durchlauf (Quick-Start, eine Killer-Szene)

| # | Schritt | Maschine | läuft parallel zu |
|---|---|---|---|
| 1 | Ort lokalisieren + DEM/OSM holen | KI | — |
| 2 | Gerüst + Kanten-Lineale + Tunnel generieren | KI (`terrain_eggcrate.py`) | — |
| 3 | Gerüst + Lineale schneiden | Laser | Schritt 4 |
| 4 | Portale/Wahrzeichen drucken | 3D-Druck | Schritt 3 |
| 5 | Boden-/Wasser-/Fassaden-Texturen vorbereiten | KI + Farbdrucker | Schritt 3/4 |
| 6 | Stecken → Gips/Fliesenkleber → Lineale aufkleben | Hand | — |
| 7 | Trockenbürsten + Texturen aufkleben + Streu | Hand | — |
| 8 | Figuren/Autos/Bäume setzen + LEDs rein | Hand (Kaufteile) | — |

→ **Killer-Szene in ~1 Wochenende**, weil 3/4/5 parallel laufen.

---

## 6. Städte speziell (der Stadt-Teil)

- **Masse-Häuser = Box + Fassade.** Einfacher parametrischer Körper (Laser-Spanten oder
  Druck-Box) + **Fassade aus Farbdruck** (Google-Street-View-Foto perspektiv-entzerren →
  drucken → aufkleben). Das ist der Städte-Gamechanger: hunderte Häuser, ohne jedes einzeln
  zu modellieren.
- **Echte Höhen/Proportionen aus LOD2** (BW gratis) — Gebäudehöhen stimmen, dann Fassade drauf.
- **Wahrzeichen = das EINE 3D-Druck-Hero-Piece** mit beleuchtetem Maßwerk (Skelett + flach
  gedruckte, einsteckbare, hinterleuchtbare Maßwerk-Platten). Der Rest drumherum Box+Fassade.
- **Zwei Beleuchtungs-Regime, nie mischen:** (Hoch)häuser von INNEN (transluzent/Fenster +
  LED-Strip), Monumente von AUSSEN anstrahlen (opak + Flutlicht). Warm/kühl per LED, Stromschiene
  + Controller als Skalierungs-Hebel.

---

## 7. Prinzipien & teure Lehren (nicht wiederholen)
- **Echte Daten statt raten** — Gelände aus LiDAR, Features aus OSM; IMMER Google-Maps-gegencheck.
- **Qualität vor Material an der Oberfläche** — sparen nur unsichtbar (hohl, Nesting, Band-Rippen); nie glätten.
- **Maschinen-Grenzen VORHER prüfen** — S9 410×400; echten G-Code-Bereich gegen Bett checken (442er-Lektion).
- **Mindest-Wandstärke** (hier 3 mm) — keine dünnen/Fuzzel-Teile; Steck-Schlitze kappen (Gegenschlitz tiefer) statt Rippe zerbrechen lassen.
- **Tunnel/Trasse** — Lichtraum maßstäblich (echte Röhre × nscale, NICHT absolut), Dach garantieren, Trassen-Flags echt (Tunnel nur wo wirklich Fels, sonst offenes Gleisbett), Trasse läuft tief im Einschnitt.
- **Hybrid-Maßstab** — große Landschaft N, Detail/Technik H0; nie in einer Ansicht mischen.
- **Überhöhung** 1,5–2× Sweet-Spot (0,85–1,0 für true-Proportion), alle Kacheln GLEICH.
- **Nummerieren + 3D-Zusammenbau-Tool** — jedes Teil graviert, Baustand-Filter im Viewer.

---

## 8. Werkzeug-Index (Repo)
- Gelände-Gerüst: `tools/terrain_eggcrate.py` (+ `eggcrate_sim.py` = Genauigkeits-/Schnitt-Studie)
- Deckplatten/Haut: `tools/eggcrate_deck.py`, `skin_smart_split.py`, `pack_beds.py`
- Nesten/Schneiden: `tools/laser_pack.py`, `laser_nest.py`, `grbl_send.py` (S9)
- Gebäude/Monument: `tools/mesh_former_kit.py`, Skelett+Maßwerk (`gothic_demo.py`), `flatpack_haus.py`
- Wirtschaftlichkeit (Flächen-Filter): `tools/miniland_kalk.py` (Break-even nach Besucher/Miete)
- Generieren+Packen in einem Rutsch: `modelle/<modell>/generate.sh`

# Methodik: 3D-Modell eines echten Bauwerks aus ALLEN Datenquellen

> Destillat aus dem Linachtalsperre-Projekt (2026-10). Ziel: eine **generelle,
> wiederholbare** Methode, um aus allem, was es zu einem echten Ort/Bauwerk gibt,
> das bestmögliche 3D-Modell zu bauen — und von vornherein den richtigen Weg zu
> wählen, statt sich (wie wir) durch alle Sackgassen zu probieren.

---

## 0. Kernerkenntnis (die eine Lektion)
**Die Methode richtet sich nach der DATENLAGE und dem ZIEL-OUTPUT — nicht nach dem
Wunsch.** Bevor man modelliert, zwei Fragen hart beantworten:
1. **Was gibt es wirklich an Daten?** (vollständig? sauber? nur Ausschnitte?)
2. **Was soll am Ende rauskommen?** (Druckteil / interaktives HTML / Pitch-Bild)

Die meiste verlorene Zeit entsteht, wenn man eine Methode erzwingt, die die Daten
nicht hergeben (z. B. „1 gescannter Bogen → saubere 13-Bogen-Wand klonen").

---

## 1. Datenquellen — Inventar + wofür jede taugt
| Quelle | Gibt | Taugt für | Fallen |
|---|---|---|---|
| **LGL DGM1 (1 m LiDAR)** | Gelände/Täler, XYZ | Landschaft, Seebecken, Trasse | Kachel muss Ort enthalten; **Nachbarkacheln stitchen** wenn Feature überläuft; Spiegel-Falle (row→Süd) |
| **DOM1 / LOD2** | Oberfläche m. Bauten | grobe Gebäudekörper | Bäume als Störung |
| **OSM / Overpass** | Umrisse, Linien, Features | Trasse, Mauerlinie, Seeumriss | öffentl. Server oft **502 overloaded** → Feature stattdessen AUS dem DEM ableiten |
| **Fotogrammetrie-Scan** (Sketchfab/Zenodo/eigene Drohne) | **echte Geometrie + Foto-Textur** | max. Detail eines TEILS; Mess-Referenz | fast immer **nur Ausschnitt**, **offene Fläche** (100k+ offene Kanten), Y-up vs Z-up, Scene-Transforms, verrauscht |
| **Fotos** (Wikimedia CC, Google) | **die echte ARCHITEKTUR** + Textur-Vorlage | verstehen WAS man baut; Fassaden-Textur | Vollphotogrammetrie aus zufälligen Netzfotos = **unmöglich** (Matsch) |
| **Maße** (Wikipedia/Structurae) | autoritative Zahlen | Grund-Proportionen | Koordinate kann daneben liegen → am DEM/Google gegenchecken |
| **KI Bild→3D** (Hi3D/Hunyuan) | ein organisches Mesh | Figuren/Props/Fels | **keine präzise Architektur** (verschwommener Klumpen) |

**Download-Fallen:** Sketchfab-Download ist **login-gesperrt** (API 401) → oft liegt
dasselbe Modell auf **Zenodo** direkt ladbar (ohne Auth); Datei kann groß sein →
`curl -C -` mit Resume + großem Timeout.

---

## 2. Die Geometrie-Entscheidung (Entscheidungsbaum)
```
Brauche ich die GANZE Struktur, sauber/wasserdicht (Druck ODER interaktiv-komplett)?
   JA → PARAMETRISCH, und zwar DATENGETRIEBEN (Parameter aus dem Scan MESSEN).
        + nahtlos reihbar, vollständig, exakte Proportionen, druckbar.
   NEIN, nur ein TEIL in max. Realismus?
        → den echten Scan DIREKT nehmen (texturiert), als GPU-Render/Showcase.

Will ich ein gescanntes Modul zur periodischen Vollstruktur VERVIELFÄLTIGEN?
   → Nur sinnvoll, wenn man ein Modul SAUBER isolieren + die Schnittebenen KAPPEN
     kann. Fotogrammetrie-Fetzen zerfallen beim Croppen / werden Matsch ohne Crop.
     In der Praxis: meist Finger weg, Parametrik gewinnt.

Will ich echtes Voll-Detail der GANZEN Struktur?
   → Es braucht einen VOLLSTÄNDIGEN Scan (systematischer Drohnenflug).
     Aus 2-3 Teil-Scans entsteht er NICHT.
```

### Der Gewinner-Weg: DATENGETRIEBENE PARAMETRIK
Nicht Maße raten — **aus dem Scan messen**, dann sauber generieren:
1. Scan ins **Dam-Frame** bringen (s. §3).
2. Messen: Höhe, **Neigung** (dY/dZ der Wasserseite), Tiefe, **Schalen-Ausbauchung**,
   **Querriegel-Höhen** (Histogramm der luftseitigen Masse über Z), Spannweite.
   > Linach real gemessen: Neigung **0,22** (nicht 0,16 geschätzt!), Tiefe **8,6 m**
   > (nicht 12), Querriegel bei z≈5/9/19. Schätzen lag „extrem viel" daneben.
3. Parametrisch generieren → **dicht unterteilen** (`subdivide`), damit die Fläche
   Fein-Farbe/Detail trägt.
4. Realismus drauf (§4). Reihen ist trivial & nahtlos, weil parametrisch.

---

## 3. Scan-Handling — die technischen Stolpersteine (hart erkämpft)
- **Transforms baken:** `scene.dump()` (nicht `geometry.values()` roh — Node-Transforms fehlen sonst). Graph-Namen ≠ Geometrie-Namen.
- **Hoch-Achse erkennen:** pro Datei verschieden (glTF oft Y-up). Heuristik: Achse mit Extent ≈ Bauwerkshöhe (~25 m) = Höhe.
- **Gemeinsames Frame** („Dam-Frame"): X = Kronenachse = **PCA-Hauptachse der hohen Punkte** (NICHT aller Punkte — See/Gelände verfälscht), Y = Tiefe, Z = Höhe ab 0; downstream = Seite mit tieferem Fuß.
- **Farben:** `g.visual.to_color().vertex_colors` holt die Textur robust als Vertexfarbe (Textur-Atlas lässt sich NICHT planar mappen).
- **Croppen zerlegt:** enges Croppen lässt nur gut gescannte Fetzen übrig (schwebende Gewölbe/Wandscheibe); nahtlos reihen nur mit **gekappten** Schnittebenen — und selbst dann fransig.

---

## 4. Realismus (der #1-Hebel ist TEXTUR, nicht Geometrie)
- **Physisch (Druck):** Fotogrammetrie-Detail ist beim FDM eh nicht auflösbar →
  saubere Form + **ANMALEN** mit Foto als Vorlage („dunkel in Spalten, hell auf
  Kanten"). Scan/Fotos = Farb-/Struktur-Referenz.
- **Digital:** Textur-Projektion eines **Frontalfotos** auf die Fassade ODER
  **dichte Vertexfarb-Übertragung** aus dem Scan (Match nach *Position-im-Bogen*
  `X mod Pitch` + Höhe). Wichtig: **Mesh muss dicht sein**, sonst „zu wenig".

---

## 5. Output & Rendering — Realität der Dateigrößen
- **Voll-Detail (1 Mio F/Bogen × N)** ist als **interaktives HTML unbrauchbar**
  (×13 ≈ 367 MB). Zwei Auswege:
  - **GPU-Offscreen-Render → PNG**: Facezahl zählt NICHT zur Dateigröße → beliebiges
    Detail. open3d `OffscreenRenderer` läuft **headless via Vulkan**. Mesh **manuell**
    bauen (`read_triangle_mesh` wirft Cast-Fehler): `TriangleMesh` + vertex_colors/UV,
    `MaterialRecord(shader='defaultLit')`.
  - **Interaktiv**: decimiertes, **vertex-gefärbtes** GLB in three.js (Textur-UV
    übersteht Decimierung nicht → Vertexfarben; `fast_simplification` verliert UV).
- **Render-Komposition (Fallen):** Kamera zu hoch → man sieht nur die Krone;
  **Gelände verdeckt die Fassade** → Struktur IMMER erst ALLEIN rendern zum Prüfen;
  Licht überstrahlt → Sonne ~72–85k + Indirect ~26–35k.
- **HTML sauber erzeugen:** b64-GLB DIREKT ins Template (kein `str.replace('v2',..)`
  — korrumpiert u. U. die Base64-Daten!); Lade-/Fehler-Anzeige einbauen.

---

## 6. Die generelle Pipeline (Synthese)
1. **Alle Daten sammeln** (DEM, Scans, Fotos, Maße, OSM) + Download-Fallen umgehen.
2. **Fotos STUDIEREN** → die echte Architektur verstehen (Linach: konkave Schalen +
   Querriegel sah man NUR auf den Fotos — hätte man nie geraten). *Immer vor dem Modellieren.*
3. **Lokalisieren + Gelände** aus DEM (Kacheln stitchen, am Google/DEM gegenchecken).
4. **Geometrie** per Entscheidungsbaum (§2) — Default: **datengetriebene Parametrik**.
5. **Realismus** (§4): Textur/Farbe digital, oder Anmal-Vorlage für Druck.
6. **Output** (§5): GPU-Render (max Detail-Bild) / decimiertes GLB (interaktiv) /
   wasserdichtes STL (Druck).
7. **Verifizieren**: Struktur allein rendern, gegen die Fotos prüfen, euler/watertight.

---

## 7. Anti-Pattern (was wir gelernt haben NICHT zu tun)
- ❌ Teil-Scan zur Vollstruktur klonen (zerfällt/Matsch) — außer sauber gekappt.
- ❌ Maße raten statt messen („extrem viel" daneben).
- ❌ Vollphotogrammetrie aus zufälligen Google-Fotos erwarten.
- ❌ Voll-Detail-Mesh als interaktives HTML (Dateigröße explodiert).
- ❌ Detail für Material/Zeit opfern (vgl. „Qualität vor Material").
- ❌ Gespeicherten Koordinaten blind trauen (am DEM/Google prüfen).
- ❌ Struktur im Gelände rendern ohne vorher die Struktur allein zu prüfen.

---

## 8. Research-Stand 2024-2026 (Deep-Research, 23 Quellen, adversarial geprüft)
**Kernaussage: KEINE Einzelmethode — hybrid, geometrie-zuerst.**

- **SfM-Photogrammetrie = metrisches Rückgrat** (COLMAP/RealityCapture/Metashape).
  Schlägt End-to-End-KI klar: COLMAP mAAq **1.000** vs. VGGT 0.267 / Fast3R 0.124
  (ISPRS 2025). KI skaliert hochauflösende Fotos intern auf ~512 px → Detail weg.
  **Für präzise Architektur immer SfM als Geometrie-Wahrheit.**
- **Neuronal (2DGS, GOF, 3DGS) = KOMPLEMENTÄR**, kein Ersatz. Gewinnt bei **dünnen
  Elementen (Viadukt-Eisenwerk), reflektierenden/strukturlosen Flächen** (auf Glas:
  2DGS 96 % vs. Metashape 17 % Vollständigkeit). Saubere Mesh-Exporte:
  **2DGS** = Tiefenkarten→TSDF→Marching Cubes (DTU 0.80 mm vs. 3DGS 1.96 mm);
  **GOF** = Opacity-Level-Set→Marching Tetrahedra. Groß-Szene: **Block-PSPGOF**
  (Scene-Blocking). Drohnenfrei: **Gaussian Building Mesh** aus Google Earth Studio
  (scheitert an dünn/spiegelnd).
- **KI Bild/Text→3D** (Hunyuan3D 2.1 m. PBR, TRELLIS, Hi3D) = NUR Textur-/Detail-
  Füllung + schnelle Rohform, **nie metrisch präzise** → Fusionsrolle.
- **Daten-Fusion:** SfM + **CPD/FMR**-Registrierung fügt LiDAR/DGM + Photogrammetrie
  zusammen; Poisson-Hole-Fill; **repetitive Joche parametrisch vervielfältigen**.
- **⚠️ Widerlegt (NICHT drauf verlassen):** Photogrammetrie schlägt neural NICHT auf
  allen Achsen (Textur/dünn/spiegelnd → neural besser); Gen-KI ist NICHT „in
  Sekunden" schneller als SfM; Hunyuan3D 2.1 NICHT voll CC-BY.
- **Grenze der Studienlage:** kein direkter Linach-/Ravenna-Case; alles Analog-
  Strukturen (Fachwerkbrücken, Dämme, Stadtgebäude) → Übertrag ist inferentiell.

### Empfohlene Toolchain (nach Research)
1. Erfassen: Drohne + **geplanter** Flug (§9), >80 % Overlap, 300+ Fotos.
2. **COLMAP** (gratis) od. RealityCapture → dichte Wolke/Mesh, über bekannte Maße metrisch skaliert.
3. optional **2DGS/GOF** für dünne/strukturlose Partien → Mesh, einfügen.
4. **Fusion** mit LGL-DGM1 (CPD/ICP), Maße = Scale-Anker.
5. Cleanup: Poisson → Retopo → **parametrische Joch-Vervielfältigung** wo Coverage schlecht → Textur reprojizieren/baken.
6. Output: decimiert=GLB/HTML · wasserdicht=Druck · GPU-Render=Pitch.

### Fall-Zuordnung
- **Linachtalsperre** (matter Beton, kompakt): klassischer **SfM-Fall**, läuft sauber.
- **Ravennaviadukt** (groß, Stein + dünne/filigrane Teile): SfM **+ neural** für dünne/
  verdeckte Partien + **Block-Scene-Blocking** wegen Größe.
- Beide repetitiv → DGM-Gelände + parametrische Joche fusionieren.

> Flugplan-Rezept (Voxel/Overlap/Winkel/Fotozahl) siehe **FLUGPLAN_LINACHTALSPERRE.md**.

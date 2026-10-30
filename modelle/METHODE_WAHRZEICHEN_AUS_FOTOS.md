# Methode: Wahrzeichen-3D aus Fotos (halbautomatisch, schnell wiederholbar)

Ziel: aus Fotos (Google/Wikipedia/eigene) + amtlichen Daten ein **reines 3D-Modell**
(keine Textur, alle Details als Geometrie) eines markanten Bauwerks erzeugen — in einer
**Validier-Ratsche mit Vision-Juror-Ensemble**, die automatisch und stabil zum PASS
konvergiert. Gegenstück: Masse-Gebäude vollautomatisch aus LOD2 (keine Juroren nötig).

Diese Datei ist das **Rezept zum schnellen Start neuer Wahrzeichen** — jeder Schritt mit
den konkreten Fallen, die uns beim Historischen Kaufhaus Freiburg Zeit gekostet haben.

---

## Pipeline (7 Schritte)

0. **Foto ZUERST sezieren (Pflicht, vor jeder Zeile Code).** Das Foto zone-für-zone zoomen
   (PIL-Crops: Dach, Rake, Gauben, Erker/Helm, Traufe, Fenster, Statuen, Balkon, Arkade, Sockel)
   und eine **ELEMENT-SPEC** schreiben: welche Elemente gibt es, welche Form, welche Anordnung.
   PROPORTIONEN per Pixelmessung (Himmel/rote Fassade segmentieren → Dach/Fassade-Verhältnis).
   Die teuersten Irrwege kamen aus Bauen-nach-Annahme statt Foto-Studium (Vorhangbogen statt
   Kielbogen; Balkon/Dachstufen ganz vergessen). Siehe [[mess_getrieben_statt_meinung]].

1. **Daten holen.** Fotos sammeln (Frontal + schräg + Detail). Amtlich: LOD2 (Grundriss +
   Trauf-/Firsthöhe), DOP (Lage), DGM1 (Gelände). Maße aus Fotos **messen** — mit einem
   Referenzobjekt für den Maßstab (Tür, Mensch, Lok). Nicht raten.

2. **Parametrischer Generator** (Muster: `tools/kaufhaus_measured.py`). Reine Geometrie:
   - Fassadenwand = `shapely`-Polygon (Außenrechteck) **minus Löcher** (Bögen, Fenster) →
     `trimesh.extrude_polygon`. Löcher immer mit `.buffer(0)` säubern.
   - Alle Zahlen als Konstanten oben (W, D, EAVE, RIDGE, N_ARCH, nbay, ORIEL_X, …) — damit
     Juror-Fixes als reine Parameteränderung umsetzbar sind.
   - Bögen echt 3D (Rund-/Spitzbogen als Polygon-Leibung), Erker/Helme/Gauben/Statuen als
     eigene Mesh-Gruppen mit eigener Farbe (Export je Gruppe als STL + gemeinsames GLB).

3. **Render** (`tools/glb_render.py`, pyrender/EGL offscreen, venv `/tmp/rv`,
   `PYOPENGL_PLATFORM=egl`). Front + schräg. Für das Orientierungs-Gate orthografisch.

4. **Validierung — VALIDATOR ZUR FRAGEART PASSEN (ein „ist es gut?"-Juror reicht NIE):**
   Reihenfolge **Inventar → Mess-Check → Note** (vorne die großen fehlenden Teile fangen):
   - **Vollständigkeit** → **Inventar-Juror** zone-für-zone „was FEHLT/ist falsch" (JSON
     fehlt/falsch/ok). Fängt GANZ fehlende Elemente, die der Noten-Juror per Gestalt-Bias
     übersieht (Balkon/Dachstufen fand sonst erst der User). [[vollstaendigkeits_inventar_juror]]
   - **Proportion** (Dach:Fassade, L:H) → **Pixelmessung am Foto**, NICHT Juror (der oszilliert;
     Oszillation = Signal zum Messen).
   - **Anzahl** → Vermesser-Ensemble (Median), User/Foto override.
   - **Orientierung** (Flip/Schräg) → programmatisches Gate (`tools/modell_bewerter.py`, ortho).
   - **Form/Feinschliff** → Noten-Juror-Ensemble: 3 Agenten parallel (`subagent_type: claude`)
     → `python3 tools/juror_ensemble.py j1.json j2.json j3.json` (Median/Mehrheit/Konsens-Fixes).

5. **Ratsche (stabil!).** Aus dem Ensemble nur anwenden:
   - **einstimmige Bool-Flags** (z.B. `gauben_im_dach=false` 3/3 → sicher ein Bug),
   - Zählungen nur bei **schmaler Streuung** (sonst oszilliert der Juror — NICHT drauf
     reagieren),
   - jeden Fix **gegen das Foto kreuzprüfen** (LLM-Juror irrt: einer wollte „rotes Dach",
     Foto zeigt grün). Vor jeder Änderung Render nach `_prev/` sichern; kein Schritt darf ein
     schlechteres Ergebnis behalten (Note-Median / match-Quote muss steigen).

6. **Loop** bis `verdikt=PASS` (Mehrheit PASS **und** Note-Median ≥ 6). Autonom, ohne User.

7. **Ausliefern:** selbst-enthaltenes `*_3d.html` (three.js, GLB base64) + `*_3d.stl`.

---

## Gelernte Fallen (konkret — spart beim nächsten Modell Zeit)

- **Render-Azimut der Fassade kennen.** Die ornamentierte Seite kann **−Y** zeigen (Statuen/
  Erker ragen nach −y). Dann ist Front `az=270`, nicht 90 — sonst rendert man die blanke
  Rückwand und hält sie fälschlich für „Fassade kaputt". Immer am Render prüfen, ob Arkade/
  Fenster sichtbar sind.
- **Anbauten an die Trägerfläche klammern.** Gaubentiefe `proj` MUSS an die Dachgeometrie
  gebunden sein: `proj = min(proj, ys-0.5)` (ys = y-Lage der Dachhaut auf dieser Höhe), sonst
  ragt die Gaube über die Traufe (`yf = ys-proj < 0`). Untere Gaubenreihe hoch genug legen
  (frac ≥ 0.3), damit Dachtiefe zum Einbetten da ist.
- **Figuren auf die richtige Ebene stellen.** Statuen-Fußpunkt auf die **Galerie/Brüstung**
  (nicht ins Fensterband) + schlank halten — sonst liest der Juror „vor den Fenstern" statt
  „zwischen den Fenstern".
- **Juror-Zählungen streuen** (Bögen 4/5/5, Fächer 5/6/8). → **Ensemble** (Median/Mehrheit)
  statt Einzel-Juror. Die **einstimmigen Bool-Flags** sind die verlässlichen Signale.
- **Programmatische Struktur-Validatoren versagen** für Anzahl/Form (Kantenprofil, FFT,
  Blob — alle mit Zahlen belegt). Struktur nur per Vision-Juror; das programmatische Gate nur
  für Orientierung (Flip/Schräg).
- **Parametrik-Decke:** echte Figuren / durchbrochenes Maßwerk brauchen Mesh-Sculpting;
  Platzhalter-Geometrie (Kegel/Kugel) bleibt als „Pfeil/Sanduhr" erkennbar — bewusst
  akzeptieren oder gezielt ein Detail-Mesh laden.

---

## Werkzeuge (wiederverwendbar)

| Zweck | Tool |
|---|---|
| Parametrischer Modell-Generator (Vorlage) | `tools/kaufhaus_measured.py` |
| Offscreen-Render (EGL) | `tools/glb_render.py` |
| GLB → self-contained HTML | `tools/glb_html_viewer.py` |
| Orientierungs-Gate (Flip/Schräg) | `tools/modell_bewerter.py` |
| **Juror-Ensemble-Aggregator** | `tools/juror_ensemble.py` |
| Masse-Gebäude vollautomatisch | `tools/lod2_gebaeude.py` |

Siehe auch `modelle/METHODE_3D_AUS_ALLEN_DATEN.md` (Methodenwahl nach Datenlage) und
`modelle/METHODE_BAUWERK_AUS_DATEN.md` (scanfreie Bauwerk-Pipeline).

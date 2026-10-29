# Protokoll: Einheitlicher vollautomatischer Modell-Validator

Ziel: EIN Validator (tools/modell_validator.py), der Realität gegen Modell über ALLE Register
prüft und vollautomatisch einen Score + priorisierte Fixes liefert — damit wir generisch
möglichst gute Modelle bekommen. Grundregel: Validator zur Frageart passen; an bekannt-guten
Modellen KALIBRIEREN (Kaufhaus/Oberkirch liefen gut → müssen hoch scoren).

## Register (alle vollautomatisch) + Gewichte
| Register | Frageart | Quelle | Gewicht | Verlässlichkeit |
|---|---|---|---|---|
| MASSING | Proportion | GLB-BBox vs LOD2 (front_w/ridge) | 0.35 | hoch (amtlich) |
| FARBE | Farbtreue | Median-Fassadenfarbe Foto vs Render | 0.25 | hoch (Lücke gefüllt) |
| ANZAHL | Zahl/Anordnung | fenster_zaehler Foto vs Render | 0.20 | GROB (Detektor crop-sensitiv) |
| ORIENTIERUNG | Lage-Gate | Silhouetten-Massenverteilung | 0.10 | hoch (Gate) |
| SILHOUETTE | grobe Form | Breiten-Profil Foto vs Render | 0.05 | niedrig (perspektiv-gedeckelt) |
| FERTIGUNG | Druckbarkeit | watertight der Druck-STL | 0.05 | informativ (Anzeige-Mesh mehrteilig) |

## Läufe (Kalibrierung)
| Lauf | Kaufhaus | Oberkirch | Kornhaus | Befund |
|---|---|---|---|---|
| v1 (roh) | **0.25** | **0.28** | 0.69 | INVERTIERT — Validator kaputt, nicht Modelle |
| v2 (adaptiv+Fixes) | 0.57 | 0.32 | 0.75 | besser; ANZAHL-Detektor crop-instabil |
| v3 (ANZAHL grob, reweight) | **0.77** | **0.56** | **0.86** | kalibriert; gute Modelle hoch, Oberkirch-Höhe geflaggt |

## Lehren (chronologisch, jede sofort eingebaut)
1. **Validator an bekannt-guten Modellen kalibrieren.** v1 bewertete Kaufhaus/Oberkirch (gut)
   mit 0.25/0.28 UNTER Kornhaus (0.69) → Beweis, dass der Validator selbst falsch war. Ein
   Validator, der gute Modelle schlechtredet, ist wertlos ([[checker_taugt_nichts_lehre]]).
2. **Fenster-Detektor war Kornhaus-überfittet (nur weisse Wand).** Auf dem ROTEN Kaufhaus fand
   er 1 statt ~10 Fenster. Fix generalisiert: ADAPTIVE lokale Schwelle (Fenster = lokal dunkler
   als umgebende Wand, egal welche Fassadenfarbe) statt globalem Dunkel-Threshold. Kaufhaus 1→9.
3. **Richtiges Eingangsfoto zählt.** Oberkirch „ob_front.jpg" war das HÄNGESCHILD, nicht die
   Fassade → 3 Fenster. Frontalfoto ist ob_platz_jm3399.jpg. Validator braucht das Mess-Frontal.
4. **Fensterzählung ist crop-/kontrast-instabil** (Kornhaus 12 standalone → 6 im Validator-Crop,
   adaptive Schwelle content-abhängig). → ANZAHL als GROBER Sanity-Flag (±3 oder 40 % frei),
   NICHT als Feinscore. Sonst zieht Detektor-Rauschen gute Modelle runter.
5. **MASSING-Höhe braucht einseitige Toleranz.** Zier (Statuen/Finial) ragt über den LOD2-First
   (Kaufhaus 24.1 vs 21.4) — kein Fehler. Einseitig: zu KURZ bestraft, bis +18 % über First frei.
6. **FERTIGUNG darf Anzeige-Meshes nicht abstrafen.** measured.glb ist absichtlich mehrteilig
   (Farbgruppen) → nie watertight; Druck läuft über mesh_druckbar.py. → dedizierte *_3d.stl
   prüfen, sonst informativ (0.7), niedriges Gewicht.

## Echte Befunde, die der kalibrierte Validator fand (= sein Nutzen)
- **Oberkirch Höhe 15.5 m vs LOD2-First 21.0 m** → Dach zu kurz (Dach-zu-kurz-Falle,
  [[hybrid_alle_daten_lod2]]). MASSING=0.00, korrekt geflaggt.
- **Oberkirch Breite 8.1 m vs LOD2 9.4 m** → W noch geschätzt, nicht aus LOD2-Grundriss.
  GENERALISIEREN: front_w-Regel ([[alle_oeffentlichen_daten_mergen]]) auf den traufständigen
  bauwerk_generator ziehen (wie beim Kornhaus gemacht).
- **Kaufhaus Farbe ΔE 75** (Modell-Lichtelemente zu warm/tan vs Foto-grau) → Farbkalibrierung.

## Offene Generalisierungen (Roadmap)
1. front_w/depth aus LOD2-Grundriss auch im traufständigen Generator (Oberkirch/Kaufhaus) —
   lod2_gebaeude schreibt front_w_m bereits; nur alte LOD2-JSONs neu erzeugen + Generator lesen.
2. ANZAHL crop-invariant machen (feste statt std-basierte Schwelle, oder Zählung gegen die
   GEBAUTE Stückzahl aus fenster.json statt Neu-Detektion auf dem Render).
3. Perspektiv-Overlay (foto_modell_homografie) als SILHOUETTE-Ersatz einhängen (misst echte
   Abweichung statt perspektiv-gedeckelter IoU) — braucht verlässliche Passpunkte/Kalibrierung.
4. FARBE: pro Farbgruppe (Wand/Dach/Zier) statt nur Fassaden-Median.

## Nachtrag: Kornhaus-Fenster genauer (User: „fehlt ein Fenster, Form passt nicht")
Diagnose (durch genaues Hinsehen Modell vs Foto-Giebel):
1. **Adaptiv-Umbau regressierte den Kornhaus** (Lokalisierung brach: Box lief in Café/Nachbar,
   Giebelfenster verloren). Globale Schwelle ist für HELLE Putzfassaden am stabilsten → auf
   diese zurück (adaptiv nur als Auto-Fallback für dunkle/farbige Fassaden gedacht; aktuell
   deaktiviert, da Lokalisierung instabil). Kornhaus wieder sauber 13 Fenster, Box 0.33–0.73.
2. **Fensterform zu quadratisch** (h/w≈1.1), real HOCHKANT (h/w≈1.5–1.8). Ursache: Detektor
   misst das DUNKELGLAS, nicht die Öffnung — Himmel-Spiegelung/Bogen kappt oben → Höhe
   systematisch zu klein. Fix: physik. Prior im Generator (Mindest-h/w 1.5), kein Augenmaß.
3. OFFEN/ehrlich: exakte Form (Bogen-Oberkante + Kreuzstock-Teilung + Sandstein-Öffnung statt
   Glas-BBox) braucht KONTUR-Erkennung der Öffnung, nicht nur Dunkel-Blob-BBox. Giebel wirkt
   noch zu gestreckt (Stufenhöhe ~2 m); Giebelfenster evtl. kleiner als Prior.

LEHRE (hart, selbst): NICHT durch schnelles Parameter-Drehen „generalisieren" — der Adaptiv-
Umbau verbesserte das rote Kaufhaus, regressierte aber das Kornhaus. Jede Änderung gegen ALLE
bekannt-guten Fälle testen (Kalibrier-Suite), sonst Oszillation [[fehleranalyse_warum_oszillation]].

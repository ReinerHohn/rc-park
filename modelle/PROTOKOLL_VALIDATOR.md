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

## Nachtrag 2: Fenster-Durchbruch per ML (Option 1+2, Vollgas)
Heuristik-Wand bestätigt über 3 Ansätze → Wechsel auf ML: tools/fenster_ml.py (SegFormer
CMP-Facade, venv /tmp/ml). Farb-/perspektiv-robust, fängt Rundbögen. Dominant-Cluster trennt
Nachbarn (22→14). Multi-Foto-Konsens funktioniert NUR auf ML-Basis: Heuristik 13/3/5/10 (schräg/
Nacht kaputt) vs ML 14/13/14/17 → robuster Median 14. LEHRE: an der Heuristik-Rausch-Wand ist ein
vortrainiertes Open-Source-Netz (CPU reicht) der Hebel, nicht noch ein Schwellwert.

## Fehler-Log (laufend, auf User-Wunsch)
**F1 (2026-10-29) Koordinaten-Bezugssystem verwechselt.** Traufständig-Wiring: die regularisierten
x_fracs sind relativ zur FENSTER-Bounding-Box (schmaler als die Fassade). Ich habe sie als
FASSADEN-Bruchteile (×W) verwendet → Oberkirch-Fenster zu weit gespreizt, ragten über den Rand.
User: „zu schmal, Fenster ragen raus, davor war es besser." ROOT: Bezugssystem nicht geprüft
(Detektor-Box ≠ Fassade); Mess-Box ≠ exakter Fassadenrand → Umrechnung asymmetrisch. META-FEHLER
(wieder): committet + „funktioniert" gesagt, BEVOR ich den Render an den Rändern/Proportionen
genau geprüft habe (die Fenster am Rand waren sichtbar, ich hab's übersehen) → [[score_ist_nicht_hinschauen]].
FIX: fenster_auto aus Oberkirch-Config raus → zurück auf fassade_messen (funktioniert). LEHRE:
(1) vor JEDER Übernahme von Detektor-Koordinaten das Bezugssystem explizit umrechnen + prüfen;
(2) nach JEDER Änderung Render GANZ anschauen (Ränder, Breite, Proportion), nicht nur „passt grob".

**F2 (2026-10-29) Guten Stand kaputtgeaendert + nicht am Render geprueft.** Oberkirch-Zierband
von gemessen (gut) auf 9.25 verschoben -> „wieder Schrott", weil nicht am Render/Foto kontrolliert
(wieder [[score_ist_nicht_hinschauen]]). KONSEQUENZ (harter Beweis statt Worte): tools/aenderung_check.py
(VORHER|NACHHER|Heatmap|FOTO) gebaut und an genau diesem Fehler vorgefuehrt -> lokalisiert die
Band-Linie unuebersehbar. PFLICHTPROZESS: nach JEDER Aenderung aenderung_check laufen lassen,
Heatmap gegen Foto pruefen, erst dann 'verbessert' sagen; sonst sofort zurueck (git). Siehe
memory aenderungs_waechter_pflicht.

## F3 (2026-10-29): Gauben — VERSTECKTER Hardcode (Clamp überschrieb die Messung) + Überkorrektur
Fehler, zwei Lagen:
1. **Clamp fraß die Messung.** `DORMER_H = max(min(DORMER_H, 1.4), 1.3)` zog die aus
   gauben_mass.json GEMESSENE Höhe (0.95 m) stillschweigend auf 1.3 m hoch. Ein Guard, der den
   gemessenen Wert ÜBERSCHREIBT, ist ein verdeckter Hardcode — verletzt [[kein_hardcoding_alles_erkennen]].
   Dazu war dormer_w_m=2.04 selbst falsch (am falschen Bezug gemessen) → Gauben ~2× zu groß.
2. **Überkorrektur der Reihenhöhe.** Davor base 0.11→0.30 UND gap 0.21→0.33 in EINEM Rutsch →
   obere Reihe schoss an den First (Oberkante Gaube z=15.45 bei First 16.6 = nur 1.15 m Luft).
   Klassische „ins Gegenteil überschießen"-Falle ([[parametrisch_gueltig_nie_degeneriert]]).
Fix: w 2.04→1.05, h-Clamp 1.1 (Messung 0.95 kommt durch), gap 0.33→0.27 (Dach bleibt ÜBER der
oberen Reihe). GEMESSEN am Dachebenen-Crop (Öffnung ~20px @ ~24px/m → ~0.8m + Rahmen = 1.05m).
**Beweis gelernt (Mechanismus):** aenderung_check VOR dem „verbessert": 2.6% geändert, Region
NUR die Gaubenzone — Rest unberührt; Zoom-Vergleich Render-Dach↔Foto-Dach bestätigt kleiner +
obere Reihe tiefer. Erst dann committet (10e6bd4).
LEHRE generell: (a) jeder Clamp/Default, der eine Messung nach oben/unten zwingt, ist verdächtig —
Messung durchlassen, nur echte Degeneration abfangen. (b) nie zwei Positions-Parameter gleichzeitig
groß drehen; eine Änderung, Wächter, dann die nächste.

## F4 (2026-10-29): Pfeiler — wieder Überkorrektur (zu kurz -> Stumpf in der Luft)
User wollte: Pfeiler nicht bis zum Balkon, sondern „in den Bogen übergehen", ohne die zwei
Kapitell-/Impost-RINGE. Ich habe (a) die Ringe entfernt (richtig) ABER (b) PIER_H von ARC_APEX
auf ARC_SPRING halbiert -> Pfeiler endeten am Kämpfer als abgeschnittener Stumpf, besonders UNTER
DEN ERKERN, wo der Bogen nur auf der Innenseite ansetzt -> „Säule hängt in der Luft". Dazu war die
Pfeilerfarbe heller [138,48,42] als die Fassade [116,38,34] -> sichtbarer Farbsprung.
Fix: PIER_H zurück auf ARC_APEX (Pfeiler steigen MIT dem Bogen bis zum Scheitel, Apex 5,2 < Balkon 5,4
= trotzdem nicht bis zum Balkon) + Pfeilerfarbe = Fassadenrot -> fließend, gleichfarbig.
LEHRE (3. Mal dieselbe Klasse, vgl. F3 Gauben, Oberkirch-Band): „X soll weniger weit gehen" heißt
NICHT „X radikal halbieren". Erst das MINIMALE zielgerichtete Delta (hier: nur die Ringe weg) testen
und ansehen, bevor man auch noch die Grundgeometrie (Höhe) ändert. Ein geometrisches Element, das
ein anderes trägt/überleitet (Pfeiler->Bogen), darf man nicht kürzen, ohne zu prüfen, ob der Übergang
erhalten bleibt — sonst entsteht ein Stumpf. Immer Render ansehen (Änderungs-Wächter), BESONDERS die
Sonderfälle an den Rändern/unter Anbauten (Erker), nicht nur die Regelmitte.

## F5 (2026-10-29): warum erst JETZT gefunden (Spitzbögen, Gold-Helm, Pfeiler-Gold, Dächlein)
Vom User gefunden, nicht von mir: (1) Arkade RUND statt SPITZ, (2) Erker-Helme golddominant statt
bunt glasiert, (3) senkrechte Gold-Lisene + Kapitellringe an Pfeilern existieren gar nicht,
(4) Walm-Dächlein zu flach. WARUM übersehen — 4 verschiedene Ursachen, eine gemeinsame Wurzel:
- **Spitzbögen**: ich habe einer EIGENEN alten Notiz/einem Juror vertraut („Arkade ist rund, Foto/Juror")
  statt das Foto JEDES MAL selbst neu zu lesen. Anker auf vergangener Schlussfolgerung statt Grundwahrheit.
  -> Eigene Notizen/Juror-Urteile sind KEINE Grundwahrheit; das Foto schlägt beide (vgl. [[vision_juror_ratsche]]).
- **Gold-Helm**: nur auf GEBÄUDE-Ebene (Gestalt „bunter Helm = ok") geprüft, nie einen Nah-Crop MEINES
  Helms neben einen Nah-Crop des ECHTEN gelegt. Element-Nahvergleich (vom User erzwungen) zeigte sofort
  Gold-Dominanz + Schachbrett statt Farbbänder.
- **Pfeiler-Gold/Ringe**: SPEKULATIV hinzugefügte „plausible" Zierde („feines Gliederungsdetail"), nie
  gegen das Foto verifiziert. ÜBER-GENERIERUNG ist eine eigene Fehlerklasse — Details ERFINDEN ist so
  falsch wie Details übersehen.
- **Dächlein**: Geometrie war da, aber nur in der FRONT-Ansicht geprüft, wo Walmdächer edge-on
  verschwinden -> sah aus wie flache Löcher. Nie eine 3/4-Ansicht gerendert.
GEMEINSAME WURZEL: in der FALSCHEN GRANULARITÄT und gegen die FALSCHE REFERENZ geprüft (Gestalt +
eigene Notizen statt Element-Nahvergleich gegen das Foto, und nur EIN Blickwinkel).
KONSEQUENZ (neuer Pflicht-Pass, generisch): tools/element_fotovergleich.py — schneidet je Bauteil
(Helm/Gaube/Pfeiler/Bogen/Fenster/Statue) denselben Ausschnitt aus Render UND Foto und legt sie
paarweise nebeneinander; zusätzlich IMMER mind. 2 Blickwinkel rendern (front + 3/4), weil 3D-Details
head-on verschwinden. Und: aktiv auch nach ZUVIEL suchen (habe ich etwas gebaut, das im Foto fehlt?).

## F6 (2026-10-29): GENERELLE LEHRE — Whack-a-Mole, weil nie ein VOLLSTÄNDIGER Mehrflächen-Audit
Der User musste Fehler für Fehler selbst finden (Erker-Fenster nur vorn, Sockel grau, Statuen-Nische
dunkel, Seitenfenster außerhalb/zu wenig, GAUBEN-Form, obere Giebelfenster fehlen). JEDER einzelne
war am FOTO sofort sichtbar — ich habe nur nie systematisch ALLE Flächen gegen ALLE Fotos geprüft,
sondern reaktiv auf den jeweils genannten Punkt. ROOT CAUSE (generell, teuer, wiederholt):
„fertig/besser" gesagt nach FRONT-Ansicht + genanntem Element, statt nach einem VOLLSTÄNDIGEN
Inventar über alle Ansichten.
GENERELLE KONSEQUENZ (Pflicht vor „fertig" bei JEDEM Gebäude):
1. ALLE Ansichten rendern: front, LINKS, RECHTS, 3/4 links, 3/4 rechts, Dach-Aufsicht. Nicht nur front.
2. ALLE vorhandenen Fotos nebeneinander (nicht nur das Frontfoto) — jedes Bauteil auf JEDER Fläche.
3. Element-Inventar zone-für-zone (vgl. [[vollstaendigkeits_inventar_juror]]): für jede Fläche
   auflisten FEHLT / FALSCH / ÜBERFLÜSSIG — erst dann Note/„fertig".
4. Aktiv auch nach ZU WENIG (fehlende Fenster/Flächen) UND ZU VIEL (erfundene Zierde) suchen.
Das ist dieselbe Wurzel wie F5 (falsche Granularität/Referenz) — jetzt verschärft: nicht nur
Element-Nahvergleich, sondern VOLLSTÄNDIGKEIT über alle Flächen, BEVOR ich dem User etwas zeige.

## F7 (2026-10-29): goldener Überhang — ineffizient diagnostiziert + beim Fix ÜBER das Ziel hinaus
Zwei Lehren aus einem Vorgang:
1. **Diagnose ineffizient.** Ich habe ~6 Runden „Element auskommentieren → rendern → schauen"
   gebraucht, um das Überhang-Element zu finden. Die DEFINITIVE Methode (jedes verdächtige Teil in
   EINE eigene Farbe umfärben, EIN Render → man SIEHT sofort, welches Teil es ist) habe ich erst
   zuletzt genutzt. REGEL: bei „welches von N Teilen erzeugt diesen Pixel?" ZUERST Farb-Isolation
   (ein Render, N Farben), nicht serielles Deaktivieren.
2. **Fix größer als nötig → Kollateralschaden.** Der Überhang war NUR die durchlaufende Gold-
   Sohlbank. Ich habe aber „sicherheitshalber" AUCH Rahmen + Transom auf out=0 geflacht → der
   Querbalken (Transom) versank im Glas → Fenster kaputt (User fand's). REGEL: nur das
   IDENTIFIZIERTE Teil ändern; nicht benachbarte Teile „mitnehmen". Und nach dem Fix das GANZE
   betroffene Bauteil (hier: das Fenster selbst, Querbalken/Pfosten) nachprüfen — nicht nur die
   Artefakt-Stelle. (Gleiche Wurzel wie F3/F4: Überkorrektur + nur die Zielstelle statt des ganzen
   Bauteils geprüft.) Verschärft [[parametrisch_gueltig_nie_degeneriert]] + [[aenderungs_waechter_pflicht]].

## F8 (2026-10-29): Helm-Überkorrektur — EINE Eigenschaft gemeint, ZWEI geändert
URSACHE, warum ich den Bug ausgelöst habe:
Problem war NUR die BREITE: der Helm-Fuß (cr0*1.30 = 1.56) war breiter als der Erker-Körper
(w/2 = 1.25) → überkragte wie ein Kreisel. Die EINE verantwortliche Stellschraube war cr0 (Radius).
Ich habe aber ZWEI Dinge gleichzeitig geändert:
  (a) cr0 kleiner  — richtig, löst den Überhang.
  (b) das PROFIL plattgemacht: prof-Fuß von [(cr0*1.30,…),(cr0*1.08,…)] auf [(cr0,…),(cr0*0.99,…)]
      — das hat die KONKAVE Glockensilhouette zerstört (gerader Kegel) = ein Feature gekillt, das
      der User mochte und das gar nicht das Problem war.
Ich habe also „Überhang" (ein GRÖSSEN-Problem) mit der FORM verwechselt und beides angefasst.
LEHRE (gleiche Wurzel wie F3/F4/F7, jetzt auf PARAMETER-Ebene): wenn der User „X ragt über /
ist zu breit" sagt, ist das ein GRÖSSEN-/LAGE-Problem → NUR den Größen-/Lage-Parameter drehen
(hier cr0), NIE die Form-Parameter (Profil/Silhouette) „sicherheitshalber" mitändern. Vor dem Edit
fragen: „welche EINE Variable steuert genau die gemeldete Eigenschaft?" — nur die ändern, Rest fix
lassen. Fix: konkaves Profil zurück + nur cr0=w*0.38 (Fuß ≈ Körperbreite). Verschärft [[parametrisch_gueltig_nie_degeneriert]].

## F9 (2026-10-29): erfundenes Feature (Seiten-Durchgang) nie gegen Foto geprüft
Der Giebelseiten-„Eck-Durchgang" (round_arch in der Seitenwand) existiert am realen Kaufhaus GAR
NICHT (Foto pe_side: massive Giebelwand) und lag ausgerechnet vor der Arkaden-Rückwand → durch die
Öffnung sah man die rote Wand bis zum Boden = „hängt da rum / geht zum Boden" (User, verwirrt).
Das Feature stammte aus einer früheren Runde und ich habe es im Mehrflächen-Audit zwar GESEHEN,
aber als gegeben hingenommen statt gegen das Foto zu prüfen.
LEHRE: der Audit muss auch BESTEHENDE Features hinterfragen „gibt es das am Original überhaupt?",
nicht nur fehlende/falsche suchen. ÜBER-Generierung (erfundene Durchgänge/Lisenen/Kapitellringe,
vgl. F5) ist eine eigene Fehlerklasse — jedes Bauteil braucht einen Foto-Beleg, sonst raus.
Diagnose hier sauber per FARB-ISOLATION (laube/piers/glas je eigene Farbe, ein Render) → sofort
sichtbar dass die Arkaden-Rückwand (laube) durch den Durchgang schien (vgl. F7/F8: Farb-Isolation zuerst).

## F10 (2026-10-29): Torbogen GANZ entfernt statt nur sauber gemacht (Überkorrektur, 2. Mal)
User war über Clutter im Seiten-Durchgang verwirrt → ich habe den Durchgang KOMPLETT entfernt.
Der ist aber real der begehbare Laube-Durchgang (Torbogen) an den Arkaden-Enden → User wollte ihn
behalten, nur clutterfrei. Exakt die F7/F8-Wurzel: statt die EINE Ursache (Rückwand schien durch)
zu beheben, das ganze Feature gelöscht. Richtig gewesen wäre von Anfang an: Öffnung nach vorn +
Rückwand an den Eck-Jochen weg → durchsichtig. LEHRE (jetzt wirklich einbrennen): bei „X stört/
sieht falsch aus" NIE X löschen, sondern die konkrete störende Eigenschaft minimal beheben; Löschen
nur wenn das Feature NACHWEISLICH (Foto) nicht existiert (vgl. F9, wo es wirklich nicht existierte —
hier existiert es doch). Vor Löschen eines Features: „gibt es das am Original?" am Foto klären.

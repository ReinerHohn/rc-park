# KI-gestuetztes parametrisches Modellieren realer Gebaeude: Methoden, Werkzeuge, Arbeitsmuster (Stand 15.11.2026)

Hinweise zur Lesart:
- "Belegt (Primaerquelle gelesen)" = Zahl stammt aus der abgerufenen Originalseite. "Nur Suchtreffer" = Zahl stammt aus einem Suchausschnitt oder einer Zweitquelle und ist NICHT an der Primaerquelle geprueft.
- Die beiden frueheren Berichte (LIMAP, Orthofoto-Stapel, Sweep-Staerkung, CMA-ES-Parameterfit an Fotokanten, DiffCSG, nvdiffrast-Lizenz) werden hier nicht wiederholt, nur dort erwaehnt, wo neue Belege sie stuetzen oder einschraenken.
- Alle Benchmarks unten betreffen Maschinenbauteile oder Blender-Szenen. Fuer historische Gebaeude/Fassaden wurde KEIN Benchmark eines LLM-Code-CAD-Agenten gefunden. Uebertragungen stehen deshalb unter "Inferences".

## 1. LLM/VLM-getriebene CAD-Erzeugung 2024-2026: Systeme, Benchmarks, welches Feedback hilft

### Takeaway
Belegt ist: Rueckmeldung aus Renderbildern verbessert Code-CAD messbar, aber wenig (rund 10-20 % weniger Punktwolkenabstand) und nur fuer ein bis zwei Runden; danach wird es oft schlechter. Die grossen Spruenge kommen aus exakten, vom Geometriekern gemessenen Zahlen (Bounding-Box, Volumen, Gueltigkeit) und aus typisierten Bestanden/Nicht-bestanden-Urteilen mit Fehlbetrag, nicht aus dem Blick des VLM auf das Bild.

### Cited Findings

**CADCodeVerify (ICLR 2025, CadQuery, Benchmark CADPrompt mit 200 Objekten) - Primaerquelle gelesen**
- Verfahren: Das VLM erzeugt selbst Ja/Nein-Pruef­fragen zum Objekt, beantwortet sie an vier Renderansichten (0, 90, 180, 270 Grad) und korrigiert danach den Code. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- GPT-4 few-shot: Punktwolkenabstand ohne Verfeinerung 0,155, mit 3D-Premise 0,137, mit CADCodeVerify 0,127, mit Geometrie-Loeser gegen die Sollgeometrie (Obergrenze, braucht Ground Truth) 0,103. Kompilierrate 96,0 % / 91,0 % / 96,5 % / 95,5 %. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Rueckmeldung OHNE Bilder (nur Text) bringt fast nichts: Punktwolkenabstand 0,153 statt 0,156; mit Bildern und Beispiel-Fragen 0,126; ohne Beispiel-Fragen 0,141 (Ablation, 100 Stichproben). — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Mehr Runden helfen nicht: Die Autoren nutzen zwei Runden, weil "no improvement was observed beyond the second refinement". In mehreren Zeilen ist Runde 2 schlechter als Runde 1 (GPT-4 zero-shot 0,146 -> 0,159; Gemini few-shot 0,166 -> 0,178; CodeLlama-Kompilierrate 70,0 % -> 47,0 %). Die Zeile "Best Refine" ist nachtraeglich ausgewaehlt, das Auswahlverfahren ist nicht erklaert. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Das VLM beantwortet seine eigenen Pruef­fragen nur zu 64,6 % (Runde 1) bzw. 68,2 % (Runde 2) richtig; 26,6 % bzw. 19,3 % der Antworten sind "Unclear"; 8,8 % bzw. 12,5 % sind falsch. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Mensch in der Schleife (50 Beispiele, GPT-4 few-shot): Punktwolkenabstand 0,156 (ohne), 0,137 (CADCodeVerify), 0,120 (menschliche Rueckmeldung). Der Mensch schlaegt also die Selbstpruefung, erreicht aber nicht die Obergrenze des Geometrie-Loesers. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Fehlerarten: 48 % "Structural Configuration Error" (falscher Aufbau/Anordnung), 18 % Logikfehler. Die Autoren nennen Punktwolken- und Hausdorff-Abstand selbst "noisy"; kleine Spalte (Tischbein beruehrt Platte nicht) werden nicht erkannt. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Code und Daten: github.com/Kamel773/CAD_Code_Generation (Lizenz nicht geprueft). — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)

**CADSmith (arXiv 2603.26512, Maerz 2026, CadQuery) - Abstract gelesen**
- Mehragenten-Kette mit zwei verschachtelten Schleifen: innen Ausfuehrungsfehler beheben, aussen "programmatic geometric validation" mit exakten Messwerten aus dem OpenCASCADE-Kern (Bounding-Box-Masse, Volumen, Gueltigkeit des Koerpers) plus ein unabhaengiges VLM als "Judge". API-Wissen kommt per Retrieval aus der Dokumentation statt per Feintuning. — [arXiv 2603.26512](https://arxiv.org/abs/2603.26512)
- Ergebnis gegen Zero-Shot (100 Prompts, drei Schwierigkeitsstufen): Ausfuehrungsrate 95 % -> 100 %, Median-IoU 0,8085 -> 0,9629, Median-F1 0,9707 -> 0,9846, mittlerer Chamfer-Abstand 28,37 -> 0,74. — [arXiv 2603.26512](https://arxiv.org/abs/2603.26512)
- Repo laut Suchtreffer: github.com/jabarkle/CADSmith (Lizenz nicht geprueft). — [GitHub CADSmith](https://github.com/jabarkle/CADSmith)

**Agenten mit FEA-Rueckmeldung (arXiv 2605.17448, 2026, CadQuery) - Primaerquelle zu zwei Dritteln gelesen**
- Aufbau: Coding-Agent schreibt CadQuery, exportiert STEP; ein deterministischer Controller fuehrt Werkzeuge aus und gibt Berichte zurueck. Optional: Blueprint-Stufe (YAML-Entwurfsplan mit geschlossener Grammatik parametrischer Primitive), 21-Ansichten-Render, FEA mit typisierten Urteilen. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Eine einzige Rueckmelderunde hebt die mittlere Anforderungserfuellung deutlich, z. B. GPT-5.5 high Mehrteil-Aufgaben 8,3 % -> 39,2 %, GPT-5.4 high Einzelteil 23,3 % -> 42,1 %; bei Opus-4.7 xhigh Einzelteil dagegen 32,7 % -> 31,4 % (keine Verbesserung). Streng bestanden (alle Anforderungen): 0 von 50 bei allen Modellen ausser einem Fall. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Langer Lauf (bis 10 Versuche, im Mittel 68 Minuten je Teil): 60,5 % mittlere Anforderungserfuellung, 9 von 50 streng bestanden. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Viele Ansichten: Render-Rueckmeldung brachte bei GPT-Modellen im Mittel etwa +6,3 Punkte; 7 Ansichten waren bei einfachen, von aussen bestimmten Objekten teils gleich gut oder besser als 21. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Kernaussage zur Feedback-Art: Die meisten Reparaturen, die zum strengen Bestehen fuehrten, waren in Renderbildern NICHT sichtbar; sie hingen an Zahlenurteilen mit Fehlbetrag. Beispiel: Flaechendichte um mehr als eine Groessenordnung falsch bei unauffaelliger Silhouette. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Rueckmeldung wurde gestuft: erst nur Urteil bestanden/nicht bestanden, ab Versuch 6 zusaetzlich Fehlbetrag und betroffene Stelle/Lastfall. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Blueprint-Planung wirkte gemischt: IoU 0,444 -> 0,592 auf einem Datensatz (GPT-5.5), fast kein Effekt auf dem FEA-Benchmark fuer GPT (+0,3 Punkte), +3,9 Punkte fuer Claude. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Kein lernendes Skill-Gedaechtnis: Das "Skill" ist ein statisches Planungspaket (23 Dateien, rund 50.000 Zeichen). — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)

**BlenderGym (2025, VLM editiert Blender-Python, um ein Zielbild zu treffen) - Primaerquelle gelesen**
- Menschen (10 durchschnittliche Blender-Nutzer, 8 Minuten je Aufgabe) schlagen alle VLM-Systeme in jeder Spalte; Beispiel prozedurale Geometrie: Chamfer 0,334 (Mensch) gegen 1,192 (GPT-4o). — [arXiv 2504.01786](https://arxiv.org/html/2504.01786v1)
- VLM als Pruefer ("welches von zwei Renderbildern ist naeher am Ziel"): Uebereinstimmung Mensch-Mensch 0,79, bester VLM-Pruefer (Claude 3.5 Sonnet) 0,66, Zufall 0,5. Ein Modell (Qwen) bevorzugt stur den zweiten Kandidaten (Positions-Bias). — [arXiv 2504.01786](https://arxiv.org/html/2504.01786v1)
- Pruefer oefter laufen lassen hilft; bei kleinem Budget (<30 Abfragen) lohnt mehr Erzeugung, bei grossem (>100) ein hoeherer Pruefanteil. Kosten rund 0,45 USD je 100 Abfragen. — [arXiv 2504.01786](https://arxiv.org/html/2504.01786v1)
- Fehlerarten: Erzeuger halluziniert Unterschiede oder uebersieht feine; Code-Aenderung passt nicht zum erkannten Bildunterschied, besonders bei Skripten ueber 80 Zeilen; prozedurale Geometrie und Material sind am schwersten. — [arXiv 2504.01786](https://arxiv.org/html/2504.01786v1)

**Weitere Systeme (nur Abstract oder Suchtreffer)**
- CAD-Recode (ICCV 2025): Punktwolke -> CadQuery-Code, trainiert auf 1 Mio. prozedural erzeugten Programmen, Qwen2-1.5B plus Punktwolken-Projektor. Projektseite: 10-fach geringerer Chamfer-Abstand und ueber 20 % hoehere IoU als Vorgaenger auf DeepCAD/Fusion360. Zahl "IoU 92,0 %, CD 0,30 auf DeepCAD" NUR aus Zweitquelle. — [Projektseite CAD-Recode](https://cad-recode.github.io); [Review (Zweitquelle)](https://www.themoonlight.io/review/cad-recode-reverse-engineering-cad-code-from-point-clouds)
- CADReasoner (arXiv 2603.29847, 2026): trainiertes Modell, das die eigene CadQuery-Vorhersage iterativ verbessert; Eingabe sind Mehransicht-Render UND Punktwolke, das gerenderte Netz der letzten Vorhersage wird im naechsten Schritt wieder eingespeist. Die Autoren begruenden das damit, dass agentenbasierte Verfahren durch "weak 3D grounding in frozen VLMs" begrenzt seien. Zahlen (IoU 90,0 DeepCAD, 83,1 Fusion360 nach 5 Schritten) NUR aus Suchausschnitt. — [arXiv 2603.29847](https://arxiv.org/abs/2603.29847)
- CADGenBench (Hugging Face, Code Apache-2.0): Aufgaben "Zeichnung -> STEP" und "STEP editieren". Wertung: Gueltigkeit als Tor (Fehlschlag setzt alles auf null), Formaehnlichkeit (Oberflaechenabstand-F1, Volumen-IoU), Schnittstellen-Treffer ueber Keep-in/Keep-out-Teilvolumen, Topologie ueber Betti-Zahlen. Referenz-Agent: schreibt build123d (CadQuery moeglich), exportiert und validiert STEP, rendert im Prozess mit PyVista/VTK, sieht die Bilder an, verbessert. Keine Rangliste auf der README-Seite. — [GitHub cadgenbench](https://github.com/huggingface/cadgenbench)
- CadEval (Epoch AI): Text -> CAD-Programm (OpenSCAD-artig), Wertung ueber Render-Erfolg, Chamfer-/Hausdorff-Abstand, Volumenpruefung mit strengen Schwellen. Die Seite nennt weder Schwellen noch Modellwerte. — [Epoch AI CadEval](https://epoch.ai/benchmarks/cad-eval)
- LL3M (arXiv 2508.08228, 2025): Mehragentensystem schreibt Blender-Python fuer Einzelobjekte; "BlenderRAG" (Retrieval ueber Blender-API-Doku), Selbstkritik an Code und Bild, Nutzer gibt laufend Korrekturen. Keine Zahlen im Abstract. Die Autoren halten fest, dass ein LLM, das direkt Blender-Skripte schreibt, minderwertige oder nicht lauffaehige Ergebnisse liefert. — [arXiv 2508.08228](https://arxiv.org/abs/2508.08228)
- SceneCraft (2024): innere Schleife (Blender-Skript, rendern, Selbstkritik) und aeussere Schleife, die eine Bibliothek wiederverwendbarer Funktionen aufbaut. — [arXiv 2403.01248](https://arxiv.org/pdf/2403.01248)
- 3DCodeBench (nur Zweitquelle): Benchmark fuer VLM-Agenten bei prozeduraler 3D-Erzeugung, 12 Modelle, Skripte im Median 387 Zeilen, VLM-"Visual Critic" vergleicht Mehransicht-Render mit Referenzbildern. — [hyper.ai Zusammenfassung](https://hyper.ai/en/papers/2606.01057)
- Zero-to-CAD (arXiv 2604.24479, nur Suchtreffer): LLM mit Werkzeugzugriff in der Interpreter-Schleife erzeugt rund eine Million lauffaehige Konstruktionsfolgen. — [alphaxiv 2604.24479](https://www.alphaxiv.org/abs/2604.24479.md)

**Praxisberichte Blender-MCP mit Claude (Blogs, kleine Stichproben, nicht kontrolliert)**
- Brauchbar fuer Szenenaufbau, Kamerasetzen, einfache harte Formen (ein Autor nennt eine erkennbare Burg); schwach bei organischen Formen; Ergebnisse schwanken stark von Lauf zu Lauf. — [mindstudio.ai](https://www.mindstudio.ai/blog/claude-blender-mcp-real-world-performance); [3daistudio.com](https://www.3daistudio.com/3d-generator-ai-comparison-alternatives-guide/blender-mcp)

### Inferences
- Das eigene Abnahmeskript (Masstabelle + Kanten-F1 je Teil) entspricht dem, was in der Literatur am staerksten wirkt: exakte Kernmessungen und typisierte Urteile. Der Zeitverlust liegt vermutlich nicht am Tor, sondern an der Zahl der Runden und daran, dass das Tor nur "bestanden/nicht" liefert. Die FEA-Arbeit zeigt, dass Urteil + Fehlbetrag + betroffene Stelle zusammen wirken. Uebertragen: Je fehlgeschlagener Pruefung dem Agenten die Stelle (Teil, Kante, Foto), die Richtung und den Betrag in Millimetern nennen ("Erkersims 38 mm zu tief in Foto 6117"), nicht nur F1.
- Rundenzahl hart begrenzen: zwei bis drei Verfeinerungsrunden je Teil, danach nicht weiter iterieren, sondern Ansatz wechseln (anderes Template, Mensch klickt Punkte). CADCodeVerify und BlenderGym zeigen beide, dass lange Selbstkorrektur-Ketten abdriften.
- Besser als eine lange Kette: mehrere unabhaengige Kandidaten parallel erzeugen und das deterministische Tor (nicht das VLM) den besten waehlen lassen. BlenderGym belegt den Nutzen von Kandidatenvielfalt bei kleinem Budget; die eigene Foto-F1 ist ein staerkerer Waehler als ein VLM mit 0,66 Uebereinstimmung.
- VLM-Blick auf Renderbilder nur fuer grobe Strukturfragen nutzen ("Hat der Erker ein Dach? Sitzt das Gesims ueber oder unter den Fenstern?"), als Ja/Nein-Fragenliste, die aus der Teilbeschreibung erzeugt wird. Antworten "unklar" sind haeufig (rund ein Viertel) und duerfen nicht als "passt" zaehlen.
- 4 bis 7 Ansichten reichen fuer Aussenformen; mehr Ansichten kosten Kontext ohne belegten Nutzen.
- Skripte klein halten: BlenderGym nennt Fehlzuordnung zwischen Bild und Code ab etwa 80 Zeilen. Die vorhandene Gliederung "eine Funktion je Bauteil" ist richtig; je Runde dem Agenten nur die Funktion des einen Teils plus dessen Fotos/Render geben.
- Eine Teilebibliothek, die der Agent abruft statt neu zu schreiben (SceneCraft-Muster, CADSmith-Retrieval), ist der plausibelste Hebel von "Tage" auf "Stunden": Erker, Baldachin, Rippe einmal als parametrische Funktion mit Belegen, beim naechsten Bau nur Parameter setzen.
- Feingetunte Punktwolke-zu-CAD-Modelle (CAD-Recode, CADReasoner) sind auf Maschinenbauteile aus Skizze+Extrusion trainiert und laufen ueber die dichte Wolke. Fuer dieses Projekt passen sie weder zur Kernmethode (Form aus Fotokanten) noch zum Formenschatz. Vermutung: kein Nutzen.

### Gaps
- Kein Benchmark gefunden, der Code-CAD-Agenten an Gebaeuden oder Fassaden misst. Alle Zahlen stammen von Maschinenbauteilen (DeepCAD, Fusion360, CADPrompt) oder Blender-Szenen.
- Keine kontrollierte Studie gefunden, die Tiefen-/Normalen-Render, numerische Fehlerkarten oder Differenzbilder als Feedback direkt gegen RGB-Render vergleicht. Die FEA-Arbeit sagt selbst, dass sie Bild gegen Zahl nicht isoliert getestet hat.
- CAD-Coder, Text2CAD, Img2CAD, 3D-PreMise: in dieser Recherche nicht an Primaerquellen geprueft; 3D-PreMise erscheint nur als Vergleichszeile bei CADCodeVerify.
- Fuer manifold3d als LLM-Ziel wurde keine Veroeffentlichung gefunden; alle Arbeiten nutzen CadQuery, build123d, OpenSCAD oder Blender-Python.
- Ranglisten von CADGenBench und CadEval nicht abrufbar; welche Modelle Ende 2026 vorn liegen, ist hier offen.
- CADSmith: Einzelbeitraege der Feedback-Bausteine (Ablation) und verwendete Modelle stehen nur im Volltext, nicht gelesen.

## 2. Inverse prozedurale Modellierung und Formprogramme fuer Gebaeude/Fassaden

### Takeaway
Es gibt kein fertiges offenes Werkzeug, das aus kalibrierten Fotos ein editierbares Fassadenprogramm in Druckqualitaet liefert. Belegt sind Bausteine: Split-Grammatik aus segmentierter Fassade (FaçAID), Grammatikauswahl plus ableitungsfreie Parameteranpassung an die Silhouette (Nishida 2018, BOBYQA), Transformer von Punktwolke zu Gebaeudeprogramm (Google 2025).

### Cited Findings
- FaçAID (2024, SIGGRAPH-Poster): Transformer wandelt eine segmentierte, flache Fassade in eine prozedurale Definition in einer eigenen Split-Grammatik um, die danach editierbar ist. — [arXiv 2406.01829](https://arxiv.org/html/2406.01829v2)
- "Synthesizing 3D Abstractions by Inverting Procedural Buildings with Transformers" (Google, CVPR-2025-Workshop SynData4CV): Transformer wird auf prozedural erzeugten Gebaeuden mit simulierten Punktwolken trainiert und gibt zu einer Punktwolke eine Programmbeschreibung des abstrahierten Gebaeudes aus. — [arXiv 2501.17044](https://web3.arxiv.org/abs/2501.17044)
- Nishida, Bousseau, Aliaga (Eurographics 2018): Gebaeude aus EINEM Foto; je Stufe (Baukoerper, Fassade, Fenster) waehlt ein CNN die Grammatik, danach werden die Parameter optimiert; die Distanz zur Silhouette wird mit BOBYQA (ableitungsfreier lokaler Optimierer) minimiert. — [HAL/Eurographics](https://hal-univ-tlse3.archives-ouvertes.fr/INRIA/hal-01810207); [PDF Purdue](https://www.cs.purdue.edu/cgvlab/papers/aliaga/eg18.pdf)
- Photo2Building: derselbe Ansatz als Cloud-Dienst beschrieben. — [arXiv 2008.01286](https://arxiv.org/pdf/2008.01286)
- Gradientenbasierte Alternative (2023): Eingabeparameter eines prozeduralen Generators werden ueber einen Silhouetten-Verlust zwischen Referenz- und Renderbild geschaetzt. — [arXiv 2310.13373](https://arxiv.org/html/2310.13373v1)
- Pro-DG (2025): rekonstruiert aus einem Fassadenbild das Layout per Grammatikregeln und nutzt es zur Steuerung einer Bild-Diffusion (Ziel ist Bildsynthese, nicht Geometrie). — [Zusammenfassung arXiv 2504.01571](https://arxiv.deeppaper.ai/papers/2504.01571v1?locale=en)
- DI-PCG (2025, nur Suchtreffer): Diffusionsmodell schaetzt Parameter prozeduraler Generatoren aus Bildern, nicht gebaeudespezifisch. — Suchtreffer, keine Primaerquelle gelesen; siehe Gaps.
- LoD3-Fassaden aus RGB-Bildern (ISPRS 2025): Instanzsegmentierung mit YOLOv8 und SAM plus klassische Linien-/Kantenerkennung, ohne prozedurale Parameteranpassung. — [ISPRS Archives 2025](https://isprs-archives.copernicus.org/articles/XLVIII-G-2025/473/2025/isprs-archives-XLVIII-G-2025-473-2025.pdf)

### Inferences
- Das Nishida-Muster passt direkt auf den eigenen Generator: (a) Template waehlen (hier durch Agent oder Mensch statt CNN), (b) wenige Parameter ableitungsfrei gegen Bildkanten anpassen. Der fruehere Bericht schlug CMA-ES vor; BOBYQA ist die belegte Variante fuer genau diese Aufgabe und braucht bei wenigen Parametern und gutem Start weniger Auswertungen als CMA-ES (Vermutung zur Auswertungszahl, nicht gemessen).
- Der Agent sollte Templates schreiben, der Optimierer die Zahlen. Das trennt die beiden Fehlerquellen, die in Abschnitt 1 belegt sind (Strukturfehler 48 % gegen Massfehler) und spart genau die Runden, in denen der Agent heute Masse nachstellt.
- Wiederholung ausnutzen: Eine Fensterachse einmal anpassen, dann Achsabstand und Anzahl als zwei Parameter fuer die ganze Reihe. Die Anzahl bleibt fest aus der Foto-Zaehlung (Projektregel).
- Die gelernten Inversionsmodelle (FaçAID, Google-Transformer) liefern Layouts auf LoD3-Niveau (Fensterraster), keine Erker, Masswerke oder Rippen. Nutzen fuer H0-Detailteile: vermutlich gering.

### Gaps
- Kein offenes, gepflegtes Werkzeug gefunden, das CGA/Split-Grammatiken an Fotos anpasst. CityEngine/CGA: in dieser Recherche nicht untersucht (kommerziell, Esri; Linux-Skriptbarkeit ungeprueft).
- Keine Arbeit gefunden, die CMA-ES oder Bayes-Optimierung gegen Kanten-Distanzfelder fuer Gebaeudeteile mit Genauigkeitszahlen belegt.
- Genauigkeits- und Zeitangaben aus Nishida 2018 konnten nicht ausgelesen werden (PDF zu gross fuer den Abruf).
- DI-PCG, Code-Verfuegbarkeit und Lizenzen von FaçAID und dem Google-Transformer: ungeprueft.

## 3. Wiederverwendbare parametrische Teilebibliotheken und Generatoren

### Takeaway
Fertige offene Generatoren decken generische Stadthaeuser, Walmdaecher und Holzrahmenbau ab, nicht aber Fachwerk nach deutschem Muster oder gotisches Masswerk; fuer Masswerk gibt es nur die Konstruktionsregeln (Havemann/Fellner 2004) ohne gefundenen Code. Der realistische Weg ist eine eigene manifold3d-Teilebibliothek, die Algorithmen (Straight Skeleton, Masswerk-Konstruktion) uebernimmt, nicht fremde Add-ons.

### Cited Findings

**Daecher**
- bpypolyskel: Python-Bibliothek, berechnet aus einem Grundriss (auch mit Loechern) das Straight Skeleton und daraus die Dachflaechen eines Walmdachs; `polygonize()` liefert die Dachpolygone, `skeletonize()` das Skelett. Lizenz GPL-3.0. Ausserhalb von Blender nur `mathutils` noetig (`pip install mathutils`). Getestet an rund 320.000 Walmdaechern aus OpenStreetMap, laut README 99,99 % erfolgreich. Das Ergebnis ist bewusst kein mathematisch reines Skelett (Bereinigungsschritte). Ueberstand wird nicht erwaehnt. — [GitHub bpypolyskel](https://github.com/prochitecture/bpypolyskel)
- Grenzen des Straight Skeleton: ergibt Walmdaecher und mit Nachbearbeitung Satteldaecher. — [OSArch-Diskussion](https://community.osarch.org/discussion/423/)
- compas_cgal bietet laut Forumsbeitrag inneres Straight Skeleton und dessen Extrusion zu einem Walmdach-Netz (CGAL-Bindung fuer Python). — [McNeel-Forum](https://discourse.mcneel.com/t/cgal-on-rhino8-scripteditor/201957?page=2)
- shapely-polyskel: Straight Skeleton auf Shapely-Polygonen (PyPI). — [PyPI shapely-polyskel](https://pypi.org/project/shapely-polyskel/0.1.0)
- Rust-Crate `straight_skeleton` mit `Roof`-Typ, der ein Dach auf eine gegebene Hoehe zwischen Traufe und First kappen kann. — [docs.rs](https://docs.rs/straight-skeleton)
- Archipack enthaelt einen eigenen Dachgenerator in Python (`archipack_roof.py`, ueber 5000 Zeilen) im Blender-Add-on-Repository. — [projects.blender.org](https://projects.blender.org/blender/blender-addons/src/tag/v2.93.15/archipack/archipack_roof.py)

**Gebaeudegeneratoren fuer Blender**
- Buildify: kostenloser Geometry-Nodes-Generator, setzt Gebaeude aus Bibliotheken von Bauteilen zusammen. — [CG Channel](https://www.cgchannel.com/2022/07/download-free-blender-3d-building-generator-buildify/)
- buildingnodes (durman): prozedurale Gebaeude fuer Blender 3.0+, Quelltext auf GitHub. — [GitHub buildingnodes](https://github.com/durman/buildingnodes)
- Mehrere weitere Generatoren sind kostenpflichtig oder je Angebot unterschiedlich lizenziert (ArchGen, BRiCKiTECT, PBG 2). — [Superhive ArchGen](https://superhivemarket.com/products/archgen-blender-procedural-builder)

**IFC/BIM**
- IfcOpenShell (inklusive Python-API) steht unter LGPL-3.0-or-later; Bonsai (frueher BlenderBIM, umbenannt 2024) unter GPL-3.0-or-later. — [Anaconda ifcopenshell](https://anaconda.org/freecad/ifcopenshell); [Blender Extensions Bonsai](https://extensions.blender.org/add-ons/bonsai/versions/)

**Holzbau/Fachwerk**
- COMPAS Timber (Gramazio Kohler, Python): offenes Paket zum Modellieren und Fertigen von Holzrahmenkonstruktionen (Staebe, Verbindungen); wird als Rhino-Plugin installiert. — [GitHub compas_timber](https://github.com/gramaziokohler/compas_timber)
- FreeCAD Timber Workbench: nicht mehr gepflegt; der Fork "Wood Frame" ebenfalls nicht aktiv. — [FreeCAD-Wiki Timber](https://wiki.freecad.org/Timber_Workbench); [FreeCAD-Wiki Wood Frame](https://wiki.freecad.org/Wood_Frame_Workbench)
- Kumiki (PyPI): offenes Python-Paket fuer japanische Holzverbindungen. — [PyPI kumiki](https://pypi.org/project/kumiki/)
- Kostenloses Geometry-Nodes-Setup fuer Holzhaeuser (Mai 2026). — [BlenderNation](https://www.blendernation.com/2026/05/26/free-download-generate-wooden-houses-with-this-geometry-nodes-setup/)

**Gotik**
- Havemann und Fellner, "Generative Parametric Design of Gothic Window Tracery" (VAST 2004): Masswerk prozedural aus Zirkel-und-Lineal-Konstruktionen, modular aus Grundkonstruktionen kombiniert, in der eigenen Sprache GML. — [Eurographics Digital Library](https://diglib.eg.org/items/607768b5-11b0-4e72-9869-5d5df169f3f1)
- Ein parametrischer OpenSCAD-Fenstergenerator mit Spitzbogen-Option (Rahmen und Sprossen, kein Masswerk) liegt auf MakerWorld. — [MakerWorld 1523133](https://www.makerworld.com/en/models/1523133)

### Inferences
- Lizenzfolge: bpypolyskel, Archipack und Bonsai sind GPL. Wer sie in den eigenen Generator importiert, macht den Generator bei Weitergabe GPL-pflichtig (die erzeugten STL-Dateien nicht). Fuer ein Hobbyprojekt ohne Weitergabe des Codes unkritisch; in `modelle/LIZENZ_WERKZEUGE.md` vermerken. Keine Rechtsberatung.
- Dachueberstand (offene Sichtbeobachtung am Schwabentor): Straight Skeleton auf dem um den Ueberstand nach aussen versetzten Grundriss rechnen und die Dachflaechen entsprechend tiefer ansetzen. Dieses Vorgehen ist NICHT durch eine Quelle belegt, sondern geometrisch naheliegend; mit `tools/bauen_abnehmen.sh` pruefen.
- Geometry-Nodes-Generatoren (Buildify u. a.) setzen vorgefertigte Bauteil-Meshes zusammen. Sie sind fuer Stadtkulissen gebaut, liefern keine Belegkette je Mass und kein garantiert wasserdichtes Netz. Fuer das Projektziel (auditierbar, druckbar) vermutlich ungeeignet; brauchbar hoechstens fuer Nachbarhaeuser als Kulisse.
- Masswerk nach Havemann/Fellner ist eine kleine Menge von Kreisbogen-Konstruktionen (Spitzbogen aus zwei Kreisen, Paesse aus n Kreisen im Umkreis, Versatz fuer Profile). Das laesst sich als 2D-Kontur (Shapely-Versatz) plus Extrusion in manifold3d in einer Funktion umsetzen. Aufwand geschaetzt ein bis zwei Agentenrunden je Grundform; Schaetzung, nicht gemessen.
- Fachwerk: kein Generator gefunden; als Bibliotheksfunktion "Balkenraster aus 2D-Linienliste" bauen (Linien kommen aus dem Orthofoto, siehe Abschnitt 4).

### Gaps
- Nicht recherchiert bzw. nicht belegt in dieser Runde: Building Tools (Blender), Archimesh, Sverchok, Houdini-Gebaeudegeneratoren, CadQuery-/OpenSCAD-Architekturbibliotheken, CGAL-Straight-Skeleton-Extrusion direkt (nur ueber Forumsbeitrag zu compas_cgal). Aus Vorwissen: Sverchok und Archimesh sind GPL-Add-ons, CGAL 6 hat eine Skelett-Extrusion; hier ohne Quelle, also ungeprueft.
- Ob COMPAS Timber ohne Rhino als reines Python-Skript unter Linux laeuft und welche Lizenz es hat, wurde nicht geprueft.
- Letzte Aktivitaet von bpypolyskel und buildingnodes unbekannt.
- Kein offener Code fuer gotisches Masswerk, Kreuzrippen, Fialen oder Krabben gefunden.

## 4. Mensch in der Schleife: schnelles bildbasiertes Modellieren

### Takeaway
Fuer das fotogestuetzte Modellieren gibt es gute freie Werkzeuge, aber keine belastbaren Zeitangaben je Fassade. Die einzige harte Zahl zum Nutzen des Menschen: Menschliche Rueckmeldung schlaegt die Selbstpruefung des VLM (Punktwolkenabstand 0,120 gegen 0,137), und durchschnittliche Blender-Nutzer schlagen VLM-Systeme bei 8 Minuten je Aufgabe deutlich.

### Cited Findings
- fSpy: freie, plattformuebergreifende Anwendung zum Kamera-Abgleich an einem Einzelbild ueber Fluchtlinien; Blender-Importer setzt Kamera und Hintergrundbild. Herstellernahe Aussage: Kamera "in a matter of minutes". — [80.lv](https://80.lv/articles/improving-blender-workflows-with-still-image-camera-matching-app); [BlenderArtists](https://blenderartists.org/t/retiring-blam-and-announcing-fspy-a-stand-alone-camera-matching-app)
- Perspective Plotter und Blenspy: kostenpflichtige Blender-Add-ons, die den Kamera-Abgleich in Blender selbst erledigen. — [Superhive Perspective Plotter](https://superhivemarket.com/products/perspective-plotter/ratings?page=4); [Superhive Blenspy](https://superhivemarket.com/products/blenspy)
- Haeufiger Fehler laut Lehrbuch: Modellieren nach Referenzfoto ohne Massstabsabgleich. — [Packt, 3D Environment Design with Blender](https://www.packtpub.com/product/3d-environment-design-with-blender/9781803235851)
- Menschliche Rueckmeldung in der CAD-Schleife: Punktwolkenabstand 0,120 gegen 0,137 (VLM-Selbstpruefung) und 0,156 (ohne), 50 Beispiele. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Menschen mit 8 Minuten Limit sind bei Blender-Editieraufgaben in jeder Metrik besser als alle getesteten VLM-Systeme. — [arXiv 2504.01786](https://arxiv.org/html/2504.01786v1)
- LL3M sieht laufende Nutzerkorrekturen ausdruecklich als Teil der Schleife vor ("co-creative loop"). — [arXiv 2508.08228](https://arxiv.org/abs/2508.08228)
- Entzerrung der Fotos auf die LoD2-Wand verbessert die Segmentierung um rund 11 % (schon im frueheren Bericht zitiert; hier nur als Stuetze fuer das Nachzeichnen auf Orthofotos). — [Texture2LoD3](https://arxiv.org/html/2504.05249v1)

### Inferences
- fSpy loest ein Problem, das hier schon geloest ist: Die COLMAP-Kameras sind genauer als ein Fluchtlinien-Abgleich am Einzelbild. Nuetzlich waere fSpy nur fuer historische Einzelfotos, die sich nicht registrieren lassen.
- Der passende Mensch-Agent-Schnitt (Vorschlag, nicht belegt): Der Mensch klickt je Bauteil 6-12 Punkte oder Linien in zwei bis drei kalibrierten Fotos oder im Orthofoto der Wand; ein Werkzeug trianguliert sie mit den SfM-Kameras zu 3D-Punkten mit Restfehler; der Agent bekommt diese Punkte als benannte Sollwerte (z. B. "Erker: UK Konsole, OK Bruestung, Vorderkante links/rechts") und waehlt nur noch das Template. Das ersetzt die teuerste Agentenarbeit (Bildverstehen, feine Lokalisierung) durch die Staerke des Menschen und haelt die Belegkette (Klick -> Foto -> Pixel -> 3D) vollstaendig.
- Die Klicks gehoeren als Quelle in `masstabelle.json` (Foto, Pixel, wer, wann), damit die Abnahme sie wie `tools/foto_mass.py`-Messungen behandelt.
- Fuer Fachwerk und Fensterraster ist Nachzeichnen von Linien auf dem entzerrten Orthofoto (2D, in Metern) vermutlich am schnellsten: Die Linien sind bereits das Generator-Feature. Als Zeichenwerkzeug reicht ein Vektorprogramm mit SVG-Ausgabe, das der Agent einliest (Vorschlag).
- Der Mensch als Strukturpruefer: Statt den Agenten ueber Strukturfehler iterieren zu lassen, nach Runde 1 ein Bild "Render neben Foto" zeigen und eine Ein-Satz-Korrektur einholen. Das zielt auf die belegte Hauptfehlerklasse (Strukturfehler 48 %).

### Gaps
- Keine Quelle mit gemessener Zeit je Fassade fuer fotogestuetztes Modellieren (fSpy, SketchUp Match Photo, PhotoModeler) gefunden.
- SketchUp Match Photo, PhotoModeler, Punktwolken-Snapping (z. B. in CloudCompare oder Blender-Add-ons): in dieser Runde nicht recherchiert.
- Kein veroeffentlichter Arbeitsablauf "Mensch markiert Punkte, LLM-Agent baut das parametrische Teil" gefunden; der Vorschlag oben ist eine eigene Ableitung.

## 5. Planung und Priorisierung: Sichtqualitaet je Stunde in 1:87

### Takeaway
Belegt ist nur Grobes: Aus Armlaenge sind in H0 Details wie Nagelloecher und Schrauben nicht erkennbar, und Resin-Druck bildet erhabene Details ab etwa 0,1-0,5 mm und vertiefte ab etwa 0,2-0,4 mm ab (je nach Quelle). Eine belastbare Rangliste "welches Bauteil bringt wie viel" wurde nicht gefunden.

### Cited Findings
- "Three foot rule" im Modellbahnbau: Ein Modell gilt als gut genug, wenn es aus etwa drei Fuss (rund 0,9 m) gut aussieht. — [raildig.com](https://raildig.com/blog/three-foot-rule/)
- Forentest: Ein auf H0 skaliertes Foto einer Holzverschalung zeigte Nagelloecher, die auf Armlaenge nicht auffielen; Schrauben wurden erst bei etwa 3 Zoll (rund 8 cm) Kameraabstand klar sichtbar. — [trains.com Forum](https://cs.trains.com/mrr/f/88/p/295521/3453026.aspx)
- Umrechnung: 3,5 mm im Modell entsprechen einem Fuss im Vorbild (H0). — [trains.com Forum](https://cs.trains.com/mrr/f/88/p/295521/3453026.aspx)
- Resin-Druck, Mindestdetail laut einem Dienstleister-Datenblatt: erhaben 0,5 mm, vertieft 0,2 mm, Mindestspalt 0,2 mm. — [Facfox](https://facfox.com/?p=211811)
- Abweichende Richtlinie einer Hochschulwerkstatt: erhaben 0,1 mm, vertieft 0,4 mm, gestuetzte Wand mindestens 0,4 mm. — [SAIC-Richtlinie](https://sites.saic.edu/aoc/?p=1000)
- Allgemein: Resin etwa 0,2 mm Mindestdetail gegen etwa 0,5 mm bei FDM. — [JLC3DP](https://jlc3dp.com/blog/resin-vs-fdm-for-miniatures)
- Die theoretische Aufloesung von LCD-Druckern liegt unter 50 Mikrometern; praktisch begrenzt, was den Abziehvorgang uebersteht. — [LinkedIn Learning/Lynda](https://www.lynda.com/CAD-tutorials/Resolution-thin-parts/2808541/2254011-4.html)
- H0-Druckmodelle werden teils in zwei Fassungen angeboten: filigran und mit verstaerkten Details fuer sicheren Druck. — [CGTrader](https://www.cgtrader.com/3d-print-models/hobby-diy/hobby-accessories/h0-1-87-scale-faals-freight-car)

### Inferences
- Eigene Rechnung: 0,2 mm im Modell sind 17 mm am Bau, 0,5 mm sind 44 mm. Der fruehere Bericht nannte 26-70 mm fuer 0,3-0,8 mm; beides passt zusammen. Alles unter rund 2 cm Vorbildmass (Fugen, Nagelkoepfe, feine Profilstufen) ist weder druckbar noch aus 30 cm erkennbar und kann entfallen.
- Eigene Rechnung zum Auge: Bei 1 Bogenminute Aufloesung und 0,9 m Abstand liegt die Grenze bei etwa 0,26 mm im Modell (23 mm Vorbild); bei 0,3 m Abstand bei etwa 0,09 mm (8 mm Vorbild). Die Sehschaerfe-Annahme ist Lehrbuchwissen ohne Quelle in dieser Recherche.
- Vermutete Rangfolge nach Sichtwirkung je Stunde (deckt sich mit der Nutzer-Prioritaet Erker > Baldachine > Speier > Schindeln): 1. Silhouette und Dachlandschaft (Firstlinien, Ueberstaende, Tuermchen, Gauben), 2. grosse Vor- und Ruecksprunge mit Schattenwurf (Erker, Galerien, Gesimse ab etwa 5 cm Ausladung), 3. Oeffnungsraster mit richtiger Laibungstiefe, 4. wiederholte Reliefs (Rippen, Masswerk) als ein Template, 5. Flaechentextur (Schindeln, Quader) nur soweit druckbar. Nicht durch eine Studie belegt.
- Zwei Detailstufen je Teil vorsehen (filigran / druckfest), wie es H0-Anbieter tun; der Parameter gehoert in die Teilefunktion.

### Gaps
- Keine Quelle aus dem Architekturmodellbau mit konkreten Detaillierungsregeln je Massstab gefunden (die deutsche Suche lieferte nur Shop-Seiten).
- Keine Untersuchung gefunden, die misst, welche Bauteilklassen die wahrgenommene Aehnlichkeit eines Gebaeudemodells am staerksten bestimmen.
- Mindestwandstaerken speziell fuer H0-Gebaeude im Resin-Druck: keine Quelle; die genannten Werte sind allgemeine Richtlinien und widersprechen sich teils (erhaben 0,1 gegen 0,5 mm).

## 6. Schnellere Verifikation: billige Metriken, VLM als Richter, Fallstricke

### Takeaway
VLM-Richter sind messbar schwaecher als Menschen (0,66 gegen 0,79 Paar-Uebereinstimmung; eigene Pruef­fragen nur zu rund zwei Dritteln richtig) und haengen stark von Kamera, Bildaufbereitung und Prompt ab. CLIP-Aehnlichkeit korreliert bei Geometrie fast gar nicht mit Menschen (Pearson 0,074, nur Suchtreffer). Als hartes Tor taugen nur deterministische Geometrie- und Kantenmasse; VLM und Mensch sind fuer Strukturfragen da.

### Cited Findings
- VLM als Paar-Pruefer: bester Wert 0,66 (Claude 3.5 Sonnet) gegen 0,79 zwischen Menschen; Positions-Bias bei einem Modell; mehrfaches Abfragen des Pruefers verbessert das Ergebnis. — [arXiv 2504.01786](https://arxiv.org/html/2504.01786v1)
- VLM-Selbstpruefung per Fragen: 64,6-68,2 % richtig, bis 12,5 % falsch, rund ein Fuenftel bis ein Viertel "unklar". — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Punktwolken- und Hausdorff-Abstand sind laut den Autoren verrauscht und uebersehen strukturelle Luecken. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Fehler, die im Bild unsichtbar sind, findet nur die Zahl: Die meisten Reparaturen zum strengen Bestehen waren in Renderbildern nicht oder nur teilweise sichtbar. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- CADGenBench kombiniert vier Achsen und macht Gueltigkeit zum Tor: wasserdicht/gueltig, Oberflaechenabstand-F1 + Volumen-IoU, Keep-in/Keep-out-Volumen fuer Schnittstellen, Betti-Zahlen fuer Topologie (Anzahl Teile, Loecher, Hohlraeume). — [GitHub cadgenbench](https://github.com/huggingface/cadgenbench)
- DB-3DME (CVPR-2026-Workshop): 2.619 synthetische Netze mit menschlichen Noten fuer Geometrie und Prompt-Treue; die Art, wie das 3D-Objekt dem VLM bildlich gezeigt wird, ist laut Abstract ein Schluesselfaktor fuer die Uebereinstimmung mit Menschen; ein auf dem Bild-Encoder nachtrainiertes Qwen-2.5-VL-7B schlaegt vortrainierte VLMs. — [arXiv 2606.10142](https://arxiv.org/abs/2606.10142)
- CLIP-Score in DB-3DME: Pearson 0,074 bei Geometrie, 0,228 bei Prompt-Treue (NUR Suchausschnitt, Tabelle nicht gelesen). — [arXiv 2606.10142 PDF](https://arxiv.org/pdf/2606.10142)
- 3D-DefectBench (nur Suchausschnitt): Die Modellwahl erklaert den groessten Teil der Uebereinstimmung mit menschlichen Labels, aber Kameraprotokoll, Bildeingabe, Prompt-Schema und Richter-Modell wirken zusammen; eine Render-Einstellung, die einem Modell hilft, kann einem anderen schaden. Niedrige Uebereinstimmung kann auch an den Referenzlabels liegen. — [alphaxiv 2607.10826](https://www.alphaxiv.org/abs/2607.10826)
- GPTEval3D und Gen3DEval: VLM-Richter ueber Mehransicht-Render mit Paarvergleichen/Elo; Gen3DEval begruendet eigenes Feintuning damit, dass GPT-4V nicht fuer 3D-Qualitaetsbewertung trainiert ist. — [arXiv 2401.04092](https://arxiv.org/html/2401.04092v2); [arXiv 2504.08125](https://arxiv.org/html/2504.08125v1)
- 3DGen-Bench: Ein auf menschliche Praeferenzen nachtrainiertes CLIP-Modell stimmt deutlich besser mit Menschen ueberein als die anderen Metriken. — [arXiv 2503.21745](https://arxiv.org/html/2503.21745v2)

### Inferences
- Betti-Zahlen und Teilezahl sind ein fast kostenloses Zusatztor fuer den Generator: Anzahl zusammenhaengender Koerper, Durchbrueche (Fenster, Arkaden) und Hohlraeume je Teil gegen die Foto-Zaehlung. Das faengt genau die Strukturfehler, die Abstands- und Kantenmasse uebersehen (fehlender Durchbruch, schwebendes Teil). manifold3d liefert Genus und Komponentenzerlegung direkt (Vorwissen, nicht in dieser Recherche belegt).
- Keep-in/Keep-out-Volumen lassen sich auf Gebaeude uebertragen: Keep-out = Sichtstrahl-Freiraum aus den Fotos und Strassenraum; Keep-in = triangulierte Kantenpunkte muessen auf oder im Modell liegen. Das ist die eigene "Beleg vor/auf/hinter der Flaeche"-Idee als hartes Tor.
- Silhouetten-IoU je kalibriertem Foto ist billig und trifft die in Abschnitt 5 vermutete wichtigste Qualitaet (Umriss, Dachlandschaft); braucht aber eine Gebaeudemaske je Foto (Himmel-Trennung ist einfach, Nachbarhaeuser nicht). Nicht durch eine Gebaeudestudie belegt.
- Gelernte Bildmasse (LPIPS, DINO-Merkmale) zwischen untexturiertem Render und Foto vergleichen vor allem Material und Licht, nicht Form; es wurde kein Beleg gefunden, dass sie hier taugen. Wenn ueberhaupt, dann auf Kantenbildern oder Normalen-Rendern gegen Foto-Kanten. Vermutung.
- Wenn ein VLM als Richter laeuft: immer Paarvergleich in beiden Reihenfolgen (Positions-Bias), mehrfach abfragen und Mehrheit bilden, Kamera und Bildaufbau fest einfrieren, "unklar" als nicht bestanden werten, und das VLM nie ueber Masse urteilen lassen.
- Fallstricke beim Optimieren auf eine Metrik: (a) Kanten-F1 belohnt Modellkanten auf Fugen und Schatten, daher Precision als hartes Tor (schon im frueheren Bericht); (b) nachtraegliche Bestenauswahl ("Best Refine") schoent Ergebnisse, daher Annahme nur ueber das feste Tor, nicht ueber "bester von n" am selben Foto - besser ein Teil der Fotos als Kontrollsatz zurueckhalten, den der Optimierer nie sieht; (c) Abstandsmasse uebersehen Topologiefehler, daher Topologie-Tor getrennt.

### Gaps
- Keine Studie gefunden, die Silhouetten-IoU, Kanten-F1, LPIPS oder DINO fuer Gebaeudemodell-gegen-Foto mit menschlichem Urteil korreliert. Auch der fruehere Bericht fand keine Validierung eines Bildmasses gegen Laser-Referenz.
- Korrelationszahlen der VLM-Richter aus DB-3DME und 3D-DefectBench nicht an der Primaerquelle gelesen.
- Zu DINO-Merkmalen und zum Abstand Render-gegen-Foto (sim-to-real) lieferte die Suche nichts.

## Uebergreifende Arbeitsmuster (Zusammenzug, alles Inferenz aus den Abschnitten oben)

### Takeaway
Der belegbar wirksamste Umbau ist eine Dreiteilung: Mensch liefert Struktur und wenige Klickpunkte, Agent liefert Template-Code aus einer Bibliothek, ein ableitungsfreier Optimierer liefert die Zahlen; das deterministische Tor entscheidet und meldet Fehlbetrag und Ort statt nur bestanden/nicht bestanden.

### Cited Findings
- Strukturfehler sind die groesste Fehlerklasse (48 %), VLM-Selbstpruefung ist unzuverlaessig (rund zwei Drittel richtig), mehr als zwei Runden bringen nichts. — [arXiv 2410.05340v2](https://arxiv.org/html/2410.05340v2)
- Zahlenurteile mit Fehlbetrag und Ort tragen die strengen Erfolge; lange Laeufe kosten rund 68 Minuten je Teil bei 9 von 50 Erfolgen. — [arXiv 2605.17448v2](https://arxiv.org/html/2605.17448v2)
- Kernmessungen (Bounding-Box, Volumen, Gueltigkeit) plus Doku-Retrieval heben Median-IoU von 0,81 auf 0,96. — [arXiv 2603.26512](https://arxiv.org/abs/2603.26512)
- Menschen sind in 8 Minuten besser als VLM-Systeme beim Treffen eines Zielbilds. — [arXiv 2504.01786](https://arxiv.org/html/2504.01786v1)
- Template waehlen, dann Parameter ableitungsfrei an die Silhouette anpassen, ist fuer Gebaeude seit 2018 gezeigt. — [Nishida et al. 2018](https://hal-univ-tlse3.archives-ouvertes.fr/INRIA/hal-01810207)

### Inferences
- Vorschlag fuer den Ablauf je Bauteil (Ziel: unter einer Stunde, nicht gemessen): (1) Mensch: Template aus Bibliothek nennen oder neues anfordern, 6-12 Punkte/Linien in Fotos klicken (5-10 Minuten). (2) Werkzeug: Triangulation der Klicks, Startparameter. (3) Agent: nur falls Template fehlt, Funktion schreiben, hoechstens zwei bis drei Runden, drei Kandidaten parallel. (4) Optimierer: Parameter gegen Fotokanten, Anzahlen fest. (5) Tor: Masstabelle, Foto-F1 mit Precision-Tor, Topologie-Tor, Kontrollfotos. (6) Mensch: Render neben Foto, ein Satz Korrektur oder Annahme.
- Reihenfolge fuer ein neues Gebaeude: zuerst Silhouette und Dach fuer das ganze Haus (Straight Skeleton mit Ueberstand, Erker und Galerien als Kloetze), erst danach Relief; das liefert nach kurzer Zeit ein zeigbares Bild (Projektregel "Schnellversion zuerst").
- Der staerkste Einzelhebel bleibt die Teilebibliothek: Jedes abgenommene Teil wird als parametrische Funktion mit Belegliste abgelegt und beim naechsten Bau nur noch angepasst.

### Gaps
- Keine veroeffentlichte Messung, dass diese Dreiteilung bei Gebaeuden Tage auf Stunden verkuerzt; die Stundenangabe ist ein Ziel, kein Befund. Ein Musterbauteil (z. B. ein Erker) mit Zeitmessung vor/nach waere der noetige Eigenversuch.

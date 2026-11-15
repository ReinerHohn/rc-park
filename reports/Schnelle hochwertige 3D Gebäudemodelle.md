# Grundkoerper plus Scan-Relief schlaegt reine Agentenarbeit

Der schnellste Weg zu sehr guten, druckbaren H0-Modellen ist eine Mischung, kein Ersatz. Der masshaltige, wasserdichte Grundkoerper kommt weiter aus Fotokanten, aber aus einer Teilebibliothek, mit Klickpunkten des Menschen und einem Optimierer fuer die Masse statt aus vielen Agentenrunden. Das Relief der Waende kommt als ueberhoehte Hoehenkarte aus den Fotos. Plastische Einzelstuecke (Speier, Baldachine, Konsolen, Erkerschmuck) werden als kleine Netz-Einsaetze aus dem Scan eingesetzt. Ein reines Scan-Netz als Endprodukt empfehle ich nicht: Es schlug zwar am Kaufhaus das parametrische Modell im Foto-Vergleich (eigene Messung BS72), aber bei 1:87 liegt sein Feindetail unter der Druckgrenze, waehrend wellige Waende und weiche Kanten sichtbar bleiben. Generative Bild-zu-3D-Modelle sind nur ein billiger Seitenversuch fuer organische Teile: Sie erfinden ungesehene Seiten, und ihre Treue an Architekturteilen hat niemand gemessen. Der Versuchsplan unten braucht fuenf Tage und unter 20 USD. Wichtigste Einschraenkung: Dass diese Mischung Tage auf Stunden verkuerzt, ist eine begruendete Vermutung, kein veroeffentlichter Befund. Fuer keinen der drei Wege gibt es eine Messung an H0-Gebaeuden. Der Plan ist deshalb so gebaut, dass jeder Schritt am eigenen Foto-Tor besteht oder faellt. Zweite Einschraenkung: Das Projekt schliesst Verkauf ein, und mehrere der besten Werkzeuge sind dafuer nicht lizenziert.

## Rechnen dauert 40 Minuten, Modellieren Tage: dort liegt der Hebel

Kameras und dichte Wolke stehen nach rund 40 Minuten je Objekt, die Lage wird per GPS- und Grundriss-Tor geprueft (eigene Messung, `modelle/STAND_2026-11-14.md`). Das Schwabentor ist trotzdem noch eine LoD2-Kiste mit Laser-Dach (rund 25 %), und das Kaufhaus brauchte Tage mit vielen Agentenrunden. Der Engpass ist also die Handarbeit je Bauteil, nicht die Rechenzeit.

Drei Tatsachen bestimmen, was sich lohnt:

- **Die Druckgrenze entscheidet, nicht die Messgenauigkeit.** Harz bildet erhabene Details ab etwa 0,1 mm ab, Loecher ab 0,5 mm; gestuetzte Waende brauchen 0,2-0,4 mm, freie 0,6 mm ([Formlabs-Leitfaden](https://www.torontomu.ca/content/dam/design-technology-lab/services/3d-printing/SLA-Design-Guide.pdf), [Xometry](https://xometry.pro/en/?p=22102)). In 1:87 sind 0,2 mm im Modell 17 mm am Bau, 0,5 mm sind 44 mm (eigene Rechnung). Fugen, Putz und flache Profilstufen kann der Drucker nicht zeigen.
- **Relief muss ueberhoeht werden.** Ein H0-Ziegelwand-Modell hat bewusst 1 mm breite Fugen, rund neunmal breiter als massstaeblich ([STLFinder](https://stlfinder.com/model/ho-scale-brick-wall-YpRPsreU/4334506)). Fachwerkbalken liegen oft buendig im Gefach; ohne Ueberhoehung druckt die Wand glatt.
- **Niemand dokumentiert H0-Gebaeude aus Scans.** Die gefundene Praxis ist Drohne, Fertigsoftware, Blender/Meshmixer, Druck in grobem Massstab, und die Netzbereinigung kostet dabei die meiste Zeit ([Erfahrungsbericht](https://mazikainen.blogspot.com/2020/04/using-photogrammetry-and-3d-printing-to.html)). Die Modellbahnszene konstruiert Gebaeude von Hand ([Prusa-Blog](https://blog.prusa3d.com/de/3d-gedruckte-eisenbahnmodelle-teil-ii-zuege-und-gebaeude_30758/)).

## Weg b: Das Netz gewinnt im Foto und verliert im Druck

### Was belegt ist

- **Klassische Verfahren reichen.** Im einzigen Vergleich an Kulturerbe mit Laserscan als Referenz war klassisches Mehrbild-Stereo (Metashape) an Architektur gleich genau oder leicht genauer als das neuronale Verfahren MILo und 36- bis 50-mal schneller: an Ornament 0,20 cm Streuung in 4,5 Minuten gegen 0,30 cm in 163 Minuten, an der gotischen Fassade des Strassburger Muensters beide 3,0 cm ([Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)). Nur drei Datensaetze, aber die Richtung ist klar.
- **Neuronale Netze aus Splatting sind an grossen Gebaeuden schwach.** Auf der Gebaeudeszene Courthouse erreichen alle verglichenen Verfahren nur F1 0,10-0,24 ([arXiv 2604.07337](https://arxiv.org/html/2604.07337)). Lokal war 3DGS/2DGS als Netzquelle ebenfalls schlechter (`modelle/NICHTS_GEBRACHT.md`).
- **Die Problemzonen sind ueberall dieselben:** Fialen, Tuermchen, Portalrelief, bei beiden Verfahrensfamilien ([Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)). Ein Verfahrenswechsel hilft dort nicht, mehr Fotos dieser Zonen schon.
- **Eigene Messungen am Kaufhaus (7./8.11.2026):** Das dichte OpenMVS-Netz `mvs_default` schlug das parametrische Modell im Foto-Diff (-0,1060 gegen -0,0855, 19 von 22 Fotos besser, BS72). Es war mit 748 000 Flaechen nicht wasserdicht. trimesh, Open3D, Poisson und fTetWild scheiterten alle an der Reparatur. Ursache laut BS36c: Das Netz hat keine eindeutige Innen- und Aussenseite (offener Boden, Naht zwischen Teilnetzen).
- **Zwei eigene Befunde gehen leicht unter:** Die wasserdichte Offset-Schale war im Foto-Diff nicht vom Rohnetz unterscheidbar (BS23b). Und ein auf 90 000 Flaechen ausgeduenntes Netz war auf unbekannten Fotos praktisch gleich gut (BS132). Das Netz ist also naeher an druckbar, als "gescheitert" klingt.

### Warum trotzdem nicht das ganze Haus als Netz

Bei 1:87 spielt das Netz seinen Detailvorteil nur bei Formen ueber etwa 2-5 cm am Bau aus. Seine Nachteile bleiben sichtbar: wellige Waende, runde Kanten, Loecher an Dach und duennen Teilen, keine ungesehenen Seiten, keine gezielte Ueberhoehung, keine saubere Teilung in Druckteile. Das Netz gewinnt bei Plastischem und Unregelmaessigem, der parametrische Koerper bei geraden Kanten, Wiederholungen, Wandstaerken und Masshaltigkeit (Einordnung aus den Befunden, nicht gemessen).

### Die Mischform, die beides nutzt

1. **Grundkoerper** aus Fotokanten wie bisher: masshaltig, wasserdicht, teilbar.
2. **Relief je Wand als Hoehenkarte.** Der Abstand der Oberflaeche zur Wandebene wird als Graustufenbild gespeichert und verformt die unterteilte Wandflaeche wirklich. Das Verfahren ist in der Bauaufnahme seit 2011 beschrieben ([ISPRS 2011](https://isprs-archives.copernicus.org/articles/XXXVIII-5-W16/191/2011/isprsarchives-XXXVIII-5-W16-191-2011.pdf), [ISPRS 2012](https://isprs-archives.copernicus.org/articles/XXXIX-B5/285/2012/isprsarchives-XXXIX-B5-285-2012.pdf)). Eine Hoehenkarte ueber einer geschlossenen Flaeche ist von der Bauart her wasserdicht; genau das umgeht die gescheiterte Reparatur (Vermutung, plausibel).
3. **Einsaetze** fuer Plastisches: kleiner Netzausschnitt aus Nahfotos, auf einen Quader beschnitten, per Voxel-Neuvernetzung mannigfaltig gemacht, an der Wandebene abgeschnitten und mit manifold3d in den Grundkoerper vereinigt. Ein Ausschnitt mit ebener Rueckseite hat eine eindeutige Innenseite, anders als das ganze Haus mit offenem Boden (Vermutung, Versuch 5). Dass sich das lohnt, stuetzt die Messung: an Einzelobjekten 0,10-0,20 cm Streuung, an der ganzen Fassade 3 cm ([Billi et al. 2026](https://isprs-archives.copernicus.org/articles/XLIX-B2-2026/801/2026/isprs-archives-XLIX-B2-2026-801-2026.pdf)).

Zur Kernmethode passt das nur mit einer Regel: Relief wird nur dort zugelassen, wo der Kanten-Sweep eine Struktur bestaetigt. Sonst wird mit der Ueberhoehung auch das Rauschen ueberhoeht (1-3 cm am Bau sind 0,1-0,3 mm im Modell, eigene Rechnung). Einsaetze aus dem Scan weichen von "Form nie aus der Wolke" ab. Das ist eine Entscheidung des Nutzers, kein technischer Selbstlaeufer.

## Weg c: Mensch klickt, Bibliothek liefert, Optimierer rechnet

Die Forschung zu KI-gestuetztem CAD misst Maschinenbauteile, keine Gebaeude. Vier Befunde uebertragen sich trotzdem:

- **Lange Selbstkorrektur-Ketten bringen nichts.** Rueckmeldung aus Renderbildern senkt den Formfehler nur von 0,155 auf 0,127, nach der zweiten Runde wird es oft schlechter. Das Sprachmodell beantwortet seine eigenen Prueffragen nur zu rund zwei Dritteln richtig. 48 % der Fehler sind Strukturfehler, also falscher Aufbau, nicht falsche Masse ([CADCodeVerify](https://arxiv.org/html/2410.05340v2)).
- **Zahlenurteile mit Fehlbetrag und Ort tragen den Erfolg.** Die meisten Reparaturen, die zum strengen Bestehen fuehrten, waren im Renderbild nicht sichtbar. Ein langer Lauf brauchte im Mittel 68 Minuten je Teil und bestand nur 9 von 50 ([arXiv 2605.17448](https://arxiv.org/html/2605.17448v2)). Exakte Messwerte aus dem Geometriekern hoben die mittlere Ueberdeckung von 0,81 auf 0,96 ([CADSmith](https://arxiv.org/abs/2603.26512)).
- **Der Mensch ist bei Struktur schneller und besser.** Durchschnittliche Blender-Nutzer schlagen mit 8 Minuten je Aufgabe alle getesteten Bildmodelle; als Schiedsrichter zwischen zwei Renderbildern erreicht das beste Modell 0,66 Uebereinstimmung, Menschen untereinander 0,79 ([BlenderGym](https://arxiv.org/html/2504.01786v1)).
- **Vorlage waehlen, dann Masse automatisch anpassen** ist fuer Gebaeude seit 2018 gezeigt: Ein Netz waehlt die Grammatik, der ableitungsfreie Optimierer BOBYQA passt die Parameter an die Silhouette an ([Nishida et al. 2018](https://www.cs.purdue.edu/cgvlab/papers/aliaga/eg18.pdf)).

Daraus folgt eine Dreiteilung (Ableitung, nicht veroeffentlicht gemessen):

- **Mensch:** nennt die Vorlage und klickt je Bauteil 6-12 Punkte oder Linien in zwei bis drei kalibrierten Fotos oder im entzerrten Wandbild. Ein Werkzeug trianguliert die Klicks mit den SfM-Kameras und schreibt sie mit Foto, Pixel und Datum in `masstabelle.json`.
- **Agent:** schreibt nur noch fehlende Vorlagen, hoechstens zwei bis drei Runden, besser drei Kandidaten parallel als eine lange Kette. Jede abgenommene Funktion wandert in die Bibliothek.
- **Optimierer:** stellt die Masse gegen die Fotokanten ein (BOBYQA oder CMA-ES), Anzahlen bleiben fest aus der Foto-Zaehlung.
- **Tor:** meldet statt "nicht bestanden" Stelle, Richtung und Betrag, etwa "Erkersims 38 mm zu tief in Foto 6117". Dazu ein Topologie-Tor (Zahl der Koerper und Durchbrueche gegen die Foto-Zaehlung) und Kontrollfotos, die der Optimierer nie sieht.

Fertige Bausteine gibt es nur fuer Teile davon. `bpypolyskel` rechnet Walmdachflaechen aus einem Grundriss (GPL-3.0, laut README an rund 320 000 Daechern getestet) ([bpypolyskel](https://github.com/prochitecture/bpypolyskel)). Fuer gotisches Masswerk existieren die Konstruktionsregeln aus Zirkel und Lineal, aber kein gefundener Code ([Havemann/Fellner 2004](https://diglib.eg.org/items/607768b5-11b0-4e72-9869-5d5df169f3f1)). Fuer deutsches Fachwerk wurde kein Generator gefunden. Gelernte Fassadenmodelle liefern Fensterraster, keine Erker oder Rippen ([FacAID](https://arxiv.org/html/2406.01829v2)).

## Weg a: Generatoren erfinden, was sie nicht sehen

- **Treue:** Die besten offenen Einzelbild-Modelle treffen auf Spielzeug-Datensaetzen nur rund zwei Drittel der Flaeche innerhalb von 5 % der Objektgroesse (TRELLIS.2 F-Score 0,66, Hunyuan3D 2.1 0,64) ([arXiv 2611.06141](https://arxiv.org/html/2611.06141)). Eine Uebersichtsarbeit zeigt an der Nofretete-Bueste "substantial discrepancies", Ornamente aehneln dem Original nur lose ([Heritage 2026](https://doi.org/10.3390/heritage9070246)). Fuer Masswerk, Fachwerk oder Wasserspeier gibt es keine Messung.
- **Mehrere echte Fotos helfen nur maessig.** ReconViaGen (VGGT plus TRELLIS, Code MIT) verbessert den Formfehler mit vier Ansichten um rund 10-25 % ([ReconViaGen](https://github.com/GAP-LAB-CUHK-SZ/ReconViaGen), [arXiv 2604.01479](https://arxiv.org/pdf/2604.01479)). Es schaetzt eigene Kameras; das Ergebnis muss nachtraeglich an unsere Wolke gelegt werden. Kein offenes Verfahren nutzt bekannte Kameras als harten Zwang.
- **Am besten passt "Grobform plus Foto ergibt Detail":** Hi3D v1.0 verfeinert ein Grobnetz anhand eines Referenzbilds bis 1536 Voxel Kantenlaenge, offene Gewichte seit 23.10.2026, aber nur auf einer 96-GB-Karte validiert und unter eigener Lizenz ([Pandaily](https://pandaily.com/hi3d-v1-0-open-source-sparc3d-high-resolution-3d-geometry-refinement-1536)). Hunyuan3D-Omni nimmt Punktwolke oder Quader als Bedingung ([arXiv 2509.21245](https://arxiv.org/abs/2509.21245v1)), ist aber wie Hunyuan3D 2.1 in der EU nicht lizenziert ([LICENSE](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE)).
- **Rechner:** TRELLIS.2 verlangt offiziell 24 GB und erzeugt ein Teil in 3-60 Sekunden auf einer H100 ([TRELLIS.2](https://github.com/microsoft/TRELLIS.2)). Auf 8 GB laufen offiziell nur Stable Fast 3D und SPAR3D im Sparmodus ([SPAR3D](https://github.com/Stability-AI/stable-point-aware-3d)). Der Laptop scheidet aus.
- **Preise (Stand 15.11.2026):** Rodin ueber fal.ai 0,40 USD je Generierung ([fal.ai](https://fal.ai/models/fal-ai/hyper3d/rodin)). Tripo rund 0,20-0,30 USD, Meshy rund 0,40-0,60 USD je Modell; beide Angaben stammen von Wiederverkaeufern und widersprechen sich teils ([ModelsLab](https://modelslab.com/meshy-api-alternative)). Offizielle Preislisten wurden nicht gelesen.
- **Druck:** In Meshys eigenem Test waren nur 55 % der Exporte direkt wasserdicht ([Meshy-Blog](https://www.meshy.ai/blog/best-ai-tools-for-3d-printing)). TRELLIS.2 garantiert es nicht.

Sinnvoll sind Generatoren nur fuer organische Einzelstuecke mit schlechter Fotoabdeckung. Bei Fachwerk, Masswerk, Zifferblatt und Fensterrastern sind Zaehl- und Symmetriefehler zu erwarten (Vermutung). Die Erzeugung ist stochastisch und billig. Mehrere Laeufe erzeugen und nur behalten, was auf nicht verwendeten Fotos das Foto-Tor besteht, macht das Tor wichtiger als die Wahl des Generators.

## Empfehlung: Bauteilart bestimmt den Weg

- **Baukoerper, Dach, Oeffnungen, Gesimse:** Weg c. Vorlage, Klickpunkte, Optimierer. Zuerst Silhouette und Dach fuer das ganze Haus, dann Vorspruenge, dann Relief.
- **Fachwerk des Nachbarhauses:** Balkenlinien auf dem entzerrten Wandbild nachzeichnen (Mensch, SVG), als Balkenraster mit Ueberhoehung ausgeben. Die Linien sind bereits das Generator-Merkmal.
- **Flaechenrelief (Quader, Rippen, Laibungen):** Hoehenkarte je Wand, nur wo Fotokanten sie bestaetigen.
- **Plastisches (Speier, Baldachine, Konsolen, Erkerschmuck, Wappen):** Netz-Einsatz aus Nahfotos. Generator nur, wenn die Fotos nicht reichen und das Tor besteht.
- **Ganzes Scan-Netz:** nicht als Druckmodell, aber sofort als Zielbild, Fehlteile-Finder und Quelle fuer Hoehenkarten und Einsaetze.

Am schnellsten wirkt vermutlich die Kombination aus Klickpunkten und Bibliothek, weil sie die belegte Hauptfehlerklasse (Struktur) dem Menschen gibt und die Massarbeit dem Rechner. Die Hoehenkarte bringt den groessten sichtbaren Sprung je Stunde an Fachwerk und Quaderwaenden.

## Versuchsplan: fuenf Tage, unter 20 USD

Voraussetzung fuer alle Foto-Vergleiche am Schwabentor: Die uebertragene Ausrichtung von `schwab_v3` ist mit 0,3 m Rest vermutlich zu grob (Kanten-F1 0,017 gegen 0,093 bei `schwab_auto`). Erst die Kameras verfeinern oder mit `schwab_auto` arbeiten.

**Versuch 1 - Netz als Zielbild (Tag 1 vormittags, 2-3 Stunden, 0 EUR)**
- OpenMVS-Netz des Schwabentors samt Nachbarhaus aus der gesaeuberten Wolke, auf 100 000-300 000 Flaechen ausduennen, als 3D-Seite zeigen.
- `tools/foto_diff.py` gegen die LoD2-Kiste, getrennt nach Wand, Dach, Aufbauten.
- Erfolg: besser auf mindestens 80 % der Fotos; Liste der Zonen, in denen das Netz Loecher hat (erwartet: Dach, Helm).

**Versuch 2 - Generator-Stichprobe (Tag 1 nachmittags, 2 Stunden, unter 5 USD)**
- Ein Speier oder Baldachin am Kaufhaus, fuer den ein abgenommenes parametrisches Teil existiert.
- 3-4 freigestellte eigene Fotos an Rodin (Modus `concat`, 0,40 USD je Lauf) und Tripo (Mehransicht), je drei Laeufe. Vorher die Nutzungsbedingungen zum Hochladen lesen (nicht geprueft).
- Ergebnis per skalierter Ausrichtung an die Wolke legen, an der Wandebene abschneiden, auf nicht verwendeten Fotos pruefen.
- Erfolg: Foto-F1 ueber dem des parametrischen Teils und die drei Hauptmasse passen zu `tools/foto_mass.py`. Faellt es durch, ist Weg a fuer dieses Projekt vorerst erledigt.

**Versuch 3 - Klickpunkte mit Stoppuhr (Tag 2, 1 Tag, 0 EUR)**
- Kleines Klick-Werkzeug mit Triangulation. Daran Tordurchfahrt und Holzgalerie des Schwabentors: Mensch klickt, Vorlage aus der Kaufhaus-Bibliothek oder neu, Optimierer stellt die Masse.
- Erfolg: `tools/bauen_abnehmen.sh` bestanden, Foto-F1 steigt, und die Zeit je Bauteil liegt unter einer Stunde (Ziel, kein Befund). Vergleichswert ist die bisherige Dauer je Bauteil am Kaufhaus.

**Versuch 4 - Fachwerk und Hoehenkarte (Tag 3, 1 Tag, 0 EUR plus Probedruck)**
- Entzerrtes Wandbild des Fachwerk-Nachbarhauses, Balken nachzeichnen, Balkenraster bauen.
- Probeplatte mit drei Relieftiefen (0,1 / 0,2 / 0,3 mm) drucken; die Tiefe ist ANNAHME und wird am Druck geeicht.
- An einer Kaufhauswand die Hoehenkarte gegen das vorhandene parametrische Relief stellen.
- Erfolg: Foto-F1 mit Precision-Tor nicht schlechter als das Handmodell, Probedruck aus 30 cm lesbar.

**Versuch 5 - Netz-Einsatz (Tag 4, 1 Tag, 0 EUR)**
- Ein plastisches Teil (Erker des Nachbarhauses oder ein Kaufhaus-Baldachin) als Netzausschnitt: beschneiden, Voxel-Neuvernetzung bei 0,05-0,1 mm Modellmass, Wandebene schneiden, mit manifold3d vereinigen.
- Erfolg: wasserdicht, ein Koerper, `druck.splitter_verwerfen` ohne Befund, Foto-F1 ueber dem parametrischen Teil, keine Breitenaenderung wie bei fTetWild (dort 16 mm).

**Tag 5 - Entscheidung, Mietkarte nur bei Bedarf**
- Was bestanden hat, wird Standard in der Kette. Die Kennzahl je Objekt ist Foto-F1 auf Kontrollfotos plus die Realitaets-Prozentzahl nach Sichtpruefung.
- Nur wenn Versuch 2 besteht: offene Generatoren auf einer Mietkarte. Eine RTX 4090 mit 24 GB kostete bei RunPod 0,34 USD je Stunde, eine RTX 3090 0,22 USD (Preisseite vom 12.11.2026) ([RunPod](https://www.runpod.io/pricing)). Ein Tag Einrichtung sind 3-8 USD.

## Lizenzen entscheiden, was in ein Verkaufsmodell darf

- **Frei auch fuer Verkauf:** TRELLIS.2 (MIT, aber die Abhaengigkeiten nvdiffrast und nvdiffrec haben eigene Lizenzen) ([TRELLIS.2](https://github.com/microsoft/TRELLIS.2)); Stable3DGen/Hi3DGen (Code MIT, NVIDIA-Teile entfernt; Lizenz der Gewichte ungeprueft) ([Stable3DGen](https://github.com/Stable-X/Stable3DGen)); Stable Fast 3D und SPAR3D bis 1 Mio. USD Jahresumsatz ([Stability AI](https://stability.ai/news-updates/stable-point-aware-3d)); RealityScan 2.0 frei bis 1 Mio. USD Umsatz ([RealityScan](https://www.realityscan.com/license?lang=en-us)).
- **In der EU nicht gedeckt:** Hunyuan3D 2.1, vermutlich auch Omni.
- **Nur Test:** fast alle Splatting-Verfahren (Inria-Lizenz, nicht gelesen), GS4Buildings, der Standard-Checkpoint von VGGT, auf dem ReconViaGen aufbaut (`modelle/LIZENZ_WERKZEUGE.md`).
- **Mit Pflichten:** `bpypolyskel` GPL-3.0 (betrifft den Generator-Code bei Weitergabe, nicht die STL-Dateien; keine Rechtsberatung), OpenMVS AGPL, SAM 3D Objects eigene Meta-Lizenz und 32 GB VRAM ([SAM 3D](https://github.com/facebookresearch/sam-3d-objects/blob/main/doc/setup.md)).
- **Ungeklaert:** Rechte an Ausgaben der gehosteten Dienste und deren Umgang mit hochgeladenen Fotos; Lizenztext von Hi3D v1.0.

## Belegt und Vermutung getrennt

**Belegt durch Quellen**
- Klassisches Mehrbild-Stereo ist an Architektur so genau wie neuronale Netze und 36- bis 50-mal schneller.
- Lange Selbstkorrektur von Sprachmodellen bringt nach zwei Runden nichts; Zahlenurteile mit Fehlbetrag wirken; Menschen schlagen Bildmodelle bei Strukturfragen.
- Generatoren erfinden ungesehene Teile; ihre Ausgaben sind nicht verlaesslich wasserdicht.
- Druckgrenzen fuer Harz und die Praxis der Ueberhoehung im Modellbau.
- Hoehenkarte auf ebener Flaeche als Verfahren der Bauaufnahme.

**Belegt durch eigene Messung**
- 40 Minuten je Objekt bis zur dichten Wolke.
- OpenMVS-Netz schlaegt das parametrische Kaufhaus-Modell im Foto-Diff; Reparatur des ganzen Netzes scheitert; Offset-Schale und starkes Ausduennen kosten im Foto-Diff fast nichts.

**Vermutung**
- Dass Klickpunkte, Bibliothek und Optimierer ein Bauteil in unter einer Stunde liefern.
- Dass Netz-Einsaetze mit ebener Rueckseite die Wasserdicht-Reparatur bestehen.
- Dass eine ueberhoehte Hoehenkarte sauber druckt und welche Tiefe dafuer noetig ist.
- Alle Zeitangaben im Plan und die Rangfolge der Bauteilarten nach Sichtwirkung.
- Dass Generatoren an Zaehl- und Symmetrieteilen scheitern und an organischen Teilen brauchbar sind.

**Offen**
- Kein Benchmark misst KI-Modellierung, Generatoren oder Scan-Druck an historischen Gebaeuden in kleinem Massstab.
- Offizielle Preise von Tripo und Meshy; VRAM-Bedarf von ReconViaGen, Hi3DGen und Hi3D unterhalb der Maximalaufloesung.
- Ob RealityScan unter Linux laeuft: Die Ankuendigung listet nur Windows, eine fruehere Recherche fand eine experimentelle Linux-Befehlszeile. Es liegt nicht auf dem kritischen Weg.

## Fazit

Die Frage "Netz oder Parametrik" loest sich bei 1:87 auf: Der Drucker zeigt nur, was am Bau groesser als etwa zwei Zentimeter ist, und genau diese Formen sind entweder regelhaft (dann gewinnt die Vorlage) oder plastisch (dann gewinnt der Scan-Ausschnitt). Die eigenen Messungen vom 7. und 8.11. hatten das schon angedeutet. Verworfen wurde damals das ganze Netz, nicht die Idee, es in Stuecken auf einen sauberen Koerper zu setzen.

Der zweite Befund betrifft die Arbeitsteilung. Das vorhandene Tor mit Masstabelle und Foto-F1 ist weiter als die Literatur. Was fehlt, ist davor der Mensch mit zwoelf Klicks und danach ein Optimierer, der dem Agenten das Nachstellen von Zahlen abnimmt. Ob das die Tage wirklich zu Stunden macht, zeigt die Stoppuhr in Versuch 3. Faellt er durch, bleibt die Hoehenkarte als unabhaengiger Gewinn.

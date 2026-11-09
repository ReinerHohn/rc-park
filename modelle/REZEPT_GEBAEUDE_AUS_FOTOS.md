# Rezept: Gebäude aus Fotos zum H0-Modell (Stand 9.11.2026 abends)

Ziel: Jedes Gebäude der Miniaturwelt mit wenig Aufwand in einem unbeaufsichtigten Lauf. Fotos/Video rein, geprüftes, druckbares H0-Modell raus.
Das hier ist die generalisierte Methode aus dem Kaufhaus Freiburg (9.11.). Objektspezifisches gehört nur in `modelle/<objekt>/objekt.json` und die Masstabelle, nie in den Code.
Erst lesen: `modelle/NICHTS_GEBRACHT.md` (Sackgassen), `CLAUDE.md` (Abnahmeregeln).

## Grundidee in einem Satz
**Kanten finden, Wiederholungen falten, jede Kante gegen Fotos UND Wolke prüfen, Formen aus dem Generator, Maße aus den Kanten.**

## Die fünf Säulen
1. **Kantengitter** (rein aus Daten): Tiefen-Sweep auf Stabilitätskarten, RANSAC-Aufbau, Foto-Schleife, Vereinigung über Läufe (`gitter_zurueck.py`: nie eine fotobelegte Kante verlieren).
2. **Wiederholung und Spiegelung** (Musterzelle): Zone aus dem Gitter, Periode per Autokorrelation (mehrstufig: Elementabstand, dann Teilung im Element), Instanzen falten, Phase per Symmetrie, Form aus der gemittelten Zelle, jede Kopie einzeln an den Fotos abnehmen. Vorbild: `baluster_fit.py` (68 Baluster, Periode 0,306, Zählung am Foto getroffen). Allgemein: `muster_fit.py --familie ...` (im Bau).
3. **Kanten-Tor** (kantenneutral, `kanten_tor.py`, im Bau): Jede Kante, egal aus welchem Bauteil, wird quer verschoben und an den Enden variiert, getrennt gegen Wolke und Fotos.
4. **Generator** (`baukasten_gen.py` + Masstabelle): Formfamilien (Satteldach, Staffelgiebel, Bogenreihe, Rundpfeiler, Brüstung, Fensterreihe, Helmkegel, Gaubenreihe) mit Maßen aus dem Gitter, Quelle "kantengitter", Prüfstand muss grün sein.
5. **Abnahme am Foto**: foto_diff, fehlteile, Sichtblatt aller Seiten, Fehlerliste je kleinstem Teil.

## Ablauf (eine Kette, `tools/gitter_kette.sh NAME --vorher BESTES.json`)
| Stufe | Werkzeug | Ergebnis | Tor |
|---|---|---|---|
| Kameras | SfM gemeinsam, Video-Frames dazu, Rahmen loten | kam_*.json | Reproj < 1,5 px |
| Karten | Stabilitätskarten je Foto (261 Läufe) | stabil/ | - |
| sweep, konsens | Tiefen-Sweep A und B (unabhängige Referenzen, dz-Basis) | Kantenpunkte | B als Fremdprüfung |
| aufbau, schleife | RANSAC zwei Bänder, Foto-Schleife | Gitter | Treffer/Abdeckung je Höhenband |
| formen | helm_fit, saeulen_fit, arkaden_fit, baluster_fit, (muster_fit) | Formteile | Synth-Test + 3 Fotos |
| wiederh, spiegel | Wiederholung/Spiegel | Kopien | jede Kopie >= 3 Fotos |
| kurven | Ketten zu Linie/Bogen/Bezier | Kurven | Z-Puffer-Fotoprüfung |
| verfeinern | DT-Verlust gegen Karten, Topologie | saubere Ecken | max 5 cm |
| tor (neu) | kanten_tor.py | Status je Kante | Entscheidregel unten |
| zusammen | Vereinigung mit Vorgänger | Gitter | Anteil alter Kanten je Band |
| messen, zeigen | Wolke/B-Konsens, Pruefblatt, Viewer 450k Punkte | 3D-HTML | ansehen |
| koerper | koerper_kette.sh (Durchsicht-Test, offene Lauben, runde Säulen) | STL wasserdicht | Gate + Overlay |
| generator | Masstabelle aus Gitter, bauen_abnehmen | H0-STL | Prüfstand grün |

## Entscheidregel (Nutzerentscheide 9.11.)
- **Fotos UND Wolke**, getrennt geprüft, nie gemittelt.
- **Nur mit genug Daten**: Wolke Mindestpunkte im Prüfschlauch und signifikante Spitze (>= 3 MAD); Fotos >= 3 sehende aus >= 2 Richtungen. Sonst ist die Quelle blind.
- **GRÜN**: beide genug, beide Optima beim Wert.
- **ENTSCHIEDEN(Quelle)**: Die Quelle mit den besseren Daten gewinnt (Menge, Signifikanz, Plateau, Einigkeit der Instanzen; Suchgrenze disqualifiziert). Ein Begründungssatz mit Zahlen gehört in Datei und Log.
- **OFFEN**: keine Quelle ausreichend oder kein klarer Sieger. Der Wert bleibt `ANNAHME:`.
- **Kopplung nur auf Probe**: Wiederholte/gespiegelte Kanten werden gemeinsam geprüft. Will eine Untergruppe signifikant woanders hin, wird sie automatisch abgetrennt (Beispiel: der Kämpfer des Mittellichts sitzt höher als bei den Seitenlichtern).

## Prüfdisziplin (aus Fehlern des 9.11.)
- Fehlerliste vor Lob: je kleinstem Teil (je Licht, je Konsole, je Pfosten) "trifft echte Kante ja/nein". Zwischenstände heißen `*_entwurf`.
- Agentenmeldung "angesehen ok" nie ungeprüft übernehmen (Sichtblatt mit schwebendem Dach war "ok").
- Nutzer-Sichtfund zuerst als Testfall, der am alten Stand fehlschlägt.
- Grenzen größer als der erwartete Fehler; Fit auf Grenze = Grenze erweitern.
- Jedes neue Rechenwerkzeug nutzt die GPU, mit gemessenem VRAM-Budget; n×n-Vergleiche immer blockweise.


## Bewährter Messweg je Element (Laubenrückwand Kaufhaus, 9.11., Nutzer: "gigantischer Schritt")
1. Ebene des Elements aus dem Kantengitter (Normale + Abstand, ±0,3 m).
2. Anzahl und Teilung am Foto zählen (`foto_zaehlung.py`, Regel 9).
3. Kanten messen: `foto_mass.py --kamera K-<foto> --ebene nx,ny,nz=d`. Pixel ergibt Sehstrahl, der Schnitt mit der Ebene ergibt Meter (±0,06 m).
4. Generator-Bauteil mit Beleg, die Prüfung schlägt vorher fehl, Einbettung 0,04 m.
5. Overlay plus Fehlerliste je Teil.
Anwenden auf alle Elemente mit bekannter Ebene: Fenster, Türen, Giebelfenster, Gesimse, Gaubenfronten, Erkerflächen.
Schritte 2 und 3 sind heute Sichtpicks des Sprachmodells, also Handarbeit mit Protokoll. Diese Handwerte sind der Prüfmaßstab, bis `kanten_tor`/`muster_fit` dieselben Werte automatisch aus Karten und Wolke treffen.

## Lehren-Register (generalisiert; nach JEDER Runde ergänzen, 1 Zeile je Lehre)
Format: Lehre (allgemein formuliert) | Anlass | wo im Werkzeug/Ablauf umgesetzt.
- L1 Wiederholung: Abstände zuerst auf Konstanz prüfen. Starr falten nur bei konstantem Abstand, sonst jede Instanz einzeln ausrichten und nur die Form mitteln | Konsolen 1,45-1,93 statt Raster 2,006 | `konsolen_zelle.py`, `muster_fit instanzen_ungefaltet`
- L2 Unterelemente einer Musterzelle haben eigene Parameter. Die Kopplung gilt nur auf Probe, das Tor trennt auf, wenn eine Untergruppe signifikant abweicht | Mittellicht-Kämpfer 12,28 statt 11,75 | `kanten_tor.py` Auto-Split
- L3 Prüfen kantenneutral: Bauteile liefern Kanten plus Kopplungen, das Tor prüft je Kante gegen Fotos UND Wolke getrennt, mit Mindestdaten. Die bessere Datenlage gewinnt, mit Begründung | Nutzerentscheide | `kanten_tor.py`
- L4 Zone gezielt aus dem Gitter suchen, nie blind in feste Höhenbänder schneiden | gitter_wiederholung verfehlte Pfeiler, Gauben, Fensterachsen | `baluster_fit`/`muster_fit`
- L5 Altteile mit falscher Lage verfälschen globale Diff-Suchen (dichte Kanten ziehen den Versatz) | traufzone_alt, 0,93 m Versatz | Altteile ersetzen, Diff ohne globale Verschiebung gegenprüfen (KORREKTUR Runde 5: Hauptursache war der Rahmenversatz, siehe L11)
- L6 Druckbarkeit ist eine Prüfung mit Sollwert (1 Teilnetz, wasserdicht, Wandstärke), nicht ein Endschritt. Splitter entstehen durch deckungsgleiche Flächen und Spalte im mm-Bereich, deshalb einbetten | Runde 4 | `druck_vorcheck.py`, Generator-Option einbindung
- L7 Overlays brauchen Verdeckung (Z-Puffer), sonst entstehen Scheinfehler durch Wände | schiefer „Pfeiler“ = Rückwandfenster | Overlay-Werkzeug (Runde 5)
- L8 Kantenwolken können blanke Flächen nicht entscheiden (Wand oder Öffnung). Dafür braucht es dichte Wolke oder Textur | Stirnwände | offen
- L9 Fehlerliste je kleinstem Unterelement, nie je durchgehender Linie. Agenten-„ok“ immer selbst nachprüfen | Kämpfer, Sichtblatt | Prüfdisziplin
- L10 Webfotos von Aussichtspunkten (Kirchturm, Turmaussicht) sind die beste freie Dachquelle | Commons Münsterturm | Dach-Agent (läuft)
- L11 Fotoauswahl fuer eine Pruefung erst NACH der Sichtbarkeitspruefung auf die Zahl begrenzen (nicht davor), sonst fuellen verdeckte Nahfotos die Plaetze und die Datenlage wirkt 'blind' | Sohlbank hinter Konsolen: min 1 / median 3 statt 12-16 sehende Fotos | `kanten_tor.py Tor.fotos_waehlen`
- L12 Bei Quellenwiderspruch nie nach 'Signifikanz in MAD' entscheiden (saturiert, MAD des flachen Untergrunds ist winzig), sondern nach Profilschaerfe (Halbwertsbreite in m) und Instanz-Einigkeit | Wolke mit 10 cm Rauschen schlug scharfe Fotos | `kanten_tor.py urteil` (Signifikanz bei 5 k MAD gedeckelt, Halbwertsbreite)
- L13 Handmasse gelten nur auf ihrer Messebene: Handpixel auf die in der Wolke gefundene Ebene umrechnen, bevor Automatik und Hand verglichen werden (Ebenenfehler 0,75 m = 0,2-0,3 m Hoehenfehler) | M-6120 Rueckwand 6,54 vs Wolke 7,29 | `tools/muster_regression.py`
- L11 Jede Kamera nennt ihren Rahmen ausdrücklich (rahmen_verschiebung, auch [0,0,0]). Eine fehlende Angabe darf kein stilles „auf zmin schieben“ auslösen. Gegenprobe: Kamerazentrum K gegen SfM-Datei vergleichen | Diff-Werkzeuge schoben das Modell 1,45 m nach unten; ein Restversatz sah nach „Kamerafehler“ aus | K-Protokolle; `fehlteile_finden.py` liest rahmen_verschiebung wie `foto_diff.py`
- L12 Druckteilung folgt aus der Geometrie: Schnitt genau in waagerechte Unterseiten (Decke wird Bettfläche), Lage = beste von 6 Achslagen mit tragfähiger Auflage, Bettschnitt an der kleinsten Schnittfläche, Stifte nur wo beide Seiten Material haben | Laubendecke 173 m² Überhang | `druck_teilung.py` + Prüfung `druck_teile_ueberhang`, Lauf in `bauen_abnehmen.sh` bei `druck_teilung` in objekt.json
- L13 Wiederholte Anbauteile ohne Raster: Lagen je Instanz aus der Messdatei, im Quellrahmen umgerechnet. Zählprüfung nur am Foto, Modellzählung als Vorsprünge vor einer Ebene | Balkonkonsolen | Bauteiltyp `konsolenreihe` (lagen_datei + quell_rahmen), Messart `ebene_vorspruenge`

## Was die Methode heute nicht kann (ehrlich)
- Blanke Wände: Eine Kantenwolke kann Wand und Öffnung nicht unterscheiden (Stirnwände blieben ANNAHME). Dafür braucht es eine dichte Wolke oder Fototextur.
- Dach über 15 m: Abdeckung 0,20. Dafür braucht es Drohnen-/Hochframes und Dachebenen aus dem Generator.
- Rückseiten ohne Fotos: nur ANNAHME (Spiegelung).
- Figuren und Maßwerk: nur Silhouette bzw. Relief in H0.

## Neues Gebäude in Schritten
1. `tools/objekt_anlegen.py`, Fotos und Video nach `/media/oem/scan/rc-park_daten/<objekt>/`.
2. SfM + Stabilitätskarten (Nachtlauf).
3. `gitter_kette.sh <objekt>` (Nachtlauf), morgens Bericht + Viewer ansehen.
4. Formfamilien wählen (Fotos aus 3 Richtungen), Generator-Masstabelle aus dem Gitter füllen, `bauen_abnehmen.sh`.
5. Zählprotokolle am Foto, foto_diff, Sichtblatt mit Fehlerliste.
6. H0-Teileteilung, Slicer-Vorcheck, Teil neben Foto (Regel 9b), Probedruck eines Ausschnitts.

Ziel für die Miniaturwelt: Schritte 2 und 3 laufen unbeaufsichtigt, Schritt 4 wird zur Formfamilien-Erkennung automatisiert, und Handarbeit bleibt nur, wo ein Tor OFFEN meldet.
- L-OD1 Dachansichten: Turm-/Aussichtsfotos (Commons, Titel "Blick vom <Turm>", "Luftbild", "von oben", Staatsarchiv-Serien) holen, aber Registrierung gelingt nur, wenn Bodenueberlapp besteht (Telebrennweite mit Fassadendetail, Boden-Tele aufs Dach); Steilblicke von weit oben scheitern mit SIFT, ALIKED+LightGlue rettet einen Teil | Dachabdeckung >15 m 0,20 bei Bodenfotos | `tools/online_ansichten_holen.py --suche <Objekt Ort> ... --aus DIR`, `tools/online_dach_registrieren.py rein|reg` (EXIF-f je Bild, je Bild eigene Kameragruppe), `zusatzfotos_lightglue.py`
- L-OD2 Wikimedia: 1 Datei je >=25 s, kein Retry-Sturm, bei 429 abbrechen (IP-Sperre ~15 min); YouTube-Drohnenclips haben Standardlizenz und zeigten das Dach nicht brauchbar | 429-Sperre nach 11 Bildern | `online_ansichten_holen.py` (Abbruch bei Fehler)

# Feature: Trennscharfes Formmaß „Formsitz" (seit 24.11.2026)

Werkzeug `tools/formsitz.py`, eingebaut in `tools/konvergenz.py` (Urteil steigt / PLATEAU / fällt), Test `tools/test_formsitz.py`.
Ast: [Doku/projekt/kanten-messen.md](../Doku/projekt/kanten-messen.md) · Zweig `worktree-agent-a469a2add20096d49` (Commit 12b228a4a).

## Warum
Das grobe Foto-F1 (Kantenkarte gegen Fotokanten) lag am Schwabentor je Seite nur 0,00–0,16 über Zufall (Nullprobe: Kantenkarte
um 1,3/2,1 m verschoben). Es maß Kantendichte (Quaderfugen, Rauschen), nicht ob die Form sitzt → Fortschritt und PLATEAU waren blind.
Ein Maß, das ein falsch platziertes Modell fast gleich gut bewertet wie ein richtiges, kann keine Konvergenz zeigen.

## Was es misst
1. **Tiefen-Übereinstimmung je Foto:** Aus jeder Kamera des festen Fotosatzes werden Modell und dichte Wolke
   (`sfm/punkte_modell_*.npy`) als Tiefenbild gerendert (Pixel ≈ 8 cm am Objekt, Verzeichnung k1 aus der K-Datei).
2. **Treffer** = Pixel, in dem beide etwas zeigen und |Tiefenunterschied| < 25 cm.
   **Formsitz** = Treffer / alle Pixel, in denen Modell ODER Wolke etwas zeigt (eine IoU). Ein Wolkenpixel zählt erst ab 3 Punkten
   innerhalb 0,3 m (Geisterpunkte und Rückseite fallen weg).
3. **Zufallswert (Nullprobe, Pflicht):** dasselbe Modell um 1,3 bzw. 2,1 m verschoben. Nur der Abstand über Zufall zählt.
4. **Trennschärfe der Daten:** zwei Hälften der Wolke gegeneinander, minus deren Zufallswert = wie weit ein perfektes Modell über
   Zufall läge. Unabhängig vom Modell → unterscheidet „Maß blind" von „Modell schlecht".
5. **Urteil:** Nur wenn die Trennschärfe ≥ `TRENN_MIN` (ANNAHME 0,25) ist, darf `konvergenz.py` „steigt" / PLATEAU / „fällt" sagen,
   sonst „nicht trennbar (Zufallsniveau)".
6. **Nebenwerte je Seite** in `audit/konvergenz.jsonl`: `formsitz`, `formsitz_null`, `formsitz_trennschaerfe`, `formsitz_trennt`,
   `med_dz` (typischer Abstand Modell–Wolke), `a10`/`a25` (Anteil < 10/25 cm), `kontur` (Oberkontur gegen Himmelsmaske, nur Bericht).
   Bilder: `audit/formsitz.jpg` (rot = Modell vor der Wolke, blau = dahinter), violette Linie im Konvergenz-Kurvenbild.

## Belegt (1122zb-Wolke, 20 Fotos, CPU, 180 s, 0,9 GB, zwei Läufe bitgleich)
- Trennschärfe je Seite 0,61–0,65 (altes F1: 0,00–0,16 über Zufall).
- Nord 0,16 gegen Zufall 0,04 · Süd 0,38 / 0,05 · West 0,41 / 0,15 · Ost 0,08 / 0,04 (Ost: altes Modell gegen neue Wolke, siehe Grenzen).
- Nullprobe 1 m senkrecht zur Wand: Abfall Nord 0,13 · Süd 0,36 · West 0,39.
- Rot-Probe Fassade 0,35 m nach außen: Süd −0,33, West −0,32, Nord −0,085 erkannt; andere Seiten ≤ 0,04 (schlägt auf der richtigen Seite an).
- Bestätigt den Hauptbefund 24.11.: Modell 0,3 m nach innen → Nord +0,16, Süd +0,12 (Körperwand stand auf LoD2- statt Fotokanten-Ebene).

## Grenzen (offen)
- **Höhe fast blind:** ±0,3 m in z → Abfall ≤ 0,005, ±2 m → 0,01–0,06. Gesims/Dach/Laterne in falscher Höhe fällt nicht auf →
  zweites Maß nötig (Traufe/Gesimse über Tiefensprünge).
- **Längs der Wand schwach** (Nord ±1 m: 0,02–0,06).
- **Bezug ist die dichte Wolke:** liegt die Wolke falsch, zählt es als Modellfehler → Lage-Tore bleiben Voraussetzung.
- `TRENN_MIN` 0,25 nur an einem Objekt geprüft (synthetisch verrauscht 0,16, echt 0,61–0,65).
- Oberkontur nur Bericht: Turmspitze in den meisten Satzfotos abgeschnitten/verdeckt.

## Benutzung
`tools/py tools/formsitz.py <objekt.json> ...` einzeln; im Kettenlauf automatisch über `tools/konvergenz.py` (abschaltbar `--ohne-formsitz`,
dann altes Urteil mit Hinweis „nicht trennscharf"). Regel: Ein neues Maß darf erst urteilen, wenn es Nullprobe und Rot-Probe besteht.

## Zweites Maß: Höhensitz (seit 24.11.2026 nachts) — gegen die Höhenblindheit
Werkzeug `tools/hoehensitz.py`, eingebaut in `tools/konvergenz.py` (Felder `hoehensitz*`, `hoehe_*`, `status_hoehe`; abschaltbar `--ohne-hoehe`),
Test `tools/test_hoehensitz.py` (Schnelltest). Synonyme: Höhe, z, Gesims, Traufe, Dachfuß, Sohlbank, Uhr, Bogenscheitel, Formmaß, Konvergenz.

**Was es misst.** Je Seite (Achse aus `seiten_konvention`) im 3D-Rahmen, nicht im Foto: für Modell und dichte Wolke je Wandstreifen (1 m breit) und
Höhenzelle (5 cm) die äußerste gestützte Schicht (erster Punkt von außen mit ≥ 5 Punkten in 15 cm dahinter; Geisterpunkte zählen nicht).
Waagerechte Strukturlinien = Sprünge dieser Außenlage in z (Traufe, Gesims Unter-/Oberkante, Rücksprung, Durchfahrtsende), gleichmäßige Dachneigung
wird abgezogen. Jede Modell-Linie sucht im selben Streifen die nächste Wolken-Linie gleichen Vorzeichens (≤ 1 m) → dz.
`hoehensitz` = F1 aus „Modell-Linien < 25 cm" und „Wolken-Linien < 25 cm"; dazu a10/a25, med|dz|, Fehlerliste (Streifen t, Höhe z, dz,
„Modell zu hoch/zu tief/ohne Partner"). Nur Zellen, die Modell UND Wolke belegen, zählen.
Warum 3D statt Tiefensprung im Foto: ein ausladendes Gesims wird aus tieferer Kamera um Ausladung·tan(Blickhöhe) falsch in z gelesen (Rezept-Falle,
1,4 m Ausladung + 10 m Höhenunterschied = +0,8 m); im Seitenrahmen ist z direkt die Höhe, kein Render, < 1 min CPU.

**Nullprobe / Trennschärfe / Rot** wie beim Formsitz: Zufall = Modell 1,3/2,1 m in ±z; Trennschärfe = Wolkenhälfte A gegen B minus A in z
verschoben; Urteil nur bei Trennschärfe ≥ 0,25 und ≥ 8 Wolken-Linien. Rot: stärkste richtig sitzende Linie der Seite um 0,5 m gehoben →
erkannt, wenn die Fehlerliste sie in ≥ der Hälfte ihrer Streifen als „zu hoch ~0,5" nennt und diese Seite stärker fällt als jede andere.

**Ergänzt den Formsitz (gemessen, orthogonal):** Modell ±0,25/0,5 m senkrecht zur Wand ändert den Höhensitz um ≤ 0,012, z ±0,3 m senkt die Decke um
0,31–0,47 (Formsitz in z: ≤ 0,005).

### Belegt
- Synthetisch (Turm, 2 Gesimse, Traufplatte, Sohlbänke): Modell = Wahrheit ≥ 0,8 (bis 1,0) bei Zufall ≤ 0,1; ±0,3/1/2 m in z Abfall ≥ 0,3 je Seite;
  echtes STL mit Süd-Gesims 0,5 m zu hoch → nur Süd fällt (0,19–0,3), Fehlerliste nennt z ~13,5 m, dz ~ −0,5 „Modell zu hoch"; 0,6-m-Rauschwolke →
  nicht trennbar.
- Schwabentor 1122 (Wolke 12 M im Bereich → 6 M, Modell 4 M Punkte, CPU 39 s ohne Proben, 193 s mit --probe --rot, < 1 GB):
  Trennschärfe Nord 0,49 · Süd 0,56 · West 0,43 · Ost 0,41 (alle trennen).
  Decke-Nullprobe (Wolkenhälfte als perfektes Modell) z ±0,3 m: Abfall Nord 0,43/0,47 · Süd 0,44/0,46 · West 0,38/0,39 · Ost 0,31/0,33.
  Modell 1122: Nord 0,29 (Zufall 0,22) · Süd 0,23 (0,15) · West 0,13 (0,17, unter Zufall) · Ost 0,21 (0,13) → Höhenstruktur des Modells sitzt kaum über
  Zufall. z-Abtastung des Modells: Süd hat ein deutliches Maximum bei 0..+0,1 m (±0,6 m → 0,08–0,15), Nord bei −0,2 m, West/Ost flach.
  Fehlerliste Ost: Linie bei z 36,0 m in mehreren Streifen, Wolke ~0,8–1,0 m höher (Traufe/Galerie, Modell zu tief) — ungeprüft, Bildbefund nötig.
  Rot am Bestand: Seitenabfall nur 0,02–0,07 (eine Linie unter 80–390), immer auf der richtigen Seite außer Modell-West (Linie bei 0,76 m, 1 Streifen);
  Meldung der gehobenen Linie Modell 1/4 Seiten (Nord/Ost: gehobene Traufe 38,6 m liegt über der Wolke, p99 z 35 m), Wolkenhälfte 3/4.

### Grenzen (offen)
- Wolkenhälften teilen Artefakte der Wolke (Schichtung) → Decke überschätzt die Datenqualität; besser Teilung nach Quellfoto (Punkte tragen keine Quelle).
- Eine einzelne falsche Linie bewegt den Seitenwert kaum; dafür die Fehlerliste lesen (`hoehe_fehler` in konvergenz.jsonl).
- Fenster schmaler als ein Streifen und Bänder < 0,3 m Höhe werden kaum erkannt; Ecken werden über die gestützte Außenschicht abgefangen.
- Über der Wolkenobergrenze (Schwabentor ~35 m dicht) keine Aussage über Traufe/Dach.
- Schwellen (Sprung 0,12 m, Streifen 1 m, Such 1 m) ANNAHME, nur an einem Objekt geprüft.

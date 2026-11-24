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
- **Durchsicht/Verdeckung (seit 24.11. abends):** fehlt in der Wolke die Vorderflaeche (Fremdbau davor nicht rekonstruiert, Wand duenn belegt), sah das Tiefenbild auf die Rueckwand (Ost 1122zb: med|dz| 3,57 m ohne Modellfehler). Jetzt: Pixel mit Wolke hinter dem Modellkoerper und Pixel hinter Aussenwolke (60 m Sichtschutz) zaehlen nicht; Felder `durchsicht`/`verdeckt`/`unbeobachtet`; Seite mit Durchsicht > 0,3 oder unbeobachtet > 0,5 → 'Bezug fehlt', kein Urteil (ANNAHMEN). Test `tools/test_formsitz_durchblick.py`.
- `TRENN_MIN` 0,25 nur an einem Objekt geprüft (synthetisch verrauscht 0,16, echt 0,61–0,65).
- Oberkontur nur Bericht: Turmspitze in den meisten Satzfotos abgeschnitten/verdeckt.

## Benutzung
`tools/py tools/formsitz.py <objekt.json> ...` einzeln; im Kettenlauf automatisch über `tools/konvergenz.py` (abschaltbar `--ohne-formsitz`,
dann altes Urteil mit Hinweis „nicht trennscharf"). Regel: Ein neues Maß darf erst urteilen, wenn es Nullprobe und Rot-Probe besteht.

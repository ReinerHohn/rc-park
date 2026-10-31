# Lernjournal Martinstor — Detailschleife (Foto ↔ Modell)

Zweck: jeder Schritt der Detailverbesserung wird hier festgehalten (Beobachtung, Abweichung, Änderung, Ergebnis, Lehre),
damit man **offline** nachvollziehen und weiterlernen kann. Neue Einträge unten anhängen, nichts löschen. Datum 2026-10-31.

**Ziel:** Das H0-Modell (1:87) soll beim Anblick im Miniaturwelt ein echtes „Wow“ auslösen: erkennbar, fein, druckbar.
**Regel:** Foto schlägt Notiz (Lehre aus `hofgut_sternen/STAND.md`): erst am Foto messen, dann im Generator ändern.

## Datenlage (Quellen, alle frei lizenziert, Autor/Lizenz in `daten/martinstor/fotos/manifest.json`)

- 60 Fotos der Wikimedia-Commons-Kategorie „Martinstor (Freiburg im Breisgau)“ (`tools/commons_harvest.py`, 46 Dateien lokal verwertbar).
  Befehl: `python3 tools/commons_harvest.py --category "Martinstor (Freiburg im Breisgau)" --max 60 --width 1600 --out daten/martinstor/fotos`
- Beste Detailfotos (Index in sortierter Liste): `031_…8005.jpg` (2025, Schrägblick auf Turmkopf), `043_…Martinstor_2.jpg` (Turmkopf, Uhr),
  `042_…Martinstor_1.jpg`, `030_…7999.jpg`, `040/041_Freiburg_im_Breisgau_45/46.jpg`; Gesamtansicht Vergleich: `modelle/martinstor_gen/mt_vergleich.jpg`.
- **Achtung Zeitebene:** `023_Freiburg_Bauten_b_200.jpg` und `024_…_201.jpg` sind **historische Vermessungspläne des ALTEN Tors vor 1901**
  (Aufriss, Schnitte, Grundrisse, ca. 22 m hoch, Zeltdach mit Glockentürmchen). Sie gelten **nicht** für den heutigen Turm mit Ecktürmchen.
  Brauchbar nur für: Rundbogentor, Bruchstein-Quaderung, Uhr-Gestaltung (römische Ziffern). Nicht für Dach/Türmchen.
- OSM-Teile (Schaft 13,4 × 12,7 m, Traufe 33 m, Türmchen 28–43,5 m), LOD2 (Höhe 45,3 m), Scan-Hülle (`modelle/scan_koerper/`).

## Eintrag 0 — Ausgangsbefund (Modell `martinstor_detail_gen.py` gegen Fotos 031/043)

| Teil | Foto (heutiger Turm) | Modell (Ausgangsstand) | Urteil |
|---|---|---|---|
| Dach | steil, **glatte Kupferdeckung** mit senkrechten Stehfalzen; oben abgeflacht; **keine Gauben** | 16 Schindel-Lagen, **4 Gauben** | Gauben **falsch** (aus alter Notiz übernommen) |
| Glockenstock | **abgesetztes weißes Geschoss** mit 2 Rundbogen-Schallöffnungen + gestuften Eckquadern zwischen Zinnen und Dach | fehlt komplett, Dach sitzt direkt auf der Traufe | fehlt |
| Kragdach | weit auskragendes **Holzkonsolen-Dach** (Kupferschräge) über den Zinnen | nur kleine Konsolen | stark vereinfacht |
| Zinnen | ~5 breite Zinnen je Seite, unter dem Kragdach | feine kleine Zähne (Konsolfries) | zu fein/falsch |
| Ecktürmchen | **achteckige Erker**: Sandstein-Sockel, Brüstung mit **X-Fachwerk**, offene Arkade, spitzes Kupferdach, Goldkugel | quadratischer Block mit Pyramide | stark vereinfacht |
| Uhr | Rahmen mit **gezacktem Innenkranz** und **Giebel (Verdachung)**, römische Ziffern in Gold | Kreis in Rechteckrahmen, Marken | Giebel + Kranz fehlen |
| Dachreiter | schlanke Spitze, **Wetterfahne**, 4 Goldkugeln auf den Dachecken | Laterne + Spitze, 1 Kugel | Kugeln fehlen |
| Schaft | verputzt, **Eckquader gezahnt**, Mauer **läuft unten breiter aus** (Steinsockel) | Quader ja; Schaft durchgehend 13,4 m breit | Proportion wahrscheinlich falsch |

**Lehre 0:** Die Silhouette passte, aber Gaube/Glockenstock/Kragdach/Erker-Aufbau waren falsch oder fehlten. Das Auge-gegen-Foto-Prüfen hat
mehr gefunden als alle Zahlenprüfungen (Wasserdichtigkeit, Bauraum): die Zahlen waren alle „grün“.

## Eintrag 1 — Höhe und Breite: drei unabhängige Messungen stimmen überein

Offene Frage seit Anfang: 45,9 / 54 / 65 m. Neue Auswertung (Maßstab-frei, nur Verhältnisse):

- **Scan** (3D, perspektivfrei): Höhe / Fußbreite ≈ 3,4; Höhe / oberer Schaft ≈ 4,9.
- **OSM**: Fußbreite 13,4 m. ⇒ Höhe ≈ 13,4 × 3,4 ≈ 45,2 m. **LOD2 sagt 45,3 m.** Zwei unabhängige Quellen, dasselbe Ergebnis.
- **Schaft** oben ≈ 9 m (Scan 9,2–9,5 m; LOD2-Footprint 9 m), also **schmaler als der Fuß**: das Tor läuft unten breiter aus (Steinsockel).
- Die Textquellen (60/63/65/66 m) stimmen untereinander, könnten aber auf eine gemeinsame Zahl zurückgehen; sie passen nicht zu den
  Messdaten. **Arbeitsannahme: H ≈ 45,3 m** (LOD2 + Scan + OSM-Breite). Für 62 m ließe sich das Modell gleichmäßig skalieren
  (`martinstor_detail_65m_h0.stl`), das hätte dann aber 18 m Fußbreite, was keiner der Datensätze stützt.

**Lehre 1:** Wenn mehrere Messungen mit anderem Fehlerprofil dasselbe sagen, wiegen sie mehr als eine Textangabe. Dennoch bleibt es eine
Annahme; endgültig wäre ein einziges vermessenes Maß (z. B. Turmbreite am Uhrgeschoss oder Torbogenbreite).

## Eintrag 2 — Vertikales Layout aus dem Foto (Auswertung `031_…8005.jpg`, Einheit: Uhrdurchmesser)

Pixelmessung am Foto (Uhrdurchmesser ≈ 230 px ⇒ Maßstab ≈ 85 px je 2,7 m-Uhr = Vergleichsgröße), Höhen **über Uhrmitte**:

| Merkmal | px ab Uhrmitte | Höhe über Uhrmitte (bei Uhr ⌀ 3,5 m) |
|---|---|---|
| Giebel der Uhrverdachung (Spitze) | 235 | ≈ 3,6 m |
| Zinnen Oberkante | 295 | ≈ 4,5 m |
| Unterkante Kragdach (Konsolen) | 325 | ≈ 5,0 m |
| Kupferschräge Oberkante / Fuß Glockenstock | 405 | ≈ 6,2 m |
| Traufe Dach / Oberkante Glockenstock | 645 | ≈ 9,9 m |
| First Dach (abgeflacht) | 905 | ≈ 13,8 m |
| Spitze Dachreiter | 1185 | ≈ 18,1 m |

Aus dem Gesamtfoto `mt_vergleich.jpg`: Uhr ≈ 0,38–0,62 der Turmhöhe (perspektivverzerrt, nur grob). Zusammen mit Eintrag 1 (H ≈ 45 m)
ergibt sich Uhrmitte ≈ 27 m, Zinnen ≈ 32–33 m (deckt sich mit OSM-Traufe 33 m), Dachspitze ≈ 45 m.
Die Perspektive (Blick steil nach oben) staucht obere Teile: Zahlen sind ±15 %.

**Lehre 2:** Das alte Modell hatte die Uhr bei 20 m (zu tief) und das Dach von 33 bis 53 m (Dach ~ 20 m hoch!). Real ist der gesamte Dachbereich
(Glockenstock + Dach + Reiter) nur ≈ 12–13 m hoch. Das Dach war etwa doppelt so hoch wie in Wirklichkeit.


## Eintrag 3 — Neuer Generator `modelle/martinstor_v3_gen.py` (Aufbau nach Foto, Höhe 45,3 m)

Änderungen gegenüber `martinstor_detail_gen.py` (jede mit Grund aus Eintrag 0–2):

| Änderung | Grund |
|---|---|
| Gauben entfernt | Foto 031/043: Dach ist glatt, keine Gauben |
| Neuer **abgesetzter Glockenstock** (6,8 × 7,2 m) mit je 2 Rundbogen-Schallöffnungen pro Seite + gestufte Eckquader | Foto 031/043 |
| **Zinnenkranz** mit 5 breiten Zinnen je Seite + Holzkonsolen + **Kupferschräge (Kragdach)** | Foto 031 |
| Kupferdach steiler, oben abgeflacht, **4 Goldkugeln** auf den Ecken, Dachreiter mit Knauf, Spitze, Fahne | Foto 031/043 |
| Ecktürmchen: **achteckiger Erker** (Fachwerk-Brüstung mit X-Schlitzen, 8 Säulen, spitzes Kupferdach, Kugel) auf Sandsteinturm mit Auskragung | Foto 031/043 |
| Uhr bei 27 m, Ø 3,5 m, **Giebel** und **12-zackiger Kranz** | Eintrag 2: Uhr war bei 20 m zu tief |
| Rumpf: senkrechter **Steinsockel** (11,6 × 13,4 m, 12,5 m hoch) + nach oben **verjüngter Schaft** (→ 9,6 × 10,0 m am Kopf) | Foto-Vergleich nach Eintrag 3a (siehe unten) |
| Eckquader laufen mit der Verjüngung (`quoins3`, je Lage eigene Halbmaße) | gleiche Ursache |

**3a — Fehler und Korrektur im Rumpf (wichtigste Lehre dieses Schritts).** Erste Fassung: Steinsockel 13,4 m breit + *senkrechter* Schaft 9 m darüber.
Im Seiten-an-Seiten-Vergleich mit dem Gesamtfoto (`mt_vergleich.jpg`) sah das wie ein breites Podest mit aufgesetztem Turm aus. Das echte Tor hat einen
**durchgehenden Anlauf** (Mauer verjüngt sich stetig). Mit dem Frustum-Rumpf passt Silhouette und Wirkung.
Randbedingung für Details auf geneigten Flächen: Reliefs sind Quader an einer festen Ebene. Bei 3,7° Neigung weicht die Wandebene auf 1 m Höhe um 6 cm ab,
das sind im Maßstab 1:87 knapp 0,7 mm und damit eine Reliefdicke. Darum bekommt **jedes Detail die Halbmaße auf seiner eigenen Höhe** (`hxy(z)`);
lange Elemente (Torbogen) bleiben im senkrechten Sockel.

**Werte:** 598 Bauteile, 231 Schnitte, ≈ 20 500 Dreiecke, Höhe 520,7 mm (1:87). Läuft in ≈ 20 s.
**Lehre 3:** (a) Zahlen („wasserdicht, passt in den Bauraum“) hatten die Fehler nicht gesehen; erst der Bildvergleich mit Foto (links Foto, rechts
Modell, gleiche Höhe) zeigte, dass der Rumpf falsch war. (b) Mehrere Quellen (Foto-Maßstab, Uhr-Ø, Scan-Verhältnis) mussten zusammenspielen, keine allein reichte.
(c) Der Renderer (`rend.py`, Painter-Algorithmus, kein GPU nötig) reicht für den Vergleich; er zeigt Dreiecke als feine Linien, das ist nur Darstellung.

## Eintrag 4 — Feinstruktur: Bruchstein, unregelmäßige Eckquader, Stehfalze

Beobachtung am Foto (`mt_vergleich.jpg`, `042_…Martinstor_1.jpg`): Der Sockel besteht aus **groben, unregelmäßigen Bruchsteinen** (verschiedene Höhen und Breiten,
tiefe Fugen); die Eckquader des Schafts sind **gezahnt, aber nicht gleichmäßig** (wechselnde Länge und Vorsprung); das Kupferdach hat **senkrechte Stehfalze**.

| Maßnahme (Code in `martinstor_v3_gen.py`) | Werte | Wirkung im Druck |
|---|---|---|
| `bruchstein()`: Quader je Lage 0,48–0,78 m hoch, 0,7–1,7 m breit, Vorsprung 0,05–0,22 m, Fuge 6 cm; Aussparung für Tor, Tafel, Fenster | fester Zufallsstart `random.Random(1900)` → reproduzierbar | Relief 0,6–2,5 mm, Fugen 0,7 mm |
| `quoins3()` mit Zufall: Länge lang 0,95–1,75 m / kurz 0,55–0,95 m, Vorsprung 0,08–0,2 m | gleiche Reihe pro Lauf | gezahnter, lebendiger Rand |
| `falze()`: je Dachseite ≈ 12 Rillen (6 cm breit, 8 cm tief), nur bis dahin, wo die Dachfläche noch breit genug ist | – | Kupferdach-Charakter |

**Technische Lehren aus diesem Schritt:**
1. **STL nicht wasserdicht, obwohl die Boolesche Operation (Manifold) sauber war.** Ursache: Uhr-Giebel (Prisma) und Rahmen berührten sich an einer
   Kante exakt (4 Flächen an 4 Kanten, bei x = ±5,02 m, z ≈ 29,5 m). Behebung: Prisma sitzt jetzt mit 2 cm Überlappung auf dem Rahmen, nicht mehr kantengleich.
   **Regel:** Bauteile dürfen sich nie nur in einer Kante oder Fläche exakt berühren; immer mit ≥ 1–2 cm Überlappung bauen (auch ZB−0.01, 0.02 Extrusion).
   Diagnose: `np.unique(m.edges_sorted, axis=0, return_counts=True)` → Kanten mit Zähler ≠ 2 zeigen die Stelle.
2. Float32 im STL reicht für 1:87 aus (Rundungsfehler < 0,0001 mm), das war nicht die Ursache.
3. Mehr Teile = nur etwas länger: 1034 Bauteile, 203 Schnitte → ≈ 26 300 Dreiecke, Lauf ≈ 25 s.

**Ergebnis:** `modelle/h0/martinstor_v3_h0.stl`: 141,8 × 159,4 × 520,7 mm (1:87), wasserdicht, 26 302 Flächen, **3 Teile** (je ≈ 174 mm hoch), nur **0,4 %** dünne Wand (Vorgänger: 1,3 %), Wand p5 2,5 mm.

## Eintrag 5 — Hofgut-Fehler (Nebenfund beim Anschauen des Viewers)

`hofgut_h0.stl` war eine 20-Flächen-Platte. Ursache: `wasserdicht()` in `h0_druckfertig.py` ließ pymeshfix auf das Gesamtmesh los (behält nur die größte Komponente);
das Hofgut besteht aus 10 739 Einzelteilen. Behoben: Reparatur je Komponente + Schutzprüfung (Abbruch, wenn die Ausdehnung > 2 % schrumpft).
Neu gerechnet: 128 864 Flächen, 485 × 297 × 225 mm, 6 Teile, wasserdicht. **Aber 26 % der Wand ist dünner als 0,8 mm** (Dachziegel/Gauben als Flächen) — das Modell
braucht vor dem Druck eine Verdickung (`--solid`) oder andere Dachbehandlung. Das steht noch aus.
**Lehre 5:** Immer die Flächenzahl vor und nach der Reparatur vergleichen; ein „wasserdicht: ja“ im Bericht sagt nichts über den Inhalt.

## Offene Punkte der Detailschleife (nächste Stufen)
1. Am Foto ablesbar, noch nicht gebaut: Wappen/Reliefs auf dem Kragdach, Fachwerk-Muster im Erker (nur X statt Rautenmuster), Fensterläden, Wetterfahne mit Schrift,
   Nachbarhaus links (Erker „Zum Walfisch“), Torvorbau seitlich (zweiter Bogen im Foto links).
2. Maße am Bauplan gegenprüfen (`bauforschung-bw.de`-PDF der Denkmalbehörde).
3. Mit zwei weiteren Fotos (z. B. Rückseite Tor) das Doppeladler-Relief und die Rückfassade prüfen (Foto 026/027).
4. SfM aus den 46 Commons-Fotos (COLMAP-GPU-Wrapper) als unabhängige 3D-Kontrolle der Proportionen.

## Eintrag 6 — Korrektur der Höhe: v4 mit 54 m (Eintrag 1 war zu optimistisch)

Auslöser: Seitenvergleich v3 gegen `042_…Martinstor_1.jpg` und `030_…7999.jpg` (wiederholtes Vergleichen mit neuem Foto, andere Perspektive).
Das Modell wirkte **gedrungen**: Kopf (Zinnen bis Spitze) im Foto ≈ 40 % der Gesamthöhe, im v3 nur 26 %; Turmkegel der Erker im Foto doppelt so hoch.

**Messung am Foto (Pixel, `042`, Bild 1500 × 2000):**
- Torbogen-Öffnung ≈ 215 px breit ↔ im Modell 6,0 m ⇒ Uhr (Ø ≈ 160 px) ≈ **4,6 m** statt der angenommenen 3,5 m.
- Von Uhrmitte bis Spitze ≈ 5,15 Uhrdurchmesser ⇒ **≈ 24 m** über der Uhr (v3: 18 m).
- Uhr bei 0,55 der Höhe; Zinnen 0,62–0,65; Kragdach 0,65–0,67; Glockenstock 0,67–0,75; Dachfirst 0,88; Spitze 1,0.
  Mit H = 54 m ergibt das: Uhrmitte 29,7 m, Zinnen 34 m, Glockenstock 37–40 m, Firstkante 47 m, Spitze 54 m.
  Das deckt sich mit den **OSM-Werten (Traufe 33 m, Dach bis 47 m, Spitze 53 m)**. Perspektive (Blick nach oben) staucht den Kopf, die wahren Werte liegen eher darüber.
- Der Dachreiter (Spitze) ist ≈ 6,5 m lang (v3: 4 m).

**Neubewertung von Eintrag 1:** LOD2 (45,3 m) und der Scan (45,9 m angenommen) messen offenbar nur die **Dachfläche bis zur Firstkante** (≈ 47 m laut OSM),
nicht den Dachreiter. Der Scan hatte die dünne Spitze nicht erfasst (Höhe = Zuschnitt-Obergrenze). Damit sind die „drei übereinstimmenden Quellen“ aus Eintrag 1
**keine unabhängigen Belege für 45 m**, sondern gemeinsam unvollständig. Die Textquellen (60–66 m) können Spitze + Wetterfahne meinen; 54 m ist die
bestbelegte Zahl (OSM + Foto-Verhältnisse). Rest-Unsicherheit ± 5 m, bis ein vermessenes Maß vorliegt.
**Lehre 6:** Nicht auf Übereinstimmung von Quellen vertrauen, wenn sie dieselbe Lücke haben (hier: Spitze nicht erfasst). Ein zweites Foto aus anderer Richtung
hat den Fehler gezeigt, den die Auswertung des ersten nicht zeigte. Sicherheitsregel: jede Annahme aus einem Foto an einem zweiten gegenprüfen.

**Änderungen v4 (`martinstor_v4_gen.py`, kopiert aus v3, v3 bleibt reproduzierbar):**

| Größe | v3 | v4 | Grund |
|---|---|---|---|
| Gesamthöhe | 45,3 m | **54,0 m** | s. o. |
| Sockel (Stein) | 11,6 × 13,4, 10,0 m hoch | 12,0 × 13,6, **8,0 m** | Foto: Putz beginnt knapp über dem Torbogen |
| Schaftkopf | 9,6 × 10,0 | 10,6 × 11,4 | Foto: Turm breiter als angenommen |
| Uhr | Mitte 27,0 m, r 1,75 m | **29,7 m, r 2,3 m** | Maßstab Torbogen |
| Zinnen | 32,3 m | **34,0 m** | Foto, OSM-Traufe |
| Glockenstock | 2,5 m hoch | 3,3 m | Foto |
| Dach | 3,6 m hoch | **6,7 m**, steiler | Foto |
| Erkerdach | 2,85 m | **5,2 m**, schlanker | Foto: Kegel ≈ 3 : 1 |
| Fenster unter Uhr | 2 + 1, z 23,4 / 20,6 | z 25,3 / 21,6 | Foto 042 |
| Adler/Tafel | 11,7–13,5 m | 8,6–10,6 m | Foto 030/042: knapp über dem Stein |

Ergebnis `modelle/h0/martinstor_v4_h0.stl` (Stand vor Adler-Vergrößerung, siehe Eintrag 7): 154,6 × 164,5 × 620,7 mm (1:87), 24 258 Flächen, wasserdicht, 3 Teile à ≈ 207 mm, 0,5 % dünne Wand (Wand p5 2,6 mm).

**Noch sichtbar anders als das Foto:** Der Doppeladler ist im Modell zu klein (Foto ≈ 2,6 × 3 m, Modell ≈ 1,8 m); die Quaderbänder könnten noch gröber sein;
Fachwerk der Erker ist nur ein X (Foto: X mit Zierleisten); es gibt keine Seitenbauten (Erkerhaus links, zweiter Torbogen).

## Eintrag 7 – Doppeladler vergrößert (v4, Detailschleife)

- Änderung: Tafel 2,8 × 3,2 m (vorher 1,8 × 1,8 m), Vertiefung + Adlerkugeln mit Faktor 1,5, Mitte z = 10,2 m (Foto 030/042: Adler ≈ 2,6 × 3 m).
- Prüfung: neu generiert (23 216 Flächen, wasserdicht), Seitenansicht gerendert, H0-Lauf erneut: 154,6 × 164,5 × 620,7 mm, 3 Teile, 0,4 % dünne Wand, wasserdicht.
- Lehre: Die Differenzliste aus dem Fotovergleich (Eintrag 6) direkt abarbeiten – jede Zeile ist ein überprüfbarer Schritt. Ein Render des Ausschnitts genügt als Kontrolle, bevor die ganze Pipeline läuft.
- Weiterhin offen: gröbere Quaderbänder, Zierleisten am Erker, Seitenbauten, zweiter Torbogen; echte Höhe ±5 m.

## Eintrag 8 – gröbere Quaderbänder, Zierringe am Erker (v4 final)

- Quaderlagen 0,95 m statt 0,74 m, Fuge 9 cm (bei 1:87 ≈ 11 mm Lage; die feinere Teilung ging beim Druck als Rauschen verloren).
- Erkerbrüstung: drei Zierringe (unten/Mitte/oben) zusätzlich zum X-Fachwerk.
- Ergebnis: 24 988 Flächen, wasserdicht; H0-Lauf erneut grün (siehe `martinstor_v4_h0.bericht.json`).
- Bewusst nicht gebaut: Seitenbauten und zweiter Torbogen gehören nicht zum Tor selbst (Nachbarhäuser); der Druck soll das freistehende Tor zeigen.
- Offen bleibt nur, was Daten nicht liefern: die echte Höhe (54 m ±5 m) und die Wirkung am gedruckten Teil.

Nachtrag Eintrag 8: Foto-Gegenprobe (Foto 042 neben Render, Ansicht 35°). Grobe Gestalt stimmt (Schaft mit Eckquadern, Zinnenband, vier Erkertürme, Kupferdach mit Dachreiter, Spitze). Das Modell wirkt im Render breiter als das Foto; wegen unterschiedlicher Blickwinkel (Foto fast frontal, Render diagonal) nicht belastbar → nächster Schritt wäre ein Render exakt frontal mit gleicher Brennweite. Kaufhaus-H0-Lauf scheiterte 2× an RAM (trimesh-Subdivision, 22 Mio. Kanten); gelöst nur teilweise (MemoryError-Fallback), Lauf wurde vom OOM-Killer beendet → separat, wenn nichts anderes läuft.

## Eintrag 9 – Uhr: Relief verschwand (CSG-Reihenfolge)

- Fund: Beim Nahrender der Uhr fehlten Stundenstriche, Zeiger und Nabe. Ursache: Die Nische (`cuts`) wird nach allen `adds` abgezogen und schnitt das Zifferblatt-Relief mit weg. Die Zahlen „wasserdicht, 24 988 Flächen“ hatten das nicht gezeigt.
- Fix: Zifferblatt, Striche, Zeiger und Nabe in Liste `late`, die nach dem Abzug vereinigt wird; Reliefhöhen gestaffelt (Blatt < Striche < Zeiger < Nabe), sonst koplanar/unsichtbar.
- Ergebnis: 26 482 Flächen, wasserdicht, H0 erneut grün.
- Lehre: Jedes Detail, das in eine Nische soll, muss nach dem Abziehen eingefügt werden; Details einzeln im Nahrender prüfen, nicht nur die Summenwerte.
- Foto-Gegenprobe frontal (Foto 030 neben Render 90°/−90°): Proportionen, Zinnenband, Erkertürme, Torbogen und Wappentafel stimmen grob; Torbogen im Foto etwas breiter/höher.

## Eintrag 10 – Dach und Erkertürmchen zu gedrungen (Rückmeldung des Nutzers)

- Beobachtung: Der Nutzer sah im Viewer, dass Dach und Türme zu gedrungen wirken. Der Foto-Render-Vergleich (030) bestätigt es: Foto-Dach ≈ 1,25 × so hoch wie breit, Modell < 1; Erkerkegel im Foto deutlich schlanker.
- Änderung: Glockenstock schmaler (D−4,4 / W−4,4 statt −3,4), Dach 9,0 m statt 6,7 m hoch mit schmalerem First (1,4 × 1,8 m), Erkerkegel 7,4 m statt 5,2 m und schlanker (Fuß OR+0,12). Spitze bleibt bei 54 m (kürzerer Dachreiter-Mast).
- Lehre: Proportionen (Höhe/Breite einzelner Bauteile) systematisch messen, nicht nur Gesamthöhe; Nutzerblick ernst nehmen – er fiel auf, obwohl alle Zahlen grün waren.
- Ergebnis: 25 920 Flächen, wasserdicht, H0 154,6 × 164,5 × 620,7 mm.

## Eintrag 11 – Torbogen breiter und höher

- Foto 030: Durchfahrt im Verhältnis zum Sockel breiter/höher als im Modell. Änderung: Breite 6,6 m (vorher 6,0), Kämpferhöhe 4,3 m (vorher 4,2); Scheitel 7,6 m, unter der Sockelkante (8,0 m). Keilsteine und Schlussstein im Nahrender intakt.
- Ergebnis: 26 100 Flächen, wasserdicht, H0 erneut grün (154,6 × 164,5 × 620,7 mm).
- Ehrlicher Stand: Alle Vergleiche sind Render-gegen-Foto; ein Probedruck fehlt weiterhin, die echte Höhe bleibt ±5 m unsicher.

## Eintrag 12 – Maßstabs-Nachweis gegen amtliche LiDAR-Daten (großer Umbau)

- **Auslöser:** Neues Ziel „alle Maße maßstabsgetreu, beweisen“. Textquellen nennen 60–66 m, mein Modell 54 m (nur auf OSM + Foto gestützt).
- **Neue Datenquelle:** LGL-BW DOM1/DGM1 (1 m LiDAR, ±0,15 m), frei abrufbar. Münster-Gegenprobe: 116,6 m statt amtlich 116 m.
  Ergebnis: Martinstor = **54,80 m**. Die Texte (65–66 m) sind für die heutige Spitze falsch; mein 54-m-Wert war richtig, aber nur durch Zufall der Annahmen.
- **Methode:** Modell fein unterteilen → von oben auf 1-m-Raster → je Höhenschwelle Fläche zählen wie der Laser (Zelle zählt, wenn irgendwo darin > t) → gegen Laser tabellieren.
  Drehung/Rasterphase werden gesucht, weil die Zählung davon abhängt (±15 %).
- **Fehlversuche (wichtig):** (1) SfM aus 35 Commons-Fotos: Punktwolke fast nur eine Fassadenebene, Höhe/Breite unbrauchbar → verworfen.
  (2) Punktweise Höhenabweichung nach Drehung/Verschiebung: Nachbarhäuser dominieren, Optimum sinnlos → Hypsometrie (Fläche je Höhe) ist drehfrei und robust.
  (3) Rasterung nur aus Eckpunkten ließ Löcher → feine Unterteilung (0,45 m) nötig.
- **Befund:** Gesamthöhe stimmte, aber Binnenhöhen nicht: Glockenstock-Oberkante 39,8 → ≈ 36,9 m, Dachfirst 49 → 46,2 m, Erkerkörper-Oberkante 37,2 → 33,7 m,
  Erkerkegel-Spitze 43,6 m, Dachreiter 5 → ≈ 9 m (Kegel, Fußradius ≈ 1,5 m), Schaft 12×13,6 m am Fuß → 9,8×11,3 m, oben 9,3×10,3 m (inkl. Quader ≈ 10,7 × 11,7 m im Laser).
  Zinnen niedriger (Wehrgang), Kragdach flacher, Uhr 1,9 m tiefer (27,8 m).
- **Ergebnis (Endstand):** Spitze 54,80 = 54,79 m; Schaft +7…+14 %, Zinnen +18 %, Glockenstock/Dach/Dachreiter −7…+12 %, nur Stufe 35 m +35 %; Median 7 %, Mittel 12 %. Zinnenkrone lag 0,9 m zu hoch (Randzellen im Laser 31–33 m), das fiel erst im Zellkarten-Vergleich auf, nicht in der Tabelle. Siehe `modelle/MASSPRUEFUNG_MARTINSTOR.md`.
- **Lehre:** (a) Amtliche Höhendaten schlagen Textquellen und Fotoschätzung; zuerst DOM/DGM holen, nicht erst nach Wochen. (b) Eine Stimmigkeit der Gesamthöhe beweist nichts über die Binnenhöhen.
  (c) Ein Nachweis braucht die Zählweise der Referenz (hier „höchste Fläche je Zelle“), sonst vergleicht man Äpfel mit Birnen. (d) Was von oben unsichtbar ist (Bogen, Uhr), bleibt Fotovergleich.

## Eintrag 13 – Unsichtbares messen: Verhältnisse zur laservermessenen Fassade

- Das Hook-Urteil „Torbogen/Uhr/Fenster unbewiesen“ war berechtigt. Einzige Referenz für die Querrichtung ist die Fassadenbreite (Laser). Torbogen, Zifferblatt, Schild als Verhältnis dazu auf **zwei** Fotos gemessen (Tabelle in `MASSPRUEFUNG_MARTINSTOR.md`, Teil 2).
- Ergebnis: Durchfahrt 4,7 m (nicht 6,6), Zifferblatt 4,2 m (nicht 4,6), Wappenschild 1,7 × 2,3 m (nicht 2,8 × 3,2). Mein früheres „Foto zeigt breiter“ war ein Augenvergleich gegen ein schräges Render und lag falsch.
- Lehre: Ein Augenvergleich zweier Bilder aus verschiedenen Blickwinkeln misst nichts. Messen am **selben** Foto, **in einer Ebene**, **auf gleicher Bildhöhe**, Verhältnis zu einer bekannten Länge. Zwei Fotos geben die Streuung (hier ≤ 10 %).
- Eine Kameralösung (PnP) aus handgesetzten 2D-3D-Punkten wurde erwogen und verworfen: zu viele mehrdeutige Zuordnungen (welcher der vier Erker), Fehler größer als der Gewinn.

## Eintrag 14 – Höhenlage der Uhr, und eine gescheiterte Kamerabestimmung

- Messung über das kreisrunde Zifferblatt: senkrechte Stauchung 0,88 liefert den lokalen senkrechten Maßstab; Uhrmitte liegt 3,5 m unter dem Gesims (Modell 3,15 m) → ±0,4 m (Teil 3 der Maßprüfung).
- PnP-Kamerabestimmung aus fünf hochliegenden Ankern: mathematisch „guter“ Fit (6,6 px), aber Kamerahöhe 13,8 m – physikalisch unmöglich. Mit realer Augenhöhe 31 px Fehler, Uhr 256 px daneben. Lehre: Ein kleiner Restfehler beweist nichts, wenn die Anker alle in einer Ebene/einem Höhenband liegen; die Lösung muss auch **plausibel** sein (Kamerahöhe!). Extrapolation aus 40–55 m nach 7 m ist nicht bestimmt.
- Beim Ablesen am Gitterbild zweimal Koordinatensysteme verwechselt (Anzeige 0,9× gegen Originalpixel). Gitter immer in Originalpixeln beschriften und nur dort ablesen.

## Eintrag 15 – LoD2 als zweite Referenz, und was nicht half

- LGL-BW LoD2 (Geometrie statt Raster) liefert Grundriss 115 m² (Modell −4 %) und Dachfirst 45,0 m (Modell 46,2). Den First auf 45,0 zu setzen verschlechterte den Laser-Vergleich → verworfen. Zwei Referenzen widersprechen sich um 1,2 m, ich entscheide nicht „nach Bauchgefühl“, sondern halte den Widerspruch offen (`MASSPRUEFUNG_MARTINSTOR.md`, Teil 4).
- Lehre: Eine zweite Quelle bestätigt nur, wo sie unabhängig ist. LoD2 ist selbst aus Laserdaten abgeleitet und verallgemeinert; sie ist keine unabhängige Wahrheit.
- Rohpunktwolke (ALS) ist bei LGL BW nicht über denselben Weg frei abrufbar (404 für getestete Pfade); damit bleibt 1 m die feinste verfügbare Auflösung.

## Eintrag 16 – Parametersuche: das Modell steht am Optimum

- 8 Varianten gegen den Laser (Glockenstock-Oberkante 4,4–5,3 m über ZZ, Erkerkörper-Oberkante 32,2–33,2 m, Traufüberstand 1,0–2,0 m), jede mit eigener Generierung und der Tabelle `masspruefung_tabelle.py`.
- Ergebnis: Keine Variante verbessert Mittel (12 %) und Median (7 %) zugleich; der aktuelle Stand (5,0 / 32,7 / 1,5) ist am besten. Stufe 35 m springt zwischen +22 % und +35 %, das sind 17 gegen 27 m², also ein bis zwei Randzellen. Diese Stufe ist damit **innerhalb des Rauschens der Methode** (Raster-Phase und Drehung ändern die Zählung um etwa ±15 %), nicht ein klarer Modellfehler.
- Lehre: Eine Abweichung ist erst dann ein Fehler, wenn sie größer ist als die Streuung der Messmethode. Das gehört in jede Tabelle als Fehlerband.

## Eintrag 17 – Mehr Fotos, andere Wahrheit: Bogenhöhe und Sockelhöhe

- Kontaktbogen der 46 Fotos, drei frontale Straßenfotos (050, 002, 030) gewählt. Wieder Verhältnis zur Fassade in der Fassadenebene.
- Bogenbreite bestätigt (3 Fotos: 0,39–0,42). **Bogenhöhe falsch:** der Scheitel war mit 6,55 m 1,5 m zu hoch (aus schräger Aufnahme 030 abgeleitet); Sockeloberkante 8,0 → 6,2 m; Inschrifttafel 3,4 × 2,0 m statt 4,8 × 1,8 m, direkt über dem Bogen.
- Lehre: Ein Maß erst glauben, wenn es an mindestens drei Fotos aus unterschiedlichen Blickwinkeln übereinstimmt. Aus 030 allein war die Breite richtig, die Höhe aber falsch – bei schräger Aufnahme stimmt nur die Breite am Fuß halbwegs. Frontale, bodennahe Aufnahmen (050, 002) sind für Höhen die besseren.
- Weiterhin offen: Fenster (Größe/Lage), Sockelaufweitung, Probedruck.

## 18. Fenster nach Foto korrigiert
- Vorher: Fensterpaar bei z=25,3 (nur ~1,1 m unter Uhrmitte, kollidierte mit dem Uhrrahmen), Öffnungen 20 % zu hoch.
- Foto 042/050 (Originalpixel, Fassadenbreite 11,5 m als Maßstab): Paar ca. 4,8 m unter Uhrmitte (z≈21,65), drittes ca. 8,5 m darunter (z≈18,1), Öffnung ca. 0,6 x 0,85 m.
- Laser-Tabelle unverändert (Median 7 %), Modell wasserdicht. Beleg nur aus Fotos (±10 %), nicht aus Laser (Fenster < 1 m Raster).
- Weiter ungeprüft: Stufe 35 m, Nadel 52 m, First 46,2 vs 45,0 (LoD2), Sockelaufweitung, Probedruck.

## 19. Schwebende Teile an der Front gefunden und beseitigt
- Anlass (Nutzer): "Struktur an der Front nicht genau, komische Artefakte, Kanten aber gut".
- Pruefung `m.split()`: 15 Koerper statt 1. 12 Holzkonsolen (z 31,5-31,8) beruehrten die Zinnen nur flaechig (Stoss ohne Ueberlappung); 2 Fenster an +y/-y nutzten die Sockelbreite statt der verjuengten Wandbreite hxy(z) und schwebten vor der Wand.
- Fix: Konsolen 0,1 m in Zinne hinein; Fenster mit hh=hxy(z). Ergebnis: 1 Koerper, wasserdicht, Laser-Tabelle unveraendert (Median 7 %).
- Regel: nach jeder Aenderung Koerperzahl pruefen (muss 1 sein); Bauteile immer >=0,1 m ueberlappen.
- Dachfirst: punktweiser Vergleich (tools/masspruefung_dach.py) im 4,5-m-Umkreis der Spitze: Fehler 2,58 / 2,55 / 2,64 m fuer First 46,2 / 45,0 / 44,0; mittlere Hoehenabweichung +0,01 / -0,50 / -0,91 m. Rasterfehler dominiert, aber nur 46,2 trifft die Hoehe im Mittel -> bleibt.

## 20. Adlerrelief fehlte (CSG-Reihenfolge, zweites Mal)
- Fund: Eckpunkte in der Wappenzone -x: nur 16, Tiefen 4,85-5,01 m = nur Tafel + Nische, kein Adler. Die Adler-Kugeln lagen in `adds`, die Nische (Einsenken) wird danach abgezogen und nahm sie mit.
- Fix: Adler in `late` (nach dem Ausschnitt vereinigt), Mitte auf Nischenboden (_hT[0] + rel(0.09)). Danach 523 Eckpunkte, Relief bis 5,07 m (Tafel 5,01).
- Regel: jedes Relief IN einer Nische gehoert in `late`; Test: Eckpunkte/Tiefenkarte der Zone pruefen, nicht nur Koerperzahl und Wasserdichtheit.
- Pruefmethode: Oberflaeche abtasten (trimesh.sample) und Tiefe als Farbkarte -> sichtbar auch ohne Renderer.

## 21. Optimierer: Wettlauf um cur.stl, Wiederholbarkeit, Luftbild-Test
- Fund: lauf1.json und lauf2.json waren nicht bit-gleich. Feld-Diff: nur probe[63] (OR +0,15) wich ab (e 0,092 gegen 0,051). Ursache: parallel laufender Mehrfachstart schrieb dieselbe `cur.stl`/`cur_gen.py` (Wettlauf). Fix: Dateiname je Prozess (`cur<PID>`). Mehrfachstart-Ergebnisse davor verworfen, neu gerechnet.
- Beleg Wiederholbarkeit: lauf3.json gegen lauf4.json (nacheinander, nichts parallel): 0 Unterschiede. Ergebnis beider: 0 von 64 Proben robust besser, Parameter bleiben an der Basis.
- Mehrfachstart (5 Starts, sauber): alle erreichen bessere Laserwerte als die Basis (e 0,046-0,089, hold-out 0,055-0,096, punktweise 3,3-3,5 m gegen 0,083/0,147/4,13), aber Parameter streuen um bis zu 1,6 m (T1, rh, T0, ZZ). Das Tal ist flach: die Laserdaten legen diese Masse nicht eindeutig fest. Hold-out stammt aus denselben Daten, also nicht unabhaengig. Alle Loesungen verkleinern D/W, das Luftbild spricht fuer groessere Abstaende. Nicht uebernommen.
- Luftbild DOP20: Kugelspitzen der Tuermchen ca. 9,1 x 8,0 m gegen Modell 8,5 x 7,5 m. Test: Tuermchen-Versatz 0,4 -> 0,7 m: Laserfehler schlechter (11,9 -> 14,8 %, M1 9,1 -> 14,3 %); mit TWs 2,0/OR 0,9: 12,7 %, M1 12,4 % - ebenfalls schlechter. Ablesefehler im Luftbild ca. +-0,3 m = Grosse der Verschiebung. Verworfen, Generator unveraendert.
- Regel: eine Aenderung, die eine Quelle stuetzt und eine andere (genauere) verschlechtert, wird nicht uebernommen, solange der Unterschied im Messfehler liegt.
- Dachflaechen im Orthofoto sind verschmiert (Turm nicht sauber entzerrt); First 46,2 gegen 45,0 m damit nicht entscheidbar.

## 22. Foto-Silhouetten-Anpassung (GPU) - Oberteil des Modells gegen 3 Fotos
- Werkzeug `tools/foto_silhouette_gpu.py`: 200 000 Oberflaechenpunkte des Modells, je Kandidat-Kamera (8 Parameter: Abstand, Azimut, Elevation, Blickhoehe, Roll, Brennweite, Bildverschiebung) auf die GPU projiziert, IoU gegen Nicht-Himmel-Maske im Ausschnitt (nur oberer Turm); Kamerahoehe ueber Grund ~1,7 m als weiche Nebenbedingung. Zufallssuche 30 000 Posen + CEM, ~40 s je Foto.
- Ergebnis (2 Startwerte): Foto 044 IoU 0,92-0,93, Foto 043 0,85-0,86, Foto 042 0,77-0,81. Modellkontur liegt auf Nadel, Dach, beiden Tuermchen, Glocken- und Uhrgeschoss; bei 042 sogar auf Schaft und Torbogen (ausserhalb des Anpassungsbereichs).
- Grenzen: Quadratturm -> Azimut-Loesungen um ~90 Grad gleichwertig (044: -60 gegen +27 Grad); Abstand und Brennweite gekoppelt, daher absolute Masse nur ueber bekannte Gesamthoehe 54,8 m; Bereichsgrenzen anfangs zu eng (043 stiess an alle), danach erweitert. Streuung zwischen Startwerten 0,01-0,04 IoU = Rauschen der Anpassung, Unterschiede darunter nicht belastbar.
- Aussage: bestaetigt die Gesamtform des Oberteils unabhaengig vom Laser (Fotos), nicht einzelne Masse. Keine Modelländerung abgeleitet. Naechster Schritt waere Parametervariation (Dachhoehe, Nadel) mit IoU ueber alle drei Fotos - Effekt muss ueber dem Anpassungsrauschen liegen.
- Bilder: modelle/foto_silhouette/fit_042|043|044.png (rot = Modellkontur, gruen = Anpassungsbereich).

## 23. Dachfirst-Test gegen drei Fotos (Silhouette, GPU)
- Aufbau: Firsthoehe 43,5 / 44,8 / 46,2 / 47,6 / 49,0 m (Gesamthoehe fest 54,8 m, Nadel dehnt/staucht mit), je Variante Kamera pro Foto neu angepasst (3 Startposen, bester Wert). Datei `modelle/foto_silhouette/dachtest.json`.
- Ergebnis (IoU Mittel ueber 042/043/044): 0,854 / 0,866 / 0,877 / 0,885 / 0,888. Alle drei Fotos steigen gleichsinnig, kein Maximum im Bereich.
- Bewertung: Spanne 0,034 liegt nur knapp ueber dem Anpassungsrauschen (~0,02); die Variation verkuerzt gleichzeitig die Nadel (Verzerrung), Laser und LoD2 sprechen fuer 45-46 m. Kein Beleg fuer ein hoeheres Dach, Modell unveraendert. Eine saubere Messung braucht frontale Fotos mit bekannten Massen oder eine getrennte Variation von Dach und Nadel.

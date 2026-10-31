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

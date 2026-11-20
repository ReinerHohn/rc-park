# Fotos aufnehmen fürs automatische Modell-Overlay

Ziel: Fotos so machen, dass unser **georeferenziertes Modell** (Viadukt, Linach-Staumauer,
Höllental-Gelände …) **automatisch und scharf** perspektivisch drübergelegt werden kann —
so wenig Klicken wie möglich. Zwei Wege, der zweite ist der stärkere.

---

## Weg A — Einzelfoto (schnell, 1 Bild)
Für ein schnelles Overlay eines einzelnen Bauwerks.

**So aufnehmen:**
- **Normales Einzelfoto, KEIN Panorama** (siehe Falle unten).
- **GPS an**, vor der Aufnahme **Kompass kalibrieren** (Handy: liegende Acht; Drohne: IMU/Kompass-Kalib).
- Das **Bauwerk gut und möglichst ganz** im Bild.
- Wenn möglich **den Horizont/Bergrücken mit drauf** — damit zieht `foto_skyline_orient.py`
  die Blickrichtung aus dem Gelände gerade (unabhängig vom ungenauen Kompass).
- Scharf, ruhig, bekannte Kamera (EXIF-Brennweite + Modell → Sensorbreite).

**Läuft dann über:** `tools/foto_georef_overlay.py` (Metadaten-Start) + `tools/foto_skyline_orient.py`
(Orientierungs-Feinschliff). Fallback ohne Metadaten: `tools/foto_punkt_picker.py` (Punkte klicken).

---

## Weg B — Foto-Serie für COLMAP (bester, „jede Perspektive automatisch")
Mehrere überlappende Fotos → COLMAP rechnet **Position + Orientierung + Maßstab gemeinsam**
in **einem** Koordinatensystem. Dann wird das georef-Modell **einmal** registriert und **jede**
Aufnahme sitzt automatisch. Löst die Kopplung Position/Orientierung, die bei Einzelbildern beißt.

**So aufnehmen (die COLMAP-Regeln):**
- **15–40 Fotos**, **60–80 % Überlappung** zwischen Nachbarbildern.
- **Umrunden/Bogen ums Objekt** — nicht nur vom Fleck drehen! COLMAP braucht **Parallaxe**
  (die Kamera muss sich **bewegen**, Standort wechseln), reines Schwenken reicht nicht.
- **Mehrere Höhen/Winkel** (tief, Augenhöhe, hoch; schräg von beiden Seiten).
- **Konstante Brennweite** (nicht zoomen), **gleiche Belichtung**, alles **scharf**.
- **Keine bewegten Objekte** (Autos, Leute, Zug) als Hauptinhalt; ruhiger Hintergrund hilft.
- **Drohne ideal** (DJI Mini 4 Pro): langsam **im Orbit** ums Bauwerk, Gimbal leicht geneigt;
  EXIF liefert gutes GPS **und** Gimbal-Winkel → georef-Registrierung fast geschenkt.
- **Alle Einzelbilder behalten** (RAW/JPG), **NICHT** zu einem Panorama zusammenrechnen lassen.

**Läuft dann über:** COLMAP (SfM) → Kameraposen; danach georef-Registrierung des Modells
(7-DOF Ähnlichkeit auf die Sparse-Cloud / per GPS-Anker). *(Registrier-Skript folgt, sobald
eine echte Serie da ist.)*

---

## Was das EXIF enthalten sollte
- **GPS** (Breite/Länge) — grobe Position. Höhe ist meist unbrauchbar (siehe Fallen).
- **GPSImgDirection** (Kompass-Blickrichtung) — grober Start, wird per Skyline korrigiert.
- **FocalLength** + **Kameramodell** → Sensorbreite → Brennweite in Pixeln (Intrinsics).
  (Canon 80D Sensor 22,3 mm; APS-C ~23,6 mm; Handys klein → f35/EXIF nutzen.)

---

## Fallen (in dieser Session hart gelernt)
- **NIE ein gestitchtes Panorama** fürs Overlay. Es ist **keine einzige Kamera** — ferner
  Horizont und nahes Bauwerk gehorchen nicht derselben Projektion, keine Pose trifft beides.
  → Immer die **Einzelaufnahmen** aufheben.
- **GPS-Höhe ist unzuverlässig** (Ellipsoid vs. Geoid ~48 m, dazu ±10–30 m). Kamerahöhe
  lieber aus dem **DEM am Standort + Augenhöhe** nehmen, nicht aus EXIF.
- **Handy-Kompass ~15–25° daneben** — deshalb Skyline-Feinschliff. Drohne besser.
- **Zu wenig Parallaxe** (nur gedreht statt bewegt) → COLMAP scheitert. Umrunden!
- **Position und Orientierung koppeln** bei Einzelbildern — ein GPS-Fehler wandert in den
  Winkel. Mehrbild/COLMAP löst das sauber; darum ist Weg B stärker.

---

## Kurz-Checkliste vor Ort
1. Kompass/IMU kalibrieren, GPS an.
2. Weg B wenn möglich: **langsam ums Bauwerk, 20–30 Fotos, 70 % Überlappung, mehrere Höhen.**
3. Mindestens **ein** sauberes Einzelfoto mit **Horizont** im Bild (für Weg A / Skyline).
4. Nichts stitchen, alle Originale sichern.
5. Kameramodell notieren (für Sensorbreite), falls EXIF mal fehlt.

Gehört zu `tools/foto_georef_overlay.py`, `tools/foto_skyline_orient.py`,
`tools/foto_punkt_picker.py`, `tools/foto_modell_overlay.py`.

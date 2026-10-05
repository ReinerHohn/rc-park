# Plan: Freiburger Wahrzeichen in sehr guter Qualität drucken

> Ziel: die Hero-Wahrzeichen (nicht die Hintergrund-Masse) in **maximaler Detailschärfe**
> drucken. Ehrliche Wahrheit vorweg: **filigrane Gotik (Münster-Helm, Maßwerk) wird auf FDM
> nie gestochen scharf — dafür ist Resin (MSLA) da.** FDM ist top für die kompakten Türme/Tore.

## 1. Die Wahrzeichen-Prioliste (nach Wow + Machbarkeit)

| # | Wahrzeichen | Quelle | Beste Technik |
|---|---|---|---|
| 1 | **Münster** | ✅ Scan vorhanden (750k Poly) | **Resin** (Helm/Maßwerk) |
| 2 | **Schwabentor** | selbst scannen | FDM gut (kompakter Turm) |
| 3 | **Martinstor** | selbst scannen | FDM gut (kompakter Turm) |
| 4 | **Historisches Kaufhaus** | selbst scannen | FDM + Bemalung (Rot/Erker) |
| 5 | **Altes Rathaus** | selbst scannen | FDM + Bemalung |
| — | Hintergrund-Häuser | LoD2 (haben wir) | FDM hohl, Masse |

## 2. Quelle: so holst du jedes Wahrzeichen in scharfer Qualität

**A) Selbst scannen (bester Weg, du bist vor Ort).** Handy-Photogrammetrie:
- App **Polycam** oder **Scaniverse** (kostenlos/günstig, iOS/Android).
- **80–200 Fotos**, 3 Umläufe (Augenhöhe / leicht hoch / tief), **60–70 % Überlappung**.
- Gleichmäßiges Licht (bewölkt ideal), **keine Menschen/Autos im Bild**, einmal ganz rum.
- Maßstab merken (eine bekannte Kante, z. B. Torbreite) → später exakt skalieren.
- Export als **OBJ/STL**. (Genau so ist der Münster-Scan entstanden.)

**B) Fallback: Google 3D Tiles / `3d.freiburg.de`** — texturiertes Mesh aller Gebäude, aber
geometrisch weich. Nur wenn Scannen nicht geht (siehe `datenquellen.md`).

## 3. Mesh aufbereiten (Scan → druckbar)
Reihenfolge (Blender kostenlos, oder Meshmixer/Fusion):
1. **Boden-/Rauschreste abschneiden** (am Münster-Scan ist unten Foto-Müll).
2. **Löcher schließen** → **wasserdicht** (manifold) machen.
3. **Aufrecht stellen**, Basis plan auf Z=0, kleine **Standfläche** anlegen.
4. **Dezimieren** auf ~200–500k Dreiecke (Detail bleibt, Datei handlich).
5. Auf **Zielhöhe skalieren** (einheitlich zum Diorama, s. u.).

## 4. Zwei Druck-Spuren — je nach Qualitätsanspruch

### Spur FDM (Prusa MK4S, hast du) — gut für kompakte Türme/Tore
- **Schichthöhe 0,10–0,15 mm** (Qualität) · optional **0,25-mm-Düse** für feine Kanten.
- **3 Perimeter**, **10–15 % Infill** (oder hohl 0 % bei großen Teilen).
- **Supports: organic/tree**, nur wo nötig; Überhänge (Turmspitze) brauchen Stützen.
- **Orientierung**: Turm aufrecht; filigrane Spitze ggf. separat drucken + kleben.
- **Langsamer = sauberer**: Außenperimeter-Speed runter, Lüftung 100 % (PLA/PETG).

### Spur Resin/MSLA — für Münster-Helm, Maßwerk, echte Gotik
- MSLA-Drucker (z. B. günstiger Einstieg ~150–250 €) → **0,03–0,05 mm** = gestochen scharf.
- **Hohl aushöhlen** (Software „Hollow" 2–3 mm Wand) + **Drainagelöcher** + Supports.
- Der **einzige** Weg, den filigranen Münster-Turmhelm wirklich scharf zu bekommen.

> Faustregel: **FDM für Masse + kompakte Formen, Resin für die feinen Hero-Spitzen.**

## 5. Einheitlicher Maßstab (wichtig fürs Diorama!)
- Diorama-Stadt ist **~1:500** (`bauplan-miniaturwunderland.md`).
- Hero-Wahrzeichen dürfen **leicht überhöht** größer sein (MiWuLa macht das auch) — aber
  **ein fester Hero-Maßstab**, z. B. **1:300**, damit alle Wahrzeichen zusammenpassen.
- Beispiel Münster-Turm 116 m → 1:300 = **39 cm** (zu hoch fürs Bett → in 2 Teilen) oder
  1:500 = **23 cm** (ein Druck, passt aufs MK4S-Bett). → **Hero = 1:500, ein Stück, bettfüllend.**

## 6. Finish (das hebt es auf MiWuLa-Niveau)
Grundieren (Filler-Primer) → **Schichtlinien schleifen** → Airbrush/Pinsel Grundfarbe →
**Washing** (dunkle Lasur in die Fugen = Tiefe) → Trockenbürsten (Kanten hell) →
**LED** von innen (hohl!) → matter Klarlack. Siehe `beleuchtung-detail.md`, `farbe-drucken.md`.

## 7. Sofort-Start (diese Woche)
1. **Münster FDM-Testdruck hohl** (fertig geslict, ~4,7 h) → Proportion/Orientierung prüfen.
2. Entscheiden: **Münster final als Resin** (scharf) oder FDM 0,12 mm + schleifen/bemalen.
3. **Schwabentor + Martinstor** beim nächsten Stadtgang **scannen** (Polycam) → aufbereiten → FDM.
4. Alle Heroes auf **1:500** bringen, bemalen, LED → ins Diorama.

Bezug: [`plan-schnellstes-modell.md`](plan-schnellstes-modell.md) (Hybrid Druck+Laser),
[`bauplan-miniaturwunderland.md`](bauplan-miniaturwunderland.md) (Maßstab/Sektionen),
[`prioliste-freiburg.md`](prioliste-freiburg.md) (Wahrzeichen-Reihenfolge).

# Maximales Detail: der 3D-Scan-Weg

> Mehr Detail als jedes handmodellierte STL gibt es nur über einen **echten 3D-Scan**
> (Photogrammetrie / Laserscan) des realen Bauwerks. Das ist die Detail-Obergrenze:
> jede Figur, jedes Maßwerk, echte Steintextur.

## Vorhandene Scans des Freiburger Münsters

| Scan | Was | Quelle | Lizenz |
|---|---|---|---|
| **Komplettes Münster** | 750k Dreiecke, Photogrammetrie, volle Fassade | LAD BW (Landesamt f. Denkmalpflege), [Sketchfab](https://sketchfab.com/3d-models/freiburger-munster-f0f4d479997f48659658fafebc14f90c) | **CC BY-NC** ⚠️ |
| **Oktogon + Turmhelm** | nur der berühmte durchbrochene Turm (Hero-Feature) | kbdenkmal, [Sketchfab](https://sketchfab.com/3d-models/freiburg-ib-munster-oktogon-und-turmhelm-c99e25060a304903b9d9a3002fc06e16) | Sketchfab prüfen |
| **Stadtmodell Freiburg 3D** | mehrere Wahrzeichen auf einmal | 3ds-scan.de, [Sketchfab](https://sketchfab.com/3d-models/stadtmodell-freiburg-in-3d-e4d72fd5254840a28989e86fb8bf34f1) | prüfen |

## ⚠️ Lizenz-Falle (für kommerziellen Park kritisch)
Der LAD-BW-Scan ist **CC BY-NC = nicht-kommerziell**. Ein RC-Park ist kommerziell → du
brauchst eine **ausdrückliche Freigabe des Landesamts für Denkmalpflege** (oft für Bildungs-/
Tourismuszwecke erhältlich). Jeden Scan vor Nutzung auf die Lizenz prüfen. Sauberste Lösung
siehe „Eigener Scan" unten.

## Harte Wahrheit: Detail > Druckerauflösung
Ein Scan erfasst **mehr Detail, als ein Drucker physisch wiedergeben kann** — feine
Steintextur, dünne Fialen, schmale Spalten überleben das Slicen bei grober Auflösung nicht.
Das heißt:
- **Resin ist Pflicht** (8K–12K), FDM reicht fürs Feinste nicht.
- Selbst dann: **Bemalung** holt das Detail erst sichtbar heraus (Wash in die Fugen,
  Drybrush auf Kanten) — ein roher einfarbiger Druck zeigt die Textur kaum.
- Realistisch: Scan liefert die **Geometrie-Obergrenze**, Resin + Farbe realisieren sie.

## Scan → Druck Workflow
1. **Import** der dichten Scan-Mesh (OBJ/PLY) in Blender / Meshmixer / ZBrush.
2. **Cleanup**: Löcher füllen, losgelöste Fragmente entfernen, Boden kappen.
3. **Maßstab** real setzen (z. B. 1:200) und **aushöhlen** (Wandstärke ~1,5–2 mm) → spart
   Resin, vermeidet Saugnäpfe.
4. **Entlüftungslöcher** in Hohlraum (Resin muss ablaufen).
5. **In Module schneiden** (Flat-Wall / Bausatz) für Größe + Parallelität.
6. **Resin-Slicer**: orientieren (45°), Supports, drucken; waschen + UV-härten.
7. **Finish**: grundieren, Wash + Drybrush, optional **Fenster hinterleuchten**
   (siehe [`beleuchtung-detail.md`](beleuchtung-detail.md)).

## Die ultimative Option: eigenen Scan beauftragen
Löst Detail **und** Lizenz in einem:
- **Drohnen-Photogrammetrie** des realen Münsters (ein Dienstleister überfliegt/fotografiert,
  liefert hochauflösende Mesh) → **du besitzt das Modell**, keine Lizenzfrage, maximales Detail.
- Alternativ **terrestrischer Laserscan** (dotscene u. a. bieten mobile Gebäude-Laserscans).
- Kosten überschaubar gegen den Wow-Effekt eines maßstabsgetreuen, beleuchteten Scan-Münsters
  als Diorama-Zentrum.

## Qualitäts-Benchmark (handmodelliert, als Vergleich)
Falls kein Scan: **MiniWorld3D Notre-Dame de Paris** gilt als eines der detailliertesten
druckbaren Kathedralen-Modelle (Resin-tauglich, Benchmark für „so detailliert geht FDM/Resin"):
https://www.myminifactory.com/object/3d-print-notre-dame-de-paris-cathedral-91899
— zeigt, welches Detailniveau erreichbar ist; ein Freiburg-Pendant in dieser Güte gäbe es
nur über Scan oder Auftragsmodellierung.

## Fazit / Entscheidung
- **Max Detail, schnell verfügbar:** vorhandener LAD-BW-Scan → **aber Lizenz klären** (NC).
- **Max Detail, rechtssicher, dein Eigentum:** eigenen Drohnen-/Laserscan beauftragen.
- **Beides braucht:** Resin-Druck (8K+) + Bemalung, große Teile als Flat-Wall-Bausatz.

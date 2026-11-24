---
name: foto-vor-ort
description: Nutzer laedt aus der Stadt ein Foto hoch - sofort pruefen und kurz PASST / PASST NICHT antworten. Auch "welche Fotos brauchen wir noch" (Fotoauftrag).
---
1. Sofort: `bash tools/foto_check.sh <objekt> <datei> [auftrag-nr]` (braucht `modelle/<objekt>/audit/fotoauftrag.json`; sonst erst `tools/foto_auftrag.py`).
2. Antwort 2-4 Zeilen: "PASST fuer Auftrag N" oder "PASST NICHT" + genau EINE Anweisung (Standort/Richtung/Zoom). Bild `check_<name>.jpg` mit Zielrahmen per SendUserFile zurueck.
2b. Gibt es `modelle/<objekt>/audit/foto_auftrag.json` (Skizze der Kette), prueft foto_check.sh das Foto-GPS (+ Kompass) gegen die nummerierten Standpunkte: "ERFUELLT Standpunkt N" / "PASST NICHT ... bitte X m nach links" - diese Zeile woertlich weitergeben. Von Hand: `tools/py seg tools/foto_auftrag_skizze.py --pruefen <json> <foto...>`.
3. Fotobedarf zeigen: ZUERST die Skizze `modelle/<objekt>/audit/foto_auftrag_handy.png` (Hochformat fuers Handy, Luftbild, max. 8 Standpunkte mit GPS, Blick, "Handy ~N Grad nach oben", Hoehe im Bild; Pflicht-Eckfotos zuerst) bzw. `foto_auftrag.png` (+ Standpunktliste `foto_auftrag.md`, GPS je Standpunkt) schicken - entsteht in der Kette nach der SfM und am Laufende (`tools/foto_auftrag_skizze.py <objekt.json>`); danach bei Bedarf `tools/foto_auftrag.py` (Stadtplan, Standorte, Ziele); Wunschliste `modelle/<objekt>/fotowuensche.json`.
4. Kuenftig GPS im EXIF einschalten lassen (Anker fuer Seite/Massstab).

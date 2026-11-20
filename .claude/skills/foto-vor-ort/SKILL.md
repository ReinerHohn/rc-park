---
name: foto-vor-ort
description: Nutzer laedt aus der Stadt ein Foto hoch - sofort pruefen und kurz PASST / PASST NICHT antworten. Auch "welche Fotos brauchen wir noch" (Fotoauftrag).
---
1. Sofort: `bash tools/foto_check.sh <objekt> <datei> [auftrag-nr]` (braucht `modelle/<objekt>/audit/fotoauftrag.json`; sonst erst `tools/foto_auftrag.py`).
2. Antwort 2-4 Zeilen: "PASST fuer Auftrag N" oder "PASST NICHT" + genau EINE Anweisung (Standort/Richtung/Zoom). Bild `check_<name>.jpg` mit Zielrahmen per SendUserFile zurueck.
3. Fotobedarf zeigen: `tools/foto_auftrag.py` (Stadtplan, Standorte, Ziele); Wunschliste `modelle/<objekt>/fotowuensche.json`.
4. Kuenftig GPS im EXIF einschalten lassen (Anker fuer Seite/Massstab).

# Cloud-Rechnen (Runpod, vast.ai) – Unterast  ← [betrieb](../betrieb.md) ← [PROJEKT.md](../../../PROJEKT.md)
Anleitungen: [tools/cloud/CLOUD_RUNPOD.md](../../../tools/cloud/CLOUD_RUNPOD.md) (Befehlsliste, Kosten, Pod-Wahl) · [tools/cloud/CLOUD_VAST.md](../../../tools/cloud/CLOUD_VAST.md) (vast.ai, Upload-Messung)

## Gilt
- Runpod für Läufe, die lokal am RAM (15 GB) oder VRAM (8 GB) scheitern. Claude, Generator und Abnahme bleiben lokal; in die Cloud geht nur das Minimal-Paket (`tools/cloud/runpod_paket.py`).
- Jeder Cloud-Lauf: zuerst den Dry-Run und den Mini-Test LOKAL (`tools/cloud/runpod_dicht.sh --lokal`), dann den Mini-Test in der Cloud (≤ 15 min), dann den großen Lauf. Mieten nur nach Freigabe des Nutzers.
- Kostenbremse steckt im Skript: Selbststopp per `runpodctl pod stop $RUNPOD_POD_ID` nach einem Zeitlimit (Standard 3 h), bei einem Fehler und nach dem Download-Fenster. Ohne funktionierendes runpodctl rechnet nichts.
  Nach dem Download den Pod LÖSCHEN, denn ein gestopptes Volume kostet 0,20 $/GB/Monat.
- Pod-Wahl dichte Wolke: RTX 3090 (125 GB RAM), nicht die 4090 (Runpod gibt je 4090 nur 41 GB RAM, Preisliste 27.11.).

## Versucht
- 27.11. · Runpod-Lauf dichte Wolke Handy-Teilmodell (634 Bilder, volle Größe, Fusion am Stück) vorbereitet (Cloud, GPU mieten, PatchMatch, Fusion, RAM-Grenze) → ℹ vorbereitet, Cloud ungelaufen.
  Paket 972 MB (Sparse 159 MB + Rohbilder 909 MB; db.db 2,9 GB nicht nötig), Upload ≈ 7 min (ANNAHME 8,5 GB/h).
  Dry-Run lokal: 4,93 Mpx je Bild, Fusion braucht geschätzt 87 GB (27 MB/Mpx) und Platz ≈ 68 GB; lokal würde die Fusion auf 640 px verkleinert.
  Mini-Test lokal (20 Bilder Treppe/Anbau, volle Größe): rc 0, PatchMatch 177 s, Fusion-RAM 26,2 MB/Mpx, 21 164 Punkte.
  Gegenprobe 1600 px: 98 s, 18 956 Punkte. Volle Größe heißt 2× Tiefenpixel, aber nur +12 % Fusionspunkte im Mini; im Mini sind die Karten nur zu 5–35 % gefüllt (20 Nachbarn).
  Kostenbremse mit Ersatz-runpodctl geprüft (rc 7 ohne Bremse, Zeitlimit → Stopp). Lehre: In Containern zeigt /proc/meminfo den Host, deshalb liest das Skript die cgroup-Grenze. [tools/cloud/runpod_dicht.py]
- 20.11. · vast.ai vorbereitet (vast.sh, Zeitgeber auf dem Laptop) → ℹ NICHT erprobt · 4090 + 64 GB ab 0,42 $/h · [tools/cloud/CLOUD_VAST.md]

## Offen
- Cloud-Mini-Test und großer Lauf: rc, Zeit je Phase, RAM-Spitze Fusion je Mpx, echter $/h, Abrechnung. Bestätigen, dass der pod-eigene `RUNPOD_API_KEY` den Selbststopp darf (ANNAHME laut Doku „Pod-scoped").
- Rahmen: Das Paket nutzt `teilmodell/0_ausgerichtet` (wie die lokale Wolke). Die neue Einpassung (`handy_teil_spuren/teil_sfm`, BRUECKE-LAGE 27.11.) liegt in einem anderen Rahmen: entweder ein neues Paket oder die Wolke hinterher per Sim3 umrechnen.
- Danach lokal `tools/wolke_vereinigen.py` und eine Zählung je Zelle an Treppe/Anbau/Steg gegen `handy_teil_dicht` (kachel/vereint).

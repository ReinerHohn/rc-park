# 📷 Fotos → SfM → H0-Modell (GPU-PC, ab Nov. 2026)  ← [PROJEKT.md](../../PROJEKT.md)
Details: `modelle/INDEX.md` (Dokumentbaum) · `modelle/ZIEL_PIPELINE_H0.md` (Stand) · `modelle/NICHTS_GEBRACHT.md` (alle Sackgassen, Inhalt: `modelle/inhalt/`) · Skills `.claude/skills/`

## Gilt
- **Kernmethode (Nutzer 15.11.):** Form = Fotokanten + Triangulation mit SfM-Kameras; dichte Wolke/LoD2/DOM1 nur Lage-Veto, Höhe, Gegenprobe.
- **Wandbild = Bauplan (17.11.):** jede Wand aus vielen Fotos entzerrt (1-cm-Raster) + Tiefe je Zelle → Gestalt nachbilden; kein Musterteil.
- Neue Objekte: Fotos → SfM → LoD2 nur Abgleich (entschieden 20.11., Nutzer „neuer ist besser"; ersetzt „LOD2 = Massing" aus Okt.).
- Feindetail = echte Löcher/Relief aus dem Wandbild, aber druckbar (Mindestmaß 0,8 mm, keine Mikroteile wie 31.560 Sprossen) — entschieden 20.11.
- Ungesehene Seite nie spiegeln/erfinden → Fotos suchen. Zählen nur am Foto. Verwerfen nur mit benannter Ursache.
- Globaler Mapper nur als Konsens zweier Läufe; jedes globale Modell erst zerlegen (`tools/modell_zerlegen.py`), dann bewerten.
- Lizenzen müssen Verkauf erlauben (`modelle/LIZENZ_WERKZEUGE.md`); Git: > 1 MB nie ohne LFS, Zugangsdaten nur `~/.config/rcpark/`.

## Versucht
**Kameras & Mapper**
- 20.11. · globaler Mapper „Modell 0" als ein Stück bewertet → ⚠ Falle · enthält punktlos getrennte Gruppen, Lage zueinander beliebig → `modell_zerlegen` [Logbuch Kettentest]
- 20.11. · Konsens-Stufe 2 mit allen Bildern → ✗ zwang 21 Süd-Bilder ins Nordmodell · Seitenfilter `fremde_seite` [45d76d5c]
- 20.11. · FlexGlue statt SIFT-Zuordnung → ✓ +30 % Nord / +40 % Süd Bilder Martinstor, Schwabentor +6 %, Lage gleich · zuschaltbar `RCPARK_FLEXGLUE=1` [dc0b84b9]
- 20.11. · FlexGlue-„Türsteher" trennt Seiten → ✗ Fehlmeldung · fairer SIFT-Lauf trennt genauso [Logbuch Kettentest]
- 20.11. · Schwerkraft-Vorgabe je Bild im Mapper → ✗ 12–14 Bilder weniger, kein Genauigkeitsgewinn
- 20.11. · DINOv2-Bildsuche als Paarvorfilter → ✗ nur 9 % der neuen FlexGlue-Paare in top-150
- 20.11. · Einzellauf globaler Mapper → ⚠ je Methode ein deformierter Wiederholungslauf · immer Konsens zweier Läufe
- 13.11. · Mehrthread-Mapper → ⚠ nicht reproduzierbar (181/149/181/21 Bilder) · ein Thread

**Dichte Wolke & Seiten**
- 20.11. · Seiten vereinen aus globalen Stücken (Klappung) → ✗ nur 50–53 tragende Punktpaare, Achse 14–20 % uneinig · Rückfall: jede Seite an LoD2
- 20.11. · PatchMatch-Korrektur PR 5041 → ✗ kein messbarer Unterschied
- 20.11. · Depth Anything 3 als Fülltiefe → ✗ kein klarer Gewinn gegen Ebenenfüllung
- 20.11. · LoMa-Zuordnung → ✗ Gewichte nicht kommerziell nutzbar

**Betrieb**
- 20.11. · COLMAP-Bau mit fremdem ONNX-Ordner → ⚠ CMake löscht dessen `lib/cmake` · Vorrat je Bau kopieren
- 20.11. · ungepushte Arbeit auf dem GPU-PC (1159 Commits, 8,2 GB Binärdateien) → ✗ Katastrophe · Push je Arbeitsblock, Git-Sperre 1 MB/Geheimnisse

## Offen
- Seiten (Nord/Süd) symmetrischer Tore automatisch vereinen (Stand 20.11.)
- FlexGlue als Standard? (Nutzerentscheid, +2,5 h Laufzeit)
- Große Binärdateien schon auf GitHub (23 Pfade, 160 MB) entfernen? braucht Force-Push (Nutzer)

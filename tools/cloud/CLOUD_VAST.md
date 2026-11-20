# Rechnen auf vast.ai (Stand 20.11.2026, vorbereitet, noch NICHT erprobt)

Werkzeug: `tools/cloud/vast.sh` (lokal), `tools/cloud/einrichten_remote.sh` (läuft auf der Mietmaschine), Umgebungen als
`tools/cloud/anforderungen_{seg,colmap,gen}.txt` (pip freeze der Laptop-venvs vom 20.11.). CLI: `~/.venvs/vast/bin/vastai`.

## Warum
Laptop: RTX 4060 mit 8 GB VRAM, 15 GB RAM, 28 Threads. Die Auswertung von 43 Sitzungen ergab 234 „Killed" (RAM) und
103 CUDA-OOM (VRAM). Eine Mietmaschine mit RTX 4090 (24 GB) und 64–110 GB RAM beseitigt genau diese Engpässe.
Die Jobs, die Stunden dauern (dichte Wolke, FlexGlue-Abgleich, Mapper), laufen dort; Claude, Generator und Abnahme bleiben lokal.

## Preise (live über die vast.ai-API abgefragt, 20.11.2026, 1 GPU, ≥ 64 GB RAM, ≥ 16 Kerne, CUDA ≥ 13.2, Zuverlässigkeit > 0,98)
- RTX 3090 (24 GB): 11 Angebote, ab 0,26 $/h, Median 0,40 $/h
- RTX 4090 (24 GB): 35 Angebote, ab 0,42 $/h, Median 0,66 $/h  ← Empfehlung (Ada wie der Laptop, gleiche CUDA-Arch-Familie)
- RTX 5090 (32 GB): 32 Angebote, ab 0,48 $/h, Median 0,85 $/h
- Speicher: Median 0,23–0,33 $ je GB und Monat, berechnet solange die Instanz existiert (auch gestoppt).
- Netz: 4–12 $ je TB; unsere Fotos (Martinstor 277 MB) und Ergebnisse (wenige GB) kosten Cent-Beträge.
Marktpreise schwanken stündlich; `vast.sh suchen` zeigt den aktuellen Stand.

## Kosten-Beispiele (ANNAHME: 4090 ≈ 0,50 $/h; Laufzeit auf der 4090 ≈ halb so lang wie lokal, ungemessen)
- Einmal einrichten (venvs + COLMAP-Bau): ca. 45 min ≈ 0,40 $.
- Ein Martinstor-Kettenlauf (lokal 3–5 h): ca. 1,5–3 h ≈ 1–1,50 $.
- Nachtbetrieb 10 h je Nacht, 30 Nächte: 300 h ≈ 150 $/Monat, dazu Speicher 150 GB ≈ 1,30 $/Tag, wenn die Instanz tagsüber nur gestoppt ist.
- Rund um die Uhr: 720 h ≈ 360 $/Monat (+ ca. 40 $ Speicher).
Lokale Auslastung zum Vergleich (Journal, nur über job_start.sh gestartete Jobs): 17.–19.11. je 6–10 Jobstunden am Tag.

## Datenmengen und Upload (gemessen 20.11.2026)
- Upload zu Hause: 18–20 Mbit/s (≈ 8,5 GB/h; Cloudflare-Messung, 2 × 50 MB). Download nicht messbar (Messdienst lehnte ab, 403).
- Hoch je Objekt: Code (git ls-files) 0,6 GB + Fotos (Martinstor 1,1 GB) ≈ 12 min; mit Videobildern (+4,3 GB) ≈ 40 min.
- Nicht hochladen: Python-Pakete (~13 GB), COLMAP, KI-Modelle (3 GB) – lädt die Mietmaschine selbst.
- Zurück nur Ergebnisse: fused.ply (34 MB), sparse + kameras.json (~0,3 GB), optional db.db (2,5 GB). Tiefenkarten (7 GB) und
  Konsens-Zwischenstände (8 GB) bleiben dort.
- Plan, damit nichts wiederholt hochgeht: Umgebung als Docker-Image (einmal bauen), Fotos einmal in billigen Objektspeicher
  (z. B. Backblaze B2, ANNAHME ~6–7 $/TB/Monat), kein dauerhafter vast-Speicher (hängt an einem Vermieter-Rechner).

## Ablauf
1. Einmalig: Konto auf cloud.vast.ai, Guthaben aufladen (Vorkasse, kein Abo), API-Schlüssel erzeugen,
   `~/.venvs/vast/bin/vastai set api-key <SCHLÜSSEL>`, `vastai create ssh-key "$(cat ~/.ssh/id_ed25519.pub)"`, dann `vast.sh pruefen`.
2. `vast.sh suchen` (oder `vast.sh suchen "RTX 3090" 64`) → Angebots-ID wählen → `vast.sh mieten <ID>` (fragt nach).
3. `vastai show instances` bis „running" → `vast.sh einrichten <INST>` (Repo ohne .git/Daten hoch, Umgebungen bauen, Schnelltest).
4. Daten hoch: `vast.sh hoch <INST> /media/oem/rcdaten/.../martinstor/lokal/fotos` (landet am selben absoluten Pfad, Symlinks aufgelöst).
5. Job: `vast.sh job <INST> mt1120 "taskset -c 0-15 /media/oem/scan/venv-seg/bin/python -u -I tools/gesamtkette.py ..."`, `vast.sh log <INST> mt1120`.
6. Ergebnis zurück: `vast.sh holen <INST> /media/oem/scan/rc-park_daten/martinstor-1120`, lokal Tore/Abnahme wie immer.
7. `vast.sh kosten`, danach `vast.sh ende <INST>`. Nie Instanzen vergessen: sie kosten weiter.

## Grenzen und offene Punkte
- Ungeprüft: Bild-Tag `nvidia/cuda:13.0.1-cudnn-devel-ubuntu24.04` (sonst `VAST_IMAGE=...`), COLMAP-Bau aus ce2b5ab mit Ubuntu-Ceres,
  Schnelltest auf der Mietmaschine. Erster Lauf = Probelauf mit kleinem Objekt (Dummy-Test laut Skill langer-job).
- Ceres dort ohne CUDA/cuDSS → GPU-Bündelausgleich fehlt (gemessen nur 13,6 s gegen 17,1 s, also unerheblich).
- Die GPU-/RAM-Buchung von job_start.sh gilt dort nicht; `vast.sh job` startet direkt. Auf 24 GB passen mehrere Jobs parallel,
  dafür JOB_GPU_LIMIT_MB=22000 setzen, falls job_start.sh dort genutzt wird.
- Die Fotos liegen beim Vermieter (Privatrechner weltweit, „verified" heißt nur geprüft). Fotos öffentlicher Gebäude sind unkritisch,
  keine Zugangsdaten mit hochladen (das Repo geht ohne .git hoch; `.env`/Schlüssel vorher prüfen).
- Wiederholtes Einrichten vermeiden: entweder Instanz stoppen statt zerstören (Speicher ≈ 1–1,50 $/Tag) oder später ein
  eigenes Docker-Bild bauen (braucht Docker-Hub-Konto).

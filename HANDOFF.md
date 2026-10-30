# HANDOFF — Kontext für die GPU-PC-Instanz

> Dieses Dokument ersetzt das lokale Claude-Gedächtnis (das bleibt auf dem Laptop).
> Branch **`pipeline-tools`** (sauber, ohne Riesendateien). `git pull` holt alles.

## Projekt
**Mini-Freiburg**: 3D-druckbare Wahrzeichen-Modelle von Freiburg/Schwarzwald für ein
Miniatur-Wunderland-ähnliches Geschäftsmodell. Repo `rc-park`. User = MD.

## Methode (der „Hofgut-Weg" = bestes Rezept)
Nicht Vollautomatik (gibt Klötze), sondern **Craft mit Daten + Mensch im Loop** (~1 Tag/Hero-Gebäude):
1. **Quellen-Inventur** (`quellen_inventar.py` → `QUELLEN.md`): alle 16 Datenquellen durchgehen, nichts raten.
2. **Merge jede Quelle für ihre Stärke**: LOD2=Massing · Laser nDOM (DOM1−DGM1)=Dachform · DOP=Dachstruktur/Kamine · Fotos=Fassade/Fenster.
3. **Schrittweise** mit 3D-HTML nach jedem Schritt (`stl_html_viewer.py`/`glb_html_viewer.py`).
4. **Harter Validator** gegen Laser-Grundwahrheit (Form/IoU, nicht Farbe).
HARTE REGEL: nichts hardcoden, jedes Detail aus Foto/Daten messen; bei Fehler Detektor fixen, nicht Wert raten.

## Fertige Modelle
- **Historisches Kaufhaus Freiburg** — Detailmodell `modelle/kaufhaus_freiburg/kaufhaus_measured.glb` (47 Teile: Arkade/Erker/Statuen/Helm/Dachziegel). Bestes Detailniveau.
- **Hofgut Sternen** (Ravennaschlucht) — `modelle/hofgut_sternen/hofgut_sternen.glb`. Hybrid LOD2+Laser+DOP+Foto. Reproduzierbar via `python3 tools/hofgut_sternen.py`.
- **Ravenna-Viadukt** — `modelle/ravenna/ravenna_viadukt_final.stl`. Generator `ravenna_viadukt.py`. SELBER ORT wie Hofgut → gehören in eine Höllental-Szene.
- **Martinstor** v2 — `modelle/martinstor_gen/martinstor_measured.glb` (NEU, Stadttor-Typ: Zinnen+4 Eck-Türmchen+Helm+Uhr+Wappen+Rustika, 45.9m=LOD2). `martinstor_3d.html` zum Anschauen.
- Kornhaus, Hotel Oberkirch — fertig (`bauwerke/*.json`).

## Neue Tools dieser Session (auf pipeline-tools)
- `foto_zu_config.py` — halbautomatischer Vermesser: Foto-Ordner+LOD2 → `bauwerke/<name>.json` + TODO-Report.
- `stadttor_generator.py` — Typ-Generator Torturm (Martinstor/Schwabentor). Schwabentor = nur neue Config.
- `commons_harvest.py` — Wikimedia-Commons-Ernte, **`--search` (Volltext, robustester Weg)**, Lizenz/Autor je Bild.
- `video_frames.py` — Fotos aus Videos (yt-dlp+ffmpeg+Schärfefilter) für Photogrammetrie.
- `mapillary_rip.py` — Fassadenfotos Google-frei (Mapillary, Token in `~/.config/mapillary_token`).
- `opensfm_run.py` — Photogrammetrie-Wrapper (OpenSfM, braucht Docker `mapillary/opensfm`).
- `foto_displacement.py` — Tiefe→Druck-Relief (Depth-Anything/Marigold + Detrend).
- `auto_bauwerk.py` — Orchestrator; `openbuildings_fallback.py` — LoD1-Fallback.

## DEINE MISSION (GPU-PC)
Den **Mittelweg zu fotoreal** fahren, den der Laptop (nur AMD-iGPU, kein CUDA) nicht konnte:
1. `nvidia-smi` prüfen → Stack wählen: VRAM≥16GB → **TRELLIS/Hunyuan3D** (generativ Bild→3D), ~6-8GB → TripoSR.
2. **Martinstor fotoreal**: Frontal `daten/martinstor/fotos/commons/008_*7999.jpg` durch Bild→3D ODER die 22 CC-Fotos (`daten/martinstor/fotos/commons/`, manifest mit Lizenzen) + `video_frames.py` durch **Photogrammetrie** (OpenSfM/COLMAP).
3. Ergebnis auf **LOD2 ausrichten/skalieren** (`modelle/martinstor/martinstor_turm.json`, 45.3m) + druckbar machen (`drone_to_print.py`).
RECHTLICH: Commons-Fotos sind CC/PD (Attribution wahren, siehe manifest). YouTube-Frames = Uploader-Copyright, fürs Produkt nur mit Rechten.

## Ehrliche Grenzen (gelernt)
- Vollautomatik aus Koordinaten = Klotz. Qualität braucht gutes Frontalfoto + Mensch-Loop.
- Crowd-Fotos (Mapillary) = nur Massing; **Commons-Volltextsuche** liefert die guten Frontals.
- Monokulare ML-Tiefe = Szenentiefe, nicht Fassaden-Mikrorelief (erst rektifizieren).
- Gotisches Maßwerk (Münster) = Photogrammetrie schwer → eher Lasercut-Maßwerk-Platten.

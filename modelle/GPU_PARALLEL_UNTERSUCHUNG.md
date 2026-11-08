# GPU-Parallelbetrieb: Untersuchung (Zwischenstand 2026-11-06, wird laufend ergaenzt)

## Vorbefund aus Kernel-Log (journalctl -k, Boot 0 seit 2026-11-01)
- NVRM "Out of memory [NV_ERR_NO_MEMORY] ... _kgmmuClientShadowFaultBufferPagesAllocate": 8 Gruppen mit Fault-Buffer-Zeile
  (02.11. 17:19, 22:15; 03.11. 18:51, 20:21; 05.11. 20:35:44, 20:36:00, 20:36:23, 20:36:44, 20:37:12, 20:37:23, 22:31:39, 22:32:53) plus 3 ohne
  Fault-Buffer-Zeile (02.11. 16:52, 03.11. 16:41, 05.11. 20:26:26). Kein Xid, kein "illegal memory access" im Kernel-Log.
- Der Fehler steht bei isSystemMemory-Zweig (Alloc NV01_MEMORY_SYSTEM): der Fault-Buffer wird im HOST-Speicher angelegt -> NO_MEMORY kann
  Hostspeicher/Fragmentierung meinen, nicht VRAM. 05.11. 20:26:26 faellt mit einem globalen OOM-Kill (Host-RAM) zusammen.
- 05.11. 20:35:26-20:37:23: parallel liefen rcpark-ws_kh_ho und rcpark-ws_fd_voll (fotodiff, Torch); Fehler alle ~20 s = Prozess-/Kontextstarts.
- Torch-VRAM-OOM (User-Space, "CUDA out of memory") ist davon getrennt: beweis_rps_r1.log (04.11. 22:36, Fremdprozess 510 MiB) und
  beweis_rast_ps.log, kaufhaus_handy_masken/job.log - dabei KEINE NVRM-Zeile im Kernel-Log.
- Nicht rekonstruierbar: GPU-Speicher je Prozess zu den Zeitpunkten (kein nvidia-smi-Log), Host-RAM ausser 20:12/20:26 (OOM-Tabelle im dmesg).

## Zwischenstand 14:56 (Lock `gpu_par_test` gehalten, Zeitbox bis 15:06)
Testaufbau: Skripte in /tmp/claude-29999/-home-oem-git-rc-park/57b6d967-3617-4d4e-a161-9a78fa34e188/scratchpad/{run.sh,sift.py,torchload.py}; Ergebnisse je Lauf in .../scratchpad/out/<tag>/
(smi.log = Zeitreihe 0,5 s: VRAM, Auslastung, freier Host-RAM, freier Swap, Prozess-VRAM; kern.log = neue NVRM/Xid-Zeilen; sift.log; torch.log).
SIFT = pycolmap 4.2.1 extract_features (Device.cuda), 50 Martinstor-Fotos, 8 Wiederholungen je Lauf, je Lauf neuer Prozess/Kontext.
Torch = fp16-Matmul 4096^2 Dauerlast (mittlere Auslastung 86 %, max 100 %), Variante a mit 5,5/6,5 GB Ballast (ungebremst).

| Lauf | Ergebnis |
|---|---|
| SIFT allein (3x + 8er-Lauf) | 3,8-4,6 s je 50 Bilder (~6,6 s/Lauf im 8er-Lauf), VRAM-Spitze 4473 MiB (!), GPU-Auslastung im Mittel 1,2 % (SIFT ist fast ganz CPU/IO-gebunden), 491956-492040 Keypoints |
| Torch allein a / b / c | 202 / 204 / 20 Matmul/s (c wegen empty_cache+Neuallokation je Schritt 10x langsamer), kein Kernel-Ereignis |
| Torch a (5,5 GB) + SIFT parallel, 4 Laeufe | KEIN Kernel-Ereignis, KEIN Prozessabsturz, SIFT rc=0, Torch-Rate unveraendert (202/s). ABER: SiftGPU meldet 500-1000+ Zeilen `CuTexImage::InitTexture2D / FilterH / FilterV: out of memory` und liefert **0 Keypoints** fuer alle 50 Bilder, Rueckgabecode 0 (stiller Ausfall). Allein: 492k Keypoints. Gesamt-VRAM-Spitze 7804 von 8188 MiB. |
| Host-RAM/Swap | in allen Laeufen RAM verfuegbar 7,2-7,8 GB, Swap frei 12,8 GB - kein Hostspeicher-Druck |

Befund bisher: Die VRAM-Ueberbelegung ist reproduziert, aber als STILLER Ausfall in SiftGPU (0 Features, rc 0), nicht als Kernel-NVRM-Ereignis und nicht als 'illegal memory access'.
Das erklaert das dokumentierte Symptom (Register BA: danach >=80 %-Regel/CPU-Rueckfall). Die NVRM-Kernel-Ereignisse sind NICHT reproduziert (Host-Fault-Buffer, vermutlich Hostspeicher/Fragmentierung bei Kontextstart, siehe Vorbefund) - offen.
Noch ausstehend: Torch Variante b (fraction 0,35) und c parallel; 3-4 gleichzeitige Prozesse (mehrere Torch + SIFT, PatchMatch, OWLv2/foto_diff-GPU); Durchsatzgewinn; Grenze ab der der Kernel kippt. Zeitschaetzung bis Befund: ~10 min.

## Endbefund 15:12 (Lock freigegeben, alle Testprozesse beendet)
Weitere Laeufe (Rohdaten: .../scratchpad/out/<tag>/{smi.log,kern.log,sift.log,torch.log,sift.summ}):
| Lauf | Ergebnis |
|---|---|
| Torch b (Fraction 0,35 + expandable_segments) + SIFT | stabil, 2x 50 Bilder je 492k Keypoints; ABER Torch reserviert real nur 120 MiB (Matmul 4096^2) - der Test belastet die Grenze nicht. Torch-Rate 183/s (-10 %). |
| Torch c (empty_cache + Neuallokation) + SIFT | **Torch-OOM** ("CUDA out of memory ... Process 2413387 has 7.13 GiB"): SIFT-GPU belegte 7,13 GiB und Torch bekam nichts. Lehre: SiftGPU nimmt solo bis 7,4 GB (Lauf mis3200; frueher 4,4 GB gemessen) - es ist der gierige Teil, nicht Torch. |
| SIFT max_image_size 3200 / 1600 / 1024 solo | VRAM-Spitze 7397 / 2121 / 921 MiB; Keypoints bei 1600 ~465-473k (-4 %) |
| Torch a 5,5 GB + SIFT(1600) | **KRACH REPRODUZIERT**: Kernel `NVRM: Xid 31 MMU Fault ENGINE GRAPHICS` (=GPU 'illegal memory access', pid = SIFT-Prozess) 3x im ersten, 11 Zeilen im zweiten Lauf, danach `pmaAllocatePages / ctxBufPoolReserve: Failed to reserve memory ... Out of memory [NV_ERR_NO_MEMORY]` (Kontextpuffer nicht reservierbar). SIFT lieferte 0-10 von 50 Bildern, rc 0. Torch-Rate 144-182/s. Gesamt-VRAM 7802 von 8188 MiB; Host-RAM frei >= 4,1 GB, Swap 12,8 GB frei. |
| Torch a 5,5 GB + SIFT(3200) (4 Laeufe) | kein Kernel-Ereignis, aber SiftGPU `CuTexImage ... out of memory` (500-26000 Zeilen), 0 Keypoints, rc 0 (stiller Ausfall) |
| **Torch a 4,0 GB + SIFT(1600), 3 Laeufe** | **stabil**: 0 Kernel-Ereignisse, 0 SIFT-OOM, je 50 Bilder 474.3k Keypoints, VRAM-Spitze 6444-6705 MiB, GPU-Auslastung im Mittel 99 % |

**Befund: Hypothese bestaetigt (Speicherueberbelegung), Gegenhypothese (UVM-Fehler bei viel freiem Speicher) nicht gestuetzt.** Der Crash (Xid 31 + NVRM NO_MEMORY in ctxBufPoolReserve) tritt genau dann auf, wenn die Summe der VRAM-Reservierungen
~7,8 GB erreicht (Torch-Ballast 5,5 GB + SIFT); bei 6,4-6,7 GB Gesamtbelegung nie. Ursache ist die Kombination: Torch-Caching-Allocator haelt Reserve (peak_reserved bleibt), SiftGPU alloziert ungebremst
alles Freie (bis 7,1-7,4 GB, haengt von max_image_size ab) und kann bei Mangel nicht sauber scheitern (rc 0, 0 Features oder MMU-Fault). Die 'Fault-Buffer'-NVRM-Zeilen vom 02.-05.11.
(Host-seitig, vermutlich Kontextstart bei Speichermangel) sind in diesem Test nicht einzeln reproduziert; nur die ctxBufPoolReserve-Variante. Host-RAM war kein Faktor in diesen Tests.
Durchsatz: SIFT-Laufzeit parallel 12,6 s/Lauf gegen 13,4 s solo (gleiche CPU-Last durch laufenden video_sweep) = kein Verlust; Torch (Dauerlast) 148-186/s gegen 202/s solo = 82-92 % (Mittel 85 %).
Bei gleich grossen Arbeitsanteilen ergibt das rund +70 bis +80 % Gesamtdurchsatz gegen seriell (Schaetzung, nicht an realen Pipeline-Jobs gemessen). SIFT selbst belastet die GPU nur ~1 % (CPU/IO-gebunden) - es verdraengt nur Speicher.

### Regelvorschlag (nicht in tools/ eingebaut)
1. VRAM-Budget je GPU-Job, Summe <= 6,5 GiB (8 GiB minus Desktop ~0,6 GiB minus Kontextpuffer/Reserve ~1 GiB). Vorschlag: SIFT/COLMAP <= 2,2 GiB (`extraction_options.max_image_size=1600`, Spitze 2121 MiB gemessen; ohne Kappung bis 7,4 GB!), Torch-Job <= 4 GiB.
2. Torch-Jobs: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` und `torch.cuda.set_per_process_memory_fraction(0.45-0.5)` (setzt echtes OOM im Torch-Prozess statt Kernel-Fault beim Nachbarn); `empty_cache()` nur zwischen Stapeln (Variante c kostet hier 10x Rate).
3. Vor dem Start eines zweiten Jobs `nvidia-smi --query-gpu=memory.used`: Start nur wenn used + Budget des neuen Jobs <= 7,0 GiB (statt 'GPU belegt' als Sperre in tools/job_start.sh: Pruefung (b) ersetzen). Lock-Datei bleibt fuer Jobs OHNE Budget (Default: exklusiv).
4. Tool-Diff-Skizze: `tools/zusatzfotos_registrieren.py` Z.111 `pycolmap.extract_features(db, ..., image_names=nn, camera_mode=..., reader_options=ro)` -> `extraction_options=FeatureExtractionOptions(max_image_size=1600)` (gleiches in sfm_netz.py/video_sfm.py/dicht_handy-SIFT);
   Torch-Tools (lg_match, zusatzfotos_lightglue, foto_diff-GPU, handy_masken_v2, dicht_handy): Kopf `os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF","expandable_segments:True"); torch.cuda.set_per_process_memory_fraction(float(os.environ.get("GPU_FRAKTION","0.5")))`;
   `tools/gpu_werkzeuge.txt` um Spalte Budget in MiB erweitern, job_start.sh summiert `nvidia-smi memory.used` + Budget. Zusaetzlich: Ergebnis-Gate nach extract_features (Keypoints > 0 je Bild), weil SiftGPU bei Speichermangel rc 0 mit 0 Features liefert.
5. Genuegt nicht: nur 'expandable_segments' (Variante b-Beobachtung beweist nichts, da Torch dort fast nichts belegte). Bewiesen ist nur: Summe <= ~6,7 GB stabil, ~7,8 GB kippt.

### Offen (nicht gemessen)
- 3-4 gleichzeitige GPU-Prozesse und echte Pipeline-Jobs (PatchMatch patch_match_stereo, LightGlue, OWLv2/Masken, foto_diff-GPU): Speicherbedarf je Job unbekannt; erst einzeln mit dem Sampler (smi.log) messen, dann Budget eintragen. PatchMatch/COLMAP-Dense ist in der Regel selbst gierig -> wie SIFT begrenzen.
- Untere Grenze genau (zwischen 6,7 und 7,8 GB), Einfluss CPU-Auslastung (video_sweep lief die ganze Zeit mit, Rate Torch-Schwankung 148-186 teils dadurch).
- MPS nicht geprueft (Laptop-GPU, ohne sudo wenig sinnvoll; Crash ist Speicherthema, nicht Kontextwechsel). NVreg/uvm-Parameter nicht angefasst.
- Fault-Buffer-Variante (02.-05.11.) nicht einzeln nachgestellt.

## Budgets je Werkzeug (2026-11-06 15:2x, Messung mit `tools/gpu_messen.py`, Ergebnis `tools/gpu_budget.txt`)
Verfahren: nvidia-smi alle 0,5 s (`memory.used` + `--query-compute-apps=pid,used_memory`); gezaehlt werden nur Compute-Prozesse, die beim Start NICHT schon auf der GPU waren (Fremdlast rcpark-video_dicht ~0,6-0,9 GB zaehlt nicht);
>= 2 Laeufe je Werkzeug; Budget = Maximum + 20 %. Gesamtbelegung blieb <= 7000 MiB (Ausnahme siehe silhouette). Rohlogs (CSV: t, gesamt_mib, neu_mib, pid:mib):
`/tmp/claude-29999/-home-oem-git-rc-park/57b6d967-3617-4d4e-a161-9a78fa34e188/scratchpad/bud/*.csv` (lg_*, sift_*, hypso_*, fdiff_*, tfd_*, silh_1, fenster_*, par_*), Fremdlast-Zeitreihe `fremd_video_dicht.log` (ebenda).

| Werkzeug | Spitze Prozess (MiB) | Budget (MiB) | Status / Bedingung |
|---|---|---|---|
| lg_match.py (4 Bilder, ALIKED+LightGlue) | resize 2048: 5176 / 1600: 3240 / 1024: 1458 (je 2 Laeufe, identisch) | 3900 | gemessen; gilt NUR mit `--resize 1600` (Standard 2048 = 6200 noetig); sfm_netz.py ruft es mit `--lg-resize` Standard 2048 -> dort 1600 setzen |
| SIFT (pycolmap extract_features, 50 Fotos) | max_image_size 1600: 2092 / 1024: 897 (2 Laeufe); 3200 frueher 7397 | 2510 | gemessen mit Aequivalent-Skript (sift.py im Scratchpad), nicht mit dem Werkzeug; eingetragen fuer zusatzfotos_registrieren.py (hat `RCPARK_SIFT_MAX`). sfm_netz.py kappt NICHT -> exklusiv |
| foto_diff.py (Martinstor 030) | 1102 (2 Laeufe) | 1330 | gemessen, 8,2-8,7 s |
| test_foto_diff.py | 1416 / 2534 (startet 2 foto_diff parallel) | 3050 | gemessen (Test selbst meldet NICHT BESTANDEN - bestehender Befund, fuer die Messung irrelevant; Ausgaben in Scratchpad) |
| hypso_gpu.py | 1684 (2 Laeufe) | 2050 | nur `--selbsttest`; Echtlauf nicht gemessen |
| dicht_handy.py / PatchMatch | 856 | 1030 | nur BEOBACHTET am laufenden video_dicht (max-size 1600), kein eigener Lauf |
| foto_silhouette_gpu.py | 6760 (1 Lauf, Gesamt 7138) | - | EXKLUSIV: Caching-Allocator greift alles; zweiter Lauf abgebrochen (Grenze 7000 waere ueberschritten); mit set_per_process_memory_fraction begrenzbar, nicht getestet |
| foto_profil_gpu.py | nicht gemessen | - | exklusiv (gleicher Kern wie silhouette) |
| fenster_ml.py | 0 | - | laeuft in venv-seg auf CPU (kein cuda im Skript) -> kein GPU-Werkzeug |
| render_kern.py | - | - | Bibliothek, Bedarf steckt in foto_diff/test_foto_diff |
| sfm_netz.py, sfm_dicht.py, video_sfm.py, video_match_gpu.py (braucht match_dump.npz), nullstart.py u. Orchestratoren, param_suche, generator_optimierer, zier_*, kanten_*, handy_masken*, dicht_handy_cache u. a. | nicht gemessen | - | kein sicherer Kurzlauf ohne Eingabedaten/Fremdschreiben; bleiben exklusiv bis gemessen |

`tools/job_start.sh`: ohne `JOB_GPU_MB` wird das Budget aus `tools/gpu_budget.txt` gelesen (awk `$1==<Treffer aus gpu_werkzeuge.txt>`); kein Eintrag = exklusiv. `bash -n` ok. Getestet (Kopie mit anderem Lock, Fake-nvidia-smi): Wartepfad "VRAM-Budget: belegt 6500 + Job 3900 > 7000" (lg_match), Exklusivpfad ohne Eintrag (sfm_netz -> "GPU belegt durch fremden Prozess"), Startpfad bei freier Karte (hypso_gpu startete, keine Lock-Datei geschrieben), `JOB_GPU_MB` ueberschreibt die Tabelle.
Achtung: laeuft ein EXKLUSIV-Job mit Sperrdatei (jetzt video_dicht), warten auch Budget-Jobs ueber job_start.sh ("GPU belegt durch video_dicht") - die Parallelitaet zu video_dicht wurde daher mit gpu_messen.py direkt, nicht ueber job_start.sh geprueft. Soll parallel zu video_dicht gehen, muss dessen Start ein Budget tragen (JOB_GPU_MB=1030).

### Stichprobe gleichzeitiger Betrieb (parallel zu video_dicht)
lg_match (resize 1024, 1458) + SIFT 1600 (2092) + foto_diff (1102) gleichzeitig, 2 Wiederholungen, plus video_dicht (~0,7-0,86 GB): Gesamt-VRAM-Spitze 4446 / 4323 MiB von 8188 (Tabelle haette 1750+2510+1330+740 = 6330 erlaubt).
Ergebnis: kein Absturz, alle rc 0, SIFT 474.3k Keypoints (wie solo), `journalctl -k | grep nvrm/xid` ohne neue Zeile (letzte NVRM-Zeilen 15:07 stammen aus den frueheren Tests).
Durchsatz: SIFT 14,0-14,4 s (solo 13,0-15,1), foto_diff 7,9-8,5 s (solo 8,2-8,7), lg_match 8,8-11,5 s (solo 14,9-15,9, durch Cache/Anlaufschwankung kein Beleg fuer Beschleunigung) -> kein messbarer Verlust der Testjobs.
Fremdlast: video_dicht-Iteration (dicht.log) im Testfenster 2,6-3,45 s, Mittel der 9 Iterationen im Fenster 3,1 s gegen 2,68 s davor = ca. +16 % langsamer (CPU-Konkurrenz durch SIFT mit; GPU-Auslastung war ohnehin 100 %). Rohdaten: par_1.csv, par_2.csv.
Nicht untersucht: laengere Laeufe (>15 s), 4+ Prozesse, Echt-Pipelinejobs.

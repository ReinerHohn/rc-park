# Rechner einrichten (gilt fuer jeden Rechner, auf dem die Pipeline laeuft)

Beim ersten Start einer Sitzung auf einem neuen/anderen Rechner pruefen und ggf. nachziehen; fehlt etwas, hier eintragen.

## 1. Luefter und GPU-Leistung (Laptop, hp-wmi / OMEN; auf anderen Geraeten analog)
- Der Treiber kennt nur Automatik (zurueckhaltend, GPU drosselt bei 84 C) und volle Drehzahl. `tools/luefter_adaptiv.sh` regelt zweistufig
  nach GPU/CPU-Temperatur (voll ab 75 C, Automatik unter 62 C, Hysterese). Dauerhaft als Dienst, EINMAL pro Rechner:
  `sudo ~/git/rc-park/tools/luefter_installieren.sh`   (pruefen: `systemctl status luefter_adaptiv`)
- Ohne hp-wmi (`/sys/class/hwmon/*/pwm1_enable` fehlt): Skript bricht mit Meldung ab; dann Hersteller-Werkzeug (nbfc, asusctl, thinkfan) und
  diese Datei ergaenzen.
- GPU-Leistungslimit: `nvidia-smi -q -d POWER` zeigt Current/Max; OMEN 16: 80 W Standard, 140 W moeglich: `sudo nvidia-smi -pl 140`
  (gilt bis Neustart; nur mit laufendem Luefterregler sinnvoll). Energieprofil: `powerprofilesctl set performance`.
- **CPU-Leistung (6.11.):** Werkseinstellung 25 W/31 W (Chip darf 55 W), Takt unter Last ~1 GHz. Pakete einmalig: `sudo apt install linux-tools-$(uname -r) msr-tools` + `sudo modprobe msr`
  (turbostat/rdmsr, ohne sie laeuft `tools/leistung_diagnose.sh` nicht; nach Kernel-Update nachziehen). Messung/Regler/Dienst: `modelle/CPU_LEISTUNG.md`
  (`sudo bash tools/leistung_testen.sh --beide`, `sudo tools/cpu_leistung_installieren.sh`). GPU-Powerlimit per `nvidia-smi -pl` bringt hier nichts (Karte bleibt bei ~80 W).
- GPU parallel: Absturz = VRAM-Summe > ~7,8 GB; Budget-Jobs per `JOB_GPU_MB` in `tools/job_start.sh`, SIFT `RCPARK_SIFT_MAX=1600` (Details `modelle/GPU_PARALLEL_UNTERSUCHUNG.md`, `modelle/CPU_LEISTUNG.md` Abschnitt 5).
- Nur EIN GPU-Job zur Zeit (Altregel, bleibt fuer Jobs OHNE Budget): COLMAP SIFT-GPU stuerzt neben LightGlue/Torch ab ('illegal memory access'). `tools/nullstart.py` wartet per
  gpu_warten(), die Ernte deckelt auf 45 % GPU-Speicher; `sfm_netz.py` hat CPU-Rueckfall.

## 2. Platten
- Root ist klein (48 GB). ALLES Grosse auf die Datenplatte: `/media/oem/scan/rc-park_daten/<objekt>/` (fotos, fotos_eingang, sfm, Ernte-Caches)
  und `/media/oem/scan/rc-park_null/` (Nullstart-Objekte); im Repo nur Symlinks (`ls -l daten/martinstor modelle/martinstor/sfm`).
  Vor grossen Laeufen `df -h /`. Auf einem anderen Rechner: Datenplatte einhaengen, Symlinkziele anpassen oder Daten dorthin kopieren.

## 3. Python-Umgebungen
- `/media/oem/scan/venv-seg/bin/python -I` (torch, CUDA, trimesh, embreex, lightglue): Analyse, Wolken, Regression, Nullstart.
- `/media/oem/scan/venv-colmap/bin/python -I` (pycolmap 4.2.1, scipy 1.13, numpy 1.26): sfm_netz/ausrichten/registrieren/dicht.
- `~/.venvs/rcpark/bin/python` (manifold3d): Generatoren.
- Neue Pakete nur verlustfrei und dokumentiert (modelle/LIZENZ_WERKZEUGE.md).

## 4. Zugangsdaten
- Mapillary (kostenlos, Developers -> Register Application): Token nach `~/.config/mapillary_token`; dann liefert `tools/bilder_holen.py`
  georeferenzierte Strassenbilder aller Seiten. Ohne Token meldet das Werkzeug die Quelle als uebersprungen.

## 5. Schnelltest nach der Einrichtung
- `tools/regression.py modelle/martinstor/objekt.json --pruefen` (9 s, 10 Dateien identisch) und einmal `tools/nullstart.py ... --ziel martinstor_null`.

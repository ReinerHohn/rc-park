# Rechnen auf Runpod (Stand 27.11.2026, vorbereitet und lokal getestet, in der Cloud NOCH NICHT gelaufen)

Erster Zweck: die dichte Wolke der Handyfotos 26.11. (Schwabentor-Teilmodell, 634 Bilder) in EINEM Stück und in voller Bildgröße.
Lokal (15 GB RAM) musste die Fusion in Kacheln/Teile zerlegt werden; dabei gingen an Treppe, Anbau und Steg Punkte verloren.
Allgemeine Cloud-Überlegungen (Upload-Messung, was nicht hochgeht, vast.ai): [CLOUD_VAST.md](CLOUD_VAST.md). Diese Datei ersetzt sie nicht.
Projekt-Ast (Gilt · Versucht · Offen): [Doku/projekt/betrieb/cloud.md](../../Doku/projekt/betrieb/cloud.md).

## Werkzeuge
- `tools/cloud/runpod_paket.py`: baut das Minimal-Paket. Es prüft, ob jedes Bild zu seiner Kamera passt; `--mini N --box` wählt N Bilder einer Zone für den Mini-Test.
- `tools/cloud/runpod_dicht.sh`: läuft auf dem Pod oder lokal (`--lokal`). Es übernimmt Kostenbremse, Umgebung, Entpacken, Rechenkern und Packen.
- `tools/cloud/runpod_dicht.py`: der Rechenkern (Entzerren, PatchMatch, Fusion am Stück, Takt-Protokoll mit RAM/GPU). `--nur_pruefen` = Dry-Run.

## Was ins Paket gehört
Nötig sind nur das Sparse-Modell (cameras/images/points3D/frames/rigs.bin, 159 MB) und die 634 Rohbilder (909 MB).
Entzerrt wird erst in der Cloud; das ist je Kamera deterministisch.
Nicht nötig: `db.db` (2,9 GB, nur für SfM), `lg.npz`, Tiefenkarten und nicht registrierte Bilder.
- Groß: `/media/oem/rcdaten/tmp/runpod_paket/handy_teil.tar.zst` = **972 MB**, Upload ≈ 7 min (ANNAHME 8,5 GB/h, Messung 20.11.).
- Mini: `/media/oem/rcdaten/tmp/runpod_paket/handy_mini20.tar.zst` = 38 MB (20 Bilder, Box x 0..12, y −18..−6 Modellmeter, Treppe/Anbau-Ende des Stegs).
- Quelle: `zusatz_20261126_voll/lg/teilmodell/0_ausgerichtet`, derselbe Rahmen wie die lokale Wolke `handy_teil_dicht`.
  Ein anderer Rahmen (z. B. die neue Einpassung `/media/oem/rcdaten/tmp/handy_teil_spuren/teil_sfm`) heißt: Paket neu bauen.
  Der Zeitbedarf ist gleich, weil die Bilder dieselben sind.

## Pod-Wahl (Preisliste runpod.io/pricing, abgerufen 27.11.2026, Preise USD/h, RAM je GPU)
- **RTX 4090 reicht NICHT**: Runpod gibt je 4090 nur 41 GB RAM und 6 vCPU. Die Fusion braucht in voller Größe geschätzt 87 GB (634 × 5,07 Mpx × 27 MB/Mpx, gemessen im Mini-Test).
- **Empfehlung RTX 3090**: 24 GB VRAM, **125 GB RAM**, 16 vCPU; Community 0,22 $/h, Secure 0,50 $/h.
- Ersatz: L40S (48 GB, 94 GB RAM) für 0,79 bzw. 1,09 $/h. A6000 hat nur 50 GB RAM, 5090 nur 35 GB RAM; beide sind ungeeignet.
- Filter: 1 GPU, CUDA ≥ 12.8 (das Wheel nutzt CUDA 12.9), Container-Platte 100 GB (Tiefen- und Normalenkarten ≈ 68 GB), Volume 20 GB.
  Das Volume liegt unter `/workspace` und hält nur Paket und Ergebnis. Es bleibt beim Stoppen erhalten und kostet dann 0,20 $/GB/Monat, also 4 $/Monat.
  Deshalb den Pod nach dem Download IMMER löschen.
- Image: das offizielle Runpod-PyTorch-Template (z. B. `runpod/pytorch:...-cuda12.8...-ubuntu22.04`). Es bringt Python 3.10–3.12, SSH und `runpodctl` mit.
  Die Umgebung braucht nur `pip install pycolmap-cuda12==4.2.1`, wie lokal (73-MB-Wheel, manylinux_2_28; enthält Kernel für sm_80, die auch auf sm_86/89 laufen).

## Zeit und Kosten (ANNAHME, ungemessen in der Cloud)
- Lokal gemessen (27.11.): PatchMatch für 634 Bilder bei 1600 px mit window_step 2 auf der RTX 4060 Laptop dauerte 52 min (4,9 s je Bild).
- Mini-Test lokal (20 Bilder): volle Größe 177 s gegen 98 s bei 1600 px, also ×1,8 → ≈ 95 min auf der 4060 für alle 634 Bilder. ANNAHME: die 3090 ist 2–2,5× schneller → **40–50 min**.
- Fusion bei 16 vCPU, volle Größe: ANNAHME 20–40 min. Einrichten, Entpacken und Entzerren: ≈ 10 min.
- Summe ≈ 1,2–1,7 h. Hinzu kommen das Download-Fenster (bis 45 min) und der Mini-Test (≤ 15 min).
- Auf einer 3090 Community (0,22 $/h) ergibt das **≈ 0,6 $**, auf Secure (0,50 $/h) **≈ 1,4 $**. Das Zeitlimit von 3 h deckelt den Lauf bei 0,66 bzw. 1,50 $ zuzüglich Fenster.
  Beides liegt weit unter 6 EUR je Lauf bzw. 10 EUR gesamt (ANNAHME Kurs 1 EUR ≈ 1,15 $).

## Kostenbremse (im Skript)
1. Auf dem Pod rechnet nichts, wenn `runpodctl` fehlt oder den eigenen Pod (`$RUNPOD_POD_ID`, Pod-Schlüssel `$RUNPOD_API_KEY`, beide setzt Runpod automatisch) nicht abfragen kann (rc 7).
2. Ein Wächter (eigener Prozess per setsid, überlebt SSH-Abbruch) stoppt nach `--stunden` (Standard 3) den Rechenkern, packt und stoppt den Pod.
   Dafür dient `runpodctl pod stop $RUNPOD_POD_ID`, bei alter CLI `runpodctl stop pod`. Mit `--stopp delete` wird der Pod gelöscht.
3. Bei Erfolg folgt der Selbststopp nach `--warte_min` (45), bei einem Fehler nach `--warte_fehler_min` (20). In diesem Fenster wird heruntergeladen.
4. Grenze: Der Pod-Hauptprozess darf nicht einfach enden, sonst startet Runpod den Container neu und berechnet weiter.
   Nur der API-Stopp beendet die GPU-Abrechnung. Wenn die Prüfung unter 1. scheitert, muss der Hauptagent den Pod von außen stoppen.
   Die zweite Bremse ist das Guthaben: Runpod läuft auf Vorkasse, bei 0 stoppen die Pods.

## Befehlsliste für den Hauptagenten (erst nach Freigabe des Nutzers)
0. Lokal prüfen: `ls -la /media/oem/rcdaten/tmp/runpod_paket/` (beide `.tar.zst` und `.sha256`). Kontostand im Runpod-Konto ansehen (10 $ Guthaben).
   Einen SSH-Schlüssel im Konto hinterlegen (Settings → SSH Public Keys: `cat ~/.ssh/id_ed25519.pub`).
1. Pod anlegen (Web-Konsole oder MCP): RTX 3090 ×1, Community Cloud, Template Runpod PyTorch (CUDA 12.8), Container Disk 100 GB, Volume 20 GB unter `/workspace`.
   TCP-Port 22 freigeben (SSH over exposed TCP). Den Preis je Stunde notieren; er ist die echte Grundlage statt der ANNAHME.
2. SSH-Daten aus „Connect → SSH over exposed TCP" holen: `ssh root@<IP> -p <PORT> -i ~/.ssh/id_ed25519`.
3. Hochladen (der einfachste sichere Weg ist rsync über SSH: verschlüsselt, setzt nach Abbruch fort):
   `rsync -av --partial --progress -e "ssh -p <PORT>" /media/oem/rcdaten/tmp/runpod_paket/handy_mini20.tar.zst* tools/cloud/runpod_dicht.sh tools/cloud/runpod_dicht.py root@<IP>:/workspace/`
   (Fehlt rsync im Image, vorher per SSH `apt-get update && apt-get install -y rsync zstd` ausführen oder `scp -P <PORT>` nutzen.)
4. MINI-TEST in der Cloud (≤ 15 min, Cent-Betrag):
   `ssh ... 'cd /workspace && nohup bash runpod_dicht.sh --paket /workspace/handy_mini20.tar.zst --stunden 0.25 --warte_min 20 --arbeit /root/arbeit_mini --ergebnis /workspace/erg_mini > /workspace/mini.out 2>&1 &'`
   Warten mit einer einmaligen Schleife und Zeitlimit:
   `timeout 900 bash -c 'until ssh ... grep -q JOB_ENDE /workspace/erg_mini/lauf.log; do sleep 30; done'`
   Danach `ssh ... tail -20 /workspace/erg_mini/lauf.log /workspace/erg_mini/protokoll.log`.
   Prüfen: rc=0, `Kostenbremse: runpodctl erreicht Pod`, Punktzahl ähnlich lokal (Mini lokal: siehe Ast), RAM-Spitze der Fusion je Mpx.
   Die RAM-Spitze der Fusion (`protokoll.json` → `spitzen.rss_je_phase_mb.fusion`, lokal 3319 MB) gegen die Pause davor (`patchmatch`, lokal 805 MB) rechnen:
   (Fusion − Grundlast) / (20 × 4,79 Mpx) ergab lokal 26,2 MB/Mpx; der Standard ist 27. Liegt der Wert deutlich darüber, beim großen Lauf `-- --ram_mb_je_mpx <Wert>` setzen.
   Das Protokoll muss `RAM frei ... (Grenze ...)` zeigen; ist die Grenze kleiner als 109 GB, verkleinert das Skript die Fusion und meldet `FUSION VERKLEINERT`.
5. GROSSER LAUF (auf demselben Pod, das Mini-Ergebnis ist geholt). Ein neuer Aufruf ersetzt den Wächter des Mini-Tests:
   `rsync ... handy_teil.tar.zst* root@<IP>:/workspace/`, dann
   `ssh ... 'cd /workspace && nohup bash runpod_dicht.sh --paket /workspace/handy_teil.tar.zst --stunden 3 --warte_min 45 > /workspace/lauf.out 2>&1 &'`
   Nach 5–10 min einmal nachsehen (`tail /workspace/ergebnis/protokoll.log`: PHASE patchmatch, gpu %, kein ABBRUCH). Dann einmalig warten (timeout, kein Dauer-Check).
6. Herunterladen (Ergebnis-Tar ≈ fused.ply, ANNAHME 0,5–1 GB):
   `rsync -av --partial -e "ssh -p <PORT>" root@<IP>:/workspace/ergebnis/ /media/oem/rcdaten/tmp/runpod_ergebnis/handy_teil_voll/`, dann lokal `sha256sum -c ergebnis.tar.sha256` und `tar -xf ergebnis.tar`.
7. Pod LÖSCHEN (nicht nur stoppen): in der Web-Konsole Terminate oder `runpodctl pod delete <POD_ID>` bzw. per MCP. Danach muss die Pod-Liste leer sein, auch ohne gestoppte Pods.
8. Abrechnung: Runpod-Konsole → Billing (Verbrauch des Tages, Restguthaben); die Zahlen ins Logbuch und in den Ast `Doku/projekt/betrieb/cloud.md` (Versucht) eintragen.
9. Lokal weiter: `tools/wolke_vereinigen.py` (Zweig wolken-vereinen, Stufe `wolken_vereinen_stufe.sh`) mit `--quelle handy_voll=<fused.ply>`.
   Dann Treppe/Anbau/Steg je Zelle zählen (`tools/dichte_diagnose.py`), gegen `handy_teil_dicht` (kachel.ply / vereint.ply) und Bild ansehen.

## Lokaler Mini-Test 27.11. (20 Bilder, RTX 4060, job_start mit GPU-Buchung)
- rc 0. Entzerren 1 s, PatchMatch 177 s (100 % GPU, VRAM-Spitze 3,8 GB), Fusion 22 s mit RAM-Spitze 3,3 GB. Ergebnis 21 164 Punkte.
- Gegenprobe gleiches Paket mit `-- --groesse 1600`: 98 s, 18 956 Punkte. Volle Größe bringt 2,07× gültige Tiefenpixel (18,1 gegen 8,75 Mio), aber nur +12 % Punkte nach der Fusion.
- Die Tiefenkarten sind im Mini nur zu 5–35 % gefüllt; im lokalen 634-Bilder-Lauf sind dieselben Bilder zu 28–59 % gefüllt. Ursache (ANNAHME): Nur 20 Nachbarbilder stehen zur Verfügung. Das Mini taugt nicht als Dichtemaß.
- Bild: Draufsicht und Seitenansicht beider Mini-Wolken zeigen gleiche Lage. Die volle Größe reicht höher (z p95 15,7 gegen 11,8 m).
- Kostenbremse lokal mit einem Ersatz-runpodctl geprüft: Ohne erreichbares runpodctl endet der Lauf mit rc 7, ohne zu rechnen.
  Das Zeitlimit beendet den Kern (rc 143), packt und ruft `runpodctl pod stop <id>`. Nach Erfolg und Fenster 0 min folgt ebenfalls `pod stop`.

## Lokal testen (vor jedem Mieten)
`JOB_CPU=alle JOB_GPU_MB=4500 JOB_RAM_MB=4000 bash tools/job_start.sh runpod-mini <log> bash tools/cloud/runpod_dicht.sh --lokal --paket /media/oem/rcdaten/tmp/runpod_paket/handy_mini20.tar.zst --arbeit <dir> --ergebnis <dir> --py /media/oem/scan/venv-colmap/bin/python`
Dry-Run des großen Pakets: dasselbe mit `--nur_pruefen` und `--paket /media/oem/rcdaten/tmp/runpod_paket/handy_teil`. Es meldet den RAM-Plan und Platzbedarf und rechnet nichts.

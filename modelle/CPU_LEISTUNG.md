# CPU/GPU maximal auslasten - Messung, Werkzeuge, Einrichtung (Stand 2026-11-06)

Rechner: HP OMEN 16 (Board 8C77, BIOS F.15), i7-14700HX (28 Threads), RTX 4060 Laptop 8 GB, 15 GB RAM, Linux 6.17 OEM, Secure Boot an.
Alles Folgende ist GEMESSEN (Quelle: `/media/oem/scan/rc-park_daten/leistung_test_*.log`) oder ausdruecklich als Vermutung markiert.

## 1. Befund
- **CPU-Dauerlimit steht ab Werk/zur Laufzeit auf 25 W (PL1) / 31 W (PL2)**, obwohl der Chip 55 W Dauerlast erlaubt (`constraint_0_max_power_uw`) und die Firmware-Schnittstelle
  `intel-rapl-mmio` 55 W / 130 W zeigt. Netzbetrieb (ACAD online) ist NICHT die Ursache. Wer das Limit senkt, ist ungeklaert (Vermutungen: HP-Firmware im Standardprofil,
  weil `platform_profile` auf diesem Board fehlt; `thermald --adaptive` mit den DPTF-Tabellen der Firmware). Waehrend der Messungen wurde das gesetzte Limit NICHT zurueckgeschrieben.
- Unter Volllast bei 25 W: Takt ~1 GHz, Temperatur nur 65-68 C -> **Leistungslimit, kein Hitzeproblem.**
- **Messung (20 s Volllast je Stufe, Fremdlast COLMAP/Agenten lief mit - verrauscht):**

  | Stufe | Paket (Ist) | Takt | Durchsatz | Temp |
  |---|---|---|---|---|
  | ref-1 25/31 W | 25,0 W | 992 MHz | 2,20 Mio/s | 68 C |
  | 45/90-1 | 45,4 W | 1942 MHz | 4,20 Mio/s (+91 %) | 73 C |
  | 55/120-1 | 40,7 W | 1414 MHz | 4,02 Mio/s | 73 C |
  | ref-2 | 31,0 W | 1328 MHz | 2,94 Mio/s | 72 C |
  | 45/90-2 | 40,3 W | 1528 MHz | 3,62 Mio/s | 73 C |
  | 55/120-2 | 35,3 W | 1536 MHz | 2,81 Mio/s | 76 C |

  Lesart: Bis 45 W folgt die Paketleistung dem Limit, Gewinn +20 bis +90 % (je nach Waermezustand). Mit warmem Geraet zieht das Paket bei gleichem Limit weniger (45 -> 40 W).
  **55 W bringt nichts**: das Limit blieb gesetzt (`PL1-mitte 55`), das Paket kam nie ueber 41 W -> eine ANDERE Bremse (Kuehlung/Firmware) greift. Welche, ist offen (-> Abschnitt 4).
  ref-2 ist nicht "Rauschen": Kurzzeit-Limit PL2 31 W + Zeitfenster 32 s erlauben nach einer Pause kurz mehr als PL1.
- **GPU:** `nvidia-smi -pl 100/130` laesst sich setzen, die Karte zieht trotzdem ~80 W (Dynamic Boost/Firmware). **Kein Gewinn durch Powerlimit** (Messung 15:07, GPU-Teil des Skripts).
  Der 115-W-Lauf lieferte keinen Messwert (Fehlschlag, nicht ausgewertet).

## 2. Benoetigte Pakete (einmal pro Rechner, braucht Root)
```
sudo apt install linux-tools-$(uname -r) msr-tools      # turbostat (Takt/Leistung/Temperatur), rdmsr (Limit-Gruende MSR 0x64F)
sudo modprobe msr                                       # fuer rdmsr/turbostat (Zugriff auf /dev/cpu/*/msr)
```
Ohne diese Pakete laeuft `tools/leistung_diagnose.sh` nicht (bricht mit Meldung ab); `turbostat` meldet sonst "not found for kernel ..." bzw. "Failed to access /dev/cpu/0/msr" (nicht als root).
Das Paket muss zur LAUFENDEN Kernelversion passen (`uname -r`; nach einem Kernel-Update nachinstallieren). Secure Boot (an): erlaubt Lesen der MSR, blockiert aber Schreiben
(Undervolting ueber MSR 0x150 geht deshalb NICHT; nur mit abgeschaltetem Secure Boot, ungeprueft - nicht empfohlen ohne BIOS-Wissen).

## 3. Werkzeuge im Repo
| Werkzeug | Zweck |
|---|---|
| `sudo bash tools/leistung_testen.sh [--beide]` | CPU-Stufen 25/45/55 W je 2x, danach GPU-Powerlimit-Stufen (nur wenn GPU-Lock frei). Setzt alles am Ende zurueck. Log unter `rc-park_daten/`. |
| `sudo bash tools/leistung_diagnose.sh [DAUER] [PL1]` | Was bremst? Volllast + turbostat + Limit-Gruende (0x64F). Braucht die Pakete aus Abschnitt 2. |
| `sudo tools/cpu_leistung_installieren.sh` | Dauerhaft (systemd): `tools/cpu_leistung_regler.sh` hebt PL1 von 35 W in 5-W-Schritten bis 55 W an, solange Paket-Temp < 80 C, GPU-Temp < 83 C und das Paket >= 90 % des Limits zieht; senkt ab 88 C, Notbremse ab 92 C (zurueck auf 35 W). Setzt PL2 130 W (Zeitfenster bleibt unveraendert). Fremde Aenderungen am Limit werden zurueckgeschrieben und gezaehlt (`journalctl -fu cpu_leistung_regler`, `/run/cpu_leistung_regler.state`). Stoppen stellt die Ausgangswerte wieder her. Parameter als Umgebungsvariablen im Dienst (`START MAX SCHRITT TOK THOCH TNOT GOK T PL2 TAU_US`). |
| Sofort, ohne Dienst (gilt bis Neustart) | `echo 45000000 \| sudo tee /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw` und `echo 90000000 \| sudo tee .../constraint_1_power_limit_uw` |

## 3b. Diagnose-Lauf 15:13 (PL1 45 W, 40 s Volllast, `leistung_diagnose_20261106_*.log`)
- Die ersten ~30 s: Paket 44,8-45,0 W (= Limit), 1,92-1,96 GHz, 73-75 C. Dann bei t = 33 s (15:13:55) **faellt die Leistung abrupt auf 34-38 W, 1,47-1,76 GHz**, obwohl PL1 weiter 45 W ist
  und die Temperatur dabei von 75 auf 72 C sinkt. Dauerzustand also ca. **35-38 W**, nicht 45 W; passt zu den Stufen 55 W (Paket 35-41 W).
- Kein Kernel-Ausloeser: die Trip-Punkte der Zone TCPU liegen bei 103-110 C (kein Punkt bei 75 C), `intel_powerclamp` cur=0, PL1 wurde nicht veraendert. Ursache = wohl Firmware/EC (z. B. Waermebudget/Dynamic Tuning). UNBEWIESEN.
- MSR 0x64F zeigte VOR der Last denselben Rohwert (9d030400) wie waehrend der Last -> keine Aussagekraft; die Bitnamen im Skript sind nach Gedaechtnis (SDM), nicht verifiziert. Spaltenreihenfolge des Skripts: Bzy_MHz, PkgTmp, PkgWatt.
- Folge: Boost ~30 s auf PL1, danach ~36 W. PL2/Tau-Erhoehung ueber 45 W bringt daher voraussichtlich nichts; naechster Test waere 55 W (zeigt, ob der 30-s-Abfall bleibt) und ein Lauf mit Lueftern auf voller Drehzahl
  (`echo 0 | sudo tee /sys/class/hwmon/hwmon*/pwm1_enable`, zurueck mit 2).

### 3c. Gegenprobe mit Luefter VOLL (15:15, PL1 45 W, 60 s)
- Gleiches Muster: 45 W bis ca. t = 33 s, dann ~37-40 W (Mittel ~39,5 W, vorher ohne Vollluefter ~36-38 W) bei 71-74 C (nicht heisser als vorher). **Kuehlung ist NICHT der Hauptbegrenzer** (+~2 W durch volle Drehzahl).
  Das 0x64F-Register zeigte beim Abfall keine Aenderung -> die CPU meldet keinen Grund; die Bremse sitzt ausserhalb (Firmware/EC) oder ist ein Zeitfenster-Effekt (Abfall ~33 s ~ Dauerlimit-Zeitfenster 32 s, evtl. Zufall).
  Zu der Zeit lief die GPU mit (video_dicht, ~45 W): ein geteiltes Plattformbudget (CPU+GPU) ist moeglich, aber nicht belegt (keine `psys`-Domaene in /sys/class/powercap).
- **Netzteil:** Original-HP, 280 W (Nutzerangabe 6.11.) -> weder Wattzahl noch Netzteil-Erkennung erklaeren die Grenze. Bleiben: Firmware/EC-Timer oder -Sensorik, geteiltes CPU/GPU-Budget, Zeitfenster-Effekt.
- Entscheidungstest: `sudo bash tools/leistung_diagnose.sh 90 45 100` (Zeitfenster auf 100 s). Wandert der Abfall von ~33 s nach hinten -> Tau-Effekt (dann Zeitfenster dauerhaft hoch, Regler setzt TAU_US); bleibt er bei ~33 s -> Firmware/EC-Timer.
  Zweiter Test ohne GPU-Last (kein GPU-Job laeuft) zeigt, ob die GPU das CPU-Budget schmaelert.

### 3d. Zeitfenster-Test (15:18, PL1 45 W, Fenster 95 s statt 31 s, 90 s Volllast)
- 45 W bis ca. t = 40 s (Abfall 15:18:43; vorher nach ~33 s), danach Pendeln 34-40 W (Mittel ~38 W) bei konstant 72-74 C. **Das Zeitfenster ist NICHT die Ursache** (sonst Abfall bei ~95 s).
  Es bleibt ein Firmware-/EC-Timer (~30-40 s) bzw. geteiltes CPU/GPU-Budget (GPU lief mit). Der Regler aendert das Zeitfenster daher nicht mehr (`TAU_US` leer).
- Praktischer Nutzen: ~40 s Boost auf das gesetzte PL1, danach ~38 W Dauer = ca. +50 % gegenueber 25 W. Hoeheres PL1/PL2 ueber 45 W ist wirkungslos, solange der Timer greift. Offen: Test OHNE GPU-Last.

## 4. Offen / naechste Schritte
1. `leistung_diagnose.sh` ausfuehren (Pakete aus Abschnitt 2): zeigt, ob THERMAL/PROCHOT/VR/EDP die CPU bei >40 W begrenzt. Danach entscheidet sich, ob der 130-W-Kurzzeitboost nutzbar ist.
2. Kuehlung: Lueftersteuerung steht auf BIOS-Automatik (`pwm1_enable=2`, volle Drehzahl springt erst ab 75 C durch `luefter_adaptiv`); die Drehzahl wird vom Treiber nicht gemeldet. Praktisch: Unterlage mit Luftzug, Lueftungsschlitze reinigen.
3. Regler erst installieren, wenn Abschnitt 4.1 klar ist; MAX > 55 W ist ungetestet.
4. Der Regler-Zielwert haengt vom Waermezustand: im warmen Dauerbetrieb sind ca. 40 W Paketleistung real erreichbar, nicht 55 W.

## 5. GPU parallel (Befund `modelle/GPU_PARALLEL_UNTERSUCHUNG.md`)
- Der "Crash" ist VRAM-Ueberbelegung: Absturz (Xid 31 + NVRM NO_MEMORY) bei Summe ~7,8 von 8,2 GB; SiftGPU scheitert sonst STILL (0 Keypoints, rc 0).
- SiftGPU braucht 7,4 GB bei `max_image_size` 3200, 2,1 GB bei 1600, 0,9 GB bei 1024; es belastet die GPU kaum (~1 %), verdraengt nur Speicher.
- Stabil gemessen (3 Wiederholungen): Torch 4 GB + SIFT `max_image_size=1600` parallel: 0 Ereignisse, GPU 99 %, SIFT unveraendert schnell, Torch 82-92 % -> grob +70-80 % Gesamtdurchsatz (Schaetzung aus Messlasten).
- Eingebaut (opt-in, Standardverhalten unveraendert): `JOB_GPU_MB=<MiB>` in `tools/job_start.sh` (Budget-Job laeuft parallel, wenn belegter VRAM + Budget <= `JOB_GPU_LIMIT_MB`, Standard 7000; beachtet Exklusiv-Sperre, schreibt keine);
  `RCPARK_SIFT_MAX=1600` in `tools/zusatzfotos_registrieren.py`; dort jetzt auch ein Gate "0 Keypoints -> Abbruch". Getestet: Wartepfad (Meldung "GPU belegt durch ..."). NICHT getestet: Startpfad bei freier Karte.
- Offen: 3-4 gleichzeitige Prozesse, VRAM-Bedarf je echtem Job (PatchMatch, LightGlue, OWLv2, foto_diff-GPU) einzeln messen.

## 6. hp-wmi fuer Board 8C77 (Stand 6.11. 16:00: Modul laeuft, erster Lauf mit performance - VORLAEUFIG)
**Befund:** Kernel 6.17 kennt das Board 8C77 (OMEN 16-wf1xxx) in `hp-wmi` nicht (Upstream-Commit 344bf523, erst nach 6.17). Ohne Treiber-Eintrag gibt es kein `platform_profile`; die Firmware bleibt im Standardprofil. **Vermutung (unbewiesen):** das Profil `performance` hebt die ~38-W-Dauerbremse.
**Bau:** `tools/hp_wmi_8c77/` (hp-wmi.c aus linux-6.18.y plus Eintrag fuer 8C77, Makefile, README); Modul gegen die Header von 6.17.0-1032-oem gebaut, `hp-wmi.ko` unter /media/oem/scan/rc-park_null/hpwmi_bau/build/.
**Secure Boot ist AN** (mokutil), Kernel-Lockdown [integrity]: unsignierte Module werden abgelehnt -> Signatur mit MOK, einmaliges Passwort per `mokutil --import`, Bestaetigung beim naechsten Start (blauer Bildschirm).
**Ablauf:** `tools/hp_wmi_installieren.sh bauen | signieren | laden | zurueck` (sudo selbst). Nach dem Reboot: MOK enrollen, `laden`, `echo performance | sudo tee /sys/firmware/acpi/platform_profile`, `sudo bash tools/leistung_diagnose.sh 60 45`.
**Auswertung:** faellt die Leistung weiter nach ~35 s auf ~38 W -> Profil bringt nichts (Ergebnis hier eintragen, Modul per `zurueck` entfernen); haelt sie -> Gewinn, Prozent in 1. eintragen.
**Wartung:** nach jedem Kernel-Update Modul neu bauen und signieren. Rueckweg jederzeit mit `zurueck`.

### 6b. Erster Lauf mit Profil performance (6.11. 15:59, `leistung_diagnose.sh 60 45`, Ausgang 35/130 W)
- Modul geladen (Signer = MOK-Schluessel, Secure Boot an), `platform-profile-0` = hp-wmi, Auswahl low-power/balanced/performance, Profil stand auf performance.
- Verlauf: t = 0-14 s **~111 W, 3,59 GHz, 92-96 C**; dann Einbruch auf **34 W / 1,84 GHz bei 68 C** (Temperatur faellt sofort, EDP/ICCMAX-Bit im 0x64F - Rohwert unsicher);
  danach **stufenweise Anstieg 34 -> 40 -> 45 -> 50 -> 55 W** (Takt 1,8 -> 2,6 GHz) in ca. 45 s bei konstant 65-68 C, Plateau 55 W (= `constraint_0_max_power_uw`) erst am Laufende.
- Vergleich mit 3b-3d (balanced, ohne Modul): dort Abfall nach 33-40 s auf Pendeln 34-40 W (Mittel ~38 W). Jetzt kein Pendeln, sondern Anstieg ueber das gesetzte PL1 (45 W) hinaus -> Firmware setzt Limits offenbar selbst.
- **NICHT BEWIESEN:** kein Balanced-Lauf direkt davor im gleichen Waermezustand; Lauf endete beim Anstieg (Plateau/Dauerwert unbekannt); der Einbruch bei 96 C koennte ein Hitzeschutz nach dem 111-W-Stoss sein.
- Naechste Messungen: (1) gleicher Lauf mit `balanced` direkt hintereinander (A/B), (2) 180 s Dauer mit performance, (3) Durchsatz-Messung statt nur Watt.

### 6c. 180-s-Lauf mit performance (6.11. 16:02, Ausgang 55/130 W) - Balanced-Umschaltung misslang (Tippfehler `profil`), also KEIN A/B
- Wiederholbar: 12 s Stoss ~110 W bei 97 C (0x64F = THERMAL, also echte Hitzebremse im Stoss), Einbruch auf 34 W, Treppe 40/45/50/55 W (alle ~10 s +5 W).
- **Dauerplateau 55 W (54,9-55,0) ueber 133 s (16:03:12-16:05:25), 2,58 GHz, 67-70 C, ohne Abfall.** Vorher (balanced, ohne Modul): Abfall auf ~38 W, Pendeln. Plus ca. 45 %.
- Temperatur 67-70 C -> Kuehlung begrenzt nicht; 55 W = Leistungslimit (= constraint_0_max). 0x64F zeigt dauerhaft EDP/ICCMAX (Rohwert, unsicher).
- Offen: sauberer A/B (balanced direkt davor), GPU-Messung, Dauerbetrieb des Profils (Modul beim Boot laden, nach Kernel-Update neu bauen+signieren).

### 6d. A/B balanced vs performance (6.11. 16:14-16:34, `tools/leistung_ab.sh`, Modul geladen, je Phase 2. Haelfte gemittelt)
| Profil | Phase | CPU W | CPU MHz | CPU C | CPU Durchsatz/s | GPU W | GPU MHz | GPU TFLOPS |
|---|---|---|---|---|---|---|---|---|
| balanced | CPU | 51,0 | 2588 | 69 | 5,76 Mio | - | - | - |
| balanced | GPU | 39,3 | 4441 | 94 | - | 72,8 | 2232 | 26,8 |
| balanced | CPU+GPU | 52,4 | 2661 | 79 | 5,39 Mio | 71,2 | 2206 | 26,5 |
| performance | CPU | 51,4 | 2621 | 69 | 5,89 Mio | - | - | - |
| performance | GPU | 35,5 | 4286 | 95 | - | 106,7 | 2595 | 31,2 |
| performance | CPU+GPU | 53,0 | 2599 | 80 | 5,20 Mio | 107,3 | 2595 | 31,2 |
- **CPU: Profil ohne Wirkung** (51,0 vs 51,4 W, 5,76 vs 5,89 Mio/s, +2 % = Rauschen). Gewinn (38 -> 51-55 W) kommt vom GELADENEN Modul/Treiber, nicht vom Umschalten. NICHT gemessen: gleicher Test OHNE Modul.
- **GPU: performance wirkt** (+47 % Leistung, +16 % TFLOPS). Board 8C77 laeuft im Victus-S-Pfad (cTGP+PPAB werden bei performance gesetzt).
- **CPU+GPU zusammen:** GPU verliert nichts (31,2 wie allein), CPU -12 % gegenueber CPU allein (5,20 vs 5,89 Mio/s; 80 C, GPU-Fuetterungsthread + gemeinsame Kuehlung), Paket+GPU ~160 W. Kein hartes gemeinsames Budget erkennbar.
- Einzelkern-Takt bis 4,4 GHz bei wenig Last (GPU-Phase), 94-95 C wegen gemeinsamer Kuehlung.
- Plattform-Profil performance bleibt Standard; `tools/hpwmi_pruefen.sh` zu Sitzungsbeginn (Modul gilt nur fuer Kernel 6.17.0-1032-oem).

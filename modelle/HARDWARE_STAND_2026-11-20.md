# Hardware-Stand und Aufruest-Optionen (gemessen 20.11.2026)

Rechner: HP OMEN 16-wf1xxx (Board 8C77, BIOS F.15 vom 08.01.2025), i7-14700HX, RTX 4060 Laptop 8 GB. Verwandt: `modelle/CPU_LEISTUNG.md`, Ast `Doku/projekt/betrieb.md`.
Quelle der Speicherdaten: `sudo dmidecode -t memory` / `-t slot` (Nutzer, 20.11. ca. 15:30; Rohdatei `~/ram_info.txt`).

## Arbeitsspeicher (gemessen)
- Verbaut: 2 x 8 GB = 16 GB, Samsung M425R1GB4BB0-CWM, DDR5-5600 SO-DIMM, 1,1 V, Rang 1. BEIDE Steckplaetze belegt ("Bottom-slot 1 (left)", "Bottom-slot 2 (right)").
- Firmware meldet `Maximum Capacity: 64 GB`, 2 Steckplaetze -> 2 x 32 GB ist laut Geraet selbst zulaessig (HP-Datenblatt nennt nur 32 GB; die Firmware-Angabe ist die bessere Quelle, ein Betriebstest steht aus).
- KAUFEMPFEHLUNG: **2 x 32 GB DDR5-5600 SO-DIMM (262 Pin, 1,1 V, CL46, ohne ECC), als Paar**, mit Rueckgaberecht. Die zwei 8-GB-Riegel kommen raus (kein Mischen).
  Sichere Alternative: 2 x 16 GB gleicher Bauart.
- Bedarf (gemessen): Kette bucht 11 GB, ein globaler Mapper-Lauf ~6 GB, FlexGlue-Stufe 2 bucht 4 GB, Fusion will 32 GB Zwischenspeicher (heute Teilfusion als Umweg).
  Zustand 20.11. 15:00: 6,8 GB ausgelagert; Kette, FlexGlue und Sued-Anhang schliessen sich gegenseitig aus; zwei Konsens-Mapper-Laeufe nur nacheinander.
- Mit 32 GB: Kette + ein Messlauf parallel, Mapper-Laeufe parallel. Mit 64 GB zusaetzlich: zwei Objekte gleichzeitig, Fusion ohne Umweg.
- Nach dem Einbau: `free -g`, Schnelltest, RAM-Grenze in `tools/job_start.sh` pruefen (85 % MemTotal rechnet selbst), dann parallele Mapper-Laeufe messen.

## Prozessor (gemessen)
- 16 schnelle Faeden (0-15) + 12 langsame (16-27). Dauerleistung 55 W = Firmware-Obergrenze (`constraint_0`), kurz 130 W.
- 20.11. 15:35, Kette + Auslagern, Last ~16: **Paketleistung 55 W** (10-s-Mittel aus `energy_uj`) -> die 55-W-Grenze greift schon bei Teillast, nicht erst bei 28 Faeden.
- Hitzedrosselung: 15:01-15:19 +1250 Ereignisse = 4,2 s in 18 min (0,4 %); ueber 14 Tage Laufzeit 12 737 s (~1 %). Temperatur 62-84 C, Luefter 6000/6400 U/min.
  -> Kuehlung ist NICHT der Engpass; externer Luefter bringt hoechstens ~1 %.
- NICHT BEWIESEN: dass das Geraet mehr als 55 W Dauer kann. Klaerender Test (offen, ~15 min ohne laufende Kette): Windows starten, OMEN Gaming Hub Leistungsmodus,
  Volllast, Dauer-Watt ablesen. >= 80 W -> Linux fehlt nur der Schalter (dann suchen); ~55 W -> Thema erledigt.
- BIOS-Update: nicht ohne Beleg (kein Hinweis auf hoehere Grenze; Eigenbau-hp-wmi-Modul koennte ausfallen -> Rueckfall auf 25 W).
- Falle 20.11.: Kette lief nur auf den 12 langsamen Kernen (Ursache + Fix im Ast betrieb, `tools/job_start.sh`).

## Platten (gemessen)
- Intern NVMe 477 GB: Root 48 GB (7 frei), scan 100 GB ext4 (15 frei vor dem Auslagern), Volume 193 GB NTFS, Windows 135 GB (95 belegt).
- Extern `/media/oem/rcdaten`: 1,8 TB, USB 3 (5 Gbit/s, uas), 691 GB belegt (38 %).
- Zweiter M.2-Platz: aus `dmidecode -t slot` NICHT ablesbar (nur allgemeine PCIe-Bezeichner, ein x4-Platz J8C1 "Available" - kann der M.2-Platz sein, ANNAHME). Klaerung nur durch Blick unter den Deckel (beim RAM-Einbau mit ansehen).
- Regel (Nutzer 20.11.): intern nur was laufend gebraucht wird (CLAUDE.md Technik).

## Grafikkarte
- 8 GB VRAM, bei ~80 W gedeckelt (`nvidia-smi -pl` wirkungslos, 6.11.). Waehrend des globalen Mappers 0 % Last. Kein Hebel gefunden.

## Rangfolge der Hebel
1. Arbeitsspeicher 2 x 32 GB (siehe oben).
2. Interner Arbeitsplatz: Volume leeren und als ext4 nutzen bzw. zweite M.2 (nur nach Nutzer-Ja).
3. Windows-Test der Dauerleistung.
4. Cloud ohne Kreditkarte (Trooper.ai PayPal/SEPA, vast.ai Krypto) - `tools/cloud/CLOUD_VAST.md`.

## Was kann das Geraet unter Windows? (Recherche 20.11. 15:40)
- Kernel-Bugzilla 219125 "Low performance in a 8C77 HP Omen laptop" (UNSER Board 8C77, dort mit i9-14900HX): Windows Leistungsmodus **PL1 90 W**, ausbalanciert 50 W;
  Ubuntu im Profil performance nur 45 W Dauer. Quelle nur als Suchtreffer-Auszug gelesen (Seite selbst verweigert den Abruf, 403) -> Zahl gilt als HINWEIS, nicht als Messung an unserem Geraet.
- Testberichte mit Dauer-Watt fuer genau die i7-14700HX-Ausfuehrung: keine gefunden.
- hp-wmi-Patch Januar 2026 (Schwesterboard 8C78, ebenfalls 16-wf1xxx): Profilwerte 0x30/0x31 (Omen V1) statt Victus-S - unser Eigenbau nutzt fuer 8C77 schon omen_v1 (README). Der Patch nennt keine Watt-Zahlen
  und meldet "keine sichtbare Aenderung" der Spitzenleistung.
- Grafikkarte: bei OMEN Max 16 ist "GPU haengt bei 80 W unter Linux" bekannt (Nvidia-Forum; dort hilft ein Zusatzmodul omen_wmi_boost) - anderes Board, fuer 8C77 ungeprueft. Bei uns wirkt performance schon (+47 %, CPU_LEISTUNG.md Z.112).

## Test OHNE Windows vorbereitet: Leistungsgrenze per WMI anheben
- Das Modul hat die Firmware-Abfrage 0x29 (`victus_s_set_cpu_pl1_pl2`), ruft sie aber nur mit "Standard" auf. NEU (Eigenzusatz in `tools/hp_wmi_8c77/hp-wmi.c`): Parameter
  `rcpark_pl1`, `rcpark_pl2` (Watt) + `rcpark_pl_anwenden`. Gebaut 20.11. (unsigniert, `/media/oem/scan/rc-park_null/hpwmi_bau/build/hp-wmi.ko`; alter Stand daneben als `hp-wmi.ko.stand_0611`). NOCH NICHT GELADEN.
- Ablauf (Nutzer, sudo; laufende Jobs bleiben am Leben, waehrend des Modulwechsels kurz Standardprofil):
  1. `sudo bash tools/hp_wmi_installieren.sh signieren && sudo bash tools/hp_wmi_installieren.sh laden`, danach `bash tools/hpwmi_pruefen.sh` (muss OK melden, Profil performance).
  2. `echo 70 | sudo tee /sys/module/hp_wmi/parameters/rcpark_pl1; echo 130 | sudo tee /sys/module/hp_wmi/parameters/rcpark_pl2; echo 1 | sudo tee /sys/module/hp_wmi/parameters/rcpark_pl_anwenden`
  3. Messen unter Volllast (Paketleistung aus `energy_uj`, Temperatur, Drosselzaehler) - erst 70 W, dann 90 W. Zurueck: 0 / 0 / anwenden.
- Abbruchregel: Temperatur dauerhaft > 95 C oder Drosselanteil > 5 % -> eine Stufe zurueck. Dann (und nur dann) lohnt ein externer Luefter.
- Unbekannt: ob die Firmware von 8C77 die Abfrage 0x29 annimmt (Victus-S-Befehl; Rueckgabewert steht im Kernellog `rcpark: PL1=... -> <rc>`). Nimmt sie sie nicht an, bleibt der Windows-Test.

## ERGEBNIS Vollgas-Test (20.11.2026 15:37-15:48, Nutzer mit sudo, Logs `job_logs/vollgas_test_1120_1537.log`, `vollgas_test2_1120_1542.log`)
- Test 1 (nur WMI-Befehl 70 W, neues Modul): Firmware nimmt an (rc 0), Paket bleibt 55 W. URSACHE (uebersehen): unser eigener Dienst `cpu_leistung_regler` (MAX=55, MSR) und die MMIO-Grenze standen beide auf 55 W.
- Test 2 (Regler angehalten; WMI + MSR + MMIO gemeinsam gesetzt; Volllast 28 Faeden, je 90 s, Watt = Paketleistung aus energy_uj):
  55 W -> 63 C · **70 W -> 70 C · 90 W -> 79 C · 110 W -> 93 C (gemessen 109 W)**, ueberall 0 % Drosselzeit, Verlauf je 15 s konstant (kein Einbruch nach 30-40 s).
- Damit BEWIESEN: das Geraet kann unter Linux das Doppelte der bisherigen Dauerleistung; die 55-W-Grenze war eine Einstellung (Firmware-MMIO + eigener Regler), keine Hardware-Grenze.
  Der Windows-Test ist dafuer nicht mehr noetig. Offen: welche der drei Stellen wirklich noetig ist (WMI allein reicht nicht; MSR+MMIO ohne WMI nicht getrennt geprueft).
- NICHT gemessen: Dauerbetrieb ueber Stunden (Waermestau), gleichzeitige GPU-Last (gemeinsame Kuehlung), Durchsatzgewinn der Kette (Watt != Tempo; ANNAHME +25-40 % bei Stufen mit vielen Faeden).
- Dauerloesung: `tools/cpu_leistung_regler.sh` setzt jetzt alle drei Stellen; Dienst MAX=100, START=55, hoch bei < 80 C, runter ab 88 C, Notfall 94 C -> 55 W.
  Einspielen: `sudo bash tools/cpu_leistung_installieren.sh`. Gilt nur mit dem neuen hp-wmi-Modul (nach Kernel-Update neu bauen/signieren).
- Kuehlung: ab ~90 W ist die Temperatur die Grenze (79 C bei 90 W, 93 C bei 110 W) -> externer Luefter/Unterlage lohnt JETZT (verschiebt, wo der Regler stehen bleibt). Vorher/nachher am Regler-Zustand `/run/cpu_leistung_regler.state` messbar.

## Nachtraege 20.11. ab 16:00
- Regler im Dauerbetrieb (Kette + Nebenlast): pendelt 60-80 W. Befund: bei WENIGEN Faeden mit vollem Turbo ist die Pakettemperatur (heissester Kern) hoeher als bei Volllast
  auf allen Kernen (16:15: 82 C Mittel bei 50 W Kettenlast; 16:16 Volllast 28 Faeden: 65-68 C Mittel bei 65-74 W, Spitze 84 C). Der Regler nimmt dann die Grenze zurueck,
  obwohl sie gar nicht bindet -> offen: Regel nur anwenden, wenn die Paketleistung nahe der Grenze liegt.
- Externer Luefter seit ca. 16:13 dran: Wirkung NICHT sauber belegt (Kettenlast wechselt). Sauberer Vergleich = `vollgas_test2.sh` erneut (Bezug ohne Luefter 15:43: 63/70/79/93 C bei 55/70/90/110 W).
- OpenBLAS-A/B: kein Gewinn (158 -> 148 s CPU, GPU-Loeser 33 s), siehe Ast betrieb. Globaler Mapper: Gesamtausgleich je Runde ~2,5 min statt 6,5 min (alle Kerne + mehr Leistung).
- zswap an (zstd). Grosse Speicherseiten (THP always): noch nicht getestet.

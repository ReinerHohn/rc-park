# hp-wmi mit Unterstuetzung fuer OMEN 16-wf1xxx (Board 8C77)
Quelle: Linux-Stabilzweig 6.18.y `drivers/platform/x86/hp/hp-wmi.c` (GPL-2.0) + EINE Tabellenzeile fuer "8C77" (omen_v1_thermal_params), wie der Upstream-Patch
"platform/x86: hp-wmi: Add support for Omen 16-wf1xxx (8C77)" (Commit 344bf523, in Linux 7.1 gemerged, fuer 6.18-7.0 als Stable-Backport vorgeschlagen). Im Kernel 6.17 OEM fehlt das ->
kein `platform_profile`, Firmware bleibt im Standardprofil (CPU ~25 W). Siehe modelle/CPU_LEISTUNG.md Abschnitt 6.
Bauen/Installieren: tools/hp_wmi_installieren.sh (Phasen bauen | signieren | laden | zurueck). Nach JEDEM Kernel-Update neu bauen und neu signieren (Modul ist an die Kernelversion gebunden).

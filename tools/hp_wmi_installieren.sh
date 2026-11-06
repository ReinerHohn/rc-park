#!/bin/bash
# hp_wmi_installieren.sh - hp-wmi-Treiber mit Board 8C77 (OMEN 16-wf1xxx) bauen, fuer Secure Boot signieren und laden. Ziel: Linux bekommt das Plattformprofil
# (/sys/class/platform-profile/*), mit dem die Firmware in den Leistungsmodus geht (wie die OMEN-Software unter Windows). Hintergrund: tools/hp_wmi_8c77/README.md.
#   bash   tools/hp_wmi_installieren.sh bauen        (OHNE Root: Kernel-Header laden/entpacken, Modul bauen)         -> $ARB/build/hp-wmi.ko
#   sudo   tools/hp_wmi_installieren.sh signieren    (Modul mit MOK-Schluessel signieren + Schluessel zur Aufnahme vormerken: fragt ein EINMAL-Passwort)
#          -> NEUSTART, im blauen MOK-Bildschirm "Enroll MOK" -> Continue -> Yes -> Passwort -> Reboot   (einmalig; Schluessel ist dann dauerhaft eingetragen)
#   sudo   tools/hp_wmi_installieren.sh laden        (nach dem Neustart: Modul nach /lib/modules/<kernel>/updates/ installieren, depmod, hp_wmi neu laden, Profil anzeigen)
#   sudo   tools/hp_wmi_installieren.sh zurueck      (entfernt unser Modul, Original-hp_wmi wird wieder geladen)
set -u; export LC_ALL=C
K=$(uname -r); R=$(cd "$(dirname "$0")/.." && pwd); SRC=$R/tools/hp_wmi_8c77; ARB=${ARB:-/media/oem/scan/rc-park_null/hpwmi_bau}
MOKD=/var/lib/shim-signed/mok/MOK.der; MOKP=/var/lib/shim-signed/mok/MOK.priv
phase=${1:-}
case "$phase" in
bauen)
  mkdir -p $ARB/deb $ARB/root $ARB/build && cd $ARB/deb
  apt-get download linux-headers-$K 2>&1 | tail -1
  COMMON=$(dpkg-deb -f linux-headers-$K*.deb Depends | tr ',' '\n' | grep -o "linux-oem-[0-9.]*-headers-[0-9.-]*" | head -1); [ -n "$COMMON" ] && apt-get download $COMMON 2>&1 | tail -1
  for d in *.deb; do dpkg -x "$d" $ARB/root; done
  cp $SRC/hp-wmi.c $SRC/Makefile $ARB/build/ && cd $ARB/build
  make -C $ARB/root/usr/src/linux-headers-$K M=$PWD modules 2>&1 | tail -4
  modinfo ./hp-wmi.ko | grep -E "vermagic|depends"; echo "fertig: $ARB/build/hp-wmi.ko";;
signieren)
  [ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
  [ -f $ARB/build/hp-wmi.ko ] || { echo "erst 'bauen'"; exit 1; }
  [ -f $MOKP ] || { echo "kein MOK-Schluessel ($MOKP)"; exit 1; }
  kmodsign sha512 $MOKP $MOKD $ARB/build/hp-wmi.ko && echo "Modul signiert"
  if mokutil --test-key $MOKD 2>&1 | grep -q "is already enrolled"; then echo "Schluessel ist schon eingetragen -> direkt 'laden'"; else
    echo; echo "Schluessel wird vorgemerkt. Gleich nach der Passwort-Abfrage NEUSTARTEN und im blauen MOK-Bildschirm bestaetigen (Enroll MOK -> Continue -> Yes -> Passwort -> Reboot)."
    mokutil --import $MOKD
  fi;;
laden)
  [ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
  if mokutil --sb-state 2>&1 | grep -qi "SecureBoot enabled"; then
    mokutil --test-key $MOKD 2>&1 | grep -q "is already enrolled" || { echo "Secure Boot AN und Schluessel noch NICHT eingetragen (Neustart + MOK-Bestaetigung fehlt; oder Secure Boot im BIOS ausschalten)"; exit 1; }
  else echo "Secure Boot ist aus -> keine Signatur noetig"; fi
  mkdir -p /lib/modules/$K/updates && cp $ARB/build/hp-wmi.ko /lib/modules/$K/updates/hp-wmi.ko && depmod -a
  modprobe -r hp_bioscfg 2>/dev/null; modprobe -r hp_wmi 2>&1 | head -1; modprobe hp_wmi 2>&1 | head -2; modprobe hp_bioscfg 2>/dev/null
  modinfo hp_wmi | grep -E "^filename|signer" | cut -c1-110
  for d in /sys/class/platform-profile/*; do echo "$d: name=$(cat $d/name) profile=$(cat $d/profile) choices=$(cat $d/choices | tr '\n' ' ')"; done
  echo "Profil setzen:  echo performance | sudo tee /sys/class/platform-profile/platform-profile-0/profile   (Name pruefen!), danach: sudo bash tools/leistung_diagnose.sh 60 45";;
zurueck)
  [ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
  rm -f /lib/modules/$K/updates/hp-wmi.ko; depmod -a; modprobe -r hp_wmi 2>/dev/null; modprobe hp_wmi; echo "Original-Treiber wieder aktiv: $(modinfo hp_wmi | grep ^filename)";;
*) sed -n 2,12p "$0";;
esac

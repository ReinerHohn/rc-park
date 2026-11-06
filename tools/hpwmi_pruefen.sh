#!/bin/bash
# hpwmi_pruefen.sh - ist das selbstgebaute hp-wmi-Modul (Board 8C77, Profil performance) noch da? Kein Root noetig.
#   bash tools/hpwmi_pruefen.sh      Exit 0 = alles ok, 1 = ACHTUNG (Text sagt was zu tun ist)
# Aufruf: zu JEDEM Sitzungsbeginn / nach Neustart / nach Kernel-Update (steht in CLAUDE.md); auch von leistung_ab.sh.
# Hintergrund: modelle/CPU_LEISTUNG.md Abschnitt 6. Das Modul gilt nur fuer EINEN Kernel (vermagic) - nach Kernel-Update ist es weg.
export LC_ALL=C; K=$(uname -r); PP=/sys/class/platform-profile/platform-profile-0; F=0
warn() { echo "ACHTUNG KERNEL-MODUL: $*"; F=1; }
# 1) Mainline-Kernel kennt das Board schon? Dann Eigenbau unnoetig (zurueck: sudo tools/hp_wmi_installieren.sh zurueck)
ST=$(ls /lib/modules/$K/kernel/drivers/platform/x86/hp/hp-wmi.ko* 2>/dev/null | head -1)
if [ -n "$ST" ]; then
  case "$ST" in *.zst) CAT="zstd -dc";; *.xz) CAT="xz -dc";; *.gz) CAT="gzip -dc";; *) CAT=cat;; esac
  if $CAT "$ST" 2>/dev/null | grep -aq 8C77; then echo "HINWEIS: Der mitgelieferte Kernel $K kennt das Board 8C77 schon -> Eigenbau-Modul kann weg (sudo tools/hp_wmi_installieren.sh zurueck), Profil kommt dann vom Kernel."; fi
fi
# 2) Eigenbau-Modul fuer den LAUFENDEN Kernel vorhanden?
U=/lib/modules/$K/updates/hp-wmi.ko
if [ ! -e $U ] && ! ls $U.* >/dev/null 2>&1; then warn "kein Eigenbau-Modul fuer Kernel $K (Kernel-Update?). Neu bauen: tools/hp_wmi_installieren.sh bauen, signieren, laden (sudo selbst)."
else
  VM=$(modinfo -F vermagic hp-wmi 2>/dev/null | awk '{print $1}')
  [ "$VM" = "$K" ] || warn "Modul-vermagic '$VM' passt nicht zum Kernel $K."
fi
# 3) geladen und Profil da?
lsmod | grep -q '^hp_wmi' || warn "hp_wmi nicht geladen (sudo tools/hp_wmi_installieren.sh laden)."
if [ -r $PP/profile ]; then echo "Profil: $(cat $PP/profile)  (Auswahl: $(cat $PP/choices))"; else warn "kein platform-profile -> Modul fehlt/laedt nicht; CPU bremst wieder auf ~38 W."; fi
# 4) neuerer Kernel installiert als der laufende? (naechster Start -> Modul fehlt)
N=$(ls /lib/modules | grep '^[0-9]' | sort -V | tail -1); [ "$N" != "$K" ] && echo "HINWEIS: neuerer Kernel $N installiert - fuer ihn Modul bauen+signieren, bevor du dorthin neu startest (oder pruefen, ob er 8C77 selbst kennt)."
# 5) MOK-Schluessel noch eingetragen? (Signer des Moduls)
S=$(modinfo -F signer hp-wmi 2>/dev/null); [ -n "$S" ] && { mokutil --list-enrolled 2>/dev/null | grep -q "Subject: CN=$S" || warn "Signer-Schluessel '$S' nicht in der MOK-Liste (mokutil --import noetig)."; }
[ $F = 0 ] && echo "hp-wmi-Modul: OK" || echo "-> Details: modelle/CPU_LEISTUNG.md Abschnitt 6"
exit $F

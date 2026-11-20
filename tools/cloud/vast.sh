#!/bin/bash
# vast.sh - Rechenjobs der Kette auf einer gemieteten vast.ai-Maschine (GPU/RAM/CPU waehlbar) statt auf dem Laptop.
# Prinzip: Die Cloud-Maschine bekommt DIESELBEN absoluten Pfade wie hier (/home/oem/git/rc-park, /media/oem/scan/venv-*, Datenordner),
# damit kein Werkzeug umgeschrieben werden muss. Claude/Generator/Abnahme bleiben lokal; nur lange Jobs laufen dort.
# Kostenregel: Abrechnung je Sekunde, solange die Instanz EXISTIERT (auch gestoppt: Speicher). Nach dem Holen immer `ende`.
# Anleitung, Kosten, Grenzen: tools/cloud/CLOUD_VAST.md
#
# Befehle:
#   vast.sh pruefen                      CLI + API-Schluessel da? Guthaben
#   vast.sh suchen [GPU] [RAM_GB]        guenstigste passende Angebote (Standard: RTX 4090, 64 GB RAM, CUDA>=13.2, verlaesslich)
#   vast.sh mieten ANGEBOT_ID [STUNDEN] [DISK_GB]  Instanz anlegen (Guthaben-Pruefung, fragt nach, zerstoert sich nach STUNDEN; Std. 4 h, 120 GB)
#   vast.sh verlaengern INST STUNDEN     Selbstzerstoerung auf STUNDEN ab jetzt verschieben
#   vast.sh einrichten INST              Repo hochladen + Umgebung bauen (tools/cloud/einrichten_remote.sh, einmalig ~30-60 min)
#   vast.sh hoch INST PFAD...            Datenordner an DENSELBEN absoluten Pfad hochladen (Symlinks werden aufgeloest)
#   vast.sh job INST NAME "BEFEHL"       Befehl dort im Repo starten (nohup, Log /media/oem/scan/rc-park_daten/job_logs/NAME.log)
#   vast.sh log INST NAME                letzte Logzeilen + JOB_ENDE?
#   vast.sh holen INST PFAD...           Ergebnisordner zurueck an denselben Pfad (rsync, ueberschreibt nur Neueres)
#   vast.sh kosten                       laufende Instanzen mit $/h und bisheriger Laufzeit
#   vast.sh ende INST                    Instanz ZERSTOEREN (Daten dort weg; vorher holen!)
#   vast.sh fertig INST PFAD...          Ergebnisse holen und NUR bei Erfolg die Instanz zerstoeren (Normalfall nach jedem Lauf)
#   vast.sh aufraeumen [--ja]            alle Instanzen (auch gestoppte = Speicherkosten) und Volumes zeigen und loeschen -> 0 $ laufende Kosten
set -euo pipefail
V="${VASTAI:-$HOME/.venvs/vast/bin/vastai}"
REPO=/home/oem/git/rc-park
HIER="$(cd "$(dirname "$0")" && pwd)"
IMAGE="${VAST_IMAGE:-nvidia/cuda:13.0.1-cudnn-devel-ubuntu24.04}"   # ANNAHME: Tag existiert; sonst VAST_IMAGE setzen (devel noetig fuer COLMAP-Bau)

[ -x "$V" ] || { echo "vastai-CLI fehlt: python3 -m venv ~/.venvs/vast && ~/.venvs/vast/bin/pip install vastai"; exit 2; }

ssh_ziel() {  # INST -> "user@host port"
  local url; url=$("$V" ssh-url "$1" 2>/dev/null | tail -1)   # ssh://root@1.2.3.4:12345
  [[ "$url" =~ ssh://([^@]+)@([^:]+):([0-9]+) ]] || { echo "keine SSH-Adresse fuer Instanz $1 (laeuft sie schon?)" >&2; exit 3; }
  echo "${BASH_REMATCH[1]}@${BASH_REMATCH[2]} ${BASH_REMATCH[3]}"
}
rssh() { local z p; read -r z p < <(ssh_ziel "$1"); shift; ssh -o StrictHostKeyChecking=accept-new -p "$p" "$z" "$@"; }
rsync_hin() {  # INST QUELLE... (gleiche absolute Pfade; -L loest Symlinks auf, -R behaelt Pfad)
  local i="$1"; shift; local z p; read -r z p < <(ssh_ziel "$i")
  rsync -aLR --info=progress2 --partial -e "ssh -o StrictHostKeyChecking=accept-new -p $p" "$@" "$z:/"
}

cmd="${1:-}"; shift || true
case "$cmd" in
  pruefen)
    "$V" show user --raw 2>/dev/null | python3 -c "import json,sys;u=json.load(sys.stdin);print('Konto ok, Guthaben $%.2f'%u.get('credit',0))" \
      || echo "Kein API-Schluessel: auf cloud.vast.ai -> Account -> API Keys erzeugen, dann: $V set api-key <SCHLUESSEL>"
    ls ~/.ssh/id_*.pub >/dev/null 2>&1 && echo "SSH-Schluessel vorhanden (einmalig: $V create ssh-key \"\$(cat ~/.ssh/id_ed25519.pub)\")" \
      || echo "kein SSH-Schluessel: ssh-keygen -t ed25519";;
  suchen)
    GPU="${1:-RTX 4090}"; RAM="${2:-64}"
    "$V" search offers "num_gpus=1 gpu_name=\"$GPU\" cpu_ram>=$RAM cpu_cores_effective>=16 cuda_vers>=13.2 reliability>0.98 disk_space>=150 inet_down>=200 direct_port_count>=1 rentable=true" \
      -o 'dph_total' --no-color 2>&1 | head -15;;
  mieten)
    # KOSTENBREMSE (Nutzer 20.11.): (1) Guthaben muss fuer STUNDEN x Preis (+10 % und Speicher) reichen, sonst Abbruch;
    # (2) einmaliger Zeitgeber (systemd-run, kein wiederkehrender Check) ZERSTOERT die Instanz nach STUNDEN; `verlaengern` setzt ihn neu.
    # Grenze: der Zeitgeber laeuft auf DIESEM Rechner - ist er aus, greift nur noch das Guthaben (bei 0 $ stoppt vast.ai die Instanz).
    ID="${1:?ANGEBOT_ID aus suchen}"; H="${2:-4}"; DISK="${3:-120}"
    # Preis je Angebot: CLI 'search offers id=...' findet nichts (getestet 20.11.), die API-Abfrage ueber ask_contract_id schon.
    read -r PREIS SPEICHER < <(curl -s -m 30 -G "https://console.vast.ai/api/v0/bundles/" --data-urlencode "q={\"ask_contract_id\":{\"eq\":$ID}}" \
      | python3 -c "import json,sys;o=json.load(sys.stdin).get('offers',[]);o=o[0] if o else {};print(o.get('dph_total',0),o.get('storage_cost') or 0.3)")
    [ "$PREIS" != 0 ] || { echo "Angebot $ID nicht (mehr) verfuegbar"; exit 2; }
    GUTHABEN=$("$V" show user --raw 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('credit',0))" 2>/dev/null) \
      || { echo "Preis $PREIS \$/h - aber kein API-Schluessel/Guthaben lesbar (vast.sh pruefen). Abbruch."; exit 4; }
    BEDARF=$(python3 -c "print(round($PREIS*$H*1.1 + $DISK*$SPEICHER/730*$H, 2))")
    echo "Preis $PREIS \$/h, Speicher $SPEICHER \$/GB/Monat, $H h => Bedarf ~$BEDARF \$, Guthaben $GUTHABEN \$"
    python3 -c "import sys;sys.exit(0 if $GUTHABEN >= $BEDARF else 1)" || { echo "KOSTENBREMSE: Guthaben reicht nicht fuer $H h - weniger Stunden oder aufladen."; exit 4; }
    read -r -p "Instanz anlegen, Selbstzerstoerung nach $H h? Ab jetzt kostet es je Sekunde. [ja/nein] " a; [ "$a" = ja ] || exit 1
    INST=$("$V" create instance "$ID" --image "$IMAGE" --disk "$DISK" --ssh --direct --label rcpark --raw \
      --onstart-cmd "apt-get update -qq && apt-get install -y -qq rsync git python3-venv >/dev/null" \
      | python3 -c "import json,sys;print(json.load(sys.stdin)['new_contract'])")
    systemd-run --user --quiet --on-active="${H}h" --unit="rcpark-vast-ende-$INST" bash "$HIER/vast.sh" ende "$INST" --ja
    echo "Instanz $INST angelegt; Selbstzerstoerung $(date -d "+$H hour" +%H:%M) (vast.sh verlaengern $INST STUNDEN). Status 'running' abwarten, dann: vast.sh einrichten $INST";;
  verlaengern)
    I="${1:?INST}"; H="${2:?STUNDEN ab jetzt}"
    systemctl --user stop "rcpark-vast-ende-$I.timer" 2>/dev/null || true
    systemd-run --user --quiet --on-active="${H}h" --unit="rcpark-vast-ende-$I" bash "$HIER/vast.sh" ende "$I" --ja
    echo "Selbstzerstoerung von $I jetzt $(date -d "+$H hour" +%H:%M)";;
  einrichten)
    I="${1:?INST}"
    rssh "$I" "mkdir -p $REPO /media/oem/scan/rc-park_daten/job_logs /home/oem/.venvs"
    z_p=$(ssh_ziel "$I"); read -r z p <<<"$z_p"
    # Nur von git verfolgte Dateien (keine .git, keine ignorierten Dateien mit Zugangsdaten, keine Rohdaten); Daten gezielt per `hoch`.
    # Symlinks bleiben Symlinks (zeigen auf dieselben absoluten Pfade, die `hoch` dort anlegt).
    git -C "$REPO" ls-files -z | rsync -a --from0 --files-from=- --info=progress2 \
      -e "ssh -o StrictHostKeyChecking=accept-new -p $p" "$REPO/" "$z:$REPO/"
    rssh "$I" "bash $REPO/tools/cloud/einrichten_remote.sh 2>&1 | tee /media/oem/scan/rc-park_daten/job_logs/einrichten.log | tail -25";;
  hoch)
    I="${1:?INST}"; shift; [ $# -gt 0 ] || { echo "Pfade angeben"; exit 2; }
    for q in "$@"; do du -shL "$q" 2>/dev/null | tail -1; done
    rsync_hin "$I" "$@";;
  job)
    I="${1:?INST}"; N="${2:?NAME}"; B="${3:?BEFEHL}"; L=/media/oem/scan/rc-park_daten/job_logs/$N.log
    rssh "$I" "cd $REPO && export HOME=/home/oem && nohup bash -c $(printf %q "$B > $L 2>&1; echo JOB_ENDE rc=\$? >> $L") >/dev/null 2>&1 & echo gestartet: $N, Log $L";;
  log)
    I="${1:?INST}"; N="${2:?NAME}"; rssh "$I" "tail -n 15 /media/oem/scan/rc-park_daten/job_logs/$N.log | cut -c1-200";;
  holen)
    I="${1:?INST}"; shift; read -r z p < <(ssh_ziel "$I")
    for q in "$@"; do rsync -a -u --info=progress2 -e "ssh -o StrictHostKeyChecking=accept-new -p $p" "$z:$q/" "$q/"; done;;
  kosten)
    "$V" show instances --raw | python3 -c "
import json,sys,time
for i in json.load(sys.stdin):
    h=(time.time()-(i.get('start_date') or time.time()))/3600; d=i.get('dph_total',0)
    print(i['id'], i.get('gpu_name'), i.get('actual_status'), '%.3f \$/h'%d, '%.1f h'%h, '~\$%.2f bisher'%(h*d), i.get('label') or '')";;
  ende)
    I="${1:?INST}"
    if [ "${2:-}" != "--ja" ]; then read -r -p "Instanz $I ZERSTOEREN (alle Daten dort weg)? [ja/nein] " a; [ "$a" = ja ] || exit 1; fi
    "$V" destroy instance "$I" && echo "$(date +%FT%T) Instanz $I zerstoert" >> /media/oem/scan/rc-park_daten/job_logs/vast.log
    systemctl --user stop "rcpark-vast-ende-$I.timer" 2>/dev/null || true;;
  fertig)
    # Ergebnisse holen, NUR wenn das Holen klappt: Instanz zerstoeren (damit auch keine Speicherkosten mehr laufen).
    I="${1:?INST}"; shift; [ $# -gt 0 ] || { echo "Ergebnispfade angeben"; exit 2; }
    "$0" holen "$I" "$@" && "$0" ende "$I" --ja || { echo "Holen fehlgeschlagen - Instanz $I bleibt bestehen (Daten sicher), Fehler pruefen"; exit 5; };;
  aufraeumen)
    # Alles, was noch Geld kostet: Instanzen (laufend ODER gestoppt = Speicherkosten) und Volumes. Zeigt erst, dann eine Rueckfrage (--ja: ohne).
    "$V" show user --raw >/dev/null 2>&1 || { echo "kein API-Schluessel (vast.sh pruefen) - kann nicht aufraeumen"; exit 4; }
    "$V" show instances --raw | python3 -c "
import json,sys
for i in json.load(sys.stdin): print('Instanz',i['id'],i.get('actual_status'),i.get('label') or '','%.3f \$/h'%(i.get('dph_total') or 0))" | tee /tmp/vast_reste.$$
    "$V" show volumes --raw 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); d=d.get('volumes',d) if isinstance(d,dict) else d
for v in d or []: print('Volume',v.get('id'),v.get('disk_space') or v.get('size'),'GB')" | tee -a /tmp/vast_reste.$$ || true
    [ -s /tmp/vast_reste.$$ ] || { echo "Nichts mehr gemietet - es laufen keine Kosten."; rm -f /tmp/vast_reste.$$; exit 0; }
    if [ "${1:-}" != "--ja" ]; then read -r -p "ALLES oben zerstoeren/loeschen (Daten dort weg)? [ja/nein] " a; [ "$a" = ja ] || exit 1; fi
    while read -r art id _; do
      case "$art" in Instanz) "$0" ende "$id" --ja;; Volume) "$V" delete volume "$id";; esac
    done < /tmp/vast_reste.$$; rm -f /tmp/vast_reste.$$
    sleep 5; echo "Kontrolle (muss leer sein):"; "$V" show instances --raw | python3 -c "import json,sys;print(len(json.load(sys.stdin)),'Instanzen uebrig')";;
  *) sed -n '2,22p' "$0"; exit 2;;
esac

#!/usr/bin/env bash
# Kantengitter-Kette (Nutzerregel 9.11.: alles automatisch, kein manuelles Zusammenstecken). Ein Aufruf, ein Log, feste Reihenfolge:
#  1 sweep      Tiefen-Sweep A (Aufbau) und B (unabhaengige Pruefmenge, andere Referenzfotos), Basis nach Tiefenaufloesung (--dz)
#  2 konsens    B-Konsens (>= 3 Refs je 8-cm-Voxel) als Pruefreferenz
#  3 aufbau     RANSAC-Gitter aus A (zwei Hoehenbaender, qe-Ausgleich)
#  4 schleife   Foto-Schleife (Stabilitaetskarten) auf dem Gitter
#  5 formen     Helme (helm_fit) + Pfeiler (saeulen_fit) als Formfamilien
#  6 wiederh    Wiederholungs-Prior (Periode/Musterzelle, Fotopruefung)
#  7 spiegel    Spiegel-Prior (Gebaeudesymmetrie, Fotopruefung)
#  8 zusammen   Zusammenfuehren (Doppelte raus: Kopien nur, wenn nicht schon im Gitter)
#  9 messen     gitter_naehe gegen Wolkenkanten UND B-Konsens; Pruefblatt ueber alle Fotos mit Z-Puffer
# 10 zeigen     Viewer-HTML bauen, Editor neu starten
# Aufruf: tools/gitter_kette.sh NAME [--ab STUFE] [--kam KAM.json] [--bilder DIR] [--refs 220] [--vmin 0.6] [--maxpx 80000]
#   Ergebnis: <DATEN>/kette_<NAME>/ (alle Zwischendateien), Gitter = kette_<NAME>/gitter.json, Bericht kette_<NAME>/bericht.txt
# Lange Laufzeit -> ueber tools/job_start.sh starten: JOB_GPU_MB=4500 tools/job_start.sh kette_NAME LOG tools/gitter_kette.sh NAME
set -u
cd "$(dirname "$0")/.."
PY=/media/oem/scan/venv-seg/bin/python; D=/media/oem/scan/rc-park_daten/kaufhaus_alle
NAME=${1:?NAME}; shift
AB=sweep; KAM=$D/sfm/kam_lot2.json; BILDER=$D/bilder; REFS=220; VMIN=0.6; MAXPX=80000; REFPREFIX=""
while [ $# -gt 0 ]; do case "$1" in
  --ab) AB=$2; shift 2;; --kam) KAM=$2; shift 2;; --bilder) BILDER=$2; shift 2;; --refs) REFS=$2; shift 2;; --vmin) VMIN=$2; shift 2;; --maxpx) MAXPX=$2; shift 2;; --ref_prefix) REFPREFIX=$2; shift 2;; *) echo "unbekannt $1"; exit 2;; esac; done
K=$D/kette_$NAME; mkdir -p "$K" modelle/kaufhaus_grob3/audit/kette_$NAME; B=$K/bericht.txt; AUD=modelle/kaufhaus_grob3/audit/kette_$NAME
STUFEN="sweep konsens aufbau schleife formen wiederh spiegel zusammen messen zeigen"; los=0
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$B"; }
stufe(){ [ "$1" = "$AB" ] && los=1; [ $los -eq 1 ]; }
WOLKE=$D/ref_wolke_kanten.npy; STAB=$D/stabil; FOTOS80=$D/sam3d_k80.npz; MASKEN=$D/sam3d_mf_kachel; KZ=$D/kanten3d_sweep.npz
log "Kette $NAME ab Stufe $AB (KAM $KAM, Refs $REFS, vmin $VMIN)"

if stufe sweep; then
  PREF=""; [ -n "$REFPREFIX" ] && PREF="--ref_prefix $REFPREFIX"
  log "1 sweep A"; $PY -I tools/kanten_tiefe_sweep.py "$KAM" $STAB $K/sweep_A.npz --refs $REFS --maxpx $MAXPX --nb 14 --dz 0.08 --box $WOLKE --dmax_ref 35 --vmin $VMIN $PREF >> $K/sweep_A.log 2>&1 || { log "FEHLER sweep A"; exit 1; }
  # B = unabhaengige Pruefmenge: andere Referenzfotos; bei Praefix-Lauf (z.B. nur Videoframes) sind die FOTOS die Pruefmenge
  if [ -n "$REFPREFIX" ]; then BARGS="--refs 220 --exclude $K/sweep_A.npz"; else BARGS="--refs $REFS --exclude $K/sweep_A.npz"; fi
  log "1 sweep B"; $PY -I tools/kanten_tiefe_sweep.py "$KAM" $STAB $K/sweep_B.npz $BARGS --maxpx $MAXPX --nb 14 --dz 0.08 --box $WOLKE --dmax_ref 35 --vmin $VMIN >> $K/sweep_B.log 2>&1 || { log "FEHLER sweep B"; exit 1; }
  log "   A: $(grep fertig $K/sweep_A.log | tail -1)  B: $(grep fertig $K/sweep_B.log | tail -1)"
fi
if stufe konsens; then
  log "2 konsens B"; $PY -I - "$K" <<'EOF' >> $B 2>&1
import numpy as np, sys; K = sys.argv[1]; Z = np.load(K + "/sweep_B.npz"); P = Z["P"]; r = Z["ref"]
v = np.floor(P / 0.08).astype(np.int64); key = v[:, 0] * 1000003 * 1000003 + v[:, 1] * 1000003 + v[:, 2]
o = np.lexsort((r, key)); k = key[o]; rr = r[o]; new = np.r_[True, (k[1:] != k[:-1]) | (rr[1:] != rr[:-1])]; u, cnt = np.unique(k[new], return_counts=True)
Q = P[np.isin(key, u[cnt >= 3])]; Q = Q[np.unique(np.floor(Q / 0.08).astype(np.int64), axis=0, return_index=True)[1]]; np.save(K + "/konsens_B.npy", Q.astype(np.float32)); print("   B-Konsens", len(Q))
EOF
fi
if stufe aufbau; then
  log "3 aufbau"; $PY -I tools/gitter_aufbauen.py $K/sweep_A.npz $WOLKE $K/g1_aufbau.json --qe 0.003 --tol_o 0.10 --vo 0.05 --minpts_o 5 --minlen_o 0.6 >> $K/aufbau.log 2>&1 || { log "FEHLER aufbau"; exit 1; }
  log "   $(grep fertig $K/aufbau.log | tail -1)"
fi
if stufe schleife; then
  log "4 schleife"; $PY -I tools/kanten_schleife.py "$KAM" $KZ $FOTOS80 $MASKEN $BILDER $K/g1_aufbau.json $K/g2_schleife.json $AUD/schleife --stabil $STAB --iter 4 >> $K/schleife.log 2>&1 || { log "FEHLER schleife"; exit 1; }
  log "   $(grep '^Durchgang 4' $K/schleife.log | cut -c1-140)"
fi
if stufe formen; then
  log "5 formen: Helme"; $PY -I tools/helm_fit.py $K/sweep_A.npz $K/helme.json --kam "$KAM" --stabil $STAB >> $K/formen.log 2>&1 || log "   helm_fit ohne Ergebnis"
  log "5 formen: Pfeiler"; $PY -I tools/saeulen_fit.py $D/kanten3d_k80.npz $K/g2_schleife.json $K/g3_formen.json --mind 8 --zmin 3.0 --zmax 6.0 --rmin 0.25 --rmax 0.9 >> $K/formen.log 2>&1 || cp $K/g2_schleife.json $K/g3_formen.json
  $PY -I - "$K" <<'EOF' >> $B 2>&1
import json, sys, os; K = sys.argv[1]; S = json.load(open(K + "/g3_formen.json"))
if os.path.exists(K + "/helme.json"): H = json.load(open(K + "/helme.json")); S["segmente"] += H["segmente"]; S["helme"] = H["helme"]; print("   Helme", len(H["helme"]))
print("   Pfeiler", len(S.get("saeulen", [])), "Segmente", len(S["segmente"])); json.dump(S, open(K + "/g3_formen.json", "w"))
EOF
fi
if stufe wiederh; then
  log "6 wiederholung"; $PY -I tools/gitter_wiederholung.py $K/sweep_A.npz "$KAM" $STAB $K/g3_formen.json $K/g4_wiederh.json >> $K/wiederh.log 2>&1 || { log "   wiederholung fehlgeschlagen, uebernehme g3"; cp $K/g3_formen.json $K/g4_wiederh.json; }
  log "   $(grep '^neu' $K/wiederh.log | tail -1)"
fi
if stufe spiegel; then
  log "7 spiegel"; $PY -I tools/gitter_spiegel.py $K/sweep_A.npz "$KAM" $STAB $K/g4_wiederh.json $K/g5_spiegel.json >> $K/spiegel.log 2>&1 || { log "   spiegel fehlgeschlagen, uebernehme g4"; cp $K/g4_wiederh.json $K/g5_spiegel.json; }
  log "   $(grep '^neu' $K/spiegel.log | tail -1)"
fi
if stufe zusammen; then
  log "8 zusammen (Doppelte raus)"; $PY -I - "$K" <<'EOF' >> $B 2>&1
import json, sys, numpy as np; sys.path.insert(0, "tools"); from gpu_knn import min_abstand; K = sys.argv[1]
f = lambda Q, X: (lambda d: np.asarray(d.cpu() if hasattr(d, "cpu") else d))(min_abstand(Q, X))
S = json.load(open(K + "/g5_spiegel.json")); seg = S["segmente"]; basis = [s for s in seg if s[2] not in (5, 6)]; kop = [s for s in seg if s[2] in (5, 6)]
def pts(s, st=0.05):
    a = np.array(s[0]); b = np.array(s[1]); n = max(2, int(np.linalg.norm(b - a) / st)); return a + (b - a) * np.linspace(0, 1, n)[:, None]
if kop:
    BP = np.vstack([pts(s) for s in basis]).astype(np.float32); keep = []
    for s in kop:
        d = f(pts(s).astype(np.float32), BP); keep.append((d < 0.08).mean() < 0.6)
    kop = [s for s, k in zip(kop, keep) if k]
S["segmente"] = basis + kop; json.dump(S, open(K + "/gitter.json", "w")); print("   Basis", len(basis), "Kopien behalten", len(kop), "Gitter", len(S["segmente"]))
EOF
fi
if stufe messen; then
  log "9 messen"; { echo "== Wolkenkanten"; $PY -I tools/gitter_naehe.py $K/gitter.json $WOLKE | tail -3; echo "== B-Konsens (unabhaengig)"; $PY -I tools/gitter_naehe.py $K/gitter.json $K/konsens_B.npy | tail -3; } 2>&1 | tee -a $B
  $PY -I tools/gitter_pruefblatt.py "$KAM" $STAB $BILDER $K/gitter.json $AUD/pruefblatt.jpg --k 12 --wolke $D/kanten3d_k80.npz 2>&1 | head -1 | tee -a $B
fi
if stufe zeigen; then
  log "10 zeigen"; $PY -I tools/viewer_kanten_bauen.py modelle/kaufhaus_grob3/viewer_kanten.html --seg $K/gitter.json --kp $K/konsens_B.npy >> $K/zeigen.log 2>&1 && log "   Viewer gebaut"
  systemctl --user stop rcpark-editordraht.service 2>/dev/null; sleep 1; rm -f modelle/kaufhaus_grob3/draht_kanten.json
  tools/job_start.sh editordraht /tmp/editordraht.log $PY -I tools/editor_draht.py "$KAM" $BILDER $D/kanten3d_k80.npz $K/gitter.json modelle/kaufhaus_grob3/draht_kanten.json >/dev/null 2>&1; log "   Editor neu gestartet mit $K/gitter.json"
fi
log "Kette $NAME fertig"

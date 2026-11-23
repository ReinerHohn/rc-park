#!/bin/bash
# Bauen UND abnehmen - fuer JEDES Objekt mit modelle/<objekt>/objekt.json. Bricht bei Pruefstand-Fehler ab.
#   tools/bauen_abnehmen.sh martinstor          -> Generator aus objekt.json, dann tools/pruefstand.py, dann tools/seiten_audit.py (Sichtblatt)
#   tools/bauen_abnehmen.sh martinstor --nur-pruefen
# Danach zeigen/committen/Viewer NUR bei "alle Pruefungen bestanden" UND nachdem das Sichtblatt angesehen wurde (Lehre F5/F6).
# RCPARK_KURZ=1 (20.11.2026, Kontext sparen): volle Ausgabe ins Log, auf dem Bildschirm nur Befunde + Summenzeile "ABNAHME <obj> rc=.. log=..".
if [ "${RCPARK_KURZ:-0}" = "1" ] && [ -z "${_BA_INNEN:-}" ]; then
  L=/media/oem/scan/rc-park_daten/job_logs/abnahme_$1.log; _BA_INNEN=1 RCPARK_KURZ=0 bash "$0" "$@" > "$L" 2>&1; R=$?
  grep -E 'bestanden|ACHTUNG|FEHLGESCHLAGEN|ABBRUCH|FEHLER|nicht erfuellt' "$L" | tail -10 | cut -c1-200; echo "ABNAHME $1 rc=$R log=$L"; exit $R
fi
set -e
cd "$(dirname "$0")/.."
python3 tools/platz_pruefen.py || exit 3   # Platztor (G1)
OBJ="modelle/$1/objekt.json"; [ -f "$OBJ" ] || { echo "kein $OBJ"; exit 2; }
exec 8>"/tmp/rcpark_bau_$1.lock"; flock -n 8 || { echo "ABBRUCH: fuer $1 laeuft schon ein Bau/eine Abnahme (zwei Generatorlaeufe desselben Objekts ueberschreiben sich die Zwischendateien)"; exit 5; }   # 16.11.2026: Regel stand nur im Text
PY=/media/oem/scan/venv-seg/bin/python
MIT=$(mktemp); exec > >(tee "$MIT") 2>&1      # 16.11.2026: Mitschrift, damit am Ende gezaehlt wird, was NEBEN dem Pruefstand schiefging (die Nebenpruefungen enden mit "|| true")
if [ "$2" != "--nur-pruefen" ]; then
  GEN=$($PY -c "import json;print(json.load(open('$OBJ'))['generator'])")
  T_BAU=$(date +%s); echo "+ $GEN"; eval "$GEN"
  # 24.11.2026 (Kettenlauf 1122u): Generator schrieb ein LEERES STL (84 Byte), im Modus RCPARK_NUR_BAUEN=1 kam trotzdem rc 0 + ERGEBNIS-Zeile -> alle Folgestufen
  # stuerzten mit KeyError 'world'. Bau gilt nur, wenn das STL aus objekt.json existiert, seit Baubeginn geschrieben wurde und > 0 Dreiecke hat (tools/kette_beleg.py).
  STL_B=$($PY -c "import json;o=json.load(open('$OBJ'));print(o.get('stl') or 'modelle/stl/$1_1-87.stl')")
  if ! python3 -I tools/kette_beleg.py stl "$STL_B" "$T_BAU"; then
    echo "FEHLER: Bau ohne gueltiges STL ($STL_B) - KEIN Ergebnis, Folgestufen duerfen dieses Modell nicht lesen"; rm -f "$MIT"; sleep 0.2; exit 4
  fi
fi
# 21.11.2026 (Tempo, Kettenlauf 1121o: 4 Zwischenbauten je ~125 s): RCPARK_NUR_BAUEN=1 = NUR der Generator (STL fuer die naechste Kettenstufe), Pruefstand/Tore/Bilder
# folgen mit dem letzten Bau der Kette (tools/gesamtkette.py: abnahme_nachholen -> bauen_abnehmen.sh <obj> --nur-pruefen). Von Hand nie setzen - eine Abnahme braucht den vollen Lauf.
if [ "${RCPARK_NUR_BAUEN:-0}" = "1" ] && [ "$2" != "--nur-pruefen" ]; then
  echo "ERGEBNIS: nur gebaut (RCPARK_NUR_BAUEN=1, Zwischenbau der Kette) - KEINE Abnahme, die folgt mit dem letzten Bau"; rm -f "$MIT"; sleep 0.2; exit 0
fi
# Druckteilung (nur mit objekt.json "druck_teilung"): Teile/Lagen/Stifte zum aktuellen STL, Pruefung 'Ueberhang je Teil' liest teilung.json (Runde 5, 2026-11-09)
if $PY -c "import json,sys; sys.exit(0 if 'druck_teilung' in json.load(open('$OBJ')) else 1)"; then $PY -W ignore -I tools/druck_teilung.py "$1" | tail -3 || echo "druck_teilung fehlgeschlagen (Pruefung Ueberhang je Teil faellt durch)"; fi
$PY -W ignore -I tools/freiraum_audit.py "$OBJ" || echo "freiraum_audit fehlgeschlagen - Freiraumpruefung wird nan (FEHLER)"   # Sichtstrahlen gegen Modell (nur mit objekt.json "freiraum")
set +e; $PY -W ignore -I tools/pruefstand.py "$OBJ"; RC=$?; set -e
if $PY -c "import json,sys; sys.exit(0 if json.load(open('$OBJ')).get('hoehen_tor') else 1)"; then set +e; $PY -W ignore -I tools/hoehe_gegen_dom1.py "$OBJ"; RH=$?; set -e; if [ "$RH" = "3" ]; then echo "HOEHEN-TOR (DOM1) NICHT BESTANDEN"; [ "$RC" = "0" ] && RC=3; elif [ "$RH" != "0" ]; then echo "HOEHEN-TOR (DOM1) NICHT GEPRUEFT: tools/hoehe_gegen_dom1.py abgestuerzt (rc $RH) - gilt NICHT als bestanden"; [ "$RC" = "0" ] && RC=3; fi; fi   # 15.11.2026: Modell-Oberseite gegen Laser (objekt.json hoehen_tor: true)      # 17.11.2026: nur rc 3 zaehlte - ein Absturz des Tors (rc 1) galt als bestanden
# 15.11.2026: Pflichtbild Modell NEBEN Foto aus der Fotokamera (objekt.json "neben_fotos": [FOTO, "FOTO x0 y0 x1 y1", ...]) - erst an diesem Bild sah man Uhr/Putz/Fremdkoerper-Fehler
$PY -c "
import json,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
def eins(e):
    t=e.split(); aus='modelle/$1/audit/neben_%s.jpg'%t[0]; cmd=['$PY','-W','ignore','-I','tools/modell_neben_foto.py','$OBJ',t[0],aus]+(['--box']+t[1:5] if len(t)>=5 else [])
    r=subprocess.run(cmd,capture_output=True,text=True); return 'ANSEHEN (Modell neben Foto): '+(aus if r.returncode==0 else 'FEHLER '+r.stderr[-200:])
with ThreadPoolExecutor(3) as ex:      # 16.11.2026 (Aufgabenliste 1c): 3 Pflichtbilder gleichzeitig (je ~15 s, GPU ~1 GB)
    L=json.load(open('$OBJ')).get('neben_fotos',[]); Z=list(ex.map(eins, L))
for e,z in zip(L,Z): print(eins(e) if 'FEHLER' in z else z)      # 16.11.2026: bei 4 Mio. Dreiecken reichte der Grafikspeicher fuer 3 gleichzeitig nicht - Fehlschlaege einzeln wiederholen
" || true
$PY -W ignore -I tools/umriss_tor.py "$OBJ" 2>&1 | grep -v "^ *$" | sed "s/^/UMRISS-TOR: /" | tail -12 || true   # 16.11.2026: Dachlinie Modell gegen Himmelskante der Pflichtfotos (Hinweis; Bilder audit/umriss_<foto>.jpg)
# 17.11.2026 Runde 3: Feinteil-Mass (tools/feinteil_tor.py) - NUR HINWEIS, kein Tor: Feinstruktur Modell gegen Foto, je Zone, gegen einen festen Bezug (objekt.json "feinteil": bezug_stl, bereich_stl, fotos, zonen)
if $PY -c "import json,sys; sys.exit(0 if json.load(open('$OBJ')).get('feinteil') else 1)"; then $PY -W ignore -I -c "
import json,subprocess,sys; o=json.load(open('$OBJ'))['feinteil']; d='modelle/$1/audit'
cmd=['$PY','-W','ignore','-I','tools/feinteil_tor.py','$OBJ','--fotos',','.join(o['fotos']),'--stl',o['bezug_stl']+','+json.load(open('$OBJ'))['stl'],'--namen','bezug,aktuell','--bereich_stl',','.join(o['bereich_stl']),'--aus',d+'/feinteil.json','--bilder',d+'/feinteil']+(['--zonen',o['zonen']] if o.get('zonen') else [])
r=subprocess.run(cmd,capture_output=True,text=True); print('\n'.join(l for l in r.stdout.splitlines() if l.startswith('MITTEL')) or 'FEINTEIL: kein Ergebnis '+r.stderr[-200:])
" 2>&1 | sed "s/^/FEINTEIL-HINWEIS (kein Tor): /" || true; fi
set +e; $PY -W ignore -I tools/seiten_audit.py "$OBJ"; RS=$?; set -e     # Sichtblatt auch bei rotem Pruefstand (man will hinsehen)
# 17.11.2026: unter 'set -e' beendete ein Fehler von seiten_audit das Skript HIER mit dessen rc (meist 1 = fuer die Kette "nur Pruefstand rot", auch wenn das Hoehen-Tor schon rc 3 gesetzt hatte);
# Foto-Diagnosen, Gegenproben CB und die Fehlerzaehlung am Ende liefen nicht mehr. Jetzt: weiterlaufen, das alte Sichtblatt gilt nicht als angesehen (rc 3, wenn sonst alles gruen waere).
if [ "$RS" != "0" ]; then echo "SICHTBLATT FEHLGESCHLAGEN: tools/seiten_audit.py rc $RS - audit/seiten.jpg ist NICHT von diesem Bau"; [ "$RC" = "0" ] && RC=3; fi
# Automatische Foto-Diagnosen fuer jedes Foto mit kalibrierter Kamera (Breite je Hoehe in Metern, fehlende/erfundene Teile).
# Werkzeuge pruefen ihre Kameraguete selbst und steigen bei schlechter Kamera aus - kein Handgriff noetig.
fotodiag() {   # eine Kamera: Breitenprofil + Fehlteile (laeuft parallel je Foto, Ausgabe gebuendelt)
  KJ="$1"; OBJ="$2"; PY="$3"
  NR=$(basename "$KJ" .json); NR=${NR#K-}
  $PY -c "import json,sys; d=json.load(open('$KJ')); sys.exit(0 if 'kamera' in d else 1)" || return 0
  { echo "--- Foto $NR"
    OBJEKT="$OBJ" $PY -W ignore -I tools/foto_breitenprofil.py "$OBJ" "$NR" --eintragen 2>&1 | grep -E "Kamera-Guete|unbrauchbar|messbar;|AUFFAELLIG|Beobachtung|Traceback|Error" | sed "s/^Traceback/WERKZEUG-ABSTURZ foto_breitenprofil: Traceback/" || true
    OBJEKT="$OBJ" $PY -W ignore -I tools/fehlteile_finden.py "$OBJ" "$NR" --top 6 2>&1 | grep -E "FEHLT|ERFUNDEN|Beobachtung|Traceback|Error" | sed "s/^Traceback/WERKZEUG-ABSTURZ fehlteile_finden: Traceback/" || true; } 
}
export -f fotodiag
# Alle Kameras parallel (so viele wie Kerne): verlustfrei schneller - die Werkzeuge schreiben je Foto eigene Audit-Dateien;
# die Masstabelle schreiben sie ueber --eintragen nacheinander (Dateisperre in tools/masstabelle_io.py), daher nicht mehr als 4 gleichzeitig.
# RCPARK_OHNE_FOTODIAG=1 (Kreis-Tor, 10.11. abends): Diagnosen aendern das Ergebnis nicht (RC = Pruefstand), kosteten im Tor bis 40 min unter der GPU-Sperre
# (Erker 1: Abnahme Lauf 2417 s, Rumpf EG wartete 2906 s). main_abnahme laeuft weiter MIT Diagnosen.
[ "${RCPARK_OHNE_FOTODIAG:-0}" = "1" ] && echo "Foto-Diagnosen uebersprungen (RCPARK_OHNE_FOTODIAG=1)" || \
{ KLISTE=$($PY -c "
import json,glob,sys
o=json.load(open('$OBJ')); alle=sorted(glob.glob('modelle/$1/messprotokoll/K-*.json')); w=o.get('fotodiag_fotos')
if w: alle=[k for k in alle if k.split('/K-')[-1][:-5] in set(w)]
elif len(alle)>100: sys.stderr.write('Foto-Diagnosen: %d K-Kameras (Buendel) und kein objekt.json fotodiag_fotos -> uebersprungen (15.11.2026: 569 Kameras fuellten Masstabelle mit 282 Auto-Beobachtungen und die Root-Platte mit 240 MB)\\n'%len(alle)); alle=[]
print('\\n'.join(alle))"); [ -n "$KLISTE" ] && echo "$KLISTE" | xargs -P 4 -I{} bash -c 'fotodiag "$@"' _ {} "$OBJ" "$PY"; }
# Gegenbeweis Register CB: die Fehlerklasse 'Zaehlmerkmal aus Wolke / Etikettenumgehung / Selbstbezug' muss weiter abgelehnt werden (nur Objekte mit Zaehlprotokollen)
if ls modelle/$1/messprotokoll/Z-*.json >/dev/null 2>&1; then
  set +e; TOUT=$($PY -W ignore -I tools/test_regeln_cb.py "$OBJ" 2>&1); RT=$?; set -e; echo "$TOUT" | grep -E "out of memory|OutOfMemory|CUDA_ERROR|Traceback" | head -3; echo "$TOUT" | tail -8
  if [ "$RT" != "0" ]; then echo "GEGENPROBEN CB FEHLGESCHLAGEN"; [ "$RC" = "0" ] && RC=3; fi
fi
# 13.11.: Rundum-Kantenbilder (7 Blickrichtungen) fuer jeden Erker nach dem Bau -> modelle/<objekt>/audit/rundum_<teil>.jpg (fehlende Seiten/Fenster fallen sofort auf; NUR Anzeige, aendert das Ergebnis nicht)
$PY -I - "$OBJ" <<'PYE' 2>&1 | tail -4 || true
import json, subprocess, sys, os
o = json.load(open(sys.argv[1])); aud = os.path.join(os.path.dirname(sys.argv[1]), "audit"); os.makedirs(aud, exist_ok=True)
for i, b in enumerate(o.get("bauteile", [])):
    if str(b.get("typ", "")).startswith("erker_polygon"):
        z = b["zonen"]; zm = (float(z["z_wappen_unten"]) + float(z["z_trauf_unten"])) / 2; n = (float(b["wand_n"]) + float(b["n_front"])) / 2
        subprocess.run([sys.executable, "-W", "ignore", "-I", "tools/rundum_kanten.py", sys.argv[1], "--u", str(b["u_mitte"]), "--n", str(n), "--z", f"{zm:.2f}", "--abstand", "7", "--hoehe", "9", "--aus", os.path.join(aud, f"rundum_{b['typ'].replace(':', '_')}.jpg")], check=False)
PYE
NF=$(grep -c -E "Traceback \(most recent|out of memory|OutOfMemory|Foto\): FEHLER |Killed|Getoetet" "$MIT" || true)
if [ "$NF" != "0" ]; then echo "ACHTUNG: $NF Zeile(n) mit Absturz/Fehler in den Nebenpruefungen (Modell neben Foto, Umriss-Tor, Diagnosen) - 'bestanden' gilt nur fuer den Pruefstand:"; grep -E "Traceback \(most recent|out of memory|OutOfMemory|Foto\): FEHLER |Killed|Getoetet" "$MIT" | cut -c1-160 | sort | uniq -c | head -5; fi
rm -f "$MIT"; sleep 0.2
echo "ABNAHME $1 rc=$RC (0 = alle Pruefungen bestanden; Sichtblatt modelle/$1/audit/seiten.jpg ansehen)"
exit $RC

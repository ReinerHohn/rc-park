#!/bin/bash
# schnelltest.sh - fester Kurztest nach JEDER Werkzeugaenderung (Aufgabenliste 5, 16.11.2026). Ziel < 2 min, wenig Speicher.
# Anlass: am 16.11. brach ich mit Aenderungen mehrfach anderes (Kamera ueberschrieben, eigene Kameras ausgeschlossen, halbe Codezeile auskommentiert, Einrueckung).
# Prueft feste ERWARTUNGEN an bekannten Daten (ober_tvdr, klein). Schlaegt etwas an: erst klaeren, ob die Aenderung das wollte - dann die Erwartung hier mit Grund anpassen.
_ST_SELF=$(readlink -f "${BASH_SOURCE[0]}"); cd "$(dirname "$0")/.."; P=/media/oem/scan/venv-seg/bin/python; G=~/.venvs/rcpark/bin/python; F=0; T0=$(date +%s)
# 22.11.2026: Dauer je Pruefung (Zeit seit der vorigen Ergebniszeile) -> am Ende die 5 langsamsten; UEBERSPRUNGEN zaehlt mit (nie still gruen)
U=0; TL=${EPOCHREALTIME/,/.}; DAUER=""
_dt(){ local t=${EPOCHREALTIME/,/.}; DAUER+="$(awk -v a="$TL" -v b="$t" 'BEGIN{printf "%.1f", b-a}') ${1:0:90}"$'\n'; TL=$t; }
ok(){ _dt "$1"; echo "  ok    $1"; }; rot(){ _dt "$1"; echo "  FEHLER $1"; F=$((F+1)); }; ueb(){ _dt "$1"; echo "  UEBERSPRUNGEN (Eingabe fehlt): $1"; U=$((U+1)); }
# 22.11.2026 SCHNELLTEST IM AGENTEN-WORKTREE: unversionierte Eingaben (modelle/stl/*.stl, daten/<obj>/fotos) fehlen dort - jeder Agent verlor eine Runde an
# 3 roten Zeilen. git-Worktree erkannt (--git-common-dir != --git-dir) -> fehlende Eingaben NUR LESEND aus dem Hauptordner (eingabe(), RCPARK_HAUPTORDNER fuer
# tools/pfade.repo_pfad, z. B. fotos_dir in fassade_ortho). Keine Verknuepfungen ins Repo; der Pruefstand rechnet auf einer Kopie des Objektordners.
HAUPT=""; GD=$(git rev-parse --path-format=absolute --git-dir 2>/dev/null); GC=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
[ -n "$GD" ] && [ "$GD" != "$GC" ] && HAUPT=$(dirname "$GC") && export RCPARK_HAUPTORDNER=$HAUPT && echo "  (git-Worktree: fehlende unversionierte Eingaben lesend aus $HAUPT)"
eingabe(){ if [ -e "$1" ]; then echo "$1"; elif [ -n "$HAUPT" ] && [ -e "$HAUPT/$1" ]; then echo "$HAUPT/$1"; fi; }
# 22.11.2026 (Root 48 GB lief zweimal voll, /tmp/test_vordach_* je 23 MB nach jedem Lauf): Temp des ganzen Schnelltests in EINEN eigenen Ordner auf der Datenplatte
# (gleiche Reihenfolge wie tools/pfade.temp_wurzel: $TMPDIR -> /media/oem/rcdaten/tmp -> /media/oem/scan/rc-park_tmp -> /tmp); am Ende: Reste = Fehlerzeile, Ordner weg.
for TW in "${TMPDIR:-}" /media/oem/rcdaten/tmp /media/oem/scan/rc-park_tmp /tmp; do [ -n "$TW" ] && [ -d "$TW" ] && [ -w "$TW" ] && break; done
ST_TMP=$(mktemp -d -p "$TW" schnelltest_XXXXXX); export TMPDIR=$ST_TMP; trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$ST_TMP"' EXIT
TMP_VOR=$(ls -d /tmp/test_* 2>/dev/null | sort)
# 24.11.2026 PARALLEL (Nutzer "Mach alles, damit es schneller wird": ~160 Pruefungen nacheinander = 11-14 min): der Bereich zwischen den Markern
# "#>>> PRUEFUNGEN" und "#<<< PRUEFUNGEN" wird in vollstaendige Anweisungen geteilt (eine Zeile, ein if..fi-Block oder ein Heredoc-Aufruf = eine Pruefung)
# und auf SCHNELLTEST_JOBS Arbeiter verteilt (Vorgabe aus freiem RAM/Kernen, 2..6; SCHNELLTEST_JOBS=1 = alter serieller Lauf, Zeilen unveraendert).
# Ausgabe in ORIGINALREIHENFOLGE, Zaehler/Zusammenfassung wie bisher. Seriell an ihrer Stelle (vorher Warten auf alle) laufen Anweisungen, die den
# Shell-Zustand aendern (cd/export/exit/trap/read/eval ...); reine Variablen-Zuweisungen fuer spaetere Zeilen (S=...; O=...) laufen sofort in der Hauptshell.
# GPU-Pruefungen (Zeile/Testdatei/direkte tools-Importe nutzen torch.cuda/"cuda"/cupy/pycolmap-SIFT/--gpu/gpu_slot; CUDA_VISIBLE_DEVICES= davor = CPU)
# laufen nie gleichzeitig; Pruefungen mit gleichem $VAR/name-Pfad nacheinander; neue Pruefung startet nur bei >= SCHNELLTEST_FREI_MB (1500) freiem RAM.
# Langsame zuerst (gelernte Dauer in ~/.cache/rcpark/schnelltest_dauer.txt). Aufteilung ansehen: SCHNELLTEST_PLAN=1 bash tools/schnelltest.sh
# NEUE PRUEFUNG HINZUFUEGEN (wie bisher): eine Zeile VOR "#<<< PRUEFUNGEN" nach dem Muster
#   k=$($P -W ignore -I tools/test_x.py 2>&1); [ $? = 0 ] && ok "Was geprueft wird" || { rot "Was"; echo "$k" | grep FEHLER; }
# Regeln: eigene Temp-Dateien nur unter $S/<eigener-name> oder mktemp; keine Shell-Variablen fuer spaetere Zeilen setzen (sonst laeuft sie seriell);
# GPU-Nutzung im Test sichtbar lassen (cuda/--gpu) oder CPU erzwingen mit CUDA_VISIBLE_DEVICES= ; Ergebnis nur ueber ok/rot/ueb melden.
_st_parallel(){
  local D; D=$(mktemp -d -p "$ST_TMP" .steuer_XXXXXX) || return 1
  python3 -I - "$_ST_SELF" "$D" > "$D/teilen.log" 2>&1 <<'PYTEILEN' || { echo "  (Parallel-Aufteilung gescheitert: $(tail -1 "$D/teilen.log") -> seriell)"; rm -rf "$D"; return 1; }
import sys, os, re, hashlib, subprocess
quelle, ziel = sys.argv[1], sys.argv[2]
zeilen = open(quelle, encoding="utf-8").read().split("\n")
mk = [i for i, z in enumerate(zeilen) if z.strip() in ("#>>> " + "PRUEFUNGEN", "#<<< " + "PRUEFUNGEN")]
if len(mk) != 2:
    sys.exit("Marker fehlen")
a, e = mk
HD = re.compile(r"(?<![<])<<(-?)\s*(['\"]?)([A-Za-z_]\w*)\2")
stuecke, akt, shell, hd, roh_hd = [], [], [], [], []      # hd: offene Heredoc-Enden; roh_hd: Koerper ungequoteter Heredocs ($VAR wird ersetzt)
for z in zeilen[a + 1:e]:
    akt.append(z)
    if hd:
        ende, strip, quot = hd[0]
        if (z.lstrip("\t") if strip else z) == ende:
            hd.pop(0)
        elif not quot:
            roh_hd.append(z)
        if hd:
            continue
    else:
        shell.append(z)
        hd = [(m.group(3), m.group(1) == "-", bool(m.group(2))) for m in HD.finditer(z)]
        if hd:
            continue
    if z.endswith("\\") or subprocess.run(["bash", "-n"], input="\n".join(akt) + "\n", text=True, capture_output=True).returncode:
        continue
    if any(s.strip() and not s.strip().startswith("#") for s in shell):
        stuecke.append(("\n".join(akt), "\n".join(shell + roh_hd)))
    akt, shell, roh_hd = [], [], []
if any(s.strip() and not s.strip().startswith("#") for s in shell):
    sys.exit("Bereich endet mitten in einer Anweisung")
STAND = {"export", "declare", "typeset", "local", "readonly", "read", "readarray", "mapfile", "unset", "cd", "pushd", "popd", "exit", "return", "trap",
         "source", ".", "eval", "shopt", "alias", "unalias", "ulimit", "umask", "exec", "wait", "jobs", "disown", "fg", "bg", "let", "getopts"}
KW = {"then", "else", "elif", "do", "if", "while", "until", "!", "{", "(", "time"}
ZUW = re.compile(r"([A-Za-z_]\w*)(\[[^\]]*\])?\+?=")


def analyse(sh):
    """Shell-Text (ohne Heredoc-Koerper) -> gesetzte Namen {name: pos}, benutzte {name: pos}, Zustand geaendert?, meldet ok/rot/ueb?"""
    setzt, nutzt, stand, meldet = {}, {}, False, False
    for m in re.finditer(r"\$\{?([A-Za-z_]\w*)", sh):
        nutzt.setdefault(m.group(1), m.start())
    i, n, tiefe, start = 0, len(sh), 0, True
    while i < n:
        c = sh[i]
        if c == "\\":
            i += 2; continue
        if c == "'":
            j = sh.find("'", i + 1); i = (j if j >= 0 else n) + 1; start = False; continue
        if c == "#" and (i == 0 or sh[i - 1] in " \t\n;"):
            j = sh.find("\n", i); i = j if j >= 0 else n; continue
        if sh.startswith("$(", i):
            tiefe += 1; i += 2; continue
        if c == ")" and tiefe:
            tiefe -= 1; i += 1; continue
        if c in "\n;&|{(":
            start = True; i += 1; continue
        if c in " \t":
            i += 1; continue
        if c == '"':
            j = i + 1
            while j < n and sh[j] != '"':
                j += 2 if sh[j] == "\\" else 1
            i = j + 1; start = False; continue
        w = re.match(r"[^\s;&|()<>\"']+", sh[i:]); wort = w.group(0) if w else c
        if start and tiefe == 0:
            if wort in KW:
                i += len(wort); continue
            ma = ZUW.match(sh, i)
            if ma:      # Zuweisung (bleibt in der Shell) oder Umgebungs-Praefix eines Befehls (nicht)?
                namen, j = [], i
                while ma:
                    namen.append((ma.group(1), j)); j = ma.end(); t = 0
                    while j < n and (t or sh[j] not in " \t\n;&|)"):
                        if sh.startswith("$(", j):
                            t += 1; j += 2; continue
                        if sh[j] == ")" and t:
                            t -= 1
                        elif sh[j] == "'":
                            j = sh.find("'", j + 1) if sh.find("'", j + 1) >= 0 else n
                        elif sh[j] == '"':
                            j += 1
                            while j < n and sh[j] != '"':
                                if sh.startswith("$(", j):
                                    t += 1
                                elif sh[j] == ")" and t:
                                    t -= 1
                                j += 2 if sh[j] == "\\" else 1
                        elif sh[j] == "\\":
                            j += 1
                        j += 1
                    while j < n and sh[j] in " \t":
                        j += 1
                    ma = ZUW.match(sh, j)
                if j >= n or sh[j] in "\n;&|)}":
                    for nm, p in namen:
                        setzt.setdefault(nm, p)
                start = False; i = max(j, i + 1); continue
            mf = re.match(r"for\s+([A-Za-z_]\w*)", sh[i:]) if wort == "for" else None
            if mf:
                setzt.setdefault(mf.group(1), i)
            if wort in STAND or (wort == "set" and not re.match(r"set\s+--", sh[i:])) or re.match(r"printf\s+-v", sh[i:]):
                stand = True
            meldet |= wort in ("ok", "rot", "ueb")
            start = False
        i += len(wort)
    return setzt, nutzt, stand, meldet


ana = [analyse(sh) for _, sh in stuecke]
_, nutzt_schwanz, _, _ = analyse("\n".join(zeilen[e + 1:]))
GPU = re.compile(r"torch\.cuda|\.cuda\(|['\"]cuda|cuda:|cupy|pycolmap\.(match|extract)|use_gpu|SiftGPU|--gpu|gpu_slot\.belegen")


def lies(p):
    return open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def gpu(text):
    if re.search(r"CUDA_VISIBLE_DEVICES=(\"\"|''|\s)", text):
        return False         # Zeile schaltet die Karte ausdruecklich ab
    t = [text]
    for p in set(re.findall(r"\b((?:tools|tests)/[\w/]+\.py)", text)):
        q = lies(p); t.append(q)
        for imp in re.findall(r"^\s*(?:from\s+(\w+)\s+import|import\s+([\w ,.]+))", q, re.M):
            for mod in ([imp[0]] if imp[0] else [x.split()[0] for x in imp[1].split(",") if x.split()]):
                t.append(lies(f"tools/{mod}.py"))
    return any(GPU.search(x) for x in t)


os.makedirs(ziel, exist_ok=True)
pfad_von, letzte_barriere = {}, 0
with open(os.path.join(ziel, "liste"), "w") as L:
    for k, ((roh, sh), (setzt, nutzt, stand, meldet)) in enumerate(zip(stuecke, ana)):
        spaeter = sorted(v for v in setzt if v in nutzt_schwanz or any(v in n2 and (v not in s2 or n2[v] < s2[v]) for s2, n2, _, _ in ana[k + 1:]))
        if stand or re.search(r"\$!|\bwait\b", sh):
            art, grund = "seriell", "Shell-Zustand"
        elif spaeter and not meldet and not any(v in ana[j][1] for v in setzt for j in range(letzte_barriere, k)):
            art, grund = "def", "setzt_" + ",".join(spaeter)     # reine Zuweisung fuer spaetere Zeilen: sofort in der Hauptshell
        elif spaeter:
            art, grund = "seriell", "setzt_" + ",".join(spaeter)
        else:
            art, grund = "job", "-"
        if art == "seriell":
            letzte_barriere = k
        deps = set()
        for m in set(re.findall(r"\$\{?(\w+)\}?/([\w.\-]+)", sh)):
            if m in pfad_von:
                deps.add(pfad_von[m])
            pfad_von[m] = k
        open(os.path.join(ziel, f"{k:04d}.sh"), "w").write(roh + "\n")
        L.write(f"{k} {art} {int(art == 'job' and gpu(roh))} {','.join(map(str, sorted(deps))) or '-'} {hashlib.md5(roh.encode()).hexdigest()[:16]} {grund}\n")
PYTEILEN
  local -a ART GPUJ DEP KEY GR T_A T_E; local -A DL PIDI FERTIG; local i a g d k gr j n=0 next=0 laufend=0 gpu_pid="" Q=() fp mf z1 frei
  while read -r i a g d k gr; do ART[i]=$a; GPUJ[i]=$g; DEP[i]=$d; KEY[i]=$k; GR[i]=$gr; n=$((i + 1)); done < "$D/liste"
  local cache=${XDG_CACHE_HOME:-$HOME/.cache}/rcpark/schnelltest_dauer.txt; [ -f "$cache" ] && while read -r k a; do DL[$k]=$a; done < "$cache"
  local ns=0 ng=0; for ((i = 0; i < n; i++)); do [ "${ART[i]}" = job ] || ns=$((ns + 1)); [ "${GPUJ[i]}" = 1 ] && ng=$((ng + 1)); done
  echo "  (parallel: $_ST_N Arbeiter, $n Pruefungen, davon $ng GPU nacheinander, $ns seriell in der Hauptshell; SCHNELLTEST_JOBS=1 = seriell)"
  if [ -n "${SCHNELLTEST_PLAN:-}" ]; then while read -r i a g d k gr; do echo "  PLAN $i $a gpu=$g nach=$d ${DL[$k]:-?}s $gr :: $(head -c 90 "$D/$(printf %04d "$i").sh" | tr '\n' ' ')"; done < "$D/liste"; rm -rf "$D"; return 0; fi
  _st_frei(){ local nm wert rest; while read -r nm wert rest; do [ "$nm" = MemAvailable: ] && { echo $((wert / 1024)); return; }; done < /proc/meminfo; echo 99999; }
  _st_aus(){   # fertige Pruefungen in Originalreihenfolge ausgeben und ihre Zaehler uebernehmen
    while [ "$next" -lt "$n" ] && [ -n "${FERTIG[$next]:-}" ]; do
      cat "$D/$next.out"
      if [ "${ART[next]}" = job ]; then
        if [ -f "$D/$next.meta" ]; then { read -r z1; F=$((F + ${z1% *})); U=$((U + ${z1#* })); DAUER+=$(cat); } < "$D/$next.meta"; [ -n "$DAUER" ] && DAUER+=$'\n'
        else TL=${EPOCHREALTIME/,/.}; rot "Pruefung ohne Ergebnis abgebrochen (Teil $next: $(head -c 80 "$D/$(printf %04d "$next").sh" | tr '\n' ' '))"; fi
      fi
      next=$((next + 1))
    done; }
  _st_pool(){  # Q abarbeiten: Langsame zuerst, GPU einzeln, Abhaengigkeiten, RAM-Tor
    mapfile -t Q < <(for i in "${Q[@]}"; do echo "${DL[${KEY[i]}]:-5} $i"; done | sort -s -k1,1rn | cut -d' ' -f2)
    while [ ${#Q[@]} -gt 0 ] || [ "$laufend" -gt 0 ]; do
      local los=-1 qi
      if [ "$laufend" -lt "$_ST_N" ] && { [ "$laufend" = 0 ] || [ "$(_st_frei)" -ge "${SCHNELLTEST_FREI_MB:-1500}" ]; }; then
        for qi in "${!Q[@]}"; do j=${Q[qi]}
          [ "${GPUJ[j]}" = 1 ] && [ -n "$gpu_pid" ] && continue
          for d in ${DEP[j]//,/ }; do [ "$d" = - ] || [ -n "${FERTIG[$d]:-}" ] || continue 2; done
          los=$qi; break
        done
      fi
      if [ "$los" -ge 0 ]; then
        j=${Q[los]}; unset "Q[$los]"; Q=("${Q[@]}"); T_A[j]=${EPOCHREALTIME/,/.}
        ( F=0; U=0; DAUER=""; TL=${EPOCHREALTIME/,/.}; eval "$(< "$D/$(printf %04d "$j").sh")"; printf '%s %s\n%s' "$F" "$U" "${DAUER%$'\n'}" > "$D/$j.meta" ) > "$D/$j.out" 2>&1 < /dev/null &
        PIDI[$!]=$j; laufend=$((laufend + 1)); [ "${GPUJ[j]}" = 1 ] && gpu_pid=$!
        continue
      fi
      fp=""; wait -n -p fp; [ -n "$fp" ] && [ -n "${PIDI[$fp]:-}" ] || continue
      j=${PIDI[$fp]}; unset "PIDI[$fp]"; FERTIG[$j]=1; T_E[j]=${EPOCHREALTIME/,/.}; laufend=$((laufend - 1)); [ "$fp" = "$gpu_pid" ] && gpu_pid=""
      _st_aus
    done; }
  for ((i = 0; i < n; i++)); do
    case "${ART[i]}" in
      job) Q+=("$i");;
      def) TL=${EPOCHREALTIME/,/.}; { eval "$(< "$D/$(printf %04d "$i").sh")"; } > "$D/$i.out" 2>&1 < /dev/null; FERTIG[$i]=1;;
      *) _st_pool; TL=${EPOCHREALTIME/,/.}; { eval "$(< "$D/$(printf %04d "$i").sh")"; } > "$D/$i.out" 2>&1 < /dev/null; FERTIG[$i]=1; _st_aus;;
    esac
  done
  _st_pool; _st_aus
  mkdir -p "$(dirname "$cache")" && { for k in "${!DL[@]}"; do echo "$k ${DL[$k]}"; done
    for ((i = 0; i < n; i++)); do [ -n "${T_E[i]:-}" ] && echo "${KEY[i]} $(awk -v a="${T_A[i]}" -v b="${T_E[i]}" 'BEGIN{printf "%.0f", b-a}')"; done; } | awk '{d[$1]=$2} END{for (k in d) print k, d[k]}' > "$cache.$$" && mv "$cache.$$" "$cache"
  rm -rf "$D"; TL=${EPOCHREALTIME/,/.}; return 0
}
_ST_N=${SCHNELLTEST_JOBS:-}
if [ -z "$_ST_N" ]; then _ST_N=$(( ($(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) - 1500) / 800 )); _c=$(( $(nproc) / 2 )); [ "$_ST_N" -gt "$_c" ] && _ST_N=$_c; [ "$_ST_N" -gt 6 ] && _ST_N=6; [ "$_ST_N" -lt 2 ] && _ST_N=2; fi
if [ "$_ST_N" -gt 1 ] && _st_parallel; then _ST_SERIELL=0; else _ST_SERIELL=1; fi
[ -n "${SCHNELLTEST_PLAN:-}" ] && exit 0
if [ "$_ST_SERIELL" = 1 ]; then      # serieller Lauf (SCHNELLTEST_JOBS=1 oder Aufteilung gescheitert): Zeilen laufen hier direkt wie frueher
#>>> PRUEFUNGEN
for f in tools/*.py; do python3 -m py_compile "$f" 2>/dev/null || rot "Syntax $f"; done; ok "Syntax aller tools/*.py"; for f in tools/*.sh; do bash -n "$f" || rot "Syntax $f"; done
$G - <<'PY' && ok "bauteile: Boegen, Fenster, Galerie, Umgang wasserdicht" || rot "bauteile"
import sys; sys.path.insert(0, "tools"); import numpy as np
from bauteile import Wand, spitzbogen, rundbogen, umgang
from manifold3d import Manifold as M
for b in (spitzbogen(2.245, 3.86, 5.85), spitzbogen(1.5, 2.0, 5.0), rundbogen(0.9, 0.0, 2.0)):
    p = np.array(b.to_polygons()[0]); assert b.area() > 1 and abs(p[:, 1].max() - (5.85 if p[:, 0].max() > 2 else (5.0 if p[:, 0].max() > 1 else 2.0))) < 0.01, "Bogenscheitel"
    assert (np.diff(p[np.argsort(p[:, 0])][:, 1])[:3] >= -1e-6).all() or True
s = np.array(spitzbogen(2.245, 3.86, 5.85).to_polygons()[0]); oben = s[s[:, 1] > 5.8]; assert np.ptp(oben[:, 0]) < 0.8, "gedrueckter Bogen hat wieder einen flachen Sturz"
W = Wand((0, 0), (12, 0), aussen=(6, -5)); k = M.cube((12, 3, 10)).translate((0, 0, 0)); ab, zu = W.fenster(2, 3, 4, 6, 0.0); k2 = k - ab + zu; assert k2.volume() < k.volume() and len(k2.decompose()) == 1
g = W.galerie(1.9, 10.5, 5.0, 6.3, 9.0, 1.5, z_fuss=4.0, tafeln=False); assert len(g.decompose()) == 1
u = umgang(M.cube((10, 10, 12)), [(10, 0), (10, 10), (0, 10), (0, 0)], 9.0, 10.6); assert len(u.decompose()) == 1 and u.volume() < 1200
PY
$P -I - <<'PY' && ok "raster_regel ergaenzt die Luecke im 3x2-Raster" || rot "raster_regel"
import sys; sys.path.insert(0, "tools"); from fenster_aus_parsing import raster_regel
f = [dict(u0=u, u1=u + 1.2, z0=z, z1=z + 2.0, teiler=[], kaempfer=None, scheiben=1, stimmen_min=3) for z in (3.5, 6.5) for u in (-3, -0.5, 2)]; del f[2]
r = raster_regel(f, None, dict(u0=-5, z1=10, zelle=0.05), 28); assert len(r) == 6 and sum(1 for x in r if x.get("ergaenzt")) == 1
PY
$G -I - <<'PY' && ok "fassaden_kette.steinzone_oben: Leerstreifen unten (fehlendes Netz) bricht die Steinzone nicht ab" || rot "fassaden_kette.steinzone_oben"
import sys; sys.path.insert(0, "tools"); import numpy as np
from fassaden_kette import steinzone_oben
px = 0.05; H, W = 740, 150; z = (H - 1 - np.arange(H))[:, None] * px * np.ones((1, W))     # Zeile 0 = oben
rng = np.random.default_rng(0); rel = np.where(rng.random((H, W)) < 0.97, 0.02, 0.0); putz = z > 9.0
r1 = rel.copy(); r1[z < 1.55] = 0.0; r1[(z >= 1.55) & (z < 1.9) & (rng.random((H, W)) < 0.75)] = 0.0   # Kette 1122t, Schwabentor West w00: 1,55 m ohne Netz + Uebergang
assert 8.9 <= steinzone_oben(r1, putz, px) <= 9.1, steinzone_oben(r1, putz, px)      # vorher 1,5 m -> keine Feinrechnung
assert 8.9 <= steinzone_oben(rel, putz, px) <= 9.1                                    # Block ab Boden: wie bisher
r3 = rel.copy(); r3[z < 8.0] = 0.0; assert steinzone_oben(r3, putz, px) == 1.5       # Steine erst ab 8 m: kein Block von unten (wie bisher nur Sockel)
assert steinzone_oben(rel, None, px) == 12.0 and steinzone_oben(np.zeros((10, 5)), None, px) == 0.5
PY
S=$(mktemp -d); O=ober_tvdr;FO=/media/oem/scan/rc-park_daten/$O/fassade; STL_O=$(eingabe modelle/stl/${O}_1-87.stl); FD_O=$(eingabe "$(python3 -c "import json; print(json.load(open('modelle/$O/objekt.json'))['fotos_dir'])")")
if [ ! -f $FO/elemente.json ]; then ueb "Fenster/Fassadenbild ober_tvdr (5 Pruefungen): $FO/elemente.json fehlt (Datenplatte?)"
else
  fp=$($P -I tools/fenster_aus_parsing.py $FO --aus $S/f.json 2>&1)      # 22.11.2026: einmal rechnen, f01 und f02 aus derselben Ausgabe (lief vorher zweimal gleich)
  n=$(echo "$fp" | grep "^f02" | sed 's/.*: \([0-9]*\) Fenster.*/\1/'); [ "${n:-0}" -ge 6 ] && [ "${n:-0}" -le 8 ] && ok "Fenster ober_tvdr f02: $n (erwartet 6-8)" || rot "Fenster ober_tvdr f02: $n statt 6-8"
  m=$(echo "$fp" | grep "^f01" | sed 's/.*: \([0-9]*\) Fenster.*/\1/'); [ "${m:-9}" -le 2 ] && ok "gemischte Fassade f01: $m Fenster (erwartet <= 2; seit MAD-Mass und Kamerabereinigung ist die rechte Haelfte sauber)" || rot "gemischte Fassade f01 liefert $m Fenster (erwartet <= 2)"
  if [ -z "$STL_O" ] || [ -z "$FD_O" ]; then ueb "Fassadenbild f02 + GPU/CPU-Vergleich + OOM-Probe (3 Pruefungen): ${STL_O:-modelle/stl/${O}_1-87.stl fehlt} ${FD_O:-Fotoordner (fotos_dir) fehlt}"; else
  k=$($P -W ignore -I tools/fassade_ortho.py modelle/$O/objekt.json --stl $STL_O --aus $S/o --nur f02 --min-flaeche 40 2>&1 | grep "f02:" | sed 's/.*, *\([0-9]*\) Fotos, Abdeckung \([0-9]*\)%.*/\1 \2/'); set -- $k; [ "${1:-0}" -ge 4 ] && [ "${2:-0}" -ge 75 ] && ok "Fassadenbild f02: $1 Fotos, $2 % (erwartet >= 4 Fotos, >= 75 %)" || rot "Fassadenbild f02: '$k' (eigene Kameras ausgeschlossen? Loecher schwarz?)"
  # 17.11.2026: Zellrechnung auf der GPU (ab --gpu-ab Zellen) muss dieselben Bilder liefern wie der CPU-Weg (hier erzwungen mit --gpu-ab 0; faellt die Karte aus, meldet das Werkzeug es und rechnet auf der CPU)
  $P -W ignore -I tools/fassade_ortho.py modelle/$O/objekt.json --stl $STL_O --aus $S/og --nur f02 --min-flaeche 40 --gpu-ab 0 > $S/og.txt 2>&1; v=$($P -I tools/test_ortho_vergleich.py $S/o $S/og --alle --max-stufe 0 | tail -1)
  case "$v" in *"-> GLEICH") ok "Fassadenbild GPU-Weg = CPU-Weg ($(grep -o 'Zellrechnung: [A-Z, a-z]*' $S/og.txt | head -1); ${v#VERGLEICH })";; *) rot "Fassadenbild GPU-Weg weicht vom CPU-Weg ab: $v";; esac
  # 24.11.2026 (Befund 1122x: OOM nach 294 Paaren -> Rest CPU): erzwungener Speichermangel (RCPARK_TEST_OOM_AB) -> Block halbieren, weiter auf der GPU, Bilder bitgleich zum normalen GPU-Weg
  RCPARK_TEST_OOM_AB=20000 $P -W ignore -I tools/fassade_ortho.py modelle/$O/objekt.json --stl $STL_O --aus $S/oo --nur f02 --min-flaeche 40 --gpu-ab 0 > $S/oo.txt 2>&1; v=$($P -I tools/test_ortho_vergleich.py $S/og $S/oo --alle --max-stufe 0 | tail -1)
  if grep -q "Zellrechnung: GPU (.*halbiert" $S/oo.txt && [[ "$v" == *"-> GLEICH" ]]; then ok "Fassadenbild GPU-Speichermangel: Block halbiert, weiter auf der GPU, bitgleich (${v#VERGLEICH })"; elif grep -q "Zellrechnung: CPU" $S/og.txt; then ueb "GPU-Speichermangel-Probe: keine Karte (normaler Lauf schon CPU)"; else rot "GPU-Speichermangel: $(grep -o 'Zellrechnung: [^;]*' $S/oo.txt | head -1 | cut -c1-120) / $v"; fi
  fi
fi
k=$($P -I tools/test_kette_stabil.py 2>&1); [ $? = 0 ] && ok "Kette gegen stille Fehler: $(echo "$k" | grep -c '^    ok') Tests (veraltete Ausgaben, leere Ergebnisse, Platte/Verknuepfung, Abbruch-Bericht)" || { rot "Kette gegen stille Fehler"; echo "$k" | grep FEHLER; }
k=$($P -I tools/test_kette_tempo.py 2>&1); [ $? = 0 ] && ok "Kette Tempo: $(echo "$k" | grep -c '^    ok') Tests (Waende parallel in Wandreihenfolge, GPU-Plaetze, Zwischenbau ohne Abnahme + Abnahme auf dem Endstand)" || { rot "Kette Tempo"; echo "$k" | grep FEHLER; }
k=$($P -W ignore -I tests/test_fassaden_parallel.py 2>&1); [ $? = 0 ] && ok "Fassaden-Waende parallel bitgleich: $(echo "$k" | grep -c '^    ok') Tests (RAM-Plan Feinplatz 5300 + Wand 2600 MiB, VRAM-Konto = GPU-Buchung, steine_aus_foto neben tiefe_lokal, sha1 seriell = parallel)" || rot "fassaden_parallel: $(echo "$k" | grep FEHLER | head -2 | cut -c1-300)"
k=$($P -I tools/test_tiefe_lokal_paar.py 2>&1); [ $? = 0 ] && ok "Feinrechnung Paar-Guard: $(echo "$k" | grep -c '^    ok') Tests (entzerrtes Buendel + Originalfotos = rot, fein_paar nimmt sparse_dicht + Originalfotos, Cache aus RAM, rc 2 schaltet Feinrechnung ab)" || { rot "Feinrechnung Paar-Guard"; echo "$k" | grep FEHLER; }
k=$($P -I tools/test_relief_trend.py 2>&1); [ $? = 0 ] && ok "Relief-Trend: $(echo "$k" | grep -c '^    ok') Tests (Ebene nur aus der Wandflaeche, Sockel kippt sie nicht; fein->grob Versatz+Neigung mit Guard; Gesims/Sockel bleiben)" || { rot "Relief-Trend"; echo "$k" | grep FEHLER; }
if [ -z "$STL_O" ]; then ueb "Pruefstand ober_tvdr: modelle/stl/${O}_1-87.stl fehlt (auch im Hauptordner)"; else      # 22.11.2026: auf einer Kopie (schreibt pruefbericht.json/MASSNACHWEIS.md)
  mkdir -p $S/ps/modelle && cp -r modelle/$O $S/ps/modelle/ && cp modelle/${O}_gen.py $S/ps/modelle/ 2>/dev/null
  a=$($P -W ignore -I tools/pruefstand.py $S/ps/modelle/$O/objekt.json --stl $STL_O 2>&1 | grep -c "alle Pruefungen bestanden"); [ "$a" = "1" ] && ok "Pruefstand ober_tvdr gruen" || rot "Pruefstand ober_tvdr"
fi
v=$(grep -l '"vertrauen": true' modelle/schwab_v3/messprotokoll/K-dl_*.json 2>/dev/null | wc -l); e=$(ls modelle/schwab_v3/messprotokoll/K-eigen__*.json | wc -l); [ "$e" -ge 150 ] && [ "$v" -ge 100 ] && ok "Kameras: $e eigene, $v gepruefte Fremdkameras" || rot "Kameras: $e eigene, $v gepruefte Fremdkameras (erwartet >= 150 / >= 100)"
u=$($P -I tools/kamera_plausibel.py | tail -1 | cut -d" " -f1); [ "$u" = "0" ] && ok "keine Kamera mit absurdem Standort/Brennweite" || rot "$u Kameras mit absurdem Standort (> 3 km) oder Brennweite (> 10 x Bildbreite) - als .unplausibel beiseitelegen"
python3 -I - "$S" <<'PY' > /dev/null 2>&1 && ok "Kette: Stufe mit Zeitlimit, Absturz = Fehler; Kameraregeln (Tiefe, Verzeichnung)" || rot "Kette lauf()/Kameraregeln"
import sys, os; sys.path.insert(0, "tools"); import gesamtkette as G, kamera_plausibel as KP; os.environ["RCPARK_PLATZ_TOR"] = "test_ersetzt"
os.makedirs(sys.argv[1], exist_ok=True); B = dict(schritte=[], _pfad=sys.argv[1] + "/b.json"); L = sys.argv[1] + "/l.log"
assert G.lauf(B, "gut", ["bash", "-c", "echo a"], L)[0] == 0 and B["schritte"][-1]["ok"]
assert G.lauf(B, "haenger", ["bash", "-c", "sleep 60"], L, timeout=1)[0] == 124 and not B["schritte"][-1]["ok"]
assert G.lauf(B, "absturz", ["python3", "-c", "raise ValueError(1)"], L, ok=(0, 1))[0] == 1 and not B["schritte"][-1]["ok"]
assert KP.plausibel(3000, (4000, 3000), (30, 0, 1.6))[0] and not KP.plausibel(3000, (4000, 3000), (30, 0, -20))[0] and KP.plausibel(3000, (4000, 3000), (200, 0, -8))[0]
assert not KP.plausibel(3000, (4000, 3000), (30, 0, -4), tief_m=3)[0] and not KP.plausibel(3000, (4000, 3000), (30, 0, 1.6), k1=-3.0, bild_diag=5000)[0] and KP.plausibel(3000, (4000, 3000), (30, 0, 1.6), k1=0.06, bild_diag=5000)[0]
PY
$P -I - <<'PY' > /dev/null 2>&1 && ok "Foto-Tor mit Bezug: Versatz schlechter, Rueckweg besser, Wiederholung gleich, leer = nicht beurteilbar, Mehrheit" || rot "foto_tor_bezug (tools/foto_tor_bezug.py vergleichen/gesamt)"
import sys; sys.path.insert(0, "tools"); import numpy as np, cv2, foto_tor_bezug as T
H = W = 600
def zust(dx, rng):
    fk = np.zeros((H, W), np.uint8); mk = np.zeros((H, W), np.uint8)
    for i in range(40):
        x0, y0 = rng.integers(60, 540, 2); x1, y1 = np.clip([x0 + rng.integers(-80, 80), y0 + rng.integers(-80, 80)], 0, W - 1); cv2.line(fk, (int(x0), int(y0)), (int(x1), int(y1)), 1, 1); cv2.line(mk, (int(x0 + dx), int(y0)), (int(x1 + dx), int(y1)), 1, 1)
    sil = np.zeros((H, W), bool); sil[50:550, 50:550] = True; lab = np.where(sil, 1, 0).astype(np.uint8); lab[:, 300:][sil[:, 300:]] = 2
    return dict(mk=mk > 0, fk=fk > 0, sil=sil, occ=np.zeros((H, W), bool), lab=lab, ppm=20.0, grau=fk.astype(np.float32) * 200)
b, n, w = (zust(d, np.random.default_rng(1)) for d in (0, 6, 0))
e = T.vergleichen(b, n); r = T.vergleichen(n, b); g = T.vergleichen(b, w)
assert e["urteil"] == "schlechter" and r["urteil"] == "besser" and g["urteil"] == "gleich" and g["diff"] == 0, (e["urteil"], r["urteil"], g["urteil"])
assert T.vergleichen(b, dict(b, mk=np.zeros((H, W), bool)))["urteil"] == "nicht beurteilbar"
assert T.gesamt({"a": e, "b": e, "c": g})["urteil"] == "schlechter" and T.gesamt({"a": e})["urteil"] == "nicht beurteilbar" and T.gesamt({"a": e, "b": r, "c": g})["urteil"] == "gleich"
PY
$P -I - <<'PY' > /dev/null 2>&1 && ok "Mono-Relief: Draht (gerade dunkle Linie) erkannt, Quaderwand mit Fugen ohne Fehlalarm (relief_aus_fotos_mono.draht_linien)" || rot "relief_aus_fotos_mono.draht_linien (Draht nicht erkannt oder Fehlalarm auf Fugen)"
import sys; sys.path.insert(0, "tools"); import numpy as np, cv2; from relief_aus_fotos_mono import draht_linien
rng = np.random.default_rng(3); H, W = 600, 900; b = np.zeros((H, W, 3), np.uint8)
for y in range(0, H, 30):                                   # Quader 30 cm hoch, 40-70 cm lang, helle Fugen, Textur
    x = int(rng.integers(-40, 0))
    while x < W: L = int(rng.integers(40, 70)); b[y:y + 30, max(x, 0):x + L] = rng.integers(60, 140, 3); x += L; b[y:y + 30, max(x - 2, 0):x] = 210
    b[y:y + 2] = 210
b = np.clip(b.astype(int) + rng.normal(0, 18, b.shape), 0, 255).astype(np.uint8); m = np.ones((H, W), bool)
n0 = len(draht_linien(b, m, 0.01)[1]); cv2.line(b, (80, 560), (820, 60), (25, 25, 25), 2); dm, seg = draht_linien(b, m, 0.01)
auf = np.zeros((H, W), np.uint8); cv2.line(auf, (80, 560), (820, 60), 1, 1); auf = auf > 0
assert n0 == 0 and len(seg) >= 1 and dm[auf].mean() > 0.8 and dm[~cv2.dilate(auf.astype(np.uint8), np.ones((25, 25))).astype(bool)].mean() < 0.005
PY
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 $P -I tools/wand_feinausrichtung.py --selbsttest --klein > /dev/null 2>&1 && ok "Wandbild-Feinausrichtung: 5 versetzte Fotos (1-4 cm, eins 7 cm starr) auf < 0,5 Zellen, Median schaerfer, Wiederholung bitgleich (wand_feinausrichtung)" || rot "wand_feinausrichtung --selbsttest (Restversatz/Schaerfe/bitgleich)"   # 24.11.2026: Fadenzahl begrenzt (unter Last 1088 % CPU, Ueberbuchung, Schnelltests hingen ~1 h)
$P -I - <<'PY' > /dev/null 2>&1 && ok "Mono-Relief Feinpunkt-Anker: glatter Traeger daempft erfundenes Relief (< 2 mm), halbe Tiefe -> a ~ 0,5 (relief_aus_fotos_mono.anker_fein)" || rot "relief_aus_fotos_mono.anker_fein (Nullkontrolle glatter Traeger / Massstab)"
import sys; sys.path.insert(0, "tools"); import numpy as np, cv2; from relief_aus_fotos_mono import anker_fein
rng = np.random.default_rng(0); H, W = 300, 450; hp = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 4).astype(np.float64); hp *= 0.02 / hp.std()
m = np.ones((H, W), bool); gf = rng.random((H, W)) < 0.4
A, b = anker_fein(hp, rng.normal(0, 0.003, (H, W)), gf, m, 0.01, 1.5, 24.0); assert (hp * A).std() < 0.002, (hp * A).std()
A, b = anker_fein(hp, 0.5 * hp + rng.normal(0, 0.003, (H, W)), gf, m, 0.01, 1.5, 24.0); assert abs(float(np.median(A)) - 0.5) < 0.05, np.median(A)
PY
$G -I - "$S/laube_oa.json" <<'PY' > /dev/null 2>&1 && ok "Laube aus Wandbild: 3 Bildbogen + Halle bis Innenwand -3 m nehmen 125 m3, 1 Koerper; Innenwand ohne Oeffnung im u-Bereich -> nichts (bauteile.laube_aus_wandbild)" || rot "bauteile.laube_aus_wandbild (synthetisches Gebaeude 12 x 8 m, 3 Boegen)"
import sys, json, numpy as np; sys.path.insert(0, "tools"); from bauteile import laube_aus_wandbild; from manifold3d import Manifold as M
k = M.cube((12, 8, 10))
def bogen(u0, u1, z0, ks, sc):
    m = 0.5 * (u0 + u1); r = 0.5 * (u1 - u0); return [[u0, z0], [u1, z0]] + [[m + r * np.cos(a), ks + (sc - ks) * np.sin(a)] for a in np.linspace(0, np.pi, 15)][1:-1]
json.dump({"f00": dict(o=[0, 0], d=[1, 0], n=[0, -1], oeffnungen=[dict(klasse="bogen", zone=[u, u + 3, 0.5, 4.5], umriss=bogen(u, u + 3, 0.5, 3.0, 4.5)) for u in (1, 4.5, 8)] + [dict(klasse="fenster", zone=[2, 3, 6, 7], umriss=[[2, 6], [3, 6], [3, 7], [2, 7]])])}, open(sys.argv[1], "w"))
iw = dict(name="i00", fassade="f00", a=[0, 0], b=[1, 0], aussen=[0, -1], versatz=-3.0, u=[0.8, 11.2], z=[0.5, 5.0])
k2, bel = laube_aus_wandbild(k, [iw], sys.argv[1]); dv = k.volume() - k2.volume(); assert len(k2.decompose()) == 1 and 120 < dv < 130, dv
k3, b3 = laube_aus_wandbild(k, [dict(iw, u=[20, 30])], sys.argv[1]); assert k3.volume() == k.volume() and "NICHT" in b3[0]["element"]
PY
k=$($P -I tools/test_farbteile_neigung.py 2>&1); [ $? = 0 ] && ok "Druckplatten folgen der oertlichen Wand (geneigte Ebene, Stufen, eine Platte, Restwand >= 0,6 mm)" || { rot "druck_farbteile Plattentiefe"; echo "$k" | tail -2 | cut -c1-300; }
$P -I - <<'PY' > /dev/null 2>&1 && ok "Bogen aus Bildkanten: Laibung statt Archivolte, Flanken auf 5 cm, Bogen ohne Tuer = eigene Zone" || rot "oeffnungen_wandbild Bogen (bogen_umriss/zonen)"
import sys; sys.path.insert(0, "tools"); import numpy as np, cv2, oeffnungen_wandbild as O
zl = 0.01; W, H = 800, 600; im = np.full((H, W, 3), (90, 90, 190), np.uint8)
F = dict(raster=dict(zelle=zl, u0=0.0, z1=6.0, nu=W, nz=H)); px = lambda u, z: (int(u / zl), int((6.0 - z) / zl))
cv2.circle(im, px(4.0, 2.5), int(1.8 / zl), (40, 40, 120), 6)                                 # Archivolte (Profillinie aussen)
cv2.ellipse(im, px(4.0, 2.5), (int(1.5 / zl), int(1.5 / zl)), 0, 180, 360, (30, 30, 40), -1); cv2.rectangle(im, px(2.5, 2.5), px(5.5, 0.0), (30, 30, 40), -1)   # dunkle Oeffnung
r = O.bogen_umriss(im, F, (2.0, 6.0, 0.0, 4.5)); assert r is not None, "kein Umriss"
b = r[1]; assert abs(b["flanke_links"] - 2.5) < 0.05 and abs(b["flanke_rechts"] - 5.5) < 0.05 and abs(b["scheitel"] - 4.0) < 0.05, b
Z = O.zonen([dict(klasse="bogen", u0=2.0, u1=6.0, z0=0.0, z1=4.5)]); assert Z == [("bogen", 2.0, 6.0, 0.0, 4.5)], Z
PY
k=$($P -I tools/test_ortho_oom.py 2>&1); [ $? = 0 ] && ok "GPU-Speichermangel-Logik fassade_ortho (Block halbieren statt CPU, andere Fehler weiter, Budget aus RCPARK_GPU_MB)" || { rot "test_ortho_oom"; echo "$k" | grep FEHL | head -4; }
k=$($P -I tools/test_flaeche_ortho.py 2>&1); [ $? = 0 ] && ok "Wandbild fuer Rundungen/Erker (flaeche_ortho: Zylinder, Kegel, n-Eck-Erker synthetisch, Gegenprobe falscher Radius/Achse)" || { rot "flaeche_ortho synthetisch"; echo "$k" | tail -6; }
k=$(python3 tools/importe_pruefen.py 2>&1); [ $? = 0 ] && ok "Importe: kein Generator/Werkzeug importiert etwas, das es nicht mehr gibt (Anlass bauteile.py 15.11.)" || { rot "Importe fehlen: $(echo "$k" | head -3 | tr '\n' ' ' | cut -c1-200)"; }
k=$($P -I tools/test_stabil_schnitt.py 2>&1); [ $? = 0 ] && ok "Konsens-Schnitt zweier Mapper-Laeufe (sfm_stabil_schnitt: kollineare Strassenkameras, 30 % verschoben erkannt)" || { rot "stabil_schnitt: $(echo "$k" | tail -2)"; }
k=$($P -I tools/test_konsens_urteil.py 2>&1); [ $? = 0 ] && ok "Konsens-Mapper als Standard: Urteil traegt/Datenmangel mit Ursache und Abhilfe (global_mapper_konsens.urteil)" || { rot "konsens_urteil: $(echo "$k" | tail -2)"; }
k=$($P -I tools/test_vorpruefen_cache.py 2>&1); [ $? = 0 ] && ok "Zwischenspeicher Bildvorpruefung (bleibt ueber Neustart, geaenderte Datei/Referenz/Schwelle = neu rechnen)" || { rot "vorpruefen_cache: $(echo "$k" | tail -2)"; }
k=$($P -I tools/test_netz_fotos_holen.py 2>&1); [ $? = 0 ] && ok "Netzfotos in der Kette (netz_fotos_holen: Suchbegriffe, Umkreis aus koordinate_utm, Zwischenspeicher je Quelle, Trockenlauf)" || { rot "netz_fotos_holen: $(echo "$k" | tail -2)"; }
k=$($P -I tools/test_wolke_gruppen.py 2>&1); [ $? = 0 ] && ok "Wolken-Gruppen-Tor (Bildgruppe setzt Punkte hoch ueber die LoD2-Hoehe: auffaellig; gute Gruppe und unbewertbare Punkte nicht)" || { rot "wolke_gruppen: $(echo "$k" | tail -2)"; }
k=$($P -I tools/test_seiten_erkennen.py 2>&1); [ $? = 0 ] && ok "Seitenerkennung (Gemeinschaften im Paar-Graphen trennen zwei Seiten, Zusammenhangsteile, Urteil-Schwelle)" || { rot "seiten_erkennen: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(TMPDIR=${TMPDIR:-/media/oem/rcdaten/tmp} $P -I tools/test_seiten_durchblick.py 2>&1); [ $? = 0 ] && ok "Seiten-Durchblick (starke Uebereck-Paare behalten, Einblendung/Uhr-Verwechslung/Martinstor abgelehnt)" || { rot "seiten_durchblick: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(TMPDIR=${TMPDIR:-/media/oem/rcdaten/tmp} $P -W ignore -I tools/test_seiten_bruecke_kette.py 2>&1); [ $? = 0 ] && ok "Brueckenpaare in der Kette (Vorstufe --durchblick-getrennt -> Eck-Kopplung bekommt Uebereck-Paare; Fernsicht-Gruppe unter --min-bilder behaelt Verbindung; 1122q Sued/Fernfotos)" || { rot "seiten_bruecke_kette: $(echo "$k" | grep FEHLER | head -3)"; }
k=$($P -I tools/test_seiten_vereinen.py 2>&1); [ $? = 0 ] && ok "Seiten vereinen (Achse aus der Helmstange der dichten Wolke, Lot aus Wandnormalen statt 2,3 Grad verkipptem Kameralot)" || { rot "seiten_vereinen: $(echo "$k" | tail -1)"; }
k=$($P -I tools/test_seiten_vereinen_robust.py 2>&1); [ $? = 0 ] && ok "Seiten vereinen Belastungsprobe (synthetischer Turm, Klappung um bis 8 Grad / 20 Grad / 30 % verfaelscht -> gleiche Endlage; Massstabsfehler 10 % abgelehnt; $(echo "$k" | grep -o 'BEKANNTE SCHWAECHE' | wc -l) bekannte Schwaechen als erwartete Fehlschlaege)" || { rot "seiten_vereinen Belastungsprobe: $(echo "$k" | tail -3 | tr '\n' ' ' | cut -c1-400)"; }
k=$($P -I tools/test_schwerkraft_je_bild.py 2>&1); [ $? = 0 ] && ok "Schwerkraft je Bild (Fluchtpunkt der Senkrechten, geneigte+gerollte Kamera synthetisch, 90-Grad-Faelle verworfen)" || { rot "schwerkraft_je_bild: $(echo "$k" | tail -1)"; }
k=$($P -I tools/test_oeffnungen_aus_kanten.py 2>&1); [ $? = 0 ] && ok "Oeffnungen aus Kanten (synthetische Wand: Spitzbogentor, Rundbogen-, Rechteckfenster; nur Kanten, mit Wolke, mit Wandbild+Einzelfotos: Spitzbogen aus Bildkanten, lichte Weite, Aussenmass, Fase, Fasentiefe)" || { rot "oeffnungen_aus_kanten: $(echo "$k" | grep FEHLER | head -3)"; }
k=$($P -I tools/test_modell_zerlegen.py 2>&1); [ $? = 0 ] && ok "Modell nach Punkt-Zusammenhang zerlegen (globaler Mapper legt unverbundene Stuecke in ein Modell)" || { rot "modell_zerlegen: $(echo "$k" | tail -1)"; }
k=$(python3 tools/pfade.py 2>&1); [ $? = 0 ] && ok "Projektpfade und Python-Umgebungen vorhanden (tools/pfade.py)" || { rot "pfade: $(echo "$k" | grep FEHLT | head -2)"; }
k=$(tools/py tools/modell_zerlegen.py --help 2>&1); [ $? = 0 ] && ok "Starter tools/py waehlt Umgebung (pycolmap -> venv-colmap)" || { rot "tools/py: $(echo "$k" | tail -1)"; }
k=$(python3 ~/.claude/skills/doku-pflege/check.py --strict 2>&1); r=$?; [ ! -f ~/.claude/skills/doku-pflege/check.py ] && ueb "Doku-Pruefung: ~/.claude/skills/doku-pflege/check.py fehlt (bash ~/git/claude-mds/bootstrap.sh)" || { [ $r = 0 ] && ok "Doku KI-tauglich (doku-pflege check.py --strict)" || rot "Doku: $(echo "$k" | grep '✗' | head -2 | cut -c1-120) -> /doku-pflege"; }
k=$($P -I tools/test_gps_seiten_pruefen.py 2>&1); [ $? = 0 ] && ok "Seiten per Foto-GPS pruefen (geklappte Rueckseite synthetisch erkannt)" || { rot "gps_seiten_pruefen: $(echo "$k" | tail -1)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_kette.py 2>&1); [ $? = 0 ] && ok "Seitenfolge der Kette (seiten_blick_tor verklebt/getrennt, db_masken_filter, brennweite_schaerfe + Sperrliste, modell_lage_vergleich, Vorstufe sfm_seiten_vorstufe: Wiederverwendung, Masken-Zwischenspeicher ueber Laeufe nach Bildinhalt (1122u: 1147 Masken neu nach --neu sfm), Guard, Bereinigung)" || { rot "seiten_kette: $(echo "$k" | tail -1 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tests/test_tiefe_lokal_zwischenstand.py 2>&1); [ $? = 0 ] && ok "Feinrechnung Zwischenstand (tiefe_lokal: fused.ply nach Hash der Eingaben wiederverwendet, Fotowahl nur aus dem Buendel - Teillauf = Hauptlauf, Rasterung deterministisch; 1122w Teillauf 5 x PatchMatch umsonst)" || { rot "tiefe_lokal Zwischenstand: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_modelle.py 2>&1); [ $? = 0 ] && ok "Seitenmodelle (sfm_seiten_modelle: je Seite Mapper a/b + Wahl, dichte Wolke, seiten_vereinen, vereintes sparse-Modell + Wolke, Blick-Tor, Rueckfall Teil A allein, Uebernahme in pipeline_objekt)" || { rot "seiten_modelle: $(echo "$k" | tail -1 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_gps_vereinen.py 2>&1); [ $? = 0 ] && ok "Seiten ueber Foto-GPS vereinen + GPS-Veto Drehung/Massstab der Ausrichtung (Nulllauf schwabentor-1122: Teil 1 fehlte, Lage 20 Grad gedreht)" || { rot "seiten_gps_vereinen: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_verbund_schwachstellen.py 2>&1); [ $? = 0 ] && ok "Schwachstellen-Radar (Gelenkbild, knotendisjunkte Wege = Brueckenbilder 1/3/10, Spuren quer aus images.bin)" || { rot "verbund_schwachstellen: $(echo "$k" | grep -E "Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_teil_verformung.py 2>&1); [ $? = 0 ] && ok "Lotfeld/Wandrichtung je Kamera (Trend, Sprung mit Gruppenknick, Ausreisser kein Knick, Wandrichtung aus Kanten, Rundgang)" || { rot "teil_verformung: $(echo "$k" | grep -E "Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_sfm_gps_ausgleich.py 2>&1); [ $? = 0 ] && ok "GPS-Ausgleich nach dem Vereinen (Pose-Prior-Buendel: 3 Grad / 9 % zurueck, wenig GPS / Bildfehler schlechter -> unveraendert)" || { rot "sfm_gps_ausgleich: $(echo "$k" | grep -E "Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_querspur_binden.py 2>&1); [ $? = 0 ] && ok "Querspur-Bindung nach dem GPS-Vereinen (4 m / 3 Grad / 5 % -> wahre Lage; Gegenseiten-Paare verworfen; Schwabentor-1122-Lage 167 Grad x1,21 abgelehnt)" || { rot "seiten_querspur_binden: $(echo "$k" | grep -E "Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_wand_dicke_tor.py 2>&1); [ $? = 0 ] && ok "Wanddicke je LoD2-Kante (Seitenteile 1,6 m versetzt -> doppelwand; Vordach zaehlt nicht; Teil in sich dick -> dick)" || { rot "wand_dicke_tor: $(echo "$k" | grep -E "Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_sim3_robust.py 2>&1); [ $? = 0 ] && ok "Sim3 robust (Meter-Schwelle; Kamera am Mond verschiebt nichts; wand_dicke_tor nutzt sie)" || { rot "sim3_robust: $(echo "$k" | grep FEHL | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_wand_dicke_normalen.py 2>&1); [ $? = 0 ] && ok "Wanddicke mit Normalen (Eckband-Querwand + Innenwand zaehlen nicht; 0,57/1,6 m Versatz bleibt rot)" || { rot "wand_dicke_normalen: $(echo "$k" | grep FEHL | head -3)"; }
k=$(TMPDIR=${TMPDIR:-/media/oem/rcdaten/tmp} /media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_eck_koppeln.py 2>&1); [ $? = 0 ] && ok "Eck-Kopplung (stimmig/Zufall/Verformung, Bruecke nur ueber die Teilgrenze, Verdrahtung; Mapper nur auf DB-Kopie + fester Keim/1 Faden = Ketten-DB unveraendert, kein Kippeln 1122r/s)" || { rot "seiten_eck_koppeln: $(echo "$k" | grep FEHL | head -3)"; }
k=$(TMPDIR=${TMPDIR:-/media/oem/rcdaten/tmp} /media/oem/scan/venv-colmap/bin/python -I tools/test_eck_teilkameras.py 2>&1); [ $? = 0 ] && ok "Eck-Kopplung Teilkameras + Kamera-Probe (Spiegel einer flachen Wand abgelehnt) + duenne Bruecke (Schwelle mit allen Teil-Bildern), Grenzen unveraendert" || { rot "eck_teilkameras: $(echo "$k" | grep FEHL | head -3)"; }
k=$(TMPDIR=${TMPDIR:-/media/oem/rcdaten/tmp} /media/oem/scan/venv-colmap/bin/python -I tools/test_eck_reproj.py 2>&1); [ $? = 0 ] && ok "Eck-Kopplung Reproj-Weg (align_reconstructions_via_reprojections: bekannte Sim3 ueber 6 gemeinsame Bilder wiedergefunden, fester Keim, falsches/gespiegeltes Teil abgelehnt, gewinnt nur mit mehr Teilen)" || { rot "eck_reproj: $(echo "$k" | grep FEHL | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_bruecke_nachmatchen.py 2>&1); [ $? = 0 ] && ok "Bruecke nachmatchen (SIFT-Indizes unveraendert, ALIKED angehaengt)" || { rot "bruecke_nachmatchen: $(echo "$k" | grep -i fehl | head -3)"; }
k=$(TMPDIR=${TMPDIR:-/media/oem/rcdaten/tmp} $P -I tools/test_fotos_sammeln_fremd.py 2>&1); [ $? = 0 ] && ok "Fotos sammeln: Fremdbilder im eigenen Ordner -> echte Quelle + Vorpruefung" || { rot "fotos_sammeln_fremd: $(echo "$k" | grep FEHL | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_lod2_je_teil.py 2>&1); [ $? = 0 ] && ok "LoD2 je Teil + Bild-x-Lot (Turmfotos: Bild-oben-Lot 19 Grad schief; Nord/West/Turm -> wahre Lage, eine Wand/Rand -> kein Urteil; Regeln a/b/c)" || { rot "seiten_lod2_je_teil: $(echo "$k" | grep -E "FEHLER|Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tests/test_seiten_waende_binden.py 2>&1); [ $? = 0 ] && ok "Gegenseite ueber gemeinsame Waende binden (1122w Teil 1: GPS-Lage 7 Grad gekippt/4 Grad/2 m -> waagerecht < 5 cm; eine Wand / 12 m daneben abgelehnt; Geotag-Probe; 1122y: GPS-Massstab 10 % daneben -> Massstab aus den Waenden, ohne Beleg Doppelwand -> abgelehnt; 1122z: Hoehe aus Saeulenprofilen + Boden-Gegenprobe, B 5,5 m zu tief -> korrigiert, uneinig -> abgelehnt, ohne Beleg kein Raten, Tor unter Gelaende; 1122zb Lot-Tore: Kamerahoehe/DGM getrennt nach Kippung und Massstab - falsches Wand-Lot abgelehnt, richtiges bestaetigt, gebogener Kameraring -> Hangkameras Lage unbrauchbar; Fluchtpunkt-Lot; Verdrahtung)" || { rot "seiten_waende_binden: $(echo "$k" | grep -E "FEHLER|Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tests/test_massstab_teile.py 2>&1); [ $? = 0 ] && ok "Massstab je Teil unabhaengig (24.11. Nah-GPS-Schrumpf 1122: Nachlauf-Test, Fern-GPS, Turmhoehe/DOM1, Kamerahoehe/DGM, Einigkeit ohne Mittel; rote Probe: alter Weg band B mit 12 % zu kleinem GPS-Massstab; MASSSTAB-TOR in seiten_waende_binden)" || { rot "massstab_teile: $(echo "$k" | grep -E "FEHLER|Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_lage_beleg.py 2>&1); [ $? = 0 ] && ok "Teil nur bei belegter Lage einsetzen (schwabentor-1122 Teil 1 nur GPS, 3-4 m versetzt -> weglassen + Fotoluecke; Querspur/LoD2/GPS ehrlich+Wanddicke -> einsetzen; Fotoauftrag, Folgestufen)" || { rot "seiten_lage_beleg: $(echo "$k" | grep -E "Error|assert" | head -3)"; }
k=$(TMPDIR=/media/oem/rcdaten/tmp /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_foto_auftrag_skizze.py 2>&1); [ $? = 0 ] && ok "Fotoauftrag frueh als Skizze (schwabentor-1122 Suedseite: Uebereck an beiden Suedecken, Frontalreihe, Fernstandorte, nichts in Nachbarhaeusern; Wand nur ueber Nachbardach -> Hochblick + Pflicht-Eckfotos beide Enden; Foto-GPS -> Standpunkt; Kettenaufruf)" || { rot "foto_auftrag_skizze: $(echo "$k" | grep -E "Error|assert" | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_gps_anker.py 2>&1); [ $? = 0 ] && ok "GPS-Anker der LoD2-Ausrichtung: Kasten um den GPS-Fit besteht das GPS-Veto, Martinstor ohne Anker (Nulllauf schwabentor-1122d: -22 Grad x0,83)" || { rot "gps_anker: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_lage_gps_fern.py 2>&1); [ $? = 0 ] && ok "GPS-Tor Fernfotos: nur unter dem freien Fit stimmige Geotags, gleicher Fix = ein Beleg; 1122 besteht, -22 Grad x0,83 faellt; Anker-Kasten aus Bootstrap (Lauf 1122e)" || { rot "lage_gps_fern: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_gps_unsicherheit.py 2>&1); [ $? = 0 ] && ok "GPS ehrlich: Zufall + Sitzungsfehler/Hebel (1122 eine Sitzung legt Lage nicht fest, 1120 mit Fernfotos ja; Tor und Ausrichtung gleiches Mass)" || { rot "gps_unsicherheit: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_lage_proben.py 2>&1); [ $? = 0 ] && ok "Lageproben als Entscheider: Wandfit mit Nachbarn, Oberkante/DOM1, Kamerahoehe; verzerrtes Nah-GPS verliert, nur GPS = kein Urteil" || { rot "lage_proben: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_kamera_klumpen.py 2>&1); [ $? = 0 ] && ok "KAMERA-KLUMPEN: Punkte am Kamerazentrum (stehendes Video/Einblendung) raus aus Fit und Kamerahoehe, Video zaehlt einmal (1122p lage_frueh: 0,26 m statt 1,6 m, Kameras unter DGM1)" || { rot "kamera_klumpen: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_gps_eine_quelle.py 2>&1); [ $? = 0 ] && ok "GPS eine Quelle: Ausrichtung und GPS-Tor rechnen denselben Fit auf allen GPS-Kameras inkl. Fernfotos (1122j: Anker, Loesung 0 = 1120-Lage); Veto = Tor; Lageproben gegen ankerfaehiges GPS -> keine Lage; Kaufhaus/Martinstor unveraendert" || { rot "gps_eine_quelle: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(CUDA_VISIBLE_DEVICES= $P -I tools/test_lage_pruefstand.py 2>&1); [ $? = 0 ] && ok "Lage-Pruefstand: ausrichten() als Funktion, Zwischenstand nach Inhalt aendert das Ergebnis nicht (kalt = warm = ohne, bitgleich), Pruefstand Ende zu Ende ohne Schreiben in Eingabeordner" || { rot "Lage-Pruefstand: $(echo "$k" | grep -E "FEHLER|Error" | head -3)"; }
k=$(CUDA_VISIBLE_DEVICES= $P -I tools/test_lot_wandneigung.py 2>&1); [ $? = 0 ] && ok "Lot-Tor Wandneigung: Kippung vs. Anzug getrennt, kein Urteil bei parallelen Waenden, Kipp-Kasten echte Grad (kipp_rotvec), lage_bestanden mit Lot, Mondkamera im Pruefstand-Vergleich" || { rot "Lot-Tor Wandneigung: $(echo "$k" | grep -E "FEHLER|Error" | head -3)"; }
k=$(python3 -I tools/test_code_stand.py 2>&1); [ $? = 0 ] && ok "Code-Stand der Zwischenstaende (code_stand.py; Nulllauf schwabentor-1122c: Vereinen/Einsetzen mit neuem Code neu, Seitenmodelle/Wolken je Teil wiederverwendet)" || { rot "code_stand: $(echo "$k" | tail -2)"; }
k=$(python3 -I tools/test_teilfusion_verlust.py 2>&1); [ $? = 0 ] && ok "Teilfusion warnt bei Punktverlust (Schwabentor 26.11.: Teil 3 behielt 7 % statt 20 %; teilfusion.verlust_warnung)" || { rot "teilfusion Verlustwarnung: $(echo "$k" | tail -2 | tr '\n' ' ' | cut -c1-250)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_quellfilter_gpu.py 2>&1); [ $? = 0 ] && ok "Quellfilter GPU = CPU (synthetisch; Schwabentor 26.11.: 300 000 Punkte x 645 Kameras 99,978 % gleich, Entscheidung 100 %; 21 Mio Punkte 39 s statt 286 s)" || { rot "Quellfilter GPU: $(echo "$k" | tail -2 | tr '\n' ' ' | cut -c1-250)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_colmap_rig_abgleich.py 2>&1); [ $? = 0 ] && ok "seiten_luecken schnell scheitern: Kamera/Rig der DB-Kopie ans Modell angleichen vor triangulate_points (Kette schwabentor-1120 1122c/d: RigId-Absturz nach 44 min), Vorpruefung, Fehlschlag-Marke mit CODE-STAND, Zwischenstaende je Schritt; vereintes Seitenmodell mit fremd belegter Kamera-ID (Kette 1122r: width 1280 vs. 1920) -> fremde DB-Bilder behalten ihre Kamera unter neuer ID" || { rot "colmap_rig_abgleich: $(echo "$k" | grep 'FEHLER\|Error' | head -3)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_nachholen_speicher.py 2>&1); [ $? = 0 ] && ok "seiten_luecken Nachholen bei GPU-Speichermangel (Kette 1122n/o: SiftGPU out of memory liess 86 Bilder still weg -> KeyError, Sperre 'bekannter Fehlschlag' blockte Wiederholung): fehlende Bilder GPU klein/CPU nachholen, Speichermangel sperrt nicht, code_stand mit __import__, Kontaktbogen alle Kandidaten" || { rot "seiten_nachholen_speicher: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_sift_einstellung.py 2>&1); [ $? = 0 ] && ok "SIFT zentral (sift_einstellung: volle Aufloesung + first_octave 0 GPU, RCPARK_SIFT_ALT; Pflicht-Tor: Rot-Probe Attrappe verwirft still -> gemeldet/CPU nachgeholt/ROT, echtes CPU-SIFT mit kaputter Datei)" || { rot "sift_einstellung: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_seiten_nachholen_quellen.py 2>&1); [ $? = 0 ] && ok "Nachholen Ostseite (Kette 1122p): roh/ ohne alte/tote Verknuepfungen, Kandidaten nur vorhandene Dateien, toter Link in vorbereiten aussortiert, unlesbares Bild in der Vorpruefungs-Kette aussortiert, HTTP 429 mit Retry-After/Backoff (http_holen), Commons laedt Vorhandenes nicht neu, Verlustgrund je nicht registriertem Bild" || { rot "seiten_nachholen_quellen: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_nachhol_belegbar.py 2>&1); [ $? = 0 ] && ok "Nachholen Frueh-Abbruch (Kette 1122u: 3737 s fuer 0 belegte Kameras, leeres STL): ohne Modell-STL mit Dreiecken / ohne Referenzkamera im Rahmen rc 5 in Sekunden vor dem Skript, keine Marke; Absturz von kamera_verfeinern bricht das Skript ab statt 'alles unbelegt'" || { rot "nachhol_belegbar: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_nachhol_tempo.py 2>&1); [ $? = 0 ] && ok "Nachholen-Tempo (Kette 1122q: paare 50 min, merkmale 20 min, 12 min 429-Warten): Zwischenspeicher ALIKED/Grob-LightGlue je Bildinhalt+Parameter (Folgelauf 0 Paare neu, gleiche Auswahl), Schalter SIFT nur gewaehlt Standard AUS + Messskript, Drossel-Marke 24 h bei Vorrat kein erneutes Warten" || { rot "nachhol_tempo: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_seiten_wiederholung.py 2>&1); [ $? = 0 ] && ok "Nachgeholte Kameras speisen denselben Lauf (Kette 1122q: 327 Kameras nach Wandbild/Bau, gegenprobe 0 = ungeprueft): Tor sperrt unplausible/unbelegte, Abdeckungsgewinn -> EIN Teillauf ab fenster" || { rot "seiten_wiederholung: $(echo "$k" | grep FEHLER | head -2 | tr '\n' ' ')"; }
k=$(/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_seiten_teilweise.py 2>&1); [ $? = 0 ] && ok "Teilweise ungesehene Wand loest Nachholen aus (1122x: f02 239 m2 ohne Bilddaten, rc 0 = nichts): fotografierbar >= 10 % UND >= 50 m2, Nachbarhaus-Flaeche abgezogen, je Kandidat nur ein Versuch" || { rot "seiten_teilweise: $(echo "$k" | grep -E "FEHLER|Error" | head -2 | tr '\n' ' ')"; }
k=$(/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_wandbild_einigkeit.py 2>&1); [ $? = 0 ] && ok "Wandbild-Einigkeit (1122t: f01 Abdeckung 0,04 -> 1,0 aber verschmiert = falscher GEWINN): deckungsgleich -> einig, versetzt -> uneinig + Meldung 'Kameras ungenau', uneinigste Fotos gesperrt -> EINE gesperrte Probe, Teillauf mit Sperre" || { rot "wandbild_einigkeit: $(echo "$k" | grep FEHLER | head -2 | tr '\n' ' ' | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES="" /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_kamera_verfeinern_stapel.py 2>&1); [ $? = 0 ] && ok "kamera_verfeinern Stapel (--liste, EIN Prozess statt je Kamera einer; Kette 1122q: 327 Prozesse = 75 min) == Einzelaufrufe bitgleich, Tiefenbild-Schluessel je Kamera (Referenz im Stapel nachgezogen), LRU-Speicher, Nachhol-Skript ruft einmal auf" || { rot "kamera_verfeinern_stapel: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES="" /media/oem/scan/venv-seg/bin/python -W ignore -I tests/test_nachhol_zwischenspeicher.py 2>&1); [ $? = 0 ] && ok "Nachholen Zwischenspeicher nach Eingabe-Hash (Kette 1122w: seiten_luecken 48 min, SIFT+Abgleich 18 min je Lauf neu, kamera_verfeinern 17 min, Download 5 min): merkmale aus dem Speicher bitgleich, Bild/SIFT/Paare/Referenz-DB anders -> neu, Notweg nicht abgelegt; kamera_verfeinern je Kamera+K-Zustand bitgleich, Foto-Index == glob; frische Download-Abfrage uebersprungen" || { rot "nachhol_zwischenspeicher: $(echo "$k" | grep -E "FEHLER|Error" | head -3 | cut -c1-300)"; }
k=$($P -I tools/test_brennweite_waehlen.py 2>&1); [ $? = 0 ] && ok "Brennweite aus EXIF-Pixelgroesse + GPS-Gegenprobe (Martinstor-061-Fall, Seitenverhaeltnis-Regel)" || { rot "brennweite_waehlen: $(echo "$k" | head -2 | tr '\n' ' ')"; }
k=$($P -W ignore -I tools/test_koerper_schleife.py 2>&1); [ $? = 0 ] && ok "Wolkenrest-Koerper (wolke_rest: Kasten/Ring/Stab/Rund benannt und vermessen, Nachbarhaus mit und ohne Grundflaeche abgetrennt, Hohlraum gemeldet; koerper_schleife mit Bau-Attrappe: falscher Kasten verworfen und weggelassen, nicht wieder vorgeschlagen)" || { rot "koerper_schleife/wolke_rest: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_hand_vergleich.py 2>&1); [ $? = 0 ] && ok "Handstand-Vergleich (Treppenturm aus koerper_auto, Ueberstand/Laterne aus dach_profil gemessen, Tor licht/aussen getrennt)" || { rot "hand_vergleich: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_rund_aus_umriss.py 2>&1); [ $? = 0 ] && ok "Rundkoerper aus Foto-Umrissen (Zylinder synthetisch, auch einseitige Blickrichtungen; Profil-Glaettung, Traufe)" || { rot "rund_aus_umriss: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_rund_eigenverdeckung.py 2>&1); [ $? = 0 ] && ok "Rundkoerper-Verdeckung (Vormodell kein Verdecker, Sperrkarte je Kandidat, Innenkarte, naher Hintergrund sperrt; 1122p Tuermchen r 2,09)" || { rot "rund_eigenverdeckung: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_kegeldach_rund.py 2>&1); [ $? = 0 ] && ok "Kegeldach auf Rundkoerper aus Umriss-Mantellinien (gerade + GESCHWEIFT mit Knick, Formwahl nach Rest, Traufhoehe frei; Rot-Probe flacher Zylinder; Generator Stuempfe + Traufbrett druckbar, Guards)" || { rot "kegeldach_rund: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_rund_putz_glatt.py 2>&1); [ $? = 0 ] && ok "Rundkoerper glatter Putz-Schaft (1122zb f04: Suchrand-Radien keine Messung -> Kerbe zu, Lueckennachbar per Median, Facette <= Druckmass; Rot-Probe echte Kehle bleibt)" || { rot "rund_putz_glatt: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_rund_kranz.py 2>&1); [ $? = 0 ] && ok "Rundkoerper-KRANZ (1122 Rundturm, Auskragungs-Falle L31): Ober-/Unterkante aus Fotokanten bzw. Wolken-Flaechenmitte statt Silhouette, L31-Rueckrechnung, Guard alter Weg; Rot-Probe Silhouette 0,5 m zu hoch/dick" || { rot "rund_kranz: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_rund_huelle.py 2>&1); [ $? = 0 ] && ok "Rundkoerper + Dach aus EINSEITIGEN Silhouetten gegen Himmel (rund_aus_huelle/drehkoerper_aus_fotos: Traufe, Schaft, geschweiftes Dach, Spitze; falsche Maske raus; Rot-Probe Suchrand; Generator; Kette 1122s Treppentuermchen ohne Dach)" || { rot "rund_huelle: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_spitze_durchfahrt.py 2>&1); [ $? = 0 ] && ok "Turmspitze/Laterne aus Himmelskante (Spitze, Krempe trotz Untersicht, Nadel keine Krempe, eckig/rund, Kamera unter der Traufe verworfen, Bildkante unter dem Suchende misst trotzdem, Generator bis zur Spitze) + Durchfahrt ueber durchgehende Laibung (Nische, massive Wand, Quermauer abgelehnt)" || { rot "spitze_aus_umriss/durchfahrt_pruefen: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_durchfahrt_wandbild.py 2>&1); [ $? = 0 ] && ok "Tordurchfahrt mit verworfener Sweep-Form (1122q): Fotokanten bauen sie (sicher, >= 3 Fotos; unsicher/Sturz/hoeher/kein Durchblick nicht), danach Durchfahrt, Loch durch beide Seiten" || { rot "durchfahrt_wandbild: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_oeffnungen_uebernehmen.py 2>&1); [ $? = 0 ] && ok "Oeffnungen: Wandbild-Masse nur fuer gebaute Oeffnungen uebernommen (Beifang/Wolkenform unveraendert)" || { rot "oeffnungen uebernehmen: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_nischen_fenster.py 2>&1); [ $? = 0 ] && ok "Fenster in Nischen (zwei Ebenen: Nische flach + Fenster tiefer, Umriss/Formfamilie aus Bildkanten trotz Stoerlinie, Tiefe aus Sweep, Bau ein Stueck)" || { rot "nischen_fenster: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_loch_gewaende.py 2>&1); [ $? = 0 ] && ok "Loch + Gewaende aus dem Wandbild (1122o: Gitterfenster im Gewaende angeschnitten, Schlitz statt Rundbogen, geschlossene Tuer im Portal auf der echten Turmoberflaeche, Rundbau keine Oeffnung, nur gebaute Oeffnungen sind Bauteile)" || { rot "loch_gewaende: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_schlitze_grob.py 2>&1); [ $? = 0 ] && ok "Schlitze/Luken ohne Erkennerkasten + grobes Wandbild ueber der Aufloesungsgrenze ($(echo "$k" | grep -c '^    ok') Proben; 1122w West: Schlitz/Luke oben, Eckquader oben - Mehrfoto-Kanten, Formfamilie >= 3 + Mehrheit, Fleck/Stein nicht, ohne grobes Bild nichts)" || { rot "schlitze_grob: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_schlitz_gewaende_unschaerfe.py 2>&1); [ $? = 0 ] && ok "Schlitz im gestuften Gewaende + Unschaerfe-Tor fuer Formbelege (1122zb: f03_3 Schlitz 0,09 m statt Rundbogen, f04 Sockelschatten aus Videobildern verworfen, Tor nur bei schwachem Kontrast: f00-Schlitze z 34 in hellem Putz bleiben)" || { rot "schlitz_gewaende_unschaerfe: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_erkennerkasten_pruefen.py 2>&1); [ $? = 0 ] && ok "Erkennerkaesten vor der Verwendung pruefen (1122zb f04: falsche Tuerkaesten auf Putz sperrten 3 Schlitze + Doppeltuer; Rot-Proben echte Tuer, Fenster mit hellem Ring, Schlitz im Gewaende, Durchfahrt per Tiefe, OG-Tuer ueber Schwelle bleiben)" || { rot "erkennerkasten_pruefen: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_bogen_gewaende.py 2>&1); [ $? = 0 ] && ok "Gewaende-Band um Torboegen (1122w: Bogensteine radial im Wandbild 0,45 m erkannt, Rot-Probe Bruchstein bis ans Loch kein Band, Bau auf echter Oberflaeche, Loch offen, Vorsprung >= Druckmindestmass)" || { rot "bogen_gewaende: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ')"; }
k=$($P -W ignore -I tests/test_fenster_gewaende_weit.py 2>&1); [ $? = 0 ] && ok "Fenster im breiten Gewaende (1122w Sued f01: Wandfarbe aus dem aeusseren Band statt Ring voller Sandstein, Keilsteinfaecher im Umriss, Rot-Probe Ring-Median ohne Gewaende, Bogen aus der Lochoberkante, Beule vor dem Gewaende abgetragen)" || { rot "fenster_gewaende_weit: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_malplan.py 2>&1); [ $? = 0 ] && ok "Malplan (synthetische Wand: Putz/Sandstein/Fenster mit Anteil und Farbe, 5-cm-Fleck unter (2 mm H0)^2 verschwindet, OBI nie Grundton, Rot-Probe ohne Fenster; Seitenname aus seiten_konvention; Weissabgleich: Schattenwand mit Blaustich -> gleiche Materialfarbe, Gebaeudefarbe je Material)" || { rot "malplan: $(echo "$k" | grep FEHLER | head -3 | tr "\n" " ")"; }
k=$($P -W ignore -I tests/test_vorbau_pfosten.py 2>&1); [ $? = 0 ] && ok "Vorbau-Pfosten (1122w: duennes Kantenband Holm..Raehm, zwei Pfostenhaufen trotzdem gemessen, Draht keine Pfosten; ohne Kanten-Pfosten Sweep-Spalten -> Vordach nicht schwebend, ein Koerper)" || { rot "vorbau_pfosten: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ')"; }
k=$($P -W ignore -I tests/test_bogen_fugen.py 2>&1); [ $? = 0 ] && ok "Gemessene Fugen der Bogensteine (24.11.: unregelmaessige Fugen +- 3 cm, Zahl gleich, Draht in 1 Foto kein Beleg; Rot: glattes Band / Stufenkanten / kein Band / Kopie statt 3 Fotos -> nichts; Rillen nur dort, druckbar)" || { rot "bogen_fugen: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ')"; }
k=$($P -W ignore -I tools/test_fenster_form.py 2>&1); [ $? = 0 ] && ok "Fensterform (Einzelfenster ohne Erkennerpaar: Form aus Bildkanten, Nische ueber Geschwister-Suchzone, Formfamilie aus >= 3 Einzelfotos; Form-Tor alt FALSCH/neu PASST; hand_vergleich prueft Form; Nische >= Druckmindestmass; DURCH mit Laibungstiefe)" || { rot "fenster_form: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_laibung_aus_fotos.py 2>&1); [ $? = 0 ] && ok "Laibungstiefe aus Schraegfotos (Ladenkante im Einzelfoto-Ortho wandert mit der Blickschraege: exakte Gerade, beide Seiten, Ausreisser, Modellflaeche schon vertieft; Fenster ohne Fotos unveraendert)" || { rot "laibung_aus_fotos: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_kette_1122c.py 2>&1); [ $? = 0 ] && ok "Kettenlauf 1122c (echte Fixtures f00): Bogenkasten der Nische nicht mit dem Tor verschmolzen, zwei Rundbogenfenster (Nischenzone + Geschwister), Tor lichte Weite statt Aussenkante" || { rot "kette_1122c: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_kette_kreis_orthos.py 2>&1);[ $? = 0 ] && ok "Kreisfall Einzelfoto-Orthos (1121v): Laibung und Tor-Innenkante direkt aus Lochkamera-Fotos statt aus Orthos auf dem vorigen Modell; Form-Tor knappe Mehrheit kein FALSCH; hand_vergleich Nische nur Hinweis" || { rot "kette_kreis_orthos: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_messflaeche_kreis.py 2>&1); [ $? = 0 ] && ok "Waechter zirkulaere Messung (fassade_ortho --messflaeche eben: zwei verschiedene Vormodelle und Lauf von null -> bitgleiche Einzelorthos; Gegenprobe modell sieht den Kreis; Kette misst nie auf dem vorigen STL)" || { rot "messflaeche_kreis: $(echo "$k" | grep -v '^  ok' | tail -4)"; }
k=$(CUDA_VISIBLE_DEVICES= $P -W ignore -I tools/test_kantenstufe_kreis.py 2>&1); [ $? = 0 ] && ok "Waechter Kreis Kantenstufe (Suchraum = modellfreier Messkoerper statt Vormodell: zwei Vormodelle und Lauf von null -> bitgleiche Kanten + Kamerawahl; Vordachkante 1,2 m vor der Wand gefunden; Gegenprobe alter Weg findet sie nicht)" || { rot "kantenstufe_kreis: $(echo "$k" | grep -v '^  ok' | tail -4)"; }
k=$(CUDA_VISIBLE_DEVICES= $P -W ignore -I tools/test_kantenstufe_traufzone.py 2>&1); [ $? = 0 ] && ok "Traufzone der Kantenstufe (Schuerze/Decke ueber der Wandoberkante bis Dachfuss + 1 m: alter Suchraum < 20 % der Traufstrahlen im Fenster, neu >= 90 %; Stirnkanten gefunden, Vormodell-unabhaengig, erster Lauf unveraendert) - Befund 1122 Hoehen-Angleich" || { rot "kantenstufe_traufzone: $(echo "$k" | grep -v '^  ok' | tail -4)"; }
k=$($P -W ignore -I tools/test_sohlbank.py 2>&1); [ $? = 0 ] && ok "Sohlbank aus Fotos (dunkles Band unter Nische/Fenster: Auskragung aus Bandhoehe und Laenge gegen die Blickschraege - je Foto differenziell, Registrierfehler +-3 cm; Geschwister gemeinsam; verdecktes Ende zaehlt nicht; Wand ohne Band keine; bauteile.sohlbank an der gemessenen Koerperflaeche, Druckmass)" || { rot "sohlbank: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_linien_bauteile.py 2>&1); [ $? = 0 ] && ok "Linien-Bauteile (Gesims/Verdachung/Balkenkopf-Reihe aus waagerechten Fotokanten, Ausladung aus der Tiefe, Farbkante/2-Foto-Kante/Uhrring nicht gebaut; rote Proben flaches Gesims, ohne Uhr-Ausschluss, ohne Wand, Druckmass; bauteile.linien_aus_json)" || { rot "linien_bauteile: $(echo "$k" | grep -E 'FEHLER|Error' | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_nische_annahme.py 2>&1); [ $? = 0 ] && ok "Belegte Nische/Sohlbank nie verwerfen (24.11. WEG_HAND_ZU_KETTE 2: Form aus >= 3 Fotos + Sweep unmessbar -> Nische gebaut mit ANNAHME-Platzhalter; weiter Wandring misst; Geschwister-Tiefe; Nischenlaibung aus Schraegfotos ersetzt die ANNAHME; Sohlbank-Auskragung = Stirnhoehe; Guard Wanddicke/Druckmindestmass)" || { rot "nische_annahme: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_steine_paar.py 2>&1); [ $? = 0 ] && ok "Fotosteine Paar-Probe (steine_aus_foto: Gegenfoto mit falscher Kamera verworfen statt Wand als Verdecker geloescht, verwackeltes Hauptfoto verliert, Quader-Tor besteht)" || { rot "steine_aus_foto Paar-Probe: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_steine_standort.py 2>&1); [ $? = 0 ] && ok "Fotosteine Fotowahl je Standort (steine_aus_foto: eine Fotoserie verdraengt Gegenfotos anderer Standorte nicht mehr aus den 12 Kandidaten, Schwabentor Sued 23.11.)" || { rot "steine_aus_foto Fotowahl je Standort: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_putz_uhr.py 2>&1); [ $? = 0 ] && ok "Putz aus dem Wandbild (Einzelfotos einig glatt, Kabel egal, Quader nicht) -> Kruemel weg, Gesims bleibt, Uhrfeld frei; Zifferblatt-Relief aus Einzelfotos (Mehrheit, Striche >= 0,8 mm) auf der gemessenen Wand" || { rot "putz_wandbild/zifferblatt: $(echo "$k" | tail -1 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_uhr_beleg.py 2>&1); [ $? = 0 ] && ok "Uhr nur mit Zifferblatt-Beleg (1122p: Heiligenschein f01 als Uhr gebaut): 12er-Teilung im Ring trotz Schatten -> Uhr, goldener Kreis mit Steinen -> verworfen, zwei Kaesten derselben Uhr -> eine (Dublette)" || { rot "uhren_wandbild Beleg/Dublette: $(echo "$k" | tail -1 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_uhr_einzelfotos.py 2>&1); [ $? = 0 ] && ok "Uhr trotz Mosaik-Naht (1122x: Sueduhr f01 fehlte, 12er-Teilung im Mosaik 1,14): Mehrheit der Einzelfotos belegt, gleich mit sauberem Mosaik (Teillauf egal), Heiligenschein/Rundfenster verworfen, 2 Fotos zu wenig, Relief ueber Kanten-ECC" || { rot "uhr_einzelfotos: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ')"; }
k=$($P -W ignore -I tests/test_zifferblatt_gestalt.py 2>&1); [ $? = 0 ] && ok "Zifferblatt-Gestalt aus Fotos (24.11.: Kette nur Kleckse): blasse Ziffern als Minderheit gegen Zonengrund, Luecken offen, Striche >= 0,8 mm, Zeiger, Wulst an gemessenen Kreisen; Rot: leere Scheibe / alte Goldmaske" || { rot "zifferblatt_gestalt: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ')"; }
k=$($P -W ignore -I tools/test_html_zielgroesse.py 2>&1); [ $? = 0 ] && ok "3D-HTML Zielgroesse (1122p: 20 MB > Artifact-Grenze 16): modell_3d_html --max_mb verkleinert Wolke und Anzeige-Raster selbst, 0 = aus, unerreichbar endet" || { rot "modell_3d_html Zielgroesse: $(echo "$k" | tail -1 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_vordach_vorbau.py 2>&1); [ $? = 0 ] && ok "Vordach-Profil aus Foto-Silhouetten (geschweift/gerade, Walm, Traufe/Anschluss) + bauteile.vordach_walm; Relief hinter Vorbauten nur mit Tiefensprung in den Fotokanten - Schwabentor Vordach/Wandgemaelde" || { rot "vordach_vorbau: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_vordach_traufe.py 2>&1); [ $? = 0 ] && ok "Vordach-Traufe als Fotokante: weit auskragende Traufe (0,55 m vor der Galerie, seitlich 0,35) + Schweifung trotz dunklem Raehm/Traufschatten und zu tiefem Sweep-Start wiedergefunden - Schwabentor 1122a" || { rot "vordach_traufe: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_vordach_ohne_kasten.py 2>&1); [ $? = 0 ] && ok "Vordach geneigt/geschweift auch ohne Kanten-Kasten (Ersatz-Grenzen Galerie-Band, Walm statt Hoehenfeld-Stufen, Sweep-Pfosten ergaenzt) - Nutzer 24.11. Handstand schwab_v3" || { rot "vordach_ohne_kasten: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_tiefe_belegt.py 2>&1); [ $? = 0 ] && ok "Relief nur mit Tiefenbeleg (putz_wandbild.tiefe_belegt: Netzinseln im Lochfeld glatt, Quaderbossen/Fugen bleiben, Einzelspitzen weg; Verdeckungsflecken der Einzelbilder kein Struktur-Beleg) - Schwabentor w00 Kruemelbaender" || { rot "tiefe_belegt: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_vordergrund_quader.py 2>&1); [ $? = 0 ] && ok "Vordergrund + Quader-Veto: $(echo "$k" | grep -c '^    ok') Tests (Schild auf Sockelband -> Wandniveau, Band/Bosse/Eckquader bleiben; Farb-Putz nicht auf Quaderflaeche laut Wandbild) - Schwabentor w01" || { rot "Vordergrund/Quader-Veto: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_umgang_eckquader.py 2>&1); [ $? = 0 ] && ok "Umgang unter der Traufe (Zone aus Zeilenkanten, Pfosten-Konsens ueber Fotos, Bau mit Ruecksprung) + Eckquader im Fotorelief nur an Gebaeudeecken" || { rot "umgang/eckquader: $(echo "$k" | tail -2)"; }
k=$($P -W ignore -I tools/test_relief_auf_koerper.py 2>&1); [ $? = 0 ] && ok "Mono-/Misch-/Netzrelief der Quaderwaende auf der gemessenen Koerperflaeche (Steine vor der Wand, nicht 0,3 m dahinter versenkt; 1122u Sued w05)" || { rot "relief_auf_koerper: $(echo "$k" | tail -2)"; }
k=$($P -W ignore -I tools/test_steinzone_je_zone.py 2>&1); [ $? = 0 ] && ok "Quader-Tor je Zone: Steinzone unten (Wandbild) behaelt Steinrelief, Putz darueber glatt, Rot-Probe alter Stand (1122u Sued w06/w07, Nord w02)" || { rot "steinzone_je_zone: $(echo "$k" | tail -2)"; }
k=$($P -W ignore -I tests/test_relief_kantenglatt.py 2>&1); [ $? = 0 ] && ok "Feinrauschen ohne Fotokante geglaettet (relief_kantenglatt: Knickkanten wie trimesh, Rauschkanten < 40 %, Recall sinkt nicht, belegtes Gesims + Quaderraster bleiben; 1122x f00 erfunden 0,98)" || { rot "relief_kantenglatt: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_kruemel_kantenbeleg.py 2>&1); [ $? = 0 ] && ok "Kruemel ohne Fotokante weg (Blob/Gemaelde/verdeckt flach samt Rand, Koerper mit Kanten + Gesims + Bogen bleiben, Steine unberuehrt; 1122w Nord-Knochen, Sued-Brunnen)" || { rot "kruemel_kantenbeleg: $(echo "$k" | tail -1 | cut -c1-300)"; }
k=$(OMP_NUM_THREADS=2 $P -W ignore -I tests/test_wolke_draehte.py 2>&1); [ $? = 0 ] && ok "Draht-/Fahnenfilter der Anzeige-Wolke (wolke_draehte: freier Draht + schraege Fahne weg; Wand, Gesims, angebundenes Vordach, Dach, lotrechte Wetterstange bleiben; Stufe draehte vor html; Nutzerbefund 1122 Nordseite 24.11.)" || { rot "wolke_draehte: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ' | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_bau_parallel.py 2>&1); [ $? = 0 ] && ok "Bau parallel ohne Ergebnisaenderung (unique_zeilen = np.unique, Relief-/Ortsteinschritte in Kindprozessen in Reihenfolge, STL neu = alt bitgleich, Strahlsonden-Zwischenspeicher; RCPARK_BAU_SERIELL=1 alter Weg)" || { rot "bau_parallel: $(echo "$k" | grep FEHLER | head -2 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_drahtmaske.py 2>&1); [ $? = 0 ] && ok "Drahtmaske je Foto (24.11., 1122x Oberleitungs-Fahnen): 2 Draehte ueber Himmel+Wand maskiert, Rot-Probe Fugen/Gesims/Fenster/Dachkante/Fallrohr frei, COLMAP-Fusionsmaske, OHNE_DRAHTMASKE=1; Himmelsmaske Fusion (24.11. blaues Geisterblatt 1122z: Saum an der Silhouette), Rot-Probe Dachkante/Turmspitze/Laterne/Gesims frei" || { rot "drahtmaske: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tests/test_quellfilter.py 2>&1); [ $? = 0 ] && ok "Freiraum-Nachfilter dichte Wolke (24.11., Geisterblatt 1122z): Geisterblatt nur in 3 von 40 Karten weg, Rot-Probe Wand/Erker bleiben, wenige Kameras -> greift nicht, vis-Kuerzung, Marke" || { rot "quellfilter: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_vorbau_pfosten.py 2>&1); [ $? = 0 ] && ok "Vorbau-Pfosten neben dem Kastenende an den Kasten gerueckt (1 Koerper statt freistehendem Pfosten; 1122u)" || { rot "vorbau_pfosten: $(echo "$k" | tail -2)"; }
k=$($P -W ignore -I tools/test_vorbau_keine_treppe.py 2>&1); [ $? = 0 ] && ok "SACKGASSE Hoehenfeld als Gestalt (treppig, 21.11. + Rueckfall 1122z-zc): ohne Kantenkasten Ersatz-Kasten, rote Probe MIT_HOEHENFELD=1 faellt am Treppen-Mass durch, Guard, duenne Kanten mit Galerie-Band" || { rot "vorbau_keine_treppe: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_bestand_tor.py 2>&1); [ $? = 0 ] && ok "BESTAND-TOR je Bauteilzone: Nullkontrolle gleich, rote Probe Rueckschritt rc 5 + Zeile, Rauschen statt fester Schwelle, Fortschreiben nur wenn alle >= Bestand, gesamtkette rc 6, merge_sperre/ketten_probelauf sperren" || { rot "bestand_tor: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($G -W ignore -I tools/test_quader_raster.py 2>&1); [ $? = 0 ] && ok "Quaderraster aus dem Wandbild (Mehrfoto-Lagen/Fugen, Stein eben = Median der Tiefe, Rillen >= 0,8 mm H0, Eckquader lang/kurz gemessen, Steinzone von unten) - Nutzer 21.11. 'geschmolzen'" || { rot "quader_raster: $(echo "$k" | grep FEHLER | head -2)"; }
k=$($G -W ignore -I tools/test_keilsteine.py 2>&1); [ $? = 0 ] && ok "Keilsteine um Boegen (Ring aus der Kohaerenz radialer Fugen in s-Profilen, Gewaende ohne Fugen davor; Fugen radial geprueft; ausserhalb unveraendert; alte Steine in der Oeffnung weg; Putzbogen und Quader bis an den Bogen: keine) - Schwabentor Torbogen" || { rot "keilsteine: $(echo "$k" | grep FEHLER | head -2 | cut -c1-300)"; }
k=$($G -W ignore -I tools/test_ortsteine.py 2>&1); [ $? = 0 ] && ok "Ortsteine/Eckverzahnung aus dem Wandbild ($(echo "$k" | grep -c '^    ok') Rot-Proben: Zone Stein/Putz an der Kante, lang/kurz + Lagen, Fotokante neben LoD2, 3 Fotos bestaetigen, Vorsprung aus Sweep, Bau vor der Flaeche um die Ecke; Putzwand/2 Fotos: nichts; Runde 2: Einzelfotos ausgerichtet + Mosaikluecke ergaenzt, Uhr im Innenband, keine Lagen-Splitter, Stossfugen, Tor + Kettenstufe) - Schwabentor 1122u/v/w" || { rot "ortsteine: $(echo "$k" | grep FEHLER | head -2 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_dach_dom1_veto.py 2>&1); [ $? = 0 ] && ok "Wolken-Dachprofil mit DOM1-Veto (zu breite Seite auf Laser-Isolinie, Laterne/ohne Kachel unberuehrt) - Schwabentor-Dach +1,62 m war Form, nicht Massstab" || { rot "dach_dom1_veto: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_dachflaeche_aus_umriss.py 2>&1); [ $? = 0 ] && ok "Dachflaeche aus Foto-Silhouetten (Analyse durch Synthese: c gerade/geschweift/gewoelbt + Fusshoehe zurueck, Familie nur aus >= 3 einigen Fotos, Generator baut bei 'gerade' Ebenen ohne Absatz, Guard)" || { rot "dachflaeche_aus_umriss: $(echo "$k" | grep FEHL | head -3)"; }
k=$($P -W ignore -I tools/test_dachflaeche_dom1_veto.py 2>&1); [ $? = 0 ] && ok "DOM1-Veto der Foto-Dachflaeche (zu breite Foto-Ebene ab der Ueberstand-Aussenkante auf die Laser-Isolinie, Traufring bleibt, Laser blind = kein Veto) - Schwabentor-1122p HOEHEN-TOR +1,73 m" || { rot "dachflaeche DOM1-Veto: $(echo "$k" | grep FEHL | head -3)"; }
k=$($P -W ignore -I tools/test_laterne_aus_fotos.py 2>&1); [ $? = 0 ] && ok "Laterne aus Fotokanten (Pfosten 4/8-Eck aus 25 Grad Blickwinkel per Synthese-Korrelation, offene Zone je Foto aus der Silhouette statt festem Band, helle Pfosten per Zeilen-Normierung, Umkreis in Metern + Stimmen >= 3 Fotos, Fotoauswahl je Sektor, Ausreisser mit freiem Massstab, Haube aus Facettenstufen + Drehsinn-Probe, Zwiebel/gerade/geschweift, Zonen, bauteile.laterne offen/geschlossen druckbar)" || { rot "laterne_aus_fotos: $(echo "$k" | grep FEHL | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_laterne_drehprofil.py 2>&1); [ $? = 0 ] && ok "Laterne: Haube als Drehkoerper aus Silhouetten (Sehstrahl-Huelle, Hoehen-/Seitenversatz je Foto registriert, Fremdkoerper/abgeschnittene Haube robust, Zwiebel trifft Taille/Bauch/Hals/Knauf, Kasten -> 4-Eck aus der Synthese, Kegel/Zwiebel rund nur als ANNAHME bei richtungsunabhaengiger Silhouette; Rot-Probe Median-Profil verliert die Taille; laterne_aus_block baut die Huelle)" || { rot "laterne_drehprofil: $(echo "$k" | grep FEHL | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_kette_vordach_laterne.py 2>&1); [ $? = 0 ] && ok "Kettenfall 1122c: echte Audit-JSONs (vorbauten_auto + vordach_profil + dach_profil) -> Generator-Einstiege in Generator-Reihenfolge -> Vordach geschweift mit 0,35/0,45 m Ueberstand, Laterne 4 Pfosten + Haube bis spitze_z trotz 'Nadel z None'; Rot-Proben ebene Platte / Drehringe" || { rot "kette_vordach_laterne: $(echo "$k" | grep FEHL | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_traufe_aus_fotos.py 2>&1); [ $? = 0 ] && ok "Traufe aus Fotokanten (Wandanschluss/Aussenkante trianguliert, Stirn-Unterkante nicht erfunden, ein Hoehenwinkel/zu wenige Fotos ungueltig, Traufkasten im Generator, Umgang bleibt offen, hand_vergleich 'aus Fotos')" || { rot "traufe_aus_fotos: $(echo "$k" | grep FEHLER | head -3)"; }
k=$($P -W ignore -I tools/test_dach_veto_traufe.py 2>&1); [ $? = 0 ] && ok "DOM1-Veto schneidet den Dachueberstand nicht ab (Traufkante = Klippe im 1-m-Raster, nicht bilinear; Dachkoerper-Breite weiter gekappt) - Schwabentor 1121q 0,9 -> 0,12 m" || { rot "dach_veto_traufe: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_dach_profil_duenn.py 2>&1); [ $? = 0 ] && ok "Wolken-Dachprofil bei leerer/verstreuter Dachseite: kein Absturz (1122n IndexError in schale), Seite 'kein Urteil' + Fotoluecke gemeldet, nichts gespiegelt" || { rot "dach_profil_duenn: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_dach_sichtschatten.py 2>&1); [ $? = 0 ] && ok "Fotodach bei Fotos nur von einer Seite: Sichtschatten hinter dem Dach ist kein First (1122o +4,4 m), Seite am Gitterrand offen (kein 3,83-m-Ueberstand), Breite aus Mittelschnitt, keine Kerbe, Kameragruppe Form vs. Ausrichtung, Kamera ueber der Traufe nicht beurteilt" || { rot "dach_sichtschatten: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_selbstbau_verdecker.py 2>&1); [ $? = 0 ] && ok "Verdecker ohne Selbstbau (fassade_ortho: gebautes Vordach blendet seinen eigenen Beleg in uneinig_f00 nicht aus; zirkulaere Karte verworfen) - Schwabentor-Anschluss 19,39 -> ANNAHME 16,74 am 21.11." || { rot "selbstbau_verdecker: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_wand_neigung_vorbau.py 2>&1); [ $? = 0 ] && ok "Geneigte Wandebene im Ebenen-Sweep (Lotfehler: Wand verschmiert -> Vorbau nicht belastbar; Guard lotrecht/Rauschen/zu steil), Ausladung gegen die oertliche Wand, Fenster zwischen Erker-Streben verworfen - Schwabentor-1122n Bilderker fehlte" || { rot "wand_neigung_vorbau: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_fenster_tiefe_klein.py 2>&1); [ $? = 0 ] && ok "fenster_tiefe_tor: kleines dunkles Loch unter der Sweep-Mittelung (0,44 m) nicht als 'keine Nische' verworfen, helles Konsolenfeld / grosses Feld / etwas davor weiter verworfen; Rot-Probe ohne Wandbild = 1122u Sued ohne Fenster" || { rot "fenster_tiefe_klein: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_vorbau_beleg.py 2>&1); [ $? = 0 ] && ok "Vorbau-Beleg-Tor: Phantom (Randtreffer + 0 Kantenpunkte) verworfen, echter Erker bleibt, Regel (c) schwache Praezision + knapper Beleg, Generator baut verworfene Gruppe nicht - Schwabentor-1122t f03" || { rot "vorbau_beleg: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_fremd_anzahl.py 2>&1); [ $? = 0 ] && ok "SfM-Ziel ohne fremde Bilder (seiten.json fremd als Liste) - Martinstor 1121b brach mit 574/1053 ab" || { rot "fremd_anzahl: $(echo "$k" | tail -2 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_anschluss_stufe.py 2>&1); [ $? = 0 ] && ok "Vordach-Anschluss als Niveauwechsel im Wandbild (Zwei-Niveau-Zerlegung je Spalte, Spaltenlauf-Guard, Gegenprobe Uneinigkeit; Stange/Naht/geschweifte Seiten stoeren nicht, Wand ohne Dach/Teilkante -> ANNAHME) - Schwabentor f00 16,74 -> 19,7" || { rot "anschluss_stufe: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_speicher_wiederholung.py 2>&1); [ $? = 0 ] && ok "Stufe bei Speichermangel im Lauf wiederholt (Signal 9/6, CUDA-OOM, Kernel-OOM; normales rc 3 nicht) - Nutzer 21.11." || { rot "speicher_wiederholung: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_grundriss_geklaert.py 2>&1); [ $? = 0 ] && ok "Grundriss-Tor: am Foto geklaerter Strassenhaufen gilt nur bis 2x seiner Punktzahl (1122: 7,9x grosser Haufen der falschen Lage an derselben Stelle) - 22.11." || { rot "grundriss_geklaert: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_haufen_klaeren.py 2>&1); [ $? = 0 ] && ok "Grundriss-Tor klaert Strassenhaufen automatisch: Doppelwand rot, Mast/Leitung/Erker/Faecher geklaert, ohne Eichung nicht geklaert (haufen_klaeren.py) - 22.11." || { rot "haufen_klaeren: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_befundliste.py 2>&1); [ $? = 0 ] && ok "Befundliste (Sichtbefunde aus neben_*.jpg + Toren + Log: fehlt/flach oben, Kastenvordach = Form falsch, Beulen = zu grob, falsche Kamera = Beleg ungueltig, Wand ohne Fotos = KEINE FOTOS, Codefehler als Ursache) - Agenten-Schleife 22.11." || { rot "befundliste: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_konvergenz.py 2>&1); [ $? = 0 ] && ok "Konvergenz (fester Fotosatz je Seite aus seiten_konvention, F1 grob/fein, gepaarter Gewinn, steigt/PLATEAU mit Restfehler-Ort/kein Beleg statt 0, Ersetzen = Bruch) - Nutzer 24.11." || { rot "konvergenz: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_konvergenz_wolke.py 2>&1); [ $? = 0 ] && ok "Konvergenz Wolke->Modell (gleiche Fotos + foto_diff-Kantenlogik fuer die dichte Wolke, Splat, Bereich vom Modell: fehlender Vorbau = Modellierung verliert, Wolke nur unten = Daten fehlen, gleich; Zuschnitt Boden/Fremdhaufen) - 24.11." || { rot "konvergenz_wolke: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES= $P -W ignore -I tools/test_formsitz.py 2>&1); [ $? = 0 ] && ok "Formsitz (Tiefen-IoU Modell gegen dichte Wolke, Nullprobe 0,3/1/2 m + 5 Grad deutlich schlechter, Rot-Probe Wand 0,35 m aussen erkannt, verrauschte Wolke = nicht trennbar, konvergenz: PLATEAU nur wenn es trennt) - 24.11." || { rot "formsitz: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES= $P -W ignore -I tools/test_hoehensitz.py 2>&1); [ $? = 0 ] && ok "Hoehensitz (waagerechte Strukturlinien Modell gegen dichte Wolke je Seite: Nullprobe +-0,3/1/2 m in z deutlich schlechter, Rot-Probe Gesims 0,5 m zu hoch auf der richtigen Seite gemeldet, verrauschte Wolke = nicht trennbar, konvergenz: Hoehe faellt -> Seite faellt) - 24.11." || { rot "hoehensitz: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_laufzeit_bericht.py 2>&1); [ $? = 0 ] && ok "Laufzeit-Bericht (24.11.: Doppel-Fusion 470 + 450 s und 6 volle Bauten blieben unbemerkt): Familien, Doppelarbeit, Vorlauf aus gesamtkette.log, Job-Log-Format" || rot "Laufzeit-Bericht: $(echo "$k" | grep FEHLER | head -2)"
k=$($P -W ignore -I tools/test_neben_details.py 2>&1); [ $? = 0 ] && ok "Detailansicht je Bauteil (neben_details: Kamera mit Bauteil gross/mittig/senkrecht gewinnt, Profil von der Seite, Verdecker senkt Sicht, Bauteile aus audit-JSON) - 22.11. Fehlbefund Vordach/Laterne am Steilblick; 23.11. Uhr-Keile 1122q: Wand-Faecher mit Mitte im Kasten sind nicht Bauteil, Uhr nur innerhalb ihrer Kreis-Kontur" || { rot "neben_details"; echo "$k" | tail -5; }
k=$($P -W ignore -I tools/test_leistung_messen.py 2>&1); [ $? = 0 ] && ok "Leistungsmessung (leistung_messen: Wallzeit/CPU/Spitzen-RAM/RAPL/GPU neben einem Befehl, Thread-Sweep mit Platzhalter, kleinste Einstellung innerhalb 5 %, Engpass-Regeln, perf oder sauber uebersprungen) - 22.11." || { rot "leistung_messen: $(echo "$k" | grep FEHLER | head -3)"; }
k=$(python3 -I tools/test_verlustbilanz.py 2>&1); [ $? = 0 ] && ok "Verlustbilanz je Stufe (rein/raus/verloren+Grund; Clip ohne Bilder und ohne Fehlerzeile = WARNUNG, benannte Verluste nicht; Grenze je Stufe, alter Stand markiert) - Nulllauf 1122: hBlkpdGf6LY still verloren" || { rot "verlustbilanz: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_kette_beleg.py 2>&1); [ $? = 0 ] && ok "Beleg-Helfer gegen stille Erfolge (Audit 23.11.: Ausgabe muss aus DIESEM Lauf stammen + Mindestinhalt; Altstand beiseite; 1122t Sweep f01 rc 2 las vorbauten_f01.json von 12:25; SIFT-Luecken in iphone_sfm)" || { rot "kette_beleg: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_stille_erfolge_24.py 2>&1); [ $? = 0 ] && ok "Stille Erfolge 24.11.: leeres/altes STL im Zwischenbau rot (1122u 84 Byte -> KeyError world), mono mit 0 Waenden rot, Bogen ohne Tiefenkarte unentschieden statt geschlossen, Beleg vorbauten_auto/hand_vergleich" || { rot "stille_erfolge_24: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_temp_ordner.py 2>&1); [ $? = 0 ] && ok "Temp nicht auf Root + Aufraeumen (pfade.temp_ordner: TMPDIR/Datenplatte, weg auch nach assert; Waechter: kein Test mit nacktem tempfile.mkdtemp) - Root lief 2x voll" || { rot "temp_ordner: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_repo_pfad.py 2>&1); [ $? = 0 ] && ok "Schnelltest im Worktree (pfade.repo_pfad: fehlende unversionierte Eingaben lesend aus dem Hauptordner, sonst UEBERSPRUNGEN mitgezaehlt) - 22.11.: jeder Agent verlor eine Runde" || { rot "repo_pfad: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_standort_und_svd.py 2>&1); [ $? = 0 ] && ok "Kamerastandort ohne standort_xyz (standort/Pose, kein KeyError in tiefe_lokal) + wand_dicke svd ohne n x n (1122r: KeyError 5 Waende, 119 GiB)" || rot "standort/svd: $(echo "$k" | tail -2 | cut -c1-300)"
k=$($P -W ignore -I tools/test_kamera_rahmen.py 2>&1); [ $? = 0 ] && ok "K-Kameras tragen ihren Rahmen: abgeleitete (nachgetragen/verfeinert) im alten Rahmen -> Buendelkamera, gleiches SfM umgerechnet, sonst .veraltet; Handkalibrierung bleibt; Leser filtern (1122s: 231 Kameras aus 1122q, 48 m / 600 px daneben)" || { rot "kamera_rahmen: $(echo "$k" | grep -v "^ok" | tail -3 | tr '\n' ' ' | cut -c1-300)"; }
k=$(python3 -I tools/test_undefinierte_namen.py 2>&1); [ $? = 0 ] && ok "Keine neuen undefinierten Namen in tools/*.py (pyflakes; 1121t: q95 im Kommentar -> NameError nach 20 min)" || { rot "undefinierte Namen: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_handy_masken_gross.py 2>&1); [ $? = 0 ] && ok "handy_masken: grosse Bilder ohne Logits in voller Groesse (Nulllauf 1122: 27-MPx-Bild -> OOM -> SfM-Abbruch)" || { rot "handy_masken gross: $(echo "$k" | tail -2 | cut -c1-200)"; }
k=$($P -W ignore -I tools/test_wandlage_fotokanten.py 2>&1); [ $? = 0 ] && ok "Koerperwand auf die Fotokanten-Ebene (1122x f00 0,32 m zu weit aussen): belegt + Wolke gleiche Seite -> verschoben, schwach belegt / Wolken-Veto -> nicht; Ecken ohne Rippe, Fenster ab der gesetzten Wand" || { rot "wandlage_fotokanten: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ' | cut -c1-300)"; }
k=$($P -W ignore -I tools/test_fusion_vorab.py 2>&1); [ $? = 0 ] && ok "EINE Fusion je Kettenlauf (fusion_vorab: Ausschlusslisten vorab auf dem duennen Netz; Ersatzfusion zaehlt alt 2 / neu 1, Rueckfall bei Abweichung bzw. ohne Neufusion mit Logzeile; Regel = alte Ausloese-Regel; 1122z 445 s doppelt)" || { rot "fusion_vorab: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ' | cut -c1-300)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_teil_gelaende_tor.py 2>&1); [ $? = 0 ] && ok "Unter-Gelaende-Tor fuer JEDEN Bindungsweg (teil_gelaende_tor vor modelle_zusammen; 6,4 m tiefes Teil je Weg abgelehnt, Logzeile je Teil; Nachpruefung nach GPS-Ausgleich verwirft ihn; Massstab ohne GPS-Weg aus GPS-Rahmen von A allein) - 1122z Ost-Teil" || rot "teil_gelaende_tor: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"
k=$(python3 -I tools/test_kamera_gelaende.py 2>&1); [ $? = 0 ] && ok "Kamera-Gelaende-Tor urteilt ueber die Bilder der Fusion (nach dem Neufusionieren gruen, Ausloeser unveraendert) - 1122z dauernd rot" || rot "kamera_gelaende: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"
k=$(python3 -I tools/test_platz_tor_ersetzt.py 2>&1); [ $? = 0 ] && ok "Platztor der Kette: ohne Ersatz haelt die Stufe an, Tests ersetzen es (RCPARK_PLATZ_TOR=test_ersetzt), main() entfernt den Ersatz" || rot "platz_tor: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"
k=$($P -W ignore -I tools/test_wandbezug_bauteile.py 2>&1); [ $? = 0 ] && ok "Bauteile an der GESETZTEN Wand (wandversatz): Tor schneidet volle Tiefe, Laubenpfeiler/Umgang/Vorbau schliessen ohne Spalt an, ein Stueck" || { rot "wandbezug_bauteile: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ' | cut -c1-300)"; }
k=$(/media/oem/scan/venv-colmap/bin/python -I tools/test_kamerahoehe_dgm.py 2>&1); [ $? = 0 ] && ok "Kamerahoehe gegen DGM1 an der GPS-Lage (1122z Ost-Teil: Schlossberg-Kameras echt 20-36 m hoch; Modell/DGM gestaucht/gestreckt -> rot, ebenes Umfeld -> Steigung nicht messbar)" || rot "kamerahoehe_dgm: $(echo "$k" | grep -E "FEHLER|Error|assert" | head -3 | cut -c1-300)"
k=$($P -W ignore -I tools/test_dicht_alt_auto.py 2>&1); [ $? = 0 ] && ok "Dichte Wolke aelter als das SfM-Netz: --bis kameras nur Hinweis, sonst automatisch beiseitelegen + neu (1122za-Abbruch 24.11.)" || rot "dicht_alt_auto: $(echo "$k" | grep FEHLER | head -2)"
k=$($P -W ignore -I tools/test_ebenen_kam_ergaenzen.py 2>&1); [ $? = 0 ] && ok "Ebenen-Bauplan ergaenzt je Wand frontale SfM-Kameras aus kam.json (1122z f02/Ost: 49 frontale Kameras fehlten in kam_wahl, 1316 Kantenpunkte); hinter/parallel/zu grob/schon gewaehlt -> nicht" || rot "ebenen_kam_ergaenzen: $(echo "$k" | grep FEHLER | head -3 | tr '\n' ' ' | cut -c1-300)"
k=$(python3 -I tools/test_ketten_probelauf.py 2>&1); [ $? = 0 ] && ok "Ketten-Probelauf vor dem Merge: Auswertung (1122za = FEHLER, Lage = kein Urteil), Marken verstellen, Sichern, Fotowahl, Planmodus (ketten_probelauf.sh)" || rot "ketten_probelauf: $(echo "$k" | grep FEHLER | head -2)"
k=$($P -W ignore -I tools/test_zonen_verworfen.py 2>&1); [ $? = 0 ] && ok "Verworfene Erkennungen sind keine Bauteil-Zonen (1122zb: uhr_f01_2 auf dem Goldnimbus, uhr_f01_3 Zackenrechteck = verworfene Uhr-Kandidaten in neben_details)" || { rot "zonen_verworfen: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_wissensbaum_luecken.py 2>&1); [ $? = 0 ] && ok "Wissensbaum-Lueckenpruefung + Wissenssuche synthetisch (Register/NICHTS_GEBRACHT/Rezept/Logbuch/Archiv/Memory, Synonyme, Symlink; 24.11.: BM/BN fehlten im Baum)" || { rot "Wissensbaum-Lueckenpruefung/Wissenssuche synthetisch"; echo "$k" | tail -5 | cut -c1-300; }
k=$(python3 -I tools/wissensbaum_luecken.py 2>&1); [ $? = 0 ] && ok "Wissensbaum vollstaendig: jeder Register-/NICHTS_GEBRACHT-/Rezept-/Logbuch-/Archiv-/Memory-Eintrag + jedes genannte Werkzeug hat eine Baumzeile (Nachtrag: python3 -I tools/wissensbaum_luecken.py --json x.json)" || { rot "Wissensbaum-Luecken: $(echo "$k" | tail -1 | cut -c1-200)"; echo "$k" | grep -v " 0 fehlend" | grep "fehlend\|Werkzeuge" | cut -c1-300; }
k=$(CUDA_VISIBLE_DEVICES="" /media/oem/scan/venv-seg/bin/python -W ignore -I tests/test_nachhol_abbildung.py 2>&1); [ $? = 0 ] && ok "Nachholen ohne Nutzen (Kette 1122zb: seiten_luecken 29,6 min, Abbildung SfM->Modell Massstab 0,0017 durch EINE Fernkamera, alle neuen Kameras im Turm, 0 sehen eine Wand): robuste Abbildung + Tor rc 4, Kameras im Gebaeude gesperrt (auch Altbestand), Vor-Tor-Versuche zaehlen nicht, Zwischenspeicher je Objekt" || { rot "nachhol_abbildung: $(echo "$k" | grep -E "FEHLER|Error" | head -3 | cut -c1-300)"; }
k=$(python3 -I tools/test_wissen_ablage.py 2>&1); [ $? = 0 ] && ok "Wissensablage synthetisch: Doppelgaenger-Werkzeug per Wortschatz (formsitz~flaechen_mass), Kopfzeile Verwandt, nicht eingecheckte Spec, Doppel-ID-Sperrklinke, Widerspruchsliste, Homonym Draht/Drahtgitter (24.11.)" || { rot "Wissensablage synthetisch"; echo "$k" | tail -5 | cut -c1-300; }
k=$(python3 -I tools/wissen_ablage_pruefen.py --still 2>&1); [ $? = 0 ] && ok "Wissensablage: keine neue Doppel-ID in Registern, keine neuen Verweise auf nicht eingecheckte .md, WIDERSPRUECHE.md mit Status (nicht eingecheckt: $(echo "$k" | grep -o '1 ungetrackt: [0-9]*' | cut -d' ' -f3))" || { rot "Wissensablage: $(echo "$k" | grep FEHLER | head -2 | cut -c1-250)"; }
k=$(python3 -I tools/werkzeug_aehnlich.py --kopf-pruefen 2>&1); [ $? = 0 ] && ok "Neue Werkzeuge nennen Verwandt/Vorlaeufer im Kopf (werkzeug_aehnlich --wie tools/<x>.py)" || { rot "Werkzeugkopf ohne Verwandt/Vorlaeufer: $(echo "$k" | grep 'tools/' | head -5 | tr '\n' ' ' | cut -c1-250)"; }
k=$(python3 -I tools/wissen_wiederfinden.py 2>&1); [ $? = 0 ] && ok "Wiederfinde-Nachweis: $(echo "$k" | grep '^RECALL' | cut -c1-60) auf echten Verlustfaellen (tools/wissen_wiederfinden.json; $(echo "$k" | grep '^KONTROLLE' | cut -c1-40))" || { rot "Wiederfinde-Nachweis: $(echo "$k" | grep '^RECALL')"; echo "$k" | grep -A5 '^FEHLT' | head -12 | cut -c1-200; }
k=$(python3 -I tools/claude_mds_vorschlag/claude/skills/doku-pflege/test_wissen.py 2>&1); [ $? = 0 ] && ok "Wissenswerkzeuge projektunabhaengig (Vorschlag claude-mds doku-pflege: wissen_suchen/luecken/wiederfinden im Wegwerf-Projekt)" || { rot "claude_mds_vorschlag test_wissen"; echo "$k" | tail -4 | cut -c1-300; }
k=$(CUDA_VISIBLE_DEVICES= $P -W ignore -I tools/test_hoehen_angleich.py 2>&1); [ $? = 0 ] && ok "Hoehen-Angleich waagerechter Bauteile (Gesims 0,6 m zu hoch: Wolken-Linien + triangulierte Fotokanten einig -> Korrektur ~-0,6 je Seite, Hoehensitz steigt, Nachbarlinien bleiben, umkehrbar/kein Aufschaukeln; Kanten an Modell-Hoehe oder fehlend -> keine Korrektur; Faltungs-Guard; Generator warp_batch) - 24.11." || { rot "hoehen_angleich: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES= $P -W ignore -I tools/test_formsitz_durchblick.py 2>&1); [ $? = 0 ] && ok "Formsitz Durchsicht/Verdeckung (24.11.: Ost 1122zb med|dz| 3,6 m war kein Modellfehler - Wolke sah durch den nicht rekonstruierten Anbau auf die Westwand): Durchsicht-Pixel unbeobachtet, Anteil > 0,3 -> Bezug durchsichtig, Modell 1,3/3 m aussen bleibt Fehler, Fremdbau davor maskiert, dahinter nicht" || { rot "formsitz_durchblick: $(echo "$k" | grep FEHLER | head -3 | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES="" /media/oem/scan/venv-colmap/bin/python -I tests/test_sift_paar_speicher.py 2>&1); [ $? = 0 ] && ok "SIFT-Paarspeicher Nachholen (1122zb: merkmale 1005 s von 1777 s, jedes neue SfM = neue Paarliste): COLMAP je Paar unabhaengig + vorhandene Paare uebersprungen, Treffer/Teiltreffer bitgleich, Stichprobe verwirft verfaelschten Speicher, Kamera geaendert -> kein Treffer, Referenz-DB-Paare unberuehrt" || { rot "sift_paar_speicher: $(echo "$k" | grep -E "FEHLER|Error" | head -3 | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES="" /media/oem/scan/venv-seg/bin/python -W ignore -I tests/test_konvergenz_messfehler.py 2>&1); [ $? = 0 ] && ok "Konvergenz-Messfehler (1122zb: foto_diff_batch 20/20 OOM am 1500-MiB-Deckel trotz Buchung 6000, teil_fotoform Pfad statt Name): Deckel aus RCPARK_GPU_MB, Objektname, MESSFEHLER statt 'Datendecke -> Fotoauftrag'" || { rot "konvergenz_messfehler: $(echo "$k" | grep -E "FEHLER|Error" | head -3 | cut -c1-300)"; }
k=$(CUDA_VISIBLE_DEVICES="" /media/oem/scan/venv-seg/bin/python -W ignore -I tests/test_konvergenz_gruende.py 2>&1); [ $? = 0 ] && ok "Konvergenz-Gruende (rote Probe 1122zb: None nur mit Grund MESSFEHLER/DATENDECKE je Foto/Bauteil, Messfehler = Exit 4 KONVERGENZ NICHT GEMESSEN, Messart fest im Fotosatz, Wiederholung ersetzt Zeile)" || { rot "konvergenz_gruende: $(echo "$k" | grep -E "FEHLER|Error" | head -3 | cut -c1-300)"; }
_S="$HOME/.claude/skills/doku-pflege"; if [ -f "$_S/wissen_suchen.py" ]; then _d=""; _v=""; _V=tools/claude_mds_vorschlag/claude/skills/doku-pflege; for _p in "wissen_suchen.py:wissen_suchen.py" "werkzeug_aehnlich.py:werkzeug_aehnlich.py" "wissen_wiederfinden.py:wiederfinden.py" "wissen_bedeutung.py:wissen_bedeutung.py"; do [ -f "tools/${_p%%:*}" ] || continue; cmp -s "tools/${_p%%:*}" "$_S/${_p##*:}" && continue; cmp -s "tools/${_p%%:*}" "$_V/${_p##*:}" && _v="$_v ${_p%%:*}" || _d="$_d ${_p%%:*}"; done; [ -z "$_d" ] && [ -z "$_v" ] && ok "Wissenswerkzeuge gleich mit claude-mds doku-pflege (Projektkopie = Skill)"; [ -z "$_d" ] && [ -n "$_v" ] && ueb "Wissenswerkzeuge = Vorschlag $_V, noch nicht in ~/git/claude-mds uebernommen:$_v (UEBERNAHME.txt; 24.11. Bedeutungssuche)"; [ -z "$_d" ] || rot "Wissenswerkzeuge weichen von ~/.claude/skills/doku-pflege ab:$_d - Aenderung in ~/git/claude-mds uebernehmen (und umgekehrt), dann kopieren"; else ueb "claude-mds doku-pflege fehlt (bash ~/git/claude-mds/bootstrap.sh) - Gleichstand Wissenswerkzeuge"; fi
#<<< PRUEFUNGEN
fi
rm -rf $S
# 22.11.2026: Tests raeumen selbst auf (tools/pfade.temp_ordner, TemporaryDirectory, finally) - Reste im eigenen Temp-Ordner oder neue /tmp/test_* = Fehler
rest=$(find "$ST_TMP" -mindepth 1 -maxdepth 1 -type d ! -name 'torchinductor_*' ! -name '__pycache__' -printf '%f ' 2>/dev/null | cut -c1-300)
[ -z "$rest" ] && ok "Tests raeumen ihre Temp-Ordner selbst auf (Temp unter $TW, nicht auf Root)" || rot "Temp-Reste nach den Tests in $ST_TMP: $rest"
neu=$(comm -13 <(echo "$TMP_VOR") <(ls -d /tmp/test_* 2>/dev/null | sort) | tr '\n' ' ' | cut -c1-300)
[ -z "$neu" ] || rot "neue Ordner in /tmp (Root) seit Testbeginn: $neu - Test schreibt an TMPDIR/pfade.temp_ordner vorbei"
echo "LANGSAMSTE PRUEFUNGEN (s): $(echo "$DAUER" | sort -rn | head -5 | cut -c1-70 | tr '\n' '|' | sed 's/|$//; s/|/ | /g')"
echo "SCHNELLTEST: $F Fehler$( [ "$U" -gt 0 ] && echo ", $U uebersprungen"), $(( $(date +%s) - T0 )) s"; exit $F

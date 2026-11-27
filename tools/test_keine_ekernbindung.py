#!/usr/bin/env python3
"""test_keine_ekernbindung.py - Hardware-Bug-Test (27.11.2026): CPU-Jobs duerfen NICHT immer auf die langsamen E-Kerne 16-27 festgenagelt werden.
Lehre: job_start.sh band jeden reinen CPU-Job IMMER per taskset an 16-27 (12 Kerne, 3,9 GHz), auch bei leerer GPU; Nachtketten-Skripte hatten es doppelt (Nutzer: Katastrophe).
Prueft: (1) job_start.sh enthaelt keine unbedingte Standardbindung ${JOB_CPU_KERNE:-16-27}; (2) die Bindung haengt an 'nvidia-smi --query-compute-apps' (GPU belegt);
(3) kein Skript tools/*.sh ruft 'taskset -c 16-27' hart auf; (4) keine Bindung auf einen Teil der Kerne ohne Begruendung in tools/handy_*.sh. Rot = Rueckfall."""
import os, re, sys, glob
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); fehler = []
js = open(os.path.join(R, "tools", "job_start.sh")).read()
if re.search(r'\$\{JOB_CPU_KERNE:-16-27\}', js): fehler.append("job_start.sh: unbedingte Standardbindung ${JOB_CPU_KERNE:-16-27} (Rueckfall)")
if "query-compute-apps" not in js: fehler.append("job_start.sh: Bindung nicht an 'GPU belegt' gekoppelt")
for f in sorted(glob.glob(os.path.join(R, "tools", "*.sh"))):
    if os.path.basename(f) == "job_start.sh": continue
    for n, z in enumerate(open(f, errors="replace"), 1):
        if re.search(r'taskset\s+-c\s+16-27', z) and not z.lstrip().startswith("#"): fehler.append(f"{os.path.relpath(f, R)}:{n}: harte Bindung taskset -c 16-27 (E-Kerne)")
        if os.path.basename(f).startswith("handy_") and re.search(r'taskset\s+-c', z) and not z.lstrip().startswith("#"): fehler.append(f"{os.path.relpath(f, R)}:{n}: taskset in Nachtkette (job_start entscheidet)")
if fehler: print("ROT\n" + "\n".join(fehler)); sys.exit(1)
print("ok test_keine_ekernbindung")

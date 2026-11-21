#!/usr/bin/env python3
"""Undefinierte Namen in tools/*.py (pyflakes) - Lauf 1121t verlor die Feinrechnung, weil 'q5, q95 = ...' bei einem Agenten-Merge in einen Kommentar rutschte
(NameError erst nach 20 min Rechnung). Bekannte Altstellen (Stand 21.11.2026, toter Code/Closure) stehen in BEKANNT; jede NEUE Stelle ist rot."""
import subprocess, sys, os, re, glob
R = os.path.dirname(os.path.abspath(__file__))
BEKANNT = {("pruefstand.py", "c"), ("pruefstand.py", "P"), ("pruefstand.py", "s_"), ("relief_aus_fotos_mono.py", "draht_u"),
           ("render_kern.py", "Nc"), ("render_kern.py", "d"), ("wand_feinausrichtung.py", "volc")}
py = os.path.expanduser("~/.venvs/rcpark/bin/python")
o = subprocess.run([py, "-m", "pyflakes"] + sorted(glob.glob(os.path.join(R, "*.py"))), capture_output=True, text=True)
if "No module named pyflakes" in o.stderr: print("FEHLER pyflakes fehlt: ~/.venvs/rcpark/bin/pip install pyflakes"); sys.exit(1)
neu = sorted({(os.path.basename(m.group(1)), m.group(2), m.group(3)) for m in re.finditer(r"^(.*?\.py):(\d+):\d+:? undefined name '([^']+)'", o.stdout, re.M)
              if (os.path.basename(m.group(1)), m.group(3)) not in BEKANNT})
for f, z, n in neu: print(f"    FEHLER {f}:{z} undefinierter Name '{n}'")
print(("FEHLER" if neu else "OK") + f" undefinierte Namen: {len(neu)} neu"); sys.exit(1 if neu else 0)

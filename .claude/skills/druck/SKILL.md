---
name: druck
description: Druckteile vorbereiten und Drucker starten (Bambu P1S, Prusa MK4S) - nur auf ausdruecklichen Nutzerwunsch. Details auf Bambu, lange Waende auf MK4S.
---
0. Nur auf Nutzerwunsch. Vorher Teil neben Referenzfoto ansehen (Detailtreue vor Druck).
1. Bausatz/Teilung: `tools/bausatz.sh` bzw. `tools/druck_teilung.py`.
2. Bambu (Details, Klipsteile): `python3 tools/bambu_slice.py <aus.gcode.3mf> <teil.stl> --schicht 0.16 --brim 0`, dann `~/.venvs/strom/bin/python tools/p1s_print.py status|print`.
3. Prusa MK4S (Waende 1 mm: Rippen, Rahmen, Brim): `python3 tools/prusa_slice.py <stl> --out <ordner> --printer "Original Prusa MK4 Input Shaper 0.8 nozzle" --print "0.40mm QUALITY @MK4IS 0.8"`, `python3 tools/prusa_print.py print <gcode> <name>` (Zugang ~/.config/rcpark/prusalink.json).
4. Start selbst ausloesen und Status melden.

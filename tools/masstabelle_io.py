#!/usr/bin/env python3
"""masstabelle_io.py - Masstabelle nebenlaeufig sicher aendern (Dateisperre). Mehrere Werkzeuge (foto_breitenprofil, fehlteile_finden, ...)
laufen in tools/bauen_abnehmen.sh parallel je Foto und tragen Beobachtungen ein; ohne Sperre ueberschreiben sie einander (Lese-Aendere-Schreibe).
  from masstabelle_io import aendern
  def f(tab): ...; return anzahl_neu
  neu = aendern(pfad, f)      # liest UNTER der Sperre, ruft f(tab), schreibt zurueck
"""
import json, os, fcntl

def aendern(pfad, fn):
    lock = pfad + ".lock"
    with open(lock, "w") as L:
        fcntl.flock(L, fcntl.LOCK_EX)
        try:
            tab = json.load(open(pfad)); erg = fn(tab)
            tmp = pfad + ".tmp"; json.dump(tab, open(tmp, "w"), indent=1, ensure_ascii=False); os.replace(tmp, pfad)
            return erg
        finally:
            fcntl.flock(L, fcntl.LOCK_UN)

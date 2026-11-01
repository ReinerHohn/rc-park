#!/usr/bin/env python3
"""masstabelle_io.py - Masstabelle nebenlaeufig sicher aendern (Dateisperre). Mehrere Werkzeuge (foto_breitenprofil, fehlteile_finden, ...)
laufen in tools/bauen_abnehmen.sh parallel je Foto und tragen Beobachtungen ein; ohne Sperre ueberschreiben sie einander (Lese-Aendere-Schreibe).
  from masstabelle_io import aendern
  def f(tab): ...; return anzahl_neu
  neu = aendern(pfad, f)      # liest UNTER der Sperre, ruft f(tab), schreibt zurueck
"""
import json, os, fcntl

def sperren(pfad):
    """Exklusive Sperre auf <pfad>.lock holen (Lese-Aendere-Schreibe-Abschnitt); Rueckgabe: offenes Sperrobjekt fuer schreiben()."""
    L = open(pfad + ".lock", "w"); fcntl.flock(L, fcntl.LOCK_EX); return L

def schreiben(pfad, tab, L=None):
    """Tabelle atomar schreiben (tmp + rename) und die Sperre freigeben."""
    tmp = pfad + ".tmp"; json.dump(tab, open(tmp, "w"), indent=1, ensure_ascii=False); os.replace(tmp, pfad)
    if L is not None: fcntl.flock(L, fcntl.LOCK_UN); L.close()

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

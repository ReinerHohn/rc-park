#!/usr/bin/env python3
"""speicher_muster.py - EIN Muster fuer "Stufe scheiterte am Speicher (RAM oder GPU-VRAM)" fuer Kette (gesamtkette.lauf) und Stufen mit Fehlschlag-Marke (seiten_luecken).

WARUM (23.11.2026, Kette schwabentor-null-1122n): SiftGPU meldete "CuTexImage::InitTexture2D: out of memory" (zwei Agenten-Jobs belegten die GPU), die Kette erkannte
SPEICHERMANGEL und wiederholte seiten_luecken - aber die Fehlschlag-Marke der Stufe hielt den voruebergehenden Fehler fuer "bekannt" und sperrte die Wiederholung und
jeden Folgelauf (1122o). Beide Stellen muessen dasselbe Muster benutzen. Nur Standardbibliothek."""
import re

SPEICHER_MUSTER = re.compile(r"CUDA out of memory|OutOfMemoryError|MemoryError|std::bad_alloc|cudaErrorMemoryAllocation|out of memory|vom System beendet \(Signal (9|6)|Signal (9|6)\b|Killed\b", re.I)
SPEICHER_RC = (-9, -6, 137, 134)      # vom System beendet: 9 = OOM-Killer, 6 = Abbruch nach fehlgeschlagener Anforderung (auch 128 + n aus bash)


def speicher_fehler(rc, ausgabe):
    """True, wenn ein Abbruch (rc != 0) nach Speichermangel aussieht (Rueckgabecode des Systems oder Speicher-Meldung in der Ausgabe)."""
    if rc in (0, None): return False
    return rc in SPEICHER_RC or bool(SPEICHER_MUSTER.search(ausgabe or ""))

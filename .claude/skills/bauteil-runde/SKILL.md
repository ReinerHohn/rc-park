---
name: bauteil-runde
description: Ein Bauteil ist neu, fehlt oder ist falsch (Nutzerfund) - Befund erfassen, Form aus Fotos, zaehlen, messen, rote Pruefung, generisches Bauteil, Abnahme. Optional als Agent im Worktree.
---
1. Befund in `modelle/<objekt>/masstabelle.json` `beobachtungen_offen` (datum, wer, text, naechster_schritt).
2. Auftrag aus `modelle/VORLAGE_BAUTEIL_RUNDE.md` (Platzhalter fuellen, TABU-Liste); als Agent mit `isolation: worktree`.
3. Stufen: 0 Form aus >= 3 Fotos (`tools/bauteil_sichtliste.py`, `tools/kamera_bruecke.py`), 1 Zaehlen (`tools/foto_zaehlung.py`), 2 Messen (`tools/foto_mass.py --tri`), 3 Pruefung erst ROT machen, 4 Gestalt aus Wandbild als generische Funktion in `tools/bauteile.py`, 5 Skill `abnahme`.
4. Integration: Schnelltest auf aktuellem main, nur eigene Dateien committen; Lehre ins Register `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md`.
Kreis-Variante: `tools/bauteil_kreis.py --nach_main` (Foto-F1 entscheidet, Wolke nur Veto).

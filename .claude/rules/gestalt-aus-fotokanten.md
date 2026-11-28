---
paths:
  - "tools/bauteile.py"
  - "tools/dach_bauen.py"
  - "tools/fassaden_kette.py"
  - "tools/koerper_schleife.py"
  - "tools/gesamtkette.py"
  - "tools/objekt_anlegen.py"
  - "modelle/*_gen.py"
---
# ⛔ Gestalt nur aus Fotokanten (Nutzer 28.11.2026)
Du aenderst Code, der die Form des Modells bestimmt. Lies `modelle/SPEC_GESTALT_AUS_FOTOKANTEN.md` (6 Invarianten).
- Maße, Konturen, Profile, Daecher, Kaesten, Baender: Quelle ist Fotokante/Sweep/Wandbild. NIE dichte Wolke, LoD2, DOM1 - auch nicht als Rueckfall.
- Wolke/LoD2/DOM1 nur Lage-Veto (blockiert nur bei Widerspruch zur unabhaengigen Lage), Hoehe, Gegenprobe.
- Fotos uneinig -> Ursache klaeren oder Teil nicht bauen (Beleg "kein Fotomass"), nie auf Wolke ausweichen.
- Im Commit/Bericht: "Quelle der Gestalt: ..." nennen.

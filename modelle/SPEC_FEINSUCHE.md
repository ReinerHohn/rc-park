# SPEC Automatische Feinsuche (Nutzer 11.11. ~18:00 "automatische Feinsuche auf jeden Fall")

## Warum
Details (Erker-Netzrippen, Fenstersprossen, Eckfiguren/Drachen, Wasserspeier, Schindeln) fand bisher nur der Nutzer per Auge. Grund: die Fotometrik
glaettete auf 0,18 m, gelbe Flecken (`foto_fehlteile.py`) entstehen erst ab grossen Flaechen. Seit 2932633b liefert `teil_fotoform.py` je Teil und Foto
die Feinzahlen (`praez_f`, `recall_f`, `mkf_px`, `fkf_px`, volle Aufloesung, Toleranz 0,03 m) - die Feinkanten-Fehlstellen (Fotokante fein ohne Modellkante fein)
sind damit messbar. Ziel: der Kreis findet fehlende Feinform SELBST und arbeitet sie ab; der Nutzer nimmt nur noch per Auge ab.

## Was (generisch, kein Objektname im Code)
1. `tools/teil_fotoform.py` (nur falls noetig, Hauptzahl F1 und f1_fein bitgleich): je Teil und Foto die groessten FEIN-gelben Flecken (zusammenhaengende Feinkanten
   ohne Modell-Feinkante, nach Dichte, nicht Einzelpixel) mit Weltpunkt auf der Modellflaeche ausgeben - analog zu den groben gelben Flecken, eigenes Feld
   (z. B. `flecken_fein`). Zuerst pruefen, ob `foto_fehlteile.py`/`flecken()` schon wiederverwendbar ist.
2. `tools/foto_feinsuche.py <objekt> [--formliste DATEI] [--min_fotos 3] [--aus DATEI]`: Fein-Flecken ueber alle Fotos sammeln, je Foto entdoppeln, raeumlich clustern
   (GPU, `tools/gpu_knn.py`), nur Cluster in >= 3 Fotos aus verschiedenen Richtungen (Winkelabstand der Kameras >= 15 Grad). Ausgabe je Cluster:
   Teil (welchem Teil der Weltpunkt gehoert), Zentrum/Kasten, Fotos, Fein-Defizit (fehlende Feinkantenpixel), Bildausschnitte als Kollage
   `/media/oem/scan/rc-park_tmp/feinsuche/<objekt>/cluster_<id>.jpg` (Fotoausschnitt + Teil-Render aus derselben Kamera, `tools/teil_render_foto.py`).
   Stoerer: Stoermaske (`tools/foto_stoermaske.py`) anwenden; Muster OHNE Relief (Glasmuster/Butzen hinter Glas, Bemalung, Moos) sind KEINE Form -
   Kennzeichnen statt verwerfen: Feld `art_verdacht` aus einfachen Merkmalen (Farbtextur ohne Schattenwechsel ueber Fotos mit verschiedener Beleuchtung) - ANNAHME, nicht als Tor.
3. Rangliste: Fein-Defizit x Anzahl Fotos, je Teil hoechstens 3 Cluster. Bericht `bericht.json` + Uebersichtskollage der Top 10.
4. Uebergabe an den Kreis (NUR vorbereiten, Kreiscode macht die Hauptsitzung): JSON-Felder so, dass ein Cluster als Beobachtung
   `{teil, merkmal: "Feinform fehlt: <Teil> <Ort>", text, fotos, wer: "Feinsuche automatisch", pruef_stichworte}` in die Masstabelle uebernommen werden kann.

## Beweis (Pflicht)
- Synthetisch: in ein echtes Foto gerenderte Testrippen auf einer Modellflaeche, Modell ohne Rippen -> Cluster gefunden an der richtigen Stelle (< 0,3 m), in >= 3 Fotos;
  Modell MIT Rippen -> kein Cluster dort.
- Echt kaufhaus_grob3: Die bekannten Nutzerfunde muessen unter den Top 15 stehen: Erker-Konsole (Netzrippen) erker_polygon__1/__0, Erker-Fenster (Sprossen/Masswerk),
  Eckfiguren unter den Erkerhelmen (Traufecken), Wasserspeier Haupttraufe, Baldachin-Kronen. Jede gefundene/nicht gefundene Stelle nennen; die Kollagen der Top 10 ANSEHEN und
  je Cluster in einem Satz sagen, was dort im Foto ist (Form oder nur Muster?). Falsche Treffer zaehlen.
- `tools/regression.py modelle/kaufhaus_grob3/objekt.json --pruefen` identisch.

## Nicht
Kein Kreis-/Reglercode, keine Generatoraenderung, keine Sollwerte, nichts loeschen. Lange GPU-Laeufe ueber `tools/job_start.sh` mit `JOB_GPU_MB` (vorher messen).

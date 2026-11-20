# STAND 8.11.2026 abends - nach /clear zuerst lesen (Kaufhaus, Schleife je Bauteil)
Logbuch: `modelle/LOGBUCH_2026-11-08.md` (Schritte 1-25), Lehren `LEHREN_2026-11-08_SWEEP_UND_FOTOLOOP.md`, Sackgassen `NICHTS_GEBRACHT.md` BS144-BS150, Methode `METHODE_GPU_SWEEP.md`, Recherchen `RECHERCHE_2026-11-08_BAUTEIL_LAGE.md` + `_RUNDE2.md`. Commits 711a82c, 26038de, 5c09e24 (+ nach diesem Stand ein weiterer).

## Die eine wichtigste Erkenntnis
**Der Wolken-/Kamerarahmen (gemeinsame SfM -> Netzrahmen) war ~25 Grad GEKIPPT.** Entdeckt vom Nutzer am Overlay ("Perspektive wirkt falsch, Kamera zu weit oben"), bewiesen durch Fluchtpunkt der Vertikalen aus 36-54 Fotos (`tools/lot_aus_fotos.py`: up_welt (-0.19,-0.39,0.90), Streuung 0,6 Grad). Kamerahoehe ueber Boden war 4-6 m (iPhone 4,3 m) statt ~2 m. Korrektur `tools/rahmen_lot_foto.py` (Lot aus Foto-Vertikalen + Wandgier -3,17 Grad + Boden-Modus auf z=1,66): Kamerahoehe danach 1,5/2,0/2,3 m, Lotabweichung der Fotos 0,06 Grad. **Alle frueheren Sweeps/Overlays/Teile-Laeufe in diesem Rahmen sind ungueltig** (Boden-/Wand-Ebenenfit mit z-Fenster war verzerrt, BS150).
Korrigierte Daten: Wolke voll `/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy` (1,85 Mio Pkt), Ausschnitt `lot2/j_voll_lot2_crop.npy` (1,83 Mio), RGB `lot2/j_crop_rgb2.npy`, Kameras `/media/oem/scan/rc-park_daten/kaufhaus_alle/sfm/kam_lot2.json` (+ `.rot.json`). Erzeugt aus `scratchpad/j_netz.npy` + `sfm/kameras_netz.json` mit `lot_aus_fotos.json` (`modelle/kaufhaus_grob3/lot_aus_fotos.json`).

## Werkzeuge dieser Sitzung (alle im Repo, tools/)
- `teil_sweep_gpu.py`, `sweep_alle.py`, `test_sweep_synth.py`: Verschiebungs-Sweep je Teil (Distanzfeld, Pyramide, Plateaubreite, `--synth` Beweistest, `--fotos` Kantenterm). Synthetik <1 cm.
- `modell_ausrichten_gpu.py`: 8 Freiheitsgrade (du,dn,dz, gier/nick/roll, su,sz), feste Rueckrichtung (Schrumpf-Falle!), `--fotos` Kantenterm, `--basis` (Teil im Rahmen der Gesamtausrichtung), Grenzen `--su_lo/hi --sz_lo/hi`.
- `schleife_ausrichten.py` (Gesamt, iterativ konvergierend, Overlay je Runde, Logbuchzeile), `schleife_teile.py` (je Bauteil, noch NICHT erfolgreich gelaufen im richtigen Rahmen).
- `modell_foto_overlay.py` (Wolke gelb + Modellkanten rot aufs Foto = DIE Loop, Nutzer: "richtig geil"), `teil_foto_overlay.py`.
- `lot_aus_fotos.py`, `rahmen_lot_foto.py` (Lot), `wolke_lot_ausrichten.py` (alt, Boden/Wand - VERALTET/verzerrt).
Pfade: venv `/media/oem/scan/venv-seg/bin/python -I`; Jobs `RCPARK_DATEN_MIN_GB=3 JOB_GPU_MB=4000 tools/job_start.sh NAME LOG cmd`.

## Befunde vor der Lotkorrektur (Gueltigkeit neu pruefen!)
- Modell p26 im (falschen) Rahmen: Gesamt-Schleife su 1,33 (Breite 20->27 m), nick 9 Grad: koennte teilweise Rahmenkippen kompensiert haben. Nach Lotkorrektur Gesamt-Schleife NEU laufen lassen (Lauf wurde beim Clear unterbrochen, Timeout).
- Nutzer-Sichtbeobachtungen (masstabelle beobachtungen_offen): Modell zu schmal (links ~200 px), Dach zu niedrig, Arkadenabstand/Erkerlage. Bogenreihe hat n_boegen=4 (am Foto gezaehlt), Photo zeigt 4 Arkaden.
- Fototerm allein schrumpft (BS145-aehnlich): Gegenrichtung im Bild (Fotokanten ohne Modellkante) noch zu bauen; vorerst Skalierungsgrenzen.
- Sweep-Beweistest synthetisch bleibt gueltig (Methode ok), Echtbefund hing am gekippten Rahmen.
- Web: Historisches Kaufhaus hat 4 Arkaden zur Muensterplatzseite + 2 Erker; keine Meterangaben gefunden (Broschuere = Bild-PDF, BLB-PDF >10 MB, structurae 403).

## Offen / naechste Schritte (Reihenfolge)
1. Overlay auf korrigiertem Rahmen ansehen (`modell_foto_overlay.py --fotos kam_lot2.json --wolke lot2/j_voll_lot2_crop.npy`), dann `schleife_ausrichten.py` Gesamt neu (`--extra "--du_max 6 --su_lo 0.85 --su_hi 1.45"`), im Hintergrund per job_start (sonst Timeout).
2. `schleife_teile.py` je Bauteil (Basis = Gesamt-JSON), Overlay je Teil ansehen.
3. Plausibilitaetsprobe automatisch in die Pipeline: Kamerahoehe ueber Boden 0,8-4 m, Fluchtpunkt-Lot < 2 Grad, Exit 2 sonst (in rahmen_lot_foto.py als Text vorgesehen, noch nicht erzwungen).
4. Gegenrichtung Fototerm im Bild; Dach/First per Himmelsmaske (Recherche Runde 2, TOP 2); Arkadenabstand/Erker.
5. Regression (Regel 8b) rot, Pruefstand fuer neue Werkzeuge noch nicht angebunden.

## Regeln/Nutzerwuensche heute
Immer mitloggen (Logbuch), iterative konvergierende Loops, je Bauteil, Bildfeedback vor Zahlen, nichts von Hand messen, Commit nur auf Auftrag (heute erteilt).

## Nachtrag (spaeter am 8.11.)
- Lot ist automatisch berechnet (lot_aus_fotos/rahmen_lot_foto), aber NICHT in der Pipeline eingehaengt; boden_z 1,66 ist Festwert im Aufruf. Offen: einhaengen + Synthetiktest (Rahmen 25 Grad kippen -> Kette holt zurueck).
- Befund: alle Bauteilparameter stammten aus dem alten Rahmen -> je Bauteil neu gegen lot2-Wolke fitten (Dach fertig: Median 0,16 m; Erker/Bogenreihe Job teilefit_lot2; Gauben/Fenster/Staffelgiebel offen). Gesamt-dz nie als Ausgleich missbrauchen (dz +2,73 war Symptom).
- tools/lod2_winkel_abgleich.py: LoD2 nur Winkel/Richtung (Nutzerwunsch), nicht Hoehen.
- Overlay immer ansehen: audit/dachfit_lot2_6161.jpg.

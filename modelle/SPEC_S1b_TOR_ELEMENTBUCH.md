# Spezifikation S1b: Uebernahmetor streng + Elementbuch im Laeufer (`tools/qualitaetsstufen.py`)

Ziel: Fehler 2 (Uebernahme bei "nicht deutlich schlechter", t < 2) und Fehler 5 (gutes Altelement durch globalen Gewinn verloren) aus
`modelle/LOG_2026-11-05_FEHLER_UND_STAND.md` werden technisch unmoeglich. Beweis nach `beweis-pflicht`: synthetischer Test + Kaufhaus + Martinstor-Regression + Bild angesehen.

## 1. Ist-Zustand (Code lesen, nicht raten)
- `tools/qualitaetsstufen.py`: `tor_ok` (Z. 50-63) = nur Druckbarkeit (quelltyp `modell`); `v_fassade` Z. 373-376: `ueb = dm < 0 and t <= -2`, bei `freiraum`/`entscheid == "nicht_schlechter"` nur `t < 2` (DAS ist Fehler 2); `v_parameter` Z. 192-196; `v_gemeinsam` Z. 460.
- `modell_messen` (Z. 129-135) speichert je Foto NUR `kosten_param`; `bewerten` liefert aber das ganze foto_diff-JSON mit `anteil_modellkanten_ohne_foto` (rot) und `anteil_fotokanten_ohne_modell` (gelb).
- `kosten_auf` (Z. 271-278) cacht je Stand+Foto nur die Kosten.
- foto_diff kann je Foto eine Kostenkarte schreiben: `--kostenkarte <datei.npz>` mit `mkp` (Modellkantenpixel), `fkp` (Fotokantenpixel), `dF`, `dM` (Abstaende / Kappe, float16) in Bildaufloesung des entzerrten Fotos (Z. 461).
- Kamera je Foto: `fehlteile_finden.kamera_laden(K, obj, nr, root, W, H)` -> R, t, f_px; cx/cy aus `fehlteile_finden.kmatrix`; Projektion wie `foto_diff.py` Z. 34 (`proj`).
- Elementdatei je Bau: `bauen_fest(..., elem)` schreibt `ELEMENTE_AUS` (Liste von Belegen mit `seite`, `element`, `quelle` und Geometriefeldern). Pruefen, welche Geometriefelder `fassade_auto`-Elemente tragen (`baukasten_gen.py` ab Z. 332, `beleg(...)`-Aufrufe); falls u0/u1/z0/z1/fassade fehlen, diese Felder im Beleg ergaenzen (einzige erlaubte Aenderung an baukasten_gen.py; danach `tools/bauen_abnehmen.sh martinstor` + Regression beider Objekte).

## 2. Uebernahmetor (neue Funktion `uebernahme_tor`)
Signatur: `uebernahme_tor(ctx, name, neu, alt, fotos, cfg) -> (ok: bool, gruende: list[str], detail: dict)`; `neu`/`alt` = Stand-Dicts mit `fest`, `je_foto` (Kosten), `je_foto_rg` ({nr: [rot, gelb]}), `stl`.
Bedingungen (alle muessen gelten; jede Verletzung erzeugt einen Grund mit Buchstabe, der ins Log und in `st["schritte"][..]["tor"]` kommt):
- (a) **je Foto nicht schlechter**: fuer jedes Foto in `fotos`: `(rot+gelb)_neu <= (rot+gelb)_alt + tol`, und keine Einzelgroesse steigt um > 0,10. `tol` = Plan-Schluessel `tor_toleranz` (Standard 0.01; T0 belegt: Wiederholung bitgleich).
  KORREKTUR 5.11. 19:40 nach T2: rot und gelb getrennt zu werten war ein Regelfehler - jede Kantenkorrektur tauscht rot gegen gelb (Foto 000: rot 0,23->0,40, gelb 0,23->0,10) und wurde faelschlich abgelehnt. Ebenso (e): lokale Summe, Mehrheitsregel 2/3, "gemischt" blockiert nicht.
- (b) **in der Summe deutlich besser**: `gepaart(kosten_neu, kosten_alt)`: dm < 0 und t <= -2 (wie bisher). Ausnahme nur fuer Kandidaten mit eigener Messquelle (`freiraum`, `entscheid: "nicht_schlechter"`): statt (b) muss die zugehoerige Pruefstand-Pruefung (quelltyp `foto_freiraum`) im Wert FALLEN (neu < alt, Werte aus `pruefstand.py --bericht`; `tor_fehler` so erweitern, dass es auch die Werte je Pruefung liefert) UND (a) gelten. `t < 2` gibt es nicht mehr.
- (c) **Restfeld nicht schlechter** (nur wenn Plan-Schluessel `tor_restfeld: true` und `objekt.json["freiraum"]` vorhanden): `tools/restfeld_fassade.py --stl <stl> --dicht ... --ausrichtung ... --fassaden <fassaden.json des Laufs> --aus <dir>` fuer alt und neu (je STL cachen); je Fassade mit beobachtetem Anteil >= 0.3: `mittel_abs_rest_neu <= mittel_abs_rest_alt + 0.02`. Laufzeit einmal messen und im Bericht nennen; ueber 90 s je STL: Schluessel bleibt aus, Begruendung im Versuchslog.
- (d) **Pruefstand** wie bisher `tor_ok` (hart nur Druckbarkeit; Quellenverletzung = Widerspruch in die Masstabelle).
- (e) **Elementbuch** (Abschnitt 3): jedes neue/geaenderte/entfernte Element muss lokal bestehen.
Alle Aufrufstellen (`v_parameter`, `v_fassade` inkl. Suche und Zier, `v_gemeinsam`) nutzen `uebernahme_tor`. `modell_messen` und `kosten_auf` liefern zusaetzlich `je_foto_rg`; alte `stand.json` ohne `je_foto_rg` bleiben lesbar (Fortsetzung: fehlende rg nachrechnen oder Schritt neu messen, nicht abstuerzen).

## 3. Elementbuch (`tools/elementbuch.py`, Datei `<aus>/elemente_best.json`)
- **Element-Schluessel**: (fassade-id, klasse, round(u-Mitte, 1), round(z-Mitte, 1)) aus der Elementdatei des Baus; fuer Bauteile ohne Fassadenkoordinaten (Erker-Bloecke, Figuren) die 3D-Box aus dem Beleg (x0..z1). Elemente ohne Geometrie werden uebersprungen (im Log nennen).
- **ROI je Foto**: 3D-Box des Elements (Fassadenebene: 4 Ecken aus o + u*d, z; plus 0.5 m Rand) mit der Kamera des Fotos projizieren -> Bildrechteck. Element sichtbar, wenn Rechteck >= 400 Pixel im Bild und Elementmitte nicht verdeckt (optional: Tiefe aus Kostenkarte nicht pruefbar -> weglassen, dokumentieren).
- **Lokale Kennzahl je Foto**: aus der Kostenkarte des jeweiligen Baus (`bewerten` ruft foto_diff mit `--kostenkarte`): `rot_lok = mean(dF[mkp & roi] > 1.0)`, `gelb_lok = mean(dM[fkp & roi] > 1.0)` (dF/dM sind durch die Kappe geteilt, 1.0 = tol). Mindestens 30 Kantenpixel je Art, sonst "nicht beurteilbar".
- **Regel**: Element gilt als lokal besser, wenn in >= 2 Fotos (gelb_lok_neu < gelb_lok_alt - 0.02 oder rot_lok_neu < rot_lok_alt - 0.02) und in keinem Foto (gelb_lok_neu > gelb_lok_alt + 0.02 oder rot_lok_neu > rot_lok_alt + 0.02). Fuer NEUE Elemente wird am selben ROI alt (ohne Element) gegen neu verglichen; fuer ENTFERNTE ebenso. Ein Kandidat faellt durch (e), sobald ein Element lokal schlechter ist. Kandidat mit lauter "nicht beurteilbar": (e) gilt als erfuellt, wird im Log als "ungeprueft" vermerkt.
- `elemente_best.json`: je Schluessel bester Stand (Stufe/Schritt-Tag, fest-Auszug des Bauteils, lokale Kennzahlen je Foto). Nach jeder Uebernahme aktualisieren. Lesbar fuer Menschen (indent 1).
- Kostenkarten liegen auf der Datenplatte (`<aus>/messung_<tag>/<nr>/kostenkarte.npz`) und werden nach der Entscheidung geloescht, ausser fuer den uebernommenen Stand.

## 4. Beweise (`tools/test_tor_elementbuch.py`, Daten aus null6; GPU: vorher `nvidia-smi --query-compute-apps=pid --format=csv,noheader` leer)
Ausgangsdaten: `/media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null6/stand.json` (Stufe 3 Schritte: v1 = 4 Boegen, uebernommen; v2 = Freiraum mit Eckoeffnungen), Plan `modelle/PLAN_STANDARD_qualitaetsstufen.json`, Fotos = `PS.fotos_waehlen(od, 12, ohne_nacht=True)` wie der Laeufer, Bewertungsmaske `<aus>/maske`.
Testordner: `/media/oem/scan/rc-park_null/test_tor_elementbuch/` (Datenplatte, danach aufraeumen bis auf JSON-Ergebnisse).
- T0 Toleranz: foto_diff zweimal auf derselben STL (s3_v1) und denselben 11 Fotos -> |rot-rot'| und |gelb-gelb'| je Foto; Maximum muss < tor_toleranz sein (sonst tor_toleranz = 2 x Maximum setzen und im Plan dokumentieren).
- T1 Ablehnung: alt = fest von v1, neu = fest von v2 (Eckoeffnungen). Erwartung: `uebernahme_tor` -> False mit Grund (a) oder (e) (welcher, im Bericht); zusaetzlich die Pruefstand-Zeile "Arkade Hauptfassade: Oeffnungen ab Boden (Anzahl)" (S1a, falls schon in der Masstabelle) rot.
- T2 Annahme: alt = fest von v1 mit `fassade_auto.bogen_kaempfer_versatz_m = +0.8` (absichtlich falsch), neu = fest von v1 (richtig). Erwartung: True, alle Buchstaben erfuellt, Elementbuch meldet die 4 Boegen lokal besser in >= 2 Fotos.
- T3 Identitaet: alt = neu = v1 -> False mit Grund (b) (t = 0), keine (a)-Verletzung.
- T4 Elementbuch-Schutz: alt = v1; neu = v1, aber ein Bogen um 0,6 m nach rechts verschoben (Elementdatei kopieren und u0/u1 des Bogens aendern, als `fassade_auto.datei`). Erwartung: False mit Grund (e) fuer genau dieses Element; die anderen 3 Boegen "gleich".
- T5 Martinstor: `tools/regression.py modelle/martinstor/objekt.json --pruefen` identisch (qualitaetsstufen ist nicht in der Kette, aber bauen_abnehmen/Pruefstand laufen mit); wenn baukasten_gen.py angefasst wurde, zusaetzlich `tools/bauen_abnehmen.sh martinstor` gruen.
- Bild: fuer T1 und T2 je ein Foto (004) das Overlay `foto_diff_004.jpg` von alt und neu ANSEHEN und in 2 Saetzen beschreiben; Pfade in den Bericht.
Jeder Test schreibt `ergebnis.json` mit bestanden/nicht; Exit 1, wenn einer durchfaellt. Werte NICHT nachjustieren, damit es gruen wird; wenn ein Test durchfaellt, Ursache beschreiben und STOPP.

## 5. Nicht aendern
`tools/foto_diff.py` (G2/S2 testen es gerade), `tools/pruefstand.py` (S1a arbeitet darin; die Werte-Erweiterung von `tor_fehler` passiert in qualitaetsstufen ueber `--bericht`, nicht im Pruefstand), Sollwerte, Schnappschuesse.

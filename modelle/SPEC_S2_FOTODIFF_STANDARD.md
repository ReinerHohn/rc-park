# Spezifikation S2: foto_diff-Beweis gueltig machen, mehrstufige Kanten als Standard entscheiden

Befund (S2-Analyse 5.11. 18:50, `modelle/STAND_2026-11-06.md`): keine Regression in `tools/foto_diff.py`/`test_foto_diff.py`. Der Beweis vom 4.11. galt
`kaufhaus_null4` (2372 Flaechen, Fassadendetails); auf dem Objekt-STL von `kaufhaus_null5` (LoD2-Rumpf, 682 Flaechen, fast keine Innenkanten) ist die
Versatzschaetzung haltlos (Gewinn 0,014, nicht "deutlich") und T1v faellt zufaellig durch. Mit `--mehrstufig` besteht null5; `martinstor_lod2` 014 besteht beides;
`martinstor` 014 hat keine Kamera (Absturz KeyError 'kamera').

## 1. Gueltigkeitstor im Test (`tools/test_foto_diff.py`, keine Schwelle aendern)
- Vor der Bewertung von T1v/T2v: Modellkantenpixel in der Bewertungsmaske >= `--min-kanten-px` (Standard 2000; Wert aus den Laeufen null4/s3_v9/martinstor_lod2 belegen:
  Median der bestandenen Laeufe / 5, im Bericht nennen) UND `T1_versatz.deutlich` (Gewinn >= 0,08) fuer das wahre Pruefbild. Sonst: Ergebnis "NICHT BEURTEILBAR"
  (Exit 3, JSON `gueltig: false`, Grund). Ein nicht beurteilbarer Test gilt NICHT als bestanden (Pflichtliste: "teilbewiesen").
- Beim fehlenden Kamerablock (`K-<foto>.json` ohne "kamera"): klare Meldung + Exit 3 statt KeyError.
- `--stl` bleibt; der Beweis laeuft auf dem BESTEN Stand (siehe 2), nicht auf dem Objekt-STL, wenn dieses nur der Rumpf ist.

## 2. Beweisobjekte (in `tools/nullstart_pflicht.json` und `modelle/PROTOKOLL_VALIDATOR.md` eintragen)
- Kaufhaus: `modelle/kaufhaus_null5/objekt.json --foto 004 --stl /media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null6/modell_s3_v9.stl` UND `modelle/kaufhaus_null4/objekt.json --foto 004`.
- Martinstor: `modelle/martinstor_lod2/objekt.json --foto 014` (Begruendung: K-014 mit Buendelkamera; `martinstor` hat fuer 014 nur Picks). Zusaetzlich ein Foto mit Kamera in `martinstor` suchen (K-Dateien mit "kamera" und buendel_tor ok, `python -c` Liste) und als drittes Beweisfoto nehmen.
- Alle Laeufe mit `--arbeit` auf der Datenplatte (`/media/oem/scan/rc-park_daten/test_fd_2026-11-06/s2/`), GPU nur frei (nvidia-smi) oder ueber job_start (GPU-Sperre).

## 3. Entscheidung mehrstufig
- Laeufe: die drei Beweisobjekte je ohne und mit `--fd=--mehrstufig`. Tabelle T0-T6b + gueltig.
- Regel (vorab): mehrstufig wird Standard, wenn alle gueltigen Laeufe mit mehrstufig bestehen, kein Lauf mit mehrstufig schlechter als ohne ist (T1v, T2v, T3, T4 jeweils nicht schlechter als 10 %),
  und die Overlays (`foto_diff_<nr>.jpg` je Objekt, ANSEHEN) keine Zunahme von Texturkanten (Pflaster, Ziegel) als gelb zeigen; Laufzeit je Foto nennen (CPU-Anteil der Kette).
- Umsetzung bei Ja: `foto_diff.py` Standard `--mehrstufig` an, `--einstufig` als Rueckweg; `FD_MEHRSTUFIG=0` fuer alte Vergleiche; Dokumentation im Docstring mit den Beweiswerten; Register-Abschnitt "CN - mehrstufige Fotokanten Standard".
- Bei Nein: Standard bleibt, Begruendung mit Zahlen im Register.

## 3b. Versatzkompensierte Kennzahlen (Befund S1b T2, 5.11. 19:45 - Voraussetzung fuer die Konvergenzschleife)
Fotos mit geschaetztem Kameraversatz 0,6-0,9 m (010, 214) bevorzugen ein um 0,6 m falsch verschobenes Bogenelement; eine korrekte Korrektur kann das strenge Tor so nie passieren.
foto_diff schaetzt den Versatz je Foto bereits (`versatz`: versatz_px/versatz_m, Gewinn, deutlich). Neu: zusaetzlich zu rot/gelb die Felder `rot_versatz`/`gelb_versatz` =
Anteile nach Verschiebung der Modellkanten um den geschaetzten Versatz (nur wenn `deutlich` und |versatz_m| <= 1,5 m, sonst gleich rot/gelb; Deckel als Argument `--versatz-max`),
ebenso `kosten_param_versatz`/`kosten_lr_versatz`. Der Versatz ist ein Stoerparameter je Foto-Modell-Paar; im Laeufer werden alt und neu je mit ihrem eigenen besten Versatz bewertet
(beide duerfen verschieben, keiner profitiert einseitig). Beweis: test_foto_diff T2v bleibt (Versatz wird weiter erkannt und gemeldet); test_tor_elementbuch mit `--rg-feld rot_versatz,gelb_versatz`:
T2 muss JA werden, T1 und T4 NEIN bleiben, T2b NEIN (b). Faellt T1 oder T4 auf JA: Deckel/Regel nicht lockern, Befund melden.

## 4. Absicherung
- `tools/regression.py` beider Objekte `--pruefen`: foto_diff steckt NICHT in der Martinstor-Kette (Uebergabe 4.11.), also Schnappschuesse unveraendert erwartet; falls doch Abweichung: nennen, nicht erneuern.
- `test_foto_diff` in den Nullstart-Schritt `beweise` (`tools/test_nullstart_schritte.py`) mit den Beweisobjekten aus 2 (nur, wenn das Objekt eine Buendelkamera fuer das Foto hat; sonst "nicht beurteilbar", Exit 3 wird dort als "teilbewiesen" gefuehrt).
- Kostenkarten/Entscheidungen des Laeufers aendern sich mit dem Standard: `qualitaetsstufen`-Laeufe, die VOR der Umstellung begonnen wurden, muessen ab der naechsten Stufe neu messen (Hinweis im Log, `FD_MEHRSTUFIG` im stand.json vermerken).

## 5. Nicht aendern
Schwellen (0,15 m, 0,08 Gewinn, tol 0,35), Pruefstand, Generator, qualitaetsstufen (S1b/S3). Erst starten, wenn S1b fertig ist (nutzt foto_diff fuer Beweise).

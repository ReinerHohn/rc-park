# Widerspruchsliste: gleiche Groesse, verschiedene Werte (mit Status)

Wozu: Stehen fuer dieselbe Groesse mehrere Werte in Registern, Logbuechern oder Quellen, dann landet der Widerspruch HIER als eine Zeile, auch wenn er schon geklaert ist. So greift niemand wieder zum widerlegten Wert. Anlass 24.11.2026: Die Martinstor-Hoehe war am 31.10. per Laser geklaert (54,8 m), trotzdem wurde am 19.11. mit "Turm ~60 m" und "LoD2 45 m" gerechnet.
Format, eine Zeile je Groesse (geprueft von `tools/wissen_ablage_pruefen.py`, Schnelltest):
`- <Objekt>: <Groesse> · Werte: <Wert> (<Quelle>), <Wert> (<Quelle>) ... · Status: offen | geklaert · gilt: <Wert + Beleg> · <Datum>`
Regeln:
- Vor jedem Rechnen mit einem Mass zuerst hier nachsehen: `python3 -I tools/wissen_suchen.py "<Groesse>"`. Die Suche liest diese Datei mit.
- Quellen werden nicht gemittelt (CLAUDE.md). Es gilt der unabhaengig belegte Wert (Laser, DOM1, mehrere Fotos). Der Grund steht in der Zeile.
- Eine geklaerte Zeile bleibt stehen. Wer den alten Wert wieder benutzt, haengt ein "Rueckfall <Datum>" an.

- Martinstor: Hoehe Turmspitze ueber Gelaende · Werte: 54,8 m (Laser DOM1-DGM1, MASSPRUEFUNG_MARTINSTOR "Was bewiesen ist"/"widerlegt", 31.10.), 53 m (OSM), 60-66 m (Textquellen: Bauforschung BW 65, Schwarzwaldportal 66, PDF-Absatz 60), ~60/~65 m (LOGBUCH_KETTENTEST_2026-11-19 Z.73/84/86), 45 m (LOGBUCH_KETTENTEST_2026-11-19 Z.117 "Hoehenprobe gegen LoD2-Hoehe 45 m" - das ist der LoD2-DACHFIRST, keine Spitze) · Status: geklaert · gilt: 54,8 m (Laser misst die heutige Spitze; 60-66 m widerlegt) · 31.10.2026; Rueckfall 19.11.2026 (Kettentest rechnete mit ~60 m und nahm den First 45 m als Turmhoehe)
- Martinstor: Dachfirst ueber Gelaende · Werte: 45,0 m (LoD2, MASSPRUEFUNG Teil 4), 46,2 m (Laser-Fit des Modells, MASSPRUEFUNG Teil 4) · Status: offen · Senken auf 45,0 m verschlechtert den Laser-Abgleich (Median 7 -> 10 %); LoD2 ist modelliert, Laser gemessen · 31.10.2026
- Martinstor: Torbogen-Scheitel · Werte: 6,55 m (Foto 030 schraeg), 6,0-6,6 m (Augenvergleich), 5,0-5,2 m (Fotos 050/002 frontal) · Status: geklaert · gilt: 5,0 m ±10 % (MASSPRUEFUNG_MARTINSTOR Teil 5: drei frontale Strassenfotos) · 31.10.2026
- Martinstor: Oberkante Bruchsteinsockel · Werte: 8,0 m (frueher), ≈ 6,2 m (Fotos 050/030) · Status: geklaert · gilt: 6,2 m (MASSPRUEFUNG_MARTINSTOR Teil 5) · 31.10.2026

# Aufwand und Nutzen aller Schritte der Sitzung 2026-11-03 (10:55 bis 12:05)

Zweck (Nutzerwunsch): Sweetspot "moeglichst schnell durch die Stadt, moeglichst viele Modelle in kurzer Zeit". Jeder Schritt wird festgehalten und NACH dem Ergebnis bewertet.
Zeiten sind GESCHAETZTE Arbeitsminuten dieser Sitzung (nicht gemessen), Rechenzeit gemessen wo angegeben (`modelle/aufwand/`). Nutzenklassen (vorab festgelegt):
**M** = veraenderte das Modell | **F** = deckte Fehler/falsche Annahme auf | **I** = Infrastruktur fuer Sweetspot/Pipeline | **K** = kein Nutzen. Bewertung vorlaeufig, "Nachbewertung" wird nach den Ergebnissen eingetragen.

## Bilanz in einem Satz (vorlaeufig)
Modelaenderung heute: EINE (Suedfenster 0,60 -> 0,77 m, ca. 2 mm in H0). Der Hauptnutzen heute liegt in aufgedeckten Fehlern/Annahmen (Sued-Netz entartet, Schafttiefe unbelegt, Restscherung der Wolken, defekter Suedclip) und in Messinfrastruktur - noch NICHT in einem besseren STL.

| Nr | Schritt | Aufwand | Ergebnis | Klasse | Bewertung vorlaeufig | Nachbewertung |
|---|---|---|---|---|---|---|
| 1 | Versuchslog + Register BV (Fensterbreite) | 5 min CPU | dokumentiert, Abnahme (Sichtblatt/Regression) noch offen | I | sinnvoll (Pflicht Regel 2/8b); Abnahme fehlt noch | |
| 2 | Review `bilder_schleife.py`/`bilder_holen.py` | 10 min | Bug `a.stufe` (0 = falsch) behoben; Schwaeche M13: Seite eines geholten Bildes = Seite des Nachbarfotos | F | sinnvoll (echter Bug + Designluecke) | |
| 3 | `video_dicht.py --aus` (M1) | 5 min | Option gebaut, ungetestet | I | sinnvoll, Nutzen erst nach Test | |
| 4 | `doppelschicht.py` (Plan 2.4) | 25 min CPU | unkorrigiert 7/7 Schichten doppelt, korrigiert 0/7; Fehlalarm-Falle (Helmpyramide) gefunden | F/I | teils: gutes QS-Werkzeug, aber noch keine Pruefzeile, nur Nord | |
| 5 | `lotpruefung.py` (Plan 2.3 Wolkenteil) | 40 min CPU | Restscherung +17..+35 mm/m auch nach Entzerrung; meine Annahme "Wand senkrecht" widerlegt durch Generator-Kontrolle | F | sinnvoll (Kontrolle deckte falsche Annahme auf); KEINE Modellaenderung, Drohne nicht unabhaengig | |
| 6 | Quelle der Generator-Verjuengung + LoD2-Test | 15 min | Schafttiefe 9,8->9,3->9,0 stammt aus Breiten, nie aus Tiefe gemessen: ANNAHME; LoD2 blind (Extrusion) | F | sinnvoll (Annahme sichtbar), Loesung braucht Suedfotos | |
| 7 | `aufwand_log.py` + Mitschrift Bodenwolke | 15 min | laeuft seit 11:14, Probe/min | I | sinnvoll (Voraussetzung fuer Sweetspot) | |
| 8 | `wolken_vergleich.py` + Basislinie | 20 min CPU | untere Nordwand z 5-20 m schwach (Strasse 43-165 Pkt/m2, Drohne Schaerfe 0,13-0,21) | I/F | sinnvoll (praezisiert die Hypothese zur Bodenwolke) | |
| 9 | `zeit_je_modell.py`, Zeitfelder in `treppe.py` | 15 min | Strassenmodell grob 11,6 min, voll 6,3 min; dichte Wolke 50-90 % | I | sinnvoll (Zeitbasis), `treppe.py`-Aenderung ungetestet | |
| 10 | Lot mit Abschnitten aus der Wolke | 10 min | Ergebnis haengt nicht an der Generatorwahl | F | teils (bestaetigte nur) | |
| 11 | Strang D Testlauf (Hintergrundagent, `bilder_holen.py`) | ca. 45+ min, bis 16 Kerne | KEIN Ergebnis (paarweise Kalibrierung auf CPU), beendet; Bodenwolke lief danach 9 statt 6 Karten/min? (nicht bewiesen) | K | NICHT sinnvoll in dieser Form; Lehre: Schwellen-Cache vor dem Lauf, Probe an 6 Bildern zuerst | |
| 12 | Quelleninventur 19 Clips (ffprobe + Kontaktboegen) | 15 min | 7 unbenutzt: 5 nicht Martinstor, 1 Strasse, 1 Blick vom Turm; F8y3 defekt | F | sehr sinnvoll (fand F8y3) | |
| 13 | Sued-Netz-Diagnose (pycolmap) | 20 min CPU | Netz entartet: Kameras bei x 4-5 statt 28-40 m (K-030/K-041 unabhaengig), Punkte z<3 m, kein SFM-AUSRICHTUNG-sued.json | F | sehr sinnvoll (deutet auf Softwareproblem statt Datenmangel) | |
| 14 | F8y3 reparieren (DASH), 150 Frames, `video_masken.py`, `--masken-vorlage` | 25 min + 3 min CPU | erste Bodenquelle Sued; Bahn/Personen maskiert (Grenze: Bahn-Nahwand) | F/I | sinnvoll; Wert erst nach SfM | |
| 15 | **Bodenwolke** (`video_dicht.py`, 7 Bodenclips, 350 Bilder) | >1,5 h GPU (ca. 40-45 W, Auslastung 100 %), ~1 CPU-Kern | laeuft, 668/700 um 12:01 | ? | Fertig 12:07 (gemessen: 54 Min. Wanduhr ab 11:14, GPU 42 W, 0,038 kWh; Gesamtlaufzeit ca. 1,6 h). Hypothese teils bestaetigt: Dichte z 5-20 m 4-17x hoeher; Schaerfe zwischen Drohne und Strasse; Lot +37 mm/m (schlechter); Tiefenlage 0,3-0,5 m abweichend; Sued/Ost/West kein Gewinn | **Nachbewertung 12:25 (vorlaeufig): Klasse K/F, Modellgewinn NICHT nachgewiesen; 1,6 h Wanduhr; als Standard im Stadtlauf NICHT empfohlen.** Endgueltig erst nach Pruefzeilen-Test mit/ohne Quelle |
| 16 | `dicht_vorpruefung.py` (Schranke vor dichter Rechnung) | 15 min | Martinstor: Boden lohnt nur fuer Nord ueber "neue Hoehenlage" (0,4 m vs 34 m), Drohne Ost/West lohnt, Fotos Sued lohnt (Netz-Problem) | I | sinnvoll als Entwurf; Schwellen ANNAHMEN, selbst ein Versuch | **Nachbewertung 12:25:** Vorhersage 'Boden lohnt nur Nord ueber Hoehenlage' STIMMT (Dichte unten hoeher, Sued/Ost/West nichts) - aber 'lohnt' hiess nicht 'verbessert das Modell': die Schranke misst Kameras, nicht Nutzen; sie haette die Rechnung nicht verhindert. Fuer Stadtlauf: Schranke um 'erwarteter Nutzen je Stunde' ergaenzen |

## Auswertungsregel fuer die Nachbewertung (vorab)
1. Bodenwolke: Dichte/Schaerfe/Lot (`wolken_vergleich.py`) gegen Basislinie, Gewinn an bestandenen unabhaengigen Pruefungen mit/ohne Quelle (Rauschband 5). Nutzen pro Wanduhrstunde gegen billigere Stufen.
2. Schranke (16): stimmt ihre Vorhersage ("Boden lohnt nur Nord, Hoehenlage") mit dem gemessenen Gewinn ueberein? Wenn nein -> Regel aendern, nicht Messung.
3. Jede Zeile ohne Nutzen (K) gibt eine Lehre als Zeile im Versuchslog (`versuch_log.py`), nicht nur hier.
4. Gesamtbilanz: Modelaenderungen / Wanduhrstunden und aufgedeckte Fehler / Wanduhrstunden - als Zahl in den Sweetspot uebernehmen.

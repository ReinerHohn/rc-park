---
name: erkenntnis
description: Eine Erkenntnis destillieren (RC-Park) - nach jedem ueberraschenden Befund, jeder gefundenen Ursache, jedem "warum merken wir das erst jetzt" oder widerlegten Urteil. Macht aus dem Einzelfund eine Pruefung in der Kette und eine Zeile im Erkenntnis-Register.
---
Ziel: Ein Fund darf nicht im Logbuch versickern. Er wird (a) ein Satz im Register, (b) eine Pruefung, die ihn beim naechsten Objekt von selbst findet, (c) eine Suche nach Geschwistern.

1. **Satz + Zahl + Beleg** in `modelle/ERKENNTNISSE.md` (eine Zeile: Datum · Erkenntnis · Messwert · Beleg-Pfad/Bild · Folge in der Kette). Keine Erzaehlung; die steht im Logbuch.
2. **Art bestimmen** (bestimmt die Folge):
   - DATEN (in den Bildern/der Datenbank steckt etwas Unerwartetes) -> Pflichtausgabe am Bild (Kontaktbogen) + Tor mit Zahl.
   - NICHT IN DER KETTE (Werkzeug/Handfolge existiert, wird nicht aufgerufen) -> Aufrufer in `tools/gesamtkette.py` + Kettenlauf als Beleg; `grep -L` gegen die Kette nach weiteren verwaisten Werkzeugen desselben Themas.
   - MESSFEHLER (mein Werkzeug hat falsch geurteilt) -> Werkzeug berichtigen, ALTE Urteile mit dem berichtigten Werkzeug nachmessen, widerlegte Zeilen in `NICHTS_GEBRACHT.md`/Register als berichtigt kennzeichnen.
   - ANNAHME WIDERLEGT -> die Stelle suchen, an der die Annahme steht (Doku, Kommentar, Schwelle), dort berichtigen.
3. **Die Frage "welche Pruefung haette es am ersten Tag gefunden?"** beantworten und GENAU DIESE Pruefung bauen (klein, generisch, ohne Vorwissen ueber das Objekt). Meist: ein Bild ansehen, das bisher nur als Zahl vorlag.
4. **Geschwister suchen:** wo gilt dasselbe Muster noch? (anderes Objekt, andere Stufe, gleiche Datenquelle). Mindestens eine Stichprobe messen, Ergebnis in dieselbe Registerzeile.
5. **Verhaltenslehre** (wenn der Fund an meiner Arbeitsweise lag) -> Memory `feedback-*`; Methodenlehre -> `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md` (Lehren-Register).
6. **Dem Nutzer melden:** Erkenntnis, Zahl, was ab jetzt automatisch geprueft wird, was offen bleibt. Danach Skill `logbuch-commit`.

Warum Recherche solche Funde nicht liefert: Recherche beantwortet die gestellte Frage ("wie wird der Mapper besser?"). Ein Datenbefund (Person im Vordergrund auf beiden Torseiten) steht in keiner Quelle - er steht in den eigenen Bildern. Vor jeder Recherche zu einem Fehlverhalten: die betroffenen Daten am Bild ansehen (Kontaktbogen der auffaelligen Gruppe).

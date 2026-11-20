# Spec: Formfund-Tor (Nutzerentscheid 11.11., 13:25 „Ja“)

**Anlass.** Bei Formfunden des Nutzers ist die Kantenmessung blind:
- Staffelgiebel West, Treppe statt Sägezahn: −0,002.
- Balkon-Stirnen: +0,004, lokal +0,004.

Lokales Messen hilft hier nicht (`SPEC_LOKALES_FOTOTOR.md`, Rückblick). Gebraucht wird, was der Nutzer selbst tut: Foto, Modell vorher und Modell nachher nebeneinander ansehen.

## Regel (zusätzlicher Weg, das Kantentor bleibt)
Eine Runde besteht über den Formfund-Weg, wenn ALLE Bedingungen gelten:
1. Das Ziel der Runde ist eine offene Beobachtung mit `wer` ~ „Nutzer“ und `formfamilie_test: true`. Sie muss das Zielteil betreffen ODER ein Teil, das der Patch nachweislich geändert hat; geänderte Teile werden per Dateivergleich der Teile-STLs bestimmt.
2. Die Foto-Note jedes GEÄNDERTEN Teils fällt um höchstens 0,005, sowohl auf den Torfotos als auch auf den Kontrollfotos.
3. Der Formfund-Prüfer (unten) urteilt `verbessert: true`, `erfunden: false`, `sicher` ≥ mittel.
4. Der normale Prüfer nimmt an.

Die Verschiebungskontrolle läuft, gibt aber nur Hinweise. Formfunde ändern die Lage nicht.

## Werkzeug `tools/formfund_pruefen.py`
- **Eingabe:** objekt, `--vorher` Teile-Ordner, `--nachher` Teile-Ordner, `--teile` (die geänderten Teile), `--befund` (Text des Nutzerfunds), `--aus` JSON.
- **Bilder:** Je geändertem Teil 3 bis 4 Fotos, Wahl wie in `tools/formfamilie_pruefen.py`:
  - meiste Sichtfläche,
  - verschiedene Richtungen,
  - Detail- und Konturkacheln, wo sinnvoll.
  
  Je Foto ein Dreierbild aus Fotoausschnitt, Render vorher und Render nachher, gleicher Ausschnitt, ganzes Modell schattiert, das Teil farbig. Die Kachel-, Render- und Fotowahl-Funktionen aus `formfamilie_pruefen.py` werden wiederverwendet (importieren, nicht kopieren, wo es geht).
- **Prüfer:** `claude -p` mit opus, gleicher Aufrufweg wie in `formfamilie_pruefen.py`. Fester Prompt:
  1. Erst die Form im Foto am betroffenen Merkmal beschreiben, dann vorher, dann nachher.
  2. Ist nachher näher am Foto als vorher, und zwar nur an diesem Merkmal? Antwort: `verbessert`.
  3. Hat nachher etwas, das im Foto nicht da ist (erfundene Form, falsche Bogenart, zu viel oder zu wenig Elemente)? Antwort: `erfunden`.
  4. Ausgabe als JSON `{verbessert, erfunden, sicher: hoch|mittel|niedrig, begruendung, fotos}`.
  
  Den Befundtext gibt es als FRAGE („Der Nutzer meldet: …; prüfe am Foto, ob das stimmt und ob nachher besser ist“), nicht als Tatsache. Ein Fehler oder fehlendes JSON heißt `ungeprueft`, nicht „passt“.
- Laufzeit sparsam: ein Prüferaufruf je Runde mit allen Bildern.

## Beweis (Pflicht vor dem Einhängen): `tools/test_formfund_tor.py`
Grundlage sind die Teile-Ordner vorher und nachher aus den Laufordnern unter `/media/oem/scan/rc-park_kreis/kaufhaus_grob3/<lauf>/`. Fehlt ein Nachher-Ordner, den Patch in einen Worktree anwenden und mit `BAUTEILE_AUS` exportieren.

**Positiv, soll bestehen:**
- a125135 r1: Westgiebel Treppe, Befund #Treppe
- a095328 r1 bzw. a104922: Gewölbe Rippen (Befund Gewölbeansatz)

**Negativ, soll durchfallen:**
- a091923 r2: Tor rund, Befund (alt, falsch) „Tor ist rund statt spitz“. Das Foto zeigt einen Spitzbogen, also muss nachher schlechter oder erfunden sein.
- a102727 r1: Rinne zu hoch; Befund generisch „Rinne/Traufe“.
- Ein synthetischer Fall: Westgiebel nachher plus ein erfundener Kasten 0,5 m auf einer Stufe; muss `erfunden: true` ergeben.

**Offen, zur Auswertung:**
- a105629 r2 bzw. a123234 r1: Balkon-Stirnen, Befund Seitengeländer. Der Agent hatte die Baluster-Zahl angenommen, das Urteil ist hier ehrlich offen.

**Ziel:** alle Positiven bestehen, alle Negativen fallen. Wenn nicht: Ursache je Fall berichten, höchstens 2 Verbesserungsrunden.

## Randbedingungen
- Neue Dateien: `tools/formfund_pruefen.py`, `tools/test_formfund_tor.py`. Keine bestehenden Dateien ändern; `formfamilie_pruefen.py` nur importieren.
- Kein Commit, nichts löschen, kein Objektname im Code.
- GPU-Regeln aus CLAUDE.md. Arbeitsdaten unter `/media/oem/scan/rc-park_tmp/formfund/`.
- Mindestens 4 Dreierbilder selbst ansehen (Read), bevor die Prüfer laufen.
- Das Einhängen in `bauteil_kreis.py` (Frühablehnung bei „Stufe halb ohne Gewinn“ für Formfund-Runden aussetzen, Entscheidung nach der Regel oben) macht der Koordinator nach dem Beweis.

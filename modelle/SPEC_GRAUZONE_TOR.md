# Spec: Grauzonen-Tor (Formfund-Tor Stufe 2, Nutzer 11.11. 14:15 "Ja")

## Anlass
76 verworfene Runden am 11.11., viele davon mit einer Kantennote (Foto-F1) zwischen -0,005 und +0,02: nicht schlechter, aber nicht klar besser. In diesem Bereich ist die Kantennote blind für Form (L46, L47, L50). Das Formfund-Tor (`tools/formfund_pruefen.py`) urteilt am Dreierbild Foto|vorher|nachher. Im Probelauf hat es 8 von 8 Fällen richtig entschieden (`SPEC_FORMFUND_TOR.md`).

## Regel (erst nach Beweis einbauen)
Eine reguläre Runde, also keine Nutzerfund-Runde, besteht über die Grauzone nur, wenn ALLE Bedingungen erfüllt sind:
- **Kantennote:** Gewinn am Foto-F1 im Bereich [-0,005; +0,02).
- **Höhenwert:** fällt um höchstens 0,02.
- **Kontrollfotos:** nicht schlechter als -0,005.
- **Grauzonen-Prüfer:** urteilt `verbessert: true`, `erfunden: false`, `sicher: hoch`.
- **Normaler Prüfer:** nimmt an.

Der Prüfer bekommt KEINEN Agentenbericht und keine Absichtserklärung. Er erhält nur Teilname und Bilder. Seine Frage lautet: „Was hat sich zwischen vorher und nachher geändert? Ist nachher näher am Foto? Ist etwas erfunden?“ So bleibt er frei vom Selbstlob des Agenten.

## Beweis: `tools/test_grauzone_tor.py`
1. **Rückblick-Satz:** alle gespeicherten verworfenen Runden mit Generatoränderung, die in der Grauzone lagen.
   - Quellen: `rc-park_kreis/kaufhaus_grob3/*/kreis.jsonl`, `verworfen_rN.patch`, Teile-Ordner vorher/nachher.
   - Fehlen die Teile-Ordner: Patch in einen Worktree anwenden und mit `BAUTEILE_AUS` exportieren.
   - Liste wie beim Rückblick in `SPEC_LOKALES_FOTOTOR.md` (Agent dort: `/media/oem/scan/rc-park_tmp/` lokal*); vorhandene Liste wiederverwenden.
2. **Fallen** (mindestens 12, synthetisch an echten Teilen mit sichtbarem Fotobeleg), je Art 3 Fälle:
   - erfundener Kasten oder Vorsprung 0,3 bis 0,5 m,
   - Teil 0,3 m verschoben,
   - falsche Formfamilie (spitz ↔ rund, Treppe ↔ Sägezahn, Rippen weg),
   - Teil um 20 % skaliert.
3. **Bekannte Fälle:**
   - Negativ: a091923 r2 (Tor rund) und a044705 r4 (erfundene Facetten) müssen fallen.
   - Positiv: a095328/a104922 (Gewölbe) müssen bestehen, diesmal ohne Befundtext.
4. **Messgrößen:**
   - Fehlannahmen-Quote auf den Fallen; Soll < 5 %, also höchstens 0 von 12.
   - Annahmen im Rückblick.
   - Für jede Annahme im Rückblick 1 Dreierbild selbst ansehen und ein eigenes Urteil daneben.
   - Bericht als Tabelle: Runde | Teil | F1 vorher/nachher | Urteil | sicher | eigenes Urteil | Bildpfad.

## Randbedingungen
- Nur neue Dateien: `tools/test_grauzone_tor.py`. Wird eine Prompt-Variante ohne Befund gebraucht, dann als neue Option in `formfund_pruefen.py`.
  - Die Option `--ohne_befund` darf eingebaut werden, das Verhalten ohne Option muss bitgleich bleiben.
  - Danach `tools/test_formfund_tor.py` erneut grün.
- **Laufzeit:**
  - Bilder auf der GPU nacheinander.
  - Prüferaufrufe bis zu 3 parallel; das ist CPU- bzw. netzgebunden.
  - Mit `gpu_slot` und `JOB_GPU_MB` gemäß CLAUDE.md.
- Kein Commit, nichts löschen, kein Objektname im Code. Arbeitsdaten unter `/media/oem/scan/rc-park_tmp/grauzone/`.
- **Zwischenbericht** per SendMessage nach den Fallen (vor dem Rückblick): Die Fehlannahmen-Quote entscheidet, ob der Rückblick lohnt.
- Einbau in `bauteil_kreis.py` macht der Koordinator.

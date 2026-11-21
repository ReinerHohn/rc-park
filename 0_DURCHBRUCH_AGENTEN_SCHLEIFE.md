# 0 · DURCHBRUCH: Die Agenten-Schleife (Nacht 21./22.11.2026)

> **Gigantische, bombengeile Hardcore-Erfahrung (Nutzer 22.11.2026, 00:50).** Zentral für alles Weitere.
> In einer Nacht ging das Schwabentor von „Klumpen, flache Fenster, Kasten-Vordach, glockiges Dach, runde Säule“
> zu Quaderlagen, gemessenen Rundbogenfenstern, geschweiftem Vordach, gerader Dachpyramide und offener Laterne,
> und zwar NUR über Kettenläufe plus selbst gestartete Agenten, nicht über Handarbeit am Modell.

## Ziel
Neue Gebäude sollen möglichst ohne Agenten durch die Kette laufen. Ganz ohne geht es nie, weil jedes Gebäude Besonderheiten hat.
Das ist auch nicht schlimm. Wichtig ist, dass der Kreislauf **automatisch** läuft: Agenten finden das Diff, beheben es als
Kettenstufe, die Kette prüft. Jede Besonderheit wird zur allgemeinen Stufe, darum braucht jedes weitere Gebäude weniger Runden.

## Die drei Schlüssel (warum ich Agenten selbst starten kann statt der Nutzer)
1. **Erlaubnis + feste Regel.** Gedächtnis „parallele Code-Arbeit per Agent im Worktree selbst starten“ und Nutzerauftrag
   „Plan entwickeln, dann arbeiten einfache Agenten das ab“. Vorher wurde gefragt oder selbst gefummelt.
2. **Feste Agenten-Vorlage** (modelle/PLAN_NACHT_2026-11-21.md, Schritt 6). Jeder Agent bekommt:
   - genau EINEN Befund (mit Bildpfad, Log, Zahlen);
   - einen eigenen Worktree und `model: "opus"`;
   - Lieferpflicht: Ursache benennen + **Kettenstufe/Werkzeug-Fix + Test** (tools/test_*.py, Zeile in schnelltest.sh);
   - Verbote: keine Handstand-Werte, nicht selbst mergen, KEINE Rechenläufe während eines Kettenlaufs (15 GB RAM);
   - Bericht: Fehlerliste zuerst, Kontrollbild NEBEN dem Foto (selbst angesehen), Realitäts-%.

   Das Schlimmste, was passieren kann, ist ein Zweig, der nicht gemergt wird. Deshalb geht es ohne Rückfrage.
3. **Ein Tor, das sich nicht beschönigen lässt.**
   - Merge nur bei `bash tools/schnelltest.sh` = 0 Fehler (inkl. `test_undefinierte_namen`).
   - Nach JEDEM Lauf das **Nebeneinander-Bild** `audit/neben_*.jpg` (Foto | Modell) ansehen und schicken.
   - **Wichtigster Schlüssel der Nacht:** Nutzer „Das ist noch nicht gut“ bei 11/11 Handstand-Treffern. Ab da zählte das
     Bild, nicht die Zahl. Erst dadurch gingen die Agenten auf das, was sichtbar falsch war.

## Der Kreislauf (heute noch von mir gesteuert, Ziel: Skill/Workflow `kette-schleife`)
1. **Kettenlauf** (immer nur EINER, `tools/job_start.sh`, RAM-Buchung). Speichermangel → Stufe wird im Lauf wiederholt.
2. **Auswerten:** `ERGEBNIS DES LAUFS`, Tore (foto_diff, Umriss-Tor, Fenster-Form-Tor, hand_vergleich, ebenen_abweichung),
   `seiten.jpg` + `neben_*.jpg` ANSEHEN → Fehlerliste mit sichtbaren Fehlern.
3. **Je Befund ein Agent** (Vorlage oben, höchstens 2 gleichzeitig, nur Code solange die Kette läuft).
4. **Merge-Probe** in eigenem Worktree auf /media/oem/scan (Konflikte vorab lösen, Einzeltests) → nach Laufende
   Merge in main → voller Schnelltest → Push → nächster Lauf.
5. Erst der **Kettenlauf** beweist einen Fix. Agenten-Kontrollbilder sind nur Proben.

Automatisierbar als Nächstes: Befundliste aus Bild + Toren durch einen Prüf-Agenten (JSON), Agentenstart und Merge nach Regeln.

## Lehren der Nacht (je eine benannte Ursache)
- **Zirkuläre Messung, zweimal:**
  - das gebaute Vordach verdeckte seinen eigenen Beleg (Selbstbau-Verdecker);
  - Einzelfoto-Orthos auf dem STL des VORIGEN Laufs → Kanten kleben an alten Nähten,
    das Tor wechselte von Lauf zu Lauf zwischen 4,3 und 5,2 m.

  Messungen dürfen nie vom eigenen vorigen Modell abhängen. Bei kippelnden Ergebnissen zuerst danach suchen.
- **Probe ≠ Kette:** Ein Fix, der in der Agenten-Probe stimmt, kann in der Kette nicht ankommen (andere Eingabedateien,
  Reihenfolge der Stufen, Log zeigt nur die letzten Zeilen). Immer am nächsten Kettenlauf prüfen.
- **Zahl ≠ Aussehen:** 11/11 prüft nur Höhen und Lagen. Form, Tiefe und Lesbarkeit zeigt nur das Nebeneinander-Bild.
- **Wolke/DOM1 erzeugen Formen, die es nicht gibt:** Die Dachstufen kamen aus dem 1-m-Laserraster, der Absatz war ein Wolkendeckel.
  Fotokanten schlagen Wolke (KERNMETHODE).
- **Speicher:** Agenten-Testläufe parallel zur Kette → OOM. Seitdem gilt: ein Job, Agenten rechnen nicht, Wiederholung bei Speichermangel.
- **Merge-Fehler fangen:** Die Zeile `q5, q95 = …` rutschte in einen Kommentar → NameError nach 20 min.
  Seitdem prüft pyflakes im Schnelltest auf neue undefinierte Namen.

Details: modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md · Plan: modelle/PLAN_NACHT_2026-11-21.md · Register: modelle/ERKENNTNISSE.md

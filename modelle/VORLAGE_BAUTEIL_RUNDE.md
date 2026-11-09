# Vorlage: Bauteil-Runde (ein Bauteil neu oder richtig bauen)

Stand 9.11.2026. Entstanden aus der Erker-Runde am Kaufhaus (Runde 7).

**Zweck:** Jedes neue oder falsche Bauteil an jedem Gebäude läuft nach demselben Ablauf. Ein Agent bekommt diese Vorlage mit ausgefüllten Platzhaltern als Auftrag.
Der Prüfer (starkes Modell oder Nutzer) prüft nur zwei Dinge:
- die Formbeschreibung (Stufe 0), BEVOR gemessen wird,
- den Bericht am Ende.

**Grundsatz:**
- Die FORM kommt aus den Fotos: Zonen, Grundriss, Anzahl.
- Die LAGE kommt aus Triangulation und Wolke.
- Wer die Form nicht beschrieben hat, darf nicht messen. Sonst entsteht ein „besserer Kasten“ (Erker) oder eine „Sprungschanze“ (Gauben).

Platzhalter: `<OBJEKT>` (z. B. kaufhaus_grob3), `<BAUTEIL>` (z. B. erker:0, erker:1), `<BEFUND>` (Nutzer- oder Prüferbefund wörtlich), `<FOTOS>` (Startfotos, falls bekannt), `<TABU>` (Dateien, an denen gerade andere Agenten arbeiten), `<RUNDE>`.

---

## Auftragstext (kopieren, Platzhalter füllen)

Repo /home/oem/git/rc-park, Objekt `<OBJEKT>`. Sprache Deutsch. Auftrag: Bauteil(e) `<BAUTEIL>` nach Foto belegen und im Generator richtig bauen. Befund: „`<BEFUND>`“.

ZUERST LESEN: `CLAUDE.md` (Regeln 2, 3b, 3c, 8b, 9, 9b, 9c, 9d), `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md` (Messweg und Lehren-Register), `modelle/NICHTS_GEBRACHT.md`, das Logbuch der letzten Generatorrunde von `<OBJEKT>`.

### Stufe 0: Formbeschreibung (Pflicht, vor jeder Messung)
1. Fotos je Bauteil wählen:
   - `tools/bauteil_sichtliste.py --wolke …` und `tools/kamera_bruecke.py --kandidaten`.
   - Mindestens 3 Fotos aus verschiedenen Richtungen, davon mindestens 1 Nahfoto und 1 Übersicht.
   - Vorher den Modellpunkt ins Foto projizieren und prüfen, welches Teil wo liegt (L18).
2. Die Fotos ANSEHEN und schriftlich beschreiben (Abschnitt „Formbeschreibung“ im Logbuch):
   - **Zonen** von unten nach oben (z. B. Unterbau/Konsole, Brüstung/Wappenzone, Fensterband, Traufe, Dach). Je Zone die Grundform (Prisma, Pyramide, Kegelstumpf, Bogen …) und ihre Elemente.
   - **Grundriss bzw. Querschnitt**: Rechteck, Teil-Vieleck, rund? Wie viele Flächen sind sichtbar, und wo schließt das Teil an die Wand an?
   - **Wiederholungen** je Fläche oder Zone (Lichter, Felder, Rippen, Stufen). Nur benennen, gezählt wird in Stufe 1.
   - **Anschlüsse** an Nachbarteile (Helm sitzt auf der Traufe, Konsole unter dem Unterbau). Gleiche Achse und gleiche Maße müssen zusammenpassen.
   - **Was am aktuellen Modell anders ist**: Overlay oder Detailrender neben dem Fotoausschnitt (Regel 9b).
3. Formfamilie festlegen:
   - Gibt es sie schon in `tools/baukasten_gen.py`, die vorhandene nehmen.
   - Fehlt sie, eine neue GENERISCHE Familie mit freien Parametern bauen, ohne Objektnamen oder Festwerte im Code.
   - Begründung ins Logbuch.
4. Unsicherheiten als Frage notieren, z. B. „Rückseite nicht sichtbar → ANNAHME Spiegelung“.

### Stufe 1: Zählen (nur am Foto)
- Mit `tools/foto_zaehlung.py` (Protokoll Z-*.json mit markiertem Bild) zählen: Flächen des Grundrisses, Elemente je Fläche, Elemente je Zone.
- Verdeckte Teile aus mindestens 2 Richtungen zählen.
- Nie aus Wolke, LoD2 oder Generatordateien zählen (Regel 9, Register CB).

### Stufe 2: Messen
- Zonengrenzen (Höhen), Auskragung, Flächenbreiten und Achslage per `tools/foto_mass.py --tri` über mehrere Kameras messen, ergibt Messprotokolle M-*.
- Messebene nie aus dem Grobkörper übernehmen (L16).
- Steile oder schlanke Teile: Profil r(z) aus Fotosilhouetten durch die Bauteilachse (L17).
- Die Wolke nur zur Gegenprobe der Lage nutzen.
- Bei Widerspruch ein drittes, frontales Foto holen (L19). Nicht mitteln (Regel 5).

### Stufe 3: Prüfung, die vorher fehlschlägt
- Befund als `beobachtungen_offen` in `modelle/<OBJEKT>/masstabelle.json` eintragen.
- Je gezähltem und gemessenem Merkmal eine Prüfung mit Sollwert, Quelle und Protokoll anlegen.
- `tools/bauen_abnehmen.sh <OBJEKT>` auf dem ALTEN Stand laufen lassen: Die neuen Prüfungen müssen ROT sein. Wenn nicht, prüfen sie das Falsche.

### Stufe 4: Generator
- Familie und Parameter in `objekt.json` eintragen.
- Jedes Element bekommt `beleg(seite, element, quelle)`, Annahmen heißen `ANNAHME: …`.
- Alte Teile auf `aktiv: false` setzen, nicht löschen, nie ersatzlos abschalten (Regel 9c).
- Druckbarkeit erhalten: 1 Teilnetz, wasserdicht, Wandstärke.

### Stufe 5: Abnahme und Sichtprüfung
1. `tools/bauen_abnehmen.sh <OBJEKT>` bis „alle Pruefungen bestanden“. Sollwerte nie lockern.
2. Bei Werkzeugänderung: `tools/regression.py modelle/<OBJEKT>/objekt.json --pruefen`.
3. `tools/teile_lage_pruefen.py <OBJEKT>`, `foto_diff`, `fehlteile_finden` laufen lassen, und `audit/seiten.jpg` ANSEHEN.
4. Overlays je Bauteil in mindestens 3 Fotos, Vorher und Nachher nebeneinander: `audit/gitter_generator/runde<RUNDE>_<bauteil>_<foto>.jpg`. SELBST ansehen.
5. Wenn vorhanden: `tools/teile_sichtpruefung.py` für das Bauteil laufen lassen. Erst ab bewiesenem Gate zählt das Urteil, bis dahin nur als Zusatzhinweis.

### Randbedingungen
- Kein Commit, kein Löschen, kein Slicen oder Drucken ohne Nutzerwort.
- Große Zwischendateien gehören nach `/media/oem/scan/rc-park_daten/<objekt>/agent_scratch_<RUNDE>/`, nicht auf die Root-Platte.
- GPU-Jobs laufen über `JOB_GPU_MB=<MiB> tools/job_start.sh …`. Neue Rechenwerkzeuge nutzen die GPU.
- NICHT anfassen: `<TABU>`.
- Ehrlich bleiben: Nur selbst am Bild Geprüftes heißt „trifft“, sonst „ungeprüft“.

### Bericht (Pflichtform)
1. **Formbeschreibung** (Stufe 0), mit den 3+ Fotos und der gewählten Formfamilie.
2. **Zählungen** mit Z-Protokoll.
3. **Tabelle der Prüfungen**: vorher, nachher, Sollwert, Quelle.
4. **Overlay-Pfade.**
5. **Fehlerliste je Bauteil und je Zone**: trifft, trifft nicht, ungeprüft.
6. **Geänderte Dateien.**
7. **Generalisierte Lehre**: Lehre | Anlass | Werkzeug. Zusätzlich ins Lehren-Register von REZEPT_GEBAEUDE_AUS_FOTOS.md eintragen, Fehlschläge in NICHTS_GEBRACHT.md.

---

## Prüfer-Checkliste (für den, der den Agenten startet)
- [ ] Platzhalter gefüllt. `<TABU>` gegen laufende Agenten geprüft (Dateikonflikte).
- [ ] Nach Stufe 0, wenn möglich: Formbeschreibung gegen die Fotos selbst prüfen. Zonen, Grundriss und Anschlüsse vollständig?
- [ ] Bericht: Overlays SELBST ansehen, Übersichtsfoto ganz plus bestes Foto je Bauteil. Fehlerliste über ALLE Bauteile, nicht nur das bearbeitete.
- [ ] Erst danach commit und Nutzermeldung, mit Fehlerliste vor Lob.

## Was diese Vorlage (noch) nicht leistet
- **Entdecken**, dass ein Teil fehlt oder falsch ist: Das kommt heute vom Nutzer oder Prüfer. Später soll es aus dem ROT von `teile_sichtpruefung.py` kommen (sobald bewiesen) und aus einer Objekterkennung (OWLv2) für ganz fehlende Teile.
- **Formbeschreibung automatisch**: Stufe 0 ist Sichtarbeit des Sprachmodells mit Protokoll. Ziel: Vorschlag der Formfamilie aus Erkennung plus Fotokanten. Das Prüfer-Häkchen bleibt.

## Verlauf
| Datum | Bauteil | Objekt | Ergebnis |
|---|---|---|---|
| 9.11. | erker:0, erker:1 (Runde 7, erste Anwendung, Formbeschreibung vom Prüfer vorgegeben) | kaufhaus_grob3 | läuft |

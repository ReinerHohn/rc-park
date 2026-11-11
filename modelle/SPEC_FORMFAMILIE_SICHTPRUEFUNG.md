# Spec: Formfamilien-Sichtprüfung je Bauteil (`tools/formfamilie_pruefen.py`)

Nutzerauftrag 11.11. („Ja machen“). Anlass: Der Nutzer fand am 11.11. zwischen 08:38 und 08:48 im Viewer 8 Formfehler, die der Kreis nie gefunden hat:
Sägezahn statt Treppe, spitz statt rund, Rechteck statt Bogen, Sockel zu niedrig, fehlende Aufsätze und Geländer.
Die Kantenmessung (Foto-F1) entscheidet keine Formfamilie: Sie misst Kantendichte (Lehren L46, L47 in `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md`).
Gebraucht wird, was der Nutzer tut: Foto und Modell nebeneinander ansehen und nur die FORMFAMILIE vergleichen.

## Was das Werkzeug tut
1. **Eingabe:**
   - Objekt (`kaufhaus_grob3`)
   - Teile-Ordner: Teil-STLs eines Kreislaufs, z. B. `/media/oem/scan/rc-park_kreis/kaufhaus_grob3/<lauf>/teile_r1_vorher/` vom aktuellen main. Alternativ selbst exportieren wie in `tools/bauteil_kreis.py`, Umgebungsvariable `BAUTEILE_AUS`, aber nur in einem eigenen Arbeitsordner oder Worktree, nie in main.
   - Formliste: `/media/oem/scan/rc-park_kreis/kaufhaus_grob3/fotoform/<stl_sha>_v2_wolkenverdeckung_festbereich.json`. Je Teil und Foto stehen dort `mk_px`, `fk_px` und `sicht_px`.
   - `--teile` als Liste, ohne Angabe alle Teile.
2. **Fotowahl je Teil:**
   - 3 bis 4 Fotos mit der größten sichtbaren Fläche (`sicht_px`) aus der Formliste.
   - Möglichst verschiedene Blickrichtungen (mindestens 25 Grad Unterschied, Kamerazentren aus der Kameradatei).
   - Mindestens ein Foto, das das Teil schräg oder von der Seite zeigt, falls vorhanden.
3. **Bildpaar je Foto:** zwei Bilder gleicher Größe nebeneinander, als JPG in den Arbeitsordner.
   - **Links:** Fotoausschnitt um die projizierte Teilbox (+30 % Rand), entzerrt wie in `tools/teil_fotoform.py`.
   - **Rechts:** schattierter Render des **ganzen Modells** aus derselben Kamera, gleicher Ausschnitt.
     - Das Zielteil ist farbig hervorgehoben, der Rest grau.
     - Schattierung über Normalen, damit Bögen, Stufen und Sockel als Form lesbar sind.
     - Nur die Kantenüberlagerung reicht nicht, der Render muss die Form zeigen.
   - **Wiederverwendung:**
     - Kamera: `fehlteile_finden.kamera_laden`, `teil_fotoform.rahmen`
     - Raster: `render_kern.dreiecke_rastern` (GPU, liefert Tiefe und Position)
     - Mesh: Maßstab `stl_massstab/1000`
     - Kameradatei und Fotos: siehe `objekt.json` bzw. Aufrufe in `tools/fotoform_auffrischen.sh`
4. **Urteil je Teil:**
   - **Wer urteilt:** Ein Bildprüfer, `claude -p` mit Modell opus.
   - **Was er bekommt:** Die Pfade der Bildpaare. Er soll sie mit dem Read-Werkzeug ansehen, das Bilder anzeigt.
   - **Prompt, kurz und fest:**
     - Erst die Form im Foto beschreiben, dann die im Modell.
     - Dann NUR Formfamilien-Abweichungen nennen:
       - Bogenart (rund, spitz, gerade, Segment)
       - Stufen (Treppe oder Zacke oder Dach)
       - Anzahl gleicher Elemente
       - fehlende oder erfundene Elemente (Sockel, Aufsatz, Geländer, Stirn, Rippen)
       - Proportion grob, falls mehr als etwa 30 % daneben
     - Keine Farb-, Textur- oder Feinlagefehler.
     - Ausgabe als JSON: `{"teil", "fotos", "form_foto", "form_modell", "abweichungen": [{"merkmal", "foto", "modell", "fotos_belegt": [...], "sicher": "hoch|mittel|niedrig"}]}`
   - Läuft der Prüfer in einen Fehler oder liefert kein JSON, heißt das Ergebnis „ungeprüft“, nicht „passt“.
5. **Ausgabe:**
   - `<arbeit>/formfamilie.json` (alle Teile) und `<arbeit>/bilder/`.
   - Noch NICHT in `masstabelle.json` schreiben und nicht in den Kreis einhängen. Das kommt erst nach dem Beweis und meinem Okay.

## Beweis (Pflicht, Regel 3e: Nutzer-Sichtfunde als automatischer Test)
`tools/test_formfamilie_nutzerfunde.py` läuft das Werkzeug auf den Teilen unten und wertet aus.

**Nutzerfunde 11.11. (Sollbefund: Abweichung erkannt):**
1. `staffelgiebel__ost` und `staffelgiebel__west`: Stufen sind waagerechte Treppen; im Modell Sägezahn/Dächlein.
2. `bruestung__balkon`: seitliche Geländer (Stirnen) an beiden Balkonenden fehlen.
3. `baldachinreihe__baldachine`: Maßwerk-Aufsatz über jedem Baldachin fehlt.
4. `bogenreihe__laube`: Säulensockel (achteckiger Fuß) im Foto viel höher.
5. `bogenreihe__laube` oder die Stirnseite der Laube (welches Teil die Seitenöffnung bildet, selbst klären): Seitendurchgänge sind Bögen, im Modell Rechteck.
6. `freiform__tor_b2__ausschnitt`: Tor in der Rückwand ist rund, im Modell spitz.
7. `erker_polygon__0`: Rippennetz/Maßwerk fehlt (schon bekannt).

**Gegenprobe (sollen KEINE groben Formfamilien-Abweichungen melden oder höchstens „niedrig“):**
- `helm_geschweift__o`
- `helm_geschweift__w`
- `zylinder__dienst_laube_u975_schaft`
- `gaubenreihe__unten`

**Bericht:**
- Trefferquote je Fund (welcher Fund erkannt, mit welchem Text und welcher Sicherheit).
- Fehlalarme der Gegenprobe.
- Laufzeit und Kosten (Anzahl der claude-Aufrufe).

**Ziel:** mindestens 6 von 7 Funden erkannt, höchstens 1 Fehlalarm „hoch“.

**Ehrlich bleiben:**
- Gelingt es nicht, die Ursache je verfehltem Fund nennen (Bildausschnitt falsch? Render unlesbar? Prompt?), bis zu zwei Verbesserungsrunden machen, dann berichten.
- Niemals den Prompt mit den Sollbefunden füttern (das wäre Selbstbezug).

## Randbedingungen
- Neue Dateien nur `tools/formfamilie_pruefen.py`, `tools/test_formfamilie_nutzerfunde.py` und diese Spec. Keine bestehenden Werkzeuge ändern.
- Kein Commit, kein Löschen.
- Arbeitsdaten nach `/media/oem/scan/rc-park_tmp/formfamilie/`.
- **GPU-Rasterung:**
  - Python `/media/oem/scan/venv-seg/bin/python -I`.
  - Vor dem Start `nvidia-smi` prüfen. Der Kreis nutzt die GPU parallel; zusammen höchstens etwa 7000 MiB VRAM.
  - Lange Läufe über `JOB_GPU_MB=<MiB> tools/job_start.sh NAME LOG BEFEHL`, im Vordergrund warten mit `until grep -q JOB_ENDE LOG; do sleep 20; done`. Nicht im Hintergrund warten.
- Kein Objektname im Werkzeugcode, alles aus `objekt.json` und den Argumenten.
- Bilder selbst ansehen: Mindestens 3 Bildpaare mit dem Read-Werkzeug prüfen, bevor die Prüfer-Aufrufe starten. Ausschnitt und Render müssen dasselbe zeigen.

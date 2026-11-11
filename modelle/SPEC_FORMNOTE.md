# Spec: Formnote (Realität Teil 2: Form)

Nutzerentscheid 11.11., 14:30: „Ja“.

## Anlass
Die Realitätszahl misst heute nur, ob die Kanten an der richtigen Stelle liegen (Foto-F1), und ist dadurch blind für die Form (L46, L47, L50). Wird ein Nutzer-Formfund richtig umgesetzt, bewegt sie sich kaum. Künftig wird die Realität dreiteilig berichtet:
- **Lage:** Foto-F1, sobald es die Fassung mit festem sigma gibt
- **Form:** diese Spec
- **Offene Funde:** Zahl der offenen Nutzer-Formfunde in der Masstabelle

Die drei Teile werden getrennt berichtet und nie gemittelt.

## Werkzeug `tools/realitaet_form.py`
- **Eingabe:**
  - `objekt`
  - `--teile_dir` (Export der Teile aus dem Generator mit `BAUTEILE_AUS`) oder `--stl` (dann selbst exportieren)
  - `--aus JSON`
  - `--nur TEIL,...`
  - `--cache_dir`
- **Je Teil:** feste Wahl von 3 bis 4 Fotos plus eine Konturkachel. Die Kriterien entsprechen `formfund_pruefen`/`formfamilie_pruefen.fotowahl`: meiste Sichtfläche, verschiedene Richtungen.
  - Die Fotowahl wird beim ersten Lauf in `<cache_dir>/fotowahl.json` gespeichert und danach nicht mehr geändert. So bleiben die Werte über die Zeit vergleichbar.
  - Je Foto ein Zweierbild: Fotoausschnitt | Render des Modells; das Teil farbig, das übrige Modell schattiert.
- **Prüfer** (`claude -p`, opus, Aufrufweg wie `formfund_pruefen.pruefer`). Er urteilt je Teil über die Form, nicht über die Lage:
  - Merkmale im Foto aufzählen: Umriss, Bogenart, Anzahl und Anordnung der Wiederholungen, Profile, Öffnungen, Dachform.
  - Je Merkmal angeben: `stimmt`, `teilweise`, `falsch` oder `fehlt`.
  - Gesamturteil je Teil: `form` in {1,0; 0,5; 0}, dazu `sicher` und `fehler`, eine Liste kurzer Sätze.
  - Ausgabe als JSON. Ein Fehler oder fehlendes JSON ergibt `ungeprueft`; das Teil zählt dann nicht und wird gemeldet.
  - Bis zu 3 Aufrufe parallel. Mehrere kleine Teile dürfen in einen Aufruf gebündelt werden; der Prompt muss die Teile dann trennen.
- **Cache:** Schlüssel = md5(Teil-STL) + Prompt-Version + Fotowahl. Unveränderte Teile werden nicht neu bewertet.
- **Gesamtwert:** `form_prozent` = Mittel der `form`-Werte, gewichtet mit der sichtbaren Teilfläche in Pixeln (`sicht_px` aus der Formliste, Summe über die gewählten Fotos). Zusätzlich die Liste der Teile mit `form` < 1 und deren `fehler`.

## Fallen (Pflicht bei JEDEM Lauf)
- Mindestens 4 feste Fallen-Teile liegen unter `<cache_dir>/fallen/`, einmal erzeugt und dann unverändert:
  - Westgiebel als Sägezahn (`daechlein_h` 0,8, Altstand)
  - Tor rund statt spitz (a091923 r2 nachher)
  - ein Teil mit erfundenem Kasten
  - ein Teil mit falscher Anzahl an Wiederholungen, z. B. Gauben oder Fenster −1
- Sie werden genau wie echte Teile bewertet und bekommen neutrale Namen; der Prüfer weiß nicht, dass es Fallen sind.
- Bekommt eine Falle `form` ≥ 0,5, ist der ganze Lauf `ungueltig`, und `form_prozent` wird nicht ausgegeben.
- Fallen werden NIE gecacht; sie werden in jedem Lauf neu bewertet.

## Beweis: `tools/test_realitaet_form.py`
1. Die Fallen fallen alle durch.
2. **Bekannte Paare:** Das bessere Teil bekommt eine höhere Formnote.
   - a125135 vorher (Sägezahn) < nachher (Treppe)
   - a095328 vorher (glattes Gewölbe) < nachher (Rippen)
   - a091923 r2 vorher (spitz) > nachher (rund)
3. **Wiederholbarkeit:** zweimal ohne Cache auf dem aktuellen Modell. Die Abweichung je Teil darf in höchstens 10 % der Teile 0,5 betragen; das wird berichtet.
4. **Erster echter Lauf auf main:**
   - Tabelle Teil | form | sicher | fehler
   - Laufzeit gesamt und je Teil
   - Anzahl der Claude-Aufrufe

## Randbedingungen
- Nur neue Dateien. `formfund_pruefen.py`, `formfamilie_pruefen.py` und `foto_lokal.py` werden nur importiert, nicht geändert.
- GPU-Regeln aus CLAUDE.md. `gpu_slot` gilt nur für die Bilder. Prüferaufrufe laufen ohne GPU-Sperre.
- Kein Commit, nichts löschen, kein Objektname im Code. Arbeitsdaten unter `/media/oem/scan/rc-park_tmp/formnote/`.
- Mindestens 6 Zweierbilder selbst ansehen. Davon einzeln 2 der eigenen Urteile des Prüfers gegen das Foto prüfen.
- Den Einbau in `realitaet_prozent.py`/`realitaet_verlauf.jsonl` macht der Koordinator.

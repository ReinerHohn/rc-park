# Spec: Lokales Foto-Tor (Änderungsbereich) im Kreis

Nutzerentscheid 11.11., 12:45: „Lokal + ganzes Teil“.

**Anlass:** Das Foto-Tor misst den F1 des ganzen Teils. Kleine echte Details ändern ihn um weniger als +0,02 und werden deshalb immer verworfen, zum Beispiel:
- Balkon-Stirnen: 0,767 → 0,764, obwohl die Stirn in j05 klar zu sehen ist (a123234)
- Sockelhöhe
- Schlussstein
- Baldachin-Aufsatz

Lehren L46 und L47: Die Gesamtnote misst Kantendichte, nicht die Form im Detail.

## Regel
Eine Runde besteht das Foto-Tor nur, wenn **beide** Bedingungen erfüllt sind:
1. **Lokal:** Der F1 im **Änderungsbereich** steigt um mindestens `MIN_GEWINN_LOKAL`, Standard 0,05, auf den Torfotos (pixelgewichtet wie `_gesamt`).
2. **Ganz:** Der F1 des ganzen Teils fällt nicht um mehr als 0,005. Heute wird +0,02 verlangt; diese Forderung gilt weiter als ALTERNATIVE, nicht als Pflicht.

Das alte Tor (ganzes Teil mindestens +0,02) bleibt bestehen. Es genügt, wenn **eine** der beiden Bedingungen erfüllt ist:
- altes Tor ganz, oder
- lokal plus ganz nicht schlechter.

Kontrollfotos, Verschiebungskontrolle und Prüfer bleiben unverändert. Das gilt auch für die lokale Variante: Die Kontrollfotos messen ebenfalls lokal.

## Änderungsbereich je Foto
- Je Foto die Pixelmaske, in der sich das gerenderte Teil zwischen vorher und nachher unterscheidet:
  - Silhouette XOR, ODER
  - Tiefe weicht um mehr als 0,05 m ab, ODER
  - Normale weicht um mehr als 20 Grad ab.
- Die Maske wird um die Kantentoleranz erweitert (Schwelle 0,14 m in Pixeln).
- In dieser Maske werden Präzision, Recall und F1 gezählt, auf dieselbe Weise wie heute im Festbereich (`--bereich_von`, Verdeckung gegen das ganze Modell und die Wolke).
- Neue Option in `tools/teil_fotoform.py`, `--aenderung_von <teile_dir_vorher>`. Ausgabe je Foto `f1_lokal`, `praez_lokal`, `recall_lokal`, `px_lokal`; in `_gesamt` `f1_lokal`.
- Vorher und nachher werden in derselben Maske gemessen. Die Maske hängt von beiden Ständen ab, ist also für beide gleich.
- Ist der Änderungsbereich in einem Foto kleiner als 150 Kantenpixel, zählt dieses Foto lokal nicht. Gibt es lokal weniger als 3 Fotos, ist die lokale Bedingung nicht messbar, und dann gilt nur das alte Tor.

## Beweis (Pflicht, vor dem Einhängen)
Synthetischer Test `tools/test_lokales_fototor.py` am echten Modell:
1. **Erfundenes Detail muss scheitern:** z. B. ein Kasten 0,4 m an einer Stelle der Brüstung, an der im Foto nichts ist. Der lokale F1 muss FALLEN oder unter der Schwelle bleiben.
2. **Echtes Detail muss bestehen:** Ein vorhandenes, im Foto belegtes Kleinteil wird entfernt und wieder eingesetzt, z. B. Sockel oder Baldachin-Aufsatz eines aktuellen Teils. Lokal muss der Wert um mindestens 0,05 steigen.
3. **Verschobenes Detail muss schlechter abschneiden als das richtig liegende:** dasselbe Teil 0,3 m versetzt.

Zusätzlich die Regression mit `tools/regression.py ... --pruefen`. Das Ergebnis muss „identisch“ sein, denn ohne die neue Option ändert sich nichts.

## Einbau in `tools/bauteil_kreis.py`
- An den Stellen, an denen `ff_v` und `ff_n` für reguläre Teile und für eingebaute Fehlteile gemessen werden: zusätzlich `--aenderung_von` und die Lokalwerte loggen, als `FOTO-TOR LOKAL <teil>: f1_lokal v -> n (k Fotos), ganz v -> n`.
- Entscheidung nach der Regel oben.
- Das kreis.jsonl-Protokoll bekommt `foto_lokal_vor_nach`.

## Randbedingungen
- Kein Lockern bestehender Sollwerte. Neu ist nur ein zusätzlicher Weg mit eigener, strengerer Schwelle.
- GPU-Regeln aus CLAUDE.md. Regel 8b gilt: Regression nach jeder Werkzeugänderung.
- Datei-Reihenfolge: `teil_fotoform.py` wird gerade vom Tempo-Agenten umgebaut. Diese Spec wird ERST danach umgesetzt, auf seinem Stand.

# SPEC Störmaske für die Foto-Metrik (Nutzerfreigabe 11.11. 16:4x „Punkt 1 kannst du einbauen“)

## Warum
Die Hauptzahl Realität (Foto) = Mittel Foto-F1 je Teil (`tools/teil_fotoform.py`). Fotokanten von Dingen, die kein Gebäudemodell je hat, senken den Recall
dauerhaft: Menschen, Fahrzeuge, Schilder, Tische/Stühle/Schirme, Marktstände, Pflanzen/Kübel, Fahnen. Schwächste Teile 15:32: quader__rumpf_eg 0,499,
quader__laube_rueck 0,509 (beide stark von Menschen/Schildern/Tischen überdeckt). Die vorhandene Verdeckung (Modell + Fotowolke, Metrik v2)
erfasst nur Verdecker, die in der Wolke stehen; bewegte Menschen/Fahrzeuge fehlen dort.

## Was (Umfang eng)
1. `tools/foto_stoermaske.py <objekt> [--fotos a,b,..] [--alle]`: je kalibriertem Foto (gleiche Fotoliste/Bildquelle wie teil_fotoform) eine Maske
   „nicht Gebäude, kein Modellinhalt“, GPU. **Wiederverwenden** statt neu bauen: Klassenlogik und Modelle aus `tools/handy_masken_v2.py`
   (SegFormer-ADE20K + OWLv2, Lizenz schon eingetragen). Klassen: Personen, alle Fahrzeuge/Fahrräder, Schilder/Plakate (signboard, poster),
   Tische/Stühle/Schirme/Markise/Zelt/Stand, Pflanzen/Bäume/Kübel, Fahne. NICHT maskieren: Gebäudeteile, Lampen am Gebäude, Figuren/Statuen
   am Gebäude (sind Modellteile!), Himmel. Maske um ~ Schwelle (0,14 m im Bild, aus der Kamera) erweitern. Cache:
   `/media/oem/scan/rc-park_tmp/stoermaske/<objekt>/<foto>.png` + `bericht.json` (Klassen, Flächenanteil je Foto). Kein Objektname im Code.
2. `tools/teil_fotoform.py`: Option `--stoermaske an|aus` (Standard **aus**, auch `RCPARK_STOERMASKE`): Fotokantenpixel in der Maske zählen nicht
   (Recall), Modellkantenpixel in der Maske zählen nicht (Präzision; dort ist das Modell im Foto verdeckt). Sonst NICHTS ändern.
   Mit `aus` bitgleich zum Ist (Beweis: gleiche JSON-Werte auf 3 Teilen x 10 Fotos; `tools/regression.py modelle/kaufhaus_grob3/objekt.json --pruefen` identisch).
   Metrik-Etikett mit Maske: eigene Version (z. B. Suffix `_stoermaske`), Cache-Schlüssel getrennt.
3. `tools/realitaet_prozent.py`: NEBENZAHL `prozent_foto_maskiert` (gleiche Formliste, Maske an) zusätzlich ausgeben/protokollieren, Hauptzahl unverändert.

## Beweis (Pflicht, Regel Beweispflicht)
- Synthetisch: Testbild mit eingesetztem „Störer“ (Rechteck mit Kanten) über einer bekannten Modellkante: ohne Maske Recall sinkt, mit Maske gleich dem Bild ohne Störer.
- Echt: Masken für die 10 Torfotos von quader__rumpf_eg, quader__laube_rueck, satteldach__haupt, figurenreihe__figuren erzeugen und **ANSEHEN**
  (Overlay Maske halbtransparent auf Foto, je Foto ein JPG unter `/media/oem/scan/rc-park_tmp/stoermaske/<objekt>/blick/`).
  Fehlmaskierungen (Gebäude/Figur maskiert) zählen und nennen; Figuren am Gebäude dürfen NICHT maskiert sein (Falle).
- Tabelle Teil | F1 ohne | F1 mit Maske | maskierter Flächenanteil, plus Gesamtzahl prozent_foto alt/neu für die aktuelle main-Formliste.

## Nicht
Kein Kreis-/Tor-Code (bauteil_kreis.py, kreis_regler.py), keine Generatoränderung, keine Sollwerte, nichts löschen, Hauptzahl nicht umstellen
(Umstellung entscheidet der Nutzer nach dem Beweis). Lange Läufe über `tools/job_start.sh` mit `JOB_GPU_MB` (Budget vorher messen).

## Offen (nicht in diesem Auftrag)
Dachflächen: einzelne Schindeln fallen durch die Glättung (0,18 m) weg, aber **Moos-/Flechtenflecken** erzeugen Farbkanten auf ebener Fläche
(q11 satteldach: viele gelbe Kanten mitten auf dem Dach). Später: nur geometrische Fotokanten zählen (Normalen-/Tiefenkanten aus Monokular-Normalen
oder Dichtewolke) – eigener Spec.

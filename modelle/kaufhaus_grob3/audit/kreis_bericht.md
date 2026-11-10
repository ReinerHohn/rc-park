# Kreis1 Fehlteil fk_+16_+0_+26 (Lauf 20261110_033946a033946, r1) - Neuaufsetzen des verworfenen Patches a031245 r1

**Kurz:** Der Kasten ist kein fehlendes Bauteil. Der Ost-Staffelgiebel existiert, lag aber 1,3-1,4 m zu weit aussen (u 17,15 statt 15,85). Ich habe die Korrektur aus dem verworfenen Patch (`.../20261110_031245a031245/verworfen_r1.patch`) uebernommen (objekt.json, 5 Pruefungen, 5 Messorte, Messprotokolle M-6115-001..008, K-6115, K-6257, Logbuch) und neu gebaut. `tools/bauen_abnehmen.sh kaufhaus_grob3`: **alle Pruefungen bestanden**. Keine neue Messung in diesem Lauf (ehrlich: die Triangulation stammt aus dem Vorlauf).

## 1. Formbeschreibung
Fotos 6115 (Ost, Nah), 6257 (West), 6145 (Gegenprobe), Details siehe `modelle/LOGBUCH_GIEBEL_OST_KREIS1_2026-11-10.md`. Formfamilie vorhanden: `staffelgiebel:ost` (8 Stufen, Teilung 1,0 m in n, Stufenoberkante flach in Kappenfirsthoehe). Dach `satteldach:haupt` endet nun an der Giebelwand (u1 15,75).
## 2. Zaehlungen
8 Stufen: bestehend Z-075-004; in diesem Lauf nicht neu gezaehlt (Spitzen M-6115-001..008 liefern 8 Stufen).
## 3. Pruefungen (alle am Altstand rot laut Vorlauf, hier NICHT erneut am Altstand gebaut)
| Pruefung | Modell | Soll | Quelle |
|---|---|---|---|
| Ostgiebel Aussenebene u | 15,85 | 15,55-15,95 | M-6115-001..008 |
| Stufe 2 z | 27,42 | 27,17-27,77 | M-6115-002 |
| Stufe 4 z | 24,74 | 24,51-25,11 | M-6115-004 |
| Stufe 8 z | 19,38 | 19,07-19,67 | M-6115-008 |
| Vorderende n | 11,00 | 10,85-11,2 | M-6115-008 |
## 4. Overlays (Vorher/Nachher, selbst angesehen: Nachher liegen die Modellstufen auf den Fotostufen)
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_giebel_ost_6115.jpg (angesehen)
- .../rundekreis1_giebel_ost_6145.jpg, .../rundekreis1_giebel_ost_6257.jpg (aus Vorlauf, nur 6115 hier angesehen)
## 5. Fehlerliste
- trifft: Stufenlage/-hoehe Ostgiebel (6115 gesehen); Dach-Ostende.
- trifft nicht / offen: Rumpf OG/EG und Gesims Ost enden noch bei u 17,15 (Gitter z 8-15 u 17,0-17,5, ungeprueft, Beobachtung offen); Ziegel-Kaeppchen je Stufe nicht modelliert; Rueckflanke Spiegel-ANNAHME; im Overlay 6115 liegen unten links Modellkanten (Rumpf) noch neben der Fotokante.
- ungeprueft: Gate-Zahlen in diesem Lauf nicht neu gerechnet (Tor macht bauteil_kreis). Vorlauf: Recall im Kasten 0,100->0,361 (+0,261, Soll >=0,25), Gesamt-Recall 0,648->0,651, kein Bauteil > -0,02 Guete; **Kanten-Praezision des Giebels 0,025 < 0,25 (Gate verfehlt, Kantengitter dort nur 39 Segmente)**. Das war vermutlich der Grund fuer "Vortor rot" - eine Gitter-Duenne, kein Fotobefund.
- `teile_lage_pruefen.py` crasht weiterhin (KeyError 'world'), Wolke reicht nur bis z 21; nicht ausgefuehrt.
## 6. Geaenderte Dateien
objekt.json, masstabelle.json (5 Messorte, 5 Pruefungen, 2 Beobachtungen), messprotokoll/M-6115-00x, K-6115/6257, LOGBUCH_GIEBEL_OST_KREIS1_2026-11-10.md, Erzeugnisse (STL, MASSNACHWEIS, audit/*).
## 7. Generalisierte Lehre
Lehre | Anlass | Werkzeug: Ein "Fehlteil"-Kasten kann ein vorhandenes, falsch gelegtes Teil sein (Spiegel-ANNAHME) -> erst Triangulation der Teilspitzen aus 2 Fotos, dann Bauen | fk_+16_+0_+26 | foto_mass --tri. Eintraege stehen schon im Rezept (L-KR8..12) und NICHTS_GEBRACHT.


---
# Kreis Runde 2 (a033946 r2) - Nachtrag
**Kurzfassung:** Kein fehlendes Bauteil. Wie in r1 (und Vorlauf a031245 r1) lag der Ost-Staffelgiebel 1,3-1,4 m zu weit aussen. r2 uebernimmt den r1-Zweig (Triangulation M-6115-001..008) und prueft zwei Varianten gegen das Tor.

**Gemessen (konvergenz_bericht, gleiche Argumente wie Kreis-Tor):**
| Variante | Region-Recall (Soll +0,25 ueber 0,1026) | Gesamt-Recall (main 0,648) | Praez. 10-15 m (main 0,372) | Gesamt-Praez. (main 0,077) |
|---|---|---|---|---|
| main (Giebel u 17,15) | 0,1026 | 0,648 | 0,372 | 0,077 |
| Giebel 15,85 + Dach 15,85 (ABGENOMMEN in dieser Runde) | 0,3585 | 0,651 | 0,361 | 0,080 |
| Giebel 15,75 + Dach 15,75 (r1) | 0,350 / 0,361 | 0,650-0,651 | 0,361 | 0,080 |
| zusaetzlich Rumpf EG/OG/Gesims u1 15,85 (VERWORFEN) | 0,3609 | 0,644 (-0,004) | 0,368 | 0,080; Recall 0-5 m 0,631->0,614 |

- Rumpf EG/OG/Gesims-Verschiebung nach 15,85 ist falsch: die Ostwand bei u 17,15 traegt belegte Gitterkanten (z 8-15, u 17,0-17,5); Gesamt-Recall sinkt unter die Toleranz. Nicht uebernommen, Befund bleibt als offene Beobachtung.
- Dach-Ende 15,75 vs 15,85: kein Unterschied in Praezision; 15,85 = Giebel-Aussenebene (konsistent), `werte_quellen`/`historie` angepasst.
- **Gate NICHT erfuellt:** Praezision im Band 10-15 m faellt 0,372 -> 0,361 (Rausch 0,010, Tor rc 3); Kanten-Praezision Giebel 0,025 (Soll 0,25; Gitter hat dort nur ~39 Segmente, Gitterarmut, keine erfundene Form - Overlay 6115 zeigt die Stufen auf den Fotostufen). Gesamt-Praezision steigt 0,077 -> 0,080. Sollwerte nicht gelockert.
- `tools/bauen_abnehmen.sh kaufhaus_grob3`: alle Pruefungen bestanden (die 5 Giebel-Pruefungen aus r1 gruen; am alten Stand rot lt. r1-Protokoll).
- Overlay selbst angesehen: `audit/gitter_generator/rundekreis1_giebel_ost_6115.jpg` (Nachher trifft; unten links liegen die Rumpf-Ostkanten weiter neben der Fotokante = offen). 6145, 6257 nicht erneut angesehen.
- `teile_lage_pruefen.py` stuerzt weiter ab (KeyError 'world'), ungeprueft.

**Overlays:** modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_giebel_ost_{6115,6145,6257}.jpg
**Geaenderte Dateien (gegenueber main):** wie r1-Zweig, dazu objekt.json (Dach u1 15,85 statt 15,75).

**Generalisierte Lehre:** Ein Bauteil, das nach Messung KUERZER wird, kann die Band-Praezision senken, obwohl die Gesamt-Praezision steigt; Rumpfenden nie mit dem Giebel mitverschieben ohne Gitter-Gegenprobe (Ostwand traegt Kanten) | Anlass: fk_+16_+0_+26, Variante Rumpf 15,85 | Werkzeug: konvergenz_bericht --regionen vor jeder Mehrteil-Verschiebung.

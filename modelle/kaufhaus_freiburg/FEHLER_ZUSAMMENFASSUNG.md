# Fehler-Zusammenfassung Kaufhaus Freiburg — was schiefging, Lehre, Checker-Konsequenz

Ziel: aus ALLEN Fehlern dieser Sessions lernen und jeden Fehlertyp AUTOMATISCH abfangbar machen,
damit die nächste Loop die Fehler selbst findet statt der User.

## A) Fenster — 11 Korrektur-Runden (der teuerste Block)
| # | Fehler | Ursache | Checker, der es jetzt fängt |
|---|--------|---------|------------------------------|
| 1 | zu gedrungen (B/H 0,97) | Aspekt aus fragiler Segmentierung | proportion_check Fensterhöhe + fenster_check (Projektion) |
| 2 | zu schmal | Breite aus Glas-Anteil statt voller Einheit | fenster_check (Einheit/Bay) |
| 3 | Kämpfer gerade statt gestuft | Detail übersehen | fenster_detail_check (Band Mitte) |
| 4 | Pfosten „stehen über" | zu hoch | fenster_detail_check (Band oben) |
| 5 | nicht konkav genug | Messung zu flach | fenster_detail_check (Bogenkopf) |
| 6 | **degeneriert/kollabiert** | **freier Multiplikator auf Messung** | **Gültigkeits-GUARD + degeneracy-check** |
| 7 | Pfosten zu kurz | über-korrigiert (Gegenteil) | fenster_detail_check (Band oben) |
| 8 | Kopf spitz statt flach | falsche Parametrik | fenster_detail_check + Spec |
| 9 | flach statt leicht durchhängend | übersehen | fenster_detail_check (Bogenkopf-Form) |
| 10 | Durchhang übertrieben | über-korrigiert | — (Augenmaß, dip-Parameter klein) |
| 11 | Saddle-Bars fehlten | Detail übersehen | fenster_detail_check (horiz. Kanten) |

## B) Massing (erst spät amtlich geholt)
- **Dach zu kurz** (First 15,4 statt 21,4): Foto-Messung unterschätzte das STEILE, im Frontfoto
  VERKÜRZTE Dach. → **massing_check gegen LOD2** (Traufe/First/Grundriss).
- **Fassade zu schmal** (18,5 statt 24,1): aus Foto-Verhältnis geraten. → massing_check gegen LOD2.
- **Koordinate traf den Nachbarn** (Wentzingerhaus): blind der lat/lon vertraut. → Gebäude per
  `<gml:name>` + Umriss/Google gegenprüfen.

## C) Folge-Fehler nach Massing-Änderung
- Erker-Helm zu kurz (für altes niedriges Dach gedeckelt) → Helm zielt jetzt auf % der Dachhöhe.
- Gauben zu hoch/klein verteilt (altes Dach) → tief an die Traufe.
- Gauben-Abstände ungleich → gauben_check (Abstands-CV).
→ Lehre: nach Massing-Änderung ALLE davon abhängigen Teile neu prüfen (die Checker-Suite komplett).

## D) Sonstiges
- Arkade „Bögen zu schmal": am falschen Knopf gedreht (ARC_BW=Ring, nicht Öffnung) → erst prüfen ob
  Parameter die Zielgröße bewegt (identischer Score = falscher Knopf).
- Balkon über die ganze Breite statt nur vor den Fenstern.
- Baldachine dünne Spitzen statt solide.

## META — die 7 Grundursachen
1. **Stückweises Reagieren** statt EINER vollständigen Foto-Spec vorab (→ Spec-Pflicht je Bauteil).
2. **Metriken über Hinsehen** vertraut (Gate 0,89 bei Degeneration) (→ Detail GROSS ansehen + feiner Check).
3. **Freie Multiplikatoren** auf gemessene Geometrie (→ parametrisch-gültig + Guard).
4. **Über-korrigiert** ins Gegenteil (→ auf gemessenen Zielwert, nicht übers Ziel).
5. **Checker zu grob** fürs interne Detail (→ fenster_detail_check / degeneracy-check).
6. **Daten spät/ungeprüft** (Massing, Koordinate) (→ amtliche Daten ZUERST, per Name wählen).
7. **Perspektive verwechselt** (Frontfoto verkürzt Dach) (→ Vergleich IMMER im gleichen Blickwinkel).

## Checker-Suite danach (tools/)
- `kaufhaus_check_alle.py` — EIN Lauf: Massing-vs-LOD2 + Degeneracy + proportion + fenster + gauben +
  fenster_detail → konsolidierter PASS/WARN-Report mit Prioritätenliste (= Ratsche für die nächste Loop).

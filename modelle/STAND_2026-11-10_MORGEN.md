# Stand 10.11.2026 morgens – Kaufhaus, Nachtlauf Konvergenz-Kreis

## Zahlen der Nacht (Spuren automatisch per `kreis_regler`, bis 6 parallel)
- 98 Kreis-Runden, davon 62 mit dem Gütetor (Teilgüte = Mittel aus sichtbarem Wolkenbeleg und Fotokanten-F1).
- Gütetor-Runden: 11 angenommen, 42 ohne ausreichenden Gewinn bzw. mit Rückschritt, 7 vom Prüfer abgelehnt, 2 mit roter Abnahme.
- Nach main: 16 Merges, 4 Reverts. Main war nach jedem Merge grün (seit ad04bf5 prüft der Kreis das selbst).
- Fotokanten-Recall gesamt: 0,642 (01:00) → 0,666 (06:31). Präzision gesamt: 0,078 → 0,089.
  Die Präzision bleibt niedrig, weil das Kantengitter an vielen Modellkanten leer ist.

## In main angenommen (Güte des Teils vorher → nachher)
| Teil | Güte | Offen (Prüfer) |
|---|---|---|
| figurenreihe:figuren | Beleg 0,435 → 0,852 | Baldachine, Attribute fehlen; Körper als Drehkörper |
| gaubenreihe:oben (2×) | 0,479 → 0,589 → 0,651 | Dachrückseite aus 1 Messpunkt; A/B-Höhenunterschied; Fensterbank 0,1–0,2 m zu hoch |
| helm_geschweift:o (2×) | 0,373 → 0,431 → 0,497 | Traufschnäbel; Fußring gegen Wolke strittig; Grate/Krabben/Fahne fehlen |
| helm_geschweift:w (2×) | 0,390 → 0,461 → 0,588 | Schaft z 15,4–19,4 noch zu schlank; Krabben/Fahne fehlen |
| staffelgiebel:ost (Fehlteil + 1×) | Recall im Kasten 0,10 → 0,36; Güte 0,135 → 0,208 | Ostwand/Gesims 1,3 m zu lang (Absatz); Käppchen und Giebelfenster fehlen |
| quader:gesims (2×) | 0,434 → 0,536 → 0,602 | Enden an den Helmen angenommen; Unterkante strittig (Foto 14,33 vs. Gitter 14,40) |
| bogenreihe:laube | 0,444 → 0,580 | Archivoltstufe 0,22 m nur aus Gitter (evtl. aufgemalt) |

Zurückgenommen: Laube-Rückwand (alte Kennzahl, verdeckte Flächen) und Helm Ost a024143 (Traufe 1 m zu tief).

## Neu in der Pipeline (alle Tests/Regression identisch)
- Zielart **Fehlteil**: Fotokanten ohne Modellfläche werden zum Agentenziel. Agenten-Pflichtzeile `FEHLTEIL-BEFUND`. Sperrliste `rc-park_kreis/kaufhaus_grob3/fehlteil_erledigt.json`. Schwache bzw. abweichende Säulen-Fits sind ausgenommen (L-KR7, L-KR8, L-KR13).
- **Sichtprüfung mit Verdeckung** über exakte Embree-Strahlen. Proben: Innenwürfel 0 %, Vorderwürfel 83 %. Messart-Kennung `sicht` (L-KR17).
- **Merge**:
  - Erzeugnis-Konflikte werden per Neubau gelöst.
  - Lokale Erzeugnisse werden gesichert.
  - Nach jedem Merge läuft die Abnahme auf main; ist sie rot, folgt ein automatischer Revert.
  - `tools/main_abnahme.sh` hält den Merge-Lock.
- Vorversuche nennen den Zweig und markieren angenommene Runden, die main nicht hat.
- **`teile_lage_pruefen`**: richtige Wolke (lot2), kein Absturz mehr. Die alte Voreinstellung war ein falscher Rahmen, sie meldete Helm O mit 2,54 m statt 0,14 m.
- **Prüfstand**: ungültige Beobachtungen ergeben eine klare FEHLER-Zeile statt eines Tracebacks.
- **Git-Objekte** liegen per alternates auf der Datenplatte (`tools/git_packs_auslagern.sh`). Root 7,6 → 13 GB.

## Offen / nächste Hebel
1. **Kantengitter verdichten**: Ostgiebel-Stufenecken, Helm z 16–21 (Gitter 0,1–0,2 m außerhalb Foto/Wolke, L-KR15). Sonst belohnt der Kanten-F1 falsche Formen bzw. bremst richtige.
2. **Ostwand/Gesims** auf den Giebel kürzen (Beobachtung in der Masstabelle).
3. **Westgiebel** etwa 0,75 m Höhenfehler und vermutlich gegen die Achse gedreht (Fehlteil-Befund fk_-6_+6_+28).
4. **Tor kann Teil-Entfernungen nicht bewerten**: Laube-Doppelteil, Gewinn −0,286 nur rechnerisch. Entfernungen über Gesamt-Recall/-Präzision bewerten.
5. **Audit-Bilder und STLs in Git** wachsen ca. 1 GB/h. Nutzerentscheid nötig: nicht mehr versionieren oder regelmäßig auslagern.
6. `/tmp/iph` (1,4 GB) liegt wieder auf Root (Nutzerdaten, nicht angefasst).
7. Foto 6124: Das Modell bedeckt nur 2,5 % des Bildes; Kamera prüfen.

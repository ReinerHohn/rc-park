# Kreis2 164909 r2 – satteldach:haupt, Wasserspeier an der Traufe

1. **Formbeschreibung (Stufe 0)** – Fotos 6162 (frontal, Übersicht), 6132 und 6145 (schräg, Nahausschnitt), n11_04 (Nutzerfoto, Nahaufnahme von unten), j05 (Kontrolle). Zone Traufe/Rinne: zwei lange, patinierte Rohr-Speier mit Drachenkopf (Maul offen) ragen etwa 2 m aus der Haupttraufe unter der Rinne, ~0,5 m nach unten geneigt. Sie sitzen über den Konsolen-Schmiedearmen der Figuren. Die kleinen Erker-Eckdrachen (Teil a) gehören zu `erker_polygon`/`helm` und sind NICHT gebaut. Formfamilie: `satteldach.speier` (geneigter Kragarm als Hülle Fuß→Ende plus Kopfblock) in `tools/baukasten_gen.py`, aus dem Vorversuch 161725 übernommen und um `z_ende` (Neigung) erweitert.
2. **Zählung**: 2 Traufspeier am Hauptdach, Z-6162-001. Sichtkontrolle in 6145 (beide), 6132 (links), j05 (rechts), n11_04 (beide).
3. **Prüfungen**:

| Prüfung | vorher (ohne Speier) | nachher | Soll | Quelle |
|---|---|---|---|---|
| Traufspeier A (links, u 11,36), Reichweite ab n 10 bei z 13,95 | 2,68 rot | 4,68 | 4,3–5,0 | M-6162-001..004 |
| Traufspeier B (rechts, u −4,47) | 2,66 rot | 4,61 | 4,3–5,0 | M-6162-005/006 |

   Messungen (foto_mass --tri): links Fuß u 11,36 n 12,68 z 14,3 (zwei Paare 6162+6132 und 6162+6145, Strahlabstand ≤0,05 m); Kopf u 11,5–11,6 n 14,7 z 13,8; rechts Fuß u −4,47 n 12,55 z 14,5, Kopf u −4,40 n 14,55 z 13,86 (±0,07–0,1 m). Querschnitt 0,22 m und Kopfblock 0,5×0,4 m = ANNAHME. Foto-F1 `satteldach__haupt` (10 Torfotos, halbe Auflösung): 0,795 (Vorrunde) → 0,797, kein Fall. `bauen_abnehmen.sh`: „alle Pruefungen bestanden“.
4. **Overlays**: `modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_speier_neu.jpg` (Modell-Speier grün in 6162, j05, q11, 6132, 6145; selbst angesehen). Es zeichnet die Generatorparameter, nicht die STL-Kanten.
5. **Fehlerliste**: trifft – linker Speier (6162, 6132, 6145), rechter Speier (6162, 6145, j05 unabhängig). Trifft nicht/ungeprüft – q11 (unscharf, Kamera schwach): Modell dort nicht passend, nicht als Beleg gewertet; Kopf nur Block statt Drache; Querschnitt ANNAHME; Erker-Eckspeier fehlen; `foto_diff`, `fehlteile_finden`, `regression.py`, `teile_sichtpruefung` NICHT gelaufen. `teile_lage_pruefen`: satteldach:haupt Median 2,38 m (Warnung bestand schon vorher, betrifft Dachfläche, nicht die Speier). `freiraum_audit` schlug schon im Altlauf fehl.
6. **Geänderte Dateien**: `tools/baukasten_gen.py`, `modelle/kaufhaus_grob3/objekt.json`, `masstabelle.json` (Messungen, 2 Prüfungen, `teilstand`; `erledigt` NICHT gesetzt, da (a) offen), `messprotokoll/Z-6162-001.*`, `M-6162-001..006.*`, `NICHTS_GEBRACHT.md`, `REZEPT_GEBAEUDE_AUS_FOTOS.md`, Bauartefakte unter `audit/`.
7. **Generalisierte Lehre**: L-KR33: Kleinteile abseits bekannter Ebenen nur per Zwei-Paar-Triangulation setzen, nicht per Strahl auf Ebene | Vorversuch 161725 lag 0,9 m daneben | `foto_mass.py --tri`, `schnitt_reichweite`.

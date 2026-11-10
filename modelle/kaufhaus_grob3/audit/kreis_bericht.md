# Kreis r4 helm_geschweift:w (kaufhaus_grob3, 2026-11-10)
Nichts committet, gelöscht oder gedruckt. Logbuch: `modelle/LOGBUCH_HELM_W_R4_2026-11-10.md`.

## 1. Formbeschreibung
Fotos angesehen: 6162 (Übersicht), g03 und i04 (Handy-Nahfotos von unten), 6261 (nur Overlay erzeugt, nicht einzeln beurteilt). 6257 stammt aus dem Vorlauf.
- Fuß z 13,3–15,4: konkave Ziegelhaut, im Vorlauf erledigt.
- Schaft z 15,4–21: schlanker Achtkant mit bunten Ziegelstreifen. Auf den Graten sitzen Krabben (Haken), die im Modell fehlen.
- Nadel und Kugel bei z 21,35.
- Grundriss Achteck (g03/i04: 3 volle + 2 Randflächen sichtbar). Nicht gezählt, ANNAHME Osthelm.
- Anschluss: Erkergesims z 13,1–13,3.
- Am Modell anders: Schaft 0,04–0,06 m zu schlank (Osthelm-Kopie).
Formfamilie: bestehende `helm_geschweift`, nur das Profil ist geändert.

## 2. Zählungen
Keine (kein Z-Protokoll). Die Flächenzahl 8 bleibt ANNAHME: Einzelansicht zählt kein N, g03/i04 sind nur konsistent damit.

## 3. Prüfungen
| Prüfung | vorher (Altstand) | nachher | Soll | Quelle |
|---|---|---|---|---|
| helm_w_r_16_97 | 0,44 rot | 0,50 | 0,47–0,53 | Wolke-Mitte W-helm_w-profil, M-sil-helm_w-1 |
| helm_w_r_17_76 | 0,34 rot | 0,41 | 0,38–0,44 | dito |
| helm_w_r_18_58 | 0,27 rot | 0,34 | 0,30–0,36 | dito |

`bauen_abnehmen.sh kaufhaus_grob3`: alle Prüfungen bestanden. `freiraum_audit` und die fehlende Datei `SFM-AUSRICHTUNG-buendel.json` bleiben vorbestehende Fehler.

Kennzahlen Helm W (konvergenz_bericht, Trockenlauf, Teile neu exportiert):

| | vorher | nachher |
|---|---|---|
| Beleg | 0,561 | 0,562 |
| Median-Abstand | 0,110 m | 0,094 m |
| Kanten-Recall | 0,417 | 0,721 |
| Kanten-Präzision | 0,312 | 0,533 |
| Mittel aus Beleg und F1 | 0,459 | 0,588 |

Gate: +0,129 bei geforderten +0,05, keine Größe fällt. Das habe ich aus den Zahlen selbst gerechnet.
Der Kantensprung ist größer als die Profiländerung. Wegen L-KR15 (Gitter v12 liegt bei z 16–21 evtl. 0,1–0,2 m außen) schreibe ich ihn nicht allein dem Modell zu. Der Beleg ändert sich praktisch nicht.

## 4. Overlays (rot = neu, cyan = alt)
- audit/gitter_generator/rundekreis4_helm_geschweift_w_6162.jpg
- audit/gitter_generator/rundekreis4_helm_geschweift_w_6257.jpg (erzeugt, nicht einzeln beurteilt)
- audit/gitter_generator/rundekreis4_helm_geschweift_w_6261.jpg (erzeugt, nicht einzeln beurteilt)
- audit/gitter_generator/rundekreis4_helm_geschweift_w_g03_i04.jpg
- Aus dem Vorlauf: rundekreis1_helm_geschweift_w_*
- 6259: Overlay-Absturz (Ausschnitt leer). Eintrag in NICHTS_GEBRACHT.

## 5. Fehlerliste
- **Schaft rechte Kante, z 15,4–19,4:** trifft (6162, i04, g03 angesehen).
- **Schaft linke Kante:** trifft in 6162 und g03 besser als vorher. In i04 bleibt sie ca. 60 px innen (Achsversatz ~0,05 m möglich, ungeprüft).
- **Krabben:** trifft nicht (fehlen).
- **Achteck-Flächenzahl:** ungeprüft (ANNAHME).
- **Fuß z 13,3–15,4:** aus dem Vorlauf, hier nur im Overlay angesehen, trifft.
- **Knauf und Nadel:** ungeprüft. Die Silhouette bei z 20,5–21 sagt, das Foto ist 0,2 m schmaler als der Modell-Ring, nicht geändert.
- **Rückseite:** ungeprüft (Spiegelung).
- **Staffelgiebel-Quader:** steht bei z 16,5–18,3 mit Kante 0,51 m vor der Helmachse, also 0,17 m vor der Helmfläche. Lage ungeprüft.
- **teile_lage_pruefen:** Helm W Median 0,23 m, keine Markierung (> 0,4 m).
- **Nicht gelaufen:** `foto_diff`, `teile_sichtpruefung`. `fehlteile_finden` lief nur im Rahmen von `bauen_abnehmen`.

## 6. Geänderte Dateien
- modelle/kaufhaus_grob3/objekt.json (Profil W)
- modelle/kaufhaus_grob3/masstabelle.json (3 Messungen, 3 Prüfungen, 1 Beobachtung)
- modelle/kaufhaus_grob3/messprotokoll/M-sil-helm_w-1.json (neu)
- modelle/NICHTS_GEBRACHT.md, modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md, modelle/LOGBUCH_HELM_W_R4_2026-11-10.md
- Neu gebaute STL, Audit-Dateien, pruefbericht.json, MASSNACHWEIS.md (automatisch)

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| L-KR16: Ein konstanter Schnittwert bei zwei Höhen (0,507) zeigt, dass ein Nachbarteil gemessen wird. Messrichtung über die Polygonsymmetrie auf eine freie Seite drehen, am Altstand den Wert prüfen. | Staffelgiebel-Quader im +n-Streifen des Helms | pruefstand.schnitt_reichweite, helm_profil_wolke.py, helm_silhouette_foto.py |

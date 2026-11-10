# Kreis-Bericht r1: helm_geschweift:o (kaufhaus_grob3, 2026-11-10)

## 1. Formbeschreibung (Stufe 0)
Volltext: `modelle/LOGBUCH_HELM_O_R1_2026-11-10.md`. Fotos angesehen: nu3b (Nahfoto 17 m), nuaca (21 m), 6132 (22 m), 6161 (29 m, Uebersicht), 6145, p15 (verwackelt).
Zonen: Fuss/Trauf (Ziegelhaut laeuft stetig konkav bis auf das Erkergesims ~13,2-13,3, waagerechte Traufkante) / Schweifung z 13,3-16 / Schaft mit Graten / Kupfernadel mit Kugel.
Grundriss: Achteck, eine Flaeche zur Strasse (3 Grate von vorn sichtbar; Rueckseite ANNAHME). Formfamilie: bestehende `helm_geschweift`, nur das Profil unten war falsch.
Ursache: Altprofil hatte senkrechten Kranz (z 13,1-14,15, r 1,45) und Traufring r 1,54 bei z 14,15, ~1 m zu hoch. M-nu3b-001 war Silhouettenparallaxe (+0,8 m); das "Traufe 0,7 m tiefer" aus 6261 war richtig.

## 2. Zaehlungen
Z-nu3b-001: 3 Grate in Zeile 1000 = 2 volle Flaechen. N=8 ist nicht direkt zaehlbar (Rueckseite) und bleibt ANNAHME; Gegenprobe nur ueber Overlay und Wolke-Phasenfit (Achteck besser als Kreis, Phase -0,2..-1,6 Grad).

## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| helm_o_r_13_45 | 1,46 | 1,64 | 1,50-1,78 | Wolke Flaechenmitte, W-helm_o-profil.json |
| helm_o_r_14_12 | 1,46 | 1,27 | 1,15-1,35 | dto. |
| helm_o_r_14_38 | 1,39 | 1,17 | 1,05-1,25 | dto. |
| helm_o_r_14_88 | 1,10 | 1,00 | 0,87-1,07 | dto. |
| bestehende helm_o_r_14_64/16_18/17_76 | OK | OK (1,11/0,59/0,35) | unveraendert | M-nu3b-002/004/006 |
| Wolkenbeleg Helm O | 0,486, Median 0,159 | 0,607, Median 0,088 | (kein Gate) | konvergenz_bericht |
Alle 4 neuen Zeilen waren am Altstand ROT. `bauen_abnehmen.sh`: alle Pruefungen bestanden, 1 Widerspruch offen (Gesamthoehe, vorbestehend); test_regeln_cb bestanden. Kanten-Recall/Praezision je Band unveraendert (+0,006 bei 15-20 m).

## 4. Overlays (links Foto, rechts Overlay; rot = vorher, gruen = nachher)
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_helm_geschweift_o_{nu3b,nuaca,6132,6161,6145,p15}.jpg
Weitere: audit/foto_diff_nu3b.jpg, foto_diff_nuaca.jpg (kein FALSCH-Treffer am Helm), audit/seiten.jpg (Sichtblatt angesehen, Helme mit Schweifung ohne Stufe).

## 5. Fehlerliste
- Zone Fuss/Trauf: trifft (Traufkante liegt auf dem Gesims in nu3b/nuaca/6132/6161, ~1 m tiefer als vorher); Eckenschweifung (Traufspitzen der Grate evtl. weiter aussen als regelmaessiges Achteck): UNGEPRUEFT/offen (Beobachtung).
- Zone Schweifung z 13,3-16: trifft (Wolke +-0,05, Hip-Linien in 3 Fotos auf den echten Graten).
- Schaft z 16-21: trifft am Foto, Wolke zeigt 0,04-0,07 m dicker (Foto gewinnt, nicht gemittelt).
- Nadel/Kugel: unveraendert, in den Overlays trifft.
- Rueckseite/N=8: ungeprueft (ANNAHME).
- Restbeleg 0,607: verdeckte Unterseite des Fuss-Wulstes (z 13,1) hat keine Wolke (L-KR4).

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (helm_geschweift:o), masstabelle.json (4 Pruefungen, 1 Beobachtung), neu tools/helm_profil_wolke.py, messprotokoll/W-helm_o-profil.json, Z-nu3b-001.{json,jpg}, LOGBUCH_HELM_O_R1_2026-11-10.md, REZEPT (L31-L33), NICHTS_GEBRACHT, Overlays, vom Bau neu erzeugt: modelle/stl/*, pruefbericht.json, MASSNACHWEIS.md, elemente.json, audit/*. Nicht committet.
Helm West (Beleg 0,45) hat denselben Fehler und wurde bewusst nicht angefasst. `tools/teile_lage_pruefen.py` stuerzt bei fensterreihe:og ab (Werkzeugfehler, nicht behoben).

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| L31 Silhouettenmessung gilt nur fuer Punkte in der Messebene; Auskragungen werden um Tiefenversatz*tan(Blickhoehe) falsch in z gelesen | Traufe 0,8 m zu hoch | helm_profil_wolke.py |
| L32 ANNAHME-Bauteil, das eine Fehlmessung ueberbrueckt, versteckt den Fehler; Pruefzeilen ueber die ganze Teilhoehe | Zone 13,1-14,6 ungeprueft | masstabelle helm_o_r_* |
| L33 Silhouettenspitzen sind keine Punkte (Triangulation Scheinpunkte) | Traufspitzen nu3b+6132 | NICHTS_GEBRACHT |

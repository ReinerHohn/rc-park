# Kreis-Bericht r3 – gaubenreihe:oben (kaufhaus_grob3), Lauf 20261110_024143a024143

**Kern:** Die in Runde R2 (Lauf a021332, Commit fa26647) angenommene und abgenommene Neubelegung der oberen Gaubenreihe war nie in main
gelandet (Merge-Konflikt nur in Bau-Erzeugnissen). Diese Runde hat die QUELLEN (objekt.json, masstabelle.json, tools/baukasten_gen.py,
Messprotokolle K-*/M-6259-001..013, Logbuch, Lehren) per Cherry-Pick uebernommen, Bau-Erzeugnisse per Neubau auf main erzeugt und neu nachgemessen.
Keine neue Messung, kein neuer Generatoreingriff in dieser Runde (ehrlich: die Fachergebnisse sind die aus R2, hier selbst nachgeprueft).

## 1. Formbeschreibung (aus R2-Logbuch `modelle/LOGBUCH_GAUBEN_OBEN_R2_2026-11-10.md`, Fotos 6259, c12, 6162, j05 selbst im Overlay angesehen)
Schleppgauben: Holz-Fensterkasten 1,02 m breit, 0,83 m hoch mit Rundbogenfenster und Fensterbank; darueber ziegelgedecktes Vordach
(1,45 m breit, 0,22 m vor der Stirn, dreieckige Wangen ca. 1,5 m zurueck in den Hang). Formfamilie `schlepp` (baukasten_gen.py) mit
generischen Vordach-Parametern. Alte Fehlform: Stirn 1,66 m hoch, Pultdach 2,5 m, kein Vordach.

## 2. Zaehlungen
2 Gauben, Z-018-006 (Foto 018). Die Notiz "Giebelgauben" ist durch 6162/6259 widerlegt.

## 3. Pruefungen
Vorher (alter Stand, R2): 8 neue Pruefungen rot (Vordach-Vorderkante, Halbbreite beidseitig, Dachhoehe, je Gaube); nachher alle gruen,
Sollwerte nicht gelockert. Quellen: M-6259-001..013 (K-c12, K-6259, K-6162, +-0,13 m).
Diese Runde: `tools/bauen_abnehmen.sh kaufhaus_grob3` -> "alle Pruefungen bestanden" (1 Widerspruch offen, 45 Beobachtungen ohne Pruefung);
`regression.py --pruefen` -> identisch. Wolkenbeleg gaubenreihe:oben 0,48 -> 0,592 (Median-Abstand 0,124 m).

## 4. Overlays (selbst angesehen)
- modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis2_gaubenreihe_oben_alt.jpg / _neu.jpg / _alt_nah.jpg / _neu_nah.jpg
  (Fotos 6259, c12, 6162, j05; Vorher/Nachher). Nachher: Kasten, Vordach, Wange sitzen auf den Fotokanten.

## 5. Fehlerliste
- trifft: Fensterkasten-Breite/Hoehe, Vordach-Vorderkante und -Breite, Wange (6259, c12, 6162).
- trifft nicht / offen: Vordachrueckseite (Ziegelflaeche) in c12 ca. 0,4 m hoeher als Modell (dach_tiefe aus 1 Punkt +-0,25 m, Widerspruch 6259 offen);
  Stirn in c12 ca. 0,1 m zu breit; Gaube A/B real 0,14 m Hoehenunterschied, Modell gleich.
- nicht modelliert: Rundbogenfenster, Konsolen unter dem Vordach, Fensterbankprofil. ANNAHME: vordach_dicke 0,14 m, vor.
- ungeprueft: Gaube A nur trianguliert, nicht einzeln im Overlay. Lagecheck teile_lage_pruefen markiert die Gauben nicht.
- Wolkenbeleg bleibt <1: Wolke liegt am Dach ca. 1 m zu tief (altes Ergebnis), Vordach fuer die Wolke unsichtbar.

## 6. Geaenderte Dateien (Cherry-Pick fa26647, Quellen)
tools/baukasten_gen.py, tools/bauteil_overlay.py, tools/gauben_crop.py, modelle/kaufhaus_grob3/{objekt,masstabelle}.json,
messprotokoll/K-6162, K-c12, K-j05, K-p03, M-6259-001..013, himmelsmaske/{6162,c12,p03}.png, LOGBUCH_GAUBEN_OBEN_R2, Lehren L31-L33, NICHTS_GEBRACHT; Bau-Erzeugnisse neu gebaut.
Konfliktdateien (STL, pruefbericht, fehlteile_*, seiten.jpg) = HEAD-Stand + Neubau.

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
|---|---|---|
| Angenommene Runde ist erst fertig, wenn sie auf main liegt; bei Konflikt nur in Erzeugnissen Quellen cherry-picken und neu bauen | R2 scheiterte an teil_01.stl, R1-ngb verwarf danach ohne Vortor | Kreis-Merge (bereits seit 3de8d0a); hier manuell |
Nicht ins Lehren-Register dupliziert (L31-L33 aus R2 gelten).

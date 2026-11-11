# Kreis 20261111_045306a045306 r2 - baldachinreihe:baldachine

## 1. Formbeschreibung (Stufe 0; Fotos 6120 Uebersicht/Nah, 6119, j05 Nah, 6117, i08 schraeg; angesehen via Foto-F1-Overlays)
Zonen unten->oben: Haube (hohl, 2 Wangen) / Masswerkband (Spitzbogen-Felder, Raute) / Krone = Kranzgesims-Riegel + Blattwerk / 3 Fialen. Grundriss rechteckig, wandgebunden. 4 Baldachine ueber 4 Figuren (Z-6161-002). Formfamilie: vorhandene `baldachinreihe` in baukasten_gen.py (keine neue noetig).
Befund: gelber waagerechter Balken ueber die Kronenbreite = Kranzgesims-Unterkante; Modell-Krone (t0 0,30) lag hinter der Bandfront (t1 0,36), Kante verdeckt.
Ungeklaert: Rueckseite nicht sichtbar (ANNAHME Huelle); Maßwerk-Feinform.

## 2. Zaehlungen
Keine neue Zaehlung; bestehend Z-6161-002 (4 Baldachine), Fialen 3 je Stueck (ANNAHME Seitenfialen symmetrisch).

## 3. Pruefungen
| Pruefung | vorher | nachher | Soll | Quelle |
|---|---|---|---|---|
| Baldachin 2: Kranzgesims vor Bandoberkante (neu) | Reichweite ~ -0,02 (Altstand, Krone hinter Band; Pruefstand-Rot-Lauf nicht separat protokolliert, rechnerisch) | 0,09 | 0,05..0,20 | M-6120-062/063, M-6120-060/061 |
| 7 bestehende Baldachin-Pruefungen | OK | OK | unveraendert | M-6161-022..025, M-6120-053/060/062 |
Pruefstand gesamt: Exit 0 (bauen_abnehmen, RCPARK_OHNE_FOTODIAG=1; Ohne Fotodiagnosen, "Kanten-Schleife ungeprueft" und freiraum_audit fehlgeschlagen wie vor meiner Aenderung).
Foto-F1 (halbe Aufl., alle 10 Torfotos): 0,764 -> 0,815 (Praez 0,747 -> 0,740, Recall 0,782 -> 0,907). Volle Aufloesung/Hoehenwert f1_h NICHT von mir gemessen (Endtor).
Verworfene Varianten: siehe NICHTS_GEBRACHT.md (Masswerk-Rippen -0,011, Fialen kuerzen widerspricht Messung, Parameter-Tweaks Rauschen).

## 4. Overlays
- /media/oem/scan/rc-park_kreis/kaufhaus_grob3/20261111_045306a045306/wt_r2/modelle/kaufhaus_grob3/audit/rundekreis2_baldachine/baldachinreihe__baldachine_{6120,6119,j05,6117,i08}.jpg (nachher, halbe Aufl.)
- Vorher: .../fotoform_bilder/baldachinreihe__baldachine_<foto>_r2_vorher.jpg
- Scratch: /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis2/b_* (Varianten)

## 5. Fehlerliste
- Krone/Kranzgesims-Kante: trifft (6120 Mitte und rechts am Overlay gruen gesehen); Tiefe .46/.42 = ANNAHME im Fehlerband +-0,1 m, nur durch Foto-F1 gewaehlt.
- Baldachin 1 (links, 6120): trifft NICHT - rotes Band im Kronenbereich (Form "wie 2" ANNAHME, Lage ds). Offen.
- Fialen: rot/zu dick in i08/d11/6119 (schraege Ansichten) - offen, Kuerzen widerspricht M-6120-051.
- Maßwerkband: Kanten fehlen (gelb in 6120 rechts, j05) - Rippenversuch verschlechterte, offen.
- Haube/Wangen, Rueckseite: ungeprueft. teile_lage_pruefen/foto_diff/fehlteile_finden/teile_sichtpruefung: nicht gelaufen (Zeit).

## 6. Geaenderte Dateien
modelle/kaufhaus_grob3/objekt.json (stufen[2], stufen_quelle, historie), masstabelle.json (Messung baldachin2_krone_vorn, Pruefung, Beobachtung), NICHTS_GEBRACHT.md, REZEPT_GEBAEUDE_AUS_FOTOS.md, Audit/Pruefbericht-Nebenprodukte des Baus. baukasten_gen.py unveraendert (Maßwerk-Versuch zurueckgenommen).

## 7. Generalisierte Lehre
| Lehre | Anlass | Werkzeug |
| Gelber Vollbreiten-Balken = verdeckte Gesimskante durch zu flache Stufentiefe, erst Tiefen gegen Triangulation pruefen | Krone t0 < Bandfront | teil_fotoform + Variantenmessung |
| teil_fotoform bewertet Modellkanten aus dem Gesamt-STL; Variantenlauf braucht Gesamtbau mit absolutem STL_NAME (sonst Repo-STL ueberschrieben) | erste Varianten maßen nur Rauschen | variante.sh in agent_scratch_kreis2 |

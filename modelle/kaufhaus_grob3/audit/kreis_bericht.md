# Kreis ff_+14_+8_+12 r1 (Fehlendes Element) – Bericht
**Befund:** Fehlend waren die vier Baldachine ueber den Kaiserfiguren (Wimperg-Konsole, Masswerkband, Blattwerkkrone, 3 Fialen). Der Kasten ist 16,7 m breit; die gelben Flecken stammen davon.
Vorversuche (6 Runden, alle am alten Gitter-Tor verworfen) hatten dasselbe Teil gebaut. Ich habe den Stand aus Commit 69fdfaa2 (Quelldateien) auf aktuelles main uebernommen (`git apply --3way`) und am Foto-Tor neu gemessen.

## 1 Formbeschreibung
Familie `baldachinreihe` (neu in tools/baukasten_gen.py, generisch, Parameter in objekt.json): je Figur Konsole mit hohler Haube, Masswerkband, Krone aus Huellkoerper, 3 Fialen. Fotos: 6120 (Nahaufnahme, 3 Baldachine), 6162 (Uebersicht schraeg, 4), 6161, 6117. ANNAHME: Form nur an Baldachin 2 gemessen (M-6120-051..064, M-6161-022..025), fuer die uebrigen drei uebernommen; Blattwerk nur als Huellkoerper.
## 2 Zaehlungen
Zahl 4 aus Vorrunde; in dieser Runde NICHT neu gezaehlt (kein neues Z-Protokoll). In 6162 sind 4 Baldachine am Foto sichtbar (selbst angesehen).
## 3 Pruefungen
7 Pruefungen aus der Vorrunde (Protokolle M-6120-051..064, M-6161-022..025); `tools/bauen_abnehmen.sh kaufhaus_grob3`: „alle Pruefungen bestanden“ (1 Widerspruch, 103 Beobachtungen ohne Pruefung). Vorher-rot-Test dieser Runde NICHT neu gefahren (Pruefungen stammen aus Vorrunde).
Foto-Gate (teil_fotoform, gleiche 10 Fotos 6115,6117,6119,6120,6132,6161,6162,6164,6171,6182, Vorher = Teilemenge ohne Baldachine):
| Teil | vorher | nachher |
|---|---|---|
| baldachinreihe:baldachine | 0,458 | 0,696 (Praez 0,694, Soll >= 0,25) |
| figurenreihe:figuren | 0,840 | 0,848 |
| quader:rumpf_og | 0,730 | 0,749 |
| quader:gesims | 0,615 | 0,628 |
| satteldach:haupt | 0,725 | 0,744 |
| fensterreihe:og | 0,829 | 0,827 (-0,002, < 0,02) |
Gate (+0,02 im Bildbereich, Praez >= 0,25, kein Teil > 0,02 schlechter) erfuellt.
## 4 Overlays
modelle/kaufhaus_grob3/audit/gitter_generator/rundekreis1_baldachin_nachher_{6120,6162,6161,6117}.jpg; alle 9 in /media/oem/scan/rc-park_daten/kaufhaus_grob3/agent_scratch_kreis1/bilder_nachher/ (vorher: bilder_vor/ – dort fehlt das Teil).
## 5 Fehlerliste
- baldachine: trifft: Lage ueber Figurenkoepfen, Haupthoehe/Fialen in 6120/6162 (angesehen). Trifft nicht: Blattwerk/Masswerk nur Huelle (rote Flaechen in 6120 links/rechts, gelb Masswerkband Mitte); Baldachin 1/3/4 ungemessen (ANNAHME).
- rumpf_og/gesims Ost-Ende 1,3 m zu lang: ungeprueft, nicht bearbeitet. fensterreihe:og Sohle/Glastiefe: ungeprueft. Figuren-Attribute, Dachrinne, Gassenwand-Fenster: nicht bearbeitet.
- `teile_lage_pruefen`: Baldachine nicht in der Ausgabe; quader:rumpf_eg meldet Median 3,33 m LAGE PRUEFEN (nicht durch diese Runde verursacht, nicht untersucht). foto_diff/fehlteile_finden/teile_sichtpruefung/regression NICHT gelaufen; audit/seiten.jpg nicht angesehen.
## 6 Geaenderte Dateien
tools/baukasten_gen.py, modelle/kaufhaus_grob3/{objekt,masstabelle,elemente}.json, Abnahme-Artefakte (STL, MASSNACHWEIS, pruefbericht), NICHTS_GEBRACHT.md, Overlays. Nichts committet.
## 7 Generalisierte Lehre
Lehre: Verworfenen Patch ueber `git diff <commit>^ <commit> -- <Quelldateien>` + `apply --3way` uebernehmen, nicht den Gesamtpatch | Anlass: Patch mit Binaer-/Audit-Dateien scheitert | Werkzeug: git. (Nicht ins Lehren-Register eingetragen.)

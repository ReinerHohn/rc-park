# Stand 2026-11-08 (Uebergabe): Wolke -> Modell, Foto-Diff, Leave-out

Aktives /goal (Stop-Hook): "probiere alle moeglichen algorithmen und Pipelines, wie du aus einer Punktwolke auf ein 3D Modell kommst, dass moeglichst kleinen diff hat, wenn man dieses Modell ueber alle Photos mit der jeweiligen Kamera legt". Hook meldet wiederholt "nicht erfuellt" (Vollstaendigkeit nicht beweisbar). Alle Versuche: `modelle/NICHTS_GEBRACHT.md` BS90-BS133 (BS134 fehlt noch = lo4-Ergebnis, siehe unten).

## Kernergebnis
- Tor (beide Glaettungen g0.18|g0.05, Mittel besser, >=2/3 Fotos besser, kein Foto > +0.03 schlechter), 22 Fotos global, Referenz d03_fix = -0.0848|-0.0855 (kleiner = besser).
- Parametrische Generatoren, Lage-Sweeps, Kombination, Hybrid per Ersetzen, Formen-Katalog, Glaetten, netz_verfeinern, Poisson: schlagen d03_fix NICHT (BS90-BS115).
- **hlo** = d03_fix unten (z<6 m) + Unsharp(i2k2, Clamp 0.3 mm) auf dichtem `mvs_default_fix` oben: -0.0898|-0.0940, Tor bestanden auf 22 Fotos und auf 21 weiteren Fotos (BS119-BS122). Datei `modelle/stl/kaufhaus_hlo_dfs03_d03fix.stl` (28 MB, nicht wasserdicht, ~570k Fl.). Zonengrenze 5-8 m Plateau, 4 m faellt durch.
- **Einschraenkung (BS126/BS131):** alle 22+21 Fotos liegen in der OpenMVS-Szene (94 Fotos). Leave-out (8 Testfotos weggelassen) zeigt: gleiche Netzfamilie ohne die Fotos ist 0.03|0.05 schlechter ("Gesehen"-Praemie >> hlo-Vorsprung 0.004-0.010); **Schaerfen hilft auf unbekannten Fotos NICHT** (lo_dfs03 vs lo_default +0.0043|+0.0026). hlo-Vorsprung als Modellguete NICHT belegt.
- Auf unbekannten Fotos (7 auswertbar, Basis lo_default): OpenMVS-Standard (smooth 2) am besten; s6 -0.0047|+0.0113, d30 (decimate 0.3, 90k Fl.) +0.0007|+0.0014 (praktisch gleich gut = Hebel fuer Druck), fs/q2/s0/t3/Taubin schlechter (BS132). Wasserdicht per Winding Number (tools/netz_winding.py, MPL) aus lo_d30: +0.021..+0.029|+0.002..+0.004 schlechter (BS133), Foto 014 Ausreisser.
- pymeshfix (GPL) wurde fuer BS124/BS125 nur als Test benutzt -> `modelle/LIZENZ_WERKZEUGE.md`; nicht in Produkt.

## Leave-out-Aufbau (reproduzierbar, validiert)
- Testfotos festgeschrieben: `modelle/kaufhaus_null5/leaveout_fotos.json` (001,005,014,020,025,031,042,055,067,075; 031/067 nie in der Szene; 7 von 8 auswertbar).
- Dichte Wolke ohne Testfotos: `modelle/kaufhaus_null5/sfm/dicht_alle_lo` (`tools/sfm_dicht.py ... alle_lo --netz alle --fotos <86 Fotos>`, 2088 s; NIE Seite "alle" nehmen = rmtree von dicht_alle). 
- Netz: `$OMVS InterfaceCOLMAP -i dir -o scene.mvs --image-folder dir/images` -> `ReconstructMesh scene.mvs -p scene.ply -o mesh.mvs` (OMVS=/media/oem/scan/openmvs Wrapper). Rahmen: lo-Mesh -> Modell per `Xm=((X-t)@R)/s` (SFM-AUSRICHTUNG-alle.json), STL mm = Xm*1000/87, Zuschnitt auf Bounds von `wettbewerb_kh/netze4/mvs_default.stl`. **Validiert:** Vollnetz so = mvs_default (748733 vs 748143 Fl., Abstand 0.000 mm). mvs_default_fix = default minus 24 Flaechen.
- d03_fix-Reparaturkette (Saeulen/Fix, Register BR) NICHT als Skript -> d03_fix_lo fehlt, hlo vs d03_fix auf unbekannten Fotos nicht pruefbar.
- Skripte (scratchpad, bei Bedarf neu): Zuschnitt/Umrechnung siehe Absatz oben; Diff: `python3 tools/diff_parallel.py start NAME --objekt modelle/kaufhaus_null5/objekt.json --basis lodef:/media/oem/scan/rc-park_null/lo_default.stl --kandidat X:pfad --liste 001,005,014,020,025,042,055,075 --g 0.18,0.05`; Ergebnis `diffpar/NAME/global_<g>/ergebnis.json` (Delta je Foto gegen Basis auswerten, `tools/diff_parallel.py tabelle` zeigt Mittel).

## Laufendes / offen (beim Neustart pruefen)
1. **Job lo4** (`rcpark-dp-lo4-global-018/-005`): Tiefenfilter-Fusionsvarianten auf der Leave-out-Wolke, Basis lodef = lo_default. Kandidaten `lof_mp3/mp8/re1/re4/de03/ne20.stl` = Fusion mit min_num_pixels 3/8, max_reproj_error 1/4, max_depth_error 0.03, max_normal_error 20 (aus `/media/oem/scan/rc-park_null/lo_fus/<var>/mesh.ply`). Ergebnis: `python3 tools/diff_parallel.py tabelle lo4` bzw. ergebnis.json auswerten (Delta vs lodef, besser x/7, worst); als BS134 in NICHTS_GEBRACHT eintragen. Variante `photo` (photometrische Fusion): mesh.ply fehlt (Platte war voll) -> in lo_fus/photo `ReconstructMesh scene.mvs -p scene.ply -o mesh.mvs` nachholen, dann gleich umrechnen und diffen.
2. Weitere Hebel (noch nicht getestet): hoeher aufgeloeste Wolke/Fotos, andere Tiefenfilter, Wolke ohne Gebaeude-Nachbarn, weitere Leave-out-Gruppen (10 Fotos sind wenig, Rauschen), d03_fix-Reparaturkette skripten.
3. Endergebnis nicht festgelegt: Foto-Diff-Sieger hlo (mit Vorbehalt BS126/BS131), Druck: d03_fix (wasserdicht). Entscheidung beim Nutzer.

## Platz (Vorfall 8.11. ~08:30)
- /media/oem/scan lief auf 100 % (Fusions-Varianten legten je 2,5 GB bitgleiche .dmap-Kopien an). Jetzt ~12 GB frei (88 %). Platzwaechter (Dienst `rcpark-platz_waechter`, Grenze 14 GB) verschiebt auf Stick `/media/oem/rcstick` (lo_mvs, lo_fus/mp3, mp8 liegen dort, Symlinks).
- **Regel (Nutzer 8.11., Memory feedback-platz-und-duplikate):** bitgleiche Dateien verlinken statt kopieren (cmp pruefen), Platz vor Schleifen rechnen (df), Zwischenstaende direkt auf den Stick; eigene Test-Duplikate darf ich verlinken/loeschen. Erledigt: lo_fus/re1,re4,ne20 .dmap -> Symlinks auf lo_fus/de03.
- Grosse Ordner: lo_fus (~12 GB ohne Duplikate), lo_mvs (5 GB), diffpar/*.

## Sonstiges
- 3 Artifact-Monitore gestoppt (3D-Viewer-Artifacts); 3D-HTML Wolke vs Modell: https://claude.ai/artifact/46AEWMGwLJJXFFCnB8rpLs (Stand vor hlo, nicht aktualisiert, hlo-STL zu gross).
- `tools/diff_parallel.py tabelle` Paarfilter-Fix (Foto ohne Basiswert) eingebaut.
- Kein Commit gemacht (Regel: nur auf Auftrag).

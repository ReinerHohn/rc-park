# Stand 2026-11-08 (Vormittag): parametrisches Kaufhaus gegen Wolke (Nutzerweg)

**Weg (Nutzer 8.11.):** vorgebautes Gebaeude `modelle/kaufhaus_grob3` (stl_teil-Gruppen + parametrische Bauteile), moeglichst viele Parameter je Teil, gegen die Punktwolke
`/media/oem/scan/rc-park_null/wolke_netzrahmen.npy` einpassen, neue Parameter erfinden. KEINE Netz-/Foto-Diff-Jagd mehr (hlo = "geschmolzenes Wachs"; lo4 = BS134, nichts gebracht).

## Werkzeuge (neu, tools/)
- `param_wolke_fit.py <objekt> "typ1,typ2" --zmin --rand --iter --pop --uebernehmen`: CMA-ES, baut nur die genannten Bauteile (`NUR_BAUTEIL` in baukasten_gen.py, ~1,5 s),
  J = getrimmter Abstand Wolke->Bauteil + 0,5 * Bauteil(oben)->Wolke. Parameterraum `modelle/<obj>/parameter_raum.json`. Ergebnis `wolkenfit_*.json`.
- `wolke_gauben_messen.py <objekt> <dach-typ> --aus ...`: Gauben aus Wolke (Punkte > 0,35 m ueber der Dachebene) -> Reihen/Teilung/Hoehe. Zaehlung bleibt Foto (Z-018-005 = 3 untere, Z-018-006 = 2 obere).
- baukasten_gen.py: neue Bauteile/Optionen `gaubenreihe` (sitzt auf Vorderhang, nutzt `ctx["dach"]` des Satteldachs davor), `satteldach.symmetrisch` (verworfen), `NUR_BAUTEIL` (Liste mit Komma).
- Render zum ANSEHEN (Pflicht vor jedem Zeigen): `scratchpad/rend2.py` Dreiecks-Renderer (nicht im Repo; `trimesh`+`cv2`, Painter-Algorithmus, Blick entlang +y; Hauptfassade = az 180).
  Punkt-Render (rend.py) taeuscht (Rauschen) - nicht benutzen.

## Befunde
- Wolke sieht am Dach nur den VORDERHANG (steile Ebene n 13 / z 10,8 bis n 7 / z 19,3); LoD2 dachtyp enthaelt "Sheddach" -> Dach als Pultdach: n_first 5,9, n_traufe_h 5,84, z_traufe_h 11,6 (ANNAHME aus Altmodell). Symmetrische Rueckseite war FALSCH (reichte bis n 2,4).
- Dach gefittet (grob3 `satteldach:haupt`): z_first ~20,7, Median Wolke->Dach 0,27 -> 0,12 m. Hoehe Modell 20,6 m.
- Gauben: Wolke zeigt 3 (u -4,7/0,1/3,9; z 12,1) + 2 (u -2,4/1,6; z 14,7), Teilung 4,28/4,31 = deckt Fotozaehlung. Freier Fit ohne Messstart lief in Rauschen (t 0,6/0,9) -> immer erst messen, dann fitten.
- Letzter Bau: `modelle/stl/kaufhaus_p3_1-87.stl` (grob3, stl_teil:gauben abgeschaltet). Render ansehen: Dach+Gauben plausibel, Gauben noch zu klein/schmal (breite 0,94 = nur Sichtflecken der Wolke; Wolke blind fuer Fensterflaeche).
- Artifact mit hlo-Netz (WCoxM1eLJxJECVoduDumoi) ist veraltet/unerwuenscht; Nutzer will parametrisches Modell sehen.

## Offen (Reihenfolge nach Wolkenabstand, teilabstand_2026-11-08.json)
1. Staffelgiebel (Median 0,41 m, stl_teil) -> `treppengiebel` parametrisch (Bauteil existiert, null5-Stufenzahl aus giebel_stufen_zaehlen.py).
2. Fassade 0,11, Fenster (Fensterreihen als echte Raster, nur Streben, Plexi dahinter), figuren/helme (starr).
3. Erker/Balkon/Bogenreihe liegen in grob2 (erker:0/1, balkonband:haupt, bogenreihe:laube) - in grob3 noch stl_teil:erker -> uebernehmen und per param_wolke_fit nachziehen.
4. Neue Parameter suchen (Dachueberstand, Gaubenform, Giebelstufenhoehe...), Foto-Diff/foto_overlay NUR als Gegenprobe.
5. 3D-HTML des parametrischen Modells zeigen (nach Ansehen): `tools/viewer_stl_wolke.py` (STL <= ~10 MB, `fast-simplification` ist in venv-seg installiert).
6. Erst am Ende: Pruefstand/Masstabelle fuer grob3 (Belege `beleg()` sind gesetzt), `tools/bauen_abnehmen.sh` sobald Objekt in Abnahme.
Kein Commit gemacht.

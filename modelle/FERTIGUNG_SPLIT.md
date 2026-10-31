# fertigung_split.py - Modell in Lasercut-Platten + 3D-Druckteile aufteilen

Allgemeines Werkzeug (kein Wissen ueber das Objekt): `tools/fertigung_split.py`.

```
/media/oem/scan/venv-seg/bin/python -W ignore -I tools/fertigung_split.py MODELL.stl --out ORDNER \
    --dicke 2 --bett 410x400 --druck 220x220x250 --gcode
```
(venv-seg: trimesh, shapely, manifold3d, scipy, skimage. `--gcode` ruft `laser_blank_cut.py` mit `~/.venvs/strom` auf, dort ist shapely nachinstalliert.)

## Was es tut
1. **Platten finden:** zusammenhaengende, coplanare Dreiecke (Toleranz 0,6 Grad / 0,12 mm), Flaeche >= 600 mm2, kuerzeste Seite >= 10 mm. Waagrechte Flaechen nur mit `--horizontal`.
2. **Loecher je Platte per Strahlenraster klassifizieren** (Strahlen von aussen):
   Vertiefung >= 1 mm oder offen (Fenster, Tor, Nische) = **durchgeschnitten (rot)**;
   Erhebung (Gewaende, Relief, Tafel) = Platte bleibt voll, Umriss als **Klebemarke graviert (gruen)**; jede Platte traegt ihre Nummer.
   Platten werden von aussen gesehen gezeichnet (u rechts, v oben).
3. **Druckteile = Modell - Plattenvolumen - Innenkern** (Voxel-Distanz, Hohlschale 2,4 mm) **+ Traegerschicht** 0,5 mm unter den Erhebungen, die sie zu wenigen Klebeteilen verbindet. Teile ueber dem Bauraum werden gleichmaessig geteilt.
4. **Ausgabe:** `laser/rib_platte_NN.svg` (Schnitt #f00, Gravur #0a0), `druck/*.stl`, `laser_platten.csv` (Position/Normale je Platte im Modell), `STUECKLISTE.txt`, mit `--gcode` `rohlinge/rohling_NN.svg/.png/.gcode` (Sculpfun S9, GRBL, 410x400, Nesting).

## Ergebnis Martinstor (1:87, 2 mm)
30 Platten (4 Schaftwaende 113-130 x 267 mm, Dachflaechen, Tuer-/Torwangen ...), 2 Laser-Rohlinge, 113 Druckdateien, 234 cm3 Druckvolumen, alle passen in 220x220x250 (der Sockelkoerper ist 203 mm hoch, ein Dachteil wurde in 2 geteilt). Laufzeit ca. 50 s.

## Wichtig / Grenzen (ehrlich)
- **Platten sitzen 0,5 mm hinter der Aussenebene** (Traegerschicht liegt davor). Aussen = Traeger + Relief.
- **47 von 113 Druckteilen** haben kantenberuehrende Stellen (Kanten mit >2 Flaechen); Slicer (Bambu Studio / PrusaSlicer) reparieren das beim Import, vorher einmal ansehen.
- Kein automatischer Passstift/Nut: geteilte Druckteile und Platten werden mit Klebemarken und Stossfuge zusammengesetzt. Wandkaemme der Platten (aus den Eckquaderfugen) greifen in die Eckpfosten.
- Uhr-Nische ist als Kreis durchgeschnitten: Zifferblatt muss als Druckteil eingeklebt werden.
- Bei 1:87 sind Fugen 0,8 mm und Relief ~1 mm: mit 0,2-mm-Duese druckbar, mit 0,4 mm grob.
- Schnitt-/Gravurparameter (Material, Leistung) nur Startwerte aus `s9_laser.conf`; am Restmaterial testen.
- Noch nicht getestet: echter Probeschnitt / Probedruck.

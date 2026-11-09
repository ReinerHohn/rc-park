# Methodik: Kanten-Stabilitätskarte (Sweep + Zählen)

Stand 2026-11-09. Werkzeug: `tools/kanten_stabil.py` (GPU), Stapel: `tools/stabil_alle.py`.
Idee vom Nutzer: über jedes Foto mit vielen Methoden und Parametern sweepen, dann schauen, welche Kanten bei vielen Läufen bestehen bleiben (Peaks). Echte Kanten bleiben, Rauschen nicht.

## Verfahren (je Foto, 261 Läufe, ca. 2 s auf der RTX 4060)
1. Foto auf 1500 px Breite.
2. Varianten (29):
   - 9 Farbkanäle: Grau, Lab-L/a/b, HSV-S/V, R, G, B (jeweils Original).
   - Zusätzlich für Grau, L, V, G: Gamma 0,5, Gamma 2, CLAHE (clip 2 und 5), lokale Kontrastnormierung (Helligkeits-/Kontrast-Sweep).
3. Je Variante 3 Maßstäbe (Gauß sigma 1, 2, 3) x 3 Schwellen (oberste 3 / 5 / 8 % der ausgedünnten Gradientenpixel, Hysterese: schwache Kante nur nahe einer starken).
4. Jede Kante bekommt den Anteil der Läufe, in denen sie steht (Toleranz 1 px, 3x3-Dilatation). Ergebnis `votes[H,W]` in 0..1, als PNG (Wert*255) in `<Daten>/stabil/<foto>.png`.

## Sichtbefund (IMG_6261, 9.11.)
Dachlinie gegen den Himmel, beide Staffelgiebel, Turmhelme mit Spitzen, Gauben, Arkadenbögen, Fensterrahmen und Sprossen kommen sauber und dünn heraus. Himmel und Wolken bleiben schwarz. Pflaster ist dunkel verrauscht (kurzlebige Kanten). Personen erscheinen, weil sie im einzelnen Foto Kanten haben; erst die Überlagerung mehrerer Fotos mittelt sie heraus.
Damit sind genau die Kanten sichtbar, die die 3D-Verfahren bisher nicht fanden (Dachfirst, Giebel, Helme). Das Problem lag nicht in der Kantenerkennung, sondern in den Einzelquellen (SAM / ein Canny / Mehrheit über 5 Kanäle).

## Abgrenzung zu Früherem (nicht wiederholen)
Phasenkongruenz auf Ortho (Präzision 0,06–0,15), DexiNed, Subpixel-Canny, Lab-b-Familie, Farb-Sweep als 3D-Mehrheit je Wolkenpunkt: siehe `LOGBUCH_2026-11-09.md`. Neu ist das Zählen über viele Parameter am Originalfoto.

## Nächste Schritte (Stand der Arbeit)
1. Stabilitätskarten aller kalibrierten Fotos (Job `stabil_alle`).
2. Triangulation mit `--stabil DIR [--sthr 0.5]` (Linien per LSD auf der Karte, Prüfdistanz aus Karte >= sthr).
3. 3D-Abstimmung über mehrere Fotos auf der Karte (Personen mitteln sich heraus, feste Kanten bestätigen sich).
4. Prüfung: Dachfirst/Giebel/Helme in 3D vorhanden (Anzahl Segmente z > 15 m), Overlay-Sichtprobe, dann Schleife und Editor.
5. Mögliche weitere Quellen in den Zähler: Phasenkongruenz (Log-Gabor/FFT, GPU), DexiNed; Stabilität pro Quelle messen.

## Offene Lizenz-/Annahmefragen
Keine neuen Fremdgewichte, nur OpenCV/PyTorch-Standardoperationen.

## Ergebnis Tiefen-Sweep (9.11. nacht) `tools/kanten_tiefe_sweep.py`
Statt Linienpaare zu triangulieren: jedes starke Kantenpixel (Karte >= 0,6) eines Referenzfotos wird entlang seines Strahls (4-90 m, 360 Tiefen) durchgesweept; je Tiefe zaehlt der Anteil der 12 Nachbarfotos (Basis 1-25 m), in denen an der Projektion wieder eine stabile Kante steht (>= 0,4, 1 px Toleranz). Peak (>= 0,7 und zweiter Peak <= 0,8 x erster) = 3D-Kantenpunkt. 5 s je Referenzfoto auf der GPU; 80 Referenzfotos -> 631 022 Punkte.
Befund: Voxel-Konsens (>= 2-3 verschiedene Referenzfotos) zeigt Boegen, Fenster UND das Dach: Firstlinie bei z ~ 27 m (x -6..19), Traufe bei z ~ 14,5 m, Giebelkanten an den Enden, Dachneigung in der Seitenansicht. Das Dach lag also ueber der Obergrenze, die der alte Suchkasten (Wolken-Perzentil + 8 m) zuliess, und die Wolke hat dort kaum Punkte. Segmente: `segmente_hoch_ts.json` (45, RANSAC tol 0,12 m, auf Punkten z > 14), `segmente_tsweep.json` (513, tol 0,05 m, Konsens >= 3).
Offen: Ein Teil der Dachpunkte ist duenn gepunktet; Staffelgiebel-Zacken noch nicht als Segmente; Suchkasten der Triangulation (HI z) anheben; Schleife gegen Stabilitaetskarten.

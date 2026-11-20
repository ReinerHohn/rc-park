# Spezifikation S7: Bildwert messen - nur Bilder/Frames verwenden, die Luecken schliessen (Plan Stufe 4c; Nutzer 5.11. 20:00, eigenes Video am 6.11.)

Ziel: Fuer jedes Kandidatenbild (Web, Mapillary, Videoframe, Handyfoto) VORHER einen Wert berechnen, der sagt, welche Fassaden-/Dachzellen es NEU sieht, und NACHHER messen,
ob die Abdeckung wirklich stieg. Ersetzt die Aehnlichkeitsklassen aus `bilder_schleife.py` (nicht in der Pipeline, PLAN_VERBESSERUNG M9) und `abdeckung.py` (Faustwerte).
Voraussetzung: Fehlerkarte aus S3 (`tools/fehlerkarte.py`: je Flaeche Zellraster 0,10 m mit `n_fotos`, `rot`, `gelb`, `rest`, `n_kam`).

## 1. Zellbedarf (`tools/bildwert.py --bedarf`)
Aus der Fehlerkarte des aktuellen Stands je Flaeche (Waende, Vorbauten, Dach) eine Bedarfskarte: `bedarf = w_abdeckung * max(0, 3 - n_kam)/3 + w_fehler * (gelb + rot) * [n_fotos >= 3]`
(Standard w_abdeckung 1, w_fehler 1; Plan-Schluessel). Dach: n_kam aus Wolken-Sichtbarkeit zaehlt, aber Dach-Bedarf nur ueber `rot/gelb` der Kanten (Wolke am Dach gesperrt, S3 0b).
Ausgabe: `audit/bildwert/bedarf_<fid>.png` + npz; Summe je Seite (Nord/Ost/Sued/West/Dach) als Tabelle = "wo fehlen Bilder" (ersetzt abdeckung.py).

## 2. Wert je Kandidatenbild (vorher)
Kamerapose des Kandidaten, je nach Quelle:
- Mapillary/EXIF: GPS + Peilung + Brennweite (`foto_vorpruefung.py`), Hoehe = 1,6 m ANNAHME -> grobe Pose (+-3 m, +-10 Grad), reicht fuer Sichtbarkeit.
- Videoframe/Handyfoto ohne GPS: nach dem billigen Match-Schritt (LightGlue gegen 20 Referenzfotos je Seite, `lg_match.py`) die PnP-Pose aus den 3D-Punkten des bestehenden Netzes (pycolmap `absolute_pose_estimation`, venv-colmap); ohne >= 30 Inlier: Wert = 0, Grund "nicht verortbar".
Sichtbarkeit: Zellmitten je Flaeche in das Bild projizieren (Embree-Sichttest gegen den aktuellen Stand + LoD2-Nachbarn wie `fassade_ortho`), Bedingungen: im Bild, Einfallswinkel < 70 Grad, Bodenaufloesung (m/px) < Ziel (0,05 m ANNAHME), Basiswinkel zu den bestehenden Kameras der Zelle 10-30 Grad (sonst nur halber Wert: Dublette oder reine Parallaxe).
`wert = Summe bedarf(Zelle) ueber gueltig gesehene Zellen` (m2-gewichtet). Dazu `neu_zellen` (n_kam < 3 vorher) und `seite`.
Ausgabe je Kandidat: wert, neu_zellen, seite, Pose-Guete, Grund bei 0.

## 3. Auswahl
Gierig nach Wert, mit Aktualisierung: nach Aufnahme eines Bildes n_kam der gesehenen Zellen +1, naechster Kandidat neu bewertet (sonst waehlen alle Frames dieselbe Luecke).
Abbruch: bester Wert < `min_wert` (Standard = 0,25 m2 Bedarf, ANNAHME = Druckaufloesung x 2) oder `max_bilder` je Lauf. Videoframes: Kandidaten = alle scharfen Frames (Laplace-Schwelle), Mindestabstand 0,3 s; so werden aus 5 min Video typisch 50-150 Frames statt 9000.
Ausgabe: `audit/bildwert/auswahl.json` (gewaehlt/verworfen mit Grund), Bildblatt der 16 wertvollsten (ANSEHEN).

## 4. Nachher (Beweis des Werts)
Nach Registrierung/Verdichtung der gewaehlten Bilder: Fehlerkarte neu; je Bild tatsaechlich neue Zellen (n_kam vorher < 3, nachher >= 3) gegen die Vorhersage; Kalibrierfaktor = tatsaechlich/vorhergesagt im Log; Bilder mit 0 neuen Zellen = "ohne Gewinn" (Liste).
Kennzahl des Laufs: Anteil Zellen mit n_kam >= 3 je Seite vorher/nachher (muss steigen) und F_k aus der Fehlerkarte (darf nicht steigen).

## 5. Einbau
Nullstart-Schritt `bilder` (vor `netz`) und Video-Stufe (`--videos`: Frames -> bildwert -> nur gewaehlte Frames in SfM) ; `fotos_einsortieren.py` ruft bildwert fuer den Foto-Eingang auf. `abdeckung.py` wird durch `bildwert.py --bedarf` ersetzt (alte Datei bleibt, Hinweis im Docstring).

## 6. Beweise (`tools/test_bildwert.py`)
- T1 synthetisch: Stand mit bekannter Luecke (z. B. Ostseite ohne Kameras, aus einem Kaufhaus-Netz die Ostkameras entfernen): Kandidaten = die entfernten Ostkameras + 10 Frontdubletten; Erwartung: alle Ostkameras vor jeder Frontdublette gewaehlt, Dubletten Wert < min_wert.
- T2 echt: G6-Mapillary-Seitenbilder und G3-Videoframes als Kandidaten; Tabelle Wert je Bild; Bildblatt der 16 besten angesehen: zeigen sie Seiten/Dach?
- T3 Nachher an einem Video (G3 oder Nutzer-Video 6.11.): Abdeckung je Seite vorher/nachher, Vorhersage vs tatsaechlich.
- T4 Martinstor: `--bedarf` laeuft und nennt Sued als groessten Bedarf (bekannt: Sued offen), ohne Handwert.
Regeln: GPU nur fuer LightGlue/PnP ueber job_start; keine Aenderung an foto_diff/qualitaetsstufen/baukasten_gen; Schwellen als Argumente mit ANNAHME; kein Commit.

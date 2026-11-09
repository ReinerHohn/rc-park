# Wie das Kanten-Drahtgitter entsteht (einfach erklaert, Stand 9.11.2026 abends)

**Ziel:** Eine Liste von 3D-Linien (Kanten) des Kaufhauses, aus der spaeter geschlossene, druckbare Teile entstehen.

**Ausgangsdaten:** 80 Fotos mit bekannten Kameras (Lage, Blickrichtung, Brennweite) + eine Punktwolke (1,8 Mio. Punkte). Zu jedem Punkt weiss man, welche Fotos ihn sehen.

## Schritt 1: Kanten in jedem Foto finden (nur 2D, je Foto)
Drei voneinander unabhaengige Quellen:
1. **SAM**: zerlegt das Foto in Flaechen (Fenster, Pfosten, Bogen ...). Die Grenzen zwischen den Flaechen sind Kanten. (scharf, aber verschmilzt feine Teile)
2. **Canny auf Grau**: klassische Kantenerkennung auf der Helligkeit.
3. **Farb-Sweep**: dieselbe Kantenerkennung auf fuenf Farbkanaelen (Lab L/a/b, HSV-Saettigung, Gruen). Findet Kanten, die in der Helligkeit fehlen (rot auf rot, Sprossen). Mehrheit der Kanaele entscheidet.

## Schritt 2: Die 2D-Kanten in 3D bringen (zwei verschiedene Wege)
**Weg A - Abstimmung auf der Wolke (`kanten_3d_vote.py`, `kanten_vote_quellen.py`)**: Jeder Wolkenpunkt wird in alle Fotos projiziert, die ihn sehen (Z-Puffer). Wir zaehlen, in wie vielen davon er auf einer Kante liegt. Viele Fotos stimmen ueberein -> echte Kante; nur wenige (Verdeckungsgrenze) -> verworfen. Die 3D-Lage kommt von der WOLKE. Schwaeche: wo die Wolke keine Punkte hat (Dach, ab 15 m), entsteht keine Kante.
**Weg B - Triangulation (`kanten_triangulation.py`)**: Eine 2D-Linie in Foto A und dieselbe in Foto B ergeben mit den Kameras genau eine 3D-Gerade (Schnitt zweier Ebenen). Die 3D-Lage kommt NUR aus den Fotos; die Wolke gibt nur den Suchkasten. Jeder Kandidat wird danach in den uebrigen Fotos geprueft. Findet auch Kanten ohne Wolkenpunkte.

## Schritt 3: Median statt Mittelwert (`kanten_fusion.py`)
Die drei Quellen haben verschiedene Skalen. Je Quelle zaehlen nur die besten 4 % (Rang), dann entscheidet die MEHRHEIT (>= 2 von 3). Eine einzelne verrauschte Quelle kann nichts hochziehen.

## Schritt 4: Aus Kantenpunkten Linien machen (`kanten_segmente.py`, `kanten_lib.py`)
GPU-RANSAC legt Geradenstuecke durch die Kantenpunkte (Segmente).

## Schritt 5: Schleife gegen die Fotos (`kanten_schleife.py`)
Gitter in alle 80 Fotos projizieren: Segmente ohne Fotokante loeschen; Rest leicht verschieben (maximale Fotostuetzung); Endpunkte entlang der Richtung verlaengern, solange das Foto dort eine Kante zeigt; fast gleiche Segmente verbinden; Boegen (Kreisfit) aus uebrigen Kantenpunkten. Mehrfach wiederholen.

## Schritt 6: Draht-Editor (`editor_draht.py`, Port 8767)
Mensch klickt Kandidaten an, loescht, vereinigt, schiebt Spline-Punkte, zieht neue Kanten. Rote Punkte = Kantenpunkte, die noch keine Kante erklaert. Speichern in `modelle/kaufhaus_grob3/draht_kanten.json` (`fix=true` = Nutzerkorrektur).

## Stand der Zahlen
| Lauf | Segmente | Foto-Stuetzung | Abdeckung Kantenpunkte |
|---|---|---|---|
| SAM allein (Weg A) | 787 | 0,70 | 0,43 |
| Median-Fusion + Schleife | 392 | 0,964 | 0,49 |
| + Durchziehen/Zusammenfuehren (strenger Beleg) | 364 | 0,957 | 0,50 |
| Triangulation (Weg B), 12 Referenzen | 880 | - | - (neu: Bogenreihe) |
Nicht gefunden: Dachfirst, Staffelgiebel, Tuermchenhelme (ueber 20 m). Diagnose Triangulation z>15 m: 115 517 Kandidaten, strenge Pruefung laesst 285 durch, laxe Pruefung 14 109 (Rauschen? noch offen).

## Was NICHT funktioniert hat (siehe NICHTS_GEBRACHT.md)
Hoehenfeld/Relief aus der Wolke, pymeshfix-Schliessen, voxelbasierte Huellen, Canny allein (zu viel Textur), LIMAP mit Wolkentiefe (Linien ohne Kanten).

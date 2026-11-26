# SPEC: Schwabentor-Demonstrator (Freiburg) inkl. Brücke

Stand 26.11.2026, Interview mit dem Nutzer (Skill /spec). Zugehörige Nutzerentscheidung: Memory `project-schwabentor-demonstrator-halbautomatisch`.
Zustand heute: Kette 1122zm = 10 von 11 PASST (Handvergleich), Bestand-Tor ohne Rückschritt, Brücke fehlt, Ost-Seite flach, Tür ohne Gewände/Stufen.

## Ziel
Ein zusammengesetztes, gedrucktes H0-Modell (1:87) des Schwabentors mit allen vier Wänden, dem Dach und der Brücke über die Straße (überdachter Gang mit Treppe),
das auf dem Foto kaum vom Original zu unterscheiden ist. Es dient als Demonstrator für das Geschäft („wenn wir das haben, sind alle Tore offen“).

## Nicht-Ziele
- Kein zweites Objekt (Martinstor, Kaufhaus); später nur als Gegenprobe, keine Voraussetzung.
- Keine Bemalung (eigene Spec nach dem Druck).
- Nicht das Miniatur-Wunderland / die Gesamtstadt.
- (Nicht gewählt, daher offen: Vollautomatik für beliebige Gebäude. Der Nutzer hat Halbautomatik für das Schwabentor ausdrücklich erlaubt.)

## Anforderungen
1. **Fertig** heißt: Nord, Süd, West, Ost, Dach und Brücke liegen als druckbare Teile vor, sind gedruckt und lassen sich zusammensetzen.
2. **Genauigkeit:** Form, Zahl und Lage von Fenstern, Gesimsen, Tor, Tür und Brücke stimmen mit den Fotos überein; Maßfehler unter etwa 2 % (bei 36 m Turm rund 0,7 m).
   Maßstab der Kette ist belegt (DOM1 +0,3 % ± 1,0 %); der Handbau schwab_v3 ist etwa 2,6 % zu klein und gilt nicht als Wahrheit.
3. **Grundwahrheit ist das Foto.** Ungesehene Wände werden nicht gespiegelt oder erfunden. Wo Fotos fehlen, nennt die Pipeline genau die Stelle und der Nutzer fotografiert nach.
4. **Brücke:** neuer generischer Baustein (Fotokanten + Sweep mit SfM-Kameras) in `tools/bauteile.py` für überdachten Gang mit Treppe, mit rotem Test. Kein Katalogteil.
5. **Halbautomatik erlaubt** für dieses Objekt: Kette liefert Rohform, Abgleich und Korrektur stückweise anhand der Fotos. Nie schlechter als der Bestand (Bestand-Tor), keine Handeinträge ohne Foto-Beleg.
6. **Druck:** stückweise, Details (Uhr, Zierteile) auf dem Bambu, lange 1-mm-Wände auf dem Prusa MK4S (Rippen, Rahmen, Brim). Mindestmaß 0,8 mm, keine Mikroteile.
7. **Reihenfolge der Arbeit** (damit wir konvergieren statt im Kreis zu laufen):
   1. Handyfotos (241 von 739) ins SfM-Netz einordnen, Abdeckung je Wand melden.
   2. Brücke.
   3. Ostseite und Tür (Gewände, Stufen).
   4. Fehler der Tore beheben (Freiraum-Tor, Tauschtest, Schwellen, Durchfahrt innen, Flanke f02).
   5. Druck.

## Randfälle
- Foto fehlt für eine Wand/Brücke: Stelle benennen, nicht bauen, Nutzer fotografiert; bis dahin im Bericht „nicht belegt“.
- Foto verwackelt oder Hoch-/Querformat gemischt: wird vor der Registrierung gefiltert (schon erledigt für die 739 Handyfotos: 241 gewählt).
- Neuer Code verschlechtert den Bestand: nicht nach main mergen, Ursache-Agent, Rückschritt nicht als Fortschritt melden.
- Messung nur an der Wolke belegt (z. B. Durchfahrt-Decke 7,22 m): gilt als vorläufig, bis am Foto geprüft.
- Handbau und Kette weichen ab: Maßstab und Foto entscheiden, nicht der Handbau (Referenz ist nicht fehlerfrei).

## Abnahmekriterien
- **Hauptkriterium:** Je Wand (Nord, Süd, West, Ost), Dach und Brücke ein Bild „Foto neben Modell“; der Nutzer sieht es an und sagt ja oder nein.
- Bestand-Tor ohne Rückschritt; Fehlerliste je Teil steht vor jedem Lob; Realitäts-Prozent wird gemeldet.
- Nicht verlangt (vom Nutzer nicht gewählt): Handvergleich 11 von 11, Probedruck-Passung als eigenes Tor. Beides bleibt als Hilfsmessung erlaubt.

## Offene Punkte
- Fotos für die Brücke (unten, Seite, Treppe): der Nutzer will sie später schicken; Abdeckung nach Einregistrierung prüfen.
- Ost-Seite, Treppenturm-Seite und Flanke f02: Fotos prüfen und ggf. nachfotografieren.
- Stirnbogen der Gegenseite f01 und Durchfahrt innen: nur Wolke, nicht am Foto belegt.
- Rundbogenfenster (einzige FALSCH-Zeile im Handvergleich), Tür-Gewände und Stufen.
- Merge-Sperren: Schwellen-Tor (10 Konstanten), Tauschtest, Freiraum-Tor f03 (32 %), Tor-Inventar (`tor_dichte_diagnose`).
- Bemalung und Zeitplan für den Druck: eigene Spec bzw. Nutzerentscheidung.

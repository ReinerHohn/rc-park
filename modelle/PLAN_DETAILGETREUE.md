# Plan Detailgetreue (H0, 1:87) - Stand 2026-11-02

Ziel: alle Details >= 7 cm am Original (0,8 mm in H0) sind vorhanden, an der richtigen Stelle, in richtiger Form. Der absolute Massstab (1:86 oder 1:89) ist zweitrangig (+-3 % genuegen);
wichtig sind Proportionen und Vollstaendigkeit. Proportionen lassen sich massstabsfrei aus Fotos messen (Verhaeltnisse), siehe Schritt 5.

## Ausgangslage (aus ABDECKUNG.md, Register BN-BP)
- Nordnetz: 16 Kameras, Richtungen nur in 2 von 8 Sektoren, keine Kamera ueber 6 m Hoehe; Wolke ab 45 m Hoehe duenn (< 20 % des Medians), ab 55 m fast leer -> Helm, Nadel, Turmspitze sind kaum belegt.
- Suednetz: 40 Kameras, alle 8-17 m Abstand, 76-83 Grad Blickwinkel zur Spitze -> oben stark verkuerzt, keine Details ueber der Traufe.
- Ost-/Westseite: keine eigene Abdeckung (Seiten unterscheidbar nur ueber Schlossberg-Fotos 060/061).
- Dichte Stufe: 1000 px ist der Sweet Spot fuer das GANZE Objekt; ob lokal hoehere Aufloesung Details bringt, ist ungemessen.
- Bandwahl streut zwischen Laeufen (bis 5 m); Details aus Einzelwerten sind unsicher.

## Schritt 1 - Detailkatalog und Detailbudget (Software, 1 Sitzung, kein Foto noetig)
- `elemente.json` (38 Elemente) zu einem Katalog ausbauen: je Element Seite, Hoehe, Mindestgroesse, Beleg-Fotos, Status (belegt / nur Annahme / fehlt).
- `tools/detailbudget.py` (neu): je 5-m-Hoehenschicht und Seite aus den Kamerapositionen und Brennweiten die Bodenaufloesung (cm je Pixel, Verkuerzung durch Blickwinkel) berechnen. Detail nur sichtbar, wenn Pixelgroesse <= 3,5 cm (Nyquist fuer 7 cm).
  Ergebnis: Karte "hier ist Detail physisch moeglich / nicht moeglich" - sie bestimmt Schritt 2 und verhindert, dass Software etwas verspricht, was die Fotos nicht hergeben.
- Pruefstand-Kennzahl "Detailabdeckung" = belegte Katalogelemente >= 7 cm / alle. Ziel >= 95 %; der Rest ist ausdruecklich 'Annahme'.

## Schritt 2 - Aufnahmeplan (der groesste Hebel, braucht dich)
Aus dem Budget abgeleitet (Zahlen aus ABDECKUNG.md; Standorte gemeinsam festlegen):
1. Bogen um die Nordseite, 10-15 Grad Schritte, 90-120 Grad, aus 45-70 m Abstand, Augenhoehe, gleiche Brennweite.
2. Erhoehte Standorte (Fenster, Dachterrasse, Parkhaus) fuer Helm und Nadel (45-65 m Hoehe), mit Tele getrennt von der Weitwinkelserie.
3. Suedseite aus >= 46 m Abstand (nicht 14 m), ebenfalls Bogen.
4. Ost und West (Seitenansichten der Tuermchen und des Dachs) - bisher nur Schlossberg.
5. Eine 2-m-Latte oder ein gemessener Zollstock am Boden in mehreren Fotos (Maßstab-Nebenprodukt).
6. Detailserien: Uhr, Wappen/Adler, Tafel, Tuermchen, Zinnen, Torbogen - je 8-12 Nahaufnahmen (30-60 Grad Schraegansicht), Originale ohne Zuschnitt, bedeckter Himmel.
Reihenfolge nach Nutzen je Foto (`foto_auswahl.py --beitrag` bewertet jedes neue Foto).

## Schritt 3 - Lokale Detailstufe (Software, nach neuen Fotos)
- Zweite dichte Stufe NUR fuer Interessengebiete (ROI: Uhr, Wappen, Tuermchen, Zinnen, Helm) mit hoeherer Aufloesung (--beschnitt/ROI; bisher ungetestet). Eigene Leiter 1000/1600/2400 px je ROI, gemessen gegen Fotovergleich im ROI (nicht globale Quote!).
- Reliefs (Uhr, Adler, Wappen) als Hoehenfeld aus den Nahserien (`foto_displacement.py`), Mindestrelief 0,8 mm = 7 cm.
- Mehrere Realisierungen (>= 3 Netze) -> Median je Detail statt Einzellauf (loest die Bandwahlstreuung).

## Schritt 4 - Details ins Modell (Generator)
- Bauteilbibliothek (Zinne, Konsole, Fenster, Quader-Schicht, Tuermchenhelm, Relief) mit Parametern aus den Messungen; jedes Element mit `beleg(seite, element, quelle)`; Annahmen als `ANNAHME:`.
- Detail nur einbauen, wenn Schritt-1-Budget und Fotobeleg es tragen; sonst Platzhalter in der Form des Elements (sichtbar markiert), kein Erfinden.

## Schritt 5 - Pruefung der Detailgetreue (massstabsfrei)
- `fehlteile_finden.py` je kalibriertem Foto und Seite automatisch nach jedem Bau; Treffer ansehen (Pflicht, CLAUDE.md 3e).
- Verhaeltnisse statt Meter: Schlankheit (Spitzenhoehe / Turmbreite), Geschosshoehen-Verhaeltnisse, Tuermchenabstand / Turmbreite aus Einzelfotos (Silhouette, `foto_verhaeltnis.py`). Ein Maßstabsfehler faellt dabei heraus.
- Render-gegen-Foto-Kantenabstand je ROI (Median in Pixeln), Ziel <= 2 px bei 1000 px Aufloesung.
- Sichtblatt `seiten.jpg` aller Seiten ansehen, Nutzer-Sichtfunde als Test nachbauen.

## Schritt 6 - Druckpruefung H0
- Fertigungsbewertung (`bewerter_fertigung.py`, Mindestwand/Mindestdetail je Druckverfahren): welches Verfahren (Harz/FDM) und welche Schichthoehe ist festgelegt? Davon haengt ab, welche Details 0,8 mm wirklich druckbar sind.
- Testdruck eines Ausschnitts (Tuermchen + Uhr) zur Kontrolle vor dem Gesamtdruck.

## Reihenfolge und Aufwand
1. Detailkatalog + Detailbudget: 1 Sitzung (sofort, ohne dich).
2. Aufnahmeplan mit konkreten Standorten: 1 Sitzung, dann Fotografieren durch dich (1-2 Touren).
3. Netz + lokale Stufe + Auswertung: 1-2 Sitzungen nach den neuen Fotos.
4. Generator-Details + Pruefung: 2-3 Sitzungen.
Einschaetzung ohne Gewaehr: ein Modell, dessen Detail >= 7 cm belegt ist, braucht etwa 5-8 Sitzungen plus die Fotos; das Fotografieren ist der kritische Pfad.

## Nicht Teil dieses Plans
Absoluter Massstab (Register BP); wird als Nebenprodukt der Latte-Fotos belegt, nicht angestrebt als Voraussetzung.

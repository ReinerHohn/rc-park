# PLAN: Handmodell in die Kette (Nutzer 24.11.2026: "extrem wichtig – davon haengt mein Projekt ab")

**Ziel:** Die Gesamtkette baut das Schwabentor aus Fotos AUTOMATISCH mindestens so gut wie das Handmodell `schwab_v3`
(Zielbild `modelle/schwabentor-1122/bestand/ZIEL_handstand_schwab_v3__*.jpg`) – ohne Handwerte, ohne Katalogteile.
Danach dieselbe Kette ohne Sonderweg an einem zweiten Objekt (Gegenprobe, dass es verallgemeinert).

## 1. Wie das Handmodell entstand (schwab_v3_gen.py, 15.–17.11.)
- H1 **Punkte picken:** je Bauteil Fotopunkte auf 1–2 Fotos von Hand -> `tools/foto_mass.py --tri/--tri2d` auf der Wandebene
  -> 56 Messprotokolle `M-<foto>-<nr>` in `modelle/schwab_v3/masstabelle.json`.
- H2 **Bauart je Bauteil:** typisierter Bau mit den Massen: Galerie (Boden, Bruestung, Holm, Knaggen, 3 Pfosten, 6 Streben),
  geschweiftes Pultdach, Rundbogenfenster (Blendnische + Oeffnung + Sohlbank), Uhr (Zifferblatt + Innenfeld), Spitzbogen-Tor,
  Steingewaende (fassade_fein -> steine_aus_foto), Traufkasten/Zeltdach/Laterne aus Foto-Triangulation.
- H3 **Relief:** OpenMVS-Netz + `relief_aus_fotos_mono.py` (Depth Anything V2, Apache-2.0) + `tiefe_lokal.py` (PatchMatch fein).
- H4 **Massstab:** DOM1-Laser (Faktor 0,933), Lot aus Foto-Vertikalen.

## 2. Der automatische Weg (je Hand-Schritt eine Kettenstufe)
- A1 statt H1 – **Kantenmessung je Bauteil:** Erkenner liefert die ZONE im Wandbild (fassade_fein je Flaeche) -> Kanten-Tiefen-Sweep
  in dieser Zone ueber mehrere Fotos (Kantenstufe) -> Massliste im GLEICHEN Format wie die Hand-Protokolle (`quelle: auto`, Fotos, Streuung).
  Wandbild = Bauplan: mehrere Wandbilder fuer mehrere Ebenen (Wand, Vorbau-Front, Dachflaeche).
- A2 statt H2 – **Typ + Baustein:** Bauart aus Wandbild + Formfamilie aus >= 3 Fotos -> generischer Baustein in `tools/bauteile.py`
  (Galerie/Balkon, Vordach_walm/geschweift, Rundbogenfenster mit Nische, Zifferblatt aus Fotos, Spitzbogen). Generator ruft nur auf.
- A3 statt H3 – Relief: Kettenstufen mono_relief/tiefe_lokal (laeuft, pruefen).
- A4 statt H4 – Massstab unabhaengig (Gebaeudemass/DOM1), Nah-GPS nur mit Schrumpftest (Agent 24.11.).

## 2b. Kernursache (Weg-Analyse 24.11., `modelle/WEG_HAND_ZU_KETTE.md`)
Fuer fast jedes Bauteil gibt es einen Erkenner. Ist ein Mass unsicher, STREICHT die Kette das typisierte Bauteil oder faellt auf Hoehenfeld/Kasten
zurueck; die Hand hat bei derselben Unsicherheit typisiert gebaut und die Luecke als ANNAHME belegt. GRUNDSATZ NEU: Form aus >= 3 Fotos belegt
-> typisiert bauen, unsicheres Mass als ANNAHME (begruendeter Ersatzwert + Bericht), nie verwerfen und nie Hoehenfeld.
Wurzeln: `ebenen_bauplan.py:101` (frontale Kameras nur fuer Waende -> Vorbau-Ebene 3354 statt ~50 000 Kantenpunkte -> `ebenen_masse.py:98-109`
kein Kasten -> `bauteile.py:1023` Hoehenfeld; typisierte Galerie nur mit MIT_KATALOG_GALERIE=1, `bauteile.py:1011`), `nischen_fenster.py:333`
(Nische trotz Form 16/19 verworfen), keine Gesims-Stufe, `kantenstufe.py:178` fehlende_kanten_haufen liest niemand,
`umgang_aus_fotos.py:170/185` Pfostenzahl per Mehrheit statt je Wand.

## 3. Verbote (aus Rueckfaellen)
- Hoehenfeld/Tiefenbild NIE direkt als Gestalt bauen (Treppenkloetze 21.11. + 24.11.) – nur als Messquelle fuer A1.
- Kein stiller Kasten-Fallback: faellt ein Bauteil auf Kasten zurueck, meldet das Bestand-Tor ROT mit Bauteilname.
- Keine Handwerte aus schwab_v3 in Code/JSON; `referenz_hand.json` nur zum Vergleichen.
- Jede dokumentierte Sackgasse bekommt einen roten Test, sonst gilt sie als ungesichert.

## 4. Fortschritt messen (Bild schlaegt Zahl)
- Checkliste = alle `beleg()`-Bauteile von schwab_v3. Je Bauteil Status FEHLT / FALSCH / PASST (`tools/hand_vergleich.py`)
  UND Detailbild (`tools/neben_details.py`) gegen Zielbild – PASST nur, wenn beides stimmt.
- Bestand-Tor: kein Bauteil schlechter als der beste Kettenstand (`modelle/<obj>/bestand/`).
- Je Lauf dem Nutzer: Bild Kette | Ziel | Bestand, dann Zahl "x von N Bauteilen PASST".

## 5. Reihenfolge (nach Sichtbarkeit am Zielbild)
1. Galerie (Pfosten, Streben, Bruestung) · 2. Vordach geschweift/geneigt · 3. Uhr-Zifferblatt aus Fotos · 4. Rundbogenfenster mit Nische
+ Sohlbank · 5. Spitzbogen-Tor · 6. Eckquader/Steingewaende · 7. Traufkasten/Zeltdach/Laterne · 8. Sued-/West-/Ostseite gleich behandeln.
Bruchstellen je Bauteil mit Datei:Zeile: `modelle/WEG_HAND_ZU_KETTE.md` (Agent 24.11., wird nachgetragen).

## 6. Ablauf je Bauteil (Skill kette-schleife)
Bruchstelle -> ein Agent (Stufe + Test mit roter Probe, Bild an Kopie) -> Merge-Probe -> `ketten_probelauf.sh` -> Schnelltest 0 -> main
-> Kettenlauf -> Bild gegen Ziel + Bestand -> Status in Checkliste -> naechstes Bauteil. Zwei Laeufe ohne Fortschritt = Methode wechseln.

## 7. Fertig, wenn
Alle Bauteile der Checkliste PASST (oder im Bild mindestens gleich gut), Bestand-Tor gruen, Nutzer bestaetigt am Bild;
zweites Objekt durch dieselbe Kette ohne Sonderweg mit Fortschritt.

## Stand (fortschreiben, neueste oben)
- 24.11. 22:45 · Plan angelegt. In Arbeit: Galerie-Treppen + Bestand-Tor, Uhr, Vordach/Galerie-Pfosten, Weg-Analyse (WEG_HAND_ZU_KETTE.md),
  Kegeldach, Kanten ueber Traufe, Massstab. Checkliste: noch nicht gemessen.

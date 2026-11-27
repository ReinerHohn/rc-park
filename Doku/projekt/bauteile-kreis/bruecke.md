# Brücke / überdachter Gang als Kettenstufe (Unterast)  ← [bauteile-kreis](../bauteile-kreis.md) ← [PROJEKT.md](../../../PROJEKT.md)
Plan: `modelle/RECHERCHE_BRUECKE_UND_PUTZ_2026-11-27.md` Teil A (B0–B5, Prüfungen A4). Spec: `modelle/SPEC_SCHWABENTOR_DEMONSTRATOR.md` Anf. 4.
Lage/Maßstab der Handyfotos: Zweig `lage-bruecke`, `modelle/schwabentor-1122/messprotokoll/bruecke_lage_1127/BRUECKE-LAGE.json`.

## Gilt
- Werkzeuge: `tools/bruecke_messen.py` (B1 Kamerawahl mit Wolken-Verdeckung, B2 Linien-Sweeps, B3 Massliste mit Quelle/Streuung/Status je Wert,
  eingebauter Tauschtest Zone ±30 %, Pfosten-Zählung je Foto), `tools/bruecke_bauen.py` (B4 Bau über `bauteile.ueberdachter_gang`, Tor, Teilung + STL,
  Bild „Foto neben Modell“, Schnitte in Metern). Baustein: `bauteile.ueberdachter_gang` (+ `pfosten_lagen`, `stuetzen`, `fehlt`, Liste `rot`), Tor `bauteile.bruecke_tor`.
- Ablauf: `tools/py tools/bruecke_messen.py kameras KAM.json LAGE.json WOLKE.ply BILDDIR KAMWAHL.json --max 400 --min_sicht 0.3`
  → `... messen KAMWAHL.json LAGE.json AUSDIR` (~3 min mit Tauschtest, 16 Kerne) → `tools/py tools/bruecke_bauen.py AUSDIR/massliste_bruecke.json AUSDIR/bau --kameras KAMWAHL.json --fotos a.jpg,b.jpg --wolke WOLKE.ply`.
- Kein stiller Fallback: jede Ersatzform, jedes `fehlt`/`instabil` und jeder Widerspruch zur DOM1-Länge steht in `bruecke_tor.json` als ROT mit Bauteilnamen.
- Höhen kommen aus Profilen in der Pfostenebene (Straßenfotos: Strahlen fast waagrecht → Höhe gut, Querlage schlecht); Querlagen aus senkrechten Kanten im Grundriss.
- Zählen: Pfostenzahl erst gültig, wenn ≥ 3 Fotos alle Pfosten und keinen in den Feldmitten zeigen (`zaehlung_pfosten`), sonst `fehlt`.
- Tests: `tests/test_bruecke_messen.py` (7 Teile, je mit `--fehler` rot belegt), `tests/test_ueberdachter_gang.py` (Baustein).

## Versucht
- 27.11. · Querkarte S(q,z) mit Canny-Pixeln über 40 Fotos → ✗ · nur Strahlenstreifen, keine Schnittpunkte (Straßenfotos fast waagrecht, Laub) · Höhen als Profil in der Wandebene, Querlage aus Pfosten.
- 27.11. · LSD-Geraden statt Canny-Pixel → ✓ · Pfostenreihe q −1,2 klar, Pfostenabstand ~3,1 m sichtbar.
- 27.11. · Gegenseite nur über Schwelle → ✗ · fehlte; lokale Maxima + Korrelation der Pfostenprofile (Pfosten paarweise) → q +1,96..2,0, Breite 3,16 m (DOM1 3,5 inkl. Dach).
- 27.11. · Enden aus 1-m/2-m-Fenstern mit Lückenbrücke → ✗ läuft in Anbau/Hang (52 m, 44 m); ohne Lücke, Abriss < 30 % → 28–30 m (DOM1 32,5, Wolke −13..+16) · Widerspruch gemeldet, nicht gemittelt.
- 27.11. · Tauschtest Zone ±30 % auf echten Fotos → ✗ · Pfostenzahl, Breite, Unterkante, First stabil; Traufe, Laufebene, Holm, Riegel, Spannweite springen (Kantenzuordnung mehrdeutig) → Status `instabil`, Tor ROT.
- 27.11. · Zweiter Durchgang mit Kern aus den gemessenen Enden → ↺ · Breite/Unterkante/First/Überstand stabil, Höhenkanten weiter nicht.
- 27.11. · Synthetik (12 Kameras, bekannte Brücke) → ✗ · Wandebenen und Unterkante/Traufe stimmen, Labeling falsch (Geisterkanten anderer Ebenen, einseitig sichtbare Holmkante), Spannweite/Pfosten daneben · Ursache benannt, offen.
- 27.11. · Beidseitige Höhenprofile (Minimum beider Kameraseiten) gegen Geisterkanten → ✗ verworfen · echt tauschstabil, aber falsch (Traufe 6,6 statt ~8,5 m, Holm weg: einseitig sichtbare Kanten fallen heraus); Synthetik maß gar nichts mehr · Lehre: Stabilität ist nicht Richtigkeit — Tauschtest braucht Pflichtmaße + Bildvergleich.

- 27.11. abends · Render-Abgleich (`tools/bruecke_render.py`): Gütemaß F1 mit Recall im Modellbereich → ✗ · schmales, kurzes Modell schlägt die Wahrheit (0,54 gegen 0,51).
- 27.11. abends · Gütemaß Summe über Modellpunkte minus Zufallsrate → ✗ · zwei Modellkanten an EINER Fotokante doppelt belohnt (dünne Wand + dickes Dach 141 gegen Wahrheit 113).
- 27.11. abends · Gütemaß „belegte Fotokante (jedes Pixel einmal) − Strafe × Modellkante ohne Fotokante“ → ✓ mit Strafe 0,25 · Strafe 0,5: Flachdach schlägt das echte (gleich helle Flächen ohne Fotokante).
- 27.11. abends · Suche: Koordinaten ab Zonenmitte und CMA-ES über 15 Parameter → ✗ lokale Optima (geschlossener schmaler Gang) · Sweep liefert Kandidaten (Spitzen, Wände, Enden, Pfostenabstand), Render entscheidet Zuordnung (nur Längskanten der Wände), Dach gemeinsam (8 beste Rasterpunkte verfeinert), Pfosten gemeinsam.
- 27.11. abends · Synthetik-Fotos als Kantenzeichnung (Strahltest) → ✗ · Silhouetten an Streifkanten fehlten; jetzt schattiertes Rasterbild + Störlinien vor/hinter der Brücke + Rauschen, LSD im vollen Bild (im halben fehlten Pfostenkanten).
- 27.11. nachts · Zuordnung der Höhenspitzen mit fester Startneigung 40° → ✗ · steiles Dach verdeckt obere Wandkanten, Zuordnung rutscht eine Spitze hoch (Traufe 9,22 statt 8,6); jetzt Maximum über 10°/40°.
- 27.11. nachts · „First nicht belegt (0 Fotos)“ → ✗ Programmfehler, nicht Beleglücke · Belegschlüssel „breite“ ist kein Suchparameter (jetzt ql/qr); Neigung hatte 14/14 Fotos, First 9,94 gegen Wahrheit 9,915.
- 27.11. nachts · Feinsuche Überstand ±0,3 m → ✗ · blieb bei 0,8 (Wahrheit 0,3; Güte bei 0,3 höher, Kurve zweigipflig); jetzt ganzer Bereich. Neu: Messwert nur „gemessen“, wenn die Mehrheit der Fotos mit Kontrast zustimmt (Überstand 5/14 → instabil).
- 27.11. nachts · Straßenkanten (1,78/1,98/2,16 m) als Unterkante → ✗ · jetzt Lichtraum-Veto aus der Wolke: unterste dichte Schicht im Grundrisskern = Deck-Unterseite (echt 4,87–4,93 m, Zone ±30 % stabil), Kandidaten darunter verworfen (Test 8).

## Stand 27.11. (Lauf `/media/oem/rcdaten/tmp/bruecke_baustein/lauf3`)
- Gemessen: Breite Pfostenebenen 3,16–3,20 · Unterkante 5,42 · Laufebene 6,30 (ANNAHME Stirnbrett) · Holm 7,25 · Riegel 8,43 · Traufe 8,78 · First 10,48 (DOM1 10,54) · Pfostenabstand 3,1 m · Spannweite 28 m (DOM1 32,5: Widerspruch, ROT).
- Tauschtest instabil: Traufe, Laufebene, Holm, Riegel, Spannweite; Pfostenzahl am Foto in keinem Foto vollständig bestätigt → Tor ROT.

## Offen
- Treppe am Ende a: Podesttreppe mit Wendung + Betonstützen (Fotos 160254, 160233, 155647) — Baustein kann nur geraden Lauf; Stufenkanten-Sweep fehlt → ROT.
- Stützen unter dem Deck: Kandidaten nur am Turmende, Querschnitt nicht gemessen → ROT. Ende b (Hang/Widerlager) nicht als Gelände-Auflager modelliert.
- Pfostenbreite, Wand-/Dachdicke = Druck-Mindestmaß (ANNAHME); Gegenseite (q > 0) hat wenige Fotos → Fotoauftrag A5 der Recherche.

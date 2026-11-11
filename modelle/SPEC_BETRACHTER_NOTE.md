# SPEC Betrachter-Note (Nutzer 11.11. ~19:05: "ehrlicheres Mass, das in Prozent angibt, was ein normaler Miniatur-Wunderland-Besucher sehen kann,
# bzw. ein Experte - eine Zahl, mit der wir gegen 100 % kommen koennen, sonst sind wir frustriert")

## Warum
Realitaet (Foto) misst Kantenuebereinstimmung; Decke ~85 % (Farbkanten, Schatten, Moos, Glasmuster), kleine Teile wiegen wie grosse, Glaettung 0,18 m.
Sie kann nie 100 % erreichen und sagt nicht, was ein Betrachter sieht. Gebraucht: eine Zahl, die 100 % erreichen KANN, wenn das Modell fuer das Auge stimmt.

## Was
Merkmalsliste je Objekt `modelle/<objekt>/merkmale.json` (generisch, erzeugt + gepflegt, kein Code mit Objektnamen):
- Merkmal = sichtbares Element (Teil, Ornament, Figur, Fenster, Speier, Dachdeckung, ...), Quelle: Bauteilliste (objekt.json), Nutzer-/Agentenfunde
  (masstabelle beobachtungen_offen) und Feinsuche-Cluster (SPEC_FEINSUCHE). Felder: id, teil, groesse_m (kleinste Abmessung), anzahl (Zaehlung am Foto),
  sichtbarkeit (Anteil Fotos, in denen es sichtbar ist), status 0 fehlt / 0,5 grob da (Form oder Lage falsch) / 1 stimmt, beleg (Runde/Pruefer/Render-Bild).
- Zwei Stufen nach Betrachtungsabstand in H0 (1:87): **Besucher** (Abstand ~1 m -> ~87 m real; Auge ~1 Bogenminute -> sichtbar ab ~0,25 m real) und
  **Experte** (~0,3 m -> ~26 m real -> ab ~0,08 m real). Merkmal zaehlt in einer Stufe, wenn groesse_m >= Schwelle (ANNAHME Sehschaerfe, als Parameter).
- Gewicht = sichtbare Flaeche im Mittel der Fotos (aus teil_fotoform Pixelzahlen) ^0,5 (grosse Teile wichtiger, aber Details nicht null).
- **Betrachter-Note** = Summe(Gewicht x status) / Summe(Gewicht) je Stufe, in %. 100 % = jedes sichtbare Merkmal stimmt.
- Status-Quelle (ehrlich, nicht schoenrechnen): 1 nur mit Beleg (angenommene Kreis-Runde mit Formfund-/Bildpruefer 'besteht' ODER Nutzer-Abnahme);
  0,5 = Teil vorhanden aber offener Fund dazu; 0 = Fund 'fehlt' offen. Neue Feinsuche-Funde VERGROESSERN den Nenner (Note kann fallen - im Bericht als
  "neu entdeckt" getrennt ausweisen, damit Fortschritt und neue Entdeckungen nicht vermischt werden).
- `tools/betrachter_note.py <objekt>`: erzeugt/aktualisiert merkmale.json aus den Quellen, gibt beide Noten + Liste der groessten fehlenden Gewichte aus;
  in `tools/realitaet_prozent.py` als weitere Zeile; im Viewer als Ebene (Merkmale farbig nach status).

## Beweis
- Synthetisch: Merkmalsliste mit bekannten Status -> erwartete Note exakt.
- Echt kaufhaus_grob3: Liste ansehen, je Stufe Top-10 fehlende Merkmale nennen; Plausibilitaet gegen Nutzer-Eindruck ("sieht schon geil aus").
- Kein Merkmal mit status 1 ohne Beleg-Pfad.

## Nicht
Keine Tor-Aenderung (die Note ist Anzeige/Planung, kein Kreis-Tor), keine Generatoraenderung, nichts loeschen.

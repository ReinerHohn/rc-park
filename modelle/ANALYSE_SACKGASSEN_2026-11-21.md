# Analyse: Warum 19.-21.11.2026 in Sackgassen (Auftrag Nutzer 21.11. 09:57)

Auftrag des Nutzers (mehrfach): Der HANDLAUF, der zum guten Schwabentor (`schwab_v3`, 15./16.11., 45 Commits) fuehrte, soll automatisch laufen.

## Gemessen (git log seit 19.11. 00:00, 192 Commits, grobe Stichwort-Einteilung; Job-Logs seit 19.11.)
- Mapper/SfM/Tempo: 66 Commits, 40 Job-Laeufe (26 Mapper-Versuche + 14 FlexGlue), darunter ein 8,4-h-Lauf ohne Seitenpruefung.
- Doku/Skills/Baum: 63 Commits. Hardware/Platte: 13.
- Bau aus Fotokanten (Fenster/Uhr/Tor/Fassade 13, Erker/Ebenen 6): 19 Commits = 10 %.
- Ergebnis: Kette erreicht den Handstand zu 2 von 11 Bauteilen (`audit/hand_vergleich.json`); Martinstor-Suedwand wieder verklebt.

## Ursachen
1. NIE EINE BESTANDSAUFNAHME DES HANDLAUFS. Erst am 21.11. 09:35 wurden die 45 Hand-Commits gelesen. Ohne die Liste "Handschritt -> Kettenstufe" gab es keinen Massstab; jede Teilverbesserung sah wie Fortschritt aus.
2. VORNE OPTIMIERT, HINTEN FEHLT ES. Zwei Tage flossen in Mapper-Tempo und Bildzahl (+30 % Bilder), waehrend die Stufen nach dem SfM (Bauteil finden, messen, bauen) fehlten. Der Engpass war nie das Kameramodell.
3. HAND-ERFOLGE NICHT IN DIE KETTE GEHAENGT. Seitenerkennung/-vereinen (19.11.) blieb Handfolge -> 4. Seitenverwechslung. Gleiches Muster beim Handstand selbst.
4. ERSATZKENNZAHLEN STATT ZIEL. Schleife optimierte "Fotokante an Modellflaeche" (83 -> 97 %), obwohl Tor, Fenster, Turm fehlten. Der Vergleich gegen den Handstand kam erst am 21.11. 01:00 und nur auf Nutzerdruck.
5. NUTZERANSAGEN ZU ENG AUSGEFUEHRT. "Fotokanten" -> nur Kanten auf Wandebenen; "dichte Wolke nur Gegenprobe" -> Wolke auch nicht zum FINDEN von Koerpern genutzt, obwohl der Handstand Treppenturm, Nordwandlage und Relief aus der Wolke hatte.
6. EINZELBAUTEIL STATT METHODE. Eine Nacht am Erker (Hoehenfeld, Katalog-Galerie, Farbflaechen = 3 verworfene Wege), bevor die allgemeine Folge feststand.
7. DER MENSCH IM HANDLAUF TAT ZWEI DINGE, die Kette ersetzte nur eines: (a) BENENNEN ("da ist ein Treppenturm", "Spitzbogen") und (b) PRUEFEN ("passt nicht"). Die Schleife ersetzt (b) teilweise, (a) gar nicht.

## Der Handlauf als Folge (aus den 45 Commits) und Stand in der Kette
- Rahmen lotrecht, Massstab am Laser (DOM1): IN DER KETTE.
- Wandlage an die Wolke gelegt: neu in der Schleife (Wandversatz, 21.11.).
- Relief aus Wolkennetz / feinem Wandbild, Quader mit Fugen: IN DER KETTE (Relief, Feinrelief).
- Oeffnungen (Tor Spitzbogen, Rundbogenfenster, Schlitze) aus Foto-Triangulation: Kette findet 1 von 2 Fenstern, Tor mit falschen Massen. LUECKE: Bogenform und Masse aus Kanten.
- Uhr aus Fotomassen: Kette findet sie (Hoehe 0,7 m anders), ohne Ziffern.
- Galerie/Vordach aus Foto-Triangulation: IN DER KETTE (21.11., passt).
- Treppenturm = Kreisausgleich der dichten Wolke + Schlitze aus der Abwicklung: FEHLT. `wolke_rest.py` findet ihn seit 21.11. (rund, r 1,74 m), Bau fehlt.
- Zeltdach aus 4 gemessenen Traufecken, Ueberstand, Knick; Laterne aus Fotomassen: FEHLT (Wolkenrest findet Ueberstand und Laterne).
- Umgang unter der Traufe, Eckquader, Steinbaender: FEHLT.
- Ostseite aus Fremdfotos (automatisch gewaehltes Foto mit Verdeckung): Stufe 'seiten' holt Fotos, Bau daraus fehlt.

## Folgerung (Reihenfolge der Arbeit)
1. Diese Liste ist der Arbeitsplan; jede Zeile "FEHLT/LUECKE" wird eine Kettenstufe ohne Vorwissen: FINDEN (Wolkenrest + Kantenflecken) -> BENENNEN nach Grobform (rund, Platte, Ring an der Traufe, Oeffnung mit Bogenkante) -> MESSEN aus Fotokanten -> BAUEN mit allgemeinem Bauteil -> ANNEHMEN nur bei Gewinn.
2. Der Handstand ist nur Vergleich von aussen nach jedem Lauf (Nutzer 21.11.), nie Eingang.
3. Kein Mapper-/Tempo-/Hardware-Versuch mehr, solange hinten Stufen fehlen - ausser ein Tor faellt durch (Seitenverklebung Martinstor: laeuft).
4. Jeder Hand-Erfolg sofort in die Kette + Kettenlauf als Beleg.

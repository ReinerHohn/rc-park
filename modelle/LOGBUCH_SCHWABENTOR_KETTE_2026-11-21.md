# Logbuch: Schwabentor von null, Handarbeit in die Kette (20./21.11.2026)

Ziel (Nutzer): „Was wir damals manuell gemacht haben, muss jetzt automatisch laufen“. Maßstab ist der Handstand `schwab_v3`.

Nachspielen:
- Ein Kettenlauf: `tools/gesamtkette.py schwab_auto --ziel schwabentor-1120 --ab bauplan --bis bauplan --dicht-stufe schnell` (über `tools/job_start.sh`).
- Logs: `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-1120<x>.log`.
- Die Kette vergleicht jeden Lauf automatisch mit dem Handstand: `audit/hand_vergleich.json`. Der Verlauf mit dem git-Stand je Lauf steht in `audit/hand_vergleich_verlauf.jsonl`.
- Je Werkzeugänderung gibt es einen Commit; der Commit-Text nennt das Messergebnis.

## Läufe (alle automatisch, ohne Eingriff)
- **1120d/e (20.11., bis 23:00):** Bauplan-Stufen laufen durch, der Körper bleibt ein Quader. Befund: Der Sweep findet den Erker, aber nichts baut ihn („nur Vorschläge“).
- **Werkzeug 20.11. ~23:50:** `vorbauten_bauplan.py` und `bauteile.vorbauten_aus_json` (Höhenfeld). Einmal von Hand geprüft: Erker-Fotokanten am Modell 22 % → 95 % (Kanten-Sweep `kanten_vorbau/`).
- **1120f (00:10–00:21):** Erster Beweis, dass die Kette den Erker selbst baut (meine Testdatei war vorher gelöscht). Sackgassen-Tor grün.
- **1120g (00:21–00:39, ab Stufe fenster):** Uhr gefunden (5,13 m), dazu eine Schein-Uhr im Erkerbild (77 % Kantenstütze). Der Erker war weg: Die Frontstreuung lag bei 0,60 und damit genau an der Schwelle 0,6.
- **Korrektur:** Streuung ≤ 0,8 (Erker 0,5–0,6, Torbogen-Durchblick 1,5) und Uhr-Stütze ≥ 0,85 (echt 98–100 %, Schein 77 %).
- **1120h (00:45):** Erker wieder da, eine Uhr, Konsolenfelder als Nicht-Fenster verworfen.
- **Nutzer:** „Wurstelschrott“ zum Höhenfeld-Erker. Umbau auf `galerie_messen`, das nur die Maße misst; die Gestalt kommt aus `Wand.galerie` wie in schwab_v3. Streben werden im 1-cm-Wandbild gezählt: 6, Abstand 1,56 m.
- **1120i (00:47–00:55):** Die Galerie mit 3 Pfosten, 6 Streben und Vordach kommt aus der Kette selbst. 18 Stufen in Ordnung.
- **Handstand-Vergleich neu (`tools/hand_vergleich.py`, `referenz_hand.json`):** 0 von 11 passen. Das „Vordach“ bei 18,2–19,2 m / +2,3 m war sehr wahrscheinlich die Oberleitung (2 m zu hoch).
- **Korrektur:** Traufe = erstes Band über dem Holm; Dachanschluss aus der Uneinigkeitskarte.
- **1120j (01:05–01:14):** Traufe 16,02 (Soll 16,09), Anschluss 19,39 (Soll 19,43). Weiter 0 von 11, weil in jedem gefundenen Teil ein Maß danebenliegt.

## Sackgassen und Zeitfresser
- Höhenfeld als Gestalt: treppig, keine Pfosten oder Streben. Ersetzt durch Maße plus bewährtes Bauteil.
- Der Kandidat „Dach“ aus dem Sweep, ohne Prüfung, ob er an die Galerie anschließt, war die Oberleitung.
- Fenster-Tor nur mit „vorn ≥ 20 %“: Im Zweitlauf (Galerie im Modell) lagen die Konsolenfelder bei vorn 14 %. Jetzt gilt zusätzlich: hinten < 5 % = keine Nische, und hinter einem gebauten Vorbau = kein Fenster.
- Die 3D-Seite war am Handy unbrauchbar: Kamera auf den Ursprung gerichtet, Modell zu 55 % durchsichtig. Behoben in `modell_3d_html.tpl.html`.
- Von Hand angestoßen (nur Messung, kein Modellteil): Kanten-Sweeps in `kanten_vorbau/` und `kanten_v3/`, Probeläufe der Werkzeuge in der Scratchpad-Ablage.

## Offen (Reihenfolge nach Handstand-Vergleich)
1. Laterne (fehlt)
2. Pfosten 2 statt 3
3. Vordach-Ausladung 1,10 statt 1,54
4. Galerie-Unterkante und Holm je ±0,6 m
5. Uhr-Höhe +0,7 m. Höhenbezug prüfen: Der Torscheitel liegt −0,45 m daneben, also kein einfacher Versatz.
6. Zweites Rundbogenfenster
7. Treppenturm, Umgang, Eckquader, Dachüberstand
8. Durchfahrt: Der Feldseite fehlen Fotos (f01: 4 Fotos, 18 % Abdeckung).

## Nachtrag 01:40 - Lage geprüft: Annahme „Lagekorrektur fehlt“ WIDERLEGT
- Beide Objekte haben denselben Rahmen (`objekt.json` rahmen identisch). schwab_v3 hat seine Rohmaße nachträglich pauschal mit 0,933 skaliert (alte Ausrichtung 7 % zu groß); die Kette von null hat eine eigene Ausrichtung, am Laser geprüft (Höhen-Tor k 0,9991).
- Vordach stimmt zwischen beiden auf 7 und 4 cm (Traufe 16,02 / 16,09, Anschluss 19,39 / 19,43). Also kein Höhenversatz.
- Uhrmitte: Kette 31,95 m (Kreis im Wandbild). Gegenprobe mit triangulierten Fotokanten (Kreis in den Sweep-Punkten, `kanten/` und `kanten_vorbau/`): 32,00 und 31,85 m. Handstand 31,25 m = 33,49 roh x 0,933. Die Kette liegt hier wahrscheinlich richtiger als der Handstand (beide Messungen in derselben Ausrichtung, daher nicht völlig unabhängig).
- Folge: Der Handstand ist kein Sollwert für Höhen auf ±0,3 m; `hand_vergleich` zeigt zuverlässig nur FEHLT und grobe Abweichungen.
- Echte Messschwäche der Kette: Bänder aus dem Sweep sind durch Raster und Glättung um etwa ±0,3 m verbreitert (Galerie 9,6–12,0 statt 10,2–11,4). Abhilfe (allgemein): Kanten des Bauteils auf seiner EIGENEN Ebene aus den Fotos triangulieren, wie von Hand mit foto_mass.
- Nutzer 01:38: „es geht darum, eine generelle Methode zu finden“.

## Nachtrag 01:55 - Nutzerkorrektur: KEIN Baukasten, Form aus dem feinen Wandbild
- Nutzer: „Nein, nicht aus dem Baukasten. Du musst mit dem feinen Raster aus dem Bauplan die Kanten erkennen.“ Das ist die harte Regel „Wandbild = Bauplan, keine Musterteile“. Mein Verstoß in dieser Nacht: `galerie_messen` -> `Wand.galerie` (Katalog-Galerie mit gemessenen Maßen) und `uhren_aus_json` mit `Wand.zifferblatt` (fertige Ziffern). Beides kommt wieder heraus.
- Vorhandenes Werkzeug dafür: `tools/form_aus_wandbild.py` (17.11.; Wandbild auf beliebiger Ebene `--w`, Segmentierung, Kanten einrasten, `teil()`), bisher nur von Hand am Kaufhaus, keine Kettenstufe.

## METHODE (Stand 21.11., wird hier fortgeschrieben)
Ein Gebäude = mehrere EBENEN, jede Ebene bekommt ihren eigenen Bauplan.
1. Grundebenen = Wände des Grundkörpers (Kameras aus SfM, Lage geprüft).
2. Ebenen-Sweep je Wand: Wo werden die Fotos erst vor oder hinter der Wand deckungsgleich? -> neue Ebenen (Vorbau +w, Nische/Öffnung -w) mit Zone.
3. Je gefundener Ebene ein feines Wandbild (1 cm) AUF DIESER EBENE aus den Fotos (dort ist das Teil scharf, auf der Wandebene verschmiert).
4. Gestalt aus diesem Bild: Kanten/Flächen + Tiefe je Zelle -> Form. Erkenner liefern nur Zonen, nie die Form. Kein Katalogteil.
5. Bauen, dann das Wandbild der Grundebene mit dem neuen Körper neu rechnen (Verdeckung stimmt jetzt) und ab Schritt 2 wiederholen, bis nichts Neues kommt.
6. Beweis je Lauf: Fotokanten am Modell (Anteil ≤ 15 cm), automatisch.
Offene Grenze: wirklich Freistehendes mit Luft dahinter (schräge Streben, offene Brüstung) hat auf einer Ebene Parallaxe -> Fotokanten aus mehreren Ansichten (ANNAHME, am Erker noch nicht geprüft).

Was daran neu ist (ehrlich): die Einzelteile gab es alle (Sweep 16.11., Wandbild auf Ebene 17.11., Form aus Wandbild 17.11.). Neu ist nur die Kopplung als Schleife in der Kette: Sweep-Ebene -> eigenes Wandbild -> Form -> Bau -> neu rechnen. Neu seit heute Nacht außerdem: Sackgassen-Tor, Vergleich mit dem Handstand, Verlauf je Lauf.

## Nachtrag 01:50 - Probe Schritt 3 der Methode (von Hand angestoßen, nur Bild, kein Modellteil)
- `form_aus_wandbild.wandbild_fotos` für die Zone f00 u -4,3..5,5 / z 8,3..16,6, 1 cm, 5 beste Fotos; einmal auf der Wandebene (w -0,15), einmal auf der Erkerfront (w +1,0). Bild: `audit/erker_ebenen_probe.jpg`.
- Beide Bilder sind scharf (die 5 besten Fotos stehen nah beieinander), aber auf der Wandebene liegt die Brüstung etwa 0,3 m zu hoch (Parallaxe). Auf der Erkerebene mit dem Auge abgelesen: Holm oben ≈ 11,5 m, Schwelle unten ≈ 10,35 m. Handstand: 11,42 / 10,22. Also trifft das feine Bild auf der eigenen Ebene den Handstand auf etwa 0,1 m (abgelesen, nicht mit Werkzeug gemessen).
- Pfosten (3), Knaggen, Riegel, 6 Streben und Konsolen sind im Bild einzeln erkennbar -> Form daraus lesbar. Störer: Oberleitungsdrähte quer durchs Bild.
- Nächster Schritt: diese Rechnung als Kettenstufe (Ebene aus `vorbauten_auto.json`), dann `gestalt()` darauf, Katalog-Galerie entfernen.

## Rückfälle dieser Nacht (vermeidbar, keine Werkzeuglehre)
1. Falsche Reihenfolge: Einzelteile repariert, statt zuerst Kette und Handstand zu vergleichen (~3 h).
2. Katalog-Galerie und Katalog-Ziffern gegen die Regel „Form aus dem Wandbild“ (seit 17.11.).
3. Um 00:50 ein von Hand erzeugtes Modell gezeigt statt eines Kettenlaufs.
4. Kaufhaus-Gegenprobe begonnen, obwohl das Schwabentor nicht fertig war.
5. Schwellen an einem Bauwerk eingestellt (Streuung 0,6 lag genau auf dem Messwert).

## Nachtrag ~01:53 (Uhrzeit berichtigt, stand falsch als 02:40) - Form aus dem Bild der Erkerebene: zwei Proben (von Hand angestoßen, noch KEINE Kettenstufe)
- **Probe A, Farbflächen + Sweep-Tiefe je Fläche** (`tools/ebenen_form.py`, erste Fassung; Bild `audit/ebenen_form.jpg`): Brüstung und Konsolen werden als Front erkannt, die Ränder sind aber ausgefranst. Fehler: die drei Pfosten fehlen (hängen farblich am dunklen Dachschatten, die geglättete Sweep-Tiefe sagt dort „Wand“), ein Stück des Wandbilds gilt fälschlich als Front (dort kreuzen die Oberleitungsdrähte, der Sweep misst die Drähte). Feine Sweep-Tiefe mit 2-cm-Zellen (`bauplan/tiefe_fein`) ist je Zelle zu verrauscht für eine Maske. URSACHE benannt: Farbklassen trennen Material nicht sauber, die Sweep-Tiefe löst unter ~0,4 m nicht auf.
- **Probe B, triangulierte Fotokanten auf das Bild gelegt** (`kanten_vorbau/sweep.npz`, Bild `audit/erker_kantenpunkte_probe.jpg`): 7847 Kantenpunkte in Fronttiefe. Sie zeichnen den Holm (z ≈ 11,50) und die Unterkante der Brüstung samt den Aussparungen der Konsolen (z ≈ 10,25) auf wenige cm genau nach (Handstand 11,42 / 10,22). Kantenpunkte in Wandtiefe liegen an den Strebenfüßen. Senkrechte Kanten (Pfosten) fehlen fast ganz. ANNAHME zur Ursache: die Kameras stehen entlang der Straßenachse, das gibt Parallaxe in der Höhe, kaum seitlich; außerdem suchte der Sweep nur im 0,5-m-Band um das alte Modell mit begrenzter Punktzahl.
- **Folgerung für die METHODE (Schritt 4 präzisiert):** Die Kanten kommen aus den triangulierten Fotokanten auf der Ebene (Kernmethode), nicht aus Farbflächen. Farbflächen taugen höchstens zum Füllen zwischen belegten Kanten.
- Nächste Schritte: (1) Kanten-Sweep gezielt und dicht je gefundener Ebene (Box = Zone der Ebene). (2) Bänder (Brüstungskasten, Traufband) mit diesen Kanten begrenzen statt mit dem groben Raster. (3) Stäbe/Pfosten über den Mehrfoto-Sweep für Linien (Skill linien-features), nicht über Helligkeit. (4) Dann Kettenstufe und Katalog-Galerie entfernen.

## ENTSCHEIDUNG Nutzer 21.11. ~01:55 (berichtigt)
„So wenig allgemeine Bauteile wie möglich. Untersuche, wie weit du aus Kanten triangulieren kannst, und was nicht möglich ist, wird aus allgemeinen Bauteilen gebaut. Durch das Kantenerkennen müssen wir umso genauer werden mit Maßen.“
Befund dazu: Die Galerie in schwab_v3 war selbst ein Baukastenteil (`Wand.galerie`, 16.11.) mit 4 von Hand in 3 Fotos angeklickten, triangulierten Punkten (M-113231-001: Unsicherheit 0,38 m), Stückzahlen am Foto gezählt.

## Nachtrag ~01:58 (berichtigt, stand falsch als 03:15) - UNTERSUCHUNG: Wie weit trägt die Kanten-Triangulation auf einer Sweep-Ebene? (Erker f00, von Hand angestoßen)
Aufruf (nachspielbar): Ebene als Fläche `kanten_ebene_f00/ebene.stl` (Rechteck u -4,6..5,8 / z 8,0..20,8 bei w +0,9), dann
`kanten_tiefe_sweep_flaeche.py kanten/kam_wahl.json kanten/stabil kanten_ebene_f00/sweep.npz --flaeche ebene.stl --flaeche_skala 1.0 --box3 <box.txt> --band 1.6 --ziel_auto --nbdist 80 --refs 80 --nb 12 --maxpx 150000`. Laufzeit wenige Minuten (GPU). 54 463 Kantenpunkte in der Zone (vorher 13 041 aus dem Gesamtlauf). Bild `audit/erker_kanten_dicht_probe.jpg`.
GEHT (Handstand in Klammern):
- Unterkante der Brüstung z 10,23 (10,22), Holm z 11,51 (11,42), zweite Kante am Holm 11,29, Konsolen-Unterkante 9,99.
- Breite an der Unterkante 8,35 m (8,06; grobes Raster vorher 9,08).
- Ausladung der Front 1,29 m vor der Wand, p10..p90 1,05..1,35 (1,45 bei 0,38 m Unsicherheit des Handpunkts).
- 6 Konsolen gezählt mit Lage (u -3,6 / -2,05 / -0,5 / 1,05 / 2,65 / 4,2; Abstand ~1,55 m) (Hand: 6 Streben).
- Streben laufen schräg zur Wand: Tiefe 1,28 m bei z 9,7-10,1, 0,32 m bei z 8,9-9,3, 0,14 m bei z 8,5-8,9.
GEHT NUR TEILWEISE:
- Pfosten: alle 3 gefunden (u -3,5 / 0,09..0,39 / 4,08..4,27), aber nur 109-217 Punkte und nur Teilstücke der Höhe; Breite nur am mittleren ablesbar (0,30 m).
GEHT NICHT:
- Vordach: fast keine Punkte (Traufkante z 16,19 mit 189 Punkten, Dachfläche nichts - Ziegel geben keine stabilen Kanten).
- Stärke der Hölzer nach hinten, Knaggenform.
ANNAHME zur Ursache der schwachen senkrechten Kanten: Kamerastandorte liegen entlang der Straßenachse (Parallaxe vor allem in der Höhe). Nicht geprüft.
Folgerung nach Nutzerentscheidung: Brüstungskasten, Konsolen/Streben (Zahl, Lage, Neigung) und Breite/Ausladung aus Kanten bauen; Pfosten: Lage aus Kanten, Querschnitt Bauteil-Standard; Vordach: allgemeines Bauteil mit Traufe/Anschluss aus der Uneinigkeitskarte.

## LEITBILD Nutzer 21.11. ~02:00 (berichtigt) (gilt für die METHODE oben)
„Das, was ich damals von Hand gemacht habe, wo ich dir gesagt habe, was noch nicht passt, das muss jetzt automatisch laufen. Du musst mich ersetzen durch eine automatische Bauplanabweichung, Fotokantenabweichung, die Tiefen sweepen und mehrere Baupläne auf mehrere Ebenen machen und dort die Abweichungen mit diesen Bauplänen abgleichen.“
Umsetzung als SCHLEIFE (ersetzt den Nutzer als Prüfer):
1. Ebenen finden (Tiefen-Sweep je Wand) und je Ebene einen Bauplan rechnen (feines Bild + dichte triangulierte Fotokanten auf dieser Ebene).
2. Modell bauen (Kanten -> Maße/Form; nur was Kanten nicht hergeben, aus allgemeinem Bauteil).
3. ABWEICHUNG je Ebene messen, mit Ort: (a) Fotokanten ohne Modellkante = fehlt/falsche Lage, (b) Modellkanten ohne Fotokante = erfunden, (c) Modell auf der Ebene gegen das Bauplanbild.
4. Abweichungsliste = Arbeitsliste (größte zuerst) -> zurück zu 2, bis die Abweichung unter der Schwelle liegt oder nichts mehr besser wird; Rest wird als offen gemeldet.
Vorhanden als Bausteine: `kantenstufe.py` (fehlende_kanten_haufen), `foto_diff.py`, `aenderung_check.py`, `teil_fotoform.py`. Fehlt: die Auswertung JE EBENE und die Rückführung in den Bau.

## Nachtrag 02:05 - Schritt 1 der Schleife als Werkzeug: `tools/ebenen_bauplan.py` (Job `ebenen-schwabentor`, Log job_logs/ebenen-schwabentor-1121.log)
Dichte triangulierte Fotokanten je Ebene, Laufzeit 4-6 s je Ebene (GPU), neben dem Martinstor-Mapper:
- f00_wand (Stadtseite, w -0,15): 56 768 Punkte, 76 % auf der Ebene (±15 cm)
- f03_wand (w +0,05): 93 211 Punkte, 84 %
- f02_wand: nur 2 464 Punkte, 64 % (wenige brauchbare Fotos, Baum davor)
- f00_vb0 (Erkerfront, w +1,00, Band 0,8): 46 782 Punkte, 62 %
- f01 (Feldseite) keine Ebene: nur 4 Fotos (< 6).
Ausgabe `<daten>/ebenen/ebenen.json` + je Ebene `sweep.npz`, für den Vorbau zusätzlich `bild.png` (1 cm). Noch nicht in `gesamtkette.py` eingehängt; nächster Schritt `ebenen_abweichung.py`.

## Nachtrag 02:20 - ERSTER VOLLER DURCHLAUF DER SCHLEIFE in der Kette (Lauf 1121k, 02:06-02:16, 22 Stufen in Ordnung, ohne Eingriff)
Neue Werkzeuge, alle in Stufe `bauplan` eingehängt: `ebenen_bauplan.py` (Kanten je Ebene) -> `ebenen_masse.py` (Maße aus Kanten) -> Bau (`bauteile.vorbauten_aus_json`, Zweig kanten_mass) -> `ebenen_abweichung.py` (Abweichung je Ebene mit Ort und Bild, Verlauf `audit/ebenen_abweichung_verlauf.jsonl`).
Die Kette hat am Erker selbst gemessen: Kasten z 10,23..11,47 (Hand 10,22 / 11,42), Breite 8,30 (8,06), Ausladung 1,29 (1,45 ± 0,38), 6 Konsolen im Abstand 1,55 m, Strebenfuß z 8,38 (unsicher, nicht gegengeprüft), 3 Pfosten bei u -3,51 / 0,32 / 4,19.
ABWEICHUNG vorher (Katalog-Galerie mit Grobmaßen) -> nachher (aus Kanten):
- Erkerebene f00_vb0: Fotokanten an der Modellfläche 63 % -> 91 %, an einer Modellkante 7 % -> 87 %, erfundene Modellkanten 94 % -> 75 %.
- Stadtseite Wandebene: Kante 42 % -> 50 %. Nord und Süd unverändert (91 / 45 % und 85 / 23 %).
- Gesamt (195 913 Fotokanten, 4 Ebenen): Fläche 82 % -> 88 %, Kante 35 % -> 56 %.
Bild: `audit/abweichung_f00_vb0_vergleich.jpg`. Handstand-Vergleich: Galerie PASST, Vordach PASST (dabei ist der Dachüberstand 0,25 m eine ANNAHME; gemessen sind Traufe und Anschluss) -> 2 von 11.
Arbeitsliste, die die Kette jetzt selbst schreibt (Erkerebene, „Form fehlt“): 1. zweite Kante am Holm z 11,0-11,7 rechts, 0,11 m hinter der Front (2330 Punkte); 2. dieselbe links (800); 3. Traufecke links z 16,1-16,3 (538).
Noch NICHT automatisch: der Rückweg von der Arbeitsliste in den Bau (Schritt 4) - die Liste wird geschrieben, aber noch nicht abgearbeitet.
Grenze der Kennzahl „erfunden“: 75-94 % der Modellkanten ohne Fotokante - das Relief der Wände erzeugt sehr viele kleine Modellkanten; so ist die Zahl nicht als Güte lesbar (offen: nur Kanten > 0,3 m Länge zählen).
Katalog entfernt: `Wand.galerie` nur noch mit MIT_KATALOG_GALERIE=1, Uhr ohne Katalog-Ziffern (nur gemessene Kreise).

## Nachtrag ~02:22 - Gegenprobe DICHTE WOLKE in der Abweichungsstufe (Nutzer: „wo ist die dichte Wolke, dass man abgleichen kann, dass die erzeugten Formen grob passen?“)
Wolke: `modelle/schwabentor-1120/sfm/punkte_modell_schwabentor-1120.npy` (7,85 Mio. Punkte, Modellrahmen). `ebenen_abweichung.py --wolke` (in der Kette eingehängt): je Ebene Anteil der Wolkenpunkte an der Modellfläche (≤ 15 cm) und Flecken > 0,3 m daneben.
- Erkerbereich allein (1,31 Mio. Punkte): Quader 42 % -> Höhenfeld-Erker 60 % -> Erker aus Kanten 66 % an der Fläche (≤ 30 cm: 79 %). Wolke bestätigt die Kantenmaße: Fronttiefe 1,2-1,3 m, Front belegt bei z 10,1-10,5 / 11,2-11,5 / 15,8-16,1.
- Je Ebene: Stadtseite Wand 71 % (12 % grob daneben), Nord 91 % (4 %), Süd 51 % (29 %), Erkerebene 74 % (16 %).
- Größte Wolkenflecken ohne Modell: Erker u -4,5..4,0 / z 8,2..17,7 rund 0,5 m VOR der Erkerfront (ANNAHME: geschweiftes Vordach mit Überstand und Streben - genau das, was die Kanten nicht messen konnten); Stadtseite z 0..6,8 bei -0,77 m (Tordurchfahrt); Süd mehrere Flecken +0,35..0,6 m (ANNAHME: Baum/Strebepfeiler).
Lehre: Kanten messen genau, sind aber an glatten/gekachelten Flächen blind; die Wolke zeigt grob, WO dort Form fehlt. Beide zusammen ergeben die Arbeitsliste.

## KONVERGIERENDE SCHLEIFE (Nutzer 02:28: „wir brauchen eine konvergierende Loop“) - Regeln
1. Kennzahl je Ebene = Fotokanten an Modellkante (genau) + Wolke an Modellfläche (grob). Ein Umbau wird nur ANGENOMMEN, wenn die Kennzahl seiner Ebene steigt und keine andere Ebene um mehr als 1 %-Punkt fällt; sonst verworfen (mit Grund im Verlauf).
2. Je Runde der größte offene Fleck der Arbeitsliste. Ein Fleck, der zweimal ohne Gewinn bearbeitet wurde, wird „offen“ gemeldet (Fotolücke oder Methode fehlt), nicht endlos wiederholt.
3. Ende: kein Fleck über der Mindestgröße ODER zwei Runden ohne Gewinn ODER Rundengrenze. Verlauf je Runde in `audit/ebenen_abweichung_verlauf.jsonl`.

## Nachtrag 02:30 (abgelesen) - Nutzer: keine dichte Wolke um ihrer selbst willen; Ebenen in ALLE Richtungen (auch von der Seite)
- Kein „fein“-Lauf der dichten Wolke gestartet (Nutzer: Verbesserung nur für Geschwindigkeit; Ziel sind Modellkanten, Maße, Bauplan). Wolke bleibt grobe Gegenprobe.
- `ebenen_bauplan.py --seiten 1` (Standard): je Vorbau zwei Seitenebenen senkrecht zur Wand (Achse = Tiefe ab Fassadenebene, Normale ∓d). Probe Erker (`ebenen_seitentest/`, Bild `audit/erker_seitenriss_probe.jpg`):
  - Echte Seitenebenen: nur 1710 / 1838 Kantenpunkte (16 % / 59 % auf der Ebene). URSACHE: die Fotos der Stadtseite schauen frontal die Straße entlang, die Seitenflächen des Erkers sieht kaum eine Kamera.
  - Aber: Die Kantenpunkte sind 3D. Der SEITENRISS aller Kantenpunkte des Erkers (Tiefe gegen Höhe) zeigt, was die Frontansicht nicht hergibt: Streben verlassen die Wand bei z ≈ 8,4 und laufen schräg nach vorn (bei z ≈ 9,4 etwa 0,5 m vor der Wand); Pfosten stehen auf der Frontlinie (z 14,1-15,5); Traufkante liegt bei z ≈ 15,9-16,6 etwa 0,3 m VOR der Front (Dachüberstand messbar, bisher ANNAHME 0,25).
  - Dachfläche weiterhin ohne Kanten.
- Folgerung für die METHODE: „Ebenen in alle Richtungen“ = (a) Sweep-Ebenen auch senkrecht zur Wand, wo Kameras sie sehen, (b) immer zusätzlich Seitenriss und Grundriss der 3D-Kantenpunkte auswerten. Fotos von der Seite (schräg auf den Erker) würden die Seitenebenen füllen -> Fotoauftrag.

## Nachtrag 02:33 (abgelesen) - SCHICHTSTAPEL (Nutzer: „geht auf der GPU sehr schnell ... auf ganz vielen, aus allen Winkeln machen und so einen sehr detaillierten Bauplan“)
`ebenen_bauplan.py --stapel -1.05 2.85 0.3 --nur 'f00_s*' --seiten 0` -> `ebenen_stapeltest/` (von Hand angestoßen): 14 dünne Ebenen parallel zur Stadtseite, Band ±0,15 m, je 4-6 s.
Kantenpunkte je Schicht (Tiefe gegen die Wand) und Gegenprobe „dichte Wolke ≤ 10 cm daneben“:
- -0,15 m: 30 459 Punkte, 98 % | +0,15 m: 24 988, 95 %   -> die Wand
- +1,05 m: 4 823, 96 % | +1,35 m: 17 385, 99 %           -> Erkerfront (Höhen 10,0-11,5)
- +1,65 m: 2 896, 80 %, Schwerpunkt z 16,1-16,3           -> Traufkante des Vordachs, ~0,35 m vor der Erkerfront
- -0,45 m: 5 211, 66 % (z 25-36, ANNAHME: Rücksprung/Umgang oben) | +0,45 m: 4 055, 69 % | +0,75 m: 1 113, 42 %
- ab +1,95 m: je 400-770 Punkte, 0-4 % von der Wolke bestätigt -> Scheintreffer (ANNAHME: Drähte, Mehrdeutigkeit)
- -0,75 / -1,05 m: 340 / 486 Punkte, 26-33 % -> schwach.
Summe 94 233 Punkte (nicht mehr als die zwei breiten Läufe zusammen, 103 000) - der Stapel bringt nicht mehr Punkte, aber er FINDET die Ebenen selbst (Spitzen der Punktzahl) und die Wolke trennt echte Schichten (≥ 80 % bestätigt) von Scheintreffern (≤ 4 %).
Regel-Vorschlag: Schicht gilt als Ebene, wenn Punktzahl ≥ 2 % der stärksten Schicht UND Wolkenbestätigung ≥ 80 %; 40-80 % = prüfen (Teilfläche), darunter verwerfen.
Grenze ist nicht die Rechenzeit, sondern die Kamerasicht (Seitenebenen des Erkers: nur ~1700 Punkte).

## Nachtrag 21.11. 09:44 - Martinstor: schrittweiser Mapper "eng" fertig, Suedseite VERKLEBT
- Lauf `rcpark-mt_inkr_eng2` fertig 05:18 (30 382 s): 4 Modelle, groesstes 983 von 1156 Bildern, 148 794 Punkte, `modell_zerlegen`: EIN Stueck (980).
- Seitenpruefung gegen die getrennten Bezugsmodelle vom 19.11. (`/media/oem/rcdaten/tmp/mt_seiten/dicht_sued_r9` 74 Bilder, `dicht_nord2` 384): im Hauptmodell stehen 51 Sued- und 293 Nord-Bilder,
  aber am SELBEN Ort mit GLEICHER Blickrichtung (Median-Ort 0,9 Einheiten auseinander, mittlere Blickrichtung 12 Grad statt ~180) -> Sued-Bilder auf die Nordwand geklebt (Seitenverwechslung, 4. Mal).
  `modell_zerlegen` merkt das nicht (ein Stueck). Der schrittweise Mapper ist am Martinstor also KEIN Ausweg; guter Stand bleibt 19.11.: Seiten getrennt rechnen (Sued 74 / Nord 384), dann vereinen.
- Die zwei Vergleichslaeufe (`mt_eng_varianten_1120.sh`) sind NICHT gelaufen (Warter nicht mehr aktiv, Ordner `allein` fehlt).
- Berichtigung: die Schleife (Lauf 2) endete 03:38 (Zeit der Logdatei), nicht 09:27.
- Neu: `tools/wolke_rest.py` (Rest der dichten Wolke am Modell als Haufen): Schwabentor 67 % der Wolke am Modell; Treppenturm als "rund" r 1,74 m, Dachueberstand, Laterne, zwei Fensternischen ohne Vorwissen gefunden.
- Handstand schwab_v3 (45 Commits 15./16.11.) kam aus: Bauteil vom Nutzer benannt -> allgemeines Bauteil, Masse aus Foto-Triangulation, Koerper aus der dichten Wolke (Treppenturm Kreisausgleich, Nordwand an Wolke, Relief aus Netz).

## Nachtrag 21.11. ab 09:50 - Seitenfolge in die Kette (Martinstor, Beweis an vorhandenen Daten)
- URSACHE des Rueckfalls: `seiten_erkennen.py` + `seiten_vereinen.py` (19.11.) wurden nie in `gesamtkette.py`/`iphone_sfm.py` aufgerufen; Kette hat nur Hinweis-Tore (Zerfall: merkt Verklebung nicht; GPS: Martinstor ohne GPS) und den Seitenfilter (wirft die fremde Seite weg statt sie getrennt zu rechnen). LEHRE: ein Handablauf, der zum guten Stand fuehrt, gilt erst als erledigt, wenn er in der Kette aufgerufen wird (wie Sackgassen-Tor: Werkzeug ohne Aufrufer = Fehler).
- FlexGlue (Logbuch 19./20.11.): trennt die Seiten NICHT besser (alle 4 Varianten gleich), bringt +30/+40 % Bilder; automatisches Vereinen aus GLOBALEN Stuecken scheiterte (Achsen 14-20 % uneinig), gelang nur mit schrittweise gerechneten Seiten + dichter Wolke.
- PLAN (Nutzer: "mach das unbedingt, beweise es"; Beweis zuerst an vorhandenen Daten, Kette von null spaeter): 1 Seiten erkennen (--streng) -> 2 je Seite schrittweise -> 3 dichte Wolke je Seite -> 4 vereinen -> 5 hartes Tor (getrennte Seiten duerfen nicht am selben Ort gleich blicken).
- 09:50 Job `seiten-martinstor-1121` rc 127: Befehl als EIN String an job_start.sh uebergeben (Rueckfall; job_start will BEFEHL als einzelne Argumente). 09:51 neu als `seiten-martinstor-1121b` (DB martinstor-1120, Ausgabe /media/oem/rcdaten/tmp/mt_seiten_1121/).

## Nachtrag 21.11. 10:05 - Treppenturm automatisch aus dem Wolkenrest (erste Zeile "FEHLT" der Analyse)
- `wolke_rest.py`: fuer runde Haufen DREHPROFIL r(z) in 0,25-m-Scheiben (dichteste Schale je Scheibe); `--uebernehmen` legt sie dauerhaft in `audit/koerper_auto.json` (nach dem Bau verschwindet der Haufen aus dem Rest).
- `bauteile.drehkoerper_aus_wolkenrest` (Generator + Vorlage): Kegelstuempfe aus dem Profil. Schwabentor: Achse x 1,80 y 22,80, Schaft r 1,73 m, Gesims r 1,88 bei z 11,4, Ende z 12,0.
- Messung: Wolke an der Modellflaeche 67 % -> 70 %, Haufen am Turm verschwunden (Bild audit/wolke_rest.jpg). Schnelltest 0 Fehler.
- Von aussen verglichen: Handstand Schaft 1,56 / Gesims 1,85 bei 11,57 -> Gesims passt, Schaftradius 0,17 m groesser (offen: Wolkenrauschen nach aussen oder Massstab).
- OFFEN: Haube fehlt (Wolke hat ueber z 11,6 nur 45-65 Punkte je Scheibe), Oeffnungen (Abwicklung `fassade_zylinder.py` nicht in der Kette), Koerper voll statt hohl, noch nicht im Treiber der Schleife (Annahmeregel), Abnahme nicht gelaufen.

## Nachtrag 21.11. 10:25 - Martinstor Seitenerkennung fertig (10:19, rc 3): Seiten NICHT getrennt - Ursache gefunden: PERSON als Bruecke
- `seiten_erkennen --streng` auf der DB martinstor-1120 (2107 Bilder, 2895 Pruefpaare, 29 min GPU): 170 Gruppen, 1339 fremde Bilder, 724 549 Paare geloescht; aber Teil 0 = 750 Bilder mit Sued 52 UND Nord 203 (Bezug: Seitenmodelle 19.11.).
- Die Gruppen selbst sind REIN (Sued: 2 und 13; Nord: 0, 5, 9, 11, 12, 15, 16, 27, 28, 29, 38). Alle direkten Sued<->Nord-Verbindungen = 'verwechselt' (richtig). Die Bruecke ist Gruppe 36 (18 Bilder `fotos__vf_*`):
  'echt' zu Sued-Gruppe 2 (66 Paare, 54 % eindeutig gleich) UND zu Nord-Gruppe 0 (26 Paare, 42 %). Kontaktbogen angesehen: Selbstaufnahme-Videobilder, eine PERSON fuellt das halbe Bild, auf beiden Torseiten.
  Die Zuordnungen und der Paar-Pruefer sehen dieselbe Person -> "gleiches Motiv" -> Seiten haengen ueber den Vordergrund zusammen. Das erklaert auch das verklebte Ergebnis des schrittweisen Mappers.
- Nebenbefund: 162 Nord-Bezugsbilder stehen unter 'fremd'.
- WIEDER DASSELBE MUSTER: `tools/handy_masken.py` / `video_masken.py` (Masken fuer Personen/Fahrzeuge) gibt es, `iphone_sfm.py` uebergibt aber kein mask_path -> nicht in der Kette.
- 10:22 Job `masken-martinstor-1121` (Batch 4): OOM-Rueckfaelle auf der 8-GB-Karte -> gestoppt, 10:24 neu als `...1121b` mit Batch 2. Danach: Merkmale in den Masken aus den Paaren nehmen, Seitenerkennung neu, Erwartung: Teil 0 zerfaellt in Sued und Nord.

## Nachtrag 21.11. 10:40 - Dach als Schichtprofil der Wolke (Schwabentor) + Maskenfilter (Martinstor)
- NEU `tools/dach_profil_wolke.py` -> `audit/dach_profil.json` -> `bauteile.dach_aus_profil` (Generator + Vorlage): je 0,5-m-Scheibe das Rechteck der Wolke im Fassadenrahmen, je SEITE getrennt; Modell ueber dem Dachbeginn abgetragen.
  Fassung 1 (Perzentile ueber alle Punkte): Sued-Dachflaeche fehlt in der Wolke -> Profil wanderte auf die Nordflaeche. Fassung 2 (je Seite, 97. Perzentil): Rauschen blaehte das Dach auf, Dachlinie der Wolke lag IM Modell, Kennzahl fiel -> nach der Annahmeregel VERWORFEN.
  Fassung 3 (aeusserste dichte Schale je Seite; Seite ohne Wolke an der gemessenen Achse gespiegelt = ANNAHME, 18 von 104 Scheibenseiten): Dachbeginn z 37,0, Ueberstand, Neigung ~52 Grad, Laternenkoerper bis z 50,0; Haufen am Dach (3098 Punkte) verschwunden.
- Messung auf gleicher Basis (935 436 Wolkenpunkte im alten Kasten): an der Modellflaeche 625 356 (Stand nach der Schleife) -> 653 817 mit Treppenturm + Dach (+28 461; Prozentwerte sind zwischen Bauten nicht vergleichbar, weil der Kasten mit dem Modell waechst - `wolke_rest` gibt jetzt die Anzahl aus).
- OFFEN Dach: Stufen statt glatter Flaeche, Spitze/Knauf ueber z 50 fehlt (Modell vorher 50,7), Traufzone z 37-39 unruhig, Sued-Dachflaeche ungesehen (Fotoauftrag), Kantenkennzahlen und Abnahme nicht neu gelaufen.
- Martinstor: Masken fertig 10:38 (2042 Bilder, 763 s, im Mittel 12,6 % maskiert). NEU `tools/db_masken_filter.py`: 71 488 Paare, 39 453 gekuerzt, 6281 geloescht (35 s).
  Aber: Bruecke Gruppe 36 bleibt fast gleich (zu Sued 66 -> 59 Paare, zu Nord 26 -> 22) -> die Paare haengen am HINTERGRUND; die Gruppe selbst ist GEMISCHT (Bilder von beiden Torseiten, vermutlich nur ueber die Person zu einer Gruppe geworden).
  Pruefung: Seitenerkennung neu auf der gefilterten DB (Job `seiten-martinstor-1121c`, Start 10:40) - zerfaellt Gruppe 36 auf ihre Seiten?

## Nachtrag 21.11. 10:59 - Paar-Pruefer bekommt die Masken (Nutzer: "na klar muss der Pruefer die Masken bekommen")
- `doppelgaenger_paare.pruefen(..., masken=)`: Vordergrund (Maske 0) im Bild grau gefuellt, bevor LoFTR und das Entscheidungsnetz es sehen; `seiten_erkennen.py --masken DIR`.
- Job `seiten-martinstor-1121c` (ohne Masken im Pruefer, Start 10:39) nach 17 min GESTOPPT (Ergebnis waere nicht aussagekraeftig gewesen) - Zeitverlust, ich haette den Pruefer vor dem Start anpassen muessen.
- 10:56 neu `seiten-martinstor-1121d`: gefilterte DB + Masken im Pruefer. Gruppen auf der gefilterten DB: 190 (vorher 170), 119 Gruppenpaare, 2848 Pruefpaare.
- Rueckfall: `pkill -f` mit Muster aus der eigenen Befehlszeile benutzt (Regel CLAUDE.md) - traf nur die eigene Shell (rc 144), kein Job betroffen.

## Nachtrag 21.11. 11:27 - BELEG: mit Masken trennt die Seitenerkennung Sued und Nord am Martinstor
- Job `seiten-martinstor-1121d` (gefilterte DB + Masken im Pruefer), fertig 11:25 (29 min): 190 Gruppen, 731 151 Paare geloescht, 4 Bildteile ohne echte Verbindung.
  Gegen die Bezugsmodelle vom 19.11. (nur zur Kontrolle): Teil 0 = 538 Bilder, Nord 203 / Sued 0; Teil 1 = 102 Bilder, Sued 43 / Nord 0; Teil 2 = 55 Bilder, Sued 6 / Nord 0. KEIN gemischter Teil (ohne Masken: 750 Bilder mit Sued 52 + Nord 203).
- OFFEN: 162 Nord- und 3 Sued-Bezugsbilder stehen unter 'fremd' (1362 fremde Bilder) - Regel "Teil ohne Objektfoto = fremd" pruefen; Sued zerfaellt in zwei Teile (102 + 55).
- Masken am Bild geprueft (8 Beispiele, `masken_probe.jpg` gezeigt): Personen/Autos gut, Turm frei; Brunnenfigur und ein Fleck am Turm faelschlich maskiert.
  Nutzer 11:26: Strassenbahn nicht immer, Baum gar nicht maskiert. Ursache: das Netz (ADE20K-150) hat KEINE Klasse Strassenbahn (wird 'bus' oder 'building'); 'tree'/'plant' gibt es, stehen aber nicht in der Maskenliste.
- 11:27 Job `mt_seiten_mapper_1121` (tools/versuche/mt_seiten_mapper_1121.sh): schrittweiser Mapper je Teil, Reihenfolge Sued 102, Sued 55, Nord 538.

## Nachtrag 21.11. 11:29 - Suedmodell + hartes Blick-Tor
- 11:26 Mapper-Job Fehlstart (libcudart nicht gefunden, Skript meldete rc 0 mit 0 Modellen - kein Dummy-Test, Rueckfall); 11:27 neu mit LD_LIBRARY_PATH.
- 11:28 Sued (Teil 1): 99 von 102 Bildern in 81 s, 7044 Punkte, 0,94 px; enthaelt 43 Sued- und 0 Nord-Bezugsbilder. Auffaellig wenig Punkte (71 je Bild) - pruefen.
- NEU `tools/seiten_blick_tor.py` (ohne Vorwissen: Gruppenpaare mit Urteil 'verwechselt' aus seiten.json duerfen im Modell nicht gleich blicken, Schwelle 60 Grad):
  verklebtes Nachtmodell (eng/0, 983 Bilder): 29 von 29 pruefbaren Paaren VERKLEBT (Blickwinkel 2,7-...), rc 3. Suedmodell allein: kein pruefbares Paar, rc 0 mit Hinweis "nur eine Seite".
  OFFEN: Gegenprobe am vereinten Modell (darf dort nicht anschlagen).
- `handy_masken.py`: tree/plant standardmaessig maskiert (--kein_gruen), Test bestanden. Strassenbahn: keine Klasse im Netz, offen.

## Nachtrag 21.11. 13:38 - Wolkenkoerper in der Kette (Stufe bauplan)
- `gesamtkette.py`: nach `bauen_mit_bauplan` -> `bauplan_wolkenrest` (wolke_rest --uebernehmen), `bauplan_dachprofil` (nur wenn audit/dach_profil.json fehlt, also gegen das LoD2-Dach), bei Neuem zweiter Bau `bauen_mit_wolkenkoerpern` + Nachmessung;
  faellt die Zahl der Wolkenpunkte am Modell, meldet die Kette einen Fehler (Annahmeregel als Meldung, noch kein automatisches Zuruecknehmen). Generator-Aktualitaetspruefung kennt `drehkoerper_aus_wolkenrest` und `dach_aus_profil`.
- NICHT durch einen Kettenlauf belegt (RAM belegt durch Martinstor-Laeufe) - offen.
## Nachtrag 21.11. 13:40 - Seitenfolge IN DER KETTE (Agent im Worktree, nur Code + feste Tests, KEIN Kettenlauf)
- `tools/iphone_sfm.py` ruft jetzt die Vorstufe 'seiten' (`tools/sfm_seiten_vorstufe.py`, Standard AN, `RCPARK_SEITEN=0` aus): Masken (`handy_masken --batch 2`, nur fehlende) -> Masken in der Merkmalssuche (ImageReader.mask_path; vorhandene DB ohne Masken: `db_masken_filter` als Rueckfall) -> `seiten_erkennen --streng --masken` -> Mapper auf `db_seiten.db`. Zwischenstaende mit Stand-Datei wiederverwendet.
- DB-Bereinigung (Kamera je Clip, EXIF-Prioren weg) jetzt auf JEDEM Mapper-Weg (`db_mapper.db`; Konsens bereinigt weiter selbst). Bildteile/fehlende Seiten stehen in `mapper_wahl.json` ('seiten') und als Zeile `seiten_vorstufe` im Kettenbericht; fremde Bilder zaehlen nicht mehr in die 50-%-Regel des Konsens-Urteils.
- `tools/gesamtkette.py` Stufe tore: `seiten_blick_tor.py` als HARTES Tor (rc 3 -> Abbruch rc 3, kein Loesungs-Kreislauf), `brennweite_schaerfe.py` -> `sfm/sperrliste_messen.txt` = unbestimmt + zu_wenig vereinigt mit `konsens_arbeit/unstabil.txt` (neu: `--sperrliste/--vereinen`); `pipeline_objekt.py` gibt sie `dicht_bildwahl --ohne` (Guard: > 50 % der Bilder gesperrt -> nicht anwenden).
- LEHRE (Mini-Probe, 3 Kunstbilder, CPU): COLMAP UEBERSPRINGT ein Bild ohne Maskendatei (MASK_ERROR) - es fehlt dann in der DB. Deshalb leere weisse Maske fuer jedes Bild ohne Maske; `handy_masken.py` las bisher nur *.jpg/*.png (im Sammelordner martinstor-1120 fehlten 56 .jpeg + 9 .JPG = die 65 Bilder ohne Maske) -> Endungen ohne Gross/Klein.
- ANNAHMEN, nicht am Lauf gemessen: (a) Guard "kein 'verwechselt'-Urteil -> Mapper auf ungeteilter DB" (sonst zerstueckelt --streng kleine Fotosaetze), (b) Bereinigung auch fuer den schrittweisen Mapper (heutige Handlaeufe liefen ohne), (c) Masken in der Merkmalssuche statt Filter (maskierte Merkmale verbrauchen das 6400er-Budget: Kunstbild halb maskiert = halbe Merkmalszahl), (d) Sperrlisten-Schwelle 50 %.
- OFFEN: Kettenlauf als Beweis; Mapper je Seite + Vereinen (bewusst nicht eingebaut - bei getrennten Seiten nimmt die Kette nur sparse/0 und MELDET die fehlende Seite); Sperrliste wirkt nur auf die dichte Wolke, noch nicht auf Kantenstufe/Wandbild; `--objekt` (GPS-Anker) wird der Seitenerkennung nicht uebergeben; VRAM der Masken 6,9 GiB liegt ueber der Kettenbuchung 6000 MiB; drei bis vier DB-Kopien je 2,8 GB am Martinstor.
- Fester Test `tools/test_seiten_kette.py` (5 Teile, ohne GPU) im Schnelltest; Schnelltest 0 Fehler (im Worktree erst nach Verknuepfen von `modelle/stl/ober_tvdr_1-87.stl` und `daten/schwab_v3/fotos`, die dort fehlen).
## Nachtrag 21.11. 15:10 - SEITENMODELLE IN DER KETTE: je Seite Mapper + dichte Wolke + Vereinen (Agent im Worktree, nur Code + feste Tests, KEIN Mapper-/Wolken-/Kettenlauf)
- NEU `tools/sfm_seiten_modelle.py` (einzeln startbar; `iphone_sfm.py` ruft es bei mehreren Bildteilen, Schalter `RCPARK_SEITEN_MODELLE`, Standard AN; `RCPARK_SEITEN_MIN_BILDER`, Standard 30):
  Phase 1 je Bildteil >= 30 Bilder `view_graph_calibrator` (DB-Kopie) + `global_mapper --GlobalMapper.image_list_path` ZWEIMAL, a/b per `modell_lage_vergleich` als Zahl, Sperrliste `brennweite_schaerfe`;
  Phase 2 je Teil `dicht_modell`, Teil A = meiste Bilder im Modell, jeder weitere Teil `seiten_vereinen` gegen A mit der URSPRUNGS-DB (vor der Seitenerkennung) und beiden dichten Wolken.
  rc 0 -> Teil kommt ins VEREINTE Modell, danach `seiten_blick_tor` auf dem vereinten Modell (rc 3 -> Teil wieder heraus); rc 3/2 -> Meldung mit Urteil + Pruefwerten, Teil A allein. Bericht `sfm/seiten_modelle.json`.
- REGEL Laufwahl (im Code `lauf_wahl`): mehr registrierte Bilder (Unterschied >= 1 % der Teilbilder und >= 2 Bilder), sonst kleinerer Bildfehler, sonst a. ANNAHMEN (nicht gemessen): 1-%-Grenze, 30 Bilder Mindestgroesse,
  10 Bilder Mindestmodell, Warnung "Laeufe uneinig" ab 25 % Bildern > 2 % (gemessen Nord 14 %, Sued 8 %), Sperrliste nur bis 50 % der Bilder.
- VEREINTES MODELL geht sauber (kein Rueckfall noetig): B mit `Reconstruction.transform(Sim3d)` umrechnen, dann NEUES Modell aufbauen - `add_camera_with_trivial_rig`, neues `Image` (Name, Bildpunkte, IDs) +
  `add_image_with_trivial_frame(bild, lage)`, `add_point3D(xyz, spur, farbe)`. `add_image` mit dem Bild des alten Modells scheitert an "frame.RigPtr() == &rig" (Zeiger auf Rig des alten Modells). Bild-IDs bleiben,
  Punkt-IDs neu, Kamera-ID mit verschiedenen Werten in A und B bekommt fuer B eine neue ID. Probe an den ECHTEN Martinstor-Modellen (nur gelesen, Ausgabe im Scratchpad): global_teil0_a + modell_teil1 mit der
  B_nach_A von 14:34 -> 637 Bilder, 79 244 Punkte, 1 006 722 Beobachtungen (= Summe), Bildfehler 0,916 px (A 0,914 / B 0,936), 4,7 s; `seiten_blick_tor` auf dem vereinten Modell BESTANDEN (3 Gruppenpaare, 129-145 Grad).
- DICHTE WOLKE NICHT DOPPELT: die Wolken je Seite entstehen in `sfm/seiten_modelle/teil<i>/dicht`; vereint -> `sfm/seiten_modelle/vereint/dicht` (images verknuepft, entzerrte sparse-Modelle vereint, Tiefenkarten von B
  als Kopie x Massstab, fused.ply = A + umgerechnetes B samt Normalen). `pipeline_objekt.py` (`seiten_dicht_uebernehmen`) macht `dicht/` zur Verknuepfung darauf, wenn es `dicht/` noch nicht gibt und die Wolke nicht aelter als sparse/0 ist.
- `gesamtkette.py`: Zeile `seiten_modelle` im Bericht (rot, sobald ein Teil nicht vereint ist); das Seiten-Blick-Tor prueft sparse/0 = das vereinte Modell; `tor_zerfall` meldet beim vereinten Modell erwartbar mehrere Stuecke -> Hinweiszeile.
- UNGEPRUEFT: kein Kettenlauf; `iphone_sfm.py`-Verdrahtung nur per Uebersetzen + Textprobe (Skript ohne Testrahmen); vereinter dicht-Ordner nie von Kanten-/Fassadenstufen gelesen (fused.ply.vis und consistency_graphs fehlen);
  Tiefenkarten-Massstab nur synthetisch; kein gemeinsamer Buendelausgleich der Seiten; Bereinigung (Kamera je Clip) vor dem globalen Mapper je Seite weicht vom Handlauf ab (dort unbereinigte DB); mehr als zwei Teile nur im Code.
- Fester Test `tools/test_seiten_modelle.py` (5 Teile, ohne GPU, Attrappen fuer COLMAP/dicht_modell/seiten_vereinen) im Schnelltest. Schnelltest im Worktree: 2 Fehler, beide `PLATZ ZU KNAPP` (Root 4,2 GB frei, Grenze 5 GB:
  `test_kette_stabil` und `Kette lauf()` rufen `platz_pruefen`) - nicht aus dieser Aenderung; alle uebrigen Punkte gruen.

## Nachtrag 21.11. 15:24 - Kettenlaeufe als Beleg, Platz, Agenten
- Zusammengefuehrt: Agent "Mapper je Seite + Vereinen" (a7fc0be1b, `tools/sfm_seiten_modelle.py`), Schnelltest 0 Fehler.
- PLATZ: Root nur 2,5 GB frei (Grenze 5): erster Start `kette-schwabentor-1121m` 15:11 scheiterte still am Platz-Tor (ich hatte nur die letzte Zeile der Startausgabe gelesen - Rueckfall). Abhilfe: fertige Agenten-Worktrees aufgeloest (je ~600 MB), Scratch-Ordner alter Sitzungen nach /media/oem/rcdaten/tmp/scratch_alt_1121/ ausgelagert (kopiert, Dateizahl verglichen, dann entfernt) -> 5,0 GB.
- 15:15 `kette-schwabentor-1121m` (--ab bauplan --bis bauplan): Beleg fuer Wolkenrest/Dachprofil in der Kette; `audit/koerper_auto.json` und `dach_profil.json` von Hand vorher beiseite (Scratchpad sw_hand_1121).
- 15:23 `kette-martinstor-1121a` (--ab sfm, wartet auf GPU/RAM hinter dem Schwabentor-Lauf): SCHNELLER BELEG der Seitenfolge in der Kette mit der VORHANDENEN Datenbank (Merkmale/Paare aus Cache -> Maskenfilter als Rueckfall -> Seitenerkennung -> globaler Mapper je Seite -> dichte Wolken -> Vereinen -> Tore) statt 10-14 h von null; alte sparse-Staende nach pipe/sfm/alt_1121/ verschoben. Der Lauf ganz von null (Masken in der Merkmalssuche) folgt danach.
- Agenten laufen: Oeffnungen aus Kanten, Koerper-Schleife (Nachbarn, Kasten/Ring/Stab, Annahmeregel), Rezept-Dokument + fester Vereinen-Test.

## UEBERGABE 21.11.2026 15:40
Stand siehe `.claude/UEBERGABE.md` (Martinstor-Kette 1121a laeuft, Agent Oeffnungen gemergt 84f6c437b, Koerper-Agent laeuft).

## 21.11. ~15:45 Merge koerper_schleife (Agent 992f43415) + Uhrring-Neubau
- Uhrring-Fix gebaut: Abnahme Pruefstand bestanden, "Anzahl getrennte Koerper" 1 (vorher 2). Neben-Foto-Bilder CUDA OOM, weil der Martinstor-Lauf die GPU belegt -> nachholen, wenn die GPU frei ist.
- koerper_schleife gemergt: wolke_rest trennt fremd/innen/aussen, Formen rund/stab/ring/kasten/band, Treiber tools/koerper_schleife.py, Generator ruft wolkenrest_koerper. Schnelltest 0 Fehler (132 s), Regression identisch, Abnahme bestanden, Sichtblatt unveraendert.
- Offen (Agent-Fehlerliste): r00 (161 843 Pkt.) ist kein Nachbar, sondern ein Faecher aus Streupunkten oder einer falsch registrierten Bildgruppe (Bild bestaetigt), nur per Ersatzregel weg -> Ursache in SfM/Wolke suchen. Treiber hat noch keinen echten Generatorlauf hinter sich. Am Schwabentor entsteht nur ein Band als Kandidat (Rechteckklotz, wo die Wolke einen Keil zeigt).
- Realitaet: Benennen ~60 %, Bauen neuer Formen an echten Daten ~20 % (Agent-Schaetzung, Bild gesehen).
- 15:50 Torbreite geklaert (oeffnungen_aus_kanten f00): Wolke zeigt die Seitenwaende ueber 4 m Tiefe gleich bei u -2,5 / +2,8 (keine Stufe). Im entzerrten Wandbild ortho_f00.png liegen die 5,37 m auf der Aussenkante des abgeschraegten Sandstein-Gewaendes, die Hand-4,49 m auf der lichten Weite -> beide richtig, verschiedene Masse. Form im Bild eindeutig SPITZBOGEN; das Werkzeug waehlte Rundbogen (Rest spitz 0,103 < rund 0,111, aber "nicht klar"). LEHRE: Wolkenrand misst Oeffnung inkl. Fase; Form braucht Bildkanten. Agent im Worktree baut Bogenkanten aus dem feinen Wandbild + getrennte Masse (aussen/licht/Fase).
- 15:55–16:06 SACKGASSE Faecher r00 -> Kamera suchen (tools/versuche/faecher_kamera_1121.py): Winkelbelegung bzw. "Strahlanteil" je Kamerastandort bevorzugt systematisch ferne Kameragruppen (75 m, 0,78 vs Median 0,21) - Mass entfernungsabhaengig, Kasten aus altem wolke_rest.json greift ueber das Modell hinaus (1,4 Mio statt 162 Tsd Punkte). Ursache des Abbruchs: dichte Wolke hat keine Sichtbarkeit je Punkt (fused.ply.vis fehlt). RICHTIG waere: beim Fusionieren .vis behalten oder Tiefenkarten je Bild gegen den Faecher pruefen. Erst erste Rechnung mit STL-Einheit falsch (x1000/87 statt x87/1000) -> Einheiten erst mit bounds pruefen.
- hand_vergleich liest jetzt koerper_auto.json (Treppenturm: form rund) und dach_profil.json (Ueberstand = Mittel der zwei mittleren Seiten in den unteren 2 m; Laterne: Spitze = oberste Scheibe, Krempe = erste Verbreiterung > 20 % ueber dem Hals, ANNAHME). Schwabentor 2/11 -> 4/11: Treppenturm r 1,73 (Hand 1,56) Traufe 11,77 (11,57) PASST, Ueberstand PASST; Laterne FALSCH (Spitze 49,69 statt 51,76: Wolke endet unter dem Knauf; Krempe 48,44 statt 47,0). Test tools/test_hand_vergleich.py im Schnelltest.
- 17:00 Platz Systemplatte (Platz-Tor stoppte job_start bei 4,3 GB): ~1 GB kalte, unversionierte Daten nach /media/oem/rcdaten/rc-park_auslagern (rsync + Pruefsumme, Symlink zurueck): modelle/schwabentor/sfm (20 alte sparse/punkte-Dateien), H0-Teile, decal_probe, scan_koerper, kaufhaus_gk/martinstor_gk sfm -> 5,1 GB frei. URSACHE des Dauerproblems: Root-Partition nur 48,8 GB (Windows 134 + Volume 193 + scan 100 auf derselben 477-GB-SSD); jede Agent-Arbeitskopie (.claude/worktrees) kostet ~620 MB auf Root (3 laufen = 1,9 GB). Abhilfe: Worktrees auf /media/oem/scan legen, sobald die Agenten fertig sind.

## Nachtrag 17:10 - Zweites Rundbogenfenster / Nische als eigene Ebene (Agent, Worktree; tools/nischen_fenster.py)
- Ursache belegt: (1) `fenster_tiefe_tor.py` ergaenzt innere Erkennerkaesten nur, wenn im 0,5-m-Ring um den Kasten >= 70 % sichere Sweep-Zellen liegen. Der Ring liegt beim Fenster-in-Nische grossenteils IN der Nische und auf ihren unsicheren Laibungen: links 0,68 -> nicht ergaenzt, rechts 0,71 -> ergaenzt (hinten 60 % / 53 %, beide eindeutig Nische). (2) Die aeusseren Nischenkaesten (fenster/bogen, 3 Stimmen) gingen nirgends ein; `hand_vergleich` nahm die Fensteroeffnung (0,59 m) als "Nische". (3) Fenster nur als Rechteck, keine Bogenform.
- Neu `tools/nischen_fenster.py` (Kette: bauplan nach fenster_tiefe_tor): Erkennerkaesten nur als ZONE; Paar = aeussere Zone mit genau einer inneren Gruppe. Umriss je Ebene aus dem 1-cm-Wandbild: Kandidaten aus MEDIAN-Gradientenprofilen (schraege Stoerlinien im Ortho fallen raus), Stufe 1 Laibungen+Sohlbank, Stufe 2 Scheitel+Formfamilie+Kaempfer; Mass = Anteil des Umrisses auf Bildkanten (> 4 x Rauschen der Zone); reichere Form nur bei > 2 Standardfehlern Gewinn. Tiefe: Nischenring gegen Wandring, Fenster gegen Nischengrund (Sweep). Bau: `bauteile.fenster_aus_json` schneidet Nische (flach) + Fenster (tiefer) mit Bogenquerschnitt, wenn `nische`/`bogen` im Eintrag stehen (alte Eintraege unveraendert).
- Zwischenstand verworfen mit Ursache: Mittelwert-Profile + Zonen-Median als Kontrastbezug -> rechte Nische auf einer hellen Ortho-Stoerlinie (u 2,8) als "spitz"; linker Fensterscheitel auf einem Kabel (25,17 statt 24,8).
- Probe Schwabentor f00 (nur Ausgabeordner, audit unveraendert): 2 Paare. Links Nische u -3,13..-0,97 (2,16 m) rund, Sohle 23,07, Scheitel 25,31, 0,10 tief; Fenster 0,69 m, korb (ueberhoeht: Pfeil 0,50 bei halber Breite 0,35), Sohle 22,97, Scheitel 24,80, 0,10 hinter Nischengrund. Rechts Nische 1,12..3,26 (2,14 m) rund, Sohle 23,00, Scheitel 25,48, 0,10 tief; Fenster 0,69 m rund, 23,05..24,84, 0,20 hinter Nischengrund. f03-Paar: keine Fotozellen -> kein Fenster.
- Danach Handvergleich (Kopie des Objektordners): anzahl 2 = 2, nische_breite 2,16 statt 1,95 (in Toleranz), sohlbank 23,04 statt 22,59 = FALSCH (+0,45). Hand-Nischenhoehe 2,35 / Oeffnung 1,76 stimmen mit der Kette (2,24-2,48 / 1,79-1,83) - der Versatz ist ein Hoehenbezug wie bei der Uhr (+0,7, Nachtrag 01:40), im Wandbild liegt die Sohlbank-Kante sichtbar bei z ~23,0.
- Offen: Kettenlauf mit der neuen Stufe (Bau + Abnahme schwabentor-1120 im Worktree nicht moeglich: keine Relief-/Datenordner); Nische ohne erkannten Aussenkasten wird nicht gesucht; Sohlbank-Gesims (Vorsprung) nicht gebaut.

## Nachtrag 21.11. 17:15 - Warum Fassaden glatt bleiben (Agent, Worktree): Ursachen benannt, Werkzeuge repariert
- Zuordnung (aus fassaden_kette.json, Normalen): w00 = West (+y), w01-w03 = Nord (+x), w04 = Ost (-y), w05-w07 = Sued (-x). Der Verdacht "w00/w02" war nur halb richtig: die glatten Seiten im Sichtblatt sind w04-w07.
- Sued (-x, w05-w07) und Ost (-y, w04): KEINE Fotos der Turmwand -> kein Werkzeugfehler. Netz: w05/w06 0 Dreiecke, w07 96 % / w04 85 % Loch. Fotos: Sued nur 4-5 schraege Aufnahmen, 6-35 % der Wand von >= 3 Fotos gesehen (fassade_fein f01: 4 %);
  Ost: 126 Fotos/Videobilder "sehen" die Ebene, zeigen aber die vorgelagerten Nachbarhaeuser (Fachwerk, Laubengang) - mit LoD2-Verdeckung sieht kein Foto 30 % (Bild scratchpad w04_gegen.jpg). Fotoauftrag steht schon (fotoauftrag_schwabentor-1120.json Nr. 1 Sued 347 m2, Nr. 2 Ost 258 m2); Ost oberhalb der Nachbardaecher nur von erhoehtem Standort.
- West (w00) URSACHE 1: Stufe 5c (steine_aus_foto --streng) nahm als Gegenfoto eigen__192 (K "grob", f/Lage falsch: Gesims 4 m zu tief auf der Wand). Paar auf 99 % der Struktur widerspruechlich -> 49 % des Feldes als "Verdecker" ausgeblendet = genau die Eckquader -> Quader-Tor 0 % -> keine Steine.
- West URSACHE 2: Rang-1-Foto eigen__IMG_20261106_114052 ist senkrecht verwackelt (Quader-Tor 3 %), die Nachbaraufnahmen 114037/39/50 vom selben Standort sind scharf (16-20 %, 13-18 Schichten).
- FIX steine_aus_foto.py (Paar-Probe): ein Paar, das auf < --paar 30 % der Struktur BEIDER Fotos uebereinstimmt, ist "Kamera falsch, kein Verdecker" -> naechstes Gegenfoto; unter den 3 besten Hauptfotos gewinnt das mit der hoechsten feinen Korrelation (1 cm) x Abdeckung.
  Gemessen (CPU, ohne Verdeckungs-STL): gute Paare 59-81 % einig, eigen__192 1-3 %. w00 5c jetzt rc 0, 314 Steine (vorher rc 5); w01/w02/w03 unveraendert (210 / Tor-Ablehnung richtig: Uhr + Vordachziegel / 216). Bild scratchpad w00_vorher_nachher.jpg.
- tiefe_lokal "Signal 6" (w01/w03): URSACHE Bildgroesse - Buendel aus 1600-px-Bildern (Kamera 1200x1600), Bildordner der Kette hat Originale 3000x4000 -> COLMAP-Entzerrer "Uncaught exceptions in thread pool" = SIGABRT.
  FIX tiefe_lokal.bilder_anpassen: Kamera auf die Dateigroesse umrechnen (gleiches Seitenverhaeltnis), sonst Bild aus dem Teilnetz (eigen__051: 1920x2880 gegen 1032x1600). Entzerrung auf CPU geprueft (11 Bilder); PatchMatch nicht (GPU belegt).
- Test: tools/test_steine_paar.py (synthetische Quaderwand, falsche Kamera C, verwackeltes A1) im Schnelltest; Schnelltest 0 Fehler (im Worktree nur mit voruebergehend verlinkten ober_tvdr-Daten).
- SACKGASSEN: (1) Schaerfemass "Feinanteil" |g-blur1|/|g-blur4| im Foto/auf der Wand erkannte 114052 NICHT als verwackelt (0,37 gegen 0,33 - Rauschen/JPEG). (2) Anteil "einig" (Korrelation >= 0,25 bei 3-cm-Vorglaettung) saettigt: verwackeltes Foto synthetisch 100 % einig -> Rang ueber mittlere 1-cm-Korrelation.
  (3) --tor 0 in 5c fuer Waende mit bestandenem Gesamt-Tor waere falsch: w02 wuerde Uhr und Vordachziegel zu "Quadern" machen.
- OFFEN: Kette nicht neu gelaufen (GPU belegt) - Probe ohne Verdeckungs-STL; eigen__192 hat eine falsche Kamera und speist auch fassade_ortho (f01/f03) - Kamera pruefen; Gesimsband wird zu senkrechten "Steinen", Schlitzfenster/Gewaende als Steinstreifen (Fehlerliste).

## UEBERGABE 21.11.2026 17:20
Stand in `.claude/UEBERGABE.md` (Merges Nischen-Fenster, leere Fassaden, Seiten vereinen; Tor-Wandbild-Stufe; naechster Kettenlauf ab fassaden).

## Nachtrag 21.11. 17:41 - Tor/Uhr/Fenster-Hoehen: kein gemeinsamer Hoehenbezugsfehler der Kette (Agent, Worktree)
- Frage: Uhr +0,7, Sohlbank +0,45..0,53, Tor-Scheitel -0,5 / Kaempfer -1,0 gegen Handstand - gemeinsamer Hoehenbezug (Wandbild-z, Boden, Ausrichtung, fassade_fein-Rahmen)?
- Befund 1 (kein gemeinsamer Versatz/Massstab): Vorzeichen widersprechen sich (Uhr/Sohlbank +, Tor -), Galerie (10,23/11,47) und Vordach (16,02/19,39) stimmen mit der Hand auf <= 0,07 m. Feines Ortho (ein Bezugsfoto) und Mittel-Ortho (26 Fotos je Zelle) zeigen Uhrnabe und Sohlbank-Kante genau auf den Kettenwerten (31,955 / 23,04); die Handlinien liegen sichtbar darunter.
- Befund 2 (Handrahmen): Hand-Abstaende ueber der Galerie sind gleichmaessig ~3,4 % kuerzer (Sohlbank-Galerie 11,17 statt 11,57, Uhr-Galerie 19,83 statt 20,49, Uhr-D 5,00 statt 5,13), die Verhaeltnisse (Doppelverhaeltnis Boden/Galerie/Sohlbank/Uhr) sind gleich -> reiner Rahmen-Massstab, den kein Foto entscheidet. Hand-Quelle: "Masse mit Lasermassstab 0,933 (DOM1)" = Faktor aus Dachflaechen; hoehe_gegen_dom1 dieser Kette zeigt, dass der Dachvergleich von der Dachform abhaengt (Dach +1,62, Wand passt: f00 12,17 m gegen LoD2 12,13-12,5; DOM1-Traufpixel 37,1-37,4 ueber Wandoberkante 36,5-36,9). Die Hand hat ausserdem zwei eigene Uhrwerte (31,25 und 30,97). URTEIL: Uhr/Sohlbank der Kette stimmen mit dem Foto, Handwerte ~3 % zu klein -> KEIN Kettenfix.
- Befund 3 Tor: Kette-Umriss (spitz, licht 4,50/K 2,99/S 6,22, aussen 5,26/K 3,23/S 6,60) liegt im Mittel-Ortho auf Innen- und Aussenkante des Sandstein-Gewaendes. Profil u=0: dunkel (Durchfahrt) bis 6,15, Gewaende 6,15-6,55, Bogensteine ab 6,6. Hand-Umriss (Kaempfer 3,97, licht 6,42) liegt mitten im Gewaendeband; Quelle sagt selbst "ANNAHME: Kreisboegen".
- URSACHE Vergleich: referenz_hand.json hatte unter tor "scheitel" den AUSSEN-Scheitel (schwab_v3 scheitel_aussen 6,72; lichte_hoehe 6,42) - verglichen mit dem LICHTEN Kettenscheitel. FIX: referenz_hand tor = breite 4,32 / scheitel 6,42 / scheitel_aussen 6,72 / kaempfer 3,97 mit hand_annahme kaempfer (Fotobeleg); hand_vergleich.py liest scheitel_aussen aus aussenmass, Masse unter "hand_annahme" werden angezeigt, nicht geurteilt. Test test_hand_vergleich.py (Tor licht/aussen, Annahme ohne Vermerk wieder geurteilt), Schnelltest.
- Probe (Kopie des Objektordners + oeffnungen_kanten uebernommen): Tor PASST (4,50/6,22/6,60); Uhr FALSCH bleibt (Handrahmen), Rundbogenfenster in der Kopie noch altes fenster_auto (1 Fenster). Kontrollbild scratchpad kontrolle_hoehen_uhr_fenster_tor.jpg (angesehen).
- OFFEN: Absoluter Hoehenmassstab der Kette ist nur ueber LoD2-Grundriss (+-3 %) und DOM1-Traufe belegt; wenn die Kette eher 2-3 % zu klein ist (f02-f03 12,12 statt LoD2 12,5), laege die Hand noch weiter daneben. Hand-Uhr/Sohlbank als Sollwert NICHT uebernehmen.
## 17:50 Agent Laterne + Durchfahrt (Worktree agent-a4b81dfb20a891c30)
- LATERNE, Ursache: Dachprofil nur aus der dichten Wolke; oben duenn (Wolke endet 49,94, Knauf nicht drin), Hals im Bereich mit ~300 Punkten/Scheibe. rund_aus_umriss.py passt nicht (Kreis + Gradientenkanten; Laterne offen mit Pfosten, Zwiebelhaube, Fugen).
  Neu tools/spitze_aus_umriss.py (Kettenstufe bauplan_spitze_umriss nach bauplan_dachprofil): Himmelskante der kalibrierten Fotos an der Dachachse -> Spitze (Gipfel der Silhouette auf der Achse, Traufe-verdeckt verworfen), Halbbreite je Hoehe, eckig/rund aus Blickrichtungs-Abhaengigkeit, Hals/Krempe (Plateau 93 % gegen Untersicht-Ellipse). Block 'spitze_foto' in dach_profil.json; bauteile.dach_aus_profil baut ab Laternenhals aus Fotos bis zur Spitze; hand_vergleich liest ihn.
  Probe Schwabentor: 17 Fotos aus 3 Sektoren (0, 6, 7; 173 ohne Maske im Cache, 136 Bildkante), Spitze 53,44 (Streuung 0,30), Hals 47,59 halb 0,82, Krempe 48,79; Hand 51,76 / 47,0 -> beide ~+1,75 m. ANNAHME/Befund: hoehe_gegen_dom1 meldet Modell +1,62 m ueber Laser, massstab_k 0,9605 - x0,96 gaebe 51,3 / 46,8 (passt). Massstab/Hoehenbezug pruefen, nicht im Werkzeug ausgleichen.
  Sackgasse: Untersicht-Korrektur r*tan(Hoehenwinkel) (waagrechte Scheibe) synthetisch richtig, am echten Turm +0,67 m zu viel (Krempe ausgestellt, Breite springt in 0,3 m) -> ersetzt durch Plateau-Regel.
- DURCHFAHRT, Ursache: oeffnungen_bogen.py erkennt Durchfahrt nur mit Bogenkandidat auf der Gegenseite. Gegenseite von f00 ist f01 (nicht f02; Normalen entgegengesetzt, Dicke 11,68 m) mit 4 Fotos, kein Kandidat -> Nische 0,6 m.
  Neu tools/durchfahrt_pruefen.py (Kettenstufe oeffnungen_durchfahrt nach oeffnungen_bogen): Laibung des Torwegs in der Wolke durchgehend bis zur Gegenseite mit Kontrast >= 2 gegen Kontrollstreifen beidseits + keine Rueckwand (Deckung <= 0,6). f00: Laibung rechts 100 %, links 60 %, Deckung 0,42 -> DURCHFAHRT, tiefe 12,28. Gegenproben echte Wolke: Wand neben dem Tor (u +-4,3) und 6 Stellen auf f02/f03 abgelehnt. Sackgasse 1. Fassung: alle Punkte im Querschnitt zaehlen -> massive Wand 'bestand' (Streupunkte im Turm).
  Sichtblatt (Probe, nicht committet): Sued zeigt den Torbogen jetzt durchgehend. Test tools/test_spitze_durchfahrt.py im Schnelltest.
## 17:55 Agent Umgang + Eckquader (hand_vergleich: beide FEHLT -> PASST, 4 -> 6 von 11 bei Probebau im Worktree)
- UMGANG: Ursache FEHLT = das 1-cm-Wandbild endet unter dem Dachueberstand (Stufenmodell verdeckt jede Kamera), keine Stufe sah die Zone. Neu Kettenstufe `bauplan_umgang` -> `tools/umgang_aus_fotos.py`: Band z_top-5..+0,6 m je Hauptwand aus den kalibrierten Einzelfotos entzerrt, Zone aus Zeilenkanten (Schwelle = Hell->Dunkel-Kante, Durchblick-Probe Zone dunkler als Wand), Pfosten = schmale dunkle Senken (Black-Hat 0,4 m), Konsens ueber Fotos (>= 50 %), + 2 Eckpfosten (ANNAHME). Schwabentor: f00 6 Fotos, z 35,92..36,97 (Oberkante auf Traufe begrenzt, Foto 37,14), innen u -1,90/+1,92 -> 4 Pfosten je Seite. Nur f00 hat Fotos <= 3 cm/px; Ost/Sued/West wie Nord = ANNAHME. Generator: `bauteile.umgang_aus_json` VOR aushoehlen (auch im Rumpf objekt_anlegen.py). Sackgasse: f02-Kameras zeigen im Band nur Himmel (Durchblick-Probe verwirft sie).
- ECKQUADER: Ursache 1 (Benennung): Fotosteine (steine_aus_foto) bauen die Eckquader als Relief, aber kein Beleg hiess so -> `bauteile.eckquader_aus_relief` + `fassaden_kette.wandende_ist_ecke` (Ecke = Wandende ohne gleichgerichtete Nachbarwand) -> Beleg je Eckzone. Ursache 2 (unsichtbar, schwerer): Fotostein-Relief lag mit trend=True auf der Netzebene (w01 -0,39, w03 -0,51 m), die Wand nach Abweichungsschleife bei -0,15 m -> Steine im Koerper versunken. Fix: `fassaden_kette.koerper_flaeche` misst die Koerperflaeche (9 Proben, Median), `relief_einsatz.koerper(flaeche=)` setzt Putz genau darauf (FOTOSTEINE_NETZEBENE=1 = alt). Kontrollbild /media/oem/scan/rc-park_daten/schwabentor-1120/zeigen/umgang_bau_ansicht.jpg: Eckquader an beiden Kanten verzahnt sichtbar, Umgang mit 4 Pfosten. Offen: Netz-/Mono-Relief der Wandmitte (w02) hat dieselbe Ebenen-Ursache (nicht angefasst).
## 18:15 Agent Hoehenmassstab (Frage: Kette in der HOEHE 3,5 % zu gross?) -> NEIN, Ursache = zu breites Wolken-Dachprofil
- Quellen getrennt (nicht gemittelt), alles im Rahmen rel. gelaende 282,16:
  Grundriss LoD2 (Kantenlinien, nicht rahmen_wand-Kasten): x 11,68 / y ~12,1 m; Kette f00-f01 11,68, f02-f03 12,12 -> 0 %. Die "12,5" war v1-v0 des Kastens (schraege Kanten + Ecken).
  Wolke-Waende (Modus je 2-m-Band, z 20-36): y+ +0,00, y- -0,25, x+ -0,30 m gegen LoD2 (Wolke ~2 % schmaler); x- ohne Wolke.
  Traufe: LoD2 36,31-36,86 (je Dachflaeche), Wolken-Wandende 36,5/37,0/37,25 (y+/x+/y-), dach_profil z0 36,94, DOM1-Knick ~37,5 -> Kette +0,1..0,6 m (<= 1,7 %), 3,5 % waere 38,2.
  Dachflaechen (RANSAC, 3,5 m ab Achse): DOM1 40,24-41,11; STL 41,29-42,29 (+1,0..+1,95); Wolke (nur x+) 39,25 - die Wolkenpunkte liegen im Schnitt AUF der Laserlinie.
  Laternenkoerper: Wolke ~49,9 vs DOM1 49,62. Boden: DGM1 am Tor +0,04..0,08, LoD2-Boden -0,03. Lot: Wolkenwand y+ 0,1 Grad, y- ~0, x+ 0,5 Grad (Verjuengung?) -> Hoeheneffekt 0.
- URSACHE: tools/dach_profil_wolke.py nahm in z 37-45 je Seite 0,8-3,8 m mehr als die Laser-Isolinie (Rauschsaum/Ausreisser bei z 38-39,5 bis +-7,8 m, 18 gespiegelte Seiten -n) -> 56-Grad-Dach steht +1,6..1,8 m ueber DOM1;
  hoehe_gegen_dom1 rechnet das in k 0,9605 um. Kein Massstab-, Lot-, Boden- oder Brennweitenfehler (Traufe+Grundriss+Laternenkoerper passen).
- FIX (generisch): dach_profil_wolke.dom1_veto - je Scheibe/Seite auf die DOM1-Isolinie (dom1_kachel.dom1_bilinear), wenn Ueberstand > 0,3 m; kein Veto, wo der Laser blind ist (Laterne/Spitze).
  --nur_veto zieht alte Profile nach; gesamtkette Stufe bauplan_dachprofil_veto (wenn dach_profil.json ohne Block dom1_veto). Test tools/test_dach_dom1_veto.py im Schnelltest.
  Nachrechnung auf Kopie (Profil-Huelle wie bauteile.dach_aus_profil gegen 132 DOM1-Dachpixel): vorher +1,81 m (MAD 0,31), nachher +0,02 m (MAD 0,06); 56 Eingriffe.
  Bild modelle/schwabentor-1120/audit/hoehe_ursache_dach_dom1.png (Schnitte d/n: Wolke, DOM1, Profil vorher/nachher, LoD2-Traufe).
- Erste Fassung setzte auf Isolinie + tol -> +0,45 m Rest (tol x Neigung); jetzt auf die Isolinie selbst.
- OFFEN: Kette nicht neu gebaut (Lauf 1121p); Hand-Uhr/Sohlbank 3,4 % tiefer als Kette -> Kette ist durch Traufe/DOM1 gedeckt, Hand vermutlich zu tief (nicht geprueft). Wolke ~2 % schmaler als LoD2-Grundriss bei +1 % Traufe = Seitenverhaeltnis +3 % - innerhalb LoD2-Genauigkeit (+-0,3 m), nicht entschieden. Echter Ueberstand < 1 m kann vom 1-m-Laser bis ~0,5 m beschnitten werden.
## 18:35 Agent Putz/Uhr (Nutzerbild umgang_bau_ansicht: Kruemel auf dem Putz der Stadtseite w02, Uhr nur flacher Kreis)
- URSACHE Kruemel: w02 ist Putzwand (Quader-Tor nein) -> relief_roh: Netz-Relief roh, putz_eben glaettet nur < 5 cm. Auf hellem texturarmem Putz hat das Netz 39 % Loecher, die Einzelzellen dazwischen weichen 5-15 cm ab (Rauschen, Oberleitungskabel) -> Kruemel. Netz kann Putz und Rauschen nicht trennen.
- URSACHE Ebene: Relief ohne Trend auf der LoD2-Ebene + 0,11 m Vorstand; Grundkoerper nach Wandversatz bei -0,15 m -> Putzplatte stand 0,26 m vor dem Koerper und VERDECKTE die Uhr (Ring 0,10 m vor der alten Ebene) -> "flacher Kreis".
- FIX (a) neu tools/putz_wandbild.py: Putz = >= 3 entzerrte Einzelfotos (fassade_fein/ortho_<fid>_einzeln) sehen die Zelle und >= 60 % zeigen keine Feinstruktur (Hochpass 2 cm / Ortshelligkeit < 0,8; gemessen Putz 0,25-0,30, Uhrring 6, Quader > 2). Kabel liegen je Foto woanders -> Mehrheit glatt. relief_putz_glatt: Putzzellen + kleine Inseln + Netzloecher + Uhrkreise auf EIN Niveau, uebriges Relief ohne Netzwoelbung; zusammenhaengender Koerper im Netz (>= 0,25 m2, fuellt >= 50 %) bleibt auch im "Putz" (einfarbiges Gesims). Aufruf in fassaden_kette.anbauen fuer quader=False-Waende (OHNE_PUTZ_WANDBILD=1 = alt).
- FIX (b) anbauen: Putzniveau auf die gemessene Koerperflaeche (koerper_flaeche): w02 -0,152 m, w00 -0,006 m (RELIEF_LOD2_EBENE=1 = alt). Folgefehler behoben: Zusatzkaesten der Schleife (korrekturen_aus_json 'fleck') begannen bei w_ist - 0,05 (= alte Reliefoberflaeche) und schwebten -> reichen jetzt bis hinter den Wandversatz.
- FIX (c) uhren_wandbild.zifferblatt_aus_fotos (Stufe bauplan_uhren, auch --nur_zifferblatt): je Einzelfoto Scheibe per Hough (+-12 % Radius, +-1 m Suchfenster: Einzelbilder bis 0,85 m versetzt), Normierung, ECC-affin auf das schaerfste Foto, Gold (HSV) als Mehrheit von 10 Fotos fuer r >= Innenradius; Zeiger nur aus dem schaerfsten Foto (bewegen sich). druckbar(): Striche < 0,8 mm (7 cm) auf 0,8 mm aufgeweitet, Glanzpunkte weg -> Ziffern werden Ziffernfelder (einzelne Striche bei 1:87 nicht druckbar). bauteile.uhren_aus_json baut audit/uhr_<fid>_<k>.npz ueber der gemessenen Wand (Feld 6 / Ring 10 / Gold +7 cm ANNAHME), sonst wie bisher Ring.
- Sackgassen: phaseCorrelate zur Ausrichtung (Antwort 0,0-0,3, eine Verschiebung 85 cm falsch); Wandniveau nur aus Putzzellen (1-m-Kachelstufen im Quaderteil); fusioniertes ortho_f00.png fuer die Uhr (Doppelbilder/verschmiert). Gen-Umgebung hat kein cv2 -> Putzkarte mit PIL/scipy.
- Probebau (Kopie im Scratch, Objektordner unberuehrt): vorher/nachher Ansicht Stadtseite: Kruemel weg, Uhr mit Ring + 12 Ziffernfeldern + Sonne/Stern sichtbar (vorher unsichtbar). Test tools/test_putz_uhr.py im Schnelltest.
- OFFEN: w00 (Feldseite, Wandgemaelde) behaelt Netzkruemel - Gemaelde ist im Bild Struktur, nicht Putz (anderes Kriterium noetig, z. B. Netz-Uneinigkeit); Fenster/Gesims auf w02 nur schwach (Netz-Relief); Hoehen Uhr = ANNAHME.

## UEBERGABE 21.11.2026 18:50
Stand in `.claude/UEBERGABE.md`, Nachtplan `modelle/PLAN_NACHT_2026-11-21.md` (einfache Agenten arbeiten die Schleife ab).

## 18:47 Agent Verdecker/Selbstbau (Vordach-Anschluss 19,39 -> ANNAHME 16,74 in Lauf 1121o)
- BELEGT (Kopien im Scratchpad, Kettendaten unberuehrt): fassade_ortho f00 1 cm mit vier Modellen. Kette 17:55 / STL 18:08 (mit Vordach): Messflaeche (relief_f00) liegt
  AUF dem eigenen Vordach (+1,14 m bei z 15,5-16, Hang bis +0,15 bei 19,5) -> Fotos sehen dort dieselbe Dachflaeche -> Dachband in uneinig_f00 geloescht (Median z 17-18,5: 18-22).
  Generator ohne Vorbauten (leere vorbauten_auto) und Fix: Flaeche = Wand (rel ~0), Dachband zurueck (28-36), Oberkante ~19,0-19,4 (Hand 19,43). Bild audit/verdecker_selbstbau_uneinig_f00.jpg.
- FIX generisch: tools/selbstbau_verdecker.py - Dreiecke im Vorbau-Raum (vorbauten_auto.json, u +-0,3, z Fuss..Anschluss +0,3) mehr als 0,15 m vor der vorderen von
  gemessener Wand/LoD2-Ebene raus (Schwelle ab gemessener Wand haette 50 m2 echtes Relief mitgenommen), das vom Generator weggeschnittene Wandstueck in der gemessenen Ebene
  geflickt (ohne Flicken Relief -0,60 = Blick in den Hohlraum). fassade_ortho nutzt das standardmaessig (--mit-selbstbau = alt; --waende-stl behaelt), schreibt verdecker_selbstbau
  in fassaden.json. vorbauten_bauplan.anschluss_aus_uneinig (ausgelagert) verwirft Karten 'im_modell'. Test tools/test_selbstbau_verdecker.py im Schnelltest.
- FEHLER/OFFEN: Der Stufen-Detektor (Mittel ueber u, 40 % der Fensterspitze) findet auch in der sauberen Karte KEINE Stufe: Fenstermaximum ist ein heller Balken z 19,5-20
  (43-45), die Wand darueber ist nicht mehr dunkel (25-30, alte Karte 20.11. dunkel). Ohne neuen Detektor bleibt der Anschluss ANNAHME 16,74 - der Fix allein holt 19,39 NICHT zurueck.
- GESCHWISTER (Modell als Verdecker/Flaeche fuer Messungen): fassade_ortho in fenster_ortho, fenster_ortho_fein, bauplan_innen_ortho(+_fein, Sicht-STL aus gebautem Modell) -> mit
  diesem Fix erledigt. steine_aus_foto (fassaden_kette, --stl gebautes Modell + Nachbarn): Vordach verdeckt Wandstreifen; nicht zirkulaer fuer die Steine, aber ein falsch
  platziertes Vordach verdeckt den falschen Streifen (Vorbau-Raum = 24 % von f00) - nicht umgestellt. relief_aus_fotos_mono (--stl gebautes Modell, Feld bis 10 m): Ueberlapp mit
  Vorbau-Raum nur z 8-10 m. rund_aus_umriss: 3014/6720 Umrissbeobachtungen verdeckt; der eigene Rundkoerper verdeckt die Tangentenpunkte (r0*1,08+0,05) nur, wenn der gebaute Radius
  > 8 % zu gross waere - geometrisch nicht zirkulaer, ohne Lauf. dach_profil_wolke: Achse aus dem gebauten Modell (inkl. eigenem Dachprofil) - schwach zirkulaer, nicht gemessen.
  umriss_tor/ebenen_abweichung/foto_diff: Modell ist der Pruefling (Tor), gewollt.
## 19:02 Agent Kettentempo (fassaden_kette parallel, Zwischenbau ohne Abnahme, modellkanten vektorisiert)
- FEHLERLISTE zuerst: (1) Die Feinrechnung `tiefe_lokal` (1121o: 550 + 622 s = 86 % von fassaden_kette) liefert NICHTS - w01 fein 0 %, w03 fein 1 % (127 Punkte im Feld). URSACHE (belegt): die Kette gibt `--fein pipe/dicht/sparse FV` = ENTZERRTES PINHOLE-Buendel (1200x1600) mit den VERZERRTEN Originalfotos (3000x4000); `bilder_anpassen` skaliert nur, die Verzeichnung (sfm/sparse/0: SIMPLE_RADIAL k ~0,2) fehlt -> Geometriefilter wirft alles weg. In 1121p brach w03 dazu mit Signal 6 ab -> fassaden_kette rc 3 -> bauen_mit_fassaden entfiel. NICHT angefasst (Messlogik); Abhilfe-Vorschlag: verzerrtes Buendel (sfm/sparse/0, gleicher Rahmen pruefen) oder Stufe abschalten bis repariert = -20 min je Lauf. (2) Mein erster A/B-Lauf (6 Waende gleichzeitig) loeste in 1121p um ~18:36 bei w04 einen CUDA-OOM in steine_aus_foto aus (w04 blieb wie in 1121o 'AUS', Ergebnis gleich, aber ein Absturz mehr im Bericht). Ursache: steine_aus_foto rechnet auf der GPU (render_kern), war nicht bekannt -> jetzt GPU_TEILE-Sperre. (3) 'bauplan_abweichung 460 s' gibt es in keinem Kettenlog (38-78 s); im Worktree gemessen 150 s unter Last.
- fassaden_kette: Waende in Threads (`_waende_parallel`, Ausgabe Wand fuer Wand in W-Reihenfolge), GPU-Teilwerkzeuge (steine_aus_foto, tiefe_lokal) ueber Semaphore: Plaetze = RCPARK_GPU_MB // 2300 (Kette 2500 -> 1 = nie mehr VRAM als seriell). CPU-Threads = min(Waende, Kerne/4, MemAvailable/2,6 GB; gemessen 2,5 GB Spitze je Wand). FASSADEN_PARALLEL=1 = seriell. Beleg (Worktree-Kopie, ohne --fein, unter Last): seriell 496 s -> parallel(3) 261 s, 42 Dateien (NPZ+JPG) bitgleich, fassaden_kette.json gleich.
- gesamtkette: `bauen()` - bauen_mit_fassaden/fenstern/bauplan/wolkenkoerpern bleiben (jede Folgestufe liest das STL: mono/fenster_ortho, umriss_tor, koerper_schleife, ebenen_abweichung/kantenstufe), aber als Zwischenbau RCPARK_NUR_BAUEN=1 (nur Generator, STL identisch); volle Abnahme einmal am Ende der Stufe bauplan bzw. des Laufs (`abnahme_nachholen` -> bauen_abnehmen.sh --nur-pruefen). RCPARK_ZWISCHENABNAHME=1 = alt. Gemessen: Generator 157/172 s (STL zweimal md5-gleich), Abnahme allein 48 s -> ~3 x 48 s gespart je Lauf.
- kantenstufe.modellkanten vektorisiert (79 s von 150 s in ebenen_abweichung): ganzes Schwabentor-STL 1 057 271 Punkte bitgleich, 9,2 -> 1,4 s; ebenen_abweichung 150 -> 57 s (Restunterschied 0,1 % = unbesetzter Zufall in sample_surface_even, kein Fehler).
- Test tools/test_kette_tempo.py (21) im Schnelltest; Schnelltest 0 Fehler. Cache-Ueberspringen (optional) nicht gebaut.
- 19:12 Lauf 1121p (git vor 8f40698cc, beschaedigt: fassaden_kette rc 3 durch w03 Signal 6 + w04 OOM aus Tempo-Agent-Test): 7/11 (vorher 4/11). PASST Galerie/Tor/Zeltdach/Treppenturm/Umgang/Eckquader/Durchfahrt. FALSCH Vordach 16,86 statt 19,43, Uhr 31,87 statt 31,25, Rundbogenfenster 1 statt 2, Laterne Spitze 53,44 statt 51,76. Bild: Tor beidseitig offen; Nord-/Westwand Relief kruemelig (Wandgemaelde w00); Sued/Ost glatt (keine Fotos). Gemergt: Selbstbau-Verdecker (a43dea) + Kette-Tempo (aaa66b), Schnelltest 0. Gestartet 1121q. Martinstor 1121b: Abbruch am Abdeckungs-Tor vor SfM (7/12 Sektoren, rc 2) - nebenher, offen.

## 21.11. Agent Anschluss-Stufe (Vordach f00: ANNAHME 16,74 -> gemessen 19,67-19,73)
- URSACHE: anschluss_aus_uneinig setzte voraus "Dachflaeche uneinig, Wand einig". Die echte Karte (fein_fix/ohne/wt/mit + Kettenkarte) hat Dachflaeche
  und Wand beide 25-36; hell ist nur die Anschlusslinie selbst (Balken 43-45 bei z 19,5-20) + eine senkrechte Stange (255) im u-Mittel -> 40 % der Spitze
  wird nie unterschritten -> "keine Stufe" -> ANNAHME. Messgroesse war falsch gewaehlt, nicht die Karte.
- FIX generisch (tools/vorbauten_bauplan.py): stufe_je_spalte = Zwei-Niveau-Zerlegung (kleinste SSE) des Lab-Wandbilds ortho_<fid>.png je 0,2-m-Spalte
  (Fotokante Dachdeckung -> Putz), stufenkante = Guard: zusammenhaengender Spaltenlauf >= 50 % der Spalten mit Bild, z-Band 0,5 m, Gewinn >= 0,5,
  Kontrast >= 30; dann Gegenprobe Uneinigkeit (Gipfel +-0,4 m >= 1,15 x Median ODER Niveauwechsel >= 15 %). Sonst None -> ANNAHME bleibt.
- GEMESSEN f00 (z_traufe 16,02, u -3,9..4,58): fein_fix 19,72, fein_ohne 19,73, fein_wt 19,71, fein_mit/Kettenkarte 19,68; voller vorbauten_bauplan-Lauf
  auf Kettendaten (Ausgabe Scratchpad) 19,67. Handstand 19,43 +- 0,4 (nur Pruefung): +0,24..+0,30, innerhalb. Geschweifte Dachseiten fallen aus dem Lauf.
- FEHLER/OFFEN: rechter Teil (u ~+0,9..+2,8) aus anderem Foto liegt bei 20,04 (Naht im Wandbild, +0,35 gegen links 19,60-19,73); Verdacht: Oberkante
  steht etwas vor der Wand -> in Untersicht-Fotos zu hoch projiziert (systematisch +). Nicht korrigiert (keine freien Faktoren).
- GEGENPROBE keine erfundene Stufe: f00 bei fuenf anderen Hoehenbaendern (Fenster, Leitungsschatten, Traufunterseite 42 %) und f02-f07 -> alle None.
  Test tools/test_anschluss_stufe.py (Schnelltest), test_selbstbau_verdecker.py um ortho_f00.png ergaenzt.

## 19:35 Agent Feinrechnung (tiefe_lokal 'fein 0 %' + Signal 6)
- FEHLERLISTE: (1) Ursache belegt an Code und Daten: gesamtkette gab `--fein pipe/dicht/sparse fotos` = ENTZERRTES Buendel (PINHOLE 1200x1600) + VERZERRTE Originalfotos (3000x4000; Quellbuendel sfm/sparse_dicht SIMPLE_RADIAL, k1 -0,62..+0,78). bilder_anpassen skalierte PINHOLE auf 3000x4000 (sparse_teil w01/w03 nachgesehen) -> Verzeichnung fehlte -> w01 Loecher 99,95 %, w03 98,5 %. (2) Signal 6 w03 (1121p): letzte Tiefenkarte 18:36:51, Kernel globaler OOM 18:37:10 (15-GB-Rechner, parallele Waende + Fremdjobs); PatchMatch-Cache fest 12 GB, Fusion pycolmap-Standard 32 GB. Nicht reproduziert (Einzellauf Spitze 5,2 GB RSS, 1,6 GB VRAM) -> ANNAHME: RAM-Erschoepfung (bad_alloc -> abort).
- FIX: gesamtkette.fein_paar: sfm/sparse_dicht (sonst sfm/sparse/0; Posen bitgleich zu dicht/sparse = Rahmen von fused.ply/SFM-AUSRICHTUNG, geprueft 333/333) + Originalfotos; sonst dicht/sparse + dicht/images. tiefe_lokal.paar_pruefen: PINHOLE + andere Dateigroesse -> rc 2 in 1,4 s mit Meldung; fassaden_kette schaltet dann die Feinrechnung fuer alle Waende ab (fein_aus). Abdeckung < 10 % -> rc 3, kein Relief geschrieben. Cache = RAM/3 (1-6 GB). Neue Option --arbeit. Test tools/test_tiefe_lokal_paar.py (15) im Schnelltest, 0 Fehler.
- MESSUNG w01 (Objektkopie, JOB_GPU_MB 2500, max_size 3200): vorher 0,05 % Zellen mit Punkten, ~9 min; nachher 62,4 % roh / 76,4 % nach Lueckenfuellen, 453 420 Punkte im Feld, Hub p5-p95 28,8 cm, 1012 s (laenger, weil jetzt echte Tiefen; GPU teils mit Schnelltest geteilt). Bild angesehen: Quader mit Fugen klar, Schild als Loch, Fusszone (Boden/Passanten) Loch; Restneigung im Hoehenbild (oben +, Mitte -) = grossraeumiger Trend, nicht Steinrelief.

## 20:30 Agent Dachueberstand-Rueckschritt (1121p PASST -> 1121q 0,12 statt 0,9 m)
- FEHLERLISTE: (1) Ursache = Kettenstufe `bauplan_dachprofil_veto` (Commit 6aa5fc9ac, DOM1-Veto `--nur_veto`) - 1121q-Log: "56 Seiten-Scheiben auf die Laser-Isolinie gesetzt, groesster Ueberstand 3.80 m". In audit/dach_profil.json wurden die Traufscheiben z 36,94-38,94 von Ueberstand (hand_vergleich-Mass) 0,29/0,83/1,15/1,15/0,66 auf 0,12/... gesetzt -> Messwert 1,15 (1121p) -> 0,12 (1121q). (2) Mechanismus: `dom1_bilinear` interpoliert das 1-m-DOM1 ueber die Traufkante (Dachzelle 37 m neben Strassenzelle 0 m). Roh-DOM1 +d: Dachzellen 37,1 m bis r 6,75 m (Wand halb 6,07 -> Laser selbst zeigt ~0,8 m Ueberstand), bilinear schon bei r 6,25 nur 34,1 m -> Isolinie H>=37,44 auf der WAND (5,8-6,3 m) statt an der Traufkante. Vermutung "Isolinie trifft die Wand" bestaetigt; Wandebene der Messung (wand_halb) unveraendert, war NICHT die Ursache. (3) Nicht betroffen: Dachkoerper z 39,9-45 (das eigentliche Veto-Ziel, Hoehe +1,62 m) - dort keine Klippe, Ergebnis bitgleich.
- FIX (generisch, kein Handwert): `dom1_kachel.dom1_bilinear(..., klippe=)`: Zelle mit Ecken-Spanne > klippe (Traufe/Wand) bekommt den hoeheren Eckwert (Veto schneidet nur, was der Laser ausschliesst). `dach_profil_wolke`: `--dom1_klippe` 3,0 m (72 Grad je Zelle), VETO_VERSION 2 im Block dom1_veto (+ klippe_m, scheiben_vorher auch im Vollauf); `--nur_veto` rechnet von `scheiben_vorher` neu (nimmt Veto 1 zurueck). gesamtkette zieht Profile mit Veto-Version < 2 nach.
- MESSUNG ohne Rechenlauf (nur DOM1-Kachel + vorhandenes dach_profil.json, Kopie im Scratch): Veto 2 = 41 statt 56 Eingriffe, Ueberstand nach hand_vergleich-Formel 0,83 m (Handstand 0,9, Tol 0,3 -> PASST erwartet); Dachkoerper max. Halbbreite z 39,9-45 3,90 m wie Veto 1 (vorher 5,42). klippe 3/5 gleich, 2 m lockert den Dachkoerper (4,56) -> 3 m gewaehlt.
- Test tools/test_dach_veto_traufe.py (synthetisches 1-m-Raster, Aufschiebling, rasterparallel + 1,7/14/33 Grad; reproduziert 0,9 -> 0,50 ohne Klippe) + Zeile schnelltest.sh. UNGEPRUEFT (Rechenverbot waehrend 1121r): Neubau/STL, Seitenbild, hand_vergleich am echten Lauf, Hoehen-Tor hoehe_gegen_dom1, Wolkenkoerper-Abgleich (1121q 644022 -> 642319 evtl. mitverursacht).

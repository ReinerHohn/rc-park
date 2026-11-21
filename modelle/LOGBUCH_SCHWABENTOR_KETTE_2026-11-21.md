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

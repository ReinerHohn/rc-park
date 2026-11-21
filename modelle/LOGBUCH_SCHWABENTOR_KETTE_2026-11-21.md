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

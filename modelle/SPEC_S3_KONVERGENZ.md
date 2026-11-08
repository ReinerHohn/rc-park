# Spezifikation S3: Stufe 4 Konvergenzschleife (Fehlerkarte -> Kandidaten -> Tor -> naechster Lauf)

Ziel (Plan Abschnitt 3, Stufe 4; Nutzer 5.11.: "iterativ konvergieren, keine Handauswahl"): Jeder Lauf findet die Stellen, an denen das Modell den
Daten widerspricht, erzeugt daraus Kandidaten aus den vorhandenen Bauteilregeln, nimmt nur an, was das strenge Tor (S1b) besteht, und weist eine
monoton fallende LOKALE Kennzahl aus. Voraussetzungen: S1b (uebernahme_tor, Elementbuch, Kostenkarten in `bewerten`), S1a (ebene_oeffnungen).
Beweis nach `beweis-pflicht`: Stoertest mit bekannter Wahrheit, Kaufhaus (3 Laeufe), Martinstor (nicht schlechter), Bilder angesehen.

## 0. Eingaben je Lauf k (alles aus dem Laufordner, keine Handwerte)
- Stand k: `fest` (BAUTEIL_PARAM), STL, Elementdatei des Baus (`elemente_<tag>.json`), Elementbuch.
- Fotos: ALLE kalibrierten Fotos mit `buendel_tor.ok` (nicht nur 12; `param_suche.fotos_waehlen(od, None, ohne_nacht=True)` bzw. gleichwertige Auswahl, pruefen, ob `None` = alle geht; sonst ergaenzen).
- Dichte Wolke + Ausrichtung (`objekt.json["freiraum"]`), `fassaden.json` des Laufs (LoD2-Waende + Vorbauflaechen aus `fassade_ortho --waende-stl --min-flaeche` abgeleitet aus Pixel/m, siehe S4; bis dahin die vorhandene), geneigte Dachflaechen >= 20 m2 (wie `restfeld_fassade.py --dach`).

## 0b. Quellensperre Dach (Befund "Dach zu tief", 5.11. 19:22, STAND_2026-11-06.md)
Die dichte Fotowolke liegt auf glatten Ziegelflaechen 1,4 m zu tief (an Merkmalspixeln richtig, nahe Traufe -2,1 m, am First 0), waehrend LGL-LoD2/DOM1, Stadt-LoD2 und
Stadtmesh 2025 alle 0,6-1,6 m darueber liegen und der Rahmen stimmt (Boden +0,03, Fassade ohne Steigung). Deshalb: **Restfeld und Freiraum auf DACHFLAECHEN nutzen die dichte
Wolke NICHT.** Dachzellen bekommen `rest` aus DOM1 (Zellmaximum), Stadt-LoD2-Ebene und Stadtmesh (je getrennt, nicht gemittelt; Widerspruch > 0,5 m = Cluster-Art "quellen_widerspruch",
kein Kandidat). Wandflaechen und Vorbauten weiter mit Wolke (Fassade: Median-Abstand -0,13..-0,5 m, dort ist die Wolke plausibel, aber Fenster-/Nischenpunkte beachten).
Pruefstand: Blindheitszeile fuer Quelltyp `sfm_dicht`/`foto_freiraum`: "blind fuer Dachtiefe auf texturarmen Flaechen (Kaufhaus 5.11.: -1,4 m)". Parameter `first_versatz_m`/`dach_versatz_m`
duerfen nur uebernommen werden, wenn Stadtmesh ODER Stadt-LoD2 die Richtung bestaetigen (Tor-Buchstabe (f) "Dachquellen", nur fuer Dachparameter).

## 1. Fehlerkarte (`tools/fehlerkarte.py`, nur Messung)
Je Flaeche (Wand, Vorbau, Dach) ein Zellraster (u, z bzw. u, v) mit 0,10 m. Je Zelle:
- `n_fotos`: Fotos, die die Zelle sehen (Projektion der Zellmitte in das Foto, innerhalb Bild, nicht verdeckt laut foto_diff-Verdeckermaske; Sichtbarkeit gegen das Modell per Embree wie `fassade_ortho`).
- `rot`, `gelb`: Anteil der sehenden Fotos, in denen im Fenster 0,25 m um die projizierte Zellmitte eine Modellkante ohne Fotokante (rot) bzw. Fotokante ohne Modellkante (gelb) liegt. Quelle: Kostenkarten `kostenkarte.npz` (mkp, fkp, dF, dM) aus `bewerten` (S1b), Schwelle dF/dM > 1.0 (= tol).
- `rest`, `n_kam`: Restfeld (Daten - Modell, m) und Kamerazahl aus `restfeld_fassade.py` (Funktion importieren, nicht kopieren; falls das Werkzeug nur als Skript laeuft: in Funktion umbauen, Ergebnis bitgleich pruefen).
- `frei`: Freiraumverletzung (Strahlen durch Modellmaterial) aus `freiraum_fassaden.py` je Zelle, falls vorhanden.
Ausgabe: `<aus>/fehlerkarte_k<k>/<fid>.npz` + `<fid>.jpg` (vier Tafeln: gelb, rot, rest, n_fotos; Farbskala fest, Legende im Bild) + `cluster.json`.
Warum Zellen-Stimmen ueber Fotos und nicht die foto_diff-Treffer je Foto: in null6 s3_v9 ist der groesste "FEHLT"-Treffer von Foto 022 eine einzige
Komponente mit 2295 m Kantenlaenge (die gelben Kanten der ganzen Fassade haengen zusammen) - Einzelfoto-Komponenten lokalisieren nichts. Erst die
Uebereinstimmung mehrerer Fotos je Zelle trennt Bauteil von Textur (Pflaster, Ziegel, Schatten). Der lokale Kameraversatz je Foto (0,05-1,15 m in s3_v9)
ist dabei einzurechnen: Stimmen werden mit dem je Foto geschaetzten Versatz (`versatz` im foto_diff-JSON) verschoben, bevor sie auf die Zelle fallen.
**Cluster**: Zusammenhangskomponenten (8er-Nachbarschaft) der Zellen mit `n_fotos >= 3` und (`gelb >= 0.5` oder `rot >= 0.5`); je Cluster: art (gelb|rot), fid, Box u0,u1,z0,z1, Flaeche m2, mittlere Stimmen, `rest_median`, `rest_n`, `frei_anteil`, `fotos` (Liste der sehenden Fotos), `stand_elemente` (Elemente des Stands, deren Box den Cluster schneidet). Cluster < 0,25 m2 verwerfen (unter Druckaufloesung x 2). Sortierung nach Flaeche x Stimmen.
**Kennzahl** `F_k = sum ueber Zellen mit n_fotos >= 3 von (gelb + rot) x 0,01 m2` je Flaeche und gesamt. Nur diese Zahl entscheidet ueber Konvergenz (globales Freiraumvolumen ist NICHT monoton, versuche.jsonl 5.11. 17:00).

## 2. Kandidaten (`tools/kandidaten.py`, deterministisch, keine Suche hier)
Je Cluster hoechstens 3 Kandidaten aus den VORHANDENEN Bauteilregeln (`baukasten_gen.py`: fassade_auto-Klassen fenster/bogen/gaube/figur/oeffnung/ruecksprung, relief_wolke, bloecke_wolke, figuren_netz; Parameter in BAUTEIL_PARAM). Regeln allgemein, keine Objektnamen:
- gelb und `rest_median > +0.10` (Daten vor dem Modell): **Vorsprung** - auf Wand: relief/bloecke-Element mit Box = Cluster-Box und Tiefe = rest_median; auf Dach: Klasse gaube (Box, Tiefe aus rest).
- gelb und `rest_median < -0.10` (Daten hinter dem Modell): **Ruecksprung/Nische** (Klasse ruecksprung bzw. oeffnung, wenn z0 <= 0,5 m ueber Boden oder `frei_anteil > 0.3`; Tiefe = |rest_median|, bei Durchblick die Freiraumtiefe).
- gelb und |rest| <= 0,10 oder `rest_n` klein (keine Tiefe gesehen): **Flaechenelement** - Ortho-Ausschnitt des Clusters durch `fassade_parsing` (OWLv2) mit Klassen fenster/gaube/figur/balkon, Mindestflaeche aus Pixel/m des Ausschnitts (nicht 20 m2); Treffer -> Element mit gemessener Box; kein Treffer -> Kandidat "textur" (wird nur protokolliert, nicht gebaut).
- rot (Modellkante ohne Foto) und `stand_elemente` nicht leer: **Feinlage** des Elements - Verschiebung u und z um +-0,25 m und Breite x 0,8/1,2 (6 Kandidaten -> die 3 mit geringster lokaler Kennzahl im Elementbuch-Vorabcheck), sowie **Entfernen** des Elements.
- rot ohne Element: Kandidat "parameter" fuer das Bauteil, dessen Kante dort liegt (ueber die Elementdatei/Beleg), mit dem Suchbereich aus `PLAN_STANDARD_qualitaetsstufen.json` (param_suche auf den sehenden Fotos).
Jeder Kandidat = (`fest'`, Elementdatei') + Beleg `quelle: "fehlerkarte Lauf k, Cluster c: <art>, <n> Fotos, rest <m>"` (Regel 3b). Schwellen (0,10 m, 0,5 Stimmen, 0,25 m2, 3 Fotos) stehen als Plan-Schluessel `konvergenz: {...}` mit Standardwerten und werden im Bericht genannt (keine versteckten Festwerte; `hardcode_finden.py` ausfuehren).

## 3. Lauf (`qualitaetsstufen.py` neues Verfahren `konvergenz`, cfg: `laeufe`, `max_kandidaten_je_lauf` (Standard 8), `konvergenz`-Schwellen, `tor_*`)
Je Lauf: Fehlerkarte -> Kandidaten (sortiert) -> je Kandidat: bauen, auf den sehenden Fotos messen (Kostenkarten), `uebernahme_tor` (S1b, alle Buchstaben inkl. Elementbuch) -> bei Annahme wird der Kandidat der neue Stand (greedy, sequentiell), sonst Grund-Buchstaben ins Log. Nach dem Lauf: neue Fehlerkarte, `F_{k+1}`; Abbruch, wenn (i) der GRENZWERT erreicht ist (Nutzer 5.11.: "bis es zum festgelegten Grenzwert konvergiert"; Plan Abschnitt 1:
je Fassade mit >= 3 Kameras gelb < 0,25 und rot < 0,10 im Mittel ueber die sehenden Fotos, als Plan-Schluessel `ziel_gelb`/`ziel_rot`), (ii) kein Kandidat angenommen wurde,
(iii) `F` um < 1 % fiel oder (iv) das Zeitbudget (cfg `minuten`) erreicht ist. Der Grund steht im Bericht; nur (i) heisst "konvergiert". `stand.json` je Lauf fortsetzbar; Bericht je Lauf: Tabelle Cluster -> Kandidat -> Ergebnis (Buchstaben), `F` je Flaeche, Bild vorher/nachher fuer die 3 groessten Cluster (Foto-Overlay + Fehlerkarte).
Platzpruefung vor jedem Lauf (`platz_pruefen.py`), Kostenkarten nur fuer Stand und angenommene Kandidaten behalten.

## 4. Beweise (`tools/test_konvergenz.py`)
- **T1 Stoertest (Wahrheit bekannt)**: Wahrheit = null6 `modell_s3_v9` (fest + Elementdatei). Synthetische Fotos aus den echten Kaufhaus-Kameras (Mechanik von `test_foto_diff.py`: Pruefbilder mit Albedo, Rauschen, k1, Verdeckerkasten), synthetische Wolke (Oberflaechenpunkte der Wahrheit, 5 cm Rauschen, nur sichtbar von den Kameras). Stoerungen, je einzeln: (a) ein Bogen zugemauert (Element entfernt), (b) Erkerblock-Tiefe -0,5 m, (c) eine Gaube 1,0 m verschoben, (d) ein Fenster entfernt. Erwartung je Fall: Cluster an der richtigen Stelle (Box ueberlappt Wahrheit >= 50 %), ein Kandidat angenommen, Geometrie nach <= 2 Laeufen innerhalb 0,10 m der Wahrheit, `F` faellt. Gegenprobe: ungestoerter Stand -> kein Kandidat angenommen (Tor lehnt alle ab oder keine Cluster >= 0,25 m2).
- **T2 Kaufhaus echt**: Start = null6 s3_v9, 3 Laeufe, `F` monoton fallend, Pruefstand gruen bleibt (Arkade 4, druckbar), Bilder je Lauf angesehen und in 2 Saetzen beschrieben (Foto 004 und ein Seitenfoto).
- **T3 Martinstor**: Start = Objektstand, 1 Lauf; Erwartung: `F` nicht groesser, Pruefstand gruen, Regression `--pruefen` identisch (Werkzeugaenderung 8b), alle Ablehnungen mit Buchstabe im Log.
- **T4 Determinismus**: Lauf 1 zweimal mit gleichem Stand -> gleiche Cluster-Liste und gleiche Entscheidungen (Raster ist saatunabhaengig; sonst Ursache nennen).
Werte nicht nachjustieren; wenn ein Test faellt: Ursache, STOPP, Bericht.

## 5. Nicht aendern / Grenzen
`foto_diff.py` (S2), `pruefstand.py` ausser neuer Messer nur mit Beleg; keine Objektnamen oder -zahlen im Code; keine neuen Bauteilklassen (Rippengewoelbe, Bruestung) in diesem Schritt - sie entstehen spaeter aus wiederkehrenden "textur"-Clustern (Liste im Bericht).

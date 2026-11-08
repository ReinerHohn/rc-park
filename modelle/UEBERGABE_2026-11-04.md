# Übergabe 2026-11-04 (Kaufhaus-Nullstart, Beweispflicht, Kamera-Tor, foto_diff)

Nutzerregel des Tages: **Jede Erkenntnis im Nullstart muss bewiesen sein.** Dazu gehören ein Tor im Nullstart, ein synthetischer Test mit bekannter Wahrheit, zwei echte Objekte (Kaufhaus und Martinstor) und ein angesehenes Overlay. Ein neues Gebäude bekommt den Martinstor-Umfang ohne Handarbeit (Memory `beweis-pflicht-nullstart`).

## Laufende Jobs (Stand 17:00)

| Job | Was | Log |
|---|---|---|
| `kh_null4` | Frischer Nullstart von Null mit allen neuen Schritten (Ziel `modelle/kaufhaus_null4` → Datenplatte). Merkmale fertig (GPU, 38 min). Danach 12 Mapper (CPU), dicht (GPU), dann kameras → kamera_bruecke → … → beweise. | `/media/oem/scan/rc-park_null/kaufhaus_null4.log` |

Wenn `kh_null4` fertig ist:
- `python3 tools/test_nullstart_schritte.py --bericht modelle/kaufhaus_null4/nullstart_bericht.json` laufen lassen.
- Die Ergebnisse ansehen: `audit/beweis_anker_uebersicht.jpg`, `foto_diff_*`, `wolke_vs_modell_*`, `overlay_*`.

Abgebrochene oder halbfertige Ziele, die gelöscht werden dürfen (Nutzer hat Löschen erlaubt, das Werkzeug hat es blockiert):
- `rc-park_null/kaufhaus_null3` (abgebrochen, 72 MB)
- `martinstor_mly`, `martinstor_nullA`/`B`, `hybrid_test`, `bilder_schleife_test`, `test_beschnitt`, `stufen_2026*`, `beweis_2026*` (zusammen etwa 7 GB, keine Verweise außer eigener Symlinks)

## Was jetzt im Nullstart steckt (`tools/nullstart.py`)

Schritte: … `buendel`, `generator0`, `dicht`, `entzerren`, `video`, **`kameras`, `kamera_bruecke`**, `kalibrieren`, **`beweis_anker`, `kamera_lod2`, `textur`, `abgleich`, `wolke_seiten`**, `auswertung`, `overlay`, `hybrid`, `vergleich`, **`beweise`**.

- **`entzerren`** wird beim Netz „alle“ mit Begründung übersprungen. Vorher: KeyError und Abbruch.
- **`kalibrieren`** fasst nur K-Dateien mit Picks an, Bündelkameras werden nicht überschrieben.
- **`kameras`** = `kameras_aus_buendel.py`: K-Kamera für jedes Bündelfoto.
- **`kamera_bruecke`** = `tools/kamera_bruecke_pruefen.py` (neu, siehe unten): Tor je Kamera, schreibt `K.kamera.buendel_tor`.
- **`beweis_anker`** = `tools/beweis_anker.py` (neu): amtliche Anker ins Foto, Bild zum Ansehen.
- **`kamera_lod2`**: prüft nur, schreibt nichts (Status offen, siehe unten).
- **`textur`**: `tiefen_kameras` und Texturatlas mit 2,5 cm Texelgröße, auf der Datenplatte.
- **`abgleich`**: `foto_diff` und `fehlteile` NUR für Kameras mit `buendel_tor.ok`, `lod2_tor.ok` oder Handkalibrierung. Der Schritt ist nur dann ok, wenn mehr als 0 Fotos verglichen wurden.
- **`wolke_seiten`**: `wolke_vs_modell.py --auto-rahmen` je Seite. Exit 3 bei einer Seite ohne Wolke; vorher NaN-Versatz und leeres Ergebnis mit rc 0.
- **`beweise`**: `tools/test_nullstart_schritte.py --bericht …` schreibt `nullstart_beweise.json`.
- **Pflichtliste** `tools/nullstart_pflicht.json` mit 15 Einträgen (Schritt, Werkzeug, Erkenntnis, Tor, Beweisdatei, Test, Status). Stand: 9 bewiesen, 4 teilbewiesen, 2 offen (`kamera_lod2`, `wolke_seiten_`).
- **Test** `tools/test_nullstart_schritte.py`:
  - statisch: Jedes Pflicht-Werkzeug wird aufgerufen (Gegenprobe: Werkzeug entfernt → Test fällt durch).
  - mit `--bericht`: Der letzte Eintrag je Schritt ist ok, und die Beweisdatei ist da.

## Kernerkenntnisse (bewiesen)

1. **Statischer Test reicht nicht.** Erst der echte Lauf fand drei Fehler:
   - `import bauteile` fehlte.
   - `trimesh` fehlt im colmap-venv; die STL-Höhe wird jetzt mit numpy gelesen.
   - Martinstor-Festwerte in `foto_overlay.py` (Fotoordner, 0,087) und `wolke_vs_modell.py` (Turm um den Ursprung, u ±9 m, Bänder 6–34 m).

   Allgemein gilt: **rc 0 mit leerem Ergebnis ist ein stilles Falsch-OK** und muss Exit 3 werden.
2. **Brennweiten-Prior** nur halten, wenn der Mapper ±15 % bestätigt (`sfm_netz.py`, `*_prior_pruefung.json`).
3. **Bündel** (`sfm_lod2_buendel.py`): grobe Beobachtungen mit Gewicht 0 (`BUENDEL_AUS_PX`), Tor mit Exit 3. Das neue Kaufhaus-Netz hat 0,84 px; die Kameras stehen 1,65 m über dem Boden, das Dach passt auf 0,06 m.
4. **LoD2 ist ungenauer als die Bündelkameras.**
   - Kaufhaus 004: Der LoD2-First liegt auf Höhe der Stufengiebel-Spitzen, 40–50 px über dem echten First. Das linke Nachbardach liegt 30–40 px zu hoch. Die rechte Nachbartraufe und die Bodenanker passen.
   - Maßvergleich an 20 echten Fotos: Die Kanten-Trefferquote gegen LoD2 ist an der Bündelkamera nicht besser als bei 2° Verstellung. Ein Kamera-Tor je Foto gegen LoD2 ist damit der falsche Maßstab.
   - Skripte: `/media/oem/scan/rc-park_null/erkundung_2026-11-04/mass_vergleich.py`, `zeige.py`.
5. **Neues Kamera-Tor** `tools/kamera_bruecke_pruefen.py` prüft die Kette SfM-Beobachtungen → Ausrichtung → Rahmen → K-Kamera.
   - Tor: Median ≤ 0,15 %, p90 ≤ 0,5 % der langen Seite, mindestens 30 Beobachtungen.
   - `--selbsttest` verstellt Drehung 0,2°, f 1 %, Lage 0,3 m und Rahmen 0,1 m. Jede Verstellung mit einer Bildwirkung über dem 1,5-Fachen der Grenze muss durchfallen.
   - Kaufhaus: 96/96 im Tor (Median 1,17 px), 310/310 Verstellungen abgelehnt.
   - Martinstor (`martinstor_lod2`): 23/23 (0,76 px), 0 Falschannahmen.
   - Das Bündel selbst bleibt global durch das Bündel-Tor, `beweis_anker` und `foto_overlay` geprüft.
6. **`kamera_lod2_nachfuehren.py`** (Status offen, nicht mehr Voraussetzung für den Abgleich):
   - Behoben: Punkte außerhalb des Bildes werden gekappt (vorher Randwert per `bilin`, der Optimierer floh). Neu sind Cauchy-Verlust, f_scale 0,5 und eine Nachstufe.
   - Synthetisch: Kaufhaus bestanden, Martinstor nicht (senkrechte Kanten, Fangbereich < 0,5°).
   - Echt: 2/96 bestanden, davon 064 falsch (Kanten auf dem Filmscan-Rahmen). Das Prüfbild war zu sauber.
7. **`foto_diff.py` war praktisch blind.**
   - Die Glättung von 0,18 m × px/m ergab bei hochaufgelösten Fotos 10–28 px. Danach lag der Canny-Gradient unter der Schwelle: nur 97 Fotokantenpixel in der Silhouette, also „100 % falsch, 0 % fehlt“. Auch Martinstor 061 war betroffen (0 %/0 %).
   - Neu im Repo seit 17:00:
     - Fotokanten auf einer Arbeitsauflösung mit Glättung = 2 px (`--glaett-px`)
     - `--bild`/`--aus` für Beweisläufe
     - Rahmen aus `K.rahmen_verschiebung` (vorher bei jeder STL neu berechnet, das Modell verrutschte bei Bauteiländerungen)
     - Optionen `--kanten netz` (exakte Netzkanten plus Embree-Sichtbarkeit) und `--dichte-max` (Feinfilter), beide noch Entwurf
   - Alte Version: `/media/oem/scan/rc-park_null/foto_diff_vor_2026-11-04.py`.
8. **Test `tools/test_foto_diff.py`** (neu): Das Foto ist ein Render des Modells.
   - Testfälle: T1 wahr, T2 0,6 m versetzt, T3 erfundener Kasten, T4 fehlender Kasten. T3/T4 werden über die Bildlage gegen T1 als Grundlinie geprüft.
   - Fallen im Prüfstand, alle behoben: Punktrender löchrig (dicht rendern, ≤ 2000 px, 20 Mio. Punkte); Zufallsalbedo gab zufällig gleich helle Nachbarflächen (jetzt zwei Lichter plus cos(2,3·Ebenenabstand)); ein Tiefen-Sinus erzeugte Streifen; der Kasten steckte im Balkon (jetzt auf ruhiger Fläche, zur Kamera ausgerichtet).
   - **Kaufhaus 004: alle 4 bestanden**, bestätigt mit dem installierten `tools/foto_diff.py` (Lauf `test_fd_kh`, 17:20): T1 3,1 %, T2 19,4 %, T3 91 m, T4 90 m (jeweils gegen 0 m ohne Kasten).
   - **Martinstor 014: nicht bestanden.** T1 liegt bei 43–61 %. Die Tiefenbild-Kanten übersehen Details; die Netzkanten erfassen Details unter der Fotoauflösung (Ziffern, Ziegel, Fensterkreuze). Der Feinfilter nach Kantendichte half nicht. **Nächster Schritt:** Modellkanten und Fotokanten auf derselben Skala vergleichen, also Modellkanten auf die Arbeitsauflösung bringen. Oder Details unter der Glättung schon im Netz ausfiltern (Kantenlänge, Abstand paralleler Kanten).
9. **Erster echter Abgleich** (`kaufhaus_null2`, 96 Fotos, noch mit dem alten `foto_diff`): Die Kennzahlen sind ungültig (Fehler 7). Das Bild von 004 mit der Korrektur zeigt: Der echte First liegt tiefer als im Modell, die Arkadenbögen sind zu breit und versetzt, die Gauben zu hoch. Muss nach dem neuen `foto_diff` erneut laufen.
10. **`wolke_vs_modell --auto-rahmen`**: Die Hauptfassade ist brauchbar (Bild `audit/wolke_vs_modell_ost.png`). Das Dach liegt in der Wolke tiefer als im Modell, die Stufengiebel ragen über den Wolken-Umriss. Die Tiefen sind laut Werkzeug unsicher.
11. **`foto_overlay.py`** ist generisch (96/96 statt 96 Abstürze), zeichnet aber noch verdeckte Kanten.

## Offene Aufgaben (Reihenfolge)

1. Den `foto_diff`-Beweis am Martinstor lösen (siehe 8). Kaufhaus besteht bereits. Erst dann Status „bewiesen“ in der Pflichtliste (jetzt: teilbewiesen).
2. Abgleich auf `kaufhaus_null2` mit dem neuen `foto_diff` wiederholen: `nullstart.py … --ziel kaufhaus_null2 --ab abgleich`. Die Treffer ansehen.
3. Ergebnis von `kaufhaus_null4` prüfen (Beweise, Overlays).
4. **COLMAP mehr GPU (Nutzerwunsch):**
   - pycolmap 4.2.1 hat CUDA und `IncrementalPipelineOptions.ba_use_gpu`/`ba_gpu_index`, ungenutzt in `sfm_netz.py`.
   - Messen: gleiches Netz mit und ohne `ba_use_gpu` (Zeit, Netzgüte, Reproduzierbarkeit), mit `aufwand_log.py`.
   - Achtung: 12 parallele Mapper teilen sich eine GPU (Register AY/BA, Absturzgefahr neben SIFT-GPU). Eine Lösung wäre, nur den besten Versuch mit GPU zu verfeinern.
   - Außerdem prüfen: GLOMAP global mapper und GPU-Matching.
5. `beweis_anker.py`: verdeckte Anker markieren (Strahltest gegen LoD2). Ohne das wirkt 005 falsch.
6. `foto_overlay.py`: verdeckte Kanten ausblenden.
7. **Fehlende Pipeline-Stufen** (mit dem Nutzer besprochen):
   - (a) Automatische Korrektur: Abweichungen aus `foto_diff` und `wolke_seiten` werden zu Generator-Parametern, mit Schleife — höchster Nutzen.
   - (b) Bauteile erkennen (Fassade zerlegen: Fenster, Bögen, Gauben, Erker) → Bauteilliste für den Generator — Schlüssel zur Verallgemeinerung.
   - (c) Abdeckung je Seite prüfen und neue Quellen vorschlagen.
   - (d) Druckaufbereitung (Details < 0,8 mm, Teile, Farben).
   - (e) Abschlusstor „Modell fertig“.
8. Martinstor-Süd weiter offen (neue Datenquelle nötig). Artifact Q16SrTczgtRMB7iTEXqHu8 erst danach aktualisieren.

## Neue und geänderte Dateien (nicht committet)

- **Neu:** `tools/kamera_bruecke_pruefen.py`, `tools/test_nullstart_schritte.py`, `tools/nullstart_pflicht.json`, `tools/beweis_anker.py`, `tools/kamera_lod2_nachfuehren.py`, `tools/test_kamera_lod2.py`, `tools/kameras_aus_buendel.py`, `tools/test_foto_diff.py`
- **Geändert:** `tools/nullstart.py`, `tools/foto_diff.py`, `tools/foto_overlay.py`, `tools/wolke_vs_modell.py` (`--auto-rahmen`, Exit 3; Martinstor-Regression identisch), `tools/sfm_netz.py`, `tools/sfm_lod2_buendel.py`, `tools/textur_projektion.py`, `tools/fehlteile_finden.py`
- **Versuchslog Kaufhaus** (heute): netz-prior-festhalten-verbiegt, buendel-grobe-beobachtungen-gewicht0, textur-atlas-fotopixel, kameras-aus-buendel-anker-probe, kamera-lod2-kanten-nachfuehren-v1, beweis-kamera-lod2-synthetisch, beweis-prior-pruefung-lod2-ecken, kamera-lod2-cauchy-randkappung-beweis, nullstart-pflichtliste-schritte-beweis, kamera-bruecke-statt-lod2-tor
- **Martinstor-Regression** nach allen Werkzeugänderungen: identisch (`mt_regression3.log`). `foto_diff` steht nicht in der Regressionskette.
- Versehentlich erzeugt: `modelle/martinstor/audit/foto_diff_061.*` (untracked, alte `foto_diff`-Version).

## Fortsetzung 4.11. ab 16:50

**foto_diff-Beweis Martinstor (Aufgabe 1): Zwei Fehler lagen im Beweis selbst, beide behoben. Danach ist der Beweis noch nicht gelöst.**
- **Kamera-Fehler:** Test und Werkzeug lasen verschiedene K-Dateien. `martinstor_lod2`: Die Masstabelle zeigt auf `martinstor_null`, dort liegt die Handkamera (RMS 92 px, f 4059 statt 3858).
  - Neu ist `fehlteile_finden.k_datei()` (Objektordner vor Masstabellenordner), genutzt von `foto_diff`, `fehlteile` und `test_foto_diff`.
  - `foto_diff` meldet jetzt `kamera_datei`/`f_px`/`cx`/`cy`. Der Test prüft als T0 die Kameragleichheit.
  - T1 sank dadurch von 55 % auf 33 %.
- **T2-Fehler:** Bei Hochkantfotos lag der Versatz fast in Blickrichtung (nur 6 px ≈ 0,13 m < tol).
  - Jetzt waagerecht quer zur Blickrichtung, und der Bildversatz wird geometrisch nachgewiesen (`T2_bildversatz_m`).
  - Die Phasenkorrelation taugt dafür nicht, weil beide Prüfbilder dasselbe Rauschen haben.
- **Kaufhaus 004 mit dem korrigierten Test:** weiter bestanden (T1 3,1 %, T2 19,4 %, T3 91 m, T4 90 m). Martinstor-Regression identisch.
- **Entwurf `--kanten normalen [--modell-glatt 1] [--richtung 22.5]`:** Knick/Sprung aus den Render-Normalen auf der Arbeitsauflösung der Fotokanten, mit bereinigter Tiefe und zur Kamera gedrehten Normalen.
  - Martinstor: T1 20 %, T2 25 %. T2 trennt sich nicht dreifach, denn in einer dichten Fassade findet jede Kante irgendeine Fotokante in tol.
  - Kaufhaus: T1 7 %, T2 56 %, aber 95 % der Fotokanten bleiben ohne Modellkante (Ursache noch offen).
  - Der Standard bleibt `tiefenbild`.
- **Nächster Schritt:** Versatz als Schätzung statt als Anteil, etwa über die Kreuzkorrelation der Kantenbilder je Richtung. Außerdem klären, warum die Normalenkanten am Kaufhaus so spärlich sind.
- Versuchslog Martinstor: `foto-diff-beweis-kamera-gleich-t2-richtung`. Die Pflichtliste steht weiter auf „teilbewiesen“.
- Rendern ohne GPU (wenn ein GPU-Job läuft): `RENDER_CPU=1 CUDA_VISIBLE_DEVICES=` vor `foto_diff`/`test_foto_diff`, etwa 7 s je Foto.

**COLMAP-GPU (Aufgabe 4):**
- `sfm_netz.py --ba-gpu` setzt `ba_use_gpu` (Standard aus).
- Job `ba_gpu` (Skript `erkundung_2026-11-04/ba_gpu_messung.sh`, Log `rc-park_null/ba_gpu_messung.log`): Er wartet auf `JOB_ENDE` von `kh_null4` und rechnet dann Seed 10 nacheinander, einmal auf der CPU und zweimal auf der GPU. Ausgabe `--tag bacpu/bagpu1/bagpu2`, Aufwand in `erkundung_2026-11-04/aufwand`.
- Danach bewerten (Zeit, Sigma, Kamerazahl, Wiederholbarkeit) und erst dann in `nullstart.py` einbauen. Variante: nur der beste Versuch auf der GPU nachrechnen.

**Stand 18:00: Der foto_diff-Beweis ist an beiden Objekten BESTANDEN (Pflichtliste: bewiesen).**
- Neuer Standard: `--kanten normalen --modell-glatt 1` plus Versatzschätzung (`versatz` im JSON, „deutlich“ ab Gewinn 0,08; ANNAHME).
- Beweiswerte:
  - Kaufhaus 004: T1 15 %, T1v 0,03 m, T2v 0,61 m.
  - Martinstor 014: T1 23 %, T1v 0,02 m, T2v 0,61 m.
  - T3 und T4 bestanden.
  - Der Test definiert T2 jetzt als „Anteil ODER Versatzschätzung“. T1v ist neu und Pflicht.
- Echte Fotos angesehen:
  - Kaufhaus 004: weniger Falschkanten als mit `tiefenbild`, rot sind Giebelspitze und Arkadenbögen.
  - Martinstor 014: Struktur grün, rot sind zwei Gesimslinien. Ein senkrechter Versatz von ~0,55 m ist bei beiden Kantenarten gleich, aber nicht deutlich (Gewinn 0,06), also ein Hinweis und kein Befund.
- `kh_null4` → `abgleich` läuft bereits mit dem neuen Standard.

**Arbeitsliste vom Nutzer beauftragt (18:10): nach `kh_null4` und `ba_gpu` abarbeiten, in dieser Reihenfolge.**
1. `foto_diff`: Verzeichnung k1 berücksichtigen (Foto entzerren), Beweis T5 mit verzerrtem Prüfbild.
2. `foto_diff`: Verdecker maskieren (Himmelsmaske, Tiefenkarten aus `dicht`).
3. `foto_diff`: lokaler Versatz je Bauteil oder Bildbereich.
4. Mehrfoto-Bewertung (dieselbe 3D-Stelle in mehreren Fotos = Befund).
5. Schwelle „deutlich“ (0,08) statistisch belegen.
6. Pipeline:
   - (a) automatische Korrektur
   - (b) Bauteile erkennen
   - `beweis_anker`/`foto_overlay` verdeckt
   - `kamera_lod2`
7. Rechenzeit: `ba_gpu` auswerten, GLOMAP, `foto_diff` auf GPU.
8. `test_foto_diff` in die Regression bzw. den Schritt `beweise`.

**Stand 19:00 (Punkte 1, 2 und 7 teilweise erledigt):**
- **Verzeichnung:** `foto_diff` entzerrt das Foto mit k1 (`fehlteile_finden.foto_entzerren`). Die Prüfbilder tragen k1, die Gegenprobe T5 (Martinstor ohne Entzerrung) fällt durch.
- **Verdecker:** `foto_diff --tiefen auto` blendet aus, was die Tiefenkarte deutlich näher zeigt als das Modell. Ein Tor prüft dafür, dass Tiefen- und K-Kamera übereinstimmen.
  - Grund: `martinstor_lod2/sfm/dicht_nord` stammt aus einem anderen Netz (1,8°/7,7 m) und hatte 73 % des Turms ausgeblendet.
  - Beweise T6, Gegenprobe und T6b an beiden Objekten bestanden. T6-Anteil gegen T1 + 0,05 (Nutzerentscheid).
- **GPU:** Ceres-GPU bringt bei ~100 Bildern keinen Gewinn (195 s CPU ungestört gegen 207–212 s GPU), CASPAR ist im inkrementellen Mapper gesperrt (Versuchslog Kaufhaus `colmap-ba-gpu-ceres-caspar`). Merkmale, Matching und `dicht` laufen schon auf der GPU.
- **`kh_null4`:** fertig, rc 0, alle 15 Pflichtschritte ok.
  - Bei `wolke_seiten_west` fehlt die Begründung im Bericht (nur „None“).
  - Im Abgleich (vor Verzeichnung und Verdecker) sind 22 von 87 Fotos „deutlich versetzt“; nach dem neuen `foto_diff` erneut prüfen.
- **Nutzerentscheid 19:00, nächste Schritte:** Commit; dann lokaler Versatz je Bildbereich bzw. Bauteil (Punkt 3) mit Mehrfoto-Bewertung (Punkt 4); dann automatische Korrektur der Generator-Parameter (Punkt 6a).
  - Erster Parameter: Dachversatz für `rumpf_lod2`, weil der LoD2-First auf Höhe der Stufengiebel-Spitzen liegt.
  - Danach die Treppengiebel-Maße (heute als ANNAHME gesetzt).
  - Die statistische Absicherung (5) und die echte GPU-Beschleunigung von `foto_diff` (7) sind zurückgestellt.

## Stand 4.11. spaet (nach 21 Uhr)
- **param_suche** (generisch, ein Generatorparameter gegen Fotos): feste Bewertungsmaske (`kosten_param`), Prozess-Pool (alle Probewert x Foto, Arbeiter nach RAM/VRAM), Deutlichkeitstor (gepaarter t, beidseitig >= 2), Einzelfoto-Kosten im Bericht. Beweis `test_param_suche.py` BESTANDEN (CPU und GPU).
- **foto_diff GPU-Fassung** (`--gpu` / `FD_GPU=1`, Standard in param_suche, `--cpu` zurueck): Abtastung + Z-Puffer + Versatzsuche auf torch. Bewiesen: test_foto_diff T0-T6b (Kaufhaus 004, Martinstor 014), test_param_suche, `tools/test_gpu_gleichwertig.py` (GPU-CPU <= 2x CPU-Saatwechsel, `FD_SAAT`). foto_diff allein bleibt CPU (Regression stabil). Regression Martinstor identisch.
- **Kaufhaus Dach**: Foto-Suche First -1,28 m (deutlich) gegen LoD2/DOM1 (stimmen ueberein) = offener Widerspruch in `kaufhaus_null4/masstabelle.json` (mit Diagnose und naechstem Schritt). NICHT uebernommen.
- **Luecken**: martinstor_lod2 Buendelkameras ohne `buendel_tor` -> fotos_waehlen findet keine; Kaufhaus ohne Regressions-Schnappschuss; Bildkette (Canny/Abstandskarten/Normalenkanten) noch CPU, RAM 2,2 GB je Arbeiter -> nur 4 parallel.
- **Platz**: /media/oem/scan von 0 auf 26 GB frei (Archiv /media/oem/Volume/scan_archiv, LIESMICH.txt). Nutzer loescht noch: `rm -rf /media/oem/scan/{cuda12,colmap-test,colmap-build,vggt}` (geprueft archiviert).
- **Regel neu im Gedaechtnis**: immer maximal parallel UND GPU, GPU-Frage beim Entwurf stellen.
- **GPU Schritt 2** (Normalenkanten, nrm/pos, Verdecker auf GPU) alle 5 Beweise BESTANDEN, Regression Martinstor identisch.
- **Pruefwerkzeuge** (22 Uhr): `foto_rendern` bitgleich 2-4x schneller (Schluessel je Dreieck), Pruefbilder + foto_diff-Faelle + Wahrheiten parallel, Arbeitsordner Datenplatte; Gegenbeweis identisch (fd Kaufhaus 45 s, Martinstor 50 s, param_suche 245 s). Engpass jetzt RAM (3,6 GB je Render).
- **Pruefbilder exakt gerastert** (23 Uhr, `render_kern.dreiecke_rastern`): alter Martinstor-Beweis bestand nur per Saat-Glueck (T1 je Saat 24,8-32,2 %). Jetzt saatunabhaengig, 6x schneller, 1,35 GB statt 3,6 GB RAM. `PRUEF_CPU=1` = alte Fassung.
- **foto_diff --raster / FD_RASTER=1** (Entwurf, NICHT Standard): Martinstor T1 23,5 % bestanden (Punktmodell 26,7 % durchgefallen), Kaufhaus T1 7 % (19,6 %), test_param_suche -0,789/+0,491. Nachteil sichtbar: Fotokanten ohne Modell steigt (Punkt-Pfeffer hatte das verdeckt) -> `sprung_m` 0,25 m zu grob fuer Traufe/Bruestung. **Nutzerentscheid offen: Raster als Standard?** Danach test_gpu_gleichwertig neu fassen (Raster ist absichtlich nicht CPU-gleich).
- **Naechste Hebel**: Raster-Arbeiter brauchen 1,6 GB VRAM (4 parallel); gemischter GPU+CPU-Pool in param_suche, nach FOTO getrennt. RAM-Kauf erst nach Messung (Laptop 2x8 GB, Firmware meldet max 64 GB, HP offiziell 32 GB).

## Stand 5.11. nachts (Qualitaetsstufen, Nutzerauftrag "autonom weiter bis Modell + Methodik + Pipeline stehen")
- **Qualitaetsstufen** `tools/qualitaetsstufen.py` (Plan `modelle/kaufhaus_null4/qualitaetsstufen.json`, Ausgabe `/media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null4/`, Artifact HWmkJcxsVGprFEWn9z918Z): Stufe 1 Ausgang 1,0186; Stufe 2 Parameter 0,9913 (First -1,17, Kappe 0,41 uebernommen); Stufe 3 Fassaden-Parsing; Stufe 4 CMA-ES (`v_gemeinsam`, pycma BSD). stand.json atomar.
- **Stufe 3 Werkzeuge**: `tools/fassade_ortho.py` (Einzelfoto-Orthos je LoD2-Fassade, Embree-Sicht gegen Stufenmodell + LoD2-Nachbarn, 94 Fotos 40 s), `tools/fassade_parsing.py` (OWLv2 Apache-2.0, HF_HOME=/media/oem/scan/hf_cache, Foto-Abstimmung, Reihenregel, Boegen zusammengelegt, Felder AM FOTO gezaehlt), Generator-Bauteil `fassade_auto` (+ `fassade_raster.ohne_abschnitte`, BAUTEIL_PARAM `anhaengen`/`aktiv`).
- **Befunde**: Erkennung Nordfront 5 Fenster/4 Boegen/4 Figuren = Handablesung; Achsmass Automatik 2,84 vs Hand 3,07 m -> skala_u-Suche bevorzugt 0,94-0,96 (flach), also NICHT die Handteilung - Widerspruch offen. Komplett-Ersatz der Handablesung verliert (Erker/Traufe fehlen als Bauteiltyp). Entscheidung je Fassade nur auf Fotos, die sie sehen (12 Bewertungsfotos verwaessern). Anzahlen (Felder) nie suchen (Regel 9; Suche wollte 4 statt 3).
- **Offen/Naechstes**: Bauteiltypen Erker (+Helm), Traufe, Treppengiebel-Stufenzahl automatisch zaehlen; grosse Fotos (bis 86 MP, 7,3 GB VRAM einzeln, 068 passt nicht) fuer foto_diff verkleinern (Werkzeugaenderung -> Regression); fassade_ortho-Sicht auf GPU-Rasterer; Z-Protokolle fuer automatische Zaehlungen in die Masstabelle; Kaufhaus ohne Anzahl-Pruefung (test_regeln_cb laeuft daher am Martinstor, T4 an Commit 615f721 gebunden).

## Stand 5.11. frueh (nach Stufe 4)
- Stufe 4 (CMA-ES, 12 Gen.) verworfen: bestes 0,9793 (t -1,1), Mittelpunkt 0,9771 (t -1,4) -> Stand bleibt Stufe 3 = 0,9904. HTML Artifact HWmkJcxsVGprFEWn9z918Z v3.
- Neu: `tools/druckteile_auto.py` (rekursiver Schnitt, Aushoehlen, Stiftbohrungen, Slice je Teil; Kaufhaus s2: 4 Teile ok, 1,37 kg) - Nutzer: erst Pipeline, Druck spaeter.
- Neu: `fassade_relief.py` Bloecke (Erker W/O 0,64/0,75 m, Galerie 0,59 m) -> Beobachtung Widerspruch Hand 0,90 in masstabelle; naechster Schritt Bauteil "relief_bloecke" im Generator (Stufe 5).
- Neu: `tools/zier_ausschnitt.py` (Zierteile in voller Fotoaufloesung): von 9 "figur" nur 3 echte Figuren, 4 Wirtshausschilder/Ausleger, 2 Baldachine (Box zu hoch) -> Figurenerkennung braucht Gegenbegriffe + Reliefpruefung.
- TripoSR in /media/oem/scan/venv-tsr (pth auf venv-seg, transformers 4.44 lokal, Marching Cubes via scikit-image).
- Recherche: reports/Pipeline Beschleunigung per Software.md, reports/Daten und Qualitaet fuer H0 Modelle.md; gegen Register geprueft (Caspar schon gemessen: kein Gewinn).
- Neue Quellen 17-19 (bDOM, Stadt-LoD2, Stadt-Mesh) in quellen_inventar.py/QUELLEN_REGISTER.md; Bestellentwuerfe LGL_BESTELLUNG_BDOM.txt + ALS3 (Nutzer sendet).
- Stufenplan weiter: 5 Erker/Galerie-Bloecke + Helme, 6 Treppengiebel (Foto-Zaehlung), 7 Figuren/Baldachine, 8 Feindetails (Gesimse, Faschen), 9 Lauf ohne Hand.

## Stand 5.11. vormittags (nach Stillstand 02:51-08:03, eigene Schuld: Turn beendet statt weitergearbeitet)
- Herzschlag: CronCreate alle 20 min (nur diese Sitzung). Memory nie-idle-warten.md.
- Stufe 5 "Vorbauten aus Wolkenbloecken": fassade_relief.py Bloecke + Profilform (Front, Koerper 4,85-8,9, Gesims 8,9 m/0,81-0,94 m, Helmneigung); baukasten_gen.py bloecke_wolke. Ergebnis: Automatik = Hand-Gleichstand (Nadel 9 m: -0,003 t -0,3), Bewertungsfotos 0,9761 statt 0,9904. Nicht uebernommen (Regel t<=-2); in Stufe 9 (ohne Handwerte) gegen "kein Erker". Widersprueche offen: Erkerbreite Wolke 2,0 / Hand 3,3 m; Nadelspitze (Kanten flach 9-13 m) vs Hand 14,7 m.
- Figuren: zier_ausschnitt.py --pruefen (OWLv2 Ziel vs Gegenbegriffe, Box >= 0,5 Ausschnitthoehe, Score >= 0,5 VORLAEUFIG) findet alle 4 Ritter (Figur 19 hinter Wirtshausschild -> Ausweichfoto 025). zier_3d.py (TripoSR, ~1 min fuer 4). baukasten_gen figuren_netz. Stufe 6 im Plan misst gerade.
- Schatten: schatten.py (Schattenkarte), sonne_fotos.py (EXIF+NOAA+DWD 01443) -> sonne.json (58 Fotos: 26 Sonne/15 bedeckt/11 Nacht). foto_diff --schatten (Standard aus): GEGENPROBE GESCHEITERT - gedrehte Sonnen senken die Kosten ebenso -> kosten_param belohnt Zusatzkanten. NAECHSTER SCHRITT: faires Kantenmass (Zusatzkanten duerfen nicht von selbst gewinnen), dann Schatten + Nadel neu bewerten.
- param_suche.fotos_waehlen(ohne_nacht) + Plan-Schluessel "ohne_nacht" (fuer null5: Bewertungsfotos 075/119 sind Daemmerung/Nacht).
- qualitaetsstufen.py: ortho_von_stufe, Versuchsschluessel bloecke/bauteile, fertige Stufen mit neuen Versuchen werden fortgesetzt.
- OFFEN: tools/regression.py --pruefen nach den Werkzeugaenderungen (GPU frei abwarten).

## Stand 5.11. mittags
- FAIRES MASS: foto_diff kosten_lr ('a contrario' Likelihood-Verhaeltnis, Summe/Fotokantenzahl). Beweis: +10 % Zufallskanten senken kosten_param um 0,3-0,57 (!), kosten_lr steigt +0,02..+0,05. Schatten mit EXIF-Sonne: kosten_lr schlechter (061 0,533->0,673) -> Schatten bleiben aus. Plan-Schluessel "mass": "lr" (setzt FD_MASS=lr).
- Treppengiebel: giebel_stufen_zaehlen.py (Bandabtastung, Spektrum) -> 9 Kappen-Perioden = 8 Stufen + Spitze (Z-042-001 in null5); Hand Z-050-001 = 7 -> Widerspruch offen. 7/8/9 per kosten_lr nicht unterscheidbar (0,422/0,437/0,430). In qualitaetsstufen Stufe 1 "giebel_zaehlen".
- kaufhaus_null5 (/media/oem/scan/rc-park_null/kaufhaus_null5, Symlink modelle/): OHNE fassade_raster und Hand-Zaehlungen, Plan mass lr + ohne_nacht, Fassadenstufe mit Fenster/Boegen/Gauben/Relief/Bloecken/Figuren automatisch (figuren_auto = zier_ausschnitt + zier_3d im Lauf). Laeuft als rcpark-qs_null5 (Log qualitaetsstufen_null5.log).
- beobachtungen_offen brauchen Felder 'wer' + 'text' (pruefstand KeyError sonst) - repariert.

## Stand 5.11. 11:20 (Mass-Korrektur, Nachtlauf-Bausteine)
- **kosten_lr korrigiert** (foto_diff.lr_mischung): altes festes sigma=Kappe/3 bestrafte Details (Haelfte der Kanten weg = besser). Jetzt ML-Mischung; Gegenproben (Wegnehmen, Zufall, Versatz) bestanden. Altwert als `kosten_lr_alt` im JSON. Versuchslog Kaufhaus.
- **null5 neu ab Stufe 2** (11:16, Log `rc-park_null/qualitaetsstufen_null5c.log`), Plan = `modelle/PLAN_STANDARD_qualitaetsstufen.json` (gebaeudeunabhaengig: Fassaden `haupt|alle|seiten`, `spitzen_messen`, `entscheid: zier`). Alte Stufen 2/3 in `qualitaetsstufen_kaufhaus_null5/alt_vor_lrmix/`, alter Plan `qualitaetsstufen_vor_lrmix.json`.
- **Neu:** `tools/spitze_hoehe.py` (Spitzen per RANSAC-Triangulation, Test `tools/test_spitze_hoehe.py`; Kaufhaus Erker 16,13/16,16 m aus je 11 Fotos), Generator `bloecke_wolke` gibt `spitzen` im Beleg aus und nutzt `spitzen_z`; Figurenhalter 0,2 m und hinter der Figur; Runner: `zier_entscheid` (Silhouetten-IoU je Figur, Trockentest kh_zier4: 0,59 vs 0, t -18), Grafikspeicher-Budget je Foto (0,5 + 0,2 GB/MP) in Runner und param_suche, Fehlerursache `fehler.log` je Foto; `nullstart.py` Schritt `stufen` (Standardplan) fuer den Nachtlauf je Gebaeude.
- Offen: Zier-Tor vergleicht gegen "keine Figur" (IoU 0) - schwach; lokaler Kameraversatz (0,35-1,3 m) bleibt groesster Hebel fuer Detailschaerfe; test_foto_diff (Kaufhaus 004 + Martinstor 014) nach null5 laufen lassen (GPU).

## Stand 5.11. 12:35
- null5e GESTOPPT: Stufe 2 nahm first_versatz -0,63 aus Fotos -> Pruefstand First/wasserdicht/Koerper rot (Laeufer pruefte nie). Fotorahmen am Dach >= 0,5 m zu tief (Wolke vs DOM1).
- NEU: Pruefstand-Tor in qualitaetsstufen (tor_ok an jeder Uebernahme), pruefstand.py --bericht, baukasten_gen verwirft verdeckte Schnitte (Hohlraeume), genauigkeit_ampel.py (Gegenprobe bestanden), punkte_messen.py GESPERRT (Zirkelschluss).
- null5f laeuft ab Stufe 2 (Stand s1 behalten, Backup stand_null5e_vor_tor.json), Log /media/oem/scan/rc-park_null/qualitaetsstufen_null5f.log.
- Offen: spitze_m -0,62 (Foto) evtl. Rahmen-Bias; vertikaler Kameraanker an DOM1-Dachflaechen; Erkerfenster auf Erkerflaeche.
- NACH null5i (Generatorsperre waehrend Lauf): (1) baukasten_gen: `BAUTEILE["fassade_vorbau"] = fassade_auto` (Datei aus fassade_ortho --waende-stl), bauen_abnehmen + Regression;
  (2) PLAN_STANDARD + kaufhaus_null5: Versuch {"name": "Erkerfenster auf Vorbauflaechen", "vorbau_fenster": true, "klassen": ["fenster"]} NACH dem Blockversuch;
  (3) foto_diff --sprung-m 0,08/0,12 vs 0,25 testen (GPU, test_foto_diff + Fensternische); Laeuferteil vorbau_fenster ist schon drin (13:20).
  (4) tiefen_messen.py einbauen: qualitaetsstufen nach fassade_parsing -> tiefen.json; fassade_auto-Parameter (nische_m, bogen_tiefe_m, figur_vorsprung_m) aus gemessenen Klassenwerten, Beleg "gemessen" statt ANNAHME; 2. Objekt pruefen.

### Nutzerbefunde 5.11. 13:50 (Zwischenmodell s3_v1) - alles automatisch loesen, keine Handarbeit
- Seitliche Arkadenbogen (Durchgang): Parsing findet f00-Bogen (6 Stimmen), f06 nicht; Generator baut nur Frontgalerie -> Regel "Seitenbogen in Arkadentiefe = Durchlass" + Strahltest-Pruefung.
- Bogen leicht verschoben: automatischer lokaler Versatz je Element (Chamfer im Foto) als Pruefung + Feinlage.
- Fehlend: Erkerhelme/-fenster, Bruestung/Balkon, Gauben, Figuren; Dachvernetzung (Splitterdreiecke).
- NUTZER 13:53: "das ist wieder ein Spezialfall - muss generell gefunden werden". -> KEINE Bogen-/Durchgangsregel. Stattdessen zwei generelle Pruefungen fuer jedes Objekt:
  (a) Freiraum aus Sichtstrahlen: jede Tiefenkarte (dichte Rekonstruktion) sagt "Strahl frei bis Tiefe d" -> Modellvolumen, das Kameras durchschauen, ist falsch (Durchgaenge, Arkaden, Nischen, Hoefe);
      umgekehrt Fotooberflaeche, wo Modell Luft hat = Fehlteil. Pruefstand-Merkmal "Freiraumverletzung m3 / Fehlvolumen" + Generator schneidet/ergaenzt daraus. Vorher Stand der Technik (Space Carving / Sichtbarkeitskonsistenz) und Gegenprobe (Modell mit zugemauertem Bogen muss fehlschlagen).
  (b) Feinlage je Element (alle Klassen) gegen Fotokanten statt Bogen-Sonderfall.
- 5.11. 14:16 Datenplatte voll (Errno 28 in Stufe 4): verschoben nach /media/oem/Volume/rc-park_archiv_2026-11-05/ : qualitaetsstufen_kaufhaus_null4 (8,8 G, alter Lauf) und null5/alt_vor_lrmix + alt_vor_giebelspitze (4,1 G). Platte danach 13 G frei. Laeufer braucht eine Platzpruefung vor jeder Stufe.
- 5.11. 14:32 Figuren (s3_v6, TripoSR) vom Tor verworfen, obwohl Fotokosten t -11,9: 4 Figuren (0,5-0,7 x 1,5-1,6 m) stehen FREI vor der Fassade (y 12-15, kein Kontakt), eine nicht wasserdicht, + Splitter (<0,001 m3).
  Allgemeine Regel fuer ALLE Anbauteile (nicht nur Figuren): Teilkoerper ohne Kontakt -> Konsole = Huelle(untere 20 %% der Teilpunkte + dieselben bis 0,1 m in die naechste Modellflaeche verschoben), danach vereinigen; nicht wasserdichte Netze vorher reparieren (fill_holes/Voxel-Neuvernetzung), Splitter < 1e-3 m3 verwerfen mit beleg. Gegenprobe: s3_v6 -> 1 Koerper, wasserdicht, Fotokosten nicht schlechter.
- 5.11. 14:29 freiraum_oeffnungen Gegenprobe bestanden (nach Fix: nur Strahlstuecke IM Modell). Eingabe fuer Generator: <scratchpad>/freiraum_s3v1/elemente_freiraum.json (neu erzeugen auf Endmodell s4!).
- 5.11. 15:01 Entwurf Pruefstand-Merkmal Freiraum: NICHT im Pruefstand rechnen (2-4 min, Tor ruft Pruefstand je Kandidat), sondern nach jedem Bau audit/freiraum_oeffnungen.json erzeugen (freiraum_pruefen -> _fassaden --stl -> _oeffnungen), Merkmal liest 'Freiraumflaeche ohne Oeffnung je Fassade (m2)' daraus; Datei aelter als STL = Pruefung ungueltig (Exit 2).

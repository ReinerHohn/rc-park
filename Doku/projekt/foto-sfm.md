# 📷 Fotos → SfM: Zuordnung, Mapper, Kameras  ← [PROJEKT.md](../../PROJEKT.md)
Details: `modelle/GLOBALER_MAPPER_STABIL.md` · `modelle/VERSUCHSREGISTER_MARTINSTOR.md` · `modelle/NICHTS_GEBRACHT.md` (Inhalt: `modelle/inhalt/`) · Nachbaräste: [lage-seiten](lage-seiten.md), [wolke-wandbild](wolke-wandbild.md), [kanten-messen](kanten-messen.md), [bauteile-kreis](bauteile-kreis.md), [betrieb](betrieb.md) · **Unteräste (vollständig, je Quelleintrag eine Zeile):** [fotoauswahl](foto-sfm/fotoauswahl.md) · [kameras](foto-sfm/kameras.md) · [mapper](foto-sfm/mapper.md) · [zuordnung](foto-sfm/zuordnung.md)

## Gilt
- **Immer vereinen (Nutzer 27.11.):** jede neue dichte Wolke mit ALLEN Wolken des Objekts in einen Modellrahmen (Register `modelle/<obj>/wolken.json`, Lagetore je Quelle/Block, Voxel-Gewinner, rot wenn eine Zone unter die beste Quelle faellt) → [foto-sfm/wolken-vereinen.md](foto-sfm/wolken-vereinen.md)
- **Grundbegriffe (Nutzer 26.11.):** Merkmale, Matching, Mapper, Registrierung, Tiefenkarte, Fusion, wann was → [foto-sfm/grundbegriffe.md](foto-sfm/grundbegriffe.md)
- **Teilmodell-Einpassung nur mit Qualitätstor (27.11.):** `ausgerichtet` nur bei Rest relativ ≤ 0,025, Drehfehler ≤ 0,6°, genug verteilten Ankern; sonst UNSICHER, und die Nachtkette bricht vor der dichten Wolke ab → [foto-sfm/teilmodell_qualitaetstor.md](foto-sfm/teilmodell_qualitaetstor.md)
- **Kernmethode (Nutzer 15.11.):** Form = Fotokanten + Triangulation mit SfM-Kameras; dichte Wolke/LoD2/DOM1 nur Lage-Veto, Höhe, Gegenprobe.
- **Wandbild = Bauplan (17.11.):** jede Wand aus vielen Fotos entzerrt (1-cm-Raster) + Tiefe je Zelle → Gestalt nachbilden; kein Musterteil.
- Neue Objekte: Fotos → SfM → LoD2 nur Abgleich (entschieden 20.11., Nutzer „neuer ist besser"; ersetzt „LOD2 = Massing" aus Okt.).
- Feindetail = echte Löcher/Relief aus dem Wandbild, aber druckbar (Mindestmaß 0,8 mm, keine Mikroteile wie 31.560 Sprossen) — entschieden 20.11.
- Ungesehene Seite nie spiegeln/erfinden → Fotos suchen. Zählen nur am Foto. Verwerfen nur mit benannter Ursache.
- Globaler Mapper nur als Konsens zweier Läufe; jedes globale Modell erst zerlegen (`tools/modell_zerlegen.py`), dann bewerten.
- Lizenzen müssen Verkauf erlauben (`modelle/LIZENZ_WERKZEUGE.md`); Git: > 1 MB nie ohne LFS, Zugangsdaten nur `~/.config/rcpark/`.
- **Daten selbst holen (Nutzer 02.11.):** Videos/Commons/DOM/LoD2 selbst suchen, keine Fototouren verlangen; Massstab zweitrangig, Details >= 7 cm + Proportionen zaehlen [memory videos-daten-selbst-holen]
- **Software vor Fotoauftrag (Nutzer 16.11.):** erst Bestand + Downloads auswerten (`seiten_luecken.py --download --holen`, `fassade_ein_foto.py auto`), erst dann `foto_auftrag.py` [memory feedback-lehren-fotos-ausreizen-1611]
- **Eine gemeinsame SfM (Nutzer 08.11. "ein Punkt ist ein Punkt"):** neue Fotoquellen in DIESELBE SfM geben, getrennte Wolken nur starr ausrichten, nie verformen [memory feedback-wolken-nie-verformen-gemeinsame-sfm]
- **Konsens-Mapper ist Standard (`--mapper auto`):** traegt er nicht -> `ACHTUNG DATENMANGEL` mit Ursache, erst dann alter Weg [f57e3c48, LOGBUCH_KETTENTEST_2026-11-19]
- **Lizenz fuer Verkauf:** COLMAP/GLOMAP, LightGlue, ALIKED, FlexGlue, AnyCalib, DINOv2 frei; Mapillary (BY-NC-SA), SuperPoint, MASt3R, VGGT-1B, LoMa-Gewichte gesperrt; Commons nur Messvorlage [VERSUCHSREGISTER AF/AK, LOGBUCH 20.11., memory lizenz-werkzeuge]
- **COLMAP-Version (Nutzer 18.11.):** Umstellung aller Werkzeuge auf 4.3 erst nach A/B auf eigener Platte; Mapper eigener Bau, Rest pycolmap 4.2.1 [memory project-colmap-versionen]
- **Selbst bauen statt apt (Nutzer 19.11.):** `tools/umgebung/colmap-bauen.sh`, CUDA in eigenem Ordner, ONNX-Vorrat [LOGBUCH 19.11. 19:30]
- **Handyfotos:** nie zoomen; Kamera je Format x Zoom; Hochformat-f = 1,333 x Querformat-f [VERSUCHSREGISTER DB/DD, memory handy-zoom-brennweite-2026-11-06]
- **Vor jedem neuen "Fund" Register durchsuchen** (Seitenverwechslung dreimal als neu gemeldet = Rueckfall) [LOGBUCH 19.11. 12:20, memory project-seitenverwechslung-symmetrie]
- **Vor dem Zeigen 3 Ansichten (Draufsicht + 2 Seiten) selbst rendern, Punktwolken auf dunklem Grund** [LOGBUCH 19.11. 08:47 / 17:15]

## Versucht
**Merkmale & Zuordnung**
- 28.11. · K1b Feedforward-Kameraposen (MapAnything Apache, VGGT NC, MASt3R-SfM NC) auf 4 Gruppen a 60 Handyfotos (Steg/Treppe), Holdout-Sim3 gegen die 295 PnP-Posen → ✗ kein Hebel · 0 belastbar neu eingeordnet; Steg g1 von MapAnything/VGGT auf ~2 m gestaucht, Massstab MapAnything 1,5-1,9x zu klein; Nullkontrolle (vertauschte Posen) 1,01 m in g1 = Positionszahl dort ohne Aussagekraft; bester Einzelwert MASt3R g1 Holdout 0,50 m aber p90 10,4 m; Ursache ANNAHME: Vorwaertsfahrt im engen Gang mit gleichfoermigen Pfosten + 518 px Eingabe; MP-SfM nicht gelaufen; Naechstes: Fotoauftrag mit Seitenversatz auf dem Steg [BERICHT_K1B_2026-11-27]
- 27.11. · Runpod-Messreihe Schwabentor (RTX 4090, Volume ghhv7k1089): dichte Wolke 1600-5800 px und Registrierung in voller Aufloesung ohne Gewinn fuer Wand/Registrierung → ✗ kein Hebel; ALIKED+LightGlue voll aufgeloest (4000 px, 8192 kp) ordnet von 241 Handyfotos 109 ein (SIFT voll 91, alle 91 enthalten, +18 an Bruecke/Brueckenlaube/Treppenturm/Rundturm, Reproj 1,63 px) → ✓ wirkt an den schwachen Stellen, Lage/Qualitaetstor der Bruecke NICHT geprueft; RoMa (K5, nur Probe) 6 von 148 der nicht eingeordneten Fotos sicher (>=40 Inlier) → ~ kleine Ergaenzung. Lehre: SQLite-DB nie auf dem Netz-Volume (>1 h statt 3 min); Ergebnis /media/oem/rcdaten/tmp/runpod_test/lg_voll [SPEC_VERFAHREN_RUNPOD_2026-11-27]
- 01.11. · COLMAP-SfM ueber alle 37 Turmfotos (pycolmap, 2000 px) → ✓ Methode · 36/37 in 10 s registriert; Problem ist Ausrichtung, nicht Rekonstruktion [VERSUCHSREGISTER AE]
- 01.11. · ALIKED+LightGlue / hybrid statt SIFT (Martinstor, fast ebene Fassaden) → ✗ verworfen · registriert alles, aber Netz VERBOGEN; SIFT vorsichtiger [VERSUCHSREGISTER AK]
- 01.11. · SIFT mit Vollaufloesungs-Ausschnitten fuer Luft-/Fernbilder → ✗ · 0 verifizierte Paare; Ausschnitt heilt Massstab, nicht Blickwinkel > 45 Grad [VERSUCHSREGISTER AJ]
- 02.11. · CPU-SIFT-Datenbank fuer GLOMAP → ⚠ Falle · Massstab-Sigma 27-54 %; GLOMAP nur mit GPU-SIFT (Ursache offen) [VERSUCHSREGISTER BL]
- 06.11. · Zusatzfotos per ALIKED+LightGlue mit 512er-Vorfilter nachregistrieren → ✓ Methode · 115 statt 72 von 146, LG-Pose in 49/71 genauer [VERSUCHSREGISTER CY/DA]
- 07.11. · Belichtungs-/Kontrast-Sweep (CLAHE) fuer mehr Punkte → ✗ · wirkt wie niedrigere SIFT-Schwelle, kein neuer Blickwinkel [NICHTS_GEBRACHT BS2]
- 14.11. · Bildvorpruefung per ALIKED+LightGlue gegen eigene Fotos (>= 60 Inlier) → ✓ Methode · filtert Commons/Netzbilder vor der SfM (`bilder_vorpruefen.py`) [archiv/STAND_2026-11-14]
- 15.11. · LightGlue-Paare ungefiltert in die DB → ✗ · 12 780 Paare gegenueberliegender Seiten; nur bis ~110 Grad Azimut (`lg_in_db_anhaengen.py`) [NICHTS_GEBRACHT 15.11.]
- 15.11. · COLMAP SIFT_LIGHTGLUE auf 8-GB-GPU → ⏸ zurueckgestellt · nur <= 4096 Merkmale, 0,46 s/Paar; Attention-Puffer sprengt Speicher [archiv/STAND_2026-11-14 09:30]
- 19.11. · FlexGlue (min_covisibility 0,5) als Querpaar-Pruefer → ✓ Methode · Nord-Sued-Querpaare 1 % bestaetigt, echte 99-100 %; braucht CUDA-12-ONNX, 6000 Merkmale [LOGBUCH 19.11. 22:20]
- 20.11. · SIFT ∪ FlexGlue vereinigt → ✗ · liegt zwischen beiden (949/154 Bilder), kein Vorteil gegen FlexGlue allein [RECHERCHE_VERBESSERUNGEN Ergebnis 4]
- 20.11. · FlexGlue frueher abbrechen (early_stop_decay 0,3/0,2) → ✗ · nicht schneller; Zeit steckt im Merkmalsladen je Paar [LOGBUCH 20.11.]
- 20.11. · FlexGlue-Stufe 2 (von SIFT abgewiesene Paare), Stichprobe 4000 → ⏸ laeuft · bestaetigt 23,6 % neu, hochgerechnet ~60 000 Paare, ~20 h [LOGBUCH 20.11. 02:25]
- 19.11. · LoFTR fp16 im Seitenpruefer (kornia 0.9.2) → ✗ · 30 % schneller, aber Urteile an p90-Schwelle kippen [LOGBUCH 19.11. 19:30]
- 20.11. · FlexGlue statt SIFT-Zuordnung → ✓ +30 % Nord / +40 % Süd Bilder Martinstor, Schwabentor +6 %, Lage gleich · zuschaltbar `RCPARK_FLEXGLUE=1` [dc0b84b9]
- 20.11. · FlexGlue-„Türsteher" trennt Seiten → ✗ Fehlmeldung · fairer SIFT-Lauf trennt genauso [Logbuch Kettentest]
- 20.11. · DINOv2-Bildsuche als Paarvorfilter → ✗ nur 9 % der neuen FlexGlue-Paare in top-150
- 20.11. · LoMa-Zuordnung → ✗ Gewichte nicht kommerziell nutzbar

**Mapper: inkrementell / global / Konsens**
- 02.11. · Inkrementeller Mapper wiederholt (gleiche DB) → ⚠ Falle · Massstab-Sigma 2,8-24,6 %; mehrere Laeufe, nach kleinstem Sigma waehlen [VERSUCHSREGISTER BF]
- 02.11. · GLOMAP (pycolmap) 3 Seeds → ✓ · praktisch identisch, Sigma 2,5 %, 20 s [VERSUCHSREGISTER BF/BG]
- 13.11. · globaler Mapper ohne Brennweiten-Vorgabe → ↺ ersetzt durch view_graph_calibrator davor · Kameras 10 m zu hoch; Ursache stand im Log [memory feedback-verworfenes-neu-pruefen]
- 15.11. · global + view_graph_calibrator gegen schrittweise (Schwabentor, Schiedsrichter Foto-GPS) → ✓ · 2-3 % statt 18-19 % Fotos > 15 m, 8,6 statt 40 min [archiv/STAND_2026-11-14 15.11. nachts]
- 15.11. · eine Kamera je Geraet/Clip (PER_FOLDER) im globalen Mapper → ✗ · 18 % GPS-Ausreisser statt 3 %; geteilte Intrinsik nimmt Freiheit [NICHTS_GEBRACHT 15.11.]
- 19.11. · EXIF-Prioren aus pycolmap 4.2.1 uebernehmen → ✗ Gift · Canon/Pentax-f bis 8,7 Mio px; Kameras mit Prior kalibriert der Kalibrator nicht [GLOBALER_MAPPER_STABIL Befund 1]
- 19.11. · AnyCalib-Brennweite als Prior oder fest → ✗ · schaltet Paar-Kalibrierung ab bzw. verbiegt (S3/S4: 29-30 % statt 10 %) [GLOBALER_MAPPER_STABIL]
- 19.11. · ra_reweighting, ba_num_iterations 6, fester Seed → ✗ · alles im Laufrauschen; Mapper auch mit Seed nicht deterministisch [GLOBALER_MAPPER_STABIL S2d/S6/S7]
- 19.11. · Nur-Fotos zuerst / Fotos per image_registrator an Videorueckgrat → ✗ · Videobilder sind das Rueckgrat; image_registrator haengt nur die Haelfte ein [GLOBALER_MAPPER_STABIL F0-F2/V7b]
- 19.11. · Konsens-Rezept (Prioren loeschen, Kamera je Clip, 2 Laeufe, Schnitt <10 % Kernradius/<2 Grad, Stufe 2 fix_existing_frames) → ✓ Methode · Kaufhaus Qualitaet wie schrittweise in 1/6 Zeit [GLOBALER_MAPPER_STABIL, LOGBUCH 09:17]
- 19.11. · Stufe 2 mit strukturlosem Registrier-Rueckfall → ✗ · erzeugt alle "zum Mond"-Kameras; `structure_less_registration_fallback 0` Pflicht [GLOBALER_MAPPER_STABIL S8d/S8e]
- 19.11. · Konsens-Schnitt als Seitenpruefung → ⚠ Falle · beide Laeufe verkleben gleich; Wiederholbarkeit erkennt Verwechslung nicht [LOGBUCH 19.11. 12:45]
- 19.11. · fremde Videobilder ohne Objektverbindung im Mapper lassen → ✗ · 68 statt 45 min, bringen nichts; vor dem Mapper streichen [LOGBUCH 19.11. 12:05/15:00]
- 19.11. · globaler Mapper auf Bildliste mit beiden Seiten (Suedanhang) → ✗ · verklebt; global nur seitenrein [LOGBUCH 19.11. 22:20]
- 19.11. · COLMAP main (18.11.) / Ceres-Drehmittel / COVARIANCE gegen alten Bau → ✗ · kein messbarer Gewinn, Laufstreuung gleich gross [LOGBUCH 19.11. 21:30]
- 13.11. · GPU-Buendelausgleich (dense_gpu_solver 0) → ✓ · 240 statt 340 s, gleiches Ergebnis; Registrierung/Fusion ohne GPU-Code [memory project-schwabentor-software-optimum]
- 03.11. · Kameramodell OPENCV statt SIMPLE_RADIAL → ✓ fuer Drohnenclips / ✗ fuer Strassennetz · Clip-Tiefenversatz 1,1-1,7 m -> ~0,1 m; Strasse eher schlechter [VERSUCHSREGISTER BU]
- 01.11./03.11. · RADIAL bzw. feste EXIF-f fuer einseitiges Suednetz → ✗ · Stauchung bleibt; einseitig + eben + unbekanntes f = verbogen [VERSUCHSREGISTER AI/BC]
- 20.11. · Kamera-Unsicherheit lokal (6 Posenparameter, Punkte fest) → ✓ als Hinweis · alle Springer unter den 10 % unsichersten; BA-Kovarianz scheitert [LOGBUCH 20.11. 00:30]
- 20.11. · Rollverschluss-Mass aus Videoposen → ✗ keine Massnahme · Videobilder trotzdem genauer als Fotos [LOGBUCH 20.11.]
- 20.11. · globaler Mapper „Modell 0" als ein Stück bewertet → ⚠ Falle · enthält punktlos getrennte Gruppen, Lage zueinander beliebig → `modell_zerlegen` [Logbuch Kettentest]
- 20.11. · Konsens-Stufe 2 mit allen Bildern → ✗ zwang 21 Süd-Bilder ins Nordmodell · Seitenfilter `fremde_seite` [45d76d5c]
- 20.11. · Schwerkraft-Vorgabe je Bild im Mapper → ✗ 12–14 Bilder weniger, kein Genauigkeitsgewinn
- 20.11. · Einzellauf globaler Mapper → ⚠ je Methode ein deformierter Wiederholungslauf · immer Konsens zweier Läufe
- 13.11. · Mehrthread-Mapper → ⚠ nicht reproduzierbar (181/149/181/21 Bilder) · ein Thread

**Kameras prüfen & Brennweite**
- 01.11. · Reprojektionsfehler als Guetemass → ⚠ Falle · 0,7 px bei projektiv verbogenem Netz; vorher `sfm_verzerrung_test.py` [VERSUCHSREGISTER AI]
- 01.11. · Anker im Buendelausgleich (`sfm_bundle_anker.py`) → ✗ · Spurresiduen halten das verbogene Netz starr [VERSUCHSREGISTER AI]
- 01.11. · Brennweite einer Serie uebertragen / f35 auf beschnittene Breite → ⚠ Falle · Zoom; Sensorbreite gehoert zur langen, unbeschnittenen Seite [VERSUCHSREGISTER AH/AI/AJ]
- 01.11. · Kamera-Tauglichkeit per Anker-RMS → ↺ ersetzt durch Ankerzone (`ankerzone_z`) · Fehler kommt aus Extrapolation unter tiefsten Anker [VERSUCHSREGISTER AG]
- 06.11. · eine feste Handy-Brennweite fuer alle Bilder → ✗ · Hochformat 24 % falsch, 38 gezoomt; Kamera je Format x Zoom 157/200 statt 72/146 [VERSUCHSREGISTER DB/DF]
- 07.11. · Einzel-Kamerafeinlage per foto_diff / gemeinsamer Ausgleich → ✗ · Ueberanpassung, 5 von 6 Holdouts schlechter [NICHTS_GEBRACHT BS3c/BS3d]
- 09.11. · Linien-Feinlage der Pose gegen Kantengitter → ✗ · Rueckholung 0,79 statt <= 0,3 [NICHTS_GEBRACHT 2026-11-09]
- 09.11. · Leave-one-out-Kameraguete (Flaechenfehler in m) → ✓ Methode · Median 2 mm, 13 unbrauchbar erkannt [archiv/LOG_KAMERA_GUETE_2026-11-09]
- 16.11. · Kameras ohne Plausibilitaetspruefung nutzen → ✗ · 14 PnP-Tele-Loesungen bis 350 000 km liessen embree kriechen; Abstand > 600 m / f > 10 x Breite sperren [NICHTS_GEBRACHT 16.11.]
- 15.11. · Kameras unter Gelaende als Hinweis-Tor (`kamera_plausibel.py`) → ✓ · fand Clip, der eine Geisterwand erzeugte [archiv/STAND_2026-11-14 08:10]
- 24.11. · Nachholen nur fuer GANZ ungesehene Waende (< 20 %) → ✗ · 1122x f02 44 % gesehen, 239 m2 ohne Bilddaten, rc 0, nichts geschah; davon ~190 m2 hinter dem angebauten Nachbarhaus (nie fotografierbar), 57 m2 frei (z 17,7-23,5 m). ↺ `seiten_luecken` 'teilweise': fotografierbar >= 10 % UND >= 50 m2 (LoD2-Nachbar abgezogen) loest Nachholen/Wiederholung aus, je Kandidat nur ein Versuch (`versucht_kandidaten.json`), sonst Fotoauftrag [tools/test_seiten_teilweise.py]

## Offen
- Martinstor-Kette von null (`kette-martinstor-1120`): tor_zerfall, fremde_seite.txt, Seiten getrennt pruefen (Stand 20.11.) [LOGBUCH UEBERGABE]
- FlexGlue-Stufe 2 Martinstor (~20 h): Ergebnis + ob neue Paare neue Bilder bringen (Stand 20.11.) [LOGBUCH UEBERGABE]
- Unstabile/unsicherste Kameras aus Wandbild und Kanten-Sweep heraushalten; in Toren getrennt ausweisen (Ideen 12/22/25, Stand 20.11., nur dichte Wolke umgesetzt)
- Stille Kettenfehler 38-44 (SfM-Cache halbes Paarnetz, Bewertungsabsturz -> falscher DATENMANGEL, 3-h-Grenze toetet Rueckfall) (Stand 19.11., ungeprueft)
- Kaufhaus-Konsens: Kameraluecke 78 -> 93 Grad; verworfene Lueckenbilder gezielt nachregistrieren (Idee 19, Stand 19.11.)
- pycolmap aus 4.3-Quellstand bauen + A/B, dann Umstellung entscheiden (Nutzerentscheid 18.11.)
- GLOMAP mit CPU-SIFT-DB unbrauchbar - Ursache offen (Stand 02.11.)
- FlexGlue als Standard? (Nutzerentscheid, +2,5 h Laufzeit)
- 24.11. · Laufzeit-Bericht je Kettenlauf (`tools/laufzeit_bericht.py`, Stufe `laufzeit` vor befundliste → audit/laufzeit.json): Familien, DOPPELARBEIT (Fusion 2x 470+445 s in 1122z), WIEDERHOLUNG (6 volle Bauten 37,7 min in 1122x), GEWACHSEN gegen den Vorlauf aus gesamtkette.log → ✓ Werkzeug + Test; Wirkung erst ab nächstem Lauf

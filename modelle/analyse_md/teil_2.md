# Teil 2 der Modell-Registrierung: Lehren aus 37 Dokumenten (modelle/*.md)

Gelesen: alle 37 Dateien aus `_liste_2.txt`. NICHTS_GEBRACHT.md (155 KB) nur Kopf, Nebenabschnitte 2026-11-12 und jede 3. Zeile der Eintragsmasse (BS1-BS154, Kreis-Eintraege 9.-12.11.) - Einzeleintraege daher nicht vollstaendig. Alle anderen Dateien >= Anfangsteil, die grossen (LERNJOURNAL, PIPELINE_KOMPLETT, METHODE_MASSTABELLE, PIPELINE_H0, LOG_*) weitgehend.
Kennzeichnung: **[B]** = belegt (Messung/Foto/Zahl im Dokument), **[A]** = Annahme (im Dokument so markiert), **[M]** = Meinung/Einzelaussage ohne Beleg, **[R]** = Recherche (Web, nicht selbst geprueft).
Kuerzel: NG = NICHTS_GEBRACHT.md, LJ = LERNJOURNAL_MARTINSTOR.md, PK = PIPELINE_KOMPLETT_2026-11-07.md, MM = METHODE_MASSTABELLE.md, PH = PIPELINE_H0.md, NS = NULLSTART_GENERALITAET.md. Zwei Objekte kommen vor: Martinstor (Torturm, Generator-Weg, Okt/Anf. Nov) und Kaufhaus (Wolke/Foto-Weg, ab ca. 3.11.).

---
## 1. Was hat funktioniert

**Rahmen / Disziplin**
- Masse als Daten (`masstabelle.json`) + generischer Pruefstand mit Quellen-Blindheit: Tabelle wird abgelehnt (Exit 2), wenn eine Quelle ein Merkmal belegt, das sie nicht sehen kann (LoD2 blind fuer Aufbauten, Laser 1 m blind fuer Nadel/Fassade). [B] MM Abschn. 2; Beleg dort: Nadel 0,1 m unsichtbar im DOM1: 54,8 statt 60 m; LoD2 45,3 m = ohne Aufbauten.
- Pflichtablauf Beobachtung -> Pruefung die am alten Modell ROT ist -> Generator aendern -> gruen. Wirksamkeit [B]: der Stand vor der Korrektur faellt mit 4 Pruefungen durch, der korrigierte besteht (PH 2.6). Entstand, weil "Tuermchen zu gedrungen" nach Korrektur unbemerkt zurueckkam (PH 2.6, MM Einleitung: "Lektion aufgeschrieben, nicht erzwungen").
- `beleg(seite, element, quelle)` im Generator + Sichtblatt `audit/seiten.jpg`: beim ersten Eintragen fiel auf, dass Tafel und Adler auf falschen Seiten sassen (MM 6) [B]. Zweck: Whack-a-Mole beenden, jede Seite ansehen, nicht nur die fotografierte.
- Gegenpruefung "Foto neben Render ansehen" fand mehr als alle Zahlen: Gaube/Glockenstock/Kragdach/Erker waren falsch, obwohl alle Zahlen gruen waren (LJ Eintrag 0, 3a) [B]. Rumpf als Podest+Turm statt durchgehendem Anlauf wurde erst im Seiten-an-Seiten-Vergleich sichtbar (LJ 3a).
- Amtliche Hoehendaten schlagen Texte und Fotoschaetzung: DOM1-Hypsometrie ergab Martinstor 54,80 m; Texte 60-66 m falsch, 45,3 m (LoD2) = ohne Dachreiter (LJ Eintrag 6 und Folgeeintrag, Lehre a "zuerst DOM/DGM holen, nicht nach Wochen") [B].
- Masse nur so glauben: >= 3 Fotos aus verschiedenen Blickwinkeln (LJ 17: Bogenscheitel aus schraeger Aufnahme 1,5 m zu hoch; frontale bodennahe Fotos besser fuer Hoehen) [B]; Verhaeltnis ohne mitgerechnete Unsicherheit ist keine Messung (MM 8b: Knauflage schien Widerspruch 0,49/0,51 vs 0,43, mit Band 0,364..0,736 keiner) [B].
- Ankerzone-Sperre: eine Kamera gilt nur im Hoehenbereich ihrer Anker (+2 m). Beleg [B]: K-060 trifft Tuermchenspitzen auf 0,7 m, rechnet 20 m tiefer die Westwand-Oberkante auf 23,8 statt 30,5 m; `fehlteile_finden` meldete damit 6 "erfundene Teile". Kriterium ist Extrapolation, nicht Anker-RMS (der haette die bewaehrte K-030 gesperrt) (MM 8).
- Fehlteile-/Erfunden-Finder `fehlteile_finden.py` (Rot/Blau je 1-m-Zelle): fand am Martinstor Uhrgiebel und Kragdach vor dem Einbau (MM 9) [B].
- SfM-Kette fuer Kaufhaus: 94 -> spaeter 440 registrierte Fotos (kam_lot2); Reprojektionsfehler Median 0,56 px (PK 2) [B]. Kameraguete per Leave-one-out: gut 406, grob 21, unbrauchbar 13; Fehler Median 2 mm, P90 9 mm, P99 77 mm; Synthetik reproduziert eingespielte Fehler (0,3 m -> 0,264) (LOG_KAMERA_GUETE) [B]. Einschraenkung im Dokument selbst: "trivial", die LOO-Pose haengt nicht von der gespeicherten ab; Anker (LoD2) nicht pruefbar.
- Rahmen der Kameras per Umeyama aus den 94 Kamerazentren, Rest 0,05 cm (PK 3) [B]; Kaltstart-Ausrichtung `sfm_lod2_ausrichten.py` (Lot aus Kameraebene, Grobsuche an Wandlinien ALLER LoD2-Gebaeude, Fein in SfM-Einheiten, massstabsneutral) (NS D) [B: lief im Kaufhaus-Kaltstart].
- Diff-basierter Wettbewerb `foto_diff` `kosten_lr` (Raster-Modus, GPU): trennt grobe Netzunterschiede; Siegerlage haengt aber von Glaettung ab (BS22: g=0,05 gewinnt Saeulen-Regel -0,1138, g=0,18 gewinnt default). OpenMVS Delaunay+Graph-Cut gewann gegen Poisson, Carving, Splatting, PolyFit (PK 5, NG BR/BS) [B]; Raster-Mittel (23 Fotos, g0,18): default -0,1139, Saeule -0,1086, d03_pl30 -0,1064, fein -0,0864 (PK 5).
- Erster "Tor-Sieger" Hybrid hlo (d03_fix unten + geschaerftes mvs_default_fix oben, Unsharp i2k2 Clamp 0,3 mm) (NG BS119) [B im Diff; Sieg dann relativiert, s. 2.]. Leave-out-Test mit 8 weggelassenen Fotos als einzig echte Unabhaengigkeit (NG BS131).
- Kaufhaus: Gittererkennung der Bogenreihe aus Wolke: 5 Pfeiler/4 Boegen, pitch 4,329 m, R 1,652 (NG BS86); aus Gitter 4 Arkaden R 3,04/3,06/3,04/2,46, Inlier 59-66 %, rms 3-4 cm (LOG_KOERPER) [B]. Gitter -> Rohkoerper in 1 s, wasserdicht, 784 Dreiecke; Dach/First/Traufe decken sich mit dem Foto (Overlay angesehen) (LOG_KOERPER) [B].
- Wiederholungs-Prior: Template-Matching findet genau 5 Fenster 0,89-0,95 und kein weiterer Treffer >= 0,35 (NG BS28); Autokorrelation Perioden 2,86/5,74/8,62 m (NG BS29) [B]. Aber: Zahl aus Wolke-Ortho ist kein Sollwert, Zaehlung nur am Foto (NG BS25b).
- Kreis-/Bauteil-Runden auf grob3: nur Teile mit klarer Messgroesse liefen sauber: Giebel Ost (Beleg 0,224 -> 0,376-0,381, Gate +0,075 vs 0,05) durch Neigung der Wandebene aus Kappenfirst-Linie 0,0609 m je m (LOGBUCH_GIEBEL_OST) [B]; Gauben oben (Pultdach statt Satteldach, 8 Pruefungsfehler -> 0; Wolkenbeleg 0,459 -> 0,588) per 3-Kamera-Triangulation (LOGBUCH_GAUBEN_OBEN) [B]; Fenster EG0 Beleg 0,875 -> 0,996 (LOGBUCH_FENSTER_EG0) [B].
- GPU-Sweep fuer Bauteil-Ort: synthetisch findet er Versatz zurueck (Erker:1 (0.8,-1.2,0.5) -> (0.796,-1.196,0.496)), Bestimmtheit je Achse via Plateaubreite > 0,3 m = nicht bestimmt (METHODE_GPU_SWEEP) [B].
- GPU-Beschleunigung: Ausrichtung alter Generator -> Wolke ~500x Durchsatz (CPU KD-Baum 0,12 Mio/s vs GPU 60 Mio/s) (NG "BEWEIS Beschleunigung") [B]. Gitterverfeinerung gesamt 59,7 s (LOG_VERFEINERN) [B].
- Gitterverfeinerung `gitter_verfeinern.py` mit hartem Deckel maxshift 5 cm und eingefrorenen Formen: Stuetzung Mittel 0,469 -> 0,497, Abdeckung z<12 0,90 -> 0,89 (Tor erlaubt -2) (LOG_VERFEINERN) [B]. Bei 15 cm: Abdeckung -4/-7 Punkte und verzerrte Pfeilerkaefige.
- Fotovorbereitung: Retry-Backoff gegen Wikimedia 429, KALTSTART-Saat = groesste sich bestaetigende Gruppe (110 von 132) (NS D) [B].
- Bildwert/Spec S7: Vorhersage "Boden lohnt nur Nord, Drohne Ost/West lohnt" stimmte laut Nachbewertung (AUFWAND_BEWERTUNG Zeile 16, Nachbewertung 12:25: "STIMMT") [B, Rest der Zeile abgeschnitten].
- Dachreiter/Tuermchen aus Foto-Vollbild-Messung statt Laser: Nadel 0,08-0,14 m, Knauf 0,67 m; Tuermchen OR 1,3 -> 1,1, Kegel 4,5 -> 5,3 m (Spitze 41,35 m vs Laser-Maxima 40,9/41,4) (LJ) [B].

## 2. Was ist gescheitert und warum

**Messung / Kamera**
- Reprojektionsfehler als Lagemass: blind fuer f 2 % = 0,6 m und Wolkenversatz 0,5 m (PK 2, NG BS1) [B].
- Einzel-Kamerafeinlage / Kameraausgleich (BS3a-d): 12 gueltige Fotos bestehen die Gegenhaelften-Pruefung nicht (Ueberanpassung); `kosten_lr` hat kein eindeutiges Optimum; Rotation erst ab ~0,5 Grad/20 px erkennbar, Zentrum 3-10 cm nicht rueckholbar (synthetisch). Erster Lauf UNGUELTIG durch CUDA-OOM, VRAM-Doppelbelegung durch eigene Parallelitaet (Foto 073 ~3,6 GiB); OOM-Fehlproben kosteten ~1,5-2,5 h (PK 12) [B].
- Aussage "073 schlechte Kamera" = Messartefakt (Raster 0,24 m); "gemeinsamer rx 0,3 Grad = Netzfehler" zurueckgezogen (NG BS3e, BS3d-ERGEBNIS) [B].
- Falsche Ausrichtungsdatei: `SFM-AUSRICHTUNG-alle.json` passte nicht zur Wolke dicht_alle, 60 m daneben (NG BS10, PK 3) [B]. Gleichartig: `mt_org` war der OSM-Knoten, 37 m daneben (MM 8) [B]; Wolke aus gemeinsamer SfM 1,6 Grad gekippt (Umeyama auf flachen Kamerazentren legt Rotation schlecht fest, NG BS146) [B].
- `vis`-Index in vier Werkzeugen falsch ueber sortierte Namen statt COLMAP-Bild-ID (PK Kurzbewertung; Korrektur `freiraum_pruefen.vis_ids`) [B].
- PnP mit hochliegenden Ankern: Fit 6,6 px, aber Kamerahoehe 13,8 m (unmoeglich); mit realer Augenhoehe 31 px (LJ 14) [B]. Handpicks aus verkleinerten Gittern +-20 px sind der Engpass (MM 8). Handpunkte nie als Messung (NG BS148: Pfeilerabstand 6,6 m/7 Grad Schraege durch RANSAC -2,0/-1,3 Grad widerlegt) [B].
- Verschiedene Kamerasaetze erzeugen Scheinversatz bis 0,09 m (Baldachine "Krone nicht mittig"; Absolut-Pruefung blieb gruen, nur die Differenzpruefung war rot) (NG 11.11.) [B].

**Netz / Wolke**
- 3DGS/2DGS (kosten_lr -0,06 vs -0,104), feineres Netz (-0,081/-0,042 vs -0,104/-0,091), Min-Cut/PolyFit-Nachbau (~0, 7x schlechter), Wasserdicht per pymeshfix (-0,073/-0,078), Glaettung (Taubin 5 Iter -0,0786, 20 Iter -0,0600: "zerstoert Kanten"), Belichtungs-/CLAHE-Sweep (+31 % Punkte, gleiche Fehler), Triangulation mit gelockerten Schwellen (171 130 Segmente/422 km = Rauschen) (NG) [B].
- Wasserdichtmachen von mvs_default ENDGUELTIG aufgegeben (BS20-20f): trimesh fill_holes wirkungslos, Open3D bleibt nicht manifold, Fan-Deckel schneidet das Innere (565 von 677 Flaechen; "wasserdicht" nur formal, Volumen 1,62e6 -> 1,05e6), Poisson depth 9/10/11 nicht wasserdicht, Blasen/Fladen am offenen Boden. Erst Offset-Schale (Marching Cubes, BS23) war wasserdicht, im Diff aber NICHT unterscheidbar vom Original (+0,0006, KI -0,0031..+0,0044) [B]. Lehre: "wasserdicht: ja" im Bericht sagt nichts; Flaechenzahl/Ausdehnung/Bild pruefen (PH 4, LJ 5).
- Hoehenskala der Wolkenlage: Optimierer SCHRUMPFT das Modell, wenn die Wolkenregion mitwandert (su 0,65, sz 0,82; ICP freier Massstab 1,0 -> 0,75) (NG BS143, BS145) [B]. Fix: feste Wolkenregion + Wolkenpunkt ohne Modellnaehe kostet.
- Parametergrenzen kleiner als der Fehler: Helme-Fit mit +-0,5 m scheiterte, mit +-2,5 m gefunden (dn -1,4/-1,1; Median 0,088) (NG BS138+) [B].
- Wolke ist am Dach duenn/falsch: Dach > 15 m nur 1337 Wolkenpunkte; Wolke liegt am Dach "~1 m tief" (LOGBUCH_GAUBEN_OBEN, BEWERTUNG_KANTENGITTER). Webfotos von oben: 3/8 registriert, Dach >15 m Wolke 0,20 -> 0,24, 0 neue Dachkanten (NG 9.11.). Commons-Nachholung: 6 von 24 registriert, alle Ost-/Schraegsicht, 0 Sued/Dach/Erker (NG BT-WEB) [B].
- Video-Quellen: YouTube Muensterplatz, Drohnenclips, Google-Earth-Flug: 0-5 Frames brauchbar, Objekt <1 % der Bildflaeche oder reine Drehung ohne Parallaxe; Google-3D = Photogrammetrienetz (Modell aus Modell) (NG) [B].
- Relief aus Einzelbild (Depth Anything V2): Korrelation 0,16, schlechter als Nullschaetzung, erfindet 0,04 m Relief (NG 11.11.) [B] - nur als Lagekarte brauchbar.

**Details aus Wolke**
- Bogenkontur aus Foto-Median-Ortho: zerschmiert, Parallaxe, "Nutzer sah es zuerst" (NG BS9); Bogen-RANSAC auf Laibung: Kronen 17 m / Ein-Flanken-Kreise, R-Spanne von 0,5 m Daten (BS13); Bogenbauteil aus Wolke im Diff signifikant SCHLECHTER als Basis (BS16: Bootstrap-KI W-B Region +0,0125 [0,0041; 0,0223]); Ursache offen (BS21d: Kamera-Versatz nicht gestuetzt) [B]. S9 verwarf 4/4 Fits, S10 3D-Kantenfeld fand 1/4 (PK 7).
- Fenster: 5 Typfenster eingebaut (BS30-33b) -> Diff NEUTRAL (-0,0008, KI -0,0050..+0,0029); das Fenster ist flach, der Diff blind dafuer (NG BS84) [B].
- Dach: z-Skalierung 0,87/0,93 schlechter (BS58); Dach-dz-Sweep flach/Rauschen (BS98-101); Dach-Schaerfen-Raster nur Rauschen (BS112/115). Treppengiebel-Varianten TGa +0,0067 schlechter (BS82), TGd +0,0009 (BS87) [B].
- Wolke -> Hybrid Generator-Rumpf nur in Luecken (BS46): nicht monoton, Gewinne 0,003-0,005 (BS46b) [B].
- Bauteilweise Einpassung gegen Wolke verschlechtert den Foto-Diff (BS95), Kreislauf-Tor per Diff: keine Gruppe uebernommen (BS55) [B].
- Wolken-Gruppenhoehe (BS78/81): Giebel +3 m ueberschiesst, Wahrheit ~+2 m (Overlay 004) [B].
- Kantengitter: Streuerfilter per Score, Kontrastfilter gegen Sweep B, Union A+B, Buendelung im Dach, Phasenkongruenz/DexiNed als Einzelquelle, gleichgewichtete Fusion, Voxelhuellen/Schnitzen scheiterten; "jeder Filter, der nur an EINER Referenz eingestellt wurde, entfernte echte Kanten" (BEWERTUNG_KANTENGITTER 2) [B]. Statistik-Kontrastfilter: Wolken-Gegenprobe 0,87 -> 0,71 (NG 9.11.) [B].
- Kanten-NCC-Tiefenscan entlang Epipolarlinie: kein Gipfel (NCC 0,05-0,15), wiederholte Streifenmuster (NG 12.11., Ursache nur Vermutung). Erker-Schraegflaechen als gedrehtes Frontnetz: Durcheinander im Render (Vermutung: Trichter nicht rotationssymmetrisch). Rippen S1/R4 per kante_auf_flaeche: Gegenprobe in 2. Foto FAILED (30 px in die Luft); "kleiner Tiefenrest beweist nichts" (NG 12.11.) [B].
- Rippen: duenne Rippen (b 0,07 am Foto gemessen) lassen Druckpruefung fallen (93 Teilnetze), Rippen bis 0,18 m Tiefe 0,07 ebenso (91 Teilnetze); Ursache deckungsgleiche Stirnflaechen/Ueberhang (NG 12.11.) [B]. Rippentiefe aus Fremdfotos per Maske-Distanzkarte: kein Gewinn (Pruef <=30 px 0,508 -> 0,510); Naheaufnahmen benoetigt (NG 12.11.) [B].
- Foto-Metriken blind: Foto-F1/f1_h/f1_v/SAM-iou bewerten die um 90 Grad gedrehte Nullkontrolle BESSER als die echte Konsole (0,80 vs 0,71); nur f1_fein trennt (NG 11.11.). Bei Baldachinen/Erker-Elementen sind Nullkontrolle ("hoch" +0,3 m) besser als Vorher, d.h. weder Messbarkeit noch Lage klar (NG 12.11.) [B]. Kantenmessung entscheidet keine Formfamilie (Saegezahn vs Treppe -0,002; SPEC_FLAECHENMASS, SPEC_FORMFAMILIE) [B].
- Periodische Reihen: `fensterreihe:og` bleibt GRUEN auch bei 1 m Versatz (hit 0,92-0,98); Endelement-Test und rand_hit trennen nicht (LOG_TEILE_SICHT Nachtrag) [B]. Saeulen ROT trotz sichtbar passender Zylinder (glatt, keine Kanten) -> Silhouetten-Gradient thr 1,1 (korrekt 1,4-2,1, versetzt 0,0-1,1).
- LLM als Beurteiler (3x Sonnet, Overlay-Paare): Eichsatz 49 % klar, Nullkontrolle 50 % (Regel >= 80 %) -> nicht tauglich (NG BU-LLM, PK 7) [B]. (Spaeter SPEC_FORMFAMILIE setzt dennoch `claude -p` opus als Bildpruefer fuer Formfamilien an - dort nur geplant [A].)

**Prozess**
- Rueckfrage-Stillstand 04:24-08:15 (~4 h verloren) (PK 12). Strang D (paarweise ALIKED/LightGlue auf CPU, 45+ min, 16 Kerne, kein Ergebnis) vom Nutzer beendet (UEBERGABE 7, AUFWAND Zeile 11 "K" = kein Nutzen).
- Nachtlauf 12.11. 00:30-07:45: 34 Laeufe, nur Mini-Annahmen; Erker/Baldachine/Figuren/Gauben nie Ziel, weil der globale Sperrzaehler (3 Fehlversuche) Verwerfungen unter dem alten rauschblinden Tor mitzaehlte. "Neues Tor = alte Sperrzaehler zuruecksetzen, vor dem Nachtlauf `--nur_wahl` ansehen." (NG 12.11.) [B]
- Leere Runden: Teil 'laubengewoelbe' war fuer den Kreis unsichtbar (beob_ziele nimmt nur gemessene Teile): 5+ Leerrunden; Westgiebel 4 leere Runden (Rueckseite ohne Foto) (NG 11.11.) [B]. Fehlzuordnung durch mich: Treppen-Fund des Nutzers lag an staffelgiebel:ost, Saegezahn war nur West (NG 11.11. 12:51) [B].
- Agenten-Berichte: Zahlen zu pruefen (UEBERGABE Fallen "Subagenten-Berichte nachpruefen"); "Selbstbezug": Pruefung auf demselben Messpunkt wie die Aenderung (Rueckkante z 22,747 -> Beleg 0,589 -> 0,699, verworfen, NG 10.11.) [B]; Balkonband-Rettung F1 0,613 -> 0,824 teilweise Schrumpf-Artefakt (Fotokanten im Teilbereich 188k -> 63k px) [B].
- `json.dump` formatiert objekt.json/fassade.json um (grosser Diff; fassade.json NIE mit json.dump, UEBERGABE, NG 12.11.) [B].

## 3. Regeln/Tore: was wirklich etwas verhindert hat / nur Aufwand war

**Hat verhindert (mit Beleg)**
- Pruefstand + "Pruefung muss am alten Modell ROT sein": verhinderte stilles Zurueckkommen von Fehlern (PH 2.6) [B].
- Quellen-Blindheit (Exit 2) und Ankerzone-Sperre: verhinderten Pruefzeilen aus Extrapolation (MM 2, 8) [B].
- Holdout-Disziplin / Bootstrap-KI: verhinderte falsche Siege (BS16, BS23b, BS32: Differenzen im Rauschboden; "default vs Saeule nicht signifikant") [B]. Aber: Holdout flog in SfM/MVS ein, nur aus dem Ausgleichs-Fit ausgenommen -> nicht voll unabhaengig (REVIEW-CODEX, REVIEW-GOOGLE, PK 8); 6 Holdout-Fotos durch Mehrfachauswahl verbraucht -> neue Fotos als unangetasteter Abschlusstest reservieren [B].
- Gate-Pruefung "kein Parameter an der Suchgrenze" (BS151: Teilfit bogenreihe:laube entartet, Gesamtscore-Tor liess ihn durch, Rauschen 0,02) [B].
- Gleiche-Volumen-Pruefung (Aussparung ohne n_front schnitt nichts: "erkannt am gleichen Volumen", NG 12.11.) [B].
- Gate "Abdeckung -2 Punkte" bei Gitterverfeinerung: erzwang maxshift 5 cm statt 15 cm (LOG_VERFEINERN) [B].
- Mindest-Ueberlappung >= 0,1 m (frueher 1-2 cm) und Koerperzahl 1: verhinderte schwebende Teile (LJ 4, 19) [B].
- Rauschtor mit Nullkontrollen und Synthetik-Beweis vor Einbau jedes Tors (SPEC_STOERMASKE: "Beweis Pflicht", METHODE_GPU_SWEEP: Beweis zuerst) [M: als Regel, Wirksamkeit je Fall]
- Foto-Zaehlung nur am Foto (BS25b: Wolke-Ortho findet 5 Fenster, "kein Sollwert") [B].
- Lizenzbefund vor Verkauf: OpenMVS AGPL-3.0, CGAL/PolyFit GPL, 3DGS-Familie NC, nvdiffrast NC, ELSDc AGPL, PiDiNet "research only" (NG BS24, RECHERCHE_KANTEN_2, RECHERCHE_KANTENGITTER) [R/B] - fuer ein verkauftes Produkt relevant, nicht fuer das private Testprojekt (Nutzerfreigabe 7.11.).

**Nur Aufwand / wenig Wirkung / ungeeignet**
- Kameraausgleich je Foto (BS3), Reprojektionsfehler je Foto (BS1), LLM-Beurteiler, Kamerarestversatz-Korrektur in teile_sichtpruefung (Standard AUS, "SfM-Posen mm-genau") [B].
- teile_sichtpruefung: 20 von 22 Teilen ROT, Spezifitaet gering; Schwellen thr_gewinn 0,15/thr_recall 0,45/thr_sil 0,55/thr_himmel 0,06 sind synthetisch, nicht an einem echten Referenzdatensatz verifiziert; GRUEN heisst nur "kein Widerspruch gefunden", ROT belastbar nur bei Himmel/Wolke/Silhouette (Westgiebel, Helme, Erker) (LOG_TEILE_SICHT) [B].
- Mehrere konkurrierende "beste" Modellstaende und Kennzahlen (PK Kurzbewertung); Sitzungsaussage "d03_fix bester Kandidat" korrigiert zu "druckbare Referenz" (NG BS116) [B].
- Unterlassungen mit Gewinn: Fotokanten-Zwischenspeicher "nicht der Engpass" (BS8); Beschleunigung teil_fotoform Schnellweg nur 230 -> 207 s statt -50 % (NG 10.11.) [B].
- 20 handgemessene Kanten als "Handwahrheit" gefordert (BEWERTUNG_KANTENGITTER Luecke 4, Plan 5; RECHERCHE_KANTEN_2: 6-10 Fotos, 2-3 h Nutzerzeit) - [A] noch nicht ausgefuehrt, ohne sie ist "jede weitere Verbesserung nicht messbar" (RECHERCHE_KANTEN_2) [R/M].

## 4. Werkzeuge (tools/*.py, soweit in den Dokumenten genannt)

Zustand: **laeuft** = im Dokument als gelaufen/Selbsttest bestanden; **ersetzt**; **tot/verworfen**; **offen**. Zustand aus den Dokumenten, nicht erneut ausgefuehrt.

| Werkzeug | Zweck / wann | Zustand (Beleg) |
|---|---|---|
| `pruefstand.py`, `bauen_abnehmen.sh`, `masstabelle.json` | Pflichtrahmen; nach jeder Generatoraenderung | laeuft (MM); Vorgaenger `modell_pruefstand.py`/`martinstor_bauen.sh` ersetzt (PH 2.6) |
| `objekt_anlegen.py`, `nullstart.py`, `objekt_daten.py` | Neues Objekt mit objekt.json, Kaltstart bis Wolke | laeuft fuer Kaufhaus; Seitenvorzeichen-Bug N-S/O-W behoben (NS D); NS B-Liste: Martinstor-Wissen in nullstart.py (Seiten, Fotos 060/061, Hoehe 44 8) nur teilweise bereinigt [Stand 3.11., spaeter nicht geprueft] |
| `sfm_lod2_ausrichten.py` | Ausrichtung SfM an LoD2/DGM1 ohne Handpicks | laeuft (NS D) |
| `foto_kalibrieren.py`, `foto_pick_pruefen.py` (PFLICHT), `foto_bundle.py`, `foto_mass.py`, `foto_pick.py` | Einzelkamera/Bundle/Messung Pixel -> Meter auf Wandebene; Protokoll M-/K- | laeuft (MM 7-8); Handpicks ±20 px Engpass |
| `foto_verhaeltnis.py` | Hoehenverhaeltnisse aus fernen Fotos (~1 km) | laeuft; bricht bei >10 % Messstrecke ab (MM 8b) |
| `fehlteile_finden.py`, `foto_diff.py`, `teile_lage_pruefen.py` | Rot/Blau-Diff Modell vs Foto | laeuft; `teile_lage_pruefen` stuerzt bei Einzelteil-Szene ab (trimesh Scene KeyError 'world') (NG 10.11.) |
| `foto_diff_batch.py` | Punktmodus 2,1x schneller | verwendbar, aber Punktfassung degeneriert bei Tele 073; Raster ist Messziel (PK 5) |
| `modell_wettbewerb.py`, `versuch_log.py` | Netzvergleich; automatische Rohspur `versuche_auto.jsonl` | laeuft; ohne Konfig-Fingerabdruck/Vollstaendigkeitsgate (REVIEW-CODEX) |
| `kamera_ausgleich.py`, `kamera_unabhaengig.py`, `bogen_fit.py`, `bogen_kontur.py` | Kameras/Boegen | tot/verworfen (BS3, BS9, BS12, BS13) |
| `kamera_guete_lot2.py` | LOO-Kameraguete | laeuft (LOG_KAMERA_GUETE); `kamera_sfm_guete.py` nur Ersatz |
| `wolke_ueber_foto.py` | Wolke ins Foto | laeuft, Netzkanten-Kennzahl defekt (BS10) |
| `wolke_front.py` | gefaerbte Wolke frontal (Ortho, z-Puffer, GPU) | laeuft (BS11); Tiefenfenster ±6 m zu gross |
| `wolke_bereinigen.py`, `wolke_abstand_region.py`, `wolke_abweichungskarte.py`, `wolke_abweichung_o3d.py` | Filter/Abstaende | bereinigen: Wolke 961k -> 805k (BS41); 1. Abweichungslauf UNGUELTIG (Wolke ungefiltert) (BS36d) |
| `wolke_gruppen_fit.py`, `wolke_gruppen_hoehe.py`, `generator_teile_einpassen.py`, `generator_kreislauf.py` | Einpassung Generatorteile gegen Wolke | Ergebnis: verschlechtert Foto-Diff (BS52-BS55, BS95) - Werkzeug laeuft, Methode verworfen |
| `teil_sweep_gpu.py`, `sweep_alle.py` | GPU-Sweep Bauteil-Ort | laeuft; Fenster-Beweistest faellt durch (METHODE_GPU_SWEEP) |
| `kanten_3d_vote.py`, `kanten_triangulation.py`, `kanten_fusion.py`, `kanten_segmente.py`, `kanten_schleife.py`, `editor_draht.py`, `gitter_aufbauen.py` | Kantengitter-Kette (ERKLAERUNG_DRAHTGITTER) | laeuft; `--qe`-Bugfix (Segmente 4 % zu kurz -> 0,3 %) |
| `gitter_verfeinern.py` | Endpunkte per DT-Verlust, Topologie | laeuft (LOG_VERFEINERN), Standard 5 cm |
| `gitter_koerper.py` | Gitter -> Ebenen -> Rohkoerper (manifold3d) | laeuft (1 s bauen, 2,5 min pruefen) (LOG_KOERPER) |
| `helm_fit.py` | Helm als n-eckige Pyramide (GPU) | laeuft, grosser Helm gut, kleiner Helm zu breit/hoch |
| `limap_lauf.py`, `limap_auswerten.py`, `limap_kantenzwang.py` | 3D-Linien aus Tiefenkarten | gelaufen (3 min); Kantenzwang im Diff Rauschen (BS61, BS65) |
| `teile_sichtpruefung.py` | Teil gegen >= 2 Fotos aus >= 2 Richtungen | laeuft; Spezifitaet gering (s. 3) |
| `formfamilie_pruefen.py`, `flaechen_mass.py`, `foto_stoermaske.py` | Specs 11.11.: Formfamilie per Bildpaar/`claude -p` opus; SAM-Flaechen-IoU; Stoermaske SegFormer+OWLv2 | **Specs, Umsetzung/Ergebnis in diesen Dateien nicht belegt [offen]** |
| `bildwert.py`, `fehlerkarte.py`, `abdeckung.py` | Wert eines Kandidatenbilds | Spec (SPEC_S7); `abdeckung.py` soll ersetzt werden [Spec] |
| `h0_druckfertig.py`, `scan_zu_koerper.py`, `viewer_bauen.py` | Massstab/Wasserdicht/Teilen; Scan->Schichtkoerper; 3D-HTML | laeuft (PH); Hofgut-pymeshfix-Bug behoben |
| `hypso_gpu.py`, `generator_optimierer.py`, `optimierung_validieren.py` | Hoehenkarten 2106 Drehungen (GPU==CPU bit-gleich), Koordinatensuche, Annahmeregel | laeuft; Aufgabe Martinstor |
| `foto_silhouette_gpu.py`, `foto_dachtest_gpu.py` | Silhouette gegen Foto, IoU-Rauschen 0,01-0,04, Azimut ±90 Grad mehrdeutig | laeuft; nicht beweisend fuer Einzelmasse |
| `doppelschicht.py`, `lotpruefung.py`, `wolken_vergleich.py`, `dicht_vorpruefung.py`, `aufwand_log.py`, `zeit_je_modell.py`, `video_dicht.py`, `video_sfm.py`, `video_masken.py` | Wolkenqualitaet / Aufwand | Selbsttests bestanden (UEBERGABE), nicht von `regression.py` gedeckt, Schranke steht nicht in nullstart/treppe |
| `netz_verfeinern.py` (PyTorch3D), `netz_winding.py`, `objekte_schliessen.py`, `fenster_einbauen.py`, `fenster_fit.py` | Netzverfeinerung/wasserdicht/Fenster | verfeinern: Holdout -3,7 % aber im echten Foto-Diff +-0,007 (BS38b/e); winding: nicht wasserdicht (BS40) bzw. mit GWN+groesster Komponente (BS133); Fenster: neutral |
| `baukasten_gen.py` (stl_teil, bogenreihe, gaubenreihe, staffelgiebel ...) | Baukasten-Generator fuer grob3 | laeuft; regression soll bitgleich bleiben bei neuen Parametern |
| `relief_aus_foto.py`, `epilinie.py --ncc`, `pfade_tiefe_mehrfoto.py`, `kante_3d`/`kante_auf_flaeche` | Tiefe aus Einzelbild/Mehrfoto-Linie | verworfen als Hoehenquelle bzw. ohne Gewinn (NG 11./12.11.) |
| `teil_fotoform.py`, `teil_varianten_tor.py`, `kreis_*.py`, `bauteil_kreis.py` | Foto-F1 je Teil; Best-of-N; Kreis-Runden | laeuft; Variante-Tor nur f1_fein trennbar |
| `platz_pruefen.py`, `job_start.sh` | Platz-/GPU-Tor | geplant/gebaut (AUFTRAG G1); GPU-Semaphor nur im eigenen Prozess |
| `commons_harvest.py`, `bilder_holen.py`, `bilder_schleife.py` | Bildbeschaffung | laeuft; Bug `a.stufe`; Schwaeche M13 (Seite eines geholten Bildes = Seite des Nachbarfotos); Strang D CPU-Kalibrierung unbrauchbar |
| `terrain_eggcrate.py`, `laser_pack.py`, `ortho_drape.py`, `bewerter_*.py`, `schwarzwald_katalog.py` | Gelaende/Laser/Bewertungspanel | andere Projektlinie (METHODIK_KOMPLETT, NACHT_BERICHT) - nicht Kaufhaus |

## 5. Fallen und Nutzer-Rueckmeldungen

**Wiederholt vom Nutzer bemaengelt / eingefordert**
- "Nutzer sah es zuerst": zerschmierte Bogenkontur (BS9); Proportionen (LJ: "Nutzerblick ernst nehmen – er fiel auf, obwohl alle Zahlen gruen waren"); 8 Formfehler am 11.11. 08:38-08:48 im Viewer (Saegezahn statt Treppe, spitz statt rund, Rechteck statt Bogen, Sockel zu niedrig, fehlende Aufsaetze/Gelaender), die der Kreis nie fand (SPEC_FORMFAMILIE) [B].
- Foto-Messen statt Wolke fuer Form; Zaehlen nur am Foto (Regel 9); Wolke Lage-Veto (CLAUDE.md, PK 0). "Wolke ist die Wahrheit fuer Form" (PK 0, Nutzerregel `wolke-einzige-basis`) widerspricht der spaeteren Regel "Foto-Kanten richten Form, Wolke nur Veto" (CLAUDE.md) - siehe 6.
- Nutzer 6.11. verlangte Erkennen + Einpassen mit freien Parametern iterativ + Medianfilter (SPEC_S9); Nutzer 5.11.: "beweise, generalisiert" (SPEC_BEWEIS_ANSATZ); "Perfektes 3D-Modell zuerst; Sweetspot spaeter schnell durch die Stadt" (UEBERGABE); "Bodenwolke nie gefaehrden" mehrfach deutlich.
- Nutzernachrichten werden oft abgeschnitten ("gib", "Botschaft" = Bodenwolke) - nicht raten (UEBERGABE) [B].
- Nutzerfreigaben: Web-Bilder fuer privaten Test erlaubt (7.11.), Google erweitert fuer Test, keine Umgehung technischer Sperren; Lizenz je Bild in LIZENZ_BILDER.json (NG).

**Angenommen und falsch**
- Martinstor-Hoehe 45,3 m (LoD2/Scan/OSM "drei unabhaengige Quellen") -> 54 m -> 54,80 m (DOM1). Die drei Quellen hatten dieselbe Luecke (Dachreiter) (LJ 1 -> 6) [B]. Texte 60-66 m ebenfalls falsch.
- Gauben am Martinstor (aus alter Notiz) -> Foto: glatt, keine Gauben (LJ 0) [B]. Zifferblatt 4,6 vs 4,2, Durchfahrt 6,6 vs 4,7, Wappen 2,8x3,2 vs 1,7x2,3 (Augenvergleich schraeger Bilder) (LJ 13) [B].
- Schafttiefe-Verjuengung 9,8 -> 9,3 -> 9,0 des Martinstor-Generators ist ANNAHME (aus Silhouetten-Breiten, keine Tiefenmessung); "Wand senkrecht" widerlegt durch Restscherung +17..+35 mm/m (UEBERGABE 2-3) [B].
- Sued-Netz Martinstor entartet (Kameras bei x 4-5 statt 28-40 m; ~7x zu klein), nicht Datenmangel sondern Softwareproblem (AUFWAND 13) [B].
- Martinstor Bogen/Sockel: Scheitel 6,55 m war 1,5 m zu hoch (aus schraeger Aufnahme) (LJ 17) [B].
- Dachgauben "Giebelgauben" (LOG_FORMEN) -> Fotos zeigen Pultdach (LOGBUCH_GAUBEN_OBEN) [B]. "Dienst vor jedem Joch bis zum Boden" falsch: Muschel z 5,03, darunter glatte Wand (NG 11.11.). Rechter Erker: neue Wolke Mitte 9,8/Breite 3,9 vs Modell 8,36/1,75, LoD2-Ecke 9,64 - Widerspruch offen (METHODE_GPU_SWEEP).
- Ostwand u 9-24 ist Nachbarhaus, nicht Kaufhaus (NG BS136-Nachtrag) [B]. Fotos 005, 074, 089, 106, 107 zeigen Umgebung, nicht das Netz (NG BS19) [B].
- Wolke -> Modell: "Pfeiler 0,9 m deutliches Minimum" zurueckgenommen (Einzelfoto-Artefakt, Split-Half). Alte Wolke "SFM-AUSRICHTUNG" 60 m daneben.
- Erker-Figur-Vorsprung 0,45 -> 0,35 (Render gegen Foto) (NG 11.11.). Unterspitze: tiefster Punkt am Gesimsrand, nicht 0,5 m draussen (M-6145-003).
- Rolle von LoD2 ueberschaetzt: keine unabhaengige Wahrheit (aus Laserdaten abgeleitet, verallgemeinert) (LJ 15). Wolke-gegen-LoD2: nur 6 % < 0,1 m, 59 % > 0,6 m (BS47).

**Technische Fallen**
- Float/Voxel: `voxel_solid` Massstab um 1/Pitch zu gross (658 statt 527 mm); `wasserdicht()` pymeshfix behaelt nur groesste Komponente -> Hofgut 20-Flaechen-Platte (PH 4, LJ 5).
- STL nicht wasserdicht trotz sauberer Booleans, wenn sich Teile nur an einer Kante beruehren; CSG-Reihenfolge: Details in Nischen NACH dem Abziehen (`late`) einfuegen (Uhr, Adlerrelief 2x) (LJ 4, 20) [B].
- Optimierer-Wettlauf um `cur.stl` (parallele Prozesse, gemeinsame Zwischendatei) (LJ 21, CLAUDE.md "nie zwei Laeufe mit gleicher Zwischendatei") [B].
- GPU-OOM durch eigene Parallelitaet; `tools/sfm_dicht.py` loescht Ausgabeordner `dicht_<seite>` per rmtree (PLAN_LEAVEOUT) [B]. `pkill -f` trifft die eigene Shell; Foreground-sleep gesperrt (UEBERGABE).
- `teil_fotoform` ohne `--teile_dir` baut aus AKTUELLER objekt.json: "Vorher"-Baseline nach Edit ist schon Nachher (gleicher stl_sha) (NG 11.11.) [B].
- Rasterartefakt in Nahaufnahmen < 5 m: rote Strahlenbuendel, Fotos mit z_med < 5 m nicht werten (LOG_TEILE_SICHT). Wolke durch Passanten/Boden: z 1-3 m Median 0,86 m (LOG_KOERPER).
- Speicherplatz: Root-Platte war 100 % voll; Tor `platz_pruefen.py --root-min-gb 5 --daten-min-gb 15` (AUFTRAG G1).
- Nummern doppelt vergeben (BS49 zweimal), NG-Kopf "Stand 7.11." obwohl Eintraege bis 12.11. (siehe 6).
- Anleitung Handy (nubia Z2462N): Menuepunkte nicht belegbar (Web), RAW, OIS, Ausgabeformat unbekannt; empfohlen: Hauptkamera 1x, kein Zoom, Wasserzeichen aus, Standort an, ein Aufloesungsmodus [G/V im Dokument markiert] (ANLEITUNG_FOTOS_NUBIA).
- Nur [R]: LLM-/Web-Recherchen zu Kanten (SketchSplat MIT, EdgeGaussians keine Lizenz, CGGT arXiv "2609.14521" - Zitat unverifiziert) nicht selbst erprobt; LIMAP pylimap 2.0.0 BSD (belegt per pip index) aber im Diff Rauschen.

## 6. Widersprueche zwischen Dokumenten / veraltete Stellen

1. **Martinstor-Hoehe**: LJ Eintrag 1 (45,3 m "drei Quellen") und PH Zeile "v3 45,3 m" sind ueberholt durch LJ Eintrag 6 (54 m) und DOM1-Messung 54,80 m; PH-Tabelle nennt v4 "54 m" - Messung ist 54,80 [veraltet/unscharf].
2. **Wahrheitsquelle**: PH ("Daten-Methode fuer das Druckmodell, Scan nur zur Kontrolle") vs PK ("Wolke ist die Wahrheit fuer Form") vs CLAUDE.md ("Form/Masse richten sich nach Fotokanten, Wolke nur Lage-Veto"). Spaetere Praxis (grob3-Generator mit Baukasten und Kreis) folgt dem Foto, nicht der Wolke. PK Gate 3 "carv_kh3 als Fertigungsbasis" ist durch den Wechsel auf `kaufhaus_grob3` (BS72: Grobgenerator Diff identisch zu altem ausgerichtetem Generator -0,0320) ueberholt.
3. **Kameragenauigkeit**: LOG_TEILE_SICHT/LOG_KAMERA_GUETE "SfM-Posen mm-genau (Median 2 mm)" vs NG BS12 "Eichrest ~12 cm (Rauschboden Buendelneuausgleich)", BS3d "Zentrum 3-10 cm nicht rueckholbar", NG BS10 (Kamera 114 Wolkenrand 4,0 px). Unterschiedliche Messarten (LOO-Triangulation vs Neuausgleich vs Diff); nicht gleichgesetzt; in teile_sicht 0,1-m-Handfotos mit Kamerafehler > 0,1 m.
4. **pymeshfix/GPL**: NG BS20 "pymeshfix nicht installiert (GPL, Verkauf geplant -> nicht verwenden)" vs BS124 (pymeshfix auf hlo-Ableitung benutzt), LJ 5 und PH 2.1 (pymeshfix ist Standard in h0_druckfertig), BR "pymeshfix". Lizenzstand ungeklaert [offen].
5. **Poisson**: PK 5 nennt Poisson als Kandidat; NG REVIEW-GOOGLE "Poisson hat verloren, OpenMVS gewann"; BS20e/f Poisson untauglich (nicht wasserdicht, 14x zu gross); SPEC_BEWEIS_ANSATZ nimmt Poisson als Verfahren A (Photogrammetrie) - Spec vom 5.11., vor BS20.
6. **LLM-Beurteiler**: NG/PK: nicht tauglich (49 %/50 %); SPEC_FORMFAMILIE (11.11.) setzt `claude -p` opus als Urteiler ein [A, Wirksamkeit unbelegt, Prompt auf Formfamilien beschraenkt].
7. **NG-Kopf** "Stand 7.11.2026", Titel "Kaufhaus, Wolke -> Netz"; die Datei enthaelt aber Eintraege bis 12.11. und Martinstor-Themen; BS49 doppelt (Druckkandidat 1 / Min-Cut-Agent, NG selbst vermerkt NUMMERNHINWEIS). Kurzindex im Kopf nennt BR/BS4-BS8, nicht die spaeteren Eintraege.
8. **PK Stand-Aussagen**: "Letzter Laufstatus rcpark-kh24_raster lief" wird im Dokument selbst als veraltet/unbestaetigt markiert; "94 registriert" vs 440 (kam_lot2 spaeter) vs 92 IDs aus S10-Befund. PK "Regression noch nicht gelaufen".
9. **MM "Sollwerte nie lockern"** vs RECHERCHE_KANTEN_2 "Toleranz nicht lockern, um Gruen zu bekommen" - konsistent; abweichend: SPEC_FLAECHENMASS legt Schwellen (Unterschied >= 0,05) im Spec fest [A].
10. **NS A** nennt 248 feste Zahlen im Martinstor-Generator und "kein neuer Code pro Objekt" als Ziel; die Praxis (grob3: Bauteil-Rezepte, Kreis-Runden mit Handpatches wie `staffelgiebel_treppe_a125135.patch`) zeigt: Bauteil-Wissen bleibt objektspezifisch, nur Werkzeug ist generisch [M, Einschaetzung aus mehreren Dateien].
11. **Datumsreferenzen**: BEWERTUNG_KANTENGITTER nennt "51 Versuche destilliert" und "Logbuch Runden 1-4" - Dateien (LAGEBILD_KANTENGITTER, Logbuch) in dieser Liste nicht enthalten.
12. **Kontext**: FREIBURG_STRATEGIE/FINANZMODELL/NACHT_BERICHT/BELEUCHTUNG/METHODIK_KOMPLETT behandeln Miniatur-Wunderland, Schwarzwald-Terrain und Laser-Rippen (Linachtalsperre) - andere Projektlinie, nicht Kaufhaus-Pipeline.

## 7. Offene Fragen

- Bogenverlust im Diff (BS21): Ursache ungeklaert (Platte/t_back widerlegt, Kamera-Versatz nicht gestuetzt; Hypothese "Diff misst Raster-Tiefensprung, nicht Laibung").
- Keine unabhaengige Wahrheit fuer Kanten: Handwahrheit (20 Kanten) und synthetischer Rundlauf-Pruefstand fehlen (BEWERTUNG_KANTENGITTER Luecke 4, RECHERCHE_KANTEN_2 Handlungsliste 1: ~1-1,5 Tage + 2-3 h Nutzer).
- Fehlende Dachsicht: Kaufhaus-Dachkanten, kleiner Helm, Gauben, rechte Giebelkante unvollstaendig; Wolke dort duenn/versetzt (BEWERTUNG_KANTENGITTER 3).
- Rippen/Erker-Schraegflaechen: Tiefe nicht belegt (nur Lage in 6171), Naheaufnahmen nach `AUFNAHMEPLAN_ERKER_RIPPEN.md` noetig; Druckreparatur fuer duenne Rippen offen (NG 12.11.).
- Periodische Strukturen: identitaetsbehaftetes Mass (Periode/Phase aus `muster_fit`) fehlt (LOG_TEILE_SICHT).
- Saeulen: Farbgradient an Silhouette statt Stabilitaetskarte, erst synthetisch (LOG_TEILE_SICHT 1).
- Umsetzungsstand der Specs vom 11.11. (Formfamilie, Flaechenmass, Stoermaske) in diesen Dateien nicht belegt.
- Kettenbildung (Curvix-artig), Kurvenfits (SketchSplat-Idee) fuer Boegen/Helmgrate; EdgeGaussians als Vollstaendigkeits-Orakel (BEWERTUNG_KANTENGITTER Plan 1-6) [Plan].
- Rueckseite/Dachflaeche des Kaufhauses: ANNAHME (Rueckwand = Firstspiegel -6,56 m, Boden 1,50 m) (LOG_KOERPER).
- Lizenzfragen: OpenMVS AGPL (Produkt), pymeshfix, CGAL, PiDiNet, SAM-Eintrag in LIZENZ_WERKZEUGE fehlt evtl.; Bild-Lizenzen CC BY(-SA).
- Hoehenzone Martinstor: Westwandoberkante 30,5 m / Ankerzone; Sued-Netz ohne `SFM-AUSRICHTUNG-sued.json` (UEBERGABE 1).
- Nutzen-pro-Wanduhrstunde-Bilanz (Sweetspot) aus AUFWAND_BEWERTUNG: Gesamtbilanz "als Zahl in den Sweetspot uebernehmen" - Ergebnis nicht in den Dateien.
- Finanz/Strategie: Investitionskosten & Break-even Freiburg "eigene Schaetzung noetig (nicht belegt)"; Haftpflicht/Brandschutz offen (FREIBURG_STRATEGIE); FINANZMODELL Zahlen sind Szenarien [A].

## 8. Zeit-/Kostenangaben (aus den Dokumenten)

- Martinstor-Generator v3 laeuft ≈ 20-25 s (598-1034 Bauteile, 20-26 k Dreiecke) (LJ 3-4). Neues Objekt anlegen "10 Minuten" (MM 5) [A].
- Strassenfoto-Modell (Nullstart) Stufe grob Median 11,6 min (8,3-13,2), voll 6,3 min; dichte Nordwolke 50-90 % der Zeit, Sued-Netz ~20 % (UEBERGABE 8, `zeit_je_modell.py`, 33 Nullstart-Berichte) [B].
- Bodenwolke Martinstor (7 Bodenclips, 350 Bilder): 54 min Wanduhr ab 11:14, GPU 42 W, 0,038 kWh; Gesamtlauf ca. 1,6 h; PatchMatch nur 40-47 W, 443-545 MiB trotz "100 %" (UEBERGABE, AUFWAND 15) [B].
- Sitzung 3.11. 10:55-12:05: EINE Modellaenderung (Suedfenster 0,60 -> 0,77 m, ca. 2 mm in H0), Hauptnutzen Fehler/Annahmen aufgedeckt (AUFWAND Bilanz) [B, Zeiten geschaetzte Arbeitsminuten].
- Strang D 45+ min / 16 Kerne ohne Ergebnis; doppelschicht 25 min CPU; lotpruefung 40 min CPU; Rueckfrage-Stillstand ~4 h; OOM-Fehlproben ~1,5-2,5 h (AUFWAND, PK 12).
- COLMAP patch_match + Fusion ~40 min (Zeitstempel dicht_alle 16:58-17:37, PLAN_LEAVEOUT) [Schaetzung]. fTetWild 154 s (BS36c); Poisson/Offset-Schale als 'Job'-Laeufe; PyTorch3D netz_verfeinern 43 s/Schritt (BS38b), Uebergang 1074 s fuer 25 Schritte.
- GPU-Sweep Erker: je 6 min (BS154). teile_sichtpruefung: 56 s bis 833 s je nach GPU-Auslastung anderer Agenten. teil_fotoform 230 -> 207 s, "Profil: 40 von 50 s im Rendering". Gitterverfeinerung 59,7 s; gitter_koerper bauen 1 s, pruefen 2,5 min.
- Plan Kantengitter: Kettenbildung 1 Tag, Verfeinerung 1 Tag, Helm klein/Gauben 0,5 Tag, Wiederholungs-Prior 0,5 Tag, Handwahrheit 0,5 Tag (BEWERTUNG_KANTENGITTER) [A]. LIMAP-Installation 0,5 Tag; SketchSplat-Adapter 1 Tag (RECHERCHE_KANTENGITTER) [R/A].
- Nachtlauf 12.11. 00:30-07:45: 34 Laeufe, Nutzen minimal (NG).
- H0-Druck: Martinstor v4 155x165x621 mm, 3 Teile, 0,5 % duenne Wand (PH 5) [B]. Kaufhaus Rohkoerper 356x321x299 mm (LOG_KOERPER) [B].
- Finanz (FINANZMODELL_FREIBURG): Szenario Klein ~15 000 Besucher, ~120 000 EUR Umsatz, Break-even ~12 400; Mittel 45 000 Besucher, 495 000 EUR, Break-even 33 400 [A, nicht Pipeline].
- Cloud nur recherchiert (RunPod RTX 4090, Network Volume 0,07 USD/GB/Monat), nichts gemietet (PK 10).

---
## Die 8 wichtigsten Lehren (siehe Antwort)

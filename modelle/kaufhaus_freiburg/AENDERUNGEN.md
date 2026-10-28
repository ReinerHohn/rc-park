## Quercheck-Suite + 6 Form-Fixes (Fenster-Höhe, Erker, Balkon-Breite, Gauben-Raster)
Der User fand nacheinander Fehler, die KEIN Checker fing. Grundmuster (immer gleich): eine Eigenschaft,
die das Auge sofort sieht, hatte keine ZAHL-Metrik → rutschte durch. Fix = je Fehler eine messbare
Quer-Prüfung bauen und beweisen, dass sie den Fehler fängt.
- **Fenster zu gedrungen:** WIN_ASPECT kam aus fragiler Segmentierung (~0,97 statt echt 0,45). Zudem war
  die LOGIK falsch: HEAD=SILL+Breite/Aspekt ließ den Sturz ÜBER die Traufe schießen. Fix: HEAD/SOHL aus
  Messung (9,18/6,13), BREITE = Einheit/Bay-Teilung (0,54, aus kh_fenster) → hoch+schlank. Robuste
  Aspekt-Messung (Projektionen) in shape_extract. NEU `tools/proportion_check.py` erweitert um
  Fensterhöhe/Fassade → fing 0,10 vs 0,57 = „zu gedrungen". NEU `tools/fenster_check.py`.
- **Gauben ungleichmäßig:** x-Abstände waren 0,042/0,128/0,128/0,042 (CV=0,50) — an den Rändern gedrängt.
  Ursache: Reihen mit eigener Teilung statt gemeinsamem Raster. Fix: versetztes GEMEINSAMES Raster
  (untere Reihe gerade Slots 0/2/4, obere ungerade 1/3 = Lücken-Mitten) → alle Abstände gleich (CV=0,02).
  dormer_width_frac 0,59→0,51 (Foto-Spreizung). NEU `tools/gauben_check.py` (Abstands-CV) — bewiesen:
  ALT CV 0,50 FAIL, NEU CV 0,02 PASS, Foto 0,10.
- **Erkerfenster bis zum Dach:** jetzt rotes Mauerstück über dem Fenstersturz (wz 0,72→0,62, wh→0,42).
- **Erker-Helm:** startet unter der Traufe (z1 EAVE+0,1→EAVE−1,0), breiter überkragender Glockenfuß +
  gedeckelte Höhe + schneller konkaver Einzug (Foto: wuchtige Glocke, nicht Nadel).
- **Balkon:** nur noch vor den Fenstern (stoppt an den Erkern, BAL_X0/1), nicht über die ganze Breite.
- **„Dach schräg":** GEOMETRIE ist symmetrisch (Dach-Oberkante links=rechts, Δ=0 px) — der Eindruck
  kam vom diagonalen Schuppenmuster/Schattierung, nicht von Schieflage. Mit Messung widerlegt statt geraten.

LEHRE (deep-learning-Prozess): für JEDE neue Fehlerklasse eine Zahl-Metrik + Quer-Check bauen, nicht nur
den Einzelfall glätten. Markante, SICHER erkennbare Kanten nehmen (Farbzonen-Grenzen, Dunkelblobs) und
VERHÄLTNISSE/Rhythmen quer vergleichen — skalenfrei, robust. Checker-Suite wächst mit: proportion_check
(Band-Höhen+Fensterhöhe), fenster_check (Aspekt), gauben_check (Abstands-Regelmäßigkeit), + alte.

## Fenster-Ogee + Balkon dunkel + Gauben plastisch (User-Korrekturen)
- **Fenster (User: „eckig und so konkav … stimmen einfach nicht"):** win_profile.json war FLACH
  (h≈0,71 über die ganze Breite) → Fenster lasen als Rechteck. Ursache: die shape_extract-Box
  [0.435,0.37,…] fing erst bei y=0,37 an und SCHNITT die Kielbogen-SPITZE ab. Neu gemessen mit Box
  ab y=0,29 (Spitze drin) → echter Ogee/Kielbogen: Schultern h0,68 → Spitze h0,97 (shape_extract
  kh_fenster.jpg 0.435,0.29,0.565,0.605). Generator baut daraus den Schulterbogen-Kopf. LEHRE:
  Mess-Box MUSS das ganze Bauteil inkl. Spitze umschließen, sonst misst man eine abgeschnittene Form.
- **Balkon (User: „nicht zufriedenstellend"):** Brüstung war ROT. Foto-Pixel zeigen dunkelbraune
  Baluster (~55,40,38). → `gitter` [150,52,46]→[60,42,38], `balkon`-Platte [138,48,42]→[92,40,34].
- **Gauben (User: „die 5 Gauben … noch falsch"):** Anzahl/Lage waren RICHTIG (Blob-Detektor fand
  3 untere x0,26/0,51/0,76 + 2 obere versetzt x0,39/0,62 = 5, = DORMER_ROWS[3,2]). Problem war die
  DARSTELLUNG: flache dunkle Löcher. Fix: Walmdächlein HÖHER/steiler (apex zt+1,15) wie der tiled
  Ziegelhut im Foto + neuer heller Steinrahmen `gauben_rahmen` (Pfosten/Sturz/Sohlbank) ums dunkle
  Gaubenfenster. LEHRE: „falsch" hieß hier nicht Anzahl, sondern fehlende Plastik/Rahmen — erst
  Detektor fragen (stimmt die Zahl?), dann die Form nachbessern.
- **Beleg:** /tmp/final_side.png (Foto vs. Modell).

## Bogen-Ratsche: ARC_BW war der FALSCHE Knopf (wichtige Lehre)
- **Was:** Loop gebaut, der die Arkaden-Bögen ans Foto anpassen sollte (User: „bis die Bulgen gleich
  wie im Foto sind"). Erster Loop sweepte `ARC_BW` (bogen_breite_frac) → **alle Werte gaben IDENTISCHES
  Ergebnis**. Ursache: die lichte ÖFFNUNG wird von den PFEILERN bestimmt (`arcade_piers`, Teilung
  W/N_ARCH − Pfeilerbreite), NICHT von ARC_BW. `ARC_BW` skaliert nur den Gold-Ring (`arch_rings`,
  bw=pitch·ARC_BW). Man kann eine Öffnung nicht breiter machen, indem man am Ring dreht.
- **Messung (selbst hingeschaut + gemessen):** Foto-Arkade = 4 Öffnungen (Pfeiler x 0,24/0,51/0,77 +
  Ecken), Öffnung/Pitch ≈ 0,70. Modell = 4 Öffnungen, lichte Weite/Pitch ≈ 0,74–0,81. → **Bogenanzahl
  UND Öffnungsbreite stimmten bereits**. Die Bögen waren gar nicht zu schmal; mein buggy Loop hatte
  ARC_BW auf 0,70 gesenkt → Gold-Ring zu klein, schwebte frei in der Öffnung (sah „falsch" aus).
- **Fix:** `tools/bogen_ratsche.py` misst jetzt die lichte Weite/Pitch im Render an der Kämpfer-Zeile
  und setzt ARC_BW = diesen Wert (0,811) → die Gold-Archivolte RAHMT die Öffnung wie im Foto.
- **Lehre:** (1) Beim „Ratschen" ZUERST prüfen, ob der Parameter die Zielgröße überhaupt beeinflusst
  (identischer Score über den ganzen Sweep = Parameter wirkt nicht → falscher Knopf, kein Messproblem).
  (2) Die Öffnung ist eine Folge von Pfeilerbreite×Anzahl, nicht des Dekor-Rings. (3) Selbst hinschauen
  + zählen zeigte sofort: Bögen waren nie zu schmal — das Problem war nur der verrutschte Ring.
- **Belege:** /tmp/arcade_vergleich.png (Foto · vorher 0,70 · nachher 0,811).

## Ratsche + Kalibrier-Präzisionsgrenze (empirisch)
- Kalibriertool overlay_diff validiert (Selbst=0, Verschiebung monoton, Perspektive-Recovery 0.0001).
- Zwei Metriken getestet: Offenheit (verdeckungs-anfällig) + Kanten-Profil (textur/licht-robust).
- GROBE Strukturparameter: RIDGE-Sweep-Minimum EXAKT bei gemessen 15,41 m → Ratsche fängt grobe Fehler.
- FEINE Lagen: ~0,4-m-Boden, Tal flach (SILL-Min 5,70 statt 6,13; Gauben-Sweep = Rauschen).
- ARBEITSTEILUNG: Präzise Maße aus Direkt-Detektoren; overlay_diff für Grob-Validierung + Multiview.
  NICHT die Ratsche zum Sub-0,5-m-Feinschliff zwingen.

# Änderungsprotokoll — Kaufhaus Freiburg (Modell aus Fotos)

Jede Änderung mit **Was / Warum / Lehre**, damit nachvollziehbar ist, was wann korrigiert wurde.
Datei: `tools/kaufhaus_measured.py`. Belegfotos: `daten/kaufhaus_freiburg/fotos/`.

Reihenfolge = neueste zuerst.

---

## FEHLER-LOG (User-Funde, die ich automatisch hätte erkennen müssen) — Stand offen

Regel: bei JEDEM dieser Punkte NICHT den Generatorwert von Hand ändern, sondern DETEKTOR bauen,
der es aus dem Foto misst → JSON → Generator liest. Diese Liste = Lernmaterial.

1. **Fenster-Kopf: Mitte zu niedrig (sagt „durchhängen").** Echt: MITTE am höchsten (flacher hoher
   Mittelteil), Schultern konkav nach außen fallend. Meine Kontur hat Bumps bei ±0,2 (Pfostenlage)
   leicht ÜBER der Mitte → winziger Mitten-Dip. FIX-Weg: Kontur denoisen/glätten in `_load_profile`
   so dass Mitte Peak ist (automatisch, nicht Wert raten).
2. **Erker-Fenster „hoch und flach" — Form falsch.** Erker-Bucht-Fenster haben eigene Form (nicht
   die Fassaden-Vorhangbögen). Muss aus kh_erker ERKANNT werden (shape_extract/fenster_struktur auf
   den Erker-Crop), nicht hardcodiert.
3. **Erker ZU HOCH.** Höhe/Proportion der Bucht stimmt nicht → Erker-Maße aus Foto messen
   (foto_kanten_messen/shape_extract auf den Erker).
4. **Erker startet „über dem Dach".** Die vertikale LAGE des Erkers (wo Bucht/Helm relativ zu
   Traufe/Dach ansetzen) ist falsch → aus Foto messen (Erker-Unterkante, Bucht-Oberkante, Helm-Fuß).
5. **Balkon zu wenig AUSLADEND.** Echt kragt der Balkon viel weiter vor → Auskragung aus Schräg-/
   Seitenfoto messen (Tiefe), `balcony()`-Projektion danach.

6. **Erker-Fenster liefen bis zum BODEN.** Echt: Fenster NUR im oberen Teil, unten solide Schürze
   mit Wappen. FIX: `wh=(z1-z0)*0.48`, Fenster im oberen Teil (wz=z0+0.72·H), Wappen auf die Schürze
   darunter. *(behoben)*

**WARUM ich solche Fehler nicht automatisch merke (Kernproblem, User „ich drehe durch"):**
Meine Checks waren SCHMAL — `passform_check` vergleicht nur ein paar Element-HÖHEN (Statue, Traufe).
Es gab KEINEN Test, der JEDE Region Modell↔Foto vergleicht → un-getestete Stellen (Erker-Fenster-
Ausdehnung) rutschen durch, bis der User sie sieht. FIX: `tools/overlay_diff.py` — Render aufs Foto
normieren, im Raster die „Offenheit" (dunkel=Öffnung vs. hell=Wand) vergleichen, Abweichzellen
markieren → Fehler leuchten von selbst auf. v1 funktioniert, wird aber noch von Foto-Müll (Marktstände/
Leute in der Arkade) überlagert → muss maskiert werden (Arkaden-Boden/Menschen ausblenden), dann ist
es das verlässliche Auto-Netz.

Grundsatz (User, mehrfach, mit Nachdruck): „Ich will nicht manuell rumfuschen, du musst es
automatisch erkennen. Mach dir ganz viele Notizen über deine Fehler und lerne daraus."

---

## Runde 4 — Fenster: GLIEDERUNG ERKANNT statt hardcodiert (harte Regel: KEIN Hardcoding)

- **Fehler-Kette (selbst verschuldet):** Waben→Quadrate, Hexagone quollen aus der Fensterform,
  Fensterform zu schmal/hoch, nur 1 Pfosten statt 2, Kämpfer fehlten. Ursache: ich habe die
  Fenster-Gliederung nach Gefühl hardcodiert statt sie zu MESSEN.
- **Lösung (messgetrieben, kein Hardcoding):**
  - `tools/fenster_struktur.py` — erkennt am Foto die goldenen Stege: VERTIKALE Pfosten (Anzahl +
    x-Lagen), HORIZONTALE Kämpfer (Anzahl + z-Lagen), Waben-Zellgröße (FFT der Bleistege).
    Schreibt `modelle/kaufhaus_freiburg/win_struct.json`. Erkannt: **2 Pfosten (±0,167), 1 Kämpfer
    (Mitte), Hex R≈0,067·Breite**.
  - `tools/shape_extract.py` — Fenster-UMRISS (Vorhangbogen, Doppel-Hump) → `win_profile.json`;
    gemessenes Seitenverhältnis **w/h=0,92** (Fenster ist BREIT, war viel zu schmal 0,56).
  - Generator `kaufhaus_measured.py`: `_load_winstruct()` lädt win_struct.json → `window_goldframe`
    setzt Pfosten+Kämpfer an die ERKANNTEN Lagen, `window_muntins` nimmt die erkannte Hex-Größe.
    Fenster-HÖHE aus Seitenverhältnis 0,92 statt der zu hohen Sturz-Kante (HEAD 9,18→8,52).
  - Waben jetzt echte Flat-Top-Hexagone, auf die Fensterform GEKLIPPT (`glass.contains(seg)`) →
    keine Hexagone außerhalb des Glases.
- **Lehre:** JEDE Stückzahl/Gliederung (Pfosten, Kämpfer, Waben) kommt aus Foto-Erkennung in eine
  JSON, der Generator liest sie. Nichts hardcoden — auch nicht „nur dieser eine Pfosten".
- **Automatischer Lage-Check:** `tools/passform_check.py` vergleicht Element-HÖHEN Render↔Foto
  (fing die zu hohe Giebel-Fiale 18,2 m → gekappt auf ~16,3).

---

## Runde 3 (messgetrieben: Breite, Statuen, Balkon, Tiefenmessung angefangen)

- **Zu breit** → Foto-Verhältnis gemessen (grid): B/H ≈ 1,25 (First→Boden); Modell war 1,47.
  `W` 23 → **18,5 m** (D 12,5→11,0). Passt.
- **Statuen gingen zu weit runter** → Statuen-Spalte am Foto vermessen (Fenster SILL/HEAD als Maßstab):
  Füße ~**6,9 m**, Kopf ~**8,3 m**, Figur ~1,4 m, Konsole bis ~6,35 m, Brüstung-OK ~6,1 m.
  `STAT_Z = SILL+0,47`, Figur KOMPAKT (war zu hoch+Robe zu lang), Konsole kürzer, `BAL_Z1`→6,1.
- **Zu wenige Baluster** → Teilung am Foto gemessen (~0,28 m) → `nb = Breite/0,28` (~64 schlanke
  Baluster statt 34 dicke).
- **Balkon-Schrott** → große Gold-Wappenmünzen aus der Brüstung ENTFERNT (verdeckten die Baluster);
  Baluster als echte Drechselform (Fuß→Bauch→Hals→Kapitell). Wappen sitzen an den Erkern (Foto).
- **Erker**: Bucht schmaler+höher (w 3,0→2,5), Fenster höher (Glas dominiert, dunkle Bleiruten).
- **MULTIVIEW-TIEFE (angefangen):** `tools/tiefe_messen.py` — Canny+Hough → Fluchtpunkte per RANSAC.
  Findet den Fassaden-VP korrekt (kh_front2025b). Für echte Tiefe braucht es eine Ansicht mit
  klarer SEITENfläche (kh_nr1/2) → Rektifizierung beider Flächen über die gemeinsame Höhe = nächster Schritt.

---

## Runde 2 (Erker/Statuen/Balkon „richtig machen" + Methode MESSEN)

### M. Methode: ERST MESSEN statt platzieren-und-korrigieren
- **Was:** `tools/fassade_vermessen.py` — segmentiert die Fassade, misst die WAAGRECHTEN Kanten
  (Höhen-Bänder) aus dem Zeilenprofil der Öffnungs-Dichte und zählt/vermisst die SENKRECHTEN
  Teilungen (Arkadenbögen, Fensterband) → JSON + Overlay.
- **Warum (User):** „Du musst doch alle Kanten erkennen, Abstände messen und dann entscheiden,
  welche Objekte du reinsetzt." Ich hatte Bauteile nach Impression gesetzt → O(n) Korrekturen.
- **Lehre:** Lage/Anzahl/Band-Höhen aus dem Foto MESSEN, nicht raten. Messung + Grundwahrheit
  abgleichen (Tool fand 5 Arkaden-Öffnungen, Grundwahrheit 4 = zentraler Durchgang mitgezählt).
- **Grenze (ehrlich):** aus EINEM Frontfoto ist nur die 2D-Fassade messbar, NICHT die Tiefe/der
  Auskragung (Erker-Überstand) — dafür brauche ich Schräg-/Seitenfoto oder Maße.

### O1. Erker saßen zu weit INNEN
- **Was:** `ORIEL_X [0.065W,0.935W] → [0, W]` — Erkermitte = Gebäudeecke, halbe Bucht kragt über die
  Hausflucht hinaus.
- **Warum:** Foto: Erker sitzen AUSSEN am Eck und ragen übers Haus; bei mir war Wand/Giebel daneben.
- **Lehre:** Eck-Erker = an die Ecke, mit Auskragung — nicht nach innen versetzen.

### O2. Erker-Helm = runder gerader Kegel → OKTOGONAL + durchgeschwungen
- **Was:** Helm-Kern `_revolve(sections=8)` (8-eckig) + 8 Gold-Grat-Rippen, höher/schlanker
  (chh 3.9→4.7, cr0 0.42w→0.38w), konkaves Glockenprofil. Diamant-Glasur 4-farbig.
- **Lehre:** Helmform = 8-eckig facettiert mit Gratrippen, nicht rund; Silhouette konkav.

### O3. Erker-Fenster zu golden/falsch
- **Was:** 1 schlanker Gold-Mittelpfosten (2 Lichter statt 3), schlanke Jamben, 1 Transom,
  Bleiruten DUNKEL statt gold (sonst Goldgitter), großes buntes Wappen-Rundschild darunter.

### O4. Statuen höher angesetzt (vorher „zu weit runter"); Balkon
- **Was:** Balustrade jetzt ROTER Sandstein (galerie-Farbe gold→rot), 42 schlanke Baluster statt
  30 dicke Perlen; Blendarkaden-Fries raus; Wappen zwischen die Fenster.
- **Lehre:** Brüstungsfarbe am Foto prüfen (rot, nicht gold); Baluster schlank.

### O5. Seitlicher Durchgang: Bogen VORNE + Seitenfenster
- **Was:** `side_walls()` — 1 Rundbogen bei Y≈1,9 (vorne, Eck-Durchgang) statt mittig; 2 Fenster
  im oberen Band mit dunklen Scheiben (`seitenglas`).
- **Lehre:** Durchgang gehört an die Front-Ecke (Durchgang), nicht in die Seitenmitte; Seite hat Fenster.

---

## Runde: vom User gemeldete Fehler (alle, die ich selbst hätte sehen müssen)

### 1. Dach-Seiten waren grün statt rot
- **Was:** Dach von Walmdach (grüne Seitenflächen) auf **Satteldach mit roten Giebel-Endwänden**
  umgestellt. `ROOF_INSET 1.8→0`, neue `gables()` (rote Dreiecke x=0 und x=W), rote Stufenkante
  (`dach_krabben`) läuft auf der Giebelschräge.
- **Warum:** Foto (kh_jm3289, kh_erker) zeigt an den Seiten **rote Giebel** mit roter Stufen-Coping,
  keinen grünen Walm.
- **Lehre:** Dachtyp (Walm vs. Giebel) zuerst am Foto klären — er bestimmt, ob die Seite grün oder rot ist.

### 2. Statuen gingen zu weit nach unten
- **Was:** Figuren-Fußpunkt `STAT_Z 6.3→7.05` angehoben, Figur gekürzt (Robe 1.95→1.3 m),
  Konsolen/Nische/Krone mitgezogen.
- **Warum:** Beim vorherigen Fix gegen „zu gestaucht" hatte ich sie nach UNTEN verlängert statt
  höher anzusetzen → Füße reichten bis zur Brüstung. Foto: Füße im oberen Fensterband.
- **Lehre:** Bei Figuren IMMER die Fuß-Linie UND die Kopf-Linie gegen das Foto prüfen, nicht nur die Höhe.

### 3. Erker-Fenster völlig falsch
- **Was:** Statt dunkler Kästen jetzt **facettengerechte Bleiglas-Bucht-Fenster**: Gold-Mittelpfosten
  (3 Lichter), Querkämpfer, flacher Gold-Sturz, Sohlbank, Bleiruten; bunte Wappen-Rundschilde darunter.
  Je Facette zur Facettennormalen gedreht.
- **Warum:** Foto kh_erker zeigt hohe, gegliederte Bleiglasfenster mit Goldmaßwerk.
- **Lehre:** Für den Erker gibt es ein EIGENES Detailfoto (kh_erker) — das hätte ich zoomen müssen.

### 4. Erker-Helm war gerader Kegel statt durchgeschwungen
- **Was:** Helm von geradem `tcone` auf **konkaves Glockenprofil** (Rotationskörper `_revolve`,
  Profil `cr0*(1-t)^1.5`, Glockenfuß flares aus) umgebaut; Diamant-Glasur folgt der konkaven Silhouette.
- **Warum:** Foto: der Helm ist „durchgeschwungen" (konkav/Glockenhelm), nicht gerade.
- **Lehre:** Bei gekrümmten Bauteilen die SILHOUETTE/Profilkurve gegen das Foto legen, nicht nur „Kegel ✓".

### 5. Seitlicher Unterdurchgang fehlte
- **Was:** `side_walls()` — Seitenwände bekommen **einen** Rundbogen (Unterdurchgang) wie die Arkade.
  (Zuerst 2 gebaut → User: nur 1 → `nside=2→1`.)
- **Warum:** User/Foto: die Arkade läuft seitlich als Durchgang weiter.
- **Lehre:** Anzahl immer bestätigen lassen (erst 2 geraten, korrekt ist 1).

### 6. Goldener Balken war ein dicker Strich statt zwei feiner
- **Was:** `cornice()` von einem 0,5 m dicken Gold-Balken auf **zwei schmale Gold-Profile mit Spalt** geändert.
- **Warum:** Foto: das Traufgesims sind zwei feine Linien.
- **Lehre:** Horizontale Zierbänder auf Einzel- vs. Doppelprofil prüfen (Linienzahl zählen).

### 7. Balkon war „völliger Schrott"
- **Was:** Balkonzone neu: `gallery()` = nur zwei Gold-Leisten (Blendarkaden-Fries mit 26 Mini-Bögen
  ENTFERNT); `attic_railing()` = 30 kräftige Baluster (statt 56 dünne Stäbchen); `balcony()` saubere
  Platte+Konsolen; Wappen-Rundschilde auf die Brüstung zwischen die Fenster gesetzt (vorher über den Bögen).
- **Warum:** Drei Elemente (Fries + Baluster + Wappen) überlagerten sich wuselig; Foto zeigt klare Brüstung.
- **Lehre:** Zonen nicht mit drei konkurrierenden Mustern überladen — ein klares Hauptmotiv je Zone.

---

## Vorherige Runde (autonom, vor den User-Korrekturen)
- Statuen schlank statt stämmig; Arkade als Laubengang mit Tiefe (Rückwand schattiert statt schwarz);
  Gauben-Anzahl 3-unten/2-oben; Rauten-Glasurmuster vergröbert; 4-farbige Helm-Glasur.
  (Details siehe git-Diff; mehrere davon musste der User nachbessern — siehe oben.)

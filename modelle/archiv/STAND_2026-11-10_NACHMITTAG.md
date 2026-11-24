# Stand 10.11.2026 nachmittags (13:45) - Uebergabe vor /clear

Nach /clear ZUERST diese Datei lesen. Davor: `bash tools/hpwmi_pruefen.sh` (Sitzungsbeginn-Regel).
Anrede "mein grosser Meister", Deutsch. Vorgaenger: `modelle/STAND_2026-11-10_MORGEN.md`.

## 0. Nachtrag 13:50 (nach /clear erledigt)
- main-Abnahme Wiederholung GRUEN (d3913151), Ost-Text der masstabelle mitcommittet. Wiederkehrend, nicht blockierend: `freiraum_audit`
  scheitert in JEDER main-Abnahme an fehlender `messprotokoll/SFM-AUSRICHTUNG-buendel.json` (offen, nicht angefasst).
- Regler-Regel gebaut (23790212): keine Formliste-Auffrischung solange gpu_tor.lock belegt/ansteht, main-Abnahme laeuft oder eine Spur
  nach OOM wartet; laufende Auffrischung wird bei OOM-Wartezeit angehalten. Regression identisch. Regler neu gestartet.
  Folge: bei 8 Spuren laeuft die Auffrischung praktisch nie (Sperre fast immer belegt) - gewollt, Spuren messen "vorher" selbst.
- Fotoplan-Handyseite fertig (c75ebb9f): https://claude.ai/artifact/TcMmbri9m7o6FadDuRUHt6
  (`tools/luecken_seite_bauen.py <foto_luecken_dir> <aus.html> --titel ...`). Offen: Standpunkte 12/14 liegen im Plan am Nordrand
  zwischen Waenden (Gasse?) - vor Ort pruefen. foto_luecken.py selbst weiter uncommittet (Test braucht freie GPU).
- NICHTS_GEBRACHT BT-LUECKEN eingetragen (13c3d3e7).
- freiraum_audit-Ursache: objekt.json "freiraum.ausrichtung" zeigt auf eine Datei, die es nur in modelle/kaufhaus_grob gibt (alter
  LoD2-/null4-Rahmen, nicht lot2). NICHT kopieren (falscher Rahmen = stiller Fehler). Richtig: dicht_alle (kaufhaus_null4) per ICP in lot2
  ausrichten, neue SFM-AUSRICHTUNG fuer grob3 schreiben - GPU, erst wenn Tore frei. Kein Sollwert haengt daran.
- Realitaetszahl (Nutzerwunsch): tools/realitaet_prozent.py, automatisch nach jeder gruenen main-Abnahme (054afdfb). Basis 14:01: 79,0 %
  (Fotokanten 69,5 %, 11/23 Teile >= 0,9). Nach JEDEM Ergebnis dem Nutzer die Zahl + Differenz nennen.
- 14:09 Westgiebel R1 verworfen (Beleg 0,238 -> 0,217, Foto-F1 0,413 -> 0,394): datenbegrenzt, neue Westfotos noetig.

## 1. Was jetzt laeuft (systemd, `systemctl --user list-units 'rcpark-*'`)
- `rcpark-kreis_regler` (`--gpu_ziel 85 --max 8`, neu gestartet 13:37): startet Spuren selbst. KEINE Bauteil-Agenten von Hand starten.
- Spuren: a103253 (r2 figuren), a111556 (staffelgiebel__west), a112030 (fensterreihe_og), a112930 (balkonband),
  a112330, a112630, a115833, a120333. Um 13:40 hingen 4 davon im "OOM im Torschritt ... warte 300 s"
  (alter Spurcode, feste 300 s; neuer Code pollt freien VRAM - wirkt erst fuer neue Runden).
- Ursache der OOM-Staus: meine Nebenjobs (ff_giebel, Formliste-Auffrischung `rcpark-fotoform`) + Agenten-Testlaeufe.
  Gestoppt: `rcpark-ff_giebel`, `rcpark-fotoform` (13:43 nochmals, der Regler hatte es 13:36:42 wieder gestartet; setzt
  spaeter aus der `.teil`-Datei fort). Danach VRAM 1,9 GB belegt.
- `rcpark-abnahme_main`: Wiederholung "Nutzer-Sichtfund Staffelgiebel/Bruestung (Wiederholung, OOM-fest)". Ergebnis in
  `/media/oem/scan/rc-park_kreis/abnahme_main.log` (JOB_ENDE / MAIN_ABNAHME). Pruefen: gruen? Und ob die Erweiterung des
  Ost-Textes in `masstabelle.json` (beobachtungen_offen staffelgiebel__ost, Nutzerbestaetigung 13:25) mitcommittet wurde.
- `rcpark-commons_dl` (Datenluecken-Agent): laedt 65 freie Commons-Kandidaten, 1 Bild/min, nach
  `/media/oem/scan/rc-park_daten/kaufhaus_alle/online_luecken/commons/orig/` (herkunft.json cm_00..cm_64). Neustart ueberspringt Vorhandenes.

## 2. Sofort zu tun (Reihenfolge)
1. Torergebnisse der 4 haengenden Spuren abwarten (`grep -E "ANGENOMMEN|VERWORFEN" /media/oem/scan/rc-park_kreis/kreis_a1*.log`).
   Bei jeder Annahme: Pruefer-Fehlerliste lesen, main-Abnahme gruen, dann Viewer neu (Abschnitt 5) + Artifact
   https://claude.ai/artifact/9mpGqmnVR3bBqUYnh6jXyQ aktualisieren, Nutzer melden.
2. **Regler-Regel bauen (versprochen):** Solange eine Spur im Torschritt wartet (gpu_tor.lock belegt / "OOM im Torschritt" /
   "Warten" im Log), startet der Regler KEINE Nebenjobs (Formliste-Auffrischung usw.). Bisher nur: Auffrischung nur bei VRAM < 3000 MiB
   belegt (Commit 72a90ad9) - reicht nicht, Auffrischung belegt danach selbst 2,3 GB. Danach `tools/regression.py modelle/kaufhaus_grob3/objekt.json --pruefen`.
3. Keine eigenen GPU-Jobs starten, solange Tore warten.

## 3. Heute gebaut (committet)
- Effizienz ohne Qualitaetsverlust (Regression 2x identisch, Bitgleich-Tests): gemeinsamer vorher-Speicher je Schluessel
  (`KREISDIR/OBJ/vorher_speicher`), vorher-Formwert aus Formliste bei gleichem STL-sha, `sh_cpu` (Generator ausserhalb GPU-Sperre),
  Abnahme geteilt (Generator CPU / Pruefen unter Sperre / Export wiederverwendet), OOM-Wiederholung in teil_fotoform (+Fortsetzen),
  render_kern adaptiver Rasterblock (`tools/test_raster_block.py`), `tools/gpu_slot.py` rechnerweite GPU-Schlange (3 Plaetze,
  >= 1500 MiB frei; `tools/test_gpu_slot.py`), eingehaengt in foto_diff, fehlteile_finden, foto_breitenprofil, pruefstand, konvergenz_bericht,
  teil_fotoform, modell_fotofarbe. main_abnahme.sh OOM-fest.
  Messung Durchsatz: 1 parallel 66-70 s, 2 parallel 79 s, 3 parallel 400 s statt 200 s -> parallel nur bis zur VRAM-Grenze.
  Lehren L-KR27..L-KR30 in `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md`.
- Viewer (`tools/viewer_kanten_bauen.py` + `viewer_kanten_vorlage.html`): passendes Foto zur Ansicht (Uebersichtsfotos bevorzugt),
  "Ansicht wie Foto", Handy-Layout (Foto unter Modell, 50vh/30vh), Modell in echten Fotofarben (`tools/modell_fotofarbe.py`, 59,8 % gefaerbt).
  Groesse 10 MB (`--foto_px 380 --foto_q 68 --n_fotos 70`).
- Nutzer-Sichtfunde als Beobachtungen in masstabelle (382a4e41): staffelgiebel__ost versetzt/zu hoch, Helm breiter;
  bruestung__balkon ~22 dicke ovale Staebe statt dichter Reihe schlanker Docken (Anzahl per foto_zaehlung!).

## 4. Gebaut, NICHT committet (untracked)
- `tools/foto_luecken.py` + `tools/test_foto_luecken.py` (Sonnet-Agent): Abdeckung je Flaeche + 17 Standpunkte mit lat/lon,
  Kompass, Zoom, Format. Ausgabe `/media/oem/scan/rc-park_daten/kaufhaus_grob3/foto_luecken/` (foto_luecken.json, luecken_3d.json,
  georef.json, standpunkt_1..17.jpg; LoD2-Variante `foto_luecken_lod2/`). Bilanz: gut 1109, mittel 868, fehlt 1352 von 3330 m²;
  vom Boden erreichbar 466 m², nur erhoeht 1755 m². Georef IoU 0,63, Umriss median 1,07 m.
  TODO: Test bei freier GPU neu laufen lassen (`/media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_foto_luecken.py`), dann committen;
  `foto_luecken.py 1500` in `tools/gpu_budget.txt` + `tools/gpu_werkzeuge.txt`; in `nullstart.py` nach kamera_lod2/wolke_seiten einhaengen
  (`--flaeche auto --wolke ... --daten ...`).
- `tools/luecken_seite_bauen.py` (von mir, eben geschrieben, NIE gelaufen): baut Handy-Seite aus dem foto_luecken-Ordner.
  FEHLT noch: `tools/luecken_seite_vorlage.html` (Platzhalter `__TITEL__` und `/*DATA*/`). Annahmen im Skript pruefen:
  georef.json-Schluessel `theta_grad`, `t`, `xhat_utm`, `yhat_utm`, `mitte_utm` (gegen echte Datei abgleichen!), luecken_3d `klasse` je Dreieck.
  Seite soll: nordorientierter SVG-Plan (Waende Ampelfarbe), nummerierte Standpunkte mit Blickkeil, Vorschaubild je Standpunkt,
  Kompass/Neigung/Zoom/Hoch-Quer/Anzahl Fotos/Bauteile, Google-Maps-Link `https://www.google.com/maps?q=lat,lon`,
  Abhakliste in localStorage (try/catch), `navigator.geolocation` versuchen mit Rueckfall (es gibt KEINE geolocation-Capability),
  ehrlicher Hinweis "Lage auf wenige Meter genau". Dann als Artifact veroeffentlichen (vorher artifact-design laden).
- `tools/teil_ansichten.py` (Datenluecken-Agent, nie durchgelaufen, OOM): gute Ansichten je Teil, fehlende Richtungen (45-Grad-Sektoren + Kompass).
  Aufruf im Agentenbericht: `--teile_dir /media/oem/scan/rc-park_kreis/kaufhaus_grob3/cp_test_teile --kameras <sfm>/kam_lot2.json,kam_lot2_dach.json,kam_lot2_video.json
  --georef .../foto_luecken/georef.json --aus <out.json>`; JOB_GPU_MB=800, ~10 min.
- `tools/aufraeumen_2026-11-10.sh`: Loeschskript fuer den Nutzer (nur er fuehrt es aus).

## 5. Viewer neu bauen (nach jeder angenommenen Runde)
```
S=/tmp/claude-29999/-home-oem-git-rc-park/a5fbd00e-fb5b-4dd4-9599-06bcd6fe5384/scratchpad   # bisheriger Scratchpad; nach /clear ggf. neuer -> main_m.stl neu erzeugen
D=/media/oem/scan/rc-park_daten/kaufhaus_alle
# main_m.stl = modelle/stl/kaufhaus_grob3_1-87.stl * 0.087 (trimesh) -> $S/main_m.stl
JOB_GPU_MB=1500 tools/job_start.sh fotofarbe LOG /media/oem/scan/venv-seg/bin/python -I tools/modell_fotofarbe.py $S/main_m.stl $D/sfm/kam_lot2.json $D/bilder $D/modell_fotofarbe.npz
/media/oem/scan/venv-seg/bin/python -I tools/viewer_kanten_bauen.py $S/kaufhaus_r6.html --seg $D/segmente_gitter_v12.json --kp $D/kette_video_alle/konsens_B.npy \
  --n 180000 --koerper $S/main_m.stl --objekt kaufhaus_grob3 --fotos $D/sfm/kam_lot2.json --bilder $D/bilder --n_fotos 70 --foto_px 380 --foto_q 68 \
  --modell_farbe $D/modell_fotofarbe.npz
```
Kameras kam_lot2 liegen im gleichen Rahmen wie main_m.stl (geprueft per Kantenueberlagerung handy_03). Kopfloser Test:
`firefox --headless --no-remote --profile $S/ffprof --window-size=412,860 --screenshot ...`. Letzte Fassung V41.
Offen (optional): falsche Nachbarfarben an Seitenwaenden (Farbe nur, wenn Wolken-/Fototiefe zur Modellflaeche passt).

## 6. Konvergenzstand main (STL 41ffd33)
Mittel wolkenbeleg 0,769; 10/23 Teile >= 0,9; Pruefstand 119/120. Schwach: staffelgiebel__west 0,185, quader__rumpf_og 0,384,
gaubenreihe__unten 0,411, quader__rumpf_eg 0,51, quader__laube_rueck 0,565, staffelgiebel__ost 0,653.
Schaetzung dem Nutzer genannt: 6 schwache Teile behoben -> ~89 %, 10-12 h; Westgiebel/Rueckseite datenbegrenzt (neue Fotos noetig).

## 7. Datenluecken-Agent (ac167539c15fb5b17), Zwischenbericht
65 freie Commons-Kandidaten (CC BY/BY-SA/PD, >= 1500x1100), Abgleich gegen alte Manifeste unvollstaendig. Mapillary bewusst nicht
(CC BY-NC-SA, Verkauf). Nichts registriert, Wirkung nicht gemessen. Erwartung gering (frueher zeigten freie Fotos fast nur die Ostfassade).
Plan: teil_ansichten -> gezielte Suche -> Registrierung NUR auf Kopie (`sfm/kam_lot2_online_luecken.json`) mit Overlay-Tor
(Reproj < 2 px ist blind fuer Lage, od_04). NICHTS_GEBRACHT-Zeile vorgeschlagen: "BT-LUECKEN (10.11.) ... Registrierung/Wirkung offen" - eintragen.
Vor Ort wahrscheinlich noetig: Gaessle/Rueckseite (West/Hof), Dach erhoeht (Drohne?), Obergeschosse ohne Bodensicht.

## 8. Lehren heute
- Nebenjobs auf der GPU verstopfen die Tore -> Tore haben Vorrang (Regel in den Regler, Punkt 2.2).
- Parallel ueber die VRAM-Grenze ist insgesamt LANGSAMER (Messung oben).
- Laufende Spuren nutzen alten Worktree-Code: Werkzeugverbesserungen wirken erst in neuen Runden.
- JS-Zeilenkommentar `//` in einzeilig zusammengesetztem Vorlagencode verschluckt den Rest -> nur `/* */`.
- Hotel-Admin-/Verwaltungsplan-Anfrage war falsches Projekt - ignorieren.

## Feste Regeln (unveraendert)
Loeschen nur per Nutzerskript; kein Druck/Slicen ohne Wort; `/tmp/iph` nicht anfassen; Datenplatte > 10,5 GB (jetzt 18 G),
Root > 6 GB (jetzt 7,6 G); Commits mit Attributionszeilen; lange Jobs nur `tools/job_start.sh`; Zaehlmerkmale nur am Foto.

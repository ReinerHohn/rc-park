# RC-Park – Arbeitsregeln (gelten für jede Sitzung, jedes Objekt)

## Modell-Abnahme (Pflicht; Rahmen: `modelle/METHODE_MASSTABELLE.md`)
Je Objekt `modelle/<objekt>/objekt.json` + `masstabelle.json` (Masse = Daten mit Quelle/Quelltyp/Merkmal, nicht Code).
1. Nach JEDER Generatoraenderung: `tools/bauen_abnehmen.sh <objekt>` (baut + `tools/pruefstand.py`). Martinstor: `tools/bauen_abnehmen.sh martinstor`.
   Nur bei "alle Pruefungen bestanden" weiter (Viewer, Commit, H0, Fertigung). Sollwerte nie lockern, um Gruen zu bekommen; nur mit neuer Quelle (+ `historie`).
2. **Sichtbeobachtung** (Nutzer oder eigene: "zu gedrungen", "stimmt nicht") = Testauftrag: SOFORT als `beobachtungen_offen` in die Masstabelle,
   DANN messen (Vollbild/Dokument/Laser passend zum Merkmal) und als Pruefung eintragen, die am aktuellen Modell FEHLSCHLAEGT, DANN Generator aendern.
3. Nach jedem Bau das Sichtblatt `modelle/<objekt>/audit/seiten.jpg` ANSEHEN (alle Seiten, nicht nur die fotografierte) und bei Bedarf
   `tools/foto_render_seite.py` / `tools/foto_profil_gpu.py`. Zahlen allein (IoU ohne Blick auf den ROI) gelten nicht.
3b. Jedes neue Generator-Element bekommt `beleg(seite, element, quelle)`; ohne Quelle faellt der Pruefstand durch. Annahmen heissen `ANNAHME: ...`.
3c. Fotomasse nur ueber `tools/foto_mass.py` (Messprotokoll M-<foto>-<nr>), Tabellenzeile mit `protokoll` und `massstab`; Massstab aus dem Modell = zirkulaer.
    `modelle/<objekt>/MASSNACHWEIS.md` ist der automatische Nachweis - nicht von Hand schreiben. Neues Objekt: `tools/objekt_anlegen.py`.
3e. Nach jedem Bau mit kalibrierter Kamera `tools/fehlteile_finden.py <objekt> <foto>` laufen lassen und die Treffer ansehen (fehlende/erfundene Teile),
    bevor der Nutzer sie findet. Nutzer-Sichtfunde zuerst als automatischen Test nachbauen, dann einbauen.
3f. **Kontur-Diff Modell gegen Foto**: `tools/foto_diff.py <objekt> <foto>` (rot = Modellkante ohne Fotokante: falsche/erfundene Form, gelb = Fotokante fehlt im Modell). Nach jedem Bau fuer die kalibrierten Fotos laufen lassen und `audit/foto_diff_<foto>.jpg` ansehen; Treffer ausserhalb der Ankerzone sind unsicher. (Register CC; Schwellen noch nicht als Pruefstand-Sollwert.)
3d. Echte Meter aus Fotos nur ueber amtliche Anker (`anker3d.json` aus LoD2/DOM1/DGM1): `foto_kalibrieren.py` -> **`foto_pick_pruefen.py` ansehen** ->
    `foto_bundle.py` -> `foto_mass.py --kamera`. Fotos ohne Bodenanker nur mit EXIF-Brennweite oder `f_gruppe`. Georeferenz jeder Nebendatei pruefen.
4. Quellen-Blindheit (vom Pruefstand erzwungen, Exit 2): Laser DOM1 sieht keine Bauteile < ~3 m, keine Nadeln, keine Fassade, keine absolute Spitzenhoehe, keinen Fussabdruck steiler Helmflaechen (> ~75 Grad: Zellzahl/Schnitt Faktor 2 zu klein, Register AR);
   LoD2 keine Aufbauten; Fotos keine absoluten Masse ohne Massstab; Dokumente keine Form.
5. Widersprueche zwischen Quellen (Foto vs Laser) NICHT mitteln - als offene Beobachtung stehen lassen, naechsten Schritt notieren.
6. Optimierer-/Mehrfachstart-Ergebnisse je Parameter bewerten; neue sichtbare Merkmale als Parameter + Tabellenzeile.
7. Symmetrische Objekte: Seiten unterscheidbar machen (Fotos nach Seite in `objekt.json`), sonst ist jede Kameraanpassung mehrdeutig.
8b. Werkzeug-/Bibliotheksaenderung (tools/*.py, bauteile.py, pruefstand.py): danach `tools/regression.py modelle/<objekt>/objekt.json --pruefen` (Kette + 10 Ergebnisdateien gegen Schnappschuss; Register AW). Schnappschuss (`--schnappschuss`) nur erneuern, wenn das Ergebnis sich AENDERN soll, mit Register-Eintrag.
9. **Zaehl-/Strukturmerkmale (Anzahl Oeffnungen/Fenster/Zinnen je Flaeche) NUR am Foto zaehlen** (`tools/foto_zaehlung.py` -> messprotokoll/Z-*.json mit markiertem Bild), nie aus Punktwolke/Laser/LoD2 und nie aus Dateien, die der Generator selbst liest (Selbstbezug).
   Merkmal-Etikett ehrlich setzen (Zaehlart -> `anzahl`/`fassade`); der Pruefstand lehnt Umgehung und Selbstbezug ab (Exit 2), `tools/test_regeln_cb.py` beweist das bei jedem Bau. Zahl aus Wolke/Median = nie Sollwert (Register CB).
9b. **Vor jedem Druck/Zeigen eines Bauteils**: Teil neben das Referenzfoto legen (Detailrender des Teils ansehen), Anzahl/Anordnung der Elemente pro Flaeche mit dem Foto vergleichen - nicht nur Slicer-Bericht und Pruefstand-Zahlen.
9c. **Lage-Regel (Nutzer 8.11., Erker/Helme)**: (a) Parametergrenzen MUESSEN groesser sein als der erwartete Fehler (Helme: Fehler >1 m, Grenze +-0,5 m = Fit konnte nie ankommen); Fit auf Grenze = Grenze erweitern, nicht aufgeben.
    (b) Gruppen mit mehreren Gegenstuecken (links/rechts) in EIN Teil je Gegenstueck trennen, sonst gemeinsame Verschiebung.
    (c) Vor jedem Zeigen: `tools/teile_lage_pruefen.py <objekt>` (Median je Bauteil gegen Wolke, Markierung > 0,4 m) UND Render von vorn/Seite/schraeg ansehen; nie ein Bauteil ersatzlos abschalten (p18-Fehler, BS140).
    (d) Statt nur lokaler CMA-ES-Suche: globale Formsuche (3D-Template-Matching per FFT-Kreuzkorrelation im Voxelgitter / Hough) fuer Helme, Fenster, Figuren - Status: GPU-Positions-Sweep gebaut (`tools/teil_sweep_gpu.py`, `sweep_alle.py`, Methode `modelle/METHODE_GPU_SWEEP.md`): Beweistest `--synth` Pflicht, Plateaubreite je Achse; Template-Matching/FFT fuer Form weiter offen.
9d. **Fit-Ziel immer Wolke UND Fotos (Nutzer 8.11., Gauben 'Sprungschanze' nie bemerkt)**: Die Wolke legt nur LAGE/Hoehe fest, die FORM (Dachart, Bogen, Fensterteilung, Anzahl) kommt aus den Fotos. Vor und nach jedem Fit eines neuen/veraenderten Bauteils:
    (a) Teil gegen mindestens 3 Fotos aus verschiedenen Richtungen ansehen (Detailrender neben Fotoausschnitt, Regel 9b) und Formfamilie festlegen, DANN Maße fitten;
    (b) Zielfunktion = Wolkenabstand + Foto-Kantenabstand (Modellkanten in kalibrierte Fotos projiziert, `tools/foto_diff.py`-Logik) - Ziel: `param_wolke_fit.py --fotos`, Kameras aus dem gemeinsamen SfM (`kaufhaus_alle/sfm`, per ICP in den Netzrahmen gelegt). Status: noch NICHT gebaut.
9e. **Fotokanten entscheiden (Nutzerregel 10./11.11.)**: Form, Masse und jedes Annahme-Tor (Kreis, auch neue Teile) richten sich nach den FOTOKANTEN (Foto-F1 `tools/teil_fotoform.py`);
    Wolke/Kantengitter/LoD2 nur Lage-Veto bzw. Gegenprobe. Leere Wolke ist kein Datenmangel, solange das Merkmal in >= 3 Fotos zu sehen ist (vorher Fotos je Teil zaehlen).
8. Commit-Sperre: `tools/git_hooks/pre-commit` prueft ueberwachte Dateien. Aktivierung nur durch den Nutzer: `git config core.hooksPath tools/git_hooks`.

## Vor neuen Versuchen lesen
- **Bauteil neu/falsch → Agentenauftrag immer aus `modelle/VORLAGE_BAUTEIL_RUNDE.md`** (Stufe 0 Formbeschreibung aus >=3 Fotos vor jeder Messung, feste Berichtform; Nutzerwunsch 9.11.)
- `modelle/NICHTS_GEBRACHT.md` (Kurzindex der Sackgassen Kaufhaus Wolke->Netz, 1 Zeile je Versuch; zuerst ansehen, neue Fehlschlaege SOFORT eintragen)
- `modelle/VERSUCHSREGISTER_MARTINSTOR.md` (was schon probiert wurde, Fehlschlaege, Ursachenanalyse I, Dach/Spitze J-J5, Seiten K)
- `modelle/LIZENZ_WERKZEUGE.md` (Verkauf geplant: NC-Werkzeuge nur zum Testen, eintragen)
- `modelle/LERNJOURNAL_MARTINSTOR.md`, `modelle/PIPELINE_H0.md`, `modelle/PROTOKOLL_VALIDATOR.md` (Fehler-Log F1-F10)

## Technik
- **Sitzungsbeginn / nach Neustart / nach Kernel-Update: `bash tools/hpwmi_pruefen.sh` laufen lassen** (Nutzerwunsch 6.11.). Das selbstgebaute hp-wmi-Modul (Board 8C77, Profil `performance` = CPU 55 W statt ~38 W) gilt nur fuer EINEN Kernel und verschwindet beim Kernel-Update. Meldet das Skript `ACHTUNG KERNEL-MODUL`, dem Nutzer SOFORT sagen (bauen/signieren/laden = sudo durch ihn); meldet es `HINWEIS ... kennt das Board 8C77 schon`, ist eine Mainline-Version da und das Eigenbau-Modul kann weg. Details `modelle/CPU_LEISTUNG.md` Abschnitt 6.
- Neuer/anderer Rechner: `EINRICHTUNG_RECHNER.md` abarbeiten (Luefterregler-Dienst, Datenplatte, venvs, Mapillary-Token, GPU-Regeln).
- Grosse Daten (Fotos, Foto-Eingang, SfM-Netze, Wolken, Caches, Nullstart-Objekte) NIE auf der Root-Platte: immer unter `/media/oem/scan/rc-park_daten/<objekt>/` bzw. `/media/oem/scan/rc-park_null/`, im Repo Symlinks (Nutzerregel 2026-11-01; Root war bei 99 %).
- Python-Umgebungen: `/media/oem/scan/venv-seg/bin/python -I` (trimesh, torch, CUDA), `~/.venvs/rcpark` (manifold3d fuer den Generator).
- Lange Jobs (Nullstart, SfM, Optimierer) nur ueber `tools/job_start.sh NAME LOG BEFEHL...` (systemd-Benutzerdienst): Claude-Code-Hintergrundshells werden bei Speicherknappheit beendet (2026-11-03).
- GPU PARALLEL (Nutzerwunsch 6.11., ersetzt "nur ein GPU-Job"): Der Absturz war VRAM-Ueberbelegung (Summe > ~7,8 von 8,2 GB; SiftGPU scheitert dann still mit 0 Keypoints), kein Parallelverbot (`modelle/GPU_PARALLEL_UNTERSUCHUNG.md`).
  Neue GPU-Jobs mit VRAM-Budget starten: `JOB_GPU_MB=<MiB> tools/job_start.sh ...` (laeuft parallel, solange belegt + Budget <= 7000 MiB), SIFT mit `RCPARK_SIFT_MAX=1600`, Torch mit `expandable_segments`;
  Budget je Werkzeug zuerst MESSEN (nvidia-smi-Zeitreihe), nicht raten. Jobs ohne Budget bleiben exklusiv (Altverhalten). `tools/nullstart.py` wartet per gpu_warten, Ernte deckelt auf 45 %; Werkzeugaenderung danach `tools/nullstart.py ... --ziel martinstor_null` als Wiederholbarkeitstest (Register AY/BA).
- **Jedes NEUE Rechenwerkzeug nutzt die GPU von Anfang an** (Nutzerregel, 8.11. mehrfach verletzt): Nachbar-/Abstandssuche ueber `tools/gpu_knn.py` (`min_abstand`, PyTorch3D knn_points), nie KD-Baum/`torch.cdist` auf grossen Mengen; vor dem Start der Schleife `nvidia-smi` pruefen (Auslastung > 0). Nur der Manifold-Generatorbau bleibt CPU (Kerne parallel).
- Nie zwei Optimierer/Generatorlaeufe parallel mit gleicher Zwischendatei; Generatordatei nicht aendern, solange Optimierer laufen.
- Kein Commit/Push ohne Auftrag; Commit-Texte enden mit den Attribution-Zeilen der Sitzung.

## Linienhafte Features automatisch erkennen (12.11., Nutzer: "nicht nur Rippen, alles generalisieren")
1. Ursprungsmethode nutzen: Kanten, die in mehreren Fotos/Farb-/Kontrastkanaelen vorkommen (Stabilitaetskarten, 440 SfM-Fotos `kam_lot2.json`), Tiefen-Sweep mit Konsens; ungebunden mehrdeutig bei parallelen Kanten -> Tiefenband +-0,25..0,6 m um die Modellflaeche (`kanten_tiefe_sweep_flaeche.py --flaeche STL --band`).
2. `kanten_features.py --farbe stabil --sweep SWEEP.npz --nur_ref`: Skelett, Zweige, Tiefe aus gesicherten Sweep-Punkten (Luecken interpoliert/geglaettet), Belegung >= 15-20 % (filtert Wandrauschen), Klasse (waagerecht/senkrecht/geneigt, gerade/gebogen), Doppelkanten zusammen, `--maske` = nur Fehlendes.
3. `features_in_objekt.py`: Filter, Fragmente verbinden, Duplikate gegen Vorhandenes, als Pfad mit eigener Flaechennormale ins Bauteil; danach Abnahme und Render neben Foto (Zahlen allein gelten nicht).
4. Druck: Teilnetze/nicht wasserdicht zuerst auf Mini-Splitter pruefen (`druck.splitter_verwerfen`), nicht auf Konsolen/Anbauteile schliessen (Ursache 12.11.).
5. Offen: Fragmente zu durchgehenden Splines verbinden (Verbinder greift auf Erker 1 nicht), Zweitkamera mit gleichem Massstab fuer Gegenprobe, Realitaets-% ueber Kreis.

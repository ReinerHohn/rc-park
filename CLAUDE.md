# RC-Park – Arbeitsregeln (Kurzfassung)
Volltext aller Regeln (Nummern 1-9e, Technik, Lesepflichten): `modelle/REGELN_AUSFUEHRLICH.md` – bei Bedarf gezielt per grep/Read-Abschnitt lesen, nicht komplett.
Aktueller Stand: `modelle/STAND_2026-11-14.md` (Abschnitt UEBERGABE am Ende zuerst lesen).

## KERNMETHODE (nie vergessen, Nutzer 15.11.2026)
- Modell = Fotokanten + Triangulation (Kanten-Tiefen-Sweep mit SfM-Kameras) -> Generator-Features. NICHT aus der dichten Wolke.
- SfM liefert vor allem die KAMERAS (K, R, t). Dichte Wolke/LoD2/DOM1 nur Lage-Veto, Hoehe, Gegenprobe. Dachart/Form aus Fotos (Regel 9d/9e).
- Jede Pipeline/Kette (auch `tools/gesamtkette.py`) braucht die Kantenstufe + Foto-F1 (`tools/teil_fotoform.py`) + `tools/foto_diff.py` als Tor.
- **WANDBILD = BAUPLAN (Durchbruch Schwabentor, Nutzer 17.11.2026 "gigantischer Schritt"):** jede Wand aus vielen Fotos entzerrt zum Wandbild (`fassade_fein.py`, 1-cm-Raster) + Tiefe je Zelle (`tiefe_lokal.py`, `relief_aus_fotos_mono.py`) -> Features werden daraus NACHGEBILDET (Umriss, Profil, Tiefenstufen aus Bildkanten). Erkennen bestimmt nur Zone/Loch, nie die Gestalt; KEINE Musterteile aus dem Katalog ("irgendeine Tuer"). Katalogfunktionen nur fuer Freistehendes, auch dann Form aus Fotokanten mehrerer Ansichten. Ablauf: `modelle/PIPELINE_FASSADEN.md`.

## Abnahme (Pflicht)
- Nach JEDER Generatoraenderung: `tools/bauen_abnehmen.sh <objekt>`; nur bei "alle Pruefungen bestanden" weiter. Sollwerte nie lockern ohne neue Quelle (+ `historie`).
- Sichtbeobachtung = Testauftrag: erst `beobachtungen_offen` (datum, wer, text, naechster_schritt) in `masstabelle.json`, dann messen, dann Generator aendern.
- Nach jedem Bau `modelle/<objekt>/audit/seiten.jpg` ansehen; Zahlen allein gelten nicht. Neue Elemente: `beleg(seite, element, quelle)`; Annahmen heissen `ANNAHME: ...`.
- Fotomasse nur ueber `tools/foto_mass.py`; Zaehlungen nur am Foto (`tools/foto_zaehlung.py`); Form/Masse richten sich nach Fotokanten, Wolke nur Lage-Veto.
- Nach Bau: `tools/fehlteile_finden.py`, `tools/foto_diff.py`, `tools/teile_lage_pruefen.py`; vor Zeigen/Druck Teil neben Referenzfoto ansehen.
- Nach JEDER tools-Aenderung zuerst `tools/schnelltest.sh` (30 s, feste Erwartungen; rot = erst klaeren). Offene Arbeit: `modelle/AUFGABENLISTE_2026-11-16.md`.
- Nach tools-Aenderung: `python3 tools/regression.py modelle/<objekt>/objekt.json --pruefen`.
- Linienhafte Features (Rippen, Baender, Leisten, Stäbe) NIE nach Farbschwelle/Wolke: Mehrfoto-Sweep mit Stabilitaetskarten (`tools/kanten_tiefe_sweep_flaeche.py`, Tiefenband um Flaeche) -> `tools/kanten_features.py --farbe stabil --sweep` (Luecken per Belegung/Spline, Rauschen faellt weg) -> `tools/features_in_objekt.py`; danach Abnahme + Render neben Foto. Druck-Teilnetze: erst `druck.splitter_verwerfen` pruefen (Mini-Splitter), nicht Konsolen.
- Nach dichter Wolke (jedes Objekt, auch im Nullstart Schritt `grundriss`): `tools/kamera_abdeckung.py <sparse>` (Kameraluecke >90 Grad = Seite ungesehen) + `tools/wolke_grundriss_pruefen.py <objekt.json> --wolke <npy>` (rc 3 = Wolkenhaufen auf der Strasse = falsch verortetes Teilnetz, nicht modellieren; Test B dort nur Hinweis) + `tools/lage_gps_pruefen.py <objekt.json> <SFM-AUSRICHTUNG.json>` (Foto-GPS gegen Lage: Massstab/Drehung, rc 3).
- Nach jedem Bau das Bild Modell NEBEN Foto ansehen (`tools/modell_neben_foto.py`, automatisch ueber objekt.json `neben_fotos` -> `audit/neben_<foto>.jpg`), je Seite mindestens ein Foto; ohne dieses Bild nichts als passend melden.
- Fassaden-Kette: regelmaessige Teile scharf (`tools/bauteile.py`, Picks `tools/wand_ortho.py`, Masse `foto_mass.py`); Bruchstein `relief_einsatz.py` -> Putz eben per Fotofarbe `relief_putz.py` -> Loecher/Fremdkoerper `steine_generieren.py` (nie in Oeffnungen; generiert = ANNAHME).
- Fassaden automatisch (Stufen `fassaden`, `fenster` der Gesamtkette; feines 1-cm-Fassadenbild `fassade_fein.py`; lokale Feinrechnung der Tiefe `tiefe_lokal.py`): Ablauf, Zahlen, Grenzen in `modelle/PIPELINE_FASSADEN.md` - vor Fassadenarbeit lesen.
- Fenster = echte Loecher: am Generatorende `bauteile.aushoehlen` (Wand `WAND_MM` 1,2 mm im Druck); glatte Quader `relief_quader_eben.py`; Fugen, wo das Scan-Relief Brei ist, aus dem feinen Fassadenbild `steine_aus_foto.py` (Bild `<x>_foto.jpg` ansehen). Nutzerbild aus der 3D-Seite erst am STL nachrendern (`modell_ansicht.py`).
- Wand ohne Foto (leeres Fassadenbild) = Auftrag: `tools/seiten_luecken.py ... --download --holen` (Stufe `seiten`; alle freien Quellen, Nachregistrieren), sonst Kamera aus Modellpunkten + `fassade_ein_foto.py`. Nie spiegeln/erfinden. Neue Bauteile nur als generische Funktion in `tools/bauteile.py` (Katalog in PIPELINE_FASSADEN.md).
- Nutzer laedt vor Ort ein Foto hoch = sofort `tools/foto_check.sh <objekt> <datei>` laufen lassen und kurz antworten: PASST / PASST NICHT + was aendern, Bild mit Zielrahmen zurueckschicken. Fotobedarf zeigen: `tools/foto_auftrag.py` (Stadtplan, Standorte, markierte Ziele; Wunschliste `modelle/<objekt>/fotowuensche.json`).
- Quellen-Blindheit beachten (Laser/LoD2/Fotos/Dokumente); Quellenwidersprueche nicht mitteln.
- Neues Bauteil/falsch: Agentenauftrag aus `modelle/VORLAGE_BAUTEIL_RUNDE.md`.

## Technik
- Sitzungsbeginn: `bash tools/hpwmi_pruefen.sh` (bei ACHTUNG KERNEL-MODUL Nutzer sofort sagen).
- Grosse Daten nur unter `/media/oem/scan/...`, nie Root-Platte; Symlinks im Repo.
- Python: `/media/oem/scan/venv-seg/bin/python -I`, Generator `~/.venvs/rcpark`.
- Lange Jobs nur `JOB_GPU_MB=<MiB> JOB_RAM_MB=<MiB> tools/job_start.sh NAME LOG BEFEHL...` (RAM-Buchung, grosse Jobs 11000). Neue Rechenwerkzeuge von Anfang an auf GPU (`tools/gpu_knn.py`, Merkmale ALIKED+LightGlue); vorhandene Werkzeuge VOR Start auf GPU-Nutzung pruefen; `gpu_wache.sh` meldet CPU-Jobs ohne GPU in `/media/oem/scan/rc-park_daten/gpu_warnungen.log`.
- Nie zwei Optimierer/Generatorlaeufe mit gleicher Zwischendatei parallel.
- Kein Commit/Push ohne Auftrag; Commit-Texte enden mit den Attribution-Zeilen der Sitzung. Pre-commit-Hook nur durch Nutzer aktivieren.
- Vor neuen Versuchen: `modelle/NICHTS_GEBRACHT.md`, `modelle/VERSUCHSREGISTER_MARTINSTOR.md`, `modelle/LIZENZ_WERKZEUGE.md`.
- Tool-Ausgaben kuerzen (cut/head/tail), Kontext sparen.

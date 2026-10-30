# Session-History / Handoff — Historisches Kaufhaus Freiburg (3D-Modell)

Zweck: Kontext-Übergabe. Alles Wesentliche, damit nach dem Kontext-Leeren nahtlos weitergearbeitet
werden kann. (Ergänzt FEHLER_ZUSAMMENFASSUNG.md, BEFUND_DRUCKBARKEIT.md, METHODE_GEBAEUDEGENERATOR.md.)

## Ziel
Aus Fotos + amtlichen Daten ein DETAILLIERTES, foto-genaues, 3D-druckbares Modell des Historischen
Kaufhauses Freiburg bauen — parametrisch, KEIN Hardcoding (jedes Maß/Detail aus Foto/Daten gemessen).
Danach: Flachteil-Steck-Bausatz (farbgetrennt) + generischer Gebäude-Generator fürs Nachbargebäude.

## HARTE REGELN (vom User, mehrfach, mit Nachdruck)
1. **KEIN HARDCODING.** Jede Dimension/Stückzahl/Form aus Foto/LOD2/DOP MESSEN → JSON → Generator liest.
   Bei Fehler NICHT den Wert raten, sondern den DETEKTOR bauen/messen. (Zuletzt verletzt bei Gauben-Größe!)
2. **Detail GROSS selbst anschauen** nach jeder Änderung; Metriken allein lügen (Gate gab 0,89 bei
   degenerierten Fenstern).
3. **Bauteil VORAB komplett aus Foto sezieren + Spec**, nicht Symptom-für-Symptom reagieren (sonst Oszillation).
4. **Parametrisch-gültig bauen + Guard**; NIE freie Multiplikatoren auf gemessene Geometrie (degeneriert).
5. **Massing amtlich aus LOD2**, Gebäude per `<gml:name>` wählen (Koordinate traf den Nachbarn!).
6. Vergleich IMMER im gleichen Blickwinkel (Frontfoto verkürzt das steile Dach → Maß-Trugschluss).

## Umgebung / Workflow
- Generator läuft in **System-python3** (hat trimesh 5.1.1 + shapely + cv2 + manifold3d).
- **Rendern** nur in venv **/tmp/rv** (`PYOPENGL_PLATFORM=egl`, `/tmp/rv/bin/python`); /tmp/rv hat
  KEIN cv2 (also cv2-Tools in system-python3 laufen).
- Build: `python3 tools/kaufhaus_measured.py` → `modelle/kaufhaus_freiburg/kaufhaus_measured.glb` +
  `khm_<teil>.stl` je Farbgruppe.
- 3D-HTML: `python3 tools/glb_html_viewer.py --glb ...glb --out ...kaufhaus_3d.html` (GLB+Foto eingebettet).
- Git-Branch **kaufhaus-freiburg** (viele Commits, siehe `git log`).

## Amtliche Massing (LOD2, FIX — in kaufhaus_mass.json + Quellcode)
Gebäude **DEBW_0010007Tv9r "Historisches Kaufhaus"**, Kachel LoD2_32_414_5316. Hauptteil (Teil1)
**23.3 × 20.5 × 21.4 m**. Verwendet: **W=24.1, D=20.0, Traufe(eave)=9.7(≈9.61 intern), First(ridge)=21.4**.
(Falle gelernt: Koordinate 414436/5316379 traf den Nachbarn „Wentzingerhaus/Museum für Stadtgeschichte"
DEBW_0010007Tv9k; Kaufhaus per `<gml:name>` wählen. Dach war lange zu kurz (First 15,4 geschätzt) UND zu
steil (D=12 statt 20) — beides via LOD2 korrigiert.)

## Dateien
- **Generator**: `tools/kaufhaus_measured.py` (alle Element-Funktionen; liest kaufhaus_mass.json /
  win_struct.json / win_profile.json / kaufhaus_params.json / kaufhaus_lod2.json / gauben_mass.json).
- **Detektoren** (Foto→JSON): `shape_extract.py` (Fenster-Kopfkontur+Aspekt), `fassade_gitter.py`,
  `foto_kanten_messen.py`, `lod2_gebaeude.py` (--name!), (Gauben-Messung noch zu bauen, s.u.).
- **Checker/Ratsche**: `kaufhaus_check_alle.py` (EIN Lauf: Massing-vs-LOD2 + Degeneracy + Kanten-Gate →
  Prioritätenliste), `kanten_abgleich.py` (Farbzonen-Kanten, --sweep feature-verankert),
  `fenster_detail_check.py` (interne Fensterkanten band-weise), `proportion_check.py`, `fenster_check.py`,
  `gauben_check.py` (Abstands-CV), `bogen_ratsche.py`.
- **Druck**: `druckbar_export.py` (1:50 STL, Textur-Detail raus, Voxel-Verbundcheck),
  `druckteile_flach.py` (farbgetrennte Flachteile → modelle/kaufhaus_freiburg/flachteile/).
- **Daten**: `daten/kaufhaus_freiburg/fotos/` (kh_fenster=Fassade frontal/scharf, kh_erker=Erker+Dach
  schräg, kh_jm3289=ganzes Gebäude frontal, …), `lod2/`, `dop/` (Orthofoto, .tfw Georef).

## Element-Status (was STIMMT)
- **Hauptfenster**: Kielbogen-Kopf (shoulder≈0,6, LEICHTER Durchhang dip=0,05 in der Mitte — zwei
  Spitzen über 2 Lichtern, NICHT flach/NICHT spitz), 2 Gold-Pfosten GANZ DURCH bis an die Kante,
  GESTUFTER Kämpfer (Mitte erhöht), feine waagrechte Saddle-Bars, Waben-Bleiglas. Parametrisch-gültig+Guard
  (`measured_window`, `_load_profile`). Gate: Fenster PASS.
- **Arkade**: 4 Bögen (amtlich/Foto), Archivolt-Ring (ARC_BW=lichte Weite/Pitch≈0,81), Pfeiler mit
  abgesetztem DUNKLEM Steinsockel (`pier_bases`, Farbe pierbase).
- **Balkon**: dunkel, NUR vor den Fenstern (BAL_X0/1 = ORIEL_X±1.9), stoppt vor den Erkern.
- **Erker**: Glockenhelm (startet UNTER der Traufe, Spitze ~62% Dachhöhe), Buchtfenster mit KONKAV-
  durchhängendem Kielbogen-Glas (facet_poly), feines GEÄSTEL (Rippennetz) unter der Bucht, kleine
  Wappen-SCHILDE (Gold-Rand+Feld+Kreuz).
- **Statuen**+solide Baldachine zwischen den Fenstern; **Treppengiebel**; **Seitenwand-Fenster** (3,
  GESCHÄTZT — kein klares Seitenfoto!); Dach moosgrün, roof_courses/diaper als Textur (im Druck raus).

## OFFENE PUNKTE (direkt weitermachen)
1. **GAUBEN (Dachfenster) — AKTUELL KAPUTT/IM FLUSS:**
   - FORM: nach genauer Foto-Studie (dorm_B face-on) = **WALMGAUBE mit kurzem waagrechtem First**
     (trapezförmige Ziegel-Vorderfläche schräg nach hinten-oben zum First + dreieckige Walm-Seiten,
     moderate Höhe). `dormer_roofs()` baut das. (NICHT spitz, NICHT Schlepp/Sprungschanze, NICHT flach.)
   - GRÖSSE: **User sagt zu KLEIN**. Ich hatte DORMER_W/H gerade HARDGECODED (2.3/1.4) → **User wütend
     (kein Hardcoding!)**. TODO: Gaubenbreite/-höhe aus dem Foto MESSEN (dunkle Gaubenfenster-Blobs /
     Gebäudebreite 24,1 m) → `gauben_mass.json` (dormer_w_m/dormer_h_m) → Generator liest es statt der
     Konstante. Mess-Skript war begonnen (gauben_mass.json noch leer). Anzahl/Lage: 3 untere + 2 obere
     versetzt (gauben_check Abstands-CV grün).
2. Waben auch in den ERKER-Fenstern (aktuell glattes Glas).
3. Wappen echter Reichsadler statt Kreuz (Foto zeigt Doppeladler).
4. Seitenwand/Giebel-Fenster am Foto verifizieren (geschätzt).

## Druckbarkeit (Strategie: „zwei Regime")
Druck-Geometrie (watertight, @1:50 ~44 cm → in ~4 Teile schneiden) + Feindetail (Waben/Glasur/Ziegel/
Farbe) als TEXTUR/Bemalung. `druckbar_export.py` lässt sprossen/dachmuster/dachrauten weg. Flachteil-
Bausatz: farbgetrennte Panels liegend drucken + stecken (`druckteile_flach.py`). Steckzapfen/Dach-
Schrägen-flachlegen = noch offen.

## Nächster großer Schritt (vom User gewünscht)
Element-Bibliothek aus `kaufhaus_measured.py` in `tools/bauwerk_generator.py` heben (Konstante→Config),
`BauwerkConfig` (Massing+Stückzahlen+Feature-Flags), Kaufhaus- + **Wentzingerhaus**-Konfig (Nachbar,
weniger Detail, has_arcade/oriels/statues=False). Siehe METHODE_GEBAEUDEGENERATOR.md.

## Ratsche-Lauf (so prüfen)
`python3 tools/kaufhaus_check_alle.py --render /tmp/model.png` → Massing-vs-LOD2 + Degeneracy + Kanten-
Gate-Sweep → Prioritätenliste. Absolut-Score des Zonen-Gates ist instabil → nur Ranking+Overlay nutzen;
fürs Fenster-Feindetail `fenster_detail_check.py`; immer zusätzlich selbst GROSS hinschauen.

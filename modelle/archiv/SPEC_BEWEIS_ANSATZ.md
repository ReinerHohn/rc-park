# Spezifikation: Vergleichslauf "Welcher Ansatz ist bei unserer Datenlage der beste?" (Nutzer 5.11. abends: "beweise, generalisiert")

Behauptung (Plan Stufe 4/4b): Modellbasierte Rekonstruktion (parametrischer Generator aus amtlichen Daten + lokales Restfeld aus Fotos/Wolke) ist bei wenigen
gemischten Fotos in allen Zielmetriken mindestens so gut wie reine Photogrammetrie und wie das reine amtliche Modell, und in der Fotokantenmetrik besser als beide.
Der Lauf ist falsifizierbar: Faellt eine Metrik, steht das als Befund gegen den Ansatz im Register. Keine Metrik wird nachjustiert.

## Verfahren (gleiche Eingaben je Objekt)
- **A Photogrammetrie**: vorhandene dichte Wolke (Kaufhaus `objekt.json["freiraum"]["dicht"]` = kaufhaus_null4/sfm/dicht_alle fused.ply mit Ausrichtung; Martinstor: `modelle/martinstor/objekt.json["sfm"]`/`freiraum`, sonst martinstor_null/sfm) -> Normalen schaetzen -> Poisson-Rekonstruktion (Open3D, Tiefe 9-10, Dichte-Trimmen 2 %) -> groesste Komponente -> wasserdicht machen (fill_holes, sonst Voxel-Neuvernetzung 5 cm) -> STL im Modellrahmen (gleiche Zentrierung wie objekt.json).
- **B amtlich**: Generator NUR mit LoD2/DOM1/DGM1 (Bauteile `rumpf_lod2` + Treppengiebel/Dach aus LoD2, keine Fassadenbauteile, keine Fotoparameter: `BAUTEIL_PARAM` mit `fassade_auto.aktiv=false`, `first_versatz_m=0` usw.; pruefen, wie `qualitaetsstufen.v_ausgang` das Ausgangsmodell baut, und genau das nehmen).
- **C Modell + Restfeld**: bester uebernommener Laeuferstand (Kaufhaus: `/media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null6/modell_s3_v9.stl` bzw. stand.json "fest" der letzten uebernommenen Stufe; Martinstor: `modelle/stl/martinstor_1-87.stl` aus objekt.json), plus Restfeld-Kennzahl (restfeld_fassade) als Zusatzausgabe.
- **Synthetisch (Wahrheit bekannt)**: ein viertes "Objekt" aus dem Martinstor-Generator mit verstellten Parametern (z. B. Traufe +0,8 m, ein Fenster weniger je Seite, Helmneigung) = WAHRHEIT; daraus mit `tools/test_foto_diff.py`-Mechanik (Pruefbilder: `foto_rendern`, Albedo, Rauschen, k1, Verdeckerkasten) 10 Fotos aus den echten Martinstor-Kameras; dazu eine synthetische "Wolke" (Oberflaechenpunkte der Wahrheit mit 5 cm Rauschen, nur von den Kameras sichtbar - Sichtbarkeit per Embree) und ein synthetisches DOM1 (1-m-Raster Maxima der Wahrheit). Dann A, B, C auf diesen synthetischen Eingaben (C = Generator mit Standardparametern + Stufe 2 param_suche auf den synthetischen Fotos + Restfeld).

## Metriken (gleich fuer alle Verfahren)
1. **Geometrie gegen Wahrheit** (nur synthetisch): Hausdorff/Chamfer-Abstand Flaeche-zu-Flaeche (trimesh/Open3D, 100k Stichproben), Anteil der Oberflaeche mit Fehler > 3,5 cm (Druckaufloesung 1:87 bei 0,4-Duese) und > 10 cm.
2. **Zurueckgehaltene Fotos** (echt + synthetisch): je Objekt 6 kalibrierte Fotos, die in KEINER Anpassung benutzt wurden (nicht in `PS.fotos_waehlen`-Liste des Laufs; Liste im Bericht), `foto_diff --mehrstufig` (bzw. der dann gueltige Standard) -> rot (Modellkante ohne Foto) und gelb (Fotokante ohne Modell) je Foto, Mittel + je Foto.
3. **Dach gegen DOM1**: `tools/pruefstand.py` Zeilen mit quelltyp laser/lod2 (Werte), zusaetzlich mittlere |Hoehendifferenz| Modelloberkante vs DOM1-Zellen ueber dem Grundriss (vorhandene Werkzeuge `hypso_*`/`dach_dop_check` pruefen, sonst eigene 20 Zeilen).
4. **Zaehlmerkmale**: Pruefstand-Zeilen mit merkmal `anzahl` (Kaufhaus: Arkade f02; Martinstor: Tuermchen, Oeffnungen je Flaeche): bestanden/nicht je Verfahren (A wird hier meist nan/0 liefern - das ist ein Ergebnis, kein Fehler).
5. **Druckbarkeit**: wasserdicht, Koerperzahl, Volumen, Dreieckszahl, Slicer-Lauf (`tools/bambu_slice.py --help` lesen; wenn Slicer nicht ohne Drucker laeuft, nur Geometriepruefung) und Mindestbreite (kleinste Wandstaerke per Strahltest, 200 Stichproben).
6. **Aufwand**: Rechenzeit je Verfahren (`tools/aufwand_log.py`), Handarbeit = 0 (alle Schritte skriptiert in `tools/beweis_ansatz.py`).

## Bestanden-Kriterium (vorab festgelegt)
- C >= A und C >= B in JEDER Metrik (gleich = innerhalb der Saatstreuung aus S1b T0 bzw. 1 %), und C < A und C < B in Metrik 2 (gelb UND rot im Mittel ueber die zurueckgehaltenen Fotos) bei mindestens 2 von 3 Objekten.
- Zusatzbefund (kein Kriterium): wo A besser ist als C (einzelne Fassadenzellen), ist das genau der Bereich, den das Restfeld noch nicht uebernommen hat -> Liste dieser Zellen als Eingabe fuer Stufe 4.

## Ausgabe
`modelle/BEWEIS_ANSATZ_2026-11-06.md` mit Tabelle (Verfahren x Objekt x Metrik), Bildblatt je Objekt (A | B | C aus derselben Kamera, Overlay rot/gelb auf einem zurueckgehaltenen Foto) unter `modelle/<objekt>/audit/beweis_ansatz/`, JSON mit allen Zahlen, Register-Abschnitt "CM - Vergleichslauf Ansatz". Bilder ANSEHEN und je Objekt 3 Saetze.

## Regeln
GPU nur, wenn frei (nvidia-smi leer; andere Agenten S1b/S2 laufen); alles auf der Datenplatte `/media/oem/scan/rc-park_null/beweis_ansatz/`; keine Aenderung an Generator, Pruefstand, foto_diff, qualitaetsstufen; keine Sollwerte; kein Commit. Lizenz: Open3D MIT, trimesh MIT - Zeile in LIZENZ_WERKZEUGE.md, falls Open3D neu ist (pruefen: `python -c "import open3d"` in venv-seg; wenn nicht vorhanden, Poisson ueber `pymeshlab`? Falls beides fehlt: STOPP und melden, nicht installieren).

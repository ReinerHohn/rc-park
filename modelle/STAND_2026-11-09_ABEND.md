# Stand 9.11.2026, 22:30 – Übergabe vor /clear (Kaufhaus Freiburg)

**Nach /clear zuerst lesen:** dieses Dokument, dann `modelle/REZEPT_GEBAEUDE_AUS_FOTOS.md` (Methode + Lehren-Register L1 ff.), `modelle/LOGBUCH_2026-11-09.md`, `modelle/NICHTS_GEBRACHT.md`.
Anrede des Nutzers: „mein großer Meister“. Sprache: Deutsch.

## Ziel (Nutzer)
Vollautomatisch aus Fotos und Kanten ein „geiles“, druckbares H0-Modell (1:87). Die Methode soll generalisiert werden, damit weitere Gebäude für die Miniaturwelt schnell gehen. Jede Lehre wird allgemein ins Lehren-Register geschrieben.

## Was steht
- **Kantengitter v12** `$D/segmente_gitter_v12.json` mit 5252 Kanten bleibt das beste. D = /media/oem/scan/rc-park_daten/kaufhaus_alle.
  - Abdeckung unter 15 m: 0,85 bis 0,90.
  - Dach über 15 m: 0,20 bis 0,24. Das ist die größte Lücke.
  - Kette: `tools/gitter_kette.sh` (Kopie nach /tmp starten, cd-Zeile fest setzen).
- **Generator `kaufhaus_grob3`**, Runde 5, Commit 928c312:
  - Prüfstand grün, 1 Teilnetz, wasserdicht.
  - 8 H0-Druckteile in `modelle/stl/kaufhaus_grob3_teile/`, Werkzeug `tools/druck_teilung.py`.
  - Konsolen je Instanz (11), Brüstung 68 Baluster plus Pfosten, Laubenrückwand Bogen 3 mit Fenster und Tür (foto_mass).
- **3D-HTML:** https://claude.ai/artifact/9mpGqmnVR3bBqUYnh6jXyQ, Version 17.
  - Inhalt: Wolke 450k, Gitter v12, Generator Runde 5 als violette Ebene „Modell“.
  - Neu bauen mit `viewer_kanten_bauen.py OUT --seg … --kp $D/kette_video_alle/konsens_B.npy --n 450000 --koerper <STL in m>`.
  - Generator-STL × 0,087 liegt im lot2-Rahmen.
- **Körper v11** (Gitter-Körper, `tools/koerper_kette.sh`): Konsolen je Instanz aus der Wolke (`konsolen_zelle.py`), Kantenliste export/zuruecklesen (`koerper_kantenliste.py`).
- **Kanten-Tor** `tools/kanten_tor.py` und **muster_fit** `tools/muster_fit.py`:
  - Synth 3/3.
  - Mittellicht-Kämpfer 12,28 automatisch bestätigt, Seitenlichter 11,75.
  - Fenster 5×3 automatisch gefunden (Periode 3,966).
  - M-6120-Regression nur 2 von 9 Kanten grün.

## Nutzerbefunde, offen (Regel 2: Prüfung muss vorher fehlschlagen)
1. **Erker**, beide: Grundriss vieleckig, Fensterband, Wappenzone, Unterbau. Das Modell trifft auf 6261 nur teilweise.
2. **Erkerdächer**: Echt ist ein geschweifter Helm, dessen Fuß fast über die ganze Erkerbreite reicht (r ≈ 1,6). Das Modell ist ein Kegel mit r 0,85 auf einem Kasten. Belege: `modelle/kaufhaus_grob3/audit/nutzerbefund/2026-11-09_erkerhelm_*_6261.jpg`. Regel-9d-Verstoß.
3. **EG-Fenster** Bögen 1, 2 und 4: Das große Tor in Bogen 2 fehlt, eg0 und eg2 sind ANNAHME. **Die Rückwandebene liegt laut Wolke bei 7,29, nicht bei 6,54.** Damit sind alle M-6120-Werte auf der falschen Ebene.
4. **Westumriss**: Auf 6261 ragt ein Umriss samt Giebel über das Nachbarhaus, vermutlich die angenommene hintere Hälfte oder der Rumpf.
5. Stufe von 8 cm bei z 8,0, Querbalken je Licht im Generator, Gaubenform (Schlepp oder Satteldach) nicht entschieden.
6. **Kein Probedruck und kein Slicen** ohne ausdrückliches Wort des Nutzers.

## Laufende Agenten zum Zeitpunkt der Übergabe
Ihre Ergebnisse landen in den Logs. Nach /clear dort nachsehen, nicht auf Meldungen warten.
| Agent | Auftrag | Log / Ergebnis |
|---|---|---|
| Generator Runde 6 | Rückwandebene messen (7,29?), Westumriss, Erker plus geschweifte Helme, EG-Tor/Fenster, danach Kämpfer je Licht und Stufe z 8 | `modelle/LOG_GITTER_GENERATOR_2026-11-09.md`, `audit/gitter_generator/runde6_*` |
| Teile-Sichtprüfung (BEWEIS) | `tools/teile_sichtpruefung.py` + `tools/test_teile_sichtpruefung.py`: je Bauteil die besten Fotos, Präzision UND Recall, Gate. Muss auf Runde 5 (928c312) ROT melden für Westumriss, Erker, Erkerhelme, Fenster Bogen 3 und den Helm-Fit; GRÜN für Konsolen, Brüstung, Säulen, Fenster und Tür Bogen 3 | `modelle/LOG_TEILE_SICHT_2026-11-09.md`, `audit/teile_sicht/` |
| muster_fit / Kanten-Tor Runde 3 | Baluster-Regression, Mindest-Pixelbreite → UNGEPRÜFT, Zurücklesen ins Körper-Modell plus erstes Nicht-Entwurf-Fenster-Overlay, Gauben-Unterscheidungskanten | `modelle/LOG_MUSTER_2026-11-09.md` |
Die Arbeitskopien dieser Agenten sind im Commit „Sicherung vor /clear“ mitgesichert (WIP-Stand möglich). Nach dem Fertigwerden: Bericht prüfen, Bilder SELBST ansehen (Übersichtsfoto 6261 GANZ plus bestes Foto je Bauteil), Fehlerliste über ALLE Bauteile, dann committen.

## Versprechen an den Nutzer (einhalten)
- Beweis der Teile-Sichtprüfung: Tabelle erwartet gegen Urteil plus Ausschnitte. Danach bietet der Nutzer einen **Blindtest** an: Er nennt eine Fehlerstelle, das Werkzeug muss sie rot melden.
- Das Werkzeug kommt als Gate in `bauen_abnehmen.sh` und hinter `formen` in `gitter_kette.sh`.
- Nur selbst Geprüftes als „trifft“ melden, alles andere als „ungeprüft“.
- Dach von oben: Internetfotos sind gescheitert (0,20 → 0,24, Rauschen). Der Nutzer wurde um eigene Fotos vom Münsterturm gebeten.

## Offene Entscheidungen
- Regressions-Schnappschuss Kaufhaus: noch nicht erneuert (regression.py meldet „identisch“). Erst nach Runde 6 mit Registereintrag.
- `modelle/stl/_tmp_*.stl` (Testdateien Generator): löschen nur durch den Nutzer.
- Fremde Gegenprobe (LIMAP/EdgeGaussians): Download fremden Codes war blockiert; braucht die Freigabe des Nutzers („Gegenprobe freigegeben“).

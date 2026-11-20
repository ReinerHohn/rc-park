# RC-Park Freiburg

**Miniatur-Wunderland zum Selbersteuern** — Konzept + Businessplan für eine Indoor-Erlebniswelt in Freiburg, plus eine
**3D-Pipeline**, die Freiburger/Schwarzwälder Bauwerke und Gelände aus öffentlichen Daten (LOD2, Luftbild, Laser, Fotos)
als druckbare Modelle erzeugt. Vision: **`KONZEPT.md`** · Inhaltsübersicht: **`README.md`**.

- **Projekt-Wissen als Baum: `PROJEKT.md`** (Wurzel) → `Doku/projekt/<ast>.md` mit **Gilt · Versucht · Offen**.
  **Vor jedem neuen Lösungsansatz** den passenden Ast unter „Versucht" lesen (✗ = nicht nochmal probieren); **nach jedem
  Versuch** eine Zeile eintragen. Nutzer-Vorgaben → „Gilt".

## Aufbau
| Ort | Inhalt |
|---|---|
| `KONZEPT.md`, `README.md`, `HANDOFF.md` | Vision · Index aller Dokumente · Übergabe-Kontext für die Claude-Instanz auf dem GPU-PC |
| `Doku/konzept/` · `Doku/markt-kalkulation/` · `Doku/standort/` · `Doku/rc-attraktionen/` · `Doku/modellbau/` | Konzept-/Businessplan-Kapitel nach Thema |
| `annahmen.json`, `attraktionen/*.json` → `build.py` → `businessplan.html` | Finanzmodell (Daten → generierte Seite); `mvp-rechner.html` = FPV-Pop-up-Rechner |
| `tools/*.py` (~210) | 3D-Pipeline: Daten holen (LOD2/DOP/Laser/Fotos), Generatoren, Vermesser, Validatoren/Juroren, Export STL/HTML |
| `bauwerke/<name>.json` | Konfiguration je Bauwerk (Massing aus LOD2, Stückzahlen/Features aus Fotos) — Generator liest sie |
| `modelle/<name>/` · `modelle/METHODE_*.md` | erzeugte Modelle (STL/GLB/HTML) · die Methoden-Rezepte (z. B. `METHODE_WAHRZEICHEN_AUS_FOTOS.md`, `METHODIK_KOMPLETT.md`) |
| `daten/<ort>/` | heruntergeladene Rohdaten und Fotos je Bauwerk · `modelle/QUELLEN_REGISTER.md` = Quellen-Register |
| `scan-setup/` | eigenes Scannen (Photogrammetrie), Linux/Windows-Setup |

## Befehle
| Zweck | Befehl |
|---|---|
| Businessplan bauen + beide Rechner öffnen | `./start.sh` (oder `python3 build.py`) |
| harte Tests | `python3 tests/test_quellen_hart.py` · `python3 tests/test_hybrid_hart.py` (Exit 1 bei Fehlschlag) |
| Änderungs-Wächter nach JEDER Modell-Änderung | `python3 tools/aenderung_check.py` (VORHER/NACHHER/Heatmap/Foto) |
| Doku-Gesundheit | `/doku-pflege` (Projektteil `.claude/doku-pflege.json` + `.md`) |

## ⛔ Harte Regeln (Nutzer)
- **Kein Hardcoding — alles erkennen.** Jedes Detail (Maße, Stückzahlen, Fenster, Formen, Farben) wird aus Daten/Fotos ERKANNT →
  JSON → Generator liest. Bei einem Detail-Fehler NICHT den Wert ändern, sondern den Detektor bauen/fixen. Typ-Generatoren sind
  generisch (Haus = Konfiguration), nie ein Einzelhaus-Skript.
- **Alle öffentlichen Daten zusammenführen, nichts raten**, wenn eine Quelle existiert: LOD2 = Grundriss/Höhen/Dachform, Luftbild =
  Dachstruktur, Laser (nDOM) = Grobform/Validierung, Fotos = Fassadendetail. Massing aus LOD2 schlägt Foto-Schätzung.
- **Erst die Realität zählen, dann bauen:** Foto Zone für Zone sezieren (Ground Truth), dann Modell bauen und durch Nachzählen beider prüfen.
- **Selbst hinschauen — Score ≠ Ergebnis.** Nie Erfolg behaupten wegen einer Metrik/Juror-Note; finalen Render neben dem Foto Element
  für Element prüfen. Foto-Grundwahrheit schlägt Juror-Mehrheit.
- **Änderungs-Wächter ist Pflicht** nach jeder Modell-Änderung; Heatmap gegen Foto prüfen, bevor „verbessert" gesagt wird — sonst zurück (git).
- **Parametrisch-gültig, nie degeneriert:** keine freien Multiplikatoren auf gemessene Geometrie; Gültigkeits-Guard + Fallback.
- **Druckbar:** Feindetail als Textur/Bemalung auf saubere, wasserdichte Geometrie — nicht als tausende Mikro-Teile; Druckmaßstab zuerst.
- Schätzungen im Businessplan sind begründete Annahmen (öffentliche Benchmarks), keine testierte Finanzplanung.

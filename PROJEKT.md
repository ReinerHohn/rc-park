# PROJEKT.md — Wurzel des Projekt-Wissens (rc-park)

> Hier steht, was NICHT im Code/Git-Log steht: Vorgaben, Entscheidungen, **was schon versucht wurde** und was offen ist — als Baum.
> Nur den Ast öffnen, der zur Aufgabe passt. Vision: `KONZEPT.md` · Inhalte: `README.md` · Technik/Regeln: `CLAUDE.md`

## Äste
| Bereich | Datei | Kern in einer Zeile |
|---|---|---|
| 💶 Konzept & Geschäft | [`Doku/projekt/konzept-geschaeft.md`](Doku/projekt/konzept-geschaeft.md) | klein + zentral starten, Phasen mit Beweis, Display statt RC als Kern |
| 🚜 RC-Attraktionen & Ausstattung | [`Doku/projekt/rc-attraktionen.md`](Doku/projekt/rc-attraktionen.md) | robust hinter Polycarbonat, Getriebe-Bagger 1:14/1:16, schienengeführt |
| 🖨️ Modellbau & Druck | [`Doku/projekt/modellbau-druck.md`](Doku/projekt/modellbau-druck.md) | Flaches lasern, Körper drucken, Blickfang scannen; Qualität vor Material |
| 🏛️ 3D-Pipeline & Validierung | [`Doku/projekt/pipeline.md`](Doku/projekt/pipeline.md) | alles erkennen statt hardcoden, alle Daten mergen, selbst hinschauen |

Jede Ast-Datei: **Gilt** (Vorgaben/Entscheidungen) · **Versucht** (Ansatz → Ergebnis → Lehre) · **Offen**.

## Pflege-Regel (für Mensch und Claude)
- **Vor einem neuen Lösungsansatz:** im Ast unter „Versucht" nachsehen — ✗ nicht erneut probieren (außer die Lage hat sich belegbar geändert).
- **Nach einem Versuch:** EINE Zeile `TT.MM. · Ansatz → ✓ | ✗ | ↺ ersetzt | ⚠ Falle | ⏸ · Lehre [Quelle/Commit]`.
- Neue Vorgabe → „Gilt"; Erledigtes aus „Offen" löschen. Details gehören in `Doku/<thema>/` oder `modelle/METHODE_*.md`.
- Weitere Fallen-Sammlungen: `modelle/METHODIK_KOMPLETT.md` §3, `modelle/METHODE_3D_AUS_ALLEN_DATEN.md` §7, `modelle/PROTOKOLL_VALIDATOR.md`.

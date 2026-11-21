# Übergabe 21.11.2026 18:50
Weiter mit: „weiter“ (oder /uebergabe fortsetzen; vorher Skill `sitzungsbeginn`) – dann **modelle/PLAN_NACHT_2026-11-21.md** abarbeiten.

## Auftrag
- „Was? Arbeitstage? … Morgen früh ist es fertig“ → Schwabentor-Modell aus der Kette bis 22.11. früh, Nacht durcharbeiten.
- „du sollst nicht manuell rumfummeln, die Kette sollst du automatisch machen“ → nur Kettenläufe zählen; Agenten liefern Kettenstufe + Test.
- „es darf halt nicht sein, dass wir zweimal halb machen, statt einmal richtig“ → Schwabentor zuerst, Martinstor nur nebenher.
- „Mindestplatz ist ab sofort 15 GB“ / „nicht abbrechen, sondern anfangen aufzuräumen“ → umgesetzt (7baf8d6a3).
- „berichte mir regelmäßig“ → nach jedem Lauf Bild + X/11 + Fehlerliste (SendUserFile).
- „Plan entwickeln, … dann arbeiten einfache Agenten das ab“ → modelle/PLAN_NACHT_2026-11-21.md.

## Erledigt und geprüft (alles gemergt, Schnelltest 0 Fehler, gepusht bis e67be7985)
- Agenten gemergt: Nischen-Fenster, leere Fassaden (Paar-Probe), Seiten vereinen (ohne Sperrliste), Höhen (Kette misst richtig; referenz_hand Tor-Abschrift berichtigt), Laterne aus Himmelskante + Tordurchfahrt, Umgang + Eckquader, Massstab (Kette NICHT zu gross; Dach zu breit → DOM1-Veto-Stufe), Putz/Uhr (glatter Putz, Zifferblatt).
- Tor-Übernahme: Höhe+Breite müssen passen (Lauf 1121o gab Tor die Fenstermaße) – Fix mit Test.
- Platz-Tor 15 GB, räumt auf statt abzubrechen; Coredumps (4,1 GB) vom Nutzer gelöscht.
- Erkenntnisse: modelle/ERKENNTNISSE.md (8 neue Zeilen), Wissensbaum pipeline/betrieb (Durchbruch Seiten-SfM).
- Letzter gesehener Kettenlauf 1121o (18:11): 4/11, ~30 % Realität (Tor zu, Süd/Ost glatt, Wandmitte krümelig) – Ursachen inzwischen gemergt, aber NOCH NICHT im Lauf bewiesen.

## Läuft gerade
- `kette-schwabentor-1121p` (gestartet 18:12, --ab fassaden --bis bauplan; hat Umgang/Laterne/Durchfahrt/Eckquader, NICHT Dach-Veto/Putz-Uhr) · Log /media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-1121p.log · Ende ~19:10 · danach Plan Schritt 5.
- `kette-martinstor-1121b` eingereiht (Hintergrund-Shell, startet nach 1121p per RAM-Buchung) · Log …/kette-martinstor-1121b.log.
- Agent „Kette beschleunigen“ (Worktree-Zweig worktree-agent-aaa66bd05bb189959) und Agent „zirkuläre Verdeckung/Vordach“ (worktree-agent-a43dea14bfa4ba0ff) – nach Fertigmeldung mergen (Plan Schritt 3).
- Dauerdienste gpuwache/platz_waechter/editordraht nicht melden.

## Nächste Schritte
1. Nach Ende 1121p: Plan Schritt 5 (Sichtblatt ansehen + an Nutzer, X/11, Logbuch).
2. Fertige Agenten mergen, dann Lauf `kette-schwabentor-1121q` (Plan Schritt 4) – enthält dann Dach-Veto, Putz/Uhr, Beschleunigung.
3. Schleife laut Plan bis morgens; Endbeweis Nulllauf.

## Entscheidungen des Nutzers
- ✓ Handstand nie Eingabe. ✓ Nur Kettenläufe zählen. ✓ Schwabentor vor Martinstor. ✓ Mindestplatz 15 GB, aufräumen statt abbrechen.
- ? Handstand-Vergleichswerte Uhr/Sohlbank/Laterne um ~3,4 % berichtigen (Kette belegt richtig) – Nutzer fragen.
- ? hand_annahme-Vermerk Tor-Kämpfer (zählt nicht mehr) – Nutzer bestätigen lassen.
- ? Fototermin Süd/Ost Schwabentor.

## Fehler und Lehren dieser Sitzung
- 45 min durch Platz-Tor verloren (nicht vorher aufgeräumt) → 15-GB-Regel, Memory feedback-interne-ssd-nur-noetiges.
- Worktree mit uncommitteten Änderungen per --force gelöscht → Memory feedback-worktree-nur-sauber-entfernen.
- Tor-Übernahme ohne Höhenprüfung (mein Code) → zerstörte Tor im Lauf 1121o; Fix + Test.
- Zirkuläre Messung: Modell als Verdecker löscht eigenen Beleg (Vordach) → Agent läuft.
- Zu viel Handarbeit tagsüber → Register ERKENNTNISSE.md (ARBEITSWEISE).

## Wichtige Pfade und Befehle
- Plan: modelle/PLAN_NACHT_2026-11-21.md · Logbuch: modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md · Verlauf: modelle/schwabentor-1120/audit/hand_vergleich_verlauf.jsonl.

## Vorsicht
- Worktree agent-a1b159488c8983a24 (Zweig ram-je-stufe-1120) nicht anfassen. Uncommittete fremde Änderungen (kaufhaus_grob3, martinstor_gk, MASSNACHWEIS) nicht mitcommitten.
- Toshiba-Platte nie anfassen; Buchung RAM/GPU nie von Hand senken; Löschen nur nach „Ja“.
- Systemplatte nur ~10 GB frei (Agenten-Worktrees auf Root) – nach Agentenende .claude/worktrees auf /media/oem/scan verlegen.

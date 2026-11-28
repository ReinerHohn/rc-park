# SPEC: Gestalt nur aus Fotokanten (Nutzer 28.11.2026: "das ging unter, obwohl es in der CLAUDE.md stand")
Verwandt: CLAUDE.md (KERNMETHODE), modelle/PLAN_HANDMODELL_IN_KETTE.md, modelle/ERKENNTNISSE.md (28.11. Audit "Wolke statt Fotokanten").
Zweck: Die Regel steht nicht nur als Text, sondern als pruefbare Invarianten mit je einer Pruefung. Neue Aenderung = erst Invarianten lesen.

## Invarianten (jede muss durch ein Tor/Test belegt sein; Status in der letzten Spalte der Zeile)
1. **Quelle der Gestalt.** Jedes Bauteil in `elemente.json`/`koerper_auto.json` hat ein Fotomass (`foto_umriss`, Kanten-Sweep, Wandbild, `foto_mass`). Maße, Konturen, Profile, Daecher, Kaesten, Baender dürfen NICHT die Quelle "dichte Wolke", "LoD2" oder "DOM1" haben. Pruefung: Quellen-Waechter (Entwurf 28.11., noch nicht in main) - Status OFFEN.
2. **Wolke/LoD2/DOM1 nur in drei Rollen:** Lage-Veto (blockiert nur bei Widerspruch der Fotokanten zur UNABHAENGIGEN Lage, nie weil die Wolke fehlt), Hoehe, Gegenprobe. Nie Rueckfall: ist eine Fotoflaeche "uneinig" (z. B. 55 von 92), wird die Ursache geklaert oder das Teil nicht gebaut (Beleg "kein Fotomass"), nie auf Wolke ausgewichen.
3. **Annahmeregel nur am Foto.** Ein Bauteil bleibt im Modell, wenn Foto-F1/foto_diff der Zone es belegt; nie weil "mehr Wolkenpunkte am Modell liegen" (Selbstpruefung der Wolke, so kasten0).
4. **Tor NACH dem Bau.** Foto-Tor und Bestand-Tor pruefen das FERTIGE Modell (nach `bauplan`), Zonen automatisch aus dem Modell abgeleitet (Dach, Traufe, Kaesten, Nebenturm), nicht nur Laterne/Spitze. "gleich" bei glatter Pyramide darf nicht moeglich sein.
5. **Neue Objekte erben die Regel.** `tools/objekt_anlegen.py` schreibt keine Wolken-/LoD2-Gestaltwege (`gebaeude_aus_lod2`, `wolkenrest_koerper`, `dach_aus_profil`) in neue Generatoren.
6. **Agentenauftraege nennen die Quelle.** Jede Vorlage/jeder Auftrag (Vorlage `modelle/VORLAGE_BAUTEIL_RUNDE.md`) enthaelt die Zeile "Quelle der Gestalt = Fotokanten; Wolke/LoD2/DOM1 nur Lage-Veto/Hoehe/Gegenprobe".

## Aenderungsregel
Wer Code anfasst, der Gestalt formt (bauteile.py, dach_bauen.py, fassaden_kette.py, koerper_schleife.py, Bau-Stufen in gesamtkette.py), liest diese Datei zuerst (pfadabhaengige Regel `.claude/rules/gestalt-aus-fotokanten.md`) und nennt im Commit die Quelle der Gestalt.

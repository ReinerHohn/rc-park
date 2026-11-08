# Methode: Ort parametrischer Bauteile per GPU-Sweep (Nutzer 8.11.: "sehr wichtig, generalisiert, unbedingt umsetzen")

Ziel: fuer JEDES Bauteil jedes Objekts den richtigen Ort finden, ohne lokale Optimierer (CMA-ES) auf falschen Start zu verlassen.

1. Bauteil EINMAL bauen (Generator, NUR_BAUTEIL), Oberflaeche abtasten. Wolke -> Abstandsfeld (Voxel, GPU, knn), Modell -> Abstandsfeld.
2. Alle Verschiebungen (du entlang Fassade, dn senkrecht, dz Hoehe; Achse `fassade_n` aus objekt.json) per Nachschlagen bewerten (zweiseitig, 80 % getrimmt, Kappung 1.5 m).
3. Pyramide: 10 cm ueber +-Bereich, 6 verschiedene Peaks, dann 3 cm, 1 cm, 4 mm. (Geplant: 25-cm-Vorstufe ueber +-5 m.)
4. **Bestimmtheit je Achse**: Plateaubreite (Abstand <= bester + 1 cm). > 0,3 m = Achse nicht bestimmt (z. B. Erker/Fenster in dz: senkrechte Wand). Nicht bestimmte Achsen NICHT uebernehmen; ihre Lage kommt aus anderen Merkmalen (Oberkante, Dachkante, Foto).
5. **Beweis zuerst**: `--synth du,dn,dz` ersetzt die Wolke durch die Modellflaeche, verschoben + Rauschen 3 cm + Streupunkte; der Sweep muss den Versatz zurueckfinden. Erker:1: (0.8,-1.2,0.5) -> (0.796,-1.196,0.496); (-1.5,1,-0.7) -> (-1.500,1.000,-0.688). Fensterreihe:eg0 FAELLT durch (Abstand 0.21, kein Treffer): offen.
6. Urteil und Uebernahme nur mit Render + `teile_lage_pruefen.py`; unplausible Verschiebungen (Gauben dz -2.6 m = Boxrand) sind Plateau/Fehlminimum, nicht Befund.

Werkzeuge: `tools/teil_sweep_gpu.py`, `tools/sweep_alle.py` (Ergebnis `modelle/<objekt>/SWEEP_ALLE.md`).
Offen: Fenster-Beweistest reparieren, Vorstufe 25 cm, Normalen-/Kantenterm gegen Plateaus in dz, Fototerm.

## Befunde 8.11. abends (Warum Beweistest genau, echte Wolke nicht)
- Synthetik bleibt <1 cm auch bei 10 cm Rauschen, nur-sichtbaren Flaechen, echter Wolke als Stoerinhalt (`--synth_dazu`), Formfehler 15 % (nur dz driftet bis 0,6 m). Methode ist also nicht die Ursache.
- Echte Wolke: bester Abstand bleibt 0,17-0,56 m => Modellteil und Wolke stimmen in Form/Ort nicht ueberein.
- OFFENE BEOBACHTUNG (Regel 5, nicht mitteln): Rechter Erker in der NEUEN Wolke u 7,8..11,7 (Breite 3,9 m, Mitte 9,8) vs Modell/alte Wolke Mitte 8,36 Breite 1,75; LoD2-Ecke rechts u=9,64. Links stimmt (Wolke -10,2..-7,1, Modell -8,97). => neue Wolke rechts evtl. ~1,4 m verzogen. Schiedsrichter: LoD2-Anker als Ausgleichs-Bedingung im gemeinsamen SfM (naechster Schritt), Fotos.
- Fehler in sfm_kameras_export.py: Feld `C` stimmt nicht mit -R^T t ueberein (siehe Pruefung); Projektion ueber Rn/tn ist richtig (Wolke passt aufs Foto), Fotoauswahl nach Abstand nicht auf `C` stuetzen.

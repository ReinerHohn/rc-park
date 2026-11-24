# Stand 12.11.2026 vormittags (nach /clear zuerst lesen)

Anrede: "mein grosser Meister", Deutsch, ehrliche Fehlerliste und Realitaet %, keine Schoenfaerberei.
Ziel: ueberzeugendes H0-Modell kaufhaus_grob3 (Historisches Kaufhaus Freiburg) fuer Miniatur-Wunderland, ueber den Konvergenz-Kreis. Drucken ist NICHT das Ziel.
Viewer: https://claude.ai/artifact/9mpGqmnVR3bBqUYnh6jXyQ (Neubau: `bash /media/oem/scan/rc-park_tmp/viewer/neu_html.sh`, dann mit dem Artifact-Tool auf diese URL publizieren; Stand zuletzt v55).

## Prioritaeten des Nutzers
1. Erker Netzrippen (Gedaest, Rosetten, Rippenbuendel in die runde Saeule, Eckfiguren/Drachen). Schluesselfoto 6171 (dreisträngige Spitzbogenrippen, Rautennetz, Buendel); Rosetten am West-Erker in 6162 sichtbar.
2. Baldachine. 3. Wasserspeier. 4. Dachschindeln/Zipfel. 5. Erker-Fenster (Butzen, nicht Sprossen). 6. Seiten-/Gassenwand-Fenster (mehrfach gemeldet). 7. Laube Dienste (akzeptiert).
Offener Nutzerfund 20:59: "Erker Ost: aeusseres Segment fehlt (Gassenseite)" (Fotos 6259, i_09, n11_05/06). Ob mit Seitenfenstern Ost- oder Westwand gemeint ist, ist UNGEKLAERT (Agent ordnete n11_05/06 dem staffelgiebel__west zu; Ostwand unkalibriert) -> Nutzer fragen.

## Harte Regeln (Nutzer)
- Nie abbrechen wegen Platz ("Abbruch ist Kacke ... immer"). Platzwaechter tools/platz_waechter.sh (root <10 GB, Daten <14 GB -> auslagern).
- Prozess muss ohne Nutzer laufen; GPU/CPU voll nutzen; Nacht nicht verschwenden.
- Privaten Ordner handy_phone_2026-11-11/nicht_kaufhaus NIE oeffnen. Nie loeschen, nur verschieben. Grosse Daten nur unter /media/oem/scan.
- Lange Jobs nur per `JOB_GPU_MB=<MiB> tools/job_start.sh NAME LOG BEFEHL`. Commits nur eigene Dateien: `flock /media/oem/scan/rc-park_kreis/merge.lock git commit -- <pfade>`; Texte enden mit `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01BMC5F7JqzthTsrTAV2gKLz`.
- Fremde uncommittete Dateien nie anfassen: tools/konvergenz_bericht.py, tools/nachbarn_modellrahmen.py, tools/formfund_pruefen.py, realitaet_verlauf.jsonl.
- Nach tools-Aenderung `python3 tools/regression.py modelle/kaufhaus_grob3/objekt.json --pruefen` ("identisch"). Keine Objektnamen im Code.
- masstabelle-Eintraege: beobachtungen_offen braucht datum, wer, text, naechster_schritt; vor Commit `bash tools/bauen_abnehmen.sh kaufhaus_grob3 --nur-pruefen` (Memory feedback-masstabelle-pruefen-vor-commit).
- Hotel-App-Nachrichten (QR-Code, Raspberry Pi) gehoeren zu einer anderen Sitzung.

## Was in der Nacht 11./12.11. passiert ist (ehrlich)
- Rauschtor (6fbe1c61) eingefuehrt: teil-lokale Nullkontrollen (0,3 m verschoben/angehoben, 90 Grad gedreht), Messwahl f1_fein/f1, Messbarkeits-Filter, Rueckgabe aus, Start-Abnahme main. Grund: Foto-F1-Schwelle 0,02 lag unter dem Rauschen (~0,03); in 4 Tagen keine Konvergenz (pixel ~71 %).
- Nachtlauf 00:30-07:45: 54 Runden (12 leer, 37 verworfen, 5 angenommen = Laubensockel/Satteldach, Aenderung +-0,00-0,01, nicht sichtbar). Erker/Baldachine/Figuren/Gauben waren NIE Ziel: globaler Sperrzaehler (MAX_GLOBAL 3) zaehlte Verwerfungen aus dem alten, rauschblinden Tor. Mein Fehler: vor dem Start nicht `--nur_wahl` angesehen. Eintrag in modelle/NICHTS_GEBRACHT.md.
- Verwertbare Reste: Balkonkonsolen-Patch (konvexe Huelle ueber konkaves Profil; f1_fein 0,432 -> 0,531, Rauschtor bestanden; nur abgelehnt wegen "Hoehenlage verdaechtig: 0,3-m-Kopie misst besser f1_h 0,807 vs 0,753") -> Neupruefung laeuft; Westgiebel +0,033 vom Pruefer als erfunden abgelehnt (diagonales rotes Band), Lehre: First laeuft laengs, Giebeldreieck an der +n-Stirn.
- Erker 0 (Ornamentik) und baldachinreihe__baldachine: Rauschtor findet KEIN trennendes Mass (Reihen-Teil, Region zu gross); fotowunsch.jsonl hat 15 Eintraege (Fenster EG0/EG2/OG, Nischen, Helme, Dienste-Sockel).

## Heutige Aenderungen (committet)
- eb6c10f7: Sperrzaehler zaehlt nur Rauschtor-Runden.
- 4681cbc0: Regel 1-4 gegen Wiederholung: (1) TOR_VERSION-Hash im kreis.jsonl, Sperrzaehler zaehlt nur aktuelle Torversion; (2) Regler startet stuendlich `bauteil_kreis.py --nur_wahl` -> wahl_probe.json (waehlbar, Nutzerfund-Teile, gesperrte Nutzerfunde); (3) Freigabe gesperrter Nutzerfunde (freigabe.json), wenn 1 h keine Runde an Nutzerfund-Teilen, max alle 3 h je Schluessel; (4) Stundenbericht in kreis_regler.log + /media/oem/scan/rc-park_kreis/kaufhaus_grob3/stundenbericht.txt mit ALARM-Zeilen.
- 68ed6955: Fehlalarm beim Start behoben. c23ad76d: Agentengrenze 35 statt 60 Minuten (`--max_minuten`).
- Regler: `tools/job_start.sh kreis_regler /media/oem/scan/rc-park_kreis/kreis_regler.log python3 tools/kreis_regler.py kaufhaus_grob3 --gpu_ziel 101 --max 4`. Aenderung an bauteil_kreis.py beendet Spuren an der Rundengrenze.

## Laufende Arbeiten (beim Wiedereinstieg pruefen)
1. Konsolen-Neupruefung (kein Agent): Job `rcpark-kreis_konsolen_regate`, Log /media/oem/scan/rc-park_kreis/kreis_konsolen_regate.log, Patch /media/oem/scan/rc-park_kreis/kaufhaus_grob3/patches/konsolen_huelle_20261112.patch. Wartete auf gpu_tor.lock. Bei Annahme: Viewer neu bauen + publizieren. Bei Ablehnung wegen Hoehe: Hoehen-Sweep der Konsolenreihe (tools/teil_sweep_gpu.py), Patch erneut.
2. Agent a3ee0950df4503a40 (Sonnet): Element-Messregion fuer Reihen-Teile (Baldachine, Erker 0), Worktree /media/oem/scan/rc-park_tmp/wt_element, Beweis synthetisch + Echttabelle je Element. Bericht kommt per Notification. Wiederverwendbar: tools/zier_ausschnitt.py (Elementboxen -> Vollaufloesungs-Ausschnitt), teil_varianten_tor.py. element_vergleich.py ist ungeeignet (Wolkenprofile).
3. Regler mit 4 Spuren laeuft; Zielwahl-Probe zeigt jetzt 24-27 Kandidaten, Erker 0/1 oben. Belegt waren zuletzt erker_polygon__1, bogenreihe__laube, staffelgiebel__ost, quader__laube_sockel_w.
4. Kontrolle um ca. 20 Uhr: mindestens eine sichtbare Erker-Annahme (fehlendes Segment oder Netzrippen). Morgen frueh: pixel-Realitaet > 72 % (heute ~71 %), sonst Weg wechseln. Zeitprognose "Miniatur-Wunderland-tauglich": 2-3 gute Naechte fuer Erker/Baldachine/Dach, Schaetzung, keine Zusage.

## Offene Punkte (Reihenfolge)
- Erker-Netzrippen: frische Agentenrunde mit voller Beschreibung aus Foto 6171 (Pruefer muss 6259 sehen; erker6/erker7-Runden scheiterten an Sperre/Formfund-Pruefer "erfunden").
- Erker-Segment aussen (Gassenseite) mit Foto 6259 als Pflichtfoto fuer den Formfund-Pruefer.
- Seitenfenster klaeren (Ost/West), dann Gassenwand-Runde.
- Turmfotos n11_01-03 nicht registriert (kaum gemeinsame 3D-Punkte, lockere Registrierung gab Kamerahoehe 42-98 m = falsch, verworfen). Idee: erst mit j_/c_-Handyfotos Turmpunkte triangulieren, dann PnP.
- Feinsuche (/media/oem/scan/rc-park_tmp/feinsuche/lauf_voll/ergebnis/): Cluster sind unbenannte Orte ("Feinform fehlt") und speisen den Kreis schon als Foto-Cluster; Import in die Masstabelle bewusst NICHT gemacht (keine Aufgabe fuer Agenten). Interpretation aus top10.jpg: Erker-Fenster mit Masswerk/Sprossen/Eckfigur, Laubenpfeiler-Sockel (achteckig profiliert statt rund), Traufe/Speier, Sprossenfenster, Gewoelberippen.
- Spaeter: Bild-zu-3D fuer Drachen/Speier/Figuren (SPAR3D/Hi3DGen; Hunyuan3D wegen EU-Lizenz ausgeschlossen), Dachdeckung, Erker-Fenster Butzen, Fehlteil-Pfad (56 Runden, 4 Annahmen, baut nichts) reparieren oder pausieren.
- Quota: ~70 % der Woche verbraucht (Reset 15.11. 9:00).

## Messfakten
- Grob-Foto-F1 (0,18 m Glaettung) ist fuer Ornament blind/invertiert; f1_fein (0,03 m) trennt Nullkontrollen. Rauschen je Teil: erker_polygon__1 f1 -0,070 / f1_fein +0,031 (nur f1_fein trennt); gaubenreihe__oben f1 +0,042; baldachine: kein Mass.
- Cache der Nullkontrollen: /media/oem/scan/rc-park_kreis/kaufhaus_grob3/rauschen/ (131 Eintraege).
- Probe der Zielwahl jederzeit: `python3 tools/bauteil_kreis.py kaufhaus_grob3 --nur_wahl`.

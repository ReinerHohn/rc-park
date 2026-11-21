# Logbuch: Schwabentor von null, Handarbeit in die Kette (20./21.11.2026)

Ziel (Nutzer): „Was wir damals manuell gemacht haben, muss jetzt automatisch laufen“. Maßstab ist der Handstand `schwab_v3`.

Nachspielen:
- Ein Kettenlauf: `tools/gesamtkette.py schwab_auto --ziel schwabentor-1120 --ab bauplan --bis bauplan --dicht-stufe schnell` (über `tools/job_start.sh`).
- Logs: `/media/oem/scan/rc-park_daten/job_logs/kette-schwabentor-1120<x>.log`.
- Die Kette vergleicht jeden Lauf automatisch mit dem Handstand: `audit/hand_vergleich.json`. Der Verlauf mit dem git-Stand je Lauf steht in `audit/hand_vergleich_verlauf.jsonl`.
- Je Werkzeugänderung gibt es einen Commit; der Commit-Text nennt das Messergebnis.

## Läufe (alle automatisch, ohne Eingriff)
- **1120d/e (20.11., bis 23:00):** Bauplan-Stufen laufen durch, der Körper bleibt ein Quader. Befund: Der Sweep findet den Erker, aber nichts baut ihn („nur Vorschläge“).
- **Werkzeug 20.11. ~23:50:** `vorbauten_bauplan.py` und `bauteile.vorbauten_aus_json` (Höhenfeld). Einmal von Hand geprüft: Erker-Fotokanten am Modell 22 % → 95 % (Kanten-Sweep `kanten_vorbau/`).
- **1120f (00:10–00:21):** Erster Beweis, dass die Kette den Erker selbst baut (meine Testdatei war vorher gelöscht). Sackgassen-Tor grün.
- **1120g (00:21–00:39, ab Stufe fenster):** Uhr gefunden (5,13 m), dazu eine Schein-Uhr im Erkerbild (77 % Kantenstütze). Der Erker war weg: Die Frontstreuung lag bei 0,60 und damit genau an der Schwelle 0,6.
- **Korrektur:** Streuung ≤ 0,8 (Erker 0,5–0,6, Torbogen-Durchblick 1,5) und Uhr-Stütze ≥ 0,85 (echt 98–100 %, Schein 77 %).
- **1120h (00:45):** Erker wieder da, eine Uhr, Konsolenfelder als Nicht-Fenster verworfen.
- **Nutzer:** „Wurstelschrott“ zum Höhenfeld-Erker. Umbau auf `galerie_messen`, das nur die Maße misst; die Gestalt kommt aus `Wand.galerie` wie in schwab_v3. Streben werden im 1-cm-Wandbild gezählt: 6, Abstand 1,56 m.
- **1120i (00:47–00:55):** Die Galerie mit 3 Pfosten, 6 Streben und Vordach kommt aus der Kette selbst. 18 Stufen in Ordnung.
- **Handstand-Vergleich neu (`tools/hand_vergleich.py`, `referenz_hand.json`):** 0 von 11 passen. Das „Vordach“ bei 18,2–19,2 m / +2,3 m war sehr wahrscheinlich die Oberleitung (2 m zu hoch).
- **Korrektur:** Traufe = erstes Band über dem Holm; Dachanschluss aus der Uneinigkeitskarte.
- **1120j (01:05–01:14):** Traufe 16,02 (Soll 16,09), Anschluss 19,39 (Soll 19,43). Weiter 0 von 11, weil in jedem gefundenen Teil ein Maß danebenliegt.

## Sackgassen und Zeitfresser
- Höhenfeld als Gestalt: treppig, keine Pfosten oder Streben. Ersetzt durch Maße plus bewährtes Bauteil.
- Der Kandidat „Dach“ aus dem Sweep, ohne Prüfung, ob er an die Galerie anschließt, war die Oberleitung.
- Fenster-Tor nur mit „vorn ≥ 20 %“: Im Zweitlauf (Galerie im Modell) lagen die Konsolenfelder bei vorn 14 %. Jetzt gilt zusätzlich: hinten < 5 % = keine Nische, und hinter einem gebauten Vorbau = kein Fenster.
- Die 3D-Seite war am Handy unbrauchbar: Kamera auf den Ursprung gerichtet, Modell zu 55 % durchsichtig. Behoben in `modell_3d_html.tpl.html`.
- Von Hand angestoßen (nur Messung, kein Modellteil): Kanten-Sweeps in `kanten_vorbau/` und `kanten_v3/`, Probeläufe der Werkzeuge in der Scratchpad-Ablage.

## Offen (Reihenfolge nach Handstand-Vergleich)
1. Laterne (fehlt)
2. Pfosten 2 statt 3
3. Vordach-Ausladung 1,10 statt 1,54
4. Galerie-Unterkante und Holm je ±0,6 m
5. Uhr-Höhe +0,7 m. Höhenbezug prüfen: Der Torscheitel liegt −0,45 m daneben, also kein einfacher Versatz.
6. Zweites Rundbogenfenster
7. Treppenturm, Umgang, Eckquader, Dachüberstand
8. Durchfahrt: Der Feldseite fehlen Fotos (f01: 4 Fotos, 18 % Abdeckung).

# 🖨️ Modellbau & Druck  ← [PROJEKT.md](../../PROJEKT.md)
Kapitel: `Doku/modellbau/` · Methoden: `modelle/archiv/METHODIK_KOMPLETT.md`, `modelle/MASSSTAB.md` · **Unteräste (vollständig, je Quelleintrag eine Zeile):** [druck](modellbau-druck/druck.md)

## Gilt
- Merksatz: „Alles Flache lasern, alle Körper drucken, den Blickfang scannen/Resin."
- Generisches kaufen (Faller & Co.), nur Freiburg-Einzigartiges selbst drucken.
- Qualität vor Material: Detail nie für Verschnitt/Zeit opfern; Terrain-Laser mit smooth 0.
- Will der Nutzer lasern, den Laser-Lauf selbst starten (`grbl_send.py --yes`).

- Kein Slicen/Probedruck vor Detailtreue, nur auf ausdrücklichen Nutzerwunsch – dann Drucker selbst starten [Memory feedback-kein-druck-vor-details, reference-drucker-starten]
- Details (Uhr, Zierteile) als Klipsteil auf den Bambu (0,4); MK4S (0,8) nur grobe Wand mit Rippen, Rahmen, Brim [Memory feedback-druck-details-bambu-wand-prusa, 17.11.]
- Wandstärke im Druck `WAND_MM` 1,2 mm (drei Bahnen 0,4) = 0,10 m bei 1:87 („minimal dünn, stabil, schnell“) [PIPELINE_FASSADEN Z.129, Nutzer 16.11.]

## Versucht
**H0-Druck aus der Foto-Pipeline (Bambu P1S, Prusa MK4S, ab Nov.)**
- 03.11. · Slicer-Bericht als Freigabe → ✗ drei Fehldrucke · Zapfen = Luftdruck, Bettart Cool vs Textured PEI (55 °C); Schnitt ansehen [Memory bambu-p1s-druck-lektionen]
- 03.11. · Bambu-CLI mit geerbten Profilen → ⚠ Falle · Profile abflachen, sonst 0,2-mm-Standard; `M190 S55` prüfen [Memory bambu-p1s-druck-lektionen]
- 17.11. · PrusaSlicer-G-Code mit `M862.3 P "MK4"` → ⚠ Falle · MK4S hält mit Rückfrage; `prusa_slice.py` schreibt MK4S [15493969e]
- 17.11. · 1-mm-Wand mit 0,8-Düse ohne Aussteifung → ✗ Wand verzog, Uhr drückte durch · Innenrippen (schlank 60 mm/0,9 mm) + Rahmen + Brim 5 mm [Memory feedback-druck-details-bambu-wand-prusa, 1494f928d, 8dd6b782e]
- 17.11. · Zeiger-Aufsätze 0,68 mm → ✗ löste sich · ≥ 1,0 mm; mit Brim → Fäden ↺ Spritzling mit 3-mm-Rahmen, sonst Raft (`--floss`) [19477b6a8, 2a7e0ab6b, 05f1b00ff]
- 17.11. · Wanddetail als Klipsteil (`druck_klips.py`, Schnitt an Grundplatte, Stiftlöcher mit 0,6-mm-Haut) → ✓ Methode [9f293b287]
- 17.11. · aufrechter Hohlkörper → ↺ flache Wandpaneele + Steinplatten · ~2,5× schneller (gemessen) [PIPELINE_FASSADEN Druckzeit 17.11.]
- 17.11. · Einsatz-Bauart (1-mm-Wand, Sockel hohl) → ✓ Methode · 334 statt 824 cm³, 14 h statt 24 h [PIPELINE_FASSADEN Agentenrunde 17.11.]
- 17.11. · Klebefalz nur am Rand + Eckpfosten → ✗ verworfen · Körper zerfiel in 243 Stücke [PIPELINE_FASSADEN 17.11.]
- 17.11. · Luftinseln je Schicht prüfen + Stützen (`druck_luft.py`) → ✓ Methode · Anlass Zeiger-Spaghetti [c0b901f63, 27c68ac03]
- 18.11. · Luftstützen ohne Taschen-Kenntnis → ⚠ Falle · ragten in Putz; Platte auf Tasche minus halbes Fügespiel beschneiden [ZIEL V8, f97f9adcc]
- 18.11. · eine Plattenebene je Wand → ↺ Plattentiefe je Pixel (geneigte Ebene + 0,6-mm-Stufen) · Restwand < 0,6 mm 41 % → 2 % [b649c0db5]
- 18.11. · ringschicht über alle Schnittstücke schließen → ✗ falscher Hohlraum · nur Stücke > 0,05 m² [NICHTS_GEBRACHT 18.11.]
- 18.11. · Fehlerfall-Testobjekt gelöscht → ⚠ Falle · Ursache nicht mehr nachstellbar; Fehlerfälle bis Klärung behalten [NICHTS_GEBRACHT Druck-Taschen]
- 12.11. · Dachziegel-Leisten bündig mit Teilrand/über Traufhülle → ⚠ Falle · 91 Teilnetze; Leisten nie über Hülle/Dachenden [NICHTS_GEBRACHT kreis1 040618, L-KR40]
- 12.11. · Teilnetze für Konsolen gehalten → ⚠ Falle · erst Mini-Splitter prüfen (`druck.splitter_verwerfen`) [REGELN Linienhafte 4]
- 09.11. · Druckteilung nach Geometrie (Schnitt in waagerechte Unterseiten, beste von 6 Lagen) → ✓ Methode [L12]
- 01.11. · 0,4-mm-Düse für Reliefteile → ⚠ 108/113 zu dünn · Details mit 0,2 bzw. als Klipsteil [FERTIGUNG_SPLIT Düsenprüfung]
- 17.11. · `druck_vorcheck` für große Netze auf GPU → ✗ 14 GB VRAM, Absturz · ab 150k Dreiecken Embree [PIPELINE_FASSADEN Z.435]
- 17.11. · Bemalung: OBI-Wandfarbe als Grundierung, UHU-Sprühkleber → ✗ · Grundierung Army Painter Matt Grey, Sealant vor Decal, Acryl-Mattlack; OBI nur Lasur [Memory user-malmaterial-bestand]
- · Stein-Finish: Wash über Marble/Grau, Drybrush, dünn in Schichten → ✓ Methode [archiv/FINISH_STEINGEBAEUDE.md]

**Gelände, Laser, Stadtmodell (Okt.)**
- 22.10. · Farbe per AMS „Scan → AMS → fertig farbig" → ✗ Irrtum · nur 2–8 Volltöne, langsam, Abfall; Hero über Vollfarb-Service, sonst bemalen
- · ganze Stadt selbst drucken → ↺ kaufen + nur Wahrzeichen drucken · ~90 % weniger Druckzeit
- · alles lasern bzw. alles drucken → ↺ Hybrid (flach lasern, Körper drucken, Blickfang scannen)
- · LAD-BW-Münsterscan kommerziell nutzen → ⚠ Lizenz CC BY-NC · Freigabe oder eigener Scan
- 06.10. · Drohnenscan-Detail per Höhenfeld-Solidify → ✗ rastert zu Blobs · Screened Poisson
- 25.10. · Kanten-Lineale per Halb-Überblattung (Kerben) → ✗ brachen Rippe Y4 · oben aufkleben
- 24.10. · clean-contour (Douglas-Peucker) für Terrain-Platten → ✗ zerzog flache Platten · Open3D + Grid-Clip [1c339f2]
- 18.10. · Terrain glätten (smooth 0.8) für dichteres Nesting → ✗ Qualität vor Material
- 18.10. · Band-Rippen (`--rib-depth`) → ↺ Rippen bis Boden · 6-mm-Bänder zu wabbelig [d30ebc7]
- 22.10. · Fingerzinken mit Einzelzahn → ⚠ Sollbruch · mehrere Finger je Stoß, nur bei hoher Rippe
- 14.10. · Mini-SMD-LED-Schlitze in der Petersdom-Kuppel → ↺ Ø3,3-Bohrungen für 3-mm-LED
- 11.10. · Gelände-Überhöhung 3,7× → ✗ zu spitz/fake · 1,5–2×, auf allen Kacheln gleich
- 08.10. · 0,8-Düse für Hohl-Gelände (4,5× schneller erwartet) → ⚠ nur ~1,6× und mehr Plastik
- 11.10. · 1,2-m-Hirschsprung true-scale → ⚠ Material ∝ Fläche² (~31 kg/700 €) · 60 cm Sweet Spot
- 28.10. · Feindetail als Mikro-Geometrie (31.560 Sprossenteile) → ✗ nicht watertight · ↺ 20.11. entschieden: echte Löcher/Relief, aber druckbar ≥ 0,8 mm, keine Mikroteile
- · S9-Laser über HP-Dock / Pack-Report vertraut → ⚠ Serial-Abbruch · USB direkt; echten G-Code-Bereich prüfen (442 statt 410 mm)

## Offen
- Druck: 9 Steinplatten mehrteilig (meist 2 Stücke); Bausatz ohne Steinplatten; Testdruck Steinplatte (Fugen 0,35 mm sichtbar?); `druck_paneele.py` nicht gebaut (Stand 20.11.) [ZIEL Übergabe, PIPELINE_FASSADEN Z.456]
- Stand Höllental-Gerüst: `modelle/hoellental_geruest_a3/STAND.md`

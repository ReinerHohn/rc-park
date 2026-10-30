# Master-Plan: Freiburger Miniatur-Wunderland

Oberziel: der Stadt Freiburg ein Miniatur-Wunderland vorschlagen, Demonstrator als
Fähigkeitsbeweis (Anmalen · Licht · Bewegung). Prinzip überall: **max Effekt / min Handarbeit.**
Detailreferenzen: [[SWEET_SPOTS.md]] · [[BELEUCHTUNG.md]] · [[FINISH_STEINGEBAEUDE.md]] · [[FREIBURG_STRATEGIE.md]]

---

## 0. Die 5 Grundregeln
1. **Filament = Farbe**, wo's geht (Marmor=Stein, Bronze-Silk=Eiffel, bunt=Kirmes) → kein Pinsel.
2. **Eine 12-V-Schiene** für Motor + LED + Pumpe. Ein Netzteil für alles.
3. **N20 = Standard-Motor**, Antrieb per **Magnetkupplung durch die Platte** = verschleißfrei.
4. **Hohl drucken**, Gelände mit **0,8-HF-Düse**, Detail/Monumente mit **0,4** (P1S/MK4S).
5. **Modular bauen** (Regalbrett-Module), nie die Wohnung voll, wächst mit.

## 1. Maßstab (Hybrid)
- **N (1:160):** große Landschaft (Belchen & Co) — klein, billig, schnell.
- **H0 (1:87):** Detail/Technik/Demonstrator, bewegte Teile, Wahrzeichen-Showpieces.
- **Nie zwei Maßstäbe in EINER Ansicht** mischen. Monumente = eigener Schau-Maßstab (24 cm = ein P1S-Print).
- Figuren/Autos: **H0-Bulk fertig bemalt kaufen** (~10 €/100 Stk) → null Pinsel.

---

## 2. 🎨 ANMALEN / Finish (minimal Handarbeit)

### Gelände (Belchen & Berge) — Reihenfolge
1. **Druck grau** (0,8-Düse, hohl) — Grobheit egal, wird überdeckt.
2. **Spray-Grundierung Erdbraun** (Dose).
3. **Statische Grasfasern / Flock** mit verdünntem Weißleim (Noch/Busch Streugras) → Farbe kommt aus dem Gras, kein Malen.
4. **Dunkle Wash** in Täler/Vertiefungen → Tiefe.
5. **Hell drybrushen** über Grate → 3D-Pop.
6. **Schnee am Gipfel:** Weiß drybrush oder Backpulver+Weißleim.
7. **Wasser (Bach/See):** Gießharz/Epoxy eingießen.

### Steingebäude (Münster, Petersdom, Burg)
- **Druck in Marmor-/Stein-PLA** = Steinoptik direkt. ⚠️ Marble ist kühl/bläulich → **warm waschen**.
- **Skeleton-Bone-Spray** (warmer Stein-Grundton) → **Wash „Strong Tone"** (Rillen/Fugen) → **Drybrush Bone** (Kanten).
- Oder in 1 Anstrich: **Speedpaint „Ashen Stone"**.
- Petersdom-Kuppel: **Felder blau-grau (Blei), Rippen hell** = der Realismus-Trick.
- Alterung (optional): Regenstreifen (dunkle Wash nach unten), unten dunkler, Weathering-Powder.

### Eiffelturm / Metall
- **Metallic-Silk-Filament „antique bronze"** → Farbe + Glanz aus dem Material, kein Pinsel.

### Einkauf Finish (minimal)
Army Painter **Skeleton Bone Spray** (~12 €) · **Wash Strong Tone** / Speedpaint **Ashen Stone** (~4 €) · **Drybrush-Pinsel** (~4 €) · statisches Gras + Flock + Weißleim · Gießharz · (Marmor-/Bronze-Silk-Filament).

---

## 3. 💡 BELEUCHTUNG

### Grundsatz
- **Eine 12-V-Schiene.** LEDs in **4er-Reihen + 1 Widerstand (~220 Ω)** → Widerstand bleibt kühl, 4× Licht pro Strom.
- **Warm**, nicht kalt: warmweiß für Häuser, golden für Eiffel.
- **Anstrahlen statt Durchleuchten** bei Monumenten (warme LEDs im Sockel nach oben) — nicht das ganze Haus glühen lassen.
- **Lichtsperre:** Hausinnen schwarz/Alufolie → Licht nur aus Fenstern.

### Technik-Wahl
- **Versteckte Quelle:** 3–5 mm LED (billig, hell).
- **Sichtbare Punkte:** 0402 vorverdrahtete Micro-LED (kein Löten).
- **Viele Punkte aus EINER LED:** Fiberoptik (perfekt fürs Eiffel-Funkeln & viele Fenster).
- **Straßenlaternen:** 0402 im Kopf + **1,4-mm-Messingrohr als Mast** (Draht innen) ODER voll gedruckt mit Kabel-Rille.
- **Effekte / Tag-Nacht:** **NeoControl + WS2812** (bis ~100 LEDs, eine Datenleitung) oder PWM-Dimmer zum Faden. Tag/Nacht = der Wow-Moment.
- **Eiffel:** golden anstrahlen + Twinkle-Draht + blinkendes Leuchtfeuer oben.

---

## 4. 🔄 BEWEGUNG

### Grundsatz
- **N20-Getriebemotor (12 V, langsam 10–30 U/min)** + **Magnetkupplung durch die Grundplatte** (Motor unsichtbar drunter) = **null Verschleiß**, nur Dauerrotation.
- Drehzahl übers **Getriebe** wählen, nicht Spannung aushungern. Feintuning per PWM.
- **Leise:** Motor weich einkleben (Silikon/Schaum), PWM >20 kHz; beim Slicen Accel/Jerk runter.

### Bewegte Highlights
- **Seilbahn (Belchen-Skigebiet!):** H0 fertig **Brawa 6346** / **Jägerndorfer D-Line** (⚠️ H0, nicht N) ODER N20-Eigenbau. Marker-Quader (Berg-/Talstation) sind die Ankerpunkte.
- **Riesenrad / Karussell:** N20 + Magnet (drucken + Motor rein).
- **Fahrzeuge/Boote:** Magnorail (89–109 €, auch N) oder Faller-Car-System (Magnet+Draht).
- **Zug:** klassische Modellbahn-Runde.

---

## 5. 🖨️ Druck-Workflow
- **MK4S + 0,8-HF** = Gelände-Fabrik (hohl, Lightning-Infill, schnell). Große Flächen in **Kacheln** (nahtlos, ≤200 mm fürs MK4S).
- **P1S + 0,4** = Detail/Monument-Fabrik (Marmor/Metallic, hohl, 24 cm am Stück).
- **Überhöhung 2×**, **enger Zuschnitt aufs Massiv** (nicht flache Platte) = Drama.
- Profile: `mk4s_08hf_turbo` (schnell) / `..._silent` (leise) / `..._quality_nobrim` (Detail).
- Tipp: `gcode_resolution` an → kleinere Files, kein „transfer too slow".

---

## 6. 📍 Standort-Hebel: Münster (nur kulturell!)
- **Münstermarkt (FWTM)** umschließt das Münster (~8.000 m², 400 m) = extreme Frequenz.
- ⚠️ **Kommerz verboten** am Münsterplatz; Einvernehmen Stadt + Erzdiözese nötig.
- → **Als „Schwarzwald in Miniatur — Heimat-Ausstellung"** rahmen (kein Verkauf) = gangbar + emotional + Presse. Kontakt: **muenstermarkt@fwtm.de**.
- Günstige Dauer-Basis: Gewerbehalle Randlage (~6,90 €/m²) oder FWTM-Pop-up-Laden. Siehe [[FREIBURG_STRATEGIE.md]].

---

## 7. 🗺️ Phasen-Fahrplan
1. **Demonstrator (jetzt):** Belchen-Elefant (40 cm, überhöht) + Riesenrad (Bewegung+Licht) + 1 beleuchtetes Wahrzeichen → Fotos/Video.
2. **Solo-Pop-up / Heimat-Ausstellung** (FWTM, ~200 €, Innenstadt/Münster-nah) → öffentlich testen, Presse.
3. **Gemeinnütziger e.V.** (7 Mitglieder aus Eisenbahnfreunde Breisgau e.V.) → schaltet Sponsoring/Förderung frei.
4. **Kulturamt-Förderung + Crowdfunding** → fester kleiner Standort (<200 m² = keine VStättVO).
5. **Stadt-Pitch** → Stadt beantragt TIP-BW-Förderung für den großen Ausbau.

---

## 8. 🛒 Konsolidierte Einkaufsliste (Start)
**Bewegung:** N20 12 V langsam (×mehrere), PWM-Dimmer, Neodym-Magnete, 12-V-Netzteil.
**Licht:** vorverdrahtete SMD-LEDs/LED-Filament (warmweiß + gelb), Widerstände, Fiberoptik, (NeoControl+WS2812 für Effekte), 1,4-mm-Messingrohr.
**Finish:** Skeleton-Bone-Spray, Strong-Tone-Wash/Ashen-Stone, Drybrush-Pinsel, statisches Gras+Flock+Weißleim, Gießharz, Marmor-/Bronze-Silk-Filament.
**Kaufen fertig:** H0-Figuren/Autos (Bulk), Seilbahn (H0), ggf. Magnorail.

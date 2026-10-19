# Sweet Spots — Miniatur-Wunderland-Pitch (Freiburg)

Ziel: der Stadt Freiburg ein Miniatur-Wunderland vorschlagen. Demonstrator =
transportables Pitch-Board „Freiburg im Kleinen", das **Anmalen · Licht · Bewegung**
auf einen Blick beweist. Prinzip überall: **max Effekt / min Handarbeit**.

---

## A. Maßstab / Strategie
- **Hybrid:** N (1:160) für große Landschaft (Belchen), H0 (1:87) für Detail/Technik/Demonstrator. **Nie zwei Maßstäbe in EINER Ansicht** (nur in getrennten Modulen).
- **Pitch-Board = N** → epische Landschaft + viele Highlights auf eine transportable Fläche.
- **Monumente = eigener Schau-Maßstab**, nicht true-scale (MiWuLa macht Petersdom 1:100 vertikal / 1:130 horizontal). Niemand stellt ein Männchen an den Sockel → Maßstabssprung fällt nicht auf.
- **Monument-Regel am Bauraum:** real ≤20 m → echtes H0, ein Print; >20 m → auf ~24 cm stauchen (ggf. Breite stärker als Höhe, à la MiWuLa).

## B. Drucken
- **MK4S 0,8 mm = Gelände-Fabrik** (Belchen): hohl, schnell, grob reicht (Detail steckt in der Form).
- **P1S 0,4 mm = Detail-/Monument-Fabrik** (Münster, Petersdom, Eiffel).
- **Hohl drucken** (0 % Infill / Vase) → wenig Material, über Nacht fertig.
- **Ein Bauraum = ein Print = kein Segmentieren/Kleben** — größter Handarbeits-Killer. P1S ~24 cm nutzbar.
- Layer-Linien auf Steinbau = Mauerwerk-Look (Feature, nicht Fehler).

## C. Bewegung (wenig Verschleiß)
- **Magnetkupplung durch die Grundplatte:** Motor unsichtbar drunter, Magnet dreht Teil oben. Keine Welle/Dichtung/Zahnräder → null Verschleiß.
- Nur **Dauerrotation**, nie reziprok (kein Pleuel/Nocken).
- **N20 = Standard-Motor** → passt in die meisten druckbaren Projekte („N20 rein und fertig").
- **Drehzahl übers Getriebe wählen** (10–15 U/min), nicht über Spannung aushungern → volles Drehmoment, leise, kein Stottern. PWM nur zum Feintunen.
- **Leise:** Motor weich einkleben (Silikon/Schaum) statt hart verschrauben = entkoppelt. PWM >20 kHz, sonst Brummen.
- Gute sichtbare Bewegung: Seilbahn, Riesenrad, Karussell, Wasserrad.

## D. Spannung — eine Schiene
- **Mit Pumpe: 12 V DC** für Motor+LED+Pumpe (ein Netzteil). In DE überall, SELV = sicher am Wasser.
- Nur Motor+LED, max billig: **5 V USB** (Netzteil gratis).
- N20 kostet in jeder Spannung gleich → **kein Lock-in**, späterer Tausch = 2 €.

## E. Licht (kein Löten)
- **Vorverdrahtete SMD-LEDs mit Widerstand** / **LED-Filament**: einstecken, fertig.
- Alles auf eine Schiene.
- **Tag/Nacht-Schaltung + Zufalls-Flacker-Controller** = Wow ohne Programmieren.
- WS2812 + fertiger Sketch für Effekte (Feuer, Lauflicht).

## F. Finish OHNE Pinsel — Filament = Farbe ⭐
- **Marmor-/Stein-Filament** → Petersdom, Burg, Münster = Steinoptik direkt vom Drucker.
- **Metallic-Silk-Filament** → Eiffelturm (bronze-braun = echte Farbe + Glanz). *Nicht* metallgefülltes PLA (schmirgelt Düse); Silk reicht.
- **Terracotta/Sandstein-matt** → Altstadt-/Südhäuser.
- **Stein-/mineralgefülltes PLA** → matte Textur, versteckt Layer-Linien.
- Nur wo nötig: **Spray-Grundierung + dunkler Wash + hell Drybrush** (Gelände-Hänge). **Flock** fürs Grün.
- **Figuren/Autos: H0-Bulk fertig bemalt** (Amazon ~100 Stück ~10 €). Null Pinsel.

## G. Pitch-Logik
- **Lokal** (Münster, Schwarzwald, Altstadt) = emotionale Bindung der Stadt.
- **Tag/Nacht + Bewegung** = der Wow-Moment im Termin.
- **Modular** bauen (Regalbrett-Module) → nie Wohnung voll, wächst mit, einzeln transportabel.
- **Phasenweise** → früh steht was Beeindruckendes.

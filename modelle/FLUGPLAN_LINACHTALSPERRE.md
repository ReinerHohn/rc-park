# Flugplan: Linachtalsperre — Drohnen-Fotogrammetrie (DJI Mini 4 Pro)

> Ziel: vollständiger Foto-Satz für eine **metrisch saubere SfM-Rekonstruktion**
> (COLMAP/RealityCapture) der ganzen 13-Bogen-Mauer inkl. Luftseite (Wandscheiben +
> Querstreben in den Nischen), Krone und Wasserseite (konkave Schalen).
> Basiert auf dem Research-Stand (§8 der Methodik): >80 % Overlap, 300+ Fotos,
> Mehrwinkel gegen Selbstverdeckung. Lage: 48.0183 N / 8.2906 E, UTM32 447097/5318581.

## Bauwerk (Maße = Scale-Anker)
- Länge **143 m**, Höhe **25 m** (36 m ab Sohle), **13 Gewölbe à 10,8 m**, 12 Wandscheiben.
- Diese bekannten Maße dienen als **metrische Referenz** (Scale-Bar in COLMAP/RC),
  falls keine GCPs gelegt werden.

## Kamera & GSD (gerechnet, Mini 4 Pro, 48 MP = 8064×6048)
- Pixel ≈ 1,19 µm, Brennweite ≈ 6,7 mm → **GSD ≈ 0,018 cm/px pro Meter Abstand**.
- **Flugabstand 28 m → GSD ≈ 0,5 cm/px** (sehr detailliert; für Modell ideal).
- Ein Foto deckt bei 28 m ≈ **40 m breit × 30 m hoch** ab.
- Overlap 80 % längs → **Foto alle ~8 m**; 143 m Länge → **~18 Fotos je Bahn**.
- Höhen-Bahnen 75 % Überlappung → Bahnabstand ~7 m vertikal → **3-4 Höhen** decken 25 m.

## Flugbahnen (Reihenfolge)
**Luftseite (talseits — die Bogenreihe):**
1. **Bahn tief** — parallel zur Mauer, D≈28 m, Höhe ~5 m über Sohle, Kamera waagrecht. ~18 Fotos.
2. **Bahn Mitte** — Höhe ~13 m, Kamera waagrecht. ~18 Fotos.
3. **Bahn Krone** — Höhe ~25 m, Kamera leicht −15° abwärts. ~18 Fotos.
4. **Schräg links +30…45°** — Kamera entlang der Mauer angewinkelt, damit man **in die
   Nischen/Querstreben** sieht (gegen Selbstverdeckung). ~18 Fotos.
5. **Schräg rechts −30…45°** — Gegenrichtung, in die Nischen. ~18 Fotos.

**Krone & Übergänge:**
6. **Krone nadir + schräg** — über den Fahrweg (Geländer, Überlauf rechts), 70 % Overlap. ~15 Fotos.

**Wasserseite (Stausee — die konkaven Schalen):**
7. **Bahn Wasserseite** — vom Ufer/über dem Wasser, D≈30-35 m, 2 Höhen, viele Winkel
   (Wasser = Reflexe/wenig Textur → mehr Blickwinkel, ggf. **2DGS/GOF** nachträglich
   für diese Flächen). ~30-40 Fotos. **Vorsicht: GPS/RTH über Wasser.**

**Nischen-Detail (Querstreben):**
8. Je 2-3 **nahe Schräg-Fotos pro Nische** von talseits in die Gewölbe (die 5 Querriegel).
   13 Nischen → ~30-40 Fotos. Alternativ systematische Schräg-Bahn dicht an der Luftseite.

**Gesamt ≈ 250-350 Fotos** (Research-Empfehlung: lieber mehr).

## Einstellungen
- **Foto-Modus:** 48 MP, **AEB/Single**, feste Belichtung (manuell!) — gleiche Helligkeit
  über alle Fotos (bewölkt/diffus = ideal, keine harten Schatten in den Nischen).
- **Weißabgleich manuell** (fix), **Fokus auf ∞/Hyperfokal**, ISO niedrig, scharf.
- Überlappung **80 % längs / 75 % quer**; langsam fliegen, stabil, keine Bewegungsunschärfe.
- RAW wenn möglich (bessere Textur), sonst JPEG fein.

## Sicherheit & Recht (DE/EU)
- Mini 4 Pro <250 g → **Kategorie A1**; trotzdem **VLOS**, Abstand zu Personen, nicht über
  Menschenmengen. **No-Fly/Geozonen in DJI Fly prüfen** (Tal, evtl. Schutzgebiet).
- **≥5-8 m Abstand** zum Bauwerk/Bäumen; Wind im Tal beachten.
- Über Wasser: **Reflexe stören GPS-optische Sensoren** → höher fliegen, RTH-Höhe setzen.
- **3-4 Akkus** (je ~25-30 min nutzbar); der volle Satz braucht mehrere Flüge.

## Nachbearbeitung (→ Methodik §8)
1. **COLMAP** (gratis) oder RealityCapture: alle Fotos → Pose + dichte Wolke + Mesh.
2. **Metrisch skalieren** über bekannte 143 m / 10,8-m-Spannweite (Scale-Bar).
3. Wasserseiten-/dünne Partien ggf. **2DGS/GOF** separat → Mesh, einfügen.
4. **Mit LGL-DGM1-Tal fusionieren** (registrieren, Mauer-Fuß auf Talsohle).
5. Poisson-Hole-Fill → Retopo → wo Coverage fehlt: **Joch parametrisch** (v4/v5-Geometrie).
6. Output: GLB/HTML (decimiert), Druck-STL (wasserdicht), GPU-Render.

---
### Ravennaviadukt (Kurz-Variante)
Größer, Stein + filigrane Bogen-/evtl. Stahlteile → **mehr Akkus/Fotos (400+)**,
Orbits je Pfeiler + schräge Pässe in die Bogenöffnungen; **neural (2DGS/GOF) für dünne/
verdeckte Teile**, Block-Scene-Blocking wegen Größe. Sonst identische Pipeline.

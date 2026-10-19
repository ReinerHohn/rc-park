# 📐 Maßstab — VERBINDLICH: N 1:160

**Entschieden am 2026-10-07. Gilt für das gesamte Miniaturland-Projekt.**
Maßstab NICHT mehr ändern — sonst wird gekauftes/gedrucktes Material unbrauchbar.
(Zuvor kurz H0 1:87 erwogen; wegen ~8× schnellerem Druck der Wahrzeichen + 1/3 Platz auf N 1:160 gewechselt.)

## Grundregel
**1 echter Meter = 6,25 mm** (= 1000 mm ÷ 160)

| Real | Modell (÷160) | Hinweis |
|---|---|---|
| Mensch 1,80 m | ~11 mm | Preiser N / kaufen |
| Auto 4,5 m | ~28 mm | N-Autos kaufen |
| LKW/Bus 12 m | ~75 mm | |
| Hausgeschoss 3 m | ~19 mm | |
| Fahrspur 3,5 m | ~22 mm | |
| **Gleis-Spurweite** | **9 mm** | N-Norm, fix |
| Kachel 200 mm | = 32 m Landschaft | Standard-Grundkachel |
| Baum 10–20 m | 62–125 mm | DIY aus Naturmaterial |
| **Münster 116 m** | **725 mm** (~3 Segmente) | Wahrzeichen |

## Was gilt strikt 1:160
Alles Menschengemachte: **Häuser, Figuren, Fahrzeuge, Gleise, Straßen, Flieger.**
→ Gekauft: nur mit Label **„N" / „1:160"** (eher neu kaufen, Gebrauchtmarkt dünner als H0).
→ Gedruckt: STL immer mit Faktor **÷160** aus Realmaßen skalieren.

## Ausnahme: Gelände/Berge
Echter Maßstab unmöglich (Belchen 1414 m → 8,8 m Modell).
→ **Berge werden gestaucht** (Höhe + Grundfläche komprimiert, „künstlerische Perspektive").
→ Nur Objekte DARAUF (Häuser, Figuren) müssen maßstäblich sein.

## Arbeitsteilung
| Selbst machen (billig) | Drucken (custom, FDM) | Kaufen (fertig N) |
|---|---|---|
| Bäume (Naturmaterial/Seemoos) | Gelände/Berge (DEM, gestaucht) | Figuren, Tiere |
| Gras/Büsche/Boden (Streugras) | Kacheln/Fundament (200 mm) | Autos, Loks, Gleise |
| Wasser (Gießharz) | Wahrzeichen (Münster, Burgen) | Standard-Häuser (Bausätze) |

Hinweis FDM-Detailgrenze (~0,4–0,8 mm): in N wird gedrucktes Hausdetail grob — Silhouette/Massing
liest sich trotzdem. Feinkram (Figuren/Autos) NICHT drucken, sondern kaufen.

## Sweet-Spot-Szenen (max Effekt / min Aufwand)
Flach / Wiederholung / generisch / Bewegung = „sweet".
1. ✈️ Flugplatz Freiburg (flach, Kleinflieger) — auch idealer Downdraft-Absaug-Kandidat
2. ⚽ SC-Stadion (1 Sitzreihe drucken → Array, Figuren-Masse)
3. 🚂 Hbf Freiburg + Gleise (flach, Bewegung = Wow)
4. 🏰 Münsterplatz/Altstadt (nutzt Altstadt-LOD2 + Münster)
5. 🚠 Belchen-Skigebiet + Seilbahn (DEM + Seilbahn-Plan, Grün DIY)

## Wahrzeichen-Grundstock (schon im Repo, nur auf 1:160 skalieren + slicen)
Münster (Altstadt-LOD2), Altstadt, Stadttor (stadttor_gen.py), Kastelburg, Kloster St. Trudpert, Belchen (DEM).

## Staub / Wartung (Ziel: nichts per Hand)
- Haube/Vitrine = 90 % Vermeidung + dient zugleich als Besucher-Barriere (5 € Eintritt).
- HEPA-Luftreiniger im Raum + Antistatik aufs Grün.
- Optional: Downdraft-Plenum unter den Kacheln, Lochraster in flachen Zonen, Zonenventil pro Kachel,
  Blasen-von-oben + Saugen-von-unten kombiniert, automatisiert via Controller.

## Attraktion (5 € Eintritt)
Braucht: Bewegung (Zug/Seilbahn), Licht+Tag/Nacht, Dichte, Such-Gags.
Rechtlich bei Publikumsverkehr beachten: Platz, Versicherung/Haftung, Brandschutz.

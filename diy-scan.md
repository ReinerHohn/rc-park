# Eigene hochdetaillierte Modelle per Kamera + Drohne (Photogrammetrie)

> Ja — du kannst extrem detaillierte Modelle **selbst** erstellen. Genau so entstand auch der
> vorhandene Münster-Scan (RealityCapture). **Vorteil: du besitzt sie** → kommerziell für den
> Park nutzbar (löst das CC-BY-NC-Problem aus [`max-detail-scan.md`](max-detail-scan.md)).

## Software (Stand 2026)
| Tool | Kosten | Für wen |
|---|---|---|
| **RealityCapture** (= RealityScan, Epic) | **gratis** unter 1 Mio $ Umsatz | **Top-Empfehlung**: schnellstes (2–4× via GPU), Profi-Standard, baute den LAD-BW-Münster-Scan |
| **Meshroom** (AliceVision) | gratis, Open Source | Budget/Lernen; braucht NVIDIA-GPU |
| **Agisoft Metashape** | ab 179 $ | Präzision/Vermessung |
| **Polycam / KIRI Engine** | Handy/Cloud, Freemium | kleine Objekte, super einfach |

## Aufnahme — so wird's detailliert
- **200–500 Fotos** pro Objekt; jeder Punkt in **3–5 Bildern** sichtbar.
- **Überlappung 70–80 %** (Gebäude: **80 %+** in beide Richtungen).
- **≥12 MP**, scharf, **gleichmäßiges Licht** (bedeckter Himmel ideal, keine harten Schatten,
  keine laufenden Personen im Bild).
- **In Ringen umkreisen** auf mehreren Höhen (unten + schräg oben); Drohne für Dach/Turm.
- Bei 30 m Höhe ~0,8–1,2 cm/Pixel Auflösung — mehr/näher = feiner.

## ⚠️ Drohnen-Recht Deutschland (wichtig!)
- **< 250 g** (z. B. DJI Mini): **kein Führerschein** nötig — aber Regeln gelten trotzdem.
- **≥ 250 g**: EU-Kompetenznachweis **A1/A3** (25–50 €); **A2** (100–150 €) für < 50 m zu Personen.
- **Verbot: Flug über Menschenansammlungen** (§21h LuftVO) — **der volle Münsterplatz ist
  genau das** → Drohnenflug dort **praktisch nicht erlaubt**.
- Keine Überflüge von Wohngebäuden ohne Zustimmung; Datenschutz beachten.
- Genehmigung nötig für: Kontrollzonen, >120 m, Nacht, außer Sicht, über Menschen.
- **Immer vorher verbindlich prüfen: [dipul.de](https://www.dipul.de)** (offizielle Geozonen-
  Karte; Standort eingeben → zeigt Verbote/Auflagen + ob DFS-Freigabe nötig). Freiburg hat
  zudem einen Flugplatz (mögliche Kontrollzone).

### Darf die Drohne ums Freiburger Münster? → kommt auf Zeit + dipul.de an
- **Tagsüber / bei Markt (Mo–Sa): nein** — Münsterplatz = Menschenansammlung → Überflug verboten.
- **Sonntag sehr früh: evtl. machbar** — **kein Markt** (Mo–Sa), vor Öffnung/Gottesdienst
  menschenleer; mit **Kleinstdrohne < 250 g (C0)** ist das Personen-Problem dann gelöst.
- **Flugplatz Freiburg (EDTF)**: 1,5-km-Drohnensperrzone; Münster ~3 km entfernt → **wohl
  außerhalb**, aber Rettungshubschrauber/Uniklinik-Luftraum beachten.
- **Verbindlich: [dipul.de](https://www.dipul.de)** für „Freiburg Münsterplatz" prüfen —
  zeigt er keine Geozone, ist ein kurzer Flug sehr früh realistisch legal; zeigt er eine
  Sperre, braucht es eine Genehmigung (zeitunabhängig).
- Immer: keine erkennbaren Personen filmen, Kirchen-/Denkmal-Hausrecht beachten.
- **Einfacher Weg zum Üben: Kastelburg** (abgelegen, keine Menschenmassen).

### Grundregeln „wo erlaubt / wo nicht"
- **A1, < 250 g (C0):** Stadt/Wohngebiet erlaubt, über *einzelne* Unbeteiligte ok — **nie
  über Menschenansammlungen.**
- **A3 (schwerer):** nur freies Land, 150 m Abstand zu Wohn-/Gewerbe-/Erholungsgebieten.
- **Immer verboten/nur mit Genehmigung:** Menschenansammlungen, Geozonen (dipul.de),
  Flughafen-/Kontrollzonen, > 120 m, Nacht, außer Sicht, fremde Wohngrundstücke.

## Praxis: was für dich realistisch ist
- **Freiburger Münster (Innenstadt)**: Drohne **schwierig** (Menschenmassen, Airspace,
  Denkmal). Lösung: **bodennah + schräg** fotografieren, obere Partien von der **Turmgalerie**
  aus, Rest ergänzen — oder den vorhandenen Scan nur zum Testen, eigenen für den kommerziellen
  Einsatz separat erstellen/beauftragen.
- **Kastelburg Waldkirch (Ruine auf dem Hügel)**: **ideal für DIY-Drohne** — abgelegen, kaum
  Menschen, freie Sicht. **Dein perfektes erstes eigenes Scan-Projekt** (und genau dein
  Inspirations-Motiv! siehe [`startausstattung.md`](startausstattung.md)).
- **Kleine Objekte**: gehen **ganz ohne Drohne** — Handy + Drehteller + Polycam/KIRI →
  Souvenir-Master, Figuren, Details.

## Nach dem Scan → Druck
Mesh aufbereiten (Boden weg, aushöhlen, skalieren, Löcher schließen), dann wie gewohnt
slicen/drucken — siehe [`max-detail-scan.md`](max-detail-scan.md). Resin für Feinstes.

## Fazit
- **Ja, selbst machbar** → eigene, rechtssichere Max-Detail-Modelle.
- **Werkzeug**: RealityCapture (gratis) + eine **Sub-250-g-Drohne** (wenig Bürokratie) + gute Fotos.
- **Erst üben an der Kastelburg** (legal einfach), dann die kniffligeren Innenstadt-Motive.

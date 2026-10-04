# Technischer Prototyp & Konzept (Vollgas)

> Ziel: **schnell** ein vorzeigbarer technischer Prototyp — NICHT der ganze Park, sondern ein
> kleiner spielbarer Beweis: *„man fährt / fliegt / baggert auf einem gedruckten Mini-Freiburg".*
> Billig über **3D-Druck + gebrauchte eBay-Bagger/-Drohnen (reparieren)**. Fürs eigene Lernen
> und als Demo für FWTM/Partner.

## Der Prototyp (Minimal-Demo, Tisch- bis 1-Raum-Größe)
- **Gedruckte Mini-Freiburg-Platte** (1–2 Module): Straßen + ein paar Wahrzeichen (Münster-
  Teil, Häuserzeilen) — als Kulisse UND Fahr-/Flugfläche.
- **1–2 RC-Bagger** (gebraucht, ggf. repariert) + kleine Schüttgut-Ecke.
- **1–2 FPV-Micro-Drohnen** (Tiny Whoop) + kleiner Flugbereich mit 2–3 Gates + provisorischem Netz.
- optional **1 RC-Auto** auf den gedruckten Straßen.
- **Jeton/Timer** provisorisch (erstmal Handbetrieb).

→ Das reicht, um das Erlebnis zu zeigen, Video/Fotos zu machen und die Nachfrage zu testen.

## Beschaffung: eBay, günstig, reparieren
| Teil | gebraucht ca. | Hinweis |
|---|---|---|
| RC-Bagger (1:14, Huina o. ä.) | **100–300 €** | „Defekt/Bastler"-Angebote am billigsten → reparieren |
| FPV-Whoop (Cetus/Tinyhawk) | **50–100 €** | gebraucht/Set; Props/Frames spottbillig |
| RC-Auto | 30–80 € | robust, einfach |
| Ersatzteile (Props, Motoren, Servos, Zahnräder, Akkus) | je wenige € | standardisiert, überall erhältlich |
- **„Defekt/Bastler/Ersatzteilträger"** filtern = am günstigsten; typische Fixe: Akku, Motor,
  Zahnrad, Servo, Props — Schrauber-/Lötniveau.
- Das Reparieren ist **Teil des Konzepts** (spätere **gläserne Schau-Werkstatt** = Attraktion
  + hält die Flotte billig am Laufen).

## 3D-Druck-Teil (schnell)
- **Druckfarm** (2–3 günstige Drucker) parallel → Durchsatz.
- **Reihenfolge**: (1) Basisplatte/Module + **Straßen** (flach, schnell), (2) **Häuserzeilen**
  (Flat-Wall, hohl), (3) **Wahrzeichen** (Münster-Teil) als Hingucker.
- Settings/Methoden: [`3d-druck-strategie.md`](3d-druck-strategie.md) (grobe Düse, hohl,
  Flat-Wall, Detail nur wo's zählt).

## Personal-Konzept
- **Bau/Prototyp-Phase:** du + evtl. 1 Helfer. Mehr nicht.
- **Betrieb (Pop-up):**
  - **1 Aufsicht/Einweiser** während der Öffnung (v. a. für FPV: kurze Einweisung + Reset).
  - **Self-Service-Stationen** (Bagger, RC-Auto) laufen nebenbei mit, 1 Person überblickt alles.
  - **Jeton-/Zeit-Automat** statt Kasse → kein Kassierer.
  - **Wartung/Reparatur/Druck** = wenige Stunden/Woche (du oder ein **RC-/Drohnen-affiner
    Minijobber/Student** — günstig + motiviert).
  - **Skaliert mit Öffnungsstunden**: an Stoßzeiten/Wochenende 2 Kräfte, sonst 1.
- Einordnung unbemannt vs. betreut: [`risikolos-ohne-personal.md`](risikolos-ohne-personal.md)
  (Stufe A Schau-Zone unbemannt, Stufe B Self-Service semi-bemannt, Premium betreut).

## Vollgas-Fahrplan (grob)
1. **Woche 1:** 2–3 Drucker + 1 Bagger + 1–2 Whoops (eBay) bestellen; erste Druckmodule
   (Basisplatte + Straßen + 1 Häuserzeile).
2. **Woche 2:** Gebrauchtteile testen/reparieren; Mini-Platte zusammenbauen; FPV-Testflug + Gates.
3. **Woche 3–4:** Prototyp **spielbar** machen (Bagger-Ecke + FPV-Bereich + RC-Auto), Netz
   provisorisch, **Video/Fotos** fürs Demo.
4. **Danach:** Demo bei FWTM/Partner zeigen → geförderten Pop-up anstoßen (dann erst das
   Anschreiben). Zahlen dafür: [`mvp-kalkulation.md`](mvp-kalkulation.md) / `mvp-rechner.html`.

## Was du dafür schon hast
- Druck-Pipeline (MK4S + PrusaSlicer), Scan-Setup (`scan-setup/`), Münster-Modelle, der
  FPV-Bereich ([`indoor-fpv.md`](indoor-fpv.md)) und die Rechner. → Prototyp ist v. a. noch
  **eBay-Gear + ein paar Druckmodule + zusammenstecken**.

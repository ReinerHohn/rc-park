# Freiburg 3D Daten - Strategie & Quellen

## 🎯 Problem
3d.freiburg.de ist nur ein **Web-Viewer** – es gibt keinen direkten Download der Modelle.

## ✅ LÖSUNG: 3 Wege

---

## **WEG 1: 3d.freiburg.de kontaktieren & anfordern** ⭐ BEST OPTION

### Aktion:
```
Kontakt: Stadt Freiburg, Amt für Geoinformation
Email: geoinfo@stadt.freiburg.de (wahrscheinlich)
```

**Was schreiben:**
```
Betreff: Anfrage CityGML/3D-Modelle Freiburg - Kommerzielles Projekt

Hallo,

ich arbeite an einem touristischen Miniaturmodell-Projekt 
("Freiburg Miniaturwunderland") mit Rapid Prototyping 
(3D-Druck + Lasercutter).

Fragen:
1. Sind die 3D-Modelle von 3d.freiburg.de downloadbar?
   Format: CityGML, LoD2, LoD3?
2. Lizenz für kommerzielle Nutzung (Museum/Installation)?
3. Aktualität der Daten (Zeitstempel)?

Danke!
```

### ⏱️ Ergebnis: 1-2 Wochen
### 💰 Kosten: €0

---

## **WEG 2: Drohnen-Photogrammetrie (Falls Plan 1 scheitert)** ⭐ EMPFOHLEN

### Hardware:
```
DJI Mini 2 (gebraucht):     €250-350
Ersatz-Batterien:           €60
USB-C Hub + Speicher:       €30
Total:                      ~€400
```

### Software (kostenlos):
```
Meshroom (NVIDIA):          Kostenlos (automatisch)
COLMAP:                     Kostenlos
CloudCompare:               Kostenlos
```

### Workflow:
```
1. Foto-Sammlung (1-2 Tage)
   □ Innenstadt: 500-1000 Fotos von allen Seiten
   □ Highlights: Münster (100+ Fotos), Rathaus, Uni-Bib, etc.
   □ Drohne: 50m Höhe, 360° Umflüge

2. Verarbeitung (1-2 Tage CPU-Zeit)
   □ Meshroom automatisch verarbeiten
   □ Output: STL/OBJ mit hoher Qualität (LoD3+)
   
3. Post-Processing (1-2 Tage)
   □ CloudCompare: Noise-Reduction
   □ Bleaser: Mesh-Reparatur
   □ Skalierung & Normalisierung

4. Result: Hochdetaillierte Modelle (~10-20MB pro Gebäude)
   → KEINE Lizenz-Probleme
   → 100% kommerziell nutzbar
   → Bessere Qualität als CityGML
```

### ⏱️ Gesamtzeit: 4-5 Tage
### 💰 Kosten: ~€400 (Drohne einmalig)

---

## **WEG 3: Open-Source Datenquellen (Fallback)**

### 🟢 OpenStreetMap (Kostenlos, aber einfach)
```
Daten: Building Footprints + Height Tags
Format: OSM XML → STL konvertiert
Tool: OSMBuildings, Blender-Addon
Qualität: LoD1-LoD2 (flache Kästen)
Lizenz: ODbL (kommerziell OK)

Download:
https://overpass-turbo.eu/
Query: [bbox:Freiburg]; (way["building"]; relation["building"];); out geom;

Nachteil: Sehr einfache Geometrie (nur Höhe)
Vorteil: Kostenlos, alle Gebäude dabei
```

### 🟡 Gebäude-Dataset (Teilweise)
```
• Stadt Freiburg GIS-Portal (gab es mal)
• BW-Geobasis (Baden-Württemberg offiziell)
• Google Buildings (API)
```

### 🔴 Google Maps / Street View (Grauzone)
```
Technisch möglich: Bilder extrahieren → Photogrammetrie
Legal: NICHT OK für kommerzielle Nutzung
Risiko: Google kann Cease & Desist schicken
→ NICHT EMPFOHLEN
```

---

## 🚀 MEIN PLAN FÜR DICH

### **TAG 1-2: Email an 3d.freiburg.de**
```bash
# Erstelle Template-Email
cat > anfrage_3d.txt << 'EOF'
Betreff: Anfrage CityGML-Modelle für Museum-Projekt

Sehr geehrte Damen und Herren,

ich arbeite an "Freiburg Miniaturwunderland" - einer touristischen 
Installation mit 3D-gedruckten und lasergescnittenen Miniaturmodellen 
(Hybrid Rapid Prototyping).

Fragen zur 3d.freiburg.de Datenbasis:
1. Download-Zugang für CityGML-Modelle?
2. Lizenz für kommerzielle Nutzung (Museum)?
3. LoD-Level und Aktualität?
4. Masse/Präzision der Gebäude?

Ich möchte damit beginnen, Highlights wie Münster, Rathaus, 
Uni-Bibliothek hochdetailliert zu drucken.

Für Rückfragen: [deine Kontakt-Info]

Danke & Grüße
EOF

# Adresse suchen
echo "Sending to: geoinfo@stadt.freiburg.de"
```
```

### **Parallel TAG 3-7: Drohne kaufen & Test-Flüge**
```bash
# Falls Stadt nicht antwortet → Plan B aktivieren
# DJI Mini 2 kann sofort fliegen (keine Registrierung für Hobbies)

# Teste mit einem Gebäude (z.B. Parthenon-Modell analog)
# Foto-Test → Meshroom → STL
```

### **TAG 8+: Daten verarbeiten**
```
Sobald du Modelle hast (egal ob Stadt-Daten oder Drohne):
→ Alle mit freiburg_pipeline.py decomposieren
→ Produktion starten
```

---

## 💡 REALISTISCHE TIMELINE

```
❌ PESSIMISTISCH (Stadt antwortet nicht):
   TAG 1-2:  Email, keine Antwort
   TAG 3-7:  Drohne kaufen + First Test
   TAG 8-14: Foto-Sammlung (Innenstadt)
   TAG 15-28: Meshroom processing
   TAG 29+:  Production starten
   TOTAL: ~4 Wochen bis ready

✅ OPTIMISTISCH (Stadt gibt Daten):
   TAG 1-2:   Email
   TAG 8-14:  Daten Download + Konvertierung
   TAG 15+:   Production starten
   TOTAL: ~2 Wochen

⚡ HYBRID (Stadt + Drohne):
   - Stadt-Daten für Hintergrund (140 Gebäude)
   - Drohne-Fotos für Highlights (5-10 Top-Gebäude)
   - BEST QUALITY + SPEED
```

---

## 📋 SOFORT STARTEN:

### 1. EMAIL SCHREIBEN (30 min)
```bash
# Kontakte suchen:
- Stadt Freiburg Pressestelle
- Amt für Geoinformation  
- Tourismusamt
- Ordnungsamt (Geodaten)
```

### 2. DROHNE RECHERCHIEREN (1h)
```bash
# Options:
- DJI Mini 2 Second Hand: €250-350 (WillhabenAT, eBay, Facebook)
- Neu: €450
- Mieten: €80/Tag (local shops)
```

### 3. MESHROOM TESTEN (2h)
```bash
# Installiere auf deinem Computer
# Test mit Parthenon-Fotos (weniger Aufwand als vollständige Stadt)
```

---

## 🎯 ENTSCHEIDUNGSMATRIX

| | 3d.Freiburg | Drohne | OpenStreetMap |
|---|---|---|---|
| **Zeitaufwand** | Schnell | 1-2 Wochen | Schnell |
| **Qualität** | Medium (LoD2) | Hoch (LoD3+) | Niedrig |
| **Kosten** | €0 | €400 | €0 |
| **Alle Gebäude?** | Ja | Nur highlights | Ja (einfach) |
| **Kommerziell OK?** | Fraglich | ✅ Ja | ✅ Ja (ODbL) |
| **Detaillierung** | Dach-Form | Fassaden/Fenster | Nur Höhe |

---

## 🏆 MEINE EMPFEHLUNG:

**HYBRID-APPROACH:**
1. **Email an Stadt** (kein Risiko, 0 Kosten)
2. **Parallel Drohne kaufen** (€400, du brauchst sie eh für Highlights)
3. **Falls Stadt antwortet:**
   - LoD2-Modelle für Hintergrund (schnell, 140 Gebäude)
   - Drohnen-Fotos für Highlights (detailliert, 5-10 Top-Gebäude)
4. **Falls Stadt nicht antwortet:**
   - Nur Drohne nutzen (qualitativ besser sowieso!)
   - Highlight-Gebäude in top Qualität

**RESULT: Best of both worlds - schnell + hochwertig**

---

**NEXT: Sollen wir Email-Template verfeinern & absenden?**

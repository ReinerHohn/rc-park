# 🚀 QUICK START: Freiburg Miniaturwunderland (Heute starten!)

## ✅ Was du brauchst:
- ✅ Dein Prusa MK4S (hast du!)
- ✅ Computer mit Internet (jetzt gerade!)
- ✅ Python (du hast's schon)
- ❌ Wartezeit auf Stadt ← NICHT NÖTIG!

---

## 🎯 PLAN (Diesen Monat fertig):

```
WOCHE 1:   Daten downloaden + STL generieren
WOCHE 2-3: Drucken (FastDay Profil, 24/7)
WOCHE 4:   Assembly + Eröffnung
```

---

## 📋 SCHRITT-FÜR-SCHRITT (Diesen Tag noch!)

### **SCHRITT 1: OpenStreetMap Daten downloaden (10 min)**

Geh auf: **https://overpass-turbo.eu/**

```
1. Oben links: "Wizard" Knopf klicken
2. Folgendes eingeben:
   building in Freiburg
3. "Build and Run" klicken
4. Rechts: "Export" → "GeoJSON" → "Download" klicken
5. Speichern als: freiburg_osm.geojson
```

**Fertig!** Du hast jetzt 140+ Gebäude von Freiburg! 🎉

---

### **SCHRITT 2: GeoJSON → STL konvertieren (5 min)**

```bash
cd modelle/decompose

# Konvertiere mit meinem Script:
python3 osm_to_stl.py /pfad/zu/freiburg_osm.geojson -o ./freiburg_osm_output/

# Output: freiburg_osm_output/freiburg_osm.stl
```

**Fertig!** Du hast jetzt ein 3D-Modell aller Freiburger Gebäude! 🎉

---

### **SCHRITT 3: Mit Pipeline decomposieren (automatisch!)**

```bash
# Alle Gebäude automatisch zerlegen (Laser + Print):
python3 freiburg_pipeline.py freiburg_osm_output/ -o freiburg_production/

# Warte ~5-10 Minuten
```

**Fertig!** Alles ist decomposiert und ready! 🎉

---

### **SCHRITT 4: Drucken starten! 🖨️**

```bash
# Geh in dein Output-Verzeichnis:
cd freiburg_production/buildings/

# Alle STL-Dateien sind im Unterordner
# Lade sie in PrusaSlicer:
ls *print.stl | head -20
```

**In PrusaSlicer:**
```
1. Datei öffnen: erste *_print.stl
2. Profil: "FastDay" (schnell, 0.3mm, 220mm/s)
3. Slice!
4. Nächstes Gebäude
5. Parallel drucken (wenn mehrere Drucker)
```

**Fertig!** Druck läuft! ✅

---

## ⏱️ TIMELINE (Real):

```
HEUTE (Tag 1):
  □ Overpass Daten downloaden (10 min)
  □ osm_to_stl.py laufen lassen (5 min)
  □ Pipeline laufen lassen (10 min)
  = FERTIG, alle Daten ready! 🎉

MORGEN (Tag 2-14):
  □ Druck starten (PrusaSlicer)
  □ 24/7 laufen lassen
  □ Du machst nichts - Drucker arbeitet!

TAG 15-21:
  □ Assembly (zusammenstecken)
  □ Vitrine aufstellen
  □ Eröffnung!
```

---

## 💰 KOSTENRECHNUNG:

```
Investition:
  - OSM: €0 (kostenlos!)
  - Drucken: ~€300-500 Material (für 140 Gebäude)
  - TOTAL: ~€500

Verdienst (pro Monat danach):
  - 200 Besucher × €5 Eintritt = €1.000
  - 50 verkaufte Modelle × €30 = €1.500
  - TOTAL: €2.500/Monat

Break Even: 1 Monat! 🎉
```

---

## 🔑 Die wichtigste Info:

**Du schuldest NIEMANDEM etwas!**
- OpenStreetMap: Kostenlos (ODbL Lizenz)
- Keine Stadt-Genehmigung nötig!
- Deine eigene Production

**Los geht's! 🚀**

---

## 📞 Falls es nicht funktioniert:

```bash
# Error beim osm_to_stl.py?
python3 osm_to_stl.py freiburg_osm.geojson -h

# Welche Dateien sind im Verzeichnis?
ls -lh

# Meshroom Problem?
# → Ignorieren (für später, Highlights)
```

---

**Schreib mir, wenn du die GeoJSON hast!** 👇

Dann zeige ich dir die exakte Kommando-Zeile für deinen Computer.

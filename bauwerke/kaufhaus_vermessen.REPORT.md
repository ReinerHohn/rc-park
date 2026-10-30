# kaufhaus_vermessen — Vermesser-Report

**Config:** `bauwerke/kaufhaus_vermessen.json`

## AUTO (zuverlässig)
- Massing LOD2 `DEBW_0010007Tv9r`: Traufe **9.65 m**, First **21.4 m**, Dachtyp 3100 (Satteldach)
- Hülle (bbox) **25.5 × 24.6 × 21.4 m**
- Fassade: **4 Fenster** in **3 Reihen**, Arkade mit 1 Bögen
- Farben aus Foto: fassade [135, 56, 59], dach [72, 68, 85], fenster [44, 28, 33]

## TODO MENSCH (geflaggt)
- [ ] Front≈Tiefe (fast quadratische Hülle) — Frontseite am Foto bestimmen
- [ ] W/Tiefe = Hüll-Bbox (LOD2-Kantenheuristik unzuverlässig bei mehrteiligem Grundriss)
- [ ] z/w/h der Fensterreihen aus Foto-Fraktionen × Höhe GESCHÄTZT — grob
- [ ] Zierdetail (Erker/Statuen/Türmchen/Maßwerk) NICHT auto — als elements ergänzen
- [ ] welche Aufnahme frontal ist + n_axes prüfen

## Nächster Schritt
`python3 tools/bauwerk_generator.py --config bauwerke/kaufhaus_vermessen.json` → Render neben Foto prüfen → geflaggte Werte nachziehen → Juror/Validator.
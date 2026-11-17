#!/usr/bin/env python3
"""druck_farben.py <objekt> [--eintragen] - je Druckteil (tools/druck_teilung.py) die Druckfarbe vorschlagen: EIN Teil = EINE Farbe, der Rest wird gemalt.

Anlass 17.11.2026 (Nutzerziel: Bausatz in mehreren Teilen, direkt in verschiedenen Farben drucken, zusammenstecken, nur noch nachmalen). Die Druckteilung schnitt bisher
nur nach Ueberhang und Bettgroesse; welche Farbe ein Teil bekommt, stand nirgends.
Verfahren (nur Geometrie + vorhandene Fassadenbilder, nichts Objektspezifisches):
  1. Je Teil (lage/teil_NN.stl, Originallage, mm 1:Massstab) die Aussenflaeche nach Neigung aufteilen: DACH = Normale 20..80 Grad gegen die Senkrechte nach oben
     und oberhalb der halben Gebaeudehoehe; WAND = steiler als 80 Grad; Rest = waagerecht (Boden, Schnittflaechen, Simse).
  2. Art des Teils = groesserer Flaechenanteil aus DACH und WAND ("dach" ab 50 % der schraegen+senkrechten Flaeche).
  3. Farbe: dach -> mittlere Fotofarbe ist hier NICHT gemessen (Fassadenbilder zeigen nur Waende) = ANNAHME 'Dachfarbe waehlen';
     wand -> mittlere Farbe der Fassadenbilder (<daten>/fassade/ortho_fNN.png) im Hoehenbereich des Teils, getrennt nach hell (Putz) und dunkel/bunt (Stein);
     der groessere Anteil ist die Druckfarbe, der kleinere steht als 'nachmalen' dabei.
Ausgabe: Liste je Teil + audit/druck_farben.json; --eintragen schreibt 'farbe' je Teil in teilung.json.
Grenzen: eine Farbe je Teil; Stein UND Putz in einer Wand bleiben EIN Teil (der kleinere Anteil wird gemalt) - eine Trennung in Einlegeteile gibt es noch nicht.
Dachfarbe kommt nicht aus Fotos. Fassadenbilder fehlen -> nur Art, keine Farbe.
"""
import sys, os, json, glob, numpy as np, trimesh, cv2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def name_farbe(bgr):
    b, g, r = [float(x) for x in bgr]; h, s, v = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0, 0].astype(float)
    if s < 40: return "weiss/hell" if v > 170 else ("grau" if v > 90 else "dunkelgrau")
    if h < 12 or h > 165: return "rot/Sandstein" if v > 90 else "dunkelrot"
    if h < 25: return "ocker/braun" if v < 170 else "sandfarben"
    if h < 40: return "gelb/beige"
    return "gruen" if h < 90 else "blau"


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not a: sys.exit(__doc__)
    ob = a[0]; od = os.path.join(ROOT, "modelle", ob); obj = json.load(open(os.path.join(od, "objekt.json"))); sc = float(obj.get("stl_massstab", 87)) / 1000.0
    td = os.path.join(ROOT, "modelle", "stl", f"{ob}_teile"); tj = os.path.join(td, "teilung.json")
    if not os.path.exists(tj): print("keine Druckteilung (tools/druck_teilung.py", ob, ")"); return 2
    T = json.load(open(tj)); netze = {}
    for f in sorted(glob.glob(os.path.join(td, "lage", "teil_*.stl"))): m = trimesh.load(f); m.apply_scale(sc); netze[os.path.basename(f)[:-4]] = m
    if not netze: print("keine Teile in", td); return 2
    zmax = max(m.bounds[1][2] for m in netze.values()); zmin = min(m.bounds[0][2] for m in netze.values())
    fd = f"/media/oem/scan/rc-park_daten/{ob}/fassade"; fj = (sorted(glob.glob(f"/media/oem/scan/rc-park_daten/{ob}/fassade*/fassaden.json"), key=os.path.getmtime) or [""])[-1]      # das juengste Fassadenbild
    fass = []
    if fj:
        F = json.load(open(fj)); fl = F.get("fassaden", F) if isinstance(F, dict) else F; fl = fl if isinstance(fl, list) else list(fl.values())
        for i, f in enumerate(fl):
            p = os.path.join(os.path.dirname(fj), f"ortho_f{i:02d}.png"); im = cv2.imread(p, cv2.IMREAD_UNCHANGED) if os.path.exists(p) else None
            if im is not None and isinstance(f, dict) and "z" in f: fass.append((f, im))
    def wandpixel(z0, z1):
        px = []
        for f, im in fass:
            H = im.shape[0]; fz0, fz1 = f["z"]; r0 = int(np.clip((fz1 - z1) / (fz1 - fz0) * H, 0, H)); r1 = int(np.clip((fz1 - z0) / (fz1 - fz0) * H, 0, H))
            if r1 - r0 < 3: continue
            s_ = im[r0:r1]; ok = (s_[:, :, 3] > 0) if s_.shape[2] == 4 else (s_[:, :, :3].sum(2) > 0); px.append(s_[:, :, :3][ok])
        return np.concatenate(px) if px else np.zeros((0, 3), np.uint8)
    # Palette des GANZEN Gebaeudes: 3 Farbgruppen aller Wandpixel (Lab), nur Gruppen mit >= 15 % Anteil sind Druckfarben (17.11.2026: je Teil einzeln benannt gab 8 "Farben" an einem Turm aus Putz und Sandstein, darunter Himmelblau am Traufgesims)
    alle = wandpixel(zmin, zmax); pal = []
    if len(alle) > 5000:
        st = alle[np.random.default_rng(0).choice(len(alle), min(200000, len(alle)), replace=False)]; lab = cv2.cvtColor(st[None], cv2.COLOR_BGR2LAB)[0].astype(np.float32)
        _, lb, ce = cv2.kmeans(lab, 3, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS); lb = lb.ravel()
        for c in range(3):
            if (lb == c).mean() >= 0.15: pal.append(dict(lab=ce[c], bgr=[int(x) for x in np.median(st[lb == c], 0)], anteil=round(float((lb == c).mean()), 2)))
        for q in pal: q["name"] = name_farbe(q["bgr"])
        print("Palette des Gebaeudes: " + "; ".join(f"{q['name']} (BGR {q['bgr']}, {q['anteil'] * 100:.0f} %)" for q in pal))
    erg = []
    for nm, m in netze.items():
        n = m.face_normals; ar = m.area_faces; zc = m.triangles_center[:, 2]; w = np.degrees(np.arccos(np.clip(n[:, 2], -1, 1)))
        dach = float(ar[(w > 20) & (w < 80) & (zc > zmin + 0.5 * (zmax - zmin))].sum()); wand = float(ar[(w >= 80) & (w <= 100)].sum()); art = "dach" if dach > wand else "wand"
        z0, z1 = float(m.bounds[0][2]), float(m.bounds[1][2]); e = dict(teil=nm, art=art, z=[round(z0, 2), round(z1, 2)], dach_m2=round(dach, 1), wand_m2=round(wand, 1))
        if art == "dach": e.update(farbe="ANNAHME: Dachfarbe waehlen (aus Fotos nicht gemessen)", nachmalen="")
        else:
            px = wandpixel(z0, z1)
            if len(px) > 500 and pal:
                lab = cv2.cvtColor(px[::max(1, len(px) // 100000)][None], cv2.COLOR_BGR2LAB)[0].astype(np.float32); d = np.stack([np.linalg.norm(lab - q["lab"], axis=1) for q in pal], 1); zu = d.argmin(1); an = np.bincount(zu, minlength=len(pal)) / len(zu); o = np.argsort(-an)
                e.update(farbe=pal[o[0]]["name"], farbe_bgr=pal[o[0]]["bgr"], anteil=round(float(an[o[0]]), 2), nachmalen="; ".join(f"{pal[i_]['name']} ({an[i_] * 100:.0f} % der Wandflaeche)" for i_ in o[1:] if an[i_] > 0.08))
            else: e.update(farbe="unbekannt (kein Fassadenbild fuer diesen Hoehenbereich)", nachmalen="")
        erg.append(e); print(f"{nm}: {art:4s} z {z0:5.1f}..{z1:5.1f} m  Dach {dach:6.1f} m2, Wand {wand:6.1f} m2  -> drucken in: {e['farbe']}" + (f" | nachmalen: {e['nachmalen']}" if e.get("nachmalen") else ""))
    farben = sorted(set(e["farbe"] for e in erg)); print(f"{len(erg)} Teile, {len(farben)} Druckfarben: " + "; ".join(farben))
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); sys.path.insert(0, os.path.join(ROOT, "tools")); import json_sicher
    json_sicher.schreiben(os.path.join(od, "audit", "druck_farben.json"), dict(objekt=ob, teile=erg, farben=farben))
    if "--eintragen" in sys.argv:
        for t in T.get("teile", []):
            for e in erg:
                if str(t.get("name", t.get("datei", ""))).startswith(e["teil"]): t["farbe"] = e["farbe"]; t["art"] = e["art"]; t["nachmalen"] = e.get("nachmalen", "")
        json_sicher.schreiben(tj, T)
    return 0


if __name__ == "__main__":
    sys.exit(main())

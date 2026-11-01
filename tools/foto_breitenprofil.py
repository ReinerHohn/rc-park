#!/usr/bin/env python3
"""foto_breitenprofil.py - BREITE JE HOEHE IN METERN, automatisch aus Foto und Modell (kalibrierte Kamera, keine Handpicks).

Fuer jede Hoehe z wird in der Vertikalebene durch die Turmachse (senkrecht zur horizontalen Blickrichtung) ein METER-Lineal nach
links und rechts gelegt, auf das Bild projiziert und abgetastet: der aeusserste Punkt, der noch zum Bauwerk gehoert, gibt die
Halbbreite. Dasselbe am gerenderten Modell. Ergebnis: Tabelle z -> Breite Foto / Modell / Differenz in Metern, plus Beobachtungen.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_breitenprofil.py modelle/<objekt>/objekt.json <foto> [--von 20 --bis 50 --schritt 0.5] [--stl x.stl] [--eintragen]
Vorbedingung: messprotokoll/K-<foto>.json mit "kamera" (tools/foto_kalibrieren.py). Die Silhouette kommt aus der Himmelsmaske:
gemessen wird NUR, wo beide Seiten gegen Himmel stehen (sonst Nachbarhaus) - jede Zeile meldet, warum sie uebersprungen wurde.
Grenzen: Breite senkrecht zur Blickrichtung (Tiefe unsichtbar); Kamerafehler wirkt wie ein Massstabsfehler (~2 % je 1 % Brennweitenfehler).
"""
import sys, os, json, glob, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def strahlen_setup(kam):
    R, _ = cv2.Rodrigues(np.array(kam["rvec"])); t = np.array(kam["t"]); C = -R.T @ t; return R, t, C, kam["f_px"], kam["cx"], kam["cy"]

def projiziere(X, R, t, f, cx, cy):
    Xc = X @ R.T + t; return np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy], Xc[:, 2]

def quer_richtung(C, z):
    """Horizontale Richtung senkrecht zur Blickachse: darauf wird das Meter-Lineal gelegt."""
    b = np.array([-C[0], -C[1], 0.0]); b /= np.linalg.norm(b); return np.array([-b[1], b[0], 0.0])

def halbbreite(maske, R, t, f, cx, cy, C, z, vz, grenze=9.0, schritt=0.02, himmel=None, pruef_m=0.6):
    """Laeuft vom Achsenpunkt (0,0,z) in beide Richtungen auf dem Lineal nach aussen; letzter Punkt mit Maske=True je Seite."""
    H, W = maske.shape; out = []
    for s in (+1, -1):
        d = np.arange(0.0, grenze, schritt) * s
        X = np.outer(d, vz) + np.array([0, 0, z]); uv, zc = projiziere(X, R, t, f, cx, cy)
        u = np.round(uv[:, 0]).astype(int); v = np.round(uv[:, 1]).astype(int)
        gueltig = (zc > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        if not gueltig.any(): out.append(np.nan); continue
        drin = np.zeros(len(d), bool); drin[gueltig] = maske[v[gueltig], u[gueltig]]
        if not drin[0]: out.append(np.nan); continue                      # Achse selbst nicht im Objekt -> Hoehe passt nicht
        # Loecher der Punktwolke (Modellmaske) ueberbruecken: erst eine Luecke laenger als 0,12 m gilt als Kante.
        tol = max(1, int(0.12 / schritt)); ende = len(d) - 1
        i = 0
        while i < len(d):
            if drin[i]: i += 1; continue
            j = i
            while j < len(d) and not drin[j]: j += 1
            if j - i > tol: ende = i - 1; break
            i = j
        if ende >= len(d) - 1: out.append(np.nan); continue
        # ECHTE Silhouettenkante nur, wenn dahinter HIMMEL liegt. Sonst verdeckt ein Nachbarhaus/Baum die Kante
        # (Foto 000: rechte Haelfte 4,1 statt 7,4 m - das war der scheinbare Widerspruch zu Foto 030).
        if himmel is not None:
            nach = np.arange(abs(d[ende]) + 0.05, abs(d[ende]) + pruef_m, schritt) * s
            X2 = np.outer(nach, vz) + np.array([0, 0, z]); uv2, z2 = projiziere(X2, R, t, f, cx, cy)
            u2 = np.round(uv2[:, 0]).astype(int); v2 = np.round(uv2[:, 1]).astype(int)
            g2 = (z2 > 1) & (u2 >= 0) & (u2 < W) & (v2 >= 0) & (v2 < H)
            if not g2.any() or himmel[v2[g2], u2[g2]].mean() < 0.6: out.append(np.nan); continue
        out.append(abs(d[max(ende, 0)]))
    return out

def modell_maske(stl, obj, R, t, f, cx, cy, W, H, n=2500000):
    m = trimesh.load(stl)
    if obj.get("stl_einheit_mm", True): m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]])
    P, _ = trimesh.sample.sample_surface(m, n, seed=0); uv, z = projiziere(np.asarray(P), R, t, f, cx, cy)
    u = np.round(uv[:, 0]).astype(int); v = np.round(uv[:, 1]).astype(int); ok = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
    M = np.zeros((H, W), np.uint8); M[v[ok], u[ok]] = 1
    return cv2.morphologyEx(M, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)

def main():
    a = sys.argv[1:]; objp, nr = a[0], a[1]
    def opt(k, d): return float(a[a.index(k) + 1]) if k in a else d
    von, bis, schritt = opt("--von", 20.0), opt("--bis", 50.0), opt("--schritt", 0.5)
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp)))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    K = json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json")))
    if "kamera" not in K: raise SystemExit(f"K-{nr}.json hat keine Kamera - erst tools/foto_kalibrieren.py")
    R, t, C, f, cx, cy = strahlen_setup(K["kamera"])
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); H, W = im.shape[:2]
    import foto_pick as FP
    himmel = FP.himmel(im, streng=True); objekt = ~himmel                                   # "Objekt" = alles, was nicht Himmel ist (inkl. Nachbarhaeuser!)
    stl = a[a.index("--stl") + 1] if "--stl" in a else os.path.join(root, obj["stl"])
    MM = modell_maske(stl, obj, R, t, f, cx, cy, W, H)
    # KAMERA-GUETE: ohne passende Kamera ist jedes Mass Unsinn (Foto 041: RMS 530 px -> Modellbreiten 1,5 m statt 13 m).
    hoch = objekt & (np.arange(H)[:, None] < int(0.75 * H)); iou = (MM & hoch).sum() / max(1, (MM | (hoch & cv2.dilate(MM.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool))).sum())
    rms = K["kamera"].get("rms_px", float("nan"))
    print(f"  Kamera-Guete: Silhouetten-Ueberdeckung {iou:.2f}, Anker-RMS {rms:.0f} px ({100*rms/H:.1f} % der Bildhoehe)")
    if iou < 0.6:
        raise SystemExit(f"Kamera unbrauchbar fuer Metermessung (Ueberdeckung {iou:.2f} < 0,60). Erst Picks verbessern (tools/foto_pick.py) und neu kalibrieren.")
    print(f"Breitenprofil Foto {nr} (Kamera f={f:.0f} px, Standort {np.round(C,1).tolist()}, Abstand {np.hypot(*C[:2]):.1f} m, Modell {os.path.basename(stl)})")
    print("Gemessen wird die SILHOUETTENBREITE aus dieser Blickrichtung (schraeg = Diagonale), nicht die Seitenbreite - Foto und Modell sind gleich behandelt.")
    print(f"{'z (m)':>6} | {'Foto links':>10} {'rechts':>7} {'Breite':>7} | {'Modell l':>8} {'r':>6} {'Breite':>7} | {'Diff':>6}   Hinweis")
    zeilen = []
    for z in np.arange(von, bis + 1e-9, schritt):
        vz = quer_richtung(C, z)
        fl, fr = halbbreite(objekt, R, t, f, cx, cy, C, z, vz, himmel=himmel)
        ml, mr = halbbreite(MM, R, t, f, cx, cy, C, z, vz)
        fb = fl + fr if not (np.isnan(fl) or np.isnan(fr)) else np.nan
        mb = ml + mr if not (np.isnan(ml) or np.isnan(mr)) else np.nan
        einseitig = False
        if np.isnan(fb) and not np.isnan(fl) and not np.isnan(ml): fb, mb, einseitig = 2 * fl, 2 * ml, True   # nur linke Seite frei
        elif np.isnan(fb) and not np.isnan(fr) and not np.isnan(mr): fb, mb, einseitig = 2 * fr, 2 * mr, True
        # Nachbarhaus: Silhouette laeuft bis ans Lineal-Ende -> unbrauchbar
        hinweis = ""
        if np.isnan(fb): hinweis = "Foto: keine freie Kante (Nachbarhaus/Baum oder Hoehe ausserhalb)"
        elif max(fl, fr) > 8.5: hinweis = "Foto: Kante am Linealende - vermutlich Nachbarhaus"; fb = np.nan
        elif einseitig and abs(fb - mb) > 1.5:
            # Eine EINSEITIGE Messung ist halbe Information: sie darf bestaetigen, aber keine grosse Abweichung belegen -
            # die sichtbare Kante kann selbst verdeckt sein (Baum mit Himmel dahinter). Grosse Abweichungen brauchen beide Seiten oder ein zweites Foto.
            hinweis = f"Foto: nur eine Seite frei und Abweichung gross ({fb-mb:+.2f} m) - nicht belastbar, verworfen"; fb = np.nan
        elif not any(np.isnan(x) for x in (fl, fr, ml, mr)) and abs((fl - ml) - (fr - mr)) > 1.0:
            # Beide Seiten weichen GEGENSINNIG ab -> eine Kante ist verdeckt (Baum/Haus mit Himmel dahinter besteht die Himmelspruefung).
            hinweis = f"Foto: Seiten uneins (links {fl-ml:+.2f}, rechts {fr-mr:+.2f}) - eine Kante verdeckt, verworfen"; fb = np.nan
        d = fb - mb if not (np.isnan(fb) or np.isnan(mb)) else np.nan
        zeilen.append((z, fl, fr, fb, ml, mr, mb, d, hinweis))
        print(f"{z:6.1f} | {fl:10.2f} {fr:7.2f} {fb:7.2f} | {ml:8.2f} {mr:6.2f} {mb:7.2f} | {d:+6.2f}   {hinweis}")
    gut = [x for x in zeilen if not np.isnan(x[7])]
    if gut:
        dd = np.array([x[7] for x in gut]); print(f"\n{len(gut)} von {len(zeilen)} Hoehen messbar; Differenz Foto-Modell: Median {np.median(dd):+.2f} m, Spanne {dd.min():+.2f} .. {dd.max():+.2f} m")
        auff = [x for x in gut if abs(x[7]) > 0.5]
        for x in auff: print(f"  AUFFAELLIG z={x[0]:.1f} m: Foto {x[3]:.2f} m, Modell {x[6]:.2f} m ({x[7]:+.2f})")
        zonen = []                                                        # zusammenhaengende Hoehen mit gleichem Vorzeichen zusammenfassen
        for x in auff:
            if zonen and np.sign(x[7]) == np.sign(zonen[-1][-1][7]) and x[0] - zonen[-1][-1][0] <= 1.01: zonen[-1].append(x)
            else: zonen.append([x])
        zonen = [z for z in zonen if len(z) >= 2 or abs(z[0][7]) > 1.0]   # Einzelhoehen nur bei grosser Abweichung
        print(f"  {len(zonen)} zusammenhaengende Zone(n):")
        for z in zonen: print(f"    z {z[0][0]:.1f}-{z[-1][0]:.1f} m: Foto {np.mean([x[3] for x in z]):.2f} m, Modell {np.mean([x[6] for x in z]):.2f} m ({np.mean([x[7] for x in z]):+.2f} m)")
        if "--eintragen" in a and zonen:
            tp = os.path.join(root, obj["masstabelle"]); tab = json.load(open(tp)); vorhanden = {b.get("auto_id") for b in tab.get("beobachtungen_offen", [])}; neu = 0
            for z in zonen:
                aid = f"breite-{nr}-{z[0][0]:.0f}-{z[-1][0]:.0f}"
                if aid in vorhanden: continue
                tab.setdefault("beobachtungen_offen", []).append(dict(datum="auto", wer=f"foto_breitenprofil (Foto {nr}, Kamera K-{nr})", auto_id=aid,
                    text=f"Silhouettenbreite z {z[0][0]:.1f}-{z[-1][0]:.1f} m: Foto {np.mean([x[3] for x in z]):.2f} m, Modell {np.mean([x[6] for x in z]):.2f} m ({np.mean([x[7] for x in z]):+.2f} m)",
                    naechster_schritt="gegen ein zweites Foto pruefen; nur wenn beide einig sind, Ursache isolieren (tools/variante_bauen.sh) und Pruefzeile")); neu += 1
            json.dump(tab, open(tp, "w"), indent=1, ensure_ascii=False); print(f"  -> {neu} Beobachtung(en) eingetragen")
    json.dump([dict(z=float(x[0]), foto=None if np.isnan(x[3]) else float(x[3]), modell=None if np.isnan(x[6]) else float(x[6])) for x in zeilen],
              open(os.path.join(root, obj.get("audit", "audit"), f"breitenprofil_{nr}.json"), "w"), indent=1)

if __name__ == "__main__":
    main()

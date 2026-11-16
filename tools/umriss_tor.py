#!/usr/bin/env python3
"""umriss_tor.py <objekt.json> [FOTO ...] [--stl a.stl,...] [--tol 0.35] [--breite 0.6] [--eintragen] - UMRISS-TOR: Dachlinie des Modells gegen die Himmelskante im Foto.

Aufgabenliste 2 (16.11.2026). Anlass: Formfehler fand an diesem Tag nur das Auge des Nutzers (Dach gerade statt geknickt, Tuermchendach, Umgang, Bogenform).
Fuer jedes Foto (Standard: objekt.json 'neben_fotos') mit Messkamera K-<FOTO>.json:
  1. Himmelsmaske des Fotos (tools/foto_pick.himmel, mit Cache), Modell aus der Fotokamera rastern (GPU).
  2. Je Bildspalte: oberster Modellpixel gegen obersten Nicht-Himmel-Pixel. Nur Spalten, in denen ueber beiden Kanten Himmel ist (sonst verdeckt ein Vordergrund).
  3. Abweichung in METERN (Pixel x Entfernung / Brennweite). Zusammenhaengende Spaltenlaeufe mit |Abweichung| > --tol und Breite > --breite (m) = Befund:
     'Foto hoeher' (dem Modell fehlt dort etwas oder ein Baum/Nachbar steht davor) oder 'Modell hoeher' (Modell zu hoch / erfunden).
     Je Befund der 3D-Punkt der Modellkante (x, y, z) und die mittlere Abweichung.
Ausgabe: audit/umriss_<FOTO>.jpg (Foto mit Modellkante gruen, Fotokante rot, Befunde markiert - ANSEHEN), audit/umriss_tor.json; --eintragen schreibt die Befunde als beobachtungen_offen.
rc 2, wenn kein Foto geprueft werden konnte (kein neben_fotos / keine Messkamera). rc 3, wenn ein Befund 'Modell hoeher' > 2 x tol besteht (das kann kein Verdecker sein). 'Foto hoeher' ist Hinweis (Baeume, Nachbarn, Draehte geben Fehlalarm).
Grenzen: nur die Kante gegen den Himmel (Dach, Tuermchen, Giebel) - Formen vor einer Wand (Boegen, Galerie) sieht dieses Tor NICHT; Himmelsmaske kann an hellem Putz irren.
"""
import sys, os, json, glob, argparse, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as rk, foto_pick as FP
from scipy import ndimage as ndi


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fotos", nargs="*"); ap.add_argument("--stl"); ap.add_argument("--tol", type=float, default=0.35); ap.add_argument("--breite", type=float, default=0.6); ap.add_argument("--eintragen", action="store_true"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); fd = os.path.join(root, obj["fotos_dir"]); au = os.path.join(root, obj.get("audit", os.path.join(od, "audit")))
    ms = [trimesh.load(q) for q in ([os.path.join(root, obj["stl"])] + (a.stl.split(",") if a.stl else []))]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0); n_eigen = len(ms[0].faces)
    fotos = a.fotos or [e.split()[0] for e in obj.get("neben_fotos", [])]; alle = []; schlimm = False; n_gepr = 0; grob = []
    if not fotos: print("KEIN Foto zu pruefen: objekt.json hat kein 'neben_fotos' (tools/neben_fotos_waehlen.py <objekt.json> --eintragen) - das Umriss-Tor hat NICHTS geprueft"); return 2      # 16.11.2026: lief an Kettenobjekten leer mit rc 0 durch
    for nm in fotos:
        kf = os.path.join(od, "messprotokoll", "K-" + nm + ".json"); pf = glob.glob(os.path.join(fd, nm + ".*"))
        if not os.path.exists(kf) or not pf: print(f"{nm[-34:]}: keine Messkamera K-<foto>.json oder kein Foto - uebersprungen"); continue
        n_gepr += 1
        K = json.load(open(kf))["kamera"]; im = cv2.imread(pf[0]); H0, W0 = im.shape[:2]; s = min(1.0, 1600.0 / max(H0, W0)); W, H = int(W0 * s), int(H0 * s); ims = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
        try: sk = FP.himmel_cached(ims, os.path.join(au, "himmel_cache", f"umriss_{nm}.png"))
        except (Exception, SystemExit) as e: print(f"{nm[-34:]}: keine Himmelsmaske ({str(e)[:80]})"); continue      # 16.11.2026: foto_pick beendet sich per sys.exit - das brach das ganze Tor ab (rc 1, kein Ergebnis geschrieben)
        R = cv2.Rodrigues(np.array(K["rvec"]))[0]; t = np.array(K["t"]); f = K["f_px"] * s; cx, cy = K["cx"] * s, K["cy"] * s
        tiefe, fid = [np.asarray(v) for v in rk.dreiecke_rastern(mm, R, t, f, cx, cy, W, H)[:2]]; mod = (fid >= 0) & (fid < n_eigen); irgend = fid >= 0
        sk = ndi.binary_opening(sk, np.ones((5, 5))); cols = np.arange(W); hat_m = mod.any(0); ym = np.where(hat_m, mod.argmax(0), -1)
        frei = np.cumprod(sk, axis=0).astype(bool)                            # Himmel zusammenhaengend von der Bildoberkante
        yf = frei.sum(0)                                                      # erste Nicht-Himmel-Zeile je Spalte
        gueltig = hat_m & (yf > 3) & (ym > 3) & (yf < H - 2)
        gueltig &= ~np.array([irgend[:max(ym[c], 0), c].any() if hat_m[c] else True for c in cols])       # ueber der eigenen Kante kein Nachbarmodell
        z = np.where(gueltig, tiefe[np.clip(ym, 0, H - 1), cols], np.nan); dm = (ym - yf) * z / f          # + = Foto hoeher (im Modell fehlt etwas), - = Modell hoeher
        med_ = float(np.median(np.abs(dm[gueltig]))) if gueltig.any() else 9.0
        if gueltig.sum() >= 40 and 1.5 < med_ < 15.0: grob.append((nm, float(np.median(dm[gueltig]))))
        if gueltig.sum() < 40 or med_ > 1.5: print(f"{nm[-34:]}: nicht auswertbar (kein Himmel hinter dem Gebaeude oder Kamera falsch; {int(gueltig.sum())} Spalten, Median {med_:.1f} m)"); continue      # 16.11.: Fernfoto mit Stadt im Hintergrund gab 12 m 'Abweichung'
        versatz = float(np.median(dm[gueltig])); gueltig &= np.abs(dm) < 3.0                              # > 3 m ist nie ein fehlendes Bauteil, sondern ein Nachbardach/Baum vor oder hinter der Kante
        dm = np.where(gueltig, dm, 0.0); mpc = np.nanmedian(z[gueltig]) / f if gueltig.any() else 1.0; mal = ims.copy(); bef = []
        for c in cols[gueltig]: cv2.circle(mal, (int(c), int(ym[c])), 1, (60, 220, 60), -1); cv2.circle(mal, (int(c), int(yf[c])), 1, (40, 40, 240), -1)
        for vz, name in ((1, "Foto hoeher (Modell fehlt etwas / Verdecker)"), (-1, "Modell hoeher (zu hoch / erfunden)")):
            lab, n = ndi.label(ndi.binary_closing(gueltig & (vz * dm > a.tol), np.ones(5)))
            for li, sl in enumerate(ndi.find_objects(lab), 1):
                cs = np.arange(sl[0].start, sl[0].stop); cs = cs[lab[cs] == li]; br = len(cs) * mpc
                if br < a.breite: continue
                cmid = int(cs[len(cs) // 2]); zc = float(tiefe[ym[cmid], cmid]); Xc = np.array([(cmid - cx) / f * zc, (ym[cmid] - cy) / f * zc, zc]); Xw = R.T @ (Xc - t); mit = float(np.median(dm[cs]))
                bef.append(dict(foto=nm, art=name, abweichung_m=round(float(mit), 2), breite_m=round(float(br), 2), xyz=[round(float(v), 2) for v in Xw]))
                cv2.rectangle(mal, (int(cs[0]), int(min(ym[cs].min(), yf[cs].min())) - 6), (int(cs[-1]), int(max(ym[cs].max(), yf[cs].max())) + 6), (0, 200, 255) if vz > 0 else (255, 0, 255), 2)
                if len(cs) > 0.6 * gueltig.sum(): bef[-1]["art"] = "GANZE KANTE versetzt - Kamera dieses Fotos oder Gesamthoehe pruefen"; continue
                if vz < 0 and abs(mit) > 2 * a.tol: schlimm = True
        cv2.imwrite(os.path.join(au, f"umriss_{nm}.jpg"), mal); alle += bef
        print(f"{nm[-34:]}: {int(gueltig.sum())} Spalten verglichen ({gueltig.sum() * mpc:.0f} m Kante), Abweichung Median {np.median(np.abs(dm[gueltig])) if gueltig.any() else float('nan'):.2f} m, {len(bef)} Befunde")
        for b in bef: print(f"    {b['art'][:13]:13s} {b['abweichung_m']:+.2f} m ueber {b['breite_m']:.1f} m bei x {b['xyz'][0]} y {b['xyz'][1]} z {b['xyz'][2]}")
    if len(grob) >= 2 and (all(g[1] > 0 for g in grob) or all(g[1] < 0 for g in grob)):      # 16.11.2026: am Kettenturm sagten 2 Fotos unabhaengig 5 m - einzeln galt jedes als "nicht auswertbar", das Tor meldete nichts
        mv = float(np.median([g[1] for g in grob])); alle.append(dict(foto=grob[0][0], art="GANZE DACHLINIE versetzt (" + ("Foto hoeher: Dach/Aufbau fehlt oder zu niedrig" if mv > 0 else "Modell hoeher") + f"), {len(grob)} Fotos einig", abweichung_m=round(mv, 2), breite_m=0.0, xyz=[0.0, 0.0, 0.0]))
        print(f"GROB: {len(grob)} Fotos zeigen dieselbe Richtung, Median {mv:+.1f} m - Dachform/Gesamthoehe des Modells pruefen (" + ", ".join(f"{g[0][-20:]} {g[1]:+.1f}" for g in grob) + ")"); schlimm = True
    json.dump(dict(tol_m=a.tol, befunde=alle), open(os.path.join(au, "umriss_tor.json"), "w"), indent=1, ensure_ascii=False)
    if a.eintragen and alle:
        mt = os.path.join(root, obj["masstabelle"]); d = json.load(open(mt)); d["beobachtungen_offen"] = [b for b in d.get("beobachtungen_offen", []) if b.get("auto_id", "").split("-")[0] != "umriss"]
        for i, b in enumerate(alle): d["beobachtungen_offen"].append(dict(datum="auto", wer="umriss_tor", auto_id=f"umriss-{b['foto']}-{i}", text=f"{b['art']}: {b['abweichung_m']:+.2f} m ueber {b['breite_m']} m bei {b['xyz']} (Foto {b['foto']})", naechster_schritt="am Bild audit/umriss_<foto>.jpg pruefen; echt = messen und bauen, Verdecker = verwerfen"))
        json.dump(d, open(mt, "w"), indent=1, ensure_ascii=False)
    if not n_gepr: print("KEIN Foto geprueft - das Umriss-Tor hat nichts belegt"); return 2
    return 3 if schlimm else 0


if __name__ == "__main__":
    sys.exit(main())

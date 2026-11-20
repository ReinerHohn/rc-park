#!/usr/bin/env python3
"""vorbauten_bauplan.py - Vorbauten (Erker, Galerie, Vordach, Balkon) aus dem Ebenen-Sweep in eine BAULISTE uebersetzen (20.11.2026).

Bisher endete der Sweep (tools/fassade_tiefe.py -> vorbauten_fNN.json + tiefe_fNN.npz) als 'Vorschlag' - kein Generator las ihn,
der Schwabentor-Erker existierte nur im Hand-Generator schwab_v3 (Nutzer 20.11.: "Wir haben hier manuell alles gebastelt ... und jetzt
haben wir diese Faehigkeit verloren"). Dieses Werkzeug schliesst die Luecke; bauteile.vorbauten_aus_json baut die Liste.

Regeln (generisch, keine Objektwerte):
  KOERPER  = Kandidat 'Vorbau' mit ebener Front: w_median >= --w_min, Streuung w_p90 - w_p10 <= --streuung, Flaeche >= --min_m2,
             Front nicht am Rand des Suchbereichs (w_p90 <= Grenze - 0,25 m).
             (Durchblick durch eine Tordurchfahrt streut ueber > 1 m - faellt hier heraus; die Oeffnung ist Sache von oeffnungen_wandbild.)
  DACH     = Kandidat 'Vorbau' direkt ueber einem Koerper (Unterkante bis --dach_abstand ueber dessen Oberkante, u-Ueberlappung >= 50 %),
             darf streuen (schraege Dachflaeche).
  GESTALT  = Hoehenfeld je Zelle (--raster, Standard 0,2 m) aus der Sweep-Tiefe (nur 'gut'-Zellen, Median), im Rechteck Koerper..Dach;
             Zellen ohne sichere Tiefe = Median ihrer Zeile, sonst Wand (0). 3x3-Median gegen Einzelausreisser. Kein Spiegeln, kein Erfinden:
             was die Fotos nicht sicher sehen, steht nicht vor der Wand.
Aufruf:  vorbauten_bauplan.py <objekt.json> <fassaden-ordner> [--aus audit/vorbauten_auto.json]
Ausgabe: JSON {fassaden: [{id, o, d, n, w_wand, gruppen: [{koerper, dach, u0, z1, raster, w: [[...]] }]}]} + Bild audit/vorbauten_auto.jpg
rc 0 = mindestens ein Vorbau, rc 3 = keiner (kein Fehler).
"""
import sys, os, json, argparse, numpy as np
from scipy import ndimage as ndi


def gruppen_bilden(kand, w_min, streuung, min_m2, dach_abstand, w_grenze=9.0):
    vb = [k for k in kand if k.get("art") == "Vorbau"]
    # w_grenze: Front bis 0,25 m an den Rand des Suchbereichs = kein echtes Kostenminimum (Himmel, Dachkante, Bildrand; Schwabentor f03 20.11.: zwei Scheinkoerper bei +2,2 m)
    koerper = [k for k in vb if k["w_median"] >= w_min and (k["w_p90"] - k["w_p10"]) <= streuung and k["flaeche_m2"] >= min_m2 and k["w_p90"] <= w_grenze - 0.25]
    out = []
    for k in sorted(koerper, key=lambda k: -k["flaeche_m2"]):
        if any(not (k["u1"] <= g["u0"] or k["u0"] >= g["u1"] or k["z1"] <= g["z0"] or k["z0"] >= g["z1"]) for g in out): continue   # liegt in einer groesseren Gruppe
        daecher = [d for d in vb if d is not k and k["z1"] - 0.5 <= d["z0"] <= k["z1"] + dach_abstand and d["w_median"] >= w_min
                   and (min(k["u1"], d["u1"]) - max(k["u0"], d["u0"])) >= 0.5 * (d["u1"] - d["u0"])]
        dach = max(daecher, key=lambda d: d["flaeche_m2"]) if daecher else None
        g = dict(koerper=k, dach=dach, u0=min(k["u0"], dach["u0"]) if dach else k["u0"], u1=max(k["u1"], dach["u1"]) if dach else k["u1"],
                 z0=k["z0"], z1=dach["z1"] if dach else k["z1"])
        out.append(g)
    return out


def hoehenfeld(npz, w_wand, g, raster, w_max):
    w = npz["w"] - w_wand; gut = npz["gut"]; c = float(npz["zelle"]); u0n = float(npz["u0"]); z1n = float(npz["z1"])
    H, W = w.shape; nu = max(1, int(round((g["u1"] - g["u0"]) / raster))); nz = max(1, int(round((g["z1"] - g["z0"]) / raster)))
    feld = np.full((nz, nu), np.nan)
    for r in range(nz):
        za, zb = g["z1"] - (r + 1) * raster, g["z1"] - r * raster; i0, i1 = int((z1n - zb) / c), int(np.ceil((z1n - za) / c))
        for s in range(nu):
            ua, ub = g["u0"] + s * raster, g["u0"] + (s + 1) * raster; j0, j1 = int((ua - u0n) / c), int(np.ceil((ub - u0n) / c))
            i0_, i1_, j0_, j1_ = max(i0, 0), min(i1, H), max(j0, 0), min(j1, W)
            if i1_ <= i0_ or j1_ <= j0_: continue
            m = gut[i0_:i1_, j0_:j1_]
            if m.mean() >= 0.25: feld[r, s] = float(np.median(w[i0_:i1_, j0_:j1_][m]))
    for r in range(nz):                                         # Luecken: Median der Zeile (eine Erkerfront ist zeilenweise eben), sonst Wand
        z_ = feld[r]; ok = np.isfinite(z_)
        if ok.sum() >= max(2, 0.3 * nu): z_[~ok] = np.median(z_[ok])
    feld = np.nan_to_num(feld, nan=0.0)
    feld = ndi.median_filter(feld, 3, mode="nearest")
    return np.clip(feld, 0.0, w_max)


def galerie_messen(feld, g, raster, w_wand, fein=None, fid=None):
    """21.11.2026 (Nutzer: "der Erker ist doch generiert beim guten Fall ... hier voelliger Wurstelschrott"): wie im Hand-Generator schwab_v3 nur MASSE messen und das
    bewaehrte Bauteil bauteile.Wand.galerie bauen lassen. Aus dem Hoehenfeld (Zeile 0 = oben): Bruestungsband = unterstes zusammenhaengendes Zeilenband, in dem >= 50 % der
    Spalten >= halbe Frontausladung haben (z_boden, z_holm); Pfosten = Spaltenhaufen zwischen Holm und Dach mit Ausladung in >= 25 % der Zeilen (Enden zaehlen immer);
    Dach = Gruppe 'dach' (Traufe = Unterkante, Ausladung = Median). Streben aus dem feinen Wandbild: dunkle senkrechte Linien im 1-m-Band unter der Bruestung, regelmaessiger
    Abstand (Median der starken Spitzen), Fussende = tiefster Punkt, bis zu dem die Linie dunkel bleibt. Kein Ergebnis -> None (dann Hoehenfeld)."""
    k = g["koerper"]; front = k["w_median"]; nz, nu = feld.shape; zr = lambda i: g["z1"] - (i + 0.5) * raster
    voll = (feld >= 0.5 * front).mean(1); band = [i for i in range(nz) if voll[i] >= 0.5 and k["z0"] - 0.3 <= zr(i) <= k["z1"] + 0.3]
    if len(band) < 3: return None
    i_unten = max(band); i_oben = i_unten
    while i_oben - 1 in band: i_oben -= 1
    z_boden, z_holm = zr(i_unten) - raster / 2, zr(i_oben) + raster / 2
    if z_holm - z_boden < 0.6: return None
    d_ = g.get("dach"); z_dach = d_["z0"] if d_ else min(g["z1"], z_holm + 3.0)
    oben = [i for i in range(nz) if z_holm + 0.3 < zr(i) < z_dach - 0.1]; spalten = []
    if oben:
        anteil = (feld[oben] >= 0.5 * front).mean(0); j = 0
        while j < nu:
            if anteil[j] >= 0.25:
                e = j
                while e + 1 < nu and anteil[e + 1] >= 0.25: e += 1
                spalten.append(g["u0"] + (0.5 * (j + e) + 0.5) * raster); j = e + 1
            else: j += 1
    u0, u1 = g["koerper"]["u0"], g["koerper"]["u1"]; pf = sorted(set([u0 + 0.11, u1 - 0.11] + [u for u in spalten if u0 + 0.6 < u < u1 - 0.6]))
    erg = dict(u0=u0, u1=u1, z_boden=round(z_boden, 2), z_holm=round(z_holm, 2), z_dach=round(z_dach, 2), w=round(w_wand + front, 2), w_wand=round(w_wand - 0.05, 2),
               pfosten=[round(u, 2) for u in pf], streben=0, z_fuss=None, quelle="Hoehenfeld Ebenen-Sweep (Bruestungsband, Pfostenspalten), Dach aus Gruppe 'dach'")
    if fein and fid:
        try:
            import cv2
            from scipy.signal import find_peaks
            R_ = {f["id"]: f for f in json.load(open(os.path.join(fein, "fassaden.json")))["fassaden"]}[fid]["raster"]; c = float(R_["zelle"])
            im = cv2.imread(os.path.join(fein, f"ortho_{fid}_fein.png"), 0); gr_ = cv2.imread(os.path.join(fein, f"ortho_{fid}.png"), 0)
            if gr_ is not None: im = np.where(im > 0, im, cv2.resize(gr_, (im.shape[1], im.shape[0])))
            px = lambda u: int((u - R_["u0"]) / c); py = lambda z: int((R_["z1"] - z) / c)
            B = im[py(z_boden):py(z_boden - 1.0), px(u0):px(u1)].astype(float); p = np.convolve(B.mean(0), np.ones(9) / 9, "same"); d = np.convolve(p, np.ones(81) / 81, "same") - p
            pk, pr = find_peaks(d, height=0.5 * d.max(), distance=int(0.5 / c))
            if len(pk) >= 3:
                ab = float(np.median(np.diff(pk))) * c; us = u0 + pk[0] * c; st = [us + i * ab for i in range(int((u1 - us) / ab) + 1)]
                fuss = []
                for u in st:
                    sp = im[py(z_boden):py(z_boden - 3.0), max(0, px(u) - 4):px(u) + 5].astype(float).mean(1); hell = np.median(im[py(z_boden):py(z_boden - 3.0), px(u0):px(u1)])
                    dunkel = sp < 0.75 * hell; n_ = 0
                    while n_ < len(dunkel) and dunkel[n_]: n_ += 1
                    if n_ > 10: fuss.append(z_boden - n_ * c)
                erg.update(streben=len(st), streben_u=[round(u, 2) for u in st], streben_abstand=round(ab, 2), z_fuss=round(float(np.median(fuss)), 2) if fuss else round(z_boden - 1.0, 2),
                           streben_quelle=f"feines Wandbild {fid}: {len(pk)} starke dunkle Linien unter der Bruestung, Abstand {ab:.2f} m" + ("" if fuss else "; Fussende ANNAHME 1,0 m"))
        except Exception as e_: erg["streben_fehler"] = str(e_)[:120]
    if d_:
        wt = w_wand + d_["w_median"]; erg["vordach"] = dict(z_traufe=round(d_["z0"], 2), w_traufe=round(wt, 2), z_anschluss=round(d_["z1"] + 0.6 * d_["w_median"], 2), u0=d_["u0"], u1=d_["u1"],
                                                          annahme="Anschluss an der Wand = Oberkante Dachband + 0,6 x Ausladung (Dachneigung ~31 Grad, nicht gemessen); Breite = Galerie + 0,1 m")
    return erg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner"); ap.add_argument("--aus")
    ap.add_argument("--w_min", type=float, default=0.5, help="Mindest-Ausladung eines Vorbaus (m)")
    ap.add_argument("--streuung", type=float, default=0.8, help="max. w_p90 - w_p10 einer Koerperfront (m); 21.11.: Erker 0,5-0,6 (zweiter Lauf genau 0,60 -> fiel bei 0,6 heraus), Durchblick Torbogen 1,5")
    ap.add_argument("--min_m2", type=float, default=3.0); ap.add_argument("--dach_abstand", type=float, default=6.0)
    ap.add_argument("--raster", type=float, default=0.2, help="Bauraster (m); 0,2 m = 2,3 mm in H0"); ap.add_argument("--fein", help="fassade_fein-Ordner (Streben zaehlen im 1-cm-Wandbild)")
    a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "vorbauten_auto.json")
    F = json.load(open(os.path.join(a.ordner, "fassaden.json")))["fassaden"]; erg = []; bilder = []
    for i, f in enumerate(F):
        vj, nz = os.path.join(a.ordner, f"vorbauten_f{i:02d}.json"), os.path.join(a.ordner, f"tiefe_f{i:02d}.npz")
        if not (os.path.exists(vj) and os.path.exists(nz)): print(f"f{i:02d}: kein Sweep"); continue
        v = json.load(open(vj))
        if not v.get("belastbar"): print(f"f{i:02d}: Sweep nicht belastbar - kein Vorbau"); continue
        npz = np.load(nz); gr = gruppen_bilden(v["kandidaten"], a.w_min, a.streuung, a.min_m2, a.dach_abstand, w_grenze=v["w_bereich"][1] - v["wand_versatz_m"]); fg = []
        for g in gr:
            w_max = max(g["koerper"]["w_p90"], g["dach"]["w_p90"] if g["dach"] else 0.0)
            feld = hoehenfeld(npz, v["wand_versatz_m"], g, a.raster, w_max)
            if (feld > a.w_min * 0.5).mean() < 0.2: print(f"f{i:02d}: Gruppe u {g['u0']:.2f}..{g['u1']:.2f} - Hoehenfeld fast leer, verworfen"); continue
            fg.append(dict(u0=g["u0"], u1=g["u1"], z0=g["z0"], z1=g["z1"], raster=a.raster, w=np.round(feld, 2).tolist(),
                           koerper={k: g["koerper"][k] for k in ("u0", "u1", "z0", "z1", "w_median", "w_p10", "w_p90", "flaeche_m2")},
                           dach={k: g["dach"][k] for k in ("u0", "u1", "z0", "z1", "w_median", "w_p10", "w_p90", "flaeche_m2")} if g["dach"] else None))
            ga = galerie_messen(feld, g, a.raster, v["wand_versatz_m"], fein=a.fein, fid=f.get("id", f"f{i:02d}"))
            if ga: fg[-1]["galerie"] = ga; print(f"f{i:02d}: GALERIE u {ga['u0']:.2f}..{ga['u1']:.2f}, Boden {ga['z_boden']:.2f}, Holm {ga['z_holm']:.2f}, Dach {ga['z_dach']:.2f}, Ausladung {ga['w']:.2f} m, {len(ga['pfosten'])} Pfosten, {ga['streben']} Streben (Fuss {ga['z_fuss']})")
            print(f"f{i:02d}: VORBAU u {g['u0']:.2f}..{g['u1']:.2f}  z {g['z0']:.2f}..{g['z1']:.2f}  Front w {g['koerper']['w_median']:+.2f} m"
                  + (f"  Dach z {g['dach']['z0']:.2f}..{g['dach']['z1']:.2f} w {g['dach']['w_median']:+.2f}" if g["dach"] else "  (ohne Dach)")
                  + f"  max {feld.max():.2f} m")
            bilder.append((f"f{i:02d}", feld))
        if fg: erg.append(dict(id=f.get("id", f"f{i:02d}"), nr=i, o=f["o"], d=f["d"], n=f["n"], w_wand=v["wand_versatz_m"], gruppen=fg))
    os.makedirs(os.path.dirname(aus), exist_ok=True)
    json.dump(dict(quelle="tools/vorbauten_bauplan.py aus fassade_tiefe (Ebenen-Sweep) - Hoehenfeld je Zelle", fassaden=erg), open(aus, "w"), indent=0)
    if bilder:
        import cv2
        kach = []
        for nm, fe in bilder:
            im = cv2.applyColorMap(np.clip(fe / max(fe.max(), 0.1) * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
            im = cv2.resize(im, (im.shape[1] * 12, im.shape[0] * 12), interpolation=cv2.INTER_NEAREST); cv2.putText(im, nm, (5, 20), 0, 0.6, (255, 255, 255), 2); kach.append(im)
        hm = max(k.shape[0] for k in kach); cv2.imwrite(aus[:-5] + ".jpg", np.hstack([np.pad(k, ((0, hm - k.shape[0]), (0, 8), (0, 0))) for k in kach]))
    n = sum(len(e["gruppen"]) for e in erg); print(f"-> {aus}: {n} Vorbau-Gruppen"); return 0 if n else 3


if __name__ == "__main__": sys.exit(main())

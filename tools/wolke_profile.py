#!/usr/bin/env python3
"""wolke_profile.py - GENERISCH: Formprofile je Hoehenschicht aus der dichten Fotowolke (+ DOM1) -> Profiltabelle fuer den Generator
und automatische Pruefzeilen in der Masstabelle (Register AR). Keine Handuebertragung einzelner Zahlen mehr.

Zwei Koerperklassen:
  zentral   Dach/Helm auf der Bauwerksachse: je Schicht Breite quer (p2-p98 der Wolke, Fassadenebene = verlaesslich) minus Rand-
            zuschlag; Tiefe aus dem DOM1-Rohraster (Schnitt durch den Peak, Zellmaxima -> Halbbreite je Hoehe), weil die Wolkentiefe
            einseitiger Netze driftet (Register AO). Ergebnis: Profil [(z, breite_tiefe, breite_quer)].
  abseits   Rundkoerper neben der Achse (Ecktuermchen): je Schicht Kreisfit (kleinste Quadrate) an die Punkte eines Quadranten ->
            (z, Durchmesser, Achse). Ergebnis je Quadrant und gemittelt.
Ausgabe: modelle/<objekt>/profile_<seite>.json; --pruefungen schreibt/aktualisiert Pruefzeilen 'Profil ...' in der Masstabelle
(Soll = Wolkenwert +- Toleranz, quelltyp sfm_bodenanker, idempotent ueber den Namen). --generator schreibt die Profile in
modelle/<objekt>/profile_generator.json, das der Generator als Loft liest.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_profile.py modelle/<objekt>/objekt.json nord --pruefungen --generator
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bauteile import seite_achsen

def kreis(X):
    A = np.c_[2 * X[:, 0], 2 * X[:, 1], np.ones(len(X))]; b = (X ** 2).sum(1); c = np.linalg.lstsq(A, b, rcond=None)[0]
    return float(c[0]), float(c[1]), float(np.sqrt(max(c[2] + c[0] ** 2 + c[1] ** 2, 0.0)))

def dom1_halbbreite(obj, od, achse, z, r_max=6.5):
    """DOM1-Rohraster: entlang der Achse durch die Peakzelle die Entfernung (m) vom Peak, bei der die Zellhoehe unter z faellt
    (linear interpoliert) - gemittelt ueber beide Richtungen. Zellmaxima -> Halbbreite um ~0,5 m zu gross; wird abgezogen."""
    L = obj["laser"]; W = np.load(L["fenster_npy"]) - float(L["gelaende_m"]); pr = np.unravel_index(np.nanargmax(W), W.shape)
    # Modell-x (Sued) = Raster-Zeile nach unten? Achsrichtung aus anker3d: xhat_utm (-0,27,-0,96) ~ Sued = Zeile+; y Ost = Spalte+
    prof = W[pr[0], :] if achse == "y" else W[:, pr[1]]; i0 = pr[1] if achse == "y" else pr[0]
    hs = []
    for d in (1, -1):
        prev = prof[i0]; dist = None
        for k in range(1, int(r_max) + 2):
            v = prof[i0 + d * k]
            if v < z: dist = (k - 1) + (prev - z) / max(prev - v, 1e-6); break
            prev = v
        if dist is not None: hs.append(dist)
    return (float(np.mean(hs)) - 0.5) if hs else float("nan")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--dicht"); ap.add_argument("--dz", type=float, default=0.5)
    ap.add_argument("--zentral-z", nargs=2, type=float, default=[36.0, 57.0]); ap.add_argument("--abseits-z", nargs=2, type=float, default=[30.5, 44.5])
    ap.add_argument("--abseits-min-r", type=float, default=2.8, help="Quadrantenpunkte: |quer| > ... (Tuermchen liegen aussen)")
    ap.add_argument("--achsstreifen", type=float, default=1.5, help="halbe Breite quer des Achsstreifens fuer die Front"); ap.add_argument("--frontfenster", type=float, default=0.8, help="Tiefenfenster um die Front fuer die Breite quer"); ap.add_argument("--rand", type=float, default=0.2, help="Abzug vom p2-p98-Mass quer (Wolkenstreuung; Gratbereiche duenn besetzt -> klein halten)")
    ap.add_argument("--pruefungen", action="store_true"); ap.add_argument("--generator", action="store_true"); ap.add_argument("--toleranz", type=float, default=0.5); ap.add_argument("--tief-quelle", default="wolke", help="wolke | silhouette:<foto> (Silhouettenprofil eines fernen Seitenfotos, messprotokoll/M-<foto>-S1.json: misst die volle Tiefe direkt, ohne Symmetrie- und Driftannahme)"); ap.add_argument("--tuerm-rand", type=float, default=0.8, help="Hoehenabstand ueber den Tuermchenspitzen, ab dem die Wolkenbreite ohne Tuermchen gilt")
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); s = a.seite.lower()
    P = np.load(os.path.join(od, a.dicht or f"sfm/dicht_{s}_entzerrt.npy")).astype(float)
    tief, sgn, quer = seite_achsen(s)
    it = 0 if tief == "x" else 1; iq = 1 - it
    # ---- zentral
    zentral = []
    for z in np.arange(a.zentral_z[0], a.zentral_z[1], a.dz):
        # Front der sichtbaren Flaeche: Median der Tiefe im Achsstreifen |quer| < 1,5 -> Tiefe des (symmetrischen) Koerpers = 2 * |Front|
        ks = (P[:, 2] >= z) & (P[:, 2] < z + a.dz) & (np.abs(P[:, iq]) < a.achsstreifen) & (sgn * P[:, it] > 0.3) & (sgn * P[:, it] < 7.0)
        if ks.sum() < 10: continue
        xf = float(np.median(sgn * P[ks, it]))
        # Pass 1: Breite quer im ENGEN Frontfenster (|tief - Front| < 0,2) - nur als Dachmaske fuer den Tuermchen-Fit; endgueltig in Pass 2
        k = (P[:, 2] >= z) & (P[:, 2] < z + a.dz) & (np.abs(sgn * P[:, it] - xf) < 0.2)
        bq = float(np.percentile(P[k, iq], 98) - np.percentile(P[k, iq], 2)) if k.sum() >= 15 else 0.0
        hq = dom1_halbbreite(obj, od, quer, z + a.dz / 2); ht = dom1_halbbreite(obj, od, tief, z + a.dz / 2)
        zentral.append(dict(z=round(float(z + a.dz / 2), 2), front_tief=round(xf, 2), breite_tief_wolke=round(2 * xf, 2), breite_quer_wolke=round(bq, 2), breite_quer_dom1=(round(2 * hq, 2) if hq == hq else None), breite_tief_dom1=(round(2 * ht, 2) if ht == ht else None), n=int(k.sum()), n_front=int(ks.sum())))
    print(f"Zentralkoerper ({len(zentral)} Schichten): z | Front tief | Tiefe Wolke | Breite quer Wolke (Frontfenster) | DOM1 quer | DOM1 tief")
    for r in zentral: print(f"  {r['z']:5.2f}  {r['front_tief']:5.2f}  {r['breite_tief_wolke']:5.2f}  {r['breite_quer_wolke']:5.2f}  {r['breite_quer_dom1'] if r['breite_quer_dom1'] is not None else '  -  '}  {r['breite_tief_dom1'] if r['breite_tief_dom1'] is not None else '  -  '}")
    def front_bei(z):
        """(halbe Breite quer, Front tief) des Zentralkoerpers bei z (naechste Schichten), sonst None"""
        c = [r for r in zentral if abs(r["z"] - z) <= a.dz]
        return (max(r["breite_quer_wolke"] for r in c) / 2, float(np.median([r["front_tief"] for r in c]))) if c else None
    # ---- abseits (zwei Quadranten der sichtbaren Seite)
    abseits = {}
    for qs in (-1, 1):
        rows = []
        for z in np.arange(a.abseits_z[0], a.abseits_z[1], a.dz):
            fb = front_bei(z + a.dz / 2)
            k = (np.abs(P[:, 2] - (z + a.dz / 2)) < a.dz / 2) & (np.sign(P[:, iq]) == qs) & (np.abs(P[:, iq]) > a.abseits_min_r) & (sgn * P[:, it] > 2.5) & (sgn * P[:, it] < 8.5)
            if fb: k &= ~((np.abs(P[:, iq]) <= fb[0] + 0.3) & (np.abs(sgn * P[:, it] - fb[1]) < 0.8))   # Dachflaechen-Punkte (in Dachbreite UND Dachtiefe) ausblenden
            if k.sum() < 12: continue
            X = P[k][:, :2]; cx, cy, r = kreis(X)
            for _ in range(2):                                            # robust: 20 % groesste Residuen verwerfen, neu fitten
                res = np.abs(np.hypot(X[:, 0] - cx, X[:, 1] - cy) - r); X = X[res <= np.percentile(res, 80)]
                if len(X) < 8: break
                cx, cy, r = kreis(X)
            if r > 2.5 or r < 0.1: continue
            rows.append(dict(z=round(float(z + a.dz / 2), 2), d=round(2 * r, 2), achse=[round(cx, 2), round(cy, 2)], n=int(k.sum()), n_fit=int(len(X))))
        abseits[("quer+" if qs > 0 else "quer-")] = rows
    # Mittelprofil ueber beide Quadranten (robust: Median je z)
    zs = sorted({r["z"] for rows in abseits.values() for r in rows}); mittel = []
    for z in zs:
        ds = [r["d"] for rows in abseits.values() for r in rows if r["z"] == z]; ax = [abs(r["achse"][it]) for rows in abseits.values() for r in rows if r["z"] == z]; aq = [abs(r["achse"][iq]) for rows in abseits.values() for r in rows if r["z"] == z]
        if len(ds) < len(abseits): continue                                 # nur Schichten, die in BEIDEN Quadranten gefittet wurden
        mittel.append(dict(z=z, d=round(float(np.median(ds)), 2), achse_tief=round(float(np.median(ax)), 2), achse_quer=round(float(np.median(aq)), 2), n=len(ds)))
    print(f"\nAbseits-Koerper (Ecktuermchen), Mittel beider Quadranten: z | d | |Achse tief| | |Achse quer|")
    for r in mittel: print(f"  {r['z']:5.2f}  {r['d']:4.2f}  {r['achse_tief']:4.2f}  {r['achse_quer']:4.2f}  (n={r['n']})")
    # DOM1-Flaechenkurve (Zellen > z im 9-m-Umkreis um den Peak) -> Tiefe = Flaeche / Breite_quer (Zellmaxima, grob +-0,5 m)
    L = obj["laser"]; Wd = np.load(L["fenster_npy"]) - float(L["gelaende_m"]); pr = np.unravel_index(np.nanargmax(Wd), Wd.shape)
    yy, xx = np.mgrid[:Wd.shape[0], :Wd.shape[1]]; dd = np.hypot(yy - pr[0], xx - pr[1])
    tuerm_top = max([r["z"] for r in mittel], default=0.0)
    # Tuermchen-Modell aus den Fits: Koerper = Median d der grossen Schichten (d >= 0,8 dmax), Helm = Kegel durch die Spitze (TUERM_SPITZE),
    # Steigung aus allen Schichten oberhalb des Koerpers (kleinste Quadrate mit festem Nullpunkt an der Spitze) - robust gegen einzelne Fehlfits
    from bauteile import lade_masse
    _m = lade_masse(os.path.join(od, "masse.json")); _sp = obj.get("koerper", {}).get("tuermchen", {}).get("spitze", "TUERM_SPITZE")
    TS = float(sum(_m[t] if t in _m else float(t) for t in str(_sp).split("+")))            # Spitze des Abseits-Koerpers aus objekt.json['koerper']
    kegel = None
    if mittel:
        dmax = max(r["d"] for r in mittel); koerper = [r for r in mittel if r["d"] >= 0.8 * dmax]; d_k = float(np.median([r["d"] for r in koerper]))
        at_ = float(np.median([r["achse_tief"] for r in koerper])); aq_ = float(np.median([r["achse_quer"] for r in koerper]))
        # Durchmesser je Schicht aus der AUSSENKANTE der Wolke in der Tuermchenzone (p3 der Tiefe, |quer - Achse| < d_k): d = 2 (Kante - Achse).
        # Robuster als Kreisfits an Teilboegen (die oberhalb des Koerpers streuen): die Kante ist eine Silhouette wie im Seitenfoto.
        kante = []
        for z in np.arange(a.abseits_z[0], TS, a.dz):
            k = (np.abs(P[:, 2] - (z + a.dz / 2)) < a.dz / 2) & (np.abs(np.abs(P[:, iq]) - aq_) < d_k) & (sgn * P[:, it] > at_) & (sgn * P[:, it] < at_ + 4.0)
            if k.sum() < 15: continue
            kante.append((round(float(z + a.dz / 2), 2), round(float(2 * (np.percentile(sgn * P[k, it], 97) - at_)), 2), int(k.sum())))
        d_kante_k = float(np.median([d for z, d, n in kante if d >= 0.8 * max(d for _, d, _ in kante)])) if kante else d_k
        # Knick = letzte Schicht von unten, deren Kantendurchmesser noch >= 90 % des Koerperwerts ist; Kegel = Gerade durch die Spitze ueber den Schichten darueber
        ueber = [(z, d) for z, d, n in kante if d < 0.9 * d_kante_k and z > min(z for z, d, n in kante if d >= 0.9 * d_kante_k)]
        unter = [z for z, d, n in kante if d >= 0.9 * d_kante_k]
        if len(ueber) >= 3:
            h = np.array([TS - z for z, d in ueber]); dd_ = np.array([d for z, d in ueber]); k_ = float((dd_ * h).sum() / (h * h).sum())
            z_knick = TS - d_kante_k / k_
            kegel = dict(steigung_d_je_m=round(k_, 3), d_koerper=round(d_kante_k, 2), z_knick=round(z_knick, 2), z_koerper_oben=max(unter), spitze=TS, schichten=len(ueber), verfahren="Aussenkante der Wolke (p97 Tiefe) in der Tuermchenzone", kante=kante)
            print(f"\nTuermchen-Modell (Aussenkante): Koerper d {d_kante_k:.2f} (Kreisfit-Koerper {d_k:.2f}) bis {max(unter)} m, Kegel d = {k_:.3f} x (Spitze - z) aus {len(ueber)} Schichten -> Knick bei {z_knick:.2f} m, d bei Spitze-2 m = {2 * k_:.2f}, bei Spitze-4 m = {4 * k_:.2f}")
            print("   Kante je Schicht:", " ".join(f"{z}:{d}" for z, d, n in kante if z >= 36))
    def d_tuerm(z):
        if kegel: return kegel["d_koerper"] if z <= kegel["z_knick"] else max(kegel["steigung_d_je_m"] * (TS - z), 0.0)
        c = [r["d"] for r in mittel if r["z"] >= z]; return max(c) if c else 0.0
    achse_q = float(np.median([r["achse_quer"] for r in mittel])) if mittel else None
    widerspruch = []; sil = None
    if a.tief_quelle.startswith("silhouette:"):
        foto = a.tief_quelle.split(":", 1)[1]; Sp = json.load(open(os.path.join(od, "messprotokoll", f"M-{foto}-S1.json")))
        assert Sp.get("achse") == tief, f"Silhouette {foto} misst Achse {Sp.get('achse')}, hier ist tief = {tief}"
        sz = np.array([q["z"] for q in Sp["profil"]]); sb = np.array([q["breite"] for q in Sp["profil"]]); sil = (foto, sz, sb)
        print(f"Tiefe aus Silhouette Foto {foto} ({len(sz)} Schichten, {Sp['px_je_m']} px/m); Wolkenfront nur Vergleich")
    for r in zentral:
        # Pass 2: Breite quer im WEITEN Frontfenster (+-0,8 m Tiefe: Wolkenstreuung, Gratbereiche) ohne die Tuermchenzone (|quer| um die Tuermchenachse +-1,6 bis ueber die Spitzen)
        k = (P[:, 2] >= r["z"] - a.dz / 2) & (P[:, 2] < r["z"] + a.dz / 2) & (np.abs(sgn * P[:, it] - r["front_tief"]) < a.frontfenster)
        if achse_q is not None and r["z"] <= TS + a.tuerm_rand: k &= np.abs(np.abs(P[:, iq]) - achse_q) > d_tuerm(r["z"]) / 2 + 0.3   # Tuermchenzone (Achse +- d/2 + 0,3) ausblenden
        if k.sum() >= 15: r["breite_quer_wolke"] = round(float(np.percentile(P[k, iq], 98) - np.percentile(P[k, iq], 2)) - a.rand, 2); r["n"] = int(k.sum())
        r["dom1_flaeche"] = int(((Wd > r["z"]) & (dd <= 9)).sum())
        r["breite_quer"] = r["breite_quer_wolke"]
        r["breite_tief"] = r["breite_tief_wolke"]                     # Wolkenfront (entzerrt, an LoD2-Wand gehaengt); DOM1 nur Vergleichsspalte
        if sil and sil[1].min() <= r["z"] <= sil[1].max():
            r["breite_tief_silhouette"] = round(float(np.interp(r["z"], sil[1], sil[2])), 2); r["breite_tief"] = r["breite_tief_silhouette"]
        if r["breite_tief_dom1"] and abs(r["breite_tief_dom1"] - r["breite_tief"]) > 1.0: widerspruch.append(r["z"])
    rampe = None
    if sil:
        AN = json.load(open(os.path.join(od, "anker3d.json")))["anker"]; z_ank = max(v["xyz"][2] for v in AN.values() if v.get("quelltyp") == "lod2")   # oberste LoD2-Hoehe = bis hierhin ist die Wolke an amtliche Flaechen gehaengt (Wandebene/Kanten)
        paare = [(r["z"], r["breite_tief_silhouette"] - r["breite_tief_wolke"]) for r in zentral if "breite_tief_silhouette" in r]
        if paare:
            zz_ = np.array([q[0] for q in paare]) - z_ank; dd_ = np.array([q[1] for q in paare]); k_ = float((zz_ * dd_).sum() / (zz_ * zz_).sum())
            rampe = dict(z_anker=round(z_ank, 2), m_je_m=round(k_, 4), median=round(float(np.median(dd_)), 2), spanne=[round(float(dd_.min()), 2), round(float(dd_.max()), 2)], schichten=len(paare))
            print(f"  Silhouette minus Wolkenfront: Median {rampe['median']:+.2f} m, Spanne {rampe['spanne'][0]:+.2f}..{rampe['spanne'][1]:+.2f} -> Tiefen-Offset der einseitigen Wolke als Rampe {k_:+.4f} m je m ueber der obersten amtlichen Ankerhoehe {z_ank} m; unterhalb der Silhouette so korrigiert")
            for r in zentral:
                if "breite_tief_silhouette" not in r and r["z"] > z_ank: r["breite_tief_korrigiert"] = round(r["breite_tief_wolke"] + k_ * (r["z"] - z_ank), 2); r["breite_tief"] = r["breite_tief_korrigiert"]
    print("\nDachprofil (quer aus der Wolke; tief aus %s; Wolkenfront roh/DOM1 zum Vergleich; tief ggf. driftkorrigiert):" % ("Silhouette " + sil[0] if sil else "Wolkenfront"))
    for r in zentral: print(f"  z {r['z']:5.2f}  quer {r['breite_quer']:5.2f}  tief {r['breite_tief']:5.2f}   Wolkenfront {r['breite_tief_wolke']}  DOM1 quer {r['breite_quer_dom1']} tief {r['breite_tief_dom1']}  (DOM1-Flaeche {r['dom1_flaeche']} Zellen)")
    # Traufe des Zentralkoerpers: breiteste Front-Schicht im Traufbereich (Tropfkante) - ins Generatorprofil, damit der Ueberstand kein Handmass ist
    traufe = None
    kand = [r for r in zentral if r["z"] < a.zentral_z[0] + 1.5]
    if kand:
        rt = max(kand, key=lambda r: r["breite_tief"]); traufe = dict(z=rt["z"], tief=rt["breite_tief"], quer=rt["breite_quer"], quelle="breiteste Frontschicht im Traufbereich (Tropfkante)" + (", Tiefe driftkorrigiert" if rampe else ""))
        print(f"  Traufe: z {traufe['z']} tief {traufe['tief']} quer {traufe['quer']}")
    if widerspruch: print(f"  DOM1-Tiefe weicht in {len(widerspruch)} Schichten > 1 m ab ({widerspruch[0]}..{widerspruch[-1]} m): Laser-Zellmaxima auf steilen Helmflaechen (Quellen-Blindheit), Schiedsrichter = fernes Seitenfoto (tools/foto_silhouette_profil.py)")
    out = dict(seite=s, dz=a.dz, zentral=zentral, abseits=abseits, abseits_mittel=mittel, tuerm_top=tuerm_top, tuerm_kegel=kegel, dom1_widerspruch_z=widerspruch, hinweis="Tiefe = 2 x Wolkenfront im Achsstreifen, Breite quer = p2-p98 im Frontfenster minus Rand; DOM1-Schnitte nur Vergleich (blind auf steilen Flaechen); Abseits: robuster Kreisfit je Schicht ausserhalb der Dachbreite")
    json.dump(out, open(os.path.join(od, f"profile_{s}.json"), "w"), indent=1, ensure_ascii=False); print("\ngeschrieben:", os.path.join(od, f"profile_{s}.json"))
    if a.generator:
        # Generatorprofil: zentral (z, tief, quer) - quer aus Wolke, tief aus DOM1 falls vorhanden sonst quer * (DOM1-Verhaeltnis der naechsten Schicht); abseits (z, d)
        dach = [[r["z"], r["breite_tief"], round(r["breite_quer"], 2)] for r in zentral if r["breite_tief"] and r["breite_quer"] > 1.0]
        # Monotonie (Helm wird nach oben nicht breiter): von OBEN nach unten laufendes Maximum - die oberen Schichten (Silhouette) gelten, tiefere werden hochgezogen
        for i in range(len(dach) - 2, -1, -1): dach[i][1] = max(dach[i][1], dach[i + 1][1] - 0.05); dach[i][2] = max(dach[i][2], dach[i + 1][2] - 0.05)
        if kegel:   # Koerper (Zylinder, Median d) + Kegel durch die Spitze - statt der einzelnen, oberhalb des Koerpers streuenden Fits
            tuerm = [[r["z"], kegel["d_koerper"]] for r in mittel if r["z"] <= kegel["z_knick"]] + [[round(float(z), 2), round(d_tuerm(z), 2)] for z in np.arange(kegel["z_knick"], TS - 0.4, a.dz)]
        else: tuerm = [[r["z"], r["d"]] for r in mittel]
        dmax = max(r["d"] for r in mittel); koerper = [r for r in mittel if r["d"] >= 0.8 * dmax]     # Achse aus den Schichten des Erkerkoerpers (grosser Bogen, stabiler Fit)
        achse = dict(tief=float(np.median([r["achse_tief"] for r in koerper])), quer=float(np.median([r["achse_quer"] for r in koerper])), aus_schichten=[koerper[0]["z"], koerper[-1]["z"]])
        json.dump(dict(seite=s, dach_profil=dach, dach_traufe=traufe, tiefen_rampe=rampe, tief_quelle=a.tief_quelle, tuerm_profil=tuerm, tuerm_kegel=kegel, tuerm_achse=achse, quelle="tools/wolke_profile.py (Register AR): Wolkenfront (tief), Frontfenster (quer), robuster Kreisfit + Kegelgerade durch die Spitze (Tuermchen)"), open(os.path.join(od, "profile_generator.json"), "w"), indent=1, ensure_ascii=False)
        print("geschrieben:", os.path.join(od, "profile_generator.json"), f"({len(dach)} Dachschichten, {len(tuerm)} Tuermchenschichten, Achse {achse})")
    if a.pruefungen:
        tp = os.path.join(od, "masstabelle.json"); from masstabelle_io import sperren, schreiben; _L = sperren(tp); T = json.load(open(tp)); neu = 0
        gesetzt = set()
        def setze(name, wert, soll, quelle, merkmal, messung):
            nonlocal neu
            gesetzt.add(name)
            T["messungen"][wert.replace("_durchmesser", "")] = {k: v for k, v in messung.items() if k != "feld"}   # dict-Messung -> Pruefstand haengt _durchmesser an
            for pr in T["pruefungen"]:
                if pr["name"] == name:
                    if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "wolke_profile.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                    pr["wert"] = wert
                    return
            T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=quelle, quelltyp="sfm_bodenanker", merkmal=merkmal, massstab="LoD2-Eckkanten + Wandebene", protokoll=f"profile_{s}.json")); neu += 1
        # Dach: Breite quer bei 4 Stuetzhoehen (alle 4 m ab 41), Tuermchen: Durchmesser bei 3 Hoehen
        for r in zentral:
            if abs((r["z"] - 41.25) % 4.0) < 1e-6 or abs(r["z"] - 53.25) < 1e-6:
                if r["z"] <= tuerm_top + a.tuerm_rand: continue                                   # dort stecken die Tuermchen in der Breite
                z = r["z"]; b = r["breite_quer_wolke"]
                setze(f"Profil Dach: Breite {quer} bei {z:.1f} m (m)", f"profil_dach_{int(z * 10)}", [round(b - a.toleranz, 2), round(b + a.toleranz, 2)], f"wolke_profile.py (Register AR): Wolkenbreite {quer} p2-p98 minus {a.rand} m = {b} bei {z} m; DOM1-Flaeche {r['dom1_flaeche']} Zellen", "schlankheit", {"typ": "ausdehnung_streifen", "z": z, "achse": quer, "quer_max": 2.5})
        # Tuermchen: Durchmesser = Ausdehnung des Schnitts in Tiefenrichtung in einem Fenster seitlich der Dachbreite (Glockenstock/Kragdach
        # verschmelzen im Schnitt mit dem Erker, deshalb kein Schwerpunkt-Filter); Soll aus dem Tuermchen-Modell (Koerper + Kegelgerade)
        if mittel and kegel:
            at, aq = float(np.median([r["achse_tief"] for r in mittel])), achse_q; dk = kegel["d_koerper"]
            fen = {("x0" if it == 0 else "y0"): round(sgn * at - 0.7 * dk, 2), ("x1" if it == 0 else "y1"): round(sgn * at + 0.7 * dk, 2),
                   ("y0" if it == 0 else "x0"): round(aq - 0.3 * dk, 2), ("y1" if it == 0 else "x1"): round(aq + 0.7 * dk, 2)}
            if sgn < 0: fen[("x0" if it == 0 else "y0")], fen[("x1" if it == 0 else "y1")] = min(fen[("x0" if it == 0 else "y0")], fen[("x1" if it == 0 else "y1")]), max(fen[("x0" if it == 0 else "y0")], fen[("x1" if it == 0 else "y1")])
            for z in (34.25, 37.75, 40.25, TS - 2.0):
                dz_ = d_tuerm(z); fits = [r["d"] for r in mittel if abs(r["z"] - z) < 0.3]
                setze(f"Profil Ecktuermchen: Durchmesser bei {z:.2f} m (m)", f"profil_tuerm_{int(round(z * 100))}", [round(dz_ - 0.4, 2), round(dz_ + 0.4, 2)], f"wolke_profile.py (Register AR): Tuermchen-Modell Koerper d {dk} bis {kegel['z_knick']} m, Kegel {kegel['steigung_d_je_m']} m/m zur Spitze {TS} -> d {dz_:.2f} bei {z} m (Einzelfit dort: {fits}); Fenster seitlich der Dachbreite", "schlankheit", {"typ": "schnitt_ausdehnung", "z": round(float(z), 2), **fen, "achse": tief})
        # Profil-Pruefungen frueherer Laeufe, die es in diesem Lauf nicht mehr gibt (andere Stuetzhoehen/Rand), entfernen - sie gehoeren dem Werkzeug
        eigene = ("Profil Dach: ", "Profil Ecktuermchen: ")                                   # nur eigene Zeilen; 'Profil Dach (Foto ...)' gehoert foto_silhouette_profil.py
        alt = [pr for pr in T["pruefungen"] if pr["name"].startswith(eigene) and pr["name"] not in gesetzt]
        T["pruefungen"] = [pr for pr in T["pruefungen"] if not (pr["name"].startswith(eigene) and pr["name"] not in gesetzt)]
        for pr in alt: T["messungen"].pop(pr["wert"].replace("_durchmesser", ""), None)
        schreiben(tp, T, _L); print(f"Masstabelle: {neu} neue Profil-Pruefungen, {len(alt)} veraltete entfernt (bestehende aktualisiert)")

if __name__ == "__main__":
    main()

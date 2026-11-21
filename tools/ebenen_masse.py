#!/usr/bin/env python3
"""ebenen_masse.py - MASSE eines Vorbaus aus den dichten triangulierten Fotokanten seiner Ebene (21.11.2026, Kettenstufe 'bauplan', Schritt 2 der Schleife).

Nutzer 21.11.: "So wenig allgemeine Bauteile wie moeglich. Untersuche, wie weit du aus Kanten triangulieren kannst, und was nicht moeglich ist, wird aus allgemeinen
Bauteilen gebaut ... durch das Kantenerkennen muessen wir umso genauer werden mit Massen." Untersuchung Erker Schwabentor (Logbuch 21.11.): waagrechte Kanten, Breite,
Ausladung, Konsolenzahl und Strebenneigung gehen; Pfosten nur als Lage; Dachflaeche nicht.
Eingang: <ebenen>/ebenen.json (tools/ebenen_bauplan.py, Ebenen der Art 'vorbau') + audit/vorbauten_auto.json (Grobband aus dem Sweep als SUCHFENSTER).
Je Vorbau (alles aus Kantenpunkten, keine Stueckzahl vorgegeben):
  front       haeufigste Tiefe der Kantenpunkte vor der Wand (Histogramm 5 cm) -> Ausladung = Median der Punkte +-0,2 m um die Spitze.
  kasten      waagrechte Kantenlinien in Fronttiefe (z-Histogramm 2 cm), die mindestens halb so lang belegt sind wie die laengste Linie, im Grobband +-0,5 m: unterste = Unterkante, oberste = Oberkante (Holm);
              Breite = belegter u-Bereich der Unterkante.
  konsolen    kurze Kantenstuecke (0,15-0,9 m) in Fronttiefe auf der naechsten Linie bis 0,5 m UNTER der Unterkante: Zahl, Lage, Unterkante.
  streben     Kantenpunkte unter den Konsolen zwischen Wand und Front: Fusspunkt z = 5. Perzentil der Punkte ZWISCHEN Wand und Front (0,12 m .. Ausladung - 0,2 m) -> Strebe vom Wandfuss zur Konsole (gerade = ANNAHME).
  pfosten     senkrechte Kantenhaufen in Fronttiefe ueber der Oberkante (u-Histogramm 2 cm, Haufen < 0,5 m zusammen): Lage; Breite nur bei zwei belegten Flanken, sonst None.
Schreibt je Gruppe 'kanten_mass' in audit/vorbauten_auto.json (bauteile.vorbauten_aus_json baut daraus) und audit/ebenen_masse.json. rc 0 / rc 3 = kein Vorbau mit Kantenmass.
"""
import sys, os, json, argparse, numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks


def stuecke(u, lo, hi, zelle=0.05, min_p=5):
    h, e = np.histogram(u, bins=np.arange(lo, hi + zelle, zelle)); L, _ = ndi.label(ndi.binary_closing(h >= min_p, np.ones(3)))
    return [(float(e[s[0].start]), float(e[s[0].stop]), int(h[s[0]].sum())) for s in ndi.find_objects(L)]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ebenen"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); vp = os.path.join(od, "audit", "vorbauten_auto.json")
    if not os.path.exists(vp): print("keine vorbauten_auto.json"); return 3
    VB = json.load(open(vp)); EJ = {e["id"]: e for e in json.load(open(os.path.join(a.ebenen, "ebenen.json")))["ebenen"]}; n_ok = 0; ber = {}
    for F in VB.get("fassaden", []):
        for k, g in enumerate(F["gruppen"]):
            g.pop("kanten_mass", None); e = EJ.get(f"f{F['nr']:02d}_vb{k}")
            if not e or not e.get("sweep") or not os.path.exists(e["sweep"]): continue
            o = np.array(e["o"]); d = np.array(e["d"]); n = np.array(e["n"]); ww = float(e.get("w_wand", 0.0)); P = np.load(e["sweep"])["P"].astype(float)
            ew = EJ.get(f"f{F['nr']:02d}_wand")                                # Kanten der Wandebene derselben Fassade dazu (Strebenfuesse liegen an der Wand, ausserhalb des Bands der Vorbau-Ebene)
            if ew and ew.get("sweep") and os.path.exists(ew["sweep"]): P = np.vstack([P, np.load(ew["sweep"])["P"].astype(float)])
            u = (P[:, :2] - o) @ d; z = P[:, 2]; w = (P[:, :2] - o) @ n - ww; u0, u1, z0, z1 = e["zone"]; ok = (u >= u0) & (u <= u1) & (z >= z0) & (z <= z1); u, z, w = u[ok], z[ok], w[ok]
            vorn = w > 0.4
            if vorn.sum() < 500: continue
            h, ed = np.histogram(w[vorn], bins=np.arange(0.4, max(w.max(), 0.6) + 0.05, 0.05)); wp = float(ed[h.argmax()] + 0.025); fr = np.abs(w - wp) < 0.2; aus = float(np.median(w[fr]))
            km = dict(ausladung=round(aus, 2), ausladung_p10_p90=[round(float(x), 2) for x in np.percentile(w[fr], [10, 90])], punkte_front=int(fr.sum()), quelle=f"dichte triangulierte Fotokanten {e['id']} ({len(u)} Punkte)")
            zb = np.arange(z0, z1 + 0.02, 0.02); hz, _ = np.histogram(z[fr], bins=zb); s = np.convolve(hz, np.ones(3), "same"); pk, _ = find_peaks(s, height=max(40, 0.01 * fr.sum()), distance=6)
            breite_zone = g["koerper"]["u1"] - g["koerper"]["u0"]; lin = []
            for p in pk:
                zl = float(zb[p] + 0.01); st = stuecke(u[fr & (np.abs(z - zl) < 0.05)], u0, u1); bel = sum(b_ - a_ for a_, b_, _ in st)
                lin.append(dict(z=round(zl, 2), belegt_m=round(bel, 2), stuecke=[[round(a_, 2), round(b_, 2)] for a_, b_, _ in st], punkte=int(s[p])))
            km["linien"] = [dict(z=l_["z"], belegt_m=l_["belegt_m"], punkte=l_["punkte"]) for l_ in lin]
            gz0, gz1 = g["koerper"]["z0"] - 0.5, g["koerper"]["z1"] + 0.5; imb = [l_ for l_ in lin if gz0 <= l_["z"] <= gz1]; bmax = max([l_["belegt_m"] for l_ in imb] or [0.0]); voll = [l_ for l_ in imb if l_["belegt_m"] >= 0.5 * bmax and bmax >= 0.4 * breite_zone]      # 'durchgehend' = mindestens halb so lang belegt wie die laengste Linie im Grobband (Holm Schwabentor: 4,85 von 7,6 m - Draehte/Schatten unterbrechen)
            if len(voll) >= 2:
                lu, lo_ = min(voll, key=lambda l_: l_["z"]), max(voll, key=lambda l_: l_["z"])
                if lo_["z"] - lu["z"] >= 0.5:
                    us = [x for s_ in lu["stuecke"] for x in s_]; km["kasten"] = dict(z_unten=lu["z"], z_oben=lo_["z"], u0=round(min(us), 2), u1=round(max(us), 2), breite=round(max(us) - min(us), 2))
                    kl = [l_ for l_ in lin if lu["z"] - 0.5 <= l_["z"] < lu["z"] - 0.08]
                    if kl:
                        kb = max(kl, key=lambda l_: l_["punkte"]); ks = [s_ for s_ in kb["stuecke"] if 0.15 <= s_[1] - s_[0] <= 0.9 and km["kasten"]["u0"] - 0.2 <= s_[0] and s_[1] <= km["kasten"]["u1"] + 0.2]
                        if len(ks) >= 2:
                            km["konsolen"] = dict(z_unten=kb["z"], anzahl=len(ks), lage=[[s_[0], s_[1]] for s_ in ks], abstand=round(float(np.median(np.diff([0.5 * (s_[0] + s_[1]) for s_ in ks]))), 2))
                            mu = np.zeros(len(u), bool)
                            for s_ in ks: mu |= (u > s_[0] - 0.3) & (u < s_[1] + 0.3)
                            q = mu & (z < kb["z"] - 0.1) & (w > 0.12) & (w < aus - 0.2)      # ZWISCHEN Wand und Front (Wandkanten = Fugen zaehlen nicht; 1. Fassung nahm sie mit: Fuss 7,95 = Zonenrand)
                            if q.sum() >= 50:
                                prof = [[round(float(za), 2), round(float(np.median(w[mu & (z >= za) & (z < za + 0.4) & (w > -0.3) & (w < aus + 0.2)])), 2)] for za in np.arange(max(z0, kb["z"] - 2.4), kb["z"], 0.4) if (mu & (z >= za) & (z < za + 0.4) & (w > -0.3) & (w < aus + 0.2)).sum() >= 30]
                                km["streben"] = dict(z_fuss=round(float(np.percentile(z[q], 5)), 2), punkte_zwischen=int(q.sum()), tiefenprofil=prof, hinweis="gerade Strebe vom Wandfuss zur Konsole = ANNAHME (Profil zeigt die gemessene Tiefe je Hoehenband)")
                    mz = fr & (z > lo_["z"] + 0.2) & (z < (g.get("galerie") or {}).get("z_dach", g["z1"]) - 0.1)
                    if mz.sum() >= 100:
                        hu, eu = np.histogram(u[mz], bins=np.arange(u0, u1 + 0.02, 0.02)); su = np.convolve(hu, np.ones(3), "same"); pu, _ = find_peaks(su, height=max(25, 0.04 * mz.sum()), distance=4); pf = []
                        for x in eu[pu] + 0.01:
                            if pf and x - pf[-1][-1] < 0.5: pf[-1].append(float(x))
                            else: pf.append([float(x)])
                        km["pfosten"] = [dict(u=round(float(np.mean(c_)), 2), breite=round(c_[-1] - c_[0], 2) if len(c_) >= 2 and c_[-1] - c_[0] >= 0.12 else None, punkte=int(((np.abs(u - np.mean(c_)) < 0.3) & mz).sum())) for c_ in pf]
            if "kasten" in km:
                g["kanten_mass"] = km; n_ok += 1; K_ = km["kasten"]
                print(f"{e['id']}: KASTEN z {K_['z_unten']:.2f}..{K_['z_oben']:.2f}, u {K_['u0']:.2f}..{K_['u1']:.2f} (Breite {K_['breite']:.2f}), Ausladung {km['ausladung']:.2f} m"
                      + (f" | {km['konsolen']['anzahl']} Konsolen (Abstand {km['konsolen']['abstand']:.2f}, Unterkante {km['konsolen']['z_unten']:.2f})" if "konsolen" in km else " | keine Konsolen")
                      + (f" | Strebenfuss z {km['streben']['z_fuss']:.2f}" if "streben" in km else "") + (f" | Pfosten bei u {[p_['u'] for p_ in km['pfosten']]}" if km.get("pfosten") else " | keine Pfosten belegt"))
            else: print(f"{e['id']}: kein Kasten aus Kanten (volle Linien im Grobband: {[l_['z'] for l_ in voll]}) - Grobmass bleibt")
            ber[e["id"]] = km
    json.dump(VB, open(vp, "w"), indent=0); json.dump(ber, open(os.path.join(od, "audit", "ebenen_masse.json"), "w"), indent=1)
    return 0 if n_ok else 3


if __name__ == "__main__": sys.exit(main())

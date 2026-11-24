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


def laeufe(c, t, luecke=3, min_lauf=3):
    """Laeufe von Zellen mit c >= t (Luecken bis 'luecke' Zellen ueberbrueckt), nur Laeufe mit >= min_lauf belegten Zellen: [(i0, i1 inkl.)]."""
    r, a, b, n, gap = [], None, None, 0, 0
    for i, v in enumerate(c):
        if v >= t:
            if a is None: a, n = i, 0
            b, n, gap = i, n + 1, 0
        elif a is not None:
            gap += 1
            if gap > luecke:
                if n >= min_lauf: r.append((a, b))
                a, gap = None, 0
    if a is not None and n >= min_lauf: r.append((a, b))
    return r


def bruestung(u, z, w, aus, K, zelle=0.02, d_min=0.08):
    """BRUESTUNG zwischen Unter- und Oberkante des Kastens aus den Kantenpunkten (24.11.2026, Befund 1122w: Bild-Vorbau Nord als glatter Kasten, im Foto
    Schwelle + vorstehender Holm, dazwischen offen mit Knaggen an den Pfosten, Wandgemaelde dahinter sichtbar). Alles in Tiefe w ab der Wand.
      holm      zusammenhaengendes Kantenband (Luecken <= 3 Zellen) von der Oberkante abwaerts -> Unterkante; Front = Median-Tiefe der Punkte vor der Bruestungsfront,
                Rueckseite = Median der Holmpunkte hinter der Front (Unterkanten-Ansicht), sonst None.
      schwelle  erster dichter Lauf ueber Unterkante + 0,15 m = Oberkante der Schwelle (dort beginnt das Feld); keiner -> None (Bau nimmt ANNAHME).
      knaggen   u-Haufen der Frontpunkte im Feld (10 cm, >= 3 Punkte je Zelle, Luecken <= 0,3 m, >= 20 Punkte, <= 1,2 m breit).
      offen     Feld ohne waagrechte Frontkanten ausserhalb der Knaggen (belegt < 15 % der Breite) und >= 2 Knaggen - geschlossene Bretter mit Fugen/Kanten bleiben Kasten.
    Mindestdicke d_min (0,08 m = 0,9 mm in H0, Druckmindestmass 0,8 mm)."""
    zu, zo, ua, ub = K["z_unten"], K["z_oben"], K["u0"], K["u1"]
    if zo - zu < 0.6: return None
    mu = (u > ua - 0.1) & (u < ub + 0.1); m = mu & (w > 0.4) & (w < aus + 0.4)
    zb = np.arange(zo - 0.45, zo + 0.06 + 1e-6, zelle); c, _ = np.histogram(z[m], bins=zb); io = int(min(len(c) - 1, (zo - zb[0]) / zelle))
    top = c[max(0, io - 2): io + 3].max() if len(c) else 0
    if top < 15: return None
    L = [l_ for l_ in laeufe(c, max(15, 0.05 * top)) if l_[0] <= io + 2 and l_[1] >= io - 2]
    if not L: return None
    hu = float(min(zb[L[0][0]], zo - d_min)); hu_q = "Kantenband"
    if L[0][0] == 0: hu, hu_q = zo - 0.15, "ANNAHME 0,15 m (Kantenband reicht ueber das Suchfenster)"
    hb = m & (z >= hu) & (z <= zo + 0.04); hv = hb & (w > aus - 0.15); hh = hb & (w <= aus - 0.15)
    h_front = round(max(float(np.median(w[hv])) if hv.sum() >= 15 else aus, aus), 2); h_hinten = round(float(np.median(w[hh])), 2) if hh.sum() >= 30 else None
    zs = np.arange(zu + 0.15, hu - 0.2 + 1e-6, zelle); cs, _ = np.histogram(z[m], bins=zs) if len(zs) > 1 else (np.zeros(0), None)
    Ls = laeufe(cs, 12, luecke=1) if len(cs) else []
    so = round(float(zs[Ls[0][0]]), 2) if Ls else None
    if so is not None and so - zu < d_min: so = None
    fz0, fz1 = (so if so is not None else zu + 0.3) + 0.02, hu - 0.02
    if fz1 - fz0 < 0.2: return None
    fm = mu & (np.abs(w - aus) < 0.25) & (z > fz0) & (z < fz1)
    ub_ = np.arange(ua - 0.1, ub + 0.1 + 1e-6, 0.1); cu, _ = np.histogram(u[fm], bins=ub_)
    kn, belegt = [], 0.0
    for a_, b_ in laeufe(cu, 3, luecke=3, min_lauf=1):
        n_ = int(cu[a_:b_ + 1].sum()); breite = ub_[b_ + 1] - ub_[a_]
        if n_ >= 20 and breite <= 1.2: kn.append(dict(u0=round(float(ub_[a_]), 2), u1=round(float(ub_[b_ + 1]), 2), punkte=n_))
        else: belegt += float((cu[a_:b_ + 1] >= 3).sum()) * 0.1
    offen = len(kn) >= 2 and belegt < 0.15 * (ub - ua)
    return dict(holm_unten=round(hu, 2), holm_unten_quelle=hu_q, holm_front=h_front, holm_hinten=h_hinten, schwelle_oben=so, knaggen=kn, feld_belegt_m=round(belegt, 2), offen=bool(offen),
                feld=[round(fz0, 2), round(fz1, 2)], quelle="Kantenpunkte der Vorbau-Ebene (ebenen_masse.bruestung)",
                hinweis="offen = keine waagrechten Frontkanten im Feld ausser an den Knaggen; Knaggenform (Trapez) und Brettstaerke = ANNAHME")


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
            u = (P[:, :2] - o) @ d; z = P[:, 2]; ne = e.get("neigung")
            w = (P[:, :2] - o) @ n - ww - ((ne["b_u"] * (u - ne["u_ref"]) + ne["c_z"] * (z - ne["z_ref"])) if ne else 0.0)      # 22.11.2026: Tiefe gegen die oertliche (geneigte) Wand
            u0, u1, z0, z1 = e["zone"]; ok = (u >= u0) & (u <= u1) & (z >= z0) & (z <= z1); u, z, w = u[ok], z[ok], w[ok]
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
                        # 24.11.2026 (1122w: 5 statt 6 Konsolen, Foto 113130 zeigt 6): die letzte Konsole (u 4,09..4,39) ragte 0,05 m ueber 'Kastenende + 0,2' hinaus - das
                        # Kastenende ist die belegte Unterkante und endet an der Wand frueher. Entscheidend ist die MITTE des Stuecks im Kastenbereich (+-0,2 m).
                        kb = max(kl, key=lambda l_: l_["punkte"]); ks = [s_ for s_ in kb["stuecke"] if 0.15 <= s_[1] - s_[0] <= 0.9 and km["kasten"]["u0"] - 0.2 <= 0.5 * (s_[0] + s_[1]) <= km["kasten"]["u1"] + 0.2]
                        if len(ks) >= 2:
                            km["konsolen"] = dict(z_unten=kb["z"], anzahl=len(ks), lage=[[s_[0], s_[1]] for s_ in ks], abstand=round(float(np.median(np.diff([0.5 * (s_[0] + s_[1]) for s_ in ks]))), 2))
                            mu = np.zeros(len(u), bool)
                            for s_ in ks: mu |= (u > s_[0] - 0.3) & (u < s_[1] + 0.3)
                            q = mu & (z < kb["z"] - 0.1) & (w > 0.12) & (w < aus - 0.2)      # ZWISCHEN Wand und Front (Wandkanten = Fugen zaehlen nicht; 1. Fassung nahm sie mit: Fuss 7,95 = Zonenrand)
                            if q.sum() >= 50:
                                prof = [[round(float(za), 2), round(float(np.median(w[mu & (z >= za) & (z < za + 0.4) & (w > -0.3) & (w < aus + 0.2)])), 2)] for za in np.arange(max(z0, kb["z"] - 2.4), kb["z"], 0.4) if (mu & (z >= za) & (z < za + 0.4) & (w > -0.3) & (w < aus + 0.2)).sum() >= 30]
                                km["streben"] = dict(z_fuss=round(float(np.percentile(z[q], 5)), 2), punkte_zwischen=int(q.sum()), tiefenprofil=prof, hinweis="gerade Strebe vom Wandfuss zur Konsole = ANNAHME (Profil zeigt die gemessene Tiefe je Hoehenband)")
                    mz = fr & (z > lo_["z"] + 0.2) & (z < (g.get("galerie") or {}).get("z_dach", g["z1"]) - 0.1)
                    # 24.11.2026 (Lauf 1122w: 'keine Pfosten belegt', Vordach schwebte ohne Stuetze ueber der Galerie): das Band zwischen Holm und Raehm war duenn
                    # trianguliert (94 Punkte), die zwei Pfosten aber klar (24 / 61 Punkte je 6 cm, wie 1122t-v: u -3,45 / 4,25). Das Sammeltor 'mz >= 100' warf sie weg -
                    # massgeblich ist der einzelne Haufen, nicht die Summe ueber das ganze Band. Haufen-Untergrenze 15 Punkte je 6 cm (vorher 25: linker Pfosten 1122w 24 Punkte);
                    # bei dichtem Band gilt weiter 4 % der Bandpunkte. Draehte/Riegel liegen waagrecht und bilden keine u-Spitze.
                    if mz.sum() >= 15:
                        hu, eu = np.histogram(u[mz], bins=np.arange(u0, u1 + 0.02, 0.02)); su = np.convolve(hu, np.ones(3), "same"); pu, _ = find_peaks(su, height=max(15, 0.04 * mz.sum()), distance=4); pf = []
                        for x in eu[pu] + 0.01:
                            if pf and x - pf[-1][-1] < 0.5: pf[-1].append(float(x))
                            else: pf.append([float(x)])
                        km["pfosten"] = [dict(u=round(float(np.mean(c_)), 2), breite=round(c_[-1] - c_[0], 2) if len(c_) >= 2 and c_[-1] - c_[0] >= 0.12 else None, punkte=int(((np.abs(u - np.mean(c_)) < 0.3) & mz).sum())) for c_ in pf]
                    br_ = bruestung(u, z, w, aus, km["kasten"])
                    if br_:
                        km["bruestung"] = br_
                        for k_ in br_["knaggen"]:              # Knagge sitzt am Pfostenfuss: Knagge ohne Kanten-Pfosten in 0,6 m = Pfostenlage (1122w: Mittelpfosten im Band Holm..Raehm ohne Punkte)
                            um_ = 0.5 * (k_["u0"] + k_["u1"])
                            if not any(abs(p_["u"] - um_) < 0.6 for p_ in km.get("pfosten") or []):
                                km.setdefault("pfosten", []).append(dict(u=round(um_, 2), breite=None, punkte=k_["punkte"], quelle="Knagge im Bruestungsfeld"))
                        if km.get("pfosten"): km["pfosten"].sort(key=lambda p_: p_["u"])
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

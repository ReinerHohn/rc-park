#!/usr/bin/env python3
"""wolke_baender.py - GENERISCH: Hoehenbaender EINES KOERPERS (Ecktuermchen, Zentralkoerper, Anbau) aus der farbigen Fotowolke.

Ein Koerper ist eine senkrechte Achse (tief, quer) mit einer Zonenbreite quer - definiert in objekt.json["koerper"][name] oder per
--achse/--zone; 'tuermchen' nimmt die Kreisfit-Achse aus profile_generator.json, 'zentral' die Bauwerksachse (0, 0).
Je 0,25-m-Schicht in der Zone (|quer - Achse| < Zonenbreite, Tiefe vor der Achse): Aussenradius r = p97 der Tiefe minus Achse
(Silhouette/Front) und Farbklassen-Anteile (stein, weiss, dunkel, kupfer). Daraus eine Klasse je Schicht:
  kupfer   Kupferanteil > Schwelle (Dach/Kegel)
  traufe   Radius springt gegen die Nachbarn nach aussen (Kragplatte/Dachtraufe)
  gesims   wie traufe, aber unter einem helleren Band (Kragplatte unter der Bruestung) - im Zweifel 'gesims'
  offen    dunkel-dominiert ohne Steinanteil (Oeffnungen/Arkaden, Schatten)
  fachwerk hell/gemischt, wenig dunkel, wenig Stein (Bruestung mit Holz und Putz)
  stein    Steinanteil dominiert (Schaft, Konsolen)
Schichten gleicher Klasse werden zu Baendern zusammengefasst (Mindesthoehe 0,5 m, kuerzere gehen im Nachbarn auf); ein Kupferdach ueber der
letzten Traufe als Gerade durch die Spitze (Mass 'spitze' des Koerpers). Ausgabe: modelle/<objekt>/profile_baender_<koerper>.json
{achse, baender [{z0, z1, r, klasse, anteile}], kegel} - der Generator baut daraus (Tuermchen); --pruefungen legt je Band eine Zeile
'Band <koerper> <klasse>: Aussenradius bei z' an (Modell: tuerm_radius = Strahl von aussen auf die Achse) - zuerst rot, dann Generator.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_baender.py modelle/<objekt>/objekt.json nord --koerper tuermchen --pruefungen
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_baender.py modelle/<objekt>/objekt.json nord --koerper zentral
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bauteile import seite_achsen, lade_masse

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--dicht"); ap.add_argument("--dz", type=float, default=0.25)
    ap.add_argument("--koerper", default="tuermchen", help="Name in objekt.json['koerper'] (tuermchen | zentral | ...)")
    ap.add_argument("--z", nargs=2, type=float); ap.add_argument("--zone", type=float, help="halbe Zonenbreite quer um die Achse (ueberschreibt objekt.json)")
    ap.add_argument("--achse", nargs=2, type=float, help="Achse tief quer (ueberschreibt objekt.json)")
    ap.add_argument("--kupfer-schwelle", type=float, default=10.0); ap.add_argument("--min-band", type=float, default=0.5); ap.add_argument("--toleranz", type=float, default=0.3)
    ap.add_argument("--pruefungen", action="store_true"); a = ap.parse_args(); import cv2
    od = os.path.dirname(os.path.abspath(a.objekt)); s = a.seite.lower()
    pf = os.path.join(od, a.dicht or f"sfm/dicht_{s}_entzerrt.npy"); P = np.load(pf).astype(float)
    C = np.load(pf.replace("_entzerrt.npy", "_modell.npy").replace("_modell.npy", "_farben.npy"))
    tief, sgn, quer = seite_achsen(s); it = 0 if tief == "x" else 1; iq = 1 - it
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from bauteile import lade_masse
    masse = lade_masse(os.path.join(od, "masse.json")); obj = json.load(open(a.objekt))
    KO = obj.get("koerper", {})
    if a.koerper not in KO: sys.exit(f"Koerper '{a.koerper}' nicht in objekt.json['koerper'] (vorhanden: {list(KO)}) - Achse/Zone/Hoehen/Spitze dort als Daten eintragen")
    K = KO[a.koerper]
    ach = K["achse"]
    if isinstance(ach, str) and ach.startswith("profile_generator.json:"):
        G = json.load(open(os.path.join(od, "profile_generator.json")))[ach.split(":", 1)[1]]; ach = [G["tief"], G["quer"]]
    at, aq = (a.achse if a.achse else ach); zone = a.zone or K["zone"]; zr = a.z or K["z"]; reich = K.get("reichweite", 4.0)
    def hoehe(ausdruck): return float(sum(masse[t] if t in masse else float(t) for t in str(ausdruck).split("+")))
    TS = hoehe(K["spitze"])
    hsv = cv2.cvtColor(C.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(float); h, sa, v = hsv.T
    kl = {"stein": ((h <= 20) | (h >= 165)) & (sa > 45) & (v > 60) & (v < 200), "weiss": (sa < 45) & (v > 165), "dunkel": v < 75, "kupfer": (h >= 60) & (h <= 100) & (sa > 50)}
    schichten = []
    for z in np.arange(zr[0], zr[1], a.dz):
        k = (np.abs(P[:, 2] - (z + a.dz / 2)) < a.dz / 2) & (np.abs(np.abs(P[:, iq]) - aq) < zone) & (sgn * P[:, it] > at) & (sgn * P[:, it] < at + reich)
        if k.sum() < 12: continue
        x = sgn * P[k, it]; fr = {n: float(m[k].mean()) for n, m in kl.items()}
        schichten.append(dict(z=round(float(z + a.dz / 2), 3), n=int(k.sum()), r=round(float(np.percentile(x, 97) - at), 3), **{f"p_{n}": round(100 * f, 1) for n, f in fr.items()}))
    # Klasse je Schicht
    rs = np.array([q["r"] for q in schichten])
    for i, q in enumerate(schichten):
        unten = rs[max(0, i - 4):i]; bump = q["r"] - (np.median(unten) if len(unten) else q["r"])   # Kragplatte: springt gegen das DARUNTER liegende Band vor
        if q["p_kupfer"] >= a.kupfer_schwelle and q["p_kupfer"] >= q["p_stein"]: q["klasse"] = "kupfer"
        elif bump > 0.12: q["klasse"] = "traufe"
        elif q["p_dunkel"] > 45 and q["p_stein"] < 35: q["klasse"] = "offen"
        elif q["p_dunkel"] < 20 and q["p_stein"] < 40: q["klasse"] = "hell"                           # Putz/Holz hell (Bruestung, Glockenstock-Wand)
        else: q["klasse"] = "stein"
    # Kupferdach-Kontinuitaet: Schichten ueber einem Kupferband, deren Radius der Dachlinie folgt (Gerade durch die Kupferschichten, +-0,35 m)
    # und die keinen Stein zeigen, gehoeren zum Dach (Glanzlichter/Schatten aendern nur die Farbe). Eine Wand mit anderem Radius bleibt Wand.
    i = 0
    while i < len(schichten):
        if schichten[i]["klasse"] != "kupfer": i += 1; continue
        j = i
        while j < len(schichten) and schichten[j]["klasse"] == "kupfer": j += 1
        zz = np.array([q["z"] for q in schichten[i:j]]); rr = np.array([q["r"] for q in schichten[i:j]])
        if len(zz) >= 3:
            A_ = np.c_[zz, np.ones(len(zz))]; (m_, b_), *_ = np.linalg.lstsq(A_, rr, rcond=None)
            k = j
            while k < len(schichten) and schichten[k]["klasse"] in ("hell", "offen", "traufe") and schichten[k]["p_stein"] < 15 and abs(schichten[k]["r"] - (m_ * schichten[k]["z"] + b_)) < 0.35 and m_ < 0:
                schichten[k]["klasse"] = "kupfer"; schichten[k]["dach_kontinuitaet"] = True; k += 1
            j = k
        i = j
    # Baender: gleiche Klasse zusammenfassen, Minibaender im Nachbarn aufgehen lassen
    baender = []
    for q in schichten:
        if baender and baender[-1]["klasse"] == q["klasse"]: baender[-1]["z1"] = q["z"] + a.dz / 2; baender[-1]["schichten"].append(q)
        else: baender.append(dict(klasse=q["klasse"], z0=q["z"] - a.dz / 2, z1=q["z"] + a.dz / 2, schichten=[q]))
    geaendert = True
    while geaendert:
        geaendert = False
        for i, b in enumerate(baender):
            if b["z1"] - b["z0"] < a.min_band - 1e-6 and len(baender) > 1 and b["klasse"] not in ("traufe",):
                j = i - 1 if i > 0 else i + 1
                if i > 0 and i + 1 < len(baender) and len(baender[i + 1]["schichten"]) > len(baender[i - 1]["schichten"]): j = i + 1
                baender[j]["schichten"] += b["schichten"]; baender[j]["z0"] = min(baender[j]["z0"], b["z0"]); baender[j]["z1"] = max(baender[j]["z1"], b["z1"]); baender.pop(i); geaendert = True; break
    for b in baender:
        rr = [q["r"] for q in b["schichten"]]; b["r"] = round(float(np.median(rr)), 2); b["r_max"] = round(float(max(rr)), 2); b["n"] = int(sum(q["n"] for q in b["schichten"]))
        b["anteile"] = {n: round(float(np.mean([q[f"p_{n}"] for q in b["schichten"]])), 1) for n in ("stein", "weiss", "dunkel", "kupfer")}
        b["z0"] = round(b["z0"], 2); b["z1"] = round(b["z1"], 2); b["schichten"] = [q["z"] for q in b["schichten"]]
    # ---- Strukturen IN den Baendern (generisch, aus denselben Punkten):
    #  offen : Dunkellaeufe entlang der sichtbaren Flaeche (quer, 8-cm-Zellen) -> Oeffnungen je Flaeche (Anzahl, Breiten, Hoehe p5-p95)
    #  stein : Farbperiode (Steinanteil entlang z, 5-cm-Zellen, Autokorrelation) an der sichtbaren Kante -> Quader-/Schichthoehe
    dunkel = kl["dunkel"]; stein_m = kl["stein"]
    fb_default = lambda r: r * np.tan(np.radians(22.5))                                   # halbe Flaechenbreite eines Achtecks mit Schluesselweite 2r
    for b in baender:
        if b["klasse"] == "offen":
            r = b["r"]; fb = fb_default(r); ergeb = []
            for vorz in ((1, -1) if aq > 0.5 else (0,)):                                  # beide Koerper (quer +-Achse) oder einer auf der Achse
                qc = vorz * aq
                k = (P[:, 2] >= b["z0"]) & (P[:, 2] < b["z1"]) & (sgn * P[:, it] > at + r - 0.45) & (np.abs(P[:, iq] - qc) < fb + 0.1)
                if k.sum() < 40: continue
                y = P[k, iq] - qc; d = dunkel[k]; bins = np.arange(-fb - 0.1, fb + 0.1001, 0.08); idx = np.digitize(y, bins) - 1
                frac = np.array([d[idx == i].mean() if (idx == i).sum() >= 4 else np.nan for i in range(len(bins) - 1)])
                laeufe = []; cur = None
                for i, f in enumerate(frac):
                    if f == f and f > 0.5: cur = [i, i] if cur is None else [cur[0], i]
                    elif cur: laeufe.append(cur); cur = None
                if cur: laeufe.append(cur)
                laeufe = [(round(float(bins[a0] + 0.04), 2), round(float((b1 - a0 + 1) * 0.08), 2)) for a0, b1 in laeufe if (b1 - a0 + 1) * 0.08 >= 0.15]
                zz = P[k, 2][d]
                ergeb.append(dict(koerper_quer=round(qc, 2), n=int(k.sum()), dunkel_anteil=round(float(d.mean()), 2), laeufe=laeufe, hoehe=[round(float(np.percentile(zz, 5)), 2), round(float(np.percentile(zz, 95)), 2)] if d.sum() > 10 else None))
            if ergeb:
                anz = [len(e["laeufe"]) for e in ergeb]; br = [w for e in ergeb for _, w in e["laeufe"]]
                b["oeffnungen"] = dict(je_flaeche=int(round(float(np.median(anz)))), breite_median=round(float(np.median(br)), 2) if br else None, breiten=br, hoehe=ergeb[0]["hoehe"], flaechenbreite=round(2 * fb, 2), details=ergeb,
                                      hinweis="Dunkellaeufe > 50 % je 8 cm entlang der sichtbaren Flaeche; Laeufe < 15 cm verworfen")
        if b["klasse"] == "stein" and b["z1"] - b["z0"] >= 1.5:
            # Kante des Koerpers: Punkte nahe der Aussenkante (Tiefe > Achse + 0,85 r) -> Steinanteil je 5 cm Hoehe -> Autokorrelation
            r = b["r"]; k = (P[:, 2] >= b["z0"]) & (P[:, 2] < b["z1"]) & (sgn * P[:, it] > at + 0.85 * r) & (np.abs(np.abs(P[:, iq]) - aq) < zone)
            if k.sum() >= 200:
                zb = np.arange(b["z0"], b["z1"] + 1e-6, 0.05); idx = np.digitize(P[k, 2], zb) - 1; st = stein_m[k]
                reihe = np.array([st[idx == i].mean() if (idx == i).sum() >= 3 else np.nan for i in range(len(zb) - 1)])
                ok = ~np.isnan(reihe)
                if ok.sum() >= 20:
                    x = reihe.copy(); x[~ok] = np.nanmean(reihe); x = x - x.mean(); ac = np.correlate(x, x, "full")[len(x) - 1:]; ac = ac / max(ac[0], 1e-9)
                    lags = np.arange(len(ac)) * 0.05; cand = [(lags[i], ac[i]) for i in range(4, min(len(ac), 40)) if ac[i] > ac[i - 1] and ac[i] >= ac[i + 1 if i + 1 < len(ac) else i]]
                    cand = [q for q in cand if q[1] > 0]
                    if cand:
                        _stm = max(q[1] for q in cand); lag, st_ = min((q for q in cand if q[1] >= 0.5 * _stm), key=lambda q: q[0]); b["farbperiode"] = dict(periode_m=round(float(lag), 2), staerke=round(float(st_), 2), zellen=int(ok.sum()), hinweis="Autokorrelation des Steinanteils entlang z (5-cm-Zellen) an der Aussenkante; Periode = Schichthoehe der Quader/Baender")
    # Farbperiode auch bandunabhaengig in 4-m-Fenstern ueber den ganzen Koerper (Quaderhoehe des Schafts, Bandhoehen) - gleiche Methode
    perioden = []
    for zf in np.arange(zr[0], zr[1] - 2.0, 2.0):
        k = (P[:, 2] >= zf) & (P[:, 2] < zf + 4.0) & (np.abs(np.abs(P[:, iq]) - aq) < zone)
        rr = np.array([q["r"] for q in schichten if zf <= q["z"] < zf + 4.0]); 
        if k.sum() < 300 or len(rr) == 0: continue
        k &= (sgn * P[:, it] > at + 0.85 * float(np.median(rr)))
        zb = np.arange(zf, zf + 4.0 + 1e-6, 0.05); idx = np.digitize(P[k, 2], zb) - 1; st = stein_m[k]
        reihe = np.array([st[idx == i].mean() if (idx == i).sum() >= 3 else np.nan for i in range(len(zb) - 1)]); ok = ~np.isnan(reihe)
        if ok.sum() < 30: continue
        x = reihe.copy(); x[~ok] = np.nanmean(reihe); x = x - x.mean(); ac = np.correlate(x, x, "full")[len(x) - 1:]; ac = ac / max(ac[0], 1e-9)
        cand = [(i * 0.05, ac[i]) for i in range(4, min(len(ac), 40)) if ac[i] > ac[i - 1] and ac[i] >= ac[min(i + 1, len(ac) - 1)]]
        cand = [q for q in cand if q[1] > 0]
        if cand: _stm = max(q[1] for q in cand); lag, st_ = min((q for q in cand if q[1] >= 0.5 * _stm), key=lambda q: q[0]); perioden.append(dict(z0=round(float(zf), 1), z1=round(float(zf + 4.0), 1), periode_m=round(float(lag), 2), staerke=round(float(st_), 2), zellen=int(ok.sum())))
    # Erste Traufe (Kragplatte unter dem Bruestungsband) heisst 'gesims', die hoechste 'traufe' (Dachtraufe, darauf der Kegel)
    trauf = [b for b in baender if b["klasse"] == "traufe"]
    for b in trauf[:-1]: b["klasse"] = "gesims"
    # Kegel: Gerade von der Dachtraufe (r der Traufplatte) zur Spitze - Steigung aus den Kupferschichten (kleinste Quadrate durch die Spitze)
    kegel = None; kb = [b for b in baender if b["klasse"] == "kupfer"]
    if kb:
        ob = kb[-1]; kup = [q for q in schichten if q["klasse"] == "kupfer" and ob["z0"] <= q["z"] <= ob["z1"] and q["z"] < TS - 0.3]
        tr_unter = [b for b in baender if b["klasse"] in ("traufe", "gesims") and abs(b["z1"] - ob["z0"]) < 0.3]
        if len(kup) >= 4:
            hh = np.array([TS - q["z"] for q in kup]); rr = np.array([q["r"] for q in kup]); kr = float((rr * hh).sum() / (hh * hh).sum())
            A_ = np.c_[[q["z"] for q in kup], np.ones(len(kup))]; (m_, b_), *_ = np.linalg.lstsq(A_, rr, rcond=None)
            z0 = tr_unter[-1]["z1"] if tr_unter else ob["z0"]; r_tr = tr_unter[-1]["r"] if tr_unter else float(m_ * z0 + b_)
            kegel = dict(r_je_m=round(kr, 4), z0=round(float(z0), 2), r0=round(float(r_tr), 2), r0_aus_steigung=round(float(kr * (TS - z0)), 2), spitze=TS, schichten=len(kup),
                         gerade_frei=dict(r_je_m=round(float(m_), 4), r_bei_z0=round(float(m_ * z0 + b_), 2), r_oben=round(float(m_ * ob["z1"] + b_), 2), z_oben=ob["z1"]))
    print(f"Baender Koerper '{a.koerper}' ({s}), Achse tief {at} quer {aq}, Zone +-{zone}, Spitze {TS}:")
    for b in baender:
        print(f"  {b['klasse']:9s} {b['z0']:6.2f}..{b['z1']:6.2f}  r {b['r']:.2f} (max {b['r_max']:.2f})  stein {b['anteile']['stein']:4.0f} weiss {b['anteile']['weiss']:4.0f} dunkel {b['anteile']['dunkel']:4.0f} kupfer {b['anteile']['kupfer']:4.0f}  n={b['n']}")
        if "oeffnungen" in b: o = b["oeffnungen"]; print(f"            Oeffnungen: {o['je_flaeche']} je Flaeche ({o['flaechenbreite']} m breit), Breiten {o['breiten']}, Hoehe {o['hoehe']}")
        if "farbperiode" in b: f = b["farbperiode"]; print(f"            Farbperiode (Quader/Schichten): {f['periode_m']} m (Staerke {f['staerke']}, {f['zellen']} Zellen)")
    if kegel: print(f"  Kegel: r = {kegel['r_je_m']} x (Spitze - z) ab {kegel['z0']} m (r0 {kegel['r0']}) aus {kegel['schichten']} Kupferschichten")
    # Farbperiode QUER (Quaderlaenge entlang der Fassade) in den Steinzonen nahe der Kante: Steinanteil je 5 cm entlang quer, 2 m ab der Kante
    perioden_quer = []
    kanten_ = K.get("kanten") or ([dict(z0=-1e9, z1=1e9, quer=K["kante_quer"])] if K.get("kante_quer") is not None else [])
    for kk in kanten_:
        for zf in np.arange(max(zr[0], kk["z0"]), min(zr[1], kk["z1"]) - 2.0, 2.0):
            rr = np.array([q["r"] for q in schichten if zf <= q["z"] < zf + 4.0])
            if len(rr) == 0: continue
            front = at + float(np.median(rr))
            for vorz in (1, -1):
                k = (P[:, 2] >= zf) & (P[:, 2] < zf + 4.0) & (sgn * P[:, it] > front - 0.6) & (vorz * P[:, iq] > kk["quer"] - 2.0) & (vorz * P[:, iq] < kk["quer"] + 0.1)
                if k.sum() < 300: continue
                qb = np.arange(kk["quer"] - 2.0, kk["quer"] + 0.1 + 1e-6, 0.05); idx = np.digitize(vorz * P[k, iq], qb) - 1; st = stein_m[k]
                reihe = np.array([st[idx == i].mean() if (idx == i).sum() >= 3 else np.nan for i in range(len(qb) - 1)]); ok = ~np.isnan(reihe)
                if ok.sum() < 25: continue
                x = reihe.copy(); x[~ok] = np.nanmean(reihe); x = x - x.mean(); ac = np.correlate(x, x, "full")[len(x) - 1:]; ac = ac / max(ac[0], 1e-9)
                cand = [(i * 0.05, ac[i]) for i in range(4, min(len(ac) - 1, 40)) if ac[i] > ac[i - 1] and ac[i] >= ac[i + 1]]
                cand = [q for q in cand if q[1] > 0]
                if cand: _stm = max(q[1] for q in cand); lag, st_ = min((q for q in cand if q[1] >= 0.5 * _stm), key=lambda q: q[0]); perioden_quer.append(dict(z0=round(float(zf), 1), z1=round(float(zf + 4.0), 1), seite_quer=vorz, periode_m=round(float(lag), 2), staerke=round(float(st_), 2), zellen=int(ok.sum())))
    if perioden_quer: print("  Farbperiode QUER an der Kante (Quaderlaenge) je 4-m-Fenster: " + ", ".join(f"{q['z0']}-{q['z1']}{'+' if q['seite_quer']>0 else '-'}: {q['periode_m']} m (St {q['staerke']})" for q in perioden_quer))
    if perioden: print("  Farbperiode je 4-m-Fenster (Steinanteil an der Kante): " + ", ".join(f"{q['z0']}-{q['z1']}: {q['periode_m']} m (St {q['staerke']})" for q in perioden))
    out = dict(seite=s, koerper=a.koerper, achse=dict(tief=at, quer=aq), zone=zone, spitze=TS, baender=baender, kegel=kegel, farbperioden=perioden, farbperioden_quer=perioden_quer, schichten=schichten, quelle="tools/wolke_baender.py: Aussenradius p97 + Farbklassen je 0,25 m, Baender nach Klassenwechsel")
    op = os.path.join(od, f"profile_baender_{a.koerper}.json"); json.dump(out, open(op, "w"), indent=1, ensure_ascii=False); print("geschrieben:", op)
    if a.pruefungen:
        tp = os.path.join(od, "masstabelle.json"); from masstabelle_io import sperren, schreiben; _L = sperren(tp); T = json.load(open(tp)); gesetzt = set(); neu = 0
        seite = ("-" if sgn < 0 else "+") + tief
        for b in (baender + ([dict(klasse="kegel", z0=kegel["z0"], z1=TS, r=None)] if kegel else [])) if K.get("pruefungen_radius", True) else []:
            if b["klasse"] == "kegel": zm = round((kegel["z0"] + TS) / 2, 2); r = kegel["r0"] * (TS - zm) / (TS - kegel["z0"])
            else: zm = round((b["z0"] + b["z1"]) / 2, 2); r = b["r"]
            if a.koerper == "tuermchen" and b["klasse"] == "stein" and b["z0"] < 30: continue   # Schaft/Konsolen haben eigene Pruefungen (Gesamtbreite 28,5, TWs)
            name = f"Band {a.koerper} {b['klasse']} ({b['z0']:.2f}-{b['z1']:.2f} m): Aussenradius bei {zm:.2f} m (m)"; wert = f"band_{a.koerper}_{b['klasse']}_{int(round(zm * 100))}"
            soll = [round(r - a.toleranz / 2, 2), round(r + a.toleranz / 2, 2)]; gesetzt.add(name)
            T["messungen"][wert] = {"typ": "tuerm_radius", "seite": seite, "z": zm, "quer": round(float(aq), 2), "achse_tief": round(float(at), 3)}
            quelle = f"wolke_baender.py ({a.koerper}): Band {b['klasse']} {b['z0']}-{b['z1']} m, Aussenradius p97 {r:.2f} (Anteile {b.get('anteile', '')}); Modell: Strahl von {seite} auf die Achse"
            for pr in T["pruefungen"]:
                if pr["name"] == name:
                    if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "wolke_tuerm_baender.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                    pr["wert"] = wert; break
            else: T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=quelle, quelltyp="sfm_bodenanker", merkmal="schlankheit", massstab="LoD2-Eckkanten + Wandebene", protokoll=f"profile_baender_{a.koerper}.json")); neu += 1
        # Oeffnungen je Flaeche (Modell: Laeufe tiefer Treffer entlang der sichtbaren Flaeche auf Bandmitte)
        for b in baender:
            o = b.get("oeffnungen")
            if not o or not o.get("je_flaeche"): continue
            if not K.get("pruefungen_offen", True):                                            # ohne Pruefrecht: Befund als offene Beobachtung (einmal je Band)
                aid = f"band_{a.koerper}_offen_{int(b['z0'] * 100)}"
                if not any(x.get("auto_id") == aid for x in T.get("beobachtungen_offen", []) + T.get("beobachtungen_erledigt", [])):
                    T.setdefault("beobachtungen_offen", []).append(dict(datum="auto", wer=f"wolke_baender.py ({a.koerper})", auto_id=aid, text=f"Band offen {b['z0']}-{b['z1']} m: {o['je_flaeche']} Oeffnung(en) je Flaeche, Breiten {o['breiten']}, Hoehe {o['hoehe']} (Dunkellaeufe)", naechster_schritt="gegen Fassadendaten (fassade.json) pruefen; bei Bestaetigung pruefungen_offen fuer den Koerper setzen"))
                continue
            zm = round(float(np.mean(o["hoehe"])) if o.get("hoehe") else (b["z0"] + b["z1"]) / 2, 2); fbh = o["flaechenbreite"] / 2
            for key, soll, feld in (("anzahl", [o["je_flaeche"], o["je_flaeche"]], "anzahl"), ("breite", [round(o["breite_median"] - 0.15, 2), round(o["breite_median"] + 0.15, 2)], "breite_median")):
                if key == "breite" and not o.get("breite_median"): continue
                name = f"Band {a.koerper} offen ({b['z0']:.2f}-{b['z1']:.2f} m): Oeffnungen je Flaeche {key} bei {zm:.2f} m"; wert = f"band_{a.koerper}_oeffn_{int(round(zm * 100))}"
                gesetzt.add(name); T["messungen"][wert] = {"typ": "flaeche_oeffnungen", "seite": seite, "z": zm, "quer0": round(float(aq - fbh), 2), "quer1": round(float(aq + fbh), 2), "tiefe": 0.2}
                quelle = f"wolke_baender.py ({a.koerper}): Dunkellaeufe entlang der sichtbaren Flaeche im Band offen: {o['je_flaeche']} je Flaeche, Breiten {o['breiten']}, Hoehe {o['hoehe']}; Nutzer: 'Boegen zu klein und zu viele'"
                for pr in T["pruefungen"]:
                    if pr["name"] == name:
                        if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "wolke_baender.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                        pr["wert"] = f"{wert}_{feld}"; break
                else: T["pruefungen"].append(dict(name=name, wert=f"{wert}_{feld}", soll=soll, quelle=quelle, quelltyp="sfm_bodenanker", merkmal="schlankheit", massstab="LoD2-Eckkanten + Wandebene", protokoll=f"profile_baender_{a.koerper}.json")); neu += 1
        # Quader-/Schichtperiode an der Kante (Modell: relief_periode entlang der Kantenlinie); Kantenlage quer aus objekt.json['koerper'][..]['kante_quer']
        kanten = K.get("kanten") or ([dict(z0=-1e9, z1=1e9, quer=K["kante_quer"])] if K.get("kante_quer") is not None else [])
        def kante_bei(z): return next((kk["quer"] for kk in kanten if kk["z0"] <= z <= kk["z1"]), None)
        stein_z = [(b["z0"], b["z1"]) for b in baender if b["klasse"] in ("stein", "hell")]
        per_liste = [dict(z0=b["z0"], z1=b["z1"], **b["farbperiode"]) for b in baender if "farbperiode" in b] + [q for q in perioden if any(z0 <= q["z0"] and q["z1"] <= z1 for z0, z1 in stein_z) or q["staerke"] >= 0.45]
        for q in (per_liste if K.get("pruefungen_periode", True) else []):
            kq = kante_bei((q["z0"] + q["z1"]) / 2)
            if kq is None or q["staerke"] < 0.3: continue
            if True:
                name = f"Band {a.koerper} Quaderperiode {q['z0']:.0f}-{q['z1']:.0f} m: Reliefperiode an der Kante (m)"; wert = f"band_{a.koerper}_periode_{int(q['z0'])}"
                soll = [round(q["periode_m"] - 0.1, 2), round(q["periode_m"] + 0.1, 2)]; gesetzt.add(name)
                T["messungen"][wert] = {"typ": "relief_periode", "seite": seite, "quer": float(kq), "z0": q["z0"], "z1": q["z1"]}
                soll = [round(q["periode_m"] - 0.12, 2), round(q["periode_m"] + 0.12, 2)]
                quelle = f"wolke_baender.py ({a.koerper}): Farbperiode des Steinanteils an der Kante {q['z0']}-{q['z1']} m = {q['periode_m']} m (Staerke {q['staerke']}); Nutzer: 'Backsteine zu grob'"
                for pr in T["pruefungen"]:
                    if pr["name"] == name:
                        if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "wolke_baender.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                        pr["wert"] = wert; break
                else: T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=quelle, quelltyp="sfm_bodenanker", merkmal="verhaeltnis", massstab="LoD2-Eckkanten + Wandebene", protokoll=f"profile_baender_{a.koerper}.json")); neu += 1
        alt = [pr for pr in T["pruefungen"] if (pr["name"].startswith(f"Band {a.koerper} ") or (a.koerper == "tuermchen" and pr["name"].startswith("Ecktuermchen Band "))) and pr["name"] not in gesetzt]
        T["pruefungen"] = [pr for pr in T["pruefungen"] if pr not in alt]
        noch = {pr["wert"] for pr in T["pruefungen"]}
        for pr in alt:
            if pr["wert"] not in noch: T["messungen"].pop(pr["wert"], None)                     # Messung nur loeschen, wenn keine Zeile sie mehr nutzt
        schreiben(tp, T, _L); print(f"Masstabelle: {neu} neue Band-Pruefungen, {len(alt)} veraltete entfernt")

if __name__ == "__main__":
    main()

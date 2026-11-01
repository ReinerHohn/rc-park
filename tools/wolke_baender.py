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
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from bauteile import lade_masse, seite_achsen
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
    for b in baender: print(f"  {b['klasse']:9s} {b['z0']:6.2f}..{b['z1']:6.2f}  r {b['r']:.2f} (max {b['r_max']:.2f})  stein {b['anteile']['stein']:4.0f} weiss {b['anteile']['weiss']:4.0f} dunkel {b['anteile']['dunkel']:4.0f} kupfer {b['anteile']['kupfer']:4.0f}  n={b['n']}")
    if kegel: print(f"  Kegel: r = {kegel['r_je_m']} x (Spitze - z) ab {kegel['z0']} m (r0 {kegel['r0']}) aus {kegel['schichten']} Kupferschichten")
    out = dict(seite=s, koerper=a.koerper, achse=dict(tief=at, quer=aq), zone=zone, spitze=TS, baender=baender, kegel=kegel, schichten=schichten, quelle="tools/wolke_baender.py: Aussenradius p97 + Farbklassen je 0,25 m, Baender nach Klassenwechsel")
    op = os.path.join(od, f"profile_baender_{a.koerper}.json"); json.dump(out, open(op, "w"), indent=1, ensure_ascii=False); print("geschrieben:", op)
    if a.pruefungen:
        tp = os.path.join(od, "masstabelle.json"); from masstabelle_io import sperren, schreiben; _L = sperren(tp); T = json.load(open(tp)); gesetzt = set(); neu = 0
        seite = ("-" if sgn < 0 else "+") + tief
        for b in baender + ([dict(klasse="kegel", z0=kegel["z0"], z1=TS, r=None)] if kegel else []):
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
        alt = [pr for pr in T["pruefungen"] if (pr["name"].startswith(f"Band {a.koerper} ") or (a.koerper == "tuermchen" and pr["name"].startswith("Ecktuermchen Band "))) and pr["name"] not in gesetzt]
        T["pruefungen"] = [pr for pr in T["pruefungen"] if pr not in alt]
        noch = {pr["wert"] for pr in T["pruefungen"]}
        for pr in alt:
            if pr["wert"] not in noch: T["messungen"].pop(pr["wert"], None)                     # Messung nur loeschen, wenn keine Zeile sie mehr nutzt
        schreiben(tp, T, _L); print(f"Masstabelle: {neu} neue Band-Pruefungen, {len(alt)} veraltete entfernt")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""wolke_tuerm_baender.py - GENERISCH: Baender eines Rundkoerpers neben der Achse (Ecktuermchen/Erker) aus der farbigen Fotowolke.

Je 0,25-m-Schicht in der Tuermchenzone (|quer - Achse| < Zonenbreite, Tiefe vor der Achse): Aussenradius r = p97 der Tiefe minus Achse
(Silhouette) und Farbklassen-Anteile (stein, weiss, dunkel, kupfer). Daraus eine Klasse je Schicht:
  kupfer   Kupferanteil > Schwelle (Dach/Kegel)
  traufe   Radius springt gegen die Nachbarn nach aussen (Kragplatte/Dachtraufe)
  gesims   wie traufe, aber unter einem helleren Band (Kragplatte unter der Bruestung) - im Zweifel 'gesims'
  offen    dunkel-dominiert ohne Steinanteil (Oeffnungen/Arkaden, Schatten)
  fachwerk hell/gemischt, wenig dunkel, wenig Stein (Bruestung mit Holz und Putz)
  stein    Steinanteil dominiert (Schaft, Konsolen)
Schichten gleicher Klasse werden zu Baendern zusammengefasst (Mindesthoehe 0,5 m, kuerzere gehen im Nachbarn auf), der Kupferkegel als
Gerade durch die Spitze (TUERM_SPITZE). Ausgabe: modelle/<objekt>/profile_tuerm_baender.json {achse, baender [{z0, z1, r, klasse, anteile}],
kegel {r0, z0, spitze}} - der Generator baut daraus die Tuermchen; --pruefungen legt je Band eine Zeile 'Ecktuermchen Band <klasse> <z>' an
(Durchmesser als Schnittausdehnung im Fenster seitlich der Dachbreite, Soll 2r +- Toleranz) - zuerst rot, dann Generator.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/wolke_tuerm_baender.py modelle/<objekt>/objekt.json nord --pruefungen
"""
import sys, os, json, argparse, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--dicht"); ap.add_argument("--dz", type=float, default=0.25)
    ap.add_argument("--z", nargs=2, type=float, default=[27.0, 45.0]); ap.add_argument("--zone", type=float, default=1.6, help="halbe Zonenbreite quer um die Tuermchenachse")
    ap.add_argument("--kupfer-schwelle", type=float, default=15.0); ap.add_argument("--min-band", type=float, default=0.5); ap.add_argument("--toleranz", type=float, default=0.3)
    ap.add_argument("--pruefungen", action="store_true"); a = ap.parse_args(); import cv2
    od = os.path.dirname(os.path.abspath(a.objekt)); s = a.seite.lower()
    pf = os.path.join(od, a.dicht or f"sfm/dicht_{s}_entzerrt.npy"); P = np.load(pf).astype(float)
    C = np.load(pf.replace("_entzerrt.npy", "_modell.npy").replace("_modell.npy", "_farben.npy"))
    tief, sgn, quer = {"nord": ("x", -1.0, "y"), "sued": ("x", 1.0, "y"), "ost": ("y", 1.0, "x"), "west": ("y", -1.0, "x")}[s]; it = 0 if tief == "x" else 1; iq = 1 - it
    G = json.load(open(os.path.join(od, "profile_generator.json"))); at, aq = G["tuerm_achse"]["tief"], G["tuerm_achse"]["quer"]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from bauteile import lade_masse
    TS = lade_masse(os.path.join(od, "masse.json"))["TUERM_SPITZE"]
    hsv = cv2.cvtColor(C.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(float); h, sa, v = hsv.T
    kl = {"stein": ((h <= 20) | (h >= 165)) & (sa > 45) & (v > 60) & (v < 200), "weiss": (sa < 45) & (v > 165), "dunkel": v < 75, "kupfer": (h >= 60) & (h <= 100) & (sa > 50)}
    schichten = []
    for z in np.arange(a.z[0], a.z[1], a.dz):
        k = (np.abs(P[:, 2] - (z + a.dz / 2)) < a.dz / 2) & (np.abs(np.abs(P[:, iq]) - aq) < a.zone) & (sgn * P[:, it] > at) & (sgn * P[:, it] < at + 4.0)
        if k.sum() < 12: continue
        x = sgn * P[k, it]; fr = {n: float(m[k].mean()) for n, m in kl.items()}
        schichten.append(dict(z=round(float(z + a.dz / 2), 3), n=int(k.sum()), r=round(float(np.percentile(x, 97) - at), 3), **{f"p_{n}": round(100 * f, 1) for n, f in fr.items()}))
    # Klasse je Schicht
    rs = np.array([q["r"] for q in schichten]); dach = False
    for i, q in enumerate(schichten):
        unten = rs[max(0, i - 4):i]; bump = q["r"] - (np.median(unten) if len(unten) else q["r"])   # Kragplatte: springt gegen das DARUNTER liegende Band vor
        if dach: q["klasse"] = "kupfer"; continue                                                      # oberhalb der Dachtraufe ist alles Kegel (Licht/Schatten aendern nur die Farbe)
        if q["p_kupfer"] > a.kupfer_schwelle: q["klasse"] = "kupfer"; dach = True
        elif bump > 0.12: q["klasse"] = "traufe"
        elif q["p_dunkel"] > 45 and q["p_stein"] < 35: q["klasse"] = "offen"
        elif q["p_dunkel"] < 20 and q["p_stein"] < 40: q["klasse"] = "fachwerk"
        else: q["klasse"] = "stein"
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
    kegel = None; kup = [q for q in schichten if q["klasse"] == "kupfer" and q["z"] < TS - 0.3 and (not trauf or q["z"] > trauf[-1]["z1"])]
    if len(kup) >= 4:
        hh = np.array([TS - q["z"] for q in kup]); rr = np.array([q["r"] for q in kup]); kr = float((rr * hh).sum() / (hh * hh).sum())
        z0 = trauf[-1]["z1"] if trauf else kup[0]["z"]; r_tr = trauf[-1]["r"] if trauf else kr * (TS - z0)
        kegel = dict(r_je_m=round(kr, 4), z0=round(float(z0), 2), r0=round(float(r_tr), 2), r0_aus_steigung=round(float(kr * (TS - z0)), 2), spitze=TS, schichten=len(kup))
    print(f"Tuermchen-Baender ({s}), Achse tief {at} quer {aq}, Spitze {TS}:")
    for b in baender: print(f"  {b['klasse']:9s} {b['z0']:6.2f}..{b['z1']:6.2f}  r {b['r']:.2f} (max {b['r_max']:.2f})  stein {b['anteile']['stein']:4.0f} weiss {b['anteile']['weiss']:4.0f} dunkel {b['anteile']['dunkel']:4.0f} kupfer {b['anteile']['kupfer']:4.0f}  n={b['n']}")
    if kegel: print(f"  Kegel: r = {kegel['r_je_m']} x (Spitze - z) ab {kegel['z0']} m (r0 {kegel['r0']}) aus {kegel['schichten']} Kupferschichten")
    out = dict(seite=s, achse=dict(tief=at, quer=aq), spitze=TS, baender=baender, kegel=kegel, schichten=schichten, quelle="tools/wolke_tuerm_baender.py: Aussenradius p97 + Farbklassen je 0,25 m, Baender nach Klassenwechsel")
    op = os.path.join(od, "profile_tuerm_baender.json"); json.dump(out, open(op, "w"), indent=1, ensure_ascii=False); print("geschrieben:", op)
    if a.pruefungen:
        tp = os.path.join(od, "masstabelle.json"); T = json.load(open(tp)); gesetzt = set(); neu = 0
        seite = ("-" if sgn < 0 else "+") + tief
        for b in baender + ([dict(klasse="kegel", z0=kegel["z0"], z1=TS, r=None)] if kegel else []):
            if b["klasse"] == "kegel": zm = round((kegel["z0"] + TS) / 2, 2); r = kegel["r0"] * (TS - zm) / (TS - kegel["z0"])
            else: zm = round((b["z0"] + b["z1"]) / 2, 2); r = b["r"]
            if b["klasse"] == "stein" and b["z0"] < 30: continue                 # Schaft/Konsolen haben eigene Pruefungen (Gesamtbreite 28,5, TWs)
            name = f"Ecktuermchen Band {b['klasse']} ({b['z0']:.2f}-{b['z1']:.2f} m): Aussenradius bei {zm:.2f} m (m)"; wert = f"tuerm_band_{b['klasse']}_{int(round(zm * 100))}"
            soll = [round(r - a.toleranz / 2, 2), round(r + a.toleranz / 2, 2)]; gesetzt.add(name)
            T["messungen"][wert] = {"typ": "tuerm_radius", "seite": seite, "z": zm, "quer": round(float(aq), 2), "achse_tief": round(float(at), 3)}
            quelle = f"wolke_tuerm_baender.py: Band {b['klasse']} {b['z0']}-{b['z1']} m, Aussenradius p97 {r:.2f} (Anteile {b.get('anteile', '')}); Modell: Strahl von {seite} auf die Tuermchenachse"
            for pr in T["pruefungen"]:
                if pr["name"] == name:
                    if pr["soll"] != soll: pr.setdefault("historie", []).append({"datum": "auto", "alt_soll": pr["soll"], "grund": "wolke_tuerm_baender.py neu gerechnet"}); pr["soll"] = soll; pr["quelle"] = quelle
                    pr["wert"] = wert; break
            else: T["pruefungen"].append(dict(name=name, wert=wert, soll=soll, quelle=quelle, quelltyp="sfm_bodenanker", merkmal="schlankheit", massstab="LoD2-Eckkanten + Wandebene", protokoll="profile_tuerm_baender.json")); neu += 1
        alt = [pr for pr in T["pruefungen"] if pr["name"].startswith("Ecktuermchen Band ") and pr["name"] not in gesetzt]
        T["pruefungen"] = [pr for pr in T["pruefungen"] if pr not in alt]
        noch = {pr["wert"] for pr in T["pruefungen"]}
        for pr in alt:
            if pr["wert"] not in noch: T["messungen"].pop(pr["wert"], None)                     # Messung nur loeschen, wenn keine Zeile sie mehr nutzt
        json.dump(T, open(tp, "w"), indent=1, ensure_ascii=False); print(f"Masstabelle: {neu} neue Band-Pruefungen, {len(alt)} veraltete entfernt")

if __name__ == "__main__":
    main()

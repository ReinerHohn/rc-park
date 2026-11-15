#!/usr/bin/env python3
"""fenster_aus_parsing.py <ortho-ordner> [--aus fenster.json] [--stimmen 3] - aus den OWLv2-Kaesten (fassade_parsing.py) BAUBARE Fenster machen.

Der Erkenner findet je Fensterfluegel/Oberlicht einen eigenen Kasten (gut, 15.11.2026 Nordgiebel Nachbarhaus: Lage auf ~5 cm) und daneben Fehltreffer
(Fachwerkfelder, Sammelkaesten, Konsolen). Hier, ohne Handgriff:
  1. Glasprobe am fusionierten Ortho (ortho_<id>.png): das Kasteninnere muss gleichmaessig sein (Helligkeitsstreuung < 0,16), ohne hellweissen Putz (< 8 %) und ohne viel Dunkles (< 30 %) -> Fachwerkfelder, Konsolen fallen weg.
  2. Sammelkaesten (enthalten >= 2 andere) und Doppelte (IoU > 0,5) weg; Mindeststimmen aus der Mehrfoto-Abstimmung.
  3. Scheiben zu Fenstern gruppieren (waagerecht Luecke < --luecke bei gleicher Hoehenlage, senkrecht ebenso) -> Fensterrechteck u0,u1,z0,z1,
     Pfostenlagen (Mitten der senkrechten Luecken) und Kaempferhoehe (Mitte der waagerechten Luecke).
Ausgabe: je Fassade Wandpunkt o, Richtung d (u-Achse), Normale n und die Fenster - direkt fuer bauteile.fenster_aus_json(koerper, datei).
Die Anzahl bleibt eine ERKENNUNG (Regel 9: Zaehlung am Foto pruefen, Bild fenster_<id>.jpg ansehen); Rahmen-/Nischentiefen sind ANNAHME.
"""
import sys, os, json, argparse, numpy as np, cv2


def iou(a, b):
    w = min(a["u1"], b["u1"]) - max(a["u0"], b["u0"]); h = min(a["z1"], b["z1"]) - max(a["z0"], b["z0"])
    if w <= 0 or h <= 0: return 0.0
    i = w * h; return i / ((a["u1"] - a["u0"]) * (a["z1"] - a["z0"]) + (b["u1"] - b["u0"]) * (b["z1"] - b["z0"]) - i)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ortho"); ap.add_argument("--aus"); ap.add_argument("--stimmen", type=int, default=3); ap.add_argument("--weiss", type=float, default=0.12)
    ap.add_argument("--luecke", type=float, default=0.25); ap.add_argument("--min_b", type=float, default=0.25); a = ap.parse_args()
    FA = {F.get("id_vorbau") or F.get("_id") or F.get("id"): F for F in json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"]}; EL = json.load(open(os.path.join(a.ortho, "elemente.json")))["fassaden"]; erg = {}
    def seite(F_): return int(round(np.degrees(np.arctan2(F_["n"][1], F_["n"][0])) / 20.0)) % 18
    VMED = {}; samm = {}
    for fid, X in EL.items():                                               # Vorlauf: gewichteter Helligkeitsmedian je Gebaeudeseite
        F = FA.get(fid); im = cv2.imread(os.path.join(a.ortho, f"ortho_{fid}.png"))
        if F is None or im is None: continue
        r = F["raster"]; zl = r["zelle"]; hv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32) / 255.0
        for e in X["elemente"]:
            if e["klasse"] != "fenster" or e.get("stimmen", 0) < a.stimmen: continue
            du = (e["u1"] - e["u0"]) * 0.2; dz = (e["z1"] - e["z0"]) * 0.2; c = hv[max(int((r["z1"] - e["z1"] + dz) / zl), 0):int((r["z1"] - e["z0"] - dz) / zl), max(int((e["u0"] + du - r["u0"]) / zl), 0):int((e["u1"] - du - r["u0"]) / zl)]
            if c.size < 60 or ((c[..., 2] > 0.85) & (c[..., 1] < 0.12)).mean() >= 0.08: continue
            samm.setdefault(seite(F), []).append((float(c[..., 2].mean()), e.get("stimmen", 1) * (e["u1"] - e["u0"]) * (e["z1"] - e["z0"])))
    for k_, L_ in samm.items():
        L_.sort(); cw = np.cumsum([w_ for _, w_ in L_]); VMED[k_] = L_[int(np.searchsorted(cw, 0.5 * cw[-1]))][0]
    for fid, X in EL.items():
        F = FA.get(fid); im = cv2.imread(os.path.join(a.ortho, f"ortho_{fid}.png"))
        if F is None or im is None: continue
        r = F["raster"]; zl = r["zelle"]; hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32) / 255.0; weiss = (hsv[..., 2] > 0.72) & (hsv[..., 1] < 0.25); leer = im.sum(2) == 0
        def px(e, rand=0.2):
            du = (e["u1"] - e["u0"]) * rand; dz = (e["z1"] - e["z0"]) * rand
            return int((e["u0"] + du - r["u0"]) / zl), int((e["u1"] - du - r["u0"]) / zl), int((r["z1"] - e["z1"] + dz) / zl), int((r["z1"] - e["z0"] - dz) / zl)
        K = []
        for e in X["elemente"]:
            if e["klasse"] != "fenster" or e.get("stimmen", 0) < a.stimmen or e["u1"] - e["u0"] < a.min_b or e["z1"] - e["z0"] < a.min_b: continue
            x0, x1, y0, y1 = px(e); w = weiss[max(y0, 0):y1, max(x0, 0):x1]
            if w.size < 20 or leer[max(y0, 0):y1, max(x0, 0):x1].mean() > 0.3: continue
            c = hsv[max(y0, 0):y1, max(x0, 0):x1]; hell = float(((c[..., 2] > 0.85) & (c[..., 1] < 0.12)).mean()); dunkel = float((c[..., 2] < 0.3).mean()); sd = float(c[..., 2].std())
            e = dict(e, hellweiss=hell, dunkel=dunkel, sd=sd, V=float(c[..., 2].mean())); K.append(e)
        # Glasprobe (Zahlen aus dem Nordgiebel, 34 Kaesten): Scheiben sd 0,01-0,14 / hellweiss 0 / dunkel <= 0,11; Fachwerkfelder, Konsolen, Sammelkaesten sd >= 0,17 oder dunkel >= 0,37 oder hellweiss >= 0,17
        # 15.11. Gegenprobe Historisches Kaufhaus: die Regel "gleichmaessiges helles Glas" (sd < 0,16, dunkel < 0,3) warf dort ALLE Masswerkfenster weg (Butzen/Sechseck-Verglasung,
        # dunkel, bunt). Allgemein gilt nur: im Fenster liegt kein hellweisser Putz. Balken/Schnitzfelder faengt der Erkenner selbst ueber Gegenbegriffe (fassade_parsing GEGEN).
        K = [e for e in K if e["hellweiss"] < 0.08]
        # Fassadenrichtungs-Regel: die echten Fenster EINER Gebaeudeseite sehen aehnlich hell aus (helles Spiegelglas ODER dunkle Butzenfenster). Kaesten, deren Helligkeit
        # > 0,17 vom stimmen- und flaechengewichteten Median der Seite abweicht, sind etwas anderes (dunkle Schnitzfelder/Balken am Fachwerk; helle Tafeln am Kaufhaus).
        K = [e for e in K if abs(e["V"] - VMED.get(seite(F), e["V"])) <= 0.17]
        K = [e for e in K if sum(1 for o in K if o is not e and o["u0"] >= e["u0"] - 0.05 and o["u1"] <= e["u1"] + 0.05 and o["z0"] >= e["z0"] - 0.05 and o["z1"] <= e["z1"] + 0.05) < 2]
        K.sort(key=lambda e: -e.get("stimmen", 0)); S = []
        for e in K:
            if all(iou(e, o) < 0.5 for o in S): S.append(e)
        # gruppieren (Union-Find ueber Nachbarschaft)
        par = list(range(len(S)))
        def f(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        for i, p in enumerate(S):
            for j, q in enumerate(S[:i]):
                uo = min(p["u1"], q["u1"]) - max(p["u0"], q["u0"]); zo = min(p["z1"], q["z1"]) - max(p["z0"], q["z0"]); bu = min(p["u1"] - p["u0"], q["u1"] - q["u0"]); bz = min(p["z1"] - p["z0"], q["z1"] - q["z0"])
                if (-a.luecke < uo <= 0.05 and zo > 0.6 * bz) or (-a.luecke < zo <= 0.05 and uo > 0.6 * bu) or (uo > 0.3 * bu and zo > 0.3 * bz): par[f(i)] = f(j)
        G = {}
        for i, p in enumerate(S): G.setdefault(f(i), []).append(p)
        fen = []
        for g in G.values():
            u0 = min(p["u0"] for p in g); u1 = max(p["u1"] for p in g); z0 = min(p["z0"] for p in g); z1 = max(p["z1"] for p in g)
            sp = sorted({round(0.5 * (p["u0"] + p["u1"]), 1): p for p in g}.values(), key=lambda p: p["u0"]); teiler = [round(0.5 * (sp[k]["u1"] + sp[k + 1]["u0"]), 3) for k in range(len(sp) - 1) if sp[k + 1]["u0"] - sp[k]["u1"] > -0.05]
            ze = sorted({round(0.5 * (p["z0"] + p["z1"]), 1): p for p in g}.values(), key=lambda p: p["z0"]); ka = [round(0.5 * (ze[k]["z1"] + ze[k + 1]["z0"]), 3) for k in range(len(ze) - 1) if ze[k + 1]["z0"] - ze[k]["z1"] > -0.05]
            fen.append(dict(u0=round(u0, 3), u1=round(u1, 3), z0=round(z0, 3), z1=round(z1, 3), teiler=teiler, kaempfer=ka[0] if len(ka) == 1 else None, scheiben=len(g), stimmen_min=min(p.get("stimmen", 0) for p in g)))
        # Sprossen (Nutzer 15.11.: "trifft der Erkenner auch die Streben innerhalb des Fensters?"): je Scheibe duenne dunkle Linien im Ortho - Helligkeitsprofil quer,
        # Einbruch gegen den gleitenden Median > 0,05, hoechstens 6 cm breit, nicht am Scheibenrand; gilt nur, wenn die Linie ueber >= 70 % der Scheibe durchlaeuft.
        grau = hsv[..., 2]
        def linien(c, achse):
            from scipy.ndimage import median_filter, label
            prof = c.mean(axis=achse); n_ = len(prof); k = max(5, int(0.25 / zl) | 1)
            if n_ < 12: return []
            ein = median_filter(prof, size=k, mode="nearest") - prof; lab, m = label(ein > 0.05); out = []
            for q in range(1, m + 1):
                ix = np.flatnonzero(lab == q); mi = 0.5 * (ix[0] + ix[-1])
                if len(ix) * zl > 0.06 or mi < 0.06 / zl or mi > n_ - 1 - 0.06 / zl: continue
                streifen = c[:, ix] if achse == 0 else c[ix, :]; quer = streifen.mean(axis=1 if achse == 0 else 0)
                if (quer < np.median(c) - 0.03).mean() >= 0.7: out.append(mi)
            out = [m_ for k_, m_ in enumerate(out) if k_ == 0 or (m_ - out[k_ - 1]) * zl > 0.08]; t_ = [(m_ + 0.5) / n_ for m_ in out]; gut = []          # doppelte weg; dann REGEL: Sprossen teilen die Scheibe gleichmaessig
            for m_, t in zip(out, t_):                                    # (1/2, Drittel, Viertel) und stehen ab Dritteln spiegelbildlich - Einzellinien woanders sind Spiegelungen, Draehte, Vorhangkanten
                if abs(t - 0.5) < 0.12 or any(abs(t - k_ / q_) < 0.07 and any(abs(o - (1 - t)) < 0.07 for o in t_) for q_ in (3, 4) for k_ in range(1, q_)): gut.append(m_)
            return gut
        # je Scheibe messen, dann REGELMAESSIGKEIT: gleich grosse Scheiben einer Fassade tragen dasselbe Sprossenbild - das haeufigste gemessene Muster (Anzahl), Lagen gemittelt, gilt fuer alle
        for p in S:
            x0, x1, y0, y1 = px(p, 0.0); c = grau[max(y0, 0):y1, max(x0, 0):x1]; p["_v"] = []; p["_h"] = []
            if c.size >= 100: p["_v"] = [(m_ + 0.5) / c.shape[1] for m_ in linien(c, 0)]; p["_h"] = [(m_ + 0.5) / c.shape[0] for m_ in linien(c, 1)]
        import collections
        for p in S:
            gl = [q for q in S if abs((q["u1"] - q["u0"]) / (p["u1"] - p["u0"]) - 1) < 0.1 and abs((q["z1"] - q["z0"]) / (p["z1"] - p["z0"]) - 1) < 0.1]
            for key in ("_v", "_h"):
                zahl = collections.Counter(len(q[key]) for q in gl if q[key]); n_m = zahl.most_common(1)[0][0] if zahl and sum(zahl.values()) >= max(2, 0.4 * len(gl)) else 0
                mus = [q[key] for q in gl if len(q[key]) == n_m]; p[key + "m"] = [float(np.mean([m_[k_] for m_ in mus])) for k_ in range(n_m)] if n_m else []
        for w in fen:
            w["sprossen"] = []
            for p in S:
                if not (p["u0"] >= w["u0"] - 0.02 and p["u1"] <= w["u1"] + 0.02 and p["z0"] >= w["z0"] - 0.02 and p["z1"] <= w["z1"] + 0.02): continue
                bu = p["u1"] - p["u0"]; bz = p["z1"] - p["z0"]
                w["sprossen"] += [[round(p["u0"] + t * bu, 3), round(p["z0"], 3), round(p["u0"] + t * bu, 3), round(p["z1"], 3)] for t in p["_vm"]]
                w["sprossen"] += [[round(p["u0"], 3), round(p["z1"] - t * bz, 3), round(p["u1"], 3), round(p["z1"] - t * bz, 3)] for t in p["_hm"]]
        fen.sort(key=lambda w: (round(w["z0"]), w["u0"])); erg[fid] = dict(o=F["o"], d=F["d"], n=F["n"], fenster=fen, fotos=X.get("fotos", [])[:4])
        for w in fen:
            x0, x1, y0, y1 = px(w, 0.0); cv2.rectangle(im, (x0, y0), (x1, y1), (0, 255, 0), 2)
            for t in w["teiler"]: X_ = int((t - r["u0"]) / zl); cv2.line(im, (X_, y0), (X_, y1), (0, 200, 255), 1)
            if w["kaempfer"]: Y_ = int((r["z1"] - w["kaempfer"]) / zl); cv2.line(im, (x0, Y_), (x1, Y_), (0, 200, 255), 1)
            for a0, b0, a1, b1 in w.get("sprossen", []): cv2.line(im, (int((a0 - r["u0"]) / zl), int((r["z1"] - b0) / zl)), (int((a1 - r["u0"]) / zl), int((r["z1"] - b1) / zl)), (255, 0, 255), 1)
        cv2.imwrite(os.path.join(a.ortho, f"fenster_{fid}.jpg"), im); print(f"{fid}: {len(fen)} Fenster aus {len(S)} Scheiben ({len(X['elemente'])} Kaesten): " + "; ".join(f"u {w['u0']:.2f}..{w['u1']:.2f} z {w['z0']:.2f}..{w['z1']:.2f} T{len(w['teiler'])} Spr{len(w.get('sprossen', []))}" for w in fen))
    aus = a.aus or os.path.join(a.ortho, "fenster.json"); json.dump(erg, open(aus, "w"), indent=1); print("->", aus)


if __name__ == "__main__":
    sys.exit(main())

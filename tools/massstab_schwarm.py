#!/usr/bin/env python3
"""massstab_schwarm.py - Massstab aus MEHREREN unabhaengigen Quellen sammeln, auf Verträglichkeit pruefen, offen ausweisen (Register BP).

Warum: Der Modellmassstab haengt sonst allein an den Bodenankern (amtliche LoD2/DGM1). Liegen diese oder die Hoehenverzerrung daneben, merkt es keine
Pruefung (Register BJ). Jede Quelle liefert  s = wahre Meter / Modellmeter  (1,0 = Modell stimmt) mit Unsicherheit; eine Quelle ist ein Plug-in:
modelle/<objekt>/audit/massstab_<quelle>.json (Schema: quelle, richtung horizontal|vertikal|vertikal_boden, unabhaengig_von, abhaengig_von, median, mad, sigma, n, annahmen, blind).
Eingebaut: 'bodenanker' (Referenz, abhaengig: s_sigma der Ausrichtung), 'dom1_gipfel' (Gipfelzelle Laser gegen Wolkenmaximum; schwach).
Plug-ins: massstab_quelle_gps.py (EXIF-GPS der Fotos), massstab_quelle_normobjekt*.py (Personen u. a.), massstab_quelle_lod2.py (Nachbarhoehen).
Regeln: (1) Widerspruchsregel CLAUDE.md 5 - Quellen, die sich nicht vertragen (|ds| > K * sqrt(sig_i^2 + sig_j^2), K=2), werden NICHT gemittelt; es wird die
groesste vertraegliche Gruppe UNABHAENGIGER Quellen gebildet, die uebrigen stehen als Widerspruch im Bericht. (2) Unsicherheit je Quelle = max(angegebenes sigma, 1,4826*MAD/sqrt(n)).
(3) Kombination nur innerhalb der vertraeglichen Gruppe (inverse Varianz) - und nur als Gegenpruefer: der Bericht aendert KEINEN Sollwert und keine Ausrichtung.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/massstab_schwarm.py modelle/<objekt>/objekt.json [--k 2.0]
"""
import sys, os, json, glob, math, argparse, itertools, numpy as np

def dom1_gipfel(od, obj, wolke):
    """Wolkenmaximum in der DOM1-Gipfelzelle (+-0,5 m) gegen DOM1-Hoehe. Schwach: DOM1 sieht Nadeln nicht, die Wolke ggf. schon (Nadel hoeher -> s < 1 verfaelscht)."""
    try:
        L = obj["laser"]; W = np.load(L["fenster_npy"]) - float(L["gelaende_m"]); pr = np.unravel_index(np.nanargmax(W), W.shape)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        A = json.load(open(os.path.join(od, "anker3d.json"))); ns = {}; src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "masspruefung_daten.py")).read()
        exec(src[src.index("def utm32"):src.index("E,N=utm32")], {"math": math}, ns)
        lat, lon = [float(x) for x in src[src.index("LAT,LON="):].split("=")[1].split("#")[0].split(",")]
        E, N = ns["utm32"](lat, lon); x0, y0 = 414000.5, 5316999.5; c = int(E - x0); r = int(y0 - N)
        Ec = x0 + (c - 30 + pr[1]); Nc = y0 - (r - 30 + pr[0]); d = np.array([Ec - A["mitte_utm"][0], Nc - A["mitte_utm"][1]])
        X = float(d @ np.array(A["xhat_utm"])); Y = float(d @ np.array(A["yhat_utm"])); P = np.load(wolke).astype(float)
        k = (np.abs(P[:, 0] - X) < 0.5) & (np.abs(P[:, 1] - Y) < 0.5)
        if k.sum() < 8: return None
        zmax = float(np.percentile(P[k, 2], 99)); zd = float(W[pr])
        return dict(quelle="dom1_gipfel", richtung="vertikal", median=round(zd / zmax, 4), mad=0.0, sigma=0.03, n=1, unabhaengig_von=["Bodenanker", "Fotopicks"], abhaengig_von=["Wolke (Hoehe)"],
                    annahmen=["ANNAHME: Wolkenmaximum der Gipfelzelle (p99) = Dachspitze; sigma 3 % gesetzt (Nadel/Goldkugeln, Zelle 1 m, Lage +-0,7 m)"], blind=["eine Zelle; Nadel unsichtbar fuer DOM1"], belege=dict(dom1=zd, wolke=zmax))
    except Exception as e:
        return dict(quelle="dom1_gipfel", fehler=str(e))

def laden(od):
    Q = []
    for f in sorted(glob.glob(os.path.join(od, "audit", "massstab_*.json"))):
        if os.path.basename(f) == "massstab_schwarm.json": continue
        try: Q.append(json.load(open(f)))
        except Exception as e: Q.append(dict(quelle=os.path.basename(f), fehler=str(e)))
    return Q

def unsicherheit(q):
    s = q.get("sigma") or 0.0; n = q.get("n") or 0; mad = q.get("mad") or 0.0
    return max(s, 1.4826 * mad / math.sqrt(n) if n > 0 else 0.0, 0.005)

def groesste_vertraegliche_gruppe(Q, K):
    """Teilmenge mit paarweiser Vertraeglichkeit |ds| <= K*sqrt(si^2+sj^2), groesste zuerst (bei Gleichstand kleinste Gesamtunsicherheit)."""
    best = ()
    for r in range(len(Q), 0, -1):
        for g in itertools.combinations(range(len(Q)), r):
            if all(abs(Q[i]["median"] - Q[j]["median"]) <= K * math.hypot(Q[i]["_u"], Q[j]["_u"]) for i, j in itertools.combinations(g, 2)):
                if r > len(best) or (r == len(best) and sum(Q[i]["_u"] for i in g) < sum(Q[i]["_u"] for i in best)): best = g
        if best: break
    return best

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--k", type=float, default=2.0); ap.add_argument("--wolke"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt)); Q = laden(od)
    ar = os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-nord.json")
    if os.path.exists(ar):
        sp = json.load(open(ar))["transformation"]["s_sigma_prozent"] / 100.0
        Q.insert(0, dict(quelle="bodenanker", richtung="isotrop", median=1.0, mad=0.0, sigma=round(sp, 4), n=1, unabhaengig_von=[], abhaengig_von=["LoD2-Boden", "DGM1"], referenz=True,
                         annahmen=["Definition: das Modell ist auf diese Anker ausgerichtet; s=1 per Konstruktion, sigma = Streuung der Ausrichtung"], blind=["Hoehenverzerrung ueber den Ankern", "gemeinsamer Fehler der amtlichen Anker"]))
    wolke = a.wolke or os.path.join(od, "sfm", "dicht_nord_entzerrt.npy")
    if os.path.exists(wolke):
        d = dom1_gipfel(od, obj, wolke)
        if d: Q.append(d)
    ungueltig = [q for q in Q if q.get("belastbar") is False]
    Q = [q for q in Q if q.get("fehler") is None and q.get("median") is not None and q.get("belastbar") is not False]
    keine = [q for q in laden(od) if q.get("median") is None]
    for q in Q: q["_u"] = unsicherheit(q)
    print(f"{'Quelle':16}{'Richtung':16}{'n':>4}{'s':>8}{'MAD':>7}{'Unsicherh.':>11}   Abhaengigkeit")
    for q in Q: print(f"{q['quelle']:16}{q['richtung']:16}{q.get('n') or 0:4d}{q['median']:8.3f}{q.get('mad') or 0:7.3f}{q['_u']:11.3f}   {'REFERENZ ' if q.get('referenz') else ''}haengt an: {', '.join(q.get('abhaengig_von') or ['-'])}")
    for q in ungueltig: print(f"{q.get('quelle', '?'):16}(NICHT belastbar, ausgeschlossen: {q.get('unbelastbar_grund')})")
    for q in keine: print(f"{q.get('quelle', '?'):16}(kein Ergebnis: {q.get('hinweis') or q.get('fehler') or 'leer'})")
    abh = [q for q in Q if not q.get("referenz") and any("bodenanker" in x.lower() for x in (q.get("abhaengig_von") or []))]       # Kameraposen aus Bodenankern: pruefen die LOKALE Metrik, beweisen den Massstab nicht
    unabh = [q for q in Q if not q.get("referenz") and q not in abh]
    for q in abh: print(f"  [abhaengig] {q['quelle'][:40]}: s={q['median']:.3f} +- {q['_u']:.3f} - zaehlt NICHT als unabhaengiger Beleg (haengt an Bodenankern), prueft die lokale Metrik/Verzerrung")
    if not unabh: print("keine unabhaengige Quelle"); return
    # Verträglichkeit unabhaengiger Quellen untereinander und gegen die Referenz (s=1)
    ref = next((q for q in Q if q.get("referenz")), None); bericht = dict(quellen=[{k: v for k, v in q.items() if not k.startswith("_") and k != "schaetzungen"} for q in Q])
    gruppe = groesste_vertraegliche_gruppe(unabh, a.k); G = [unabh[i] for i in gruppe]; W = [1 / q["_u"] ** 2 for q in G]
    s = sum(w * q["median"] for w, q in zip(W, G)) / sum(W); u = 1 / math.sqrt(sum(W))
    wid = [q["quelle"] for q in unabh if q not in G]
    print(f"\nVertraegliche Gruppe unabhaengiger Quellen (K={a.k}): {[q['quelle'] for q in G]} -> s = {s:.3f} +- {u:.3f} (inverse Varianz, nur innerhalb der Gruppe)")
    if wid: print("WIDERSPRUCH (nicht gemittelt, CLAUDE.md 5):", wid)
    if ref:
        dz = (s - 1.0) / math.hypot(u, ref["_u"]); print(f"Gegen die Bodenanker-Referenz: s - 1 = {s - 1:+.3f}, {dz:+.1f} Sigma (gemeinsame Unsicherheit {math.hypot(u, ref['_u']):.3f}) -> " + ("vertraeglich" if abs(dz) <= a.k else "WIDERSPRUCH: Ankermassstab oder Quellen pruefen"))
        bericht["gegen_referenz"] = dict(s=round(s, 4), u=round(u, 4), sigma_abstand=round(dz, 2), vertraeglich=bool(abs(dz) <= a.k))
    bericht["abhaengige_quellen"] = [dict(quelle=q["quelle"], s=q["median"], u=round(q["_u"], 4)) for q in abh]
    bericht.update(gruppe=[q["quelle"] for q in G], s=round(s, 4), u=round(u, 4), widerspruch=wid, k=a.k, keine_ergebnisse=[q.get("quelle") for q in keine])
    json.dump(bericht, open(os.path.join(od, "audit", "massstab_schwarm.json"), "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    main()

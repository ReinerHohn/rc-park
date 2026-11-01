#!/usr/bin/env python3
"""masse_aus_profilen.py - STUFE C: Masse, die bisher von Hand aus Werkzeugausgaben in masse.json uebertragen wurden, schreibt das Werkzeug
selbst - nach REGELN, die als Daten in objekt.json["masse_regeln"] stehen. Quelle, Zahlenherkunft und Historie je Mass automatisch.

Datenquellen (Ausgaben der Kette): profile_baender_<koerper>.json (Baender, Perioden), profile_generator.json, merkmal_<farbe>_<seite>.json
(wolke_farbmerkmal), anker3d.json, die dichte Wolke (fuer Kreisfits), masse.json selbst (Formeln ueber andere Masse).
Regeltypen (params je Regel):
  band_z        koerper, auswahl, lage(z0|z1|mitte)          auswahl: vor_kupfer_1 | kupfer_1 | traufe_vor_letztem_kupfer | klasse:<k>:<index> | stein_ab:<min_hoehe>
  band_r2       koerper, auswahl[, minus:<massname>]          2 x Aussenradius des Bandes (minus einem anderen Mass, z. B. D)
  band_r        koerper, auswahl                               Aussenradius
  baender_r2_median koerper, zwischen:[massA, massB], klassen  2 x Median r der Baender im Hoehenbereich
  band_periode  koerper, auswahl                               Farbperiode (Schichthoehe) des Bandes
  perioden_gruppen koerper, bereich:[zA, zB], ziel(unten|oben|grenze), min_staerke   Fenster-Perioden in zwei Gruppen (klein/gross) teilen
  periode_fenster koerper, bereich:[massA, massB], min_staerke  staerkste Fensterperiode im Bereich
  periode_quer  koerper, bereich:[zA, zB], min_staerke, runden  Median der Quer-Perioden (Blocklaenge)
  anker_z       name                                           z eines Ankers aus anker3d.json
  differenz     a, b                                           Mass/Anker/Regelwert a minus b (Namen aus masse oder vorher gerechneten Regeln)
  merkmal       datei, feld                                    Wert aus merkmal_*.json
  kreis_achse   zone{z:[..], tief:[..], quer:[..]}, feld(tief|quer|r)   Kreisfit an Wolkenpunkte der Zone (Rundkoerper-Achse)
  konstante     wert, grund                                    ausdruecklich gesetzter Wert mit Begruendung
  bleibt        grund                                          nicht automatisch ableitbar - bleibt Handwert (wird im Bericht als Stufe C gefuehrt)
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/masse_aus_profilen.py modelle/<objekt>/objekt.json [--schreiben] [--seite nord]
Ohne --schreiben: Tabelle alt -> neu. Mit --schreiben: masse.json aktualisiert (Historie nur bei Aenderung > Rundung), Bericht masse_regeln_bericht.json.
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bauteile import lade_masse, seite_achsen

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--schreiben", action="store_true"); ap.add_argument("--seite", default="nord")
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); R = obj.get("masse_regeln")
    if not R: sys.exit("objekt.json['masse_regeln'] fehlt")
    mp = os.path.join(od, "masse.json"); MJ = json.load(open(mp)); M = MJ["masse"]; MW = lade_masse(mp)
    AN = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    B = {}
    for k in obj.get("koerper", {}):
        fp = os.path.join(od, f"profile_baender_{k}.json")
        if os.path.exists(fp): B[k] = json.load(open(fp))
    P = None
    def wolke():
        nonlocal P
        if P is None: P = np.load(os.path.join(od, f"sfm/dicht_{a.seite}_entzerrt.npy")).astype(float)
        return P
    neu = {}
    def wert_von(name):
        if name in neu: return neu[name]["wert"]
        if name in MW: return MW[name]
        try: return float(eval(name, {"__builtins__": {}}, dict(MW)))                      # Formel ueber Masse, z. B. "-DB / 2"
        except Exception: pass
        if name in AN: return AN[name]["xyz"][2]
        return float(name)
    def waehle(bd, auswahl):
        bl = bd["baender"]; kup = [i for i, b in enumerate(bl) if b["klasse"] == "kupfer"]
        if auswahl == "kupfer_1": return bl[kup[0]]
        if auswahl == "kupfer_letztes": return bl[kup[-1]]
        if auswahl == "vor_kupfer_1": return bl[kup[0] - 1]
        if auswahl == "traufe_vor_letztem_kupfer":
            i = kup[-1] - 1
            while i >= 0 and bl[i]["klasse"] not in ("traufe", "gesims"): i -= 1
            return bl[i]
        if auswahl.startswith("klasse:"):
            _, k, idx = auswahl.split(":"); c = [b for b in bl if b["klasse"] == k]; return c[int(idx)]
        if auswahl.startswith("stein_ab:"):
            h = float(auswahl.split(":")[1]); return next(b for b in bl if b["klasse"] == "stein" and b["z1"] - b["z0"] >= h)
        raise ValueError(auswahl)
    def lage(b, l): return b["z0"] if l == "z0" else b["z1"] if l == "z1" else round((b["z0"] + b["z1"]) / 2, 3)
    bericht = []
    for reg in R:
        name, typ, p = reg["masse"], reg["regel"], reg.get("params", {}); rnd = reg.get("runden", 2); herk = ""
        try:
            if typ == "band_z":
                b = waehle(B[p["koerper"]], p["auswahl"]); w = lage(b, p.get("lage", "mitte")); herk = f"Band {p['koerper']} {b['klasse']} {b['z0']}-{b['z1']} m ({p.get('lage', 'mitte')})"
            elif typ in ("band_r2", "band_r"):
                b = waehle(B[p["koerper"]], p["auswahl"]); w = (2 if typ == "band_r2" else 1) * b["r"]; herk = f"Band {p['koerper']} {b['klasse']} {b['z0']}-{b['z1']} m, Aussenradius {b['r']}"
                if p.get("minus"): w -= wert_von(p["minus"]); herk += f" minus {p['minus']} {wert_von(p['minus']):.2f}"
            elif typ == "baender_r2_median":
                zA, zB = (wert_von(x) for x in p["zwischen"]); bb = [b for b in B[p["koerper"]]["baender"] if b["z0"] >= zA - 0.01 and b["z1"] <= zB + 0.01 and b["klasse"] in p.get("klassen", ["hell", "stein", "offen"])]
                w = 2 * float(np.median([b["r"] for b in bb])); herk = f"2 x Median r von {len(bb)} Baendern {zA:.1f}-{zB:.1f} m ({', '.join(str(b['r']) for b in bb)})"
            elif typ == "band_periode":
                b = waehle(B[p["koerper"]], p["auswahl"]); w = b["farbperiode"]["periode_m"]; herk = f"Farbperiode Band {p['koerper']} {b['klasse']} {b['z0']}-{b['z1']} m (Staerke {b['farbperiode']['staerke']})"
            elif typ == "perioden_gruppen":
                zA, zB = p["bereich"]; fs = [q for q in B[p["koerper"]]["farbperioden"] if q["staerke"] >= p.get("min_staerke", 0.3) and q["z0"] >= zA and q["z1"] <= zB]
                per = np.array([q["periode_m"] for q in fs]); schwelle = (per.min() + per.max()) / 2; unten = [q for q in fs if q["periode_m"] < schwelle]; oben = [q for q in fs if q["periode_m"] >= schwelle]
                if p["ziel"] == "unten": w = float(np.median([q["periode_m"] for q in unten]))
                elif p["ziel"] == "oben": w = float(np.median([q["periode_m"] for q in oben]))
                else: w = (max(q["z1"] for q in unten) + min(q["z0"] for q in oben)) / 2 if unten and oben else float("nan")
                herk = f"Fensterperioden {zA}-{zB} m (Staerke >= {p.get('min_staerke', 0.3)}): klein {[(q['z0'], q['periode_m']) for q in unten]}, gross {[(q['z0'], q['periode_m']) for q in oben]}"
            elif typ == "periode_fenster":
                zA, zB = (wert_von(x) for x in p["bereich"]); fs = [q for q in B[p["koerper"]]["farbperioden"] if q["staerke"] >= p.get("min_staerke", 0.3) and q["z0"] >= zA - 0.5 and q["z1"] <= zB + 0.5]
                q = max(fs, key=lambda q: q["staerke"]); w = q["periode_m"]; herk = f"staerkste Fensterperiode {q['z0']}-{q['z1']} m: {q['periode_m']} (Staerke {q['staerke']}) von {len(fs)} Fenstern"
            elif typ == "periode_quer":
                zA, zB = p["bereich"]; fs = [q for q in B[p["koerper"]].get("farbperioden_quer", []) if q["staerke"] >= p.get("min_staerke", 0.3) and q["z0"] >= zA and q["z1"] <= zB]
                w = float(np.median([q["periode_m"] for q in fs])); herk = f"Median der Quer-Perioden {zA}-{zB} m aus {len(fs)} Fenstern {[q['periode_m'] for q in fs]}"
            elif typ == "anker_z": w = AN[p["name"]]["xyz"][2]; herk = f"Anker {p['name']} ({AN[p['name']].get('quelle', '')[:70]})"
            elif typ == "differenz": w = wert_von(p["a"]) - wert_von(p["b"]); herk = f"{p['a']} {wert_von(p['a']):.2f} - {p['b']} {wert_von(p['b']):.2f}"
            elif typ == "merkmal": d = json.load(open(os.path.join(od, p["datei"]))); w = d[p["feld"]]; herk = f"{p['datei']}: {p['feld']} ({d.get('punkte')} Punkte, Farbe {d.get('farbe')})"
            elif typ == "kreis_achse":
                Pw = wolke(); z = p["zone"]; tief, sgn, quer = seite_achsen(a.seite); it = 0 if tief == "x" else 1; iq = 1 - it
                k = (Pw[:, 2] >= z["z"][0]) & (Pw[:, 2] <= z["z"][1]) & (Pw[:, it] >= z["tief"][0]) & (Pw[:, it] <= z["tief"][1]) & (Pw[:, iq] >= z["quer"][0]) & (Pw[:, iq] <= z["quer"][1])
                X = Pw[k][:, :2]; A_ = np.c_[2 * X[:, 0], 2 * X[:, 1], np.ones(len(X))]; c = np.linalg.lstsq(A_, (X ** 2).sum(1), rcond=None)[0]
                for _ in range(2):
                    r_ = np.sqrt(max(c[2] + c[0] ** 2 + c[1] ** 2, 0)); res = np.abs(np.hypot(X[:, 0] - c[0], X[:, 1] - c[1]) - r_); X = X[res <= np.percentile(res, 80)]
                    A_ = np.c_[2 * X[:, 0], 2 * X[:, 1], np.ones(len(X))]; c = np.linalg.lstsq(A_, (X ** 2).sum(1), rcond=None)[0]
                r_ = float(np.sqrt(max(c[2] + c[0] ** 2 + c[1] ** 2, 0))); w = {"tief": float(c[0]), "quer": float(c[1]), "r": r_}[p["feld"]]
                herk = f"Kreisfit (robust) an {int(k.sum())} Wolkenpunkte z {z['z']}, Mitte ({c[0]:.2f}, {c[1]:.2f}), r {r_:.2f}"
            elif typ == "zylinder_an_wand":
                # Rundkoerper, der vor einer Wand vortritt (Treppenturm): robust sind FRONT (p2 der Tiefe) und SEHNE an der Wandebene,
                # nicht der Kreisfit am einseitigen Bogen. v = Vorsprung, c = halbe Sehne -> r = (c^2 + v^2) / (2 v); Mitte = Front + r.
                Pw = wolke(); z = p["zone"]; tief, sgn, quer = seite_achsen(a.seite); it = 0 if tief == "x" else 1; iq = 1 - it
                wand = wert_von(p["wand"]) if not isinstance(p["wand"], (int, float)) else p["wand"]; wa = abs(wand)
                k = (Pw[:, 2] >= z["z"][0]) & (Pw[:, 2] <= z["z"][1]) & (Pw[:, iq] >= z["quer"][0]) & (Pw[:, iq] <= z["quer"][1]) & (sgn * Pw[:, it] > wa + 0.05)
                front = float(np.percentile(sgn * Pw[k, it], 98)); v = front - wa
                # Sehne in HALBER Vorsprungstiefe (nicht an der Wand: dort mischen Eckquader und Wandrelief): c^2 = r^2 - (r - (v - d))^2
                d_ = v / 2; ks = k & (np.abs(sgn * Pw[:, it] - (wa + d_)) < 0.15); ys = Pw[ks, iq]; c = float(np.percentile(ys, 97) - np.percentile(ys, 3)) / 2; ym = float((np.percentile(ys, 97) + np.percentile(ys, 3)) / 2)
                h_ = v - d_; r_ = (c ** 2 + h_ ** 2) / (2 * h_) if h_ > 0.05 else float("nan"); mitte_t = sgn * (front - r_)
                w = {"tief": mitte_t, "quer": ym, "r": r_, "vorsprung": v}[p["feld"]]
                herk = f"Front {sgn * front:.2f} (p98 Tiefe, {int(k.sum())} Pkt.) vor Wand {wand:.2f}: Vorsprung {v:.2f}; halbe Sehne in {d_:.2f} m Tiefe {c:.2f} ({int(ks.sum())} Pkt.) -> r {r_:.2f}, Mitte ({mitte_t:.2f}, {ym:.2f})"
            elif typ == "konstante": w = p["wert"]; herk = "gesetzt: " + p["grund"]
            elif typ == "bleibt": bericht.append(dict(masse=name, status="bleibt_hand", grund=p["grund"], wert=M.get(name, {}).get("wert"))); continue
            else: raise ValueError("unbekannte Regel " + typ)
        except Exception as e:
            bericht.append(dict(masse=name, status="fehler", fehler=f"{type(e).__name__}: {e}")); continue
        if w is None or (isinstance(w, float) and np.isnan(w)): bericht.append(dict(masse=name, status="fehler", fehler="kein Wert")); continue
        w = round(float(w), rnd); alt = M.get(name, {}).get("wert"); neu[name] = dict(wert=w, herk=herk, typ=typ, alt=alt)
        bericht.append(dict(masse=name, status="abgeleitet", alt=alt, neu=w, herkunft=herk, regel=typ))
    print(f"{'Mass':22s} {'alt':>10s} {'neu':>8s}  Herkunft");
    for b in bericht:
        if b["status"] == "abgeleitet": print(f"{b['masse']:22s} {str(b['alt'])[:10]:>10s} {b['neu']:8.3g}  {b['herkunft'][:110]}")
        elif b["status"] == "bleibt_hand": print(f"{b['masse']:22s} {str(b['wert'])[:10]:>10s} {'bleibt':>8s}  {b['grund'][:110]}")
        else: print(f"{b['masse']:22s} {'':>10s} {'FEHLER':>8s}  {b['fehler'][:110]}")
    if a.schreiben:
        n_ae = 0
        for name, d in neu.items():
            alt = M.get(name, {}).get("wert"); altw = MW.get(name)
            quelle = f"masse_aus_profilen.py ({d['typ']}): {d['herk']}"
            if name not in M: M[name] = dict(wert=d["wert"], einheit="m", was=name, quelle=quelle, quelltyp="sfm_bodenanker"); n_ae += 1; continue
            if isinstance(altw, (int, float)) and abs(altw - d["wert"]) <= 0.5 * 10 ** (-2) + 1e-9 and not isinstance(alt, str):
                M[name]["quelle"] = quelle; continue                                        # gleicher Wert: nur Quelle nachziehen
            M[name].setdefault("historie", []).append({"datum": "auto", "alt": alt, "neu": d["wert"], "grund": quelle}); M[name]["wert"] = d["wert"]; M[name]["quelle"] = quelle; n_ae += 1
        json.dump(MJ, open(mp, "w"), indent=1, ensure_ascii=False); json.dump(dict(bericht=bericht), open(os.path.join(od, "masse_regeln_bericht.json"), "w"), indent=1, ensure_ascii=False)
        print(f"\nmasse.json: {len(neu)} Masse abgeleitet, {n_ae} geaendert/neu; {sum(1 for b in bericht if b['status'] == 'bleibt_hand')} bleiben Hand (Stufe C), {sum(1 for b in bericht if b['status'] == 'fehler')} Fehler")

if __name__ == "__main__":
    main()

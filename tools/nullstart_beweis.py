#!/usr/bin/env python3
"""nullstart_beweis.py - KOMPLETTER Nullstart N-mal und ein Beweis, wie gut er ist (Register BK).

Lauf:      python3 -I tools/nullstart_beweis.py modelle/martinstor/objekt.json --laeufe 3 [--streng] [--mapper global]
           (je Lauf: tools/nullstart.py komplett ab 'anlegen'; danach Sicherung von Pruefbericht, Masse, STL, Bericht unter <Datenplatte>/beweis_<datum>/lauf_<i>/)
Auswerten: python3 -I tools/nullstart_beweis.py modelle/martinstor/objekt.json --auswerten <beweisordner>   -> modelle/<objekt>/NULLSTART_BEWEIS.md
Was der Beweis zeigt (und was nicht):
  1. Wiederholbarkeit: Punktzahl, Streuung, welche Pruefungen in allen/einigen/keinem Lauf bestehen.
  2. UNABHAENGIGKEIT: Bestehensquote getrennt nach Quelltyp der Pruefung (lod2, laser_dom1, dokument = unabhaengig von der Referenz; sfm_bodenanker, foto_* = Messung aus Fotos;
     annahme/modell = nicht belegend). Eine hohe Quote bei lod2/laser/dokument ist der staerkere Beleg als die Gesamtzahl.
  3. Geometrie gegen die Referenz (Volumen, Hoehen), gemittelt ueber die Laeufe - die Referenz ist NICHT die Wahrheit, nur ein Vergleich.
  4. Ehrliche Grenzen: Vorwissen (Masse ohne Regel aus der Referenz), Hoehenunsicherheit Netz-Sigma.
"""
import sys, os, json, shutil, subprocess, argparse, time, glob, statistics, collections

def lauf_n(a, repo, od):
    zd = os.path.realpath(os.path.join(repo, "modelle", a.ziel)); basis = os.path.join(os.path.dirname(zd), f"beweis_{time.strftime('%Y%m%d_%H%M')}"); os.makedirs(basis, exist_ok=True)
    print("Beweisordner:", basis, flush=True)
    for i in range(1, a.laeufe + 1):
        t0 = time.time(); cmd = [sys.executable, "-I", "tools/nullstart.py", a.objekt, "--ziel", a.ziel, "--mapper", a.mapper, "--netzversuche", str(a.netzversuche)] + (["--streng"] if a.streng else [])
        log = os.path.join(basis, f"lauf_{i}.log"); print(f"Lauf {i}/{a.laeufe}: {' '.join(cmd[2:])}", flush=True)
        with open(log, "w") as f: rc = subprocess.run(cmd, cwd=repo, stdout=f, stderr=subprocess.STDOUT).returncode
        d = os.path.join(basis, f"lauf_{i}"); os.makedirs(d, exist_ok=True)
        for fn in ("pruefbericht.json", "masse.json", "masstabelle.json", "nullstart_bericht.json", "masse_regeln_bericht.json"):
            if os.path.exists(os.path.join(zd, fn)): shutil.copy2(os.path.join(zd, fn), d)
        stl = os.path.join(repo, "modelle", "stl", f"{a.ziel}_v4_1-87.stl")
        if os.path.exists(stl): shutil.copy2(stl, d)
        print(f"  rc {rc}, {time.time() - t0:.0f} s", flush=True)
    print("fertig:", basis)

def auswerten(a, repo, od):
    import numpy as np
    L = sorted(glob.glob(os.path.join(a.auswerten, "lauf_*/pruefbericht.json"))); n = len(L); R = [json.load(open(p)) for p in L]
    tab = json.load(open(os.path.join(os.path.dirname(L[0]), "masstabelle.json"))); qt = {p["name"]: (p.get("quelltyp") or "?", p.get("massstab") or "?") for p in tab["pruefungen"]}
    ref = json.load(open(os.path.join(od, "pruefbericht.json"))); T = []; M = ["# Nullstart-Beweis (automatisch)", "", f"{n} komplette Laeufe ab 'anlegen' ({time.strftime('%Y-%m-%d')}), Ordner `{a.auswerten}`.", ""]
    pb = [{p["name"]: bool(p["ok"]) for p in r["pruefungen"]} for r in R]; sc = [sum(d.values()) for d in pb]; tot = [len(d) for d in pb]
    M += ["## 1. Wiederholbarkeit", "", "| Lauf | bestanden | von | Summe Schrittzeiten s (parallele Schritte doppelt gezaehlt; Wanduhr steht im Lauflog) |", "|---|---|---|---|"]
    for i, (s, t) in enumerate(zip(sc, tot), 1):
        b = json.load(open(os.path.join(a.auswerten, f"lauf_{i}", "nullstart_bericht.json"))); dau = sum(x.get("sekunden", 0) for x in b["schritte"])
        M.append(f"| {i} | {s} | {t} | {dau:.0f} |")
    quote = [s / t for s, t in zip(sc, tot)]
    M += ["", f"Bestehensquote: Mittel {100 * statistics.mean(quote):.1f} %, min {100 * min(quote):.1f} %, max {100 * max(quote):.1f} %" + (f", Standardabweichung {100 * statistics.stdev(quote):.1f} Prozentpunkte" if n > 1 else ""),
          f"Referenz (zum Vergleich): {sum(p['ok'] for p in ref['pruefungen'])}/{len(ref['pruefungen'])}", ""]
    gem = sorted(set.intersection(*[set(d) for d in pb])); M += [f"**Nur Pruefungen, die in ALLEN {n} Laeufen vorkommen ({len(gem)}; die uebrigen heissen nach den gemessenen Bandfenstern und existieren je Lauf anders):** " + ", ".join(f"Lauf {i}: {sum(d[x] for x in gem)}/{len(gem)}" for i, d in enumerate(pb, 1)) + f"; in allen bestanden: {sum(all(d[x] for d in pb) for x in gem)}; nie: {sum(not any(d[x] for d in pb) for x in gem)}; flackernd: {sum(0 < sum(d[x] for d in pb) < n for x in gem)}", ""]
    namen = sorted(set().union(*[set(d) for d in pb])); immer = [x for x in namen if all(d.get(x, False) for d in pb)]; nie = [x for x in namen if not any(d.get(x, False) for d in pb)]; misch = [x for x in namen if x not in immer and x not in nie]
    M += [f"In allen Laeufen bestanden: {len(immer)} Pruefungen; nie bestanden: {len(nie)}; gemischt (flackernd): {len(misch)}.", ""]
    if nie: M += ["**Nie bestanden:**"] + [f"- {x}" for x in nie] + [""]
    if misch: M += ["**Flackernd:**"] + [f"- {x} ({sum(d.get(x, False) for d in pb)}/{n})" for x in misch] + [""]
    M += ["## 2. Unabhaengigkeit der Belege (Quelltyp der Pruefung)", "", "| Quelltyp | Pruefungen | Bestehensquote (Mittel ueber Laeufe) | Bedeutung |", "|---|---|---|---|"]
    bed = {"lod2": "amtlich, unabhaengig von Referenz und Fotos", "laser_dom1": "amtlich (Laser), unabhaengig", "dokument": "Dokument, unabhaengig", "sfm_bodenanker": "Messung aus Fotos + amtlichen Ankern", "foto_kalibriert": "Foto mit kalibrierter Kamera",
           "foto_verhaeltnis": "Foto-Verhaeltnis (relativ)", "foto_vollbild": "Foto Vollbild", "annahme": "ANNAHME - belegt nichts", "modell": "zirkulaer (Modell)"}
    G = collections.defaultdict(list)
    for x in namen: G[qt.get(x, ("?",))[0]].append(x)
    for q, xs in sorted(G.items(), key=lambda kv: -len(kv[1])): M.append(f"| {q} | {len(xs)} | {100 * statistics.mean([sum(d.get(x, False) for x in xs) / len(xs) for d in pb]):.0f} % | {bed.get(q, '')} |")
    unab = [x for q in ("lod2", "laser_dom1", "dokument") for x in G.get(q, [])]
    if unab: M += ["", f"**Unabhaengige Pruefungen (lod2, laser_dom1, dokument): {len(unab)}; Quote {100 * statistics.mean([sum(d.get(x, False) for x in unab) / len(unab) for d in pb]):.0f} %.**", ""]
    M += ["## 3. Geometrie gegen die Referenz (nur Vergleich)", ""]
    try:
        import trimesh
        vs = []
        for i in range(1, n + 1):
            f = glob.glob(os.path.join(a.auswerten, f"lauf_{i}", "*.stl"))
            if f: m = trimesh.load(f[0]); vs.append(abs(m.volume))
        rf = trimesh.load(os.path.join(repo, "modelle", "stl", "martinstor_v4_1-87.stl")); M += [f"STL-Volumen: Referenz {abs(rf.volume):.0f}, Nullstart {', '.join(f'{v:.0f}' for v in vs)} (relative Abweichung {', '.join(f'{100 * abs(v - abs(rf.volume)) / abs(rf.volume):.1f} %' for v in vs)})", ""]
    except Exception as e: M += [f"(STL-Vergleich nicht moeglich: {e})", ""]
    mm = [json.load(open(os.path.join(a.auswerten, f"lauf_{i}", "masse.json")))["masse"] for i in range(1, n + 1)]; mr = json.load(open(os.path.join(od, "masse.json")))["masse"]
    M += ["| Mass | Referenz | " + " | ".join(f"Lauf {i}" for i in range(1, n + 1)) + " | Streuung (max-min) |", "|---|---|" + "---|" * (n + 1)]
    for k in ("H_TOTAL", "UZ", "KRAG_TRAUFE", "GZ0", "GZ1", "ERKER_OBEN", "KONSOLE_Z1", "GX", "DACHHOEHE"):
        v = [m[k]["wert"] for m in mm if k in m and isinstance(m[k].get("wert"), (int, float))]
        if len(v) == n and k in mr: M.append(f"| {k} | {mr[k]['wert']} | " + " | ".join(f"{x}" for x in v) + f" | {max(v) - min(v):.2f} |")
    rb = [json.load(open(os.path.join(a.auswerten, f"lauf_{i}", "masse_regeln_bericht.json")))["bericht"] for i in range(1, n + 1) if os.path.exists(os.path.join(a.auswerten, f"lauf_{i}", "masse_regeln_bericht.json"))]
    if rb: M += ["", "Ableitung der Masse (Regeln): " + "; ".join(f"Lauf {i}: " + ", ".join(f"{k} {v}" for k, v in sorted(collections.Counter(x["status"] for x in b).items())) for i, b in enumerate(rb, 1))]
    M += ["", "## 4. Grenzen (ehrlich)", "", "- Masse OHNE Regel (32 von 59) stammen aus der Referenz; die Vorwissen-Messung zeigt, dass 22 davon von Pruefungen kontrolliert werden, 9 vom Generator nicht gelesen, 1 unkontrolliert (Register BI).",
          "- Sollwerte der Pruefungen stammen aus der Referenz-Masstabelle (Quellen: Laser/LoD2/Dokumente/Fotos); 'bestanden' heisst Uebereinstimmung mit diesen Quellen, nicht mit der Wirklichkeit.",
          "- Hoehen tragen die Netz-Unsicherheit (Sigma ca. 3 %, +-1,9 m bei 65 m); die Ausrichtung nutzt nur Bodenanker (Register BJ).", "- Die Suedwolke ist nicht Teil des Nullstart-Ergebnisses (verbogen, keine gueltige Ausrichtung)."]
    out = os.path.join(od, "NULLSTART_BEWEIS.md"); open(out, "w").write("\n".join(M) + "\n"); print("\n".join(M)); print("\ngeschrieben:", out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--laeufe", type=int, default=3); ap.add_argument("--ziel", default="martinstor_null"); ap.add_argument("--mapper", default="global")
    ap.add_argument("--netzversuche", type=int, default=2); ap.add_argument("--streng", action="store_true"); ap.add_argument("--auswerten")
    a = ap.parse_args(); repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); od = os.path.dirname(os.path.abspath(a.objekt))
    if a.auswerten: auswerten(a, repo, od)
    else: lauf_n(a, repo, od)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""sweetspot.py - Sweet Spot der dichten Stufe (Bildauflösung für PatchMatch) für EIN Objekt MESSEN statt behaupten (Register BM).

Der Sweet Spot ist objektabhängig (Fotos, Kameras, Detailgröße) - für das Martinstor gemessen, für andere Objekte nicht übertragbar.
Verfahren: auf dem vorhandenen Netz (modelle/<ziel>, z. B. nach einem Nullstart) die dichte Stufe mit ALLEN Fotos bei einer Leiter von Auflösungen
rechnen (tools/stufenversuch.py -> nullstart.py --ab dicht --dicht-extra "--max-size PX"), danach die Prüfungen vergleichen, die in ALLEN Stufen vorkommen
(Bandprüfungen tragen das gemessene Fenster im Namen und existieren je Lauf anders). Gewählt wird die KLEINSTE Auflösung, deren Quote um höchstens
--toleranz Prüfungen unter der besten liegt. ANNAHME: Rauschband +-3 Prüfungen (Register BL: ähnliche Einstellungen streuen um 44-50 von 54).
Ergebnis: modelle/<objekt>/sweetspot.json (Auflösung, Tabelle, Zeiten, Netz, Datum); nullstart.py --stufe auto liest es.

  python3 -I tools/sweetspot.py modelle/martinstor/objekt.json [--ziel martinstor_null] [--leiter 800 1000 1200 1600] [--toleranz 3]
  python3 -I tools/sweetspot.py modelle/martinstor/objekt.json --aus-ordner /pfad/stufen_xxx [/pfad/stufen_yyy ...] --px-aus-name   (nur auswerten)
Lauf kostet die Summe der Leiter (Martinstor: ca. 4+5+8+11 min). GPU: nur ein Job zur Zeit.
"""
import sys, os, json, re, argparse, subprocess, glob, time

def waehle_px(tabelle, toleranz):
    """tabelle: {px: {'ok': Anzahl gemeinsam bestanden, 'n': gemeinsame Pruefungen, 'sek': Zeit}} -> (px, Begründung)."""
    best = max(v["ok"] for v in tabelle.values())
    kand = sorted(px for px, v in tabelle.items() if v["ok"] >= best - toleranz)
    return kand[0], f"kleinste Aufloesung mit >= {best - toleranz} von {next(iter(tabelle.values()))['n']} gemeinsamen Pruefungen (beste Stufe: {best}, Toleranz {toleranz})"

def auswerten(ordner_px, toleranz):
    """ordner_px: {px: pfad zu einer Variante (mit pruefbericht.json, nullstart_bericht.json)} -> Tabelle ueber die gemeinsamen Pruefungen."""
    P = {px: {x["name"]: bool(x["ok"]) for x in json.load(open(os.path.join(d, "pruefbericht.json")))["pruefungen"]} for px, d in ordner_px.items()}
    gem = set.intersection(*[set(p) for p in P.values()]); T = {}
    for px, d in ordner_px.items():
        try: nb = json.load(open(os.path.join(d, "nullstart_bericht.json"))); sek = [s["sekunden"] for s in nb["schritte"] if s.get("schritt") == "dicht_nord"][-1]
        except Exception: sek = None
        T[px] = dict(ok=sum(P[px][x] for x in gem), n=len(gem), alle=f"{sum(P[px].values())}/{len(P[px])}", sek=sek)
    return T

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ziel", default="martinstor_null"); ap.add_argument("--leiter", nargs="+", type=int, default=[800, 1000, 1200, 1600])
    ap.add_argument("--toleranz", type=int, default=3); ap.add_argument("--aus-ordner", nargs="+"); ap.add_argument("--px-aus-name", action="store_true", help="Variantenname 'nXX_<px>' liefert die Aufloesung; nur Varianten ohne --fotos (n27_*) zaehlen")
    a = ap.parse_args(); repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); od = os.path.dirname(os.path.abspath(a.objekt))
    if a.aus_ordner:
        op = {}
        for d in a.aus_ordner:
            for v in sorted(glob.glob(os.path.join(d, "*"))):
                m = re.match(r"n27_(\d+)$", os.path.basename(v))
                if m and os.path.exists(os.path.join(v, "pruefbericht.json")): op[int(m.group(1))] = v
        basis = [v for d in a.aus_ordner for v in glob.glob(os.path.join(d, "basis"))]
        if basis and 1600 not in op: op[1600] = basis[0]
    else:
        var = [f"px{px}:--max-size {px}" for px in a.leiter]; cmd = [sys.executable, "-I", "tools/stufenversuch.py", a.objekt, "--ziel", a.ziel, "--varianten"] + var
        print("Leiter:", a.leiter, flush=True); r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True); print(r.stdout[-1500:])
        zd = os.path.realpath(os.path.join(repo, "modelle", a.ziel)); ords = sorted(d_ for d_ in glob.glob(os.path.join(os.path.dirname(zd), "stufen_*")) if os.path.isdir(d_))[-1]
        op = {px: os.path.join(ords, f"px{px}") for px in a.leiter if os.path.exists(os.path.join(ords, f"px{px}", "pruefbericht.json"))}
    if len(op) < 2: raise SystemExit(f"zu wenige Stufen ausgewertet: {sorted(op)}")
    T = auswerten(op, a.toleranz); px, grund = waehle_px(T, a.toleranz)
    out = dict(datum=time.strftime("%Y-%m-%d %H:%M"), px=px, grund=grund, toleranz=a.toleranz, tabelle={str(k): v for k, v in sorted(T.items())}, ziel=a.ziel,
               hinweis="objektabhaengig; ANNAHME Rauschband +-3 Pruefungen (Register BL); ein Netz = ein Messpunkt - bei Aenderung der Fotos neu messen")
    json.dump(out, open(os.path.join(od, "sweetspot.json"), "w"), indent=1, ensure_ascii=False)
    for k, v in sorted(T.items()): print(f"  {k:5d} px  {v['ok']}/{v['n']} gemeinsam  (alle {v['alle']})  dichte Stufe {v['sek']} s")
    print(f"=> Sweet Spot {px} px - {grund}\ngeschrieben: {os.path.join(od, 'sweetspot.json')}")

if __name__ == "__main__":
    main()

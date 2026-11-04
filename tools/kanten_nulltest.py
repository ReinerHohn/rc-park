#!/usr/bin/env python3
"""kanten_nulltest.py - BEWEIS, dass die Kanten-Schleife (foto_kanten_loop.py) einen Teilfehler findet - und keinen erfindet (Register BX, PIPELINE_H0.md 8c).
Ablauf (je Objekt, mit kalibrierten Kameras K-<nr>.json):
  1. Leerlauf   : Versatz 0 (Kontrolle: Wiederholbarkeit, darf nichts 'finden')
  2. Teilversatz: die 4 Eck-Tuermchen um --versatz Meter nach aussen (dx dy dz), Rest des Modells unveraendert
Pro Foto: Verhaeltnis r = Median_px(Tuermchen, nach Kameraanpassung, verschoben) / Median_px(... Leerlauf) und Anstieg in px.
Gefunden, wenn r >= --faktor UND Anstieg >= --min-px. Bestanden, wenn
  (a) Leerlauf gegen die gespeicherte Referenz (audit/foto_kanten/foto_kanten.json): |Aenderung| <= --rausch-px je Foto und Region (Wiederholbarkeit),
  (b) Teilversatz in >= --mehrheit der Fotos gefunden (Gleichrichtungsregel).
Die Grenzen (Faktor/min-px/Rauschen) sind Daten aus dem ersten Nulltest 2026-11-03 (Register BX), nicht Handwerte: Rauschen = beobachtete Streuung des Leerlaufs.
Ergebnis: audit/kanten_nulltest.json (vom Pruefstand gelesen); Exit 0 = bestanden, 1 = nicht bestanden.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/kanten_nulltest.py [--fotos 030 031 040 041] [--versatz 1.0 1.0 0] [--objekt modelle/martinstor]
"""
import sys, os, json, time, argparse, subprocess

def lauf(objekt, fotos, zusatz, zielname):
    d = os.path.join(objekt, "audit", zielname)
    cmd = [sys.executable, "-W", "ignore", "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "foto_kanten_loop.py"), "--objekt", objekt, "--fotos", *fotos, *zusatz]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: sys.exit("foto_kanten_loop fehlgeschlagen: " + r.stderr[-400:])
    return json.load(open(os.path.join(d, "foto_kanten.json")))["fotos"]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--objekt", default="modelle/martinstor"); ap.add_argument("--fotos", nargs="*", default=["030", "031", "040", "041"])
    ap.add_argument("--versatz", nargs=3, type=float, default=[1.0, 1.0, 0.0]); ap.add_argument("--faktor", type=float, default=1.4); ap.add_argument("--min-px", type=float, default=2.0)
    ap.add_argument("--rausch-px", type=float, default=0.8); ap.add_argument("--mehrheit", type=float, default=0.6); ap.add_argument("--region", default="Tuermchen")
    a = ap.parse_args(); v = a.versatz
    leer = lauf(a.objekt, a.fotos, ["--versatz", "0", "0", "0"], "foto_kanten_versatz_0_0_0")
    tv = lauf(a.objekt, a.fotos, ["--versatz-tuermchen", *map(str, v)], "foto_kanten_tuerm_%g_%g_%g" % tuple(v))
    ref = {}
    rp = os.path.join(a.objekt, "audit", "foto_kanten", "foto_kanten.json")
    if os.path.exists(rp): ref = json.load(open(rp))["fotos"]
    je_foto = {}; rausch_max = 0.0; gefunden = 0
    for nr in a.fotos:
        if nr not in leer or nr not in tv: continue
        l = leer[nr]["nachher"].get(a.region, {}).get("median_px"); t = tv[nr]["nachher"].get(a.region, {}).get("median_px")
        if l is None or t is None: continue
        r = t / max(l, 0.1); anstieg = t - l; ok = (r >= a.faktor) and (anstieg >= a.min_px); gefunden += ok
        rau = None
        if nr in ref:
            rau = max(abs(leer[nr]["nachher"][k]["median_px"] - ref[nr]["nachher"][k]["median_px"]) for k in leer[nr]["nachher"] if k in ref[nr]["nachher"]); rausch_max = max(rausch_max, rau)
        je_foto[nr] = dict(leerlauf_px=l, verschoben_px=t, faktor=round(r, 2), anstieg_px=round(anstieg, 1), gefunden=bool(ok), leerlauf_gegen_referenz_max_px=None if rau is None else round(rau, 2))
    n = len(je_foto); anteil = gefunden / n if n else 0.0
    best_a = rausch_max <= a.rausch_px; best_b = anteil >= a.mehrheit
    erg = dict(stand=time.strftime("%Y-%m-%d %H:%M"), region=a.region, versatz_m=v, grenzen=dict(faktor=a.faktor, min_px=a.min_px, rausch_px=a.rausch_px, mehrheit=a.mehrheit),
               je_foto=je_foto, gefunden_anteil=round(anteil, 2), rausch_max_px=round(rausch_max, 2), wiederholbar=bool(best_a), teilversatz_gefunden=bool(best_b), bestanden=bool(best_a and best_b),
               grenze_der_methode="Starrversatz des GANZEN Modells ist unsichtbar (Kamera gleicht aus); nur Teil-gegen-Rest ab ca. 1 m (Register BX)")
    json.dump(erg, open(os.path.join(a.objekt, "audit", "kanten_nulltest.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: erg[k] for k in ("je_foto", "gefunden_anteil", "rausch_max_px", "wiederholbar", "teilversatz_gefunden", "bestanden")}, ensure_ascii=False, indent=1))
    sys.exit(0 if erg["bestanden"] else 1)

if __name__ == "__main__":
    main()

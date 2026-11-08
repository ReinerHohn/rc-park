#!/usr/bin/env python3
"""Tabelle aus kennzahlen.json (wolke_kennzahlen.py): je Variante gewichteter Mittelwert ueber die Referenzebenen (Gewicht = Wandpunkte) + Einzelebenen. Aufruf: tabelle.py kennzahlen.json"""
import sys, json, numpy as np
d = json.load(open(sys.argv[1])); E = d["ebenen"]; print("Ebenen:", [(round(e["n_inlier"] / 1000), "k Inl.", round(e["flaeche_belegt_m2"]), "m2") for e in E])
cols = [("n_punkte", None), ("rausch_p50_cm", "p50"), ("rausch_p90_cm", "p90"), ("rauheit_p50_cm", "rau50"), ("schale_10_90_cm", "schale"), ("kante_oben_cm", "kOben"), ("abdeckung", "abd"), ("vor_fassade_prozent", "vor%"), ("vor_isoliert_prozent", "isoV%")]
print("%-9s %8s " % ("Variante", "Punkte") + " ".join("%7s" % c[1] for c in cols[1:]) + "  isoGes%")
for nm, v in d["varianten"].items():
    r = v["ebenen"]; w = np.array([x["n_wand"] for x in r], float); row = []
    for k, _ in cols[1:]:
        a = np.array([x[k] if x[k] is not None else np.nan for x in r], float); row.append(np.nansum(a * w) / w[~np.isnan(a)].sum() if k != "abdeckung" and k != "vor_fassade_prozent" and k != "vor_isoliert_prozent" else float(np.nanmean(a)))
    print("%-9s %8d " % (nm, v["punkte"]) + " ".join("%7.2f" % x for x in row) + "  %6.2f" % v.get("isoliert_gesamt_prozent", np.nan))
print("\nEinzelebenen (p50/p90/Rauheit50/Schale/kOben/abd/vor%/isoV%):")
for nm, v in d["varianten"].items():
    print(nm, [(x["rausch_p50_cm"], x["rausch_p90_cm"], x["rauheit_p50_cm"], x["schale_10_90_cm"], x["kante_oben_cm"], x["abdeckung"], x["vor_fassade_prozent"], x["vor_isoliert_prozent"]) for x in v["ebenen"]])

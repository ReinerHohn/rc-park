#!/usr/bin/env python3
"""llm_urteil_auswerten.py - sammelt Urteile unabhaengiger Beurteiler (<lauf>/urteile/<beurteiler>/<Pnn>.json {"urteil":"links|rechts|gleich","grund":..}), entschluesselt mit _schluessel/<lauf>.json (ausserhalb des Lauf-Ordners),
zaehlt je Netz/Variante Siege/Niederlagen, Mehrheit (>= --min-beurteiler), Konsistenz zwischen Beurteilern, Position-Bias und Vergleich mit dem Diff (kosten_lr, kleiner = besser).
Eichsatz-Treffer: erwartung A/B = Diff entscheidet; 'gleich' = Nullkontrolle. Entscheidungsregel (Nutzerauftrag): Einsatz nur wenn Treffer >= 80 % UND Nullkontrolle >= 80 % 'gleich'.
  llm_urteil_auswerten.py <lauf> [--min-beurteiler 3] [--eich]"""
import sys, os, json, glob, collections, argparse
ap = argparse.ArgumentParser(); ap.add_argument("lauf"); ap.add_argument("--min-beurteiler", type=int, default=3); ap.add_argument("--eich", action="store_true"); a = ap.parse_args()
d = os.path.join("/media/oem/scan/rc-park_null/llm_urteil", a.lauf) if not os.path.isdir(a.lauf) else a.lauf
key = json.load(open(os.path.join("/media/oem/scan/rc-park_null/llm_urteil/_schluessel", os.path.basename(d.rstrip("/")) + ".json"))); U = collections.defaultdict(dict)
for f in glob.glob(d + "/urteile/*/P*.json"):
    b, pid = f.split("/")[-2], os.path.basename(f)[:-5]
    try: u = json.load(open(f)).get("urteil", "").strip().lower()
    except Exception: continue
    if u in ("links", "rechts", "gleich") and pid in key: U[pid][b] = u
def sieger(pid, u):                                   # Urteil -> 'A' / 'B' / 'gleich'
    return "gleich" if u == "gleich" else (key[pid]["links"] if u == "links" else ("B" if key[pid]["links"] == "A" else "A"))
ent = {p: {b: sieger(p, u) for b, u in bs.items()} for p, bs in U.items()}
beurteiler = sorted({b for bs in ent.values() for b in bs}); out = {"beurteiler": beurteiler, "paare": len(key), "beurteilt": len(ent)}
def mehrheit(v):
    c = collections.Counter(v); (w, n), = c.most_common(1); return w if n > len(v) / 2 else "unklar"
# Konsistenz
agr = []
for p, bs in ent.items():
    v = list(bs.values())
    for i in range(len(v)):
        for j in range(i + 1, len(v)): agr.append(v[i] == v[j])
out["konsistenz_paarweise"] = round(sum(agr) / len(agr), 3) if agr else None
# Position-Bias (ueber alle Urteile ausser 'gleich')
lr = collections.Counter(u for bs in U.values() for u in bs.values()); out["urteile_links_rechts_gleich"] = dict(lr)
nl, nr_ = lr.get("links", 0), lr.get("rechts", 0); out["position_bias_links_anteil"] = round(nl / (nl + nr_), 3) if nl + nr_ else None
# Siege je Variante (Mehrheit je Paar)
sw = collections.defaultdict(lambda: [0, 0, 0]); zeilen = []
for p, bs in sorted(ent.items()):
    k = key[p]; m = mehrheit(list(bs.values())) if len(bs) >= a.min_beurteiler else "zu_wenig"
    diff = None
    if k.get("lr_a") is not None and k.get("lr_b") is not None: diff = "gleich" if abs(k["lr_a"] - k["lr_b"]) < 0.004 else ("A" if k["lr_a"] < k["lr_b"] else "B")
    if m in ("A", "B"):
        w, l = (k["a"], k["b"]) if m == "A" else (k["b"], k["a"]); sw[w][0] += 1; sw[l][1] += 1
    elif m == "gleich": sw[k["a"]][2] += 1; sw[k["b"]][2] += 1
    zeilen.append(dict(id=p, kat=k.get("kat"), nr=k.get("nr"), mehrheit=m, einzel=list(bs.values()), diff=diff, erwartung=k.get("erwartung"), stimmt_mit_diff=(m == diff) if m in ("A", "B", "gleich") else None))
out["siege_niederlagen_gleich_je_variante"] = dict(sw)
ok = [z for z in zeilen if z["stimmt_mit_diff"] is not None]; out["uebereinstimmung_mehrheit_mit_diff"] = f"{sum(z['stimmt_mit_diff'] for z in ok)}/{len(ok)}"
if a.eich:
    def rate(f, kr): 
        zs = [z for z in zeilen if f(z)]; return zs, kr
    # Treffer-Rate sowohl je Einzelurteil (Konfidenz des einzelnen Beurteilers) als auch Mehrheit
    for name, f in (("klar_netz_und_kamera", lambda z: z["erwartung"] in ("A", "B")), ("nullkontrolle_gesamt", lambda z: z["erwartung"] == "gleich"),
                    ("null_identisch", lambda z: z["kat"] == "null_identisch"), ("null_nahgleich", lambda z: z["kat"] == "null_nahgleich"), ("netz", lambda z: z["kat"] == "netz"),
                    ("kamera_1", lambda z: z["kat"] == "kamera_1"), ("kamera_0.5", lambda z: z["kat"] == "kamera_0.5")):
        zs = [z for z in zeilen if f(z)]; e = [(z["einzel"], z["erwartung"]) for z in zs]
        ein = [(x == ex) for es, ex in e for x in es]; out["eich_" + name] = dict(paare=len(zs), einzelurteil_treffer=f"{sum(ein)}/{len(ein)}", mehrheit_treffer=f"{sum(z['mehrheit'] == z['erwartung'] for z in zs)}/{len(zs)}",
                                                                                   einzel_rate=round(sum(ein) / len(ein), 3) if ein else None)
    k_, n_ = out.get("eich_klar_netz_und_kamera", {}), out.get("eich_nullkontrolle_gesamt", {})
    out["entscheidung"] = "EINSATZ als zweite Sicht" if (k_.get("einzel_rate") or 0) >= 0.8 and (n_.get("einzel_rate") or 0) >= 0.8 else "TAUGT NICHT (Regel: beide Raten >= 80 %)"
    out["entscheidung_mehrheit"] = "EINSATZ" if k_.get("paare") and n_.get("paare") and eval(k_["mehrheit_treffer"]) >= 0.8 and eval(n_["mehrheit_treffer"]) >= 0.8 else "TAUGT NICHT"
out["zeilen"] = zeilen; json.dump(out, open(d + "/auswertung.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in out.items() if k != "zeilen"}, indent=1, ensure_ascii=False))
for z in zeilen: print(z["id"], z["kat"], z["nr"], "mehrheit", z["mehrheit"], z["einzel"], "diff", z["diff"])

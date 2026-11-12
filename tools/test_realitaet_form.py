#!/usr/bin/env python3
"""test_realitaet_form.py - Beweis zu tools/realitaet_form.py (Spec modelle/SPEC_FORMNOTE.md).
  1. Fallen fallen alle durch (form < 0,5).   2. Bekannte Paare: besseres Teil hat hoehere Formnote (a125135, a095328, a091923 r2).
  3. --wiederholung: zwei Laeufe ohne Cache auf dem aktuellen Modell, Abweichung je Teil (darf bei hoechstens 10 % der Teile 0,5 betragen).
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_realitaet_form.py <objekt> --teile_dir D [--paare] [--wiederholung] [--cache_dir C]
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import realitaet_form as RF

KR = "/media/oem/scan/rc-park_kreis/kaufhaus_grob3"
PAARE = [  # (name, Teil, vorher-STL (schlechter), nachher-STL, erwartung)
    ("a125135", "staffelgiebel__west", f"{KR}/20261111_125136a125135/teile_r1_vorher_form", f"{KR}/20261111_125136a125135/teile_r1_nachher", "vorher<nachher", "Saegezahn -> Treppe"),
    ("a095328", "kreuzgewoelbe__laube", f"{KR}/20261111_095328a095328/teile_r1_vorher", f"{KR}/20261111_095328a095328/teile_r1_nachher", "vorher<nachher", "glattes Gewoelbe -> Rippen"),
    ("a091923", "freiform__tor_b2__ausschnitt", f"{KR}/20261111_091923a091923/teile_r2_vorher", f"{KR}/20261111_091923a091923/teile_r2_nachher", "vorher>nachher", "spitz -> rund (Rueckschritt)"),
]


def paare(a):
    extra = []
    for pid, tn, dv, dn, erw, was in PAARE:
        extra += [{"id": f"{pid}_v", "ersetzt": tn, "stl": os.path.join(dv, tn + ".stl"), "was": was + " vorher"},
                  {"id": f"{pid}_n", "ersetzt": tn, "stl": os.path.join(dn, tn + ".stl"), "was": was + " nachher"}]
    e = RF.lauf(a.objekt, a.teile_dir, None, os.path.join(a.cache_dir, "test_paare.json"), nur=["-"], cache_dir=a.cache_dir, kein_cache=True, extra=extra)
    ok = True; zeilen = []
    for f, x in sorted(e["teile"].items()):
        pass
    fallen = {k: v for k, v in e["teile"].items() if v["falle"]}
    for k, v in fallen.items():
        durch = v.get("status") == "ok" and v["form"] < 0.5; ok &= durch
        zeilen.append(f"Falle {k:3s} ({v['falle_was'][:60]}): form={v.get('form')} sicher={v.get('sicher')} -> {'DURCH (richtig)' if durch else 'NICHT DURCHGEFALLEN'}")
    for pid, tn, dv, dn, erw, was in PAARE:
        v, n = e["extras"].get(pid + "_v", {}), e["extras"].get(pid + "_n", {})
        if v.get("form") is None or n.get("form") is None: ok = False; zeilen.append(f"Paar {pid} ({was}): ungeprueft"); continue
        cmp_ = (lambda x, y: x < y) if erw == "vorher<nachher" else (lambda x, y: x > y)
        gut = cmp_(v["form"], n["form"]); fein = v.get("fein") is not None and n.get("fein") is not None and cmp_(v["fein"], n["fein"]); ok &= gut
        zeilen.append(f"Paar {pid} ({was}): vorher {v['form']} (fein {v.get('fein')}) nachher {n['form']} (fein {n.get('fein')}) (erwartet {erw}) -> "
                      + ("OK" if gut else ("FALSCH nach form (3 Stufen, Gleichstand), Feinnote richtig" if fein and v["form"] == n["form"] else "FALSCH")))
    print("\n".join(zeilen)); print("GESAMT paare/fallen:", "BESTANDEN" if ok else "NICHT BESTANDEN", "| Laufstatus:", e["status"], e["ungueltig_gruende"], "| Aufrufe", e["claude_aufrufe"], "Sek", e["sek_gesamt"])
    return ok


def wiederholung(a):
    r = []
    for i in (1, 2):
        r.append(RF.lauf(a.objekt, a.teile_dir, None, os.path.join(a.cache_dir, f"test_wiederholung_{i}.json"), cache_dir=a.cache_dir, kein_cache=True))
    t1, t2 = r[0]["teile"], r[1]["teile"]; d = {}; fein = {}
    for n in t1:
        if t1[n]["falle"] or t1[n]["extra"]: continue
        a1, a2 = t1[n].get("form"), t2[n].get("form")
        if a1 is None or a2 is None: continue
        d[n] = (a1, a2, abs(a1 - a2)); fe = (RF.feinnote(t1[n].get("merkmale")), RF.feinnote(t2[n].get("merkmale")))
        if None not in fe: fein[n] = abs(fe[0] - fe[1])
    import statistics as st
    if fein: print(f"Feinnote: mittlere Abweichung je Teil {st.mean(fein.values()):.3f}, max {max(fein.values()):.2f}, Teile mit Abw >= 0,25: {sum(1 for v in fein.values() if v >= 0.25)} von {len(fein)}")
    gross = [n for n, v in d.items() if v[2] >= 0.5]
    print("Teil | lauf1 | lauf2 | abw")
    for n, v in sorted(d.items()): print(f"{n} | {v[0]} | {v[1]} | {v[2]}{'  <-- 0,5' if v[2] >= 0.5 else ''}")
    print(f"Teile verglichen {len(d)}, Abweichung >= 0,5: {len(gross)} ({100 * len(gross) / max(1, len(d)):.0f} %) -> {'BESTANDEN' if len(gross) <= 0.1 * len(d) else 'NICHT BESTANDEN'}; form_prozent {r[0]['form_prozent']} / {r[1]['form_prozent']}; form_fein_prozent {r[0]['form_fein_prozent']} / {r[1]['form_fein_prozent']}; Status {r[0]['status']}/{r[1]['status']}; Sek {r[0]['sek_gesamt']}/{r[1]['sek_gesamt']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir", required=True); ap.add_argument("--cache_dir", default=RF.CACHE_STD)
    ap.add_argument("--paare", action="store_true"); ap.add_argument("--wiederholung", action="store_true"); a = ap.parse_args()
    if a.paare or not a.wiederholung: paare(a)
    if a.wiederholung: wiederholung(a)

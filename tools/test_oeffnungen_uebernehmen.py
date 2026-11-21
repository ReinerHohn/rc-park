#!/usr/bin/env python3
"""test_oeffnungen_uebernehmen.py - fester Test fuer oeffnungen_aus_kanten.uebernehmen (21.11.2026): nur GEBAUTE Oeffnungen bekommen Wandbild-Form/-Masse,
Beifang baut nichts, Wolken-Formen ueberschreiben nichts, Sohle bleibt, alte Werte stehen unter 'vor_wandbild'. < 1 s."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oeffnungen_aus_kanten as O

def oe(i, form, q, u, b, k, s): return dict(id=i, form=form, form_quelle=q, mitte_u=u, zone=[u - b / 2, u + b / 2, 0.0 if s < 10 else k - 1.5, s], breite=dict(wert=b, hinweis="lichte Weite"), kaempfer=dict(wert=k), scheitel=dict(wert=s))
# 21.11.2026 'f' = Fenster in 25 m Hoehe auf derselben Achse wie das Tor (Kettenlauf 1121o nahm es faelschlich als Tor) - darf NICHT uebernommen werden
with tempfile.TemporaryDirectory() as T:
    p = os.path.join(T, "oa.json")
    json.dump({"f00": {"oeffnungen": [dict(gebaut=True, form="rund", u=0.0, breite=4.9, kaempfer=3.2, scheitel=6.3, unten=-0.03),
                                       dict(gebaut=False, form="rund", u=3.0, breite=1.0, kaempfer=1, scheitel=2)]},
               "f01": {"oeffnungen": [dict(gebaut=True, form="rund", u=0.0, breite=2.0, kaempfer=2, scheitel=3)]}}, open(p, "w"))
    ber = {"ebenen": {"f00_wand": {"oeffnungen": [oe("a", "spitzbogen", "wandbild", 0.17, 4.5, 3.0, 6.22), oe("b", "sturz", "wandbild", 3.0, 0.8, 9.8, 9.8), oe("f", "rundbogen", "wandbild", 0.05, 1.8, 24.4, 25.3),
                                                    oe("c", "rundbogen", "wandbild", 6.0, 1.0, 1, 2)]},
                      "f01_wand": {"oeffnungen": [oe("d", "rundbogen", "wolkenrand", 0.0, 1.5, 2, 3)]}}}
    n = O.uebernehmen(ber, p, log=lambda *a: None); A = json.load(open(p)); x = A["f00"]["oeffnungen"][0]
    ok = (n == 1 and x["form"] == "spitz" and x["breite"] == 4.5 and x["u"] == 0.17 and x["unten"] == -0.03 and x["vor_wandbild"]["breite"] == 4.9
          and A["f00"]["oeffnungen"][1]["form"] == "rund" and A["f01"]["oeffnungen"][0]["breite"] == 2.0)
    print(("OK" if ok else "FEHLER") + f" oeffnungen uebernehmen: {n} uebernommen, Tor {x['form']} {x['breite']} (Soll spitz 4.5), Beifang/Wolkenform unveraendert")
    sys.exit(0 if ok else 1)

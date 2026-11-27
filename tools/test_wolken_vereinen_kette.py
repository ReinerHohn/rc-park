#!/usr/bin/env python3
"""test_wolken_vereinen_kette.py - Dummy-Test des Kettenschritts wolken_vereinen (tools/wolken_vereinen_kette.py, tools/gesamtkette.py) ohne Rechenjob (27.11.2026).
Prueft: Register der Quelle wird uebernommen ('kette' der Quelle heisst dann kette_<quelle>), die frische Kettenwolke steht VORNE als Bezug, ein zweiter Lauf
ersetzt sie (kein Doppeleintrag); ergebnis(): rc 0 + Bezug 'kette' -> neue Wolke; ROT oder fremder Bezug -> alte Wolke bleibt, Grund (NICHT VEREINT ...) im Text.
Dazu ein Mini-Lauf des echten Werkzeugs auf zwei kleinen Wolken (Sekunden) - derselbe Befehl, den die Kette absetzt.
Aufruf: tools/py tools/test_wolken_vereinen_kette.py"""
import os, sys, json, tempfile, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolken_vereinen_kette as K, wolke_vereinigen as WV  # noqa: E402

F = []


def pruef(ok, t):
    print(("OK    " if ok else "FEHLER") + " " + t, flush=True)
    if not ok: F.append(t)


def main():
    tmp = tempfile.mkdtemp(prefix="test_wvk_", dir="/media/oem/scan/tmp" if os.path.isdir("/media/oem/scan/tmp") else None); qo = os.path.join(tmp, "modelle", "turm", "objekt.json"); zo = os.path.join(tmp, "modelle", "turm-neu", "objekt.json")
    for p in (qo, zo): os.makedirs(os.path.dirname(p)); json.dump(dict(name="turm"), open(p, "w"))
    WV.anmelden(qo, dict(name="alt", pfad="/x/alt.ply", rahmen="sfm:/x/AU.json", lagetor="")); WV.anmelden(qo, dict(name="kette", pfad="modelle/turm/sfm/w.npy", rahmen="modell", lagetor=""))
    W = os.path.join(tmp, "modelle", "turm-neu", "sfm", "punkte_modell_turm-neu.npy")
    n, t = K.vorbereiten(zo, qo, W, root=tmp); R = WV.register_lesen(zo)
    pruef(n == 3 and [q["name"] for q in R["quellen"]] == ["kette", "alt", "kette_turm"], f"Register uebernommen, Kette vorne: {[q['name'] for q in R['quellen']]} ({t})")
    pruef(R["quellen"][0]["pfad"] == "modelle/turm-neu/sfm/punkte_modell_turm-neu.npy", f"Kettenwolke relativ zum Repo: {R['quellen'][0]['pfad']}")
    n2, _ = K.vorbereiten(zo, qo, W, root=tmp); pruef(n2 == 3, f"zweiter Lauf: kein Doppeleintrag ({n2})")
    n3, _ = K.vorbereiten(os.path.join(tmp, "modelle", "allein", "objekt.json") if os.makedirs(os.path.join(tmp, "modelle", "allein")) is None else "", None, W, root=tmp)
    pruef(n3 == 1, f"ohne Register der Quelle nur eine Wolke ({n3}) -> Kette vereint nicht")
    # ergebnis()
    aus = os.path.join(tmp, "aus"); os.makedirs(aus); np.save(os.path.join(aus, "punkte_modell.npy"), np.zeros((2, 3)))
    def vj(**k): json.dump(dict(dict(punkte=10, rot=[], quellen=[dict(name="kette", angenommen=True, rolle="Bezug"), dict(name="handy", angenommen=False, grund="Lagetor: UNSICHER: Rest 1,4 m")]), **k), open(os.path.join(aus, "vereint.json"), "w"))
    vj(); ok, txt, Wn = K.ergebnis(aus, 0); pruef(ok and Wn and "NICHT VEREINT: handy: Lagetor: UNSICHER" in txt, f"rc 0: neue Wolke, Grund der nicht vereinten Quelle im Text ({txt})")
    vj(rot=[dict(zone="Nord", vereint=1, beste=5)]); ok, txt, Wn = K.ergebnis(aus, 3); pruef(not ok and Wn is None and "ROT" in txt, f"rot: alte Wolke bleibt ({txt})")
    vj(quellen=[dict(name="alt", angenommen=True, rolle="Bezug")]); ok, txt, Wn = K.ergebnis(aus, 0); pruef(not ok and "nicht die Kettenwolke" in txt, "fremder Bezug: alte Wolke bleibt")
    # Mini-Lauf des echten Werkzeugs (Befehl wie in der Kette)
    rng = np.random.default_rng(0); A = np.c_[rng.uniform(0, 5, 20000), rng.uniform(0, 5, 20000), np.zeros(20000)]
    os.makedirs(os.path.dirname(W)); np.save(W, A); np.save(W.replace("punkte_modell", "punkte_farben"), np.full((len(A), 3), 7, np.uint8))
    B2 = np.c_[rng.uniform(3, 8, 20000), rng.uniform(0, 5, 20000), np.zeros(20000)]; bp = os.path.join(tmp, "b_punkte_modell.npy"); np.save(bp, B2)
    zo2 = os.path.join(tmp, "modelle", "mini", "objekt.json"); os.makedirs(os.path.dirname(zo2)); json.dump(dict(name="mini"), open(zo2, "w"))
    WV.anmelden(zo2, dict(name="b", pfad=bp, rahmen="modell", lagetor="")); K.vorbereiten(zo2, None, W, root=os.path.join(tmp, "anderes_repo"))   # absoluter Pfad
    a2 = os.path.join(tmp, "aus2"); cmd = K.befehl(sys.executable, zo2, a2); cmd[2] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wolke_vereinigen.py")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp); ok, txt, Wn = K.ergebnis(a2, r.returncode)
    n_v = len(np.load(Wn)) if Wn else 0
    pruef(r.returncode == 0 and ok and n_v > 30000, f"Mini-Lauf rc {r.returncode}: {txt} ({n_v} Punkte; {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]})")
    __import__("shutil").rmtree(tmp, ignore_errors=True)
    print("ERGEBNIS:", "ALLES GRUEN" if not F else f"{len(F)} FEHLER"); return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())

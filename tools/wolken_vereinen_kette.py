#!/usr/bin/env python3
"""wolken_vereinen_kette.py - Kettenschritt 'wolken_vereinen' fuer tools/gesamtkette.py (27.11.2026, Nutzer: "Ich dachte, das machst du automatisch. ... Immer vereinen.").

Nach JEDER neuen dichten Wolke (Stufe tore bestanden) wird sie mit ALLEN Wolken desselben Objekts vereint (tools/wolke_vereinigen.py, Register modelle/<obj>/wolken.json).
  vorbereiten(ziel_objekt, quelle_objekt, W): Register des Ziels anlegen (fehlt es, Eintraege der Quelle uebernehmen - gleicher Modellrahmen = objekt.json rahmen),
      die frische Kettenwolke W als 'kette' VORNE (Bezug, ihre Lage hat die Tore gerade bestanden) eintragen. Rueckgabe (anzahl_quellen, text).
  befehl(py, ziel_objekt, aus): Aufruf des Werkzeugs.  ergebnis(aus, rc): (ok, text, W_neu|None) - W_neu nur bei rc 0 und vereint.json mit 'kette' als Bezug.
Bei Lagetor UNSICHER / ABGELEHNT einer Quelle vereint das Werkzeug die anderen und nennt den Grund; ergebnis() gibt ihn woertlich weiter.
Abschalten: RCPARK_WOLKEN_VEREINEN=0. Test: tools/test_wolken_vereinen_kette.py (Dummy-Ordner, kein Rechenjob).
Verwandt: tools/wolke_vereinigen.py (Werkzeug), tools/wolken_vereinen_stufe.sh (dasselbe fuer die Nachtketten-Skripte).
Vorlaeufer: keiner - vor dem 27.11. vereinte keine Kette; Nachtketten rechneten nur auf der neuen Wolke (Schwabentor Handy: Nord 4x weniger Punkte als die alte Wolke, 0,89 gegen 3,53 Mio).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_vereinigen as WV  # noqa: E402


def vorbereiten(ziel_objekt, quelle_objekt, W, root=WV.ROOT):
    rz = WV.register_pfad(ziel_objekt); rq = WV.register_pfad(quelle_objekt) if quelle_objekt else None; text = []
    if not os.path.exists(rz) and rq and os.path.exists(rq) and os.path.abspath(rq) != os.path.abspath(rz):
        R = json.load(open(rq)); qn = os.path.basename(os.path.dirname(os.path.abspath(quelle_objekt)))
        for q in R.get("quellen", []):
            if q["name"] == "kette": q = dict(q, name=f"kette_{qn}")
            WV.anmelden(ziel_objekt, q)
        text.append(f"Register von {qn} uebernommen ({len(R.get('quellen', []))} Quellen)")
    Wr = os.path.relpath(W, root) if os.path.abspath(W).startswith(os.path.abspath(root) + os.sep) else os.path.abspath(W)
    R = WV.anmelden(ziel_objekt, dict(name="kette", pfad=Wr, rahmen="modell", lagetor=""), vorne=True)
    text.append("Quellen: " + ", ".join(q["name"] for q in R["quellen"])); return len(R["quellen"]), "; ".join(text)


def befehl(py, ziel_objekt, aus):
    return [py, "-I", "tools/wolke_vereinigen.py", "--objekt", ziel_objekt, "--aus", aus]


def ergebnis(aus, rc):
    vj = os.path.join(aus, "vereint.json"); W_neu = os.path.join(aus, "punkte_modell.npy")
    if not os.path.exists(vj): return False, f"kein {vj} (rc {rc})", None
    B = json.load(open(vj)); nicht = [f"{z['name']}: {z.get('grund')}" for z in B.get("quellen", []) if not z.get("angenommen")]
    zz = B.get("zonen_zahlen") or {}; v = zz.get("VEREINT", {})
    je = "; ".join(f"{zn} {v[zn]}" for zn in v)
    t = f"vereint {B.get('punkte')} Punkte" + (f" | Zonen: {je}" if je else "") + (f" | NICHT VEREINT: {' / '.join(nicht)}" if nicht else "")
    if B.get("rot"): t += f" | ROT {B['rot']}"
    bezug = next((z["name"] for z in B.get("quellen", []) if z.get("rolle") == "Bezug"), None)
    ok = rc == 0 and not B.get("rot") and bezug == "kette" and os.path.exists(W_neu)
    if rc == 0 and bezug != "kette": t += f" | Bezug ist {bezug}, nicht die Kettenwolke - W bleibt"
    return ok, t, (W_neu if ok else None)

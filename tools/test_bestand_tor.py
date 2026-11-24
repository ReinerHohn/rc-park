#!/usr/bin/env python3
"""Test BESTAND-TOR (24.11.2026, Rueckfall Galerie -> Treppenkloetze 1122z-zc; Verwandt: test_foto_tor_bezug.py, test_vorbau_keine_treppe.py; Vorlaeufer: keiner je Zone).
Ohne GPU: Messungen als teil_fotoform-Berichte aus Dateien (--messung).
  1. kein Bestand -> angelegt, rc 2 (kein Urteil).
  2. NULLKONTROLLE: derselbe Stand nochmal -> kein Rueckschritt, rc 0 (d = 0).
  3. ROTE PROBE: Zone vorbau_f00 deutlich schlechter (Treppenkloetze: F1 0,62 -> 0,38 je Foto, Rauschen ~0,03) -> rc 5, Zeile 'vorbau_f00 F1 ...'; Bestand NICHT fortgeschrieben.
  4. Rauschen statt fester Schwelle: kleine Streuung um 0 (eine Zone -0,01 bei sd 0,05) -> kein Rueckschritt.
  5. alle Zonen besser -> fortgeschrieben (Bestand = neuer Wert); eine Zone leicht schlechter (nicht signifikant) -> NICHT fortgeschrieben.
  6. gesamtkette.bestand_rueckschritt: Log-Zeile 'BESTAND RUECKSCHRITT: <zone> F1 alt->neu', rote Notiz, Liste fuer rc 6.
  7. merge_sperre.sh: Bericht mit Rueckschritt -> Exit 1 'MERGE GESPERRT'; ohne -> Exit 0. ketten_probelauf.sh (RCPARK_SPERRE_TEST=1) -> Exit 4 / 0."""
import os, sys, json, shutil, subprocess, io, contextlib, time
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); R0 = os.path.dirname(HIER); sys.path.insert(0, HIER)
import bestand_tor as BT
from pfade import temp_ordner

FEHLER = []
def pruef(ok, text):
    print(("    ok " if ok else "    FEHLER ") + text)
    if not ok: FEHLER.append(text)

rng = np.random.default_rng(3)
FOTOS = [f"foto{i}" for i in range(8)]
def bericht(werte):
    """{zone: (mittel, sd)} -> teil_fotoform-Bericht mit praez = recall = F1 je Foto."""
    t = {}
    for z, (m, s) in werte.items():
        v = np.clip(m + rng.normal(0, s, len(FOTOS)), 0.01, 0.99) if s else np.full(len(FOTOS), m)
        t[z] = {f: dict(praez=round(float(x), 4), recall=round(float(x), 4)) for f, x in zip(FOTOS, v)}
    return dict(teile=t)

td = temp_ordner("test_bestand_tor_")
alt_wurzel = os.environ.get("RCPARK_BESTAND_DATEN"); os.environ["RCPARK_BESTAND_DATEN"] = os.path.join(td, "daten")
BT.DATEN_WURZEL = os.environ["RCPARK_BESTAND_DATEN"]
try:
    od = os.path.join(td, "modelle", "obj_test"); os.makedirs(os.path.join(od, "audit"))
    stl = os.path.join(td, "m.stl"); open(stl, "wb").write(b"solid x\nendsolid x\n")
    json.dump(dict(generator="true", stl=stl), open(os.path.join(od, "objekt.json"), "w"))
    op = os.path.join(od, "objekt.json"); bp = os.path.join(od, "bestand", "bestand.json"); ap_ = os.path.join(od, "audit", "bestand_tor.json")
    def lauf(werte, name):
        mj = os.path.join(td, name + ".json"); json.dump(werte if "teile" in werte else bericht(werte), open(mj, "w"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out): rc = BT.main([op, "--stl", stl, "--messung", mj])
        return rc, out.getvalue()
    gut = bericht({"vorbau_f00": (0.62, 0.03), "uhr_f00": (0.55, 0.04), "fenster_f00_2": (0.48, 0.05)})
    rc, _ = lauf(gut, "gut"); pruef(rc == 2 and os.path.exists(bp), f"1. kein Bestand -> angelegt, rc {rc} (Soll 2)")
    rc, o = lauf(gut, "gut2"); pruef(rc == 0 and "RUECKSCHRITT" not in o, f"2. Nullkontrolle gleicher Stand: rc {rc} (Soll 0)")
    schlecht = json.loads(json.dumps(gut)); schlecht["teile"]["vorbau_f00"] = bericht({"vorbau_f00": (0.38, 0.03)})["teile"]["vorbau_f00"]
    b_vor = json.load(open(bp))
    rc, o = lauf(schlecht, "schlecht"); J = json.load(open(ap_))
    pruef(rc == BT.RC_RUECKSCHRITT and any(r.startswith("vorbau_f00 F1 0.6") for r in J["rueckschritt"]) and "BESTAND RUECKSCHRITT: vorbau_f00" in o,
          f"3. ROTE PROBE Treppenkloetze: rc {rc}, {J['rueckschritt']}")
    pruef(json.load(open(bp))["zonen"] == b_vor["zonen"], "3. Bestand bei Rueckschritt NICHT fortgeschrieben")
    pruef(not any(r.startswith("uhr_f00") or r.startswith("fenster") for r in J["rueckschritt"]), "3. unveraenderte Zonen nicht rot")
    # 4. reines Rauschen um 0 (Mittel -0,0225, sd 0,05) -> statistisch nicht schlechter
    U2 = BT.urteil(dict(zonen={"z": dict(f1={f: 0.5 for f in FOTOS})}), {"z": {f: 0.5 + d for f, d in zip(FOTOS, [-0.06, 0.05, -0.04, 0.03, 0.02, -0.05, 0.04, -0.07])}})
    pruef(not U2["rueckschritt"] and U2["zonen"]["z"]["urteil"] == "gleich", f"4. Rauschen (Mittel {U2['zonen']['z']['d']:+.3f}, Schwelle {U2['zonen']['z']['schwelle']:+.3f}) -> gleich")
    besser = bericht({"vorbau_f00": (0.70, 0.03), "uhr_f00": (0.60, 0.04), "fenster_f00_2": (0.55, 0.05)})
    rc, o = lauf(besser, "besser"); pruef(rc == 0 and "fortgeschrieben" in o and json.load(open(bp))["zonen"]["vorbau_f00"]["f1"]["foto0"] > 0.6, f"5. alle besser -> fortgeschrieben (rc {rc})")
    b_vor = json.load(open(bp)); knapp = json.loads(json.dumps(besser))
    for f in FOTOS: knapp["teile"]["uhr_f00"][f]["praez"] = knapp["teile"]["uhr_f00"][f]["recall"] = round(b_vor["zonen"]["uhr_f00"]["f1"][f] - 0.004 + (0.01 if f == "foto0" else 0), 4)
    for z in ("vorbau_f00", "fenster_f00_2"):
        for f in FOTOS: knapp["teile"][z][f]["praez"] = knapp["teile"][z][f]["recall"] = b_vor["zonen"][z]["f1"][f]
    rc, o = lauf(knapp, "knapp"); pruef(rc == 0 and "fortgeschrieben" not in o and json.load(open(bp))["zonen"] == b_vor["zonen"], f"5. eine Zone leicht schlechter -> kein Rueckschritt, aber NICHT fortgeschrieben (rc {rc})")
    # 6. gesamtkette-Auswertung
    import gesamtkette as GK
    lauf(schlecht, "schlecht2"); Bk = dict(schritte=[]); L = []; out = io.StringIO()
    GK.notiz = lambda B_, name, ok, **k: B_["schritte"].append(dict(stufe=name, ok=ok, **k))
    with contextlib.redirect_stdout(out): rs = GK.bestand_rueckschritt(Bk, 5, ap_, time.time() - 5, L)
    pruef(L and "BESTAND RUECKSCHRITT: vorbau_f00 F1" in out.getvalue() and Bk["schritte"][-1]["ok"] is False and GK.RC_BESTAND_RUECKSCHRITT == 6, f"6. gesamtkette: Log-Zeile + rote Notiz + Liste {L}")
    # 7. Merge-Sperre
    env = dict(os.environ, RCPARK_MERGE_SPERRE_WURZEL=os.path.join(td, "modelle"))
    r = subprocess.run(["bash", os.path.join(HIER, "merge_sperre.sh"), "obj_test"], capture_output=True, text=True, env=env)
    pruef(r.returncode == 1 and "MERGE GESPERRT" in r.stdout and "vorbau_f00" in r.stdout, f"7. merge_sperre mit Rueckschritt: Exit {r.returncode}")
    r2 = subprocess.run(["bash", os.path.join(HIER, "ketten_probelauf.sh")], capture_output=True, text=True, env=dict(env, RCPARK_SPERRE_TEST="1"))
    pruef(r2.returncode == 4, f"7. ketten_probelauf verweigert (Exit {r2.returncode}, Soll 4)")
    lauf(besser, "besser2")
    r = subprocess.run(["bash", os.path.join(HIER, "merge_sperre.sh"), "obj_test"], capture_output=True, text=True, env=env)
    r2 = subprocess.run(["bash", os.path.join(HIER, "ketten_probelauf.sh")], capture_output=True, text=True, env=dict(env, RCPARK_SPERRE_TEST="1"))
    pruef(r.returncode == 0 and r2.returncode == 0, f"7. ohne Rueckschritt frei: merge_sperre {r.returncode}, probelauf {r2.returncode}")
    # 8. EINGANGS-TOR: Frontpunkte f00_vb0 11573 -> 2430 (Abfall > Haelfte) = Rueckschritt mit Zonenname; 11573 -> 9000 nicht
    ej = os.path.join(td, "ebenen.json"); json.dump(dict(ebenen=[dict(id="f00_vb0", punkte=13116)]), open(ej, "w"))
    json.dump({"f00_vb0": dict(punkte_front=11573)}, open(os.path.join(od, "audit", "ebenen_masse.json"), "w"))
    mj = os.path.join(td, "besser3.json"); json.dump(besser, open(mj, "w"))
    with contextlib.redirect_stdout(io.StringIO()): BT.main([op, "--stl", stl, "--messung", mj, "--ebenen", ej])
    pruef(json.load(open(bp))["eingang"].get("f00_vb0:punkte_front") == 11573, "8. Eingangs-Bestwert gespeichert")
    json.dump(dict(ebenen=[dict(id="f00_vb0", punkte=3354)]), open(ej, "w")); json.dump({"f00_vb0": dict(punkte_front=2430)}, open(os.path.join(od, "audit", "ebenen_masse.json"), "w"))
    out = io.StringIO()
    with contextlib.redirect_stdout(out): rc = BT.main([op, "--stl", stl, "--messung", mj, "--ebenen", ej])
    J = json.load(open(ap_))
    pruef(rc == BT.RC_RUECKSCHRITT and "EINGANG f00_vb0:punkte_front 11573->2430" in J["rueckschritt"] and "EINGANG f00_vb0:kantenpunkte 13116->3354" in J["rueckschritt"],
          f"8. ROTE PROBE Eingang (Zone F1 gleich, Belegdichte eingebrochen): rc {rc}, {J['rueckschritt']}")
    pruef(json.load(open(bp))["eingang"]["f00_vb0:punkte_front"] == 11573, "8. Bestwert bleibt das Maximum (Rueckfall verdeckt ihn nicht)")
    json.dump({"f00_vb0": dict(punkte_front=9000)}, open(os.path.join(od, "audit", "ebenen_masse.json"), "w")); json.dump(dict(ebenen=[dict(id="f00_vb0", punkte=12000)]), open(ej, "w"))
    with contextlib.redirect_stdout(io.StringIO()): rc = BT.main([op, "--stl", stl, "--messung", mj, "--ebenen", ej])
    pruef(rc == 0, f"8. Abfall < Haelfte ist kein Eingangs-Rueckschritt (rc {rc})")
    # 9. Handstand nie still: Geschwister hat referenz_hand.json -> Grund; ERGEBNIS-Zusatz und Verlaufszeile
    wz = os.path.join(td, "w"); os.makedirs(os.path.join(wz, "modelle", "turm-1120")); os.makedirs(os.path.join(wz, "modelle", "turm-1122"))
    open(os.path.join(wz, "modelle", "turm-1120", "referenz_hand.json"), "w").write("{}")
    p_, g_ = GK.handstand_referenz(wz, "turm-1122", os.path.join(wz, "modelle", "turm-1122", "objekt.json"))
    pruef(p_ is None and g_ and "Geschwister" in g_, f"9. fehlende Handreferenz bei Geschwister mit Referenz -> Fehlergrund ({g_})")
    p_, g_ = GK.handstand_referenz(wz, "turm-1120", "")
    pruef(p_ and g_ is None, "9. eigene Referenz gefunden")
    Bz = dict(schritte=[dict(stufe="bestand_tor_urteil", ok=True, urteil="gleich")])
    zl = GK.bauteile_zeile([dict(passt=5, gesamt=11, bauteile={"vorbau_f00": "FALSCH"})], [], Bz, 0)
    pruef("BAUTEILE 5 von 11 PASST" in zl and "BESTAND: gleich" in zl, f"9. Ergebniszeile: '{zl}'")
    pruef("HANDSTAND NICHT GEMESSEN" in GK.bauteile_zeile([], ["x"], dict(schritte=[dict(stufe="handstand", ok=False)]), 0), "9. Ergebniszeile ohne Handstand nennt es")
    GK.verlauf_bauteile(od, [dict(passt=5, gesamt=11, bauteile={"vorbau_f00": "FALSCH"})], ["vorbau_f00 F1 0.6->0.4"], Bz, 0, 6)
    vz = json.loads(open(os.path.join(od, "audit", "verlauf_bauteile.jsonl")).read().splitlines()[-1])
    pruef(vz["x"] == 5 and vz["N"] == 11 and vz["bestand"] == "RUECKSCHRITT" and vz["bauteile"]["vorbau_f00"] == "FALSCH", "9. audit/verlauf_bauteile.jsonl Zeile je Lauf")
finally:
    if alt_wurzel is None: os.environ.pop("RCPARK_BESTAND_DATEN", None)
    else: os.environ["RCPARK_BESTAND_DATEN"] = alt_wurzel
    shutil.rmtree(td, ignore_errors=True)
if FEHLER: print("FEHLER test_bestand_tor:", len(FEHLER)); sys.exit(1)
print("    ok test_bestand_tor")

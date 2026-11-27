#!/usr/bin/env python3
"""test_ebenen_stapel_schleife.py - fester synthetischer Test (27.11.2026, K7: Schichtstapel + Abweichungsschleife in der Kette hinter RCPARK_EBENEN_SCHLEIFE=1).
Rot ohne die K7-Aenderung (tools/ebenen_stapel.py fehlt, ebenen_schleife ohne --neu_eigene/--ohne_wandversatz/Schichten, gesamtkette ohne ebenen_schleife_stufe).
Werte sind Testgeometrie, kein Objektmass. Keine GPU, kein Kettenlauf, < 1 min.
  A ebenen_stapel.spitzen: oertliche Maxima >= 2 % der staerksten; urteil: >= 80 % Ebene, 40-80 pruefen, sonst Schein.
  B ebenen_stapel (--schichten): Wand f00 w 0, Schichten -0,3..+2,4; Spitzen bei 0 (Wand), +1,2 (Wolke bestaetigt) und +2,1 (Wolke fehlt = Scheintreffer)
    -> ebenen.json = Kettenebenen + NUR f00_s05 (w +1,2); ohne Wolke rc 3 und keine ebenen.json; Altstand ebenen.json wird entfernt.
  C ebenen_schleife: Wandscheibe y -0,5..0, Schicht w +1,2 mit Kantenfeld x 3..5, z 3..5 ohne Modellflaeche (Form fehlt) -> Runde 1 Kasten auf +1,2, angenommen,
    rc 0; fremde Korrektur (wandlage, quelle) bleibt, eigene Altkorrektur ohne quelle faellt (--neu_eigene), kein Wandversatz-Kandidat (--ohne_wandversatz, Wand w +0,2).
  D gesamtkette.ebenen_schleife_stufe: Schalter aus -> nichts; an -> Stapel, Schleife auf dem Stapel-Ordner mit beiden Schaltern, Neubau; Stapel rc 3 -> Kettenebenen;
    Schleife rc 2 -> Korrekturen zurueck auf den Stand vorher + Neubau + rote Notiz."""
import os, sys, json, subprocess, tempfile, shutil
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
fehler = []
def pruef(b, t):
    print(("ok    " if b else "FEHLER ") + t, flush=True)
    if not b: fehler.append(t)


import ebenen_stapel as ES
pruef(ES.spitzen([0, 5, 100, 40, 3, 1, 50, 2]) == [2, 6], "A spitzen [0,5,100,40,3,1,50,2] -> [2, 6]")
pruef(ES.spitzen([100, 1, 1.5, 0]) == [0], "A Spitze unter 2 % der staerksten zaehlt nicht")
pruef(ES.urteil(0.85) == "ebene" and ES.urteil(0.5) == "pruefen" and ES.urteil(0.1) == "schein" and ES.urteil(None) == "unbestaetigt", "A urteil-Schwellen 80/40")

from pfade import temp_ordner
T = temp_ordner("test_k7_"); rg = np.random.default_rng(1)
try:
    # ---------- B Stapel-Auswertung ----------
    o, d, n = [0.0, 0.0], [1.0, 0.0], [0.0, 1.0]; zone = [0.0, 10.0, 0.0, 8.0]
    eb = os.path.join(T, "ebenen"); os.makedirs(eb); st = os.path.join(T, "stapel"); os.makedirs(os.path.join(st, "schichten"))
    E = [dict(id="f00_wand", art="wand", fassade="f00", o=o, d=d, n=n, w=0.0, zone=zone, band=0.5)]
    json.dump(dict(ebenen=E), open(os.path.join(eb, "ebenen.json"), "w"))
    def feld(w, k, x=(1, 9), z=(1, 7)): return np.c_[rg.uniform(*x, k), np.full(k, w) + rg.normal(0, 0.02, k), rg.uniform(*z, k)]
    ws = np.round(np.arange(-0.3, 2.4 + 1e-6, 0.3), 3); zahl = {0.0: 4000, 1.2: 1500, 2.1: 600}; S = []; WO = []
    for j, w in enumerate(ws):
        k = zahl.get(float(w), 30); P = feld(float(w), k, *(((3, 5), (3, 5)) if float(w) == 1.2 else ((1, 9), (1, 7))))
        sw = os.path.join(st, "schichten", f"s{j:02d}.npz"); np.savez(sw, P=P.astype(np.float32))
        S.append(dict(id=f"f00_s{j:02d}", art="schicht", fassade="f00", o=o, d=d, n=n, w=float(w), w_wand=0.0, zone=zone, band=0.15, punkte=k, sweep=sw))
        if float(w) in (0.0, 1.2): WO.append(P + rg.normal(0, 0.02, P.shape))                 # Wolke bestaetigt Wand und Erkerfront, NICHT die Schicht +2,1 (Draht)
    WO.append(feld(2.45, 500))                                                                # duenne Wolke 0,35 m HINTER der Drahtschicht: Umfeld belegt, Kanten nicht bestaetigt
    sj = os.path.join(st, "schichten", "ebenen.json"); json.dump(dict(ebenen=S), open(sj, "w")); wo = os.path.join(T, "wolke.npy"); np.save(wo, np.vstack(WO).astype(np.float32))
    open(os.path.join(st, "ebenen.json"), "w").write("{}")                                   # Altstand
    PY = sys.executable; ST = os.path.join(H, "ebenen_stapel.py")
    r = subprocess.run([PY, "-I", ST, "x.json", T, T, eb, st, "--schichten", sj], capture_output=True, text=True)
    pruef(r.returncode == 3 and not os.path.exists(os.path.join(st, "ebenen.json")), f"B ohne Wolke rc 3 und keine ebenen.json (Altstand entfernt) (rc {r.returncode})")
    r = subprocess.run([PY, "-I", ST, "x.json", T, T, eb, st, "--schichten", sj, "--wolke", wo], capture_output=True, text=True)
    ej = os.path.join(st, "ebenen.json"); M = json.load(open(ej))["ebenen"] if os.path.exists(ej) else []
    pruef(r.returncode == 0, f"B mit Wolke rc 0 (rc {r.returncode}) {r.stderr.strip()[-200:]}")
    pruef([e["id"] for e in M] == ["f00_wand", "f00_s05"], f"B ebenen.json = Wand + nur Erkerfront-Schicht (ist {[e['id'] for e in M]})")
    rb = json.load(open(os.path.join(st, "stapel_ebenen.json"))) if os.path.exists(os.path.join(st, "stapel_ebenen.json")) else {}
    zz = {z["id"]: z for b in rb.get("waende", []) for z in b["schichten"]}
    pruef(zz.get("f00_s08", {}).get("urteil") == "schein" and zz.get("f00_s01", {}).get("rolle") == "wand", "B Bericht: +2,1 Scheintreffer, Schicht 0 = Wand")

    # ---------- C Schleife mit Dummy-Generator ----------
    od = os.path.join(T, "obj"); os.makedirs(os.path.join(od, "audit")); stl = os.path.join(T, "modell.stl"); gen = os.path.join(T, "gen.py")
    open(gen, "w").write('''import json, os, sys, trimesh, numpy as np
kp, stl = sys.argv[1], sys.argv[2]
def kasten(x0, x1, y0, y1, z0, z1):
    b = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0]); b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    for _ in range(4): b = b.subdivide()
    return b
T = [kasten(0, 10, -0.5, 0, 0, 8)]
for K in (json.load(open(kp)).get("korrekturen", []) if os.path.exists(kp) else []):
    if K.get("angenommen") is False or K.get("art") != "fleck": continue
    T.append(kasten(K["u0"], K["u1"], min(K["w_ist"], K["w_soll"]) - 0.05, max(K["w_ist"], K["w_soll"]), K["z0"], K["z1"]))
trimesh.util.concatenate(T).export(stl)
''')
    kp = os.path.join(od, "audit", "schleife_korrekturen.json")
    json.dump(dict(generator=f"{PY} -I {gen} {kp} {stl}", stl=stl, stl_massstab=1000), open(os.path.join(od, "objekt.json"), "w"))
    json.dump(dict(korrekturen=[dict(id="wl_f01", ebene="f01_wand", art="wandversatz", schluessel=None, fassade="f01", o=o, d=d, n=n, u0=0, u1=1, z0=0, z1=1, w_ist=0, w_soll=-0.1, angenommen=True, quelle="tools/wandlage_fotokanten.py"),
                                dict(id="k00", ebene="f00_wand", art="fleck", schluessel="8,6,9,7", fassade="f00", o=o, d=d, n=n, u0=8, u1=9, z0=6, z1=7, w_ist=0, w_soll=0.5, angenommen=True)]), open(kp, "w"))
    ec = os.path.join(T, "ebenen_c"); os.makedirs(ec); Pw = feld(0.0, 3000, (0.5, 9.5), (0.5, 7.5)); Ps = feld(1.2, 2500, (3, 5), (3, 5))
    np.savez(os.path.join(ec, "w.npz"), P=Pw.astype(np.float32)); np.savez(os.path.join(ec, "s.npz"), P=Ps.astype(np.float32))
    json.dump(dict(ebenen=[dict(id="f00_wand", art="wand", fassade="f00", o=o, d=d, n=n, w=0.2, zone=zone, band=0.5, sweep=os.path.join(ec, "w.npz")),     # w +0,2: haette ohne Schalter einen Wandversatz-Kandidaten
                           dict(id="f00_s05", art="schicht", fassade="f00", o=o, d=d, n=n, w=1.2, zone=zone, band=0.15, sweep=os.path.join(ec, "s.npz"))]), open(os.path.join(ec, "ebenen.json"), "w"))
    # Wand-Kantenpunkte liegen bei y 0 = w -0,2 gegen die Ebene: fuer die Abweichung egal (misst gegen das Modell), Kandidat (a) prueft nur e['w']
    r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(H, "ebenen_schleife.py"), os.path.join(od, "objekt.json"), ec, "--neu_eigene", "--ohne_wandversatz", "--runden", "3"], capture_output=True, text=True)
    KO = json.load(open(kp))["korrekturen"]; ids = {k["id"]: k for k in KO}
    pruef(r.returncode == 0, f"C Schleife rc 0 (rc {r.returncode}) {(r.stderr.strip() or r.stdout.strip())[-300:]}")
    pruef("wl_f01" in ids and "k00" not in ids, f"C fremde Korrektur bleibt, eigene Altkorrektur faellt (ist {sorted(ids)})")
    neu = [k for k in KO if k.get("quelle") == "tools/ebenen_schleife.py"]
    pruef(any(k["art"] == "fleck" and k["ebene"] == "f00_s05" and k.get("angenommen") and abs(k["w_soll"] - 1.2) < 0.05 for k in neu), f"C Fleck auf der Schicht +1,2 angenommen ({[(k['ebene'], k['art'], k.get('urteil')) for k in neu]})")
    pruef(not any(k["art"] == "wandversatz" for k in neu), "C kein Wandversatz-Kandidat der Schleife (--ohne_wandversatz)")
    pruef(any("vorher" in k for k in neu) and all("erfunden" in k["vorher"] for k in neu if "vorher" in k), "C Kennzahl 'erfunden' im Protokoll (Guard)")

    # ---------- D Verdrahtung in gesamtkette ----------
    import gesamtkette as GK
    Z = os.path.join(T, "Z"); D = os.path.join(T, "D"); os.makedirs(os.path.join(Z, "audit")); os.makedirs(os.path.join(D, "ebenen")); os.makedirs(os.path.join(D, "ebenen_stapel"))
    open(os.path.join(D, "ebenen", "ebenen.json"), "w").write("{}"); gp = os.path.join(T, "g_gen.py"); open(gp, "w").write("#"); kpz = os.path.join(Z, "audit", "schleife_korrekturen.json"); open(kpz, "w").write('{"korrekturen": []}')
    rufe, gebaut, notizen = [], [], []; rc_von = {}
    def f_lauf(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
        rufe.append((name, cmd)); rc = rc_von.get(name, 0)
        if name == "bauplan_ebenen_stapel" and rc == 0: open(os.path.join(D, "ebenen_stapel", "ebenen.json"), "w").write("{}")
        if name == "bauplan_ebenen_schleife": open(kpz, "w").write('{"korrekturen": [{"id": "halb", "angenommen": null}]}')
        return rc, ""
    GK.lauf = f_lauf; GK.bauen = lambda B, name, ziel, log, zwischen=True: gebaut.append(name); GK.notiz = lambda B, name, ok, **k: notizen.append((name, ok))
    arg = lambda: ({}, "x.json", Z, D, os.path.join(D, "fassade"), os.path.join(D, "kanten"), os.path.join(D, "ebenen"), os.path.join(T, "fehlt.npy"), "x", None, gp)
    os.environ.pop("RCPARK_EBENEN_SCHLEIFE", None)
    pruef(GK.ebenen_schleife_stufe(*arg()) is None and not rufe and not gebaut, "D Schalter aus: nichts gerechnet, nichts gebaut")
    os.environ["RCPARK_EBENEN_SCHLEIFE"] = "1"; e1 = GK.ebenen_schleife_stufe(*arg())
    sl = [c for nm, c in rufe if nm == "bauplan_ebenen_schleife"]
    pruef([nm for nm, _ in rufe] == ["bauplan_ebenen_stapel", "bauplan_ebenen_schleife"] and sl and sl[0][6] == os.path.join(D, "ebenen_stapel") and "--neu_eigene" in sl[0] and "--ohne_wandversatz" in sl[0],
          f"D an: Stapel, dann Schleife auf dem Stapel-Ordner mit --neu_eigene --ohne_wandversatz ({[nm for nm, _ in rufe]})")
    pruef(gebaut == ["bauen_mit_ebenen_schleife"] and e1.get("ebenen_schleife_rc") == 0, f"D Neubau nach geaenderten Korrekturen ({gebaut})")
    rufe.clear(); gebaut.clear(); open(kpz, "w").write('{"korrekturen": []}'); rc_von.update(bauplan_ebenen_stapel=3, bauplan_ebenen_schleife=2); os.remove(os.path.join(D, "ebenen_stapel", "ebenen.json"))
    e2 = GK.ebenen_schleife_stufe(*arg()); sl = [c for nm, c in rufe if nm == "bauplan_ebenen_schleife"]
    pruef(sl and sl[0][6] == os.path.join(D, "ebenen"), "D Stapel rc 3: Schleife auf den Ebenen der Kette")
    pruef(open(kpz).read() == '{"korrekturen": []}' and gebaut == ["bauen_nach_ebenen_schleife_abbruch"] and ("bauplan_ebenen_schleife_fallback", False) in notizen and e2.get("ebenen_schleife_fallback"),
          "D Schleife rc 2: Korrekturen zurueck, Neubau, rote Notiz (Fallback alter Weg)")
finally:
    os.environ.pop("RCPARK_EBENEN_SCHLEIFE", None); shutil.rmtree(T, ignore_errors=True)
print("ERGEBNIS:", "alle ok" if not fehler else f"{len(fehler)} FEHLER"); sys.exit(1 if fehler else 0)

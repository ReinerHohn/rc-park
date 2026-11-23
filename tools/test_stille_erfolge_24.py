#!/usr/bin/env python3
"""test_stille_erfolge_24.py - offene Befunde des Audits 'stille Erfolge' (modelle/AUDIT_STILLE_ERFOLGE_2026-11-23.md, Nachtrag 24.11.2026). Attrappen, Sekunden.
Jeder Fall waere am alten Stand ROT:
(a) Stufe mono: 0 bearbeitete Waende -> NICHT in Ordnung (kette_beleg.bearbeitet_urteil; vorher notiz(B, "mono", True, ...)).
(b) oeffnungen_wandbild: Bogen ohne Tiefenkarte -> 'unentschieden', flach None, rc 3 (vorher 'nicht offen (keine Tiefenkarte)', flach True, rc 0 = still geschlossen).
(c) bauen_abnehmen.sh RCPARK_NUR_BAUEN=1: leeres STL (84 Byte, Lauf 1122u) bzw. nicht neu geschriebenes STL -> rc 4 ohne ERGEBNIS-Zeile (vorher rc 0 + ERGEBNIS);
    gueltiges STL -> rc 0 + ERGEBNIS. Dazu kette_beleg.stl_dreiecke (binaer/ASCII/kaputt).
(d) gesamtkette: Beleg fuer vorbauten_auto.json (Absturz von vorbauten_bauplan -> Generator baute Vorbauten des Vorlaufs) und hand_vergleich.json (befundliste las
    den Vergleich eines frueheren Laufs); bauplan_innen_oeffnungen nimmt rc 3 (unentschiedene Boegen) weiter an."""
import os, sys, json, time, struct, shutil, tempfile, subprocess
HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER); sys.path.insert(0, HIER)
import kette_beleg as KB

PYS = "/media/oem/scan/venv-seg/bin/python"
F = 0
def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text); F += 0 if ok else 1


def stl_bin(p, n):
    with open(p, "wb") as f:
        f.write(b"attrappe".ljust(80, b" ") + struct.pack("<I", n))
        for k in range(n): f.write(struct.pack("<12fH", 0, 0, 1, 0, 0, k, 1, 0, k, 0, 1, k, 0))


with tempfile.TemporaryDirectory(prefix="test_stille_erfolge_24_") as T:
    # (a)
    ok_, f_ = KB.bearbeitet_urteil([], {"w_nord": 4, "w_ost": 4}, ["w_sued"])
    pruef(not ok_ and "0 Waende" in f_ and "w_nord rc 4" in f_ and "w_sued" in f_, f"(a) mono mit 0 Waenden = NICHT in Ordnung: {f_}")
    pruef(KB.bearbeitet_urteil(["w_nord"], {"w_nord": 0})[0], "(a) mono mit 1 Wand = in Ordnung")
    src = open(os.path.join(HIER, "gesamtkette.py")).read()
    pruef('notiz(B, "mono", True' not in src and 'notiz(B, "mono", ok_m' in src, "(a) gesamtkette: Zeile mono nutzt das Urteil statt fest True")
    # (c) STL-Zaehlung
    for n in (0, 3): stl_bin(os.path.join(T, f"b{n}.stl"), n)
    open(os.path.join(T, "a.stl"), "w").write("solid x\n facet normal 0 0 1\n outer loop\n endloop\n endfacet\n facet normal 0 0 1\n endfacet\nendsolid x\n")
    open(os.path.join(T, "k.stl"), "wb").write(b"\0" * 80 + struct.pack("<I", 5) + b"\0" * 20)
    pruef([KB.stl_dreiecke(os.path.join(T, n)) for n in ("b0.stl", "b3.stl", "a.stl", "k.stl")] == [0, 3, 2, -1], "(c) stl_dreiecke: 84-Byte-STL 0, binaer 3, ASCII 2, abgeschnitten -1")
    pruef(KB.stl_pruefen(os.path.join(T, "b0.stl"), time.time() - 5) != [] and KB.stl_pruefen(os.path.join(T, "b3.stl"), time.time() - 5) == [], "(c) stl_pruefen: leer = Verstoss, 3 Dreiecke frisch = belegt")
    # (c) bauen_abnehmen.sh als Attrappe in einem Schein-Repo (Kopie des Skripts + kette_beleg.py, Platztor-Attrappe rc 0 - das echte Platztor wuerde bei knapper
    #     Systemplatte mit rc 3 abbrechen und den Fall falsch gruen machen); Generator schreibt nur ein STL, sonst wird nichts gerechnet
    R_ = os.path.join(T, "repo"); os.makedirs(os.path.join(R_, "tools"))
    for n_ in ("bauen_abnehmen.sh", "kette_beleg.py"): shutil.copy(os.path.join(HIER, n_), os.path.join(R_, "tools", n_))
    open(os.path.join(R_, "tools", "platz_pruefen.py"), "w").write("import sys; sys.exit(0)\n")
    obj = "attrappe_stl"; od = os.path.join(R_, "modelle", obj); stl = os.path.join(T, "attrappe.stl")
    gen = {"leer": f"python3 -c \"import struct;open('{stl}','wb').write(b' '*80+struct.pack('<I',0))\"",
           "alt": "true",
           "gut": f"python3 -c \"import struct;open('{stl}','wb').write(b' '*80+struct.pack('<I',1)+struct.pack('<12fH',0,0,1,0,0,0,1,0,0,0,1,0,0))\""}
    try:
        os.makedirs(od)
        for fall, cmd in gen.items():
            json.dump(dict(generator=cmd, stl=stl), open(os.path.join(od, "objekt.json"), "w"))
            if fall == "alt": stl_bin(stl, 4); t_ = time.time() - 3600; os.utime(stl, (t_, t_))
            r = subprocess.run(["bash", os.path.join(R_, "tools", "bauen_abnehmen.sh"), obj], cwd=R_, capture_output=True, text=True, timeout=120,
                               env=dict(os.environ, RCPARK_NUR_BAUEN="1", RCPARK_KURZ="0"))
            erg = "ERGEBNIS:" in r.stdout
            if fall == "gut": pruef(r.returncode == 0 and erg, f"(c) NUR_BAUEN mit gueltigem STL: rc {r.returncode}, ERGEBNIS {erg}")
            else: pruef(r.returncode not in (0, 1) and not erg, f"(c) NUR_BAUEN mit {fall}em STL = rot (rc {r.returncode}, ERGEBNIS-Zeile {erg}): {[z for z in r.stdout.splitlines() if 'STL' in z][-1:]}")
    finally: shutil.rmtree(od, ignore_errors=True)
    # (b) oeffnungen_wandbild ohne Tiefenkarte
    fe = os.path.join(T, "fein"); os.makedirs(fe); oj = os.path.join(T, "obj", "objekt.json"); os.makedirs(os.path.dirname(oj)); json.dump({}, open(oj, "w"))
    json.dump(dict(fassaden=[dict(id="f00", o=[0, 0, 0], d=[1, 0, 0], n=[0, -1, 0], raster=dict(zelle=0.05, u0=0, z1=10, nu=200, nz=200))]), open(os.path.join(fe, "fassaden.json"), "w"))
    json.dump(dict(fassaden={"f00": dict(elemente=[dict(klasse="bogen", u0=2.0, u1=5.0, z0=0.0, z1=4.0)])}), open(os.path.join(fe, "elemente.json"), "w"))
    if os.path.exists(PYS):
        aus = os.path.join(T, "oa.json")
        for zus in ([], ["--tiefe_ordner", os.path.join(T, "keine_tiefe")]):
            r = subprocess.run([PYS, "-W", "ignore", "-I", os.path.join(HIER, "oeffnungen_wandbild.py"), oj, fe, "--aus", aus] + zus, capture_output=True, text=True, timeout=120)
            e = (json.load(open(aus)).get("f00", {}).get("oeffnungen") or [{}])[0] if os.path.exists(aus) else {}
            pruef(r.returncode == 3 and e.get("unentschieden") and e.get("flach") is None and "UNENTSCHIEDEN" in r.stdout,
                  f"(b) Bogen ohne Tiefenkarte {'(kein --tiefe_ordner)' if not zus else '(Ordner ohne tiefe_f00.npz)'}: rc {r.returncode}, flach {e.get('flach')}, unentschieden {e.get('unentschieden')}" + ('' if r.returncode in (0, 3) else ' ' + r.stderr[-200:]))
    else: pruef(False, f"(b) {PYS} fehlt")
    # (d)
    pruef('beleg(B, "bauplan_vorbauten", [os.path.join(Z, "audit", "vorbauten_auto.json")], t_vb, altstand_beiseite=True' in src, "(d) Beleg vorbauten_auto.json (Altstand beiseite)")
    pruef('beleg(B, "hand_vergleich", [os.path.join(Z, "audit", "hand_vergleich.json")], t_hv, altstand_beiseite=True' in src, "(d) Beleg hand_vergleich.json (Altstand beiseite)")
    pruef('"--aus", oi_], log)[0] in (0, 3))' in src, "(d) bauplan_innen_oeffnungen: rc 3 (unentschiedene Boegen) bricht die Innenwand-Kette nicht ab")
    ba = open(os.path.join(HIER, "bauen_abnehmen.sh")).read()
    pruef("kette_beleg.py stl" in ba and ba.index("kette_beleg.py stl") < ba.index("RCPARK_NUR_BAUEN:-0"), "(c) STL-Beleg steht VOR dem NUR_BAUEN-Ausstieg")

print("FEHLER gesamt", F) if F else print("alle Faelle gruen")
sys.exit(1 if F else 0)

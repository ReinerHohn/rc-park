#!/usr/bin/env python3
"""vorwissen_empfindlichkeit.py - Wie viel Vorwissen steckt im Nullstart? (Register BI)

Im Nullstart leitet nur ein Teil der Masse (masse_regeln) frisch aus der Wolke ab; der Rest (ohne Regel) kommt unveraendert aus der Referenz.
Frage je Mass ohne Regel: BEMERKT der Pruefstand, wenn es falsch waere?  Dazu wird jedes dieser Masse einzeln um +-FAKTOR veraendert,
Modell gebaut, Pruefstand gelaufen, und festgehalten, welche Pruefungen von bestanden auf durchgefallen kippen.
  kontrolliert   = mindestens eine Pruefung faellt (das Mass ist durch Quellen/Messungen abgesichert)
  unkontrolliert = Modell aendert sich, aber keine Pruefung merkt es (freier Parameter bzw. reine Annahme/Handwert)
  wirkungslos    = das STL bleibt bitgleich (Mass wird vom Generator nicht gelesen, z. B. wegen PROFIL_DATEI)
Arbeitet in einer KOPIE des Nullstart-Ordners (modelle/<ziel>_vw -> Datenplatte), der echte bleibt unberuehrt.
  python3 -I tools/vorwissen_empfindlichkeit.py modelle/martinstor/objekt.json [--ziel martinstor_null] [--faktor 0.15]
Ergebnis: modelle/<ziel>/vorwissen_empfindlichkeit.json + Zusammenfassung auf der Konsole.
"""
import sys, os, json, shutil, subprocess, argparse, time, re, hashlib

def lauf(cmd, env, cwd):
    r = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True); return r.returncode, r.stdout + r.stderr

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ziel", default="martinstor_null"); ap.add_argument("--faktor", type=float, default=0.15)
    a = ap.parse_args(); repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ref = json.load(open(os.path.join(repo, a.objekt)))
    zd = os.path.realpath(os.path.join(repo, "modelle", a.ziel)); vw_name = a.ziel + "_vw"; vw_link = os.path.join(repo, "modelle", vw_name)
    vw_real = os.path.join(os.path.dirname(zd), vw_name)
    if os.path.exists(vw_real): shutil.rmtree(vw_real)
    shutil.copytree(zd, vw_real, ignore=shutil.ignore_patterns("sfm", "audit", "regression"), symlinks=True)
    if os.path.islink(vw_link): os.remove(vw_link)
    os.symlink(vw_real, vw_link)
    for d in ("sfm", "audit", "regression"):                                       # grosse/unbenoetigte Ordner: Verweis auf das Original (nur lesen)
        if os.path.exists(os.path.join(zd, d)) and not os.path.exists(os.path.join(vw_real, d)): os.symlink(os.path.join(zd, d), os.path.join(vw_real, d))
    oj = json.load(open(os.path.join(vw_real, "objekt.json"))); oj["name"] = oj.get("name", "") + " (Vorwissen-Test)"; oj["stl"] = f"modelle/stl/{vw_name}_v4_1-87.stl"
    for k_, v_ in list(oj.items()):                                                # ALLE Pfade der Kopie auf die Kopie umbiegen (masstabelle, audit, ...) - sonst schreibt der Pruefstand
        if isinstance(v_, str) and f"modelle/{a.ziel}/" in v_: oj[k_] = v_.replace(f"modelle/{a.ziel}/", f"modelle/{vw_name}/")   # in den ECHTEN Ordner (Fehler 2026-11-02: Pruefbericht ueberschrieben)
    json.dump(oj, open(os.path.join(vw_real, "objekt.json"), "w"), indent=1, ensure_ascii=False)
    assert oj["masstabelle"].startswith(f"modelle/{vw_name}/"), "masstabelle zeigt nicht auf die Kopie"
    pb_echt = os.path.join(zd, "pruefbericht.json"); pb_echt_stamp = os.path.getmtime(pb_echt) if os.path.exists(pb_echt) else None
    gen = oj["generator"].replace(a.ziel + "_v4", vw_name + "_v4").replace(f"OBJ_DIR={a.ziel}", f"OBJ_DIR={vw_name}").replace(f"STL_NAME={a.ziel}_v4_1-87.stl", f"STL_NAME={vw_name}_v4_1-87.stl")
    env = dict(os.environ); PY = "/media/oem/scan/venv-seg/bin/python"
    mp = os.path.join(vw_real, "masse.json"); M0 = json.load(open(mp)); regeln = {r.get("masse") for r in ref.get("masse_regeln", [])}
    kand = [k for k, v in M0["masse"].items() if k not in regeln and isinstance(v, dict) and isinstance(v.get("wert"), (int, float)) and not isinstance(v.get("wert"), bool)]
    def pruefen():
        rc, o = lauf(gen, env, repo)
        if rc != 0: return None, "Generator: " + o.strip().splitlines()[-1][:120] if o.strip() else "Generator rc %d" % rc
        pb = os.path.join(vw_real, "pruefbericht.json")
        if os.path.exists(pb): os.remove(pb)                                        # alten (kopierten) Bericht nie wiederverwenden
        rc, o = lauf(f"{PY} -W ignore -I tools/pruefstand.py modelle/{vw_name}/objekt.json", env, repo)
        if not os.path.exists(pb): return None, "kein Pruefbericht (Pruefstand schrieb nicht in die Kopie)"
        if vw_name not in json.load(open(pb)).get("stl", ""): return None, "Pruefbericht gehoert nicht zum Variantenmodell"
        B = json.load(open(pb)); sp = os.path.join(repo, oj["stl"]); h = hashlib.md5(open(sp, "rb").read()).hexdigest() if os.path.exists(sp) else None
        return ({p["name"]: bool(p["ok"]) for p in B["pruefungen"]}, h), None
    t0 = time.time(); _b, fehler = pruefen()
    if _b is None: raise SystemExit(f"Basislauf scheitert: {fehler}")
    basis, h_basis = _b
    print(f"Basis: {sum(basis.values())}/{len(basis)} bestanden ({time.time() - t0:.0f} s je Lauf); {len(kand)} Masse ohne Regel, Faktor +-{a.faktor:.0%}", flush=True)
    erg = {}
    for k in kand:
        w0 = M0["masse"][k]["wert"]; res = {"typ": M0["masse"][k].get("quelltyp"), "wert": w0, "richtungen": {}}; gekippt = set()
        for sg in (+1, -1):
            M1 = json.loads(json.dumps(M0)); M1["masse"][k]["wert"] = round(w0 * (1 + sg * a.faktor), 4) if w0 != 0 else sg * a.faktor; json.dump(M1, open(mp, "w"), indent=1, ensure_ascii=False)
            _p, fe = pruefen()
            if _p is None: res["richtungen"][f"{sg:+d}"] = {"fehler": fe}; continue
            P, h = _p; kipp = sorted(n for n, ok in P.items() if basis.get(n, True) and not ok); gekippt.update(kipp); res["richtungen"][f"{sg:+d}"] = {"gekippt": kipp, "bestanden": sum(P.values()), "modell_gleich": h == h_basis}
        res["status"] = "kontrolliert" if gekippt else ("generatorfehler" if all("fehler" in r for r in res["richtungen"].values()) else ("wirkungslos" if all(r.get("modell_gleich") for r in res["richtungen"].values() if "fehler" not in r) else "unkontrolliert")); res["gekippt"] = sorted(gekippt)
        erg[k] = res; print(f"  {k:18} {str(res['typ']):18} {res['status']:14} {len(gekippt):2} Pruefungen {sorted(gekippt)[:2]}", flush=True)
        json.dump(M0, open(mp, "w"), indent=1, ensure_ascii=False)
    z = {s: sorted(k for k, v in erg.items() if v["status"] == s) for s in ("kontrolliert", "unkontrolliert", "wirkungslos", "generatorfehler")}
    out = dict(datum=time.strftime("%Y-%m-%d %H:%M"), faktor=a.faktor, basis=f"{sum(basis.values())}/{len(basis)}", zusammenfassung={s: len(v) for s, v in z.items()}, unkontrolliert=z["unkontrolliert"], masse=erg)
    json.dump(out, open(os.path.join(zd, "vorwissen_empfindlichkeit.json"), "w"), indent=1, ensure_ascii=False)
    print(f"\nVorwissen: {len(z['kontrolliert'])} kontrolliert, {len(z['unkontrolliert'])} UNKONTROLLIERT (Modell aendert sich, keine Pruefung merkt es), {len(z['wirkungslos'])} wirkungslos (Modell bleibt gleich), {len(z['generatorfehler'])} Generatorfehler")
    print("unkontrolliert:", ", ".join(z["unkontrolliert"]))
    os.remove(vw_link); shutil.rmtree(vw_real, ignore_errors=True)
    if pb_echt_stamp is not None and os.path.getmtime(pb_echt) != pb_echt_stamp: print("WARNUNG: der echte pruefbericht.json wurde veraendert - Pruefstand neu laufen lassen!")

if __name__ == "__main__":
    main()

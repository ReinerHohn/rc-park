#!/usr/bin/env python3
"""nullstart.py - BEWEIS: ein Objekt mit der aktuellen Pipeline von den EINGABEN aus neu erzeugen und mit dem Referenzstand vergleichen.

Eingaben (werden in einen frischen Objektordner kopiert): objekt.json (angepasst), masse.json, anker3d.json, masstabelle.json (Sollwerte),
fassade.json, messprotokoll/K-*.json + V-*.json (Picks; abgeleitete Kameras werden entfernt), torbau/ (Nebengebaeude, nicht Teil des Laufs).
Geteilt und nur gelesen: Fotos (fotos_dir), DOM1-Fenster (laser.fenster_npy), LoD2-Kacheln.
NICHT kopiert (wird neu gerechnet): sfm/ (Netze, Dichtwolke, Entzerrung), SFM-AUSRICHTUNG-*.json, profile_*.json, elemente.json,
pruefbericht.json, audit/, regression/basis.

Kette (jeder Schritt mit Laufzeit und Rueckgabewert in <ziel>/nullstart_bericht.json):
  netz nord/sued -> ausrichten (Wandebene) -> verzerrungstest (Gate, protokolliert) -> registrieren 060/061 -> Generator (ohne Profile)
  -> dichte Wolke nord -> entzerren (wolke_vs_modell) -> foto_kalibrieren 061 -> regression.py <ziel> --schnappschuss (Auswertungskette)
  -> Vergleich mit dem Referenzstand (regression/basis des Referenzobjekts) mit SfM-Toleranzen.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/nullstart.py modelle/martinstor/objekt.json --ziel martinstor_null [--ab <schritt>] [--ohne-sued]
Ehrlichkeit: masse.json ist Eingabe. Werte darin, die frueher von Hand aus Werkzeugausgaben uebertragen wurden (Historie 'grund'), werden
NICHT neu abgeleitet - der Bericht listet sie (Stufe C). Automatisch neu entstehen Netze, Wolke, Profile, Baender, Pruefzeilen, Modell (Stufen A+B).
"""
import sys, os, json, glob, shutil, subprocess, time, argparse

PY = "/media/oem/scan/venv-seg/bin/python"; PC = "/media/oem/scan/venv-colmap/bin/python"; RC = os.path.expanduser("~/.venvs/rcpark/bin/python")

def lauf(bericht, name, cmd, repo, log, ok_rcs=(0,)):
    t0 = time.time(); print(f"\n+++ {name}: {cmd[:160]}", flush=True)
    with open(log, "a") as L:
        L.write(f"\n\n=== {name} @ {time.strftime('%H:%M:%S')}\n$ {cmd}\n"); L.flush()
        r = subprocess.run(cmd, shell=True, cwd=repo, stdout=L, stderr=subprocess.STDOUT, text=True)
    dt = time.time() - t0; eintrag = dict(schritt=name, kommando=cmd, rc=r.returncode, sekunden=round(dt, 1), ok=r.returncode in ok_rcs)
    bericht["schritte"].append(eintrag); json.dump(bericht, open(bericht["_pfad"], "w"), indent=1, ensure_ascii=False)
    print(f"    rc {r.returncode}, {dt:.0f} s", flush=True)
    return r.returncode in ok_rcs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ziel", default="martinstor_null"); ap.add_argument("--ab", default="anlegen"); ap.add_argument("--ohne-sued", action="store_true")
    a = ap.parse_args(); ref = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od)); refname = os.path.basename(od)
    zd = os.path.join(repo, "modelle", a.ziel); os.makedirs(zd, exist_ok=True); zobj = os.path.join(zd, "objekt.json"); log = os.path.join(zd, "nullstart.log")
    bp = os.path.join(zd, "nullstart_bericht.json"); bericht = json.load(open(bp)) if os.path.exists(bp) and a.ab != "anlegen" else dict(referenz=refname, ziel=a.ziel, start=time.strftime("%Y-%m-%d %H:%M"), schritte=[])
    bericht["_pfad"] = bp
    schritte = ["anlegen", "netz_nord", "netz_sued", "ausrichten_nord", "ausrichten_sued", "verzerrung", "registrieren", "generator0", "dicht", "entzerren", "kalibrieren_061", "auswertung", "vergleich"]
    start_i = schritte.index(a.ab)
    def dran(n): return schritte.index(n) >= start_i
    stl_name = f"{a.ziel}_v4_1-87.stl"
    if dran("anlegen"):
        for d in ("sfm", "messprotokoll", "audit", "regression"): os.makedirs(os.path.join(zd, d), exist_ok=True)
        for f in ("masse.json", "anker3d.json", "masstabelle.json", "fassade.json"): shutil.copy(os.path.join(od, f), zd)
        if os.path.isdir(os.path.join(od, "torbau")): shutil.copytree(os.path.join(od, "torbau"), os.path.join(zd, "torbau"), dirs_exist_ok=True)
        for kp in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")) + glob.glob(os.path.join(od, "messprotokoll", "V-*.json")):
            K = json.load(open(kp))
            for k in list(K):
                if k.startswith("kamera"): K.pop(k)                                                  # abgeleitete Kameras raus - nur Picks bleiben Eingabe
            json.dump(K, open(os.path.join(zd, "messprotokoll", os.path.basename(kp)), "w"), indent=1, ensure_ascii=False)
        o = json.loads(json.dumps(ref)); o["name"] = f"{ref.get('name', refname)} (Nullstart)"; o["stl"] = f"modelle/stl/{stl_name}"; o["masstabelle"] = f"modelle/{a.ziel}/masstabelle.json"; o["audit"] = f"modelle/{a.ziel}/audit"
        o["generator"] = f"SCALE=87 MINMM=0.8 OBJ_DIR={a.ziel} STL_NAME={stl_name} {RC} modelle/martinstor_v4_gen.py"
        for nb in o.get("nebengebaeude", {}).values():
            for k, v in list(nb.items()):
                if isinstance(v, str) and f"modelle/{refname}/" in v: nb[k] = v.replace(f"modelle/{refname}/", f"modelle/{a.ziel}/")
        o["regression"]["kette"] = [c.replace("{RC} modelle/martinstor_v4_gen.py", f"OBJ_DIR={a.ziel} STL_NAME={stl_name} {{RC}} modelle/martinstor_v4_gen.py") for c in o["regression"]["kette"]]
        o["regression"]["dateien"]["stl"]["pfad"] = f"../stl/{stl_name}"; o["nullstart"] = dict(referenz=refname, hinweis="von den Eingaben neu gerechnet (tools/nullstart.py)")
        json.dump(o, open(zobj, "w"), indent=1, ensure_ascii=False); open(log, "w").write(f"Nullstart {a.ziel} aus {refname}\n")
        bericht["schritte"].append(dict(schritt="anlegen", ok=True, kopiert=["masse.json", "anker3d.json", "masstabelle.json", "fassade.json", "messprotokoll/K-*,V-* (ohne Kameras)", "torbau/"])); json.dump(bericht, open(bp, "w"), indent=1, ensure_ascii=False)
    Z = os.path.relpath(zobj, repo)
    seiten = ["nord"] + ([] if a.ohne_sued else ["sued"])
    for s in seiten:
        if dran(f"netz_{s}") and not lauf(bericht, f"netz_{s}", f"{PC} -I tools/sfm_netz.py {Z} {s} --reparieren", repo, log): sys.exit(f"netz_{s} fehlgeschlagen")
    for s in seiten:
        if dran(f"ausrichten_{s}") and not lauf(bericht, f"ausrichten_{s}", f"{PC} -I tools/sfm_ausrichten.py {Z} --sparse modelle/{a.ziel}/sfm/sparse_{s}/0 --name {s} --wand {s} --schreiben", repo, log): sys.exit(f"ausrichten_{s} fehlgeschlagen")
    if dran("verzerrung") and not a.ohne_sued:
        lauf(bericht, "verzerrung_nord", f"{PC} -I tools/sfm_verzerrung_test.py {Z} --sparse modelle/{a.ziel}/sfm/sparse_modell_nord --spiegel modelle/{a.ziel}/messprotokoll/SFM-AUSRICHTUNG-sued.json", repo, log, ok_rcs=(0, 1))   # Gate: protokolliert, bricht den Nullstart nicht ab
    if dran("registrieren"):
        lauf(bericht, "registrieren_060", f"{PC} -I tools/sfm_registrieren.py {Z} --netz nord --foto 060 --schreiben", repo, log, ok_rcs=(0, 1))
        lauf(bericht, "registrieren_061", f"{PC} -I tools/sfm_registrieren.py {Z} --netz nord --foto 061 --hoehe 44 8 --schreiben", repo, log, ok_rcs=(0, 1))
    if dran("generator0") and not lauf(bericht, "generator0", json.load(open(zobj))["generator"], repo, log): sys.exit("generator0 fehlgeschlagen")
    if dran("dicht") and not lauf(bericht, "dicht_nord", f"{PC} -I tools/sfm_dicht.py {Z} nord", repo, log): sys.exit("dicht fehlgeschlagen")
    if dran("entzerren") and not lauf(bericht, "entzerren", f"{PY} -W ignore -I tools/wolke_vs_modell.py {Z} nord --entzerren --nebengebaeude", repo, log): sys.exit("entzerren fehlgeschlagen")
    if dran("kalibrieren_061"): lauf(bericht, "kalibrieren_061", f"{PY} -W ignore -I tools/foto_kalibrieren.py {Z} 061", repo, log, ok_rcs=(0, 1))
    if dran("auswertung") and not lauf(bericht, "auswertung", f"{PY} -W ignore -I tools/regression.py {Z} --schnappschuss", repo, log): sys.exit("auswertung fehlgeschlagen")
    if dran("vergleich"):
        sys.path.insert(0, os.path.join(repo, "tools")); import regression as RG
        R = json.load(open(zobj))["regression"]; basis_ref = os.path.join(od, "regression", "basis"); basis_ziel = os.path.join(zd, "regression", "basis")
        tol = {"silhouette_061": 0.3, "profile_generator": 0.35, "profile_nord": 0.35, "baender_tuermchen": 0.3, "baender_zentral": 0.3, "masstabelle": 0.35, "pruefbericht": 0.35, "elemente": 0.35, "stl": 0.05, "wolke_vs_modell": 0.5}
        ign = {"datum", "historie", "schichten", "details", "befunde", "n", "n_fit", "zeilen", "kante", "quelle", "hinweis"}
        verg = {}
        for name in R["dateien"]:
            pr, pz = os.path.join(basis_ref, name + ".json"), os.path.join(basis_ziel, name + ".json")
            if not (os.path.exists(pr) and os.path.exists(pz)): verg[name] = dict(status="fehlt"); continue
            A, B = json.load(open(pr)), json.load(open(pz))
            if name == "stl":
                dv = abs(A["volumen"] - B["volumen"]) / max(A["volumen"], 1e-9); verg[name] = dict(status="ok" if dv <= tol["stl"] else "abweichung", volumen_ref=A["volumen"], volumen_ziel=B["volumen"], rel=round(dv, 4), dreiecke=[A["dreiecke"], B["dreiecke"]]); continue
            if name == "pruefbericht":
                okA = sum(A["ok"].values()); okB = sum(B["ok"].values()); diff = RG.vergleiche(A["werte"], B["werte"], tol[name], ign)
                verg[name] = dict(status="ok" if not diff else "abweichung", bestanden_ref=f"{okA}/{len(A['ok'])}", bestanden_ziel=f"{okB}/{len(B['ok'])}", werte_abweichend=len(diff), beispiele=diff[:10]); continue
            diff = RG.vergleiche(A, B, tol[name], ign); verg[name] = dict(status="ok" if not diff else "abweichung", abweichungen=len(diff), beispiele=diff[:8])
        # Stufe C: Masse, die aus Werkzeugausgaben von Hand uebertragen wurden (Historie mit Werkzeugnamen) - werden im Nullstart NICHT neu abgeleitet
        M = json.load(open(os.path.join(zd, "masse.json")))["masse"]; hand = sorted(k for k, v in M.items() if any(w in (v.get("quelle", "") + " ".join(h.get("grund", "") for h in v.get("historie", []))) for w in ("wolke_", "foto_silhouette", "foto_kalibrieren", "Register A")))
        bericht["vergleich"] = verg; bericht["stufe_C_masse_von_hand_uebertragen"] = hand; bericht["ende"] = time.strftime("%Y-%m-%d %H:%M")
        json.dump(bericht, open(bp, "w"), indent=1, ensure_ascii=False)
        print("\n=== VERGLEICH Nullstart vs Referenz"); [print(f"  {n:18s} {v.get('status'):10s} {json.dumps({k: x for k, x in v.items() if k not in ('status', 'beispiele')}, ensure_ascii=False)[:120]}") for n, v in verg.items()]
        print(f"  Stufe C (Masse aus Werkzeugausgaben, von Hand in masse.json): {len(hand)} - {hand[:12]}{' ...' if len(hand) > 12 else ''}")

if __name__ == "__main__":
    main()

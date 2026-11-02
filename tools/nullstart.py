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
import sys, os, json, glob, shutil, subprocess, time, argparse, resource

PY = "/media/oem/scan/venv-seg/bin/python"; PC = "/media/oem/scan/venv-colmap/bin/python"; RC = os.path.expanduser("~/.venvs/rcpark/bin/python")

def gpu_warten(max_mib=1500, max_s=3600):
    """Vor GPU-Schritten warten, bis kein anderer Prozess die GPU belegt (COLMAP SIFT-GPU stuerzt sonst mit 'illegal memory access' ab)."""
    t0 = time.time()
    while time.time() - t0 < max_s:
        try: used = int(subprocess.run("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits", shell=True, capture_output=True, text=True).stdout.strip().split()[0])
        except Exception: return
        if used < max_mib: return
        print(f"    GPU belegt ({used} MiB) - warte", flush=True); time.sleep(30)

def lauf(bericht, name, cmd, repo, log, ok_rcs=(0,)):
    if ("sfm_netz.py" in cmd and "--cpu" not in cmd) or "sfm_dicht.py" in cmd: gpu_warten()
    t0 = time.time(); print(f"\n+++ {name}: {cmd[:160]}", flush=True)
    with open(log, "a") as L:
        L.write(f"\n\n=== {name} @ {time.strftime('%H:%M:%S')}\n$ {cmd}\n"); L.flush()
        r = subprocess.run(cmd, shell=True, cwd=repo, stdout=L, stderr=subprocess.STDOUT, text=True, preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))   # kein Core-Dump auf die Root-Platte (Nullstart 5/6: 2 x 1,3 GB)
    dt = time.time() - t0; eintrag = dict(schritt=name, kommando=cmd, rc=r.returncode, sekunden=round(dt, 1), ok=r.returncode in ok_rcs, uebersprungen=(r.returncode == 3 and 3 in ok_rcs))
    bericht["schritte"].append(eintrag); json.dump(bericht, open(bericht["_pfad"], "w"), indent=1, ensure_ascii=False)
    print(f"    rc {r.returncode}{' (uebersprungen: keine Daten)' if eintrag['uebersprungen'] else ''}, {dt:.0f} s", flush=True)
    return r.returncode in ok_rcs

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ziel", default="martinstor_null"); ap.add_argument("--ab", default="anlegen"); ap.add_argument("--streng", action="store_true", help="Startwerte aller regelabgeleiteten Masse auf die MITTE ihres Plausibilitaetsfensters setzen: scheitert eine Ableitung, faellt es im Pruefstand auf, statt dass der Referenzwert still stehen bleibt (Register BF)"); ap.add_argument("--sued-seriell", action="store_true", help="Suednetz vor dem dichten Schritt statt parallel dazu (CPU) rechnen"); ap.add_argument("--mapper", default="incremental", choices=["incremental", "global"], help="Mapper der Hauptseite: incremental (Standard) | global = GLOMAP (Register BF)"); ap.add_argument("--netzversuche", type=int, default=6, help="parallele Mapper-Versuche der Hauptseite (Auswahl nach Massstab-Sigma)"); ap.add_argument("--ohne-sued", action="store_true")
    a = ap.parse_args(); ref = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od)); refname = os.path.basename(od)
    zd = os.path.join(repo, "modelle", a.ziel); os.makedirs(zd, exist_ok=True); zobj = os.path.join(zd, "objekt.json"); log = os.path.join(zd, "nullstart.log")
    bp = os.path.join(zd, "nullstart_bericht.json"); bericht = json.load(open(bp)) if os.path.exists(bp) and a.ab != "anlegen" else dict(referenz=refname, ziel=a.ziel, start=time.strftime("%Y-%m-%d %H:%M"), schritte=[])
    bericht["_pfad"] = bp
    schritte = ["anlegen", "netz_nord", "netz_sued", "ausrichten_nord", "ausrichten_sued", "verzerrung", "registrieren", "generator0", "dicht", "entzerren", "kalibrieren_061", "auswertung", "vergleich"]
    start_i = schritte.index(a.ab)
    def dran(n): return schritte.index(n) >= start_i
    stl_name = f"{a.ziel}_v4_1-87.stl"
    if dran("anlegen"):
        # ALLES Abgeleitete entfernen (sonst fusioniert sfm_dicht alte Tiefenkarten mit neuen Posen: Nullstart 2 lieferte 476 statt 99 000 Punkte)
        for d in ("sfm", "audit", "regression", "torbau"):
            if os.path.isdir(os.path.join(zd, d)): shutil.rmtree(os.path.join(zd, d))
        for f in glob.glob(os.path.join(zd, "*.json")) + glob.glob(os.path.join(zd, "*.md")) + glob.glob(os.path.join(zd, "messprotokoll", "*")): os.remove(f)
        for d in ("sfm", "messprotokoll", "audit", "regression"): os.makedirs(os.path.join(zd, d), exist_ok=True)
        for f in ("masse.json", "anker3d.json", "masstabelle.json", "fassade.json"): shutil.copy(os.path.join(od, f), zd)
        if a.streng:
            mj = json.load(open(os.path.join(zd, "masse.json"))); n_s = 0
            for rg in ref.get("masse_regeln", []):
                if rg.get("masse") in mj["masse"] and rg.get("bereich") and isinstance(mj["masse"][rg["masse"]]["wert"], (int, float)): mj["masse"][rg["masse"]]["wert"] = round(sum(rg["bereich"]) / 2, 3); n_s += 1
            json.dump(mj, open(os.path.join(zd, "masse.json"), "w"), indent=1, ensure_ascii=False); print(f"    streng: {n_s} Startwerte auf Fenstermitte gesetzt", flush=True)
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
    haupt = json.load(open(zobj)).get("sfm", {}).get("hauptseite", "nord"); sfmd = os.path.join(zd, "sfm")
    def netz_und_ausrichten(s, lg_=None, cpu_=False):
        """Netz bauen + ausrichten. COLMAP ist nicht deterministisch (Register BF): gleiche Eingaben gaben Netze mit Massstab-Sigma 2,8 bis 24,6 %.
        Hauptseite: Merkmale + Matches EINMAL (GPU), dann K Mapper-Versuche mit eigenem Seed PARALLEL auf der CPU, je Versuch ausrichten; das Netz mit
        kleinstem Sigma (+ 2 je entfernte Kamera) wird uebernommen und kanonisch neu ausgerichtet. Andere Seiten: ein Versuch."""
        lg_ = lg_ or log; kan = lambda cmd_: lauf(bericht, f"ausrichten_{s}", cmd_, repo, lg_)
        auskmd = lambda sp, name, extra="": f"{PC} -I tools/sfm_ausrichten.py {Z} --sparse {sp} --name {name} --wand {s} {extra}"
        if s != haupt:
            return lauf(bericht, f"netz_{s}", f"{PC} -I tools/sfm_netz.py {Z} {s} --reparieren" + (" --cpu" if cpu_ else ""), repo, lg_) and kan(auskmd(f"modelle/{a.ziel}/sfm/sparse_{s}/0", s, "--schreiben"))
        if not lauf(bericht, f"merkmale_{s}", f"{PC} -I tools/sfm_netz.py {Z} {s} --nur-merkmale", repo, log): return False
        K = a.netzversuche; procs = []; t0 = time.time()
        for k in range(1, K + 1):
            cmd_ = f"{PC} -I tools/sfm_netz.py {Z} {s} --reparieren --db-von db_{s}.db --seed {k} --tag v{k} --threads 4 --mapper {a.mapper}"
            L = open(log, "a"); L.write(f"\n\n=== netz_{s}_v{k} (parallel) @ {time.strftime('%H:%M:%S')}\n$ {cmd_}\n"); L.flush()
            procs.append((k, subprocess.Popen(cmd_, shell=True, cwd=repo, stdout=L, stderr=subprocess.STDOUT, text=True, preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))))
        for k, pr in procs: pr.wait()
        print(f"    {K} Netzversuche parallel: {time.time() - t0:.0f} s", flush=True)
        versuche = []
        for k, pr in procs:
            sp = f"modelle/{a.ziel}/sfm/sparse_{s}_v{k}/0"; nb = os.path.join(sfmd, f"netz_{s}_v{k}.json")
            if pr.returncode != 0 or not os.path.exists(os.path.join(repo, sp)) or not os.path.exists(nb): versuche.append(dict(versuch=k, fehler=True)); continue
            nj = json.load(open(nb)); entf = sum(len(r.get("entfernt", [])) for r in nj.get("runden", []) if isinstance(r, dict)); ok_ = sum(1 for r in nj.get("runden", [])[-1:] for _ in [0])
            r_ = subprocess.run(auskmd(sp, f"{s}_v{k}"), shell=True, cwd=repo, capture_output=True, text=True, preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
            import re as _re; m_ = _re.search(r"Massstab SfM-Einheiten/m = ([\d.]+) \+- ([\d.]+) %", r_.stdout)
            versuche.append(dict(versuch=k, sigma=float(m_.group(2)) if m_ else 99.0, entfernt=entf, kameras=len(nj.get("ergebnis", {}).get("registriert", [])), fehler=r_.returncode != 0 or not m_))
            print(f"    Versuch {k}: Sigma {versuche[-1]['sigma']:.1f} %, entfernte Kameras {entf}, Kameras {versuche[-1]['kameras']}", flush=True)
        gut = [v for v in versuche if not v.get("fehler")]
        if not gut: print("    kein brauchbarer Netzversuch", flush=True); return False
        best = min(gut, key=lambda v: v["sigma"] - 0.1 * v["kameras"]); k = best["versuch"]          # Sigma entscheidet; Kameras nur bei Gleichstand (Lauf 9: Sigma 5,8 % gewaehlt wegen 0 entfernter Kameras -> Turm 3 m zu tief)
        for t in (f"sparse_{s}", f"sparse_{s}_bilder"):
            shutil.rmtree(os.path.join(sfmd, t), ignore_errors=True); shutil.copytree(os.path.join(sfmd, f"{t.replace(s, s + '_v' + str(k), 1)}"), os.path.join(sfmd, t), symlinks=True)
        shutil.copy2(os.path.join(sfmd, f"netz_{s}_v{k}.json"), os.path.join(sfmd, f"netz_{s}.json")); shutil.copy2(os.path.join(sfmd, f"db_{s}_v{k}.db"), os.path.join(sfmd, f"db_{s}.db")) if os.path.exists(os.path.join(sfmd, f"db_{s}_v{k}.db")) else None
        for t in glob.glob(os.path.join(sfmd, f"*_{s}_v*")) + glob.glob(os.path.join(zd, "messprotokoll", f"*{s}_v*")) + glob.glob(os.path.join(sfmd, f"sparse_modell_{s}_v*")): shutil.rmtree(t, ignore_errors=True) if os.path.isdir(t) else os.remove(t)
        bericht["schritte"].append(dict(schritt=f"netzwahl_{s}", ok=True, versuche=versuche, gewaehlt=k)); json.dump(bericht, open(bp, "w"), indent=1, ensure_ascii=False)
        print(f"    gewaehlt: Versuch {k} von {K}", flush=True)
        return kan(auskmd(f"modelle/{a.ziel}/sfm/sparse_{s}/0", s, "--schreiben"))
    import threading; sued_thr = []; sued_res = {}
    for s in seiten:
        if dran(f"netz_{s}"):
            if s != haupt and not a.sued_seriell and dran("dicht"):                                 # Suednetz auf der CPU PARALLEL zum dichten Schritt der Hauptseite (spart ~1,5 min)
                t_ = threading.Thread(target=lambda s_=s: sued_res.__setitem__(s_, netz_und_ausrichten(s_, os.path.join(zd, "nullstart_sued.log"), True))); t_.start(); sued_thr.append(t_); continue
            if not netz_und_ausrichten(s): sys.exit(f"netz_{s} fehlgeschlagen")
    for s in seiten:
        if dran(f"ausrichten_{s}") and not dran(f"netz_{s}") and not lauf(bericht, f"ausrichten_{s}", f"{PC} -I tools/sfm_ausrichten.py {Z} --sparse modelle/{a.ziel}/sfm/sparse_{s}/0 --name {s} --wand {s} --schreiben", repo, log): sys.exit(f"ausrichten_{s} fehlgeschlagen")
    def verzerrung_gate():
        lauf(bericht, "verzerrung_nord", f"{PC} -I tools/sfm_verzerrung_test.py {Z} --sparse modelle/{a.ziel}/sfm/sparse_modell_nord --spiegel messprotokoll/SFM-AUSRICHTUNG-sued.json", repo, log, ok_rcs=(0, 1))   # Gate: protokolliert, bricht den Nullstart nicht ab
    if dran("verzerrung") and not a.ohne_sued and not sued_thr: verzerrung_gate()
    if dran("registrieren"):
        lauf(bericht, "registrieren_060", f"{PC} -I tools/sfm_registrieren.py {Z} --netz nord --foto 060 --schreiben", repo, log, ok_rcs=(0, 1))
        lauf(bericht, "registrieren_061", f"{PC} -I tools/sfm_registrieren.py {Z} --netz nord --foto 061 --hoehe 44 8 --schreiben", repo, log, ok_rcs=(0, 1))
    if dran("generator0") and not lauf(bericht, "generator0", json.load(open(zobj))["generator"], repo, log): sys.exit("generator0 fehlgeschlagen")
    if dran("dicht") and not lauf(bericht, "dicht_nord", f"{PC} -I tools/sfm_dicht.py {Z} nord", repo, log): sys.exit("dicht fehlgeschlagen")
    for t_ in sued_thr: t_.join()                                                                 # Suednetz (CPU) war parallel zum dichten Schritt unterwegs
    if sued_thr:
        print(f"    Suednetz parallel: {'ok' if all(sued_res.values()) else 'FEHLER'} (Log nullstart_sued.log)", flush=True)
        if dran("verzerrung") and not a.ohne_sued: verzerrung_gate()
    if dran("entzerren") and not lauf(bericht, "entzerren", f"{PY} -W ignore -I tools/wolke_vs_modell.py {Z} nord --entzerren --nebengebaeude", repo, log): sys.exit("entzerren fehlgeschlagen")
    if dran("kalibrieren_061"):   # alle Kameras aus Picks + Ankern neu loesen (Schritt heisst historisch kalibrieren_061): jedes K-Protokoll
        for kp in sorted(glob.glob(os.path.join(zd, "messprotokoll", "K-*.json"))):
            nr = os.path.basename(kp)[2:-5]; lauf(bericht, f"kalibrieren_{nr}", f"{PY} -W ignore -I tools/foto_kalibrieren.py {Z} {nr}", repo, log, ok_rcs=(0, 1, 3))
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
        # Masse: Referenz vs Nullstart (beide von masse_aus_profilen.py geschrieben) - der eigentliche Stufe-C-Test
        try:
            from bauteile import lade_masse
            MR, MZ = lade_masse(os.path.join(od, "masse.json")), lade_masse(os.path.join(zd, "masse.json")); dm = {}
            for k in MR:
                if k in MZ and isinstance(MR[k], float) and abs(MR[k] - MZ[k]) > 0.3 + 1e-6 * abs(MR[k]): dm[k] = [round(MR[k], 2), round(MZ[k], 2)]
            RB = json.load(open(os.path.join(zd, "masse_regeln_bericht.json")))["bericht"] if os.path.exists(os.path.join(zd, "masse_regeln_bericht.json")) else []
            verg["masse"] = dict(status="ok" if not dm else "abweichung", abweichend_ueber_0_3=dm, abgeleitet=sum(1 for b in RB if b["status"] == "abgeleitet"), bleibt_hand=[b["masse"] for b in RB if b["status"] == "bleibt_hand"], fehler=[b["masse"] for b in RB if b["status"] == "fehler"])
        except Exception as e: verg["masse"] = dict(status="fehler", fehler=str(e))
        # Stufe C: Masse, die aus Werkzeugausgaben von Hand uebertragen wurden (Historie mit Werkzeugnamen) - werden im Nullstart NICHT neu abgeleitet
        M = json.load(open(os.path.join(zd, "masse.json")))["masse"]; hand = sorted(k for k, v in M.items() if any(w in (v.get("quelle", "") + " ".join(h.get("grund", "") for h in v.get("historie", []))) for w in ("wolke_", "foto_silhouette", "foto_kalibrieren", "Register A")))
        bericht["vergleich"] = verg; bericht["stufe_C_masse_von_hand_uebertragen"] = hand; bericht["ende"] = time.strftime("%Y-%m-%d %H:%M")
        json.dump(bericht, open(bp, "w"), indent=1, ensure_ascii=False)
        print("\n=== VERGLEICH Nullstart vs Referenz"); [print(f"  {n:18s} {v.get('status'):10s} {json.dumps({k: x for k, x in v.items() if k not in ('status', 'beispiele')}, ensure_ascii=False)[:120]}") for n, v in verg.items()]
        try:                                                                                        # Serienprotokoll: welche Pruefung scheitert in wie vielen Laeufen? (tools/nullstart_serie.py wertet aus)
            sp = os.path.join(od, "nullstart_serie.json"); S_ = json.load(open(sp)) if os.path.exists(sp) else dict(laeufe=[])
            PB = json.load(open(os.path.join(basis_ziel, "pruefbericht.json"))); nz = [n for n, ok in PB["ok"].items() if not ok]; RBz = verg.get("masse", {})
            nw = next((s_ for s_ in bericht["schritte"] if s_.get("schritt", "").startswith("netzwahl")), {})
            S_["laeufe"].append(dict(datum=time.strftime("%Y-%m-%d %H:%M"), mapper=a.mapper, streng=a.streng, netzwahl=nw.get("gewaehlt"), versuche=nw.get("versuche"),
                bestanden=f"{sum(PB['ok'].values())}/{len(PB['ok'])}", nicht_bestanden=nz, masse_abweichend=sorted(RBz.get("abweichend_ueber_0_3", {})), frisch_abgeleitet=RBz.get("abgeleitet"),
                bleibt_referenz=RBz.get("bleibt_hand"), uebersprungen=[s_["schritt"] for s_ in bericht["schritte"] if s_.get("uebersprungen")]))
            json.dump(S_, open(sp, "w"), indent=1, ensure_ascii=False); print(f"  Serie: Lauf {len(S_['laeufe'])} protokolliert in {os.path.relpath(sp, repo)} (tools/nullstart_serie.py)")
        except Exception as e: print("  Serienprotokoll fehlgeschlagen:", e)
        print(f"  Stufe C (Masse aus Werkzeugausgaben, von Hand in masse.json): {len(hand)} - {hand[:12]}{' ...' if len(hand) > 12 else ''}")

if __name__ == "__main__":
    main()

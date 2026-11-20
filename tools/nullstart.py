#!/usr/bin/env python3
"""nullstart.py - BEWEIS: ein Objekt mit der aktuellen Pipeline von den EINGABEN aus neu erzeugen und mit dem Referenzstand vergleichen.

Eingaben (werden in einen frischen Objektordner kopiert): objekt.json (angepasst), masse.json, anker3d.json, masstabelle.json (Sollwerte),
fassade.json, messprotokoll/K-*.json + V-*.json (Picks; abgeleitete Kameras werden entfernt), torbau/ (Nebengebaeude, nicht Teil des Laufs).
Geteilt und nur gelesen: Fotos (fotos_dir; KEIN Download - Ordner wird gegen fotoliste.json (SHA-256) geprueft, tools/fotoliste.py), DOM1-Fenster (laser.fenster_npy), LoD2-Kacheln.
NICHT kopiert (wird neu gerechnet): sfm/ (Netze, Dichtwolke, Entzerrung), SFM-AUSRICHTUNG-*.json, profile_*.json, elemente.json,
pruefbericht.json, audit/, regression/basis.

GENERISCH (modelle/NULLSTART_GENERALITAET.md): Seiten = Fotolisten in objekt.json['sfm'] (Hauptseite sfm.hauptseite), Zusatzfotos sfm.registrieren
[{foto, netz, hoehe}], Generator = objekt.json['generator'], Nebengebaeude-Ordner aus objekt.json['nebengebaeude'], Vergleichstoleranzen regression.toleranzen.
Kette (jeder Schritt mit Laufzeit und Rueckgabewert in <ziel>/nullstart_bericht.json):
  netz je Seite -> ausrichten (Wandebene) -> verzerrungstest (Gate, protokolliert) -> registrieren (sfm.registrieren) -> Generator (ohne Profile)
  -> dichte Wolke Hauptseite -> entzerren (wolke_vs_modell) -> foto_kalibrieren (alle K-Protokolle) -> regression.py <ziel> --schnappschuss (Auswertungskette)
  -> Vergleich mit dem Referenzstand (regression/basis des Referenzobjekts) mit SfM-Toleranzen.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/nullstart.py modelle/<objekt>/objekt.json [--ziel <objekt>_null] [--ab <schritt>] [--ohne-sued]
Ehrlichkeit: masse.json ist Eingabe. Werte darin, die frueher von Hand aus Werkzeugausgaben uebertragen wurden (Historie 'grund'), werden
NICHT neu abgeleitet - der Bericht listet sie (Stufe C). Automatisch neu entstehen Netze, Wolke, Profile, Baender, Pruefzeilen, Modell (Stufen A+B).
Weitere Optionen u. a.: --stufe, --mapper, --videos/--nur-video, --streng, --ohne-stufen. Steuerung in venv-seg; Teilschritte laufen selbst mit
venv-colmap (SfM) bzw. ~/.venvs/rcpark (Generator). Grosse Zielordner nur auf der Datenplatte (echter Ordner auf der Root-Platte -> Abbruch).
Exit 0 = Kette durch; fehlende Eingabe oder gescheiterter Schritt -> Abbruch mit Text (Exit 1), Stand in nullstart_bericht.json.
"""
import sys, os, json, glob, shutil, subprocess, time, argparse, resource
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PY = "/media/oem/scan/venv-seg/bin/python"; PC = "/media/oem/scan/venv-colmap/bin/python"; RC = os.path.expanduser("~/.venvs/rcpark/bin/python")

def gpu_warten(max_mib=1500, max_s=3600):
    """Vor GPU-Schritten warten, bis kein anderer Prozess die GPU belegt (COLMAP SIFT-GPU stuerzt sonst mit 'illegal memory access' ab)."""
    t0 = time.time()
    while time.time() - t0 < max_s:
        try: used = int(subprocess.run("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits", shell=True, capture_output=True, text=True).stdout.strip().split()[0])
        except Exception: return
        if used < max_mib: return
        print(f"    GPU belegt ({used} MiB) - warte", flush=True); time.sleep(30)

import threading as _th
_BERICHT_SPERRE = _th.Lock()

def lauf(bericht, name, cmd, repo, log, ok_rcs=(0,)):
    if ("sfm_netz.py" in cmd and "--cpu" not in cmd) or "sfm_dicht.py" in cmd or "video_sfm.py" in cmd or "video_dicht.py" in cmd or "video_ausrichten.py" in cmd: gpu_warten()
    t0 = time.time(); print(f"\n+++ {name}: {cmd[:160]}", flush=True)
    with open(log, "a") as L:
        L.write(f"\n\n=== {name} @ {time.strftime('%H:%M:%S')}\n$ {cmd}\n"); L.flush()
        r = subprocess.run(cmd, shell=True, cwd=repo, stdout=L, stderr=subprocess.STDOUT, text=True, preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))   # kein Core-Dump auf die Root-Platte (Nullstart 5/6: 2 x 1,3 GB)
    dt = time.time() - t0; eintrag = dict(schritt=name, kommando=cmd, rc=r.returncode, sekunden=round(dt, 1), ok=r.returncode in ok_rcs, uebersprungen=(r.returncode == 3 and 3 in ok_rcs))
    with _BERICHT_SPERRE:
        bericht["schritte"].append(eintrag); json.dump(bericht, open(bericht["_pfad"], "w"), indent=1, ensure_ascii=False)
    print(f"    rc {r.returncode}{' (uebersprungen: keine Daten)' if eintrag['uebersprungen'] else ''}, {dt:.0f} s", flush=True)
    return r.returncode in ok_rcs

def _stl_hoehe(pfad):
    """z-Ausdehnung einer STL (binaer oder ASCII) ohne trimesh."""
    import numpy as np
    roh = open(pfad, "rb").read()
    n = int.from_bytes(roh[80:84], "little")
    if len(roh) == 84 + 50 * n:
        z = np.frombuffer(roh[84:], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n)["v"][:, :, 2]
    else:
        z = np.array([float(l.split()[3]) for l in roh.decode(errors="ignore").splitlines() if l.strip().startswith("vertex")])
    return float(z.max() - z.min())

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ziel", default=None, help="Zielordner unter modelle/ (Standard <referenz>_null)"); ap.add_argument("--netz-threads", type=int, default=1, help="Mapper-Threads je Netzversuch. STANDARD 1 = bit-reproduzierbares Netz (Register CA: mit 4 Threads streuen Punktzahl/Kameras bei gleichem Seed)"); ap.add_argument("--ab", default="anlegen"); ap.add_argument("--stufe", default="auto", choices=["voll", "fein", "grob", "auto"], help="STANDARD auto = Aufloesung aus modelle/<objekt>/sweetspot.json (tools/sweetspot.py), sonst grob; fein = voll (1600 px, ueber Nacht); grob = Entwurf: dichte Stufe bei --grob-px (Standard 1000 px, alle Fotos; Register BM); voll = alle Fotos, 1600 px (Standard)"); ap.add_argument("--grob-fotos", type=int, default=0, help="0 = alle Fotos (Standard; Foto-Teilmengen verloren Tuermchen/Zinnen, Register BM), N = nur die N besten"); ap.add_argument("--grob-px", type=int, default=1000); ap.add_argument("--kamera-modell", default="", help="COLMAP-Kameramodell fuer die Strassennetze (sfm_netz.py --kamera-modell); leer = SIMPLE_RADIAL (Register BU)"); ap.add_argument("--videos", action="store_true", help="Videostufe: Drohnen-/Videoframes (objekt.json video_stufe) -> SfM -> Ausrichtung -> dichte Wolke -> obere Haelfte einfuegen (Register BQ)"); ap.add_argument("--nur-video", action="store_true", help="Schritt video als letzten ausfuehren (nach video_merge Ende: keine Folgeschritte, kein auswertung/regression-Schnappschuss; Register CR)"); ap.add_argument("--video-clips", default="", help="nur diese Clips (Komma) statt video_stufe.clips; eigener Arbeitsordner d_<ziel>_<clips>"); ap.add_argument("--videos-neu", action="store_true", help="Video-SfM neu rechnen (sonst Zwischenergebnis wiederverwenden)"); ap.add_argument("--dicht-extra", default="", help="zusaetzliche Argumente fuer sfm_dicht.py, z. B. \"--max-size 1200 --fotos 014,031\" (Stufenmodell, Register BK)"); ap.add_argument("--kal-seriell", action="store_true", help="Kalibrierung wie frueher erst nach entzerren (nicht parallel zu PatchMatch)"); ap.add_argument("--streng", action="store_true", help="Startwerte aller regelabgeleiteten Masse auf die MITTE ihres Plausibilitaetsfensters setzen: scheitert eine Ableitung, faellt es im Pruefstand auf, statt dass der Referenzwert still stehen bleibt (Register BF)"); ap.add_argument("--sued-seriell", action="store_true", help="Suednetz vor dem dichten Schritt statt parallel dazu (CPU) rechnen"); ap.add_argument("--mapper", default="incremental", choices=["incremental", "global"], help="Mapper der Hauptseite: incremental (Standard) | global = GLOMAP (Register BF)"); ap.add_argument("--netzversuche", type=int, default=6, help="parallele Mapper-Versuche der Hauptseite (Auswahl nach Massstab-Sigma)"); ap.add_argument("--ohne-sued", action="store_true"); ap.add_argument("--ohne-stufen", action="store_true", help="Qualitaetsstufen (Plan modelle/PLAN_STANDARD_qualitaetsstufen.json) NICHT anschliessen")
    a = ap.parse_args(); KM = f" --kamera-modell {a.kamera_modell}" if a.kamera_modell else ""; ref = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od)); refname = os.path.basename(od)
    a.ziel = a.ziel or f"{refname}_null"
    # GENERISCH (modelle/NULLSTART_GENERALITAET.md B2-B5): Seiten, Registrierfotos, Generator, Nebengebaeude-Ordner, Toleranzen aus objekt.json - kein Objektwissen hier
    SEITEN_ALLE = ("nord", "sued", "ost", "west")
    sfm_cfg = ref.get("sfm", {}); haupt = sfm_cfg.get("hauptseite") or next((s_ for s_ in SEITEN_ALLE if isinstance(sfm_cfg.get(s_), list)), "nord")
    seiten_cfg = [haupt] + [s_ for s_ in SEITEN_ALLE if s_ != haupt and isinstance(sfm_cfg.get(s_), list)]
    nebenseiten = seiten_cfg[1:]
    gen_ref = ref["generator"]; gen_py = next(t for t in gen_ref.split() if t.endswith(".py"))
    neben_dirs = sorted({v.split(f"modelle/{refname}/", 1)[1].split("/")[0] for nb in ref.get("nebengebaeude", {}).values() for v in nb.values() if isinstance(v, str) and f"modelle/{refname}/" in v and "/" in v.split(f"modelle/{refname}/", 1)[1]})
    zd = os.path.join(repo, "modelle", a.ziel)
    # Datenplatten-Regel (Nutzer 2026-11-01): Nullstart-Ziele (SfM-Netze, dichte Wolken: GB) NIE auf der Root-Platte. Kaufhaus 2026-11-04: Ziel wurde als echter
    # Ordner im Repo angelegt, PatchMatch schrieb 2,3 GB, Root lief auf 100 % voll. Jetzt: Ziel immer unter DATEN_NULL anlegen und im Repo verlinken; ein echter
    # Ordner auf der Root-Platte bricht ab.
    daten_null = os.environ.get("RCPARK_NULL", "/media/oem/scan/rc-park_null")
    if not os.path.lexists(zd):
        os.makedirs(os.path.join(daten_null, a.ziel), exist_ok=True); os.symlink(os.path.join(daten_null, a.ziel), zd)
    elif not os.path.islink(zd) and os.stat(zd).st_dev == os.stat(repo).st_dev:
        sys.exit(f"{zd} ist ein echter Ordner auf der Root-Platte - zuerst nach {daten_null}/{a.ziel} verschieben und verlinken (Datenplatten-Regel)")
    zobj = os.path.join(zd, "objekt.json"); log = os.path.join(zd, "nullstart.log")
    bp = os.path.join(zd, "nullstart_bericht.json"); bericht = json.load(open(bp)) if os.path.exists(bp) and a.ab != "anlegen" else dict(referenz=refname, ziel=a.ziel, start=time.strftime("%Y-%m-%d %H:%M"), schritte=[])
    bericht["_pfad"] = bp
    schritte = ["anlegen"] + [f"netz_{s_}" for s_ in seiten_cfg] + [f"ausrichten_{s_}" for s_ in seiten_cfg] + ["verzerrung", "registrieren", "buendel", "generator0", "dicht", "grundriss", "dach", "entzerren", "video", "kameras", "kamera_bruecke", "kalibrieren", "beweis_anker", "kamera_lod2", "textur", "abgleich", "wolke_seiten", "auswertung", "overlay", "hybrid", "vergleich", "beweise", "stufen"]
    a.ab = {"kalibrieren_061": "kalibrieren", "netz_nord": f"netz_{haupt}"}.get(a.ab, a.ab)          # alte Schrittnamen weiter erlaubt
    start_i = schritte.index(a.ab)
    def dran(n): return schritte.index(n) >= start_i
    # Ausrichtung: mit LoD2-Eckpicks (K-*.json) sfm_ausrichten.py, ohne Picks (neues Objekt, Kaltstart) sfm_lod2_ausrichten.py (LoD2-Umgebung + DGM1, Plan B7)
    _picks = any(any(n.startswith("ecke_boden") for n in list(json.load(open(kp)).get("punkte", {})) + list(json.load(open(kp)).get("linien", {}))) for kp in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")))
    AUSR = sfm_cfg.get("ausrichtung_werkzeug") or ("sfm_ausrichten.py" if _picks else "sfm_lod2_ausrichten.py")
    print(f"    Ausrichtung: {AUSR} ({'LoD2-Eckpicks vorhanden' if _picks else 'keine Eckpicks - automatisch an LoD2/DGM1'})", flush=True)
    stl_name = os.path.basename(ref["stl"]).replace(refname, a.ziel, 1) if refname in os.path.basename(ref["stl"]) else f"{a.ziel}_1-87.stl"
    if dran("anlegen"):
        # ALLES Abgeleitete entfernen (sonst fusioniert sfm_dicht alte Tiefenkarten mit neuen Posen: Nullstart 2 lieferte 476 statt 99 000 Punkte)
        for d in ("sfm", "audit", "regression", *neben_dirs):
            if os.path.isdir(os.path.join(zd, d)): shutil.rmtree(os.path.join(zd, d))
        for f in glob.glob(os.path.join(zd, "*.json")) + glob.glob(os.path.join(zd, "*.md")) + glob.glob(os.path.join(zd, "messprotokoll", "*")): os.remove(f)
        for d in ("sfm", "messprotokoll", "audit", "regression"): os.makedirs(os.path.join(zd, d), exist_ok=True)
        for f in ("masse.json", "anker3d.json", "masstabelle.json", "fassade.json"):
            if os.path.exists(os.path.join(od, f)): shutil.copy(os.path.join(od, f), zd)
            elif f in ("masse.json", "fassade.json"):                                              # neues Objekt (Kaltstart): leeres Geruest, keine erfundenen Werte
                json.dump({"masse": {}} if f == "masse.json" else {}, open(os.path.join(zd, f), "w"), indent=1); print(f"    {f} fehlt in der Referenz - leeres Geruest (Kaltstart)", flush=True)
            else: sys.exit(f"Eingabe {f} fehlt in modelle/{refname}/ (anker3d: tools/objekt_daten.py, masstabelle: tools/objekt_anlegen.py)")
        if a.streng:
            mj = json.load(open(os.path.join(zd, "masse.json"))); n_s = 0
            for rg in ref.get("masse_regeln", []):
                if rg.get("masse") in mj["masse"] and rg.get("bereich") and isinstance(mj["masse"][rg["masse"]]["wert"], (int, float)): mj["masse"][rg["masse"]]["wert"] = round(sum(rg["bereich"]) / 2, 3); n_s += 1
            json.dump(mj, open(os.path.join(zd, "masse.json"), "w"), indent=1, ensure_ascii=False); print(f"    streng: {n_s} Startwerte auf Fenstermitte gesetzt", flush=True)
        for sp_ in ref.get("bauteile", []):                                                           # Bauteil-Eingaben (z. B. fassade_raster 'datei' = Foto-Ablesung) sind Eingaben wie die Picks (2026-11-04: kaufhaus_null2 brach ohne fassade_nord.json ab)
            df_ = sp_.get("datei") if isinstance(sp_, dict) else None
            if df_ and os.path.exists(os.path.join(od, df_)): os.makedirs(os.path.dirname(os.path.join(zd, df_)) or zd, exist_ok=True); shutil.copy(os.path.join(od, df_), os.path.join(zd, df_)); print(f"    Bauteil-Eingabe {df_} kopiert", flush=True)
            elif df_: sys.exit(f"Bauteil-Eingabe {df_} fehlt in modelle/{refname}/")
        for nd_ in neben_dirs:                                                                        # Nebengebaeude-Ordner (aus objekt.json['nebengebaeude'] abgeleitet)
            if os.path.isdir(os.path.join(od, nd_)): shutil.copytree(os.path.join(od, nd_), os.path.join(zd, nd_), dirs_exist_ok=True)
        for kp in glob.glob(os.path.join(od, "messprotokoll", "Z-*")) + glob.glob(os.path.join(od, "messprotokoll", "M-*")):   # Foto-Zaehl-/Massprotokolle = Eingaben wie die Picks (Register CB/CE)
            shutil.copy(kp, os.path.join(zd, "messprotokoll"))
        for kp in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")) + glob.glob(os.path.join(od, "messprotokoll", "V-*.json")):
            K = json.load(open(kp))
            if "kalibrier_optionen" not in K:                                                       # aeltere Protokolle: Optionen aus der Referenzloesung ableiten (Register CK)
                K["kalibrier_optionen"] = ["--silhouette"] if K.get("kamera", {}).get("silhouette_genutzt") else []
            for k in list(K):
                if k.startswith("kamera"): K.pop(k)                                                  # abgeleitete Kameras raus - nur Picks bleiben Eingabe
            json.dump(K, open(os.path.join(zd, "messprotokoll", os.path.basename(kp)), "w"), indent=1, ensure_ascii=False)
        o = json.loads(json.dumps(ref)); o["name"] = f"{ref.get('name', refname)} (Nullstart)"; o["stl"] = f"modelle/stl/{stl_name}"; o["masstabelle"] = f"modelle/{a.ziel}/masstabelle.json"; o["audit"] = f"modelle/{a.ziel}/audit"
        o["generator"] = f"OBJ_DIR={a.ziel} STL_NAME={stl_name} {gen_ref}"                       # Generator des Referenzobjekts, nur Ziel-Ordner/STL umgelenkt
        for nb in o.get("nebengebaeude", {}).values():
            for k, v in list(nb.items()):
                if isinstance(v, str) and f"modelle/{refname}/" in v: nb[k] = v.replace(f"modelle/{refname}/", f"modelle/{a.ziel}/")
        import re as _re
        o.setdefault("regression", {}).setdefault("kette", []); o["regression"].setdefault("dateien", {})
        o["regression"]["kette"] = [_re.sub(r"(\S+\s+" + _re.escape(gen_py) + r")", f"OBJ_DIR={a.ziel} STL_NAME={stl_name} \\1", c).replace(ref["stl"], o["stl"]) if gen_py in c else c.replace(ref["stl"], o["stl"]) for c in o["regression"]["kette"]]
        if "stl" in o["regression"]["dateien"]: o["regression"]["dateien"]["stl"]["pfad"] = f"../stl/{stl_name}"
        o["nullstart"] = dict(referenz=refname, hinweis="von den Eingaben neu gerechnet (tools/nullstart.py)")
        json.dump(o, open(zobj, "w"), indent=1, ensure_ascii=False); open(log, "w").write(f"Nullstart {a.ziel} aus {refname}\n")
        bericht["schritte"].append(dict(schritt="anlegen", ok=True, kopiert=["masse.json", "anker3d.json", "masstabelle.json", "fassade.json", "messprotokoll/K-*,V-* (ohne Kameras), Z-*, M-* (Foto-Zaehl-/Massprotokolle)", "" + "/, ".join(neben_dirs) + "/"])); __import__("json_sicher").schreiben(bp, bericht)
    Z = os.path.relpath(zobj, repo)
    # Foto-Eingang belegen (Register BZ): der Nullstart laedt keine Bilder, liest nur fotos_dir -> Ordner gegen festgeschriebene Fotoliste (SHA-256) pruefen
    if a.ab == "anlegen" and os.path.exists(os.path.join(od, "fotoliste.json")):
        lauf(bericht, "fotoliste", f"{PY} -I tools/fotoliste.py {os.path.relpath(a.objekt, repo) if not os.path.isabs(a.objekt) else a.objekt} --pruefen", repo, log, ok_rcs=(0,))
    seiten = [haupt] + ([] if a.ohne_sued else nebenseiten); sfmd = os.path.join(zd, "sfm")
    def netz_und_ausrichten(s, lg_=None, cpu_=False):
        """Netz bauen + ausrichten. COLMAP ist nicht deterministisch (Register BF): gleiche Eingaben gaben Netze mit Massstab-Sigma 2,8 bis 24,6 %.
        Hauptseite: Merkmale + Matches EINMAL (GPU), dann K Mapper-Versuche mit eigenem Seed PARALLEL auf der CPU, je Versuch ausrichten; das Netz mit
        kleinstem Sigma (+ 2 je entfernte Kamera) wird uebernommen und kanonisch neu ausgerichtet. Andere Seiten: ein Versuch."""
        lg_ = lg_ or log; kan = lambda cmd_: lauf(bericht, f"ausrichten_{s}", cmd_, repo, lg_)
        auskmd = lambda sp, name, extra="": f"{PC} -I tools/{AUSR} {Z} --sparse {sp} --name {name} --wand {s} {extra}"
        if s != haupt:
            return lauf(bericht, f"netz_{s}", f"{PC} -I tools/sfm_netz.py {Z} {s} --reparieren{KM}" + (" --cpu" if cpu_ else ""), repo, lg_) and kan(auskmd(f"modelle/{a.ziel}/sfm/sparse_{s}/0", s, "--schreiben"))
        if not lauf(bericht, f"merkmale_{s}", f"{PC} -I tools/sfm_netz.py {Z} {s} --nur-merkmale{KM}", repo, log): return False
        K = a.netzversuche; procs = []; t0 = time.time()
        for k in range(1, K + 1):
            cmd_ = f"{PC} -I tools/sfm_netz.py {Z} {s} --reparieren --db-von db_{s}.db --seed {k} --tag v{k} --threads {a.netz_threads} --mapper {a.mapper}{KM}"
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
        bericht["schritte"].append(dict(schritt=f"netzwahl_{s}", ok=True, versuche=versuche, gewaehlt=k)); __import__("json_sicher").schreiben(bp, bericht)
        print(f"    gewaehlt: Versuch {k} von {K}", flush=True)
        return kan(auskmd(f"modelle/{a.ziel}/sfm/sparse_{s}/0", s, "--schreiben"))
    import threading; sued_thr = []; sued_res = {}
    for s in seiten:
        if dran(f"netz_{s}"):
            if s != haupt and not a.sued_seriell and dran("dicht"):                                 # Suednetz auf der CPU PARALLEL zum dichten Schritt der Hauptseite (spart ~1,5 min)
                t_ = threading.Thread(target=lambda s_=s: sued_res.__setitem__(s_, netz_und_ausrichten(s_, os.path.join(zd, f"nullstart_{s_}.log"), True))); t_.start(); sued_thr.append(t_); continue
            if not netz_und_ausrichten(s): sys.exit(f"netz_{s} fehlgeschlagen")
    for s in seiten:
        if dran(f"ausrichten_{s}") and not dran(f"netz_{s}") and not lauf(bericht, f"ausrichten_{s}", f"{PC} -I tools/{AUSR} {Z} --sparse modelle/{a.ziel}/sfm/sparse_{s}/0 --name {s} --wand {s} --schreiben", repo, log): sys.exit(f"ausrichten_{s} fehlgeschlagen")
    def verzerrung_gate():
        for ns_ in nebenseiten:
            lauf(bericht, f"verzerrung_{haupt}", f"{PC} -I tools/sfm_verzerrung_test.py {Z} --sparse modelle/{a.ziel}/sfm/sparse_modell_{haupt} --spiegel messprotokoll/SFM-AUSRICHTUNG-{ns_}.json", repo, log, ok_rcs=(0, 1))   # Gate: protokolliert, bricht den Nullstart nicht ab
    if dran("verzerrung") and not a.ohne_sued and not sued_thr: verzerrung_gate()
    if dran("registrieren"):
        for rg_ in sfm_cfg.get("registrieren", []):                                              # Zusatzfotos ins Netz (objekt.json sfm.registrieren: foto, netz, hoehe)
            hh_ = f" --hoehe {rg_['hoehe'][0]} {rg_['hoehe'][1]}" if rg_.get("hoehe") else ""
            lauf(bericht, f"registrieren_{rg_['foto']}", f"{PC} -I tools/sfm_registrieren.py {Z} --netz {rg_.get('netz', haupt)} --foto {rg_['foto']}{hh_} --schreiben", repo, log, ok_rcs=(0, 1))
    # Buendel mit LoD2/DGM1-Flaechen + EXIF-Brennweiten (Kaufhaus 2026-11-04): Einzelfoto-Netze ohne Picks haben schlecht bestimmte Brennweiten -> Wolke
    # in sich verzerrt. Standard: an, wenn ohne Picks ausgerichtet wurde (sfm_lod2_ausrichten); objekt.json sfm.buendel true/false erzwingt. Die dichte Wolke rechnet dann auf diesem Netz.
    buendel_an = sfm_cfg.get("buendel", AUSR == "sfm_lod2_ausrichten.py"); netz_dicht = ""
    if buendel_an:
        if dran("buendel") and not lauf(bericht, "buendel", f"{PC} -u -W ignore -I tools/sfm_lod2_buendel.py {Z} {haupt} --name buendel --schreiben", repo, log): sys.exit("buendel fehlgeschlagen")
        netz_dicht = " --netz buendel"
    if dran("generator0") and not lauf(bericht, "generator0", json.load(open(zobj))["generator"], repo, log): sys.exit("generator0 fehlgeschlagen")
    kal_fertig = False
    def _hat_picks(kp):                                                                             # nur K-Protokolle mit Picks kalibrieren; Buendelkameras (kameras_aus_buendel) nicht ueberschreiben
        K_ = json.load(open(kp)); return bool(K_.get("punkte") or K_.get("linien"))
    def kal_opt(nr):                                                                              # Kalibrier-Optionen aus dem K-Protokoll (z. B. --silhouette), wie in der Referenz
        return " ".join(json.load(open(os.path.join(zd, "messprotokoll", f"K-{nr}.json"))).get("kalibrier_optionen", []))
    def kalibrieren_alle():                                                                       # je Foto unabhaengig: liest anker3d.json + eigenes K-<foto>.json, schreibt nur dasselbe K-<foto>.json
        from concurrent.futures import ThreadPoolExecutor
        nrs = [os.path.basename(kp)[2:-5] for kp in sorted(glob.glob(os.path.join(zd, "messprotokoll", "K-*.json"))) if _hat_picks(kp)]
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(nrs)))) as ex:
            list(ex.map(lambda nr: lauf(bericht, f"kalibrieren_{nr}", f"{PY} -W ignore -I tools/foto_kalibrieren.py {Z} {nr} {kal_opt(nr)}".rstrip(), repo, log, ok_rcs=(0, 1, 3)), nrs))
    kal_thr = None
    if dran("kalibrieren") and dran("dicht") and not a.kal_seriell:                           # CPU war waehrend PatchMatch zu 93 % leer (Messung 2026-11-02): Kalibrierung dorthin verlegen
        kal_thr = _th.Thread(target=kalibrieren_alle); kal_thr.start(); kal_fertig = True
    dicht_extra = a.dicht_extra
    if a.stufe == "fein": a.stufe = "voll"
    if a.stufe == "auto" and not dicht_extra:
        sp_ = os.path.join(od, "sweetspot.json")
        if os.path.exists(sp_): a.grob_px = int(json.load(open(sp_))["px"]); print(f"    Stufe auto: Sweet Spot {a.grob_px} px aus {os.path.relpath(sp_, repo)}", flush=True)
        else: print(f"    Stufe auto: keine sweetspot.json ({os.path.relpath(sp_, repo)}) - Rueckfall grob {a.grob_px} px; Messung: tools/sweetspot.py", flush=True)
        a.stufe = "grob"
    if a.stufe == "grob" and not dicht_extra and dran("dicht"):                                   # Stufe grob: Fotoauswahl aus dem frisch gebauten Netz
        import re as _re
        dicht_extra = f"--max-size {a.grob_px}"
        if a.grob_fotos > 0:
            r_ = subprocess.run([PC, "-I", "tools/foto_auswahl.py", Z, "--waehle", str(a.grob_fotos)], cwd=repo, capture_output=True, text=True).stdout
            m_ = _re.search(r"--fotos (\S+)", r_)
            if m_: dicht_extra += f" --fotos {m_.group(1)}"
        print(f"    Stufe grob: {dicht_extra}", flush=True)
    bericht["stufe"] = a.stufe; bericht["dicht_extra"] = dicht_extra
    if dran("dicht") and not lauf(bericht, f"dicht_{haupt}", f"{PC} -I tools/sfm_dicht.py {Z} {haupt}{netz_dicht} {dicht_extra}", repo, log): sys.exit("dicht fehlgeschlagen")
    for t_ in sued_thr: t_.join()                                                                 # Suednetz (CPU) war parallel zum dichten Schritt unterwegs
    if sued_thr:
        print(f"    Suednetz parallel: {'ok' if all(sued_res.values()) else 'FEHLER'} (Log nullstart_<seite>.log)", flush=True)
        if dran("verzerrung") and not a.ohne_sued: verzerrung_gate()
    if dran("grundriss"):                                                                         # Lehre Schwabentor 2026-11-14: Fluegel 1 m duenn auf der Strasse, Kameraluecke 103 Grad,
        wk_ = os.path.join(sfmd, f"dicht_{haupt}_modell.npy"); sp_ = f"modelle/{a.ziel}/sfm/sparse_{haupt}/0"   # Ausrichtung 0,222 vs 0,194 mehrdeutig -> vor Modellierung pruefen
        if os.path.exists(os.path.join(repo, sp_)):
            lauf(bericht, "kamera_abdeckung", f"{PY} -I tools/kamera_abdeckung.py {sp_}", repo, log)   # rc 2 = Seite ohne Kameras: Warnung, kein Abbruch
        au_ = f"modelle/{a.ziel}/messprotokoll/SFM-AUSRICHTUNG-{haupt}.json"                  # Lehre Schwabentor: Lage 1,8x zu klein + 134 Grad verdreht, GPS haette es gezeigt
        if os.path.exists(os.path.join(repo, au_)) and not lauf(bericht, "lage_gps", f"{PY} -I tools/lage_gps_pruefen.py {Z} {au_}", repo, log):
            print("    WARNUNG lage_gps: Ausrichtung widerspricht dem Foto-GPS - audit/lage_gps.json ansehen, NICHT modellieren", flush=True)
        if os.path.exists(wk_):
            if not lauf(bericht, "grundriss", f"{PY} -I tools/wolke_grundriss_pruefen.py {Z} --wolke {wk_}", repo, log):
                print("    WARNUNG grundriss: Wolke auf der Strasse oder Lage gegen LoD2 mehrdeutig - audit/wolke_grundriss.png ansehen, NICHT modellieren", flush=True)
    if dran("dach"):                                                                              # Lehre Schwabentor 2026-11-14: Dach war Pyramiden-ANNAHME; DOM1 zeigte Zelt 56 Grad + Spitze
        _oz = json.load(open(os.path.join(repo, Z)))                                               # -> dach.json (Ebenen je LoD2-Teil), Generator baut es mit tools/dach_bauen.py
        if _oz.get("lod2", {}).get("id"):
            wk_ = os.path.join(sfmd, f"dicht_{haupt}_modell.npy")
            lauf(bericht, "dach", f"{PY} -I tools/dach_vermessen.py {Z}" + (f" --wolke {wk_}" if os.path.exists(wk_) else ""), repo, log)
        else: bericht["schritte"].append(dict(schritt="dach", ok=True, uebersprungen=True, grund="objekt.json ohne lod2.id"))
    _SEITEN = SEITEN_ALLE
    if dran("entzerren") and haupt.lower() not in _SEITEN:                                         # Netz 'alle' (Buendel an LoD2): keine einseitige Tiefendrift -> ueberspringen statt abbrechen (Kaufhaus: KeyError 'alle')
        bericht["schritte"].append(dict(schritt="entzerren", ok=True, uebersprungen=True, grund=f"Netz '{haupt}' ist keine Fassadenseite {sorted(_SEITEN)}; Buendel haelt die Wolke an LoD2/DGM1")); __import__("json_sicher").schreiben(bp, bericht)
    elif dran("entzerren") and not lauf(bericht, "entzerren", f"{PY} -W ignore -I tools/wolke_vs_modell.py {Z} {haupt} --entzerren" + (" --nebengebaeude" if ref.get("nebengebaeude") else ""), repo, log): sys.exit("entzerren fehlgeschlagen")
    if dran("video") and a.videos:                                                              # Videostufe (Register BQ): Drohnenclips -> SfM -> Ausrichtung -> dichte Wolke -> obere Haelfte in die Nordwolke
        vz = json.load(open(zobj)).get("video_stufe") or {}; vd = vz.get("ordner"); PCV = PC; _n0v = len(bericht["schritte"])
        if not (vd and vz.get("clips") and vz.get("frames")): print("    Videostufe: keine video_stufe in objekt.json - uebersprungen", flush=True)
        else:
            cl_ = [c_ for c_ in a.video_clips.split(",") if c_] or vz["clips"]; fr = vz["frames"]; clips = " ".join(cl_); vs = os.path.join(vd, "d_" + a.ziel + ("_" + "+".join(c_[:6] for c_ in cl_) if a.video_clips else ""))
            # Register CR: Netz/Pfade aus objekt.json (video_netz.py); Frames je Clip begrenzt, Matching sequenziell + Retrieval (100-450 Frames < 1 h statt exhaustiv)
            vmf = vz.get("max_frames_je_clip", 40); vmm = vz.get("matching", "sequenziell"); vmod = "--modell auto"
            # Eigene Videos (Nutzer 6.11.): fehlen Frames eines Clips, aber liegt <video_ordner>/<clip>/<clip>.* lokal, Frames automatisch ziehen (video_frames.py --file)
            vvo = vz.get("video_ordner") or os.path.join(os.path.dirname(fr.rstrip("/")), "video")
            for c_ in cl_:
                if os.path.exists(os.path.join(fr, c_, "manifest.json")): continue
                vq = sorted(glob.glob(os.path.join(vvo, c_, c_ + ".*")))
                if vq: lauf(bericht, "video_frames_" + c_, f"{PCV} -I tools/video_frames.py --file {vq[0]} --out {os.path.join(fr, c_)} --fps {vz.get('fps', 2)}", repo, log)
                else: print(f"    Videostufe: Clip {c_} ohne Frames und ohne lokale Videodatei in {vvo} - video_sfm wird ihn nicht finden", flush=True)
            if a.videos_neu or not os.path.exists(os.path.join(vs, "sparse")): lauf(bericht, "video_sfm", f"{PCV} -I tools/video_sfm.py {fr} {vs} --clips {clips} --max-frames-je-clip {vmf} --matching {vmm}", repo, log)
            if lauf(bericht, "video_ausrichten", f"{PCV} -W ignore -I tools/video_ausrichten.py {Z} {vs} {vmod} --jeder {vz.get('jeder', 2)}" + (f" --tol-m {vz['tol_m']}" if vz.get("tol_m") else ""), repo, log) and lauf(bericht, "video_dicht", f"{PCV} -W ignore -I tools/video_dicht.py {Z} {vs} {vmod}", repo, log):
                lauf(bericht, "video_merge", f"{PCV} -W ignore -I tools/video_merge.py {Z} {vs} --zmin {vz.get('zmin', 38)}", repo, log)   # Standard: nach sfm/dicht_<netz>_video/, Basiswolke bleibt; objekt.json freiraum_video
    if a.nur_video and a.videos and dran("video"):
        bericht["ende"] = time.strftime("%Y-%m-%d %H:%M"); bericht["nur_video"] = True; __import__("json_sicher").schreiben(bp, bericht)
        print("    --nur-video: Schritt video fertig - keine Folgeschritte (kein auswertung/regression-Schnappschuss)", flush=True); sys.exit(0 if all(x.get("ok", True) for x in bericht["schritte"][_n0v:]) else 1)
    if kal_thr is not None: kal_thr.join()
    ausr_b = os.path.join(zd, "messprotokoll", "SFM-AUSRICHTUNG-buendel.json")
    if dran("kameras") and os.path.exists(ausr_b):                                                  # Kameras fuer ALLE Fotos ohne Picks (Pflichtliste: kameras)
        lauf(bericht, "kameras", f"{PC} -I tools/kameras_aus_buendel.py {Z} --ausrichtung messprotokoll/SFM-AUSRICHTUNG-buendel.json --stl modelle/stl/{stl_name}", repo, log)
    if dran("kamera_bruecke") and os.path.exists(ausr_b):                                           # Tor je Kamera: K-Kamera == Buendel (Selbsttest mit bekannter Wahrheit inklusive)
        lauf(bericht, "kamera_bruecke", f"{PC} -I tools/kamera_bruecke_pruefen.py {Z} --ausrichtung messprotokoll/SFM-AUSRICHTUNG-buendel.json --schreiben --selbsttest", repo, log)
    if dran("kalibrieren") and not kal_fertig:   # alle Kameras aus Picks + Ankern neu loesen (Schritt heisst historisch kalibrieren_061): jedes K-Protokoll
        for kp in [k_ for k_ in sorted(glob.glob(os.path.join(zd, "messprotokoll", "K-*.json"))) if _hat_picks(k_)]:
            nr = os.path.basename(kp)[2:-5]; lauf(bericht, f"kalibrieren_{nr}", f"{PY} -W ignore -I tools/foto_kalibrieren.py {Z} {nr} {kal_opt(nr)}".rstrip(), repo, log, ok_rcs=(0, 1, 3))
    if dran("beweis_anker"): lauf(bericht, "beweis_anker", f"{PY} -W ignore -I tools/beweis_anker.py {Z}", repo, log, ok_rcs=(0, 3))   # Sichtbeweis je Kamera (ansehen!)
    if dran("kamera_lod2"):                                                                         # Zahlen-Tor je Kamera an LoD2 (Pflichtliste offen: synthetisch Kaufhaus ja/Martinstor nein, echt 1 Falschannahme)
        lauf(bericht, "kamera_lod2", f"{PY} -W ignore -I tools/kamera_lod2_nachfuehren.py {Z} --stl modelle/stl/{stl_name}", repo, log, ok_rcs=(0,))   # OFFEN: echte Fotos 2/96, davon 1 falsch (Filmrahmen) -> nur pruefen, nichts schreiben
    dicht_ws = os.path.join(sfmd, f"dicht_{haupt}")
    if dran("textur") and os.path.isdir(os.path.join(dicht_ws, "stereo")) and os.path.exists(ausr_b):   # Fotofarben: Buendelkameras, LoD2-Verdecker, Tiefentest, Texturatlas
        if lauf(bericht, "tiefen_kameras", f"{PC} -I tools/tiefen_kameras.py {dicht_ws}", repo, log):
            os.makedirs(os.path.join(zd, "audit", "textur"), exist_ok=True)
            lauf(bericht, "textur", f"{PY} -W ignore -I tools/textur_projektion.py {Z} --stl modelle/stl/{stl_name} --kameras-sfm messprotokoll/SFM-AUSRICHTUNG-buendel.json --verdecker-lod2 80 --tiefen {dicht_ws} --kante 0.25 --ohne-drohne --ausgabe {zd}/audit/textur/{a.ziel} --atlas 0.025 --atlas-kante 1.0", repo, log)
    if dran("abgleich"):                                                                            # Regel 3e/3f: nur Kameras mit bestandenem LoD2-Tor oder Handkalibrierung (Buendelkamera ohne Tor = unbewiesen)
        n_ab = 0; n_weg = 0
        for kp in sorted(glob.glob(os.path.join(zd, "messprotokoll", "K-*.json"))):
            K_ = json.load(open(kp)).get("kamera") or {}; nr_ = os.path.basename(kp)[2:-5]
            if not K_: continue
            if K_.get("brennweite_quelle") == "buendel" and not ((K_.get("buendel_tor") or {}).get("ok") or (K_.get("lod2_tor") or {}).get("ok")): n_weg += 1; continue   # Buendelkamera nur mit bestandenem Bruecken-Tor
            n_ab += 1; lauf(bericht, f"foto_diff_{nr_}", f"{PY} -W ignore -I tools/foto_diff.py {Z} {nr_} --stl modelle/stl/{stl_name}", repo, log, ok_rcs=(0, 1, 3))
            lauf(bericht, f"fehlteile_{nr_}", f"{PY} -W ignore -I tools/fehlteile_finden.py {Z} {nr_} --stl modelle/stl/{stl_name}", repo, log, ok_rcs=(0, 1, 3))
        bericht["schritte"].append(dict(schritt="abgleich", ok=n_ab > 0, grund=None if n_ab else "keine Kamera mit bewiesenem Tor (buendel_tor/lod2_tor/handkalibriert) - Abgleich nicht erfolgt", fotos=n_ab, ohne_bestandenes_tor=n_weg, hinweis="Buendelkameras ohne bestandenes Bruecken-Tor (kamera_bruecke_pruefen) werden nicht verglichen")); __import__("json_sicher").schreiben(bp, bericht)
        print(f"    abgleich: {n_ab} Fotos verglichen, {n_weg} Kameras ohne bestandenes Tor ausgelassen", flush=True)
    if dran("wolke_seiten"):                                                                        # Wolke gegen Modell je Fassadenseite, auch beim Netz 'alle'
        wk_ = os.path.join(sfmd, f"dicht_{haupt}_modell.npy")
        if os.path.exists(wk_):
            h_ = _stl_hoehe(os.path.join(repo, "modelle", "stl", stl_name)) * json.load(open(zobj)).get("stl_massstab", 87) / 1000.0   # ohne trimesh (Nullstart laeuft im colmap-venv)
            for s_ in sorted(_SEITEN):
                lauf(bericht, f"wolke_seiten_{s_}", f"{PY} -W ignore -I tools/wolke_vs_modell.py {Z} {s_} --dicht {wk_} --schaft {0.35 * h_:.1f} {0.85 * h_:.1f} --auto-rahmen", repo, log, ok_rcs=(0, 1, 3))
    if dran("auswertung") and not lauf(bericht, "auswertung", f"{PY} -W ignore -I tools/regression.py {Z} --schnappschuss", repo, log): sys.exit("auswertung fehlgeschlagen")
    if dran("overlay"):                                                                             # Register BW: Modell-Kanten ueber jedes kalibrierte Foto (Sichtpruefung, Regel 3) -> audit/overlay_<nr>.jpg
        od_ = os.path.join(zd, "audit"); os.makedirs(od_, exist_ok=True); n_ov = 0
        for kp in sorted(glob.glob(os.path.join(zd, "messprotokoll", "K-*.json"))):
            nr_ = os.path.basename(kp)[2:-5]
            if "kamera" in json.load(open(kp)): n_ov += lauf(bericht, f"overlay_{nr_}", f"{PY} -W ignore -I tools/foto_overlay.py {nr_} {od_}/overlay_{nr_}.jpg --objekt modelle/{a.ziel} --stl modelle/stl/{stl_name}", repo, log, ok_rcs=(0,))
        print(f"    overlay: {n_ov} Fotos nach audit/overlay_*.jpg (ansehen!)", flush=True)
    if dran("hybrid"):                                                                              # Register BW: Form vom Generator-STL, Farbe/Verfeinerung aus den Bildpunkten (Exit 3 = Seite fiel durch die Pruefung, kein Abbruch)
        wk = os.path.join(sfmd, f"dicht_{haupt}_entzerrt.npy"); hy = os.path.join(zd, "hybrid")
        if os.path.exists(wk) and os.path.exists(os.path.join(repo, "modelle", "stl", stl_name)):
            lauf(bericht, "hybrid", f"/media/oem/scan/venv-mesh/bin/python -I tools/wolke_auf_generator.py {wk} {hy} --stl modelle/stl/{stl_name}", repo, log, ok_rcs=(0, 3))
        else: print(f"    hybrid uebersprungen: dicht_{haupt}_entzerrt.npy oder STL fehlt", flush=True); bericht["schritte"].append(dict(schritt="hybrid", ok=True, uebersprungen=True, grund="Eingabe fehlt")); __import__("json_sicher").schreiben(bp, bericht)
    if dran("beweise"): lauf(bericht, "beweise", f"{PY} -I tools/test_nullstart_schritte.py --bericht {bp}" + (" --foto-diff" if os.environ.get("NULLSTART_FD_BEWEIS") == "1" else ""), repo, log, ok_rcs=(0, 1))   # Pflichtliste gegen den Lauf (Schritt ok + Beweisdatei)
    if dran("vergleich"):
        sys.path.insert(0, os.path.join(repo, "tools")); import regression as RG
        R = json.load(open(zobj))["regression"]; basis_ref = os.path.join(od, "regression", "basis"); basis_ziel = os.path.join(zd, "regression", "basis")
        tol = {"stl": 0.05, "wolke_vs_modell": 0.5, **R.get("toleranzen", {})}; tol_std = R.get("toleranz_standard", 0.35)   # SfM-Toleranzen je Datei aus objekt.json['regression']
        tol = {n_: tol.get(n_, tol_std) for n_ in R["dateien"]}
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
        __import__("json_sicher").schreiben(bp, bericht)
        print("\n=== VERGLEICH Nullstart vs Referenz"); [print(f"  {n:18s} {v.get('status'):10s} {json.dumps({k: x for k, x in v.items() if k not in ('status', 'beispiele')}, ensure_ascii=False)[:120]}") for n, v in verg.items()]
        try:                                                                                        # Serienprotokoll: welche Pruefung scheitert in wie vielen Laeufen? (tools/nullstart_serie.py wertet aus)
            sp = os.path.join(od, "nullstart_serie.json"); S_ = json.load(open(sp)) if os.path.exists(sp) else dict(laeufe=[])
            PB = json.load(open(os.path.join(basis_ziel, "pruefbericht.json"))); nz = [n for n, ok in PB["ok"].items() if not ok]; RBz = verg.get("masse", {})
            nw = next((s_ for s_ in bericht["schritte"] if s_.get("schritt", "").startswith("netzwahl")), {})
            S_["laeufe"].append(dict(datum=time.strftime("%Y-%m-%d %H:%M"), mapper=a.mapper, streng=a.streng, stufe=a.stufe, dicht_extra=bericht.get("dicht_extra"), netzwahl=nw.get("gewaehlt"), versuche=nw.get("versuche"),
                bestanden=f"{sum(PB['ok'].values())}/{len(PB['ok'])}", nicht_bestanden=nz, masse_abweichend=sorted(RBz.get("abweichend_ueber_0_3", {})), frisch_abgeleitet=RBz.get("abgeleitet"),
                bleibt_referenz=RBz.get("bleibt_hand"), uebersprungen=[s_["schritt"] for s_ in bericht["schritte"] if s_.get("uebersprungen")]))
            json.dump(S_, open(sp, "w"), indent=1, ensure_ascii=False); print(f"  Serie: Lauf {len(S_['laeufe'])} protokolliert in {os.path.relpath(sp, repo)} (tools/nullstart_serie.py)")
        except Exception as e: print("  Serienprotokoll fehlgeschlagen:", e)
        print(f"  Stufe C (Masse aus Werkzeugausgaben, von Hand in masse.json): {len(hand)} - {hand[:12]}{' ...' if len(hand) > 12 else ''}")

    if dran("stufen") and not a.ohne_stufen:                                                        # Nachtlauf je Gebaeude (Nutzer 2026-11-05): Qualitaetsstufen ohne Handwerte direkt anschliessen
        pq = os.path.join(zd, "qualitaetsstufen.json")
        if not os.path.exists(pq):
            vorlage = os.path.join(repo, "modelle", "PLAN_STANDARD_qualitaetsstufen.json"); shutil.copy(vorlage, pq)
        lauf(bericht, "stufen", f"{PY} -u -I tools/qualitaetsstufen.py {zobj} --plan {pq}", repo, log, ok_rcs=(0,))


if __name__ == "__main__":
    main()

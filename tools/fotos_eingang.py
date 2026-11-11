#!/usr/bin/env python3
"""fotos_eingang.py - AUTOMATISCHER Fotoeingang (11.11., Nutzer: "muss ohne mich gehen"): neue, noch nicht registrierte Fotoordner eines Objekts
finden, gegen die gemeinsame SfM registrieren, pruefen und nur BESTANDENE Kameras als Messkameras K-<nr> anhaengen.

  fotos_eingang.py <objekt> [--trocken] [--ordner PFAD ...]
Konfiguration NUR in modelle/<objekt>/objekt.json, Abschnitt "fotos_eingang" (nichts Objektspezifisches im Code):
  muster       Liste von Globs (Ordner) ODER {"glob":..., "kurz":"n11"} (kurz = Praefix der Messkamera-Nr, sonst aus dem Ordnernamen)
  ausschluss   Teilstrings, die einen Pfad ausschliessen (zusaetzlich immer: Pfadteile, die mit "nicht_" beginnen oder "privat" enthalten)
  bekannt_glob Globs auf vorbereitet.json, deren Quelldateien als schon registriert/versucht gelten (Standard: <zusatz_dir>/*/vorbereitet.json)
  zusatz_dir   Zielordner (je Eingangsordner ein Unterordner, enthaelt eingang_protokoll.json)
  ref_db, ref_sparse, kam_alt, T, rot, kamera_profil, f_px (Prior), bilder_lot2
  max_reproj_px (Std 2,5), zmin/zmax (Std 1,5/6), max_rot (Std 0,25 = Anteil Modellkanten ohne Fotokante im Overlay), gpu_mb (Std 2600)
Ablauf je Ordner: vorbereiten -> merkmale (GPU, SIFT 1600) -> registrieren (feste Kamera je Format/Zoom aus kamera_profil; Zoomklassen nur, wenn
<ordner>/zoom_sicht.json oder zoom_json existiert, sonst 'normal' - ANNAHME) -> zusatz_kameras_lot2 (NEUE Datei kam_lot2_<name>.json) -> je registriertem Bild:
Pruefung Reprojektionsfehler, Kamerahoehe z, Kanten-Overlay (foto_diff rot-Anteil) -> bestanden: K-<nr> (kamera_bruecke) bleibt; sonst K-<nr>.json.abgelehnt
(umbenannt, nie geloescht). Protokoll: <zusatz_dir>/<name>/eingang_protokoll.json + <kreisdir>/<objekt>/eingang_ereignisse.jsonl (Kreis gibt gesperrte Teile frei).
Sperrdatei <zusatz_dir>/.eingang.lock (nie doppelt). Eingang bei Kreis-Regler: tools/job_start.sh mit JOB_GPU_MB."""
import sys, os, json, glob, time, subprocess, argparse, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYC = "/media/oem/scan/venv-colmap/bin/python"; PYS = "/media/oem/scan/venv-seg/bin/python"
BILD = (".jpg", ".jpeg", ".png")


def privat(p):
    return any(t.startswith("nicht_") or "privat" in t.lower() for t in p.split(os.sep))


def ordner_finden(cfg, objdir):
    """Kandidatenordner nach Mustern (relativ zu ROOT erlaubt), ohne Ausschluss/Privates; nur Ordner mit Bildern."""
    out = []
    for m in cfg.get("muster", []):
        g, kurz = (m, None) if isinstance(m, str) else (m["glob"], m.get("kurz"))
        for d in sorted(glob.glob(g if os.path.isabs(g) else os.path.join(ROOT, g))):
            d = os.path.realpath(d)
            if not os.path.isdir(d) or privat(d) or any(x in d for x in cfg.get("ausschluss", [])): continue
            if any(f.lower().endswith(BILD) for f in os.listdir(d)): out.append((d, kurz))
    return out


def bekannte_quellen(cfg, zd):
    """Realpfade + MD5-Kurzsummen aller Quelldateien in vorbereitet.json (schon registriert ODER versucht - Fehlversuche nicht endlos wiederholen)."""
    bek = set()
    for g in cfg.get("bekannt_glob", [os.path.join(zd, "*", "vorbereitet.json")]):
        for p in glob.glob(g):
            try: V = json.load(open(p))["bilder"]
            except Exception: continue
            for v in V.values():
                q = v.get("quelle")
                if q: bek.add(os.path.realpath(q))
    return bek


def lauf(cmd, log, env=None):
    with open(log, "a") as f:
        f.write("\n$ " + " ".join(cmd) + "\n"); f.flush()
        return subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=dict(os.environ, **(env or {}))).returncode


def verarbeiten(cfg, obj, objp, ordner, kurz, a):
    zd = cfg["zusatz_dir"]; name = os.path.basename(ordner.rstrip("/")); Z = os.path.join(zd, name); os.makedirs(Z, exist_ok=True)
    log = os.path.join(Z, "eingang.log"); prot = dict(ordner=ordner, name=name, zeit=time.strftime("%Y-%m-%d %H:%M:%S"), schritte={}, bilder={}, kameras_angehaengt=[])
    def stufe(n, rc):
        prot["schritte"][n] = rc; json.dump(prot, open(os.path.join(Z, "eingang_protokoll.json"), "w"), indent=1, ensure_ascii=False)
        return rc == 0
    ref = dict(db=cfg["ref_db"], sp=cfg["ref_sparse"])
    if not stufe("vorbereiten", lauf([PYC, "-I", "tools/zusatzfotos_registrieren.py", "vorbereiten", "--fotos", ordner, "--aus", Z, "--breite", "0"], log)): return prot
    zj = cfg.get("zoom_json") or (os.path.join(ordner, "zoom_sicht.json") if os.path.exists(os.path.join(ordner, "zoom_sicht.json")) else None)
    if not stufe("merkmale", lauf([PYC, "-I", "tools/zusatzfotos_registrieren.py", "merkmale", "--ref-db", ref["db"], "--sparse", ref["sp"], "--aus", Z, "--f-px", str(cfg.get("f_px", 2790))], log, {"RCPARK_SIFT_MAX": "1600"})): return prot
    cmd = [PYC, "-I", "tools/zusatzfotos_registrieren.py", "registrieren", "--sparse", ref["sp"], "--aus", Z, "--kameras", cfg["kamera_profil"]] + (["--zoom", zj] if zj else [])
    if not stufe("registrieren", lauf(cmd, log)): return prot
    reg = json.load(open(os.path.join(Z, "registrierung.json"))); prot["registriert"] = f"{reg['registriert']}/{reg['von']}"; prot["reproj_mittel_px"] = reg.get("reproj_mittel_px")
    kam_neu = os.path.join(Z, f"kam_lot2_{name}.json"); bl = os.path.join(Z, "bilder_lot2")
    rc = lauf([PYC, "-I", "tools/zusatz_kameras_lot2.py", "--kam", cfg["kam_alt"], "--aus", kam_neu, "--T", cfg["T"], "--rot", cfg["rot"], "--ziel", Z, "--quelle", name,
               "--bilder-aus", bl, "--zmin", str(cfg.get("zmin", 1.5)), "--zmax", str(cfg.get("zmax", 6.0))], log)
    stufe("lot2", rc)
    if not os.path.exists(kam_neu): return prot
    K = json.load(open(kam_neu)); V = json.load(open(os.path.join(Z, "vorbereitet.json")))["bilder"]
    nur_neu = [n for n in K if K[n].get("quelle") == name]; kz = kurz or "".join(c for c in name if c.isalnum())[:6]
    rootg = os.path.join(ROOT, "modelle", obj, "messprotokoll"); od = os.path.join(Z, "overlay"); os.makedirs(od, exist_ok=True)
    for i, n in enumerate(sorted(V), 1):
        nr = f"{kz}_{i:02d}"; b = prot["bilder"].setdefault(n, dict(nr=nr))
        if n not in nur_neu: b["urteil"] = "nicht registriert"; continue
        z = K[n]["C"][2]; rp = K[n].get("reproj_px")
        b.update(reproj_px=rp, kamera_z=round(float(z), 2))
        if rp is not None and rp > cfg.get("max_reproj_px", 2.5): b["urteil"] = f"abgelehnt: Reproj {rp:.2f} px"; continue
        if not (cfg.get("zmin", 1.5) <= z <= cfg.get("zmax", 6.0)): b["urteil"] = f"abgelehnt: Kamerahoehe z {z:.1f} m"; continue
        if lauf([sys.executable, "-I", "tools/kamera_bruecke.py", objp, "--kameras", kam_neu, "--bilder", bl, "--bild", n, "--nr", nr], log) != 0: b["urteil"] = "Fehler kamera_bruecke"; continue
        kf = os.path.join(rootg, f"K-{nr}.json")
        lauf([PYS, "-I", "tools/foto_diff.py", objp, nr, "--gpu", "--aus", od], log, {"FD_GPU": "1"})
        jd = os.path.join(od, f"foto_diff_{nr}.json")
        try: rot = json.load(open(jd))["anteil_modellkanten_ohne_foto"]
        except Exception: rot = None
        b["rot_anteil"] = rot; b["overlay"] = os.path.join(od, f"foto_diff_{nr}.jpg")
        if rot is None or rot > cfg.get("max_rot", 0.25):
            os.rename(kf, kf + ".abgelehnt"); b["urteil"] = f"abgelehnt: Overlay rot-Anteil {rot}"; continue
        b["urteil"] = "bestanden"; prot["kameras_angehaengt"].append(nr); prot.setdefault("bilder_angehaengt", []).append(n)
    stufe("pruefung", 0)
    if prot["kameras_angehaengt"]:
        ev = os.path.join(a.kreisdir, obj); os.makedirs(ev, exist_ok=True)
        with open(os.path.join(ev, "eingang_ereignisse.jsonl"), "a") as f:
            f.write(json.dumps(dict(zeit=time.strftime("%Y-%m-%dT%H:%M:%S"), ordner=ordner, kamerafile=kam_neu, kameras=prot["kameras_angehaengt"], bilder=prot["bilder_angehaengt"])) + "\n")
    return prot


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("objekt"); ap.add_argument("--trocken", action="store_true"); ap.add_argument("--ordner", nargs="*", help="Ordner explizit (statt Muster)")
    ap.add_argument("--kreisdir", default="/media/oem/scan/rc-park_kreis"); ap.add_argument("--konfig", help="Abschnitt fotos_eingang aus dieser JSON (Test)")
    a = ap.parse_args(argv)
    objp = os.path.join("modelle", a.objekt, "objekt.json"); ojs = json.load(open(os.path.join(ROOT, objp)))
    cfg = json.load(open(a.konfig)) if a.konfig else ojs.get("fotos_eingang")
    if not cfg: print(f"{a.objekt}: kein Abschnitt fotos_eingang in objekt.json"); return 0
    zd = cfg["zusatz_dir"]; os.makedirs(zd, exist_ok=True); bek = bekannte_quellen(cfg, zd)
    kand = [(os.path.realpath(o), None) for o in a.ordner] if a.ordner else ordner_finden(cfg, objp)
    neu = []
    for d, kurz in kand:
        if privat(d): continue
        bilder = [os.path.realpath(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.lower().endswith(BILD)]
        if any(b not in bek for b in bilder): neu.append((d, kurz))
    print(f"{a.objekt}: {len(kand)} Kandidatenordner, {len(neu)} mit neuen Fotos: {[os.path.basename(d) for d, _ in neu]}")
    if a.trocken or not neu: return 0
    lock = os.path.join(zd, ".eingang.lock")
    try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, str(os.getpid()).encode()); os.close(fd)
    except FileExistsError:
        try: os.kill(int(open(lock).read().strip() or 0), 0); print("Eingang laeuft schon (Sperrdatei)"); return 1
        except (ProcessLookupError, ValueError):
            os.remove(lock); fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, str(os.getpid()).encode()); os.close(fd)   # Sperre eines toten Prozesses
        except PermissionError: print("Eingang laeuft schon"); return 1
    ges = []
    try:
        for d, kurz in neu: ges.append(verarbeiten(cfg, a.objekt, objp, d, kurz, a))
    finally:
        try: os.remove(lock)
        except OSError: pass
    p = os.path.join(zd, f"eingang_lauf_{time.strftime('%Y%m%d_%H%M%S')}.json"); json.dump(ges, open(p, "w"), indent=1, ensure_ascii=False)
    for g in ges: print(g["name"], g.get("registriert"), "angehaengt:", g["kameras_angehaengt"])
    return 0


if __name__ == "__main__": sys.exit(main())

#!/usr/bin/env python3
"""llm_urteil_paare.py - BLIND-Paarbilder aus foto_diff-Overlays fuer einen LLM-Plausibilitaetspruefer (7.11., Nutzerwunsch). NICHT der Diff: kosten_lr bleibt das Mass;
der Beurteiler ist eine zweite, unabhaengige Sicht. Keine Netznamen im Bild, links/rechts zufaellig (ausgewogen), Schluessel separat (_schluessel/<lauf>.json), nie an Beurteiler geben.
  paare    --a DIR --b DIR --fotos 004,059 --lauf NAME [--region-box x0,y0,x1,y1 (Bruchteile 0-1 des Bildes, sonst Gebaeudemaske-Bbox)]
           DIR enthaelt <nr>/foto_diff_<nr>.jpg (+ .json); schreibt <ROOT>/<lauf>/{bilder,key.json,aufgaben.json}
  eichsatz --lauf NAME  : Eichsatz ~20 Paare mit bekanntem Ausgang (Netz default/fein, Kamera 0,5/1 Grad, Nullkontrolle) - rechnet fehlende Kameraverschiebungs-Laeufe selbst (foto_diff Raster)
Quelle der Eichsatz-Netzpaare: wettbewerb_kh23_raster (Register BS7, Raster, Maske C kh9g). Kameraverschiebung = Schwenk der K-Datei (Rodrigues) in einem Scratch-Objekt, Original unberuehrt."""
import sys, os, json, glob, random, subprocess, shutil, argparse, numpy as np, cv2
ROOT = "/media/oem/scan/rc-park_null/llm_urteil"; NULL = "/media/oem/scan/rc-park_null"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJ = os.path.join(REPO, "modelle/kaufhaus_null5/objekt.json"); MASKEN = NULL + "/wettbewerb_kh9g/masken"
KH23 = NULL + "/wettbewerb_kh23_raster/p2"; BREITE = 790
FRAGE = ("Links und rechts ist dasselbe Foto mit den Kanten eines 3D-Modells. Gruen = Modellkante passt zu einer Fotokante, ROT = Modellkante ohne Fotokante (falsch/erfunden), "
         "GELB = Fotokante fehlt im Modell. Weniger rot/gelb und mehr gruen ist besser. Welche Seite passt besser? Antworte links/rechts/gleich + 1 Satz Grund.")

def _jpg(d, nr):
    for p in (os.path.join(d, nr, f"foto_diff_{nr}.jpg"), os.path.join(d, f"foto_diff_{nr}.jpg")):
        if os.path.exists(p): return p
    raise FileNotFoundError(f"{d}/{nr}")

def lr_von(d, nr):
    for p in (os.path.join(d, nr, f"foto_diff_{nr}.json"), os.path.join(d, f"foto_diff_{nr}.json")):
        if os.path.exists(p): return json.load(open(p)).get("kosten_lr")

def _box(nr, shape, region):
    H, W = shape[:2]
    if region: x0, y0, x1, y1 = [float(v) for v in region.split(",")]; return int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)
    m = cv2.imread(os.path.join(MASKEN, f"C_{nr}.png"), 0)
    if m is None or not (m > 0).any(): return 0, 0, W, H
    ys, xs = np.nonzero(m > 0); r = int(0.02 * W); return max(0, xs.min() - r), max(0, ys.min() - r), min(W, xs.max() + r), min(H, ys.max() + r)

def paarbild(ja, jb, nr, region, links_a, aus):
    A, B = cv2.imread(ja), cv2.imread(jb); x0, y0, x1, y1 = _box(nr, A.shape, region)
    s = BREITE / (x1 - x0); sz = (BREITE, max(1, int((y1 - y0) * s)))
    A, B = [cv2.resize(i[y0:y1, x0:x1], sz, interpolation=cv2.INTER_AREA) for i in (A, B)]
    L, R = (A, B) if links_a else (B, A); bild = np.hstack([L, np.full((sz[1], 20, 3), 128, np.uint8), R])
    cv2.imwrite(aus, bild, [cv2.IMWRITE_JPEG_QUALITY, 82]); return bild.shape[1], bild.shape[0]

def bauen(lauf, spec, region=None, seed=7):
    """spec: Liste dict(kat, nr, a_jpg, b_jpg, a, b, erwartung, lr_a, lr_b). Seiten ausgewogen zufaellig; Paar-IDs zufaellig gemischt (kein Rueckschluss aus der Nummer)."""
    out = os.path.join(ROOT, lauf); os.makedirs(out + "/bilder", exist_ok=True); rng = random.Random(seed)
    seiten = [True, False] * (len(spec) // 2 + 1); rng.shuffle(seiten); ids = list(range(1, len(spec) + 1)); rng.shuffle(ids)
    key, aufg = {}, []
    for s, la, pid in zip(spec, seiten, ids):
        pid = f"P{pid:02d}"; png = os.path.join(out, "bilder", pid + ".jpg"); w, h = paarbild(s["a_jpg"], s["b_jpg"], s["nr"], s.get("region", region), la, png)
        key[pid] = dict(links="A" if la else "B", **{k: v for k, v in s.items() if k not in ("a_jpg", "b_jpg")}, a_jpg=s["a_jpg"], b_jpg=s["b_jpg"], px=[w, h])
        aufg.append(dict(id=pid, bild=png, frage=FRAGE, antwort_datei_muster="urteile/<beurteiler>/%s.json" % pid, antwort_format='{"urteil":"links|rechts|gleich","grund":"1 Satz"}'))
    aufg.sort(key=lambda a: a["id"])
    os.makedirs(ROOT + "/_schluessel", exist_ok=True); json.dump(key, open(f"{ROOT}/_schluessel/{lauf}.json", "w"), indent=1); json.dump(aufg, open(out + "/aufgaben.json", "w"), indent=1)
    print(f"{len(aufg)} Paare -> {out}/aufgaben.json (Schluessel {ROOT}/_schluessel/{lauf}.json NICHT weitergeben)"); return out

def kamera_lauf(grad, vorz, nrs, netz="mvs_default", netz_pfad=NULL + "/wettbewerb_kh/netze4/mvs_default.stl"):
    """foto_diff mit um grad (Schwenk um die Kamera-y-Achse, Vorzeichen vorz) verschobener Kamera; Ergebnis <ROOT>/_kam/<netz>_<grad>_<vz>/<nr>/. Original: Objektordner unveraendert."""
    tag = f"{netz}_{grad:g}_{'p' if vorz > 0 else 'm'}"; base = os.path.join(ROOT, "_kam", tag)
    sroot = os.path.join(base, "root"); od = os.path.join(sroot, "modelle", "kam"); os.makedirs(os.path.join(od, "messprotokoll"), exist_ok=True)
    for src, dst in ((REPO + "/daten", sroot + "/daten"), (REPO + "/modelle/kaufhaus_null5", sroot + "/modelle/kaufhaus_null5"), (REPO + "/modelle/kaufhaus_null5/sfm", od + "/sfm"), (REPO + "/modelle/kaufhaus_null5/himmelsmaske", od + "/himmelsmaske")):
        if not os.path.lexists(dst): os.symlink(os.path.realpath(src), dst)
    shutil.copy(OBJ, od + "/objekt.json")
    for nr in nrs:
        k = json.load(open(REPO + f"/modelle/kaufhaus_null5/messprotokoll/K-{nr}.json")); R, _ = cv2.Rodrigues(np.array(k["kamera"]["rvec"], float))
        d = np.radians(grad * vorz); Rd = np.array([[np.cos(d), 0, np.sin(d)], [0, 1, 0], [-np.sin(d), 0, np.cos(d)]])
        k["kamera"]["rvec"] = cv2.Rodrigues(Rd @ R)[0].ravel().tolist(); json.dump(k, open(f"{od}/messprotokoll/K-{nr}.json", "w"))
        o = os.path.join(base, nr)
        if glob.glob(o + "/foto_diff_*.json"): continue
        r = subprocess.run(["taskset", "-c", "0-3", "/media/oem/scan/venv-seg/bin/python", "-W", "ignore", "-I", REPO + "/tools/foto_diff.py", od + "/objekt.json", nr, "--stl", netz_pfad, "--aus", o,
                            "--bewertung-maske", f"{MASKEN}/C_{nr}.png"], capture_output=True, text=True, env=dict(os.environ, FD_RASTER="1", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True", OMP_NUM_THREADS="4"), cwd=REPO)
        if not glob.glob(o + "/foto_diff_*.json"): print("FEHLER", tag, nr, r.stderr[-300:])
    return base

def eichsatz(lauf):
    sp = []; D, F = KH23 + "/mvs_default", KH23 + "/mvs_fein"
    # Gruppe N: Netz, Diff entscheidet klar (kosten_lr kleiner = besser; default klar besser als fein, Differenz >= 0,04)
    for nr in ("004", "059", "043", "022", "065", "054"):
        sp.append(dict(kat="netz", nr=nr, a_jpg=_jpg(D, nr), b_jpg=_jpg(F, nr), a="mvs_default", b="mvs_fein", erwartung="A", lr_a=lr_von(D, nr), lr_b=lr_von(F, nr)))
    # Gruppe K: Kamera um 0,5 / 1,0 Grad geschwenkt (Original gegen verschoben, gleiches Netz mvs_default); Original muss besser sein
    plan = [("004", 1.0, 1), ("059", 1.0, -1), ("043", 1.0, 1), ("032", 1.0, -1), ("054", 1.0, -1), ("022", 1.0, 1), ("016", 0.5, 1), ("026", 0.5, -1), ("000", 0.5, 1), ("065", 0.5, -1)]
    for nr, g, vz in plan:
        base = kamera_lauf(g, vz, [nr]); o = os.path.join(base, nr)
        if not glob.glob(o + "/foto_diff_*.json"): continue
        if lr_von(base, nr) - lr_von(D, nr) < 0.01: print("ausgelassen (Diff entscheidet nicht klar, Delta kosten_lr < 0,01):", nr, g, vz); continue
        sp.append(dict(kat=f"kamera_{g:g}", nr=nr, a_jpg=_jpg(D, nr), b_jpg=_jpg(base, nr), a="original", b=f"schwenk_{g:g}_{vz:+d}", erwartung="A", lr_a=lr_von(D, nr), lr_b=lr_von(base, nr)))
    # Gruppe 0: Nullkontrolle: 3 identische Bilder (A gegen A; Raster hat keinen Zufall -> identisch) + 3 fast gleiche Netze (|delta lr| < 0,004: default gegen saeule_median)
    for nr in ("010", "000", "082"):
        sp.append(dict(kat="null_identisch", nr=nr, a_jpg=_jpg(D, nr), b_jpg=_jpg(D, nr), a="mvs_default", b="mvs_default", erwartung="gleich", lr_a=lr_von(D, nr), lr_b=lr_von(D, nr)))
    S = KH23 + "/saeule_median"
    for nr in ("010", "049", "114"):
        la, lb = lr_von(D, nr), lr_von(S, nr)
        sp.append(dict(kat="null_nahgleich", nr=nr, a_jpg=_jpg(D, nr), b_jpg=_jpg(S, nr), a="mvs_default", b="saeule_median", erwartung="gleich", lr_a=la, lr_b=lb))
    return bauen(lauf, sp)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("paare"); p.add_argument("--a", required=True); p.add_argument("--b", required=True); p.add_argument("--fotos", required=True); p.add_argument("--lauf", required=True); p.add_argument("--region-box")
    e = sub.add_parser("eichsatz"); e.add_argument("--lauf", required=True); a = ap.parse_args()
    if a.cmd == "eichsatz": eichsatz(a.lauf)
    else:
        sp = []
        for nr in a.fotos.split(","):
            la, lb = lr_von(a.a, nr), lr_von(a.b, nr); sp.append(dict(kat="frei", nr=nr, a_jpg=_jpg(a.a, nr), b_jpg=_jpg(a.b, nr), a=a.a, b=a.b, erwartung=("A" if la is not None and lb is not None and la < lb else "B") if la != lb else "gleich", lr_a=la, lr_b=lb))
        bauen(a.lauf, sp, a.region_box)

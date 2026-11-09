#!/usr/bin/env python3
"""test_teile_sichtpruefung.py - BEWEIS, dass tools/teile_sichtpruefung.py die Fehler der Runde 5 (Kaufhaus) automatisch findet.

 T1 SYNTHETISCH (Kalibrierung der Schwellen, NICHT am Kaufhaus-Ergebnis): Wahrheit = die Bauteil-Netze des Runde-5-Standes, 'Fotos' = deren eigene Kantenbilder
    + Zufallskanten (Dichte wie ein echtes Fassadenfoto), Himmel/Wolke aus der Wahrheit. Je Bauteil Varianten: korrekt (MUSS GRUEN), 1 m seitlich, 1 m hoch,
    20 % zu gross, halbe Breite (Kegel statt Glocke) (MUESSEN ROT). Mehrere Kameras, je Variante dieselbe Urteilsregel wie im Werkzeug.
 T2 ECHT: Runde-5-Stand (git 928c312, Scratch-Kopie) mit den echten Fotos; erwartet ROT: Westumriss, beide Erker, EG-Fenster Bogen 3, beide Helme, Ganzmodell;
    erwartet GRUEN: mindestens eines von Konsolenreihe/Bruestung/Fensterreihe og (nachweislich passend).
Ergebnis als Tabelle; Rueckgabecode != 0, wenn eine Erwartung verletzt ist.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_teile_sichtpruefung.py [--nur synth|echt] [--scratch DIR]"""
import os, sys, json, subprocess, argparse, time, math, numpy as np, cv2, trimesh
TOOLS = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import teile_sichtpruefung as TS

DATEN = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; COMMIT = "928c312"
ERWARTET_ROT = {"staffelgiebel:west": "Westumriss (ragt ueber das Nachbarhaus)", "erker:0": "Erker links", "erker:1": "Erker rechts", "fensterreihe:eg1": "EG-Fenster Bogen 3 (sitzt daneben)",
                "zylinder:helm_w": "Erkerhelm links (schmaler Kegel statt Glocke)", "zylinder:helm_o": "Erkerhelm rechts", "GANZ": "Gesamtmodell (ragt in fremde Flaeche)"}
KANDIDATEN_GRUEN = ["konsolenreihe:balkon", "bruestung:balkon", "fensterreihe:og", "fensterreihe:eg1_tuer"]

def scratch_bauen(sc):
    r5 = os.path.join(sc, "r5")
    if not os.path.exists(os.path.join(r5, "tools", "baukasten_gen.py")):
        os.makedirs(r5, exist_ok=True)
        p = subprocess.run(f"cd {REPO} && git archive {COMMIT} tools modelle/kaufhaus_grob3 | tar -x -C {r5}", shell=True); assert p.returncode == 0
    stl = os.path.join(sc, "r5_ganz.stl")
    if not os.path.exists(stl): open(stl, "wb").write(subprocess.check_output(["git", "show", f"{COMMIT}:modelle/stl/kaufhaus_grob3_1-87.stl"], cwd=REPO))
    return r5, stl

def echt(sc, fotos=6):
    r5, stl = scratch_bauen(sc); out = os.path.join(sc, "r5_out")
    cmd = [sys.executable, "-W", "ignore", "-I", os.path.join(TOOLS, "teile_sichtpruefung.py"), "kaufhaus_grob3", "--root", r5, "--stl", stl, "--kameras", f"{DATEN}/sfm/kam_lot2.json", "--bilder", f"{DATEN}/bilder",
           "--stabil", f"{DATEN}/stabil", "--wolke", f"{DATEN}/kanten3d_k80.npz", "--pflicht", "ip_IMG_6120.jpg,ip_IMG_6261.jpg", "--fotos", str(fotos), "--out", out]
    p = subprocess.run(cmd, capture_output=True, text=True); print(p.stdout[-600:]); d = json.load(open(os.path.join(out, "teile_sicht.json"))); return d, p.returncode

def tabelle_echt(d):
    U = {e["typ"]: e for e in d["teile"]}; ok = True; zeilen = []
    for t, was in ERWARTET_ROT.items():
        e = U.get(t); u = e["urteil"] if e else "FEHLT"; zeilen.append((t, "ROT", u, was, e["grund"][:110] if e else "")); ok &= (u == "ROT")
    gr = [t for t in KANDIDATEN_GRUEN if U.get(t, {}).get("urteil") == "GRUEN"]
    for t in KANDIDATEN_GRUEN:
        e = U.get(t); u = e["urteil"] if e else "FEHLT"; zeilen.append((t, "GRUEN (mind. 1)", u, "passt nachweislich", e["grund"][:110] if e else ""))
    ok &= len(gr) >= 1
    print("\n%-22s %-16s %-11s %s" % ("Bauteil", "erwartet", "Urteil", "Bedeutung | Grund"))
    for t, er, u, was, g in zeilen: print("%-22s %-16s %-11s %s | %s" % (t, er, u, was, g))
    return ok

def formen_test(sc):
    """T3 Zweiter Einsatzort: Formfit-Ergebnisse der Kantenkette (helm_fit -> formen/helme.json ROT, saeulen_fit -> kette_foto/g3_formen.json R 0,437 GRUEN)."""
    ok = True; res = {}
    for tag, f, ad in (("helme", f"{DATEN}/formen/helme.json", "helme"), ("saeulen", f"{DATEN}/kette_foto/g3_formen.json", "saeulen")):
        out = os.path.join(sc, "formen_" + tag)
        cmd = [sys.executable, "-W", "ignore", "-I", os.path.join(TOOLS, "teile_sichtpruefung.py"), "kaufhaus_grob3", "--formen", f, "--adapter", ad, "--kameras", f"{DATEN}/sfm/kam_lot2.json", "--bilder", f"{DATEN}/bilder",
               "--stabil", f"{DATEN}/stabil", "--wolke", f"{DATEN}/kanten3d_k80.npz", "--pflicht", "ip_IMG_6120.jpg,ip_IMG_6261.jpg", "--fotos", "6", "--min-fotos", "3", "--out", out]
        p = subprocess.run(cmd, capture_output=True, text=True); res[tag] = json.load(open(os.path.join(out, "teile_sicht.json")))
    print("\n%-12s %-9s %-11s %s" % ("Formteil", "erwartet", "Urteil", "Werte | Grund"))
    for e in res["helme"]["teile"]:
        if e["typ"] == "GANZ": continue
        print("%-12s %-9s %-11s %s" % (e["typ"], "ROT", e["urteil"], e["grund"][:120])); ok &= e["urteil"] == "ROT"
    sa = [e for e in res["saeulen"]["teile"] if e["typ"].startswith("saeule")]; R = json.load(open(f"{DATEN}/kette_foto/g3_formen.json"))["saeulen"]; gr = 0
    for e in sa:
        i = int(e["typ"].split("_")[1]); r = R[i]["R"]; erw = "GRUEN" if abs(r - 0.437) < 0.01 else "(frei)"
        print("%-12s %-9s %-11s R %.3f | %s" % (e["typ"], erw, e["urteil"], r, e["grund"][:100]))
        if erw == "GRUEN": gr += e["urteil"] == "GRUEN"; ok &= e["urteil"] in ("GRUEN",)
    ok &= gr >= 1; return ok

# ------------------------------------------------------------------ Synthetik
def zufallskanten(shape, dichte, rng):
    m = np.zeros(shape, np.uint8); H, W = shape
    while (m > 0).mean() < dichte:
        x, y = int(rng.integers(0, W)), int(rng.integers(0, H)); a = rng.uniform(0, 2 * math.pi) if rng.random() < 0.3 else (0 if rng.random() < 0.5 else math.pi / 2); L = int(rng.integers(8, 40))
        cv2.line(m, (x, y), (int(x + L * math.cos(a)), int(y + L * math.sin(a))), 1, 1)
    return m.astype(bool)

def variante(m, art, achse_u=np.array([0.9423, -0.3347, 0.0])):
    v = m.copy(); c = m.centroid.copy()
    if art == "korrekt": return v
    if art == "seitlich_1m": v.apply_translation(achse_u * 1.0)
    elif art == "hoch_1m": v.apply_translation([0, 0, 1.0])
    elif art == "gross_20": v.apply_translation(-c); v.apply_scale(1.2); v.apply_translation(c)
    elif art == "halbe_breite":                                                                       # nur horizontal um die senkrechte Achse durch den Schwerpunkt verengen (Kegel statt Glocke)
        V = np.asarray(v.vertices).copy(); V[:, :2] = c[:2] + (V[:, :2] - c[:2]) * 0.5; v = trimesh.Trimesh(V, v.faces, process=False)
    return v

ARTEN_ROT = ["seitlich_1m", "hoch_1m", "gross_20", "halbe_breite"]

def synth(out, sw, fotos=6, teile=("erker:0", "zylinder:helm_w", "staffelgiebel:west", "bogenreihe:laube", "fensterreihe:og", "konsolenreihe:balkon", "quader:rumpf_og", "satteldach:haupt"), verbose=True):
    """Rueckgabe ok, Zeilen. Teile aus out/teile_stl (vom echten Lauf), Kameras: die im echten Lauf je Teil gewaehlten."""
    kam = json.load(open(f"{DATEN}/sfm/kam_lot2.json")); d = json.load(open(os.path.join(out, "teile_sicht.json"))); mass = 87.0; rng = np.random.default_rng(1)
    stl = {}
    for f in sorted(os.listdir(os.path.join(out, "teile_stl"))):
        if not f.endswith(".stl"): continue
        stl[f[3:-4]] = os.path.join(out, "teile_stl", f)
    namen = {e["typ"]: e for e in d["teile"]}; M = {}
    for t, e in namen.items():
        key = t.replace(":", "_").replace("/", "_")
        if key in stl and e["dreiecke"] > 3: M[t] = TS.stl_m(stl[key], mass)
    zeilen = []; ok = True; wahr_cache = {}
    for t in teile:
        if t not in M: continue
        cams = [f["foto"] for f in namen[t]["fotos"] if f["auswertbar"]][:fotos]
        for variantenname in ["korrekt"] + ARTEN_ROT:
            mess = []
            for n in cams:
                kc = TS.kamera_skaliert(kam[n]); shape = (kc["H"], kc["W"])
                if n not in wahr_cache:
                    allm = trimesh.util.concatenate(list(M.values())); Dw, Ew = TS.ganz_raster(allm, kc); fin = np.isfinite(Dw)
                    cover = cv2.dilate(fin.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
                    FK = cv2.dilate(Ew.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) | zufallskanten(shape, 0.05, rng)
                    wahr_cache[n] = (FK, ~cover, np.where(fin, Dw, np.inf).astype(np.float32), kc)
                FK, sky, cz, kc = wahr_cache[n]
                andere = [m for k, m in M.items() if k != t]; test = trimesh.util.concatenate(andere + [variante(M[t], variantenname)]); Dg, Eg = TS.ganz_raster(test, kc)
                A = TS.Ansicht(n, kc["R"], kc["t"], kc["f"], kc["cx"], kc["cy"], kc["W"], kc["H"], Dg, FK, sky, cz, None, Eg)
                r = TS.teil_messen(variante(M[t], variantenname), A, kc, sw); mess.append((n, r))
            u, g = TS.teil_urteil(mess, sw); erwartet = "GRUEN" if variantenname == "korrekt" else "ROT"
            if u == "UNGEPRUEFT": ok_ = None
            else: ok_ = (u == erwartet)
            ok &= bool(ok_)
            ausw = [r for _, r in mess if r["auswertbar"]]
            def mw(k): v = [r[k] for r in ausw if r.get(k) is not None]; return round(float(np.mean(v)), 2) if v else None
            zeilen.append((t, variantenname, erwartet, u, len(ausw), mw("hit"), mw("gewinn"), mw("himmel"), mw("wolke"), mw("recall"), mw("sil_recall"), g[:70]))
            if verbose: print("%-22s %-13s erw %-5s %-10s n=%d hit %s gew %s himm %s wolke %s rec %s sil %s | %s" % zeilen[-1], flush=True)
    return ok, zeilen

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--nur", choices=["synth", "echt", "formen"]); ap.add_argument("--scratch", default=os.path.join(os.environ.get("TMPDIR", "/tmp"), "teile_sicht_test"))
    ap.add_argument("--vorhandenen-lauf", help="Ergebnisordner eines schon gelaufenen echten Laufs verwenden"); a = ap.parse_args(); os.makedirs(a.scratch, exist_ok=True); t0 = time.time(); ok = True
    if a.nur == "formen": d, rc = None, 0
    elif a.vorhandenen_lauf: d, rc = json.load(open(os.path.join(a.vorhandenen_lauf, "teile_sicht.json"))), 1; out = a.vorhandenen_lauf
    else: d, rc = echt(a.scratch); out = os.path.join(a.scratch, "r5_out")
    if a.nur in (None, "echt"): ok &= tabelle_echt(d)
    if a.nur in (None, "formen"): ok &= formen_test(a.scratch)
    if a.nur in (None, "synth"):
        print("\nSYNTHETISCH (Schwellen aus teile_sichtpruefung.SCHWELLEN)"); o2, z = synth(out, dict(TS.SCHWELLEN)); ok &= o2
    print("\nTEST teile_sichtpruefung:", "BESTANDEN" if ok else "FEHLGESCHLAGEN", f"({time.time() - t0:.0f} s)"); sys.exit(0 if ok else 1)

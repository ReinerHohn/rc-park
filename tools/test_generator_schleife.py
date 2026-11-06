#!/usr/bin/env python3
"""test_generator_schleife.py - BEWEIS (bekannte Wahrheit, OHNE echte Fotos) fuer generator_schleife.py (2026-11-06).

Synthetisches Objekt 'haus' (Quader + Satteldach + Anbau + Schornstein) mit einem Mini-Generator, der wie baukasten_gen BAUTEIL_PARAM/STL_NAME/ELEMENTE_AUS liest.
6 kalibrierte Kameras rund um das Haus; Pruefbilder = Render der WAHRHEIT (test_foto_diff.foto_rendern, Rauschen). Der Startvektor ist absichtlich falsch.
  T1 Wahrheit zurueck: |gefunden - Wahrheit| <= --tol je freiem Parameter; angenommene J faellt monoton; ein FEST-Override (Handeingriff, falsch gesetzt) bleibt
     in JEDEM ausgewerteten Vektor unveraendert; --uebernehmen schreibt Werte + quelle + historie in das (synthetische) objekt.json.
  T2 Gegenprobe gestoerte Fotos (Bilder den falschen Kameras zugeordnet): das Tor nimmt NICHTS an (J_ende == J_start, kein Parameter bewegt).
  T3 sperren: gesperrter Parameter wird nicht optimiert und bleibt unveraendert.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_generator_schleife.py [--tol 0.2] [--minuten 25] [--nur T1,T2,T3]
"""
import sys, os, json, argparse, subprocess, datetime, shutil, numpy as np, cv2
os.environ["CUDA_VISIBLE_DEVICES"] = ""; os.environ["PRUEF_CPU"] = "1"
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
import param_suche as PS

MINI = r'''
import os, sys, json, numpy as np, trimesh
bp = json.loads(os.environ.get("BAUTEIL_PARAM", "{}")).get("haus", {})
g = lambda k, d: float(bp.get(k, d))
wh, fh, ab, sh = g("wand_h", 6.0), g("first_h", 3.0), g("anbau_b", 2.0), g("schornstein_h", 0.5)
teile = [trimesh.creation.box(extents=(12, 8, wh), transform=trimesh.transformations.translation_matrix((0, 0, wh / 2)))]
V = np.array([[-6, -4, wh], [6, -4, wh], [6, 4, wh], [-6, 4, wh], [-6, 0, wh + fh], [6, 0, wh + fh]], float)
F = [[0, 1, 5], [0, 5, 4], [3, 5, 2], [3, 4, 5], [0, 4, 3], [1, 2, 5]]
teile.append(trimesh.Trimesh(V, F, process=False))
teile.append(trimesh.creation.box(extents=(ab, 5, 3.0), transform=trimesh.transformations.translation_matrix((6 + ab / 2, 0, 1.5))))
teile.append(trimesh.creation.box(extents=(0.8, 0.8, sh), transform=trimesh.transformations.translation_matrix((-3, 0, wh + fh * 0.5 + sh / 2))))
m = trimesh.util.concatenate(teile)
os.makedirs(os.path.join("modelle", "stl"), exist_ok=True); m.export(os.path.join("modelle", "stl", os.environ["STL_NAME"]))
json.dump([], open(os.environ.get("ELEMENTE_AUS", "/dev/null"), "w"))
'''
WAHR = dict(wand_h=7.0, first_h=4.2, anbau_b=3.0, schornstein_h=1.5)
START = dict(wand_h=6.2, first_h=3.4, anbau_b=2.0)
FEST = dict(schornstein_h=0.5)                                                                  # absichtlich FALSCH (Wahrheit 1,5), Handeingriff -> darf nie geaendert werden
RAUM = {"haus": {"wand_h": dict(lo=5.0, hi=9.0, schritt=0.05), "first_h": dict(lo=2.5, hi=6.0, schritt=0.05), "anbau_b": dict(lo=1.0, hi=5.0, schritt=0.05), "schornstein_h": dict(lo=0.0, hi=3.0, schritt=0.05)}}


def aufbauen(base):
    import trimesh
    od = os.path.join(base, "modelle", "haus"); os.makedirs(os.path.join(od, "messprotokoll"), exist_ok=True); os.makedirs(os.path.join(base, "fotos"), exist_ok=True)
    open(os.path.join(od, "mini_gen.py"), "w").write(MINI)
    obj = dict(name="haus", generator=f"{PS.PY} {os.path.join(od, 'mini_gen.py')}", stl="modelle/stl/haus.stl", stl_massstab=1000, zentrierung="achse", masstabelle="modelle/haus/masstabelle.json", fotos_dir="fotos",
               audit="modelle/haus/audit", bauteile=[dict(typ="haus", **START, schornstein_h=0.5, quelle="Test: absichtlich falscher Start")], overrides={"haus": {"schornstein_h": 0.5, "fest": True, "quelle": "Handeingriff Test (falsch gesetzt)"}})
    json.dump(obj, open(os.path.join(od, "objekt.json"), "w"), indent=1); json.dump({}, open(os.path.join(od, "masstabelle.json"), "w"))
    json.dump(RAUM, open(os.path.join(od, "parameter_raum.json"), "w"), indent=1)
    W, H, f = 1000, 640, 900.0; cams = []
    for i in range(6):
        az = np.deg2rad(30 + 60 * i); cam = np.array([40 * np.sin(az), -40 * np.cos(az), 12.0 + 4.0 * (i % 2)]); tgt = np.array([0, 0, 4.0]); fw = tgt - cam; fw /= np.linalg.norm(fw)
        x = np.cross(fw, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(fw, x); R = np.vstack([x, y, fw]); t = -R @ cam; rv, _ = cv2.Rodrigues(R)
        nr = f"{i:03d}"; cams.append(nr)
        json.dump(dict(foto=nr, kamera=dict(rvec=rv.ravel().tolist(), t=t.tolist(), f_px=f, cx=W / 2, cy=H / 2, k1=0.0, bild=[W, H], rahmen_verschiebung=[0.0, 0.0, 0.0], ankerzone_z=[-5.0, 40.0],
                  brennweite_quelle="buendel", buendel_tor=dict(ok=True))), open(os.path.join(od, "messprotokoll", f"K-{nr}.json"), "w"))
    return od, obj, cams


def wahrheit_bilder(base, od, obj, cams, ziel_dir):
    """Pruefbilder der WAHRHEIT je Kamera (Mini-Generator mit WAHR -> STL -> Render)."""
    import test_foto_diff as TF, fehlteile_finden as FF, trimesh
    env = dict(os.environ, BAUTEIL_PARAM=json.dumps({"haus": WAHR}), STL_NAME="_wahr_haus.stl", ELEMENTE_AUS="/dev/null")
    r = subprocess.run(["bash", "-c", obj["generator"]], cwd=ROOT, env=env, capture_output=True, text=True)
    stl = os.path.join(ROOT, "modelle", "stl", "_wahr_haus.stl")
    if r.returncode != 0 or not os.path.exists(stl): raise SystemExit("Wahrheit nicht gebaut: " + (r.stderr or r.stdout)[-500:])
    os.makedirs(ziel_dir, exist_ok=True); objp = os.path.join(od, "objekt.json")
    for nr in cams:
        K = json.load(open(os.path.join(od, "messprotokoll", f"K-{nr}.json"))); kk = K["kamera"]; W, H = kk["bild"]
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, base, W, H); m, _ = TF.modell(obj, stl, kk)
        cv2.imwrite(os.path.join(ziel_dir, f"{nr}_synth.jpg"), TF.foto_rendern(m, R, t, f, W / 2, H / 2, W, H, np.random.default_rng(int(nr) + 1)), [cv2.IMWRITE_JPEG_QUALITY, 95])
    os.remove(stl)


def lauf(od, aus, minuten, extra=()):
    cmd = [PS.PY, "-W", "ignore", "-I", os.path.join(TOOLS, "generator_schleife.py"), os.path.join(od, "objekt.json"), "--aus", aus, "--minuten", str(minuten), "--fd=--tiefen aus", "--starts", "2", "--geduld", "3"] + list(extra)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True); open(aus + ".log", "w").write(r.stdout + r.stderr); print(r.stdout[-1800:])
    if r.returncode != 0: print("STDERR:", r.stderr[-1500:])
    return json.load(open(os.path.join(aus, "ergebnis.json"))) if os.path.exists(os.path.join(aus, "ergebnis.json")) else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tol", type=float, default=0.2); ap.add_argument("--minuten", type=float, default=25); ap.add_argument("--nur", default="T1,T2,T3"); ap.add_argument("--arbeit"); a = ap.parse_args()
    base = a.arbeit or os.path.join("/media/oem/scan/rc-park_null", f"test_gschleife_{datetime.datetime.now():%Y%m%d_%H%M%S}"); os.makedirs(base, exist_ok=True)
    od, obj, cams = aufbauen(base); wahr_dir = os.path.join(base, "wahr_bilder")
    if not os.path.exists(os.path.join(wahr_dir, "000_synth.jpg")): wahrheit_bilder(base, od, obj, cams, wahr_dir)
    res = {}; nur = a.nur.split(",")
    def fotos_setzen(modus):
        d = os.path.join(base, "fotos"); [os.remove(os.path.join(d, x)) for x in os.listdir(d)]
        for i, nr in enumerate(cams):
            src = nr if modus == "wahr" else cams[(i + 2) % 6]                                  # gestoert: Bild der Kamera i+2 an Kamera i
            shutil.copy(os.path.join(wahr_dir, f"{src}_synth.jpg"), os.path.join(d, f"{nr}_synth.jpg"))
    if "T1" in nur:
        fotos_setzen("wahr"); aus = os.path.join(base, "lauf_t1"); e = lauf(od, aus, a.minuten, ["--uebernehmen"])
        ok = e is not None; det = {}
        if e:
            for k, d in e["parameter"].items():
                p = k.split(".")[1]; fehler = d["ergebnis"] - WAHR[p]; det[k] = dict(start=d["start"], ergebnis=d["ergebnis"], wahr=WAHR[p], fehler=round(fehler, 3), ok=abs(fehler) <= a.tol); ok &= abs(fehler) <= a.tol
            mono = e["monoton"] and e["J_ende"] < e["J_start"]; ok &= mono
            fest_ok = True
            for l in open(os.path.join(aus, "cache_" + [f for f in os.listdir(aus) if f.startswith("cache_")][0][6:])):
                bp = json.loads(l)["bp"]; fest_ok &= bp["haus"]["schornstein_h"] == FEST["schornstein_h"]
            ok &= fest_ok; ob = json.load(open(os.path.join(od, "objekt.json"))); sp = ob["bauteile"][0]
            uebern = all(abs(sp[p] - e["parameter"][f"haus.{p}"]["ergebnis"]) < 1e-9 for p in ("wand_h", "first_h", "anbau_b")) and bool(sp.get("historie")) and "generator_schleife" in sp.get("quelle", "") and sp["schornstein_h"] == 0.5
            ok &= uebern
            res["T1"] = dict(ok=bool(ok), parameter=det, J_start=e["J_start"], J_ende=e["J_ende"], monoton=e["monoton"], J_verlauf=e["J_verlauf_akzeptiert"], fest_unveraendert_in_allen_Vektoren=fest_ok, uebernehmen_ok=uebern,
                             ausw=e["auswertungen"], dauer_s=e["dauer_s"], vorher_nachher=e["vorher_nachher"])
        else: res["T1"] = dict(ok=False, grund="kein Ergebnis")
        # objekt.json zurueck auf den Start fuer T2/T3
        ob = json.load(open(os.path.join(od, "objekt.json"))); ob["bauteile"] = obj["bauteile"]; json.dump(ob, open(os.path.join(od, "objekt.json"), "w"), indent=1)
    if "T2" in nur:
        fotos_setzen("falsch"); aus = os.path.join(base, "lauf_t2"); e = lauf(od, aus, min(a.minuten, 10))
        if e:
            bewegt = [k for k, d in e["parameter"].items() if d["bewegt"]]
            res["T2"] = dict(ok=bool(e["J_ende"] == e["J_start"] and not bewegt), J_start=e["J_start"], J_ende=e["J_ende"], bewegt=bewegt, ausw=e["auswertungen"], dauer_s=e["dauer_s"])
        else: res["T2"] = dict(ok=False, grund="kein Ergebnis")
    if "T3" in nur:
        fotos_setzen("wahr"); aus = os.path.join(base, "lauf_t3"); e = lauf(od, aus, min(a.minuten, 6), ["--starts", "1", "--overrides", os.path.join(base, "sperre.json")] if json.dump({"sperren": ["haus.first_h"]}, open(os.path.join(base, "sperre.json"), "w")) is None else [])
        if e: res["T3"] = dict(ok=bool("haus.first_h" not in e["parameter"] and any(k == "haus.first_h" for k, _ in e["gesperrt"]) and "wand_h" in str(e["parameter"]) and e["bauteil_param_bester"]["haus"]["schornstein_h"] == 0.5 and "first_h" not in e["bauteil_param_bester"]["haus"]),
                               gesperrt=e["gesperrt"], parameter=list(e["parameter"]), J_start=e["J_start"], J_ende=e["J_ende"])
        else: res["T3"] = dict(ok=False, grund="kein Ergebnis")
    json.dump(res, open(os.path.join(base, "test_ergebnis.json"), "w"), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
    ok = all(v["ok"] for v in res.values()); print("BEWEIS generator_schleife:", "BESTANDEN" if ok else "NICHT BESTANDEN", "->", base); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

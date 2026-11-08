#!/usr/bin/env python3
"""test_s4.py - Beweise S4 (SPEC_S4_FEHLENDE_BAUTEILE.md Abschnitt 4): T1 Vorbauflaechen, T2 Kacheln, T3 Neuvernetzung der Figuren-Netze.
Ausgaben unter /media/oem/scan/rc-park_null/test_s4/. Jeder Teil schreibt <teil>/ergebnis.json; KEINE Sollwerte, KEINE Schwellenanpassung: Fehlschlag bleibt Fehlschlag.

  T1: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_s4.py T1 --ortho DIR --parse DIR
  T3: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_s4.py T3 --lauf <qualitaetsstufen_<obj>-Ordner> --objekt modelle/<obj>/objekt.json [--aus DIR]
"""
import os, sys, json, glob, shutil, argparse, subprocess, numpy as np
TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); sys.path.insert(0, TOOLS)
PY = "/media/oem/scan/venv-seg/bin/python"; AUS = "/media/oem/scan/rc-park_null/test_s4"


def t1(a):
    FA = json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"]; P = json.load(open(os.path.join(a.parse, "elemente.json")))
    vor = [F for F in FA if F["id"].startswith("e")]; geparst = P["fassaden"]; skip = P.get("uebersprungen", {})
    zeilen = []
    for F in vor:
        fid = F["id"]; n3 = sum(1 for v in F["fotos"].values() if v["guete_median"] > 0)
        e = geparst.get(fid); z = {k: v for k, v in (e["anzahl"] if e else {}).items() if v}
        fen = [x for x in (e["elemente"] if e else []) if x["klasse"] == "fenster"]
        zeilen.append(dict(id=fid, m2=F["flaeche_m2"], zelle_m=F["raster"]["zelle"], px=[F["raster"]["nu"], F["raster"]["nz"]], fotos=n3, geparst=bool(e), uebersprungen=skip.get(fid), anzahl=z,
                           fenster_stimmen=[x["stimmen"] for x in fen]))
    ok_geparst = [z for z in zeilen if z["fotos"] >= 3 and z["geparst"]]; fen_ok = [z for z in zeilen if z["geparst"] and any(s >= 2 for s in z["fenster_stimmen"])]
    erg = dict(vorbauflaechen=len(vor), mit_ge3_fotos=sum(1 for z in zeilen if z["fotos"] >= 3), geparst_von_diesen=len(ok_geparst), mit_erkerfenster_stimmen_ge2=len(fen_ok), zeilen=zeilen,
               z_protokolle=P.get("z_protokolle"), gegen_verworfen=P.get("gegen_verworfen"))
    json.dump(erg, open(os.path.join(a.parse, "t1_ergebnis.json"), "w"), indent=1); print(json.dumps({k: v for k, v in erg.items() if k != "zeilen"}, indent=1))
    for z in zeilen: print(z)


def t2(a):
    """Vergleich der Erkennerlaeufe auf einer Fassade (--ortho = Ordner mit alt/kachel/kachel_gegen/elemente.json je Variante, --fassade). Kennzahlen je Variante: Anzahl je Klasse,
    Figuren mit Score >= 0,5 (Schwelle aus zier_ausschnitt.Pruefer, VORLAEUFIG), breite Fenster (>= --breit m: Fensterachsen statt Einzelfelder), verworfene Gegenbegriffe."""
    out = {}
    for v in ("alt", "kachel", "kachel_gegen"):
        p = os.path.join(a.ortho, v, "elemente.json")
        if not os.path.exists(p): continue
        d = json.load(open(p)); f = d["fassaden"][a.fassade]; el = f["elemente"]; fen = [e for e in el if e["klasse"] == "fenster"]
        out[v] = dict(anzahl=f["anzahl"], figur_score_ge_05=sum(1 for e in el if e["klasse"] == "figur" and e["score"] >= 0.5), fenster_breit=sum(1 for e in fen if e["u1"] - e["u0"] >= a.breit),
                      fenster_breit_je=[(round(e["u0"], 1), round(e["u1"], 1), round(e["z0"], 1), round(e["z1"], 1), e["stimmen"]) for e in fen if e["u1"] - e["u0"] >= a.breit], gegen_verworfen=d.get("gegen_verworfen"), sekunden=d["sekunden"])
    json.dump(out, open(os.path.join(a.ortho, "t2_ergebnis.json"), "w"), indent=1); print(json.dumps(out, indent=1))


def baue(objp, fest, name, elem, extra_env=None):
    obj = json.load(open(objp)); import re; cmd = obj["generator"]; cmd = re.sub(r"STL_NAME=\S+", f"STL_NAME={name}", cmd) if "STL_NAME=" in cmd else f"STL_NAME={name} " + cmd
    r = subprocess.run(["bash", "-c", cmd.replace("~", os.path.expanduser("~"))], cwd=ROOT, env=dict(os.environ, BAUTEIL_PARAM=json.dumps(fest), ELEMENTE_AUS=elem, **(extra_env or {})), capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit("Generator fehlgeschlagen: " + (r.stderr or r.stdout)[-600:])
    return os.path.join(ROOT, "modelle", "stl", name), r.stdout


def koerper(stl):
    import trimesh
    m = trimesh.load(stl); teile = m.split(only_watertight=False)
    return dict(dreiecke=int(len(m.faces)), wasserdicht=bool(m.is_watertight), koerper=len(teile), volumen_mm3=round(float(abs(m.volume)), 1),
                nullvolumen=sum(1 for t in teile if abs(t.volume) < 1e-3 * abs(m.volume)))


def t3(a):
    st = json.load(open(os.path.join(a.lauf, "stand.json")))["stufen"][2]["fest"]; zj = os.path.join(a.lauf, "zier_s3", "ausschnitte.json"); d = os.path.join(AUS, "T3"); os.makedirs(d, exist_ok=True)
    fest_neu = json.loads(json.dumps(st)); fest_neu["figuren_netz"] = {"anhaengen": True, "datei": zj}; erg = {}
    ohne = json.loads(json.dumps(fest_neu)); ohne.pop("figuren_netz"); fa = ohne.get("fassade_auto")                      # wie qualitaetsstufen.zier_entscheid: Modell ohne Zierteile
    if fa: fa["klassen"] = [k for k in fa.get("klassen", []) if k != "figur"]
    for name, fe, env in (("ohne", ohne, None), ("alt", st, None), ("neu_mit", fest_neu, {"NETZ_NEU_VERNETZEN": "1"}), ("neu_ohne", fest_neu, {"NETZ_NEU_VERNETZEN": "0"})):
        stl, out = baue(a.objekt, fe, f"_s4_t3_{name}.stl", os.path.join(d, f"elemente_{name}.json"), env); ziel = os.path.join(d, f"{name}.stl"); shutil.move(stl, ziel)
        erg[name] = koerper(ziel); erg[name]["stl"] = ziel; erg[name]["log"] = [l for l in out.splitlines() if "Figur" in l or "Anbauteile" in l or "Druckreparatur" in l]; print(name, erg[name], flush=True)
        pb = os.path.join(d, f"pruefbericht_{name}.json"); r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "pruefstand.py"), a.objekt, "--stl", ziel, "--bericht", pb], cwd=ROOT, capture_output=True, text=True)
        open(os.path.join(d, f"pruefstand_{name}.log"), "w").write(r.stdout + r.stderr); erg[name]["pruefstand_rc"] = r.returncode; erg[name]["pruefstand_ende"] = (r.stdout.strip().splitlines() or [""])[-1]
    rr = subprocess.run([PY, "-I", os.path.join(TOOLS, "zier_pruefen.py"), a.objekt, zj, "--ohne", erg["ohne"]["stl"], "--stl", "alt=" + erg["alt"]["stl"], "--stl", "neu_mit=" + erg["neu_mit"]["stl"], "--stl", "neu_ohne=" + erg["neu_ohne"]["stl"], "--aus", os.path.join(d, "zier")],
                        cwd=ROOT, capture_output=True, text=True); open(os.path.join(d, "zier_pruefen.log"), "w").write(rr.stdout + rr.stderr); erg["zier_rc"] = rr.returncode
    if rr.returncode == 0:
        E = json.load(open(os.path.join(d, "zier", "zier_pruefung.json")))["ergebnisse"]
        for k in ("alt", "neu_mit", "neu_ohne"): erg[f"iou_{k}"] = float(np.mean([e[k]["iou"] for e in E if k in e])); erg["n_elemente"] = len(E)
    json.dump(erg, open(os.path.join(d, "ergebnis.json"), "w"), indent=1); print(json.dumps({k: v for k, v in erg.items() if not isinstance(v, dict)}, indent=1))


def t3b(a):
    """Wie qualitaetsstufen Versuch 8 (V8 0,557): Basis OHNE jede Figur (kein Erkennerkasten), plus Netz mit/ohne Neuvernetzung; IoU je Variante gegen Basis."""
    st = json.load(open(os.path.join(a.lauf, "stand.json")))["stufen"][2]["fest"]; zj = os.path.join(a.lauf, "zier_s3", "ausschnitte.json"); d = os.path.join(AUS, "T3"); os.makedirs(d, exist_ok=True)
    ohne = json.loads(json.dumps(st)); fa = ohne.get("fassade_auto")
    if fa: fa["klassen"] = [k for k in fa.get("klassen", []) if k != "figur"]
    netz = json.loads(json.dumps(ohne)); netz["figuren_netz"] = {"anhaengen": True, "datei": zj}; erg = {}
    for name, fe, env in (("v8_basis", ohne, None), ("v8_netz_mit", netz, {"NETZ_NEU_VERNETZEN": "1"}), ("v8_netz_ohne", netz, {"NETZ_NEU_VERNETZEN": "0"})):
        stl, out = baue(a.objekt, fe, f"_s4_t3_{name}.stl", os.path.join(d, f"elemente_{name}.json"), env); ziel = os.path.join(d, f"{name}.stl"); shutil.move(stl, ziel)
        erg[name] = koerper(ziel); erg[name]["stl"] = ziel; print(name, erg[name], flush=True)
        pb = os.path.join(d, f"pruefbericht_{name}.json"); r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "pruefstand.py"), a.objekt, "--stl", ziel, "--bericht", pb], cwd=ROOT, capture_output=True, text=True)
        open(os.path.join(d, f"pruefstand_{name}.log"), "w").write(r.stdout + r.stderr); erg[name]["pruefstand_ende"] = (r.stdout.strip().splitlines() or [""])[-1]
    rr = subprocess.run([PY, "-I", os.path.join(TOOLS, "zier_pruefen.py"), a.objekt, zj, "--ohne", erg["v8_basis"]["stl"], "--stl", "mit=" + erg["v8_netz_mit"]["stl"], "--stl", "ohne=" + erg["v8_netz_ohne"]["stl"], "--aus", os.path.join(d, "zier_v8")],
                        cwd=ROOT, capture_output=True, text=True); open(os.path.join(d, "zier_pruefen_v8.log"), "w").write(rr.stdout + rr.stderr); erg["zier_rc"] = rr.returncode
    if rr.returncode == 0:
        E = json.load(open(os.path.join(d, "zier_v8", "zier_pruefung.json")))["ergebnisse"]
        for k in ("mit", "ohne"): erg[f"iou_{k}"] = float(np.mean([e[k]["iou"] for e in E])); erg[f"iou_{k}_je"] = [round(e[k]["iou"], 3) for e in E]
        erg["n_elemente"] = len(E)
    json.dump(erg, open(os.path.join(d, "ergebnis_v8.json"), "w"), indent=1); print(json.dumps({k: v for k, v in erg.items() if not isinstance(v, dict)}, indent=1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("teil"); ap.add_argument("--ortho"); ap.add_argument("--parse"); ap.add_argument("--lauf"); ap.add_argument("--objekt"); ap.add_argument("--aus"); ap.add_argument("--fassade", default="f02"); ap.add_argument("--breit", type=float, default=1.5); a = ap.parse_args()
    {"T1": t1, "T3": t3, "T3b": t3b, "T2": t2}[a.teil](a)


if __name__ == "__main__":
    main()

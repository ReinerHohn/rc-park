#!/usr/bin/env python3
"""test_tor_elementbuch.py - Beweise fuer Uebernahmetor + Elementbuch (SPEC_S1b_TOR_ELEMENTBUCH Abschnitt 4, 2026-11-06).

Daten: Stufenlauf kaufhaus_null6 (stand.json, Stufe 3: v1 = 4 Boegen uebernommen, v2 = Freiraum mit Eckoeffnungen), Fotos wie der Laeufer
(PS.fotos_waehlen(od, 12, ohne_nacht=True), ohne Foto ohne Bewertungsmaske), Bewertungsmaske <null6>/maske. Ausgaben NUR unter
/media/oem/scan/rc-park_null/test_tor_elementbuch/ (Datenplatte). Die Masstabelle wird nicht beschrieben (Kopie fuer tor_ok).
  T0 Toleranz   foto_diff zweimal auf derselben STL/denselben Fotos: max |rot-rot'|, |gelb-gelb'| < tor_toleranz (sonst 2 x Maximum in den Plan, T0 'angepasst')
  T1 Ablehnung  alt = v1, neu = v2 (Eckoeffnungen) -> uebernahme_tor False (Grund a oder e) + Pruefstand-Zeile Arkade Hauptfassade rot
  T2 Annahme    Umkehrung von T4: alt = v1 mit dem um 0,6 m verschobenen Bogen (Elementdatei wie T4), neu = v1 richtig -> Tor JA, (e): der Bogen lokal besser
                (neu- und entfernt-Eintrag je >= 2 Fotos besser), keine (a)-Verletzung ueber tol
  T2 BEFUND (bleibt DURCHGEFALLEN, 5.11.): korrekte 0,6-m-Korrektur nicht annehmbar, weil Fotos 010 (Versatz 0,59 m) und 214 (0,94 m) das falsche Modell bevorzugen - Kameraversatz
                je Foto > Elementkorrektur; Voraussetzung: versatzkompensierte Kennzahlen (S2) / Feinlage (Stufe 5). Dann T2 wiederholen: --rg-feld rot_versatz,gelb_versatz (Felder anpassen).
  T2b unsichtbar alt = v1 mit bogen_kaempfer_versatz_m +0.8, neu = v1 -> Tor NEIN durch (b) mit |dm| < 0.001 und KEINE (e)-Ablehnung eines Elements in mehr als der Haelfte der
                Fotos. WARUM: Der urspruengliche T2 (Erwartung 'richtiger Kaempfer ist besser') fiel durch (dm -0.0001, 1 von 4 Boegen besser, 3 durch einzelne Fotos schlechter):
                die Kantenmetrik (tol 0,35 m, 11 Fotos) ist fuer die Bogenkrone BLIND. Das ist ein Befund gegen die Metrik, nicht gegen das Tor: eine unsichtbare Aenderung
                darf nicht angenommen werden (Beobachtung in der Masstabelle, S2/Plan 4b)
  T3 Identitaet alt = neu = v1 -> False mit Grund (b), keine (a)-Verletzung
  T4 Schutz     neu = v1 mit einem um 0.6 m verschobenen Bogen -> Tor NEIN durch (a) und/oder (b); Elementbuch: der verschobene Bogen (2 Eintraege neu/entfernt) NICHT 'besser',
                die anderen 3 Boegen gleich. ERWARTUNG GEAENDERT (Entscheid 5.11. nach Summenregel): (e) ist einer von mehreren Waechtern; 'gemischt' ist zulaessig, weil Fotos 000/010/214
                das verschobene Modell leicht bevorzugen (Kameraversatz je Foto > Elementkorrektur)
  T5 Martinstor tools/regression.py modelle/martinstor/objekt.json --pruefen identisch (+ bauen_abnehmen martinstor), Option --t5
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_tor_elementbuch.py [--nur T0,T1,T2,T2b,...] [--t5] [--rg-feld rot,gelb]
Werte werden NICHT nachjustiert, damit ein Test gruen wird (Ausnahme T0 nach Spec). Exit 1, wenn ein Test durchfaellt.
"""
import sys, os, json, time, copy, glob, shutil, subprocess, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import param_suche as PS, qualitaetsstufen as QS, elementbuch as EB

ROOT = PS.ROOT; PY = PS.PY
TEST = "/media/oem/scan/rc-park_null/test_tor_elementbuch"
LAUF = "/media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null6"
OBJP = os.path.join(ROOT, "modelle/kaufhaus_null5/objekt.json")
PLAN = os.path.join(ROOT, "modelle/PLAN_STANDARD_qualitaetsstufen.json")


def frei_gb(pfad="/media/oem/scan"): s = os.statvfs(pfad); return s.f_bavail * s.f_frsize / 1e9


def platz_tor():
    if frei_gb() < 3.0: print(f"STOPP: Datenplatte nur {frei_gb():.1f} GB frei (< 3 GB)", flush=True); sys.exit(4)


def gpu_tor(max_min=30):
    """Spec: nvidia-smi ohne Rechen-Prozess und kein laufender rcpark-Job ausser video_suche; sonst 60 s warten, max 30 min."""
    t0 = time.time()
    while True:
        apps = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
        jobs = [l for l in subprocess.run(["systemctl", "--user", "list-units", "rcpark-*", "--plain", "--no-pager"], capture_output=True, text=True).stdout.splitlines() if "running" in l and "video_suche" not in l and "s1b_tests" not in l]
        if not apps and not jobs: return
        if time.time() - t0 > max_min * 60: print(f"STOPP: GPU nach {max_min} min nicht frei (Prozesse {apps!r}, Jobs {jobs})", flush=True); sys.exit(5)
        print(f"  GPU belegt ({apps!r}; {len(jobs)} Jobs) - warte 60 s", flush=True); time.sleep(60)


def kontext():
    obj = json.load(open(OBJP)); os.makedirs(TEST, exist_ok=True); mk = os.path.join(TEST, "masstabelle_kopie.json")
    if not os.path.exists(mk): shutil.copy(os.path.join(ROOT, obj["masstabelle"]), mk)
    obj["masstabelle"] = mk                                                                       # tor_ok schreibt WIDERSPRUECHE: in die Kopie, nicht in die echte Tabelle
    md = os.path.join(LAUF, "maske"); od = os.path.dirname(OBJP)
    fotos = [nr for nr in PS.fotos_waehlen(od, 12, ohne_nacht=True) if os.path.exists(os.path.join(md, f"{nr}.png"))]
    plan = json.load(open(PLAN)); plan["tor_alle"] = True; plan["tor_restfeld"] = True   # (c) Restfeld im Test mitlaufen lassen
    return dict(objp=OBJP, obj=obj, plan=plan, fotos=fotos, aus=TEST, md=md, nr=3, fassaden_json=os.path.join(LAUF, "fassade_ortho_s3", "fassaden.json")), fotos


CACHE = "st_cache.json"


def st_laden():
    p = os.path.join(TEST, CACHE); return json.load(open(p)) if os.path.exists(p) else {}


def st_speichern(st): json.dump(st, open(os.path.join(TEST, CACHE), "w"))


def stand(ctx, st, fest, fotos, tag):
    platz_tor(); gpu_tor(); t0 = time.time(); s = QS.stand_von(ctx, st, fest, fotos, tag); st_speichern(st)
    print(f"  Stand {tag}: {len(s['karten'])} Karten, {time.time() - t0:.0f} s, frei {frei_gb():.1f} GB", flush=True); return s


def foto004(ctx, fest, tag, ziel):
    """Overlay foto_diff_004.jpg fuer einen Stand (Bildbeweis T1/T2)."""
    platz_tor(); gpu_tor(); od = os.path.basename(os.path.dirname(ctx["objp"]))
    stl = QS.bauen_fest(ctx["obj"], fest, f"_qs_{od}_{tag}_004.stl", os.path.join(TEST, f"elemente_{tag}_004.json"))
    try: QS.bewerten(ctx["objp"], ["004"], stl, ziel, maske_dir=ctx["md"])
    finally: os.remove(os.path.join(ROOT, stl))
    return os.path.join(ziel, "004", "foto_diff_004.jpg")


def schreibe(name, erg):
    d = os.path.join(TEST, name); os.makedirs(d, exist_ok=True); json.dump(erg, open(os.path.join(d, "ergebnis.json"), "w"), indent=1, default=str, ensure_ascii=False)


def detail_speichern(name, det):
    d = os.path.join(TEST, name); os.makedirs(d, exist_ok=True); json.dump(det, open(os.path.join(d, "detail.json"), "w"), indent=1, default=str, ensure_ascii=False)


def verschoben(f1):
    """v1 mit EINEM um 0,6 m verschobenen Bogen (zweiter Bogen der Hauptfassade f02, nach u sortiert) als eigene Elementdatei (fassade_auto.datei)."""
    E = json.load(open(f1["fassade_auto"]["datei"])); L = sorted([e for e in E["fassaden"]["f02"]["elemente"] if e["klasse"] == "bogen" and e["stimmen"] >= 2], key=lambda e: e["u0"])
    z = L[1]; u = (z["u0"], z["u1"]); z["u0"] += 0.6; z["u1"] += 0.6; os.makedirs(os.path.join(TEST, "T4"), exist_ok=True)
    dv = os.path.join(TEST, "T4", "elemente_verschoben.json"); json.dump(E, open(dv, "w")); fv = copy.deepcopy(f1); fv["fassade_auto"]["datei"] = dv
    return fv, u


def boegen_f02(det):
    """Elemente der Hauptfassade f02, Klasse bogen, aus dem Elementbuch-Detail."""
    return {k: v for k, v in det["e"]["voll"]["elemente"].items() if v["klasse"] == "bogen" and v["fassade"] == "f02"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--nur"); ap.add_argument("--t5", action="store_true")
    ap.add_argument("--rg-feld", help="rot,gelb: foto_diff-Felder fuer rot/gelb (Standard anteil_modellkanten_ohne_foto,anteil_fotokanten_ohne_modell); nach S2 z. B. rot_versatz,gelb_versatz - eigener Cache, Tests unveraendert")
    a = ap.parse_args()
    if a.rg_feld:
        global CACHE; QS.RG_FELDER = tuple(a.rg_feld.split(",")); CACHE = "st_cache_" + "_".join(QS.RG_FELDER) + ".json"
    nur = set(a.nur.split(",")) if a.nur else {"T0", "T1", "T2", "T2b", "T3", "T4"}; platz_tor()
    ctx, fotos = kontext(); S = json.load(open(os.path.join(LAUF, "stand.json")))["stufen"][2]["schritte"]; v1, v2 = S[0], S[1]
    assert v1["uebernommen"] and v2["uebernommen"], "Ausgangsdaten null6: v1/v2 muessen uebernommen sein"
    f1, f2 = v1["fest"], v2["fest"]; st = st_laden(); res = {}; print(f"Fotos ({len(fotos)}): {','.join(fotos)}  frei {frei_gb():.1f} GB", flush=True)
    s1 = stand(ctx, st, f1, fotos, "v1")
    # ---------------- T0
    if "T0" in nur:
        gpu_tor(); od = os.path.basename(os.path.dirname(OBJP)); stl = QS.bauen_fest(ctx["obj"], f1, f"_qs_{od}_t0.stl", os.path.join(TEST, "elemente_t0.json"))
        try: e2 = QS.bewerten(OBJP, fotos, stl, os.path.join(TEST, "T0", "lauf2"), maske_dir=ctx["md"])
        finally: os.remove(os.path.join(ROOT, stl))
        diffs = {}
        for nr in fotos:
            a_, b_ = s1["je_foto_rg"].get(nr), QS.rg_von(e2.get(nr))
            if a_ and b_: diffs[nr] = [round(abs(a_[0] - b_[0]), 5), round(abs(a_[1] - b_[1]), 5)]
        mx = max(max(d) for d in diffs.values()); tol = float(ctx["plan"].get("tor_toleranz", 0.01)); ok = mx < tol; angepasst = None
        if not ok:                                                                                 # Spec T0: tor_toleranz = 2 x Maximum, im Plan dokumentieren
            angepasst = round(2 * mx, 4); p_ = json.load(open(PLAN)); p_["tor_toleranz"] = angepasst
            p_["tor_toleranz_quelle"] = f"test_tor_elementbuch T0 {time.strftime('%Y-%m-%d')}: max |rot/gelb-Wiederholung| {mx:.5f} >= 0.01 -> 2 x Maximum"; json.dump(p_, open(PLAN, "w"), indent=1, ensure_ascii=False)
            ctx["plan"]["tor_toleranz"] = angepasst
        res["T0"] = dict(bestanden=ok, grund="Maximum < tor_toleranz" if ok else f"Maximum {mx:.5f} >= {tol}; tor_toleranz {angepasst} in den Plan geschrieben (Spec-Ausnahme)", maximum=mx, tor_toleranz=tol if ok else angepasst, je_foto=diffs, fotos=len(diffs))
        schreibe("T0", res["T0"]); print("T0", res["T0"]["bestanden"], f"max {mx:.5f}", flush=True)
    # ---------------- T1
    if "T1" in nur:
        s2 = stand(ctx, st, f2, fotos, "v2"); ok_, gr, det = QS.uebernahme_tor(ctx, "T1 v2 gegen v1", s2, s1, fotos, {}); detail_speichern("T1", det)
        pz = QS.tor_pruefung(ctx, f2).get("Arkade Hauptfassade: Oeffnungen ab Boden (Anzahl)", {}); b1 = QS.tor_pruefung(ctx, f1).get("Arkade Hauptfassade: Oeffnungen ab Boden (Anzahl)", {})
        buchst = sorted({g[:3] for g in gr})
        bestanden = (not ok_) and any(b in buchst for b in ("(a)", "(e)")) and pz.get("status") == "fehler"
        i1 = foto004(ctx, f1, "v1", os.path.join(TEST, "T1", "alt")); i2 = foto004(ctx, f2, "v2", os.path.join(TEST, "T1", "neu"))
        res["T1"] = dict(bestanden=bestanden, tor=ok_, buchstaben=buchst, gruende=gr, arkade_zeile_v2=pz, arkade_zeile_v1=b1, a=det["a"], b=det["b"], d=det["d"],
                         e=det["e"] if not isinstance(det["e"], dict) else {k: det["e"][k] for k in ("zaehlung", "ungeprueft", "status")}, bild_alt=i1, bild_neu=i2)
        schreibe("T1", res["T1"]); print("T1", bestanden, buchst, flush=True)
    # ---------------- T2 (Umkehrung von T4)
    if "T2" in nur:
        fv, ziel_u = verschoben(f1); sv = stand(ctx, st, fv, fotos, "v1verschoben")
        ok_, gr, det = QS.uebernahme_tor(ctx, "T2 v1 gegen v1 mit verschobenem Bogen (alt)", s1, sv, fotos, {}); detail_speichern("T2", det)
        bg = boegen_f02(det); geaendert = {k: v for k, v in bg.items() if v["art"] != "gleich_geformt"}; gleich = sorted(k for k, v in bg.items() if v["art"] == "gleich_geformt")
        besser = [k for k, v in geaendert.items() if v["status"] == "besser" and v["n_besser"] >= 2]
        bestanden = ok_ and len(geaendert) == 2 and len(besser) == 2 and not det["a"]["verletzt"]
        i1 = foto004(ctx, fv, "v1verschoben", os.path.join(TEST, "T2", "alt")); i2 = foto004(ctx, f1, "v1", os.path.join(TEST, "T2", "neu"))
        res["T2"] = dict(bestanden=bestanden, tor=ok_, gruende=gr, a=det["a"], b=det["b"], c=det["c"], d=det["d"], e_zaehlung=det["e"].get("zaehlung") if isinstance(det["e"], dict) else det["e"],
                         bogen_geaendert={k: dict(status=v["status"], art=v["art"], n_besser=v.get("n_besser"), n_schlechter=v.get("n_schlechter"), n_fotos=v.get("n_fotos")) for k, v in geaendert.items()}, bogen_gleich=gleich, boegen_lokal_besser=besser, bild_alt=i1, bild_neu=i2)
        schreibe("T2", res["T2"]); print("T2", bestanden, "Boegen besser", len(besser), flush=True)
    # ---------------- T2b (unsichtbare Aenderung wird NICHT angenommen)
    if "T2b" in nur:
        falsch = copy.deepcopy(f1); falsch["fassade_auto"]["bogen_kaempfer_versatz_m"] = 0.8; sf = stand(ctx, st, falsch, fotos, "v1kv")
        ok_, gr, det = QS.uebernahme_tor(ctx, "T2b v1 gegen v1+Kaempfer0.8", s1, sf, fotos, {}); detail_speichern("T2b", det)
        E_ = det["e"]["voll"]["elemente"] if isinstance(det["e"], dict) else {}
        schl = {k: v for k, v in E_.items() if v.get("status") == "schlechter"}; zuviel = [k for k, v in schl.items() if v["n_schlechter"] > 0.5 * v["n_fotos"]]
        dm = det["b"].get("dm"); bestanden = (not ok_) and any(g.startswith("(b)") for g in gr) and dm is not None and abs(dm) < 0.001 and not zuviel
        res["T2b"] = dict(bestanden=bestanden, tor=ok_, gruende=gr, a=det["a"], b=det["b"], e_ueber_haelfte=zuviel, e_schlechter={k: (v["n_schlechter"], v["n_fotos"]) for k, v in schl.items()})
        schreibe("T2b", res["T2b"]); print("T2b", bestanden, "dm", dm, "(e) ueber Haelfte", zuviel, flush=True)
    # ---------------- T3
    if "T3" in nur:
        ok_, gr, det = QS.uebernahme_tor(ctx, "T3 v1 gegen v1", s1, s1, fotos, {}); detail_speichern("T3", det)
        bestanden = (not ok_) and any(g.startswith("(b)") for g in gr) and not any(g.startswith("(a)") for g in gr)
        res["T3"] = dict(bestanden=bestanden, tor=ok_, gruende=gr, a=det["a"], b=det["b"]); schreibe("T3", res["T3"]); print("T3", bestanden, flush=True)
    # ---------------- T4
    if "T4" in nur:
        fv, ziel_u = verschoben(f1)
        ziel = dict(u0=ziel_u[0] + 0.6, u1=ziel_u[1] + 0.6)
        sv = stand(ctx, st, fv, fotos, "v1verschoben"); ok_, gr, det = QS.uebernahme_tor(ctx, "T4 v1 gegen v1 mit verschobenem Bogen", sv, s1, fotos, {}); detail_speichern("T4", det)
        bg = boegen_f02(det); geaendert = {k: v for k, v in bg.items() if v["art"] != "gleich_geformt"}; gleich = {k: v for k, v in bg.items() if v["art"] == "gleich_geformt"}
        e_gr = [g for g in gr if g.startswith("(e)")]; schl = [k for k, v in geaendert.items() if v["status"] == "schlechter"]
        besser_ = [k for k, v in geaendert.items() if v["status"] == "besser"]
        bestanden = (not ok_) and any(g[:3] in ("(a)", "(b)") for g in gr) and len(gleich) >= 3 and len(geaendert) == 2 and not besser_     # NEU (Entscheid 5.11.): (e) ist einer von mehreren Waechtern, 'gemischt' zulaessig
        res["T4"] = dict(bestanden=bestanden, tor=ok_, verschoben=dict(bogen_u=[ziel_u[0] + 0.6, ziel_u[1] + 0.6], von=ziel_u), gruende=gr, e_gr=e_gr,
                         bogen_geaendert={k: dict(status=v["status"], art=v["art"], n_besser=v.get("n_besser"), n_schlechter=v.get("n_schlechter"), n_fotos=v.get("n_fotos")) for k, v in geaendert.items()}, bogen_gleich=sorted(gleich), a=det["a"], b=det["b"],
                         e_zaehlung=det["e"].get("zaehlung") if isinstance(det["e"], dict) else det["e"])
        schreibe("T4", res["T4"]); print("T4", bestanden, flush=True)
    # ---------------- T5
    if a.t5:
        t0 = time.time(); r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(ROOT, "tools/regression.py"), os.path.join(ROOT, "modelle/martinstor/objekt.json"), "--pruefen"], cwd=ROOT, capture_output=True, text=True)
        open(os.path.join(TEST, "T5_regression.log"), "w").write(r.stdout + r.stderr)
        res["T5"] = dict(bestanden=r.returncode == 0, rc=r.returncode, sekunden=round(time.time() - t0), ende=(r.stdout + r.stderr)[-600:]); schreibe("T5", res["T5"]); print("T5", res["T5"]["bestanden"], flush=True)
    schlecht = [k for k, v in res.items() if not v["bestanden"]]; erg_all = dict(tests={k: v["bestanden"] for k, v in res.items()}, durchgefallen=schlecht, zeit=time.strftime("%Y-%m-%d %H:%M"))
    json.dump(erg_all, open(os.path.join(TEST, "ergebnis.json"), "w"), indent=1); print("ERGEBNIS", erg_all, flush=True); sys.exit(1 if schlecht else 0)


if __name__ == "__main__":
    main()

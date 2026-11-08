#!/usr/bin/env python3
"""test_konvergenz_logik.py - Trockenlauf der Konvergenzschleife OHNE GPU und OHNE Generatorbau (S3 Phase A, 2026-11-05).
Prueft die STEUERUNG von qualitaetsstufen.v_konvergenz mit vorhandenen Messdaten (Kostenkarten Stand v1 aus test_tor_elementbuch, Restfeld/Fassaden/Wolke Kaufhaus):
Fehlerkarte -> Kandidaten -> (Tor GEMOCKT) -> greedy Stand -> F_{k+1} -> Abbruchregeln (i)-(iv) -> Fortsetzen aus stand.json -> Bericht.
Das Tor, der Bau und die Messung sind Attrappen (nur Ablaufbeweis, KEIN Qualitaetsbeweis): die echten Beweise T1-T4 (SPEC_S3 Abschnitt 4) brauchen die GPU und kommen in Phase B.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_konvergenz_logik.py
"""
import os, sys, json, shutil, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); ROOT = os.path.dirname(HERE)
import qualitaetsstufen as Q, fehlerkarte as FKM
T = "/media/oem/scan/rc-park_null/test_tor_elementbuch"; N6 = "/media/oem/scan/rc-park_null/qualitaetsstufen_kaufhaus_null6"; S = "/media/oem/scan/rc-park_null/s3_phase_a"
AUS = os.path.join(S, "mocktest"); fehler = []


def pruefe(name, ok, text=""):
    print(("OK    " if ok else "FEHLER"), name, text, flush=True)
    if not ok: fehler.append(name)


def abbruchregeln():
    s = FKM.schwellen_laden(); cfg = dict(minuten=10, ziel_gelb=0.25, ziel_rot=0.10, ziel_min_kameras=3)
    g, k = Q.abbruch_grund([100, 80], True, 3, 1, cfg, s); pruefe("(i) Grenzwert = konvergiert", g.startswith("(i)") and k)
    g, k = Q.abbruch_grund([100, 80], False, 0, 1, cfg, s); pruefe("(ii) nichts angenommen, nicht konvergiert", g.startswith("(ii)") and not k)
    g, k = Q.abbruch_grund([100, 99.5], False, 2, 1, cfg, s); pruefe("(iii) F fiel < 1 %", g.startswith("(iii)") and not k)
    g, k = Q.abbruch_grund([100, 120], False, 2, 1, cfg, s); pruefe("(iii) F stieg", g.startswith("(iii)") and not k)
    g, k = Q.abbruch_grund([100, 80], False, 2, 11, cfg, s); pruefe("(iv) Zeitbudget", g.startswith("(iv)") and not k)
    g, k = Q.abbruch_grund([100, 80], False, 2, 1, cfg, s); pruefe("weiter", g is None)
    res = dict(F_je_flaeche=dict(a=dict(zellen_sicht=10, fotos_je_zelle_median=5, gelb_mittel=0.2, rot_mittel=0.05), b=dict(zellen_sicht=10, fotos_je_zelle_median=2, gelb_mittel=0.9, rot_mittel=0.9)))
    pruefe("ziel: Flaeche mit < 3 Kameras zaehlt nicht", Q.ziel_erreicht(res, cfg)[0])
    res["F_je_flaeche"]["a"]["gelb_mittel"] = 0.3; pruefe("ziel: gelb 0,30 >= 0,25 -> nicht erreicht", not Q.ziel_erreicht(res, cfg)[0])


def schleife():
    shutil.rmtree(AUS, ignore_errors=True); os.makedirs(AUS)
    for d in ("fassade_ortho_s3", "fassade_parse_s3"): os.symlink(os.path.join(N6, d), os.path.join(AUS, d))
    objp = os.path.join(ROOT, "modelle", "kaufhaus_null5", "objekt.json"); obj = json.load(open(objp)); plan = json.load(open(FKM.PLAN_STANDARD)); cfg = next(s for s in plan["stufen"] if s["verfahren"] == "konvergenz")
    cfg = dict(cfg, laeufe=3, max_kandidaten_je_lauf=4); fotos = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(T + "/entscheid_v1/*/kostenkarte.npz"))
    karten = {nr: f"{T}/entscheid_v1/{nr}/kostenkarte.npz" for nr in fotos}
    stl_mock = os.path.join(ROOT, "modelle", "stl", "_mock_s3.stl")
    def stand_von(ctx, st, fest, fo, tag): return dict(fest=fest, je_foto={nr: 0.5 for nr in fo}, je_foto_rg={nr: [0.2, 0.3] for nr in fo}, karten={nr: karten[nr] for nr in fo if nr in karten}, elemente=f"{T}/elemente_v1.json", stl=None)
    def bauen_fest(o, fest, name, elem): shutil.copy(f"{N6}/modell_s3_v1.stl", stl_mock); return "modelle/stl/_mock_s3.stl"
    ablehn = []; zaehler = [0]
    def entscheide(ctx, st, name, neu, alt, fo, cfg_, tag, behalten=()):
        zaehler[0] += 1; ok = (zaehler[0] % 3 == 0)                                                   # jeder dritte Kandidat 'bestanden' (Attrappe)
        if not ok: ablehn.append(name)
        return ok, ([] if ok else ["(a) Attrappe: je Foto schlechter", "(e) Attrappe"]), dict(b=dict(art="gepaart"))
    def modell_messen(*a, **k): return dict(fest=a[5], kennzahlen=dict(kosten=0.5, modell_ohne_foto=0.2, foto_ohne_modell=0.3, fotos=11), stl=None, je_foto={}, bilder={})
    Q.stand_von, Q.bauen_fest, Q.entscheide_fest, Q.modell_messen = stand_von, bauen_fest, entscheide, modell_messen
    Q.alle_fotos = lambda ctx: fotos
    Q.restfeld_messen = lambda ctx, stand, fj, dach=False: f"{S}/restfeld_v1"
    Q._param_fest = lambda ctx, fest, p, fo, tag: (None, dict(zustand="flach (Attrappe)"))
    ctx = dict(objp=objp, obj=obj, plan=plan, fotos=fotos, aus=AUS, md=f"{N6}/maske", fest={}, nr=4, t0=0.0, speichern=lambda: json.dump(st, open(os.path.join(AUS, "stand.json"), "w"), indent=1, default=str), vorige=None)
    st = dict(name="Konvergenz (Attrappe)", verfahren="konvergenz"); import time; ctx["t0"] = time.time()
    try: Q.v_konvergenz(ctx, st, cfg)
    finally:
        if os.path.exists(stl_mock): os.remove(stl_mock)
    ctx["speichern"](); L = st["laeufe"]                                                              # wie main(): nach dem Verfahren speichern
    pruefe("Laeufe gelaufen", len(L) >= 1, f"{len(L)} Laeufe, Abbruch: {st['abbruch']}")
    pruefe("jeder Lauf hat F_start und F_ende", all(l.get("F_start") is not None and l.get("F_ende") is not None for l in L))
    pruefe("Kandidaten protokolliert mit Buchstaben bei Ablehnung", all((r["angenommen"] or r.get("versuche") is None or r["versuche"][0]["buchstaben"] == ["a", "e"]) for l in L for r in l["kandidaten"]), f"{sum(len(l['kandidaten']) for l in L)} Kandidaten")
    pruefe("Bericht je Lauf", all(os.path.exists(os.path.join(AUS, "konvergenz_s4", f"bericht_k{l['k']}.md")) for l in L))
    pruefe("F-Verlauf gespeichert", len(st["F_verlauf"]) == len(L) + 1, str(st["F_verlauf"]))
    pruefe("Bilder vorher/nachher", all(isinstance(l.get("bilder"), list) and len(l["bilder"]) >= 1 for l in L), str(L[0].get("bilder"))[:160])
    pruefe("Abbruchgrund genannt, nur (i) heisst konvergiert", bool(st["abbruch"]) and (st["konvergiert"] == st["abbruch"].startswith("(i)")), st["abbruch"])
    # Fortsetzen: gleiche stand.json, zweiter Aufruf darf keine Kandidaten wiederholen
    n0 = sum(len(l["kandidaten"]) for l in L); zaehler[0] = 0
    st2 = json.load(open(os.path.join(AUS, "stand.json"))); st2.pop("abbruch"); st2["laeufe"][-1]["fertig"] = False
    ctx["speichern"] = lambda: None
    shutil.copy(f"{N6}/modell_s3_v1.stl", stl_mock)
    try: Q.v_konvergenz(ctx, st2, dict(cfg, laeufe=len(L)))
    finally:
        if os.path.exists(stl_mock): os.remove(stl_mock)
    pruefe("Fortsetzen wiederholt keine erledigten Kandidaten", sum(len(l["kandidaten"]) for l in st2["laeufe"]) == n0, f"{n0} vorher, {sum(len(l['kandidaten']) for l in st2['laeufe'])} nachher")


if __name__ == "__main__":
    abbruchregeln(); schleife()
    print("ALLE BESTANDEN" if not fehler else f"DURCHGEFALLEN: {fehler}"); sys.exit(1 if fehler else 0)

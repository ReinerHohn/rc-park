#!/usr/bin/env python3
"""kandidaten.py - Kandidaten aus den Clustern der Fehlerkarte (SPEC_S3_KONVERGENZ Abschnitt 2, deterministisch, KEINE Suche und KEIN Bau hier, 2026-11-05).

Je Cluster hoechstens `max_je_cluster` Kandidaten aus den VORHANDENEN Bauteilregeln (baukasten_gen: fassade_auto-Klassen, relief_wolke/bloecke_wolke, param_suche); Regeln allgemein:
  gelb, rest_median > +rest_tol   Daten vor dem Modell  -> VORSPRUNG: Wand = Block (bloecke_wolke, Box = Cluster, Tiefe = rest_median), Dach = Klasse gaube (Tiefe aus rest)
  gelb, rest_median < -rest_tol   Daten hinter dem Modell -> RUECKSPRUNG: Klasse oeffnung, wenn z0 <= ruecksprung_boden_m oder frei_anteil > frei_ruecksprung, sonst Klasse ruecksprung
                                  (Tiefe = |rest_median|; die Klasse 'ruecksprung' kennt baukasten_gen noch nicht -> anwendbar = false, bis S4 sie liefert)
  gelb, |rest| <= rest_tol oder rest_n < rest_n_min (keine Tiefe gesehen) -> FLAECHENELEMENT: Ortho-Ausschnitt des Clusters (Pixel/m des Ausschnitts, Mindestgroesse flaechenelement_min_px)
                                  fuer fassade_parsing (OWLv2, Klassen textur_klassen) - das Parsen selbst (GPU) macht der Laeufer; Ausschnitt zu klein -> 'textur' (nur Protokoll)
  rot, Cluster schneidet Elemente des Stands -> FEINLAGE des Elements mit der groessten Ueberdeckung (Verschiebung u/z +- feinlage_m, Breite x feinlage_breiten = 6 Varianten,
                                  davon die 3 besten im Elementbuch-Vorabcheck - der Laeufer misst) und ENTFERNEN desselben Elements
  rot ohne Element                -> PARAMETER: Suchraum aus dem Plan (Stufe 'parameter' bzw. Formsuche der Fassade), Dach: Dachparameter (Plan dach_parameter)
  Dach (alle Arten): Dachparameter-Kandidat mit Richtung nach dem Vorzeichen des Rest-Medians der Dachebene je Quelle; Tor-Buchstabe (f): Richtung muss mindestens dach_quellen_min
                                  Quelle AUSSER DOM1 (Stadt-LoD2 oder Stadtmesh) bestaetigen; Wolke ist fuer Dach gesperrt (Spec 0b).
  Art 'quellen_widerspruch' (Dachquellen weichen > widerspruch_m ab): KEIN Kandidat, nur Protokoll.
Jeder Kandidat traegt `beleg` ("fehlerkarte Lauf k, Cluster c: <art>, <n> Fotos, rest <m>", Regel 3b). `anwenden()` schreibt fuer den Bau die geaenderte Elementdatei/Reliefdatei (JSON)
und liefert fest' - gebaut wird erst im Laeufer (qualitaetsstufen konvergenz). Schwellen NUR aus Plan konvergenz (fehlerkarte.schwellen_laden), keine Festwerte.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/kandidaten.py <cluster.json> --ortho <fassade_ortho-Ordner> [--elemente E.json] [--plan P.json] [--aus DIR]
"""
import os, sys, json, copy, argparse
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fehlerkarte as FKM


def plan_parameter(plan):
    """Suchraeume aus dem Plan: Stufe 'parameter' (Liste) + Formsuche der Fassade (suche) -> [dict(bauteil, param, werte)]."""
    out = []
    for s in (plan or {}).get("stufen", []):
        if s.get("verfahren") == "parameter": out += [dict(bauteil=p["bauteil"], param=p["param"], werte=p["werte"]) for p in s.get("parameter", [])]
        for v in s.get("versuche", []) or []:
            for q in v.get("suche", []) or []: out.append(dict(bauteil="fassade_auto", param=q["param"], werte=q["werte"]))
    return out


def dach_ebenen_median(fk_dir, fid, schw):
    """Median des Rests je Quelle ueber die ganze Dachebene (nur Zellen mit n_fotos >= min_fotos) aus <fk_dir>/<fid>.npz -> {quelle: median}."""
    z = np.load(os.path.join(fk_dir, f"{fid}.npz")); ok = z["n_fotos"] >= schw["min_fotos"]; out = {}
    for q in FKM.QUELLEN:
        if f"rest_{q}" not in z.files: continue
        r = z[f"rest_{q}"].astype(np.float32); m = ok & np.isfinite(r)
        if m.sum(): out[q] = round(float(np.median(r[m])), 3)
    return out


def ausschnitt(c, ortho_dir, fassaden, schw, aus=None):
    """Ortho-Ausschnitt eines Clusters (ortho_<fid>.png) -> (pixel_je_m, (breite_px, hoehe_px), Datei oder None). Raster aus fassaden.json (u0, z1, zelle)."""
    F = next((f for f in fassaden if f["id"] == c["fid"]), None); p = os.path.join(ortho_dir, f"ortho_{c['fid']}.png")
    if F is None or not os.path.exists(p): return None, None, None
    r = F["raster"]; ppm = 1.0 / r["zelle"]; im = cv2.imread(p)
    x0, x1 = int(round((c["u0"] - r["u0"]) * ppm)), int(round((c["u1"] - r["u0"]) * ppm)); y0, y1 = int(round((r["z1"] - c["z1"]) * ppm)), int(round((r["z1"] - c["z0"]) * ppm))
    x0, x1, y0, y1 = max(0, x0), min(im.shape[1], x1), max(0, y0), min(im.shape[0], y1)
    if x1 <= x0 or y1 <= y0: return ppm, (0, 0), None
    f = None
    if aus:
        os.makedirs(aus, exist_ok=True); f = os.path.join(aus, f"ausschnitt_c{c['id']:03d}_{c['fid']}.png"); cv2.imwrite(f, im[y0:y1, x0:x1])
    return ppm, (x1 - x0, y1 - y0), f


def element_zuordnung(c, stand_el):
    """Element der Datei mit der groessten Ueberdeckung mit dem Cluster (Box in u/z) -> (schluessel, ueberdeckung_m2) oder None."""
    best = None
    for k, g in stand_el.get(c["fid"], []):
        w = min(c["u1"], g["u1"]) - max(c["u0"], g["u0"]); h = min(c["z1"], g["z1"]) - max(c["z0"], g["z0"])
        if w > 0 and h > 0 and (best is None or w * h > best[1]): best = (k, w * h)
    return best


def kandidaten_aus_clustern(res, schw, plan=None, fk_dir=None, ortho_dir=None, fassaden=None, stand_el=None, aus=None):
    """res = cluster.json (fehlerkarte.rechnen); Rueckgabe dict(kandidaten=[...], protokoll=[...])."""
    k = res["k"]; C = res["cluster"]; kand = []; prot = []; pl = plan_parameter(plan); stand_el = stand_el or {}; dach_med = {}
    def beleg(c, art, extra=""):
        r = c.get("rest_median"); return f"fehlerkarte Lauf {k}, Cluster {c['id']}: {art}, {len(c['fotos'])} Fotos, rest {('%+.2f m' % r) if r is not None else 'n/a'} ({c.get('rest_quelle', '-')}){extra}"
    def neu(c, art, **kw):
        d = dict(art=art, cluster=c["id"], fid=c["fid"], box=dict(u0=c["u0"], u1=c["u1"], z0=c["z0"], z1=c["z1"]), flaeche_m2=c["flaeche_m2"], fotos=c["fotos"], beleg=beleg(c, art, kw.pop("beleg_extra", "")), **kw)
        d["id"] = len(kand); kand.append(d); return d
    for c in C:
        n0 = len(kand)
        if c["art"] == "quellen_widerspruch":
            prot.append(dict(cluster=c["id"], art="quellen_widerspruch", fid=c["fid"], rest_je_quelle=c["rest_je_quelle"], text="Dachquellen widersprechen sich > widerspruch_m: kein Kandidat (Spec 0b)")); continue
        r, rn = c.get("rest_median"), c.get("rest_n", 0); tol = schw["rest_tol_m"]; el = element_zuordnung(c, stand_el)
        if c["dach"] and fk_dir:                                                                          # Dachparameter: Richtung je Dachebene, Tor-Buchstabe (f) schon HIER ausgewiesen
            if c["fid"] not in dach_med: dach_med[c["fid"]] = dach_ebenen_median(fk_dir, c["fid"], schw)
            med = dach_med[c["fid"]]; ref = med.get("dom1") if med.get("dom1") is not None else next(iter(med.values()), None)
            if ref is not None and abs(ref) > tol and not any(x["art"] == "parameter" and x["fid"] == c["fid"] and x.get("dach") for x in kand):
                bestaetigt = [q for q, v in med.items() if q != "dom1" and abs(v) > tol and np.sign(v) == np.sign(ref)]
                p_ = [p for p in pl if p["param"] in schw["dach_parameter"]]
                neu(c, "parameter", dach=True, kandidaten_parameter=p_, richtung=("hoeher" if ref > 0 else "tiefer"), ebene_median=med, f_bestaetigt_durch=bestaetigt,
                    f_ok=len(bestaetigt) >= schw["dach_quellen_min"], beleg_extra=f"; Dachebene {c['fid']} Median je Quelle {med}")
        if c["art"] == "gelb":
            if rn >= schw["rest_n_min"] and r is not None and r > tol:
                if c["dach"]: neu(c, "vorsprung", klasse="gaube", tiefe_m=round(r, 3))
                else: neu(c, "vorsprung", klasse="bloecke_wolke", tiefe_m=round(r, 3))
            elif rn >= schw["rest_n_min"] and r is not None and r < -tol:
                kl = "oeffnung" if (c["z0"] <= schw["ruecksprung_boden_m"] or (c.get("frei_anteil") or 0) > schw["frei_ruecksprung"]) else "ruecksprung"
                neu(c, "ruecksprung", klasse=kl, tiefe_m=round(abs(r), 3), anwendbar=(kl == "oeffnung"), **({} if kl == "oeffnung" else dict(grund="Klasse 'ruecksprung' fehlt in baukasten_gen (S4)")))
            elif not c["dach"]:
                ppm, px, f = ausschnitt(c, ortho_dir, fassaden, schw, aus) if (ortho_dir and fassaden) else (None, None, None)
                if px is not None and min(px) >= schw["flaechenelement_min_px"]:
                    neu(c, "flaechenelement", klassen=schw["textur_klassen"], ausschnitt_px=list(px), pixel_je_m=ppm, ausschnitt_datei=f, parsen="OWLv2 (fassade_parsing) im Laeufer, GPU")
                else: neu(c, "textur", ausschnitt_px=(list(px) if px else None), pixel_je_m=ppm, text="nur protokolliert: Ausschnitt zu klein oder kein Ortho", anwendbar=False)
            else: neu(c, "textur", text="Dach ohne Tiefe: nur protokolliert", anwendbar=False)
        elif c["art"] == "rot":
            if el:
                var = [dict(du=sg * schw["feinlage_m"], dz=0.0, breite=1.0) for sg in (-1, 1)] + [dict(du=0.0, dz=sg * schw["feinlage_m"], breite=1.0) for sg in (-1, 1)] + [dict(du=0.0, dz=0.0, breite=b_) for b_ in schw["feinlage_breiten"]]
                neu(c, "feinlage", element=el[0], varianten=var, vorabcheck=f"Elementbuch im Laeufer: die {schw['feinlage_behalten']} besten von {len(var)}", behalten=schw["feinlage_behalten"])
                neu(c, "entfernen", element=el[0])
            else:
                if not any(x["art"] == "parameter" and x["cluster"] == c["id"] for x in kand):
                    p_ = [p for p in pl if (p["param"] in schw["dach_parameter"]) == bool(c["dach"])]
                    neu(c, "parameter", dach=bool(c["dach"]), kandidaten_parameter=p_, suchbereich="Plan: " + ", ".join(f"{p['bauteil']}.{p['param']} {p['werte']}" for p in p_[:6]))
        extra = [x for x in kand[n0:]]
        if len(extra) > schw["max_je_cluster"]:
            for x in extra[schw["max_je_cluster"]:]: kand.remove(x)
    for i, x in enumerate(kand): x["id"] = i
    return dict(kandidaten=kand, protokoll=prot, lauf=k, schwellen=schw, erzeugt_aus=res.get("restfeld"))


def anwenden(kand, fest, ctx, schw):
    """Geaenderte Dateien schreiben (JSON, KEIN Bau) und fest' liefern: (fest', {'datei': ..., 'hinweis': ...}) oder (None, grund).
    ctx: aus (Ordner), fassaden (Liste fassaden.json), elemente_parse (fassade_parsing-elemente.json des Stands) - noch nicht jede Art ist anwendbar (siehe 'anwendbar')."""
    if kand.get("anwendbar") is False: return None, kand.get("grund", "nicht anwendbar")
    f = copy.deepcopy(fest); os.makedirs(ctx["aus"], exist_ok=True); tag = f"c{kand['cluster']:03d}_k{kand['id']:02d}"; b = kand["box"]
    fa = f.get("fassade_auto") or {}; ep = fa.get("datei") or ctx.get("elemente_parse")
    if kand["art"] in ("feinlage", "entfernen", "flaechenelement") or (kand["art"] == "ruecksprung" and kand.get("klasse") == "oeffnung"):
        E = json.load(open(ep)); Fa = E["fassaden"][kand["fid"]]
        if kand["art"] == "ruecksprung":
            Fa["elemente"].append(dict(klasse="oeffnung", u0=b["u0"], u1=b["u1"], z0=b["z0"], z1=b["z1"], stimmen=len(kand["fotos"]), tiefe_m=kand["tiefe_m"], quelle=kand["beleg"]))
        else:
            i_ = min(range(len(Fa["elemente"])), key=lambda i: abs(0.5 * (Fa["elemente"][i]["u0"] + Fa["elemente"][i]["u1"]) - 0.5 * (b["u0"] + b["u1"])) + abs(0.5 * (Fa["elemente"][i]["z0"] + Fa["elemente"][i]["z1"]) - 0.5 * (b["z0"] + b["z1"])))
            if kand["art"] == "entfernen": Fa["elemente"].pop(i_)
            elif kand["art"] == "feinlage":
                v = kand.get("variante") or kand["varianten"][0]; e = Fa["elemente"][i_]; w = e["u1"] - e["u0"]; um = 0.5 * (e["u0"] + e["u1"]) + v["du"]
                e["u0"], e["u1"] = um - 0.5 * w * v["breite"], um + 0.5 * w * v["breite"]; e["z0"] += v["dz"]; e["z1"] += v["dz"]
            else: return None, "flaechenelement: Elemente liefert erst fassade_parsing auf dem Ausschnitt (Laeufer)"
        p = os.path.join(ctx["aus"], f"elemente_{tag}.json"); json.dump(E, open(p, "w"), indent=1); f.setdefault("fassade_auto", {}).update(datei=p, quelle=kand["beleg"]); return f, dict(datei=p)
    if kand["art"] == "vorsprung" and kand.get("klasse") == "bloecke_wolke":
        bw = f.get("bloecke_wolke") or {}; rj = bw.get("datei"); F_ = next(x for x in ctx["fassaden"] if x["id"] == kand["fid"])
        R = json.load(open(rj)) if rj and os.path.exists(rj) else dict(fassaden={}, parameter=dict(stufe=0), wolke="fehlerkarte")
        Fa = R["fassaden"].setdefault(kand["fid"], dict(n=F_["n"], d=F_["d"], o=F_["o"], stufen=[], bloecke=[])); Fa.setdefault("bloecke", []).append(dict(u=[b["u0"], b["u1"]], z=[b["z0"], b["z1"]], tiefe_m=kand["tiefe_m"], quelle=kand["beleg"]))
        p = os.path.join(ctx["aus"], f"relief_{tag}.json"); json.dump(R, open(p, "w"), indent=1); bw.update(anhaengen=True, datei=p, fassaden=sorted(set((bw.get("fassaden") or []) + [kand["fid"]]))); f["bloecke_wolke"] = bw; return f, dict(datei=p)
    return None, f"Art {kand['art']}/{kand.get('klasse')} noch nicht anwendbar (Laeufer-Phase B)"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cluster"); ap.add_argument("--ortho"); ap.add_argument("--elemente"); ap.add_argument("--plan"); ap.add_argument("--aus"); a = ap.parse_args(argv)
    res = json.load(open(a.cluster)); schw = res["schwellen"]; plan = json.load(open(a.plan if a.plan else FKM.PLAN_STANDARD)); fa = json.load(open(os.path.join(a.ortho, "fassaden.json")))["fassaden"] if a.ortho else None
    stand_el = {}
    if a.elemente:
        import elementbuch as EB
        for kk, g in EB.elemente_laden(a.elemente)[0].items():
            F_ = next((f for f in (fa or []) if f["id"] == g["fassade"]), None); sg = -1.0 if (F_ is not None and float(np.dot(g["rahmen"]["d"][:2], F_["d"][:2])) < 0) else 1.0
            stand_el.setdefault(g["fassade"], []).append((kk, dict(g, u0=min(sg * g["u0"], sg * g["u1"]), u1=max(sg * g["u0"], sg * g["u1"]))))
    out = kandidaten_aus_clustern(res, schw, plan, os.path.dirname(os.path.abspath(a.cluster)), a.ortho, fa, stand_el, a.aus)
    aus = a.aus or os.path.dirname(os.path.abspath(a.cluster)); json.dump(out, open(os.path.join(aus, "kandidaten.json"), "w"), indent=1, ensure_ascii=False)
    for x in out["kandidaten"][:schw["ausgabe_max_kandidaten"]]: print(x["id"], x["art"], x.get("klasse", ""), x["fid"], x["box"], x.get("tiefe_m", ""), x["beleg"])
    print(f"{len(out['kandidaten'])} Kandidaten, {len(out['protokoll'])} Protokolleintraege -> {aus}/kandidaten.json")


if __name__ == "__main__":
    main()

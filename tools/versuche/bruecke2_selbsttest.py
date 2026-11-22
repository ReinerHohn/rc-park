#!/usr/bin/env python3
"""bruecke2_selbsttest.py --fall NAME=<selbsttest-k-ordner>:<fotos> ... --aus DIR [--gpu] [--vram-mb 2500]   (22.11.2026)
   bruecke2_selbsttest.py --echt NAME=<teilA>:<teilB>:<zwischenmodell>:<fotos> --aus DIR [--gpu]

MESSUNG DER DREI SOFTWARE-HEBEL (tools/bruecke_hebel.py) an den Selbsttest-Ordnern von eck_selbsttest.py (teilA = Ausschnitt des wahren Modells, teilB = Ausschnitt,
mit bekannter Sim3 MB bewegt, stufe/eck.json = Zwischenmodelle der Kopplungsstufe). Keine Mapper-Laeufe: die Zwischenmodelle des Selbsttests werden wiederverwendet.
Je Fall:
 0 FREI    : Kopplung E->A, E->B wie seiten_eck_koppeln (kopplung_pruefen), Fehler gegen die Wahrheit: Drehung, davon Kippung (Lot-Achse) / Kurs, Massstab, Lage B (m).
 A LOT     : Fluchtpunkt-Lot je Teil; relativer Lotfehler der Teile (Wahrheit); Lot-Zwang (lot_kante); Gegenprobe Lot B absichtlich 0,5 Grad verfaelscht.
 B FUEHREN : Kandidatenpaare A x B aus der Naeherung (frei bzw. Lot), ALIKED+LightGlue (--gpu), Epipolarband, direkte Spuren, direkte Sim3; Negativfaelle mit falscher
             Naeherung (2 Grad Kurs, 0,5 m, 3 m, 180 Grad um das Lot) - Bestaetigung = direkte Kopplung trifft die (falsche) Naeherung.
 C AUSGLEICH: gemeinsamer Ausgleich (starr 7 / Lot 5 / halbstarr +2) ueber E-A, E-B, direkte Spuren; Verformungsfaelle: Teil B mit Massstabsverlauf 2/5 % bzw. Biegung 1/3 Grad
             (Feld wie eck_rest_eichung.verformen) -> Lagefehler B starr vs. halbstarr, erkannte Verformung a, b +- sigma.
Ausgabe: <aus>/<NAME>/ergebnis.json, Zusammenfassung <aus>/zusammenfassung.json."""
import os, sys, json, argparse, numpy as np, pycolmap
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
import bruecke_hebel as BH, seiten_eck_koppeln as EK
from sim3_robust import matrix, anwenden


def wahrheit_MB():
    rng = np.random.default_rng(7); q = rng.normal(size=4); q /= np.linalg.norm(q); return matrix(1.7, pycolmap.Rotation3d(q).matrix(), [5.0, -3.0, 2.0])   # wie eck_selbsttest


def fehler(M_est, M_true, PB, m_je, oben_a):
    """Fehler der Kopplung B->A gegen die Wahrheit: Drehung, Kippung (Bewegung des Lots), Kurs, Massstab %, Lage der B-Punkte (m)."""
    if M_est is None: return None
    s, R, _ = EK.zerlegen(M_est @ np.linalg.inv(M_true)); u = np.asarray(oben_a, float) / np.linalg.norm(oben_a)
    kipp = float(np.degrees(np.arccos(np.clip((R @ u) @ u, -1, 1)))); d = np.linalg.norm(anwenden(M_est, PB) - anwenden(M_true, PB), axis=1) * m_je
    return dict(drehung_grad=round(EK.winkel(R), 3), kippung_grad=round(kipp, 3), massstab_prozent=round(abs(s - 1) * 100, 3), lage_median_m=round(float(np.median(d)), 3), lage_p90_m=round(float(np.percentile(d, 90)), 3))


def koppeln_frei(E, Z):
    X, Y, td, ns = BH.punkte(E, Z)
    if len(ns) < EK.MIN_BILDER_TEIL: return None, dict(bilder=len(ns)), False, "zu wenige Bilder", (X, Y, td)
    M, pr, ok, g = EK.kopplung_pruefen(X, Y, E.ausdehnung(), Z.ausdehnung(), tiefe=td); return M, pr, ok, g, (X, Y, td)


def kurs_drehen(M_AB, oben_a, B_in_A_mitte, grad):
    """Falsche Naeherung: Drehung um das Lot von A durch die Mitte von B."""
    R = BH._rot(np.radians(grad) * np.asarray(oben_a, float) / np.linalg.norm(oben_a)); c = B_in_A_mitte; D = np.eye(4); D[:3, :3] = R; D[:3, 3] = c - R @ c; return D @ M_AB


def verschieben(M_AB, oben_a, meter, m_je):
    """Falsche Naeherung: waagerecht um 'meter' (senkrecht zum Lot) verschoben."""
    u = np.asarray(oben_a, float) / np.linalg.norm(oben_a); e = BH.basis(u)[:, 0]; D = np.eye(4); D[:3, 3] = e * meter / m_je; return D @ M_AB


def fuehren(name, A, B, M_AB, sigma, fotos, aus, gpu, vram, resize, wahr=None):
    """Kandidatenpaare -> LightGlue -> Pruefung -> direkte Kopplung. -> (info, spuren, M_direkt)."""
    os.makedirs(aus, exist_ok=True); kp = BH.kandidaten_paare(A, B.transformiert(M_AB)); info = dict(kandidatenpaare=len(kp))
    npz = os.path.join(aus, "lg.npz")
    pj = os.path.join(aus, "paare.json"); gleich = os.path.isfile(npz) and os.path.isfile(pj) and json.load(open(pj)) == [list(p[:2]) for p in kp]
    if not gleich:
        if not gpu: info["grund"] = "keine LightGlue-Zuordnungen (ohne --gpu)"; return info, [], None
        if os.path.isfile(npz): os.rename(npz, npz + ".alt")
        if not kp: info["grund"] = "keine Kandidatenpaare"; return info, [], None
        npz = BH.lg_paare(kp, fotos, aus, vram_mb=vram, resize=resize); json.dump([list(p[:2]) for p in kp], open(os.path.join(aus, "paare.json"), "w"))
        if npz is None: info["grund"] = "lg_match gescheitert"; return info, [], None
    st, sp = BH.paare_pruefen(npz, A, B, M_AB, sigma); info.update(st)
    M, pr, ok, g, X, Y, td = BH.direkt_koppeln(A, B, sp); info.update(direkt=dict(ok=ok, grund=g, **pr))
    if M is not None:
        b, d = BH.bestaetigt(M, M_AB, B.P, sigma); info["bestaetigt_naeherung"] = b; info["unterschied_zur_naeherung"] = d
    return info, sp, (M if ok else None)


def _m4(sim):
    M = np.eye(4); M[:3, :] = np.asarray(sim.matrix(), float); return M


def lauf(name, A, B, E, fotos, aus, gpu, vram, resize, MB=None, m_je=1.0, lot_cache=None, rE=None):
    os.makedirs(aus, exist_ok=True); erg = dict(name=name); Mt = np.linalg.inv(MB) if MB is not None else None; PB = B.P
    rA, rB = lot_cache
    la = BH.lot_modell(rA, fotos, cache=os.path.join(aus, "lot_a.json")); lb = BH.lot_modell(rB, fotos, cache=os.path.join(aus, "lot_b.json")); erg["lot"] = dict(a=la, b=lb)
    oa, ob = np.asarray(la["oben"]), np.asarray(lb["oben"])
    MA, pa, oka, ga, (XA, YA, tA) = koppeln_frei(E, A); MBc, pb, okb, gb, (XB, YB, tB) = koppeln_frei(E, B)
    erg["frei"] = dict(a=dict(ok=oka, grund=ga, **pa), b=dict(ok=okb, grund=gb, **pb))
    if not (oka and okb): erg["grund"] = "freie Kopplung nicht stimmig"; return erg
    M_frei = MA @ np.linalg.inv(MBc); sig = float(np.sqrt(sum(p["rest_rel"] ** 2 + p["massstab_haelften_rel"] ** 2 for p in (pa, pb))))
    R_ab = EK.zerlegen(M_frei)[1]; erg["frei"]["lot_winkel_grad"] = round(float(np.degrees(np.arccos(np.clip(abs((R_ab @ ob) @ oa) / np.linalg.norm(ob) / np.linalg.norm(oa), -1, 1)))), 3)
    erg["frei"]["sigma"] = round(sig, 5)
    if Mt is not None:
        erg["frei"]["fehler"] = fehler(M_frei, Mt, PB, m_je, oa)
        Rt = EK.zerlegen(Mt)[1]; erg["lot"]["relativ_fehler_grad"] = round(float(np.degrees(np.arccos(np.clip(abs((Rt @ ob) @ oa) / np.linalg.norm(oa) / np.linalg.norm(ob), -1, 1)))), 3)
    # Zweitkopplung ueber Rueckprojektion gemeinsamer Bilder (pycolmap.align_reconstructions_via_reprojections, Kern von model_merger; Recherche 22.11. Methode 7)
    if rE is not None:
        try:
            ra, rb = pycolmap.align_reconstructions_via_reprojections(rE, rA), pycolmap.align_reconstructions_via_reprojections(rE, rB)
            if ra is not None and rb is not None:
                M_rp = _m4(ra) @ np.linalg.inv(_m4(rb)); erg["reproj"] = dict(ok=True, unterschied_zu_frei=BH.bestaetigt(M_rp, M_frei, B.P, sig)[1])
                if Mt is not None: erg["reproj"]["fehler"] = fehler(M_rp, Mt, PB, m_je, oa)
            else: erg["reproj"] = dict(ok=False, grund="keine Ausrichtung")
        except Exception as ex: erg["reproj"] = dict(ok=False, grund=str(ex)[:200])
    print("  frei", json.dumps(erg.get("frei", {}).get("fehler")), "reproj", json.dumps((erg.get("reproj") or {}).get("fehler")), flush=True)
    # A: Lot-Zwang
    ausdE = E.ausdehnung(); lk = BH.lot_kante(XA, YA, tA, XB, YB, tB, oa, ob, MA, MBc, ausdE, A.ausdehnung(), B.ausdehnung())
    M_lot = lk["Ma"] @ np.linalg.inv(lk["Mb"]) if lk["Ma"] is not None and lk["Mb"] is not None else None
    erg["lot_zwang"] = dict(ok=bool(lk["ok_a"] and lk["ok_b"]), grund=[lk["grund_a"], lk["grund_b"]], pruefung=[lk["pruefung_a"], lk["pruefung_b"]], winkel_frei_grad=lk["winkel_frei_grad"],
                            verschiebung_lot_e_grad=lk["verschiebung_lot_e_grad"])
    if Mt is not None and M_lot is not None:
        erg["lot_zwang"]["fehler"] = fehler(M_lot, Mt, PB, m_je, oa)
        for w in (0.5,):                                                                  # Gegenprobe: Lot B verfaelscht
            obf = BH._rot(np.radians(w) * BH.basis(ob)[:, 0]) @ ob; lf = BH.lot_kante(XA, YA, tA, XB, YB, tB, oa, obf, MA, MBc, ausdE, A.ausdehnung(), B.ausdehnung())
            if lf["Ma"] is not None and lf["Mb"] is not None: erg["lot_zwang"][f"lot_b_falsch_{w}_grad"] = dict(ok=bool(lf["ok_a"] and lf["ok_b"]), fehler=fehler(lf["Ma"] @ np.linalg.inv(lf["Mb"]), Mt, PB, m_je, oa))
    print("  lot", json.dumps(erg["lot_zwang"], default=str)[:400], flush=True)
    # B: gefuehrtes Nachmessen (Naeherung = freie Kopplung; Lot-Kopplung nur wenn besser belegt - hier frei, damit B unabhaengig von A gemessen wird)
    fi, sp, M_dir = fuehren(name, A, B, M_frei, sig, fotos, os.path.join(aus, "fuehren"), gpu, vram, resize)
    erg["fuehren"] = fi
    if Mt is not None and M_dir is not None: erg["fuehren"]["fehler"] = fehler(M_dir, Mt, PB, m_je, oa)
    if Mt is not None:
        BAc = np.median(anwenden(M_frei, B.P), 0); neg = {}
        for nm, Mf in (("kurs_2grad", kurs_drehen(M_frei, oa, BAc, 2.0)), ("versatz_0.5m", verschieben(M_frei, oa, 0.5, m_je)), ("versatz_3m", verschieben(M_frei, oa, 3.0, m_je)),
                       ("kurs_180grad", kurs_drehen(M_frei, oa, BAc, 180.0))):
            ni, _, Mn = fuehren(name, A, B, Mf, sig, fotos, os.path.join(aus, "neg_" + nm), gpu, vram, resize)
            ni["naeherung_fehler"] = fehler(Mf, Mt, PB, m_je, oa); ni["fehler_direkt"] = fehler(Mn, Mt, PB, m_je, oa) if Mn is not None else None; neg[nm] = ni
        erg["negativ"] = neg
    print("  fuehren", json.dumps(erg["fuehren"], default=str)[:400], flush=True)
    # C: gemeinsamer Ausgleich (starr, Lot, halbstarr) + Verformungsfaelle
    q = dict(ea=_inl(MA, XA, YA, tA), eb=_inl(MBc, XB, YB, tB))
    if sp:
        X, Y, td = B.P[[s[1] for s in sp]], A.P[[s[0] for s in sp]], np.array([s[2] for s in sp])
        if M_dir is not None: q["direkt"] = _inl(M_dir, X, Y, td)
    fp = BH.feld_parameter(B.P, ob); c = {}
    for nm, kw in (("starr", {}), ("lot", dict(lot=(oa, ob))), ("halbstarr", dict(fp=fp, verformung=True)), ("halbstarr_lot", dict(lot=(oa, ob), fp=fp, verformung=True))):
        for quelle in (("alle", q), ("nur_e", {k: v for k, v in q.items() if k != "direkt"}), ("nur_direkt", {k: v for k, v in q.items() if k == "direkt"})):
            if not quelle[1]: continue
            if quelle[0] == "alle" and "direkt" not in q: continue
            g = BH.ausgleich(quelle[1], M_frei, MA, **kw); z = dict(rest_median=round(g["rest_median"], 5), n=g["n"])
            if kw.get("verformung"): z.update(a=round(g["a"], 5), b_grad=round(float(np.degrees(g["b"])), 3), sigma_a=g.get("sigma_a"), sigma_b_grad=np.degrees(g.get("sigma_b", np.nan)), urteil=BH.verformung_urteil(g))
            if Mt is not None: z["fehler"] = fehler_feld(g, Mt, B.P, B.P, m_je, oa, fp, kw.get("verformung"))
            z["M"] = g["M_AB"].tolist(); c[f"{nm}_{quelle[0]}"] = z
    erg["ausgleich"] = c
    if Mt is not None: erg["verformung"] = verformungsfaelle(A, B, E, MA, M_frei, sp, M_dir, fi, sig, Mt, m_je, oa, ob, os.path.join(aus, "fuehren"))
    erg["_M"] = dict(frei=M_frei.tolist(), lot=M_lot.tolist() if M_lot is not None else None, direkt=M_dir.tolist() if M_dir is not None else None)
    return erg


def _inl(M, X, Y, td, n_max=4000):
    w = np.flatnonzero(BH._rest(M, X, Y, td) <= EK.SCHWELLE_REL)
    if len(w) > n_max: w = np.random.default_rng(0).choice(w, n_max, replace=False)
    return X[w], Y[w], td[w]


def fehler_feld(g, Mt, PB_eigen, PB_wahr_quelle, m_je, oa, fp, verf):
    """Lagefehler der B-Punkte nach dem Ausgleich (mit geschaetztem Feld, wenn halbstarr). PB_eigen = Punkte im (ggf. verformten) B-Rahmen, PB_wahr_quelle = unverformt."""
    X = BH.feld(fp, g["a"], g["b"])(PB_eigen)[0] if verf else PB_eigen; d = np.linalg.norm(anwenden(g["M_AB"], X) - anwenden(Mt, PB_wahr_quelle), axis=1) * m_je
    s, R, _ = EK.zerlegen(g["M_AB"] @ np.linalg.inv(Mt))
    return dict(drehung_grad=round(EK.winkel(R), 3), massstab_prozent=round(abs(s - 1) * 100, 3), lage_median_m=round(float(np.median(d)), 3), lage_p90_m=round(float(np.percentile(d, 90)), 3))


def verformungsfaelle(A, B, E, MA, M_frei, sp, M_dir, fi, sig, Mt, m_je, oa, ob, fuehr_dir):
    """Teil B absichtlich verformt (Punkte + Kameras), Zuordnungen bleiben (Bildmessungen), Kopplung + Ausgleich neu."""
    fp0 = BH.feld_parameter(B.P); out = {}; npz = os.path.join(fuehr_dir, "lg.npz")
    for art, a, b in (("massstab_2", 0.02, 0.0), ("massstab_5", 0.05, 0.0), ("biegung_1", 0.0, np.radians(1.0)), ("biegung_3", 0.0, np.radians(3.0))):
        Bd = B.verformt(BH.feld(fp0, a, b, drehungen=True)); z = dict()
        MBd, pb, okb, gb, (XB, YB, tB) = koppeln_frei(E, Bd); z["frei_b"] = dict(ok=okb, grund=gb, anteil=pb.get("anteil"), rest_rel=pb.get("rest_rel"))
        if MBd is None: out[art] = z; continue
        Mf = MA @ np.linalg.inv(MBd); z["frei_fehler"] = fehler_feld(dict(M_AB=Mf, a=0, b=0), Mt, Bd.P, B.P, m_je, oa, None, False)
        X0, Y0, t0 = BH.punkte(E, A)[:3]; q = dict(ea=_inl(MA, X0, Y0, t0), eb=_inl(MBd, XB, YB, tB))
        if os.path.isfile(npz):
            st, spd = BH.paare_pruefen(npz, A, Bd, Mf, sig); Md, prd, okd, gd, X, Y, td = BH.direkt_koppeln(A, Bd, spd); z["direkt"] = dict(ok=okd, grund=gd, spuren=len(spd), **{k: prd.get(k) for k in ("anteil", "rest_rel", "hebel", "hebel_b")})
            if Md is not None: q["direkt"] = _inl(Md, X, Y, td); z["direkt_fehler"] = fehler_feld(dict(M_AB=Md, a=0, b=0), Mt, Bd.P, B.P, m_je, oa, None, False)
        fp = BH.feld_parameter(Bd.P, ob)
        for nm, kw, qq in (("starr", {}, q), ("halbstarr", dict(fp=fp, verformung=True), q), ("halbstarr_direkt", dict(fp=fp, verformung=True), {k: v for k, v in q.items() if k == "direkt"})):
            if not qq: continue
            g = BH.ausgleich(qq, Mf, MA if "ea" in qq else None, **kw); r = dict(fehler=fehler_feld(g, Mt, Bd.P, B.P, m_je, oa, fp, kw.get("verformung")), rest_median=round(g["rest_median"], 5))
            if kw: r.update(a=round(g["a"], 5), b_grad=round(float(np.degrees(g["b"])), 3), sigma_a=g.get("sigma_a"), sigma_b_grad=float(np.degrees(g.get("sigma_b", np.nan))), urteil=BH.verformung_urteil(g))
            z[nm] = r
        out[art] = z; print("   verformung", art, json.dumps({k: (v.get("fehler") or v) if isinstance(v, dict) else v for k, v in z.items()}, default=str)[:600], flush=True)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fall", action="append", default=[]); ap.add_argument("--echt", action="append", default=[]); ap.add_argument("--aus", required=True)
    ap.add_argument("--gpu", action="store_true"); ap.add_argument("--vram-mb", type=int, default=2500); ap.add_argument("--resize", type=int, default=1600); a = ap.parse_args()
    os.makedirs(a.aus, exist_ok=True); zus = {}
    for f in a.fall:
        name, rest = f.split("=", 1); ordner, fotos = rest.rsplit(":", 1); ej = json.load(open(os.path.join(ordner, "stufe", "eck.json")))
        m_je = json.load(open(os.path.join(os.path.dirname(ordner.rstrip("/")), "selbsttest.json")))["meter_je_einheit"]
        kb = [k for k in ej.get("kanten", []) if k.get("im_baum")]; zi = kb[0]["zwischenmodell"] if kb else 0; em = ej["zwischenmodelle"][zi]["modell"]
        rA, rB = pycolmap.Reconstruction(os.path.join(ordner, "teilA")), pycolmap.Reconstruction(os.path.join(ordner, "teilB"))
        print(f"== {name}: E {em}", flush=True)
        erg = lauf(name, BH.Modell(rA), BH.Modell(rB), BH.Modell(pycolmap.Reconstruction(em)), fotos, os.path.join(a.aus, name), a.gpu, a.vram_mb, a.resize, MB=wahrheit_MB(), m_je=m_je, lot_cache=(rA, rB), rE=pycolmap.Reconstruction(em))
        erg.update(zwischenmodell=em, meter_je_einheit=m_je); json.dump(erg, open(os.path.join(a.aus, name, "ergebnis.json"), "w"), indent=1, default=str); zus[name] = kurz(erg)
        print(json.dumps(zus[name], default=str), flush=True)
    for f in a.echt:
        name, rest = f.split("=", 1); ta, tb, em, fotos = rest.split(":"); rA, rB = pycolmap.Reconstruction(ta), pycolmap.Reconstruction(tb)
        erg = lauf(name, BH.Modell(rA), BH.Modell(rB), BH.Modell(pycolmap.Reconstruction(em)), fotos, os.path.join(a.aus, name), a.gpu, a.vram_mb, a.resize, lot_cache=(rA, rB), rE=pycolmap.Reconstruction(em))
        erg.update(zwischenmodell=em, teil_a=ta, teil_b=tb); json.dump(erg, open(os.path.join(a.aus, name, "ergebnis.json"), "w"), indent=1, default=str); zus[name] = kurz(erg)
        print(json.dumps(zus[name], default=str), flush=True)
    json.dump(zus, open(os.path.join(a.aus, "zusammenfassung.json"), "w"), indent=1, default=str)


def kurz(e):
    g = lambda *p: (lambda d: d)(_get(e, p))
    out = dict(frei=g("frei", "fehler"), hebel=[_get(e, ("frei", "a", "hebel")), _get(e, ("frei", "b", "hebel"))], lot_rel=_get(e, ("lot", "relativ_fehler_grad")),
               lot_winkel_frei=_get(e, ("frei", "lot_winkel_grad")), lot=dict(ok=_get(e, ("lot_zwang", "ok")), fehler=_get(e, ("lot_zwang", "fehler"))), reproj=_get(e, ("reproj", "fehler")),
               fuehren={k: _get(e, ("fuehren", k)) for k in ("kandidatenpaare", "paare_bestaetigt", "spuren", "bestaetigt_naeherung", "fehler")},
               fuehren_direkt={k: _get(e, ("fuehren", "direkt", k)) for k in ("ok", "anteil", "rest_rel", "hebel", "hebel_b", "grund")},
               negativ={k: dict(paare=v.get("paare_bestaetigt"), spuren=v.get("spuren"), ok=_get(v, ("direkt", "ok")), bestaetigt=v.get("bestaetigt_naeherung")) for k, v in (e.get("negativ") or {}).items()},
               ausgleich={k: v.get("fehler") or v.get("rest_median") for k, v in (e.get("ausgleich") or {}).items()})
    return out


def _get(d, p):
    for k in p:
        if not isinstance(d, dict) or k not in d: return None
        d = d[k]
    return d


if __name__ == "__main__": main()

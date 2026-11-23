#!/usr/bin/env python3
"""bruecke2_stufe2.py --fall NAME=<teilA>:<teilB>:<eck.json>[:<npz-ordner-wiederverwenden>] --fotos F --orig <sparse> --m-je X --aus DIR [--gpu]  (23.11.2026)

GEFUEHRTES NACHMESSEN + DIREKTE KOPPLUNG an SELBSTTEST STUFE 2 (Agent ae06, /media/oem/rcdaten/tmp/selbsttest2/: Teile je fuer sich NEU gerechnet, also mit Eigen-
verformung, optional zusaetzlich eingespielte Verformung). Wahrheit = Ursprungsmodell: Teil A wird per robuster Sim3 ueber seine Kamerazentren auf das Ursprungs-
modell gelegt (A = Bezug, wie in der Kette); jede Kopplung B->A wird an den B-Kamerazentren gemessen (Meter): Naht (20 % der B-Kameras naechst an A), Ende (20 %
fernste), Median; Massstab/Drehung der Sim3 'vorhergesagt -> wahr' ueber alle B-Kameras (zeigt, ob die Kopplung den Massstab von B auffaengt).
Varianten: frei (Zwischenmodell), ausgleich_e (tiefengewichtet), direkt (gefuehrtes Nachmessen, gewichtete Sim3), direkt_ausgleich, halbstarr_direkt;
dazu Massstab direkt / Zwischenmodell (erkennt die direkte Kopplung eine Massstabsabweichung?) und Lot-Winkel je Variante."""
import os, sys, json, argparse, numpy as np, pycolmap
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
import bruecke_hebel as BH, seiten_eck_koppeln as EK
from sim3_robust import sim3_meter, anwenden


def zentren(rec):
    return {im.name: np.asarray(im.projection_center(), float) for im in rec.images.values() if im.has_pose}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fall", action="append", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--orig", required=True)
    ap.add_argument("--m-je", type=float, required=True); ap.add_argument("--aus", required=True); ap.add_argument("--gpu", action="store_true"); ap.add_argument("--resize", type=int, default=1024)
    a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True); O = zentren(pycolmap.Reconstruction(a.orig)); zus = {}
    for fall in a.fall:
        name, rest = fall.split("=", 1); teile = rest.split(":"); ta, tb, ej = teile[:3]; wieder = teile[3] if len(teile) > 3 else None; aus = os.path.join(a.aus, name); os.makedirs(aus, exist_ok=True)
        rA, rB = pycolmap.Reconstruction(ta), pycolmap.Reconstruction(tb); A, B = BH.Modell(rA), BH.Modell(rB); e = json.load(open(ej))
        kb = [k for k in e.get("kanten", []) if k.get("im_baum")]; E = BH.Modell(pycolmap.Reconstruction(e["zwischenmodelle"][kb[0]["zwischenmodell"] if kb else 0]["modell"]))
        CA, CB = zentren(rA), zentren(rB); na = [n for n in CA if n in O]; f = sim3_meter(np.array([CA[n] for n in na]), np.array([O[n] for n in na]), schwelle_m=float("inf"), min_anteil=0)
        TA = f["M"]; nb = [n for n in CB if n in O]; XB = np.array([CB[n] for n in nb]); YB = np.array([O[n] for n in nb]); OA = np.array([O[n] for n in na])
        dA = np.min(np.linalg.norm(YB[:, None] - OA[None], axis=2), axis=1); q20, q80 = np.percentile(dA, [20, 80])
        def ev(M, feld=None):
            if M is None: return None
            X = feld(XB)[0] if feld else XB; P = anwenden(TA @ M, X); d = np.linalg.norm(P - YB, axis=1) * a.m_je; s, R, _ = EK.zerlegen(sim3_meter(P, YB, schwelle_m=float("inf"), min_anteil=0)["M"])
            return dict(naht_m=round(float(np.median(d[dA <= q20])), 3), ende_m=round(float(np.median(d[dA >= q80])), 3), median_m=round(float(np.median(d)), 3),
                        drehung_grad=round(EK.winkel(R), 3), massstab_prozent=round((1 / s - 1) * 100, 3))
        erg = dict(fall=name, teil_a=ta, teil_b=tb, eck=ej, a_auf_orig_rest_m=round(f["rest_median_m"] * a.m_je, 3))
        la = BH.lot_modell(rA, a.fotos, cache=os.path.join(aus, "lot_a.json")); lb = BH.lot_modell(rB, a.fotos, cache=os.path.join(aus, "lot_b.json")); oa, ob = np.asarray(la["oben"]), np.asarray(lb["oben"])
        lw = lambda M: None if M is None else round(float(np.degrees(np.arccos(np.clip(abs((EK.zerlegen(M)[1] @ ob) @ oa) / np.linalg.norm(oa) / np.linalg.norm(ob), -1, 1)))), 3)
        XA_, YA_, tA_, _ = BH.punkte(E, A); XB_, YB_, tB_, _ = BH.punkte(E, B)
        MA, pa, oka, ga = EK.kopplung_pruefen(XA_, YA_, E.ausdehnung(), A.ausdehnung(), tiefe=tA_); MB, pb, okb, gb = EK.kopplung_pruefen(XB_, YB_, E.ausdehnung(), B.ausdehnung(), tiefe=tB_)
        erg["frei_pruefung"] = dict(a=dict(ok=oka, grund=ga, **pa), b=dict(ok=okb, grund=gb, **pb))
        if MA is None or MB is None: erg["grund"] = "keine Zwischenmodell-Kopplung"; zus[name] = erg; continue
        M0 = MA @ np.linalg.inv(MB); sig = float(np.sqrt(sum(p["rest_rel"] ** 2 + p["massstab_haelften_rel"] ** 2 for p in (pa, pb)))); V = dict(frei=M0)
        q = {}
        for k, M, X, Y, td in (("ea", MA, XA_, YA_, tA_), ("eb", MB, XB_, YB_, tB_)):
            w = np.flatnonzero(BH._rest(M, X, Y, td) <= EK.SCHWELLE_REL)[:4000]; q[k] = (X[w], Y[w], td[w])
        V["ausgleich_e"] = BH.ausgleich(q, M0, MA)["M_AB"]
        if la.get("quelle") == "fluchtpunkte" and lb.get("quelle") == "fluchtpunkte": V["ausgleich_e_lot"] = BH.ausgleich(q, M0, MA, lot=(oa, ob))["M_AB"]   # Lot-Zwang (5 FG)
        fo = os.path.join(wieder or aus, "fuehren"); npz = os.path.join(fo, "lg.npz")
        if not os.path.isfile(npz):
            kp = BH.kandidaten_paare(A, B.transformiert(V["ausgleich_e"])); erg["kandidatenpaare"] = len(kp)
            npz = BH.lg_paare(kp, a.fotos, fo, vram_mb=2500, resize=a.resize) if (kp and a.gpu) else None
        if npz and os.path.isfile(npz):
            st, sp = BH.paare_pruefen(npz, A, B, V["ausgleich_e"], sig); z2d = st.pop("_z2d", []); Md, prd, okd, gd, X, Y, td = BH.direkt_koppeln(A, B, sp); erg["fuehren"] = dict(st, direkt=dict(ok=okd, grund=gd, **prd))
            ge = BH.ausgleich_epipolar(A, B, z2d, V["ausgleich_e"])
            if ge: V["epipolar"] = ge["M_AB"]; erg["epipolar"] = dict(rest_px_median=ge["rest_px_median"], n=ge["n"])
            if Md is not None:
                erg["fuehren"]["bestaetigt"] = BH.bestaetigt(Md, V["ausgleich_e"], B.P, sig); V["direkt"] = Md
                w = np.flatnonzero(BH._rest(Md, X, Y, td) <= EK.SCHWELLE_REL); qd = dict(direkt=(X[w], Y[w], td[w])); V["direkt_ausgleich"] = BH.ausgleich(qd, Md)["M_AB"]
                if "ausgleich_e_lot" in V: V["direkt_lot"] = BH.ausgleich(qd, Md, lot=(oa, ob))["M_AB"]
                fp = BH.feld_parameter(B.P, ob); gh = BH.ausgleich(qd, Md, fp=fp, verformung=True); erg["halbstarr_direkt"] = dict(a=gh["a"], b_grad=float(np.degrees(gh["b"])), urteil=BH.verformung_urteil(gh))
                erg["massstab_direkt_gegen_e_prozent"] = round((EK.zerlegen(V["direkt_ausgleich"])[0] / EK.zerlegen(V["ausgleich_e"])[0] - 1) * 100, 3)
                erg["varianten"] = {k: dict(ev(M), lot_winkel_grad=lw(M)) for k, M in V.items()}
                erg["varianten"]["halbstarr_direkt"] = dict(ev(gh["M_AB"], BH.feld(fp, gh["a"], gh["b"])), lot_winkel_grad=lw(gh["M_AB"]))
        erg.setdefault("varianten", {k: dict(ev(M), lot_winkel_grad=lw(M)) for k, M in V.items()}); erg["lot"] = dict(a=la, b=lb)
        json.dump(erg, open(os.path.join(aus, "ergebnis.json"), "w"), indent=1, default=str); zus[name] = erg
        print("==", name, json.dumps({k: erg.get(k) for k in ("varianten", "massstab_direkt_gegen_e_prozent", "halbstarr_direkt")}, default=str), flush=True)
        print("   fuehren", json.dumps({k: v for k, v in (erg.get("fuehren") or {}).items() if k != "direkt"}, default=str)[:300], (erg.get("fuehren") or {}).get("direkt"), flush=True)
    json.dump(zus, open(os.path.join(a.aus, "zusammenfassung.json"), "w"), indent=1, default=str)


if __name__ == "__main__": main()

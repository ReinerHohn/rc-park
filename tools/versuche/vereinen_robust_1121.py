#!/usr/bin/env python3
"""vereinen_robust_1121.py - BELASTUNGSPROBE fuer tools/seiten_vereinen.py (Nutzer 21.11.2026: "beweise, dass du es bei jeder Wand in Zukunft richtig ausrichten wirst").
Die Klappung (Aufeinanderlegen der aehnlichen Waende) war am Martinstor in Lage (35 % der Turmhoehe), Lot (4,5 Grad) und Drehung (16,7 Grad) falsch. Seit 21.11. kommen diese drei
aus der Geometrie der dichten Wolken. Probe: die Klappung wird ABSICHTLICH zusaetzlich verfaelscht (Kippung bis 8 Grad, Drehung um das Lot bis +-20 Grad, Verschiebung bis 30 % der
Turmhoehe, Zufall mit festem Keim) - die Endlage der zweiten Seite muss trotzdem dieselbe bleiben. Gemessen je Lauf gegen den unverfaelschten Lauf: Verschiebung der B-Wolke (Median,
% der Bauhoehe), Unterschied Wandrichtung und Lot (Grad), Urteil.
Aufruf: vereinen_robust_1121.py <modell_A> <modell_B> <db> <dicht_a.ply> <dicht_b.ply> <arbeitsordner> [--laeufe 8]"""
import sys, os, json, argparse
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import seiten_vereinen as SV


def rot(achse, grad):
    a = np.asarray(achse, float); a /= np.linalg.norm(a); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]]); w = np.radians(grad); return np.eye(3) + np.sin(w) * K + (1 - np.cos(w)) * K @ K


def main():
    ap = argparse.ArgumentParser(); [ap.add_argument(n) for n in ("a", "b", "db", "da", "dbp", "aus")]; ap.add_argument("--laeufe", type=int, default=8); a = ap.parse_args()
    orig = SV.geklappt; rng = np.random.default_rng(7); DB = SV.ply_punkte(a.dbp); DB = DB[np.random.default_rng(0).choice(len(DB), min(200000, len(DB)), replace=False)]; E = []; ref = None
    for i in range(a.laeufe + 1):
        st = dict(kipp=0.0, dreh=0.0, schub=0.0) if i == 0 else dict(kipp=float(rng.uniform(2, 8)), dreh=float(rng.uniform(-20, 20)), schub=float(rng.uniform(0.05, 0.30)))
        def falsch(P, Q, up, *aa, **kk):
            g = orig(P, Q, up, *aa, **kk)
            if g is None or i == 0: return g
            s, R, t, inl = g; c = np.median(Q[inl], 0); H = float(np.percentile(np.linalg.norm(Q[inl] - c, axis=1), 90)) * 2
            q = np.cross(up, rng.normal(size=3)); dR = rot(up, st["dreh"]) @ rot(q, st["kipp"]); sh = np.cross(up, rng.normal(size=3)); sh = sh / np.linalg.norm(sh) * st["schub"] * H
            return s, dR @ R, dR @ (t - c) + c + sh, inl
        SV.geklappt = falsch; od = os.path.join(a.aus, f"lauf{i}"); rc = SV.main([a.a, a.b, a.db, "--aus", od, "--dicht-a", a.da, "--dicht-b", a.dbp]); d = json.load(open(os.path.join(od, "vereinen.json")))
        M = np.array(d["B_nach_A"]) if "B_nach_A" in d else None
        if i == 0: ref = (M, d); continue
        X0 = DB @ ref[0][:3, :3].T + ref[0][:3, 3]; H = float(ref[1]["bauhoehe"])
        if M is None: E.append(dict(st, rc=rc, urteil=d.get("urteil"))); continue
        X1 = DB @ M[:3, :3].T + M[:3, 3]; R0 = ref[0][:3, :3] / np.cbrt(np.linalg.det(ref[0][:3, :3])); R1 = M[:3, :3] / np.cbrt(np.linalg.det(M[:3, :3]))
        E.append(dict(st, rc=rc, urteil=d.get("urteil"), lage_median_proz=float(np.median(np.linalg.norm(X1 - X0, axis=1)) / H * 100), drehung_gegen_ref_grad=float(np.degrees(np.arccos(np.clip((np.trace(R1 @ R0.T) - 1) / 2, -1, 1)))),
                      gemeldet=dict(lot=(d.get("lot_b") or {}).get("kippung_grad"), dreh=(d.get("dreh_b") or {}).get("verdrehung_grad"), versatz=(d.get("spitzen") or {}).get("klapp_versatz"))))
    SV.geklappt = orig; json.dump(dict(referenz=ref[1].get("urteil"), laeufe=E), open(os.path.join(a.aus, "robust.json"), "w"), indent=1); print("\n==== BELASTUNGSPROBE ====")
    for e in E: print(f"Klappung verfaelscht um Kippung {e['kipp']:.1f} Grad, Drehung {e['dreh']:+.1f} Grad, Verschiebung {100 * e['schub']:.0f} % -> rc {e['rc']} {e['urteil']}; Endlage gegen Referenz: " + (f"Lage {e['lage_median_proz']:.2f} % der Bauhoehe, Drehung {e['drehung_gegen_ref_grad']:.2f} Grad" if "lage_median_proz" in e else "KEINE"))
    return 0


if __name__ == "__main__": sys.exit(main())

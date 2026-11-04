#!/usr/bin/env python3
"""doppelschicht.py - Doppelschicht-Detektor (Plan 2.4): enthaelt eine Wandflaeche der Punktwolke ZWEI Ebenen (Doppeldach = Clip-Versatz/Doming) statt einer?

Je z-Schicht (+-dz) wird die Tiefe t = P . u (u = Aussennormale der Seite, wie hybrid_abgleich.SEITEN) der Punkte VOR der Achse betrachtet und ein Gauss-Modell mit 1 gegen 2
Komponenten per BIC verglichen (eigene 1D-EM, nur numpy). Eine Schicht ist DOPPELT, wenn  BIC2 + --bic-min < BIC1,  Abstand der Mittel >= --abstand-m  und beide Gewichte >= --gewicht.
ANNAHMEN (Argumente, nicht aus Daten abgeleitet): abstand 0,4 m (> Rauschen der Quellen ~0,2 m, < sichtbarer Versatz 1 m), gewicht 0,05 (Befund: zweite Ebene der unkorrigierten Wolke hat nur 8-17 %), bic-min 20, dz 0,5 m, Schrittweite 1 m.
Grenze: eine echte Stufe der Fassade (Gesims, Vorsprung) ist von aussen NICHT von einem Versatz zu unterscheiden -> Treffer sind Pruefhinweise, kein Beweis; Schichten mit Stufe im
Generator (--stl) gegenpruefen. Dachneigung verbreitert die Schicht (dz/tan(Neigung), bei 77 Grad +-0,12 m): deshalb Abstand-Schwelle > 0,3.
  python3 -I tools/doppelschicht.py modelle/<objekt>/objekt.json --wolke datei.npy [--wolke ...] [--seite Nord(-x)] [--zlo 41 --zhi 55] [--ausgabe name]
  python3 -I tools/doppelschicht.py --selbsttest        (synthetisch: 1 Ebene darf nicht, 2 Ebenen muessen gemeldet werden)
Ausgabe: modelle/<objekt>/audit/doppelschicht_<name>.json; Exit 0 = keine Doppelschicht, 4 = mindestens eine Schicht doppelt.
"""
import sys, os, json, argparse, numpy as np

SEITEN = {"Nord(-x)": (-1.0, 0.0), "Sued(+x)": (1.0, 0.0), "Ost(+y)": (0.0, 1.0), "West(-y)": (0.0, -1.0)}      # wie hybrid_abgleich.SEITEN

def _ll(t, w, m, s):
    return np.log(np.maximum(w * np.exp(-0.5 * ((t[:, None] - m) / s) ** 2) / (s * np.sqrt(2 * np.pi)), 1e-300))

def gmm2(t, iters=200, smin=0.03):
    """Zwei-Komponenten-EM in 1D -> (w, m, s, loglik). Start: Quartile."""
    q1, q3 = np.percentile(t, [25, 75]); m = np.array([q1, q3]); s = np.array([max(t.std(), smin)] * 2); w = np.array([0.5, 0.5]); ll0 = -np.inf
    for _ in range(iters):
        L = _ll(t, w, m, s); mx = L.max(1, keepdims=True); r = np.exp(L - mx); tot = r.sum(1, keepdims=True); r /= tot; ll = float((mx[:, 0] + np.log(tot[:, 0])).sum())
        nk = np.maximum(r.sum(0), 1e-9); w = nk / len(t); m = (r * t[:, None]).sum(0) / nk; s = np.maximum(np.sqrt((r * (t[:, None] - m) ** 2).sum(0) / nk), smin)
        if abs(ll - ll0) < 1e-6 * abs(ll): break
        ll0 = ll
    return w, m, s, ll

def schicht(t, a):
    """-> dict fuer eine Schicht (n, Mittel/Sigma/Gewicht, delta_bic, doppelt)."""
    n = len(t); ll1 = float((-0.5 * ((t - t.mean()) / max(t.std(), 1e-3)) ** 2 - np.log(max(t.std(), 1e-3) * np.sqrt(2 * np.pi))).sum())
    bic1 = -2 * ll1 + 2 * np.log(n); w, m, s, ll2 = gmm2(t); bic2 = -2 * ll2 + 5 * np.log(n); o = np.argsort(m); w, m, s = w[o], m[o], s[o]
    d = float(m[1] - m[0]); gain = float(bic1 - bic2); doppelt = bool(gain >= a.bic_min and d >= a.abstand_m and w.min() >= a.gewicht)
    return dict(n=n, mittel=[round(float(x), 3) for x in m], sigma=[round(float(x), 3) for x in s], gewicht=[round(float(x), 3) for x in w], abstand_m=round(d, 3), bic_gewinn=round(gain, 1), doppelt=doppelt)

def analysiere(P, u, a):
    u = np.array(u); v = np.array([-u[1], u[0]]); rows = []
    t_all = P[:, :2] @ u; l_all = P[:, :2] @ v
    for z in np.arange(a.zlo, a.zhi + 0.01, a.schritt):
        k = (np.abs(P[:, 2] - z) <= a.dz) & (t_all > 0.2) & (t_all < a.tmax) & (np.abs(l_all) < a.quer)
        if k.sum() < a.minpts: rows.append(dict(z=round(float(z), 2), n=int(k.sum()), status="zu wenige Punkte")); continue
        t = t_all[k]
        if len(t) > a.maxpts: t = np.random.default_rng(0).choice(t, a.maxpts, replace=False)
        rows.append(dict(z=round(float(z), 2), status="ok", **schicht(t, a)))
    return rows

def selbsttest(a):
    rng = np.random.default_rng(1); fehler = []
    def wolke(delta):
        z = rng.uniform(40, 56, 60000); t = 3 + 0.2 * (z - 48) + rng.normal(0, 0.12, z.size) + (rng.random(z.size) < 0.5) * delta; y = rng.uniform(-3, 3, z.size)
        return np.c_[-t, y, z]                    # Nord: Tiefe = -x
    for delta, soll in ((0.0, False), (0.8, True), (0.25, False)):
        R = [r for r in analysiere(wolke(delta), SEITEN["Nord(-x)"], a) if r["status"] == "ok"]; n_d = sum(r["doppelt"] for r in R); ist = n_d > len(R) // 2
        print(f"  Versatz {delta:.2f} m: {n_d}/{len(R)} Schichten doppelt -> {'doppelt' if ist else 'einfach'} (Soll {'doppelt' if soll else 'einfach'})")
        if ist != soll: fehler.append(delta)
    print("SELBSTTEST", "BESTANDEN" if not fehler else f"FEHLGESCHLAGEN bei {fehler}"); return 1 if fehler else 0

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("--wolke", action="append", default=[]); ap.add_argument("--seite", default="Nord(-x)", choices=list(SEITEN))
    ap.add_argument("--zlo", type=float, default=43.0); ap.add_argument("--zhi", type=float, default=49.0); ap.add_argument("--dz", type=float, default=0.5); ap.add_argument("--schritt", type=float, default=1.0)
    ap.add_argument("--tmax", type=float, default=7.0); ap.add_argument("--quer", type=float, default=1.0, help="halbe Breite quer zur Normalen: nur die Mitte der Flaeche, sonst mischen die Nachbarflaechen des Helms (Pyramide) eine scheinbare zweite Ebene hinein (Befund 3.11.: bei 4,6 m 15 Fehlalarme)"); ap.add_argument("--minpts", type=int, default=300); ap.add_argument("--maxpts", type=int, default=60000)
    ap.add_argument("--abstand-m", type=float, default=0.4); ap.add_argument("--gewicht", type=float, default=0.05); ap.add_argument("--bic-min", type=float, default=20.0); ap.add_argument("--ausgabe", default=None); ap.add_argument("--selbsttest", action="store_true")
    a = ap.parse_args()
    if a.selbsttest: sys.exit(selbsttest(a))
    if not a.objekt or not a.wolke: sys.exit("objekt.json und mindestens eine --wolke noetig")
    od = os.path.dirname(os.path.abspath(a.objekt)); erg = {}; treffer = 0
    for wp in a.wolke:
        P = np.load(wp).astype(float); rows = analysiere(P, SEITEN[a.seite], a); name = os.path.basename(os.path.dirname(wp)) + "/" + os.path.basename(wp)
        print(f"\n{name}  ({len(P)} Punkte, Seite {a.seite})\n  {'z':>6}{'n':>8}{'Mittel':>16}{'Gewicht':>14}{'Abstand':>9}{'dBIC':>8}")
        for r in rows:
            if r["status"] != "ok": print(f"  {r['z']:6.1f}{r['n']:8d}  {r['status']}"); continue
            print(f"  {r['z']:6.1f}{r['n']:8d}  {r['mittel'][0]:6.2f}/{r['mittel'][1]:6.2f}  {r['gewicht'][0]:5.2f}/{r['gewicht'][1]:5.2f}{r['abstand_m']:9.2f}{r['bic_gewinn']:8.0f}" + ("   DOPPELT" if r["doppelt"] else ""))
        nd = sum(1 for r in rows if r.get("doppelt")); treffer += nd; erg[name] = dict(punkte=len(P), doppelte_schichten=nd, schichten=rows)
    out = dict(seite=a.seite, parameter={k: getattr(a, k) for k in ("zlo", "zhi", "dz", "schritt", "tmax", "quer", "minpts", "abstand_m", "gewicht", "bic_min")}, annahme="Schwellen sind ANNAHMEN; Gesimsstufen sind nicht von Versatz zu unterscheiden", wolken=erg)
    pf = os.path.join(od, "audit", f"doppelschicht_{a.ausgabe or 'wolken'}.json"); os.makedirs(os.path.dirname(pf), exist_ok=True); json.dump(out, open(pf, "w"), indent=1, ensure_ascii=False)
    print(f"\n{treffer} doppelte Schicht(en); Bericht {pf}"); sys.exit(4 if treffer else 0)

if __name__ == "__main__":
    main()

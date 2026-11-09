#!/usr/bin/env python3
"""gauben_unterscheidung.py - Foto entscheidet die Gaubenform (Wolke trennt Schlepp/Satteldach nicht).
Unterscheidungskanten: Satteldach hat FIRSTLINIE und GIEBELDREIECK (zwei Schraegen Traufe->Scheitel an der Front), Schleppgaube hat beides NICHT.
Je Gaube und Kantenart: Gradientenantwort (Sobel des Originalfotos, Mittel laengs der projizierten Kante) fuer seitliche/tiefe Lageverschiebungen (+-0,3 m, +-0,2 m) -> Spitze gegen Median der Verschiebungen
(Ziegeltextur liefert Grundrauschen, deshalb Spitze/Median, nicht Absolutwert). Kante 'belegt' in einem Foto: Spitze/Median >= --ratio (1,5) UND Spitze >= Median + 3 MAD. Entscheid: Satteldach nur, wenn First UND Giebel in >= 50 % der
sehenden Fotos (>= 3 Fotos, >= 2 Richtungen) belegt; Schlepp, wenn beide in genug sehenden Fotos NICHT belegt UND die Schleppkante (Frontoberkante) belegt ist; sonst OFFEN. Beweis --synth (Zeichnung mit/ohne First).
Aufruf: gauben_unterscheidung.py GAUBE.json --gitter G --kam KAM --bilder DIR [--bilder2 DIR2] --out OUT.json [--audit DIR] ; --synth
Python: venv-seg -I. GPU: nur Projektion/Gradient auf CPU (kleine Datenmenge, ~100 Polylinien x 125 Verschiebungen); ANNAHME: reicht (Abruf < 1 min)."""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
import cv2
from kanten_tor import log, Fotos
import muster_fit as MF


def gradient_bild(pfad, breite=1500):
    im = cv2.imread(pfad, 0)
    if im is None: return None, 1.0
    s = breite / im.shape[1]; im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); im = cv2.GaussianBlur(im, (0, 0), 1.2).astype(np.float32)
    gx = cv2.Sobel(im, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(im, cv2.CV_32F, 0, 1, ksize=3); G = np.hypot(gx, gy); G = G / (np.percentile(G, 95) + 1e-6); return np.clip(G, 0, 2.0), s


def antwort(Gr, s, F, f, pts):
    u, v, z = F.proj(f, pts); u = u * s * (Gr.shape[1] / (F.KAM[f]["W"] * s)); v = v * s * (Gr.shape[1] / (F.KAM[f]["W"] * s))
    ok = (z > 1) & (u >= 0) & (u < Gr.shape[1] - 1) & (v >= 0) & (v < Gr.shape[0] - 1)
    if ok.mean() < 0.9: return None
    uu = np.clip(np.round(u).astype(int), 1, Gr.shape[1] - 2); vv = np.clip(np.round(v).astype(int), 1, Gr.shape[0] - 2); return float(np.mean([Gr[max(vv_ - 1, 0):vv_ + 2, max(uu_ - 1, 0):uu_ + 2].max() for uu_, vv_ in zip(uu, vv)]))


def kantenarten(par, fam, t0, o0, A, B, u, n, dx, dd):
    """Polylinien-Gruppen je Kantenart (Punkte dicht)."""
    P = MF.gaube_umriss(par, fam, t0, o0, A, B, u, n, dx=dx, dd=dd, schritt=0.05); dens = lambda pl: MF.poly_pts(pl, 0.05)
    if fam == "satteldach": pen = P[0]; return dict(first=dens(P[1]), giebel=dens(np.array([pen[1], pen[2], pen[3]])), front_unten=dens(np.array([pen[0], pen[1]])))
    pen = P[0]; return dict(schleppkante=dens(np.array([pen[1], pen[2]])), wange=dens(np.vstack([P[1], P[2]])), front_unten=dens(np.array([pen[0], pen[1]])))


def messen(res, F, fotos_je_gaube, bilder, rah, famen=("satteldach", "schlepp"), shifts=None):
    u, n, of = rah; A, B = res["dachebene"]["a"], res["dachebene"]["b"]; shifts = shifts or [(dx, dd) for dx in np.arange(-0.3, 0.301, 0.1) for dd in np.arange(-0.2, 0.201, 0.1)]; out = {}
    for fam in famen:
        par = res["fits"][fam]["par"]; out[fam] = []
        for gi, ins in enumerate(res["instanzen"]):
            lst = fotos_je_gaube[gi]; zeile = dict(gaube=gi, kanten={})
            for f in lst:
                Gr, s = bilder(f)
                if Gr is None: continue
                resp = {}
                for dx, dd in shifts:
                    for nm, pts in kantenarten(par, fam, ins["t"] - par[-1] * 0, ins["off"], A, B, u, n, dx, dd).items():
                        r_ = antwort(Gr, s, F, f, pts); resp.setdefault(nm, []).append(r_)
                for nm, v in resp.items():
                    v = np.array([x for x in v if x is not None]);
                    if len(v) < 5: continue
                    med = float(np.median(v)); mad = float(np.median(np.abs(v - med))) + 1e-6; pk = float(v.max()); zeile["kanten"].setdefault(nm, []).append(dict(foto=f, spitze=pk, median=med, ratio=pk / max(med, 1e-6), mad_abstand=(pk - med) / mad))
            out[fam].append(zeile)
    return out


def belegt(e, ratio): return e["ratio"] >= ratio and e["mad_abstand"] >= 3.0


def entscheiden(M, ratio=1.5, nmin=3, anteil=0.5):
    rep = {}
    for fam, liste in M.items():
        for z in liste:
            for nm, es in z["kanten"].items():
                rep.setdefault((fam, nm), []).append((z["gaube"], len(es), sum(belegt(e, ratio) for e in es)))
    zus = {}
    for (fam, nm), lst in rep.items():
        zus[fam + "/" + nm] = dict(gauben=[dict(gaube=g_, fotos=n_, belegt=b_) for g_, n_, b_ in lst], gauben_mit_beleg=sum(1 for _, n_, b_ in lst if n_ >= nmin and b_ >= anteil * n_), gauben_mit_daten=sum(1 for _, n_, b_ in lst if n_ >= nmin), gauben_ohne_beleg=sum(1 for _, n_, b_ in lst if n_ >= nmin and b_ < anteil * n_))
    fi, gi_, sk = zus.get("satteldach/first"), zus.get("satteldach/giebel"), zus.get("schlepp/schleppkante")
    if not fi or not gi_ or fi["gauben_mit_daten"] < 2: ent = ("OFFEN", "zu wenig sehende Fotos je Gaube fuer die Unterscheidungskanten")
    elif fi["gauben_mit_beleg"] >= 0.5 * fi["gauben_mit_daten"] and gi_["gauben_mit_beleg"] >= 0.5 * gi_["gauben_mit_daten"]: ent = ("satteldach", "First und Giebel in >= 50 % der sehenden Fotos belegt")
    elif fi["gauben_ohne_beleg"] >= 0.5 * fi["gauben_mit_daten"] and gi_["gauben_ohne_beleg"] >= 0.5 * gi_["gauben_mit_daten"]: ent = ("schlepp", "weder First noch Giebeldreieck belegt (Gradientenspitze/Median < %.1f), Schleppkante %s" % (ratio, ("belegt in %d von %d Gauben" % (sk["gauben_mit_beleg"], sk["gauben_mit_daten"])) if sk else "nicht gemessen"))
    else: ent = ("OFFEN", "First/Giebel nur teilweise belegt")
    return dict(entscheid=ent[0], grund=ent[1], kantenarten=zus, ratio=ratio)


def main():
    res = json.load(open(a[1])); G = MF.gitter_laden(g("--gitter", "", str)); rah = MF.rahmen_auto(G); F = Fotos(g("--kam", "", str), g("--stabil", "", str) or ".", g("--bilder", "", str)); dirs = [g("--bilder", "", str)] + ([g("--bilder2", "", str)] if "--bilder2" in a else [])
    cache = {}
    def bilder(f):
        if f not in cache:
            cache.clear()
            for d in dirs:
                p = os.path.join(d, f)
                if os.path.exists(p): cache[f] = gradient_bild(p); break
            else: cache[f] = (None, 1.0)
        return cache[f]
    u, n, of = rah; fl = {}
    for gi, ins in enumerate(res["instanzen"]):
        P = u * ins["t"] - n * ins["off"]; P = np.array([P[0], P[1], res["dachebene"]["a"] + res["dachebene"]["b"] * ins["off"]]); cand = []
        for f, k in F.KAM.items():
            if not any(os.path.exists(os.path.join(d, f)) for d in dirs): continue
            C = np.array(k["C"]); uu, vv, zz = F.proj(f, P[None]); dist = float(np.linalg.norm(P - C))
            if zz[0] > 2 and 0 < uu[0] < k["W"] and 0 < vv[0] < k["H"] and 8 < dist < 120 and float((n[:2] @ (C[:2] - P[:2]))) < 0 and k["f"] * 0.25 / dist > 8:
                cand.append((float(np.degrees(np.arctan2(C[1] - P[1], C[0] - P[0]))), dist, f))
        pick = []; sek = {}
        for az, dist, f in sorted(cand, key=lambda x: x[1]):
            sk = int((az % 360) // 20)
            if sek.get(sk, 0) < 1: sek[sk] = 1; pick.append(f)
        pick += [f for az, dist, f in cand if f.startswith("od_") and f not in pick]; fl[gi] = pick[:g("--nmax", 10, int)]
    log("Fotos je Gaube:", {k: len(v) for k, v in fl.items()}, "dachfotos:", sorted({f for v in fl.values() for f in v if f.startswith("od_")}))
    M = messen(res, F, fl, bilder, rah); E = entscheiden(M, g("--ratio", 1.5)); log("ENTSCHEID Gaubenform:", E["entscheid"], "-", E["grund"])
    for k, v in E["kantenarten"].items(): log("  %-22s Gauben mit Daten %d, mit Beleg %d, ohne Beleg %d  %s" % (k, v["gauben_mit_daten"], v["gauben_mit_beleg"], v["gauben_ohne_beleg"], [(x["gaube"], x["belegt"], x["fotos"]) for x in v["gauben"]]))
    json.dump(dict(entscheidung=E, messung=M, fotos_je_gaube=fl), open(g("--out", "", str), "w"), indent=1, default=float); log("geschrieben:", g("--out", "", str))


if __name__ == "__main__" and "--synth" not in a: main()
